"""Explicit OJS delivery of an immutable package, with durable write intents.

An uncertain remote write is never retried. The Study reservation remains occupied
after any final-submit attempt until the actual journal outcome is recorded.
"""

import hashlib
import html
import json
import os
from contextlib import contextmanager, nullcontext
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import Field, field_validator

from . import publication
from .integrity import frozen_workspace
from .manuscript import Document, number_text
from .models import Claim, Paper, Record, Submission, SubmissionState, now, uid
from .ojs import OJSClient, OJSDraft, OJSError, OJSKeyword, OJSPublicationMetadata, OJSReceipt, OJSSettings
from .submission_package import Package, verify as verify_package
from .venue_compiler import _redact, policy_fingerprint
from .venue_policy import MAX_SOURCE_BYTES, VenuePolicy, _origin, refresh_policy, validate_policy
from .workspace import Workspace, digest_file, safe_relative, write_json


class Upload(Record):
    path: str
    genre_id: int = Field(gt=0, strict=True)

    @field_validator("path")
    @classmethod
    def package_file(cls, value):
        # Validate portable syntax independently of a real workspace.
        safe_relative(Path.cwd(), value)
        return value


class PortalSettings(Record):
    connection: OJSSettings
    draft: OJSDraft
    uploads: list[Upload] = Field(min_length=1, max_length=30)
    remote_submission_id: int | None = Field(default=None, gt=0, strict=True)


class PortalPlan(Record):
    id: str = Field(default_factory=lambda: uid("portal"))
    submission_id: str
    package_sha256: str
    settings: PortalSettings
    metadata: OJSPublicationMetadata
    files: dict[str, str]
    prepared_at: str = Field(default_factory=now)


class StoredPlan(PortalPlan):
    artifact_sha256: str


class PortalEventData(Record):
    id: str = Field(default_factory=lambda: uid("portal-event"))
    plan_id: str
    sequence: int = Field(gt=0, strict=True)
    previous_sha256: str | None
    kind: Literal["intent", "success", "failure", "inspection", "reconciliation", "publication"]
    operation: str
    recorded_at: str = Field(default_factory=now)
    values: dict


class PortalEvent(PortalEventData):
    artifact_sha256: str


def _root(ws, plan):
    return ws.path(f"portals/{plan.id}")


def _plans(ws: Workspace, *, db=None) -> list[StoredPlan]:
    plans = ws.list("portal_plan", StoredPlan) if db is None else publication._rows(db, "portal_plan", StoredPlan)
    root = ws.path("portals")
    actual = {ws.path(path.relative_to(ws.root).as_posix()).name for path in root.iterdir()} if root.exists() else set()
    if actual != {plan.id for plan in plans}:
        raise ValueError("Portal registry differs from preserved delivery evidence; writes and cancellation are blocked")
    events = ws.list("portal_event", PortalEvent) if db is None else publication._rows(db, "portal_event", PortalEvent)
    if {event.plan_id for event in events} - {plan.id for plan in plans}:
        raise ValueError("Portal events refer to an unregistered delivery plan")
    return plans


def _history(ws: Workspace, plan: StoredPlan, *, db=None, allow_unindexed: bool = False) -> list[PortalEvent]:
    _plans(ws, db=db)
    stored = ws.get("portal_plan", plan.id, StoredPlan) if db is None else publication._get(db, "portal_plan", plan.id, StoredPlan)
    if stored != plan:
        raise ValueError("Portal plan differs from its indexed immutable observation")
    root = _root(ws, plan)
    if (digest_file(root / "plan.json") != plan.artifact_sha256
            or PortalPlan.model_validate_json((root / "plan.json").read_bytes()) != PortalPlan.model_validate(plan.model_dump(exclude={"artifact_sha256"}))):
        raise ValueError("Portal plan artifact changed")
    if db is None:
        events = ws.list("portal_event", PortalEvent)
    else:
        events = publication._rows(db, "portal_event", PortalEvent)
    events = sorted((event for event in events if event.plan_id == plan.id), key=lambda event: event.sequence)
    expected = {"plan.json"}
    previous = None
    for index, event in enumerate(events, 1):
        relative = f"{event.sequence:04d}-{event.id}.json"
        path = root / relative
        if event.sequence != index or event.previous_sha256 != previous or digest_file(path) != event.artifact_sha256:
            raise ValueError("Portal history artifact or sequence changed")
        if PortalEventData.model_validate_json(path.read_bytes()) != PortalEventData.model_validate(event.model_dump(exclude={"artifact_sha256"})):
            raise ValueError("Portal history differs from its immutable artifact")
        previous = event.artifact_sha256
        expected.add(relative)
    actual = {path.name for path in root.iterdir()}
    if (not expected <= actual) or (not allow_unindexed and actual != expected):
        raise ValueError("Uncommitted portal evidence requires reconciliation; writes are blocked")
    return events


def _append(ws, plan, kind, operation, values, *, db=None):
    history = _history(ws, plan, db=db)
    data = PortalEventData(plan_id=plan.id, sequence=len(history) + 1,
        previous_sha256=history[-1].artifact_sha256 if history else None,
        kind=kind, operation=operation, values=values)
    path = _root(ws, plan) / f"{data.sequence:04d}-{data.id}.json"
    write_json(path, data)
    event = PortalEvent(**data.model_dump(), artifact_sha256=digest_file(path))
    # Preserve evidence if commit acknowledgement is lost. An orphan blocks writes.
    if db is None:
        ws.save("portal_event", event)
    else:
        db.execute("INSERT INTO records VALUES (?,?,?)", ("portal_event", event.id, event.model_dump_json()))
    return event


def _package(ws, plan):
    submission = ws.get("submission", plan.submission_id, Submission)
    report = verify_package(ws, submission, fresh=False)
    if not report["passed"] or not report["ready"]:
        raise ValueError("Portal requires an intact ready package: " + "; ".join(report["errors"]))
    package = ws.get("package", submission.id, Package)
    if package.manifest_sha256 != plan.package_sha256 or any(package.files.get(path) != value for path, value in plan.files.items()):
        raise ValueError("Portal package binding changed")
    return submission, package


def _review_html(text: str, doc: Document, *, anonymized: bool) -> str:
    if anonymized:
        text = _redact(text, doc)
    return html.escape(text, quote=False)


def _abstract(doc: Document, snapshot: Workspace, *, anonymized: bool) -> str:
    section = next((section for section in doc.sections if section.heading == "Abstract"), None)
    parts = []
    for block in section.blocks if section else []:
        if block.kind == "prose":
            parts.append(block.text)
        elif block.kind == "claim":
            claim = snapshot.get("claim", block.ref, Claim)
            unit = f" {claim.unit}" if claim.unit else ""
            parts.append(f"{claim.description}: {number_text(claim.value)}{unit}.")
    text = " ".join(parts)
    if not text.strip():
        raise ValueError("Canonical abstract is required for portal metadata")
    # OJS stores this RichTextarea as HTML. Prose remains literal, and verified
    # numeric sentences contain neither Markdown decoration nor audit labels.
    return _review_html(text, doc, anonymized=anonymized)


def prepare(ws: Workspace, submission: Submission, settings: PortalSettings) -> StoredPlan:
    """Bind reviewed file roles and canonical metadata without uploading anything."""
    settings = PortalSettings.model_validate(settings)
    with ws.lock(f"submission-{submission.id}"):
        current = ws.get("submission", submission.id, Submission)
        if current.state != SubmissionState.SUBMISSION_READY:
            raise ValueError("Portal preparation requires a ready unused candidate")
        from .revision_submission import assert_regular_candidate
        assert_regular_candidate(ws, current)
        if any(plan.submission_id == current.id for plan in _plans(ws)):
            raise ValueError("This candidate already has a portal plan; use its existing plan")
        result = verify_package(ws, current, fresh=False)
        if not result["passed"] or not result["ready"]:
            raise ValueError("Portal requires an intact ready package")
        package = ws.get("package", current.id, Package)
        policy = ws.get("policy", package.policy_id, VenuePolicy)
        api = urlsplit(settings.connection.api_url)
        official = urlsplit(policy.values.submission_url or "")
        if _origin(settings.connection.api_url) != _origin(policy.values.submission_url or ""):
            raise ValueError("OJS API must use the reviewed journal submission origin")
        journal = api.path.removesuffix("/api/v1").rstrip("/")
        if not journal or not (official.path == journal or official.path.startswith(journal + "/")):
            raise ValueError("OJS API context must match the reviewed journal submission path")
        root = ws.path(f"submissions/{current.id}/package")
        roles = json.loads((root / "package-readme.json").read_bytes())
        allowed = set(roles["reviewer_files"])
        paths = [item.path for item in settings.uploads]
        if len(paths) != len(set(paths)) or any(path not in allowed or path not in package.files for path in paths):
            raise ValueError("Automatic uploads are limited to unique approved reviewer files; complete administrative material through the journal UI")
        if not set(paths).intersection(roles["accepted_manuscript_files"]):
            raise ValueError("Upload mappings must include an accepted manuscript")
        paper = ws.get("paper", current.paper_id, Paper)
        snapshot = frozen_workspace(ws, paper)
        doc = Document.model_validate_json(snapshot.path("canonical.json").read_bytes())
        text = _abstract(doc, snapshot, anonymized=policy.values.anonymization_required is True)
        metadata = json.loads((root / "metadata.json").read_bytes())
        title = _review_html(doc.title, doc, anonymized=policy.values.anonymization_required is True)
        keywords = metadata["keywords"]
        if policy.values.anonymization_required is True:
            keywords = [_redact(word, doc) for word in keywords]
        locale = settings.draft.locale
        plan = PortalPlan(submission_id=current.id, package_sha256=package.manifest_sha256,
            settings=settings, metadata=OJSPublicationMetadata(title={locale: title}, abstract={locale: text},
                keywords={locale: [OJSKeyword(name=word) for word in keywords]}),
            files={path: package.files[path] for path in paths})
        destination = _root(ws, plan) / "plan.json"
        if destination.exists():
            raise ValueError("Portal plan already exists")
        binding = _remote_binding(ws, plan, settings.remote_submission_id) if settings.remote_submission_id else nullcontext()
        with binding:
            write_json(destination, plan)
            stored = StoredPlan(**plan.model_dump(), artifact_sha256=digest_file(destination))
            try:
                ws.save("portal_plan", stored)
            except BaseException:
                ws.discard_uncommitted_artifact(destination.parent, kind="portal_plan",
                    record_id=stored.id, field="artifact_sha256", expected_value=stored.artifact_sha256)
                raise
        return stored


def _remote_id(plan, history):
    values = [event.values.get("submission_id") for event in history
        if event.kind in {"success", "reconciliation"} and event.operation in {"create", "attach"}]
    return values[-1] if values else plan.settings.remote_submission_id


def _api_context(plan):
    return (_origin(plan.settings.connection.api_url), urlsplit(plan.settings.connection.api_url).path)


@contextmanager
def _remote_binding(ws, plan, remote_id):
    """Serialize one provider draft and refuse another local plan's identity."""
    if type(remote_id) is not int or remote_id <= 0:
        raise ValueError("An actual positive OJS submission ID is required")
    context = _api_context(plan)
    key = hashlib.sha256(json.dumps([context, remote_id]).encode()).hexdigest()
    with ws.lock("portal-remote-" + key):
        for other in _plans(ws):
            if other.id != plan.id and _api_context(other) == context:
                if _remote_id(other, _history(ws, other)) == remote_id:
                    raise ValueError("This OJS draft is already bound to another local portal plan")
        yield


def _pending(history):
    settled = {event.values.get("intent_id") for event in history if event.kind in {"success", "failure"}}
    return [event for event in history if event.kind == "intent" and event.id not in settled]


def _submit_attempts(history):
    failed = {event.values.get("intent_id") for event in history if event.kind == "failure" and event.operation == "submit"}
    return [event for event in history if event.kind == "intent" and event.operation == "submit" and event.id not in failed]


def _write(ws, plan, operation, call, values=None, *, db=None):
    if db is not None:
        raise ValueError("Remote writes must run after the durable intent transaction commits")
    intent = _append(ws, plan, "intent", operation, values or {})
    try:
        receipt = call()
        if values and values.get("sha256") and receipt.upload_sha256 != values["sha256"]:
            raise OJSError("uploaded_bytes_differ_from_approved_package", reconciliation_required=True)
    except OJSError as error:
        if not error.reconciliation_required:
            _append(ws, plan, "failure", operation, {"intent_id": intent.id, "status_code": error.status_code})
        raise
    _append(ws, plan, "success", operation, {"intent_id": intent.id, "receipt": receipt.model_dump(mode="json"),
        "submission_id": receipt.submission_id, "file_id": receipt.file_id})
    return receipt


def connect(ws: Workspace, plan: StoredPlan, client: OJSClient, *, upload: bool) -> dict:
    if upload is not True:
        raise ValueError("Creating or modifying an OJS draft requires explicit upload approval")
    with ws.lock(f"portal-{plan.id}"):
        _connection(plan, client)
        current, _ = _package(ws, plan)
        if current.state not in {SubmissionState.SUBMISSION_READY, SubmissionState.AUTHOR_ATTESTED}:
            raise ValueError("Only an unsubmitted package can modify an OJS draft")
        history = _history(ws, plan)
        if _pending(history):
            raise ValueError("A remote write has an uncertain outcome; reconcile before further writes")
        remote_id = _remote_id(plan, history)
        if remote_id is None:
            receipt = _write(ws, plan, "create", lambda: client.create_draft(plan.settings.draft))
            remote_id = receipt.submission_id
        with _remote_binding(ws, plan, remote_id):
            remote = client.get_submission(remote_id)
            _assert_draft(plan, remote.data)
            publication_id = remote.publication_id
            if not publication_id:
                raise ValueError("OJS draft has no current publication identifier")
            _assert_section(plan, client.get_publication(remote_id, publication_id).data)
            successful = {event.operation for event in _history(ws, plan) if event.kind == "success"}
            if "metadata" not in successful:
                _write(ws, plan, "metadata", lambda: client.update_publication(remote_id, publication_id, plan.metadata))
            for mapping in plan.settings.uploads:
                operation = "upload:" + mapping.path
                if operation not in successful:
                    path = ws.path(f"submissions/{current.id}/package/{mapping.path}")
                    if digest_file(path) != plan.files[mapping.path]:
                        raise ValueError("Upload artifact changed")
                    _write(ws, plan, operation, lambda: client.upload_file(remote_id, path, mapping.genre_id,
                        expected_sha256=plan.files[mapping.path]),
                        {"path": mapping.path, "sha256": plan.files[mapping.path], "genre_id": mapping.genre_id})
            return _inspect(ws, plan, client, remote_id)


def _submitted(data):
    value = data.get("dateSubmitted")
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("OJS submitted date is invalid") from None
    return data.get("submissionProgress") == ""


def _assert_draft(plan, data):
    if _submitted(data) or data.get("submissionProgress") in {None, ""}:
        raise ValueError("OJS record must be an actual unsubmitted draft")
    if data.get("locale") != plan.settings.draft.locale:
        raise ValueError("OJS draft locale differs from the reviewed plan")


def _assert_section(plan, publication_data):
    # OJS 3.5 exposes sectionId on Publication; Submission marks it write-only.
    if publication_data.get("sectionId") != plan.settings.draft.sectionId:
        raise ValueError("OJS publication section differs from the reviewed plan")


def _review_digest(data):
    # Hash all review material; timestamps/links can change on a read without
    # changing the submission. Publication and contributor fields remain bound.
    volatile = {"_href", "urlWorkflow", "urlPublished", "urlAuthorWorkflow", "lastModified", "dateLastActivity"}

    def normalize(value):
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items() if key not in volatile}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    content = normalize(data)
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def inspect(ws: Workspace, plan: StoredPlan, client: OJSClient) -> dict:
    with ws.lock(f"portal-{plan.id}"):
        _connection(plan, client)
        history = _history(ws, plan)
        remote_id = _remote_id(plan, history)
        if not remote_id:
            raise ValueError("Create or explicitly attach an OJS draft before inspection")
        with _remote_binding(ws, plan, remote_id):
            return _inspect(ws, plan, client, remote_id)


def _inspect(ws: Workspace, plan: StoredPlan, client: OJSClient, remote_id: int) -> dict:
    _connection(plan, client)
    _package(ws, plan)
    remote = client.get_submission(remote_id)
    material = _inspection(client, remote_id, remote)
    _assert_section(plan, material["publication"])
    receipt = _append(ws, plan, "inspection", "inspect", {"receipt": remote.model_dump(mode="json"),
        "material": material, "review_sha256": _review_digest(material)})
    return {"plan_id": plan.id, "remote_submission_id": remote_id,
        "review_sha256": receipt.values["review_sha256"], "remote": material,
        "uploads": [mapping.model_dump() for mapping in plan.settings.uploads],
        "notice": "Review the actual contributors, metadata, genre visibility, files and journal-specific checklist before final submit."}


def _connection(plan, client):
    if client.settings != plan.settings.connection:
        raise ValueError("OJS client connection differs from the immutable portal plan")


def _inspection(client, remote_id, remote):
    publication_id = remote.publication_id
    if not publication_id:
        raise ValueError("OJS record has no current publication identifier")
    return {"submission": remote.data,
        "publication": client.get_publication(remote_id, publication_id).data,
        "contributors": client.get_contributors(remote_id, publication_id).data,
        "files": client.get_submission_files(remote_id).data}


def _check_metadata(ws, plan, material, history):
    current = material["publication"]
    _assert_section(plan, current)
    locale = plan.settings.draft.locale
    if current.get("title", {}).get(locale) != plan.metadata.title[locale] or current.get("abstract", {}).get(locale) != plan.metadata.abstract[locale]:
        raise ValueError("OJS title or abstract differs from the approved canonical manuscript")
    keywords = current.get("keywords", {}).get(locale)
    if (not isinstance(keywords, list) or any(not isinstance(item, dict) for item in keywords)
            or sorted(item.get("name", "") for item in keywords) != sorted(item.name for item in plan.metadata.keywords[locale])):
        raise ValueError("OJS keywords differ from the approved package metadata")
    if plan.metadata.primaryContactId is not None and current.get("primaryContactId") != plan.metadata.primaryContactId:
        raise ValueError("OJS primary contact differs from the reviewed plan")
    contributors = material["contributors"].get("items", [])
    if not contributors:
        raise ValueError("Complete the actual OJS contributors before final author review")
    submission, _ = _package(ws, plan)
    author = json.loads(ws.path(f"submissions/{submission.id}/package/author.json").read_bytes())
    if not any(item.get("email", "").casefold() == author["email"].casefold() for item in contributors):
        raise ValueError("The approved author's email must occur in the actual OJS contributor roster")
    files = material["files"].get("items", [])
    for mapping in plan.settings.uploads:
        uploaded = next((event for event in reversed(history) if event.kind == "success" and event.operation == "upload:" + mapping.path), None)
        if not uploaded:
            raise ValueError("Reviewed upload has no successful receipt")
        received = uploaded.values["receipt"]["data"]
        item = next((item for item in files if item.get("id") == received.get("id")), None)
        if (not item or item.get("fileId") != received.get("fileId") or item.get("fileStage") != 2
                or item.get("genreId") != mapping.genre_id or item.get("name", {}).get(locale) != Path(mapping.path).name):
            raise ValueError("OJS file, upload stage or genre differs from the reviewed package upload")


def _record_submission(ws, plan, remote_id, receipt, actor):
    if receipt.data.get("id") != remote_id or not _submitted(receipt.data):
        raise ValueError("OJS has not confirmed an actual submitted date; reconcile without retrying final submit")
    data = receipt.data
    for pending in _pending(_history(ws, plan)):
        if pending.operation == "submit":
            _append(ws, plan, "success", "submit", {"intent_id": pending.id,
                "receipt": receipt.model_dump(mode="json"), "submission_id": remote_id, "reconciled": True})
    url = plan.settings.connection.api_url + f"/submissions/{remote_id}"
    # PKP stores dates in the site's configured timezone; never invent UTC for a
    # naive remote timestamp. Observation time records our confirmed receipt.
    observed = datetime.fromisoformat(data["dateSubmitted"].replace("Z", "+00:00"))
    occurred = observed.isoformat() if observed.tzinfo else receipt.received_at
    current = ws.get("submission", plan.submission_id, Submission)
    history = publication.check(ws, current)
    if not history["passed"]:
        raise ValueError("Publication history is invalid")
    submitted = [event for event in history["events"] if event["kind"] == "receipt" and event["to_state"] == "SUBMITTED"]
    if submitted:
        if submitted[-1]["values"]["external_id"] != str(remote_id):
            raise ValueError("Existing journal submission identity differs from OJS")
        event_id = submitted[-1]["id"]
    else:
        evidence = _append(ws, plan, "reconciliation", "submitted", {"receipt": receipt.model_dump(mode="json"), "submission_id": remote_id})
        evidence_path = _root(ws, plan) / f"{evidence.sequence:04d}-{evidence.id}.json"
        event = publication.record_receipt(ws, current, publication.ReceiptInput(target_state=SubmissionState.SUBMITTED,
            external_id=str(remote_id), external_url=url, occurred_at=occurred, verified_by=actor,
            note="OJS API confirms dateSubmitted; raw response and durable delivery intents are retained."), evidence_path)
        event_id = event.id
    _append(ws, plan, "publication", "record", {"publication_event_id": event_id, "submission_id": remote_id})
    return {"plan_id": plan.id, "remote_submission_id": remote_id, "publication_event_id": event_id, "state": "SUBMITTED"}


def submit(ws: Workspace, plan: StoredPlan, client: OJSClient, values: publication.AttestationInput,
           *, review_sha256: str, approve: bool, final_submit: bool, confirm_copyright: bool = False,
           policy_client: httpx.Client | None = None) -> dict:
    if approve is not True or final_submit is not True:
        raise ValueError("Final OJS submission requires explicit factual approval and final Submit")
    with ws.lock(f"portal-{plan.id}"):
        _connection(plan, client)
        current, package = _package(ws, plan)
        history = _history(ws, plan)
        if _pending(history) or _submit_attempts(history):
            raise ValueError("Final submission was attempted or has an uncertain outcome; reconcile without retrying")
        successful = {event.operation for event in history if event.kind == "success"}
        if "metadata" not in successful or any("upload:" + item.path not in successful for item in plan.settings.uploads):
            raise ValueError("All reviewed metadata and package uploads must complete before final submit")
        remote_id = _remote_id(plan, history)
        with _remote_binding(ws, plan, remote_id):
            remote = client.get_submission(remote_id)
            _assert_draft(plan, remote.data)
            material = _inspection(client, remote_id, remote)
            _check_metadata(ws, plan, material, history)
            if not any(event.kind == "inspection" and event.values["review_sha256"] == review_sha256 for event in history) or _review_digest(material) != review_sha256:
                raise ValueError("Fresh OJS inspection differs from the explicitly reviewed snapshot")
            values = publication.AttestationInput.model_validate(values)
            if current.state == SubmissionState.SUBMISSION_READY:
                publication.attest(ws, current, values, client=policy_client)
            else:
                event = publication.assert_current_attestation(ws, current)
                if event.values["attestation"] != values.model_dump(mode="json"):
                    raise ValueError("Final factual declarations differ from the reserved author attestation")
                original = ws.get("policy", package.policy_id, VenuePolicy)
                live = refresh_policy(ws, original, client=policy_client)
                if validate_policy(ws, live) or policy_fingerprint(live) != policy_fingerprint(original):
                    raise ValueError("Official journal policy changed before final submit")
            # Policy verification can take time. Re-read all actual review material
            # afterwards; OJS offers no atomic conditional final-submit guarantee.
            remote = client.get_submission(remote_id)
            _assert_draft(plan, remote.data)
            material = _inspection(client, remote_id, remote)
            _check_metadata(ws, plan, material, history)
            if _review_digest(material) != review_sha256:
                raise ValueError("OJS review material changed during final policy and author verification")
            with publication._write_transaction(ws) as (db, _):
                attestation = publication.assert_current_attestation(ws, current, db=db)
                intent = _append(ws, plan, "intent", "submit", {"submission_id": remote_id, "attestation_event_id": attestation.id,
                    "review_sha256": review_sha256, "confirm_copyright": confirm_copyright}, db=db)
            try:
                # Even _validateOnly is a provider write. Its response is checked
                # inside final_submit, after both reservation and durable intent.
                receipt = client.final_submit(remote_id, approved=True, confirm_copyright=confirm_copyright)
            except OJSError as error:
                if not error.reconciliation_required:
                    _append(ws, plan, "failure", "submit", {"intent_id": intent.id, "status_code": error.status_code})
                raise
            _append(ws, plan, "success", "submit", {"intent_id": intent.id, "receipt": receipt.model_dump(mode="json"), "submission_id": remote_id})
            # Independently read the provider's actual submitted state after the PUT.
            receipt = client.get_submission(remote_id)
            return _record_submission(ws, plan, remote_id, receipt, values.actor)


def _validate_recovered_event(db, plan, event, history, *, actor):
    """Accept only outcomes that this plan's recorded operation could produce."""
    values, operation = event.values, event.operation
    remote_id = _remote_id(plan, history)
    uploads = {"upload:" + item.path: item for item in plan.settings.uploads}
    if event.kind == "intent":
        if operation not in {"create", "metadata", "submit", *uploads} or _pending(history):
            raise ValueError("Recovered intent is unsupported or overlaps an unsettled write")
        if operation == "create":
            if remote_id is not None or values:
                raise ValueError("Recovered creation intent already has a remote identity")
        elif remote_id is None:
            raise ValueError("Recovered remote write has no bound journal identity")
        if operation in uploads:
            item = uploads[operation]
            if values != {"path": item.path, "sha256": plan.files[item.path], "genre_id": item.genre_id}:
                raise ValueError("Recovered upload intent differs from its approved file mapping")
        if operation == "submit":
            attestation = publication._get(db, "publication_event", values.get("attestation_event_id"), publication.PublicationEvent)
            if (attestation.kind != "attestation" or attestation.submission_id != plan.submission_id
                    or values.get("submission_id") != remote_id or type(values.get("confirm_copyright")) is not bool
                    or _submit_attempts(history)
                    or not any(item.kind == "inspection" and item.values.get("review_sha256") == values.get("review_sha256") for item in history)):
                raise ValueError("Recovered final-submit intent differs from its author and remote review")
        return
    if event.kind in {"success", "failure"}:
        intent = next((item for item in _pending(history) if item.id == values.get("intent_id")), None)
        if intent is None or intent.operation != operation:
            raise ValueError("Recovered outcome has no matching unsettled intent")
        if event.kind == "failure":
            attached = values.get("confirmed_existing_draft_id")
            status = values.get("status_code")
            if attached is not None:
                if operation != "create" or attached != remote_id:
                    raise ValueError("Recovered failed creation differs from its confirmed adopted draft")
            elif status is not None and (type(status) is not int or not 400 <= status < 500):
                raise ValueError("An ambiguous provider failure cannot settle a recovered intent")
            return
        receipt = OJSReceipt.model_validate(values["receipt"])
        if receipt.status_code != 200 or values.get("submission_id") != receipt.submission_id:
            raise ValueError("Recovered successful receipt identity or HTTP status differs")
        if operation == "create":
            if receipt.method != "POST" or receipt.route != "/submissions":
                raise ValueError("Recovered draft creation has an unexpected provider route")
            OJSClient._submission(receipt, draft=True)
            _assert_draft(plan, receipt.data)
        elif receipt.submission_id != remote_id:
            raise ValueError("Recovered successful write changes the bound journal identity")
        elif operation == "metadata":
            if receipt.method != "PUT" or receipt.route != f"/submissions/{remote_id}/publications/{receipt.publication_id}":
                raise ValueError("Recovered metadata receipt has an unexpected provider route")
            OJSClient._publication(receipt, remote_id, receipt.publication_id)
            _assert_section(plan, receipt.data)
        elif operation in uploads:
            item = uploads[operation]
            body = receipt.data
            if (receipt.method != "POST" or receipt.route != f"/submissions/{remote_id}/files"
                    or receipt.upload_sha256 != plan.files[item.path] or not isinstance(body, dict)
                    or body.get("submissionId") != remote_id or body.get("genreId") != item.genre_id
                    or body.get("fileStage") != 2 or type(body.get("fileId")) is not int or body["fileId"] <= 0
                    or receipt.file_id != body.get("id") or values.get("file_id") != receipt.file_id):
                raise ValueError("Recovered upload receipt differs from its approved bytes, stage or genre")
        elif operation == "submit":
            reconciled = values.get("reconciled") is True
            route = f"/submissions/{remote_id}" + ("" if reconciled else "/submit")
            if receipt.method != ("GET" if reconciled else "PUT") or receipt.route != route:
                raise ValueError("Recovered final-submit receipt has an unexpected provider route")
            OJSClient._submission(receipt, remote_id, submitted=True)
            if not _submitted(receipt.data):
                raise ValueError("Recovered final-submit receipt does not confirm submission")
        return
    if event.kind in {"inspection", "reconciliation"}:
        receipt = OJSReceipt.model_validate(values["receipt"])
        expected_id = values.get("submission_id") if event.kind == "reconciliation" else remote_id
        if (receipt.method != "GET" or receipt.status_code != 200 or receipt.submission_id != expected_id
                or receipt.route != f"/submissions/{expected_id}" or (remote_id is not None and expected_id != remote_id)):
            raise ValueError("Recovered journal observation changes its identity or provider route")
        OJSClient._submission(receipt, expected_id)
        if event.kind == "inspection":
            if operation != "inspect" or _review_digest(values["material"]) != values.get("review_sha256"):
                raise ValueError("Recovered inspection differs from its reviewed material")
            if (values["material"]["submission"] != receipt.data
                    or values["material"]["publication"].get("submissionId") != remote_id
                    or values["material"]["publication"].get("id") != receipt.publication_id):
                raise ValueError("Recovered inspection material changes its journal identity")
            _assert_section(plan, values["material"]["publication"])
        elif operation == "attach":
            if remote_id is not None or values.get("actor") != actor:
                raise ValueError("Recovered adoption cannot replace a bound draft")
            _assert_draft(plan, receipt.data)
        elif operation == "submitted":
            if not _submit_attempts(history) or not _submitted(receipt.data):
                raise ValueError("Recovered submission observation has no final attempt or actual confirmation")
        else:
            raise ValueError("Unsupported recovered journal observation")
        return
    if event.kind == "publication" and operation == "record":
        recorded = publication._get(db, "publication_event", values.get("publication_event_id"), publication.PublicationEvent)
        if (recorded.submission_id != plan.submission_id or recorded.kind != "receipt"
                or recorded.to_state != SubmissionState.SUBMITTED or values.get("submission_id") != remote_id
                or recorded.values.get("external_id") != str(remote_id)):
            raise ValueError("Recovered publication link differs from its actual submission receipt")
        return
    raise ValueError("Unsupported recovered portal event")


def recover_local_events(ws: Workspace, plan: StoredPlan, *, actor: str, confirmed: bool = False) -> list[PortalEvent]:
    """Import verified preserved local evidence; never issue a provider request."""
    with ws.lock(f"portal-{plan.id}"):
        return _recover_local_events(ws, plan, actor=actor, confirmed=confirmed)


def _recover_local_events(ws, plan, *, actor, confirmed):
    if confirmed is not True:
        raise ValueError("Importing preserved local portal evidence requires explicit author confirmation")
    current, _ = _package(ws, plan)
    paper = ws.get("paper", current.paper_id, Paper)
    if actor != paper.approved_by:
        raise ValueError("Local portal recovery must be by the approved author")
    root = _root(ws, plan)
    try:
        with publication._write_transaction(ws) as (db, _):
            publication._audit(ws, db)
            history = _history(ws, plan, db=db, allow_unindexed=True)
            expected = {"plan.json", *[f"{item.sequence:04d}-{item.id}.json" for item in history]}
            preserved = sorted((path for path in root.iterdir() if path.name not in expected), key=lambda path: path.name)
            recovered = []
            for path in preserved:
                path = ws.path(path.relative_to(ws.root).as_posix())
                if not path.is_file() or not 0 < path.stat().st_size <= MAX_SOURCE_BYTES:
                    raise ValueError(f"Unsupported preserved portal artifact: {path}")
                raw = path.read_bytes()
                data = PortalEventData.model_validate_json(raw)
                canonical = (json.dumps(data.model_dump(mode="json"), indent=2, ensure_ascii=False, allow_nan=False) + "\n").replace("\n", os.linesep).encode("utf-8")
                if (raw != canonical or data.plan_id != plan.id or data.sequence != len(history) + 1
                        or data.previous_sha256 != (history[-1].artifact_sha256 if history else None)
                        or path.name != f"{data.sequence:04d}-{data.id}.json"):
                    raise ValueError(f"Preserved portal event is not the exact next canonical event: {path}")
                event = PortalEvent(**data.model_dump(), artifact_sha256=digest_file(path))
                _validate_recovered_event(db, plan, event, history, actor=actor)
                db.execute("INSERT INTO records VALUES (?,?,?)", ("portal_event", event.id, event.model_dump_json()))
                history.append(event)
                recovered.append(event)
        return recovered
    except (ValueError, OSError, TypeError, KeyError) as error:
        raise ValueError(f"Preserved portal evidence at {root} requires author review: {error}") from error


def reconcile(ws: Workspace, plan: StoredPlan, client: OJSClient, *, actor: str,
              remote_submission_id: int | None = None, confirm: bool = False, recover_local: bool = False) -> dict:
    """Read remote facts; never repeat a mutating request."""
    with ws.lock(f"portal-{plan.id}"):
        _connection(plan, client)
        if recover_local:
            _recover_local_events(ws, plan, actor=actor, confirmed=confirm)
        current, _ = _package(ws, plan)
        paper = ws.get("paper", current.paper_id, Paper)
        if actor != paper.approved_by:
            raise ValueError("Reconciliation must be by the approved author")
        history = _history(ws, plan)
        known = _remote_id(plan, history)
        if known and remote_submission_id and known != remote_submission_id:
            raise ValueError("Reconciliation cannot change the bound remote submission identity")
        remote_id = known or remote_submission_id
        if not remote_id or (known is None and confirm is not True):
            raise ValueError("Unknown draft creation requires an explicitly confirmed remote submission ID")
        with _remote_binding(ws, plan, remote_id):
            remote = client.get_submission(remote_id)
            if _submitted(remote.data):
                if not any(event.kind == "intent" and event.operation == "submit" for event in history):
                    raise ValueError("Submitted remote record was not bound to this plan's final-submit attempt; import its actual receipt separately")
                return _record_submission(ws, plan, remote_id, remote, actor)
            _assert_draft(plan, remote.data)
            _assert_section(plan, client.get_publication(remote_id, remote.publication_id).data)
            if known is None:
                _append(ws, plan, "reconciliation", "attach", {"submission_id": remote_id, "receipt": remote.model_dump(mode="json"), "actor": actor})
            adopted = any(event.kind == "reconciliation" and event.operation == "attach"
                and event.values.get("submission_id") == remote_id for event in _history(ws, plan))
            if adopted:
                # A recovered attach receipt may have committed before the
                # interrupted caller could settle its uncertain creation intent.
                for pending in _pending(history):
                    if pending.operation == "create":
                        _append(ws, plan, "failure", "create", {"intent_id": pending.id, "confirmed_existing_draft_id": remote_id})
            return {"plan_id": plan.id, "remote_submission_id": remote_id, "state": "DRAFT",
                "notice": "Remote draft observed. Uncertain uploads or final Submit remain blocked; inspect the journal before taking further action."}


def assert_cancellable(ws: Workspace, submission: Submission, *, db=None) -> None:
    plans = _plans(ws, db=db)
    for plan in plans:
        if plan.submission_id == submission.id:
            history = _history(ws, plan, db=db)
            if _submit_attempts(history):
                raise ValueError("An OJS final-submit attempt requires actual journal outcome evidence; its reservation cannot be cancelled")


def check(ws: Workspace, plan: StoredPlan) -> dict:
    try:
        _package(ws, plan)
        history = _history(ws, plan)
        return {"plan_id": plan.id, "passed": True, "errors": [], "remote_submission_id": _remote_id(plan, history),
            "uncertain_operations": [event.operation for event in _pending(history)],
            "final_submit_attempted": any(event.kind == "intent" and event.operation == "submit" for event in history),
            "submission_confirmed": any(event.kind == "publication" for event in history), "events": len(history)}
    except (ValueError, OSError, TypeError, KeyError) as error:
        return {"plan_id": plan.id, "passed": False, "errors": [str(error)]}


def client_from_environment(plan: StoredPlan) -> OJSClient:
    token = os.environ.get(plan.settings.connection.token_env, "")
    if not token:
        raise ValueError(f"Set {plan.settings.connection.token_env} to the actual OJS API token; secrets are never saved in the plan")
    return OJSClient(plan.settings.connection, token)

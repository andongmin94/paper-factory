"""Same-journal revision packages and separately attested resubmission receipts.

The original submission occupies the Study's slot throughout revision. Its
scientific approval and initial package remain immutable; revised derivatives
and reviewer responses are bound by a separate delivery manifest.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Literal

import httpx
from pydantic import Field

from . import publication, submission_package, venue_compiler
from .integrity import frozen_workspace
from .manuscript import Document
from .models import Paper, Record, Submission, SubmissionState, now, uid
from .publication import AttestationInput, ReceiptInput
from .submission_package import Package
from .venue_policy import VenuePolicy, refresh_policy, validate_policy
from .venues import Venue
from .workspace import Workspace, digest_file, ensure_unlinked, write_json


class DeliveryData(Record):
    id: str = Field(default_factory=lambda: uid("revision-delivery"))
    revision_id: str
    original_submission_id: str
    original_paper_id: str
    base_paper_id: str
    base_freeze_digest: str
    study_id: str
    decision_event_id: str
    external_id: str
    candidate_id: str
    revised_paper_id: str
    revised_freeze_digest: str
    response_id: str
    response_sha256: str
    package_sha256: str
    archive_sha256: str
    files: dict[str, str]
    created_at: str = Field(default_factory=now)


class RevisionDelivery(DeliveryData):
    manifest_sha256: str
    state: Literal["PREPARED", "AUTHOR_ATTESTED", "RESUBMITTED"] = "PREPARED"
    attestation_sha256: str | None = None
    publication_event_id: str | None = None


class AttestationData(Record):
    id: str
    delivery_id: str
    manifest_sha256: str
    values: AttestationInput
    policy_id: str
    policy_fingerprint: str
    preprint_records: dict[str, str]
    attested_at: str = Field(default_factory=now)


class RevisionAttestation(AttestationData):
    artifact_sha256: str


def _root(ws: Workspace, delivery: RevisionDelivery | DeliveryData) -> Path:
    return ws.path(f"revision-deliveries/{delivery.id}")


def _records(ws: Workspace, db: sqlite3.Connection | None = None) -> list[RevisionDelivery]:
    records = publication._rows(db, "revision_delivery", RevisionDelivery) if db is not None else ws.list("revision_delivery", RevisionDelivery)
    root = ws.path("revision-deliveries")
    artifacts = set()
    if root.exists():
        for child in root.iterdir():
            child = ws.path(f"revision-deliveries/{child.name}")
            if child.name.startswith(".preparing-"):
                continue
            if not child.is_dir():
                raise ValueError("Revision delivery registry contains an unexpected artifact")
            artifacts.add(child.name)
    if artifacts != {item.id for item in records}:
        raise ValueError("Revision delivery registry and artifacts differ")
    return records


def assert_regular_candidate(ws: Workspace, candidate: Submission, *, db: sqlite3.Connection | None = None) -> None:
    """A revised package cannot acquire a second independent publication slot."""
    for delivery in _records(ws, db):
        if delivery.candidate_id == candidate.id:
            raise ValueError("This candidate is a same-journal revision delivery; use revision delivery attestation")


def _review_records(ws: Workspace, delivery: RevisionDelivery):
    from .revisions import Revision, ResponseBuild, verify_response
    revision = ws.get("revision", delivery.revision_id, Revision)
    response = ws.get("revision_response", delivery.response_id, ResponseBuild)
    result = verify_response(ws, response, require_approved=True, require_active=False)
    if not result.get("ready") or not result.get("passed", result.get("valid", False)):
        raise ValueError("Revision response is incomplete or changed: " + "; ".join(result.get("errors", [])))
    if (revision.base_submission_id != delivery.original_submission_id
            or revision.base_paper_id != delivery.base_paper_id
            or revision.base_freeze_digest != delivery.base_freeze_digest
            or revision.study_id != delivery.study_id
            or revision.decision_event_id != delivery.decision_event_id
            or revision.revised_paper_id != delivery.revised_paper_id
            or response.revision_id != revision.id
            or response.revised_paper_id != delivery.revised_paper_id
            or response.artifact_sha256 != delivery.response_sha256):
        raise ValueError("Revision delivery response/scientific lineage binding differs")
    return revision, response


def _readme(delivery: DeliveryData, response, anonymized: bool) -> dict:
    reviewer = ([f"reviewer-response/letter.{suffix}" for suffix in ("md", "pdf", "docx")]
        if anonymized else [f"response/{name}" for name in ("letter.md", "letter.pdf", "letter.docx") if name in response.files])
    return {"revision_id": delivery.revision_id, "original_submission_id": delivery.original_submission_id,
        "candidate_id": delivery.candidate_id, "anonymized": anonymized,
        "reviewer_response_files": reviewer,
        "administrative_response_files": [f"response/{name}" for name in response.files if f"response/{name}" not in reviewer],
        "manuscript_archive": "submission.zip", "revision_portal_requirements_verified": False,
        "notice": "Upload only the journal's requested documents after checking its revision instructions. The original response plan, bindings and manuscript diff are administrative audit files. The manuscript archive also contains administrative author metadata; do not upload the entire archive as a blinded review document."}


def _validate(ws: Workspace, delivery: RevisionDelivery) -> tuple[Submission, Submission, Paper, Package]:
    root = _root(ws, delivery)
    manifest = root / "manifest.json"
    expected_manifest = delivery.model_dump(mode="json", include=set(DeliveryData.model_fields))
    if digest_file(manifest) != delivery.manifest_sha256 or json.loads(manifest.read_bytes()) != expected_manifest:
        raise ValueError("Revision delivery manifest changed or differs from its record")
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()} - {"manifest.json", "attestation.json"}
    if actual != set(delivery.files):
        raise ValueError("Revision delivery file set changed")
    for name, digest in delivery.files.items():
        if digest_file(ws.path(f"revision-deliveries/{delivery.id}/{name}")) != digest:
            raise ValueError(f"Revision delivery artifact changed: {name}")
    original = ws.get("submission", delivery.original_submission_id, Submission)
    candidate = ws.get("submission", delivery.candidate_id, Submission)
    base = ws.get("paper", original.paper_id, Paper)
    child = ws.get("paper", candidate.paper_id, Paper)
    if (original.paper_id != delivery.original_paper_id or base.study_id != delivery.study_id
            or child.id != delivery.revised_paper_id or child.study_id != base.study_id
            or original.venue_id != candidate.venue_id or candidate.state != SubmissionState.SUBMISSION_READY
            or child.freeze_digest != delivery.revised_freeze_digest
            or child.approved_by != base.approved_by):
        raise ValueError("Revision delivery must preserve the same Study, journal and approved named author")
    package = publication._package(ws, candidate)
    if package.manifest_sha256 != delivery.package_sha256 or package.archive_sha256 != delivery.archive_sha256 or delivery.files.get("submission.zip") != package.archive_sha256:
        raise ValueError("Revision delivery package differs from its approved derivative")
    revision, response = _review_records(ws, delivery)
    policy = ws.get("policy", package.policy_id, VenuePolicy)
    anonymized = policy.values.anonymization_required is True
    expected = {"submission.zip": package.archive_sha256,
        **{f"response/{name}": digest for name, digest in response.files.items()},
        "delivery-readme.json": delivery.files.get("delivery-readme.json")}
    if anonymized:
        expected.update({f"reviewer-response/letter.{suffix}": delivery.files.get(f"reviewer-response/letter.{suffix}")
            for suffix in ("md", "pdf", "docx")})
        doc = Document.model_validate_json(frozen_workspace(ws, child).path("canonical.json").read_bytes())
        letter = venue_compiler._redact((root / "response" / "letter.md").read_text(encoding="utf-8"), doc)
        if (root / "reviewer-response" / "letter.md").read_text(encoding="utf-8") != letter:
            raise ValueError("Blinded reviewer response differs from the verified author response")
        errors = venue_compiler._review_identification_errors(root / "reviewer-response", doc, stem="letter")
        if errors:
            raise ValueError("; ".join(errors))
    if delivery.files != expected or any(value is None for value in expected.values()):
        raise ValueError("Revision delivery omits or changes the verified reviewer response files")
    if json.loads((root / "delivery-readme.json").read_bytes()) != _readme(delivery, response, anonymized):
        raise ValueError("Revision delivery administrative/reviewer file roles changed")
    decision = ws.get("publication_event", revision.decision_event_id, publication.PublicationEvent)
    if decision.submission_id != original.id or decision.to_state != SubmissionState.REVISION or decision.values.get("external_id") != delivery.external_id:
        raise ValueError("Revision delivery differs from the journal's manuscript ID or revision decision")
    return original, candidate, child, package


def _current(ws: Workspace, delivery: RevisionDelivery, db: sqlite3.Connection) -> tuple[Submission, list[publication.PublicationEvent], dict[str, Submission]]:
    submissions, histories = publication._audit(ws, db)
    current = submissions.get(delivery.original_submission_id)
    history = histories.get(delivery.original_submission_id, [])
    if (current is None or current.state != SubmissionState.REVISION or not history
            or history[-1].id != delivery.decision_event_id):
        raise ValueError("Revision delivery requires the current journal revision decision and its occupied submission slot")
    return current, history, submissions


def prepare(ws: Workspace, revision, settings_path: Path, *, response=None,
            policy: VenuePolicy | None = None, pandoc: str | None = None,
            client: httpx.Client | None = None) -> tuple[RevisionDelivery, Path]:
    """Build a reviewed, approved child package without releasing the original slot."""
    from .revisions import ResponseBuild, verify_response
    if response is None:
        responses = [item for item in ws.list("revision_response", ResponseBuild) if item.revision_id == revision.id]
        if not responses:
            raise ValueError("Prepare a complete reviewer response before preparing revision delivery")
        response = responses[-1]
    report = verify_response(ws, response, require_approved=True, require_active=True)
    if not report.get("ready") or not report.get("passed", report.get("valid", False)):
        raise ValueError("Revision delivery requires a complete reviewed response and approved child manuscript: " + "; ".join(report.get("errors", [])))
    original = ws.get("submission", revision.base_submission_id, Submission)
    if original.state != SubmissionState.REVISION:
        raise ValueError("Revision delivery requires a current journal revision decision")
    child = ws.get("paper", revision.revised_paper_id, Paper)
    base = ws.get("paper", original.paper_id, Paper)
    if child.study_id != base.study_id or child.approved_by != base.approved_by:
        raise ValueError("Revised manuscript must retain the same Study and approved named author")
    selected_policy_id = (policy.id if policy is not None
        else publication._effective_submission(ws, original).policy_id)
    policy = ws.get("policy", selected_policy_id, VenuePolicy)
    if policy.venue_id != original.venue_id:
        raise ValueError("Revised policy must belong to the original journal")
    venue = ws.get("venue", original.venue_id, Venue)
    candidate = venue_compiler.select(ws, child, venue, policy)
    candidate, _ = venue_compiler.compile_submission(ws, candidate, settings_path, pandoc=pandoc, client=client)
    package, package_root = submission_package.build(ws, candidate, client=client)
    if not package.ready:
        raise ValueError("Revised submission package is blocked: " + "; ".join(package.errors))
    decision = ws.get("publication_event", revision.decision_event_id, publication.PublicationEvent)
    data = DeliveryData(revision_id=revision.id, original_submission_id=original.id,
        original_paper_id=base.id, base_paper_id=revision.base_paper_id,
        base_freeze_digest=revision.base_freeze_digest,
        study_id=base.study_id, decision_event_id=decision.id,
        external_id=decision.values["external_id"], candidate_id=candidate.id,
        revised_paper_id=child.id, revised_freeze_digest=child.freeze_digest,
        response_id=response.id, response_sha256=response.artifact_sha256,
        package_sha256=package.manifest_sha256, archive_sha256=package.archive_sha256, files={})
    parent = ws.path("revision-deliveries")
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".preparing-", dir=parent))
    destination = _root(ws, data)
    published = False
    try:
        shutil.copyfile(package_root / "submission.zip", stage / "submission.zip")
        for name in response.files:
            target = ws.path(f"{stage.relative_to(ws.root).as_posix()}/response/{name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ws.path(f"revisions/{revision.id}/responses/{response.id}/{name}"), target)
        copied = {path.relative_to(stage).as_posix(): digest_file(path) for path in stage.rglob("*") if path.is_file()}
        if copied != {"submission.zip": package.archive_sha256, **{f"response/{name}": digest for name, digest in response.files.items()}}:
            raise ValueError("Revised package or response changed during delivery preparation")
        current_policy = ws.get("policy", package.policy_id, VenuePolicy)
        anonymized = current_policy.values.anonymization_required is True
        if anonymized:
            doc = Document.model_validate_json(frozen_workspace(ws, child).path("canonical.json").read_bytes())
            reviewer_root = stage / "reviewer-response"
            reviewer_root.mkdir()
            letter = venue_compiler._redact((stage / "response" / "letter.md").read_text(encoding="utf-8"), doc)
            (reviewer_root / "letter.md").write_text(letter, encoding="utf-8", newline="")
            for suffix in ("pdf", "docx"):
                venue_compiler.convert(reviewer_root / "letter.md", reviewer_root / f"letter.{suffix}", pandoc=pandoc)
            errors = venue_compiler._review_identification_errors(reviewer_root, doc, stem="letter")
            if errors:
                raise ValueError("; ".join(errors))
            # Pandoc/Typst intermediates are unnecessary in the reviewer file
            # set; the pinned administrative response retains its own sources.
            for name in ("letter.typ", "letter-pandoc-metadata.json"):
                ws.path(f"{stage.relative_to(ws.root).as_posix()}/reviewer-response/{name}").unlink(missing_ok=True)
        write_json(stage / "delivery-readme.json", _readme(data, response, anonymized))
        data.files = {path.relative_to(stage).as_posix(): digest_file(path) for path in stage.rglob("*") if path.is_file()}
        write_json(stage / "manifest.json", data)
        delivery = RevisionDelivery(**data.model_dump(), manifest_sha256=digest_file(stage / "manifest.json"))
        with ws._database() as db:
            db.execute("BEGIN IMMEDIATE")
            _records(ws, db)
            _current(ws, delivery, db)
            ws.rename_artifact(stage, destination)
            published = True
            _validate(ws, delivery)
            db.execute("INSERT INTO records VALUES (?,?,?)", ("revision_delivery", delivery.id, delivery.model_dump_json()))
        return delivery, destination
    except BaseException:
        if published:
            with ws._database() as db:
                persisted = db.execute("SELECT 1 FROM records WHERE kind='revision_delivery' AND id=?", (data.id,)).fetchone()
            if persisted is None:
                shutil.rmtree(ws.path(f"revision-deliveries/{data.id}"))
        raise
    finally:
        if stage.exists():
            shutil.rmtree(ws.path(stage.relative_to(ws.root).as_posix()))


def _attestation(ws: Workspace, delivery: RevisionDelivery, *, validated=None) -> RevisionAttestation:
    record = ws.get("revision_attestation", delivery.id, RevisionAttestation)
    path = _root(ws, delivery) / "attestation.json"
    if (digest_file(path) != record.artifact_sha256 or delivery.attestation_sha256 != record.artifact_sha256
            or json.loads(path.read_bytes()) != record.model_dump(mode="json", exclude={"artifact_sha256"})
            or record.id != delivery.id or record.delivery_id != delivery.id
            or record.manifest_sha256 != delivery.manifest_sha256):
        raise ValueError("Final revised author attestation changed or differs from delivery")
    _, candidate, child, package = validated if validated is not None else _validate(ws, delivery)
    if record.values.actor != child.approved_by:
        raise ValueError("Revised final attestation must be by the approved named author")
    policy = ws.get("policy", record.policy_id, VenuePolicy)
    if (validate_policy(ws, policy, fresh=False) or policy.venue_id != candidate.venue_id
            or record.policy_fingerprint != venue_compiler.policy_fingerprint(policy)
            or record.policy_fingerprint != venue_compiler.policy_fingerprint(ws.get("policy", package.policy_id, VenuePolicy))
            or record.preprint_records != publication._review_preprints(ws, child, record.values, policy, live_boundary=False)):
        raise ValueError("Revised final attestation current-policy or existing-preprint binding differs")
    timestamp = datetime.fromisoformat(record.attested_at)
    if timestamp.tzinfo is None or timestamp > datetime.now(timezone.utc) + timedelta(minutes=1) or timestamp < datetime.fromisoformat(delivery.created_at):
        raise ValueError("Revised attestation chronology is invalid")
    for source in policy.sources:
        fetched = datetime.fromisoformat(source.fetched_at)
        if fetched > timestamp or timestamp - fetched > timedelta(minutes=5):
            raise ValueError("Revised attestation lacks a submission-time official policy capture")
    return record


def attest(ws: Workspace, delivery: RevisionDelivery, values: AttestationInput,
           *, client: httpx.Client | None = None) -> RevisionAttestation:
    values = AttestationInput.model_validate(values)
    delivery = ws.get("revision_delivery", delivery.id, RevisionDelivery)
    if delivery.state != "PREPARED":
        raise ValueError("Only an unused prepared revision delivery can be attested")
    _, candidate, child, package = _validate(ws, delivery)
    if values.actor != child.approved_by:
        raise ValueError("Final revised attestation must be by the approved named author")
    packaged = ws.get("policy", package.policy_id, VenuePolicy)
    live = refresh_policy(ws, packaged, client=client)
    errors = validate_policy(ws, live)
    if errors or venue_compiler.policy_fingerprint(live) != venue_compiler.policy_fingerprint(packaged):
        raise ValueError("Revised submission-time official policy changed or requires review: " + "; ".join(errors))
    data = AttestationData(id=delivery.id, delivery_id=delivery.id, manifest_sha256=delivery.manifest_sha256,
        values=values, policy_id=live.id, policy_fingerprint=venue_compiler.policy_fingerprint(live),
        preprint_records=publication._review_preprints(ws, child, values, live, live_boundary=True))
    path = _root(ws, delivery) / "attestation.json"
    written = False
    try:
        with ws._database() as db:
            db.execute("BEGIN IMMEDIATE")
            _records(ws, db)
            current = publication._get(db, "revision_delivery", delivery.id, RevisionDelivery)
            if current.state != "PREPARED" or path.exists():
                raise ValueError("Only an unused prepared revision delivery can be attested")
            _, _, submissions = _current(ws, current, db)
            _validate(ws, current)
            publication._overlap_guard(ws, db, child, submissions,
                exclude_submission_id=current.original_submission_id)
            if data.preprint_records != publication._review_preprints(ws, child, values, live, live_boundary=True, db=db):
                raise ValueError("Existing preprint posting facts changed during revised attestation")
            write_json(path, data)
            written = True
            record = RevisionAttestation(**data.model_dump(), artifact_sha256=digest_file(path))
            current.state = "AUTHOR_ATTESTED"
            current.attestation_sha256 = record.artifact_sha256
            db.execute("INSERT INTO records VALUES (?,?,?)", ("revision_attestation", record.id, record.model_dump_json()))
            db.execute("UPDATE records SET data=? WHERE kind='revision_delivery' AND id=?", (current.model_dump_json(), current.id))
        return record
    except BaseException:
        if written:
            with ws._database() as db:
                persisted = db.execute("SELECT 1 FROM records WHERE kind='revision_attestation' AND id=?", (delivery.id,)).fetchone()
            if persisted is None:
                ws.path(f"revision-deliveries/{delivery.id}/attestation.json").unlink()
        raise


def validate_publication_event(ws: Workspace, submission: Submission, paper: Paper,
        event: publication.PublicationEvent, external_id: str | None,
        attested_at: str | None) -> tuple[str | None, str | None]:
    """Validate a historical revised receipt without recursively auditing journal state."""
    payload = event.values
    delivery = ws.get("revision_delivery", payload["delivery_id"], RevisionDelivery)
    validated = _validate(ws, delivery)
    original, candidate, child, _ = validated
    attestation = _attestation(ws, delivery, validated=validated)
    receipt = ReceiptInput.model_validate(payload["receipt"])
    decision = ws.get("publication_event", delivery.decision_event_id, publication.PublicationEvent)
    expected = {"delivery_id": delivery.id, "manifest_sha256": delivery.manifest_sha256,
        "attestation_sha256": attestation.artifact_sha256, "receipt": receipt.model_dump(mode="json")}
    with ws._database() as db:
        persisted = db.execute("SELECT 1 FROM records WHERE kind='publication_event' AND id=?", (event.id,)).fetchone()
    if persisted:
        if delivery.state != "RESUBMITTED" or delivery.publication_event_id != event.id:
            raise ValueError("Recorded revised receipt differs from its authoritative delivery state")
    elif delivery.state != "AUTHOR_ATTESTED" or delivery.publication_event_id is not None:
        raise ValueError("New revised receipt requires an unused revised author attestation")
    if (payload != expected or original.id != submission.id or paper.id != delivery.original_paper_id
            or event.from_state != SubmissionState.REVISION or event.to_state != SubmissionState.UNDER_REVIEW
            or event.previous_sha256 != decision.artifact_sha256
            or receipt.target_state != SubmissionState.UNDER_REVIEW or not event.evidence_sha256
            or receipt.external_id != delivery.external_id or receipt.external_id != external_id
            or receipt.verified_by != child.approved_by or event.actor != child.approved_by
            or delivery.state not in {"AUTHOR_ATTESTED", "RESUBMITTED"}
            or (delivery.state == "RESUBMITTED" and delivery.publication_event_id != event.id)):
        raise ValueError("Same-journal revision receipt/author/manuscript/package binding differs")
    publication._receipt_origin(ws, candidate, receipt)
    occurred = datetime.fromisoformat(receipt.occurred_at)
    if occurred < datetime.fromisoformat(attestation.attested_at) or occurred > datetime.fromisoformat(event.recorded_at) + timedelta(minutes=1):
        raise ValueError("Revision receipt occurrence must follow revised author attestation and precede its import")
    return receipt.external_id, attested_at


def record(ws: Workspace, delivery: RevisionDelivery, values: ReceiptInput,
           evidence_path: Path) -> publication.PublicationEvent:
    """Import a real resubmission confirmation for the original journal manuscript."""
    values = ReceiptInput.model_validate(values)
    if values.target_state != SubmissionState.UNDER_REVIEW:
        raise ValueError("A revised submission confirmation must report UNDER_REVIEW")
    ensure_unlinked(evidence_path.expanduser())
    source = evidence_path.expanduser().resolve()
    if not source.is_file():
        raise ValueError("Revision confirmation evidence must be an existing file")
    with source.open("rb") as stream:
        evidence = stream.read(publication.MAX_RECEIPT_BYTES + 1)
    if not evidence or len(evidence) > publication.MAX_RECEIPT_BYTES:
        raise ValueError("Revision confirmation evidence must be nonempty and at most 20 MiB")
    with publication._write_transaction(ws) as (db, published):
        _records(ws, db)
        current = publication._get(db, "revision_delivery", delivery.id, RevisionDelivery)
        if current.state != "AUTHOR_ATTESTED":
            raise ValueError("Revision confirmation requires a separate final revised author attestation")
        original, history, submissions = _current(ws, current, db)
        validated = _validate(ws, current)
        _, _, child, _ = validated
        attestation = _attestation(ws, current, validated=validated)
        publication._overlap_guard(ws, db, child, submissions,
            exclude_submission_id=current.original_submission_id)
        policy = ws.get("policy", attestation.policy_id, VenuePolicy)
        if publication._review_preprints(ws, child, attestation.values, policy, live_boundary=True, db=db) != attestation.preprint_records:
            raise ValueError("Existing preprint posting facts changed after revised author attestation")
        paper = publication._get(db, "paper", original.paper_id, Paper)
        payload = {"delivery_id": current.id, "manifest_sha256": current.manifest_sha256,
            "attestation_sha256": attestation.artifact_sha256, "receipt": values.model_dump(mode="json")}
        event = publication._append(ws, db, original, paper, history, kind="revision_submission",
            target=SubmissionState.UNDER_REVIEW, actor=values.verified_by, values=payload, evidence=evidence)
        published.append(event)
        current.state = "RESUBMITTED"
        current.publication_event_id = event.id
        db.execute("UPDATE records SET data=? WHERE kind='revision_delivery' AND id=?", (current.model_dump_json(), current.id))
    return event


def check(ws: Workspace, delivery: RevisionDelivery) -> dict:
    try:
        records = _records(ws)
        current = next((item for item in records if item.id == delivery.id), None)
        if current is None:
            raise ValueError("Unknown revision delivery")
        validated = _validate(ws, current)
        original, _, _, _ = validated
        if current.state != "PREPARED":
            _attestation(ws, current, validated=validated)
        elif current.attestation_sha256 or current.publication_event_id or (_root(ws, current) / "attestation.json").exists():
            raise ValueError("Unused revision delivery contains unexpected attestation or receipt")
        report = publication.check(ws, original)
        if not report["passed"]:
            raise ValueError("Original journal publication history is damaged: " + "; ".join(report["errors"]))
        if current.state == "RESUBMITTED":
            events = [event for event in report["events"] if event["kind"] == "revision_submission" and event["values"].get("delivery_id") == current.id]
            if len(events) != 1 or events[0]["id"] != current.publication_event_id:
                raise ValueError("Revision delivery differs from its recorded resubmission confirmation")
        else:
            if current.publication_event_id:
                raise ValueError("Unconfirmed revision delivery has a resubmission event")
        current_round_active = (original.state == SubmissionState.REVISION and bool(report["events"])
            and report["events"][-1]["id"] == current.decision_event_id)
        return {"delivery_id": current.id, "passed": True, "errors": [], "state": current.state,
            "original_submission_id": original.id, "original_submission_state": original.state,
            "candidate_id": current.candidate_id, "resubmission_recorded": current.state == "RESUBMITTED",
            "current_round_active": current_round_active,
            "attestation_allowed": current_round_active and current.state == "PREPARED",
            "confirmation_allowed": current_round_active and current.state == "AUTHOR_ATTESTED",
            "local_review_bundle_ready": True, "revision_portal_requirements_verified": False,
            "warnings": ["Review this response and manuscript against the journal's current revision instructions before any upload. Local compilation does not verify marked manuscript or portal upload requirements."],
            "automatic_external_submission_performed": False, "directory": str(_root(ws, current))}
    except (ValueError, OSError, KeyError, TypeError) as error:
        return {"delivery_id": delivery.id, "passed": False, "errors": [str(error)], "automatic_external_submission_performed": False}

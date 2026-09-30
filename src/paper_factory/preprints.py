"""Separate, author-approved preprint preparation and imported posting facts.

These operations never upload files or touch the peer-review submission state.
An imported receipt records the author's observation, not API verification or
permission to post. Permission preparation always re-fetches publisher policy.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
from typing import Literal
import zipfile

import httpx
from pydantic import Field, field_validator

from .conversion import convert, verify_receipts
from .integrity import frozen_workspace
from .manuscript import Document, claim_text, escape_md, render
from .models import Claim, Paper, Record, now, uid
from .venue_compiler import policy_fingerprint
from .venue_policy import PolicyEvidence, VenuePolicy, _origin, normalize_text, refresh_policy, validate_policy
from .workspace import Workspace, digest_file, ensure_unlinked, write_json


class PreprintSettings(Record):
    paper_id: str
    policy_id: str
    server: str
    server_url: str
    license: str
    reviewed_by: str
    decision: Literal["allowed", "forbidden", "unknown"] = "unknown"
    evidence: PolicyEvidence
    author_approval: bool = Field(default=False, strict=True)
    authorized_to_post: bool = Field(default=False, strict=True)
    policy_interpretation_confirmed: bool = Field(default=False, strict=True)

    @field_validator("server", "license", "reviewed_by")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Preprint settings require actual nonempty author statements")
        return value.strip()

    @field_validator("server_url")
    @classmethod
    def public_server(cls, value: str) -> str:
        _origin(value)
        return value


class PostingReceipt(Record):
    paper_id: str
    remote_identifier: str = Field(min_length=1, max_length=500)
    source_url: str
    posted_at: str
    recorded_by: str
    statement: str = Field(min_length=10, max_length=4000)
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    preparation_id: str | None = None

    @field_validator("remote_identifier", "recorded_by", "statement")
    @classmethod
    def real_text(cls, value: str) -> str:
        if not value.strip() or any(ord(character) < 32 for character in value):
            raise ValueError("Posting observations require nonempty readable text")
        return value.strip()

    @field_validator("source_url")
    @classmethod
    def public_receipt(cls, value: str) -> str:
        _origin(value)
        return value

    @field_validator("posted_at")
    @classmethod
    def observed_time(cls, value: str) -> str:
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is None or timestamp > datetime.now(timezone.utc) + timedelta(minutes=1):
            raise ValueError("Posting date must include a timezone and cannot be in the future")
        return value


class Preprint(Record):
    id: str = Field(default_factory=lambda: uid("preprint"))
    paper_id: str
    study_id: str
    freeze_digest: str
    state: Literal["PREPRINT_READY", "PREPRINTED"]
    created_at: str = Field(default_factory=now)
    policy_id: str | None = None
    settings_sha256: str | None = None
    policy_fingerprint: str | None = None
    files: dict[str, str] = Field(default_factory=dict)
    manifest_sha256: str | None = None
    receipt_sha256: str | None = None
    evidence_sha256: str | None = None
    remote_identifier: str | None = None
    source_url: str | None = None
    posted_at: str | None = None
    recorded_by: str | None = None


def _read_input(path: Path, maximum: int) -> bytes:
    path = Path(path).absolute()
    ensure_unlinked(path)
    if not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise ValueError("Preprint input must be a nonempty ordinary file within the size limit")
    data = path.read_bytes()
    if not 0 < len(data) <= maximum:
        raise ValueError("Preprint input changed while reading or exceeds the size limit")
    return data


def _approved(ws: Workspace, paper_id: str, actor: str | None = None):
    paper = ws.get("paper", paper_id, Paper)
    snapshot = frozen_workspace(ws, paper)
    if actor is not None and actor != paper.approved_by:
        raise ValueError("Preprint action must be confirmed by the approved scientific author")
    return paper, snapshot


def _permission(settings: PreprintSettings, policy: VenuePolicy) -> None:
    if settings.decision != "allowed":
        raise ValueError("Preprint preparation requires an explicit allowed policy decision")
    if not all((settings.author_approval, settings.authorized_to_post, settings.policy_interpretation_confirmed)):
        raise ValueError("Preprint preparation requires every explicit author attestation")
    evidence = policy.evidence.get("preprint_policy")
    if not policy.values.preprint_policy or evidence is None:
        raise ValueError("An official preprint policy with reviewed evidence is required")
    if settings.evidence.source_url != evidence.source_url or normalize_text(settings.evidence.excerpt) != normalize_text(evidence.excerpt):
        raise ValueError("Preprint decision must quote the captured official preprint policy evidence")
    # The researcher's typed decision is intentional; no keyword guessing about
    # arbitrary publisher prose establishes permission.


def _active_venue_errors(ws: Workspace, paper: Paper, policy: VenuePolicy) -> list[str]:
    # Reuse the publication journal replay, including its corruption checks,
    # rather than trusting a mutable Submission.state alone.
    from .publication import active_for_study, _effective_submission
    errors = []
    for submission in active_for_study(ws, paper.study_id):
        effective = _effective_submission(ws, submission)
        active_policy = ws.get("policy", effective.policy_id, VenuePolicy)
        if submission.venue_id != policy.venue_id or policy_fingerprint(active_policy) != policy_fingerprint(policy):
            errors.append("Preprint permission must use the currently active peer-reviewed venue's reviewed policy")
    return errors


def _manuscript(snapshot, doc: Document, settings: PreprintSettings) -> str:
    text = render(snapshot, doc, include_audit=False)
    for section in doc.sections:
        for block in section.blocks:
            if block.kind == "claim":
                claim = snapshot.get("claim", block.ref, Claim)
                text = text.replace(claim_text(claim), claim_text(claim).split(" [Evidence:", 1)[0])
    text += "\n\n## License\n\n" + escape_md(settings.license) + "\n"
    if doc.ai_provenance:
        text += "\n## Recorded AI assistance\n\n"
        text += "\n".join(f"- {escape_md(item['role'])}: {escape_md(item['tool'])}, model {escape_md(item['model'] or 'unspecified')}." for item in doc.ai_provenance) + "\n"
    return text


def _metadata(doc: Document, settings: PreprintSettings) -> dict:
    # Public identity fields only: private email and internal source paths never
    # enter the public manuscript or source archive.
    author = {key: doc.author[key] for key in ("display_name", "affiliation", "orcid") if doc.author.get(key)}
    return {"title": doc.title, "author": author, "license": settings.license,
            "server": settings.server, "server_url": settings.server_url,
            "publication_type": "preprint", "peer_reviewed": False}


def _preparation_manifest(record: Preprint) -> dict:
    return {"preprint_id": record.id, "paper_id": record.paper_id, "study_id": record.study_id,
            "freeze_digest": record.freeze_digest, "policy_id": record.policy_id,
            "policy_fingerprint": record.policy_fingerprint, "settings_sha256": record.settings_sha256,
            "files": record.files, "external_upload_performed": False, "peer_reviewed": False}


def audit_registry(ws: Workspace, *, db: sqlite3.Connection | None = None) -> list[Preprint]:
    """Reconcile indexed facts with committed artifacts, ignoring failed staging.

    A publication boundary passes its existing SQLite write transaction so a
    deleted posting index cannot erase the required journal compatibility review.
    Artifact checks deliberately omit active-policy replay to avoid recursion.
    """
    if db is None:
        with ws._database() as connection:
            return audit_registry(ws, db=connection)
    rows = db.execute("SELECT id,data FROM records WHERE kind='preprint' ORDER BY rowid").fetchall()
    records = []
    for key, value in rows:
        record = Preprint.model_validate_json(value)
        if record.id != key:
            raise ValueError("Preprint registry identifier differs from its indexed record")
        records.append(record)
    root = ws.path("preprints")
    artifacts = set()
    if root.exists():
        for path in root.iterdir():
            path = ws.path(f"preprints/{path.name}")
            if path.name.startswith(".preparing-"):
                if not path.is_dir():
                    raise ValueError("Preprint staging artifact must be an ordinary directory")
                continue
            if not path.is_dir():
                raise ValueError("Preprint registry contains an unexpected artifact")
            artifacts.add(path.name)
    if artifacts != {record.id for record in records}:
        raise ValueError("Preprint registry and committed artifacts differ; missing or orphaned posting facts block author attestation")
    for record in records:
        report = check(ws, record, check_active_policy=False)
        if not report["valid"]:
            raise ValueError("Preprint registry artifact validation failed: " + "; ".join(report["errors"]))
    return records


def prepare(ws: Workspace, settings_path: Path, *, pandoc: str | None = None,
            client: httpx.Client | None = None) -> tuple[Preprint, Path]:
    data = _read_input(settings_path, 128 * 1024)
    settings = PreprintSettings.model_validate_json(data)
    with ws.lock(f"preprint-paper-{settings.paper_id}"):
        audit_registry(ws)
        paper, snapshot = _approved(ws, settings.paper_id, settings.reviewed_by)
        original = ws.get("policy", settings.policy_id, VenuePolicy)
        errors = validate_policy(ws, original, fresh=False)
        if errors:
            raise ValueError("Preprint policy failed verification: " + "; ".join(errors))
        _permission(settings, original)
        target_errors = _active_venue_errors(ws, paper, original)
        if target_errors:
            raise ValueError("; ".join(target_errors))
        current = refresh_policy(ws, original, client=client)
        errors = validate_policy(ws, current)
        if errors or policy_fingerprint(current) != policy_fingerprint(original):
            raise ValueError("Live preprint policy changed or failed verification; review the current official source")
        _permission(settings, current)
        doc = Document.model_validate_json(snapshot.path("canonical.json").read_bytes())
        record = Preprint(paper_id=paper.id, study_id=paper.study_id, freeze_digest=paper.freeze_digest,
                          state="PREPRINT_READY", policy_id=current.id, policy_fingerprint=policy_fingerprint(current))
        parent = ws.path("preprints")
        parent.mkdir(exist_ok=True)
        destination = ws.path(f"preprints/{record.id}")
        stage = Path(tempfile.mkdtemp(prefix=".preparing-", dir=parent))
        published = False
        try:
            (stage / "settings.json").write_bytes(data)
            record.settings_sha256 = digest_file(stage / "settings.json")
            (stage / "manuscript.md").write_text(_manuscript(snapshot, doc, settings), encoding="utf-8")
            write_json(stage / "metadata.json", _metadata(doc, settings))
            conversion = {}
            for format in ("tex", "pdf"):
                conversion[format] = convert(stage / "manuscript.md", stage / f"manuscript.{format}",
                                             pandoc=pandoc)
            write_json(stage / "conversion.json", conversion)
            public_files = ("manuscript.md", "manuscript.tex", "metadata.json")
            with zipfile.ZipFile(stage / "source.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name in public_files:
                    archive.write(stage / name, name)
            record.files = {path.relative_to(stage).as_posix(): digest_file(path) for path in stage.iterdir() if path.is_file()}
            write_json(stage / "manifest.json", _preparation_manifest(record))
            record.manifest_sha256 = digest_file(stage / "manifest.json")
            # Recheck the approved evidence after conversion before publication.
            _approved(ws, paper.id, settings.reviewed_by)
            with ws._database() as db:
                db.execute("BEGIN IMMEDIATE")
                audit_registry(ws, db=db)
                target_errors = _active_venue_errors(ws, paper, current)
                if target_errors:
                    raise ValueError("; ".join(target_errors))
                ws.rename_artifact(stage, destination)
                published = True
                db.execute("INSERT INTO records VALUES (?,?,?)", ("preprint", record.id, record.model_dump_json()))
            return record, destination
        except BaseException:
            if published:
                ws.discard_uncommitted_artifact(destination, kind="preprint",
                    record_id=record.id, field="manifest_sha256", expected_value=record.manifest_sha256)
            if stage.exists():
                # A failed local derivative can be inspected and retried without
                # publishing a PREPRINT_READY record.
                write_json(stage / "failure.json", {"preprint_id": record.id, "failed_at": now()})
            raise


def record_posting(ws: Workspace, receipt_path: Path, evidence_path: Path, *, confirmed: bool = False) -> tuple[Preprint, Path]:
    if confirmed is not True:
        raise ValueError("Explicit author confirmation is required to import a posting receipt")
    receipt_bytes = _read_input(receipt_path, 128 * 1024)
    evidence_bytes = _read_input(evidence_path, 4 * 1024 * 1024)
    receipt = PostingReceipt.model_validate_json(receipt_bytes)
    with ws.lock("preprint-register"):
        audit_registry(ws)
        paper, _ = _approved(ws, receipt.paper_id, receipt.recorded_by)
        if receipt.content_digest != paper.freeze_digest:
            raise ValueError("Posting receipt must identify the approved frozen content digest")
        records = ws.list("preprint", Preprint)
        if any(item.state == "PREPRINTED" and (item.source_url == receipt.source_url or
               (item.source_url and _origin(item.source_url) == _origin(receipt.source_url) and item.remote_identifier == receipt.remote_identifier)) for item in records):
            raise ValueError("This external preprint posting is already recorded")
        prepared = bool(receipt.preparation_id)
        if prepared:
            record = ws.get("preprint", receipt.preparation_id, Preprint)
            if record.state != "PREPRINT_READY" or record.paper_id != paper.id or record.freeze_digest != receipt.content_digest:
                raise ValueError("Posting receipt differs from its approved preparation")
            audit = check(ws, record)
            if not audit["valid"]:
                raise ValueError("Preprint preparation is corrupt: " + "; ".join(audit["errors"]))
            root = ws.path(f"preprints/{record.id}")
            settings = PreprintSettings.model_validate_json(ws.path(f"preprints/{record.id}/settings.json").read_bytes())
            if _origin(receipt.source_url) != _origin(settings.server_url):
                raise ValueError("Posting receipt source differs from the prepared preprint server")
        else:
            # Existing external posting is an observable fact even if the
            # author had no policy permission; it cannot authorize another post.
            record = Preprint(paper_id=paper.id, study_id=paper.study_id, freeze_digest=paper.freeze_digest, state="PREPRINTED")
            root = ws.path(f"preprints/{record.id}")
            root.parent.mkdir(exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".posting-" if prepared else ".preparing-", dir=root if prepared else root.parent))
        receipt_stage = stage if prepared else stage / "posting"
        receipt_stage.mkdir(exist_ok=True)
        destination = root / "posting" if prepared else root
        published = False
        try:
            (receipt_stage / "receipt.json").write_bytes(receipt_bytes)
            (receipt_stage / "evidence.bin").write_bytes(evidence_bytes)
            record.receipt_sha256 = digest_file(receipt_stage / "receipt.json")
            record.evidence_sha256 = digest_file(receipt_stage / "evidence.bin")
            record.state = "PREPRINTED"
            record.remote_identifier = receipt.remote_identifier
            record.source_url = receipt.source_url
            record.posted_at = receipt.posted_at
            record.recorded_by = receipt.recorded_by
            with ws._database() as db:
                db.execute("BEGIN IMMEDIATE")
                audit_registry(ws, db=db)
                ws.rename_artifact(stage, destination)
                published = True
                db.execute("INSERT INTO records VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data", ("preprint", record.id, record.model_dump_json()))
            return record, root
        except BaseException:
            if published:
                ws.discard_uncommitted_artifact(destination, kind="preprint",
                    record_id=record.id, field="receipt_sha256", expected_value=record.receipt_sha256)
            if stage.exists():
                write_json(stage / "failure.json", {"preprint_id": record.id, "failed_at": now()})
            raise


def check(ws: Workspace, preprint: Preprint, *, check_active_policy: bool = True) -> dict:
    errors, permission_errors = [], []
    posting_valid = False
    if check_active_policy:
        try:
            audit_registry(ws)
        except (ValueError, OSError) as error:
            permission_errors.append(f"Preprint registry audit failed: {error}")
    try:
        record = ws.get("preprint", preprint.id, Preprint)
        if record != preprint:
            errors.append("Preprint record differs from its stored identity")
        paper, snapshot = _approved(ws, record.paper_id)
        if record.study_id != paper.study_id or record.freeze_digest != paper.freeze_digest:
            errors.append("Preprint differs from the approved scientific content")
        root = ws.path(f"preprints/{record.id}")
        if record.policy_id:
            policy = ws.get("policy", record.policy_id, VenuePolicy)
            errors.extend(validate_policy(ws, policy, fresh=False))
            permission_errors.extend(validate_policy(ws, policy))
            if check_active_policy:
                try:
                    permission_errors.extend(_active_venue_errors(ws, paper, policy))
                except ValueError as error:
                    permission_errors.append(f"Active peer-review audit failed: {error}")
            if policy_fingerprint(policy) != record.policy_fingerprint:
                errors.append("Prepared preprint policy differs from its binding")
            manifest_path = ws.path(f"preprints/{record.id}/manifest.json")
            if digest_file(manifest_path) != record.manifest_sha256 or json.loads(manifest_path.read_bytes()) != _preparation_manifest(record):
                errors.append("Preprint preparation manifest changed")
            actual = {path.name for path in root.iterdir() if path.is_file()}
            if actual != {*record.files, "manifest.json"}:
                errors.append("Preprint preparation file set changed")
            for name, digest in record.files.items():
                if digest_file(ws.path(f"preprints/{record.id}/{name}")) != digest:
                    errors.append(f"Prepared preprint artifact changed: {name}")
            errors.extend(verify_receipts(root / "manuscript.md",
                {format: root / f"manuscript.{format}" for format in ("tex", "pdf")},
                root / "conversion.json"))
            settings_path = ws.path(f"preprints/{record.id}/settings.json")
            settings = PreprintSettings.model_validate_json(settings_path.read_bytes())
            if digest_file(settings_path) != record.settings_sha256 or settings.paper_id != record.paper_id or settings.reviewed_by != paper.approved_by:
                errors.append("Prepared preprint author settings changed")
            original = ws.get("policy", settings.policy_id, VenuePolicy)
            errors.extend(validate_policy(ws, original, fresh=False))
            if original.venue_id != policy.venue_id or policy_fingerprint(original) != record.policy_fingerprint:
                errors.append("Prepared preprint differs from its originally reviewed venue policy")
            _permission(settings, policy)
            doc = Document.model_validate_json(snapshot.path("canonical.json").read_bytes())
            if (root / "manuscript.md").read_text(encoding="utf-8") != _manuscript(snapshot, doc, settings) or json.loads((root / "metadata.json").read_bytes()) != _metadata(doc, settings):
                errors.append("Prepared preprint differs from the frozen scientific manuscript")
            with zipfile.ZipFile(root / "source.zip") as archive:
                names = archive.namelist()
                if set(names) != {"manuscript.md", "manuscript.tex", "metadata.json"} or len(names) != 3:
                    errors.append("Preprint source archive contains unexpected or private files")
                else:
                    for name in names:
                        if archive.read(name) != (root / name).read_bytes():
                            errors.append(f"Preprint source archive content differs: {name}")
        elif record.state == "PREPRINT_READY" or record.files or record.manifest_sha256 or record.settings_sha256 or record.policy_fingerprint:
            errors.append("Preprint preparation has no policy binding")
        if record.state == "PREPRINTED":
            posting_errors = []
            receipt_path = ws.path(f"preprints/{record.id}/posting/receipt.json")
            evidence_path = ws.path(f"preprints/{record.id}/posting/evidence.bin")
            if digest_file(receipt_path) != record.receipt_sha256 or digest_file(evidence_path) != record.evidence_sha256:
                posting_errors.append("Imported preprint receipt evidence changed")
            receipt = PostingReceipt.model_validate_json(receipt_path.read_bytes())
            expected = (record.paper_id, record.freeze_digest, record.remote_identifier, record.source_url, record.posted_at, record.recorded_by)
            observed = (receipt.paper_id, receipt.content_digest, receipt.remote_identifier, receipt.source_url, receipt.posted_at, receipt.recorded_by)
            if expected != observed or receipt.recorded_by != paper.approved_by or receipt.preparation_id != (record.id if record.policy_id else None):
                posting_errors.append("Imported preprint observation differs from its approved content or author")
            if record.policy_id and _origin(receipt.source_url) != _origin(settings.server_url):
                posting_errors.append("Imported preprint source differs from its prepared server")
            if not evidence_path.stat().st_size:
                posting_errors.append("Imported preprint receipt evidence is empty")
            if {path.name for path in receipt_path.parent.iterdir()} != {"receipt.json", "evidence.bin"}:
                posting_errors.append("Imported preprint posting evidence file set changed")
            posting_valid = not posting_errors
            errors.extend(posting_errors)
        elif any((record.receipt_sha256, record.evidence_sha256, record.remote_identifier, record.source_url, record.posted_at, record.recorded_by)) or (root / "posting").exists():
            errors.append("A prepared preprint cannot contain unrecorded posting observations")
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        errors.append(f"Preprint artifact validation failed: {error}")
    valid = not errors
    return {"preprint_id": preprint.id, "valid": valid, "errors": sorted(set(errors)),
            "upload_authorized": valid and check_active_policy and preprint.state == "PREPRINT_READY" and not permission_errors,
            "permission_errors": sorted(set(permission_errors)),
            "posting_recorded": valid and posting_valid, "peer_reviewed": False,
            "external_upload_performed": False,
            "verification_scope": "author-confirmed imported receipt" if preprint.state == "PREPRINTED" else "approved local derivative and researcher-reviewed policy",
            "permission_scope": "author attestation and reviewed journal preprint policy",
            "server_submission_requirements_verified": False,
            "warnings": ["A preprint is separate from peer-reviewed publication and does not release a peer-review submission slot",
                         "Server classification, metadata, license eligibility and server-side TeX compilation still require author review before any upload"]}

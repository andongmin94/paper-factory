"""Author-recorded publication history with a workspace-local single active slot.

This module never uploads manuscripts or contacts submission systems. Journal
receipts are imported by an identified author and retained as evidence. A
withdrawal request keeps the slot occupied until an actual decision is recorded.
"""

from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import hashlib
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Literal

import httpx
from pydantic import Field, StrictBool, field_validator, model_validator

from .integrity import frozen_workspace
from .models import Claim, Paper, Project, Record, Study, Submission, SubmissionState, now, transition_submission, uid
from .submission_package import Package, verify as verify_package
from .venue_compiler import policy_fingerprint
from .venue_policy import PolicyEvidence, VenuePolicy, _origin, normalize_text, refresh_policy, validate_policy
from .venues import Venue
from .workspace import Workspace, digest_file, ensure_unlinked, write_json


ACTIVE_STATES = frozenset({SubmissionState.AUTHOR_ATTESTED, SubmissionState.SUBMITTED,
    SubmissionState.UNDER_REVIEW, SubmissionState.REVISION, SubmissionState.WITHDRAWAL_REQUESTED,
    SubmissionState.ACCEPTED, SubmissionState.PROOF, SubmissionState.PUBLISHED})
PREPARATION_STATES = frozenset({SubmissionState.VENUE_SELECTED, SubmissionState.VENUE_COMPILED, SubmissionState.SUBMISSION_READY})
RECEIPT_STATES = frozenset(set(SubmissionState) - PREPARATION_STATES - {SubmissionState.AUTHOR_ATTESTED})
MAX_RECEIPT_BYTES = 20 * 1024 * 1024


class PreprintReview(Record):
    decision: Literal["allowed", "forbidden", "unknown"]
    preprint_ids: list[str]
    evidence: PolicyEvidence

    @field_validator("preprint_ids")
    @classmethod
    def exact_identifiers(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("Reviewed preprint identifiers must be unique")
        for value in values:
            Record.safe_id(value)
        return values


class AttestationInput(Record):
    actor: str = Field(min_length=1, max_length=300)
    all_authors_approved: StrictBool
    not_under_review_elsewhere: StrictBool
    coi_correct: StrictBool
    funding_correct: StrictBool
    ai_disclosure_correct: StrictBool
    author_information_correct: StrictBool
    preprint_review: PreprintReview | None = None

    @field_validator("actor")
    @classmethod
    def actual_actor(cls, value):
        if not value.strip():
            raise ValueError("An actual named author is required")
        return value.strip()

    @model_validator(mode="after")
    def affirmative(self):
        if any(getattr(self, name) is not True for name in ("all_authors_approved", "not_under_review_elsewhere",
                "coi_correct", "funding_correct", "ai_disclosure_correct", "author_information_correct")):
            raise ValueError("All six final author attestations must explicitly be true")
        return self


class ReceiptInput(Record):
    target_state: SubmissionState
    external_id: str = Field(min_length=1, max_length=300)
    external_url: str = Field(min_length=1, max_length=4000)
    occurred_at: str
    verified_by: str = Field(min_length=1, max_length=300)
    note: str = Field(min_length=10, max_length=12000)

    @field_validator("target_state")
    @classmethod
    def actual_receipt_state(cls, value):
        if value not in RECEIPT_STATES:
            raise ValueError("Receipt target must be a journal submission or decision state")
        return value

    @field_validator("external_id", "verified_by", "note")
    @classmethod
    def actual_text(cls, value):
        if not value.strip():
            raise ValueError("Receipt details and a named verifier must be supplied")
        return value.strip()

    @field_validator("external_url")
    @classmethod
    def public_url(cls, value):
        _origin(value)
        return value

    @field_validator("occurred_at")
    @classmethod
    def actual_date(cls, value):
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is None or timestamp > datetime.now(timezone.utc) + timedelta(minutes=1):
            raise ValueError("Receipt occurrence time must include a timezone and cannot be in the future")
        return timestamp.astimezone(timezone.utc).isoformat()


class CancellationInput(Record):
    actor: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=10, max_length=4000)

    @field_validator("actor", "reason")
    @classmethod
    def actual_text(cls, value):
        if not value.strip():
            raise ValueError("Cancellation requires a named author and actual reason")
        return value.strip()


class EventData(Record):
    id: str
    submission_id: str
    paper_id: str
    study_id: str
    sequence: int = Field(ge=1, strict=True)
    kind: Literal["attestation", "receipt", "cancellation", "revision_submission"]
    from_state: SubmissionState
    to_state: SubmissionState
    actor: str
    recorded_at: str
    previous_sha256: str | None
    values: dict
    evidence_sha256: str | None = None


class PublicationEvent(EventData):
    artifact_sha256: str


def _rows(db: sqlite3.Connection, kind: str, model: type[Record]) -> list[Record]:
    records = []
    for key, raw in db.execute("SELECT id,data FROM records WHERE kind=? ORDER BY rowid", (kind,)):
        record = model.model_validate_json(raw)
        if record.id != key:
            raise ValueError(f"Publication audit: persisted {kind} identifier differs from its key")
        records.append(record)
    return records


def _get(db: sqlite3.Connection, kind: str, key: str, model: type[Record]) -> Record:
    raw = db.execute("SELECT data FROM records WHERE kind=? AND id=?", (kind, key)).fetchone()
    if raw is None:
        raise ValueError(f"Publication audit: missing {kind} record {key}")
    record = model.model_validate_json(raw[0])
    if record.id != key:
        raise ValueError(f"Publication audit: persisted {kind} identifier differs from its key")
    return record


def _event_root(ws: Workspace, event: EventData) -> Path:
    return ws.path(f"publication/{event.submission_id}/{event.id}")


def _author(ws: Workspace, submission: Submission, paper: Paper) -> str:
    author = json.loads(ws.path(f"submissions/{submission.id}/package/author.json").read_bytes())
    if not paper.approved_by or author.get("display_name") != paper.approved_by:
        raise ValueError("Publication audit: approved author and packaged author differ")
    return paper.approved_by


def _package(ws: Workspace, submission: Submission) -> Package:
    result = verify_package(ws, submission, fresh=False)
    if not result.get("passed") or not result.get("ready"):
        raise ValueError("Publication requires an intact ready package: " + "; ".join(result["errors"]))
    return ws.get("package", submission.id, Package)


def _effective_submission(ws: Workspace, submission: Submission, *, before_sequence: int | None = None) -> Submission:
    """Use the last confirmed revised policy after its journal event was audited."""
    events = [event for event in ws.list("publication_event", PublicationEvent)
        if event.submission_id == submission.id and event.kind == "revision_submission"
        and (before_sequence is None or event.sequence < before_sequence)]
    if not events:
        return submission
    from .revision_submission import RevisionDelivery
    event = max(events, key=lambda item: item.sequence)
    delivery = ws.get("revision_delivery", event.values["delivery_id"], RevisionDelivery)
    candidate = ws.get("submission", delivery.candidate_id, Submission)
    if (delivery.original_submission_id != submission.id or delivery.state != "RESUBMITTED"
            or delivery.publication_event_id != event.id or candidate.venue_id != submission.venue_id
            or candidate.paper_id != delivery.revised_paper_id):
        raise ValueError("Confirmed revision differs from its effective journal policy")
    return candidate


def _receipt_origin(ws: Workspace, submission: Submission, values: ReceiptInput) -> None:
    policy = ws.get("policy", submission.policy_id, VenuePolicy)
    permitted = {_origin(policy.values.submission_url)} if policy.values.submission_url else set()
    # The manuscript system's ID is anchored to the configured submission
    # service. A publisher decision page may also use an evidenced official host.
    venue = ws.get("venue", submission.venue_id, Venue)
    if venue.official_url:
        permitted.add(_origin(venue.official_url, allow_http=True))
    permitted.update(_origin(origin.origin) for origin in policy.official_origins)
    if _origin(values.external_url) not in permitted:
        raise ValueError("Receipt URL must use the verified submission service or an evidenced official policy host")


def _review_preprints(ws: Workspace, paper: Paper, values: AttestationInput, policy: VenuePolicy,
                     *, live_boundary: bool, db: sqlite3.Connection | None = None) -> dict[str, str]:
    from .preprints import Preprint, audit_registry, check as check_preprint
    review = values.preprint_review
    if live_boundary:
        records = audit_registry(ws, db=db)
        observed = {item.id for item in records if item.study_id == paper.study_id and item.state == "PREPRINTED"}
        if observed and (review is None or set(review.preprint_ids) != observed):
            raise ValueError("Every existing Study preprint posting must be explicitly reviewed against the target venue policy")
        if review is not None and set(review.preprint_ids) != observed:
            raise ValueError("Reviewed preprint identifiers must exactly match the Study's existing postings")
    if review is None:
        return {}
    if review.decision != "allowed":
        raise ValueError("Existing preprints require an explicit allowed decision against the target venue policy")
    evidence = policy.evidence.get("preprint_policy")
    if not policy.values.preprint_policy or evidence is None or review.evidence.source_url != evidence.source_url or normalize_text(review.evidence.excerpt) != normalize_text(evidence.excerpt):
        raise ValueError("Existing-preprint review must quote the freshly captured official preprint policy evidence")
    records = {}
    for preprint_id in review.preprint_ids:
        preprint = ws.get("preprint", preprint_id, Preprint)
        if preprint.study_id != paper.study_id or preprint.state != "PREPRINTED":
            raise ValueError("Reviewed preprint differs from the Study's actual posting facts")
        report = check_preprint(ws, preprint, check_active_policy=False)
        if not report["valid"] or not report["posting_recorded"]:
            raise ValueError("Existing preprint posting evidence is missing or corrupt: " + "; ".join(report["errors"]))
        records[preprint_id] = hashlib.sha256(json.dumps(preprint.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    return records


def _receipt_values(event: PublicationEvent) -> dict | None:
    if event.kind == "receipt":
        return event.values
    if event.kind == "revision_submission":
        return event.values["receipt"]
    return None


def _validate_event(ws: Workspace, submission: Submission, paper: Paper, event: PublicationEvent,
                    state: SubmissionState, previous: PublicationEvent | None,
                    external_id: str | None, attested_at: str | None) -> tuple[str | None, str | None]:
    root = _event_root(ws, event)
    expected_files = {"event.json", *( {"evidence.bin"} if event.evidence_sha256 else set())}
    actual_files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    if actual_files != expected_files or digest_file(ws.path(f"publication/{submission.id}/{event.id}/event.json")) != event.artifact_sha256:
        raise ValueError("Publication event artifact changed or is missing")
    if json.loads((root / "event.json").read_bytes()) != event.model_dump(mode="json", exclude={"artifact_sha256"}):
        raise ValueError("Publication event record differs from its immutable artifact")
    if event.evidence_sha256 and (digest_file(ws.path(f"publication/{submission.id}/{event.id}/evidence.bin")) != event.evidence_sha256 or (root / "evidence.bin").stat().st_size == 0):
        raise ValueError("Imported publication receipt evidence changed or is missing")
    if event.paper_id != paper.id or event.study_id != paper.study_id or event.submission_id != submission.id:
        raise ValueError("Publication event paper/study/submission binding differs")
    if event.from_state != state or event.previous_sha256 != (previous.artifact_sha256 if previous else None):
        raise ValueError("Publication event state or hash chain differs")
    recorded = datetime.fromisoformat(event.recorded_at)
    if recorded.tzinfo is None or recorded > datetime.now(timezone.utc) + timedelta(minutes=1) or (previous and recorded < datetime.fromisoformat(previous.recorded_at)):
        raise ValueError("Publication event chronology is invalid")
    probe = submission.model_copy(update={"state": state})
    transition_submission(probe, event.to_state)
    author = _author(ws, submission, paper)
    if event.kind == "attestation":
        if event.from_state != SubmissionState.SUBMISSION_READY or event.to_state != SubmissionState.AUTHOR_ATTESTED or event.evidence_sha256:
            raise ValueError("Invalid author attestation event")
        values = AttestationInput.model_validate(event.values.get("attestation"))
        if values.actor != author or event.actor != author:
            raise ValueError("Final attestation must be by the approved named author")
        package = ws.get("package", submission.id, Package)
        policy = ws.get("policy", event.values["policy_id"], VenuePolicy)
        policy_errors = validate_policy(ws, policy, fresh=False)
        packaged_policy = ws.get("policy", package.policy_id, VenuePolicy)
        expected = {"attestation": values.model_dump(mode="json"), "package_sha256": package.manifest_sha256,
            "archive_sha256": package.archive_sha256, "freeze_digest": paper.freeze_digest,
            "author_sha256": package.files["author.json"], "declarations_sha256": package.files["declarations.json"],
            "policy_id": policy.id, "policy_fingerprint": policy_fingerprint(policy),
            "preprint_records": _review_preprints(ws, paper, values, policy, live_boundary=False)}
        if event.values != expected or policy_errors or policy.venue_id != submission.venue_id or policy_fingerprint(policy) != policy_fingerprint(packaged_policy):
            raise ValueError("Final attestation package/freeze/declarations/current-policy binding differs")
        # The new policy capture must have been retrieved for this attestation,
        # and still have been within its permitted lifetime at attestation time.
        for source in policy.sources:
            fetched = datetime.fromisoformat(source.fetched_at)
            if fetched.tzinfo is None or fetched > recorded or recorded - fetched > timedelta(minutes=5):
                raise ValueError("Final attestation was not backed by a submission-time live policy capture")
        return None, event.recorded_at
    if event.kind == "cancellation":
        values = CancellationInput.model_validate(event.values)
        if event.from_state != SubmissionState.AUTHOR_ATTESTED or event.to_state != SubmissionState.SUBMISSION_READY or event.evidence_sha256 or event.actor != author or values.actor != author:
            raise ValueError("Only an unused author attestation reservation can be cancelled")
        return None, None
    if event.kind == "revision_submission":
        from .revision_submission import validate_publication_event
        previous_receipt = _receipt_values(previous) if previous else None
        current_receipt = ReceiptInput.model_validate(event.values["receipt"])
        if previous_receipt and datetime.fromisoformat(current_receipt.occurred_at) < datetime.fromisoformat(previous_receipt["occurred_at"]):
            raise ValueError("Journal receipt chronology moved backwards")
        return validate_publication_event(ws, submission, paper, event, external_id, attested_at)
    values = ReceiptInput.model_validate(event.values)
    if values.target_state != event.to_state or event.actor != values.verified_by or not event.evidence_sha256:
        raise ValueError("Journal state changes require preserved, author-imported receipt evidence")
    if values.verified_by != author:
        raise ValueError("Journal receipt must be verified by the approved named author")
    _receipt_origin(ws, _effective_submission(ws, submission, before_sequence=event.sequence), values)
    if external_id is not None and values.external_id != external_id:
        raise ValueError("Journal manuscript ID changed within a submission history")
    occurred = datetime.fromisoformat(values.occurred_at)
    if not attested_at or occurred < datetime.fromisoformat(attested_at) or occurred > recorded + timedelta(minutes=1):
        raise ValueError("Journal receipt occurrence time precedes author attestation or follows its import")
    previous_receipt = _receipt_values(previous) if previous else None
    if previous_receipt and occurred < datetime.fromisoformat(previous_receipt["occurred_at"]):
        raise ValueError("Journal receipt chronology moved backwards")
    return values.external_id, attested_at


def _audit(ws: Workspace, db: sqlite3.Connection) -> tuple[dict[str, Submission], dict[str, list[PublicationEvent]]]:
    submissions = {item.id: item for item in _rows(db, "submission", Submission)}
    events = _rows(db, "publication_event", PublicationEvent)
    indexed = {(event.submission_id, event.id) for event in events}
    artifacts = set()
    root = ws.path("publication")
    if root.exists():
        for candidate in root.iterdir():
            candidate = ws.path(f"publication/{candidate.name}")
            if not candidate.is_dir():
                raise ValueError("Publication journal contains an unexpected artifact")
            for artifact in candidate.iterdir():
                artifact = ws.path(f"publication/{candidate.name}/{artifact.name}")
                if artifact.name.startswith(".event-"):
                    continue
                if not artifact.is_dir():
                    raise ValueError("Publication journal contains an unexpected artifact")
                artifacts.add((candidate.name, artifact.name))
    if artifacts != indexed:
        raise ValueError("Publication journal and record index differ; a missing or orphaned event blocks further submissions")
    by_submission: dict[str, list[PublicationEvent]] = {}
    for event in events:
        if event.submission_id not in submissions:
            raise ValueError("Publication journal references a missing submission; active status cannot be established")
        by_submission.setdefault(event.submission_id, []).append(event)
    active_studies: dict[str, str] = {}
    for submission in submissions.values():
        history = sorted(by_submission.get(submission.id, []), key=lambda item: item.sequence)
        if not history:
            if submission.state not in PREPARATION_STATES:
                raise ValueError("Active or concluded submission has no publication journal")
            continue
        paper = _get(db, "paper", submission.paper_id, Paper)
        _get(db, "study", paper.study_id, Study)
        _package(ws, submission)
        state = SubmissionState.SUBMISSION_READY
        previous, external_id, attested_at = None, None, None
        for sequence, event in enumerate(history, 1):
            if event.sequence != sequence:
                raise ValueError("Publication event sequence contains a gap or duplicate")
            external_id, attested_at = _validate_event(ws, submission, paper, event, state, previous, external_id, attested_at)
            state, previous = event.to_state, event
        if submission.state != state:
            raise ValueError("Submission state differs from its immutable publication journal")
        if state in ACTIVE_STATES:
            if paper.study_id in active_studies:
                raise ValueError("Study has more than one active peer-reviewed submission")
            active_studies[paper.study_id] = submission.id
        by_submission[submission.id] = history
    return submissions, by_submission


def _append(ws: Workspace, db: sqlite3.Connection, submission: Submission, paper: Paper,
            history: list[PublicationEvent], *, kind: str, target: SubmissionState, actor: str,
            values: dict, evidence: bytes | None = None) -> PublicationEvent:
    if kind == "receipt" and submission.state == SubmissionState.REVISION and target == SubmissionState.UNDER_REVIEW:
        raise ValueError("Resubmission requires a verified revision delivery and revised author attestation; use revision submission record")
    event_id = uid("publication-event")
    parent = ws.path(f"publication/{submission.id}")
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".event-", dir=parent))
    destination = parent / event_id
    published = False
    try:
        evidence_sha256 = None
        if evidence is not None:
            (stage / "evidence.bin").write_bytes(evidence)
            evidence_sha256 = digest_file(stage / "evidence.bin")
        data = EventData(id=event_id, submission_id=submission.id, paper_id=paper.id, study_id=paper.study_id,
            sequence=len(history) + 1, kind=kind, from_state=submission.state, to_state=target, actor=actor,
            recorded_at=now(), previous_sha256=history[-1].artifact_sha256 if history else None,
            values=values, evidence_sha256=evidence_sha256)
        write_json(stage / "event.json", data)
        event = PublicationEvent(**data.model_dump(), artifact_sha256=digest_file(stage / "event.json"))
        ws.rename_artifact(stage, destination)
        published = True
        # Reuse the semantic audit before changing the authoritative state.
        previous_receipt = next((data for prior in reversed(history) if (data := _receipt_values(prior)) is not None), None)
        external = previous_receipt["external_id"] if previous_receipt else None
        attested = next((prior.recorded_at for prior in reversed(history) if prior.kind == "attestation"), None)
        _validate_event(ws, submission, paper, event, submission.state, history[-1] if history else None, external, attested)
        transition_submission(submission, target)
        db.execute("INSERT INTO records VALUES (?,?,?)", ("publication_event", event.id, event.model_dump_json()))
        db.execute("UPDATE records SET data=? WHERE kind='submission' AND id=?", (submission.model_dump_json(), submission.id))
        return event
    except BaseException:
        if published:
            shutil.rmtree(ws.path(f"publication/{submission.id}/{event_id}"))
        raise
    finally:
        if stage.exists():
            shutil.rmtree(ws.path(stage.relative_to(ws.root).as_posix()))


@contextmanager
def _write_transaction(ws: Workspace):
    """Roll back only this operation's event artifacts if its DB commit fails."""
    published = []
    try:
        with ws._database() as db:
            db.execute("BEGIN IMMEDIATE")
            yield db, published
    except BaseException:
        for event in published:
            ws.discard_uncommitted_artifact(ws.root / "publication" / event.submission_id / event.id,
                kind="publication_event", record_id=event.id,
                field="artifact_sha256", expected_value=event.artifact_sha256)
        raise


def active_for_study(ws: Workspace, study_id: str) -> list[Submission]:
    """Return workspace-local occupied slots, failing closed on damaged history."""
    with ws._database() as db:
        submissions, _ = _audit(ws, db)
        _get(db, "study", study_id, Study)
        return [submission for submission in submissions.values() if submission.state in ACTIVE_STATES
            and _get(db, "paper", submission.paper_id, Paper).study_id == study_id]


def assert_current_attestation(ws: Workspace, submission: Submission,
        *, db: sqlite3.Connection | None = None) -> PublicationEvent:
    """Validate final author facts before an outbound initial submission action.

    An imported receipt remains an observed fact. A new outbound action must
    match the latest attestation, including preprints recorded since it was made.
    Pass the caller's write transaction to keep this boundary atomic.
    """
    if db is None:
        with ws._database() as connection:
            return assert_current_attestation(ws, submission, db=connection)
    submissions, histories = _audit(ws, db)
    current = submissions.get(submission.id)
    history = histories.get(submission.id, [])
    if current is None or current.state != SubmissionState.AUTHOR_ATTESTED or not history or history[-1].kind != "attestation":
        raise ValueError("Outbound submission requires the current final author attestation")
    event = history[-1]
    paper = _get(db, "paper", current.paper_id, Paper)
    values = AttestationInput.model_validate(event.values["attestation"])
    policy = _get(db, "policy", event.values["policy_id"], VenuePolicy)
    observed = _review_preprints(ws, paper, values, policy, live_boundary=True, db=db)
    if observed != event.values["preprint_records"]:
        raise ValueError("Existing preprint posting facts changed after final author attestation")
    return event


def _evidence_signature(ws: Workspace, paper: Paper) -> tuple[str, set[tuple]]:
    snapshot = frozen_workspace(ws, paper)
    study = snapshot.get("study", paper.study_id, Study)
    project = snapshot.get("project", study.project_id, Project)
    claims = [snapshot.get("claim", claim_id, Claim) for claim_id in paper.claim_ids]
    return project.snapshot_digest, {(claim.raw_sha256, claim.pointer, claim.metric_name, claim.value) for claim in claims}


def _overlap_guard(ws: Workspace, db: sqlite3.Connection, paper: Paper, submissions: dict[str, Submission],
                   *, exclude_submission_id: str | None = None) -> None:
    """Conservatively block exact approved evidence reuse under a new Study ID."""
    source_digest, signatures = _evidence_signature(ws, paper)
    for candidate in submissions.values():
        if candidate.state not in ACTIVE_STATES or candidate.id == exclude_submission_id:
            continue
        paper_ids = {candidate.paper_id}
        # Every submitted version still belongs to the occupied journal slot,
        # including evidence removed from a later revision. _audit has already
        # validated these immutable events and their delivery bindings.
        for event in _rows(db, "publication_event", PublicationEvent):
            if event.submission_id == candidate.id and event.kind == "revision_submission":
                from .revision_submission import RevisionDelivery
                delivery = _get(db, "revision_delivery", event.values["delivery_id"], RevisionDelivery)
                paper_ids.add(delivery.revised_paper_id)
        # Final revised author attestation also reserves newly introduced
        # evidence before its resubmission receipt arrives.
        from .revision_submission import RevisionDelivery, _attestation
        for delivery in _rows(db, "revision_delivery", RevisionDelivery):
            if delivery.original_submission_id == candidate.id and delivery.state in {"AUTHOR_ATTESTED", "RESUBMITTED"}:
                _attestation(ws, delivery)
                paper_ids.add(delivery.revised_paper_id)
        for other_id in paper_ids:
            other = _get(db, "paper", other_id, Paper)
            other_source, other_signatures = _evidence_signature(ws, other)
            if set(paper.claim_ids).intersection(other.claim_ids) or (source_digest == other_source and signatures.intersection(other_signatures)):
                raise ValueError(f"Approved evidence overlaps an active or published manuscript: {candidate.id}; a new Study ID does not release the submission guard")


def attest(ws: Workspace, submission: Submission, values: AttestationInput, *, client: httpx.Client | None = None) -> PublicationEvent:
    """Reserve the Study's sole slot after six explicit final author statements."""
    values = AttestationInput.model_validate(values)
    current = ws.get("submission", submission.id, Submission)
    from .revision_submission import assert_regular_candidate
    assert_regular_candidate(ws, current)
    if current.state != SubmissionState.SUBMISSION_READY:
        raise ValueError("Final author attestation requires a ready, unused submission candidate")
    package = _package(ws, current)
    paper = ws.get("paper", current.paper_id, Paper)
    if values.actor != _author(ws, current, paper):
        raise ValueError("Final attestation must be by the approved named author")
    packaged_policy = ws.get("policy", package.policy_id, VenuePolicy)
    live = refresh_policy(ws, packaged_policy, client=client)
    errors = validate_policy(ws, live)
    if errors or policy_fingerprint(live) != policy_fingerprint(packaged_policy):
        raise ValueError("Submission-time official policy changed or requires review; recompile a new candidate: " + "; ".join(errors))
    payload = {"attestation": values.model_dump(mode="json"), "package_sha256": package.manifest_sha256,
        "archive_sha256": package.archive_sha256, "freeze_digest": paper.freeze_digest,
        "author_sha256": package.files["author.json"], "declarations_sha256": package.files["declarations.json"],
        "policy_id": live.id, "policy_fingerprint": policy_fingerprint(live),
        "preprint_records": _review_preprints(ws, paper, values, live, live_boundary=True)}
    with _write_transaction(ws) as (db, published):
        submissions, histories = _audit(ws, db)
        current = submissions.get(submission.id)
        if current is None or current.state != SubmissionState.SUBMISSION_READY:
            raise ValueError("Final author attestation requires a ready, unused submission candidate")
        assert_regular_candidate(ws, current, db=db)
        paper = _get(db, "paper", current.paper_id, Paper)
        _get(db, "study", paper.study_id, Study)
        occupied = [candidate for candidate in submissions.values() if candidate.state in ACTIVE_STATES
            and _get(db, "paper", candidate.paper_id, Paper).study_id == paper.study_id]
        if occupied:
            raise ValueError(f"Study already has an active peer-reviewed submission: {occupied[0].id} ({occupied[0].state})")
        _overlap_guard(ws, db, paper, submissions)
        if _review_preprints(ws, paper, values, live, live_boundary=True, db=db) != payload["preprint_records"]:
            raise ValueError("Existing preprint posting facts changed during final author attestation")
        _package(ws, current)
        event = _append(ws, db, current, paper, histories.get(current.id, []), kind="attestation",
            target=SubmissionState.AUTHOR_ATTESTED, actor=values.actor, values=payload)
        published.append(event)
    return event


def record_receipt(ws: Workspace, submission: Submission, values: ReceiptInput, evidence_path: Path) -> PublicationEvent:
    """Import an actual receipt or decision; never infer a journal's state."""
    values = ReceiptInput.model_validate(values)
    ensure_unlinked(evidence_path.expanduser())
    source = evidence_path.expanduser().resolve()
    if not source.is_file():
        raise ValueError("Journal receipt evidence must be an existing file")
    with source.open("rb") as stream:
        evidence = stream.read(MAX_RECEIPT_BYTES + 1)
    if not evidence or len(evidence) > MAX_RECEIPT_BYTES:
        raise ValueError("Journal receipt evidence must be nonempty and at most 20 MiB")
    with _write_transaction(ws) as (db, published):
        submissions, histories = _audit(ws, db)
        current = submissions.get(submission.id)
        if current is None:
            raise ValueError("Unknown submission for publication receipt")
        if current.state == SubmissionState.REVISION and values.target_state == SubmissionState.UNDER_REVIEW:
            raise ValueError("Resubmission requires a verified revision delivery and revised author attestation; use revision submission record")
        paper = _get(db, "paper", current.paper_id, Paper)
        event = _append(ws, db, current, paper, histories.get(current.id, []), kind="receipt",
            target=values.target_state, actor=values.verified_by, values=values.model_dump(mode="json"), evidence=evidence)
        published.append(event)
    return event


def cancel_attestation(ws: Workspace, submission: Submission, actor: str, reason: str) -> PublicationEvent:
    """Release only an unused local reservation, retaining its entire audit."""
    values = CancellationInput(actor=actor, reason=reason)
    with _write_transaction(ws) as (db, published):
        submissions, histories = _audit(ws, db)
        current = submissions.get(submission.id)
        if current is None or current.state != SubmissionState.AUTHOR_ATTESTED:
            raise ValueError("Only an unused author attestation reservation can be cancelled")
        from .portal import assert_cancellable
        assert_cancellable(ws, current, db=db)
        paper = _get(db, "paper", current.paper_id, Paper)
        event = _append(ws, db, current, paper, histories[current.id], kind="cancellation",
            target=SubmissionState.SUBMISSION_READY, actor=values.actor, values=values.model_dump(mode="json"))
        published.append(event)
    return event


def check(ws: Workspace, submission: Submission) -> dict:
    try:
        with ws._database() as db:
            submissions, histories = _audit(ws, db)
            current = submissions.get(submission.id)
            if current is None:
                raise ValueError("Unknown submission for publication audit")
            history = histories.get(current.id, [])
            return {"submission_id": current.id, "passed": True, "errors": [], "state": current.state,
                "active": current.state in ACTIVE_STATES, "events": [event.model_dump(mode="json") for event in history],
                "external_submission_recorded": any(event.kind == "receipt" and event.to_state == SubmissionState.SUBMITTED for event in history),
                "automatic_external_submission_performed": False, "guard_scope": "current_workspace"}
    except (ValueError, OSError, TypeError, KeyError) as error:
        return {"submission_id": submission.id, "passed": False, "errors": [str(error)],
            "automatic_external_submission_performed": False, "guard_scope": "current_workspace"}

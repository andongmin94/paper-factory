"""Validated records. Research, writing and submission identities stay distinct."""

from datetime import datetime, timezone
from enum import StrEnum
import re
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    @field_validator("id", check_fields=False)
    @classmethod
    def safe_id(cls, value: str) -> str:
        device = value.split(".", 1)[0].upper()
        if value.endswith(".") or device in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]} or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
            raise ValueError("Record ID must be a safe portable identifier")
        return value


class Asset(Record):
    path: str
    sha256: str
    size: int
    kind: str


class Project(Record):
    id: str = Field(default_factory=lambda: uid("project"))
    name: str
    source: str
    source_commit: str | None = None
    snapshot_digest: str
    assets: list[Asset]
    imported_at: str = Field(default_factory=now)
    state: Literal["PROJECT_IMPORTED"] = "PROJECT_IMPORTED"


class StudyState(StrEnum):
    STUDY_PLANNED = "STUDY_PLANNED"
    NOVELTY_CHECKED = "NOVELTY_CHECKED"
    EXPERIMENTS_RUNNING = "EXPERIMENTS_RUNNING"
    EVIDENCE_READY = "EVIDENCE_READY"


class Candidate(Record):
    id: str
    title: str
    research_question: str
    why_it_matters: str
    what_is_new: str
    required_evidence: list[str]
    required_experiments: list[str]
    likely_field: str
    estimated_additional_work: str
    existing_related_work: list[str] = Field(default_factory=list)
    incremental_risk: str
    score: int


class Study(Record):
    id: str = Field(default_factory=lambda: uid("study"))
    project_id: str
    title: str
    research_question: str
    domain: Literal["software_engineering", "generic_empirical"] = "generic_empirical"
    state: StudyState = StudyState.STUDY_PLANNED
    novelty_status: Literal["unassessed", "searched", "author_assessed"] = "unassessed"
    literature_search_ids: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=lambda: [
        "Descriptive evidence alone does not establish novelty, causality or generalizability."
    ])
    human_subjects: bool = False
    ethics_approval: str | None = None
    created_at: str = Field(default_factory=now)


class Metric(Record):
    name: str
    output: str
    pointer: str
    unit: str = ""
    description: str

    @field_validator("pointer")
    @classmethod
    def json_pointer(cls, value: str) -> str:
        if value and not value.startswith("/"):
            raise ValueError("Metric pointer must be an RFC 6901 JSON pointer")
        return value


class ExperimentManifest(Record):
    id: str = Field(default_factory=lambda: uid("experiment"))
    study_id: str
    source_commit: str | None = None
    source_digest: str
    command: list[str] = Field(min_length=1)
    environment: dict[str, str] = Field(default_factory=dict)
    inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(min_length=1)
    metrics: list[Metric] = Field(min_length=1)
    seed: int = 0
    timeout_seconds: int = Field(default=120, ge=1, le=86400)
    human_subjects: bool = False
    ethics_approval: str | None = None


class ExperimentRun(Record):
    id: str = Field(default_factory=lambda: uid("run"))
    experiment_id: str
    study_id: str
    source_commit: str | None = None
    source_digest: str
    command: list[str]
    environment: dict[str, str]
    seed: int
    started_at: str = Field(default_factory=now)
    ended_at: str | None = None
    status: Literal["RUNNING", "SUCCEEDED", "FAILED"] = "RUNNING"
    exit_code: int | None = None
    error: str | None = None
    artifacts: list[Asset] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    processed_sha256: str | None = None


class Claim(Record):
    id: str = Field(default_factory=lambda: uid("claim"))
    study_id: str
    run_id: str
    metric_name: str
    value: float
    unit: str
    description: str
    raw_artifact: str
    raw_sha256: str
    pointer: str
    calculation: Literal["identity JSON-pointer extraction"] = "identity JSON-pointer extraction"


class Citation(Record):
    id: str
    doi: str
    title: str
    authors: list[str]
    year: int | None = None
    source_url: str
    verified_at: str
    metadata_sha256: str
    verified: bool = True
    verification_scope: Literal["metadata_only"] = "metadata_only"


class PaperState(StrEnum):
    MANUSCRIPT_DRAFTED = "MANUSCRIPT_DRAFTED"
    INTEGRITY_CHECKED = "INTEGRITY_CHECKED"
    AUTHOR_APPROVED = "AUTHOR_APPROVED"


class Paper(Record):
    id: str = Field(default_factory=lambda: uid("paper"))
    study_id: str
    title: str
    state: PaperState = PaperState.MANUSCRIPT_DRAFTED
    claim_ids: list[str]
    citation_ids: list[str]
    manuscript_sha256: str
    document_sha256: str
    generated_at: str = Field(default_factory=now)
    approved_at: str | None = None
    approved_by: str | None = None
    freeze_digest: str | None = None


class SubmissionState(StrEnum):
    VENUE_SELECTED = "VENUE_SELECTED"
    VENUE_COMPILED = "VENUE_COMPILED"
    SUBMISSION_READY = "SUBMISSION_READY"
    AUTHOR_ATTESTED = "AUTHOR_ATTESTED"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    REVISION = "REVISION"
    WITHDRAWAL_REQUESTED = "WITHDRAWAL_REQUESTED"
    WITHDRAWN_CONFIRMED = "WITHDRAWN_CONFIRMED"
    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"
    PROOF = "PROOF"
    PUBLISHED = "PUBLISHED"


class Submission(Record):
    """One venue-specific candidate and its author-recorded publication history."""
    id: str = Field(default_factory=lambda: uid("submission"))
    paper_id: str
    venue_id: str
    policy_id: str
    candidate_digest: str
    state: SubmissionState = SubmissionState.VENUE_SELECTED
    created_at: str = Field(default_factory=now)
    compilation_digest: str | None = None
    package_digest: str | None = None


def transition_submission(submission: Submission, target: SubmissionState) -> None:
    allowed = {
        SubmissionState.VENUE_SELECTED: {SubmissionState.VENUE_COMPILED},
        SubmissionState.VENUE_COMPILED: {SubmissionState.SUBMISSION_READY},
        SubmissionState.SUBMISSION_READY: {SubmissionState.AUTHOR_ATTESTED},
        SubmissionState.AUTHOR_ATTESTED: {SubmissionState.SUBMISSION_READY, SubmissionState.SUBMITTED},
        SubmissionState.SUBMITTED: {SubmissionState.UNDER_REVIEW, SubmissionState.REVISION, SubmissionState.WITHDRAWAL_REQUESTED, SubmissionState.REJECTED, SubmissionState.ACCEPTED},
        SubmissionState.UNDER_REVIEW: {SubmissionState.REVISION, SubmissionState.WITHDRAWAL_REQUESTED, SubmissionState.REJECTED, SubmissionState.ACCEPTED},
        SubmissionState.REVISION: {SubmissionState.UNDER_REVIEW, SubmissionState.WITHDRAWAL_REQUESTED, SubmissionState.REJECTED, SubmissionState.ACCEPTED},
        SubmissionState.WITHDRAWAL_REQUESTED: {SubmissionState.WITHDRAWN_CONFIRMED, SubmissionState.REJECTED, SubmissionState.ACCEPTED},
        SubmissionState.WITHDRAWN_CONFIRMED: set(),
        SubmissionState.REJECTED: set(),
        SubmissionState.ACCEPTED: {SubmissionState.PROOF, SubmissionState.PUBLISHED},
        SubmissionState.PROOF: {SubmissionState.PUBLISHED},
        SubmissionState.PUBLISHED: set(),
    }
    if target not in allowed[submission.state]:
        raise ValueError(f"Invalid submission transition: {submission.state} -> {target}")
    submission.state = target


class Provenance(Record):
    id: str = Field(default_factory=lambda: uid("activity"))
    role: str
    tool: str
    model: str | None = None
    inputs: list[str]
    outputs: list[str]
    timestamp: str = Field(default_factory=now)
    ai: bool = False


def transition_study(study: Study, target: StudyState) -> None:
    allowed = {
        StudyState.STUDY_PLANNED: {StudyState.NOVELTY_CHECKED, StudyState.EXPERIMENTS_RUNNING},
        StudyState.NOVELTY_CHECKED: {StudyState.EXPERIMENTS_RUNNING},
        StudyState.EXPERIMENTS_RUNNING: {StudyState.EVIDENCE_READY},
        StudyState.EVIDENCE_READY: {StudyState.EXPERIMENTS_RUNNING},
    }
    if target not in allowed[study.state]:
        raise ValueError(f"Invalid study transition: {study.state} -> {target}")
    study.state = target


def transition_paper(paper: Paper, target: PaperState) -> None:
    allowed = {
        PaperState.MANUSCRIPT_DRAFTED: {PaperState.INTEGRITY_CHECKED},
        PaperState.INTEGRITY_CHECKED: {PaperState.AUTHOR_APPROVED, PaperState.MANUSCRIPT_DRAFTED},
        PaperState.AUTHOR_APPROVED: set(),
    }
    if target not in allowed[paper.state]:
        raise ValueError(f"Invalid paper transition: {paper.state} -> {target}")
    paper.state = target

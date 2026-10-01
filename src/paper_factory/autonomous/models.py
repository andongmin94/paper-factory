"""Typed contracts shared by research workers, model adapters and the web UI."""

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from ..models import Record, now, uid


class Budget(Record):
    max_model_calls: int = Field(default=12, ge=1, le=40)
    repair_attempts: int = Field(default=2, ge=0, le=5)
    wall_seconds: int = Field(default=3600, ge=60, le=86400)
    model_timeout_seconds: int = Field(default=600, ge=10, le=3600)
    experiment_timeout_seconds: int = Field(default=300, ge=1, le=3600)


class Measure(Record):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    unit: str = Field(default="", max_length=80)
    description: str = Field(min_length=8, max_length=1000)


class ResearchPlan(Record):
    feasible: bool
    reason: str = Field(min_length=8, max_length=4000)
    title: str = Field(min_length=8, max_length=300)
    question: str = Field(min_length=12, max_length=2000)
    runtime: Literal["python", "node"]
    source_files: list[str] = Field(min_length=1, max_length=20)
    production_entrypoint: str = Field(default="", max_length=300)
    dependencies: list[str] = Field(default_factory=list, max_length=20)
    conditions: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(min_length=2, max_length=6)
    metrics: list[Measure] = Field(min_length=1, max_length=8)
    comparator: str = Field(min_length=12, max_length=3000)
    independent_oracle: str = Field(min_length=12, max_length=3000)
    sampling_unit: str = Field(min_length=8, max_length=1000)
    sample_size: int = Field(ge=3, le=500)
    seeds: list[int] = Field(min_length=2, max_length=20)
    parameters: dict[Annotated[str, Field(min_length=1, max_length=100)], str | int | float] = Field(default_factory=dict)
    procedure: list[str] = Field(min_length=3, max_length=30)
    analysis_method: str = Field(min_length=12, max_length=2000)
    limitations: list[str] = Field(min_length=2, max_length=12)
    literature_queries: list[str] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def distinct_protocol(self):
        for values in (self.conditions, self.seeds, self.source_files, [m.name for m in self.metrics]):
            if len(values) != len(set(values)):
                raise ValueError("Protocol identifiers, conditions, seeds and metrics must be distinct")
        return self


class GeneratedFile(Record):
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=262144)


class CodeBundle(Record):
    runtime: Literal["python", "node"]
    entrypoint: str = Field(min_length=1, max_length=200)
    files: list[GeneratedFile] = Field(min_length=1, max_length=12)
    explanation: str = Field(min_length=12, max_length=5000)

    @model_validator(mode="after")
    def distinct_files(self):
        names = [f.path for f in self.files]
        if len(names) != len(set(names)) or self.entrypoint not in names:
            raise ValueError("Generated bundle requires distinct files and a declared entrypoint")
        if sum(len(f.content.encode("utf-8")) for f in self.files) > 512 * 1024:
            raise ValueError("Generated bundle exceeds 512 KiB")
        return self


class DraftSection(Record):
    heading: str = Field(min_length=3, max_length=100)
    text: str = Field(min_length=40, max_length=30000)


class ManuscriptDraft(Record):
    title: str = Field(min_length=8, max_length=300)
    sections: list[DraftSection] = Field(min_length=10, max_length=14)


class ScientificReview(Record):
    accepted: bool
    issues: list[str] = Field(default_factory=list, max_length=20)
    checks: list[str] = Field(default_factory=list, max_length=20)


class FrozenArtifact(Record):
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size: int = Field(ge=0)


class StageAttempt(Record):
    stage: str
    attempt: int = Field(ge=1)
    started_at: str = Field(default_factory=now)
    ended_at: str | None = None
    status: Literal["running", "completed", "blocked", "failed", "cancelled", "interrupted"] = "running"
    code: str | None = None
    message: str | None = None


class PipelineRun(Record):
    id: str = Field(default_factory=lambda: uid("pipeline"))
    project_id: str
    study_id: str | None = None
    goal: str = Field(min_length=8, max_length=4000)
    model: str | None = Field(default=None, max_length=200)
    budget: Budget = Field(default_factory=Budget)
    status: Literal["queued", "running", "paused", "blocked", "failed", "cancelled", "completed"] = "queued"
    stage: Literal["assess", "plan", "literature", "generate", "execute", "analyze", "write", "export", "verify", "done"] = "assess"
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    started_at: str | None = None
    ended_at: str | None = None
    model_calls: int = Field(default=0, ge=0)
    elapsed_seconds: float = Field(default=0, ge=0)
    code_attempt: int = Field(default=0, ge=0)
    artifacts: dict[str, FrozenArtifact] = Field(default_factory=dict)
    attempts: list[StageAttempt] = Field(default_factory=list)
    active_handle: dict = Field(default_factory=dict)
    cancellation_requested: bool = False
    code: str | None = None
    message: str | None = None

    @field_validator("goal")
    @classmethod
    def valid_goal(cls, value):
        if not value.strip() or "\x00" in value:
            raise ValueError("Research goal must be nonempty text")
        return value.strip()

"""Persisted state for native-assistant research and owned experiment jobs."""

from datetime import datetime
import hashlib
from typing import Literal

from pydantic import Field, model_validator

from .autonomous.models import FrozenArtifact
from .models import Record, now, uid


class ModelEvidenceReceipt(Record):
    """Main-process SDK evidence; no credentials or execution authority."""
    id: str = Field(pattern=r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")
    phase: Literal["source-selection", "plan", "study-review", "redesign-plan", "redesign-review", "code", "code-review", "literature-plan", "evidence-selection", "manuscript", "manuscript-review"]
    at: str = Field(max_length=40)
    model: str = Field(min_length=1, max_length=100)
    profileId: str = Field(min_length=1, max_length=128)
    prompt: str = Field(min_length=1, max_length=700000)
    promptSha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    text: str | None = Field(default=None, max_length=700000)
    textSha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    outcome: Literal["started", "completed", "failed", "interrupted"]
    code: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def verified_receipt(self):
        if datetime.fromisoformat(self.at.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("Inference receipt needs a timezone")
        if hashlib.sha256(self.prompt.encode()).hexdigest() != self.promptSha256:
            raise ValueError("Inference prompt hash differs from its text")
        if (self.text is None) != (self.textSha256 is None):
            raise ValueError("Inference output and hash must be supplied together")
        if self.text is not None and hashlib.sha256(self.text.encode()).hexdigest() != self.textSha256:
            raise ValueError("Inference output hash differs from its text")
        if self.outcome == "completed" and self.text is None:
            raise ValueError("Completed inference receipt needs its original output")
        return self


class Workflow(Record):
    id: str = Field(default_factory=lambda: uid("research"))
    project_id: str
    parent_research_id: str | None = Field(default=None, pattern=r"^research-[a-f0-9]{12}$")
    root_research_id: str | None = Field(default=None, pattern=r"^research-[a-f0-9]{12}$")
    redesign_attempt: int = Field(default=0, ge=0, le=2)
    goal: str = Field(min_length=8, max_length=4000)
    status: Literal["ready", "running", "blocked", "failed", "cancelled", "completed"] = "ready"
    stage: Literal["created", "proposed", "planned", "code_ready", "execute", "analyzed", "manuscript", "exported"] = "created"
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    experiment_timeout_seconds: int = Field(default=300, ge=1, le=300)
    proposal_attempt: int = Field(default=0, ge=0, le=3)
    study_literature_attempt: int = Field(default=0, ge=0, le=3)
    code_attempt: int = Field(default=0, ge=0)
    execution_attempt: int = Field(default=0, ge=0)
    draft_attempt: int = Field(default=0, ge=0)
    artifacts: dict[str, FrozenArtifact] = Field(default_factory=dict)
    active_handle: dict = Field(default_factory=dict)
    cancellation_requested: bool = False
    terminal_control_failure: bool = False
    code: str | None = None
    message: str | None = None

    @model_validator(mode="after")
    def consistent_lineage(self):
        if self.redesign_attempt == 0:
            if self.parent_research_id is not None or self.root_research_id is not None:
                raise ValueError("An original study cannot claim redesign lineage")
        elif (self.parent_research_id is None or self.root_research_id is None or
              self.parent_research_id == self.id or self.root_research_id == self.id or
              (self.redesign_attempt == 1 and self.parent_research_id != self.root_research_id)):
            raise ValueError("A redesigned study requires a distinct parent and root")
        return self

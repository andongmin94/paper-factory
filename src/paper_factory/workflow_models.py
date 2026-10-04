"""Persisted state for native-assistant research and owned experiment jobs."""

from typing import Literal

from pydantic import Field

from .autonomous.models import FrozenArtifact
from .models import Record, now, uid


class Workflow(Record):
    id: str = Field(default_factory=lambda: uid("research"))
    project_id: str
    goal: str = Field(min_length=8, max_length=4000)
    status: Literal["ready", "running", "blocked", "failed", "cancelled", "completed"] = "ready"
    stage: Literal["created", "planned", "code_ready", "execute", "analyzed", "manuscript", "exported"] = "created"
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    experiment_timeout_seconds: int = Field(default=300, ge=1, le=300)
    code_attempt: int = Field(default=0, ge=0)
    execution_attempt: int = Field(default=0, ge=0)
    draft_attempt: int = Field(default=0, ge=0)
    artifacts: dict[str, FrozenArtifact] = Field(default_factory=dict)
    active_handle: dict = Field(default_factory=dict)
    cancellation_requested: bool = False
    terminal_control_failure: bool = False
    code: str | None = None
    message: str | None = None

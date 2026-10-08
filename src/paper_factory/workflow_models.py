"""Persisted state for native-assistant research and owned experiment jobs."""

from datetime import datetime
import hashlib
import re
from typing import Literal

from pydantic import Field, StrictInt, StrictStr, field_validator, model_validator

from .autonomous.models import FrozenArtifact
from .models import Record, now, uid


_REQUEST_PARAM_ROOTS = frozenset({
    "model", "input", "instructions", "store", "stream", "tools", "additional_tools", "tool_choice", "reasoning", "text", "service_tier",
    "background", "conversation", "max_output_tokens", "max_tool_calls", "metadata", "moderation", "multi_agent", "prompt",
    "prompt_cache_retention", "safety_identifier", "temperature", "top_logprobs", "top_p", "truncation", "user", "previous_response_id",
})
_REQUEST_PARAM_FIELDS = frozenset({"type", "role", "content", "text", "name", "description", "parameters", "namespace", "strict", "format", "effort", "summary"})
_SHAPE_FIELDS = frozenset({"error", "detail", "code", "message", "type", "param", "loc", "input", "ctx", "response", "status", "request_id"})
_SHAPE_TYPES = frozenset({"null", "string", "number", "boolean", "undefined", "bigint", "symbol", "function", "object", "array", "redacted"})


def _safe_diagnostic_shape(value: str) -> bool:
    """Validate the desktop's field/type-only response grammar without values."""
    position = 0

    def word():
        nonlocal position
        match = re.match(r"[a-z_]+", value[position:])
        if match is not None:
            position += len(match[0])
            return match[0]
        return None

    def parse(depth: int) -> bool:
        nonlocal position
        if value[position:position + 1] == "{":
            if depth >= 3:
                return False
            position += 1
            if value[position:position + 1] == "}":
                position += 1
                return True
            for _ in range(13):
                field = word()
                if (field is None or (field != "other" and field not in _SHAPE_FIELDS) or
                        value[position:position + 1] != ":"):
                    return False
                position += 1
                if field == "other":
                    count = re.match(r"(?:0|[1-9][0-9]{0,6})", value[position:])
                    if count is None or int(count[0]) > 1_000_000:
                        return False
                    position += len(count[0])
                elif not parse(depth + 1):
                    return False
                if value[position:position + 1] == "}":
                    position += 1
                    return True
                if value[position:position + 1] != ",":
                    return False
                position += 1
            return False
        if value[position:position + 1] == "[":
            if depth >= 3:
                return False
            position += 1
            if value[position:position + 1] == "]":
                position += 1
                return True
            if not parse(depth + 1) or value[position:position + 1] != "]":
                return False
            position += 1
            return True
        return word() in _SHAPE_TYPES

    return parse(0) and position == len(value)


class ModelEvidenceDiagnostics(Record):
    """Bounded HTTP identifiers and response structure, never response values."""
    httpStatus: StrictInt | None = Field(default=None, ge=100, le=599)
    requestId: StrictStr | None = Field(default=None, min_length=1, max_length=160,
                                      pattern=r"^[a-zA-Z0-9_][a-zA-Z0-9_.:\[\]-]*$")
    param: StrictStr | None = Field(default=None, min_length=1, max_length=160)
    responseShape: StrictStr | None = Field(default=None, min_length=1, max_length=2048)

    @model_validator(mode="before")
    @classmethod
    def nonempty_fields(cls, value):
        if not isinstance(value, dict) or not value or any(item is None for item in value.values()):
            raise ValueError("Diagnostics require nonempty, non-null fields")
        return value

    @field_validator("param")
    @classmethod
    def safe_param(cls, value):
        if not re.fullmatch(r"[a-z][a-z0-9_]*(?:\[[0-9]{1,5}\]|\.[a-z][a-z0-9_]*)*", value):
            raise ValueError("Diagnostics parameter must be an allowlisted field path")
        fields = re.findall(r"[a-z][a-z0-9_]*", value)
        if fields[0] not in _REQUEST_PARAM_ROOTS or any(field not in _REQUEST_PARAM_FIELDS for field in fields[1:]):
            raise ValueError("Diagnostics parameter must be an allowlisted field path")
        return value

    @field_validator("responseShape")
    @classmethod
    def safe_shape(cls, value):
        if not _safe_diagnostic_shape(value):
            raise ValueError("Diagnostics response shape must contain only allowlisted fields and types")
        return value


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
    diagnostics: ModelEvidenceDiagnostics | None = None

    @field_validator("diagnostics", mode="before")
    @classmethod
    def supplied_diagnostics(cls, value):
        if value is None:
            raise ValueError("Supplied diagnostics must be a nonempty object")
        return value

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
        if self.diagnostics is not None and self.outcome not in {"failed", "interrupted"}:
            raise ValueError("Diagnostics may accompany only failed or interrupted inference")
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

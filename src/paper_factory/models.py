"""Validated core records for frozen research source snapshots."""

from datetime import datetime, timezone
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

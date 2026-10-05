"""Bounded input and evidence checks shared by the QuickJS controller."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import stat

from ..workspace import ensure_unlinked, is_link, loads_json


MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_LOG_BYTES = 256 * 1024
MAX_INPUT_BYTES = 256 * 1024 * 1024
MAX_INPUT_FILES = 20_000
MAX_PRODUCTION_FUNCTIONS = 512


def _safe_tree(path: Path, label: str) -> Path:
    ensure_unlinked(path)
    if is_link(path) or not path.is_dir():
        raise ValueError(f"{label} must be a real directory")
    resolved = path.resolve()
    count = total = 0
    for parent, directories, files in os.walk(resolved, followlinks=False):
        for name in directories + files:
            item = Path(parent) / name
            info = item.lstat()
            if is_link(item) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError(f"{label} must not contain links or special files")
            if stat.S_ISREG(info.st_mode):
                count += 1
                total += info.st_size
                if count > MAX_INPUT_FILES or total > MAX_INPUT_BYTES:
                    raise ValueError(f"{label} exceeds sandbox input limits")
    return resolved


def _retain_observations(output: Path, data: bytes) -> dict:
    """Retain exact bounded JSON bytes without changing the execution status."""
    if not data or len(data) > MAX_ARTIFACT_BYTES:
        raise ValueError("observation is empty or exceeds size limit")
    loads_json(data.decode("utf-8"))
    path = output / "observations.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
    return {"output_path": str(path), "artifacts": [{"path": "observations.json", "size": len(data),
                                                    "sha256": hashlib.sha256(data).hexdigest()}]}


def _production_calls(value: object, source: Path) -> list[dict]:
    if not isinstance(value, list) or len(value) > MAX_PRODUCTION_FUNCTIONS:
        raise ValueError("invalid production execution receipt")
    normalized = []
    identities = set()
    for record in value:
        if not isinstance(record, dict):
            raise ValueError("invalid production execution record")
        path, function, calls = (record.get(key) for key in ("path", "function", "calls"))
        if not isinstance(path, str) or len(path) > 256 or not isinstance(function, str) or not 1 <= len(function) <= 128:
            raise ValueError("invalid production execution identity")
        relative = PurePosixPath(path)
        if (relative.is_absolute() or ".." in relative.parts or "\\" in path or not relative.parts
                or relative.as_posix() != path or any(ord(character) < 32 for character in path + function)
                or function == "<module>"):
            raise ValueError("production receipt escapes the source snapshot")
        if not source.joinpath(*relative.parts).is_file():
            raise ValueError("production receipt does not identify a source snapshot file")
        if isinstance(calls, bool) or not isinstance(calls, int) or not 1 <= calls <= 1_000_000_000:
            raise ValueError("invalid production execution count")
        if (path, function) in identities:
            raise ValueError("duplicate production execution record")
        identities.add((path, function))
        normalized.append({"path": path, "function": function, "calls": calls})
    return normalized

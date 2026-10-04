"""macOS liveness guardian and nonce-bound cleanup receipts, without PID kills."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time

from ..workspace import ensure_unlinked

GUARDIAN = Path(__file__).with_name("quickjs_guardian.py")


def identity(supervisor_root: Path, nonce: str, node: Path, worker_sha256: str) -> dict:
    ensure_unlinked(GUARDIAN)
    return {"guardian_sha256": hashlib.sha256(GUARDIAN.read_bytes()).hexdigest(),
            "guardian_receipt": str(supervisor_root / ("guardian-" + nonce + ".json")),
            "worker_sha256": worker_sha256, "node_path": str(node), "owner_uid": os.getuid()}


def _read_receipt(path: Path) -> dict:
    ensure_unlinked(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_size > 8192):
            raise ValueError("Guardian receipt is not a bounded private ordinary file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return json.loads(stream.read(8193))
    finally:
        os.close(descriptor)


def completed(supervisor_root: Path, handle: dict, expected: dict) -> bool:
    if (not re.fullmatch(r"[a-f0-9]{32}", str(handle.get("owner_nonce", "")))
            or any(handle.get(key) != value for key, value in expected.items())):
        return False
    path = supervisor_root / ("guardian-" + handle["owner_nonce"] + ".json")
    try:
        result = _read_receipt(path)
        return (isinstance(result, dict) and result.get("format") == "paper-factory-quickjs-guardian-v1"
                and result.get("owner_nonce") == handle["owner_nonce"]
                and all(result.get(key) == expected[key] for key in
                        ("guardian_sha256", "worker_sha256", "node_path", "owner_uid"))
                and type(result.get("guardian_pid")) is int and result["guardian_pid"] > 0
                and (handle.get("pid") == 0 or result["guardian_pid"] == handle.get("pid"))
                and result.get("cleanup_confirmed") is True
                and type(result.get("worker_pid")) is int and result["worker_pid"] >= 0
                and ((result["worker_pid"] == 0 and result.get("worker_exit_code") is None)
                     or (result["worker_pid"] > 0 and type(result.get("worker_exit_code")) is int)))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def recover(supervisor_root: Path, handle: dict, expected: dict) -> bool:
    # Acquiring the controller lease proves the original owner released or lost
    # its endpoint. Its guardian observes EOF and reaps the actual child. Missing
    # or malformed completion evidence is unresolved, never an absent-PID guess.
    if any(handle.get(key) != value for key, value in expected.items()):
        return False
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if completed(supervisor_root, handle, expected):
            return True
        time.sleep(0.02)
    return False


class Guardian:
    def __init__(self):
        self.control, self.child_endpoint = socket.socketpair()

    def spawn(self, node: Path, worker: Path, runtime_root: Path, environment: dict, handle: dict):
        command = [str(Path(sys.executable).resolve()), "-B", str(GUARDIAN),
                   "--control-fd", str(self.child_endpoint.fileno()),
                   "--receipt", handle["guardian_receipt"], "--nonce", handle["owner_nonce"],
                   "--worker-sha256", handle["worker_sha256"], "--", str(node),
                   "--max-old-space-size=128", str(worker), str(runtime_root)]
        try:
            return subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env={**environment, "PYTHONDONTWRITEBYTECODE": "1"},
                                    close_fds=True, pass_fds=(self.child_endpoint.fileno(),))
        finally:
            self.child_endpoint.close()

    def close(self):
        self.control.close()
        self.child_endpoint.close()

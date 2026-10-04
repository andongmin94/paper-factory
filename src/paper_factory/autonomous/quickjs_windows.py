"""Owned Windows jobs for the trusted QuickJS embedder, without native guests."""
from __future__ import annotations

import re
import time

from . import windows_runtime


def create(nonce: str):
    # Non-inheritable, user-private job. Controller death closes the last handle
    # and the kernel terminates every process assigned to this job.
    return windows_runtime.WindowsJob(name="Local\\paper-factory-codex-" + nonce)


def attach(job, process) -> dict:
    job.assign(process._handle)
    ticks = windows_runtime.process_ticks(process.pid)
    if type(ticks) is not int or ticks <= 0:
        raise ValueError("Owned Windows worker creation time is unavailable")
    return {"job_name": job.name, "start_ticks": ticks}


def valid(handle: dict) -> bool:
    return (handle.get("job_name") == "Local\\paper-factory-codex-" + handle["owner_nonce"]
            and type(handle.get("start_ticks")) is int and handle["start_ticks"] > 0
            and isinstance(handle.get("node_path"), str) and bool(handle["node_path"])
            and bool(re.fullmatch(r"[a-f0-9]{64}", str(handle.get("worker_sha256", "")))))


def recover(handle: dict) -> bool:
    if not valid(handle):
        return False
    # Termination addresses the private kernel job, never a recovered bare PID.
    # If the job is gone, Windows' creation-time check proves the old worker is
    # absent without signalling a potentially reused PID.
    # KILL_ON_JOB_CLOSE is asynchronous. After controller death, the job name
    # can disappear before its terminating worker's process handle is signalled.
    # Wait for that original creation time to disappear; never signal its PID.
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if windows_runtime.stop(handle):
            return True
        time.sleep(0.02)
    return False

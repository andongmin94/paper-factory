"""Windows Job Object limits and identity checks for trusted workers."""
import ctypes
import os
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from paper_factory.autonomous.windows_runtime import WindowsJob
from paper_factory.autonomous import windows_runtime


@pytest.mark.parametrize("change", [
    {"job_name": "unowned"}, {"pid": True}, {"pid": 1}, {"start_ticks": True}, {"start_ticks": 0},
])
def test_invalid_identity_never_opens_a_job(monkeypatch, change):
    handle = {"job_name": "Local\\paper-factory-codex-" + "a" * 32, "pid": 12345, "start_ticks": 10, **change}
    monkeypatch.setattr(windows_runtime, "_api", lambda: pytest.fail("Invalid ownership queried native jobs"))
    assert windows_runtime.stop(handle) is False


@pytest.mark.parametrize("current,expected", [(None, True), (11, True), (10, False)])
def test_absent_job_requires_absent_or_distinct_process_identity(monkeypatch, current, expected):
    api = SimpleNamespace(OpenJobObjectW=lambda *_args: 0)
    monkeypatch.setattr(windows_runtime, "_api", lambda: (api, None))
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 2, raising=False)
    monkeypatch.setattr(windows_runtime, "process_ticks", lambda pid: current)
    handle = {"job_name": "Local\\paper-factory-codex-" + "a" * 32, "pid": 12345, "start_ticks": 10}
    assert windows_runtime.stop(handle) is expected


def test_absent_job_does_not_claim_cleanup_when_process_identity_is_inaccessible(monkeypatch):
    api = SimpleNamespace(OpenJobObjectW=lambda *_args: 0)
    monkeypatch.setattr(windows_runtime, "_api", lambda: (api, None))
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 2, raising=False)
    def inaccessible(pid):
        raise OSError("Synthetic process identity access denial")
    monkeypatch.setattr(windows_runtime, "process_ticks", inaccessible)
    handle = {"job_name": "Local\\paper-factory-codex-" + "a" * 32, "pid": 12345, "start_ticks": 10}
    assert windows_runtime.stop(handle) is False


def test_owned_job_is_closed_even_when_cleanup_fails(monkeypatch):
    closed = []
    api = SimpleNamespace(OpenJobObjectW=lambda *_args: 99, CloseHandle=closed.append)
    monkeypatch.setattr(windows_runtime, "_api", lambda: (api, None))
    monkeypatch.setattr(windows_runtime, "_stop_job", lambda handle: False)
    monkeypatch.setattr(windows_runtime, "process_ticks", lambda pid: pytest.fail("Opened job does not need leader identity"))
    handle = {"job_name": "Local\\paper-factory-codex-" + "a" * 32, "pid": 12345, "start_ticks": 10}
    assert windows_runtime.stop(handle) is False
    assert closed == [99]


@pytest.mark.skipif(os.name != "nt", reason="Windows CPU deadline requires a native Job Object")
def test_native_job_stops_cpu_bound_parser():
    from pathlib import Path
    import subprocess
    import sys
    import time

    job = WindowsJob(limits={"memory_bytes": 512 * 1024 * 1024, "pids": 1, "cpu_seconds": 1})
    process = None
    try:
        started = time.monotonic()
        process = subprocess.Popen([str(Path(sys.base_prefix) / "python.exe"), "-I", "-c", "while True: pass"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        job.assign(process._handle)
        assert process.wait(timeout=15) != 0
        assert time.monotonic() - started >= 1
        assert job.stop()
    finally:
        job.close()
        if process is not None:
            process.wait(timeout=5)


@pytest.mark.skipif(os.name != "nt", reason="Windows owned-job cleanup regression")
def test_owned_job_cleanup_does_not_require_opening_its_leader(monkeypatch):
    import subprocess
    native = windows_runtime
    job = native.WindowsJob()
    process = subprocess.Popen([str(Path(sys.base_prefix) / "python.exe"), "-I", "-c", "import time; time.sleep(60)"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        job.assign(process._handle)
        handle = {"job_name": job.name, "pid": process.pid, "start_ticks": native.process_ticks(process.pid)}
        monkeypatch.setattr(native, "process_ticks", lambda pid: pytest.fail("Owned job cleanup queried an unrelated leader handle"))
        assert native.stop(handle)
        assert process.wait(timeout=5) is not None
    finally:
        job.close()
        process.wait(timeout=5)

"""Portable checks for untrusted native-worker log ingestion."""
import os
from pathlib import Path
import shutil
import sys

import pytest

from paper_factory.autonomous.windows_runtime import MAX_LOG_BYTES, WindowsJob, _log_text
from paper_factory.autonomous import windows_runtime


def test_log_reader_bounds_output_and_rejects_hardlinks(tmp_path):
    log = tmp_path / "worker.log"
    log.write_bytes(b"a" * (MAX_LOG_BYTES + 1))
    assert len(_log_text(log)) == MAX_LOG_BYTES
    os.link(log, tmp_path / "linked.log")
    with pytest.raises(ValueError, match="one link"):
        _log_text(log)


def test_log_reader_rejects_file_replacement_after_open(tmp_path, monkeypatch):
    log = tmp_path / "worker.log"
    replacement = tmp_path / "replacement.log"
    log.write_bytes(b"original")
    replacement.write_bytes(b"replacement")
    open_file = os.open
    monkeypatch.setattr(os, "open", lambda _path, flags: open_file(replacement, flags))
    with pytest.raises(ValueError, match="unchanged"):
        _log_text(log)


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


@pytest.mark.skipif(os.name != "nt", reason="Windows suspended-process cleanup regression")
@pytest.mark.parametrize("confirmed", [True, False])
def test_unassigned_process_requires_confirmed_direct_termination(native_suspended_runtime, monkeypatch, confirmed):
    import ctypes
    tmp_path, runtime, work = native_suspended_runtime
    native = windows_runtime
    kernel, advapi, userenv = native._api()
    original_job = native.WindowsJob
    pids = []
    receipt = None

    class TerminationOutcome:
        def __getattr__(self, name):
            return getattr(kernel, name)

        def CreateProcessW(self, *arguments):
            result = kernel.CreateProcessW(*arguments)
            if result:
                pids.append(ctypes.cast(arguments[-1], ctypes.POINTER(native.PROCESS_INFORMATION)).contents.pid)
            return result

        def TerminateProcess(self, handle, code):
            return kernel.TerminateProcess(handle, code) if confirmed else 0

        def WaitForSingleObject(self, handle, timeout):
            return kernel.WaitForSingleObject(handle, timeout) if confirmed else 0x102

    class UnassignedJob(original_job):
        def assign(self, handle):
            raise OSError("Synthetic Windows job assignment failure")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(native, "_api", lambda: (TerminationOutcome(), advapi, userenv))
            patch.setattr(native, "WindowsJob", UnassignedJob)
            receipt = native.launch([str(runtime / "python.exe"), "-I", "-c", "pass"], cwd=work,
                environment=suspended_environment(runtime, work), read_only_paths=[tmp_path, runtime], writable_paths=[work], timeout_seconds=1)
        assert len(pids) == 1
        assert receipt["handle"]["pid"] == pids[0]
        assert receipt["cleanup_confirmed"] is confirmed
        assert (native.process_ticks(pids[0]) is None) is confirmed
        if confirmed:
            assert receipt["status"] == "failed"
        else:
            assert receipt["status"] == "blocked" and receipt["code"] == "CLEANUP_UNCONFIRMED"
    finally:
        for pid in pids:
            handle = kernel.OpenProcess(0x100001, False, pid)
            if handle:
                try:
                    kernel.TerminateProcess(handle, 1)
                    assert kernel.WaitForSingleObject(handle, 5000) == 0
                finally:
                    kernel.CloseHandle(handle)
        if receipt is not None and not confirmed:
            assert native.stop(receipt["handle"])


@pytest.fixture
def native_suspended_runtime(tmp_path):
    runtime, work = tmp_path / "runtime", tmp_path / "work"
    runtime.mkdir()
    work.mkdir()
    for name in ("python.exe", "python3.dll", f"python{sys.version_info.major}{sys.version_info.minor}.dll",
                 "vcruntime140.dll", "vcruntime140_1.dll"):
        source = Path(sys.base_prefix) / name
        if source.exists():
            shutil.copyfile(source, runtime / name)
    windows_runtime.private_path(tmp_path)
    return tmp_path, runtime, work


def suspended_environment(runtime, work):
    return {"SystemRoot": os.environ["SystemRoot"], "WINDIR": os.environ["SystemRoot"],
            "USERPROFILE": str(work), "APPDATA": str(work), "LOCALAPPDATA": str(work),
            "TEMP": str(work), "TMP": str(work), "PATH": str(runtime)}


@pytest.mark.skipif(os.name != "nt", reason="Windows callback failure cleanup regression")
def test_native_callback_exception_returns_cleanup_receipt(native_suspended_runtime):
    tmp_path, runtime, work = native_suspended_runtime
    handles = []
    def refused(handle):
        handles.append(handle)
        raise RuntimeError("Synthetic durable callback failure")
    receipt = windows_runtime.launch([str(runtime / "python.exe"), "-I", "-c", "pass"], cwd=work,
        environment=suspended_environment(runtime, work), read_only_paths=[tmp_path, runtime],
        writable_paths=[work], timeout_seconds=1, on_handle=refused)
    assert receipt["status"] == "failed" and receipt["cleanup_confirmed"] is True
    assert receipt["handle"] == handles[0]
    assert windows_runtime.process_ticks(handles[0]["pid"]) is None


@pytest.mark.skipif(os.name != "nt", reason="Windows attribute-list initialization failure regression")
def test_failed_attribute_initialization_never_deletes_uninitialized_list(native_suspended_runtime, monkeypatch):
    import ctypes
    tmp_path, runtime, work = native_suspended_runtime
    native = windows_runtime
    kernel, advapi, userenv = native._api()
    opened, closed = [], []
    class FailedInitialization:
        def __getattr__(self, name):
            return getattr(kernel, name)
        def InitializeProcThreadAttributeList(self, attributes, *arguments):
            if attributes is None:
                return kernel.InitializeProcThreadAttributeList(attributes, *arguments)
            ctypes.set_last_error(8)  # ERROR_NOT_ENOUGH_MEMORY
            return 0
        def DeleteProcThreadAttributeList(self, attributes):
            pytest.fail("An uninitialized native attribute list was deleted")
        def CreateProcessW(self, *arguments):
            pytest.fail("A process was created without initialized launch attributes")
        def CreateFileW(self, *arguments):
            handle = kernel.CreateFileW(*arguments)
            opened.append(handle)
            return handle
        def CloseHandle(self, handle):
            closed.append(handle)
            return kernel.CloseHandle(handle)
    monkeypatch.setattr(native, "_api", lambda: (FailedInitialization(), advapi, userenv))
    receipt = native.launch([str(runtime / "python.exe"), "-I", "-c", "pass"], cwd=work,
        environment=suspended_environment(runtime, work), read_only_paths=[tmp_path, runtime],
        writable_paths=[work], timeout_seconds=1)
    assert receipt["status"] == "failed" and receipt["cleanup_confirmed"] is True
    assert "handle" not in receipt
    assert len(opened) == 3 and set(opened).issubset(closed)


@pytest.mark.skipif(os.name != "nt", reason="Windows initial thread ownership regression")
def test_resume_refuses_a_reused_thread_owner(tmp_path, monkeypatch):
    import subprocess
    native = windows_runtime
    kernel, advapi, userenv = native._api()
    marker = tmp_path / "started.txt"
    program = "from pathlib import Path;Path(" + repr(str(marker)) + ").write_text('started')"
    process = subprocess.Popen([str(Path(sys.base_prefix) / "python.exe"), "-I", "-c", program],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW | 0x4)
    class ReusedOwner:
        def __getattr__(self, name):
            return getattr(kernel, name)
        def GetProcessIdOfThread(self, handle):
            return process.pid + 1
        def ResumeThread(self, handle):
            pytest.fail("A thread belonging to another process was resumed")
    try:
        monkeypatch.setattr(native, "_api", lambda: (ReusedOwner(), advapi, userenv))
        with pytest.raises(OSError, match="no longer belongs"):
            native.resume_process(process.pid)
        assert not marker.exists() and process.poll() is None
    finally:
        process.kill()
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


@pytest.mark.skipif(os.name != "nt", reason="Windows uncertain-process cleanup regression")
def test_absent_job_requires_accessible_process_identity(monkeypatch):
    from uuid import uuid4
    def inaccessible(pid):
        raise OSError("Synthetic process identity access denial")
    monkeypatch.setattr(windows_runtime, "process_ticks", inaccessible)
    handle = {"job_name": "Local\\paper-factory-codex-" + uuid4().hex, "pid": 12345, "start_ticks": 10}
    assert windows_runtime.stop(handle) is False

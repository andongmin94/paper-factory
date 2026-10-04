"""Actual Windows owned-job checks and explicitly simulated macOS API checks."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from paper_factory.autonomous import quickjs_guardian as guardian
from paper_factory.autonomous import quickjs_macos as mac
from paper_factory.autonomous import quickjs_windows as windows
from paper_factory.autonomous.quickjs_runner import QuickJSRunner, WORKER
from paper_factory.autonomous.windows_runtime import process_ticks
from test_quickjs_runner import pinned_runtime, supervisor_root, runner, inputs, run, experiment, envelope


@pytest.mark.skipif(os.name != "nt", reason="Actual Windows kernel job test")
def test_windows_handle_is_owned_job_before_guest_input(runner, inputs):
    captured = []

    def on_handle(handle):
        entry = runner._active[handle["owner_nonce"]]
        assert entry["job"].name == handle["job_name"]
        assert process_ticks(handle["pid"]) == handle["start_ticks"]
        assert handle["worker_sha256"] == hashlib.sha256(WORKER.read_bytes()).hexdigest()
        captured.append(handle)

    result = run(runner, inputs, experiment("const value=JSON.parse(callProduction('[41]'));" + envelope()),
                 on_handle=on_handle)
    assert result["status"] == "succeeded" and result["cleanup_confirmed"] is True
    assert len(captured) == 1 and runner._active == {}
    assert runner.stop(captured[0]) is True  # named job is gone; original creation time is gone


@pytest.mark.skipif(os.name != "nt", reason="Actual Windows kernel controller-crash cleanup")
def test_windows_controller_crash_closes_job_and_recovery_confirms_exit(pinned_runtime, tmp_path):
    state, handle_file = tmp_path / "owner", tmp_path / "handle.json"
    program = r'''
import hashlib,json,sys
from pathlib import Path
from paper_factory.autonomous.quickjs_runner import QuickJSRunner
runtime, state, output = map(Path,sys.argv[1:])
source='module.exports={calculate(x){return x+1}};'
code='export default function run(){while(true){}}'
request={'source_files':{'source.cjs':{'text':source,'sha256':hashlib.sha256(source.encode()).hexdigest()}},
'experiment_files':{'test.mjs':{'text':code,'sha256':hashlib.sha256(code.encode()).hexdigest()}},
'entrypoint':'test.mjs','production_entrypoint':'source.cjs:calculate','timeout_seconds':300}
runner=QuickJSRunner(runtime,supervisor_root=state)
node,_=runner._runtime()
runner._execute(node,request,on_handle=lambda handle: output.write_text(json.dumps(handle)))
'''
    owner = subprocess.Popen([sys.executable, "-B", "-c", program, str(pinned_runtime), str(state), str(handle_file)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                             creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline = time.monotonic() + 10
        while not handle_file.exists() and owner.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert handle_file.exists(), owner.communicate(timeout=1)
        handle = json.loads(handle_file.read_bytes())
        assert process_ticks(handle["pid"]) == handle["start_ticks"]
        time.sleep(0.2)
        owner.kill()  # exact retained Popen of this test's controller
        owner.wait(timeout=5)
        fresh = QuickJSRunner(pinned_runtime, supervisor_root=state)
        assert fresh._records[handle["owner_nonce"]]["handle"] == handle
        # Windows can publish controller exit before its kernel releases all
        # file locks. Until that release the new owner must remain fail-closed.
        deadline = time.monotonic() + 5
        confirmed = False
        while not confirmed and time.monotonic() < deadline:
            confirmed = fresh.stop(handle)
            if not confirmed:
                time.sleep(0.02)
        assert confirmed is True
        assert process_ticks(handle["pid"]) != handle["start_ticks"]
        assert json.loads(fresh._journal_path.read_bytes())["workers"] == []
        fresh.close()
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=5)
        for pipe in (owner.stdout, owner.stderr):
            pipe.close()


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual macOS guardian and child ownership test")
def test_macos_guardian_normal_guest_has_actual_bound_completion(runner, inputs):
    captured = []

    def on_handle(handle):
        entry = runner._active[handle["owner_nonce"]]
        assert entry["guardian"] is not None and entry["process"].pid == handle["pid"]
        assert entry["guardian"].control.fileno() >= 0
        captured.append(handle)

    result = run(runner, inputs, experiment("const value=JSON.parse(callProduction('[41]'));" + envelope()),
                 on_handle=on_handle)
    assert result["status"] == "succeeded" and result["cleanup_confirmed"] is True
    assert result["production_calls"] == [{"path": "source.js", "function": "calculate", "calls": 1}]
    handle = captured[0]
    completion = mac._read_receipt(Path(handle["guardian_receipt"]))
    assert completion["guardian_pid"] == handle["pid"]
    assert completion["worker_pid"] > 0 and completion["worker_pid"] != handle["pid"]
    assert completion["worker_exit_code"] == 0 and completion["cleanup_confirmed"] is True
    receipt = json.loads((inputs[2] / "runtime-manifest.json").read_bytes())
    assert receipt["guardian_parent_monitoring"] is True
    assert receipt["supervision"]["mechanism"] == "macos-liveness-guardian"
    assert runner._active == {} and runner._records == {}


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual macOS controller-crash EOF cleanup and recovery")
def test_macos_controller_crash_eof_reaps_owned_worker_and_recovers(pinned_runtime, tmp_path):
    state, handle_file = tmp_path / "mac-owner", tmp_path / "mac-handle.json"
    program = r'''
import hashlib,json,sys
from pathlib import Path
from paper_factory.autonomous.quickjs_runner import QuickJSRunner
runtime,state,output=map(Path,sys.argv[1:])
source='module.exports={calculate(x){return x+1}};'
code='export default function run(){while(true){}}'
request={'source_files':{'source.cjs':{'text':source,'sha256':hashlib.sha256(source.encode()).hexdigest()}},
'experiment_files':{'test.mjs':{'text':code,'sha256':hashlib.sha256(code.encode()).hexdigest()}},
'entrypoint':'test.mjs','production_entrypoint':'source.cjs:calculate','timeout_seconds':300}
runner=QuickJSRunner(runtime,supervisor_root=state)
node,_=runner._runtime()
runner._execute(node,request,on_handle=lambda h:output.write_text(json.dumps(h)))
'''
    owner = subprocess.Popen([sys.executable, "-B", "-c", program, str(pinned_runtime), str(state), str(handle_file)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    try:
        deadline = time.monotonic() + 10
        while not handle_file.exists() and owner.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert handle_file.exists(), owner.communicate(timeout=1)
        handle = json.loads(handle_file.read_bytes())
        time.sleep(0.2)
        owner.kill()  # Only this retained test-controller Popen, never a recovered PID.
        owner.wait(timeout=5)
        fresh = QuickJSRunner(pinned_runtime, supervisor_root=state)
        try:
            assert fresh._records[handle["owner_nonce"]]["handle"] == handle
            assert fresh.stop(handle) is True
            completion = mac._read_receipt(Path(handle["guardian_receipt"]))
            assert completion["guardian_pid"] == handle["pid"]
            assert completion["worker_pid"] > 0 and completion["worker_pid"] != handle["pid"]
            assert completion["worker_exit_code"] == -signal.SIGKILL
            assert completion["cleanup_confirmed"] is True
            assert json.loads(fresh._journal_path.read_bytes())["workers"] == []
        finally:
            fresh.close()
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=5)
        for pipe in (owner.stdout, owner.stderr):
            pipe.close()


def test_windows_foreign_job_nonce_is_rejected_without_kernel_stop(monkeypatch):
    monkeypatch.setattr(windows.windows_runtime, "stop", lambda _handle: pytest.fail("Foreign job must not be touched"))
    assert windows.recover({"owner_nonce": "a" * 32, "job_name": "Local\\paper-factory-codex-" + "b" * 32,
                            "pid": 42, "start_ticks": 123}) is False


@pytest.fixture
def mac_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(mac.os, "getuid", lambda: 501, raising=False)
    expected = mac.identity(tmp_path, "a" * 32, Path("trusted-node"), "b" * 64)
    handle = {"kind": "quickjs-worker", "pid": 42, "owner_nonce": "a" * 32, **expected}
    result = {"format": "paper-factory-quickjs-guardian-v1", "owner_nonce": "a" * 32,
              "guardian_pid": 42, "worker_pid": 43, "worker_exit_code": -9, "cleanup_confirmed": True,
              **{key: expected[key] for key in ("guardian_sha256", "worker_sha256", "node_path", "owner_uid")}}
    return tmp_path, handle, expected, result


def test_macos_recovery_requires_actual_bound_cleanup_receipt(mac_identity, monkeypatch):
    root, handle, expected, result = mac_identity
    monkeypatch.setattr(mac, "_read_receipt", lambda path: result)
    assert mac.completed(root, handle, expected) is True
    assert mac.recover(root, handle, expected) is True


@pytest.mark.parametrize("field,value", [("owner_nonce", "c" * 32), ("guardian_pid", 99),
    ("cleanup_confirmed", False), ("worker_exit_code", None), ("worker_pid", -1),
    ("guardian_sha256", "d" * 64), ("worker_sha256", "e" * 64), ("node_path", "foreign-node"),
    ("owner_uid", 502)])
def test_macos_foreign_or_incomplete_receipt_never_confirms_cleanup(mac_identity, monkeypatch, field, value):
    root, handle, expected, result = mac_identity
    monkeypatch.setattr(mac, "_read_receipt", lambda path: {**result, field: value})
    assert mac.completed(root, handle, expected) is False


def test_macos_starting_marker_uses_receipt_not_guessed_pid(mac_identity, monkeypatch):
    root, handle, expected, result = mac_identity
    monkeypatch.setattr(mac, "_read_receipt", lambda path: result)
    assert mac.completed(root, {**handle, "pid": 0}, expected) is True
    monkeypatch.setattr(mac, "_read_receipt", lambda path: (_ for _ in ()).throw(FileNotFoundError()))
    assert mac.completed(root, {**handle, "pid": 0}, expected) is False


@pytest.fixture
def guardian_api(monkeypatch):
    calls = []
    monkeypatch.setattr(guardian, "signal", SimpleNamespace(SIGCHLD=17, SIG_DFL=0, SIGTERM=15, SIGINT=2,
                        getsignal=lambda _sig: 0, signal=lambda *_args: None))
    monkeypatch.setattr(guardian, "sys", SimpleNamespace(stdin=SimpleNamespace(buffer=object()),
                        stdout=SimpleNamespace(buffer=object()), stderr=SimpleNamespace(buffer=object())))

    class Child:
        pid, returncode = 77, None
        def poll(self):
            return self.returncode
        def kill(self):
            calls.append("owned-child-kill")
            self.returncode = -9
        def wait(self, timeout):
            calls.append("owned-child-wait")
            return self.returncode

    child = Child()
    monkeypatch.setattr(guardian.subprocess, "Popen", lambda command, **options:
                        calls.append({"command": command, "options": options}) or child)
    return calls, child


def test_macos_guardian_parent_crash_kills_and_reaps_owned_child(guardian_api, monkeypatch):
    calls, child = guardian_api
    checks = iter([[], ["control"]])
    monkeypatch.setattr(guardian.select, "select", lambda *_args: (next(checks), [], []))
    control = SimpleNamespace(recv=lambda *_args: b"")
    completion = {}
    assert guardian.supervise(["trusted-node"], control, completion) == 137
    assert calls[-2:] == ["owned-child-kill", "owned-child-wait"]
    assert calls[0]["options"]["close_fds"] is True
    assert calls[0]["options"]["env"]["PF_QUICKJS_GUARDIAN"] == str(os.getpid())
    assert completion["worker_pid"] == 77 and completion["worker_exit_code"] == -9
    assert completion["cleanup_confirmed"] is True


def test_macos_guardian_already_dead_parent_never_spawns_node(guardian_api, monkeypatch):
    calls, child = guardian_api
    monkeypatch.setattr(guardian.select, "select", lambda *_args: (["control"], [], []))
    completion = {}
    assert guardian.supervise(["trusted-node"], SimpleNamespace(recv=lambda *_args: b""), completion) == 1
    assert calls == [] and completion["worker_pid"] == 0 and completion["cleanup_confirmed"] is True


def test_macos_guardian_unconfirmed_child_wait_preserves_failure(guardian_api, monkeypatch):
    calls, child = guardian_api
    checks = iter([[], ["control"]])
    monkeypatch.setattr(guardian.select, "select", lambda *_args: (next(checks), [], []))
    child.kill = lambda: calls.append("owned-child-kill")
    child.wait = lambda timeout: (_ for _ in ()).throw(subprocess.TimeoutExpired("owned-child", timeout))
    completion = {}
    with pytest.raises(subprocess.TimeoutExpired):
        guardian.supervise(["trusted-node"], SimpleNamespace(recv=lambda *_args: b""), completion)
    assert completion["cleanup_confirmed"] is False

"""Labelled controller routing controls, without Chromium or account access."""

from types import SimpleNamespace
import base64
import hashlib
import json
import os

import pytest

from paper_factory import ipc
from paper_factory.standalone_runtime import ResearchRunners
from paper_factory import standalone_runtime
from paper_factory.autonomous import browser_runner


class Runner:
    def __init__(self, name, *, ready=True, cleaned=True):
        self.name, self.ready, self.cleaned = name, ready, cleaned
        self.calls = []
        self.error = None

    def status(self):
        return {"ready": self.ready, "runtimes": [self.name] if self.ready else [],
                "backend": self.name, "declared_limits": {"profile": self.name},
                "versions": {"engine": self.name}, "cleanup_confirmed": self.cleaned}

    def run(self, *args, **kwargs):
        self.calls.append(("run", args, kwargs))
        if not self.ready:
            raise ValueError("Synthetic selected profile is unavailable")
        return {"runtime": self.name}

    def stop(self, handle):
        self.calls.append(("stop", handle))
        return True

    def close(self, *, deadline=None):
        self.calls.append(("close", deadline))
        if self.error:
            raise self.error


def test_unavailable_chromium_cannot_fall_back_to_quickjs():
    quickjs, chromium = Runner("quickjs"), Runner("chromium", ready=False)
    runners = ResearchRunners(quickjs, chromium)
    status = runners.status()
    assert status["ready"] and status["runtimes"] == ["quickjs"]
    assert status["profiles"]["chromium"]["ready"] is False
    with pytest.raises(ValueError, match="selected profile"):
        runners.run("source", runtime="chromium", source_order=["a.js"])
    assert quickjs.calls == []
    assert chromium.calls == [("run", ("source",), {"runtime": "chromium", "source_order": ["a.js"]})]
    with pytest.raises(ValueError, match="unavailable"):
        runners.run("source", runtime="node")
    assert quickjs.calls == [] and len(chromium.calls) == 1


def test_pending_owned_worker_blocks_all_profile_admission():
    runners = ResearchRunners(Runner("quickjs"), Runner("chromium", cleaned=False))
    status = runners.status()
    assert status["ready"] is False and status["runtimes"] == []
    assert status["cleanup_confirmed"] is False
    assert status["profiles"]["quickjs"]["ready"] is True


@pytest.mark.parametrize("malformed", [1, "false", None])
def test_router_does_not_turn_malformed_readiness_or_stop_results_into_authority(malformed):
    quickjs, chromium = Runner("quickjs"), Runner("chromium")
    chromium.ready = malformed
    runners = ResearchRunners(quickjs, chromium)
    assert runners.status()["runtimes"] == ["quickjs"]
    chromium.stop = lambda handle: malformed
    assert runners.stop({"kind": "chromium-worker"}) is False


def test_cancellation_routes_only_to_the_exact_owned_handle_kind():
    quickjs, chromium = Runner("quickjs"), Runner("chromium")
    runners = ResearchRunners(quickjs, chromium)
    browser = {"kind": "chromium-worker", "owner_nonce": "synthetic"}
    assert runners.stop(browser)
    assert quickjs.calls == [] and chromium.calls == [("stop", browser)]
    for foreign in (None, [], {}, {"kind": "foreign-worker"}, {"kind": []}, {"kind": {}}):
        assert runners.stop(foreign) is False
    assert quickjs.calls == [] and chromium.calls == [("stop", browser)]


def test_shutdown_attempts_both_supervisors_with_the_same_deadline():
    quickjs, chromium = Runner("quickjs"), Runner("chromium")
    quickjs.error = ValueError("Synthetic unconfirmed cleanup")
    with pytest.raises(ValueError, match="unconfirmed"):
        ResearchRunners(quickjs, chromium).close(deadline=123.0)
    assert quickjs.calls == chromium.calls == [("close", 123.0)]


@pytest.mark.parametrize("member", ["executable", "worker", "assets", "app_entry"])
def test_browser_resources_inside_owned_data_are_rejected_before_any_controller_write(tmp_path, monkeypatch, member):
    home, resources = tmp_path / "owned-data", tmp_path / "immutable-resources"
    home.mkdir()
    resources.mkdir()
    quickjs = resources / "quickjs"
    quickjs.mkdir()
    marker = home / "owner.json"
    marker.write_text(json.dumps(standalone_runtime.OWNER), encoding="utf-8")
    outside, inside = resources / "file.bin", home / "file.bin"
    outside.write_bytes(b"Labelled immutable runtime file, never executed.")
    inside.write_bytes(b"Labelled forbidden data-tree runtime file, never executed.")
    def binding(path):
        raw = path.read_bytes()
        return {"path": str(path), "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    browser = {"executable": binding(outside), "worker": binding(outside), "assets": []}
    if member == "assets":
        browser[member] = [binding(inside)]
    else:
        browser[member] = binding(inside)
    before = {p.name: p.read_bytes() for p in home.iterdir()}
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid immutable path must be rejected before supervisor construction")
    monkeypatch.setattr(standalone_runtime, "QuickJSRunner", forbidden)
    with pytest.raises(ValueError, match="App data must be separate"):
        standalone_runtime.StandaloneRuntime(home, quickjs, outside, outside, chromium_binding=browser)
    assert {p.name: p.read_bytes() for p in home.iterdir()} == before


@pytest.mark.parametrize("method,service_method", [
    ("workflow.submitProposal", "submit_proposal"), ("workflow.submitCode", "submit_code")])
def test_chromium_submission_reaches_workflow_admission_without_runtime_substitution(method, service_method):
    calls = []
    value = {"runtime": "chromium"}
    service = SimpleNamespace(**{service_method: lambda *args: calls.append(args) or {"stage": "synthetic"}})
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), None)
    params = {"researchId": "research-abcdefabcdef", "value": value}
    if method.endswith("Code"):
        params["review"] = {"accepted": False}
    try:
        assert dispatcher.execute(method, params) == {"stage": "synthetic"}
        assert calls[0][0:2] == (params["researchId"], value)
        with pytest.raises(ValueError, match="QuickJS or Chromium"):
            dispatcher.execute(method, {**params, "value": {"runtime": "node"}})
        assert len(calls) == 1
    finally:
        dispatcher._pool.shutdown(wait=True)


def _synthetic_browser_status(tmp_path, monkeypatch, failed_check=None):
    """Protocol-only status replies; no Electron, guest JS, workflow or SCI."""
    trusted = tmp_path / "synthetic-immutable-runtime.bin"
    trusted.write_bytes(b"Synthetic file binding, never executed.")
    descriptor = {"path": str(trusted.resolve()), "size": trusted.stat().st_size,
                  "sha256": hashlib.sha256(trusted.read_bytes()).hexdigest()}
    runner = browser_runner.BrowserRunner({"executable": descriptor, "worker": descriptor, "assets": []},
                                          supervisor_root=tmp_path / "supervisor")
    monkeypatch.setattr(browser_runner.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("Synthetic status launched a process"))
    monkeypatch.setattr(runner, "_verify_manifest", lambda envelope, packet: envelope["runtime_manifest"])
    received = []

    def execute(packet, **kwargs):
        code = packet["experiment_files"]["check.mjs"]["text"]
        if "globalThis.callProduction=" in code:
            label, error = "caught_gate_replacement_rejected", "Browser capability replacement: callProduction"
        elif "await fetch(" in code:
            label, error = "caught_fetch_rejected", "Forbidden browser capability: fetch"
        elif "while(true)" in code:
            label, error = "owned_tree_termination", None
        else:
            label, error = "canvas_and_held_call", None
        value = {"value": {"value": 7, "width": 12}, "noNode": True, "rejection": True, "immutable": True,
                 "input": packet["scientific_inputs"].get("supporting-document-000000000000"),
                 "fixture": {"sha256": hashlib.sha256("가".encode()).hexdigest(),
                             "content": base64.b64encode("가".encode()).decode()}}
        envelope = {"status": "failed" if error else "succeeded", "error": error,
                    "production_calls": [{"path": "check.js", "function": "J.measure", "calls": 2}],
                    "runtime_manifest": {"versions": {"engine": "synthetic status control"}},
                    "observation_b64": base64.b64encode(json.dumps(value).encode()).decode()}
        receipt = {"exit_code": 1 if error else 0, "envelope": envelope,
                   "cleanup_confirmed": True, "active_handle": {}, "reason": None,
                   "forced_stop_confirmed": True, "raw_response": b"SYNTHETIC original worker response\xff\x00\r\n",
                   "stderr": "SYNTHETIC returned stderr\ufffd\r\n", "startup_preamble": [],
                   "input_transport_errors": [], "duration_seconds": 0.001}
        if label == "owned_tree_termination":
            receipt.update(envelope=None, reason="cancelled")
        if label == failed_check:
            receipt["reason"] = "synthetic original transport failure"
        received.append((label, receipt))
        return receipt

    monkeypatch.setattr(runner, "_execute", execute)
    return runner, received


@pytest.mark.skipif(os.name != "nt", reason="Windows readiness control, no browser process")
@pytest.mark.parametrize("failed_check", ["canvas_and_held_call", "caught_gate_replacement_rejected",
                                        "caught_fetch_rejected", "owned_tree_termination"])
def test_failed_browser_readiness_preserves_exact_original_receipt_and_identifies_check(tmp_path, monkeypatch, failed_check):
    runner, received = _synthetic_browser_status(tmp_path, monkeypatch, failed_check)
    try:
        status = runner.status()
        assert status["ready"] is False and status["cleanup_confirmed"] is True
        diagnostic = status["diagnostic"]
        assert diagnostic["self_check"] == failed_check
        original = received[-1][1]
        assert received[-1][0] == failed_check
        assert diagnostic["worker"] == {"exit_code": original["exit_code"], "reason": original["reason"],
            "cleanup_confirmed": original["cleanup_confirmed"], "envelope_status": (original["envelope"] or {}).get("status"),
            "envelope_error": (original["envelope"] or {}).get("error")}
        binding = diagnostic["evidence"]
        path = runner.supervisor_root / binding["path"]
        raw = path.read_bytes()
        assert len(raw) == binding["size"] and hashlib.sha256(raw).hexdigest() == binding["sha256"]
        preserved = json.loads(raw)
        response = preserved["raw_response"]
        response_raw = (runner.supervisor_root / response["path"]).read_bytes()
        assert response_raw == original["raw_response"]
        assert len(response_raw) == response["size"] and hashlib.sha256(response_raw).hexdigest() == response["sha256"]
        stderr = preserved.pop("stderr_text_artifact")
        assert (runner.supervisor_root / stderr["path"]).read_bytes() == original["stderr"].encode("utf-8")
        assert preserved.pop("stderr_scope") == "Returned UTF-8 replace-decoded text, not original stderr bytes"
        preserved["raw_response"] = response_raw
        assert preserved == original and type(original["raw_response"]) is bytes
        assert len(list((runner.supervisor_root / "self-check-failures").iterdir())) == 1
        assert set(item.name for item in path.parent.iterdir()) == {"receipt.json", "raw-response.bin", "stderr-returned-text.txt"}
        assert len(received) == ["canvas_and_held_call", "caught_gate_replacement_rejected",
                                 "caught_fetch_rejected", "owned_tree_termination"].index(failed_check) + 1
    finally:
        runner.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows readiness control, no browser process")
def test_failed_diagnostic_retention_cannot_turn_browser_unavailability_into_readiness(tmp_path, monkeypatch):
    runner, received = _synthetic_browser_status(tmp_path, monkeypatch, "caught_fetch_rejected")
    def denied(receipt):
        raise PermissionError("Synthetic diagnostic storage failure")
    monkeypatch.setattr(runner, "_retain_self_check_failure", denied)
    try:
        status = runner.status()
        assert status["ready"] is False and status["diagnostic"]["self_check"] == "caught_fetch_rejected"
        assert status["diagnostic"]["evidence_retention_error"] == "PermissionError"
        assert "evidence" not in status["diagnostic"]
        assert len(received) == 3 and received[-1][1]["reason"] == "synthetic original transport failure"
    finally:
        runner.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows readiness control, no browser process")
def test_successful_browser_status_creates_no_failure_evidence_and_keeps_all_seven_checks(tmp_path, monkeypatch):
    runner, received = _synthetic_browser_status(tmp_path, monkeypatch)
    try:
        status = runner.status()
        assert status["ready"] is True and status["cleanup_confirmed"] is True
        assert len(status["self_checks"]) == 7 and all(status["self_checks"].values())
        assert "diagnostic" not in status and len(received) == 4
        assert not (runner.supervisor_root / "self-check-failures").exists()
    finally:
        runner.close()

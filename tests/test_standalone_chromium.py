"""Labelled controller routing controls, without Chromium or account access."""

from types import SimpleNamespace
import hashlib
import json

import pytest

from paper_factory import ipc
from paper_factory.standalone_runtime import ResearchRunners
from paper_factory import standalone_runtime


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

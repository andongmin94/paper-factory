"""Native Chromium transport boundaries; the protocol double runs no guest JS."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time

import pytest

from paper_factory.autonomous import browser_runner as module
from paper_factory.autonomous import windows_runtime
from paper_factory.autonomous.browser_runner import BrowserRunner


def binding(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path.absolute()), "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


# This trusted Python protocol double exercises OS ownership and framing only.
# It never evaluates the supplied source or experiment files.
PROTOCOL_DOUBLE = r'''
import base64, hashlib, json, os, subprocess, sys, time
from urllib.parse import quote
protocol = "paper-factory-chromium-v1"
print(json.dumps({"protocol": protocol, "phase": "awaiting-go"}), flush=True)
r = json.loads(sys.stdin.readline())
mode = next(iter(r["experiment_files"].values()))["text"]
if mode == "hang":
    while True: time.sleep(.1)
if mode == "overflow":
    sys.stdout.write("x" * 20000); sys.stdout.flush(); time.sleep(60)
selected, function = r["production_entrypoint"].rsplit(":", 1)
child = None
if mode == "descendant":
    child = subprocess.Popen([sys.executable,"-I","-c","import time;time.sleep(300)"],creationflags=0x08000000)
observation = {"value": 7, "fixtures": [], "child_pid": child.pid if child else None,
               "profile": os.environ["APPDATA"], "controls":[{"name":"negative","passed":mode!="control-failure"}]}
raw = json.dumps(observation).encode()
manifest = {"backend":"chromium-sandbox","bridge":"controller-held-chromium-call-gate",
    "production_entrypoint":r["production_entrypoint"],"source_order":r["source_order"],
    "source_files":{k:{"original_sha256":v["sha256"],"size":len(v["text"].encode())} for k,v in r["source_files"].items()},
    "experiment_files":{k:{"sha256":v["sha256"],"size":len(v["text"].encode())} for k,v in r["experiment_files"].items()},
    "scientific_inputs":{k:{"name":v["name"],"sha256":v["sha256"],"size":len(v["text"].encode())} for k,v in r["scientific_inputs"].items()},
    "scientific_input_bytes":sum(len(v["text"].encode()) for v in r["scientific_inputs"].values()),
    "versions":{"electron":"synthetic protocol double"},"production_dispatch_attempts":1,"production_completed_calls":1,
    "call_receipts":[{"index":1,"input_sha256":hashlib.sha256(b"[6]").hexdigest(),"input_bytes":3,
                      "status":"succeeded","output_sha256":hashlib.sha256(b"7").hexdigest(),"output_bytes":1}],
    "distinct_renderer_processes":True,"separate_nonpersistent_sessions":True,"sandboxed":True,
    "network_denied":True,"shutdown_windows_closed":True,"node_integration":False,
    "fixture_count":0,"fixture_bytes":0,"retained_fixtures":[],"scientific_input_reads":0,"scientific_input_read_bytes":0,
    "renderer_capabilities": {"production":{"require":"undefined","process":"undefined"},
                             "experiment":{"require":"undefined","process":"undefined"}}}
manifest["owned_deny_proxy"] = {"host":"127.0.0.1","port":12345,"denied_connections":0,
                               "close_requested":True,"close_callback_confirmed":False}
scripts = [{"path":name,"script_url":"pf-science://production-"+r["nonce"]+"/"+quote(name,safe="/~.-_"),
            "script_id":str(i),"sha256":r["source_files"][name]["sha256"],"size":len(r["source_files"][name]["text"].encode())}
           for i,name in enumerate(r["source_order"],1)]
manifest["loaded_source_scripts"] = scripts
manifest["function_provenance"] = {"script_url":scripts[-1]["script_url"],"script_id":scripts[-1]["script_id"],
                                   "script_sha256":scripts[-1]["sha256"],"size":scripts[-1]["size"]}
if mode == "bad-manifest": manifest["source_order"] = ["forged.js"]
if mode == "bad-call": function = "measure"
if mode == "float-calls": manifest["production_dispatch_attempts"] = 1.0
if mode == "bool-completed": manifest["production_completed_calls"] = True
if mode == "missing-receipts": manifest["call_receipts"] = []
if mode == "wrong-index": manifest["call_receipts"][0]["index"] = 2
if mode == "wrong-digest": manifest["call_receipts"][0]["input_sha256"] = "forged"
if mode == "bool-source-size": manifest["source_files"][selected]["size"] = True
if mode == "node-visible": manifest["renderer_capabilities"]["production"]["process"] = "object"
if mode == "wrong-script": manifest["function_provenance"]["script_sha256"] = "0" * 64
if mode == "wrong-loaded": manifest["loaded_source_scripts"][0]["sha256"] = "0" * 64
if mode == "fake-fixtures": observation["fixtures"] = [{"label":"fake","encoding":"base64","content":"eA==","sha256":hashlib.sha256(b"x").hexdigest()}]
if mode == "wrong-fixture-count": manifest["fixture_count"] = 1
raw = json.dumps(observation).encode()
frame = {"protocol":protocol,"phase":"result","nonce":r["nonce"],
    "status":"failed" if mode=="control-failure" else "succeeded",
    "observation_b64":base64.b64encode(raw).decode(),"production_calls":[{"path":selected,"function":function,"calls":1}],
    "coverage_truncated":False,"coverage_mechanism":"controller-held-chromium-call-gate","runtime_manifest":manifest}
if mode == "bad-nonce": frame["nonce"] = "f" * 32
print(json.dumps(frame), flush=True)
if mode == "extra-frame": print(json.dumps(frame), flush=True)
'''


@pytest.fixture
def configured(tmp_path):
    worker = tmp_path / "trusted_protocol_double.py"
    worker.write_text(PROTOCOL_DOUBLE, encoding="utf-8")
    executable = Path(sys.base_prefix) / ("python.exe" if os.name == "nt" else "bin/python3")
    if not executable.is_file():
        executable = Path(sys.executable)
    descriptor = {"executable": binding(executable), "worker": binding(worker), "assets": [], "app_entry": binding(worker)}
    return BrowserRunner(descriptor, supervisor_root=tmp_path / "supervisor")


@pytest.fixture
def inputs(tmp_path):
    source, bundle, output = (tmp_path / name for name in ("source", "bundle", "output"))
    source.mkdir(); bundle.mkdir()
    (source / "util.js").write_bytes(b"window.J={};\r\n")
    (source / "measure.js").write_bytes(b"J.measure=x=>x+1;\n")
    (bundle / "run.mjs").write_bytes(b"positive")
    return source, bundle, output


def packet(runner, inputs, **options):
    return runner._packet(inputs[0], inputs[1], source_order=["util.js", "measure.js"], entrypoint="run.mjs",
                          production_entrypoint="measure.js:J.measure", scientific_inputs=None, timeout_seconds=5, **options)


def native_run(runner, inputs, mode="positive", **kwargs):
    (inputs[1] / "run.mjs").write_text(mode, encoding="utf-8")
    return runner.run(*inputs, runtime="chromium", source_order=["util.js", "measure.js"], entrypoint="run.mjs",
                      production_entrypoint="measure.js:J.measure", **kwargs)


def test_config_requires_exact_absolute_frozen_bindings(tmp_path):
    f = tmp_path / "worker.js"; f.write_text("trusted")
    good = binding(f)
    with pytest.raises(ValueError, match="absolute"):
        BrowserRunner({"executable": {**good, "path": "worker.js"}, "worker": good, "assets": []}, supervisor_root=tmp_path / "supervisor")
    with pytest.raises(ValueError, match="absolute"):
        BrowserRunner({"executable": {**good, "size": True}, "worker": good, "assets": []}, supervisor_root=tmp_path / "supervisor")
    with pytest.raises(ValueError, match="explicit"):
        BrowserRunner({"executable": good, "worker": good, "assets": [], "launch_args": ["--unsafe"]}, supervisor_root=tmp_path / "supervisor")


def test_changed_worker_and_companion_bindings_never_spawn(configured, monkeypatch):
    Path(configured.binding["worker"]["path"]).write_bytes(b"changed")
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_args, **_kwargs: pytest.fail("Changed worker was launched"))
    with pytest.raises(ValueError, match="bytes changed"):
        configured._runtime()


@pytest.mark.parametrize("order", [[], ["util.js", "util.js"], ["../measure.js"], ["measure.js", "util.js"], [None]])
def test_order_cannot_escape_duplicate_or_change_selected_module(configured, inputs, order):
    before = {path.name: path.read_bytes() for path in inputs[0].iterdir()}
    with pytest.raises(ValueError):
        configured._packet(inputs[0], inputs[1], source_order=order, entrypoint="run.mjs",
                           production_entrypoint="measure.js:J.measure", scientific_inputs=None, timeout_seconds=5)
    assert before == {path.name: path.read_bytes() for path in inputs[0].iterdir()}


def test_original_order_and_whole_unicode_bytes_are_preserved(configured, inputs):
    text = "// 가🙂\r\nJ.measure=x=>x+1;\r\n"
    (inputs[0] / "measure.js").write_bytes(text.encode("utf-8"))
    request = packet(configured, inputs)
    assert request["source_order"] == ["util.js", "measure.js"]
    assert request["source_files"]["measure.js"] == {"text": text, "sha256": hashlib.sha256(text.encode()).hexdigest()}
    assert (inputs[0] / "measure.js").read_bytes() == text.encode()


def test_source_read_gate_cannot_substitute_declared_production_bytes(configured, inputs):
    record = {"name": "measure.js", "text": "forged", "sha256": hashlib.sha256(b"forged").hexdigest()}
    with pytest.raises(ValueError, match="differs"):
        configured._packet(inputs[0], inputs[1], source_order=["util.js", "measure.js"], entrypoint="run.mjs",
                           production_entrypoint="measure.js:J.measure", scientific_inputs={"source/measure.js": record}, timeout_seconds=5)


def test_controller_owned_bundle_metadata_is_not_a_generated_module(configured, inputs):
    (inputs[1] / "bundle.json").write_bytes(b'{"runtime":"chromium","files":[]}')
    (inputs[1] / "review.json").write_bytes(b'{"approved":true}')
    request = packet(configured, inputs)
    assert set(request["experiment_files"]) == {"run.mjs"}
    (inputs[1] / "generated-notes.md").write_bytes(b"Frozen generated artifact, not executable")
    request = packet(configured, inputs)
    assert set(request["experiment_files"]) == {"run.mjs"}
    (inputs[1] / "unregistered.bin").write_bytes(b"not a declared artifact type")
    with pytest.raises(ValueError, match="JavaScript"):
        packet(configured, inputs)


@pytest.mark.parametrize("kind", ["quickjs-worker", "chromium-worker"])
def test_incomplete_or_other_runtime_handles_never_signal_processes(configured, monkeypatch, kind):
    monkeypatch.setattr(windows_runtime, "stop", lambda *_: pytest.fail("Unowned job was opened"))
    assert configured.stop({"kind": kind, "pid": 999, "owner_nonce": "a" * 32}) is False


def test_non_windows_profile_is_unavailable_without_a_fallback(configured, monkeypatch):
    monkeypatch.setattr(module, "os", type("Platform", (), {"name": "posix"})())
    monkeypatch.setattr(configured, "_runtime", lambda: pytest.fail("Unsupported platform inspected/ran assets"))
    result = configured.status()
    assert result["ready"] is False and result["runtimes"] == [] and result["cleanup_confirmed"] is True


def test_incomplete_starting_marker_remains_blocked_without_pid_guessing(configured, monkeypatch):
    handle = {"kind": "chromium-worker", "pid": 0, "owner_nonce": "a" * 32}
    original = json.dumps({"format": module.JOURNAL, "workers": [{"phase": "starting", "purpose": "probe", "handle": handle}]}).encode()
    configured._journal_path.write_bytes(original)
    configured._records = configured._load_journal()
    monkeypatch.setattr(windows_runtime, "stop", lambda *_: pytest.fail("Incomplete identity signalled a job"))
    assert configured._prepare() is False and configured._pending() == handle
    assert configured._journal_path.read_bytes() == original
    with pytest.raises(ValueError, match="unconfirmed"):
        configured.close(deadline=time.monotonic() + 30)
    configured._release()
    assert configured._journal_path.read_bytes() == original


def test_generated_bytes_share_the_frozen_map_budget(configured, inputs, monkeypatch):
    size = sum(path.stat().st_size for path in inputs[0].iterdir())
    monkeypatch.setattr(module, "MAX_SOURCE_BYTES", size)
    with pytest.raises(ValueError, match="byte boundary"):
        packet(configured, inputs)


@pytest.fixture
def manifest_envelope(configured, inputs, monkeypatch):
    """Build the existing trusted protocol double's receipt without spawning."""
    request = {**packet(configured, inputs), "nonce": "a" * 32}
    output = io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdin", io.StringIO(json.dumps(request) + "\n"))
        patch.setattr(sys, "stdout", output)
        patch.setenv("APPDATA", str(inputs[0].parent))
        exec(PROTOCOL_DOUBLE, {})
    envelope = json.loads(output.getvalue().splitlines()[-1])
    configured._verify_manifest(envelope, request)
    return envelope, request


@pytest.mark.parametrize("field,value", [
    ("record", None), ("record", []),
    ("host", None), ("host", "localhost"), ("host", "192.0.2.1"),
    ("port", None), ("port", True), ("port", 12345.0), ("port", 0), ("port", 65536),
    ("denied_connections", None), ("denied_connections", True), ("denied_connections", 0.0),
    ("denied_connections", -1), ("denied_connections", 1_000_000_001),
    ("close_requested", None), ("close_requested", False), ("close_requested", 1),
    ("close_callback_confirmed", None), ("close_callback_confirmed", 0),
    ("close_callback_confirmed", "false"), ("unsupported", True),
])
def test_owned_proxy_receipt_rejects_missing_unowned_or_malformed_fields(manifest_envelope, field, value):
    envelope, request = manifest_envelope
    manifest = envelope["runtime_manifest"]
    if field == "record":
        if value is None:
            manifest.pop("owned_deny_proxy")
        else:
            manifest["owned_deny_proxy"] = value
    elif value is None:
        manifest["owned_deny_proxy"].pop(field)
    else:
        manifest["owned_deny_proxy"][field] = value
    with pytest.raises(ValueError, match="owned network-denial proxy"):
        BrowserRunner._verify_manifest(envelope, request)


@pytest.mark.parametrize("port,count,callback", [(1, 0, False), (65535, 1_000_000_000, True)])
def test_owned_proxy_callback_receipt_does_not_replace_native_job_cleanup(manifest_envelope, port, count, callback):
    envelope, request = manifest_envelope
    proxy = envelope["runtime_manifest"]["owned_deny_proxy"]
    proxy.update(port=port, denied_connections=count, close_callback_confirmed=callback)
    assert BrowserRunner._verify_manifest(envelope, request)["owned_deny_proxy"] == proxy


@pytest.fixture
def transport(configured, monkeypatch, request):
    if os.name != "nt":
        pytest.skip("Native owned multiprocess transport requires Windows")
    # Bypass Chromium's actual readiness checks only for this labelled transport
    # double. These tests establish no browser isolation or Canvas capability.
    monkeypatch.setattr(configured, "status", lambda: {"ready": True, "cleanup_confirmed": True})
    request.addfinalizer(lambda: configured.close(deadline=time.monotonic() + 30))
    return configured


def assert_closed(runner, result):
    assert result["cleanup_confirmed"] is True and result["active_handle"] == {}
    assert json.loads(runner._journal_path.read_bytes())["workers"] == []
    assert not list((runner.supervisor_root / "profiles").iterdir())


def test_native_transport_retains_exact_nonce_bound_observations_and_manifest(transport, inputs):
    original = {p.name: p.read_bytes() for p in inputs[0].iterdir()}
    handles = []
    result = native_run(transport, inputs, on_handle=handles.append)
    assert result["status"] == "succeeded", result
    assert result["production_calls"] == [{"path": "measure.js", "function": "J.measure", "calls": 1}]
    raw = (inputs[2] / "observations.json").read_bytes()
    assert json.loads(raw)["value"] == 7
    manifest = json.loads((inputs[2] / "runtime-manifest.json").read_bytes())
    assert manifest["source_order"] == ["util.js", "measure.js"]
    assert manifest["binding_scope"] == "explicit configured files only"
    assert manifest["entire_electron_binary_closure_verified"] is False
    assert handles[0]["kind"] == "chromium-worker" and windows_runtime.process_ticks(handles[0]["pid"]) is None
    assert original == {p.name: p.read_bytes() for p in inputs[0].iterdir()}
    assert_closed(transport, result)


@pytest.mark.parametrize("mode", ["bad-nonce", "extra-frame"])
def test_nonce_and_single_result_frame_are_native_authority(transport, inputs, mode):
    result = native_run(transport, inputs, mode)
    assert result["status"] == "failed" and "invalid worker response" in result["stderr"]
    assert (inputs[2] / "worker-response.json").is_file()
    assert not (inputs[2] / "observations.json").exists()
    assert_closed(transport, result)


@pytest.mark.parametrize("mode", ["bad-manifest", "bad-call", "control-failure", "float-calls", "bool-completed",
                                "missing-receipts", "wrong-index", "wrong-digest", "bool-source-size", "node-visible",
                                "wrong-script", "wrong-loaded", "fake-fixtures", "wrong-fixture-count"])
def test_failed_evidence_retains_raw_observations_without_promoting_success(transport, inputs, mode):
    result = native_run(transport, inputs, mode)
    assert result["status"] == "failed"
    raw = (inputs[2] / "observations.json").read_bytes()
    frame = json.loads((inputs[2] / "worker-response.json").read_bytes())
    assert raw == base64.b64decode(frame["observation_b64"])
    assert_closed(transport, result)


def test_parent_exit_cannot_leave_owned_descendants_or_pipe_writers(transport, inputs):
    result = native_run(transport, inputs, "descendant")
    assert result["status"] == "succeeded", result
    pid = json.loads((inputs[2] / "observations.json").read_bytes())["child_pid"]
    assert windows_runtime.process_ticks(pid) is None
    assert_closed(transport, result)


def test_timeout_terminates_entire_owned_job(transport, inputs):
    started = time.monotonic()
    result = native_run(transport, inputs, "hang", timeout_seconds=1)
    assert result["status"] == "timeout" and time.monotonic() - started < 12
    assert_closed(transport, result)


def test_cancel_after_persisted_handle_confirms_owned_exit(transport, inputs):
    handles = []
    result = native_run(transport, inputs, "hang", cancel=lambda: bool(handles), on_handle=handles.append)
    assert result["status"] == "cancelled" and len(handles) == 1
    assert windows_runtime.process_ticks(handles[0]["pid"]) is None
    assert_closed(transport, result)


def test_oversized_frame_stops_worker_and_retains_bounded_raw(transport, inputs, monkeypatch):
    monkeypatch.setattr(module, "MAX_RESPONSE_BYTES", 8192)
    result = native_run(transport, inputs, "overflow")
    assert result["status"] == "failed" and "overflow" in result["stderr"]
    assert (inputs[2] / "worker-response.json").stat().st_size <= 8192
    assert_closed(transport, result)


@pytest.mark.skipif(os.name != "nt", reason="Actual Chromium worker profile currently supports Windows")
def test_real_canvas_async_gate_raw_fixture_validation_and_owned_shutdown(tmp_path):
    root = Path(__file__).resolve().parents[1]
    executable = root / "desktop/node_modules/electron/dist/electron.exe"
    worker = root / "desktop/dist/chromium-worker.mjs"
    if not executable.is_file() or not worker.is_file():
        pytest.skip("Build the installed desktop Chromium worker before this actual boundary control")
    candidate = BrowserRunner({"executable": binding(executable), "worker": binding(worker), "assets": [],
                               "app_entry": binding(worker)}, supervisor_root=tmp_path / "actual-supervisor")
    source, bundle = tmp_path / "source", tmp_path / "bundle"
    source.mkdir(); bundle.mkdir()
    name = "원문 # % .js"
    original = b'const ctx=document.createElement("canvas").getContext("2d");window.J={measure(x){return {value:x+1,width:ctx.measureText("original").width}}};\r\n'
    (source / name).write_bytes(original)
    (bundle / "bundle.json").write_text('{"runtime":"chromium"}')
    (bundle / "review.json").write_text('{"approved":true}')
    code = '''export default async function run(){
      const result=JSON.parse(await callProduction("[6]"));
      const fixture=JSON.parse(await retainFixture("input","[6]"));
      return {observations:[{unit_id:"synthetic",seed:11,condition:"original",metric:"value",value:result.value}],
        controls:[{name:"actual Canvas result",passed:result.value===7&&result.width>0,details:"synthetic boundary control"}],fixtures:[fixture]};}'''
    (bundle / "run.mjs").write_text(code)
    try:
        ready = candidate.status()
        assert ready["ready"] is True and ready["cleanup_confirmed"] is True, ready
        assert all(ready["self_checks"].values()) and len(ready["self_checks"]) == 7
        result = candidate.run(source, bundle, tmp_path / "positive", runtime="chromium", source_order=[name],
                               entrypoint="run.mjs", production_entrypoint=name + ":J.measure", timeout_seconds=15)
        assert result["status"] == "succeeded", result
        assert (source / name).read_bytes() == original
        observed = json.loads((tmp_path / "positive/observations.json").read_bytes())
        manifest = json.loads((tmp_path / "positive/runtime-manifest.json").read_bytes())
        assert observed["fixtures"] == manifest["retained_fixtures"]
        assert manifest["function_provenance"]["script_sha256"] == hashlib.sha256(original).hexdigest()
        assert "%23" in manifest["function_provenance"]["script_url"] and "%25" in manifest["function_provenance"]["script_url"]
        assert_closed(candidate, result)
        forged = code.replace("fixtures:[fixture]", "fixtures:[{...fixture,label:'forged'}]")
        (bundle / "run.mjs").write_text(forged)
        rejected = candidate.run(source, bundle, tmp_path / "forged", runtime="chromium", source_order=[name],
                                 entrypoint="run.mjs", production_entrypoint=name + ":J.measure", timeout_seconds=15)
        assert rejected["status"] == "failed" and "gate-retained fixtures" in rejected["stderr"]
        assert (tmp_path / "forged/observations.json").is_file()
        assert_closed(candidate, rejected)
    finally:
        candidate.close(deadline=time.monotonic() + 30)

"""Owned temporary controllers; no account state or retained user evidence."""

import builtins
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import zipfile

import httpx
import pytest

from paper_factory import ipc, project, standalone_runtime
from paper_factory.autonomous.models import ResearchPlan
from paper_factory.models import Project
from paper_factory.standalone_runtime import OWNER, StandaloneRuntime
from paper_factory.workflow import WorkflowError
from paper_factory.workspace import digest_file, file_lock, loads_json, write_json


@pytest.fixture(autouse=True)
def isolated_runtime_environment(monkeypatch):
    # StandaloneRuntime owns a process in production. Preserve the test host's
    # environment when several isolated controllers share pytest's process.
    for name in ("PF_NODE_BIN", "PYPANDOC_PANDOC", "TYPST_FONT_PATHS"):
        monkeypatch.setenv(name, os.environ.get(name, ""))


@pytest.fixture(scope="module")
def runtime_files(tmp_path_factory):
    root = tmp_path_factory.mktemp("standalone-resources")
    assets = Path(__file__).resolve().parents[1] / "desktop/runtime-inputs/assets"
    metadata = loads_json((assets / "quickjs-runtime.json").read_bytes())
    raw = (assets / "quickjs-runtime.zip").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == metadata["archive_sha256"]
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for item in archive.infolist():
            target = root / item.filename
            assert target.resolve().is_relative_to(root.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(item))
    node = shutil.which("node")
    if not node or not subprocess.check_output([node, "--version"], timeout=5).startswith(b"v24."):
        pytest.skip("Actual standalone runner requires explicit Node 24")
    return root / "quickjs-runtime", Path(node).resolve()


@pytest.fixture
def runtime(tmp_path, runtime_files, pandoc, monkeypatch):
    for name in ("PF_NODE_BIN", "PYPANDOC_PANDOC", "TYPST_FONT_PATHS"):
        monkeypatch.delenv(name, raising=False)
    engine = StandaloneRuntime(tmp_path / "home", *runtime_files, Path(pandoc).resolve())
    yield engine
    engine.close()


def frame(identifier, method, **params):
    return ipc.request(json.dumps({"id": identifier, "method": method, "params": params}).encode())


def receipt(outcome="completed"):
    prompt, text = "A bounded original prompt.", "Original model output: 한글."
    value = {"id": "12345678-1234-1234-1234-123456789abc", "phase": "code-review",
             "at": "2026-10-05T00:00:00Z", "model": "gpt-6-astra", "profileId": "owned-test-profile",
             "prompt": prompt, "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(), "outcome": outcome}
    if outcome == "completed":
        value.update(text=text, textSha256=hashlib.sha256(text.encode()).hexdigest())
    return value


def create_local(engine, tmp_path):
    source = tmp_path / "public-fixture"
    source.mkdir()
    (source / "source.js").write_text("module.exports={calculate(x){return x+1;}};", encoding="utf-8")
    return engine.service.create(str(source), "Test a bounded production transformation against an independent oracle.")["id"]


def protocol():
    from test_workflow import protocol as workflow_protocol
    return {"feasible": True, "reason": "A public transformation supports independently annotated fixture checks.",
            "title": "Controlled production transformation fixture validation", "question": "How does the transformation preserve annotated fixture values?",
            "research_gap": "Synthetic IPC fixture; no actual gap in research literature is established.",
            "expected_contribution": "Synthetic positive proposal for IPC tests, not an academically useful study.",
            "comparison_rationale": "The removed increment is a fixture comparator for controller validation only.",
            "sampling_rationale": "The fixed arithmetic grid validates orchestration rather than representative sampling.",
            "runtime": "quickjs", "source_files": ["source.js"], "production_entrypoint": "source.js:calculate",
            "dependencies": [], "conditions": ["production", "ablation"],
            "metrics": [{"name": "error", "unit": "events", "description": "Independent expected value mismatches."}],
            "comparator": "Remove the increment rule in an explicit comparator.",
            "independent_oracle": "Known arithmetic fixture annotations define expected values.",
            "sampling_unit": "An independently seeded annotated fixture.", "units_per_seed": 3, "seeds": [11, 37],
            "parameters": {}, "procedure": ["Generate seeded annotations.", "Invoke unchanged source and comparator.", "Record paired errors and controls."],
            "analysis_method": "Descriptive means paired by fixture and seed.",
            "limitations": ["Synthetic fixtures do not represent natural populations.", "Instrumentation affects execution timing."],
            "literature_queries": ["independent software test oracle"],
            "research_claim": workflow_protocol()["research_claim"]}


@pytest.mark.parametrize("raw", [
    b'{"id":"a","id":"b","method":"runtime.status","params":{}}',
    b'{"id":"a","method":"shell.run","params":{}}',
    b'{"id":"a","method":"runtime.status","params":{"path":"C:/private"}}',
    b'{"id":"a","method":"workflow.status","params":{"researchId":"../../private"}}',
    b'{"id":"a","method":"workflow.status","params":{"researchId":"research-abcdefabcdef","includeMaterials":1}}',
    b'{"id":"a","method":"workflow.submitPlan","params":{"researchId":"research-abcdefabcdef"}}',
    b'{"id":"a","method":"workflow.readMaterial","params":{"researchId":"research-abcdefabcdef","area":"source","name":"x","limit":32001}}',
])
def test_request_rejects_ambiguous_unbounded_or_undeclared_input(raw):
    with pytest.raises((ValueError, WorkflowError)):
        ipc.request(raw)


def test_request_byte_limit():
    with pytest.raises(WorkflowError, match="byte limit"):
        ipc.request(b" " * (ipc.MAX_INPUT_BYTES + 1))


@pytest.mark.parametrize("method", ["workflow.resume", "workflow.reviseWriting", "workflow.redesignStudy", "workflow.improveWriting"])
def test_authoring_ipc_accepts_only_research_id_and_maps_to_explicit_method(method):
    from types import SimpleNamespace
    valid = {"id": "authoring", "method": method, "params": {"researchId": "research-abcdefabcdef"}}
    assert ipc.request(json.dumps(valid).encode()) == valid
    for params in ({}, {"researchId": "research-abcdefabcdef", "force": True}, {"researchId": "../private"}):
        with pytest.raises(ValueError):
            ipc.request(json.dumps({**valid, "params": params}).encode())
    calls = []
    service = SimpleNamespace(resume=lambda identifier: calls.append(("resume", identifier)) or {"status": "ready"},
                              revise_writing=lambda identifier: calls.append(("revise", identifier)) or {"status": "ready"},
                              redesign_study=lambda identifier: calls.append(("redesign", identifier)) or {"status": "ready"},
                              improve_writing=lambda identifier: calls.append(("improve", identifier)) or {"status": "ready"},
                              collect_literature=None, start_experiment=None, cancel=None, export=None)
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), io.BytesIO())
    try:
        assert dispatcher.execute(valid["method"], valid["params"]) == {"status": "ready"}
        assert calls == [({"workflow.resume": "resume", "workflow.reviseWriting": "revise", "workflow.redesignStudy": "redesign", "workflow.improveWriting": "improve"}[method], "research-abcdefabcdef")]
    finally:
        dispatcher._pool.shutdown(wait=True)


@pytest.mark.parametrize("method,field", [("workflow.submitProposal", "value"), ("workflow.submitStudyReview", "review")])
def test_study_ipc_routes_bounded_objects_to_explicit_new_methods(method, field):
    from test_workflow import STUDY_REVIEW

    value = protocol() if field == "value" else STUDY_REVIEW
    params = {"researchId": "research-abcdefabcdef", field: value}
    valid = {"id": "study", "method": method, "params": params}
    assert ipc.request(json.dumps(valid).encode()) == valid
    for bad in ({"researchId": params["researchId"]}, {**params, "force": True},
                {**params, "researchId": "../private"}, {**params, field: []}):
        with pytest.raises(ValueError):
            ipc.request(json.dumps({**valid, "params": bad}).encode())
    calls = []
    service = SimpleNamespace(
        submit_proposal=lambda identifier, item: calls.append(("proposal", identifier, item)) or {"stage": "proposed"},
        submit_study_review=lambda identifier, item: calls.append(("study", identifier, item)) or {"stage": "planned"})
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), io.BytesIO())
    try:
        result = dispatcher.execute(method, params)
        assert result == {"stage": "proposed" if field == "value" else "planned"}
        assert calls == [("proposal" if field == "value" else "study", params["researchId"], value)]
        if field == "value":
            with pytest.raises(ValueError, match="QuickJS"):
                dispatcher.execute(method, {**params, "value": {**value, "runtime": "node"}})
            assert len(calls) == 1
    finally:
        dispatcher._pool.shutdown(wait=True)


def test_removed_submit_plan_ipc_cannot_bypass_suitability_gate():
    with pytest.raises(WorkflowError) as rejected:
        frame("old-plan", "workflow.submitPlan", researchId="research-abcdefabcdef", value=protocol())
    assert rejected.value.code == "METHOD_NOT_ALLOWED"


def test_public_validation_feedback_has_locations_without_input_or_private_paths():
    secret = "C:/private/repository/private-source.js"
    try:
        ResearchPlan.model_validate({"title": secret})
    except ValueError as error:
        feedback = ipc.public_error(error)
    assert feedback["code"] == "INVALID_ARGUMENT" and "feasible: Field required" in feedback["message"]
    assert secret not in feedback["message"]
    feedback = ipc.public_error(ValueError("Invalid placeholder in C:/private/source.md and sk-abcdefghijklmnopqrstuv"))
    assert "private/source" not in feedback["message"] and "sk-" not in feedback["message"]
    assert "Invalid placeholder" in feedback["message"]


def test_lease_precedes_recovery_and_rejects_second_controller(runtime, runtime_files, pandoc, monkeypatch):
    calls = []
    monkeypatch.setattr(standalone_runtime, "WorkflowService", lambda *a, **kw: calls.append(a))
    with pytest.raises(ValueError, match="Another operation"):
        StandaloneRuntime(runtime.home, *runtime_files, Path(pandoc).resolve())
    assert not calls
    assert loads_json((runtime.home / "owner.json").read_bytes()) == OWNER


def test_existing_unmarked_or_different_owner_never_recovers(tmp_path, runtime_files, pandoc, monkeypatch):
    calls = []
    monkeypatch.setattr(standalone_runtime, "WorkflowService", lambda *a, **kw: calls.append(a))
    home = tmp_path / "home"
    home.mkdir()
    retained = home / "untouched.json"
    retained.write_text('{"retained":true}', encoding="utf-8")
    before = retained.read_bytes()
    with pytest.raises(ValueError, match="ownership"):
        StandaloneRuntime(home, *runtime_files, Path(pandoc).resolve())
    assert retained.read_bytes() == before and not calls and not (home / "engine.lock").exists()
    retained.unlink()
    write_json(home / "owner.json", {**OWNER, "app_id": "different-test-owner"})
    with pytest.raises(ValueError, match="different owner"):
        StandaloneRuntime(home, *runtime_files, Path(pandoc).resolve())
    assert not calls


def test_actual_quickjs_status_and_restart_restore(runtime, runtime_files, pandoc, tmp_path):
    snapshot = runtime.runner.status()
    assert snapshot["ready"] and snapshot["backend"] == "quickjs-wasm"
    research_id = create_local(runtime, tmp_path)
    saved = runtime.service.status(research_id, include_materials=False)
    # A prior owned cache is ordinary retained data; restarting never deletes it.
    retained_cache = runtime.home / "matplotlib" / "retained-cache.json"
    retained_cache.parent.mkdir()
    retained_cache.write_bytes(b'{"retained":true}')
    runtime.close()
    restored = StandaloneRuntime(runtime.home, *runtime_files, Path(pandoc).resolve())
    try:
        assert restored.service.status(research_id, include_materials=False) == saved
        assert restored.runner.status()["ready"]
        assert retained_cache.read_bytes() == b'{"retained":true}'
    finally:
        restored.close()


def test_main_precreated_empty_directories_can_be_owned(tmp_path, runtime_files, pandoc):
    home = tmp_path / "seeded-home"
    (home / "temp").mkdir(parents=True)
    engine = StandaloneRuntime(home, *runtime_files, Path(pandoc).resolve())
    try:
        assert loads_json((home / "owner.json").read_bytes()) == OWNER
    finally:
        engine.close()


def test_unmarked_plotting_directory_is_not_adopted(tmp_path, runtime_files, pandoc):
    home = tmp_path / "unmarked-home"
    directory = home / "matplotlib"
    directory.mkdir(parents=True)
    with pytest.raises(ValueError, match="ownership"):
        StandaloneRuntime(home, *runtime_files, Path(pandoc).resolve())
    assert directory.is_dir() and not (home / "owner.json").exists()


def test_runner_and_recovery_follow_owned_environment_without_plotting(tmp_path, monkeypatch):
    events = []
    home = tmp_path / "owned-home"
    resources = tmp_path / "resources"
    quickjs = resources / "quickjs-runtime"
    fonts = resources / "fonts"
    quickjs.mkdir(parents=True)
    fonts.mkdir()
    node, pandoc = resources / "node", resources / "pandoc"
    node.write_bytes(b"test executable placeholder; never executed")
    pandoc.write_bytes(b"test executable placeholder; never executed")
    monkeypatch.setenv("TYPST_FONT_PATHS", str(fonts))
    original_import = builtins.__import__

    def observe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "numpy" or name.startswith("numpy.") or name == "matplotlib" or name.startswith("matplotlib."):
            raise ImportError("Plotting libraries are not available in this runtime")
        return original_import(name, globals, locals, fromlist, level)

    class Controller:
        def __init__(self, *args, **kwargs):
            assert threading.current_thread() is threading.main_thread()
            assert loads_json((home / "owner.json").read_bytes()) == OWNER
            assert os.environ["PYPANDOC_PANDOC"] == str(pandoc)
            assert os.environ["PF_NODE_BIN"] == str(node)
            assert os.environ["TYPST_FONT_PATHS"] == str(fonts)
            assert not events
            events.append("runner")

        def close(self, *, deadline=None):
            pass

    class Service:
        def __init__(self, *args, **kwargs):
            assert events == ["runner"]
            events.append("service-recovery")

        def close(self, *, deadline=None):
            pass

    monkeypatch.setattr(builtins, "__import__", observe_import)
    monkeypatch.setattr(standalone_runtime, "QuickJSRunner", Controller)
    monkeypatch.setattr(standalone_runtime, "WorkflowService", Service)
    engine = StandaloneRuntime(home, quickjs, node, pandoc)
    engine.close()
    assert events == ["runner", "service-recovery"]


def test_runner_initialization_failure_stops_recovery_and_releases_home_lease(tmp_path, monkeypatch):
    home = tmp_path / "owned-home"
    resources = tmp_path / "resources"
    quickjs = resources / "quickjs-runtime"
    quickjs.mkdir(parents=True)
    node, pandoc = resources / "node", resources / "pandoc"
    node.write_bytes(b"test executable placeholder; never executed")
    pandoc.write_bytes(b"test executable placeholder; never executed")
    monkeypatch.delenv("TYPST_FONT_PATHS", raising=False)
    def unavailable_runner(*args, **kwargs):
        raise RuntimeError("Synthetic unavailable QuickJS runtime")

    monkeypatch.setattr(standalone_runtime, "QuickJSRunner", unavailable_runner)
    monkeypatch.setattr(standalone_runtime, "WorkflowService", lambda *a, **kw: pytest.fail("Recovery started after native initialization failed"))
    for _ in range(2):
        with pytest.raises(RuntimeError, match="Synthetic unavailable QuickJS runtime"):
            StandaloneRuntime(home, quickjs, node, pandoc)
    assert loads_json((home / "owner.json").read_bytes()) == OWNER


@pytest.fixture
def synthetic_shutdown_runtime(tmp_path, monkeypatch):
    from test_workflow import FixtureRunner
    resources = tmp_path / "synthetic-resources"
    quickjs = resources / "quickjs-runtime"
    quickjs.mkdir(parents=True)
    node, pandoc = resources / "node", resources / "pandoc"
    node.write_bytes(b"synthetic executable placeholder; never executed")
    pandoc.write_bytes(b"synthetic executable placeholder; never executed")
    monkeypatch.delenv("TYPST_FONT_PATHS", raising=False)

    class Runner(FixtureRunner):
        def __init__(self, *args, **kwargs):
            super().__init__()
            self.shutdown_cleanable = False
            self.close_deadlines = []

        def close(self, *, deadline=None):
            self.close_deadlines.append(deadline)
            if not self.shutdown_cleanable:
                raise ValueError("Synthetic owned worker cleanup remains unconfirmed")

    monkeypatch.setattr(standalone_runtime, "QuickJSRunner", Runner)
    engine = StandaloneRuntime(tmp_path / "synthetic-owned-home", quickjs, node, pandoc)
    source = tmp_path / "synthetic-source"
    source.mkdir()
    (source / "transform.js").write_text("export function transform(values) { return values.slice(); }\n", encoding="utf-8")
    identifier = engine.service.create(str(source), "Verify synthetic shutdown evidence retention and retry.")["id"]
    yield engine, identifier
    engine.runner.shutdown_cleanable = True
    engine.runner.cleanable = True
    if engine.runner.release:
        engine.runner.release.set()
    engine.close()


def test_shutdown_failure_keeps_runtime_home_lease_and_allows_preservation_then_retry(synthetic_shutdown_runtime):
    engine, identifier = synthetic_shutdown_runtime
    owner_bytes = (engine.home / "owner.json").read_bytes()
    with pytest.raises(WorkflowError) as rejected:
        engine.close()
    assert rejected.value.code == "CLEANUP_UNCONFIRMED" and engine._closed is False
    assert engine.service._closed is True
    with pytest.raises(ValueError, match="Another operation"):
        with file_lock(engine.home / "engine.lock"):
            pytest.fail("Failed shutdown released the ownership lease")
    assert engine.service.status(identifier)["id"] == identifier
    saved = engine.service.record_inference(identifier, receipt("started"))
    assert engine.service.artifact_path(identifier, saved["artifactId"]).is_file()
    with pytest.raises(ValueError, match="closed"):
        engine.service.create(str(engine.home.parent / "synthetic-source"), "No new study during shutdown.")
    engine.runner.shutdown_cleanable = True
    engine.close()
    engine.close()
    assert engine._closed is True and len(engine.runner.close_deadlines) == 2
    assert (engine.home / "owner.json").read_bytes() == owner_bytes
    with file_lock(engine.home / "engine.lock"):
        pass


def test_shutdown_runtime_shares_one_deadline_and_keeps_lease_when_budget_is_exhausted(synthetic_shutdown_runtime, monkeypatch):
    engine, _ = synthetic_shutdown_runtime
    engine.runner.shutdown_cleanable = True
    started, elapsed, deadlines = time.monotonic(), [0], []
    original_close = engine.service.close

    def late_service_close(*, deadline):
        deadlines.append(deadline)
        original_close(deadline=deadline)
        elapsed[0] = 31

    with monkeypatch.context() as clock_patch:
        clock_patch.setattr(standalone_runtime, "time", SimpleNamespace(monotonic=lambda: started + elapsed[0]))
        clock_patch.setattr(engine.service, "close", late_service_close)
        with pytest.raises(WorkflowError) as rejected:
            engine.close()
        assert rejected.value.code == "CLEANUP_UNCONFIRMED" and engine._closed is False
    assert deadlines == [started + 30] and engine.runner.close_deadlines == deadlines
    with pytest.raises(ValueError, match="Another operation"):
        with file_lock(engine.home / "engine.lock"):
            pytest.fail("Expired shutdown released the ownership lease")
    engine.close()
    assert engine._closed is True


def test_shutdown_main_keeps_command_loop_after_failure_and_exits_only_after_retry(synthetic_shutdown_runtime, monkeypatch):
    engine, identifier = synthetic_shutdown_runtime
    original_status = engine.runner.status

    def status_and_enable_cleanup():
        engine.runner.shutdown_cleanable = True
        return original_status()

    monkeypatch.setattr(engine.runner, "status", status_and_enable_cleanup)
    monkeypatch.setattr(ipc, "StandaloneRuntime", lambda *args: engine)
    requests = [frame("first", "shutdown"), frame("runtime", "runtime.status"), frame("list", "workflow.list"),
                frame("retained", "workflow.status", researchId=identifier, includeMaterials=False),
                frame("receipt", "workflow.recordInference", researchId=identifier, receipt=receipt("started")),
                frame("new", "workflow.create", source="https://github.com/fixture-owner/fixture", goal="Must not create a new study."),
                frame("retry", "shutdown"), frame("after", "runtime.status")]
    incoming = io.BytesIO(b"".join((json.dumps(item) + "\n").encode() for item in requests))
    output = io.BytesIO()
    monkeypatch.setattr(ipc.sys, "stdin", SimpleNamespace(buffer=incoming))
    monkeypatch.setattr(ipc.sys, "stdout", SimpleNamespace(buffer=output))
    monkeypatch.setattr(ipc.sys, "stderr", io.StringIO())
    args = [part for name, value in (("home", engine.home), ("runtime-root", engine.runtime_root),
                                    ("node", engine.node), ("pandoc", engine.pandoc)) for part in ("--" + name, str(value))]
    assert ipc.main(args) == 0
    replies = [loads_json(raw) for raw in output.getvalue().splitlines()]
    assert [reply["id"] for reply in replies] == [item["id"] for item in requests[:-1]]
    assert replies[0]["ok"] is False and replies[0]["error"]["code"] == "CLEANUP_UNCONFIRMED"
    assert all(reply["ok"] for reply in replies[1:5])
    assert replies[2]["result"][0]["id"] == identifier and replies[3]["result"]["id"] == identifier
    assert replies[5]["ok"] is False and replies[5]["error"]["code"] == "CANCELLED"
    assert replies[6] == {"id": "retry", "ok": True, "result": {"closed": True}}
    assert engine._closed is True and len(engine.runner.close_deadlines) == 2


def test_ipc_real_process_has_json_stdout_and_explicit_shutdown(tmp_path, runtime_files, pandoc):
    env = {k: v for k, v in os.environ.items() if k not in {"PF_HOME", "PF_NODE_BIN", "TYPST_FONT_PATHS"}}
    child = subprocess.Popen([sys.executable, "-I", "-B", "-m", "paper_factory.ipc", "--home", str(tmp_path / "owned-process"),
                              "--runtime-root", str(runtime_files[0]), "--node", str(runtime_files[1]), "--pandoc", str(Path(pandoc).resolve())],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        for identifier, method in (("status", "runtime.status"), ("list", "workflow.list"), ("exit", "shutdown")):
            child.stdin.write((json.dumps({"id": identifier, "method": method, "params": {}}) + "\n").encode())
            child.stdin.flush()
            value = loads_json(child.stdout.readline())
            assert value["id"] == identifier and value["ok"], value
            if method == "runtime.status":
                assert value["result"]["ready"]
            elif method == "workflow.list":
                assert value["result"] == []
        child.stdin.close()
        assert child.wait(timeout=15) == 0
        assert child.stdout.read() == b""
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        for stream in (child.stdin, child.stdout, child.stderr):
            stream.close()


def test_cancel_interrupts_blocked_collection_before_serial_cancel(runtime, tmp_path, monkeypatch):
    research_id = create_local(runtime, tmp_path)
    runtime.service.submit_proposal(research_id, protocol())
    entered = threading.Event()
    cancelled = threading.Event()
    def blocked_collector(queries, root, *, limit, cancel):
        entered.set()
        deadline = time.monotonic() + 5
        while not cancel() and time.monotonic() < deadline:
            cancelled.wait(0.01)
        assert cancel(), "Input reader failed to cancel the blocked operation"
        cancelled.set()
        return {"sources": [], "cancelled": True}
    monkeypatch.setattr(standalone_runtime.literature, "collect", blocked_collector)
    output = io.BytesIO()
    dispatcher = ipc.Dispatcher(runtime, output)
    dispatcher.submit(frame("collect", "workflow.collectLiterature", researchId=research_id))
    assert entered.wait(5)
    dispatcher.submit(frame("cancel", "workflow.cancel", researchId=research_id))
    dispatcher.finish()
    values = [loads_json(raw) for raw in output.getvalue().splitlines()]
    assert cancelled.is_set()
    assert values[0]["error"]["code"] == "LITERATURE_EVIDENCE_INSUFFICIENT"
    assert values[1]["ok"] and values[1]["result"]["status"] == "cancelled"


@pytest.fixture
def synthetic_cancel_engine(tmp_path, monkeypatch):
    from test_workflow import FixtureRunner, collect, prepare
    from paper_factory.workflow import WorkflowService
    source = tmp_path / "synthetic-source"
    source.mkdir()
    (source / "transform.js").write_text("export function transform(values) { return values.slice(); }\n", encoding="utf-8")
    runner = FixtureRunner()
    service = WorkflowService(tmp_path / "synthetic-home", runner=runner, collector=collect)
    research_id = service.create(str(source), "Verify the synthetic IPC cancellation acknowledgement contract.")["id"]
    prepare(service, research_id)
    runtime = SimpleNamespace(service=service, set_cancel=lambda callback: None, close=service.close)
    yield runtime, runner, research_id
    runner.cleanable = True
    if runner.release:
        runner.release.set()
    service.close()


@pytest.fixture
def synthetic_export_resolution(synthetic_cancel_engine):
    from paper_factory.workflow import _freeze
    from paper_factory.workflow_models import Workflow
    from paper_factory.workspace import Workspace
    runtime, runner, research_id = synthetic_cancel_engine
    ws = Workspace(runtime.service.root / research_id)
    record = ws.get("workflow", research_id, Workflow)
    root = ws.path("research/exports/export-attempt-fixture")
    root.mkdir(parents=True)
    files = {"export-md": ("paper.md", b"# Synthetic manuscript\n\n![Computed figure.](figure-1.png)\n"),
             "export-tex": ("paper.tex", br"\pandocbounded{\includegraphics[keepaspectratio,alt={Computed figure.}]{figure-1.png}}"),
             "export-pdf": ("paper.pdf", b"Synthetic PDF bytes; never rendered"),
             "export-figure-1": ("figure-1.png", b"\x89PNG\r\n\x1a\nSynthetic frozen figure bytes; never rendered")}
    paths = {}
    for key, (name, content) in files.items():
        path = root / name
        path.write_bytes(content)
        _freeze(ws, record, key, path)
        paths[key] = path
    ws.save("workflow", record)
    yield runtime, runner, research_id, ws, record, paths


@pytest.mark.parametrize("artifact_id", ["export-md", "export-tex"])
def test_artifact_resolve_returns_verified_companions_without_modifying_bytes(synthetic_export_resolution, artifact_id):
    runtime, runner, research_id, _, _, paths = synthetic_export_resolution
    original = {key: path.read_bytes() for key, path in paths.items()}
    dispatcher = ipc.Dispatcher(runtime, io.BytesIO())
    try:
        result = dispatcher.execute("artifact.resolve", {"researchId": research_id, "artifactId": artifact_id})
    finally:
        dispatcher._pool.shutdown(wait=True)
    primary, figure = paths[artifact_id], paths["export-figure-1"]
    assert result == {"path": str(primary), "sha256": digest_file(primary), "size": primary.stat().st_size,
                      "companions": [{"name": "figure-1.png", "path": str(figure),
                                      "sha256": digest_file(figure), "size": figure.stat().st_size}]}
    assert {key: path.read_bytes() for key, path in paths.items()} == original and runner.calls == 0


@pytest.mark.parametrize("artifact_id", ["context", "export-pdf", "export-figure-1"])
def test_artifact_resolve_regular_artifacts_have_empty_companions(synthetic_export_resolution, artifact_id):
    runtime, _, research_id, _, _, _ = synthetic_export_resolution
    dispatcher = ipc.Dispatcher(runtime, io.BytesIO())
    try:
        result = dispatcher.execute("artifact.resolve", {"researchId": research_id, "artifactId": artifact_id})
    finally:
        dispatcher._pool.shutdown(wait=True)
    path = runtime.service.artifact_path(research_id, artifact_id)
    assert result == {"path": str(path), "sha256": digest_file(path), "size": path.stat().st_size, "companions": []}


@pytest.mark.parametrize("artifact_id", ["export-md", "export-tex"])
@pytest.mark.parametrize("change", ["missing-file", "changed-bytes", "missing-entry", "duplicate-name", "unsafe-name", "other-directory", "markdown-reference"])
def test_artifact_resolve_refuses_incomplete_or_changed_figure_inventory(synthetic_export_resolution, artifact_id, change):
    from paper_factory.workflow import _freeze
    runtime, runner, research_id, ws, record, paths = synthetic_export_resolution
    figure = paths["export-figure-1"]
    if change == "missing-file":
        figure.unlink()
    elif change == "changed-bytes":
        figure.write_bytes(b"Changed PNG bytes with an untrusted image")
    elif change == "missing-entry":
        del record.artifacts["export-figure-1"]
    elif change == "duplicate-name":
        record.artifacts["export-figure-2"] = record.artifacts["export-figure-1"].model_copy()
    elif change in {"unsafe-name", "other-directory"}:
        destination = figure.with_name("unowned-image.png") if change == "unsafe-name" else ws.path("research/other/figure-1.png")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(figure.read_bytes())
        _freeze(ws, record, "export-figure-1", destination)
    else:
        paths["export-md"].write_bytes(b"# Synthetic manuscript\n\n![Unowned figure.](../outside.png)\n")
        _freeze(ws, record, "export-md", paths["export-md"])
    ws.save("workflow", record)
    dispatcher = ipc.Dispatcher(runtime, io.BytesIO())
    try:
        with pytest.raises(WorkflowError) as rejected:
            dispatcher.execute("artifact.resolve", {"researchId": research_id, "artifactId": artifact_id})
        assert rejected.value.code == "ARTIFACT_CHANGED" and runner.calls == 0
    finally:
        dispatcher._pool.shutdown(wait=True)


def test_artifact_resolve_refuses_tex_references_outside_frozen_inventory(synthetic_export_resolution):
    from paper_factory.workflow import _freeze
    runtime, runner, research_id, ws, record, paths = synthetic_export_resolution
    paths["export-tex"].write_bytes(br"\includegraphics{../unowned.png}")
    _freeze(ws, record, "export-tex", paths["export-tex"])
    ws.save("workflow", record)
    with pytest.raises(WorkflowError) as rejected:
        runtime.service.resolve_artifact(research_id, "export-tex")
    assert rejected.value.code == "ARTIFACT_CHANGED" and runner.calls == 0


def test_cancellation_ack_waits_for_owned_worker_cleanup_before_serial_ipc_reply(synthetic_cancel_engine, monkeypatch):
    runtime, runner, research_id = synthetic_cancel_engine
    requested, release = threading.Event(), threading.Event()

    def delayed_cleanup(*args, cancel, on_handle, **kwargs):
        runner.calls += 1
        on_handle({"kind": "fixture", "pid": 123, "simulation": True})
        runner.entered.set()
        deadline = time.monotonic() + 5
        while not cancel() and time.monotonic() < deadline:
            requested.wait(0.01)
        assert cancel()
        requested.set()
        assert release.wait(5)
        return {"status": "cancelled", "cleanup_confirmed": True, "simulation": True}

    monkeypatch.setattr(runner, "run", delayed_cleanup)
    monkeypatch.setattr(runner, "stop", lambda handle: False)
    runtime.service.start_experiment(research_id)
    assert runner.entered.wait(2)
    output = io.BytesIO()
    dispatcher = ipc.Dispatcher(runtime, output)
    try:
        dispatcher.submit(frame("cancel", "workflow.cancel", researchId=research_id))
        assert requested.wait(2)
        assert output.getvalue() == b""
        pending = runtime.service.status(research_id)
        assert pending["status"] == "running" and pending["cleanup_pending"] is True
        assert "active_handle" not in pending and "cleanup_confirmed" not in pending
    finally:
        release.set()
        dispatcher.finish()
    replies = [loads_json(raw) for raw in output.getvalue().splitlines()]
    assert len(replies) == 1 and replies[0]["id"] == "cancel" and replies[0]["ok"] is True
    result = replies[0]["result"]
    assert result["status"] == "cancelled" and result["cleanup_pending"] is False
    assert result["cleanup_confirmed"] is True and "active_handle" not in result and runner.calls == 1


def test_cancellation_ack_failure_and_retry_preserve_engine_evidence(synthetic_cancel_engine):
    from test_workflow import finished
    runtime, runner, research_id = synthetic_cancel_engine
    runner.cleanup_confirmed = False
    runner.cleanable = False
    runtime.service.start_experiment(research_id)
    initial = finished(runtime.service, research_id)
    runtime.service._jobs[research_id].result(timeout=2)
    original_execution = runtime.service.artifact_path(research_id, "execution").read_bytes()
    output = io.BytesIO()
    dispatcher = ipc.Dispatcher(runtime, output)
    try:
        dispatcher.submit(frame("first", "workflow.cancel", researchId=research_id))
        dispatcher._pool.submit(lambda: None).result(timeout=2)
        failed = loads_json(output.getvalue().splitlines()[0])
        assert failed["id"] == "first" and failed["ok"] is False
        assert failed["error"]["code"] == "CLEANUP_UNCONFIRMED" and "result" not in failed
        assert runtime.service.status(research_id)["cleanup_pending"] is True
        runner.cleanable = True
        dispatcher.submit(frame("retry", "workflow.cancel", researchId=research_id))
        dispatcher._pool.submit(lambda: None).result(timeout=5)
        succeeded = loads_json(output.getvalue().splitlines()[1])
        assert succeeded["id"] == "retry" and succeeded["ok"] is True
        result = succeeded["result"]
        assert result["status"] == "cancelled" and result["stage"] == "analyzed"
        assert result["cleanup_confirmed"] is True and result["cleanup_pending"] is False
        assert result["execution_attempt"] == initial["execution_attempt"] == 1 and runner.calls == 1
        assert runtime.service.artifact_path(research_id, "execution").read_bytes() == original_execution
    finally:
        runner.cleanable = True
        dispatcher.finish()


def test_literature_search_original_reply_is_frozen(runtime, tmp_path, monkeypatch):
    from test_workflow import collect
    research_id = create_local(runtime, tmp_path)
    runtime.service.submit_proposal(research_id, protocol())
    def collector(queries, root, **options):
        evidence = collect(queries, root, **options)
        search = Path(root) / "literature/search-fixture.json"
        write_json(search, {"fixture": "original search reply"})
        evidence["searches"] = [{"query": queries[0], "status": "succeeded", "attempted": True,
                                "raw_path": "literature/search-fixture.json", "sha256": digest_file(search)}]
        return evidence
    monkeypatch.setattr(standalone_runtime.literature, "collect", collector)
    state = runtime.service.collect_literature(research_id)
    search = state["literature"]["searches"][0]
    bindings = [key for key, artifact in state["artifacts"].items() if artifact["sha256"] == search["sha256"] and
                runtime.service.artifact_path(research_id, key).relative_to(runtime.service.root / research_id).as_posix() == "research/" + search["raw_path"]]
    assert len(bindings) == 1
    search_key = bindings[0]
    original = runtime.service.artifact_path(research_id, search_key)
    original.write_text("changed search reply", encoding="utf-8")
    with pytest.raises(WorkflowError, match="changed"):
        runtime.service.artifact_path(research_id, search_key)


def test_inference_receipts_are_hash_bound_append_only_and_export_selected(runtime, tmp_path):
    research_id = create_local(runtime, tmp_path)
    value = receipt()
    result = runtime.service.record_inference(research_id, value)
    original = runtime.service.artifact_path(research_id, result["artifactId"])
    assert digest_file(original) == result["sha256"]
    assert runtime.service.record_inference(research_id, value) == result
    changed = {**value, "text": "Changed output", "textSha256": hashlib.sha256(b"Changed output").hexdigest()}
    with pytest.raises(WorkflowError, match="append-only"):
        runtime.service.record_inference(research_id, changed)
    wrong_hash = {**value, "promptSha256": "0" * 64}
    with pytest.raises(ValueError, match="prompt hash"):
        runtime.service.record_inference(research_id, wrong_hash)
    runtime.service.record_inference(research_id, receipt("started"))
    state = runtime.service.status(research_id, include_materials=False)
    assert len([key for key in state["artifacts"] if key.startswith("model-evidence-")]) == 2
    assert len([key for key in state["artifacts"] if key.startswith("model-journal-")]) == 2
    assert loads_json(original.read_bytes()) == value


def test_actual_guest_analysis_and_exports_include_model_receipts(runtime, tmp_path, monkeypatch):
    """Synthetic protocol evidence; validates real guest/analysis/converters, not a study."""
    from test_workflow import collect, manuscript, REVIEW, STUDY_REVIEW, MANUSCRIPT_REVIEW
    research_id = create_local(runtime, tmp_path)
    runtime.service.submit_proposal(research_id, protocol())
    runtime.service.record_inference(research_id, receipt("started"))
    runtime.service.record_inference(research_id, receipt())
    monkeypatch.setattr(standalone_runtime.literature, "collect", collect)
    runtime.service.collect_literature(research_id)
    runtime.service.submit_study_review(research_id, STUDY_REVIEW)
    code = """export default function run() {
      const observations=[], inputs=[];
      for(const seed of [11,37]) for(let i=0;i<3;i++) {
        const x=seed+i, expected=x+1;
        const actual=JSON.parse(callProduction(JSON.stringify([x])));
        inputs.push({seed,i,x,expected,actual});
        for(const [condition, answer] of [['production',actual],['ablation',x]])
          observations.push({unit_id:'case-'+i,seed,condition,metric:'error',value:Number(answer!==expected)});
      }
      return {observations, controls:[
        {name:'positive known result',passed:inputs.every(x=>x.actual===x.expected),details:'Actual production result matches independent arithmetic annotations.'},
        {name:'negative deliberate increment removal',passed:inputs.every(x=>x.x!==x.expected),details:'Removing the increment causes an independently detected mismatch.'}],
        fixtures:[JSON.parse(retainFixture('synthetic-input-and-oracle.json',JSON.stringify(inputs)))]};
    }"""
    runtime.service.submit_code(research_id, {"runtime": "quickjs", "entrypoint": "experiment.mjs",
        "files": [{"path": "experiment.mjs", "content": code}], "explanation": "Synthetic actual production fixture and independently computed oracle checks."}, REVIEW)
    runtime.service.start_experiment(research_id)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        state = runtime.service.status(research_id)
        if state["status"] != "running":
            break
        time.sleep(0.02)
    assert state["stage"] == "analyzed", state
    assert state["execution"]["cleanup_confirmed"] and state["execution"]["production_calls"][0]["calls"] == 6
    assert state["analysis"]["results"]["error.paired_2_minus_1.mean"]["value"] == 1
    draft = manuscript()
    draft["title"] = protocol()["title"]
    runtime.service.submit_manuscript(research_id, draft, MANUSCRIPT_REVIEW)
    exported = runtime.service.export(research_id)
    assert exported["status"] == "completed"
    with zipfile.ZipFile(runtime.service.artifact_path(research_id, "reproducibility")) as archive:
        names = archive.namelist()
        assert len([name for name in names if name.startswith("model-evidence/")]) == 4
        assert any(name.endswith("-completed.json") and not "/journal-" in name for name in names)
        inventory = loads_json(archive.read("inventory.json"))
        assert all(hashlib.sha256(archive.read(name)).hexdigest() == item["sha256"] for name, item in inventory.items())


def repository_archive(commit, items):
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        for name, content in items.items():
            archive.writestr("fixture-" + commit + "/" + name, content)
    return raw.getvalue()


def github_client(monkeypatch, archive, commit="a" * 40):
    requested = []
    original = httpx.Client
    def respond(request):
        requested.append(str(request.url))
        if request.url.host == "api.github.com":
            return httpx.Response(200, json={"sha": commit})
        return httpx.Response(200, content=archive)
    monkeypatch.setattr(project.httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    return requested


def test_public_github_uses_fixed_commit_archive_without_git(tmp_path, monkeypatch):
    commit = "a" * 40
    requested = github_client(monkeypatch, repository_archive(commit, {"source.js": "module.exports={calculate:x=>x+1};", ".env": "secret", "node_modules/x.js": "ignored"}))
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: pytest.fail("Remote collection must not use Git or shell"))
    ws = project.ingest("https://github.com/fixture-owner/fixture", tmp_path / "workspace")
    imported = ws.latest("project", Project)
    assert imported.source_commit == commit
    assert [asset.path for asset in imported.assets] == ["source.js"]
    assert requested == ["https://api.github.com/repos/fixture-owner/fixture/commits/HEAD", "https://codeload.github.com/fixture-owner/fixture/zip/" + commit]


@pytest.mark.parametrize("items", [{"../escape.txt": "no"}, {"x.js": "a", "X.js": "b"}])
def test_github_archive_rejects_escape_and_portable_duplicates(tmp_path, monkeypatch, items):
    github_client(monkeypatch, repository_archive("a" * 40, items))
    with pytest.raises(ValueError):
        project.ingest("https://github.com/fixture-owner/fixture", tmp_path / "workspace")
    assert not (tmp_path / "workspace").exists() and not (tmp_path / "escape.txt").exists()


def test_generic_remote_and_credentials_rejected_before_network(tmp_path, monkeypatch):
    monkeypatch.setattr(project.httpx, "Client", lambda **kw: pytest.fail("Invalid authorities must fail before HTTP"))
    for source in ("https://user:secret@github.com/owner/repo", "https://example.invalid/owner/repo", "ssh://git@github.com/owner/repo"):
        with pytest.raises(ValueError, match="public GitHub"):
            project.ingest(source, tmp_path / "workspace")

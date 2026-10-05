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
import zipfile

import httpx
import pytest

from paper_factory import ipc, project, standalone_runtime
from paper_factory.autonomous.models import ResearchPlan
from paper_factory.models import Project
from paper_factory.standalone_runtime import OWNER, StandaloneRuntime
from paper_factory.workflow import WorkflowError
from paper_factory.workspace import digest_file, loads_json, write_json


@pytest.fixture(autouse=True)
def isolated_runtime_environment(monkeypatch):
    # StandaloneRuntime owns a process in production. Preserve the test host's
    # environment when several isolated controllers share pytest's process.
    for name in ("PF_NODE_BIN", "PYPANDOC_PANDOC", "MPLCONFIGDIR", "TYPST_FONT_PATHS"):
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
    for name in ("PF_NODE_BIN", "PYPANDOC_PANDOC", "MPLCONFIGDIR", "TYPST_FONT_PATHS"):
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
    return {"feasible": True, "reason": "A public transformation supports independently annotated fixture checks.",
            "title": "Controlled production transformation fixture validation", "question": "How does the transformation preserve annotated fixture values?",
            "runtime": "quickjs", "source_files": ["source.js"], "production_entrypoint": "source.js:calculate",
            "dependencies": [], "conditions": ["production", "ablation"],
            "metrics": [{"name": "error", "unit": "events", "description": "Independent expected value mismatches."}],
            "comparator": "Remove the increment rule in an explicit comparator.",
            "independent_oracle": "Known arithmetic fixture annotations define expected values.",
            "sampling_unit": "An independently seeded annotated fixture.", "units_per_seed": 3, "seeds": [11, 37],
            "parameters": {}, "procedure": ["Generate seeded annotations.", "Invoke unchanged source and comparator.", "Record paired errors and controls."],
            "analysis_method": "Descriptive means paired by fixture and seed.",
            "limitations": ["Synthetic fixtures do not represent natural populations.", "Instrumentation affects execution timing."],
            "literature_queries": ["independent software test oracle"]}


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


@pytest.mark.parametrize("method", ["workflow.resumeWriting", "workflow.reviseWriting"])
def test_authoring_ipc_accepts_only_research_id_and_maps_to_explicit_method(method):
    from types import SimpleNamespace
    valid = {"id": "authoring", "method": method, "params": {"researchId": "research-abcdefabcdef"}}
    assert ipc.request(json.dumps(valid).encode()) == valid
    for params in ({}, {"researchId": "research-abcdefabcdef", "force": True}, {"researchId": "../private"}):
        with pytest.raises(ValueError):
            ipc.request(json.dumps({**valid, "params": params}).encode())
    calls = []
    service = SimpleNamespace(resume_writing=lambda identifier: calls.append(("resume", identifier)) or {"status": "ready"},
                              revise_writing=lambda identifier: calls.append(("revise", identifier)) or {"status": "ready"},
                              collect_literature=None, start_experiment=None, cancel=None, export=None)
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), io.BytesIO())
    try:
        assert dispatcher.execute(valid["method"], valid["params"]) == {"status": "ready"}
        assert calls == [("resume" if method.endswith("resumeWriting") else "revise", "research-abcdefabcdef")]
    finally:
        dispatcher._pool.shutdown(wait=True)


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
    runtime.close()
    restored = StandaloneRuntime(runtime.home, *runtime_files, Path(pandoc).resolve())
    try:
        assert restored.service.status(research_id, include_materials=False) == saved
        assert restored.runner.status()["ready"]
    finally:
        restored.close()


def test_main_precreated_empty_directories_can_be_owned(tmp_path, runtime_files, pandoc):
    home = tmp_path / "seeded-home"
    for name in ("temp", "matplotlib"):
        (home / name).mkdir(parents=True)
    engine = StandaloneRuntime(home, *runtime_files, Path(pandoc).resolve())
    try:
        assert loads_json((home / "owner.json").read_bytes()) == OWNER
    finally:
        engine.close()


def test_native_plotting_precedes_runner_and_recovery_after_owned_environment(tmp_path, monkeypatch):
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
    monkeypatch.setenv("MPLCONFIGDIR", str(home / "matplotlib"))
    import matplotlib
    original_import, original_use = builtins.__import__, matplotlib.use

    def observe_import(name, globals=None, locals=None, fromlist=(), level=0):
        result = original_import(name, globals, locals, fromlist, level)
        if globals and globals.get("__name__") == standalone_runtime.__name__ and name in {"matplotlib", "matplotlib.pyplot"}:
            assert threading.current_thread() is threading.main_thread()
            assert loads_json((home / "owner.json").read_bytes()) == OWNER
            assert os.environ["MPLCONFIGDIR"] == str(home / "matplotlib")
            assert os.environ["PYPANDOC_PANDOC"] == str(pandoc)
            assert os.environ["PF_NODE_BIN"] == str(node)
            assert os.environ["TYPST_FONT_PATHS"] == str(fonts)
            events.append(name)
        return result

    def observe_backend(backend):
        events.append("backend:" + backend)
        return original_use(backend)

    class Controller:
        def __init__(self, *args, **kwargs):
            assert events == ["matplotlib", "backend:Agg", "matplotlib.pyplot"]
            events.append("runner")

        def close(self):
            pass

    class Service:
        def __init__(self, *args, **kwargs):
            assert events == ["matplotlib", "backend:Agg", "matplotlib.pyplot", "runner"]
            events.append("service-recovery")

        def close(self):
            pass

    monkeypatch.setattr(builtins, "__import__", observe_import)
    monkeypatch.setattr(matplotlib, "use", observe_backend)
    monkeypatch.setattr(standalone_runtime, "QuickJSRunner", Controller)
    monkeypatch.setattr(standalone_runtime, "WorkflowService", Service)
    engine = StandaloneRuntime(home, quickjs, node, pandoc)
    engine.close()
    assert events == ["matplotlib", "backend:Agg", "matplotlib.pyplot", "runner", "service-recovery"]


def test_native_plotting_failure_stops_recovery_and_releases_home_lease(tmp_path, monkeypatch):
    home = tmp_path / "owned-home"
    resources = tmp_path / "resources"
    quickjs = resources / "quickjs-runtime"
    quickjs.mkdir(parents=True)
    node, pandoc = resources / "node", resources / "pandoc"
    node.write_bytes(b"test executable placeholder; never executed")
    pandoc.write_bytes(b"test executable placeholder; never executed")
    monkeypatch.delenv("TYPST_FONT_PATHS", raising=False)
    monkeypatch.setenv("MPLCONFIGDIR", str(home / "matplotlib"))
    original_import = builtins.__import__

    def unavailable_plotting(name, globals=None, locals=None, fromlist=(), level=0):
        if globals and globals.get("__name__") == standalone_runtime.__name__ and name == "matplotlib.pyplot":
            raise ImportError("Synthetic unavailable native plotting")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", unavailable_plotting)
    monkeypatch.setattr(standalone_runtime, "QuickJSRunner", lambda *a, **kw: pytest.fail("Runner started after native initialization failed"))
    monkeypatch.setattr(standalone_runtime, "WorkflowService", lambda *a, **kw: pytest.fail("Recovery started after native initialization failed"))
    for _ in range(2):
        with pytest.raises(ImportError, match="Synthetic unavailable native plotting"):
            StandaloneRuntime(home, quickjs, node, pandoc)
    assert loads_json((home / "owner.json").read_bytes()) == OWNER


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
    runtime.service.submit_plan(research_id, protocol())
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


def test_literature_search_original_reply_is_frozen(runtime, tmp_path, monkeypatch):
    from test_workflow import collect
    research_id = create_local(runtime, tmp_path)
    runtime.service.submit_plan(research_id, protocol())
    def collector(queries, root, **options):
        evidence = collect(queries, root, **options)
        search = Path(root) / "literature/search-fixture.json"
        write_json(search, {"fixture": "original search reply"})
        evidence["searches"] = [{"query": queries[0], "status": "succeeded", "attempted": True,
                                "raw_path": "literature/search-fixture.json", "sha256": digest_file(search)}]
        return evidence
    monkeypatch.setattr(standalone_runtime.literature, "collect", collector)
    state = runtime.service.collect_literature(research_id)
    assert "literature-search-0" in state["artifacts"]
    original = runtime.service.artifact_path(research_id, "literature-search-0")
    original.write_text("changed search reply", encoding="utf-8")
    with pytest.raises(WorkflowError, match="changed"):
        runtime.service.artifact_path(research_id, "literature-search-0")


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
    from test_workflow import collect, manuscript, REVIEW
    research_id = create_local(runtime, tmp_path)
    runtime.service.submit_plan(research_id, protocol())
    runtime.service.record_inference(research_id, receipt("started"))
    runtime.service.record_inference(research_id, receipt())
    monkeypatch.setattr(standalone_runtime.literature, "collect", collect)
    runtime.service.collect_literature(research_id)
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
    runtime.service.submit_manuscript(research_id, draft, REVIEW)
    import matplotlib
    monkeypatch.setenv("TYPST_FONT_PATHS", str(Path(matplotlib.get_data_path()) / "fonts/ttf"))
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

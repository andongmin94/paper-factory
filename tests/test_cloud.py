"""Cloud JSON transport over real controller state and explicitly synthetic runners."""

import base64
import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from paper_factory import cloud
from paper_factory.workflow import WorkflowError, WorkflowService
from paper_factory.workspace import digest_file, write_json
from test_workflow import BUNDLE, REVIEW, FixtureRunner, collect, protocol


class CloudFixtureRunner(FixtureRunner):
    """Only test observations are synthesized; submitted source is never executed."""

    def run(self, source_dir, bundle_dir, output_dir, *, runtime, entrypoint, production_entrypoint,
            timeout_seconds, cancel, on_handle):
        assert production_entrypoint == "transform.py:transform"
        assert runtime == "python" and timeout_seconds == 300
        assert Path(source_dir, "transform.py").is_file() and Path(bundle_dir, entrypoint).is_file()
        self.calls += 1
        on_handle({"kind": "fixture", "pid": 123, "simulation": True})
        write_json(Path(output_dir) / "observations.json", copy.deepcopy(self.outputs))
        return {"status": "succeeded", "simulation": True, "exit_code": 0,
                "coverage_mechanism": "synthetic", "coverage_truncated": False,
                "cleanup_confirmed": True,
                "production_calls": [{"path": "transform.py", "function": "transform", "calls": 6}]}


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "matplotlib"))
    source = tmp_path / "source"
    source.mkdir()
    (source / "transform.py").write_text("def transform(values):\n    return list(values)\n", encoding="utf-8")
    inputs = tmp_path / "fixed-inputs"
    evidence = collect(["fixture oracle"], inputs, limit=6, cancel=None)
    manifest = inputs / "manifest.json"
    write_json(manifest, evidence)
    runner = CloudFixtureRunner()
    closed = []

    class TrackedService(WorkflowService):
        def close(self):
            try:
                return super().close()
            finally:
                closed.append(self)

    def factory(home, **kwargs):
        assert kwargs["runner"] is None
        return TrackedService(home, runner=runner, collector=kwargs["collector"])

    return {"home": tmp_path / "home", "source": source, "runner": runner, "factory": factory,
            "manifest": manifest, "inputs": inputs, "closed": closed}


def invoke(fixture, capsys, command, *args):
    code = cloud.main(["--data", str(fixture["home"]), "--literature-manifest", str(fixture["manifest"]),
                       command, *map(str, args)], service_factory=fixture["factory"])
    output = capsys.readouterr()
    assert output.err == ""
    assert fixture["closed"][-1]._closed
    return code, json.loads(output.out)


def ready(fixture, capsys, tmp_path):
    code, state = invoke(fixture, capsys, "create", "--source", fixture["source"],
                         "--goal", "Validate a controlled synthetic transformation study through the Cloud adapter.")
    assert code == 0 and state["stage"] == "created"
    research_id = state["id"]
    for name, value in (("plan", protocol()), ("bundle", copy.deepcopy(BUNDLE)), ("review", REVIEW)):
        write_json(tmp_path / (name + ".json"), value)
    assert invoke(fixture, capsys, "submit-plan", research_id, "--input", tmp_path / "plan.json")[0] == 0
    assert invoke(fixture, capsys, "collect-literature", research_id)[0] == 0
    code, state = invoke(fixture, capsys, "submit-code", research_id, "--input", tmp_path / "bundle.json",
                         "--review", tmp_path / "review.json")
    assert code == 0 and state["stage"] == "code_ready"
    return research_id


def test_json_commands_wait_for_actual_controller_analysis_and_return_frozen_bytes(fixture, capsys, tmp_path):
    research_id = ready(fixture, capsys, tmp_path)
    code, state = invoke(fixture, capsys, "run", research_id)
    assert code == 0 and state["stage"] == "analyzed" and state["status"] == "ready"
    assert fixture["runner"].calls == 1
    code, full = invoke(fixture, capsys, "status", research_id, "--include-materials")
    assert code == 0 and full["analysis"]["results"]["error.condition_1.mean"]["value"] == 0
    assert full["literature"]["sources"][0]["simulation"] is True
    assert full["literature"]["sources"][0]["scope"] == "abstract"
    code, transport = invoke(fixture, capsys, "artifact-bytes", research_id, "observations")
    assert code == 0 and transport["encoding"] == "base64"
    content = base64.b64decode(transport["content"], validate=True)
    assert len(content) == transport["size"] == state["artifacts"]["observations"]["size"]
    assert hashlib.sha256(content).hexdigest() == transport["sha256"] == state["artifacts"]["observations"]["sha256"]
    assert json.loads(content)["observations"][0]["condition"] == "production"


def test_failed_control_remains_terminal_across_cli_process_lifetimes(fixture, capsys, tmp_path):
    fixture["runner"].outputs["controls"][1]["passed"] = False
    research_id = ready(fixture, capsys, tmp_path)
    code, state = invoke(fixture, capsys, "run", research_id)
    assert code == 1 and state["code"] == "CONTROL_FAILED" and state["terminal_control_failure"]
    code, error = invoke(fixture, capsys, "run", research_id)
    assert code == 1 and error["error"]["code"] == "CONTROL_FAILED"
    assert fixture["runner"].calls == 1


def test_missing_json_input_returns_actionable_error_and_closes_controller(fixture, capsys, tmp_path):
    code, state = invoke(fixture, capsys, "create", "--source", fixture["source"], "--goal", "Inspect declared source inputs.")
    code, error = invoke(fixture, capsys, "submit-plan", state["id"], "--input", tmp_path / "missing.json")
    assert code == 1 and error["error"]["code"] == "INPUT_NOT_FOUND"
    assert str(tmp_path) not in json.dumps(error)
    assert invoke(fixture, capsys, "status", state["id"])[1]["stage"] == "created"


def test_artifact_transport_rechecks_bytes_after_controller_resolution(fixture, capsys, monkeypatch):
    _, created = invoke(fixture, capsys, "create", "--source", fixture["source"], "--goal", "Inspect frozen source integrity.")
    with_service = WorkflowService(fixture["home"], runner=fixture["runner"])
    original = with_service.artifact_path

    def changed(research_id, artifact_id):
        path = original(research_id, artifact_id)
        path.write_bytes(path.read_bytes() + b"changed after controller verification")
        return path

    monkeypatch.setattr(with_service, "artifact_path", changed)
    try:
        with pytest.raises(WorkflowError) as error:
            cloud.artifact_bytes(with_service, created["id"], "context")
        assert error.value.code == "ARTIFACT_CHANGED"
    finally:
        with_service.close()


def test_artifact_transport_rejects_oversized_record_before_reading_a_file():
    class OversizedArtifact:
        def status(self, research_id, *, include_materials):
            return {"artifacts": {"reproducibility": {"size": cloud.MAX_ARTIFACT_BYTES + 1, "sha256": "0" * 64}}}

        def artifact_path(self, research_id, artifact_id):
            raise AssertionError("Oversized artifact must not be opened")

    with pytest.raises(WorkflowError) as error:
        cloud.artifact_bytes(OversizedArtifact(), "research-123456abcdef", "reproducibility")
    assert error.value.code == "ARTIFACT_TOO_LARGE"


def test_fixed_literature_retains_exact_bytes_scopes_and_supports_interrupted_copy_retry(fixture, tmp_path):
    importer = cloud.FixedLiteratureCollector(fixture["manifest"])
    root = tmp_path / "retained"
    first = importer(["fixture oracle"], root, limit=6)
    second = importer(["fixture oracle"], root, limit=6)
    assert first == second
    source = first["sources"][0]
    assert source["scope"] == "abstract" and source["simulation"] is True
    assert digest_file(root / source["raw_path"]) == source["sha256"]
    assert (root / source["raw_path"]).read_bytes() == (fixture["inputs"] / source["raw_path"]).read_bytes()
    cancelled = importer(["fixture oracle"], tmp_path / "cancelled", limit=6, cancel=lambda: True)
    assert cancelled["cancelled"] and cancelled["sources"] == []
    assert not (tmp_path / "cancelled").exists()


@pytest.mark.parametrize("target", ["manifest", "raw", "retained"])
def test_fixed_literature_rejects_changed_inputs_without_changing_scope(fixture, tmp_path, target):
    importer = cloud.FixedLiteratureCollector(fixture["manifest"])
    root = tmp_path / "retained"
    if target == "manifest":
        path = fixture["manifest"]
    elif target == "raw":
        path = fixture["inputs"] / "literature/fixture-source.json"
    else:
        importer(["fixture oracle"], root, limit=6)
        path = root / "literature/fixture-source.json"
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(WorkflowError) as error:
        importer(["fixture oracle"], root, limit=6)
    assert error.value.code == "ARTIFACT_CHANGED"


def test_fixed_literature_rejects_undeclared_paths_and_invented_excerpts(fixture):
    manifest = json.loads(fixture["manifest"].read_text(encoding="utf-8"))
    manifest["sources"][0]["raw_path"] = "literature/../private.json"
    write_json(fixture["manifest"], manifest)
    with pytest.raises(ValueError, match="relative"):
        cloud.FixedLiteratureCollector(fixture["manifest"])
    manifest["sources"][0]["raw_path"] = "literature/fixture-source.json"
    manifest["sources"][0]["excerpts"] = ["This fabricated claim is not present in the declared inspected source text. " * 2]
    write_json(fixture["manifest"], manifest)
    importer = cloud.FixedLiteratureCollector(fixture["manifest"])
    with pytest.raises(ValueError, match="retained inspected text"):
        importer(["fixture oracle"], fixture["home"], limit=6)


def test_cloud_import_and_help_need_no_mcp_or_account_runtime(tmp_path):
    script = (
        "import builtins, sys\n"
        "original = builtins.__import__\n"
        "def restricted(name, *args, **kwargs):\n"
        "    if name == 'mcp' or name.startswith('mcp.'):\n"
        "        raise AssertionError('Cloud adapter imported MCP')\n"
        "    return original(name, *args, **kwargs)\n"
        "builtins.__import__ = restricted\n"
        "from paper_factory.cloud import main\n"
        "main(['--help'])\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0 and "--runtime-root" in result.stdout
    assert "artifact-bytes" in result.stdout and result.stderr == ""


@pytest.mark.parametrize("close_failure", [False, True])
@pytest.mark.parametrize("host_profile", ["private", "provided"])
def test_environment_preserves_unconfirmed_cleanup_without_exposing_owned_handle(tmp_path, monkeypatch, capsys, close_failure, host_profile):
    from paper_factory.autonomous import quickjs_runner

    data, runtime = tmp_path / "data", tmp_path / "runtime"
    closed = []
    monkeypatch.setenv("PF_HOST_MODE", host_profile)

    class BlockedRunner:
        def __init__(self, runtime_root, *, supervisor_root, host_profile):
            assert runtime_root == runtime
            assert host_profile == os.environ["PF_HOST_MODE"]
            assert supervisor_root == data / "quickjs-supervisor"
            assert runtime not in supervisor_root.parents

        def status(self):
            return {"ready": False, "backend": "quickjs-wasm", "cleanup_confirmed": False,
                    "reason": "An existing owned worker has unconfirmed cleanup.",
                    "active_handle": {"pid": 17, "owner_nonce": "private-owned-identity"}}

        def close(self):
            assert closed == [True]
            closed.append("runner")
            if close_failure:
                raise ValueError("A diagnostic worker is still active")

    class Service:
        def __init__(self, home, *, runner, collector):
            assert home == data
            self.runner = runner

        def close(self):
            closed.append(True)

    monkeypatch.setattr(quickjs_runner, "QuickJSRunner", BlockedRunner)
    code = cloud.main(["--data", str(data), "--runtime-root", str(runtime), "environment"], service_factory=Service)
    result = json.loads(capsys.readouterr().out)
    assert closed == [True, "runner"]
    if close_failure:
        assert code == 1 and result["error"]["code"] == "CLEANUP_UNCONFIRMED"
    else:
        assert code == 0 and result["ready"] is False and result["cleanup_confirmed"] is False
        assert result["code"] == "CLEANUP_UNCONFIRMED"
        assert "Reconcile" in result["instructions"]
    assert "active_handle" not in result and "private-owned-identity" not in json.dumps(result)
    assert not runtime.exists()


@pytest.mark.parametrize("code,instruction", [
    ("SUPERVISOR_UNAVAILABLE", "Restore permitted access"),
    ("SUPERVISOR_BUSY", "Wait for the existing supervisor owner"),
    ("SUPERVISOR_STATE_INVALID", "Preserve and inspect the invalid supervisor journal"),
])
def test_environment_retains_supervisor_failure_with_only_safe_diagnostics(code, instruction):
    runtime = {"ready": False, "backend": "quickjs-wasm", "cleanup_confirmed": False,
               "code": code, "reason": "Supervisor preparation could not be verified.",
               "diagnostic": {"stage": "supervisor-prepare", "exception_type": "PermissionError",
                              "errno": 13, "winerror": 5, "path": "C:/private/account", "owner_nonce": "secret-owner"}}
    service = SimpleNamespace(runner=SimpleNamespace(status=lambda: runtime))
    result = cloud._dispatch(service, SimpleNamespace(command="environment"))
    assert result["ready"] is False and result["cleanup_confirmed"] is False
    assert result["code"] == code and instruction in result["instructions"]
    assert "Reconcile" not in result["instructions"]
    assert result["diagnostic"] == {"stage": "supervisor-prepare", "exception_type": "PermissionError", "errno": 13, "winerror": 5}
    assert "private/account" not in json.dumps(result) and "secret-owner" not in json.dumps(result)


@pytest.mark.parametrize("field,value", [
    ("stage", "/private/path"), ("stage", ["supervisor-prepare"]),
    ("exception_type", "PrivateClassWithSensitiveName"), ("exception_type", ["PermissionError"]),
    ("errno", True), ("errno", "13"), ("errno", -1), ("errno", 4096),
    ("winerror", False), ("winerror", -1), ("winerror", 65536),
])
def test_environment_omits_unknown_or_unbounded_supervisor_diagnostic_values(field, value):
    diagnostic = {"stage": "supervisor-prepare", "exception_type": "OSError", "errno": 5, "winerror": 5}
    diagnostic[field] = value
    runtime = {"ready": False, "backend": "quickjs-wasm", "cleanup_confirmed": False,
               "code": "SUPERVISOR_UNAVAILABLE", "diagnostic": diagnostic}
    result = cloud._dispatch(SimpleNamespace(runner=SimpleNamespace(status=lambda: runtime)), SimpleNamespace(command="environment"))
    assert field not in result["diagnostic"]
    assert result["code"] == "SUPERVISOR_UNAVAILABLE" and result["cleanup_confirmed"] is False


@pytest.mark.parametrize("backend,code,handle", [
    ("docker", "SUPERVISOR_UNAVAILABLE", {}),
    ("quickjs-wasm", "SUPERVISOR_BUSY", {"pid": 17, "owner_nonce": "private-owned-identity"}),
    ("quickjs-wasm", "CLEANUP_UNCONFIRMED", {}),
    ("quickjs-wasm", "UNKNOWN_PRIVATE_CODE", {}),
    ("quickjs-wasm", ["SUPERVISOR_UNAVAILABLE"], {}),
])
def test_environment_keeps_cleanup_priority_for_known_workers_and_unowned_codes(backend, code, handle):
    runtime = {"ready": False, "backend": backend, "cleanup_confirmed": False,
               "code": code, "active_handle": handle,
               "diagnostic": {"stage": "supervisor-prepare", "exception_type": "OSError", "errno": 5}}
    result = cloud._dispatch(SimpleNamespace(runner=SimpleNamespace(status=lambda: runtime)), SimpleNamespace(command="environment"))
    assert result["code"] == "CLEANUP_UNCONFIRMED" and "Reconcile" in result["instructions"]
    assert "diagnostic" not in result and "active_handle" not in result
    assert "private-owned-identity" not in json.dumps(result)


def test_actual_lease_io_error_reaches_environment_without_spawn_or_journal_write(tmp_path, monkeypatch, capsys):
    from paper_factory.autonomous.quickjs_runner import QuickJSRunner
    data, runtime = tmp_path / "data", tmp_path / "runtime"
    supervisor = data / "quickjs-supervisor"
    supervisor.mkdir(parents=True)
    journal = supervisor / "owned-workers.json"
    original = b'{"format":"paper-factory-quickjs-supervisor-v1","workers":[]}\n'
    journal.write_bytes(original)
    attempts, closed = [], []

    def failed_lock(*args):
        attempts.append(args)
        raise OSError(errno.EIO, "Sensitive native details", "C:/private/lease")

    if os.name == "nt":
        import msvcrt
        monkeypatch.setattr(msvcrt, "locking", failed_lock)
    else:
        import fcntl
        monkeypatch.setattr(fcntl, "flock", failed_lock)
    monkeypatch.setattr(QuickJSRunner, "_runtime", lambda *_a, **_k: pytest.fail("Lease failure must not probe Node"))
    monkeypatch.setattr(QuickJSRunner, "_execute", lambda *_a, **_k: pytest.fail("Lease failure must not spawn"))
    monkeypatch.setattr(QuickJSRunner, "_persist", lambda *_a, **_k: pytest.fail("Lease failure must not write journal"))

    class Service:
        def __init__(self, home, *, runner, collector):
            assert home == data
            self.runner = runner

        def close(self):
            closed.append(True)

    code = cloud.main(["--data", str(data), "--runtime-root", str(runtime), "environment"], service_factory=Service)
    result = json.loads(capsys.readouterr().out)
    assert code == 0 and result["ready"] is False and result["cleanup_confirmed"] is False
    assert result["code"] == "SUPERVISOR_UNAVAILABLE"
    assert result["diagnostic"] == {"stage": "supervisor-prepare", "exception_type": "OSError", "errno": errno.EIO}
    assert "Restore permitted access" in result["instructions"] and "Reconcile" not in result["instructions"]
    assert "private/lease" not in json.dumps(result) and "Sensitive" not in json.dumps(result)
    assert len(attempts) == 1 and closed == [True]
    assert journal.read_bytes() == original and not runtime.exists()

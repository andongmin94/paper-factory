"""Native runner contracts using a simulated restricted worker, never host code."""
import base64
import hashlib
import json
import os
from pathlib import Path

import pytest

from paper_factory.autonomous import windows_runtime
from paper_factory.autonomous.windows_runner import WindowsRunner, _read_bytes
from paper_factory.workspace import write_json


@pytest.fixture
def native_inputs(tmp_path):
    source, code, output = (tmp_path / name for name in ("source", "code", "output"))
    source.mkdir()
    code.mkdir()
    (source / "production.py").write_text("def transform(value):\n    return value\n", encoding="utf-8")
    (code / "experiment.py").write_text("# The mocked restricted worker never executes this code.\n", encoding="utf-8")
    return source, code, output


@pytest.fixture
def native_runner(monkeypatch):
    runner = WindowsRunner()
    monkeypatch.setattr(runner, "status", lambda: {"ready": True, "reason": None, "runtimes": ["python"]})
    monkeypatch.setattr(windows_runtime, "private_path", lambda path: None)
    monkeypatch.setattr(windows_runtime, "is_private_path", lambda path: True)
    def stage(root):
        executable = root / "python.exe"
        executable.write_bytes(b"simulated interpreter; not executed")
        return executable, None, {"sha256": "a" * 64, "files_sha256": {}, "versions": {"python": "3.12"}}
    monkeypatch.setattr(runner, "_stage_runtime", stage)
    return runner


@pytest.mark.parametrize("root_index", [0, 1], ids=["source", "bundle"])
def test_native_rejects_nested_output_without_mutating_inputs(native_inputs, monkeypatch, root_index):
    runner = WindowsRunner()
    monkeypatch.setattr(runner, "status", lambda: pytest.fail("must reject before checking the native runtime"))
    output = native_inputs[root_index] / "new-output"
    original = sorted(path.relative_to(native_inputs[root_index]) for path in native_inputs[root_index].rglob("*"))
    with pytest.raises(ValueError, match="separate"):
        runner.run(native_inputs[0], native_inputs[1], output, runtime="python", entrypoint="experiment.py")
    assert not output.exists()
    assert sorted(path.relative_to(native_inputs[root_index]) for path in native_inputs[root_index].rglob("*")) == original


def test_native_controller_uses_staged_paths_and_verified_trace(native_runner, native_inputs, monkeypatch):
    observed = []
    def launch(command, **kwargs):
        observed.append((command, kwargs))
        environment = kwargs["environment"]
        output = Path(environment["PF_OUTPUT_ROOT"])
        write_json(output / "observations.json", {"observations": [], "controls": []})
        write_json(output / ".paper-factory-python-calls.json", {
            "calls": [{"path": "production.py", "function": "transform", "calls": 3}], "truncated": False})
        return {"status": "succeeded", "exit_code": 0, "stdout": "", "stderr": "", "cleanup_confirmed": True}
    monkeypatch.setattr(windows_runtime, "launch", launch)
    result = native_runner.run(*native_inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "succeeded"
    assert result["production_calls"][0]["calls"] == 3
    assert result["runtime_digest"] == "a" * 64
    command, options = observed[0]
    assert "paper-factory-windows-" in command[0] and command[1] == "-I"
    assert len(options["read_only_paths"]) == 5 and len(options["writable_paths"]) == 3
    assert not any("TOKEN" in name or name.startswith("PF_AUTHOR_") for name in options["environment"])
    assert Path(result["output_path"]).is_file()
    assert not Path(options["environment"]["PF_SOURCE_ROOT"]).exists()


@pytest.mark.parametrize("content", [
    '{"measured": 7}'.encode("utf-16"),
    '{"measured": 7}'.encode("utf-32"),
    b'{"measured": NaN}',
], ids=["utf16", "utf32", "nonfinite"])
def test_native_export_rejects_non_utf8_or_nonfinite_observations(native_runner, native_inputs, monkeypatch, content):
    def launch(command, **kwargs):
        output = Path(kwargs["environment"]["PF_OUTPUT_ROOT"])
        (output / "observations.json").write_bytes(content)
        write_json(output / ".paper-factory-python-calls.json", {"calls": [], "truncated": False})
        return {"status": "succeeded", "exit_code": 0, "stdout": "", "stderr": "", "cleanup_confirmed": True}
    monkeypatch.setattr(windows_runtime, "launch", launch)
    result = native_runner.run(*native_inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "failed" and result["cleanup_confirmed"] is True
    assert result["output_path"] is None
    assert not (native_inputs[2] / "observations.json").exists()
    assert "Native sandbox execution rejected" in result["stderr"]


def test_native_failed_control_retains_exact_raw_observations_without_trace(native_runner, native_inputs, monkeypatch):
    fixture = b"input=1\nexpected=3\nactual=2\n"
    content = json.dumps({
        "observations": [{"unit_id": "fixture-1", "seed": 0, "condition": "production", "metric": "value", "value": 2}],
        "controls": [{"name": "positive control", "passed": False, "details": "Expected 3, observed 2"},
                     {"name": "negative control", "passed": True, "details": "Fault detected"}],
        "fixtures": [{"label": "raw input and result", "encoding": "base64",
                      "content": base64.b64encode(fixture).decode("ascii"), "sha256": hashlib.sha256(fixture).hexdigest()}],
    }, indent=2).encode("utf-8") + b"\n"
    def launch(command, **kwargs):
        output = Path(kwargs["environment"]["PF_OUTPUT_ROOT"])
        (output / "observations.json").write_bytes(content)
        return {"status": "failed", "exit_code": 1, "stdout": "positive control failed", "stderr": "",
                "cleanup_confirmed": True}
    monkeypatch.setattr(windows_runtime, "launch", launch)
    result = native_runner.run(*native_inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "failed" and result["exit_code"] == 1
    assert result["cleanup_confirmed"] is True
    assert result["stdout"] == "positive control failed"
    assert result["output_path"] is not None, result["stderr"]
    assert Path(result["output_path"]).read_bytes() == content
    assert result["artifacts"] == [{"path": "observations.json", "size": len(content),
                                    "sha256": hashlib.sha256(content).hexdigest()}]
    assert result["production_calls"] == []


@pytest.mark.parametrize("content", [
    b'{"controls":',
    '{"controls": []}'.encode("utf-16"),
    '{"controls": []}'.encode("utf-32"),
    b'{"observations": [{"value": NaN}]}',
    b'{"observations": [{"value": Infinity}]}',
    b'{"observations": [{"value": -Infinity}]}',
    b'{"observations": [{"value": 1e999}]}',
], ids=["malformed", "utf16", "utf32", "nan", "infinity", "negative-infinity", "overflow"])
def test_native_failed_exit_rejects_invalid_raw_observations(native_runner, native_inputs, monkeypatch, content):
    def launch(command, **kwargs):
        output = Path(kwargs["environment"]["PF_OUTPUT_ROOT"])
        (output / "observations.json").write_bytes(content)
        return {"status": "failed", "exit_code": 1, "stdout": "", "stderr": "",
                "cleanup_confirmed": True}
    monkeypatch.setattr(windows_runtime, "launch", launch)
    result = native_runner.run(*native_inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "failed" and result["exit_code"] == 1
    assert result["cleanup_confirmed"] is True
    assert result["output_path"] is None and result["artifacts"] == []
    assert not (native_inputs[2] / "observations.json").exists()


@pytest.mark.parametrize("status,exit_code", [("cancelled", 1), ("timeout", 1), ("failed", None)],
                         ids=["cancelled", "timeout", "resource-limit"])
def test_native_interrupted_execution_discards_even_valid_raw_observations(native_runner, native_inputs, monkeypatch, status, exit_code):
    def launch(command, **kwargs):
        output = Path(kwargs["environment"]["PF_OUTPUT_ROOT"])
        write_json(output / "observations.json", {"controls": [{"name": "positive control", "passed": False}]})
        write_json(output / ".paper-factory-python-calls.json", {"calls": [], "truncated": False})
        return {"status": status, "exit_code": exit_code, "stdout": "",
                "stderr": "Windows experiment exceeded its log limit" if status == "failed" else "",
                "cleanup_confirmed": True}
    monkeypatch.setattr(windows_runtime, "launch", launch)
    result = native_runner.run(*native_inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == status and result["cleanup_confirmed"] is True
    assert result["output_path"] is None and result["artifacts"] == []
    assert not (native_inputs[2] / "observations.json").exists()


def test_native_cleanup_failure_preserves_staging_and_handle(native_runner, native_inputs, monkeypatch):
    handle = {"kind": "windows-experiment", "pid": 42, "start_ticks": 1,
              "job_name": "Local\\paper-factory-research-" + "b" * 32}
    monkeypatch.setattr(windows_runtime, "launch", lambda *_args, **kwargs: {
        "status": "failed", "exit_code": None, "stdout": "", "stderr": "",
        "cleanup_confirmed": False, "handle": handle})
    result = native_runner.run(*native_inputs, runtime="python", entrypoint="experiment.py")
    retained = result["active_handle"]
    assert result["status"] == "blocked" and result["code"] == "CLEANUP_UNCONFIRMED"
    assert retained["pid"] == 42 and Path(retained["staging_root"]).is_dir()
    monkeypatch.setattr(windows_runtime, "stop", lambda saved: saved["pid"] == 42)
    monkeypatch.setattr(windows_runtime, "is_private_path", lambda path: True)
    assert native_runner.stop(retained)
    assert not Path(retained["staging_root"]).exists()


def test_staging_cleanup_retries_transient_windows_locks_and_rechecks_path(monkeypatch):
    import tempfile
    from paper_factory.autonomous import windows_runner
    staging = Path(tempfile.mkdtemp(prefix=windows_runner._STAGING_PREFIX))
    (staging / "locked.dll").write_bytes(b"Dummy DLL fixture")
    remove = windows_runner.shutil.rmtree
    checked = windows_runner._checked_staging
    attempts, checks = [], []
    def delayed_delete(path, **kwargs):
        attempts.append(path)
        if len(attempts) < 3:
            error = PermissionError("Simulated transient DLL sharing violation")
            error.winerror = 32
            raise error
        remove(path, **kwargs)
    def checked_each_time(path):
        checks.append(path)
        checked(path)
    monkeypatch.setattr(windows_runner.shutil, "rmtree", delayed_delete)
    monkeypatch.setattr(windows_runner, "_checked_staging", checked_each_time)
    monkeypatch.setattr(windows_runner.time, "sleep", lambda delay: None)
    windows_runner._remove_staging(staging)
    assert len(attempts) == len(checks) == 3 and not staging.exists()


def test_staging_cleanup_deadline_returns_receipt_and_preserves_recoverable_handle(native_runner, native_inputs, monkeypatch):
    from paper_factory.autonomous import windows_runner
    handle = {"kind": "windows-experiment", "pid": 42, "start_ticks": 1,
              "job_name": "Local\\paper-factory-research-" + "b" * 32}
    def launch(command, **kwargs):
        output = Path(kwargs["environment"]["PF_OUTPUT_ROOT"])
        write_json(output / "observations.json", {"measured": 7})
        write_json(output / ".paper-factory-python-calls.json", {"calls": [], "truncated": False})
        return {"status": "succeeded", "exit_code": 0, "stdout": "measured", "stderr": "",
                "cleanup_confirmed": True, "handle": handle}
    remove = windows_runner.shutil.rmtree
    def locked_delete(path, **kwargs):
        error = PermissionError("Simulated persistent DLL sharing violation")
        error.winerror = 32
        raise error
    monkeypatch.setattr(windows_runtime, "launch", launch)
    monkeypatch.setattr(windows_runner.shutil, "rmtree", locked_delete)
    monkeypatch.setattr(windows_runner, "_STAGING_CLEANUP_SECONDS", 0)
    result = native_runner.run(*native_inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "blocked" and result["code"] == "CLEANUP_UNCONFIRMED"
    assert result["cleanup_confirmed"] is False and result["process_cleanup_confirmed"] is True
    assert result["stdout"] == "measured" and json.loads(Path(result["output_path"]).read_text()) == {"measured": 7}
    retained = result["active_handle"]
    assert retained["pid"] == 42 and Path(retained["staging_root"]).is_dir()
    monkeypatch.setattr(windows_runtime, "stop", lambda saved: False)
    assert native_runner.stop(retained) is False
    monkeypatch.setattr(windows_runtime, "stop", lambda saved: saved["pid"] == 42)
    assert native_runner.stop(retained) is False
    monkeypatch.setattr(windows_runner.shutil, "rmtree", remove)
    assert native_runner.stop(retained) is True and not Path(retained["staging_root"]).exists()


def test_launch_exception_never_restores_acl_or_deletes_an_unconfirmed_worker_tree(native_runner, native_inputs, monkeypatch):
    handle = {"kind": "windows-experiment", "pid": 42, "start_ticks": 1,
              "job_name": "Local\\paper-factory-research-" + "b" * 32}
    secured = []
    monkeypatch.setattr(windows_runtime, "private_path", secured.append)
    def launch(command, **kwargs):
        kwargs["on_handle"](handle)
        raise RuntimeError("Simulated controller failure before its cleanup receipt")
    monkeypatch.setattr(windows_runtime, "launch", launch)
    result = native_runner.run(*native_inputs, runtime="python", entrypoint="experiment.py")
    retained = result["active_handle"]
    assert result["status"] == "blocked" and result["cleanup_confirmed"] is False
    assert retained["pid"] == 42 and Path(retained["staging_root"]).is_dir()
    assert secured == [Path(retained["staging_root"])]
    monkeypatch.setattr(windows_runtime, "stop", lambda saved: True)
    assert native_runner.stop(retained) is True
    assert len(secured) == 2 and not Path(retained["staging_root"]).exists()


def test_unavailable_native_isolation_never_executes(native_inputs, monkeypatch):
    runner = WindowsRunner()
    monkeypatch.setattr(runner, "status", lambda: {"ready": False, "reason": "Isolation unavailable", "runtimes": []})
    monkeypatch.setattr(windows_runtime, "launch", lambda *_args, **_kwargs: pytest.fail("must not launch"))
    result = runner.run(*native_inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "failed" and result["stderr"] == "Isolation unavailable"


def test_native_artifact_reader_rejects_hardlinks_and_oversize(tmp_path):
    import os
    path = tmp_path / "observations.json"
    path.write_text(json.dumps({"value": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="bounded"):
        _read_bytes(path, 1)
    os.link(path, tmp_path / "second-link.json")
    with pytest.raises(ValueError, match="one link"):
        _read_bytes(path, 100)


def _real_native_worker():
    if os.name != "nt":
        pytest.skip("Native AppContainer integration requires Windows")
    runner = WindowsRunner()
    status = runner.status()
    if not status["ready"]:
        pytest.skip(status["reason"])
    return runner, status


def test_actual_native_python_denies_private_reads_writes_network_and_host_environment(tmp_path):
    import socket
    runner, _ = _real_native_worker()
    source, code, output = (tmp_path / name for name in ("source", "code", "output"))
    source.mkdir()
    code.mkdir()
    original = "def transform(value):\n    return value + 1\n"
    (source / "production.py").write_text(original, encoding="utf-8")
    private = tmp_path / "private-dummy.txt"
    private.write_text("Dummy fixture, never an actual credential", encoding="utf-8")
    windows_runtime.private_path(private)
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    code_text = '''import os, sys, pathlib, json, socket
sys.path.insert(0, os.environ['PF_SOURCE_ROOT'])
from production import transform
result = {'value': transform(1)}
try:
    pathlib.Path(PRIVATE_DUMMY).read_bytes()
    result['private_read_denied'] = False
except PermissionError:
    result['private_read_denied'] = True
try:
    with pathlib.Path(os.environ['PF_SOURCE_ROOT'], 'production.py').open('a') as stream:
        stream.write('# disallowed mutation')
    result['source_write_denied'] = False
except PermissionError:
    result['source_write_denied'] = True
try:
    connection = socket.create_connection(('127.0.0.1', LOCAL_PORT), timeout=2)
    connection.close()
    result['network_blocked'] = False
except OSError:
    result['network_blocked'] = True
result['host_environment_excluded'] = 'PF_TEST_SECRET' not in os.environ
pathlib.Path(os.environ['PF_OUTPUT_ROOT'], 'observations.json').write_text(json.dumps(result), encoding='utf-8')
'''.replace("PRIVATE_DUMMY", repr(str(private))).replace("LOCAL_PORT", str(server.getsockname()[1]))
    (code / "experiment.py").write_text(code_text, encoding="utf-8")
    previous = os.environ.get("PF_TEST_SECRET")
    os.environ["PF_TEST_SECRET"] = "Dummy test environment value"
    try:
        result = runner.run(source, code, output, runtime="python", entrypoint="experiment.py", timeout_seconds=20)
    finally:
        server.close()
        if previous is None:
            os.environ.pop("PF_TEST_SECRET", None)
        else:
            os.environ["PF_TEST_SECRET"] = previous
    assert result["status"] == "succeeded", result["stderr"]
    assert result["cleanup_confirmed"] is True
    assert json.loads(Path(result["output_path"]).read_text(encoding="utf-8")) == {
        "value": 2, "private_read_denied": True, "source_write_denied": True,
        "network_blocked": True, "host_environment_excluded": True}
    assert result["production_calls"] == [{"path": "production.py", "function": "transform", "calls": 1}]
    assert (source / "production.py").read_text(encoding="utf-8") == original


def test_actual_native_failed_positive_control_retains_raw_observations_and_production_trace(tmp_path):
    runner, _ = _real_native_worker()
    source, code, output = (tmp_path / name for name in ("source", "code", "output"))
    source.mkdir()
    code.mkdir()
    original = b"def transform(value):\n    return value + 1\n"
    (source / "production.py").write_bytes(original)
    (code / "experiment.py").write_text('''import base64, hashlib, json, os, pathlib, sys
sys.path.insert(0, os.environ['PF_SOURCE_ROOT'])
from production import transform
actual = transform(1)
fixture = f'input=1\\nexpected=3\\nactual={actual}\\n'.encode('utf-8')
observations = {
    'observations': [{'unit_id': 'fixture-1', 'seed': 0, 'condition': 'production', 'metric': 'value', 'value': actual}],
    'controls': [{'name': 'positive control', 'passed': actual == 3, 'details': f'Expected 3, observed {actual}'},
                 {'name': 'negative control', 'passed': actual != -1, 'details': 'Intentional wrong result detected'}],
    'fixtures': [{'label': 'raw input and result', 'encoding': 'base64',
                  'content': base64.b64encode(fixture).decode('ascii'), 'sha256': hashlib.sha256(fixture).hexdigest()}],
}
content = json.dumps(observations, indent=2).encode('utf-8') + b'\\n'
pathlib.Path(os.environ['PF_OUTPUT_ROOT'], 'observations.json').write_bytes(content)
sys.exit(1)
''', encoding="utf-8")
    fixture = b"input=1\nexpected=3\nactual=2\n"
    expected = json.dumps({
        "observations": [{"unit_id": "fixture-1", "seed": 0, "condition": "production", "metric": "value", "value": 2}],
        "controls": [{"name": "positive control", "passed": False, "details": "Expected 3, observed 2"},
                     {"name": "negative control", "passed": True, "details": "Intentional wrong result detected"}],
        "fixtures": [{"label": "raw input and result", "encoding": "base64",
                      "content": base64.b64encode(fixture).decode("ascii"), "sha256": hashlib.sha256(fixture).hexdigest()}],
    }, indent=2).encode("utf-8") + b"\n"
    result = runner.run(source, code, output, runtime="python", entrypoint="experiment.py", timeout_seconds=20,
                        production_entrypoint="production.py:transform")
    assert result["status"] == "failed" and result["exit_code"] == 1, result["stderr"]
    assert result["cleanup_confirmed"] is True
    assert result["output_path"] is not None, result["stderr"]
    exported = Path(result["output_path"]).read_bytes()
    assert exported == expected
    assert result["artifacts"] == [{"path": "observations.json", "size": len(expected),
                                    "sha256": hashlib.sha256(expected).hexdigest()}]
    raw = json.loads(exported)
    assert raw["controls"][0]["passed"] is False
    assert base64.b64decode(raw["fixtures"][0]["content"]) == fixture
    assert raw["fixtures"][0]["sha256"] == hashlib.sha256(fixture).hexdigest()
    assert result["production_calls"] == [{"path": "production.py", "function": "transform", "calls": 1}]
    assert (source / "production.py").read_bytes() == original


def test_actual_native_node_records_production_calls(tmp_path):
    runner, status = _real_native_worker()
    if "node" not in status["runtimes"]:
        pytest.skip("Native Node runtime is unavailable")
    source, code, output = (tmp_path / name for name in ("source", "code", "output"))
    source.mkdir()
    code.mkdir()
    (source / "production.js").write_text("exports.transform = function transform(value) { return value + 1; };", encoding="utf-8")
    (code / "experiment.js").write_text(
        "const fs = require('fs'); const path = require('path'); "
        "const { transform } = require(path.join(process.env.PF_SOURCE_ROOT, 'production.js')); "
        "fs.writeFileSync(path.join(process.env.PF_OUTPUT_ROOT, 'observations.json'), JSON.stringify({value: transform(2)}));",
        encoding="utf-8")
    result = runner.run(source, code, output, runtime="node", entrypoint="experiment.js", timeout_seconds=20)
    assert result["status"] == "succeeded", result["stderr"]
    assert result["cleanup_confirmed"] is True
    assert json.loads(Path(result["output_path"]).read_text(encoding="utf-8")) == {"value": 3}
    assert result["production_calls"] == [{"path": "production.js", "function": "transform", "calls": 1}]


def test_actual_native_cancellation_terminates_descendant(tmp_path):
    runner, _ = _real_native_worker()
    source, code, output = (tmp_path / name for name in ("source", "code", "output"))
    source.mkdir()
    code.mkdir()
    (source / "production.py").write_text("def transform(value):\n    return value\n", encoding="utf-8")
    (code / "experiment.py").write_text(
        "import os, pathlib, json, subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(120)'])\n"
        "pathlib.Path(os.environ['PF_OUTPUT_ROOT'], 'child.json').write_text(json.dumps({'pid': child.pid}), encoding='utf-8')\n"
        "while True: time.sleep(0.1)\n", encoding="utf-8")
    retained = []
    child_pid = []
    def cancel():
        if not retained:
            return False
        child = Path(retained[0]["staging_root"], "output", "child.json")
        if not child.is_file():
            return False
        try:
            pid = json.loads(child.read_text(encoding="utf-8"))["pid"]
        except (OSError, ValueError):
            return False
        child_pid.append(pid)
        return True
    result = runner.run(source, code, output, runtime="python", entrypoint="experiment.py", timeout_seconds=20,
                        cancel=cancel, on_handle=retained.append)
    assert result["status"] == "cancelled" and result["cleanup_confirmed"] is True
    assert child_pid and windows_runtime.process_ticks(child_pid[0]) is None
    assert not Path(retained[0]["staging_root"]).exists()


def test_actual_native_recovery_restores_private_staging_acl(tmp_path, monkeypatch):
    runner, _ = _real_native_worker()
    source, code, output = (tmp_path / name for name in ("source", "code", "output"))
    source.mkdir()
    code.mkdir()
    (source / "production.py").write_text("def transform(value):\n    return value\n", encoding="utf-8")
    (code / "experiment.py").write_text(
        "import os, pathlib\n"
        "pathlib.Path(os.environ['PF_OUTPUT_ROOT'], 'observations.json').write_text('{}', encoding='utf-8')\n",
        encoding="utf-8")
    launch = windows_runtime.launch
    def unconfirmed(*args, **kwargs):
        receipt = launch(*args, **kwargs)
        assert receipt["cleanup_confirmed"] is True
        return {**receipt, "cleanup_confirmed": False}
    monkeypatch.setattr(windows_runtime, "launch", unconfirmed)
    result = runner.run(source, code, output, runtime="python", entrypoint="experiment.py", timeout_seconds=20)
    assert result["status"] == "blocked" and result["code"] == "CLEANUP_UNCONFIRMED"
    retained = result["active_handle"]
    staging = Path(retained["staging_root"])
    assert staging.exists() and not windows_runtime.is_private_path(staging)
    assert runner.stop(retained)
    assert not staging.exists()

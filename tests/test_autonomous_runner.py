from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
import subprocess

import pytest

from paper_factory.autonomous import runner as module
from paper_factory.autonomous.runner import DockerRunner, IMAGE_LABEL, MAX_ARTIFACT_BYTES


IMAGE = "sha256:" + "a" * 64
CONTAINER = "b" * 64


def image_details(**overrides):
    config = {"User": "65532:65532", "Entrypoint": None, "Labels": {
        IMAGE_LABEL: "1", "org.paper-factory.research-runtimes": "python,node",
        "org.paper-factory.research-dependencies": "mido,packaging",
    }}
    config.update(overrides)
    return {"Id": IMAGE, "Config": config}


def response(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


@pytest.fixture
def inputs(tmp_path):
    source, bundle, output = (tmp_path / name for name in ("source", "bundle", "output"))
    source.mkdir(mode=0o700)
    bundle.mkdir(mode=0o700)
    (source / "witness.txt").write_text("frozen", encoding="utf-8")
    (bundle / "experiment.py").write_text("# generated program", encoding="utf-8")
    (bundle / "experiment.js").write_text("// generated program", encoding="utf-8")
    return source, bundle, output


class FakeProcess:
    def __init__(self, data: bytes, *, alive=False):
        self.stdout, self.stderr = io.BytesIO(data), io.BytesIO()
        self.returncode = None if alive else 0

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = self.returncode if self.returncode is not None else -9
        return self.returncode

    def kill(self):
        self.returncode = -9


def envelope(data=b'{"rows":[{"value":1}]}', **updates):
    value = {"protocol": module.PROTOCOL, "exit_code": 0, "stdout": "measured\n", "stderr": "",
             "observation_b64": base64.b64encode(data).decode(), "error": None, "timed_out": False}
    value.update(updates)
    return json.dumps(value).encode()


@pytest.fixture
def fake_runner(monkeypatch):
    runner = DockerRunner(IMAGE)
    calls = []
    monkeypatch.setattr(module.shutil, "which", lambda _: "/usr/bin/docker")
    process = FakeProcess(envelope())
    def control(args, **kwargs):
        calls.append(args)
        if args[0] == "info":
            return response('["name=seccomp,profile=builtin"]')
        if args[:2] == ["image", "inspect"]:
            return response(json.dumps(image_details()))
        if args[0] == "create":
            return response(CONTAINER)
        if args[0] == "kill":
            process.kill()
        return response()
    monkeypatch.setattr(runner, "_control", control)
    def popen(args, **kwargs):
        calls.append(args)
        return process
    monkeypatch.setattr(module.subprocess, "Popen", popen)
    return runner, calls, process


@pytest.mark.parametrize("image", ["", "python:3.12", "paper-factory:latest", "sha256:abc", "../unsafe"])
def test_requires_immutable_image_without_invoking_docker(monkeypatch, image):
    monkeypatch.setattr(module.shutil, "which", lambda _: "/usr/bin/docker")
    runner = DockerRunner(image)
    monkeypatch.setattr(runner, "_control", lambda *_a, **_k: pytest.fail("must not call Docker"))
    assert not runner.status()["ready"]


def test_missing_docker_fails_closed(monkeypatch, inputs):
    monkeypatch.setattr(module.shutil, "which", lambda _: None)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_k: pytest.fail("must not execute"))
    result = DockerRunner(IMAGE).run(*inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "failed"
    assert "cannot run on the host" in result["stderr"]
    assert result["artifacts"] == []


@pytest.mark.parametrize("config", [
    {"User": "root"}, {"Entrypoint": ["/bin/sh"]}, {"Labels": {}}, {"Labels": None},
    {"Volumes": {"/unbounded": {}}},
    {"Healthcheck": {"Test": ["CMD", "background-program"]}},
])
def test_rejects_unapproved_image(monkeypatch, config):
    monkeypatch.setattr(module.shutil, "which", lambda _: "/usr/bin/docker")
    runner = DockerRunner(IMAGE)
    monkeypatch.setattr(runner, "_control", lambda args, **kw: response(
        '["name=seccomp,profile=builtin"]' if args[0] == "info" else json.dumps(image_details(**config))))
    assert not runner.status()["ready"]


def test_rejects_daemon_without_seccomp(monkeypatch):
    monkeypatch.setattr(module.shutil, "which", lambda _: "/usr/bin/docker")
    runner = DockerRunner(IMAGE)
    monkeypatch.setattr(runner, "_control", lambda *_a, **_k: response('["name=cgroupns"]'))
    assert "seccomp" in runner.status()["reason"]


def test_exports_only_declared_artifact_with_hardened_options(fake_runner, inputs):
    runner, calls, _ = fake_runner
    original_mode = inputs[0].stat().st_mode
    handles = []
    result = runner.run(*inputs, runtime="python", entrypoint="experiment.py", on_handle=handles.append)
    assert result["status"] == "succeeded"
    assert json.loads(Path(result["output_path"]).read_text()) == {"rows": [{"value": 1}]}
    assert result["artifacts"][0]["path"] == "observations.json"
    assert (inputs[0] / "witness.txt").read_text() == "frozen"
    assert inputs[0].stat().st_mode == original_mode
    create = next(call for call in calls if call[0] == "create")
    assert create[create.index("--network") + 1] == "none"
    assert create[create.index("--user") + 1] == "65532:65532"
    for required in ["--read-only", "ALL", "no-new-privileges:true", "512m", "128", "private"]:
        assert required in create
    mounts = [create[index + 1] for index, item in enumerate(create) if item == "--mount"]
    assert len(mounts) == 2 and all("readonly" in mount for mount in mounts)
    assert all("paper-factory-sandbox-" in mount for mount in mounts)
    assert not any("docker.sock" in mount or ".env" in mount for mount in mounts)
    environment = [create[index + 1] for index, item in enumerate(create) if item == "--env"]
    assert set(environment) == {
        "HOME=/work", "PYTHONDONTWRITEBYTECODE=1", "PYTHONNOUSERSITE=1", "PATH=/usr/local/bin:/usr/bin:/bin",
    }
    assert not any(option in create for option in {"--env-file", "-e", "-v", "--volume", "--volumes-from"})
    assert handles[0]["container_id"] == CONTAINER
    assert handles[0]["kind"] == "container"
    assert calls[-1][:2] == ["rm", "--force"]
    assert all(call[0] in {"info", "image", "create", "docker", "rm"} for call in calls)


@pytest.mark.parametrize("entrypoint,runtime", [
    ("../experiment.py", "python"), ("/experiment.py", "python"),
    ("experiment.py", "node"), ("experiment.sh", "bash"),
    ("missing.py", "python"), ("experiment\\.py", "python"),
])
def test_rejects_unsafe_entrypoint(inputs, entrypoint, runtime):
    with pytest.raises(ValueError):
        DockerRunner(IMAGE).run(*inputs, runtime=runtime, entrypoint=entrypoint)


def test_rejects_source_symlink_before_docker(monkeypatch, inputs):
    try:
        (inputs[0] / "link").symlink_to("witness.txt")
    except OSError as error:
        if os.name != "nt" or error.winerror != 1314:
            raise
        target = inputs[0].parent / "outside-directory"
        target.mkdir()
        linked = subprocess.run(["cmd", "/c", "mklink", "/J", str(inputs[0] / "link"), str(target)], capture_output=True)
        if linked.returncode:
            pytest.skip("This Windows account cannot create a symlink or junction")
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_k: pytest.fail("must not execute"))
    with pytest.raises(ValueError, match="links"):
        DockerRunner(IMAGE).run(*inputs, runtime="python", entrypoint="experiment.py")


@pytest.mark.parametrize("timeout", [0, -1, 3601, True, 1.5])
def test_rejects_unbounded_deadline(inputs, timeout):
    with pytest.raises(ValueError, match="timeout"):
        DockerRunner(IMAGE).run(*inputs, runtime="python", entrypoint="experiment.py", timeout_seconds=timeout)


@pytest.mark.parametrize("timeout", [1801, 3600])
def test_accepts_full_pipeline_timeout_budget(fake_runner, inputs, timeout):
    runner, _, _ = fake_runner
    result = runner.run(*inputs, runtime="python", entrypoint="experiment.py", timeout_seconds=timeout)
    assert result["status"] == "succeeded"
    assert result["limits"]["timeout_seconds"] == timeout


@pytest.mark.parametrize("failure", ["returncode", "timeout"])
def test_container_cleanup_failure_retains_owned_handle(fake_runner, inputs, monkeypatch, failure):
    runner, _, _ = fake_runner
    original = runner._control
    def control(args, **kwargs):
        if args[0] == "rm":
            if failure == "timeout":
                raise subprocess.TimeoutExpired("docker rm", 5)
            return response(stderr="Docker daemon unavailable", returncode=1)
        return original(args, **kwargs)
    monkeypatch.setattr(runner, "_control", control)
    result = runner.run(*inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "blocked" and result["code"] == "CLEANUP_UNCONFIRMED"
    assert result["cleanup_confirmed"] is False
    assert result["active_handle"]["container_id"] == CONTAINER
    assert result["active_handle"]["container_name"].startswith(module.CONTAINER_PREFIX)
    assert Path(result["output_path"]).is_file()


def test_staging_does_not_require_posix_nofollow(fake_runner, inputs, monkeypatch):
    monkeypatch.delattr(module.os, "O_NOFOLLOW", raising=False)
    runner, _, _ = fake_runner
    result = runner.run(*inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "succeeded"


def test_rejects_existing_output(inputs):
    inputs[2].mkdir()
    (inputs[2] / "old.json").write_text("{}")
    with pytest.raises(ValueError, match="empty"):
        DockerRunner(IMAGE).run(*inputs, runtime="python", entrypoint="experiment.py")


@pytest.mark.parametrize("root_index", [0, 1], ids=["source", "bundle"])
def test_rejects_nested_output_without_mutating_inputs(inputs, monkeypatch, root_index):
    runner = DockerRunner(IMAGE)
    monkeypatch.setattr(runner, "status", lambda: pytest.fail("must reject before checking Docker"))
    output = inputs[root_index] / "new-output"
    original = sorted(path.relative_to(inputs[root_index]) for path in inputs[root_index].rglob("*"))
    with pytest.raises(ValueError, match="separate"):
        runner.run(inputs[0], inputs[1], output, runtime="python", entrypoint="experiment.py")
    assert not output.exists()
    assert sorted(path.relative_to(inputs[root_index]) for path in inputs[root_index].rglob("*")) == original


@pytest.mark.parametrize("payload", [
    b"garbage", envelope(protocol="forged"), envelope(observation_b64="not-base64"),
    envelope(b"not json"), envelope(b'{"value": NaN}'), envelope(error="artifact was a link"),
    envelope(observation_b64="a" * (((MAX_ARTIFACT_BYTES + 2) // 3 * 4) + 1)),
], ids=["garbage", "protocol", "base64", "json", "nonfinite", "artifact-error", "oversized"])
def test_rejects_invalid_transport_without_import(fake_runner, inputs, payload):
    runner, _, process = fake_runner
    process.stdout = io.BytesIO(payload)
    result = runner.run(*inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "failed"
    assert not list(inputs[2].iterdir())


def test_records_wrapper_timeout(fake_runner, inputs):
    runner, _, process = fake_runner
    process.stdout = io.BytesIO(envelope(timed_out=True, exit_code=-9))
    result = runner.run(*inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "timeout"
    assert result["artifacts"] == []


def test_cancel_kills_container_and_exports_nothing(fake_runner, inputs):
    runner, calls, process = fake_runner
    process.returncode = None
    checks = iter([False, True])
    result = runner.run(*inputs, runtime="python", entrypoint="experiment.py", cancel=lambda: next(checks))
    assert result["status"] == "cancelled"
    assert any(call[0] == "kill" for call in calls)
    assert calls[-1][:2] == ["rm", "--force"]
    assert not list(inputs[2].iterdir())


def test_deadline_kills_container(fake_runner, inputs, monkeypatch):
    runner, calls, process = fake_runner
    process.returncode = None
    moments = iter([0.0, 5.0, 5.0])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(moments))
    result = runner.run(*inputs, runtime="python", entrypoint="experiment.py", timeout_seconds=1)
    assert result["status"] == "timeout"
    assert any(call[0] == "kill" for call in calls)


def test_handles_docker_create_failure_without_host_execution(fake_runner, inputs, monkeypatch):
    runner, _, _ = fake_runner
    original = runner._control
    monkeypatch.setattr(runner, "_control", lambda args, **kw: response(stderr="daemon refused", returncode=1)
                        if args[0] == "create" else original(args, **kw))
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_k: pytest.fail("must not execute"))
    result = runner.run(*inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "failed" and result["stderr"] == "daemon refused"


@pytest.mark.parametrize("handle", [
    {}, {"kind": "process", "pid": 1},
    {"kind": "container", "container_id": CONTAINER, "container_name": "other-service"},
    {"kind": "container", "container_id": "unsafe", "container_name": module.CONTAINER_PREFIX + "c" * 32},
])
def test_stop_refuses_unowned_handles(monkeypatch, handle):
    runner = DockerRunner(IMAGE)
    monkeypatch.setattr(runner, "_control", lambda *_a, **_k: pytest.fail("must not call Docker"))
    assert runner.stop(handle) is False


def test_stop_verifies_container_identity_before_removal(monkeypatch):
    runner = DockerRunner(IMAGE)
    name = module.CONTAINER_PREFIX + "c" * 32
    calls = []
    def control(args, **kwargs):
        calls.append(args)
        return response(json.dumps("/" + name)) if args[0] == "inspect" else response()
    monkeypatch.setattr(runner, "_control", control)
    assert runner.stop({"kind": "container", "container_id": CONTAINER, "container_name": name})
    assert calls[-1] == ["rm", "--force", CONTAINER]


def test_stop_does_not_remove_replaced_container(monkeypatch):
    runner = DockerRunner(IMAGE)
    calls = []
    def control(args, **kwargs):
        calls.append(args)
        return response(json.dumps("/unrelated-service"))
    monkeypatch.setattr(runner, "_control", control)
    assert not runner.stop({"kind": "container", "container_id": CONTAINER,
                            "container_name": module.CONTAINER_PREFIX + "c" * 32})
    assert len(calls) == 1


def test_transport_overflow_is_rejected_without_import(fake_runner, inputs):
    runner, _, process = fake_runner
    process.stdout = io.BytesIO(b"x" * (module.MAX_TRANSPORT_BYTES + 1))
    result = runner.run(*inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "failed" and result["artifacts"] == []


def test_multibyte_logs_are_capped_and_marked(fake_runner, inputs):
    runner, _, process = fake_runner
    process.stdout = io.BytesIO(envelope(stdout="한" * module.MAX_LOG_BYTES))
    result = runner.run(*inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "succeeded"
    assert len(result["stdout"].encode()) <= module.MAX_LOG_BYTES
    assert result["stdout"].endswith("[log truncated]")


def test_execution_receipt_is_separate_from_observations(fake_runner, inputs):
    runner, _, process = fake_runner
    (inputs[0] / "production.py").write_text("def actual(): return 1\n")
    calls = [{"path": "production.py", "function": "actual", "calls": 3}]
    process.stdout = io.BytesIO(envelope(production_calls=calls, coverage_truncated=False))
    result = runner.run(*inputs, runtime="python", entrypoint="experiment.py",
                        production_entrypoint="production.py:actual")
    assert result["status"] == "succeeded"
    assert result["production_calls"] == calls
    assert result["coverage_mechanism"] == "python-profile"
    assert "production_calls" not in json.loads(Path(result["output_path"]).read_text())


@pytest.mark.parametrize("record", [
    {"path": "../outside.py", "function": "fake", "calls": 1},
    {"path": "missing.py", "function": "fake", "calls": 1},
    {"path": "witness.txt", "function": "fake", "calls": True},
    {"path": "witness.txt", "function": "fake", "calls": 0},
    {"path": "witness.txt", "function": "", "calls": 1},
])
def test_rejects_invalid_execution_receipt(fake_runner, inputs, record):
    runner, _, process = fake_runner
    process.stdout = io.BytesIO(envelope(production_calls=[record]))
    result = runner.run(*inputs, runtime="python", entrypoint="experiment.py")
    assert result["status"] == "failed" and not list(inputs[2].iterdir())


@pytest.mark.parametrize("extension", ["cjs", "mjs"])
def test_accepts_node_entrypoint_extensions(fake_runner, inputs, extension):
    runner, _, _ = fake_runner
    (inputs[1] / ("experiment." + extension)).write_text("// code")
    result = runner.run(*inputs, runtime="node", entrypoint="experiment." + extension)
    assert result["status"] == "succeeded"
    assert result["coverage_mechanism"] == "node-v8-coverage"


@pytest.mark.parametrize("selected", ["missing.py:call", "../escape.py:call", "witness.txt:bad name", "witness.txt"])
def test_rejects_invalid_selected_production_entrypoint(inputs, selected):
    with pytest.raises(ValueError, match="production entrypoint"):
        DockerRunner(IMAGE).run(*inputs, runtime="python", entrypoint="experiment.py", production_entrypoint=selected)

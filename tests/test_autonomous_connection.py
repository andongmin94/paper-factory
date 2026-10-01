"""Device flow boundaries exercised with a fake CLI; no real authentication."""
import json
import io
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from paper_factory.autonomous.connection import ConnectionManager, DEVICE_URL, _challenge, _now
from paper_factory.autonomous import connection
from paper_factory.autonomous import windows_runtime
from paper_factory.autonomous.provider import CodexProvider, ProviderBlocked, _process_options, _start_ticks, _track_process, _worker_handle
from paper_factory.autonomous.windows_runtime import is_private_path, private_path
from paper_factory.workspace import write_json


class FakeProvider:
    def __init__(self, home, settings):
        self.home, self.settings = home, settings

    def status(self):
        self.settings["status_calls"] += 1
        return {"ready": True, "authentication": self.settings.get("authentication", "chatgpt")}

    def cleanup_handle(self, handle):
        if self.settings.get("cleanup") is False:
            return False
        return CodexProvider(auth_home=self.home).cleanup_handle(handle)

    def generate(self, prompt, schema, call_dir, **kwargs):
        self.settings["generate_calls"] += 1
        assert schema["additionalProperties"] is False
        assert "Without using tools" in prompt
        assert kwargs["timeout_seconds"] <= 1800
        if self.settings.get("probe_wait"):
            while not kwargs["cancel"]():
                time.sleep(0.01)
            raise ProviderBlocked("CANCELLED", "raw-private-probe-diagnostic")
        if self.settings.get("error"):
            raise ProviderBlocked(self.settings["error"], "raw-private-probe-diagnostic bearer secret")
        return self.settings.get("response", {"ready": True})


def make_manager(tmp_path, monkeypatch, *, delay=0, diagnostic="", code=0, timeout=900, descendant=False, root=None, challenge=True):
    executable = tmp_path / ("fake-codex-" + str(time.monotonic_ns()) + ".py")
    observed = tmp_path / "observed.json"
    settings = {"delay": delay, "diagnostic": diagnostic, "code": code, "observed": str(observed), "descendant": descendant, "challenge": challenge}
    executable.write_text(
        f"#!{sys.executable}\nimport os,sys,json,time,subprocess\nfrom pathlib import Path\n"
        f"s=json.loads({json.dumps(json.dumps(settings))})\n"
        "Path(s['observed']).write_text(json.dumps({'arguments':sys.argv[1:],'home':os.environ.get('CODEX_HOME'),'private_env':[n for n in ('OPENAI_API_KEY','PF_AUTHOR_EMAIL','GH_TOKEN') if n in os.environ]}))\n"
        "Path(os.environ['CODEX_HOME'],'auth.json').write_text('fixture-owned-credential')\n"
        "if s['descendant']:\n"
        " child=subprocess.Popen([sys.executable,'-c','import time,signal;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)'])\n"
        " Path(s['observed']+'.child').write_text(str(child.pid))\n"
        "if s['challenge']:\n"
        " print('https://auth.openai.com/codex/device',flush=True)\n"
        " print('Enter this one-time code (expires in 15 minutes)\\n   ABCD-EFGH',flush=True)\n"
        "if s['diagnostic']:print(s['diagnostic'],file=sys.stderr,flush=True)\n"
        "time.sleep(s['delay']);sys.exit(s['code'])\n", encoding="utf-8")
    executable.chmod(0o755)
    state = {"status_calls": 0, "generate_calls": 0}
    monkeypatch.setenv("PF_CODEX_BIN", str(executable))
    manager = ConnectionManager(root or tmp_path / "connection", provider_factory=lambda home: FakeProvider(home, state), login_timeout_seconds=timeout)
    return manager, state, observed


def wait(manager, states, timeout=7):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = manager.status()
        if result["status"] in states and not (manager._worker and manager._worker.is_alive()):
            return result
        time.sleep(0.02)
    pytest.fail("connection operation did not complete: " + json.dumps(manager.status()))


def waiting(manager):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if manager.status()["status"] == "waiting_user":
            return manager.status()
        time.sleep(0.01)
    pytest.fail("device challenge was not available")


def test_status_is_local_and_side_effect_free(tmp_path, monkeypatch):
    manager, state, _ = make_manager(tmp_path, monkeypatch)
    try:
        for _ in range(10):
            assert manager.status()["status"] == "disconnected"
        assert state == {"status_calls": 0, "generate_calls": 0}
        assert not (manager.root / "operation.json").exists()
    finally:
        manager.close()


def test_shared_active_metadata_is_rejected(tmp_path, monkeypatch):
    manager, _, _ = make_manager(tmp_path, monkeypatch)
    profile = "profiles/" + "a" * 32
    connection._private_directory(manager.root / profile)
    active = manager.root / "active.json"
    connection._write_metadata(active, {"version": 1, "profile": profile, "verified": True, "verified_at": _now()})
    try:
        assert manager.status()["connected"] is True
        if os.name == "nt":
            windows_runtime._set_acl(active, "(A;;FA;;;WD)")
        else:
            active.chmod(0o644)
        assert manager.status()["code"] == "AUTH_STORAGE_INVALID"
        assert manager.status()["connected"] is False
    finally:
        private_path(active)
        manager.close()


def test_device_login_transient_code_and_explicit_model_promotion(tmp_path, monkeypatch):
    platform = tmp_path / "platform"
    platform.mkdir()
    (platform / "auth.json").write_text("platform-fixture-untouched")
    monkeypatch.setenv("CODEX_HOME", str(platform))
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-inherit")
    monkeypatch.setenv("PF_AUTHOR_EMAIL", "private@example.org")
    monkeypatch.setenv("GH_TOKEN", "must-not-inherit")
    manager, state, observed = make_manager(tmp_path, monkeypatch, delay=0.3)
    try:
        manager.login()
        challenge = waiting(manager)
        assert challenge["verification_url"] == DEVICE_URL and challenge["user_code"] == "ABCD-EFGH"
        assert "ABCD-EFGH" not in (manager.root / "operation.json").read_text(encoding="utf-8")
        assert not (manager.root / "active.json").exists()
        assert wait(manager, {"authenticated"})["model_available"] is False
        assert state["generate_calls"] == 0
        public = json.loads(observed.read_text(encoding="utf-8"))
        assert public["arguments"] == ["--no-daemon", "-c", 'cli_auth_credentials_store="file"', "login", "--device-auth"]
        assert public["private_env"] == []
        assert Path(public["home"]).parent == manager.root / "profiles"
        assert os.environ["CODEX_HOME"] == str(platform)
        assert (platform / "auth.json").read_text(encoding="utf-8") == "platform-fixture-untouched"
        manager.probe()
        result = wait(manager, {"available"})
        assert result["model_available"] is True and result["connected"] is True
        pointer = json.loads((manager.root / "active.json").read_text(encoding="utf-8"))
        assert set(pointer) == {"version", "profile", "verified", "verified_at"}
        assert pointer["verified"] is True
        assert is_private_path(manager.root / pointer["profile"])
        assert is_private_path(manager.root / "active.json")
        manager.disconnect()
        assert manager.status()["connected"] is False
        assert (platform / "auth.json").read_text(encoding="utf-8") == "platform-fixture-untouched"
        assert (manager.root / pointer["profile"] / "auth.json").exists()
    finally:
        manager.close()


@pytest.mark.parametrize("response", [{"ready": False}, {"ready": 1}, {"ready": True, "extra": 1}, None])
def test_invalid_probe_never_activates(tmp_path, monkeypatch, response):
    manager, state, _ = make_manager(tmp_path, monkeypatch)
    try:
        manager.login();wait(manager, {"authenticated"})
        state["response"] = response
        manager.probe()
        assert wait(manager, {"blocked"})["code"] == "SCHEMA_ERROR"
        assert not (manager.root / "active.json").exists()
    finally:
        manager.close()


def test_failed_replacement_keeps_previous_verified_profile(tmp_path, monkeypatch):
    manager, state, _ = make_manager(tmp_path, monkeypatch)
    try:
        manager.login();wait(manager, {"authenticated"});manager.probe();wait(manager, {"available"})
        old = (manager.root / "active.json").read_bytes()
        manager.login();wait(manager, {"authenticated"})
        state["error"] = "AUTH_REQUIRED"
        manager.probe()
        result = wait(manager, {"blocked"})
        assert result["connected"] and result["model_available"]
        assert (manager.root / "active.json").read_bytes() == old
        assert "raw-private" not in json.dumps(result)
        assert "raw-private" not in (manager.root / "operation.json").read_text(encoding="utf-8")
    finally:
        manager.close()


def test_api_key_login_is_rejected(tmp_path, monkeypatch):
    manager, state, _ = make_manager(tmp_path, monkeypatch)
    state["authentication"] = "api_key"
    try:
        manager.login()
        assert wait(manager, {"blocked"})["code"] == "API_KEY_UNSUPPORTED"
        assert state["generate_calls"] == 0 and not (manager.root / "active.json").exists()
    finally:
        manager.close()


@pytest.mark.parametrize("diagnostic,expected", [
    ("proxy CONNECT 403 raw-private-login-token", "PROXY_BLOCKED"),
    ("Unauthorized HTTP 401 raw-private-login-token", "AUTH_REQUIRED"),
    ("device code login is not enabled for this Codex server", "DEVICE_AUTH_UNAVAILABLE"),
])
def test_login_errors_are_classified_without_raw_output(tmp_path, monkeypatch, diagnostic, expected):
    manager, _, _ = make_manager(tmp_path, monkeypatch, diagnostic=diagnostic, code=1)
    try:
        manager.login()
        result = wait(manager, {"blocked"})
        assert result["code"] == expected
        assert "raw-private" not in json.dumps(result) + (manager.root / "operation.json").read_text(encoding="utf-8")
        assert result["user_code"] is None and result["verification_url"] is None
    finally:
        manager.close()


def test_timeout_and_cancel_stop_device_process(tmp_path, monkeypatch):
    manager, _, _ = make_manager(tmp_path, monkeypatch, delay=60, timeout=1)
    try:
        manager.login();waiting(manager)
        handle = json.loads((manager.root / "operation.json").read_text(encoding="utf-8"))["handle"]
        assert wait(manager, {"blocked"})["code"] == "LOGIN_TIMEOUT"
        assert _start_ticks(handle["pid"]) is None
    finally:
        manager.close()


def test_second_instance_status_close_and_cancel_intent(tmp_path, monkeypatch):
    first, state, _ = make_manager(tmp_path, monkeypatch, delay=60)
    second = None
    try:
        first.login();waiting(first)
        second = ConnectionManager(first.root, provider_factory=lambda home: FakeProvider(home, state))
        assert second.status()["status"] == "waiting_user"
        assert second.login()["code"] == "CONNECTION_BUSY"
        second.close()
        assert first.status()["status"] == "waiting_user"
        second = ConnectionManager(first.root, provider_factory=lambda home: FakeProvider(home, state))
        assert second.cancel()["code"] == "CANCEL_REQUESTED"
        assert wait(first, {"cancelled"})["user_code"] is None
    finally:
        if second: second.close()
        first.close()


def test_cleanup_failure_preserves_handle_and_blocks_new_actions(tmp_path, monkeypatch):
    manager, state, _ = make_manager(tmp_path, monkeypatch)
    state["cleanup"] = False
    try:
        manager.login()
        assert wait(manager, {"blocked"})["code"] == "CLEANUP_UNCONFIRMED"
        old = json.loads((manager.root / "operation.json").read_text(encoding="utf-8"))["handle"]
        assert old is not None
        assert manager.cancel()["code"] == "CLEANUP_UNCONFIRMED"
        assert manager.login()["code"] == "CLEANUP_UNCONFIRMED"
        assert manager.disconnect()["code"] == "CLEANUP_UNCONFIRMED"
        assert json.loads((manager.root / "operation.json").read_text(encoding="utf-8"))["handle"] == old
    finally:
        state["cleanup"] = True
        manager.close()


def test_successful_leader_exit_cleans_stubborn_descendants(tmp_path, monkeypatch):
    manager, _, observed = make_manager(tmp_path, monkeypatch, descendant=True)
    try:
        manager.login();wait(manager, {"authenticated"})
        child = int(Path(str(observed) + ".child").read_text(encoding="utf-8"))
        if os.name == "nt":
            assert _start_ticks(child) is None
        else:
            info = Path(f"/proc/{child}/stat")
            assert not info.exists() or info.read_text(encoding="utf-8").rsplit(")", 1)[1].split()[0] == "Z"
    finally:
        manager.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows original Job handle lifecycle")
@pytest.mark.parametrize("confirmed", [True, False], ids=["confirmed", "unconfirmed"])
def test_cleanup_of_exited_login_leader_closes_original_job_only_after_confirmation(tmp_path, monkeypatch, confirmed):
    manager, _, _ = make_manager(tmp_path, monkeypatch)
    profile = "profiles/" + "a" * 32
    connection._private_directory(manager.root / profile)
    assert manager._begin("login", profile)
    process = subprocess.Popen([sys.executable, "-c", "pass"], **_process_options(suspended=True))
    job = original_stop = None
    try:
        _track_process(process, suspended=True)
        retained = _worker_handle(process)
        manager._record_handle(retained)
        process.wait(timeout=5)
        assert process.poll() == 0
        job = process._paper_factory_job
        original_stop, original_handle = job.stop, job.handle
        assert original_handle is not None
        if not confirmed:
            monkeypatch.setattr(job, "stop", lambda: False)
        assert manager._confirm_cleanup(profile, process) is confirmed
        assert job.handle == (None if confirmed else original_handle)
        assert json.loads((manager.root / "operation.json").read_text(encoding="utf-8"))["handle"] == retained
    finally:
        # Reconcile the real controlled process even if the assertion above
        # fails; this test never leaves a synthetic cleanup failure active.
        if job is not None and original_stop is not None:
            monkeypatch.setattr(job, "stop", original_stop)
        assert connection._try_stop(process)
        manager.close()


@pytest.mark.parametrize("text", [
    "https://evil.example/codex/device\nEnter this one-time code\nABCD-EFGH",
    "https://auth.openai.com.evil/codex/device\nuser_code: ABCD-EFGH",
    "https://auth.openai.com/codex/device?token=secret\nuser_code: ABCD-EFGH",
    "https://auth.openai.com/codex/device\nBearer ABCD-EFGH",
])
def test_only_official_device_challenge_is_extracted(text):
    url, code = _challenge(text)
    assert code is None


def test_checkout_and_platform_home_are_not_adopted(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout";checkout.mkdir();(checkout / ".git").mkdir();(checkout / ".git" / "HEAD").write_text("ref")
    platform = tmp_path / "platform";platform.mkdir();(platform / "auth.json").write_text("untouched")
    monkeypatch.setenv("CODEX_HOME", str(platform))
    for root in (checkout / "auth", platform):
        manager = ConnectionManager(root)
        assert manager.status()["code"] == "AUTH_STORAGE_INVALID"
        manager.close()
    assert (platform / "auth.json").read_text(encoding="utf-8") == "untouched"


def test_placeholder_git_directory_is_not_a_checkout(tmp_path):
    (tmp_path / ".git").mkdir()
    manager = ConnectionManager(tmp_path / "auth")
    try:
        assert manager.status()["status"] == "disconnected"
    finally:
        manager.close()


def test_symlink_auth_root_is_rejected(tmp_path):
    target = tmp_path / "target";target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks is unavailable on this system")
    manager = ConnectionManager(link)
    try:
        assert manager.status()["code"] == "AUTH_STORAGE_INVALID"
    finally:
        manager.close()


def test_restart_recovers_only_unlocked_owned_worker(tmp_path):
    root = tmp_path / "auth";root.mkdir(mode=0o700);profile = "profiles/" + "a" * 32
    private_path(root)
    (root / profile).mkdir(mode=0o700, parents=True)
    private_path(root / profile)
    process = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"], **_process_options())
    _track_process(process)
    write_json(root / "operation.json", {"version": 1, "operation_id": "b" * 32, "kind": "login", "profile": profile,
        "status": "waiting_user", "authentication": "unknown", "started_at": _now(), "expires_at": _now(),
        "handle": _worker_handle(process),
        "code": None, "message": None})
    private_path(root / "operation.json")
    manager = ConnectionManager(root)
    try:
        assert manager.status()["code"] == "INTERRUPTED"
        process.wait(timeout=2)
        assert json.loads((root / "operation.json").read_text(encoding="utf-8"))["handle"] is None
    finally:
        manager.close()
        if process.poll() is None: process.kill();process.wait()


@pytest.mark.parametrize("version,verified_at", [(True, "2026-10-01T00:00:00+00:00"), (1, "2026-10-01T00:00:00")])
def test_invalid_active_metadata_is_not_trusted(tmp_path, version, verified_at):
    root = tmp_path / "auth";root.mkdir(mode=0o700);profile = "profiles/" + "a" * 32
    (root / profile).mkdir(mode=0o700, parents=True)
    write_json(root / "active.json", {"version": version, "profile": profile, "verified": True, "verified_at": verified_at})
    manager = ConnectionManager(root)
    try:
        assert manager.status()["code"] == "AUTH_STORAGE_INVALID"
    finally:
        manager.close()


def test_manager_never_opens_authentication_files(tmp_path, monkeypatch):
    manager, _, _ = make_manager(tmp_path, monkeypatch)
    original = Path.open
    def guarded(path, *args, **kwargs):
        if path.name in {"auth.json", "credentials.json"}:
            pytest.fail("manager must not open authentication files")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)
    try:
        manager.login();wait(manager, {"authenticated"});manager.probe();wait(manager, {"available"})
    finally:
        manager.close()


def test_stale_cancel_intent_does_not_cancel_next_login(tmp_path, monkeypatch):
    first, state, _ = make_manager(tmp_path, monkeypatch, delay=0.3)
    second = None
    try:
        first.login();waiting(first)
        second = ConnectionManager(first.root, provider_factory=lambda home: FakeProvider(home, state))
        second.cancel();wait(first, {"cancelled"})
        old = json.loads((first.root / ".cancel.json").read_text(encoding="utf-8"))["operation_id"]
        first.login();wait(first, {"authenticated"})
        assert json.loads((first.root / "operation.json").read_text(encoding="utf-8"))["operation_id"] != old
    finally:
        if second: second.close()
        first.close()


def test_cancelled_probe_preserves_previous_active_profile(tmp_path, monkeypatch):
    manager, state, _ = make_manager(tmp_path, monkeypatch)
    try:
        manager.login();wait(manager, {"authenticated"});manager.probe();wait(manager, {"available"})
        old = (manager.root / "active.json").read_bytes()
        manager.login();wait(manager, {"authenticated"})
        state["probe_wait"] = True
        manager.probe()
        manager.cancel()
        assert wait(manager, {"cancelled"})["model_available"] is True
        assert (manager.root / "active.json").read_bytes() == old
    finally:
        manager.close()


def test_no_challenge_has_separate_bounded_startup_deadline(tmp_path, monkeypatch):
    manager, _, _ = make_manager(tmp_path, monkeypatch, delay=60, challenge=False)
    manager.startup_challenge_timeout_seconds = 1
    try:
        manager.login()
        assert wait(manager, {"blocked"})["code"] == "LOGIN_START_TIMEOUT"
        assert manager.status()["user_code"] is None
    finally:
        manager.close()


def test_login_reader_start_exception_retains_unconfirmed_worker_handle(tmp_path, monkeypatch):
    manager, state, _ = make_manager(tmp_path, monkeypatch)
    profile = "profiles/" + "d" * 32
    connection._private_directory(manager.root / profile)
    assert manager._begin("login", profile)
    state["cleanup"] = False
    class Process:
        pid = 999999
        stdout = io.BufferedReader(io.BytesIO())
        stderr = io.BufferedReader(io.BytesIO())
        def poll(self):
            return None
    monkeypatch.setattr(connection.subprocess, "Popen", lambda *args, **kwargs: Process())
    handle = {"kind": "codex", "pid": 999999, "pgid": 999999, "start_ticks": 1}
    monkeypatch.setattr(connection, "_cli_command", lambda binary: [binary])
    monkeypatch.setattr(connection, "_track_process", lambda process, **kwargs: None)
    monkeypatch.setattr(connection, "_worker_handle", lambda process: handle)
    monkeypatch.setattr(connection, "_try_stop", lambda process: False)
    def failed_start(thread):
        raise RuntimeError("fixture-reader-start-failure")
    monkeypatch.setattr(connection.threading.Thread, "start", failed_start)
    try:
        manager._login_worker("fixture-codex", profile)
        assert manager.status()["code"] == "CLEANUP_UNCONFIRMED"
        handle = json.loads((manager.root / "operation.json").read_text(encoding="utf-8"))["handle"]
        assert handle == {"kind": "codex", "pid": 999999, "pgid": 999999, "start_ticks": 1}
        assert manager.cancel()["code"] == "CLEANUP_UNCONFIRMED"
        assert manager.disconnect()["code"] == "CLEANUP_UNCONFIRMED"
        assert json.loads((manager.root / "operation.json").read_text(encoding="utf-8"))["handle"] == handle
    finally:
        manager.close()


def test_probe_exception_retains_unconfirmed_worker_handle(tmp_path, monkeypatch):
    manager, state, _ = make_manager(tmp_path, monkeypatch)
    try:
        manager.login();wait(manager, {"authenticated"})
        state["cleanup"] = False
        handle = {"kind": "codex", "pid": 999999, "pgid": 999999, "start_ticks": 1}
        def failed_generate(provider, prompt, schema, call_dir, **kwargs):
            kwargs["on_handle"](handle)
            raise RuntimeError("fixture-unexpected-provider-error")
        monkeypatch.setattr(FakeProvider, "generate", failed_generate)
        manager.probe()
        assert wait(manager, {"blocked"})["code"] == "CLEANUP_UNCONFIRMED"
        assert json.loads((manager.root / "operation.json").read_text(encoding="utf-8"))["handle"] == handle
        assert not (manager.root / "active.json").exists()
        assert manager.cancel()["code"] == "CLEANUP_UNCONFIRMED"
    finally:
        manager.close()


@pytest.mark.parametrize("valid_identity", [True, False], ids=["retained-identity", "missing-identity"])
def test_probe_undelivered_cleanup_identity_preserves_receipts_and_blocks_new_workers(tmp_path, monkeypatch, valid_identity):
    manager, state, _ = make_manager(tmp_path, monkeypatch)
    retained = {"kind": "codex", "pid": 999999, "pgid": 999999, "start_ticks": 1 if valid_identity else None}
    calls = []
    def failed_generate(provider, prompt, schema, call_dir, **kwargs):
        calls.append(Path(call_dir))
        write_json(Path(call_dir) / "receipt.json", {"simulation": True, "active_handle": retained})
        raise ProviderBlocked("CLEANUP_UNCONFIRMED", "Simulated ownership callback failure", active_handle=retained)
    try:
        manager.login(); wait(manager, {"authenticated"})
        state["cleanup"] = False
        monkeypatch.setattr(FakeProvider, "generate", failed_generate)
        manager.probe()
        assert wait(manager, {"blocked"})["code"] == "CLEANUP_UNCONFIRMED"
        operation = json.loads((manager.root / "operation.json").read_text(encoding="utf-8"))
        assert operation["handle"] == (retained if valid_identity else None)
        assert (calls[0] / "receipt.json").is_file()
        assert not (manager.root / "active.json").exists()
        assert manager.login()["code"] == "CLEANUP_UNCONFIRMED"
        assert manager.probe()["code"] == "CLEANUP_UNCONFIRMED"
        assert len(calls) == 1
    finally:
        manager.close()


def test_accepted_cross_instance_cancel_prevents_probe_promotion(tmp_path, monkeypatch):
    manager, state, _ = make_manager(tmp_path, monkeypatch)
    peer = None
    try:
        manager.login();wait(manager, {"authenticated"})
        peer = ConnectionManager(manager.root, provider_factory=lambda home: FakeProvider(home, state))
        accepted = []
        def generate_then_cancel(provider, prompt, schema, call_dir, **kwargs):
            accepted.append(peer.cancel()["code"])
            return {"ready": True}
        monkeypatch.setattr(FakeProvider, "generate", generate_then_cancel)
        manager.probe()
        assert wait(manager, {"cancelled"})["code"] == "CANCELLED"
        assert accepted == ["CANCEL_REQUESTED"]
        assert not (manager.root / "active.json").exists()
    finally:
        if peer: peer.close()
        manager.close()


def test_probe_commit_serializes_cross_instance_cancel_acceptance(tmp_path, monkeypatch):
    manager, state, _ = make_manager(tmp_path, monkeypatch)
    peer = None
    try:
        manager.login();wait(manager, {"authenticated"})
        peer = ConnectionManager(manager.root, provider_factory=lambda home: FakeProvider(home, state))
        after_response, cancellation = [], []
        def generated(provider, prompt, schema, call_dir, **kwargs):
            after_response.append(True)
            return {"ready": True}
        def at_commit():
            if after_response and not cancellation:
                cancellation.append(peer.cancel()["code"])
            return _now()
        monkeypatch.setattr(FakeProvider, "generate", generated)
        monkeypatch.setattr(connection, "_now", at_commit)
        manager.probe()
        result = wait(manager, {"available"})
        assert result["model_available"]
        assert cancellation == ["CONNECTION_BUSY"]
        assert not (manager.root / ".cancel.json").exists()
    finally:
        if peer: peer.close()
        manager.close()

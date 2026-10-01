"""Official-CLI adapter boundaries exercised with real subprocesses."""

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

from paper_factory.autonomous.provider import CodexProvider, ProviderBlocked, MAX_LOG_BYTES, DISABLED_FEATURES, auth_root, resolve_auth_home

SCHEMA = {"type": "object", "properties": {"answer": {"type": "integer"}}, "required": ["answer"], "additionalProperties": False}


@pytest.fixture(autouse=True)
def private_auth_selection(tmp_path, monkeypatch):
    # Unit tests never consult a user or cloud worker's connection pointer.
    monkeypatch.setenv("PF_CODEX_AUTH_HOME", str(tmp_path / "connections"))


def connected_profile(root, identity="a" * 32, *, active=True):
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    profiles = root / "profiles"
    profiles.mkdir(mode=0o700, exist_ok=True)
    home = profiles / identity
    home.mkdir(mode=0o700)
    if active:
        pointer = root / "active.json"
        pointer.write_text(json.dumps({"version": 1, "profile": "profiles/" + identity, "verified": True,
                                       "verified_at": "2026-10-01T12:00:00+00:00"}))
        pointer.chmod(0o600)
    return home


def fake_codex(tmp_path, *, output='{"answer":42}', diagnostic="", code=0, authentication="chatgpt", sleep=0, events=None, spawn_child=False, read_stdin=True, missing_capability=None, stubborn_child=False):
    path = tmp_path / "codex-fake"
    settings = {"output": output, "diagnostic": diagnostic, "code": code, "authentication": authentication,
                "sleep": sleep, "events": events if events is not None else [{"type": "turn.completed", "usage": {"input_tokens": 11, "cached_input_tokens": 3, "output_tokens": 7}, "model": "actual-model"}], "spawn_child": spawn_child, "read_stdin": read_stdin,
                "missing_capability": missing_capability, "features": list(DISABLED_FEATURES), "stubborn_child": stubborn_child}
    path.write_text(
        f"#!{sys.executable}\n"
        "import json,os,sys,time,subprocess\nfrom pathlib import Path\n"
        f"settings=json.loads({json.dumps(json.dumps(settings))})\n"
        "arguments=sys.argv[1:]\n"
        "if arguments==['--version']:print('codex-cli 1.2.3-test');sys.exit(0)\n"
        "if arguments==['--help']:\n"
        " print(' '.join(flag for flag in ('--no-daemon','--ask-for-approval') if flag!=settings['missing_capability']));sys.exit(0)\n"
        "if arguments==['exec','--help']:\n"
        " print(' '.join(flag for flag in ('--ignore-user-config','--ignore-rules','--ephemeral','--skip-git-repo-check','--sandbox','--json','--output-schema','--output-last-message','--disable') if flag!=settings['missing_capability']));sys.exit(0)\n"
        "if arguments==['features','list']:\n"
        " print('\\n'.join(feature+' stable true' for feature in settings['features'] if 'feature:'+feature!=settings['missing_capability']));sys.exit(0)\n"
        "if arguments==['login','status']:\n"
        " authentication=settings['authentication']\n"
        " print('Logged in using ChatGPT' if authentication=='chatgpt' else 'Logged in using an API key: sk-not-persist-this-value' if authentication=='api_key' else 'Not logged in',file=sys.stderr)\n"
        " sys.exit(0 if authentication in ('chatgpt','api_key') else 1)\n"
        "prompt=sys.stdin.read() if settings['read_stdin'] else ''\n"
        "destination=Path(arguments[arguments.index('-o')+1])\n"
        "work=Path(arguments[arguments.index('-C')+1])\n"
        "observed={'arguments':arguments,'cwd':str(Path.cwd()),'workspace_files':[p.name for p in work.iterdir()],"
        "'private_env_present':[name for name in ('PF_AUTHOR_EMAIL','PF_OJS_API_TOKEN','OPENAI_API_KEY','OTHER_SECRET') if name in os.environ],"
        "'codex_home_present':'CODEX_HOME' in os.environ,'codex_home':os.environ.get('CODEX_HOME'),'prompt':prompt}\n"
        "(destination.parent/'observed.json').write_text(json.dumps(observed))\n"
        "if settings['spawn_child']:\n"
        " ready=destination.parent/'child.ready'\n"
        " child_code='import time,signal; from pathlib import Path; '+('signal.signal(signal.SIGTERM,signal.SIG_IGN); ' if settings['stubborn_child'] else '')+'Path('+repr(str(ready))+').write_text(\"ready\"); time.sleep(60)'\n"
        " child=subprocess.Popen([sys.executable,'-c',child_code])\n"
        " while not ready.exists():time.sleep(0.01)\n"
        " (destination.parent/'child.pid').write_text(str(child.pid))\n"
        "for event in settings['events']:print(json.dumps(event),flush=True)\n"
        "if settings['diagnostic']:print(settings['diagnostic'],file=sys.stderr,flush=True)\n"
        "time.sleep(settings['sleep'])\n"
        "if settings['output'] is not None:destination.write_text(settings['output'])\n"
        "sys.exit(settings['code'])\n", encoding="utf-8",
    )
    path.chmod(0o755)
    return CodexProvider(path)


def test_status_reports_existing_authentication_without_raw_key(tmp_path):
    for auth in ("chatgpt", "api_key", "logged_out"):
        provider = fake_codex(tmp_path, authentication=auth)
        result = provider.status()
        assert result == {"executable_available": True, "authentication": auth, "ready": auth != "logged_out",
                          "cli_version": "1.2.3-test", "capabilities_supported": True, "missing_capabilities": []}
        assert "sk-" not in json.dumps(result)
    assert CodexProvider(tmp_path / "missing").status() == {"executable_available": False, "authentication": "unknown", "ready": False,
                                                         "cli_version": None, "capabilities_supported": False, "missing_capabilities": []}


def test_generation_validates_schema_and_records_real_usage_and_model(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_AUTHOR_EMAIL", "private@example.org")
    monkeypatch.setenv("PF_OJS_API_TOKEN", "private-publication-token")
    monkeypatch.setenv("OPENAI_API_KEY", "private-api-key")
    monkeypatch.setenv("OTHER_SECRET", "private-other-secret")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "existing-official-auth-home"))
    call = tmp_path / "call"
    handles = []
    prompt = "Generate the known answer without using any tools."
    result = fake_codex(tmp_path).generate(prompt, SCHEMA, call, model="requested-model", on_handle=handles.append)
    assert result == {"answer": 42}
    receipt = json.loads((call / "receipt.json").read_text())
    assert receipt["status"] == "completed"
    assert receipt["cli_version"] == "1.2.3-test" and receipt["capabilities_supported"] is True
    assert receipt["actual_model"] == "actual-model"
    assert receipt["requested_model"] == "requested-model"
    assert receipt["usage"] == {"input_tokens": 11, "cached_input_tokens": 3, "output_tokens": 7}
    assert receipt["prompt_sha256"] == hashlib.sha256(prompt.encode()).hexdigest()
    assert receipt["output_sha256"] == hashlib.sha256((call / "output.json").read_bytes()).hexdigest()
    assert receipt["elapsed_seconds"] >= 0
    observed = json.loads((call / "observed.json").read_text())
    assert observed["private_env_present"] == []
    assert observed["codex_home_present"] is True
    assert observed["workspace_files"] == []
    assert observed["cwd"] != str(call)
    assert observed["prompt"].startswith(prompt + "\n\nStructured-output adapter:")
    assert receipt["model_input_prompt_sha256"] == hashlib.sha256(observed["prompt"].encode()).hexdigest()
    assert receipt["wire_schema_sha256"] == receipt["model_input_schema_sha256"] == hashlib.sha256((call / "schema.json").read_bytes()).hexdigest()
    assert receipt["raw_output_sha256"] == hashlib.sha256((call / "model-output.json").read_bytes()).hexdigest()
    assert receipt["normalized_output_sha256"] == receipt["output_sha256"]
    arguments = observed["arguments"]
    assert arguments[arguments.index("--sandbox") + 1] == "read-only"
    assert arguments[arguments.index("-a") + 1] == "never"
    assert "--dangerously-bypass-approvals-and-sandbox" not in arguments
    assert "--ephemeral" in arguments and "--ignore-user-config" in arguments
    assert "shell_tool" in arguments and "unified_exec" in arguments and "plugins" in arguments
    assert json.loads((call / "runtime-handle.json").read_text()) == handles[0]
    assert handles[0]["kind"] == "codex" and handles[0]["pid"] > 0
    if Path("/proc").is_dir():
        assert handles[0]["start_ticks"] > 0
    for log in (call / "stdout.log", call / "stderr.log"):
        assert "private-publication-token" not in log.read_text()
        assert "private-api-key" not in log.read_text()


def test_unknown_model_is_recorded_as_unknown_not_invented(tmp_path):
    call = tmp_path / "call"
    fake_codex(tmp_path, events=[{"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 2}}]).generate("Make an answer", SCHEMA, call)
    receipt = json.loads((call / "receipt.json").read_text())
    assert receipt["actual_model"] is None
    assert receipt["requested_model"] is None


@pytest.mark.parametrize("diagnostic,expected", [("Usage limit reached", "RATE_LIMITED"), ("401 unauthorized", "AUTH_REQUIRED"), ("DNS network connection failed", "NETWORK_ERROR"), ("response_format schema invalid", "SCHEMA_ERROR"), ("Read-only file system", "CONFIGURATION_ERROR"), ("Unknown internal failure", "CODEX_FAILED")])
def test_cli_failures_are_classified_without_partial_output(tmp_path, diagnostic, expected):
    call = tmp_path / "call"
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, diagnostic=diagnostic, code=1).generate("Make an answer", SCHEMA, call)
    assert raised.value.code == expected
    receipt = json.loads((call / "receipt.json").read_text())
    assert receipt["code"] == expected
    assert receipt["status"] == "blocked"
    assert not (call / "output.json").exists()


@pytest.mark.parametrize("response", ['{"answer":"wrong"}', '{"answer":42,"unknown":1}', '{"answer":42,"answer":43}', '{"answer":NaN}', 'not JSON', '[]'])
def test_unstructured_or_invalid_responses_are_not_accepted(tmp_path, response):
    call = tmp_path / "call"
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, output=response).generate("Make an answer", SCHEMA, call)
    assert raised.value.code == "SCHEMA_ERROR"
    assert not (call / "output.json").exists()


def test_external_schema_refs_and_invalid_schema_are_rejected_before_execution(tmp_path):
    provider = fake_codex(tmp_path)
    for schema in ({"$ref": "https://untrusted.example/schema"}, {"type": "made-up"}):
        with pytest.raises(ProviderBlocked) as raised:
            provider.generate("Make an answer", schema, tmp_path / "unused")
        assert raised.value.code == "SCHEMA_ERROR"
    assert not (tmp_path / "unused").exists()


def test_authentication_required_is_a_visible_blocker_without_login_attempt(tmp_path):
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, authentication="logged_out").generate("Make an answer", SCHEMA, tmp_path / "call")
    assert raised.value.code == "AUTH_REQUIRED"
    assert not (tmp_path / "call" / "observed.json").exists()


def test_tool_actions_are_rejected_even_when_cli_returns_valid_json(tmp_path):
    event = {"type": "item.started", "item": {"type": "command_execution", "command": "cat credentials"}}
    call = tmp_path / "call"
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, events=[event]).generate("Make an answer", SCHEMA, call)
    assert raised.value.code == "POLICY_VIOLATION"
    assert "cat credentials" not in (call / "stdout.log").read_text()
    assert not (call / "output.json").exists()


def test_cancellation_terminates_process_group_and_records_stable_handle(tmp_path):
    call = tmp_path / "call"
    handles = []
    provider = fake_codex(tmp_path, sleep=60, spawn_child=True)
    def cancel():
        return (call / "child.pid").exists()
    with pytest.raises(ProviderBlocked) as raised:
        provider.generate("Make an answer", SCHEMA, call, cancel=cancel, on_handle=handles.append)
    assert raised.value.code == "CANCELLED"
    assert json.loads((call / "receipt.json").read_text())["status"] == "cancelled"
    assert handles
    child_pid = int((call / "child.pid").read_text())
    if Path("/proc").is_dir():
        child_stat = Path(f"/proc/{child_pid}/stat")
        # A briefly unreaped zombie has stopped executing too.
        assert not child_stat.exists() or child_stat.read_text().rsplit(")", 1)[1].split()[0] == "Z"


def test_timeout_terminates_running_call_and_retains_failure_receipt(tmp_path):
    call = tmp_path / "call"
    started = time.monotonic()
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, sleep=60).generate("Make an answer", SCHEMA, call, timeout_seconds=1)
    assert raised.value.code == "TIMEOUT"
    assert time.monotonic() - started < 5
    assert json.loads((call / "receipt.json").read_text())["code"] == "TIMEOUT"


def test_logs_are_bounded_and_secret_values_are_redacted(tmp_path, monkeypatch):
    monkeypatch.setenv("PRIVATE_TOKEN", "test-private-token-value")
    diagnostic = "x" * (MAX_LOG_BYTES * 2) + "test-private-token-value https://user:password@example.org bearer private-token"
    call = tmp_path / "call"
    fake_codex(tmp_path, diagnostic=diagnostic).generate("Make an answer", SCHEMA, call)
    stderr = (call / "stderr.log").read_text()
    assert len(stderr) <= MAX_LOG_BYTES
    assert "test-private-token-value" not in stderr
    assert "user:password" not in stderr


def test_uninjected_cli_token_shapes_are_redacted_without_reading_auth_files(tmp_path):
    call = tmp_path / "call"
    jwt = "eyJ0ZXN0aW5nLXRva2Vu.e30.syntheticSignature"
    diagnostic = 'token failure {"refresh_token":"opaque-sensitive-credential"} ' + jwt
    fake_codex(tmp_path, diagnostic=diagnostic).generate("Make an answer", SCHEMA, call)
    stderr = (call / "stderr.log").read_text()
    assert "opaque-sensitive-credential" not in stderr
    assert jwt not in stderr
    assert "[redacted]" in stderr


def test_existing_call_artifacts_are_never_overwritten(tmp_path):
    call = tmp_path / "call"
    call.mkdir()
    (call / "output.json").write_text("original")
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path).generate("Make an answer", SCHEMA, call)
    assert raised.value.code == "INVALID_CALL_DIR"
    assert (call / "output.json").read_text() == "original"


def test_per_call_model_overrides_environment_and_prompt_secrets_never_leave(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_CODEX_MODEL", "configured-model")
    call = tmp_path / "call"
    fake_codex(tmp_path).generate("Make an answer", SCHEMA, call, model="explicit-model")
    observed = json.loads((call / "observed.json").read_text())
    assert observed["arguments"][observed["arguments"].index("--model") + 1] == "explicit-model"
    monkeypatch.setenv("PRIVATE_TOKEN", "credential-do-not-send")
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path).generate("Contains credential-do-not-send", SCHEMA, tmp_path / "unsafe")
    assert raised.value.code == "UNSAFE_INPUT"
    assert not (tmp_path / "unsafe").exists()


def test_cli_error_items_are_diagnostics_not_tool_actions(tmp_path):
    event = {"type": "item.completed", "item": {"type": "error", "message": "401 unauthorized"}}
    call = tmp_path / "call"
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, code=1, events=[event]).generate("Make an answer", SCHEMA, call)
    assert raised.value.code == "AUTH_REQUIRED"
    assert '"item_type": "error"' in (call / "stdout.log").read_text()


def test_timeout_remains_effective_when_cli_never_reads_large_stdin(tmp_path):
    call = tmp_path / "call"
    started = time.monotonic()
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, sleep=60, read_stdin=False).generate("x" * (512 * 1024), SCHEMA, call, timeout_seconds=1)
    assert raised.value.code == "TIMEOUT"
    assert time.monotonic() - started < 5


def test_explicit_proxy_denial_stops_cli_retry_loop_early(tmp_path):
    event = {"type": "error", "message": "HTTP CONNECT 403 from proxy"}
    started = time.monotonic()
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, events=[event], sleep=60).generate("Make an answer", SCHEMA, tmp_path / "call", timeout_seconds=30)
    assert raised.value.code == "NETWORK_ERROR"
    assert "HTTP CONNECT 403" in raised.value.message
    assert time.monotonic() - started < 5


def test_proxy_denial_remains_transport_error_with_authentication_word(tmp_path):
    diagnostic = "HTTP CONNECT 403: proxy denied authentication transport"
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, diagnostic=diagnostic, code=1).generate("Make an answer", SCHEMA, tmp_path / "call")
    assert raised.value.code == "NETWORK_ERROR"
    assert "HTTP CONNECT 403" in raised.value.message


def test_unicode_diagnostics_have_actual_byte_cap(tmp_path):
    call = tmp_path / "call"
    fake_codex(tmp_path, diagnostic="측정🙂" * MAX_LOG_BYTES).generate("Make an answer", SCHEMA, call)
    raw = (call / "stderr.log").read_bytes()
    assert len(raw) <= MAX_LOG_BYTES
    assert raw.decode("utf-8")


@pytest.mark.parametrize("missing", ["--ignore-rules", "--no-daemon", "feature:shell_tool"])
def test_unsupported_cli_is_blocked_before_model_dispatch(tmp_path, missing):
    provider = fake_codex(tmp_path, missing_capability=missing)
    status = provider.status()
    assert status["authentication"] == "chatgpt"
    assert status["cli_version"] == "1.2.3-test"
    assert status["ready"] is False and status["capabilities_supported"] is False
    assert status["missing_capabilities"] == [missing]
    call = tmp_path / "call"
    with pytest.raises(ProviderBlocked) as raised:
        provider.generate("Make an answer", SCHEMA, call)
    assert raised.value.code == "CODEX_UNSUPPORTED"
    assert not (call / "observed.json").exists()
    receipt = json.loads((call / "receipt.json").read_text())
    assert receipt["code"] == "CODEX_UNSUPPORTED" and receipt["missing_capabilities"] == [missing]


def test_isolated_runtime_keeps_auth_home_readonly_and_mounts_only_call_context(tmp_path, monkeypatch):
    provider = fake_codex(tmp_path)
    home = tmp_path / "injected-auth-home"
    home.mkdir()
    call = tmp_path / "call"
    (call / "runtime").mkdir(parents=True)
    certificate = tmp_path / "public-trust.pem"
    certificate.write_text("synthetic-public-ca")
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("SSL_CERT_FILE", str(certificate))
    from paper_factory.autonomous import provider as provider_module
    original_which = provider_module.shutil.which
    monkeypatch.setattr(provider_module.shutil, "which", lambda value: "/trusted/docker" if value == "docker" else original_which(value))
    class Inspection:
        returncode = 0
        stdout = ("sha256:" + "a" * 64).encode()
    monkeypatch.setattr(provider_module.subprocess, "run", lambda *args, **kwargs: Inspection())
    command = [str(tmp_path / "codex-fake"), "exec", "-C", "/temporary/empty", "--output-schema", str(call / "schema.json"), "-o", str(call / "output.json"), "-"]
    arguments, name, image = provider._container_command(command, call)
    assert name.startswith("paper-factory-codex-")
    assert image == "sha256:" + "a" * 64
    mounts = [arguments[index + 1] for index, value in enumerate(arguments[:-1]) if value == "--mount"]
    assert f"type=bind,src={home},dst={home},readonly" in mounts
    assert f"type=bind,src={certificate},dst={certificate},readonly" in mounts
    assert f"type=bind,src={call},dst={call}" in mounts
    assert f"type=bind,src={call / 'runtime/installation_id'},dst={home}/installation_id" in mounts
    assert all("/var/run/docker.sock" not in mount for mount in mounts)
    assert all(f"src={tmp_path}," not in mount for mount in mounts)
    assert "--privileged" not in arguments
    assert arguments[arguments.index("--network") + 1] == "host"
    assert arguments[arguments.index("-C") + 1] == "/tmp"
    assert arguments[arguments.index("--cap-drop") + 1] == "ALL"
    assert str(home) not in arguments[arguments.index("-e") + 1:arguments.index(image)]
    assert (call / "runtime/installation_id").is_file()
    assert list(home.iterdir()) == []


def test_only_known_pre_request_readonly_initialization_failure_uses_runtime_fallback(tmp_path, monkeypatch):
    provider = fake_codex(tmp_path)
    call = tmp_path / "call"
    invocations = []
    def execute(command, prompt, root, work, receipt, sensitive, cancel, timeout, on_handle, container_name=None, environment=None):
        invocations.append(container_name)
        if container_name is None:
            return 1, "failed to initialize in-process app-server client: Read-only file system"
        (root / "output.json").write_text('{"answer":42}')
        receipt["usage"] = {"input_tokens": 1, "output_tokens": 2}
        return 0, ""
    monkeypatch.setattr(provider, "_execute", execute)
    monkeypatch.setattr(provider, "_container_command", lambda command, root, **kwargs: (["docker", "fake"], "owned-container", "sha256:" + "a" * 64))
    assert provider.generate("Make an answer", SCHEMA, call) == {"answer": 42}
    assert invocations == [None, "owned-container"]
    assert json.loads((call / "receipt.json").read_text())["runtime_backend"] == "docker"


def test_model_network_failure_does_not_dispatch_a_second_call(tmp_path, monkeypatch):
    provider = fake_codex(tmp_path, diagnostic="HTTP CONNECT 403 from proxy", code=1)
    def unexpected_fallback(*args):
        pytest.fail("A model-service failure must never dispatch a duplicate generation")
    monkeypatch.setattr(provider, "_container_command", unexpected_fallback)
    with pytest.raises(ProviderBlocked) as raised:
        provider.generate("Make an answer", SCHEMA, tmp_path / "call")
    assert raised.value.code == "NETWORK_ERROR"


def test_blank_optional_codex_settings_keep_cli_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_CODEX_BIN", "")
    monkeypatch.setenv("PF_CODEX_MODEL", "")
    assert CodexProvider().configured_executable == "codex"
    call = tmp_path / "call"
    fake_codex(tmp_path).generate("Make an answer", SCHEMA, call)
    receipt = json.loads((call / "receipt.json").read_text())
    assert receipt["requested_model"] is None
    assert "--model" not in json.loads((call / "observed.json").read_text())["arguments"]


def test_strict_wire_schema_roundtrips_nested_maps_refs_and_defaults(tmp_path):
    schema = {"type": "object", "properties": {
        "parameters": {"type": "object", "additionalProperties": {"$ref": "#/$defs/Measurement"}},
        "description": {"type": "string", "default": "optional"}}, "required": ["parameters"], "additionalProperties": False,
        "$defs": {"Measurement": {"type": "object", "properties": {
            "measurement": {"type": "number"}, "tags": {"type": "object", "additionalProperties": {"type": "string"}, "default": {}}},
            "required": ["measurement"], "additionalProperties": False}}}
    raw = {"parameters": [{"key": "run-a", "value": {"measurement": 3.5, "tags": [{"key": "unit", "value": "ms"}]}}], "description": "Recorded data"}
    call = tmp_path / "call"
    output = fake_codex(tmp_path, output=json.dumps(raw)).generate("Create experiment settings", schema, call)
    assert output == {"parameters": {"run-a": {"measurement": 3.5, "tags": {"unit": "ms"}}}, "description": "Recorded data"}
    wire = json.loads((call / "schema.json").read_text())
    assert wire["required"] == ["parameters", "description"]
    assert "default" not in wire["properties"]["description"]
    assert wire["properties"]["parameters"]["type"] == "array"
    assert wire["properties"]["parameters"]["items"]["additionalProperties"] is False
    assert wire["$defs"]["Measurement"]["required"] == ["measurement", "tags"]
    assert "default" not in wire["$defs"]["Measurement"]["properties"]["tags"]
    assert json.loads((call / "model-output.json").read_text()) == raw
    assert json.loads((call / "output.json").read_text()) == output
    receipt = json.loads((call / "receipt.json").read_text())
    assert receipt["raw_output_sha256"] != receipt["normalized_output_sha256"]
    assert schema["properties"]["description"]["default"] == "optional"


@pytest.mark.parametrize("entries", [[{"key": "same", "value": 1}, {"key": "same", "value": 2}],
                                    [{"key": "x", "value": 1, "unknown": 2}], [{"key": "x", "value": "wrong"}]])
def test_invalid_wire_map_entries_are_never_restored(tmp_path, entries):
    schema = {"type": "object", "additionalProperties": {"type": "integer"}}
    call = tmp_path / "call"
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, output=json.dumps(entries)).generate("Produce map", schema, call)
    assert raised.value.code == "SCHEMA_ERROR"
    assert not (call / "output.json").exists()
    assert not (call / "model-output.json").exists()


def test_restored_map_must_also_satisfy_original_schema(tmp_path):
    schema = {"type": "object", "additionalProperties": {"type": "integer"}, "required": ["must-exist"]}
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, output='[{"key":"other","value":1}]').generate("Produce map", schema, tmp_path / "call")
    assert raised.value.code == "SCHEMA_ERROR"


def test_original_optional_fields_are_required_in_wire_response(tmp_path):
    schema = {"type": "object", "properties": {"answer": {"type": "integer", "default": 42}}, "additionalProperties": False}
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, output="{}").generate("Produce settings", schema, tmp_path / "call")
    assert raised.value.code == "SCHEMA_ERROR"


@pytest.mark.parametrize("schema", [{"type": "object"}, {"type": "object", "additionalProperties": True},
                                    {"type": "object", "additionalProperties": {}}])
def test_untyped_free_objects_are_rejected_before_dispatch(tmp_path, schema):
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path).generate("Produce settings", schema, tmp_path / "call")
    assert raised.value.code == "SCHEMA_ERROR"
    assert not (tmp_path / "call").exists()


def test_free_map_union_values_are_restored_by_declared_branch(tmp_path):
    schema = {"type": "object", "properties": {"parameters": {"type": "object", "additionalProperties": {"anyOf": [
        {"type": "integer"}, {"type": "string"}, {"type": "array", "items": {"type": "integer"}}]}}}, "additionalProperties": False}
    wire = {"parameters": [{"key": "count", "value": 5}, {"key": "label", "value": "run"}, {"key": "seeds", "value": [1, 2]}]}
    result = fake_codex(tmp_path, output=json.dumps(wire)).generate("Produce settings", schema, tmp_path / "call")
    assert result == {"parameters": {"count": 5, "label": "run", "seeds": [1, 2]}}


@pytest.mark.parametrize("secret", ['secret-with-"quote', "secret-with-\nnewline", "비밀-유니코드-value"])
def test_decoded_response_secrets_are_rejected_after_json_escaping(tmp_path, monkeypatch, secret):
    monkeypatch.setenv("PRIVATE_TOKEN", secret)
    schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False}
    call = tmp_path / "call"
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, output=json.dumps({"text": secret}, ensure_ascii=True)).generate("Produce text", schema, call)
    assert raised.value.code == "UNSAFE_OUTPUT"
    assert not (call / "output.json").exists()


def test_terminal_failed_event_cannot_be_accepted_with_exit_zero(tmp_path):
    event = {"type": "turn.failed", "error": {"message": "Generic server rejected response"}}
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, events=[event]).generate("Make an answer", SCHEMA, tmp_path / "call")
    assert raised.value.code == "CODEX_FAILED"


def test_socks_proxy_userinfo_is_redacted_in_logs(tmp_path, monkeypatch):
    proxy = "socks5h://synthetic-user:synthetic-password@proxy.example:1234"
    monkeypatch.setenv("ALL_PROXY", proxy)
    call = tmp_path / "call"
    fake_codex(tmp_path, diagnostic=proxy).generate("Make an answer", SCHEMA, call)
    assert "synthetic-user" not in (call / "stderr.log").read_text()
    assert "synthetic-password" not in (call / "stderr.log").read_text()


def test_post_request_initialization_text_does_not_repeat_model_dispatch(tmp_path, monkeypatch):
    provider = fake_codex(tmp_path)
    def execute(command, prompt, root, work, receipt, *args, **kwargs):
        receipt["usage"] = {"input_tokens": 7, "output_tokens": 2}
        return 1, "failed to initialize in-process app-server client: Read-only file system"
    monkeypatch.setattr(provider, "_execute", execute)
    monkeypatch.setattr(provider, "_container_command", lambda *args: pytest.fail("Post-request failure must not retry"))
    with pytest.raises(ProviderBlocked) as raised:
        provider.generate("Make an answer", SCHEMA, tmp_path / "call")
    assert raised.value.code == "CONFIGURATION_ERROR"


def test_cancellation_kills_descendant_ignoring_sigterm_after_leader_exits(tmp_path):
    call = tmp_path / "call"
    provider = fake_codex(tmp_path, sleep=60, spawn_child=True, stubborn_child=True)
    with pytest.raises(ProviderBlocked) as raised:
        provider.generate("Produce answer", SCHEMA, call, cancel=lambda: (call / "child.pid").exists())
    assert raised.value.code == "CANCELLED"
    child = Path(f"/proc/{(call / 'child.pid').read_text()}/stat")
    if Path("/proc").is_dir():
        assert not child.exists() or child.read_text().rsplit(")", 1)[1].split()[0] == "Z"
    assert json.loads((call / "receipt.json").read_text())["cleanup_confirmed"] is True


@pytest.mark.parametrize("mode", ["failure", "timeout"])
def test_container_cleanup_needs_confirmed_removal_or_absence(tmp_path, monkeypatch, mode):
    from paper_factory.autonomous import provider as module
    provider = fake_codex(tmp_path)
    name = "paper-factory-codex-" + "a" * 16
    identity = "b" * 64
    monkeypatch.setattr(module.shutil, "which", lambda *args: "/trusted/docker")
    calls = []
    def run(arguments, **kwargs):
        calls.append(arguments)
        assert "DOCKER_CONFIG" in kwargs["env"]
        if "inspect" in arguments:
            return type("Result", (), {"returncode": 0, "stdout": f"{identity} /{name}".encode()})()
        if "rm" in arguments:
            assert arguments[-1] == identity
            if mode == "timeout":
                import subprocess
                raise subprocess.TimeoutExpired(arguments, 15)
            return type("Result", (), {"returncode": 1})()
        return type("Result", (), {"returncode": 0, "stdout": identity.encode()})()
    monkeypatch.setattr(module.subprocess, "run", run)
    assert provider._remove_container(name) is False
    assert calls


def test_container_cleanup_confirms_absence_and_rejects_different_identity(tmp_path, monkeypatch):
    from paper_factory.autonomous import provider as module
    provider = fake_codex(tmp_path)
    name = "paper-factory-codex-" + "a" * 16
    monkeypatch.setattr(module.shutil, "which", lambda *args: "/trusted/docker")
    def absent(arguments, **kwargs):
        return type("Result", (), {"returncode": 1 if "inspect" in arguments else 0, "stdout": b""})()
    monkeypatch.setattr(module.subprocess, "run", absent)
    assert provider._remove_container(name) is True
    def mismatch(arguments, **kwargs):
        assert "rm" not in arguments
        return type("Result", (), {"returncode": 0, "stdout": f"{'b' * 64} /{name}".encode()})()
    monkeypatch.setattr(module.subprocess, "run", mismatch)
    assert provider._remove_container(name, "c" * 64) is False


def test_unconfirmed_cleanup_blocks_output_and_preserves_recovery_handle(tmp_path, monkeypatch):
    provider = fake_codex(tmp_path)
    monkeypatch.setattr(provider, "_remove_container", lambda name: False)
    call = tmp_path / "call"
    with pytest.raises(ProviderBlocked) as raised:
        provider.generate("Produce answer", SCHEMA, call)
    assert raised.value.code == "CLEANUP_UNCONFIRMED"
    receipt = json.loads((call / "receipt.json").read_text())
    assert receipt["cleanup_confirmed"] is False and receipt["code"] == "CLEANUP_UNCONFIRMED"
    assert (call / "runtime-handle.json").is_file()
    assert not (call / "output.json").exists()


def test_public_cleanup_rejects_foreign_name_and_reused_pid_is_not_signaled(tmp_path, monkeypatch):
    from paper_factory.autonomous import provider as module
    provider = fake_codex(tmp_path)
    monkeypatch.setattr(module.os, "killpg", lambda *args: pytest.fail("Unrelated process must not be signaled"))
    handle = {"kind": "codex", "pid": 12345, "pgid": 12345, "start_ticks": 10}
    assert provider.cleanup_handle({**handle, "container_name": "foreign-container"}) is False
    monkeypatch.setattr(module, "_start_ticks", lambda pid: 11)
    assert provider.cleanup_handle(handle) is True


def test_exponent_overflow_is_rejected_as_nonfinite_json_number(tmp_path):
    schema = {"type": "object", "properties": {"answer": {"type": "number"}}, "required": ["answer"], "additionalProperties": False}
    call = tmp_path / "call"
    with pytest.raises(ProviderBlocked) as raised:
        fake_codex(tmp_path, output='{"answer":1e999}').generate("Produce number", schema, call)
    assert raised.value.code == "SCHEMA_ERROR"
    assert not (call / "model-output.json").exists()


def test_actual_research_plan_contract_is_supported_without_changing_caller_api(tmp_path):
    from paper_factory.autonomous.models import ResearchPlan
    plan = ResearchPlan(feasible=True, reason="Repository behavior can be measured directly.", title="Measured repository behavior",
        question="How does the production implementation compare with a reference?", runtime="python", source_files=["module.py"],
        production_entrypoint="module.py", dependencies=[], conditions=["reference", "production"],
        metrics=[{"name": "duration", "description": "Measured elapsed runtime per independent sample.", "unit": "ms"}],
        comparator="Use a preserved independent baseline implementation.", independent_oracle="Check each result against a simple reference implementation.",
        sampling_unit="One independently seeded fixture.", sample_size=3, seeds=[1, 2],
        parameters={"count": 3, "ratio": 0.5, "label": "fixture"},
        procedure=["Generate independent seeded inputs.", "Invoke both production and reference.", "Record paired observations."],
        analysis_method="Compare paired observations with a bootstrap confidence interval.",
        limitations=["Synthetic fixtures limit external validity.", "Measurements characterize this worker."], literature_queries=["paired software measurements"])
    original = plan.model_dump(mode="json")
    wire = {**original, "parameters": [{"key": key, "value": value} for key, value in original["parameters"].items()]}
    result = fake_codex(tmp_path, output=json.dumps(wire)).generate("Prepare a research plan", ResearchPlan.model_json_schema(), tmp_path / "call")
    assert result == original
    assert ResearchPlan.model_validate(result) == plan


@pytest.mark.parametrize("blank", ["", " \t "])
def test_auth_root_optional_setting_defaults_without_creating_directories(tmp_path, monkeypatch, blank):
    monkeypatch.setenv("PF_HOME", str(tmp_path / "application-data"))
    monkeypatch.setenv("PF_CODEX_AUTH_HOME", blank)
    assert auth_root() == tmp_path / "application-data/codex-auth"
    assert not auth_root().exists()
    explicit = tmp_path / "private-connections"
    monkeypatch.setenv("PF_CODEX_AUTH_HOME", str(explicit))
    assert auth_root() == explicit
    assert resolve_auth_home() is None


def test_active_profile_uses_only_owned_nonsecret_metadata(tmp_path, monkeypatch):
    root = tmp_path / "connections"
    home = connected_profile(root)
    original = Path.read_text
    def guarded(path, *args, **kwargs):
        assert path.name != "auth.json", "Provider must not inspect authentication files"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", guarded)
    assert resolve_auth_home() == home
    assert resolve_auth_home(root) == home


def test_connected_profile_reaches_cli_without_mutating_supplied_auth_home(tmp_path, monkeypatch):
    root = tmp_path / "connections"
    home = connected_profile(root)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "existing-managed-home"))
    provider = fake_codex(tmp_path)
    call = tmp_path / "call"
    assert provider.generate("Produce answer", SCHEMA, call) == {"answer": 42}
    observed = json.loads((call / "observed.json").read_text())
    assert observed["codex_home"] == str(home)
    assert os.environ["CODEX_HOME"] == str(tmp_path / "existing-managed-home")
    assert str(home) not in json.dumps(provider.status())
    assert str(home) not in (call / "receipt.json").read_text()


def test_explicit_profile_probe_bypasses_active_selection_and_never_implies_generation_success(tmp_path, monkeypatch):
    root = tmp_path / "connections"
    connected_profile(root)
    pending = connected_profile(root, "b" * 32, active=False)
    provider = fake_codex(tmp_path, diagnostic="401 unauthorized", code=1)
    provider = CodexProvider(provider.configured_executable, auth_home=pending)
    assert provider.status()["ready"] is True
    call = tmp_path / "probe"
    with pytest.raises(ProviderBlocked) as raised:
        provider.generate("Probe structured response", SCHEMA, call)
    assert raised.value.code == "AUTH_REQUIRED"
    assert json.loads((call / "observed.json").read_text())["codex_home"] == str(pending)
    assert json.loads((call / "receipt.json").read_text())["status"] == "blocked"
    assert resolve_auth_home() == root / "profiles" / ("a" * 32)


def test_profile_is_pinned_across_status_and_generation_when_connection_changes(tmp_path, monkeypatch):
    root = tmp_path / "connections"
    first = connected_profile(root)
    second = connected_profile(root, "b" * 32, active=False)
    provider = fake_codex(tmp_path)
    original_status = provider._status
    def changing_status(environment):
        result = original_status(environment)
        pointer = root / "active.json"
        pointer.write_text(json.dumps({"version": 1, "profile": "profiles/" + second.name, "verified": True}))
        return result
    monkeypatch.setattr(provider, "_status", changing_status)
    call = tmp_path / "call"
    provider.generate("Produce answer", SCHEMA, call)
    assert json.loads((call / "observed.json").read_text())["codex_home"] == str(first)
    assert resolve_auth_home() == second


@pytest.mark.parametrize("selection", [{"version": 1, "profile": "../escape", "verified": True},
    {"version": 1, "profile": "profiles/" + "a" * 32, "verified": False},
    {"version": True, "profile": "profiles/" + "a" * 32, "verified": True},
    {"version": 1, "profile": "profiles/" + "a" * 32, "verified": True, "unexpected": "secret-content"},
    {"version": 1, "profile": "profiles/" + "a" * 32, "verified": True, "verified_at": "2026-10-01T12:00:00"}])
def test_malformed_active_selection_fails_closed_without_private_diagnostics(tmp_path, selection):
    root = tmp_path / "connections"
    connected_profile(root)
    (root / "active.json").write_text(json.dumps(selection))
    with pytest.raises(ProviderBlocked) as raised:
        resolve_auth_home()
    assert raised.value.code == "CONFIGURATION_ERROR"
    assert "secret-content" not in str(raised.value)
    provider = fake_codex(tmp_path)
    assert provider.status()["code"] == "CONFIGURATION_ERROR"
    call = tmp_path / "call"
    with pytest.raises(ProviderBlocked) as raised:
        provider.generate("Produce answer", SCHEMA, call)
    assert raised.value.code == "CONFIGURATION_ERROR"
    assert not (call / "observed.json").exists()


@pytest.mark.parametrize("unsafe", ["root_permissions", "profile_permissions", "pointer_permissions", "pointer_symlink", "profile_symlink", "git_ancestor"])
def test_connection_paths_require_private_unlinked_directories_outside_git(tmp_path, unsafe):
    root = tmp_path / "connections"
    home = connected_profile(root)
    if unsafe == "root_permissions":
        root.chmod(0o755)
    elif unsafe == "profile_permissions":
        home.chmod(0o755)
    elif unsafe == "pointer_permissions":
        (root / "active.json").chmod(0o644)
    elif unsafe == "pointer_symlink":
        pointer = root / "active.json"
        original = root / "previous.json"
        pointer.rename(original)
        pointer.symlink_to(original)
    elif unsafe == "profile_symlink":
        home.rmdir()
        outside = tmp_path / "outside"
        outside.mkdir(mode=0o700)
        home.symlink_to(outside, target_is_directory=True)
    elif unsafe == "git_ancestor":
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git/HEAD").write_text("ref: refs/heads/main\n")
    with pytest.raises(ProviderBlocked) as raised:
        resolve_auth_home(root)
    assert raised.value.code == "CONFIGURATION_ERROR"


def test_explicit_profile_requires_private_directory(tmp_path):
    home = tmp_path / "unsafe-profile"
    home.mkdir(mode=0o755)
    home.chmod(0o755)
    provider = fake_codex(tmp_path)
    explicit = CodexProvider(provider.configured_executable, auth_home=home)
    assert explicit.status()["code"] == "CONFIGURATION_ERROR"
    with pytest.raises(ProviderBlocked) as raised:
        explicit.generate("Produce answer", SCHEMA, tmp_path / "call")
    assert raised.value.code == "CONFIGURATION_ERROR"


def test_selected_profile_is_same_home_mounted_into_isolated_runtime(tmp_path, monkeypatch):
    from paper_factory.autonomous import provider as module
    root = tmp_path / "connections"
    home = connected_profile(root)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "original-home"))
    provider = fake_codex(tmp_path)
    call = tmp_path / "call"
    (call / "runtime").mkdir(parents=True)
    original_which = module.shutil.which
    monkeypatch.setattr(module.shutil, "which", lambda value: "/trusted/docker" if value == "docker" else original_which(value))
    inspection = type("Inspection", (), {"returncode": 0, "stdout": ("sha256:" + "a" * 64).encode()})()
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: inspection)
    command = [str(tmp_path / "codex-fake"), "exec", "-C", "/empty", "-"]
    arguments, name, image = provider._container_command(command, call)
    assert f"type=bind,src={home},dst={home},readonly" in arguments
    assert all("original-home" not in argument for argument in arguments)
    assert os.environ["CODEX_HOME"].endswith("original-home")


def test_selection_pointer_must_be_regular_file_without_blocking_fifo(tmp_path):
    if not hasattr(os, "mkfifo"):
        pytest.skip("Named pipes are not supported on this platform")
    root = tmp_path / "connections"
    connected_profile(root)
    (root / "active.json").unlink()
    os.mkfifo(root / "active.json", 0o600)
    began = time.monotonic()
    with pytest.raises(ProviderBlocked) as raised:
        resolve_auth_home()
    assert raised.value.code == "CONFIGURATION_ERROR"
    assert time.monotonic() - began < 1


def test_long_non_url_log_line_does_not_stall_redaction_supervision():
    from paper_factory.autonomous.provider import _redact
    diagnostic = "x" * MAX_LOG_BYTES
    began = time.monotonic()
    assert _redact(diagnostic, []) == diagnostic
    assert time.monotonic() - began < 2

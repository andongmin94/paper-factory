"""Independent boundary tests: untrusted JavaScript runs only inside Wasm."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import time
from types import SimpleNamespace
import zipfile

import pytest

from paper_factory.autonomous import quickjs_runner as module
from paper_factory.autonomous.quickjs_runner import QuickJSRunner


RUNTIME_ASSETS = Path(__file__).resolve().parents[1] / "desktop/runtime-inputs/assets"
SOURCE = "module.exports = {calculate(x) { return x + 1; }};\n"


def experiment(body: str) -> str:
    return "export default function run() {\n" + body + "\n}\n"


def test_shutdown_reconciles_a_retained_worker_journal_before_releasing_ownership(tmp_path, monkeypatch):
    supervisor = tmp_path / "synthetic-supervisor"
    supervisor.mkdir()
    handle = {"kind": "quickjs-worker", "pid": 123, "owner_nonce": "a" * 32}
    journal = supervisor / "owned-workers.json"
    journal.write_text(json.dumps({"format": "paper-factory-quickjs-supervisor-v1", "workers": [
        {"phase": "unresolved", "purpose": "experiment", "handle": handle}]}), encoding="utf-8")
    candidate = QuickJSRunner(tmp_path / "unused-runtime", supervisor_root=supervisor)
    calls = []
    monkeypatch.setattr(candidate, "stop", lambda value: calls.append(value) or False)
    with pytest.raises(ValueError, match="cleanup remains unconfirmed"):
        candidate.close(deadline=time.monotonic() + 30)
    assert calls == [handle] and candidate._lease is not None and len(candidate._records) == 1
    retained = journal.read_bytes()
    with pytest.raises(ValueError, match="shutdown deadline"):
        candidate.close(deadline=time.monotonic() + 0.1)
    assert calls == [handle] and journal.read_bytes() == retained
    monkeypatch.setattr(candidate, "stop", lambda value: calls.append(value) or True)
    candidate.close(deadline=time.monotonic() + 30)
    assert calls == [handle, handle] and candidate._lease is None and not candidate._records
    assert json.loads(journal.read_bytes())["workers"] == []


def test_shutdown_worker_cleanup_does_not_reset_the_shared_deadline(tmp_path, monkeypatch):
    supervisor = tmp_path / "synthetic-supervisor"
    supervisor.mkdir()
    handles = [{"kind": "quickjs-worker", "pid": 123 + index, "owner_nonce": letter * 32}
               for index, letter in enumerate(("a", "b"))]
    journal = supervisor / "owned-workers.json"
    journal.write_text(json.dumps({"format": "paper-factory-quickjs-supervisor-v1", "workers": [
        {"phase": "unresolved", "purpose": "experiment", "handle": handle} for handle in handles]}), encoding="utf-8")
    candidate = QuickJSRunner(tmp_path / "unused-runtime", supervisor_root=supervisor)
    elapsed, calls = [0], []

    def stopped(handle):
        calls.append(handle)
        elapsed[0] += 21
        return True

    monkeypatch.setattr(candidate, "stop", stopped)
    with monkeypatch.context() as clock_patch:
        clock_patch.setattr(module, "time", SimpleNamespace(monotonic=lambda: elapsed[0]))
        with pytest.raises(ValueError, match="shutdown deadline"):
            candidate.close(deadline=30)
    assert calls == handles[:1] and list(candidate._records) == [handles[1]["owner_nonce"]]
    assert json.loads(journal.read_bytes())["workers"][0]["handle"] == handles[1]
    candidate.close(deadline=time.monotonic() + 30)
    assert calls == handles and not candidate._records and candidate._lease is None


def envelope(value: str = "value", *, fixtures: str = "[JSON.parse(retainFixture('input', '[41]'))]") -> str:
    return """return {
        observations: [{unit_id: 'unit', seed: 11, condition: 'production', metric: 'value', value: VALUE}],
        controls: [{name: 'positive result', passed: Number.isFinite(VALUE), details: 'trusted test fixture'},
                   {name: 'negative mismatch', passed: VALUE !== VALUE + 1, details: 'trusted test fixture'}],
        fixtures: FIXTURES
    };""".replace("VALUE", value).replace("FIXTURES", fixtures)


@pytest.fixture(scope="module")
def pinned_runtime(tmp_path_factory):
    archive_path = RUNTIME_ASSETS / "quickjs-runtime.zip"
    metadata_path = RUNTIME_ASSETS / "quickjs-runtime.json"
    assert archive_path.is_file() and metadata_path.is_file(), "Required bundled QuickJS test assets are missing"
    metadata = json.loads(metadata_path.read_bytes())
    assert metadata["root_directory"] == "quickjs-runtime"
    assert metadata["inventory_sha256"] == module.INVENTORY_SHA256
    assert archive_path.stat().st_size == metadata["archive_size"] <= 2 * 1024 * 1024
    raw = archive_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == metadata["archive_sha256"]
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        names = {item.filename for item in entries}
        assert len(entries) == len({name.casefold() for name in names}) == metadata["entries"] == 53
        assert sum(item.file_size for item in entries) <= 2 * 1024 * 1024
        assert archive.testzip() is None
        for item in entries:
            name = item.filename
            assert not item.is_dir() and not stat.S_ISLNK(item.external_attr >> 16)
            assert not PurePosixPath(name).is_absolute() and "\\" not in name and ":" not in name
            assert all(part not in {"", ".", ".."} for part in name.split("/"))
            assert name in {"quickjs-runtime/package.json", "quickjs-runtime/package-lock.json",
                            "quickjs-runtime/inventory.json"} or name.startswith("quickjs-runtime/node_modules/")
        inventory_raw = archive.read("quickjs-runtime/inventory.json")
        assert hashlib.sha256(inventory_raw).hexdigest() == module.INVENTORY_SHA256
        records = json.loads(inventory_raw)["files"]
        assert names == {"quickjs-runtime/inventory.json", *("quickjs-runtime/" + name for name in records)}
        for name, record in records.items():
            content = archive.read("quickjs-runtime/" + name)
            assert len(content) == record["size"] and hashlib.sha256(content).hexdigest() == record["sha256"]
        scratch = tmp_path_factory.mktemp("verified-quickjs").resolve()
        for item in entries:
            target = scratch.joinpath(*PurePosixPath(item.filename).parts).resolve()
            assert target.is_relative_to(scratch)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(archive.read(item.filename))
    node = shutil.which(os.environ.get("PF_NODE_BIN") or "node")
    if not node:
        pytest.skip("Trusted Node is unavailable; bundled assets were verified and no native-code fallback is used")
    version = subprocess.run([node, "--version"], capture_output=True, timeout=5, check=False)
    if version.returncode or not re.fullmatch(rb"v(?:22|24)\.[0-9]+\.[0-9]+", version.stdout.strip()):
        pytest.skip("Tests require Node 22 or 24; the runner applies the explicit host-profile gate")
    return scratch / "quickjs-runtime"


@pytest.fixture
def supervisor_root(tmp_path):
    return tmp_path / "supervisor"


@pytest.fixture
def runner(pinned_runtime, supervisor_root, request):
    value = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root,
                          host_profile=getattr(request, "param", "private"))
    snapshot = value.status()
    assert snapshot["ready"], snapshot
    return value


@pytest.fixture
def inputs(tmp_path):
    source, bundle, output = (tmp_path / name for name in ("source", "bundle", "output"))
    source.mkdir()
    bundle.mkdir()
    (source / "source.js").write_bytes(SOURCE.encode("utf-8"))
    return source, bundle, output


def run(runner, inputs, code: str, **options):
    (inputs[1] / "experiment.mjs").write_text(code, encoding="utf-8")
    return runner.run(*inputs, runtime="quickjs", entrypoint="experiment.mjs",
                      production_entrypoint="source.js:calculate", **options)


def observed(result):
    assert result["status"] == "succeeded", result
    assert result["cleanup_confirmed"] is True
    return json.loads(Path(result["output_path"]).read_text(encoding="utf-8"))


def manifest(inputs):
    return json.loads((inputs[2] / "runtime-manifest.json").read_text(encoding="utf-8"))


def failed_observed(result):
    assert result["status"] == "failed", result
    assert result["cleanup_confirmed"] is True
    assert result["output_path"] is not None, result
    raw = Path(result["output_path"]).read_bytes()
    assert len(raw) <= module.MAX_ARTIFACT_BYTES
    assert result["artifacts"][0]["size"] == len(raw)
    assert result["artifacts"][0]["sha256"] == hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


@pytest.mark.parametrize("runner", ["private", "provided"], indirect=True)
def test_smallest_real_guest_calls_original_and_retains_unicode(runner, inputs):
    text = "실제 UTF-8 관측값: 가🙂\\n"
    code = experiment("const value = JSON.parse(callProduction('[41]'));\n"
                      + "const fixture = JSON.parse(retainFixture('원자료', " + json.dumps(text, ensure_ascii=False) + "));\n"
                      + envelope(fixtures="[fixture]"))
    result = run(runner, inputs, code)
    payload = observed(result)
    assert payload["observations"][0]["value"] == 42
    fixture = payload["fixtures"][0]
    raw = base64.b64decode(fixture["content"], validate=True)
    assert raw == text.encode("utf-8")
    assert fixture == {"label": "원자료", "encoding": "base64", "content": base64.b64encode(raw).decode(),
                       "sha256": hashlib.sha256(raw).hexdigest()}
    assert result["production_calls"] == [{"path": "source.js", "function": "calculate", "calls": 1}]


@pytest.mark.parametrize("runner", ["private", "provided"], indirect=True)
def test_original_guest_state_and_callable_are_separate_and_read_only(runner, inputs):
    (inputs[0] / "source.js").write_text(
        "globalThis.originalState = 17; module.exports = {calculate(x) { return x + originalState; }};",
        encoding="utf-8")
    code = experiment("""
        globalThis.originalState = 999;
        globalThis.module = {exports: {calculate() {return -100;}}};
        const originalGate = callProduction;
        try { globalThis.callProduction = () => '-100'; } catch {}
        for (const name of ['callProduction', 'retainFixture']) {
            const gate = Object.getOwnPropertyDescriptor(globalThis, name);
            if (gate.writable || gate.configurable) throw Error('mutable gate');
        }
        if (callProduction !== originalGate) throw Error('replaced gate');
        const value = JSON.parse(callProduction('[25]'));
        """ + envelope())
    assert observed(run(runner, inputs, code))["observations"][0]["value"] == 42


@pytest.mark.parametrize("runner", ["private", "provided"], indirect=True)
def test_guest_has_no_ambient_process_filesystem_or_network(runner, inputs):
    code = experiment("""
        const names = ['process', 'require', 'fetch', 'XMLHttpRequest', 'WebSocket', 'Worker',
                       'WebAssembly', 'Deno', 'Bun'];
        let absent = names.every(name => typeof globalThis[name] === 'undefined');
        try { globalThis.constructor.constructor('return process')(); absent = false; } catch {}
        const value = absent ? JSON.parse(callProduction('[41]')) : -1;
        """ + envelope())
    assert observed(run(runner, inputs, code))["observations"][0]["value"] == 42


@pytest.mark.parametrize("runtime", ["python", "node", "bash"])
def test_unsupported_runtime_never_executes_on_host(runner, inputs, monkeypatch, runtime):
    (inputs[1] / "experiment.mjs").write_text(experiment("const value = 42;" + envelope()), encoding="utf-8")
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_k: pytest.fail("No untrusted native execution"))
    with pytest.raises(ValueError):
        runner.run(*inputs, runtime=runtime, entrypoint="experiment.mjs", production_entrypoint="source.js:calculate")


@pytest.mark.parametrize("entrypoint", ["../experiment.mjs", "/experiment.mjs", "missing.mjs", "experiment\\.mjs"])
def test_unsafe_bundle_entrypoint_fails_before_child(runner, inputs, monkeypatch, entrypoint):
    (inputs[1] / "experiment.mjs").write_text(experiment("const value = 42;" + envelope()), encoding="utf-8")
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_k: pytest.fail("Unsafe input must not spawn"))
    with pytest.raises(ValueError):
        runner.run(*inputs, runtime="quickjs", entrypoint=entrypoint, production_entrypoint="source.js:calculate")


@pytest.mark.parametrize("selector", ["../source.js:calculate", "/source.js:calculate", "source.js:../calculate",
                                     "source.js:calculate()", "missing.js:calculate"])
def test_unsafe_production_selector_fails_before_child(runner, inputs, monkeypatch, selector):
    (inputs[1] / "experiment.mjs").write_text(experiment("const value = 42;" + envelope()), encoding="utf-8")
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_k: pytest.fail("Unsafe selector must not spawn"))
    with pytest.raises(ValueError):
        runner.run(*inputs, runtime="quickjs", entrypoint="experiment.mjs", production_entrypoint=selector)


def test_inherited_export_is_not_attributed_to_production(runner, inputs):
    (inputs[1] / "experiment.mjs").write_text(experiment("const value = JSON.parse(callProduction('[41]'));" + envelope()), encoding="utf-8")
    result = runner.run(*inputs, runtime="quickjs", entrypoint="experiment.mjs", production_entrypoint="source.js:constructor")
    assert result["status"] == "failed", result
    assert result["cleanup_confirmed"] is True
    assert result["production_calls"] == []


def test_tampered_wasm_bundle_is_not_ready_and_never_starts(pinned_runtime, tmp_path, inputs, monkeypatch, supervisor_root):
    copied = tmp_path / "tampered-runtime"
    shutil.copytree(pinned_runtime, copied)
    wasm = copied / "node_modules/@jitl/quickjs-wasmfile-release-sync/dist/emscripten-module.wasm"
    original = wasm.read_bytes()
    wasm.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    candidate = QuickJSRunner(copied, supervisor_root=supervisor_root)
    assert candidate.status()["ready"] is False
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_k: pytest.fail("Tampered runtime must not start"))
    result = run(candidate, inputs, experiment("const value = 42;" + envelope()))
    assert result["status"] != "succeeded"
    assert result["artifacts"] == []


def test_unsupported_node_version_is_not_ready(pinned_runtime, monkeypatch, supervisor_root):
    actual = module.subprocess.run

    def version_only(arguments, **kwargs):
        if "--version" in arguments:
            return subprocess.CompletedProcess(arguments, 0, b"v18.20.0\n", b"")
        return actual(arguments, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", version_only)
    assert QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root).status()["ready"] is False


@pytest.mark.parametrize("profile,version,accepted", [
    ("private", "v24.21.0", True), ("private", "v22.16.0", False),
    ("provided", "v22.16.0", True), ("provided", "v22.22.0", True),
    ("provided", "v24.21.0", True), ("provided", "v22.15.1", False),
    ("provided", "v20.20.0", False), ("provided", "v23.11.0", False),
    ("provided", "v25.0.0", False), ("provided", "22.16.0", False),
])
def test_node_profile_version_gate_is_explicit(pinned_runtime, monkeypatch, supervisor_root, profile, version, accepted):
    """Version simulation only; it never certifies an actual Node 22 guest."""
    monkeypatch.setattr(module.subprocess, "run", lambda arguments, **kwargs:
                        subprocess.CompletedProcess(arguments, 0, (version + "\n").encode(), b""))
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root, host_profile=profile)
    if accepted:
        _node, metadata = candidate._runtime()
        assert metadata["node_version"] == version and metadata["host_profile"] == profile
    else:
        with pytest.raises(ValueError, match="Private hosts require"):
            candidate._runtime()


@pytest.mark.parametrize("profile", ["", "auto", "node22", None, []])
def test_unknown_host_profile_fails_before_creating_scratch(pinned_runtime, supervisor_root, profile):
    with pytest.raises(ValueError, match="host profile"):
        QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root, host_profile=profile)
    assert not supervisor_root.exists()


def test_provided_profile_retains_actual_local_parser_guest_and_cleanup_receipts(pinned_runtime, supervisor_root, inputs):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root, host_profile="provided")
    try:
        readiness = candidate.status()
        assert readiness["ready"] and readiness["cleanup_confirmed"]
        assert readiness["host_profile"] == "provided" and readiness["typescript_parser_self_check"] is True
        actual_version = subprocess.run([shutil.which(os.environ.get("PF_NODE_BIN") or "node"), "--version"],
                                        capture_output=True, check=True).stdout.decode().strip()
        assert readiness["versions"]["node"] == actual_version
        result = run(candidate, inputs, experiment("const value=JSON.parse(callProduction('[41]'));" + envelope()))
        assert observed(result)["observations"][0]["value"] == 42
        assert result["production_calls"] == [{"path": "source.js", "function": "calculate", "calls": 1}]
        assert manifest(inputs)["host_profile"] == "provided"
        assert manifest(inputs)["node_version"] == actual_version
        assert candidate._active == {} and candidate._records == {}
    finally:
        candidate.close()


@pytest.mark.parametrize("module_name", ["check.ts", "delta.ts"])
@pytest.mark.parametrize("defect", ["parser-unavailable", "wrong-compiled-hash", "wrong-transformer-version",
                                   "missing-transformation-options", "missing-source-url", "wrong-source-url",
                                   "wrong-mode", "wrong-source-map", "unexpected-option", "missing-options-scope"])
def test_type_parser_readiness_failure_cannot_be_bypassed(pinned_runtime, supervisor_root, monkeypatch, defect, module_name):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root, host_profile="provided")
    actual = candidate._execute
    calls = []

    def parser_failure(node, packet, **kwargs):
        calls.append(packet["production_entrypoint"])
        if packet["production_entrypoint"] == "check.ts:calculate" and defect == "parser-unavailable":
            return {"exit_code": 1, "cleanup_confirmed": True, "reason": "worker-failed", "envelope": {}}
        receipt = actual(node, packet, **kwargs)
        if packet["production_entrypoint"] == "check.ts:calculate":
            runtime = receipt["envelope"]["runtime_manifest"]
            compiled = runtime["compiled_files"][module_name]
            if defect == "wrong-compiled-hash":
                compiled["compiled_sha256"] = compiled["original_sha256"]
            elif defect == "wrong-transformer-version":
                runtime["transformer"]["version"] = "v0.0.0"
            elif defect == "missing-transformation-options":
                compiled.pop("transformation_options")
            elif defect == "missing-source-url":
                compiled["transformation_options"].pop("sourceUrl")
            elif defect == "wrong-source-url":
                compiled["transformation_options"]["sourceUrl"] = "source/unrecorded.ts"
            elif defect == "wrong-mode":
                compiled["transformation_options"]["mode"] = "transform"
            elif defect == "wrong-source-map":
                compiled["transformation_options"]["sourceMap"] = True
            elif defect == "unexpected-option":
                compiled["transformation_options"]["unrecorded"] = True
            elif defect == "missing-options-scope":
                runtime["transformer"].pop("options_scope")
        return receipt

    monkeypatch.setattr(candidate, "_execute", parser_failure)
    readiness = candidate.status()
    assert readiness["ready"] is False and readiness["typescript_parser_self_check"] is False
    assert readiness["cleanup_confirmed"] is True
    assert calls == ["check.cjs:calculate", "check.ts:calculate"]
    candidate.close()


@pytest.mark.parametrize("argument", [
    "'not-json'", "'{}'", "{}", "JSON.stringify(new Array(17).fill(1))",
    "JSON.stringify(['가'.repeat(350000)])",
    "JSON.stringify([Array.from({length: 70}).reduce(value => [value], 0)])",
])
def test_invalid_gate_inputs_are_rejected_without_original_dispatch(runner, inputs, argument):
    code = experiment("let denied = false; try { callProduction(" + argument + "); } catch { denied = true; }\n"
                      "if (!denied) throw Error('Invalid gate input accepted');\n"
                      "const value = 0;\n" + envelope())
    result = run(runner, inputs, code)
    assert failed_observed(result)["observations"][0]["value"] == 0
    assert result["production_calls"] == []


def test_guest_receipt_fields_do_not_replace_controller_evidence(runner, inputs):
    payload = envelope().replace("fixtures:", """production_calls: [{path: 'source.js', function: 'calculate', calls: 999}],
        cleanup_confirmed: true, runtime_manifest: {source_files: {}}, fixtures:""")
    result = run(runner, inputs, experiment("const value = JSON.parse(callProduction('[41]'));\n" + payload))
    observed(result)
    assert result["production_calls"] == [{"path": "source.js", "function": "calculate", "calls": 1}]
    assert manifest(inputs)["source_files"]["source.js"]["original_sha256"] == hashlib.sha256(SOURCE.encode()).hexdigest()


def test_original_exceptions_count_and_exhaust_dispatch_budget(runner, inputs):
    (inputs[0] / "source.js").write_text("module.exports = {calculate() { throw Error('original fault'); }};", encoding="utf-8")
    code = experiment("""
        let originalFailures = 0, budgetFailures = 0;
        for (let i = 0; i < 65538; i++) {
            try { callProduction('[]'); } catch (error) {
                if (error.message.includes('budget')) budgetFailures++;
                else if (error.message.includes('original fault')) originalFailures++;
                else throw error;
            }
        }
        if (originalFailures !== 65536) throw Error('Incorrect original fault count');
        const value = budgetFailures;
        """ + envelope())
    result = run(runner, inputs, code, timeout_seconds=60)
    assert failed_observed(result)["observations"][0]["value"] == 2
    assert "budget" in result["stderr"].lower(), result
    assert result["production_calls"] == [{"path": "source.js", "function": "calculate", "calls": 65536}]
    assert manifest(inputs)["production_dispatch_attempts"] == 65536
    assert manifest(inputs)["production_completed_calls"] == 0


@pytest.mark.parametrize("runner", ["private", "provided"], indirect=True)
def test_actual_original_rejections_are_measured_invocations(runner, inputs):
    (inputs[0] / "source.js").write_text(
        "module.exports = {calculate(x) { if (x === null) throw Error('actual rejection'); return x + 1; }};",
        encoding="utf-8")
    code = experiment("""
        let rejections = 0;
        for (let i = 0; i < 3; i++) {
            try { callProduction('[null]'); } catch (error) {
                if (!error.message.includes('actual rejection')) throw error;
                rejections++;
            }
        }
        if (rejections !== 3) throw Error('Original rejection missing');
        const value = JSON.parse(callProduction('[41]'));
        """ + envelope())
    result = run(runner, inputs, code)
    assert observed(result)["observations"][0]["value"] == 42
    assert result["production_calls"] == [{"path": "source.js", "function": "calculate", "calls": 4}]
    assert manifest(inputs)["production_dispatch_attempts"] == 4
    assert manifest(inputs)["production_completed_calls"] == 1


@pytest.mark.parametrize("specifier", ["node:fs", "node:child_process", "https://example.com/guest.mjs", "../source/source.js"])
@pytest.mark.parametrize("runner", ["private", "provided"], indirect=True)
def test_imports_outside_frozen_guest_map_are_rejected(runner, inputs, specifier):
    code = "import * as escaped from " + json.dumps(specifier) + ";\n" + experiment("const value = 42;" + envelope())
    result = run(runner, inputs, code)
    assert result["status"] == "failed", result
    assert result["cleanup_confirmed"] is True
    assert result["artifacts"] == []


@pytest.mark.parametrize("runner", ["private", "provided"], indirect=True)
def test_frozen_relative_experiment_import_is_supported(runner, inputs):
    (inputs[1] / "helper.mjs").write_text("export const input = 41;", encoding="utf-8")
    code = "import {input} from './helper.mjs';\n" + experiment(
        "const value = JSON.parse(callProduction(JSON.stringify([input])));\n" + envelope())
    result = run(runner, inputs, code)
    assert observed(result)["observations"][0]["value"] == 42
    assert "experiment/helper.mjs" in manifest(inputs)["imports"]


def test_retained_fixture_total_is_limited_to_eight_mib(runner, inputs):
    code = experiment("""
        const small = JSON.parse(retainFixture('empty', ''));
        const piece = 'x'.repeat(1024 * 1024);
        for (let i = 0; i < 8; i++) retainFixture('piece_' + i, piece);
        let denied = false;
        try { retainFixture('overflow', 'x'); } catch (error) {
            if (!error.message.includes('boundary')) throw error;
            denied = true;
        }
        if (!denied) throw Error('Retention total exceeded eight MiB');
        const value = JSON.parse(callProduction('[41]'));
        """ + envelope(fixtures="[small]"))
    result = run(runner, inputs, code)
    assert failed_observed(result)["observations"][0]["value"] == 42
    assert "retention boundary" in result["stderr"].lower(), result


def test_eight_mib_total_fixture_bytes_are_supported(runner, inputs):
    code = experiment("""
        const small = JSON.parse(retainFixture('empty', ''));
        const piece = 'x'.repeat(1024 * 1024);
        for (let i = 0; i < 8; i++) retainFixture('piece_' + i, piece);
        const value = JSON.parse(callProduction('[41]'));
        """ + envelope(fixtures="[small]"))
    result = run(runner, inputs, code)
    assert observed(result)["observations"][0]["value"] == 42
    assert manifest(inputs)["fixture_bytes"] == 8 * 1024 * 1024


def test_fixture_limit_counts_utf8_bytes_instead_of_characters(runner, inputs):
    code = experiment("""
        let denied = false;
        try { retainFixture('oversized_unicode', '가'.repeat(3 * 1024 * 1024)); }
        catch (error) {
            if (!error.message.includes('boundary')) throw error;
            denied = true;
        }
        if (!denied) throw Error('Unicode byte cap was ignored');
        const value = JSON.parse(callProduction('[41]'));
        """ + envelope())
    result = run(runner, inputs, code)
    assert failed_observed(result)["observations"][0]["value"] == 42


@pytest.mark.parametrize("label", ["''", "'x'.repeat(201)", "'bad\\u0000label'"])
def test_invalid_fixture_labels_are_rejected(runner, inputs, label):
    code = experiment("let denied=false; try { retainFixture(" + label + ", 'actual'); } catch { denied=true; }\n"
                      "const value=denied ? 1 : 0;\n" + envelope())
    result = run(runner, inputs, code)
    assert failed_observed(result)["observations"][0]["value"] == 1


def test_duplicate_fixture_labels_are_rejected(runner, inputs):
    code = experiment("""
        const fixture = JSON.parse(retainFixture('input', '[41]'));
        let denied = false;
        try { retainFixture('input', 'changed'); } catch { denied = true; }
        if (!denied) throw Error('Duplicate label was accepted');
        const value = JSON.parse(callProduction('[41]'));
        """ + envelope(fixtures="[fixture]"))
    result = run(runner, inputs, code)
    actual = failed_observed(result)
    assert actual["fixtures"][0]["sha256"] == hashlib.sha256(b"[41]").hexdigest()


@pytest.mark.parametrize("runner", ["private", "provided"], indirect=True)
def test_guest_out_of_memory_is_failed_with_confirmed_cleanup(runner, inputs):
    code = experiment("const blocks=[]; while (true) blocks.push(new Array(10000).fill('x'));\n" + envelope())
    result = run(runner, inputs, code, timeout_seconds=5)
    assert result["status"] == "failed", result
    assert result["cleanup_confirmed"] is True
    assert result["artifacts"] == []
    assert "memory" in result["stderr"].lower(), result


def test_oversized_return_is_never_exported(runner, inputs):
    result = run(runner, inputs, experiment("return {oversized: 'x'.repeat(9 * 1024 * 1024)};"), timeout_seconds=5)
    assert result["status"] == "failed", result
    assert result["cleanup_confirmed"] is True
    assert result["output_path"] is None
    assert result["artifacts"] == []
    assert len(result["stdout"].encode("utf-8")) <= 256 * 1024
    assert len(result["stderr"].encode("utf-8")) <= 256 * 1024


def test_async_experiment_is_rejected(runner, inputs):
    code = "export default async function run() { return {}; }"
    result = run(runner, inputs, code)
    assert result["status"] == "failed", result
    assert result["cleanup_confirmed"] is True
    assert "synchronous" in result["stderr"].lower(), result


@pytest.mark.parametrize("runner", ["private", "provided"], indirect=True)
def test_typescript_source_imports_have_compiler_and_original_hash_receipts(runner, inputs):
    source = "import {delta} from './helper.ts'; export function calculate(x: number): number { return x + delta; }\n"
    helper = "export const delta: number = 1;\n"
    (inputs[0] / "source.ts").write_bytes(source.encode("utf-8"))
    (inputs[0] / "helper.ts").write_bytes(helper.encode("utf-8"))
    (inputs[1] / "experiment.mjs").write_text(
        experiment("const value=JSON.parse(callProduction('[41]'));\n" + envelope()), encoding="utf-8")
    result = runner.run(*inputs, runtime="quickjs", entrypoint="experiment.mjs", production_entrypoint="source.ts:calculate")
    assert observed(result)["observations"][0]["value"] == 42
    receipt = manifest(inputs)
    assert receipt["transformer"]["native_typescript_execution"] is False
    assert receipt["native_node_execution"] is False
    assert receipt["transformer"]["name"] == "node:module.stripTypeScriptTypes"
    assert receipt["transformer"]["options"] == {"mode": "strip", "sourceMap": False}
    assert receipt["transformer"]["options_scope"] == "shared"
    for name, original in (("source.ts", source), ("helper.ts", helper)):
        digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
        assert receipt["source_files"][name]["original_sha256"] == digest
        assert receipt["compiled_files"][name]["original_sha256"] == digest
        assert receipt["compiled_files"][name]["compiled_sha256"] != digest
        assert receipt["compiled_files"][name]["transformation"] == "node:module.stripTypeScriptTypes"
        assert receipt["compiled_files"][name]["transformation_options"] == {
            "mode": "strip", "sourceMap": False, "sourceUrl": "source/" + name}
    assert "source/helper.ts" in receipt["imports"]
    assert result["production_calls"] == [{"path": "source.ts", "function": "calculate", "calls": 1}]


@pytest.mark.parametrize("runner", ["private", "provided"], indirect=True)
def test_guest_interrupt_deadline_confirms_owned_child_exit(runner, inputs):
    children = []

    def handle(value):
        children.append(runner._active[value["owner_nonce"]]["process"])

    started = time.monotonic()
    result = run(runner, inputs, experiment("while (true) {}"), timeout_seconds=1, on_handle=handle)
    assert result["status"] in {"failed", "timeout"}, result
    assert result["cleanup_confirmed"] is True
    assert result["artifacts"] == []
    assert 0.8 <= time.monotonic() - started < 10
    assert len(children) == 1 and children[0].poll() is not None
    assert runner._active == {}


@pytest.mark.parametrize("runner", ["private", "provided"], indirect=True)
def test_cancellation_confirms_owned_child_exit(runner, inputs):
    children, active_since = [], []

    def handle(value):
        children.append(runner._active[value["owner_nonce"]]["process"])
        active_since.append(time.monotonic())

    def cancelled():
        return bool(active_since) and time.monotonic() - active_since[0] > 0.15

    result = run(runner, inputs, experiment("while (true) {}"), timeout_seconds=10, cancel=cancelled, on_handle=handle)
    assert result["status"] == "cancelled", result
    assert result["cleanup_confirmed"] is True
    assert result["artifacts"] == []
    assert len(children) == 1 and children[0].poll() is not None
    assert runner._active == {}


def test_handle_callback_failure_cleans_child_without_publishing(runner, inputs):
    children = []

    def callback(value):
        children.append(runner._active[value["owner_nonce"]]["process"])
        raise RuntimeError("Synthetic durable handle callback failure")

    result = run(runner, inputs, experiment("const value=JSON.parse(callProduction('[41]'));\n" + envelope()), on_handle=callback)
    assert result["status"] == "failed", result
    assert result["cleanup_confirmed"] is True
    assert result["artifacts"] == []
    assert len(children) == 1 and children[0].poll() is not None
    assert runner._active == {}


@pytest.mark.parametrize("field,new_value", [("start_time", "999999"), ("boot_id", "new_boot"), ("owner_uid", 101)])
def test_stop_rejects_reused_or_unowned_pid_before_signalling(pinned_runtime, monkeypatch, field, new_value, supervisor_root):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    assert candidate._prepare() is True
    closed, opened, inspected = [], [], []
    actual_os, actual_path = module.os, module.Path
    class LinuxOs:
        name = "posix"
        def __getattr__(self, name):
            return getattr(actual_os, name)
        def getuid(self):
            return 100
        def pidfd_open(self, pid, flags):
            opened.append((pid, flags))
            return 77
        def close(self, descriptor):
            if descriptor == 77:
                closed.append(descriptor)
            else:
                actual_os.close(descriptor)
    monkeypatch.setattr(module, "os", LinuxOs())
    monkeypatch.setattr(module, "sys", SimpleNamespace(**{**vars(module.sys), "platform": "linux"}))
    monkeypatch.setattr(module, "signal", SimpleNamespace(SIGKILL=9, pidfd_send_signal=lambda *_a: pytest.fail("No reused PID signal")))
    namespace = {"pid_namespace": "pid:[4026533123]", "namespace_index": 1}
    monkeypatch.setattr(module, "_namespace", lambda: namespace)
    monkeypatch.setattr(module, "_pidfd_identity", lambda *_a: {**namespace, "proc_pid": 2887})
    boot = new_value if field == "boot_id" else "boot"
    monkeypatch.setattr(module, "Path", lambda path: SimpleNamespace(read_text=lambda **_k: boot)
                        if str(path) == "/proc/sys/kernel/random/boot_id" else actual_path(path))
    identity = {"start_time": "123456", "boot_id": "boot", "owner_uid": 100}
    actual = {**identity, field: new_value}
    monkeypatch.setattr(module, "_linux_identity", lambda pid: inspected.append(pid) or actual)
    handle = {"kind": "quickjs-worker", "pid": 6, "owner_nonce": "a" * 32, **identity, **namespace,
              "proc_pid": 2887, "node_path": str(actual_path(shutil.which(os.environ.get("PF_NODE_BIN") or "node")).resolve()),
              "worker_sha256": module._hash(module._read(module.WORKER, 128 * 1024))}
    candidate._records[handle["owner_nonce"]] = {"phase": "unresolved", "purpose": "experiment", "handle": handle}
    candidate._persist()
    assert candidate.stop(handle) is False
    assert opened == ([] if field == "boot_id" else [(6, 0)])
    assert inspected == ([] if field == "boot_id" else [2887])
    assert closed == ([] if field == "boot_id" else [77])
    assert candidate._records[handle["owner_nonce"]]["handle"] == handle
    candidate._release_lease()


def test_windows_recovery_never_terminates_an_unowned_pid(pinned_runtime, monkeypatch, supervisor_root):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    mock_windows_os(monkeypatch)
    assert candidate.stop({"kind": "quickjs-worker", "pid": 12345, "owner_nonce": "a" * 32}) is False
    assert candidate._lease is None and candidate._records == {}
    assert not candidate._journal_path.exists()


def test_active_handle_pid_mismatch_is_rejected(pinned_runtime, supervisor_root):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    candidate._active["a" * 32] = {"process": SimpleNamespace(pid=54321), "pidfd": None, "handle": {}}
    assert candidate.stop({"kind": "quickjs-worker", "pid": 12345, "owner_nonce": "a" * 32}) is False


class OwnedFakeProcess:
    """Trusted supervisor fixture; it neither launches nor evaluates JavaScript."""

    def __init__(self, stdout=b"{}"):
        self.pid = 12345
        self.stdin, self.stdout, self.stderr = io.BytesIO(), io.BytesIO(stdout), io.BytesIO()
        self.returncode = None

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("trusted fake supervisor", timeout)
        return self.returncode


def fake_windows_job(monkeypatch, child):
    """Mock only the native ownership API; transport/watchdogs remain real."""
    from paper_factory.autonomous import quickjs_windows
    monkeypatch.setattr(quickjs_windows, "create", lambda nonce: SimpleNamespace(
        name="Local\\paper-factory-codex-" + nonce,
        stop=lambda: child.kill() or True, close=lambda: None))
    monkeypatch.setattr(quickjs_windows, "attach", lambda job, process:
                        {"job_name": job.name, "start_ticks": 123})


def mock_windows_os(monkeypatch):
    actual_os = module.os
    class WindowsOs:
        name = "nt"
        def __getattr__(self, name):
            return getattr(actual_os, name)
    monkeypatch.setattr(module, "os", WindowsOs())
    monkeypatch.setattr(module, "sys", SimpleNamespace(**{**vars(module.sys), "platform": "win32"}))


def test_outer_wall_watchdog_rejects_a_frame_from_a_non_exiting_worker(pinned_runtime, monkeypatch, supervisor_root):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    child = OwnedFakeProcess(b'{"status":"succeeded","protocol":"paper-factory-quickjs-v1"}')
    fake_windows_job(monkeypatch, child)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_k: child)
    mock_windows_os(monkeypatch)
    ticks = iter([0, 5])
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: next(ticks, 5), sleep=lambda _seconds: None))
    receipt = candidate._execute(Path("trusted-node"), {"timeout_seconds": 1})
    assert receipt["reason"] == "timeout"
    assert receipt["envelope"] is None
    assert receipt["cleanup_confirmed"] is True
    assert child.poll() == -9
    assert candidate._active == {}


def test_supervisor_output_overflow_stops_owned_worker(pinned_runtime, monkeypatch, supervisor_root):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    child = OwnedFakeProcess(b"x" * (module.MAX_RESPONSE_BYTES + 1))
    fake_windows_job(monkeypatch, child)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_k: child)
    mock_windows_os(monkeypatch)
    receipt = candidate._execute(Path("trusted-node"), {"timeout_seconds": 1})
    assert receipt["reason"] == "overflow"
    assert receipt["envelope"] is None
    assert receipt["cleanup_confirmed"] is True
    assert child.poll() == -9


@pytest.mark.parametrize("exit_code", [1, -9, None])
def test_success_frame_with_unsuccessful_exit_never_exports(runner, inputs, monkeypatch, exit_code):
    monkeypatch.setattr(runner, "status", lambda: {"ready": True})
    monkeypatch.setattr(runner, "_runtime", lambda: (Path("trusted-node"), {}))
    monkeypatch.setattr(runner, "_execute", lambda *_a, **_k: {
        "exit_code": exit_code, "cleanup_confirmed": True, "active_handle": {}, "duration_seconds": 0,
        "reason": None, "envelope": {"protocol": "paper-factory-quickjs-v1", "status": "succeeded",
            "production_calls": [{"path": "source.js", "function": "calculate", "calls": 999}],
            "runtime_manifest": {"production_entrypoint": "source.js:calculate", "distinct_wasm_memories": True,
                                 "hard_linear_growth_denied": True},
            "observation_b64": base64.b64encode(b'{"fake":"success"}').decode()}})
    result = run(runner, inputs, experiment("return {};"))
    assert result["status"] == "failed"
    assert result["output_path"] is None
    assert result["artifacts"] == []


def test_unconfirmed_cleanup_keeps_owned_handle_and_blocks_publication(runner, inputs, monkeypatch):
    handle = {"kind": "quickjs-worker", "pid": 12345, "owner_nonce": "a" * 32}
    monkeypatch.setattr(runner, "status", lambda: {"ready": True})
    monkeypatch.setattr(runner, "_runtime", lambda: (Path("trusted-node"), {}))
    monkeypatch.setattr(runner, "_execute", lambda *_a, **_k: {
        "exit_code": None, "cleanup_confirmed": False, "active_handle": handle, "duration_seconds": 0,
        "reason": "cancelled", "envelope": None})
    result = run(runner, inputs, experiment("return {};"))
    assert result["status"] == "blocked"
    assert result["code"] == "CLEANUP_UNCONFIRMED"
    assert result["cleanup_confirmed"] is False
    assert result["active_handle"] == handle
    assert result["output_path"] is None
    assert result["artifacts"] == []


@pytest.mark.parametrize("runner", ["private", "provided"], indirect=True)
def test_caught_boundary_failure_retains_actual_failed_control_envelope(runner, inputs):
    payload = envelope(fixtures="[inputFixture, malformedFixture, outputFixture]").replace(
        "passed: value !== value + 1", "passed: !boundaryRejected")
    code = experiment("""
        const inputFixture = JSON.parse(retainFixture('input', '[41]'));
        const malformedFixture = JSON.parse(retainFixture('malformed', 'not-json'));
        const value = JSON.parse(callProduction('[41]'));
        const outputFixture = JSON.parse(retainFixture('output', JSON.stringify(value)));
        let boundaryRejected = false;
        try { callProduction('not-json'); } catch { boundaryRejected = true; }
        """ + payload)
    result = run(runner, inputs, code)
    assert result["status"] == "failed", result
    assert result["cleanup_confirmed"] is True
    assert result["exit_code"] != 0
    assert result["output_path"] is not None, result
    raw = Path(result["output_path"]).read_bytes()
    actual = json.loads(raw)
    assert actual["controls"][1]["passed"] is False
    assert actual["observations"][0]["value"] == 42
    assert result["production_calls"] == [{"path": "source.js", "function": "calculate", "calls": 1}]
    assert base64.b64decode(actual["fixtures"][1]["content"], validate=True) == b"not-json"
    assert actual["fixtures"][1]["sha256"] == hashlib.sha256(b"not-json").hexdigest()
    assert result["artifacts"][0]["sha256"] == hashlib.sha256(raw).hexdigest()


def test_failed_negative_control_is_retained_without_infrastructure_failure(runner, inputs):
    payload = envelope(fixtures="[inputFixture, outputFixture]").replace(
        "passed: value !== value + 1", "passed: unmutatedOutput !== value")
    code = experiment("""
        const inputFixture = JSON.parse(retainFixture('input', '[41]'));
        const value = JSON.parse(callProduction('[41]'));
        const unmutatedOutput = value;
        const outputFixture = JSON.parse(retainFixture('output', JSON.stringify(value)));
        """ + payload)
    result = run(runner, inputs, code)
    actual = observed(result)
    # Program completion is separate from scientific acceptance: the workflow
    # must see this actual false flag and make CONTROL_FAILED terminal.
    assert actual["controls"][1]["passed"] is False
    assert actual["observations"][0]["value"] == 42
    raw = Path(result["output_path"]).read_bytes()
    assert result["artifacts"][0]["sha256"] == hashlib.sha256(raw).hexdigest()


def test_parsed_failed_control_survives_unconfirmed_cleanup_without_approval(runner, inputs, monkeypatch):
    handle = {"kind": "quickjs-worker", "pid": 12345, "owner_nonce": "a" * 32}
    actual = {"observations": [{"unit_id": "unit", "seed": 11, "condition": "production", "metric": "value", "value": 42}],
              "controls": [{"name": "positive result", "passed": True, "details": "Trusted parsed frame fixture"},
                           {"name": "negative mismatch", "passed": False, "details": "Actual false control in parsed frame fixture"}],
              "fixtures": [{"label": "input", "encoding": "base64", "content": base64.b64encode(b"[41]").decode(),
                            "sha256": hashlib.sha256(b"[41]").hexdigest()}]}
    raw = json.dumps(actual, separators=(",", ":")).encode("utf-8")
    monkeypatch.setattr(runner, "status", lambda: {"ready": True})
    monkeypatch.setattr(runner, "_runtime", lambda: (Path("trusted-node"), {}))
    monkeypatch.setattr(runner, "_execute", lambda *_a, **_k: {
        "exit_code": None, "cleanup_confirmed": False, "active_handle": handle, "duration_seconds": 0,
        "reason": None, "envelope": {"protocol": "paper-factory-quickjs-v1", "status": "failed",
            "error": "Fatal runtime boundary", "observation_b64": base64.b64encode(raw).decode(),
            "production_calls": [{"path": "source.js", "function": "calculate", "calls": 1}],
            "runtime_manifest": {"production_entrypoint": "source.js:calculate", "distinct_wasm_memories": True,
                                 "hard_linear_growth_denied": True}}})
    result = run(runner, inputs, experiment("return {};"))
    assert result["status"] == "blocked"
    assert result["code"] == "CLEANUP_UNCONFIRMED"
    assert result["cleanup_confirmed"] is False
    assert result["active_handle"] == handle
    assert Path(result["output_path"]).read_bytes() == raw
    assert json.loads(raw)["controls"][1]["passed"] is False
    assert result["production_calls"] == [{"path": "source.js", "function": "calculate", "calls": 1}]
    assert result["artifacts"][0]["sha256"] == hashlib.sha256(raw).hexdigest()


def test_fixture_text_preserves_embedded_nul_utf8_bytes(runner, inputs):
    text = "before\x00after🙂"
    code = experiment("const value=JSON.parse(callProduction('[41]'));\n"
                      + "const fixture=JSON.parse(retainFixture('actual_nul', " + json.dumps(text, ensure_ascii=False) + "));\n"
                      + envelope(fixtures="[fixture]"))
    result = run(runner, inputs, code)
    fixture = observed(result)["fixtures"][0]
    raw = base64.b64decode(fixture["content"], validate=True)
    assert raw == text.encode("utf-8"), {"retained": raw, "expected": text.encode("utf-8")}
    assert fixture["sha256"] == hashlib.sha256(raw).hexdigest()


def test_gate_does_not_truncate_trailing_nul_before_json_validation(runner, inputs):
    code = experiment("""
        let denied = false;
        try { callProduction('[41]\\u0000junk'); } catch { denied = true; }
        const value = denied ? 1 : 0;
        """ + envelope())
    result = run(runner, inputs, code)
    assert failed_observed(result)["observations"][0]["value"] == 1
    assert result["production_calls"] == []


@pytest.mark.parametrize("arguments", ["'input', '\\ud800'", "'\\ud800', 'actual'"])
def test_fixture_lone_surrogate_is_rejected_without_lossy_encoding(runner, inputs, arguments):
    code = experiment("let denied=false; try { retainFixture(" + arguments + "); } catch { denied=true; }\n"
                      "const value=denied ? 1 : 0;\n" + envelope())
    result = run(runner, inputs, code)
    payload = failed_observed(result)
    assert payload["observations"][0]["value"] == 1
    assert result["production_calls"] == []
    assert manifest(inputs)["fixture_bytes"] == len(b"[41]")


def test_fixture_surrogate_pair_preserves_actual_utf8_bytes(runner, inputs):
    code = experiment("const value=JSON.parse(callProduction('[41]'));\n"
                      "const fixture=JSON.parse(retainFixture('pair', '\\ud83d\\ude42'));\n"
                      + envelope(fixtures="[fixture]"))
    fixture = observed(run(runner, inputs, code))["fixtures"][0]
    raw = base64.b64decode(fixture["content"], validate=True)
    assert raw == "🙂".encode("utf-8")
    assert fixture["sha256"] == hashlib.sha256(raw).hexdigest()


def test_gate_preserves_json_escaped_surrogate_argument(runner, inputs):
    (inputs[0] / "source.js").write_bytes(
        b"module.exports={calculate(x){return {length:x.length,code:x.charCodeAt(0)}}};\n")
    code = experiment(r"""
        const actual=JSON.parse(callProduction(String.raw`["\ud800"]`));
        if (actual.length !== 1) throw Error('JSON argument was rewritten');
        const value=actual.code;
        """ + envelope())
    result = run(runner, inputs, code)
    assert observed(result)["observations"][0]["value"] == 0xD800
    assert result["production_calls"] == [{"path": "source.js", "function": "calculate", "calls": 1}]


def mocked_proc(monkeypatch, contents, links, *, caller_pid=5):
    """Fixed kernel-metadata fixtures; no real process or /proc access."""
    class ProcPath:
        def __init__(self, path):
            self.path = str(path)

        def read_text(self, **_options):
            assert self.path in contents, "Unexpected process metadata read: " + self.path
            return contents[self.path]

    monkeypatch.setattr(module, "Path", ProcPath)
    monkeypatch.setattr(module, "os", SimpleNamespace(getpid=lambda: caller_pid,
                                                    readlink=lambda path: links[path]))


def test_namespace_mapping_uses_callers_inner_pid_not_proc_visible_pid(monkeypatch):
    mocked_proc(monkeypatch, {"/proc/self/status": "Pid:\t2821\nNSpid:\t2821\t5\n"},
                {"/proc/self/ns/pid": "pid:[4026533123]"})
    assert module._namespace() == {"pid_namespace": "pid:[4026533123]", "namespace_index": 1,
                                   "proc_pid": 2821, "namespace_pid": 5}


@pytest.mark.parametrize("status", ["Pid: 5\nNSpid: 5 5\n", "Pid: 2821\nNSpid: 2821 6\n",
                                    "Pid: 111\nNSpid: 2821 5\n"])
def test_ambiguous_or_inconsistent_caller_namespace_mapping_is_rejected(monkeypatch, status):
    mocked_proc(monkeypatch, {"/proc/self/status": status}, {})
    with pytest.raises(ValueError):
        module._namespace()


def test_pidfd_maps_inner_child_pid_to_verified_proc_visible_identity(monkeypatch):
    mocked_proc(monkeypatch, {"/proc/self/fdinfo/77": "Pid:\t2887\nNSpid:\t2887\t6\n"},
                {"/proc/2887/ns/pid": "pid:[4026533123]"})
    namespace = {"pid_namespace": "pid:[4026533123]", "namespace_index": 1}
    assert module._pidfd_identity(77, 6, namespace) == {
        "proc_pid": 2887, "pid_namespace": "pid:[4026533123]", "namespace_index": 1}


@pytest.mark.parametrize("fdinfo", ["Pid: -1\nNSpid: -1 -1\n", "Pid: 2887\nNSpid: 2887 7\n",
                                    "Pid: 2887\nNSpid: 2887\n", "Pid: 999\nNSpid: 2887 6\n"])
def test_pidfd_foreign_or_ambiguous_identity_is_rejected(monkeypatch, fdinfo):
    mocked_proc(monkeypatch, {"/proc/self/fdinfo/77": fdinfo}, {})
    with pytest.raises(ValueError):
        module._pidfd_identity(77, 6, {"pid_namespace": "pid:[4026533123]", "namespace_index": 1})


def test_pidfd_matching_number_in_foreign_pid_namespace_is_rejected(monkeypatch):
    mocked_proc(monkeypatch, {"/proc/self/fdinfo/77": "Pid: 2887\nNSpid: 2887 6\n"},
                {"/proc/2887/ns/pid": "pid:[4026533999]"})
    with pytest.raises(ValueError):
        module._pidfd_identity(77, 6, {"pid_namespace": "pid:[4026533123]", "namespace_index": 1})


def test_supervisor_state_cannot_modify_immutable_runtime(pinned_runtime):
    with pytest.raises(ValueError):
        QuickJSRunner(pinned_runtime, supervisor_root=pinned_runtime / "supervisor")


@pytest.mark.parametrize("failure", [PermissionError(13, "private path must not be exposed", "/secret/owner"),
                                     OSError(5, "private I/O details", "/secret/owner")])
def test_supervisor_access_failure_blocks_without_spawn_write_or_false_cleanup(pinned_runtime, supervisor_root,
                                                                              inputs, monkeypatch, failure):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    candidate._journal_path.write_bytes(b'{"format":"paper-factory-quickjs-supervisor-v1","workers":[]}\n')
    before = candidate._journal_path.read_bytes()
    monkeypatch.setattr(module, "file_lock", lambda _path: (_ for _ in ()).throw(failure))
    monkeypatch.setattr(candidate, "_execute", lambda *_a, **_k: pytest.fail("Inaccessible supervisor must not spawn"))
    monkeypatch.setattr(candidate, "_persist", lambda: pytest.fail("Inaccessible supervisor must not write journal"))
    snapshot = candidate.status()
    assert snapshot["ready"] is False and snapshot["cleanup_confirmed"] is False
    assert snapshot["code"] == "SUPERVISOR_UNAVAILABLE" and "busy" not in snapshot["reason"]
    assert snapshot["diagnostic"] == {"stage": "supervisor-prepare", "exception_type": type(failure).__name__,
                                      "errno": failure.errno}
    assert "/secret/owner" not in json.dumps(snapshot) and "private path" not in json.dumps(snapshot)
    result = run(candidate, inputs, experiment("return {};"))
    assert result["status"] == "blocked" and result["code"] == "CLEANUP_UNCONFIRMED"
    assert result["cleanup_confirmed"] is False and result["active_handle"] == {}
    assert candidate._journal_path.read_bytes() == before and candidate._lease is None


def test_supervisor_error_numeric_diagnostics_are_bounded(pinned_runtime, supervisor_root, monkeypatch):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    failure = OSError(99999, "sensitive path")
    failure.winerror = 999999
    monkeypatch.setattr(candidate, "_prepare", lambda: (_ for _ in ()).throw(failure))
    snapshot = candidate.status()
    assert snapshot["diagnostic"] == {"stage": "supervisor-prepare", "exception_type": "OSError"}
    assert snapshot["cleanup_confirmed"] is False


def test_journal_missing_is_empty_but_permission_denied_is_not_absence(pinned_runtime, supervisor_root, monkeypatch):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    assert candidate._load_journal() == {}
    actual_read, actual_exists = module._read, Path.exists

    def denied(path, limit):
        if path == candidate._journal_path:
            raise PermissionError(13, "private journal")
        return actual_read(path, limit)

    # Some supported pathlib versions report inaccessible paths as exists=False.
    # State access must still use a read and distinguish EACCES from ENOENT.
    monkeypatch.setattr(Path, "exists", lambda path: False if path == candidate._journal_path else actual_exists(path))
    monkeypatch.setattr(module, "_read", denied)
    with pytest.raises(PermissionError):
        candidate._load_journal()
    with pytest.raises(PermissionError):
        QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)


@pytest.mark.parametrize("raw", [b'not-json',
                                b'{"format":"paper-factory-quickjs-supervisor-v1","workers":"invalid"}'])
def test_invalid_journal_reload_is_blocked_and_preserved(pinned_runtime, supervisor_root, monkeypatch, raw):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    candidate._journal_path.write_bytes(raw)
    monkeypatch.setattr(candidate, "_execute", lambda *_a, **_k: pytest.fail("Invalid journal must not spawn"))
    monkeypatch.setattr(candidate, "_persist", lambda: pytest.fail("Invalid journal must not be rewritten"))
    snapshot = candidate.status()
    assert snapshot["ready"] is False and snapshot["cleanup_confirmed"] is False
    assert snapshot["code"] == "SUPERVISOR_STATE_INVALID" and "busy" not in snapshot["reason"]
    assert snapshot["diagnostic"]["stage"] == "supervisor-prepare"
    assert candidate._journal_path.read_bytes() == raw and candidate._lease is None


def test_busy_empty_cached_journal_does_not_prove_owned_cleanup(pinned_runtime, supervisor_root, monkeypatch):
    owner = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    assert owner._prepare() is True
    owner._persist()
    observer = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    before = owner._journal_path.read_bytes()
    monkeypatch.setattr(observer, "_execute", lambda *_a, **_k: pytest.fail("Live owner must not be interrupted"))
    try:
        snapshot = observer.status()
        assert snapshot["ready"] is False and snapshot["cleanup_confirmed"] is False
        assert snapshot["code"] == "SUPERVISOR_BUSY"
        assert owner._journal_path.read_bytes() == before and owner._lease is not None
    finally:
        owner._release_lease()


def test_second_supervisor_never_reaps_a_live_controller_worker(pinned_runtime, supervisor_root, monkeypatch):
    owner = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    nonce = "a" * 32
    handle = {"kind": "quickjs-worker", "pid": 12345, "owner_nonce": nonce}
    assert owner._prepare() is True
    owner._active[nonce] = {"process": OwnedFakeProcess(), "pidfd": None, "handle": handle}
    owner._records[nonce] = {"phase": "running", "purpose": "experiment", "handle": handle}
    owner._persist()
    observer = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    monkeypatch.setattr(observer, "stop", lambda _handle: pytest.fail("Live owner's child must not be reaped"))
    try:
        before = observer._journal_path.read_bytes()
        snapshot = observer.status()
        assert snapshot["ready"] is False and snapshot["cleanup_confirmed"] is False
        assert snapshot["code"] == "CLEANUP_UNCONFIRMED"
        assert snapshot["diagnostic"]["exception_type"] == "ValueError"
        assert observer._journal_path.read_bytes() == before
        with pytest.raises(ValueError, match="Another operation is already running"):
            observer._prepare()
        assert observer._active == {}
        assert json.loads(observer._journal_path.read_bytes())["workers"][0]["handle"] == handle
    finally:
        # These are in-memory process fixtures, so release their actual file
        # lease without signalling any process or leaving test-owned state.
        owner._active.clear()
        owner._records.clear()
        owner._persist()
        owner._release_lease()


def test_orphaned_probe_journal_blocks_fresh_supervisor_and_new_spawn(pinned_runtime, supervisor_root, inputs, monkeypatch):
    previous = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    handle = {"kind": "quickjs-worker", "pid": 12345, "owner_nonce": "a" * 32}
    assert previous._prepare() is True
    previous._records[handle["owner_nonce"]] = {"phase": "unresolved", "purpose": "probe", "handle": handle}
    previous._persist()
    previous._release_lease()
    fresh = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    attempts = []
    monkeypatch.setattr(fresh, "_stop_recovered", lambda value: attempts.append(value.copy()) or False)
    monkeypatch.setattr(fresh, "_execute", lambda *_a, **_k: pytest.fail("Unresolved probe must prohibit spawning"))
    snapshot = fresh.status()
    assert snapshot["ready"] is False and snapshot["cleanup_confirmed"] is False
    result = run(fresh, inputs, experiment("return {};"))
    assert result["status"] == "blocked" and result["code"] == "CLEANUP_UNCONFIRMED"
    assert result["cleanup_confirmed"] is False and result["output_path"] is None
    assert attempts and all(value == handle for value in attempts)
    assert json.loads(fresh._journal_path.read_bytes())["workers"][0]["handle"] == handle


def test_busy_execute_preserves_the_live_owners_journal_bytes(pinned_runtime, supervisor_root, monkeypatch):
    owner = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    assert owner._prepare() is True
    handle = {"kind": "quickjs-worker", "pid": 12345, "owner_nonce": "a" * 32}
    owner._active[handle["owner_nonce"]] = {"process": OwnedFakeProcess(), "pidfd": None, "handle": handle}
    owner._records[handle["owner_nonce"]] = {"phase": "running", "purpose": "experiment", "handle": handle}
    owner._persist()
    before = owner._journal_path.read_bytes()
    observer = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_k: pytest.fail("Busy supervisor must not spawn"))
    try:
        result = observer._execute(Path("trusted-node"), {"timeout_seconds": 1}, purpose="probe")
        assert result["reason"] == "controller failure" and result["cleanup_confirmed"] is False
        assert observer._journal_path.read_bytes() == before
        assert observer._active == {} and owner._active[handle["owner_nonce"]]["process"].poll() is None
    finally:
        owner._active.clear()
        owner._records.clear()
        owner._persist()
        owner._release_lease()


def test_successful_orphan_recovery_keeps_lease_until_fresh_spawn(pinned_runtime, supervisor_root, monkeypatch):
    previous = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    assert previous._prepare() is True
    old_handle = {"kind": "quickjs-worker", "pid": 12345, "owner_nonce": "a" * 32}
    previous._records[old_handle["owner_nonce"]] = {"phase": "unresolved", "purpose": "probe", "handle": old_handle}
    previous._persist()
    previous._release_lease()
    fresh = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    recovered, spawned = [], []
    child = OwnedFakeProcess()
    fake_windows_job(monkeypatch, child)
    def recover(handle):
        assert fresh._lease is not None
        recovered.append(handle.copy())
        return True
    def spawn(*_arguments, **_options):
        assert fresh._lease is not None
        current = json.loads(fresh._journal_path.read_bytes())["workers"]
        assert len(current) == 1 and current[0]["phase"] == "starting" and current[0]["purpose"] == "probe"
        assert current[0]["handle"]["owner_nonce"] != old_handle["owner_nonce"]
        competing = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
        with pytest.raises(ValueError, match="Another operation is already running"):
            competing._prepare()
        spawned.append(True)
        return child
    mock_windows_os(monkeypatch)
    monkeypatch.setattr(fresh, "_stop_recovered", recover)
    monkeypatch.setattr(module.subprocess, "Popen", spawn)
    ticks = iter([0, 5])
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: next(ticks, 5), sleep=lambda _seconds: None))
    result = fresh._execute(Path("trusted-node"), {"timeout_seconds": 1}, purpose="probe")
    assert recovered == [old_handle] and spawned == [True]
    assert result["cleanup_confirmed"] is True and child.poll() == -9
    assert fresh._active == {} and fresh._lease is None
    assert json.loads(fresh._journal_path.read_bytes())["workers"] == []


def recovery_metadata(monkeypatch):
    """Fixed identity metadata and ESRCH only; this never opens a real pidfd."""
    actual_os, actual_path = module.os, module.Path
    opened = []
    class LinuxOs:
        name = "posix"
        def __getattr__(self, name):
            return getattr(actual_os, name)
        def getuid(self):
            return 100
        def pidfd_open(self, pid, flags):
            opened.append((pid, flags))
            raise ProcessLookupError("Recorded process is absent")
    monkeypatch.setattr(module, "os", LinuxOs())
    monkeypatch.setattr(module, "sys", SimpleNamespace(**{**vars(module.sys), "platform": "linux"}))
    monkeypatch.setattr(module, "signal", SimpleNamespace(SIGKILL=9, pidfd_send_signal=lambda *_a: pytest.fail("No process signal")))
    namespace = {"pid_namespace": "pid:[4026533123]", "namespace_index": 1}
    monkeypatch.setattr(module, "_namespace", lambda: namespace)
    monkeypatch.setattr(module, "Path", lambda path: SimpleNamespace(read_text=lambda **_k: "boot")
                        if str(path) == "/proc/sys/kernel/random/boot_id" else actual_path(path))
    handle = {"kind": "quickjs-worker", "pid": 6, "proc_pid": 2887, "owner_nonce": "a" * 32,
              **namespace, "start_time": "123456", "boot_id": "boot", "owner_uid": 100,
              "node_path": str(actual_path(shutil.which(os.environ.get("PF_NODE_BIN") or "node")).resolve()),
              "worker_sha256": module._hash(module._read(module.WORKER, 128 * 1024))}
    return handle, opened


def test_complete_private_workflow_handle_confirms_absence_after_journal_clear(pinned_runtime, supervisor_root, monkeypatch):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    handle, opened = recovery_metadata(monkeypatch)
    assert candidate._records == {}
    assert candidate.stop(handle) is True
    assert opened == [(6, 0)]
    assert candidate._active == {} and candidate._lease is None


@pytest.mark.parametrize("field,value", [("start_time", None), ("proc_pid", True),
                                         ("pid_namespace", "pid:[4026533999]"), ("namespace_index", -1),
                                         ("node_path", "untrusted-node"), ("worker_sha256", None)])
def test_partial_or_foreign_workflow_handle_is_rejected_before_pidfd_open(pinned_runtime, supervisor_root, monkeypatch, field, value):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    handle, opened = recovery_metadata(monkeypatch)
    handle[field] = value
    assert candidate.stop(handle) is False
    assert opened == []
    assert candidate._active == {} and candidate._lease is None


@pytest.mark.parametrize("identity_failure", [False, True])
def test_live_pidfd_order_mapping_journal_and_cleanup(pinned_runtime, supervisor_root, monkeypatch, identity_failure):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    events, private = [], {}
    actual_os, actual_path = module.os, module.Path
    class Input(io.BytesIO):
        def write(self, value):
            records = json.loads(candidate._journal_path.read_bytes())["workers"]
            assert len(records) == 1 and records[0]["phase"] == "running"
            events.append("feed")
            return super().write(value)
    class Child(OwnedFakeProcess):
        def poll(self):
            events.append("poll")
            if identity_failure and self.stdin.closed:
                self.returncode = 2  # Fixed trusted-worker EOF failure, no guest ran.
            return self.returncode
    child = Child()
    child.pid, child.stdin = 6, Input()
    class LinuxOs:
        name = "posix"
        def __getattr__(self, name):
            return getattr(actual_os, name)
        def getuid(self):
            return 100
        def pidfd_open(self, pid, flags):
            assert (pid, flags) == (6, 0) and "poll" not in events and "feed" not in events
            events.append("open77")
            return 77
        def dup(self, descriptor):
            assert descriptor == 77
            events.append("dup78")
            return 78
        def close(self, descriptor):
            if descriptor in {77, 78}:
                events.append("close" + str(descriptor))
            else:
                actual_os.close(descriptor)
    def spawn(arguments, **options):
        private.update(arguments=arguments, nonce=options["env"]["PF_QUICKJS_OWNER"])
        assert candidate._lease is not None
        return child
    def proc_path(path):
        if str(path) == "/proc/2887/environ":
            return SimpleNamespace(open=lambda *_a: io.BytesIO(("PF_QUICKJS_OWNER=" + private["nonce"]).encode() + b"\0"))
        if str(path) == "/proc/2887/cmdline":
            return SimpleNamespace(open=lambda *_a: io.BytesIO(b"\0".join(actual_os.fsencode(item) for item in private["arguments"]) + b"\0"))
        return actual_path(path)
    def identity(pid):
        assert pid == 2887
        events.append("identity2887")
        if identity_failure:
            raise FileNotFoundError("Fixed missing mapped proc metadata")
        return {"start_time": "123456", "boot_id": "boot", "owner_uid": 100}
    def signal_child(descriptor, *_arguments):
        assert descriptor == 78
        events.append("signal78")
        child.returncode = -9
    def callback(handle):
        assert "pidfd" not in handle and "fd" not in handle
        assert handle["pid"] == 6 and handle["proc_pid"] == 2887
        assert json.loads(candidate._journal_path.read_bytes())["workers"][0] == {
            "phase": "running", "purpose": "probe", "handle": handle}
        events.append("callback")
    monkeypatch.setattr(module, "os", LinuxOs())
    monkeypatch.setattr(module, "sys", SimpleNamespace(**{**vars(module.sys), "platform": "linux"}))
    monkeypatch.setattr(module, "Path", proc_path)
    monkeypatch.setattr(module.subprocess, "Popen", spawn)
    monkeypatch.setattr(module, "signal", SimpleNamespace(SIGCHLD=17, SIG_DFL=0, SIGKILL=9,
                            getsignal=lambda _signal: 0, pidfd_send_signal=signal_child))
    monkeypatch.setattr(module, "_namespace", lambda: {"pid_namespace": "pid:[4026533123]", "namespace_index": 1})
    monkeypatch.setattr(module, "_pidfd_identity", lambda descriptor, pid, _namespace:
                        {"proc_pid": 2887, "pid_namespace": "pid:[4026533123]", "namespace_index": 1}
                        if (descriptor, pid) == (77, 6) else pytest.fail("Wrong owned descriptor mapping"))
    monkeypatch.setattr(module, "_linux_identity", identity)
    result = candidate._execute(actual_path("trusted-node"), {"timeout_seconds": 1}, cancel=lambda: True,
                                on_handle=callback, purpose="probe")
    assert result["cleanup_confirmed"] is True
    assert result["reason"] == ("controller failure" if identity_failure else "cancelled")
    assert events.count("open77") == events.count("close77") == 1
    assert events.count("identity2887") == (1 if identity_failure else 2)
    if identity_failure:
        assert all(event not in events for event in ("callback", "feed", "dup78", "signal78", "close78"))
        assert child.returncode == 2
    else:
        assert events.index("open77") < events.index("identity2887") < events.index("callback") < events.index("feed")
        assert "identity2887" not in events[events.index("callback") + 1:]
        assert events.count("dup78") == events.count("signal78") == events.count("close78") == 1
        assert events.index("signal78") < events.index("close78") < events.index("close77")
        assert child.returncode == -9
    assert all(pipe.closed for pipe in (child.stdin, child.stdout, child.stderr))
    assert candidate._active == {} and candidate._lease is None
    assert json.loads(candidate._journal_path.read_bytes())["workers"] == []


def test_nondefault_sigchld_is_rejected_before_spawning(pinned_runtime, supervisor_root, monkeypatch):
    candidate = QuickJSRunner(pinned_runtime, supervisor_root=supervisor_root)
    actual_os = module.os
    class LinuxOs:
        name = "posix"
        def __getattr__(self, name):
            return getattr(actual_os, name)
    monkeypatch.setattr(module, "os", LinuxOs())
    monkeypatch.setattr(module, "sys", SimpleNamespace(**{**vars(module.sys), "platform": "linux"}))
    monkeypatch.setattr(module, "signal", SimpleNamespace(SIGCHLD=17, SIG_DFL=0, getsignal=lambda _signal: 1))
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_k: pytest.fail("Unsupported SIGCHLD must not spawn"))
    result = candidate._execute(Path("trusted-node"), {"timeout_seconds": 1}, purpose="probe")
    assert result["reason"] == "controller failure" and result["cleanup_confirmed"] is True
    assert candidate._active == {} and candidate._lease is None

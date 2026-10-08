"""Synthetic Chromium routing contracts; these fixtures execute no browser or science."""

import base64
import copy
import hashlib
import json
from pathlib import Path
import zipfile

from jsonschema import Draft202012Validator
import pytest

from paper_factory.autonomous import science
from paper_factory.autonomous.models import CodeBundle, ResearchPlan
from paper_factory.workflow import (
    EXECUTION_INSTRUMENTATION, WorkflowError, WorkflowService, _design_identity,
    _production_execution, _protocol_runtime, _reproduction_runtime_instructions,
    _freeze,
)
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import digest_file, write_json
from test_workflow import FixtureRunner, REVIEW, STUDY_REVIEW, collect, finished, protocol


def browser_protocol():
    return {**protocol(), "runtime": "chromium", "source_files": ["dependency.js", "editor.js"],
            "production_entrypoint": "editor.js:ResearchFixture.transform"}


def browser_bundle():
    return {"runtime": "chromium", "entrypoint": "experiment.mjs", "files": [{
        "path": "experiment.mjs", "content": "export default async function run(){throw new Error('Synthetic fixture never executes');}\n"}],
        "explanation": "Unexecuted synthetic browser routing fixture; it establishes no research value."}


class BrowserFixtureRunner(FixtureRunner):
    def __init__(self):
        super().__init__()
        self.browser_ready = True
        self.manifest_defect = None
        self.received_order = None
        self.received_selector = None
        self.raw_defect = None

    def status(self):
        quickjs = super().status()
        chromium = {"ready": self.browser_ready, "simulation": True, "backend": "chromium-sandbox",
                    "runtimes": ["chromium"] if self.browser_ready else [], "dependencies": [],
                    "declared_limits": {"native_job_memory_bytes": 1024 ** 3, "native_job_processes": 16},
                    "versions": {"chromium": "synthetic-not-executed"}, "capabilities": {"simulation": True},
                    "native_host_rss_limit_claimed": False}
        return {**quickjs, "runtimes": ["quickjs", "chromium"] if self.browser_ready else ["quickjs"],
                "profiles": {"quickjs": quickjs, "chromium": chromium}}

    def run(self, source_dir, bundle_dir, output_dir, *, runtime, entrypoint, production_entrypoint,
            scientific_inputs, source_order, timeout_seconds, cancel, on_handle):
        assert runtime == "chromium" and timeout_seconds == 300
        assert Path(bundle_dir, entrypoint).is_file()
        assert source_order == ["dependency.js", "editor.js"]
        self.calls += 1
        self.received_order = list(source_order)
        self.received_selector = production_entrypoint
        self.scientific_inputs = copy.deepcopy(scientific_inputs)
        self.entered.set()
        on_handle({"kind": "fixture", "pid": 123, "simulation": True})
        if self.manifest_defect != "absent":
            manifest = {"backend": "chromium-sandbox", "simulation": True,
                        "source_order": list(source_order), "production_entrypoint": production_entrypoint,
                        "source_files": {name: {"original_sha256": digest_file(Path(source_dir, name)),
                                                "size": Path(source_dir, name).stat().st_size} for name in source_order}}
            if self.manifest_defect == "order":
                manifest["source_order"].reverse()
            elif self.manifest_defect == "selector":
                manifest["production_entrypoint"] = "editor.js:ResearchFixture.other"
            elif self.manifest_defect == "hash":
                manifest["source_files"]["editor.js"]["original_sha256"] = "0" * 64
            elif self.manifest_defect == "size":
                manifest["source_files"]["editor.js"]["size"] = True
            elif self.manifest_defect == "extra":
                manifest["source_files"]["extra.js"] = {"original_sha256": "0" * 64, "size": 0}
            write_json(Path(output_dir, "runtime-manifest.json"), manifest)
        write_json(Path(output_dir, "observations.json"), copy.deepcopy(self.outputs))
        raw = (b"Malformed synthetic worker frame\xff\n" if self.raw_defect == "malformed" else
               (json.dumps({"simulation": True, "scope": "Native workflow double; no Chromium execution",
                            "observations": self.outputs}, ensure_ascii=False) + "\n").encode())
        artifacts = []
        if self.raw_defect != "absent":
            Path(output_dir, "worker-response.json").write_bytes(raw)
            artifacts.append({"path": "worker-response.json", "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
            if self.raw_defect == "digest":
                artifacts[0]["sha256"] = "0" * 64
            elif self.raw_defect == "size":
                artifacts[0]["size"] = True
            elif self.raw_defect == "path":
                artifacts[0]["path"] = "../worker-response.json"
            elif self.raw_defect == "duplicate":
                artifacts.append(copy.deepcopy(artifacts[0]))
        return {"status": "failed" if self.raw_defect == "malformed" else "succeeded",
                "artifacts": artifacts, "simulation": True, "backend": "chromium-sandbox", "exit_code": 0,
                "coverage_mechanism": "synthetic-controller-held-chromium-call-gate",
                "coverage_truncated": self.coverage_truncated, "cleanup_confirmed": self.cleanup_confirmed,
                "active_handle": {} if self.cleanup_confirmed else {"kind": "fixture", "pid": 123},
                "production_calls": [{"path": "editor.js", "function": "ResearchFixture.transform", "calls": 6}]
                    if self.production_calls else []}


@pytest.fixture
def browser_setup(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "dependency.js").write_bytes(b"var fixtureDependency = 1;\r\n")
    (source / "editor.js").write_bytes(b"var ResearchFixture = {transform(values){return values.slice();}};\r\n")
    runner = BrowserFixtureRunner()
    service = WorkflowService(tmp_path / "home", runner=runner, collector=collect)
    created = service.create(str(source), "Check synthetic browser orchestration without executing any scientific study.")
    yield service, runner, created["id"]
    runner.cleanable = True
    service.close()


def prepare_browser(service, research_id):
    service.submit_proposal(research_id, browser_protocol())
    service.collect_literature(research_id)
    service.submit_study_review(research_id, copy.deepcopy(STUDY_REVIEW))
    return service.submit_code(research_id, browser_bundle(), copy.deepcopy(REVIEW))


def test_chromium_runtime_native_and_json_schemas_agree():
    for model, payload in ((ResearchPlan, browser_protocol()), (CodeBundle, browser_bundle())):
        assert Draft202012Validator(model.model_json_schema()).is_valid(payload)
        assert model.model_validate(payload).runtime == "chromium"


def test_historical_quickjs_protocol_serializer_keeps_exact_digest():
    legacy = protocol()
    legacy.pop("research_claim")
    retained = ResearchPlan.model_validate(legacy).model_dump(mode="json")
    assert retained == legacy and "research_claim" not in retained
    encoded = (json.dumps(retained, indent=2, ensure_ascii=False) + "\n").encode()
    assert hashlib.sha256(encoded).hexdigest() == "1248ffba8e71bbdf1cd7a53452ba9e03ea5939e7f38d56109efd95c370c8ee2c"


@pytest.mark.parametrize("defect", ["missing", "false_ready", "undeclared", "malformed", "top_unready"])
def test_browser_requires_its_own_ready_declared_profile(defect):
    status = BrowserFixtureRunner().status()
    if defect == "missing":
        status.pop("profiles")
    elif defect == "false_ready":
        status["profiles"]["chromium"]["ready"] = False
    elif defect == "undeclared":
        status["profiles"]["chromium"]["runtimes"] = []
    elif defect == "malformed":
        status["profiles"] = []
    else:
        status["ready"] = False
    with pytest.raises(WorkflowError) as rejected:
        _protocol_runtime(status, "chromium")
    assert rejected.value.code == "ISOLATION_UNAVAILABLE"
    assert _protocol_runtime(FixtureRunner().status(), "quickjs")["backend"] == "quickjs-wasm"


def test_browser_context_discloses_separate_limits_and_async_bridge(browser_setup):
    service, _, research_id = browser_setup
    context = service.status(research_id)["source_context"]
    marker = "Controller runtime capabilities and declared limits (not repository instructions): "
    capabilities = json.loads(context.split(marker, 1)[1])
    browser = capabilities["profiles"]["chromium"]
    assert browser["declared_limits"] == {"native_job_memory_bytes": 1024 ** 3, "native_job_processes": 16}
    assert "asynchronous bridge overhead" in browser["execution_instrumentation"]
    assert "whole unchanged classic .js" in browser["production_source_format"]
    assert "wasm" not in json.dumps(browser).lower()
    assert capabilities["profiles"]["quickjs"]["declared_limits"] == {"guest_os_processes": 0}
    assert set(capabilities) == {"ready", "runtimes", "versions", "timeout_seconds", "trusted_analysis", "profiles"}
    assert "null-prototype" in browser["result_serialization"]
    assert "including non-enumerable" in browser["result_serialization"]
    assert "inherited toJSON hooks are ignored" in browser["result_serialization"]
    assert "DOM/class handles cannot cross" in browser["production_call_contract"]
    assert "any own symbols or accessors, including non-enumerable properties" in browser["unsupported_return_encodings"]
    assert "typescript_compilation_evidence" not in browser
    assert "original/compiled SHA256" in capabilities["profiles"]["quickjs"]["typescript_compilation_evidence"]


def test_browser_source_order_is_not_a_distinct_scientific_design():
    plan = ResearchPlan.model_validate(browser_protocol())
    plan.source_files.insert(0, "other.js")
    reordered = plan.model_copy(deep=True)
    reordered.source_files = ["dependency.js", "other.js", "editor.js"]
    assert _design_identity(plan) == _design_identity(reordered)
    assert plan.model_dump(mode="json")["source_files"] != reordered.model_dump(mode="json")["source_files"]


def test_browser_dispatch_preserves_whole_source_order_and_all_frozen_inputs(browser_setup):
    service, runner, research_id = browser_setup
    before = service.status(research_id)
    assert before["execution_attempt"] == runner.calls == 0
    service.add_evidence(research_id, [{"name": "annotations.md", "contentBase64": base64.b64encode(
        b"Synthetic frozen annotations; no observed browser findings.").decode()}])
    prepare_browser(service, research_id)
    assert runner.calls == 0
    service.start_experiment(research_id)
    result = finished(service, research_id)
    assert result["stage"] == "analyzed" and result["execution_attempt"] == runner.calls == 1
    assert runner.received_order == ["dependency.js", "editor.js"]
    assert runner.received_selector == "editor.js:ResearchFixture.transform"
    ws = service._workspace(research_id)
    service._require_successful_analysis(ws, ws.get("workflow", research_id, Workflow))
    assert runner.scientific_inputs["source/dependency.js"]["text"] == "var fixtureDependency = 1;\r\n"
    assert runner.scientific_inputs["source/editor.js"]["text"].endswith(";\r\n")
    assert any(key.startswith("supporting-document-") for key in runner.scientific_inputs)
    assert "runtime-manifest" in result["artifacts"]
    assert {"worker-response", "worker-response-1"} <= result["artifacts"].keys()
    assert result["plan"]["parameters"]["execution_instrumentation"] == EXECUTION_INSTRUMENTATION["chromium"]
    for operation in (lambda: service.start_experiment(research_id),
                      lambda: service.submit_code(research_id, browser_bundle(), REVIEW)):
        with pytest.raises(WorkflowError) as rejected:
            operation()
        assert rejected.value.code == "EXPERIMENT_ALREADY_DISPATCHED"
    assert runner.calls == 1


def test_browser_readiness_loss_is_rejected_before_dispatch_budget_consumed(browser_setup):
    service, runner, research_id = browser_setup
    prepare_browser(service, research_id)
    runner.browser_ready = False
    with pytest.raises(WorkflowError) as rejected:
        service.start_experiment(research_id)
    assert rejected.value.code == "ISOLATION_UNAVAILABLE"
    assert service.status(research_id)["execution_attempt"] == runner.calls == 0


@pytest.mark.parametrize("target", ["literature", "selected-literature", "study-review", "plan", "bundle", "source"])
def test_browser_dispatch_requires_unchanged_reading_review_protocol_and_source(browser_setup, target):
    service, runner, research_id = browser_setup
    prepare_browser(service, research_id)
    path = (service._workspace(research_id).path("source/editor.js") if target == "source"
            else service.artifact_path(research_id, target))
    path.chmod(0o644)
    path.write_bytes(b"Changed synthetic frozen input.\n")
    with pytest.raises(ValueError, match="changed|modified"):
        service.start_experiment(research_id)
    assert runner.calls == 0


@pytest.mark.parametrize("defect", ["absent", "order", "selector", "hash", "size", "extra"])
def test_browser_analysis_requires_frozen_exact_manifest(browser_setup, defect):
    service, runner, research_id = browser_setup
    runner.manifest_defect = defect
    prepare_browser(service, research_id)
    service.start_experiment(research_id)
    result = finished(service, research_id)
    assert result["code"] == "RUNTIME_EVIDENCE_UNVERIFIED" and "analysis" not in result
    assert runner.calls == result["execution_attempt"] == 1
    assert "observations" in result["artifacts"]


@pytest.mark.parametrize("defect", ["absent", "digest", "size", "path", "duplicate"])
def test_browser_original_raw_binding_is_required_without_discarding_bytes(browser_setup, defect):
    service, runner, research_id = browser_setup
    runner.raw_defect = defect
    prepare_browser(service, research_id)
    service.start_experiment(research_id)
    result = finished(service, research_id)
    assert result["code"] == "RUNTIME_EVIDENCE_UNVERIFIED" and "analysis" not in result
    assert result["execution_attempt"] == runner.calls == 1
    assert "observations" in result["artifacts"]
    if defect != "absent":
        raw = service.artifact_path(research_id, "worker-response").read_bytes()
        assert json.loads(raw)["simulation"] is True
        assert service.artifact_path(research_id, "worker-response-1").read_bytes() == raw
    with pytest.raises(WorkflowError) as rejected:
        service.start_experiment(research_id)
    assert rejected.value.code == "EXPERIMENT_ALREADY_DISPATCHED"
    ws = service._workspace(research_id)
    record = ws.get("workflow", research_id, Workflow)
    for operation in (lambda: service._analyze(ws, record), lambda: service._require_successful_analysis(ws, record)):
        with pytest.raises(WorkflowError) as replay_rejected:
            operation()
        assert replay_rejected.value.code == "RUNTIME_EVIDENCE_UNVERIFIED"
    assert "analysis" not in record.artifacts


@pytest.mark.parametrize("operation", ["cancel", "close", "restart"])
@pytest.mark.parametrize("defect", [None, "absent", "digest", "size", "path", "duplicate"])
def test_browser_cleanup_reconciliation_rechecks_original_raw_binding(browser_setup, operation, defect):
    service, runner, research_id = browser_setup
    runner.cleanup_confirmed = runner.cleanable = False
    runner.raw_defect = defect
    prepare_browser(service, research_id)
    service.start_experiment(research_id)
    initial = finished(service, research_id)
    service._jobs[research_id].result(timeout=2)
    assert initial["code"] == "CLEANUP_UNCONFIRMED" and initial["cleanup_pending"] is True
    retained = {key: service.artifact_path(research_id, key).read_bytes() for key in initial["artifacts"]}
    runner.cleanable = True
    if operation == "cancel":
        service.cancel(research_id)
    elif operation == "close":
        service.close()
    else:
        recovered = WorkflowService(service.home, runner=runner, collector=collect)
        try:
            recovered.status(research_id)
        finally:
            recovered.close()
    ws = service._workspace(research_id)
    result = ws.get("workflow", research_id, Workflow)
    assert result.execution_attempt == runner.calls == 1 and not result.active_handle
    assert service._confirmed_cleanup(ws, result)
    assert all(service.artifact_path(research_id, key).read_bytes() == raw for key, raw in retained.items())
    if defect is None:
        assert result.stage == "analyzed" and "analysis" in result.artifacts
        service._require_successful_analysis(ws, result)
    else:
        assert result.stage == "code_ready" and result.code == "RUNTIME_EVIDENCE_UNVERIFIED"
        assert "analysis" not in result.artifacts


def test_browser_malformed_negative_raw_bytes_are_frozen_without_json_normalization(browser_setup):
    service, runner, research_id = browser_setup
    runner.raw_defect = "malformed"
    prepare_browser(service, research_id)
    service.start_experiment(research_id)
    result = finished(service, research_id)
    assert result["code"] == "EXPERIMENT_FAILED" and "analysis" not in result
    raw = b"Malformed synthetic worker frame\xff\n"
    assert service.artifact_path(research_id, "worker-response").read_bytes() == raw
    assert service.artifact_path(research_id, "worker-response") == service.artifact_path(research_id, "worker-response-1")
    for key in ("worker-response", "worker-response-1"):
        assert result["artifacts"][key] == {"id": key, "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def test_browser_raw_response_is_readable_and_reproduction_zip_keeps_identical_bytes(browser_setup):
    """Private ZIP selection only; fake export slots are not publication artifacts."""
    service, _, research_id = browser_setup
    prepare_browser(service, research_id)
    service.start_experiment(research_id)
    assert finished(service, research_id)["stage"] == "analyzed"
    raw = service.artifact_path(research_id, "worker-response").read_bytes()
    material = service.read_material(research_id, "evidence", "worker-response")
    assert material["text"].encode() == raw and material["sha256"] == hashlib.sha256(raw).hexdigest()
    ws = service._workspace(research_id)
    record = ws.get("workflow", research_id, Workflow)
    root = ws.path("research/synthetic-zip-control")
    root.mkdir()
    for key in ("canonical", "export-md", "export-pdf", "export-docx", "export-tex", "conversion", "manuscript-review"):
        path = root / (key + ".txt")
        path.write_bytes(b"Synthetic ZIP plumbing only; no native document or publication proof.\n")
        _freeze(ws, record, key, path)
    service._bundle(ws, record, root)
    with zipfile.ZipFile(root / "reproducibility.zip") as archive:
        assert archive.read("worker-response.json") == raw
        inventory = json.loads(archive.read("inventory.json"))
        assert inventory["worker-response.json"] == {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
        assert b"BrowserRunner.run" in archive.read("README.md")


@pytest.mark.parametrize("defect", ["calls", "truncated", "rows", "fixture", "control", "cleanup"])
def test_browser_existing_raw_control_fixture_cleanup_gates_remain(browser_setup, defect):
    service, runner, research_id = browser_setup
    if defect == "calls":
        runner.production_calls = False
    elif defect == "truncated":
        runner.coverage_truncated = True
    elif defect == "rows":
        runner.outputs["observations"].pop()
    elif defect == "fixture":
        runner.outputs["fixtures"][0]["sha256"] = "0" * 64
    elif defect == "control":
        runner.outputs["controls"][1]["passed"] = False
    else:
        runner.cleanup_confirmed = False
        runner.cleanable = False
    prepare_browser(service, research_id)
    service.start_experiment(research_id)
    result = finished(service, research_id)
    assert result["status"] == "blocked" and "analysis" not in result
    assert runner.calls == result["execution_attempt"] == 1
    assert "observations" in result["artifacts"]
    if defect == "control":
        assert result["terminal_control_failure"] and result["code"] == "CONTROL_FAILED"
    elif defect == "cleanup":
        assert result["code"] == "CLEANUP_UNCONFIRMED"


def test_browser_production_receipt_requires_full_qualified_chain():
    plan = ResearchPlan.model_validate(browser_protocol())
    receipt = {"coverage_truncated": False, "production_calls": [{"path": "editor.js", "function": "transform", "calls": 1}]}
    with pytest.raises(WorkflowError) as rejected:
        _production_execution(receipt, plan)
    assert rejected.value.code == "PRODUCTION_EXECUTION_UNVERIFIED"
    receipt["production_calls"][0]["function"] = "ResearchFixture.transform"
    _production_execution(receipt, plan)


def test_browser_cjs_experiment_rejected_before_code_attempt(browser_setup):
    service, runner, research_id = browser_setup
    service.submit_proposal(research_id, browser_protocol())
    service.collect_literature(research_id)
    service.submit_study_review(research_id, copy.deepcopy(STUDY_REVIEW))
    bundle = browser_bundle()
    bundle["entrypoint"] = bundle["files"][0]["path"] = "experiment.cjs"
    with pytest.raises(ValueError, match="Chromium experiment files"):
        service.submit_code(research_id, bundle, REVIEW)
    assert service.status(research_id)["code_attempt"] == runner.calls == 0


def test_browser_secondary_cjs_rejected_before_code_or_execution_attempt(browser_setup):
    service, runner, research_id = browser_setup
    service.submit_proposal(research_id, browser_protocol())
    service.collect_literature(research_id)
    service.submit_study_review(research_id, copy.deepcopy(STUDY_REVIEW))
    bundle = browser_bundle()
    bundle["files"].append({"path": "secondary.cjs", "content": "module.exports={synthetic:true};"})
    with pytest.raises(ValueError, match="Chromium experiment files"):
        service.submit_code(research_id, bundle, REVIEW)
    state = service.status(research_id)
    assert state["code_attempt"] == state["execution_attempt"] == runner.calls == 0
    assert "bundle" not in state["artifacts"]


def test_browser_inert_files_are_frozen_without_dispatch(browser_setup):
    service, runner, research_id = browser_setup
    service.submit_proposal(research_id, browser_protocol())
    service.collect_literature(research_id)
    service.submit_study_review(research_id, copy.deepcopy(STUDY_REVIEW))
    bundle = browser_bundle()
    bundle["files"].extend({"path": "notes" + extension, "content": "Synthetic retained artifact."}
                           for extension in (".json", ".md", ".txt"))
    accepted = service.submit_code(research_id, bundle, REVIEW)
    assert accepted["code_attempt"] == 1 and accepted["execution_attempt"] == runner.calls == 0
    metadata = json.loads(service.artifact_path(research_id, "bundle").read_bytes())
    assert {item["path"] for item in metadata["files"]} == {"experiment.mjs", "notes.json", "notes.md", "notes.txt"}


def test_reproduction_instructions_use_exact_selected_runtime_contract():
    browser = _reproduction_runtime_instructions(ResearchPlan.model_validate(browser_protocol()))
    quickjs = _reproduction_runtime_instructions(ResearchPlan.model_validate(protocol()))
    assert "BrowserRunner.run" in browser and "source_order=plan.source_files" in browser
    assert "Await callProduction" in browser and "original UTF-8 bytes without newline conversion" in browser
    assert "does not inherit QuickJS Wasm heap guarantees" in browser
    assert "DOM execution alone does not validate geometry" in browser
    assert "QuickJSRunner.run" in quickjs and "TypeScript is erased" in quickjs
    assert "BrowserRunner" not in quickjs


@pytest.mark.parametrize("defect", ["ts", "mjs", "cjs", "final_file", "unqualified", "accessor_syntax"])
def test_browser_plan_requires_ordered_classic_sources_and_exact_selector(tmp_path, defect):
    plan = browser_protocol()
    if defect in {"ts", "mjs", "cjs"}:
        plan["source_files"][0] = "dependency." + defect
    elif defect == "final_file":
        plan["source_files"].reverse()
    elif defect == "unqualified":
        plan["production_entrypoint"] = "editor.js:"
    else:
        plan["production_entrypoint"] = "editor.js:ResearchFixture['transform']"
    with pytest.raises(ValueError):
        science.validate_plan(ResearchPlan.model_validate(plan), tmp_path)


def test_browser_plan_accepts_canonical_order_without_rewriting_source_bytes(tmp_path):
    plan = ResearchPlan.model_validate(browser_protocol())
    for name in plan.source_files:
        (tmp_path / name).write_bytes(b"// Synthetic whole frozen source.\r\n")
    original = {name: (tmp_path / name).read_bytes() for name in plan.source_files}
    science.validate_plan(plan, tmp_path)
    assert plan.source_files == ["dependency.js", "editor.js"]
    assert {name: (tmp_path / name).read_bytes() for name in plan.source_files} == original

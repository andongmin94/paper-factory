"""Native host submissions with synthetic runners; no inference or network."""

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from types import SimpleNamespace
import zipfile

import pytest

from paper_factory.autonomous import science
from paper_factory.autonomous.models import FrozenArtifact
from paper_factory.workflow import WorkflowError, WorkflowService
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import Workspace, digest_file, write_json


def protocol():
    return {
        "feasible": True, "reason": "A production callable supports controlled synthetic contract checks.",
        "title": "Controlled transformation contract study for native workflow validation",
        "question": "How does the selected production transformation preserve protected fixture values?",
        "runtime": "quickjs", "source_files": ["transform.js"], "production_entrypoint": "transform.js:transform",
        "dependencies": [], "conditions": ["production", "ablation"],
        "metrics": [{"name": "error", "unit": "events", "description": "Independently detected transformation contract violations."}],
        "comparator": "An explicit guard removal ablation retains the other transformation rules.",
        "independent_oracle": "Fixture annotations define expected values independently of the comparator.",
        "sampling_unit": "An independently seeded input with protected fixture annotations.",
        "units_per_seed": 3, "seeds": [11, 37], "parameters": {"fixture_size": 12},
        "procedure": ["Generate seeded inputs and independent annotations.", "Invoke unchanged source and an explicit comparator.",
                      "Measure paired errors and inspect positive and negative controls."],
        "analysis_method": "Descriptive statistics with differences paired by seed and fixture unit.",
        "limitations": ["Synthetic inputs do not represent natural populations.", "Instrumentation affects measured execution time."],
        "literature_queries": ["independent software testing oracle"],
    }


def observations():
    data = b'{"synthetic":true,"annotations":[0,1,2]}'
    return {"observations": [
        {"unit_id": f"case-{index}", "seed": seed, "condition": condition, "metric": "error",
         "value": 0 if condition == "production" else index + 1}
        for seed in (11, 37) for index in range(3) for condition in ("production", "ablation")
    ], "controls": [
        {"name": "positive control", "passed": True, "details": "Input agrees with independent expected annotations."},
        {"name": "negative control", "passed": True, "details": "An intentional deletion is detected by the fixture oracle."},
    ], "fixtures": [{"label": "synthetic-inputs.json", "encoding": "base64",
                      "content": base64.b64encode(data).decode(), "sha256": hashlib.sha256(data).hexdigest()}]}


def manuscript():
    paragraph = (
        "This synthetic manuscript fixture checks the transfer of a frozen software protocol into an evidence linked document. "
        "Its observations are simulated inputs for orchestration validation and cannot establish production correctness. "
        "The comparison separates a baseline condition from a declared ablation while preserving paired sampling units. "
        "The trusted analyzer determines descriptive statistics from retained records rather than accepting model supplied measurements. "
        "Source hashes and independent reproduction protect the relationship between these records and displayed numerical references. "
        "The fixture exercises document integrity checks and offers no evidence of scientific novelty or model inference. "
    )
    sections = []
    for heading in science.REQUIRED_SECTIONS:
        text = paragraph * 2
        if heading == "Abstract":
            text += "The paired mean difference is {{result:error.paired_2_minus_1.mean}} events."
        elif heading == "Results":
            text += ("The production mean is {{result:error.condition_1.mean}} events and the ablation mean is "
                     "{{result:error.condition_2.mean}} events. The paired mean difference is "
                     "{{result:error.paired_2_minus_1.mean}} events.")
        elif heading == "Experimental Setup":
            text += "The protocol uses {{parameter:units_per_seed}} units for each seed."
            text += " Recorded instrumentation: {{parameter:setting.execution_instrumentation}}."
        elif heading == "Related Work":
            text += "The synthetic passage describes independently defined expected outcomes {{citation:fixture-oracle}}."
        sections.append({"heading": heading, "text": text})
    return {"title": protocol()["title"], "sections": sections}


REVIEW = {"accepted": True, "issues": [], "checks": ["Synthetic native host review fixture"]}
BUNDLE = {"runtime": "quickjs", "entrypoint": "experiment.mjs", "files": [
    {"path": "experiment.mjs", "content": "export default function run() { throw new Error('Unexecuted synthetic fixture'); }\n"}],
    "explanation": "Controlled experiment fixture for deterministic workflow orchestration checks."}


def collect(queries, root, *, limit, cancel):
    assert queries and limit == 6
    text = ("Synthetic passage: independent software test oracles define expected outcomes separately from the implementation. "
            "Controlled fixtures compare behavior with annotations and cannot establish population failure rates.")
    raw = Path(root) / "literature" / "fixture-source.json"
    metadata = raw.with_name("fixture-metadata.json")
    decoded = raw.with_suffix(".txt")
    write_json(raw, {"fixture": True, "reading_text": text})
    write_json(metadata, {"title": "Synthetic oracle passage"})
    decoded.write_text(text, encoding="utf-8")
    source = {"id": "fixture-oracle", "scope": "abstract", "title": "Synthetic oracle passage", "authors": ["Fixture Author"],
              "simulation": True, "raw_path": "literature/fixture-source.json", "sha256": digest_file(raw),
              "metadata_path": "literature/fixture-metadata.json", "metadata_sha256": digest_file(metadata),
              "text_path": "literature/fixture-source.txt", "text_sha256": digest_file(decoded), "excerpts": [text]}
    return {"sources": [source], "cancelled": False, "simulation": True,
            "searches": [{"query": query, "provider": "Crossref", "status": "succeeded", "attempted": True,
                          "resolved_ids": [source["id"]]} for query in queries]}


class FixtureRunner:
    def __init__(self):
        self.outputs = observations()
        self.calls = 0
        self.entered = threading.Event()
        self.release = None
        self.production_calls = True
        self.coverage_truncated = False
        self.exit_status = "succeeded"
        self.cleanup_confirmed = True
        self.cleanable = True

    def status(self):
        return {"ready": True, "simulation": True, "backend": "quickjs-wasm", "runtimes": ["quickjs"], "dependencies": [], "declared_limits": {"guest_os_processes": 0}}

    def stop(self, handle):
        assert handle["kind"] == "fixture"
        if self.release:
            self.release.set()
        return self.cleanable

    def run(self, source_dir, bundle_dir, output_dir, *, runtime, entrypoint, production_entrypoint, timeout_seconds, cancel, on_handle):
        assert runtime == "quickjs" and timeout_seconds == 300
        assert production_entrypoint == "transform.js:transform"
        assert Path(source_dir, "transform.js").is_file() and Path(bundle_dir, entrypoint).is_file()
        self.calls += 1
        on_handle({"kind": "fixture", "pid": 123, "simulation": True})
        self.entered.set()
        if self.release:
            while not self.release.wait(0.01):
                if cancel():
                    return {"status": "cancelled", "cleanup_confirmed": True, "simulation": True}
        write_json(Path(output_dir) / "observations.json", copy.deepcopy(self.outputs))
        return {"status": self.exit_status, "simulation": True, "exit_code": 0,
                "coverage_mechanism": "synthetic", "coverage_truncated": self.coverage_truncated,
                "cleanup_confirmed": self.cleanup_confirmed,
                "active_handle": {"kind": "fixture", "pid": 123} if not self.cleanup_confirmed else {},
                "production_calls": [{"path": "transform.js", "function": "transform", "calls": 6}] if self.production_calls else []}


def test_controller_requires_explicit_owned_home_and_runner(tmp_path):
    with pytest.raises(TypeError):
        WorkflowService(runner=FixtureRunner())
    with pytest.raises(TypeError):
        WorkflowService(tmp_path / "home")
    with pytest.raises(ValueError, match="explicit QuickJS"):
        WorkflowService(tmp_path / "home", runner=None)
    assert not (tmp_path / "home").exists()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "matplotlib"))
    source = tmp_path / "input"
    source.mkdir()
    (source / "transform.js").write_text("export function transform(values) { return values.slice(); }\n", encoding="utf-8")
    runner = FixtureRunner()
    service = WorkflowService(tmp_path / "home", runner=runner, collector=collect)
    created = service.create(str(source), "Validate a bounded controlled production transformation study.")
    yield service, runner, created["id"]
    runner.cleanable = True
    if runner.release:
        runner.release.set()
    try:
        service.close()
    except WorkflowError:
        pass


def prepare(service, research_id):
    service.submit_plan(research_id, protocol())
    service.collect_literature(research_id)
    service.submit_code(research_id, copy.deepcopy(BUNDLE), REVIEW)


def test_planning_context_discloses_projection_and_only_retained_compiler_evidence(setup):
    service, _, research_id = setup
    context = service.status(research_id)["source_context"]
    marker = "Controller runtime capabilities and declared limits (not repository instructions): "
    capabilities = json.loads(context.split(marker, 1)[1])
    assert capabilities["json_projection_only"] is True
    assert "JSON.stringify" in capabilities["result_serialization"]
    assert "Map entries" in capabilities["unsupported_return_encodings"]
    compilation = capabilities["typescript_compilation_evidence"]
    assert "original/compiled SHA256" in compilation
    assert "per-file transformation_options" in compilation
    assert "shared options" in compilation
    assert all(field in compilation for field in ("transformer", "name", "version", "options"))
    assert set(capabilities["unavailable_evidence"]) == {
        "emitted JavaScript bytes", "separate pre-call syntax/builtin-probe receipt",
    }


def finished(service, research_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        result = service.status(research_id)
        if result["status"] != "running":
            return result
        time.sleep(0.01)
    raise AssertionError("Synthetic workflow worker did not complete")


def test_native_submissions_analyze_actual_runner_artifacts(setup):
    service, runner, research_id = setup
    assert set(service.status(research_id)["schemas"]) == {"plan", "code", "review", "manuscript"}
    prepare(service, research_id)
    started = service.start_experiment(research_id)
    assert started["status"] == "running" and "active_handle" not in started
    result = finished(service, research_id)
    assert result["stage"] == "analyzed" and result["status"] == "ready"
    assert result["analysis"]["results"]["error.condition_1.mean"]["value"] == 0
    assert runner.calls == 1
    result = service.submit_manuscript(research_id, manuscript(), REVIEW)
    assert result["stage"] == "manuscript"
    review = json.loads(service.artifact_path(research_id, "manuscript-review").read_text())
    assert review["origin"] == "native_host_submission"
    assert review["analysis_sha256"] == result["artifacts"]["analysis"]["sha256"]


def test_successful_evidence_cannot_be_rerun_or_replanned(setup):
    service, runner, research_id = setup
    prepare(service, research_id)
    service.start_experiment(research_id)
    assert finished(service, research_id)["stage"] == "analyzed"
    for operation in (lambda: service.start_experiment(research_id), lambda: service.submit_code(research_id, BUNDLE, REVIEW)):
        with pytest.raises(WorkflowError) as rejected:
            operation()
        assert rejected.value.code == "EXPERIMENT_ALREADY_DISPATCHED"
    with pytest.raises(WorkflowError, match="stage"):
        service.submit_plan(research_id, protocol())
    assert runner.calls == 1


@pytest.mark.parametrize("field", ["accepted", "issues"])
def test_native_review_rejection_prevents_dispatch(setup, field):
    service, runner, research_id = setup
    service.submit_plan(research_id, protocol())
    review = copy.deepcopy(REVIEW)
    review[field] = False if field == "accepted" else ["Independent oracle defect"]
    with pytest.raises(WorkflowError, match="defect|accept"):
        service.submit_code(research_id, BUNDLE, review)
    assert runner.calls == 0 and service.status(research_id)["stage"] == "planned"


@pytest.mark.parametrize("target", ["plan", "bundle", "source", "generated", "extra"])
def test_frozen_artifacts_cannot_change_before_execution(setup, target):
    service, runner, research_id = setup
    prepare(service, research_id)
    if target == "source":
        path = service.home / "workflows" / research_id / "source" / "transform.js"
    elif target in {"generated", "extra"}:
        path = service.artifact_path(research_id, "bundle").parent / "experiment.mjs"
        if target == "extra":
            path = path.with_name("injected.js")
    else:
        path = service.artifact_path(research_id, target)
    if path.exists():
        path.chmod(0o644)
    path.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="changed|modified"):
        service.start_experiment(research_id)
    assert runner.calls == 0


@pytest.mark.parametrize("failed_exit", [False, True])
def test_failed_scientific_control_is_terminal_even_after_nonzero_exit(setup, failed_exit):
    service, runner, research_id = setup
    runner.outputs["controls"][1]["passed"] = False
    if failed_exit:
        runner.exit_status = "failed"
    prepare(service, research_id)
    service.start_experiment(research_id)
    result = finished(service, research_id)
    assert result["code"] == "CONTROL_FAILED" and result["terminal_control_failure"]
    assert "observations" in result["artifacts"]
    for operation in (lambda: service.start_experiment(research_id), lambda: service.submit_code(research_id, BUNDLE, REVIEW)):
        with pytest.raises(WorkflowError) as rejected:
            operation()
        assert rejected.value.code == "EXPERIMENT_ALREADY_DISPATCHED"
    assert runner.calls == 1


@pytest.mark.parametrize("defect", ["production_calls", "coverage_truncated", "rows", "boolean", "fixture"])
def test_runner_evidence_must_satisfy_production_and_observation_contracts(setup, defect):
    service, runner, research_id = setup
    if defect == "production_calls":
        runner.production_calls = False
    elif defect == "coverage_truncated":
        runner.coverage_truncated = True
    elif defect == "rows":
        runner.outputs["observations"].pop()
    elif defect == "boolean":
        runner.outputs["observations"][0]["value"] = True
    else:
        runner.outputs["fixtures"][0]["sha256"] = "0" * 64
    prepare(service, research_id)
    service.start_experiment(research_id)
    result = finished(service, research_id)
    assert result["status"] == "blocked" and "analysis" not in result
    assert "observations" in result["artifacts"]


def test_code_validation_repairs_remain_available_before_first_dispatch(setup):
    service, runner, research_id = setup
    service.submit_plan(research_id, protocol())
    forged = copy.deepcopy(BUNDLE)
    forged["observations"] = observations()
    with pytest.raises(ValueError):
        service.submit_code(research_id, forged, REVIEW)
    forged = copy.deepcopy(BUNDLE)
    forged["files"][0]["path"] = forged["entrypoint"] = "../escape.mjs"
    with pytest.raises(ValueError, match="safe relative"):
        service.submit_code(research_id, forged, REVIEW)
    result = service.status(research_id)
    assert result["stage"] == "planned" and result["execution_attempt"] == runner.calls == 0
    accepted = service.submit_code(research_id, copy.deepcopy(BUNDLE), REVIEW)
    first_bundle = service.artifact_path(research_id, "bundle")
    first_bytes = first_bundle.read_bytes()
    assert accepted["code_attempt"] == 1 and accepted["execution_attempt"] == runner.calls == 0
    forged = copy.deepcopy(BUNDLE)
    forged["files"].append({"path": "bundle.json", "content": "{}"})
    with pytest.raises(ValueError, match="reserved controller metadata"):
        service.submit_code(research_id, forged, REVIEW)
    assert service.status(research_id)["code_attempt"] == 1
    repaired = copy.deepcopy(BUNDLE)
    repaired["files"][0]["content"] += "// Synthetic pre-dispatch code revision.\n"
    accepted = service.submit_code(research_id, repaired, REVIEW)
    assert accepted["stage"] == "code_ready" and accepted["code_attempt"] == 2
    assert accepted["execution_attempt"] == runner.calls == 0
    assert service.artifact_path(research_id, "bundle") != first_bundle and first_bundle.read_bytes() == first_bytes
    service.start_experiment(research_id)
    assert finished(service, research_id)["stage"] == "analyzed" and runner.calls == 1


@pytest.mark.parametrize("entrypoint", ["experiment.py", "experiment.ts", "experiment.json"])
def test_code_bundle_cannot_execute_native_or_non_module_files(setup, entrypoint):
    service, runner, research_id = setup
    service.submit_plan(research_id, protocol())
    forged = copy.deepcopy(BUNDLE)
    forged["files"][0]["path"] = forged["entrypoint"] = entrypoint
    with pytest.raises(ValueError):
        service.submit_code(research_id, forged, REVIEW)
    assert runner.calls == 0
    assert "bundle" not in service.status(research_id)["artifacts"]


def test_start_is_immediate_and_cancellation_stops_owned_execution(setup):
    service, runner, research_id = setup
    runner.release = threading.Event()
    prepare(service, research_id)
    service.start_experiment(research_id)
    assert runner.entered.wait(2)
    with pytest.raises(WorkflowError) as rejected:
        service.start_experiment(research_id)
    assert rejected.value.code == "EXPERIMENT_ALREADY_DISPATCHED"
    cancelled = service.cancel(research_id)
    assert cancelled["cancellation_requested"]
    result = finished(service, research_id)
    assert result["status"] == "cancelled" and runner.calls == 1


def retained_authoring_fixture(service, research_id):
    """Freeze an explicitly synthetic prior analysis without dispatching a runner."""
    prepare(service, research_id)
    ws = Workspace(service.root / research_id)
    record = ws.get("workflow", research_id, Workflow)
    raw = observations()
    plan = json.loads(service.artifact_path(research_id, "plan").read_bytes())
    execution = {"status": "succeeded", "cleanup_confirmed": True, "coverage_truncated": False,
                 "coverage_mechanism": "synthetic prior execution fixture",
                 "production_calls": [{"path": "transform.js", "function": "transform", "calls": 6}]}
    analysis = science._compute(raw, plan)
    for key, value in (("execution", execution), ("observations", raw)):
        path = ws.path("research/" + key + "-fixture.json")
        write_json(path, value)
        record.artifacts[key] = FrozenArtifact(path=path.relative_to(ws.root).as_posix(),
                                               sha256=digest_file(path), size=path.stat().st_size)
    analysis.update(raw_sha256=record.artifacts["observations"].sha256,
                    protocol_sha256=record.artifacts["plan"].sha256)
    path = ws.path("research/analysis-fixture.json")
    write_json(path, analysis)
    record.artifacts["analysis"] = FrozenArtifact(path=path.relative_to(ws.root).as_posix(),
                                                   sha256=digest_file(path), size=path.stat().st_size)
    record.execution_attempt, record.stage = 1, "analyzed"
    ws.save("workflow", record)
    return ws


@pytest.mark.parametrize("stage", ["analyzed", "manuscript"])
def test_cancelled_authoring_resumes_without_dispatch_and_preserves_prior_state(setup, stage, monkeypatch):
    service, runner, research_id = setup
    ws = retained_authoring_fixture(service, research_id)
    record = ws.get("workflow", research_id, Workflow)
    record.stage = stage
    ws.save("workflow", record)
    cancelled = service.cancel(research_id)
    before = {key: service.artifact_path(research_id, key).read_bytes() for key in cancelled["artifacts"]}
    prior = ws.get("workflow", research_id, Workflow).model_dump(mode="json")
    monkeypatch.setattr(service, "start_experiment", lambda *args: pytest.fail("Authoring resume dispatched an experiment"))
    monkeypatch.setattr(runner, "run", lambda *args, **kwargs: pytest.fail("Authoring resume called the runner"))
    resumed = service.resume_writing(research_id)
    assert resumed["status"] == "ready" and resumed["stage"] == stage
    assert resumed["code"] is None and resumed["cancellation_requested"] is False
    assert resumed["execution_attempt"] == 1 and runner.calls == 0
    keys = [key for key in resumed["artifacts"] if key.startswith("authoring-resume-")]
    assert len(keys) == 1
    receipt = json.loads(service.artifact_path(research_id, keys[0]).read_bytes())
    assert receipt["previous_workflow"] == prior and receipt["previous_status"] == "cancelled"
    assert receipt["previous_stage"] == stage and receipt["execution_attempt"] == 1
    assert receipt["execution_sha256"] == resumed["artifacts"]["execution"]["sha256"]
    assert receipt["at"].endswith("+00:00")
    for key, content in before.items():
        assert service.artifact_path(research_id, key).read_bytes() == content
    with pytest.raises(WorkflowError) as repeated:
        service.resume_writing(research_id)
    assert repeated.value.code == "INVALID_STATE"
    original_receipt = service.artifact_path(research_id, keys[0]).read_bytes()
    service.cancel(research_id)
    again = service.resume_writing(research_id)
    assert len([key for key in again["artifacts"] if key.startswith("authoring-resume-")]) == 2
    assert service.artifact_path(research_id, keys[0]).read_bytes() == original_receipt
    assert again["execution_attempt"] == 1 and runner.calls == 0


@pytest.mark.parametrize("defect,expected_code", [
    ("execution_stage", "INVALID_STATE"), ("terminal_control", "CONTROL_FAILED"),
    ("active_handle", "CLEANUP_UNCONFIRMED"), ("cleanup", "CLEANUP_UNCONFIRMED"),
    ("failed_execution", "EXPERIMENT_FAILED"), ("production_gate", "PRODUCTION_EXECUTION_UNVERIFIED"),
    ("failed_control", "CONTROL_FAILED"), ("missing_negative", "CONTROL_FAILED"),
    ("tampered_raw", "ARTIFACT_CHANGED"), ("analysis_link", "ARTIFACT_CHANGED"),
])
def test_authoring_resume_rejects_unsafe_or_changed_retained_evidence(setup, defect, expected_code):
    service, runner, research_id = setup
    ws = retained_authoring_fixture(service, research_id)
    service.cancel(research_id)
    record = ws.get("workflow", research_id, Workflow)
    if defect == "execution_stage":
        record.stage = "execute"
    elif defect == "terminal_control":
        record.terminal_control_failure = True
    elif defect == "active_handle":
        record.active_handle = {"kind": "fixture", "pid": 123}
    else:
        key = "observations" if defect in {"failed_control", "missing_negative", "tampered_raw"} else "analysis" if defect == "analysis_link" else "execution"
        path = service.artifact_path(research_id, key)
        value = json.loads(path.read_bytes())
        if defect == "cleanup":
            value["cleanup_confirmed"] = False
        elif defect == "failed_execution":
            value["status"] = "cancelled"
        elif defect == "production_gate":
            value["production_calls"] = []
        elif defect == "failed_control":
            value["controls"][1]["passed"] = False
        elif defect == "missing_negative":
            value["controls"] = value["controls"][:1]
        elif defect == "analysis_link":
            value["raw_sha256"] = "0" * 64
        else:
            value["observations"][0]["value"] = 99
        write_json(path, value)
        if defect != "tampered_raw":
            record.artifacts[key] = FrozenArtifact(path=path.relative_to(ws.root).as_posix(),
                                                   sha256=digest_file(path), size=path.stat().st_size)
    ws.save("workflow", record)
    with pytest.raises(WorkflowError) as rejected:
        service.resume_writing(research_id)
    assert rejected.value.code == expected_code
    after = ws.get("workflow", research_id, Workflow)
    assert after.status == "cancelled" and after.execution_attempt == 1 and runner.calls == 0
    assert not any(key.startswith("authoring-resume-") for key in after.artifacts)
    if defect == "active_handle":
        # The fixture identity is not a real process; keep fixture teardown local.
        after.active_handle = {}
        ws.save("workflow", after)


def test_authoring_resume_accepts_hash_bound_confirmed_cleanup_receipt(setup):
    service, runner, research_id = setup
    ws = retained_authoring_fixture(service, research_id)
    service.cancel(research_id)
    record = ws.get("workflow", research_id, Workflow)
    execution_path = service.artifact_path(research_id, "execution")
    execution = json.loads(execution_path.read_bytes())
    execution["cleanup_confirmed"] = False
    write_json(execution_path, execution)
    record.artifacts["execution"] = FrozenArtifact(path=execution_path.relative_to(ws.root).as_posix(),
                                                   sha256=digest_file(execution_path), size=execution_path.stat().st_size)
    cleanup_path = ws.path("research/cleanup-fixture.json")
    write_json(cleanup_path, {"confirmed": True, "execution_sha256": record.artifacts["execution"].sha256})
    record.artifacts["cleanup-1"] = FrozenArtifact(path=cleanup_path.relative_to(ws.root).as_posix(),
                                                   sha256=digest_file(cleanup_path), size=cleanup_path.stat().st_size)
    ws.save("workflow", record)
    assert service.resume_writing(research_id)["status"] == "ready" and runner.calls == 0


def test_close_cancels_workers_and_prevents_new_operations(setup):
    service, runner, research_id = setup
    runner.release = threading.Event()
    prepare(service, research_id)
    service.start_experiment(research_id)
    assert runner.entered.wait(2)
    service.close()
    with pytest.raises(ValueError, match="closed"):
        service.start_experiment(research_id)
    ws = Workspace(service.home / "workflows" / research_id)
    record = ws.get("workflow", research_id, Workflow)
    assert record.status == "cancelled" and not record.active_handle


def test_unconfirmed_cleanup_preserves_identity_and_blocks_reexecution(setup):
    service, runner, research_id = setup
    runner.cleanup_confirmed = False
    prepare(service, research_id)
    service.start_experiment(research_id)
    result = finished(service, research_id)
    assert result["code"] == "CLEANUP_UNCONFIRMED"
    ws = Workspace(service.home / "workflows" / research_id)
    assert ws.get("workflow", research_id, Workflow).active_handle["pid"] == 123
    with pytest.raises(WorkflowError) as rejected:
        service.start_experiment(research_id)
    assert rejected.value.code == "EXPERIMENT_ALREADY_DISPATCHED"


def test_native_export_reopens_files_and_recomputes_observations(setup, pandoc):
    service, runner, research_id = setup
    prepare(service, research_id)
    service.start_experiment(research_id)
    assert finished(service, research_id)["stage"] == "analyzed"
    service.submit_manuscript(research_id, manuscript(), REVIEW)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("PYPANDOC_PANDOC", pandoc)
        result = service.export(research_id)
    assert result["status"] == "completed" and result["stage"] == "exported"
    assert set(result["artifacts"]) >= {"export-md", "export-pdf", "export-docx", "export-tex", "validation", "reproducibility"}
    validation = json.loads(service.artifact_path(research_id, "validation").read_text())
    assert validation["passed"] is True
    assert validation["final_verification_in_archive"] is False
    journal_key = validation["verification_journal"]
    assert journal_key.startswith("verification-journal-") and journal_key in result["artifacts"]
    assert [row["phase"] for row in verification_rows(service.artifact_path(research_id, journal_key))] == VERIFICATION_PHASES
    with zipfile.ZipFile(service.artifact_path(research_id, "reproducibility")) as archive:
        assert archive.testzip() is None
        assert {"source/transform.js", "generated/experiment.mjs", "analysis/analysis.py", "observations.json"} <= set(archive.namelist())
        assert not {"verification.jsonl", "validation.json"} & set(archive.namelist())
        readme = archive.read("README.md").decode().casefold()
        assert "verification" in readme and "journal" in readme and "validation" in readme
        images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", archive.read("paper.md").decode())
        assert images
        inventory = json.loads(archive.read("inventory.json"))
        for image in images:
            assert image in archive.namelist() and image in inventory
            assert "analysis/" + image in archive.namelist()
            assert archive.read(image) == archive.read("analysis/" + image)
    assert runner.calls == 1


VERIFICATION_PHASES = ["artifact-source-validation", "trusted-analysis", "manuscript-rendering",
                       "pdf", "docx", "tex-conversion", "zip", "complete"]


def verification_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def synthetic_verification_export(setup, monkeypatch):
    """Exercise trusted verification using fake native documents, not native executables."""
    from paper_factory import conversion
    import docx
    import pypdf

    service, runner, research_id = setup
    ws = retained_authoring_fixture(service, research_id)
    service.submit_manuscript(research_id, manuscript(), REVIEW)

    def no_analysis_rendering(*args, **kwargs):
        pytest.fail("Export verification must recompute values without analysis files or figures")

    def fixture_conversion(markdown, output, **kwargs):
        content = (b"\\begin{document}\nSynthetic verification fixture.\n\\end{document}\n"
                   if output.suffix == ".tex" else b"Synthetic native document fixture: " + output.suffix.encode())
        output.write_bytes(content)
        return {"input_sha256": digest_file(markdown), "output_sha256": digest_file(output)}

    monkeypatch.setattr(science, "analyze", no_analysis_rendering)
    monkeypatch.setattr(science, "_figures", no_analysis_rendering)
    monkeypatch.setattr(conversion, "convert", fixture_conversion)
    monkeypatch.setattr(pypdf, "PdfReader", lambda *args, **kwargs: SimpleNamespace(
        is_encrypted=False, pages=[SimpleNamespace(extract_text=lambda: "Synthetic readable PDF fixture.")]))
    monkeypatch.setattr(docx, "Document", lambda *args, **kwargs: SimpleNamespace(
        paragraphs=[SimpleNamespace(text="synthetic document fixture " * 400)]))
    return service, runner, research_id, ws


def test_verification_recomputes_equal_values_without_rendering_analysis_and_fsyncs_each_phase(setup, monkeypatch):
    from paper_factory import workflow as workflow_module

    service, runner, research_id, ws = synthetic_verification_export(setup, monkeypatch)
    raw = json.loads(service.artifact_path(research_id, "observations").read_bytes())
    protocol_value = json.loads(service.artifact_path(research_id, "plan").read_bytes())
    retained = json.loads(service.artifact_path(research_id, "analysis").read_bytes())
    compute = science._compute
    expected = {key: value for key, value in retained.items() if key not in {"raw_sha256", "protocol_sha256"}}
    inputs = []

    def verified_compute(observations_value, frozen_protocol):
        inputs.append((copy.deepcopy(observations_value), copy.deepcopy(frozen_protocol)))
        result = compute(observations_value, frozen_protocol)
        assert result == expected
        return result

    monkeypatch.setattr(science, "_compute", verified_compute)
    journal_streams, durable_phases = [], []
    original_open, original_fsync, original_freeze = Path.open, os.fsync, workflow_module._freeze

    def tracked_open(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        mode = args[0] if args else kwargs.get("mode", "r")
        if path.name == "verification.jsonl" and mode == "x":
            journal_streams.append(stream)
        return stream

    def durable_sync(descriptor):
        original_fsync(descriptor)
        for stream in journal_streams:
            if not stream.closed and stream.fileno() == descriptor:
                rows = verification_rows(Path(stream.name))
                assert rows, "The journal phase must be flushed before fsync"
                durable_phases.append(rows[-1]["phase"])

    def freeze_closed_journal(workspace, record, key, path):
        if key.startswith("verification-journal-"):
            assert journal_streams and all(stream.closed for stream in journal_streams)
        return original_freeze(workspace, record, key, path)

    monkeypatch.setattr(Path, "open", tracked_open)
    monkeypatch.setattr(workflow_module.os, "fsync", durable_sync)
    monkeypatch.setattr(workflow_module, "_freeze", freeze_closed_journal)
    result = service.export(research_id)
    validation = json.loads(service.artifact_path(research_id, "validation").read_bytes())
    journal = service.artifact_path(research_id, validation["verification_journal"])
    rows = verification_rows(journal)
    assert inputs == [(raw, protocol_value)]
    assert [row["phase"] for row in rows] == durable_phases == VERIFICATION_PHASES
    assert all(set(row) == {"at", "research_id", "phase"} and row["research_id"] == research_id
               and row["at"].endswith("+00:00") for row in rows)
    assert len(journal_streams) == 1 and journal_streams[0].closed
    assert journal.parent.name.startswith("export-attempt-")
    assert validation["passed"] is True and validation["final_verification_in_archive"] is False
    assert result["stage"] == "exported" and result["status"] == "completed"
    assert result["execution_attempt"] == 1 and runner.calls == 0


@pytest.mark.parametrize("field", ["results", "parameters", "controls", "protocol_digest", "observation_digest", "summaries", "paired_deltas"])
def test_verification_rejects_changed_analysis_even_with_a_matching_artifact_hash(setup, monkeypatch, field):
    service, runner, research_id, ws = synthetic_verification_export(setup, monkeypatch)
    path = service.artifact_path(research_id, "analysis")
    analysis = json.loads(path.read_bytes())
    if field == "results":
        analysis[field]["error.condition_1.mean"]["value"] = 99
    elif field == "parameters":
        analysis[field]["units_per_seed"] = 99
    elif field == "controls":
        analysis[field][0]["details"] = "Synthetic altered interpretation of the retained control."
    elif field in {"protocol_digest", "observation_digest"}:
        analysis[field] = "0" * 64
    else:
        analysis[field][0]["mean"] = 99
    write_json(path, analysis)
    record = ws.get("workflow", research_id, Workflow)
    record.artifacts["analysis"] = FrozenArtifact(path=path.relative_to(ws.root).as_posix(),
                                                 sha256=digest_file(path), size=path.stat().st_size)
    ws.save("workflow", record)
    with pytest.raises(ValueError, match="Analysis differs from raw observation recomputation: " + field):
        service.export(research_id)
    journals = list(ws.path("research/exports").glob("*/verification.jsonl"))
    assert len(journals) == 1
    assert [row["phase"] for row in verification_rows(journals[0])] == VERIFICATION_PHASES[:2]
    after = ws.get("workflow", research_id, Workflow)
    assert not any(key.startswith("verification-journal-") for key in after.artifacts)
    assert after.stage == "manuscript" and after.execution_attempt == 1 and runner.calls == 0


@pytest.mark.parametrize("phase", VERIFICATION_PHASES[:-1])
def test_verification_failure_preserves_durable_journal_and_prior_attempt_bytes(setup, monkeypatch, phase):
    from paper_factory import conversion, workflow as workflow_module
    import docx
    import pypdf

    service, runner, research_id, ws = synthetic_verification_export(setup, monkeypatch)
    verify = service._verify
    journals, durable_phases = [], []
    original_fsync = os.fsync

    def interrupted(*args, **kwargs):
        raise RuntimeError("Synthetic verification interruption at " + phase)

    def interrupted_verification(workspace, record, journal):
        journals.append(journal)
        targets = {
            "artifact-source-validation": (workflow_module, "_verify_artifacts"),
            "trusted-analysis": (science, "_compute"),
            "manuscript-rendering": (science, "validate_and_render"),
            "pdf": (pypdf, "PdfReader"),
            "docx": (docx, "Document"),
            "tex-conversion": (conversion, "verify_receipts"),
            "zip": (zipfile, "ZipFile"),
        }
        target, name = targets[phase]
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(target, name, interrupted)
            return verify(workspace, record, journal)

    def durable_sync(descriptor):
        original_fsync(descriptor)
        for journal in journals:
            if journal.exists():
                opened = os.fstat(descriptor)
                retained = journal.stat()
                if (opened.st_dev, opened.st_ino) == (retained.st_dev, retained.st_ino):
                    rows = verification_rows(journal)
                    assert rows, "The interrupted phase must be flushed before fsync"
                    durable_phases.append(rows[-1]["phase"])

    monkeypatch.setattr(service, "_verify", interrupted_verification)
    monkeypatch.setattr(workflow_module.os, "fsync", durable_sync)
    expected_phases = VERIFICATION_PHASES[:VERIFICATION_PHASES.index(phase) + 1]
    with pytest.raises(RuntimeError, match="Synthetic verification interruption at " + phase):
        service.export(research_id)
    assert [row["phase"] for row in verification_rows(journals[0])] == durable_phases == expected_phases
    first = {path: path.read_bytes() for path in journals[0].parent.rglob("*") if path.is_file()}
    with pytest.raises(RuntimeError, match="Synthetic verification interruption at " + phase):
        service.export(research_id)
    assert journals[0] != journals[1] and journals[0].parent != journals[1].parent
    assert all(path.read_bytes() == content for path, content in first.items())
    assert [row["phase"] for row in verification_rows(journals[1])] == expected_phases
    assert durable_phases == expected_phases * 2
    after = ws.get("workflow", research_id, Workflow)
    assert not any(key.startswith("verification-journal-") for key in after.artifacts)
    assert "validation" not in after.artifacts
    assert after.stage == "manuscript" and after.execution_attempt == 1 and runner.calls == 0


def test_already_exported_verification_adds_only_a_new_journal_and_preserves_completed_outputs(setup, monkeypatch):
    service, runner, research_id, ws = synthetic_verification_export(setup, monkeypatch)
    completed = service.export(research_id)
    original = {key: service.artifact_path(research_id, key).read_bytes() for key in completed["artifacts"]}
    original_metadata = copy.deepcopy(completed["artifacts"])
    validation = json.loads(original["validation"])
    first_journal = validation["verification_journal"]
    repeated = service.export(research_id)
    added = set(repeated["artifacts"]) - set(completed["artifacts"])
    assert len(added) == 1
    new_journal = added.pop()
    assert new_journal.startswith("verification-journal-") and new_journal != first_journal
    path = service.artifact_path(research_id, new_journal)
    assert path.parent.name.startswith("verification-attempt-")
    assert [row["phase"] for row in verification_rows(path)] == VERIFICATION_PHASES
    assert all(service.artifact_path(research_id, key).read_bytes() == content for key, content in original.items())
    assert all(repeated["artifacts"][key] == value for key, value in original_metadata.items())
    assert json.loads(service.artifact_path(research_id, "validation").read_bytes())["verification_journal"] == first_journal
    assert repeated["status"] == "completed" and repeated["stage"] == "exported"
    assert repeated["execution_attempt"] == 1 and runner.calls == 0
    record = ws.get("workflow", research_id, Workflow)
    with pytest.raises(FileExistsError):
        service._verify(ws, record, service.artifact_path(research_id, first_journal))
    assert all(service.artifact_path(research_id, key).read_bytes() == content for key, content in original.items())
    assert set(record.artifacts) == set(repeated["artifacts"])


def test_completed_export_revision_preserves_bytes_and_approval_then_requires_a_new_draft(setup, monkeypatch):
    service, runner, research_id, ws = synthetic_verification_export(setup, monkeypatch)
    completed = service.export(research_id)
    prior = ws.get("workflow", research_id, Workflow).model_dump(mode="json")
    original = {key: (ws.path(item["path"]), ws.path(item["path"]).read_bytes())
                for key, item in prior["artifacts"].items()}
    for name in ("start_experiment", "_execute", "_analyze"):
        monkeypatch.setattr(service, name, lambda *args, **kwargs: pytest.fail("Writing revision dispatched or analyzed science"))
    monkeypatch.setattr(runner, "run", lambda *args, **kwargs: pytest.fail("Writing revision ran the experiment"))
    with monkeypatch.context() as revision_only:
        revision_only.setattr(science, "validate_and_render", lambda *args, **kwargs: pytest.fail("Revision generated a draft"))
        revision_only.setattr(service, "_verify", lambda *args, **kwargs: pytest.fail("Revision re-rendered native exports"))
        result = service.revise_writing(research_id)
    assert (result["status"], result["stage"], result["code"], result["cancellation_requested"]) == ("ready", "analyzed", None, False)
    assert (result["execution_attempt"], result["code_attempt"], result["draft_attempt"], runner.calls) == (1, 1, 1, 0)
    revision = next(key for key in result["artifacts"] if key.startswith("authoring-revision-"))
    receipt = json.loads(service.artifact_path(research_id, revision).read_bytes())
    assert receipt["id"] == revision and receipt["event"] == "authoring-revision" and receipt["at"].endswith("+00:00")
    assert receipt["previous_workflow"] == prior
    assert receipt["previous_status"] == "completed" and receipt["previous_stage"] == "exported"
    assert receipt["execution_attempt"] == 1
    assert all(receipt[name + "_sha256"] == prior["artifacts"][key]["sha256"] for name, key in
               (("execution", "execution"), ("observations", "observations"), ("analysis", "analysis")))
    assert revision in {item["name"] for item in result["material_manifest"]["evidence"]}
    assert json.loads(service.read_material(research_id, "evidence", revision, limit=32000)["text"]) == receipt
    for key, item in prior["artifacts"].items():
        preserved_key = receipt["preserved_artifacts"].get(key, key)
        assert ws.get("workflow", research_id, Workflow).artifacts[preserved_key].model_dump(mode="json") == item
        assert original[key][0].read_bytes() == original[key][1]
    for key in receipt["preserved_artifacts"]:
        assert key not in result["artifacts"]
    with pytest.raises(WorkflowError) as rejected:
        service.export(research_id)
    assert rejected.value.code == "INVALID_STATE"
    with pytest.raises(WorkflowError) as rejected:
        service.submit_code(research_id, BUNDLE, REVIEW)
    assert rejected.value.code == "EXPERIMENT_ALREADY_DISPATCHED"

    revised_draft = manuscript()
    revised_draft["title"] += " revised"
    manuscript_state = service.submit_manuscript(research_id, revised_draft, REVIEW)
    assert manuscript_state["draft_attempt"] == 2
    fresh_review = json.loads(service.artifact_path(research_id, "manuscript-review").read_bytes())
    old_review = json.loads(original["manuscript-review"][1])
    assert fresh_review["manuscript_sha256"] != old_review["manuscript_sha256"]
    assert fresh_review["manuscript_sha256"] == manuscript_state["artifacts"]["manuscript"]["sha256"]
    second_export = service.export(research_id)
    assert second_export["execution_attempt"] == 1 and second_export["draft_attempt"] == 2 and runner.calls == 0
    with zipfile.ZipFile(service.artifact_path(research_id, "reproducibility")) as archive:
        names = archive.namelist()
        assert archive.testzip() is None and len(names) == len(set(names))
        assert not any(name.endswith(".zip") for name in names)
        assert json.loads(archive.read("authoring/" + revision + ".json")) == receipt
        inventory = json.loads(archive.read("inventory.json"))
        for key, preserved_key in receipt["preserved_artifacts"].items():
            if key == "reproducibility":
                continue
            path, content = original[key]
            name = "authoring/history/" + preserved_key + "/" + path.name
            assert archive.read(name) == content
            assert inventory[name] == {"sha256": prior["artifacts"][key]["sha256"], "size": len(content)}
        for key in prior["artifacts"]:
            if key.startswith(("draft-", "verification-journal-")):
                path, content = original[key]
                assert archive.read("authoring/retained/" + key + "/" + path.name) == content
        for name, item in inventory.items():
            content = archive.read(name)
            assert item == {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
    assert all(path.read_bytes() == content for path, content in original.values())

    second_prior = ws.get("workflow", research_id, Workflow).model_dump(mode="json")
    second_original = {key: (ws.path(item["path"]), ws.path(item["path"]).read_bytes())
                       for key, item in second_prior["artifacts"].items()}
    again = service.revise_writing(research_id)
    assert len([key for key in again["artifacts"] if key.startswith("authoring-revision-")]) == 2
    revised_draft["title"] += " again"
    service.submit_manuscript(research_id, revised_draft, REVIEW)
    service.export(research_id)
    with zipfile.ZipFile(service.artifact_path(research_id, "reproducibility")) as archive:
        assert archive.testzip() is None and not any(name.endswith(".zip") for name in archive.namelist())
        assert "authoring/" + revision + ".json" in archive.namelist()
    assert all(path.read_bytes() == content for path, content in second_original.values())
    assert all(path.read_bytes() == content for path, content in original.values())
    assert service.status(research_id)["execution_attempt"] == 1 and runner.calls == 0


@pytest.mark.parametrize("status,stage", [
    ("ready", "analyzed"), ("cancelled", "analyzed"), ("ready", "manuscript"),
    ("failed", "exported"), ("blocked", "exported"), ("running", "exported"), ("completed", "analyzed"),
])
def test_writing_revision_rejects_other_states_without_mutation(setup, monkeypatch, status, stage):
    service, runner, research_id, ws = synthetic_verification_export(setup, monkeypatch)
    service.export(research_id)
    record = ws.get("workflow", research_id, Workflow)
    record.status, record.stage = status, stage
    ws.save("workflow", record)
    prior = record.model_dump(mode="json")
    files = {path: path.read_bytes() for path in ws.path("research").rglob("*") if path.is_file()}
    with pytest.raises(WorkflowError) as rejected:
        service.revise_writing(research_id)
    assert rejected.value.code == "INVALID_STATE"
    assert ws.get("workflow", research_id, Workflow).model_dump(mode="json") == prior
    assert all(path.read_bytes() == content for path, content in files.items()) and runner.calls == 0


@pytest.mark.parametrize("defect,expected_code", [
    ("terminal_control", "CONTROL_FAILED"), ("active_handle", "CLEANUP_UNCONFIRMED"),
    ("cleanup", "CLEANUP_UNCONFIRMED"), ("failed_execution", "EXPERIMENT_FAILED"),
    ("production_gate", "PRODUCTION_EXECUTION_UNVERIFIED"), ("failed_control", "CONTROL_FAILED"),
    ("missing_negative", "CONTROL_FAILED"), ("analysis_link", "ARTIFACT_CHANGED"),
    ("tampered_raw", "ARTIFACT_CHANGED"), ("tampered_source", "ARTIFACT_CHANGED"),
    ("missing_validation", "ARTIFACT_MISSING"), ("failed_validation", "REVISION_UNVERIFIED"),
    ("incomplete_journal", "REVISION_UNVERIFIED"), ("review_binding", "ARTIFACT_CHANGED"),
    ("rejected_review", "REVIEW_REJECTED"), ("receipt_collision", "REVISION_EVIDENCE_CONFLICT"),
])
def test_writing_revision_rejects_unsafe_or_changed_completed_evidence_before_mutation(setup, monkeypatch, defect, expected_code):
    from paper_factory import workflow as workflow_module
    service, runner, research_id, ws = synthetic_verification_export(setup, monkeypatch)
    service.export(research_id)
    record = ws.get("workflow", research_id, Workflow)
    if defect == "terminal_control":
        record.terminal_control_failure = True
    elif defect == "active_handle":
        record.active_handle = {"kind": "synthetic", "pid": 123}
    elif defect == "missing_validation":
        del record.artifacts["validation"]
    elif defect == "tampered_source":
        source = ws.path("source/transform.js")
        source.chmod(0o644)
        source.write_text("Synthetic changed source, never executed.", encoding="utf-8")
    elif defect == "receipt_collision":
        monkeypatch.setattr(workflow_module, "uid", lambda prefix: prefix + "-abcdefabcdef")
        ws.path("research/authoring-revision-abcdefabcdef.json").write_bytes(b"Retained collision fixture.")
    else:
        key = ("observations" if defect in {"failed_control", "missing_negative", "tampered_raw"} else
               "analysis" if defect == "analysis_link" else "validation" if defect == "failed_validation" else
               "manuscript-review" if defect in {"review_binding", "rejected_review"} else "execution")
        if defect == "incomplete_journal":
            key = json.loads(service.artifact_path(research_id, "validation").read_bytes())["verification_journal"]
        path = service.artifact_path(research_id, key)
        if defect == "incomplete_journal":
            path.write_text("\n".join(path.read_text(encoding="utf-8").splitlines()[:-1]) + "\n", encoding="utf-8")
        else:
            value = json.loads(path.read_bytes())
            if defect == "cleanup":
                value["cleanup_confirmed"] = False
            elif defect == "failed_execution":
                value["status"] = "cancelled"
            elif defect == "production_gate":
                value["production_calls"] = []
            elif defect == "failed_control":
                value["controls"][1]["passed"] = False
            elif defect == "missing_negative":
                value["controls"] = value["controls"][:1]
            elif defect == "analysis_link":
                value["raw_sha256"] = "0" * 64
            elif defect == "failed_validation":
                value["passed"] = False
            elif defect == "review_binding":
                value["manuscript_sha256"] = "0" * 64
            elif defect == "rejected_review":
                value["review"]["accepted"] = False
            else:
                value["observations"][0]["value"] = 99
            write_json(path, value)
        if defect != "tampered_raw":
            record.artifacts[key] = FrozenArtifact(path=path.relative_to(ws.root).as_posix(), sha256=digest_file(path), size=path.stat().st_size)
    ws.save("workflow", record)
    prior = record.model_dump(mode="json")
    files = {path: path.read_bytes() for path in ws.path("research").rglob("*") if path.is_file()}
    with pytest.raises((WorkflowError, ValueError)) as rejected:
        service.revise_writing(research_id)
    if defect == "tampered_source":
        assert "Source snapshot was modified" in str(rejected.value)
    else:
        assert rejected.value.code == expected_code
    after = ws.get("workflow", research_id, Workflow)
    assert after.model_dump(mode="json") == prior and not any(key.startswith("authoring-revision-") for key in after.artifacts)
    assert all(path.read_bytes() == content for path, content in files.items()) and runner.calls == 0
    if defect == "active_handle":
        after.active_handle = {}
        ws.save("workflow", after)


@pytest.mark.parametrize("failure_phase", ["draft-render", "native-export"])
def test_failed_revised_authoring_preserves_all_previous_completed_bytes(setup, monkeypatch, failure_phase):
    from paper_factory import conversion
    service, runner, research_id, ws = synthetic_verification_export(setup, monkeypatch)
    service.export(research_id)
    prior = ws.get("workflow", research_id, Workflow).model_dump(mode="json")
    original = {key: (ws.path(item["path"]), ws.path(item["path"]).read_bytes())
                for key, item in prior["artifacts"].items()}
    revised = service.revise_writing(research_id)
    revision = next(key for key in revised["artifacts"] if key.startswith("authoring-revision-"))
    receipt = json.loads(service.artifact_path(research_id, revision).read_bytes())
    def interrupted(*args, **kwargs):
        raise RuntimeError("Synthetic revised authoring interruption")
    if failure_phase == "draft-render":
        monkeypatch.setattr(science, "validate_and_render", interrupted)
        with pytest.raises(RuntimeError, match="Synthetic revised"):
            service.submit_manuscript(research_id, manuscript(), REVIEW)
    else:
        service.submit_manuscript(research_id, manuscript(), REVIEW)
        monkeypatch.setattr(conversion, "convert", interrupted)
        with pytest.raises(RuntimeError, match="Synthetic revised"):
            service.export(research_id)
    current = ws.get("workflow", research_id, Workflow)
    for key, item in prior["artifacts"].items():
        preserved = receipt["preserved_artifacts"].get(key, key)
        assert current.artifacts[preserved].model_dump(mode="json") == item
        assert original[key][0].read_bytes() == original[key][1]
    assert current.execution_attempt == 1 and runner.calls == 0


def test_failed_export_attempts_preserve_partial_files_without_rerunning_science(setup, monkeypatch):
    from paper_factory import conversion

    service, runner, research_id = setup
    prepare(service, research_id)
    service.start_experiment(research_id)
    assert finished(service, research_id)["stage"] == "analyzed"
    service.submit_manuscript(research_id, manuscript(), REVIEW)
    before = service.status(research_id)
    outputs = []

    def interrupted_conversion(markdown, output, **kwargs):
        outputs.append(output)
        output.write_bytes(b"synthetic interrupted native output " + str(len(outputs)).encode())
        raise TimeoutError("Synthetic export interruption after writing partial bytes")

    monkeypatch.setattr(conversion, "convert", interrupted_conversion)
    with pytest.raises(TimeoutError, match="Synthetic export"):
        service.export(research_id)
    first = {path: digest_file(path) for path in outputs[0].parent.iterdir() if path.is_file()}
    with pytest.raises(TimeoutError, match="Synthetic export"):
        service.export(research_id)
    assert outputs[0].parent != outputs[1].parent
    assert all(digest_file(path) == digest for path, digest in first.items())
    after = service.status(research_id)
    attempts = [key for key in after["artifacts"] if key.startswith("export-attempt-")]
    assert len(attempts) == 2
    for key in attempts:
        receipt = json.loads(service.artifact_path(research_id, key).read_bytes())
        assert receipt["event"] == "export-started"
        assert receipt["execution_attempt"] == 1
        assert receipt["manuscript_sha256"] == before["artifacts"]["manuscript"]["sha256"]
        assert receipt["execution_sha256"] == before["artifacts"]["execution"]["sha256"]
    assert after["artifacts"]["observations"] == before["artifacts"]["observations"]
    assert after["stage"] == "manuscript" and after["status"] == "ready"
    assert after["execution_attempt"] == runner.calls == 1


def test_artifact_resolution_never_accepts_host_paths(setup):
    service, runner, research_id = setup
    for invalid in ("../outside", "C:/Users", "research-../escape"):
        with pytest.raises(ValueError):
            service.status(invalid)
    with pytest.raises(WorkflowError, match="missing"):
        service.artifact_path(research_id, "../../private")


def test_restart_finishes_retained_success_without_favorable_rerun(setup):
    service, runner, research_id = setup
    prepare(service, research_id)
    service.start_experiment(research_id)
    assert finished(service, research_id)["stage"] == "analyzed"
    service.close()
    ws = Workspace(service.home / "workflows" / research_id)
    record = ws.get("workflow", research_id, Workflow)
    record.status, record.stage = "running", "execute"
    # Simulate a hard interruption after receipt/observations checkpoint and
    # before committing analysis. Existing uncheckpointed analysis is retained.
    record.artifacts = {key: value for key, value in record.artifacts.items()
                        if key != "analysis" and not key.startswith("analysis-")}
    ws.save("workflow", record)
    recovered = WorkflowService(service.home, runner=runner, collector=collect)
    try:
        result = recovered.status(research_id)
        assert result["stage"] == "analyzed" and result["status"] == "ready"
        assert runner.calls == 1
        with pytest.raises(WorkflowError) as rejected:
            recovered.start_experiment(research_id)
        assert rejected.value.code == "EXPERIMENT_ALREADY_DISPATCHED"
    finally:
        recovered.close()


def test_restart_preserves_failed_controls_even_before_terminal_checkpoint(setup):
    service, runner, research_id = setup
    runner.outputs["controls"][1]["passed"] = False
    prepare(service, research_id)
    service.start_experiment(research_id)
    assert finished(service, research_id)["code"] == "CONTROL_FAILED"
    service.close()
    ws = Workspace(service.home / "workflows" / research_id)
    record = ws.get("workflow", research_id, Workflow)
    record.status, record.stage, record.terminal_control_failure = "running", "execute", False
    ws.save("workflow", record)
    recovered = WorkflowService(service.home, runner=runner, collector=collect)
    try:
        result = recovered.status(research_id)
        assert result["code"] == "CONTROL_FAILED" and result["terminal_control_failure"]
        with pytest.raises(WorkflowError) as rejected:
            recovered.submit_code(research_id, BUNDLE, REVIEW)
        assert rejected.value.code == "EXPERIMENT_ALREADY_DISPATCHED"
        assert runner.calls == 1
    finally:
        recovered.close()


def test_another_service_does_not_reconcile_a_live_owned_worker(setup):
    service, runner, research_id = setup
    runner.release = threading.Event()
    prepare(service, research_id)
    service.start_experiment(research_id)
    assert runner.entered.wait(2)
    other = WorkflowService(service.home, runner=runner, collector=collect)
    try:
        assert other.status(research_id)["status"] == "running"
        assert runner.calls == 1
    finally:
        other.close()
    service.cancel(research_id)
    assert finished(service, research_id)["status"] == "cancelled"


def test_failed_worker_diagnostics_are_not_public_host_paths(setup):
    service, runner, research_id = setup
    prepare(service, research_id)
    def fail(*args, **kwargs):
        raise OSError("private C:/Users/Private/credentials.json could not be accessed")
    runner.run = fail
    service.start_experiment(research_id)
    result = finished(service, research_id)
    assert result["status"] == "blocked"
    assert "C:/Users" not in result["message"] and "credentials.json" not in result["message"]
    assert "C:/Users" not in result["diagnostics"]["validation"]
    assert "credentials.json" not in result["diagnostics"]["validation"]


@pytest.mark.parametrize("state", ["blocked", "cancelled", "running", "analyzed"])
def test_dispatched_experiment_rejects_code_replacement_and_reexecution_without_mutation(setup, monkeypatch, state):
    service, runner, research_id = setup
    if state == "blocked":
        runner.outputs["observations"].pop()
    elif state in {"cancelled", "running"}:
        runner.release = threading.Event()
    prepare(service, research_id)
    service.start_experiment(research_id)
    assert runner.entered.wait(2)
    if state == "cancelled":
        service.cancel(research_id)
    result = service.status(research_id) if state == "running" else finished(service, research_id)
    assert result["execution_attempt"] == runner.calls == 1
    if state == "analyzed":
        assert result["stage"] == "analyzed" and result["status"] == "ready"
    else:
        assert result["status"] == state
    if state == "blocked":
        diagnostic = result["diagnostics"]["validation"]
        assert "row" in diagnostic.lower()
        assert "C:/Users" not in diagnostic and str(service.home) not in diagnostic
        assert "do not replace its code or rerun this study" in result["instructions"]

    ws = Workspace(service.root / research_id)
    before = ws.get("workflow", research_id, Workflow).model_dump(mode="json")
    artifact_bytes = {key: service.artifact_path(research_id, key).read_bytes() for key in before["artifacts"]}
    research_files = {path.relative_to(ws.root).as_posix(): path.read_bytes()
                      for path in ws.path("research").rglob("*") if path.is_file()}

    def forbidden(*args, **kwargs):
        pytest.fail("A dispatched experiment must be rejected before state validation or runtime access")

    monkeypatch.setattr(service, "_require", forbidden)
    monkeypatch.setattr(runner, "status", forbidden)
    for operation in (lambda: service.submit_code(research_id, copy.deepcopy(BUNDLE), REVIEW),
                      lambda: service.start_experiment(research_id)):
        with pytest.raises(WorkflowError) as rejected:
            operation()
        assert rejected.value.code == "EXPERIMENT_ALREADY_DISPATCHED"
        assert ws.get("workflow", research_id, Workflow).model_dump(mode="json") == before
        assert service.status(research_id).get("diagnostics") == result.get("diagnostics")
        assert all(service.artifact_path(research_id, key).read_bytes() == content for key, content in artifact_bytes.items())
        assert {path.relative_to(ws.root).as_posix(): path.read_bytes()
                for path in ws.path("research").rglob("*") if path.is_file()} == research_files
        assert runner.calls == 1


def test_contract_instructions_cover_measurements_and_manuscript_requirements(setup):
    service, runner, research_id = setup
    created = service.status(research_id)
    assert "ResearchPlan" in created["instructions"]
    planned = service.submit_plan(research_id, protocol())
    assert "returned observations envelope" in planned["instructions"]
    assert "intentional" in planned["instructions"] and "base64" in planned["instructions"]
    service.collect_literature(research_id)
    service.submit_code(research_id, BUNDLE, REVIEW)
    service.start_experiment(research_id)
    analyzed = finished(service, research_id)
    assert "twelve hundred" in analyzed["instructions"]
    assert "{{result:key}}" in analyzed["instructions"] and "{{citation:id}}" in analyzed["instructions"]
    for heading in science.REQUIRED_SECTIONS:
        assert heading in analyzed["instructions"]


def test_incomplete_import_cannot_break_service_recovery(setup):
    service, runner, research_id = setup
    Workspace.create(service.root / "research-000000000001")
    other = WorkflowService(service.home, runner=runner, collector=collect)
    try:
        assert other.status(research_id)["stage"] == "created"
    finally:
        other.close()


def test_status_polling_can_exclude_materials(setup):
    service, runner, research_id = setup
    prepare(service, research_id)
    compact = service.status(research_id, include_materials=False)
    assert compact["id"] == research_id and compact["stage"] == "code_ready"
    assert set(compact["artifacts"]) >= {"context", "plan", "bundle", "literature"}
    assert not set(compact) & {"schemas", "source_context", "instructions", "plan", "literature", "analysis", "execution", "active_handle", "material_manifest"}
    assert set(service.status(research_id)) >= {"schemas", "source_context", "instructions", "plan", "literature"}


def test_retained_metadata_only_literature_never_becomes_usable_on_repeat(setup):
    service, runner, research_id = setup
    service.submit_plan(research_id, protocol())
    def metadata_only(*args, **kwargs):
        result = collect(*args, **kwargs)
        result["sources"][0]["scope"] = "metadata_only"
        result["sources"][0]["excerpts"] = []
        return result
    service.collector = metadata_only
    for _ in range(2):
        with pytest.raises(WorkflowError, match="metadata|Metadata"):
            service.collect_literature(research_id)
    assert "literature" in service.status(research_id)["artifacts"]


def test_partial_literature_completes_missing_query_without_changing_retained_bytes(setup):
    service, runner, research_id = setup
    plan = protocol()
    plan["literature_queries"] = ["first frozen query", "second frozen query"]
    service.submit_plan(research_id, plan)
    calls = []

    def partial_then_complete(queries, root, *, limit, cancel):
        calls.append((queries, limit))
        if len(calls) == 1:
            evidence = collect(queries[:1], root, limit=limit, cancel=cancel)
            evidence["sources"] = [dict(evidence["sources"][0], id=f"retained-source-{index}") for index in range(6)]
            return evidence
        assert queries == ["second frozen query"] and limit == 0
        path = Path(root) / "literature" / "second-query-search.json"
        write_json(path, {"status": "ok", "message": {"items": []}})
        return {"sources": [], "searches": [{"query": queries[0], "provider": "Crossref", "status": "succeeded",
                    "attempted": True, "resolved_ids": [], "raw_path": "literature/second-query-search.json",
                    "sha256": digest_file(path)}], "warnings": []}

    service.collector = partial_then_complete
    with pytest.raises(WorkflowError) as first:
        service.collect_literature(research_id)
    assert first.value.code == "LITERATURE_QUERIES_INCOMPLETE"
    original = service.artifact_path(research_id, "literature")
    original_bytes = original.read_bytes()
    original_digest = digest_file(original)
    retained = json.loads(original_bytes)
    result = service.collect_literature(research_id)
    current = service.artifact_path(research_id, "literature")
    assert current != original and original.read_bytes() == original_bytes
    assert result["literature"]["sources"] == retained["sources"]
    assert result["literature"]["searches"][:1] == retained["searches"]
    assert len(result["literature"]["sources"]) == 6 and len(result["literature"]["searches"]) == 2
    history = result["literature"]["history"][0]
    assert history["sha256"] == original_digest
    assert service.artifact_path(research_id, history["artifact_id"]) == original
    assert result["artifacts"][history["artifact_id"]]["sha256"] == original_digest
    assert "literature-search-1" in result["artifacts"]
    service.collect_literature(research_id)
    assert len(calls) == 2 and runner.calls == 0
    assert current.read_bytes() == service.artifact_path(research_id, "literature").read_bytes()


def test_failed_attempt_completes_query_but_unattempted_error_remains_missing(setup):
    service, runner, research_id = setup
    plan = protocol()
    plan["literature_queries"] = ["first frozen query", "second frozen query"]
    service.submit_plan(research_id, plan)
    calls = []

    def collector(queries, root, *, limit, cancel):
        calls.append(queries)
        if len(calls) == 1:
            evidence = collect(queries[:1], root, limit=limit, cancel=cancel)
            evidence["searches"].append({"query": queries[1], "status": "failed", "attempted": False, "error": "OSError"})
            return evidence
        assert queries == ["second frozen query"] and limit == 5
        return {"sources": [], "searches": [{"query": queries[0], "status": "failed", "attempted": True,
                                                "error": "HTTPStatusError"}], "warnings": ["Observed provider failure"]}

    service.collector = collector
    with pytest.raises(WorkflowError) as initial:
        service.collect_literature(research_id)
    assert initial.value.code == "LITERATURE_QUERIES_INCOMPLETE"
    prior = service.artifact_path(research_id, "literature").read_bytes()
    result = service.collect_literature(research_id)
    assert result["literature"]["searches"][:2] == json.loads(prior)["searches"]
    assert result["literature"]["searches"][-1]["error"] == "HTTPStatusError"
    assert result["literature"]["sources"] == json.loads(prior)["sources"]
    service.collect_literature(research_id)
    assert len(calls) == 2 and runner.calls == 0


def test_explicit_research_id_does_not_change_global_workspace_selection(setup):
    service, runner, research_id = setup
    pointer = service.home / "current.json"
    assert not pointer.exists()
    write_json(pointer, {"workspace": "existing-legacy-selection"})
    original = pointer.read_bytes()
    service.create(str(service.home.parent / "input"), "Validate another bounded controlled transformation study.")
    assert pointer.read_bytes() == original


def test_recovered_unconfirmed_worker_cannot_be_hidden_by_shutdown(setup):
    service, runner, research_id = setup
    prepare(service, research_id)
    service.start_experiment(research_id)
    assert finished(service, research_id)["stage"] == "analyzed"
    service.close()
    ws = Workspace(service.home / "workflows" / research_id)
    record = ws.get("workflow", research_id, Workflow)
    record.status, record.code = "blocked", "CLEANUP_UNCONFIRMED"
    record.active_handle = {"kind": "fixture", "pid": 123}
    ws.save("workflow", record)
    runner.cleanable = False
    recovered = WorkflowService(service.home, runner=runner, collector=collect)
    assert recovered.status(research_id, include_materials=False)["code"] == "CLEANUP_UNCONFIRMED"
    with pytest.raises(WorkflowError, match="cleanup"):
        recovered.close()
    assert ws.get("workflow", research_id, Workflow).active_handle["pid"] == 123
    runner.cleanable = True
    recovered.close()
    record = ws.get("workflow", research_id, Workflow)
    assert not record.active_handle and record.stage == "analyzed"


def test_material_reading_returns_declared_source_and_current_experiment(setup):
    service, runner, research_id = setup
    source = service.read_material(research_id, "source", "transform.js", limit=10)
    assert source["text"] == "export fun" and source["offset"] == 0 and source["next_offset"] == 10
    assert source["is_untrusted_data"] is True
    remainder = service.read_material(research_id, "source", "transform.js", offset=10, limit=32000)
    text = source["text"] + remainder["text"]
    assert hashlib.sha256(text.encode()).hexdigest() == source["sha256"] == remainder["sha256"]
    assert len(text) == source["total_chars"] and remainder["next_offset"] is None
    prepare(service, research_id)
    code = service.read_material(research_id, "experiment", "experiment.mjs")
    assert code["text"].replace("\r\n", "\n") == BUNDLE["files"][0]["content"]
    materials = service.status(research_id)["material_manifest"]
    assert materials["source"][0]["name"] == "transform.js"
    assert materials["experiment"][0]["name"] == "experiment.mjs"
    assert materials["experiment"][0]["sha256"] == code["sha256"]


def test_reviewer_can_read_bounded_hash_verified_runtime_and_numbered_code_review(setup):
    service, runner, research_id = setup
    prepare(service, research_id)
    ws = Workspace(service.root / research_id)
    record = ws.get("workflow", research_id, Workflow)
    path = ws.path("research/runtime-manifest.json")
    write_json(path, {"compiled_source": "trusted transformer fixture " * 200, "transformer_version": "fixture"})
    record.artifacts["runtime-manifest"] = FrozenArtifact(path=path.relative_to(ws.root).as_posix(),
                                                          sha256=digest_file(path), size=path.stat().st_size)
    ws.save("workflow", record)
    for name in ("runtime-manifest", "code-review-1"):
        expected = service.artifact_path(research_id, name)
        page = service.read_material(research_id, "evidence", name, limit=19)
        assert len(page["text"]) == 19 and page["sha256"] == digest_file(expected) and page["next_offset"] == 19
        assert page["is_untrusted_data"] is True
        entry = next(item for item in service.status(research_id)["material_manifest"]["evidence"] if item["name"] == name)
        assert entry["sha256"] == page["sha256"] and entry["size"] == expected.stat().st_size
    assert runner.calls == 0
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(WorkflowError) as changed:
        service.read_material(research_id, "evidence", "runtime-manifest")
    assert changed.value.code == "ARTIFACT_CHANGED"


@pytest.mark.parametrize("name", ["code-review", "code-review-0", "code-review-01", "code-review-1/../plan", "code-review--1"])
def test_numbered_code_review_allowlist_rejects_other_keys(setup, name):
    service, runner, research_id = setup
    prepare(service, research_id)
    with pytest.raises(WorkflowError) as rejected:
        service.read_material(research_id, "evidence", name)
    assert rejected.value.code == "MATERIAL_NOT_DECLARED"


def test_material_reading_exposes_actual_runner_raw_evidence_for_fresh_review(setup):
    service, runner, research_id = setup
    prepare(service, research_id)
    service.start_experiment(research_id)
    assert finished(service, research_id)["stage"] == "analyzed"
    raw = service.read_material(research_id, "evidence", "observations")
    assert json.loads(raw["text"]) == runner.outputs
    assert raw["sha256"] == service.status(research_id)["artifacts"]["observations"]["sha256"]
    service.submit_manuscript(research_id, manuscript(), REVIEW)
    assert service.read_material(research_id, "evidence", "manuscript")["text"].startswith("# ")
    canonical = service.read_material(research_id, "evidence", "canonical")
    fragments = [canonical["text"]]
    original_hash = canonical["sha256"]
    while canonical["next_offset"] is not None:
        canonical = service.read_material(research_id, "evidence", "canonical", offset=canonical["next_offset"])
        assert canonical["sha256"] == original_hash
        fragments.append(canonical["text"])
    assert json.loads("".join(fragments))["title"] == manuscript()["title"]


@pytest.mark.parametrize("area,name", [
    ("source", "../records.sqlite3"), ("source", "C:/Users/private.txt"), ("source", "/private.txt"),
    ("source", ".env"), ("source", "absent.py"), ("experiment", "../protocol.json"),
    ("experiment", "bundle.json"), ("experiment", "review.json"),
    ("evidence", "execution"), ("evidence", "active_handle"), ("evidence", "../../records.sqlite3"),
    ("other", "transform.js"),
])
def test_material_reading_refuses_host_paths_and_undeclared_files(setup, area, name):
    service, runner, research_id = setup
    prepare(service, research_id)
    with pytest.raises(ValueError):
        service.read_material(research_id, area, name)


@pytest.mark.parametrize("offset,limit", [(-1, 10), (True, 10), (0, False), (0, 0), (0, 32001), (0.5, 10), (0, "10")])
def test_material_paging_has_exact_bounded_integer_parameters(setup, offset, limit):
    service, runner, research_id = setup
    with pytest.raises(ValueError, match="paging"):
        service.read_material(research_id, "source", "transform.js", offset=offset, limit=limit)


@pytest.mark.parametrize("data", [b"\xff\xfe", b"text\x00binary"])
def test_material_reader_refuses_binary_files(setup, data):
    service, runner, research_id = setup
    source = service.home.parent / "binary-input"
    source.mkdir()
    (source / "asset.bin").write_bytes(data)
    created = service.create(str(source), "Inspect the declared binary fixture without reading private host files.")
    with pytest.raises(WorkflowError, match="UTF-8|Binary"):
        service.read_material(created["id"], "source", "asset.bin")


def test_material_reader_checks_all_frozen_artifacts_before_reading(setup):
    service, runner, research_id = setup
    prepare(service, research_id)
    protocol_file = service.artifact_path(research_id, "plan")
    protocol_file.write_text("{}", encoding="utf-8")
    with pytest.raises(WorkflowError, match="changed"):
        service.read_material(research_id, "source", "transform.js")


def test_material_paging_counts_unicode_characters_not_bytes(setup):
    service, runner, research_id = setup
    source = service.home.parent / "unicode-input"
    source.mkdir()
    text = "한글🙂readable"
    (source / "note.txt").write_text(text, encoding="utf-8")
    created = service.create(str(source), "Inspect a declared Unicode text fixture with bounded character pages.")
    page = service.read_material(created["id"], "source", "note.txt", offset=1, limit=2)
    assert page["text"] == "글🙂" and page["next_offset"] == 3 and page["total_chars"] == len(text)
    assert page["sha256"] == hashlib.sha256(text.encode()).hexdigest()


def test_material_unicode_paging_preserves_characters_across_stream_chunks(setup):
    service, runner, research_id = setup
    source = service.home.parent / "chunked-unicode-input"
    source.mkdir()
    text = "a" * 65535 + "한글🙂" + "tail" * 10
    (source / "note.txt").write_text(text, encoding="utf-8")
    created = service.create(str(source), "Inspect bounded Unicode material across decoder chunk boundaries.")
    page = service.read_material(created["id"], "source", "note.txt", offset=65534, limit=4)
    assert page["text"] == "a한글🙂" and page["next_offset"] == 65538
    assert page["total_chars"] == len(text) and page["sha256"] == hashlib.sha256(text.encode()).hexdigest()

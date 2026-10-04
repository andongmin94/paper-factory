"""Native host submissions with synthetic runners; no inference or network."""

import base64
import copy
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import zipfile

import pytest

from paper_factory.autonomous import science
from paper_factory.workflow import WorkflowError, WorkflowService
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import Workspace, digest_file, write_json


def protocol():
    return {
        "feasible": True, "reason": "A production callable supports controlled synthetic contract checks.",
        "title": "Controlled transformation contract study for native workflow validation",
        "question": "How does the selected production transformation preserve protected fixture values?",
        "runtime": "python", "source_files": ["transform.py"], "production_entrypoint": "transform.py:transform",
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
BUNDLE = {"runtime": "python", "entrypoint": "experiment.py", "files": [
    {"path": "experiment.py", "content": "# Synthetic runner fixture; not executed by FixtureRunner.\npass\n"}],
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
    return {"sources": [source], "cancelled": False, "simulation": True}


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
        return {"ready": True, "simulation": True, "runtimes": ["python", "node"], "dependencies": []}

    def stop(self, handle):
        assert handle["kind"] == "fixture"
        if self.release:
            self.release.set()
        return self.cleanable

    def run(self, source_dir, bundle_dir, output_dir, *, runtime, entrypoint, production_entrypoint, timeout_seconds, cancel, on_handle):
        assert runtime == "python" and timeout_seconds == 300
        assert production_entrypoint == "transform.py:transform"
        assert Path(source_dir, "transform.py").is_file() and Path(bundle_dir, entrypoint).is_file()
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
                "production_calls": [{"path": "transform.py", "function": "transform", "calls": 6}] if self.production_calls else []}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "matplotlib"))
    source = tmp_path / "input"
    source.mkdir()
    (source / "transform.py").write_text("def transform(values):\n    return list(values)\n", encoding="utf-8")
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
    for operation in (lambda: service.start_experiment(research_id), lambda: service.submit_plan(research_id, protocol()),
                      lambda: service.submit_code(research_id, BUNDLE, REVIEW)):
        with pytest.raises(WorkflowError, match="stage"):
            operation()
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
        path = service.home / "workflows" / research_id / "source" / "transform.py"
    elif target in {"generated", "extra"}:
        path = service.artifact_path(research_id, "bundle").parent / "experiment.py"
        if target == "extra":
            path = path.with_name("injected.py")
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
        with pytest.raises(WorkflowError, match="terminal"):
            operation()
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


def test_code_bundle_cannot_supply_measurements_or_escape_its_directory(setup):
    service, runner, research_id = setup
    service.submit_plan(research_id, protocol())
    forged = copy.deepcopy(BUNDLE)
    forged["observations"] = observations()
    with pytest.raises(ValueError):
        service.submit_code(research_id, forged, REVIEW)
    forged = copy.deepcopy(BUNDLE)
    forged["files"][0]["path"] = forged["entrypoint"] = "../escape.py"
    with pytest.raises(ValueError, match="safe relative"):
        service.submit_code(research_id, forged, REVIEW)
    assert runner.calls == 0


def test_start_is_immediate_and_cancellation_stops_owned_execution(setup):
    service, runner, research_id = setup
    runner.release = threading.Event()
    prepare(service, research_id)
    service.start_experiment(research_id)
    assert runner.entered.wait(2)
    with pytest.raises(WorkflowError):
        service.start_experiment(research_id)
    cancelled = service.cancel(research_id)
    assert cancelled["cancellation_requested"]
    result = finished(service, research_id)
    assert result["status"] == "cancelled" and runner.calls == 1


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
    with pytest.raises(WorkflowError, match="cleanup"):
        service.start_experiment(research_id)


def test_native_export_reopens_files_and_recomputes_observations(setup):
    import pypandoc
    service, runner, research_id = setup
    prepare(service, research_id)
    service.start_experiment(research_id)
    assert finished(service, research_id)["stage"] == "analyzed"
    service.submit_manuscript(research_id, manuscript(), REVIEW)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("PYPANDOC_PANDOC", pypandoc.get_pandoc_path())
        result = service.export(research_id)
    assert result["status"] == "completed" and result["stage"] == "exported"
    assert set(result["artifacts"]) >= {"export-md", "export-pdf", "export-docx", "export-tex", "validation", "reproducibility"}
    validation = json.loads(service.artifact_path(research_id, "validation").read_text())
    assert validation["passed"] is True
    with zipfile.ZipFile(service.artifact_path(research_id, "reproducibility")) as archive:
        assert archive.testzip() is None
        assert {"source/transform.py", "generated/experiment.py", "analysis/analysis.py", "observations.json"} <= set(archive.namelist())
        images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", archive.read("paper.md").decode())
        assert images
        inventory = json.loads(archive.read("inventory.json"))
        for image in images:
            assert image in archive.namelist() and image in inventory
            assert "analysis/" + image in archive.namelist()
            assert archive.read(image) == archive.read("analysis/" + image)
    assert runner.calls == 1


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
        with pytest.raises(WorkflowError, match="stage"):
            recovered.start_experiment(research_id)
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
        with pytest.raises(WorkflowError, match="terminal"):
            recovered.submit_code(research_id, BUNDLE, REVIEW)
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


def test_contract_feedback_supports_repairs_without_exposing_private_paths(setup):
    service, runner, research_id = setup
    runner.outputs["observations"].pop()
    prepare(service, research_id)
    service.start_experiment(research_id)
    result = finished(service, research_id)
    assert "row" in result["diagnostics"]["validation"].lower()
    assert result["diagnostics"]["validation"] in result["instructions"]
    runner.outputs = observations()
    service.submit_code(research_id, BUNDLE, REVIEW)
    service.start_experiment(research_id)
    assert finished(service, research_id)["stage"] == "analyzed"


def test_contract_instructions_cover_measurements_and_manuscript_requirements(setup):
    service, runner, research_id = setup
    created = service.status(research_id)
    assert "ResearchPlan" in created["instructions"]
    planned = service.submit_plan(research_id, protocol())
    assert "observations.json" in planned["instructions"]
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
    source = service.read_material(research_id, "source", "transform.py", limit=10)
    assert source["text"] == "def transf" and source["offset"] == 0 and source["next_offset"] == 10
    assert source["is_untrusted_data"] is True
    remainder = service.read_material(research_id, "source", "transform.py", offset=10, limit=32000)
    text = source["text"] + remainder["text"]
    assert hashlib.sha256(text.encode()).hexdigest() == source["sha256"] == remainder["sha256"]
    assert len(text) == source["total_chars"] and remainder["next_offset"] is None
    prepare(service, research_id)
    code = service.read_material(research_id, "experiment", "experiment.py")
    assert code["text"].replace("\r\n", "\n") == BUNDLE["files"][0]["content"]
    materials = service.status(research_id)["material_manifest"]
    assert materials["source"][0]["name"] == "transform.py"
    assert materials["experiment"][0]["name"] == "experiment.py"
    assert materials["experiment"][0]["sha256"] == code["sha256"]


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
    ("other", "transform.py"),
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
        service.read_material(research_id, "source", "transform.py", offset=offset, limit=limit)


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
        service.read_material(research_id, "source", "transform.py")


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

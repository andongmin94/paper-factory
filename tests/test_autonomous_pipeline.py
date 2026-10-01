"""Synthetic model/runner/literature fixtures; real trusted analysis and exports.

These tests verify orchestration, not live inference, container isolation,
production execution or a real scientific paper. No credentials are needed.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import zipfile

import pytest

from paper_factory.author import AuthorProfile
from paper_factory.autonomous import literature, pipeline, science
from paper_factory.autonomous.models import PipelineRun, ResearchPlan
from paper_factory.autonomous.provider import CodexProvider, ProviderBlocked
from paper_factory.project import ingest
from paper_factory.workspace import digest_file, write_json


def protocol():
    return {
        "feasible": True, "reason": "Synthetic callable fixture supports controlled orchestration checks.",
        "title": "Simulated controlled transformation study for pipeline validation",
        "question": "How does the selected production transformation preserve protected fixture values?",
        "runtime": "python", "source_files": ["transform.py"], "production_entrypoint": "transform.py:transform",
        "dependencies": [], "conditions": ["production", "ablation"],
        "metrics": [{"name": "error", "unit": "events", "description": "Independently detected transformation contract violations."}],
        "comparator": "An explicit guard-removal ablation retains the other transformation rules.",
        "independent_oracle": "Fixture annotations define exact expected values independently of the comparator.",
        "sampling_unit": "An independently seeded input with its own protected annotations.",
        "sample_size": 3, "seeds": [11, 37], "parameters": {"fixture_size": 12, "execution_instrumentation": "Synthetic controller trace receipt; no actual production execution"},
        "procedure": ["Generate seeded inputs and independent annotations.", "Invoke unchanged source and explicit comparator.",
                      "Measure paired errors and inspect positive and negative controls."],
        "analysis_method": "Descriptive statistics with differences paired by seed and fixture unit.",
        "limitations": ["Synthetic observations do not represent natural input populations.",
                        "This test does not demonstrate live model or container execution."],
        "literature_queries": ["independent software testing oracle"],
    }


def observations():
    return {"observations": [
        {"unit_id": f"case-{index}", "seed": seed, "condition": condition, "metric": "error",
         "value": 0 if condition == "production" else index + 1}
        for seed in (11, 37) for index in range(3) for condition in ("production", "ablation")
    ], "controls": [
        {"name": "positive control", "passed": True, "details": "Synthetic input agrees with its independently annotated expected result."},
        {"name": "negative control", "passed": True, "details": "An intentional synthetic deletion is detected by the fixture oracle."},
    ]}


def manuscript():
    # Repetition exercises prose-size validation; this is not a research paper.
    paragraph = (
        "This synthetic manuscript fixture checks the transfer of a frozen software protocol into an evidence linked document. "
        "Its observations are simulated inputs for orchestration validation and cannot establish production correctness. "
        "The comparison separates a baseline condition from an explicitly declared ablation while preserving paired sampling units. "
        "The trusted analyzer determines descriptive statistics from retained raw records rather than accepting model supplied measurements. "
        "Source hashes and independent reproduction protect the relationship between these records and the displayed numerical references. "
        "The fixture demonstrates document integrity checks and offers no evidence of scientific novelty or real model inference. "
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
            text += "The protocol sample size is {{parameter:sample_size}} units per seed."
            text += " Recorded instrumentation: {{parameter:setting.execution_instrumentation}}."
        elif heading == "Related Work":
            text += "The synthetic passage describes independently defined expected outcomes {{citation:fixture-oracle}}."
        sections.append({"heading": heading, "text": text})
    return {"title": "Simulated controlled transformation study for pipeline validation", "sections": sections}


class FixtureProvider:
    def __init__(self, *, ready=True, authentication="chatgpt"):
        self.availability = {"ready": ready, "authentication": authentication, "simulation": True}
        self.calls, self.prompts = [], []
        self.plan = protocol()
        self.reviews = [{"accepted": True, "issues": [], "checks": []}]
        self.block_write = False
        self.on_generate = None

    def status(self):
        return copy.deepcopy(self.availability)

    def generate(self, prompt, schema, call_dir, *, cancel, timeout_seconds, model, on_handle=None):
        label = schema["title"]
        self.calls.append(label)
        self.prompts.append(prompt)
        if on_handle:
            on_handle({"kind": "fixture", "simulation": True})
        write_json(Path(call_dir) / "receipt.json", {"provider": "test_fixture", "simulation": True,
                   "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "status": "simulated"})
        if self.on_generate:
            self.on_generate(label)
        if label == "ResearchPlan":
            return copy.deepcopy(self.plan)
        if label == "CodeBundle":
            return {"runtime": "python", "entrypoint": "experiment.py", "files": [
                {"path": "experiment.py", "content": "# Synthetic fixture; FixtureRunner never executes this file.\npass\n"}
            ], "explanation": "Simulated code bundle for checkpoint and analysis/export wiring validation."}
        if label == "ScientificReview":
            index = self.calls.count("ScientificReview") - 1
            return copy.deepcopy(self.reviews[min(index, len(self.reviews) - 1)])
        if label == "ManuscriptDraft":
            if self.block_write:
                raise ProviderBlocked("NETWORK_ERROR", "Synthetic model outage at manuscript generation")
            return manuscript()
        raise AssertionError(f"Unexpected fixture model schema: {label}")

    def substantive_calls(self):
        return [label for label in self.calls if label != "ScientificReview"]


class FixtureRunner:
    def __init__(self, *, ready=True, outputs=None, production_calls=True):
        self.ready = ready
        self.outputs = outputs or [observations()]
        self.production_calls = production_calls
        self.calls = 0
        self.on_run = None

    def status(self):
        return {"ready": self.ready, "simulation": True, "reason": None if self.ready else "Synthetic missing isolation image",
                "image_digest": "sha256:" + "1" * 64, "runtimes": ["python", "node"], "dependencies": []}

    def run(self, source_dir, bundle_dir, output_dir, *, runtime, entrypoint, timeout_seconds, cancel, on_handle=None):
        self.calls += 1
        assert Path(source_dir, "transform.py").is_file() and Path(bundle_dir, entrypoint).is_file()
        assert runtime == "python" and timeout_seconds > 0
        if on_handle:
            on_handle({"kind": "fixture", "simulation": True})
        write_json(Path(output_dir) / "observations.json", copy.deepcopy(self.outputs[min(self.calls - 1, len(self.outputs) - 1)]))
        if self.on_run:
            self.on_run()
        return {"status": "succeeded", "simulation": True, "image_digest": "sha256:" + "1" * 64,
                "production_calls": [{"path": "transform.py", "function": "transform", "calls": 6}] if self.production_calls else [],
                "stdout": "synthetic runner fixture", "stderr": "", "exit_code": 0}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_HOME", str(tmp_path / "app-home"))
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "matplotlib"))
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    for name in AuthorProfile.model_fields:
        monkeypatch.delenv("PF_AUTHOR_" + name.upper(), raising=False)
    monkeypatch.delenv("PF_AUTHOR_PROFILE_JSON", raising=False)
    monkeypatch.setenv("PF_AUTHOR_DISPLAY_NAME", "Fixture Author")
    monkeypatch.setenv("PF_AUTHOR_EMAIL", "fixture@example.org")
    monkeypatch.setenv("PF_AUTHOR_AFFILIATION", "Test Institution")
    source = tmp_path / "source-input"
    source.mkdir()
    (source / "transform.py").write_text("def transform(values):\n    return list(values)\n", encoding="utf-8")
    return ingest(str(source), tmp_path / "workspace")


@pytest.fixture
def components(monkeypatch):
    retrieved = []
    scope = {"value": "abstract"}

    def collect(queries, root, *, limit, cancel):
        retrieved.append(list(queries))
        text = ("Synthetic passage: independent software test oracles define expected outcomes separately from the implementation. "
                "Controlled fixtures compare observed behavior with annotations and cannot establish population failure rates.")
        raw = Path(root) / "literature" / "fixture-source.json"
        metadata = raw.with_name("fixture-metadata.json")
        decoded = raw.with_suffix(".txt")
        write_json(raw, {"fixture": True, "reading_text": text})
        write_json(metadata, {"fixture": True, "title": "Synthetic oracle passage for pipeline tests"})
        decoded.write_text(text, encoding="utf-8")
        source = {"id": "fixture-oracle", "scope": scope["value"], "title": "Synthetic oracle passage for pipeline tests",
                  "authors": ["Fixture Author"], "simulation": True, "raw_path": "literature/fixture-source.json",
                  "sha256": digest_file(raw), "metadata_path": "literature/fixture-metadata.json", "metadata_sha256": digest_file(metadata),
                  "text_path": "literature/fixture-source.txt", "text_sha256": digest_file(decoded),
                  "excerpts": [text] if scope["value"] in {"abstract", "full_text"} else []}
        return {"sources": [source], "cancelled": False, "simulation": True}

    monkeypatch.setattr(literature, "collect", collect)
    return FixtureProvider(), FixtureRunner(), retrieved, scope


def launch(workspace, components, *, budget=None):
    provider, runner, _, _ = components
    created = pipeline.create(workspace, "Validate a bounded controlled transformation study.", budget=budget)
    return pipeline.run(workspace, created.id, provider=provider, runner=runner)


def blocked_at_write(workspace, components):
    components[0].block_write = True
    result = launch(workspace, components)
    assert result.status == "blocked" and result.code == "NETWORK_ERROR", result.message
    assert result.stage == "write" and "analysis" in result.artifacts
    return result


def native_exports_available(pandoc, monkeypatch):
    monkeypatch.setenv("PYPANDOC_PANDOC", pandoc)
    for module in ("typst", "pypdf", "docx"):
        pytest.importorskip(module)


@pytest.mark.parametrize("authentication,ready,code", [("chatgpt", False, "CODEX_AUTH_REQUIRED"),
                                                       ("api_key", True, "SUBSCRIPTION_AUTH_REQUIRED"),
                                                       ("api_key", False, "SUBSCRIPTION_AUTH_REQUIRED")])
def test_no_authentication_or_api_key_cannot_start_subscription_study(workspace, components, authentication, ready, code):
    provider, runner, retrieved, _ = components
    provider.availability.update(authentication=authentication, ready=ready)
    result = launch(workspace, components)
    assert result.status == "blocked" and result.code == code
    assert not provider.calls and runner.calls == 0 and not retrieved


def test_resume_after_assessment_rejects_changed_api_key_authentication(workspace, components, monkeypatch):
    def interrupt_code_generation(label):
        if label == "CodeBundle":
            raise ProviderBlocked("NETWORK_ERROR", "Synthetic interruption after subscription assessment")

    components[0].on_generate = interrupt_code_generation
    interrupted = launch(workspace, components)
    assert interrupted.stage == "generate" and interrupted.code == "NETWORK_ERROR"
    plan_digest = interrupted.artifacts["plan"].sha256
    provider = CodexProvider()
    monkeypatch.setattr(provider, "_status", lambda environment: {
        "executable_available": True, "authentication": "api_key", "ready": False,
        "cli_version": "test", "capabilities_supported": True, "missing_capabilities": [],
    })
    monkeypatch.setattr(provider, "_execute", lambda *args, **kwargs: pytest.fail("API-authenticated model must not dispatch"))
    pipeline.resume(workspace, interrupted.id)
    resumed = pipeline.run(workspace, interrupted.id, provider=provider, runner=components[1])
    assert resumed.status == "blocked" and resumed.code == "SUBSCRIPTION_AUTH_REQUIRED"
    assert resumed.stage == "generate" and resumed.artifacts["plan"].sha256 == plan_digest
    assert components[1].calls == 0


def test_missing_isolation_has_no_host_fallback(workspace, components):
    components[1].ready = False
    result = launch(workspace, components)
    assert result.status == "blocked" and result.code == "ISOLATION_UNAVAILABLE"
    assert not components[0].calls and components[1].calls == 0


def test_model_budget_counts_calls_and_is_not_reset_by_resume(workspace, components):
    result = launch(workspace, components, budget={"max_model_calls": 1})
    assert result.status == "blocked" and result.code == "MODEL_BUDGET_EXHAUSTED"
    assert result.model_calls == 1 and result.stage == "generate"
    plan_hash = result.artifacts["plan"].sha256
    pipeline.resume(workspace, result.id)
    retried = pipeline.run(workspace, result.id, provider=components[0], runner=components[1])
    assert retried.code == "MODEL_BUDGET_EXHAUSTED" and retried.model_calls == 1
    assert retried.artifacts["plan"].sha256 == plan_hash and components[1].calls == 0


def test_metadata_only_cannot_support_related_work(workspace, components):
    components[3]["value"] = "metadata_only"
    result = launch(workspace, components)
    assert result.status == "blocked" and result.code == "LITERATURE_EVIDENCE_INSUFFICIENT"
    assert result.stage == "literature" and components[1].calls == 0
    assert components[0].calls == ["ResearchPlan"]
    assert (workspace.root / "autonomous" / result.id / "literature" / "fixture-source.json").is_file()


def test_false_control_preserves_evidence_without_favorable_regeneration(workspace, components):
    failed = observations()
    failed["controls"][0]["passed"] = False
    components[1].outputs = [failed, observations()]
    result = launch(workspace, components, budget={"repair_attempts": 3})
    assert result.status == "blocked" and result.code == "CONTROL_FAILED"
    assert result.code_attempt == 1 and components[1].calls == 1
    assert components[0].substantive_calls() == ["ResearchPlan", "CodeBundle"]
    assert json.loads(workspace.path(result.artifacts["observations"].path).read_text()) == failed
    assert "manuscript" not in result.artifacts


def test_rejected_code_review_blocks_execution_with_no_repair_budget(workspace, components):
    components[0].reviews = [{"accepted": False, "issues": ["Synthetic review found a missing independent oracle."], "checks": []}]
    result = launch(workspace, components, budget={"repair_attempts": 0})
    assert result.status == "blocked" and result.code == "EXPERIMENT_REPAIRS_EXHAUSTED"
    assert components[1].calls == 0 and "observations" not in result.artifacts
    assert components[0].calls.count("ScientificReview") == 1


def test_rejected_manuscript_review_does_not_regenerate_successful_experiment(workspace, components):
    components[0].reviews = [{"accepted": True, "issues": [], "checks": []},
                             {"accepted": False, "issues": ["Synthetic interpretation exceeds its inspected reading passage."], "checks": []}]
    result = launch(workspace, components, budget={"repair_attempts": 0})
    assert result.status == "blocked" and result.code == "MANUSCRIPT_EVIDENCE_INVALID"
    assert components[1].calls == 1 and "analysis" in result.artifacts
    assert "manuscript" not in result.artifacts


def test_missing_instrumented_production_execution_blocks_replacement_study(workspace, components):
    components[1].production_calls = False
    result = launch(workspace, components)
    assert result.status == "blocked" and result.code == "PRODUCTION_EXECUTION_UNVERIFIED"
    assert "observations" in result.artifacts and "analysis" not in result.artifacts
    assert result.code_attempt == 1 and components[1].calls == 1


def test_invalid_observation_shape_uses_bounded_repairs_with_frozen_protocol(workspace, components):
    components[1].outputs = [{"unrecognized": []}]
    result = launch(workspace, components, budget={"repair_attempts": 1})
    assert result.status == "blocked" and result.code == "EXPERIMENT_REPAIRS_EXHAUSTED"
    assert components[1].calls == 2 and result.code_attempt == 2
    assert components[0].substantive_calls() == ["ResearchPlan", "CodeBundle", "CodeBundle"]
    protocol_hash = result.artifacts["plan"].sha256
    receipts = [item for key, item in result.artifacts.items() if key.startswith("execution-")]
    assert len(receipts) == 2
    for item in receipts:
        assert json.loads(workspace.path(item.path).read_text())["protocol_sha256"] == protocol_hash
    feedback = json.loads((workspace.root / "autonomous" / result.id / "repair-feedback.json").read_text())
    assert feedback["protocol_sha256"] == protocol_hash and "not" in feedback["notice"].lower()


def test_completed_mock_wiring_reopens_native_exports_and_recomputes_raw_data(workspace, components, tmp_path, pandoc, monkeypatch):
    native_exports_available(pandoc, monkeypatch)
    components[3]["value"] = "full_text"
    result = launch(workspace, components)
    assert result.status == "completed", (result.code, result.message)
    assert result.stage == "done" and result.model_calls == len(components[0].calls) and components[1].calls == 1
    assert pipeline.verify(workspace, result.id)["passed"]
    from docx import Document
    from pypdf import PdfReader
    assert len(PdfReader(workspace.path(result.artifacts["export-pdf"].path)).pages) > 0
    assert len(Document(workspace.path(result.artifacts["export-docx"].path)).paragraphs) > 10
    assert "\\begin{document}" in workspace.path(result.artifacts["export-tex"].path).read_text()
    raw = json.loads(workspace.path(result.artifacts["observations"].path).read_text())
    values = [row["value"] for row in raw["observations"] if row["condition"] == "ablation"]
    assert sum(values) / len(values) == 2
    analysis = json.loads(workspace.path(result.artifacts["analysis"].path).read_text())
    assert analysis["results"]["error.paired_2_minus_1.mean"]["value"] == 2
    assert "paired mean difference is 2 events" in workspace.path(result.artifacts["manuscript"].path).read_text()
    assert not any("fixture@example.org" in prompt for prompt in components[0].prompts)
    with zipfile.ZipFile(workspace.path(result.artifacts["reproducibility"].path)) as archive:
        assert archive.testzip() is None
        assert {"source/transform.py", "analysis/analysis.py"} <= set(archive.namelist())
        assert all(".env" not in name and "auth.json" not in name for name in archive.namelist())
        for name, entry in json.loads(archive.read("inventory.json")).items():
            content = archive.read(name)
            assert len(content) == entry["size"] and hashlib.sha256(content).hexdigest() == entry["sha256"]
        archive.extractall(tmp_path / "reproduction")
    rerun = subprocess.run([sys.executable, str(tmp_path / "reproduction" / "analysis" / "analysis.py")],
                           capture_output=True, text=True, timeout=20)
    assert rerun.returncode == 0, rerun.stderr
    reproduced = json.loads((tmp_path / "reproduction" / "analysis" / "analysis-reproduced.json").read_text())
    for key in ("results", "parameters", "controls", "protocol_digest", "observation_digest", "summaries", "paired_deltas"):
        assert reproduced[key] == analysis[key]
    canonical = json.loads(workspace.path(result.artifacts["canonical"].path).read_text())
    assert canonical["publication_status"] == "not_submitted" and canonical["scientific_review"] == "required"


def test_structural_repair_can_succeed_without_replanning(workspace, components, pandoc, monkeypatch):
    native_exports_available(pandoc, monkeypatch)
    components[1].outputs = [{"bad_shape": True}, observations()]
    result = launch(workspace, components, budget={"repair_attempts": 1})
    assert result.status == "completed", result.message
    assert result.code_attempt == 2 and components[1].calls == 2
    assert components[0].calls.count("ResearchPlan") == 1 and len(components[2]) == 1
    assert {"bundle-1", "bundle-2"} <= set(result.artifacts)
    assert len([key for key in result.artifacts if key.startswith("observations-")]) == 2


def test_cancel_resume_after_successful_execution_does_not_rerun_it(workspace, components, pandoc, monkeypatch):
    native_exports_available(pandoc, monkeypatch)
    provider, runner, _, _ = components
    created = pipeline.create(workspace, "Validate interruption after successful fixture execution.")
    runner.on_run = lambda: pipeline.cancel(workspace, created.id)
    stopped = pipeline.run(workspace, created.id, provider=provider, runner=runner)
    assert stopped.status == "cancelled" and stopped.stage == "analyze"
    assert "observations" in stopped.artifacts and runner.calls == 1
    observed_hash = stopped.artifacts["observations"].sha256
    runner.on_run = None
    pipeline.resume(workspace, created.id)
    finished = pipeline.run(workspace, created.id, provider=provider, runner=runner)
    assert finished.status == "completed", finished.message
    assert runner.calls == 1 and finished.artifacts["observations"].sha256 == observed_hash
    assert provider.substantive_calls() == ["ResearchPlan", "CodeBundle", "ManuscriptDraft"]


def test_restart_reconciliation_resumes_only_unfinished_manuscript(workspace, components, pandoc, monkeypatch):
    native_exports_available(pandoc, monkeypatch)
    stopped = blocked_at_write(workspace, components)
    stopped.status = "running"
    stopped.attempts[-1].status = "running"
    stopped.active_handle = {"kind": "fixture", "simulation": True}
    workspace.save("pipeline", stopped)
    reconciled = pipeline.status(workspace, stopped.id)
    assert reconciled["status"] == "paused" and reconciled["code"] == "INTERRUPTED"
    assert reconciled["attempts"][-1]["status"] == "interrupted"
    components[0].block_write = False
    pipeline.resume(workspace, stopped.id)
    completed = pipeline.run(workspace, stopped.id, provider=components[0], runner=components[1])
    assert completed.status == "completed", completed.message
    assert components[1].calls == 1 and components[0].calls.count("CodeBundle") == 1
    assert components[0].calls.count("ManuscriptDraft") == 2


@pytest.mark.parametrize("target,code", [("source", None), ("bundle", "CODE_CHANGED"), ("literature", "ARTIFACT_CHANGED")])
def test_resume_rejects_mutated_source_bundle_or_raw_literature(workspace, components, target, code):
    stopped = blocked_at_write(workspace, components)
    if target == "source":
        path = workspace.root / "source" / "transform.py"
    elif target == "bundle":
        path = workspace.path(stopped.artifacts["bundle"].path).parent / "experiment.py"
    else:
        path = workspace.path(stopped.artifacts["literature-0-raw_path"].path)
    path.chmod(0o600)
    path.write_bytes(path.read_bytes() + b"\nmutated fixture bytes")
    with pytest.raises(ValueError) as error:
        pipeline.resume(workspace, stopped.id)
    if code:
        assert error.value.code == code
    else:
        assert "Source snapshot was modified" in str(error.value)
    assert workspace.get("pipeline", stopped.id, PipelineRun).status == "blocked"


def test_concurrent_create_and_worker_calls_allow_one_project_job(workspace, components):
    barrier = threading.Barrier(2)

    def create():
        barrier.wait(timeout=5)
        try:
            return pipeline.create(workspace, "Validate the single active research job invariant.")
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(lambda _: create(), range(2)))
    assert sum(record is not None for record in records) == 1
    created = next(record for record in records if record is not None)
    reached, release = threading.Event(), threading.Event()

    def wait_in_plan(label):
        if label == "ResearchPlan":
            reached.set()
            assert release.wait(timeout=10)
            raise ProviderBlocked("NETWORK_ERROR", "Synthetic worker stop after lock verification")

    components[0].on_generate = wait_in_plan
    with ThreadPoolExecutor(max_workers=1) as pool:
        active = pool.submit(pipeline.run, workspace, created.id, provider=components[0], runner=components[1])
        try:
            assert reached.wait(timeout=5)
            assert pipeline.status(workspace, created.id)["status"] == "running"
            with pytest.raises(ValueError, match="already running"):
                pipeline.run(workspace, created.id, provider=components[0], runner=components[1])
        finally:
            release.set()
        assert active.result(timeout=10).status == "blocked"
    assert len(workspace.list("pipeline", PipelineRun)) == 1


def test_resume_does_not_queue_second_job_for_one_project(workspace, components):
    components[1].ready = False
    first = launch(workspace, components)
    assert first.status == "blocked"
    second = pipeline.create(workspace, "Another bounded empirical study awaits execution.")
    with pytest.raises(ValueError, match="queued|running|active"):
        pipeline.resume(workspace, first.id)
    assert workspace.get("pipeline", second.id, PipelineRun).status == "queued"
    assert workspace.get("pipeline", first.id, PipelineRun).status == "blocked"


def test_cancel_preserves_unconfirmed_worker_and_resume_requires_cleanup(workspace, components, monkeypatch):
    from paper_factory.autonomous import provider as provider_module
    created = pipeline.create(workspace, "Validate cancellation with an unconfirmed worker stop.")
    retained = {"kind": "codex", "pid": 12345, "pgid": 12345, "start_ticks": "synthetic"}

    def interrupted(prompt, schema, call_dir, *, on_handle, **kwargs):
        on_handle(retained.copy())
        pipeline.cancel(workspace, created.id)
        write_json(Path(call_dir) / "receipt.json", {"simulation": True, "code": "CLEANUP_UNCONFIRMED"})
        raise ProviderBlocked("CLEANUP_UNCONFIRMED", "Synthetic worker termination could not be confirmed")

    monkeypatch.setattr(components[0], "generate", interrupted)
    stopped = pipeline.run(workspace, created.id, provider=components[0], runner=components[1])
    assert stopped.status == "blocked" and stopped.code == "CLEANUP_UNCONFIRMED"
    assert stopped.cancellation_requested and stopped.active_handle == retained
    assert "model-call-1" in stopped.artifacts
    assert pipeline.cancel(workspace, created.id)["code"] == "CLEANUP_UNCONFIRMED"
    monkeypatch.setattr(provider_module.CodexProvider, "cleanup_handle", lambda self, handle: False)
    with pytest.raises(pipeline.PipelineBlocked) as error:
        pipeline.resume(workspace, created.id)
    assert error.value.code == "CLEANUP_UNCONFIRMED"
    assert workspace.get("pipeline", created.id, PipelineRun).active_handle == retained
    monkeypatch.setattr(provider_module.CodexProvider, "cleanup_handle", lambda self, handle: True)
    resumed = pipeline.resume(workspace, created.id)
    assert resumed.status == "queued" and not resumed.active_handle and not resumed.cancellation_requested


def test_provider_initialization_cleanup_identity_survives_undelivered_callback(workspace, components, monkeypatch):
    from paper_factory.autonomous import provider as provider_module
    retained = {"kind": "codex", "pid": 12345, "start_ticks": 67890,
                "job_name": "Local\\paper-factory-codex-" + "a" * 32}
    def initialization_failed(prompt, schema, call_dir, *, on_handle, **kwargs):
        # A worker started, but initialization failed before the normal handle
        # callback could deliver its capability to the pipeline checkpoint.
        write_json(Path(call_dir) / "receipt.json", {"simulation": True, "code": "CLEANUP_UNCONFIRMED",
                                                   "active_handle": retained})
        raise ProviderBlocked("CLEANUP_UNCONFIRMED", "Synthetic ownership initialization and cleanup failure",
                              active_handle=retained)
    monkeypatch.setattr(components[0], "generate", initialization_failed)
    result = launch(workspace, components)
    assert result.status == "blocked" and result.code == "CLEANUP_UNCONFIRMED"
    assert result.active_handle == retained
    assert workspace.get("pipeline", result.id, PipelineRun).active_handle == retained
    assert "model-call-1" in result.artifacts
    monkeypatch.setattr(provider_module.CodexProvider, "cleanup_handle", lambda self, handle: False)
    with pytest.raises(pipeline.PipelineBlocked, match="cleanup"):
        pipeline.resume(workspace, result.id)
    with pytest.raises(pipeline.PipelineBlocked, match="cleanup"):
        pipeline.create(workspace, "A second job cannot bypass unresolved cleanup.")
    monkeypatch.setattr(provider_module.CodexProvider, "cleanup_handle", lambda self, handle: handle == retained)
    resumed = pipeline.resume(workspace, result.id)
    assert resumed.status == "queued" and resumed.active_handle == {} and resumed.code is None


@pytest.mark.parametrize("status", ["blocked", "running"])
def test_cleanup_uncertainty_without_identity_never_resumes_or_creates_worker(workspace, monkeypatch, status):
    created = pipeline.create(workspace, "Validate an unresolved worker whose capability could not be retained.")
    created.status, created.code = status, "CLEANUP_UNCONFIRMED"
    created.active_handle = {}
    workspace.save("pipeline", created)
    monkeypatch.setattr(pipeline, "_cleanup_handle", lambda handle: pytest.fail("An empty identity cannot prove worker cleanup"))
    recovered = pipeline.recover(workspace, created.id)
    assert recovered.status == "blocked" and recovered.code == "CLEANUP_UNCONFIRMED"
    with pytest.raises(pipeline.PipelineBlocked, match="identity"):
        pipeline.resume(workspace, created.id)
    with pytest.raises(pipeline.PipelineBlocked, match="cleanup"):
        pipeline.create(workspace, "A new job must preserve the unresolved cleanup boundary.")
    assert pipeline.cancel(workspace, created.id)["code"] == "CLEANUP_UNCONFIRMED"


def test_unrecognized_cleanup_capability_cannot_be_treated_as_terminated():
    assert pipeline._cleanup_handle({"kind": "unrecognized", "job_name": "Local\\unowned"}) is False


def test_resuming_another_job_cannot_bypass_unresolved_worker_cleanup(workspace):
    stopped = pipeline.create(workspace, "A stopped research job can ordinarily resume.")
    stopped.status, stopped.code = "blocked", "NETWORK_ERROR"
    workspace.save("pipeline", stopped)
    unresolved = pipeline.create(workspace, "A worker whose cleanup is unresolved blocks this project.")
    unresolved.status, unresolved.code = "blocked", "CLEANUP_UNCONFIRMED"
    unresolved.active_handle = {"kind": "codex", "pid": 12345, "start_ticks": 67890}
    workspace.save("pipeline", unresolved)
    with pytest.raises(pipeline.PipelineBlocked, match="cleanup"):
        pipeline.resume(workspace, stopped.id)
    assert workspace.get("pipeline", stopped.id, PipelineRun).status == "blocked"
    assert workspace.get("pipeline", unresolved.id, PipelineRun).active_handle == unresolved.active_handle


def test_recovery_preserves_handle_until_cleanup_is_confirmed(workspace, monkeypatch):
    from paper_factory.autonomous import provider as provider_module
    created = pipeline.create(workspace, "Validate recovery of a stopped scheduler worker.")
    created.status = "running"
    created.active_handle = {"kind": "codex", "pid": 12345, "start_ticks": "synthetic"}
    workspace.save("pipeline", created)
    monkeypatch.setattr(provider_module.CodexProvider, "cleanup_handle", lambda self, handle: False)
    recovered = pipeline.recover(workspace, created.id)
    assert recovered.status == "blocked" and recovered.code == "CLEANUP_UNCONFIRMED"
    assert recovered.active_handle == created.active_handle


def test_execution_cleanup_failure_blocks_and_retains_handle(workspace, components, monkeypatch):
    runner = components[1]
    original = runner.run
    retained = {"kind": "container", "container_id": "a" * 64,
                "container_name": "paper-factory-research-" + "b" * 32}
    def execute(*args, **kwargs):
        receipt = original(*args, **kwargs)
        return {**receipt, "status": "blocked", "code": "CLEANUP_UNCONFIRMED",
                "error": "Synthetic Docker removal timeout", "active_handle": retained}
    monkeypatch.setattr(runner, "run", execute)
    result = launch(workspace, components)
    assert result.status == "blocked" and result.code == "CLEANUP_UNCONFIRMED"
    assert result.active_handle == retained and result.stage == "execute"
    assert "execution" in result.artifacts and "analysis" not in result.artifacts
    assert runner.calls == 1


def test_generation_resume_preserves_partial_attempt_and_uses_fresh_code(workspace, components):
    provider = components[0]
    created = pipeline.create(workspace, "Validate fresh generation after a hard worker interruption.")
    def interrupt(label):
        if label == "CodeBundle":
            pipeline.cancel(workspace, created.id)
    provider.on_generate = interrupt
    stopped = pipeline.run(workspace, created.id, provider=provider, runner=components[1])
    assert stopped.status == "cancelled" and stopped.stage == "generate"
    # Reconstruct the persisted state of a hard crash before the directory's
    # allocation checkpoint; its partial source must never be reused.
    stopped.code_attempt = 0
    workspace.save("pipeline", stopped)
    partial = workspace.root / "autonomous" / created.id / "generated" / "attempt-1" / "partial.py"
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text("unreviewed partial generated source", encoding="utf-8")
    provider.on_generate = None
    provider.block_write = True
    pipeline.resume(workspace, created.id)
    result = pipeline.run(workspace, created.id, provider=provider, runner=components[1])
    assert result.status == "blocked" and result.stage == "write"
    assert result.code_attempt == 2 and components[1].calls == 1
    assert partial.read_text(encoding="utf-8") == "unreviewed partial generated source"
    assert "attempt-2" in result.artifacts["bundle"].path


def test_maximum_plan_limitations_survive_instrumentation_disclosure(workspace, components):
    components[0].plan["limitations"] = [f"Bounded fixture limitation {index}" for index in range(12)]
    components[0].block_write = True
    result = launch(workspace, components)
    assert result.status == "blocked" and result.stage == "write"
    plan = ResearchPlan.model_validate(pipeline._read(workspace, result, "plan"))
    assert len(plan.limitations) == 12
    assert "Production-call instrumentation" in plan.limitations[-1]


@pytest.mark.skipif(os.name != "nt", reason="Actual native execution requires Windows")
def test_native_pipeline_measures_source_and_verifies_exports(workspace, components, monkeypatch, pandoc):
    """Simulated model/literature; actual Windows execution, analysis and exports."""
    from paper_factory.autonomous.windows_runner import WindowsRunner
    for dependency in ("typst", "pypdf", "docx"):
        pytest.importorskip(dependency)
    monkeypatch.setenv("PYPANDOC_PANDOC", pandoc)
    provider = components[0]
    provider.plan["title"] = "Measured Windows fixture integration with simulated model and literature"
    provider.plan["comparator"] = "A deletion ablation removes the final annotated fixture value while preserving all other values."
    provider.plan["limitations"] = ["Controlled fixtures do not establish natural input population behavior.",
                                   "Model planning, review, manuscript and literature in this integration test are simulated."]
    settings = {"seeds": provider.plan["seeds"], "sample_size": provider.plan["sample_size"],
                "fixture_size": provider.plan["parameters"]["fixture_size"]}
    code = '''import itertools, json, os, pathlib, random, sys
sys.path.insert(0, os.environ['PF_SOURCE_ROOT'])
from transform import transform
settings = SETTINGS
def violations(actual, expected):
    missing = object()
    return sum(left != right for left, right in itertools.zip_longest(actual, expected, fillvalue=missing))
rows = []
for seed in settings['seeds']:
    generator = random.Random(seed)
    for unit in range(settings['sample_size']):
        values = [generator.randrange(10000) for _ in range(settings['fixture_size'])]
        annotation = tuple(values)
        actual = transform(values)
        ablation = values[:-1]
        for condition, result in [('production', actual), ('ablation', ablation)]:
            rows.append({'unit_id': 'case-' + str(unit), 'seed': seed, 'condition': condition,
                         'metric': 'error', 'value': violations(result, annotation)})
controls = [
    {'name': 'positive control', 'passed': violations(transform([7, 11]), (7, 11)) == 0,
     'details': 'Actual production output agrees with the independently specified two-value annotation.'},
    {'name': 'negative control', 'passed': violations([7], (7, 11)) > 0,
     'details': 'The independent oracle detects a deliberate deletion from the known expected annotation.'}]
pathlib.Path(os.environ['PF_OUTPUT_ROOT'], 'observations.json').write_text(
    json.dumps({'observations': rows, 'controls': controls}), encoding='utf-8')
'''.replace("SETTINGS", repr(settings))
    original = provider.generate
    def measured_bundle(prompt, schema, call_dir, **kwargs):
        value = original(prompt, schema, call_dir, **kwargs)
        if schema["title"] == "CodeBundle":
            value["files"][0]["content"] = code
            value["explanation"] = "Actual imported production calls and deletion ablation measured against independent fixture annotations."
        elif schema["title"] == "ManuscriptDraft":
            value["title"] = provider.plan["title"]
            for section in value["sections"]:
                section["text"] = section["text"].replace(
                    "Its observations are simulated inputs for orchestration validation and cannot establish production correctness.",
                    "Model and literature inputs are simulated, while the native Windows worker measures the actual imported production source.")
        return value
    monkeypatch.setattr(provider, "generate", measured_bundle)
    created = pipeline.create(workspace, "Validate native controlled source execution through the complete export pipeline.")
    result = pipeline.run(workspace, created.id, provider=provider, runner=WindowsRunner())
    assert result.status == "completed", result.message
    raw = pipeline._read(workspace, result, "observations")
    assert len(raw["observations"]) == 12
    assert {row["value"] for row in raw["observations"] if row["condition"] == "production"} == {0}
    assert {row["value"] for row in raw["observations"] if row["condition"] == "ablation"} == {1}
    execution = pipeline._read(workspace, result, "execution")
    assert execution["backend"] == "windows-appcontainer" and execution["cleanup_confirmed"] is True
    assert execution["production_calls"] == [{"path": "transform.py", "function": "transform", "calls": 7}]
    assert "runtime-manifest" in result.artifacts
    assert pipeline.verify(workspace, result.id)["passed"] is True
    with zipfile.ZipFile(pipeline._artifact(workspace, result, "reproducibility")) as archive:
        assert {"runtime-manifest.json", "observations.json", "paper.pdf", "paper.docx", "paper.tex"} <= set(archive.namelist())
        instructions = archive.read("README.md").decode("utf-8")
        assert "Windows AppContainer" in instructions and "Docker and WSL are not required" in instructions
        assert "PF_SOURCE_ROOT" in instructions and "runtime-manifest.json" in instructions


@pytest.mark.parametrize("stale_status", ["running", "completed"])
def test_stale_checkpoint_cannot_erase_committed_cancellation(workspace, stale_status):
    created = pipeline.create(workspace, "Validate durable cancellation during a worker checkpoint.")
    stale = workspace.get("pipeline", created.id, PipelineRun)
    pipeline.cancel(workspace, created.id)
    stale.status = stale_status
    pipeline._save(workspace, stale)
    persisted = workspace.get("pipeline", created.id, PipelineRun)
    assert persisted.cancellation_requested
    if stale_status == "completed":
        assert persisted.status == "cancelled" and persisted.code == "CANCELLED"

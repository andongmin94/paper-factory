import json
import os
import sqlite3
import shutil
import stat
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import httpx

from paper_factory.evidence import claims_for_run, study_readiness_errors, verify_claim
from paper_factory.experiments import extract_metric, register_manifest, run_experiment, _human_subjects
from paper_factory.models import ExperimentManifest, ExperimentRun, Metric, Paper, PaperState, Project, Study, StudyState
from paper_factory.project import ingest, inventory, verify_snapshot
from paper_factory.research import create_study, discover, plan
from paper_factory.workspace import Workspace, write_json


@pytest.fixture
def imported(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_HOME", str(tmp_path / "home"))
    source = tmp_path / "original"
    source.mkdir()
    (source / "analysis.py").write_text("print('original')\n", encoding="utf-8")
    (source / "data.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    (source / ".env").write_text("PRIVATE_TOKEN=do-not-copy", encoding="utf-8")
    (source / "id_ed25519").write_text("private-key", encoding="utf-8")
    (source / "node_modules").mkdir()
    (source / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")
    ws = ingest(str(source), tmp_path / "workspace")
    return ws, source


def custom_manifest(ws, tmp_path, *, script=None, output="result.json", pointer="/score", **kwargs):
    study = create_study(ws, question=kwargs.pop("question", "What measured score does this analysis produce?"), human_subjects=kwargs.pop("study_human_subjects", False))
    project = ws.latest("project", Project)
    manifest = ExperimentManifest(
        study_id=study.id, source_commit=project.source_commit, source_digest=project.snapshot_digest,
        command=["{python}", "-c", script or "from pathlib import Path; Path('result.json').write_text('{\"score\": 7.25}')"],
        expected_outputs=[output], metrics=[Metric(name="score", output=output, pointer=pointer, unit="points", description="Measured score")],
        **kwargs,
    )
    path = tmp_path / "manifest.json"
    write_json(path, manifest)
    return register_manifest(ws, path)


@pytest.mark.parametrize("input_path,output", [("data.csv", "data.csv"), ("data.csv", "DATA.CSV"), ("measurements", "measurements/result.json")])
def test_register_rejects_outputs_that_would_delete_declared_input(imported, tmp_path, input_path, output):
    ws, _ = imported
    if input_path == "measurements":
        # A registered directory input protects its contents, not only its name.
        source = tmp_path / "directory-input-source"
        source.mkdir()
        (source / input_path).mkdir()
        (source / input_path / "result.json").write_text('{"score": 1}', encoding="utf-8")
        ws = ingest(str(source), tmp_path / "directory-input-workspace")
    before = inventory(ws.path("source"))
    with pytest.raises(ValueError, match="separate from declared input"):
        custom_manifest(ws, tmp_path, output=output, inputs=[input_path])
    assert inventory(ws.path("source")) == before
    assert ws.list("run", ExperimentRun) == []


@pytest.mark.parametrize("question", [
    "Patient satisfaction survey", "Clinical interviews with patients", "Student experience survey",
    "Interviews with customers", "임상 환자 면담", "학생 만족도 설문", "연구 대상자 인터뷰",
])
def test_obvious_human_collection_descriptors_block_before_process_launch(imported, tmp_path, question):
    ws, _ = imported
    manifest = custom_manifest(ws, tmp_path, question=question)
    with pytest.raises(ValueError, match="Human-subject research cannot execute"):
        run_experiment(ws, manifest)
    assert ws.list("run", ExperimentRun) == []


@pytest.mark.parametrize("question", ["Survey of existing citation libraries", "Clinical parser benchmark", "Interview transcript parser benchmark", "Patiently waiting for compiler completion"])
def test_unrelated_survey_or_clinical_software_words_do_not_mark_human_collection(imported, tmp_path, question):
    ws, _ = imported
    manifest = custom_manifest(ws, tmp_path, question=question)
    study = ws.get("study", manifest.study_id, Study)
    assert not _human_subjects(study, manifest)
    assert run_experiment(ws, manifest).status == "SUCCEEDED"


def test_ingestion_is_sanitized_stable_and_independent_of_cwd(imported, tmp_path, monkeypatch):
    ws, source = imported
    original = inventory(source, sanitize=True)
    assert ws.latest("project", Project).assets == original
    assert not (ws.root / "source" / ".env").exists()
    assert not (ws.root / "source" / "id_ed25519").exists()
    assert not (ws.root / "source" / "node_modules").exists()
    monkeypatch.chdir(tmp_path)
    discover(ws)
    study = create_study(ws)
    run = run_experiment(ws, plan(ws, study))
    assert run.status == "SUCCEEDED"
    assert run.metrics == {"file_count": 2.0, "total_bytes": float(sum(asset.size for asset in original))}
    claims = claims_for_run(ws, run)
    assert all(verify_claim(ws, claim) == [] for claim in claims)
    assert inventory(source, sanitize=True) == original
    verify_snapshot(ws)
    other = ingest(str(source), tmp_path / "another-workspace")
    assert other.latest("project", Project).snapshot_digest == ws.latest("project", Project).snapshot_digest


def test_nested_workspaces_are_rejected_without_source_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_HOME", str(tmp_path / "home"))
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError, match="separate"):
        ingest(str(source), source / "workspace")
    assert list(source.iterdir()) == []
    with pytest.raises(ValueError, match="separate"):
        ingest(str(source), tmp_path)


def test_all_symlinks_are_skipped(imported, tmp_path):
    ws, source = imported
    secret = tmp_path / "external.txt"
    secret.write_text("external", encoding="utf-8")
    try:
        (source / "external-link").symlink_to(secret)
        (source / "dir-link").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires Windows developer mode")
    new_ws = ingest(str(source), tmp_path / "symlink-workspace")
    assert not (new_ws.root / "source" / "external-link").exists()
    assert not (new_ws.root / "source" / "dir-link").exists()


def test_dirty_git_commit_and_exact_dirty_content(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_HOME", str(tmp_path / "home"))
    source = tmp_path / "git-source"
    source.mkdir()
    for argv in (["git", "init", str(source)], ["git", "-C", str(source), "config", "user.email", "fixture@example.invalid"],
                 ["git", "-C", str(source), "config", "user.name", "Fixture"]):
        subprocess.run(argv, capture_output=True, check=True)
    (source / "data.txt").write_text("committed", encoding="utf-8")
    subprocess.run(["git", "-C", str(source), "add", "data.txt"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-m", "fixture"], capture_output=True, check=True)
    (source / "data.txt").write_text("dirty exact bytes", encoding="utf-8")
    ws = ingest(str(source), tmp_path / "workspace")
    project = ws.latest("project", Project)
    assert len(project.source_commit) == 40
    assert (ws.root / "source" / "data.txt").read_text(encoding="utf-8") == "dirty exact bytes"
    assert not (ws.root / "source" / ".git").exists()


def test_duplicate_studies_and_candidate_honesty(imported):
    ws, _ = imported
    candidate = discover(ws)[0]
    assert "No novelty" in candidate.what_is_new
    assert candidate.incremental_risk.startswith("High")
    create_study(ws, question="What IS the measured count?")
    with pytest.raises(ValueError, match="Duplicate"):
        create_study(ws, question="what is the measured count!")


def test_real_custom_metric_and_json_pointer(imported, tmp_path):
    ws, source = imported
    manifest = custom_manifest(ws, tmp_path, script="from pathlib import Path; Path('result.json').write_text('{\"a/b\": {\"~key\": [0, 4.5]}}')", pointer="/a~1b/~0key/1")
    run = run_experiment(ws, manifest)
    assert run.status == "SUCCEEDED"
    assert run.metrics["score"] == 4.5
    claim = claims_for_run(ws, run)[0]
    assert claim.value == 4.5
    assert verify_claim(ws, claim) == []
    assert (source / "analysis.py").read_text(encoding="utf-8") == "print('original')\n"


@pytest.mark.parametrize("script,error", [
    ("print('logged failure'); raise SystemExit(9)", "code 9"),
    ("print('no output')", "not produced"),
    ("from pathlib import Path; Path('result.json').write_text('{\"score\": true}')", "finite number"),
    ("from pathlib import Path; Path('result.json').write_text('{\"score\": NaN}')", "Nonfinite"),
    ("from pathlib import Path; Path('result.json').write_text('{\"other\": 1}')", "absent"),
])
def test_failure_records_cannot_become_claims(imported, tmp_path, script, error):
    ws, _ = imported
    manifest = custom_manifest(ws, tmp_path, script=script)
    run = run_experiment(ws, manifest)
    assert run.status == "FAILED"
    assert error in run.error
    assert run.ended_at
    assert (ws.root / "runs" / run.id / "stdout.log").is_file()
    assert ws.get("run", run.id, type(run)).status == "FAILED"
    with pytest.raises(ValueError, match="Cannot create quantitative"):
        claims_for_run(ws, run)


def test_timeout_preserves_failure(imported, tmp_path):
    ws, _ = imported
    manifest = custom_manifest(ws, tmp_path, script="import time; print('starting', flush=True); time.sleep(5)", timeout_seconds=1)
    run = run_experiment(ws, manifest)
    assert run.status == "FAILED"
    assert "timed out" in run.error
    assert "starting" in (ws.root / "runs" / run.id / "stdout.log").read_text(encoding="utf-8")


@pytest.mark.parametrize("options", [
    {"study_human_subjects": True}, {"human_subjects": True, "ethics_approval": "IRB example"},
    {"question": "How do participants respond to the intervention?"},
    {"question": "How does this user study measure interaction?"},
])
def test_human_subject_collection_is_blocked(imported, tmp_path, options):
    ws, _ = imported
    manifest = custom_manifest(ws, tmp_path, **options)
    with pytest.raises(ValueError, match="Human-subject"):
        run_experiment(ws, manifest)
    assert not ws.list("run", ExperimentRun)


@pytest.mark.parametrize("output", ["../outside.json", "/absolute.json", "C:/absolute.json", "nested/../../outside.json", "nested\\output.json", "CON.json", "nested/NUL.json", "LPT1/data.json", "result.json.", "result.json "])
def test_manifest_rejects_unsafe_paths(imported, tmp_path, output):
    ws, _ = imported
    with pytest.raises(ValueError, match="safe relative"):
        custom_manifest(ws, tmp_path, output=output)


def test_stale_outputs_are_not_reused(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_HOME", str(tmp_path / "home"))
    source = tmp_path / "source"
    source.mkdir()
    (source / "result.json").write_text('{"score": 100}', encoding="utf-8")
    ws = ingest(str(source), tmp_path / "workspace")
    manifest = custom_manifest(ws, tmp_path, script="print('no output generated')")
    run = run_experiment(ws, manifest)
    assert run.status == "FAILED"
    assert "not produced" in run.error
    assert (source / "result.json").read_text(encoding="utf-8") == '{"score": 100}'


@pytest.mark.parametrize("tampered", ["raw/result.json", "processed.json", "manifest.json", "provenance.json", "stdout.log", "run.json"])
def test_evidence_tampering_is_detected(imported, tmp_path, tampered):
    ws, _ = imported
    run = run_experiment(ws, custom_manifest(ws, tmp_path))
    claim = claims_for_run(ws, run)[0]
    path = ws.root / "runs" / run.id / tampered
    path.write_text('{"score": 999}', encoding="utf-8")
    assert verify_claim(ws, claim)
    with pytest.raises(ValueError, match="Cannot create quantitative"):
        claims_for_run(ws, run)


def test_snapshot_tampering_invalidates_claim(imported, tmp_path):
    ws, _ = imported
    run = run_experiment(ws, custom_manifest(ws, tmp_path))
    claim = claims_for_run(ws, run)[0]
    path = ws.root / "source" / "data.csv"
    path.chmod(stat.S_IREAD | stat.S_IWRITE)
    path.write_text("tampered", encoding="utf-8")
    assert any("snapshot" in error.lower() for error in verify_claim(ws, claim))


def test_credentials_do_not_cross_environment_boundary(imported, tmp_path, monkeypatch):
    ws, _ = imported
    monkeypatch.setenv("VERY_PRIVATE_TOKEN", "private-value")
    monkeypatch.setenv("PF_AUTHOR_EMAIL", "private-author@example.invalid")
    script = "import os; from pathlib import Path; Path('result.json').write_text('{\"score\": ' + str(int('VERY_PRIVATE_TOKEN' not in os.environ)) + '}')"
    run = run_experiment(ws, custom_manifest(ws, tmp_path, script=script))
    assert run.status == "SUCCEEDED" and run.metrics["score"] == 1
    assert "VERY_PRIVATE_TOKEN" not in run.environment
    assert "PF_AUTHOR_EMAIL" not in run.environment
    provenance = json.loads((ws.root / "runs" / run.id / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["effective_command"][0] == sys.executable
    assert Path(provenance["effective_executable"]).resolve() == Path(sys.executable).resolve()
    assert "pydantic" in provenance["package_versions"]
    assert list(provenance["package_versions"]) == sorted(provenance["package_versions"])
    assert all(isinstance(name, str) and isinstance(version, str) for name, version in provenance["package_versions"].items())
    assert "private-value" not in json.dumps(provenance)
    assert "private-author@example.invalid" not in json.dumps(provenance)
    assert provenance["environment_sha256"]


def test_git_url_credentials_are_not_persisted(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "credential.helper")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "synthetic-unreviewed-helper")
    source = "https://user:private-secret@example.invalid/project.git?access_token=private-secret"
    clones = []

    def fake_git(command, **kwargs):
        if "clone" in command:
            assert command[:6] == ["git", "-c", "credential.helper=", "-c", "core.hooksPath=" + os.devnull, "clone"]
            assert command[6:-1] == ["--depth", "1", "--", source]
            environment = kwargs["env"]
            assert {key: value for key, value in environment.items() if key.upper().startswith("GIT_")} == {
                "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_ASKPASS": "",
            }
            clones.append(command)
            checkout = Path(command[-1])
            checkout.mkdir()
            (checkout / "data.txt").write_text("public asset", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")
        assert command[:2] == ["git", "-C"] and command[-2:] == ["rev-parse", "HEAD"]
        return subprocess.CompletedProcess(command, 0, "f" * 40 + "\n", "")
    monkeypatch.setattr("paper_factory.project.subprocess.run", fake_git)
    ws = ingest(source, tmp_path / "workspace")
    assert len(clones) == 1
    project = ws.latest("project", Project)
    assert project.source == "https://example.invalid/project.git"
    assert project.source_commit == "f" * 40
    assert (ws.root / "source/data.txt").read_text(encoding="utf-8") == "public asset"
    assert "private-secret" not in (ws.root / "project.json").read_text(encoding="utf-8")


def test_execution_copy_changes_leave_both_sources_untouched(imported, tmp_path):
    ws, original = imported
    script = "from pathlib import Path; Path('analysis.py').write_text('changed in work'); Path('result.json').write_text('{\"score\": 1}')"
    run = run_experiment(ws, custom_manifest(ws, tmp_path, script=script))
    assert run.status == "SUCCEEDED"
    assert (original / "analysis.py").read_text(encoding="utf-8") == "print('original')\n"
    assert (ws.root / "source" / "analysis.py").read_text(encoding="utf-8") == "print('original')\n"
    assert (ws.root / "runs" / run.id / "work" / "analysis.py").read_text(encoding="utf-8") == "changed in work"


def test_unknown_run_cannot_supply_claims(imported):
    ws, _ = imported
    fake = ExperimentRun(experiment_id="unknown", study_id="unknown", source_digest="fake", command=["fake"], environment={}, seed=0,
                         status="SUCCEEDED", exit_code=0, metrics={"score": 100})
    with pytest.raises(ValueError, match="Unknown run"):
        claims_for_run(ws, fake)


def test_builtin_inventory_includes_existing_results_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_HOME", str(tmp_path / "home"))
    source = tmp_path / "source"
    (source / ".paperfactory-results").mkdir(parents=True)
    (source / ".paperfactory-results" / "old-data.csv").write_text("x\n1", encoding="utf-8")
    ws = ingest(str(source), tmp_path / "workspace")
    run = run_experiment(ws, plan(ws, create_study(ws)))
    assert run.status == "SUCCEEDED" and run.metrics["file_count"] == 1


def test_manifest_credentials_and_duplicate_metrics_rejected(imported, tmp_path):
    ws, _ = imported
    with pytest.raises(ValueError, match="Credential"):
        custom_manifest(ws, tmp_path, environment={"API_TOKEN": "do-not-persist"})


def test_substantive_study_requires_its_own_plan(imported):
    ws, _ = imported
    study = create_study(ws, question="What is the speedup of the real algorithm versus a baseline?")
    with pytest.raises(ValueError, match="study-specific"):
        plan(ws, study)


@pytest.mark.parametrize("argument", ["--output=C:\\original\\data.json", "--input=/original/data", "../original/data.json", "--input=../original/data.json", "\\original\\data.json", "C:outside.json"])
def test_manifest_rejects_explicit_outside_path_arguments(imported, tmp_path, argument):
    ws, _ = imported
    manifest = custom_manifest(ws, tmp_path)
    manifest.id = "outside-path-test"
    manifest.command = ["{python}", "analysis.py", argument]
    path = tmp_path / "outside-manifest.json"
    write_json(path, manifest)
    with pytest.raises(ValueError, match="filesystem paths|outside the working copy"):
        register_manifest(ws, path)


def test_duplicate_metric_names_rejected(imported, tmp_path):
    ws, _ = imported
    manifest = custom_manifest(ws, tmp_path)
    manifest.id = "duplicate-metric-test"
    manifest.metrics.append(manifest.metrics[0].model_copy())
    path = tmp_path / "duplicate-manifest.json"
    write_json(path, manifest)
    with pytest.raises(ValueError, match="unique"):
        register_manifest(ws, path)


@pytest.mark.parametrize("value", [True, "1", float("inf"), float("nan"), None])
def test_metric_requires_finite_number(value):
    with pytest.raises(ValueError, match="finite number"):
        extract_metric({"value": value}, "/value")


def test_identity_metric_rejects_lossy_integer_conversion():
    with pytest.raises(ValueError, match="loses precision"):
        extract_metric({"count": 9007199254740993}, "/count")


@pytest.mark.parametrize("record_id", ["../outside", "C:/outside", "a/b", "a\\b", "CON", "con.json", "NUL", "COM1", "LPT9", "ends-dot.", "trailing "])
def test_record_ids_must_be_portable(record_id):
    with pytest.raises(ValueError, match="safe portable"):
        Project(id=record_id, name="fixture", source="fixture", snapshot_digest="digest", assets=[])


@pytest.mark.parametrize("failure_stage", ["copy", "provenance"])
def test_setup_failures_preserve_completed_failure_records(imported, tmp_path, monkeypatch, failure_stage):
    ws, source = imported
    manifest = custom_manifest(ws, tmp_path)
    def fail(*args, **kwargs):
        raise RuntimeError(f"{failure_stage} setup failed")
    if failure_stage == "copy":
        monkeypatch.setattr("paper_factory.experiments.shutil.copytree", fail)
    else:
        monkeypatch.setattr("paper_factory.experiments.importlib.metadata.distributions", fail)
    run = run_experiment(ws, manifest)
    assert run.status == "FAILED" and run.ended_at
    assert failure_stage in run.error
    assert ws.get("run", run.id, ExperimentRun) == run
    assert ExperimentRun.model_validate_json(ws.path(f"runs/{run.id}/run.json").read_text(encoding="utf-8")) == run
    assert ws.path(f"runs/{run.id}/stdout.log").read_bytes() == b""
    assert not list((ws.root / "runs" / run.id).glob("raw/*"))
    assert (source / "analysis.py").read_text(encoding="utf-8") == "print('original')\n"


def test_keyboard_interrupt_preserves_terminal_record(imported, tmp_path, monkeypatch):
    ws, _ = imported
    manifest = custom_manifest(ws, tmp_path)
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr("paper_factory.experiments._execute", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run_experiment(ws, manifest)
    run = ws.latest("run", ExperimentRun)
    assert run.status == "FAILED" and run.ended_at
    assert "KeyboardInterrupt" in run.error


def test_failed_retry_does_not_destroy_evidence_or_restore_readiness(imported, tmp_path, monkeypatch):
    ws, _ = imported
    manifest = custom_manifest(ws, tmp_path)
    first = run_experiment(ws, manifest)
    claim = claims_for_run(ws, first)[0]
    assert ws.get("study", manifest.study_id, Study).state == StudyState.EVIDENCE_READY
    with monkeypatch.context() as scoped:
        scoped.setattr("paper_factory.experiments._execute", lambda *args, **kwargs: 9)
        failed = run_experiment(ws, manifest)
    assert failed.status == "FAILED"
    assert verify_claim(ws, claim) == []
    assert claims_for_run(ws, first)[0] == claim
    assert ws.get("study", manifest.study_id, Study).state == StudyState.EXPERIMENTS_RUNNING
    assert failed.id in study_readiness_errors(ws, manifest.study_id)[0]
    retry = run_experiment(ws, manifest)
    claims_for_run(ws, retry)
    assert study_readiness_errors(ws, manifest.study_id) == []
    assert ws.get("study", manifest.study_id, Study).state == StudyState.EVIDENCE_READY


def test_concurrent_study_execution_is_rejected_without_partial_record(imported, tmp_path):
    ws, _ = imported
    manifest = custom_manifest(ws, tmp_path)
    with ws.lock(f"study-{manifest.study_id}"):
        with pytest.raises(ValueError, match="already running"):
            run_experiment(ws, manifest)
    assert ws.list("run", ExperimentRun) == []
    assert run_experiment(ws, manifest).status == "SUCCEEDED"


def test_next_run_preserves_and_closes_an_abandoned_attempt(imported, tmp_path):
    ws, _ = imported
    manifest = custom_manifest(ws, tmp_path)
    interrupted = ExperimentRun(experiment_id=manifest.id, study_id=manifest.study_id, source_digest=manifest.source_digest,
                                source_commit=manifest.source_commit, command=manifest.command, environment={}, seed=manifest.seed)
    ws.save("run", interrupted)
    current = run_experiment(ws, manifest)
    previous = ws.get("run", interrupted.id, ExperimentRun)
    assert previous.status == "FAILED" and previous.ended_at
    assert "interrupted" in previous.error
    assert current.status == "SUCCEEDED"
    assert study_readiness_errors(ws, manifest.study_id) == []


def test_timeout_terminates_descendants_before_they_can_finish(imported, tmp_path):
    ws, _ = imported
    script = ("import subprocess, sys, time; "
              "subprocess.Popen([sys.executable, '-c', \"import time; from pathlib import Path; time.sleep(2.5); Path('child-finished').write_text('late')\"]); "
              "print('parent started', flush=True); time.sleep(10)")
    run = run_experiment(ws, custom_manifest(ws, tmp_path, script=script, timeout_seconds=1))
    assert run.status == "FAILED" and "timed out" in run.error
    time.sleep(2.1)
    assert not ws.path(f"runs/{run.id}/work/child-finished").exists()
    assert "parent started" in ws.path(f"runs/{run.id}/stdout.log").read_text(encoding="utf-8")


def directory_link(path, target):
    try:
        path.symlink_to(target, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            pytest.skip("Directory links are unavailable")
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(path), str(target)], capture_output=True, check=False)
        if result.returncode:
            pytest.skip("Windows junction creation is unavailable")


def test_workspace_paths_reject_links_even_when_target_stays_inside_workspace(imported):
    ws, _ = imported
    link = ws.root / "runs" / "linked"
    directory_link(link, ws.root / "source")
    with pytest.raises(ValueError, match="symlinks|junctions"):
        ws.path("runs/linked/data.csv")
    with pytest.raises(ValueError, match="symlinks|junctions"):
        write_json(link / "new.json", {"should": "not be written"})
    assert not (ws.root / "source" / "new.json").exists()


def test_linked_workspace_destination_is_rejected_before_writes(imported, tmp_path):
    _, source = imported
    external = tmp_path / "external"
    external.mkdir()
    link = tmp_path / "workspace-link"
    directory_link(link, external)
    with pytest.raises(ValueError, match="symlinks|junctions"):
        ingest(str(source), link)
    assert list(external.iterdir()) == []


def test_missing_empty_source_snapshot_is_invalid(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_HOME", str(tmp_path / "home"))
    source = tmp_path / "empty"
    source.mkdir()
    ws = ingest(str(source), tmp_path / "workspace")
    ws.path("source").rmdir()
    with pytest.raises(ValueError, match="missing"):
        verify_snapshot(ws)


def test_inaccessible_inventory_cannot_silently_omit_assets(imported, monkeypatch):
    ws, _ = imported
    def inaccessible(root, **kwargs):
        kwargs["onerror"](PermissionError("unreadable snapshot directory"))
        return iter([])
    monkeypatch.setattr("paper_factory.project.os.walk", inaccessible)
    with pytest.raises(PermissionError, match="unreadable"):
        verify_snapshot(ws)


def test_concurrent_json_writes_publish_complete_documents_without_temp_collisions(tmp_path):
    destination = tmp_path / "shared.json"
    def publish(index):
        value = {"writer": index, "payload": str(index) * 10000}
        write_json(destination, value)
        return value
    with ThreadPoolExecutor(max_workers=8) as pool:
        versions = list(pool.map(publish, range(24)))
    assert json.loads(destination.read_text(encoding="utf-8")) in versions
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize("path", ["source/a?b", "source/a*b", "source/a|b", "source/a<b", 'source/a"b', "source/a\x00b", "source/a\nb"])
def test_workspace_rejects_nonportable_paths(imported, path):
    ws, _ = imported
    with pytest.raises(ValueError, match="safe relative"):
        ws.path(path)


def test_create_workspace_does_not_adopt_existing_content(tmp_path):
    root = tmp_path / "occupied"
    root.mkdir()
    sentinel = root / "important.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        Workspace.create(root)
    assert list(root.iterdir()) == [sentinel]


def test_planning_does_not_accept_a_modified_snapshot(imported):
    ws, _ = imported
    source = ws.path("source/data.csv")
    source.chmod(stat.S_IREAD | stat.S_IWRITE)
    source.write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError, match="modified"):
        create_study(ws, question="What is the modified data?")


def test_database_record_identity_must_match_its_storage_key(imported):
    ws, _ = imported
    project = ws.latest("project", Project)
    changed = project.model_copy(update={"id": "project-counterfeit"})
    with sqlite3.connect(ws.path("records.sqlite3")) as database:
        database.execute("UPDATE records SET data=? WHERE kind='project' AND id=?", (changed.model_dump_json(), project.id))
    with pytest.raises(ValueError, match="identifier"):
        ws.get("project", project.id, Project)
    with pytest.raises(ValueError, match="identifier"):
        ws.latest("project", Project)


@pytest.mark.skipif(os.name != "nt", reason="Windows command interpreter")
def test_windows_command_switches_can_execute_copy_local_scripts(imported, tmp_path):
    _, original = imported
    (original / "measure.cmd").write_text('@echo off\n> result.json echo {"score": 5}\n', encoding="utf-8")
    ws = ingest(str(original), tmp_path / "cmd-workspace")
    manifest = custom_manifest(ws, tmp_path)
    manifest.id = "experiment-windows-cmd"
    manifest.command = ["cmd", "/d", "/c", "measure.cmd"]
    path = tmp_path / "cmd-manifest.json"
    write_json(path, manifest)
    run = run_experiment(ws, register_manifest(ws, path))
    assert run.status == "SUCCEEDED", run.error
    assert claims_for_run(ws, run)[0].value == 5
    assert not (original / "result.json").exists()


def test_relative_executable_is_resolved_against_execution_copy(imported, tmp_path, monkeypatch):
    _, original = imported
    (original / "tools").mkdir()
    if os.name == "nt":
        executable = "tools/cmd.exe"
        shutil.copyfile(shutil.which("cmd.exe"), original / executable)
        (original / "measure.cmd").write_text('@echo off\n> result.json echo {"score": 5}\n', encoding="utf-8")
        command = [executable, "/d", "/c", "measure.cmd"]
    else:
        executable = "tools/measure"
        (original / executable).write_text('#!/bin/sh\nprintf \'{"score": 5}\\n\' > result.json\n', encoding="utf-8")
        (original / executable).chmod(0o755)
        command = [executable]
    ws = ingest(str(original), tmp_path / "executable-workspace")
    manifest = custom_manifest(ws, tmp_path)
    manifest.id = "experiment-relative-executable"
    manifest.command = command
    path = tmp_path / "executable-manifest.json"
    write_json(path, manifest)
    registered = register_manifest(ws, path)
    # A same-name file in the invoking directory must never be selected.
    unrelated = tmp_path / "unrelated"
    (unrelated / "tools").mkdir(parents=True)
    (unrelated / executable).write_text("wrong executable", encoding="utf-8")
    monkeypatch.chdir(unrelated)
    run = run_experiment(ws, registered)
    assert run.status == "SUCCEEDED", run.error
    assert claims_for_run(ws, run)[0].value == 5
    provenance = json.loads(ws.path(f"runs/{run.id}/provenance.json").read_text(encoding="utf-8"))
    assert Path(provenance["effective_command"][0]) == ws.path(f"runs/{run.id}/work/{executable}")
    assert not (original / "result.json").exists()


def reviewable_measurement(imported, tmp_path, monkeypatch):
    from paper_factory import literature, manuscript
    ws, _ = imported
    monkeypatch.delenv("PF_AUTHOR_PROFILE_JSON", raising=False)
    original_which = shutil.which
    monkeypatch.setattr(manuscript.shutil, "which", lambda command, *args, **kwargs: None if command == "pandoc" else original_which(command, *args, **kwargs))
    author = {"display_name": "Example Researcher", "email": "researcher@example.org", "affiliation": "Example University"}
    manifest = custom_manifest(ws, tmp_path)
    study = ws.get("study", manifest.study_id, Study)
    def respond(request):
        message = {"items": [{"DOI": "10.1234/measurements"}]} if request.url.path == "/works" else {
            "DOI": "10.1234/measurements", "title": ["Auditable Measurement Practices"],
            "author": [{"given": "Example", "family": "Scholar"}], "published": {"date-parts": [[2025]]},
        }
        return httpx.Response(200, json={"status": "ok", "message": message})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        literature.search(ws, "auditable measurements", study, client=client)
    run = run_experiment(ws, manifest)
    claim = claims_for_run(ws, run)[0]
    paper, _ = manuscript.build(ws, ws.get("study", study.id, Study), author_values=author)
    return ws, manifest, run, claim, paper, author


def test_failed_latest_attempt_is_visible_in_live_and_frozen_review(imported, tmp_path, monkeypatch):
    from paper_factory import integrity, manuscript
    ws, manifest, first, claim, _, author = reviewable_measurement(imported, tmp_path, monkeypatch)
    with monkeypatch.context() as scoped:
        scoped.setattr("paper_factory.experiments._execute", lambda *args, **kwargs: 9)
        failed = run_experiment(ws, manifest)
    paper, _ = manuscript.build(ws, ws.get("study", manifest.study_id, Study), author_values=author)
    assert verify_claim(ws, claim) == []
    assert ws.get("study", manifest.study_id, Study).state == StudyState.EXPERIMENTS_RUNNING
    report = integrity.check(ws, paper)
    assert report["passed"], report["errors"]
    assert not report["experiment_review"]["ready"]
    assert any(failed.id in issue for issue in report["warnings"])
    frozen = integrity.approve(ws, paper, approved=True, assessment="Reviewed the failed retry, earlier measured evidence and study limitations.", author_values=author)
    records = json.loads((frozen / "records.json").read_text(encoding="utf-8"))
    assert list(records["run"]) == [first.id, failed.id]
    assert records["run"][failed.id]["status"] == "FAILED"
    assert (frozen / "runs" / failed.id / "stdout.log").exists()
    frozen_report = integrity.check_frozen(ws, paper)
    assert frozen_report["passed"], frozen_report["errors"]
    assert not frozen_report["experiment_review"]["ready"]
    assert any(failed.id in issue for issue in frozen_report["warnings"])
    retry = run_experiment(ws, manifest)
    claims_for_run(ws, retry)
    assert not study_readiness_errors(ws, manifest.study_id)
    # Subsequent live recovery cannot rewrite the approved experiment history.
    assert not integrity.check_frozen(ws, paper)["experiment_review"]["ready"]


def test_incomplete_latest_attempt_warns_but_cannot_freeze_historic_claims(imported, tmp_path, monkeypatch):
    from paper_factory import integrity, manuscript
    ws, manifest, _, claim, paper, author = reviewable_measurement(imported, tmp_path, monkeypatch)
    pending = ExperimentRun(experiment_id=manifest.id, study_id=manifest.study_id, source_digest=manifest.source_digest,
                            source_commit=manifest.source_commit, command=manifest.command, environment={}, seed=manifest.seed)
    ws.save("run", pending)
    study = ws.get("study", manifest.study_id, Study)
    study.state = StudyState.EXPERIMENTS_RUNNING
    ws.save("study", study)
    paper, _ = manuscript.build(ws, study, author_values=author)
    assert verify_claim(ws, claim) == []
    report = integrity.check(ws, paper)
    assert report["passed"] and not report["experiment_review"]["ready"]
    assert any(pending.id in issue for issue in report["warnings"])
    with pytest.raises(ValueError, match="incomplete experiment"):
        integrity.approve(ws, paper, approved=True, assessment="Reviewed earlier measured evidence.", author_values=author)
    assert not list(ws.path("freezes").iterdir())
    retry = run_experiment(ws, manifest)
    claims_for_run(ws, retry)
    assert integrity.check(ws, paper)["experiment_review"]["ready"]


@pytest.mark.parametrize("style", ["forward_slashes", "escaped_backslashes", "environment"])
def test_explicit_source_references_cannot_bypass_protection_by_path_spelling(imported, tmp_path, style):
    ws, original = imported
    target = str(original)
    if style == "environment":
        with pytest.raises(ValueError, match="original project|source snapshot"):
            custom_manifest(ws, tmp_path, environment={"RESEARCH_DIRECTORY": target.replace("\\", "/")})
    else:
        value = repr(target) if style == "escaped_backslashes" else repr(target.replace("\\", "/"))
        script = f"from pathlib import Path; Path({value}).joinpath('analysis.py').write_text('original overwritten')"
        with pytest.raises(ValueError, match="original project|source snapshot"):
            custom_manifest(ws, tmp_path, script=script)
    assert (original / "analysis.py").read_text(encoding="utf-8") == "print('original')\n"


def test_corrupt_record_store_reports_a_workspace_error(imported):
    ws, _ = imported
    ws.path("records.sqlite3").write_bytes(b"not a sqlite database")
    with pytest.raises(ValueError, match="record store.*corrupt"):
        ws.list("project", Project)


@pytest.mark.skipif(os.name != "nt", reason="Windows transient file locks")
def test_transient_freeze_publication_error_is_retried(imported, tmp_path, monkeypatch):
    from paper_factory import integrity
    ws, _, _, _, paper, author = reviewable_measurement(imported, tmp_path, monkeypatch)
    original_rename = Path.rename
    attempts = []
    def transient_rename(source, destination):
        if source.parent == ws.path("freezes") and Path(destination).name == paper.id:
            attempts.append(source)
            if len(attempts) == 1:
                raise PermissionError("Injected transient Windows file lock")
        return original_rename(source, destination)
    monkeypatch.setattr(Path, "rename", transient_rename)
    frozen = integrity.approve(ws, paper, approved=True, assessment="Reviewed measured evidence and limitations.", author_values=author)
    assert 2 <= len(attempts) <= 5
    assert frozen.is_dir() and integrity.check_frozen(ws, paper)["passed"]
    assert list(ws.path("freezes").iterdir()) == [frozen]


@pytest.mark.skipif(os.name != "nt", reason="Windows transient file locks")
def test_persistent_freeze_publication_error_cleans_staging_and_can_retry(imported, tmp_path, monkeypatch):
    from paper_factory import integrity
    ws, _, _, _, paper, author = reviewable_measurement(imported, tmp_path, monkeypatch)
    original_rename = Path.rename
    attempts = []
    def denied_rename(source, destination):
        if source.parent == ws.path("freezes") and Path(destination).name == paper.id:
            attempts.append(source)
            raise PermissionError("Injected persistent Windows file lock")
        return original_rename(source, destination)
    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "rename", denied_rename)
        with pytest.raises(PermissionError, match="persistent"):
            integrity.approve(ws, paper, approved=True, assessment="Reviewed measured evidence and limitations.", author_values=author)
    assert len(attempts) == 5
    assert not list(ws.path("freezes").iterdir())
    assert ws.get("paper", paper.id, Paper).state == PaperState.INTEGRITY_CHECKED
    integrity.approve(ws, paper, approved=True, assessment="Reviewed measured evidence and limitations.", author_values=author)
    assert integrity.check_frozen(ws, paper)["passed"]


def test_artifact_publication_rejects_paths_outside_workspace(imported, tmp_path):
    ws, _ = imported
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(ValueError, match="inside its workspace"):
        ws.rename_artifact(outside, tmp_path / "renamed")
    assert outside.exists()

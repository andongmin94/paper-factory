"""Synthetic admission/storage controls; no real worker, model or scientific dispatch."""
import copy
import hashlib
import json
import zipfile

import pytest

from paper_factory import ipc
from paper_factory.workflow import WorkflowError, _freeze, _readable_evidence
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import write_json
from test_chromium_workflow import browser_setup, browser_protocol, prepare_browser
from test_preexecution_redesign import exhaust, stage
from test_workflow import protocol, setup


def state(service, identifier):
    ws = service._workspace(identifier)
    return ws, ws.get("workflow", identifier, Workflow)


def scientific_state(record):
    return record.model_dump(mode="json", exclude={"artifacts", "updated_at"})


def admissions(record):
    return {key: value for key, value in record.artifacts.items() if key.startswith("runtime-admission-")}


def unavailable(runner, monkeypatch, defect="chromium"):
    status = copy.deepcopy(runner.status())
    status["profiles"]["chromium"]["diagnostic"] = {
        "stage": "synthetic-self-check", "detail": "C:/Users/synthetic/private/credentials.json sk-" + "x" * 24}
    status["private_failure"] = {"headers": {"authorization": "Bearer synthetic-private-header"},
                                 "body": "synthetic-private-direct-response-body"}
    if defect == "chromium":
        status["profiles"]["chromium"].update(ready=False, runtimes=[])
        status["runtimes"] = ["quickjs"]
    else:
        status.update(ready=False, runtimes=[], cleanup_confirmed=False)
        status["profiles"]["quickjs"]["cleanup_confirmed"] = False
        # The selected profile remains ready; top-level failure still blocks.
    calls = []
    monkeypatch.setattr(runner, "status", lambda: calls.append("status") or copy.deepcopy(status))
    return status, calls


def reject(operation):
    with pytest.raises(WorkflowError) as error:
        operation()
    assert error.value.code == "ISOLATION_UNAVAILABLE"
    return error.value


def test_successful_runtime_admission_adds_no_diagnostic_artifact(browser_setup, monkeypatch):
    service, runner, identifier = browser_setup
    ws, before = state(service, identifier)
    status, calls = runner.status(), []
    monkeypatch.setattr(runner, "status", lambda: calls.append("status") or copy.deepcopy(status))
    service.submit_proposal(identifier, browser_protocol())
    _, after = state(service, identifier)
    assert not admissions(after) and not ws.path("research/runtime-admission").exists()
    assert calls == ["status"] and after.execution_attempt == runner.calls == 0
    assert before.artifacts.items() <= after.artifacts.items()


@pytest.mark.parametrize("defect", ["chromium", "other-profile-cleanup"])
def test_failed_admission_freezes_whole_status_without_changing_science(browser_setup, monkeypatch, defect):
    service, runner, identifier = browser_setup
    ws, before = state(service, identifier)
    originals = {key: service.artifact_path(identifier, key).read_bytes() for key in before.artifacts}
    source_bytes = ws.path("source/editor.js").read_bytes()
    status, calls = unavailable(runner, monkeypatch, defect)
    error = reject(lambda: service.submit_proposal(identifier, browser_protocol()))
    _, after = state(service, identifier)
    new = admissions(after)
    assert len(new) == 1 and calls == ["status"]
    key, artifact = next(iter(new.items()))
    raw = ws.path(artifact.path).read_bytes()
    receipt = json.loads(raw)
    assert receipt["status"] == status
    assert (receipt["event"], receipt["operation"], receipt["runtime"], receipt["research_id"]) == (
        "runtime-admission-failed", "submit-proposal", "chromium", identifier)
    assert artifact.size == len(raw) and artifact.sha256 == hashlib.sha256(raw).hexdigest()
    assert scientific_state(after) == scientific_state(before)
    assert {key: after.artifacts[key] for key in before.artifacts} == before.artifacts
    assert all(service.artifact_path(identifier, key).read_bytes() == value for key, value in originals.items())
    assert ws.path("source/editor.js").read_bytes() == source_bytes and runner.calls == 0
    assert key in str(error) and "chromium" in str(error)
    public_error = ipc.public_error(error)
    assert public_error["code"] == "ISOLATION_UNAVAILABLE"
    assert not any(value in json.dumps(public_error) for value in ("credentials.json", "C:/Users", "sk-" + "x" * 24, "synthetic-self-check"))
    public = service.status(identifier)
    assert not any(value in json.dumps(public) for value in ("synthetic-private-header", "synthetic-private-direct-response-body", "C:/Users", "sk-" + "x" * 24))
    assert not _readable_evidence(key) and key not in {item["name"] for item in public["material_manifest"]["evidence"]}
    with pytest.raises(WorkflowError) as blocked:
        service.read_material(identifier, "evidence", key)
    assert blocked.value.code == "MATERIAL_NOT_DECLARED"


def test_repeated_admission_failures_are_distinct_append_only_receipts(browser_setup, monkeypatch):
    service, runner, identifier = browser_setup
    unavailable(runner, monkeypatch)
    reject(lambda: service.submit_proposal(identifier, browser_protocol()))
    _, first = state(service, identifier)
    old = {key: service.artifact_path(identifier, key).read_bytes() for key in admissions(first)}
    reject(lambda: service.submit_proposal(identifier, browser_protocol()))
    _, second = state(service, identifier)
    assert len(admissions(second)) == 2 and set(old) < set(admissions(second))
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in old.items())
    assert scientific_state(second) == scientific_state(first) and second.proposal_attempt == second.execution_attempt == runner.calls == 0


@pytest.mark.parametrize("defect", ["missing", "changed"])
def test_changed_admission_proof_blocks_next_operation_before_status(browser_setup, monkeypatch, defect):
    service, runner, identifier = browser_setup
    _, calls = unavailable(runner, monkeypatch)
    reject(lambda: service.submit_proposal(identifier, browser_protocol()))
    ws, before = state(service, identifier)
    artifact = next(iter(admissions(before).values()))
    if defect == "missing":
        ws.path(artifact.path).unlink()
    else:
        ws.path(artifact.path).write_bytes(b"changed synthetic diagnostic")
    with pytest.raises(WorkflowError) as blocked:
        service.submit_proposal(identifier, browser_protocol())
    assert blocked.value.code == "ARTIFACT_CHANGED" and calls == ["status"]
    _, after = state(service, identifier)
    assert after == before and runner.calls == 0


@pytest.mark.parametrize("collision", ["physical-unregistered", "registered"])
def test_runtime_admission_identifier_collision_cannot_overwrite(browser_setup, monkeypatch, collision):
    service, runner, identifier = browser_setup
    unavailable(runner, monkeypatch)
    fixed = "runtime-admission-111111111111"
    monkeypatch.setattr("paper_factory.workflow.uid", lambda prefix: fixed)
    ws, _ = state(service, identifier)
    path = ws.path("research/runtime-admission/" + fixed + ".json")
    if collision == "physical-unregistered":
        path.parent.mkdir(parents=True)
        path.write_bytes(b"unregistered original synthetic bytes")
    else:
        reject(lambda: service.submit_proposal(identifier, browser_protocol()))
    original = path.read_bytes()
    _, before = state(service, identifier)
    with pytest.raises(WorkflowError) as blocked:
        service.submit_proposal(identifier, browser_protocol())
    assert blocked.value.code == "RUNTIME_ADMISSION_EVIDENCE_CONFLICT"
    assert path.read_bytes() == original
    _, after = state(service, identifier)
    assert after == before and runner.calls == 0


def test_experiment_readiness_failure_is_retained_before_lease_or_dispatch(browser_setup, monkeypatch):
    service, runner, identifier = browser_setup
    prepare_browser(service, identifier)
    ws, before = state(service, identifier)
    status, calls = unavailable(runner, monkeypatch)
    execution_lease = ws.path("locks/execution.lock")
    assert not execution_lease.exists()
    reject(lambda: service.start_experiment(identifier))
    _, after = state(service, identifier)
    raw = service.artifact_path(identifier, next(iter(admissions(after)))).read_bytes()
    assert json.loads(raw)["operation"] == "start-experiment" and json.loads(raw)["status"] == status
    assert scientific_state(after) == scientific_state(before)
    assert after.execution_attempt == runner.calls == 0 and calls == ["status"]
    assert not execution_lease.exists() and identifier not in service._jobs


def test_prepared_redesign_basis_survives_operational_failure(setup, monkeypatch):
    service, runner, identifier = setup
    exhaust(service, identifier)
    prepared = stage(service, identifier)
    value = prepared["redesign_candidate"]
    ws, before = state(service, identifier)
    basis = service._preparation_redesign_basis(ws, before)
    original = {key: service.artifact_path(identifier, key).read_bytes() for key in before.artifacts}
    ready = runner.status()
    calls = []
    failed = {**ready, "ready": False, "runtimes": [], "diagnostic": {"detail": "synthetic readiness failure"}}
    monkeypatch.setattr(runner, "status", lambda: calls.append("status") or copy.deepcopy(failed))
    reject(lambda: service.submit_redesign_proposal(identifier, value))
    _, after = state(service, identifier)
    assert scientific_state(after) == scientific_state(before)
    assert service._preparation_redesign_basis(ws, after) == basis
    assert service.status(identifier)["preparation_redesign_available"] is True
    assert json.loads(service.artifact_path(identifier, next(iter(admissions(after)))).read_bytes())["operation"] == "submit-redesign-proposal"
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in original.items())
    monkeypatch.setattr(runner, "status", lambda: copy.deepcopy(ready))
    restored = service.submit_redesign_proposal(identifier, value)
    assert restored["redesign_candidate"] == value and restored["execution_attempt"] == runner.calls == 0
    assert restored["proposal_attempt"] == 3 and restored["study_literature_attempt"] == 3


def test_reproduction_archive_keeps_raw_admission_proof_without_science_claim(setup, monkeypatch):
    service, runner, identifier = setup
    ready = runner.status()
    monkeypatch.setattr(runner, "status", lambda: {**ready, "ready": False, "runtimes": []})
    reject(lambda: service.submit_proposal(identifier, protocol()))
    ws, record = state(service, identifier)
    key = next(iter(admissions(record)))
    original = service.artifact_path(identifier, key).read_bytes()
    # Only exercise archive selection with labelled packaging doubles, never execution/approval.
    required = ("plan", "observations", "execution", "analysis", "literature", "canonical", "study-review", "selected-literature",
                "export-md", "export-pdf", "export-docx", "export-tex", "conversion", "manuscript-review", "bundle")
    for name in required:
        path = ws.path("research/synthetic-export/" + name + ".json")
        write_json(path, protocol() if name == "plan" else {"simulation": True, "scope": "Packaging double; no actual science or approval"})
        _freeze(ws, record, name, path)
    export = ws.path("research/synthetic-package")
    export.mkdir()
    service._bundle(ws, record, export)
    with zipfile.ZipFile(export / "reproducibility.zip") as package:
        member = "runtime-admission/" + key + ".json"
        assert package.read(member) == original
        assert json.loads(package.read("inventory.json"))[member] == {"sha256": hashlib.sha256(original).hexdigest(), "size": len(original)}
    assert record.execution_attempt == runner.calls == 0 and record.stage == "created" and not _readable_evidence(key)

"""Exact retained evidence re-admission; synthetic receipts, no provider or project execution."""
import copy
import json

import pytest

from test_research_development_contract import (
    development, generated_evidence, continuation, study, unwritten_portfolio,
    design, audit,
)
from test_manuscript_improvement import current, reserve, retain


OLD_ERROR = "Every rule must map to exact externally verified repository source witnesses"


def reject_completed_repair(service, rid, evidence, monkeypatch, damage=None):
    # Match the actual stopped round: design plan retained, both evidence inputs
    # rejected by the old transport contract, no valid current-round packet.
    with monkeypatch.context() as patch:
        def old_design_contract(*args, **kwargs):
            raise ValueError(OLD_ERROR)
        patch.setattr(service, "_development_check_evidence", old_design_contract)
        _, value = design(service, rid, evidence)
    retain(service, rid, reserve(service, rid), audit(current(service.status(rid)), value, repair=True, ready=False))
    task = reserve(service, rid)
    assert task["purpose"] == "develop-repair"
    if damage == "unknown_variable":
        value["cases"][0]["alternatives"][0]["rules"][0]["guard"][0]["left"] = {"variable": "invented_variable"}
    elif damage == "planned_case":
        value["cases"][0]["id"] = "invented_case"
    with monkeypatch.context() as patch:
        def old_contract(*args, **kwargs):
            raise ValueError(OLD_ERROR)
        patch.setattr(service, "_development_check_evidence", old_contract)
        rejected = retain(service, rid, task, value)
    assert current(rejected)["calls"][-1]["outcome"] == "rejected"
    closed = service.finish_manuscript_improvement(rid)
    return task, value, closed


@pytest.mark.parametrize("development", [2], indirect=True)
@pytest.mark.parametrize("damage", [None, "unknown_variable", "planned_case"])
def test_exact_repair_admission_preserves_history_and_requires_reaudit(development, monkeypatch, damage):
    service, rid, _, _, evidence = development
    task, value, closed = reject_completed_repair(service, rid, evidence, monkeypatch, damage)
    before = current(closed)
    old_development = copy.deepcopy(before["research_development"])
    old_calls = copy.deepcopy(before["calls"])
    old_files = {key: service.artifact_path(rid, key).read_bytes() for key in closed["artifacts"]}
    assert before["counts"]["model_attempts"] == len(old_calls)
    repaired = service.repair_manuscript_improvement(rid)
    state = current(repaired)
    development_state = state["research_development"]
    proof_ref = development_state["evidence_admission_repairs"][task["call_id"]]
    proof = json.loads(service.artifact_path(rid, proof_ref["artifact_id"]).read_bytes())
    assert state["calls"] == old_calls
    assert state["counts"] == before["counts"] and state["policy"] == before["policy"]
    assert proof["remaining_authorized_requests"] == 3 and proof["additional_model_requests"] == 0
    assert development_state["evidence_failures"] == old_development["evidence_failures"]
    assert state.get("research_development_history") == before.get("research_development_history")
    for key, raw in old_files.items():
        assert repaired["artifacts"][key] == closed["artifacts"][key]
        assert service.artifact_path(rid, key).read_bytes() == raw
    if damage is None:
        from paper_factory.autonomous.research_development import DevelopmentResearchEvidence
        assert proof["outcome"] == "admitted" and not state["finished"]
        assert state["next_task"]["purpose"] == "develop-re-audit"
        assert len(development_state["evidence_versions"]) == len(old_development["evidence_versions"]) + 1
        result = json.loads(service.artifact_path(rid, development_state["evidence_artifact_id"]).read_bytes())
        assert result["value"] == DevelopmentResearchEvidence.model_validate(value).model_dump(mode="json")
        failure_id = proof["native_failure_artifact_id"]
        assert json.loads(service.artifact_path(rid, failure_id).read_bytes())["value"] == value
        assert development_state["audit"] == old_development["audit"]
        assert development_state["audit"]["evidence_sha256"] != development_state["evidence_sha256"]
        assert development_state["readiness"]["ready_to_write"] is False
        assert "repair_limit_reached" not in development_state
        assert development_state["previous_closures"][-1]["report_artifact_id"] == before["report_artifact_id"]
    else:
        assert proof["outcome"] == "rejected" and state["finished"]
        assert state["next_task"] is None
        assert development_state["evidence_versions"] == old_development["evidence_versions"]
        assert development_state.get("previous_closures") == old_development.get("previous_closures")
    snapshot = repaired["manuscript_improvement_snapshot"]
    assert service.repair_manuscript_improvement(rid)["manuscript_improvement_snapshot"] == snapshot


@pytest.mark.parametrize("development", [2], indirect=True)
@pytest.mark.parametrize("damage", ["failure_sha", "receipt", "budget", "downstream", "pending", "legacy", "unsupported_error"])
def test_repair_admission_cannot_reopen_wrong_binding_or_spend_new_authorization(development, monkeypatch, damage):
    from paper_factory import workflow as engine
    service, rid, _, _, evidence = development
    task, _, closed = reject_completed_repair(service, rid, evidence, monkeypatch)
    with service._operation(rid) as (ws, record):
        state = service._improvement_state(ws, record)
        dev = state["research_development"]
        if damage == "failure_sha":
            dev["latest_failed_candidate_sha256"] = "0" * 64
        elif damage == "budget":
            state["policy"]["model_call_limit"] = len(state["calls"]) + 2
        elif damage == "downstream":
            dev["completed_stages"].append("re-audit")
        elif damage == "pending":
            state["calls"][-1]["outcome"] = "reserved"
        elif damage == "legacy":
            dev["contract_version"] = 1
        elif damage == "unsupported_error":
            state["calls"][-1]["error"] = "A genuine unbound or unsupported scientific response"
        service._improvement_save(ws, record, state)
    baseline = current(service.status(rid))
    if damage == "receipt":
        verify = engine._verified_inference
        def wrong_receipt(*args, **kwargs):
            receipt = verify(*args, **kwargs)
            if receipt["id"] == task["call_id"] and receipt["outcome"] == "completed":
                return {**receipt, "prompt": receipt["prompt"] + " changed"}
            return receipt
        with monkeypatch.context() as patch:
            patch.setattr(engine, "_verified_inference", wrong_receipt)
            with pytest.raises(ValueError, match="exact"):
                service.repair_manuscript_improvement(rid)
    elif damage == "failure_sha":
        with pytest.raises(ValueError, match="exact"):
            service.repair_manuscript_improvement(rid)
    else:
        service.repair_manuscript_improvement(rid)
    after = current(service.status(rid))
    assert after["calls"] == baseline["calls"] and after["counts"] == baseline["counts"]
    assert after["finished"] and not after["research_development"].get("evidence_admission_repairs")
    assert after["research_development"]["evidence_versions"] == baseline["research_development"]["evidence_versions"]

"""One native schema repair on retained synthetic model receipts; no actual inference."""

import copy
import hashlib
import io
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from paper_factory import ipc
from paper_factory.autonomous.repository_portfolio import ANALYSIS_REPAIR_KEY
from paper_factory.workflow import WorkflowError, _inference_read
from test_repository_paper_workflow import study, analysis_value
from test_repository_portfolio import portfolio, unwritten_portfolio, retain_portfolio_response


def rejected_value(service, rid):
    value = analysis_value(service, rid)
    witness = value["source_evidence"][0]
    value["source_evidence"].extend([{**witness, "id": "open_path"}, {**witness, "id": "content_check"}])
    value["units"].append(copy.deepcopy(value["units"][0]))
    for unit, identifier, witness_id in zip(value["units"], ("clipboard_read", "clipboard_write"), ("open_path", "content_check")):
        unit["id"] = identifier
        unit["observations"][0]["evidence_ids"] = [witness_id]
    value["findings"][0]["unit_ids"] = [unit["id"] for unit in value["units"]]
    return value


@pytest.fixture
def rejected_portfolio(unwritten_portfolio):
    service, rid, _ = unwritten_portfolio
    value = rejected_value(service, rid)
    key, started = retain_portfolio_response(service, rid, value, "source-analysis")
    with pytest.raises(ValidationError):
        service.submit_portfolio_analysis(rid, {"inference_artifact_id": key, "analysis": value})
    return service, rid, value, key, started


def repair_material(service, rid, corruption=None):
    text = service.artifact_path(rid, ANALYSIS_REPAIR_KEY).read_bytes().decode("utf-8")
    body = {"artifact_id": ANALYSIS_REPAIR_KEY,
        "sha256": hashlib.sha256(text.encode()).hexdigest(), "text": text, **_inference_read(text)}
    if corruption == "text":
        body["text"] += " Synthetic injected change."
    elif corruption == "hash":
        body["sha256"] = "0" * 64
    elif corruption == "eof":
        body["pages"][-1]["nextOffset"] = 32000
    return lambda materials: materials.update({"portfolioAnalysisRepair": body}) if corruption != "omitted" else None


def corrected_value(value):
    value = copy.deepcopy(value)
    for unit in value["units"]:
        unit["evidence_ids"].extend(unit["observations"][0]["evidence_ids"])
    return value


def test_native_plan_keeps_full_original_rejection_and_repair_admits_once(rejected_portfolio):
    service, rid, rejected, key, _ = rejected_portfolio
    before = service.status(rid)
    old = {artifact: service.artifact_path(rid, artifact).read_bytes() for artifact in before["artifacts"]}
    original = json.loads(old[key])
    assert before["repository_paper"]["analysis_attempts"] == 1
    assert before["repository_paper"]["portfolio"]["analysis_repair_available"]
    assert before["repository_paper"]["portfolio"]["analysis_repair_candidate_artifact_id"] == key
    prepared = service.prepare_portfolio_analysis_repair(rid, key)
    portfolio = prepared["repository_paper"]["portfolio"]
    plan_bytes = service.artifact_path(rid, ANALYSIS_REPAIR_KEY).read_bytes()
    plan = json.loads(plan_bytes)
    assert plan["original_candidate"] == rejected and plan["original_candidate_text"] == original["text"]
    assert plan["original_inference_sha256"] == before["artifacts"][key]["sha256"]
    assert plan["original_prompt_sha256"] == original["promptSha256"]
    assert plan["validation_errors"][0]["msg"] == "Value error, Analysis observation evidence must bind unique existing identifiers"
    assert plan["validation_errors"][0]["loc"] == ["analysis"]
    assert [row["outside_unit_evidence_ids"] for row in plan["validation_details"]] == [["open_path"], ["content_check"]]
    assert portfolio["analysis_repair"]["status"] == "planned"
    assert portfolio["analysis_binding"]["analysis_schema_repair_sha256"] == portfolio["analysis_repair"]["sha256"]
    assert portfolio["analysis_binding"]["attempt"] == 2 and portfolio["analysis_outcome"] is None
    service.prepare_portfolio_analysis_repair(rid, key)
    assert service.artifact_path(rid, ANALYSIS_REPAIR_KEY).read_bytes() == plan_bytes
    value = corrected_value(rejected)
    repaired_key, started = retain_portfolio_response(service, rid, value, "source-analysis", material_change=repair_material(service, rid))
    saved = service.submit_portfolio_analysis(rid, {"inference_artifact_id": repaired_key, "analysis": value})
    assert saved["repository_paper"]["analysis_attempts"] == 2
    assert saved["repository_paper"]["portfolio"]["analysis_repair"]["status"] == "completed"
    assert saved["repository_paper"]["portfolio"]["analysis"] == value
    assert saved["repository_paper"]["portfolio"]["analysis_binding"] is None
    assert saved["execution_attempt"] == saved["draft_attempt"] == 0
    assert all(service.artifact_path(rid, artifact).read_bytes() == data for artifact, data in old.items())
    with pytest.raises(WorkflowError) as repeated:
        service.record_inference(rid, {**started, "id": str(uuid4())})
    assert repeated.value.code == "PORTFOLIO_ANALYSIS_LIMIT"


@pytest.mark.parametrize("outcome", [None, "failed", "interrupted"])
def test_failure_or_unknown_start_consumes_single_repair_without_new_binding(rejected_portfolio, outcome):
    service, rid, value, key, _ = rejected_portfolio
    service.prepare_portfolio_analysis_repair(rid, key)
    _, started = retain_portfolio_response(service, rid, corrected_value(value), "source-analysis",
        material_change=repair_material(service, rid), outcome=outcome)
    saved = service.prepare_portfolio_analysis_repair(rid, key)
    assert saved["repository_paper"]["analysis_attempts"] == 2
    assert saved["repository_paper"]["portfolio"]["analysis_repair"]["status"] == "incomplete"
    assert saved["repository_paper"]["portfolio"]["analysis_binding"] is None
    with pytest.raises(WorkflowError) as repeated:
        service.record_inference(rid, {**started, "id": str(uuid4())})
    assert repeated.value.code == "PORTFOLIO_ANALYSIS_LIMIT"
    assert service.status(rid)["repository_paper"]["analysis_attempts"] == 2


@pytest.mark.parametrize("corruption", ["text", "hash", "eof", "omitted"])
def test_whole_original_candidate_and_native_rejection_are_required_before_reservation(rejected_portfolio, corruption):
    service, rid, value, key, _ = rejected_portfolio
    service.prepare_portfolio_analysis_repair(rid, key)
    before = service.status(rid)
    with pytest.raises(WorkflowError) as failure:
        retain_portfolio_response(service, rid, corrected_value(value), "source-analysis", material_change=repair_material(service, rid, corruption))
    assert failure.value.code == "PORTFOLIO_ANALYSIS_REPAIR_READING_INVALID"
    after = service.status(rid)
    assert after["artifacts"] == before["artifacts"] and after["repository_paper"]["analysis_attempts"] == 1


def test_repaired_response_still_fails_strict_schema_and_cannot_be_repaired_again(rejected_portfolio):
    service, rid, value, key, _ = rejected_portfolio
    service.prepare_portfolio_analysis_repair(rid, key)
    repair_key, _ = retain_portfolio_response(service, rid, value, "source-analysis", material_change=repair_material(service, rid))
    with pytest.raises(ValidationError):
        service.submit_portfolio_analysis(rid, {"inference_artifact_id": repair_key, "analysis": value})
    saved = service.status(rid)
    assert saved["repository_paper"]["portfolio"]["analysis_repair"]["status"] == "incomplete"
    assert saved["repository_paper"]["portfolio"]["analysis_binding"] is None
    with pytest.raises(WorkflowError) as failure:
        service.prepare_portfolio_analysis_repair(rid, repair_key)
    assert failure.value.code == "PORTFOLIO_ANALYSIS_REPAIR_CONFLICT"
    assert service.status(rid)["repository_paper"]["analysis_attempts"] == 2


def test_schema_valid_response_and_missing_receipt_do_not_authorize_repair(unwritten_portfolio):
    service, rid, _ = unwritten_portfolio
    value = analysis_value(service, rid)
    key, _ = retain_portfolio_response(service, rid, value, "source-analysis")
    for supplied_key in (key, "model-evidence-invented-completed"):
        with pytest.raises(WorkflowError) as failure:
            service.prepare_portfolio_analysis_repair(rid, supplied_key)
        assert failure.value.code == "PORTFOLIO_ANALYSIS_REPAIR_UNAVAILABLE"
    assert ANALYSIS_REPAIR_KEY not in service.status(rid)["artifacts"]


@pytest.mark.parametrize("outcome", [None, "failed", "interrupted"])
def test_initial_transport_failure_does_not_authorize_a_schema_repair(unwritten_portfolio, outcome):
    service, rid, _ = unwritten_portfolio
    value = rejected_value(service, rid)
    key, _ = retain_portfolio_response(service, rid, value, "source-analysis", outcome=outcome)
    saved = service.status(rid)
    assert not saved["repository_paper"]["portfolio"]["analysis_repair_available"]
    with pytest.raises(WorkflowError) as failure:
        service.prepare_portfolio_analysis_repair(rid, key)
    assert failure.value.code == "PORTFOLIO_ANALYSIS_REPAIR_UNAVAILABLE"
    assert service.status(rid)["repository_paper"]["analysis_attempts"] == 1


def test_initial_repair_spends_last_shared_attempt_after_retained_base_analysis(portfolio):
    service, rid, _, _ = portfolio
    original_counts = service.status(rid)
    assert original_counts["repository_paper"]["analysis_attempts"] == 1
    rejected = rejected_value(service, rid)
    key, _ = retain_portfolio_response(service, rid, rejected, "source-analysis")
    prepared = service.prepare_portfolio_analysis_repair(rid, key)
    assert prepared["repository_paper"]["portfolio"]["analysis_binding"]["attempt"] == 3
    value = corrected_value(rejected)
    repaired_key, _ = retain_portfolio_response(service, rid, value, "source-analysis", material_change=repair_material(service, rid))
    saved = service.submit_portfolio_analysis(rid, {"inference_artifact_id": repaired_key, "analysis": value})
    assert saved["repository_paper"]["analysis_attempts"] == 3
    assert saved["draft_attempt"] == original_counts["draft_attempt"]
    assert saved["study_literature_attempt"] == original_counts["study_literature_attempt"]
    assert saved["execution_attempt"] == original_counts["execution_attempt"] == 0


def test_source_witness_and_exact_model_response_are_still_required(rejected_portfolio):
    service, rid, rejected, key, _ = rejected_portfolio
    service.prepare_portfolio_analysis_repair(rid, key)
    value = corrected_value(rejected)
    value["source_evidence"][0]["quote"] = "Invented literal source witness that never occurred in the retained source."
    repaired_key, _ = retain_portfolio_response(service, rid, value, "source-analysis", material_change=repair_material(service, rid))
    with pytest.raises(WorkflowError) as invalid_witness:
        service.submit_portfolio_analysis(rid, {"inference_artifact_id": repaired_key, "analysis": value})
    assert invalid_witness.value.code == "SOURCE_EVIDENCE_INVALID"
    changed = corrected_value(rejected)
    with pytest.raises(WorkflowError) as changed_response:
        service.submit_portfolio_analysis(rid, {"inference_artifact_id": repaired_key, "analysis": changed})
    assert changed_response.value.code == "PORTFOLIO_RESPONSE_CHANGED"
    saved = service.status(rid)["repository_paper"]["portfolio"]
    assert saved["analysis"] is None and saved["analysis_binding"] is None
    assert saved["analysis_repair"]["status"] == "incomplete"
    assert saved["analysis_repair"]["repair_validation_errors"][0]["type"] == "SOURCE_EVIDENCE_INVALID"


def test_prepare_analysis_repair_ipc_uses_only_retained_identity():
    calls = []
    service = SimpleNamespace(prepare_portfolio_analysis_repair=lambda rid, key: calls.append((rid, key)) or {"ok": True})
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), io.BytesIO())
    try:
        message = {"id": "repair", "method": "workflow.preparePortfolioAnalysisRepair",
            "params": {"researchId": "research-abcdefabcdef", "inferenceArtifactId": "retained"}}
        assert ipc.request(json.dumps(message).encode()) == message
        assert dispatcher.execute(message["method"], message["params"]) == {"ok": True}
        assert calls == [("research-abcdefabcdef", "retained")]
        for extra in ({"reset": True}, {"validationErrors": []}, {"analysisBudget": 10}):
            with pytest.raises(ValueError):
                ipc.request(json.dumps({**message, "params": {**message["params"], **extra}}).encode())
    finally:
        dispatcher._pool.shutdown(wait=True)

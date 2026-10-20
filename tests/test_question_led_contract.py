"""A constructive question-led round spends at most its original six requests."""
from copy import deepcopy

from paper_factory.autonomous.research_development import development_next_task, development_readiness
from paper_factory.autonomous.finite_rules import check_evidence


def state(stages, *, strengthen=False, ready=False):
    return {"finished": False, "policy": {"model_call_limit": 30},
        "calls": [{"purpose": "historical", "round_id": "older", "outcome": "completed"} for _ in range(24)] +
            [{"purpose": "develop-" + stage, "round_id": "new", "outcome": "completed"} for stage in stages],
        "research_development": {"id": "new", "contract_version": 3, "closed": False,
            "additional_call_limit": 6, "authorized_model_call_limit": 30,
            "completed_stages": stages, "strengthening_needed": strengthen,
            "selected_question": {"id": "answerable"}, "evidence_artifact_id": "actual-evidence",
            "evidence_sha256": "current", "work_product_report_artifact_id": "actual-work",
            "audit_artifact_id": "audit" if ready else None, "audit_sha256": "audit-sha" if ready else None,
            "audit": {"evidence_sha256": "current", "ready_to_write": ready, "repair_required": False}}}


def test_six_requests_include_new_evidence_strengthening_before_independent_audit():
    value = state(["question", "design"], strengthen=True)
    before = deepcopy(value)
    assert development_next_task(value)["purpose"] == "develop-strengthen"
    assert value == before
    value = state(["question", "design", "strengthen"], strengthen=True)
    assert development_next_task(value)["purpose"] == "develop-audit"
    assert development_next_task(state(["question", "design", "strengthen", "audit"], strengthen=True, ready=True))["purpose"] == "develop-write"
    assert development_next_task(state(["question", "design", "strengthen", "audit", "write"], strengthen=True, ready=True))["purpose"] == "develop-review"
    assert development_next_task(state(["question", "design", "strengthen", "audit", "write", "review"], strengthen=True, ready=True)) is None


def test_five_requests_are_enough_without_strengthening_and_unanswerable_question_stops():
    value = state(["question", "design"])
    assert development_next_task(value)["purpose"] == "develop-audit"
    assert development_next_task(state(["question", "design", "audit"])) is None
    value["research_development"]["selected_question"] = None
    assert development_next_task(value) is None
    assert development_readiness(value["research_development"])["reason"] == "no_answerable_question_from_retained_evidence"
    assert development_next_task(state(["question", "design", "audit", "write", "review"], ready=True)) is None


def test_generic_source_comparison_never_claims_a_finite_experiment():
    result = check_evidence({"method_scope": "source_comparison_not_project_execution",
        "source_evidence": [{"id": "actual-source"}], "document_evidence": [], "cases": []}, {"actual-source"})
    assert result["kind"] == "native_source_comparison_bindings"
    assert result["cases"] == [] and result["project_execution"] is False
    assert "No finite model or project was executed" in result["scope"]

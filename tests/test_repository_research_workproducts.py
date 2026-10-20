"""New first-draft research work, using synthetic sources and no model service."""

import copy
import json

import pytest

from paper_factory.workflow import WorkflowError
from test_repository_portfolio import (
    analyze_portfolio, draft, retain_portfolio_response, unwritten_portfolio,
)
from test_repository_paper_workflow import analysis_value, study


def test_new_study_requires_completed_work_in_first_analysis(unwritten_portfolio):
    service, rid, status = unwritten_portfolio
    portfolio = status["repository_paper"]["portfolio"]
    assert portfolio["research_workproducts_contract"] == 1
    assert portfolio["analysis_binding"]["research_workproducts_contract"] == 1
    assert "work_products" in status["schemas"]["repository_analysis"]["required"]
    value = analysis_value(service, rid)
    key, _ = retain_portfolio_response(service, rid, value, "source-analysis", include_work_products=False)
    with pytest.raises(ValueError, match="work_products"):
        service.submit_portfolio_analysis(rid, {"inference_artifact_id": key, "analysis": value})
    retained = service.status(rid)
    assert retained["repository_paper"]["portfolio"]["analysis"] is None
    assert retained["repository_paper"]["portfolio"]["analysis_repair_available"]
    assert retained["repository_paper"]["analysis_attempts"] == 1
    assert retained["code_attempt"] == retained["execution_attempt"] == 0
    assert key in retained["artifacts"]


def test_initial_analysis_freezes_native_decision_matrix_and_honest_limits(unwritten_portfolio):
    service, rid, _ = unwritten_portfolio
    status = analyze_portfolio(service, rid)
    portfolio = status["repository_paper"]["portfolio"]
    report = portfolio["work_products_report"]
    assert report["internal_consistency_passed"]
    assert not report["implementation_validated"]
    assert not report["publication_quality_assessed"]
    assert report["audit_required"]
    assert report["evidence_limits"]
    assert "current" in report["markdown"] and "proposed" in report["markdown"]
    frozen = json.loads(service.artifact_path(rid, portfolio["analysis_artifact_id"]).read_bytes())
    assert frozen["work_products_report"] == report
    assert frozen["value"]["work_products"]["products"][0]["changed_decisions"]


def test_retained_model_level_rejection_keeps_original_submission_location(unwritten_portfolio):
    service, rid, _ = unwritten_portfolio
    value = analysis_value(service, rid)
    value["units"][0]["observations"][0]["evidence_ids"] = ["undeclared-witness"]
    key, _ = retain_portfolio_response(service, rid, value, "source-analysis")
    with pytest.raises(ValueError):
        service.submit_portfolio_analysis(rid, {"inference_artifact_id": key, "analysis": value})
    status = service.status(rid)
    assert status["repository_paper"]["portfolio"]["analysis_repair_available"]
    service.prepare_portfolio_analysis_repair(rid, key)
    retained = service.status(rid)["repository_paper"]["portfolio"]["analysis_repair"]
    assert retained["validation_errors"][0]["loc"] == ["analysis"]


def test_valid_optional_work_product_fields_do_not_change_original_model_response(unwritten_portfolio):
    service, rid, _ = unwritten_portfolio
    value = analysis_value(service, rid)
    from test_repository_portfolio import work_products_fixture
    value["work_products"] = work_products_fixture(value["source_evidence"][0]["id"])
    decision = value["work_products"]["products"][0]["changed_decisions"][0]
    del decision["prior_method_evidence_ids"]
    del decision["result_refs"]
    key, _ = retain_portfolio_response(service, rid, value, "source-analysis")
    saved = service.submit_portfolio_analysis(rid, {"inference_artifact_id": key, "analysis": value})
    assert saved["repository_paper"]["portfolio"]["work_products_report"]["internal_consistency_passed"]
    original = json.loads(service.artifact_path(rid, key).read_bytes())["text"]
    assert "prior_method_evidence_ids" not in original


@pytest.mark.parametrize("damage", ["omit", "digest", "truncate"])
def test_first_writer_cannot_spend_call_without_exact_completed_research(unwritten_portfolio, damage):
    service, rid, _ = unwritten_portfolio
    status = analyze_portfolio(service, rid)
    before = copy.deepcopy(status["artifacts"])
    venue = status["repository_paper"]["portfolio"]["targets"][0]["venue_id"]
    def alter(materials):
        if damage == "omit":
            del materials["portfolioResearchWork"]
        elif damage == "digest":
            materials["portfolioResearchWork"]["sha256"] = "0" * 64
        else:
            materials["portfolioResearchWork"]["text"] = "Truncated synthetic research."
    with pytest.raises(WorkflowError) as error:
        retain_portfolio_response(service, rid, draft(service, rid, prepare_analysis=False),
            "venue-manuscript", venue, material_change=alter)
    assert error.value.code == "PORTFOLIO_RESEARCH_WORK_READING_INVALID"
    after = service.status(rid)
    assert after["artifacts"] == before
    assert after["repository_paper"]["portfolio"]["venues"][0]["draft_attempts"] == 0

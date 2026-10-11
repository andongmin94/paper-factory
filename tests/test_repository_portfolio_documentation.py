"""Comparison acquisition and local repair use immutable synthetic temporary studies only."""

import json

import pytest

from paper_factory.workflow import WorkflowError, _inference_read
from test_repository_paper_workflow import study, draft, review, reference_selection, fetched_document
from test_repository_portfolio import unwritten_portfolio, analyze_portfolio, retain_portfolio_response
from test_repository_portfolio_revision import retain_revision_response


def comparison_selection(url="https://docs.example.org/first-comparison"):
    return {**reference_selection(url), "venue_suggestions": []}


def submit_article(service, rid, venue_id):
    value = draft(service, rid, prepare_analysis=False)
    key, _ = retain_portfolio_response(service, rid, value, "venue-manuscript", venue_id)
    return service.submit_portfolio_manuscript(rid, {
        "venue_id": venue_id, "inference_artifact_id": key, "manuscript": value})


def submit_assessment(service, rid, venue_id, *, documentation=False, analytical=False):
    assessment = review(not documentation)
    if documentation:
        assessment["next_actions"] = [{"action": "retrieve_documentation", "target": "Actual comparison documentation",
            "required_change": "Retrieve the complete public comparison documentation and connect its documented boundary to the retained source.",
            "verification": "The revised manuscript quotes the actual retained whole document and qualifies that no code was executed."}]
        if analytical:
            assessment["content_assessment"]["next_actions"].append({"action": "revise_source_analysis", "target": "Configuration observation",
                "required_change": "Clarify the retained analytical boundary from literal witnesses without asserting any measured effect.",
                "verification": "The actual changed analysis must retain unique existing source evidence identifiers."})
    key, _ = retain_portfolio_response(service, rid, assessment, "venue-manuscript-review", venue_id)
    return service.submit_portfolio_review(rid, {
        "venue_id": venue_id, "inference_artifact_id": key, "review": assessment})


def first_reviews(service, rid, *, documentation=False, pending=False, analytical=False):
    analyze_portfolio(service, rid)
    submit_article(service, rid, "ieee-software")
    submit_assessment(service, rid, "ieee-software", documentation=documentation, analytical=analytical)
    if pending:
        retain_portfolio_response(service, rid, draft(service, rid, prepare_analysis=False),
            "venue-manuscript", "ieee-security-privacy", outcome=None)
    else:
        submit_article(service, rid, "ieee-security-privacy")
        submit_assessment(service, rid, "ieee-security-privacy")
    return service.status(rid)


def test_initial_portfolio_comparison_documentation_is_available_before_any_analysis(unwritten_portfolio, monkeypatch):
    service, rid, original = unwritten_portfolio
    monkeypatch.setattr("paper_factory.submission_requirements.fetch_requirements", fetched_document)
    saved = service.collect_repository_references(rid, comparison_selection())
    source = saved["repository_paper"]["references"][0]
    assert source["status"] == "retained" and source["purpose"] == "comparison"
    material = service.read_material(rid, "evidence", source["text_artifact_id"])
    assert material["sha256"] == source["text_sha256"]
    assert saved["material_manifest"]["references"][0]["body_range"]["end"] == material["total_chars"]
    intent = json.loads(service.artifact_path(rid, "repository-reference-intent-1").read_bytes())
    assert intent["portfolio_remediation"] == {"portfolio_start_sha256": original["artifacts"]["repository-portfolio-start"]["sha256"],
        "analysis_sha256": None, "reviews": []}
    assert saved["repository_paper"]["analysis_attempts"] == saved["draft_attempt"] == saved["execution_attempt"] == 0
    assert not saved["repository_paper"]["portfolio"]["documentation_followup_available"]
    assert all(saved["artifacts"][key] == value for key, value in original["artifacts"].items())
    chosen = comparison_selection("https://docs.example.org/invalid-purpose")
    chosen["references"][0]["purpose"] = "venue"
    with pytest.raises(WorkflowError) as error:
        service.collect_repository_references(rid, chosen)
    assert error.value.code == "PORTFOLIO_DOCUMENTATION_SCOPE"
    assert service.status(rid)["artifacts"] == saved["artifacts"]


def test_first_post_analysis_collection_cannot_bypass_actual_negative_documentation_feedback(unwritten_portfolio):
    service, rid, _ = unwritten_portfolio
    before = first_reviews(service, rid)
    assert not before["repository_paper"]["portfolio"]["documentation_followup_available"]
    assert not before["repository_paper"]["reference_collections"]
    with pytest.raises(WorkflowError) as error:
        service.collect_repository_references(rid, comparison_selection())
    assert error.value.code == "REVIEW_REMEDIATION_REQUIRED"
    assert service.status(rid)["artifacts"] == before["artifacts"]


def test_actual_documentation_request_waits_for_pending_original_other_article(unwritten_portfolio):
    service, rid, _ = unwritten_portfolio
    before = first_reviews(service, rid, documentation=True, pending=True)
    assert not before["repository_paper"]["portfolio"]["documentation_followup_available"]
    with pytest.raises(WorkflowError) as error:
        service.collect_repository_references(rid, comparison_selection())
    assert error.value.code == "PORTFOLIO_REVISION_PENDING"
    assert service.status(rid)["artifacts"] == before["artifacts"]


@pytest.mark.parametrize("outcome", ["retained", "failed", "interrupted"])
def test_review_bound_docs_are_spent_once_and_only_complete_bodies_enable_local_rewrite(unwritten_portfolio, monkeypatch, outcome):
    service, rid, _ = unwritten_portfolio
    before = first_reviews(service, rid, documentation=True, analytical=outcome == "retained")
    if outcome == "retained":
        # Preserve an actual completed but invalid common repair, as happened
        # during the Electron run. New docs must still repair local articles
        # against the retained first analysis without spending analysis3.
        service.prepare_portfolio_revision(rid)
        value = dict(before["repository_paper"]["portfolio"]["analysis"])
        value["method"] += " This invalid synthetic repair cannot replace the valid first analysis."
        value["units"] = json.loads(json.dumps(value["units"]))
        value["units"][0]["observations"][0]["evidence_ids"] = ["not_an_existing_evidence_identifier"]
        key, _ = retain_revision_response(service, rid, value)
        with pytest.raises(ValueError, match="unique existing identifiers"):
            service.submit_portfolio_analysis(rid, {"inference_artifact_id": key, "analysis": value})
        before = service.status(rid)
    portfolio = before["repository_paper"]["portfolio"]
    assert portfolio["documentation_followup_available"]
    assert portfolio["venues"][0]["writer_binding"] is None
    original = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}

    def fetch(url):
        if outcome == "interrupted":
            raise KeyboardInterrupt("Synthetic fetch interruption after the immutable intent is retained")
        if outcome == "failed":
            return {"status": "failed", "http_status": 403, "content_type": "text/plain",
                "raw": b"Synthetic unavailable documentation", "error": "Synthetic refusal"}
        return fetched_document(url)

    monkeypatch.setattr("paper_factory.submission_requirements.fetch_requirements", fetch)
    if outcome == "interrupted":
        with pytest.raises(KeyboardInterrupt):
            service.collect_repository_references(rid, comparison_selection())
        saved = service.status(rid)
    else:
        saved = service.collect_repository_references(rid, comparison_selection())
    intent = json.loads(service.artifact_path(rid, "repository-reference-intent-1").read_bytes())
    assert intent["portfolio_remediation"] == {"portfolio_start_sha256": portfolio["sha256"],
        "analysis_sha256": portfolio["analysis_sha256"],
        "reviews": [{"venue_id": venue["venue_id"], "draft_sha256": venue["draft_sha256"],
            "review_sha256": before["artifacts"][venue["artifact_ids"]["review"]]["sha256"]} for venue in portfolio["venues"]]}
    assert not saved["repository_paper"]["portfolio"]["documentation_followup_available"]
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in original.items())
    assert saved["repository_paper"]["analysis_attempts"] == before["repository_paper"]["analysis_attempts"]
    assert saved["draft_attempt"] == saved["execution_attempt"] == 0
    with pytest.raises(WorkflowError) as repeat:
        service.collect_repository_references(rid, comparison_selection("https://docs.example.org/repeated-feedback"))
    assert repeat.value.code == "REVIEW_REMEDIATION_REQUIRED"
    assert service.status(rid)["artifacts"] == saved["artifacts"]
    if outcome != "retained":
        assert saved["repository_paper"]["portfolio"]["venues"][0]["writer_binding"] is None
        return

    source = saved["repository_paper"]["references"][0]
    actual_text = service.artifact_path(rid, source["text_artifact_id"]).read_bytes().decode("utf-8")
    assert saved["repository_paper"]["portfolio"]["venues"][0]["writer_binding"]["attempt"] == 2
    assert saved["repository_paper"]["portfolio"]["venues"][1]["writer_binding"] is None
    value = draft(service, rid, prepare_analysis=False)
    value["document_evidence"] = [{"source_id": source["id"], "text_sha256": source["text_sha256"],
        "quote": "separate from the native process adapter", "interpretation":
        "The unchanged complete synthetic documentation describes a boundary; the fixture proves no actual runtime or publication outcome."}]
    value["sections"][2]["text"] += " This newly retained documented comparison qualifies the source {{document:" + source["id"] + "}}."
    value["revision"] = {"prior_draft_sha256": portfolio["venues"][0]["draft_sha256"],
        "changes": ["Added the actual complete comparison document and qualified the static source observation without executing any code."]}

    def materials(materials):
        materials["retainedReferences"] = [{"source_id": source["id"], "name": source["text_artifact_id"],
            "sha256": source["text_sha256"], "url": source["url"], "purpose": source["purpose"],
            "text": actual_text, **_inference_read(actual_text)}]

    key, _ = retain_portfolio_response(service, rid, value, "venue-manuscript", "ieee-software", material_change=materials)
    service.submit_portfolio_manuscript(rid, {"venue_id": "ieee-software", "inference_artifact_id": key, "manuscript": value})
    key, _ = retain_portfolio_response(service, rid, review(True), "venue-manuscript-review", "ieee-software", material_change=materials)
    done = service.submit_portfolio_review(rid, {"venue_id": "ieee-software", "inference_artifact_id": key, "review": review(True)})
    assert done["repository_paper"]["analysis_attempts"] == before["repository_paper"]["analysis_attempts"] == 2
    assert done["repository_paper"]["portfolio"]["analysis_sha256"] == portfolio["analysis_sha256"]
    assert done["repository_paper"]["portfolio"]["venues"][0]["draft_attempts"] == 2
    assert done["repository_paper"]["portfolio"]["venues"][0]["review_attempts"] == 2
    assert done["repository_paper"]["portfolio"]["venues"][1]["draft_attempts"] == 1
    assert done["repository_paper"]["portfolio"]["analysis_revision"]["status"] == "planned"
    assert not done["repository_paper"]["portfolio"]["analysis_revision_required"]
    assert done["repository_paper"]["portfolio"]["analysis_binding"] is None
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in original.items())

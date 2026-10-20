"""Actual native admissions on synthetic temporary studies; no model or project execution."""

import copy
import hashlib
import io
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from paper_factory import ipc
from paper_factory.autonomous.repository_portfolio import REVISION_KEY, PORTFOLIO_MARKER, MATERIAL_HEADER, portfolio_frame
from paper_factory.workflow import WorkflowError, _inference_read
from test_repository_paper_workflow import study, draft, review
from test_repository_portfolio import (
    portfolio, analyze_portfolio, retain_portfolio_response, interrupted_portfolio_writer,
)


@pytest.fixture
def reviewed_portfolio(portfolio, request):
    service, rid, _, _ = portfolio
    if isinstance(getattr(request, "param", None), dict) and request.param.get("precollect"):
        service.collector = lambda queries, root, **kwargs: {"sources": [], "searches": [{"query": query} for query in queries],
            "warnings": [], "pdf_reservations": [{"identity": "doi:10.1234/synthetic-extra-" + str(n),
                "url": "https://example.org/synthetic-" + str(n) + ".pdf", "pdf_attempted": True} for n in (1, 2)] if kwargs["pdf_reservation_limit"] else []}
        service.collect_portfolio_literature(rid, ["a distinct synthetic primary search before common analysis"])
        service.collect_portfolio_literature(rid, ["a second distinct synthetic primary search before common analysis"])
    current = analyze_portfolio(service, rid)
    value = draft(service, rid, prepare_analysis=False)
    for index, target in enumerate(current["repository_paper"]["portfolio"]["targets"]):
        venue_id = target["venue_id"]
        key, _ = retain_portfolio_response(service, rid, value, "venue-manuscript", venue_id)
        service.submit_portfolio_manuscript(rid, {"venue_id": venue_id, "inference_artifact_id": key, "manuscript": value})
        assessment = review(index != 0)
        if index == 1 and isinstance(getattr(request, "param", None), dict) and request.param.get("human_elsewhere"):
            assessment = review(False)
            assessment["content_assessment"]["next_actions"] = [{"action": "human_validation", "target": "Synthetic S&P independent validation",
                "required_change": "Obtain actual independent validation only for this synthetic journal contribution; no validation has occurred.",
                "verification": "Retain real independent judgments before claiming validated scientific contribution."}]
        if index == 0 and getattr(request, "param", False):
            assessment["content_assessment"]["literature_queries"] = ["a synthetic closest-method body comparison"]
            assessment["content_assessment"]["next_actions"] = [{"action": "retrieve_literature", "target": "Closest primary method",
                "required_change": "Retrieve and inspect an actual closest primary scholarly body; this fixture does not fulfill that retrieval.",
                "verification": "Retain full primary text and exact source-bound comparison before asserting originality."}]
        key, _ = retain_portfolio_response(service, rid, assessment, "venue-manuscript-review", venue_id)
        service.submit_portfolio_review(rid, {"venue_id": venue_id, "inference_artifact_id": key, "review": assessment})
    return service, rid


def revised_analysis(service, rid):
    value = copy.deepcopy(service.status(rid)["repository_paper"]["portfolio"]["analysis"])
    value["method"] += " This explicitly synthetic repair separately analyzes request authority and native-effect authority; no new case, runtime outcome or human validation is claimed."
    value["units"][0]["observations"][0]["finding"] += " This changed interpretation remains restricted to the literal retained configuration expression."
    return value


def retain_revision_response(service, rid, value, *, corruption=None, outcome="completed"):
    revision = service.status(rid)["repository_paper"]["portfolio"]["analysis_revision"]
    text = service.artifact_path(rid, revision["artifact_id"]).read_bytes().decode("utf-8")
    def materials_change(materials):
        body = {"artifact_id": revision["artifact_id"], "sha256": revision["sha256"], "text": text, **_inference_read(text)}
        if corruption == "text":
            body["text"] = text + " Invented reviewer instruction."
        elif corruption == "hash":
            body["sha256"] = "0" * 64
        elif corruption == "eof":
            body["pages"][-1]["nextOffset"] = 32000
        elif corruption == "omitted":
            return
        materials["portfolioRevision"] = body
    return retain_portfolio_response(service, rid, value, "source-analysis", material_change=materials_change, outcome=outcome)


def test_common_repair_plan_is_deterministic_review_bound_and_append_only(reviewed_portfolio):
    service, rid = reviewed_portfolio
    before = service.status(rid)
    original = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    assert before["repository_paper"]["portfolio"]["analysis_revision_available"]
    saved = service.prepare_portfolio_revision(rid)
    portfolio = saved["repository_paper"]["portfolio"]
    revision = portfolio["analysis_revision"]
    plan_bytes = service.artifact_path(rid, REVISION_KEY).read_bytes()
    plan = json.loads(plan_bytes)
    assert revision["status"] == "planned" and revision["prior_analysis_sha256"] == before["repository_paper"]["portfolio"]["analysis_sha256"]
    assert len(plan["reviews"]) == 2 and revision["affected_venues"] == [row["venue_id"] for row in portfolio["targets"]]
    assert any(item["action"] == "revise_source_analysis" for item in revision["actions"])
    assert len({json.dumps(item, sort_keys=True) for item in revision["actions"]}) == len(revision["actions"])
    for row in plan["reviews"]:
        assert row["review"] == json.loads(original[row["review_artifact_id"]])
        assert row["review_sha256"] == before["artifacts"][row["review_artifact_id"]]["sha256"]
    assert portfolio["analysis_binding"]["analysis_revision_sha256"] == revision["sha256"]
    assert portfolio["analysis_binding"]["attempt"] == 3 and portfolio["analysis_outcome"] is None
    service.prepare_portfolio_revision(rid)
    assert service.artifact_path(rid, REVISION_KEY).read_bytes() == plan_bytes
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in original.items())
    assert saved["execution_attempt"] == before["execution_attempt"] == 0
    assert saved["draft_attempt"] == before["draft_attempt"] and saved["study_literature_attempt"] == before["study_literature_attempt"]
    assert saved["repository_paper"]["analysis_attempts"] == before["repository_paper"]["analysis_attempts"] == 2


def test_actual_changed_analysis_uses_last_shared_attempt_and_old_passes_become_historical(reviewed_portfolio):
    service, rid = reviewed_portfolio
    before = service.status(rid)
    original = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    prepared = service.prepare_portfolio_revision(rid)
    value = revised_analysis(service, rid)
    key, started = retain_revision_response(service, rid, value)
    pending = service.status(rid)["repository_paper"]["portfolio"]
    assert pending["analysis_outcome"] == "completed" and pending["analysis_revision"]["status"] == "planned"
    saved = service.submit_portfolio_analysis(rid, {"inference_artifact_id": key, "analysis": value})
    portfolio = saved["repository_paper"]["portfolio"]
    result_key = "repository-portfolio-analysis-revision-3"
    assert portfolio["analysis"] == value and portfolio["analysis_sha256"] == saved["artifacts"][result_key]["sha256"]
    assert saved["repository_paper"]["analysis_attempts"] == 3
    assert portfolio["analysis_revision"]["status"] == "completed" and not portfolio["analysis_revision_required"]
    assert not portfolio["analysis_revision_available"] and portfolio["analysis_binding"] is None
    assert all(not row["analysis_current"] and not row["scientific_ready"] and not row["content_ready"] for row in portfolio["venues"])
    assert portfolio["venues"][0]["revise_available"] and portfolio["venues"][0]["writer_binding"]["attempt"] == 2
    assert all(row["writer_binding"] is None for row in portfolio["venues"][1:])
    assert portfolio["venues"][1]["review"] == before["repository_paper"]["portfolio"]["venues"][1]["review"]
    assert all(service.artifact_path(rid, artifact).read_bytes() == raw for artifact, raw in original.items())
    result = json.loads(service.artifact_path(rid, result_key).read_bytes())
    assert not result["research_incomplete"] and result["unfulfilled_actions"] == []
    assert result["prior_analysis_sha256"] == prepared["repository_paper"]["portfolio"]["analysis_sha256"]
    with pytest.raises(WorkflowError) as repeated:
        service.record_inference(rid, {**started, "id": str(uuid4())})
    assert repeated.value.code == "PORTFOLIO_ANALYSIS_LIMIT"
    old = json.loads(original["repository-portfolio-" + portfolio["venues"][1]["venue_id"] + "-review-1"])
    with service._operation(rid) as (ws, record):
        assert service._portfolio_binding(ws, record, "venue-manuscript-review", portfolio["venues"][1]["venue_id"], 1,
            analysis_basis=old["reviewer_bindings"]) == old["reviewer_bindings"]
        held = service._portfolio_binding(ws, record, "venue-manuscript", portfolio["venues"][0]["venue_id"], 2)
    prior = service.status(rid)
    _, materials = portfolio_frame(started["prompt"])
    text = service.artifact_path(rid, result_key).read_bytes().decode("utf-8")
    materials["portfolioResearchWork"] = {"artifact_id": result_key,
        "sha256": held["portfolio_analysis_sha256"], "text": text, **_inference_read(text)}
    prompt = "Synthetic held targeted writer. " + PORTFOLIO_MARKER + json.dumps(held) + MATERIAL_HEADER + json.dumps(materials)
    with pytest.raises(WorkflowError) as held_writer:
        service.record_inference(rid, {**started, "id": str(uuid4()), "phase": "venue-manuscript",
            "prompt": prompt, "promptSha256": hashlib.sha256(prompt.encode()).hexdigest()})
    assert held_writer.value.code == "PORTFOLIO_DRAFT_READING_INVALID"
    assert service.status(rid)["repository_paper"]["analysis_attempts"] == prior["repository_paper"]["analysis_attempts"]


@pytest.mark.parametrize("corruption", ["text", "hash", "eof", "omitted"])
def test_repair_requires_actual_whole_review_plan_text_hash_and_eof(reviewed_portfolio, corruption):
    service, rid = reviewed_portfolio
    service.prepare_portfolio_revision(rid)
    value = revised_analysis(service, rid)
    key, _ = retain_revision_response(service, rid, value, corruption=corruption)
    with pytest.raises(WorkflowError) as failure:
        service.submit_portfolio_analysis(rid, {"inference_artifact_id": key, "analysis": value})
    assert failure.value.code == "PORTFOLIO_REVISION_READING_INVALID"
    saved = service.status(rid)
    assert "repository-portfolio-analysis-revision-3" not in saved["artifacts"] and saved["repository_paper"]["analysis_attempts"] == 3


def test_unchanged_analysis_is_not_a_completed_research_repair(reviewed_portfolio):
    service, rid = reviewed_portfolio
    old = service.status(rid)["repository_paper"]["portfolio"]["analysis"]
    service.prepare_portfolio_revision(rid)
    key, _ = retain_revision_response(service, rid, old)
    with pytest.raises(WorkflowError) as failure:
        service.submit_portfolio_analysis(rid, {"inference_artifact_id": key, "analysis": old})
    assert failure.value.code == "ANALYSIS_UNCHANGED"
    assert service.status(rid)["repository_paper"]["portfolio"]["analysis_revision"]["status"] == "planned"


@pytest.mark.parametrize("reviewed_portfolio", [True], indirect=True)
def test_admitted_new_analysis_does_not_complete_actual_retained_literature_action(reviewed_portfolio):
    service, rid = reviewed_portfolio
    before = service.status(rid)
    service.prepare_portfolio_revision(rid)
    value = revised_analysis(service, rid)
    key, _ = retain_revision_response(service, rid, value)
    saved = service.submit_portfolio_analysis(rid, {"inference_artifact_id": key, "analysis": value})
    portfolio = saved["repository_paper"]["portfolio"]
    assert portfolio["analysis"] == value and portfolio["analysis_revision"]["status"] == "incomplete"
    assert portfolio["analysis_binding"] is None and not portfolio["analysis_revision_available"]
    assert saved["repository_paper"]["analysis_attempts"] == 3
    result = json.loads(service.artifact_path(rid, "repository-portfolio-analysis-revision-3").read_bytes())
    assert result["research_incomplete"] and [item["action"] for item in result["unfulfilled_actions"]] == ["retrieve_literature"]
    assert saved["study_literature_attempt"] == before["study_literature_attempt"] and saved["execution_attempt"] == 0
    assert all(not row["content_ready"] for row in portfolio["venues"])
    assert portfolio["venues"][0]["revise_available"] and portfolio["venues"][0]["writer_binding"]["attempt"] == 2
    assert all(row["writer_binding"] is None for row in portfolio["venues"][1:])


@pytest.mark.parametrize("outcome", ["failed", "interrupted"])
def test_failed_repair_remains_counted_incomplete_and_never_reserves_another_request(reviewed_portfolio, outcome):
    service, rid = reviewed_portfolio
    service.prepare_portfolio_revision(rid)
    original = service.artifact_path(rid, REVISION_KEY).read_bytes()
    _, started = retain_revision_response(service, rid, revised_analysis(service, rid), outcome=outcome)
    saved = service.status(rid)
    assert saved["repository_paper"]["analysis_attempts"] == 3
    assert saved["repository_paper"]["portfolio"]["analysis_revision"]["status"] == "incomplete"
    assert saved["repository_paper"]["portfolio"]["analysis_binding"] is None
    service.prepare_portfolio_revision(rid)
    assert service.artifact_path(rid, REVISION_KEY).read_bytes() == original
    with pytest.raises(WorkflowError) as failure:
        service.record_inference(rid, {**started, "id": str(uuid4())})
    assert failure.value.code == "PORTFOLIO_ANALYSIS_LIMIT"


@pytest.mark.parametrize("outcome", [None, "completed"])
def test_prepare_holds_unknown_start_and_completed_unadmitted_original_writer(reviewed_portfolio, outcome):
    service, rid = reviewed_portfolio
    venue = service.status(rid)["repository_paper"]["portfolio"]["venues"][0]
    value = draft(service, rid, prepare_analysis=False)
    value["sections"][3]["text"] += " This changed temporary writer is still awaiting native admission."
    value["revision"] = {"prior_draft_sha256": venue["draft_sha256"], "changes": ["Changed an actual retained fixture paragraph only."]}
    retain_portfolio_response(service, rid, value, "venue-manuscript", venue["venue_id"], outcome=outcome)
    assert not service.status(rid)["repository_paper"]["portfolio"]["analysis_revision_available"]
    with pytest.raises(WorkflowError) as failure:
        service.prepare_portfolio_revision(rid)
    assert failure.value.code == "PORTFOLIO_REVISION_PENDING"


def test_prepare_holds_eligible_original_tail(reviewed_portfolio):
    service, rid = reviewed_portfolio
    venue = service.status(rid)["repository_paper"]["portfolio"]["venues"][0]
    interrupted_portfolio_writer(service, rid, venue["venue_id"])
    assert not service.status(rid)["repository_paper"]["portfolio"]["analysis_revision_available"]
    with pytest.raises(WorkflowError) as failure:
        service.prepare_portfolio_revision(rid)
    assert failure.value.code == "PORTFOLIO_REVISION_PENDING"


def test_prepare_endpoint_has_no_reset_or_supplied_action_authority():
    calls = []
    service = SimpleNamespace(prepare_portfolio_revision=lambda rid: calls.append(rid) or {"ok": True})
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), io.BytesIO())
    try:
        message = {"id": "repair", "method": "workflow.preparePortfolioRevision", "params": {"researchId": "research-abcdefabcdef"}}
        assert ipc.request(json.dumps(message).encode()) == message
        assert dispatcher.execute(message["method"], message["params"]) == {"ok": True}
        assert calls == ["research-abcdefabcdef"]
        for extra in ({"reset": True}, {"value": {"actions": []}}, {"pdfBudget": 10}):
            with pytest.raises(ValueError):
                ipc.request(json.dumps({**message, "params": {**message["params"], **extra}}).encode())
    finally:
        dispatcher._pool.shutdown(wait=True)

"""Native changed-basis journal revisions; temporary fixtures, no SDK or project execution."""
import copy
import json
from uuid import uuid4

import pytest

from paper_factory.workflow import WorkflowError
from test_repository_paper_workflow import study, draft, review
from test_repository_portfolio import portfolio, retain_portfolio_response
from test_repository_portfolio_revision import reviewed_portfolio, revised_analysis, retain_revision_response
from test_scholarly_html import HINT, collection, clock


def repair(service, rid):
    service.prepare_portfolio_revision(rid)
    value = revised_analysis(service, rid)
    key, _ = retain_revision_response(service, rid, value)
    return service.submit_portfolio_analysis(rid, {"inference_artifact_id": key, "analysis": value})


def revised_draft(service, rid, venue):
    value = draft(service, rid, prepare_analysis=False)
    value["sections"][3]["text"] += " This manuscript-level synthetic correction uses the changed retained analysis; no retrieval, executed effect or human validation is claimed."
    value["revision"] = {"prior_draft_sha256": venue["draft_sha256"], "changes": ["Corrected the bounded analytical method and its explicitly unfulfilled requirements."]}
    return value


@pytest.mark.parametrize("reviewed_portfolio", [{"precollect": True, "human_elsewhere": True}], indirect=True)
def test_remaining_collection_binds_actual_review_plan_preserves_all_analysis_and_pdf_counts(reviewed_portfolio):
    service, rid = reviewed_portfolio
    before = repair(service, rid)
    pf = before["repository_paper"]["portfolio"]
    assert pf["literature_budget"] == {"used": 2, "limit": 3} and pf["literature_followup_available"]
    original = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    calls = []
    def collect(queries, root, **kwargs):
        calls.append(kwargs)
        return {"sources": [], "searches": [{"query": query} for query in queries], "warnings": [], "pdf_reservations": []}
    service.collector = collect
    after = service.collect_portfolio_literature(rid, ["a distinct exact retained reviewer followup comparison"])
    pf2 = after["repository_paper"]["portfolio"]
    assert len(calls) == 1 and calls[0]["pdf_reservation_limit"] == 0 and "html_candidates" not in calls[0]
    assert pf2["literature_budget"] == {"used": 3, "limit": 3} and not pf2["literature_followup_available"]
    assert pf2["pdf_budget"] == pf["pdf_budget"]
    assert after["repository_paper"]["analysis_attempts"] == before["repository_paper"]["analysis_attempts"] == 3
    assert after["execution_attempt"] == before["execution_attempt"] == 0
    intent = json.loads(service.artifact_path(rid, "repository-portfolio-literature-intent-3").read_bytes())
    assert intent["bindings"]["attempt"] == 3 and "phase" not in intent["bindings"]
    assert intent["bindings"]["analysis_sha256"] == pf["analysis_sha256"]
    assert intent["bindings"]["literature_sha256"] == pf["literature_sha256"]
    assert intent["bindings"]["review_plan_sha256"] == pf["analysis_revision"]["sha256"]
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in original.items())
    assert sum(key.startswith("model-evidence-") for key in after["artifacts"]) == sum(key.startswith("model-evidence-") for key in before["artifacts"])
    with pytest.raises(WorkflowError) as repeated:
        service.collect_portfolio_literature(rid, ["another genuine comparison without remaining collection budget"])
    assert repeated.value.code == "STUDY_LITERATURE_LIMIT" and len(calls) == 1
    venue_id = pf2["venues"][0]["venue_id"]
    old = json.loads(original["repository-portfolio-" + venue_id + "-review-1"])
    with service._operation(rid) as (ws, record):
        assert service._portfolio_binding(ws, record, "venue-manuscript-review", venue_id, 1,
            analysis_basis=old["reviewer_bindings"]) == old["reviewer_bindings"]


@pytest.mark.parametrize("reviewed_portfolio", [{"human_elsewhere": True}], indirect=True)
def test_changed_analysis_allows_local_revision_without_closing_elsewhere_human_or_local_literature_actions(reviewed_portfolio):
    service, rid = reviewed_portfolio
    before = repair(service, rid)
    original = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    pf = before["repository_paper"]["portfolio"]
    venue = pf["venues"][0]
    assert pf["analysis_revision"]["status"] == "incomplete" and venue["revise_available"]
    assert not venue["analysis_current"] and not venue["content_ready"]
    assert venue["writer_binding"]["portfolio_analysis_sha256"] == pf["analysis_sha256"]
    assert venue["writer_binding"]["prior_review_sha256"] == before["artifacts"][venue["artifact_ids"]["review"]]["sha256"]
    value = revised_draft(service, rid, venue)
    key, started = retain_portfolio_response(service, rid, value, "venue-manuscript", venue["venue_id"])
    pending = service.status(rid)["repository_paper"]["portfolio"]["venues"][0]
    assert pending["revise_available"] and pending["writer_binding"]["attempt"] == 2 and pending["writer_outcome"] == "completed"
    admitted = service.submit_portfolio_manuscript(rid, {"venue_id": venue["venue_id"], "inference_artifact_id": key, "manuscript": value})
    current = admitted["repository_paper"]["portfolio"]["venues"][0]
    assert current["analysis_current"] and current["admitted_drafts"] == current["draft_attempts"] == 2
    assert not current["content_ready"] and not current["scientific_ready"] and current["review"] is None
    assert admitted["repository_paper"]["analysis_attempts"] == 3 and admitted["execution_attempt"] == 0
    assert all(service.artifact_path(rid, k).read_bytes() == raw for k, raw in original.items())
    negative = review(False)
    negative["content_assessment"]["next_actions"] = [{"action": "retrieve_literature", "target": "Actual closest body remains missing",
        "required_change": "Retain a real closest method body; this changed analysis and manuscript are not that evidence.",
        "verification": "Verify a real complete body before claiming comparative contribution."}]
    negative["content_assessment"]["literature_queries"] = [HINT["title"]]
    review_key, _ = retain_portfolio_response(service, rid, negative, "venue-manuscript-review", venue["venue_id"])
    after = service.submit_portfolio_review(rid, {"venue_id": venue["venue_id"], "inference_artifact_id": review_key, "review": negative})
    final = after["repository_paper"]["portfolio"]["venues"][0]
    assert not final["revise_available"] and final["writer_binding"] is None
    assert final["draft_attempts"] == final["review_attempts"] == 2 and not final["content_ready"]
    assert after["repository_paper"]["portfolio"]["analysis_revision"]["status"] == "incomplete"
    with pytest.raises(WorkflowError) as replay:
        service.record_inference(rid, {**started, "id": str(uuid4())})
    assert replay.value.code == "PORTFOLIO_RESEARCH_INCOMPLETE"


@pytest.mark.parametrize("reviewed_portfolio", [True], indirect=True)
def test_local_revision_requires_whole_prior_draft_and_review_before_any_start(reviewed_portfolio):
    service, rid = reviewed_portfolio
    before = repair(service, rid)
    venue = before["repository_paper"]["portfolio"]["venues"][0]
    value = revised_draft(service, rid, venue)
    for corruption in ("text", "sha", "eof", "omitted", "draft"):
        def change(materials):
            if corruption == "text":
                materials["portfolioPriorReview"]["text"] += " Fabricated local instruction."
            elif corruption == "sha":
                materials["portfolioPriorReview"]["sha256"] = "0" * 64
            elif corruption == "eof":
                materials["portfolioPriorReview"]["pages"][-1]["nextOffset"] = 32000
            elif corruption == "omitted":
                materials.pop("portfolioPriorReview")
            else:
                materials["portfolioDraft"]["text"] += " Fabricated prior paragraph."
        with pytest.raises(WorkflowError) as failure:
            retain_portfolio_response(service, rid, value, "venue-manuscript", venue["venue_id"], material_change=change)
        assert failure.value.code == ("PORTFOLIO_DRAFT_READING_INVALID" if corruption == "draft" else "PORTFOLIO_REVIEW_READING_INVALID")
        after = service.status(rid)
        assert set(after["artifacts"]) == set(before["artifacts"])
        assert after["repository_paper"]["portfolio"]["venues"][0]["draft_attempts"] == 1


@pytest.mark.parametrize("reviewed_portfolio", [True], indirect=True)
def test_failed_local_revision_preserves_attempt_and_never_retries_same_changed_basis(reviewed_portfolio):
    service, rid = reviewed_portfolio
    before = repair(service, rid)
    venue = before["repository_paper"]["portfolio"]["venues"][0]
    value = revised_draft(service, rid, venue)
    key, started = retain_portfolio_response(service, rid, value, "venue-manuscript", venue["venue_id"], outcome="failed")
    after = service.status(rid)
    local = after["repository_paper"]["portfolio"]["venues"][0]
    assert local["draft_attempts"] == 2 and local["admitted_drafts"] == 1
    assert not local["revise_available"] and local["writer_binding"] is None
    assert key in after["artifacts"] and after["repository_paper"]["analysis_attempts"] == 3
    with pytest.raises(WorkflowError) as repeated:
        service.record_inference(rid, {**started, "id": str(uuid4())})
    assert repeated.value.code == "PORTFOLIO_RESEARCH_INCOMPLETE"


@pytest.mark.parametrize("reviewed_portfolio", [{"precollect": True}], indirect=True)
def test_full_frozen_html_primary_body_unlocks_next_local_revision_without_analysis_or_pdf_reset(reviewed_portfolio, monkeypatch, clock):
    service, rid = reviewed_portfolio
    repaired = repair(service, rid)
    venue = repaired["repository_paper"]["portfolio"]["venues"][0]
    value = revised_draft(service, rid, venue)
    key, _ = retain_portfolio_response(service, rid, value, "venue-manuscript", venue["venue_id"])
    service.submit_portfolio_manuscript(rid, {"venue_id": venue["venue_id"], "inference_artifact_id": key, "manuscript": value})
    negative = review(False)
    negative["content_assessment"]["next_actions"] = [{"action": "retrieve_literature", "target": "Closest primary mechanism",
        "required_change": "Read a primary method body before claiming a comparative contribution.",
        "verification": "Preserve complete original body bytes and literal comparison passages."}]
    negative["content_assessment"]["literature_queries"] = [HINT["title"]]
    key, _ = retain_portfolio_response(service, rid, negative, "venue-manuscript-review", venue["venue_id"])
    before = service.submit_portfolio_review(rid, {"venue_id": venue["venue_id"], "inference_artifact_id": key, "review": negative})
    old_venue = before["repository_paper"]["portfolio"]["venues"][0]
    assert not old_venue["revise_available"] and old_venue["writer_binding"] is None
    original = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    calls = []
    def collect(queries, root, **kwargs):
        calls.append(kwargs)
        packet, requests = collection(monkeypatch, root)
        assert len(requests) == 2
        return packet
    service.collector = collect
    after = service.collect_portfolio_literature(rid, [HINT["title"]], [], [HINT])
    pf = after["repository_paper"]["portfolio"]
    assert len(calls) == 1 and calls[0]["html_candidates"] == [HINT] and calls[0]["pdf_reservation_limit"] == 0
    assert pf["literature_budget"] == {"used": 3, "limit": 3} and pf["pdf_budget"] == before["repository_paper"]["portfolio"]["pdf_budget"]
    assert after["repository_paper"]["analysis_attempts"] == 3 and after["execution_attempt"] == 0
    assert pf["analysis_sha256"] == before["repository_paper"]["portfolio"]["analysis_sha256"]
    local = pf["venues"][0]
    assert local["revise_available"] and local["writer_binding"]["attempt"] == 3
    assert local["writer_binding"]["literature_sha256"] == pf["literature_sha256"]
    assert local["writer_binding"]["prior_review_sha256"] == before["artifacts"][old_venue["artifact_ids"]["review"]]["sha256"]
    assert not local["scientific_ready"] and not local["content_ready"] and pf["analysis_revision"]["status"] == "incomplete"
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in original.items())
    packet = json.loads(service.artifact_path(rid, "repository-portfolio-literature-3").read_bytes())
    source, = [source for source in packet["sources"] if source.get("copy_type") == "scholarly_html"]
    from paper_factory.workflow import _retained_primary_body
    with service._operation(rid) as (ws, record):
        assert _retained_primary_body(ws, record, source, packet)
        invalid = copy.deepcopy(source)
        invalid["publication_version"] = "earlier_draft"
        assert not _retained_primary_body(ws, record, invalid, packet)
        invalid = copy.deepcopy(source)
        text = (ws.path("research") / source["text_path"]).read_text(encoding="utf-8")
        invalid["excerpts"] = [text[:160]]
        invalid["excerpt_ranges"] = [{"start": 0, "end": 160}]
        assert not _retained_primary_body(ws, record, invalid, packet)

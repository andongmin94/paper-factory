"""Bounded manuscript reasoning repairs and retained resumption; no actual SDK."""
import hashlib
import json
from uuid import uuid4

import pytest

from paper_factory.workflow import WorkflowError
from test_repository_paper_workflow import study, draft, review
from test_repository_portfolio import portfolio, retain_portfolio_response
from test_repository_portfolio_revision import reviewed_portfolio
from test_repository_portfolio_followup import repair, revised_draft


def local_second_review(service, rid, external=None):
    saved = repair(service, rid)
    venue = saved["repository_paper"]["portfolio"]["venues"][0]
    value = revised_draft(service, rid, venue)
    key, _ = retain_portfolio_response(service, rid, value, "venue-manuscript", venue["venue_id"])
    service.submit_portfolio_manuscript(rid, {"venue_id": venue["venue_id"], "inference_artifact_id": key, "manuscript": value})
    assessed = review(False)
    assessed["next_actions"][0].update(target="Local authority interpretation", required_change=
        "Re-derive remaining effect discretion from the already retained source witnesses in the manuscript; do not claim a new common analysis.")
    if external:
        assessed["content_assessment"]["next_actions"].append({"action": external, "target": "Missing external evidence",
            "required_change": "Obtain actual missing evidence; unchanged source reasoning cannot fulfill this external action.",
            "verification": "An independent review checks actual retained evidence without claiming fictional collection or validation."})
        if external == "retrieve_literature":
            assessed["content_assessment"]["literature_queries"] = ["a real closest method body is still absent in this synthetic fixture"]
    key, _ = retain_portfolio_response(service, rid, assessed, "venue-manuscript-review", venue["venue_id"])
    return service.submit_portfolio_review(rid, {"venue_id": venue["venue_id"], "inference_artifact_id": key, "review": assessed})


@pytest.mark.parametrize("reviewed_portfolio", [{"human_elsewhere": True}], indirect=True)
@pytest.mark.parametrize("outcome", ["completed", "failed"])
def test_retained_analytical_third_repair_preserves_common_basis_negative_review_and_attempt_cap(reviewed_portfolio, outcome):
    service, rid = reviewed_portfolio
    before = local_second_review(service, rid)
    pf = before["repository_paper"]["portfolio"]
    venue = pf["venues"][0]
    assert pf["analysis_revision"]["status"] == "incomplete" and venue["analysis_current"]
    assert venue["revise_available"] and venue["writer_binding"]["attempt"] == 3
    assert "preserve the frozen common analysis" in venue["revise_reason"]
    assert not venue["scientific_ready"] and not venue["content_ready"]
    assert venue["writer_binding"]["prior_review_sha256"] == before["artifacts"][venue["artifact_ids"]["review"]]["sha256"]
    prior = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    value = revised_draft(service, rid, venue)
    value["sections"][3]["text"] += " This final synthetic manuscript derivation corrects unilateral effect discretion from existing witnesses and is not source analysis four."
    value["revision"]["changes"].append("Re-derived local analytical reasoning only; immutable common analysis and external obligations remain.")
    key, started = retain_portfolio_response(service, rid, value, "venue-manuscript", venue["venue_id"], outcome=outcome)
    evidence = service.artifact_path(rid, key).read_bytes()
    pending = service.status(rid)
    local = pending["repository_paper"]["portfolio"]["venues"][0]
    assert local["draft_attempts"] == 3
    if outcome == "completed":
        assert local["revise_available"] and local["writer_outcome"] == "completed"
        saved = service.submit_portfolio_manuscript(rid, {"venue_id": venue["venue_id"], "inference_artifact_id": key, "manuscript": value})
        local = saved["repository_paper"]["portfolio"]["venues"][0]
        assert local["admitted_drafts"] == 3 and local["review"] is None
        assert not local["scientific_ready"] and not local["content_ready"]
        review_key, _ = retain_portfolio_response(service, rid, review(False), "venue-manuscript-review", venue["venue_id"])
        saved = service.submit_portfolio_review(rid, {"venue_id": venue["venue_id"], "inference_artifact_id": review_key, "review": review(False)})
    else:
        saved = pending
        assert local["admitted_drafts"] == 2 and not local["revise_available"]
    final = saved["repository_paper"]["portfolio"]
    assert final["venues"][0]["writer_binding"] is None and not final["venues"][0]["revise_available"]
    assert final["analysis_sha256"] == pf["analysis_sha256"] and final["literature_sha256"] == pf["literature_sha256"]
    assert final["analysis_revision"] == pf["analysis_revision"] and final["pdf_budget"] == pf["pdf_budget"]
    assert final["literature_budget"] == pf["literature_budget"]
    assert saved["repository_paper"]["analysis_attempts"] == before["repository_paper"]["analysis_attempts"] == 3
    assert saved["execution_attempt"] == before["execution_attempt"] == 0
    assert all(service.artifact_path(rid, k).read_bytes() == raw for k, raw in prior.items())
    with pytest.raises(WorkflowError) as fourth:
        service.record_inference(rid, {**started, "id": str(uuid4())})
    assert fourth.value.code == "PORTFOLIO_INFERENCE_LIMIT"
    assert service.artifact_path(rid, key).read_bytes() == evidence


@pytest.mark.parametrize("reviewed_portfolio", [True], indirect=True)
@pytest.mark.parametrize("external", ["retrieve_literature", "human_validation", "infeasible"])
def test_unchanged_basis_mixed_external_action_remains_held(reviewed_portfolio, external):
    service, rid = reviewed_portfolio
    saved = local_second_review(service, rid, external)
    venue = saved["repository_paper"]["portfolio"]["venues"][0]
    assert venue["analysis_current"] and venue["draft_attempts"] == 2
    assert not venue["revise_available"] and venue["writer_binding"] is None
    assert not venue["scientific_ready"] and not venue["content_ready"]
    assert any(action["action"] == external for action in venue["review"]["content_assessment"]["next_actions"])
    assert saved["repository_paper"]["analysis_attempts"] == 3 and saved["execution_attempt"] == 0


@pytest.mark.parametrize("reviewed_portfolio", [{"human_elsewhere": True}], indirect=True)
def test_completed_local_review_and_export_resume_exact_remaining_portfolio_without_common_rewrite(reviewed_portfolio, monkeypatch):
    service, rid = reviewed_portfolio
    before = local_second_review(service, rid)
    venue_id = before["repository_paper"]["portfolio"]["venues"][0]["venue_id"]
    calls = []
    def convert(source, output, **kwargs):
        calls.append(output.suffix)
        raw = b"Synthetic export fixture only; no usable PDF or DOCX is claimed."
        output.write_bytes(raw)
        return {"input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "output_sha256": hashlib.sha256(raw).hexdigest()}
    monkeypatch.setattr("paper_factory.conversion.convert", convert)
    exported = service.export_portfolio_draft(rid, venue_id)
    assert calls == []
    pf = exported["repository_paper"]["portfolio"]
    assert pf["venues"][0]["export_status"] == "completed" and pf["venues"][0]["writer_binding"]["attempt"] == 3
    cancelled = service.cancel(rid)
    assert cancelled["status"] == "cancelled" and cancelled["resume_kind"] == "authoring"
    original = {key: service.artifact_path(rid, key).read_bytes() for key in cancelled["artifacts"]}
    monkeypatch.setattr(service, "start_experiment", lambda *a, **kw: pytest.fail("Portfolio resume cannot execute a project"))
    monkeypatch.setattr(service, "submit_repository_manuscript", lambda *a, **kw: pytest.fail("Portfolio resume cannot recreate the common manuscript"))
    resumed = service.resume(rid)
    assert resumed["status"] == "ready" and resumed["stage"] == cancelled["stage"] == "repository_manuscript"
    assert resumed["code"] is None and resumed["cancellation_requested"] is False
    assert resumed["execution_attempt"] == cancelled["execution_attempt"] == 0
    assert resumed["draft_attempt"] == cancelled["draft_attempt"]
    assert resumed["repository_paper"] == cancelled["repository_paper"]
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in original.items())
    added = set(resumed["artifacts"]) - set(cancelled["artifacts"])
    assert len(added) == 1
    key = added.pop()
    assert key.startswith("repository-resume-")
    receipt = json.loads(service.artifact_path(rid, key).read_bytes())
    assert receipt["previous_status"] == "cancelled" and receipt["execution_attempt"] == 0
    assert receipt["portfolio_start_sha256"] == pf["sha256"]
    assert calls == []

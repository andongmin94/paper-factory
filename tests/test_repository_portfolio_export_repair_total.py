"""Current-draft repair limits and immutable cumulative history are distinct."""
import pytest
from paper_factory.workflow import WorkflowError

from test_repository_paper_workflow import study, draft, review
from test_repository_portfolio import portfolio, retain_portfolio_response
from test_repository_portfolio_export_repair import failed_export, successful_conversion


@pytest.mark.parametrize("repair_outcome", ["completed", "interrupted"])
def test_export_repair_total_retains_prior_draft_completed_or_unknown_attempt(failed_export, monkeypatch, repair_outcome):
    service, rid, venue_id, _, _, calls = failed_export
    if repair_outcome == "completed":
        monkeypatch.setattr("paper_factory.conversion.convert", successful_conversion(calls))
        first = service.repair_portfolio_export(rid, venue_id)
    else:
        def interrupted(source, output):
            calls.append((source, output))
            raise RuntimeError("Synthetic unknown conversion after immutable original repair input")
        monkeypatch.setattr("paper_factory.conversion.convert", interrupted)
        with pytest.raises(RuntimeError):
            service.repair_portfolio_export(rid, venue_id)
        first = service.status(rid)
    prior = first["repository_paper"]["portfolio"]["venues"][0]
    assert prior["export_repair_attempts"] == 1 and prior["export_repair_total"] == 1
    if repair_outcome == "interrupted":
        with pytest.raises(WorkflowError) as held:
            retain_portfolio_response(service, rid, review(False), "venue-manuscript-review", venue_id, preflight=False)
        assert held.value.code == "PORTFOLIO_EXPORT_REQUIRED"
        current = service.status(rid)["repository_paper"]["portfolio"]["venues"][0]
        assert current["review_attempts"] == 0 and current["writer_binding"] is None
        return
    assessment = review(False)
    key, _ = retain_portfolio_response(service, rid, assessment, "venue-manuscript-review", venue_id)
    first = service.submit_portfolio_review(rid, {"venue_id": venue_id, "inference_artifact_id": key, "review": assessment})
    prior = first["repository_paper"]["portfolio"]["venues"][0]
    originals = {key: service.artifact_path(rid, key).read_bytes() for key in first["artifacts"]}
    candidate = draft(service, rid, prepare_analysis=False)
    candidate["sections"][3]["text"] += " This synthetic revised manuscript retains the same source study and its original failures."
    candidate["revision"] = {"prior_draft_sha256": prior["draft_sha256"], "changes": ["Changed the manuscript-level explanation from retained sources only."]}
    key, _ = retain_portfolio_response(service, rid, candidate, "venue-manuscript", venue_id)
    service.submit_portfolio_manuscript(rid, {"venue_id": venue_id, "inference_artifact_id": key, "manuscript": candidate})
    assessment = review(False)
    key, _ = retain_portfolio_response(service, rid, assessment, "venue-manuscript-review", venue_id)
    service.submit_portfolio_review(rid, {"venue_id": venue_id, "inference_artifact_id": key, "review": assessment})
    monkeypatch.setattr("paper_factory.conversion.convert", successful_conversion(calls))
    current = service.export_portfolio_draft(rid, venue_id)
    latest = current["repository_paper"]["portfolio"]["venues"][0]
    assert latest["admitted_drafts"] == 2 and latest["export_status"] == "completed"
    assert latest["export_repair_attempts"] == 0 and latest["export_repair_total"] == 1
    assert not latest["export_repair_available"]
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in originals.items())
    assert service.artifact_path(rid, f"repository-portfolio-{venue_id}-export-1").read_bytes() == originals[f"repository-portfolio-{venue_id}-export-1"]
    if repair_outcome == "completed":
        repair_key = f"repository-portfolio-{venue_id}-export-repair-1"
        assert service.artifact_path(rid, repair_key).read_bytes() == originals[repair_key]
    else:
        assert f"repository-portfolio-{venue_id}-export-repair-1" not in current["artifacts"]
        assert f"repository-portfolio-{venue_id}-export-markdown-repair-1" in current["artifacts"]
    for field in ("proposal_attempt", "study_literature_attempt", "draft_attempt", "code_attempt", "execution_attempt", "redesign_attempt"):
        assert current[field] == first[field]
    for field in ("analysis", "analysis_attempts", "draft", "review"):
        assert current["repository_paper"][field] == first["repository_paper"][field]
    assert latest["draft_attempts"] == prior["draft_attempts"] + 1 and latest["review_attempts"] == prior["review_attempts"] + 1

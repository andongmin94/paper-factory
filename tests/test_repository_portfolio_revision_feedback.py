"""Bounded external corrections retain actual draft/review provenance on synthetic studies."""

import copy
import hashlib
import io
import json
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from paper_factory import ipc
from paper_factory.autonomous.repository_portfolio import PORTFOLIO_MARKER, MATERIAL_HEADER
from paper_factory.workflow import WorkflowError, _inference_read
from test_repository_paper_workflow import study, draft, review
from test_repository_portfolio import unwritten_portfolio, analyze_portfolio, retain_portfolio_response


FEEDBACK = "The retained Word manuscript is below the official feature-article minimum. Develop the supported design implications using retained source witnesses; do not pad text, invent evidence or replace the original positive scientific review."


def venue(service, rid, venue_id):
    return next(row for row in service.status(rid)["repository_paper"]["portfolio"]["venues"] if row["venue_id"] == venue_id)


@pytest.fixture
def written_feedback_portfolio(unwritten_portfolio):
    service, rid, _ = unwritten_portfolio
    analyze_portfolio(service, rid)
    venue_id = "ieee-security-privacy"
    value = draft(service, rid, prepare_analysis=False)
    key, _ = retain_portfolio_response(service, rid, value, "venue-manuscript", venue_id)
    service.submit_portfolio_manuscript(rid, {"venue_id": venue_id, "inference_artifact_id": key, "manuscript": value})
    return service, rid, venue_id


def fixture_export(service, rid, venue_id):
    def convert(source, output, **kwargs):
        output.write_bytes(b"Synthetic native-preflight fixture only: " + output.suffix.encode())
        return {"input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "engine": "synthetic-fixture"}
    with patch("paper_factory.conversion.convert", convert):
        service.export_portfolio_draft(rid, venue_id)


def assess(service, rid, venue_id, material_change=None):
    key, _ = retain_portfolio_response(service, rid, review(True), "venue-manuscript-review", venue_id, material_change=material_change)
    return service.submit_portfolio_review(rid, {"venue_id": venue_id, "inference_artifact_id": key, "review": review(True)})


def feedback_material(service, rid, venue_id, corruption=None):
    feedback = venue(service, rid, venue_id)["revision_feedback"]
    text = service.artifact_path(rid, feedback["artifact_id"]).read_bytes().decode("utf-8")
    body = {"artifact_id": feedback["artifact_id"], "sha256": feedback["sha256"], "text": text, **_inference_read(text)}
    if corruption == "text": body["text"] += " Invented external evidence."
    elif corruption == "hash": body["sha256"] = "0" * 64
    elif corruption == "eof": body["pages"][-1]["nextOffset"] = 32000
    return lambda materials: materials.update({"portfolioRevisionFeedback": body}) if corruption != "omitted" else None


def revised_value(service, rid, venue_id):
    before = venue(service, rid, venue_id)
    value = copy.deepcopy(before["draft"])
    value["sections"][2]["text"] += " This synthetic correction develops a qualified interpretation using unchanged retained witnesses without asserting any new empirical evidence."
    value["revision"] = {"prior_draft_sha256": before["draft_sha256"],
        "changes": ["Developed the supported interpretation in response to retained external authoring feedback."]}
    return value


def revise(service, rid, venue_id, material_change=None, outcome="completed"):
    value = revised_value(service, rid, venue_id)
    key, started = retain_portfolio_response(service, rid, value, "venue-manuscript", venue_id,
        material_change=material_change or feedback_material(service, rid, venue_id), outcome=outcome)
    if outcome == "completed":
        service.submit_portfolio_manuscript(rid, {"venue_id": venue_id, "inference_artifact_id": key, "manuscript": value})
    return started


def test_positive_review_is_retained_and_new_feedback_requires_new_draft_and_review(written_feedback_portfolio):
    service, rid, venue_id = written_feedback_portfolio
    assess(service, rid, venue_id)
    before = service.status(rid)
    old = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    current = venue(service, rid, venue_id)
    assert current["scientific_ready"] and current["content_ready"] and not current["revise_available"]
    assert current["revision_feedback_available"]
    service.submit_portfolio_revision_feedback(rid, venue_id, FEEDBACK)
    pending = venue(service, rid, venue_id)
    assert pending["scientific_ready"] and pending["content_ready"] and pending["revision_feedback_pending"]
    assert pending["revise_available"] and pending["writer_binding"]["attempt"] == 2
    assert pending["writer_binding"]["revision_feedback_sha256"] == pending["revision_feedback"]["sha256"]
    assert pending["review"] == current["review"]
    assert pending["revision_feedback"]["review_sha256"] == before["artifacts"][current["artifact_ids"]["review"]]["sha256"]
    assert "no scientific evidence" in pending["revision_feedback"]["scope"]
    with pytest.raises(WorkflowError) as duplicate:
        service.submit_portfolio_revision_feedback(rid, venue_id, FEEDBACK + " Duplicate.")
    assert duplicate.value.code == "PORTFOLIO_FEEDBACK_CONFLICT"
    started = revise(service, rid, venue_id)
    revised = venue(service, rid, venue_id)
    assert revised["admitted_drafts"] == 2 and revised["draft_attempts"] == 2 and revised["review_attempts"] == 1
    assert not revised["revision_feedback_pending"] and revised["review"] is None and not revised["content_ready"]
    assert revised["reviewer_binding"]["revision_feedback_sha256"] == pending["revision_feedback"]["sha256"]
    assess(service, rid, venue_id, feedback_material(service, rid, venue_id))
    saved = service.status(rid)
    final = venue(service, rid, venue_id)
    assert final["scientific_ready"] and final["content_ready"] and final["review_attempts"] == 2
    assert saved["repository_paper"]["analysis_attempts"] == before["repository_paper"]["analysis_attempts"] == 1
    assert saved["study_literature_attempt"] == before["study_literature_attempt"] and saved["execution_attempt"] == 0
    assert all(service.artifact_path(rid, key).read_bytes() == data for key, data in old.items())
    with pytest.raises(WorkflowError): service.record_inference(rid, {**started, "id": str(uuid4())})


def test_unreviewed_exported_draft_can_be_corrected_before_any_review_is_dispatched(written_feedback_portfolio):
    service, rid, venue_id = written_feedback_portfolio
    assert not venue(service, rid, venue_id)["revision_feedback_available"]
    fixture_export(service, rid, venue_id)
    exported = venue(service, rid, venue_id)
    assert exported["revision_feedback_available"]
    service.submit_portfolio_revision_feedback(rid, venue_id, FEEDBACK)
    pending = venue(service, rid, venue_id)
    assert pending["revision_feedback"]["review_sha256"] is None and pending["reviewer_binding"] is None
    assert "prior_review_sha256" not in pending["writer_binding"]
    prompt = "Synthetic held original review." + PORTFOLIO_MARKER + json.dumps(exported["reviewer_binding"]) + MATERIAL_HEADER + "{}"
    with pytest.raises(WorkflowError) as old_review:
        service.record_inference(rid, {"id": str(uuid4()), "phase": "venue-manuscript-review", "at": "2026-10-15T00:00:00+00:00",
            "model": "synthetic-test-model", "profileId": "fixture-profile", "prompt": prompt,
            "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(), "outcome": "started"})
    assert old_review.value.code == "PORTFOLIO_FEEDBACK_PENDING"
    revise(service, rid, venue_id)
    assert venue(service, rid, venue_id)["review_attempts"] == 0
    assess(service, rid, venue_id, feedback_material(service, rid, venue_id))
    final = venue(service, rid, venue_id)
    assert final["draft_attempts"] == 2 and final["review_attempts"] == 1 and final["content_ready"]


@pytest.mark.parametrize("outcome", [None, "failed", "interrupted", "completed"])
def test_original_uncertain_or_unadmitted_review_cannot_be_skipped(written_feedback_portfolio, outcome):
    service, rid, venue_id = written_feedback_portfolio
    retain_portfolio_response(service, rid, review(True), "venue-manuscript-review", venue_id, outcome=outcome)
    before = service.status(rid)
    assert not venue(service, rid, venue_id)["revision_feedback_available"]
    with pytest.raises(WorkflowError) as failure:
        service.submit_portfolio_revision_feedback(rid, venue_id, FEEDBACK)
    assert failure.value.code == "PORTFOLIO_FEEDBACK_UNAVAILABLE"
    assert service.status(rid)["artifacts"] == before["artifacts"]


@pytest.mark.parametrize("corruption", ["text", "hash", "eof", "omitted"])
def test_full_feedback_proof_is_required_before_writer_slot_is_spent(written_feedback_portfolio, corruption):
    service, rid, venue_id = written_feedback_portfolio
    assess(service, rid, venue_id)
    service.submit_portfolio_revision_feedback(rid, venue_id, FEEDBACK)
    before = service.status(rid)
    with pytest.raises(WorkflowError) as failure:
        revise(service, rid, venue_id, feedback_material(service, rid, venue_id, corruption))
    assert failure.value.code == "PORTFOLIO_FEEDBACK_READING_INVALID"
    assert service.status(rid)["artifacts"] == before["artifacts"]
    assert venue(service, rid, venue_id)["draft_attempts"] == 1


def test_revised_independent_review_cannot_omit_feedback_reading_proof(written_feedback_portfolio):
    service, rid, venue_id = written_feedback_portfolio
    assess(service, rid, venue_id)
    service.submit_portfolio_revision_feedback(rid, venue_id, FEEDBACK)
    revise(service, rid, venue_id)
    with pytest.raises(WorkflowError) as failure:
        retain_portfolio_response(service, rid, review(True), "venue-manuscript-review", venue_id)
    assert failure.value.code == "PORTFOLIO_FEEDBACK_READING_INVALID"
    assert venue(service, rid, venue_id)["review"] is None
    assert venue(service, rid, venue_id)["review_attempts"] == 1


def test_same_prior_draft_cannot_retry_failed_external_revision(written_feedback_portfolio):
    service, rid, venue_id = written_feedback_portfolio
    assess(service, rid, venue_id)
    service.submit_portfolio_revision_feedback(rid, venue_id, FEEDBACK)
    started = revise(service, rid, venue_id, outcome="failed")
    assert not venue(service, rid, venue_id)["revise_available"]
    with pytest.raises(WorkflowError): service.record_inference(rid, {**started, "id": str(uuid4())})
    assert venue(service, rid, venue_id)["draft_attempts"] == 2


def test_feedback_cannot_reset_existing_three_writing_and_review_budgets(written_feedback_portfolio):
    service, rid, venue_id = written_feedback_portfolio
    assess(service, rid, venue_id)
    for _ in range(2):
        service.submit_portfolio_revision_feedback(rid, venue_id, FEEDBACK)
        revise(service, rid, venue_id)
        assess(service, rid, venue_id, feedback_material(service, rid, venue_id))
    final = venue(service, rid, venue_id)
    assert final["draft_attempts"] == final["review_attempts"] == 3
    assert not final["revision_feedback_available"]
    with pytest.raises(WorkflowError) as failure:
        service.submit_portfolio_revision_feedback(rid, venue_id, FEEDBACK)
    assert failure.value.code == "PORTFOLIO_FEEDBACK_UNAVAILABLE"
    assert service.status(rid)["repository_paper"]["analysis_attempts"] == 1


def test_external_feedback_does_not_authorize_invented_literal_source(written_feedback_portfolio):
    service, rid, venue_id = written_feedback_portfolio
    assess(service, rid, venue_id)
    service.submit_portfolio_revision_feedback(rid, venue_id, FEEDBACK)
    value = revised_value(service, rid, venue_id)
    value["source_evidence"][0]["quote"] = "Invented source witness that never occurred in the unchanged repository source."
    key, _ = retain_portfolio_response(service, rid, value, "venue-manuscript", venue_id, material_change=feedback_material(service, rid, venue_id))
    with pytest.raises(WorkflowError) as failure:
        service.submit_portfolio_manuscript(rid, {"venue_id": venue_id, "inference_artifact_id": key, "manuscript": value})
    assert failure.value.code == "SOURCE_EVIDENCE_INVALID"
    final = venue(service, rid, venue_id)
    assert final["admitted_drafts"] == 1 and final["draft_attempts"] == 2


def test_feedback_has_no_budget_reset_or_scientific_approval_authority_in_ipc():
    calls = []
    service = SimpleNamespace(submit_portfolio_revision_feedback=lambda *args: calls.append(args) or {"ok": True})
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), io.BytesIO())
    try:
        message = {"id": "feedback", "method": "workflow.submitPortfolioRevisionFeedback",
            "params": {"researchId": "research-abcdefabcdef", "venueId": "ieee-security-privacy", "feedback": FEEDBACK}}
        assert ipc.request(json.dumps(message).encode()) == message
        assert dispatcher.execute(message["method"], message["params"]) == {"ok": True}
        assert calls == [("research-abcdefabcdef", "ieee-security-privacy", FEEDBACK)]
        for extra in ({"reset": True}, {"scientificReady": True}, {"review": {"criteria": {}}}):
            with pytest.raises(ValueError): ipc.request(json.dumps({**message, "params": {**message["params"], **extra}}).encode())
    finally:
        dispatcher._pool.shutdown(wait=True)

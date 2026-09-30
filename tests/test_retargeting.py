import json

import httpx
import pytest

from paper_factory import integrity, manuscript, publication, revisions, revision_submission, submission_package, venue_compiler, venue_policy, venues
from paper_factory.models import Paper, Submission, SubmissionState
from paper_factory.revisions import ReviewComment, ReviewSpec
from paper_factory.venue_policy import VenuePolicy
from paper_factory.workspace import digest_file, write_json
from test_publication import ready_case, attest, receipt, author_values
from test_revisions import response_plan
from test_submission import prepared, mock_conversion
from test_venue_policy import setup_policy


def rejected_case(prepared, tmp_path, *, import_report=True):
    ws, base, original, handler = ready_case(prepared)
    attest(ws, original, handler)
    receipt(ws, original, SubmissionState.SUBMITTED, tmp_path)
    receipt(ws, original, SubmissionState.REJECTED, tmp_path)
    report, spec = tmp_path / "rejection-report.txt", tmp_path / "rejection-comments.json"
    report.write_text("Please clarify the analysis method before submitting this study elsewhere.", encoding="utf-8")
    write_json(spec, ReviewSpec(reviewed_by=base.approved_by, comments=[ReviewComment(id="comment-a", excerpt=report.read_text(encoding="utf-8"), sections=["Method"])]))
    revision = revisions.import_review(ws, original, spec, report, confirmed=True)[0] if import_report else None
    return ws, base, original, handler, revision, spec, report


def new_venue_candidate(ws, child, original, handler, prepared, tmp_path):
    # Both discovery and policy evidence are complete synthetic API/page captures.
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": [{
        "id": "https://openalex.org/S456", "display_name": "Second Fixture Journal", "type": "journal",
        "issn": ["5678-1234"], "host_organization_name": "Example Publisher", "homepage_url": "https://example.org/second-journal",
    }]}))) as client:
        target = venues.discover(ws, "second journal", client=client)[0]
    policy = ws.get("policy", original.policy_id, VenuePolicy)
    spec = json.loads(ws.path(policy.spec_path).read_bytes())
    spec["venue_id"] = target.id
    quote = "Second Fixture Journal ISSN 5678-1234 Science Citation Index Expanded SCIE"
    spec["evidence"]["indexing"]["excerpt"] = quote
    path = tmp_path / "second-venue-policy.json"
    write_json(path, spec)

    def pages(request):
        return httpx.Response(200, text=handler(request).text + f"<p>{quote}</p>", headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(pages)) as client:
        policy = venue_policy.verify_policy(ws, target, path, client=client)
        assert policy.status == "verified", policy.issues
        selected = venue_compiler.select(ws, child, target, policy)
        selected, _ = venue_compiler.compile_submission(ws, selected, prepared[3], client=client)
        package, _ = submission_package.build(ws, selected, client=client)
    assert package.ready
    return ws.get("submission", selected.id, Submission), pages


def test_rejected_feedback_creates_approved_child_for_new_venue_without_reopening_original(prepared, mock_conversion, tmp_path):
    ws, base, original, handler, revision, _, _ = rejected_case(prepared, tmp_path)
    frozen = digest_file(ws.path(f"freezes/{base.id}/canonical.json"))
    package = original.package_digest
    child, _ = revisions.draft(ws, revision)
    assert child.id != base.id and child.study_id == base.study_id
    _, plan = response_plan(ws, revision, tmp_path)
    child, _ = revisions.apply_plan(ws, revision, plan)
    response, _ = revisions.build_response(ws, revision, plan)
    assert response.ready
    integrity.approve(ws, child, approved=True, assessment="Author reviewed the rejection feedback, revised method, related work, evidence and limitations.")
    assert revisions.verify_response(ws, response, require_approved=True)["ready"]
    with pytest.raises(ValueError, match="current journal revision decision"):
        revision_submission.prepare(ws, revision, prepared[3], response=response)
    candidate, pages = new_venue_candidate(ws, child, original, handler, prepared, tmp_path)
    assert candidate.venue_id != original.venue_id
    with httpx.Client(transport=httpx.MockTransport(pages)) as client:
        publication.attest(ws, candidate, author_values(), client=client)
    assert ws.get("submission", original.id, Submission).state == SubmissionState.REJECTED
    assert ws.get("submission", original.id, Submission).package_digest == package
    assert digest_file(ws.path(f"freezes/{base.id}/canonical.json")) == frozen
    assert len(publication.active_for_study(ws, base.study_id)) == 1
    assert publication.check(ws, candidate)["active"]
    assert revisions.verify_response(ws, response, require_approved=True)["ready"]
    assert not revisions.check(ws, revision)["passed"]  # Further edits wait for the new journal's actual decision.


@pytest.mark.parametrize("operation", ["import", "draft", "apply", "render"])
def test_active_retargeting_slot_blocks_old_rejected_feedback_edit_paths(prepared, mock_conversion, tmp_path, operation):
    ws, _, original, _, revision, spec, report = rejected_case(prepared, tmp_path, import_report=operation != "import")
    child = None
    if operation in {"apply", "render"}:
        child, _ = revisions.draft(ws, revision)
        _, plan = response_plan(ws, revision, tmp_path)
    _, _, competitor, handler = ready_case(prepared)
    attest(ws, competitor, handler)
    with pytest.raises(ValueError, match="another active peer-reviewed submission"):
        if operation == "import":
            revisions.import_review(ws, original, spec, report, confirmed=True)
        elif operation == "draft":
            revisions.draft(ws, revision)
        elif operation == "apply":
            revisions.apply_plan(ws, revision, plan)
        else:
            manuscript.refresh(ws, child)
    assert ws.get("submission", original.id, Submission).state == SubmissionState.REJECTED
    assert publication.check(ws, competitor)["active"]


def test_rejected_feedback_child_cannot_freeze_while_another_journal_occupies_study(prepared, mock_conversion, tmp_path):
    ws, _, original, _, revision, _, _ = rejected_case(prepared, tmp_path)
    child, _ = revisions.draft(ws, revision)
    _, _, competitor, handler = ready_case(prepared)
    attest(ws, competitor, handler)
    with pytest.raises(ValueError, match="another active peer-reviewed submission"):
        integrity.approve(ws, child, approved=True, assessment="Author reviewed the rejection feedback, evidence, related work and limitations.")
    assert not ws.path(f"freezes/{child.id}").exists()
    assert ws.get("paper", child.id, Paper).freeze_digest is None
    assert ws.get("submission", original.id, Submission).state == SubmissionState.REJECTED

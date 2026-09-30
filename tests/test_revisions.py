from contextlib import contextmanager
import io
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from paper_factory import experiments, integrity, manuscript, publication, research, revisions
from paper_factory.models import Claim, ExperimentManifest, ExperimentRun, Paper, Submission, SubmissionState, uid
from paper_factory.revisions import CommentResponse, ResponseBuild, ReviewComment, ReviewSpec, Revision, SectionEdit
from paper_factory.workspace import digest_file, write_json
from test_publication import ready_case, attest, receipt
from test_submission import prepared, mock_conversion
from test_venue_policy import setup_policy


def review_case(prepared, tmp_path, text="Please clarify the analysis method.", **changes):
    ws, paper, submission, handler = ready_case(prepared)
    attest(ws, submission, handler)
    receipt(ws, submission, SubmissionState.SUBMITTED, tmp_path)
    receipt(ws, submission, SubmissionState.REVISION, tmp_path)
    report = tmp_path / "referee.txt"
    report.write_text(text, encoding="utf-8", newline="")
    values = {"reviewed_by": paper.approved_by, "comments": [{"id": "comment-a", "excerpt": text, "sections": ["Method"]}]}
    values.update(changes)
    spec = tmp_path / "review.json"
    write_json(spec, values)
    revision, _ = revisions.import_review(ws, submission, spec, report, confirmed=True)
    return ws, paper, submission, revision, spec, report


def response_plan(ws, revision, tmp_path, disposition="accept", *, edit=True):
    plan = revisions.plan_template(ws, revision)
    response = plan.responses[0]
    response.disposition = disposition
    response.reply = "The method now explicitly describes the registered inspection protocol."
    if disposition in {"disagree", "partially_accept"}:
        response.justification = "The study is a descriptive inspection, so causal interpretation would exceed its evidence."
    if edit:
        response.edits = [SectionEdit(section="Method", blocks=[manuscript.prose("The registered descriptive inspection protocol defines the inputs and the extraction of declared measurement fields.")])]
    path = tmp_path / "response-plan.json"
    write_json(path, plan)
    return plan, path


def test_actual_review_creates_distinct_editable_child_without_rewriting_submitted_freeze(prepared, mock_conversion, tmp_path):
    ws, base, submission, revision, _, report = review_case(prepared, tmp_path)
    original = digest_file(ws.path(f"freezes/{base.id}/canonical.json"))
    child, root = revisions.draft(ws, revision)
    assert child.id == revision.revised_paper_id and child.id != base.id and child.study_id == base.study_id
    assert digest_file(ws.path(f"freezes/{base.id}/canonical.json")) == original
    assert revisions.check(ws, revision)["drafted"]
    assert (ws.path(f"revisions/{revision.id}") / "report.bin").read_bytes() == report.read_bytes()
    assert (root / "canonical.json").is_file()
    with pytest.raises(ValueError, match="already exists"):
        revisions.draft(ws, revision)


@pytest.mark.parametrize("change,match", [
    ({"reviewed_by": "Unknown Author"}, "approved named author"),
    ({"comments": [{"id": "comment-a", "excerpt": "Invented reviewer request", "sections": ["Method"]}]}, "actual referee report"),
    ({"comments": [{"id": "comment-a", "excerpt": "Please clarify the analysis method.", "sections": ["Nonexistent"]}]}, "submitted scientific freeze"),
    ({"comments": [{"id": "comment-a", "excerpt": "Please clarify the analysis method.", "claim_ids": ["claim-fake"]}]}, "submitted scientific freeze"),
])
def test_review_observation_rejects_unknown_author_quote_or_original_target(prepared, mock_conversion, tmp_path, change, match):
    with pytest.raises(ValueError, match=match):
        review_case(prepared, tmp_path, **change)
    assert not prepared[0].list("revision", Revision)


def test_explicit_confirmation_current_revision_decision_and_single_open_round_are_required(prepared, mock_conversion, tmp_path):
    ws, _, submission, revision, spec, report = review_case(prepared, tmp_path)
    with pytest.raises(ValueError, match="Explicit author confirmation"):
        revisions.import_review(ws, submission, spec, report)
    with pytest.raises(ValueError, match="already has an open revision"):
        revisions.import_review(ws, submission, spec, report, confirmed=True)
    receipt(ws, submission, SubmissionState.REJECTED, tmp_path)
    assert revisions.verify_review(ws, revision) == []
    assert not revisions.check(ws, revision)["passed"]
    with pytest.raises(ValueError, match="current confirmed"):
        revisions.draft(ws, revision)
    with pytest.raises(ValueError, match="confirmed journal REVISION"):
        revisions.import_review(ws, submission, spec, report, confirmed=True)


def test_native_crlf_report_preserves_raw_bytes_and_verifies_exact_multiline_quote(prepared, mock_conversion, tmp_path):
    ws, _, submission, handler = ready_case(prepared)
    attest(ws, submission, handler)
    receipt(ws, submission, SubmissionState.SUBMITTED, tmp_path)
    receipt(ws, submission, SubmissionState.REVISION, tmp_path)
    report = tmp_path / "windows-report.txt"
    report.write_bytes(b"Please clarify the method.\r\nPlease state its limitations.\r\n")
    spec = tmp_path / "review.json"
    write_json(spec, ReviewSpec(reviewed_by="Fixture [Author]", comments=[ReviewComment(id="review-a", excerpt="Please clarify the method.\nPlease state its limitations.", sections=["Method", "Limitations"])]))
    revision, root = revisions.import_review(ws, submission, spec, report, confirmed=True)
    assert (root / "report.bin").read_bytes() == report.read_bytes()
    assert revisions.verify_review(ws, revision) == []


def test_pending_unapplied_and_accepted_unchanged_comments_block_response_readiness(prepared, mock_conversion, tmp_path):
    ws, _, _, revision, _, _ = review_case(prepared, tmp_path)
    revisions.draft(ws, revision)
    path = tmp_path / "pending.json"
    write_json(path, revisions.plan_template(ws, revision))
    pending, _ = revisions.build_response(ws, revision, path)
    assert not pending.ready and any("pending" in error for error in pending.errors)
    _, path = response_plan(ws, revision, tmp_path)
    unapplied, _ = revisions.build_response(ws, revision, path)
    assert not unapplied.ready and any("has not been applied" in error for error in unapplied.errors)
    plan, path = response_plan(ws, revision, tmp_path, edit=False)
    unchanged, _ = revisions.build_response(ws, revision, path)
    assert not unchanged.ready and any("actually changed" in error for error in unchanged.errors)


def test_applied_author_changes_build_hashed_letter_diff_and_require_separate_scientific_approval(prepared, mock_conversion, tmp_path):
    ws, base, _, revision, _, _ = review_case(prepared, tmp_path)
    revisions.draft(ws, revision)
    _, path = response_plan(ws, revision, tmp_path)
    child, _ = revisions.apply_plan(ws, revision, path)
    response, root = revisions.build_response(ws, revision, path)
    assert response.ready and revisions.verify_response(ws, response)["passed"]
    assert not revisions.verify_response(ws, response, require_approved=True)["ready"]
    assert "registered descriptive inspection protocol" in (root / "manuscript.diff").read_text(encoding="utf-8")
    assert "comment-a,accept,Method" in (root / "changes.csv").read_text(encoding="utf-8")
    integrity.approve(ws, child, approved=True, assessment="The referee response, related work, measured evidence and limitations were reviewed.")
    assert revisions.verify_response(ws, response, require_approved=True)["passed"]
    assert ws.get("paper", base.id, Paper).freeze_digest == base.freeze_digest
    with pytest.raises(ValueError, match="frozen"):
        revisions.apply_plan(ws, revision, path)


@pytest.mark.parametrize("disposition", ["partially_accept", "disagree"])
def test_partial_acceptance_and_disagreement_need_actual_author_rationale(prepared, mock_conversion, tmp_path, disposition):
    ws, _, _, revision, _, _ = review_case(prepared, tmp_path)
    revisions.draft(ws, revision)
    plan, path = response_plan(ws, revision, tmp_path, disposition, edit=disposition != "disagree")
    if plan.responses[0].edits:
        revisions.apply_plan(ws, revision, path)
    response, _ = revisions.build_response(ws, revision, path)
    assert response.ready
    plan.responses[0].justification = ""
    write_json(path, plan)
    blocked, _ = revisions.build_response(ws, revision, path)
    assert not blocked.ready and any("justification" in error for error in blocked.errors)


@pytest.mark.parametrize("text", ["We achieved accuracy of 99 percent.", "We measured twenty files.", "We proved the approach is novel.", "See DOI: 10.5555/unverified."])
def test_author_response_cannot_invent_numeric_results_novelty_or_inline_citations(prepared, mock_conversion, tmp_path, text):
    ws, _, _, revision, _, _ = review_case(prepared, tmp_path)
    revisions.draft(ws, revision)
    plan, path = response_plan(ws, revision, tmp_path, "disagree", edit=False)
    plan.responses[0].reply = text
    write_json(path, plan)
    response, _ = revisions.build_response(ws, revision, path)
    assert not response.ready
    assert not revisions.verify_response(ws, response)["ready"]


def test_numeric_actual_reviewer_quote_is_preserved_without_becoming_author_result(prepared, mock_conversion, tmp_path):
    ws, _, _, revision, _, _ = review_case(prepared, tmp_path, "Can the study achieve accuracy of 99 percent? See DOI: 10.5555/reviewer.")
    revisions.draft(ws, revision)
    _, path = response_plan(ws, revision, tmp_path, "disagree", edit=False)
    response, root = revisions.build_response(ws, revision, path)
    assert response.ready and "Reviewer excerpt:" in (root / "letter.md").read_text(encoding="utf-8")
    assert "99 percent" in (root / "letter.md").read_text(encoding="utf-8")


def test_rejected_quantitative_section_edits_leave_child_science_unchanged(prepared, mock_conversion, tmp_path):
    ws, _, _, revision, _, _ = review_case(prepared, tmp_path)
    child, root = revisions.draft(ws, revision)
    plan, path = response_plan(ws, revision, tmp_path)
    plan.responses[0].edits[0].blocks = [manuscript.prose("We achieved accuracy of 99 percent.")]
    write_json(path, plan)
    original = (root / "canonical.json").read_bytes()
    with pytest.raises(ValueError, match="quantitative prose"):
        revisions.apply_plan(ws, revision, path)
    assert (root / "canonical.json").read_bytes() == original
    assert ws.get("paper", child.id, Paper).document_sha256 == child.document_sha256


def test_additional_experiments_require_executed_postreview_run_and_a_manuscript_claim(prepared, mock_conversion, tmp_path):
    ws, _, _, revision, _, _ = review_case(prepared, tmp_path)
    revisions.draft(ws, revision)
    plan, path = response_plan(ws, revision, tmp_path)
    response = plan.responses[0]
    response.additional_experiments_required = True
    old = ws.list("run", ExperimentRun)[0]
    response.run_ids = [old.id]
    response.experiment_ids = [old.experiment_id]
    response.claim_ids = [claim.id for claim in ws.list("claim", Claim) if claim.run_id == old.id]
    write_json(path, plan)
    revisions.apply_plan(ws, revision, path)
    blocked, _ = revisions.build_response(ws, revision, path)
    assert not blocked.ready and any("post-review" in error for error in blocked.errors)
    fresh = experiments.run_experiment(ws, ws.get("manifest", old.experiment_id, ExperimentManifest))
    assert fresh.status == "SUCCEEDED"
    claims = manuscript.claims_for_run(ws, fresh)
    response.run_ids = [fresh.id]
    response.claim_ids = [claim.id for claim in claims]
    # New claim must enter both Abstract and Results, as required by the existing validator.
    child_root = ws.path(f"manuscripts/{revision.revised_paper_id}")
    doc = manuscript.Document.model_validate_json((child_root / "canonical.json").read_bytes())
    for section in doc.sections:
        if section.heading in {"Abstract", "Results"}:
            section.blocks += [manuscript.Block(kind="claim", ref=claim.id) for claim in claims]
    write_json(child_root / "canonical.json", doc)
    manuscript.refresh(ws, ws.get("paper", revision.revised_paper_id, Paper))
    write_json(path, plan)
    ready, root = revisions.build_response(ws, revision, path)
    assert ready.ready and revisions.verify_response(ws, ready)["passed"]
    assert fresh.id in (root / "letter.md").read_text(encoding="utf-8")
    assert claims[0].id in (root / "letter.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("value", ["true", 1, None])
def test_additional_experiment_decision_is_an_explicit_strict_boolean(value):
    with pytest.raises(ValidationError):
        CommentResponse(comment_id="comment-a", additional_experiments_required=value)


@pytest.mark.parametrize("case", ["failed", "different-study"])
def test_failed_or_other_study_experiments_cannot_answer_requested_additional_analysis(prepared, mock_conversion, tmp_path, case):
    ws, _, _, revision, _, _ = review_case(prepared, tmp_path)
    revisions.draft(ws, revision)
    plan, path = response_plan(ws, revision, tmp_path)
    source = ws.list("manifest", ExperimentManifest)[0]
    manifest = source.model_copy(update={"id": uid("experiment")}, deep=True)
    if case == "failed":
        manifest.command = ["{python}", "-c", "raise SystemExit(7)"]
    else:
        independent = research.create_study(ws, question="Which measurements describe this separate protocol?", title="Independent fixture")
        manifest.study_id = independent.id
    manifest_path = tmp_path / "requested-experiment.json"
    write_json(manifest_path, manifest)
    experiments.register_manifest(ws, manifest_path)
    run = experiments.run_experiment(ws, manifest)
    response = plan.responses[0]
    response.additional_experiments_required = True
    response.experiment_ids = [manifest.id]
    response.run_ids = [run.id]
    if case == "different-study":
        response.claim_ids = [claim.id for claim in manuscript.claims_for_run(ws, run)]
    write_json(path, plan)
    revisions.apply_plan(ws, revision, path)
    blocked, _ = revisions.build_response(ws, revision, path)
    assert not blocked.ready
    assert any("successful experiment" in error or "another Study" in error or "same-Study" in error for error in blocked.errors)


def test_response_plan_cannot_replace_a_real_comment_with_an_invented_comment(prepared, mock_conversion, tmp_path):
    ws, _, _, revision, _, _ = review_case(prepared, tmp_path)
    revisions.draft(ws, revision)
    plan, path = response_plan(ws, revision, tmp_path)
    plan.responses[0].comment_id = "invented-comment"
    write_json(path, plan)
    with pytest.raises(ValueError, match="every actual reviewer comment"):
        revisions.build_response(ws, revision, path)


def test_large_or_empty_review_inputs_are_rejected_before_unbounded_read(tmp_path):
    report = tmp_path / "large-report.txt"
    with report.open("wb") as stream:
        stream.truncate(revisions.MAX_REPORT_BYTES + 1)
    with pytest.raises(ValueError, match="20 MiB"):
        revisions._read_bounded(report)
    report.write_bytes(b"")
    with pytest.raises(ValueError, match="nonempty"):
        revisions._read_bounded(report)


def test_actual_pdf_referee_extraction_rejects_encrypted_and_unreadable_reports(tmp_path):
    typst = pytest.importorskip("typst")
    pypdf = pytest.importorskip("pypdf")
    source = tmp_path / "referee.typ"
    source.write_text('Please clarify the registered analysis method.\n', encoding="utf-8")
    raw = typst.compile(str(source), root=str(tmp_path))
    assert "Please clarify the registered analysis method." in revisions._report_text(raw, "pdf")
    writer = pypdf.PdfWriter()
    writer.append(io.BytesIO(raw))
    writer.encrypt("fixture-password")
    encrypted = io.BytesIO()
    writer.write(encrypted)
    with pytest.raises(ValueError, match="Encrypted"):
        revisions._report_text(encrypted.getvalue(), "pdf")
    blank = pypdf.PdfWriter()
    blank.add_blank_page(width=100, height=100)
    unreadable = io.BytesIO()
    blank.write(unreadable)
    with pytest.raises(ValueError, match="no extractable text"):
        revisions._report_text(unreadable.getvalue(), "pdf")


@pytest.mark.parametrize("artifact", ["report.bin", "report-text.txt", "spec.json", "review.json", "delete-index"])
def test_review_tampering_or_hidden_registry_entry_fails_closed(prepared, mock_conversion, tmp_path, artifact):
    ws, _, _, revision, _, _ = review_case(prepared, tmp_path)
    if artifact == "delete-index":
        with ws._database() as db:
            db.execute("DELETE FROM records WHERE kind='revision' AND id=?", (revision.id,))
    else:
        ws.path(f"revisions/{revision.id}/{artifact}").write_text("Tampered", encoding="utf-8")
    assert revisions.verify_review(ws, revision)
    with pytest.raises(ValueError, match="history is invalid"):
        revisions.draft(ws, revision)


@pytest.mark.parametrize("artifact", ["letter.md", "changes.csv", "manuscript.diff", "bindings.json", "delete-index"])
def test_response_tampering_or_hidden_registry_entry_fails_closed(prepared, mock_conversion, tmp_path, artifact):
    ws, _, _, revision, _, _ = review_case(prepared, tmp_path)
    revisions.draft(ws, revision)
    _, path = response_plan(ws, revision, tmp_path, "disagree", edit=False)
    response, root = revisions.build_response(ws, revision, path)
    if artifact == "delete-index":
        with ws._database() as db:
            db.execute("DELETE FROM records WHERE kind='revision_response' AND id=?", (response.id,))
    else:
        (root / artifact).write_text("Tampered", encoding="utf-8")
    assert not revisions.verify_response(ws, response)["passed"]


def test_response_bound_to_actual_document_becomes_stale_after_author_edit(prepared, mock_conversion, tmp_path):
    ws, _, _, revision, _, _ = review_case(prepared, tmp_path)
    child, root = revisions.draft(ws, revision)
    _, path = response_plan(ws, revision, tmp_path, "disagree", edit=False)
    response, _ = revisions.build_response(ws, revision, path)
    doc = manuscript.Document.model_validate_json((root / "canonical.json").read_bytes())
    next(section for section in doc.sections if section.heading == "Discussion").blocks = [manuscript.prose("The interpretation remains limited to the declared descriptive protocol.")]
    write_json(root / "canonical.json", doc)
    manuscript.refresh(ws, child)
    result = revisions.verify_response(ws, response)
    assert not result["ready"] and any("stale" in error for error in result["errors"])


def test_response_remains_auditable_after_terminal_decision_but_cannot_be_prepared(prepared, mock_conversion, tmp_path):
    ws, _, submission, revision, _, _ = review_case(prepared, tmp_path)
    child, _ = revisions.draft(ws, revision)
    _, path = response_plan(ws, revision, tmp_path, "disagree", edit=False)
    response, _ = revisions.build_response(ws, revision, path)
    integrity.approve(ws, child, approved=True, assessment="Author reviewed response, related work, evidence and limitations.")
    receipt(ws, submission, SubmissionState.REJECTED, tmp_path)
    assert revisions.verify_response(ws, response, require_approved=True)["passed"]
    assert not revisions.verify_response(ws, response, require_active=True)["passed"]
    with pytest.raises(ValueError, match="current confirmed"):
        revisions.build_response(ws, revision, path)


@pytest.mark.parametrize("operation", ["import", "response"])
def test_database_commit_failure_removes_only_the_uncommitted_review_or_response(prepared, mock_conversion, tmp_path, monkeypatch, operation):
    if operation == "import":
        ws, paper, submission, handler = ready_case(prepared)
        attest(ws, submission, handler)
        receipt(ws, submission, SubmissionState.SUBMITTED, tmp_path)
        receipt(ws, submission, SubmissionState.REVISION, tmp_path)
        spec, report = tmp_path / "review.json", tmp_path / "report.txt"
        report.write_text("Please clarify the analysis method.", encoding="utf-8")
        write_json(spec, ReviewSpec(reviewed_by=paper.approved_by, comments=[ReviewComment(id="comment-a", excerpt="Please clarify the analysis method.", sections=["Method"])]))
        kind = "revision"
    else:
        ws, _, submission, revision, spec, report = review_case(prepared, tmp_path)
        revisions.draft(ws, revision)
        _, path = response_plan(ws, revision, tmp_path, "disagree", edit=False)
        kind = "revision_response"
    count = len(ws.list(kind, Revision if kind == "revision" else ResponseBuild))
    original = ws._database
    failed = False

    @contextmanager
    def fail_commit():
        nonlocal failed
        with original() as db:
            yield db
            current = db.execute("SELECT count(*) FROM records WHERE kind=?", (kind,)).fetchone()[0]
            if current > count and not failed:
                failed = True
                raise OSError("Synthetic revision commit failure")

    monkeypatch.setattr(ws, "_database", fail_commit)
    with pytest.raises(OSError, match="Synthetic revision commit failure"):
        if operation == "import":
            revisions.import_review(ws, submission, spec, report, confirmed=True)
        else:
            revisions.build_response(ws, revision, path)
    assert len(ws.list(kind, Revision if kind == "revision" else ResponseBuild)) == count
    revisions._registry(ws)
    if operation == "response":
        assert revisions.verify_review(ws, revision) == []

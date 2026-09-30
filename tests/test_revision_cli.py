import json

from typer.testing import CliRunner

from paper_factory import revisions
from paper_factory.cli import app
from paper_factory.models import ExperimentManifest, uid
from paper_factory.workspace import write_json
from test_publication import ready_case, attest, receipt
from test_revisions import review_case, response_plan
from test_revision_submission import delivery_case
from test_submission import prepared, mock_conversion
from test_venue_policy import setup_policy


def invoke(ws, *arguments):
    return CliRunner().invoke(app, ["--workspace", str(ws.root), *arguments])


def test_revision_cli_schemas_expose_exact_quotes_and_explicit_experiment_requirement():
    result = CliRunner().invoke(app, ["revision", "schema"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert "excerpt" in data["review"]["$defs"]["ReviewComment"]["properties"]
    assert "additional_experiments_required" in data["response_plan"]["$defs"]["CommentResponse"]["required"]


def test_revision_cli_import_requires_confirm_and_preserves_actual_report(prepared, mock_conversion, tmp_path):
    ws, paper, submission, handler = ready_case(prepared)
    attest(ws, submission, handler)
    receipt(ws, submission, "SUBMITTED", tmp_path)
    receipt(ws, submission, "REVISION", tmp_path)
    spec, report = tmp_path / "review.json", tmp_path / "review.txt"
    quote = "Please clarify the analysis method."
    write_json(spec, {"reviewed_by": paper.approved_by, "comments": [{"id": "review-a", "excerpt": quote, "sections": ["Method"]}]})
    report.write_text(quote, encoding="utf-8")
    rejected = invoke(ws, "revision", "import", submission.id, str(spec), str(report))
    assert rejected.exit_code == 1 and "confirmation" in rejected.output
    result = invoke(ws, "revision", "import", submission.id, str(spec), str(report), "--confirm")
    assert result.exit_code == 0, result.output
    record = json.loads(result.stdout)["revision"]
    assert ws.path(f"revisions/{record['id']}/report.bin").read_bytes() == report.read_bytes()


def test_revision_cli_draft_plan_apply_response_and_check_work_end_to_end(prepared, mock_conversion, tmp_path):
    ws, _, _, revision, _, _ = review_case(prepared, tmp_path)
    result = invoke(ws, "revision", "draft", revision.id)
    assert result.exit_code == 0, result.output
    pending_path = tmp_path / "pending.json"
    result = invoke(ws, "revision", "plan", revision.id, "--output", str(pending_path))
    assert result.exit_code == 0, result.output
    result = invoke(ws, "revision", "response", revision.id, str(pending_path))
    assert result.exit_code == 1
    assert not json.loads(result.stdout)["response"]["ready"]
    _, plan_path = response_plan(ws, revision, tmp_path)
    result = invoke(ws, "revision", "apply", revision.id, str(plan_path))
    assert result.exit_code == 0, result.output
    result = invoke(ws, "revision", "response", revision.id, str(plan_path))
    assert result.exit_code == 0, result.output
    response_id = json.loads(result.stdout)["response"]["id"]
    result = invoke(ws, "revision", "response-check", response_id)
    assert result.exit_code == 0 and json.loads(result.stdout)["ready"], result.output
    result = invoke(ws, "revision", "response-check", response_id, "--approved")
    assert result.exit_code == 1
    result = invoke(ws, "revision", "check", revision.id)
    assert result.exit_code == 0 and json.loads(result.stdout)["drafted"], result.output


def test_revision_cli_plan_cannot_overwrite_preserved_review_artifact(prepared, mock_conversion, tmp_path):
    ws, _, _, revision, _, _ = review_case(prepared, tmp_path)
    destination = ws.path(f"revisions/{revision.id}/review.json")
    original = destination.read_bytes()
    result = invoke(ws, "revision", "plan", revision.id, "--output", str(destination))
    assert result.exit_code == 1 and "artifact directories" in result.output
    assert destination.read_bytes() == original


def test_revision_cli_experiment_cannot_execute_another_study_manifest(prepared, mock_conversion, tmp_path):
    ws, _, _, revision, _, _ = review_case(prepared, tmp_path)
    manifest = ws.list("manifest", ExperimentManifest)[0].model_copy(update={"id": uid("experiment"), "study_id": "study-unrelated"})
    path = tmp_path / "unrelated-experiment.json"
    write_json(path, manifest)
    result = invoke(ws, "revision", "experiment", revision.id, str(path))
    assert result.exit_code == 1 and "original Study" in result.output
    assert all(item.id != manifest.id for item in ws.list("manifest", ExperimentManifest))


def test_revision_delivery_cli_requires_separate_approval_and_receipt_confirmation(prepared, mock_conversion, tmp_path):
    ws, _, _, _, _, _, _, delivery, _ = delivery_case(prepared, tmp_path)
    path = tmp_path / "facts.json"
    result = invoke(ws, "revision", "submission", "attestation", delivery.id, "--output", str(path))
    assert result.exit_code == 0, result.output
    facts = json.loads(path.read_text(encoding="utf-8"))
    assert facts["all_authors_approved"] is False and facts["not_under_review_elsewhere"] is False
    result = invoke(ws, "revision", "submission", "attest", delivery.id, str(path))
    assert result.exit_code == 1 and "--approve" in result.output
    result = invoke(ws, "revision", "submission", "record", delivery.id, str(path), str(path))
    assert result.exit_code == 1 and "--confirm" in result.output
    result = invoke(ws, "revision", "submission", "check", delivery.id)
    assert result.exit_code == 0, result.output
    audit = json.loads(result.stdout)
    assert audit["local_review_bundle_ready"] and audit["revision_portal_requirements_verified"] is False

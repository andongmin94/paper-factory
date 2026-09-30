"""Author gates and imported receipts through the actual command interface."""

import json
import os
from pathlib import Path
import subprocess
import sys

import httpx
from typer.testing import CliRunner

from paper_factory import cli, preprints, publication, submission_package
from paper_factory.cli import app
from paper_factory.models import Paper, Submission, SubmissionState, now
from paper_factory.workspace import write_json
from test_submission import compile_case, mock_conversion, prepared
from test_venue_policy import setup_policy


def ready_case(prepared):
    ws, paper, submission, _, handler = compile_case(prepared)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        submission_package.build(ws, submission, client=client)
    return ws, ws.get("paper", paper.id, Paper), ws.get("submission", submission.id, Submission), handler


def affirmative(actor):
    return {"actor": actor, "all_authors_approved": True, "not_under_review_elsewhere": True,
            "coi_correct": True, "funding_correct": True, "ai_disclosure_correct": True,
            "author_information_correct": True}


def invoke(runner, ws, *args):
    return runner.invoke(app, ["--workspace", str(ws.root), *map(str, args)])


def test_author_confirmation_and_receipt_evidence_are_enforced_by_cli(prepared, mock_conversion, tmp_path, monkeypatch):
    ws, paper, submission, handler = ready_case(prepared)
    runner = CliRunner()
    attestation = tmp_path / "attest.json"
    result = invoke(runner, ws, "submission", "attestation", submission.id, "--output", attestation)
    assert result.exit_code == 0, result.output
    draft = json.loads(attestation.read_bytes())
    assert draft["actor"] == paper.approved_by
    assert all(draft[field] is False for field in affirmative(paper.approved_by) if field != "actor")
    denied = invoke(runner, ws, "submission", "attest", submission.id, attestation)
    assert denied.exit_code == 1 and "--approve" in denied.output
    denied = invoke(runner, ws, "submission", "attest", submission.id, attestation, "--approve")
    assert denied.exit_code == 1 and "true" in denied.output
    assert ws.get("submission", submission.id, Submission).state == SubmissionState.SUBMISSION_READY

    write_json(attestation, affirmative(paper.approved_by))
    original_refresh = publication.refresh_policy
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(publication, "refresh_policy", lambda workspace, policy, **kwargs: original_refresh(workspace, policy, client=client))
        result = invoke(runner, ws, "submission", "attest", submission.id, attestation, "--approve")
    assert result.exit_code == 0, result.output
    assert ws.get("submission", submission.id, Submission).state == SubmissionState.AUTHOR_ATTESTED
    assert json.loads(result.stdout)["external_submission_performed"] is False
    assert submission_package.verify(ws, submission)["ready"]

    receipt_json = tmp_path / "receipt.json"
    receipt_file = tmp_path / "actual-receipt.txt"
    receipt_file.write_text("SYNTHETIC TEST RECEIPT: journal confirms submission FIXTURE-001.", encoding="utf-8")
    write_json(receipt_json, {"target_state": "SUBMITTED", "external_id": "FIXTURE-001",
                            "external_url": "https://submit.example.org/manuscript/FIXTURE-001",
                            "occurred_at": now(), "verified_by": paper.approved_by,
                            "note": "Synthetic author reviewed the synthetic confirmation receipt."})
    denied = invoke(runner, ws, "submission", "record-receipt", submission.id, receipt_json, receipt_file)
    assert denied.exit_code == 1 and "--confirm" in denied.output
    result = invoke(runner, ws, "submission", "record-receipt", submission.id, receipt_json, receipt_file, "--confirm")
    assert result.exit_code == 0, result.output
    assert ws.get("submission", submission.id, Submission).state == SubmissionState.SUBMITTED
    history = invoke(runner, ws, "submission", "history", submission.id)
    assert history.exit_code == 0, history.output
    report = json.loads(history.stdout)
    assert report["passed"] and report["active"] and report["external_submission_recorded"]
    cancelled = invoke(runner, ws, "submission", "cancel-attestation", submission.id,
                       "--actor", paper.approved_by, "--reason", "Synthetic cancellation cannot cancel a submitted paper.")
    assert cancelled.exit_code == 1
    status = invoke(runner, ws, "status")
    assert status.exit_code == 0, status.output
    assert json.loads(status.stdout)["external_submission_recorded"] is True
    assert json.loads(status.stdout)["external_submission_performed"] is False

    # The CLI points to immutable copies: changing the input cannot rewrite history.
    receipt_file.write_text("changed original input", encoding="utf-8")
    assert invoke(runner, ws, "submission", "history", submission.id).exit_code == 0
    event = ws.latest("publication_event", publication.PublicationEvent)
    ws.path(f"publication/{submission.id}/{event.id}/evidence.bin").write_bytes(b"tampered preserved receipt")
    tampered = invoke(runner, ws, "submission", "history", submission.id)
    assert tampered.exit_code == 1 and "changed" in tampered.output


def test_preprint_receipt_cli_records_facts_without_peer_review_or_upload(prepared, mock_conversion, tmp_path):
    ws, paper, submission, _ = ready_case(prepared)
    runner = CliRunner()
    settings = tmp_path / "preprint-settings.json"
    result = invoke(runner, ws, "preprint", "settings", "--policy", submission.policy_id,
                    "--paper", paper.id, "--output", settings)
    assert result.exit_code == 0, result.output
    values = json.loads(settings.read_bytes())
    assert values["decision"] == "unknown" and values["author_approval"] is False
    denied = invoke(runner, ws, "preprint", "prepare", settings)
    assert denied.exit_code == 1 and "--approve" in denied.output

    receipt = tmp_path / "preprint-receipt.json"
    evidence = tmp_path / "actual-posting.txt"
    evidence.write_text("SYNTHETIC POSTING RECEIPT: synthetic:cli-v1 was posted.", encoding="utf-8")
    write_json(receipt, {"paper_id": paper.id, "remote_identifier": "synthetic:cli-v1",
                        "source_url": "https://preprints.example.org/synthetic-cli-v1",
                        "posted_at": now(), "recorded_by": paper.approved_by,
                        "statement": "Synthetic author confirms this synthetic external posting fact.",
                        "content_digest": paper.freeze_digest})
    denied = invoke(runner, ws, "preprint", "record", receipt, evidence)
    assert denied.exit_code == 1
    result = invoke(runner, ws, "preprint", "record", receipt, evidence, "--confirm")
    assert result.exit_code == 0, result.output
    record = ws.latest("preprint", preprints.Preprint)
    report = invoke(runner, ws, "preprint", "check", record.id)
    assert report.exit_code == 0, report.output
    observed = json.loads(report.stdout)
    assert observed["posting_recorded"] and not observed["upload_authorized"] and not observed["peer_reviewed"]
    assert ws.get("submission", submission.id, Submission).state == SubmissionState.SUBMISSION_READY
    ws.path(f"preprints/{record.id}/posting/evidence.bin").write_bytes(b"changed evidence")
    assert invoke(runner, ws, "preprint", "check", record.id).exit_code == 1


def test_cli_exposes_publication_and_preprint_schemas_without_a_workspace():
    runner = CliRunner()
    assert runner.invoke(app, ["submission", "receipt-schema"]).exit_code == 0
    assert runner.invoke(app, ["preprint", "schema"]).exit_code == 0


def test_cli_json_preserves_unicode_in_windows_legacy_output_encoding():
    env = dict(os.environ, PYTHONIOENCODING="cp949", PYTHONUTF8="0")
    result = subprocess.run([sys.executable, "-c", "from paper_factory.cli import output; output({'title': '\\u2013 \\U0001f4da \\uc5f0\\uad6c'})"],
                            capture_output=True, env=env, cwd=Path(__file__).resolve().parents[1], timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.decode("ascii"))["title"] == "– 📚 연구"

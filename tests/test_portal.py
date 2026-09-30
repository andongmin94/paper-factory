"""Synthetic official-contract OJS transport; never creates a live journal record."""

import json
from pathlib import Path
import subprocess
import sys

import httpx
import pytest
from typer.testing import CliRunner

from paper_factory import cli, portal, publication, submission_package
from paper_factory.models import Paper, Submission, SubmissionState
from paper_factory.ojs import OJSClient, OJSError, OJSSettings
from paper_factory.workspace import write_json
from test_publication import author_values
from test_submission import compile_case, mock_conversion, prepared
from test_venue_policy import setup_policy


@pytest.fixture
def portal_case(prepared, mock_conversion):
    ws, paper, submission, _, handler = compile_case(prepared, blind=True,
        changes={"submission_url": "https://submit.example.org/journal/submission", "submission_system": "OJS 3.5"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        submission_package.build(ws, submission, client=client)
    submission = ws.get("submission", submission.id, Submission)
    settings = portal.PortalSettings(connection=OJSSettings(api_url="https://submit.example.org/journal/api/v1"),
        draft=portal.OJSDraft(sectionId=2, locale="en"), uploads=[portal.Upload(path="manuscript.pdf", genre_id=7)])
    plan = portal.prepare(ws, submission, settings)
    return ws, paper, submission, plan, handler


class Journal:
    def __init__(self):
        self.submission = {"id": 123, "currentPublicationId": 456, "locale": "en", "status": 1,
            "submissionProgress": "start", "dateSubmitted": None, "publications": [{"id": 456}]}
        self.publication = {"id": 456, "submissionId": 123, "sectionId": 2, "title": {}, "abstract": {}}
        self.authors = [{"id": 99, "publicationId": 456, "givenName": {"en": "Fixture [Author]"},
            "email": "author@example.org", "affiliations": [{"name": {"en": "Fixture *University*"}}]}]
        self.files = []
        self.calls = []
        self.fail = None
        self.submit_count = 0

    def handler(self, request):
        route = request.url.path.split("/api/v1", 1)[1]
        self.calls.append((request.method, route))
        assert request.headers["Host"] == "submit.example.org"
        assert request.extensions["sni_hostname"] == "submit.example.org"
        assert request.headers["Authorization"] == "Bearer synthetic-fixture-token"
        payload = json.loads(request.content) if request.headers.get("content-type", "").startswith("application/json") else None
        if route == "/submissions" and request.method == "POST":
            if self.fail == "create":
                raise httpx.ReadTimeout("synthetic ambiguous creation")
            return httpx.Response(200, json=self.submission)
        if route == "/submissions/123" and request.method == "GET":
            return httpx.Response(200, json=self.submission)
        if route == "/submissions/123/publications/456":
            if request.method == "PUT":
                self.publication.update(payload)
            return httpx.Response(200, json=self.publication)
        if route == "/submissions/123/publications/456/contributors":
            return httpx.Response(200, json={"itemsMax": len(self.authors), "items": self.authors})
        if route == "/submissions/123/files":
            if request.method == "POST":
                assert b'filename="manuscript.pdf"' in request.content
                # Blinded native manuscript is uploaded; administrative identity
                # and the whole ZIP archive never cross this adapter boundary.
                assert b"author@example.org" not in request.content
                if self.fail == "upload":
                    raise httpx.ReadTimeout("synthetic ambiguous upload")
                item = {"id": 15, "fileId": 25, "submissionId": 123, "genreId": 7, "fileStage": 2,
                    "name": {"en": "manuscript.pdf"}}
                self.files.append(item)
                return httpx.Response(200, json=item)
            return httpx.Response(200, json={"itemsMax": len(self.files), "items": self.files})
        if route == "/submissions/123/submit":
            if payload.get("_validateOnly"):
                return httpx.Response(200, json=[])
            self.submit_count += 1
            if self.fail == "rejected":
                return httpx.Response(400, json={"files": ["synthetic missing requirement"]})
            self.submission.update(submissionProgress="", dateSubmitted="2026-09-30 01:02:03")
            if self.fail == "submit":
                raise httpx.ReadTimeout("synthetic accepted request with lost response")
            return httpx.Response(200, json=self.submission)
        raise AssertionError((request.method, route))

    def client(self, plan):
        return OJSClient(plan.settings.connection, "synthetic-fixture-token",
            client=httpx.Client(transport=httpx.MockTransport(self.handler), trust_env=False))


def deliver(ws, plan, journal):
    with journal.client(plan) as client:
        return portal.connect(ws, plan, client, upload=True)


def final(ws, plan, journal, handler, review, **kwargs):
    with journal.client(plan) as client, httpx.Client(transport=httpx.MockTransport(handler)) as policy_client:
        return portal.submit(ws, plan, client, author_values(), review_sha256=review,
            approve=True, final_submit=True, policy_client=policy_client, **kwargs)


def test_end_to_end_official_contract_preserves_science_and_records_confirmed_submit(portal_case):
    ws, paper, submission, plan, handler = portal_case
    freeze = paper.freeze_digest
    original_zip = ws.path(f"submissions/{submission.id}/package/submission.zip").read_bytes()
    journal = Journal()
    reviewed = deliver(ws, plan, journal)
    result = final(ws, plan, journal, handler, reviewed["review_sha256"])
    assert result["state"] == "SUBMITTED" and journal.submit_count == 1
    assert ws.get("submission", submission.id, Submission).state == SubmissionState.SUBMITTED
    assert ws.get("paper", paper.id, Paper).freeze_digest == freeze
    assert ws.path(f"submissions/{submission.id}/package/submission.zip").read_bytes() == original_zip
    assert len(publication.active_for_study(ws, paper.study_id)) == 1
    report = portal.check(ws, plan)
    assert report["passed"] and report["submission_confirmed"] and not report["uncertain_operations"]
    assert publication.check(ws, submission)["passed"]
    with pytest.raises(ValueError, match="attempted"):
        final(ws, plan, journal, handler, reviewed["review_sha256"])
    assert journal.submit_count == 1
    assert not any("synthetic-fixture-token" in p.read_text(encoding="utf-8") for p in ws.path(f"portals/{plan.id}").iterdir())


def test_unknown_final_submit_keeps_slot_blocks_cancel_and_reconciles_without_retry(portal_case):
    ws, paper, submission, plan, handler = portal_case
    journal = Journal()
    reviewed = deliver(ws, plan, journal)
    journal.fail = "submit"
    with pytest.raises(OJSError) as error:
        final(ws, plan, journal, handler, reviewed["review_sha256"])
    assert error.value.reconciliation_required
    assert portal.check(ws, plan)["uncertain_operations"] == ["submit"]
    assert ws.get("submission", submission.id, Submission).state == SubmissionState.AUTHOR_ATTESTED
    with pytest.raises(ValueError, match="cannot be cancelled"):
        publication.cancel_attestation(ws, submission, paper.approved_by, "Synthetic author cannot cancel an uncertain submission.")
    with pytest.raises(ValueError, match="uncertain"):
        final(ws, plan, journal, handler, reviewed["review_sha256"])
    with journal.client(plan) as client:
        result = portal.reconcile(ws, plan, client, actor=paper.approved_by)
    assert result["state"] == "SUBMITTED" and journal.submit_count == 1
    assert not portal.check(ws, plan)["uncertain_operations"]


def test_definite_final_rejection_can_release_unused_author_slot(portal_case):
    ws, paper, submission, plan, handler = portal_case
    journal = Journal()
    reviewed = deliver(ws, plan, journal)
    journal.fail = "rejected"
    with pytest.raises(OJSError) as error:
        final(ws, plan, journal, handler, reviewed["review_sha256"])
    assert not error.value.reconciliation_required
    publication.cancel_attestation(ws, submission, paper.approved_by, "Provider rejected final submission before accepting it.")
    assert not publication.active_for_study(ws, paper.study_id)


@pytest.mark.parametrize("field", ["title", "contributors", "genre", "file", "review"])
def test_changed_remote_material_blocks_final_submit(portal_case, field):
    ws, _, _, plan, handler = portal_case
    journal = Journal()
    reviewed = deliver(ws, plan, journal)
    if field == "title":
        journal.publication["title"]["en"] = "A different unsupported study"
    elif field == "contributors":
        journal.authors[0]["email"] = "different@example.org"
    elif field == "genre":
        journal.files[0]["genreId"] = 8
    elif field == "file":
        journal.files[0]["fileId"] = 999
    else:
        reviewed["review_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        final(ws, plan, journal, handler, reviewed["review_sha256"])
    assert journal.submit_count == 0


def test_unknown_upload_stops_without_duplicate_post(portal_case):
    ws, _, _, plan, _ = portal_case
    journal = Journal()
    journal.fail = "upload"
    with pytest.raises(OJSError):
        deliver(ws, plan, journal)
    assert portal.check(ws, plan)["uncertain_operations"] == ["upload:manuscript.pdf"]
    with pytest.raises(ValueError, match="uncertain"):
        deliver(ws, plan, journal)
    assert journal.calls.count(("POST", "/submissions/123/files")) == 1


def test_unknown_creation_can_attach_explicitly_inspected_draft(portal_case):
    ws, paper, _, plan, _ = portal_case
    journal = Journal()
    journal.fail = "create"
    with pytest.raises(OJSError):
        deliver(ws, plan, journal)
    with journal.client(plan) as client:
        with pytest.raises(ValueError, match="explicitly confirmed"):
            portal.reconcile(ws, plan, client, actor=paper.approved_by, remote_submission_id=123)
        report = portal.reconcile(ws, plan, client, actor=paper.approved_by, remote_submission_id=123, confirm=True)
    assert report["state"] == "DRAFT"
    journal.fail = None
    assert deliver(ws, plan, journal)["remote_submission_id"] == 123
    assert journal.calls.count(("POST", "/submissions")) == 1


@pytest.mark.parametrize("name", ["plan.json", "event", "orphan", "deleted-row"])
def test_preserved_portal_evidence_tampering_blocks_writes_and_slot_release(portal_case, name):
    ws, paper, submission, plan, handler = portal_case
    journal = Journal()
    deliver(ws, plan, journal)
    with httpx.Client(transport=httpx.MockTransport(handler)) as policy_client:
        publication.attest(ws, submission, author_values(), client=policy_client)
    root = ws.path(f"portals/{plan.id}")
    if name == "deleted-row":
        with ws._database() as db:
            db.execute("DELETE FROM records WHERE kind='portal_plan' AND id=?", (plan.id,))
    elif name == "orphan":
        (root / "uncommitted.json").write_text("{}", encoding="utf-8")
    else:
        path = root / "plan.json" if name == "plan.json" else next(root.glob("0001-*.json"))
        path.write_text("{}", encoding="utf-8")
    assert not portal.check(ws, plan)["passed"]
    with pytest.raises(ValueError):
        publication.cancel_attestation(ws, submission, paper.approved_by, "An invalid delivery record cannot release the slot.")


def test_cli_has_explicit_upload_and_final_submit_gates_without_credentials(portal_case, tmp_path):
    ws, _, submission, plan, _ = portal_case
    runner = CliRunner()
    base = ["--workspace", str(ws.root), "submission", "portal"]
    assert runner.invoke(cli.app, ["submission", "portal", "schema"]).exit_code == 0
    result = runner.invoke(cli.app, [*base, "upload", plan.id])
    assert result.exit_code == 1 and "--upload" in result.output
    values = tmp_path / "attestation.json"
    write_json(values, author_values())
    result = runner.invoke(cli.app, [*base, "submit", plan.id, str(values), "--review-sha256", "0" * 64])
    assert result.exit_code == 1 and "--submit" in result.output
    result = runner.invoke(cli.app, [*base, "check", plan.id])
    assert result.exit_code == 0 and json.loads(result.stdout)["passed"]


def test_module_mode_exposes_same_portal_commands_as_console_entrypoint():
    result = subprocess.run([sys.executable, "-m", "paper_factory.cli", "submission", "portal", "schema"],
        capture_output=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stderr
    assert "connection" in json.loads(result.stdout)["properties"]


@pytest.mark.parametrize("url,path", [
    ("https://other.example.org/journal/api/v1", "manuscript.pdf"),
    ("https://submit.example.org/other/api/v1", "manuscript.pdf"),
    ("https://submit.example.org/journal/api/v1", "author.json"),
    ("https://submit.example.org/journal/api/v1", "submission.zip"),
])
def test_wrong_target_or_administrative_upload_plan_is_rejected(prepared, mock_conversion, url, path):
    ws, _, submission, _, handler = compile_case(prepared,
        changes={"submission_url": "https://submit.example.org/journal/submission"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        submission_package.build(ws, submission, client=client)
    settings = portal.PortalSettings(connection=OJSSettings(api_url=url), draft=portal.OJSDraft(sectionId=2, locale="en"),
        uploads=[portal.Upload(path=path, genre_id=7)])
    with pytest.raises(ValueError):
        portal.prepare(ws, submission, settings)

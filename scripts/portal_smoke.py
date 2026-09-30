"""Real CLI/experiments/exports with a synthetic official-contract OJS provider.

Every journal, policy, author and provider receipt is a labelled local fixture.
MockTransport handles all provider calls; actual HTTP transport is disabled.
This script never uses an account, credential or real journal upload.
"""

import argparse
from contextlib import contextmanager
from email import policy as email_policy
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import httpx
from pypdf import PdfReader
from typer.testing import CliRunner

from paper_factory import cli, portal, publication, submission_package
from paper_factory.models import Paper, Submission, SubmissionState, now
from paper_factory.ojs import OJSClient
from paper_factory.workspace import digest_file, write_json
import phase3_smoke
from phase2_smoke import SYNTHETIC_AUTHOR, prepare_scientific_fixture, public_fixture_dns, settings, synthetic_policy
from phase3_smoke import author_values, make_candidate

TOKEN = "SYNTHETIC-LOCAL-TEST-TOKEN-NEVER-A-CREDENTIAL"
API = "https://submission.synthetic.example.org/journal/api/v1"


def portal_policy(venue_id):
    spec, body = synthetic_policy(venue_id)
    changes = {"submission_url": "https://submission.synthetic.example.org/journal/submission",
               "submission_system": "SYNTHETIC LOCAL OJS 3.5 FIXTURE ONLY",
               "review_model": "Double anonymous", "anonymization_required": True}
    for field, value in changes.items():
        spec["values"][field] = value
        spec["evidence"][field]["excerpt"] = f"Synthetic reviewed {field}: {json.dumps(value)}"
    return spec, body


class SyntheticJournal:
    def __init__(self, identifier, lost_final_response=False):
        self.identifier = identifier
        self.publication_id = identifier + 1000
        self.lost_final_response = lost_final_response
        self.final_count = 0
        self.calls = []
        self.uploads = []
        self.files = []
        self.submission = {"id": identifier, "currentPublicationId": self.publication_id,
                           "status": 1, "submissionProgress": "start", "locale": "en",
                           "dateSubmitted": None}
        self.publication = {"id": self.publication_id, "submissionId": identifier,
                            "sectionId": 2, "title": {}, "abstract": {}, "keywords": {}}
        self.authors = [{"id": identifier + 2000, "publicationId": self.publication_id,
                        "givenName": {"en": SYNTHETIC_AUTHOR["display_name"]},
                        "fullName": SYNTHETIC_AUTHOR["display_name"], "email": SYNTHETIC_AUTHOR["email"],
                        "userGroupId": 6, "seq": 0, "includeInBrowse": True,
                        "affiliations": [{"name": {"en": SYNTHETIC_AUTHOR["affiliation"]}}]}]

    def data(self):
        # sectionId is write-only on Submission; publication summaries own it.
        return {**self.submission, "publications": [{"id": self.publication_id,
            "submissionId": self.identifier, "sectionId": self.publication["sectionId"],
            "title": self.publication["title"], "status": 1}]}

    def handler(self, request):
        if request.url.host != "93.184.216.34" or request.headers["Host"] != "submission.synthetic.example.org":
            raise AssertionError("Unexpected synthetic OJS destination")
        if request.extensions["sni_hostname"] != "submission.synthetic.example.org" or request.headers["Authorization"] != "Bearer " + TOKEN:
            raise AssertionError("Synthetic transport lost hostname/credential binding")
        route = request.url.path.removeprefix("/journal/api/v1")
        self.calls.append({"method": request.method, "route": route})
        prefix = f"/submissions/{self.identifier}"
        publication_route = prefix + f"/publications/{self.publication_id}"
        body = json.loads(request.content) if request.headers.get("content-type", "").startswith("application/json") else None
        if request.method == "POST" and route == "/submissions":
            if body != {"sectionId": 2, "locale": "en"}:
                raise AssertionError("Unexpected synthetic draft payload")
            return httpx.Response(200, json=self.data())
        if request.method == "GET" and route == prefix:
            return httpx.Response(200, json=self.data())
        if route == publication_route:
            if request.method == "PUT":
                self.publication.update(body)
            return httpx.Response(200, json={**self.publication, "authors": self.authors})
        if request.method == "GET" and route == publication_route + "/contributors":
            return httpx.Response(200, json={"itemsMax": len(self.authors), "items": self.authors})
        if route == prefix + "/files":
            if request.method == "GET":
                return httpx.Response(200, json={"itemsMax": len(self.files), "items": self.files})
            message = BytesParser(policy=email_policy.default).parsebytes(
                ("Content-Type: " + request.headers["content-type"] + "\r\nMIME-Version: 1.0\r\n\r\n").encode() + request.read())
            parts = {part.get_param("name", header="content-disposition"): part for part in message.iter_parts()}
            content = parts["file"].get_payload(decode=True)
            if parts["file"].get_filename() != "manuscript.pdf" or parts["fileStage"].get_payload(decode=True) != b"2" or parts["genreId"].get_payload(decode=True) != b"7":
                raise AssertionError("Unexpected multipart file role")
            self.uploads.append(hashlib.sha256(content).hexdigest())
            item = {"id": self.identifier + 3000, "fileId": self.identifier + 4000,
                    "submissionId": self.identifier, "genreId": 7, "fileStage": 2,
                    "name": {"en": "manuscript.pdf"}}
            self.files.append(item)
            return httpx.Response(200, json=item)
        if request.method == "PUT" and route == prefix + "/submit":
            if body == {"_validateOnly": True}:
                return httpx.Response(200, json=[])
            if body != {"confirmCopyright": True}:
                raise AssertionError("Unexpected final-submit payload")
            self.final_count += 1
            self.submission.update(submissionProgress="", dateSubmitted=now()[:19].replace("T", " "))
            if self.lost_final_response:
                raise httpx.ReadTimeout("SYNTHETIC provider accepted final Submit; response intentionally lost")
            return httpx.Response(200, json=self.data())
        raise AssertionError((request.method, route))


def run_case(root, pandoc, *, lost_final_response):
    root.mkdir()
    ws, paper, run, claims = prepare_scientific_fixture(root, pandoc)
    candidate, policy_handler = make_candidate(root, ws, paper, settings(root), pandoc)
    freeze = paper.freeze_digest
    archive = ws.path(f"submissions/{candidate.id}/package/submission.zip")
    archive_digest = digest_file(archive)
    manuscript_pdf = ws.path(f"submissions/{candidate.id}/package/manuscript.pdf")
    pdf = PdfReader(manuscript_pdf)
    pdf_text = " ".join(page.extract_text() or "" for page in pdf.pages)
    if not pdf.pages or "Measured corpus byte length" not in pdf_text or SYNTHETIC_AUTHOR["email"] in pdf_text:
        raise RuntimeError("Actual blinded PDF lacks measurements or exposes synthetic identity")
    journal = SyntheticJournal(102 if lost_final_response else 101, lost_final_response)
    runner = CliRunner()
    base = ["--workspace", str(ws.root), "submission", "portal"]
    executions = []

    def invoke(arguments, *, expected=0):
        result = runner.invoke(cli.app, base + arguments)
        executions.append({"arguments": list(arguments), "exit_code": result.exit_code, "output": result.output})
        if result.exit_code != expected:
            raise RuntimeError(f"Synthetic CLI failed {arguments}: {result.output}") from result.exception
        return json.loads(result.stdout) if expected == 0 else result.output

    @contextmanager
    def client_from_fixture(plan):
        with httpx.Client(transport=httpx.MockTransport(journal.handler), trust_env=False) as transport:
            with OJSClient(plan.settings.connection, TOKEN, client=transport) as client:
                yield client

    original_submit = portal.submit
    def submit_with_fixture_policy(*args, **kwargs):
        with httpx.Client(transport=httpx.MockTransport(policy_handler), trust_env=False) as policy_client:
            return original_submit(*args, **kwargs, policy_client=policy_client)

    settings_path = root / "SYNTHETIC-portal-settings.json"
    attestation_path = root / "SYNTHETIC-ATTESTATION-LOCAL-TEST-ONLY.json"
    write_json(attestation_path, author_values(ws, candidate))
    with patch.object(portal, "client_from_environment", client_from_fixture), patch.object(portal, "submit", submit_with_fixture_policy):
        invoke(["settings", candidate.id, "--api-url", API, "--section", "2", "--locale", "en", "--genre", "7", "--output", str(settings_path)])
        plan_id = invoke(["prepare", candidate.id, str(settings_path)])["plan"]["id"]
        invoke(["upload", plan_id], expected=1)
        if journal.calls:
            raise RuntimeError("CLI unapproved upload reached synthetic provider")
        uploaded = invoke(["upload", plan_id, "--upload"])
        reviewed = invoke(["inspect", plan_id])
        abstract = journal.publication["abstract"]["en"]
        if "**" in abstract or not all(str(value) in abstract for value in (459, 215)):
            raise RuntimeError("Synthetic OJS HTML abstract lost verified numeric prose or retains Markdown decoration")
        if uploaded["review_sha256"] != reviewed["review_sha256"]:
            raise RuntimeError("Unchanged official-contract inspection digest differs")
        submit_args = ["submit", plan_id, str(attestation_path), "--review-sha256", reviewed["review_sha256"]]
        invoke(submit_args, expected=1)
        submit_args += ["--approve", "--submit", "--confirm-copyright"]
        if lost_final_response:
            error = invoke(submit_args, expected=1)
            pending = invoke(["check", plan_id])
            if pending["uncertain_operations"] != ["submit"] or ws.get("submission", candidate.id, Submission).state != SubmissionState.AUTHOR_ATTESTED:
                raise RuntimeError("Unknown final Submit did not preserve pending intent and reservation")
            if TOKEN in error:
                raise RuntimeError("Synthetic credential appeared in error")
            try:
                publication.cancel_attestation(ws, candidate, SYNTHETIC_AUTHOR["display_name"], "SYNTHETIC attempt to cancel unknown final submission")
            except ValueError:
                pass
            else:
                raise RuntimeError("Unknown final Submit incorrectly released its Study slot")
            invoke(submit_args, expected=1)
        else:
            confirmed = invoke(submit_args)
            if confirmed["state"] != "SUBMITTED":
                raise RuntimeError("Synthetic final response was not recorded")
        reconciled = invoke(["reconcile", plan_id, "--actor", SYNTHETIC_AUTHOR["display_name"]])
        audit = invoke(["check", plan_id])
    if reconciled["state"] != "SUBMITTED" or not audit["submission_confirmed"] or audit["uncertain_operations"] or journal.final_count != 1:
        raise RuntimeError("Read-only reconciliation repeated final Submit or failed confirmation")
    if len(journal.uploads) != 1 or journal.uploads[0] != digest_file(manuscript_pdf):
        raise RuntimeError("Synthetic multipart bytes differ from real approved PDF")
    if ws.get("paper", paper.id, Paper).freeze_digest != freeze or digest_file(archive) != archive_digest:
        raise RuntimeError("Portal workflow modified scientific freeze or submission archive")
    package_report = submission_package.verify(ws, candidate, fresh=False)
    history = publication.check(ws, candidate)
    if not package_report["passed"] or not package_report["ready"] or not history["passed"]:
        raise RuntimeError("Final scientific package or publication audit failed")
    if len(publication.active_for_study(ws, paper.study_id)) != 1:
        raise RuntimeError("Synthetic submission did not retain one peer-review slot")
    if any(TOKEN in path.read_text(encoding="utf-8") for path in ws.path(f"portals/{plan_id}").iterdir()):
        raise RuntimeError("Synthetic credential was persisted in portal evidence")
    return {"workspace": str(ws.root), "plan_id": plan_id, "lost_final_response": lost_final_response,
            "actual_experiment": {"id": run.id, "status": run.status, "metrics": run.metrics},
            "actual_claim_ids": [claim.id for claim in claims], "real_pdf": str(manuscript_pdf), "pdf_pages": len(pdf.pages),
            "uploaded_pdf_sha256": journal.uploads[0], "immutable_freeze": freeze, "immutable_archive": archive_digest,
            "synthetic_provider_metadata": journal.publication,
            "synthetic_final_requests": journal.final_count, "synthetic_provider_calls": journal.calls,
            "synthetic_publication_state": history["state"], "portal_audit": audit,
            "unknown_final_blocks_cancel_and_retry": lost_final_response, "cli_executions": executions,
            "external_submission_performed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Empty external artifact directory")
    parser.add_argument("--pandoc", required=True, help="Existing actual Pandoc executable")
    args = parser.parse_args()
    root = args.root.resolve() if args.root else Path(tempfile.mkdtemp(prefix="paperfactory-portal-smoke-"))
    if root.exists() and any(root.iterdir()):
        raise ValueError("Smoke output root must be empty")
    root.mkdir(parents=True, exist_ok=True)
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith(("PF_AUTHOR_", "PF_OJS_"))}
    environment["PF_HOME"] = str(root / "home")
    def reject_real_network(*args, **kwargs):
        raise AssertionError("Actual HTTP transport is disabled in the synthetic portal smoke")
    with patch.dict(os.environ, environment, clear=True), patch("socket.getaddrinfo", public_fixture_dns), \
            patch.object(httpx.HTTPTransport, "handle_request", reject_real_network), \
            patch.object(phase3_smoke, "synthetic_policy", portal_policy):
        normal = run_case(root / "confirmed-fixture", args.pandoc, lost_final_response=False)
        ambiguous = run_case(root / "unknown-final-fixture", args.pandoc, lost_final_response=True)
    summary = {"synthetic_provider_policies_authors_and_receipts_only": True,
               "no_real_credentials_accounts_or_journal_calls": True, "external_submission_performed": False,
               "normal": normal, "unknown_final": ambiguous}
    result_path = root / "SYNTHETIC-portal-smoke-result.json"
    write_json(result_path, summary)
    print(json.dumps({"result": str(result_path), "actual_metrics": normal["actual_experiment"]["metrics"],
                      "real_pdf_pages": [normal["pdf_pages"], ambiguous["pdf_pages"]],
                      "synthetic_final_requests": [normal["synthetic_final_requests"], ambiguous["synthetic_final_requests"]],
                      "unknown_final_reconciled_without_retry": True, "external_submission_performed": False},
                     ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

"""Actual local execution/exports with synthetic publication confirmations only.

No account, upload, real author attestation or journal/preprint submission occurs.
The scientific measurement and Pandoc/Typst exports use the real implementation;
all directory/policy responses and external receipts are conspicuous fixtures.
"""

import argparse
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import httpx

from paper_factory import preprints, publication, submission_package, venue_compiler, venue_policy, venues
from paper_factory.models import Paper, Submission, now
from paper_factory.workspace import write_json
from phase2_smoke import (SYNTHETIC_AUTHOR, mock_directory, prepare_scientific_fixture,
                          public_fixture_dns, settings, synthetic_policy)


def make_candidate(root, ws, paper, compiler_settings, pandoc, second=False):
    def directory(request):
        response = mock_directory(request)
        data = response.json()
        if second:
            data["results"][0].update(id="https://openalex.org/S124", display_name="Synthetic Retarget Journal")
        return httpx.Response(200, json=data)

    with httpx.Client(transport=httpx.MockTransport(directory)) as client:
        venue = venues.discover(ws, "synthetic lifecycle smoke", 1, client=client)[0]
    spec, _ = synthetic_policy(venue.id)
    if second:
        spec["evidence"]["indexing"]["excerpt"] = "Synthetic Retarget Journal ISSN 1234-5678 Science Citation Index Expanded SCIE"
    body = "<h1>SYNTHETIC JOURNAL POLICY FIXTURE ONLY</h1>" + "".join(
        f"<p>{item['excerpt']}</p>" for item in spec["evidence"].values())
    path = root / f"{venue.id}-policy.json"
    write_json(path, spec)

    def handler(request):
        if request.url.host != "93.184.216.34" or request.headers["Host"] not in {"synthetic.example.org", "mjl.clarivate.com"}:
            raise AssertionError("Unexpected synthetic policy request")
        return httpx.Response(200, text=body, headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        policy = venue_policy.verify_policy(ws, venue, path, client=client)
        candidate = venue_compiler.select(ws, paper, venue, policy)
        compiled, _ = venue_compiler.compile_submission(ws, candidate, compiler_settings, pandoc=pandoc, client=client)
        package, _ = submission_package.build(ws, compiled, client=client)
    if not package.ready:
        raise RuntimeError(f"Synthetic policy failed readiness: {package.errors}")
    return ws.get("submission", candidate.id, Submission), handler


def author_values(ws, candidate, posted=None):
    values = dict(actor=SYNTHETIC_AUTHOR["display_name"], all_authors_approved=True,
                  not_under_review_elsewhere=True, coi_correct=True, funding_correct=True,
                  ai_disclosure_correct=True, author_information_correct=True)
    if posted:
        policy = ws.get("policy", candidate.policy_id, venue_policy.VenuePolicy)
        values["preprint_review"] = {"decision": "allowed", "preprint_ids": [posted.id],
                                    "evidence": policy.evidence["preprint_policy"].model_dump(mode="json")}
    return publication.AttestationInput.model_validate(values)


def attest(ws, candidate, handler, posted=None):
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        return publication.attest(ws, candidate, author_values(ws, candidate, posted), client=client)


def receipt(root, ws, candidate, state):
    evidence = root / f"{candidate.id}-{state}.txt"
    evidence.write_text(f"SYNTHETIC INTEGRATION TEST RECEIPT ONLY.\nSynthetic system records {state} for {candidate.id}.\n", encoding="utf-8")
    values = publication.ReceiptInput(target_state=state, external_id=f"SYNTHETIC-{candidate.id}",
        external_url=f"https://submission.synthetic.example.org/manuscript/{candidate.id}",
        occurred_at=now(), verified_by=SYNTHETIC_AUTHOR["display_name"],
        note="Synthetic test reviewer confirms the synthetic receipt; this is not an actual journal event.")
    return publication.record_receipt(ws, candidate, values, evidence)


def must_block(action, reason):
    try:
        action()
    except ValueError as error:
        if reason not in str(error):
            raise RuntimeError(f"Blocked for an unexpected reason: {error}") from error
        return str(error)
    raise RuntimeError("The publication guard did not block a competing action")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Empty external output directory")
    parser.add_argument("--pandoc", help="Installed Pandoc executable")
    args = parser.parse_args()
    root = args.root.resolve() if args.root else Path(tempfile.mkdtemp(prefix="paperfactory-phase3-smoke-"))
    if root.exists() and any(root.iterdir()):
        raise ValueError("Smoke output root must be empty")
    root.mkdir(parents=True, exist_ok=True)
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("PF_AUTHOR_")}
    environment["PF_HOME"] = str(root / "home")
    with patch.dict(os.environ, environment, clear=True), patch("socket.getaddrinfo", public_fixture_dns):
        ws, paper, run, claims = prepare_scientific_fixture(root, args.pandoc)
        compiler_settings = settings(root)
        first, first_handler = make_candidate(root, ws, paper, compiler_settings, args.pandoc)
        second, second_handler = make_candidate(root, ws, paper, compiler_settings, args.pandoc, second=True)
        attest(ws, first, first_handler)
        initial_block = must_block(lambda: attest(ws, second, second_handler), "active peer-reviewed")
        receipt(root, ws, first, "SUBMITTED")
        receipt(root, ws, first, "UNDER_REVIEW")

        policy = ws.get("policy", first.policy_id, venue_policy.VenuePolicy)
        preprint_settings = root / "synthetic-preprint-settings.json"
        write_json(preprint_settings, {"paper_id": paper.id, "policy_id": policy.id,
            "server": "Synthetic Test Preprint Server", "server_url": "https://preprints.synthetic.example.org/",
            "license": "CC-BY-4.0; SYNTHETIC FIXTURE REVIEW ONLY", "reviewed_by": SYNTHETIC_AUTHOR["display_name"],
            "decision": "allowed", "evidence": policy.evidence["preprint_policy"].model_dump(mode="json"),
            "author_approval": True, "authorized_to_post": True, "policy_interpretation_confirmed": True})
        with httpx.Client(transport=httpx.MockTransport(first_handler)) as client:
            prepared, preprint_root = preprints.prepare(ws, preprint_settings, pandoc=args.pandoc, client=client)
        posting = root / "synthetic-posting.json"
        posting_evidence = root / "synthetic-posting-confirmation.txt"
        posting_evidence.write_text("SYNTHETIC PREPRINT POSTING RECEIPT ONLY: synthetic:phase3-v1.\n", encoding="utf-8")
        write_json(posting, {"paper_id": paper.id, "preparation_id": prepared.id,
            "remote_identifier": "synthetic:phase3-v1", "source_url": "https://preprints.synthetic.example.org/phase3-v1",
            "posted_at": now(), "recorded_by": SYNTHETIC_AUTHOR["display_name"], "content_digest": paper.freeze_digest,
            "statement": "Synthetic test-only observation; no external preprint was actually posted."})
        posted, _ = preprints.record_posting(ws, posting, posting_evidence, confirmed=True)
        preprint_report = preprints.check(ws, posted)
        if not preprint_report["valid"] or not preprint_report["posting_recorded"] or preprint_report["peer_reviewed"]:
            raise RuntimeError(f"Separate preprint audit failed: {preprint_report}")
        if len(publication.active_for_study(ws, paper.study_id)) != 1:
            raise RuntimeError("Preprint posting changed the peer-review slot")

        receipt(root, ws, first, "WITHDRAWAL_REQUESTED")
        withdrawal_block = must_block(lambda: attest(ws, second, second_handler, posted), "active peer-reviewed")
        receipt(root, ws, first, "WITHDRAWN_CONFIRMED")
        attest(ws, second, second_handler, posted)
        receipt(root, ws, second, "SUBMITTED")
        final_event = receipt(root, ws, second, "REJECTED")
        if publication.active_for_study(ws, paper.study_id):
            raise RuntimeError("Confirmed rejection did not release the slot")

        preserved_receipt = ws.path(f"publication/{second.id}/{final_event.id}/evidence.bin")
        original = preserved_receipt.read_bytes()
        try:
            preserved_receipt.write_bytes(b"synthetic tamper test")
            must_block(lambda: publication.active_for_study(ws, paper.study_id), "changed")
            tamper_detected = True
        finally:
            preserved_receipt.write_bytes(original)
        histories = [publication.check(ws, candidate) for candidate in (first, second)]
        packages = [submission_package.verify(ws, candidate) for candidate in (first, second)]
        if not all(report["passed"] for report in histories) or not all(report["ready"] for report in packages):
            raise RuntimeError("Restored historical journal/package audit failed")
        if ws.get("paper", paper.id, Paper).freeze_digest != paper.freeze_digest:
            raise RuntimeError("Publication workflow modified the approved scientific content")
        summary = {"workspace": str(ws.root), "synthetic_policies_authors_and_receipts_only": True,
            "actual_experiment": {"id": run.id, "status": run.status, "metrics": run.metrics},
            "claim_ids": [claim.id for claim in claims], "freeze_digest": paper.freeze_digest,
            "competing_attestation_block": initial_block, "withdrawal_request_block": withdrawal_block,
            "retarget_after_confirmed_withdrawal": True, "confirmed_rejection_releases_slot": True,
            "receipt_tamper_detected": tamper_detected, "history": histories,
            "preprint": {"record": posted.model_dump(mode="json"), "audit": preprint_report,
                         "directory": str(preprint_root), "pdf": str(preprint_root / "manuscript.pdf")},
            "packages": packages, "external_submission_performed": False, "external_preprint_upload_performed": False}
    write_json(root / "phase3-smoke-result.json", summary)
    print(json.dumps({"result": str(root / "phase3-smoke-result.json"), "workspace": str(ws.root),
        "metrics": run.metrics, "states": [report["state"] for report in histories],
        "retarget_after_confirmed_withdrawal": True, "preprint_separate": True,
        "receipt_tamper_detected": tamper_detected, "external_submission_performed": False},
        indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

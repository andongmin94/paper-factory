"""Real experiments and PDF exports with conspicuous synthetic review fixtures.

The script performs no external account action, upload or publisher submission.
Policy captures and journal receipts are synthetic; the compression experiments,
scientific freezes, reviewer bindings and Pandoc/Typst exports are actual code.
"""

import argparse
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import httpx
from pypdf import PdfReader

from paper_factory import evidence, experiments, integrity, publication, revisions, revision_submission, submission_package
from paper_factory.manuscript import Block
from paper_factory.models import ExperimentManifest, Paper, Submission, now
from paper_factory.workspace import digest_file, write_json
from phase2_smoke import SYNTHETIC_AUTHOR, prepare_scientific_fixture, public_fixture_dns, settings, synthetic_policy
from phase3_smoke import author_values, attest, make_candidate, must_block, receipt


def blind_synthetic_policy(venue_id):
    spec, body = synthetic_policy(venue_id)
    for field, value in {"review_model": "Double anonymous", "anonymization_required": True}.items():
        spec["values"][field] = value
        spec["evidence"][field]["excerpt"] = f"Synthetic reviewed {field}: {json.dumps(value)}"
    return spec, body  # make_candidate derives its synthetic HTML from these excerpts.


def run_review(root, ws, original, first_run, first_claims, pandoc):
    excerpts = {
        "method": "Please clarify the lossless compression method and retained inputs.",
        "repeat": "Please repeat the local compression experiment and report the measured results.",
        "scope": "Please generalize the observations to other corpora.",
    }
    report_path = root / "SYNTHETIC-referee-report.txt"
    # Native Windows report input also exercises canonical CRLF extraction.
    report_path.write_bytes(("SYNTHETIC REFEREE REPORT ONLY; NO REAL JOURNAL REVIEW.\r\n"
        + "\r\n".join(excerpts.values()) + "\r\n").encode("utf-8"))
    spec = revisions.ReviewSpec(reviewed_by=SYNTHETIC_AUTHOR["display_name"], comments=[
        revisions.ReviewComment(id="comment-method", excerpt=excerpts["method"], sections=["Method"]),
        revisions.ReviewComment(id="comment-repeat", excerpt=excerpts["repeat"], sections=["Abstract", "Results"],
            claim_ids=[claim.id for claim in first_claims], experiment_ids=[first_run.experiment_id]),
        revisions.ReviewComment(id="comment-scope", excerpt=excerpts["scope"], sections=["Discussion", "Limitations"]),
    ])
    spec_path = root / "SYNTHETIC-review-comments.json"
    write_json(spec_path, spec)
    revision, _ = revisions.import_review(ws, original, spec_path, report_path, confirmed=True)
    revisions.draft(ws, revision, pandoc=pandoc, pdf=True)

    manifest = ws.get("manifest", first_run.experiment_id, ExperimentManifest).model_copy(deep=True)
    manifest.id = "smoke-corpus-compression-review-repeat"
    manifest.seed = 7
    for metric in manifest.metrics:
        metric.description = "Repeated-run " + metric.description.lower()
    manifest_path = root / "review-repeat-manifest.json"
    write_json(manifest_path, manifest)
    new_run = experiments.run_experiment(ws, experiments.register_manifest(ws, manifest_path))
    if new_run.status != "SUCCEEDED":
        raise RuntimeError(f"Real post-review repetition failed: {new_run.error}")
    new_claims = evidence.claims_for_run(ws, new_run)

    plan = revisions.plan_template(ws, revision)
    responses = {item.comment_id: item for item in plan.responses}
    method = responses["comment-method"]
    method.disposition = "accept"
    method.reply = "The Method now explains the lossless compression protocol and the retained input corpus."
    method.edits = [revisions.SectionEdit(section="Method", blocks=[Block(kind="prose",
        text="The supplied analysis script reads the retained corpus and applies the registered lossless compression protocol. The registered commands execute in isolated working copies and preserve the original input snapshot and raw results.")])]

    repeated = responses["comment-repeat"]
    repeated.disposition = "accept"
    repeated.reply = "The registered compression protocol was executed again after the referee request. The Abstract and Results now report the linked repeated-run measurements."
    repeated.additional_experiments_required = True
    repeated.experiment_ids = [new_run.experiment_id]
    repeated.run_ids = [new_run.id]
    repeated.claim_ids = [claim.id for claim in new_claims]
    repeated.edits = [
        revisions.SectionEdit(section="Abstract", blocks=[Block(kind="prose",
            text="We document a repeated execution of the supplied descriptive compression protocol. The observations below are limited to the included corpus and the registered local procedure."),
            *[Block(kind="claim", ref=claim.id) for claim in new_claims]]),
        revisions.SectionEdit(section="Results", blocks=[Block(kind="prose",
            text="The repeated local experiment retained the input snapshot and raw measurement artifacts. The measured outcomes follow."),
            *[Block(kind="claim", ref=claim.id) for claim in new_claims]]),
    ]

    scope = responses["comment-scope"]
    scope.disposition = "disagree"
    scope.reply = "We retain the limited scope of the supplied corpus and do not add a generalization claim."
    scope.justification = "The current study contains the supplied corpus and its registered procedure. Evidence from independent corpora would be required to support broader inference; the Discussion and Limitations preserve this restriction."
    plan_path = root / "SYNTHETIC-response-plan.json"
    write_json(plan_path, plan)
    child, _ = revisions.apply_plan(ws, revision, plan_path, pandoc=pandoc, pdf=True)
    review_check = revisions.check(ws, revision)
    if not review_check["passed"]:
        raise RuntimeError(f"Review verification failed: {review_check['errors']}")
    response, response_root = revisions.build_response(ws, revision, plan_path, pandoc=pandoc)
    if not response.ready:
        raise RuntimeError(f"Response remains incomplete: {response.errors}")
    scientific = integrity.check(ws, child)
    if not scientific["passed"]:
        raise RuntimeError(f"Revised scientific integrity failed: {scientific['errors']}")
    integrity.approve(ws, child, approved=True,
        assessment="SYNTHETIC WORKFLOW REVIEW ONLY. The genuine post-review compression repetition and source-linked response were checked. The corpus remains limited, the empty synthetic literature search establishes no novelty, and this fixture approval does not authorize an external submission.",
        author_values=SYNTHETIC_AUTHOR)
    child = ws.get("paper", child.id, Paper)
    response_check = revisions.verify_response(ws, response, require_approved=True, require_active=True)
    if not response_check["ready"]:
        raise RuntimeError(f"Approved response binding failed: {response_check['errors']}")
    return revision, child, response, response_root, new_run, new_claims


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Empty external output directory")
    parser.add_argument("--pandoc", required=True, help="Existing installed Pandoc executable")
    args = parser.parse_args()
    root = args.root.resolve() if args.root else Path(tempfile.mkdtemp(prefix="paperfactory-phase4-smoke-"))
    if root.exists() and any(root.iterdir()):
        raise ValueError("Smoke output root must be empty")
    root.mkdir(parents=True, exist_ok=True)
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("PF_AUTHOR_")}
    environment["PF_HOME"] = str(root / "home")
    with patch.dict(os.environ, environment, clear=True), patch("socket.getaddrinfo", public_fixture_dns), \
            patch("phase3_smoke.synthetic_policy", blind_synthetic_policy):
        ws, base, first_run, first_claims = prepare_scientific_fixture(root, args.pandoc)
        compiler_settings = settings(root)
        original, handler = make_candidate(root, ws, base, compiler_settings, args.pandoc)
        competitor, competitor_handler = make_candidate(root, ws, base, compiler_settings, args.pandoc, second=True)
        old_freeze = base.freeze_digest
        old_manifest = original.package_digest
        old_archive = digest_file(ws.path(f"submissions/{original.id}/package/submission.zip"))
        attest(ws, original, handler)
        for state in ("SUBMITTED", "UNDER_REVIEW", "REVISION"):
            receipt(root, ws, original, state)
        competitor_block = must_block(lambda: attest(ws, competitor, competitor_handler), "active peer-reviewed")
        revision, child, response, response_root, new_run, new_claims = run_review(
            root, ws, original, first_run, first_claims, args.pandoc)
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            delivery, delivery_root = revision_submission.prepare(ws, revision, compiler_settings,
                response=response, pandoc=args.pandoc, client=client)
            revision_submission.attest(ws, delivery, author_values(ws, original), client=client)
        evidence_path = root / "SYNTHETIC-revision-confirmation.txt"
        evidence_path.write_text("SYNTHETIC REVISION CONFIRMATION ONLY. No actual publisher action occurred.\n", encoding="utf-8")
        revised_receipt = publication.ReceiptInput(target_state="UNDER_REVIEW", external_id=delivery.external_id,
            external_url=f"https://submission.synthetic.example.org/manuscript/{original.id}",
            occurred_at=now(), verified_by=SYNTHETIC_AUTHOR["display_name"],
            note="Synthetic fixture review records the revised package under the original synthetic manuscript identifier; no external resubmission took place.")
        event = revision_submission.record(ws, delivery, revised_receipt, evidence_path)

        reviewer_root = delivery_root / "reviewer-response"
        reviewer_letter = reviewer_root / "letter.md"
        roles = json.loads((delivery_root / "delivery-readme.json").read_bytes())
        reviewer_text = reviewer_letter.read_text(encoding="utf-8")
        reviewer_pdf = PdfReader(reviewer_root / "letter.pdf")
        reviewer_pdf_text = "\n".join(page.extract_text() or "" for page in reviewer_pdf.pages)
        if (not roles["anonymized"] or not roles["reviewer_response_files"]
                or "response/letter.md" not in roles["administrative_response_files"]
                or any(value.casefold() in (reviewer_text + reviewer_pdf_text).casefold()
                    for value in SYNTHETIC_AUTHOR.values())):
            raise RuntimeError("The blinded reviewer derivative exposes author identity or incorrect file roles")

        letter_path = response_root / "letter.md"
        letter_bytes = letter_path.read_bytes()
        try:
            letter_path.write_bytes(letter_bytes + b"\nSYNTHETIC TAMPER CHECK\n")
            if revisions.verify_response(ws, response)["ready"]:
                raise RuntimeError("Response letter modification was not detected")
            must_block(lambda: publication.active_for_study(ws, base.study_id), "changed")
        finally:
            letter_path.write_bytes(letter_bytes)
        reviewer_bytes = reviewer_letter.read_bytes()
        try:
            reviewer_letter.write_bytes(reviewer_bytes + b"\nSYNTHETIC REVIEWER DERIVATIVE TAMPER CHECK\n")
            if revision_submission.check(ws, delivery)["passed"]:
                raise RuntimeError("Reviewer derivative modification was not detected")
        finally:
            reviewer_letter.write_bytes(reviewer_bytes)
        receipt_path = ws.path(f"publication/{original.id}/{event.id}/evidence.bin")
        receipt_bytes = receipt_path.read_bytes()
        try:
            receipt_path.write_bytes(b"SYNTHETIC TAMPER CHECK")
            must_block(lambda: publication.active_for_study(ws, base.study_id), "changed")
        finally:
            receipt_path.write_bytes(receipt_bytes)

        journal_check = publication.check(ws, original)
        delivery_check = revision_submission.check(ws, delivery)
        old_package_check = submission_package.verify(ws, original)
        if not journal_check["passed"] or not delivery_check["passed"] or not old_package_check["ready"]:
            raise RuntimeError(f"Restored publication/delivery/package verification failed: {journal_check}, {delivery_check}, {old_package_check}")
        current_original = ws.get("submission", original.id, Submission)
        if (current_original.state != "UNDER_REVIEW" or current_original.paper_id != base.id
                or current_original.package_digest != old_manifest or ws.get("paper", base.id, Paper).freeze_digest != old_freeze
                or digest_file(ws.path(f"submissions/{original.id}/package/submission.zip")) != old_archive
                or len(publication.active_for_study(ws, base.study_id)) != 1):
            raise RuntimeError("Same-journal revision altered the original freeze/package or active slot")
        pdfs = {
            "original": ws.path(f"submissions/{original.id}/compiled/manuscript.pdf"),
            "revised": ws.path(f"submissions/{delivery.candidate_id}/compiled/manuscript.pdf"),
            "response": response_root / "letter.pdf",
            "reviewer_response": reviewer_root / "letter.pdf",
        }
        pdf_summary = {name: {"path": str(path), "pages": len(PdfReader(path).pages), "sha256": digest_file(path)}
            for name, path in pdfs.items()}
        if any(not item["pages"] for item in pdf_summary.values()):
            raise RuntimeError("An actual exported PDF has no pages")
        summary = {"workspace": str(ws.root), "synthetic_policies_authors_and_receipts_only": True,
            "actual_experiments": [{"id": run.id, "status": run.status, "started_at": run.started_at,
                "ended_at": run.ended_at, "metrics": run.metrics} for run in (first_run, new_run)],
            "post_review_run_ids": [new_run.id], "post_review_claim_ids": [claim.id for claim in new_claims],
            "revision_id": revision.id, "revised_paper_id": child.id, "delivery_id": delivery.id,
            "external_id": delivery.external_id, "original_freeze_and_package_preserved": True,
            "same_active_slot_preserved": True, "competing_attestation_block": competitor_block,
            "review_dispositions": {"method": "accept", "repeat": "accept", "scope": "disagree"},
            "response_letter_tamper_detected": True, "receipt_tamper_detected": True,
            "blind_reviewer_response_verified": True, "reviewer_response_tamper_detected": True,
            "publication": journal_check, "delivery": delivery_check, "pdfs": pdf_summary,
            "delivery_directory": str(delivery_root), "external_submission_performed": False}
    write_json(root / "phase4-smoke-result.json", summary)
    print(json.dumps({"result": str(root / "phase4-smoke-result.json"), "workspace": str(ws.root),
        "actual_experiments": summary["actual_experiments"], "state": journal_check["state"],
        "same_active_slot_preserved": True, "original_freeze_and_package_preserved": True,
        "response_letter_tamper_detected": True, "receipt_tamper_detected": True,
        "blind_reviewer_response_verified": True, "reviewer_response_tamper_detected": True,
        "pdfs": pdf_summary, "external_submission_performed": False}, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

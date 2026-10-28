"""Reconcile existing exact-file preparation records without rendering or submitting.

The report checks supplied records and current bytes. It does not authenticate a
person, conduct peer review, remeasure Word, or upload files.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from _publication_files import digest_file
from _publication_templates import official_template
from research_workspace import _absolute, _manifest, _new_folder, _relative, _write
from submission_support import DECLARATIONS, VENUES, _declaration_status


def _confirmation(statement, record, files):
    # Reuse the same exact statement/file scope rules as declaration records.
    return _declaration_status({"author_approval": statement}, {"author_approval": record}, files)["author_approval"]


def check(root: Path, record_path: Path, output_dir: Path) -> dict:
    root, record_path = _absolute(root), _absolute(record_path)
    record_bytes = record_path.read_bytes()
    if len(record_bytes) > 2 * 1024 * 1024:
        raise ValueError("Final preparation record must be at most 2 MiB")
    supplied = json.loads(record_bytes.decode("utf-8-sig"))
    required = {"venue_id", "manuscript", "docx", "pdf", "format_report", "visual_review", "bundle_report", "scientific_review", "pages", "confirmations"}
    if not isinstance(supplied, dict) or set(supplied) != required or supplied["venue_id"] not in VENUES:
        raise ValueError("Record requires venue_id, manuscript, docx, pdf, format_report, visual_review, bundle_report, scientific_review, pages and confirmations")
    if (not isinstance(supplied["pages"], list) or not supplied["pages"] or any(not isinstance(name, str) for name in supplied["pages"]) or
            len(set(supplied["pages"])) != len(supplied["pages"])):
        raise ValueError("pages must explicitly list distinct ordered page-image paths")
    confirmations = supplied["confirmations"]
    if not isinstance(confirmations, dict) or set(confirmations) - {"author_identity", "author_photo", "current_guidance", "required_files"}:
        raise ValueError("Unsupported final preparation confirmation")
    snapshots, checks = {record_path: hashlib.sha256(record_bytes).hexdigest()}, []

    def read(path, *, document=False):
        if path is None:
            return None
        if path.is_file():
            data = path.read_bytes()
            snapshots[path] = hashlib.sha256(data).hexdigest()
            if document:
                if len(data) > 2 * 1024 * 1024:
                    raise ValueError("A supplied preparation report must be at most 2 MiB")
                value = json.loads(data.decode("utf-8-sig"))
                if not isinstance(value, dict):
                    raise ValueError("A supplied preparation report must be a JSON object")
                return value
            return data
        snapshots[path] = None
        return None

    def selected(name, *, document=False):
        raw = supplied[name]
        return read(_relative(root, raw), document=document) if raw is not None else None

    def item(identifier, passed, reason):
        checks.append({"id": identifier, "status": "passed" if passed else "pending", "reason": reason})

    data = {name: selected(name) for name in ("manuscript", "docx", "pdf")}
    hashes = {name: hashlib.sha256(value).hexdigest() if value is not None else None for name, value in data.items()}
    native = selected("format_report", document=True) or {}
    binding = native.get("binding", {})
    if (not isinstance(binding, dict) or not isinstance(native.get("items", []), list) or
            any(not isinstance(row, dict) for row in native.get("items", [])) or
            not isinstance(native.get("metrics", {}), dict)):
        raise ValueError("Format report requires binding and metrics objects and an items list of objects")
    _, template = official_template(supplied["venue_id"])
    expected = {"markdown_sha256": hashes["manuscript"], "docx_sha256": hashes["docx"], "pdf_sha256": hashes["pdf"],
                "template_sha256": template["sha256"], "template_provenance_sha256": template["provenance_sha256"]}
    native_items = [row for row in native.get("items", []) if row.get("stage") in {"manuscript", "native"}]
    native_ids = {row.get("id") for row in native_items}
    native_passed = (native.get("venue_id") == supplied["venue_id"] and all(hashes.values()) and
                     all(binding.get(key) == value for key, value in expected.items()) and
                     native.get("content_format_passed") is True and
                     {"native_word", "all_pages", "export_binding"} <= native_ids and
                     all(row.get("status") == "passed" for row in native_items))
    item("native_format", bool(native_passed), "Existing format report must pass native checks and bind these exact manuscript, DOCX, PDF and retained template bytes.")

    pages = [read(_relative(root, name)) for name in supplied["pages"]]
    page_hashes = [hashlib.sha256(value).hexdigest() if value is not None else None for value in pages]
    page_qa = native.get("page_qa") or {}
    if (not isinstance(page_qa, dict) or not isinstance(page_qa.get("pages", []), list) or
            any(not isinstance(row, dict) for row in page_qa.get("pages", []))):
        raise ValueError("Format report page_qa requires an object with page objects")
    visual = selected("visual_review", document=True) or {}
    try:
        visual_date = datetime.fromisoformat(visual.get("reviewed_at", "").replace("Z", "+00:00"))
        date_present = visual_date.tzinfo is not None
    except (ValueError, TypeError, AttributeError):
        date_present = False
    visual_passed = bool(all(page_hashes) and visual.get("approved") is True and visual.get("reviewer") and date_present and
                         visual.get("pdf_sha256") == hashes["pdf"] and hashes["pdf"] is not None and
                         visual.get("page_image_sha256") == page_hashes and page_qa.get("page_count") == len(pages) and
                         [row.get("image_sha256") for row in page_qa.get("pages", [])] == page_hashes)
    item("page_inspection", visual_passed, "Supplied dated page inspection must identify the exact PDF and every ordered actual page image; this is separate from author approval.")

    bundle = selected("bundle_report", document=True) or {}
    approval_files = bundle.get("approval_files", [])
    if (not isinstance(approval_files, list) or not isinstance(bundle.get("supplied_declarations", {}), dict)):
        raise ValueError("Bundle report requires an approval_files list and supplied_declarations object")
    bundle_path = _relative(root, supplied["bundle_report"]) if supplied["bundle_report"] is not None else None
    actual_files, bundle_matches, seen = [], bool(approval_files), set()
    for row in approval_files:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or row["path"].casefold() in seen:
            raise ValueError("Bundle approval_files requires distinct file paths")
        seen.add(row["path"].casefold())
        value = read(_relative(bundle_path.parent, row["path"]))
        current = hashlib.sha256(value).hexdigest() if value is not None else None
        bundle_matches = bundle_matches and current is not None and current == row.get("sha256")
        actual_files.append({**row, "sha256": current})
    manuscripts = [row for row in actual_files if row.get("role") == "manuscript"]
    review_pdfs = [row for row in actual_files if row.get("role") == "review_pdf"]
    selected_native = (len(manuscripts) == 1 and hashes["docx"] is not None and manuscripts[0]["sha256"] == hashes["docx"] and
                       all(row["sha256"] == hashes["pdf"] for row in review_pdfs))
    item("selected_files", bool(bundle_matches and bundle.get("venue_id") == supplied["venue_id"] and selected_native),
         "Select the exact DOCX as manuscript and any review PDF as the verified PDF; every final bundle file, including a generated cover letter, must still match its recorded bytes.")
    declarations = _declaration_status(bundle.get("supplied_declarations", {}), bundle.get("supplied_confirmations", {}), actual_files)
    declarations_passed = bool(bundle_matches and all(declarations[name]["status"] == "explicit_confirmation_recorded" for name in DECLARATIONS))
    item("author_declarations", declarations_passed, "All supplied declaration confirmations must bind their exact statement and every current final bundle file.")

    author_rows = (native.get("metrics") or {}).get("authors", [])
    if not isinstance(author_rows, list) or any(not isinstance(row, dict) for row in author_rows):
        raise ValueError("Format report authors must be a list of objects")
    factual_rows = [row for row in native.get("items", []) if row.get("id") in {"author_profile_binding", "author_biography"}]
    facts_complete = bool(author_rows and len(factual_rows) == 2 and all(row.get("status") == "passed" for row in factual_rows) and
                          all(row.get("supplied_fields_complete") is True and not row.get("missing_byline_values") for row in author_rows))
    item("supplied_author_facts", facts_complete, "Every author's supplied facts, byline association and biography must already be complete in the existing format report.")
    human = {}
    human_names = ["author_identity", "current_guidance", "required_files"]
    if supplied["venue_id"] == "ieee-software":
        human_names.append("author_photo")
    for name in human_names:
        record = confirmations.get(name)
        statement = record.get("statement") if isinstance(record, dict) else None
        if statement is not None and not isinstance(statement, str):
            raise ValueError("A confirmation statement must be supplied text")
        if isinstance(statement, str) and not statement.strip():
            statement = None
        human[name] = _confirmation(statement, record, actual_files)
        passed = bool(bundle_matches and human[name]["status"] == "explicit_confirmation_recorded")
        if name == "author_photo":
            passed = passed and bool(author_rows) and sum(row.get("role") == "author_photo" for row in actual_files) >= len(author_rows)
        item(name, bool(passed), "Actual supplied confirmation must identify who confirmed this statement, when, and every exact final file." +
             (" Select an approved photograph for each named author." if name == "author_photo" else ""))

    review = selected("scientific_review", document=True) or {}
    recommendation = review.get("recommendation")
    review_current = bool(hashes["manuscript"] and review.get("manuscript_sha256") == hashes["manuscript"] and
                          review.get("venue_id") == supplied["venue_id"])
    scientific_passed = bool(review_current and recommendation == "consider_submission" and review.get("essential_errors") == [])
    item("scientific_recommendation", scientific_passed, "A supplied scientific assessment must cover this exact manuscript and venue, recommend consideration, and record no essential errors. No new review is performed.")
    for path, expected_hash in snapshots.items():
        if (digest_file(path) if path.is_file() else None) != expected_hash:
            raise ValueError("An input changed while reconciling final preparation")
    administrative = [row for row in checks if row["id"] not in {"native_format", "page_inspection", "scientific_recommendation"}]
    report = {"mode": "existing_record_final_preparation", "created_at": datetime.now(timezone.utc).isoformat(),
              "venue_id": supplied["venue_id"], "artifact_hashes": hashes, "checks": checks,
              "native_format_passed": bool(native_passed), "page_inspection_recorded": visual_passed,
              "administrative_preparation_complete": all(row["status"] == "passed" for row in administrative),
              "scientific_content": {"review_current": review_current, "recommendation": recommendation, "consider_submission": scientific_passed},
              "human_confirmations": human, "declaration_status": declarations,
              "submission_ready": all(row["status"] == "passed" for row in checks),
              "pending": [row["id"] for row in checks if row["status"] != "passed"],
              "actual_submission_performed": False, "author_approval_inferred": False,
              "source_reports_preserved": True, "word_or_research_executed": False,
              "scope": "Reconciles supplied records with actual bytes; does not independently authenticate human records, redo scientific or native review, verify current publisher rules, submit, or predict acceptance.",
              "input_files": [{"path": str(path), "sha256": value} for path, value in snapshots.items()]}
    folder = _new_folder(output_dir)
    _write(folder / "final-preparation.json", report)
    lines = ["# Final submission preparation", "", "Submission ready: " + str(report["submission_ready"]),
             "Actual submission performed: False", "", "| Check | Status |", "| --- | --- |"]
    lines += [f"| {row['id']} | {row['status']} |" for row in checks]
    lines += ["", report["scope"], ""]
    (folder / "final-preparation.md").write_text("\n".join(lines), encoding="utf-8")
    _manifest(folder)
    return {"output_dir": str(folder), **report}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("check")
    command.add_argument("--root", type=Path, required=True)
    command.add_argument("--record", type=Path, required=True)
    command.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = check(args.root, args.record, args.output_dir)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["submission_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

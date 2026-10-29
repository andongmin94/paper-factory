"""Synthetic exact-file records exercise closure without executing Word or research."""

import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
finalizer = importlib.import_module("finalize_submission")
support = importlib.import_module("submission_support")


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) if isinstance(value, (dict, list)) else value, encoding="utf-8")
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def confirmation(statement, files):
    return {"statement": statement, "confirmed": True, "confirmed_by": "Synthetic fixture author; not a real approval",
            "confirmed_at": "2026-10-29T12:00:00+09:00", "declaration_sha256": hashlib.sha256(statement.encode()).hexdigest(),
            "files": [{"path": row["path"], "sha256": row["sha256"]} for row in files]}


@pytest.fixture
def prepared(tmp_path):
    root = tmp_path / "study"
    raw = root / "raw"
    manuscript = put(raw / "article.md", "# Synthetic fixture article\n\n## Abstract\n\nBounded content.\n")
    docx = put(raw / "article.docx", "Synthetic native bytes; this helper trusts a supplied bound report and does not render.")
    pdf = put(raw / "article.pdf", "Synthetic PDF bytes; no PDF parser is invoked by this reconciliation test.")
    put(raw / "photo.jpg", "Synthetic approved photograph placeholder.")
    pages = [put(root / "pages" / f"page-{i}.png", f"Synthetic rendered page {i}") for i in (1, 2)]
    rows = [{"role": role, "path": name} for role, name in (("manuscript", "article.docx"), ("review_pdf", "article.pdf"), ("author_photo", "photo.jpg"))]
    approval = [{"path": "files/" + row["path"], "sha256": sha(raw / row["path"])} for row in rows]
    cover = "Synthetic fixture cover letter."
    approval.append({"path": "cover-letter.md", "sha256": hashlib.sha256((cover + "\n").encode()).hexdigest()})
    declarations = {name: "Synthetic statement for " + name for name in support.DECLARATIONS}
    plan = put(root / "plan.json", {"venue_id": "ieee-software", "title": "Synthetic fixture article", "files": rows,
                                    "cover_letter": {"text": cover}, "declarations": declarations,
                                    "confirmations": {name: confirmation(text, approval) for name, text in declarations.items()}})
    support.prepare_bundle(plan, raw, root / "bundle")
    _, template = finalizer.official_template("ieee-software")
    native = {"venue_id": "ieee-software", "content_format_passed": True,
              "binding": {"markdown_sha256": sha(manuscript), "docx_sha256": sha(docx), "pdf_sha256": sha(pdf),
                          "template_sha256": template["sha256"], "template_provenance_sha256": template["provenance_sha256"]},
              "items": [{"id": name, "stage": "native", "status": "passed"} for name in ("abstract", "native_word", "all_pages", "export_binding")] +
                       [{"id": name, "stage": "submission", "status": "passed"} for name in ("author_profile_binding", "author_biography")] +
                       [{"id": name, "stage": "submission", "status": "pending"} for name in ("author_identity", "author_declarations", "author_photo", "visual_review")],
              "metrics": {"authors": [{"id": "synthetic", "supplied_fields_complete": True, "missing_byline_values": []}]},
              "page_qa": {"page_count": 2, "pages": [{"image_sha256": sha(p)} for p in pages]}}
    put(root / "format.json", native)
    put(root / "visual.json", {"approved": True, "reviewer": "Synthetic fixture visual reviewer", "reviewed_at": "2026-10-29T12:00:00+09:00",
                               "pdf_sha256": sha(pdf), "page_image_sha256": [sha(p) for p in pages]})
    put(root / "scientific.json", {"venue_id": "ieee-software", "manuscript_sha256": sha(manuscript),
                                   "recommendation": "consider_submission", "essential_errors": []})
    record = {"venue_id": "ieee-software", "manuscript": "raw/article.md", "docx": "raw/article.docx", "pdf": "raw/article.pdf",
              "format_report": "format.json", "visual_review": "visual.json", "bundle_report": "bundle/report.json", "scientific_review": "scientific.json",
              "pages": [p.relative_to(root).as_posix() for p in pages],
              "confirmations": {name: confirmation("Synthetic fixture confirmation for " + name, approval)
                                for name in ("author_identity", "current_guidance", "required_files", "author_photo")}}
    record_path = put(root / "record.json", record)
    return root, record_path, record


def test_complete_supplied_records_can_close_preparation_without_claiming_submission(prepared, tmp_path):
    root, record, _ = prepared
    before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = finalizer.check(root, record, tmp_path / "final")
    assert result["submission_ready"]
    assert result["native_format_passed"] and result["page_inspection_recorded"]
    assert result["administrative_preparation_complete"]
    assert result["scientific_content"]["consider_submission"]
    assert not result["actual_submission_performed"] and not result["author_approval_inferred"]
    assert not result["word_or_research_executed"]
    assert before == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_generated_cover_letter_change_invalidates_current_human_records(prepared, tmp_path):
    root, record, _ = prepared
    put(root / "bundle/cover-letter.md", "Changed bytes without fresh confirmation.\n")
    report = finalizer.check(root, record, tmp_path / "final")
    assert not report["submission_ready"]
    assert "selected_files" in report["pending"] and "author_declarations" in report["pending"]
    assert report["native_format_passed"]
    assert report["human_confirmations"]["author_identity"]["status"] == "pending"


def test_changed_native_file_cannot_reuse_a_successful_format_report(prepared, tmp_path):
    root, record, _ = prepared
    put(root / "raw/article.docx", "Changed exact native bytes.")
    report = finalizer.check(root, record, tmp_path / "final")
    assert not report["native_format_passed"] and not report["submission_ready"]
    assert "selected_files" in report["pending"]


def test_native_docx_in_a_companion_role_does_not_select_the_manuscript(prepared, tmp_path):
    root, record, _ = prepared
    bundle = json.loads((root / "bundle/report.json").read_text())
    next(row for row in bundle["approval_files"] if row["role"] == "manuscript")["role"] = "companion"
    put(root / "bundle/report.json", bundle)
    report = finalizer.check(root, record, tmp_path / "final")
    assert "selected_files" in report["pending"]
    assert not report["submission_ready"]


def test_confirmed_bundle_pdf_must_be_the_visually_checked_native_pdf(prepared, tmp_path):
    root, record_path, record = prepared
    bundle = json.loads((root / "bundle/report.json").read_text())
    row = next(row for row in bundle["approval_files"] if row["role"] == "review_pdf")
    put(root / "bundle" / row["path"], "Different selected PDF; explicitly synthetic fresh confirmations below.")
    row["sha256"] = sha(root / "bundle" / row["path"])
    for name, statement in bundle["supplied_declarations"].items():
        bundle["supplied_confirmations"][name] = confirmation(statement, bundle["approval_files"])
    for name, previous in record["confirmations"].items():
        record["confirmations"][name] = confirmation(previous["statement"], bundle["approval_files"])
    put(root / "bundle/report.json", bundle)
    put(record_path, record)
    report = finalizer.check(root, record_path, tmp_path / "final")
    assert report["native_format_passed"] and report["page_inspection_recorded"]
    assert report["declaration_status"]["author_approval"]["status"] == "explicit_confirmation_recorded"
    assert "selected_files" in report["pending"] and not report["submission_ready"]


def test_old_scientific_review_is_not_assigned_to_changed_manuscript(prepared, tmp_path):
    root, record, _ = prepared
    put(root / "raw/article.md", "Changed scientific manuscript.")
    report = finalizer.check(root, record, tmp_path / "final")
    assert not report["scientific_content"]["review_current"]
    assert "scientific_recommendation" in report["pending"]


@pytest.mark.parametrize("formats", [("docx",), ("pdf",), ("docx", "pdf")])
@pytest.mark.parametrize("matching", [True, False])
def test_explicit_scientific_review_export_bindings_must_match(prepared, tmp_path, formats, matching):
    root, record_path, _ = prepared
    review = json.loads((root / "scientific.json").read_text())
    review.update({name + "_sha256": sha(root / "raw" / ("article." + name)) if matching else "0" * 64
                   for name in formats})
    put(root / "scientific.json", review)
    report = finalizer.check(root, record_path, tmp_path / "final")
    assert report["native_format_passed"] and report["page_inspection_recorded"]
    assert report["scientific_content"]["review_current"] is matching
    assert report["submission_ready"] is matching
    assert ("scientific_recommendation" in report["pending"]) is not matching


def test_missing_human_information_stays_pending(prepared, tmp_path):
    root, record_path, record = prepared
    record["confirmations"] = {}
    put(record_path, record)
    report = finalizer.check(root, record_path, tmp_path / "final")
    assert not report["submission_ready"]
    assert {"author_identity", "author_photo", "current_guidance", "required_files"} <= set(report["pending"])


def test_wrong_or_missing_page_inspection_does_not_get_implicit_approval(prepared, tmp_path):
    root, record_path, record = prepared
    visual = json.loads((root / "visual.json").read_text())
    visual["page_image_sha256"].reverse()
    put(root / "visual.json", visual)
    first = finalizer.check(root, record_path, tmp_path / "wrong-order")
    assert not first["page_inspection_recorded"]
    record["visual_review"] = None
    put(record_path, record)
    missing = finalizer.check(root, record_path, tmp_path / "missing")
    assert not missing["page_inspection_recorded"]


def test_essential_error_prevents_unqualified_scientific_recommendation(prepared, tmp_path):
    root, record_path, _ = prepared
    review = json.loads((root / "scientific.json").read_text())
    review["essential_errors"] = ["Synthetic essential factual defect."]
    put(root / "scientific.json", review)
    report = finalizer.check(root, record_path, tmp_path / "final")
    assert not report["submission_ready"] and not report["scientific_content"]["consider_submission"]


def test_missing_author_facts_cannot_be_overridden_by_a_confirmation(prepared, tmp_path):
    root, record_path, _ = prepared
    native = json.loads((root / "format.json").read_text())
    native["metrics"]["authors"][0]["supplied_fields_complete"] = False
    put(root / "format.json", native)
    report = finalizer.check(root, record_path, tmp_path / "final")
    assert "supplied_author_facts" in report["pending"]


@pytest.mark.parametrize("missing,duplicate", [("author_biography", "author_profile_binding"),
                                               ("author_profile_binding", "author_biography")])
def test_each_author_fact_check_must_be_present_once(prepared, tmp_path, missing, duplicate):
    root, record_path, _ = prepared
    native = json.loads((root / "format.json").read_text())
    next(row for row in native["items"] if row["id"] == missing)["id"] = duplicate
    put(root / "format.json", native)
    report = finalizer.check(root, record_path, tmp_path / "final")
    assert report["native_format_passed"]
    assert "supplied_author_facts" in report["pending"]
    assert not report["submission_ready"]


def test_paths_cannot_escape_and_existing_final_report_is_preserved(prepared, tmp_path):
    root, record_path, record = prepared
    bad = copy.deepcopy(record)
    bad["pdf"] = "../outside.pdf"
    put(record_path, bad)
    with pytest.raises(ValueError, match="remain below"):
        finalizer.check(root, record_path, tmp_path / "bad")
    put(record_path, record)
    existing = tmp_path / "existing"
    existing.mkdir()
    keep = put(existing / "keep", "Retain me")
    with pytest.raises(FileExistsError):
        finalizer.check(root, record_path, existing)
    assert keep.read_text() == "Retain me"


def test_blank_statement_is_not_actual_confirmation(prepared, tmp_path):
    root, record_path, record = prepared
    files = json.loads((root / "bundle/report.json").read_text())["approval_files"]
    record["confirmations"]["author_identity"] = confirmation("   ", files)
    put(record_path, record)
    report = finalizer.check(root, record_path, tmp_path / "final")
    assert "author_identity" in report["pending"]


@pytest.mark.parametrize("filename,field,value", [("format.json", "items", ["malformed item"]),
                                                ("bundle/report.json", "approval_files", {"not": "a list"})])
def test_malformed_existing_report_is_refused_before_output(prepared, tmp_path, filename, field, value):
    root, record_path, _ = prepared
    supplied = json.loads((root / filename).read_text())
    supplied[field] = value
    put(root / filename, supplied)
    with pytest.raises(ValueError):
        finalizer.check(root, record_path, tmp_path / "final")
    assert not (tmp_path / "final").exists()

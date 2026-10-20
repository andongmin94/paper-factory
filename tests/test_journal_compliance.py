"""Journal-format contracts, distinct from scientific merit and author consent."""

import hashlib

import pytest

from paper_factory import conversion, journal_compliance as compliance, official_templates
from paper_factory.workspace import digest_file


def manuscript(venue="ieee-software", words=1000, abstract=40):
    insights = "\n\n## Actionable Insights\n\n- Use the retained boundary.\n- Compare the actual alternative.\n- State the conditional limit.\n" if venue == "ieee-software" else ""
    return ("# Synthetic format contract\n\nA Real Author\n\n## Abstract\n\n" + "bounded " * abstract
            + "\n\nKeywords: architecture; security; boundaries\n\n## Evidence\n\n"
            + "Supported " * words + "finding [1].\n" + insights
            + "\n## Acknowledgments\n\nSynthetic Tool, an AI language model, provided synthetic draft assistance throughout this test manuscript.\n"
            + "\n## References\n\n[1] A. Author, “Actual source title,” 2024. [Online]. Available: https://example.org/source.\n")


@pytest.mark.parametrize("venue", ["ieee-software", "ieee-security-privacy"])
def test_guidance_records_exact_different_limits_without_selecting_a_special_issue(venue):
    result = compliance.format_guidance(venue)
    assert result["checked_at"] == "2026-10-18"
    assert result["limits"]["max_abstract_words"] == (150 if venue == "ieee-software" else 50)
    assert result["limits"]["max_words"] == (4200 if venue == "ieee-software" else 7200)
    assert result["human_information_available"]["biography"] is False
    assert "does not select" in result["source_scope"]


def test_editorial_preparation_preserves_science_code_headings_and_original_binding():
    source = ("# Real title\n\n## Abstract\n\nThe finding is conditional.\n\n## Evidence\n\n"
              "The manuscript contains 12 reference entries and meets the word limit. Actual result remains.\n"
              "Literal prose\\n\\n## Limitations\\nUnknown deployment effects.\n\n"
              "`const value = '\\n'; arr[1]`\n\n```js\nconsole.log('\\n');\n```\n")
    result = compliance.prepare_editorial_markdown(source)
    assert "# Real title\n\n## Abstract" in result["markdown"]
    assert "Actual result remains." in result["markdown"]
    assert "12 reference entries" not in result["markdown"]
    assert "## Limitations\nUnknown deployment" in result["markdown"]
    assert "`const value = '\\n'; arr[1]`" in result["markdown"]
    assert "console.log('\\n');" in result["markdown"]
    assert result["original_sha256"] == hashlib.sha256(source.encode()).hexdigest()
    assert compliance.prepare_editorial_markdown(result["markdown"])["changes"] == []


def test_retained_reference_metadata_upgrades_only_matching_entries_without_inventing_fields():
    source = "## References\n\n[1] [https://example.org/source](https://example.org/source)\n\n[2] Unknown source https://example.org/unknown\n\n## Author Biography\n\nActual author text.\n"
    card = {"id": "focused-document-1", "url": "https://example.org/source", "title": "Actual retained title", "authors": ["A. Author", "B. Author"], "year": 2024, "doi": None, "fetched_at": "2026-10-18T00:00:00Z"}
    result = compliance.prepare_editorial_markdown(source, [card])
    assert '[1] A. Author, B. Author, “Actual retained title,” 2024.' in result["markdown"]
    assert "Accessed: 2026-10-18." in result["markdown"]
    assert "vol." not in result["markdown"] and "doi:" not in result["markdown"]
    assert "[2] Unknown source https://example.org/unknown" in result["markdown"]
    assert "## Author Biography\n\nActual author text." in result["markdown"]
    assert result["changes"][0]["supplied_fields"] == ["authors", "fetched_at", "title", "year"]


def test_pure_checks_count_keyword_paragraph_separately_and_expose_specific_author_facts():
    result = compliance.validate_manuscript(manuscript(abstract=150), "ieee-software", {"biography": "An incomplete supplied biography."})
    assert result["prefilter_passed"]
    assert result["metrics"]["abstract_words_estimate"] == 150
    assert len(result["metrics"]["missing_biography_fields"]) == 6
    assert not result["submission_ready"] and result["scientific_merit_assessed"] is False
    biography = next(item for item in result["items"] if item["id"] == "author_biography")
    assert biography["status"] == "pending" and "highest_degree" in biography["reason"]
    assert all({"id", "label", "status", "stage", "reason", "source_url"} == set(item) for item in result["items"])


def test_biography_field_presence_never_implies_identity_confirmation():
    author = {"biography": "Actual author-supplied text.", "biography_details": {key: "Actual supplied fact" for key in compliance.BIOGRAPHY_FIELDS}}
    result = compliance.validate_manuscript(manuscript(), "ieee-software", author)
    states = {item["id"]: item["status"] for item in result["items"]}
    assert states["author_biography"] == "passed"
    assert states["author_identity"] == states["author_declarations"] == states["author_photo"] == "pending"


def test_actual_previous_security_privacy_numeric_defects_cannot_be_declared_passed():
    result = compliance.validate_manuscript(manuscript("ieee-security-privacy", words=4700, abstract=51), "ieee-security-privacy")
    states = {item["id"]: item["status"] for item in result["items"]}
    assert states["abstract"] == states["word_count"] == "failed"
    assert not result["prefilter_passed"]


@pytest.mark.parametrize("defect,identifier", [
    ("Keywords: architecture; architecture; security", "keywords"),
    ("The manuscript contains 12 reference entries.", "self_attestation"),
    (r"Escaped prose\n\n## Another", "escaped_prose"),
    ("TODO: add the evidence", "placeholders"),
])
def test_format_prefilter_identifies_concrete_defects(defect, identifier):
    text = manuscript()
    text = text.replace("Keywords: architecture; security; boundaries", defect) if identifier == "keywords" else text.replace("## Evidence\n\n", "## Evidence\n\n" + defect + "\n\n")
    result = compliance.validate_manuscript(text, "ieee-software")
    assert next(item for item in result["items"] if item["id"] == identifier)["status"] == "failed"


def test_missing_ai_acknowledgment_cannot_be_faked_by_a_generic_author_responsibility_statement():
    text = manuscript().replace("Synthetic Tool, an AI language model, provided synthetic draft assistance throughout this test manuscript.", "All authors approved the paper.")
    result = compliance.validate_manuscript(text, "ieee-software")
    assert next(item for item in result["items"] if item["id"] == "ai_disclosure")["status"] == "failed"


@pytest.mark.parametrize("heading", ["Limits and Acknowledgments", "Limitations & ACKNOWLEDGEMENTS", "Acknowledgment and Funding"])
def test_ai_disclosure_accepts_a_bounded_acknowledgment_word_in_a_combined_heading(heading):
    text = manuscript().replace("## Acknowledgments", "## " + heading)
    result = compliance.validate_manuscript(text, "ieee-software")
    assert next(item for item in result["items"] if item["id"] == "ai_disclosure")["status"] == "passed"
    incomplete = text.replace("Synthetic Tool, an AI language model, provided synthetic draft assistance throughout this test manuscript.", "All authors approved the paper.")
    assert next(item for item in compliance.validate_manuscript(incomplete, "ieee-software")["items"] if item["id"] == "ai_disclosure")["status"] == "failed"


def test_ai_disclosure_heading_match_does_not_accept_an_acknowledgment_substring():
    text = manuscript().replace("## Acknowledgments", "## Limits and NotAcknowledgments")
    assert next(item for item in compliance.validate_manuscript(text, "ieee-software")["items"] if item["id"] == "ai_disclosure")["status"] == "failed"


def test_actionable_insights_accepts_descriptive_heading_but_not_a_substring():
    text = manuscript().replace("## Actionable Insights", "## Exactly Three Actionable Insights")
    result = compliance.validate_manuscript(text, "ieee-software")
    assert result["metrics"]["actionable_insights"] == 3
    assert next(item for item in result["items"] if item["id"] == "actionable_insights")["status"] == "passed"
    for heading, expected in (("NotActionable Insights", 0), ("Exactly Three Actionable InsightsExtra", 0)):
        invalid = manuscript().replace("## Actionable Insights", "## " + heading)
        assert compliance.validate_manuscript(invalid, "ieee-software")["metrics"]["actionable_insights"] == expected


@pytest.mark.parametrize("disclosure", [
    "gpt-6.1-sol provided substantial assistance in source and literature analysis, comparative reasoning, finite-model drafting, and manuscript prose.",
    "gpt-6.1-sol assisted the methods analysis and writing.",
])
def test_ai_disclosure_recognizes_named_gpt_model_and_actual_affected_prose(disclosure):
    text = manuscript().replace("Synthetic Tool, an AI language model, provided synthetic draft assistance throughout this test manuscript.", disclosure)
    assert next(item for item in compliance.validate_manuscript(text, "ieee-software")["items"] if item["id"] == "ai_disclosure")["status"] == "passed"


@pytest.mark.parametrize("disclosure", [
    "gpt-6.1-sol is named here without describing any assistance.",
    "Source analysis and manuscript writing received substantial assistance.",
    "gpt-6.1-sol performed comparative reasoning and research.",
])
def test_ai_disclosure_still_requires_tool_use_and_affected_manuscript_parts(disclosure):
    text = manuscript().replace("Synthetic Tool, an AI language model, provided synthetic draft assistance throughout this test manuscript.", disclosure)
    assert next(item for item in compliance.validate_manuscript(text, "ieee-software")["items"] if item["id"] == "ai_disclosure")["status"] == "failed"


def test_scientific_inert_placeholder_is_not_an_unfinished_editorial_marker():
    sentence = "The selected value initially serves as an inert placeholder; no queued request or live authority exists until selection."
    text = manuscript().replace("## Evidence\n\n", "## Evidence\n\n" + sentence + "\n\n")
    assert next(item for item in compliance.validate_manuscript(text, "ieee-software")["items"] if item["id"] == "placeholders")["status"] == "passed"


@pytest.mark.parametrize("marker", ["TODO", "todo: finish", "TBD", "fixme", "PLACEHOLDER", "[placeholder title]",
                                    "<placeholder>", "{{placeholder}}", "{{source:unknown}}"])
def test_explicit_editorial_markers_still_block_preflight(marker):
    text = manuscript().replace("## Evidence\n\n", "## Evidence\n\n" + marker + "\n\n")
    assert next(item for item in compliance.validate_manuscript(text, "ieee-software")["items"] if item["id"] == "placeholders")["status"] == "failed"


def test_missing_native_files_and_receipts_cannot_pass_complete_preflight(tmp_path):
    source = tmp_path / "draft.md"
    source.write_text(manuscript(), encoding="utf-8")
    result = compliance.compliance_report(source, None, "ieee-software")
    assert not result["content_format_passed"]
    assert any(item["id"] == "native_word" and item["status"] == "pending" for item in result["items"])
    assert any(item["id"] == "export_binding" and item["status"] == "failed" for item in result["items"])


def test_actual_pdfium_pages_are_bound_immutable_and_never_approve_visual_quality(tmp_path):
    import typst
    pdf = tmp_path / "actual.pdf"
    pdf.write_bytes(typst.compile(b'First actual PDF page. #pagebreak() Second actual PDF page.'))
    result = compliance.render_pdf_pages(pdf, tmp_path / "pages")
    assert result["page_count"] == 2 and result["automatic_checks"]
    assert result["pdf_sha256"] == digest_file(pdf)
    assert result["visual_review_status"] == "pending"
    assert all(page["text_chars"] > 0 and page["outside_page_characters"] == 0 for page in result["pages"])
    repeat = compliance.render_pdf_pages(pdf, tmp_path / "pages")
    assert result == repeat
    (tmp_path / "pages/page-001.png").write_bytes(b"different immutable page bytes")
    with pytest.raises(ValueError, match="replace different"):
        compliance.render_pdf_pages(pdf, tmp_path / "pages")


def test_blank_pdf_is_failed_structural_evidence(tmp_path):
    from pypdf import PdfWriter
    pdf = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=400, height=600)
    writer.write(pdf)
    result = compliance.render_pdf_pages(pdf, tmp_path / "pages")
    assert not result["automatic_checks"] and result["status"] == "failed"


def test_native_actual_metrics_override_estimates_and_require_exact_export_receipts(tmp_path, pandoc, monkeypatch):
    import typst
    source = tmp_path / "draft.md"
    source.write_text(manuscript(), encoding="utf-8")
    document, pdf = source.with_suffix(".docx"), source.with_suffix(".pdf")
    docx_receipt = conversion.convert(source, document, pandoc=pandoc, venue_id="ieee-software")
    pdf.write_bytes(typst.compile(b'Synthetic PDF rendering fixture only.'))
    actual = {"read_only": True, "whole_words": 1000, "abstract_words": 40, "body_words": 4201, "body_table_words": 0,
              "body_tables": 0, "body_figures": 0, "tables": 0, "figures": 0, "reference_heading_found": True, "reference_count": 1}
    monkeypatch.setattr(official_templates, "measure_word", lambda _: {"metrics": actual})
    pdf_receipt = {"input_sha256": digest_file(source), "output_sha256": digest_file(pdf), "source_docx_sha256": digest_file(document),
                   "word_rendering": {"source_docx_sha256": digest_file(document)}, "official_template": docx_receipt["official_template"]}
    kwargs = {"pdf": pdf, "qa_root": tmp_path / "pages", "conversion_receipts": {"docx": docx_receipt, "pdf": pdf_receipt}}
    result = compliance.compliance_report(source, document, "ieee-software", **kwargs)
    assert not result["content_format_passed"] and result["metrics"]["effective_words"] == 4201
    actual["body_words"] = 4000
    passed = compliance.compliance_report(source, document, "ieee-software", **kwargs)
    assert passed["content_format_passed"] and not passed["submission_ready"]
    assert next(item for item in passed["items"] if item["id"] == "visual_review")["status"] == "pending"
    kwargs["conversion_receipts"]["pdf"]["source_docx_sha256"] = "0" * 64
    failed = compliance.compliance_report(source, document, "ieee-software", **kwargs)
    assert not failed["content_format_passed"] and any("exact saved official Word" in message for message in failed["blockers"])

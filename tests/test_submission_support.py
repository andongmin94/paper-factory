"""Local submission preparation preserves facts, history and explicit scope."""

import importlib
import json
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
support = importlib.import_module("submission_support")

ARTICLE = """# A shared setting

<!-- paper-factory:authors:start -->

Old Author | old@example.org

<!-- paper-factory:authors:end -->

## Abstract

A bounded source example.

Keywords: configuration; ownership; cleanup

## Analysis

Alice Research wrote the retained tool. The local claim survives.

## References

[1] A retained source, 2026.

## Author biographies

Old biographical text.
"""


def put(path, value):
    path.write_text(json.dumps(value) if isinstance(value, dict) else value, encoding="utf-8")
    return path


@pytest.fixture
def inputs(tmp_path):
    article = put(tmp_path / "article.md", ARTICLE)
    profile = put(tmp_path / "profile.json", {
        "authors": [
            {"id": "alice", "author": {"display_name": "Alice Research", "affiliation": "Lab A", "email": "alice@example.org", "biography": "Studies software."}, "contributions": ["Writing"]},
            {"id": "bob", "author": {"display_name": "Bob Scientist", "affiliation": "Lab B"}, "contributions": ["Investigation"]}],
        "order": ["bob", "alice"], "corresponding_author": "alice", "funding": None, "conflicts": None})
    return article, profile


def test_explicit_coauthors_order_and_original_preserved(tmp_path, inputs):
    article, profile = inputs
    before = article.read_bytes(), profile.read_bytes()
    result = support.prepare_authors(profile, article, tmp_path / "authors")
    written = (tmp_path / "authors/manuscript.md").read_text(encoding="utf-8")
    assert written.index("Bob Scientist") < written.index("Alice Research")
    assert "Alice Research. Studies software." in written
    assert "Old Author" not in written and "Old biographical text" not in written
    assert "Alice Research wrote the retained tool. The local claim survives." in written
    assert "## References\n\n[1] A retained source, 2026." in written
    assert "bob: email" in result["missing_supplied_fields"]
    assert result["author_confirmation_required"] and not result["author_approval_inferred"]
    assert before == (article.read_bytes(), profile.read_bytes())


def test_anonymous_dedicated_fields_removed_body_match_reported(tmp_path, inputs):
    article, profile = inputs
    result = support.prepare_authors(profile, article, tmp_path / "new", anonymous=True)
    text = (tmp_path / "new/anonymous.md").read_text(encoding="utf-8")
    assert "Old Author" not in text and "Author biographies" not in text
    assert "Alice Research wrote the retained tool" in text
    assert "Alice Research" in result["anonymous_check"]["residual_matches"]
    assert not result["anonymous_check"]["fully_anonymized_claimed"]
    assert "metadata" in result["anonymous_check"]["scope"]


@pytest.mark.parametrize("field,value", [("order", ["alice", "alice"]), ("order", ["alice"]), ("corresponding_author", "absent")])
def test_invalid_author_order_and_selection_rejected(tmp_path, inputs, field, value):
    article, profile = inputs
    content = json.loads(profile.read_text())
    content[field] = value
    put(profile, content)
    with pytest.raises(ValueError):
        support.prepare_authors(profile, article, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_author_preparation_refuses_existing_output(tmp_path, inputs):
    article, profile = inputs
    folder = tmp_path / "out"
    folder.mkdir()
    keep = put(folder / "keep", "original")
    with pytest.raises(FileExistsError):
        support.prepare_authors(profile, article, folder)
    assert keep.read_text() == "original"


def test_unrecognized_pre_abstract_section_is_not_silently_replaced(tmp_path, inputs):
    article, profile = inputs
    put(article, ARTICLE.replace("Old Author | old@example.org", "## Context\n\nResearch finding."))
    with pytest.raises(ValueError, match="dedicated byline"):
        support.prepare_authors(profile, article, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_unmarked_pre_abstract_prose_is_refused_without_any_deletion(tmp_path, inputs):
    article, profile = inputs
    prose = "This practical argument follows an important boundary condition."
    put(article, ARTICLE.replace("<!-- paper-factory:authors:start -->\n\nOld Author | old@example.org\n\n<!-- paper-factory:authors:end -->", prose))
    original = article.read_bytes()
    with pytest.raises(ValueError, match="Ambiguous pre-Abstract content"):
        support.prepare_authors(profile, article, tmp_path / "new")
    assert article.read_bytes() == original
    assert not (tmp_path / "new").exists()


def test_prose_next_to_explicit_author_block_and_repeated_preparation_survive(tmp_path, inputs):
    article, profile = inputs
    prose = "Scope note: the article analyzes a retained source snapshot."
    put(article, ARTICLE.replace("<!-- paper-factory:authors:end -->", "<!-- paper-factory:authors:end -->\n\n" + prose))
    support.prepare_authors(profile, article, tmp_path / "first", anonymous=True)
    support.prepare_authors(profile, tmp_path / "first/manuscript.md", tmp_path / "second", anonymous=True)
    for folder in ("first", "second"):
        text = (tmp_path / folder / "manuscript.md").read_text()
        assert text.count(prose) == 1
        assert text.count("Bob Scientist | Lab B") == 1
        assert prose in (tmp_path / folder / "anonymous.md").read_text()


def test_author_markers_in_front_matter_code_are_not_deletion_instructions(tmp_path, inputs):
    article, profile = inputs
    example = "```html\n<!-- paper-factory:authors:start -->\nA literal marker example.\n<!-- paper-factory:authors:end -->\n```"
    source = "# Title\n\n" + example + "\n\n## Abstract\n\nBounded text.\n"
    put(article, source)
    with pytest.raises(ValueError, match="Ambiguous pre-Abstract content"):
        support.prepare_authors(profile, article, tmp_path / "out")
    assert article.read_text() == source
    assert not (tmp_path / "out").exists()


def test_biography_heading_in_code_example_is_preserved(tmp_path, inputs):
    article, profile = inputs
    put(article, ARTICLE.replace("The local claim survives.", "The local claim survives.\n\n```markdown\n## Author biographies\nAn example, not an actual author section.\n```"))
    support.prepare_authors(profile, article, tmp_path / "out", anonymous=True)
    text = (tmp_path / "out/anonymous.md").read_text()
    assert "## Author biographies\nAn example, not an actual author section." in text
    assert "Old biographical text." not in text


@pytest.mark.parametrize("abstract_heading,biography_heading", [
    ("## Abstract", "## Author biographies ##"),
    ("  ## Abstract ##", "  ## Author biographies ##"),
])
def test_author_preparation_recognizes_markdown_section_variants(tmp_path, inputs, abstract_heading, biography_heading):
    article, profile = inputs
    example = "```markdown\n## Author biographies ##\nA literal biography example.\n```"
    appendix = "  ## Appendix ##\n\nThe retained appendix remains.\n"
    source = ARTICLE.replace("## Abstract\n", abstract_heading + "\n")
    source = source.replace("## Author biographies\n", biography_heading + "\n")
    source = source.replace("The local claim survives.", "The local claim survives.\n\n" + example)
    put(article, source + "\n" + appendix)
    original = article.read_bytes(), profile.read_bytes()
    result = support.prepare_authors(profile, article, tmp_path / "out", anonymous=True)
    authored = (tmp_path / "out/manuscript.md").read_text(encoding="utf-8")
    anonymous = (tmp_path / "out/anonymous.md").read_text(encoding="utf-8")
    for text in (authored, anonymous):
        assert "Old biographical text." not in text
        assert "A bounded source example." in text
        assert "Alice Research wrote the retained tool. The local claim survives." in text
        assert "## References\n\n[1] A retained source, 2026." in text
        assert example in text
        assert appendix in text
    assert "Alice Research. Studies software." in authored
    assert "Alice Research. Studies software." not in anonymous
    assert result["anonymous_check"]["fully_anonymized_claimed"] is False
    assert original == (article.read_bytes(), profile.read_bytes())


def test_responses_check_actual_after_section_and_do_not_infer_resolution(tmp_path):
    before = put(tmp_path / "before.md", "# A\n\n## Analysis\n\nOld text.\n")
    after = put(tmp_path / "after.md", "# A\n\n## Analysis\n\nNew bounded text.\n\n## Limits\n\nNew limits.\n")
    comments = put(tmp_path / "comments.json", {"comments": [
        {"id": "R1", "comment": "Clarify scope.", "status": "addressed", "response": "The scope is stated in Analysis.", "changes": [{"quote": "New bounded text.", "section": "Analysis"}]},
        {"id": "R2", "comment": "Add evidence.", "status": "addressed", "response": "Added.", "changes": [{"quote": "New limits.", "section": "Analysis"}]},
        {"id": "R3", "comment": "Show execution.", "status": "pending", "response": "", "changes": []}]})
    original = before.read_bytes(), after.read_bytes(), comments.read_bytes()
    result = support.prepare_responses(comments, before, after, tmp_path / "replies")
    assert result["comments"][0]["changes"][0]["present_in_revised_manuscript"]
    assert not result["comments"][1]["changes"][0]["present_in_revised_manuscript"]
    assert result["comments"][1]["issues"]
    assert not result["scientific_resolution_verified"]
    assert "Response pending." in (tmp_path / "replies/response-letter.md").read_text()
    assert original == (before.read_bytes(), after.read_bytes(), comments.read_bytes())


def test_response_anchors_follow_markdown_section_boundaries(tmp_path):
    before = put(tmp_path / "before.md", "# Article\n\n  ## Analysis ##\n\nOld analysis.\n\n  ## Limits ##\n\nOld limits.\n")
    after = put(tmp_path / "after.md", "# Article\n\n  ## Analysis ##\n\nNew bounded analysis.\n\n  ## Limits ##\n\nNew limitation.\n")
    comments = put(tmp_path / "comments.json", {"comments": [
        {"id": "R1", "comment": "Clarify the analysis.", "status": "addressed", "response": "The analysis is clarified.",
         "changes": [{"quote": "New bounded analysis.", "section": "Analysis"}]},
        {"id": "R2", "comment": "Clarify the limit.", "status": "addressed", "response": "A limitation is stated.",
         "changes": [{"quote": "New limitation.", "section": "Analysis"}]},
    ]})
    original = before.read_bytes(), after.read_bytes(), comments.read_bytes()
    result = support.prepare_responses(comments, before, after, tmp_path / "replies")
    assert result["comments"][0]["changes"][0]["present_in_revised_manuscript"] is True
    assert result["comments"][0]["issues"] == []
    assert result["comments"][1]["changes"][0]["present_in_revised_manuscript"] is False
    assert result["comments"][1]["issues"]
    assert original == (before.read_bytes(), after.read_bytes(), comments.read_bytes())


def test_addressed_without_response_or_anchor_is_flagged(tmp_path):
    manuscript = put(tmp_path / "m.md", "# Article\n")
    comments = put(tmp_path / "c.json", {"comments": [{"id": "R1", "comment": "More context", "status": "addressed"}]})
    result = support.prepare_responses(comments, manuscript, manuscript, tmp_path / "new")
    assert result["comments"][0]["supplied_status"] == "addressed"
    assert result["comments"][0]["issues"]
    assert result["summary"]["incomplete_response_count"] == 1
    assert result["all_change_anchors_present"] is None


def test_not_changed_requires_explanation_and_summary_preserves_pending(tmp_path):
    manuscript = put(tmp_path / "m.md", "# Article\n")
    comments = put(tmp_path / "c.json", {"comments": [
        {"id": "R1", "comment": "Execute a study", "status": "not_changed"},
        {"id": "R2", "comment": "Add measurements", "status": "pending"},
        {"id": "R3", "comment": "Broaden scope", "status": "not_changed", "response": "The retained study has no population evidence; we preserve its bounded static scope."}]})
    result = support.prepare_responses(comments, manuscript, manuscript, tmp_path / "new")
    assert result["summary"] == {"comment_count": 3, "pending_comment_count": 1, "incomplete_response_count": 2,
                                 "change_anchor_count": 0, "missing_change_anchor_count": 0, "response_draft_complete": False}
    assert result["comments"][0]["issues"] and not result["comments"][2]["issues"]
    assert not result["scientific_resolution_verified"]


def test_honest_explained_disagreement_completes_draft_without_claiming_change(tmp_path):
    manuscript = put(tmp_path / "m.md", "# Article\n")
    comments = put(tmp_path / "c.json", {"comments": [{"id": "R1", "comment": "Execute a study", "status": "not_changed",
                                                     "response": "No deployment evidence was collected; we narrowed the claim to static analysis."}]})
    result = support.prepare_responses(comments, manuscript, manuscript, tmp_path / "new")
    assert result["summary"]["response_draft_complete"]
    assert result["all_change_anchors_present"] is None
    assert not result["scientific_resolution_verified"]


def test_an_unchanged_quote_is_not_evidence_that_revision_was_done(tmp_path):
    manuscript = put(tmp_path / "m.md", "# Article\n\n## Analysis\n\nExisting sentence.\n")
    comments = put(tmp_path / "c.json", {"comments": [{"id": "R1", "comment": "More context", "status": "addressed", "response": "Changed.", "changes": [{"quote": "Existing sentence."}]}]})
    result = support.prepare_responses(comments, manuscript, manuscript, tmp_path / "new")
    assert result["comments"][0]["changes"][0]["also_present_in_previous_manuscript"]
    assert any("already occurred" in issue for issue in result["comments"][0]["issues"])


def test_bundle_only_allowlisted_files_and_exact_hashes(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    manuscript = put(root / "article.md", ARTICLE)
    put(root / "private-profile.json", {"email": "not-in-package@example.org"})
    plan = put(tmp_path / "plan.json", {"venue_id": "ieee-software", "title": "A shared setting", "files": [{"role": "manuscript", "path": "article.md"}], "cover_letter": {"text": "Please consider the attached article."}, "declarations": {"originality": "Author must confirm"}})
    result = support.prepare_bundle(plan, root, tmp_path / "package")
    assert (tmp_path / "package/files/article.md").read_bytes() == manuscript.read_bytes()
    assert not (tmp_path / "package/files/private-profile.json").exists()
    assert "Please consider" in (tmp_path / "package/cover-letter.md").read_text()
    assert any("photographs" in x for x in result["pending"])
    assert "Confirm actual originality" in result["pending"]
    assert result["declaration_status"]["originality"]["status"] == "pending"
    assert not result["submission_ready"] and not result["actual_submission_performed"]
    manifest = json.loads((tmp_path / "package/manifest.json").read_text())
    assert all(support.digest_file(tmp_path / "package" / row["path"]) == row["sha256"] for row in manifest["files"])


def test_explicit_declaration_confirmation_is_bound_to_exact_text_and_all_selected_files(tmp_path):
    import hashlib
    root = tmp_path / "source"
    root.mkdir()
    article = put(root / "article.md", ARTICLE)
    statement = "The named author confirms the originality of this exact selected manuscript."
    confirmation = {"confirmed": True, "confirmed_by": "Synthetic test author", "confirmed_at": "2026-10-28T12:00:00+09:00",
                    "declaration_sha256": hashlib.sha256(statement.encode()).hexdigest(),
                    "files": [{"path": "files/article.md", "sha256": support.digest_file(article)}]}
    plan_data = {"venue_id": "ieee-software", "title": "A", "files": [{"role": "manuscript", "path": "article.md"}],
                 "declarations": {"originality": statement}, "confirmations": {"originality": confirmation}}
    plan = put(tmp_path / "plan.json", plan_data)
    result = support.prepare_bundle(plan, root, tmp_path / "confirmed")
    assert result["declaration_status"]["originality"]["status"] == "explicit_confirmation_recorded"
    assert "Confirm actual originality" not in result["pending"]
    assert not result["author_approval_inferred"] and not result["submission_ready"]
    put(article, ARTICLE + "\nChanged exact article bytes.\n")
    result = support.prepare_bundle(plan, root, tmp_path / "changed-file")
    assert result["declaration_status"]["originality"]["status"] == "pending"
    assert "Confirm actual originality" in result["pending"]
    plan_data["declarations"]["originality"] = "A different statement without fresh confirmation."
    put(plan, plan_data)
    result = support.prepare_bundle(plan, root, tmp_path / "changed-statement")
    assert any("exact declaration text" in reason for reason in result["declaration_status"]["originality"]["reasons"])


def test_generated_cover_letter_is_part_of_exact_confirmation_scope(tmp_path):
    import hashlib
    root = tmp_path / "source"
    root.mkdir()
    article = put(root / "article.md", ARTICLE)
    statement = "Synthetic test author approves these exact prepared files."
    cover = "Please consider the attached bounded case study."
    record = {"confirmed": True, "confirmed_by": "Synthetic test author", "confirmed_at": "2026-10-29T12:00:00+09:00",
              "declaration_sha256": hashlib.sha256(statement.encode()).hexdigest(),
              "files": [{"path": "files/article.md", "sha256": support.digest_file(article)},
                        {"path": "cover-letter.md", "sha256": hashlib.sha256((cover + "\n").encode()).hexdigest()}]}
    data = {"venue_id": "ieee-software", "title": "A", "files": [{"role": "manuscript", "path": "article.md"}],
            "cover_letter": {"text": cover}, "declarations": {"author_approval": statement}, "confirmations": {"author_approval": record}}
    plan = put(tmp_path / "plan.json", data)
    report = support.prepare_bundle(plan, root, tmp_path / "first")
    assert report["declaration_status"]["author_approval"]["status"] == "explicit_confirmation_recorded"
    assert report["approval_files"][-1]["sha256"] == support.digest_file(tmp_path / "first/cover-letter.md")
    data["cover_letter"]["text"] += " This changed wording needs fresh approval."
    put(plan, data)
    changed = support.prepare_bundle(plan, root, tmp_path / "changed")
    assert changed["declaration_status"]["author_approval"]["status"] == "pending"


def test_cover_letter_must_have_one_unambiguous_source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    put(root / "cover.md", "A supplied letter")
    plan = put(tmp_path / "plan.json", {"venue_id": "ieee-software", "title": "A", "files": [{"role": "cover_letter", "path": "cover.md"}],
                                      "cover_letter": {"text": "A generated letter"}})
    with pytest.raises(ValueError, match="one supplied cover-letter"):
        support.prepare_bundle(plan, root, tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_bare_boolean_is_not_a_human_declaration_record(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    put(root / "article.md", ARTICLE)
    plan = put(tmp_path / "plan.json", {"venue_id": "ieee-software", "title": "A", "files": [{"role": "manuscript", "path": "article.md"}],
                                      "declarations": {"author_approval": True}})
    with pytest.raises(ValueError, match="separate confirmations"):
        support.prepare_bundle(plan, root, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("path", ["../outside.md", "/outside.md", "C:/outside.md", "a/../outside.md", "a\\outside.md", "article.md:stream", "a//b.md"])
def test_bundle_rejects_path_escape_without_output(tmp_path, path):
    root = tmp_path / "root"
    root.mkdir()
    put(tmp_path / "outside.md", "private")
    plan = put(tmp_path / "plan.json", {"venue_id": "ieee-software", "title": "A", "files": [{"role": "manuscript", "path": path}]})
    with pytest.raises(ValueError):
        support.prepare_bundle(plan, root, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_bundle_refuses_duplicate_destination_and_output_inside_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    put(root / "a.md", "# A")
    entry = {"role": "manuscript", "path": "a.md"}
    plan = put(tmp_path / "plan.json", {"venue_id": "ieee-software", "title": "A", "files": [entry, entry]})
    with pytest.raises(ValueError, match="Duplicate"):
        support.prepare_bundle(plan, root, tmp_path / "out")
    with pytest.raises(ValueError, match="outside"):
        support.prepare_bundle(plan, root, root / "out")


def test_docx_metadata_actual_author_custom_orcid_and_revision_markers(tmp_path, inputs):
    _, profile = inputs
    document = tmp_path / "article.docx"
    with zipfile.ZipFile(document, "w") as package:
        package.writestr("docProps/core.xml", '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>Alice Research</dc:creator><cp:lastModifiedBy>Bob Scientist</cp:lastModifiedBy></cp:coreProperties>')
        package.writestr("docProps/custom.xml", '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><property name="ORCID"><vt:lpwstr>0009-0009-8671-9967</vt:lpwstr></property></Properties>')
        package.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:ins w:author="Alice Research"><w:r><w:t>A change</w:t></w:r></w:ins></w:p></w:body></w:document>')
        package.writestr("word/comments.xml", '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:comment w:author="Alice Research" w:id="0"><w:p/></w:comment></w:comments>')
    before = document.read_bytes()
    report = support.inspect_metadata(document, tmp_path / "metadata", profile=profile)
    assert report["metadata"]["core.creator"] == "Alice Research"
    assert report["metadata"]["custom.ORCID"] == "0009-0009-8671-9967"
    assert report["docx_comment_count"] == report["docx_tracked_change_elements"] == 1
    assert any(match["matched_profile_value"] == "Alice Research" for match in report["profile_matches"])
    assert not report["metadata_scrubbed"] and not report["fully_anonymized_claimed"]
    assert document.read_bytes() == before


def pdf_bytes():
    # A real, tiny PDF with an Info dictionary, parsed by the existing PDFium.
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>',
               b'<< /Author (Alice Research) /Title (A shared setting) /Creator (A local tool) >>']
    content, offsets = b'%PDF-1.4\n', [0]
    for number, item in enumerate(objects, 1):
        offsets.append(len(content))
        content += str(number).encode() + b' 0 obj\n' + item + b'\nendobj\n'
    xref = len(content)
    content += b'xref\n0 5\n0000000000 65535 f \n'
    content += b''.join(f'{offset:010} 00000 n \n'.encode() for offset in offsets[1:])
    return content + f'trailer\n<< /Size 5 /Root 1 0 R /Info 4 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


def test_pdf_metadata_uses_actual_pdfium_and_keeps_original(tmp_path, inputs):
    _, profile = inputs
    document = tmp_path / "article.pdf"
    document.write_bytes(pdf_bytes())
    original = document.read_bytes()
    report = support.inspect_metadata(document, tmp_path / "pdf-check", profile=profile)
    assert report["metadata"]["Author"] == "Alice Research"
    assert report["metadata"]["Title"] == "A shared setting"
    assert report["profile_matches"]
    assert report["manual_anonymity_review_required"]
    assert document.read_bytes() == original


@pytest.mark.parametrize("suffix,content", [(".docx", b"invalid zip"), (".pdf", b"invalid pdf"), (".txt", b"plain text")])
def test_invalid_metadata_input_does_not_create_output(tmp_path, suffix, content):
    source = tmp_path / ("input" + suffix)
    source.write_bytes(content)
    with pytest.raises(ValueError):
        support.inspect_metadata(source, tmp_path / "new")
    assert source.read_bytes() == content
    assert not (tmp_path / "new").exists()


def test_malformed_docx_property_xml_is_reported_without_replacement(tmp_path):
    source = tmp_path / "a.docx"
    with zipfile.ZipFile(source, "w") as z:
        z.writestr("word/document.xml", "<broken>")
    with pytest.raises(ValueError, match="malformed"):
        support.inspect_metadata(source, tmp_path / "new")
    assert not (tmp_path / "new").exists()

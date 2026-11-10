"""Output-tool invariants without executing an input repository or launching Word."""

import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
exporter = importlib.import_module("export_manuscript")
converter = importlib.import_module("_publication_convert")
templates = importlib.import_module("_publication_templates")
checks = importlib.import_module("_publication_checks")
author_facts = importlib.import_module("_author_profile")

ARTICLE = """# Shared configuration cleanup

## Abstract

A conditional static example explains a maintenance decision.

Keywords: maintenance; configuration; ownership

## A practical decision

A shared requirement may survive the command that first wrote it. [1]

## Actionable insights

- Record the continuing consumer.
- Preserve the original setting.
- Refuse uncertain restoration.

## Acknowledgments

OpenAI Codex assisted with the analysis and prose throughout this article.

## References

[1] Example Authors, A retained source, 2025. https://example.org/source
"""


@pytest.fixture
def manuscript(tmp_path):
    source = tmp_path / "article.md"
    source.write_text(ARTICLE, encoding="utf-8")
    return source


def test_preflight_uses_explicit_facts_and_preserves_input(manuscript, monkeypatch):
    monkeypatch.setenv("PF_AUTHOR_PROFILE_JSON", '{"display_name":"Ambient person"}')
    before = manuscript.read_bytes()
    result = exporter.preflight(manuscript, "ieee-software")
    assert result["author_metadata"] == {}
    assert result["prefilter_passed"]
    assert not result["submission_ready"]
    assert not result["native_word_measured"]
    assert manuscript.read_bytes() == before
    assert list(manuscript.parent.iterdir()) == [manuscript]


@pytest.mark.parametrize("separator", ["\n", "\n\n"])
def test_preflight_counts_multiline_references_with_supported_separators(manuscript, separator):
    references = [
        "[1] First Authors,\n  A retained first title, 2024. https://example.org/first",
        "[2] Second Authors,\n  A retained second title, 2025. https://example.org/second",
    ]
    manuscript.write_text(ARTICLE.split("## References", 1)[0] + "## References\n\n" +
                          separator.join(references) + "\n", encoding="utf-8")
    original = manuscript.read_bytes()
    result = exporter.preflight(manuscript, "ieee-software")
    statuses = {row["id"]: row["status"] for row in result["items"]}
    assert result["metrics"]["reference_count"] == 2
    assert statuses["reference_count"] == "passed"
    assert statuses["reference_metadata"] == "passed"
    assert result["prefilter_passed"]
    assert not result["native_word_measured"]
    assert manuscript.read_bytes() == original


@pytest.mark.parametrize("case, count_status, metadata_status", [
    ("duplicate", "failed", "passed"),
    ("gap", "failed", "passed"),
    ("over_limit", "failed", "passed"),
    ("raw_url", "passed", "failed"),
])
def test_preflight_rejects_invalid_consecutive_references(manuscript, case, count_status, metadata_status):
    numbers = {
        "duplicate": [1, 1, 2, 3],
        "gap": [1, 3],
        "over_limit": list(range(1, checks.VENUE_LIMITS["ieee-software"]["max_references"] + 2)),
        "raw_url": [1, 2],
    }[case]
    references = [f"[{number}] Example Authors, Retained source {index}, 2025."
                  for index, number in enumerate(numbers, 1)]
    if case == "raw_url":
        references[1] = "[2] https://example.org/second"
    manuscript.write_text(ARTICLE.split("## References", 1)[0] + "## References\n\n" +
                          "\n".join(references) + "\n", encoding="utf-8")
    original = manuscript.read_bytes()
    result = exporter.preflight(manuscript, "ieee-software")
    statuses = {row["id"]: row["status"] for row in result["items"]}
    assert result["metrics"]["reference_count"] == len(numbers)
    assert statuses["reference_count"] == count_status
    assert statuses["reference_metadata"] == metadata_status
    assert not result["prefilter_passed"]
    assert not result["native_word_measured"]
    assert manuscript.read_bytes() == original


@pytest.mark.parametrize("citation", ["[1]", "[1, 3]", "[1-4]", "[1; 3]", "[1, 3–4]"])
def test_preflight_rejects_supported_numeric_citations_in_abstract(manuscript, citation):
    text = ARTICLE.replace("A conditional static example explains a maintenance decision.",
                           "A conditional static example bounds $x \\in [0,1]$ " + citation + ".", 1)
    manuscript.write_text(text, encoding="utf-8")
    original = manuscript.read_bytes()
    result = exporter.preflight(manuscript, "ieee-software")
    statuses = {row["id"]: row["status"] for row in result["items"]}
    assert statuses["abstract_structure"] == "failed"
    assert not result["prefilter_passed"]
    assert not result["native_word_measured"]
    assert manuscript.read_bytes() == original


def test_math_in_body_and_abstract_passes_preflight_cli(manuscript, capsys):
    text = ARTICLE.replace("A conditional static example explains a maintenance decision.",
                           "A conditional static example bounds $p \\in [0,1]$.", 1)
    text = text.replace("first wrote it. [1]", "first wrote it. [1]\n\n"
                        "The parameter is bounded by $x \\in [0,1]$.\n\n$$a[3-1]$$")
    manuscript.write_text(text, encoding="utf-8")
    original = manuscript.read_bytes()
    parsed = subprocess.run([str(_real_pandoc()), "--from=" + converter.WORD_MARKDOWN_READER,
                             "--to=json", "--standalone", str(manuscript)],
                            capture_output=True, text=True, encoding="utf-8", check=True, timeout=30)
    math = [node["c"] for block in json.loads(parsed.stdout)["blocks"] if block["t"] == "Para"
            for node in block["c"] if node["t"] == "Math"]
    assert [(kind["t"], content) for kind, content in math] == [
        ("InlineMath", r"p \in [0,1]"), ("InlineMath", r"x \in [0,1]"),
        ("DisplayMath", "a[3-1]")]
    status = exporter.main(["preflight", "--manuscript", str(manuscript), "--venue", "ieee-software"])
    result = json.loads(capsys.readouterr().out)
    statuses = {row["id"]: row["status"] for row in result["items"]}
    assert status == 0 and result["prefilter_passed"]
    assert statuses["abstract_structure"] == statuses["citation_references"] == "passed"
    assert not result["native_word_measured"]
    assert manuscript.read_bytes() == original


def test_preflight_body_grouped_citation_does_not_fail_abstract_structure(manuscript):
    text = ARTICLE.replace("A shared requirement may survive the command that first wrote it. [1]",
                           "A shared requirement may survive the command that first wrote it. [1, 3–4]", 1)
    text = text.split("## References", 1)[0] + "## References\n\n" + "\n\n".join(
        f"[{number}] Example Authors, Retained source {number}, 2025." for number in range(1, 5)) + "\n"
    manuscript.write_text(text, encoding="utf-8")
    original = manuscript.read_bytes()
    result = exporter.preflight(manuscript, "ieee-software")
    statuses = {row["id"]: row["status"] for row in result["items"]}
    assert statuses["abstract_structure"] == "passed"
    assert result["prefilter_passed"]
    assert not result["native_word_measured"]
    assert manuscript.read_bytes() == original


@pytest.mark.parametrize("citation", [
    "[4]", "[1, 4]", "[2-4]", "[3-1]", "[1–999999999]", "[1,,2]",
    "[1, **4**]", "[1, *4*]", "[1,\n4]",
    pytest.param("An unmatched `marker.\n\nThe result cites [9].\n\nAnother `marker.",
                 id="backticks-across-paragraphs"),
])
def test_numeric_citation_gate_fails_preflight_cli_without_changing_source(manuscript, capsys, citation):
    text = ARTICLE.replace("first wrote it. [1]", "first wrote it. " + citation)
    text = text.split("## References", 1)[0] + "## References\n\n" + "\n\n".join(
        f"[{number}] Example Authors, Retained source {number}, 2025." for number in range(1, 4)) + "\n"
    manuscript.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    original = manuscript.read_bytes()
    status = exporter.main(["preflight", "--manuscript", str(manuscript), "--venue", "ieee-software"])
    result = json.loads(capsys.readouterr().out)
    assert status == 1
    row = next(item for item in result["items"] if item["id"] == "citation_references")
    assert row["status"] == "failed" and row["reason"] in result["blockers"]
    assert not result["prefilter_passed"]
    assert manuscript.read_bytes() == original


@pytest.mark.parametrize("citation", ["[1, **2**; *3*]", "[1,\n2–3]"])
def test_numeric_citation_gate_accepts_formatted_and_wrapped_valid_groups(manuscript, citation):
    text = ARTICLE.replace("first wrote it. [1]", "first wrote it. " + citation)
    text = text.split("## References", 1)[0] + "## References\n\n" + "\n\n".join(
        f"[{number}] Example Authors, Retained source {number}, 2025." for number in range(1, 4)) + "\n"
    manuscript.write_text(text, encoding="utf-8")
    original = manuscript.read_bytes()
    result = exporter.preflight(manuscript, "ieee-software")
    assert result["prefilter_passed"]
    assert next(item for item in result["items"] if item["id"] == "citation_references")["status"] == "passed"
    assert manuscript.read_bytes() == original


def test_numeric_citation_gate_preserves_examples_and_does_not_promote_other_editorial_findings(manuscript):
    text = ARTICLE.replace("## References", """Additional examples use (1, 4), `[3-1]`, and [[1–999999999]](https://example.org/range).
The [1,,2][example] link and Figure 9 require separate editorial review.

```text
[1-]
```

## References""", 1) + "\n## Appendix\n[example]: https://example.org/example\n"
    manuscript.write_text(text, encoding="utf-8")
    original = manuscript.read_bytes()
    result = exporter.preflight(manuscript, "ieee-software")
    assert result["prefilter_passed"]
    assert next(item for item in result["items"] if item["id"] == "citation_references")["status"] == "passed"
    assert manuscript.read_bytes() == original


def test_numeric_citation_gate_checks_appendices_after_references(manuscript):
    manuscript.write_text(ARTICLE + "\n## Appendix\nThe extra result uses [9].\n", encoding="utf-8")
    result = exporter.preflight(manuscript, "ieee-software")
    assert not result["prefilter_passed"]
    row = next(item for item in result["items"] if item["id"] == "citation_references")
    assert row["status"] == "failed" and "[9]" in row["reason"]


@pytest.mark.parametrize("citation", ["[1, 4]", "[1–999999999]", "[1, **4**]", "[1,\n4]"])
def test_numeric_citation_gate_fails_compliance_with_actual_docx(manuscript, tmp_path, monkeypatch, citation):
    """Real Pandoc/DOCX; only native Word counts and PDF rasterization are stubbed."""
    text = ARTICLE.replace("first wrote it. [1]", "first wrote it. " + citation)
    text = text.split("## References", 1)[0] + "## References\n\n" + "\n\n".join(
        f"[{number}] Example Authors, Retained source {number}, 2025." for number in range(1, 4)) + "\n"
    manuscript.write_text(text, encoding="utf-8")
    original = manuscript.read_bytes()
    docx, pdf = tmp_path / "actual.docx", tmp_path / "synthetic-native.pdf"
    receipt = converter.convert_docx(manuscript, docx, venue_id="ieee-software", pandoc=str(_real_pandoc()))
    pdf.write_bytes(b"Synthetic PDF fixture; native Word and rasterization are not exercised")
    docx_bytes = docx.read_bytes()
    docx_sha = exporter.digest_file(docx)
    receipts = {"docx": receipt, "pdf": {
        "input_sha256": exporter.digest_file(manuscript), "output_sha256": exporter.digest_file(pdf),
        "official_template": receipt["official_template"], "source_docx_sha256": docx_sha,
        "word_rendering": {"source_docx_sha256": docx_sha}}}
    monkeypatch.setattr(templates, "measure_word", lambda _: {"metrics": {
        "body_words": 300, "body_table_words": 0, "body_tables": 0, "body_figures": 0,
        "abstract_words": 10, "reference_heading_found": True, "reference_count": 3}})
    monkeypatch.setattr(checks, "render_pdf_pages", lambda *_: {
        "automatic_checks": True, "issues": [], "page_count": 1, "pages": []})
    result = checks.compliance_report(manuscript, docx, "ieee-software", pdf=pdf,
                                      qa_root=tmp_path / "pages", conversion_receipts=receipts)
    assert not result["content_format_passed"]
    row = next(item for item in result["items"] if item["id"] == "citation_references")
    assert row["status"] == "failed" and row["reason"] in result["blockers"]
    assert manuscript.read_bytes() == original and docx.read_bytes() == docx_bytes


def test_author_input_requires_real_typed_fields(tmp_path):
    assert author_facts._explicit_author({"given_name": "A", "family_name": "B"})["display_name"] == "A B"
    assert author_facts._explicit_author({"orcid": "0009-0009-8671-9967"})["orcid"] == "0009-0009-8671-9967"
    for value in [[], {"email": "invalid"}, {"orcid": "0009-0009-8671-9968"},
                  {"approved": True}, {"display_name": 123}, {"display_name": "A\u2028"},
                  {"biography_details": {"role": 4}}]:
        with pytest.raises(ValueError):
            author_facts._explicit_author(value)


@pytest.mark.parametrize("value", [
    {"display_name": "A\x00B"},
    {"given_name": "A\vB"},
    {"affiliation": "Lab\nTown"},
    {"email": "person@example.org\t"},
    {"biography": "First\fSecond"},
    {"biography_details": {"role": "A\x00B"}},
    {"biography_details": {"role": "A\vB"}},
    {"biography_details": {"role": "A\x7fB"}},
    {"biography_details": {"role\x00": "Researcher"}},
])
def test_author_control_characters_are_rejected_before_trimming(value):
    with pytest.raises(ValueError, match="control character"):
        author_facts._explicit_author(value)


def test_biography_allows_only_normal_multiline_control_characters():
    result = author_facts._explicit_author({
        "given_name": " A ", "family_name": " B ",
        "biography": " First line\nSecond line\r\nThird\tpart ",
        "biography_details": {"role": " First\nSecond\tpart "},
    })
    assert result["display_name"] == "A B"
    assert result["biography"] == "First line\nSecond line\r\nThird\tpart"
    assert result["biography_details"]["role"] == "First\nSecond\tpart"


def test_same_multi_author_profile_reaches_preflight_and_export_without_losing_coauthors(manuscript, tmp_path, monkeypatch):
    import submission_support
    profile = tmp_path / "profile.json"
    alice = {"display_name": "Alice Research", "affiliation": "Synthetic Lab A", "email": "alice@example.org",
             "orcid": "0009-0009-8671-9967", "biography": "Alice studies software maintenance.",
             "biography_details": {key: "Synthetic supplied fact for " + key for key in ("role", "location", "research_interests", "highest_degree", "degree_institution", "professional_membership")}}
    profile.write_text(json.dumps({"authors": [{"id": "alice", "author": alice},
                                               {"id": "bob", "author": {"display_name": "Bob Scientist"}}],
                                   "order": ["bob", "alice"], "corresponding_author": "alice", "funding": None, "conflicts": None}), encoding="utf-8")
    prepared = tmp_path / "prepared"
    result = submission_support.prepare_authors(profile, manuscript, prepared)
    assert "bob: biography_details.highest_degree" in result["missing_supplied_fields"]
    check = exporter.preflight(prepared / "manuscript.md", "ieee-software", profile=prepared / "authors.json")
    assert check["author_metadata"]["order"] == ["bob", "alice"]
    bob, alice = check["metrics"]["authors"]
    assert bob["id"] == "bob" and "affiliation" in bob["missing_fields"]
    assert "biography_details.highest_degree" in bob["missing_fields"]
    assert alice["id"] == "alice" and alice["supplied_fields_complete"]
    assert alice["supplied_biography_in_manuscript"]
    assert not bob["missing_byline_values"] and not alice["missing_byline_values"]
    assert not check["submission_ready"]
    _mock_native_export(monkeypatch)
    original_report = exporter.compliance_report
    def report(*args, **kwargs):
        assert kwargs["author_metadata"]["order"] == ["bob", "alice"]
        return original_report(*args, **kwargs)
    monkeypatch.setattr(exporter, "compliance_report", report)
    output = tmp_path / "export"
    exporter.export(prepared / "manuscript.md", "ieee-software", output, profile=prepared / "authors.json")
    assert (output / "authors.json").read_bytes() == (prepared / "authors.json").read_bytes()
    provenance = json.loads((output / "provenance.json").read_text())
    assert [entry["id"] for entry in provenance["author_metadata"]["authors"]] == ["bob", "alice"]


def test_coauthor_metadata_does_not_hide_a_missing_rendered_byline(manuscript, tmp_path):
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"authors": [{"id": "bob", "author": {"display_name": "Bob Scientist", "email": "bob@example.org"}}],
                                   "order": ["bob"]}), encoding="utf-8")
    check = exporter.preflight(manuscript, "ieee-software", profile=profile)
    row = check["metrics"]["authors"][0]
    assert set(row["missing_byline_values"]) == {"display_name", "email"}
    assert next(item for item in check["items"] if item["id"] == "author_profile_binding")["status"] == "pending"


def _real_pandoc():
    try:
        binary = converter.pandoc_binary()
        converter.pandoc_version(binary)
        return binary
    except ValueError as exc:
        if os.environ.get("CI", "").casefold() == "true":
            pytest.fail("CI requires the actual Pandoc conversion regressions: " + str(exc))
        pytest.skip("An installed Pandoc is required for the actual native conversion regression")


def test_ci_cannot_skip_a_broken_pandoc_installation(monkeypatch):
    monkeypatch.setenv("CI", "true")
    def unavailable():
        raise ValueError("Broken discovery")
    monkeypatch.setattr(converter, "pandoc_binary", unavailable)
    with pytest.raises(pytest.fail.Exception, match="CI requires"):
        _real_pandoc()


def test_conversion_rejects_a_python_executable_without_creating_docx(manuscript, tmp_path):
    target = tmp_path / "wrong.docx"
    with pytest.raises(ValueError, match="identify itself as Pandoc"):
        converter.convert_docx(manuscript, target, venue_id="ieee-software", pandoc=sys.executable)
    assert not target.exists()


@pytest.mark.parametrize("scope", ["native", "docx", "incomplete_docx"])
def test_prepared_author_manuscript_exports_real_docx_with_explicit_resource_dir(manuscript, tmp_path, monkeypatch, capsys, scope):
    import submission_support
    import zipfile
    from docx import Document
    from PIL import Image
    binary = _real_pandoc()
    manuscript.write_text(ARTICLE.replace("## References", "![A relative image](figure.png)\n\n## References", 1),
                          encoding="utf-8")
    if scope == "incomplete_docx":
        manuscript.write_text(manuscript.read_text(encoding="utf-8").replace(
            "Keywords: maintenance; configuration; ownership", ""), encoding="utf-8")
    figure = tmp_path / "figure.png"
    Image.new("RGB", (480, 120), "navy").save(figure)
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"authors": [{"id": "alice", "author": {
        "display_name": "Alice Research", "affiliation": "Lab A", "email": "alice@example.org",
        "biography": "Studies software."}, "contributions": ["Writing"]}], "order": ["alice"]}), encoding="utf-8")
    original = {path: path.read_bytes() for path in (manuscript, profile, figure)}
    prepared = tmp_path / "prepared"
    submission_support.prepare_authors(profile, manuscript, prepared)
    prepared_manuscript, prepared_profile = prepared / "manuscript.md", prepared / "authors.json"
    original.update({path: path.read_bytes() for path in (prepared_manuscript, prepared_profile)})
    assert not (prepared / "figure.png").exists()
    sentinel = "Native Word intentionally not run"
    word_calls = []
    def stop_before_word(docx, pdf, **kwargs):
        word_calls.append((docx, pdf))
        raise ValueError(sentinel)
    monkeypatch.setattr(exporter, "word_pdf", stop_before_word)
    if scope != "native":
        def no_native_report(*args, **kwargs):
            pytest.fail("DOCX-only export must not invoke native Word compliance checks")
        monkeypatch.setattr(exporter, "compliance_report", no_native_report)
    output = tmp_path / "export"
    result = exporter.main(["export", "--manuscript", str(prepared_manuscript), "--profile", str(prepared_profile),
                            "--venue", "ieee-software", "--output-dir", str(output), "--pandoc", str(binary),
                            "--resource-dir", str(tmp_path)] + (["--docx-only"] if scope != "native" else []))
    captured = capsys.readouterr()
    if scope == "native":
        assert result == 2
        assert json.loads(captured.err)["error"] == sentinel
    else:
        assert result == (1 if scope == "incomplete_docx" else 0)
        assert not captured.err
        actual = json.loads(captured.out)
        assert actual["pdf"] is None and not actual["native_word_measured"]
        assert not actual["content_format_passed"] and not actual["submission_ready"]
        assert actual["visual_review_status"] == "pending"
        report = json.loads((output / "format-report.json").read_text(encoding="utf-8"))
        assert report["mode"] == "skill_docx_export"
        assert report["word_measurement"] is None and report["page_qa"] is None
        assert report["binding"]["markdown_sha256"] == exporter.digest_file(prepared_manuscript)
        assert report["binding"]["docx_sha256"] == exporter.digest_file(Path(actual["docx"]))
        assert not report["content_format_passed"] and not report["submission_ready"]
        assert report["blockers"] if scope == "incomplete_docx" else not report["blockers"]
        receipts = json.loads((output / "conversion-receipts.json").read_text(encoding="utf-8"))
        assert set(receipts) == {"docx"}
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        assert {row["path"] for row in manifest["files"]} == {
            path.name for path in output.iterdir() if path.name != "manifest.json"}
        assert all(exporter.digest_file(output / row["path"]) == row["sha256"] for row in manifest["files"])
        assert (output / "manuscript.md").read_bytes() == prepared_manuscript.read_bytes()
    docx, pdf = output / "manuscript-ieee-software.docx", output / "manuscript-ieee-software.pdf"
    assert word_calls == ([(docx, pdf)] if scope == "native" else [])
    document = Document(docx)
    assert len(document.inline_shapes) == 1
    assert document.inline_shapes[0].width < 4 * 914400
    assert document.inline_shapes[0].width == 4 * document.inline_shapes[0].height
    assert "Alice Research | Lab A | alice@example.org" in [paragraph.text for paragraph in document.paragraphs]
    with zipfile.ZipFile(docx) as archive:
        images = [archive.read(name) for name in archive.namelist()
                  if name.startswith("word/media/") and name.lower().endswith(".png")]
    assert original[figure] in images
    assert all(path.read_bytes() == contents for path, contents in original.items())
    assert not pdf.exists()


def test_docx_only_rejects_joss_without_creating_output(manuscript, tmp_path, capsys):
    output = tmp_path / "joss-docx"
    assert exporter.main(["export", "--manuscript", str(manuscript), "--venue", "joss",
                          "--output-dir", str(output), "--docx-only"]) == 2
    assert "--docx-only is for Word venues" in json.loads(capsys.readouterr().err)["error"]
    assert not output.exists()


@pytest.mark.parametrize("kind", ["relative", "missing", "file"])
def test_conversion_rejects_invalid_resource_directory_before_docx(manuscript, tmp_path, kind):
    resource_dir = {"relative": Path("relative-media"), "missing": tmp_path / "missing", "file": manuscript}[kind]
    output = tmp_path / "invalid-resource.docx"
    with pytest.raises(ValueError, match="Resource directory must be an existing absolute directory"):
        converter.convert_docx(manuscript, output, venue_id="ieee-software", resource_dir=resource_dir)
    assert not output.exists()


def test_real_pandoc_hides_only_author_controls_and_preserves_code_and_relative_media(tmp_path):
    from docx import Document
    from PIL import Image
    binary = _real_pandoc()
    source = tmp_path / "article.md"
    start, end = "<!-- paper-factory:authors:start -->", "<!-- paper-factory:authors:end -->"
    front = "# Shared configuration cleanup\n\n" + start + "\n\nAlice Example | alice@example.org\n\n" + end + "\n\n"
    body = ARTICLE.split("## Abstract", 1)[1]
    examples = ("\n\n## Control marker examples\n\nInline example: `" + start + "` is code.\n\n"
                "```html\n" + start + "\n" + end + "\n```\n\n"
                "Arbitrary <!-- unrelated comment --> prose survives.\n\n"
                "A paragraph containing " + end + " remains literal prose.\n\n![A relative image](figure.png)\n")
    source.write_text(front + "## Abstract" + body + examples, encoding="utf-8")
    Image.new("RGB", (12, 12), "navy").save(tmp_path / "figure.png")
    original = source.read_bytes()
    output = tmp_path / "actual.docx"
    receipt = converter.convert_docx(source, output, venue_id="ieee-software", pandoc=str(binary))
    document = Document(output)
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    assert "Alice Example | alice@example.org" in paragraphs
    assert start not in paragraphs and end not in paragraphs
    assert "Inline example: " + start + " is code." in paragraphs
    assert start + "\n" + end in paragraphs
    assert "Arbitrary <!-- unrelated comment --> prose survives." in paragraphs
    assert "A paragraph containing " + end + " remains literal prose." in paragraphs
    assert len(document.inline_shapes) == 1
    assert source.read_bytes() == original
    assert receipt["input_sha256"] == exporter.digest_file(source)
    assert receipt["working_directory"] == str(tmp_path.resolve())
    import hashlib
    marker_receipt = receipt["author_control_markers"]
    assert marker_receipt["filter_sha256"] == hashlib.sha256(marker_receipt["filter_source"].encode()).hexdigest()


def test_real_pandoc_does_not_hide_unpaired_or_inline_code_only_marker(tmp_path):
    from docx import Document
    binary = _real_pandoc()
    start = "<!-- paper-factory:authors:start -->"
    source = tmp_path / "unpaired.md"
    source.write_text("# Title\n\n" + start + "\n\n`<!-- paper-factory:authors:end -->`\n\n## Abstract\n\nA bounded example.\n\n## Analysis\n\nAn example is preserved.\n", encoding="utf-8")
    output = tmp_path / "unpaired.docx"
    converter.convert_docx(source, output, venue_id="ieee-software", pandoc=str(binary))
    paragraphs = [paragraph.text for paragraph in Document(output).paragraphs]
    assert start in paragraphs
    assert "<!-- paper-factory:authors:end -->" in paragraphs


@pytest.mark.parametrize("missing", [True, False])
def test_real_pandoc_cannot_silently_deliver_a_missing_or_invalid_figure(tmp_path, missing):
    binary = _real_pandoc()
    source = tmp_path / "article.md"
    source.write_text(ARTICLE + "\n![A necessary figure](figure.png)\n", encoding="utf-8")
    if not missing:
        (tmp_path / "figure.png").write_bytes(b"This is not an image.")
    original = source.read_bytes()
    with pytest.raises(ValueError, match="Pandoc failed" if missing else "unreadable raster image") as failure:
        converter.convert_docx(source, tmp_path / "incomplete.docx", venue_id="ieee-software", pandoc=str(binary))
    if missing:
        assert "figure.png" in str(failure.value)
    assert source.read_bytes() == original


def test_pandoc_resolves_only_an_existing_installation(tmp_path, monkeypatch):
    binary = tmp_path / "pandoc.exe"
    binary.write_bytes(b"test executable")
    assert converter.pandoc_binary(str(binary)) == binary.resolve()
    with pytest.raises(ValueError):
        converter.pandoc_binary("relative/pandoc")
    monkeypatch.delenv("PYPANDOC_PANDOC", raising=False)
    monkeypatch.setattr(converter.shutil, "which", lambda _: None)
    def unavailable():
        raise OSError("not installed")
    monkeypatch.setitem(sys.modules, "pypandoc", SimpleNamespace(get_pandoc_path=unavailable))
    with pytest.raises(ValueError, match="Pandoc is unavailable"):
        converter.pandoc_binary()


def test_existing_output_is_never_replaced(manuscript, tmp_path, monkeypatch):
    folder = tmp_path / "existing"
    folder.mkdir()
    sentinel = folder / "keep.txt"
    sentinel.write_bytes(b"original")
    monkeypatch.setattr(exporter, "pandoc_binary", lambda _: manuscript)
    with pytest.raises(FileExistsError):
        exporter.export(manuscript, "ieee-software", folder)
    assert sentinel.read_bytes() == b"original"
    assert list(folder.iterdir()) == [sentinel]


def _mock_native_export(monkeypatch, *, mutate_source=None):
    monkeypatch.setattr(exporter, "pandoc_binary", lambda _: Path(sys.executable))
    monkeypatch.setattr(exporter, "image_sources", lambda *args, **kwargs: {})
    _, original = templates.official_template("ieee-software")
    def convert(source, output, **kwargs):
        digest = exporter.digest_file(source)
        output.write_bytes(b"native word fixture")
        if mutate_source is not None:
            mutate_source.write_text(ARTICLE + "\nChanged\n", encoding="utf-8")
        return {"input_sha256": digest, "output_sha256": exporter.digest_file(output),
                "official_template": original}
    def render(source, output, **kwargs):
        output.write_bytes(b"%PDF-native fixture")
        return {"source_docx_sha256": exporter.digest_file(source), "visible": False, "read_only": True}
    monkeypatch.setattr(exporter, "convert_docx", convert)
    monkeypatch.setattr(exporter, "word_pdf", render)
    def report(*args, **kwargs):
        receipts = kwargs["conversion_receipts"]
        assert receipts["pdf"]["source_docx_sha256"] == exporter.digest_file(args[1])
        return {"content_format_passed": True, "submission_ready": False,
                "page_qa": {"visual_review_status": "pending"}}
    monkeypatch.setattr(exporter, "compliance_report", report)


def test_export_binds_real_bytes_and_never_infers_approval(manuscript, tmp_path, monkeypatch):
    _mock_native_export(monkeypatch)
    before = manuscript.read_bytes()
    output = tmp_path / "new"
    result = exporter.export(manuscript, "ieee-software", output)
    assert result["content_format_passed"] and not result["submission_ready"]
    assert (output / "manuscript.md").read_bytes() == before == manuscript.read_bytes()
    provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["model_calls_made_by_tool"] == 0
    assert provenance["author_approval_inferred"] is False
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert all(exporter.digest_file(output / row["path"]) == row["sha256"] for row in manifest["files"])


@pytest.mark.parametrize("docx_only", [False, True])
@pytest.mark.parametrize("changed_copy", [False, True])
def test_changed_source_fails_but_retains_diagnostic_output(manuscript, tmp_path, monkeypatch, docx_only, changed_copy):
    output = tmp_path / "new"
    retained = output / "manuscript.md"
    _mock_native_export(monkeypatch, mutate_source=retained if changed_copy else manuscript)
    with pytest.raises(ValueError, match="changed during direct export"):
        exporter.export(manuscript, "ieee-software", output, docx_only=docx_only)
    assert (manuscript if changed_copy else retained).read_text(encoding="utf-8") == ARTICLE
    assert (output / "manuscript-ieee-software.docx").is_file()
    assert not (output / "provenance.json").exists()


@pytest.mark.parametrize("venue", ["ieee-software", "ieee-security-privacy"])
def test_retained_publisher_styles_columns_and_citations(tmp_path, venue):
    """Exercise actual template mappings, without Pandoc or Microsoft Word."""
    from docx import Document
    from docx.oxml.ns import qn
    template, record = templates.official_template(venue)
    assert exporter.digest_file(template) == record["sha256"]
    doc = Document(template)
    for child in list(doc._element.body):
        if child.tag != qn("w:sectPr"):
            doc._element.body.remove(child)
    for text, style in [("A concrete maintenance decision", "Heading 1"),
                        ("Abstract", "Heading 2"), ("A bounded static example.", "Normal"),
                        ("Keywords: one; two; three", "Normal"), ("Introduction", "Heading 2"),
                        ("Source supports this statement. [1]", "Normal"),
                        ("References", "Heading 2"), ("[1] Authors, A source, 2025.", "Normal")]:
        doc.add_paragraph(text, style)
    reference_heading = next(p for p in doc.paragraphs if p.text == "References")
    caption = doc.add_paragraph("Table 1. Retained seven-column content")
    reference_heading._p.addprevious(caption._p)
    table = doc.add_table(rows=2, cols=7)
    for row_index, row in enumerate(table.rows):
        for column_index, cell in enumerate(row.cells):
            cell.text = f"r{row_index}c{column_index}"
    reference_heading._p.addprevious(table._tbl)
    expected_cells = [[cell.text for cell in row.cells] for row in table.rows]
    path = tmp_path / (venue + ".docx")
    doc.save(path)
    proof = templates.apply_official_styles(path, template, citation_style=templates.template_record(venue)["citation_style"])
    structure = checks._native_structure(path, venue == "ieee-software")
    assert not structure["issues"]
    assert structure["reference_count"] == 1
    assert proof["citation_typography"]["callout_groups_formatted"] == 1
    checked = Document(path)
    assert checked.paragraphs[0].style.name == "Title_document"
    assert any(s._sectPr.find(qn("w:cols")).get(qn("w:num")) == "2" for s in checked.sections)
    assert len(checked.tables) == 1 and len(checked.tables[0].columns) == 7
    assert [[cell.text for cell in row.cells] for row in checked.tables[0].rows] == expected_cells
    assert checked.tables[0].rows[0]._tr.get_or_add_trPr().find(qn("w:tblHeader")) is not None
    assert next(p for p in checked.paragraphs if p.text.startswith("Table 1.")).style.name == "TableCaption"


@pytest.mark.parametrize("venue", ["ieee-software", "ieee-security-privacy"])
def test_real_pandoc_grouped_citations_preserve_ranges_and_protected_content(tmp_path, venue, monkeypatch):
    import zipfile
    from xml.etree import ElementTree
    from docx import Document
    from docx.oxml.ns import qn
    binary = _real_pandoc()
    software = venue == "ieee-software"
    cases = [
        ("Comma evidence. [1, 2]", "Comma evidence.1,2", "Comma evidence [1], [2].", "1,2"),
        ("Semicolon evidence [1; 3].", "Semicolon evidence.1,3", "Semicolon evidence [1], [3].", "1,3"),
        ("Hyphen evidence. [1-3]", "Hyphen evidence.1–3", "Hyphen evidence [1], [2], [3].", "1–3"),
        ("En-dash evidence. [1–3]", "En-dash evidence.1–3", "En-dash evidence [1], [2], [3].", "1–3"),
        ("Mixed evidence. [1, 2–3]", "Mixed evidence.1,2–3", "Mixed evidence [1], [2], [3].", "1,2–3"),
        ("Footnoted evidence [1, 2][^scope].", "Footnoted evidence.1,2", "Footnoted evidence [1], [2].", "1,2"),
        ("**Split evidence.** [1, **2**; *3*] *retained emphasis*",
         "Split evidence.1,2,3 retained emphasis", "Split evidence [1], [2], [3]. retained emphasis", "1,2,3"),
    ]
    controls = ("Unknown evidence. [1, 4]\n\nWide range evidence. [1–999999999]\n\n"
                "Inline code. `[1, 2]` and `[1–3]`.\n\n"
                "Linked evidence. [[1, 2]](https://example.org/group) and [[1–3]](https://example.org/range).\n\n"
                "```text\n[1, 2]\n[1–3]\n```\n\n"
                "+-----------------------+\n"
                "| Python example        |\n"
                "+=======================+\n"
                "| ```python             |\n"
                "| result = [1, 2]       |\n"
                "| ```                   |\n"
                "+-----------------------+")
    source = tmp_path / "groups.md"
    source.write_text(ARTICLE.replace("A shared requirement may survive the command that first wrote it. [1]",
                                      "\n\n".join(case[0] for case in cases) + "\n\n" + controls)
                     .replace("[1] Example Authors, A retained source, 2025. https://example.org/source",
                              "\n\n".join(f"[{number}] Authors, Source {number}, 2025." for number in range(1, 4)))
                     + "\n[^scope]: This exact footnote text must remain reachable.\n",
                      encoding="utf-8")
    original = source.read_bytes()
    output = tmp_path / "groups.docx"
    code_runs = []
    footnote_ids = []
    apply_styles = converter.apply_official_styles

    def capture_content_then_apply(path, reference, **kwargs):
        document = Document(path)
        footnote_ids.extend(document._element.xpath(".//w:footnoteReference/@w:id"))
        assert len(footnote_ids) == 1
        code = document.tables[0].cell(1, 0).paragraphs[0]
        assert code.style.name == "Source Code" and code.text == "result = [1, 2]"
        code_runs.extend(run._r.xml for run in code.runs)
        return apply_styles(path, reference, **kwargs)

    monkeypatch.setattr(converter, "apply_official_styles", capture_content_then_apply)
    receipt = converter.convert_docx(source, output, venue_id=venue, pandoc=str(binary))
    document = Document(output)
    code = document.tables[0].cell(1, 0).paragraphs[0]
    assert code.style.name == "Source Code" and code.text == "result = [1, 2]"
    assert [run._r.xml for run in code.runs] == code_runs
    paragraphs = {paragraph.text: paragraph for paragraph in document.paragraphs}
    for _, superscript_text, bracketed_text, numbers in cases:
        paragraph = paragraphs[superscript_text if software else bracketed_text]
        superscript = "".join(run.text for run in paragraph.runs if run.font.superscript)
        assert superscript == (numbers if software else "")
    footnoted = paragraphs["Footnoted evidence.1,2" if software else "Footnoted evidence [1], [2]."]
    assert footnoted._p.xpath(".//w:footnoteReference/@w:id") == footnote_ids
    with zipfile.ZipFile(output) as archive:
        notes = ElementTree.fromstring(archive.read("word/footnotes.xml"))
    note_texts = {note.get(qn("w:id")): "".join(node.text or "" for node in note.iter(qn("w:t"))).strip()
                  for note in notes.findall(qn("w:footnote"))}
    assert note_texts[footnote_ids[0]] == "This exact footnote text must remain reachable."
    proof = receipt["official_template"]["citation_typography"]
    assert proof["callout_groups_formatted"] == len(cases)
    assert proof["unknown_reference_numbers_preserved"] == ["4", "999999999"]
    assert "Unknown evidence. [1, 4]" in paragraphs
    assert "Wide range evidence. [1–999999999]" in paragraphs
    assert "Inline code. [1, 2] and [1–3]." in paragraphs
    assert "[1, 2]\n[1–3]" in paragraphs
    linked = paragraphs["Linked evidence. [1, 2] and [1–3]."]
    assert ["".join(link.xpath(".//w:t/text()")) for link in linked._p.xpath("./w:hyperlink")] == ["[1, 2]", "[1–3]"]
    assert [document.part.rels[link.get(qn("r:id"))].target_ref for link in linked._p.xpath("./w:hyperlink")] == [
        "https://example.org/group", "https://example.org/range"]
    split = paragraphs[cases[-1][1 if software else 2]]
    assert any("Split evidence" in run.text and run.bold for run in split.runs)
    assert any("retained emphasis" in run.text and run.italic for run in split.runs)
    assert source.read_bytes() == original
    assert not checks._native_structure(output, software)["issues"]

    # A missed group must fail native QA, including citations split across runs.
    target = paragraphs[cases[0][1 if software else 2]]
    for prefix, citation, suffix in [("Grouped evidence ", "[1, 2]", "."),
                                     ("Range evidence. ", "[1–3]", "")]:
        target.text = prefix
        target.add_run(citation[:2])
        target.add_run(citation[2:]).italic = True
        target.add_run(suffix)
        document.save(output)
        issues = checks._native_structure(output, software)["issues"]
        assert any(("superscript typography" if software else "separate brackets") in issue for issue in issues)
        if not software:
            assert any("after terminal punctuation" in issue for issue in issues) is bool(prefix.endswith(". "))


@pytest.mark.parametrize("word_count,paragraph_count", [(1, 1), (1, 4), (4, 1), (4, 4)])
def test_native_reference_counts_must_match_canonical_entries(manuscript, tmp_path, monkeypatch, word_count, paragraph_count):
    """Collapsed bibliography paragraphs must fail even when native counts fit the limit."""
    from docx import Document
    from docx.oxml.ns import qn
    references = [f"[{number}] Example Authors, Retained source {number}, 2025." for number in range(1, 5)]
    manuscript.write_text(ARTICLE.split("## References", 1)[0] + "## References\n\n" +
                          "\n".join(references) + "\n", encoding="utf-8")
    template, record = templates.official_template("ieee-software")
    doc = Document(template)
    for child in list(doc._element.body):
        if child.tag != qn("w:sectPr"):
            doc._element.body.remove(child)
    for text, style in [("A concrete maintenance decision", "Heading 1"),
                        ("Abstract", "Heading 2"), ("A bounded static example.", "Normal"),
                        ("Keywords: one; two; three", "Normal"), ("Introduction", "Heading 2"),
                        ("Source supports this statement. [1]", "Normal"), ("References", "Heading 2")]:
        doc.add_paragraph(text, style)
    for entry in references if paragraph_count == 4 else [" ".join(references)]:
        doc.add_paragraph(entry, "Normal")
    native_docx = tmp_path / "native.docx"
    doc.save(native_docx)
    templates.apply_official_styles(native_docx, template, citation_style=record["citation_style"])
    monkeypatch.setattr(templates, "measure_word", lambda _: {"metrics": {
        "body_words": 300, "body_table_words": 0, "body_tables": 0, "body_figures": 0,
        "abstract_words": 10, "reference_heading_found": True, "reference_count": word_count}})
    native_pdf = tmp_path / "native.pdf"
    native_pdf.write_bytes(b"PDF fixture; rendering is mocked")
    docx_sha = exporter.digest_file(native_docx)
    receipts = {name: {"input_sha256": exporter.digest_file(manuscript),
                       "output_sha256": exporter.digest_file(path), "official_template": record}
                for name, path in (("docx", native_docx), ("pdf", native_pdf))}
    receipts["pdf"].update(source_docx_sha256=docx_sha, word_rendering={"source_docx_sha256": docx_sha})
    monkeypatch.setattr(checks, "render_pdf_pages", lambda *_: {
        "automatic_checks": True, "issues": [], "page_count": 1, "pages": []})
    result = checks.compliance_report(manuscript, native_docx, "ieee-software", pdf=native_pdf,
                                      qa_root=tmp_path / "pages", conversion_receipts=receipts)
    row = next(item for item in result["items"] if item["id"] == "reference_count_consistency")
    expected_pass = word_count == paragraph_count == 4
    assert row["status"] == ("passed" if expected_pass else "failed")
    assert result["content_format_passed"] is expected_pass
    assert result["metrics"]["reference_count"] == 4
    assert result["metrics"]["native_structure"]["reference_count"] == paragraph_count
    if not expected_pass:
        assert row["reason"] in result["blockers"]


@pytest.mark.parametrize("venue", ["ieee-software", "ieee-security-privacy"])
@pytest.mark.parametrize("image_width_inches,image_height_inches", [(1, 0.25), (6, 1.5), (1, 12)])
def test_body_images_fit_publisher_columns_without_changing_front_table_or_media(tmp_path, venue, image_width_inches, image_height_inches):
    from docx import Document
    from docx.oxml.ns import qn
    from docx.shared import Inches, Twips
    from PIL import Image
    import zipfile

    template, _ = templates.official_template(venue)
    document = Document(template)
    for child in list(document._element.body):
        if child.tag != qn("w:sectPr"):
            document._element.body.remove(child)
    image = tmp_path / "figure.png"
    Image.new("RGB", (480, 120), "navy").save(image)
    body_image = tmp_path / "body-figure.png"
    Image.new("RGB", (round(image_width_inches * 80), round(image_height_inches * 80)), "navy").save(body_image)
    document.add_paragraph("A concrete image layout", "Heading 1")
    front = document.add_paragraph().add_run().add_picture(str(image), width=Inches(4.5))
    document.add_paragraph("Abstract", "Heading 2")
    document.add_paragraph("A bounded image layout example.", "Normal")
    document.add_paragraph("Introduction", "Heading 2")
    body = document.add_paragraph().add_run().add_picture(str(body_image), width=Inches(image_width_inches))
    prose = document.add_paragraph("An inline image within prose keeps its paragraph indent.", "Normal")
    prose.paragraph_format.first_line_indent = Inches(0.25)
    prose_image = prose.add_run().add_picture(str(image), width=Inches(1))
    table = document.add_table(rows=1, cols=1)
    cell = table.cell(0, 0).paragraphs[0].add_run().add_picture(str(image), width=Inches(4.5))
    document.add_paragraph("References", "Heading 2")
    document.add_paragraph("[1] Authors, A retained source, 2025.", "Normal")
    before = [(shape.width, shape.height) for shape in (front, body, cell)]
    path = tmp_path / "images.docx"
    document.save(path)
    with zipfile.ZipFile(path) as archive:
        original_media = {name: archive.read(name) for name in archive.namelist() if name.startswith("word/media/")}

    templates.apply_official_styles(path, template, citation_style=templates.template_record(venue)["citation_style"])

    checked = Document(path)
    front, body, prose_image, cell = checked.inline_shapes
    section = next(s for s in reversed(list(checked.sections))
                   if s._sectPr.find(qn("w:cols")).get(qn("w:num")) == "2")
    gap = Twips(int(section._sectPr.find(qn("w:cols")).get(qn("w:space"))))
    column_width = (section.page_width - section.left_margin - section.right_margin - gap) // 2
    page_height = section.page_height - section.top_margin - section.bottom_margin
    assert body.width <= column_width
    assert body.height <= page_height
    assert abs(body.width - body.height * image_width_inches / image_height_inches) <= 2
    picture_only_paragraph = next(p for p in checked.paragraphs
                                  if not p.text.strip() and p._p.xpath(".//wp:inline")
                                  and p.style.name == "Para")
    assert picture_only_paragraph.paragraph_format.first_line_indent == 0
    prose = next(p for p in checked.paragraphs if p.text.startswith("An inline image within prose"))
    assert prose.paragraph_format.first_line_indent == Inches(0.25)
    assert prose_image.width == Inches(1)
    if before[1][0] <= column_width and before[1][1] <= page_height:
        assert (body.width, body.height) == before[1]
    else:
        assert body.width < before[1][0] and body.height < before[1][1]
    assert (front.width, front.height) == before[0]
    assert (cell.width, cell.height) == before[2]
    with zipfile.ZipFile(path) as archive:
        assert {name: archive.read(name) for name in archive.namelist() if name.startswith("word/media/")} == original_media
        assert image.read_bytes() in original_media.values()
        assert body_image.read_bytes() in original_media.values()


def test_skill_copy_preflight_works_without_old_checkout(tmp_path):
    isolated = tmp_path / "standalone-skill"
    (isolated / "scripts").mkdir(parents=True)
    for path in (ROOT / "scripts").glob("*.py"):
        if path.name in {"export_manuscript.py", "_author_profile.py", "editorial_checks.py"} or path.name.startswith("_publication_"):
            shutil.copyfile(path, isolated / "scripts" / path.name)
    shutil.copytree(ROOT / "assets" / "templates", isolated / "assets" / "templates")
    manuscript = tmp_path / "input.md"
    manuscript.write_text(ARTICLE, encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PAPER_FACTORY_ROOT"}}
    env["PYTHONIOENCODING"] = "cp1252"  # Match the Windows pipe encoding that broke UTF-8 JSON consumers.
    result = subprocess.run([sys.executable, str(isolated / "scripts" / "export_manuscript.py"),
                             "preflight", "--manuscript", str(manuscript), "--venue", "ieee-software"],
                            cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["prefilter_passed"] and report["model_calls_made_by_tool"] == 0
    assert Path(report["official_template"]["path"]).is_relative_to(isolated)
    assert not (isolated / "desktop").exists() and not (isolated / "src").exists()

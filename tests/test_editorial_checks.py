"""Local editorial invariants; no network or scientific quality scoring."""

import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
editorial = importlib.import_module("editorial_checks")


def codes(result, key="structural_findings"):
    return {x["code"] for x in result[key]}


def test_numeric_citations_missing_duplicate_and_unused():
    result = editorial.check_manuscript("""# Article

The result follows [1, 3–4].

## References

[1] First source.
[1] A second label.
[2] Unused source.
[3] Third source.
""")
    assert {"citation_without_reference", "duplicate_reference_label"} <= codes(result)
    assert result["metrics"]["recognized_body_citations"] == [1, 3, 4]
    assert "reference_not_cited" in codes(result, "manual_review_suggestions")
    assert not result["scientific_merit_assessed"]


def test_code_and_links_do_not_create_body_citations():
    text = """# Article

`array[9]` and [8](https://example.org/[7]) are code and links.

```python
values[6]
```

~~~text
another[5]
~~~

A real citation [1].

## References

[1] First source.
"""
    result = editorial.check_manuscript(text)
    assert result["metrics"]["recognized_body_citations"] == [1]
    assert "citation_without_reference" not in codes(result)


@pytest.mark.parametrize("opener,closer", [("```python", "````"), ("~~~text", "~~~~~")])
def test_longer_closing_fences_hide_code_without_hiding_following_citations(opener, closer):
    result = editorial.check_manuscript(
        "# Article\n" + opener + "\narray[9]\n## References\n[8] Example only.\n" + closer +
        "\nA real citation [1].\n## References\n[1] Actual source.\n")
    assert result["metrics"]["recognized_body_citations"] == [1]
    assert result["metrics"]["reference_entries"] == 1
    assert not result["structural_findings"]


def test_inline_code_with_literal_backticks_does_not_create_citations():
    result = editorial.check_manuscript(
        "# Article\nUse ``literal `array[9]` notation``; the actual source is [1].\n"
        "## References\n[1] Actual source.\n")
    assert result["metrics"]["recognized_body_citations"] == [1]
    assert not result["structural_findings"]


def test_reference_heading_inside_code_does_not_end_the_real_body():
    result = editorial.check_manuscript("# Article\n```text\n## References\n[9] Not a reference.\n```\nReal source [1].\n## References\n[1] Source.\n")
    assert result["metrics"]["reference_entries"] == 1
    assert result["metrics"]["recognized_body_citations"] == [1]
    assert not result["structural_findings"]


def test_appendix_after_references_still_checks_citations_and_callouts():
    result = editorial.check_manuscript("""# Article
The main argument uses [1].
## References
[1] First source.
## Appendix A
The additional case requires [9] and Figure 3.
Table A1 compares the cases.
Table A1. Additional comparison.
""")
    assert result["metrics"]["reference_entries"] == 1
    assert result["metrics"]["recognized_body_citations"] == [1, 9]
    assert any(x["code"] == "citation_without_reference" and x["reference_id"] == 9
               for x in result["structural_findings"])
    assert any(x["code"] == "callout_without_caption" and "3" in x["detail"]
               for x in result["structural_findings"])
    assert result["metrics"]["table_captions"] == 1


def test_reference_style_links_and_definitions_are_not_scholarly_citations():
    result = editorial.check_manuscript("""# Article
The [8][project] link and [7][] shortcut are documentation links.
The numeric shortcut [6] is another link; actual source [1] is a citation.
An unresolved [9][unknown] is still ordinary bracketed prose.
## References
[1] Scholarly source.
## Appendix
[project]: https://example.org/project
[7]: https://example.org/seven
[6]: https://example.org/six
[5]: https://example.org/five
""")
    assert result["metrics"]["recognized_body_citations"] == [1, 9]
    assert [x["reference_id"] for x in result["structural_findings"]
            if x["code"] == "citation_without_reference"] == [9]


def test_fenced_bibliography_examples_do_not_create_entries_or_identifiers():
    result = editorial.check_manuscript("""# Article
Sources [1, 2].
## References
[1] Actual first source. doi:10.1234/first

```text
[9] Example only. doi:10.1234/first
## Example heading, not an appendix
```

[2] Actual second source. doi:10.1234/second
## Appendix
An additional discussion of [2].
""")
    assert result["metrics"]["reference_entries"] == 2
    assert result["metrics"]["recognized_body_citations"] == [1, 2]
    assert not result["structural_findings"]


def test_link_definitions_in_code_do_not_hide_real_citations():
    result = editorial.check_manuscript("""# Article
Actual source [1] and missing source [9].
```markdown
[9]: https://example.org/code-example
```
## References
[1] Actual source.
""")
    assert result["metrics"]["recognized_body_citations"] == [1, 9]
    assert any(x["code"] == "citation_without_reference" and x["reference_id"] == 9
               for x in result["structural_findings"])


def test_duplicate_doi_and_url_are_literal_relationships():
    result = editorial.check_manuscript("""# Article
Both accounts [1, 2].
## References
[1] First. https://doi.org/10.1234/example
[2] Second. doi:10.1234/EXAMPLE and https://doi.org/10.1234/example
""")
    assert {"duplicate_doi", "duplicate_reference_url"} <= codes(result)
    assert "not checked online" in result["metadata_scope"]


def test_explicit_bad_doi_and_metadata_mismatch():
    result = editorial.check_manuscript("""# Article
Sources [1, 2].
## References
[1] First title. doi:not-a-doi
[2] Second title. doi:10.1234/actual
""", [{"id": 1, "title": "First title", "doi": "bad"},
       {"id": 2, "title": "Second title", "doi": "10.1234/other", "verified_metadata": True}])
    assert {"malformed_doi", "malformed_metadata_doi", "metadata_doi_mismatch"} <= codes(result)
    assert "not verification" in result["metadata_scope"]


def test_metadata_author_year_and_url_are_literal_manual_comparisons():
    result = editorial.check_manuscript("# Article\n[1]\n## References\n[1] A. Writer, A title, 2024. https://example.org/one\n",
                                        [{"id": 1, "title": "A title", "authors": ["Alice Writer"],
                                          "year": 2025, "url": "https://example.org/two"}])
    assert {"metadata_author_not_found", "metadata_year_not_found", "metadata_url_not_printed"} <= codes(result, "manual_review_suggestions")
    assert not result["structural_findings"]


def test_duplicate_supplied_titles_and_dois():
    result = editorial.check_manuscript("""# Article
Sources [1, 2].
## References
[1] Same title.
[2] Same title.
""", [{"id": 1, "title": "Same title", "doi": "10.1234/same"},
       {"id": 2, "title": " SAME  TITLE ", "doi": "https://doi.org/10.1234/SAME"}])
    assert {"duplicate_metadata_title", "duplicate_metadata_doi"} <= codes(result)


def test_table_and_figure_calls_use_captions_not_their_own_labels():
    result = editorial.check_manuscript("""# Article
Tables 1 and 2 compare decisions. Figure 3 illustrates them.
*Table 1. First comparison.*
*Table 2. Second comparison.*
Figure 1. An unused figure.
""")
    assert result["metrics"]["table_captions"] == 2
    assert result["metrics"]["figure_captions"] == 1
    assert any(x["code"] == "callout_without_caption" and "3" in x["detail"] for x in result["structural_findings"])
    assert "caption_not_called_out" in codes(result, "manual_review_suggestions")


def test_duplicate_headings_and_captions():
    result = editorial.check_manuscript("# Article\n## Method\n## Method\nTable 1. One.\nTable 1. Two.\n")
    assert {"duplicate_heading", "duplicate_caption"} <= codes(result)


def test_acronyms_are_advisory_not_structural_failures():
    result = editorial.check_manuscript("# Article\nAn application programming interface (API) is compared with IPC.\n")
    warnings = [x["acronym"] for x in result["manual_review_suggestions"] if x["code"] == "acronym_definition_check"]
    assert "IPC" in warnings and "API" not in warnings
    assert not result["structural_findings"]


@pytest.mark.parametrize("metadata", [{}, ["bad"], [{"id": "1"}], [{"id": 0}],
                                     [{"id": 1}, {"id": 1}], [{"id": 1, "doi": 12}]])
def test_invalid_metadata_is_not_silently_treated_as_verified(metadata):
    with pytest.raises(ValueError):
        editorial.check_manuscript("# Article\n[1]\n## References\n[1] Source.\n", metadata)


def test_report_preserves_inputs_and_refuses_existing_output(tmp_path):
    manuscript = tmp_path / "article.md"
    manuscript.write_bytes(b"\xef\xbb\xbf# Article\r\nA result [1].\r\n## References\r\n[1] Source.\r\n")
    metadata = tmp_path / "references.json"
    metadata.write_text('[{"id":1,"title":"Source"}]', encoding="utf-8")
    before = manuscript.read_bytes(), metadata.read_bytes()
    output = tmp_path / "new"
    result = editorial.write_report(manuscript, output, metadata)
    assert result["structural_findings"] == 0
    assert result["network_requests"] == 0 and not result["content_rewritten"]
    assert (manuscript.read_bytes(), metadata.read_bytes()) == before
    saved = (output / "editorial-report.json").read_bytes()
    with pytest.raises(FileExistsError):
        editorial.write_report(manuscript, output, metadata)
    assert saved == (output / "editorial-report.json").read_bytes()


def test_relative_output_paths_are_rejected(tmp_path):
    source = tmp_path / "article.md"
    source.write_text("# Article", encoding="utf-8")
    with pytest.raises(ValueError, match="absolute"):
        editorial.write_report(source, Path("new-output"))


def test_cli_has_no_checkout_or_app_requirement(tmp_path):
    import shutil
    isolated = tmp_path / "skill"
    isolated.mkdir()
    for name in ["editorial_checks.py", "_publication_files.py", "_publication_text.py"]:
        shutil.copyfile(ROOT / "scripts" / name, isolated / name)
    manuscript = tmp_path / "article.md"
    manuscript.write_text("# Article\nA source [1].\n## References\n[1] Source.\n", encoding="utf-8")
    result = subprocess.run([sys.executable, str(isolated / "editorial_checks.py"), "check", "--manuscript",
                             str(manuscript), "--output-dir", str(tmp_path / "report")],
                            cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["structural_findings"] == 0

"""JOSS source packages use real Pandoc parsing and preserve supplied source bytes."""

import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import _publication_joss as joss


HEADER = """---
title: 'Research tool: a supplied example'
authors:
  - name: Alice Research
    affiliation: "1, 2"
  - name: Bob Scientist
    affiliation: [2]
affiliations:
  - index: 1
    name: Research Institute
  - index: 2
    name: Example University
date: 2 November 2026
bibliography: paper.bib
---

"""
BIBLIOGRAPHY = b"""% Preserve this supplied comment and all unmapped fields.
@article{retained,
 title = {A Retained {Research} Tool},
 author = {Researcher, Alice},
 year = {2025},
 journal = {Full Journal Name},
 volume = {12},
 pages = {1--9},
 doi = {10.1234/example},
 note = {An original field not regenerated from metadata JSON}
}
"""


def paper(words=800):
    return HEADER + "# Summary\n\n" + "supported " * words + "[@retained].\n\n" + "\n\n".join(
        "# " + heading.title() + "\n\nActual supplied analysis."
        for heading in joss.SECTIONS[1:-1]) + "\n\n# References\n"


@pytest.fixture
def sources(tmp_path):
    try:
        binary = joss.pandoc_binary()
        joss.pandoc_version(binary)
    except ValueError as exc:
        if os.environ.get("CI", "").casefold() == "true":
            pytest.fail("CI requires actual Pandoc for JOSS source checks: " + str(exc))
        pytest.skip("An installed Pandoc is required: " + str(exc))
    manuscript = tmp_path / "draft.md"
    manuscript.write_text(paper(), encoding="utf-8")
    bibliography = tmp_path / "paper.bib"
    bibliography.write_bytes(BIBLIOGRAPHY)
    return manuscript, bibliography


def test_preflight_parses_official_metadata_and_multiple_affiliations_without_writes(sources):
    manuscript, bibliography = sources
    original = manuscript.read_bytes(), bibliography.read_bytes()
    result = joss.preflight(manuscript)
    assert result["prefilter_passed"]
    assert result["official_template"]["venue_id"] == "joss"
    assert result["official_template"]["citation_style"] == "apa_author_date"
    assert result["metrics"]["authors"] == [
        {"name": "Alice Research", "affiliations": ["1", "2"], "valid": True},
        {"name": "Bob Scientist", "affiliations": ["2"], "valid": True}]
    assert result["metrics"]["citation_keys"] == ["retained"]
    assert not result["submission_ready"] and not result["publisher_pdf_rendered"]
    assert not result["author_approval_inferred"] and result["model_calls_made_by_tool"] == 0
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == original
    assert {p.name for p in manuscript.parent.iterdir()} == {"draft.md", "paper.bib"}


@pytest.mark.parametrize("name_fields,expected", [
    ("given-names: Ludwig\n    non-dropping-particle: van\n    surname: Beethoven", "Ludwig van Beethoven"),
    ("name:\n      given-names: Ludwig\n      non-dropping-particle: van\n      surname: Beethoven", "Ludwig van Beethoven"),
    ("given-names: Jane\n    dropping-particle: de\n    non-dropping-particle: van\n    surname: Doe\n    suffix: Jr.", "Jane de van Doe Jr."),
    ("literal: Research Software Consortium", "Research Software Consortium"),
    ("name:\n      literal: Research Software Consortium", "Research Software Consortium"),
    ("given: Alice\n    family_name: Research", "Alice Research"),
    ("given_name: Alice\n    family: Research", "Alice Research"),
    ("first: Alice\n    last: Research", "Alice Research"),
    ("firstname: Alice\n    lastname: Research", "Alice Research"),
    ("name: 'Research, Alice'\n    literal: Ignored Group\n    given-names: Ignored\n    surname: Name", "Research, Alice"),
    ("name:\n      name: 'Research, Alice'\n      literal: Ignored Group\n      given-names: Ignored\n      surname: Name", "Research, Alice"),
    ("literal: Research Software Consortium\n    given-names: Ignored\n    surname: Name", "Research Software Consortium"),
    ("given-names: Alice\n    given: Ignored\n    surname: Research\n    family: Name", "Alice Research"),
])
def test_author_name_forms_match_publisher_and_preserve_source(sources, tmp_path, name_fields, expected):
    manuscript, _ = sources
    manuscript.write_text(paper().replace("name: Alice Research", name_fields), encoding="utf-8")
    original = manuscript.read_bytes()
    output = tmp_path / "named-authors"
    result = joss.export(manuscript, output)
    report = json.loads(Path(result["format_report"]).read_text())
    assert report["metrics"]["authors"][0] == {
        "name": expected, "affiliations": ["1", "2"], "valid": True}
    assert report["source_package_passed"]
    assert not report["author_approval_inferred"]
    assert manuscript.read_bytes() == original == (output / "paper.md").read_bytes()


def test_export_retains_bibtex_and_images_and_records_source_only_scope(sources, tmp_path):
    from PIL import Image
    manuscript, bibliography = sources
    image = tmp_path / "figures" / "architecture.png"
    image.parent.mkdir()
    Image.new("RGB", (60, 20), "navy").save(image)
    manuscript.write_text(paper().replace("# State Of The Field", "![Architecture](figures/architecture.png)\n\n# State Of The Field"), encoding="utf-8")
    expected = {"paper.md": manuscript.read_bytes(), "paper.bib": bibliography.read_bytes(),
                "figures/architecture.png": image.read_bytes()}
    output = tmp_path / "delivery"
    result = joss.export(manuscript, output)
    assert result["source_package_passed"]
    assert result["docx"] is None and result["pdf"] is None
    assert not result["publisher_pdf_rendered"] and not result["submission_ready"]
    for relative, data in expected.items():
        assert (output / relative).read_bytes() == data
    report = json.loads((output / "format-report.json").read_text())
    assert report["mode"] == "joss_source_export"
    assert report["bibliography_sha256"] == hashlib.sha256(BIBLIOGRAPHY).hexdigest()
    assert report["visual_review_status"] == "not_rendered"
    manifest = json.loads((output / "manifest.json").read_text())
    assert {row["path"] for row in manifest["files"]} == {*expected, "format-report.json"}
    for row in manifest["files"]:
        assert row["sha256"] == hashlib.sha256((output / row["path"]).read_bytes()).hexdigest()


@pytest.mark.parametrize("replacement,failed", [
    (("affiliation: [2]", "affiliation: [3]"), "authors"),
    (("  - name: Bob Scientist\n    affiliation: [2]", "  - affiliation: [2]"), "authors"),
    (("date: 2 November 2026", "date: 2026-11-02"), "date"),
    (("bibliography: paper.bib", "bibliography: another.bib"), "bibliography_metadata"),
    (("# Software Design", "# Implementation"), "section_software_design"),
    (("[@retained]", "[@absent]"), "citation_keys"),
])
def test_current_joss_requirements_fail_before_source_export(sources, tmp_path, replacement, failed):
    manuscript, _ = sources
    manuscript.write_text(paper().replace(*replacement), encoding="utf-8")
    result = joss.preflight(manuscript)
    assert next(item for item in result["items"] if item["id"] == failed)["status"] == "failed"
    assert not result["prefilter_passed"]
    output = tmp_path / "invalid"
    with pytest.raises(ValueError, match="JOSS source preflight failed"):
        joss.export(manuscript, output)
    assert not output.exists()


def test_duplicate_bibtex_keys_are_blocked_but_unmapped_fields_are_retained(sources):
    manuscript, bibliography = sources
    bibliography.write_bytes(BIBLIOGRAPHY + b"\n@article{retained,title={Another source},date={2026-11-02}}\n")
    result = joss.preflight(manuscript)
    assert next(item for item in result["items"] if item["id"] == "bibliography_keys")["status"] == "failed"
    bibliography.write_bytes(b"@article{retained,title={Supplied title},date={2026-11-02},journaltitle={Full Venue}}\n")
    result = joss.preflight(manuscript)
    assert result["prefilter_passed"]
    assert any(item["code"] == "incomplete_reference_metadata" for item in result["bibliography_review"])


@pytest.mark.parametrize("words,passed", [(700, False), (800, True), (1800, False)])
def test_word_estimates_exclude_metadata_and_fenced_code(sources, words, passed):
    manuscript, _ = sources
    text = paper(words).replace("bibliography: paper.bib", "notes: '" + "metadata " * 800 + "'\nbibliography: paper.bib")
    text = text.replace("# Statement Of Need", "```python\n" + "code " * 800 + "\n```\n\n# Statement Of Need")
    manuscript.write_text(text, encoding="utf-8")
    result = joss.preflight(manuscript)
    status = next(item for item in result["items"] if item["id"] == "word_count")["status"]
    assert (status == "passed") is passed
    assert words <= result["metrics"]["prose_words_estimate"] < words + 100


def test_prose_after_references_still_counts_toward_joss_length(sources):
    manuscript, _ = sources
    manuscript.write_text(paper() + "\n# Additional analysis\n\n" + "finding " * 1200,
                          encoding="utf-8")
    result = joss.preflight(manuscript)
    assert result["metrics"]["prose_words_estimate"] > 2000
    assert next(item for item in result["items"] if item["id"] == "word_count")["status"] == "failed"
    assert not result["prefilter_passed"]


@pytest.mark.parametrize("target", ["../outside.png", "https://example.org/image.png", "/absolute.png", "missing.png"])
def test_source_images_must_be_available_inside_bundle(sources, tmp_path, target):
    manuscript, _ = sources
    manuscript.write_text(paper().replace("# References", "![Figure](" + target + ")\n\n# References"), encoding="utf-8")
    with pytest.raises((ValueError, OSError)):
        joss.export(manuscript, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("markup", [
    r"Inline figure: \includegraphics[width=2cm]{plot.png}.",
    "\\begin{figure}\n\\includegraphics*{plot.png}\n\\end{figure}",
    '<img src="plot.png" alt="Plot">',
])
def test_raw_figures_cannot_pass_export_with_missing_assets(sources, tmp_path, markup):
    from PIL import Image
    manuscript, _ = sources
    Image.new("RGB", (16, 16)).save(tmp_path / "plot.png")
    manuscript.write_text(paper().replace("# References", markup + "\n\n# References"), encoding="utf-8")
    with pytest.raises(ValueError, match="Use Markdown image syntax"):
        joss.export(manuscript, tmp_path / "delivery")
    assert not (tmp_path / "delivery").exists()


def test_literal_figure_examples_are_not_assets(sources):
    manuscript, _ = sources
    examples = r'''Write `\includegraphics{example.png}` or `<img src="example.png">`.

```tex
\includegraphics{example.png}
```

An expression $x \in S$ and an HTML comment <!-- <img src="example.png"> -->.

\begin{figure}
% \includegraphics{example.png}
\end{figure}

\verb|\includegraphics{example.png}|
'''
    manuscript.write_text(paper().replace("# References", examples + "\n# References"), encoding="utf-8")
    assert joss.preflight(manuscript)["prefilter_passed"]


def test_explicit_bibliography_and_resource_directory_reach_exact_source_bundle(sources, tmp_path):
    from PIL import Image
    manuscript, bibliography = sources
    media = tmp_path / "media"
    media.mkdir()
    Image.new("RGB", (20, 20), "white").save(media / "figure.png")
    manuscript.write_text(paper().replace("# References", "![Figure](figure.png)\n\n# References"), encoding="utf-8")
    renamed = tmp_path / "original-export.bib"
    bibliography.rename(renamed)
    output = tmp_path / "out"
    joss.export(manuscript, output, bibliography=renamed, resource_dir=media)
    assert (output / "paper.bib").read_bytes() == BIBLIOGRAPHY
    assert (output / "figure.png").read_bytes() == (media / "figure.png").read_bytes()


def test_existing_output_is_preserved(sources, tmp_path):
    manuscript, _ = sources
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("unchanged")
    with pytest.raises(ValueError, match="must be new"):
        joss.export(manuscript, output)
    assert marker.read_text() == "unchanged"
    assert list(output.iterdir()) == [marker]

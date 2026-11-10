"""JOSS source packages use real Pandoc parsing and preserve supplied source bytes."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
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


@pytest.mark.parametrize("markup,in_metadata", [
    (r"Inline figure: \includegraphics[width=2cm]{plot.png}.", False),
    ("\\begin{figure}\n\\includegraphics*{plot.png}\n\\end{figure}", False),
    ('<img src="plot.png" alt="Plot">', False),
    pytest.param('<img src="plot.png" alt="Plot">', True, id="metadata-html"),
])
def test_raw_figures_cannot_pass_export_with_missing_assets(sources, tmp_path, markup, in_metadata):
    from PIL import Image
    manuscript, _ = sources
    Image.new("RGB", (16, 16)).save(tmp_path / "plot.png")
    text = (paper().replace("bibliography: paper.bib", "bibliography: paper.bib\nabstract: '" + markup + "'")
            if in_metadata else paper().replace("# References", markup + "\n\n# References"))
    manuscript.write_text(text, encoding="utf-8")
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


def metadata_paper(metadata, body=""):
    return paper().replace("bibliography: paper.bib", "bibliography: paper.bib\n" + metadata) + body


def pandoc_document(manuscript):
    parsed = subprocess.run(
        [str(joss.pandoc_binary()), "--from=markdown", "--to=json", "--standalone", "--fail-if-warnings"],
        input=manuscript.read_text(encoding="utf-8-sig"), cwd=manuscript.parent,
        capture_output=True, text=True, encoding="utf-8", timeout=30, check=True)
    return json.loads(parsed.stdout)


def image_bytes(path, color="navy"):
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 24), color).save(path, format="PNG")
    return path.read_bytes()


@pytest.mark.parametrize("metadata,types", [
    ("abstract: 'A retained diagram ![Plot](figures/plot.png)'", {"MetaInlines"}),
    ("notes:\n  exports:\n    - caption: '![Plot](figures/plot.png)'", {"MetaMap", "MetaList", "MetaInlines"}),
    ("notes:\n  exports:\n    - caption: |\n        First paragraph.\n\n        ![Plot](figures/plot.png)",
     {"MetaMap", "MetaList", "MetaBlocks"}),
    ("include-before:\n  - 'A retained diagram ![Plot](figures/plot.png)'", {"MetaList", "MetaInlines"}),
])
def test_metadata_images_use_actual_pandoc_structures_and_preserve_source_bytes(sources, tmp_path, metadata, types):
    manuscript, bibliography = sources
    body_word_count = joss.preflight(manuscript)["metrics"]["prose_words_estimate"]
    manuscript.write_bytes(("\ufeff" + metadata_paper(metadata)).replace("\n", "\r\n").encode("utf-8"))
    picture = image_bytes(tmp_path / "figures/plot.png")
    original = manuscript.read_bytes(), bibliography.read_bytes()
    document = pandoc_document(manuscript)
    meta_nodes = list(joss._nodes(document["meta"]))
    assert types <= {node.get("t") for node in meta_nodes}
    assert [node["c"][-1][0] for node in meta_nodes if node.get("t") == "Image"] == ["figures/plot.png"]
    assert not any(node.get("t") == "Image" for node in joss._nodes(document["blocks"]))

    report = joss.preflight(manuscript)
    assert report["prefilter_passed"] and report["metrics"]["image_count"] == 1
    assert report["metrics"]["prose_words_estimate"] == body_word_count
    assert report["metrics"]["citation_keys"] == ["retained"]
    output = tmp_path / "delivery"
    result = joss.export(manuscript, output)
    assert result["source_package_passed"] and not result["publisher_pdf_rendered"]
    assert not result["submission_ready"] and result["pdf"] is None and result["docx"] is None
    assert (output / "paper.md").read_bytes() == original[0]
    assert (output / "paper.bib").read_bytes() == original[1]
    assert (output / "figures/plot.png").read_bytes() == picture
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == original
    rows = json.loads((output / "manifest.json").read_text(encoding="utf-8"))["files"]
    image = next(row for row in rows if row["path"] == "figures/plot.png")
    assert image["sha256"] == hashlib.sha256(picture).hexdigest() and image["bytes"] == len(picture)


@pytest.mark.parametrize("location", ["title", "scalar", "nested", "reference"])
@pytest.mark.parametrize("operation", ["preflight", "export"])
def test_metadata_missing_images_fail_preflight_and_export_before_output(sources, tmp_path, location, operation):
    manuscript, bibliography = sources
    if location == "title":
        # Reproduce the original gap; this is not an example of an acceptable JOSS title.
        text = paper().replace("title: 'Research tool: a supplied example'",
                               "title: 'Research tool ![Logo](missing-logo.png)'")
    elif location == "scalar":
        text = metadata_paper("abstract: '![Missing](missing-logo.png)'")
    elif location == "nested":
        text = metadata_paper("notes:\n  entries:\n    - description: |\n        First paragraph.\n\n        ![Missing](missing-logo.png)")
    else:
        text = metadata_paper("abstract: '![Missing][logo]'", "\n[logo]: missing-logo.png\n")
    manuscript.write_text(text, encoding="utf-8")
    original = manuscript.read_bytes(), bibliography.read_bytes()
    document = pandoc_document(manuscript)
    assert any(node.get("t") == "Image" and node["c"][-1][0] == "missing-logo.png"
               for node in joss._nodes(document["meta"]))
    output = tmp_path / "missing-delivery"
    with pytest.raises((ValueError, OSError), match=r"missing-logo\.png"):
        if operation == "preflight":
            joss.preflight(manuscript)
        else:
            joss.export(manuscript, output)
    assert not output.exists()
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == original


@pytest.mark.parametrize("definition_in_metadata", [False, True])
def test_metadata_reference_images_and_body_duplicates_are_retained_once(sources, tmp_path, definition_in_metadata):
    manuscript, _ = sources
    metadata = "abstract: |\n  ![Shared][plot]\n\n  ![Metadata only](figures/meta.png)"
    body = "\n![Body](figures/shared.png)\n"
    if definition_in_metadata:
        metadata += "\n\n  [plot]: figures/shared.png"
    else:
        body += "\n[plot]: figures/shared.png\n"
    manuscript.write_text(metadata_paper(metadata, body), encoding="utf-8")
    expected = {name: image_bytes(tmp_path / name, color) for name, color in
                [("figures/shared.png", "navy"), ("figures/meta.png", "red")]}
    document = pandoc_document(manuscript)
    targets = [node["c"][-1][0] for node in joss._nodes(document) if node.get("t") == "Image"]
    assert targets.count("figures/shared.png") == 2 and targets.count("figures/meta.png") == 1
    report = joss.preflight(manuscript)
    assert report["prefilter_passed"] and report["metrics"]["image_count"] == 2
    output = tmp_path / "delivery"
    joss.export(manuscript, output)
    rows = json.loads((output / "manifest.json").read_text(encoding="utf-8"))["files"]
    assert {row["path"] for row in rows} == {"paper.md", "paper.bib", "format-report.json", *expected}
    for name, data in expected.items():
        assert (output / name).read_bytes() == data
        assert len([row for row in rows if row["path"] == name]) == 1


@pytest.mark.parametrize("relative,markup", [
    ("figures/측정 그림 (v1).png", "![Plot](<figures/측정 그림 (v1).png>)"),
    ("figures/plot(one).png", "![Plot](figures/plot(one).png)"),
    ("figures/plot%20one.png", "![Plot](figures/plot%2520one.png)"),
    ("figures/plot#one.png", "![Plot](figures/plot%23one.png)"),
])
def test_metadata_image_filenames_survive_moving_and_removing_original_sources(sources, tmp_path, relative, markup):
    manuscript, bibliography = sources
    original_dir = tmp_path / "original"
    original_dir.mkdir()
    manuscript = manuscript.rename(original_dir / manuscript.name)
    bibliography = bibliography.rename(original_dir / bibliography.name)
    manuscript.write_text(metadata_paper("abstract: '" + markup + "'"), encoding="utf-8")
    picture = image_bytes(original_dir / relative)
    source_bytes, bib_bytes = manuscript.read_bytes(), bibliography.read_bytes()
    output = tmp_path / "delivery"
    joss.export(manuscript, output)
    moved = tmp_path / "relocated"
    shutil.move(str(output), moved)
    shutil.rmtree(original_dir)
    rebuilt = tmp_path / "rebuilt"
    assert joss.preflight(moved / "paper.md")["prefilter_passed"]
    assert joss.export(moved / "paper.md", rebuilt)["source_package_passed"]
    for directory in (moved, rebuilt):
        assert (directory / "paper.md").read_bytes() == source_bytes
        assert (directory / "paper.bib").read_bytes() == bib_bytes
        assert (directory / relative).read_bytes() == picture


def test_metadata_images_use_only_the_explicit_resource_directory(sources, tmp_path):
    manuscript, _ = sources
    manuscript.write_text(metadata_paper("abstract: '![Plot](figures/plot.png)'"), encoding="utf-8")
    image_bytes(tmp_path / "figures/plot.png", "red")
    resources = tmp_path / "resources"
    picture = image_bytes(resources / "figures/plot.png", "navy")
    output = tmp_path / "delivery"
    report = joss.preflight(manuscript, resource_dir=resources)
    assert report["prefilter_passed"] and report["metrics"]["image_count"] == 1
    joss.export(manuscript, output, resource_dir=resources)
    assert (output / "figures/plot.png").read_bytes() == picture
    (resources / "figures/plot.png").unlink()
    with pytest.raises(OSError, match=r"plot\.png"):
        joss.preflight(manuscript, resource_dir=resources)


@pytest.mark.parametrize("target", [
    "../outside.png", "%2e%2e/outside.png", "/absolute.png", "C:/plot.png", "figures%5Cplot.png",
    "https://example.invalid/plot.png", "figure.png?download=1", "figure.png#fragment",
    "paper.md", "paper.bib", "format-report.json", "manifest.json", "manifest.json/figure.png",
])
def test_metadata_images_keep_existing_relative_path_and_reserved_name_guards(sources, tmp_path, target):
    manuscript, bibliography = sources
    manuscript.write_text(metadata_paper("abstract: '![Plot](" + target + ")'"), encoding="utf-8")
    original = manuscript.read_bytes(), bibliography.read_bytes()
    output = tmp_path / "invalid"
    with pytest.raises(ValueError, match="local relative image paths"):
        joss.preflight(manuscript)
    with pytest.raises(ValueError, match="local relative image paths"):
        joss.export(manuscript, output)
    assert not output.exists()
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == original


@pytest.mark.parametrize("kind", ["file", "directory", "resource_root"])
def test_metadata_images_keep_symlink_guards(sources, tmp_path, kind):
    manuscript, _ = sources
    manuscript.write_text(metadata_paper("abstract: '![Plot](figures/plot.png)'"), encoding="utf-8")
    real = tmp_path / "real"
    picture = image_bytes(real / "figures/plot.png")
    if kind == "file":
        link, target = tmp_path / "figures/plot.png", real / "figures/plot.png"
    elif kind == "directory":
        link, target = tmp_path / "figures", real / "figures"
    else:
        link, target = tmp_path / "resources", real
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=kind != "file")
    except OSError as exc:
        pytest.skip("This environment cannot create a symlink fixture: " + str(exc))
    kwargs = {"resource_dir": link} if kind == "resource_root" else {}
    output = tmp_path / "invalid"
    with pytest.raises(ValueError, match="(?i)symlink|junction|reparse"):
        joss.preflight(manuscript, **kwargs)
    with pytest.raises(ValueError, match="(?i)symlink|junction|reparse"):
        joss.export(manuscript, output, **kwargs)
    assert not output.exists()
    assert (real / "figures/plot.png").read_bytes() == picture


@pytest.mark.parametrize("kind", ["empty", "corrupt", "directory"])
def test_metadata_images_keep_file_and_raster_validation(sources, tmp_path, kind):
    manuscript, _ = sources
    manuscript.write_text(metadata_paper("abstract: '![Plot](plot.png)'"), encoding="utf-8")
    picture = tmp_path / "plot.png"
    if kind == "directory":
        picture.mkdir()
    else:
        picture.write_bytes(b"" if kind == "empty" else b"Not a PNG image.")
    output = tmp_path / "invalid"
    with pytest.raises((ValueError, OSError)):
        joss.preflight(manuscript)
    with pytest.raises((ValueError, OSError)):
        joss.export(manuscript, output)
    assert not output.exists()


def test_metadata_literal_examples_and_plain_paths_are_not_image_dependencies(sources, tmp_path):
    manuscript, _ = sources
    metadata = """notes:
  code: '`![Example](missing-code.png)`'
  path: missing-string.png
  html: '`<img src="missing-html.png">`'
  tex: '`\\includegraphics{missing-tex.png}`'
"""
    manuscript.write_text(metadata_paper(metadata), encoding="utf-8")
    nodes = list(joss._nodes(pandoc_document(manuscript)["meta"]))
    assert any(node.get("t") == "Code" for node in nodes)
    assert not any(node.get("t") == "Image" for node in nodes)
    report = joss.preflight(manuscript)
    assert report["prefilter_passed"] and report["metrics"]["image_count"] == 0
    output = tmp_path / "delivery"
    joss.export(manuscript, output)
    assert {path.name for path in output.iterdir()} == {"paper.md", "paper.bib", "format-report.json", "manifest.json"}


@pytest.mark.parametrize("stage", ["preflight", "export"])
def test_metadata_image_changes_keep_source_snapshot_guards(sources, tmp_path, monkeypatch, stage):
    from PIL import Image
    manuscript, _ = sources
    manuscript.write_text(metadata_paper("abstract: '![Plot](plot.png)'"), encoding="utf-8")
    picture = tmp_path / "plot.png"
    image_bytes(picture)
    output = tmp_path / "delivery"
    if stage == "preflight":
        actual_open = Image.open
        def open_then_change(*args, **kwargs):
            opened = actual_open(*args, **kwargs)
            picture.write_bytes(b"Changed after image bytes were read")
            return opened
        monkeypatch.setattr(Image, "open", open_then_change)
        with pytest.raises(ValueError, match="changed during preflight"):
            joss.preflight(manuscript)
    else:
        actual_open = Path.open
        def open_then_change(path, mode="r", *args, **kwargs):
            opened = actual_open(path, mode, *args, **kwargs)
            if path == output / "plot.png" and mode == "xb":
                picture.write_bytes(b"Changed while the retained image was being written")
            return opened
        monkeypatch.setattr(Path, "open", open_then_change)
        with pytest.raises(ValueError, match="changed during export"):
            joss.export(manuscript, output)
    assert not (output / "manifest.json").exists()
    assert not (output / "format-report.json").exists()


def test_metadata_images_survive_explicit_submission_bundle_and_source_removal(sources, tmp_path):
    from submission_support import prepare_bundle
    manuscript, bibliography = sources
    original_dir = tmp_path / "original"
    original_dir.mkdir()
    manuscript = manuscript.rename(original_dir / manuscript.name)
    bibliography = bibliography.rename(original_dir / bibliography.name)
    relative = "figures/측정 그림.png"
    text = metadata_paper("abstract: '![Retained][plot]'", "\n[plot]: <" + relative + ">\n")
    manuscript.write_text(text, encoding="utf-8")
    picture = image_bytes(original_dir / relative)
    exported = tmp_path / "exported"
    joss.export(manuscript, exported)
    selections = [("manuscript", "paper.md"), ("bibliography", "paper.bib"), ("figure", relative)]
    plan = tmp_path / "bundle-plan.json"
    plan.write_text(json.dumps({"venue_id": "joss", "title": "Retained source image",
                               "files": [{"role": role, "path": path} for role, path in selections]},
                              ensure_ascii=False), encoding="utf-8")
    bundle = tmp_path / "bundle"
    report = prepare_bundle(plan, exported, bundle)
    assert not report["submission_ready"] and not report["author_approval_inferred"]
    assert {path.relative_to(bundle / "files").as_posix() for path in (bundle / "files").rglob("*")
            if path.is_file()} == {path for _, path in selections}
    moved = tmp_path / "moved-bundle"
    shutil.move(str(bundle), moved)
    shutil.rmtree(original_dir)
    shutil.rmtree(exported)
    rebuilt = tmp_path / "rebuilt"
    assert joss.export(moved / "files/paper.md", rebuilt)["source_package_passed"]
    assert (moved / "files/paper.md").read_bytes() == (rebuilt / "paper.md").read_bytes()
    assert (moved / "files/paper.bib").read_bytes() == (rebuilt / "paper.bib").read_bytes() == BIBLIOGRAPHY
    assert (moved / "files" / relative).read_bytes() == (rebuilt / relative).read_bytes() == picture


def citation_ids(value):
    return [citation["citationId"] for node in joss._nodes(value) if node.get("t") == "Cite"
            for citation in node["c"][0]]


@pytest.mark.parametrize("location", [
    "abstract", "nested_inlines", "nested_blocks", "metadata_references", "body", "references_section",
])
@pytest.mark.parametrize("operation", ["preflight", "export"])
def test_undefined_citations_in_metadata_and_body_are_blocked(sources, tmp_path, location, operation):
    manuscript, bibliography = sources
    if location == "abstract":
        text = metadata_paper("abstract: 'A source [@missing].'")
    elif location == "nested_inlines":
        text = metadata_paper("notes:\n  entries:\n    - description: 'A source [@missing].'")
    elif location == "nested_blocks":
        text = metadata_paper("notes:\n  entries:\n    - description: |\n        First paragraph.\n\n        A source [@missing].")
    elif location == "metadata_references":
        text = metadata_paper("references:\n  - id: metadata-entry\n    type: article-journal\n    title: 'A source [@missing].'")
    elif location == "body":
        text = paper().replace("# Statement Of Need", "A source [@missing].\n\n# Statement Of Need", 1)
    else:
        text = paper() + "\nA source [@missing].\n"
    manuscript.write_text(text, encoding="utf-8")
    original = manuscript.read_bytes(), bibliography.read_bytes()
    document = pandoc_document(manuscript)
    in_metadata = location not in {"body", "references_section"}
    assert citation_ids(document["meta"]).count("missing") == int(in_metadata)
    assert citation_ids(document["blocks"]).count("missing") == int(not in_metadata)
    assert set(citation_ids(document)) == {"missing", "retained"}
    output = tmp_path / "invalid-citations"
    if operation == "preflight":
        report = joss.preflight(manuscript)
        item = next(row for row in report["items"] if row["id"] == "citation_keys")
        assert item["status"] == "failed" and "missing" in item["reason"]
        assert item["reason"] in report["blockers"]
        assert not report["prefilter_passed"] and not report["source_package_passed"]
        assert report["metrics"]["citation_keys"] == sorted(set(citation_ids(document["blocks"])))
    else:
        with pytest.raises(ValueError, match="JOSS source preflight failed:.*missing"):
            joss.export(manuscript, output)
    assert not output.exists()
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == original


def test_valid_metadata_citations_preserve_body_metrics_and_source_bundle(sources, tmp_path):
    manuscript, bibliography = sources
    extra = b"""
@article{alpha, title={Alpha Source}, author={Writer, Alice}, year={2026}, journal={Source Journal}}
@article{zeta, title={Zeta Source}, author={Writer, Bob}, year={2026}, journal={Source Journal}}
@article{metadataonly, title={Metadata Source}, author={Writer, Casey}, year={2026}, journal={Source Journal}}
"""
    bibliography.write_bytes(BIBLIOGRAPHY + extra)
    body = paper().replace("# Statement Of Need",
                           "Other sources [@zeta; @retained; @alpha; @retained].\n\n# Statement Of Need", 1)
    manuscript.write_text(body, encoding="utf-8")
    baseline = joss.preflight(manuscript)
    assert baseline["prefilter_passed"]
    metadata = """abstract: 'A source [@metadataonly; @retained] and again [@metadataonly].'
references:
  - id: metadata-entry
    title: 'A discussed source [@alpha].'
"""
    text = body.replace("bibliography: paper.bib", "bibliography: paper.bib\n" + metadata)
    manuscript.write_bytes(("\ufeff" + text).replace("\n", "\r\n").encode("utf-8"))
    original = manuscript.read_bytes(), bibliography.read_bytes()
    document = pandoc_document(manuscript)
    assert citation_ids(document["meta"]).count("metadataonly") == 2
    assert citation_ids(document["blocks"]).count("retained") >= 2
    assert set(citation_ids(document["meta"])) == {"alpha", "metadataonly", "retained"}
    report = joss.preflight(manuscript)
    assert report["prefilter_passed"]
    assert next(row for row in report["items"] if row["id"] == "citation_keys")["status"] == "passed"
    assert report["metrics"]["citation_keys"] == ["alpha", "retained", "zeta"]
    assert report["metrics"]["reference_count"] == 4
    assert report["metrics"]["prose_words_estimate"] == baseline["metrics"]["prose_words_estimate"]
    output = tmp_path / "delivery"
    result = joss.export(manuscript, output)
    assert result["source_package_passed"] and not result["submission_ready"]
    assert result["pdf"] is None and result["docx"] is None and not result["publisher_pdf_rendered"]
    assert (output / "paper.md").read_bytes() == original[0]
    assert (output / "paper.bib").read_bytes() == original[1]
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == original
    rows = json.loads((output / "manifest.json").read_text(encoding="utf-8"))["files"]
    for name, data in zip(("paper.md", "paper.bib"), original):
        row = next(row for row in rows if row["path"] == name)
        assert row["sha256"] == hashlib.sha256(data).hexdigest() and row["bytes"] == len(data)


def test_metadata_citation_like_literals_are_not_inferred_as_cites(sources, tmp_path):
    manuscript, bibliography = sources
    metadata = """notes:
  plain: missing-string
  code: '`[@missing-code]`'
  html: '<span data-key="@missing-html"></span>'
  tex: '\\cite{missing-tex}'
"""
    manuscript.write_text(metadata_paper(metadata), encoding="utf-8")
    original = manuscript.read_bytes(), bibliography.read_bytes()
    document = pandoc_document(manuscript)
    nodes = list(joss._nodes(document["meta"]))
    assert {"Code", "RawInline"} <= {node.get("t") for node in nodes}
    assert citation_ids(document["meta"]) == []
    report = joss.preflight(manuscript)
    assert report["prefilter_passed"] and report["metrics"]["citation_keys"] == ["retained"]
    output = tmp_path / "delivery"
    assert joss.export(manuscript, output)["source_package_passed"]
    assert (output / "paper.md").read_bytes() == original[0]
    assert (output / "paper.bib").read_bytes() == original[1]
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == original


@pytest.mark.parametrize("metadata,expected", [
    pytest.param("nocite: '@retained'", ["retained"], id="explicit"),
    pytest.param("nocite: '@*'", ["*"], id="wildcard"),
    pytest.param("nocite: '@retained, @*'", ["retained", "*"], id="mixed"),
    pytest.param("nocite: '[@retained; @retained; @*; @*]'", ["retained", "retained", "*", "*"], id="duplicates"),
    pytest.param("nocite:\n  - '@retained'\n  - '@*'", ["retained", "*"], id="list"),
    pytest.param("nocite: ''", [], id="empty-string"),
    pytest.param("nocite: null", [], id="null"),
    pytest.param("nocite: []", [], id="empty-list"),
    pytest.param("nocite: {}", [], id="empty-map"),
    pytest.param("nocite: |\n", [], id="empty-block"),
    pytest.param("nocite: '`[@missing]`'", [], id="code"),
    pytest.param("nocite: '\\@missing'", [], id="escaped-literal"),
    pytest.param("nocite: missing-string", [], id="plain-string"),
    pytest.param('nocite: \'<span data-key="@missing"></span>\'', [], id="html-attribute"),
    pytest.param("nocite: '\\cite{missing}'", [], id="raw-tex"),
])
def test_nocite_actual_cites_and_noncitation_values_preserve_body_metrics(sources, tmp_path, metadata, expected):
    manuscript, bibliography = sources
    body_word_count = joss.preflight(manuscript)["metrics"]["prose_words_estimate"]
    manuscript.write_text(metadata_paper(metadata), encoding="utf-8")
    original = manuscript.read_bytes(), bibliography.read_bytes()
    document = pandoc_document(manuscript)
    assert sorted(citation_ids(document["meta"].get("nocite"))) == sorted(expected)
    assert citation_ids(document["blocks"]) == ["retained"]
    report = joss.preflight(manuscript)
    assert report["prefilter_passed"]
    assert next(row for row in report["items"] if row["id"] == "citation_keys")["status"] == "passed"
    assert report["metrics"]["citation_keys"] == ["retained"]
    assert report["metrics"]["reference_count"] == 1
    assert report["metrics"]["prose_words_estimate"] == body_word_count
    output = tmp_path / "delivery"
    result = joss.export(manuscript, output)
    assert result["source_package_passed"] and not result["submission_ready"]
    assert (output / "paper.md").read_bytes() == original[0]
    assert (output / "paper.bib").read_bytes() == original[1]
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == original


@pytest.mark.parametrize("metadata,body,missing", [
    pytest.param("nocite: '@missing'", "", "missing", id="top-level-explicit"),
    pytest.param("nocite: '@*, @missing'", "", "missing", id="wildcard-with-missing"),
    pytest.param("nocite:\n  - '@missing'", "", "missing", id="top-level-list"),
    pytest.param("nocite:\n  entries:\n    - selection: '[@*; @missing]'", "", "missing", id="top-level-nested"),
    pytest.param("notes:\n  nocite: '@*'", "", "*", id="nested-nocite-name"),
    pytest.param("notes:\n  entries:\n    - nocite: '[@*; @retained]'", "", "*", id="nested-list-nocite-name"),
    pytest.param("abstract: '@*'", "", "*", id="ordinary-metadata-wildcard"),
    pytest.param("", "\nA body selector @*.\n", "*", id="body-wildcard"),
])
def test_nocite_rejects_undefined_explicit_keys_and_misplaced_wildcards(sources, tmp_path, metadata, body, missing):
    manuscript, bibliography = sources
    manuscript.write_text(metadata_paper(metadata, body), encoding="utf-8")
    original = manuscript.read_bytes(), bibliography.read_bytes()
    document = pandoc_document(manuscript)
    assert missing in citation_ids(document)
    report = joss.preflight(manuscript)
    item = next(row for row in report["items"] if row["id"] == "citation_keys")
    assert item["status"] == "failed" and missing in item["reason"]
    assert report["blockers"] == [item["reason"]]
    assert not report["prefilter_passed"] and not report["source_package_passed"]
    assert report["metrics"]["citation_keys"] == sorted(set(citation_ids(document["blocks"])))
    output = tmp_path / "invalid-citations"
    with pytest.raises(ValueError, match="JOSS source preflight failed:") as failure:
        joss.export(manuscript, output)
    assert missing in str(failure.value)
    assert not output.exists()
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == original


@pytest.mark.parametrize("metadata", [
    "nocite: '@retained'", "nocite: '@*'", "abstract: 'A source [@retained].'",
    "abstract: 'A source [@retained].'\nnocite: '@*'",
])
def test_metadata_and_nocite_do_not_replace_required_body_citations(sources, tmp_path, metadata):
    manuscript, bibliography = sources
    text = paper().replace("[@retained]", "a retained source")
    text = text.replace("bibliography: paper.bib", "bibliography: paper.bib\n" + metadata)
    manuscript.write_text(text, encoding="utf-8")
    original = manuscript.read_bytes(), bibliography.read_bytes()
    document = pandoc_document(manuscript)
    assert citation_ids(document["blocks"]) == []
    assert citation_ids(document["meta"])
    report = joss.preflight(manuscript)
    assert report["metrics"]["citation_keys"] == []
    assert report["metrics"]["reference_count"] == 1
    assert next(row for row in report["items"] if row["id"] == "citation_keys")["status"] == "failed"
    assert not report["prefilter_passed"]
    output = tmp_path / "no-body-citations"
    with pytest.raises(ValueError, match="JOSS source preflight failed:"):
        joss.export(manuscript, output)
    assert not output.exists()
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == original


def test_nocite_wildcard_does_not_bypass_duplicate_bibliography_keys(sources, tmp_path):
    manuscript, bibliography = sources
    bibliography.write_bytes(BIBLIOGRAPHY + b"\n@article{retained,title={A different source},year={2026}}\n")
    manuscript.write_text(metadata_paper("nocite: '@*'"), encoding="utf-8")
    original = manuscript.read_bytes(), bibliography.read_bytes()
    assert citation_ids(pandoc_document(manuscript)["meta"]["nocite"]) == ["*"]
    report = joss.preflight(manuscript)
    statuses = {item["id"]: item["status"] for item in report["items"]}
    assert statuses["bibliography_keys"] == "failed" and statuses["citation_keys"] == "passed"
    assert report["metrics"]["citation_keys"] == ["retained"]
    assert report["metrics"]["reference_count"] == 2
    assert not report["prefilter_passed"]
    output = tmp_path / "duplicate-keys"
    with pytest.raises(ValueError, match="Duplicate BibTeX keys"):
        joss.export(manuscript, output)
    assert not output.exists()
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == original


def test_nocite_wildcard_does_not_hide_sorted_unique_missing_keys_from_other_scopes(sources, tmp_path):
    manuscript, bibliography = sources
    metadata = """abstract: 'Sources [@z_missing; @*; @a_missing].'
notes:
  nested:
    nocite: '[@a_missing]'
nocite: '[@*; @z_missing]'
"""
    text = metadata_paper(metadata).replace(
        "# Statement Of Need", "Body sources [@z_missing; @b_missing; @z_missing].\n\n# Statement Of Need", 1)
    manuscript.write_text(text, encoding="utf-8")
    original = manuscript.read_bytes(), bibliography.read_bytes()
    document = pandoc_document(manuscript)
    assert "*" in citation_ids(document["meta"]["abstract"])
    assert citation_ids(document["meta"]["nocite"]) == ["*", "z_missing"]
    assert citation_ids(document["blocks"]).count("z_missing") == 2
    report = joss.preflight(manuscript)
    item = next(row for row in report["items"] if row["id"] == "citation_keys")
    expected = ["*", "a_missing", "b_missing", "z_missing"]
    assert item["status"] == "failed" and str(expected) in item["reason"]
    assert report["blockers"] == [item["reason"]]
    assert report["metrics"]["citation_keys"] == ["b_missing", "retained", "z_missing"]
    assert not report["prefilter_passed"]
    output = tmp_path / "mixed-missing-keys"
    with pytest.raises(ValueError, match="JOSS source preflight failed:") as failure:
        joss.export(manuscript, output)
    assert str(expected) in str(failure.value)
    assert not output.exists()
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == original


@pytest.mark.parametrize("newline,bom", [("\n", b""), ("\r\n", b"\xef\xbb\xbf")])
def test_bibtex_field_comments_reach_joss_package_without_rewriting(sources, tmp_path, newline, bom):
    from import_references import parse_bibliography

    manuscript, bibliography = sources
    control = BIBLIOGRAPHY.decode().replace(
        " note = {An original field not regenerated from metadata JSON}",
        ' url = {https://example.org/a%20b?keep=%25},\n'
        r' note = {Keep 50\% and {nested % data} plus "quoted" text}')
    supplied = control.replace(
        " title = {A Retained {Research} Tool},",
        ' title = {A Retained {Research} Tool}, % annotation with } ) , = # @fake{key} "')
    supplied = supplied.replace(
        " year = {2025},", " year = % before the value\n {2025} % before the comma\n ,")
    supplied = supplied.replace(
        "\n}", '\n % final comment containing } ) @fake{key,title={ignored}}\n}')
    supplied = "Bibliography for related work\n% Example only: @misc{phantom,title={Ignored}}\n" + supplied
    original_bib = bom + supplied.replace("\n", newline).encode()
    bibliography.write_bytes(original_bib)
    manuscript.write_text(metadata_paper("abstract: 'A source [@retained].'\nnocite: '[@retained; @*]'"),
                          encoding="utf-8")
    original_md = manuscript.read_bytes()

    # Actual reader acceptance is separate from preservation by the local importer.
    for reader in ("bibtex", "biblatex"):
        results = []
        for text in (control, supplied):
            parsed = subprocess.run(
                [str(joss.pandoc_binary()), "--from=" + reader, "--to=csljson", "--fail-if-warnings"],
                input=text.replace("\n", newline), capture_output=True, text=True,
                encoding="utf-8", timeout=30, check=True)
            assert parsed.stderr == ""
            results.append(json.loads(parsed.stdout))
        assert results[0] == results[1]
        assert [record["id"] for record in results[1]] == ["retained"]

    record = parse_bibliography(original_bib.decode("utf-8-sig"), "bibtex")["references"][0]
    assert record["source"]["raw"] == supplied[supplied.index("@article"):].rstrip("\n").replace("\n", newline)
    assert record["url"] == "https://example.org/a%20b?keep=%25"
    preflight = joss.preflight(manuscript)
    assert preflight["prefilter_passed"]
    assert preflight["metrics"]["citation_keys"] == ["retained"]
    assert preflight["metrics"]["reference_count"] == 1

    output = tmp_path / "commented-source-package"
    result = joss.export(manuscript, output)
    assert result["source_package_passed"] and not result["publisher_pdf_rendered"]
    assert not result["submission_ready"]
    assert (output / "paper.bib").read_bytes() == original_bib
    assert (output / "paper.md").read_bytes() == original_md
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == (original_md, original_bib)
    report = json.loads((output / "format-report.json").read_text())
    assert report["bibliography_sha256"] == hashlib.sha256(original_bib).hexdigest()
    manifest = json.loads((output / "manifest.json").read_text())
    for row in manifest["files"]:
        assert row["sha256"] == hashlib.sha256((output / row["path"]).read_bytes()).hexdigest()


@pytest.mark.parametrize("fields,location,expected", [
    (" title={Retained} % missing separator\n author={Researcher, Alice},\n year=2025\n}", (5, 2), None),
    (" title {Retained},\n author={Researcher, Alice},\n year=2025\n}", (4, 8), None),
    (" title = % comment with a fake {value}\n}", (5, 1), None),
    (" title={Retained} # % missing concatenation value\n}", (4, 19),
     "Expected a BibTeX value after '#'"),
], ids=["missing-comma", "missing-equals", "missing-value", "missing-concatenation-value"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_bibtex_error_location_is_consistent_across_clis(
        sources, tmp_path, fields, location, expected, newline):
    manuscript, bibliography = sources
    text = "% retained annotation\n@string{prefix={Retained}}\n@article{retained,\n" + fields
    original_bib = b"\xef\xbb\xbf" + text.replace("\n", newline).encode()
    bibliography.write_bytes(original_bib)
    original_md = manuscript.read_bytes()
    imported, exported = tmp_path / "imported", tmp_path / "exported"
    commands = [
        [sys.executable, str(ROOT / "scripts/import_references.py"), "--input", str(bibliography),
         "--output-dir", str(imported)],
        [sys.executable, str(ROOT / "scripts/export_manuscript.py"), "preflight", "--venue", "joss",
         "--manuscript", str(manuscript), "--pandoc", str(joss.pandoc_binary())],
        [sys.executable, str(ROOT / "scripts/export_manuscript.py"), "export", "--venue", "joss",
         "--manuscript", str(manuscript), "--pandoc", str(joss.pandoc_binary()),
         "--output-dir", str(exported)],
    ]
    errors = []
    for command in commands:
        completed = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True,
                                   encoding="utf-8", timeout=30)
        assert completed.returncode == 2
        assert completed.stdout == ""
        errors.append(json.loads(completed.stderr)["error"])
    assert errors[0] == errors[1] == errors[2]
    line, column = location
    assert errors[0].startswith(f"Invalid BibTeX at line {line}, column {column}:")
    if expected is not None:
        assert expected in errors[0]
    assert not imported.exists() and not exported.exists()
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == (original_md, original_bib)


@pytest.mark.parametrize("relative,target", [
    ("PAPER.MD", "PAPER.MD"),
    ("Paper.Bib", "Paper.Bib"),
    ("FORMAT-REPORT.JSON", "FORMAT-REPORT.JSON"),
    ("Manifest.Json", "Manifest.Json"),
    ("PAPER.MD/plot.png", "PAPER.MD/plot.png"),
    ("Paper.Bib/plot.png", "Paper.Bib/plot.png"),
    ("FORMAT-REPORT.JSON/plot.png", "FORMAT-REPORT.JSON/plot.png"),
    ("Manifest.Json/plot.png", "Manifest.Json/plot.png"),
    ("PAPER.BIB", "%50APER.BIB"),
    ("Manifest.Json/plot.png", "./Manifest.Json/plot.png"),
])
@pytest.mark.parametrize("operation", ["preflight", "export"])
def test_reserved_output_case_variants_fail_before_output(sources, tmp_path, relative, target, operation):
    manuscript, bibliography = sources
    manuscript.write_text(metadata_paper("abstract: '![Plot](" + target + ")'"), encoding="utf-8")
    # Keep fixtures separate from paper.bib even on a case-insensitive filesystem.
    resources = tmp_path / "resources"
    picture = image_bytes(resources / relative)
    original = manuscript.read_bytes(), bibliography.read_bytes()
    document = pandoc_document(manuscript)
    assert any(node.get("t") == "Image" for node in joss._nodes(document["meta"]))
    output = tmp_path / "invalid"

    with pytest.raises(ValueError, match="local relative image paths"):
        if operation == "preflight":
            joss.preflight(manuscript, resource_dir=resources)
        else:
            joss.export(manuscript, output, resource_dir=resources)

    assert not output.exists()
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == original
    assert (resources / relative).read_bytes() == picture


@pytest.mark.parametrize("relative", [
    "Figures/Plot.PNG", "PAPER.BIB.png", "figures/PAPER.BIB", "Manifest.Json.assets/plot.png",
])
def test_reserved_output_case_check_preserves_other_image_paths(sources, tmp_path, relative):
    manuscript, bibliography = sources
    manuscript.write_bytes(("\ufeff" + metadata_paper("abstract: '![Plot](" + relative + ")'"))
                           .replace("\n", "\r\n").encode("utf-8"))
    resources = tmp_path / "resources"
    picture = image_bytes(resources / relative)
    original = manuscript.read_bytes(), bibliography.read_bytes()
    assert joss.preflight(manuscript, resource_dir=resources)["prefilter_passed"]
    output = tmp_path / "delivery"
    result = joss.export(manuscript, output, resource_dir=resources)

    assert result["source_package_passed"] and not result["publisher_pdf_rendered"]
    assert not result["submission_ready"]
    assert (output / "paper.md").read_bytes() == original[0]
    assert (output / "paper.bib").read_bytes() == original[1]
    assert (output / relative).read_bytes() == picture
    rows = json.loads((output / "manifest.json").read_text(encoding="utf-8"))["files"]
    assert {row["path"] for row in rows} == {"paper.md", "paper.bib", "format-report.json", relative}
    for row in rows:
        data = (output / row["path"]).read_bytes()
        assert row["bytes"] == len(data) and row["sha256"] == hashlib.sha256(data).hexdigest()
    assert (manuscript.read_bytes(), bibliography.read_bytes()) == original
    assert (resources / relative).read_bytes() == picture

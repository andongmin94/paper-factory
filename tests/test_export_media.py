"""Portable native Word-export inputs: actual Pandoc; explicit Word/PDF stubs.

The main API has no DOCX-only mode. These tests exercise its existing native
export path without claiming that Microsoft Word or page review ran.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from urllib.parse import unquote
import zipfile

from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import _publication_convert as converter
import export_manuscript as exporter


ARTICLE = """# Retained source images

## Abstract

A retained image supports a bounded software decision.

Keywords: images; software; provenance

## Evidence

The retained source supports this decision [1].

IMAGES

## Actionable insights

- Keep the input.
- Record its source.
- Inspect the output.

## Acknowledgments

OpenAI Codex assisted with analysis and prose throughout this article.

## References

[1] Example Authors, Retained source, 2025.
"""


@pytest.fixture(scope="module")
def pandoc():
    try:
        binary = converter.pandoc_binary()
        converter.pandoc_version(binary)
    except ValueError as exc:
        if os.environ.get("CI", "").casefold() == "true":
            pytest.fail("CI requires actual Pandoc for media export: " + str(exc))
        pytest.skip("An installed Pandoc is required: " + str(exc))
    return str(binary)


@pytest.fixture(autouse=True)
def native_word_stubs(monkeypatch):
    """Stub only unavailable native Word/PDF services, never Pandoc or input IO."""
    def word_stub(docx, pdf, **kwargs):
        assert docx.is_file()
        pdf.write_bytes(b"Synthetic PDF fixture; Microsoft Word was not run")
        return {"source_docx_sha256": exporter.digest_file(docx)}

    def compliance_stub(markdown, docx, venue, **kwargs):
        assert markdown == docx.parent / "manuscript.md"
        assert kwargs["pdf"].is_file()
        return {"content_format_passed": False, "submission_ready": False, "page_qa": None}

    monkeypatch.setattr(exporter, "word_pdf", word_stub)
    monkeypatch.setattr(exporter, "compliance_report", compliance_stub)


def png(path, color="navy"):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 24), color).save(path, format="PNG")
    return path.read_bytes()


def manuscript(directory, images):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "article.md"
    path.write_bytes(("\ufeff" + ARTICLE.replace("IMAGES", images)).replace("\n", "\r\n").encode("utf-8"))
    return path


def embedded_images(docx):
    with zipfile.ZipFile(docx) as document:
        return [document.read(name) for name in document.namelist() if name.startswith("word/media/")]


def assert_retained_image(output, relative, content):
    assert (output / relative).read_bytes() == content
    rows = json.loads((output / "manifest.json").read_text(encoding="utf-8"))["files"]
    matches = [row for row in rows if row["path"] == relative]
    assert len(matches) == 1
    assert matches[0]["sha256"] == hashlib.sha256(content).hexdigest()
    assert matches[0]["bytes"] == len(content)


@pytest.mark.parametrize("relative,markup", [
    ("figures/plot.png", "![Evidence](figures/plot.png)"),
    ("figures/plot one.png", "![Evidence](<figures/plot one.png>)"),
    ("figures/측정 그림.png", "![Evidence](<figures/측정 그림.png>)"),
    ("figures/plot(1).png", "![Evidence](figures/plot(1).png)"),
    ("figures/plot one.png", "![Evidence](figures/plot%20one.png)"),
    ("figures/plot%.png", "![Evidence](figures/plot%25.png)"),
    ("figures/plot%20one.png", "![Evidence](figures/plot%2520one.png)"),
    pytest.param("figures/plot#one.png", "![Evidence](figures/plot%23one.png)", id="encoded-hash"),
    ("figures/그림 (v1).png", "![Evidence][plot]\n\n[plot]: <figures/그림 (v1).png>"),
])
def test_moved_word_source_rebuilds_without_original_images(tmp_path, pandoc, relative, markup):
    source = manuscript(tmp_path / "original", markup)
    picture = png(source.parent / relative)
    source_bytes = source.read_bytes()
    output = tmp_path / "delivery"
    result = exporter.export(source, "ieee-software", output, pandoc=pandoc)
    assert not result["content_format_passed"] and not result["submission_ready"]
    assert Path(result["pdf"]).is_file()
    assert source.read_bytes() == source_bytes == (output / "manuscript.md").read_bytes()
    assert picture in embedded_images(Path(result["docx"]))
    saved_manifest = (output / "manifest.json").read_bytes()
    moved = tmp_path / "relocated" / "delivery"
    moved.parent.mkdir()
    shutil.move(str(output), moved)
    shutil.rmtree(source.parent)
    rebuilt = exporter.export(moved / "manuscript.md", "ieee-software", tmp_path / "rebuilt",
                              pandoc=pandoc)
    assert picture in embedded_images(Path(rebuilt["docx"]))
    assert_retained_image(moved, relative, picture)
    assert_retained_image(tmp_path / "rebuilt", relative, picture)
    assert (moved / "manuscript.md").read_bytes() == source_bytes
    assert (moved / "manifest.json").read_bytes() == saved_manifest


def test_explicit_resource_directory_is_retained_and_rebuilds_independently(tmp_path, pandoc):
    source = manuscript(tmp_path / "prepared", "![Evidence](figures/plot.png)")
    png(source.parent / "figures/plot.png", "red")
    resources = tmp_path / "resources"
    picture = png(resources / "figures/plot.png", "navy")
    output = tmp_path / "delivery"
    result = exporter.export(source, "ieee-software", output, resource_dir=resources,
                             pandoc=pandoc)
    assert picture in embedded_images(Path(result["docx"]))
    moved = tmp_path / "moved"
    shutil.move(str(output), moved)
    shutil.rmtree(source.parent)
    shutil.rmtree(resources)
    rebuilt = exporter.export(moved / "manuscript.md", "ieee-software", tmp_path / "rebuilt",
                              pandoc=pandoc)
    assert picture in embedded_images(Path(rebuilt["docx"]))
    assert_retained_image(moved, "figures/plot.png", picture)


def test_explicit_bundle_rebuilds_export_after_original_and_export_removal(tmp_path, pandoc):
    from submission_support import prepare_bundle
    relative = "figures/측정 그림.png"
    source = manuscript(tmp_path / "original", f"![Evidence][plot]\n\n[plot]: <{relative}>")
    picture = png(source.parent / relative)
    source_bytes = source.read_bytes()
    exported = tmp_path / "exported"
    result = exporter.export(source, "ieee-software", exported, pandoc=pandoc)
    docx_name = Path(result["docx"]).name
    docx_bytes = (exported / docx_name).read_bytes()
    selections = [("manuscript", "manuscript.md"), ("editable_docx", docx_name), ("figure", relative)]
    plan = tmp_path / "bundle-plan.json"
    plan.write_text(json.dumps({
        "venue_id": "ieee-software", "title": "Portable retained image",
        "files": [{"role": role, "path": path} for role, path in selections],
    }, ensure_ascii=False), encoding="utf-8")
    bundle = tmp_path / "bundle"
    report = prepare_bundle(plan, exported, bundle)
    assert not report["submission_ready"] and not report["author_approval_inferred"]
    assert all(row["status"] == "pending" for row in report["declaration_status"].values())
    assert {path.relative_to(bundle / "files").as_posix() for path in (bundle / "files").rglob("*")
            if path.is_file()} == {path for _, path in selections}
    assert (bundle / "files" / docx_name).read_bytes() == docx_bytes
    saved_manifest = (bundle / "manifest.json").read_bytes()
    moved = tmp_path / "moved-bundle"
    shutil.move(str(bundle), moved)
    shutil.rmtree(source.parent)
    shutil.rmtree(exported)
    rebuilt = exporter.export(moved / "files/manuscript.md", "ieee-software", tmp_path / "rebuilt",
                              pandoc=pandoc)
    assert picture in embedded_images(Path(rebuilt["docx"]))
    assert (moved / "files/manuscript.md").read_bytes() == source_bytes
    assert (tmp_path / "rebuilt/manuscript.md").read_bytes() == source_bytes
    assert_retained_image(moved, "files/" + relative, picture)
    assert_retained_image(tmp_path / "rebuilt", relative, picture)
    assert (moved / "manifest.json").read_bytes() == saved_manifest


def test_only_referenced_images_are_copied_once(tmp_path, pandoc):
    source = manuscript(tmp_path / "original", """![First](./figures/plot.png)

![Second][retained]

[retained]: figures/plot.png

`![Literal](missing-inline.png)`

```markdown
![Literal](missing-block.png)
```
""")
    picture = png(source.parent / "figures/plot.png")
    png(source.parent / "unused.png", "red")
    output = tmp_path / "delivery"
    exporter.export(source, "ieee-software", output, pandoc=pandoc)
    assert_retained_image(output, "figures/plot.png", picture)
    assert not any((output / name).exists() for name in ("unused.png", "missing-inline.png", "missing-block.png"))


@pytest.mark.parametrize("kind", ["missing", "directory", "empty", "corrupt"])
def test_invalid_local_images_cannot_finish_export(tmp_path, pandoc, kind):
    source = manuscript(tmp_path / "original", "![Evidence](figure.png)")
    picture = source.parent / "figure.png"
    if kind == "directory":
        picture.mkdir()
    elif kind == "empty":
        picture.write_bytes(b"")
    elif kind == "corrupt":
        picture.write_bytes(b"This is not a PNG image.")
    original = source.read_bytes()
    output = tmp_path / "delivery"
    with pytest.raises((ValueError, OSError)) as failure:
        exporter.export(source, "ieee-software", output, pandoc=pandoc)
    if kind == "missing":
        assert "figure.png" in str(failure.value)
    assert source.read_bytes() == original
    assert not (output / "manifest.json").exists()
    assert not (output / "provenance.json").exists()


@pytest.mark.parametrize("target", ["../outside.png", "%2e%2e/outside.png"])
def test_image_traversal_is_rejected_without_copying_external_files(tmp_path, pandoc, target):
    outside = tmp_path / "outside.png"
    picture = png(outside)
    source = manuscript(tmp_path / "original", f"![Evidence]({target})")
    original = source.read_bytes()
    output = tmp_path / "delivery"
    with pytest.raises(ValueError):
        exporter.export(source, "ieee-software", output, pandoc=pandoc)
    assert outside.read_bytes() == picture and source.read_bytes() == original
    assert not (output / "manifest.json").exists()


@pytest.mark.parametrize("directory_link", [False, True])
def test_image_symlinks_are_rejected(tmp_path, pandoc, directory_link):
    source = manuscript(tmp_path / "original", "![Evidence](figures/plot.png)")
    outside = tmp_path / "outside" / "plot.png"
    original = png(outside)
    link = source.parent / "figures" if directory_link else source.parent / "figures" / "plot.png"
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(outside.parent if directory_link else outside, target_is_directory=directory_link)
    except OSError as exc:
        pytest.skip("This test environment cannot create a symlink: " + str(exc))
    output = tmp_path / "delivery"
    with pytest.raises(ValueError, match="(?i)symlink|junction|reparse"):
        exporter.export(source, "ieee-software", output, pandoc=pandoc)
    assert outside.read_bytes() == original
    assert not (output / "manifest.json").exists()


@pytest.mark.parametrize("target", [
    "manuscript.md", "MANIFEST.JSON", "manuscript-ieee-software.docx", "pages/page-001.png",
])
def test_images_cannot_collide_with_generated_output_names(tmp_path, pandoc, target):
    source = manuscript(tmp_path / "original", f"![Evidence]({target})")
    original = png(source.parent / target)
    output = tmp_path / "delivery"
    with pytest.raises(ValueError, match="(?i)collision|reserved|conflict"):
        exporter.export(source, "ieee-software", output, pandoc=pandoc)
    assert (source.parent / target).read_bytes() == original
    assert not (output / "manifest.json").exists()


@pytest.mark.parametrize("paths", [
    ("figures/plot.png", "figures/PLOT.png"),
    ("figures/one.png", "Figures/two.png"),
    ("figures", "FIGURES/plot.png"),
])
def test_image_file_and_directory_casefold_collisions_are_rejected(tmp_path, pandoc, paths):
    source = manuscript(tmp_path / "original", "\n\n".join(f"![Evidence]({path})" for path in paths))
    try:
        for index, path in enumerate(paths):
            png(source.parent / path, "navy" if index else "red")
    except (FileExistsError, NotADirectoryError):
        pytest.skip("The filesystem cannot represent this conflicting file/directory fixture")
    before = {path: (source.parent / path).read_bytes() for path in paths}
    output = tmp_path / "delivery"
    with pytest.raises(ValueError, match="(?i)collision|reserved|conflict"):
        exporter.export(source, "ieee-software", output, pandoc=pandoc)
    assert all((source.parent / path).read_bytes() == data for path, data in before.items())
    assert not (output / "manifest.json").exists()


@pytest.mark.parametrize("target", [
    "https://example.invalid/plot.png", "/outside.png", "C:/plot.png", "C%3A/plot.png", "figures%5Cplot.png",
])
def test_unsupported_image_paths_fail_before_conversion_or_fetch(tmp_path, pandoc, monkeypatch, target):
    source = manuscript(tmp_path / "original", f"![Evidence]({target})")
    def unexpected_conversion(*args, **kwargs):
        pytest.fail("Unsupported image paths must be rejected before image conversion or retrieval")
    monkeypatch.setattr(exporter, "convert_docx", unexpected_conversion)
    output = tmp_path / "delivery"
    with pytest.raises(ValueError):
        exporter.export(source, "ieee-software", output, pandoc=pandoc)
    assert not (output / "manifest.json").exists()


@pytest.mark.parametrize("target", [
    "figures/plot%3F.png", "figures/plot%2A.png", "figures/CON.png",
    "figures/LPT¹.png", "figures./plot.png", "figures%20/plot.png",
])
def test_nonportable_windows_image_names_are_rejected_before_lookup(tmp_path, pandoc, monkeypatch, target):
    source = manuscript(tmp_path / "original", f"![Evidence]({target})")
    invalid_path = source.parent / unquote(target)
    ensure_unlinked = converter.ensure_unlinked
    def guard_lookup(path):
        if path == invalid_path:
            pytest.fail("Nonportable image names must be rejected before filesystem lookup")
        ensure_unlinked(path)
    def unexpected_conversion(*args, **kwargs):
        pytest.fail("Nonportable image names must be rejected before conversion")
    monkeypatch.setattr(converter, "ensure_unlinked", guard_lookup)
    monkeypatch.setattr(exporter, "convert_docx", unexpected_conversion)
    output = tmp_path / "delivery"
    with pytest.raises(ValueError) as failure:
        exporter.export(source, "ieee-software", output, pandoc=pandoc)
    reason = str(failure.value).split(":", 1)[0].casefold()
    assert any(word in reason for word in ("portable", "reserved", "filename", "windows"))
    assert not (output / "manifest.json").exists()


def test_native_export_retains_images_before_stubbed_word_rendering(tmp_path, pandoc, monkeypatch):
    """Actual DOCX conversion; Word/PDF rendering and native compliance are explicit stubs."""
    source = manuscript(tmp_path / "original", "![Evidence](figures/plot.png)")
    picture = png(source.parent / "figures/plot.png")
    output = tmp_path / "delivery"
    calls = []
    def word_stub(docx, pdf, **kwargs):
        assert (output / "figures/plot.png").read_bytes() == picture
        assert picture in embedded_images(docx)
        pdf.write_bytes(b"Synthetic PDF fixture; Microsoft Word was not run")
        calls.append("word")
        return {"source_docx_sha256": exporter.digest_file(docx)}
    def compliance_stub(markdown, docx, venue, **kwargs):
        assert markdown == output / "manuscript.md"
        assert (markdown.parent / "figures/plot.png").read_bytes() == picture
        calls.append("compliance")
        return {"content_format_passed": False, "submission_ready": False, "page_qa": None}
    monkeypatch.setattr(exporter, "word_pdf", word_stub)
    monkeypatch.setattr(exporter, "compliance_report", compliance_stub)
    result = exporter.export(source, "ieee-software", output, pandoc=pandoc)
    assert calls == ["word", "compliance"] and not result["submission_ready"]
    assert_retained_image(output, "figures/plot.png", picture)


@pytest.mark.parametrize("change_original", [False, True])
def test_media_changed_during_conversion_cannot_finish_export(tmp_path, pandoc, monkeypatch, change_original):
    source = manuscript(tmp_path / "original", "![Evidence](figures/plot.png)")
    png(source.parent / "figures/plot.png")
    output = tmp_path / "delivery"
    actual_convert = exporter.convert_docx
    def convert_then_change(markdown, docx, **kwargs):
        result = actual_convert(markdown, docx, **kwargs)
        path = source.parent / "figures/plot.png" if change_original else output / "figures/plot.png"
        png(path, "red")
        return result
    monkeypatch.setattr(exporter, "convert_docx", convert_then_change)
    with pytest.raises(ValueError, match="(?i)chang|differ|hash"):
        exporter.export(source, "ieee-software", output, pandoc=pandoc)
    assert not (output / "manifest.json").exists()
    assert not (output / "provenance.json").exists()

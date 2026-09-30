from pathlib import Path
import subprocess
from types import SimpleNamespace
import zipfile

import pytest

from paper_factory import conversion
from paper_factory.workspace import digest_file


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "article.md"
    path.write_text("# Export contract\n\n## Results\n\nThe document preserves its verified prose and visible section structure.\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("enabled", [False, True])
def test_docx_export_uses_native_line_and_page_settings(source, pandoc, enabled):
    docx = pytest.importorskip("docx")
    from docx.oxml.ns import qn
    output = source.with_suffix(".docx")
    report = conversion.convert(source, output, pandoc=pandoc, line_numbers=enabled, page_numbers=enabled)
    document = docx.Document(output)
    assert "Export contract" in " ".join(paragraph.text for paragraph in document.paragraphs)
    for section in document.sections:
        numbers = section._sectPr.findall(qn("w:lnNumType"))
        assert bool(numbers) is enabled
        if enabled:
            assert numbers[0].get(qn("w:restart")) == "continuous"
            assert numbers[0].get(qn("w:countBy")) == "1"
        for footer in (section.footer, section.first_page_footer, section.even_page_footer):
            fields = [field for field in footer._element.iter(qn("w:fldSimple")) if field.get(qn("w:instr")) == "PAGE"]
            assert bool(fields) is enabled
    with zipfile.ZipFile(output) as archive:
        assert "word/document.xml" in archive.namelist()
    assert report["output_sha256"] == digest_file(output)


@pytest.mark.parametrize("enabled", [False, True])
def test_latex_export_uses_native_line_and_page_settings(source, pandoc, enabled):
    output = source.with_suffix(".tex")
    conversion.convert(source, output, pandoc=pandoc, line_numbers=enabled, page_numbers=enabled)
    text = output.read_text(encoding="utf-8")
    assert "Export contract" in text
    assert (r"\usepackage{lineno}" in text) is enabled
    assert (r"\linenumbers" in text) is enabled
    assert (r"\pagestyle{empty}" in text) is not enabled


@pytest.mark.parametrize("enabled", [False, True])
def test_pdf_export_native_numbering_matches_requested_flags(source, pandoc, enabled):
    pytest.importorskip("typst")
    from pypdf import PdfReader
    output = source.with_suffix(".pdf")
    conversion.convert(source, output, pandoc=pandoc, line_numbers=enabled, page_numbers=enabled)
    typst = output.with_suffix(".typ").read_text(encoding="utf-8")
    assert ('set par.line(numbering: "1"' in typst) is enabled
    assert ('set page(numbering: none)' in typst) is not enabled
    text = " ".join(page.extract_text() or "" for page in PdfReader(output).pages)
    assert "Export contract" in text and "visible section structure" in text
    if not enabled:
        assert not any(character.isdigit() for character in text)


def test_missing_converter_cannot_leave_a_stale_successful_artifact(source, monkeypatch):
    output = source.with_suffix(".tex")
    output.write_text("stale successful export", encoding="utf-8")
    monkeypatch.setattr(conversion.shutil, "which", lambda _: None)
    with pytest.raises(ValueError, match="Pandoc is required"):
        conversion.convert(source, output)
    assert not output.exists()


@pytest.mark.parametrize("suffix", [".tex", ".pdf"])
def test_timeout_removes_partial_export_and_stale_output(source, monkeypatch, suffix):
    output = source.with_suffix(suffix)
    output.write_bytes(b"stale output")
    monkeypatch.setattr(conversion, "pandoc_binary", lambda _: "test-pandoc")

    def timeout(command, **kwargs):
        Path(command[command.index("-o") + 1]).write_text("partial output", encoding="utf-8")
        raise subprocess.TimeoutExpired(command, 120)

    monkeypatch.setattr(conversion.subprocess, "run", timeout)
    with pytest.raises(ValueError, match="timed out"):
        conversion.convert(source, output)
    assert not output.exists()
    assert not (output.with_suffix(".typ") if suffix == ".pdf" else output).exists()


def test_nonzero_converter_failure_removes_partial_export_and_keeps_diagnostics(source, monkeypatch):
    output = source.with_suffix(".tex")
    monkeypatch.setattr(conversion, "pandoc_binary", lambda _: "test-pandoc")

    def failed(command, **kwargs):
        Path(command[command.index("-o") + 1]).write_text("partial output", encoding="utf-8")
        return SimpleNamespace(returncode=9, stderr="actual parser diagnostic")

    monkeypatch.setattr(conversion.subprocess, "run", failed)
    with pytest.raises(ValueError, match=r"Pandoc failed \(9\): actual parser diagnostic"):
        conversion.convert(source, output)
    assert not output.exists()


def test_invalid_docx_export_is_removed_after_independent_reopen(source, monkeypatch):
    pytest.importorskip("docx")
    output = source.with_suffix(".docx")
    monkeypatch.setattr(conversion, "pandoc_binary", lambda _: "test-pandoc")

    def broken(command, **kwargs):
        Path(command[command.index("-o") + 1]).write_text("successful exit with invalid DOCX", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(conversion.subprocess, "run", broken)
    with pytest.raises(ValueError, match="Word document formatting failed"):
        conversion.convert(source, output)
    assert not output.exists()


def test_pdf_engine_failure_removes_partial_pdf_and_retains_debug_source(source, monkeypatch):
    typst = pytest.importorskip("typst")
    output = source.with_suffix(".pdf")
    monkeypatch.setattr(conversion, "pandoc_binary", lambda _: "test-pandoc")

    def generated(command, **kwargs):
        Path(command[command.index("-o") + 1]).write_text("Generated debug source", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    def failed(path, **kwargs):
        Path(kwargs["output"]).write_bytes(b"partial PDF")
        raise RuntimeError("actual engine diagnostic")

    monkeypatch.setattr(conversion.subprocess, "run", generated)
    monkeypatch.setattr(typst, "compile", failed)
    with pytest.raises(ValueError, match="actual engine diagnostic"):
        conversion.convert(source, output)
    assert not output.exists()
    assert "Generated debug source" in output.with_suffix(".typ").read_text(encoding="utf-8")

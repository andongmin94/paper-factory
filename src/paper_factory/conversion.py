"""Convert using Pandoc and the explicitly selected native PDF engine."""

import json
import hashlib
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .workspace import digest_file, write_json


def verify_receipts(markdown: Path, outputs: dict[str, Path], receipt_path: Path) -> list[str]:
    """Bind native exports to their recorded source and conversion output."""
    reports = json.loads(receipt_path.read_bytes())
    if not isinstance(reports, dict) or set(reports) != set(outputs):
        return ["Conversion receipt format set differs from the required exports"]
    source_digest = digest_file(markdown)
    errors = []
    for format, output in outputs.items():
        report = reports[format]
        if (not isinstance(report, dict) or report.get("input_sha256") != source_digest
                or report.get("output_sha256") != digest_file(output)):
            errors.append(f"Conversion receipt differs from its source or native output: {format}")
    return errors


def _format_docx(output: Path, *, line_numbers: bool, page_numbers: bool) -> None:
    """Use python-docx for native Word settings, keeping Pandoc's content."""
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
    except ImportError as exc:
        raise ValueError("Install the PDF/package extra for Word formatting: pip install -e '.[pdf]'") from exc
    document = Document(output)
    for section in document.sections:
        for old in section._sectPr.findall(qn("w:lnNumType")):
            section._sectPr.remove(old)
        if line_numbers:
            numbers = OxmlElement("w:lnNumType")
            numbers.set(qn("w:countBy"), "1")
            numbers.set(qn("w:restart"), "continuous")
            section._sectPr.insert_element_before(numbers, "w:pgNumType", "w:cols", "w:docGrid")
        section.different_first_page_header_footer = False
        for footer in (section.footer, section.first_page_footer, section.even_page_footer):
            footer.is_linked_to_previous = False
            for child in list(footer._element):
                footer._element.remove(child)
            paragraph = footer.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if page_numbers:
                field = OxmlElement("w:fldSimple")
                field.set(qn("w:instr"), "PAGE")
                run = OxmlElement("w:r")
                text = OxmlElement("w:t")
                text.text = "1"
                run.append(text)
                field.append(run)
                paragraph._p.append(field)
    document.save(output)
    # Independently reopen the output rather than accepting a successful save.
    checked = Document(output)
    if not checked.paragraphs:
        raise ValueError("Compiled Word document has no paragraphs")
    for section in checked.sections:
        if bool(section._sectPr.findall(qn("w:lnNumType"))) != line_numbers:
            raise ValueError("Word line-number setting differs from policy")
        actual = any(field.get(qn("w:instr")) == "PAGE" for field in section.footer._element.iter(qn("w:fldSimple")))
        if actual != page_numbers:
            raise ValueError("Word page-number field differs from policy")


def pandoc_binary(explicit: str | None = None) -> str:
    explicit = explicit or os.environ.get("PYPANDOC_PANDOC") or None
    binary = shutil.which(explicit or "pandoc")
    if not binary and not explicit:
        try:
            import pypandoc
            binary = pypandoc.get_pandoc_path()
        except (ImportError, OSError):
            pass
    if binary and not Path(binary).is_file() and Path(binary).with_suffix(".exe").is_file():
        binary = str(Path(binary).with_suffix(".exe"))
    if not binary or not Path(binary).is_file():
        raise ValueError("Pandoc is required. Install the pdf extra or pass --pandoc <executable>.")
    return str(Path(binary).resolve())


def convert(markdown: Path, output: Path, *, pandoc: str | None = None, bibliography: Path | None = None, csl: Path | None = None, metadata: dict | None = None, line_numbers: bool = False, page_numbers: bool = True, pdf_engine: str | None = None, pdflatex: str | None = None) -> dict:
    suffix = output.suffix.lower()
    if suffix not in {".pdf", ".tex", ".docx"}:
        raise ValueError("Supported conversion outputs: PDF, LaTeX and DOCX")
    pdf_engine = pdf_engine or os.environ.get("PF_PDF_ENGINE", "typst")
    if pdf_engine not in {"typst", "pdflatex"}:
        raise ValueError("Select the PDF engine explicitly: typst or pdflatex")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    target = (output.with_suffix(".typ") if pdf_engine == "typst" else output.with_suffix(".pdflatex.tex")) if suffix == ".pdf" else output
    target.unlink(missing_ok=True)
    binary = pandoc_binary(pandoc)
    source_digest = digest_file(markdown)
    format = ("typst" if pdf_engine == "typst" else "latex") if suffix == ".pdf" else {".tex": "latex", ".docx": "docx"}[suffix]
    command = [binary, str(markdown.resolve()), "--from=markdown-smart-raw_tex-raw_html", "--standalone", "--to=" + format, "-o", str(target.resolve())]
    if bibliography:
        command += ["--citeproc", "--bibliography", str(bibliography.resolve())]
    if csl:
        command += ["--csl", str(csl.resolve())]
    if suffix == ".pdf" and pdf_engine == "typst":
        metadata = {**(metadata or {}), "margin": {"x": "1in", "y": "1in"}, "page-numbering": "1" if page_numbers else None}
    elif format == "latex":
        headers = []
        if line_numbers:
            headers += [r"\usepackage{lineno}", r"\linenumbers"]
        if not page_numbers:
            headers.append(r"\pagestyle{empty}")
        if headers:
            # The source reader disables raw TeX; Pandoc's explicit header input
            # inserts these trusted native settings without treating them as prose.
            header_path = output.with_name(f"{output.stem}-formatting.tex")
            header_path.write_text("\n".join(headers) + "\n", encoding="utf-8")
            command += ["--include-in-header", str(header_path.resolve())]
    if metadata:
        metadata_path = output.parent / f"{output.stem}-pandoc-metadata.json"
        write_json(metadata_path, metadata)
        command += ["--metadata-file", str(metadata_path.resolve())]
    if suffix == ".pdf" and pdf_engine == "typst":
        # Typst headings end at a source newline. Let Typst perform visual
        # wrapping without turning Pandoc's continued title into body text.
        command += ["--wrap=none", "-V", "papersize:a4", "-V", "fontsize:11pt"]
    else:
        command += ["-V", "geometry:margin=1in"]
    try:
        result = subprocess.run(command, cwd=markdown.parent, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, check=False)
    except subprocess.TimeoutExpired as exc:
        target.unlink(missing_ok=True)
        raise ValueError("Pandoc conversion timed out after 120 seconds") from exc
    if result.returncode != 0 or not target.is_file():
        target.unlink(missing_ok=True)
        raise ValueError(f"Pandoc failed ({result.returncode}): {result.stderr[:2000]}")
    engine = "Pandoc"
    engine_commands = []
    engine_passes = []
    engine_identity = None
    if suffix == ".docx":
        try:
            _format_docx(output, line_numbers=line_numbers, page_numbers=page_numbers)
        except Exception as exc:
            output.unlink(missing_ok=True)
            raise ValueError(f"Word document formatting failed: {exc}") from exc
        engine = "Pandoc → python-docx"
    if suffix == ".pdf" and pdf_engine == "typst":
        try:
            import typst
        except ImportError as exc:
            raise ValueError("Install the PDF extra: pip install -e '.[pdf]' (Typst and pypdf)") from exc
        try:
            typst_source = target.read_text(encoding="utf-8")
            settings = '\nset page(numbering: "1")\n' if page_numbers else '\nset page(numbering: none)\n'
            if line_numbers:
                settings += 'set par.line(numbering: "1", numbering-scope: "document")\n'
            # Native rules apply to the complete generated document.
            target.write_text('#show: body => {\n' + settings + 'body\n}\n' + typst_source, encoding="utf-8")
            # Pandoc generates the source; Typst's sandbox root is this directory.
            typst.compile(str(target), output=str(output), root=str(output.parent), timestamp=datetime(2000, 1, 1, tzinfo=timezone.utc))
        except Exception as exc:
            output.unlink(missing_ok=True)
            raise ValueError(f"Typst PDF compilation failed: {exc}") from exc
        engine = "Pandoc → Typst"
    elif suffix == ".pdf":
        selected = pdflatex or os.environ.get("PF_PDFLATEX_BIN")
        latex = Path(selected) if selected else None
        if latex is None or not latex.is_absolute() or not latex.is_file():
            raise ValueError("The selected pdflatex PDF engine requires its verified absolute executable path")
        # Keep the invocation alias: TeX binaries select their format from argv[0].
        # Resolving /usr/bin/pdflatex to pdftex changes its behavior.
        engine_identity = {"path": str(latex), "target_path": str(latex.resolve()), "sha256": digest_file(latex)}
        compiled = target.with_suffix(".pdf")
        compiled.unlink(missing_ok=True)
        engine_command = [str(latex), "-no-shell-escape", "-halt-on-error", "-interaction=nonstopmode",
                          "-output-directory=" + str(output.parent.resolve()), str(target.resolve())]
        try:
            for _ in range(2):
                engine_commands.append(list(engine_command))
                native = subprocess.run(engine_command, cwd=output.parent, capture_output=True,
                                        timeout=120, check=False)
                engine_passes.append({"command": list(engine_command), "exit_code": native.returncode,
                                      "stdout_sha256": hashlib.sha256(native.stdout).hexdigest(),
                                      "stderr_sha256": hashlib.sha256(native.stderr).hexdigest(),
                                      "stdout_bytes": len(native.stdout), "stderr_bytes": len(native.stderr),
                                      "stdout": native.stdout.decode("utf-8", errors="replace")[-4000:],
                                      "stderr": native.stderr.decode("utf-8", errors="replace")[-2000:]})
                if native.returncode != 0 or not compiled.is_file():
                    raise ValueError(f"pdflatex failed ({native.returncode}): {engine_passes[-1]['stdout'][-2000:]}")
            if digest_file(latex) != engine_identity["sha256"] or str(latex.resolve()) != engine_identity["target_path"]:
                raise ValueError("Selected pdflatex executable changed during conversion")
            compiled.replace(output)
        except Exception as exc:
            compiled.unlink(missing_ok=True)
            output.unlink(missing_ok=True)
            raise ValueError(f"pdflatex PDF compilation failed: {exc}") from exc
        engine = "Pandoc → pdflatex"
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(output)
            if not output.read_bytes().startswith(b"%PDF-") or not reader.pages or reader.is_encrypted:
                raise ValueError("Compiled PDF is empty, encrypted or invalid")
        except Exception as exc:
            output.unlink(missing_ok=True)
            raise ValueError(f"Compiled PDF validation failed: {exc}") from exc
    if digest_file(markdown) != source_digest:
        output.unlink(missing_ok=True)
        raise ValueError("Manuscript changed during conversion")
    receipt = {"command": command, "engine": engine, "input_sha256": source_digest,
               "output_sha256": digest_file(output), "diagnostics": result.stderr}
    if engine_identity is not None:
        receipt.update(engine_commands=engine_commands, engine_passes=engine_passes, engine_executable=engine_identity,
                       engine_source_sha256=digest_file(target))
    return receipt

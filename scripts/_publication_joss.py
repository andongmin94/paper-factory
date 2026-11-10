"""Prepare JOSS's Markdown/BibTeX source submission without claiming PDF output."""

from datetime import datetime
from html.parser import HTMLParser
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import unquote, urlsplit

from _publication_convert import pandoc_binary, pandoc_version
from _publication_files import digest_file, ensure_unlinked
from _publication_templates import official_template
from import_references import parse_bibliography


GUIDANCE_URL = "https://joss.readthedocs.io/en/latest/paper.html"
SUBMISSION_URL = "https://joss.readthedocs.io/en/latest/submitting.html"
CHECKED_AT = "2026-11-02"
SECTIONS = ("summary", "statement of need", "state of the field", "software design",
            "research impact statement", "ai usage disclosure", "references")


def _text(value):
    """Read visible Pandoc text, excluding code, raw markup and attributes."""
    if isinstance(value, list):
        return "".join(_text(item) for item in value)
    if not isinstance(value, dict):
        return ""
    kind, content = value.get("t"), value.get("c")
    if kind in {"Str", "MetaString"}:
        return content
    if kind in {"Space", "SoftBreak", "LineBreak"}:
        return " "
    if kind in {"Code", "CodeBlock", "RawInline", "RawBlock"}:
        return ""
    text = _text(content)
    return text + " " if kind in {"Para", "Plain", "Header"} else text


def _nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nodes(child)


def _citation_keys(value):
    """Read actual Pandoc Cite identifiers without interpreting literal text."""
    return {citation["citationId"] for node in _nodes(value) if node.get("t") == "Cite"
            for citation in node["c"][0]}


def _entries(value):
    return value.get("c", []) if isinstance(value, dict) and value.get("t") == "MetaList" else []


def _fields(value):
    return value.get("c", {}) if isinstance(value, dict) and value.get("t") == "MetaMap" else {}


def _author_name(author):
    """Read supplied display names or structured fields in Inara's order."""
    name = author.get("name")
    fields = _fields(name) if name is not None else author
    if name is not None and not fields:
        return _text(name).strip()
    if "name" in fields or "literal" in fields:
        return _text(fields.get("name", fields.get("literal"))).strip()
    parts = [next((fields[key] for key in aliases if key in fields), None)
             for aliases in (("given-names", "given", "given_name", "first", "firstname"),
                             ("dropping-particle",), ("non-dropping-particle",),
                             ("surname", "family_name", "family", "last", "lastname"),
                             ("suffix",))]
    return " ".join(_text(part).strip() for part in parts if part is not None).strip()


class _HTMLImage(HTMLParser):
    found = False

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.found = True


def _raw_image(node):
    if node.get("t") not in {"RawInline", "RawBlock"}:
        return False
    fmt, source = node["c"]
    if fmt == "html":
        parser = _HTMLImage()
        parser.feed(source)
        return parser.found
    if fmt in {"tex", "latex"}:
        # Only direct graphics commands; ignore literal examples and TeX comments.
        source = re.sub(r"\\begin\{verbatim\*?\}.*?\\end\{verbatim\*?\}", "", source, flags=re.S)
        source = re.sub(r"\\verb\*?([^a-zA-Z\s]).*?\1|(?<!\\)%[^\n]*", "", source)
        return bool(re.search(r"(?<!\\)\\includegraphics\s*\*?\s*[\[{]", source))
    return False


def _inspect(manuscript, *, bibliography=None, pandoc=None, resource_dir=None):
    ensure_unlinked(manuscript)
    if manuscript.suffix.lower() != ".md":
        raise ValueError("JOSS requires an authored Markdown manuscript")
    source = manuscript.read_bytes()
    text = source.decode("utf-8-sig")
    if not text.strip():
        raise ValueError("The canonical manuscript is empty")
    template_path, template = official_template("joss")
    binary = pandoc_binary(pandoc)
    version = pandoc_version(binary)
    command = [str(binary), "--from=markdown", "--to=json", "--standalone", "--fail-if-warnings"]
    try:
        parsed = subprocess.run(command, input=text, cwd=manuscript.parent.resolve(),
                                capture_output=True, text=True, encoding="utf-8", timeout=30,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Pandoc timed out while reading JOSS Markdown") from exc
    if parsed.returncode:
        raise ValueError("Pandoc could not parse JOSS Markdown: " + parsed.stderr[:2000])
    document = json.loads(parsed.stdout)
    metadata, blocks = document["meta"], document["blocks"]
    items = []

    def item(name, passed, detail):
        items.append({"id": name, "status": "passed" if passed else "failed", "reason": detail,
                      "stage": "source", "source_url": GUIDANCE_URL})

    item("title", bool(_text(metadata.get("title")).strip()), "Supply the actual article title in YAML metadata.")
    affiliations = [_fields(value) for value in _entries(metadata.get("affiliations"))]
    indexes = [_text(value.get("index")).strip() for value in affiliations]
    item("affiliations", bool(affiliations) and all(indexes) and len(indexes) == len(set(indexes))
         and all(_text(value.get("name")).strip() for value in affiliations),
         "Supply uniquely indexed, named affiliations in YAML metadata.")
    authors = [_fields(value) for value in _entries(metadata.get("authors"))]
    author_rows = []
    for author in authors:
        affiliation = author.get("affiliation")
        supplied = (_entries(affiliation) if isinstance(affiliation, dict) and affiliation.get("t") == "MetaList"
                    else [affiliation])
        assigned = [index.strip() for value in supplied for index in _text(value).split(",")]
        name = _author_name(author)
        author_rows.append({"name": name, "affiliations": assigned,
                            "valid": bool(name and assigned and all(index in indexes for index in assigned))})
    item("authors", bool(author_rows) and all(row["valid"] for row in author_rows),
         "Supply each author's name and affiliation index or indices; these are supplied facts, not verified identity or consent.")
    date = _text(metadata.get("date")).strip()
    try:
        datetime.strptime(date, "%d %B %Y")
        valid_date = True
    except ValueError:
        valid_date = False
    item("date", valid_date, "Use an actual date in day Month year form, for example 2 November 2026.")
    item("bibliography_metadata", _text(metadata.get("bibliography")).strip() == "paper.bib",
         "The source bundle requires bibliography: paper.bib in YAML metadata.")

    headings = [(index, _text(block["c"][2]).strip().casefold()) for index, block in enumerate(blocks)
                if block["t"] == "Header" and block["c"][0] == 1]
    for section in SECTIONS:
        positions = [index for index, heading in headings if heading == section]
        nonempty = False
        if len(positions) == 1:
            start = positions[0]
            end = next((index for index, _ in headings if index > start), len(blocks))
            nonempty = bool(_text(blocks[start + 1:end]).strip()) or section == "references"
        item("section_" + section.replace(" ", "_"), len(positions) == 1 and nonempty,
             "Provide one top-level " + section.title() + " section" +
             ("; Pandoc creates entries from paper.bib." if section == "references" else " with authored content."))
    prose, in_references = [], False
    for block in blocks:
        if block["t"] == "Header" and block["c"][0] == 1:
            in_references = _text(block["c"][2]).strip().casefold() == "references"
        if not in_references:
            prose.append(block)
    word_count = len(_text(prose).split())
    item("word_count", 750 <= word_count <= 1750,
         f"Prose estimate excluding YAML, references and code: {word_count} words; current JOSS range is 750–1750.")

    bibliography = bibliography if bibliography is not None else manuscript.parent / "paper.bib"
    ensure_unlinked(bibliography)
    bib_bytes = bibliography.read_bytes()
    imported = parse_bibliography(bib_bytes.decode("utf-8-sig"), "bibtex")
    keys = [row["source"]["key"] for row in imported["references"]]
    cited = sorted(_citation_keys(blocks))
    metadata_cited = _citation_keys({name: value for name, value in metadata.items() if name != "nocite"})
    # Only top-level nocite uses '*' to select every retained bibliography entry.
    nocited = _citation_keys(metadata.get("nocite")) - {"*"}
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    missing = sorted((set(cited) | metadata_cited | nocited) - set(keys))
    item("bibliography_keys", not duplicates, "Duplicate BibTeX keys: " + str(duplicates))
    item("citation_keys", bool(cited) and not missing,
         "Cite retained paper.bib entries in the body; unresolved keys in body, metadata or nocite: " + str(missing))

    root = manuscript.parent if resource_dir is None else resource_dir
    ensure_unlinked(root)
    if resource_dir is not None and (not root.is_absolute() or not root.is_dir()):
        raise ValueError("Resource directory must be an existing absolute directory")
    files = {"paper.md": (manuscript, source), "paper.bib": (bibliography, bib_bytes)}
    # YAML strings are Markdown too; retain their Image dependencies with the body.
    images = sorted({node["c"][-1][0] for node in _nodes(document) if node.get("t") == "Image"})
    for target in images:
        parsed_target = urlsplit(target)
        relative = PurePosixPath(unquote(parsed_target.path))
        if (parsed_target.scheme or parsed_target.netloc or parsed_target.query or parsed_target.fragment
                or relative.is_absolute() or ".." in relative.parts or "\\" in str(relative)
                or not relative.parts or relative.parts[0].casefold() in {"paper.md", "paper.bib", "format-report.json", "manifest.json"}):
            raise ValueError("Use local relative image paths inside the source bundle: " + target)
        path = root.joinpath(*relative.parts)
        ensure_unlinked(path)
        data = path.read_bytes()
        if not data:
            raise ValueError("Referenced image is empty: " + target)
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp"}:
            from PIL import Image
            with Image.open(BytesIO(data)) as image:
                image.verify()
        files[relative.as_posix()] = (path, data)
    raw_image = any(_raw_image(node) for node in _nodes(document))
    item("local_images", not raw_image,
         "Use Markdown image syntax ![Caption](figures/plot.png) instead of raw TeX/HTML to include figures in the source bundle."
         if raw_image else f"Retain the actual bytes of {len(images)} local referenced images; layout is not rendered.")
    blockers = [row["reason"] for row in items if row["status"] == "failed"]
    report = {"venue_id": "joss", "mode": "joss_source_preflight", "checked_at": CHECKED_AT,
              "source_urls": [GUIDANCE_URL, SUBMISSION_URL], "items": items, "blockers": blockers,
              "metrics": {"prose_words_estimate": word_count, "reference_count": len(keys),
                          "citation_keys": cited, "authors": author_rows, "image_count": len(images)},
              "official_template": {**template, "path": str(template_path.resolve()),
                                    "usage": "Verified publisher Markdown schema reference; authored source is preserved, not replaced by the example."},
              "pandoc": {"path": str(binary), "version": version},
              "manuscript_sha256": hashlib.sha256(source).hexdigest(),
              "bibliography_sha256": hashlib.sha256(bib_bytes).hexdigest(),
              "bibliography_review": imported["structural_findings"] + [row for row in imported["manual_review_suggestions"]
                                                                       if row["code"] != "reference_numbering_check"],
              "prefilter_passed": not blockers, "source_format_passed": not blockers, "source_package_passed": not blockers,
              "content_format_passed": not blockers, "submission_ready": False,
              "native_word_measured": False, "publisher_pdf_rendered": False, "visual_review_status": "not_rendered",
              "author_approval_inferred": False, "actual_submission_performed": False, "model_calls_made_by_tool": 0,
              "pending": ["Verify current software eligibility, research impact and public development history.",
                          "Confirm actual author facts, rights and complete AI-use disclosure, including human verification.",
                          "Render with the official Open Journals publisher pipeline and inspect every final page."],
              "scope": "JOSS Markdown/BibTeX source preparation only; no Word, publisher PDF, scientific verdict or author approval."}
    for path, data in files.values():
        if path.read_bytes() != data:
            raise ValueError("A JOSS source file changed during preflight")
    return report, files


def preflight(manuscript: Path, *, bibliography: Path | None = None, pandoc: str | None = None,
              resource_dir: Path | None = None) -> dict:
    return _inspect(manuscript, bibliography=bibliography, pandoc=pandoc, resource_dir=resource_dir)[0]


def export(manuscript: Path, output_dir: Path, *, bibliography: Path | None = None,
           pandoc: str | None = None, resource_dir: Path | None = None) -> dict:
    ensure_unlinked(output_dir)
    if output_dir.exists():
        raise ValueError("Output directory must be new")
    report, files = _inspect(manuscript, bibliography=bibliography, pandoc=pandoc, resource_dir=resource_dir)
    if not report["prefilter_passed"]:
        raise ValueError("JOSS source preflight failed: " + "; ".join(report["blockers"]))
    output_dir.mkdir(parents=True, exist_ok=False)
    for relative, (source, data) in files.items():
        target = output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
    for source, data in files.values():
        if source.read_bytes() != data:
            raise ValueError("A JOSS source file changed during export; partial output retained for diagnosis")
    report["mode"] = "joss_source_export"
    with (output_dir / "format-report.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    manifest = {"algorithm": "SHA-256", "scope": "JOSS source bundle; excludes this manifest; no publisher PDF generated.",
                "files": [{"path": path.relative_to(output_dir).as_posix(), "bytes": path.stat().st_size,
                           "sha256": digest_file(path)} for path in sorted(output_dir.rglob("*")) if path.is_file()]}
    with (output_dir / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return {"output_dir": str(output_dir.resolve()), "manuscript": str((output_dir / "paper.md").resolve()),
            "bibliography": str((output_dir / "paper.bib").resolve()),
            "format_report": str((output_dir / "format-report.json").resolve()),
            "source_format_passed": True, "source_package_passed": True, "content_format_passed": True, "submission_ready": False,
            "docx": None, "pdf": None, "publisher_pdf_rendered": False, "visual_review_status": "not_rendered"}

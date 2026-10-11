"""Separate generic formatting assets from immutable scientific manuscript bytes."""

import hashlib
import json
from pathlib import Path

from ..literature import _metadata
from ..workspace import digest_file, ensure_unlinked, write_json
from . import science


def prepare_formatting_source(canonical: dict, analysis: dict, literature: dict, scientific_markdown: Path,
                              output_root: Path, *, metadata_records: dict | None = None,
                              anonymous: bool = False) -> dict:
    """Create citeproc source/CSL JSON using only already verified native data.

    This is a generic article template, not a guessed journal template or a
    verified venue style. Retain the original scientific MD and its digest.
    """
    ensure_unlinked(scientific_markdown)
    ensure_unlinked(output_root)
    original = scientific_markdown.read_text(encoding="utf-8")
    original_digest = digest_file(scientific_markdown)
    sources = science._literature_sources(literature)
    references = canonical["citation_evidence"]
    identifiers = [item["id"] for item in references]
    if len(identifiers) != len(set(identifiers)) or any(identifier not in sources for identifier in identifiers):
        raise ValueError("Formatting references must exactly identify the canonical inspected citations")
    entries, missing = [], []
    for identifier in identifiers:
        source = sources[identifier]
        entry = {"id": identifier, "type": "article", "title": source["title"],
                 "author": [{"literal": value} for value in source["authors"]]}
        if source.get("doi"):
            entry["DOI"] = source["doi"]
        if source.get("year"):
            entry["issued"] = {"date-parts": [[source["year"]]]}
        if source.get("url"):
            entry["URL"] = source["url"]
        if source.get("arxiv_id"):
            entry["note"] = "Inspected arXiv preprint " + source["arxiv_id"]
        if source.get("copy_type") in {"author_copy", "repository_copy"}:
            entry["note"] = "Inspected public copy; publication version unknown"
        if source.get("publication_type") == "technical_standard":
            entry.update(type="report", publisher=source["publisher"], number=source["report_id"],
                         version=source["standard_version"], note=f"Revision {source['revision']}; {source['author_role']}")
        record = (metadata_records or {}).get(identifier)
        if record is not None:
            doi, title, authors, year = _metadata(record)
            if any(source.get(key) != value for key, value in (("doi", doi), ("title", title), ("authors", authors), ("year", year))):
                raise ValueError("Formatting metadata differs from the actual retained citation identity")
            work = record["message"]
            if work.get("type") == "journal-article":
                entry["type"] = "article-journal"
            for raw_key, key in (("container-title", "container-title"), ("volume", "volume"),
                                 ("issue", "issue"), ("page", "page"), ("article-number", "number"),
                                 ("publisher", "publisher")):
                value = work.get(raw_key)
                if isinstance(value, list):
                    value = value[0] if value else None
                if isinstance(value, str) and 0 < len(value.strip()) <= 1000:
                    entry[key] = value.strip()
        if source.get("doi") and not source.get("arxiv_id") and source.get("publication_type") != "technical_standard":
            absent = [key for key in ("container-title", "volume", "issue") if key not in entry]
            if not entry.get("page") and not entry.get("number"):
                absent.append("page/article-number")
            if absent:
                missing.append({"id": identifier, "fields": absent,
                                "reason": "These fields are absent from retained metadata or may not apply; verify official bibliographic requirements instead of guessing values."})
        entries.append(entry)
    first = canonical["sections"][0]["heading"]
    boundary = "## " + first + "\n"
    if original.count(boundary) != 1:
        raise ValueError("Scientific source does not match its canonical first section")
    header = "# " + science._literal_text(canonical["title"]) + "\n\n" if anonymous else original.split(boundary, 1)[0]
    parts = [header.rstrip(), ""]
    for section in canonical["sections"]:
        text = section["text"]
        rendered, offset = [], 0
        for match in science.PLACEHOLDER.finditer(text):
            rendered.append(science._literal_text(text[offset:match.start()]))
            kind, key = match.groups()
            if kind == "citation":
                if key not in identifiers:
                    raise ValueError("Formatting text refers to a noncanonical citation")
                rendered.append("[@" + key + "]")
            elif kind == "result":
                rendered.append(science._literal_text(science._number(analysis["results"][key]["value"])))
            else:
                value = analysis["parameters"][key]
                rendered.append(science._literal_text(science._number(value) if type(value) in {int, float} else value))
            offset = match.end()
        rendered.append(science._literal_text(text[offset:]))
        parts += ["## " + section["heading"], "", "".join(rendered), ""]
        if section["heading"] == "Results" and canonical.get("submission_contract", {}).get("article_type", "empirical") == "empirical":
            parts += [science._tables(analysis), ""]
        if section["heading"] == "Results" and canonical.get("submission_contract", {}).get("article_type", "empirical") != "formal" and science._validation_tables(analysis):
            parts += [science._validation_tables(analysis), ""]
    parts += ["## References", "", "::: {#refs}", ":::", ""]
    disclosure = "## Reproducibility and assistance disclosure\n"
    if original.count(disclosure) != 1:
        raise ValueError("Scientific source is missing its retained disclosure")
    parts += [disclosure.rstrip(), original.split(disclosure, 1)[1]]
    output_root.mkdir(parents=True, exist_ok=True)
    source_path, bibliography = output_root / "formatting-source.md", output_root / "bibliography.json"
    for path in (source_path, bibliography):
        ensure_unlinked(path)
        if path.exists():
            raise ValueError("Submission formatting cannot overwrite retained assets")
    source_path.write_text("\n".join(parts), encoding="utf-8")
    write_json(bibliography, entries)
    if digest_file(scientific_markdown) != original_digest:
        raise ValueError("Scientific manuscript changed during separate formatting")
    return {"source_path": str(source_path), "source_sha256": digest_file(source_path),
            "bibliography_path": str(bibliography), "bibliography_sha256": digest_file(bibliography),
            "scientific_source_sha256": original_digest, "canonical_sha256": hashlib.sha256(
                json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "template": "generic_article", "csl_path": None, "venue_verified": False,
            "anonymous": anonymous, "missing_bibliographic_fields": missing,
            "scope": "Generic citeproc formatting from retained evidence; official venue requirements and any journal-specific CSL remain unverified. Anonymous mode removes title author metadata only; complete blind-review compliance still requires actual inspection."}

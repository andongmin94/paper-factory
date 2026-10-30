"""Import supplied BibTeX/RIS records for editorial_checks --references-json.

Only explicit source values are mapped. Original records, including unmapped
fields, remain in the JSON; missing facts are reported, never looked up or filled.
"""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

from _publication_files import ensure_unlinked
from editorial_checks import _doi


def _bibtex_records(text: str):
    import pyparsing as pp

    name = pp.Regex(r"[A-Za-z][A-Za-z0-9_:.+\-]*")
    escaped = pp.Regex(r"\\.")
    braced = pp.original_text_for(pp.nested_expr("{", "}", ignore_expr=escaped))
    quoted = pp.original_text_for(
        pp.Literal('"') + pp.ZeroOrMore(braced | escaped | pp.Regex(r'[^"\\{}]+')) + pp.Literal('"'))
    literal = (braced | quoted).set_parse_action(lambda t: [("literal", t[0][1:-1])])
    number = pp.Regex(r"[0-9]+").set_parse_action(lambda t: [("literal", t[0])])
    symbol = name.copy().set_parse_action(lambda t: [("symbol", t[0].casefold())])
    value = pp.Group(pp.DelimitedList(literal | number | symbol, delim="#"))
    field = pp.Group(name("name") + pp.Suppress("=") + value("parts"))
    fields = pp.Group(pp.Optional(pp.DelimitedList(field, allow_trailing_delim=True)))("fields")

    def enclosed(expression):
        return (pp.Suppress("{") + expression + pp.Suppress("}") |
                pp.Suppress("(") + expression + pp.Suppress(")"))

    definitions = pp.CaselessKeyword("string")("kind") + enclosed(fields)
    preamble = pp.CaselessKeyword("preamble")("kind") + enclosed(value)
    comment = pp.CaselessKeyword("comment")("kind") + (
        braced | pp.original_text_for(pp.nested_expr("(", ")", ignore_expr=escaped)) |
        pp.Regex(r"[^\n]*"))
    entry = name("kind") + enclosed(pp.Regex(r"[^\s,{}()=]+")("key") +
                                     pp.Optional(pp.Suppress(",") + fields))
    block = pp.Group(pp.Located(pp.Suppress("@") + (definitions | preamble | comment | entry)))
    document = pp.ZeroOrMore(pp.Regex(r"%[^\n]*").suppress() | block | pp.Regex(r"[^@]+").suppress())
    document.parse_with_tabs()
    try:
        blocks = document.parse_string(text, parse_all=True)
    except pp.ParseBaseException as exc:
        raise ValueError(f"Invalid BibTeX at line {exc.lineno}, column {exc.col}: {exc.msg}") from exc

    strings = {}

    def expand(parts):
        pieces = [value if kind == "literal" else strings.get(value) for kind, value in parts]
        return None if None in pieces else "".join(pieces)

    for block in blocks:
        data = block.value
        kind = data.kind.casefold()
        if kind == "string":
            for field in data.fields:
                strings[field.name.casefold()] = expand(field.parts)
        elif kind not in {"comment", "preamble"}:
            yield text[block.locn_start:block.locn_end], data.key, [
                (field.name.casefold(), expand(field.parts)) for field in data.get("fields", [])]


def _ris_records(text: str):
    lines, fields = [], []
    for number, raw in enumerate(text.splitlines(keepends=True), 1):
        line = raw.rstrip("\r\n")
        if not line.strip():
            if lines:
                lines.append(raw)
            continue
        match = re.fullmatch(r"([A-Z0-9]{2})  - ?(.*)", line)
        if match is None:
            if fields and line[0].isspace():
                tag, value = fields[-1]
                fields[-1] = (tag, value + "\n" + line.lstrip())
                lines.append(raw)
                continue
            raise ValueError(f"Invalid RIS tag or continuation at line {number}")
        tag, value = match.groups()
        if tag == "TY" and fields:
            raise ValueError(f"RIS record before line {number} is missing its ER terminator")
        lines.append(raw)
        if tag == "ER":
            key = next((value for name, value in fields if name == "ID"), None)
            yield "".join(lines), key, fields
            lines, fields = [], []
        else:
            fields.append((tag, value))
    if lines:
        raise ValueError("RIS record is missing its ER terminator")


def parse_bibliography(text: str, format: str) -> dict:
    """Return existing reference JSON records and the editorial finding shape."""
    if format not in {"bibtex", "ris"}:
        raise ValueError("Reference format must be bibtex or ris")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Bibliography must contain records")
    mapping = {"title": "title", "author": "authors", "year": "year", "doi": "doi", "url": "url"} if format == "bibtex" else {
        "TI": "title", "T1": "title", "AU": "authors", "A1": "authors",
        "PY": "year", "Y1": "year", "DO": "doi", "UR": "url"}
    records = _bibtex_records(text) if format == "bibtex" else _ris_records(text)
    references, findings, suggestions = [], [], []
    source_keys = defaultdict(list)
    for number, (raw, key, fields) in enumerate(records, 1):
        item = {"id": number, "source": {"format": format, "raw": raw}}
        if key is not None:
            item["source"]["key"] = key
            source_keys[key].append(number)
        for name, value in fields:
            target = mapping.get(name)
            if target is None:
                continue
            if value is None:
                suggestions.append({"code": "unresolved_bibtex_string", "reference_id": number,
                                    "detail": f"{name} uses a string not defined before this record; the original expression is retained in source.raw."})
            elif target == "authors" and format == "ris":
                item.setdefault("authors", []).append(value)
            elif target not in item:
                item[target] = value
            elif item[target] != value:
                suggestions.append({"code": "conflicting_metadata_values", "reference_id": number,
                                    "detail": f"Multiple {target} values were supplied; the first is mapped and all originals remain in source.raw."})
        if "year" in item:
            original = item.pop("year")
            pattern = r"([0-9]{4})" if format == "bibtex" else r"([0-9]{4})(?:/[0-9]{0,2}){0,3}"
            year = re.fullmatch(pattern, original.strip())
            if year:
                item["year"] = year[1]
            else:
                suggestions.append({"code": "unmapped_metadata_year", "reference_id": number,
                                    "detail": f"Year value {original!r} does not supply one supported four-digit publication year; it remains in source.raw."})
        if item.get("doi") and _doi(item["doi"]) is None:
            findings.append({"code": "malformed_metadata_doi", "reference_id": number,
                             "detail": "Supplied DOI syntax is invalid; its original value was retained."})
        authors = item.get("authors", [])
        has_authors = bool(authors.strip()) if isinstance(authors, str) else any(name.strip() for name in authors)
        missing = [field for field in ("title", "authors", "year", "doi")
                   if not (has_authors if field == "authors" else item.get(field, "").strip())]
        if missing:
            suggestions.append({"code": "incomplete_reference_metadata", "reference_id": number,
                                "detail": "Missing or unmapped metadata: " + ", ".join(missing) + ". The record is retained without filling these facts."})
        references.append(item)
    if not references:
        raise ValueError("Bibliography must contain at least one reference record")
    for key, numbers in source_keys.items():
        if len(numbers) > 1:
            suggestions.append({"code": "duplicate_source_key", "reference_ids": numbers,
                                "detail": f"Source key {key!r} occurs in multiple records; each record was retained separately."})
    suggestions.append({"code": "reference_numbering_check",
                        "detail": "IDs were assigned from 1 in input order. Match them to the manuscript's numbered references before using --references-json."})
    return {"references": references, "structural_findings": findings, "manual_review_suggestions": suggestions}


def write_import(source: Path, output_dir: Path, *, format: str | None = None) -> dict:
    if not source.is_absolute() or not output_dir.is_absolute():
        raise ValueError("Source and output paths must be absolute")
    ensure_unlinked(source)
    ensure_unlinked(output_dir)
    selected = format or {".bib": "bibtex", ".bibtex": "bibtex", ".ris": "ris"}.get(source.suffix.lower())
    if selected is None:
        raise ValueError("Use a .bib, .bibtex or .ris file, or supply --format bibtex|ris")
    original = source.read_bytes()
    result = parse_bibliography(original.decode("utf-8-sig"), selected)
    references = result.pop("references")
    report = {"mode": "local_bibliographic_import", "source_path": str(source), "source_format": selected,
              "source_input_sha256": hashlib.sha256(original).hexdigest(), "reference_count": len(references),
              **result, "network_requests": 0, "source_rewritten": False,
              "scope": "Only supplied metadata is mapped. Original records remain in source.raw; TeX markup and supplied name forms are not rewritten. IDs are local reference numbers, not verified publication identities."}
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, value in (("references.json", references), ("import-report.json", report)):
        with (output_dir / name).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    lines = ["# Bibliographic import", "", report["scope"], "", "## Structural findings", ""]
    lines += ["- " + item["code"] + ": " + item["detail"] for item in result["structural_findings"]] or ["No supported structural finding."]
    lines += ["", "## Suggestions requiring human judgment", ""]
    lines += ["- " + item["code"] + ": " + item["detail"] for item in result["manual_review_suggestions"]]
    with (output_dir / "import-report.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")
    if source.read_bytes() != original:
        raise ValueError("Source changed during bibliography import; output retained for diagnosis")
    return {"output_dir": str(output_dir), "references_json": str(output_dir / "references.json"),
            "reference_count": len(references), "structural_findings": len(result["structural_findings"]),
            "manual_review_suggestions": len(result["manual_review_suggestions"]),
            "source_input_sha256": report["source_input_sha256"], "network_requests": 0, "source_rewritten": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--format", choices=("bibtex", "ris"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = write_import(args.input, args.output_dir, format=args.format)
    except (OSError, ValueError, ImportError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

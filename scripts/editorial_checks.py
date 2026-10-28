"""Read-only citation, cross-reference and wording checks for authored Markdown.

Structural findings describe literal relationships in the supplied text. Other
observations are explicitly suggestions for an editor, never scientific review,
publisher approval, or verification of bibliographic facts over the network.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit, urlunsplit

from _publication_files import digest_file, ensure_unlinked


def _hide_code(text: str) -> str:
    def blank(match):
        return re.sub(r"[^\n]", " ", match[0])
    text = re.sub(r"(?ms)^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?^ {0,3}\1[ \t]*$", blank, text)
    return re.sub(r"`+[^`\n]*`+", blank, text)


def _prose(text: str, *, context: str | None = None) -> str:
    """Mask code and Markdown links, keeping numbered prose citations visible.

    Reference-style links depend on definitions that can occur outside this
    body slice, including after the bibliography. Unknown labels remain prose.
    """
    def blank(match):
        return re.sub(r"[^\n]", " ", match[0])

    def label(value):
        return re.sub(r"\s+", " ", value).strip().casefold()

    definition = re.compile(r"(?m)^ {0,3}\[([^\]\n]+)\]:[ \t]*\S[^\n]*$")
    labels = {label(match[1]) for match in definition.finditer(_hide_code(context if context is not None else text))}
    text = _hide_code(text)
    text = definition.sub(blank, text)
    text = re.sub(r"!?\[[^\]\n]*\]\([^\n)]*\)", blank, text)

    def reference_link(match):
        target = match[2] if match[2] else match[1]
        return blank(match) if label(target) in labels else match[0]

    text = re.sub(r"!?\[([^\]\n]+)\]\[([^\]\n]*)\]", reference_link, text)
    text = re.sub(r"!?\[([^\]\n]+)\]", lambda match: blank(match) if label(match[1]) in labels else match[0], text)
    return re.sub(r"https?://[^\s<>]+", blank, text)


def _sections(text: str) -> tuple[str, str]:
    masked = _hide_code(text)
    heading = re.search(r"(?mi)^ {0,3}(#{1,6})[ \t]+references[ \t]*#*[ \t]*$", masked)
    if heading is None:
        return text, ""
    following = re.search(r"(?m)^ {0,3}#{1," + str(len(heading[1])) + r"}[ \t]+", masked[heading.end():])
    end = heading.end() + following.start() if following else len(text)
    # Exclude only the bibliography section. Appendices and other later prose
    # still participate in citation and figure/table checks.
    body = text[:heading.start()] + re.sub(r"[^\n]", " ", text[heading.start():end]) + text[end:]
    return body, text[heading.end():end]


def _references(text: str) -> list[dict]:
    text = _hide_code(text)
    starts = list(re.finditer(r"(?m)^ {0,3}(?:\[(\d+)\]|(\d+)\.)[ \t]+", text))
    return [{"id": int(m[1] or m[2]),
             "text": text[m.end():starts[i + 1].start() if i + 1 < len(starts) else len(text)].strip()}
            for i, m in enumerate(starts)]


def _citations(text: str) -> set[int]:
    labels = set()
    for match in re.finditer(r"\[([0-9][0-9,; \t\-–]*)\]", text):
        for part in re.split(r"[,;]", match[1]):
            item = re.fullmatch(r"\s*([0-9]+)(?:\s*[-–]\s*([0-9]+))?\s*", part)
            if not item:
                continue
            lo, hi = int(item[1]), int(item[2] or item[1])
            if lo <= hi <= lo + 1000:
                labels.update(range(lo, hi + 1))
    return labels


def _doi(value: str) -> str | None:
    value = unquote(value.strip()).removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    value = re.sub(r"^doi:\s*", "", value, flags=re.I).rstrip(".,;)]}")
    return value.casefold() if re.fullmatch(r"10\.[0-9]{4,9}/[^\s<>]+", value, re.I) else None


def _dois(text: str) -> list[str]:
    return [v for m in re.finditer(r"(?i)\b10\.[0-9]{4,9}/[^\s<>\"]+", text)
            if (v := _doi(m[0]))]


def _url(value: str) -> str:
    value = value.rstrip(".,;)]}")
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path,
                       parsed.query, parsed.fragment))


def _findings_for_duplicates(values: list[tuple[int, str]], code: str, label: str) -> list[dict]:
    groups = defaultdict(set)
    for number, value in values:
        if value:
            groups[value].add(number)
    return [{"code": code, "reference_ids": sorted(ids), "detail": label + ": " + value}
            for value, ids in sorted(groups.items()) if len(ids) > 1]


def check_manuscript(text: str, references: list[dict] | None = None) -> dict:
    """Check actual text and optional supplied metadata without external lookup.

    `references` is an optional list of {id,title,doi,authors,year,url,...}.
    Its values are supplied facts to compare, not verified scholarly metadata.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Manuscript must contain text")
    if references is not None and (not isinstance(references, list) or
                                  any(not isinstance(x, dict) for x in references)):
        raise ValueError("Reference metadata must be a list of objects")
    scan = text.replace("\r\n", "\n").replace("\r", "\n")
    body, bibliography = _sections(scan)
    entries = _references(bibliography)
    prose = _prose(body, context=scan)
    cited = _citations(prose)
    counts = Counter(x["id"] for x in entries)
    defined = set(counts)
    findings, suggestions = [], []
    for number in sorted(cited - defined):
        findings.append({"code": "citation_without_reference", "reference_id": number,
                         "detail": f"Body citation [{number}] has no numbered reference."})
    for number, count in sorted(counts.items()):
        if count > 1:
            findings.append({"code": "duplicate_reference_label", "reference_id": number,
                             "detail": f"Reference label {number} occurs {count} times."})
    for number in sorted(defined - cited):
        suggestions.append({"code": "reference_not_cited", "reference_id": number,
                            "detail": f"Reference {number} has no recognized numeric body citation; check other notation manually."})
    if entries and sorted(defined) != list(range(1, len(defined) + 1)):
        findings.append({"code": "reference_numbering_gap", "detail": "Numbered references do not form a sequence starting at 1."})
    dois, urls = [], []
    for entry in entries:
        dois.extend((entry["id"], value) for value in set(_dois(entry["text"])))
        urls.extend((entry["id"], _url(m[0])) for m in re.finditer(r"https?://[^\s<>]+", entry["text"]))
        for token in re.finditer(r"(?i)(?:\bdoi:\s*|https?://doi\.org/)([^\s]+)", entry["text"]):
            if _doi(token[1]) is None:
                findings.append({"code": "malformed_doi", "reference_id": entry["id"],
                                 "detail": "Explicit DOI value has invalid syntax: " + token[1].rstrip(".,;)]}")})
    findings.extend(_findings_for_duplicates(dois, "duplicate_doi", "Same DOI appears under different reference labels"))
    findings.extend(_findings_for_duplicates(urls, "duplicate_reference_url", "Same URL appears under different reference labels"))
    headings = [re.sub(r"\s+", " ", m[1].strip().strip("#").strip()).casefold()
                for m in re.finditer(r"(?m)^ {0,3}#{1,6}[ \t]+(.+)$", _prose(scan))]
    for heading, count in sorted(Counter(headings).items()):
        if count > 1:
            findings.append({"code": "duplicate_heading", "detail": f"Heading '{heading}' occurs {count} times."})
    caption_pattern = re.compile(r"(?mi)^\s*[*_]{0,2}(Table|Figure|Fig\.)[ \t]+([A-Z]?[0-9]+)[.:][ \t]+[^\n]+$")
    captions = [("figure" if m[1].lower().startswith("fig") else "table", m[2].upper())
                for m in caption_pattern.finditer(prose)]
    caption_counts = Counter(captions)
    callout_body = caption_pattern.sub("", prose)
    callouts = set()
    for match in re.finditer(r"\b(Tables?|Figures?|Figs?\.)\s+([A-Z]?[0-9]+(?:\s*(?:,|and|&)\s*[A-Z]?[0-9]+)*)", callout_body, re.I):
        kind = "figure" if match[1].lower().startswith("fig") else "table"
        callouts.update((kind, x.upper()) for x in re.findall(r"[A-Z]?[0-9]+", match[2], re.I))
    for kind, number in sorted(callouts - caption_counts.keys()):
        findings.append({"code": "callout_without_caption", "detail": f"Recognized {kind} {number} callout has no numbered text caption."})
    for (kind, number), count in sorted(caption_counts.items()):
        if count > 1:
            findings.append({"code": "duplicate_caption", "detail": f"Caption {kind} {number} occurs {count} times."})
        if (kind, number) not in callouts:
            suggestions.append({"code": "caption_not_called_out", "detail": f"Caption {kind} {number} has no recognized body callout; inspect image/alternative notation manually."})
    if references is not None:
        supplied_ids = set()
        titles, supplied_dois = [], []
        for item in references:
            number = item.get("id")
            if type(number) is not int or number < 1:
                raise ValueError("Each reference metadata id must be a positive integer")
            if number in supplied_ids:
                raise ValueError("Reference metadata ids must be unique")
            supplied_ids.add(number)
            for field in ("title", "doi", "url"):
                if field in item and not isinstance(item[field], str):
                    raise ValueError(f"Reference metadata {field} must be text")
            authors = item.get("authors", [])
            if isinstance(authors, str):
                authors = [authors]
            if not isinstance(authors, list) or any(not isinstance(value, str) for value in authors):
                raise ValueError("Reference metadata authors must be text or a list of names")
            year = item.get("year")
            if year is not None and (type(year) not in {str, int} or not re.fullmatch(r"[0-9]{4}", str(year))):
                raise ValueError("Reference metadata year must be a four-digit year")
            if number not in defined:
                findings.append({"code": "metadata_without_reference", "reference_id": number,
                                 "detail": "Supplied metadata has no numbered manuscript entry."})
                continue
            actual = next(x["text"] for x in entries if x["id"] == number)
            title = re.sub(r"\s+", " ", item.get("title", "")).strip().casefold()
            titles.append((number, title))
            if title and title not in re.sub(r"\s+", " ", actual).casefold():
                suggestions.append({"code": "metadata_title_not_found", "reference_id": number,
                                    "detail": "The supplied title is not a literal normalized substring of this reference; check variants manually."})
            if authors and any(value.strip().casefold() not in actual.casefold() for value in authors if value.strip()):
                suggestions.append({"code": "metadata_author_not_found", "reference_id": number,
                                    "detail": "A supplied name is not printed literally in this entry; initials and abbreviated author lists need manual comparison."})
            if year is not None and not re.search(r"(?<![0-9])" + str(year) + r"(?![0-9])", actual):
                suggestions.append({"code": "metadata_year_not_found", "reference_id": number,
                                    "detail": "Supplied year is not printed in this reference entry; publication and access dates need manual comparison."})
            if item.get("url"):
                actual_urls = {_url(m[0]) for m in re.finditer(r"https?://[^\s<>]+", actual)}
                if _url(item["url"]) not in actual_urls:
                    suggestions.append({"code": "metadata_url_not_printed", "reference_id": number,
                                        "detail": "Supplied URL is absent from this entry; alternate official links need manual comparison."})
            if item.get("doi"):
                value = _doi(item["doi"])
                if value is None:
                    findings.append({"code": "malformed_metadata_doi", "reference_id": number,
                                     "detail": "Supplied DOI syntax is invalid."})
                else:
                    supplied_dois.append((number, value))
                    actual_dois = _dois(actual)
                    if actual_dois and value not in actual_dois:
                        findings.append({"code": "metadata_doi_mismatch", "reference_id": number,
                                         "detail": "Supplied DOI and manuscript DOI differ; neither is verified by this tool."})
                    elif not actual_dois:
                        suggestions.append({"code": "metadata_doi_not_printed", "reference_id": number,
                                            "detail": "Supplied DOI is absent from the manuscript entry; confirm whether the venue requires it."})
        findings.extend(_findings_for_duplicates(titles, "duplicate_metadata_title", "Same supplied normalized title under multiple labels"))
        findings.extend(_findings_for_duplicates(supplied_dois, "duplicate_metadata_doi", "Same supplied DOI under multiple labels"))
    for acronym in list(dict.fromkeys(re.findall(r"\b[A-Z][A-Z0-9]{1,7}\b", prose)))[:30]:
        if acronym.isdigit():
            continue
        first = re.search(r"\b" + re.escape(acronym) + r"\b", prose)
        context = prose[max(0, first.start() - 90):first.end() + 90]
        expanded = re.search(r"[A-Za-z][A-Za-z -]{5,80}\(\s*" + re.escape(acronym) + r"\s*\)", context)
        reverse = re.search(re.escape(acronym) + r"\s*\([A-Za-z][A-Za-z -]{5,80}\)", context)
        if not expanded and not reverse:
            suggestions.append({"code": "acronym_definition_check", "acronym": acronym,
                                "detail": "No simple expansion recognized near first use; common names, headings and code-derived tokens require editorial judgment."})
    return {"mode": "local_editorial_relationship_checks", "manuscript_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "structural_findings": findings, "manual_review_suggestions": suggestions,
            "metrics": {"reference_entries": len(entries), "recognized_body_citations": sorted(cited),
                        "table_captions": sum(v for (kind, _), v in caption_counts.items() if kind == "table"),
                        "figure_captions": sum(v for (kind, _), v in caption_counts.items() if kind == "figure")},
            "metadata_scope": "Supplied metadata compared literally; DOI resolution, publication identity, retraction and authorship were not checked online. A supplied verified_metadata field is not verification by this tool.",
            "scientific_merit_assessed": False, "publisher_compliance_certified": False,
            "scope": "Limited Markdown conventions. Structural findings report literal relationships, not factual truth; manual suggestions are heuristics and may be false positives. No content is rewritten."}


def write_report(manuscript: Path, output_dir: Path, references_json: Path | None = None) -> dict:
    if any(not path.is_absolute() for path in (manuscript, output_dir, *([references_json] if references_json is not None else []))):
        raise ValueError("Manuscript, metadata and output paths must be absolute")
    ensure_unlinked(manuscript)
    ensure_unlinked(output_dir)
    source = manuscript.read_bytes()
    references_source = None
    if references_json is not None:
        ensure_unlinked(references_json)
        references_source = references_json.read_bytes()
    result = check_manuscript(source.decode("utf-8-sig"),
                              json.loads(references_source.decode("utf-8-sig")) if references_source is not None else None)
    result["manuscript_sha256"] = hashlib.sha256(source).hexdigest()
    result["references_input_sha256"] = hashlib.sha256(references_source).hexdigest() if references_source is not None else None
    output_dir.mkdir(parents=True, exist_ok=False)
    with (output_dir / "editorial-report.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    lines = ["# Local editorial checks", "", result["scope"], "", "## Structural findings", ""]
    lines += ["- " + x["code"] + ": " + x["detail"] for x in result["structural_findings"]] or ["No supported structural finding."]
    lines += ["", "## Suggestions requiring human judgment", ""]
    lines += ["- " + x["code"] + ": " + x["detail"] for x in result["manual_review_suggestions"]] or ["No heuristic suggestion."]
    lines += ["", result["metadata_scope"], ""]
    with (output_dir / "editorial-report.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines))
    if manuscript.read_bytes() != source or references_json is not None and references_json.read_bytes() != references_source:
        raise ValueError("Input changed during editorial inspection; output retained for diagnosis")
    return {"output_dir": str(output_dir.resolve()), "structural_findings": len(result["structural_findings"]),
            "manual_review_suggestions": len(result["manual_review_suggestions"]),
            "manuscript_sha256": digest_file(manuscript), "network_requests": 0, "content_rewritten": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("check")
    command.add_argument("--manuscript", type=Path, required=True)
    command.add_argument("--references-json", type=Path)
    command.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = write_report(args.manuscript, args.output_dir, args.references_json)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

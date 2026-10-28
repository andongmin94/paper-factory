"""Prepare reusable, source-bound notes from explicitly supplied literature readings.

The agent supplies the analysis and actual reading scope. This helper checks retained
bytes and quoted locations; it neither reads a paper for the agent nor validates claims.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from _publication_files import digest_file
from research_workspace import _absolute, _json, _manifest, _new_folder, _relative, _sha256, _write

SCOPES = {"full_body", "selected_sections", "abstract_only", "metadata_only"}
TEXT_FIELDS = ("id", "title", "url", "question", "method", "results", "limitations", "relevance")


def prepare(root: Path, cards_path: Path, output_dir: Path) -> dict:
    root, supplied = _absolute(root), _json(cards_path)
    if set(supplied) != {"cards"} or not isinstance(supplied["cards"], list) or not supplied["cards"]:
        raise ValueError("Reading notes require a nonempty cards list")
    rows, identifiers, snapshots = [], set(), {}
    for card in supplied["cards"]:
        required = set(TEXT_FIELDS) | {"source", "reading_scope", "read_sections", "unread_sections", "witnesses"}
        if not isinstance(card, dict) or set(card) != required:
            raise ValueError("Each card requires id, title, url, question, method, results, limitations, relevance, source, reading_scope, read_sections, unread_sections and witnesses")
        if any(not isinstance(card[k], str) or not card[k].strip() for k in TEXT_FIELDS) or card["id"] in identifiers:
            raise ValueError("Card text fields must be nonempty strings and ids distinct")
        identifiers.add(card["id"])
        if card["reading_scope"] not in SCOPES:
            raise ValueError("reading_scope must be full_body, selected_sections, abstract_only or metadata_only")
        for key in ("read_sections", "unread_sections"):
            if not isinstance(card[key], list) or any(not isinstance(s, str) or not s.strip() for s in card[key]):
                raise ValueError(f"{key} must be an explicit list of nonempty strings")
        if not card["read_sections"] or (card["reading_scope"] == "full_body" and card["unread_sections"]):
            raise ValueError("Reading scope requires read_sections; full_body cannot list unread sections")
        source = card["source"]
        if not isinstance(source, dict) or set(source) != {"path", "sha256", "text_path", "text_sha256"}:
            raise ValueError("source requires path, sha256, text_path and text_sha256")
        original = _relative(root, source["path"])
        extracted = _relative(root, source["text_path"])
        _sha256(source["sha256"], "Source sha256")
        _sha256(source["text_sha256"], "Source text_sha256")
        issues, observed, text = [], {}, None
        for key, path, expected in (("sha256", original, source["sha256"]), ("text_sha256", extracted, source["text_sha256"])):
            if not path.is_file():
                observed[key] = None
                issues.append("missing_source" if key == "sha256" else "missing_source_text")
                continue
            data = path.read_bytes()
            observed[key] = hashlib.sha256(data).hexdigest()
            if path in snapshots and snapshots[path] != observed[key]:
                raise ValueError("A retained source changed while preparing reading notes")
            snapshots[path] = observed[key]
            if observed[key] != expected:
                issues.append("source_hash_mismatch" if key == "sha256" else "source_text_hash_mismatch")
            if key == "text_sha256":
                text = data.decode("utf-8-sig")
        witnesses = card["witnesses"]
        if not isinstance(witnesses, list):
            raise ValueError("witnesses must be a list")
        if not witnesses and card["reading_scope"] in {"full_body", "selected_sections"}:
            issues.append("no_body_witnesses")
        checked = []
        for witness in witnesses:
            if not isinstance(witness, dict) or not {"start_line", "end_line", "quote"} <= witness.keys() or set(witness) - {"start_line", "end_line", "quote", "pages"}:
                raise ValueError("Witness requires start_line, end_line, quote and optional supplied pages")
            start, end, quote = witness["start_line"], witness["end_line"], witness["quote"]
            if type(start) is not int or type(end) is not int or not 1 <= start <= end or not isinstance(quote, str) or not quote:
                raise ValueError("Witness line range and literal quote are required")
            if "pages" in witness and (not isinstance(witness["pages"], str) or not witness["pages"].strip()):
                raise ValueError("pages must be a nonempty supplied locator string")
            lines = text.splitlines() if text is not None else []
            match = end <= len(lines) and "\n".join(lines[start - 1:end]) == quote
            if not match:
                issues.append("source_quote_mismatch")
            checked.append({**witness, "quote_matches": match,
                            "page_locator_scope": "Supplied locator, not independently checked against PDF pages."})
        rows.append({**card, "source": {**source, "observed_sha256": observed["sha256"], "observed_text_sha256": observed["text_sha256"]},
                     "witnesses": checked, "issues": sorted(set(issues)), "bindings_match": not issues,
                     "body_reading_reported": card["reading_scope"] in {"full_body", "selected_sections"}})
    for path, expected in snapshots.items():
        if digest_file(path) != expected:
            raise ValueError("A retained source changed while preparing reading notes")
    folder = _new_folder(output_dir)
    report = {"format_version": 1, "created_at": datetime.now(timezone.utc).isoformat(), "cards": rows,
              "bindings_match": all(row["bindings_match"] for row in rows),
              "scope": "Supplied reading scope and analysis with literal retained-byte/quote checks only. Matching bindings do not prove full reading, source identity, interpretation, claim truth or novelty. Abstract-only and metadata-only cards cannot stand in for primary-body reading."}
    _write(folder / "literature-cards.json", report)
    prose = ["# Primary-literature reading cards", "", report["scope"], ""]
    for card in rows:
        prose += ["## " + card["id"] + ": " + card["title"], "", card["url"], "",
                  "Reported reading scope: " + card["reading_scope"], "", "Read: " + "; ".join(card["read_sections"]),
                  "", "Unread: " + ("; ".join(card["unread_sections"]) or "none reported"), "",
                  f"Retained source: {card['source']['path']} — SHA-256 `{card['source']['observed_sha256']}`", "",
                  f"Retained text: {card['source']['text_path']} — SHA-256 `{card['source']['observed_text_sha256']}`", ""]
        for field in ("question", "method", "results", "limitations", "relevance"):
            prose += ["### " + field.title(), "", card[field], ""]
        prose += ["Binding status: " + ("matches" if card["bindings_match"] else ", ".join(card["issues"])), ""]
        for witness in card["witnesses"]:
            prose += [f"- Lines {witness['start_line']}–{witness['end_line']}" + (f"; supplied pages {witness['pages']}" if witness.get("pages") else "") + ": " + ("matches" if witness["quote_matches"] else "mismatch"), "", "```text", witness["quote"], "```", ""]
    with (folder / "literature-cards.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(prose))
    _manifest(folder)
    return {"output_dir": str(folder), "card_count": len(rows), "bindings_match": report["bindings_match"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("prepare")
    command.add_argument("--root", type=Path, required=True)
    command.add_argument("--cards", type=Path, required=True)
    command.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare(args.root, args.cards, args.output_dir)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["bindings_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

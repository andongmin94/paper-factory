"""Deterministic official-template output for an agent-written manuscript.

The Markdown is the canonical authored source. This adapter copies it byte for
byte, applies the retained publisher template through existing converters, and
records native measurements and exact artifact bindings. It never drafts prose, starts a model, or infers author approval.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from _publication_convert import convert_docx, pandoc_binary
from _publication_checks import compliance_report, validate_manuscript
from _publication_templates import official_template, word_pdf
from _publication_files import digest_file, ensure_unlinked
from _author_profile import normalize_profile


VENUES = ("ieee-software", "ieee-security-privacy")


def _read_inputs(manuscript: Path, profile: Path | None):
    ensure_unlinked(manuscript)
    if manuscript.suffix.lower() != ".md":
        raise ValueError("The canonical manuscript must be a Markdown (.md) file")
    source = manuscript.read_bytes()
    text = source.decode("utf-8-sig")
    if not text.strip():
        raise ValueError("The canonical manuscript is empty")
    author_source = None
    if profile is not None:
        ensure_unlinked(profile)
        author_source = profile.read_bytes()
    author = normalize_profile(json.loads(author_source.decode("utf-8-sig"))) if author_source is not None else {}
    return source, text, author_source, author


def preflight(manuscript: Path, venue_id: str, *, profile: Path | None = None) -> dict:
    """Read-only Markdown estimates and retained-template verification; no Word."""
    source, text, author_source, author = _read_inputs(manuscript, profile)
    template_path, template = official_template(venue_id)
    return {**validate_manuscript(text, venue_id, author),
            "mode": "skill_read_only_preflight",
            "manuscript_sha256": hashlib.sha256(source).hexdigest(),
            "author_input_sha256": hashlib.sha256(author_source).hexdigest() if author_source is not None else None,
            "author_metadata": author,
            "official_template": {**template, "path": str(template_path.resolve())},
            "native_word_measured": False, "model_calls_made_by_tool": 0}


def _write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def export(manuscript: Path, venue_id: str, output_dir: Path, *,
           profile: Path | None = None, pandoc: str | None = None) -> dict:
    """Create a new direct-authoring delivery; an existing directory is refused.

    Failed conversions leave their new directory available for diagnosis. No
    prior artifact is removed, rewritten, adopted, or used as a fallback.
    """
    source, _, author_source, author = _read_inputs(manuscript, profile)
    source_sha = hashlib.sha256(source).hexdigest()
    template_path, template = official_template(venue_id)
    binary = pandoc_binary(pandoc)
    ensure_unlinked(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    output_dir = output_dir.resolve()
    retained_source = output_dir / "manuscript.md"
    with retained_source.open("xb") as stream:
        stream.write(source)
    if author_source is not None:
        with (output_dir / "authors.json").open("xb") as stream:
            stream.write(author_source)

    stem = "manuscript-" + venue_id
    docx, pdf = output_dir / (stem + ".docx"), output_dir / (stem + ".pdf")
    # Convert the actual source path so authored relative media links resolve.
    # Its bytes, and the retained canonical copy, are checked again below.
    docx_receipt = convert_docx(manuscript, docx, pandoc=str(binary), venue_id=venue_id)
    rendered = word_pdf(docx, pdf)
    receipts = {"docx": docx_receipt,
                "pdf": {"engine": "Microsoft Word PDF of the exact saved official-template DOCX",
                        "input_sha256": source_sha, "output_sha256": digest_file(pdf),
                        "official_template": docx_receipt["official_template"],
                        "source_docx_sha256": digest_file(docx), "word_rendering": rendered}}
    _write_json(output_dir / "conversion-receipts.json", receipts)
    report = compliance_report(retained_source, docx, venue_id, pdf=pdf,
                               qa_root=output_dir / "pages", author_metadata=author,
                               conversion_receipts=receipts)
    if manuscript.read_bytes() != source or retained_source.read_bytes() != source:
        raise ValueError("The canonical manuscript changed during direct export")
    if profile is not None and profile.read_bytes() != author_source:
        raise ValueError("The supplied author metadata changed during direct export")
    if digest_file(template_path) != template["sha256"]:
        raise ValueError("The official template changed during direct export")
    _write_json(output_dir / "format-report.json", report)
    provenance = {
        "mode": "direct_agent_authored_markdown_native_export",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": {"path": str(manuscript.resolve()), "sha256": source_sha},
        "author_input": {"path": str(profile.resolve()), "sha256": hashlib.sha256(author_source).hexdigest()} if author_source is not None else None,
        "author_metadata": author,
        "official_template": {**template, "path": str(template_path.resolve())},
        "pandoc": {"path": str(binary), "sha256": digest_file(binary)},
        "python": sys.executable,
        "research_automation_invoked": False,
        "model_calls_made_by_tool": 0,
        "writing_performed_by_tool": False,
        "author_approval_inferred": False,
        "actual_submission_performed": False,
        "scope": "Deterministic formatting and native QA only. Direct-agent research and model use must be documented separately. Retained guidance/template dates do not establish current publisher availability. Visual page review and author declarations remain separate.",
    }
    _write_json(output_dir / "provenance.json", provenance)
    manifest = {"algorithm": "SHA-256", "scope": "Direct-authoring delivery; excludes this manifest.",
                "manuscript_sha256": source_sha,
                "files": [{"path": path.relative_to(output_dir).as_posix(), "bytes": path.stat().st_size,
                           "sha256": digest_file(path)}
                          for path in sorted(output_dir.rglob("*")) if path.is_file()]}
    _write_json(output_dir / "manifest.json", manifest)
    return {"output_dir": str(output_dir), "manuscript": str(retained_source),
            "docx": str(docx), "pdf": str(pdf), "format_report": str(output_dir / "format-report.json"),
            "content_format_passed": report["content_format_passed"],
            "submission_ready": report["submission_ready"],
            "visual_review_status": (report.get("page_qa") or {}).get("visual_review_status", "pending")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "export"):
        command = commands.add_parser(name)
        command.add_argument("--manuscript", type=Path, required=True)
        command.add_argument("--venue", choices=VENUES, required=True)
        command.add_argument("--profile", type=Path)
        if name == "export":
            command.add_argument("--output-dir", type=Path, required=True)
            command.add_argument("--pandoc", help="Existing absolute Pandoc executable; otherwise uses an installed Pandoc")
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight(args.manuscript, args.venue, profile=args.profile)
            passed = result["prefilter_passed"]
        else:
            result = export(args.manuscript, args.venue, args.output_dir,
                            profile=args.profile, pandoc=args.pandoc)
            passed = result["content_format_passed"]
    except (OSError, ValueError, ImportError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

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

from _publication_convert import convert_docx, image_sources, pandoc_binary
from _publication_checks import compliance_report, validate_manuscript
from _publication_templates import official_template, word_pdf
from _publication_files import digest_file, ensure_unlinked
from _author_profile import normalize_profile
from _publication_venues import EXPORT_VENUES


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


def preflight(manuscript: Path, venue_id: str, *, profile: Path | None = None,
              template_path: Path | None = None, bibliography: Path | None = None,
              pandoc: str | None = None, resource_dir: Path | None = None) -> dict:
    """Read-only Markdown estimates and retained-template verification; no Word."""
    if venue_id == "joss":
        if profile is not None or template_path is not None:
            raise ValueError("JOSS uses the authored YAML metadata and bundled syntax reference; --profile and --template do not apply")
        from _publication_joss import preflight as source_preflight
        return source_preflight(manuscript, bibliography=bibliography, pandoc=pandoc, resource_dir=resource_dir)
    if bibliography is not None:
        raise ValueError("--bibliography is for JOSS; Word venues retain numbered references in the manuscript")
    source, text, author_source, author = _read_inputs(manuscript, profile)
    template_path, template = official_template(venue_id, template_path)
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
           profile: Path | None = None, pandoc: str | None = None,
           resource_dir: Path | None = None, template_path: Path | None = None,
           bibliography: Path | None = None, docx_only: bool = False) -> dict:
    """Create a new direct-authoring delivery; an existing directory is refused.

    Failed conversions leave their new directory available for diagnosis. No
    prior artifact is removed, rewritten, adopted, or used as a fallback.
    """
    if venue_id == "joss":
        if docx_only:
            raise ValueError("--docx-only is for Word venues; JOSS exports authored source files")
        if profile is not None or template_path is not None:
            raise ValueError("JOSS uses the authored YAML metadata and bundled syntax reference; --profile and --template do not apply")
        from _publication_joss import export as source_export
        return source_export(manuscript, output_dir, bibliography=bibliography, pandoc=pandoc, resource_dir=resource_dir)
    if bibliography is not None:
        raise ValueError("--bibliography is for JOSS; Word venues retain numbered references in the manuscript")
    source, text, author_source, author = _read_inputs(manuscript, profile)
    source_sha = hashlib.sha256(source).hexdigest()
    template_path, template = official_template(venue_id, template_path)
    binary = pandoc_binary(pandoc)
    ensure_unlinked(output_dir)
    if output_dir.exists():
        raise FileExistsError("Output directory must be new: " + str(output_dir))
    stem = "manuscript-" + venue_id
    images = image_sources(manuscript, text, binary=binary, resource_dir=resource_dir,
                           reserved={"manuscript.md", "authors.json", stem + ".docx", stem + ".pdf",
                                     "conversion-receipts.json", "format-report.json", "provenance.json",
                                     "manifest.json", "pages"})
    output_dir.mkdir(parents=True, exist_ok=False)
    output_dir = output_dir.resolve()
    retained_source = output_dir / "manuscript.md"
    with retained_source.open("xb") as stream:
        stream.write(source)
    if author_source is not None:
        with (output_dir / "authors.json").open("xb") as stream:
            stream.write(author_source)
    for relative, (_, data) in images.items():
        target = output_dir / relative
        ensure_unlinked(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)

    docx, pdf = output_dir / (stem + ".docx"), output_dir / (stem + ".pdf")
    # Convert the retained source and images so this delivery can be moved and
    # regenerated without the original resource directory or changed links.
    docx_receipt = convert_docx(retained_source, docx, pandoc=str(binary), venue_id=venue_id,
                                template_path=template_path)
    receipts = {"docx": docx_receipt}
    if not docx_only:
        rendered = word_pdf(docx, pdf, venue_id=venue_id)
        receipts["pdf"] = {"engine": "Microsoft Word PDF of the exact saved official-template DOCX",
                           "input_sha256": source_sha, "output_sha256": digest_file(pdf),
                           "official_template": docx_receipt["official_template"],
                           "source_docx_sha256": digest_file(docx), "word_rendering": rendered}
    _write_json(output_dir / "conversion-receipts.json", receipts)
    if docx_only:
        report = preflight(retained_source, venue_id, profile=profile, template_path=template_path)
        pending = "Native Microsoft Word measurement, Word PDF rendering and all-page visual review were not performed."
        report["items"].append({"id": "native_word_pdf", "label": "native word pdf",
                                "status": "pending", "stage": "native", "reason": pending,
                                "source_url": template["download_url"]})
        report["pending"].append(pending)
        report.update(mode="skill_docx_export", content_format_passed=False, submission_ready=False,
                      word_measurement=None, page_qa=None,
                      binding={"markdown_sha256": source_sha, "docx_sha256": digest_file(docx),
                               "template_sha256": template["sha256"],
                               "template_provenance_sha256": template["provenance_sha256"]})
    else:
        report = compliance_report(retained_source, docx, venue_id, pdf=pdf,
                                   qa_root=output_dir / "pages", author_metadata=author,
                                   conversion_receipts=receipts, template_path=template_path)
    if manuscript.read_bytes() != source or retained_source.read_bytes() != source:
        raise ValueError("The canonical manuscript changed during direct export")
    if profile is not None and profile.read_bytes() != author_source:
        raise ValueError("The supplied author metadata changed during direct export")
    for relative, (path, data) in images.items():
        target = output_dir / relative
        ensure_unlinked(path)
        ensure_unlinked(target)
        if path.read_bytes() != data or target.read_bytes() != data:
            raise ValueError("A referenced image changed during direct export: " + relative)
    if digest_file(template_path) != template["sha256"]:
        raise ValueError("The official template changed during direct export")
    _write_json(output_dir / "format-report.json", report)
    provenance = {
        "mode": "direct_agent_authored_markdown_docx_export" if docx_only else "direct_agent_authored_markdown_native_export",
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
        "scope": ("DOCX conversion and read-only manuscript preflight only; no native Word measurement, PDF or page review. " if docx_only else "Deterministic formatting and native QA only. ") + "Direct-agent research and model use must be documented separately. Retained guidance/template dates do not establish current publisher availability. Visual page review and author declarations remain separate.",
    }
    _write_json(output_dir / "provenance.json", provenance)
    manifest = {"algorithm": "SHA-256", "scope": "Direct-authoring delivery; excludes this manifest.",
                "manuscript_sha256": source_sha,
                "files": [{"path": path.relative_to(output_dir).as_posix(), "bytes": path.stat().st_size,
                           "sha256": digest_file(path)}
                          for path in sorted(output_dir.rglob("*")) if path.is_file()]}
    _write_json(output_dir / "manifest.json", manifest)
    return {"output_dir": str(output_dir), "manuscript": str(retained_source),
            "docx": str(docx), "pdf": None if docx_only else str(pdf),
            "format_report": str(output_dir / "format-report.json"),
            **({"prefilter_passed": report["prefilter_passed"], "native_word_measured": False} if docx_only else {}),
            "content_format_passed": report["content_format_passed"],
            "submission_ready": report["submission_ready"],
            "visual_review_status": (report.get("page_qa") or {}).get("visual_review_status", "pending")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "export"):
        command = commands.add_parser(name)
        command.add_argument("--manuscript", type=Path, required=True)
        command.add_argument("--venue", choices=EXPORT_VENUES, required=True)
        command.add_argument("--profile", type=Path)
        command.add_argument("--template", type=Path, help="Official downloaded Word template for IEEE Access or JORS; exact retained SHA required")
        command.add_argument("--bibliography", type=Path, help="JOSS original BibTeX file; defaults to paper.bib beside the manuscript")
        command.add_argument("--pandoc", help="Existing absolute Pandoc executable; otherwise uses an installed Pandoc")
        command.add_argument("--resource-dir", type=Path, help="Existing absolute directory for authored relative media")
        if name == "export":
            command.add_argument("--output-dir", type=Path, required=True)
            command.add_argument("--docx-only", action="store_true",
                                 help="Create official-template DOCX and reports without native Word/PDF; exit 0/1 reflects manuscript preflight, not native format approval")
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight(args.manuscript, args.venue, profile=args.profile, template_path=args.template,
                               bibliography=args.bibliography, pandoc=args.pandoc, resource_dir=args.resource_dir)
            passed = result["prefilter_passed"]
        else:
            result = export(args.manuscript, args.venue, args.output_dir,
                            profile=args.profile, pandoc=args.pandoc, resource_dir=args.resource_dir,
                            template_path=args.template, bibliography=args.bibliography, docx_only=args.docx_only)
            passed = (result["prefilter_passed"] if args.docx_only else
                      result["source_package_passed"] if args.venue == "joss" else result["content_format_passed"])
    except (OSError, ValueError, ImportError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Local coauthor, review-response and submission-file preparation.

These commands use supplied facts and text. They do not certify author consent,
evaluate scientific merit, contact anyone, or submit a manuscript.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET

from _publication_files import digest_file, ensure_unlinked
from _author_profile import normalize_profile, profile_completeness


VENUES = ("ieee-software", "ieee-security-privacy")
BIO_HEADINGS = {"author biography", "author biographies", "about the author", "about the authors"}
AUTHOR_START = "<!-- paper-factory:authors:start -->"
AUTHOR_END = "<!-- paper-factory:authors:end -->"
DECLARATIONS = ("originality", "rights", "author_approval", "funding", "conflicts", "ai_disclosure")


def _text(value, label, *, required=False):
    if not isinstance(value, str) or any(ord(c) < 32 and c not in "\n\r\t" or ord(c) == 127 for c in value):
        raise ValueError(label + " must be text without prohibited controls")
    result = value.strip()
    if required and not result:
        raise ValueError(label + " must not be empty")
    return result


def _read(path):
    ensure_unlinked(path)
    return path.read_text(encoding="utf-8-sig")


def _json(path):
    value = json.loads(_read(path))
    if not isinstance(value, dict):
        raise ValueError("Input must be a JSON object")
    return value


def _write(path, value):
    ensure_unlinked(path)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n" if isinstance(value, (dict, list)) else value)


def _new_output(path):
    ensure_unlinked(path)
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve()


def _manifest(folder):
    _write(folder / "manifest.json", {
        "algorithm": "SHA-256", "scope": "Generated preparation files, excluding this manifest.",
        "files": [{"path": path.relative_to(folder).as_posix(), "bytes": path.stat().st_size,
                   "sha256": digest_file(path)} for path in sorted(folder.rglob("*")) if path.is_file()]})


def _hide_fenced_code(markdown):
    # Preserve offsets while ignoring headings/author markers in code examples.
    protected, marker = [], None
    for line in markdown.splitlines(keepends=True):
        fence = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            current = fence[1]
            if marker is None:
                marker = current
            elif current[0] == marker[0] and len(current) >= len(marker):
                marker = None
            protected.append(" " * len(line.rstrip("\r\n")) + line[len(line.rstrip("\r\n")):])
        elif marker:
            protected.append(" " * len(line.rstrip("\r\n")) + line[len(line.rstrip("\r\n")):])
        else:
            protected.append(line)
    return "".join(protected)


def _sections(markdown):
    return list(re.finditer(r"(?m)^## ([^\r\n]+)[ \t]*$", _hide_fenced_code(markdown)))


def _without_biographies(markdown):
    matches = _sections(markdown)
    removals = [(match.start(), matches[index + 1].start() if index + 1 < len(matches) else len(markdown))
                for index, match in enumerate(matches) if match[1].strip().casefold() in BIO_HEADINGS]
    for start, end in reversed(removals):
        markdown = markdown[:start] + markdown[end:]
    return markdown


def _without_author_block(preamble):
    """Replace only our explicitly delimited slot, never arbitrary front matter."""
    protected = _hide_fenced_code(preamble)
    starts = list(re.finditer(r"(?m)^" + re.escape(AUTHOR_START) + r"[ \t]*\r?$", protected))
    ends = list(re.finditer(r"(?m)^" + re.escape(AUTHOR_END) + r"[ \t]*\r?$", protected))
    if not starts and not ends:
        if preamble.strip():
            raise ValueError("Ambiguous pre-Abstract content: preserve this prose, or explicitly mark only the intended byline with <!-- paper-factory:authors:start --> and <!-- paper-factory:authors:end --> in a new manuscript copy")
        return preamble
    if len(starts) != 1 or len(ends) != 1 or starts[0].start() >= ends[0].start():
        raise ValueError("Author block requires exactly one ordered start/end marker pair")
    return preamble[:starts[0].start()] + preamble[ends[0].end():]


def prepare_authors(profile, manuscript, output_dir, *, anonymous=False):
    ensure_unlinked(profile)
    ensure_unlinked(manuscript)
    profile_sha, manuscript_sha = digest_file(profile), digest_file(manuscript)
    normalized = normalize_profile(_json(profile))
    source = _read(manuscript)
    title = re.match(r"\A# [^\r\n]+(?:\r?\n|\Z)", source)
    abstract = next((x for x in _sections(source) if x[1].strip().casefold() == "abstract"), None)
    if not title or not abstract or abstract.start() <= title.end():
        raise ValueError("Manuscript requires a leading title and a separate Abstract section")
    if any(section.start() < abstract.start() for section in _sections(source)):
        raise ValueError("Only the dedicated byline slot may precede Abstract; preserve other sections explicitly")
    preamble = _without_author_block(source[title.end():abstract.start()]).strip()
    # Unmarked prose is retained. Only explicit author markers may be replaced.
    bylines, biographies, details, missing = [], [], ["# Supplied author details", ""], []
    sensitive = set()
    for entry in normalized["authors"]:
        identifier, author = entry["id"], entry["author"]
        name = author.get("display_name")
        if not name:
            missing.append(identifier + ": display_name")
        else:
            fields = [name]
            for key in ("affiliation", "department", "city", "country"):
                if author.get(key):
                    fields.append(author[key])
            if author.get("orcid"):
                fields.append("ORCID " + author["orcid"])
            if author.get("email"):
                fields.append(author["email"])
            bylines.append(" | ".join(fields))
        details.extend(["## " + (name or identifier), "",
                        "Corresponding author: " + ("yes (supplied selection)" if normalized["corresponding_author"] == identifier else "no"), ""])
        for key in ("affiliation", "department", "city", "country", "email", "orcid", "biography"):
            if author.get(key):
                details.extend([key.replace("_", " ").capitalize() + ": " + author[key], ""])
        details.extend(["Contributions (supplied): " + (", ".join(entry["contributions"]) or "not supplied"), ""])
        if name and author.get("biography"):
            biographies.append(name + ". " + author["biography"])
        sensitive.update(author[key] for key in ("display_name", "email", "orcid", "affiliation") if author.get(key))
    if normalized["corresponding_author"] is None:
        missing.append("corresponding author selection")
    for key in ("funding", "conflicts"):
        details.extend([key.capitalize() + " (supplied): " + (normalized[key] if normalized[key] else "not supplied"), ""])
        if not normalized[key]:
            missing.append(key + " declaration")
    completeness = profile_completeness(normalized)
    missing.extend(entry["id"] + ": " + field for entry in completeness for field in entry["missing_fields"]
                   if not (field == "display_name" and entry["id"] + ": display_name" in missing))
    body = _without_biographies(source[abstract.start():])
    authored = source[:title.end()].rstrip() + "\n\n" + AUTHOR_START + "\n\n" + "\n\n".join(bylines) + "\n\n" + AUTHOR_END + "\n\n" + (preamble + "\n\n" if preamble else "") + body
    if biographies:
        authored = authored.rstrip() + "\n\n## Author biographies\n\n" + "\n\n".join(biographies) + "\n"
    report = {"mode": "explicit_author_preparation", "source_profile_sha256": profile_sha,
              "source_manuscript_sha256": manuscript_sha, "missing_supplied_fields": missing,
              "author_confirmation_required": True, "author_approval_inferred": False,
              "actual_submission_performed": False, "anonymous_requested": anonymous,
              "authors": completeness, "unmarked_pre_abstract_content_preserved": bool(preamble)}
    folder = _new_output(output_dir)
    _write(folder / "manuscript.md", authored)
    _write(folder / "authors.json", normalized)
    _write(folder / "author-details.md", "\n".join(details) + "\nAll facts and selections require actual author confirmation.\n")
    if anonymous:
        blinded = source[:title.end()].rstrip() + "\n\n" + (preamble + "\n\n" if preamble else "") + body
        _write(folder / "anonymous.md", blinded)
        report["anonymous_check"] = {
            "residual_matches": sorted(value for value in sensitive if value.casefold() in blinded.casefold()),
            "scope": "Only explicitly marked author blocks and dedicated biography sections removed. Unmarked front matter, self-citations, links, acknowledgments, images and metadata require manual review. No DOCX/PDF metadata was scrubbed.",
            "fully_anonymized_claimed": False}
    _write(folder / "report.json", report)
    _manifest(folder)
    if digest_file(profile) != profile_sha or digest_file(manuscript) != manuscript_sha:
        raise ValueError("Inputs changed during author preparation")
    return {"output_dir": str(folder), **report}


def prepare_responses(comments, before, after, output_dir):
    for path in (comments, before, after):
        ensure_unlinked(path)
    original_sha, revised_sha, comments_sha = digest_file(before), digest_file(after), digest_file(comments)
    original = _read(before)
    revised = _read(after)
    value = _json(comments)
    if not isinstance(value.get("comments"), list) or not value["comments"]:
        raise ValueError("A non-empty comments list is required")
    identifiers, rows, letter = set(), [], ["# Response to reviewer comments", "", "Draft from supplied comments and responses; author confirmation remains required.", ""]
    for entry in value["comments"]:
        if not isinstance(entry, dict):
            raise ValueError("Each comment must be an object")
        identifier = _text(entry.get("id"), "comment id", required=True)
        if identifier in identifiers:
            raise ValueError("Comment ids must be unique")
        identifiers.add(identifier)
        comment = _text(entry.get("comment"), "comment", required=True)
        status = entry.get("status", "pending")
        if status not in {"pending", "addressed", "not_changed"}:
            raise ValueError("Comment status must be pending, addressed or not_changed")
        response = _text(entry.get("response", ""), "response")
        changes = entry.get("changes", [])
        if not isinstance(changes, list):
            raise ValueError("changes must be a list")
        anchors = []
        for change in changes:
            if not isinstance(change, dict):
                raise ValueError("Each change must contain a literal quote")
            quote = _text(change.get("quote"), "change quote", required=True)
            section = _text(change.get("section", ""), "change section")
            found = quote in revised
            if section:
                sections = _sections(revised)
                found = any(heading[1].strip().casefold() == section.casefold() and quote in revised[heading.end():sections[i + 1].start() if i + 1 < len(sections) else len(revised)]
                            for i, heading in enumerate(sections))
            anchors.append({"quote": quote, "section": section, "present_in_revised_manuscript": found,
                            "also_present_in_previous_manuscript": quote in original})
        issues = []
        if any(not anchor["present_in_revised_manuscript"] for anchor in anchors):
            issues.append("A supplied change quote is absent from the specified revised text")
        if status == "addressed" and (not response or not anchors):
            issues.append("Addressed status lacks a supplied response or change anchor")
        if status == "not_changed" and not response:
            issues.append("Not-changed status requires an explanation of why the request was not implemented")
        if status == "addressed" and anchors and all(anchor["also_present_in_previous_manuscript"] for anchor in anchors):
            issues.append("All supplied quotes already occurred in the previous manuscript; inspect the actual revision diff")
        row = {"id": identifier, "comment": comment, "supplied_status": status, "response": response,
               "changes": anchors, "issues": issues,
               "response_preparation_complete": status != "pending" and bool(response) and not issues,
               "addressed_status_is_self_reported": True, "scientific_resolution_verified": False}
        rows.append(row)
        letter.extend(["## " + identifier, "", "Reviewer comment:", "", "> " + comment.replace("\n", "\n> "), "",
                       "Supplied status: " + status, "", "Response:", "", response or "Response pending.", ""])
        for anchor in anchors:
            letter.extend(["Change location: " + (anchor["section"] or "unspecified section"), "",
                           "> " + anchor["quote"].replace("\n", "\n> "), "",
                           "Literal presence: " + ("found" if anchor["present_in_revised_manuscript"] else "NOT FOUND"), ""])
        if issues:
            letter.extend(["Preparation issues: " + "; ".join(issues), ""])
    all_anchors = [anchor for row in rows for anchor in row["changes"]]
    incomplete = sum(not row["response_preparation_complete"] for row in rows)
    summary = {"comment_count": len(rows), "pending_comment_count": sum(row["supplied_status"] == "pending" for row in rows),
               "incomplete_response_count": incomplete, "change_anchor_count": len(all_anchors),
               "missing_change_anchor_count": sum(not anchor["present_in_revised_manuscript"] for anchor in all_anchors),
               "response_draft_complete": incomplete == 0}
    letter[4:4] = ["Preparation summary: " + str(len(rows)) + " comments; " + str(incomplete) + " incomplete responses. This is not scientific resolution or author approval.", ""]
    report = {"mode": "supplied_review_response_preparation", "comments_sha256": comments_sha,
              "before_sha256": original_sha, "after_sha256": revised_sha, "comments": rows,
              "summary": summary,
              "all_change_anchors_present": all(anchor["present_in_revised_manuscript"] for anchor in all_anchors) if all_anchors else None,
              "author_confirmation_required": True, "scientific_resolution_verified": False,
              "actual_submission_performed": False}
    folder = _new_output(output_dir)
    _write(folder / "response-letter.md", "\n".join(letter))
    _write(folder / "report.json", report)
    _manifest(folder)
    if (digest_file(before), digest_file(after), digest_file(comments)) != (original_sha, revised_sha, comments_sha):
        raise ValueError("Inputs changed during response preparation")
    return {"output_dir": str(folder), **report}


def _inside_file(root, raw):
    if not isinstance(raw, str) or not raw or "\\" in raw or ":" in raw:
        raise ValueError("Bundle paths must be relative forward-slash paths")
    relative = PurePosixPath(raw)
    if relative.is_absolute() or PureWindowsPath(raw).drive or any(x in {"", ".", ".."} for x in raw.split("/")):
        raise ValueError("Bundle paths must stay inside the selected root")
    path = root.joinpath(*relative.parts)
    ensure_unlinked(path)
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError("Bundle input file is missing or outside root")
    return path


def _declaration_status(declarations, confirmations, selections):
    """Check the scope of explicitly supplied human records, never infer consent."""
    if not isinstance(confirmations, dict) or set(confirmations) - set(DECLARATIONS):
        raise ValueError("confirmations must map supported declaration names to explicit records")
    expected_files = {row["path"]: row["sha256"] for row in selections}
    statuses = {}
    for name in DECLARATIONS:
        text, record = declarations.get(name), confirmations.get(name)
        reasons = []
        if not text:
            reasons.append("Declaration text is not supplied")
        if not isinstance(record, dict):
            reasons.append("Explicit human confirmation is not supplied")
        else:
            if record.get("confirmed") is not True or not isinstance(record.get("confirmed_by"), str) or not record["confirmed_by"].strip():
                reasons.append("Confirmation must explicitly identify the actual confirming person")
            try:
                date = datetime.fromisoformat(record.get("confirmed_at", "").replace("Z", "+00:00"))
                if date.tzinfo is None:
                    raise ValueError("missing timezone")
            except (ValueError, TypeError, AttributeError):
                reasons.append("Confirmation requires an ISO timestamp including timezone")
            expected_text = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None
            if record.get("declaration_sha256") != expected_text:
                reasons.append("Confirmation is not bound to this exact declaration text")
            files = record.get("files")
            if not isinstance(files, list) or any(not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str) for item in files):
                reasons.append("Confirmation must bind every exact selected file")
            elif len(files) != len(expected_files) or {item["path"]: item["sha256"] for item in files} != expected_files:
                reasons.append("Confirmation file bindings are missing, stale or differ from the selected files")
        statuses[name] = {"status": "explicit_confirmation_recorded" if not reasons else "pending", "reasons": reasons,
                          "human_record_independently_verified": False}
    return statuses


def prepare_bundle(plan, root, output_dir):
    ensure_unlinked(plan)
    ensure_unlinked(root)
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Bundle root must be a directory")
    ensure_unlinked(output_dir)
    if output_dir.resolve().is_relative_to(root):
        raise ValueError("Bundle output must be outside the source root")
    plan_sha = digest_file(plan)
    value = _json(plan)
    if value.get("venue_id") not in VENUES:
        raise ValueError("A supported venue_id is required")
    title = _text(value.get("title"), "title", required=True)
    if not isinstance(value.get("files"), list) or not value["files"]:
        raise ValueError("Plan requires an explicit non-empty file allowlist")
    selections, names, roles = [], set(), set()
    for entry in value["files"]:
        if not isinstance(entry, dict):
            raise ValueError("Each selected file must contain role and path")
        role = _text(entry.get("role"), "file role", required=True)
        source = _inside_file(root, entry.get("path"))
        name = source.relative_to(root).as_posix()
        if name.casefold() in names:
            raise ValueError("Duplicate selected file destination")
        names.add(name.casefold())
        roles.add(role)
        selections.append({"role": role, "path": name, "source": source,
                           "bytes": source.stat().st_size, "sha256": digest_file(source)})
    declarations = value.get("declarations", {})
    if not isinstance(declarations, dict) or set(declarations) - set(DECLARATIONS) or any(v is not None and not isinstance(v, str) for v in declarations.values()):
        raise ValueError("Declarations must map supported names to supplied text or null; use separate confirmations for human records")
    declarations = {name: _text(text, name) if text is not None else None for name, text in declarations.items()}
    confirmations = value.get("confirmations", {})
    cover = value.get("cover_letter")
    cover_text = None
    if cover is not None:
        if not isinstance(cover, dict):
            raise ValueError("cover_letter must contain supplied text")
        cover_text = _text(cover.get("text"), "cover letter text", required=True)
    approval_files = [{"role": row["role"], "path": "files/" + row["path"],
                       "bytes": row["bytes"], "sha256": row["sha256"]} for row in selections]
    if cover_text:
        if "cover_letter" in roles:
            raise ValueError("Select one supplied cover-letter file or generated cover_letter.text, not both")
        cover_bytes = (cover_text + "\n").encode("utf-8")
        approval_files.append({"role": "cover_letter", "path": "cover-letter.md", "bytes": len(cover_bytes),
                               "sha256": hashlib.sha256(cover_bytes).hexdigest()})
    declaration_status = _declaration_status(declarations, confirmations, approval_files)
    pending = []
    if "manuscript" not in roles:
        pending.append("Select the final manuscript file")
    if value["venue_id"] == "ieee-software" and "author_photo" not in roles:
        pending.append("Retained Software guidance requests author photographs; supply approved images and confirm current requirements")
    if not cover_text and "cover_letter" not in roles:
        pending.append("Cover letter not supplied; check whether the selected category requests one")
    for name in DECLARATIONS:
        if declaration_status[name]["status"] == "pending":
            pending.append("Confirm actual " + name.replace("_", " "))
    pending.extend(["Reconfirm current publisher category, instructions and required files",
                    "Confirm genuine author identity, affiliation, contact and contribution selections",
                    "Inspect every final Word/PDF page and approve the exact files",
                    "Complete any submission-specific declarations in the actual portal"])
    folder = _new_output(output_dir)
    records = []
    for selected in selections:
        target = folder / "files" / selected["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        with selected["source"].open("rb") as source, target.open("xb") as output:
            shutil.copyfileobj(source, output)
        if digest_file(target) != selected["sha256"] or digest_file(selected["source"]) != selected["sha256"]:
            raise ValueError("Selected file changed during bundle preparation")
        records.append({k: v for k, v in selected.items() if k != "source"})
    if cover_text:
        _write(folder / "cover-letter.md", cover_text + "\n")
    report = {"mode": "explicit_submission_file_bundle", "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "title": title, "venue_id": value["venue_id"], "source_plan_sha256": plan_sha,
              "selected_files": records, "approval_files": approval_files, "supplied_declarations": declarations,
              "supplied_confirmations": confirmations, "declaration_status": declaration_status, "pending": pending,
              "submission_ready": False, "author_approval_inferred": False, "actual_submission_performed": False,
              "scope": "Local allowlisted copies and supplied cover text only. File presence and supplied declarations are not independent verification or consent."}
    _write(folder / "report.json", report)
    _write(folder / "checklist.md", "# Submission preparation\n\n" + title + "\n\n" +
           "\n".join("- [ ] " + item for item in pending) +
           "\n\nNo upload or submission was performed. Supplied declarations require genuine author confirmation.\n")
    _manifest(folder)
    if digest_file(plan) != plan_sha:
        raise ValueError("Plan changed during preparation")
    return {"output_dir": str(folder), **report}


def inspect_metadata(file, output_dir, *, profile=None):
    """Read document properties and revision markers without scrubbing anything."""
    ensure_unlinked(file)
    original_sha = digest_file(file)
    fields, revision_authors = {}, set()
    comments, changes = [], 0
    if file.suffix.casefold() == ".docx":
        try:
            with zipfile.ZipFile(file) as package:
                if "word/document.xml" not in package.namelist():
                    raise ValueError("DOCX main document part is missing")
                for entry in package.infolist():
                    name = entry.filename
                    if name not in {"docProps/core.xml", "docProps/custom.xml"} and not (name.startswith("word/") and name.endswith(".xml")):
                        continue
                    if entry.file_size > 16 * 1024 * 1024:
                        raise ValueError("Document property/revision XML exceeds the 16 MiB inspection limit")
                    tree = ET.fromstring(package.read(entry))
                    if name == "docProps/core.xml":
                        fields.update({"core." + child.tag.rsplit("}", 1)[-1]: "".join(child.itertext()) for child in tree})
                    elif name == "docProps/custom.xml":
                        fields.update({"custom." + child.get("name", "unnamed"): "".join(child.itertext()) for child in tree})
                    else:
                        for element in tree.iter():
                            tag = element.tag.rsplit("}", 1)[-1]
                            if tag in {"ins", "del", "moveFrom", "moveTo"}:
                                changes += 1
                            if tag == "comment":
                                comments.append(name)
                            if tag in {"ins", "del", "moveFrom", "moveTo", "comment"}:
                                revision_authors.update(value for key, value in element.attrib.items() if key.rsplit("}", 1)[-1] in {"author", "initials"} and value)
        except (zipfile.BadZipFile, ET.ParseError) as exc:
            raise ValueError("DOCX package or metadata XML is malformed") from exc
    elif file.suffix.casefold() == ".pdf":
        import pypdfium2 as pdfium
        try:
            with pdfium.PdfDocument(file.read_bytes()) as document:
                fields = document.get_metadata_dict(skip_empty=False)
        except Exception as exc:
            raise ValueError("PDF metadata could not be read: " + str(exc)) from exc
    else:
        raise ValueError("Metadata inspection supports only DOCX and PDF")
    fields["revision.authors"] = "; ".join(sorted(revision_authors))
    terms, profile_sha = set(), None
    if profile is not None:
        ensure_unlinked(profile)
        profile_sha = digest_file(profile)
        normalized = normalize_profile(_json(profile))
        terms = {author["author"][key] for author in normalized["authors"]
                 for key in ("display_name", "given_name", "family_name", "email", "orcid", "affiliation") if author["author"].get(key)}
    matches = [{"field": key, "matched_profile_value": term} for key, value in fields.items() for term in sorted(terms)
               if term.casefold() in value.casefold()]
    report = {"mode": "read_only_metadata_inspection", "file_type": file.suffix.casefold()[1:],
              "source_sha256": original_sha, "profile_sha256": profile_sha, "metadata": fields,
              "populated_metadata_fields": [key for key, value in fields.items() if value],
              "docx_comment_count": len(comments), "docx_tracked_change_elements": changes,
              "profile_matches": matches, "manual_anonymity_review_required": True,
              "fully_anonymized_claimed": False, "metadata_scrubbed": False,
              "scope": "Document properties and DOCX revision/comment markers only. Body text, filenames, links, images, PDF annotations/XMP and other embedded material may identify authors even when these fields are empty."}
    folder = _new_output(output_dir)
    _write(folder / "report.json", report)
    lines = ["# Metadata anonymity check", "", "Read-only inspection; no metadata was removed and anonymity is not certified.", ""]
    lines.extend("- " + key + ": " + (value or "(empty)") for key, value in fields.items())
    lines.extend(["", f"DOCX comments: {len(comments)}; tracked-change elements: {changes}.", ""])
    lines.extend("- Profile match: " + item["field"] + " / " + item["matched_profile_value"] for item in matches)
    lines.extend(["", report["scope"], ""])
    _write(folder / "metadata-check.md", "\n".join(lines))
    _manifest(folder)
    if digest_file(file) != original_sha or profile is not None and digest_file(profile) != profile_sha:
        raise ValueError("Inputs changed during metadata inspection")
    return {"output_dir": str(folder), **report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    authors = commands.add_parser("authors", help="Apply explicit coauthor facts to a new Markdown copy")
    authors.add_argument("--profile", type=Path, required=True)
    authors.add_argument("--manuscript", type=Path, required=True)
    authors.add_argument("--anonymous", action="store_true")
    responses = commands.add_parser("responses", help="Prepare supplied reviewer replies with literal change anchors")
    responses.add_argument("--comments", type=Path, required=True)
    responses.add_argument("--before", type=Path, required=True)
    responses.add_argument("--after", type=Path, required=True)
    bundle = commands.add_parser("bundle", help="Copy only explicit submission files into a new local folder")
    bundle.add_argument("--plan", type=Path, required=True)
    bundle.add_argument("--root", type=Path, required=True)
    metadata = commands.add_parser("metadata", help="Inspect actual DOCX/PDF properties without removing them")
    metadata.add_argument("--file", type=Path, required=True)
    metadata.add_argument("--profile", type=Path)
    for command in (authors, responses, bundle, metadata):
        command.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "authors":
            result = prepare_authors(args.profile, args.manuscript, args.output_dir, anonymous=args.anonymous)
        elif args.command == "responses":
            result = prepare_responses(args.comments, args.before, args.after, args.output_dir)
        elif args.command == "bundle":
            result = prepare_bundle(args.plan, args.root, args.output_dir)
        else:
            result = inspect_metadata(args.file, args.output_dir, profile=args.profile)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

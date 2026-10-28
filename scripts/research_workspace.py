"""Optional portable research notes, exact evidence links, and manuscript diffs.

No research is executed and no scientific judgment or historical count is inferred.
All write commands require a new directory and leave existing inputs unchanged.
"""

import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

from _publication_files import digest_file, ensure_unlinked

KINDS = {"source_declared", "observed_static", "derived", "proposed", "measured"}


def _absolute(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError("Use absolute input and output paths")
    ensure_unlinked(path)
    return path.resolve()


def _json(path: Path) -> dict:
    path = _absolute(path)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Research note JSON must be at most 2 MiB")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Research note input must be a JSON object")
    return value


def _relative(root: Path, name: object) -> Path:
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError("Material paths must be portable relative paths using forward slashes")
    parts = PurePosixPath(name)
    if parts.is_absolute() or any(part in {".", "..", ""} for part in name.split("/")):
        raise ValueError("Material paths must remain below their declared root")
    target = root.joinpath(*parts.parts)
    ensure_unlinked(target)
    if not target.resolve().is_relative_to(root):
        raise ValueError("Material path escapes its root")
    return target


def _new_folder(path: Path, *, outside: Path | None = None) -> Path:
    path = _absolute(path)
    if outside is not None and (path.is_relative_to(outside) or outside.is_relative_to(path)):
        raise ValueError("Checkpoint output and source root must be separate trees")
    path.mkdir(parents=True, exist_ok=False)
    return path


def _write(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _manifest(folder: Path) -> None:
    _write(folder / "manifest.json", {"algorithm": "SHA-256", "scope": "Files below this directory; excludes manifest.json. No authenticity or scientific validation is implied.",
           "files": [{"path": p.relative_to(folder).as_posix(), "bytes": p.stat().st_size,
                      "sha256": digest_file(p)} for p in sorted(folder.rglob("*")) if p.is_file()]})


def checkpoint(root: Path, state_path: Path, output_dir: Path) -> dict:
    """Copy explicitly selected materials and supplied notes into a portable tree."""
    root = _absolute(root)
    if not root.is_dir():
        raise ValueError("Material root must be a directory")
    state = _json(state_path)
    required = {"project", "question", "decisions", "next_steps", "constraints", "historical_counts", "files"}
    if set(state) != required or any(not isinstance(state[k], str) for k in ("project", "question")):
        raise ValueError("State requires project, question, decisions, next_steps, constraints, historical_counts and files")
    for key in ("decisions", "next_steps", "constraints", "files"):
        if not isinstance(state[key], list) or any(not isinstance(x, str) for x in state[key]):
            raise ValueError(f"{key} must be a list of strings")
    if not isinstance(state["historical_counts"], dict):
        raise ValueError("historical_counts must retain an explicit object of supplied records")
    names = state["files"]
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("Selected material paths must be distinct")
    sources = [(name, _relative(root, name)) for name in names]
    if any(not path.is_file() for _, path in sources):
        raise ValueError("Every selected material must be an existing regular file")
    folder = _new_folder(output_dir, outside=root)
    rows = []
    for name, source in sources:
        before = digest_file(source)
        target = folder / "materials" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(source.read_bytes())
        if digest_file(source) != before or digest_file(target) != before:
            raise ValueError("A selected material changed while creating the checkpoint")
        rows.append({"path": "materials/" + name, "original_relative_path": name,
                     "bytes": target.stat().st_size, "sha256": before})
    record = {"format_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
              "project": state["project"], "question": state["question"],
              "decisions": state["decisions"], "next_steps": state["next_steps"],
              "constraints": state["constraints"], "historical_counts": state["historical_counts"],
              "historical_count_scope": "Supplied historical values retained verbatim; not recalculated or an execution budget.",
              "materials": rows}
    _write(folder / "checkpoint.json", record)
    prose = ["# Research continuation", "", state["project"], "", state["question"]]
    for key in ("decisions", "next_steps", "constraints"):
        prose += ["", "## " + key.replace("_", " ").title(), ""] + ["- " + x for x in state[key]]
    prose += ["", "## Captured materials", ""] + [f"- {item['path']} — SHA-256 `{item['sha256']}`" for item in rows]
    prose += ["", "Historical counts are supplied records, not new measurements. Run resume to check the copied file hashes before continuing.", ""]
    with (folder / "resume.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(prose))
    _manifest(folder)
    return {"checkpoint": str(folder), "material_count": len(rows), "existing_inputs_modified": False}


def resume(folder: Path) -> dict:
    """Verify a moved checkpoint without locating the original PC or rewriting it."""
    folder = _absolute(folder)
    manifest = _json(folder / "manifest.json")
    record = _json(folder / "checkpoint.json")
    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise ValueError("Checkpoint manifest requires a file list")
    issues, listed = [], set()
    for item in rows:
        if not isinstance(item, dict) or not {"path", "bytes", "sha256"} <= item.keys():
            raise ValueError("Malformed checkpoint manifest entry")
        path = _relative(folder, item["path"])
        if item["path"].casefold() in listed:
            raise ValueError("Duplicate checkpoint manifest entry")
        listed.add(item["path"].casefold())
        if not path.is_file():
            issues.append({"path": item["path"], "status": "missing"})
        elif path.stat().st_size != item["bytes"] or digest_file(path) != item["sha256"]:
            issues.append({"path": item["path"], "status": "changed"})
    if "checkpoint.json" not in listed or "resume.md" not in listed:
        raise ValueError("Checkpoint notes are absent from its manifest")
    for path in folder.rglob("*"):
        ensure_unlinked(path)
        if path.is_file():
            name = path.relative_to(folder).as_posix()
            if name != "manifest.json" and name.casefold() not in listed:
                issues.append({"path": name, "status": "unlisted"})
    materials = record.get("materials")
    if not isinstance(materials, list):
        raise ValueError("Checkpoint requires retained material records")
    expected = {item["path"]: item for item in rows}
    for item in materials:
        if not isinstance(item, dict) or not {"path", "bytes", "sha256"} <= item.keys():
            raise ValueError("Malformed retained material record")
        _relative(folder, item["path"])
        bound = expected.get(item["path"])
        if bound is None or any(bound[key] != item[key] for key in ("bytes", "sha256")):
            issues.append({"path": item["path"], "status": "unbound_material"})
    return {"verified": not issues, "issues": issues, "checkpoint": str(folder),
            "notes": record, "scope": "Hash consistency of copied records only; historical facts, source identity and scientific claims require judgment."}


def evidence(root: Path, ledger_path: Path, output_dir: Path) -> dict:
    """Check literal manuscript/source bindings without asserting entailment."""
    root, ledger = _absolute(root), _json(ledger_path)
    manuscript = _relative(root, ledger.get("manuscript"))
    snapshot = manuscript.read_bytes()
    text = snapshot.decode("utf-8-sig")
    initial = hashlib.sha256(snapshot).hexdigest()
    claims = ledger.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("Evidence ledger requires a nonempty claims list")
    output, identifiers = [], set()
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("id"), str) or not claim["id"] or claim["id"] in identifiers:
            raise ValueError("Every claim requires a distinct nonempty string id")
        identifiers.add(claim["id"])
        if claim.get("kind") not in KINDS or not isinstance(claim.get("claim"), str) or not claim["claim"].strip():
            raise ValueError("Every claim requires text and an explicit evidence kind")
        anchor = claim.get("manuscript_quote")
        if not isinstance(anchor, str) or not anchor:
            raise ValueError("Every claim requires a literal manuscript_quote")
        sources = claim.get("sources")
        if not isinstance(sources, list):
            raise ValueError("Claim sources must be a list")
        issues = [] if anchor in text else ["manuscript_quote_not_found"]
        if not sources:
            issues.append("no_source_bindings")
        witnesses = []
        for source in sources:
            if not isinstance(source, dict):
                raise ValueError("Source witness must be an object")
            path = _relative(root, source.get("path"))
            start, end, quote = source.get("start_line"), source.get("end_line"), source.get("quote")
            if type(start) is not int or type(end) is not int or not 1 <= start <= end or not isinstance(quote, str) or not quote:
                raise ValueError("Source witness requires positive start_line/end_line and a nonempty quote")
            status = []
            observed_hash = None
            if not path.is_file():
                status.append("missing_source")
            else:
                observed_hash = digest_file(path)
                lines = path.read_text(encoding="utf-8-sig").splitlines()
                if end > len(lines) or "\n".join(lines[start - 1:end]) != quote:
                    status.append("source_quote_mismatch")
                if source.get("sha256") is not None and source["sha256"] != observed_hash:
                    status.append("source_hash_mismatch")
                if digest_file(path) != observed_hash:
                    raise ValueError("Evidence source changed during inspection")
            witnesses.append({**source, "observed_sha256": observed_hash, "issues": status})
            issues.extend(status)
        output.append({**claim, "sources": witnesses, "issues": sorted(set(issues)), "bindings_match": not issues})
    if digest_file(manuscript) != initial:
        raise ValueError("Manuscript changed during evidence inspection")
    folder = _new_folder(output_dir)
    report = {"manuscript": ledger["manuscript"], "manuscript_sha256": initial, "claims": output,
              "bindings_match": all(item["bindings_match"] for item in output),
              "scope": "Literal location/hash checks only. Matching witnesses do not establish claim truth, novelty, runtime observation or scientific entailment."}
    _write(folder / "evidence.json", report)
    prose = ["# Claim and source bindings", "", report["scope"], "",
             f"Manuscript: {report['manuscript']}", "", f"Manuscript SHA-256: `{initial}`", ""]
    for item in output:
        prose += ["## " + item["id"], "", item["claim"], "", "Kind: " + item["kind"],
                  "", "Binding status: " + ("matches" if item["bindings_match"] else ", ".join(item["issues"])), ""]
        prose += [f"- {s['path']}:{s['start_line']}–{s['end_line']} ({', '.join(s['issues']) or 'matches'})" for s in item["sources"]]
    with (folder / "evidence.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(prose) + "\n")
    _manifest(folder)
    return {"output_dir": str(folder), "bindings_match": report["bindings_match"], "claim_count": len(output)}


def _structure(text: str) -> dict:
    return {"headings": re.findall(r"^#{1,6}\s+(.+)$", text, flags=re.MULTILINE),
            "citation_labels": sorted(set(re.findall(r"\[(\d+)\]", text)), key=int),
            "markdown_table_count": len(re.findall(r"^\s*\|?\s*:?-{3,}:?\s*\|(?:\s*:?-{3,}:?\s*\|?)+\s*$", text, flags=re.MULTILINE))}


def compare(before: Path, after: Path, output_dir: Path) -> dict:
    before, after = _absolute(before), _absolute(after)
    old_hash, new_hash = digest_file(before), digest_file(after)
    old, new = before.read_text(encoding="utf-8-sig"), after.read_text(encoding="utf-8-sig")
    patch = "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                          fromfile=before.name, tofile=after.name))
    if digest_file(before) != old_hash or digest_file(after) != new_hash:
        raise ValueError("Manuscript changed during comparison")
    folder = _new_folder(output_dir)
    report = {"before": {"sha256": old_hash, **_structure(old)}, "after": {"sha256": new_hash, **_structure(new)},
              "identical_bytes": old_hash == new_hash,
              "scope": "Text and structural differences, not a judgment of scientific improvement, author approval or a new review."}
    _write(folder / "comparison.json", report)
    with (folder / "changes.diff").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(patch)
    _manifest(folder)
    return {"output_dir": str(folder), "identical_bytes": report["identical_bytes"]}


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def status(root: Path, state_path: Path, output_dir: Path) -> dict:
    """Summarize explicit artifacts and their version bindings, without judging quality."""
    root, state = _absolute(root), _json(state_path)
    required = {"project", "question", "current_manuscript", "artifacts", "remaining_tasks", "historical_counts"}
    if set(state) != required or any(not isinstance(state[k], str) or not state[k].strip() for k in ("project", "question")):
        raise ValueError("Status requires project, question, current_manuscript, artifacts, remaining_tasks and historical_counts")
    if not isinstance(state["historical_counts"], dict) or not isinstance(state["remaining_tasks"], list) or any(not isinstance(x, str) for x in state["remaining_tasks"]):
        raise ValueError("Status requires supplied historical_counts and a remaining_tasks string list")
    manuscript = _relative(root, state["current_manuscript"])
    if not manuscript.is_file():
        raise ValueError("Current manuscript must be an existing regular file")
    manuscript_hash = digest_file(manuscript)
    if not isinstance(state["artifacts"], list) or not state["artifacts"]:
        raise ValueError("Status requires a nonempty explicit artifacts list")
    rows, identifiers = [], set()
    for item in state["artifacts"]:
        if not isinstance(item, dict) or set(item) - {"id", "role", "path", "sha256", "manuscript_sha256"}:
            raise ValueError("Artifact supports id, role, path, sha256 and optional manuscript_sha256")
        if any(not isinstance(item.get(k), str) or not item[k].strip() for k in ("id", "role")) or item["id"] in identifiers:
            raise ValueError("Artifacts require a distinct id and nonempty role")
        identifiers.add(item["id"])
        expected = _sha256(item.get("sha256"), "Artifact sha256")
        bound = item.get("manuscript_sha256")
        if bound is not None:
            _sha256(bound, "Artifact manuscript_sha256")
        path = _relative(root, item.get("path"))
        observed = digest_file(path) if path.is_file() else None
        if observed is None:
            condition = "missing"
        elif observed != expected:
            condition = "changed"
        elif path == manuscript or bound == manuscript_hash:
            condition = "current"
        elif bound is not None:
            condition = "stale"
        else:
            condition = "unbound"
        rows.append({**item, "observed_sha256": observed, "status": condition})
    if digest_file(manuscript) != manuscript_hash:
        raise ValueError("Current manuscript changed while preparing status")
    for item in rows:
        path = _relative(root, item["path"])
        if (digest_file(path) if path.is_file() else None) != item["observed_sha256"]:
            raise ValueError("An artifact changed while preparing status")
    summary = {name: sum(item["status"] == name for item in rows) for name in ("current", "stale", "changed", "missing", "unbound")}
    report = {"format_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
              "project": state["project"], "question": state["question"],
              "current_manuscript": {"path": state["current_manuscript"], "sha256": manuscript_hash},
              "artifacts": rows, "artifact_counts": summary, "remaining_tasks": state["remaining_tasks"],
              "historical_counts": state["historical_counts"],
              "scope": "Explicit selected files and supplied manuscript bindings only. Current means matching bytes and version binding, not quality, approval or readiness. Historical counts are retained verbatim, not recalculated or an execution budget."}
    folder = _new_folder(output_dir)
    _write(folder / "status.json", report)
    prose = ["# Research status", "", report["project"], "", report["question"], "",
             f"Current manuscript: {state['current_manuscript']}", "", f"SHA-256: `{manuscript_hash}`", "",
             "| Artifact | Role | Status |", "| --- | --- | --- |"]
    prose += [f"| {item['path'].replace('|', '&#124;')} | {item['role'].replace('|', '&#124;')} | {item['status']} |" for item in rows]
    prose += ["", "## Remaining work", ""] + ["- " + task for task in state["remaining_tasks"]]
    prose += ["", "Historical counts (supplied): `" + json.dumps(state["historical_counts"], ensure_ascii=False) + "`", "", report["scope"], ""]
    with (folder / "status.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(prose))
    _manifest(folder)
    return {"output_dir": str(folder), "artifact_counts": summary, "existing_inputs_modified": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    c = commands.add_parser("checkpoint")
    c.add_argument("--root", type=Path, required=True)
    c.add_argument("--state", type=Path, required=True)
    c.add_argument("--output-dir", type=Path, required=True)
    c = commands.add_parser("resume")
    c.add_argument("--checkpoint", type=Path, required=True)
    c = commands.add_parser("evidence")
    c.add_argument("--root", type=Path, required=True)
    c.add_argument("--ledger", type=Path, required=True)
    c.add_argument("--output-dir", type=Path, required=True)
    c = commands.add_parser("compare")
    c.add_argument("--before", type=Path, required=True)
    c.add_argument("--after", type=Path, required=True)
    c.add_argument("--output-dir", type=Path, required=True)
    c = commands.add_parser("status")
    c.add_argument("--root", type=Path, required=True)
    c.add_argument("--state", type=Path, required=True)
    c.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "checkpoint":
            result = checkpoint(args.root, args.state, args.output_dir)
        elif args.command == "resume":
            result = resume(args.checkpoint)
        elif args.command == "evidence":
            result = evidence(args.root, args.ledger, args.output_dir)
        elif args.command == "status":
            result = status(args.root, args.state, args.output_dir)
        else:
            result = compare(args.before, args.after, args.output_dir)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("verified") is False or result.get("bindings_match") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())

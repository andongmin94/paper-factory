"""Retain selected repository bytes for an agent's subsequent source reading."""

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
from urllib.parse import quote, urlsplit

from _publication_files import ensure_unlinked


def _repository_url(url: str) -> str:
    if not isinstance(url, str) or any(character.isspace() or ord(character) < 32 for character in url):
        raise ValueError("Repository URL must be an HTTPS GitHub repository URL without credentials")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc.casefold() != "github.com" or parsed.query or parsed.fragment:
        raise ValueError("Use https://github.com/OWNER/REPOSITORY without credentials, ports, query or fragment")
    parts = parsed.path.rstrip("/").split("/")
    if len(parts) != 3 or parts[0] or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", parts[1]):
        raise ValueError("Repository URL must name exactly one GitHub owner and repository")
    repository = parts[2].removesuffix(".git")
    if repository in {"", ".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]+", repository):
        raise ValueError("Repository URL must name exactly one GitHub owner and repository")
    return f"https://github.com/{parts[1]}/{repository}"


def _paths(paths: list[str]) -> list[str]:
    if not isinstance(paths, list) or not paths:
        raise ValueError("Supply a nonempty explicit list of repository file paths")
    for path in paths:
        if (not isinstance(path, str) or not path or "\\" in path or ":" in path
                or any(ord(character) < 32 or ord(character) == 127 for character in path)
                or PurePosixPath(path).is_absolute()
                or any(part in {"", ".", ".."} for part in path.split("/"))):
            raise ValueError("Repository paths must be relative forward-slash file paths without traversal")
        path.encode("utf-8")
    if len({path.casefold() for path in paths}) != len(paths):
        raise ValueError("Selected repository paths must be distinct, including case")
    return paths


def _git(arguments: list[str], *, cwd: Path, hooks: Path) -> bytes:
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"}
    command = ["git", "-c", f"core.hooksPath={hooks}", "-c", "core.fsmonitor=false",
               "-c", "submodule.recurse=false", *arguments]
    try:
        result = subprocess.run(command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"Git {arguments[0]} timed out; no repository capture was completed") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Git {arguments[0]} failed" + (": " + detail if detail else ""))
    return result.stdout


def capture_repository(url: str, output_dir: Path, *, paths: list[str], ref: str | None = None) -> dict:
    """Capture explicit regular files at one commit, without checking out or running code."""
    normalized = _repository_url(url)
    selected = _paths(paths)
    if ref is not None and (not isinstance(ref, str) or not ref or ref.startswith("-")):
        raise ValueError("ref must be a branch, tag or full 40-character commit SHA")
    pinned_commit = ref.lower() if ref is not None and re.fullmatch(r"[0-9a-fA-F]{40}", ref) else None
    if not output_dir.is_absolute():
        raise ValueError("Repository capture output must be an absolute new directory")
    ensure_unlinked(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Repository capture output already exists: {output_dir}")

    with tempfile.TemporaryDirectory(prefix="paper-factory-repository-") as temporary:
        temporary = Path(temporary)
        hooks = temporary / "empty-hooks"
        hooks.mkdir()
        checkout = temporary / "repository"
        if pinned_commit is not None:
            _git(["init", "--quiet", f"--template={hooks}", str(checkout)], cwd=temporary, hooks=hooks)
            _git(["fetch", "--quiet", "--depth=1", "--no-tags", "--no-recurse-submodules", "--",
                  normalized, pinned_commit], cwd=checkout, hooks=hooks)
            revision = "FETCH_HEAD"
        else:
            if ref is not None:
                _git(["check-ref-format", "refs/heads/" + ref], cwd=temporary, hooks=hooks)
            clone = ["clone", "--quiet", "--depth=1", "--single-branch", "--no-checkout",
                     "--no-recurse-submodules", f"--template={hooks}"]
            if ref is not None:
                clone.append("--branch=" + ref)
            _git([*clone, "--", normalized, str(checkout)], cwd=temporary, hooks=hooks)
            revision = "HEAD"
        commit = _git(["rev-parse", "--verify", revision + "^{commit}"], cwd=checkout, hooks=hooks).decode("ascii").strip()
        if pinned_commit is not None and commit != pinned_commit:
            raise ValueError(f"Requested commit {pinned_commit} resolved to a different commit: {commit}")
        tree = _git(["rev-parse", "--verify", f"{commit}^{{tree}}"], cwd=checkout, hooks=hooks).decode("ascii").strip()
        object_format = _git(["rev-parse", "--show-object-format"], cwd=checkout, hooks=hooks).decode("ascii").strip()
        timestamp = _git(["show", "-s", "--format=%cI", commit], cwd=checkout, hooks=hooks).decode("ascii").strip()
        entries = {}
        for row in _git(["ls-tree", "-r", "-z", "--full-tree", commit], cwd=checkout, hooks=hooks).split(b"\0"):
            if row:
                metadata, name = row.split(b"\t", 1)
                mode, kind, object_id = metadata.decode("ascii").split(" ")
                entries[name] = (mode, kind, object_id)
        sources, contents = [], []
        for name in selected:
            entry = entries.get(name.encode("utf-8"))
            for prefix in [name, *[parent.as_posix() for parent in PurePosixPath(name).parents if parent.as_posix() != "."]]:
                ancestor = entries.get(prefix.encode("utf-8"))
                if ancestor is not None and ancestor[0] in {"120000", "160000"}:
                    kind = "symlink" if ancestor[0] == "120000" else "submodule"
                    raise ValueError(f"Selected repository path traverses or selects a {kind}: {prefix}")
            if entry is None:
                raise ValueError(f"Selected repository file is missing or is a directory: {name}")
            mode, kind, blob = entry
            if kind != "blob" or mode not in {"100644", "100755"}:
                raise ValueError(f"Selected repository path is not a tracked regular file: {name}")
            data = _git(["show", "--no-ext-diff", "--no-textconv", blob], cwd=checkout, hooks=hooks)
            sources.append({"repository_path": name, "path": "sources/" + name, "git_mode": mode,
                            "git_blob_sha": blob, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                            "commit_pinned_url": normalized + "/blob/" + commit + "/" + quote(name, safe="/")})
            contents.append(data)

    report = {
        "format_version": 1, "repository_url": normalized, "requested_ref": ref,
        "commit_sha": commit, "tree_sha": tree, "git_object_format": object_format,
        "commit_timestamp": timestamp, "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources, "tracked_entry_count": len(entries), "retained_file_count": len(sources),
        "unretained_entry_count": len(entries) - len(sources), "project_code_executed": False,
        "scope": ("Original bytes of explicitly selected tracked regular files at one Git commit only. "
                  "Git blob IDs use git_object_format; sha256 hashes the retained file bytes. "
                  "Tracked/unretained counts include symlink and submodule entries, which cannot be captured. "
                  "No checkout, build, tests or repository hooks were run. This capture is not source reading, "
                  "semantic analysis, proof of claim truth, signature verification or verification of remote authenticity.")
    }
    # Import only when called: research_workspace's CLI imports this adapter.
    from research_workspace import _manifest, _write

    ensure_unlinked(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    for source, data in zip(sources, contents):
        destination = output_dir / source["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(data)
    _write(output_dir / "repository.json", report)
    _manifest(output_dir)
    return {"output_dir": str(output_dir), **report}

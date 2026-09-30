"""Copy research assets into a sanitized, content-addressed local snapshot."""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .models import Asset, Project, uid
from .workspace import Workspace, digest_file, ensure_unlinked, is_link, pf_home, write_json

IGNORED_DIRECTORIES = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SECRET_NAMES = {"credentials", "credentials.json", "token.json", "auth.json", "secrets.json", "secrets.yaml", "secrets.yml", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", ".netrc", "_netrc", ".npmrc", ".pypirc", ".git-credentials"}


def _secret(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith(".env") or name in SECRET_NAMES or bool(re.search(r"service[-_]?account|private[-_]?key|access[-_]?token", name)) or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".keystore"}


def asset_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv", ".json", ".h5", ".hdf5", ".parquet", ".npy", ".npz"}:
        return "data"
    if suffix in {".py", ".r", ".m", ".jl", ".js", ".ts", ".tsx", ".c", ".cpp", ".rs", ".go", ".java"}:
        return "code"
    if suffix in {".png", ".jpg", ".jpeg", ".svg", ".tif", ".tiff"}:
        return "figure"
    if suffix in {".tex", ".pdf", ".docx"}:
        return "manuscript"
    if suffix in {".bib", ".ris"}:
        return "bibliography"
    if suffix in {".md", ".txt", ".rst"}:
        return "note"
    return "other"


def inventory(root: Path, *, sanitize: bool = False) -> list[Asset]:
    """Inventory regular files only; snapshots must contain no symlinks."""
    ensure_unlinked(root)
    if not root.is_dir():
        raise ValueError("Snapshot root is missing or is not a directory")
    assets: list[Asset] = []
    def inaccessible(error: OSError) -> None:
        raise error
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=inaccessible):
        base = Path(directory)
        for name in list(dirs):
            path = base / name
            if is_link(path):
                if not sanitize:
                    raise ValueError("Snapshot contains a symlink")
                dirs.remove(name)
            elif sanitize and (name.casefold() in IGNORED_DIRECTORIES or _secret(path)):
                dirs.remove(name)
        for name in files:
            path = base / name
            if is_link(path):
                if not sanitize:
                    raise ValueError("Snapshot contains a symlink")
                continue
            if sanitize and _secret(path):
                continue
            if not path.is_file():
                raise ValueError(f"Snapshot contains a nonregular file: {path.name}")
            assets.append(Asset(path=path.relative_to(root).as_posix(), sha256=digest_file(path), size=path.stat().st_size, kind=asset_kind(path)))
    return sorted(assets, key=lambda item: item.path)


def snapshot_digest(assets: list[Asset]) -> str:
    data = [asset.model_dump() for asset in sorted(assets, key=lambda item: item.path)]
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def verify_snapshot(ws: Workspace) -> None:
    project = ws.latest("project", Project)
    current = inventory(ws.path("source"))
    if snapshot_digest(current) != project.snapshot_digest or current != project.assets:
        raise ValueError("Source snapshot was modified; experiment evidence is invalid")


def _safe_source(source: str) -> str:
    if "://" in source:
        parts = urlsplit(source)
        hostname = parts.hostname or ""
        if parts.port:
            hostname += f":{parts.port}"
        # Keep the SSH login name, but remove HTTP passwords/tokens and query strings.
        if parts.scheme == "ssh" and parts.username:
            hostname = f"{parts.username}@{hostname}"
        return urlunsplit((parts.scheme, hostname, parts.path, "", ""))
    return source


def _git_commit(path: Path) -> str | None:
    result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True, check=False, timeout=30)
    return result.stdout.strip() or None if result.returncode == 0 else None


def ingest(source: str, workspace_root: Path | None = None) -> Workspace:
    local = Path(source).expanduser()
    is_remote = bool(re.match(r"^(?:https?://|ssh://|git://|[^/\\\s]+@[^:]+:)", source))
    if not is_remote and not local.is_dir():
        raise ValueError("Project input must be a local directory or a Git URL")
    if not is_remote:
        ensure_unlinked(local)
    source_path = local.resolve() if not is_remote else None
    safe_source = _safe_source(source) if is_remote else str(source_path)
    name = Path(urlsplit(safe_source).path if "://" in safe_source else safe_source).name.removesuffix(".git") or "project"
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-") or "project"
    root = (workspace_root or pf_home() / "projects" / f"{slug}-{uid('workspace')}").expanduser()
    ensure_unlinked(root)
    root = root.resolve()
    if source_path is not None and (root.is_relative_to(source_path) or source_path.is_relative_to(root)):
        raise ValueError("Project source and workspace must be separate directories")
    if root.exists() and any(root.iterdir()):
        raise ValueError("Workspace destination must be empty")

    with tempfile.TemporaryDirectory(prefix="paperfactory-ingest-") as temporary:
        if is_remote:
            source_path = Path(temporary) / "checkout"
            clone_environment = dict(os.environ, GIT_TERMINAL_PROMPT="0")
            try:
                result = subprocess.run(["git", "clone", "--depth", "1", "--", source, str(source_path)], capture_output=True, text=True, check=False,
                                        timeout=300, env=clone_environment)
            except subprocess.TimeoutExpired as error:
                raise ValueError("Git clone timed out; check the network and repository access") from None
            if result.returncode:
                # Git's diagnostics may echo URL credentials. Do not persist or display them.
                raise ValueError("Git clone failed; check the URL and existing Git credentials")
        assert source_path is not None
        try:
            commit = _git_commit(source_path)
        except FileNotFoundError:
            commit = None
        assets = inventory(source_path, sanitize=True)
        ws = Workspace.create(root)
        for asset in assets:
            origin = source_path / asset.path
            ensure_unlinked(origin)
            target = ws.path(f"source/{asset.path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, target)
            if digest_file(target) != asset.sha256:
                raise ValueError("Source changed during ingestion; retry from a stable source")
            target.chmod(stat.S_IMODE(origin.stat().st_mode) & ~0o222)
        project = Project(name=name, source=safe_source, source_commit=commit, snapshot_digest=snapshot_digest(assets), assets=assets)
        ws.save("project", project)
        write_json(ws.path("project.json"), project)
        verify_snapshot(ws)
        ws.make_current()
        return ws

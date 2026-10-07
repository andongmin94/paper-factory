"""Copy research assets into a sanitized, content-addressed local snapshot."""

import hashlib
import io
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
import zipfile

import httpx

from .models import Asset, Project, now
from .workspace import Workspace, digest_file, ensure_unlinked, is_link, loads_json, safe_relative, write_json

IGNORED_DIRECTORIES = {".git", ".codex", "codex-auth", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SECRET_NAMES = {"credentials", "credentials.json", "token.json", "auth.json", "secrets.json", "secrets.yaml", "secrets.yml", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", ".netrc", "_netrc", ".npmrc", ".pypirc", ".git-credentials"}
MAX_REPOSITORY_ARCHIVE = 24 * 1024 * 1024
MAX_REPOSITORY_BYTES = 64 * 1024 * 1024
MAX_REPOSITORY_FILES = 10000


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






def _github_fetch(client, url: str, maximum: int) -> bytes:
    # Both authorities and endpoint paths are constructed here. Redirects,
    # credentials, user-supplied refs and other hosts are never requested.
    with client.stream("GET", url) as response:
        response.raise_for_status()
        chunks = bytearray()
        for chunk in response.iter_bytes():
            chunks.extend(chunk)
            if len(chunks) > maximum:
                raise ValueError("Public repository response exceeds its byte limit")
        return bytes(chunks)


def _github_checkout(source: str, destination: Path) -> tuple[str, dict]:
    match = re.fullmatch(r"https://github\.com/([A-Za-z0-9-]{1,39})/([A-Za-z0-9_.-]{1,100})/?", source)
    if not match or match[2] in {".", ".."}:
        raise ValueError("Remote project must be a public GitHub repository URL without credentials or query parameters")
    owner, repository = match[1], match[2].removesuffix(".git")
    if not repository:
        raise ValueError("Invalid public repository name")
    with httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=False, trust_env=False,
                      headers={"User-Agent": "Paper-Factory-Desktop", "Accept": "application/vnd.github+json"}) as client:
        metadata_url = f"https://api.github.com/repos/{owner}/{repository}/commits/HEAD"
        metadata_raw = _github_fetch(client, metadata_url, 1024 * 1024)
        metadata = loads_json(metadata_raw)
        commit = metadata.get("sha") if isinstance(metadata, dict) else None
        if not isinstance(commit, str) or not re.fullmatch(r"[a-f0-9]{40}", commit):
            raise ValueError("GitHub did not provide a full immutable commit")
        archive_url = f"https://codeload.github.com/{owner}/{repository}/zip/{commit}"
        archive_raw = _github_fetch(client, archive_url, MAX_REPOSITORY_ARCHIVE)
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_REPOSITORY_FILES or sum(item.file_size for item in entries) > MAX_REPOSITORY_BYTES:
            raise ValueError("Public repository archive exceeds its file or expansion limit")
        roots = {item.filename.split("/", 1)[0] for item in entries}
        if len(roots) != 1 or not entries:
            raise ValueError("Public repository archive has an invalid root")
        expected_root = repository + "-" + commit
        if len(roots) != 1 or next(iter(roots)).casefold() != expected_root.casefold():
            raise ValueError("Public repository archive root differs from its fixed commit")
        expected_root = next(iter(roots))
        names = set()
        destination.mkdir()
        for item in entries:
            name = item.filename
            if name in {expected_root, expected_root + "/"} and item.is_dir():
                continue
            relative = name[len(expected_root) + 1:].rstrip("/") if name.startswith(expected_root + "/") else ""
            target = safe_relative(destination, relative)
            if relative.casefold() in names or item.flag_bits & 1 or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("Public repository archive contains linked, encrypted or duplicate files")
            names.add(relative.casefold())
            if item.is_dir():
                continue
            if any(part.casefold() in IGNORED_DIRECTORIES or _secret(Path(part)) for part in Path(relative).parts):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(archive.read(item))
            target.chmod(0o644)
    return commit, {"format": "paper-factory-public-github-source-v1", "repository": source, "commit": commit,
                    "retrieved_at": now(), "metadata_url": metadata_url,
                    "metadata_sha256": hashlib.sha256(metadata_raw).hexdigest(),
                    "archive_url": archive_url, "archive_sha256": hashlib.sha256(archive_raw).hexdigest(),
                    "archive_size": len(archive_raw), "downloaded_files": len(entries)}


def ingest(source: str, workspace_root: Path) -> Workspace:
    local = Path(source).expanduser()
    is_remote = bool(re.match(r"^(?:https?://|ssh://|git://|[^/\\\s]+@[^:]+:)", source))
    if not is_remote and not local.is_dir():
        raise ValueError("Project input must be a local directory or a public GitHub repository URL")
    if not is_remote:
        ensure_unlinked(local)
    source_path = local.resolve() if not is_remote else None
    if source_path is not None and source_path.name.casefold() in {".codex", "codex-auth"}:
        raise ValueError("Private authentication directories cannot be imported as research projects")
    safe_source = source if is_remote else str(source_path)
    name = Path(urlsplit(safe_source).path if "://" in safe_source else safe_source).name.removesuffix(".git") or "project"
    root = workspace_root.expanduser()
    ensure_unlinked(root)
    root = root.resolve()
    if source_path is not None and (root.is_relative_to(source_path) or source_path.is_relative_to(root)):
        raise ValueError("Project source and workspace must be separate directories")
    if root.exists() and any(root.iterdir()):
        raise ValueError("Workspace destination must be empty")

    with tempfile.TemporaryDirectory(prefix="paperfactory-ingest-") as temporary:
        if is_remote:
            source_path = Path(temporary) / "checkout"
            try:
                commit, collection = _github_checkout(source, source_path)
            except httpx.HTTPError:
                raise ValueError("Public GitHub source retrieval failed; check the repository URL and network") from None
        assert source_path is not None
        if not is_remote:
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
        if is_remote:
            write_json(ws.path("source-collection.json"), collection)
        verify_snapshot(ws)
    return ws

"""Frozen, sanitized source snapshots; all input bytes are synthetic fixtures."""
import hashlib
import io
import zipfile

import httpx
import pytest
from paper_factory import project
from paper_factory.models import Project


@pytest.fixture
def imported(tmp_path):
    source = tmp_path / "original"
    source.mkdir()
    (source / "original.js").write_bytes(b"export const transform=x=>x+1;\n")
    (source / "data.json").write_bytes(b'{"units":[1,2,3]}')
    (source / ".env").write_text("SYNTHETIC_TOKEN=do-not-copy")
    (source / "id_ed25519").write_text("synthetic-private-key")
    (source / "node_modules").mkdir()
    (source / "node_modules/ignored.js").write_text("ignored")
    return project.ingest(str(source), tmp_path / "workspace"), source


def test_sanitized_snapshot_preserves_exact_bytes_and_originals_without_current_pointer(imported, tmp_path, monkeypatch):
    ws, source = imported
    original = project.inventory(source, sanitize=True)
    assert ws.latest("project", Project).assets == original
    assert not (ws.root / "source/.env").exists()
    assert not (ws.root / "source/id_ed25519").exists()
    assert not (ws.root / "source/node_modules").exists()
    monkeypatch.chdir(tmp_path)
    project.verify_snapshot(ws)
    other = project.ingest(str(source), tmp_path / "another-workspace")
    assert other.latest("project", Project).snapshot_digest == ws.latest("project", Project).snapshot_digest
    assert project.inventory(source, sanitize=True) == original
    for asset in original:
        assert ws.path("source/" + asset.path).read_bytes() == (source / asset.path).read_bytes()
    assert not (tmp_path / "current.json").exists()


def test_nested_workspace_is_rejected_without_source_changes(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError, match="separate"):
        project.ingest(str(source), source / "workspace")
    with pytest.raises(ValueError, match="separate"):
        project.ingest(str(source), tmp_path)
    assert list(source.iterdir()) == []


def test_snapshot_symlinks_do_not_import_unrelated_files(imported, tmp_path):
    _, source = imported
    secret = tmp_path / "external.txt"
    secret.write_text("synthetic external fixture")
    try:
        (source / "external-link").symlink_to(secret)
        (source / "dir-link").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires Windows developer mode")
    ws = project.ingest(str(source), tmp_path / "symlink-workspace")
    assert not ws.path("source/external-link").exists() and not ws.path("source/dir-link").exists()


def test_changed_frozen_original_cannot_pass_verification(imported):
    ws, _ = imported
    changed = ws.path("source/original.js")
    changed.chmod(0o644)
    changed.write_text("changed original")
    with pytest.raises(ValueError, match="modified"):
        project.verify_snapshot(ws)


def test_credentials_are_rejected_before_any_remote_request(tmp_path, monkeypatch):
    monkeypatch.setattr(project.httpx, "Client", lambda **kw: pytest.fail("Invalid credential URL reached HTTP"))
    source = "https://user:synthetic-secret@github.com/owner/project?access_token=synthetic-secret"
    with pytest.raises(ValueError, match="public GitHub") as failure:
        project.ingest(source, tmp_path / "workspace")
    assert "synthetic-secret" not in str(failure.value)
    assert not (tmp_path / "workspace").exists()


def public_archive(monkeypatch, entries):
    commit = "a" * 40
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(f"fixture-{commit}/{name}", content)
    archive_bytes = raw.getvalue()
    original_client = httpx.Client

    def respond(request):
        if request.url.host == "api.github.com":
            return httpx.Response(200, json={"sha": commit})
        assert str(request.url) == f"https://codeload.github.com/fixture-owner/fixture/zip/{commit}"
        return httpx.Response(200, content=archive_bytes)

    monkeypatch.setattr(project.httpx, "Client", lambda **options: original_client(
        transport=httpx.MockTransport(respond), **options))
    return archive_bytes


def test_public_snapshot_retains_large_binary_and_license_within_total_budget(tmp_path, monkeypatch):
    binary = bytes(range(256)) * (8 * 1024 * 1024 // 256) + b"\x00"
    license_bytes = b"Synthetic source license fixture; retain exact bytes.\n"
    archive = public_archive(monkeypatch, {"runtime/editor.wasm": binary, "LICENSE": license_bytes,
                                           "source.ts": b"export const evaluate = (value: number) => value;\n"})
    assert len(binary) > 8 * 1024 * 1024
    assert len(archive) < project.MAX_REPOSITORY_ARCHIVE
    ws = project.ingest("https://github.com/fixture-owner/fixture", tmp_path / "workspace")
    imported = ws.latest("project", Project)
    asset = next(asset for asset in imported.assets if asset.path == "runtime/editor.wasm")
    assert asset.size == len(binary)
    assert asset.sha256 == hashlib.sha256(binary).hexdigest()
    assert ws.path("source/runtime/editor.wasm").read_bytes() == binary
    assert ws.path("source/LICENSE").read_bytes() == license_bytes
    assert imported.source_commit == "a" * 40
    project.verify_snapshot(ws)


def test_public_archive_rejects_total_expansion_before_extraction(tmp_path, monkeypatch):
    # Each file fits the aggregate limit, but together these exceed it.
    payload = b"\x00" * (project.MAX_REPOSITORY_BYTES // 2 + 1)
    archive = public_archive(monkeypatch, {"first.bin": payload, "second.bin": payload})
    assert len(archive) < project.MAX_REPOSITORY_ARCHIVE
    monkeypatch.setattr(project, "safe_relative", lambda *args: pytest.fail("Oversized archive reached extraction"))
    destination = tmp_path / "checkout"
    with pytest.raises(ValueError, match="file or expansion limit"):
        project._github_checkout("https://github.com/fixture-owner/fixture", destination)
    assert not destination.exists()


def test_public_archive_rejects_file_count_before_extraction(tmp_path, monkeypatch):
    archive = public_archive(monkeypatch, {f"file-{index}.bin": b"" for index in range(project.MAX_REPOSITORY_FILES + 1)})
    assert len(archive) < project.MAX_REPOSITORY_ARCHIVE
    monkeypatch.setattr(project, "safe_relative", lambda *args: pytest.fail("Excessive file count reached extraction"))
    destination = tmp_path / "checkout"
    with pytest.raises(ValueError, match="file or expansion limit"):
        project._github_checkout("https://github.com/fixture-owner/fixture", destination)
    assert not destination.exists()


def test_public_repository_download_remains_bounded(tmp_path, monkeypatch):
    original_client = httpx.Client
    payload = b"x" * (project.MAX_REPOSITORY_ARCHIVE + 1)

    def respond(request):
        return httpx.Response(200, json={"sha": "a" * 40}) if request.url.host == "api.github.com" else httpx.Response(200, content=payload)

    monkeypatch.setattr(project.httpx, "Client", lambda **options: original_client(
        transport=httpx.MockTransport(respond), **options))
    monkeypatch.setattr(project.zipfile, "ZipFile", lambda *args: pytest.fail("Oversized download reached archive parsing"))
    destination = tmp_path / "checkout"
    with pytest.raises(ValueError, match="response exceeds its byte limit"):
        project._github_checkout("https://github.com/fixture-owner/fixture", destination)
    assert not destination.exists()

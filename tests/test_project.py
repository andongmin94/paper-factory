"""Frozen, sanitized source snapshots; all input bytes are synthetic fixtures."""
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

"""Official authentication stores never enter sanitized research snapshots."""

import pytest

from paper_factory import project


@pytest.mark.parametrize("name", [".codex", "codex-auth"])
def test_authentication_state_is_excluded_from_local_snapshot(tmp_path, name):
    source = tmp_path / "source"
    source.mkdir()
    private = source / name
    private.mkdir()
    (private / "auth.json").write_text('{"token":"synthetic-secret"}')
    (private / "history.sqlite").write_bytes(b'synthetic sensitive runtime state')
    (source / "subject.py").write_text("print('actual source')\n")
    workspace = project.ingest(str(source), tmp_path / "workspace")
    assert [asset.path for asset in workspace.latest("project", project.Project).assets] == ["subject.py"]
    assert not any(path.name == "history.sqlite" for path in (workspace.root / "source").rglob('*'))


def test_authentication_profile_cannot_be_imported_directly(tmp_path):
    private = tmp_path / ".codex"
    private.mkdir()
    with pytest.raises(ValueError, match="authentication directories"):
        project.ingest(str(private), tmp_path / "workspace")

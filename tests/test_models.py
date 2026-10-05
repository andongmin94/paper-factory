"""Portable source record identities and strict controller contracts."""
import pytest
from pydantic import ValidationError

from paper_factory.models import Asset, Project


def test_frozen_project_records_preserve_source_identity_and_reject_extra_fields():
    asset = Asset(path="original.js", sha256="a" * 64, size=17, kind="code")
    project = Project(name="Synthetic fixture", source="https://github.com/fixture-owner/repo", source_commit="b" * 40,
                      snapshot_digest="c" * 64, assets=[asset])
    assert project.source_commit == "b" * 40 and project.assets == [asset]
    assert project.id.startswith("project-") and project.imported_at.endswith("+00:00")
    with pytest.raises(ValidationError):
        Project(name="Fixture", source="source", snapshot_digest="digest", assets=[], untrusted=True)
    with pytest.raises(ValidationError):
        project.state = "PUBLISHED"
    assert project.state == "PROJECT_IMPORTED"


@pytest.mark.parametrize("identity", ["../escape", "/absolute", "CON", "NUL.txt", "COM1", "trailing.", "space name", "a" * 129])
def test_record_identity_rejects_path_escape_and_windows_device_names(identity):
    with pytest.raises(ValidationError, match="safe portable identifier"):
        Project(id=identity, name="Fixture", source="source", snapshot_digest="digest", assets=[])

"""Privacy boundaries of the final-article export helper."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import zipfile

import pytest

from paper_factory.author import AuthorProfile


def exporter():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_research_artifacts.py"
    spec = importlib.util.spec_from_file_location("research_artifacts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_author_uses_private_env_and_preserves_explicit_overrides(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", os.environ.copy())
    for field in AuthorProfile.model_fields:
        monkeypatch.delenv(f"PF_AUTHOR_{field.upper()}", raising=False)
    monkeypatch.delenv("PF_AUTHOR_PROFILE_JSON", raising=False)
    config = tmp_path / ".env"
    config.write_text(
        'PF_AUTHOR_DISPLAY_NAME="Local Researcher"\n'
        'PF_AUTHOR_EMAIL="local@example.org"\n'
        'PF_AUTHOR_AFFILIATION="Example University"\n'
        'PF_AUTHOR_ORCID="0000-0002-1825-0097"\n'
        'PF_AUTHOR_CITY="Example City"\n'
        'PF_AUTHOR_COUNTRY="Example Country"\n', encoding="utf-8")
    overrides = tmp_path / "author.local.json"
    overrides.write_text(json.dumps({"display_name": "Explicit Researcher"}), encoding="utf-8")
    author = exporter().load_export_author(overrides, config)
    assert author["display_name"] == "Explicit Researcher"
    assert author["email"] == "local@example.org"
    assert author["orcid"] == "0000-0002-1825-0097"


def test_reproduction_bundle_excludes_hidden_and_explicit_configuration(tmp_path):
    study = tmp_path / "study"
    study.mkdir()
    (study / "results.csv").write_bytes(b"case,score\n1,42\n")
    (study / ".env").write_text("PF_OJS_API_TOKEN=private-placeholder\n", encoding="utf-8")
    explicit = study / "settings.txt"
    explicit.write_text("PF_OJS_API_TOKEN=another-private-placeholder\n", encoding="utf-8")
    exporter().reproduce_bundle(study, {"repository": {"name": "example/study", "commit": "a" * 40}},
                                 private_files=(explicit,))
    with zipfile.ZipFile(study / "reproducibility.zip") as archive:
        assert archive.read("results.csv") == b"case,score\n1,42\n"
        assert ".env" not in archive.namelist()
        assert "settings.txt" not in archive.namelist()
        for member in archive.namelist():
            assert b"private-placeholder" not in archive.read(member)


def test_exporter_rejects_linked_ancestor_even_when_target_is_inside_study(tmp_path):
    study = tmp_path / "study"
    data = study / "data"
    data.mkdir(parents=True)
    (data / "results.csv").write_bytes(b"case,score\n1,42\n")
    linked = study / "linked"
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(linked), str(data)], capture_output=True)
        assert result.returncode == 0, result.stderr
    else:
        linked.symlink_to(data, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks or junctions"):
        exporter().safe_file(study, "linked/results.csv")

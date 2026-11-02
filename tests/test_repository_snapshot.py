"""Repository capture uses real Git objects and never executes the captured project."""

from datetime import datetime
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
snapshot = importlib.import_module("_repository_snapshot")
URL = "https://github.com/example/research-software"


def git(root, *arguments, input=None):
    return subprocess.run(
        ["git", "-c", "user.name=Repository fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "commit.gpgSign=false", "-c", f"core.hooksPath={root / 'empty-hooks'}",
         "-c", "core.autocrlf=false", *arguments],
        cwd=root, input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init", "--quiet", "--initial-branch=main")
    (root / "README.md").write_bytes("Actual source — 첫 revision.\r\n".encode("utf-8"))
    (root / "src").mkdir()
    (root / "src/analysis.py").write_bytes(b"from pathlib import Path\nPath('PROJECT_EXECUTED').touch()\n")
    (root / "unused.md").write_bytes(b"Unselected source\n")
    git(root, "add", "README.md", "src/analysis.py", "unused.md")
    git(root, "commit", "--quiet", "-m", "Initial fixture")
    initial = git(root, "rev-parse", "HEAD").decode().strip()
    link = git(root, "hash-object", "-w", "--stdin", input=b"README.md").decode().strip()
    git(root, "update-index", "--add", "--cacheinfo", f"120000,{link},readme-link")
    git(root, "update-index", "--add", "--cacheinfo", f"160000,{initial},vendor/submodule")
    git(root, "commit", "--quiet", "-m", "Special tracked entries")
    git(root, "tag", "capture-v1")
    (root / "README.md").write_bytes(b"Later default-branch revision\n")
    git(root, "add", "README.md")
    git(root, "commit", "--quiet", "-m", "Later default branch")
    return root


@pytest.fixture
def local_clone(repository, monkeypatch):
    run = subprocess.run
    calls = []

    def redirected(command, *arguments, **kwargs):
        calls.append((list(command), kwargs))
        if "clone" in command:
            command = list(command)
            # Only replace the remote URL; all capture commands use real Git.
            command[command.index(URL)] = repository.as_uri()
        return run(command, *arguments, **kwargs)

    monkeypatch.setattr(snapshot.subprocess, "run", redirected)
    return calls


def test_capture_retains_selected_original_bytes_and_pinned_provenance(tmp_path, repository, local_clone):
    output = tmp_path / "captured"
    result = snapshot.capture_repository(URL + ".git/", output,
                                         paths=["README.md", "src/analysis.py"], ref="capture-v1")
    report = json.loads((output / "repository.json").read_text(encoding="utf-8"))
    assert report["repository_url"] == URL and report["requested_ref"] == "capture-v1"
    assert report["commit_sha"] == git(repository, "rev-parse", "capture-v1").decode().strip()
    assert report["commit_sha"] != git(repository, "rev-parse", "HEAD").decode().strip()
    assert report["tree_sha"] == git(repository, "rev-parse", "capture-v1^{tree}").decode().strip()
    assert report["git_object_format"] == git(repository, "rev-parse", "--show-object-format").decode().strip()
    assert datetime.fromisoformat(report["commit_timestamp"]).tzinfo is not None
    assert datetime.fromisoformat(report["retrieved_at"]).tzinfo is not None
    assert (report["tracked_entry_count"], report["retained_file_count"], report["unretained_entry_count"]) == (5, 2, 3)
    assert result["commit_sha"] == report["commit_sha"]
    for source in report["sources"]:
        original = git(repository, "show", "capture-v1:" + source["repository_path"])
        assert (output / source["path"]).read_bytes() == original
        assert source["sha256"] == hashlib.sha256(original).hexdigest()
        assert source["bytes"] == len(original)
        assert source["git_blob_sha"] == git(repository, "rev-parse", "capture-v1:" + source["repository_path"]).decode().strip()
        assert source["git_blob_sha"] != source["sha256"]
        assert source["commit_pinned_url"] == URL + "/blob/" + report["commit_sha"] + "/" + source["repository_path"]
    assert not (output / "sources/unused.md").exists()
    assert not (repository / "PROJECT_EXECUTED").exists()
    assert not report["project_code_executed"]
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert {entry["path"] for entry in manifest["files"]} == {"repository.json", "sources/README.md", "sources/src/analysis.py"}
    for entry in manifest["files"]:
        assert entry["sha256"] == hashlib.sha256((output / entry["path"]).read_bytes()).hexdigest()
    clone, options = next((command, options) for command, options in local_clone if "clone" in command)
    assert {"--depth=1", "--no-checkout", "--no-recurse-submodules", "--branch=capture-v1"} <= set(clone)
    assert options["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert options["env"]["GCM_INTERACTIVE"] == "Never"
    assert not any("checkout" in command or "submodule" in command for command, _ in local_clone)


def test_default_ref_captures_the_actual_default_branch(tmp_path, repository, local_clone):
    result = snapshot.capture_repository(URL, tmp_path / "default", paths=["README.md"])
    assert result["requested_ref"] is None
    assert result["commit_sha"] == git(repository, "rev-parse", "HEAD").decode().strip()
    assert (tmp_path / "default/sources/README.md").read_bytes() == b"Later default-branch revision\n"


def test_existing_output_is_preserved_before_git_is_called(tmp_path, monkeypatch):
    output = tmp_path / "existing"
    output.mkdir()
    (output / "keep.txt").write_bytes(b"Original output")
    monkeypatch.setattr(snapshot.subprocess, "run", lambda *a, **k: pytest.fail("Existing output must fail before Git"))
    with pytest.raises(FileExistsError):
        snapshot.capture_repository(URL, output, paths=["README.md"])
    assert list(output.iterdir()) == [output / "keep.txt"]
    assert (output / "keep.txt").read_bytes() == b"Original output"


@pytest.mark.parametrize("path, message", [
    ("missing.py", "missing"),
    ("readme-link", "symlink"),
    ("vendor/submodule/source.py", "submodule"),
])
def test_missing_or_nonregular_selection_leaves_no_output(tmp_path, local_clone, path, message):
    output = tmp_path / "invalid-selection"
    with pytest.raises(ValueError, match=message):
        snapshot.capture_repository(URL, output, paths=[path])
    assert not output.exists()


@pytest.mark.parametrize("url", [
    "http://github.com/example/project",
    "https://token@github.com/example/project",
    "https://github.com.evil.invalid/example/project",
    "ssh://git@github.com/example/project",
    "https://github.com/example/project/tree/main",
    "https://github.com/example/project?token=secret",
])
def test_invalid_repository_urls_fail_before_git(tmp_path, monkeypatch, url):
    monkeypatch.setattr(snapshot.subprocess, "run", lambda *a, **k: pytest.fail("Invalid URL must fail before Git"))
    with pytest.raises(ValueError):
        snapshot.capture_repository(url, tmp_path / "invalid-url", paths=["README.md"])
    assert not (tmp_path / "invalid-url").exists()


@pytest.mark.parametrize("paths", [[], ["../outside"], ["src\\outside"], ["README.md", "readme.md"]])
def test_unsafe_or_ambiguous_selection_fails_before_git(tmp_path, monkeypatch, paths):
    monkeypatch.setattr(snapshot.subprocess, "run", lambda *a, **k: pytest.fail("Invalid selection must fail before Git"))
    with pytest.raises(ValueError):
        snapshot.capture_repository(URL, tmp_path / "invalid-path", paths=paths)
    assert not (tmp_path / "invalid-path").exists()

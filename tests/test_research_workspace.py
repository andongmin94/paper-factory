"""Observable portable-note preservation and exact binding behavior."""

import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
notes = importlib.import_module("research_workspace")


def json_file(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def materials(tmp_path):
    root = tmp_path / "research"
    root.mkdir()
    (root / "article.md").write_text("# A decision\n\nThe unchanged claim survives. [1]\n", encoding="utf-8")
    (root / "source.txt").write_text("first\nclaim survives\nthird\n", encoding="utf-8")
    (root / "unused.txt").write_text("not selected", encoding="utf-8")
    return root


def state(root, tmp_path):
    return json_file(tmp_path / "state.json", {"project": "Example", "question": "What survives?",
                     "decisions": ["Use a static claim"], "next_steps": ["Read retained comparison"],
                     "constraints": ["Do not execute"], "historical_counts": {"calls": 19, "unknown": None},
                     "files": ["article.md", "source.txt"]})


def test_checkpoint_portable_and_verbatim_without_modifying_materials(materials, tmp_path):
    original = {p.name: p.read_bytes() for p in materials.iterdir()}
    output = tmp_path / "snapshot"
    assert notes.checkpoint(materials, state(materials, tmp_path), output)["material_count"] == 2
    assert not (output / "materials/unused.txt").exists()
    moved = tmp_path / "other-pc/snapshot"
    moved.parent.mkdir()
    shutil.move(str(output), moved)
    shutil.move(str(materials), tmp_path / "original-now-unavailable")
    result = notes.resume(moved)
    assert result["verified"]
    assert result["notes"]["historical_counts"] == {"calls": 19, "unknown": None}
    assert result["notes"]["next_steps"] == ["Read retained comparison"]
    before = {p.relative_to(moved): p.read_bytes() for p in moved.rglob("*") if p.is_file()}
    notes.resume(moved)
    assert before == {p.relative_to(moved): p.read_bytes() for p in moved.rglob("*") if p.is_file()}
    assert original == {p.name: p.read_bytes() for p in (tmp_path / "original-now-unavailable").iterdir()}


def test_checkpoint_refuses_existing_or_nested_output(materials, tmp_path):
    payload = state(materials, tmp_path)
    with pytest.raises(ValueError, match="separate trees"):
        notes.checkpoint(materials, payload, materials / "snapshot")
    output = tmp_path / "snapshot"
    output.mkdir()
    (output / "keep.txt").write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        notes.checkpoint(materials, payload, output)
    assert (output / "keep.txt").read_bytes() == b"keep"


@pytest.mark.parametrize("name", ["../outside", "/absolute", "C:/outside", "a\\b", "a/../b", "./source.txt", "a//b"])
def test_unsafe_material_paths_rejected(materials, tmp_path, name):
    payload = state(materials, tmp_path)
    data = json.loads(payload.read_text())
    data["files"] = [name]
    json_file(payload, data)
    with pytest.raises(ValueError):
        notes.checkpoint(materials, payload, tmp_path / "snapshot")


def test_resume_detects_material_corruption(materials, tmp_path):
    output = tmp_path / "snapshot"
    notes.checkpoint(materials, state(materials, tmp_path), output)
    (output / "materials/source.txt").write_text("changed", encoding="utf-8")
    result = notes.resume(output)
    assert not result["verified"]
    assert result["issues"] == [{"path": "materials/source.txt", "status": "changed"}]


def test_resume_reports_unlisted_files_without_rewriting(materials, tmp_path):
    output = tmp_path / "snapshot"
    notes.checkpoint(materials, state(materials, tmp_path), output)
    extra = output / "materials/unlisted.txt"
    extra.write_bytes(b"not part of the supplied research")
    result = notes.resume(output)
    assert not result["verified"]
    assert result["issues"] == [{"path": "materials/unlisted.txt", "status": "unlisted"}]
    assert extra.read_bytes() == b"not part of the supplied research"


def ledger(materials, tmp_path):
    return json_file(tmp_path / "ledger.json", {"manuscript": "article.md", "claims": [
        {"id": "C1", "claim": "Recorded condition survives", "kind": "observed_static",
         "manuscript_quote": "The unchanged claim survives.", "sources": [
             {"path": "source.txt", "start_line": 2, "end_line": 2, "quote": "claim survives",
              "sha256": hashlib.sha256((materials / "source.txt").read_bytes()).hexdigest()}]}]})


def test_evidence_checks_exact_witness_without_claiming_truth(materials, tmp_path):
    before = {p.name: p.read_bytes() for p in materials.iterdir()}
    output = tmp_path / "evidence"
    assert notes.evidence(materials, ledger(materials, tmp_path), output)["bindings_match"]
    report = json.loads((output / "evidence.json").read_text())
    assert "do not establish claim truth" in report["scope"]
    assert before == {p.name: p.read_bytes() for p in materials.iterdir()}
    assert (output / "manifest.json").is_file()
    assert report["manuscript_sha256"] in (output / "evidence.md").read_text(encoding="utf-8")


def test_evidence_rejects_file_replaced_after_reading_its_anchor(materials, tmp_path, monkeypatch):
    """A located old quote must never be bound to replacement manuscript bytes."""
    manuscript = materials / "article.md"
    payload = ledger(materials, tmp_path)
    original_bytes, original_text = Path.read_bytes, Path.read_text

    def swap_bytes(path):
        data = original_bytes(path)
        if path == manuscript:
            manuscript.write_bytes(b"# Replacement without the anchored claim\n")
        return data

    def swap_text(path, *args, **kwargs):
        data = original_text(path, *args, **kwargs)
        if path == manuscript:
            manuscript.write_bytes(b"# Replacement without the anchored claim\n")
        return data

    monkeypatch.setattr(Path, "read_bytes", swap_bytes)
    monkeypatch.setattr(Path, "read_text", swap_text)
    with pytest.raises(ValueError, match="Manuscript changed"):
        notes.evidence(materials, payload, tmp_path / "must-not-approve")
    assert not (tmp_path / "must-not-approve").exists()


@pytest.mark.parametrize("change,issue", [("quote", "source_quote_mismatch"), ("sha256", "source_hash_mismatch"), ("anchor", "manuscript_quote_not_found"), ("missing", "missing_source")])
def test_evidence_retains_mismatches_instead_of_approving(materials, tmp_path, change, issue):
    payload = ledger(materials, tmp_path)
    data = json.loads(payload.read_text())
    item = data["claims"][0]
    if change == "quote":
        item["sources"][0]["quote"] = "invented"
    elif change == "sha256":
        item["sources"][0]["sha256"] = "0" * 64
    elif change == "anchor":
        item["manuscript_quote"] = "never written"
    else:
        item["sources"][0]["path"] = "missing.txt"
    json_file(payload, data)
    output = tmp_path / "evidence"
    assert not notes.evidence(materials, payload, output)["bindings_match"]
    assert issue in json.loads((output / "evidence.json").read_text())["claims"][0]["issues"]


def test_evidence_rejects_unsafe_source_paths(materials, tmp_path):
    payload = ledger(materials, tmp_path)
    data = json.loads(payload.read_text())
    data["claims"][0]["sources"][0]["path"] = "../outside"
    json_file(payload, data)
    with pytest.raises(ValueError):
        notes.evidence(materials, payload, tmp_path / "output")


def test_empty_evidence_ledger_is_not_a_success(materials, tmp_path):
    payload = json_file(tmp_path / "ledger.json", {"manuscript": "article.md", "claims": []})
    with pytest.raises(ValueError, match="nonempty"):
        notes.evidence(materials, payload, tmp_path / "output")


def test_compare_reports_exact_text_and_structure(materials, tmp_path):
    before = materials / "article.md"
    after = tmp_path / "new.md"
    after.write_text("# New decision\n\nThe unchanged claim survives. [2]\n\n| A | B |\n| --- | --- |\n| x | y |\n", encoding="utf-8")
    original = before.read_bytes(), after.read_bytes()
    output = tmp_path / "comparison"
    assert not notes.compare(before, after, output)["identical_bytes"]
    report = json.loads((output / "comparison.json").read_text())
    assert report["before"]["citation_labels"] == ["1"]
    assert report["after"]["citation_labels"] == ["2"]
    assert report["after"]["markdown_table_count"] == 1
    assert "-# A decision" in (output / "changes.diff").read_text()
    assert "+# New decision" in (output / "changes.diff").read_text()
    assert original == (before.read_bytes(), after.read_bytes())


def test_isolated_copy_cli_has_no_checkout_dependency(materials, tmp_path):
    isolated = tmp_path / "skill/scripts"
    isolated.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    for name in ["research_workspace.py", "_publication_files.py"]:
        shutil.copyfile(root / "scripts" / name, isolated / name)
    payload = state(materials, tmp_path)
    output = tmp_path / "snapshot"
    result = subprocess.run([sys.executable, str(isolated / "research_workspace.py"), "checkpoint",
                             "--root", str(materials), "--state", str(payload), "--output-dir", str(output)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["material_count"] == 2


def test_linked_material_is_rejected(materials, tmp_path):
    linked = materials / "linked.txt"
    try:
        linked.symlink_to(materials / "source.txt")
    except OSError:
        pytest.skip("Symlink creation is not available to this Windows account")
    payload = state(materials, tmp_path)
    data = json.loads(payload.read_text())
    data["files"] = ["linked.txt"]
    json_file(payload, data)
    with pytest.raises(ValueError, match="symlinks"):
        notes.checkpoint(materials, payload, tmp_path / "snapshot")


def test_status_distinguishes_stale_review_missing_output_and_changed_bytes(materials, tmp_path):
    manuscript_hash = hashlib.sha256((materials / "article.md").read_bytes()).hexdigest()
    source_hash = hashlib.sha256((materials / "source.txt").read_bytes()).hexdigest()
    (materials / "review.json").write_text('{"score": 8.11}', encoding="utf-8")
    review_hash = hashlib.sha256((materials / "review.json").read_bytes()).hexdigest()
    payload = json_file(tmp_path / "status.json", {
        "project": "Preserved study", "question": "Which revision was reviewed?",
        "current_manuscript": "article.md", "historical_counts": {"calls": 19, "unknown": None},
        "remaining_tasks": ["Ask the author for the selected affiliation"], "artifacts": [
            {"id": "article", "role": "manuscript", "path": "article.md", "sha256": manuscript_hash},
            {"id": "review", "role": "scientific_review", "path": "review.json", "sha256": review_hash, "manuscript_sha256": "0" * 64},
            {"id": "changed", "role": "evidence", "path": "source.txt", "sha256": "0" * 64, "manuscript_sha256": manuscript_hash},
            {"id": "missing", "role": "pdf", "path": "not-created.pdf", "sha256": "0" * 64, "manuscript_sha256": manuscript_hash},
            {"id": "source", "role": "source", "path": "source.txt", "sha256": source_hash}]})
    original = {p.name: p.read_bytes() for p in materials.iterdir()}
    output = tmp_path / "status-output"
    result = notes.status(materials, payload, output)
    assert result["artifact_counts"] == {"current": 1, "stale": 1, "changed": 1, "missing": 1, "unbound": 1}
    report = json.loads((output / "status.json").read_text())
    assert report["historical_counts"] == {"calls": 19, "unknown": None}
    assert report["artifacts"][1]["status"] == "stale"
    assert manuscript_hash in (output / "status.md").read_text()
    assert original == {p.name: p.read_bytes() for p in materials.iterdir()}


def test_status_requires_actual_revision_binding_for_a_current_review(materials, tmp_path):
    manuscript_hash = hashlib.sha256((materials / "article.md").read_bytes()).hexdigest()
    payload = {"project": "Study", "question": "Version?", "current_manuscript": "article.md",
               "historical_counts": {}, "remaining_tasks": [], "artifacts": [
                   {"id": "review", "role": "review", "path": "source.txt",
                    "sha256": hashlib.sha256((materials / "source.txt").read_bytes()).hexdigest(),
                    "manuscript_sha256": manuscript_hash}]}
    result = notes.status(materials, json_file(tmp_path / "status.json", payload), tmp_path / "status-output")
    assert result["artifact_counts"]["current"] == 1
    payload["artifacts"][0]["path"] = "../outside"
    with pytest.raises(ValueError, match="remain below"):
        notes.status(materials, json_file(tmp_path / "unsafe.json", payload), tmp_path / "unsafe-output")

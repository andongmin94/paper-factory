"""Exercise real CLI pipes with synthetic inputs, not a repository/publisher E2E."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "submission_support.py"


@pytest.mark.parametrize("title", ["한국어 초안", "Café — draft"])
def test_bundle_cli_json_survives_cp1252_without_changing_files(tmp_path, title):
    root = tmp_path / "source"
    root.mkdir()
    manuscript = root / "paper.md"
    original = ("# " + title + "\r\n\r\nSynthetic test input only.\r\n").encode("utf-8")
    manuscript.write_bytes(original)
    missing = "No measurement retained: " + title
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({
        "venue_id": "ieee-software", "title": title,
        "article_type": "Feature Article", "draft_status": "draft",
        "guidance_status": "partial", "missing_evidence": [missing],
        "files": [{"role": "manuscript", "path": "paper.md"}],
    }, ensure_ascii=False), encoding="utf-8")
    original_plan = plan.read_bytes()
    output = tmp_path / "bundle"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "bundle", "--plan", str(plan),
         "--root", str(root), "--output-dir", str(output)],
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b""
    report = json.loads(result.stdout.decode("utf-8"))
    retained = (output / "report.json").read_bytes()
    assert title.encode("utf-8") in retained
    assert report["title"] == title
    assert {key: value for key, value in report.items() if key != "output_dir"} == json.loads(retained)
    assert report["draft_status"] == "incomplete" and report["recommendation_status"] == "conditional"
    assert missing in report["missing_evidence"]
    assert not report["submission_ready"] and not report["author_approval_inferred"]
    assert all(row["status"] == "pending" for row in report["declaration_status"].values())
    assert (output / "files/paper.md").read_bytes() == manuscript.read_bytes() == original
    assert plan.read_bytes() == original_plan
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for row in manifest["files"]:
        data = (output / row["path"]).read_bytes()
        assert len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"]


def test_bundle_cli_error_is_utf8_json_on_cp1252_pipe(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    missing_plan = tmp_path / "café-missing.json"
    output = tmp_path / "not-created"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "bundle", "--plan", str(missing_plan),
         "--root", str(root), "--output-dir", str(output)],
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        capture_output=True, timeout=30,
    )
    assert result.returncode == 2
    assert result.stdout == b""
    error = json.loads(result.stderr.decode("utf-8"))
    assert missing_plan.name in error["error"]
    assert not output.exists()

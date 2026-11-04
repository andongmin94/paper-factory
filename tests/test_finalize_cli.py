"""Real CLI pipes with synthetic incomplete records, not Word or repository E2E."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "finalize_submission.py"


@pytest.mark.parametrize("name", ["한국어 초안", "Café — draft"])
def test_finalize_cli_pending_json_survives_cp1252_and_preserves_inputs(tmp_path, name):
    root = tmp_path / name
    root.mkdir()
    manuscript = root / "paper.md"
    manuscript.write_bytes(("# " + name + "\r\nSynthetic test input only.\r\n").encode("utf-8"))
    bundle = root / "bundle.json"
    bundle.write_text(json.dumps({
        "draft_status": "incomplete", "missing_evidence": ["No measurement retained: " + name],
    }, ensure_ascii=False), encoding="utf-8")
    record = root / "record.json"
    record.write_text(json.dumps({
        "venue_id": "jors", "manuscript": "paper.md", "docx": None, "pdf": None,
        "format_report": None, "visual_review": None, "bundle_report": "bundle.json",
        "scientific_review": None, "pages": ["not-rendered.png"], "confirmations": {},
    }), encoding="utf-8")
    original = {path: path.read_bytes() for path in (manuscript, bundle, record)}
    output = tmp_path / (name + "-checked")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "check", "--root", str(root),
         "--record", str(record), "--output-dir", str(output)],
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        capture_output=True, timeout=30,
    )
    assert result.returncode == 1, result.stderr  # Pending is not an encoding failure or approval.
    assert result.stderr == b""
    report = json.loads(result.stdout.decode("utf-8"))
    retained = (output / "final-preparation.json").read_bytes()
    assert name.encode("utf-8") in retained
    assert report["output_dir"] == str(output.resolve())
    assert {key: value for key, value in report.items() if key != "output_dir"} == json.loads(retained)
    assert not report["submission_ready"] and not report["author_approval_inferred"]
    assert not report["actual_submission_performed"] and not report["word_or_research_executed"]
    assert not report["native_format_passed"] and not report["page_inspection_recorded"]
    assert {"draft_completion", "author_declarations", "native_format", "page_inspection"} <= set(report["pending"])
    assert all(row["status"] == "pending" for row in report["declaration_status"].values())
    assert original == {path: path.read_bytes() for path in original}
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert {row["path"] for row in manifest["files"]} == {"final-preparation.json", "final-preparation.md"}
    for row in manifest["files"]:
        data = (output / row["path"]).read_bytes()
        assert len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"]


def test_finalize_cli_error_is_utf8_json_on_cp1252_pipe(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    record = root / "café-missing.json"
    output = tmp_path / "not-created"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "check", "--root", str(root),
         "--record", str(record), "--output-dir", str(output)],
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        capture_output=True, timeout=30,
    )
    assert result.returncode == 2
    assert result.stdout == b""
    error = json.loads(result.stderr.decode("utf-8"))
    assert record.name in error["error"]
    assert not output.exists()

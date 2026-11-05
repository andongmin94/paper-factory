"""Exercise bundle handoff of saved evidence reports, not repository/Word E2E."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "submission_support.py"


def prepare_case(tmp_path, variant):
    root = tmp_path / "source"
    root.mkdir()
    manuscript = b"# Synthetic manuscript\r\nA retained claim.\r\n"
    report = {
        "manuscript": "paper.md", "manuscript_sha256": hashlib.sha256(manuscript).hexdigest(),
        "bindings_match": True,
        "claims": [{"id": "C1", "kind": "observed_static", "claim": "A retained claim.",
                    "manuscript_quote": "A retained claim.", "bindings_match": True, "issues": [],
                    "sources": [{"path": "source.py", "start_line": 1, "end_line": 1,
                                 "quote": "A retained claim.", "issues": []}]}],
    }
    if variant == "failed":
        report["bindings_match"] = False
        report["claims"][0].update(bindings_match=False, issues=["missing_source"])
    elif variant == "stale":
        report["manuscript_sha256"] = "0" * 64
    elif variant == "contradictory":
        report["claims"][0].update(bindings_match=False, issues=["source_quote_mismatch"])
    elif variant == "empty":
        report["claims"] = []
    elif variant == "not_report":
        report = {"note": "Only an authored note, not an evidence report"}
    contents = {
        "paper.md": manuscript,
        "paper.bib": b"% Synthetic fixture, not a verified citation\n",
        "selection.md": b"Synthetic selection only\n",
        "guidance.md": b"Synthetic guidance record only\n",
        "evidence.json": json.dumps(report, ensure_ascii=False).encode("utf-8"),
    }
    if variant == "malformed":
        contents["evidence.json"] = b'{"claims":'
    for name, data in contents.items():
        (root / name).write_bytes(data)
    plan = {
        "venue_id": "ieee-software", "title": "Synthetic draft",
        "article_type": "Feature Article", "draft_status": "draft", "guidance_status": "verified",
        "missing_evidence": [],
        "files": [{"role": role, "path": path} for role, path in [
            ("manuscript", "paper.md"), ("bibliography", "paper.bib"),
            ("venue_selection", "selection.md"), ("guidance", "guidance.md"), ("evidence", "evidence.json")]],
    }
    return root, contents, plan


def run_bundle(tmp_path, root, contents, plan):
    plan_path = tmp_path / "plan.json"
    plan_bytes = json.dumps(plan).encode("utf-8")
    plan_path.write_bytes(plan_bytes)
    output = tmp_path / "bundle"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "bundle", "--root", str(root),
         "--plan", str(plan_path), "--output-dir", str(output)],
        capture_output=True, timeout=30, env={**os.environ, "PYTHONIOENCODING": "cp1252"},
    )
    assert result.returncode == 0, result.stderr
    assert not result.stderr
    report = json.loads(result.stdout.decode("utf-8"))
    saved = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert {k: v for k, v in report.items() if k != "output_dir"} == saved
    assert not report["submission_ready"] and not report["author_approval_inferred"]
    assert not report["actual_submission_performed"]
    assert all(row["status"] == "pending" for row in report["declaration_status"].values())
    assert plan_path.read_bytes() == plan_bytes
    for name, data in contents.items():
        assert (root / name).read_bytes() == (output / "files" / name).read_bytes() == data
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert {row["path"] for row in manifest["files"]} == {
        p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file() and p.name != "manifest.json"}
    for row in manifest["files"]:
        data = (output / row["path"]).read_bytes()
        assert len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"]
    checklist = (output / "checklist.md").read_text(encoding="utf-8")
    assert all(gap in checklist for gap in report["missing_evidence"])
    return report


@pytest.mark.parametrize("variant,reason", [
    ("failed", "C1"), ("stale", "manuscript"), ("contradictory", "C1"),
    ("empty", "claim results"), ("not_report", "claim results"), ("malformed", "JSON"),
])
def test_evidence_gaps_reach_bundle_and_checklist(tmp_path, variant, reason):
    root, contents, plan = prepare_case(tmp_path, variant)
    result = run_bundle(tmp_path, root, contents, plan)
    assert result["draft_status"] == "incomplete"
    assert result["recommendation_status"] == "conditional"
    assert any("evidence.json" in gap and reason in gap for gap in result["missing_evidence"])


def test_current_matching_report_preserves_draft_not_approval(tmp_path):
    root, contents, plan = prepare_case(tmp_path, "matching")
    result = run_bundle(tmp_path, root, contents, plan)
    assert result["draft_status"] == "draft" and result["missing_evidence"] == []
    assert result["recommendation_status"] == "conditional"


def test_current_report_never_clears_supplied_research_gaps(tmp_path):
    root, contents, plan = prepare_case(tmp_path, "matching")
    plan["missing_evidence"] = ["No controlled experiment exists"]
    result = run_bundle(tmp_path, root, contents, plan)
    assert result["draft_status"] == "incomplete"
    assert result["missing_evidence"] == plan["missing_evidence"]


def test_evidence_failure_survives_omitted_draft_status(tmp_path):
    root, contents, plan = prepare_case(tmp_path, "failed")
    del plan["draft_status"]
    result = run_bundle(tmp_path, root, contents, plan)
    assert result["recommendation_status"] == "conditional"
    assert any("C1" in gap for gap in result["missing_evidence"])

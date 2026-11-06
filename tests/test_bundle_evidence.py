"""Saved-evidence handoff tests; CLI pipe coverage lives in test_submission_cli."""

import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from research_workspace import evidence
from submission_support import prepare_bundle, record_conversion


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
    report = prepare_bundle(plan_path, root, output)
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


@pytest.mark.parametrize("changed", [None, "observation.txt", "claims.json", "copied-ledger.json"])
def test_bundle_matches_selected_sources_and_ledgers_to_their_actual_reports(tmp_path, changed):
    root, _, plan = prepare_case(tmp_path, "matching")
    files = plan["files"]
    files.remove({"role": "evidence", "path": "evidence.json"})
    for idx, (ledger, witness) in enumerate(((root / "claims.json", "observation.txt"),
                                             (tmp_path / "external.json", "unselected.txt")), 1):
        (root / witness).write_text("original observation\na second observation\n")
        value = {"manuscript": "paper.md", "claims": [
            {"id": f"C{idx}", "claim": "A retained claim.", "manuscript_quote": "A retained claim.",
             "kind": "source_declared", "sources": [{"path": witness, "start_line": line, "end_line": line,
                                                     "quote": quote} for line, quote in
                                                    [(1, "original observation"), (2, "a second observation")]]}]}
        ledger.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8-sig")
        out = root / f"evidence-{idx}"
        assert evidence(root, ledger, out)["bindings_match"]
        saved = json.loads((out / "evidence.json").read_text())
        assert saved["ledger_sha256"] == hashlib.sha256(ledger.read_bytes()).hexdigest()
        assert saved["ledger_path"] == (ledger.name if ledger.parent == root else None)
        files.append({"role": "evidence", "path": f"{out.name}/evidence.json"})

    # The second ledger was outside the root; only its renamed, explicitly selected copy travels.
    (root / "copied-ledger.json").write_bytes((tmp_path / "external.json").read_bytes())
    (tmp_path / "external.json").unlink()
    (root / "unselected.txt").unlink()
    files.extend([{"role": "case_record", "path": "claims.json"},
                  {"role": "claim_ledger", "path": "copied-ledger.json"},
                  {"role": "observation", "path": "observation.txt"}])
    if changed:
        path = root / changed
        if changed == "observation.txt":
            path.write_text("different outcome\n")
        else:
            ledger = json.loads(path.read_text(encoding="utf-8-sig"))
            ledger["claims"][0]["claim"] = "A different assertion."
            path.write_text(json.dumps(ledger))
    result = run_bundle(tmp_path, root, {f["path"]: (root / f["path"]).read_bytes() for f in files}, plan)
    if changed:
        assert result["draft_status"] == "incomplete"
        assert len(result["missing_evidence"]) == 1 and changed in result["missing_evidence"][0]
    else:
        assert result["draft_status"] == "draft" and not result["missing_evidence"]


def test_evidence_refuses_a_ledger_replaced_during_inspection(tmp_path, monkeypatch):
    root, _, _ = prepare_case(tmp_path, "matching")
    ledger = root / "ledger.json"
    recorded = json.loads((root / "evidence.json").read_text())
    ledger.write_text(json.dumps({"manuscript": "paper.md", "claims": recorded["claims"]}))
    (root / "source.py").write_text("A retained claim.\n")
    read_bytes = Path.read_bytes

    def change_ledger(path):
        if path == root / "paper.md":
            ledger.write_text("{}")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", change_ledger)
    with pytest.raises(ValueError, match="Claim ledger changed"):
        evidence(root, ledger, tmp_path / "report")
    assert not (tmp_path / "report").exists()


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


def conversion_case(tmp_path, venue):
    root, contents, plan = prepare_case(tmp_path, "matching")
    output = "paper.docx" if venue == "emse" else "paper.pdf"
    role = "editable_docx" if venue == "emse" else "review_pdf"
    inputs = ["paper.md", "paper.bib", "figure.svg"]
    contents["figure.svg"] = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
    plan["files"].append({"role": "figure", "path": "figure.svg"})
    if venue == "jmlr-mloss":
        inputs.append("paper.tex")
        contents["paper.tex"] = b"% Synthetic authored TeX\n"
        plan["files"].append({"role": "latex_source", "path": "paper.tex"})
    contents[output] = b"Synthetic output bytes; no document conversion or layout validation is performed."
    for name, data in contents.items():
        (root / name).write_bytes(data)
    plan.update(venue_id=venue, recommendation_status="not_recommended")
    plan["files"].extend([{"role": role, "path": output},
                          {"role": "conversion_record", "path": "conversion/conversion.json"}])
    record_conversion(root, inputs, output, root / "conversion")
    return root, plan, output


@pytest.mark.parametrize("venue,changed", [
    ("emse", None), ("emse", "paper.md"), ("emse", "paper.docx"),
    ("jmlr-mloss", None), ("jmlr-mloss", "paper.md"), ("jmlr-mloss", "paper.tex"),
    ("jmlr-mloss", "paper.bib"), ("jmlr-mloss", "figure.svg"), ("jmlr-mloss", "paper.pdf"),
])
def test_prepared_outputs_match_recorded_versions_after_moving_the_source_tree(tmp_path, venue, changed):
    root, plan, output = conversion_case(tmp_path, venue)
    root = root.rename(tmp_path / "moved")
    record = json.loads((root / "conversion/conversion.json").read_text())
    assert record["conversion_executed_by_tool"] is False
    if changed:
        (root / changed).write_bytes((root / changed).read_bytes() + b"\nChanged since conversion.\n")
    result = run_bundle(tmp_path, root, {f["path"]: (root / f["path"]).read_bytes() for f in plan["files"]}, plan)
    assert result["recommendation_status"] == "not_recommended"
    if changed:
        assert result["draft_status"] == "incomplete"
        assert any(changed + " changed; regenerate " + output in gap for gap in result["missing_evidence"])
    else:
        assert result["draft_status"] == "draft" and not result["missing_evidence"]


@pytest.mark.parametrize("variant,reason", [
    ("absent", "exactly one conversion_record"),
    ("malformed", "invalid record"),
    ("unbound", "paper.bib is not bound"),
    ("unselected", "figure.svg is not selected"),
    ("duplicate", "exactly one conversion_record"),
])
def test_incomplete_conversion_records_are_gaps_not_approval(tmp_path, variant, reason):
    root, plan, _ = conversion_case(tmp_path, "jmlr-mloss")
    receipt = root / "conversion/conversion.json"
    if variant == "absent":
        plan["files"] = [f for f in plan["files"] if f["role"] != "conversion_record"]
    elif variant == "malformed":
        receipt.write_text('{"inputs":')
    elif variant == "unbound":
        record = json.loads(receipt.read_text())
        record["inputs"] = [item for item in record["inputs"] if item["path"] != "paper.bib"]
        receipt.write_text(json.dumps(record))
    elif variant == "unselected":
        plan["files"] = [f for f in plan["files"] if f["path"] != "figure.svg"]
        (root / "figure.svg").unlink()  # The bundle must not read unselected receipt paths.
    else:
        (root / "duplicate.json").write_bytes(receipt.read_bytes())
        plan["files"].append({"role": "conversion_record", "path": "duplicate.json"})
    result = run_bundle(tmp_path, root, {f["path"]: (root / f["path"]).read_bytes() for f in plan["files"]}, plan)
    assert result["draft_status"] == "incomplete"
    assert result["recommendation_status"] == "not_recommended"
    assert any(reason in gap for gap in result["missing_evidence"])

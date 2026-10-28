"""Reading cards retain supplied scope and reject false byte or quote bindings."""

import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
cards = importlib.import_module("literature_cards")


@pytest.fixture
def reading(tmp_path):
    root = tmp_path / "reading"
    root.mkdir()
    (root / "paper.txt").write_bytes(b"Question\nThe method compares retained cases.\nOnly these cases were inspected.\n")
    sha = hashlib.sha256((root / "paper.txt").read_bytes()).hexdigest()
    card = {"id": "P1", "title": "A retained reading", "url": "https://example.org/paper",
            "reading_scope": "selected_sections", "read_sections": ["Method"], "unread_sections": ["Appendix"],
            "question": "What does the method compare?", "method": "Comparison of retained cases.",
            "results": "Case comparison, as described in the retained text.",
            "limitations": "Only a selected section was read.", "relevance": "Compare the same cases in the article.",
            "source": {"path": "paper.txt", "sha256": sha, "text_path": "paper.txt", "text_sha256": sha},
            "witnesses": [{"start_line": 2, "end_line": 2, "quote": "The method compares retained cases.", "pages": "2"}]}
    payload = tmp_path / "cards.json"
    payload.write_text(json.dumps({"cards": [card]}), encoding="utf-8")
    return root, payload, card


def test_card_is_portable_and_does_not_inflate_selected_reading(reading, tmp_path):
    root, payload, card = reading
    original = (root / "paper.txt").read_bytes()
    output = tmp_path / "cards-output"
    result = cards.prepare(root, payload, output)
    assert result["bindings_match"]
    report = json.loads((output / "literature-cards.json").read_text())
    recorded = report["cards"][0]
    assert recorded["reading_scope"] == "selected_sections"
    assert recorded["unread_sections"] == ["Appendix"]
    assert recorded["body_reading_reported"]
    assert "not independently checked" in recorded["witnesses"][0]["page_locator_scope"]
    assert "do not prove full reading" in report["scope"]
    assert card["source"]["sha256"] in (output / "literature-cards.md").read_text(encoding="utf-8")
    assert (root / "paper.txt").read_bytes() == original


@pytest.mark.parametrize("change,issue", [("bytes", "source_hash_mismatch"), ("quote", "source_quote_mismatch"), ("missing", "missing_source"), ("empty", "no_body_witnesses")])
def test_cards_report_missing_or_mismatched_evidence(reading, tmp_path, change, issue):
    root, payload, card = reading
    if change == "bytes":
        (root / "paper.txt").write_bytes(b"Replacement\nThe method compares retained cases.\n")
    elif change == "quote":
        card["witnesses"][0]["quote"] = "An invented result"
    elif change == "missing":
        card["source"]["path"] = "missing.pdf"
    else:
        card["witnesses"] = []
    payload.write_text(json.dumps({"cards": [card]}), encoding="utf-8")
    output = tmp_path / "cards-output"
    assert not cards.prepare(root, payload, output)["bindings_match"]
    assert issue in json.loads((output / "literature-cards.json").read_text())["cards"][0]["issues"]


def test_abstract_only_record_never_counts_as_reported_body_reading(reading, tmp_path):
    root, payload, card = reading
    card.update(reading_scope="abstract_only", read_sections=["Abstract"], unread_sections=["Body"], witnesses=[])
    payload.write_text(json.dumps({"cards": [card]}), encoding="utf-8")
    output = tmp_path / "cards-output"
    assert cards.prepare(root, payload, output)["bindings_match"]
    assert not json.loads((output / "literature-cards.json").read_text())["cards"][0]["body_reading_reported"]


def test_full_body_claim_cannot_hide_explicit_unread_sections(reading, tmp_path):
    root, payload, card = reading
    card["reading_scope"] = "full_body"
    payload.write_text(json.dumps({"cards": [card]}), encoding="utf-8")
    with pytest.raises(ValueError, match="unread"):
        cards.prepare(root, payload, tmp_path / "cards-output")


def test_reading_card_rejects_escaping_source_path(reading, tmp_path):
    root, payload, card = reading
    card["source"]["path"] = "../outside.txt"
    payload.write_text(json.dumps({"cards": [card]}), encoding="utf-8")
    with pytest.raises(ValueError):
        cards.prepare(root, payload, tmp_path / "cards-output")


def test_card_cli_runs_from_copied_skill_without_repository_import(reading, tmp_path):
    root, payload, card = reading
    isolated = tmp_path / "skill/scripts"
    isolated.mkdir(parents=True)
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    for name in ("literature_cards.py", "research_workspace.py", "_publication_files.py"):
        shutil.copyfile(scripts / name, isolated / name)
    result = subprocess.run([sys.executable, str(isolated / "literature_cards.py"), "prepare", "--root", str(root),
                             "--cards", str(payload), "--output-dir", str(tmp_path / "cli-output")],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["card_count"] == 1

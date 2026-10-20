"""One explicit four-call analytical round; all model/PDF fixtures are synthetic."""

import copy
import hashlib
import json

import pytest

from paper_factory.autonomous.manuscript_improvement import (
    PRIMARY_PRIOR_CANDIDATES, FiniteAnalyticalModel, FocusedAnalyticalResults,
    check_finite_model, canonical_focused_analysis, canonical_focused_revision, canonical_quality_revision)
from paper_factory.workflow import _freeze
from test_repository_paper_workflow import study
from test_repository_portfolio import unwritten_portfolio
from test_manuscript_improvement import continuation, current, reserve, retain, assessment, revision


def synthetic_conversion(source, output, *, venue_id):
    output.write_bytes(b"Explicit synthetic conversion fixture, not an actual manuscript file.")
    return {"input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "engine": "synthetic-fixture"}


def close_original(service, rid, monkeypatch):
    for _ in range(2):
        task = reserve(service, rid)
        retain(service, rid, task, assessment(task, 6))
    task = reserve(service, rid)
    retain(service, rid, task, outcome="failed")
    monkeypatch.setattr("paper_factory.conversion.convert", synthetic_conversion)
    return service.finish_manuscript_improvement(rid)


def selection_value():
    return {"sources": [{"url": card["url"], "comparison_question": "What explicit decision does the original permission method support?",
        "expected_method_difference": "Compare operation intent and lifetime without claiming a new security primitive."}
        for card in PRIMARY_PRIOR_CANDIDATES[:2]], "inspect_source_files": ["tool.js", "README.md"],
        "analytical_questions": ["Which exact effect requires an explicitly scoped authorization?",
                                 "Which lifetime change invalidates an earlier authorization?"]}


def synthetic_primary_collection(service, ws, record, selection):
    cards = []
    for number, choice in enumerate(selection.sources, 1):
        text = ("Explicit synthetic primary-body fixture. Authorization must bind the operation intent and its eventual effect. " * 70)
        path = ws.path(f"research/focused-synthetic-source-{number}.txt")
        path.write_text(text, encoding="utf-8")
        key = f"focused-synthetic-source-{number}"
        _freeze(ws, record, key, path)
        raw = ws.path(f"research/focused-synthetic-source-{number}.pdf")
        raw.write_bytes(b"%PDF-1.7\nExplicitly synthetic PDF bytes; never actual scientific evidence.\n%%EOF")
        _freeze(ws, record, key + "-raw", raw)
        cards.append({"id": "focused-document-" + str(number), "title": "Synthetic closest prior method",
            "url": choice.url, "authors": ["Synthetic Fixture"], "year": 2026, "purpose": "comparison",
            "status": "retained", "source_role": "primary_full_text", "complete_body": True,
            "text_artifact_id": key, "text_sha256": record.artifacts[key].sha256,
            "raw_artifact_id": key + "-raw", "raw_sha256": record.artifacts[key + "-raw"].sha256,
            "pdf_pages": 2, "fetched_at": "2026-10-18T00:00:00+00:00"})
    return {"sources": cards, "retained_full_bodies": 2, "retained_characters": 17000, "collection_count": 1}


def finite_model(proposed=False):
    invariant = {"id": "effect_requires_intent", "description": "Every committed effect requires an explicit authorizing intent.",
        "if_all": [{"variable": "committed", "equals": True}],
        "then_all": [{"variable": "authorized", "equals": True}]}
    states = [{"id": "start", "description": "No operation is authorized or committed at the abstract start.",
               "values": {"authorized": False, "committed": False}}]
    transitions = []
    if proposed:
        states.append({"id": "approved", "description": "An explicit hypothetical operation approval has been bound.",
            "values": {"authorized": True, "committed": False}})
        transitions.append({"id": "approve", "from_state": "start", "to_state": "approved",
            "event": "A hypothetical user explicitly approves this bounded operation.", "guard": [],
            "effects": {"authorized": True}, "evidence_ids": ["configuration"],
            "abstraction_assumption": "This is a proposed abstract authorization step, never an implemented fixture feature."})
    states.append({"id": "done", "description": "The modeled effect has reached its abstract committed state.",
        "values": {"authorized": proposed, "committed": True}})
    transitions.append({"id": "commit", "from_state": "approved" if proposed else "start", "to_state": "done",
        "event": "The hypothetical fixture operation commits its abstract effect.", "guard": [],
        "effects": {"committed": True}, "evidence_ids": ["configuration"],
        "abstraction_assumption": "A synthetic finite abstraction supports no assertion about actual Frontron execution."})
    return {"initial_state": "start", "states": states, "transitions": transitions, "invariants": [invariant],
            "scope": "Synthetic bounded Boolean model for controller tests, not measured security or project execution."}


def analytical_value(service, rid):
    status = current(service.status(rid))
    version = next(iter(status["versions"].values()))[-1]
    evidence = json.loads(service.artifact_path(rid, version["draft_artifact_id"]).read_text(encoding="utf-8"))["value"]["source_evidence"]
    quote = "Authorization must bind the operation intent and its eventual effect."
    comparisons = [{"source_id": "focused-document-" + str(number), "quote": quote,
        "baseline_method": "The synthetic baseline explicitly separates a caller from an authorized effect.",
        "applicable_lesson": "Model an authorization decision before committing a synthetic effect.",
        "additional_decision_value": "The completed abstract trace identifies the exact missing decision point.",
        "transfer_limit": "This synthetic fixture establishes no deployment or real implementation effectiveness."}
        for number in (1, 2)]
    return {"method_scope": "source_bound_finite_models_not_project_execution", "source_evidence": evidence,
        "worksheets": [{"case_id": case, "concrete_scenario": "A synthetic operation reaches an abstract effect after an explicit decision.",
            "retained_implementation_boundary": "Only the frozen configuration source is actually inspected in this fixture.",
            "baseline_model": finite_model(), "proposed_model": finite_model(True),
            "prior_comparisons": comparisons,
            "completed_decisions": ["Completed the exact synthetic baseline trace and identified its abstract guard.",
                                    "Completed the hypothetical bounded authorization trace and stated its assumptions."],
            "residual_risks": ["The finite abstraction is author supplied and supports no real execution or efficacy claim."],
            "proposed_change_not_implemented": True} for case in ("paste", "autosave")],
        "cross_case_findings": ["Both completed synthetic cases expose an explicit operation-to-intent decision boundary."],
        "limitations": ["Synthetic finite-model results are not empirical Frontron experiments or security guarantees."]}


def test_finite_checker_returns_actual_counterexample_and_scoped_proposed_result():
    baseline = check_finite_model(FiniteAnalyticalModel.model_validate(finite_model()), {"configuration"})
    proposed = check_finite_model(FiniteAnalyticalModel.model_validate(finite_model(True)), {"configuration"})
    assert baseline["violations"] == [{"invariant_id": "effect_requires_intent", "state_id": "done", "transition_trace": ["commit"]}]
    assert proposed["violations"] == [] and proposed["invariant_checks"] == 3
    assert not baseline["project_execution"] and not baseline["empirical_experiment"]
    broken = finite_model()
    broken["transitions"][0]["effects"] = {"committed": False}
    with pytest.raises(ValueError, match="target contradicts"):
        check_finite_model(FiniteAnalyticalModel.model_validate(broken), {"configuration"})


def test_every_page_png_is_frozen_and_must_match_its_rendering_receipt(continuation):
    service, rid, _, _ = continuation
    with service._operation(rid) as (ws, record):
        root = ws.path("research/synthetic-page-qa")
        root.mkdir()
        path = root / "page-001.png"
        content = b"Explicit synthetic page-image bytes for artifact binding tests only."
        path.write_bytes(content)
        report = {"page_qa": {"pages": [{"number": 1, "image_path": str(path),
            "image_sha256": hashlib.sha256(content).hexdigest()}]}}
        service._improvement_freeze_page_images(ws, record, report, root, "synthetic-native-qa")
        service._save(ws, record)
        assert report["page_qa"]["pages"][0]["image_artifact_id"] == "synthetic-native-qa-page-1"
        assert record.artifacts["synthetic-native-qa-page-1"].sha256 == hashlib.sha256(content).hexdigest()
        mismatched = {"page_qa": {"pages": [{"number": 1, "image_path": str(path), "image_sha256": "0" * 64}]}}
        with pytest.raises(ValueError, match="image bytes differ"):
            service._improvement_freeze_page_images(ws, record, mismatched, root, "synthetic-other-qa")


def test_focused_round_four_calls_complete_results_both_articles_blind_reviews_and_preserve_history(continuation, monkeypatch):
    service, rid, _, _ = continuation
    before = close_original(service, rid, monkeypatch)
    base_count = current(before)["counts"]["model_attempts"]
    granted = service.grant_focused_manuscript_round(rid)
    grant_snapshot = granted["manuscript_improvement_snapshot"]
    assert current(granted)["policy"]["model_call_limit"] == base_count + 4
    assert service.grant_focused_manuscript_round(rid)["manuscript_improvement_snapshot"] == grant_snapshot
    monkeypatch.setattr(service, "_improvement_collect_primary_bodies", lambda ws, record, selection:
        synthetic_primary_collection(service, ws, record, selection))
    monkeypatch.setattr(service, "_improvement_focused_preflight", lambda ws, record, state, venue, markdown:
        (markdown, {"artifact_id": "synthetic-preflight-" + venue, "sha256": "a" * 64,
                    "content_format_passed": True, "report": {"scope": "Synthetic fixture, not an actual Word compliance result."}}))
    task = reserve(service, rid)
    assert task["purpose"] == "focused-select"
    retain(service, rid, task, selection_value())
    task = reserve(service, rid)
    assert task["purpose"] == "focused-analyze"
    retain(service, rid, task, analytical_value(service, rid))
    state = current(service.status(rid))
    checker = json.loads(service.artifact_path(rid, state["focused_round"]["checker_artifact_id"]).read_text(encoding="utf-8"))
    assert not checker["project_execution"] and len(checker["cases"]) == 2
    task = reserve(service, rid)
    assert task["purpose"] == "focused-write"
    materials = json.loads(task["prompt"][task["prompt"].index('{"research_id":'):])["materials"]
    assert "prior_assessments" not in materials and "improvement_plan" not in materials and "source_analysis" not in materials
    assert materials["preserved_source_analysis"]["sha256"] and materials["remaining_article_defects"]
    assert len(materials["completed_analytical_results"]["value"]["worksheets"]) == 2
    articles = []
    cards = current(service.status(rid))["focused_round"]["primary_collection"]["sources"]
    for venue in ("ieee-software", "ieee-security-privacy"):
        item = revision(service, rid, {**task, "venue_id": venue, "action_id": "focused-write-" + venue})
        for card in cards:
            item["manuscript"]["document_evidence"].append({"source_id": card["id"], "text_sha256": card["text_sha256"],
                "quote": "Authorization must bind the operation intent and its eventual effect.",
                "interpretation": "This is an explicitly synthetic method quotation used only for native controller verification."})
            item["manuscript"]["sections"][1]["text"] += " {{document:" + card["id"] + "}}"
        articles.append(item)
    retain(service, rid, task, {"revisions": articles})
    task = reserve(service, rid)
    assert task["purpose"] == "focused-review"
    assert "prior_assessments" not in task["prompt"] and '"improvement_plan"' not in task["prompt"]
    assert "Evidence field names describe native storage kinds, not scholarly status" in task["prompt"]
    assert "An empty literature_evidence list alone is not a missing scholarly binding" in task["prompt"]
    assert "controller-generated numbered References section" in task["prompt"]
    assert "Do not write a Reference or References section" not in task["prompt"]
    assert "matching literature_evidence" not in task["prompt"]
    material = json.loads(task["prompt"][task["prompt"].index('{"research_id":'):])["materials"]
    scholarly = {card["id"] for card in material["documents"] if card.get("source_role") == "primary_full_text" and card.get("complete_body")}
    assert len(scholarly) >= 2
    for article in material["manuscripts"].values():
        assert article["evidence"]["literature_evidence"] == []
        assert scholarly.issubset({item["source_id"] for item in article["evidence"]["document_evidence"]})
    targets = current(service.status(rid))["focused_round"]["write_versions"]
    retain(service, rid, task, {"assessments": [assessment({**task, "venue_id": venue,
        "manuscript_sha256": version["markdown_sha256"]}, 8) for venue, version in targets.items()]})
    finished = service.finish_manuscript_improvement(rid)
    final = current(finished)
    assert final["finished"] and final["focused_round"]["closed"]
    assert len([call for call in final["calls"] if call.get("round_id")]) == 4
    assert final["counts"]["model_attempts"] == base_count + 4
    assert len(final["focused_round"]["completed_stages"]) == 4 and final["next_task"] is None
    assert finished["execution_attempt"] == before["execution_attempt"] == 0
    for key, value in before["artifacts"].items():
        assert finished["artifacts"][key] == value
    assert service.grant_focused_manuscript_round(rid)["manuscript_improvement_snapshot"] == finished["manuscript_improvement_snapshot"]


def misclassified_analytical_fixture(service, rid):
    value = analytical_value(service, rid)
    original = value["source_evidence"][0]
    value["source_evidence"].extend([{**original, "id": "configuration_" + str(number)} for number in range(2, 8)])
    state = current(service.status(rid))
    for card in state["focused_round"]["primary_collection"]["sources"]:
        value["source_evidence"].append({"id": card["id"], "path": card["text_artifact_id"],
            "sha256": card["text_sha256"], "quote": "Authorization must bind the operation intent and its eventual effect.",
            "interpretation": "This actual synthetic primary quotation was accidentally classified as a repository witness."})
    return value


def prepare_focused_analysis(service, rid, monkeypatch):
    close_original(service, rid, monkeypatch)
    service.grant_focused_manuscript_round(rid)
    monkeypatch.setattr(service, "_improvement_collect_primary_bodies", lambda ws, record, selection:
        synthetic_primary_collection(service, ws, record, selection))
    task = reserve(service, rid)
    selection = selection_value()
    selection["sources"].append({"url": PRIMARY_PRIOR_CANDIDATES[2]["url"],
        "comparison_question": "Which capability lifetime does the third synthetic comparison require?",
        "expected_method_difference": "Separate its source-described mechanism from a proposed application design."})
    retain(service, rid, task, selection)
    return reserve(service, rid)


def test_repair_separates_three_proven_primary_records_preserving_rejected_response_and_budget(continuation, monkeypatch):
    service, rid, _, _ = continuation
    task = prepare_focused_analysis(service, rid, monkeypatch)
    value = misclassified_analytical_fixture(service, rid)
    assert len(value["source_evidence"]) == 10
    with monkeypatch.context() as patch:
        patch.setattr("paper_factory.autonomous.manuscript_improvement_workflow.canonical_focused_analysis",
            lambda raw, cards, texts: (FocusedAnalyticalResults.model_validate(raw), None))
        rejected = retain(service, rid, task, value)
    call = current(rejected)["calls"][-1]
    assert call["outcome"] == "rejected" and call["error"] == "Repository finding differs from its frozen source manifest"
    closed = service.finish_manuscript_improvement(rid)
    assert current(closed)["finished"] and current(closed)["focused_round"]["closed"]
    repaired = service.repair_manuscript_improvement(rid)
    state = current(repaired)
    assert not state["finished"] and not state["focused_round"]["closed"]
    assert state["next_task"]["purpose"] == "focused-write"
    assert state["calls"][-1]["outcome"] == "rejected" and state["calls"][-1]["error"] == call["error"]
    assert state["policy"] == current(closed)["policy"] and state["counts"] == current(closed)["counts"]
    artifact = state["focused_round"]["analysis_artifact_id"]
    normalized = json.loads(service.artifact_path(rid, artifact).read_text(encoding="utf-8"))
    assert normalized["value"]["source_evidence"] == value["source_evidence"][:7]
    assert normalized["value"]["worksheets"] == value["worksheets"]
    assert len(normalized["primary_evidence_normalization"]["primary_document_records"]) == 3
    for key, artifact in closed["artifacts"].items():
        assert repaired["artifacts"][key] == artifact
    again = service.repair_manuscript_improvement(rid)
    assert again["manuscript_improvement_snapshot"] == repaired["manuscript_improvement_snapshot"]


@pytest.mark.parametrize("damage", ["path", "sha", "quote", "transition"])
def test_primary_record_separation_rejects_any_unproven_binding_or_transition_use(continuation, monkeypatch, damage):
    service, rid, _, _ = continuation
    prepare_focused_analysis(service, rid, monkeypatch)
    value = misclassified_analytical_fixture(service, rid)
    state = current(service.status(rid))
    cards = {item["id"]: item for item in state["focused_round"]["primary_collection"]["sources"]}
    texts = {identifier: service.artifact_path(rid, card["text_artifact_id"]).read_text(encoding="utf-8")
             for identifier, card in cards.items()}
    if damage == "path":
        value["source_evidence"][-1]["path"] = "unrelated-private-path.txt"
    elif damage == "sha":
        value["source_evidence"][-1]["sha256"] = "0" * 64
    elif damage == "quote":
        value["source_evidence"][-1]["quote"] = "This invented quotation is absent from the actual retained primary body."
    else:
        value["worksheets"][0]["baseline_model"]["transitions"][0]["evidence_ids"].append(value["source_evidence"][-1]["id"])
    with pytest.raises(ValueError, match="primary witness"):
        canonical_focused_analysis(value, cards, texts)


def test_retained_html_title_enriches_reference_metadata_without_inventing_authors(continuation, monkeypatch):
    service, rid, _, _ = continuation
    with service._operation(rid) as (ws, record):
        raw, text = ws.path("research/synthetic-electron.raw"), ws.path("research/synthetic-electron.txt")
        raw.write_text("<html><head><title>Clipboard | Electron</title></head><body>Skip to content. Actual synthetic API text.</body></html>", encoding="utf-8")
        text.write_text("Skip to content.\nActual synthetic API body, not an inferred document title.", encoding="utf-8")
        _freeze(ws, record, "synthetic-reference-raw", raw)
        _freeze(ws, record, "synthetic-reference-text", text)
        card = {"id": "synthetic-electron", "status": "retained", "url": "https://example.org/clipboard",
            "content_type": "text/html", "text_artifact_id": "synthetic-reference-text", "text_sha256": record.artifacts["synthetic-reference-text"].sha256,
            "raw_artifact_id": "synthetic-reference-raw", "raw_sha256": record.artifacts["synthetic-reference-raw"].sha256}
        with monkeypatch.context() as patch:
            patch.setattr(service, "_repository_references", lambda *args: ([card], [], []))
            enriched = service._improvement_reference_cards(ws, record, {"evidence_collection": None})[0]
        assert enriched["title"] == "Clipboard | Electron" and enriched["text"] == text.read_bytes().decode("utf-8")
        assert "authors" not in enriched and "year" not in enriched and "title" not in card


def focused_writer_value(service, rid, task, *, citation_tokens=False):
    cards = current(service.status(rid))["focused_round"]["primary_collection"]["sources"]
    articles = []
    for venue in ("ieee-software", "ieee-security-privacy"):
        item = revision(service, rid, {**task, "venue_id": venue, "action_id": "focused-write-" + venue})
        for card in cards:
            item["manuscript"]["literature_evidence"].append({"source_id": card["id"], "text_sha256": card["text_sha256"],
                "quote": "Authorization must bind the operation intent and its eventual effect.",
                "interpretation": "An explicitly synthetic retained primary method supports this controller fixture only."})
            item["manuscript"]["sections"][1]["text"] += " {{" + ("citation" if citation_tokens else "document") + ":" + card["id"] + "}}"
        articles.append(item)
    return {"revisions": articles}


def test_rejected_focused_writer_repairs_verified_primary_kind_without_new_call_and_reopens_only_review(continuation, monkeypatch):
    service, rid, _, _ = continuation
    analysis_task = prepare_focused_analysis(service, rid, monkeypatch)
    retain(service, rid, analysis_task, analytical_value(service, rid))
    task = reserve(service, rid)
    value = focused_writer_value(service, rid, task)
    with monkeypatch.context() as patch:
        patch.setattr("paper_factory.autonomous.manuscript_improvement_workflow.canonical_focused_revision",
            lambda raw, cards, texts: (canonical_quality_revision(raw)[0], {"primary_citation_kind": None}))
        rejected = retain(service, rid, task, value)
    assert current(rejected)["calls"][-1]["outcome"] == "rejected"
    closed = service.finish_manuscript_improvement(rid)
    monkeypatch.setattr(service, "_improvement_focused_preflight", lambda ws, record, state, venue, markdown:
        (markdown, {"artifact_id": "synthetic-preflight-" + venue, "sha256": "a" * 64,
                    "content_format_passed": True, "report": {"scope": "Synthetic preflight fixture, no actual Word operation."}}))
    repaired = service.repair_manuscript_improvement(rid)
    state = current(repaired)
    assert not state["finished"] and state["next_task"]["purpose"] == "focused-review"
    assert state["counts"]["model_attempts"] == current(closed)["counts"]["model_attempts"]
    assert state["policy"] == current(closed)["policy"]
    assert state["calls"][-1] == current(closed)["calls"][-1]
    assert state["focused_round"]["writer_repairs"][task["call_id"]]["outcome"] == "admitted"
    assert set(state["focused_round"]["write_versions"]) == {"ieee-software", "ieee-security-privacy"}
    for candidate in value["revisions"]:
        version = state["focused_round"]["write_versions"][candidate["venue_id"]]
        saved = json.loads(service.artifact_path(rid, version["draft_artifact_id"]).read_bytes())
        assert saved["value"]["sections"] == candidate["manuscript"]["sections"]
        assert not saved["value"]["literature_evidence"]
    for key, artifact in closed["artifacts"].items():
        assert repaired["artifacts"][key] == artifact
    assert service.repair_manuscript_improvement(rid)["manuscript_improvement_snapshot"] == repaired["manuscript_improvement_snapshot"]


def test_primary_citation_kind_moves_only_verified_records_and_exact_tokens(continuation, monkeypatch):
    service, rid, _, _ = continuation
    analysis_task = prepare_focused_analysis(service, rid, monkeypatch)
    retain(service, rid, analysis_task, analytical_value(service, rid))
    task = reserve(service, rid)
    value = focused_writer_value(service, rid, task, citation_tokens=True)["revisions"][0]
    state = current(service.status(rid))
    cards = {card["id"]: card for card in state["focused_round"]["primary_collection"]["sources"]}
    texts = {identifier: service.artifact_path(rid, card["text_artifact_id"]).read_bytes().decode()
             for identifier, card in cards.items()}
    repaired, proof = canonical_focused_revision(value, cards, texts)
    assert len(repaired.manuscript.document_evidence) == len(value["manuscript"]["document_evidence"]) + 3
    assert repaired.manuscript.source_evidence[0].model_dump() == value["manuscript"]["source_evidence"][0]
    assert repaired.manuscript.revision.model_dump() == value["manuscript"]["revision"]
    for before, after in zip(value["manuscript"]["sections"], repaired.manuscript.sections):
        expected = before["text"]
        for identifier in cards:
            expected = expected.replace("{{citation:" + identifier + "}}", "{{document:" + identifier + "}}")
        assert after.text == expected and after.heading == before["heading"]
    assert set(proof["primary_citation_kind"]["exact_token_replacements"].values()) == {1}
    for field, damage in (("source_id", "focused-document-unknown"), ("text_sha256", "0" * 64),
                          ("quote", "An invented quotation that is absent from every retained actual primary source.")):
        broken = copy.deepcopy(value)
        broken["manuscript"]["literature_evidence"][0][field] = damage
        with pytest.raises(ValueError, match="primary citation"):
            canonical_focused_revision(broken, cards, texts)


def test_uncited_document_separation_verifies_quote_before_retaining_supplement(continuation, monkeypatch):
    service, rid, _, _ = continuation
    analysis_task = prepare_focused_analysis(service, rid, monkeypatch)
    retain(service, rid, analysis_task, analytical_value(service, rid))
    task = reserve(service, rid)
    value = focused_writer_value(service, rid, task)["revisions"][0]
    with service._operation(rid) as (ws, record):
        state = service._improvement_state(ws, record)
        card = {**state["focused_round"]["primary_collection"]["sources"][0], "id": "synthetic-uncited-document"}
        state["evidence_collection"] = {"sources": [card]}
        unused = {"source_id": card["id"], "text_sha256": card["text_sha256"],
            "quote": "Authorization must bind the operation intent and its eventual effect.",
            "interpretation": "An exact synthetic uncited witness is retained as supplementary evidence only."}
        value["manuscript"]["document_evidence"].append(unused)
        repaired, proof = service._improvement_focused_revision(ws, record, state, value)
        assert proof["uncited_verified_document_witnesses"] == [unused]
        assert repaired.manuscript.sections[1].text == value["manuscript"]["sections"][1]["text"]
        broken = copy.deepcopy(value)
        broken["manuscript"]["document_evidence"][0]["quote"] = "An invented absent document quotation cannot be silently dropped as uncited."
        with pytest.raises(ValueError, match="evidence|Documentation"):
            service._improvement_focused_revision(ws, record, state, broken)

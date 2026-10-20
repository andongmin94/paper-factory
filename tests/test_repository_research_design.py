"""Constructive first-study pipeline with temporary sources and mocked acquisition.

No provider call, real study, project execution or publication-quality claim is
made by these fixtures. The real native collector verifies the acquired body.
"""

import copy
import hashlib
import json
from uuid import uuid4

import pytest

from paper_factory.autonomous.repository_portfolio import AGENDA_MARKER, MATERIAL_HEADER
from paper_factory.workflow import _inference_read, WorkflowError
from test_repository_paper_workflow import study, plan, analysis_value, draft
from test_repository_portfolio import retain_portfolio_response, work_products_fixture
from test_scholarly_html import HINT, HTML, collection, clock


def agenda():
    candidates = []
    for identifier, question, query in (
        ("effects", "Does forcing a configuration option improve observed reliability?", "configuration reliability effects"),
        ("ownership", "When should a caller retain control of a configuration default?", HINT["title"]),
    ):
        candidates.append({"id": identifier, "question": question,
            "reader_decision": "Choose whether a caller or the library owns the enabled setting.",
            "source_evidence_ids": ["configuration"],
            "known_approach": "Apply a library default before caller options when the caller owns the choice.",
            "proposed_addition": "Compare the observed override order under identical ownership requirements.",
            "falsifier": "The closest method already supplies the same decision for these exact requirements.",
            "method_route": "source_comparison", "literature_queries": [query],
            "evidence_needs": [{"kind": "closest_method", "target": "A complete method body about default ownership.",
                "purpose": "Compare the source order against a concrete existing method under equal conditions."}]})
    return {"candidates": candidates, "provisional_selected_id": "effects",
        "reason": "A provisional question remains revisable after actual source and method acquisition."}


@pytest.fixture
def designed_study(study, monkeypatch):
    service, rid = study
    service.submit_repository_plan(rid, plan(service, rid))
    monkeypatch.setattr("paper_factory.submission_requirements.fetch_requirements", lambda url: {
        "status": "retained", "raw": ("Synthetic complete publication guidance. " + url).encode(),
        "http_status": 200, "content_type": "text/plain", "error": None})
    status = service.status(rid)
    service.start_portfolio(rid, {"targets": [{"venue_id": venue["id"], "article_category": "Feature Article"}
        for venue in status["repository_paper"]["publication_venues"]["venues"]]})
    return service, rid


def planning_receipt(service, rid):
    status = service.status(rid)
    portfolio = status["repository_paper"]["portfolio"]
    value = {"queries": [HINT["title"]], "pdf_candidates": [], "html_candidates": [HINT],
        "reason": "Acquire the method needed to reconsider the provisional research question.", "research_agenda": agenda()}
    inventory = status["material_manifest"]["source"]
    source = {"tool.js": service.read_material(rid, "source", "tool.js")["text"]}
    assets = {item["name"]: item for item in inventory}
    materials = {"productionSource": source, "sourceInventory": inventory,
        "inspectedSourceFiles": list(source), "uninspectedSourceFiles": [item["name"] for item in inventory if item["name"] not in source],
        "sourceReads": [{**assets[name], **_inference_read(text)} for name, text in source.items()],
        "retainedLiterature": [], "retainedReferences": []}
    binding = {"research_id": rid, "portfolio_start_sha256": portfolio["sha256"],
        "plan": status["repository_paper"]["plan"]}
    prompt = "Synthetic existing acquisition planning task. " + AGENDA_MARKER + json.dumps(binding) + MATERIAL_HEADER + json.dumps(materials)
    receipt = {"id": str(uuid4()), "phase": "literature-plan", "at": "2026-10-20T00:00:00+00:00",
        "model": "synthetic-test-model", "profileId": "fixture-profile", "prompt": prompt,
        "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(), "outcome": "started"}
    service.record_inference(rid, receipt)
    text = json.dumps(value)
    saved = service.record_inference(rid, {**receipt, "outcome": "completed", "text": text,
        "textSha256": hashlib.sha256(text.encode()).hexdigest()})
    return value, saved["artifactId"]


def acquire(service, rid, monkeypatch):
    value, key = planning_receipt(service, rid)
    calls = []
    quote = "Defaults are applied before caller options to preserve caller control."
    body = HTML.replace(b"receiver.send(resource, content)\nreturn receipt", quote.encode())
    def collect(queries, root, **kwargs):
        calls.append((queries, kwargs))
        return collection(monkeypatch, root, body=body)[0]
    service.collector = collect
    status = service.collect_portfolio_literature(rid, value["queries"], [], [HINT], value["research_agenda"], key)
    return status, calls, quote


def test_acquisition_changes_selected_question_and_supplies_actual_comparative_content_to_writer(designed_study, monkeypatch, clock):
    service, rid = designed_study
    original = service.status(rid)
    original_bytes = {key: service.artifact_path(rid, key).read_bytes() for key in original["artifacts"]}
    acquired, calls, quote = acquire(service, rid, monkeypatch)
    pf = acquired["repository_paper"]["portfolio"]
    assert pf["research_design_contract"] == 1 and len(calls) == 1
    assert calls[0][0] == [HINT["title"]] and calls[0][1]["html_candidates"] == [HINT]
    assert acquired["study_literature_attempt"] == 1 and acquired["repository_paper"]["analysis_attempts"] == 0
    assert pf["research_agenda"]["value"]["provisional_selected_id"] == "effects"
    source, = pf["literature"]["sources"]
    assert source["scope"] == "full_text"
    material = next(item for item in acquired["material_manifest"]["literature"] if item.get("source_id") == source["id"])
    delivered = service.read_material(rid, "evidence", material["name"])
    evidence = {"source_id": source["id"], "text_sha256": source["text_sha256"], "quote": quote,
        "interpretation": "The synthetic acquired method gives the caller the final setting through option order."}
    value = analysis_value(service, rid)
    value["literature_evidence"] = [evidence]
    value["findings"][0]["claim"] = "The retained source forces enabled true; caller-owned requirements instead need the opposite override order."
    value["work_products"] = work_products_fixture("configuration")
    value["work_products"]["products"][0]["changed_decisions"][0].update({
        "prior_method_evidence_ids": [source["id"]], "baseline_decision": "Use a default before caller options when the caller owns this setting.",
        "additional_analysis": "The actual source places enabled true after the caller options and overrides that choice.",
        "changed_decision": "Retain forced enabled only under a library-owned requirement; otherwise reverse the order."})
    value["research_design"] = {"selected_question_id": "ownership", "candidate_decisions": [
        {"question_id": "effects", "decision": "not_supported", "reason": "Static source and the acquired method do not establish observed reliability effects."},
        {"question_id": "ownership", "decision": "selected", "reason": "The actual source and acquired default method support a completed ownership comparison."}],
        "closest_methods": [{"id": "caller-default", "evidence": [evidence],
            "already_provides": "The method already preserves caller control with the default first.",
            "same_conditions": "Both alternatives receive identical caller options and the same enabled ownership requirement.",
            "difference": "The repository forces the library value after those options; the method preserves the caller value.",
            "decision_change": "Choose override order from actual ownership requirements, without claiming measured gains."}],
        "finding_ids": ["finding_configuration"], "product_ids": ["source-choice"], "evidence_gaps": [],
        "strengthening_needed": False, "followup_queries": []}
    def materials(packet):
        packet["retainedLiterature"] = [{"source_id": source["id"], "name": material["name"],
            "sha256": source["text_sha256"], "text": delivered["text"], **_inference_read(delivered["text"])}]
    key, _ = retain_portfolio_response(service, rid, value, "source-analysis", material_change=materials)
    analyzed = service.submit_portfolio_analysis(rid, {"inference_artifact_id": key, "analysis": value})
    brief = analyzed["repository_paper"]["portfolio"]["research_design_report"]["writer_brief"]
    assert brief["selected_question"]["id"] == "ownership"
    assert brief["completed_findings"][0]["claim"] == value["findings"][0]["claim"]
    assert brief["closest_methods"][0]["evidence"][0]["quote"] == quote
    article = draft(service, rid, prepare_analysis=False)
    article["sections"][1]["text"] += " " + brief["selected_question"]["question"]
    writer_key, receipt = retain_portfolio_response(service, rid, article, "venue-manuscript", "ieee-software", material_change=materials)
    assert brief["completed_findings"][0]["claim"] in json.loads(receipt["prompt"].split(MATERIAL_HEADER)[1])["portfolioResearchWork"]["text"]
    written = service.submit_portfolio_manuscript(rid, {"venue_id": "ieee-software", "inference_artifact_id": writer_key, "manuscript": article})
    assert "caller retain control" in written["repository_paper"]["portfolio"]["venues"][0]["draft"]["sections"][1]["text"]
    assert written["study_literature_attempt"] == 1 and written["repository_paper"]["analysis_attempts"] == 1
    assert written["execution_attempt"] == written["code_attempt"] == written["draft_attempt"] == 0
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in original_bytes.items())


@pytest.mark.parametrize("damage", ["query", "agenda", "receipt"])
def test_collection_uses_exact_completed_candidate_plan_before_spending_acquisition(designed_study, damage):
    service, rid = designed_study
    value, key = planning_receipt(service, rid)
    before = service.status(rid)
    if damage == "query": value["queries"] = ["unrelated acquisition query"]
    if damage == "agenda": value["research_agenda"]["reason"] += " Altered after completion."
    if damage == "receipt": key = key.replace("completed", "started")
    service.collector = lambda *args, **kwargs: pytest.fail("Altered planning must not consume a collection")
    with pytest.raises((ValueError, WorkflowError)):
        service.collect_portfolio_literature(rid, value["queries"], [], [HINT], value["research_agenda"], key)
    after = service.status(rid)
    assert after["study_literature_attempt"] == 0 and after["artifacts"] == before["artifacts"]

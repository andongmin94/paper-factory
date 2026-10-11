"""Synthetic query remediation preserves history; no fixture assesses science."""
import copy
import hashlib
import json

import pytest
import httpx
from pydantic import ValidationError

from paper_factory import ipc, workflow as native
from paper_factory.autonomous import literature
from paper_factory.autonomous.preparation import RedesignSearchRepairPlan
from paper_factory.workflow import WorkflowError
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import write_json
from test_planned_claim_projection import COUNTERS
from test_redesign_admission_feedback import held
from test_redesign_question_evidence import basis
from test_redesign_question_preparation import assert_originals, frozen_originals, workflow_comparison, workflow_routes
from test_workflow import collect_arxiv_preprint, setup
from test_autonomous_literature import clock
from test_unicode_literature import install as install_unicode, public_response
from test_autonomous_literature import mocked, record as crossref_record
from test_public_pdf_hints import DOI, TITLE, URL, PDF, TEXT
from test_author_pdf_discovery import listing_leaf


def diagnosed(setup, *, transient=None, eligible_pdf=False, old_reservations=None):
    service, runner, identifier, _, proposed, *_ = held(setup)
    routes = workflow_routes(proposed)
    for index, item in enumerate(routes["candidates"]):
        item["literature_queries"] = [f"synthetic original compound prerequisite comparison evidence route {index}"]
    state = service.prepare_redesign_questions(identifier, routes)
    service.select_redesign_question(identifier, workflow_comparison(state, routes, selected=None))

    def failed_queries(queries, root, **kwargs):
        (root / "literature").mkdir(exist_ok=True)
        source_id = "source-" + hashlib.sha256(b"doi:10.1234/prior").hexdigest()[:20]
        malformed = {"status": "ok", "message": {"DOI": "10.1234/prior", "title": ["Synthetic missing-author metadata fixture"]}}
        path, sha = literature._save(root, source_id + "-metadata", "json", json.dumps(malformed).encode())
        assert native._crossref_original(path) and sha[:16] in path
        raw = {"status": "ok", "message": {"items": [malformed["message"]]}}
        crossref_path, crossref_sha = literature._save(root, "crossref-search-fixture", "json", json.dumps(raw).encode())
        empty = b'<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"><opensearch:totalResults>0</opensearch:totalResults></feed>'
        method_path, method_sha = literature._save(root, "arxiv-method-fixture", "xml", empty)
        searches = [{"query": query, "provider": "Crossref", "lookup": "bibliographic", "status": "succeeded", "attempted": True,
                     "raw_path": crossref_path, "sha256": crossref_sha} for query in queries]
        searches.append({"query": queries[0], "provider": "arXiv", "lookup": "method", "status": "succeeded", "attempted": True,
                         "raw_path": method_path, "sha256": method_sha})
        packet = {"sources": [], "searches": searches, "warnings": [], "pdf_hint_attempts": []}
        if eligible_pdf:
            valid = {"status": "ok", "message": {"DOI": "10.1234/provider", "title": ["Synthetic provider metadata fixture"],
                "author": [{"given": "Fixture", "family": "Author"}], "published": {"date-parts": [[2020]]},
                "link": [{"URL": "https://arxiv.org/pdf/2001.00001v1", "content-type": "application/pdf"}]}}
            sid = "source-" + hashlib.sha256(b"doi:10.1234/provider").hexdigest()[:20]
            mp, ms = literature._save(root, sid + "-metadata", "json", json.dumps(valid).encode())
            doi, title, authors, year = literature._metadata(valid)
            packet["sources"] = [{"id": sid, "doi": doi, "title": title, "authors": authors, "year": year,
                "provider": "Crossref", "scope": "metadata_only", "excerpts": [], "queries": list(queries),
                "url": "https://doi.org/" + doi, "metadata_path": mp, "metadata_sha256": ms,
                "raw_path": mp, "sha256": ms}]
        if transient:
            packet[transient] = True
        if old_reservations is not None:
            packet["pdf_reservations"] = old_reservations
        return packet

    service.collector = failed_queries
    state = service.collect_redesign_question_evidence(identifier)
    return service, runner, identifier, state, routes, proposed


def plan(routes, *, action="refine_queries"):
    return {"action": action, "reason": "The complete synthetic query responses diagnose an overly compound AND search, not scientific absence.",
            "queries": [] if action == "hold" else [{"question_id": routes["candidates"][0]["id"],
                "original_query": routes["candidates"][0]["literature_queries"][0], "query": "synthetic bibliography",
                "rationale": "A shorter synthetic bibliographic phrase tests the diagnosed precision repair without a scientific finding."}]}


def repair_collector(calls, *, mode="held"):
    def retrieve(queries, root, *, limit, cancel, pdf_candidates, pdf_reservation_limit, excluded_identities):
        calls.append({"queries": list(queries), "limit": limit, "pdf_candidates": pdf_candidates,
                      "remaining": pdf_reservation_limit, "excluded": list(excluded_identities)})
        if mode == "exception":
            raise OSError("Synthetic interruption after one durable search repair dispatch")
        if mode == "held":
            packet = {"sources": [], "searches": [{"query": q, "status": "succeeded", "attempted": True} for q in queries], "warnings": []}
            trace = []
        else:
            (root / "literature").mkdir(exist_ok=True)
            packet = collect_arxiv_preprint(queries, root, limit=limit, cancel=cancel, arxiv_id="2401.00001v1")
            source = packet["sources"][0]
            source["queries"] = list(queries)
            text = (root / source["text_path"]).read_text(encoding="utf-8").replace(
                "\nReferences", "\nA different synthetic primary body for mechanical query repair tests. " * 5 + "\nReferences")
            literature._retain_full_text(source, root, text, source["url"], source["raw_path"], source["sha256"])
            trace = [{"source_id": source["id"], "identity": "arxiv:" + source["arxiv_id"], "arxiv_id": source["arxiv_id"],
                      "route": "provider_pdf", "url": source["url"], "pdf_attempted": True}]
            if mode == "invalid_proof": source["text_sha256"] = "0" * 64
            if mode == "cancelled": packet["cancelled"] = True
            if mode == "cap": trace *= 3
            if mode == "excluded_alias": trace[0]["arxiv_id"] = "1311.3903v1"
        packet.update(pdf_reservation_limit=pdf_reservation_limit, pdf_reservations=trace, excluded_identities=list(excluded_identities))
        return packet
    return retrieve


def reserve_and_plan(service, identifier, routes):
    state = service.reserve_redesign_question_search_repair(identifier)
    assert state["redesign_question_search_repair"]["status"] == "planning"
    return service.submit_redesign_question_search_repair(identifier, plan(routes))


def test_diagnosis_uses_real_content_hashed_metadata_and_reserves_once_without_count_reset(setup):
    service, runner, identifier, before, routes, _ = diagnosed(setup)
    assert before["redesign_question_search_repair_available"] is True
    original = frozen_originals(service, identifier, before); original_basis = basis(service, identifier)
    state = reserve_and_plan(service, identifier, routes)
    repair = state["redesign_question_search_repair"]
    assert repair["status"] == "planned" and repair["planCount"] == 1 and repair["collectionCount"] == 0
    assert repair["remainingPdfAttempts"] == 2 and repair["newPrimarySourceIds"] == []
    assert repair["failureInventory"]["metadata_rejections"][0]["reason"] == "invalid_bibliographic_identity"
    assert state["redesign_question_search_repair_available"] is False
    assert tuple(state[key] for key in COUNTERS) == tuple(before[key] for key in COUNTERS)
    assert state["redesign_question_evidence"] == before["redesign_question_evidence"]
    assert service.reserve_redesign_question_search_repair(identifier)["redesign_question_search_repair"] == repair
    assert service.submit_redesign_question_search_repair(identifier, plan(routes))["redesign_question_search_repair"] == repair
    with pytest.raises(WorkflowError): service.submit_redesign_question_search_repair(identifier, plan(routes, action="hold"))
    assert basis(service, identifier) == original_basis
    assert_originals(service, identifier, original); assert runner.calls == 0


@pytest.mark.parametrize("transient", ["cancelled", "timed_out", "rate_limited"])
def test_transient_failure_does_not_qualify_as_query_precision_failure(setup, transient):
    service, runner, identifier, state, _, _ = diagnosed(setup, transient=transient)
    assert state["redesign_question_search_repair_available"] is False
    with pytest.raises(WorkflowError) as error: service.reserve_redesign_question_search_repair(identifier)
    assert error.value.code == "SEARCH_REPAIR_UNAVAILABLE" and runner.calls == 0


def test_unknown_historical_ordinary_pdf_reservation_cannot_reset_shared_budget(setup):
    service, runner, identifier, state, _, _ = diagnosed(setup, eligible_pdf=True)
    assert state["redesign_question_search_repair_available"] is False
    with pytest.raises(WorkflowError): service.reserve_redesign_question_search_repair(identifier)
    assert runner.calls == 0


def test_verified_old_reservation_reduces_repair_budget_without_subtracting_old_formal_collections(setup):
    old = [{"source_id": "source-" + "a" * 20, "identity": "doi:10.1234/failed", "route": "provider_pdf",
            "url": "https://arxiv.org/pdf/2301.00001v1", "pdf_attempted": True}]
    service, runner, identifier, state, routes, _ = diagnosed(setup, old_reservations=old)
    assert state["redesign_question_search_repair_available"]
    state = reserve_and_plan(service, identifier, routes)
    calls = []; service.collector = repair_collector(calls)
    state = service.collect_redesign_question_search_repair(identifier)
    assert calls[0]["remaining"] == 1 and "doi:10.1234/failed" in calls[0]["excluded"]
    assert state["redesign_question_search_repair"]["remainingPdfAttempts"] == 1 and runner.calls == 0


@pytest.mark.parametrize("mode", ["held", "cancelled", "exception", "invalid_proof", "cap", "excluded_alias"])
def test_absent_failed_or_invalid_repair_cannot_replay_collection_or_independent_vote(setup, mode):
    service, runner, identifier, before, routes, _ = diagnosed(setup)
    original = frozen_originals(service, identifier, before); original_basis = basis(service, identifier)
    reserve_and_plan(service, identifier, routes)
    calls = []; service.collector = repair_collector(calls, mode=mode)
    if mode in {"exception", "invalid_proof", "cap", "excluded_alias"}:
        with pytest.raises((ValueError, OSError)): service.collect_redesign_question_search_repair(identifier)
        state = service.status(identifier)
    else:
        state = service.collect_redesign_question_search_repair(identifier)
    repair = state["redesign_question_search_repair"]
    assert repair["status"] == ("held" if mode == "held" else "incomplete")
    assert repair["collectionCount"] == 1 and state["redesign_question_reassessment"] is None
    with pytest.raises(WorkflowError): service.reassess_redesign_question(identifier, workflow_comparison(state, routes, selected=None))
    service.collect_redesign_question_search_repair(identifier)
    assert len(calls) == 1 and calls[0]["queries"] == ["synthetic bibliography"]
    assert calls[0]["limit"] == 3 and calls[0]["pdf_candidates"] is None and calls[0]["remaining"] == 2
    assert "doi:10.1234/prior" in calls[0]["excluded"]
    assert basis(service, identifier) == original_basis
    assert_originals(service, identifier, original); assert runner.calls == 0


def test_genuinely_new_body_enables_only_unused_reassessment_with_exact_new_receipt_bindings(setup):
    service, runner, identifier, before, routes, _ = diagnosed(setup)
    original = frozen_originals(service, identifier, before); original_basis = basis(service, identifier)
    reserve_and_plan(service, identifier, routes)
    calls = []; service.collector = repair_collector(calls, mode="new")
    state = service.collect_redesign_question_search_repair(identifier)
    repair = state["redesign_question_search_repair"]
    assert repair["status"] == "ready" and repair["collectionCount"] == 1
    source_id = repair["literature"]["sources"][0]["id"]
    body = next(item for item in state["material_manifest"]["literature"] if item["source_id"] == source_id)
    assert body["name"].startswith(native.SEARCH_REPAIR_PREFIX)
    assert service.read_material(identifier, "evidence", body["name"], limit=32000)["sha256"] == body["sha256"]
    comparison = workflow_comparison(state, routes, selected=None)
    for item in comparison["comparisons"]: item["evidence_sources"] = [source_id]
    state = service.reassess_redesign_question(identifier, comparison)
    receipt = json.loads(service.artifact_path(identifier, "redesign-question-reassessment").read_bytes())
    assert receipt["bindings"] == {**repair["bindings"],
        **{key: state["artifacts"][artifact]["sha256"] for key, artifact in (
            ("search_repair_sha256", "redesign-question-search-repair"),
            ("search_repair_collection_sha256", "redesign-question-search-repair-collection"),
            ("search_repair_plan_sha256", "redesign-question-search-repair-plan"),
            ("search_repair_reservation_sha256", "redesign-question-search-repair-reservation"))}}
    assert state["redesign_question_reassessment"] == comparison and state["redesign_question_selection"] == before["redesign_question_selection"]
    assert state["redesign_question_evidence"] == before["redesign_question_evidence"]
    assert service.reassess_redesign_question(identifier, comparison)["redesign_question_reassessment"] == comparison
    changed = copy.deepcopy(comparison); changed["reason"] += " Different vote."
    with pytest.raises(WorkflowError): service.reassess_redesign_question(identifier, changed)
    service.collect_redesign_question_search_repair(identifier)
    assert len(calls) == 1 and basis(service, identifier) == original_basis
    assert_originals(service, identifier, original); assert runner.calls == 0


def test_schema_and_native_literal_query_control_rejects_duplicate_or_oracle_inputs(setup):
    service, runner, identifier, _, routes, _ = diagnosed(setup)
    reserve_and_plan(service, identifier, routes)
    for field, value in (("question_id", "invented-question"), ("original_query", "invented original words missing six literal terms"),
                         ("query", "doi:10.1234/prior"), ("query", "arxiv:2401.00001v1")):
        changed = plan(routes); changed["queries"][0][field] = value
        with pytest.raises(ValueError): service.submit_redesign_question_search_repair(identifier, changed)
    reservation_path = service.artifact_path(identifier, "redesign-question-search-repair-reservation")
    original_bytes = reservation_path.read_bytes()
    record = service._workspace(identifier).latest("workflow", Workflow)
    saved = copy.deepcopy(record.artifacts)
    for field, value in (("remainingPdfAttempts", True), ("excluded_identities", []), ("original_queries", []), ("failureInventory", {})):
        changed = json.loads(original_bytes); changed[field] = value
        write_json(reservation_path, changed)
        native._freeze(service._workspace(identifier), record, "redesign-question-search-repair-reservation", reservation_path)
        service._save(service._workspace(identifier), record)
        with pytest.raises(ValueError): service.status(identifier)
        reservation_path.write_bytes(original_bytes); record.artifacts = copy.deepcopy(saved)
        service._save(service._workspace(identifier), record)
    assert runner.calls == 0


@pytest.mark.parametrize("defect", ["one_term", "six_terms", "duplicate_tokens", "hold_with_query", "refine_empty", "extra_science"])
def test_search_plan_schema_is_small_and_cannot_encode_result_or_approval(defect):
    routes = {"candidates": [{"id": "route-1", "literature_queries": ["original compound query has more than five words"]}]}
    value = plan(routes)
    if defect == "one_term": value["queries"][0]["query"] = "single"
    elif defect == "six_terms": value["queries"][0]["query"] = "one two three four five six"
    elif defect == "duplicate_tokens": value["queries"].append({**value["queries"][0], "query": "BIBLIOGRAPHY, SYNTHETIC!"})
    elif defect == "hold_with_query": value["action"] = "hold"
    elif defect == "refine_empty": value["queries"] = []
    else: value["scientific_approval"] = True
    with pytest.raises(ValidationError): RedesignSearchRepairPlan.model_validate(value)


def test_ipc_accepts_only_native_research_id_and_model_plan_without_manual_budget_or_queries():
    for method in ("reserve", "collect", "submit"):
        request = {"id": "fixture", "method": "workflow." + method + "RedesignQuestionSearchRepair",
                   "params": {"researchId": "research-123456789abc"}}
        if method == "submit": request["params"]["value"] = {"action": "hold", "queries": [], "reason": "Synthetic explicit held plan with no favorable scientific inference."}
        assert ipc.request(json.dumps(request).encode())["params"] == request["params"]
        request["params"]["remainingPdfAttempts"] = 2
        with pytest.raises(ValueError): ipc.request(json.dumps(request).encode())


def test_reasoning_allows_existing_multiline_rationale_but_literal_queries_remain_single_line():
    routes = {"candidates": [{"id": "route-1", "literature_queries": ["original compound query has more than five words"]}]}
    value = plan(routes)
    value["reason"] += "\nA second explanatory sentence remains only provisional reasoning."
    value["queries"][0]["rationale"] += "\tNo observations or approval are inferred."
    assert RedesignSearchRepairPlan.model_validate(value).model_dump(mode="json") == value
    value["queries"][0]["query"] += "\nnew term"
    with pytest.raises(ValidationError): RedesignSearchRepairPlan.model_validate(value)


def test_real_official_html_background_does_not_discard_new_verified_pdf_body(setup, monkeypatch, clock):
    service, runner, identifier, before, routes, _ = diagnosed(setup)
    service.reserve_redesign_question_search_repair(identifier)
    value = plan(routes); value["queries"][0]["query"] = "UAX77 bibliography"
    service.submit_redesign_question_search_repair(identifier, value)
    install_unicode(monkeypatch, public_response)
    calls = []
    pdf_collect = repair_collector(calls, mode="new")
    def mixed(queries, root, **kwargs):
        background = literature.collect(queries, root, **kwargs)
        assert len(background["sources"]) == 1 and background["sources"][0]["publication_type"] == "technical_standard"
        method = pdf_collect(queries, root, **kwargs)
        background["sources"].extend(method["sources"])
        background["pdf_reservations"] = method["pdf_reservations"]
        return background
    service.collector = mixed
    state = service.collect_redesign_question_search_repair(identifier)
    repair = state["redesign_question_search_repair"]
    assert repair["status"] == "ready" and len(repair["literature"]["sources"]) == 2
    assert repair["newPrimarySourceIds"] == [repair["literature"]["sources"][1]["id"]]
    background = repair["literature"]["sources"][0]
    assert background["id"] not in repair["newPrimarySourceIds"]
    assert any(item["source_id"] == background["id"] for item in state["material_manifest"]["literature"])
    assert state["redesign_question_evidence"] == before["redesign_question_evidence"] and runner.calls == 0


def test_real_author_discovery_redirect_binds_initial_reservation_and_exact_final_identity(setup, monkeypatch, clock):
    service, runner, identifier, _, routes, _ = diagnosed(setup)
    service.reserve_redesign_question_search_repair(identifier)
    value = plan(routes); value["queries"][0]["query"] = "selective recovery comparison"
    service.submit_redesign_question_search_repair(identifier, value)
    initial = URL.replace("~NatProg", "~natprog")
    def respond(request):
        if request.url.host == "api.crossref.org":
            document = {"status": "ok", "message": {"items": [{"DOI": DOI}]}} if request.url.path == "/works" else crossref_record()
            return httpx.Response(200, json=document)
        if str(request.url) == literature.AUTHOR_PUBLICATIONS:
            return httpx.Response(200, content=listing_leaf(href=initial), headers={"content-type": "text/html"})
        if str(request.url) == initial:
            return httpx.Response(302, content=b"Retained synthetic redirect", headers={"content-type": "text/plain", "location": URL.replace("https:", "http:")})
        assert str(request.url) == URL
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    mocked(monkeypatch, respond)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT)
    service.collector = literature.collect
    state = service.collect_redesign_question_search_repair(identifier)
    repair = state["redesign_question_search_repair"]
    assert repair["status"] == "ready"
    source, = repair["literature"]["sources"]
    trace, = repair["literature"]["pdf_reservations"]
    assert source["copy_type"] == "author_copy" and source["url"] == URL and trace["url"] == initial
    assert repair["newPrimarySourceIds"] == [source["id"]] and runner.calls == 0


@pytest.mark.parametrize("traces", [[], [{"source_id": "source-fixture", "identity": "doi:10.1234/failed", "route": "author_copy", "pdf_attempted": True}]])
def test_prior_hint_dispatches_cannot_be_erased_or_merged_in_remaining_pdf_trace(monkeypatch, traces):
    attempts = [{"source_id": "source-fixture", "candidate": {"doi": "10.1234/failed"}, "pdf_attempted": True}] * 2
    monkeypatch.setattr(native, "_read", lambda *args: {"sources": [], "pdf_reservations": traces, "pdf_hint_attempts": attempts})
    with pytest.raises(WorkflowError) as error: native._question_remaining_pdf_attempts(None, None)
    assert error.value.code == "SEARCH_REPAIR_CONFLICT"


def test_repaired_pool_with_one_remaining_pdf_cannot_hide_two_consumed_hint_dispatches():
    attempt = {"source_id": "source-fixture", "candidate": {"doi": "10.1234/failed"}, "pdf_attempted": True, "status": "rejected"}
    trace = {"source_id": "source-fixture", "identity": "doi:10.1234/failed", "route": "author_copy", "pdf_attempted": True,
             "url": "https://www.cs.cmu.edu/~NatProg/papers/fixture.pdf"}
    packet = {"sources": [], "pdf_reservation_limit": 1, "excluded_identities": [], "pdf_reservations": [trace],
              "pdf_hint_attempts": [attempt, attempt]}
    reservation = {"remainingPdfAttempts": 1, "excluded_identities": []}
    with pytest.raises(WorkflowError) as error: native._search_repair_new_primary(None, None, packet, reservation)
    assert error.value.code == "SEARCH_REPAIR_CONFLICT"

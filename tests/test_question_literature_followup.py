"""Synthetic initial retrieval recovery; no fixture establishes research value."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from paper_factory import ipc, workflow as native
from paper_factory.autonomous import literature
from paper_factory.workflow import WorkflowError
from paper_factory.workflow_models import Workflow
from test_planned_claim_projection import COUNTERS
from test_research_question_preparation import artifact_bytes, questions, selection
from test_redesign_question_search_repair import repair_collector as repair_fixture
from test_workflow import protocol, setup


def initial(setup, *, status="incomplete", reservations=1):
    service, runner, identifier = setup
    calls = []
    def retrieve(queries, root, **kwargs):
        calls.append(list(queries))
        (root / "literature").mkdir(exist_ok=True)
        sid = "source-" + hashlib.sha256(b"doi:10.1234/excluded").hexdigest()[:20]
        raw = json.dumps({"status": "ok", "message": {"DOI": "10.1234/excluded", "title": ["Synthetic malformed metadata"]}}).encode()
        metadata_path, metadata_sha = literature._save(root, sid + "-metadata", "json", raw)
        feed = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/1311.3903v1</id></entry></feed>'
        method_path, method_sha = literature._save(root, "arxiv-original-method", "xml", feed)
        return {"sources": [], "warnings": [], "timed_out": status == "incomplete",
                "searches": [{"query": query, "provider": "arXiv", "lookup": "method", "status": "succeeded", "attempted": True,
                              "raw_path": method_path, "sha256": method_sha} for query in queries],
                "pdf_reservations": [{"source_id": "source-" + str(index) * 20, "identity": "doi:10.1234/failed" + str(index),
                                      "route": "provider_pdf", "url": "https://arxiv.org/pdf/2301.00001v1", "pdf_attempted": True}
                                     for index in range(reservations)]}
    service.collector = retrieve
    state = service.prepare_research_questions(identifier, questions())
    return service, runner, identifier, state, calls


def plan(*, action="refine_queries"):
    return {"action": action, "reason": "A narrower synthetic query inspects a different primary body without repeating the failed initial acquisition.",
            "queries": [] if action == "hold" else [{"question_id": "candidate-1",
                "original_query": questions()["candidates"][0]["literature_queries"][0], "query": "software testing",
                "rationale": "Shorter literal keywords reduce compound constraints while preserving the exact provisional fixture question."}]}


def prepared(service, identifier):
    state = service.reserve_question_literature_followup(identifier)
    assert state["question_literature_followup"]["status"] == "planning"
    return service.submit_question_literature_followup(identifier, plan())


def repair_collector(calls, *, mode):
    fixture = repair_fixture([], mode=mode)
    def retrieve(queries, root, **kwargs):
        calls.append({"queries": list(queries), "limit": kwargs["limit"], "remaining": kwargs["pdf_reservation_limit"],
                      "excluded": list(kwargs["excluded_identities"])})
        # The shared old fixture accepts 3/6 as its synthetic generation shape.
        # Record and assert the actual production-facing limit of two separately.
        return fixture(queries, root, **{**kwargs, "limit": 3})
    return retrieve


def unchanged(service, identifier, originals):
    assert all(service.artifact_path(identifier, key).read_bytes() == content for key, content in originals.items())


@pytest.mark.parametrize("initial_status", ["held", "incomplete"])
def test_once_followup_preserves_initials_shared_pdf_and_all_formal_counts(setup, initial_status):
    service, runner, identifier, before, initial_calls = initial(setup, status=initial_status)
    originals = artifact_bytes(service, identifier, before)
    assert before["question_literature_followup_available"] and before["question_literature_followup"] is None
    prepared(service, identifier)
    calls = []; service.collector = repair_collector(calls, mode="ready")
    after = service.collect_question_literature_followup(identifier)
    followup = after["question_literature_followup"]
    assert followup["status"] == "ready" and followup["planningCount"] == followup["collectionCount"] == 1
    assert after["question_preparation"] == before["question_preparation"] and after["research_questions"] == before["research_questions"]
    assert (after["stage"], after["status"], after["code"]) == ("created", "ready", None)
    assert tuple(after[key] for key in COUNTERS) == tuple(before[key] for key in COUNTERS)
    assert calls[0]["remaining"] == 1 and calls[0]["limit"] == 2 and calls[0]["queries"] == ["software testing"]
    assert {"doi:10.1234/failed0", "doi:10.1234/excluded", "arxiv:1311.3903v1"} <= set(calls[0]["excluded"])
    assert len(after["material_manifest"]["literature"]) == 1
    assert after["literature"]["original_question_literature"]["sha256"] == before["artifacts"]["question-literature"]["sha256"]
    assert service.collect_question_literature_followup(identifier)["question_literature_followup"] == followup
    service.prepare_research_questions(identifier, questions()); service.collect_literature(identifier)
    assert len(calls) == len(initial_calls) == 1 and runner.calls == 0
    unchanged(service, identifier, originals)


def test_active_evidence_reaches_literal_reading_selection_and_first_proposal_without_retrieval(setup):
    service, runner, identifier, before, _ = initial(setup)
    originals = artifact_bytes(service, identifier, before)
    prepared(service, identifier)
    calls = []; service.collector = repair_collector(calls, mode="ready")
    state = service.collect_question_literature_followup(identifier)
    source = state["question_literature_followup"]["literature"]["sources"][0]
    material = state["material_manifest"]["literature"][0]
    read = service.read_material(identifier, "evidence", material["name"], limit=32000)
    assert read["sha256"] == source["text_sha256"]
    state = service.select_literature_passages(identifier, [{"source_id": source["id"], "text_sha256": source["text_sha256"],
         "text": source["excerpts"][0], "relevance": "Synthetic literal reference for initial comparison and proposal inheritance only."}])
    selected = selection(source["id"])
    state = service.select_research_question(identifier, selected)
    receipt = json.loads(service.artifact_path(identifier, "question-selection").read_bytes())
    assert receipt["bindings"]["literature_sha256"] == state["artifacts"]["question-literature-followup-pool"]["sha256"]
    value = protocol(); value["literature_queries"] = native.ResearchQuestions.model_validate(questions()).queries()
    service.submit_proposal(identifier, value)
    after = service.collect_literature(identifier)
    assert len(calls) == 1 and runner.calls == 0 and after["proposal_attempt"] == 1
    assert after["literature"]["prepared_question_literature"]["artifact_id"] == "question-literature-followup-pool"
    assert after["question_preparation"]["status"] == "incomplete" and after["question_selection"] == selected
    unchanged(service, identifier, {key: raw for key, raw in originals.items() if key != "literature"})


def test_primary_with_additional_metadata_rows_preserves_collector_limit_contract(setup):
    service, runner, identifier, _, _ = initial(setup)
    prepared(service, identifier)
    calls = []; retrieve = repair_collector(calls, mode="ready")
    def with_metadata(queries, root, **kwargs):
        packet = retrieve(queries, root, **kwargs)
        for index in range(3):
            sid = "metadata-fixture-" + str(index)
            doi = "10.1234/new-metadata-" + str(index)
            raw = json.dumps({"status": "ok", "message": {"DOI": doi, "title": ["Synthetic retained metadata"]}}).encode()
            path, sha = literature._save(root, sid, "json", raw)
            packet["sources"].append({"id": sid, "doi": doi, "title": "Synthetic retained metadata", "scope": "metadata_only",
                                      "raw_path": path, "sha256": sha, "metadata_path": path, "metadata_sha256": sha})
        return packet
    service.collector = with_metadata
    state = service.collect_question_literature_followup(identifier)
    assert state["question_literature_followup"]["status"] == "ready"
    assert len(state["question_literature_followup"]["literature"]["sources"]) == 4 and calls[0]["limit"] == 2
    assert runner.calls == 0


@pytest.mark.parametrize("mode", ["held", "cancelled", "exception", "invalid_proof", "cap", "excluded_alias"])
def test_failed_or_invalid_followup_cannot_activate_or_redispatch(setup, mode):
    service, runner, identifier, before, _ = initial(setup)
    originals = artifact_bytes(service, identifier, before)
    prepared(service, identifier)
    calls = []; service.collector = repair_collector(calls, mode=mode)
    if mode in {"exception", "invalid_proof", "cap", "excluded_alias"}:
        with pytest.raises((ValueError, OSError)): service.collect_question_literature_followup(identifier)
        state = service.status(identifier)
    else:
        state = service.collect_question_literature_followup(identifier)
    followup = state["question_literature_followup"]
    assert followup["status"] == ("held" if mode == "held" else "incomplete") and followup["collectionCount"] == 1
    assert "question-literature-followup-pool" not in state["artifacts"]
    with pytest.raises(WorkflowError) as error: service.select_research_question(identifier, selection("unknown-body"))
    assert error.value.code == "QUESTION_PREPARATION_INCOMPLETE"
    service.collect_question_literature_followup(identifier)
    assert len(calls) == 1 and runner.calls == 0
    unchanged(service, identifier, originals)


def test_planning_hold_and_invalid_keyword_bindings_do_not_dispatch(setup):
    service, runner, identifier, before, _ = initial(setup)
    originals = artifact_bytes(service, identifier, before)
    service.reserve_question_literature_followup(identifier)
    for field, value in [("question_id", "missing"), ("original_query", "an unretained original query"), ("query", "independent software testing oracle")]:
        changed = plan(); changed["queries"][0][field] = value
        with pytest.raises(ValueError): service.submit_question_literature_followup(identifier, changed)
    state = service.submit_question_literature_followup(identifier, plan(action="hold"))
    assert state["question_literature_followup"]["status"] == "held" and state["question_literature_followup"]["collectionCount"] == 0
    with pytest.raises(WorkflowError): service.submit_question_literature_followup(identifier, plan())
    with pytest.raises(WorkflowError): service.collect_question_literature_followup(identifier)
    unchanged(service, identifier, originals); assert runner.calls == 0


@pytest.mark.parametrize("defect", ["pdf_exhausted", "selected", "proposed"])
def test_unavailable_states_cannot_create_another_followup(setup, defect):
    service, runner, identifier, before, _ = initial(setup, reservations=2 if defect == "pdf_exhausted" else 1)
    if defect == "selected": service.select_research_question(identifier, selection(selected=None))
    if defect == "proposed":
        ws = service._workspace(identifier); record = ws.get("workflow", identifier, Workflow)
        # Synthetic eligibility check only; no invalid workflow is persisted.
        record = record.model_copy(update={"stage": "proposed", "proposal_attempt": 1})
        assert not native._question_followup_available(ws, record)
        return
    assert not service.status(identifier)["question_literature_followup_available"]
    with pytest.raises(WorkflowError): service.reserve_question_literature_followup(identifier)
    assert runner.calls == 0


def test_consumed_interrupted_dispatch_finalizes_without_calling_collector(setup):
    service, runner, identifier, _, _ = initial(setup)
    prepared(service, identifier)
    with service._operation(identifier) as (ws, record):
        native._store_question_followup(ws, record, "question-literature-followup-dispatch", {
            "at": "synthetic-interruption", "collectionCount": 1,
            "plan_sha256": record.artifacts["question-literature-followup-plan"].sha256, "queries": ["software testing"]})
        service._save(ws, record)
    service.collector = lambda *args, **kwargs: pytest.fail("An interrupted dispatch must never be replayed")
    state = service.collect_question_literature_followup(identifier)
    assert state["question_literature_followup"]["status"] == "incomplete" and runner.calls == 0


def test_ipc_forwards_only_three_bounded_operations():
    dispatcher = object.__new__(ipc.Dispatcher)
    calls = []
    dispatcher.service = SimpleNamespace(**{name: lambda *args, name=name: calls.append((name, args)) or {"ok": True}
        for name in ("reserve_question_literature_followup", "submit_question_literature_followup", "collect_question_literature_followup")})
    for operation, payload in [("reserve", {}), ("submit", {"value": plan()}), ("collect", {})]:
        method = "workflow." + operation + "QuestionLiteratureFollowup"
        request = {"id": "fixture-" + operation, "method": method, "params": {"researchId": "research-123456789abc", **payload}}
        admitted = ipc.request(json.dumps(request).encode())
        assert dispatcher.execute(admitted["method"], admitted["params"]) == {"ok": True}
        with pytest.raises(ValueError): ipc.request(json.dumps({**request, "params": {**request["params"], "reset": True}}).encode())
    assert len(calls) == 3


def test_actual_resume_preserves_initial_failure_and_admits_unused_or_planned_followup(setup):
    service, runner, identifier, before, calls = initial(setup)
    originals = artifact_bytes(service, identifier, before)
    assert before["resume_kind"] == "preparation"
    resumed = service.resume(identifier)
    assert resumed["resume_kind"] == "preparation" and resumed["status"] == "ready"
    assert resumed["code"] == before["code"] == "QUESTION_PREPARATION_INCOMPLETE"
    planned = prepared(service, identifier)
    assert planned["resume_kind"] == "preparation"
    resumed = service.resume(identifier)
    assert resumed["question_literature_followup"] == planned["question_literature_followup"]
    assert resumed["code"] == before["code"] and resumed["question_preparation"] == before["question_preparation"]
    assert tuple(resumed[key] for key in COUNTERS) == tuple(before[key] for key in COUNTERS)
    unchanged(service, identifier, originals)
    assert len(calls) == 1 and runner.calls == 0


def test_actual_resume_rejects_consumed_planning_hold_and_incomplete_even_after_ready_status(setup):
    service, runner, identifier = setup
    for index, mode in enumerate(("planning", "held", "incomplete")):
        if index:
            identifier = service.create(str(service.home.parent / "input"), "Synthetic independent resume eligibility fixture.")["id"]
        _, _, _, before, initial_calls = initial((service, runner, identifier))
        originals = artifact_bytes(service, identifier, before)
        service.resume(identifier)
        service.reserve_question_literature_followup(identifier)
        followup_calls = []
        if mode == "held": service.submit_question_literature_followup(identifier, plan(action="hold"))
        elif mode == "incomplete":
            service.submit_question_literature_followup(identifier, plan())
            service.collector = repair_collector(followup_calls, mode="exception")
            with pytest.raises(OSError): service.collect_question_literature_followup(identifier)
        state = service.status(identifier)
        assert state["question_literature_followup"]["status"] == mode and state["resume_kind"] is None
        assert state["status"] == "ready" and state["code"] == before["code"]
        with pytest.raises(WorkflowError) as error: service.resume(identifier)
        assert error.value.code == "INVALID_STATE"
        assert tuple(state[key] for key in COUNTERS) == tuple(before[key] for key in COUNTERS)
        unchanged(service, identifier, originals)
        assert len(initial_calls) == 1 and len(followup_calls) == int(mode == "incomplete") and runner.calls == 0

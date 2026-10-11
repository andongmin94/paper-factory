"""Evidence-first preparation fixtures establish no scholarly contribution."""
import copy
import hashlib
import io
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from paper_factory import ipc, workflow as native_workflow
from paper_factory.autonomous.preparation import ResearchQuestions, ResearchQuestionSelection
from paper_factory.workflow import WorkflowError
from paper_factory.workflow_models import Workflow
from test_workflow import collect_arxiv_preprint, protocol, reject_for_redesign, setup


def questions():
    return {"candidates": [{
        "id": "candidate-" + str(index),
        "question": protocol()["question"] if index == 1 else "Which fixture constraints should be compared before declaring a transformation study?",
        "known_basis": "Provisional synthetic basis only; original prior-work findings have not yet been established.",
        "possible_contribution": "A tentative fixture contrast to compare after inspecting retained literature; no novelty is approved.",
        "importance": "This candidate only tests preparation contracts and does not establish scientific importance.",
        "validation_route": "A proposed synthetic protocol route; no measurements, expected results or experiment authority are created.",
        "literature_queries": ["independent software testing oracle"] if index == 1 else ["synthetic primary comparison references"],
    } for index in (1, 2)]}


def selection(source_id=None, *, selected="candidate-1"):
    return {"comparisons": [{
        "id": "candidate-" + str(index),
        "known_result": "A retained synthetic primary-body fixture allows testing evidence binding but establishes no real known result.",
        "proposed_difference": "This provisional comparison exercises question selection only and approves no scientific novelty.",
        "importance": "The fixture comparison does not assert scholarly significance or any favorable research outcome.",
        "validation_feasibility": "The unchanged production snapshot has a simulated runtime contract; no execution has been dispatched.",
        "evidence_sources": [source_id] if source_id else [],
        "unresolved": ["Scientific contribution and closest-work differences remain unproven."],
        "recommended": "candidate-" + str(index) == selected,
    } for index in (1, 2)], "selected_id": selected,
            "reason": "Provisional fixture choice for orchestration tests only; no scientific approval or observed outcome is attested."}


def prepare(service, identifier, *, mode=None):
    calls = []
    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        calls.append({"queries": queries, "limit": limit, "pdf_candidates": pdf_candidates})
        value = collect_arxiv_preprint(queries, root, limit=6, cancel=cancel)
        if mode == "metadata":
            value["sources"][0].update(scope="metadata_only", excerpts=[])
        elif mode in {"cancelled", "timed_out", "rate_limited"}:
            value[mode] = True
        elif mode == "exception":
            raise OSError("Synthetic interrupted collection after complete originals")
        return value
    service.collector = retrieve
    state = service.prepare_research_questions(identifier, questions())
    return state, calls


def artifact_bytes(service, identifier, state):
    return {key: service.artifact_path(identifier, key).read_bytes() for key in state["artifacts"]}


@pytest.mark.parametrize("defect", ["one", "duplicate_id", "duplicate_question", "too_many_queries", "short", "observations"])
def test_question_models_reject_unbounded_ambiguous_or_measurement_shaped_payload(defect):
    value = questions()
    if defect == "one": value["candidates"].pop()
    elif defect == "duplicate_id": value["candidates"][1]["id"] = value["candidates"][0]["id"]
    elif defect == "duplicate_question": value["candidates"][1]["question"] = value["candidates"][0]["question"]
    elif defect == "short": value["candidates"][0]["known_basis"] = " " * 30
    elif defect == "observations": value["candidates"][0]["observations"] = [{"value": 0}]
    else:
        value["candidates"].append({**copy.deepcopy(value["candidates"][0]), "id": "candidate-3", "question": "A third distinct synthetic question for bounded candidate comparison?"})
        for index, candidate in enumerate(value["candidates"]):
            candidate["literature_queries"] = [f"different synthetic query {index}-{number}" for number in range(3)]
    with pytest.raises(ValidationError): ResearchQuestions.model_validate(value)


@pytest.mark.parametrize("defect", ["multiple", "missing_recommendation", "unknown_selected", "coerced_boolean"])
def test_comparison_models_reject_inconsistent_or_coerced_recommendations(defect):
    value = selection("fixture-primary")
    if defect == "multiple": value["comparisons"][1]["recommended"] = True
    elif defect == "missing_recommendation": value["comparisons"][0]["recommended"] = False
    elif defect == "unknown_selected": value["selected_id"] = "candidate-other"
    else: value["comparisons"][0]["recommended"] = "true"
    with pytest.raises(ValidationError): ResearchQuestionSelection.model_validate(value)


def test_preparation_freezes_question_source_goal_and_pool_without_scientific_attempts(setup):
    service, runner, identifier = setup
    before = service.status(identifier)
    state, calls = prepare(service, identifier)
    assert state["research_questions"] == questions() and state["question_selection"] is None
    assert state["question_preparation"]["status"] == "ready"
    assert calls == [{"queries": ResearchQuestions.model_validate(questions()).queries(), "limit": 6, "pdf_candidates": None}]
    assert (state["stage"], state["proposal_attempt"], state["study_literature_attempt"], state["execution_attempt"], state["draft_attempt"]) == ("created", 0, 0, 0, 0)
    assert state["material_manifest"]["source"] == before["material_manifest"]["source"] and state["material_manifest"]["literature"]
    assert state["artifacts"]["question-literature"] == {**state["artifacts"]["literature"], "id": "question-literature"}
    assert runner.calls == 0


def test_identical_preparation_and_created_collect_retry_never_repeat_network(setup):
    service, runner, identifier = setup
    state, calls = prepare(service, identifier)
    originals = artifact_bytes(service, identifier, state)
    repeated = service.prepare_research_questions(identifier, questions())
    service.collect_literature(identifier)
    assert len(calls) == 1 and repeated["artifacts"] == state["artifacts"]
    assert artifact_bytes(service, identifier, state) == originals and runner.calls == 0


def test_changed_questions_cannot_replace_frozen_preparation(setup):
    service, runner, identifier = setup
    state, calls = prepare(service, identifier)
    value = questions(); value["candidates"][0]["question"] += " A changed target?"
    with pytest.raises(WorkflowError) as failure:
        service.prepare_research_questions(identifier, value)
    assert failure.value.code == "QUESTION_PREPARATION_CONFLICT" and len(calls) == 1
    assert service.status(identifier)["research_questions"] == state["research_questions"]


def test_selection_requires_complete_exact_candidates_and_verified_primary_references(setup):
    service, runner, identifier = setup
    with pytest.raises(WorkflowError) as unprepared:
        service.select_research_question(identifier, selection())
    assert unprepared.value.code == "QUESTION_PREPARATION_REQUIRED"
    state, _ = prepare(service, identifier)
    source_id = state["literature"]["sources"][0]["id"]
    for value in (selection("not-a-retained-source"), selection(),
                  {**selection(source_id), "comparisons": [selection(source_id)["comparisons"][0], {**selection(source_id)["comparisons"][1], "id": "candidate-other"}]}):
        with pytest.raises(WorkflowError) as invalid:
            service.select_research_question(identifier, value)
        assert invalid.value.code == "QUESTION_SELECTION_INVALID"
    assert "question-selection" not in service.status(identifier)["artifacts"] and runner.calls == 0


def test_frozen_selection_is_idempotent_and_bindings_precede_first_proposal(setup):
    service, runner, identifier = setup
    state, calls = prepare(service, identifier)
    selected = selection(state["literature"]["sources"][0]["id"])
    after = service.select_research_question(identifier, selected)
    repeated = service.select_research_question(identifier, selected)
    assert after["question_selection"] == selected and after["artifacts"] == repeated["artifacts"]
    receipt = json.loads(service.artifact_path(identifier, "question-selection").read_bytes())
    assert receipt["bindings"]["questions_sha256"] == state["artifacts"]["research-questions"]["sha256"]
    assert receipt["bindings"]["literature_sha256"] == state["artifacts"]["question-literature"]["sha256"]
    changed = selection(state["literature"]["sources"][0]["id"], selected="candidate-2")
    with pytest.raises(WorkflowError) as conflict: service.select_research_question(identifier, changed)
    assert conflict.value.code == "QUESTION_PREPARATION_CONFLICT" and len(calls) == 1 and runner.calls == 0


def test_first_proposal_requires_selection_exact_question_and_all_prepared_queries(setup):
    service, runner, identifier = setup
    state, calls = prepare(service, identifier)
    with pytest.raises(WorkflowError) as missing: service.submit_proposal(identifier, protocol())
    assert missing.value.code == "QUESTION_SELECTION_REQUIRED"
    service.select_research_question(identifier, selection(state["literature"]["sources"][0]["id"]))
    for question, queries in [(protocol()["question"] + " different?", ResearchQuestions.model_validate(questions()).queries()),
                              (protocol()["question"], protocol()["literature_queries"])]:
        plan = protocol(); plan.update(question=question, literature_queries=queries)
        with pytest.raises(WorkflowError) as mismatch: service.submit_proposal(identifier, plan)
        assert mismatch.value.code == "QUESTION_PROPOSAL_MISMATCH"
    assert service.status(identifier)["proposal_attempt"] == 0 and len(calls) == 1 and runner.calls == 0


def test_first_formal_literature_reuses_prepared_pool_and_preserves_original_history(setup):
    service, runner, identifier = setup
    state, calls = prepare(service, identifier)
    originals = artifact_bytes(service, identifier, state)
    service.select_research_question(identifier, selection(state["literature"]["sources"][0]["id"]))
    plan = protocol(); plan["literature_queries"] = ResearchQuestions.model_validate(questions()).queries()
    submitted = service.submit_proposal(identifier, plan)
    history = "literature-history-" + state["artifacts"]["literature"]["sha256"]
    assert submitted["artifacts"][history]["sha256"] == state["artifacts"]["literature"]["sha256"]
    collected = service.collect_literature(identifier)
    assert len(calls) == 1 and collected["proposal_attempt"] == 1 and collected["execution_attempt"] == 0
    assert collected["literature"]["prepared_question_literature"]["sha256"] == state["artifacts"]["question-literature"]["sha256"]
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in originals.items() if key != "literature")
    assert runner.calls == 0


def test_first_formal_literature_retrieves_only_concrete_new_gap_queries(setup):
    service, runner, identifier = setup
    state, calls = prepare(service, identifier)
    service.select_research_question(identifier, selection(state["literature"]["sources"][0]["id"]))
    plan = protocol(); plan["literature_queries"] = ResearchQuestions.model_validate(questions()).queries() + ["a distinct concrete unresolved primary method"]
    service.submit_proposal(identifier, plan)
    service.collect_literature(identifier)
    assert calls[-1] == {"queries": [plan["literature_queries"][-1]], "limit": 5, "pdf_candidates": []}
    assert len(calls) == 2 and runner.calls == 0


@pytest.mark.parametrize("mode", ["metadata", "cancelled", "timed_out", "rate_limited"])
def test_no_primary_or_incomplete_pool_can_hold_without_inventing_selection(setup, mode):
    service, runner, identifier = setup
    state, calls = prepare(service, identifier, mode=mode)
    assert state["question_preparation"]["status"] == ("held" if mode == "metadata" else "incomplete")
    assert state["status"] == "blocked" and state["resume_kind"] is None
    assert state["code"] == ("QUESTION_PREPARATION_NO_PRIMARY" if mode == "metadata" else "QUESTION_PREPARATION_INCOMPLETE")
    original = artifact_bytes(service, identifier, state)
    repeated = service.prepare_research_questions(identifier, questions())
    assert repeated["artifacts"] == state["artifacts"] and artifact_bytes(service, identifier, repeated) == original
    with pytest.raises(WorkflowError) as unsupported:
        service.select_research_question(identifier, selection(state["literature"]["sources"][0]["id"]))
    assert unsupported.value.code == "QUESTION_PREPARATION_INCOMPLETE"
    value = selection(selected=None)
    held = service.select_research_question(identifier, value)
    assert held["question_selection"]["selected_id"] is None and held["code"] == "RESEARCH_QUESTION_HELD"
    with pytest.raises(WorkflowError) as blocked: service.submit_proposal(identifier, protocol())
    assert blocked.value.code == "RESEARCH_QUESTION_HELD"
    service.prepare_research_questions(identifier, questions())
    assert len(calls) == 1 and held["proposal_attempt"] == held["execution_attempt"] == 0 and runner.calls == 0


def test_collector_exception_preserves_completed_files_and_never_redispatches(setup):
    service, runner, identifier = setup
    calls = []
    def retrieve(queries, root, **kwargs):
        calls.append(queries)
        collect_arxiv_preprint(queries, root, limit=6, cancel=kwargs["cancel"])
        raise OSError("Synthetic completed originals then failed transport")
    service.collector = retrieve
    with pytest.raises(OSError): service.prepare_research_questions(identifier, questions())
    state = service.status(identifier)
    assert state["question_preparation"]["status"] == "incomplete" and state["code"] == "QUESTION_PREPARATION_INTERRUPTED"
    assert "question-collection-dispatch" in state["artifacts"]
    assert any(key.startswith("literature-") for key in state["artifacts"])
    original = artifact_bytes(service, identifier, state)
    service.prepare_research_questions(identifier, questions()); service.collect_literature(identifier)
    assert len(calls) == 1 and artifact_bytes(service, identifier, state) == original and runner.calls == 0


def test_crash_dispatch_recovery_freezes_only_completed_retrieval_originals_without_redispatch(setup, monkeypatch):
    service, runner, identifier = setup
    # Reproduce the persisted checkpoint before an abrupt process exit, so no
    # collector finally/exception handler has registered the completed files.
    with monkeypatch.context() as patch:
        patch.setattr(service, "collect_literature", lambda _: {})
        service.prepare_research_questions(identifier, questions())
    ws = service._workspace(identifier)
    record = ws.get("workflow", identifier, Workflow)
    dispatch = ws.path("research/question-collection-dispatch.json")
    native_workflow.write_json(dispatch, {
        "bindings": native_workflow._question_bindings(ws, record), "scope": native_workflow.QUESTION_SCOPE,
        "questions_sha256": record.artifacts["research-questions"].sha256,
        "queries": ResearchQuestions.model_validate(questions()).queries(),
    })
    native_workflow._freeze(ws, record, "question-collection-dispatch", dispatch)
    service._save(ws, record)
    originals = {"literature/crash-search.json": b'{"synthetic":true}',
                 "literature/crash-source.pdf": b"%PDF-1.7\nSynthetic interrupted original only",
                 "literature/crash-body.txt": b"Retained original body bytes; no scholarly result is asserted."}
    for relative, content in originals.items():
        path = ws.path("research/" + relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    uncommitted = ws.path("research/literature-evidence.json")
    uncommitted.write_bytes(b'{"sources":[],"uncommitted":true}')
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("A retained preliminary dispatch must not be repeated")
    service.collector = forbidden

    state = service.prepare_research_questions(identifier, questions())
    assert state["question_preparation"]["status"] == "incomplete"
    assert state["status"] == "blocked" and state["code"] == "QUESTION_PREPARATION_INTERRUPTED" and state["resume_kind"] is None
    assert state.get("literature") is None and "question-literature" not in state["artifacts"]
    assert not any(row.path == "research/literature-evidence.json" for row in ws.get("workflow", identifier, Workflow).artifacts.values())
    for relative, content in originals.items():
        entries = [row for row in ws.get("workflow", identifier, Workflow).artifacts.values() if row.path == "research/" + relative]
        assert len(entries) == 1 and entries[0].sha256 == hashlib.sha256(content).hexdigest() and entries[0].size == len(content)
    frozen = artifact_bytes(service, identifier, state)
    service.prepare_research_questions(identifier, questions()); service.collect_literature(identifier)
    assert artifact_bytes(service, identifier, service.status(identifier)) == frozen
    assert calls == [] and runner.calls == 0 and state["proposal_attempt"] == state["study_literature_attempt"] == state["execution_attempt"] == 0
    ws.path("research/literature/crash-body.txt").write_bytes(b"Changed retained interrupted original")
    with pytest.raises(WorkflowError) as altered:
        service.prepare_research_questions(identifier, questions())
    assert altered.value.code == "ARTIFACT_CHANGED" and calls == [] and runner.calls == 0


def test_raw_or_question_tamper_blocks_selection_without_new_proposal(setup):
    service, runner, identifier = setup
    state, calls = prepare(service, identifier)
    source = state["literature"]["sources"][0]
    body = service._workspace(identifier).path("research") / source["text_path"]
    body.write_bytes(body.read_bytes() + b"Changed original")
    with pytest.raises(WorkflowError) as altered:
        service.select_research_question(identifier, selection(source["id"]))
    assert altered.value.code == "ARTIFACT_CHANGED" and len(calls) == 1 and runner.calls == 0


def test_question_comparison_freezes_original_literal_reading_receipt(setup):
    service, runner, identifier = setup
    state, _ = prepare(service, identifier)
    source = state["literature"]["sources"][0]
    read = service.select_literature_passages(identifier, [{"source_id": source["id"], "text_sha256": source["text_sha256"],
        "text": source["excerpts"][0], "relevance": "Synthetic literal body passage retained for provisional question comparison only."}])
    service.select_research_question(identifier, selection(source["id"]))
    receipt = json.loads(service.artifact_path(identifier, "question-selection").read_bytes())
    reading = receipt["bindings"]["reading"]
    assert reading["artifact_id"].startswith("literature-passages-")
    assert reading["sha256"] == read["artifacts"]["literature-reading"]["sha256"]
    plan = protocol(); plan["literature_queries"] = ResearchQuestions.model_validate(questions()).queries()
    service.submit_proposal(identifier, plan)
    assert service.artifact_path(identifier, reading["artifact_id"]).read_bytes() == service.artifact_path(identifier, "literature-reading").read_bytes()
    assert runner.calls == 0


def test_question_goal_binding_cannot_be_relabelled_after_preparation(setup):
    service, runner, identifier = setup
    state, calls = prepare(service, identifier)
    ws = service._workspace(identifier)
    record = ws.get("workflow", identifier, Workflow)
    record.goal = "A different retained goal must not inherit the same provisional question selection."
    ws.save("workflow", record)
    with pytest.raises(WorkflowError) as conflict:
        service.select_research_question(identifier, selection(state["literature"]["sources"][0]["id"]))
    assert conflict.value.code == "QUESTION_PREPARATION_CONFLICT" and len(calls) == 1 and runner.calls == 0


def test_unprepared_historical_fixture_first_submission_is_preserved(setup):
    service, runner, identifier = setup
    state = service.submit_proposal(identifier, protocol())
    assert state["proposal_attempt"] == 1 and state["research_questions"] is None and state["question_selection"] is None
    with pytest.raises(WorkflowError): service.prepare_research_questions(identifier, questions())
    assert runner.calls == 0


def test_verified_created_successor_can_prepare_without_changing_parent_science(setup):
    service, runner, identifier = setup
    rejected = reject_for_redesign(service, identifier)
    parent_bytes = artifact_bytes(service, identifier, rejected)
    child = service.redesign_study(identifier)
    before_parent = service.status(identifier)
    state, calls = prepare(service, child["id"])
    after_parent = service.status(identifier)
    assert state["parent_research_id"] == state["root_research_id"] == identifier and state["redesign_attempt"] == 1
    assert state["question_preparation"]["status"] == "ready" and state["prior_study"] == child["prior_study"]
    service.select_research_question(child["id"], selection(state["literature"]["sources"][0]["id"]))
    assert state["proposal_attempt"] == state["execution_attempt"] == 0 and len(calls) == 1
    assert after_parent["proposal_attempt"] == before_parent["proposal_attempt"]
    assert after_parent["execution_attempt"] == before_parent["execution_attempt"] == runner.calls == 1
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in parent_bytes.items())


@pytest.mark.parametrize("method", ["workflow.prepareResearchQuestions", "workflow.selectResearchQuestion"])
def test_native_ipc_accepts_only_explicit_value_request_shapes(method):
    params = {"researchId": "research-012345abcdef", "value": questions()}
    request = {"id": "question-request", "method": method, "params": params}
    assert ipc.request(json.dumps(request).encode())["params"] == params
    with pytest.raises(ValueError):
        ipc.request(json.dumps({**request, "params": {**params, "resetCounts": True}}).encode())


def test_ipc_dispatches_both_question_apis_into_native_preparation(setup):
    service, runner, identifier = setup
    service.collector = collect_arxiv_preprint
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), io.BytesIO())
    try:
        prepared = dispatcher.execute("workflow.prepareResearchQuestions", {"researchId": identifier, "value": questions()})
        selected = dispatcher.execute("workflow.selectResearchQuestion", {"researchId": identifier,
            "value": selection(prepared["literature"]["sources"][0]["id"])})
        assert selected["question_selection"]["selected_id"] == "candidate-1"
        assert selected["proposal_attempt"] == selected["execution_attempt"] == 0 and runner.calls == 0
    finally:
        dispatcher._pool.shutdown(wait=True)

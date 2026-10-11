"""Synthetic reframing contracts never attest actual scholarly contribution."""

import copy
import json

import pytest
from pydantic import ValidationError

from paper_factory import ipc
from paper_factory.autonomous.preparation import RedesignQuestionReframing, PriorQuestionDifference
from paper_factory.workflow import WorkflowError, QUESTION_REFRAMING_PATHS, _search_repair_members
from paper_factory.workflow_models import Workflow
from test_planned_claim_projection import COUNTERS
from test_preexecution_redesign import attach_validation, review as preparation_review
from test_redesign_question_evidence import prepared_hold, collector, basis
from test_redesign_question_preparation import assert_originals, frozen_originals, workflow_comparison
from test_study_repair import successor_repair
from test_workflow import setup


def held_new_pool(setup, *, search_repair=False):
    calls = []
    if search_repair:
        from test_redesign_question_search_repair import diagnosed, repair_collector, reserve_and_plan
        service, runner, identifier, _, routes, proposed = diagnosed(setup)
        reserve_and_plan(service, identifier, routes)
        service.collector = repair_collector(calls, mode="ready")
        state = service.collect_redesign_question_search_repair(identifier)
    else:
        service, runner, identifier, _, routes, proposed = prepared_hold(setup)
        service.collector = collector(calls)
        state = service.collect_redesign_question_evidence(identifier)
    state = service.reassess_redesign_question(identifier, workflow_comparison(state, routes, selected=None))
    envelope = {"action": "propose", "reason": "Synthetic new questions inspect the changed pool without asserting actual merit.",
                "candidates": copy.deepcopy(routes["candidates"])}
    for index, item in enumerate(envelope["candidates"]):
        item.update(id=f"new-route-{index + 1}",
                    question=f"Which materially different synthetic boundary comparison {index + 1} is justified?",
                    literature_queries=[f"synthetic new boundary comparison method {index + 1}"])
    return service, runner, identifier, state, routes, envelope, proposed, calls


def comparison(state, routes, envelope, *, selected="new-route-1"):
    value = workflow_comparison(state, {"candidates": envelope["candidates"]}, selected=None)
    value["selected_id"] = selected
    for item in value["comparisons"]:
        item["recommended"] = item["id"] == selected
        item["prior_questions"] = [{"question_id": old["id"],
            "scientific_difference": "This synthetic distinct-question reasoning is a fixture, not proof of new knowledge."}
            for old in routes["candidates"]]
    return value


def test_once_reframing_preserves_all_originals_and_counts_and_does_not_collect(setup):
    service, runner, identifier, before, routes, envelope, _, calls = held_new_pool(setup)
    original = frozen_originals(service, identifier, before)
    old_basis = basis(service, identifier)
    assert before["redesign_question_reframing_available"]
    reserved = service.reserve_redesign_question_reframing(identifier)
    assert reserved["redesign_question_reframing"]["status"] == "planning"
    assert reserved["redesign_question_reframing"]["planningCount"] == 1
    assert not reserved["redesign_question_reframing_available"] and not reserved["preparation_redesign_available"]
    with pytest.raises(WorkflowError, match="already consumed"):
        service.reserve_redesign_question_reframing(identifier)
    state = service.submit_redesign_question_reframing(identifier, envelope)
    assert state["redesign_question_reframing"]["status"] == "proposed"
    assert state["preparation_redesign_available"]
    state = service.reserve_redesign_question_reframing_selection(identifier)
    assert state["redesign_question_reframing"]["status"] == "reviewing"
    assert state["redesign_question_reframing"]["comparisonCount"] == 1
    assert not state["preparation_redesign_available"]
    value = comparison(state, routes, envelope)
    state = service.select_redesign_question_reframing(identifier, value)
    assert state["redesign_question_reframing"]["status"] == "ready"
    assert state["redesign_question_reframing"]["selection"] == value
    assert state["redesign_question_selection"] == before["redesign_question_selection"]
    assert state["redesign_question_reassessment"] == before["redesign_question_reassessment"]
    assert tuple(state[key] for key in COUNTERS) == tuple(before[key] for key in COUNTERS)
    assert basis(service, identifier) == old_basis
    assert_originals(service, identifier, original)
    assert len(calls) == 1 and runner.calls == 0
    with pytest.raises(WorkflowError):
        service.reserve_redesign_question_reframing_selection(identifier)
    changed = copy.deepcopy(value); changed["reason"] += " A new favorable judgment cannot replace this comparison."
    with pytest.raises(WorkflowError):
        service.select_redesign_question_reframing(identifier, changed)
    assert service.select_redesign_question_reframing(identifier, value)["redesign_question_reframing"]["selection"] == value


@pytest.mark.parametrize("where", ["planning", "comparison"])
def test_explicit_new_hold_removes_futile_action_and_never_selects_or_resets(setup, where):
    service, runner, identifier, before, routes, envelope, _, calls = held_new_pool(setup)
    service.reserve_redesign_question_reframing(identifier)
    if where == "planning":
        envelope = {"action": "hold", "reason": "The synthetic retained pool cannot justify a distinct question design.", "candidates": []}
        state = service.submit_redesign_question_reframing(identifier, envelope)
    else:
        state = service.submit_redesign_question_reframing(identifier, envelope)
        state = service.reserve_redesign_question_reframing_selection(identifier)
        state = service.select_redesign_question_reframing(identifier, comparison(state, routes, envelope, selected=None))
    assert state["redesign_question_reframing"]["status"] == "held"
    assert not state["preparation_redesign_available"] and not state["redesign_question_reframing_available"]
    assert state["redesign_candidate"] is None and state["followup_research_id"] is None
    assert tuple(state[key] for key in COUNTERS) == tuple(before[key] for key in COUNTERS)
    assert runner.calls == 0 and len(calls) == 1


@pytest.mark.parametrize("defect", ["old_id", "old_question", "old_question_case", "old_protocol", "old_requirement", "old_route", "unknown_source", "generation_blocker"])
def test_new_round_cannot_replace_old_science_or_omit_independent_coverage(setup, defect):
    service, _, identifier, _, routes, envelope, _, _ = held_new_pool(setup)
    service.reserve_redesign_question_reframing(identifier)
    if defect in {"old_id", "old_question", "old_question_case"}:
        if defect == "old_id": envelope["candidates"][0]["id"] = routes["candidates"][0]["id"]
        else: envelope["candidates"][0]["question"] = routes["candidates"][0]["question"].upper() if defect.endswith("case") else routes["candidates"][0]["question"]
        with pytest.raises(WorkflowError): service.submit_redesign_question_reframing(identifier, envelope)
        return
    state = service.submit_redesign_question_reframing(identifier, envelope)
    state = service.reserve_redesign_question_reframing_selection(identifier)
    value = comparison(state, routes, envelope)
    item = value["comparisons"][0]
    if defect == "old_protocol": item["prior_proposals"].pop()
    elif defect == "old_requirement": item["criterion_repairs"][0]["required_change"] += " Changed old science."
    elif defect == "old_route": item["prior_questions"][0]["question_id"] = "unknown-old-route"
    elif defect == "unknown_source": item["evidence_sources"] = ["a-body-not-retained"]
    else: item["generation_blockers"] = ["The synthetic independent measurement prerequisite remains undefined."]
    with pytest.raises((WorkflowError, ValidationError)):
        service.select_redesign_question_reframing(identifier, value)
    assert "redesign-question-reframing-selection" not in service.status(identifier)["artifacts"]


@pytest.mark.parametrize("search_repair", [False, True])
def test_selected_new_question_reaches_existing_candidate_review_and_inherited_child_proof(setup, search_repair):
    service, runner, identifier, before, routes, envelope, proposed, calls = held_new_pool(setup, search_repair=search_repair)
    originals = frozen_originals(service, identifier, before)
    service.reserve_redesign_question_reframing(identifier)
    state = service.submit_redesign_question_reframing(identifier, envelope)
    state = service.reserve_redesign_question_reframing_selection(identifier)
    state = service.select_redesign_question_reframing(identifier, comparison(state, routes, envelope))
    proposed = attach_validation(service, identifier, proposed)
    proposed["question"] = routes["candidates"][0]["question"]
    with pytest.raises(WorkflowError) as wrong_question:
        service.submit_redesign_proposal(identifier, proposed, successor_repair(state["study_remediation"]))
    assert wrong_question.value.code == "QUESTION_SELECTION_CONFLICT"
    proposed["question"] = envelope["candidates"][0]["question"]
    proposed["literature_queries"] = envelope["candidates"][0]["literature_queries"]
    state = service.submit_redesign_proposal(identifier, proposed, successor_repair(state["study_remediation"]))
    assert state["redesign_candidate"] == proposed
    service.submit_redesign_review(identifier, preparation_review())
    child = service.redesign_study(identifier)
    origin = json.loads(service.artifact_path(child["id"], "redesign-origin").read_bytes())
    for key in QUESTION_REFRAMING_PATHS:
        assert key in origin["parent_evidence"]
        assert any(name.endswith("-" + key) for name in child["artifacts"])
    if search_repair:
        ws = service._workspace(identifier)
        for key in _search_repair_members(ws, ws.latest("workflow", Workflow)):
            assert origin["parent_evidence"][key] == {name: before["artifacts"][key][name] for name in ("sha256", "size")}
    assert_originals(service, identifier, originals)
    assert child["proposal_attempt"] == 1 and child["execution_attempt"] == child["draft_attempt"] == 0
    assert runner.calls == 0 and len(calls) == 1


def test_reframing_requires_complete_ready_changed_pool_and_two_real_nulls(setup):
    service, _, identifier, _, routes, _ = prepared_hold(setup)
    assert not service.status(identifier)["redesign_question_reframing_available"]
    with pytest.raises(WorkflowError): service.reserve_redesign_question_reframing(identifier)
    service.collector = collector([])
    state = service.collect_redesign_question_evidence(identifier)
    assert not state["redesign_question_reframing_available"]
    state = service.reassess_redesign_question(identifier, workflow_comparison(state, routes))
    assert not state["redesign_question_reframing_available"]
    with pytest.raises(WorkflowError): service.reserve_redesign_question_reframing(identifier)


def test_reframing_scope_still_enforces_original_descendant_cap(setup):
    service, _, identifier, _, _, _, _, _ = held_new_pool(setup)
    ws = service._workspace(identifier)
    record = ws.latest("workflow", Workflow)
    # Stub only the existing eligibility boundary to verify there is no cap bypass;
    # no synthetic invalid lineage or new study is persisted.
    record = record.model_copy(update={"redesign_attempt": 2})
    with pytest.raises(WorkflowError) as error:
        service._question_reframing_bindings(ws, record)
    assert error.value.code == "STUDY_REDESIGN_NOT_ALLOWED"


@pytest.mark.parametrize("action,count", [("hold", 1), ("propose", 0), ("propose", 1)])
def test_reframing_envelope_cannot_mix_hold_and_candidates(action, count):
    with pytest.raises(ValidationError):
        RedesignQuestionReframing.model_validate({"action": action, "reason": "Synthetic envelope only tests an explicit coherent hold or question batch.",
            "candidates": [{} for _ in range(count)]})


@pytest.mark.parametrize("value", [" " * 24, "a" * 24 + "\x00"])
def test_each_old_question_difference_requires_substantive_printable_reason(value):
    with pytest.raises(ValidationError):
        PriorQuestionDifference(question_id="old-route", scientific_difference=value)


def test_four_new_apis_reach_strict_ipc_allowlist_with_exact_parameters():
    for method in ("reserveRedesignQuestionReframing", "submitRedesignQuestionReframing",
                   "reserveRedesignQuestionReframingSelection", "selectRedesignQuestionReframing"):
        params = {"researchId": "research-aabbccddeeff"}
        if method.startswith(("submit", "select")):
            params["value"] = {"fixture": "Shape dispatch only; never real scientific evidence"}
        payload = {"id": "fixture", "method": "workflow." + method, "params": params}
        assert ipc.request(json.dumps(payload).encode())["params"] == params
        payload["params"] = {**params, "resetAttempts": True}
        with pytest.raises(ValueError): ipc.request(json.dumps(payload).encode())

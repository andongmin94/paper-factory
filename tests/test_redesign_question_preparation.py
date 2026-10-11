"""Synthetic route comparisons test preservation contracts, not scholarly merit."""

import copy
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from paper_factory.autonomous.preparation import (
    ResearchQuestions,
    RedesignQuestionSelection,
    validate_redesign_question_selection,
)
from paper_factory.workflow import WorkflowError, WorkflowService, _json_digest
from paper_factory.workflow_models import Workflow
from test_planned_claim_projection import COUNTERS
from test_preexecution_redesign import attach_validation, review as preparation_review
from test_redesign_admission_feedback import held
from test_workflow import setup


PROTOCOL_IDS = ["proposal-1", "prior-study-research-fixture-proposal-2"]
REQUIRED_CHANGES = {
    "contribution": "Identify a substantive additional finding beyond the retained synthetic protocol.",
    "significance": "Explain how the prospective answer can change a justified useful decision.",
}
PRIMARY_IDS = {"fixture-primary-body"}


def questions():
    return ResearchQuestions.model_validate({"candidates": [{
        "id": f"route-{index}",
        "question": f"Which distinct synthetic comparison route {index} merits a full protocol?",
        "known_basis": "This fixture describes provisional reasoning and establishes no known scientific result.",
        "possible_contribution": "A prospective fixture contrast only; no novelty or observed finding is asserted.",
        "importance": "A synthetic decision rationale for contract tests, not evidence of scholarly importance.",
        "validation_route": "A prospective independently reviewed protocol; this record cannot authorize execution.",
        "literature_queries": [f"synthetic distinct comparison method {index}"],
    } for index in (1, 2)]})


def selection(*, selected="route-1"):
    return {"comparisons": [{
        "id": f"route-{index}",
        "known_result": "The synthetic primary-body identifier only tests retained evidence binding.",
        "proposed_difference": "This provisional fixture contrasts questions rather than changing scientific outcomes.",
        "importance": "The fixture does not establish scholarly significance or any actual product benefit.",
        "validation_feasibility": "A possible supported validation route remains subject to every fresh scientific gate.",
        "evidence_sources": ["fixture-primary-body"],
        "unresolved": ["No new study observations or fresh scientific approvals exist."],
        "recommended": selected == f"route-{index}",
        "prior_proposals": [{"artifact_id": identifier,
                             "scientific_difference": "A synthetic question distinction, not proof of a worthwhile scientific contribution."}
                            for identifier in PROTOCOL_IDS],
        "criterion_repairs": [{"criterion": criterion, "required_change": requirement,
                               "proposed_change": "A prospective substantive fixture change awaiting an independent preparation review."}
                              for criterion, requirement in REQUIRED_CHANGES.items()],
        "generation_blockers": [],
    } for index in (1, 2)], "selected_id": selected,
            "reason": "This provisional synthetic route selection neither resolves scientific criteria nor authorizes execution."}


def validate(value, *, routes=None, protocols=None, requirements=None, primary=None):
    parsed = RedesignQuestionSelection.model_validate(value)
    validate_redesign_question_selection(
        routes or questions(), parsed, PROTOCOL_IDS if protocols is None else protocols,
        REQUIRED_CHANGES if requirements is None else requirements,
        PRIMARY_IDS if primary is None else primary)
    return parsed


def test_selected_route_preserves_prospective_uncertainty_without_claiming_approval():
    value = selection()
    original = copy.deepcopy(value)
    parsed = validate(value)
    assert parsed.selected_id == "route-1"
    assert parsed.comparisons[0].unresolved == ["No new study observations or fresh scientific approvals exist."]
    assert parsed.model_dump(mode="json") == original and value == original


def test_explicit_hold_retains_missing_generation_prerequisites_without_evidence_invention():
    value = selection(selected=None)
    for item in value["comparisons"]:
        item["generation_blockers"] = ["Required directly related primary body has not been retained."]
        item["evidence_sources"] = []
    original = copy.deepcopy(value)
    parsed = validate(value, primary=set())
    assert parsed.selected_id is None
    assert all(item.generation_blockers for item in parsed.comparisons)
    assert parsed.model_dump(mode="json") == original and value == original


def test_candidate_generation_cannot_be_recommended_with_an_unmet_prerequisite():
    value = selection()
    value["comparisons"][0]["generation_blockers"] = ["An independent validation definition is missing."]
    with pytest.raises(ValidationError, match="unmet prerequisite"):
        validate(value)


@pytest.mark.parametrize("defect", ["missing", "unknown", "duplicate"])
def test_each_route_must_compare_every_exact_parent_and_ancestor_protocol(defect):
    value = selection()
    retained = value["comparisons"][1]["prior_proposals"]
    if defect == "missing": retained.pop()
    elif defect == "unknown": retained[1]["artifact_id"] = "an-unretained-protocol"
    else: retained[1] = copy.deepcopy(retained[0])
    with pytest.raises((ValueError, ValidationError)):
        validate(value)


@pytest.mark.parametrize("defect", ["missing", "extra", "duplicate", "paraphrase", "whitespace"])
def test_each_route_must_address_all_literal_rejected_criterion_requirements(defect):
    value = selection()
    repairs = value["comparisons"][0]["criterion_repairs"]
    if defect == "missing": repairs.pop()
    elif defect == "extra": repairs.append({**copy.deepcopy(repairs[0]), "criterion": "validation"})
    elif defect == "duplicate": repairs[1] = copy.deepcopy(repairs[0])
    elif defect == "whitespace": repairs[0]["required_change"] += " "
    else: repairs[0]["required_change"] = "A changed paraphrase cannot replace the frozen reviewer requirement."
    with pytest.raises((ValueError, ValidationError)):
        validate(value)


@pytest.mark.parametrize("defect", ["unknown_source", "abstract_only", "no_selected_evidence"])
def test_selection_needs_current_verified_primary_body_references(defect):
    value = selection()
    value["comparisons"][0]["evidence_sources"] = [] if defect == "no_selected_evidence" else [
        "fixture-metadata-abstract" if defect == "abstract_only" else "unretained-primary-source"]
    with pytest.raises(ValueError):
        validate(value)


def test_unselected_route_cannot_forge_a_primary_body_reference():
    value = selection()
    value["comparisons"][1]["evidence_sources"] = ["unretained-primary-source"]
    with pytest.raises(ValueError, match="current verified primary"):
        validate(value)


def test_selection_cannot_omit_or_substitute_a_frozen_question():
    value = selection()
    value["comparisons"][1]["id"] = "route-other"
    with pytest.raises(ValueError, match="every frozen research route"):
        validate(value)


@pytest.mark.parametrize("defect", ["empty_protocol_context", "duplicate_protocol_context", "empty_requirements"])
def test_context_coverage_cannot_be_silently_weakened(defect):
    context = {"protocols": []} if defect == "empty_protocol_context" else {
        "protocols": [PROTOCOL_IDS[0], PROTOCOL_IDS[0]]} if defect == "duplicate_protocol_context" else {"requirements": {}}
    with pytest.raises(ValueError):
        validate(selection(), **context)


@pytest.mark.parametrize("field", ["scientific_difference", "proposed_change"])
def test_additional_route_reasoning_is_bounded_without_truncation(field):
    value = selection()
    path = "prior_proposals" if field == "scientific_difference" else "criterion_repairs"
    value["comparisons"][0][path][0][field] = "x" * 2001
    with pytest.raises(ValidationError):
        validate(value)


@pytest.mark.parametrize("defect", ["duplicate_blockers", "control_blocker", "invented_observations", "invented_approval"])
def test_route_schema_rejects_ambiguous_prerequisites_and_science_shaped_extras(defect):
    value = selection(selected=None)
    item = value["comparisons"][0]
    if defect == "duplicate_blockers": item["generation_blockers"] = ["Missing valid primary body", " Missing valid primary body "]
    elif defect == "control_blocker": item["generation_blockers"] = ["Missing\x00 primary body"]
    elif defect == "invented_observations": item["observations"] = [{"value": 0}]
    else: value["scientific_approval"] = True
    with pytest.raises(ValidationError):
        validate(value)


def workflow_routes(proposed):
    value = questions().model_dump(mode="json")
    value["candidates"][0]["question"] = proposed["question"]
    value["candidates"][0]["literature_queries"] = list(proposed["literature_queries"]) + [
        "synthetic concrete uncollected route prerequisite"]
    return value


def workflow_comparison(state, routes, *, selected="route-1"):
    value = selection(selected=selected)
    protocols = [item["artifact_id"] for item in state["redesign_comparison"]["proposals"]]
    requirements = state["study_remediation"]["actions"]
    primary = list(dict.fromkeys(item["source_id"] for item in state["material_manifest"]["literature"]))
    assert primary, "The synthetic fixture must provide native-verified current primary-body references"
    for item in value["comparisons"]:
        item["evidence_sources"] = primary[:1]
        item["prior_proposals"] = [{"artifact_id": identifier,
                                    "scientific_difference": "A provisional synthetic question contrast; this is not a scientific approval."}
                                   for identifier in protocols]
        item["criterion_repairs"] = [{**requirement,
                                     "proposed_change": "A prospective substantive fixture change awaits independent verification in a fresh protocol."}
                                    for requirement in requirements]
        item["id"] = routes["candidates"][0 if item["id"] == "route-1" else 1]["id"]
    return value


def frozen_originals(service, identifier, state):
    return {key: service.artifact_path(identifier, key).read_bytes() for key in state["artifacts"]}


def assert_originals(service, identifier, originals):
    assert all(service.artifact_path(identifier, key).read_bytes() == content
               for key, content in originals.items())


def fail_collection(*args, **kwargs):
    raise AssertionError("Provisional redesign question preparation must not redispatch literature collection")


def test_workflow_route_preparation_and_selection_are_bound_idempotent_and_preserve_science(setup):
    service, runner, identifier, before, proposed, *_ = held(setup)
    originals = frozen_originals(service, identifier, before)
    source = service._workspace(identifier).path("source/transform.js").read_bytes()
    record = service._workspace(identifier).latest("workflow", Workflow)
    basis = service._preparation_redesign_basis(service._workspace(identifier), record)
    routes = workflow_routes(proposed)
    service.collector = fail_collection
    prepared = service.prepare_redesign_questions(identifier, routes)
    assert prepared["redesign_questions"] == routes and prepared["redesign_question_selection"] is None
    question_receipt = json.loads(service.artifact_path(identifier, "redesign-questions").read_bytes())
    assert question_receipt["bindings"]["parent_basis_sha256"] == _json_digest(basis)
    assert question_receipt["value"] == routes
    assert service.prepare_redesign_questions(identifier, copy.deepcopy(routes))["artifacts"] == prepared["artifacts"]
    assert service._preparation_redesign_basis(service._workspace(identifier),
        service._workspace(identifier).latest("workflow", Workflow)) == basis
    comparison = workflow_comparison(prepared, routes)
    selected = service.select_redesign_question(identifier, comparison)
    selection_receipt = json.loads(service.artifact_path(identifier, "redesign-question-selection").read_bytes())
    assert selection_receipt["bindings"]["parent_basis_sha256"] == _json_digest(basis)
    assert selection_receipt["bindings"]["questions_sha256"] == prepared["artifacts"]["redesign-questions"]["sha256"]
    assert selection_receipt["value"] == comparison and selected["redesign_question_selection"] == comparison
    assert service.select_redesign_question(identifier, copy.deepcopy(comparison))["artifacts"] == selected["artifacts"]
    assert service._preparation_redesign_basis(service._workspace(identifier),
        service._workspace(identifier).latest("workflow", Workflow)) == basis
    assert tuple(selected[name] for name in COUNTERS) == tuple(before[name] for name in COUNTERS) == (3, 2, 0, 0, 0, 0)
    assert selected["proposal"] == before["proposal"] and selected["study_review"] == before["study_review"]
    assert selected["redesign_candidate"] is selected["followup_research_id"] is None
    assert service._workspace(identifier).path("source/transform.js").read_bytes() == source
    assert_originals(service, identifier, originals)
    assert runner.calls == 0


def test_native_comparison_only_builds_public_state_after_its_selection_is_persisted(setup, monkeypatch):
    service, runner, identifier, _, proposed, *_ = held(setup)
    routes = workflow_routes(proposed)
    prepared = service.prepare_redesign_questions(identifier, routes)
    comparison = workflow_comparison(prepared, routes, selected=None)
    public = service._public
    responses = []

    def persisted_response(ws, record, **kwargs):
        stored = ws.latest("workflow", Workflow)
        assert "redesign-question-selection" in record.artifacts
        assert stored.artifacts["redesign-question-selection"] == record.artifacts["redesign-question-selection"]
        responses.append(record.artifacts["redesign-question-selection"])
        return public(ws, record, **kwargs)

    monkeypatch.setattr(service, "_public", persisted_response)
    selected = service.select_redesign_question(identifier, comparison)
    assert selected["redesign_question_selection"]["selected_id"] is None and len(responses) == 1
    assert service.select_redesign_question(identifier, copy.deepcopy(comparison))["artifacts"] == selected["artifacts"]
    assert len(responses) == 2 and responses[0] == responses[1]

    def forbidden_public(*args, **kwargs):
        raise AssertionError("Authenticating frozen route comparison must not construct public workflow state")

    monkeypatch.setattr(service, "_public", forbidden_public)
    ws = service._workspace(identifier)
    record = ws.latest("workflow", Workflow)
    assert service._redesign_question_selection(ws, record,
        service._preparation_redesign_basis(ws, record)).model_dump(mode="json") == comparison
    assert tuple(getattr(record, name) for name in COUNTERS) == (3, 2, 0, 0, 0, 0) and runner.calls == 0


@pytest.mark.parametrize("missing", ["redesign-preparation", "redesign-candidate", "redesign-review", "followup_intent"])
def test_impossible_operational_repair_skips_parent_material_expansion(monkeypatch, missing):
    service = WorkflowService.__new__(WorkflowService)
    artifacts = {key: object() for key in ("redesign-preparation", "redesign-candidate", "redesign-review")}
    if missing == "followup_intent": artifacts["redesign-intent"] = object()
    else: artifacts.pop(missing)

    def forbidden_basis(*args, **kwargs):
        raise AssertionError("A missing immutable candidate or existing follow-up cannot permit operational repair")

    monkeypatch.setattr(service, "_operational_repair_basis", forbidden_basis)
    assert service._operational_repair_available(None, SimpleNamespace(artifacts=artifacts)) is False


def test_workflow_frozen_routes_and_independent_comparison_cannot_be_replaced(setup):
    service, runner, identifier, _, proposed, *_ = held(setup)
    routes = workflow_routes(proposed)
    prepared = service.prepare_redesign_questions(identifier, routes)
    before = frozen_originals(service, identifier, prepared)
    changed = copy.deepcopy(routes)
    changed["candidates"][0]["question"] += " A replacement question?"
    with pytest.raises((WorkflowError, ValueError)):
        service.prepare_redesign_questions(identifier, changed)
    assert_originals(service, identifier, before)
    comparison = workflow_comparison(prepared, routes)
    selected = service.select_redesign_question(identifier, comparison)
    before = frozen_originals(service, identifier, selected)
    changed = copy.deepcopy(comparison)
    changed["reason"] += " An unbound rewrite after the independent decision."
    with pytest.raises((WorkflowError, ValueError)):
        service.select_redesign_question(identifier, changed)
    assert_originals(service, identifier, before)
    assert tuple(service.status(identifier)[name] for name in COUNTERS) == (3, 2, 0, 0, 0, 0)
    assert runner.calls == 0


def test_workflow_route_comparison_rejects_unbound_protocol_requirements_and_metadata_sources(setup, monkeypatch):
    service, runner, identifier, _, proposed, *_ = held(setup)
    routes = workflow_routes(proposed)
    prepared = service.prepare_redesign_questions(identifier, routes)
    before = frozen_originals(service, identifier, prepared)

    def forbidden_public(*args, **kwargs):
        raise AssertionError("Invalid comparison must fail before expensive public response construction")

    monkeypatch.setattr(service, "_public", forbidden_public)
    for defect in ("protocol", "requirement", "source"):
        invalid = workflow_comparison(prepared, routes)
        if defect == "protocol": invalid["comparisons"][0]["prior_proposals"][0]["artifact_id"] = "unretained-protocol"
        elif defect == "requirement": invalid["comparisons"][0]["criterion_repairs"][0]["required_change"] += " Changed requirement."
        else: invalid["comparisons"][0]["evidence_sources"] = ["fixture-metadata-abstract"]
        with pytest.raises((WorkflowError, ValueError)):
            service.select_redesign_question(identifier, invalid)
        assert_originals(service, identifier, before)
        assert "redesign-question-selection" not in service._workspace(identifier).latest("workflow", Workflow).artifacts
    assert runner.calls == 0


def test_workflow_selected_question_and_all_selected_queries_bind_the_single_full_candidate(setup):
    service, runner, identifier, _, proposed, parent_repair, *_ = held(setup)
    routes = workflow_routes(proposed)
    prepared = service.prepare_redesign_questions(identifier, routes)
    service.select_redesign_question(identifier, workflow_comparison(prepared, routes))
    proposed = attach_validation(service, identifier, proposed)
    originals = frozen_originals(service, identifier, service.status(identifier))
    wrong_question = copy.deepcopy(proposed)
    wrong_question["question"] += " A substituted scientific question."
    wrong_question["literature_queries"] = routes["candidates"][0]["literature_queries"]
    for candidate in (wrong_question, proposed):
        with pytest.raises((WorkflowError, ValueError)):
            service.submit_redesign_proposal(identifier, candidate, parent_repair)
        assert_originals(service, identifier, originals)
        assert service.status(identifier)["redesign_candidate"] is None
    proposed["literature_queries"] = routes["candidates"][0]["literature_queries"]
    staged = service.submit_redesign_proposal(identifier, proposed, parent_repair)
    assert staged["redesign_candidate"] == proposed and staged["redesign_review"] is None
    assert tuple(staged[name] for name in COUNTERS) == (3, 2, 0, 0, 0, 0)
    assert_originals(service, identifier, originals)
    with pytest.raises(WorkflowError):
        service.redesign_study(identifier)
    assert runner.calls == 0


def test_workflow_explicit_route_hold_cannot_stage_or_dispatch_a_candidate(setup):
    service, runner, identifier, _, proposed, parent_repair, *_ = held(setup)
    routes = workflow_routes(proposed)
    prepared = service.prepare_redesign_questions(identifier, routes)
    comparison = workflow_comparison(prepared, routes, selected=None)
    for item in comparison["comparisons"]:
        item["generation_blockers"] = ["Required primary evidence for a full scientific candidate is missing."]
    held_state = service.select_redesign_question(identifier, comparison)
    originals = frozen_originals(service, identifier, held_state)
    proposed = attach_validation(service, identifier, proposed)
    proposed["literature_queries"] = routes["candidates"][0]["literature_queries"]
    with pytest.raises((WorkflowError, ValueError)):
        service.submit_redesign_proposal(identifier, proposed, parent_repair)
    with pytest.raises(WorkflowError):
        service.redesign_study(identifier)
    assert_originals(service, identifier, originals)
    state = service.status(identifier)
    assert state["redesign_candidate"] is state["followup_research_id"] is None
    assert tuple(state[name] for name in COUNTERS) == (3, 2, 0, 0, 0, 0) and runner.calls == 0


@pytest.mark.parametrize("key", ["redesign-questions", "redesign-question-selection"])
def test_workflow_tampered_frozen_route_receipts_fail_closed_without_rewriting_science(setup, key):
    service, runner, identifier, before, proposed, *_ = held(setup)
    originals = frozen_originals(service, identifier, before)
    original_paths = {name: service.artifact_path(identifier, name) for name in before["artifacts"]}
    routes = workflow_routes(proposed)
    prepared = service.prepare_redesign_questions(identifier, routes)
    if key == "redesign-question-selection":
        service.select_redesign_question(identifier, workflow_comparison(prepared, routes))
    path = service.artifact_path(identifier, key)
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises((WorkflowError, ValueError)):
        service.status(identifier)
    # Artifact access also verifies hashes, so compare the already retained paths directly.
    for name, content in originals.items():
        assert original_paths[name].read_bytes() == content
    assert runner.calls == 0


def test_workflow_new_route_scouting_cannot_replace_a_frozen_or_operationally_rejected_candidate(setup):
    service, runner, identifier, _, proposed, parent_repair, *_ = held(setup)
    proposed = attach_validation(service, identifier, proposed)
    staged = service.submit_redesign_proposal(identifier, proposed, parent_repair)
    routes = workflow_routes(proposed)
    originals = frozen_originals(service, identifier, staged)
    with pytest.raises((WorkflowError, ValueError)):
        service.prepare_redesign_questions(identifier, routes)
    assert_originals(service, identifier, originals)
    review = preparation_review()
    review.update(accepted=False, issues=["A synthetic operational definition remains incomplete."])
    review["feasibility"] = {"passed": False, "reason": "The candidate requires a single permitted operational correction, not a replacement route."}
    rejected = service.submit_redesign_review(identifier, review)
    assert rejected["redesign_operational_repair_available"] is True
    originals = frozen_originals(service, identifier, rejected)
    with pytest.raises((WorkflowError, ValueError)):
        service.prepare_redesign_questions(identifier, routes)
    assert_originals(service, identifier, originals)
    assert tuple(service.status(identifier)[name] for name in COUNTERS) == (3, 2, 0, 0, 0, 0) and runner.calls == 0

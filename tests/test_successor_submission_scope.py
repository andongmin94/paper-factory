"""Distinct synthetic successor targets; no real research or execution."""
import copy

import pytest

from paper_factory.autonomous.models import ResearchPlan, StudyReview
from paper_factory.workflow import WorkflowError, SCHEMAS, _freeze
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import write_json
from test_redesign_admission_feedback import held, receipt, retain_pair
from test_planned_claim_projection import COUNTERS, retained_bytes
from test_preexecution_redesign import attach_validation, review
from test_submission_workflow import contract
from test_workflow import BUNDLE, REVIEW, STUDY_REVIEW, collect_arxiv_preprint, protocol, rejected_study_review, setup


def different(fixture):
    service, _, identifier, _, value, *_ = fixture
    value = copy.deepcopy(value)
    value["units_per_seed"] += 1
    value["seeds"] = [13, 41]
    value["research_claim"].update(mode="empirical",
        claim="Only the observed differences in the new eight-unit synthetic comparison are claimed.",
        scope="Eight newly declared synthetic units; no general population or scholarly validity is inferred.")
    return attach_validation(service, identifier, value)


def own_contract(candidate):
    value = contract()
    value["article_type"] = candidate["research_claim"]["mode"]
    value["core_claim"] = candidate["research_claim"]["claim"]
    for obligation in value["claim_obligations"]:
        obligation["validation_mode"] = value["article_type"]
        obligation["required_evidence"] = "Retained measurements for this child's exact eight declared units and fresh independent controls."
    return value


def fresh_review(candidate, collected):
    value = copy.deepcopy(STUDY_REVIEW)
    source = collected["literature"]["sources"][0]
    value["selected_sources"][0]["source_id"] = source["id"]
    ready = value["publication_readiness"]
    ready.update(claim=candidate["research_claim"]["claim"], scope=candidate["research_claim"]["scope"],
                 evidence_mode=candidate["research_claim"]["mode"])
    ready["closest_work"][0]["source_id"] = source["id"]
    return value


def test_different_supported_mode_and_domain_do_not_inherit_parent_scientific_obligations(setup):
    fixture = held(setup)
    service, runner, identifier, parent, *_ = fixture
    candidate = different(fixture)
    originals = {key: service.artifact_path(identifier, key).read_bytes() for key in parent["artifacts"]}
    schema = parent["schemas"]["plan"]
    for field, definition in (("research_claim", "ResearchClaim"), ("validation_contract", "ValidationContract")):
        assert field in schema["required"]
        assert schema["properties"][field] == {"$ref": "#/$defs/" + definition}
        assert schema["$defs"][definition]["properties"]["mode"] == {"type": "string", "enum": ["empirical", "finite_enumeration"]}
    assert "const" not in SCHEMAS["plan"]["$defs"]["ResearchClaim"]["properties"]["mode"]
    assert "constrain that parent study, not the distinct successor" in parent["planning_instructions"]
    assert "original user goal, frozen source, available isolated runtime" in parent["planning_instructions"]
    staged = service.submit_redesign_proposal(identifier, candidate, fixture[5])
    assert staged["redesign_candidate"] == candidate
    assert staged["submission_contract"] == parent["submission_contract"]
    assert staged["study_review"] == parent["study_review"] and staged["study_review"]["accepted"] is False
    assert tuple(staged[name] for name in COUNTERS) == (3, 2, 0, 0, 0, 0)
    with pytest.raises(WorkflowError) as error: service.redesign_study(identifier)
    assert error.value.code == "STUDY_REDESIGN_REVIEW_REQUIRED"
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in originals.items())
    assert runner.calls == 0


@pytest.mark.parametrize("wrong_own_mode", [False, True])
def test_reviewed_child_gets_fresh_own_target_and_fresh_review_before_science(setup, wrong_own_mode):
    fixture = held(setup)
    service, runner, identifier, parent, *_ = fixture
    candidate = different(fixture)
    target_raw = service.artifact_path(identifier, "submission-contract").read_bytes()
    service.submit_redesign_proposal(identifier, candidate, fixture[5])
    service.submit_redesign_review(identifier, review())
    child = service.redesign_study(identifier)
    child_id = child["id"]
    assert child["proposal"] == candidate and child["submission_contract"] is None
    assert child["goal"] == parent["goal"] and child["project_id"] == parent["project_id"]
    assert child["proposal"]["runtime"] == parent["proposal"]["runtime"]
    assert service.artifact_path(child_id, "prior-study-" + identifier + "-submission-contract").read_bytes() == target_raw
    assert child["study_review"] is None and tuple(child[name] for name in COUNTERS) == (1, 0, 0, 0, 0, 1)
    service.collector = collect_arxiv_preprint
    collected = service.collect_literature(child_id)
    assessment = fresh_review(candidate, collected)
    before = retained_bytes(service, child_id)
    with pytest.raises(WorkflowError) as error: service.submit_study_review(child_id, assessment)
    assert error.value.code == "SUBMISSION_CONTRACT_REQUIRED"
    assert retained_bytes(service, child_id) == before
    with pytest.raises(WorkflowError): service.submit_code(child_id, BUNDLE, REVIEW)
    with pytest.raises(WorkflowError): service.start_experiment(child_id)
    target = contract() if wrong_own_mode else own_contract(candidate)
    own = service.set_submission_contract(child_id, target)
    assert own["submission_contract"]["bindings"]["research_id"] == child_id
    assert own["submission_contract"] != parent["submission_contract"]
    before = retained_bytes(service, child_id)
    if wrong_own_mode:
        with pytest.raises(WorkflowError) as error: service.submit_study_review(child_id, assessment)
        assert error.value.code == "SUBMISSION_MODE_MISMATCH"
        assert retained_bytes(service, child_id) == before
    else:
        assert service.submit_study_review(child_id, assessment)["stage"] == "planned"
    assert tuple(service.status(identifier)[name] for name in COUNTERS) == (3, 2, 0, 0, 0, 0)
    assert service.artifact_path(identifier, "submission-contract").read_bytes() == target_raw
    assert service.status(child_id)["execution_attempt"] == runner.calls == 0


@pytest.mark.parametrize("defect", ["missing_claim", "missing_contract", "mismatched_modes", "formal", "wrong_grid", "invented_oracle"])
def test_successor_scope_exemption_keeps_every_native_validation_guard(setup, defect):
    fixture = held(setup)
    service, runner, identifier, *_ = fixture
    candidate = different(fixture)
    if defect == "missing_claim": candidate["research_claim"] = None
    elif defect == "missing_contract": candidate["validation_contract"] = None
    elif defect == "mismatched_modes": candidate["validation_contract"].update(mode="finite_enumeration", finite_domain_label="domain.json")
    elif defect == "formal":
        candidate["research_claim"]["mode"] = "formal"
        candidate["validation_contract"].update(mode="formal", finite_domain_label=None)
    elif defect == "wrong_grid": candidate["validation_contract"]["declared_units"][0]["seed"] = 999
    else: candidate["validation_contract"]["oracle_sources"][0]["quote"] = "Invented unsupported oracle passage was never part of the retained current primary body. " * 2
    before = retained_bytes(service, identifier)
    with pytest.raises(ValueError): service.submit_redesign_proposal(identifier, candidate, fixture[5])
    state = service.status(identifier)
    assert state["redesign_candidate"] is state["followup_research_id"] is None
    assert tuple(state[name] for name in COUNTERS) == (3, 2, 0, 0, 0, 0)
    assert retained_bytes(service, identifier) == before and runner.calls == 0


def test_same_study_still_requires_its_own_frozen_mode(setup):
    service, runner, identifier = setup
    state = service.set_submission_contract(identifier, contract())
    value = protocol()
    value["research_claim"]["mode"] = "empirical"
    before = retained_bytes(service, identifier)
    with pytest.raises(WorkflowError) as error: service.submit_proposal(identifier, value)
    assert error.value.code == "SUBMISSION_MODE_MISMATCH"
    assert service.status(identifier)["schemas"]["plan"]["$defs"]["ResearchClaim"]["properties"]["mode"] == {"type": "string", "const": "finite_enumeration"}
    assert service.status(identifier)["submission_contract"] == state["submission_contract"]
    assert retained_bytes(service, identifier) == before and runner.calls == 0


def test_later_infeasible_refusal_is_preserved_without_ambiguating_original_technical_pair(setup):
    fixture = held(setup)
    service, runner, identifier, *_ = fixture
    originals = retain_pair(fixture)
    expected = service.status(identifier)["redesign_admission_feedback"]
    refusal = copy.deepcopy(fixture[4])
    refusal.update(feasible=False, research_claim=None, validation_contract=None)
    ResearchPlan.model_validate(refusal)
    refused = receipt(service, identifier, "A full retained later candidate feasibility refusal, not a missing-validation admission pair.", refusal)
    raw = service.artifact_path(identifier, refused["artifactId"]).read_bytes()
    before = retained_bytes(service, identifier)
    current = service.status(identifier)
    assert current["redesign_admission_feedback"] == expected
    assert expected["proposal"]["artifact_id"] == originals[0]["artifactId"]
    assert current["redesign_candidate"] is None
    assert service.artifact_path(identifier, refused["artifactId"]).read_bytes() == raw
    assert retained_bytes(service, identifier) == before and runner.calls == 0


def pending_child(setup):
    fixture = held(setup)
    service, runner, identifier, *_ = fixture
    candidate = different(fixture)
    service.submit_redesign_proposal(identifier, candidate, fixture[5])
    service.submit_redesign_review(identifier, review())
    child = service.redesign_study(identifier)
    service.collector = collect_arxiv_preprint
    collected = service.collect_literature(child["id"])
    return service, runner, child, candidate, collected


@pytest.mark.parametrize("omitted", ["validation_contract", "research_claim"])
def test_new_child_revision_cannot_drop_its_claim_or_validation_before_own_target(setup, omitted):
    service, runner, child, candidate, _ = pending_child(setup)
    service.submit_study_review(child["id"], rejected_study_review())
    revised = copy.deepcopy(candidate)
    revised["question"] += " A synthetic revision cannot remove required declarations."
    revised[omitted] = None
    before = retained_bytes(service, child["id"])
    with pytest.raises(WorkflowError) as error: service.submit_proposal(child["id"], revised)
    assert error.value.code == ("RESEARCH_CLAIM_REQUIRED" if omitted == "research_claim" else "VALIDATION_CONTRACT_REQUIRED")
    assert service.status(child["id"])["proposal_attempt"] == 1
    assert service.status(child["id"])["submission_contract"] is None
    assert retained_bytes(service, child["id"]) == before and runner.calls == 0


@pytest.mark.parametrize("missing_claim", [False, True])
def test_archived_nullable_child_cannot_approve_submit_code_or_dispatch_without_own_target(setup, missing_claim):
    """Seed an invalid later archive only in a synthetic workspace, never an actual study."""
    service, runner, child, candidate, collected = pending_child(setup)
    ws = service._workspace(child["id"])
    record = ws.latest("workflow", Workflow)
    legacy = copy.deepcopy(candidate)
    legacy["validation_contract"] = None
    if missing_claim: legacy["research_claim"] = None
    path = ws.path("research/synthetic-archived-nullable-revision.json")
    write_json(path, ResearchPlan.model_validate(legacy))
    _freeze(ws, record, "proposal-2", path)
    _freeze(ws, record, "proposal", path)
    record.proposal_attempt = 2
    ws.save("workflow", record)
    assessment = fresh_review(candidate, collected)
    before = retained_bytes(service, child["id"])
    with pytest.raises(WorkflowError) as error: service.submit_study_review(child["id"], assessment)
    assert error.value.code == "SUBMISSION_CONTRACT_REQUIRED"
    assert retained_bytes(service, child["id"]) == before

    # Also exercise archived accepted-plan entry points without weakening native approval.
    _freeze(ws, record, "plan", path)
    selected = service._selected_literature(collected["literature"], StudyReview.model_validate(assessment).selected_sources)
    selected_path = ws.path("research/synthetic-archived-selected-literature.json")
    write_json(selected_path, selected)
    _freeze(ws, record, "selected-literature", selected_path)
    archived_review = {"origin": "native_host_submission", "review": assessment,
        "proposal_sha256": record.artifacts["proposal"].sha256, "protocol_sha256": record.artifacts["plan"].sha256,
        "literature_sha256": record.artifacts["literature"].sha256,
        "selected_literature_sha256": record.artifacts["selected-literature"].sha256}
    review_path = ws.path("research/synthetic-archived-review.json")
    write_json(review_path, archived_review)
    _freeze(ws, record, "study-review", review_path)
    record.stage = "planned"
    ws.save("workflow", record)
    before = retained_bytes(service, child["id"])
    with pytest.raises(WorkflowError) as error: service.submit_code(child["id"], BUNDLE, REVIEW)
    assert error.value.code == "SUBMISSION_CONTRACT_REQUIRED"
    assert retained_bytes(service, child["id"]) == before
    record.stage = "code_ready"
    ws.save("workflow", record)
    before = retained_bytes(service, child["id"])
    with pytest.raises(WorkflowError) as error: service.start_experiment(child["id"])
    assert error.value.code == "SUBMISSION_CONTRACT_REQUIRED"
    assert service.status(child["id"])["execution_attempt"] == runner.calls == 0
    assert retained_bytes(service, child["id"]) == before

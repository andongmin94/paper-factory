"""Exact parent evidence remains separate from scientific planning instructions."""

import copy
import json

import pytest

from paper_factory.autonomous import science
from paper_factory.workflow import SCHEMAS, WorkflowError
from test_planned_claim_projection import COUNTERS, retained_bytes
from test_preexecution_redesign import reject_three_proposals
from test_study_repair import design_rejection, recovery, remediation, retain_historical_classification
from test_submission_workflow import contract
from test_workflow import prepare, protocol, setup


def test_candidate_instructions_preserve_guidance_without_duplicating_structured_parent_decisions(setup):
    service, runner, identifier = setup
    rejected = reject_three_proposals(service, identifier, partial_attempts=2, final_review=design_rejection())
    decision = remediation(rejected)
    service.record_study_remediation(identifier, decision)
    held = retain_historical_classification(service, identifier, recovery(False))
    assert held["preparation_redesign_available"]
    before = retained_bytes(service, identifier)

    state = service.status(identifier)
    instructions = state["planning_instructions"]
    assert instructions.startswith(science.planning_prompt(held["source_context"], held["goal"]))
    assert "structured retained native workflow fields in the canonical parent evidence packet" in instructions
    assert "materially different candidate only" in instructions
    assert "every proposal in redesign_comparison" in instructions
    assert "still needs every ordinary scientific gate" in instructions
    assert "No formal proof route unsupported by the native validator is authorized." in instructions
    for field in ("study_review", "study_remediation", "study_recovery_review"):
        assert state[field] == held[field]
        assert json.dumps(state[field], ensure_ascii=False) not in instructions
    for key in ("rejected_review", "unchanged_parent_recovery_classification", "actual_counts"):
        assert f'"{key}"' not in instructions
    assert state["study_recovery_review"]["allow_successor"] is False
    assert state["redesign_comparison"] == held["redesign_comparison"]
    assert state["planned_claim"] == held["planned_claim"]
    assert state["artifacts"] == held["artifacts"]
    assert tuple(state[name] for name in COUNTERS) == tuple(held[name] for name in COUNTERS) == (3, 2, 0, 0, 0, 0)
    assert retained_bytes(service, identifier) == before and runner.calls == 0


@pytest.mark.parametrize("stage", ["created", "proposed"])
def test_active_submission_target_requires_typed_validation_in_schema_and_native_guidance(setup, stage):
    service, runner, identifier = setup
    if stage == "proposed":
        reject_three_proposals(service, identifier, partial_attempts=2, final_review=design_rejection())
    legacy_schema = copy.deepcopy(SCHEMAS)
    state = service.set_submission_contract(identifier, contract())
    before = retained_bytes(service, identifier)
    public = service.status(identifier)
    schema = public["schemas"]["plan"]
    mode = public["submission_contract"]["value"]["article_type"]
    for field, definition in (("research_claim", "ResearchClaim"), ("validation_contract", "ValidationContract")):
        assert field in schema["required"]
        assert schema["properties"][field] == {"$ref": "#/$defs/" + definition}
        assert schema["$defs"][definition]["properties"]["mode"] == {"type": "string", "const": mode}
    instructions = public["instructions"] if stage == "created" else public["planning_instructions"]
    assert "submission_contract IS PRESENT" in instructions
    assert "MUST provide non-null research_claim and validation_contract" in instructions
    assert "submission_contract.value.article_type: " + mode in instructions
    assert "exactly units_per_seed units per seed" in instructions
    assert "exact text_sha256 values and literal body quotes" in instructions
    assert "at least three distinct seeds in every stratum" in instructions
    assert "Automatic formal proof verification is unsupported" in instructions
    assert public["submission_contract"] == state["submission_contract"]
    assert SCHEMAS == legacy_schema
    assert public["artifacts"] == state["artifacts"]
    assert tuple(public[name] for name in COUNTERS) == tuple(state[name] for name in COUNTERS)
    if stage == "proposed":
        assert public["proposal"] == state["proposal"]
        assert public["proposal"].get("validation_contract") is None
        assert public["study_review"] == state["study_review"]
    else:
        with pytest.raises(WorkflowError) as error:
            service.submit_proposal(identifier, protocol())
        assert error.value.code == "VALIDATION_CONTRACT_REQUIRED"
    assert retained_bytes(service, identifier) == before and runner.calls == 0


def test_retained_planned_protocol_keeps_historical_schema_and_bytes_after_target_is_added(setup):
    service, runner, identifier = setup
    prepare(service, identifier)
    state = service.set_submission_contract(identifier, contract())
    before = retained_bytes(service, identifier)
    public = service.status(identifier)
    assert public["stage"] == "code_ready" and public["schemas"] == SCHEMAS
    assert "anyOf" in public["schemas"]["plan"]["properties"]["validation_contract"]
    assert public["plan"].get("validation_contract") is None
    assert public["artifacts"] == state["artifacts"]
    assert retained_bytes(service, identifier) == before and runner.calls == 0

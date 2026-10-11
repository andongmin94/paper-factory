"""Compact planned-claim reads on synthetic workspaces; no actual study is executed."""

import pytest

from paper_factory import ipc
from paper_factory.autonomous.models import ResearchPlan
from paper_factory.workflow import WorkflowError, _freeze
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import write_json
from test_preexecution_redesign import reject_three_proposals
from test_submission_workflow import assessment, manuscript, measured, observed
from test_workflow import prepare, protocol, setup


COUNTERS = ("proposal_attempt", "study_literature_attempt", "code_attempt", "execution_attempt",
            "draft_attempt", "redesign_attempt")


def listed(service):
    dispatcher = object.__new__(ipc.Dispatcher)
    dispatcher.service = service
    return dispatcher.execute("workflow.list", {})


def retained_bytes(service, identifier):
    root = service.root / identifier
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def projected(claim):
    return {name: claim[name] for name in ("claim", "scope", "mode")}


def test_created_compact_list_has_no_planned_claim_and_reads_change_no_bytes(setup):
    service, runner, identifier = setup
    full = service.status(identifier)
    before = retained_bytes(service, identifier)
    compact = service.status(identifier, include_materials=False)
    item, = listed(service)
    assert full["planned_claim"] is compact["planned_claim"] is item["planned_claim"] is None
    assert "material_manifest" not in item and "source_context" not in item and "schemas" not in item
    assert item["artifacts"] == full["artifacts"]
    assert retained_bytes(service, identifier) == before and runner.calls == 0


def test_rejected_three_proposal_two_collection_list_restores_exact_frozen_claim_readonly(setup):
    service, runner, identifier = setup
    full = reject_three_proposals(service, identifier, partial_attempts=2)
    assert (full["proposal_attempt"], full["study_literature_attempt"], full["execution_attempt"]) == (3, 2, 0)
    before = retained_bytes(service, identifier)
    compact = service.status(identifier, include_materials=False)
    item, = listed(service)
    expected = projected(full["proposal"]["research_claim"])
    assert expected == full["planned_claim"] == compact["planned_claim"] == item["planned_claim"]
    assert set(item["planned_claim"]) == {"claim", "scope", "mode"}
    assert "proposal" not in item and "plan" not in item and "material_manifest" not in item
    assert item["artifacts"]["proposal"] == full["artifacts"]["proposal"]
    assert tuple(item[name] for name in COUNTERS) == tuple(full[name] for name in COUNTERS)
    assert retained_bytes(service, identifier) == before and runner.calls == 0


@pytest.mark.parametrize("mode", [None, "formal"])
def test_precontract_missing_and_historical_formal_claims_are_truthful_readonly_projections(setup, mode):
    service, runner, identifier = setup
    plan = protocol()
    if mode is None:
        plan["research_claim"] = None
        # Seed a retained pre-claim record; today's proposal API correctly
        # requires a declared claim and must not be weakened for this read test.
        ws = service._workspace(identifier)
        record = ws.get("workflow", identifier, Workflow)
        path = ws.path("research/proposals/attempt-1/proposal.json")
        write_json(path, ResearchPlan.model_validate(plan))
        for key in ("proposal", "proposal-1"):
            _freeze(ws, record, key, path)
        record.stage, record.status, record.proposal_attempt = "proposed", "ready", 1
        ws.save("workflow", record)
        full = service.status(identifier)
    else:
        plan["research_claim"]["mode"] = mode
        full = service.submit_proposal(identifier, plan)
    before = retained_bytes(service, identifier)
    item, = listed(service)
    expected = projected(plan["research_claim"]) if mode else None
    assert item["planned_claim"] == full["planned_claim"] == expected
    assert item["submission_contract"] is None and item["study_review"] is None
    assert not item["submission_readiness"]["science_verified"]
    assert retained_bytes(service, identifier) == before and runner.calls == 0


def test_planned_claim_stays_distinct_from_accepted_negative_observed_manuscript_claim(setup):
    service, runner, identifier = measured(setup)
    conclusion = observed(outcome="negative")
    assert conclusion["claim"] != protocol()["research_claim"]["claim"]
    full = service.submit_manuscript(identifier, manuscript(), assessment(conclusion), conclusion)
    before = retained_bytes(service, identifier)
    compact = service.status(identifier, include_materials=False)
    item, = listed(service)
    assert full["planned_claim"] == compact["planned_claim"] == item["planned_claim"] == projected(full["plan"]["research_claim"])
    assert item["manuscript_claim"]["value"] == conclusion
    assert item["planned_claim"]["claim"] != item["manuscript_claim"]["value"]["claim"]
    assert item["artifacts"]["plan"] == full["artifacts"]["plan"]
    assert tuple(item[name] for name in COUNTERS) == tuple(full[name] for name in COUNTERS)
    assert retained_bytes(service, identifier) == before and runner.calls == 1


@pytest.mark.parametrize("key", ["proposal", "plan"])
def test_compact_and_full_reads_fail_closed_when_frozen_planned_source_bytes_change(setup, key):
    service, runner, identifier = setup
    if key == "plan":
        prepare(service, identifier)
    else:
        service.submit_proposal(identifier, protocol())
    state = service.status(identifier)
    path = service.artifact_path(identifier, key)
    path.write_bytes(path.read_bytes() + b"\n ")
    before = retained_bytes(service, identifier)
    for operation in (lambda: service.status(identifier),
                      lambda: service.status(identifier, include_materials=False),
                      lambda: listed(service)):
        with pytest.raises(WorkflowError) as error:
            operation()
        assert error.value.code == "ARTIFACT_CHANGED"
    assert retained_bytes(service, identifier) == before
    assert state["execution_attempt"] == 0 and runner.calls == 0

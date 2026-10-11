"""Structured synthetic design repairs preserve actual attempts and held decisions."""

import copy
import json

import pytest
from pydantic import ValidationError

from paper_factory import ipc
from paper_factory.autonomous.study_repair import StudyRecoveryReview, failed_criteria
from paper_factory.autonomous import literature
from paper_factory.workflow import WorkflowError, _freeze, _retain_study_decision
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import write_json
from test_autonomous_literature import clock
from test_literature_passage_selection import PASSAGE
from test_preexecution_redesign import attach_validation, candidate, exhaust, reject_three_proposals, review as redesign_review
from test_retained_primary_literature import preprint
from test_study_literature_followup import PDF_HINT, hinted_collector, rejected
from test_workflow import BUNDLE, REVIEW, SYNTHETIC_PASSAGE, committed_workflows, rejected_study_review, setup


def design_rejection():
    value = rejected_study_review()
    for name in ("novelty", "significance"):
        value["publication_readiness"][name].update(passed=False,
            reason="Synthetic knowledge and importance deficiencies require a different research question.")
    return value


def remediation(state, *, action="revise_design"):
    return {"action": action, "queries": ["synthetic directly relevant closest methods"] if action == "retrieve_literature" else [],
        "pdfCandidates": [], "reason": "Synthetic preparation diagnosis identifies missing knowledge rather than inventing favorable evidence.",
        "actions": [{"criterion": name,
                     "required_change": "Resolve the synthetic " + name + " deficiency with a substantive independently assessable change."}
                    for name in failed_criteria(state["study_review"])]}


def initial_repair_state(setup):
    service, runner, identifier = setup
    collected = preprint(service, identifier)
    state = service.submit_study_review(identifier, design_rejection())
    return service, runner, identifier, state, collected["literature"]["sources"][0]["id"]


def revised_plan(state):
    value = copy.deepcopy(state["proposal"])
    value["question"] += " A different controlled synthetic condition changes the preregistered question."
    value["expected_contribution"] += " The revised synthetic comparison explicitly addresses the recorded critique."
    return value


def repair(value, *, source_id=None):
    return {"changes": [{**item, "actual_change": "The synthetic question and declared contribution were revised to address this exact requirement.",
                         "changed_fields": ["question", "expected_contribution"],
                         "evidence_sources": [source_id] if source_id is not None else [], "unresolved": []}
                        for item in value["actions"]]}


def successor_repair(value):
    changes = repair(value)
    for item in changes["changes"]:
        item["changed_fields"] = ["question", "parameters"]
    return changes


def recovery(allowed=True):
    return {"design_defect": {"passed": allowed, "reason": "Synthetic structural contribution defect requires a distinct question before scientific execution."},
            "retrieval_cannot_repair": {"passed": allowed,
                "reason": "Synthetic declared claim remains routine even if additional literal methods are retrieved."},
            "allow_successor": allowed,
            "reason": "Synthetic recovery permission only stages a separate candidate and does not approve any scientific work."}


def retain_historical_classification(service, identifier, value):
    """Seed old immutable evidence without restoring its retired production write API."""
    ws = service._workspace(identifier)
    record = ws.latest("workflow", Workflow)
    assessment = StudyRecoveryReview.model_validate(value).model_dump(mode="json")
    _retain_study_decision(ws, record, "study-recovery-review", assessment)
    ws.save("workflow", record)
    return service.status(identifier)


def original_bytes(service, identifier, state):
    return {key: service.artifact_path(identifier, key).read_bytes() for key in state["artifacts"]}


def test_every_failed_criterion_has_bound_required_and_actual_change(setup):
    service, runner, identifier, state, source_id = initial_repair_state(setup)
    before = original_bytes(service, identifier, state)
    instruction = remediation(state)
    recorded = service.record_study_remediation(identifier, instruction)
    assert recorded["study_remediation"] == instruction
    assert recorded["proposal_attempt"] == 1 and recorded["study_literature_attempt"] == recorded["execution_attempt"] == runner.calls == 0
    assert service.record_study_remediation(identifier, copy.deepcopy(instruction))["artifacts"] == recorded["artifacts"]
    changes = repair(instruction, source_id=source_id)
    proposed = service.submit_proposal(identifier, revised_plan(state), changes)
    assert proposed["proposal_attempt"] == 2 and proposed["study_review"] is None
    assert proposed["study_remediation"] is None
    repair_keys = [key for key in proposed["artifacts"] if key.startswith("study-repair")]
    assert repair_keys
    frozen = json.loads(service.artifact_path(identifier, repair_keys[0]).read_bytes())
    assert frozen.get("repair", frozen.get("value")) == changes
    assert frozen.get("prior_study_review_sha256", (frozen.get("bindings") or {}).get("study_review_sha256")) == state["artifacts"]["study-review"]["sha256"]
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in before.items()
               if key not in {"proposal", "literature", "study-review"})
    assert service.artifact_path(identifier, "proposal-1").read_bytes() == before["proposal"]
    assert service.artifact_path(identifier, "study-review-1").read_bytes() == before["study-review"]
    assert proposed["study_literature_attempt"] == proposed["execution_attempt"] == runner.calls == 0


@pytest.mark.parametrize("defect", ["missing", "extra", "duplicate", "wrong_action", "empty_reason"])
def test_remediation_must_cover_exact_failed_criteria_and_bounded_strategy(setup, defect):
    service, runner, identifier, state, source_id = initial_repair_state(setup)
    value = remediation(state)
    if defect == "missing": value["actions"].pop()
    elif defect == "extra": value["actions"].append({"criterion": "sampling", "required_change": "A passed synthetic sampling condition cannot be relabeled as an unresolved failed requirement."})
    elif defect == "duplicate": value["actions"].append(copy.deepcopy(value["actions"][0]))
    elif defect == "wrong_action": value["queries"] = ["Unsupported retrieval beside a design change"]
    else: value["reason"] = " "
    with pytest.raises((WorkflowError, ValidationError, ValueError)):
        service.record_study_remediation(identifier, value)
    assert service.status(identifier)["artifacts"] == state["artifacts"] and runner.calls == 0


@pytest.mark.parametrize("defect", ["absent", "missing", "extra", "duplicate", "wrong_requirement", "unchanged_field", "nonexistent_field", "nested_field", "fake_source", "history_source"])
def test_claimed_repairs_cannot_replace_actual_diff_or_current_verified_evidence(setup, defect):
    service, runner, identifier, state, source_id = initial_repair_state(setup)
    instruction = remediation(state)
    recorded = service.record_study_remediation(identifier, instruction)
    value = repair(instruction, source_id=source_id)
    if defect == "absent": value = None
    elif defect == "missing": value["changes"].pop()
    elif defect == "extra": value["changes"].append({**value["changes"][0], "criterion": "sampling"})
    elif defect == "duplicate": value["changes"].append(copy.deepcopy(value["changes"][0]))
    elif defect == "wrong_requirement": value["changes"][0]["required_change"] += " Invented different requirement."
    elif defect == "unchanged_field": value["changes"][0]["changed_fields"] = ["units_per_seed"]
    elif defect == "nonexistent_field": value["changes"][0]["changed_fields"] = ["fictional_field"]
    elif defect == "nested_field": value["changes"][0]["changed_fields"] = ["parameters.fixture_size"]
    elif defect == "fake_source": value["changes"][0]["evidence_sources"] = ["invented-unretained-source"]
    else: value["changes"][0]["evidence_sources"] = ["source-retained-only-in-earlier-history"]
    with pytest.raises((WorkflowError, ValidationError, ValueError)):
        service.submit_proposal(identifier, revised_plan(state), value)
    unchanged = service.status(identifier)
    assert unchanged["proposal_attempt"] == state["proposal_attempt"] == 1
    assert unchanged["artifacts"] == recorded["artifacts"] and runner.calls == 0


def test_explicit_unresolved_requirements_remain_visible_and_never_imply_approval(setup):
    service, runner, identifier, state, source_id = initial_repair_state(setup)
    instruction = remediation(state)
    service.record_study_remediation(identifier, instruction)
    changes = repair(instruction)
    changes["changes"][0].update(changed_fields=[], evidence_sources=[],
        unresolved=["Synthetic unresolved contribution remains for independent review."])
    proposed = service.submit_proposal(identifier, revised_plan(state), changes)
    assert proposed["stage"] == "proposed" and proposed["study_review"] is None
    with pytest.raises(WorkflowError): service.submit_code(identifier, BUNDLE, REVIEW)
    with pytest.raises(WorkflowError): service.start_experiment(identifier)
    assert proposed["execution_attempt"] == runner.calls == 0


@pytest.mark.parametrize("defect", ["terminal", "cleanup", "running", "cancelled"])
def test_remediation_and_candidate_cannot_bypass_unsafe_state(setup, defect):
    service, runner, identifier = setup
    state = reject_three_proposals(service, identifier, final_review=design_rejection())
    instruction = remediation(state)
    service.record_study_remediation(identifier, instruction)
    ws = service._workspace(identifier); record = ws.latest("workflow", Workflow)
    if defect == "terminal": record.terminal_control_failure = True
    elif defect == "cleanup": record.code = "CLEANUP_UNCONFIRMED"
    else: record.status = defect
    ws.save("workflow", record)
    with pytest.raises(WorkflowError): service.record_study_remediation(identifier, instruction)
    with pytest.raises(WorkflowError): service.submit_redesign_proposal(identifier, candidate(service, identifier), successor_repair(instruction))
    assert runner.calls == 0 and len(committed_workflows(service)) == 1


@pytest.mark.parametrize("attempts", [0, 1, 2])
def test_exhausted_design_consideration_preserves_partial_retrieval_and_requires_candidate_review(setup, attempts):
    service, runner, identifier = setup
    state = reject_three_proposals(service, identifier, partial_attempts=attempts, final_review=design_rejection())
    assert not state["preparation_redesign_available"]
    originals = original_bytes(service, identifier, state)
    instruction = remediation(state)
    service.record_study_remediation(identifier, instruction)
    granted = retain_historical_classification(service, identifier, recovery())
    assert granted["study_recovery_review"] == recovery() and granted["preparation_redesign_available"]
    assert (granted["proposal_attempt"], granted["study_literature_attempt"], granted["execution_attempt"]) == (3, attempts, 0)
    assert service.status(identifier)["artifacts"] == granted["artifacts"]
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in originals.items())
    service.submit_redesign_proposal(identifier, candidate(service, identifier), successor_repair(instruction))
    with pytest.raises(WorkflowError) as held: service.redesign_study(identifier)
    assert held.value.code == "STUDY_REDESIGN_REVIEW_REQUIRED"
    service.submit_redesign_review(identifier, redesign_review())
    child = service.redesign_study(identifier)
    assert child["parent_research_id"] == identifier and child["root_research_id"] == identifier
    assert child["study_review"] is None and child["execution_attempt"] == 0
    assert (service.status(identifier)["proposal_attempt"], service.status(identifier)["study_literature_attempt"]) == (3, attempts)
    assert child["redesign_attempt"] == 1 and len(committed_workflows(service)) == 2 and runner.calls == 0
    with pytest.raises(WorkflowError): service.start_experiment(child["id"])
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in originals.items())


@pytest.mark.parametrize("defect", ["absent", "wrong_requirement", "missing", "unchanged", "invented_source"])
def test_constructive_successor_requires_exact_repair_before_independent_candidate_review(setup, defect):
    service, runner, identifier = setup
    state = reject_three_proposals(service, identifier, final_review=design_rejection())
    instruction = remediation(state)
    service.record_study_remediation(identifier, instruction)
    granted = service.status(identifier)
    changes = successor_repair(instruction)
    if defect == "absent": changes = None
    elif defect == "wrong_requirement": changes["changes"][0]["required_change"] += " A different unbound demand."
    elif defect == "missing": changes["changes"].pop()
    elif defect == "unchanged": changes["changes"][0]["changed_fields"] = ["units_per_seed"]
    else: changes["changes"][0]["evidence_sources"] = ["invented-successor-source"]
    with pytest.raises((WorkflowError, ValidationError)):
        service.submit_redesign_proposal(identifier, candidate(service, identifier), changes)
    assert service.status(identifier)["artifacts"] == granted["artifacts"] and runner.calls == 0


def test_successor_repair_is_frozen_bound_reviewed_and_copied_into_child(setup):
    service, runner, identifier = setup
    state = reject_three_proposals(service, identifier, final_review=design_rejection())
    instruction = remediation(state)
    service.record_study_remediation(identifier, instruction)
    changes = successor_repair(instruction)
    value = candidate(service, identifier)
    prepared = service.submit_redesign_proposal(identifier, value, changes)
    receipt = prepared["redesign_repair"]
    assert receipt["value"] == changes and receipt["candidate_sha256"] == prepared["artifacts"]["redesign-candidate"]["sha256"]
    assert set(receipt["actual_changed_fields"]) >= {"question", "parameters"}
    assert service.submit_redesign_proposal(identifier, value, copy.deepcopy(changes))["artifacts"] == prepared["artifacts"]
    source = service.artifact_path(identifier, "redesign-repair").read_bytes()
    reviewed = service.submit_redesign_review(identifier, redesign_review())
    review_receipt = json.loads(service.artifact_path(identifier, "redesign-review").read_bytes())
    assert review_receipt["redesign_repair_sha256"] == reviewed["artifacts"]["redesign-repair"]["sha256"]
    child = service.redesign_study(identifier)
    assert service.artifact_path(child["id"], "prior-study-" + identifier + "-redesign-repair").read_bytes() == source
    assert service.artifact_path(identifier, "redesign-repair").read_bytes() == source
    assert child["execution_attempt"] == runner.calls == 0 and len(committed_workflows(service)) == 2


@pytest.mark.parametrize("field", ["candidate_sha256", "actual_changed_fields"])
def test_rebound_successor_repair_still_requires_native_candidate_binding_and_diff(setup, field):
    service, runner, identifier = setup
    state = reject_three_proposals(service, identifier, final_review=design_rejection())
    instruction = remediation(state)
    service.record_study_remediation(identifier, instruction)
    service.submit_redesign_proposal(identifier, candidate(service, identifier), successor_repair(instruction))
    ws = service._workspace(identifier); record = ws.latest("workflow", Workflow)
    path = service.artifact_path(identifier, "redesign-repair")
    receipt = json.loads(path.read_bytes())
    receipt[field] = "0" * 64 if field == "candidate_sha256" else ["units_per_seed"]
    write_json(path, receipt)
    _freeze(ws, record, "redesign-repair", path)
    ws.save("workflow", record)
    with pytest.raises(WorkflowError) as held:
        service.submit_redesign_review(identifier, redesign_review())
    assert held.value.code == "ARTIFACT_CHANGED"
    assert len(committed_workflows(service)) == 1 and runner.calls == 0


def test_classifier_denial_is_immutable_parent_stays_held_and_candidate_has_own_gate(setup):
    service, runner, identifier = setup
    state = reject_three_proposals(service, identifier, final_review=design_rejection())
    service.record_study_remediation(identifier, remediation(state))
    denied = retain_historical_classification(service, identifier, recovery(False))
    assert denied["preparation_redesign_available"] and denied["study_recovery_review"] == recovery(False)
    assert denied["status"] == "blocked" and denied["code"] == "STUDY_REJECTED"
    with pytest.raises(ValueError):
        ipc.request(json.dumps({"id": "retired", "method": "workflow.submitStudyRecoveryReview", "params": {"researchId": identifier, "review": recovery(True)}}).encode())
    assert not hasattr(service, "submit_study_recovery_review") and "study_recovery_review" not in denied["schemas"]
    with pytest.raises(WorkflowError): service.submit_redesign_proposal(identifier, candidate(service, identifier))
    assert service.status(identifier)["artifacts"] == denied["artifacts"] and runner.calls == 0


def test_constructive_candidate_requires_exhausted_formal_proposals(setup):
    service, runner, identifier, state, source_id = initial_repair_state(setup)
    with pytest.raises(WorkflowError): service.submit_redesign_proposal(identifier, candidate(service, identifier))
    service.record_study_remediation(identifier, remediation(state))
    with pytest.raises(WorkflowError): service.submit_redesign_proposal(identifier, candidate(service, identifier), successor_repair(remediation(state)))
    assert service.status(identifier)["proposal_attempt"] == 1 and runner.calls == 0


@pytest.mark.parametrize("mode", ["missing", "retrieval"])
def test_exhausted_candidate_requires_current_design_repair_action(setup, mode):
    service, runner, identifier = setup
    state = reject_three_proposals(service, identifier, final_review=design_rejection())
    if mode == "retrieval":
        service.record_study_remediation(identifier, remediation(state, action="retrieve_literature"))
    before = service.status(identifier)
    with pytest.raises(WorkflowError): service.submit_redesign_proposal(identifier, candidate(service, identifier))
    assert service.status(identifier)["artifacts"] == before["artifacts"] and runner.calls == 0


def test_remediation_is_bound_and_conflicting_reason_or_tampered_receipt_cannot_replace_it(setup):
    service, runner, identifier, state, source_id = initial_repair_state(setup)
    instruction = remediation(state)
    recorded = service.record_study_remediation(identifier, instruction)
    alternative = copy.deepcopy(instruction)
    alternative["reason"] += " A rewritten reason alone cannot reclassify identical rejected evidence."
    with pytest.raises(WorkflowError): service.record_study_remediation(identifier, alternative)
    assert service.status(identifier)["artifacts"] == recorded["artifacts"]
    path = service.artifact_path(identifier, "study-remediation")
    path.write_bytes(path.read_bytes().replace(b"native_host_submission", b"invalid_host_submission"))
    with pytest.raises(WorkflowError): service.submit_proposal(identifier, revised_plan(state), repair(instruction, source_id=source_id))
    assert runner.calls == 0


def test_recovery_permission_cannot_survive_changed_proposal_basis(setup):
    service, runner, identifier = setup
    state = reject_three_proposals(service, identifier, final_review=design_rejection())
    service.record_study_remediation(identifier, remediation(state))
    retain_historical_classification(service, identifier, recovery())
    ws = service._workspace(identifier); record = ws.latest("workflow", Workflow)
    record.goal += " Altering the goal is not the same independently assessed scientific context."
    ws.save("workflow", record)
    changed = service.status(identifier)
    assert changed["study_recovery_review"] is None and changed["study_remediation"] is None
    with pytest.raises(WorkflowError): service.submit_redesign_proposal(identifier, candidate(service, identifier))
    assert runner.calls == 0 and len(committed_workflows(service)) == 1


def test_partial_attempt_counter_cannot_be_reset_to_recovery_permission(setup):
    service, runner, identifier = setup
    state = reject_three_proposals(service, identifier, partial_attempts=2, final_review=design_rejection())
    service.record_study_remediation(identifier, remediation(state))
    retain_historical_classification(service, identifier, recovery())
    ws = service._workspace(identifier); record = ws.latest("workflow", Workflow)
    record.study_literature_attempt = 0
    ws.save("workflow", record)
    with pytest.raises(WorkflowError): service.submit_redesign_proposal(identifier, candidate(service, identifier))
    assert len(committed_workflows(service)) == 1 and runner.calls == 0


def test_cosmetic_reading_selection_preserves_old_denied_classification_and_current_repair_basis(setup):
    service, runner, identifier = setup
    collected = preprint(service, identifier)
    state = service.submit_study_review(identifier, design_rejection())
    for number in (2, 3):
        service.submit_proposal(identifier, revised_plan(state))
        service.collect_literature(identifier)
        state = service.submit_study_review(identifier, design_rejection())
    instruction = remediation(state)
    service.record_study_remediation(identifier, instruction)
    retain_historical_classification(service, identifier, recovery(False))
    source, = state["literature"]["sources"]
    cosmetic = service.select_literature_passages(identifier, [{"source_id": source["id"],
        "text_sha256": source["text_sha256"], "text": SYNTHETIC_PASSAGE[:100],
        "relevance": "Selecting a contained literal substring cannot change an already assessed scientific context."}])
    assert not cosmetic["study_literature_pending"]
    assert cosmetic["study_remediation"] == instruction and cosmetic["study_recovery_review"] == recovery(False)
    assert not hasattr(service, "submit_study_recovery_review")
    assert cosmetic["preparation_redesign_available"] and runner.calls == 0


def test_constructive_candidate_keeps_false_parent_classification_and_exact_partial_history(setup):
    service, runner, identifier = setup
    state = reject_three_proposals(service, identifier, partial_attempts=2, final_review=design_rejection())
    instruction = remediation(state)
    service.record_study_remediation(identifier, instruction)
    held = retain_historical_classification(service, identifier, recovery(False))
    original = original_bytes(service, identifier, held)
    assert held["preparation_redesign_available"] and held["resume_kind"] is None
    assert "study_recovery_available" not in held
    assert "does not establish that the unchanged question is irreparable" in held["planning_instructions"]
    assert json.loads(json.dumps(held["study_recovery_review"])) == recovery(False)
    comparison = held["redesign_comparison"]
    expected = {held["artifacts"][f"proposal-{number}"]["sha256"] for number in (1, 2, 3)}
    assert {item["sha256"] for item in comparison["proposals"]} == expected
    for item in comparison["proposals"]:
        artifact = held["artifacts"][item["artifact_id"]]
        assert (item["sha256"], item["size"]) == (artifact["sha256"], artifact["size"])
        assert item["proposal"] == json.loads(service.artifact_path(identifier, item["artifact_id"]).read_bytes())

    value = candidate(service, identifier)
    value["conditions"].append("synthetic_mechanism_ablation")
    value["comparison_rationale"] += " The frozen synthetic ablation isolates a declared mechanism rather than increasing a catalogue."
    changes = successor_repair(instruction)
    for item in changes["changes"]:
        item["changed_fields"] = ["question", "parameters", "conditions", "comparison_rationale"]
        item["unresolved"] = ["The intended design change still needs directly related body evidence and the child's fresh study assessment."]
    prepared = service.submit_redesign_proposal(identifier, value, changes)
    assert prepared["study_review"]["accepted"] is False and prepared["study_recovery_review"] == recovery(False)
    assert all(item["unresolved"] for item in prepared["redesign_repair"]["value"]["changes"])
    with pytest.raises(WorkflowError) as error:
        service.redesign_study(identifier)
    assert error.value.code == "STUDY_REDESIGN_REVIEW_REQUIRED"
    service.submit_redesign_review(identifier, redesign_review())
    child = service.redesign_study(identifier)
    parent = service.status(identifier)
    assert (parent["proposal_attempt"], parent["study_literature_attempt"], parent["execution_attempt"], parent["redesign_attempt"]) == (3, 2, 0, 0)
    assert child["parent_research_id"] == child["root_research_id"] == identifier
    assert (child["proposal_attempt"], child["study_literature_attempt"], child["execution_attempt"], child["redesign_attempt"]) == (1, 0, 0, 1)
    assert child["proposal"] == value and child["study_review"] is None
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in original.items())
    assert service.artifact_path(child["id"], "prior-study-" + identifier + "-study-recovery-review").read_bytes() == original["study-recovery-review"]
    assert {item["sha256"] for item in child["prior_study"]["bindings"].values()} >= expected
    with pytest.raises(WorkflowError):
        service.submit_code(child["id"], BUNDLE, REVIEW)
    with pytest.raises(WorkflowError):
        service.start_experiment(child["id"])
    assert len(committed_workflows(service)) == 2 and runner.calls == 0


@pytest.mark.parametrize("nominal", ["single_fixture", "arbitrary_threshold"])
def test_nominal_candidate_rejection_cannot_spend_a_fresh_study_budget(setup, nominal):
    service, runner, identifier = setup
    state = reject_three_proposals(service, identifier, partial_attempts=2, final_review=design_rejection())
    instruction = remediation(state)
    service.record_study_remediation(identifier, instruction)
    held = retain_historical_classification(service, identifier, recovery(False))
    original = original_bytes(service, identifier, held)
    value = copy.deepcopy(held["proposal"])
    value["question"] += " A nominal relabel does not establish a new scientific decision target."
    if nominal == "single_fixture":
        value["parameters"]["fixture_size"] += 1
    else:
        value["parameters"]["arbitrary_policy_threshold"] = 40
    attach_validation(service, identifier, value)
    service.submit_redesign_proposal(identifier, value, successor_repair(instruction))
    decision = redesign_review(False)
    decision["scientific_difference"]["reason"] = "The only changed procedure is an arbitrary threshold or catalogue tweak; no named failed scientific criterion is repaired."
    decision["issues"] = ["The candidate only seeks a fresh search budget while its claimed knowledge and unresolved prerequisites are unchanged."]
    rejected = service.submit_redesign_review(identifier, decision)
    review_bytes = service.artifact_path(identifier, "redesign-review").read_bytes()
    assert not rejected["preparation_redesign_available"]
    with pytest.raises(WorkflowError): service.redesign_study(identifier)
    with pytest.raises(WorkflowError): service.submit_redesign_review(identifier, redesign_review())
    with pytest.raises(WorkflowError): service.submit_redesign_proposal(identifier, candidate(service, identifier), successor_repair(instruction))
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in original.items())
    assert service.artifact_path(identifier, "redesign-review").read_bytes() == review_bytes
    assert (rejected["proposal_attempt"], rejected["study_literature_attempt"], rejected["execution_attempt"], rejected["redesign_attempt"]) == (3, 2, 0, 0)
    assert len(committed_workflows(service)) == 1 and runner.calls == 0


@pytest.mark.parametrize("decision", ["missing", "retrieve_literature", "infeasible"])
def test_cap_exhaustion_without_current_constructive_decision_cannot_consider_candidate(setup, decision):
    service, runner, identifier = setup
    state = reject_three_proposals(service, identifier, partial_attempts=1, final_review=design_rejection())
    if decision != "missing":
        service.record_study_remediation(identifier, remediation(state, action=decision))
    held = service.status(identifier)
    with pytest.raises(WorkflowError):
        service.submit_redesign_proposal(identifier, candidate(service, identifier))
    assert not held["preparation_redesign_available"] and held["redesign_comparison"] is None
    assert service.status(identifier)["artifacts"] == held["artifacts"]
    assert (held["proposal_attempt"], held["study_literature_attempt"], held["execution_attempt"]) == (3, 1, 0)
    assert len(committed_workflows(service)) == 1 and runner.calls == 0


def test_constructive_consideration_requires_named_contribution_novelty_or_significance_failure(setup):
    service, runner, identifier = setup
    only_literature = design_rejection()
    only_literature["contribution"]["passed"] = True
    only_literature["literature"]["passed"] = False
    for name in ("novelty", "significance"):
        only_literature["publication_readiness"][name]["passed"] = True
    state = reject_three_proposals(service, identifier, partial_attempts=2, final_review=only_literature)
    assert failed_criteria(state["study_review"]) == ["literature"]
    instruction = remediation(state)
    held = service.record_study_remediation(identifier, instruction)
    original = original_bytes(service, identifier, held)
    with pytest.raises(WorkflowError) as error:
        service.submit_redesign_proposal(identifier, candidate(service, identifier), successor_repair(instruction))
    assert error.value.code == "STUDY_REDESIGN_NOT_ALLOWED"
    assert not held["preparation_redesign_available"] and held["redesign_comparison"] is None
    assert (held["proposal_attempt"], held["study_literature_attempt"], held["execution_attempt"]) == (3, 2, 0)
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in original.items())
    assert len(committed_workflows(service)) == 1 and runner.calls == 0


def test_candidate_comparison_contains_all_exact_parent_and_ancestor_proposals(setup):
    service, runner, identifier = setup
    state = reject_three_proposals(service, identifier, partial_attempts=2, final_review=design_rejection())
    instruction = remediation(state)
    service.record_study_remediation(identifier, instruction)
    held = retain_historical_classification(service, identifier, recovery(False))
    originals = original_bytes(service, identifier, held)
    parent_digests = {held["artifacts"][f"proposal-{number}"]["sha256"] for number in (1, 2, 3)}
    service.submit_redesign_proposal(identifier, candidate(service, identifier), successor_repair(instruction))
    service.submit_redesign_review(identifier, redesign_review())
    child = service.redesign_study(identifier)
    exhausted = exhaust(service, child["id"])
    child_digests = {exhausted["artifacts"][f"proposal-{number}"]["sha256"] for number in (1, 2, 3)}
    comparison = exhausted["redesign_comparison"]["proposals"]
    assert len(comparison) == 6 and {item["sha256"] for item in comparison} == parent_digests | child_digests
    for item in comparison:
        artifact = exhausted["artifacts"][item["artifact_id"]]
        assert (item["sha256"], item["size"]) == (artifact["sha256"], artifact["size"])
        assert item["proposal"] == json.loads(service.artifact_path(child["id"], item["artifact_id"]).read_bytes())
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in originals.items())
    assert service.status(identifier)["study_recovery_review"] == recovery(False)
    assert (exhausted["redesign_attempt"], exhausted["proposal_attempt"], exhausted["study_literature_attempt"], exhausted["execution_attempt"]) == (1, 3, 3, 0)
    assert len(committed_workflows(service)) == 2 and runner.calls == 0


@pytest.mark.parametrize("with_validation_contract", [False, True])
def test_constructive_candidate_cannot_route_around_unsupported_formal_validation(setup, with_validation_contract):
    from test_submission_workflow import validation_spec
    service, runner, identifier = setup
    state = reject_three_proposals(service, identifier, partial_attempts=2, final_review=design_rejection())
    instruction = remediation(state)
    held = service.record_study_remediation(identifier, instruction)
    original = original_bytes(service, identifier, held)
    assert held["submission_contract"] is None
    value = candidate(service, identifier)
    value["research_claim"]["mode"] = "formal"
    if with_validation_contract:
        value["validation_contract"] = validation_spec()
        value["validation_contract"].update(mode="formal", finite_domain_label=None)
    else:
        value["validation_contract"] = None
    with pytest.raises(WorkflowError) as error:
        service.submit_redesign_proposal(identifier, value, successor_repair(instruction))
    assert error.value.code == "VALIDATION_UNSUPPORTED"
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in original.items())
    assert service.status(identifier)["artifacts"] == held["artifacts"]
    assert "redesign-candidate" not in held["artifacts"]
    assert (held["proposal_attempt"], held["study_literature_attempt"], held["execution_attempt"]) == (3, 2, 0)
    assert len(committed_workflows(service)) == 1 and runner.calls == 0


@pytest.mark.parametrize("broken_ancestry", [False, True])
def test_final_collection_review_survives_later_verified_passage_decision_only_with_exact_ancestry(setup, monkeypatch, clock, broken_ancestry):
    from test_public_pdf_hints import TEXT
    service, runner, identifier = setup
    large = TEXT.replace("\nReferences", "\n" + "Synthetic background text establishes no scholarly result. " * 1600 + "\nReferences")
    _, ranges = literature._full_text_excerpts(large, [PDF_HINT["doi"]])
    gaps = [(first["end"], second["start"]) for first, second in zip(ranges, ranges[1:]) if second["start"] - first["end"] > 3000]
    lower, upper = max(gaps, key=lambda bounds: bounds[1] - bounds[0])
    position = (lower + upper) // 2
    literal = PASSAGE
    large = large[:position] + literal + large[position:]
    final = exhaust(service, identifier, final_collector=hinted_collector(monkeypatch, text=large))
    assert final["study_literature_pending"]
    final_decision = service.submit_study_review(identifier, rejected())
    source = next(source for source in final_decision["literature"]["sources"] if source.get("doi") == PDF_HINT["doi"])
    assert not any(literal in excerpt for excerpt in source["excerpts"])
    final_review_bytes = service.artifact_path(identifier, "study-review").read_bytes()
    selected = service.select_literature_passages(identifier, [{"source_id": source["id"], "text_sha256": source["text_sha256"],
        "text": literal, "relevance": "Synthetic late body reading exercises exact preserved final-retrieval ancestry, without academic approval."}])
    assert selected["study_literature_pending"]
    later = service.submit_study_review(identifier, rejected())
    assert later["study_literature_attempt"] == later["proposal_attempt"] == 3 and later["execution_attempt"] == runner.calls == 0
    if broken_ancestry:
        ws = service._workspace(identifier); record = ws.latest("workflow", Workflow)
        path = service.artifact_path(identifier, "study-review")
        receipt = json.loads(path.read_bytes()); receipt["prior_study_review_sha256"] = "0" * 64
        write_json(path, receipt)
        for key, frozen in list(record.artifacts.items()):
            if frozen.path == path.relative_to(ws.root).as_posix(): _freeze(ws, record, key, path)
        ws.save("workflow", record)
        with pytest.raises(WorkflowError): service.submit_redesign_proposal(identifier, candidate(service, identifier))
        assert len(committed_workflows(service)) == 1
    else:
        assert later["preparation_redesign_available"]
        prepared = service.submit_redesign_proposal(identifier, candidate(service, identifier))
        assert prepared["study_literature_attempt"] == 3 and runner.calls == 0
    assert service.artifact_path(identifier, "study-review-3-literature-3").read_bytes() == final_review_bytes

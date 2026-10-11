"""One same-candidate correction on synthetic archives; no scientific execution."""

import copy
import json

import pytest

from paper_factory import ipc
from paper_factory.workflow import WorkflowError, PREPARATION_REVISION_KEYS
from test_planned_claim_projection import COUNTERS, retained_bytes
from test_preexecution_redesign import attach_validation, review
from test_redesign_admission_feedback import held, receipt
from test_successor_submission_scope import fresh_review, own_contract
from test_workflow import BUNDLE, REVIEW, collect_arxiv_preprint, setup


ISSUES = ["The retained coordinate procedure leaves insertion and output intervals ambiguous.",
          "The retained analysis does not define the unit denominator and paired summary statistics."]


def rejected_candidate(setup, *, failed="feasibility"):
    fixture = held(setup)
    service, runner, identifier, _, candidate, parent_repair, *_ = fixture
    candidate = attach_validation(service, identifier, copy.deepcopy(candidate))
    service.submit_redesign_proposal(identifier, candidate, parent_repair)
    assessment = review()
    assessment.update(accepted=False, issues=ISSUES)
    assessment[failed] = {"passed": False, "reason": "Synthetic unresolved operational details must not be supplied by the reviewer."}
    state = service.submit_redesign_review(identifier, assessment)
    return service, runner, identifier, state


def correction(state):
    value = copy.deepcopy(state["redesign_candidate"])
    value["procedure"].append("Define original and output insertion intervals and a retained positive mapping roundtrip control.")
    value["analysis_method"] += " Count each declared unit once; retain mean, median, extrema, sample stdev and paired signed differences without dropping missing units."
    repair = {"original_candidate_sha256": state["artifacts"]["redesign-candidate"]["sha256"],
              "prior_review_sha256": state["artifacts"]["redesign-review"]["sha256"],
              "changes": [
                  {"issue_index": 0, "required_change": ISSUES[0],
                   "actual_change": "The procedure now explicitly defines coordinate intervals and an actual positive mapping control.",
                   "changed_fields": ["procedure"]},
                  {"issue_index": 1, "required_change": ISSUES[1],
                   "actual_change": "The analysis now defines the per-unit denominator and retained descriptive and paired summaries.",
                   "changed_fields": ["analysis_method"]}]}
    return value, repair


def frozen_bytes(service, identifier, state):
    return {key: service.artifact_path(identifier, key).read_bytes() for key in state["artifacts"]}


def test_operational_revision_preserves_every_original_and_requires_fresh_review(setup):
    service, runner, identifier, original = rejected_candidate(setup)
    assert original["redesign_operational_repair_available"] is True
    assert original["preparation_redesign_available"] is False
    before = frozen_bytes(service, identifier, original)
    value, repair = correction(original)
    inference = receipt(service, identifier, "Synthetic operational repair author request; no scientific approval.",
                        {"proposal": value, "preparation_repair": repair})
    model_bytes = service.artifact_path(identifier, inference["artifactId"]).read_bytes()
    updated = service.submit_redesign_proposal(identifier, value, preparation_repair=repair)
    assert updated["redesign_candidate"] == value and updated["redesign_review"] is None
    assert updated["redesign_repair"] == original["redesign_repair"]
    assert updated["redesign_operational_repair_available"] is False and updated["preparation_redesign_available"] is True
    assert updated["redesign_artifact_ids"] == {"candidate": PREPARATION_REVISION_KEYS[0], "review": None,
                                               "repair": "redesign-repair", "preparation_repair": PREPARATION_REVISION_KEYS[2]}
    retained = updated["redesign_preparation_repair"]
    assert retained["original_candidate_sha256"] == repair["original_candidate_sha256"]
    assert retained["prior_review_sha256"] == repair["prior_review_sha256"]
    assert retained["parent_repair_sha256"] == original["artifacts"]["redesign-repair"]["sha256"]
    assert retained["actual_changed_fields"] == ["analysis_method", "procedure"] and retained["value"] == repair
    assert updated["redesign_preparation_original"]["candidate"] == original["redesign_candidate"]
    assert updated["redesign_preparation_original"]["review"] == original["redesign_review"]
    assert tuple(updated[name] for name in COUNTERS) == (3, 2, 0, 0, 0, 0)
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in before.items())
    assert service.artifact_path(identifier, inference["artifactId"]).read_bytes() == model_bytes
    before_retry = retained_bytes(service, identifier)
    assert service.submit_redesign_proposal(identifier, value, preparation_repair=repair)["redesign_preparation_repair"] == retained
    assert retained_bytes(service, identifier) == before_retry
    with pytest.raises(WorkflowError) as denied: service.redesign_study(identifier)
    assert denied.value.code == "STUDY_REDESIGN_REVIEW_REQUIRED"
    assert runner.calls == 0


@pytest.mark.parametrize("failed", ["scientific_difference", "prior_evidence"])
def test_scientific_or_evidence_rejection_cannot_use_operational_route(setup, failed):
    service, runner, identifier, state = rejected_candidate(setup, failed=failed)
    assert state["redesign_operational_repair_available"] is False
    value, repair = correction(state)
    before = retained_bytes(service, identifier)
    with pytest.raises(WorkflowError) as denied: service.submit_redesign_proposal(identifier, value, preparation_repair=repair)
    assert denied.value.code == "PREPARATION_REPAIR_NOT_ALLOWED"
    assert retained_bytes(service, identifier) == before and runner.calls == 0


@pytest.mark.parametrize("field", ["question", "research_claim", "parameters", "seeds", "conditions", "metrics",
                                   "independent_oracle", "validation_contract", "source_files"])
def test_all_scientific_identity_domain_and_oracle_fields_are_locked(setup, field):
    service, runner, identifier, state = rejected_candidate(setup)
    value, repair = correction(state)
    if field in {"question", "independent_oracle"}: value[field] += " Changed scientific scope."
    elif field == "research_claim": value[field]["scope"] += " A changed population."
    elif field == "parameters": value[field]["fixture_size"] += 1
    elif field == "seeds": value[field] = [13, 41]
    elif field == "conditions": value[field][1] = "different-comparator"
    elif field == "metrics": value[field][0]["description"] += " A different measurement objective."
    elif field == "validation_contract": value[field]["oracle_sources"][0]["quote"] += " Altered oracle reference."
    else: value[field].append("not-a-frozen-source.js")
    before = retained_bytes(service, identifier)
    with pytest.raises(WorkflowError) as denied: service.submit_redesign_proposal(identifier, value, preparation_repair=repair)
    assert denied.value.code == "PREPARATION_REPAIR_INVALID"
    assert retained_bytes(service, identifier) == before and runner.calls == 0


@pytest.mark.parametrize("defect", ["missing_issue", "wrong_issue", "unchanged_field", "uncovered_field", "candidate_hash", "review_hash", "parent_repair"])
def test_exact_issue_coverage_actual_diff_and_original_hashes_are_required(setup, defect):
    service, runner, identifier, state = rejected_candidate(setup)
    value, repair = correction(state)
    old_parent_repair = None
    if defect == "missing_issue": repair["changes"].pop()
    elif defect == "wrong_issue": repair["changes"][0]["required_change"] += " Different requirement."
    elif defect == "unchanged_field": value["analysis_method"] = state["redesign_candidate"]["analysis_method"]
    elif defect == "uncovered_field": repair["changes"][1]["changed_fields"] = ["procedure"]
    elif defect == "candidate_hash": repair["original_candidate_sha256"] = "0" * 64
    elif defect == "review_hash": repair["prior_review_sha256"] = "0" * 64
    else:
        old_parent_repair = copy.deepcopy(state["redesign_repair"]["value"])
        old_parent_repair["changes"][0]["actual_change"] += " Rewritten prior scientific repair."
    before = retained_bytes(service, identifier)
    with pytest.raises(WorkflowError) as denied:
        service.submit_redesign_proposal(identifier, value, old_parent_repair, preparation_repair=repair)
    assert denied.value.code == "PREPARATION_REPAIR_INVALID"
    assert retained_bytes(service, identifier) == before and runner.calls == 0


def test_second_rejection_is_immutable_and_never_creates_child_or_science(setup):
    service, runner, identifier, original = rejected_candidate(setup)
    value, repair = correction(original)
    service.submit_redesign_proposal(identifier, value, preparation_repair=repair)
    rejected = review(); rejected.update(accepted=False, issues=ISSUES)
    rejected["feasibility"]["passed"] = False
    state = service.submit_redesign_review(identifier, rejected)
    before = retained_bytes(service, identifier)
    assert not state["redesign_operational_repair_available"] and not state["preparation_redesign_available"]
    replacement = copy.deepcopy(value); replacement["analysis_method"] += " A second rewrite."
    for action in (lambda: service.submit_redesign_proposal(identifier, replacement, preparation_repair=repair),
                   lambda: service.submit_redesign_review(identifier, review()), lambda: service.redesign_study(identifier),
                   lambda: service.submit_code(identifier, BUNDLE, REVIEW), lambda: service.start_experiment(identifier)):
        with pytest.raises(WorkflowError): action()
    assert retained_bytes(service, identifier) == before and runner.calls == 0


def test_accepted_correction_forks_exact_revision_with_all_originals_and_fresh_child_gates(setup):
    service, runner, identifier, original = rejected_candidate(setup)
    old = frozen_bytes(service, identifier, original)
    value, repair = correction(original)
    staged = service.submit_redesign_proposal(identifier, value, preparation_repair=repair)
    assessed = service.submit_redesign_review(identifier, review())
    raw_review = json.loads(service.artifact_path(identifier, PREPARATION_REVISION_KEYS[1]).read_bytes())
    assert raw_review["preparation_repair_sha256"] == staged["artifacts"][PREPARATION_REVISION_KEYS[2]]["sha256"]
    child = service.redesign_study(identifier); child_id = child["id"]
    assert child["proposal"] == value and child["submission_contract"] is None and child["study_review"] is None
    assert child["artifacts"]["proposal-1"]["sha256"] == staged["artifacts"][PREPARATION_REVISION_KEYS[0]]["sha256"]
    assert tuple(child[name] for name in COUNTERS) == (1, 0, 0, 0, 0, 1)
    for key, raw in old.items():
        assert service.artifact_path(identifier, key).read_bytes() == raw
        if not key.startswith("prior-study-") and key not in {"context", "source-collection"} and not key.startswith("supporting-document-"):
            assert service.artifact_path(child_id, "prior-study-" + identifier + "-" + key).read_bytes() == raw
    service.collector = collect_arxiv_preprint
    collected = service.collect_literature(child_id)
    assessment = fresh_review(value, collected)
    with pytest.raises(WorkflowError) as denied: service.submit_study_review(child_id, assessment)
    assert denied.value.code == "SUBMISSION_CONTRACT_REQUIRED"
    service.set_submission_contract(child_id, own_contract(value))
    assert service.submit_study_review(child_id, assessment)["stage"] == "planned"
    assert tuple(service.status(identifier)[name] for name in COUNTERS) == (3, 2, 0, 0, 0, 0) and runner.calls == 0


@pytest.mark.parametrize("value", [None, [], "not-an-object"])
def test_ipc_preparation_repair_is_an_optional_strict_object(value):
    raw = json.dumps({"id": "test", "method": "workflow.submitRedesignProposal",
                      "params": {"researchId": "research-0123456789ab", "value": {}, "preparationRepair": value}}).encode()
    with pytest.raises(ValueError, match="JSON objects"): ipc.request(raw)

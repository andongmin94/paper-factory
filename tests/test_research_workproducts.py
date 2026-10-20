"""Concrete source comparison and phased protocol outputs, never merit scores."""

from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from paper_factory.autonomous import finite_rules
from paper_factory.autonomous.research_workproducts import ResearchWorkProducts, check_work_products

TEXT = "Synthetic source-bound fixture only; no actual implementation or research claim is asserted."
SOURCE = {"synthetic-handler"}


def decision(support, refs=()):
    return {"id": "decision-one", "condition": TEXT, "prior_method_evidence_ids": [],
            "baseline_decision": "Retain the observed destination-selection boundary.", "additional_analysis": TEXT,
            "changed_decision": "Distinguish pending request identities before choosing an admission policy.",
            "support_ids": support, "result_refs": list(refs), "limitations": [TEXT]}


@pytest.fixture
def comparison():
    return {"products": [{"id": "source-choice", "kind": "source_comparison", "reader_decision": TEXT,
        "shared_requirements": [TEXT + " Same required outcome."], "common_conditions": [TEXT + " Same workload."],
        "criteria": [{"id": "boundary", "question": TEXT}],
        "alternatives": [{"id": name, "label": TEXT + " " + name, "implementation_status": status,
                          "evidence_ids": list(SOURCE), "implementation_steps": [TEXT + " Execute " + name + " phase."],
                          "costs": [TEXT + " Additional ownership work."],
                          "applicability_conditions": [TEXT + " Bounded source scope."]}
                         for name, status in [("current", "retained_source"), ("proposed", "proposed_change")]],
        "observations": [{"id": "observation-" + name, "alternative_id": name, "criterion_id": "boundary",
                          "observation": TEXT + " " + name, "evidence_ids": list(SOURCE)} for name in ["current", "proposed"]],
        "changed_decisions": [decision(["observation-current", "observation-proposed"])], "limitations": [TEXT]}]}


def predicate(name, value):
    return {"left": {"variable": name}, "op": "eq", "right": {"literal": value}}


def effect(name, value):
    return {"variable": name, "value": {"literal": value}, "delta": 0}


def rule(identifier, guards, effects):
    return {"id": identifier, "event": TEXT, "guard": guards, "effects": effects, "evidence_ids": list(SOURCE),
            "implementation_mapping": TEXT, "abstraction_assumption": TEXT}


@pytest.fixture
def protocol():
    rules = [rule("offer-one", [predicate("incoming", "empty")], [effect("incoming", "r1")]),
             rule("offer-two", [predicate("incoming", "r1")], [effect("incoming", "r2")]),
             rule("offer-three", [predicate("incoming", "r2")], [effect("incoming", "r3")]),
             rule("check", [predicate("phase", "ready"), predicate("incoming", "r3"), predicate("queued", "r2")],
                  [effect("phase", "checked")]),
             rule("start", [predicate("phase", "checked"), predicate("incoming", "r3"), predicate("queued", "r2")],
                  [effect("phase", "started"), effect("queued", "r2")]),
             rule("complete", [predicate("phase", "started")], [effect("phase", "settled")])]
    case = {"id": "request-choice", "decision_problem": TEXT, "policy": TEXT,
        "variables": {"incoming": ["empty", "r1", "r2", "r3"], "queued": ["empty", "r2", "r3"],
                      "inflight": ["empty", "r1"], "phase": ["ready", "checked", "started", "settled"]},
        "initial": {"incoming": "empty", "queued": "r2", "inflight": "r1", "phase": "ready"},
        "invariants": [{"id": "pending-kept", "description": TEXT, "if_all": [predicate("phase", "started")],
                        "then_all": [predicate("queued", "r2")]}],
        "coverage": [{"id": "three-requests", "description": TEXT,
                      "conditions": [predicate("incoming", "r3"), predicate("queued", "r2"), predicate("inflight", "r1")], "required": True},
                     {"id": "settled", "description": TEXT, "conditions": [predicate("phase", "settled")], "required": True}],
        "alternatives": [{"id": name, "label": TEXT, "implementation_status": "proposal", "rules": deepcopy(rules),
                          "assumptions": [TEXT], "costs": [TEXT]} for name in ("reject", "preserve")],
        "negative_controls": [{"id": "overwrite-ordinary-request", "alternative_id": "reject", "rule_id": "start",
                               "kind": "replace_effect", "guard_index": None, "effect": effect("queued", "r3"),
                               "expected_invariant_id": "pending-kept", "explanation": TEXT}],
        "condition_flips": [{"id": "no-arrival", "description": TEXT, "initial_overrides": {"phase": "settled"},
                             "alternative_id": "reject", "property_id": "pending-kept"}],
        "decision_findings": [TEXT], "limits": [TEXT]}
    steps = []
    for name in ("reject", "preserve"):
        for identifier, kind, before, after, indexes, variables in [
            ("check", "check", "ready", "checked", [0, 1, 2], ["phase"]),
            ("start", "native_start", "checked", "started", [0, 1, 2], ["phase", "queued"]),
            ("complete", "completion", "started", "settled", [0], ["phase"])]:
            steps.append({"id": name + "-" + identifier, "alternative_id": name, "rule_id": identifier, "actor_id": "owner",
                "kind": kind, "phase_variable": "phase", "from_phase": before, "to_phase": after,
                "guard_indexes": indexes, "effect_variables": variables, "instruction": TEXT,
                "implementation_status": "proposed_change", "evidence_ids": list(SOURCE), "failure_outcome": TEXT})
    ref = {"alternative_id": "reject", "kind": "negative_control", "result_id": "overwrite-ordinary-request",
           "trace": ["offer-one", "offer-two", "offer-three", "check", "start"]}
    product = {"id": "request-protocol", "kind": "typed_protocol", "reader_decision": TEXT, "case_id": case["id"],
        "actors": [{"id": "owner", "responsibility": TEXT, "trusted_by_design": True, "evidence_ids": list(SOURCE)}],
        "state_ownership": [{"variable": name, "actor_id": "owner", "role": "owned_state", "evidence_ids": list(SOURCE)} for name in case["variables"]],
        "requests": [{"id": "r" + str(n), "resource_id": "same-path", "payload_revision": n, "owner_generation": "generation-a"} for n in range(1, 4)],
        "request_identity": {"incoming_variable": "incoming", "queued_variable": "queued", "inflight_variable": "inflight", "empty_id": "empty"},
        "service_contract": {"id": "each-accepted-operation", "semantics": "each_request", "allow_rejection": True,
                             "allowed_supersessions": [], "required_property_ids": ["pending-kept", "settled"], "rationale": TEXT, "evidence_ids": list(SOURCE)},
        "workload": {"offered_requests": ["r1", "r2", "r3"], "environment_rule_ids": ["offer-one", "offer-two", "offer-three"],
                     "identity_coverage": {"alternative_id": "reject", "kind": "coverage", "result_id": "three-requests",
                                           "trace": ["offer-one", "offer-two", "offer-three"]}, "scope": TEXT},
        "admission_choices": [{"alternative_id": name, "policy": "reject_new" if name == "reject" else "preserve_pending",
                               "rationale": TEXT, "evidence_ids": list(SOURCE)} for name in ("reject", "preserve")],
        "steps": steps,
        "atomic_obligations": [{"id": name + "-start-boundary", "alternative_id": name, "check_step_ids": [name + "-check"],
                                "start_step_id": name + "-start", "mechanism": "unresolved", "justification": TEXT,
                                "evidence_ids": list(SOURCE), "unresolved_reason": "Actual scheduling and trusted ownership remain unimplemented."} for name in ("reject", "preserve")],
        "changed_decisions": [decision(["reject-start", "preserve-start"], [ref])], "limitations": [TEXT]}
    return {"products": [product]}, [case]


def test_source_only_comparison_produces_complete_matrix_and_decisions_without_fake_novelty(comparison):
    original = deepcopy(comparison)
    result = check_work_products(comparison, SOURCE, set())
    assert result == check_work_products(comparison, SOURCE, set())
    product = result["products"][0]
    assert len(product["matrix"]) == 2 and len(product["decision_table"]) == 1
    assert "| Alternative | Criterion |" in result["markdown"]
    assert "Retain the observed" in result["markdown"] and "Distinguish pending" in result["markdown"]
    assert "1. " + TEXT + " Execute proposed phase." in result["markdown"]
    assert "Cost: " + TEXT in result["markdown"] and "Applies when: " + TEXT in result["markdown"]
    assert "Implementation status: proposed_change" in result["markdown"]
    assert "Shared requirement: " in result["markdown"] and "Common comparison condition: " in result["markdown"]
    assert any("novelty" in limit for limit in result["evidence_limits"])
    assert result["internal_consistency_passed"] and result["audit_required"]
    assert not result["implementation_validated"] and not result["publication_quality_assessed"]
    assert result["cases_sha256"] is result["checker_sha256"] is None
    assert comparison == original


@pytest.mark.parametrize("damage", ["unknown-witness", "missing-cell", "duplicate-cell", "unknown-support", "invented-prior"])
def test_comparison_rejects_invented_or_empty_concrete_outputs(comparison, damage):
    product = comparison["products"][0]
    if damage == "unknown-witness": product["observations"][0]["evidence_ids"] = ["invented"]
    elif damage == "missing-cell": product["observations"].pop()
    elif damage == "duplicate-cell": product["observations"][1]["alternative_id"] = "current"
    elif damage == "unknown-support": product["changed_decisions"][0]["support_ids"] = ["invented"]
    else: product["changed_decisions"][0]["prior_method_evidence_ids"] = ["invented"]
    with pytest.raises(ValueError):
        check_work_products(comparison, SOURCE, set())


def test_confirming_existing_decision_is_an_honest_negative_result_not_a_forced_claim(comparison):
    row = comparison["products"][0]["changed_decisions"][0]
    row["changed_decision"] = row["baseline_decision"]
    result = check_work_products(comparison, SOURCE, set())
    assert result["products"][0]["decision_table"][0]["decision_changed"] is False
    assert any("no additional engineering decision" in limit for limit in result["evidence_limits"])
    assert result["internal_consistency_passed"] and result["audit_required"]
    assert "substantive additional value requires independent audit" in result["decision_changed_scope"]


def test_real_native_three_distinct_same_resource_requests_and_phase_results_produce_dossier(protocol):
    packet, cases = protocol
    original = deepcopy((packet, cases))
    result = check_work_products(packet, SOURCE, set(), cases=cases)
    product = result["products"][0]
    assert product["identity_witness"]["state"] == {"incoming": "r3", "queued": "r2", "inflight": "r1", "phase": "ready"}
    assert len(product["dossier"]) == 6 and "Actual finite phase" in result["markdown"]
    assert product["decision_table"][0]["result_outcomes"][0]["status"] == "caught"
    assert product["decision_table"][0]["result_outcomes"][0]["trace"][-1] == "start"
    assert sum("Unresolved atomic boundary" in limit for limit in result["evidence_limits"]) == 2
    assert (packet, cases) == original
    # Exact reachable-instance/provenance receipts are retained rather than hidden.
    assert len(json.dumps(result)) < 36000


@pytest.mark.parametrize("damage", ["resource-alias", "different-resource", "empty-alias", "fake-trace", "fake-result", "missing-phase",
                                    "missing-guard", "missing-effect", "missing-owner", "unequal-workload", "unoffered-request", "atomic-no-reason", "terminal-absent"])
def test_protocol_rejects_unbound_identity_phase_workload_or_atomic_claims(protocol, damage):
    packet, cases = protocol
    product = packet["products"][0]
    if damage == "resource-alias": cases[0]["variables"]["queued"] = ["empty", "same-path"]; cases[0]["initial"]["queued"] = "same-path"
    elif damage == "different-resource": product["requests"][2]["resource_id"] = "other-path"
    elif damage == "empty-alias": product["request_identity"]["empty_id"] = "r1"
    elif damage == "fake-trace": product["changed_decisions"][0]["result_refs"][0]["trace"] = ["start"]
    elif damage == "fake-result": product["changed_decisions"][0]["result_refs"][0]["result_id"] = "invented-result"
    elif damage == "missing-phase": product["steps"][0]["from_phase"] = "settled"
    elif damage == "missing-guard": product["steps"][0]["guard_indexes"] = [0]
    elif damage == "missing-effect": product["steps"][1]["effect_variables"] = ["phase"]
    elif damage == "missing-owner": product["state_ownership"].pop()
    elif damage == "unequal-workload": cases[0]["alternatives"][1]["rules"][0]["guard"].append(predicate("phase", "ready"))
    elif damage == "unoffered-request": product["workload"]["environment_rule_ids"].pop()
    elif damage == "atomic-no-reason": product["atomic_obligations"][0]["unresolved_reason"] = ""
    else: product["steps"] = [item for item in product["steps"] if item["kind"] != "completion"]
    with pytest.raises(ValueError):
        check_work_products(packet, SOURCE, set(), cases=cases)


def test_coalescing_is_conditioned_on_explicit_newer_snapshot_not_automatically_a_bug(protocol):
    packet, cases = protocol
    product = packet["products"][0]
    product["service_contract"].update(semantics="latest_snapshot", allowed_supersessions=[{"older_request": "r2", "newer_request": "r3"}])
    product["admission_choices"][1]["policy"] = "coalesce_latest"
    result = check_work_products(packet, SOURCE, set(), cases=cases)
    assert result["products"][0]["service_contract"]["semantics"] == "latest_snapshot"
    product["service_contract"]["semantics"] = "each_request"
    incompatible = check_work_products(packet, SOURCE, set(), cases=cases)
    assert {item["kind"] for item in incompatible["conflicts"]} == {"each_request_supersession", "coalescing_not_authorized"}
    assert incompatible["products"][0]["decision_table"] == result["products"][0]["decision_table"]
    assert any("Policy/contract conflict" in limit for limit in incompatible["evidence_limits"])


@pytest.mark.parametrize("damage", ["older-payload", "different-generation", "different-resource", "unknown-request"])
def test_contract_rejects_unjustified_loss_or_incomparable_snapshot_replacement(protocol, damage):
    packet, cases = protocol
    product = packet["products"][0]
    product["service_contract"].update(semantics="latest_snapshot", allowed_supersessions=[{"older_request": "r2", "newer_request": "r3"}])
    product["admission_choices"][1]["policy"] = "coalesce_latest"
    if damage == "older-payload": product["requests"][2]["payload_revision"] = 1
    elif damage == "different-generation": product["requests"][2]["owner_generation"] = "generation-b"
    elif damage == "different-resource": product["requests"][1]["resource_id"] = "other-path"
    else: product["service_contract"]["allowed_supersessions"][0]["older_request"] = "invented-request"
    with pytest.raises(ValueError):
        check_work_products(packet, SOURCE, set(), cases=cases)


def test_supplied_checker_is_not_trusted_over_actual_rules_or_witness_trace(protocol):
    packet, cases = protocol
    checker = finite_rules.check_evidence({"source_evidence": [{"id": "synthetic-handler"}], "cases": cases}, SOURCE)
    assert check_work_products(packet, SOURCE, set(), cases=cases, checker=checker)["internal_consistency_passed"]
    checker["cases"][0]["alternatives"][0]["edge_count"] += 1
    with pytest.raises(ValueError, match="recomputed cases"):
        check_work_products(packet, SOURCE, set(), cases=cases, checker=checker)


def test_model_can_reference_native_results_before_execution_without_predicting_bfs_trace(protocol):
    packet, cases = protocol
    explicit = check_work_products(packet, SOURCE, set(), cases=cases)
    product = packet["products"][0]
    del product["workload"]["identity_coverage"]["trace"]
    product["changed_decisions"][0]["result_refs"][0]["trace"] = None
    resolved = check_work_products(packet, SOURCE, set(), cases=cases)
    assert resolved["products"] == explicit["products"]
    assert resolved["products"][0]["identity_witness"]["trace"] == ["offer-one", "offer-two", "offer-three"]
    assert resolved["products"][0]["decision_table"][0]["result_outcomes"][0]["trace"][-2:] == ["check", "start"]
    product["workload"]["identity_coverage"]["trace"] = []
    with pytest.raises(ValueError, match="exactly equal"):
        check_work_products(packet, SOURCE, set(), cases=cases)


def test_explicit_empty_trace_remains_valid_for_an_actual_initial_state_witness(protocol):
    packet, cases = protocol
    cases[0]["coverage"].append({"id": "initial-case", "description": TEXT,
                                "conditions": [predicate("incoming", "empty")], "required": False})
    packet["products"][0]["changed_decisions"][0]["result_refs"] = [
        {"alternative_id": "reject", "kind": "coverage", "result_id": "initial-case", "trace": []}]
    report = check_work_products(packet, SOURCE, set(), cases=cases)
    assert report["products"][0]["decision_table"][0]["result_outcomes"][0]["trace"] == []


@pytest.mark.parametrize("conflict", ["coalescing-without-supersession", "rejection-forbidden"])
def test_incompatible_policy_alternatives_remain_reportable_separately_from_finite_results(protocol, conflict):
    packet, cases = protocol
    product = packet["products"][0]
    baseline = check_work_products(packet, SOURCE, set(), cases=cases)
    if conflict == "coalescing-without-supersession":
        product["admission_choices"][1]["policy"] = "coalesce_latest"
        expected = "coalescing_not_authorized"
    else:
        product["service_contract"]["allow_rejection"] = False
        expected = "rejection_not_authorized"
    result = check_work_products(packet, SOURCE, set(), cases=cases)
    assert result["internal_consistency_passed"] and result["audit_required"]
    assert not result["implementation_validated"] and not result["publication_quality_assessed"]
    assert result["products"][0]["decision_table"] == baseline["products"][0]["decision_table"]
    assert result["conflicts"][0]["kind"] == expected
    assert "Policy/contract conflict" in result["markdown"]


def test_actual_coalescing_under_each_request_contract_retains_failed_finite_outcome_and_conflict(protocol):
    packet, cases = protocol
    product = packet["products"][0]
    product["admission_choices"][1]["policy"] = "coalesce_latest"
    start = next(rule for rule in cases[0]["alternatives"][1]["rules"] if rule["id"] == "start")
    start["effects"][1] = effect("queued", "r3")  # Actually replace pending r2, rather than change only a label.
    product["changed_decisions"][0]["result_refs"].append(
        {"alternative_id": "preserve", "kind": "invariant", "result_id": "pending-kept"})
    result = check_work_products(packet, SOURCE, set(), cases=cases)
    outcomes = result["products"][0]["decision_table"][0]["result_outcomes"]
    assert outcomes[0]["status"] == "caught"
    assert outcomes[1]["status"] == "failed" and outcomes[1]["trace"][-2:] == ["check", "start"]
    assert result["conflicts"][0]["alternative_id"] == "preserve"
    assert result["conflicts"][0]["kind"] == "coalescing_not_authorized"
    assert result["audit_required"] and not result["implementation_validated"]


def test_missing_cases_or_model_authored_pass_flags_do_not_manufacture_outputs(protocol, comparison):
    packet, _ = protocol
    with pytest.raises(ValueError, match="actual finite cases"):
        check_work_products(packet, SOURCE, set())
    comparison["products"][0]["implementation_validated"] = True
    with pytest.raises(ValidationError):
        ResearchWorkProducts.model_validate(comparison)


def test_three_distinct_requests_are_expressed_in_the_schema_before_generation(protocol):
    packet, _ = protocol
    packet["products"][0]["requests"].pop()
    with pytest.raises(ValidationError):
        ResearchWorkProducts.model_validate(packet)


@pytest.mark.parametrize("damage", ["not-check-kind", "different-actor", "different-phase"])
def test_atomic_obligation_cannot_mislabel_a_start_or_an_unrelated_check(protocol, damage):
    packet, cases = protocol
    product = packet["products"][0]
    if damage == "not-check-kind":
        product["atomic_obligations"][0]["check_step_ids"] = ["reject-start"]
    elif damage == "different-actor":
        actor = deepcopy(product["actors"][0]); actor["id"] = "other-owner"
        product["actors"].append(actor)
        product["steps"][0]["actor_id"] = "other-owner"
    else:
        product["steps"].append({**deepcopy(product["steps"][0]), "id": "incoming-check", "rule_id": "offer-three",
                                "phase_variable": "incoming", "from_phase": "r2", "to_phase": "r3",
                                "guard_indexes": [0], "effect_variables": ["incoming"]})
        product["atomic_obligations"][0]["check_step_ids"] = ["incoming-check"]
    with pytest.raises(ValueError, match="explicit check steps"):
        check_work_products(packet, SOURCE, set(), cases=cases)


def test_unmapped_rules_and_one_alternative_missing_terminal_are_exposed_not_declared_complete(protocol):
    packet, cases = protocol
    product = packet["products"][0]
    product["steps"] = [step for step in product["steps"] if step["id"] != "preserve-complete"]
    report = check_work_products(packet, SOURCE, set(), cases=cases)
    assert any("Unmapped source/protocol rules for preserve:" in limit and "complete" in limit for limit in report["evidence_limits"])
    assert any("No mapped terminal" in limit and "preserve" in limit for limit in report["evidence_limits"])
    assert report["audit_required"] and not report["implementation_validated"]

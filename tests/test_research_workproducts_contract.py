"""Actual contract defects reproduced with bounded synthetic source-bound inputs."""
from copy import deepcopy
import pytest

from test_research_workproducts import comparison, protocol, SOURCE, predicate
from paper_factory.autonomous.research_workproducts import check_work_products
from paper_factory.autonomous import finite_rules


def computed_comparison(comparison):
    product = comparison["products"][0]
    product["observations"][0]["evidence_ids"] = ["synthetic-handler", "start", "settled"]
    product["observations"][1]["evidence_ids"] = ["primary-method", "pending-kept"]
    product["changed_decisions"][0]["support_ids"] = ["observation-current", "start", "settled", "synthetic-handler", "primary-method"]
    product["changed_decisions"][0]["result_refs"] = [{"alternative_id": "reject", "kind": "negative_control", "result_id": "overwrite-ordinary-request", "trace": None}]
    source_only = deepcopy(product["changed_decisions"][0])
    source_only.update(id="source-only", support_ids=["synthetic-handler"], result_refs=[])
    product["changed_decisions"].append(source_only)
    return comparison


def test_computed_matrix_binds_one_exact_native_case_without_promoting_models_to_source(comparison, protocol):
    _, cases = protocol
    packet = computed_comparison(comparison)
    original = deepcopy((packet, cases))
    checker = finite_rules.check_evidence({"source_evidence": [{"id": identifier} for identifier in SOURCE], "cases": cases}, SOURCE)
    result = check_work_products(packet, SOURCE, {"primary-method"}, cases=cases, checker=checker)
    product = result["products"][0]
    assert product["native_case_binding"]["case_id"] == cases[0]["id"]
    assert product["native_case_binding"]["case_input_sha256"] == finite_rules.canonical_sha(cases[0])
    bindings = product["decision_table"][0]["support_bindings"]
    assert {item["kind"] for item in bindings} == {"comparison_observation", "model_definition", "repository_source_witness", "retained_document_witness"}
    assert all("not a repository quotation" in item["scope"] for item in bindings if item["kind"] == "model_definition")
    outcome = product["decision_table"][0]["result_outcomes"][0]
    assert outcome["status"] == "caught" and outcome["trace"][-2:] == ["check", "start"]
    assert product["decision_table"][1]["result_outcomes"] == []
    assert result["cases_sha256"] == finite_rules.canonical_sha(cases)
    assert not result["implementation_validated"] and not result["publication_quality_assessed"]
    assert (packet, cases) == original


@pytest.mark.parametrize("damage", ["unknown-model", "unknown-support", "wrong-result-kind", "fake-trace", "ambiguous-case", "missing-case", "namespace-collision"])
def test_computed_matrix_rejects_missing_ambiguous_or_invented_bindings(comparison, protocol, damage):
    _, cases = protocol
    packet = computed_comparison(comparison)
    product = packet["products"][0]
    sources = set(SOURCE)
    if damage == "unknown-model": product["observations"][0]["evidence_ids"].append("invented-rule")
    elif damage == "unknown-support": product["changed_decisions"][0]["support_ids"].append("invented-support")
    elif damage == "wrong-result-kind": product["changed_decisions"][0]["result_refs"][0]["kind"] = "coverage"
    elif damage == "fake-trace": product["changed_decisions"][0]["result_refs"][0]["trace"] = ["start"]
    elif damage == "ambiguous-case":
        other = deepcopy(cases[0]); other["id"] = "other-case"; cases.append(other)
    elif damage == "missing-case": cases = None
    else: sources.add("start")
    with pytest.raises(ValueError):
        check_work_products(packet, sources, {"primary-method"}, cases=cases)


def test_same_environment_semantics_accept_different_explanations(protocol):
    packet, cases = protocol
    rule = cases[0]["alternatives"][1]["rules"][0]
    rule.update(event="Different environment explanation describes the same offered request.",
                implementation_mapping="The same environment rule is explained differently here.",
                abstraction_assumption="Different explanatory prose does not change guard or effects.")
    original = deepcopy((packet, cases))
    report = check_work_products(packet, SOURCE, set(), cases=cases)
    assert report["internal_consistency_passed"]
    declaration = report["products"][0]["common_environment_bindings"][0]
    assert declaration["alternative_declarations"][1]["rule"]["event"] == rule["event"]
    assert "assumptions are preserved" in declaration["scope"]
    assert (packet, cases) == original


@pytest.mark.parametrize("damage", ["id", "guard", "effects"])
def test_same_environment_still_rejects_different_actual_rules(protocol, damage):
    packet, cases = protocol
    rule = cases[0]["alternatives"][1]["rules"][0]
    if damage == "id": rule["id"] = "different-offer"
    elif damage == "guard": rule["guard"].append(predicate("phase", "ready"))
    else: rule["effects"][0]["value"]["literal"] = "r2"
    with pytest.raises(ValueError, match="same declared environment rules"):
        check_work_products(packet, SOURCE, set(), cases=cases)


def test_inequality_and_variable_copy_phase_is_only_an_exact_reachable_instance(protocol):
    packet, cases = protocol
    product = packet["products"][0]
    alternative = cases[0]["alternatives"][0]
    start = next(rule for rule in alternative["rules"] if rule["id"] == "start")
    start["guard"][2]["op"] = "ne";start["guard"][2]["right"]["literal"] = "empty"
    start["effects"][1]["value"] = {"variable": "queued"}
    for step in product["steps"]:
        if step["id"] in {"reject-start", "reject-check"}:
            step.update(phase_variable="queued", from_phase="r2", to_phase="r2")
    report = check_work_products(packet, SOURCE, set(), cases=cases)
    row = next(item for item in report["products"][0]["dossier"] if item["id"] == "reject-start")
    witness = row["phase_witness"]
    assert witness["edge"]["rule_id"] == "start" and witness["from_state"]["queued"] == witness["to_state"]["queued"] == "r2"
    assert row["phase_scope"] == "reachable_instance_not_universal"
    assert "One reachable instance, not a universal guarantee" in witness["scope"]
    assert not report["implementation_validated"]
    product["steps"][1]["from_phase"] = "r3"
    with pytest.raises(ValueError, match="reachable native rule-edge"):
        check_work_products(packet, SOURCE, set(), cases=cases)


def test_check_and_native_descriptions_group_one_atomic_rule_without_fake_events(protocol):
    packet, cases = protocol
    product = packet["products"][0]
    step = deepcopy(product["steps"][1]);step.update(id="reject-same-rule-check", kind="check")
    product["steps"].append(step)
    product["atomic_obligations"][0]["check_step_ids"] = [step["id"]]
    report = check_work_products(packet, SOURCE, set(), cases=cases)
    group = next(item for item in report["products"][0]["transition_role_groups"] if item["alternative_id"] == "reject" and item["rule_id"] == "start")
    assert group["step_ids"] == ["reject-start", "reject-same-rule-check"]
    assert "not separate events, an await gap or implementation atomicity proof" in group["scope"]
    duplicate = deepcopy(step);duplicate["id"] = "second-same-role";product["steps"].append(duplicate)
    with pytest.raises(ValueError, match="rule roles"):
        check_work_products(packet, SOURCE, set(), cases=cases)


def test_proposal_document_binding_is_distinct_and_actual_source_substitution_is_rejected(protocol):
    _, cases = protocol
    value = {"source_evidence": [{"id": identifier} for identifier in SOURCE],
             "document_evidence": [{"source_id": "primary-method"}], "cases": cases}
    cases[0]["alternatives"][0]["rules"][0]["evidence_ids"].append("primary-method")
    report = finite_rules.check_evidence(value, SOURCE, document_witness_ids={"primary-method"})
    row = report["cases"][0]["rule_evidence_bindings"][0]
    assert {item["kind"] for item in row["references"]} == {"repository_source_witness", "retained_document_witness"}
    assert "not a repository quotation or implemented effect" in row["references"][1]["scope"]
    with pytest.raises(ValueError, match="unverified retained document"):
        finite_rules.check_evidence(value, SOURCE, document_witness_ids={"other-method"})
    cases[0]["alternatives"][0]["implementation_status"] = "actual"
    with pytest.raises(ValueError, match="Actual implementation rules require"):
        finite_rules.check_evidence(value, SOURCE, document_witness_ids={"primary-method"})


def test_protocol_model_support_is_classified_without_becoming_a_source_quote(protocol):
    packet, cases = protocol
    product = packet["products"][0]
    product["admission_choices"][0]["evidence_ids"] = ["start", "primary-method"]
    product["changed_decisions"][0]["support_ids"] += ["start", "pending-kept", "synthetic-handler"]
    report = check_work_products(packet, SOURCE, {"primary-method"}, cases=cases)
    rows = report["products"][0]["protocol_evidence_bindings"]
    row = next(item for item in rows if item["field"] == "admission_choices" and item["record_id"] == "reject")
    assert {item["kind"] for item in row["references"]} == {"model_definition", "retained_document_witness"}
    assert "not a repository quotation" in row["references"][0]["scope"]
    product["admission_choices"][0]["evidence_ids"].append("made-up")
    with pytest.raises(ValueError):
        check_work_products(packet, SOURCE, {"primary-method"}, cases=cases)

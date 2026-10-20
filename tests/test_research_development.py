"""Finite-rule analysis produces evidence, never executes the research project."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from paper_factory.autonomous import finite_rules
from paper_factory.autonomous.research_development import DevelopmentEvidence, DevelopmentAudit, check_development_evidence, development_next_task, determine_audit_repair


def var(name):
    return {"variable": name}


def literal(value):
    return {"literal": value}


def pred(name, op, right):
    return {"left": var(name), "op": op, "right": right}


def effect(name, value, delta=0):
    return {"variable": name, "value": value, "delta": delta}


def rule(identifier, guard, effects):
    return {"id": identifier, "event": "Synthetic bounded event " + identifier, "guard": guard, "effects": effects,
            "evidence_ids": ["synthetic-handler"], "implementation_mapping": "Explicitly synthetic correspondence; no actual implementation is asserted.",
            "abstraction_assumption": "Trusted synthetic event source and simultaneous finite updates only."}


@pytest.fixture
def evidence():
    valid = [pred("pending", "eq", literal(1)), pred("inflight", "eq", literal(0)), pred("grant", "eq", literal(True)),
             pred("recipient", "eq", var("current")), pred("clock", "lt", var("expiry")), pred("resource", "eq", var("selected")),
             pred("writes", "lt", literal(2))]
    rules = [
        rule("enable", [pred("grant", "eq", literal(False))], [effect("grant", literal(True)), effect("dispatch", literal(False))]),
        rule("enqueue", [pred("pending", "eq", literal(0))], [effect("pending", literal(1)), effect("dispatch", literal(False))]),
        rule("dispatch", valid, [effect("pending", literal(0)), effect("inflight", literal(1)), effect("dispatch", literal(True)), effect("resource", var("selected"))]),
        rule("complete", [pred("inflight", "eq", literal(1)), pred("writes", "lt", literal(2))], [effect("inflight", literal(0)), effect("writes", var("writes"), 1), effect("dispatch", literal(False))]),
        rule("invalidate", [pred("current", "eq", literal("a"))], [effect("current", literal("b")), effect("dispatch", literal(False))]),
        rule("tick", [pred("clock", "eq", literal(0))], [effect("clock", literal(1)), effect("dispatch", literal(False))]),
    ]
    ambient = deepcopy(rules)
    ambient[2]["guard"] = [valid[0], valid[1], valid[-1]]
    case = {"id": "bounded-editor", "decision_problem": "Synthetic decision between guarded and ambient repeated effects.",
            "policy": "Authorize each start, permit already-started completion, and bound pending work.",
            "variables": {"recipient": ["a", "b"], "current": ["a", "b"], "resource": ["file-a", "file-b"], "selected": ["file-a", "file-b"],
                          "clock": [0, 1], "expiry": [0, 1], "grant": [False, True], "pending": [0, 1], "inflight": [0, 1], "dispatch": [False, True], "writes": [0, 1, 2]},
            "initial": {"recipient": "a", "current": "a", "resource": "file-a", "selected": "file-a", "clock": 0, "expiry": 1,
                        "grant": False, "pending": 0, "inflight": 0, "dispatch": False, "writes": 0},
            "invariants": [{"id": "valid-start", "description": "A new effect must have a current recipient, selected resource and live grant.",
                            "if_all": [pred("dispatch", "eq", literal(True))], "then_all": valid[2:6]},
                           {"id": "pending-bound", "description": "The count of admitted waiting work remains bounded.", "if_all": [], "then_all": [pred("pending", "le", literal(1))]}],
            "coverage": [{"id": "busy-and-queued", "description": "A started request can coexist with a waiting request.", "conditions": [pred("inflight", "eq", literal(1)), pred("pending", "eq", literal(1))], "required": True},
                         {"id": "two-writes", "description": "The policy supports two completed writes in one live window.", "conditions": [pred("writes", "eq", literal(2))], "required": True}],
            "alternatives": [{"id": "guarded", "label": "Synthetic per-start guarded alternative", "implementation_status": "proposal", "rules": rules,
                              "assumptions": ["The start boundary and invalidation events are trusted."], "costs": ["Trusted state and queue accounting require implementation work."]},
                             {"id": "ambient", "label": "Synthetic ambient dispatch alternative", "implementation_status": "environment_assumption", "rules": ambient,
                              "assumptions": ["Eligible calls are accepted without per-use generation checks."], "costs": ["Resource and recipient lifetime risks are deliberately broader."]}],
            "negative_controls": [{"id": "remove-recipient-check", "alternative_id": "guarded", "rule_id": "dispatch", "kind": "remove_guard", "guard_index": 3,
                                   "effect": None, "expected_invariant_id": "valid-start", "explanation": "Remove recipient currency while preserving the remaining checks."},
                                  {"id": "change-resource-effect", "alternative_id": "guarded", "rule_id": "dispatch", "kind": "replace_effect", "guard_index": None,
                                   "effect": effect("resource", literal("file-b")), "expected_invariant_id": "valid-start", "explanation": "Retarget an admitted effect after its selected-resource guard."},
                                  {"id": "remove-expiry-check", "alternative_id": "guarded", "rule_id": "dispatch", "kind": "remove_guard", "guard_index": 4,
                                   "effect": None, "expected_invariant_id": "valid-start", "explanation": "Let a clock-advanced request begin after its authority expires."}],
            "condition_flips": [{"id": "already-expired", "description": "An expired starting window prevents repeated progress under the same safety policy.",
                                 "initial_overrides": {"clock": 1}, "alternative_id": "guarded", "property_id": "two-writes"}],
            "decision_findings": ["The selected lifetime and recipient premises distinguish usable alternatives."],
            "limits": ["This fixture has no real source semantics or empirical implementation guarantee."]}
    return {"method_scope": "generated_finite_rules_not_project_execution",
            "source_evidence": [{"id": "synthetic-handler", "path": "synthetic-only.ts", "sha256": "a" * 64,
                                 "quote": "Explicitly synthetic retained handler witness, not a real project.", "interpretation": "Synthetic API shape for native rule-checking tests only."}],
            "document_evidence": [], "cases": [case], "comparisons": [],
            "cross_case_findings": ["This synthetic case distinguishes authority at dispatch from existing inflight work."],
            "limitations": ["No imported project is executed and no scientific result is asserted by this fixture."]}


def test_generated_identity_resource_expiry_and_simultaneous_queue_states_are_real(evidence):
    original = deepcopy(evidence)
    result = check_development_evidence(evidence, {"synthetic-handler"}, include_graph=True)
    case = result["cases"][0]
    guarded, ambient = case["alternatives"]
    assert case["cartesian_state_bound"] == 3072
    assert all(item["status"] == "passed" for item in guarded["invariants"])
    assert next(item for item in ambient["invariants"] if item["id"] == "valid-start")["status"] == "failed"
    assert any(state["values"]["inflight"] == state["values"]["pending"] == 1 for state in guarded["generated_states"])
    assert len(guarded["generated_edges"]) == guarded["edge_count"]
    assert len(guarded["generated_states"]) == guarded["reachable_state_count"] > 10
    assert all(control["caught"] and control["rule_id"] in control["counterexample"]["transition_trace"] for control in case["negative_controls"])
    assert "tick" in case["negative_controls"][2]["counterexample"]["transition_trace"]
    assert guarded["meets_declared_requirements"] and not ambient["meets_declared_requirements"]
    assert case["alternative_comparisons"][0]["different_properties"] == ["valid-start"]
    assert case["condition_flips"][0]["decisive"] and case["condition_flips"][0]["changed_status"] == "unreachable"
    assert result["project_execution"] is False and result["audit_required"] is True
    assert evidence == original


def test_native_summary_does_not_dump_all_graphs_or_fake_counterexamples(evidence):
    result = check_development_evidence(evidence)
    assert "generated_states" not in result["cases"][0]["alternatives"][0]
    assert len(json.dumps(result)) < 20000
    assert result["input_sha256"] == finite_rules.canonical_sha(DevelopmentEvidence.model_validate(evidence).model_dump(mode="json"))


@pytest.mark.parametrize("damage", ["float-domain", "bool-int-domain", "bool-int-comparison", "unknown-variable", "too-many-states", "unknown-witness", "out-of-domain-effect"])
def test_unsafe_or_ill_typed_models_reject_before_claiming_checked_results(evidence, damage):
    case = evidence["cases"][0]
    if damage == "float-domain": case["variables"]["clock"] = [0.0, 1.0]
    elif damage == "bool-int-domain": case["variables"]["grant"] = [True, 1]
    elif damage == "bool-int-comparison": case["invariants"][0]["then_all"][0]["right"] = literal(1)
    elif damage == "unknown-variable": case["invariants"][0]["then_all"][0]["left"] = var("undeclared")
    elif damage == "too-many-states": case["variables"].update({"extra": [0, 1]}); case["initial"].update({"extra": 0})
    elif damage == "unknown-witness": case["alternatives"][0]["rules"][0]["evidence_ids"] = ["invented"]
    else: case["alternatives"][0]["rules"][0]["effects"][0] = effect("grant", literal("not-a-boolean"))
    with pytest.raises((ValueError, ValidationError)):
        check_development_evidence(evidence, {"synthetic-handler"})


def test_true_and_one_never_share_a_state_identity_or_comparison(evidence):
    assert finite_rules._same(True, 1) is False
    case = evidence["cases"][0]
    case["initial"]["grant"] = 0
    with pytest.raises(ValueError, match="exact typed initial"):
        check_development_evidence(evidence)


def test_simultaneous_effects_read_pre_state_and_do_not_depend_on_assignment_order(evidence):
    case = evidence["cases"][0]
    for alternative in case["alternatives"]:
        alternative["rules"].append(rule("swap-generations", [], [effect("recipient", var("current")), effect("current", var("recipient")), effect("dispatch", literal(False))]))
    forward = check_development_evidence(evidence, include_graph=True)
    for alternative in case["alternatives"]:
        alternative["rules"][-1]["effects"].reverse()
    backward = check_development_evidence(evidence, include_graph=True)
    assert forward["cases"] == backward["cases"]


def test_vacuous_properties_dead_rules_and_ineffective_mutations_are_not_success(evidence):
    case = evidence["cases"][0]
    case["invariants"].append({"id": "never-exercised", "description": "Deliberately unreachable antecedent must be exposed as vacuous.",
                               "if_all": [pred("clock", "eq", literal(9))], "then_all": [pred("grant", "eq", literal(True))]})
    case["alternatives"][0]["rules"].append(rule("never-enabled", [pred("clock", "eq", literal(9))], [effect("dispatch", literal(False))]))
    case["negative_controls"][0]["guard_index"] = 0  # Pending admission is not an authorization predicate.
    result = check_development_evidence(evidence)
    reported = result["cases"][0]
    assert not reported["negative_controls"][0]["caught"]
    assert any("Vacuous invariant" in issue for issue in result["issues"])
    assert "never-enabled" in reported["alternatives"][0]["dead_rules"]


def test_a_preexisting_baseline_violation_is_not_a_successful_negative_control(evidence):
    evidence["cases"][0]["negative_controls"][0]["alternative_id"] = "ambient"
    evidence["cases"][0]["negative_controls"][0]["guard_index"] = 0
    result = check_development_evidence(evidence)
    control = result["cases"][0]["negative_controls"][0]
    assert control["original_status"] == "failed" and not control["caught"]


def test_rule_escape_and_duplicate_effects_do_not_silently_clip_domains(evidence):
    case = evidence["cases"][0]
    case["alternatives"][0]["rules"][0]["effects"].append(effect("pending", literal(2)))
    with pytest.raises(ValueError, match="outside its finite domain"):
        check_development_evidence(evidence)
    case["alternatives"][0]["rules"][0]["effects"][-1] = effect("grant", literal(False))
    with pytest.raises(ValueError, match="more than once"):
        check_development_evidence(evidence)


def test_generated_edge_budget_is_enforced(evidence, monkeypatch):
    monkeypatch.setattr(finite_rules, "MAX_EDGES", 3)
    with pytest.raises(ValueError, match="20000-edge"):
        check_development_evidence(evidence)


def test_standard_library_replay_reproduces_exact_results_without_site_packages(tmp_path, evidence):
    script = tmp_path / "finite_rules.py"
    script.write_bytes(Path(finite_rules.__file__).read_bytes())
    source = tmp_path / "evidence.json"
    source.write_text(json.dumps(DevelopmentEvidence.model_validate(evidence).model_dump(mode="json")), encoding="utf-8")
    output = tmp_path / "replayed.json"
    run = subprocess.run([sys.executable, "-I", "-S", str(script), str(source), "--output", str(output)], capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stderr
    report = json.loads(output.read_bytes())
    assert report.pop("input_file_sha256") == hashlib.sha256(source.read_bytes()).hexdigest()
    assert report == check_development_evidence(evidence)
    rejected = subprocess.run([sys.executable, "-I", "-S", str(script), str(source), "--output", str(tmp_path / "must-not-exist.json"), "--expected-input-sha256", "0" * 64], capture_output=True, text=True, timeout=20)
    assert rejected.returncode != 0 and "expected frozen SHA-256" in rejected.stderr
    assert not (tmp_path / "must-not-exist.json").exists()


def round_state(done=(), calls=()):
    return {"finished": False, "calls": list(calls), "research_development": {"id": "research-development-round-1", "closed": False,
            "additional_call_limit": 6, "completed_stages": list(done), "repair_required": False}}


def call(stage, outcome="completed"):
    return {"call_id": "call-" + stage, "purpose": "develop-" + stage, "round_id": "research-development-round-1", "outcome": outcome}


def test_bounded_stage_order_reserves_one_repair_and_keeps_two_manuscript_calls():
    stages, state = [], round_state()
    development = state["research_development"]
    development.update(contract_version=2, evidence_artifact_id="evidence", evidence_sha256="a" * 64,
        work_product_report_artifact_id="products", audit_artifact_id="audit", audit_sha256="b" * 64)
    for index in range(6):
        task = development_next_task(state)
        assert task is not None
        stage = task["purpose"].removeprefix("develop-")
        stages.append(stage)
        state["calls"].append(call(stage))
        state["research_development"]["completed_stages"].append(task["purpose"])
        if stage == "audit":
            development.update(repair_required=True, audit={"evidence_sha256": "a" * 64, "ready_to_write": False, "repair_required": True})
        if stage == "repair": development["evidence_sha256"] = "c" * 64
        if stage == "re-audit":
            development.update(repair_required=False, audit={"evidence_sha256": "c" * 64, "ready_to_write": True, "repair_required": False})
    assert stages == ["design", "audit", "repair", "re-audit", "write", "review"]
    assert development_next_task(state) is None


def test_failed_evidence_can_only_recover_through_a_retained_failure_audit():
    state = round_state(["develop-plan", "develop-evidence"], [call("plan"), call("evidence", "rejected")])
    assert development_next_task(state) is None
    state["research_development"]["evidence_failures"] = {"call-evidence": {"artifact_id": "actual-retained-failure"}}
    assert development_next_task(state)["purpose"] == "develop-audit"
    state["calls"].append(call("audit", "failed"))
    assert development_next_task(state) is None


def test_failed_repair_cannot_use_prior_false_audit_to_write_even_with_a_valid_packet():
    calls = [call("plan"), call("evidence"), call("audit"), call("repair", "rejected")]
    state = round_state(["plan", "evidence", "audit", "repair"], calls)
    development = state["research_development"]
    development.update(repair_required=True, repair_limit_reached=True, evidence_failures={"call-repair": {"artifact_id": "retained-repair-failure"}})
    assert development_next_task(state) is None
    development.update(evidence_artifact_id="valid-evidence", checker_artifact_id="valid-native-checker", supplement={"artifact_id": "valid-replay-supplement"})
    assert development_next_task(state) is None


def test_pending_failed_closed_and_budget_stages_cannot_start_extra_calls():
    state = round_state(calls=[call("plan", "reserved")])
    assert development_next_task(state)["purpose"] == "develop-plan"
    state["research_development"]["closed"] = True
    assert development_next_task(state) is None
    state = round_state(calls=[call("plan", "failed")])
    assert development_next_task(state) is None
    state = round_state()
    state["research_development"]["additional_call_limit"] = 4
    assert development_next_task(state) is None


def test_audit_requires_actual_attainable_repair_instead_of_a_vague_weakness():
    audit = {"evidence_sha256": "a" * 64, "correspondence": [{"case_id": "bounded-editor", "alternative_id": "guarded", "target_id": "dispatch", "verdict": "faithful",
              "reason": "Synthetic correspondence is explicitly scoped to this test.", "required_repair": ""}], "repair_actions": [],
             "decisive_findings": ["A weak or negative finding still permits an honest bounded article."], "honest_limits": ["Actual project implementation remains unverified."],
             "ready_to_write": True, "repair_required": False}
    assert determine_audit_repair(audit) is False
    audit["repair_required"] = True
    with pytest.raises(ValidationError, match="attainable"):
        DevelopmentAudit.model_validate(audit)


@pytest.mark.parametrize("target", ["dispatch", "valid-start", "busy-and-queued", "remove-recipient-check", "already-expired"])
def test_method_audit_can_target_properties_controls_and_conditions_not_only_rules(target):
    audit = {"evidence_sha256": "a" * 64,
             "correspondence": [{"case_id": "bounded-editor", "alternative_id": "guarded", "target_id": target,
                 "verdict": "needs_repair", "reason": "Synthetic audit finding identifies an actual model component.",
                 "required_repair": "Describe the precise supported scope without overstating the checked result."}],
             "repair_actions": [{"case_id": "bounded-editor", "alternative_id": "guarded", "target_id": target,
                 "issue": "A property or control can have a methodological defect independently of a transition rule.",
                 "exact_change": "Preserve the computed result and correct only its supported interpretation.",
                 "available_evidence_ids": ["synthetic-handler", target], "safely_obtainable": True}],
             "decisive_findings": ["Synthetic useful finding remains bound to the actual checked model component."],
             "honest_limits": ["Native admission still verifies these identifiers against the exact retained case."],
             "ready_to_write": False, "repair_required": True}
    parsed = DevelopmentAudit.model_validate(audit)
    assert parsed.correspondence[0].target_id == parsed.repair_actions[0].target_id == target
    obsolete = deepcopy(audit)
    obsolete["correspondence"][0]["rule_id"] = obsolete["correspondence"][0].pop("target_id")
    with pytest.raises(ValidationError):
        DevelopmentAudit.model_validate(obsolete)


def test_stored_audit_admission_repair_preserves_three_remaining_calls_without_re_request():
    state = round_state(["plan", "evidence", "audit"], [call("plan"), call("evidence"), call("audit", "rejected")])
    state["research_development"]["repair_required"] = True
    original_calls = deepcopy(state["calls"])
    assert development_next_task(state) is None
    state["research_development"]["audit_admission_repairs"] = {"call-audit": {"outcome": "rejected"}}
    assert development_next_task(state) is None
    state["research_development"]["audit_admission_repairs"]["call-audit"] = {"outcome": "admitted", "artifact_id": "actual-key-normalization-proof", "sha256": "a" * 64}
    assert development_next_task(state)["purpose"] == "develop-repair"
    state["calls"].append(call("repair"))
    state["research_development"]["completed_stages"].append("repair")
    assert development_next_task(state) is None
    assert state["calls"][:3] == original_calls and state["calls"][2]["outcome"] == "rejected"
    assert len(state["calls"]) == 4


def test_stored_writer_admission_repair_leaves_only_original_last_review_call():
    state = round_state(["plan", "evidence", "audit", "repair", "write"],
                        [call("plan"), call("evidence"), call("audit"), call("repair"), call("write", "rejected")])
    development = state["research_development"]
    development["repair_required"] = True
    original_calls = deepcopy(state["calls"])
    assert development_next_task(state) is None
    development["write_admission_repairs"] = {"different-call": {"outcome": "admitted"},
                                               "call-write": {"outcome": "rejected"}}
    assert development_next_task(state) is None
    development["write_admission_repairs"]["call-write"] = {"outcome": "admitted", "sha256": "b" * 64}
    assert development_next_task(state)["purpose"] == "develop-review"
    assert state["calls"] == original_calls and state["calls"][-1]["outcome"] == "rejected"
    development["completed_stages"].remove("write")
    assert development_next_task(state) is None
    development["completed_stages"].append("write")
    state["calls"].append(call("review"))
    development["completed_stages"].append("review")
    assert len(state["calls"]) == 6 and development_next_task(state) is None

"""Bounded transition-rule enumeration; standalone standard-library replay.

This evaluates data, never Python expressions, imported repository code, or
author-provided executable scripts. States are generated from simultaneous rule
effects. A clean authored abstraction is not an implementation security proof.
"""

import argparse
from collections import deque
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

MAX_STATES = 5000
MAX_EDGES = 20000
NAME = re.compile(r"^[a-z][a-z0-9_]{0,49}$")


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _same(left, right):
    return type(left) is type(right) and left == right


def _literal(value):
    return type(value) in {bool, int, str} and (type(value) is not int or -10000 <= value <= 10000) and (type(value) is not str or 1 <= len(value) <= 80)


def _operand(operand, state):
    return state[operand["variable"]] if operand.get("variable") is not None else operand["literal"]


def _predicate(predicate, state):
    left, right = _operand(predicate["left"], state), _operand(predicate["right"], state)
    op = predicate["op"]
    if op == "eq":
        return _same(left, right)
    if op == "ne":
        return not _same(left, right)
    if type(left) is not int or type(right) is not int:
        raise ValueError("Ordered finite comparisons require strict integers")
    return {"lt": left < right, "le": left <= right, "gt": left > right, "ge": left >= right}[op]


def _holds(predicates, state):
    return all(_predicate(predicate, state) for predicate in predicates)


def _validate_operand(operand, domains):
    if not isinstance(operand, dict) or set(operand) - {"variable", "literal"}:
        raise ValueError("Finite operands contain only variable and literal")
    variable, literal = operand.get("variable"), operand.get("literal")
    if (variable is None) == (literal is None):
        raise ValueError("A finite operand has exactly one variable or scalar literal")
    if variable is not None:
        if variable not in domains:
            raise ValueError("Finite operand references an unknown variable")
        return type(domains[variable][0])
    if not _literal(literal):
        raise ValueError("Finite literals are bounded strict booleans, integers or strings")
    return type(literal)


def _validate_predicate(predicate, domains):
    if not isinstance(predicate, dict) or set(predicate) != {"left", "op", "right"} or predicate["op"] not in {"eq", "ne", "lt", "le", "gt", "ge"}:
        raise ValueError("Finite predicates require left/op/right and a supported comparison")
    left = _validate_operand(predicate["left"], domains)
    right = _validate_operand(predicate["right"], domains)
    if left is not right or predicate["op"] not in {"eq", "ne"} and left is not int:
        raise ValueError("Finite comparisons require compatible strict types; ordering requires integers")


def _unique(items, label):
    ids = [item["id"] for item in items]
    if len(set(ids)) != len(ids) or any(not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,59}", value) for value in ids):
        raise ValueError(label + " require unique safe identifiers")


def _validate_effect(effect, domains):
    if set(effect) - {"variable", "value", "delta"} or effect.get("variable") not in domains:
        raise ValueError("Finite effects reference a declared target variable")
    target_type = type(domains[effect["variable"]][0])
    source_type = _validate_operand(effect["value"], domains)
    delta = effect.get("delta", 0)
    if type(delta) is not int or not -10000 <= delta <= 10000 or target_type is not source_type or delta and target_type is not int:
        raise ValueError("Finite effects require compatible scalar types and bounded integer deltas")


def validate_case(case, source_witness_ids, *, document_witness_ids=None):
    document_witness_ids = set(document_witness_ids or ())
    domains, initial = case["variables"], case["initial"]
    if not isinstance(domains, dict) or not 1 <= len(domains) <= 16 or set(initial) != set(domains):
        raise ValueError("Finite cases require one initial value for every bounded variable")
    for name, values in domains.items():
        if not NAME.fullmatch(name) or not isinstance(values, list) or not 1 <= len(values) <= 8:
            raise ValueError("Finite domains require safe variable names and one to eight constants")
        if any(not _literal(value) or type(value) is not type(values[0]) for value in values):
            raise ValueError("Finite domains are homogeneous strict scalar constants, never floats")
        if len({(type(value).__name__, value) for value in values}) != len(values) or not any(_same(initial[name], value) for value in values):
            raise ValueError("Finite domains are unique and contain their exact typed initial value")
    if math.prod(len(values) for values in domains.values()) > MAX_STATES:
        raise ValueError("Finite Cartesian state space exceeds the 5000-state bound")
    if not 1 <= len(case["invariants"]) <= 10 or not 1 <= len(case["coverage"]) <= 12 or not 2 <= len(case["alternatives"]) <= 4:
        raise ValueError("Finite cases require bounded invariants, coverage goals and two to four fair alternatives")
    _unique(case["invariants"], "Invariants")
    _unique(case["coverage"], "Coverage goals")
    if {item["id"] for item in case["invariants"]} & {item["id"] for item in case["coverage"]}:
        raise ValueError("Invariant and coverage property identifiers must be distinct")
    _unique(case["alternatives"], "Alternatives")
    for invariant in case["invariants"]:
        if not 0 <= len(invariant["if_all"]) <= 16 or not 1 <= len(invariant["then_all"]) <= 16:
            raise ValueError("An invariant requires a bounded antecedent and nonempty consequent")
        for predicate in invariant["if_all"] + invariant["then_all"]:
            _validate_predicate(predicate, domains)
    for goal in case["coverage"]:
        if not 1 <= len(goal["conditions"]) <= 16:
            raise ValueError("Coverage conditions must be nonempty and bounded")
        for predicate in goal["conditions"]:
            _validate_predicate(predicate, domains)
    for alternative in case["alternatives"]:
        if not 1 <= len(alternative["rules"]) <= 40:
            raise ValueError("Alternatives require one to forty generative rules")
        _unique(alternative["rules"], "Rules")
        for rule in alternative["rules"]:
            references = set(rule.get("evidence_ids", []))
            if not references or not references.issubset(source_witness_ids | document_witness_ids):
                raise ValueError("Every rule must map to exact externally verified repository or proposal-document witnesses")
            if alternative.get("implementation_status") not in {"proposal", "environment_assumption"} and (not references & source_witness_ids or references & document_witness_ids):
                raise ValueError("Actual implementation rules require repository source witnesses, never document substitutes")
            if not 0 <= len(rule["guard"]) <= 16 or not 1 <= len(rule["effects"]) <= 16:
                raise ValueError("Rule guards and simultaneous effects must be bounded")
            if len({effect["variable"] for effect in rule["effects"]}) != len(rule["effects"]):
                raise ValueError("A rule cannot assign a target variable more than once")
            for predicate in rule["guard"]:
                _validate_predicate(predicate, domains)
            for effect in rule["effects"]:
                _validate_effect(effect, domains)


def _enumerate(case, alternative, include_graph=False):
    names, domains = sorted(case["variables"]), case["variables"]
    key = lambda state: tuple((type(state[name]).__name__, state[name]) for name in names)
    first = dict(case["initial"])
    states, parents, queue = {key(first): first}, {key(first): None}, deque([key(first)])
    edges, enabled, coverage_counts, antecedents = [], set(), {}, {}
    violations, checks = {}, 0

    def trace(identifier):
        result = []
        while parents[identifier] is not None:
            previous, rule = parents[identifier]
            result.append(rule)
            identifier = previous
        return list(reversed(result))

    while queue:
        identifier = queue.popleft()
        state = states[identifier]
        for invariant in case["invariants"]:
            checks += 1
            if _holds(invariant["if_all"], state):
                antecedents[invariant["id"]] = antecedents.get(invariant["id"], 0) + 1
                if not _holds(invariant["then_all"], state):
                    record = violations.setdefault(invariant["id"], {"count": 0, "state": state, "transition_trace": trace(identifier)})
                    record["count"] += 1
        for goal in case["coverage"]:
            if _holds(goal["conditions"], state):
                coverage_counts[goal["id"]] = coverage_counts.get(goal["id"], 0) + 1
        for rule in alternative["rules"]:
            if not _holds(rule["guard"], state):
                continue
            target = dict(state)
            for effect in rule["effects"]:
                value = _operand(effect["value"], state)
                if effect.get("delta", 0):
                    value += effect["delta"]
                if not any(_same(value, constant) for constant in domains[effect["variable"]]):
                    raise ValueError("Enabled rule " + rule["id"] + " produces a value outside its finite domain")
                target[effect["variable"]] = value
            destination = key(target)
            edges.append((identifier, rule["id"], destination))
            if len(edges) > MAX_EDGES:
                raise ValueError("Generated transitions exceed the 20000-edge bound")
            enabled.add(rule["id"])
            if destination not in states:
                if len(states) >= MAX_STATES:
                    raise ValueError("Generated states exceed the 5000-state bound")
                states[destination] = target
                parents[destination] = (identifier, rule["id"])
                queue.append(destination)
    invariant_results = [{"id": item["id"], "status": "failed" if item["id"] in violations else "passed" if antecedents.get(item["id"], 0) else "vacuous",
                          "antecedent_states": antecedents.get(item["id"], 0), "violations": violations.get(item["id"], {}).get("count", 0),
                          "counterexample": {k: value for k, value in violations[item["id"]].items() if k != "count"} if item["id"] in violations else None}
                         for item in case["invariants"]]
    coverage = []
    for goal in case["coverage"]:
        witness = next((identifier for identifier, state in states.items() if _holds(goal["conditions"], state)), None)
        coverage.append({"id": goal["id"], "required": goal.get("required", True), "reachable_states": coverage_counts.get(goal["id"], 0),
                         "status": "passed" if witness is not None else "unreachable",
                         "witness": {"state": states[witness], "transition_trace": trace(witness)} if witness is not None else None})
    result = {"alternative_id": alternative["id"], "reachable_state_count": len(states), "edge_count": len(edges), "invariant_checks": checks,
              "invariants": invariant_results, "coverage": coverage, "enabled_rules": sorted(enabled),
              "dead_rules": sorted({rule["id"] for rule in alternative["rules"]} - enabled),
              "variable_value_coverage": {name: [value for value in domains[name] if any(_same(state[name], value) for state in states.values())] for name in names}}
    result["meets_declared_requirements"] = (all(item["status"] == "passed" for item in invariant_results)
                                             and all(item["status"] == "passed" for item in coverage if item["required"]))
    if include_graph:
        identifiers = {identifier: "s" + str(index) for index, identifier in enumerate(states)}
        result["generated_states"] = [{"id": identifiers[identifier], "values": state} for identifier, state in states.items()]
        result["generated_edges"] = [{"from": identifiers[start], "rule_id": rule, "to": identifiers[end]} for start, rule, end in edges]
    return result


def check_evidence(evidence, source_witness_ids=None, *, include_graph=False, document_witness_ids=None):
    """Compute findings from externally source-bound, finite declarative inputs."""
    source_ids = {item["id"] for item in evidence["source_evidence"]}
    if source_witness_ids is not None and not source_ids.issubset(source_witness_ids):
        raise ValueError("Evidence includes an unverified repository source witness")
    declared_docs = {item["source_id"] for item in evidence.get("document_evidence", [])}
    if source_ids & declared_docs:
        raise ValueError("Source and document witness identifiers must have separate namespaces")
    if document_witness_ids is not None and not declared_docs.issubset(document_witness_ids):
        raise ValueError("Evidence includes an unverified retained document witness")
    document_ids = declared_docs if document_witness_ids is not None or source_witness_ids is None else set()
    cases = evidence["cases"]
    if evidence.get("method_scope") == "source_comparison_not_project_execution":
        if cases:
            raise ValueError("Source comparison must not label finite cases as an unexecuted qualitative comparison")
        return {"kind": "native_source_comparison_bindings", "project_execution": False,
                "input_sha256": canonical_sha(evidence),
                "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "limits": {"states": MAX_STATES, "edges": MAX_EDGES}, "cases": [], "issues": [],
                "audit_required": True,
                "scope": "No finite model or project was executed. Source and prior-method comparisons are analytical judgments, independently audited; reference checks establish no novelty or implementation effect."}
    if not 1 <= len(cases) <= 3:
        raise ValueError("Development evidence requires one to three bounded cases")
    _unique(cases, "Cases")
    results, issues = [], []
    for case in cases:
        validate_case(case, source_ids, document_witness_ids=document_ids)
        alternatives = {item["id"]: item for item in case["alternatives"]}
        base = {identifier: _enumerate(case, alternative, include_graph) for identifier, alternative in alternatives.items()}
        controls = []
        if not 1 <= len(case["negative_controls"]) <= 8 or not 1 <= len(case["condition_flips"]) <= 4:
            raise ValueError("Each case requires one to eight negative controls and one to four condition flips")
        _unique(case["negative_controls"], "Negative controls")
        _unique(case["condition_flips"], "Condition flips")
        invariant_ids = {item["id"] for item in case["invariants"]}
        for control in case["negative_controls"]:
            identifier = control["alternative_id"]
            if identifier not in alternatives or control["expected_invariant_id"] not in invariant_ids:
                raise ValueError("Negative controls must identify an existing alternative and invariant")
            mutant = deepcopy(alternatives[identifier])
            rule = next((item for item in mutant["rules"] if item["id"] == control["rule_id"]), None)
            if rule is None:
                raise ValueError("Negative controls must identify an existing rule")
            if control["kind"] == "remove_guard":
                index = control.get("guard_index")
                if type(index) is not int or not 0 <= index < len(rule["guard"]):
                    raise ValueError("Guard mutation must remove one actual guard predicate")
                rule["guard"].pop(index)
            elif control["kind"] == "replace_effect":
                effect = control["effect"]
                _validate_effect(effect, case["variables"])
                index = next((index for index, original in enumerate(rule["effects"]) if original["variable"] == effect["variable"]), None)
                if index is None:
                    raise ValueError("Effect mutation must replace an actual rule assignment")
                rule["effects"][index] = effect
            else:
                raise ValueError("Unsupported finite negative-control mutation")
            changed = _enumerate(case, mutant)
            original_result = next(item for item in base[identifier]["invariants"] if item["id"] == control["expected_invariant_id"])
            altered = next(item for item in changed["invariants"] if item["id"] == control["expected_invariant_id"])
            caught = (original_result["status"] == "passed" and altered["status"] == "failed"
                      and control["rule_id"] in altered["counterexample"]["transition_trace"])
            controls.append({"id": control["id"], "alternative_id": identifier, "rule_id": control["rule_id"], "expected_invariant_id": control["expected_invariant_id"],
                             "caught": caught, "original_status": original_result["status"], "mutant_status": altered["status"],
                             "counterexample": altered["counterexample"], "reachable_state_count": changed["reachable_state_count"], "edge_count": changed["edge_count"]})
        flips = []
        for flip in case["condition_flips"]:
            identifier = flip["alternative_id"]
            if identifier not in alternatives or not flip["initial_overrides"] or not set(flip["initial_overrides"]).issubset(case["variables"]):
                raise ValueError("Condition flips require an existing alternative and declared initial variables")
            modified = deepcopy(case)
            modified["initial"].update(flip["initial_overrides"])
            validate_case(modified, source_ids, document_witness_ids=document_ids)
            changed_alternatives = {key: _enumerate(modified, alternative) for key, alternative in alternatives.items()}
            changed = changed_alternatives[identifier]
            properties = lambda report: {item["id"]: item for item in report["invariants"] + report["coverage"]}
            original, altered = properties(base[identifier]), properties(changed)
            if flip["property_id"] not in original:
                raise ValueError("Condition flips require an existing invariant or coverage property")
            old, new = original[flip["property_id"]], altered[flip["property_id"]]
            decisive = old["status"] != new["status"] and "vacuous" not in {old["status"], new["status"]}
            flips.append({"id": flip["id"], "alternative_id": identifier, "property_id": flip["property_id"], "initial_overrides": flip["initial_overrides"],
                          "original_status": old["status"], "changed_status": new["status"], "decisive": decisive,
                          "changed_property": new,
                          "alternative_outcomes_under_same_condition": [{"alternative_id": key, "meets_declared_requirements": report["meets_declared_requirements"],
                              "invariants": [{"id": item["id"], "status": item["status"]} for item in report["invariants"]],
                              "coverage": [{"id": item["id"], "status": item["status"]} for item in report["coverage"]]} for key, report in changed_alternatives.items()]})
        case_issues = ["Negative control did not expose a new intended violation: " + item["id"] for item in controls if not item["caught"]]
        case_issues.extend("No nonvacuous decision-changing condition flip: " + case["id"] for _ in [0] if not any(item["decisive"] for item in flips))
        for report in base.values():
            case_issues.extend("Vacuous invariant: " + report["alternative_id"] + "/" + item["id"] for item in report["invariants"] if item["status"] == "vacuous")
            case_issues.extend("Dead rule: " + report["alternative_id"] + "/" + rule for rule in report["dead_rules"])
        issues.extend(case["id"] + ": " + issue for issue in case_issues)
        outcome = lambda report: {item["id"]: item["status"] for item in report["invariants"] + report["coverage"]}
        comparison = [{"left": left, "right": right,
                       "different_properties": [key for key, status in outcome(base[left]).items() if outcome(base[right])[key] != status],
                       "left_meets_requirements": base[left]["meets_declared_requirements"], "right_meets_requirements": base[right]["meets_declared_requirements"]}
                      for index, left in enumerate(base) for right in list(base)[index + 1:]]
        results.append({"case_id": case["id"], "cartesian_state_bound": math.prod(len(values) for values in case["variables"].values()),
                        "rule_evidence_bindings": [{"alternative_id": alternative["id"], "implementation_status": alternative.get("implementation_status"),
                            "rule_id": rule["id"], "references": [{"id": identifier,
                                "kind": "repository_source_witness" if identifier in source_ids else "retained_document_witness",
                                "scope": ("Source/model correspondence requires independent audit; identifier membership alone is not implementation proof."
                                          if identifier in source_ids else "Conceptual support for an authored proposal or environment assumption; not a repository quotation or implemented effect.")}
                                for identifier in rule["evidence_ids"]]} for alternative in case["alternatives"] for rule in alternative["rules"]],
                        "shared_initial_sha256": canonical_sha(case["initial"]), "shared_properties_sha256": canonical_sha({"invariants": case["invariants"], "coverage": case["coverage"]}),
                        "alternatives": list(base.values()), "alternative_comparisons": comparison,
                        "negative_controls": controls, "condition_flips": flips, "issues": case_issues})
    return {"kind": "native_generated_finite_rule_enumeration", "project_execution": False, "input_sha256": canonical_sha(evidence),
            "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "limits": {"states": MAX_STATES, "edges": MAX_EDGES},
            "cases": results, "issues": issues, "audit_required": True,
            "scope": "Exhaustive reachable states of supplied finite rules; source/model correspondence and omitted behavior require independent audit. No implementation, empirical, liveness or universal security claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--graphs", action="store_true", help="Include all generated states and edges instead of compact witnesses only")
    parser.add_argument("--expected-input-sha256", help="Verify the frozen evidence.json SHA from the companion manifest before replay")
    arguments = parser.parse_args()
    raw = arguments.input.read_bytes()
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("Finite replay input exceeds 32 MiB")
    input_digest = hashlib.sha256(raw).hexdigest()
    if arguments.expected_input_sha256 is not None and arguments.expected_input_sha256 != input_digest:
        raise ValueError("Replay input differs from its expected frozen SHA-256")
    report = check_evidence(json.loads(raw), include_graph=arguments.graphs)
    report["input_file_sha256"] = input_digest
    arguments.output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

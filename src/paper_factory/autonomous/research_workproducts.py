"""Concrete source-bound research outputs, distinct from implementation proof.

Controllers verify complete source/document quotations before calling this pure
module. Protocol results are recomputed from finite rules; no repository code,
model service, filesystem mutation or publication-quality assessment occurs.
"""

from typing import Annotated, Literal
from pathlib import Path
import hashlib
from copy import deepcopy

from pydantic import Field, StrictBool, StrictInt, StrictStr

from ..models import Record
from . import finite_rules

Text = Annotated[StrictStr, Field(min_length=12, max_length=6000)]
Id = Annotated[StrictStr, Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,79}$")]
Witnesses = Annotated[list[StrictStr], Field(min_length=1, max_length=20)]


class ResultReference(Record):
    alternative_id: Id
    kind: Literal["invariant", "coverage", "negative_control", "condition_flip"]
    result_id: Id
    trace: list[Id] | None = Field(default=None, max_length=80)


class ChangedDecision(Record):
    id: Id
    condition: Text
    prior_method_evidence_ids: list[StrictStr] = Field(default_factory=list, max_length=20)
    baseline_decision: Text
    additional_analysis: Text
    changed_decision: Text
    support_ids: Witnesses
    result_refs: list[ResultReference] = Field(default_factory=list, max_length=12)
    limitations: list[Text] = Field(min_length=1, max_length=8)


class ComparisonCriterion(Record):
    id: Id
    question: Text


class ComparisonAlternative(Record):
    id: Id
    label: Text
    implementation_status: Literal["retained_source", "proposed_change"]
    evidence_ids: Witnesses
    implementation_steps: list[Text] = Field(min_length=1, max_length=12)
    costs: list[Text] = Field(min_length=1, max_length=8)
    applicability_conditions: list[Text] = Field(min_length=1, max_length=8)


class ComparisonObservation(Record):
    id: Id
    alternative_id: Id
    criterion_id: Id
    observation: Text
    evidence_ids: Witnesses


class SourceComparison(Record):
    id: Id
    kind: Literal["source_comparison"]
    reader_decision: Text
    shared_requirements: list[Text] = Field(min_length=1, max_length=8)
    common_conditions: list[Text] = Field(min_length=1, max_length=8)
    criteria: list[ComparisonCriterion] = Field(min_length=1, max_length=8)
    alternatives: list[ComparisonAlternative] = Field(min_length=2, max_length=4)
    observations: list[ComparisonObservation] = Field(min_length=2, max_length=32)
    changed_decisions: list[ChangedDecision] = Field(min_length=1, max_length=8)
    limitations: list[Text] = Field(min_length=1, max_length=8)


class ProtocolActor(Record):
    id: Id
    responsibility: Text
    trusted_by_design: StrictBool
    evidence_ids: Witnesses


class StateOwnership(Record):
    variable: Id
    actor_id: Id
    role: Literal["owned_state", "environment", "instrumentation"]
    evidence_ids: Witnesses


class RequestFixture(Record):
    id: Id
    resource_id: Id
    payload_revision: StrictInt = Field(ge=0, le=10000)
    owner_generation: Id


class RequestIdentity(Record):
    incoming_variable: Id
    queued_variable: Id
    inflight_variable: Id
    empty_id: Id


class Supersession(Record):
    older_request: Id
    newer_request: Id


class ServiceContract(Record):
    id: Id
    semantics: Literal["each_request", "latest_snapshot"]
    allow_rejection: StrictBool
    allowed_supersessions: list[Supersession] = Field(max_length=12)
    required_property_ids: Witnesses
    rationale: Text
    evidence_ids: Witnesses


class CommonWorkload(Record):
    offered_requests: list[Id] = Field(min_length=3, max_length=4)
    environment_rule_ids: list[Id] = Field(min_length=1, max_length=12)
    identity_coverage: ResultReference
    scope: Text


class AdmissionChoice(Record):
    alternative_id: Id
    policy: Literal["preserve_pending", "reject_new", "coalesce_latest", "not_queued"]
    rationale: Text
    evidence_ids: Witnesses


class ProtocolStep(Record):
    id: Id
    alternative_id: Id
    rule_id: Id
    actor_id: Id
    kind: Literal["check", "state_update", "native_start", "await", "completion", "reply", "failure", "environment"]
    phase_variable: Id
    from_phase: StrictBool | StrictInt | StrictStr
    to_phase: StrictBool | StrictInt | StrictStr
    guard_indexes: list[StrictInt] = Field(max_length=16)
    effect_variables: list[Id] = Field(min_length=1, max_length=16)
    instruction: Text
    implementation_status: Literal["retained_source", "proposed_change", "environment_assumption"]
    evidence_ids: Witnesses
    failure_outcome: Text


class AtomicObligation(Record):
    id: Id
    alternative_id: Id
    check_step_ids: list[Id] = Field(min_length=1, max_length=8)
    start_step_id: Id
    mechanism: Literal["single_synchronous_turn", "consume_before_await", "lock_owned_state", "post_await_recheck", "unresolved"]
    justification: Text
    evidence_ids: Witnesses
    unresolved_reason: StrictStr = Field(max_length=6000)


class TypedProtocol(Record):
    id: Id
    kind: Literal["typed_protocol"]
    reader_decision: Text
    case_id: Id
    actors: list[ProtocolActor] = Field(min_length=1, max_length=8)
    state_ownership: list[StateOwnership] = Field(min_length=1, max_length=16)
    requests: list[RequestFixture] = Field(min_length=3, max_length=4)
    request_identity: RequestIdentity
    service_contract: ServiceContract
    workload: CommonWorkload
    admission_choices: list[AdmissionChoice] = Field(min_length=2, max_length=4)
    steps: list[ProtocolStep] = Field(min_length=1, max_length=160)
    atomic_obligations: list[AtomicObligation] = Field(min_length=1, max_length=12)
    changed_decisions: list[ChangedDecision] = Field(min_length=1, max_length=8)
    limitations: list[Text] = Field(min_length=1, max_length=12)


class ResearchWorkProducts(Record):
    products: list[Annotated[TypedProtocol | SourceComparison, Field(discriminator="kind")]] = Field(min_length=1, max_length=3)


def _unique(values, label):
    if len(set(values)) != len(values):
        raise ValueError(label + " must be unique")


def _known(values, allowed, label):
    _unique(values, label)
    if not set(values).issubset(allowed):
        raise ValueError(label + " references an unknown retained identifier")


def _result_reference(ref, report):
    alternatives = {item["alternative_id"]: item for item in report["alternatives"]}
    if ref.alternative_id not in alternatives:
        raise ValueError("A result reference requires an existing same-case alternative")
    group = ({"invariant": alternatives[ref.alternative_id]["invariants"],
              "coverage": alternatives[ref.alternative_id]["coverage"],
              "negative_control": report["negative_controls"], "condition_flip": report["condition_flips"]})[ref.kind]
    result = next((item for item in group if item["id"] == ref.result_id), None)
    if result is None or result.get("alternative_id", ref.alternative_id) != ref.alternative_id:
        raise ValueError("A result reference requires an exact same-case native result ID")
    detail = result.get("changed_property", result)
    witness = detail.get("counterexample") or detail.get("witness")
    actual_trace = witness.get("transition_trace", []) if witness else []
    if ref.trace is not None and ref.trace != actual_trace:
        raise ValueError("A result trace must exactly equal its recomputed native witness")
    status = result.get("status", "caught" if result.get("caught") else "decisive" if result.get("decisive") else "not_decisive")
    return {"alternative_id": ref.alternative_id, "kind": ref.kind, "result_id": ref.result_id,
            "status": status, "trace": actual_trace}, witness


def _decisions(rows, support_ids, witness_ids, report=None, *, require_results=True):
    _unique([row.id for row in rows], "Changed-decision IDs")
    output = []
    for row in rows:
        _known(row.prior_method_evidence_ids, witness_ids, "Prior-method evidence")
        _known(row.support_ids, support_ids, "Changed-decision support")
        decision_changed = row.baseline_decision.strip().casefold() != row.changed_decision.strip().casefold()
        if row.result_refs and report is None:
            raise ValueError("Computed decision references require an exact finite case")
        if report is not None and require_results and not row.result_refs:
            raise ValueError("A protocol decision requires recomputed result references")
        outcomes = [_result_reference(ref, report)[0] for ref in row.result_refs]
        output.append({"id": row.id, "condition": row.condition, "baseline_decision": row.baseline_decision,
                       "additional_analysis": row.additional_analysis, "changed_decision": row.changed_decision,
                       "decision_changed": decision_changed,
                       "prior_method_evidence_ids": row.prior_method_evidence_ids, "support_ids": row.support_ids,
                       "result_outcomes": outcomes, "limitations": row.limitations})
    return output


def _model_identifiers(case):
    """Authored definitions are references, never external quotations or proof."""
    identifiers = {}
    for kind in ("invariant", "coverage", "negative_control", "condition_flip"):
        field = {"invariant": "invariants", "coverage": "coverage", "negative_control": "negative_controls", "condition_flip": "condition_flips"}[kind]
        for item in case[field]:
            identifiers.setdefault(item["id"], []).append({"kind": kind, "alternative_id": item.get("alternative_id")})
    for alternative in case["alternatives"]:
        for rule in alternative["rules"]:
            identifiers.setdefault(rule["id"], []).append({"kind": "rule", "alternative_id": alternative["id"]})
    return identifiers


def _comparison_case(product, witnesses, cases, reports):
    observations = {item.id for item in product.observations}
    model_ids = {identifier for item in product.observations for identifier in item.evidence_ids if identifier not in witnesses}
    model_ids.update(identifier for row in product.changed_decisions for identifier in row.support_ids
                     if identifier not in witnesses | observations)
    refs = [ref for row in product.changed_decisions for ref in row.result_refs]
    if not model_ids and not refs:
        return None, None, {}
    matches = []
    for case_id, case in cases.items():
        identifiers = _model_identifiers(case)
        if not model_ids.issubset(identifiers):
            continue
        report = reports.get(case_id)
        if report is None:
            continue
        try:
            for ref in refs:
                _result_reference(ref, report)
        except ValueError:
            continue
        matches.append((case, report, identifiers))
    if len(matches) != 1:
        raise ValueError("Computed comparison references must resolve to exactly one native finite case; unknown or ambiguous identifiers are not admitted")
    return matches[0]


def _reference_binding(identifier, source_ids, document_ids, model_ids, observations, case_id, *, local_kind="comparison_observation"):
    kinds = (["repository_source_witness"] if identifier in source_ids else []) + (["retained_document_witness"] if identifier in document_ids else [])
    kinds += (["model_definition"] if identifier in model_ids else []) + ([local_kind] if identifier in observations else [])
    if len(kinds) != 1:
        raise ValueError("Comparison reference must have exactly one declared witness, model or observation namespace")
    result = {"id": identifier, "kind": kinds[0]}
    if identifier in model_ids:
        result.update(case_id=case_id, definitions=model_ids[identifier],
                      scope="Authored model definition, not a repository quotation, implementation effect or efficacy evidence.")
    elif identifier in observations:
        result["scope"] = "Declared research record; exact rule/evidence bindings remain in the dossier or matrix."
    else:
        result["scope"] = "External literal quotation and whole-body hash verified by the controller; interpretation requires independent audit."
    return result


def _comparison(product, source_ids, document_ids, cases, reports):
    witnesses = source_ids | document_ids
    criteria = {item.id: item for item in product.criteria}
    alternatives = {item.id: item for item in product.alternatives}
    _unique([item.id for item in product.criteria], "Comparison criteria")
    _unique([item.id for item in product.alternatives], "Comparison alternatives")
    _unique([item.id for item in product.observations], "Comparison observations")
    cells = [(item.alternative_id, item.criterion_id) for item in product.observations]
    _unique(cells, "Comparison cells")
    if set(cells) != {(alternative, criterion) for alternative in alternatives for criterion in criteria}:
        raise ValueError("A comparison must produce every alternative-by-criterion observation")
    for item in product.alternatives:
        _known(item.evidence_ids, witnesses, "Comparison evidence")
    case, report, model_ids = _comparison_case(product, witnesses, cases, reports)
    case_id = case["id"] if case else None
    observations = {item.id for item in product.observations}
    bind = lambda identifier, observation_ids=observations: _reference_binding(identifier, source_ids, document_ids, model_ids, observation_ids, case_id)
    for item in product.observations:
        _known(item.evidence_ids, witnesses | set(model_ids), "Comparison evidence")
        for identifier in item.evidence_ids:
            bind(identifier, set())
    matrix = [{"id": item.id, "alternative_id": item.alternative_id, "alternative": alternatives[item.alternative_id].label,
               "criterion_id": item.criterion_id, "criterion": criteria[item.criterion_id].question,
               "observation": item.observation, "evidence_ids": item.evidence_ids,
               "evidence_bindings": [bind(identifier, set()) for identifier in item.evidence_ids],
               "implementation_status": alternatives[item.alternative_id].implementation_status} for item in product.observations]
    decisions = _decisions(product.changed_decisions, observations | witnesses | set(model_ids), witnesses, report, require_results=False)
    for decision in decisions:
        decision["support_bindings"] = [bind(identifier) for identifier in decision["support_ids"]]
    return {"matrix": matrix, "shared_requirements": product.shared_requirements,
            "common_conditions": product.common_conditions,
            "native_case_binding": {"case_id": case_id, "case_input_sha256": finite_rules.canonical_sha(case),
                "native_case_report_sha256": finite_rules.canonical_sha(report),
                "scope": "Recomputed bounded authored-model outcomes, not implementation validation."} if case else None,
            "alternatives": [item.model_dump(mode="json") for item in product.alternatives],
            "decision_table": decisions, "evidence_limits": list(product.limitations)}


def _reachable_phase(step, report):
    alternative = next(item for item in report["alternatives"] if item["alternative_id"] == step.alternative_id)
    states = {item["id"]: item["values"] for item in alternative["generated_states"]}
    edge = next((item for item in alternative["generated_edges"] if item["rule_id"] == step.rule_id
                 and finite_rules._same(states[item["from"]][step.phase_variable], step.from_phase)
                 and finite_rules._same(states[item["to"]][step.phase_variable], step.to_phase)), None)
    if edge is None:
        raise ValueError("A protocol phase requires an exact reachable native rule-edge instance")
    return {"alternative_id": step.alternative_id, "rule_id": step.rule_id, "phase_variable": step.phase_variable,
            "edge": dict(edge), "from_state": dict(states[edge["from"]]), "to_state": dict(states[edge["to"]]),
            "generated_graph_sha256": finite_rules.canonical_sha({"states": alternative["generated_states"], "edges": alternative["generated_edges"]}),
            "scope": "One reachable instance, not a universal guarantee over all transitions or an implementation/await-boundary proof."}


def _protocol(product, source_ids, document_ids, case, report):
    witnesses = source_ids | document_ids
    model_ids = _model_identifiers(case)
    bind = lambda identifier: _reference_binding(identifier, source_ids, document_ids, model_ids, set(), case["id"])
    actors = {item.id for item in product.actors}
    _unique([item.id for item in product.actors], "Protocol actors")
    _unique([item.variable for item in product.state_ownership], "State owners")
    if {item.variable for item in product.state_ownership} != set(case["variables"]):
        raise ValueError("Every finite variable requires one explicit state ownership/instrumentation binding")
    for item in [*product.actors, *product.state_ownership, *product.steps, *product.atomic_obligations,
                 *product.admission_choices, product.service_contract]:
        _known(item.evidence_ids, witnesses | set(model_ids), "Protocol evidence")
        for identifier in item.evidence_ids:
            bind(identifier)
    if any(item.actor_id not in actors for item in [*product.state_ownership, *product.steps]):
        raise ValueError("Protocol state and steps require declared actors")
    requests = {item.id: item for item in product.requests}
    _unique([item.id for item in product.requests], "Request fixtures")
    identity = product.request_identity
    if identity.empty_id in requests:
        raise ValueError("The empty request sentinel cannot alias a real request")
    role_variables = [identity.incoming_variable, identity.queued_variable, identity.inflight_variable]
    _unique(role_variables, "Request identity variables")
    for variable in role_variables:
        domain = case["variables"].get(variable, [])
        if not domain or not set(domain).issubset({identity.empty_id, *requests}) or not set(domain) & set(requests):
            raise ValueError("Request slots must hold distinct request IDs, never resource/path aliases")
    _known(product.workload.offered_requests, set(requests), "Common offered requests")
    alternatives = {item["id"]: item for item in case["alternatives"]}
    choices = {item.alternative_id: item for item in product.admission_choices}
    _unique([item.alternative_id for item in product.admission_choices], "Admission choices")
    if set(choices) != set(alternatives):
        raise ValueError("The same service contract must compare every modeled alternative")
    _unique(product.workload.environment_rule_ids, "Common environment rules")
    common_rules = []
    common_environment = []
    for identifier in product.workload.environment_rule_ids:
        rules = [next((rule for rule in alternative["rules"] if rule["id"] == identifier), None) for alternative in alternatives.values()]
        semantic = lambda rule: {key: rule[key] for key in ("id", "guard", "effects")}
        if any(rule is None for rule in rules) or any(semantic(rule) != semantic(rules[0]) for rule in rules[1:]):
            raise ValueError("All alternatives must receive exactly the same declared environment rules")
        common_rules.append(rules[0])
        common_environment.append({"rule_id": identifier, "semantics": semantic(rules[0]),
            "alternative_declarations": [{"alternative_id": alternative, "rule": deepcopy(rule)} for alternative, rule in zip(alternatives, rules)],
            "scope": "Only rule ID, guards and simultaneous effects are equal. Explanations and assumptions are preserved separately and require independent audit; common real-world assumptions are not proved."})
    offered = {case["initial"][identity.incoming_variable]}
    offered.update(effect["value"].get("literal") for rule in common_rules for effect in rule["effects"]
                   if effect["variable"] == identity.incoming_variable and effect["value"].get("variable") is None)
    if not set(product.workload.offered_requests).issubset(offered):
        raise ValueError("The common workload must actually offer every declared request")
    ref = product.workload.identity_coverage
    if ref.kind != "coverage":
        raise ValueError("Distinct same-resource request identity requires a native coverage witness")
    identity_result, witness = _result_reference(ref, report)
    state = witness["state"] if witness else {}
    pending, incoming, inflight = [state.get(variable) for variable in (identity.queued_variable, identity.incoming_variable, identity.inflight_variable)]
    if (pending not in requests or incoming not in requests or inflight not in requests
            or len({pending, incoming, inflight}) != 3
            or requests[pending].resource_id != requests[incoming].resource_id):
        raise ValueError("Coverage must demonstrate different in-flight, pending and arriving request IDs, including a shared resource")
    properties = {item["id"] for item in case["invariants"] + case["coverage"]}
    _known(product.service_contract.required_property_ids, properties, "Service contract properties")
    supersessions = product.service_contract.allowed_supersessions
    conflicts = []
    if product.service_contract.semantics == "each_request" and supersessions:
        conflicts.append({"alternative_id": None, "kind": "each_request_supersession",
                          "reason": "The each-request service contract declares snapshot supersessions; those declarations do not fulfill an obligation to preserve each accepted operation."})
    _unique([(item.older_request, item.newer_request) for item in supersessions], "Allowed supersessions")
    for pair in supersessions:
        older, newer = requests.get(pair.older_request), requests.get(pair.newer_request)
        if (older is None or newer is None or older.id == newer.id or older.resource_id != newer.resource_id
                or older.owner_generation != newer.owner_generation or older.payload_revision >= newer.payload_revision):
            raise ValueError("Coalescing requires an explicitly newer same-resource, same-generation snapshot")
    for choice in product.admission_choices:
        if choice.policy == "coalesce_latest" and (product.service_contract.semantics == "each_request" or not supersessions):
            conflicts.append({"alternative_id": choice.alternative_id, "kind": "coalescing_not_authorized",
                              "reason": "Declared coalescing is incompatible with the shared each-request contract or lacks explicitly allowed snapshot supersessions. A policy label does not prove actual merging or supersession reporting."})
        if choice.policy == "reject_new" and not product.service_contract.allow_rejection:
            conflicts.append({"alternative_id": choice.alternative_id, "kind": "rejection_not_authorized",
                              "reason": "The alternative declares rejection while the common service contract forbids rejecting requests. Actual rejection delivery is not established by this declaration."})
    steps = {item.id: item for item in product.steps}
    _unique([item.id for item in product.steps], "Protocol steps")
    _unique([(item.alternative_id, item.rule_id, item.kind) for item in product.steps], "Mapped protocol rule roles")
    dossier = []
    for item in product.steps:
        alternative = alternatives.get(item.alternative_id)
        rule = next((rule for rule in alternative["rules"] if rule["id"] == item.rule_id), None) if alternative else None
        if rule is None or item.phase_variable not in case["variables"]:
            raise ValueError("Protocol phases must reference actual same-case rules and state variables")
        phase_witness = _reachable_phase(item, report)
        if set(item.guard_indexes) != set(range(len(rule["guard"]))) or len(item.guard_indexes) != len(rule["guard"]):
            raise ValueError("A protocol step must map every actual guard exactly once")
        if set(item.effect_variables) != {effect["variable"] for effect in rule["effects"]} or len(set(item.effect_variables)) != len(item.effect_variables):
            raise ValueError("A protocol step must map every actual simultaneous effect")
        dossier.append({"id": item.id, "alternative_id": item.alternative_id, "rule_id": item.rule_id,
                        "actor_id": item.actor_id, "kind": item.kind, "phase": f"{item.phase_variable}: {item.from_phase} -> {item.to_phase}",
                        "guards": rule["guard"], "effects": rule["effects"],
                        "instruction": item.instruction, "implementation_status": item.implementation_status,
                        "evidence_ids": item.evidence_ids, "evidence_bindings": [bind(identifier) for identifier in item.evidence_ids],
                        "phase_scope": "reachable_instance_not_universal", "phase_witness": phase_witness,
                        "failure_outcome": item.failure_outcome})
    limits = list(dict.fromkeys([*product.limitations, *case["limits"], *report["issues"],
                                *["Policy/contract conflict: " + (item["alternative_id"] or product.service_contract.id) + ". " + item["reason"] for item in conflicts]]))
    _unique([item.id for item in product.atomic_obligations], "Atomic obligations")
    for obligation in product.atomic_obligations:
        referenced = [steps.get(identifier) for identifier in [*obligation.check_step_ids, obligation.start_step_id]]
        if any(step is None or step.alternative_id != obligation.alternative_id for step in referenced) or referenced[-1].kind != "native_start":
            raise ValueError("An atomic obligation requires same-alternative check steps and the actual native-start step")
        if any(step.kind != "check" or step.actor_id != referenced[-1].actor_id or step.phase_variable != referenced[-1].phase_variable for step in referenced[:-1]):
            raise ValueError("Atomic checks must be explicit check steps with the same actor and phase variable as native start")
        if obligation.mechanism == "unresolved" and not obligation.unresolved_reason.strip():
            raise ValueError("An unresolved atomic boundary must state its actual missing justification")
        limits.append(("Unresolved atomic boundary: " if obligation.mechanism == "unresolved" else "Declared atomic mechanism requires independent source/protocol audit: ")
                      + obligation.id + ". " + (obligation.unresolved_reason or obligation.justification))
    if not any(step.kind in {"completion", "reply", "failure"} for step in product.steps):
        raise ValueError("A concrete protocol must map a terminal completion, reply or failure phase")
    for identifier, alternative in alternatives.items():
        mapped = [step for step in product.steps if step.alternative_id == identifier]
        missing = sorted({rule["id"] for rule in alternative["rules"]} - {step.rule_id for step in mapped})
        if missing:
            limits.append("Unmapped source/protocol rules for " + identifier + ": " + ", ".join(missing) + ". Common environment equality is checked separately, not implementation correspondence.")
        if not any(step.kind in {"completion", "reply", "failure"} for step in mapped):
            limits.append("No mapped terminal completion, reply or failure phase for alternative " + identifier + ".")
    decisions = _decisions(product.changed_decisions, set(steps) | witnesses | set(model_ids), witnesses, report)
    for decision in decisions:
        decision["support_bindings"] = [_reference_binding(identifier, source_ids, document_ids, model_ids, set(steps), case["id"], local_kind="protocol_step") for identifier in decision["support_ids"]]
    groups = [{"alternative_id": alternative, "rule_id": rule,
               "step_ids": [item.id for item in product.steps if (item.alternative_id, item.rule_id) == (alternative, rule)],
               "scope": "Descriptive roles of the same atomic authored transition; not separate events, an await gap or implementation atomicity proof."}
              for alternative, rule in sorted({(item.alternative_id, item.rule_id) for item in product.steps})]
    references = [{"field": field, "record_id": getattr(item, "id", getattr(item, "variable", item.alternative_id if hasattr(item, "alternative_id") else "")),
                   "references": [bind(identifier) for identifier in item.evidence_ids]}
                  for field, rows in (("actors", product.actors), ("state_ownership", product.state_ownership),
                      ("admission_choices", product.admission_choices), ("service_contract", [product.service_contract]), ("atomic_obligations", product.atomic_obligations)) for item in rows]
    return {"dossier": dossier, "transition_role_groups": groups, "common_environment_bindings": common_environment,
            "protocol_evidence_bindings": references,
            "native_case_binding": {"case_id": case["id"], "case_input_sha256": finite_rules.canonical_sha(case), "native_case_report_sha256": finite_rules.canonical_sha(report)},
            "request_fixtures": [item.model_dump(mode="json") for item in product.requests],
            "service_contract": product.service_contract.model_dump(mode="json"),
            "admission_choices": [item.model_dump(mode="json") for item in product.admission_choices],
            "atomic_obligations": [item.model_dump(mode="json") for item in product.atomic_obligations],
            "identity_witness": {"state": state, "trace": identity_result["trace"]}, "conflicts": conflicts,
            "decision_table": decisions, "evidence_limits": limits}


def _markdown(products):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    lines = ["# Source-bound research work products", "", "Internal consistency is checked; implementation and publication merit are not established.", ""]
    for product in products:
        lines.extend(["## " + product["id"], "", product["reader_decision"], ""])
        if product["kind"] == "source_comparison":
            lines.extend([*["- Shared requirement: " + requirement for requirement in product["shared_requirements"]],
                          *["- Common comparison condition: " + condition for condition in product["common_conditions"]], ""])
            for alternative in product["alternatives"]:
                lines.extend(["### " + alternative["id"], "", alternative["label"], "",
                              "Implementation status: " + alternative["implementation_status"], "",
                              *[str(index + 1) + ". " + step for index, step in enumerate(alternative["implementation_steps"])], "",
                              *["- Cost: " + cost for cost in alternative["costs"]],
                              *["- Applies when: " + condition for condition in alternative["applicability_conditions"]], ""])
            lines.extend(["| Alternative | Criterion | Concrete observation | Witnesses |", "|---|---|---|---|"])
            lines.extend("| " + " | ".join(cell(value) for value in (row["alternative"], row["criterion"], row["observation"], ", ".join(row["evidence_ids"]))) + " |" for row in product["matrix"])
        else:
            lines.extend(["| Step | Actor | Actual finite phase | Instruction | Status |", "|---|---|---|---|---|"])
            lines.extend("| " + " | ".join(cell(row[key]) for key in ("id", "actor_id", "phase", "instruction", "implementation_status")) + " |" for row in product["dossier"])
        lines.extend(["", "| Condition | Existing-method decision | Additional analysis | Changed decision |", "|---|---|---|---|"])
        lines.extend("| " + " | ".join(cell(row[key]) for key in ("condition", "baseline_decision", "additional_analysis", "changed_decision")) + " |" for row in product["decision_table"])
        lines.extend(["", *["- " + limit for limit in product["evidence_limits"]], ""])
    return "\n".join(lines)


def check_work_products(value, source_ids, document_ids, *, cases=None, checker=None):
    """Produce a concrete matrix/dossier and decision table from verified inputs.

    Source/document ID sets are supplied by the controller after literal quote
    verification. Finite cases are recomputed rather than trusting a model's
    outcomes. Native checking establishes referential/internal consistency only.
    """
    parsed = value if isinstance(value, ResearchWorkProducts) else ResearchWorkProducts.model_validate(value)
    source_ids, document_ids = set(source_ids), set(document_ids)
    witnesses = source_ids | document_ids
    _unique([item.id for item in parsed.products], "Work-product IDs")
    protocols = [item for item in parsed.products if isinstance(item, TypedProtocol)]
    native = None
    comparisons = [item for item in parsed.products if isinstance(item, SourceComparison)]
    computed_comparison = any(any(row.result_refs for row in product.changed_decisions)
        or any(set(item.evidence_ids) - witnesses for item in product.observations)
        or any(set(row.support_ids) - witnesses - {item.id for item in product.observations}
               for row in product.changed_decisions) for product in comparisons)
    if protocols or computed_comparison:
        if not cases:
            raise ValueError("Computed or typed protocol work products require actual finite cases")
        native = finite_rules.check_evidence({"source_evidence": [{"id": identifier} for identifier in sorted(source_ids)],
            "document_evidence": [{"source_id": identifier} for identifier in sorted(document_ids)], "cases": cases}, source_ids, include_graph=True, document_witness_ids=document_ids)
        if checker is not None:
            def summary(report):
                return [{key: value for key, value in case.items() if key != "alternatives"} | {"alternatives": [
                    {key: value for key, value in alternative.items() if key not in {"generated_states", "generated_edges"}}
                    for alternative in case["alternatives"]]} for case in report["cases"]]
            if checker.get("checker_sha256") != native["checker_sha256"] or summary(checker) != summary(native):
                raise ValueError("Supplied checker must match recomputed cases and the exact native checker")
    case_lookup = {case["id"]: case for case in cases or []}
    reports = {case["case_id"]: case for case in native["cases"]} if native else {}
    products = []
    for product in parsed.products:
        if isinstance(product, SourceComparison):
            detail = _comparison(product, source_ids, document_ids, case_lookup, reports)
        else:
            if product.case_id not in case_lookup:
                raise ValueError("A protocol requires an exact existing finite case ID")
            detail = _protocol(product, source_ids, document_ids, case_lookup[product.case_id], reports[product.case_id])
        for row in product.changed_decisions:
            if not set(row.prior_method_evidence_ids) & document_ids:
                detail["evidence_limits"].append("No retained published-method comparison for decision " + row.id + "; novelty beyond existing methods remains unestablished.")
        for row in detail["decision_table"]:
            if not row["decision_changed"]:
                detail["evidence_limits"].append("Analysis confirms the baseline; no additional engineering decision is demonstrated: " + row["id"] + ".")
        products.append({"id": product.id, "kind": product.kind, "reader_decision": product.reader_decision, **detail})
    return {"contract_version": 1, "kind": "native_source_bound_research_work_products", "products": products,
            "markdown": _markdown(products), "work_products_sha256": finite_rules.canonical_sha(parsed.model_dump(mode="json")),
            "source_ids_sha256": finite_rules.canonical_sha(sorted(source_ids)), "document_ids_sha256": finite_rules.canonical_sha(sorted(document_ids)),
            "cases_sha256": finite_rules.canonical_sha(cases) if native else None,
            "checker_sha256": native["checker_sha256"] if native else None,
            "work_products_checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "internal_consistency_passed": True, "audit_required": True, "implementation_validated": False,
            "decision_changed_scope": "Textual difference only; substantive additional value requires independent audit.",
            "conflicts": [{"product_id": product["id"], **conflict} for product in products for conflict in product.get("conflicts", [])],
            "publication_quality_assessed": False, "evidence_limits": list(dict.fromkeys(limit for product in products for limit in product["evidence_limits"]))}

"""Typed research development inputs and bounded native rule-analysis contracts."""

from typing import Annotated, Literal
from copy import deepcopy
import hashlib

from pydantic import Field, StrictBool, StrictInt, StrictStr, model_validator

from ..models import Record
from .repository_paper import SourceEvidence, LiteratureEvidence
from .manuscript_improvement import FocusedManuscripts as DevelopmentManuscripts, FocusedAssessments as DevelopmentAssessments
from .finite_rules import check_evidence, canonical_sha
from .research_workproducts import ResearchWorkProducts, Id as WorkProductId

Text = Annotated[StrictStr, Field(min_length=12, max_length=6000)]
Identifier = Annotated[StrictStr, Field(pattern=r"^[a-z][a-z0-9_-]{0,59}$")]
Variable = Annotated[StrictStr, Field(pattern=r"^[a-z][a-z0-9_]{0,49}$")]
Digest = Annotated[StrictStr, Field(pattern=r"^[a-f0-9]{64}$")]
Scalar = StrictBool | StrictInt | StrictStr


class Operand(Record):
    variable: Variable | None = None
    literal: Scalar | None = None

    @model_validator(mode="after")
    def exactly_one(self):
        if (self.variable is None) == (self.literal is None):
            raise ValueError("Specify exactly one declared variable or strict scalar literal")
        return self


class Predicate(Record):
    left: Operand
    op: Literal["eq", "ne", "lt", "le", "gt", "ge"]
    right: Operand


class Effect(Record):
    variable: Variable
    value: Operand
    delta: StrictInt = Field(default=0, ge=-10000, le=10000)


class Rule(Record):
    id: Identifier
    event: Text
    guard: list[Predicate] = Field(max_length=16)
    effects: list[Effect] = Field(min_length=1, max_length=16)
    evidence_ids: list[StrictStr] = Field(min_length=1, max_length=12)
    implementation_mapping: Text
    abstraction_assumption: Text


class Invariant(Record):
    id: Identifier
    description: Text
    if_all: list[Predicate] = Field(max_length=16)
    then_all: list[Predicate] = Field(min_length=1, max_length=16)


class CoverageGoal(Record):
    id: Identifier
    description: Text
    conditions: list[Predicate] = Field(min_length=1, max_length=16)
    required: StrictBool = True


class RuleAlternative(Record):
    id: Identifier
    label: Text
    implementation_status: Literal["actual", "proposal", "environment_assumption"]
    rules: list[Rule] = Field(min_length=1, max_length=40)
    assumptions: list[Text] = Field(min_length=1, max_length=8)
    costs: list[Text] = Field(min_length=1, max_length=8)


class NegativeControl(Record):
    id: Identifier
    alternative_id: Identifier
    rule_id: Identifier
    kind: Literal["remove_guard", "replace_effect"]
    guard_index: StrictInt | None = Field(default=None, ge=0, le=15)
    effect: Effect | None = None
    expected_invariant_id: Identifier
    explanation: Text

    @model_validator(mode="after")
    def one_mutation(self):
        if self.kind == "remove_guard" and (self.guard_index is None or self.effect is not None) or self.kind == "replace_effect" and (self.effect is None or self.guard_index is not None):
            raise ValueError("A negative control changes exactly one existing guard or effect")
        return self


class ConditionFlip(Record):
    id: Identifier
    description: Text
    initial_overrides: dict[Variable, Scalar] = Field(min_length=1, max_length=16)
    alternative_id: Identifier
    property_id: Identifier


class RuleCase(Record):
    id: Identifier
    decision_problem: Text
    policy: Text
    variables: dict[Variable, list[Scalar]] = Field(min_length=1, max_length=16)
    initial: dict[Variable, Scalar] = Field(min_length=1, max_length=16)
    invariants: list[Invariant] = Field(min_length=1, max_length=10)
    coverage: list[CoverageGoal] = Field(min_length=1, max_length=12)
    alternatives: list[RuleAlternative] = Field(min_length=2, max_length=4)
    negative_controls: list[NegativeControl] = Field(min_length=1, max_length=8)
    condition_flips: list[ConditionFlip] = Field(min_length=1, max_length=4)
    decision_findings: list[Text] = Field(min_length=1, max_length=8)
    limits: list[Text] = Field(min_length=1, max_length=8)


class PlannedAlternative(Record):
    id: Identifier
    label: Text
    engineering_choice: Text
    implementation_status: Literal["actual", "proposal", "environment_assumption"]
    policy_assumptions: list[Text] = Field(min_length=1, max_length=8)
    costs: list[Text] = Field(min_length=1, max_length=8)


class PlannedCase(Record):
    id: Identifier
    reader_decision: Text
    alternatives: list[PlannedAlternative] = Field(min_length=2, max_length=4)
    properties: list[Text] = Field(min_length=1, max_length=10)
    evidence_tasks: list[Text] = Field(min_length=1, max_length=10)
    decisive_condition_flip: Text


class DevelopmentPlan(Record):
    decision_problem: Text
    source_evidence: list[SourceEvidence] = Field(min_length=1, max_length=40)
    document_evidence: list[LiteratureEvidence] = Field(max_length=12)
    cases: list[PlannedCase] = Field(min_length=1, max_length=3)
    inspect_source_files: list[StrictStr] = Field(min_length=1, max_length=20)
    expected_article_value: Text
    hard_limits: list[Text] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def distinct_inputs(self):
        if len({item.id for item in self.source_evidence}) != len(self.source_evidence) or len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Planning requires distinct actual source witnesses and case IDs")
        if len(set(self.inspect_source_files)) != len(self.inspect_source_files):
            raise ValueError("Source inspection files must not repeat")
        if any(len({item.id for item in case.alternatives}) != len(case.alternatives) for case in self.cases):
            raise ValueError("Each planned engineering alternative requires a distinct ID")
        return self


class DevelopmentComparison(Record):
    source_id: StrictStr = Field(min_length=1, max_length=100)
    established_method: Text
    local_difference: Text
    what_is_not_new: Text
    cost_or_limit: Text


class DevelopmentEvidence(Record):
    method_scope: Literal["generated_finite_rules_not_project_execution"]
    source_evidence: list[SourceEvidence] = Field(min_length=1, max_length=40)
    document_evidence: list[LiteratureEvidence] = Field(max_length=12)
    cases: list[RuleCase] = Field(min_length=1, max_length=3)
    comparisons: list[DevelopmentComparison] = Field(max_length=12)
    cross_case_findings: list[Text] = Field(min_length=1, max_length=10)
    limitations: list[Text] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def exact_ids(self):
        ids = [item.id for item in self.source_evidence]
        if len(set(ids)) != len(ids) or len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Repository witnesses and development cases require unique identifiers")
        documents = {item.source_id for item in self.document_evidence}
        if any(item.source_id not in documents for item in self.comparisons):
            raise ValueError("Each prior-method comparison requires retained primary-document evidence")
        return self


class DevelopmentResearchEvidence(DevelopmentEvidence):
    work_products: ResearchWorkProducts


class DevelopmentDesign(Record):
    plan: DevelopmentPlan
    evidence: DevelopmentResearchEvidence


class CorrespondenceFinding(Record):
    case_id: Identifier
    alternative_id: Identifier
    target_id: Identifier = Field(description="Existing same-case rule, invariant, coverage, negative-control or condition-flip ID; native admission verifies its case and alternative scope.")
    verdict: Literal["faithful", "needs_repair", "unverifiable"]
    reason: Text
    required_repair: StrictStr = Field(max_length=6000)


class DevelopmentRepair(Record):
    case_id: Identifier
    alternative_id: Identifier
    target_id: Identifier = Field(description="Existing same-case rule, invariant, coverage, negative-control or condition-flip ID; native admission verifies its case and alternative scope.")
    issue: Text
    exact_change: Text
    available_evidence_ids: list[StrictStr] = Field(min_length=1, max_length=12)
    safely_obtainable: StrictBool


class DevelopmentAudit(Record):
    evidence_sha256: Digest
    correspondence: list[CorrespondenceFinding] = Field(min_length=1, max_length=480)
    repair_actions: list[DevelopmentRepair] = Field(max_length=12)
    decisive_findings: list[Text] = Field(min_length=1, max_length=10)
    honest_limits: list[Text] = Field(min_length=1, max_length=12)
    ready_to_write: StrictBool
    repair_required: StrictBool

    @model_validator(mode="after")
    def attainable_repair(self):
        if self.repair_required != any(item.safely_obtainable for item in self.repair_actions):
            raise ValueError("Repair is required exactly when the audit identifies an attainable evidence-bound action")
        if self.ready_to_write and self.repair_required:
            raise ValueError("An audit cannot approve writing while requiring methodological repair")
        if self.ready_to_write and any(item.verdict == "needs_repair" for item in self.correspondence):
            raise ValueError("Required correspondence repairs preclude ready_to_write approval")
        return self


class WorkProductFinding(Record):
    product_id: WorkProductId
    verdict: Literal["faithful", "needs_repair", "unverifiable"]
    reason: Text
    required_repair: StrictStr = Field(max_length=6000)


class DevelopmentResearchAudit(DevelopmentAudit):
    work_product_findings: list[WorkProductFinding] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def concrete_readiness(self):
        if self.ready_to_write and any(item.verdict == "needs_repair" for item in self.work_product_findings):
            raise ValueError("Required work-product repairs preclude ready_to_write approval")
        return self


def development_readiness(development):
    """Readiness is current evidence plus an affirmative independent audit."""
    audit = development.get("audit") or {}
    current = development.get("evidence_sha256")
    if development.get("contract_version") == 3 and "design" in development.get("completed_stages", []) and development.get("selected_question") is None:
        reason = "no_answerable_question_from_retained_evidence"
    elif not development.get("evidence_artifact_id"):
        reason = "checked_research_evidence_required"
    elif development.get("contract_version", 1) >= 2 and not development.get("work_product_report_artifact_id"):
        reason = "checked_concrete_work_products_required"
    elif not development.get("audit_artifact_id") or not development.get("audit_sha256"):
        reason = "independent_method_audit_required"
    elif audit.get("evidence_sha256") != current:
        reason = "latest_evidence_requires_independent_reaudit"
    elif audit.get("repair_required"):
        reason = "methodological_repair_required"
    elif not audit.get("ready_to_write"):
        reason = "method_audit_not_ready_to_write"
    else:
        reason = "current_evidence_independently_ready"
    return {"ready_to_write": reason == "current_evidence_independently_ready", "reason": reason,
            "evidence_sha256": current, "audit_evidence_sha256": audit.get("evidence_sha256"),
            "audit_artifact_id": development.get("audit_artifact_id"), "audit_sha256": development.get("audit_sha256")}


def development_view(state):
    development = state["research_development"]
    if development.get("contract_version", 1) == 1 and development.get("closed"):
        return development
    readiness = development_readiness(development)
    pending = development_next_task(state)
    targets = set(development.get("write_versions", {}))
    if "review" in development.get("completed_stages", []) and targets and set(development.get("assessed_venues", [])) == targets:
        status, reason = "manuscripts_assessed", "bounded_manuscripts_independently_assessed"
    elif pending is not None:
        status, reason = ("ready_to_write" if readiness["ready_to_write"] else "research_in_progress"), "work_remaining"
    elif development.get("write_versions"):
        status, reason = "manuscripts_unassessed", "independent_manuscript_assessment_incomplete"
    else:
        status = "bounded_research_report"
        reason = readiness["reason"] if "audit" in development.get("completed_stages", []) else development.get("stop_reason", "bounded_research_stage_failed")
    return {**development, "status": status, "readiness": readiness,
            "stop_reason": development.get("stop_reason", reason) if development.get("closed") else reason}


def check_development_evidence(value, source_witness_ids=None, *, include_graph=False, document_witness_ids=None):
    if "research_design" in value:
        from .research_design_development import QuestionEvidence
        model = QuestionEvidence
    else:
        model = DevelopmentResearchEvidence if "work_products" in value else DevelopmentEvidence
    parsed = model.model_validate(value)
    return check_evidence(parsed.model_dump(mode="json"), source_witness_ids, include_graph=include_graph, document_witness_ids=document_witness_ids)


def computed_identifiers(evidence):
    """Exact names of native-checked models; callers authenticate and compute them first."""
    identifiers = set()
    for case in evidence["cases"]:
        identifiers.add(case["id"])
        identifiers.update(item["id"] for group in ("invariants", "coverage", "negative_controls", "condition_flips") for item in case[group])
        for alternative in case["alternatives"]:
            identifiers.add(alternative["id"])
            identifiers.update(item["id"] for item in alternative["rules"])
    return identifiers


def determine_audit_repair(value):
    model = DevelopmentResearchAudit if "work_product_findings" in value else DevelopmentAudit
    return model.model_validate(value).repair_required


def canonical_review_transport(value, targets, markdowns):
    """Repair exact current-target identity/locator roles, never a review judgment."""
    DevelopmentAssessments.model_validate(value)
    venues = [item["venue_id"] for item in value["assessments"]]
    if len(set(venues)) != len(venues) or set(venues) != set(targets) or set(markdowns) != set(targets):
        raise ValueError("Review transport must bind every exact current venue once")
    normalized = deepcopy(value)
    edits, counts = [], {}
    for index, review in enumerate(normalized["assessments"]):
        venue = review["venue_id"]
        target, markdown = targets[venue], markdowns[venue]
        expected = target["markdown_sha256"]
        if hashlib.sha256(markdown.encode("utf-8")).hexdigest() != expected:
            raise ValueError("Review transport requires exact frozen Markdown bytes")
        if review["manuscript_sha256"] != expected:
            if review["manuscript_sha256"] != target.get("draft_sha256"):
                raise ValueError("Review transport cannot map an unknown or older manuscript digest")
            edits.append({"path": ["assessments", index, "manuscript_sha256"],
                          "before": review["manuscript_sha256"], "after": expected,
                          "kind": "same_current_version_structured_draft_to_markdown"})
            review["manuscript_sha256"] = expected
        counts[venue] = 0
        for score_index, score in enumerate(review["scores"]):
            for passage_index, passage in enumerate(score["passages"]):
                if passage not in markdown:
                    first = passage[:1]
                    alternative = first.swapcase() + passage[1:]
                    if (not first or first not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz" or
                            alternative == passage or markdown.count(alternative) != 1):
                        raise ValueError("Review locator requires an exact unique first-ASCII-letter case match; no wording or other formatting repair is allowed")
                    edits.append({"path": ["assessments", index, "scores", score_index, "passages", passage_index],
                                  "before": passage, "after": alternative, "kind": "unique_first_ascii_letter_case_locator",
                                  "markdown_sha256": expected, "offset": markdown.index(alternative)})
                    score["passages"][passage_index] = alternative
                counts[venue] += 1
    DevelopmentAssessments.model_validate(normalized)
    restored = deepcopy(normalized)
    for edit in reversed(edits):
        container = restored
        for key in edit["path"][:-1]:
            container = container[key]
        if container[edit["path"][-1]] != edit["after"]:
            raise ValueError("Review transport restoration does not match its exact edit")
        container[edit["path"][-1]] = edit["before"]
    if restored != value:
        raise ValueError("Review transport must restore the exact original response object")
    return normalized, {"edits": edits, "literal_anchor_counts": counts,
        "original_response_object_sha256": canonical_sha(value),
        "normalized_response_object_sha256": canonical_sha(normalized),
        "restored_response_object_sha256": canonical_sha(restored),
        "restores_original_response_exactly": True,
        "scope": "Only the same current version's structured-draft/Markdown identity role and unique first-ASCII-letter-case quotation locators may change. All scores, reasons, recommendations, wording and scientific content remain unchanged; the original response remains retained."}


def development_next_task(state):
    """One bounded research contract; a repaired result requires a fresh audit."""
    development = state.get("research_development")
    if not development or development.get("closed") or state.get("finished"):
        return None
    calls = [item for item in state.get("calls", []) if item.get("round_id") == development["id"]]
    descriptor = lambda purpose: {"purpose": purpose, "venue_id": None, "manuscript_sha256": None, "action_id": None}
    pending = next((item for item in calls if item.get("outcome") == "reserved"), None)
    if pending:
        return descriptor(pending["purpose"])
    def retained_failure_can_continue(item):
        if item.get("outcome") != "rejected":
            return False
        if item.get("purpose") == "develop-audit":
            return development.get("audit_admission_repairs", {}).get(item.get("call_id"), {}).get("outcome") == "admitted"
        if item.get("purpose") == "develop-write":
            return development.get("write_admission_repairs", {}).get(item.get("call_id"), {}).get("outcome") == "admitted"
        if item.get("purpose") == "develop-review":
            return development.get("review_admission_repairs", {}).get(item.get("call_id"), {}).get("outcome") == "admitted"
        if (development.get("contract_version") == 2 and item.get("purpose") == "develop-repair" and
                development.get("evidence_admission_repairs", {}).get(item.get("call_id"), {}).get("outcome") == "admitted"):
            return True
        if item.get("call_id") not in development.get("evidence_failures", {}):
            return False
        if item.get("purpose") in {"develop-evidence", "develop-design"}:
            return True
        return (item.get("purpose") == "develop-repair" and development.get("repair_limit_reached")
                and all(development.get(key) for key in ("evidence_artifact_id", "checker_artifact_id", "supplement")))
    if any(item.get("outcome") in {"failed", "rejected", "interrupted"} and not retained_failure_can_continue(item) for item in calls):
        return None
    if development.get("contract_version") == 3:
        if "design" in development.get("completed_stages", []) and development.get("selected_question") is None:
            return None
        stages = ["question", "design"]
        if development.get("strengthening_needed"):
            stages.append("strengthen")
        stages += ["audit", "write", "review"]
        done = set(development.get("completed_stages", []))
        stage = next((item for item in stages if item not in done), None)
        if stage is None or stage == "write" and not development_readiness(development)["ready_to_write"]:
            return None
        remaining = min(development["additional_call_limit"] - len(calls),
                        development["authorized_model_call_limit"] - len(state.get("calls", [])),
                        state["policy"]["model_call_limit"] - len(state.get("calls", [])))
        needed = len(stages) - stages.index(stage)
        if remaining < needed or any(item["purpose"] == "develop-" + stage for item in calls):
            return None
        return descriptor("develop-" + stage)
    current_contract = development.get("contract_version", 1) == 2
    stages = (["design", "audit"] if current_contract else ["plan", "evidence", "audit"])
    if development.get("repair_required"):
        stages += ["repair"] + (["re-audit"] if current_contract else [])
    stages += ["write", "review"]
    done = {item.removeprefix("develop-") for item in development.get("completed_stages", [])}
    stage = next((item for item in stages if item not in done), None)
    if stage is None:
        return None
    if stage == "write" and not development_readiness(development)["ready_to_write"]:
        return None
    authorized_cap = development.get("authorized_model_call_limit",
        development.get("base_reservations", len(state.get("calls", [])) - len(calls)) + development.get("additional_call_limit", 6))
    remaining = min(min(6, development.get("additional_call_limit", 6)) - len(calls),
                    min(state.get("policy", {}).get("model_call_limit", authorized_cap), authorized_cap) - len(state.get("calls", [])))
    required = {"design": 4, "plan": 5, "evidence": 4, "audit": 3,
                "repair": 4 if current_contract else 3, "re-audit": 3, "write": 2, "review": 1}
    if remaining < required[stage] or any(item["purpose"] == "develop-" + stage for item in calls):
        return None
    return descriptor("develop-" + stage)

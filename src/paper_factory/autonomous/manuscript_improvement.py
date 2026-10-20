"""Bounded quality decisions. Scores are a declared proxy, never a publication promise."""

import hashlib
import json
import re

from typing import Annotated, Literal

from pydantic import Field, StrictBool, ValidationInfo, model_validator

from ..models import Record
from .repository_paper import RepositoryManuscript, RepositoryReferenceSelection, SourceEvidence

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Text = Annotated[str, Field(min_length=12, max_length=6000)]
Venue = Literal["ieee-software", "ieee-security-privacy"]
Criterion = Literal["contribution", "evidence", "method", "comparison", "practical_value",
                    "logic", "presentation", "venue_fit", "limitations"]
CRITERIA = ("contribution", "evidence", "method", "comparison", "practical_value",
            "logic", "presentation", "venue_fit", "limitations")
RUBRIC = {
    "id": "declared-magazine-quality-proxy-v1",
    "provenance": "Explicit new proxy rubric. The original external GPT review's detailed rubric was not supplied.",
    "target": 9,
    "scale": "0-10 integers; 9 requires convincing article-level evidence, not merely an absence of detected errors. Report uncertainty; do not predict acceptance.",
    "criteria": {
        "contribution": "A consequential, specific advance in readers' decisions beyond existing guidance; a well-written restatement is insufficient.",
        "evidence": "Central claims have adequate, inspectable, accurate evidence; scope and confidence match what was actually observed.",
        "method": "A traceable, reproducible analytical procedure with selection rationale, counterexamples and meaningful checks.",
        "comparison": "Fair, source-grounded comparison with the closest existing work and alternatives, identifying the actual additional value.",
        "practical_value": "Concrete, usable decisions, worked cases, costs, failure conditions and residual risks for the intended practitioner.",
        "logic": "A coherent argument where evidence supports inferences and conclusions, without unsupported generalization.",
        "presentation": "Precise, accessible, economical prose and clear explanatory tables or figures; no content is padded to meet a count.",
        "venue_fit": "A compelling feature article for the selected magazine's audience, scope and applicable article requirements.",
        "limitations": "Specific, consequential limits and alternative explanations integrated into claims and advice rather than a boilerplate disclaimer.",
    },
}


class ImprovementPolicy(Record):
    model_call_limit: int = Field(default=8, ge=7, le=24)
    action_limit: int = Field(default=4, ge=2, le=10)
    same_path_no_progress_limit: Literal[2] = 2
    target_score: Literal[9] = 9


class QualityScore(Record):
    criterion: Criterion
    score: int = Field(ge=0, le=10)
    uncertainty: Literal["low", "medium", "high"]
    passages: list[Text] = Field(min_length=1, max_length=5)
    reason: Text
    required_improvement: str = Field(max_length=6000)


class EvidenceLimit(Record):
    kind: Literal["available_evidence_limit", "access_failure", "budget_exhausted"]
    criterion: Criterion
    explanation: Text
    alternatives_attempted: list[Text] = Field(min_length=1, max_length=6)
    obtainable_evidence: Text


class IndependentAssessment(Record):
    venue_id: Venue
    manuscript_sha256: Digest
    scores: list[QualityScore] = Field(min_length=9, max_length=9)
    essential_errors: list[Text] = Field(max_length=12)
    recommendation: Literal["consider_submission", "revise_before_submission", "not_recommended"]
    recommendation_reason: Text
    evidence_limits: list[EvidenceLimit] = Field(max_length=9)

    @model_validator(mode="after")
    def complete_rubric(self):
        if {item.criterion for item in self.scores} != set(CRITERIA):
            raise ValueError("Every declared proxy criterion must be assessed exactly once")
        if self.essential_errors and self.recommendation == "consider_submission":
            raise ValueError("Essential factual, citation or source defects prohibit recommending submission")
        return self


class ResearchDirection(Record):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,59}$")
    reader_problem: Text
    added_value: Text
    closest_baseline: Text
    available_evidence: Text
    missing_evidence: Text
    selection_reason: Text


class ImprovementAction(Record):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,59}$")
    venue_id: Venue
    criterion: Criterion
    kind: Literal["verify_contract", "revise_analysis", "revise_manuscript", "retrieve_sources"]
    required_change: Text
    completion_condition: Text
    evidence_gain: Text
    expected_gain: int = Field(ge=1, le=10)
    estimated_cost: int = Field(ge=1, le=10)
    success_likelihood: Literal["low", "medium", "high"]

    @property
    def path(self):
        return self.kind + ":" + self.criterion


class ImprovementPlan(Record):
    directions: list[ResearchDirection] = Field(min_length=2, max_length=3)
    selected_direction_id: str = Field(min_length=1, max_length=60)
    actions: list[ImprovementAction] = Field(min_length=1, max_length=4)
    inspect_source_files: list[str] = Field(min_length=1, max_length=20)
    reference_selection: RepositoryReferenceSelection | None
    scope_and_limits: Text

    @model_validator(mode="after")
    def selected_direction(self):
        ids = [direction.id for direction in self.directions]
        if len(set(ids)) != len(ids) or self.selected_direction_id not in ids:
            raise ValueError("Compare distinct directions and select one explicitly")
        if len({action.id for action in self.actions}) != len(self.actions):
            raise ValueError("Improvement action IDs must be unique")
        return self


class ContributionRecord(Record):
    claim: Text
    baseline: Text
    additional_decision_value: Text
    evidence_ids: list[str] = Field(min_length=1, max_length=12)
    counterexample_or_failure_condition: Text
    applicability_limit: Text


class ManuscriptRevision(Record):
    venue_id: Venue
    action_id: str = Field(min_length=1, max_length=60)
    manuscript: RepositoryManuscript
    contributions: list[ContributionRecord] = Field(min_length=1, max_length=8)
    actual_work: list[Text] = Field(min_length=1, max_length=12)
    evidence_limits: list[EvidenceLimit] = Field(max_length=9)

    @model_validator(mode="after")
    def witnessed_contributions(self, info: ValidationInfo):
        ids = {item.id for item in self.manuscript.source_evidence}
        ids.update(item.source_id for item in [*self.manuscript.literature_evidence, *self.manuscript.document_evidence])
        computed = info.context.get("computed_evidence_ids", frozenset()) if isinstance(info.context, dict) else frozenset()
        if not isinstance(computed, (set, frozenset)) or any(not isinstance(identifier, str) or not identifier for identifier in computed):
            raise ValueError("Computed evidence IDs must be a trusted native set of nonempty strings")
        ids.update(computed)
        if any(not set(contribution.evidence_ids).issubset(ids) for contribution in self.contributions):
            raise ValueError("Each contribution must bind actual retained manuscript evidence IDs")
        return self


PRIMARY_PRIOR_CANDIDATES = [
    {"title": "User-Driven Access Control: Rethinking Permission Granting in Modern Operating Systems",
     "url": "https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/paper-48.pdf",
     "authors": ["Franziska Roesner", "Tadayoshi Kohno", "Alexander Moshchuk", "Bryan Parno", "Helen J. Wang", "Crispin Cowan"],
     "year": 2012, "publication": "IEEE Symposium on Security and Privacy (conference; distinct from the target magazine)"},
    {"title": "How to Ask for Permission", "url": "https://www.usenix.org/system/files/conference/hotsec12/hotsec12-final19.pdf",
     "authors": ["Adrienne Porter Felt", "Serge Egelman", "Matthew Finifter", "Devdatta Akhawe", "David Wagner"],
     "year": 2012, "publication": "USENIX HotSec"},
    {"title": "Capsicum: practical capabilities for UNIX", "url": "https://www.usenix.org/legacy/events/sec10/tech/full_papers/Watson.pdf",
     "authors": ["Robert N. M. Watson", "Jonathan Anderson", "Ben Laurie", "Kris Kennaway"],
     "year": 2010, "publication": "USENIX Security Symposium"},
]


class FocusedPriorChoice(Record):
    url: str = Field(min_length=12, max_length=2048)
    comparison_question: Text
    expected_method_difference: Text


class FocusedPriorSelection(Record):
    sources: list[FocusedPriorChoice] = Field(min_length=2, max_length=3)
    inspect_source_files: list[str] = Field(min_length=1, max_length=20)
    analytical_questions: list[Text] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def available_sources(self):
        urls = [item.url for item in self.sources]
        if len(set(urls)) != len(urls) or not set(urls).issubset({item["url"] for item in PRIMARY_PRIOR_CANDIDATES}):
            raise ValueError("Select two or three distinct supplied primary full-text candidates")
        return self


class ModelPredicate(Record):
    variable: str = Field(pattern=r"^[a-z][a-z0-9_]{0,49}$")
    equals: StrictBool


class AnalyticalState(Record):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,49}$")
    description: Text
    values: dict[str, StrictBool] = Field(min_length=2, max_length=12)


class AnalyticalTransition(Record):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,49}$")
    from_state: str = Field(min_length=1, max_length=50)
    to_state: str = Field(min_length=1, max_length=50)
    event: Text
    guard: list[ModelPredicate] = Field(max_length=12)
    effects: dict[str, StrictBool] = Field(min_length=1, max_length=12)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)
    abstraction_assumption: Text


class AnalyticalInvariant(Record):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,49}$")
    description: Text
    if_all: list[ModelPredicate] = Field(min_length=1, max_length=12)
    then_all: list[ModelPredicate] = Field(min_length=1, max_length=12)


class FiniteAnalyticalModel(Record):
    initial_state: str = Field(min_length=1, max_length=50)
    states: list[AnalyticalState] = Field(min_length=2, max_length=16)
    transitions: list[AnalyticalTransition] = Field(min_length=1, max_length=32)
    invariants: list[AnalyticalInvariant] = Field(min_length=1, max_length=8)
    scope: Text


class PriorMethodComparison(Record):
    source_id: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=24, max_length=3000)
    baseline_method: Text
    applicable_lesson: Text
    additional_decision_value: Text
    transfer_limit: Text


class CompletedWorksheet(Record):
    case_id: Literal["paste", "autosave"]
    concrete_scenario: Text
    retained_implementation_boundary: Text
    baseline_model: FiniteAnalyticalModel
    proposed_model: FiniteAnalyticalModel
    prior_comparisons: list[PriorMethodComparison] = Field(min_length=2, max_length=3)
    completed_decisions: list[Text] = Field(min_length=2, max_length=8)
    residual_risks: list[Text] = Field(min_length=1, max_length=8)
    proposed_change_not_implemented: Literal[True]


class FocusedAnalyticalResults(Record):
    method_scope: Literal["source_bound_finite_models_not_project_execution"]
    source_evidence: list[SourceEvidence] = Field(min_length=1, max_length=40,
        description="Actual repository files and manifest SHA values only. Primary-document quotations belong in worksheet prior_comparisons, not in repository paths.")
    worksheets: list[CompletedWorksheet] = Field(min_length=2, max_length=2)
    cross_case_findings: list[Text] = Field(min_length=1, max_length=8)
    limitations: list[Text] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def completed_cases(self):
        if {case.case_id for case in self.worksheets} != {"paste", "autosave"}:
            raise ValueError("Complete the Paste and Autosave worksheets exactly once")
        return self


def canonical_focused_analysis(value: dict, primary_cards: dict[str, dict], primary_texts: dict[str, str]) -> tuple[FocusedAnalyticalResults, dict | None]:
    """Separate proven primary-document witnesses from repository-only witnesses.

    No analytical claim, model, transition, actual source witness or document
    quotation is rewritten. Misclassified records stay in an immutable proof.
    """
    parsed = FocusedAnalyticalResults.model_validate(value)
    misplaced = [item for item in parsed.source_evidence if item.id in primary_cards]
    if not misplaced:
        return parsed, None
    transition_ids = {identifier for worksheet in parsed.worksheets
        for model in (worksheet.baseline_model, worksheet.proposed_model)
        for transition in model.transitions for identifier in transition.evidence_ids}
    for item in misplaced:
        card = primary_cards[item.id]
        if (card.get("status") != "retained" or not card.get("complete_body") or
                item.path != card.get("text_artifact_id") or item.sha256 != card.get("text_sha256") or
                hashlib.sha256(primary_texts.get(item.id, "").encode()).hexdigest() != card.get("text_sha256") or
                item.quote not in primary_texts.get(item.id, "")):
            raise ValueError("A separated primary witness must match its exact retained ID, text artifact, SHA and literal quotation")
        if item.id in transition_ids:
            raise ValueError("A primary witness referenced by a model transition cannot be removed from repository evidence")
    normalized = parsed.model_dump(mode="json")
    normalized["source_evidence"] = [item.model_dump(mode="json") for item in parsed.source_evidence if item.id not in primary_cards]
    if not normalized["source_evidence"]:
        raise ValueError("Analytical results must retain actual repository source witnesses")
    results = FocusedAnalyticalResults.model_validate(normalized)
    digest = lambda item: hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    unchanged = {key: item for key, item in parsed.model_dump(mode="json").items() if key != "source_evidence"}
    if unchanged != {key: item for key, item in results.model_dump(mode="json").items() if key != "source_evidence"}:
        raise ValueError("Primary evidence separation cannot alter analytical content")
    return results, {"kind": "separate_primary_document_witnesses_from_repository_witnesses",
        "primary_document_records": [item.model_dump(mode="json") for item in misplaced],
        "analytical_content_sha256": digest(unchanged),
        "repository_witnesses_sha256": digest(normalized["source_evidence"]),
        "scope": "Retained proven primary-document records in this proof instead of the repository-only witness list. Claims, worksheets, models, transitions, comparisons, actual source quotations and hashes remain unchanged."}


class FocusedManuscripts(Record):
    revisions: list[ManuscriptRevision] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def both_venues(self):
        if {item.venue_id for item in self.revisions} != {"ieee-software", "ieee-security-privacy"}:
            raise ValueError("Produce one complete manuscript for each supported magazine")
        return self


class FocusedAssessments(Record):
    assessments: list[IndependentAssessment] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def both_venues(self):
        ids = [item.venue_id for item in self.assessments]
        if len(set(ids)) != len(ids):
            raise ValueError("Independently assess each exact format-valid magazine manuscript once")
        return self


def check_finite_model(model: FiniteAnalyticalModel, evidence_ids: set[str]) -> dict:
    """Exhaustively check a small author-supplied abstraction, never project code."""
    states = {item.id: item for item in model.states}
    if len(states) != len(model.states) or model.initial_state not in states:
        raise ValueError("Finite models require unique states and an existing initial state")
    variables = set(next(iter(states.values())).values)
    if any(set(item.values) != variables for item in states.values()):
        raise ValueError("Every model state must declare exactly the same bounded Boolean variables")
    transitions = {item.id: item for item in model.transitions}
    if len(transitions) != len(model.transitions) or len({item.id for item in model.invariants}) != len(model.invariants):
        raise ValueError("Finite transitions and invariants require unique IDs")
    for item in model.transitions:
        if item.from_state not in states or item.to_state not in states or not set(item.evidence_ids).issubset(evidence_ids):
            raise ValueError("Finite transitions must bind declared states and actual source witnesses")
        if not set(item.effects).issubset(variables) or any(part.variable not in variables for part in item.guard):
            raise ValueError("Finite transition guards and effects must use declared variables")
        if len({part.variable for part in item.guard}) != len(item.guard):
            raise ValueError("Finite transition guards cannot repeat or contradict a variable")
        expected = {**states[item.from_state].values, **item.effects}
        if expected != states[item.to_state].values:
            raise ValueError("A finite transition's declared target contradicts its explicit effects")
    for item in model.invariants:
        if any(part.variable not in variables for part in [*item.if_all, *item.then_all]):
            raise ValueError("Finite invariants must use declared variables")
        if any(len({part.variable for part in parts}) != len(parts) for parts in (item.if_all, item.then_all)):
            raise ValueError("Finite invariant predicates cannot repeat or contradict a variable")

    def holds(parts, values):
        return all(values[part.variable] == part.equals for part in parts)

    reached, queue, enabled = {model.initial_state: []}, [model.initial_state], []
    while queue:
        identifier = queue.pop(0)
        for transition in model.transitions:
            if transition.from_state != identifier or not holds(transition.guard, states[identifier].values):
                continue
            enabled.append(transition.id)
            if transition.to_state not in reached:
                reached[transition.to_state] = [*reached[identifier], transition.id]
                queue.append(transition.to_state)
    violations = [{"invariant_id": invariant.id, "state_id": identifier, "transition_trace": trace}
        for identifier, trace in reached.items() for invariant in model.invariants
        if holds(invariant.if_all, states[identifier].values) and not holds(invariant.then_all, states[identifier].values)]
    return {"kind": "exhaustive_finite_author_supplied_model", "project_execution": False,
            "empirical_experiment": False, "reachable_states": list(reached),
            "unreachable_states": sorted(set(states) - set(reached)),
            "enabled_transitions": enabled, "invariant_checks": len(reached) * len(model.invariants),
            "violations": violations, "scope": model.scope}


def focused_next_task(state: dict) -> dict | None:
    focused = state["focused_round"]
    if focused.get("closed"):
        return None
    calls = [call for call in state["calls"] if call.get("round_id") == focused["id"]]
    pending = next((call for call in calls if call["outcome"] == "reserved"), None)
    if pending:
        return {key: pending.get(key) for key in ("purpose", "venue_id", "manuscript_sha256", "action_id")}
    if len(calls) >= 4 or len(state["calls"]) >= state["policy"]["model_call_limit"]:
        return None
    for purpose in ("focused-select", "focused-analyze", "focused-write", "focused-review"):
        prior = next((call for call in calls if call["purpose"] == purpose), None)
        if prior is None:
            return {"purpose": purpose, "venue_id": None, "manuscript_sha256": None, "action_id": None}
        repair_kind = "analysis_repairs" if purpose == "focused-analyze" else "writer_repairs" if purpose == "focused-write" else None
        repaired = bool(repair_kind and focused.get(repair_kind, {}).get(prior["call_id"], {}).get("outcome") == "admitted")
        if (prior["outcome"] != "completed" and not repaired) or purpose not in focused.get("completed_stages", []):
            return None
    return None


def canonical_quality_revision(value: dict, *, computed_evidence_ids: set[str] | frozenset[str] | None = None) -> tuple[ManuscriptRevision, dict | None]:
    """Own the bibliography and exact citation syntax without rewriting prose."""
    context = {"computed_evidence_ids": computed_evidence_ids} if computed_evidence_ids is not None else None
    revision = ManuscriptRevision.model_validate(value, context=context)
    sections = revision.manuscript.sections
    removed = [section for section in sections if section.heading.strip().casefold() in {"reference", "references"}]
    scientific = [section.model_dump(mode="json") for section in sections if section not in removed]
    normalized_sections = [{**section} for section in scientific]
    source_ids = {item.id for item in revision.manuscript.source_evidence}
    external_ids = {item.source_id for item in [*revision.manuscript.literature_evidence, *revision.manuscript.document_evidence]}
    replacements = []
    for index, section in enumerate(normalized_sections):
        changes = []
        delta = 0

        def canonical_token(match):
            nonlocal delta
            kind, identifier = match.groups()
            if identifier not in (source_ids if kind == "source" else external_ids):
                raise ValueError("A citation delimiter repair requires an actual retained manuscript witness ID")
            token = "{{" + kind + ":" + identifier + "}}"
            changes.append({"original": match.group(), "canonical": token,
                            "normalized_offset": match.start() + delta})
            delta += len(token) - len(match.group())
            return token

        original_text = section["text"]
        section["text"] = re.sub(r"\[(source|document|citation):([^\]\r\n]+)\]", canonical_token, original_text)
        restored = section["text"]
        for change in reversed(changes):
            offset = change["normalized_offset"]
            if restored[offset:offset + len(change["canonical"])] != change["canonical"]:
                raise ValueError("Citation delimiter normalization must be exactly reversible")
            restored = restored[:offset] + change["original"] + restored[offset + len(change["canonical"]):]
        if restored != original_text:
            raise ValueError("Citation delimiter normalization cannot change scientific prose")
        if changes:
            replacements.append({"section_index": index, "heading": section["heading"], "tokens": changes})
    if not removed and not replacements:
        return revision, None
    normalized = revision.model_dump(mode="json")
    normalized["manuscript"]["sections"] = normalized_sections
    revision = ManuscriptRevision.model_validate(normalized, context=context)
    digest = lambda item: hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    proof = {"kind": "controller_owned_bibliography", "removed_sections": [
        {"heading": section.heading, "text_sha256": hashlib.sha256(section.text.encode()).hexdigest()} for section in removed],
        "scientific_sections_sha256": digest(normalized_sections),
        "scope": "Removed model-authored bibliography and canonicalized exact citation delimiters only. Scientific prose, claims, evidence IDs and source witnesses remain unchanged; canonical verified references are generated by the controller."}
    if replacements:
        proof["citation_delimiters"] = {"kind": "exact_retained_witness_citation_delimiters",
            "replacement_count": sum(len(section["tokens"]) for section in replacements),
            "sections": replacements, "original_sections_sha256": digest(scientific),
            "normalized_sections_sha256": digest(normalized_sections),
            "restored_sections_sha256": digest(scientific), "exact_original_restoration_verified": True}
    return revision, proof


def canonical_focused_revision(value: dict, primary_cards: dict[str, dict], primary_texts: dict[str, str], *, computed_evidence_ids: set[str] | frozenset[str] | None = None) -> tuple[ManuscriptRevision, dict]:
    """Map exact acquired primary citations to their native retained-document kind."""
    revision, bibliography = canonical_quality_revision(value, computed_evidence_ids=computed_evidence_ids)
    original = revision.model_dump(mode="json")
    moved = [item for item in revision.manuscript.literature_evidence if item.source_id in primary_cards]
    unknown = [item.source_id for item in revision.manuscript.literature_evidence
               if item.source_id.startswith("focused-document-") and item.source_id not in primary_cards]
    if unknown:
        raise ValueError("An acquired primary citation requires an actual retained focused source ID")
    if not moved:
        return revision, {"bibliography": bibliography, "primary_citation_kind": None}
    for item in moved:
        card, text = primary_cards[item.source_id], primary_texts.get(item.source_id, "")
        if (card.get("status") != "retained" or not card.get("complete_body") or
                item.text_sha256 != card.get("text_sha256") or
                hashlib.sha256(text.encode()).hexdigest() != card.get("text_sha256") or item.quote not in text):
            raise ValueError("A primary citation kind repair requires its exact retained ID, whole-text SHA and literal quote")
        if any(existing.source_id == item.source_id and existing.quote == item.quote
               for existing in revision.manuscript.document_evidence):
            raise ValueError("A primary citation kind repair cannot merge ambiguous duplicate witnesses")
    normalized = revision.model_dump(mode="json")
    manuscript = normalized["manuscript"]
    manuscript["literature_evidence"] = [item.model_dump(mode="json") for item in revision.manuscript.literature_evidence
                                          if item.source_id not in primary_cards]
    manuscript["document_evidence"].extend(item.model_dump(mode="json") for item in moved)
    counts = {}
    for identifier in dict.fromkeys(item.source_id for item in moved):
        before, after = "{{citation:" + identifier + "}}", "{{document:" + identifier + "}}"
        counts[identifier] = sum(section["text"].count(before) for section in manuscript["sections"])
        existing_document_tokens = sum(section["text"].count(after) for section in manuscript["sections"])
        if not counts[identifier] and not existing_document_tokens:
            raise ValueError("A primary citation kind repair requires its actual exact article citation token")
        for section in manuscript["sections"]:
            section["text"] = section["text"].replace(before, after)
    context = {"computed_evidence_ids": computed_evidence_ids} if computed_evidence_ids is not None else None
    repaired = ManuscriptRevision.model_validate(normalized, context=context)
    digest = lambda item: hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    invariant = {key: item for key, item in original.items() if key != "manuscript"}
    invariant["manuscript"] = {key: item for key, item in original["manuscript"].items()
                                if key not in {"sections", "literature_evidence", "document_evidence"}}
    return repaired, {"bibliography": bibliography, "primary_citation_kind": {
        "kind": "retained_primary_citation_kind", "moved_witnesses": [item.model_dump(mode="json") for item in moved],
        "exact_token_replacements": counts, "unchanged_claims_and_source_witnesses_sha256": digest(invariant),
        "original_sections_sha256": digest(original["manuscript"]["sections"]),
        "normalized_sections_sha256": digest(manuscript["sections"]),
        "scope": "Only exact verified acquired-primary witness classification and {{citation:ID}} to {{document:ID}} markers changed. All other prose, claims, source witnesses, contributions and prior-revision SHA remain unchanged."}}


def best_assessment(reviews: list[dict]) -> dict | None:
    """Safety and the weakest criterion precede gains in average prose quality."""
    if not reviews:
        return None

    def rank(review):
        scores = {item["criterion"]: item["score"] for item in review["scores"]}
        # Supporting evidence and method must reach adequacy before aggregate gains matter.
        adequate = min(scores["evidence"], scores["method"], 7)
        # Reviewers split defects into prose bullets differently. Their count is
        # not a measure of severity and must not favor a weaker article.
        return (not bool(review["essential_errors"]), adequate, min(scores.values()),
                scores["contribution"], scores["evidence"], sum(scores.values()))

    return max(reviews, key=rank)


def target_achieved(review: dict | None) -> bool:
    return bool(review and review["recommendation"] == "consider_submission" and not review["essential_errors"] and
                all(item["score"] >= 9 for item in review["scores"]))


def path_stopped(actions: list[dict], path: str) -> bool:
    relevant = [item for item in actions if item["path"] == path and item.get("completed")]
    return len(relevant) >= 2 and all(not item.get("material_progress") for item in relevant[-2:])


def next_task(state: dict) -> dict | None:
    """All directions and retries share one fixed lifetime budget for this study."""
    if state.get("research_development"):
        from .research_development import development_next_task
        return development_next_task(state)
    if state.get("focused_round") and not state["focused_round"].get("closed"):
        return focused_next_task(state)
    if state["finished"]:
        return None
    if all(target_achieved(best_assessment(state["reviews"].get(venue, []))) for venue in state["versions"]):
        return None
    pending = next((call for call in state["calls"] if call["outcome"] == "reserved"), None)
    if pending:
        return {key: pending.get(key) for key in ("purpose", "venue_id", "manuscript_sha256", "action_id")}
    if len(state["calls"]) >= state["policy"]["model_call_limit"]:
        return None
    for venue, version in state["versions"].items():
        baseline = version[0]
        if not any(review["manuscript_sha256"] == baseline["markdown_sha256"] for review in state["reviews"].get(venue, [])):
            if not any(call["purpose"] == "review" and call["venue_id"] == venue and
                       call["manuscript_sha256"] == baseline["markdown_sha256"] for call in state["calls"]):
                return {"purpose": "review", "venue_id": venue, "manuscript_sha256": baseline["markdown_sha256"]}
    if state["plan"] is None:
        return None if any(call["purpose"] == "plan" for call in state["calls"]) else {
            "purpose": "plan", "venue_id": None, "manuscript_sha256": None}
    for venue, versions in state["versions"].items():
        latest = versions[-1]
        if len(versions) > 1 and not any(review["manuscript_sha256"] == latest["markdown_sha256"] for review in state["reviews"].get(venue, [])):
            if not any(call["purpose"] == "review" and call["venue_id"] == venue and
                       call["manuscript_sha256"] == latest["markdown_sha256"] for call in state["calls"]):
                return {"purpose": "review", "venue_id": venue, "manuscript_sha256": latest["markdown_sha256"]}
    if len(state["calls"]) + 2 > state["policy"]["model_call_limit"]:
        return None  # A writer without budget for its independent reviewer is not started.
    if len(state["actions"]) >= state["policy"]["action_limit"]:
        return None
    # Give every selected venue a first improvement before spending spare budget on one again.
    actions = sorted(state["plan"]["actions"], key=lambda item: (
        sum(action["venue_id"] == item["venue_id"] for action in state["actions"]),
        -(item["expected_gain"] / item["estimated_cost"])))
    for action in actions:
        if any(item["id"] == action["id"] for item in state["actions"]):
            continue
        path = action["kind"] + ":" + action["criterion"]
        if path_stopped(state["actions"], path):
            continue
        if target_achieved(best_assessment(state["reviews"].get(action["venue_id"], []))):
            continue
        return {"purpose": "revise", "venue_id": action["venue_id"],
                "manuscript_sha256": state["versions"][action["venue_id"]][-1]["markdown_sha256"],
                "action_id": action["id"]}
    return None


def improvement_view(state: dict) -> dict:
    if state.get("research_development"):
        from .research_development import development_view
        state = {**state, "research_development": development_view(state)}
    best = {venue: best_assessment(state["reviews"].get(venue, [])) for venue in state["versions"]}
    achieved = bool(best) and all(target_achieved(review) for review in best.values())
    descriptor = next_task(state)
    if achieved:
        reason = "target_achieved"
    elif (state["finished"] or descriptor is None) and state.get("research_development"):
        reason = state["research_development"].get("stop_reason", "bounded_research_completed")
    elif state["finished"] or descriptor is None:
        unused = [action for action in (state["plan"] or {}).get("actions", [])
                  if not any(item["id"] == action["id"] for item in state["actions"])]
        if state["plan"] and not unused:
            reason = "planned_actions_completed"
        elif len(state["calls"]) + 2 > state["policy"]["model_call_limit"]:
            reason = "budget_exhausted"
        else:
            reason = "bounded_actions_unavailable"
    else:
        reason = "work_remaining"
    return {**state, "next_task": descriptor, "target_achieved": achieved, "stop_reason": reason,
            "best_assessments": best,
            "counts": {"model_attempts": len(state["calls"]), "actions": len(state["actions"]),
                       "reviews": sum(len(items) for items in state["reviews"].values()),
                       "revisions": sum(len(items) - 1 for items in state["versions"].values()),
                       "format_repairs": len(state.get("repairs", {}))},
            "recommendations": {venue: {"recommendation": review["recommendation"] if review else "not_recommended",
                "reason": review["recommendation_reason"] if review else "No independent assessment completed within the retained budget.",
                "target_achieved": target_achieved(review)} for venue, review in best.items()}}

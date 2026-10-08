"""Native host submissions and frozen scientific artifacts."""

from typing import Annotated, Literal
import math

from pydantic import Field, field_validator, model_serializer, model_validator

from ..models import Record


class Measure(Record):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    unit: str = Field(default="", max_length=80)
    description: str = Field(min_length=8, max_length=1000)


class ResearchClaim(Record):
    mode: Literal["formal", "empirical", "finite_enumeration"]
    claim: str = Field(min_length=24, max_length=4000)
    scope: str = Field(min_length=24, max_length=4000)
    importance: str = Field(min_length=24, max_length=4000)
    validation_plan: str = Field(min_length=24, max_length=4000)

    @field_validator("claim", "scope", "importance", "validation_plan")
    @classmethod
    def substantive_claim(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 24:
            raise ValueError("Research claims require substantive scope and validation reasoning")
        return value


class ResearchPlan(Record):
    feasible: bool
    reason: str = Field(min_length=8, max_length=4000)
    title: str = Field(min_length=8, max_length=300)
    question: str = Field(min_length=12, max_length=2000)
    research_gap: str = Field(min_length=24, max_length=4000)
    expected_contribution: str = Field(min_length=24, max_length=4000)
    comparison_rationale: str = Field(min_length=24, max_length=4000)
    sampling_rationale: str = Field(min_length=24, max_length=4000)
    runtime: Literal["quickjs"]
    source_files: list[str] = Field(min_length=1, max_length=20)
    production_entrypoint: str = Field(default="", max_length=300)
    dependencies: list[str] = Field(default_factory=list, max_length=0)
    conditions: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(min_length=2, max_length=6)
    metrics: list[Measure] = Field(min_length=1, max_length=8)
    comparator: str = Field(min_length=12, max_length=3000)
    independent_oracle: str = Field(min_length=12, max_length=3000)
    sampling_unit: str = Field(min_length=8, max_length=1000)
    units_per_seed: int = Field(ge=3, le=500, description=(
        "Distinct units for EACH seed; total = units_per_seed * len(seeds). "
        "Procedures and parameters must agree with this count."
    ))
    seeds: list[int] = Field(min_length=2, max_length=20)
    parameters: dict[Annotated[str, Field(min_length=1, max_length=100)], str | int | float] = Field(default_factory=dict)
    procedure: list[str] = Field(min_length=3, max_length=30)
    analysis_method: str = Field(min_length=12, max_length=2000)
    limitations: list[str] = Field(min_length=2, max_length=12)
    literature_queries: list[str] = Field(min_length=1, max_length=8)
    research_claim: ResearchClaim | None = None

    @model_serializer(mode="wrap")
    def retained_protocol(self, handler):
        if any(type(item) is float and not math.isfinite(item) for item in self.parameters.values()):
            raise ValueError("Frozen protocol parameters must be finite scalar values")
        value = handler(self)
        # Historical frozen protocols must retain their original canonical digest.
        # Fresh proposal submissions require this field at the workflow boundary.
        if self.research_claim is None:
            value.pop("research_claim", None)
        return value

    @field_validator("parameters")
    @classmethod
    def finite_parameters(cls, value):
        if any(type(item) is float and not math.isfinite(item) for item in value.values()):
            raise ValueError("Frozen protocol parameters must be finite scalar values")
        return value

    @field_validator("research_gap", "expected_contribution", "comparison_rationale", "sampling_rationale")
    @classmethod
    def substantive_rationale(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 24:
            raise ValueError("Research value and design rationales require substantive text")
        return value

    @model_validator(mode="after")
    def distinct_protocol(self):
        for values in (self.conditions, self.seeds, self.source_files, [m.name for m in self.metrics]):
            if len(values) != len(set(values)):
                raise ValueError("Protocol identifiers, conditions, seeds and metrics must be distinct")
        return self


class GeneratedFile(Record):
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=262144)


class CodeBundle(Record):
    runtime: Literal["quickjs"]
    entrypoint: str = Field(min_length=1, max_length=200)
    files: list[GeneratedFile] = Field(min_length=1, max_length=12)
    explanation: str = Field(min_length=12, max_length=5000)

    @model_validator(mode="after")
    def distinct_files(self):
        names = [f.path for f in self.files]
        if len(names) != len(set(names)) or self.entrypoint not in names:
            raise ValueError("Generated bundle requires distinct files and a declared entrypoint")
        if sum(len(f.content.encode("utf-8")) for f in self.files) > 512 * 1024:
            raise ValueError("Generated bundle exceeds 512 KiB")
        return self


class DraftSection(Record):
    heading: str = Field(min_length=3, max_length=100)
    text: str = Field(min_length=40, max_length=30000)


class ManuscriptDraft(Record):
    title: str = Field(min_length=8, max_length=300)
    sections: list[DraftSection] = Field(min_length=10, max_length=14)


class ScientificReview(Record):
    accepted: bool
    issues: list[str] = Field(default_factory=list, max_length=20)
    checks: list[str] = Field(default_factory=list, max_length=20)


class QualityCriterion(Record):
    passed: bool
    reason: str = Field(min_length=24, max_length=4000)

    @field_validator("reason")
    @classmethod
    def substantive_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 24:
            raise ValueError("Quality criteria require a substantive reason")
        return value


class StudyRedesignReview(Record):
    """Permission to prepare a distinct successor, never scientific approval."""
    accepted: bool
    issues: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(max_length=12)
    scientific_difference: QualityCriterion
    prior_evidence: QualityCriterion
    feasibility: QualityCriterion

    @model_validator(mode="after")
    def consistent_decision(self):
        eligible = all(item.passed for item in (
            self.scientific_difference, self.prior_evidence, self.feasibility)) and not self.issues
        if self.accepted != eligible or (not self.accepted and not self.issues) or any(not item.strip() for item in self.issues):
            raise ValueError("Redesign preparation must agree with every criterion and record rejection issues")
        return self


class LiteratureSelection(Record):
    source_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    excerpt_index: int = Field(ge=0)
    relevance: str = Field(min_length=24, max_length=4000)

    @field_validator("relevance")
    @classmethod
    def substantive_relevance(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 24:
            raise ValueError("Selected literature requires a substantive relevance explanation")
        return value


class ClosestWork(Record):
    source_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    excerpt_index: int = Field(ge=0)
    quote: str = Field(min_length=80, max_length=1500)
    known_result: str = Field(min_length=24, max_length=4000)
    difference: str = Field(min_length=24, max_length=4000)

    @field_validator("known_result", "difference")
    @classmethod
    def substantive_comparison(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 24:
            raise ValueError("Closest-work comparisons require substantive reasoning")
        return value


class PublicationReadiness(Record):
    novelty: QualityCriterion
    significance: QualityCriterion
    validation: QualityCriterion
    claim: str = Field(min_length=24, max_length=4000)
    scope: str = Field(min_length=24, max_length=4000)
    evidence_basis: str = Field(min_length=24, max_length=4000)
    evidence_mode: Literal["formal", "empirical", "finite_enumeration"]
    closest_work: list[ClosestWork] = Field(max_length=12)
    analysis_keys: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(default_factory=list, max_length=32)
    fixture_labels: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(default_factory=list, max_length=12)
    proof_section: str | None = Field(default=None, min_length=3, max_length=100)
    proof_quote: str | None = Field(default=None, min_length=80, max_length=12000)

    @field_validator("claim", "scope", "evidence_basis")
    @classmethod
    def substantive_basis(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 24:
            raise ValueError("Publication readiness requires substantive evidence reasoning")
        return value

    @model_validator(mode="after")
    def distinct_evidence(self):
        references = [(work.source_id, work.excerpt_index) for work in self.closest_work]
        if len(references) != len(set(references)) or any(
                len(values) != len(set(values)) for values in (self.analysis_keys, self.fixture_labels)):
            raise ValueError("Publication evidence references must be distinct")
        if (self.proof_section is None) != (self.proof_quote is None):
            raise ValueError("Proof evidence requires both a section and a literal passage")
        return self

    def eligible(self) -> bool:
        return bool(self.closest_work) and all(
            item.passed for item in (self.novelty, self.significance, self.validation))


class StudyReview(Record):
    accepted: bool
    issues: list[str] = Field(default_factory=list, max_length=20)
    question: QualityCriterion
    contribution: QualityCriterion
    literature: QualityCriterion
    comparison: QualityCriterion
    sampling: QualityCriterion
    feasibility: QualityCriterion
    selected_sources: list[LiteratureSelection] = Field(max_length=12)
    publication_readiness: PublicationReadiness | None = None

    @model_validator(mode="after")
    def consistent_decision(self):
        criteria = (self.question, self.contribution, self.literature,
                    self.comparison, self.sampling, self.feasibility)
        eligible = all(item.passed for item in criteria) and not self.issues and bool(self.selected_sources)
        if self.publication_readiness is not None:
            eligible = eligible and self.publication_readiness.eligible()
        if self.accepted != eligible:
            raise ValueError("Study acceptance must agree with all criteria, issues and selected literature")
        selected = [(item.source_id, item.excerpt_index) for item in self.selected_sources]
        if len(selected) != len(set(selected)):
            raise ValueError("Selected source and excerpt pairs must be distinct")
        return self


class ManuscriptRepairAction(Record):
    criterion: Literal["contribution", "literature", "interpretation", "presentation"]
    action: str = Field(min_length=24, max_length=4000)

    @field_validator("action")
    @classmethod
    def substantive_action(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 24:
            raise ValueError("Manuscript repair actions require substantive text")
        return value


class ManuscriptRemediation(Record):
    strategy: Literal["revise_manuscript", "redesign_study", "infeasible"]
    reason: str = Field(min_length=24, max_length=4000)
    actions: list[ManuscriptRepairAction] = Field(min_length=1, max_length=12)
    evidence_gaps: list[Annotated[str, Field(min_length=24, max_length=4000)]] = Field(max_length=12)

    @field_validator("reason")
    @classmethod
    def substantive_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 24:
            raise ValueError("Manuscript remediation requires a substantive reason")
        return value

    @field_validator("evidence_gaps")
    @classmethod
    def substantive_evidence_gaps(cls, values: list[str]) -> list[str]:
        values = [value.strip() for value in values]
        if any(len(value) < 24 for value in values):
            raise ValueError("Manuscript evidence gaps require substantive text")
        return values

    @model_validator(mode="after")
    def evidence_matches_strategy(self):
        if self.strategy == "revise_manuscript" and self.evidence_gaps:
            raise ValueError("Manuscript revision cannot require missing evidence")
        if self.strategy == "redesign_study" and not self.evidence_gaps:
            raise ValueError("Study redesign requires a concrete evidence gap")
        return self


class ManuscriptReview(ScientificReview):
    contribution: QualityCriterion
    literature: QualityCriterion
    interpretation: QualityCriterion
    presentation: QualityCriterion
    remediation: ManuscriptRemediation | None = None
    publication_readiness: PublicationReadiness | None = None

    @model_validator(mode="after")
    def consistent_decision(self):
        criteria = (self.contribution, self.literature, self.interpretation, self.presentation)
        eligible = all(item.passed for item in criteria) and not self.issues
        if self.publication_readiness is not None:
            eligible = eligible and self.publication_readiness.eligible()
        if self.accepted != eligible:
            raise ValueError("Manuscript acceptance must agree with all quality criteria and issues")
        if self.accepted and self.remediation is not None:
            raise ValueError("Accepted manuscripts cannot require remediation")
        if self.remediation is not None:
            failed = {name for name in ("contribution", "literature", "interpretation", "presentation")
                      if not getattr(self, name).passed}
            if self.publication_readiness is not None:
                if not self.publication_readiness.novelty.passed or not self.publication_readiness.significance.passed:
                    failed.add("contribution")
                if not self.publication_readiness.validation.passed:
                    failed.add("interpretation")
            covered = {action.criterion for action in self.remediation.actions}
            if failed - covered:
                raise ValueError("Manuscript remediation must address every failed criterion")
        return self


class FrozenArtifact(Record):
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size: int = Field(ge=0)

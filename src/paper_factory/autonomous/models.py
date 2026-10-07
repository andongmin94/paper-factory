"""Native host submissions and frozen scientific artifacts."""

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from ..models import Record


class Measure(Record):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    unit: str = Field(default="", max_length=80)
    description: str = Field(min_length=8, max_length=1000)


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

    @model_validator(mode="after")
    def consistent_decision(self):
        criteria = (self.question, self.contribution, self.literature,
                    self.comparison, self.sampling, self.feasibility)
        eligible = all(item.passed for item in criteria) and not self.issues and bool(self.selected_sources)
        if self.accepted != eligible:
            raise ValueError("Study acceptance must agree with all criteria, issues and selected literature")
        selected = [item.source_id for item in self.selected_sources]
        if len(selected) != len(set(selected)):
            raise ValueError("Select one relevant excerpt per distinct source")
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

    @model_validator(mode="after")
    def consistent_decision(self):
        criteria = (self.contribution, self.literature, self.interpretation, self.presentation)
        eligible = all(item.passed for item in criteria) and not self.issues
        if self.accepted != eligible:
            raise ValueError("Manuscript acceptance must agree with all quality criteria and issues")
        if self.accepted and self.remediation is not None:
            raise ValueError("Accepted manuscripts cannot require remediation")
        if self.remediation is not None:
            failed = {name for name in ("contribution", "literature", "interpretation", "presentation")
                      if not getattr(self, name).passed}
            covered = {action.criterion for action in self.remediation.actions}
            if failed - covered:
                raise ValueError("Manuscript remediation must address every failed criterion")
        return self


class FrozenArtifact(Record):
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size: int = Field(ge=0)

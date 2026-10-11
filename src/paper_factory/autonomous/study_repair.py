"""Bounded explanations of failed study criteria; none is approval or new evidence."""

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from ..models import Record
from .models import QualityCriterion

Criterion = Literal["question", "contribution", "literature", "comparison", "sampling", "feasibility",
                    "novelty", "significance", "validation"]
Explanation = Annotated[str, Field(min_length=24, max_length=4000)]


def failed_criteria(review: dict) -> list[str]:
    return [name for name in ("question", "contribution", "literature", "comparison", "sampling", "feasibility")
            if review[name]["passed"] is False] + [name for name in ("novelty", "significance", "validation")
            if (review.get("publication_readiness") or {}).get(name, {}).get("passed") is False]


class RepairRequirement(Record):
    criterion: Criterion
    required_change: Explanation

    @field_validator("required_change", "actual_change", "reason", check_fields=False)
    @classmethod
    def meaningful_explanation(cls, value: str) -> str:
        if len(value.strip()) < 24:
            raise ValueError("Repair reasoning must contain substantive text")
        return value.strip()


class PdfHint(Record):
    doi: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=500)


class StudyRemediation(Record):
    action: Literal["retrieve_literature", "revise_design", "infeasible"]
    queries: list[Annotated[str, Field(min_length=8, max_length=500)]] = Field(max_length=4)
    pdfCandidates: list[PdfHint] = Field(max_length=2)
    reason: str = Field(min_length=24, max_length=2000)
    actions: list[RepairRequirement] = Field(min_length=1, max_length=9)

    @model_validator(mode="after")
    def consistent_actions(self):
        if len({item.criterion for item in self.actions}) != len(self.actions):
            raise ValueError("Every failed criterion needs one distinct repair requirement")
        if len(set(self.queries)) != len(self.queries) or any(not value.strip().isprintable() for value in self.queries):
            raise ValueError("Literature queries must be distinct printable text")
        if (self.action == "retrieve_literature") != bool(self.queries):
            raise ValueError("Only a literature retrieval action may include queries")
        if self.action != "retrieve_literature" and self.pdfCandidates:
            raise ValueError("Design changes cannot reserve PDF retrieval")
        return self


class CriterionRepair(RepairRequirement):
    actual_change: Explanation
    changed_fields: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(max_length=20)
    evidence_sources: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=12)
    unresolved: list[Annotated[str, Field(min_length=8, max_length=2000)]] = Field(max_length=8)

    @model_validator(mode="after")
    def distinct_references(self):
        for items in (self.changed_fields, self.evidence_sources, self.unresolved):
            if len(set(items)) != len(items):
                raise ValueError("Repair references and unresolved requirements must be distinct")
        if not self.changed_fields and not self.evidence_sources and not self.unresolved:
            raise ValueError("A repair must identify an actual change, retained evidence or unresolved requirement")
        return self


class StudyRepair(Record):
    changes: list[CriterionRepair] = Field(min_length=1, max_length=9)


class StudyRecoveryReview(Record):
    design_defect: QualityCriterion
    retrieval_cannot_repair: QualityCriterion
    allow_successor: bool
    reason: Explanation

    @model_validator(mode="after")
    def consistent_permission(self):
        if self.allow_successor != (self.design_defect.passed and self.retrieval_cannot_repair.passed):
            raise ValueError("Successor preparation requires both independently assessed recovery criteria")
        return self

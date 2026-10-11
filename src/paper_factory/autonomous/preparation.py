"""Provisional research questions and comparisons, never scientific approval."""

import re
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictStr, field_validator, model_validator

from ..models import Record
from .study_repair import Criterion


QuestionId = Annotated[StrictStr, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")]
Rationale = Annotated[StrictStr, Field(min_length=24, max_length=4000)]
Query = Annotated[StrictStr, Field(min_length=8, max_length=500)]


def search_terms(value: str) -> frozenset[str]:
    """The method collector searches literal Unicode words with AND semantics."""
    return frozenset(term.casefold() for term in re.findall(r"\w+", value))


class SearchRepairQuery(Record):
    question_id: QuestionId
    original_query: Query
    query: StrictStr = Field(min_length=3, max_length=160)
    rationale: StrictStr = Field(min_length=24, max_length=2000)

    @field_validator("original_query", "query", "rationale")
    @classmethod
    def printable(cls, value, info):
        value = value.strip()
        minimum = {"original_query": 8, "query": 3, "rationale": 24}[info.field_name]
        if len(value) < minimum or any((ord(char) < 32 and not (info.field_name == "rationale" and char in "\n\t")) or
                                       ord(char) == 127 for char in value):
            raise ValueError("Search repair requires substantive printable literal fields")
        if info.field_name == "query" and not 2 <= len(search_terms(value)) <= 5:
            raise ValueError("Search repair permits two to five distinct literal keyword terms")
        return value


class RedesignSearchRepairPlan(Record):
    action: Literal["refine_queries", "hold"]
    reason: StrictStr = Field(min_length=24, max_length=2000)
    queries: list[SearchRepairQuery] = Field(max_length=2)

    @field_validator("reason")
    @classmethod
    def substantive(cls, value):
        value = value.strip()
        if len(value) < 24 or any(ord(char) < 32 and char not in "\n\t" or ord(char) == 127 for char in value):
            raise ValueError("A search repair or hold needs a substantive printable reason")
        return value

    @model_validator(mode="after")
    def coherent(self):
        if (self.action == "refine_queries") != bool(self.queries):
            raise ValueError("A refinement needs queries; a hold must have none")
        if len({search_terms(item.query) for item in self.queries}) != len(self.queries):
            raise ValueError("Case, punctuation and word permutations cannot create another search")
        return self


class ResearchQuestion(Record):
    id: QuestionId
    question: StrictStr = Field(min_length=12, max_length=2000)
    known_basis: Rationale
    possible_contribution: Rationale
    importance: Rationale
    validation_route: Rationale
    literature_queries: list[Query] = Field(min_length=1, max_length=4)

    @field_validator("question", "known_basis", "possible_contribution", "importance", "validation_route")
    @classmethod
    def substantive(cls, value: str, info):
        value = value.strip()
        minimum = 12 if info.field_name == "question" else 24
        if len(value) < minimum or any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("Provisional research questions require substantive printable reasoning")
        return value

    @field_validator("literature_queries")
    @classmethod
    def distinct_queries(cls, values):
        values = [value.strip() for value in values]
        if (len(set(values)) != len(values) or any(not 8 <= len(value) <= 500 or
                any(ord(char) < 32 or ord(char) == 127 for char in value) for value in values)):
            raise ValueError("Research question queries must be distinct and printable")
        return values


class ResearchQuestions(Record):
    candidates: list[ResearchQuestion] = Field(min_length=2, max_length=3)

    @model_validator(mode="after")
    def distinct_candidates(self):
        if (len({candidate.id for candidate in self.candidates}) != len(self.candidates) or
                len({candidate.question.casefold() for candidate in self.candidates}) != len(self.candidates)):
            raise ValueError("Compare distinct research questions with distinct identifiers")
        if len(self.queries()) > 8:
            raise ValueError("The combined preliminary literature pool permits at most eight queries")
        return self

    def queries(self) -> list[str]:
        return list(dict.fromkeys(query for candidate in self.candidates for query in candidate.literature_queries))


class RedesignQuestionReframing(Record):
    """One new question design from the changed pool, preserving every old hold."""

    action: Literal["propose", "hold"]
    reason: Rationale
    candidates: list[ResearchQuestion] = Field(max_length=3)

    @field_validator("reason")
    @classmethod
    def substantive_reason(cls, value):
        value = value.strip()
        if len(value) < 24 or any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("Question reframing needs substantive printable reasoning")
        return value

    @model_validator(mode="after")
    def coherent(self):
        if self.action == "hold":
            if self.candidates:
                raise ValueError("A reframing hold cannot propose candidates")
        else:
            ResearchQuestions(candidates=self.candidates)
        return self


class ResearchQuestionComparison(Record):
    id: QuestionId
    known_result: Rationale
    proposed_difference: Rationale
    importance: Rationale
    validation_feasibility: Rationale
    evidence_sources: list[Annotated[StrictStr, Field(min_length=1, max_length=200)]] = Field(max_length=6)
    unresolved: list[Annotated[StrictStr, Field(min_length=8, max_length=2000)]] = Field(max_length=12)
    recommended: StrictBool

    @field_validator("known_result", "proposed_difference", "importance", "validation_feasibility")
    @classmethod
    def substantive(cls, value):
        value = value.strip()
        if len(value) < 24 or any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("Question comparisons require substantive printable reasoning")
        return value

    @field_validator("evidence_sources", "unresolved")
    @classmethod
    def distinct_items(cls, values, info):
        minimum = 8 if info.field_name == "unresolved" else 1
        values = [value.strip() for value in values]
        if len(set(values)) != len(values) or any(len(value) < minimum or
                any(ord(char) < 32 or ord(char) == 127 for char in value) for value in values):
            raise ValueError("Comparison references and unresolved items must be distinct and printable")
        return values


class ResearchQuestionSelection(Record):
    comparisons: list[ResearchQuestionComparison] = Field(min_length=2, max_length=3)
    selected_id: QuestionId | None
    reason: Rationale

    @field_validator("reason")
    @classmethod
    def substantive(cls, value):
        value = value.strip()
        if len(value) < 24 or any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("A provisional selection or hold requires substantive reasoning")
        return value

    @model_validator(mode="after")
    def consistent_selection(self):
        if len({item.id for item in self.comparisons}) != len(self.comparisons):
            raise ValueError("Each research question needs one distinct comparison")
        recommended = [item.id for item in self.comparisons if item.recommended]
        if recommended != ([] if self.selected_id is None else [self.selected_id]):
            raise ValueError("The selected question must exactly match the sole recommendation, or none")
        return self


class PriorProposalDifference(Record):
    artifact_id: Annotated[StrictStr, Field(min_length=1, max_length=200, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")]
    scientific_difference: Annotated[StrictStr, Field(min_length=24, max_length=2000)]

    @field_validator("scientific_difference")
    @classmethod
    def substantive_difference(cls, value):
        value = value.strip()
        if len(value) < 24 or any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("A route needs substantive reasoning about its scientific difference")
        return value


class CriterionRouteRepair(Record):
    criterion: Criterion
    required_change: Rationale
    proposed_change: Annotated[StrictStr, Field(min_length=24, max_length=2000)]

    @field_validator("required_change", "proposed_change")
    @classmethod
    def substantive_change(cls, value, info):
        if len(value.strip()) < 24 or any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("Each rejected criterion needs its literal requirement and substantive proposed repair")
        # The controller must compare the exact retained requirement, not a normalized paraphrase.
        return value if info.field_name == "required_change" else value.strip()


class RedesignQuestionComparison(ResearchQuestionComparison):
    prior_proposals: list[PriorProposalDifference] = Field(min_length=1, max_length=9)
    criterion_repairs: list[CriterionRouteRepair] = Field(min_length=1, max_length=9)
    generation_blockers: list[Annotated[StrictStr, Field(min_length=8, max_length=2000)]] = Field(max_length=12)

    @field_validator("generation_blockers")
    @classmethod
    def distinct_blockers(cls, values):
        values = [value.strip() for value in values]
        if len(set(values)) != len(values) or any(len(value) < 8 or
                any(ord(char) < 32 or ord(char) == 127 for char in value) for value in values):
            raise ValueError("Unmet candidate-generation prerequisites must be distinct and printable")
        return values

    @model_validator(mode="after")
    def distinct_context_items(self):
        if len({item.artifact_id for item in self.prior_proposals}) != len(self.prior_proposals):
            raise ValueError("Compare every retained protocol at most once for each research route")
        if len({item.criterion for item in self.criterion_repairs}) != len(self.criterion_repairs):
            raise ValueError("Address every retained failed criterion at most once for each research route")
        if self.recommended and self.generation_blockers:
            raise ValueError("An unmet prerequisite cannot support recommending candidate generation")
        return self


class RedesignQuestionSelection(ResearchQuestionSelection):
    """A provisional route decision; unresolved science remains for fresh study gates."""

    comparisons: list[RedesignQuestionComparison] = Field(min_length=2, max_length=3)


class PriorQuestionDifference(Record):
    question_id: QuestionId
    scientific_difference: Rationale

    @field_validator("scientific_difference")
    @classmethod
    def substantive_difference(cls, value):
        value = value.strip()
        if len(value) < 24 or any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("A new route needs substantive printable differences from each old question")
        return value


class ReframedQuestionComparison(RedesignQuestionComparison):
    prior_questions: list[PriorQuestionDifference] = Field(min_length=2, max_length=3)

    @model_validator(mode="after")
    def distinct_old_questions(self):
        if len({item.question_id for item in self.prior_questions}) != len(self.prior_questions):
            raise ValueError("Compare every retained old question exactly once")
        return self


class ReframedQuestionSelection(RedesignQuestionSelection):
    comparisons: list[ReframedQuestionComparison] = Field(min_length=2, max_length=3)


def validate_redesign_question_selection(
        questions: ResearchQuestions, selection: RedesignQuestionSelection,
        prior_protocol_ids: list[str], required_changes: dict[str, str],
        primary_source_ids: set[str]) -> None:
    """Check exact frozen context coverage, never novelty or scientific correctness."""
    if not prior_protocol_ids or len(set(prior_protocol_ids)) != len(prior_protocol_ids):
        raise ValueError("The retained protocol comparison must identify distinct complete protocols")
    if not required_changes:
        raise ValueError("A redesign route must address the retained failed-criterion requirements")
    if {item.id for item in selection.comparisons} != {item.id for item in questions.candidates}:
        raise ValueError("Independently compare every frozen research route exactly once")
    for item in selection.comparisons:
        if {prior.artifact_id for prior in item.prior_proposals} != set(prior_protocol_ids):
            raise ValueError("Every route must compare all exact retained parent and ancestor protocols")
        if {repair.criterion: repair.required_change for repair in item.criterion_repairs} != required_changes:
            raise ValueError("Every route must address all exact retained failed-criterion requirements")
        if set(item.evidence_sources) - primary_source_ids:
            raise ValueError("Route comparisons may cite only current verified primary-body sources")
        if item.id == selection.selected_id and (not item.evidence_sources or item.generation_blockers):
            raise ValueError("Candidate generation needs retained primary evidence and no unmet generation prerequisite")

"""Research questions, acquired-method synthesis and a content brief for writing.

These records describe actual research work, not a score or publication gate.
Controllers authenticate source quotations before passing their witness records
here. This module only connects those exact witnesses and completed products.
"""

from copy import deepcopy
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictStr, field_validator, model_validator

from ..models import Record
from .repository_paper import LiteratureEvidence

Id = Annotated[StrictStr, Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")]
Text = Annotated[StrictStr, Field(min_length=12, max_length=4000)]
Query = Annotated[StrictStr, Field(min_length=8, max_length=500)]


def _unique(values, label):
    if len(set(values)) != len(values):
        raise ValueError(label + " must be distinct")


def _query_key(value):
    return " ".join(value.casefold().split())


class EvidenceNeed(Record):
    kind: Literal["closest_method", "source_inspection", "comparative_analysis", "implementation_evidence", "external_data"]
    target: StrictStr = Field(min_length=1, max_length=4000)
    purpose: Text


class ResearchCandidate(Record):
    id: Id
    question: Text
    reader_decision: Text
    source_evidence_ids: list[StrictStr] = Field(min_length=1, max_length=12)
    known_approach: Text
    proposed_addition: Text
    falsifier: Text
    method_route: Literal["source_comparison", "finite_protocol"]
    literature_queries: list[Query] = Field(min_length=1, max_length=2)
    evidence_needs: list[EvidenceNeed] = Field(min_length=1, max_length=8)

    @field_validator("literature_queries")
    @classmethod
    def printable_queries(cls, values):
        values = [value.strip() for value in values]
        if any(len(value) < 8 or not value.isprintable() for value in values):
            raise ValueError("Research queries require substantive printable terms")
        _unique([_query_key(value) for value in values], "Candidate literature queries")
        return values

    @model_validator(mode="after")
    def distinct_witnesses(self):
        _unique(self.source_evidence_ids, "Candidate source evidence")
        return self


class ResearchAgenda(Record):
    candidates: list[ResearchCandidate] = Field(min_length=2, max_length=3)
    provisional_selected_id: Id
    reason: Text

    @model_validator(mode="after")
    def distinct_candidates(self):
        _unique([item.id for item in self.candidates], "Research candidate identifiers")
        _unique([_query_key(item.question) for item in self.candidates], "Research questions")
        if self.provisional_selected_id not in {item.id for item in self.candidates}:
            raise ValueError("The provisional question must name a supplied candidate")
        if len(self.queries()) > 4:
            raise ValueError("The bounded research agenda permits at most four distinct searches")
        return self

    def queries(self):
        result, seen = [], set()
        for candidate in self.candidates:
            for query in candidate.literature_queries:
                key = _query_key(query)
                if key not in seen:
                    result.append(query)
                    seen.add(key)
        return result


class CandidateDecision(Record):
    question_id: Id
    decision: Literal["selected", "deferred", "not_supported"]
    reason: Text


class ClosestMethod(Record):
    id: Id
    evidence: list[LiteratureEvidence] = Field(min_length=1, max_length=4)
    already_provides: Text
    same_conditions: Text
    difference: Text
    decision_change: Text


class EvidenceGap(Record):
    attainable: StrictBool
    needed_evidence: Text
    reason: Text


class ResearchSynthesis(Record):
    selected_question_id: Id | None
    candidate_decisions: list[CandidateDecision] = Field(min_length=2, max_length=3)
    closest_methods: list[ClosestMethod] = Field(max_length=6)
    finding_ids: list[Id] = Field(max_length=24)
    product_ids: list[Id] = Field(max_length=3)
    evidence_gaps: list[EvidenceGap] = Field(max_length=12)
    strengthening_needed: StrictBool
    followup_queries: list[Query] = Field(max_length=2)

    @field_validator("followup_queries")
    @classmethod
    def printable_queries(cls, values):
        values = [value.strip() for value in values]
        if any(len(value) < 8 or not value.isprintable() for value in values):
            raise ValueError("Follow-up queries require substantive printable terms")
        _unique([_query_key(value) for value in values], "Follow-up queries")
        return values

    @model_validator(mode="after")
    def coherent(self):
        _unique([item.question_id for item in self.candidate_decisions], "Candidate decisions")
        selected = [item.question_id for item in self.candidate_decisions if item.decision == "selected"]
        if selected != ([] if self.selected_question_id is None else [self.selected_question_id]):
            raise ValueError("The selected question must match the sole actual candidate decision")
        if self.selected_question_id is not None and (not self.finding_ids or not self.product_ids):
            raise ValueError("A selected research question must deliver completed findings and work products to the writer")
        for values, label in (([item.id for item in self.closest_methods], "Closest methods"),
                              (self.finding_ids, "Completed findings"), (self.product_ids, "Completed products")):
            _unique(values, label)
        if self.followup_queries and not self.strengthening_needed:
            raise ValueError("A follow-up search requires an explicit strengthening need")
        if self.strengthening_needed and not any(item.attainable for item in self.evidence_gaps):
            raise ValueError("Constructive strengthening must identify attainable missing evidence")
        return self


def validate_research_agenda(agenda, source_evidence_ids):
    """Ground every proposed question in already authenticated repository IDs."""
    agenda = ResearchAgenda.model_validate(agenda)
    known = set(source_evidence_ids)
    if any(not set(item.source_evidence_ids).issubset(known) for item in agenda.candidates):
        raise ValueError("Every research candidate requires actual inspected source witnesses")
    return agenda


def research_design_report(agenda, synthesis, analysis):
    """Build the writer's actual question/method/result brief without scoring it.

    ``analysis`` contains authenticated ``source_evidence``, ``document_evidence``,
    completed ``findings`` records (id, statement, evidence_ids), and the existing
    ``work_products`` object. No recursively discovered or prose-invented ID can
    stand in for a completed finding or product.
    """
    sources = analysis.get("source_evidence", [])
    source_ids = [item["id"] for item in sources]
    _unique(source_ids, "Authenticated source witnesses")
    agenda = validate_research_agenda(agenda, source_ids)
    synthesis = ResearchSynthesis.model_validate(synthesis)
    candidates = {item.id: item for item in agenda.candidates}
    if {item.question_id for item in synthesis.candidate_decisions} != set(candidates):
        raise ValueError("Synthesis must explain the decision for every original research candidate")
    documents = [LiteratureEvidence.model_validate(item).model_dump(mode="json")
                 for field in ("document_evidence", "literature_evidence") for item in analysis.get(field, [])]
    witnesses = {item["source_id"] for item in documents} | set(source_ids)
    document_keys = {(item["source_id"], item["text_sha256"], item["quote"]) for item in documents}
    methods = []
    for method in synthesis.closest_methods:
        if any((item.source_id, item.text_sha256, item.quote) not in document_keys for item in method.evidence):
            raise ValueError("Closest-method comparisons require exact authenticated document witnesses")
        methods.append(method.model_dump(mode="json"))
    findings = analysis.get("findings", [])
    if not isinstance(findings, list) or any(not isinstance(item, dict) or
            not isinstance(item.get("id"), str) or not isinstance(item.get("statement", item.get("claim")), str) or
            len(item.get("statement", item.get("claim", "")).strip()) < 12 or not isinstance(item.get("evidence_ids"), list) or
            not item["evidence_ids"] for item in findings):
        raise ValueError("Completed findings require explicit actual IDs, statements and supporting witnesses")
    _unique([item["id"] for item in findings], "Actual completed findings")
    finding_map = {item["id"]: item for item in findings}
    products = analysis.get("work_products", {}).get("products", [])
    if not isinstance(products, list) or any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in products):
        raise ValueError("Completed work products require their explicit actual product IDs")
    _unique([item["id"] for item in products], "Actual completed product identifiers")
    product_map = {item["id"]: item for item in products}
    if not set(synthesis.finding_ids).issubset(finding_map) or not set(synthesis.product_ids).issubset(product_map):
        raise ValueError("Synthesis may use only completed findings and actual work products")
    # Native computed IDs are explicit, independently checked result witnesses;
    # arbitrary model prose or another finding ID cannot manufacture support.
    witnesses.update(analysis.get("computed_evidence_ids", []))
    for identifier in synthesis.finding_ids:
        if not set(finding_map[identifier]["evidence_ids"]).issubset(witnesses):
            raise ValueError("A completed finding requires authenticated source, document or native result support")
    chosen = candidates.get(synthesis.selected_question_id)
    brief = {"selected_question": chosen.model_dump(mode="json") if chosen else None,
        "candidate_decisions": [item.model_dump(mode="json") for item in synthesis.candidate_decisions],
        "closest_methods": methods,
        "completed_findings": [deepcopy(finding_map[key]) for key in synthesis.finding_ids],
        "completed_work_products": [deepcopy(product_map[key]) for key in synthesis.product_ids],
        "evidence_gaps": [item.model_dump(mode="json") for item in synthesis.evidence_gaps],
        "strengthening_needed": synthesis.strengthening_needed,
        "followup_queries": list(synthesis.followup_queries),
        "scope": "Completed research basis for manuscript content. A proposed addition may be disproved or already known; neither selection nor this report proves novelty, effectiveness, nine-point quality or acceptance."}
    return {"agenda": agenda.model_dump(mode="json"), "synthesis": synthesis.model_dump(mode="json"),
        "writer_brief": brief}

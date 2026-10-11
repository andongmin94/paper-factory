"""Bounded submission targets and evidence-linked manuscript conclusions.

Model venue suggestions are pending research data, never verified journal rules.
"""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, model_validator

from ..models import Record

Mode = Literal["formal", "empirical", "finite_enumeration"]
Explanation = Annotated[StrictStr, Field(min_length=24, max_length=4000)]
Reference = Annotated[StrictStr, Field(min_length=1, max_length=200)]
Sha256 = Annotated[StrictStr, Field(pattern=r"^[a-f0-9]{64}$")]


class SubmissionPageConfirmation(Record):
    number: StrictInt = Field(ge=1, le=100)
    image_sha256: Sha256
    text_sha256: Sha256


class SubmissionConfirmation(Record):
    selected_venue: StrictStr = Field(min_length=3, max_length=300)
    requirements_artifact_id: Reference
    requirements_sha256: Sha256
    manuscript_sha256: Sha256
    pdf_sha256: Sha256
    package_sha256: Sha256
    canonical_sha256: Sha256
    author_sha256: Sha256
    pages: list[SubmissionPageConfirmation] = Field(min_length=1, max_length=100)
    official_source_confirmed: StrictBool
    venue_requirements_confirmed: StrictBool
    visual_pages_confirmed: StrictBool
    author_accuracy_confirmed: StrictBool
    authorship_rights_confirmed: StrictBool
    declarations_confirmed: StrictBool
    reason: Explanation

    @model_validator(mode="after")
    def affirmative_checks(self):
        if not all(getattr(self, key) for key in ("official_source_confirmed", "venue_requirements_confirmed",
                   "visual_pages_confirmed", "author_accuracy_confirmed", "authorship_rights_confirmed", "declarations_confirmed")):
            raise ValueError("Every submission check requires an explicit affirmative human confirmation")
        if len({page.number for page in self.pages}) != len(self.pages):
            raise ValueError("Every reviewed PDF page must be listed exactly once")
        return self


class ClaimObligation(Record):
    id: StrictStr = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    claim: Explanation
    validation_mode: Mode
    required_evidence: Explanation
    importance: Explanation


class VenueSuggestion(Record):
    name: StrictStr = Field(min_length=3, max_length=300)
    rationale: Explanation
    official_requirements_status: Literal["pending"]
    official_requirements: list[StrictStr] = Field(max_length=0)


class SubmissionContract(Record):
    article_type: Mode
    language: StrictStr = Field(min_length=2, max_length=100)
    target_audience: Explanation
    core_claim: Explanation
    claim_obligations: list[ClaimObligation] = Field(min_length=1, max_length=12)
    venue_candidates: list[VenueSuggestion] = Field(min_length=1, max_length=3)
    selected_venue: None

    @model_validator(mode="after")
    def distinct_target(self):
        if len({item.id for item in self.claim_obligations}) != len(self.claim_obligations):
            raise ValueError("Claim obligations need distinct identifiers")
        if len({item.name.casefold() for item in self.venue_candidates}) != len(self.venue_candidates):
            raise ValueError("Venue suggestions must be distinct")
        if any(item.validation_mode != self.article_type for item in self.claim_obligations):
            raise ValueError("Submission obligations must preserve the selected evidence mode")
        return self


class ManuscriptClaim(Record):
    mode: Mode
    claim: Explanation
    scope: Explanation
    outcome: Literal["positive", "negative", "null", "mixed"]
    scope_justification: Explanation
    analysis_keys: list[Reference] = Field(max_length=32)
    fixture_labels: list[Reference] = Field(max_length=12)
    proof_section: StrictStr | None = Field(min_length=3, max_length=100)
    proof_quote: StrictStr | None = Field(min_length=80, max_length=12000)

    @model_validator(mode="after")
    def distinct_support(self):
        if any(len(set(items)) != len(items) for items in (self.analysis_keys, self.fixture_labels)):
            raise ValueError("Observed claim references must be distinct")
        if (self.proof_section is None) != (self.proof_quote is None):
            raise ValueError("Observed proof support requires a section and literal passage")
        if self.mode == "formal" and (self.proof_section is None or self.analysis_keys):
            raise ValueError("Formal observed claims require proof support rather than measured inference")
        if self.mode != "formal" and (not self.analysis_keys or self.proof_section is not None):
            raise ValueError("Measured observed claims require retained analysis support")
        return self


class ManuscriptCriterionRepair(Record):
    criterion: Literal["contribution", "literature", "interpretation", "presentation"]
    required_change: Explanation
    actual_change: Explanation
    changed_sections: list[Reference] = Field(max_length=14)
    evidence_sources: list[Reference] = Field(max_length=12)
    unresolved: list[Annotated[StrictStr, Field(min_length=8, max_length=2000)]] = Field(max_length=12)

    @model_validator(mode="after")
    def distinct_changes(self):
        for items in (self.changed_sections, self.evidence_sources, self.unresolved):
            if len(set(items)) != len(items):
                raise ValueError("Manuscript repair references must be distinct")
        if not self.changed_sections and not self.evidence_sources and not self.unresolved:
            raise ValueError("A manuscript repair needs actual changes, current evidence or an unresolved issue")
        return self


class ManuscriptRepair(Record):
    changes: list[ManuscriptCriterionRepair] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def distinct_criteria(self):
        if len({item.criterion for item in self.changes}) != len(self.changes):
            raise ValueError("Manuscript repairs need one change record per failed criterion")
        return self


class ValidationUnit(Record):
    seed: StrictInt
    unit_id: Reference
    stratum: Reference


class OracleSource(Record):
    source_id: Reference
    text_sha256: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    quote: StrictStr = Field(min_length=80, max_length=1500)


class ValidationContract(Record):
    mode: Mode
    declared_units: list[ValidationUnit] = Field(min_length=6, max_length=10000)
    finite_domain_label: Reference | None
    uncertainty: Literal["none", "seed_cluster_bootstrap"]
    independent_sampling: StrictBool
    sampling_basis: Explanation
    bootstrap_seed: StrictInt
    bootstrap_replicates: StrictInt = Field(ge=200, le=2000)
    confidence_level: float = Field(ge=.8, le=.99)
    oracle_sources: list[OracleSource] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def coherent_validation(self):
        keys = [(item.seed, item.unit_id) for item in self.declared_units]
        if len(set(keys)) != len(keys):
            raise ValueError("Validation declarations need unique seed and unit identities")
        refs = [(item.source_id, item.text_sha256, item.quote) for item in self.oracle_sources]
        if len(set(refs)) != len(refs):
            raise ValueError("Oracle references must be distinct")
        if self.uncertainty != "none" and (self.mode != "empirical" or not self.independent_sampling):
            raise ValueError("Uncertainty requires independently sampled empirical seed clusters")
        if (self.mode == "finite_enumeration") != (self.finite_domain_label is not None):
            raise ValueError("Only bounded enumeration requires an exact domain fixture")
        return self

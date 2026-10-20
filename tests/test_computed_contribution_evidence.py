"""Controller-supplied checked result IDs never become model-authorized evidence."""

import copy
import hashlib

import pytest
from pydantic import ValidationError

from paper_factory.autonomous.manuscript_improvement import (
    FocusedManuscripts,
    ManuscriptRevision,
    canonical_focused_revision,
    canonical_quality_revision,
)


COMPUTED_IDS = frozenset({
    "overwrite_occupied_request", "pending_request_preserved", "authority_at_dispatch",
    "continuous_inspection_demand", "single_write_workflow",
})
BODY = "The synthetic analysis retains its exact scientific prose and explicitly bounded claims. " * 2
PRIMARY_TEXT = "A retained primary document binds an operation intent to its eventual effect."


def revision(*, computed=False, venue="ieee-software"):
    return {
        "venue_id": venue, "action_id": "bounded-research-write",
        "manuscript": {
            "title": "Synthetic source-bound manuscript",
            "sections": [{"heading": heading, "text": BODY}
                         for heading in ("Abstract", "Method", "Findings", "Limitations")],
            "source_evidence": [{"id": "source-one", "path": "src/example.ts", "sha256": "a" * 64,
                                 "quote": "An exact synthetic source quotation.", "interpretation": BODY}],
            "literature_evidence": [], "document_evidence": [], "revision": None,
        },
        "contributions": [{"claim": BODY, "baseline": BODY, "additional_decision_value": BODY,
                           "evidence_ids": sorted(COMPUTED_IDS) if computed else ["source-one"],
                           "counterexample_or_failure_condition": BODY, "applicability_limit": BODY}],
        "actual_work": [BODY], "evidence_limits": [],
    }


def test_plain_source_bound_contribution_remains_valid_without_context():
    value = revision()
    assert ManuscriptRevision.model_validate(value).model_dump(mode="json") == value


def test_computed_contributions_require_controller_context_and_do_not_leak():
    value = revision(computed=True)
    with pytest.raises(ValidationError, match="actual retained manuscript evidence"):
        ManuscriptRevision.model_validate(value)
    accepted = ManuscriptRevision.model_validate(value, context={"computed_evidence_ids": COMPUTED_IDS})
    assert accepted.model_dump(mode="json") == value
    with pytest.raises(ValidationError, match="actual retained manuscript evidence"):
        ManuscriptRevision.model_validate(value)


def test_nested_both_venue_validation_propagates_only_the_trusted_context():
    value = {"revisions": [revision(computed=True), revision(computed=True, venue="ieee-security-privacy")]}
    with pytest.raises(ValidationError, match="actual retained manuscript evidence"):
        FocusedManuscripts.model_validate(value)
    parsed = FocusedManuscripts.model_validate(value, context={"computed_evidence_ids": COMPUTED_IDS})
    assert parsed.model_dump(mode="json") == value
    forged = copy.deepcopy(value)
    forged["revisions"][1]["contributions"][0]["evidence_ids"].append("fabricated_native_result")
    with pytest.raises(ValidationError, match="actual retained manuscript evidence"):
        FocusedManuscripts.model_validate(forged, context={"computed_evidence_ids": COMPUTED_IDS})


def test_model_payload_cannot_supply_its_own_computed_registry():
    value = revision(computed=True)
    value["computed_evidence_ids"] = sorted(COMPUTED_IDS)
    with pytest.raises(ValidationError):
        ManuscriptRevision.model_validate(value)
    assert "computed_evidence_ids" not in ManuscriptRevision.model_json_schema()["properties"]


@pytest.mark.parametrize("untrusted", ["source-one", ["source-one"], {"source-one": True}, {1}, {""}])
def test_malformed_computed_registry_is_not_coerced_into_authority(untrusted):
    with pytest.raises(ValidationError, match="trusted native set"):
        ManuscriptRevision.model_validate(revision(), context={"computed_evidence_ids": untrusted})


def test_bibliography_normalization_keeps_context_and_exact_scientific_content():
    value = revision(computed=True)
    value["manuscript"]["sections"].append({"heading": "References", "text": BODY})
    original = copy.deepcopy(value)
    with pytest.raises(ValidationError, match="actual retained manuscript evidence"):
        canonical_quality_revision(value)
    parsed, proof = canonical_quality_revision(value, computed_evidence_ids=COMPUTED_IDS)
    expected = copy.deepcopy(value)
    expected["manuscript"]["sections"].pop()
    assert parsed.model_dump(mode="json") == expected
    assert proof["kind"] == "controller_owned_bibliography"
    assert value == original


def test_primary_kind_normalization_keeps_context_and_exact_witnesses():
    value = revision(computed=True)
    witness = {"source_id": "focused-document-1", "text_sha256": hashlib.sha256(PRIMARY_TEXT.encode()).hexdigest(),
               "quote": PRIMARY_TEXT, "interpretation": BODY}
    value["manuscript"]["literature_evidence"] = [witness]
    value["manuscript"]["sections"][1]["text"] += " {{citation:focused-document-1}}"
    value["manuscript"]["sections"].append({"heading": "References", "text": BODY})
    original = copy.deepcopy(value)
    cards = {"focused-document-1": {"status": "retained", "complete_body": True,
                                    "text_sha256": witness["text_sha256"]}}
    texts = {"focused-document-1": PRIMARY_TEXT}
    parsed, proof = canonical_focused_revision(value, cards, texts, computed_evidence_ids=COMPUTED_IDS)
    expected = copy.deepcopy(value)
    expected["manuscript"]["sections"].pop()
    expected["manuscript"]["sections"][1]["text"] = expected["manuscript"]["sections"][1]["text"].replace(
        "{{citation:focused-document-1}}", "{{document:focused-document-1}}")
    expected["manuscript"]["literature_evidence"] = []
    expected["manuscript"]["document_evidence"] = [witness]
    assert parsed.model_dump(mode="json") == expected
    assert proof["primary_citation_kind"]["exact_token_replacements"] == {"focused-document-1": 1}
    assert value == original
    with pytest.raises(ValidationError, match="actual retained manuscript evidence"):
        canonical_focused_revision(value, cards, texts)
    for field, damage in (("text_sha256", "0" * 64), ("quote", "An invented quotation absent from the retained source.")):
        invalid = copy.deepcopy(value)
        invalid["manuscript"]["literature_evidence"][0][field] = damage
        with pytest.raises(ValueError, match="exact retained ID"):
            canonical_focused_revision(invalid, cards, texts, computed_evidence_ids=COMPUTED_IDS)


def test_square_citation_delimiters_are_exact_reversible_changes_not_id_aliases():
    value = revision(computed=True)
    witness = {"source_id": "focused-document-1", "text_sha256": hashlib.sha256(PRIMARY_TEXT.encode()).hexdigest(),
               "quote": PRIMARY_TEXT, "interpretation": BODY}
    value["manuscript"]["document_evidence"] = [witness]
    suffix = " [source:source-one] [document:focused-document-1] {{source:source-one}} [source:source-one]"
    value["manuscript"]["sections"][1]["text"] += suffix
    original = copy.deepcopy(value)
    parsed, proof = canonical_quality_revision(value, computed_evidence_ids=COMPUTED_IDS)
    expected = copy.deepcopy(value)
    expected["manuscript"]["sections"][1]["text"] = (BODY + suffix).replace(
        "[source:source-one]", "{{source:source-one}}").replace(
        "[document:focused-document-1]", "{{document:focused-document-1}}")
    assert parsed.model_dump(mode="json") == expected
    delimiters = proof["citation_delimiters"]
    assert delimiters["replacement_count"] == 3
    assert delimiters["restored_sections_sha256"] == delimiters["original_sections_sha256"]
    restored = [dict(section) for section in parsed.model_dump(mode="json")["manuscript"]["sections"]]
    for section in delimiters["sections"]:
        for change in reversed(section["tokens"]):
            text = restored[section["section_index"]]["text"]
            offset = change["normalized_offset"]
            assert text[offset:offset + len(change["canonical"])] == change["canonical"]
            restored[section["section_index"]]["text"] = text[:offset] + change["original"] + text[offset + len(change["canonical"]):]
    assert restored == original["manuscript"]["sections"]
    assert value == original


@pytest.mark.parametrize("token", ["[source:unknown]", "[document:unknown]", "[citation:unknown]",
                                 "[source:authority_at_dispatch]"])
def test_square_citation_tokens_cannot_use_unknown_or_computed_ids(token):
    value = revision(computed=True)
    value["manuscript"]["sections"][1]["text"] += " " + token
    with pytest.raises(ValueError, match="actual retained manuscript witness ID"):
        canonical_quality_revision(value, computed_evidence_ids=COMPUTED_IDS)


def test_square_primary_citation_moves_kind_only_after_exact_source_verification():
    value = revision(computed=True)
    witness = {"source_id": "focused-document-1", "text_sha256": hashlib.sha256(PRIMARY_TEXT.encode()).hexdigest(),
               "quote": PRIMARY_TEXT, "interpretation": BODY}
    value["manuscript"]["literature_evidence"] = [witness]
    value["manuscript"]["sections"][1]["text"] += " [citation:focused-document-1]"
    cards = {"focused-document-1": {"status": "retained", "complete_body": True,
                                    "text_sha256": witness["text_sha256"]}}
    parsed, proof = canonical_focused_revision(value, cards, {"focused-document-1": PRIMARY_TEXT},
                                              computed_evidence_ids=COMPUTED_IDS)
    assert parsed.manuscript.sections[1].text == BODY + " {{document:focused-document-1}}"
    assert proof["bibliography"]["citation_delimiters"]["replacement_count"] == 1
    assert proof["primary_citation_kind"]["exact_token_replacements"] == {"focused-document-1": 1}

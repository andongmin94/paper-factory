"""Strict metadata parsing without manual study or publication state."""
import pytest
from paper_factory.literature import _doi, _metadata


def work():
    return {"status": "ok", "message": {"DOI": "10.1234/REPRODUCIBLE", "title": [" Actual bibliographic title "],
        "author": [{"given": "Ada", "family": "Lovelace"}, {"name": "Research Group"}],
        "published": {"date-parts": [[2024, 4, 1]]}}}


def test_metadata_preserves_provider_facts_and_normalizes_only_doi_and_whitespace():
    assert _metadata(work()) == ("10.1234/reproducible", "Actual bibliographic title", ["Ada Lovelace", "Research Group"], 2024)


@pytest.mark.parametrize("doi", ["https://attacker.invalid/a", "not-a-doi", "10.1234/../bad", "10.1234/a b", "10.1234/a\x00b"])
def test_invalid_doi_identifiers_are_rejected(doi):
    with pytest.raises(ValueError):
        _doi(doi)


@pytest.mark.parametrize("change", ["status", "message", "DOI", "title", "author", "author_name"])
def test_incomplete_provider_metadata_cannot_be_used_as_bibliographic_evidence(change):
    data = work()
    if change == "status": data["status"] = "error"
    elif change == "message": data["message"] = []
    elif change == "author_name": data["message"]["author"] = [{"given": None, "family": "Name"}]
    else: data["message"].pop(change)
    with pytest.raises(ValueError):
        _metadata(data)


def test_boolean_year_is_not_a_publication_year():
    data = work()
    data["message"]["published"]["date-parts"] = [[True]]
    assert _metadata(data)[3] is None

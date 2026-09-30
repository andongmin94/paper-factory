import hashlib
import json

import httpx
import pytest

from paper_factory.venues import Venue, discover, validate_venue
from paper_factory.workspace import Workspace


def source(**changes):
    return {"id": "https://openalex.org/S123", "display_name": "Example Journal", "type": "journal",
            "issn": ["1234-5678"], "host_organization_name": "Example Publisher",
            "homepage_url": "https://example.org/journal", "relevance_score": 14.2, **changes}


def test_dynamic_directory_search_preserves_provider_evidence(tmp_path):
    ws = Workspace.create(tmp_path)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"results": [source()]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        venues = discover(ws, "software engineering", 2, client=client)
    assert requests[0].url.params["search"] == "software engineering"
    assert requests[0].url.params["filter"] == "type:journal"
    assert requests[0].url.params["per_page"] == "2"
    assert len(venues) == 1
    venue = venues[0]
    assert venue.name == "Example Journal" and venue.indexing == "unknown"
    assert "not an assessment of manuscript fit" in venue.relevance_explanation
    assert hashlib.sha256(ws.path(venue.raw_path).read_bytes()).hexdigest() == venue.raw_sha256
    assert ws.get("venue", venue.id, Venue) == venue
    assert not validate_venue(ws, venue)


@pytest.mark.parametrize("changes", [
    {"id": "https://evil.example/S123"}, {"type": "repository"}, {"display_name": ""},
    {"issn": ["made-up"]}, {"homepage_url": "file:///etc/passwd"},
    {"homepage_url": "https://user:password@example.org"}, {"relevance_score": float("nan")},
])
def test_malformed_candidates_are_never_persisted(tmp_path, changes):
    ws = Workspace.create(tmp_path)
    payload = json.dumps({"results": [source(**changes)]})
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=payload))) as client:
        with pytest.raises(ValueError):
            discover(ws, "research", client=client)
    assert not ws.list("venue", Venue)


@pytest.mark.parametrize("query,limit", [("", 1), ("a" * 501, 1), ("research", 0), ("research", True)])
def test_invalid_search_cannot_contact_network(tmp_path, query, limit):
    ws = Workspace.create(tmp_path)
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("unexpected request"))) as client:
        with pytest.raises(ValueError):
            discover(ws, query, limit, client=client)


def test_no_results_and_service_error_are_distinct(tmp_path):
    ws = Workspace.create(tmp_path)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": []}))) as client:
        assert discover(ws, "no matching journal", client=client) == []
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(429))) as client:
        with pytest.raises(ValueError, match="OpenAlex request failed"):
            discover(ws, "research", client=client)


def test_metadata_edit_cannot_replace_official_policy_authority(tmp_path):
    ws = Workspace.create(tmp_path)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": [source()]}))) as client:
        venue = discover(ws, "research", client=client)[0]
    venue.official_url = "https://attacker.example/"
    ws.save("venue", venue)
    assert "does not match" in validate_venue(ws, venue)[0]


def test_duplicate_or_overlong_results_fail_atomically(tmp_path):
    ws = Workspace.create(tmp_path)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": [source(), source()]}))) as client:
        with pytest.raises(ValueError, match="duplicate"):
            discover(ws, "research", 2, client=client)
        with pytest.raises(ValueError, match="exceed"):
            discover(ws, "research", 1, client=client)
    assert not ws.list("venue", Venue)

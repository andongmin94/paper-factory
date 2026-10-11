"""A query repair may spend only the remaining, identity-filtered reading budget."""
import hashlib
import json

import httpx
import pytest

from paper_factory.autonomous import literature
from test_autonomous_literature import METHOD_TEXT, clock, method_entry, method_feed, mocked, record
from test_openalex_discovery import URL as REPOSITORY_URL, location, work
from test_public_pdf_hints import DOI, PDF, TEXT, TITLE, URL as AUTHOR_URL, LISTING


pytestmark = pytest.mark.usefixtures("clock")
PROVIDER_URL = "https://joss.theoj.org/papers/10.21105/joss.00001.pdf"


@pytest.mark.parametrize("value", [True, False, -1, 3, 1.0, "1", None])
def test_invalid_remaining_reservation_is_refused_before_files_or_http(tmp_path, monkeypatch, value):
    monkeypatch.setattr(literature.httpx, "Client", lambda **kwargs: pytest.fail("Invalid bound reached HTTP"))
    root = tmp_path / "not-created"
    with pytest.raises(ValueError, match="PDF reservation"):
        literature.collect([DOI], root, pdf_reservation_limit=value)
    assert not root.exists()


@pytest.mark.parametrize("value", ["doi:10.1234/test", {}, [1], ["10.1234/test"],
    ["doi:10.1234/TEST"], ["doi:https://doi.org/10.1234/test"], ["arxiv:2301.00001v0"],
    ["arxiv:2301.00001v2 "], ["doi:10.1234/test"] * 501])
def test_invalid_exclusions_are_refused_before_files_or_http(tmp_path, monkeypatch, value):
    monkeypatch.setattr(literature.httpx, "Client", lambda **kwargs: pytest.fail("Invalid exclusions reached HTTP"))
    root = tmp_path / "not-created"
    with pytest.raises(ValueError):
        literature.collect([DOI], root, excluded_identities=value)
    assert not root.exists()


@pytest.mark.parametrize("remaining", [0, 1, 2])
def test_provider_and_author_failures_share_the_remaining_reservations(tmp_path, monkeypatch, remaining):
    def respond(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json=record(links=[{"URL": PROVIDER_URL, "content-type": "application/pdf"}]))
        if request.url.host == "api.openalex.org":
            return httpx.Response(404, json={"error": "No synthetic repository copy"})
        if str(request.url) == literature.AUTHOR_PUBLICATIONS:
            return httpx.Response(200, content=LISTING, headers={"content-type": "text/html"})
        assert str(request.url) in {PROVIDER_URL, AUTHOR_URL}, "No third PDF route may run"
        return httpx.Response(403, content=b"Refused complete synthetic response", headers={"content-type": "text/plain"})

    requests = mocked(monkeypatch, respond, openalex_discovery=True)
    result = literature.collect([DOI], tmp_path, limit=1, pdf_reservation_limit=remaining)
    reservations = result["pdf_reservations"]
    assert len(reservations) == remaining
    assert [item["route"] for item in reservations] == ["provider_pdf", "author_copy"][:remaining]
    assert [item["url"] for item in reservations] == [PROVIDER_URL, AUTHOR_URL][:remaining]
    assert all(item["identity"] == "doi:" + DOI and item["pdf_attempted"] is True for item in reservations)
    assert sum(str(request.url) in {PROVIDER_URL, AUTHOR_URL} for request in requests) == remaining
    assert result["pdf_reservation_limit"] == remaining and result["sources"][0]["scope"] == "metadata_only"
    if remaining == 2:
        attempt, = [item for item in result["pdf_hint_attempts"] if item.get("pdf_attempted")]
        assert attempt["pdf_attempted"] is True and attempt["status"] == "rejected"
        assert (tmp_path / attempt["raw_path"]).read_bytes() == b"Refused complete synthetic response"


def test_repository_discovery_does_not_spend_more_than_the_remaining_one(tmp_path, monkeypatch):
    second = REPOSITORY_URL.replace("research-paper", "second-paper")
    def respond(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json=record())
        if request.url.host == literature.AUTHOR_PDF_HOST:
            return httpx.Response(200, content=b"<html><ul></ul></html>", headers={"content-type": "text/html"})
        if request.url.host == "api.openalex.org":
            return httpx.Response(200, json=work(location(), location(second)))
        assert str(request.url) == REPOSITORY_URL
        return httpx.Response(403, content=b"Synthetic repository refusal")

    requests = mocked(monkeypatch, respond, openalex_discovery=True)
    result = literature.collect([DOI], tmp_path, limit=1, pdf_reservation_limit=1)
    reservation, = result["pdf_reservations"]
    assert reservation["route"] == "repository_copy" and reservation["url"] == REPOSITORY_URL
    assert sum(request.url.host == "zenodo.org" for request in requests) == 1
    attempt, = [item for item in result["pdf_hint_attempts"] if item.get("pdf_attempted")]
    assert attempt["status"] == "rejected" and (tmp_path / attempt["raw_path"]).read_bytes() == b"Synthetic repository refusal"


def test_provider_reservation_exists_before_dns_and_cancelled_get(tmp_path, monkeypatch):
    budgets = []
    original_budget = literature._CollectionBudget
    def budget(*args, **kwargs):
        value = original_budget(*args, **kwargs)
        budgets.append(value)
        return value
    monkeypatch.setattr(literature, "_CollectionBudget", budget)
    requests = mocked(monkeypatch, lambda request: httpx.Response(200,
        json=record(links=[{"URL": PROVIDER_URL, "content-type": "application/pdf"}])))
    state = {"cancelled": False}
    original_dns = literature.socket.getaddrinfo
    def dns(host, *args, **kwargs):
        if host == "joss.theoj.org":
            assert budgets[0].pdf_reservations[0]["url"] == PROVIDER_URL
            state["cancelled"] = True
        return original_dns(host, *args, **kwargs)
    monkeypatch.setattr(literature.socket, "getaddrinfo", dns)
    result = literature.collect([DOI], tmp_path, limit=1, cancel=lambda: state["cancelled"], pdf_reservation_limit=1)
    assert result["cancelled"] is True and len(result["pdf_reservations"]) == 1
    assert len(requests) == 1 and result["sources"][0]["scope"] == "metadata_only"


@pytest.mark.parametrize("identity,query", [("doi:" + DOI, DOI),
    ("arxiv:2301.00001v2", "arxiv:2301.00001v2"),
    ("arxiv:2301.00001", "arxiv:2301.00001v2"),
    ("doi:10.48550/arxiv.2301.00001", "arxiv:2301.00001v2")])
def test_excluded_explicit_identity_does_not_reach_dns_or_get(tmp_path, monkeypatch, identity, query):
    requests = mocked(monkeypatch, lambda request: pytest.fail("Excluded identity reached HTTP"))
    result = literature.collect([query], tmp_path, excluded_identities=[identity], pdf_candidates=[])
    assert requests == [] and result["sources"] == [] and result["pdf_reservations"] == []
    assert result["searches"][0]["status"] == "excluded" and not result["searches"][0]["attempted"]
    assert result["candidate_rejections"][0]["reason"] == "excluded_identity"


def test_bibliographic_exclusion_preserves_original_search_without_resolving_old_doi(tmp_path, monkeypatch):
    other = "10.1234/new"
    def respond(request):
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": DOI}, {"DOI": other}]}})
        assert request.url.path == "/works/" + other
        return httpx.Response(200, json=record(other, abstract="A literal synthetic abstract."))
    requests = mocked(monkeypatch, respond)
    result = literature.collect(["synthetic short query"], tmp_path, limit=3, pdf_candidates=[], excluded_identities=["doi:" + DOI])
    assert len(requests) == 2 and len(result["sources"]) == 1 and result["sources"][0]["doi"] == other
    rejection, = result["candidate_rejections"]
    raw = (tmp_path / rejection["raw_path"]).read_bytes()
    assert rejection["identity"] == "doi:" + DOI and rejection["reason"] == "excluded_identity"
    assert hashlib.sha256(raw).hexdigest() == rejection["sha256"]
    assert json.loads(raw)["message"]["items"][0]["DOI"] == DOI


@pytest.mark.parametrize("route", ["exact_title", "method"])
def test_excluded_discovered_preprint_is_not_rechecked_or_read(tmp_path, monkeypatch, route):
    entry = method_entry(title="synthetic short query")
    def respond(request):
        if request.url.host == "export.arxiv.org":
            assert "id_list" not in request.url.params
            return httpx.Response(200, content=method_feed(entry), headers={"content-type": "application/atom+xml"})
        assert request.url.path == "/works"
        return httpx.Response(200, json={"status": "ok", "message": {"items": []}})
    requests = mocked(monkeypatch, respond, title_discovery=route == "exact_title", method_discovery=route == "method")
    result = literature.collect(["synthetic short query"], tmp_path, limit=3, pdf_candidates=[],
                                excluded_identities=["arxiv:2301.00001v2"])
    assert not result["sources"] and not result["pdf_reservations"]
    assert all(request.url.host != "arxiv.org" for request in requests)
    rejection, = result["candidate_rejections"]
    assert rejection["identity"] == "arxiv:2301.00001v2" and rejection["reason"] == "excluded_identity"
    search = next(item for item in result["searches"] if item["provider"] == "arXiv")
    assert (tmp_path / search["raw_path"]).read_bytes() == method_feed(entry)


def test_excluded_exact_title_leaves_other_bibliographic_identities_discoverable(tmp_path, monkeypatch):
    def respond(request):
        if request.url.host == "export.arxiv.org":
            assert "id_list" not in request.url.params
            return httpx.Response(200, content=method_feed(method_entry(title="synthetic short query")),
                                  headers={"content-type": "application/atom+xml"})
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": DOI}]}})
        return httpx.Response(200, json=record(abstract="A different identity's literal synthetic abstract."))
    requests = mocked(monkeypatch, respond, title_discovery=True)
    result = literature.collect(["synthetic short query"], tmp_path, limit=3, pdf_candidates=[],
                                excluded_identities=["arxiv:2301.00001v2"])
    assert len(requests) == 3 and result["sources"][0]["doi"] == DOI
    assert result["sources"][0]["scope"] == "abstract" and result["pdf_reservations"] == []
    assert result["candidate_rejections"][0]["reason"] == "excluded_identity"


def test_doi_discovered_excluded_preprint_alias_cannot_use_any_pdf_route(tmp_path, monkeypatch):
    metadata = record()
    metadata["message"]["type"] = "journal-article"
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json=metadata))
    def discover(client, source, root, **kwargs):
        source["arxiv_id"] = "2301.00001v2"
        return "https://arxiv.org/pdf/2301.00001v2"
    monkeypatch.setattr(literature, "_arxiv_pdf", discover)
    result = literature.collect([DOI], tmp_path, limit=1, excluded_identities=["arxiv:2301.00001v2"])
    assert len(requests) == 1 and result["sources"][0]["scope"] == "metadata_only"
    assert result["pdf_reservations"] == [] and result["pdf_hint_attempts"] == []
    assert result["candidate_rejections"][0]["stage"] == "reading"


def test_new_versioned_identity_can_retain_a_body_with_one_remaining_reservation(tmp_path, monkeypatch):
    feed = method_feed(method_entry())
    def respond(request):
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, content=feed, headers={"content-type": "application/atom+xml"})
        assert str(request.url) == "https://arxiv.org/pdf/2301.00001v2"
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    requests = mocked(monkeypatch, respond)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: METHOD_TEXT)
    result = literature.collect(["arxiv:2301.00001v2"], tmp_path, limit=3, pdf_candidates=[],
                                pdf_reservation_limit=1, excluded_identities=["arxiv:2301.00002v1"])
    source, = result["sources"]
    reservation, = result["pdf_reservations"]
    assert source["scope"] == "full_text" and source["arxiv_id"] == reservation["arxiv_id"] == "2301.00001v2"
    assert reservation["identity"] == "arxiv:2301.00001v2" and len(requests) == 2
    for path_key, hash_key in (("metadata_path", "metadata_sha256"), ("raw_path", "sha256"), ("text_path", "text_sha256")):
        assert hashlib.sha256((tmp_path / source[path_key]).read_bytes()).hexdigest() == source[hash_key]
    assert source["body_range"] == literature.full_text_body_range(METHOD_TEXT)


@pytest.mark.parametrize("change,reason", [("authors", "missing_authors"), ("long_title", "title_too_long"),
    ("stylesheet", "stylesheet_title"), ("identity", "identity_mismatch")])
def test_metadata_rejection_diagnostics_preserve_the_exact_failed_record(tmp_path, monkeypatch, change, reason):
    metadata = record()
    if change == "authors":
        metadata["message"].pop("author")
    elif change == "long_title":
        metadata["message"]["title"] = ["A" * 501]
    elif change == "stylesheet":
        metadata["message"]["title"] = ["div{font-size:12pt;line-height:14pt;} Title"]
    else:
        metadata["message"]["DOI"] = "10.1234/other"
    def respond(request):
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": DOI}]}})
        return httpx.Response(200, json=metadata)
    requests = mocked(monkeypatch, respond)
    result = literature.collect(["synthetic short query"], tmp_path, limit=3, pdf_candidates=[])
    assert len(requests) == 2 and result["sources"] == [] and result["pdf_reservations"] == []
    rejection, = result["candidate_rejections"]
    assert rejection["identity"] == "doi:" + DOI and rejection["reason"] == reason
    raw = (tmp_path / rejection["metadata_path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == rejection["metadata_sha256"] and json.loads(raw) == metadata


def test_repair_bounds_leave_only_two_method_searches_and_three_source_slots(tmp_path, monkeypatch):
    queries = ["synthetic method " + str(index) for index in range(4)]
    def respond(request):
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, content=method_feed(), headers={"content-type": "application/atom+xml"})
        if request.url.path == "/works":
            assert request.url.params["rows"] == "3"
            return httpx.Response(200, json={"status": "ok", "message": {"items": [
                {"DOI": "10.1234/item-" + str(index)} for index in range(3)]}})
        return httpx.Response(200, json=record(request.url.path.removeprefix("/works/"), abstract="Literal synthetic evidence."))
    requests = mocked(monkeypatch, respond, method_discovery=True)
    result = literature.collect(queries, tmp_path, limit=3, pdf_candidates=[], pdf_reservation_limit=1)
    assert sum(request.url.host == "export.arxiv.org" for request in requests) == 2
    assert len(result["sources"]) == 3 and result["pdf_reservations"] == []
    assert len([search for search in result["searches"] if search.get("lookup") == "method"]) == 2
    assert all(any(search["query"] == query and search["status"] == "succeeded"
                   for search in result["searches"]) for query in queries)

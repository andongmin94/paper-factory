"""Public repository discovery remains distinct from literal PDF verification."""
import json

import httpx
import pytest

from paper_factory.autonomous import literature
from test_autonomous_literature import clock, mocked, record
from test_public_pdf_hints import DOI, PDF, TEXT, TITLE, URL as AUTHOR_URL, assert_retained


URL = "https://zenodo.org/records/1234567/files/research-paper.pdf"
SOURCE = {"doi": DOI, "title": TITLE, "authors": ["Ada Lovelace"], "year": 2024}


def location(url=URL, **fields):
    return {"is_oa": True, "source": {"type": "repository"}, "pdf_url": url,
            "version": "acceptedVersion", "license": "cc-by", **fields}


def work(*locations, **fields):
    return {"doi": "https://doi.org/" + DOI, "title": TITLE, "publication_year": 2024,
            "locations": list(locations or [location()]), **fields}


def collection(monkeypatch, root, *, oa=None, oa_status=200, oa_type="application/json", text=TEXT,
               listing=b"<html><ul></ul></html>", pdf_handler=None, cancel=None, candidates=None):
    def respond(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json=record())
        if request.url.host == literature.AUTHOR_PDF_HOST:
            if str(request.url) == literature.AUTHOR_PUBLICATIONS:
                return httpx.Response(200, content=listing, headers={"content-type": "text/html"})
            return httpx.Response(403, content=b"Author copy refused", headers={"content-type": "text/plain"})
        if request.url.host == "api.openalex.org":
            assert request.url.path == "/works/doi:" + DOI and not request.url.query
            return httpx.Response(oa_status, content=oa if isinstance(oa, bytes) else json.dumps(oa or work()).encode(),
                                  headers={"content-type": oa_type})
        assert str(request.url) in {item["pdf_url"].split("?")[0] for item in (oa or work())["locations"]}
        if pdf_handler:
            return pdf_handler(request)
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    requests = mocked(monkeypatch, respond, openalex_discovery=True)
    monkeypatch.setattr(literature, "_arxiv_pdf", lambda *args, **kwargs: None)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: text)
    result = literature.collect([DOI], root, limit=1, cancel=cancel, pdf_candidates=candidates)
    return result, requests


def repository_attempts(result):
    return [attempt for attempt in result["pdf_hint_attempts"] if attempt.get("route") == "openalex_repository"]


def test_exact_location_is_pure_and_version_remains_a_claim(monkeypatch):
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *a, **k: pytest.fail("Discovery cannot perform DNS"))
    monkeypatch.setattr(literature.httpx, "Client", lambda **k: pytest.fail("Discovery cannot perform HTTP"))
    raw = json.dumps(work(location(URL + "?download=1"))).encode()
    assert literature.openalex_pdf_locations(raw, SOURCE) == [
        {"provider": "OpenAlex", "lookup_url": literature._openalex_url(DOI), "location_index": 0,
         "pdf_url": URL + "?download=1", "claimed_version": "acceptedVersion", "license": "cc-by", "url": URL}]


@pytest.mark.parametrize("fields", [
    {"doi": "https://doi.org/10.1234/other"}, {"title": TITLE + " and another contribution"},
    {"publication_year": 2025}, {"publication_year": True}, {"locations": {}},
])
def test_fuzzy_or_different_work_metadata_never_yields_a_copy(fields):
    with pytest.raises(ValueError):
        literature.openalex_pdf_locations(json.dumps(work(**fields)).encode(), SOURCE)


@pytest.mark.parametrize("url", [
    "http://zenodo.org/records/123/files/paper.pdf",
    "https://user:secret@zenodo.org/records/123/files/paper.pdf", "https://zenodo.org:444/records/123/files/paper.pdf",
    "https://127.0.0.1/records/123/files/paper.pdf", "https://zenodo.org/api/records/123",
    "https://zenodo.org/records/123/files/../paper.pdf", "https://zenodo.org/records/123/files/%2e%2e.pdf",
    URL + "?token=secret", URL + "?download=1&token=secret", URL + "#fragment", URL + "\x7f",
])
def test_discovery_rejects_unsafe_urls_before_any_request(url):
    assert literature.openalex_pdf_locations(json.dumps(work(location(url))).encode(), SOURCE) == []
    with pytest.raises(ValueError):
        literature._repository_pdf_url(url)


def test_nonpublic_nonrepository_duplicates_and_extra_locations_are_bounded():
    extra = URL.replace("research-paper", "second-paper")
    third = URL.replace("research-paper", "third-paper")
    found = literature.openalex_pdf_locations(json.dumps(work(
        location(is_oa=False), location(source={"type": "journal"}), location(), location(URL + "?download=1"),
        location(extra), location(third))).encode(), SOURCE)
    assert [item["url"] for item in found] == [URL, extra]
    assert [item["location_index"] for item in found] == [1, 4]


def test_complete_route_retains_crossref_originals_and_rederivable_pdf_proof(tmp_path, monkeypatch, clock):
    result, requests = collection(monkeypatch, tmp_path, oa=work(location(URL + "?download=1")))
    assert [request.url.host for request in requests] == ["api.crossref.org", "api.openalex.org", "zenodo.org"]
    source, = result["sources"]
    attempt, = repository_attempts(result)
    assert source["scope"] == "full_text" and source["copy_type"] == "repository_copy"
    assert source["publication_version"] == "unknown" and "arxiv_id" not in source
    assert source["url"] == URL and source["discovery_url"] == literature._openalex_url(DOI)
    assert attempt["pdf_attempted"] is True and attempt["status"] == "verified"
    proof = json.loads(assert_retained(tmp_path, source, "identity_path", "identity_sha256"))
    assert proof["route"] == "openalex_repository" and proof["redirects"] == []
    assert proof["identity"] == literature.public_pdf_identity(TEXT, source)
    assert proof["discovery"]["claimed_version"] == "acceptedVersion"
    raw = assert_retained(tmp_path, source, "discovery_path", "discovery_sha256")
    resolution, = literature.openalex_pdf_locations(raw, source)
    assert all(proof["discovery"][key] == value for key, value in resolution.items())
    assert_retained(tmp_path, source, content=PDF)
    assert_retained(tmp_path, source, "metadata_path", "metadata_sha256", json.dumps(record(), separators=(",", ":"), ensure_ascii=False).encode())
    assert_retained(tmp_path, source, "text_path", "text_sha256", TEXT.encode())
    assert source["body_range"] == literature.full_text_body_range(TEXT)
    assert sum(item.get("pdf_attempted") is True for item in result["pdf_hint_attempts"]) == 1


@pytest.mark.parametrize("conflicting", [False, True])
def test_exact_openalex_discovery_can_read_other_public_hosts_only_with_matching_body(tmp_path, monkeypatch, clock, conflicting):
    url = "https://papers.example.edu/public/verified-paper.pdf"
    text = TEXT.replace(TITLE, TITLE + " Conflicting subtitle", 1) if conflicting else TEXT
    result, requests = collection(monkeypatch, tmp_path, oa=work(location(url)), text=text)
    assert sum(str(request.url) == url for request in requests) == 1
    source, = result["sources"]
    attempt, = repository_attempts(result)
    if conflicting:
        assert source["scope"] == "metadata_only" and attempt["status"] == "rejected"
        assert "identity_path" not in source
    else:
        assert source["scope"] == "full_text" and source["publication_version"] == "unknown"
        assert attempt["identity"] == literature.public_pdf_identity(TEXT, source)
    assert_retained(tmp_path, attempt, content=PDF)


def test_prior_failed_pdf_url_is_not_requested_or_reserved_again(tmp_path, monkeypatch, clock):
    fresh = "https://papers.example.edu/public/verified-paper.pdf"
    calls = []

    def respond(request):
        calls.append(str(request.url))
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json=record())
        if request.url.host == "api.openalex.org":
            return httpx.Response(200, json=work(location(URL), location(fresh)))
        assert str(request.url) == fresh
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})

    mocked(monkeypatch, respond, openalex_discovery=True)
    monkeypatch.setattr(literature, "_arxiv_pdf", lambda *args, **kwargs: None)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT)
    result = literature.collect([DOI], tmp_path, limit=1,
        excluded_urls=[URL, literature.AUTHOR_PUBLICATIONS], pdf_reservation_limit=1)
    assert URL not in calls and literature.AUTHOR_PUBLICATIONS not in calls
    assert len(result["pdf_reservations"]) == 1 and result["pdf_reservations"][0]["url"] == fresh
    assert result["sources"][0]["scope"] == "full_text"


def test_reserved_doi_can_recover_exact_repository_copy_without_a_generic_search(tmp_path, monkeypatch, clock):
    result, requests = collection(monkeypatch, tmp_path, candidates=[{"doi": DOI, "title": TITLE}])
    assert [request.url.host for request in requests] == ["api.crossref.org", "www.cs.cmu.edu", "api.openalex.org", "zenodo.org"]
    assert all(request.url.path != "/works" and request.url.host != "export.arxiv.org" for request in requests)
    source, = result["sources"]
    attempt, = repository_attempts(result)
    assert source["scope"] == "full_text" and source["copy_type"] == "repository_copy"
    assert attempt["candidate"] == {"doi": DOI, "title": TITLE} and attempt["status"] == "verified"
    proof = json.loads(assert_retained(tmp_path, source, "identity_path", "identity_sha256"))
    assert proof["identity"] == literature.public_pdf_identity(TEXT, source)
    assert_retained(tmp_path, source, content=PDF)
    assert_retained(tmp_path, source, "text_path", "text_sha256", TEXT.encode())


def test_conflicting_reserved_title_cannot_start_repository_discovery(tmp_path, monkeypatch, clock):
    result, requests = collection(monkeypatch, tmp_path, candidates=[{"doi": DOI, "title": TITLE + " conflicting subtitle"}])
    assert [request.url.host for request in requests] == ["api.crossref.org"]
    assert result["sources"][0]["scope"] == "metadata_only" and repository_attempts(result) == []


@pytest.mark.parametrize("url", ["https://hal.science/hal-01234567/document", "https://hal.science/hal-01234567v3/document"])
def test_hal_public_main_file_uses_same_exact_metadata_pdf_identity_and_retained_proof(tmp_path, monkeypatch, clock, url):
    result, requests = collection(monkeypatch, tmp_path, oa=work(location(url)), candidates=[{"doi": DOI, "title": TITLE}])
    assert requests[-1].url.host == "hal.science" and str(requests[-1].url) == url
    source, = result["sources"]
    attempt, = repository_attempts(result)
    assert source["url"] == url and source["scope"] == "full_text" and source["publication_version"] == "unknown"
    raw = assert_retained(tmp_path, source, "discovery_path", "discovery_sha256")
    resolution, = literature.openalex_pdf_locations(raw, source)
    assert all(attempt["discovery"][key] == value for key, value in resolution.items())
    assert_retained(tmp_path, source, content=PDF)
    assert json.loads(assert_retained(tmp_path, source, "identity_path", "identity_sha256"))["identity"] == literature.public_pdf_identity(TEXT, source)


@pytest.mark.parametrize("url", ["http://hal.science/hal-01234567/document",
    "https://user:secret@hal.science/hal-01234567/document", "https://hal.science:444/hal-01234567/document",
    "https://hal.science/hal-01234567/document?download=1", "https://hal.science/hal-01234567/document?token=secret",
    "https://hal.science/hal-01234567/document#page=1", "https://hal.science/hal-01234567/../document",
    "https://hal.science/hal-01234567/%2e%2e/document", "https://hal.science/hal-01234567/document\x7f",
    "https://hal.science/hal-01234567v0/document", "https://hal.science/hal-01234567", "https://hal.science/api/search"])
def test_hal_discovery_refuses_noncanonical_private_or_nonfile_urls_before_dns(monkeypatch, url):
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *args, **kwargs: pytest.fail("Invalid endpoint cannot reach DNS"))
    assert literature.openalex_pdf_locations(json.dumps(work(location(url))).encode(), SOURCE) == []
    with pytest.raises(ValueError):
        literature._checked_url(url, pdf=True, repository_pdf=True)


def test_reserved_author_and_repository_failures_still_share_two_pdf_reservations(tmp_path, monkeypatch, clock):
    listing = ('<html><li>"' + TITLE + '" <a href="' + AUTHOR_URL + '">pdf</a></li></html>').encode()
    second = "https://hal.science/hal-01234567/document"
    result, requests = collection(monkeypatch, tmp_path, listing=listing, oa=work(location(), location(second)),
        candidates=[{"doi": DOI, "title": TITLE}], pdf_handler=lambda request: httpx.Response(403, content=b"Repository refusal"))
    assert sum(attempt.get("pdf_attempted") is True for attempt in result["pdf_hint_attempts"]) == 2
    assert all(str(request.url) != second for request in requests)
    assert result["sources"][0]["scope"] == "metadata_only"


@pytest.mark.parametrize("status,content_type,raw", [
    (404, "application/json", b'{"error":"No work"}'),
    (200, "text/html", b"<html>Not discovery JSON</html>"),
    (200, "application/json", b'{"doi":"https://doi.org/10.1234/other"}'),
])
def test_unavailable_or_substituted_discovery_retains_response_without_pdf(tmp_path, monkeypatch, clock, status, content_type, raw):
    result, requests = collection(monkeypatch, tmp_path, oa=raw, oa_status=status, oa_type=content_type)
    assert len(requests) == 3 and result["sources"][0]["scope"] == "metadata_only"
    attempt, = repository_attempts(result)
    assert attempt["status"] == "rejected" and "pdf_attempted" not in attempt
    assert_retained(tmp_path, attempt["discovery"], content=raw)
    assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")


@pytest.mark.parametrize("text", [TEXT.replace(TITLE, TITLE + " conflicting subtitle"),
    TEXT.replace("Ada Lovelace", "Different Author"), TEXT.replace(DOI, "10.1234/other")])
def test_discovery_metadata_cannot_promote_conflicting_pdf_identity(tmp_path, monkeypatch, clock, text):
    result, requests = collection(monkeypatch, tmp_path, text=text)
    source, = result["sources"]
    attempt, = repository_attempts(result)
    assert len(requests) == 4 and source["scope"] == "metadata_only" and source["excerpts"] == []
    assert "publication_version" not in source and attempt["status"] == "rejected"
    assert_retained(tmp_path, attempt, content=PDF)
    assert_retained(tmp_path, attempt, "text_path", "text_sha256", text.encode())
    assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")


def test_repository_redirect_is_retained_and_target_is_never_requested(tmp_path, monkeypatch, clock):
    raw = b"Complete public repository redirect refusal"
    result, requests = collection(monkeypatch, tmp_path, pdf_handler=lambda request:
        httpx.Response(302, content=raw, headers={"location": "https://127.0.0.1/private.pdf"}))
    assert len(requests) == 4 and result["sources"][0]["scope"] == "metadata_only"
    attempt, = repository_attempts(result)
    transition, = attempt["redirects"]
    assert transition["next_url"] is None and transition["error"] == "ValueError"
    assert_retained(tmp_path, transition, content=raw)
    assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")


def test_author_and_repository_failures_share_two_pdf_reservations(tmp_path, monkeypatch, clock):
    listing = ('<html><li>"' + TITLE + '" <a href="' + AUTHOR_URL + '">pdf</a></li></html>').encode()
    extra = URL.replace("research-paper", "second-paper")
    result, requests = collection(monkeypatch, tmp_path, listing=listing, oa=work(location(), location(extra)),
        pdf_handler=lambda request: httpx.Response(403, content=b"Repository refusal"),
        candidates=[{"doi": DOI, "title": TITLE}])
    attempted = [attempt for attempt in result["pdf_hint_attempts"] if attempt.get("pdf_attempted") is True]
    assert len(attempted) == 2 and all(attempt["status"] == "rejected" for attempt in attempted)
    assert sum(request.url.host == "zenodo.org" for request in requests) == 1
    assert all(str(request.url) != extra for request in requests)
    assert result["sources"][0]["scope"] == "metadata_only"


def test_two_repository_failures_never_request_third_location(tmp_path, monkeypatch, clock):
    urls = [URL.replace("research-paper", "paper-" + str(index)) for index in range(3)]
    result, requests = collection(monkeypatch, tmp_path, oa=work(*(location(url) for url in urls)),
        pdf_handler=lambda request: httpx.Response(403, content=b"Complete unavailable PDF"))
    assert [str(request.url) for request in requests if request.url.host == "zenodo.org"] == urls[:2]
    assert len(repository_attempts(result)) == 2
    for attempt in repository_attempts(result):
        assert_retained(tmp_path, attempt, content=b"Complete unavailable PDF")
        assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")


def test_cancellation_after_reservation_keeps_proof_without_requesting_pdf(tmp_path, monkeypatch, clock):
    state = {"cancelled": False}
    checked = literature._checked_url
    def check(url, **kwargs):
        result = checked(url, **kwargs)
        if kwargs.get("repository_pdf"):
            state["cancelled"] = True
        return result
    monkeypatch.setattr(literature, "_checked_url", check)
    result, requests = collection(monkeypatch, tmp_path, cancel=lambda: state["cancelled"])
    assert result["cancelled"] is True and len(requests) == 2
    attempt, = repository_attempts(result)
    assert attempt["status"] == "interrupted" and attempt["pdf_attempted"] is True and "raw_path" not in attempt
    assert_retained(tmp_path, attempt["discovery"])
    assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")


@pytest.mark.parametrize("url,pdf", [
    ("https://api.openalex.org/works", False),
    (literature._openalex_url(DOI) + "?api_key=secret", False),
    (URL + "?token=secret", True),
])
def test_provider_boundaries_refuse_invalid_requests_before_dns(monkeypatch, url, pdf):
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *args, **kwargs: pytest.fail("No DNS for invalid endpoint"))
    with pytest.raises(ValueError):
        literature._checked_url(url, pdf=pdf, repository_pdf=pdf)


def test_public_repository_private_dns_is_refused_even_with_proxy(monkeypatch):
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))])
    monkeypatch.setattr(literature, "getproxies_environment", lambda: {"https": "https://proxy.example"})
    with pytest.raises(ValueError, match="non-public"):
        literature._checked_url(URL, pdf=True, repository_pdf=True)


def test_shared_deadline_preserves_complete_pdf_without_dispatching_extractor(tmp_path, monkeypatch, clock):
    save = literature._save
    def retain(root, prefix, suffix, raw):
        result = save(root, prefix, suffix, raw)
        if prefix.endswith("-openalex"):
            clock.value = 75
        return result
    monkeypatch.setattr(literature, "_save", retain)
    result, requests = collection(monkeypatch, tmp_path)
    assert result["timed_out"] is True and len(requests) == 3
    assert result["sources"][0]["scope"] == "metadata_only"
    attempt, = repository_attempts(result)
    assert attempt["status"] == "interrupted" and "text_path" not in attempt
    assert_retained(tmp_path, attempt, content=PDF)
    assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")


def test_noncomplete_pdf_response_retains_bytes_without_scientific_upgrade(tmp_path, monkeypatch, clock):
    result, requests = collection(monkeypatch, tmp_path, pdf_handler=lambda request:
        httpx.Response(206, content=PDF, headers={"content-type": "application/pdf"}))
    assert len(requests) == 4 and result["sources"][0]["scope"] == "metadata_only"
    attempt, = repository_attempts(result)
    assert attempt["http_status"] == 206 and attempt["status"] == "rejected" and "text_path" not in attempt
    assert_retained(tmp_path, attempt, content=PDF)


def test_discovery_size_bound_never_retains_or_requests_oversize_payload(tmp_path, monkeypatch, clock):
    raw = b"x" * (literature.MAX_JSON_BYTES + 1)
    result, requests = collection(monkeypatch, tmp_path, oa=raw)
    assert len(requests) == 3 and result["sources"][0]["scope"] == "metadata_only"
    attempt, = repository_attempts(result)
    assert attempt["status"] == "rejected" and "raw_path" not in attempt["discovery"]
    assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")

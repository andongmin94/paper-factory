"""Exact official-list discovery, retained redirects and one-request boundaries."""
import json

import httpx
import pytest

from paper_factory.autonomous import literature
from test_autonomous_literature import clock, mocked, record
from test_public_pdf_hints import DOI, HINT, LISTING, PDF, TITLE, URL, assert_retained, collect_hint


def listing_leaf(title=TITLE, href=URL, *, tail=""):
    return ('<li>Ada Lovelace, "' + title + '", <a href="' + href + '">local pdf</a>' + tail + '</li>').encode()


def test_discovery_exact_leaf_index_title_and_literal_path_with_no_io(monkeypatch):
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *a, **k: pytest.fail("Pure discovery cannot use DNS"))
    monkeypatch.setattr(literature.httpx, "Client", lambda **k: pytest.fail("Pure discovery cannot use HTTP"))
    href = "/~natprog/papers/CaseSensitive-Paper.pdf"
    raw = b'<base href="https://evil.test/"><ul><li>"Parent"<ul>' + listing_leaf(href=href) + b'</ul></li></ul>'
    found = literature.discover_author_pdf(raw, HINT)
    assert found == {"provider": "CMU publications", "listing_url": literature.AUTHOR_PUBLICATIONS,
                     "leaf_index": 1, "quoted_title": TITLE, "literal_href": href,
                     "url": "https://www.cs.cmu.edu" + href}


def test_discovery_normalizes_complete_quoted_title_but_does_not_change_literal_href():
    href = URL.replace("verified-author", "UpperCase-author")
    raw = listing_leaf(title="VERIFIED <i>record</i> title", href=href)
    found = literature.discover_author_pdf(raw, HINT)
    assert found["quoted_title"] == "VERIFIED record title"
    assert found["literal_href"] == found["url"] == href


@pytest.mark.parametrize("raw", [
    listing_leaf(title=TITLE + " with different methods"),
    listing_leaf(title="A different paper " + TITLE),
    ('<p>"' + TITLE + '" <a href="' + URL + '">pdf</a></p>').encode(),
    ('<li>' + TITLE + ' <a href="' + URL + '">pdf</a></li>').encode(),
    b'<script>' + listing_leaf() + b'</script>',
    b'<template>' + listing_leaf() + b'</template>',
    b'<style>' + listing_leaf() + b'</style>',
    listing_leaf() + listing_leaf(),
    listing_leaf(tail=' "Another publication"'),
    listing_leaf(tail='<a href="' + URL + '">duplicate pdf</a>'),
    listing_leaf(tail='<a href="https://publisher.test/another.pdf">other pdf</a>'),
    ('<li>"' + TITLE + '" <a href="https://doi.org/10.1234/test">DOI</a></li>').encode(),
])
def test_discovery_declines_similar_nonleaf_unquoted_duplicate_and_ambiguous_matches(raw):
    with pytest.raises(ValueError):
        literature.discover_author_pdf(raw, HINT)


def test_discovery_refuses_oversize_original_html():
    with pytest.raises(ValueError):
        literature.discover_author_pdf(b'x' * (literature.MAX_JSON_BYTES + 1), HINT)


@pytest.mark.parametrize("href", [
    "http://www.cs.cmu.edu/~NatProg/papers/test.pdf",
    "https://www.cs.cmu.edu.evil.test/~NatProg/papers/test.pdf",
    "https://user:secret@www.cs.cmu.edu/~NatProg/papers/test.pdf",
    "https://www.cs.cmu.edu:444/~NatProg/papers/test.pdf",
    "https://www.cs.cmu.edu/~NATPROG/papers/test.pdf",
    "https://www.cs.cmu.edu/~other/papers/test.pdf",
    "https://127.0.0.1/~NatProg/papers/test.pdf",
    URL + "?token=secret", URL + "#fragment", URL + "\n", URL + "\x7f",
    "/~NatProg/papers/../papers/test.pdf", "/~NatProg/papers/%2e%2e/test.pdf",
    "https://www.cs.cmu.edu/~NatProg/papers/../papers/test.pdf",
    "//www.cs.cmu.edu/~NatProg/papers/test.pdf", "verified-author.pdf",
])
def test_discovery_refuses_unsafe_literal_href_before_pdf_request(tmp_path, monkeypatch, href):
    raw = listing_leaf(href=href)
    with pytest.raises(ValueError):
        literature.discover_author_pdf(raw, HINT)
    result, requests = collect_hint(monkeypatch, tmp_path, listing=raw)
    assert len(requests) == 2 and result["sources"][0]["scope"] == "metadata_only"
    attempt, = result["pdf_hint_attempts"]
    assert attempt["status"] == "rejected" and "raw_path" not in attempt
    assert_retained(tmp_path, attempt["discovery"], content=raw)
    assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")


def test_server_http_location_upgrades_to_https_preserving_actual_path_case_and_all_bytes(tmp_path, monkeypatch):
    lower = URL.replace("~NatProg", "~natprog")
    location = URL.replace("https:", "http:")
    redirected = b"Complete redirect response retained separately"
    def respond(request):
        assert request.url.scheme == "https"
        if str(request.url) == lower:
            return httpx.Response(302, content=redirected, headers={"location": location, "content-type": "text/plain"})
        assert str(request.url) == URL
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    raw = listing_leaf(href=lower)
    result, requests = collect_hint(monkeypatch, tmp_path, listing=raw, handler=respond)
    source, = result["sources"]
    assert source["scope"] == "full_text" and source["url"] == URL and len(requests) == 4
    proof = json.loads(assert_retained(tmp_path, source, "identity_path", "identity_sha256"))
    assert proof["discovery"]["literal_href"] == lower and proof["discovery"]["url"] == lower
    trace, = proof["redirects"]
    assert trace["url"] == lower and trace["status"] == 302 and trace["location"] == location and trace["next_url"] == URL
    assert_retained(tmp_path, trace, content=redirected)
    assert literature.author_pdf_redirect(lower, location) == URL


@pytest.mark.parametrize("location", [
    "http://127.0.0.1/~NatProg/papers/test.pdf", "http://www.cs.cmu.edu.evil.test/~NatProg/papers/test.pdf",
    "http://www.cs.cmu.edu:80/~NatProg/papers/test.pdf", "http://user:secret@www.cs.cmu.edu/~NatProg/papers/test.pdf",
    "http://www.cs.cmu.edu/~other/papers/test.pdf", "http://www.cs.cmu.edu/~NatProg/papers/test.pdf?token=secret",
    "https://arxiv.org/pdf/1311.3903v1", "",
])
def test_refused_redirect_never_requests_target_and_keeps_trace_and_complete_bytes(tmp_path, monkeypatch, location):
    raw = b"Refused redirect complete body"
    result, requests = collect_hint(monkeypatch, tmp_path, handler=lambda request:
        httpx.Response(302, content=raw, headers={"location": location, "content-type": "text/plain"}))
    assert len(requests) == 3 and result["sources"][0]["scope"] == "metadata_only"
    attempt = result["pdf_hint_attempts"][0]
    assert attempt["status"] == "rejected"
    trace, = attempt["redirects"]
    assert trace["location"] == location and trace["next_url"] is None and trace["error"] == "ValueError"
    assert_retained(tmp_path, trace, content=raw)
    assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")


@pytest.mark.parametrize("location", [URL + "\n", "javascript:alert(1)"])
def test_malformed_location_is_refused_even_if_httpx_rejects_before_returning_response(tmp_path, monkeypatch, location):
    with pytest.raises(ValueError):
        literature.author_pdf_redirect(URL, location)
    result, requests = collect_hint(monkeypatch, tmp_path, handler=lambda request:
        httpx.Response(302, content=b"Malformed Location", headers={"location": location}))
    assert len(requests) == 3 and result["sources"][0]["scope"] == "metadata_only"
    attempt = result["pdf_hint_attempts"][0]
    assert attempt["status"] == "rejected" and attempt["error"] in {"InvalidURL", "RemoteProtocolError"}
    # HTTPX does not expose this response; do not invent a retained HTTP trace.
    assert attempt["redirects"] == [] and "raw_path" not in attempt
    assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")


def test_three_redirects_succeed_fourth_is_refused_and_retained(tmp_path, monkeypatch):
    def chain(length):
        def respond(request):
            index = 0 if str(request.url) == URL else int(request.url.path.split('/')[-1].split('.')[0])
            if index < length:
                return httpx.Response(302, content=str(index).encode(), headers={"location": str(index + 1) + ".pdf"})
            return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
        return respond
    result, requests = collect_hint(monkeypatch, tmp_path, handler=chain(3))
    assert result["sources"][0]["scope"] == "full_text" and len(requests) == 6
    assert len(result["pdf_hint_attempts"][0]["redirects"]) == 3
    result, requests = collect_hint(monkeypatch, tmp_path / "fourth", handler=chain(4))
    assert result["sources"][0]["scope"] == "metadata_only" and len(requests) == 6
    traces = result["pdf_hint_attempts"][0]["redirects"]
    assert len(traces) == 4 and traces[-1]["next_url"] is None
    for index, trace in enumerate(traces):
        assert_retained(tmp_path / "fourth", trace, content=str(index).encode())


@pytest.mark.parametrize("status", [403, 429, 302])
def test_unavailable_list_fetched_once_for_two_candidates_preserves_completed_response(tmp_path, monkeypatch, status):
    other = "10.1234/other"
    def respond(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json=record(other if request.url.path.endswith("other") else DOI))
        assert str(request.url) == literature.AUTHOR_PUBLICATIONS
        return httpx.Response(status, content=b"Complete unavailable list", headers={"location": "/~bam/other.html", "retry-after": "1", "content-type": "text/html"})
    requests = mocked(monkeypatch, respond)
    result = literature.collect([DOI, other], tmp_path, limit=2, pdf_candidates=[HINT, {"doi": other, "title": TITLE}])
    assert len(requests) == 3 and len(result["pdf_hint_attempts"]) == 2
    assert all(source["scope"] == "metadata_only" for source in result["sources"])
    assert result["pdf_listing"]["status"] == "rejected" and result["pdf_listing"]["http_status"] == status
    assert_retained(tmp_path, result["pdf_listing"], content=b"Complete unavailable list")
    for attempt in result["pdf_hint_attempts"]:
        assert attempt["status"] == "rejected" and attempt["discovery"]["sha256"] == result["pdf_listing"]["sha256"]
        assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")


def test_ambiguous_list_has_no_pdf_or_generic_fallback_and_remains_nonbody(tmp_path, monkeypatch):
    monkeypatch.setattr(literature, "_arxiv_pdf", lambda *a, **k: pytest.fail("No generic fallback"))
    result, requests = collect_hint(monkeypatch, tmp_path, listing=LISTING + LISTING)
    assert len(requests) == 2 and result["sources"][0]["scope"] == "metadata_only"
    assert result["sources"][0]["excerpts"] == []
    assert_retained(tmp_path, result["pdf_listing"], content=LISTING + LISTING)
    assert result["pdf_hint_attempts"][0]["status"] == "rejected"


def test_cancelled_listing_preserves_completed_html_and_never_requests_pdf(tmp_path, monkeypatch):
    state = {"cancelled": False}
    original_save = literature._save
    def save(root, prefix, suffix, content):
        value = original_save(root, prefix, suffix, content)
        if prefix == "author-publications":
            state["cancelled"] = True
        return value
    monkeypatch.setattr(literature, "_save", save)
    result, requests = collect_hint(monkeypatch, tmp_path, cancel=lambda: state["cancelled"])
    assert result["cancelled"] is True and len(requests) == 2
    assert result["sources"][0]["scope"] == "metadata_only"
    assert result["pdf_hint_attempts"][0]["status"] == "interrupted"
    assert_retained(tmp_path, result["pdf_listing"], content=LISTING)


def test_listing_time_budget_is_shared_with_pdf_and_does_not_dispatch_worker(tmp_path, monkeypatch, clock):
    def respond(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json=record())
        assert str(request.url) == literature.AUTHOR_PUBLICATIONS
        clock.value = 91
        return httpx.Response(200, content=LISTING, headers={"content-type": "text/html"})
    requests = mocked(monkeypatch, respond)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: pytest.fail("Worker after deadline"))
    result = literature.collect([DOI], tmp_path, limit=1, pdf_candidates=[HINT])
    assert result["timed_out"] is True and len(requests) == 2
    assert result["sources"][0]["scope"] == "metadata_only" and "raw_path" not in result["pdf_listing"]


def test_listing_bound_refuses_oversize_before_body_identity(tmp_path, monkeypatch):
    result, requests = collect_hint(monkeypatch, tmp_path, listing=b"x" * (literature.MAX_JSON_BYTES + 1))
    assert len(requests) == 2 and result["sources"][0]["scope"] == "metadata_only"
    assert "raw_path" not in result["pdf_listing"] and result["pdf_hint_attempts"][0]["status"] == "rejected"

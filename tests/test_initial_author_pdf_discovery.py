"""Fresh bibliographic collection discovers author copies without model hints."""
import json

import httpx
import pytest

from paper_factory.autonomous import literature
from test_autonomous_literature import clock, mocked, record
from test_public_pdf_hints import DOI, HINT, LISTING, PDF, TEXT, TITLE, URL, assert_retained


def work(doi=DOI, title=TITLE, **fields):
    value = record(doi)
    value["message"].update(title=[title], **fields)
    return value


def leaf(title, index):
    return ('<li>"' + title + '" <a href="' + URL.replace("verified-author", "author-" + str(index))
            + '">pdf</a></li>').encode()


def bibliographic(monkeypatch, root, works, listing, *, pdf_handler=None, extractor=None, cancel=None, candidates=None):
    def respond(request):
        if request.url.host == "api.crossref.org":
            if request.url.path == "/works":
                assert request.url.params["query.bibliographic"] == "selective recovery comparison"
                return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": doi} for doi in works]}})
            doi = request.url.path.removeprefix("/works/")
            return httpx.Response(200, json=works[doi])
        assert request.url.host == literature.AUTHOR_PDF_HOST
        if str(request.url) == literature.AUTHOR_PUBLICATIONS:
            return httpx.Response(200, content=listing, headers={"content-type": "text/html"})
        if pdf_handler:
            return pdf_handler(request)
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    requests = mocked(monkeypatch, respond)
    monkeypatch.setattr(literature, "_pdf_text", extractor or (lambda raw: TEXT))
    result = literature.collect(["selective recovery comparison"], root, limit=len(works),
                                cancel=cancel, pdf_candidates=candidates)
    return result, requests


def test_initial_bibliographic_candidate_uses_exact_metadata_and_retains_complete_proof(tmp_path, monkeypatch, clock):
    result, requests = bibliographic(monkeypatch, tmp_path, {DOI: work()}, LISTING)
    assert len(requests) == 4 and not result["warnings"]
    assert result["pdf_discovery_mode"] == "initial_metadata"
    source, = result["sources"]
    attempt, = result["pdf_hint_attempts"]
    assert attempt["candidate"] == HINT and attempt["pdf_attempted"] is True and attempt["status"] == "verified"
    assert source["queries"] == ["selective recovery comparison"]
    assert source["scope"] == "full_text" and source["copy_type"] == "author_copy"
    assert source["publication_version"] == "unknown" and "arxiv_id" not in source
    assert source["discovery_url"] == literature.AUTHOR_PUBLICATIONS
    assert_retained(tmp_path, source, content=PDF)
    assert_retained(tmp_path, source, "text_path", "text_sha256", TEXT.encode())
    assert_retained(tmp_path, source, "discovery_path", "discovery_sha256", LISTING)
    proof = json.loads(assert_retained(tmp_path, source, "identity_path", "identity_sha256"))
    assert proof["candidate"] == HINT and proof["pdf_attempted"] is True
    assert proof["identity"] == literature.author_pdf_identity(TEXT, source)
    assert literature.discover_author_pdf(LISTING, proof["candidate"]) == {key: proof["discovery"][key] for key in
        ("provider", "listing_url", "leaf_index", "quoted_title", "literal_href", "url")}
    assert source["body_range"] == literature.full_text_body_range(TEXT)
    for excerpt, location in zip(source["excerpts"], source["excerpt_ranges"]):
        assert excerpt == TEXT[location["start"]:location["end"]]


def test_unmatched_candidates_preserve_negative_proofs_without_spending_two_pdf_attempts(tmp_path, monkeypatch, clock):
    works = {f"10.1234/work-{index}": work(f"10.1234/work-{index}", f"Candidate title {index}") for index in range(5)}
    listing = b"<ul>" + b"".join(leaf(f"Candidate title {index}", index) for index in range(2, 5)) + b"</ul>"
    def respond(request):
        index = int(request.url.path.rsplit("/", 1)[-1].removeprefix("author-").removesuffix(".pdf"))
        return httpx.Response(200, content=PDF + str(index).encode(), headers={"content-type": "application/pdf"})
    result, requests = bibliographic(monkeypatch, tmp_path, works, listing, pdf_handler=respond,
        extractor=lambda raw: TEXT.replace(TITLE, f"Candidate title {int(raw[-1:])}").replace(DOI, f"10.1234/work-{int(raw[-1:])}"))
    assert sum(str(request.url) == literature.AUTHOR_PUBLICATIONS for request in requests) == 1
    pdf_requests = [request for request in requests if request.url.path.endswith(".pdf")]
    assert [request.url.path.rsplit("/", 1)[-1] for request in pdf_requests] == ["author-2.pdf", "author-3.pdf"]
    attempts = result["pdf_hint_attempts"]
    assert len(attempts) == 4 and sum(item.get("pdf_attempted") is True for item in attempts) == 2
    assert [item["status"] for item in attempts] == ["rejected", "rejected", "verified", "verified"]
    for item in attempts:
        assert_retained(tmp_path, item, "identity_path", "identity_sha256")
        assert_retained(tmp_path, item["discovery"], content=listing)
    assert result["sources"][-1]["scope"] == "metadata_only"


def test_two_failed_matched_pdfs_consume_cap_without_requesting_a_third(tmp_path, monkeypatch, clock):
    works = {f"10.1234/work-{index}": work(f"10.1234/work-{index}", f"Candidate title {index}") for index in range(3)}
    listing = b"<ul>" + b"".join(leaf(f"Candidate title {index}", index) for index in range(3)) + b"</ul>"
    def respond(request):
        first = request.url.path.endswith("author-0.pdf")
        return httpx.Response(403 if first else 200, content=b"Complete refusal" if first else PDF,
                              headers={"content-type": "text/plain" if first else "application/pdf"})
    result, requests = bibliographic(monkeypatch, tmp_path, works, listing, pdf_handler=respond)
    assert len([request for request in requests if request.url.path.endswith(".pdf")]) == 2
    first, second = result["pdf_hint_attempts"]
    assert first["pdf_attempted"] is second["pdf_attempted"] is True
    assert first["status"] == second["status"] == "rejected"
    assert_retained(tmp_path, first, content=b"Complete refusal")
    assert_retained(tmp_path, second, content=PDF)
    assert_retained(tmp_path, second, "text_path", "text_sha256", TEXT.encode())
    assert all(source["scope"] == "metadata_only" for source in result["sources"])


def test_cancellation_after_reservation_preserves_attempt_without_dispatching_pdf(tmp_path, monkeypatch, clock):
    state = {"cancelled": False}
    checked = literature._checked_url
    def check(url, **kwargs):
        value = checked(url, **kwargs)
        if kwargs.get("author_pdf"):
            state["cancelled"] = True
        return value
    monkeypatch.setattr(literature, "_checked_url", check)
    result, requests = bibliographic(monkeypatch, tmp_path, {DOI: work()}, LISTING, cancel=lambda: state["cancelled"])
    assert result["cancelled"] is True and len(requests) == 3
    attempt, = result["pdf_hint_attempts"]
    assert attempt["pdf_attempted"] is True and attempt["status"] == "interrupted"
    assert "raw_path" not in attempt and result["sources"][0]["scope"] == "metadata_only"
    assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")
    assert_retained(tmp_path, attempt["discovery"], content=LISTING)


@pytest.mark.parametrize("listing", [LISTING + LISTING, LISTING.replace(TITLE.encode(), (TITLE + " extra methods").encode()),
    LISTING.replace(URL.encode(), b"https://127.0.0.1/private.pdf"),
    LISTING.replace(URL.encode(), b"https://www.cs.cmu.edu/~other/papers/unverified.pdf")])
def test_ambiguous_similar_or_unsafe_official_leaf_never_dispatches_pdf(tmp_path, monkeypatch, clock, listing):
    result, requests = bibliographic(monkeypatch, tmp_path, {DOI: work()}, listing)
    assert len(requests) == 3 and result["sources"][0]["scope"] == "metadata_only"
    attempt, = result["pdf_hint_attempts"]
    assert not attempt.get("pdf_attempted") and attempt["status"] == "rejected"
    assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")
    assert_retained(tmp_path, attempt["discovery"], content=listing)


def test_exact_crossref_doi_substitution_is_rejected_before_author_lookup(tmp_path, monkeypatch, clock):
    result, requests = bibliographic(monkeypatch, tmp_path, {DOI: work("10.1234/other")}, LISTING)
    assert len(requests) == 2 and result["sources"] == []
    assert result["pdf_hint_attempts"] == [] and result["pdf_listing"]["attempted"] is False


def test_explicit_empty_candidate_list_disables_automatic_author_discovery(tmp_path, monkeypatch, clock):
    result, requests = bibliographic(monkeypatch, tmp_path, {DOI: work()}, LISTING, candidates=[])
    assert len(requests) == 2 and result["sources"][0]["scope"] == "metadata_only"
    assert "pdf_hint_attempts" not in result and "pdf_listing" not in result and "pdf_discovery_mode" not in result


def test_verified_generic_full_text_skips_official_author_list(tmp_path, monkeypatch, clock):
    doi = "10.21105/joss.01234"
    def respond(request):
        assert request.url.host != literature.AUTHOR_PDF_HOST
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json=work(doi, type="journal-article"))
        assert request.url.host == "joss.theoj.org"
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    requests = mocked(monkeypatch, respond)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT)
    result = literature.collect([doi], tmp_path, limit=1)
    assert len(requests) == 2 and result["sources"][0]["scope"] == "full_text"
    assert result["pdf_hint_attempts"] == [] and result["pdf_listing"]["attempted"] is False
    assert "copy_type" not in result["sources"][0]


def test_failed_generic_pdf_uses_separate_author_proof_and_discards_stale_arxiv_identity(tmp_path, monkeypatch, clock):
    feed = ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">'
            '<entry><id>http://arxiv.org/abs/1311.3903v1</id><title>' + TITLE + '</title><arxiv:doi>' + DOI
            + '</arxiv:doi></entry></feed>').encode()
    def respond(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json=work(type="proceedings-article"))
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, content=feed, headers={"content-type": "application/atom+xml"})
        if request.url.host == "arxiv.org":
            return httpx.Response(403)
        if str(request.url) == literature.AUTHOR_PUBLICATIONS:
            return httpx.Response(200, content=LISTING, headers={"content-type": "text/html"})
        assert str(request.url) == URL
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    requests = mocked(monkeypatch, respond)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT)
    result = literature.collect([DOI], tmp_path, limit=1)
    source, = result["sources"]
    assert len(requests) == 5 and source["scope"] == "full_text" and source["copy_type"] == "author_copy"
    assert "arxiv_id" not in source and source["discovery_url"] == literature.AUTHOR_PUBLICATIONS
    assert_retained(tmp_path, source, "discovery_path", "discovery_sha256", LISTING)
    assert any(path.read_bytes() == feed for path in (tmp_path / "literature").glob("*.xml"))


def test_listing_failure_is_not_retried_for_later_exact_metadata_candidates(tmp_path, monkeypatch, clock):
    def respond(request):
        if request.url.host == "api.crossref.org":
            if request.url.path == "/works":
                return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": DOI}, {"DOI": "10.1234/other"}]}})
            return httpx.Response(200, json=work(request.url.path.removeprefix("/works/")))
        assert str(request.url) == literature.AUTHOR_PUBLICATIONS
        return httpx.Response(503, content=b"Complete unavailable list", headers={"content-type": "text/html"})
    requests = mocked(monkeypatch, respond)
    result = literature.collect(["selective recovery comparison"], tmp_path, limit=2)
    assert len(requests) == 4 and result["pdf_listing"]["http_status"] == 503
    assert_retained(tmp_path, result["pdf_listing"], content=b"Complete unavailable list")
    assert len(result["pdf_hint_attempts"]) == 2 and not any(item.get("pdf_attempted") for item in result["pdf_hint_attempts"])
    assert all(source["scope"] == "metadata_only" for source in result["sources"])


def test_initial_author_listing_shares_deadline_and_never_dispatches_pdf_after_expiry(tmp_path, monkeypatch, clock):
    def respond(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json=work())
        assert str(request.url) == literature.AUTHOR_PUBLICATIONS
        clock.value = 91
        return httpx.Response(200, content=LISTING, headers={"content-type": "text/html"})
    requests = mocked(monkeypatch, respond)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: pytest.fail("Worker after deadline"))
    result = literature.collect([DOI], tmp_path, limit=1)
    assert result["timed_out"] is True and len(requests) == 2 and result["sources"][0]["scope"] == "metadata_only"
    assert result["pdf_hint_attempts"][0]["status"] == "interrupted"
    assert not result["pdf_hint_attempts"][0].get("pdf_attempted")
    assert "raw_path" not in result["pdf_listing"]

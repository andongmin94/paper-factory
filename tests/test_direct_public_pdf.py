"""Explicit public scholarly copies retain exact identity, failures and shared budget."""
import json

import httpx
import pytest

from paper_factory.autonomous import literature
from test_autonomous_literature import clock, mocked, record
from test_openalex_discovery import work
from test_public_pdf_hints import DOI, PDF, TEXT, TITLE, assert_retained


URL = "https://papers.example.edu/papers/verified.pdf"
HINT = {"doi": DOI, "title": TITLE, "url": URL}
SOURCE = {"doi": DOI, "title": TITLE, "authors": ["Ada Lovelace"], "year": 2024}
PUBLIC_TEXT = TEXT.replace("Example University\n", "Example University, 2024\n")


def collection(monkeypatch, root, *, text=PUBLIC_TEXT, handler=None, metadata=None, cancel=None,
               extractor=None, reservation_limit=2, excluded_urls=None):
    def respond(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json=metadata or record())
        assert str(request.url) == URL
        if handler:
            return handler(request)
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})

    requests = mocked(monkeypatch, respond)
    monkeypatch.setattr(literature, "_arxiv_pdf", lambda *a, **k: pytest.fail("Direct hints cannot rediscover the work"))
    monkeypatch.setattr(literature, "_author_listing", lambda *a, **k: pytest.fail("Direct hints cannot use the CMU catalog"))
    monkeypatch.setattr(literature, "_pdf_text", extractor or (lambda raw: text))
    result = literature.collect([DOI], root, limit=1, pdf_candidates=[HINT], cancel=cancel,
        pdf_reservation_limit=reservation_limit, excluded_urls=excluded_urls)
    return result, requests


def test_direct_verified_copy_retains_full_proof_without_unrelated_discovery(tmp_path, monkeypatch, clock):
    result, requests = collection(monkeypatch, tmp_path)
    assert [str(item.url) for item in requests] == [literature.CROSSREF + "/works/10.1234%2Ftest", URL]
    source, = result["sources"]
    attempt, = result["pdf_hint_attempts"]
    assert source["scope"] == "full_text" and source["copy_type"] == "repository_copy"
    assert source["publication_version"] == "unknown" and source["discovery_url"] == URL
    assert attempt["route"] == "direct_public_pdf" and attempt["status"] == "verified"
    assert result["pdf_reservations"] == [{"source_id": source["id"], "identity": "doi:" + DOI,
        "route": "repository_copy", "url": URL, "pdf_attempted": True}]
    assert_retained(tmp_path, source, content=PDF)
    assert_retained(tmp_path, source, "text_path", "text_sha256", PUBLIC_TEXT.encode())
    selection = json.loads(assert_retained(tmp_path, source, "discovery_path", "discovery_sha256"))
    assert selection == {"origin": "explicit_pdf_candidate", "candidate": HINT,
        "metadata_path": source["metadata_path"], "metadata_sha256": source["metadata_sha256"]}
    proof = json.loads(assert_retained(tmp_path, source, "identity_path", "identity_sha256"))
    assert proof["candidate"] == HINT and proof["redirects"] == []
    assert proof["identity"] == literature.public_pdf_identity(PUBLIC_TEXT, source)
    assert proof["identity"]["doi_printed"] is True
    body = source["body_range"]
    for literal, span in zip(source["excerpts"], source["excerpt_ranges"]):
        assert literal == PUBLIC_TEXT[span["start"]:span["end"]]
        assert body["start"] <= span["start"] < span["end"] <= body["end"]


def test_normalization_is_pure_and_preserves_explicit_public_identity(monkeypatch):
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *a, **k: pytest.fail("Normalization cannot do DNS"))
    assert literature.normalize_pdf_candidates([{**HINT, "doi": " 10.1234/TEST "}], [DOI]) == [HINT]
    assert literature.normalize_pdf_candidates([{"doi": DOI, "title": TITLE}], [DOI]) == [{"doi": DOI, "title": TITLE}]
    with pytest.raises(ValueError, match="explicitly requested"):
        literature.normalize_pdf_candidates([HINT], [TITLE])


@pytest.mark.parametrize("url", ["http://papers.example.edu/paper.pdf", "https://127.0.0.1/paper.pdf",
    "https://user:secret@papers.example.edu/paper.pdf", URL + "?token=secret", URL + "#fragment",
    "https://papers.example.edu:444/paper.pdf", "https://papers.example.edu/papers/%2e%2e/paper.pdf"])
def test_unsafe_direct_hint_rejected_before_files_dns_http(tmp_path, monkeypatch, url):
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *a, **k: pytest.fail("Unsafe hint reached DNS"))
    monkeypatch.setattr(literature.httpx, "Client", lambda **k: pytest.fail("Unsafe hint reached HTTP"))
    root = tmp_path / "not-created"
    with pytest.raises(ValueError):
        literature.collect([DOI], root, pdf_candidates=[{**HINT, "url": url}])
    assert not root.exists()


def test_cover_combined_authors_and_missing_printed_doi_are_explicit():
    source = {**SOURCE, "authors": ["Ada Lovelace", "Grace Hopper"]}
    text = PUBLIC_TEXT.replace("[Page 2]", "[Page 3]").replace("[Page 1]", "[Page 2]")
    text = "[Page 1]\nOfficial conference proceedings\n2024\n" + text
    text = text.replace("Ada Lovelace\n", "Ada Lovelace†, Grace Hopper‡\n").replace(DOI + "\n", "\n", 1)
    proof = literature.public_pdf_identity(text, source)
    assert proof["identity_page"] == 2 and proof["doi_printed"] is False and proof["doi_ranges"] == []
    assert [text[item["start"]:item["end"]] for item in proof["author_ranges"]] == source["authors"]
    assert text[proof["title_range"]["start"]:proof["title_range"]["end"]] == TITLE
    # The CMU-only policy remains unchanged.
    with pytest.raises(ValueError):
        literature.author_pdf_identity(text, source)


def test_exact_printed_doi_can_bind_metadata_when_year_is_not_printed():
    proof = literature.public_pdf_identity(TEXT, SOURCE)
    assert proof["doi_printed"] is True and proof["year_ranges"] == []


def test_a_fourth_page_title_and_abstract_cannot_supply_identity():
    text = PUBLIC_TEXT.replace("[Page 2]", "[Page 5]").replace("[Page 1]", "[Page 4]")
    text = "[Page 1]\nCover\n2024\n[Page 2]\nA second cover\n[Page 3]\nA third cover\n" + text
    with pytest.raises(ValueError, match="first three pages"):
        literature.public_pdf_identity(text, SOURCE)


@pytest.mark.parametrize("text,source", [
    (PUBLIC_TEXT.replace(TITLE, TITLE + " with another method", 1), SOURCE),
    (PUBLIC_TEXT.replace(TITLE, TITLE + "\nwith another method", 1), SOURCE),
    (PUBLIC_TEXT.replace(TITLE, "Another complete title\n" + TITLE, 1), SOURCE),
    (PUBLIC_TEXT.replace("Ada Lovelace", "Ada Lovelaceford", 1), SOURCE),
    (PUBLIC_TEXT.replace("Ada Lovelace\n", "Someone Else\n", 1).replace("Abstract—", "Abstract—Ada Lovelace: ", 1), SOURCE),
    (PUBLIC_TEXT, {**SOURCE, "authors": ["Ada Lovelace", "Grace Hopper"]}),
    (PUBLIC_TEXT.replace(DOI + "\n", "10.1234/other\n", 1), SOURCE),
    (PUBLIC_TEXT.replace("2024", "2023").replace(DOI + "\n", "\n", 1), SOURCE),
    (PUBLIC_TEXT.replace("Abstract—", "Summary—", 1), SOURCE),
])
def test_public_identity_requires_complete_literal_front_matter(text, source):
    with pytest.raises(ValueError):
        literature.public_pdf_identity(text, source)


def test_title_and_authors_from_body_or_references_never_establish_identity():
    text = PUBLIC_TEXT.replace(TITLE, "Another actual paper", 1).replace("Ada Lovelace", "Someone Else", 1)
    text = text.replace("2 Methods", "2 Methods\n" + TITLE + "\nAda Lovelace")
    with pytest.raises(ValueError):
        literature.public_pdf_identity(text, SOURCE)


def test_metadata_title_mismatch_consumes_no_pdf(tmp_path, monkeypatch, clock):
    metadata = record()
    metadata["message"]["title"] = ["A different actual paper"]
    result, requests = collection(monkeypatch, tmp_path, metadata=metadata)
    assert len(requests) == 1 and result["pdf_reservations"] == []
    assert result["sources"][0]["scope"] == "metadata_only"


@pytest.mark.parametrize("status,kind,raw", [(403, "text/html", b"The entire refused page"),
    (206, "application/pdf", PDF), (200, "text/html", b"The complete non-PDF body"),
    (200, "application/pdf", b"Not a PDF signature")])
def test_failed_response_is_retained_once_never_promoted(tmp_path, monkeypatch, clock, status, kind, raw):
    result, requests = collection(monkeypatch, tmp_path, handler=lambda request:
        httpx.Response(status, content=raw, headers={"content-type": kind}))
    attempt, = result["pdf_hint_attempts"]
    assert len(requests) == 2 and len(result["pdf_reservations"]) == 1
    assert attempt["status"] == "rejected" and result["sources"][0]["scope"] == "metadata_only"
    assert_retained(tmp_path, attempt, content=raw)


def test_direct_redirect_is_retained_but_not_followed(tmp_path, monkeypatch, clock):
    result, requests = collection(monkeypatch, tmp_path, handler=lambda request:
        httpx.Response(302, content=b"Redirect response", headers={"location": "https://other.example.edu/paper.pdf"}))
    attempt, = result["pdf_hint_attempts"]
    assert len(requests) == 2 and len(attempt["redirects"]) == 1
    assert attempt["status"] == "rejected" and result["sources"][0]["scope"] == "metadata_only"
    assert_retained(tmp_path, attempt["redirects"][0], content=b"Redirect response")


@pytest.mark.parametrize("limit,excluded", [(0, []), (2, [URL])])
def test_prior_pdf_budget_and_failed_url_cannot_be_replayed(tmp_path, monkeypatch, clock, limit, excluded):
    result, requests = collection(monkeypatch, tmp_path, reservation_limit=limit, excluded_urls=excluded)
    assert len(requests) == 1 and result["pdf_reservations"] == []
    assert result["sources"][0]["scope"] == "metadata_only"


def test_private_dns_after_reservation_never_uses_proxy_exception(tmp_path, monkeypatch, clock):
    def dns(host, *a, **k):
        return [(2, 1, 6, "", ("127.0.0.1" if host == "papers.example.edu" else "8.8.8.8", 443))]
    # Set the DNS guard after the mock fixture has initialized its normal provider.
    def extractor(raw):
        pytest.fail("Private-host response cannot reach extraction")
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json=record()))
    monkeypatch.setattr(literature.socket, "getaddrinfo", dns)
    monkeypatch.setattr(literature, "getproxies_environment", lambda: {"https": "http://public-proxy"})
    monkeypatch.setattr(literature, "_pdf_text", extractor)
    result = literature.collect([DOI], tmp_path, pdf_candidates=[HINT])
    assert len(requests) == 1 and len(result["pdf_reservations"]) == 1
    assert result["sources"][0]["scope"] == "metadata_only"


def test_cancel_after_extraction_keeps_new_raw_text_without_promoting(tmp_path, monkeypatch, clock):
    state = {"cancelled": False}
    def extract(raw):
        state["cancelled"] = True
        return PUBLIC_TEXT
    result, _ = collection(monkeypatch, tmp_path, extractor=extract, cancel=lambda: state["cancelled"])
    attempt, = result["pdf_hint_attempts"]
    assert result["cancelled"] is True and attempt["status"] == "interrupted"
    assert_retained(tmp_path, attempt, content=PDF)
    assert_retained(tmp_path, attempt, "text_path", "text_sha256", PUBLIC_TEXT.encode())
    assert result["sources"][0]["scope"] == "metadata_only"


def test_exact_default_doi_reads_openalex_before_unrelated_routes(tmp_path, monkeypatch, clock):
    def respond(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json=record())
        if request.url.host == "api.openalex.org":
            return httpx.Response(200, json=work())
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    requests = mocked(monkeypatch, respond, openalex_discovery=True)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT)
    monkeypatch.setattr(literature, "_arxiv_pdf", lambda *a, **k: pytest.fail("An exact body already resolved"))
    monkeypatch.setattr(literature, "_author_listing", lambda *a, **k: pytest.fail("An exact body already resolved"))
    result = literature.collect([DOI], tmp_path, limit=1)
    assert [item.url.host for item in requests] == ["api.crossref.org", "api.openalex.org", "zenodo.org"]
    assert result["sources"][0]["scope"] == "full_text" and len(result["pdf_reservations"]) == 1


def test_failed_early_openalex_is_not_queried_again(tmp_path, monkeypatch, clock):
    def respond(request):
        if request.url.host == "api.crossref.org":
            value = record()
            value["message"]["type"] = "proceedings-article"
            return httpx.Response(200, json=value)
        if request.url.host == "api.openalex.org":
            return httpx.Response(403, content=b"Original denial", headers={"content-type": "text/plain"})
        return httpx.Response(200, content=b"<ul></ul>", headers={"content-type": "text/html"})
    requests = mocked(monkeypatch, respond, openalex_discovery=True)
    events = []
    monkeypatch.setattr(literature, "_arxiv_pdf", lambda *a, **k: events.append("arxiv") or None)
    result = literature.collect([DOI], tmp_path, limit=1)
    assert sum(item.url.host == "api.openalex.org" for item in requests) == 1
    assert events == ["arxiv"] and result["sources"][0]["scope"] == "metadata_only"
    assert result["pdf_reservations"] == []


def test_default_openalex_accepts_exact_scholarly_cover_without_printed_doi(tmp_path, monkeypatch, clock):
    text = TEXT.replace("[Page 2]", "[Page 3]").replace("[Page 1]", "[Page 2]")
    text = "[Page 1]\nOfficial conference proceedings 2024\n" + text.replace(DOI + "\n", "\n", 1)
    def respond(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json=record())
        if request.url.host == "api.openalex.org":
            return httpx.Response(200, json=work())
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    requests = mocked(monkeypatch, respond, openalex_discovery=True)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: text)
    monkeypatch.setattr(literature, "_arxiv_pdf", lambda *a, **k: pytest.fail("Already read the exact scholarly body"))
    result = literature.collect([DOI], tmp_path)
    source, = result["sources"]
    proof, = result["pdf_hint_attempts"]
    assert [item.url.host for item in requests] == ["api.crossref.org", "api.openalex.org", "zenodo.org"]
    assert source["scope"] == "full_text" and len(result["pdf_reservations"]) == 1
    assert proof["identity"]["identity_page"] == 2 and proof["identity"]["doi_printed"] is False
    assert proof["identity"] == literature.public_pdf_identity(text, source)


def test_prior_arxiv_alias_exclusions_preserve_discovery_before_doi_pdf(tmp_path, monkeypatch, clock):
    metadata = record()
    metadata["message"]["type"] = "proceedings-article"
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json=metadata), openalex_discovery=True)
    monkeypatch.setattr(literature, "_promote_openalex_pdf", lambda *a, **k: pytest.fail("An excluded preprint alias cannot become a DOI copy"))
    def discover(client, source, *a, **k):
        source["arxiv_id"] = "1311.3903v1"
        return "https://arxiv.org/pdf/1311.3903v1"
    monkeypatch.setattr(literature, "_arxiv_pdf", discover)
    result = literature.collect([DOI], tmp_path, excluded_identities=["arxiv:1311.3903"])
    assert len(requests) == 1 and result["pdf_reservations"] == []
    assert result["sources"][0]["scope"] == "metadata_only"
    assert result["candidate_rejections"][0]["reason"] == "excluded_identity"


def test_two_direct_work_copies_share_failed_and_successful_reservations(tmp_path, monkeypatch, clock):
    other_doi, other_title, other_url = "10.1234/another", "Another verified record title", URL.replace("verified", "another")
    hints = [HINT, {"doi": other_doi, "title": other_title, "url": other_url}]
    def respond(request):
        if request.url.host == "api.crossref.org":
            metadata = record(other_doi if request.url.path.endswith("another") else DOI)
            if request.url.path.endswith("another"):
                metadata["message"]["title"] = [other_title]
            return httpx.Response(200, json=metadata)
        assert str(request.url) in {URL, other_url}
        return httpx.Response(200, content=PDF if str(request.url) == other_url else b"%PDF-wrong-work",
                              headers={"content-type": "application/pdf"})
    requests = mocked(monkeypatch, respond)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: PUBLIC_TEXT.replace(TITLE, other_title).replace(DOI, other_doi)
                        if raw == PDF else PUBLIC_TEXT.replace(TITLE, "Unrelated actual work", 1))
    result = literature.collect([DOI, other_doi], tmp_path, pdf_candidates=hints)
    assert len(requests) == 4 and len(result["pdf_reservations"]) == 2
    assert [attempt["status"] for attempt in result["pdf_hint_attempts"]] == ["rejected", "verified"]
    assert [source["scope"] for source in result["sources"]] == ["metadata_only", "full_text"]
    for attempt in result["pdf_hint_attempts"]:
        assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")


def test_direct_deadline_keeps_received_pdf_without_dispatching_extraction(tmp_path, monkeypatch, clock):
    def late(request):
        clock.value = 75
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    result, _ = collection(monkeypatch, tmp_path, handler=late,
        extractor=lambda raw: pytest.fail("Insufficient extraction and cleanup time"))
    attempt, = result["pdf_hint_attempts"]
    assert result["timed_out"] is True and attempt["status"] == "interrupted"
    assert_retained(tmp_path, attempt, content=PDF)
    assert "text_path" not in attempt and len(result["pdf_reservations"]) == 1

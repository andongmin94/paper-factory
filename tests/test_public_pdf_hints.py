"""Untrusted public PDF hints bind to exact metadata and literal first-page identity."""
import hashlib
import json

import httpx
import pytest

from paper_factory.autonomous import literature
from test_autonomous_literature import clock, mocked, record


DOI = "10.1234/test"
TITLE = "Verified record title"
URL = "https://www.cs.cmu.edu/~NatProg/papers/verified-author.pdf"
HINT = {"doi": DOI, "title": TITLE, "url": URL}
PDF = b"%PDF-complete-author-copy-fixture"
HTTP_CLIENT = httpx.Client
TEXT = ("[Page 1]\nVerified record title\nAda Lovelace\nExample University\n"
        "Abstract—A literal summary.\n1 Introduction\n" + "Actual comparison and recovery methods are retained verbatim. " * 60
        + "\n10.1234/test\n\n[Page 2]\n2 Methods\n" + "Measured results and original method details. " * 60
        + "\nReferences\nA later bibliography with 10.9999/other is outside first-page identity.\n")


def collect_hint(monkeypatch, tmp_path, *, text=TEXT, raw=PDF, content_type="application/pdf", status=200,
                 metadata=None, handler=None, cancel=None, extractor=None):
    def respond(request):
        if request.url.host == "api.crossref.org":
            assert request.url.path == "/works/10.1234/test"
            return httpx.Response(200, json=metadata if metadata is not None else record())
        assert request.url.host == "www.cs.cmu.edu"
        if handler is not None:
            return handler(request)
        return httpx.Response(status, content=raw, headers={"content-type": content_type})
    monkeypatch.setattr(literature.httpx, "Client", HTTP_CLIENT)
    requests = mocked(monkeypatch, respond)
    monkeypatch.setattr(literature, "_pdf_text", extractor if extractor else lambda raw: text)
    result = literature.collect(["DOI: 10.1234/test"], tmp_path, limit=1,
                                pdf_candidates=[HINT], cancel=cancel)
    return result, requests


def assert_retained(root, value, path_key="raw_path", hash_key="sha256", content=None):
    raw = (root / value[path_key]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == value[hash_key]
    if content is not None:
        assert raw == content
    return raw


def test_verified_author_copy_preserves_metadata_pdf_text_identity_and_literal_ranges(tmp_path, monkeypatch):
    result, requests = collect_hint(monkeypatch, tmp_path)
    source, = result["sources"]
    attempt, = result["pdf_hint_attempts"]
    assert len(requests) == 2 and not result["warnings"]
    assert source["scope"] == "full_text" and source["url"] == URL
    assert source["copy_type"] == "author_copy" and source["publication_version"] == "unknown"
    assert source["doi"] == DOI and source["title"] == TITLE and source["authors"] == ["Ada Lovelace"]
    assert source["body_range"] == literature.full_text_body_range(TEXT)
    assert_retained(tmp_path, source, content=PDF)
    assert_retained(tmp_path, source, "text_path", "text_sha256", TEXT.encode())
    assert_retained(tmp_path, source, "metadata_path", "metadata_sha256")
    proof = json.loads(assert_retained(tmp_path, source, "identity_path", "identity_sha256"))
    assert proof["status"] == attempt["status"] == "verified" and proof["metadata_sha256"] == source["metadata_sha256"]
    identity = proof["identity"]
    assert TEXT[identity["title_range"]["start"]:identity["title_range"]["end"]] == TITLE
    for location in identity["author_ranges"]:
        assert TEXT[location["start"]:location["end"]] == location["author"]
    for location in identity["doi_ranges"]:
        assert TEXT[location["start"]:location["end"]] == DOI
    body = source["body_range"]
    for excerpt, location in zip(source["excerpts"], source["excerpt_ranges"]):
        assert excerpt == TEXT[location["start"]:location["end"]]
        assert body["start"] <= location["start"] < location["end"] <= body["end"]


def test_hint_normalization_is_pure_and_requires_explicit_doi(monkeypatch):
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *args, **kwargs: pytest.fail("Normalization must not do DNS"))
    value = {"doi": " 10.1234/TEST ", "title": " Verified record title ",
             "url": "https://www.cs.cmu.edu:443/~NatProg/papers/verified-author.pdf"}
    normalized = literature.normalize_pdf_candidates([value], ["DOI: 10.1234/TEST"])
    assert normalized == [HINT] and value["doi"] == " 10.1234/TEST "
    assert literature.normalize_pdf_candidates([], [TITLE]) == []
    with pytest.raises(ValueError, match="explicitly requested"):
        literature.normalize_pdf_candidates([HINT], ["A paper containing 10.1234/test somewhere"])


@pytest.mark.parametrize("value", [None, {}, [HINT] * 3, [HINT] * 2, [{**HINT, "extra": True}],
    [{"doi": DOI, "title": TITLE}], [{**HINT, "doi": "https://doi.org/10.1234/test"}],
    [{**HINT, "title": ""}], [{**HINT, "title": "x" * 501}], [{**HINT, "title": "title\x7f"}],
    [{**HINT, "title": "title\n"}], [{**HINT, "title": 2}], [{**HINT, "doi": "10.1234/else"}],
    [{**HINT, "url": "http://www.cs.cmu.edu/~NatProg/papers/test.pdf"}],
    [{**HINT, "url": "https://www.cs.cmu.edu.evil.test/~NatProg/papers/test.pdf"}],
    [{**HINT, "url": "https://user:secret@www.cs.cmu.edu/~NatProg/papers/test.pdf"}],
    [{**HINT, "url": "https://www.cs.cmu.edu:444/~NatProg/papers/test.pdf"}],
    [{**HINT, "url": URL + "?token=secret"}], [{**HINT, "url": URL + "#fragment"}],
    [{**HINT, "url": "https://www.cs.cmu.edu/~other/papers/test.pdf"}],
    [{**HINT, "url": "https://www.cs.cmu.edu/~NatProg/papers/../private.pdf"}],
    [{**HINT, "url": "https://www.cs.cmu.edu/~NatProg/papers/%2e%2e/private.pdf"}],
    [{**HINT, "url": "https://www.cs.cmu.edu/~NatProg/papers/test.html"}],
    [{**HINT, "url": URL + "\x7f"}], [{**HINT, "url": URL + "\n"}],
    [{**HINT, "url": "https://127.0.0.1/~NatProg/papers/test.pdf"}]])
def test_invalid_hints_rejected_before_files_dns_or_http(tmp_path, monkeypatch, value):
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *args, **kwargs: pytest.fail("Unsafe hint reached DNS"))
    monkeypatch.setattr(literature.httpx, "Client", lambda **kwargs: pytest.fail("Unsafe hint reached HTTP"))
    root = tmp_path / "not-created"
    with pytest.raises(ValueError):
        if value is None:
            literature.normalize_pdf_candidates(value, [DOI])
        else:
            literature.collect([DOI], root, pdf_candidates=value)
    assert not root.exists()


@pytest.mark.parametrize("text", [
    TEXT.replace(TITLE, TITLE + " with different methods", 1),
    TEXT.replace(TITLE, TITLE + "\nwith different methods", 1),
    TEXT.replace(TITLE, "A different initial heading", 1).replace("Abstract—", "Abstract—" + TITLE + ". ", 1),
    TEXT.replace("Ada Lovelace", "Grace Hopper", 1),
    TEXT.replace("Ada Lovelace\n", "", 1).replace("Abstract—", "Abstract—Ada Lovelace. ", 1),
    TEXT.replace("10.1234/test\n", "10.1234/test-extra\n", 1),
    TEXT.replace("10.1234/test\n", "10.1234/different\n", 1),
    TEXT.replace("10.1234/test\n", "\n", 1).replace("[Page 2]\n", "[Page 2]\n10.1234/test\n", 1),
    TEXT.replace("10.1234/test\n", "10.1234/test\n10.9999/other\n", 1),
    TEXT.replace("Abstract—", "Summary—", 1),
    TEXT.replace("[Page 1]\n", "", 1),
    TEXT.replace("Example University\n", "Example University\n" + "a" * 8_001 + "\n", 1),
    "[Page 1]\n" + TITLE + "\nAda Lovelace\n10.1234/test\nAbstract—" + "Summary only. " * 40,
])
def test_identity_failure_never_promotes_but_preserves_complete_original_and_extraction(tmp_path, monkeypatch, text):
    result, requests = collect_hint(monkeypatch, tmp_path, text=text)
    source, = result["sources"]
    attempt, = result["pdf_hint_attempts"]
    assert len(requests) == 2 and source["scope"] == "metadata_only"
    assert source["raw_path"] == source["metadata_path"] and "text_path" not in source
    assert attempt["status"] == "rejected" and attempt["error"] == "ValueError"
    assert_retained(tmp_path, attempt, content=PDF)
    assert_retained(tmp_path, attempt, "text_path", "text_sha256", text.encode())
    proof = json.loads(assert_retained(tmp_path, attempt, "identity_path", "identity_sha256"))
    assert proof["status"] == "rejected" and proof["sha256"] == attempt["sha256"]


def test_whole_wrapped_title_and_all_metadata_authors_are_required(tmp_path, monkeypatch):
    metadata = record()
    metadata["message"]["author"].append({"given": "Grace", "family": "Hopper"})
    text = TEXT.replace(TITLE, "Verified record\ntitle", 1).replace("Ada Lovelace\n", "Ada Lovelace\nGrace Hopper\n", 1)
    result, _ = collect_hint(monkeypatch, tmp_path, text=text, metadata=metadata)
    assert result["sources"][0]["scope"] == "full_text"
    missing = tmp_path / "missing-second-author"
    result, _ = collect_hint(monkeypatch, missing, metadata=metadata)
    assert result["sources"][0]["scope"] == "metadata_only" and result["pdf_hint_attempts"][0]["status"] == "rejected"


@pytest.mark.parametrize("metadata", [record("10.1234/other"),
    {"status": "ok", "message": {**record()["message"], "title": [TITLE + " for another problem"]}}])
def test_exact_crossref_mismatch_refuses_hint_before_pdf_request(tmp_path, monkeypatch, metadata):
    result, requests = collect_hint(monkeypatch, tmp_path, metadata=metadata)
    assert len(requests) == 1 and all(request.url.host == "api.crossref.org" for request in requests)
    assert not any(source["scope"] == "full_text" for source in result["sources"])


@pytest.mark.parametrize("status,ctype,raw", [(403, "text/html", b"Complete refused response"),
    (206, "application/pdf", PDF),
    (200, "text/html", b"Complete HTML instead of a PDF"), (200, "application/pdf", b"%PDF-malformed")])
def test_completed_failed_http_content_and_extraction_are_retained(tmp_path, monkeypatch, status, ctype, raw):
    def fail_pdf(raw):
        raise ValueError("Malformed PDF must not be promoted")
    result, _ = collect_hint(monkeypatch, tmp_path, raw=raw, status=status, content_type=ctype,
                             extractor=fail_pdf if raw == b"%PDF-malformed" else None)
    assert result["sources"][0]["scope"] == "metadata_only"
    attempt = result["pdf_hint_attempts"][0]
    assert attempt["status"] == "rejected" and attempt["http_status"] == status
    assert_retained(tmp_path, attempt, content=raw)
    assert_retained(tmp_path, attempt, "identity_path", "identity_sha256")


def test_same_origin_redirect_is_bounded_and_cross_origin_is_not_requested(tmp_path, monkeypatch):
    final = URL.replace("verified-author.pdf", "second-author.pdf")
    def same(request):
        if str(request.url) == URL:
            return httpx.Response(302, headers={"location": "second-author.pdf"})
        assert str(request.url) == final
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    result, requests = collect_hint(monkeypatch, tmp_path, handler=same)
    assert len(requests) == 3 and result["sources"][0]["url"] == final
    result, requests = collect_hint(monkeypatch, tmp_path / "cross-origin", handler=lambda request:
        httpx.Response(302, headers={"location": "https://arxiv.org/pdf/1311.3903v1"}))
    assert len(requests) == 2 and result["sources"][0]["scope"] == "metadata_only"
    assert result["pdf_hint_attempts"][0]["status"] == "rejected"


def test_private_hint_dns_is_rejected_without_proxy_exception(tmp_path, monkeypatch):
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json=record()))
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda host, *args, **kwargs:
        [(2, 1, 6, "", ("127.0.0.1" if host == "www.cs.cmu.edu" else "8.8.8.8", 443))])
    monkeypatch.setattr(literature, "getproxies_environment", lambda: {"https": "http://example-proxy"})
    result = literature.collect([DOI], tmp_path, limit=1, pdf_candidates=[HINT])
    assert len(requests) == 1 and result["sources"][0]["scope"] == "metadata_only"
    assert "raw_path" not in result["pdf_hint_attempts"][0]


def test_cmu_link_without_typed_hint_cannot_bypass_identity_check(tmp_path, monkeypatch):
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json=record(links=[{"URL": URL, "content-type": "application/pdf"}])))
    result = literature.collect([DOI], tmp_path, limit=1)
    assert len(requests) == 1 and result["sources"][0]["scope"] == "metadata_only"
    assert "pdf_hint_attempts" not in result


def test_failed_hint_has_no_arxiv_or_generic_pdf_fallback(tmp_path, monkeypatch):
    metadata = record(links=[{"URL": "https://arxiv.org/pdf/1311.3903v1", "content-type": "application/pdf"}])
    metadata["message"]["type"] = "proceedings-article"
    monkeypatch.setattr(literature, "_arxiv_pdf", lambda *args, **kwargs: pytest.fail("Hint route must never run arXiv discovery"))
    result, requests = collect_hint(monkeypatch, tmp_path, metadata=metadata,
                                    text=TEXT.replace(TITLE, "A different paper", 1))
    assert len(requests) == 2 and {request.url.host for request in requests} == {"api.crossref.org", "www.cs.cmu.edu"}
    assert result["sources"][0]["scope"] == "metadata_only"


def test_two_hints_retain_rejected_and_verified_bytes_with_separate_proofs(tmp_path, monkeypatch):
    other_url = URL.replace("verified-author.pdf", "another-author.pdf")
    wrong = b"%PDF-complete-different-paper"
    def respond(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json=record())
        return httpx.Response(200, content=wrong if str(request.url) == URL else PDF,
                              headers={"content-type": "application/pdf"})
    requests = mocked(monkeypatch, respond)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT.replace(TITLE, "A different paper", 1) if raw == wrong else TEXT)
    result = literature.collect([DOI], tmp_path, limit=1, pdf_candidates=[HINT, {**HINT, "url": other_url}])
    assert len(requests) == 3 and result["sources"][0]["scope"] == "full_text"
    rejected, verified = result["pdf_hint_attempts"]
    assert rejected["status"] == "rejected" and verified["status"] == "verified"
    assert_retained(tmp_path, rejected, content=wrong)
    assert_retained(tmp_path, verified, content=PDF)
    assert rejected["identity_path"] != verified["identity_path"]
    assert_retained(tmp_path, rejected, "identity_path", "identity_sha256")
    assert_retained(tmp_path, verified, "identity_path", "identity_sha256")


def test_hint_dns_failure_has_no_managed_proxy_exception(tmp_path, monkeypatch):
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json=record()))
    def dns(host, *args, **kwargs):
        if host == "www.cs.cmu.edu":
            raise OSError("No public DNS answer")
        return [(2, 1, 6, "", ("8.8.8.8", 443))]
    monkeypatch.setattr(literature.socket, "getaddrinfo", dns)
    monkeypatch.setattr(literature, "getproxies_environment", lambda: {"https": "http://example-proxy"})
    result = literature.collect([DOI], tmp_path, limit=1, pdf_candidates=[HINT])
    assert len(requests) == 1 and result["sources"][0]["scope"] == "metadata_only"
    assert result["pdf_hint_attempts"][0]["status"] == "rejected"


def test_cancel_after_completed_extraction_keeps_raw_text_and_original_source(tmp_path, monkeypatch):
    state = {"cancelled": False}
    def extraction(raw):
        state["cancelled"] = True
        return TEXT
    result, _ = collect_hint(monkeypatch, tmp_path, cancel=lambda: state["cancelled"], extractor=extraction)
    assert result["cancelled"] is True and result["sources"][0]["scope"] == "metadata_only"
    attempt = result["pdf_hint_attempts"][0]
    assert attempt["status"] == "interrupted" and attempt["error"] == "_Cancelled"
    assert_retained(tmp_path, attempt, content=PDF)
    assert_retained(tmp_path, attempt, "text_path", "text_sha256", TEXT.encode())


def test_extraction_time_reservation_preserves_complete_pdf_without_worker_dispatch(tmp_path, monkeypatch, clock):
    def late(request):
        clock.value = 74
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    result, _ = collect_hint(monkeypatch, tmp_path, handler=late)
    assert result["timed_out"] is True and result["sources"][0]["scope"] == "metadata_only"
    attempt = result["pdf_hint_attempts"][0]
    assert "text_path" not in attempt and attempt["error"] == "_DeadlineExceeded"
    assert_retained(tmp_path, attempt, content=PDF)


def test_hinted_explicit_doi_is_inspected_before_generic_abstract_source_limit(tmp_path, monkeypatch, clock):
    other = "10.1234/generic"
    def respond(request):
        if request.url.host == "www.cs.cmu.edu":
            return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": other}]}})
        if request.url.path.endswith("generic"):
            return httpx.Response(200, json=record(other, abstract="Unrelated generic abstract could consume the only inspected slot."))
        return httpx.Response(200, json=record())
    requests = mocked(monkeypatch, respond)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT)
    result = literature.collect(["generic title", DOI], tmp_path, limit=1, pdf_candidates=[HINT])
    source, = result["sources"]
    assert source["doi"] == DOI and source["scope"] == "full_text" and not result["warnings"]
    assert not any(request.url.path.endswith("generic") for request in requests)

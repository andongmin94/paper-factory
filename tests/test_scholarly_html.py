import hashlib
import json

import httpx
import pytest

from paper_factory.autonomous import literature
from test_autonomous_literature import clock, mocked


LANDING = "https://www.usenix.org/conference/hotsec-07/verified-source-study"
BODY = "https://www.usenix.org/legacy/event/hotsec07/tech/full_papers/sample/sample_html/index.html"
TITLE = "A source-bound delegation study"
HINT = {"landing_url": LANDING, "html_url": BODY, "title": TITLE, "authors": ["Ada Lovelace", "Grace Hopper"],
        "year": 2007, "publication_type": "proceedings-article", "publication_version": "published"}
METADATA = (f'<html><body><h1>{TITLE}</h1><pre>@inproceedings {{123,\n'
            f'author = {{Ada Lovelace and Grace Hopper}},\nyear = {{2007}},\npublisher = {{USENIX Association}},\n'
            f'url = {{{LANDING}}},\n}}\n</pre><a href="http://usenix.org/event/hotsec07/tech/full_papers/sample/sample_html">'
            'Paper (HTML)</a></body></html>').encode()
HTML = (f'<html><body><h1>{TITLE}</h1><p>Ada Lovelace; Grace Hopper</p><h2>1 Introduction</h2><p>'
        + 'Actual supplied synthetic paragraph is retained literally with explicit scope. ' * 12
        + '</p><h2>2 Protocol</h2><pre>receiver.send(resource, content)\nreturn receipt</pre>'
        '<table><tr><th>Principal</th><th>Resource</th></tr><tr><td>Alice</td><td>Selected file</td></tr></table>'
        '<p>A code example is not an executed experiment.</p><h2>3 Conclusions</h2><p>'
        + 'All limitations and counterexamples remain part of the original complete HTML text. ' * 8
        + '</p><h2>References</h2><p>A bibliography cannot establish inspected methods.</p>'
        '<script>fabricated invisible result</script></body></html>').encode()


def collection(monkeypatch, root, *, hint=HINT, metadata=METADATA, body=HTML, status=200,
               content_type="text/html", excluded_identities=None, excluded_urls=None):
    def respond(request):
        assert str(request.url) in {hint["landing_url"], hint["html_url"]}, "HTML must not issue unrelated metadata/PDF discovery"
        if str(request.url) == hint["landing_url"]:
            return httpx.Response(200, content=metadata, headers={"content-type": "text/html"})
        return httpx.Response(status, content=body, headers={"content-type": content_type,
            **({"location": "http://127.0.0.1/private"} if status == 302 else {})})
    requests = mocked(monkeypatch, respond)
    result = literature.collect([hint["title"]], root, pdf_candidates=[], html_candidates=[hint], pdf_reservation_limit=0,
                                excluded_identities=excluded_identities, excluded_urls=excluded_urls)
    return result, requests


def test_complete_original_html_preserves_proof_code_cells_and_pdf_budget(tmp_path, monkeypatch, clock):
    result, requests = collection(monkeypatch, tmp_path)
    source, = result["sources"]
    attempt, = result["html_attempts"]
    assert [str(request.url) for request in requests] == [LANDING, BODY]
    assert result["pdf_reservation_limit"] == 0 and result["pdf_reservations"] == []
    assert source["scope"] == "full_text" and source["document_format"] == "html"
    assert source["publication_type"] == "proceedings-article" and source["publication_version"] == "published"
    assert source["copy_type"] == "scholarly_html" and not source["doi"]
    assert attempt["html_attempted"] is True and "pdf_attempted" not in attempt
    assert attempt["identity"] == literature.scholarly_html_identity(METADATA, HTML, HINT)
    for field, digest in (("raw_path", "sha256"), ("metadata_path", "metadata_sha256"), ("text_path", "text_sha256"),
                          ("discovery_path", "discovery_sha256"), ("identity_path", "identity_sha256")):
        assert hashlib.sha256((tmp_path / source[field]).read_bytes()).hexdigest() == source[digest]
    text = (tmp_path / source["text_path"]).read_text(encoding="utf-8")
    assert "receiver.send(resource, content)\nreturn receipt" in text
    assert "Principal Resource" in text and "Alice Selected file" in text
    assert "bibliography" in text and "fabricated invisible result" not in text
    assert "bibliography" not in text[source["body_range"]["start"]:source["body_range"]["end"]]
    assert all(text[item["start"]:item["end"]] == quote for item, quote in zip(source["excerpt_ranges"], source["excerpts"]))
    assert len(source["section_ranges"]) == 3


@pytest.mark.parametrize("mutation", ["title", "author", "year", "link", "metadata_only", "pdf_disguise"])
def test_rejected_identity_or_nonbody_preserves_failure_without_reading_upgrade(tmp_path, monkeypatch, clock, mutation):
    metadata, body = METADATA, HTML
    if mutation == "title": body = body.replace(TITLE.encode(), b"Different study")
    if mutation == "author": body = body.replace(b"Grace Hopper", b"Unknown Author")
    if mutation == "year": metadata = metadata.replace(b"year = {2007}", b"year = {2008}")
    if mutation == "link": metadata = metadata.replace(b"sample_html", b"other_html")
    if mutation == "metadata_only": body = METADATA
    if mutation == "pdf_disguise": body = b"%PDF-1.7\nnot a scholarly HTML body"
    result, _ = collection(monkeypatch, tmp_path, metadata=metadata, body=body)
    assert not result["sources"] and not result["pdf_reservations"]
    attempt, = result["html_attempts"]
    assert attempt["status"] == "rejected" and attempt["error"] == "ValueError"
    assert (tmp_path / attempt["raw_path"]).read_bytes() == body
    assert json.loads((tmp_path / attempt["identity_path"]).read_text()) == {k:v for k,v in attempt.items() if k not in {"identity_path","identity_sha256"}}


@pytest.mark.parametrize("status,content_type", [(302,"text/html"),(403,"text/html"),(200,"application/pdf")])
def test_redirect_failure_and_pdf_content_type_are_retained_not_replayed(tmp_path, monkeypatch, clock, status, content_type):
    result, requests = collection(monkeypatch, tmp_path, status=status, content_type=content_type)
    assert len(requests) == 2 and not result["sources"] and not result["pdf_reservations"]
    assert result["html_attempts"][0]["status"] == "rejected"
    assert result["html_attempts"][0]["http_status"] == status


@pytest.mark.parametrize("identity", [True, False])
def test_previous_identity_or_url_failure_prevents_new_request(tmp_path, monkeypatch, clock, identity):
    result, requests = collection(monkeypatch, tmp_path,
        excluded_identities=["html:" + BODY] if identity else None, excluded_urls=None if identity else [BODY])
    assert len(requests) == (0 if identity else 1)
    assert not result["sources"] and result["pdf_reservations"] == []


@pytest.mark.parametrize("update", [
    {"html_url":"https://www.usenix.org/system/files/usenixsecurity24-ali.pdf"},
    {"html_url":"https://127.0.0.1/legacy/event/hotsec07/tech/full_papers/sample/sample_html/index.html"},
    {"html_url":BODY + "?token=secret"}, {"html_url":BODY + "#section"},
    {"landing_url":"https://www.usenix.org@evil.test/conference/hotsec-07/sample"},
    {"html_url":"https://www.usenix.org/legacy/event/hotsec07/tech/full_papers/sample/../sample_html/index.html"},
    {"publication_version":"unknown"}, {"publication_type":"technical_report"},
])
def test_candidate_boundary_rejects_before_collection_io(tmp_path, update):
    hint = {**HINT, **update}
    with pytest.raises(ValueError):
        literature.collect([TITLE], tmp_path, html_candidates=[hint], pdf_reservation_limit=0)
    assert not list(tmp_path.iterdir())


def test_exact_query_and_unique_two_body_bound():
    assert literature.normalize_portfolio_html_candidates([HINT], [BODY]) == [HINT]
    for hints, queries in (([HINT],["A generic Electron security search"]),([HINT,HINT],[TITLE]),([HINT]*3,[TITLE])):
        with pytest.raises(ValueError): literature.normalize_portfolio_html_candidates(hints, queries)


def test_private_dns_is_rejected_without_http(tmp_path, monkeypatch, clock):
    requests = mocked(monkeypatch, lambda request: pytest.fail("Private DNS cannot reach HTTP"))
    monkeypatch.setattr(literature.socket,"getaddrinfo",lambda *args,**kwargs:[(2,1,6,"",("127.0.0.1",443))])
    result = literature.collect([TITLE],tmp_path,pdf_candidates=[],html_candidates=[HINT],pdf_reservation_limit=0)
    assert requests == [] and not result["sources"] and result["pdf_reservations"] == []


def test_earlier_author_draft_never_becomes_published_proceedings():
    hint={**HINT,"landing_url":"https://erights.org/elib/capability/duals/",
          "html_url":"https://erights.org/elib/capability/duals/myths.html","year":2003,
          "publication_type":"technical_report","publication_version":"earlier_draft"}
    metadata=f'<html><body><h1>{TITLE}</h1><p>A somewhat earlier <a href="myths.html">html draft</a>.</p></body></html>'.encode()
    body=HTML.replace(b"</h1>",b"</h1><p>Technical Report SRL2003-02 (2003)</p>",1)
    derived=literature.scholarly_html_identity(metadata,body,hint)
    assert derived["publication_version"]=="earlier_draft" and derived["provider"]=="ERights author repository"
    with pytest.raises(ValueError): literature.scholarly_html_identity(metadata,HTML,hint)
    with pytest.raises(ValueError): literature.normalize_portfolio_html_candidates([{**hint,"publication_version":"published"}],[TITLE])


def test_bound_original_and_complete_extraction_are_not_truncated():
    with pytest.raises(ValueError): literature.scholarly_html_identity(METADATA,b"<html>"+b"a"*literature.MAX_JSON_BYTES,HINT)
    with pytest.raises(ValueError): literature.scholarly_html_identity(METADATA,HTML.replace(b"</body>",b"x"*literature.MAX_TEXT_CHARS+b"</body>"),HINT)

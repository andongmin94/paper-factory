import hashlib
from html import escape

import httpx
import pytest

from paper_factory.autonomous import literature
from test_autonomous_literature import clock, mocked, record


DOI = "10.1007/s10664-019-09772-z"
TITLE = "How different are different diff algorithms in Git?"
PDF_URL = "https://arxiv.org/pdf/1902.02467v4"


def feed(*, doi=DOI, title=TITLE, identifier="http://arxiv.org/abs/1902.02467v4", extra=""):
    return ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">'
            '<entry><id>' + escape(identifier) + '</id><title>' + escape(title) + '</title>'
            '<arxiv:doi>' + escape(doi) + '</arxiv:doi>' + extra + '</entry></feed>').encode()


def journal(*, doi=DOI, title=TITLE):
    value = record(doi, abstract="Verified abstract retained independently of optional public full text.")
    value["message"].update(type="journal-article", title=[title])
    return value


def test_exact_journal_identity_recovers_and_hashes_public_full_text(tmp_path, monkeypatch):
    raw_feed = feed(title="How Different Are Different Diff Algorithms in Git")
    raw_pdf = b"%PDF-synthetic"
    text = "[Page 1]\nAbstract\nSummary only.\n1 Introduction\n" + "Introduction and methods. " * 500 + "\n[Page 2]\nDiscussion\n" + "Patch application limitations. " * 500 + "\nReferences\nBibliographic entries."

    def handler(request):
        if request.url.host == "export.arxiv.org":
            assert request.url.path == "/api/query"
            assert dict(request.url.params) == {"search_query": 'ti:"How different are different diff algorithms in Git"', "max_results": "3"}
            return httpx.Response(200, content=raw_feed, headers={"content-type": "application/atom+xml; charset=utf-8"})
        if request.url.host == "arxiv.org":
            assert str(request.url) == PDF_URL
            return httpx.Response(200, content=raw_pdf, headers={"content-type": "application/pdf"})
        return httpx.Response(200, json=journal())

    requests = mocked(monkeypatch, handler)
    monkeypatch.setattr(literature, "_pdf_text", lambda content: text)
    result = literature.collect([DOI], tmp_path, pdf_candidates=[])
    source, = result["sources"]
    assert len(requests) == 3 and not result["warnings"] and source["scope"] == "full_text"
    assert source["arxiv_id"] == "1902.02467v4" and source["url"] == PDF_URL
    for field, digest in (("discovery_path", "discovery_sha256"), ("metadata_path", "metadata_sha256"),
                          ("raw_path", "sha256"), ("text_path", "text_sha256")):
        assert hashlib.sha256((tmp_path / source[field]).read_bytes()).hexdigest() == source[digest]
    assert (tmp_path / source["discovery_path"]).read_bytes() == raw_feed
    assert source["text_chars"] == len(text) and "Only the located literal excerpts" in source["reading_scope"]
    assert source["body_range"] == literature.full_text_body_range(text)
    assert text[source["body_range"]["start"]:source["body_range"]["end"]].strip().startswith("Introduction and methods.")
    assert len(source["excerpts"]) == len(source["excerpt_ranges"]) <= literature.MAX_EXCERPTS
    assert any(location["start"] > len(text) // 2 for location in source["excerpt_ranges"])
    for excerpt, location in zip(source["excerpts"], source["excerpt_ranges"]):
        assert excerpt == text[location["start"]:location["end"]]
        assert len(excerpt) <= literature.MAX_EXCERPT_CHARS


@pytest.mark.parametrize("heading", ["1 Introduction", "INTRODUCTION", "I. INTRODUCTION", "1\nIntroduction", "1 서론"])
def test_body_range_excludes_abstract_and_reference_entries(heading):
    text = "[Page 1]\nAbstract\nAbstract findings.\n" + heading + "\nActual methods and results.\n9 References\nBibliographic claims."
    location = literature.full_text_body_range(text)
    assert location is not None
    assert text[location["start"]:location["end"]].strip() == "Actual methods and results."
    assert "Abstract" not in text[location["start"]:location["end"]]
    assert "Bibliographic" not in text[location["start"]:location["end"]]


@pytest.mark.parametrize("text", ["Abstract\nA finding.\nReferences\nIntroduction to something.",
                                 "Introduction and methods are mentioned in this abstract.",
                                 "Contents\n1 Introduction ........... 2\nOnly abstract available.",
                                 "Introduction\nMethods.\nUnrecognized Bibliographic Section\nReferences data."])
def test_unknown_body_layout_does_not_certify_a_body_quote(text):
    assert literature.full_text_body_range(text) is None


@pytest.mark.parametrize("heading", ["References and Notes", "LITERATURE CITED", "Bibliography", "참고문헌"])
def test_common_bibliography_headings_never_become_body_evidence(heading):
    text = "Introduction\nActual methods.\n" + heading + "\nBibliographic statements."
    location = literature.full_text_body_range(text)
    assert location is not None
    assert text[location["start"]:location["end"]].strip() == "Actual methods."


@pytest.mark.parametrize("raw_feed", [
    feed(doi="10.1234/other"), feed(doi=""), feed(title="A similarly named but different diff study"),
    feed(identifier="https://private.invalid/abs/1902.02467v4"), feed(identifier="https://arxiv.org/abs/1902.02467"),
    feed(extra="<arxiv:doi>10.1234/other</arxiv:doi>"),
    b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>',
])
def test_title_similarity_or_ambiguous_identity_never_upgrades_scope(tmp_path, monkeypatch, raw_feed):
    def handler(request):
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, content=raw_feed, headers={"content-type": "application/atom+xml"})
        assert request.url.host == "api.crossref.org"
        return httpx.Response(200, json=journal())

    requests = mocked(monkeypatch, handler)
    result = literature.collect([DOI], tmp_path, pdf_candidates=[])
    source, = result["sources"]
    assert len(requests) == 2 and source["scope"] == "abstract" and "text_path" not in source
    assert "discovery_path" in source and "arxiv_id" not in source


@pytest.mark.parametrize("content, content_type", [
    (b'<!DOCTYPE feed [<!ENTITY secret "expanded">]><feed/>', "application/atom+xml"),
    ('<!DOCTYPE feed [<!ENTITY secret "expanded">]><feed/>'.encode("utf-16"), "application/atom+xml"),
    (b'<feed><broken>', "application/atom+xml"), (feed(), "text/html"),
    (b"x" * (literature.MAX_JSON_BYTES + 1), "application/atom+xml"),
], ids=["doctype", "utf16-doctype", "malformed-xml", "html-content-type", "over-limit"])
def test_untrusted_discovery_content_preserves_only_original_reading(tmp_path, monkeypatch, content, content_type):
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, content=content, headers={"content-type": content_type})
                      if request.url.host == "export.arxiv.org" else httpx.Response(200, json=journal()))
    result = literature.collect([DOI], tmp_path, pdf_candidates=[])
    source, = result["sources"]
    assert len(requests) == 2 and source["scope"] == "abstract" and "arxiv_id" not in source
    assert any("not upgraded" in warning for warning in result["warnings"])


@pytest.mark.parametrize("url", [
    "https://export.arxiv.org/private", "https://export.arxiv.org:444/api/query",
    "https://user:secret@export.arxiv.org/api/query", "http://export.arxiv.org/api/query",
    "https://api.export.arxiv.org/api/query", "https://export.arxiv.org/api/query#private",
])
def test_discovery_boundary_refuses_unrecognized_authorities_or_paths(monkeypatch, url):
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *args, **kwargs: pytest.fail("Invalid endpoint reached DNS"))
    with pytest.raises(ValueError):
        literature._checked_url(url)


def test_discovery_private_dns_and_redirect_are_refused(tmp_path, monkeypatch):
    requests = mocked(monkeypatch, lambda request: httpx.Response(302, headers={"location": "https://private.invalid/api/query"})
                      if request.url.host == "export.arxiv.org" else httpx.Response(200, json=journal()))
    result = literature.collect([DOI], tmp_path, pdf_candidates=[])
    assert len(requests) == 2 and result["sources"][0]["scope"] == "abstract"
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="non-public"):
        literature._checked_url(literature.ARXIV)


def test_discovery_spacing_has_shared_cancel_and_deadline_budget(tmp_path, monkeypatch, clock):
    starts = []

    def handler(request):
        if request.url.host == "export.arxiv.org":
            starts.append(clock.value)
            return httpx.Response(200, content=b'<feed xmlns="http://www.w3.org/2005/Atom"/>',
                                  headers={"content-type": "application/atom+xml"})
        return httpx.Response(200, json=journal(doi=request.url.path.removeprefix("/works/")))

    mocked(monkeypatch, handler)
    result = literature.collect([DOI, "10.1234/second"], tmp_path, pdf_candidates=[])
    assert len(starts) == 2 and starts[1] - starts[0] >= 3
    assert len(result["sources"]) == 2
    clock.value = 0
    starts.clear()
    result = literature.collect([DOI, "10.1234/second"], tmp_path / "cancelled", cancel=lambda: clock.value >= 1, pdf_candidates=[])
    assert len(starts) == 1 and result["cancelled"] is True
    assert len(result["sources"]) == 2 and all(source["scope"] == "abstract" for source in result["sources"])


def test_full_text_locators_preserve_whitespace_and_late_methods_results_limits():
    text = "[Page 1]\n" + "opening  information\n" * 900
    text += "\n[Page 2]\nMethods\n" + "METHOD details  remain\n" * 500
    text += "\n[Page 3]\nResults\n" + "RESULT findings\n" * 600
    text += "\n[Page 4]\nLimitations\n" + "LIMIT boundary\n" * 700
    excerpts, ranges = literature._full_text_excerpts(text, ["diff patch application"])
    assert any("Methods\n" in value for value in excerpts)
    assert any("Results\n" in value for value in excerpts)
    assert any("Limitations\n" in value for value in excerpts)
    assert [location["start"] for location in ranges] == sorted({location["start"] for location in ranges})
    assert all(value == text[location["start"]:location["end"]] for value, location in zip(excerpts, ranges))
    assert any(location["page_start"] == 4 for location in ranges)
    assert literature.MAX_TEXT_CHARS == 200_000


def test_discovery_does_not_replace_a_known_supported_pdf(tmp_path, monkeypatch):
    value = record("10.21105/joss.01234")
    value["message"]["type"] = "journal-article"

    def handler(request):
        assert request.url.host != "export.arxiv.org"
        if request.url.host == "joss.theoj.org":
            return httpx.Response(200, content=b"%PDF-source", headers={"content-type": "application/pdf"})
        return httpx.Response(200, json=value)

    requests = mocked(monkeypatch, handler)
    monkeypatch.setattr(literature, "_pdf_text", lambda content: "[Page 1]\n" + "Retained open source text. " * 20)
    result = literature.collect(["10.21105/joss.01234"], tmp_path, pdf_candidates=[])
    assert len(requests) == 2 and result["sources"][0]["scope"] == "full_text"

"""Official HTML primary retrieval using synthetic publisher responses, no network."""
import hashlib
import json
from html import escape

import httpx
import pytest

from paper_factory.autonomous import literature
from test_autonomous_literature import clock, mocked


def catalog():
    return b'''<table><tr><th><a name="annexes">Unicode Standard Annexes</a></th></tr>
    <tr><td>UAX</td><td>77</td><td><a href="tr77/">Literal Segmentation Standard</a></td></tr>
    <tr><td>UAX</td><td>78</td><td><a href="tr78/">Literal Normalization Standard</a></td></tr>
    <tr><th><a name="standards">Technical Standards</a></th></tr>
    <tr><td>UTS</td><td>79</td><td><a href="tr79/">Literal Expression Standard</a>
    <a href="tr79/proposed.html">Proposed Update</a></td></tr>
    <tr><th><a name="stabilized">Stabilized Reports</a></th></tr>
    <tr><td>UAX</td><td>80</td><td><a href="tr80/">Withdrawn Literal Standard</a></td></tr></table>'''


def report(number=77, *, version="18.0.0", revision=7, draft=False, kind="UAX", title=None):
    title = title or {77: "Literal Segmentation Standard", 78: "Literal Normalization Standard", 79: "Literal Expression Standard"}[number]
    status = ("This is a draft document; it is not a stable document." if draft else
              "This document has been approved for publication by the Unicode Consortium. This is a stable document.")
    phrase = "Literal Hangul boundary rules preserve Cafe\u0301, 각, and 👩‍💻 as their original code points. " * 5
    return f'''<html><div class="body"><h2 class="uaxtitle">Unicode® {"Standard Annex" if kind == "UAX" else "Technical Standard"} #{number}</h2>
    <h1>{escape(title)}</h1><table class="simple">
    <tr><td>Version</td><td>Unicode {version}</td></tr>
    <tr><td>Editors</td><td>Example Editor (editor@example.invalid)</td></tr>
    <tr><td>Date</td><td>2026-09-01</td></tr>
    <tr><td>This Version</td><td><a href="https://www.unicode.org/reports/tr{number}/tr{number}-{revision}.html">Permanent version</a></td></tr>
    <tr><td>Revision</td><td>{revision}</td></tr></table>
    <h4 class="summary">Summary</h4><p>SUMMARY_ONLY</p>
    <h4 class="status">Status</h4><p>{status}</p>
    <!-- This is a draft document hidden in an obsolete publisher template. -->
    <h4 class="contents">Contents</h4><ul class="toc"><li><a href="#Introduction">1 Introduction TOC_ONLY</a></li>
    <li><a href="#Rules">2 Rules TOC_ONLY</a></li><li><a href="#References">References TOC_ONLY</a></li></ul>
    <h2>1 <a name="Introduction" href="#Introduction">Introduction</a></h2><p>{phrase}</p>
    <h2><a name="Legacy_Rules"></a>2 <a name="Rules" href="#Rules">Rules</a></h2><p>{phrase}</p>
    <table><tr><th>Rule</th><th>Literal definition</th></tr><tr><td>RULE_A</td><td>ᄀ × ᅡ; Cafe\u0301</td></tr></table>
    <script>EXECUTED_SCRIPT_ONLY</script><style>STYLE_ONLY</style>
    <h2><a name="Acknowledgments">Acknowledgments</a></h2><p>ACKNOWLEDGMENTS_ONLY</p>
    <h2><a name="References">References</a></h2><p>REFERENCES_ONLY</p>
    <h2><a name="Modifications">Modifications</a></h2><p>FOOTER_ONLY</p></div></html>'''.encode()


def install(monkeypatch, handler, *, methods=False):
    return mocked(monkeypatch, handler, standard_discovery=True, method_discovery=methods)


def public_response(request, *, alias=None, fixed=None):
    if request.url.host == "www.unicode.org":
        if request.url.path == "/reports/":
            raw = catalog()
        else:
            number = int(request.url.path.split("/")[2][2:])
            raw = (fixed if request.url.path.endswith(".html") else alias) or report(number, kind="UTS" if number == 79 else "UAX")
        return httpx.Response(200, content=raw, headers={"content-type": "text/html; charset=utf-8"})
    if request.url.host == "api.crossref.org":
        return httpx.Response(200, json={"status": "ok", "message": {"items": []}})
    if request.url.host == "export.arxiv.org":
        return httpx.Response(200, content=b'<feed xmlns="http://www.w3.org/2005/Atom"/>', headers={"content-type": "application/atom+xml"})
    pytest.fail("Unexpected provider or script/subresource request")


def test_catalog_derives_only_literal_report_tokens_and_whole_titles():
    matches = literature.discover_unicode_reports(catalog(), ["Unicode UAX77 Hangul boundary rules", "Literal Normalization Standard", "UTS79", "UAX80"])
    assert [entry["report_id"] for entry in matches] == ["UAX77", "UAX78"]
    assert matches[0]["url"] == "https://www.unicode.org/reports/tr77/"
    assert literature.discover_unicode_reports(catalog(), ["boundary methods typography"]) == []
    assert literature.discover_unicode_reports(catalog(), ["UAX77suffix"]) == []
    assert literature.discover_unicode_reports(catalog(), ["UAX80"]) == []
    assert literature._unicode_query_versions(["Unicode v17.0 UAX77", "Unicode 18 UAX77", "Unicode 18.0.0-beta UAX77"]) == {"17.0", "18", "18.0.0-beta"}
    assert literature.discover_unicode_reports(catalog(), ["UTS79"])[0]["title"] == "Literal Expression Standard"
    with pytest.raises(ValueError, match="one matching official alias"):
        literature.discover_unicode_reports(catalog().replace(b'href="tr77/"', b'href="https://127.0.0.1/private"'), ["UAX77"])


def test_identity_and_body_are_derived_from_actual_header_and_anchored_sections():
    raw = report()
    identity = literature.unicode_report_identity(raw, "https://www.unicode.org/reports/tr77/tr77-7.html")
    assert identity["report_id"] == "UAX77" and identity["standard_version"] == "18.0.0"
    assert identity["revision"] == 7 and identity["author_role"] == "editor"
    assert identity["authors"] == ["Example Editor"] and "doi" not in identity
    extracted = literature.unicode_report_text(raw)
    assert extracted["body_range"] == {"start": 0, "end": len(extracted["text"])}
    assert [section["id"] for section in extracted["section_ranges"]] == ["Introduction", "Rules"]
    assert "Cafe\u0301" in extracted["text"] and "Café" not in extracted["text"]
    assert "RULE_A\tᄀ × ᅡ; Cafe\u0301" in extracted["text"]
    assert not any(word in extracted["text"] for word in ["TOC_ONLY", "SUMMARY_ONLY", "REFERENCES_ONLY", "ACKNOWLEDGMENTS_ONLY", "FOOTER_ONLY", "SCRIPT_ONLY", "STYLE_ONLY"])
    for section in extracted["section_ranges"]:
        assert 0 <= section["start"] < section["end"] <= len(extracted["text"])
        assert extracted["text"][section["start"]:section["end"]].startswith(section["heading"])


@pytest.mark.parametrize("url", ["http://www.unicode.org/reports/tr77/", "https://unicode.org/reports/tr77/", "https://www.unicode.org.evil.invalid/reports/tr77/",
    "https://user@www.unicode.org/reports/tr77/", "https://www.unicode.org/reports/tr77/tr78-7.html", "https://www.unicode.org/reports/tr77/proposed.html",
    "https://www.unicode.org/reports/tr77/?token=x", "https://www.unicode.org/reports/tr77/#Introduction"])
def test_official_html_url_boundary_rejects_other_authorities_and_unpinned_paths(url):
    with pytest.raises(ValueError):
        literature._unicode_url(url)


@pytest.mark.parametrize("mutate", [
    lambda raw: raw.replace(b"<td>Revision</td><td>7</td>", b"<td>Revision</td><td>8</td>"),
    lambda raw: raw.replace(b"<td>Date</td><td>2026-09-01</td>", b"<td>Date</td><td>2026-02-30</td>"),
    lambda raw: raw.replace(b"<td>Revision</td><td>7</td>", b"<td>Revision</td><td>7</td></tr><tr><td>Revision</td><td>7</td>"),
    lambda raw: raw.replace(b"<h1>Literal Segmentation Standard</h1>", b"<h1>One title</h1><h1>Another title</h1>"),
    lambda raw: raw.replace(b"<h4 class=\"status\">Status</h4>", b"<h4 class=\"status\">Status</h4><p>This is a proposed draft.</p>"),
])
def test_conflicting_or_ambiguous_headers_cannot_establish_primary_identity(mutate):
    with pytest.raises(ValueError):
        literature.unicode_report_identity(mutate(report()), "https://www.unicode.org/reports/tr77/tr77-7.html")


@pytest.mark.parametrize("mutate", [
    lambda raw: raw.replace(b'name="Rules"', b'name="Introduction"'),
    lambda raw: raw.replace(b'<h2>1 <a name="Introduction" href="#Introduction">Introduction</a></h2>', b''),
    lambda raw: raw.replace(b'<h2><a name="Acknowledgments">Acknowledgments</a></h2>', b'').replace(b'<h2><a name="References">References</a></h2>', b'').replace(b'<h2><a name="Modifications">Modifications</a></h2>', b''),
    lambda raw: raw[:raw.index(b'<h2>1 ')]+b'</div></html>',
])
def test_toc_only_unknown_or_duplicated_section_layouts_do_not_certify_a_body(mutate):
    with pytest.raises(ValueError):
        literature.unicode_report_text(mutate(report()))


def test_collection_retains_primary_raw_text_and_identity_before_other_source_slots(tmp_path, monkeypatch, clock):
    requests = install(monkeypatch, public_response)
    result = literature.collect(["Unicode UAX77 Hangul boundary rules", "UTS79", "other methods"], tmp_path, limit=2, pdf_candidates=[])
    assert len(result["sources"]) == 2 and all(source["scope"] == "full_text" for source in result["sources"])
    assert [request.url.path for request in requests[:5]] == ["/reports/", "/reports/tr77/", "/reports/tr77/tr77-7.html", "/reports/tr79/", "/reports/tr79/tr79-7.html"]
    assert sum(request.url.path == "/reports/" for request in requests) == 1
    for source in result["sources"]:
        assert source["document_format"] == "html" and source["publication_type"] == "technical_standard"
        proof = json.loads((tmp_path / source["identity_path"]).read_bytes())
        assert proof["status"] == "verified" and proof["source_id"] == source["id"]
        assert proof["metadata_url"].endswith("/") and proof["retrieved_url"] == source["url"]
        assert proof["discovery"]["retrieved_url"] == literature.UNICODE_REPORTS
        for field, digest in [("raw_path", "sha256"), ("metadata_path", "metadata_sha256"), ("discovery_path", "discovery_sha256"), ("text_path", "text_sha256"), ("identity_path", "identity_sha256")]:
            assert hashlib.sha256((tmp_path / source[field]).read_bytes()).hexdigest() == source[digest]
        extracted = literature.unicode_report_text((tmp_path / source["raw_path"]).read_bytes())
        assert (tmp_path / source["text_path"]).read_bytes().decode() == extracted["text"]
        assert source["body_range"] == extracted["body_range"] and source["section_ranges"] == extracted["section_ranges"]
        assert 1 <= len(source["excerpts"]) <= 12
        for passage, location in zip(source["excerpts"], source["excerpt_ranges"]):
            assert 80 <= len(passage.strip()) <= 1500 and extracted["text"][location["start"]:location["end"]] == passage
            assert any(section["start"] <= location["start"] < location["end"] <= section["end"] for section in source["section_ranges"])


@pytest.mark.parametrize("alias,fixed,query", [(report(draft=True), None, "UAX77"),
    (report(), report(version="17.0.0"), "UAX77"), (report(), None, "Unicode 17.0.0 UAX77"),
    (report(), None, "Unicode v17.0 UAX77"),
    (report(), report(title="Conflicting fixed title"), "UAX77")], ids=["draft", "fixed-version", "requested-version", "requested-short-version", "fixed-title"])
def test_draft_version_mismatch_or_conflicting_fixed_identity_stays_metadata(tmp_path, monkeypatch, clock, alias, fixed, query):
    requests = install(monkeypatch, lambda request: public_response(request, alias=alias, fixed=fixed))
    result = literature.collect([query], tmp_path, pdf_candidates=[])
    assert result["sources"] and all(source["scope"] == "metadata_only" for source in result["sources"])
    assert not any("identity_path" in source for source in result["sources"])
    assert (tmp_path / result["sources"][0]["metadata_path"]).read_bytes() == alias
    if "17.0" in query or alias == report(draft=True):
        assert not any(request.url.path.endswith(".html") for request in requests)
    assert any(json.loads(path.read_bytes())["status"] == "rejected" for path in (tmp_path / "literature").glob("*-unicode-identity-*.json"))


def test_exact_catalog_queries_preserve_two_method_searches_for_other_queries(tmp_path, monkeypatch, clock):
    requests = install(monkeypatch, public_response, methods=True)
    queries = ["Unicode UAX77 boundary rules", "UTS79 expressions", "ordinary typography methods", "ordinary rendering methods"]
    result = literature.collect(queries, tmp_path, pdf_candidates=[])
    method_queries = [request.url.params["search_query"] for request in requests if request.url.host == "export.arxiv.org"]
    assert len(method_queries) == 2 and all("ordinary" in query for query in method_queries)
    assert len([search for search in result["searches"] if search.get("lookup") == "method"]) == 2


def test_partial_unmatched_title_does_not_skip_method_discovery(tmp_path, monkeypatch, clock):
    requests = install(monkeypatch, public_response, methods=True)
    result = literature.collect(["Literal segmentation boundary methods"], tmp_path, pdf_candidates=[])
    assert not any(source.get("publication_type") == "technical_standard" for source in result["sources"])
    assert any(request.url.host == "export.arxiv.org" for request in requests)


def test_unchanged_explicit_doi_queries_do_not_fetch_a_unicode_catalog(tmp_path, monkeypatch, clock):
    requests = install(monkeypatch, lambda request: httpx.Response(200, json={"status": "ok", "message": {"DOI": "10.1234/example", "title": ["Exact DOI"],
        "author": [{"name": "Example Author"}], "published": {"date-parts": [[2026]]}}}))
    literature.collect(["10.1234/example"], tmp_path, pdf_candidates=[])
    assert len(requests) == 1 and requests[0].url.host == "api.crossref.org"


@pytest.mark.parametrize("failure", ["redirect", "type", "size", "private_dns"])
def test_failed_official_response_never_creates_primary_evidence(tmp_path, monkeypatch, clock, failure):
    def handler(request):
        if request.url.host == "www.unicode.org":
            if failure == "redirect":
                return httpx.Response(302, content=b"completed redirect body", headers={"location": "https://127.0.0.1/private"})
            if failure == "type":
                return httpx.Response(200, content=catalog(), headers={"content-type": "application/json"})
            return httpx.Response(200, content=b"too large", headers={"content-length": str(literature.MAX_JSON_BYTES+1)})
        return public_response(request)
    requests = install(monkeypatch, handler)
    if failure == "private_dns":
        monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))])
    result = literature.collect(["UAX77"], tmp_path, pdf_candidates=[])
    assert not any(source.get("scope") == "full_text" for source in result["sources"])
    assert not any(request.url.host == "127.0.0.1" for request in requests)
    if failure == "redirect":
        assert any(path.read_bytes() == b"completed redirect body" for path in (tmp_path / "literature").glob("*.html"))
    if failure == "private_dns":
        assert requests == []


@pytest.mark.parametrize("stop", ["cancel", "deadline", "cooldown"])
def test_shared_budget_preserves_completed_html_without_primary_upgrade(tmp_path, monkeypatch, clock, stop):
    cancelled = False
    def handler(request):
        nonlocal cancelled
        if request.url.host == "www.unicode.org" and request.url.path == "/reports/tr77/":
            if stop == "cancel":
                cancelled = True
            elif stop == "deadline":
                clock.value = 91
            else:
                return httpx.Response(429, content=b"completed rate-limited body", headers={"retry-after": "91", "content-type": "text/html"})
        return public_response(request)
    install(monkeypatch, handler)
    result = literature.collect(["UAX77"], tmp_path, pdf_candidates=[], cancel=lambda: cancelled)
    assert result.get({"cancel": "cancelled", "deadline": "timed_out", "cooldown": "rate_limited"}[stop]) is True
    assert not any(source.get("scope") == "full_text" for source in result["sources"])
    assert any(path.read_bytes() == catalog() for path in (tmp_path / "literature").glob("*.html"))
    if stop == "cooldown":
        assert any(path.read_bytes() == b"completed rate-limited body" for path in (tmp_path / "literature").glob("*.html"))

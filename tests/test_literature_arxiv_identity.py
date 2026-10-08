"""Explicit preprint identity and the shared bounded collector, without live HTTP."""
import hashlib
from html import escape

import httpx
import pytest

from paper_factory.autonomous import literature
from test_autonomous_literature import clock, mocked, record


ID = "1311.3903v1"
TITLE = "A Categorical Theory of Patches"
PDF = b"%PDF-synthetic-arxiv"
TEXT = "[Page 1]\nAbstract\nA summary only.\n1 Introduction\n" + "Actual patch application methods. " * 120 + "\nReferences\nUninspected bibliography."


def feed(*, identifier=ID, title=TITLE, published="2013-11-13T20:19:47Z", updated="2013-11-13T20:19:47Z",
         authors=("Samuel Mimram", "Cinzia Di Giusto"), summary="A retrieved literal abstract explaining patch application semantics.", extra=""):
    entry = ("<entry><id>http://arxiv.org/abs/" + escape(identifier) + "</id><title>" + escape(title) + "</title>"
             "<published>" + escape(published) + "</published><updated>" + escape(updated) + "</updated>"
             + "".join("<author><name>" + escape(name) + "</name></author>" for name in authors)
             + ("<summary>" + escape(summary) + "</summary>" if summary is not None else "") + extra + "</entry>")
    return ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">' + entry + '</feed>').encode()


def direct(monkeypatch, content=None, *, pdf_status=200):
    def handler(request):
        assert request.url.host != "api.crossref.org", "An explicit arXiv identifier must not depend on Crossref"
        if request.url.host == "export.arxiv.org":
            assert request.url.path == "/api/query" and request.url.params["max_results"] == "1"
            assert set(request.url.params) == {"id_list", "max_results"}
            return httpx.Response(200, content=content if content is not None else feed(), headers={"content-type": "application/atom+xml; charset=utf-8"})
        assert str(request.url) == "https://arxiv.org/pdf/" + ID
        return httpx.Response(pdf_status, content=PDF, headers={"content-type": "application/pdf"})
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT)
    return mocked(monkeypatch, handler)


@pytest.mark.parametrize("query", ["arxiv:1311.3903", "arXiv: 1311.3903v1", "10.48550/arXiv.1311.3903",
                                    "DOI: 10.48550/arxiv.1311.3903v1", "https://doi.org/10.48550/arXiv.1311.3903"])
def test_explicit_arxiv_resolves_actual_version_and_retains_all_evidence(tmp_path, monkeypatch, query):
    raw = feed(extra="<arxiv:doi>10.1016/j.entcs.2013.09.018</arxiv:doi>")
    requests = direct(monkeypatch, raw)
    result = literature.collect([query], tmp_path, limit=1, pdf_candidates=[])
    source, = result["sources"]
    assert len(requests) == 2 and not result["warnings"]
    assert source["id"] == "source-" + hashlib.sha256(("arxiv:" + ID).encode()).hexdigest()[:20]
    assert source["arxiv_id"] == ID and source["scope"] == "full_text" and source["publication_type"] == "preprint"
    assert "doi" not in source and source["authors"] == ["Samuel Mimram", "Cinzia Di Giusto"] and source["year"] == 2013
    assert source["title"] == TITLE and source["published"] == source["updated"] == "2013-11-13T20:19:47Z"
    assert source["body_range"] == literature.full_text_body_range(TEXT) and source["text_chars"] == len(TEXT)
    assert "Only the located literal excerpts were inspected" in source["reading_scope"]
    for path_key, hash_key in (("metadata_path", "metadata_sha256"), ("raw_path", "sha256"), ("text_path", "text_sha256")):
        assert hashlib.sha256((tmp_path / source[path_key]).read_bytes()).hexdigest() == source[hash_key]
    assert (tmp_path / source["metadata_path"]).read_bytes() == raw
    assert (tmp_path / source["raw_path"]).read_bytes() == PDF
    for passage, location in zip(source["excerpts"], source["excerpt_ranges"]):
        assert passage == TEXT[location["start"]:location["end"]]
    search, = result["searches"]
    assert search["provider"] == "arXiv" and search["lookup"] == "arxiv_id" and search["status"] == "succeeded"
    assert search["resolved_ids"] == [source["id"]] and (tmp_path / search["raw_path"]).read_bytes() == raw


def test_alias_queries_share_one_canonical_source_and_original_requests(tmp_path, monkeypatch):
    requests = direct(monkeypatch)
    queries = ["arxiv:1311.3903", "10.48550/arxiv.1311.3903"]
    result = literature.collect(queries, tmp_path, pdf_candidates=[])
    source, = result["sources"]
    assert len(requests) == 2 and source["queries"] == queries
    assert all(search["resolved_ids"] == [source["id"]] for search in result["searches"])
    assert len({search["raw_path"] for search in result["searches"]}) == 2


def test_direct_candidate_precedes_abstracts_when_source_limit_is_full(tmp_path, monkeypatch):
    def handler(request):
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, content=feed(), headers={"content-type": "application/atom+xml"})
        if request.url.host == "arxiv.org":
            return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
        assert request.url.path == "/works"
        return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/unrelated"}]}})
    requests = mocked(monkeypatch, handler)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT)
    result = literature.collect(["broad patch application", "arxiv:1311.3903"], tmp_path, limit=1, pdf_candidates=[])
    source, = result["sources"]
    assert source["arxiv_id"] == ID and source["scope"] == "full_text"
    assert requests[0].url.host == "export.arxiv.org" and len(requests) == 3
    assert {search["query"] for search in result["searches"] if search["attempted"]} == {"broad patch application", "arxiv:1311.3903"}


@pytest.mark.parametrize("query", ["arxiv:other", "arxiv:1311.3903v0", "arxiv:1311.3903v-1", "arxiv:1313.3903",
                                    "arxiv:https://private.invalid/paper", "arxiv:1311.3903?token=private",
                                    "arxiv:1311.3903 extra", "10.48550/arxiv.1311.3903/private", "10.48550/arxiv.1311.3903v0"])
def test_malformed_explicit_identifiers_never_reach_http(tmp_path, monkeypatch, query):
    requests = mocked(monkeypatch, lambda request: pytest.fail("Malformed identity reached HTTP"))
    result = literature.collect([query], tmp_path, pdf_candidates=[])
    assert not requests and not result["sources"] and result["searches"][0]["error"] == "ValueError"


@pytest.mark.parametrize("raw", [
    feed(identifier="1311.3904v1"), feed(identifier="1311.3903"), feed(identifier="1311.3903v2"),
    feed(title=""), feed(authors=()), feed(authors=("",)), feed(published="bad"), feed(updated="2013-02-31T20:19:47Z"),
    feed(updated="2012-11-13T20:19:47Z"), feed(extra="<id>http://arxiv.org/abs/1311.3903v1</id>"),
    feed(extra="<title>Duplicate title</title>"), feed(extra="<published>2013-11-13T20:19:47Z</published>"),
    feed(extra="<updated>2013-11-13T20:19:47Z</updated>"), feed(extra="<author><name>First</name><name>Second</name></author>"),
    feed(extra="<summary>Duplicate abstract</summary>"), feed().replace(b"</feed>", b"<entry>" + feed().split(b"<entry>", 1)[1]),
    b'<feed xmlns="http://www.w3.org/2005/Atom"/>',
], ids=["different-id", "unversioned", "different-version", "empty-title", "no-authors", "empty-author", "bad-published", "bad-updated",
        "backwards-date", "duplicate-id", "duplicate-title", "duplicate-published", "duplicate-updated", "duplicate-author-name",
        "duplicate-abstract", "duplicate-entry", "empty-feed"])
def test_missing_ambiguous_or_wrong_version_metadata_cannot_become_source(tmp_path, monkeypatch, raw):
    requests = direct(monkeypatch, raw)
    result = literature.collect(["arxiv:1311.3903v1"], tmp_path, pdf_candidates=[])
    assert len(requests) == 1 and not result["sources"] and result["searches"][0]["status"] == "failed"
    search = result["searches"][0]
    assert (tmp_path / search["raw_path"]).read_bytes() == raw
    assert hashlib.sha256(raw).hexdigest() == search["sha256"]


@pytest.mark.parametrize("raw", [b'<!DOCTYPE feed [<!ENTITY hidden "expanded">]><feed/>',
                                 '<!DOCTYPE feed [<!ENTITY hidden "expanded">]><feed/>'.encode("utf-16"),
                                 feed().decode().encode("utf-16"), b"<feed><broken>", b"x" * (literature.MAX_JSON_BYTES + 1)],
                         ids=["doctype", "utf16-doctype", "utf16", "invalid-xml", "oversize"])
def test_untrusted_xml_is_refused_without_a_pdf_request(tmp_path, monkeypatch, raw):
    requests = direct(monkeypatch, raw)
    result = literature.collect(["arxiv:1311.3903"], tmp_path, pdf_candidates=[])
    assert len(requests) == 1 and not result["sources"] and result["searches"][0]["status"] == "failed"


def test_missing_optional_abstract_or_journal_doi_still_allows_actual_body(tmp_path, monkeypatch):
    direct(monkeypatch, feed(summary=None))
    result = literature.collect(["arxiv:1311.3903"], tmp_path, pdf_candidates=[])
    source, = result["sources"]
    assert source["scope"] == "full_text" and "doi" not in source


@pytest.mark.parametrize("failure", ["http", "extraction", "deadline", "cancel"])
def test_failed_full_text_preserves_verified_preprint_metadata(tmp_path, monkeypatch, clock, failure):
    def handler(request):
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, content=feed(), headers={"content-type": "application/atom+xml"})
        assert request.url.host == "arxiv.org"
        if failure == "deadline":
            clock.value = 73
        elif failure == "cancel":
            clock.value = 1
        return httpx.Response(404 if failure == "http" else 200, content=PDF, headers={"content-type": "application/pdf"})
    mocked(monkeypatch, handler)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: (_ for _ in ()).throw(ValueError("Extraction refused")) if failure == "extraction" else pytest.fail("Failed/cancelled/deadline PDF reached extraction"))
    result = literature.collect(["arxiv:1311.3903"], tmp_path, cancel=lambda: failure == "cancel" and clock.value >= 1, pdf_candidates=[])
    source, = result["sources"]
    assert source["scope"] == "abstract" and source["arxiv_id"] == ID and "text_path" not in source
    assert source["raw_path"] == source["metadata_path"] and source["sha256"] == hashlib.sha256(feed()).hexdigest()
    if failure == "deadline":
        assert result["timed_out"] is True
    elif failure == "cancel":
        assert result["cancelled"] is True


def test_shared_arxiv_spacing_and_cancellation_before_second_request(tmp_path, monkeypatch, clock):
    starts = []
    def handler(request):
        if request.url.host == "export.arxiv.org":
            starts.append(clock.value)
            identifier = request.url.params["id_list"]
            return httpx.Response(200, content=feed(identifier=identifier + "v1"), headers={"content-type": "application/atom+xml"})
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    mocked(monkeypatch, handler)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT)
    result = literature.collect(["arxiv:1311.3903", "arxiv:2401.12345"], tmp_path, pdf_candidates=[])
    assert len(result["sources"]) == 2 and starts[1] - starts[0] >= 3
    clock.value = 0
    starts.clear()
    result = literature.collect(["arxiv:1311.3903", "arxiv:2401.12345"], tmp_path / "cancelled", cancel=lambda: clock.value >= 1, pdf_candidates=[])
    assert len(starts) == 1 and result["cancelled"] is True
    assert result["searches"][1]["attempted"] is False and result["searches"][1]["status"] == "not_attempted"
    first = result["searches"][0]
    assert hashlib.sha256((tmp_path / "cancelled" / first["raw_path"]).read_bytes()).hexdigest() == first["sha256"]


def test_legacy_arxiv_identifier_and_distinct_versions(tmp_path, monkeypatch):
    def handler(request):
        if request.url.host == "export.arxiv.org":
            identifier = request.url.params["id_list"]
            return httpx.Response(200, content=feed(identifier=identifier), headers={"content-type": "application/atom+xml"})
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    mocked(monkeypatch, handler)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT)
    result = literature.collect(["arxiv:cs/0211001v1", "arxiv:cs/0211001v2"], tmp_path, pdf_candidates=[])
    assert {source["arxiv_id"] for source in result["sources"]} == {"cs/0211001v1", "cs/0211001v2"}
    assert len({source["id"] for source in result["sources"]}) == 2


@pytest.mark.parametrize("heading", ["1 Background", "1 Background and Terminologies", "I. Background", "I Background and Terminologies",
                                    "1\nBackground", "I.\nBackground and Terminologies"])
def test_explicit_first_background_section_has_literal_body_offsets(heading):
    text = "[Page 1]\nAbstract\nAbstract-only findings.\n" + heading + "\nActual theory.\n2 Introduction\nFurther methods.\nReferences\nBibliographic claims."
    before = text.encode()
    location = literature.full_text_body_range(text)
    assert text[location["start"]:location["end"]].strip() == "Actual theory.\n2 Introduction\nFurther methods."
    assert "Abstract-only" not in text[location["start"]:location["end"]]
    assert text.find("Bibliographic claims.") > location["end"]
    assert text.encode() == before


@pytest.mark.parametrize("heading", ["Background", "Background and Terminologies", "2 Background", "II Background", "1.1 Background",
                                    "The abstract discusses 1 Background and Terminologies", "1 Background and Terminologies .......... 2"])
def test_background_mentions_or_later_sections_do_not_certify_a_body(heading):
    text = "Abstract\nAbstract-only findings.\n" + heading + "\nMore abstract text.\nReferences\nBibliographic claims."
    assert literature.full_text_body_range(text) is None


def test_earlier_introduction_remains_the_body_start():
    text = "Introduction\nActual methods.\n1 Background and Terminologies\nLater theory.\nReferences\nBibliographic claims."
    location = literature.full_text_body_range(text)
    assert text[location["start"]:location["end"]].strip().startswith("Actual methods.")


def test_first_background_requires_a_recognizable_bibliography():
    assert literature.full_text_body_range("1 Background and Terminologies\nActual theory.\nWorks consulted\nBibliographic claims.") is None


def test_repeated_methods_and_results_include_late_sections_without_abstract_or_references():
    text = "Abstract\nresults of an abstract are not a section heading.\n1 Introduction\n" + "Context  remains.\n" * 150
    for number in range(2, 14):
        text += f"\n{number}.1 Analysis Design\n" + f"Method {number} details  remain literal.\n" * 100
        text += f"\n{number}.2 Results\n" + f"Result {number} evidence  remains literal.\n" * 100
    text += "\nReferences\nresults of unrelated bibliographic claims.\n" + "Reference-only evidence.\n" * 100
    digest = hashlib.sha256(text.encode()).hexdigest()
    passages, ranges = literature._full_text_excerpts(text, ["arxiv:2401.12345"])
    assert any("2.1 Analysis Design\n" in passage for passage in passages)
    assert any("2.2 Results\n" in passage for passage in passages)
    assert any("13.1 Analysis Design\n" in passage for passage in passages)
    assert any("13.2 Results\n" in passage for passage in passages)
    body = literature.full_text_body_range(text)
    assert all(body["start"] <= item["start"] < item["end"] <= body["end"] for item in ranges)
    assert all("abstract are not" not in passage and "Reference-only" not in passage for passage in passages)
    assert len(passages) <= 12 and all(len(passage) <= 1500 for passage in passages)
    assert all(passage == text[item["start"]:item["end"]] for passage, item in zip(passages, ranges))
    assert hashlib.sha256(text.encode()).hexdigest() == digest


def test_identifier_and_zero_score_queries_do_not_frontload_body_sampling():
    text = "Abstract\nSummary.\n1 Introduction\n" + "arxiv doi identifiers.\n" * 120 + "Literal body information.\n" * 2000 + "\nReferences\nBibliography."
    expected = literature._full_text_excerpts(text, [])
    for queries in (["arxiv:2401.12345"], ["10.48550/arxiv.2401.12345"], ["10.1007/BF01840446"], ["absentcounterfactualterm"]):
        assert literature._full_text_excerpts(text, queries) == expected
    _, ranges = expected
    body = literature.full_text_body_range(text)
    assert any(item["start"] > body["start"] + (body["end"] - body["start"]) * 0.7 for item in ranges)


def test_positive_semantic_query_is_located_inside_body_not_keyword_heavy_references():
    text = "Abstract\nSummary.\n1 Introduction\n" + "Ordinary body words.\n" * 800
    text += "Validated counterfactualvalidity evidence  stays literal.\n" + "Later body words.\n" * 1600
    text += "\nReferences\n" + "counterfactualvalidity bibliography.\n" * 100
    passages, ranges = literature._full_text_excerpts(text, ["counterfactualvalidity"])
    assert any("Validated counterfactualvalidity" in passage for passage in passages)
    body = literature.full_text_body_range(text)
    assert all(body["start"] <= item["start"] < item["end"] <= body["end"] for item in ranges)
    assert all("counterfactualvalidity bibliography" not in passage for passage in passages)


def test_unknown_layout_keeps_literal_reading_without_certifying_body():
    text = "[Page 1]\nUnrecognized opening\n" + "Literal theory  details.\n" * 1000 + "\n[Page 2]\nResults\n" + "Late findings.\n" * 300
    passages, ranges = literature._full_text_excerpts(text, [])
    assert literature.full_text_body_range(text) is None
    assert any("Results\n" in passage for passage in passages)
    assert all(passage == text[item["start"]:item["end"]] for passage, item in zip(passages, ranges))
    assert len(passages) <= 12 and all(len(passage) <= 1500 for passage in passages)


def title_feed(records=None, *, total=None):
    records = [feed()] if records is None else records
    entries = b"".join(b"<entry>" + raw.split(b"<entry>", 1)[1].split(b"</entry>", 1)[0] + b"</entry>" for raw in records)
    count = str(len(records) if total is None else total).encode()
    return (b'<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom" '
            b'xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"><opensearch:totalResults>' + count +
            b'</opensearch:totalResults>' + entries + b'</feed>')


def title_transport(monkeypatch, raw=None, *, exact_only=False):
    def handler(request):
        if request.url.host == "export.arxiv.org":
            assert set(request.url.params) == {"search_query", "max_results"} and request.url.params["max_results"] == "3"
            return httpx.Response(200, content=title_feed() if raw is None else raw, headers={"content-type": "application/atom+xml"})
        if request.url.host == "arxiv.org":
            assert str(request.url) == "https://arxiv.org/pdf/" + ID
            return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
        assert not exact_only, "A uniquely resolved title must not substitute a Crossref bibliographic candidate"
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/fallback"}]}})
        return httpx.Response(200, json=record("10.1234/fallback", abstract="A separately verified Crossref abstract retained without an arXiv identity claim."))
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT)
    return mocked(monkeypatch, handler, title_discovery=True)


@pytest.mark.parametrize("query", [TITLE, TITLE.upper(), "A Categorical Theory of Patches!"])
def test_unique_normalized_full_title_recovers_preprint_without_guessing_doi(tmp_path, monkeypatch, query):
    raw = title_feed()
    requests = title_transport(monkeypatch, raw, exact_only=True)
    result = literature.collect([query], tmp_path, limit=1, pdf_candidates=[])
    source, = result["sources"]
    assert len(requests) == 2 and not result["warnings"]
    assert source["scope"] == "full_text" and source["arxiv_id"] == ID and "doi" not in source
    assert source["id"] == "source-" + hashlib.sha256(("arxiv:" + ID).encode()).hexdigest()[:20]
    search, = result["searches"]
    assert search["provider"] == "arXiv" and search["lookup"] == "exact_title" and search["resolved_ids"] == [source["id"]]
    assert (tmp_path / search["raw_path"]).read_bytes() == (tmp_path / source["metadata_path"]).read_bytes() == raw
    assert hashlib.sha256(raw).hexdigest() == search["sha256"] == source["metadata_sha256"]
    assert all(passage == TEXT[location["start"]:location["end"]] for passage, location in zip(source["excerpts"], source["excerpt_ranges"]))


def test_complete_title_feed_can_contain_one_exact_and_one_similar_candidate(tmp_path, monkeypatch):
    requests = title_transport(monkeypatch, title_feed([feed(), feed(identifier="2401.12345v2", title=TITLE + " Extended")]), exact_only=True)
    result = literature.collect([TITLE], tmp_path, pdf_candidates=[])
    source, = result["sources"]
    assert len(requests) == 2 and source["arxiv_id"] == ID and source["scope"] == "full_text"


@pytest.mark.parametrize("raw", [title_feed([feed(), feed(identifier="2401.12345v2")]), title_feed([feed(), feed()]),
                                 title_feed(total=4), title_feed(total=0), title_feed(total="bad"),
                                 title_feed().replace(b'<opensearch:totalResults>1</opensearch:totalResults>', b''),
                                 title_feed().replace(b'</feed>', b'<opensearch:totalResults>1</opensearch:totalResults></feed>'),
                                 title_feed([feed(identifier="1311.3903")]), title_feed([feed(authors=())]),
                                 title_feed([feed(published="bad")]), title_feed([feed(extra="<title>Duplicate title</title>")]),
                                 title_feed([feed(), feed(identifier="2401.12345v2").replace(escape(TITLE).encode(), b'<span>Hidden title</span>')]),
                                 title_feed([feed().replace(escape(TITLE).encode(), escape(TITLE).encode() + b'<span> Hidden suffix</span>')]),
                                 title_feed([feed(), feed(identifier="2401.12345v2", title="   ")])],
                         ids=["ambiguous-title", "duplicate-entry", "truncated-feed", "inconsistent-total", "bad-total", "missing-total",
                              "duplicate-total", "unversioned", "missing-author", "bad-date", "duplicate-title-field",
                              "nonmatching-nested-title", "matching-nested-title", "empty-neighbor-title"])
def test_ambiguous_truncated_or_invalid_title_retains_attempt_and_separate_crossref_identity(tmp_path, monkeypatch, raw):
    requests = title_transport(monkeypatch, raw)
    result = literature.collect([TITLE], tmp_path, pdf_candidates=[])
    source, = result["sources"]
    assert len(requests) == 3 and source["doi"] == "10.1234/fallback" and "arxiv_id" not in source
    arxiv_search, = [search for search in result["searches"] if search["provider"] == "arXiv"]
    assert arxiv_search["status"] == "failed" and arxiv_search["error"] == "ValueError" and not arxiv_search["resolved_ids"]
    assert "identifier" in arxiv_search["note"]
    assert (tmp_path / arxiv_search["raw_path"]).read_bytes() == raw
    assert hashlib.sha256(raw).hexdigest() == arxiv_search["sha256"]
    crossref_search, = [search for search in result["searches"] if search["provider"] == "Crossref"]
    assert crossref_search["status"] == "succeeded" and crossref_search["resolved_ids"] == [source["id"]]


@pytest.mark.parametrize("raw", [title_feed([]), title_feed([feed(title=TITLE + " Extended")])], ids=["empty-feed", "similar-title"])
def test_no_exact_title_preserves_negative_search_without_claiming_literature_absence(tmp_path, monkeypatch, raw):
    title_transport(monkeypatch, raw)
    result = literature.collect([TITLE], tmp_path, pdf_candidates=[])
    source, = result["sources"]
    arxiv_search, = [search for search in result["searches"] if search["provider"] == "arXiv"]
    assert arxiv_search["status"] == "succeeded" and not arxiv_search["resolved_ids"]
    assert "not evidence" in arxiv_search["note"] and (tmp_path / arxiv_search["raw_path"]).read_bytes() == raw
    assert "arxiv_id" not in source and source["scope"] == "abstract"


@pytest.mark.parametrize("raw", [b'<!DOCTYPE feed [<!ENTITY hidden "expanded">]><feed/>', title_feed().decode().encode("utf-16")],
                         ids=["doctype", "utf16"])
def test_unsafe_title_xml_never_promotes_a_preprint(tmp_path, monkeypatch, raw):
    title_transport(monkeypatch, raw)
    result = literature.collect([TITLE], tmp_path, pdf_candidates=[])
    assert all("arxiv_id" not in source for source in result["sources"])
    assert any(search["provider"] == "arXiv" and search["status"] == "failed" for search in result["searches"])


def test_exact_title_is_a_single_sanitized_phrase_not_raw_lucene_operators(tmp_path, monkeypatch):
    query = 'A "Precise" Study: (Patches AND Tests)'
    requests = title_transport(monkeypatch, title_feed([feed(title=query)]), exact_only=True)
    result = literature.collect([query], tmp_path, pdf_candidates=[])
    assert result["sources"][0]["scope"] == "full_text"
    assert requests[0].url.params["search_query"] == 'ti:"A Precise Study Patches AND Tests"'


def test_exact_title_candidate_precedes_earlier_generic_abstracts(tmp_path, monkeypatch, clock):
    def handler(request):
        if request.url.host == "export.arxiv.org":
            matched = TITLE in request.url.params["search_query"]
            return httpx.Response(200, content=title_feed() if matched else title_feed([]), headers={"content-type": "application/atom+xml"})
        if request.url.host == "arxiv.org":
            return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
        assert request.url.path == "/works", "Generic DOI candidates should not fill the limit ahead of the exact preprint"
        return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/noise"}]}})
    mocked(monkeypatch, handler, title_discovery=True)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT)
    result = literature.collect(["generic patch methods", "other unrelated query", TITLE], tmp_path, limit=1, pdf_candidates=[])
    source, = result["sources"]
    assert source["arxiv_id"] == ID and source["scope"] == "full_text"
    assert len([search for search in result["searches"] if search["provider"] == "arXiv"]) == 3


def test_title_lookup_uses_shared_spacing_and_preserves_cancelled_attempt(tmp_path, monkeypatch, clock):
    starts = []
    def handler(request):
        assert request.url.host == "export.arxiv.org"
        starts.append(clock.value)
        return httpx.Response(200, content=title_feed(), headers={"content-type": "application/atom+xml"})
    mocked(monkeypatch, handler, title_discovery=True)
    result = literature.collect([TITLE, TITLE.upper()], tmp_path, cancel=lambda: clock.value >= 1, pdf_candidates=[])
    assert starts == [0] and result["cancelled"] is True
    first, second = result["searches"]
    assert first["status"] == "succeeded" and (tmp_path / first["raw_path"]).read_bytes() == title_feed()
    assert second["provider"] == "arXiv" and second["status"] == "not_attempted" and second["attempted"] is False


def test_title_lookup_long_rate_limit_stops_before_crossref_fallback(tmp_path, monkeypatch, clock):
    requests = mocked(monkeypatch, lambda request: httpx.Response(429, headers={"retry-after": "11"}), title_discovery=True)
    result = literature.collect([TITLE], tmp_path, pdf_candidates=[])
    assert len(requests) == 1 and result["rate_limited"] is True and not result["sources"]
    search, = result["searches"]
    assert search["provider"] == "arXiv" and search["http_status"] == 429


def test_title_lookup_retry_uses_same_three_second_provider_budget(tmp_path, monkeypatch, clock):
    starts = []
    def handler(request):
        if request.url.host == "export.arxiv.org":
            starts.append(clock.value)
            if len(starts) == 1:
                return httpx.Response(429, headers={"retry-after": "1"})
            return httpx.Response(200, content=title_feed(), headers={"content-type": "application/atom+xml"})
        assert request.url.host == "arxiv.org"
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    mocked(monkeypatch, handler, title_discovery=True)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT)
    result = literature.collect([TITLE], tmp_path, pdf_candidates=[])
    assert len(starts) == 2 and starts[1] - starts[0] >= 3
    assert result["sources"][0]["scope"] == "full_text" and not result.get("rate_limited")


def test_title_pdf_deadline_preserves_original_identity_without_dispatching_worker(tmp_path, monkeypatch, clock):
    raw = title_feed()
    def handler(request):
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, content=raw, headers={"content-type": "application/atom+xml"})
        assert request.url.host == "arxiv.org"
        clock.value = 73
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    mocked(monkeypatch, handler, title_discovery=True)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: pytest.fail("Insufficient extraction/cleanup budget started worker"))
    result = literature.collect([TITLE], tmp_path, pdf_candidates=[])
    source, = result["sources"]
    assert result["timed_out"] is True and source["scope"] == "abstract" and "text_path" not in source
    assert source["arxiv_id"] == ID and (tmp_path / source["metadata_path"]).read_bytes() == raw


def test_title_and_explicit_id_aliases_keep_one_fixed_version_and_every_raw_search(tmp_path, monkeypatch, clock):
    def handler(request):
        if request.url.host == "export.arxiv.org":
            content = feed() if "id_list" in request.url.params else title_feed()
            return httpx.Response(200, content=content, headers={"content-type": "application/atom+xml"})
        assert request.url.host == "arxiv.org"
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    requests = mocked(monkeypatch, handler, title_discovery=True)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: TEXT)
    result = literature.collect([TITLE, "arxiv:1311.3903v1", "10.48550/arxiv.1311.3903v1"], tmp_path, pdf_candidates=[])
    source, = result["sources"]
    assert len(requests) == 3 and source["arxiv_id"] == ID
    assert len(source["queries"]) == 3 and len(result["searches"]) == 3
    assert all(search["resolved_ids"] == [source["id"]] for search in result["searches"])
    assert len({search["raw_path"] for search in result["searches"]}) == 3
    assert all(hashlib.sha256((tmp_path / search["raw_path"]).read_bytes()).hexdigest() == search["sha256"] for search in result["searches"])

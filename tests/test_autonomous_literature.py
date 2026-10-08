import hashlib
import io
import json
import os
import subprocess
from email.utils import formatdate
from html import escape
from types import SimpleNamespace

import httpx
import pytest

from paper_factory.autonomous import literature
from paper_factory import workspace


def symlink(path, target, *, directory=False):
    try:
        path.symlink_to(target, target_is_directory=directory)
    except OSError as error:
        if os.name == "nt" and error.winerror == 1314:
            pytest.skip("Creating symbolic links requires Windows developer mode or elevation")
        raise


def record(doi="10.1234/test", *, abstract=None, links=None):
    message = {"DOI": doi, "title": ["Verified record title"],
               "author": [{"given": "Ada", "family": "Lovelace"}],
               "published": {"date-parts": [[2024]]}}
    if abstract is not None:
        message["abstract"] = abstract
    if links is not None:
        message["link"] = links
    return {"status": "ok", "message": message}


def mocked(monkeypatch, handler, *, title_discovery=False, method_discovery=False):
    # Most fixtures target Crossref or explicit-ID/discovery behavior. Exact-title
    # provider tests opt into the complete multi-provider flow separately.
    if not title_discovery:
        monkeypatch.setattr(literature, "_arxiv_title_lookup", lambda *args, **kwargs: None)
    if not method_discovery:
        monkeypatch.setattr(literature, "MAX_METHOD_CANDIDATES", 0)
    original = httpx.Client
    requests = []

    def transport(request):
        requests.append(request)
        return handler(request)

    monkeypatch.setattr(literature.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs))
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("8.8.8.8", 443))])
    return requests


@pytest.fixture
def clock(monkeypatch):
    clock = SimpleNamespace(value=0.0, epoch=1_700_000_000)

    def advance(seconds):
        clock.value += seconds

    monkeypatch.setattr(literature.time, "monotonic", lambda: clock.value)
    monkeypatch.setattr(literature.time, "time", lambda: clock.epoch + clock.value)
    monkeypatch.setattr(literature.time, "sleep", advance)
    return clock


def test_collection_paces_search_and_doi_requests(tmp_path, monkeypatch, clock):
    starts = []

    def handler(request):
        starts.append(clock.value)
        if request.url.path == "/works":
            doi = "10.1234/" + request.url.params["query.bibliographic"]
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": doi}]}})
        doi = "10.1234/" + request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=record(doi, abstract="A verified literal passage."))

    mocked(monkeypatch, handler)
    result = literature.collect(["first", "second"], tmp_path, pdf_candidates=[])
    assert len(result["sources"]) == 2 and len(starts) == 4
    assert all(right - left >= 0.5 - 1e-9 for left, right in zip(starts, starts[1:]))


@pytest.mark.parametrize("retry_after, expected_delay", [(None, 2), ("1", 1), ("date", 3)])
def test_429_retries_same_get_once_then_retains_success(tmp_path, monkeypatch, clock, retry_after, expected_delay):
    starts = []
    private = "never-retain-throttling-response"

    def handler(request):
        starts.append(clock.value)
        if len(starts) == 1:
            value = formatdate(clock.epoch + 3, usegmt=True) if retry_after == "date" else retry_after
            headers = {"retry-after": value} if value else {}
            headers["x-private-diagnostic"] = private
            return httpx.Response(429, headers=headers, content=private.encode())
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/test"}]}})
        return httpx.Response(200, json=record(abstract="Literal evidence after the same GET was retried."))

    requests = mocked(monkeypatch, handler)
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    assert len(requests) == 3 and requests[0].url == requests[1].url
    assert requests[0].method == requests[1].method == "GET"
    assert starts[1] - starts[0] >= expected_delay - 1e-9
    assert result["searches"][0]["status"] == "succeeded"
    assert result["sources"][0]["excerpts"] == ["Literal evidence after the same GET was retried."]
    assert private not in json.dumps(result)
    assert all(private.encode() not in path.read_bytes() for path in (tmp_path / "literature").iterdir())


def test_429_retry_budget_is_shared_across_all_queries(tmp_path, monkeypatch, clock):
    requests = mocked(monkeypatch, lambda request: httpx.Response(429))
    queries = [f"query-{index}" for index in range(8)]
    result = literature.collect(queries, tmp_path, limit=0, pdf_candidates=[])
    assert len(requests) == len(queries) + 3
    assert all(sum(request.url.params["query.bibliographic"] == query for request in requests) <= 2 for query in queries)
    assert all(search["http_status"] == 429 and search["status"] == "failed" for search in result["searches"])
    assert all("raw_path" not in search for search in result["searches"])
    assert result["sources"] == [] and not list((tmp_path / "literature").iterdir())


@pytest.mark.parametrize("retry_after, elapsed", [("11", 0), ("date", 0), ("4", 88)])
def test_429_retry_after_over_wait_or_collection_budget_is_not_retried(tmp_path, monkeypatch, clock, retry_after, elapsed):
    def handler(request):
        clock.value += elapsed
        value = formatdate(clock.epoch + 11, usegmt=True) if retry_after == "date" else retry_after
        return httpx.Response(429, headers={"retry-after": value})

    requests = mocked(monkeypatch, handler)
    result = literature.collect(["query", "unattempted"], tmp_path, limit=0, pdf_candidates=[])
    assert len(requests) == 1 and result["searches"][0]["http_status"] == 429
    assert result["rate_limited"] is True and not result.get("timed_out") and not result.get("cancelled")
    assert "raw_path" not in result["searches"][0]
    assert result["searches"][1]["attempted"] is False and result["searches"][1]["status"] == "not_attempted"


def test_repeated_429_observes_cooldown_before_next_query(tmp_path, monkeypatch, clock):
    starts = []

    def handler(request):
        starts.append(clock.value)
        if request.url.params["query.bibliographic"] == "throttled":
            return httpx.Response(429, headers={"retry-after": "1"})
        return httpx.Response(200, json={"status": "ok", "message": {"items": []}})

    requests = mocked(monkeypatch, handler)
    result = literature.collect(["throttled", "next"], tmp_path, limit=0, pdf_candidates=[])
    assert len(requests) == 3 and starts == [0, 1, 2]
    assert result["searches"][0]["http_status"] == 429
    assert result["searches"][1]["status"] == "succeeded"


def test_long_cooldown_retains_prior_raw_search_without_dispatching_next(tmp_path, monkeypatch, clock):
    def handler(request):
        if request.url.params["query.bibliographic"] == "throttled":
            return httpx.Response(429, headers={"retry-after": "11"}, content=b"private throttling response")
        return httpx.Response(200, json={"status": "ok", "message": {"items": []}})

    requests = mocked(monkeypatch, handler)
    result = literature.collect(["first", "throttled", "unattempted"], tmp_path, limit=0, pdf_candidates=[])
    assert len(requests) == 2 and result["rate_limited"] is True
    assert not result.get("cancelled") and not result.get("timed_out")
    first, failed, unattempted = result["searches"]
    assert hashlib.sha256((tmp_path / first["raw_path"]).read_bytes()).hexdigest() == first["sha256"]
    assert failed["http_status"] == 429 and failed["error"] == "HTTPStatusError" and "raw_path" not in failed
    assert unattempted["attempted"] is False
    assert b"private throttling response" not in b"".join(path.read_bytes() for path in (tmp_path / "literature").iterdir())


def test_long_cooldown_during_doi_resolution_preserves_verified_abstract(tmp_path, monkeypatch, clock):
    def handler(request):
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [
                {"DOI": "10.1234/first"}, {"DOI": "10.1234/second"}]}})
        if request.url.path.endswith("second"):
            return httpx.Response(429, headers={"retry-after": "11"})
        return httpx.Response(200, json=record("10.1234/first", abstract="Verified evidence retained before cooldown."))

    requests = mocked(monkeypatch, handler)
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    assert len(requests) == 3 and result["rate_limited"] is True
    source, = result["sources"]
    assert source["doi"] == "10.1234/first" and source["scope"] == "abstract"
    assert hashlib.sha256((tmp_path / source["raw_path"]).read_bytes()).hexdigest() == source["sha256"]


@pytest.mark.parametrize("status", [404, 503])
def test_non_429_http_status_is_not_retried(tmp_path, monkeypatch, clock, status):
    requests = mocked(monkeypatch, lambda request: httpx.Response(status))
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    assert len(requests) == 1 and result["searches"][0]["http_status"] == status
    assert result["sources"] == []


def test_cancel_during_pacing_preserves_search_without_dispatching_next(tmp_path, monkeypatch, clock):
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json={"status": "ok", "message": {"items": []}}))
    result = literature.collect(["first", "second"], tmp_path, limit=0, cancel=lambda: clock.value >= 0.2, pdf_candidates=[])
    assert len(requests) == 1 and result["cancelled"] is True and not result.get("timed_out")
    first, second = result["searches"]
    assert first["status"] == "succeeded" and (tmp_path / first["raw_path"]).is_file()
    assert second["attempted"] is False and second["status"] == "not_attempted"
    assert clock.value < 0.5


def test_cancel_during_429_wait_does_not_retry(tmp_path, monkeypatch, clock):
    requests = mocked(monkeypatch, lambda request: httpx.Response(429, headers={"retry-after": "10"}))
    result = literature.collect(["query"], tmp_path, cancel=lambda: clock.value >= 0.3, pdf_candidates=[])
    assert len(requests) == 1 and result["cancelled"] is True and not result.get("timed_out")
    assert result["searches"][0]["attempted"] is True
    assert clock.value < 1


def test_deadline_stops_undispatched_queries_without_user_cancellation(tmp_path, monkeypatch, clock):
    def handler(request):
        if request.url.params["query.bibliographic"] == "first":
            clock.value = 89.7
        return httpx.Response(200, json={"status": "ok", "message": {"items": []}})

    requests = mocked(monkeypatch, handler)
    result = literature.collect(["first", "second", "third"], tmp_path, limit=0, pdf_candidates=[])
    assert len(requests) == 2 and result["timed_out"] is True and not result.get("cancelled")
    assert clock.value <= 90
    assert result["searches"][2]["attempted"] is False
    assert result["searches"][2]["status"] == "not_attempted"
    assert all((tmp_path / search["raw_path"]).is_file() for search in result["searches"][:2])
    assert max(requests[1].extensions["timeout"].values()) <= 0.3 + 1e-9


def test_deadline_during_doi_resolution_preserves_verified_partial_abstract(tmp_path, monkeypatch, clock):
    def handler(request):
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [
                {"DOI": "10.1234/first"}, {"DOI": "10.1234/second"}]}})
        if request.url.path.endswith("second"):
            clock.value = 90
        return httpx.Response(200, json=record("10.1234/" + request.url.path.rsplit("/", 1)[-1],
                                             abstract="Already fetched and verified literal evidence."))

    requests = mocked(monkeypatch, handler)
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    assert len(requests) == 3 and result["timed_out"] is True and not result.get("cancelled")
    assert result["searches"][0]["attempted"] is True
    source, = result["sources"]
    assert source["doi"] == "10.1234/first" and source["scope"] == "abstract"
    assert hashlib.sha256((tmp_path / source["raw_path"]).read_bytes()).hexdigest() == source["sha256"]


def test_deadline_before_pdf_upgrade_retains_verified_abstract(tmp_path, monkeypatch, clock):
    def handler(request):
        if request.url.host == "joss.theoj.org":
            clock.value = 74
            return httpx.Response(200, content=b"%PDF-test", headers={"content-type": "application/pdf"})
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.21105/joss.01234"}]}})
        return httpx.Response(200, json=record("10.21105/joss.01234", abstract="A preserved abstract before optional PDF reading."))

    mocked(monkeypatch, handler)
    monkeypatch.setattr(literature, "_pdf_text", lambda content: pytest.fail("Insufficient cleanup budget dispatched a PDF child"))
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    assert result["timed_out"] is True and not result.get("cancelled")
    source, = result["sources"]
    assert source["scope"] == "abstract" and source["excerpts"] == ["A preserved abstract before optional PDF reading."]
    assert hashlib.sha256((tmp_path / source["raw_path"]).read_bytes()).hexdigest() == source["sha256"]


def test_verified_abstract_has_literal_passage_and_raw_hash(tmp_path, monkeypatch):
    def handler(request):
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [
                {"DOI": "10.1234/test", "title": ["Unverified search snippet"]}]}})
        return httpx.Response(200, json=record(abstract="<jats:p>Measured <i>reproducibility</i> was studied.</jats:p>"))

    requests = mocked(monkeypatch, handler)
    result = literature.collect(["reproducibility"], tmp_path, pdf_candidates=[])
    assert len(requests) == 2
    assert dict(requests[0].url.params) == {"query.bibliographic": "reproducibility", "rows": "6"}
    source = result["sources"][0]
    assert source["title"] == "Verified record title"
    assert source["scope"] == "abstract"
    assert source["excerpts"] == ["Measured reproducibility was studied."]
    assert source["authors"] == ["Ada Lovelace"]
    assert source["year"] == 2024
    assert source["sha256"] == hashlib.sha256((tmp_path / source["raw_path"]).read_bytes()).hexdigest()
    assert result["searches"][0]["resolved_ids"] == [source["id"]]
    assert source["queries"] == ["reproducibility"]


def test_metadata_never_becomes_a_finding(tmp_path, monkeypatch):
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json={"status": "ok", "message": {"items": [
        {"DOI": "10.1234/test", "abstract": "Unverified search abstract must never become a reading excerpt."}]}})
           if request.url.path == "/works" else httpx.Response(200, json=record()))
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    assert len(requests) == 2 and "filter" not in requests[0].url.params
    assert result["sources"][0]["scope"] == "metadata_only"
    assert result["sources"][0]["excerpts"] == []
    raw = (tmp_path / result["sources"][0]["raw_path"]).read_bytes()
    assert "abstract" not in json.loads(raw)["message"]
    assert hashlib.sha256(raw).hexdigest() == result["sources"][0]["sha256"]
    assert any("No abstract or full text" in warning for warning in result["warnings"])


def test_different_resolved_doi_is_omitted(tmp_path, monkeypatch):
    mocked(monkeypatch, lambda request: httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/test"}]}})
           if request.url.path == "/works" else httpx.Response(200, json=record("10.1234/other", abstract="Not the requested work")))
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    assert result["sources"] == []
    assert any("verification failed" in warning for warning in result["warnings"])


@pytest.mark.parametrize("url", [
    "http://arxiv.org/pdf/2401.12345", "https://127.0.0.1/private",
    "https://arxiv.org@127.0.0.1/private", "https://secret:token@arxiv.org/pdf/2401.12345",
    "https://arxiv.org:8443/pdf/2401.12345", "https://arxiv.org/pdf/2401.12345?token=secret",
    "https://arxiv.org/../private", "https://arxiv.org/pdf/2401.12345#secret",
    "https://attacker.invalid/paper.pdf",
])
def test_untrusted_pdf_link_never_reaches_transport(tmp_path, monkeypatch, url):
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/test"}]}})
                      if request.url.path == "/works" else httpx.Response(200, json=record(abstract="Inspected abstract", links=[{"URL": url, "content-type": "application/pdf"}])))
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    assert len(requests) == 2
    assert result["sources"][0]["scope"] == "abstract"
    assert any("scope was not upgraded" in warning for warning in result["warnings"])


def test_private_dns_answer_blocks_fetch(tmp_path, monkeypatch):
    requests = mocked(monkeypatch, lambda request: pytest.fail("Private DNS address reached HTTP"))
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))])
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    assert result["sources"] == [] and requests == []
    assert result["searches"][0]["status"] == "failed"


def test_crossref_redirect_is_not_followed(tmp_path, monkeypatch):
    requests = mocked(monkeypatch, lambda request: httpx.Response(302, headers={"location": "https://127.0.0.1/private"}))
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    assert len(requests) == 1 and result["sources"] == []


@pytest.mark.parametrize("response", [
    httpx.Response(200, content=b"x" * 300, headers={"content-length": "999999999"}),
    httpx.Response(200, content=b"not json"),
    httpx.Response(503),
])
def test_network_and_format_failures_return_no_inferred_sources(tmp_path, monkeypatch, response):
    mocked(monkeypatch, lambda request: response)
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    assert result["sources"] == []
    assert result["searches"][0]["status"] == "failed"


@pytest.mark.parametrize("status", [503, 404])
def test_http_search_failure_retains_only_status_and_continues(tmp_path, monkeypatch, status):
    secret = "never-retain-http-secret"

    def handler(request):
        if request.url.path == "/works":
            if request.url.params["query.bibliographic"] == "failed query":
                private = httpx.Request("GET", f"https://api.crossref.org/works?token={secret}")
                response = httpx.Response(status, request=private, content=secret.encode(),
                                          headers={"x-private-diagnostic": secret})
                raise httpx.HTTPStatusError(secret, request=private, response=response)
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/test"}]}})
        return httpx.Response(200, json=record(abstract="A later query returned an actually inspected passage."))

    requests = mocked(monkeypatch, handler)
    result = literature.collect(["failed query", "successful query"], tmp_path, pdf_candidates=[])
    assert len(requests) == 3
    failed, succeeded = result["searches"]
    assert failed == {"query": "failed query", "provider": "Crossref", "status": "failed",
                      "attempted": True, "resolved_ids": [], "lookup": "bibliographic",
                      "error": "HTTPStatusError", "http_status": status}
    assert succeeded["status"] == "succeeded" and "http_status" not in succeeded
    assert result["sources"][0]["scope"] == "abstract"
    assert result["sources"][0]["excerpts"] == ["A later query returned an actually inspected passage."]
    assert succeeded["resolved_ids"] == [result["sources"][0]["id"]]
    assert secret not in json.dumps(result)
    assert all(secret.encode() not in path.read_bytes() for path in (tmp_path / "literature").iterdir())


def test_streamed_size_bound_without_content_length(tmp_path, monkeypatch):
    monkeypatch.setattr(literature, "MAX_JSON_BYTES", 10)
    mocked(monkeypatch, lambda request: httpx.Response(200, content=b"x" * 100))
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    assert result["sources"] == []


def test_cancel_preserves_verified_partial_evidence(tmp_path, monkeypatch):
    mocked(monkeypatch, lambda request: httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/test"}, {"DOI": "10.1234/second"}]}})
           if request.url.path == "/works" else httpx.Response(200, json=record(abstract="Inspected abstract")))
    # The source metadata artifact appears before the next candidate begins.
    result = literature.collect(["query"], tmp_path, cancel=lambda: any((tmp_path / "literature").glob("source-*")), pdf_candidates=[])
    assert result["cancelled"] is True
    assert len(result["sources"]) == 1


@pytest.mark.parametrize("location", ["root", "directory", "artifact"])
def test_symbolic_links_are_rejected(tmp_path, monkeypatch, location):
    other = tmp_path / "other"
    other.mkdir()
    root = tmp_path / "output"
    if location == "root":
        symlink(root, other, directory=True)
        with pytest.raises(ValueError, match="symbolic links"):
            literature.collect(["query"], root, pdf_candidates=[])
    elif location == "directory":
        root.mkdir()
        symlink(root / "literature", other, directory=True)
        with pytest.raises(ValueError, match="symbolic link"):
            literature.collect(["query"], root, pdf_candidates=[])
    else:
        root.mkdir()
        (root / "literature").mkdir()
        content = b"evidence"
        digest = hashlib.sha256(content).hexdigest()
        symlink(root / "literature" / f"source-{digest[:16]}.json", other / "private")
        with pytest.raises(ValueError, match="symlinks or junctions"):
            literature._save(root, "source", "json", content)
        assert not (other / "private").exists()


def test_regular_content_addressed_artifact_creation_reuse_and_corruption(tmp_path):
    root = literature._prepare_root(tmp_path / "output")
    content = "Exact evidence\x00가🙂".encode("utf-8")
    relative, digest = literature._save(root, "source", "txt", content)
    path = root / relative
    assert path.read_bytes() == content and digest == hashlib.sha256(content).hexdigest()
    assert literature._save(root, "source", "txt", content) == (relative, digest)
    path.write_bytes(b"changed evidence")
    with pytest.raises(ValueError, match="does not match"):
        literature._save(root, "source", "txt", content)
    assert path.read_bytes() == b"changed evidence"


@pytest.mark.parametrize("suffix, content", [
    ("json", '{\r\n  "z": 1, "a": "원문🙂"\r\n}\r\n'.encode("utf-8")),
    ("xml", '<?xml version="1.0"?>\r\n<entry>원문🙂</entry>\r\n'.encode("utf-8")),
    ("pdf", b"%PDF-1.7\r\n\x00raw synthetic PDF bytes\r\n%%EOF"),
    ("txt", "[Page 1]\r\nExact evidence\x00가🙂\r\n".encode("utf-8")),
])
def test_long_content_addressed_artifact_keeps_raw_bytes_and_refuses_corruption(tmp_path, suffix, content):
    prefix = "source-" + "b" * 20 + "-metadata"
    digest = hashlib.sha256(content).hexdigest()
    relative = f"literature/{prefix}-{digest[:16]}.{suffix}"
    padding = 270 - len(str(tmp_path)) - len(relative) - 2
    assert padding > 0
    # Keep the collector root a normal path while its artifact exceeds MAX_PATH.
    root = literature._prepare_root(tmp_path / ("p" + "x" * (padding - 1)))
    path = workspace.safe_relative(root, relative)
    assert len(str(path)) == 270 and len(str(root / "literature")) < 248
    assert literature._save(root, prefix, suffix, content) == (relative, digest)
    assert path.read_bytes() == content and workspace.digest_file(path) == digest
    assert path.relative_to(root).as_posix() == relative and not str(path).startswith("\\\\?\\")
    assert literature._save(root, prefix, suffix, content) == (relative, digest)
    assert list(path.parent.iterdir()) == [path]
    changed = b"changed frozen evidence\r\n"
    path.write_bytes(changed)
    with pytest.raises(ValueError, match="does not match"):
        literature._save(root, prefix, suffix, content)
    assert path.read_bytes() == changed and list(path.parent.iterdir()) == [path]


def test_final_link_detection_rejects_before_native_open(tmp_path, monkeypatch):
    """Exercise final-component refusal when symlink creation is unavailable."""
    root = literature._prepare_root(tmp_path / "output")
    content = b"evidence"
    path = root / "literature" / f"source-{hashlib.sha256(content).hexdigest()[:16]}.json"
    actual_is_link, actual_open = workspace.is_link, os.open
    monkeypatch.setattr(workspace, "is_link", lambda candidate: candidate == path or actual_is_link(candidate))

    def guarded_open(candidate, *args, **kwargs):
        if candidate == path or candidate == str(path):
            pytest.fail("A detected final link must not reach native open")
        return actual_open(candidate, *args, **kwargs)

    monkeypatch.setattr(os, "open", guarded_open)
    with pytest.raises(ValueError, match="symlinks or junctions"):
        literature._save(root, "source", "json", content)
    assert not path.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction regression")
@pytest.mark.parametrize("location", ["root", "directory", "replaced_directory"])
def test_windows_junctions_are_rejected(tmp_path, monkeypatch, location):
    other = tmp_path / "private"
    other.mkdir()
    root = tmp_path / "output"
    if location == "root":
        link = root
    elif location == "directory":
        root.mkdir()
        link = root / "literature"
    else:
        literature._prepare_root(root)
        link = root / "literature"
        link.rmdir()
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(other)],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    monkeypatch.setattr(literature.httpx, "Client", lambda **kwargs: pytest.fail("Junction reached network"))
    with pytest.raises(ValueError, match="symbolic link|symlinks or junctions"):
        if location == "replaced_directory":
            literature._save(root, "source", "json", b"evidence")
        else:
            literature.collect(["query"], root, pdf_candidates=[])
    assert list(other.iterdir()) == []


def test_duplicate_doi_is_resolved_only_once(tmp_path, monkeypatch):
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/test"}, {"DOI": "10.1234/TEST"}]}})
                      if request.url.path == "/works" else httpx.Response(200, json=record(abstract="Inspected abstract")))
    result = literature.collect(["query", "query"], tmp_path, pdf_candidates=[])
    assert len(result["sources"]) == 1 and len(requests) == 2


def test_full_text_scope_requires_successful_bounded_extraction(tmp_path, monkeypatch):
    def handler(request):
        if request.url.host == "joss.theoj.org":
            return httpx.Response(200, content=b"%PDF-test", headers={"content-type": "application/pdf"})
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.21105/joss.01234"}]}})
        return httpx.Response(200, json=record("10.21105/joss.01234", abstract="Inspected abstract"))

    requests = mocked(monkeypatch, handler)
    monkeypatch.setattr(literature, "_pdf_text", lambda content: "[Page 1]\nLiteral primary-source passage.")
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    source = result["sources"][0]
    assert len(requests) == 3 and source["scope"] == "full_text"
    assert source["url"] == "https://joss.theoj.org/papers/10.21105/joss.01234.pdf"
    assert (tmp_path / source["raw_path"]).read_bytes() == b"%PDF-test"
    assert (tmp_path / source["text_path"]).read_text() == "[Page 1]\nLiteral primary-source passage."


def test_malformed_pdf_does_not_escape_or_upgrade_reading_scope(tmp_path, monkeypatch):
    def handler(request):
        if request.url.host == "joss.theoj.org":
            return httpx.Response(200, content=b"%PDF-broken", headers={"content-type": "application/pdf"})
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.21105/joss.01234"}]}})
        return httpx.Response(200, json=record("10.21105/joss.01234", abstract="Inspected abstract"))

    mocked(monkeypatch, handler)
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    assert result["sources"][0]["scope"] == "abstract"
    assert any("not upgraded" in warning for warning in result["warnings"])


@pytest.mark.parametrize("queries,limit", [([], 6), ([""], 6), (["\nprivate"], 6), (["x" * 501], 6), (["q"], -1), (["q"], True), (["q"], 13)])
def test_invalid_inputs_fail_before_network(tmp_path, monkeypatch, queries, limit):
    monkeypatch.setattr(literature.httpx, "Client", lambda **kwargs: pytest.fail("Invalid inputs reached network"))
    with pytest.raises(ValueError):
        literature.collect(queries, tmp_path, limit=limit, pdf_candidates=[])


@pytest.mark.parametrize("candidate", [{"DOI": None}, {"DOI": 123}, {}, None])
def test_malformed_candidate_doi_is_omitted(tmp_path, monkeypatch, candidate):
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json={"status": "ok", "message": {"items": [candidate]}}))
    result = literature.collect(["query"], tmp_path, pdf_candidates=[])
    assert result["sources"] == [] and len(requests) == 1


def test_configured_proxy_can_resolve_fixed_provider_when_local_dns_is_unavailable(monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("DNS unavailable")
    monkeypatch.setattr(literature.socket, "getaddrinfo", unavailable)
    monkeypatch.setattr(literature, "getproxies_environment", lambda: {"https": "http://trusted-egress.invalid:8080"})
    monkeypatch.setattr(literature, "proxy_bypass_environment", lambda *args: False)
    assert literature._checked_url("https://api.crossref.org/works") == "https://api.crossref.org/works"
    with pytest.raises(ValueError, match="allowed provider"):
        literature._checked_url("https://private.invalid/works")


def test_proxy_bypass_does_not_skip_dns_validation(monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("DNS unavailable")
    monkeypatch.setattr(literature.socket, "getaddrinfo", unavailable)
    monkeypatch.setattr(literature, "getproxies_environment", lambda: {"https": "http://trusted-egress.invalid:8080", "no": "*"})
    monkeypatch.setattr(literature, "proxy_bypass_environment", lambda *args: True)
    with pytest.raises(ValueError, match="DNS lookup failed"):
        literature._checked_url("https://api.crossref.org/works")


@pytest.fixture
def controlled_pdf():
    import io
    PdfWriter = pytest.importorskip("pypdf").PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = writer._add_object(DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                               NameObject("/Subtype"): NameObject("/Type1"),
                                               NameObject("/BaseFont"): NameObject("/Helvetica")}))
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    stream = DecodedStreamObject()
    sentence = "Literal text of a controlled extraction fixture. " * 8
    stream.set_data(f"BT /F1 12 Tf 10 700 Td ({sentence}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue(), sentence


def test_real_pdf_extracts_literal_text_in_bounded_child(controlled_pdf):
    content, sentence = controlled_pdf
    text = literature._pdf_text(content)
    assert text.startswith("[Page 1]") and sentence.strip() in text


@pytest.mark.parametrize("disable_protection", [False, True], ids=["production-worker", "bytecode-control"])
def test_real_pdf_child_import_does_not_mutate_bytecode(controlled_pdf, tmp_path, monkeypatch, disable_protection):
    # Import a fresh writable module in the real isolated child. This tests the
    # filesystem consequence, including a control that demonstrates Python
    # would write bytecode here without the worker's protection.
    module = tmp_path / "pdf_bytecode_probe.py"
    module.write_text("with open(__file__ + '.imported', 'w') as marker:\n    marker.write('worker import executed')\n", encoding="utf-8")
    original = subprocess.Popen
    processes = []

    def instrumented_child(command, **options):
        command = list(command)
        if disable_protection:
            command = [argument for argument in command if argument != "-B"]
        script = command.index("-c") + 1
        command[script] = (f"import sys\nsys.path.insert(0, {str(tmp_path)!r})\nimport pdf_bytecode_probe\n" + command[script])
        process = original(command, **options)
        processes.append(process)
        return process

    monkeypatch.setattr(literature.subprocess, "Popen", instrumented_child)
    content, sentence = controlled_pdf
    text = literature._pdf_text(content)
    assert sentence.strip() in text
    assert (tmp_path / "pdf_bytecode_probe.py.imported").read_text() == "worker import executed"
    assert bool(list(tmp_path.rglob("*.pyc"))) is disable_protection
    assert len(processes) == 1 and processes[0].poll() is not None


def test_pdf_size_is_rejected_before_child_start(monkeypatch):
    monkeypatch.setattr(literature.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("Oversize PDF started a child"))
    with pytest.raises(ValueError, match="size limit"):
        literature._pdf_text(b"%PDF-" + b"x" * literature.MAX_PDF_BYTES)


def test_pdf_deadline_terminates_child(monkeypatch):
    original = subprocess.Popen
    processes = []

    def sleeping_child(command, **options):
        process = original([command[0], "-I", "-c", "import time; time.sleep(60)"], **options)
        communicate = process.communicate
        process.communicate = lambda content, timeout: communicate(content, timeout=0.1)
        processes.append(process)
        return process

    monkeypatch.setattr(literature.subprocess, "Popen", sleeping_child)
    with pytest.raises(ValueError, match="resource limit"):
        literature._pdf_text(b"%PDF-test")
    assert len(processes) == 1 and processes[0].poll() is not None


@pytest.mark.parametrize("confirmed", [True, False])
def test_completed_pdf_leader_still_requires_whole_tree_cleanup(monkeypatch, confirmed):
    text = "Synthetic literal extraction fixture. " * 8
    process = SimpleNamespace(returncode=0, stdin=io.BytesIO(), stdout=io.BytesIO(),
                              communicate=lambda *args, **kwargs: (json.dumps(text).encode(), None),
                              poll=lambda: 0)
    cleaned = []
    monkeypatch.setattr(literature, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(literature.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(literature, "_stop_pdf_process", lambda child: cleaned.append(child) or confirmed)
    if confirmed:
        assert literature._pdf_text(b"%PDF-synthetic") == text
    else:
        with pytest.raises(ValueError, match="cleanup could not be confirmed"):
            literature._pdf_text(b"%PDF-synthetic")
    assert cleaned == [process]
    assert process.stdin.closed and process.stdout.closed


@pytest.mark.skipif(os.name != "nt", reason="Windows job assignment regression")
def test_pdf_job_assignment_failure_terminates_child_without_sending_input(monkeypatch):
    original = subprocess.Popen
    processes = []
    jobs = []

    def waiting_child(command, **options):
        process = original(command, **options)
        process.communicate = lambda *args, **kwargs: pytest.fail("PDF input sent before job assignment")
        processes.append(process)
        return process

    class UnassignedJob(literature.WindowsJob):
        def __init__(self, **options):
            super().__init__(**options)
            jobs.append(self)

        def assign(self, handle):
            raise OSError("Job assignment was refused")

    monkeypatch.setattr(literature.subprocess, "Popen", waiting_child)
    monkeypatch.setattr(literature, "WindowsJob", UnassignedJob)
    with pytest.raises(ValueError, match="resource limit"):
        literature._pdf_text(b"%PDF-test")
    assert len(processes) == 1 and processes[0].poll() is not None
    assert len(jobs) == 1 and jobs[0].handle is None


@pytest.mark.skipif(os.name != "nt", reason="Windows job cleanup regression")
def test_pdf_unconfirmed_job_cleanup_rejects_extracted_text(controlled_pdf, monkeypatch):
    class UnconfirmedJob(literature.WindowsJob):
        def stop(self):
            assert super().stop()
            return False

    monkeypatch.setattr(literature, "WindowsJob", UnconfirmedJob)
    with pytest.raises(ValueError, match="cleanup could not be confirmed"):
        literature._pdf_text(controlled_pdf[0])


def test_later_query_can_replace_metadata_with_inspected_abstract(tmp_path, monkeypatch):
    def handler(request):
        if request.url.path == "/works":
            doi = "10.1234/metadata" if request.url.params["query.bibliographic"] == "first" else "10.1234/abstract"
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": doi}]}})
        if request.url.path.endswith("metadata"):
            return httpx.Response(200, json=record("10.1234/metadata"))
        return httpx.Response(200, json=record("10.1234/abstract", abstract="Actually inspected passage"))
    requests = mocked(monkeypatch, handler)
    result = literature.collect(["first", "second"], tmp_path, limit=1, pdf_candidates=[])
    assert len(requests) == 4
    assert len(result["sources"]) == 1
    assert result["sources"][0]["doi"] == "10.1234/abstract"
    assert result["sources"][0]["scope"] == "abstract"


def test_full_source_budget_still_retains_second_frozen_query_search(tmp_path, monkeypatch):
    def handler(request):
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [
                {"DOI": "10.1234/first"}, {"DOI": "10.1234/second"}]}})
        return httpx.Response(200, json=record("10.1234/" + request.url.path.rsplit("/", 1)[-1],
                                             abstract="Inspected literal passage"))
    requests = mocked(monkeypatch, handler)
    result = literature.collect(["first query", "second query"], tmp_path, limit=2, pdf_candidates=[])
    assert len(result["sources"]) == 2 and len(requests) == 4
    assert [item["query"] for item in result["searches"]] == ["first query", "second query"]
    assert all(item["status"] == "succeeded" and item["attempted"] is True for item in result["searches"])
    assert result["searches"][0]["resolved_ids"] == result["searches"][1]["resolved_ids"]
    assert len(result["searches"][1]["resolved_ids"]) == 2
    assert all(source["queries"] == ["first query", "second query"] for source in result["sources"])
    for search in result["searches"]:
        assert hashlib.sha256((tmp_path / search["raw_path"]).read_bytes()).hexdigest() == search["sha256"]


def test_zero_remaining_source_budget_records_search_success_and_failure(tmp_path, monkeypatch):
    def handler(request):
        assert request.url.path == "/works"
        assert request.url.params["rows"] == "1"
        if request.url.params["query.bibliographic"] == "failed query":
            return httpx.Response(503)
        return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/not-resolved"}]}})
    requests = mocked(monkeypatch, handler)
    result = literature.collect(["successful query", "failed query"], tmp_path, limit=0, pdf_candidates=[])
    assert len(requests) == 2 and result["sources"] == []
    assert [item["status"] for item in result["searches"]] == ["succeeded", "failed"]
    assert all(item["attempted"] is True for item in result["searches"])
    assert (tmp_path / result["searches"][0]["raw_path"]).is_file()
    assert result["searches"][1]["error"] == "HTTPStatusError"


def test_client_initialization_failure_records_each_unattempted_query(tmp_path, monkeypatch):
    def unavailable(**kwargs):
        raise OSError("Mock client initialization failure")
    monkeypatch.setattr(literature.httpx, "Client", unavailable)
    result = literature.collect(["first", "second"], tmp_path, limit=0, pdf_candidates=[])
    assert [search["query"] for search in result["searches"]] == ["first", "second"]
    assert all(search["status"] == "failed" and search["attempted"] is False and search["error"] == "OSError"
               for search in result["searches"])


def test_candidates_are_resolved_fairly_after_every_query_is_searched(tmp_path, monkeypatch):
    def handler(request):
        if request.url.path == "/works":
            topic = request.url.params["query.bibliographic"]
            return httpx.Response(200, json={"status": "ok", "message": {"items": [
                {"DOI": f"10.1234/{topic}-{index}"} for index in range(6)]}})
        doi = "10.1234/" + request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=record(doi, abstract="An actually retrieved literal passage."))

    requests = mocked(monkeypatch, handler)
    result = literature.collect(["ambiguous", "domain"], tmp_path, pdf_candidates=[])
    assert len(result["sources"]) == 6
    assert [source["doi"] for source in result["sources"]] == [
        "10.1234/ambiguous-0", "10.1234/domain-0", "10.1234/ambiguous-1",
        "10.1234/domain-1", "10.1234/ambiguous-2", "10.1234/domain-2"]
    assert [request.url.path for request in requests[:2]] == ["/works", "/works"]
    assert all(request.url.path != "/works" for request in requests[2:])
    assert all(len(search["resolved_ids"]) == 3 for search in result["searches"])
    assert all(source["queries"] == [source["doi"].split("/", 1)[1].rsplit("-", 1)[0]]
               for source in result["sources"])


@pytest.mark.parametrize("query", [
    "10.1234/TEST", "DOI: 10.1234/test", "https://doi.org/10.1234/test",
    "The Oracle Problem in Software Testing DOI:10.1234/test",
])
def test_explicit_doi_uses_exact_lookup_and_preserves_metadata_evidence(tmp_path, monkeypatch, query):
    def handler(request):
        assert request.url.path == "/works/10.1234/test"
        assert not request.url.params
        return httpx.Response(200, json=record(abstract="Exact DOI record with an inspected abstract."))

    requests = mocked(monkeypatch, handler)
    result = literature.collect([query], tmp_path, pdf_candidates=[])
    assert len(requests) == 1
    source = result["sources"][0]
    search = result["searches"][0]
    assert source["doi"] == "10.1234/test" and source["scope"] == "abstract"
    assert source["queries"] == [query]
    assert search["lookup"] == "doi" and search["requested_doi"] == source["doi"]
    assert search["attempted"] is True and search["status"] == "succeeded"
    assert search["resolved_ids"] == [source["id"]]
    assert search["sha256"] == source["metadata_sha256"]
    assert (tmp_path / search["raw_path"]).read_bytes() == (tmp_path / source["metadata_path"]).read_bytes()


def test_explicit_doi_without_crossref_abstract_can_use_verified_open_access_text(tmp_path, monkeypatch):
    def handler(request):
        if request.url.host == "joss.theoj.org":
            return httpx.Response(200, content=b"%PDF-test", headers={"content-type": "application/pdf"})
        assert request.url.path == "/works/10.21105/joss.01234"
        return httpx.Response(200, json=record("10.21105/joss.01234"))

    requests = mocked(monkeypatch, handler)
    monkeypatch.setattr(literature, "_pdf_text", lambda content: "[Page 1]\nRetrieved primary-source passage.")
    result = literature.collect(["10.21105/joss.01234"], tmp_path, pdf_candidates=[])
    source = result["sources"][0]
    assert len(requests) == 2
    assert source["scope"] == "full_text" and source["excerpts"] == ["[Page 1]\nRetrieved primary-source passage."]
    assert source["excerpt_ranges"] == [{"start": 0, "end": len(source["excerpts"][0]), "page_start": 1, "page_end": 1}]
    assert (tmp_path / source["raw_path"]).read_bytes() == b"%PDF-test"
    assert source["sha256"] == hashlib.sha256(b"%PDF-test").hexdigest()
    assert not result["warnings"]


def test_exact_and_bibliographic_queries_share_verified_source_provenance(tmp_path, monkeypatch):
    def handler(request):
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/test"}]}})
        return httpx.Response(200, json=record(abstract="Exact lookup also matches the bibliographic search."))

    requests = mocked(monkeypatch, handler)
    result = literature.collect(["topic", "10.1234/test", "DOI:10.1234/TEST"], tmp_path, limit=1, pdf_candidates=[])
    assert len(requests) == 2 and len(result["sources"]) == 1
    source = result["sources"][0]
    assert source["queries"] == ["topic", "10.1234/test", "DOI:10.1234/TEST"]
    assert all(search["resolved_ids"] == [source["id"]] for search in result["searches"])


def test_explicit_doi_mismatch_is_a_failed_exact_lookup(tmp_path, monkeypatch):
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json=record("10.1234/other", abstract="Wrong record.")))
    result = literature.collect(["10.1234/test"], tmp_path, pdf_candidates=[])
    assert len(requests) == 1 and result["sources"] == []
    search = result["searches"][0]
    assert search["lookup"] == "doi" and search["status"] == "failed"
    assert search["attempted"] is True and search["resolved_ids"] == []
    assert hashlib.sha256((tmp_path / search["raw_path"]).read_bytes()).hexdigest() == search["sha256"]


def test_exact_lookup_with_no_remaining_source_budget_still_records_attempt(tmp_path, monkeypatch):
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json=record()))
    result = literature.collect(["10.1234/test"], tmp_path, limit=0, pdf_candidates=[])
    assert len(requests) == 1 and result["sources"] == []
    assert result["searches"][0]["status"] == "succeeded"
    assert result["searches"][0]["attempted"] is True
    assert result["searches"][0]["resolved_ids"] == []


def test_metadata_only_candidates_do_not_consume_inspected_source_budget(tmp_path, monkeypatch):
    def handler(request):
        if request.url.path == "/works":
            topic = request.url.params["query.bibliographic"]
            return httpx.Response(200, json={"status": "ok", "message": {"items": [
                {"DOI": f"10.1234/{topic}-{index}"} for index in range(2)]}})
        doi = "10.1234/" + request.url.path.rsplit("/", 1)[-1]
        abstract = None if "/metadata-" in doi else "Actually inspected passage from the later query."
        return httpx.Response(200, json=record(doi, abstract=abstract))

    requests = mocked(monkeypatch, handler)
    result = literature.collect(["metadata", "abstract"], tmp_path, limit=2, pdf_candidates=[])
    assert len(requests) == 6
    assert [source["doi"] for source in result["sources"]] == ["10.1234/abstract-1", "10.1234/abstract-0"]
    assert all(source["scope"] == "abstract" for source in result["sources"])


def test_cancellation_during_query_discovery_keeps_completed_search_receipt(tmp_path, monkeypatch):
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/test"}]}}))
    result = literature.collect(["first", "second"], tmp_path,
                                cancel=lambda: any((tmp_path / "literature").glob("search-*")), pdf_candidates=[])
    assert len(requests) == 1 and result["cancelled"] is True and result["sources"] == []
    assert result["searches"][0]["status"] == "succeeded"
    assert result["searches"][1]["status"] == "not_attempted"
    assert result["searches"][1]["attempted"] is False
    search = result["searches"][0]
    assert hashlib.sha256((tmp_path / search["raw_path"]).read_bytes()).hexdigest() == search["sha256"]


def method_entry(identifier="2301.00001v2", *, title="Synthetic Differential Testing Method",
                 authors=("Example Author",), published="2023-01-01T00:00:00Z", updated="2023-01-02T00:00:00Z"):
    return ("<entry><id>http://arxiv.org/abs/" + escape(identifier) + "</id><title>" + escape(title) + "</title>"
            "<published>" + escape(published) + "</published><updated>" + escape(updated) + "</updated>"
            + "".join("<author><name>" + escape(author) + "</name></author>" for author in authors)
            + "<summary>A literal synthetic abstract, without a scientific approval.</summary></entry>")


def method_feed(*entries):
    return ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">'
            + "<opensearch:totalResults>" + str(len(entries)) + "</opensearch:totalResults>"
            + "".join(entries) + "</feed>").encode()


METHOD_TEXT = ("[Page 1]\nAbstract\nAn abstract only.\n1 Introduction\n"
               + "This synthetic body describes differential comparison methods and their limits. " * 35
               + "\nReferences\nUninspected bibliography.")


def test_method_discovery_reads_both_version_bound_pdfs_before_six_abstracts(tmp_path, monkeypatch, clock):
    entries = {"2301.00001v2": method_entry(), "2301.00002v1": method_entry("2301.00002v1", title="Synthetic Comparison Method")}
    original = method_feed(*entries.values())
    starts = []

    def handler(request):
        if request.url.host == "export.arxiv.org":
            starts.append(clock.value)
            if "id_list" in request.url.params:
                return httpx.Response(200, content=method_feed(entries[request.url.params["id_list"]]),
                                      headers={"content-type": "application/atom+xml"})
            assert request.url.params["max_results"] == "2" and request.url.params["sortBy"] == "relevance"
            return httpx.Response(200, content=original, headers={"content-type": "application/atom+xml"})
        if request.url.host == "arxiv.org":
            return httpx.Response(200, content=b"%PDF-synthetic-" + request.url.path.encode(), headers={"content-type": "application/pdf"})
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": f"10.1234/abstract-{i}"} for i in range(6)]}})
        return httpx.Response(200, json=record("10.1234/" + request.url.path.rsplit("/", 1)[-1], abstract="A bibliographic abstract."))

    requests = mocked(monkeypatch, handler, method_discovery=True)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: METHOD_TEXT)
    query = "differential testing comparison"
    result = literature.collect([query], tmp_path, pdf_candidates=[])
    assert len(result["sources"]) == 6
    primary = result["sources"][:2]
    assert [source["arxiv_id"] for source in primary] == list(entries)
    assert all(source["scope"] == "full_text" and source["publication_type"] == "preprint" for source in primary)
    assert all(source["queries"] == [query] and source["discovery_kind"] == "method" for source in primary)
    first_crossref_record = next(index for index, request in enumerate(requests) if request.url.path.startswith("/works/"))
    assert sum(request.url.host == "arxiv.org" for request in requests[:first_crossref_record]) == 2
    assert all(right - left >= 3 - 1e-9 for left, right in zip(starts, starts[1:]))
    method, = [search for search in result["searches"] if search.get("lookup") == "method"]
    assert method["query"] == query and method["candidate_arxiv_ids"] == list(entries)
    assert method["resolved_ids"] == [source["id"] for source in primary]
    assert "independent review" in method["note"] and not result["warnings"]
    versions = [search for search in result["searches"] if search.get("lookup") == "arxiv_version"]
    assert len(versions) == 2 and all(search["status"] == "succeeded" for search in versions)
    for source in primary:
        assert (tmp_path / source["discovery_path"]).read_bytes() == original
        assert (tmp_path / source["metadata_path"]).read_bytes() == method_feed(entries[source["arxiv_id"]])
        assert literature._arxiv_metadata((tmp_path / source["metadata_path"]).read_bytes(), source["arxiv_id"])["title"] == source["title"]
        for path_key, hash_key in (("discovery_path", "discovery_sha256"), ("metadata_path", "metadata_sha256"),
                                   ("raw_path", "sha256"), ("text_path", "text_sha256")):
            assert hashlib.sha256((tmp_path / source[path_key]).read_bytes()).hexdigest() == source[hash_key]
        body = literature.full_text_body_range(METHOD_TEXT)
        assert source["body_range"] == body
        assert all(body["start"] <= location["start"] < location["end"] <= body["end"] and
                   METHOD_TEXT[location["start"]:location["end"]] == passage
                   for passage, location in zip(source["excerpts"], source["excerpt_ranges"]))


def test_method_discovery_treats_query_operators_and_unicode_as_literal_words(tmp_path, monkeypatch):
    query = 'differential OR id:2301.00001v2 "testing" \\ βeta'

    def handler(request):
        if request.url.host == "export.arxiv.org":
            assert request.url.params["search_query"] == ('all:"differential" AND all:"OR" AND all:"id" AND '
                'all:"2301" AND all:"00001v2" AND all:"testing" AND all:"βeta"')
            assert set(request.url.params) == {"search_query", "start", "max_results", "sortBy"}
            assert "%CE%B2" in str(request.url)
            return httpx.Response(200, content=method_feed(), headers={"content-type": "application/atom+xml"})
        assert request.url.params["query.bibliographic"] == query
        return httpx.Response(200, json={"status": "ok", "message": {"items": []}})

    mocked(monkeypatch, handler, method_discovery=True)
    result = literature.collect([query], tmp_path, pdf_candidates=[])
    assert result["sources"] == []
    method, = [search for search in result["searches"] if search.get("lookup") == "method"]
    assert method["query"] == query and method["status"] == "succeeded" and method["candidate_arxiv_ids"] == []
    assert (tmp_path / method["raw_path"]).read_bytes() == method_feed()


@pytest.mark.parametrize("returned", [
    method_feed(method_entry("2301.00001v3")),
    method_feed(method_entry(title="A Conflicting Whole Title")),
    method_feed(method_entry(authors=("A Different Author",))),
    method_feed(method_entry(updated="2023-01-03T00:00:00Z")),
    method_feed(method_entry(), method_entry()),
])
def test_method_version_identity_failure_omits_candidate_and_retains_both_original_feeds(tmp_path, monkeypatch, clock, returned):
    original = method_feed(method_entry())

    def handler(request):
        assert request.url.host != "arxiv.org", "A mismatched exact identity must not request its PDF"
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, content=returned if "id_list" in request.url.params else original,
                                  headers={"content-type": "application/atom+xml"})
        return httpx.Response(200, json={"status": "ok", "message": {"items": []}})

    mocked(monkeypatch, handler, method_discovery=True)
    result = literature.collect(["differential testing"], tmp_path, pdf_candidates=[])
    assert result["sources"] == []
    method, = [search for search in result["searches"] if search.get("lookup") == "method"]
    version, = [search for search in result["searches"] if search.get("lookup") == "arxiv_version"]
    assert method["status"] == "succeeded" and version["status"] == "failed" and version["resolved_ids"] == []
    assert version["requested_arxiv_id"] == "2301.00001v2" and version["error"] == "ValueError"
    for search, raw in ((method, original), (version, returned)):
        assert (tmp_path / search["raw_path"]).read_bytes() == raw
        assert hashlib.sha256(raw).hexdigest() == search["sha256"]


@pytest.mark.parametrize("content", [
    b"<invalid>",
    method_feed(method_entry("2301.00001")),
    method_feed(method_entry(), method_entry()),
    method_feed(method_entry(), method_entry("2301.00001v3")),
    method_feed(method_entry(), method_entry("2301.00002v1"), method_entry("2301.00003v1")),
    b'<!DOCTYPE feed [<!ENTITY unsafe "identity">]><feed xmlns="http://www.w3.org/2005/Atom"/>',
])
def test_method_discovery_rejects_invalid_ambiguous_or_excess_candidates_with_raw_preserved(tmp_path, monkeypatch, content):
    def handler(request):
        assert request.url.host != "arxiv.org"
        if request.url.host == "export.arxiv.org":
            assert "id_list" not in request.url.params
            return httpx.Response(200, content=content, headers={"content-type": "application/atom+xml"})
        return httpx.Response(200, json={"status": "ok", "message": {"items": []}})

    mocked(monkeypatch, handler, method_discovery=True)
    result = literature.collect(["differential testing"], tmp_path, pdf_candidates=[])
    assert not result["sources"]
    method, = [search for search in result["searches"] if search.get("lookup") == "method"]
    assert method["status"] == "failed" and method["error"] == "ValueError"
    assert (tmp_path / method["raw_path"]).read_bytes() == content
    assert hashlib.sha256(content).hexdigest() == method["sha256"]


def test_method_searches_are_globally_bounded_and_zero_source_budget_skips_discovery(tmp_path, monkeypatch):
    def handler(request):
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, content=method_feed(), headers={"content-type": "application/atom+xml"})
        return httpx.Response(200, json={"status": "ok", "message": {"items": []}})

    requests = mocked(monkeypatch, handler, method_discovery=True)
    result = literature.collect([f"method query {i}" for i in range(8)], tmp_path, pdf_candidates=[])
    assert sum(request.url.host == "export.arxiv.org" for request in requests) == 2
    assert sum(search.get("lookup") == "method" for search in result["searches"]) == 2
    assert len([search for search in result["searches"] if search["provider"] == "Crossref"]) == 8
    before = len(requests)
    result = literature.collect(["method query"], tmp_path / "zero", limit=0, pdf_candidates=[])
    assert len(requests) == before + 1 and not any(search.get("lookup") == "method" for search in result["searches"])


def test_method_source_limit_one_requests_one_candidate_and_reads_before_any_abstract(tmp_path, monkeypatch, clock):
    original = method_feed(method_entry())

    def handler(request):
        if request.url.host == "export.arxiv.org":
            assert request.url.params["max_results"] == "1"
            return httpx.Response(200, content=original, headers={"content-type": "application/atom+xml"})
        if request.url.host == "arxiv.org":
            return httpx.Response(200, content=b"%PDF-one", headers={"content-type": "application/pdf"})
        assert request.url.path == "/works", "Crossref candidates must not consume the single primary opportunity"
        return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/abstract"}]}})

    requests = mocked(monkeypatch, handler, method_discovery=True)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: METHOD_TEXT)
    result = literature.collect(["differential testing"], tmp_path, limit=1, pdf_candidates=[])
    assert len(result["sources"]) == 1 and result["sources"][0]["scope"] == "full_text"
    assert len(requests) == 4 and not result["warnings"]


def test_ambiguous_exact_whole_title_cannot_be_reinterpreted_as_a_method_search(tmp_path, monkeypatch):
    title = "Synthetic Differential Testing Method"
    ambiguous = method_feed(method_entry(), method_entry("2301.00002v1"))

    def handler(request):
        if request.url.host == "export.arxiv.org":
            assert request.url.params["search_query"] == 'ti:"' + title + '"'
            return httpx.Response(200, content=ambiguous, headers={"content-type": "application/atom+xml"})
        return httpx.Response(200, json={"status": "ok", "message": {"items": []}})

    requests = mocked(monkeypatch, handler, title_discovery=True, method_discovery=True)
    result = literature.collect([title], tmp_path, pdf_candidates=[])
    assert not result["sources"] and sum(request.url.host == "export.arxiv.org" for request in requests) == 1
    exact, = [search for search in result["searches"] if search.get("lookup") == "exact_title"]
    assert exact["status"] == "failed" and (tmp_path / exact["raw_path"]).read_bytes() == ambiguous
    assert not any(search.get("lookup") == "method" for search in result["searches"])


@pytest.mark.parametrize("location", ["/pdf/2301.00001v3", "/pdf/2301.00002v2", "/pdf/2301.00001"])
def test_arxiv_pdf_redirect_identity_failure_keeps_raw_without_upgrading_scope(tmp_path, monkeypatch, clock, location):
    original = method_feed(method_entry())
    rejected = b"%PDF-rejected-version\r\nexact bytes\x00"

    def handler(request):
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, content=original, headers={"content-type": "application/atom+xml"})
        if request.url.host == "arxiv.org":
            if request.url.path == "/pdf/2301.00001v2":
                return httpx.Response(302, headers={"location": location})
            return httpx.Response(200, content=rejected, headers={"content-type": "application/pdf"})
        return httpx.Response(200, json={"status": "ok", "message": {"items": []}})

    mocked(monkeypatch, handler, method_discovery=True)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: pytest.fail("A different PDF version must never be parsed"))
    result = literature.collect(["differential testing"], tmp_path, pdf_candidates=[])
    source, = result["sources"]
    assert source["scope"] == "abstract" and "text_path" not in source
    assert (tmp_path / source["raw_path"]).read_bytes() == original
    pdfs = list((tmp_path / "literature").glob("*.pdf"))
    assert len(pdfs) == 1 and pdfs[0].read_bytes() == rejected
    assert any("reading scope was not upgraded" in warning for warning in result["warnings"])


def test_arxiv_same_version_pdf_suffix_retains_actual_url_and_canonical_identity(tmp_path, monkeypatch, clock):
    original = method_feed(method_entry())

    def handler(request):
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, content=original, headers={"content-type": "application/atom+xml"})
        if request.url.host == "arxiv.org":
            if not request.url.path.endswith(".pdf"):
                return httpx.Response(302, headers={"location": "/pdf/2301.00001v2.pdf"})
            return httpx.Response(200, content=b"%PDF-same-version", headers={"content-type": "application/pdf"})
        return httpx.Response(200, json={"status": "ok", "message": {"items": []}})

    mocked(monkeypatch, handler, method_discovery=True)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: METHOD_TEXT)
    result = literature.collect(["differential testing"], tmp_path, pdf_candidates=[])
    source, = result["sources"]
    assert source["scope"] == "full_text" and source["url"] == "https://arxiv.org/pdf/2301.00001v2"
    assert source["retrieved_url"] == "https://arxiv.org/pdf/2301.00001v2.pdf"
    assert len(list((tmp_path / "literature").glob("*.pdf"))) == 1 and not result["warnings"]


def test_method_collection_cancellation_preserves_discovery_and_does_not_claim_crossref_attempt(tmp_path, monkeypatch):
    original = method_feed(method_entry())

    def handler(request):
        assert request.url.host == "export.arxiv.org"
        return httpx.Response(200, content=original, headers={"content-type": "application/atom+xml"})

    requests = mocked(monkeypatch, handler, method_discovery=True)
    result = literature.collect(["differential testing", "unattempted comparison"], tmp_path, pdf_candidates=[],
        cancel=lambda: any((tmp_path / "literature").glob("method-*")))
    assert len(requests) == 1 and result["cancelled"] is True and not result["sources"]
    method, = [search for search in result["searches"] if search.get("lookup") == "method"]
    assert method["status"] == "succeeded" and (tmp_path / method["raw_path"]).read_bytes() == original
    assert all(not search["attempted"] and search["status"] == "not_attempted"
               for search in result["searches"] if search["provider"] == "Crossref")


def test_method_shared_deadline_retains_raw_pdf_before_refusing_worker_dispatch(tmp_path, monkeypatch, clock):
    original = method_feed(method_entry())
    raw_pdf = b"%PDF-time-budget"

    def handler(request):
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, content=original, headers={"content-type": "application/atom+xml"})
        if request.url.host == "arxiv.org":
            clock.value = 73
            return httpx.Response(200, content=raw_pdf, headers={"content-type": "application/pdf"})
        return httpx.Response(200, json={"status": "ok", "message": {"items": []}})

    mocked(monkeypatch, handler, method_discovery=True)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: pytest.fail("Insufficient cleanup budget must not start a worker"))
    result = literature.collect(["differential testing"], tmp_path, pdf_candidates=[])
    source, = result["sources"]
    assert result["timed_out"] is True and source["scope"] == "abstract" and "text_path" not in source
    assert next((tmp_path / "literature").glob("*.pdf")).read_bytes() == raw_pdf
    assert clock.value < 90


def test_method_long_cooldown_does_not_claim_other_provider_or_query_attempts(tmp_path, monkeypatch, clock):
    requests = mocked(monkeypatch, lambda request: httpx.Response(429, headers={"retry-after": "11"}), method_discovery=True)
    result = literature.collect(["differential testing", "unattempted comparison"], tmp_path, pdf_candidates=[])
    assert len(requests) == 1 and result["rate_limited"] is True and not result.get("timed_out")
    method, = [search for search in result["searches"] if search.get("lookup") == "method"]
    assert method["attempted"] is True and method["status"] == "failed" and method["http_status"] == 429
    assert all(not search["attempted"] and search["status"] == "not_attempted"
               for search in result["searches"] if search["provider"] == "Crossref")
    assert not list((tmp_path / "literature").iterdir())


@pytest.mark.parametrize("query", ["arxiv:2301.00001v2", "Synthetic Differential Testing Method", "10.1234/test"])
def test_exact_identity_routes_are_not_reinterpreted_as_method_queries(tmp_path, monkeypatch, clock, query):
    original = method_feed(method_entry())

    def handler(request):
        if request.url.host == "export.arxiv.org":
            if "search_query" in request.url.params:
                assert request.url.params["search_query"] == 'ti:"Synthetic Differential Testing Method"'
            else:
                assert request.url.params["id_list"] == "2301.00001v2"
            return httpx.Response(200, content=original, headers={"content-type": "application/atom+xml"})
        if request.url.host == "arxiv.org":
            return httpx.Response(200, content=b"%PDF-exact", headers={"content-type": "application/pdf"})
        assert request.url.path == "/works/10.1234/test" and not request.url.params
        return httpx.Response(200, json=record(abstract="A literal exact DOI abstract."))

    requests = mocked(monkeypatch, handler, title_discovery=True, method_discovery=True)
    monkeypatch.setattr(literature, "_pdf_text", lambda raw: METHOD_TEXT)
    result = literature.collect([query], tmp_path, pdf_candidates=[])
    assert len(result["sources"]) == 1 and len(requests) == (1 if query.startswith("10.") else 2)
    assert not any(search.get("lookup") in {"method", "arxiv_version"} for search in result["searches"])
    assert result["sources"][0]["queries"] == [query] and not result["warnings"]

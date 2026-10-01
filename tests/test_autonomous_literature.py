import hashlib
import json
import os
from pathlib import Path
import subprocess

import httpx
import pytest

from paper_factory.autonomous import literature


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


def mocked(monkeypatch, handler):
    original = httpx.Client
    requests = []

    def transport(request):
        requests.append(request)
        return handler(request)

    monkeypatch.setattr(literature.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs))
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("8.8.8.8", 443))])
    return requests


def test_verified_abstract_has_literal_passage_and_raw_hash(tmp_path, monkeypatch):
    def handler(request):
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [
                {"DOI": "10.1234/test", "title": ["Unverified search snippet"]}]}})
        return httpx.Response(200, json=record(abstract="<jats:p>Measured <i>reproducibility</i> was studied.</jats:p>"))

    requests = mocked(monkeypatch, handler)
    result = literature.collect(["reproducibility"], tmp_path)
    assert len(requests) == 2
    source = result["sources"][0]
    assert source["title"] == "Verified record title"
    assert source["scope"] == "abstract"
    assert source["excerpts"] == ["Measured reproducibility was studied."]
    assert source["authors"] == ["Ada Lovelace"]
    assert source["year"] == 2024
    assert source["sha256"] == hashlib.sha256((tmp_path / source["raw_path"]).read_bytes()).hexdigest()
    assert result["searches"][0]["resolved_ids"] == [source["id"]]


def test_metadata_never_becomes_a_finding(tmp_path, monkeypatch):
    mocked(monkeypatch, lambda request: httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/test"}]}})
           if request.url.path == "/works" else httpx.Response(200, json=record()))
    result = literature.collect(["query"], tmp_path)
    assert result["sources"][0]["scope"] == "metadata_only"
    assert result["sources"][0]["excerpts"] == []
    assert any("No abstract or full text" in warning for warning in result["warnings"])


def test_different_resolved_doi_is_omitted(tmp_path, monkeypatch):
    mocked(monkeypatch, lambda request: httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/test"}]}})
           if request.url.path == "/works" else httpx.Response(200, json=record("10.1234/other", abstract="Not the requested work")))
    result = literature.collect(["query"], tmp_path)
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
    result = literature.collect(["query"], tmp_path)
    assert len(requests) == 2
    assert result["sources"][0]["scope"] == "abstract"
    assert any("scope was not upgraded" in warning for warning in result["warnings"])


def test_private_dns_answer_blocks_fetch(tmp_path, monkeypatch):
    requests = mocked(monkeypatch, lambda request: pytest.fail("Private DNS address reached HTTP"))
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))])
    result = literature.collect(["query"], tmp_path)
    assert result["sources"] == [] and requests == []
    assert result["searches"][0]["status"] == "failed"


def test_crossref_redirect_is_not_followed(tmp_path, monkeypatch):
    requests = mocked(monkeypatch, lambda request: httpx.Response(302, headers={"location": "https://127.0.0.1/private"}))
    result = literature.collect(["query"], tmp_path)
    assert len(requests) == 1 and result["sources"] == []


@pytest.mark.parametrize("response", [
    httpx.Response(200, content=b"x" * 300, headers={"content-length": "999999999"}),
    httpx.Response(200, content=b"not json"),
    httpx.Response(503),
])
def test_network_and_format_failures_return_no_inferred_sources(tmp_path, monkeypatch, response):
    mocked(monkeypatch, lambda request: response)
    result = literature.collect(["query"], tmp_path)
    assert result["sources"] == []
    assert result["searches"][0]["status"] == "failed"


def test_streamed_size_bound_without_content_length(tmp_path, monkeypatch):
    monkeypatch.setattr(literature, "MAX_JSON_BYTES", 10)
    mocked(monkeypatch, lambda request: httpx.Response(200, content=b"x" * 100))
    result = literature.collect(["query"], tmp_path)
    assert result["sources"] == []


def test_cancel_preserves_verified_partial_evidence(tmp_path, monkeypatch):
    mocked(monkeypatch, lambda request: httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/test"}, {"DOI": "10.1234/second"}]}})
           if request.url.path == "/works" else httpx.Response(200, json=record(abstract="Inspected abstract")))
    # The source metadata artifact appears before the next candidate begins.
    result = literature.collect(["query"], tmp_path, cancel=lambda: any((tmp_path / "literature").glob("source-*")))
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
            literature.collect(["query"], root)
    elif location == "directory":
        root.mkdir()
        symlink(root / "literature", other, directory=True)
        with pytest.raises(ValueError, match="symbolic link"):
            literature.collect(["query"], root)
    else:
        root.mkdir()
        (root / "literature").mkdir()
        content = b"evidence"
        digest = hashlib.sha256(content).hexdigest()
        symlink(root / "literature" / f"source-{digest[:16]}.json", other / "private")
        with pytest.raises(ValueError, match="does not match"):
            literature._save(root, "source", "json", content)
        assert not (other / "private").exists()


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
            literature.collect(["query"], root)
    assert list(other.iterdir()) == []


def test_duplicate_doi_is_resolved_only_once(tmp_path, monkeypatch):
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/test"}, {"DOI": "10.1234/TEST"}]}})
                      if request.url.path == "/works" else httpx.Response(200, json=record(abstract="Inspected abstract")))
    result = literature.collect(["query", "query"], tmp_path)
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
    result = literature.collect(["query"], tmp_path)
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
    result = literature.collect(["query"], tmp_path)
    assert result["sources"][0]["scope"] == "abstract"
    assert any("not upgraded" in warning for warning in result["warnings"])


@pytest.mark.parametrize("queries,limit", [([], 6), ([""], 6), (["\nprivate"], 6), (["x" * 501], 6), (["q"], 0), (["q"], True), (["q"], 13)])
def test_invalid_inputs_fail_before_network(tmp_path, monkeypatch, queries, limit):
    monkeypatch.setattr(literature.httpx, "Client", lambda **kwargs: pytest.fail("Invalid inputs reached network"))
    with pytest.raises(ValueError):
        literature.collect(queries, tmp_path, limit=limit)


@pytest.mark.parametrize("candidate", [{"DOI": None}, {"DOI": 123}, {}, None])
def test_malformed_candidate_doi_is_omitted(tmp_path, monkeypatch, candidate):
    requests = mocked(monkeypatch, lambda request: httpx.Response(200, json={"status": "ok", "message": {"items": [candidate]}}))
    result = literature.collect(["query"], tmp_path)
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
    result = literature.collect(["first", "second"], tmp_path, limit=1)
    assert len(requests) == 4
    assert len(result["sources"]) == 1
    assert result["sources"][0]["doi"] == "10.1234/abstract"
    assert result["sources"][0]["scope"] == "abstract"

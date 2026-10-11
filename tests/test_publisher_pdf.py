"""DOI-free official proceedings bind actual metadata, PDF front matter and native frozen bytes."""
import copy
import json

import httpx
import pytest

from paper_factory.autonomous import literature
from paper_factory.autonomous.models import FrozenArtifact
from paper_factory.workflow import WorkflowError, _retained_primary_body, _verified_repository_pdf
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import Workspace, digest_file, write_json
from test_autonomous_literature import clock, mocked
from test_public_pdf_hints import PDF, assert_retained


LANDING = "https://www.usenix.org/conference/usenixsecurity24/presentation/ali"
URL = "https://www.usenix.org/system/files/usenixsecurity24-ali.pdf"
TITLE = "Synthetic bounded proceedings identity"
HINT = {"landing_url": LANDING, "pdf_url": URL, "title": TITLE, "authors": ["Ada Lovelace", "Grace Hopper"], "year": 2024}
HTML = (f"<html><h1>{TITLE}</h1><div>@inproceedings {{123,\n"
        f"author = {{Ada Lovelace and Grace Hopper}},\ntitle = {{{TITLE}}},\nyear = {{2024}},\n"
        f"publisher = {{USENIX Association}},\nurl = {{{LANDING}}},\n}}\n</div>"
        f'<a href="{URL}">Final PDF</a><a href="/system/files/sec24summer-prepub-120-ali.pdf">Preprint</a></html>').encode()
TEXT = (f"[Page 1]\nUSENIX proceedings 2024\n[Page 2]\n{TITLE}\nAda Lovelace, Grace Hopper\n"
        "Synthetic University\nAbstract\nA synthetic fixture does not establish a real scientific finding.\n1 Introduction\n"
        + "Synthetic source comparison has complete retained data and explicit limits. " * 30
        + "\n[Page 3]\n2 Methods\n" + "Synthetic original method and counterexample details are retained. " * 30
        + "\nReferences\nA bibliography is not inspected body evidence.\n")


def collection(monkeypatch, root, *, html=HTML, text=TEXT, status=200, raw=PDF, reservation_limit=2, excluded_urls=None,
               excluded_identities=None):
    def respond(request):
        assert request.url.host == "www.usenix.org", "Publisher identity must not issue unrelated discovery"
        if str(request.url) == LANDING:
            return httpx.Response(200, content=html, headers={"content-type": "text/html"})
        assert str(request.url) == URL
        return httpx.Response(status, content=raw, headers={"content-type": "application/pdf"})
    requests = mocked(monkeypatch, respond)
    monkeypatch.setattr(literature, "_pdf_text", lambda content: text)
    result = literature.collect([TITLE], root, pdf_candidates=[HINT], pdf_reservation_limit=reservation_limit,
        excluded_urls=excluded_urls, excluded_identities=excluded_identities)
    return result, requests


def test_official_identity_retains_complete_proof_without_invented_doi(tmp_path, monkeypatch, clock):
    ws = Workspace.create(tmp_path)
    result, requests = collection(monkeypatch, ws.path("research"))
    source, = result["sources"]
    attempt, = result["pdf_hint_attempts"]
    assert [str(request.url) for request in requests] == [LANDING, URL]
    assert source["doi"] == "" and "arxiv_id" not in source
    assert source["scope"] == "full_text" and source["page_count"] == 3
    assert source["publication_version"] == "unknown" and attempt["route"] == "publisher_public_pdf"
    assert result["pdf_reservations"] == [{"source_id": source["id"], "identity": "publisher:" + LANDING,
        "route": "repository_copy", "url": URL, "pdf_attempted": True}]
    assert_retained(ws.path("research"), source, content=PDF)
    assert_retained(ws.path("research"), source, "metadata_path", "metadata_sha256", HTML)
    assert_retained(ws.path("research"), source, "text_path", "text_sha256", TEXT.encode())
    assert _verified_repository_pdf(ws, source, [HINT])
    record = Workflow(project_id="synthetic", goal="Synthetic publisher proof contract only")
    for field in ("raw_path", "metadata_path", "text_path", "discovery_path", "identity_path"):
        path = ws.path("research") / source[field]
        record.artifacts["literature-" + field] = FrozenArtifact(path=path.relative_to(ws.root).as_posix(),
            sha256=digest_file(path), size=path.stat().st_size)
    assert _retained_primary_body(ws, record, source, result)
    forged = copy.deepcopy(result)
    forged["sources"][0]["excerpts"][0] = "A nonexistent observed result. " * 4
    assert not _retained_primary_body(ws, record, forged["sources"][0], forged)


@pytest.mark.parametrize("defect", ["title", "authors", "year", "pdf", "publisher", "doi", "second_record"])
def test_metadata_mismatch_retained_without_pdf_reservation(tmp_path, monkeypatch, clock, defect):
    html = HTML
    if defect == "title": html = html.replace(TITLE.encode(), b"Another exact title", 1)
    elif defect == "authors": html = html.replace(b"Ada Lovelace and Grace Hopper", b"Someone Else and Grace Hopper")
    elif defect == "year": html = html.replace(b"year = {2024}", b"year = {2023}")
    elif defect == "pdf": html = html.replace(URL.encode(), URL.replace("ali.pdf", "another.pdf").encode())
    elif defect == "publisher": html = html.replace(b"USENIX Association", b"Unrelated publisher")
    elif defect == "doi": html = html.replace(b"year =", b"doi = {10.1234/conflict},\nyear =")
    else: html += HTML
    result, requests = collection(monkeypatch, tmp_path, html=html)
    assert len(requests) == 1 and result["sources"] == [] and result["pdf_reservations"] == []
    attempt, = result["pdf_hint_attempts"]
    assert attempt["status"] == "rejected"
    assert_retained(tmp_path, attempt, "metadata_path", "metadata_sha256", html)


@pytest.mark.parametrize("text", [TEXT.replace(TITLE, "Another full title"), TEXT.replace("Ada Lovelace,", "Ada Lovelaceford,"),
    TEXT.replace("2024", "2023"), TEXT.replace("Abstract\n", "10.1234/conflicting\nAbstract\n")])
def test_pdf_mismatch_consumes_once_and_retains_originals(tmp_path, monkeypatch, clock, text):
    result, requests = collection(monkeypatch, tmp_path, text=text)
    assert len(requests) == 2 and result["sources"] == [] and len(result["pdf_reservations"]) == 1
    attempt, = result["pdf_hint_attempts"]
    assert_retained(tmp_path, attempt, content=PDF)
    assert_retained(tmp_path, attempt, "text_path", "text_sha256", text.encode())


@pytest.mark.parametrize("hint", [{**HINT, "landing_url": LANDING + "?token=x"}, {**HINT, "pdf_url": URL.replace("https:", "http:")},
    {**HINT, "pdf_url": URL.replace("www.usenix.org", "127.0.0.1")}, {**HINT, "pdf_url": URL.replace("ali.pdf", "../ali.pdf")},
    {**HINT, "year": 2023}, {**HINT, "authors": ["Ada Lovelace", "Ada Lovelace"]}])
def test_invalid_candidate_rejected_before_files_dns_http(tmp_path, monkeypatch, hint):
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *a, **k: pytest.fail("Invalid candidate reached DNS"))
    monkeypatch.setattr(literature.httpx, "Client", lambda **k: pytest.fail("Invalid candidate reached HTTP"))
    root = tmp_path / "not-created"
    with pytest.raises(ValueError):
        literature.collect([TITLE], root, pdf_candidates=[hint])
    assert not root.exists()


@pytest.mark.parametrize("limit,urls,identities,count", [(0, [], [], 1), (2, [URL], [], 1), (2, [], ["publisher:" + LANDING], 0)])
def test_shared_budget_and_retained_failures_are_not_reset(tmp_path, monkeypatch, clock, limit, urls, identities, count):
    result, requests = collection(monkeypatch, tmp_path, reservation_limit=limit, excluded_urls=urls, excluded_identities=identities)
    assert len(requests) == count and result["sources"] == [] and result["pdf_reservations"] == []


@pytest.mark.parametrize("status,raw", [(403, b"Complete refused response"), (206, PDF), (200, b"Not PDF content")])
def test_incomplete_or_refused_pdf_is_retained_without_promotion(tmp_path, monkeypatch, clock, status, raw):
    result, requests = collection(monkeypatch, tmp_path, status=status, raw=raw)
    assert len(requests) == 2 and not result["sources"] and len(result["pdf_reservations"]) == 1
    assert_retained(tmp_path, result["pdf_hint_attempts"][0], content=raw)


def test_publisher_redirect_is_retained_but_cannot_escape_the_exact_pdf(tmp_path, monkeypatch, clock):
    def respond(request):
        if str(request.url) == LANDING:
            return httpx.Response(200, content=HTML, headers={"content-type": "text/html"})
        assert str(request.url) == URL
        return httpx.Response(302, content=b"Literal redirect response", headers={"location": "https://other.example/paper.pdf"})
    requests = mocked(monkeypatch, respond)
    result = literature.collect([TITLE], tmp_path, pdf_candidates=[HINT])
    assert len(requests) == 2 and not result["sources"] and len(result["pdf_reservations"]) == 1
    attempt = result["pdf_hint_attempts"][0]
    assert attempt["status"] == "rejected"
    assert_retained(tmp_path, attempt["redirects"][0], content=b"Literal redirect response")


def test_publisher_private_dns_cannot_use_a_proxy_exception(tmp_path, monkeypatch, clock):
    requests = mocked(monkeypatch, lambda request: pytest.fail("Private publisher reached HTTP"))
    monkeypatch.setattr(literature.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443))])
    monkeypatch.setattr(literature, "getproxies_environment", lambda: {"https": "http://public-proxy"})
    result = literature.collect([TITLE], tmp_path, pdf_candidates=[HINT])
    assert not requests and not result["sources"] and not result["pdf_reservations"]


def test_publisher_hints_require_an_exact_requested_title_or_landing():
    with pytest.raises(ValueError, match="explicitly requested"):
        literature.normalize_portfolio_pdf_candidates([HINT], ["Related Electron studies"])
    assert literature.normalize_portfolio_pdf_candidates([HINT], [LANDING]) == [HINT]


@pytest.mark.parametrize("defect", ["metadata_bytes", "candidate", "identity", "page_count", "version", "discovery"])
def test_native_verification_rederives_identity_and_rejects_rehashed_forgeries(tmp_path, monkeypatch, clock, defect):
    ws = Workspace.create(tmp_path)
    result, _ = collection(monkeypatch, ws.path("research"))
    source = result["sources"][0]
    path = ws.path("research") / source["identity_path"]
    proof = json.loads(path.read_bytes())
    if defect == "metadata_bytes":
        metadata = ws.path("research") / source["metadata_path"]
        metadata.write_bytes(HTML.replace(b"Ada Lovelace", b"Someone Else"))
        source["metadata_sha256"] = proof["metadata_sha256"] = digest_file(metadata)
    elif defect == "candidate": proof["candidate"]["authors"] = ["Someone Else"]
    elif defect == "identity": proof["identity"]["title_range"]["end"] += 1
    elif defect == "page_count": source["page_count"] = proof["page_count"] = 2
    elif defect == "version": source["publication_version"] = "publishedVersion"
    else: source["discovery_url"] = URL
    write_json(path, proof)
    source["identity_sha256"] = digest_file(path)
    if defect == "version":
        assert not _verified_repository_pdf(ws, source)
    else:
        with pytest.raises(WorkflowError):
            _verified_repository_pdf(ws, source, [HINT])

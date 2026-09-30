import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
import threading

import httpx
import pytest

from paper_factory.literature import import_doi, search, verify_citation, verify_search
from paper_factory.models import Citation, Provenance, Study, StudyState
from paper_factory.workspace import Workspace


@pytest.fixture
def workspace(tmp_path):
    return Workspace.create(tmp_path / "workspace")


def work(doi="10.1234/reproducible", title="Actual bibliographic title"):
    return {"status": "ok", "message": {
        "DOI": doi,
        "title": [title],
        "author": [{"given": "Ada", "family": "Lovelace"}],
        "published": {"date-parts": [[2024, 4, 1]]},
    }}


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_doi_import_preserves_actual_metadata_and_raw_response(workspace):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=work())

    with client(handler) as api:
        citation = import_doi(workspace, "10.1234/REPRODUCIBLE", client=api)
    assert citation.title == "Actual bibliographic title"
    assert citation.authors == ["Ada Lovelace"]
    assert citation.year == 2024
    assert citation.verification_scope == "metadata_only"
    assert requests[0].url.host == "api.crossref.org"
    assert requests[0].url.raw_path == b"/works/10.1234%2Freproducible"
    raw = workspace.path(f"literature/{citation.id}.json").read_bytes()
    assert citation.metadata_sha256 == hashlib.sha256(raw).hexdigest()
    assert verify_citation(workspace, citation) == []
    assert workspace.get("citation", citation.id, Citation) == citation
    assert workspace.list("provenance", Provenance)[0].ai is False


@pytest.mark.parametrize("doi", ["https://attacker.invalid/a", "not-a-doi", "10.1234/../bad", "10.1234/a b", "10.1234/a\x00b"])
def test_invalid_doi_never_sends_a_request(workspace, doi):
    def handler(request):
        pytest.fail("Invalid DOI reached the HTTP transport")

    with client(handler) as api, pytest.raises(ValueError):
        import_doi(workspace, doi, client=api)


def test_injected_client_cannot_follow_provider_redirects(workspace):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": "https://attacker.invalid/metadata"})

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as api:
        with pytest.raises(ValueError, match="Crossref request failed"):
            import_doi(workspace, "10.1234/reproducible", client=api)
    assert len(requests) == 1
    assert requests[0].url.host == "api.crossref.org"


def test_query_hits_are_resolved_instead_of_used_as_verified_metadata(workspace):
    study = Study(project_id="project-test", title="Study", research_question="Question?", state=StudyState.EVIDENCE_READY)
    workspace.save("study", study)
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [
                {"DOI": "10.1234/reproducible", "title": ["Untrusted snippet title"]},
                {"DOI": "10.1234/missing"},
                {"title": ["Unidentified hit"]},
            ]}})
        if "missing" in request.url.path:
            return httpx.Response(404)
        return httpx.Response(200, json=work())

    with client(handler) as api:
        citations = search(workspace, "reproducibility evidence", study, client=api)
    assert len(citations) == 1
    assert citations[0].title == "Actual bibliographic title"
    assert requests[0].url.params["query.bibliographic"] == "reproducibility evidence"
    assert study.state == StudyState.EVIDENCE_READY
    assert study.novelty_status == "searched"
    assert study.citation_ids == [citations[0].id]
    audit = json.loads(workspace.path(f"literature/{study.literature_search_ids[0]}.json").read_text())
    assert audit["novelty_proven"] is False
    assert audit["resolved_ids"] == study.citation_ids
    assert audit["candidate_dois"] == ["10.1234/reproducible", "10.1234/missing"]
    assert audit["candidates"][1]["error"]
    assert audit["candidates"][2]["error"]
    assert verify_search(workspace, study.literature_search_ids[0], study.id) == []


def test_search_failure_is_audited_without_marking_novelty_searched(workspace):
    study = Study(project_id="project-test", title="Study", research_question="Question?")
    workspace.save("study", study)
    with client(lambda request: httpx.Response(503)) as api, pytest.raises(ValueError, match="Crossref request failed"):
        search(workspace, "query", study, client=api)
    assert study.novelty_status == "unassessed"
    assert study.literature_search_ids == []
    audits = list(workspace.path("literature").glob("search-*.json"))
    assert len(audits) == 1
    assert json.loads(audits[0].read_text())["status"] == "FAILED"
    assert any("did not succeed" in error for error in verify_search(workspace, audits[0].stem, study.id))


def test_sequential_searches_merge_current_study_instead_of_overwriting_stale_snapshot(workspace):
    study = Study(project_id="project-test", title="Study", research_question="Question?")
    workspace.save("study", study)
    stale = study.model_copy(deep=True)

    def handler(request):
        if request.url.path == "/works":
            key = request.url.params["query.bibliographic"]
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": f"10.1234/{key}"}]}})
        doi = "10.1234/" + request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=work(doi=doi, title=doi))

    with client(handler) as api:
        search(workspace, "first", study, client=api)
        current = workspace.get("study", study.id, Study)
        current.state = StudyState.EVIDENCE_READY
        current.human_subjects = True
        workspace.save("study", current)
        search(workspace, "second", stale, client=api)
    stored = workspace.get("study", study.id, Study)
    assert len(stored.literature_search_ids) == len(stored.citation_ids) == 2
    assert stored.state == StudyState.EVIDENCE_READY and stored.human_subjects
    assert stale.literature_search_ids == stored.literature_search_ids
    assert all(verify_search(workspace, id, stored.id) == [] for id in stored.literature_search_ids)


def test_competing_search_fails_explicitly_then_retry_preserves_both_searches(workspace):
    study = Study(project_id="project-test", title="Study", research_question="Question?")
    workspace.save("study", study)
    stale = study.model_copy(deep=True)
    entered, release = threading.Event(), threading.Event()

    def handler(request):
        if request.url.path == "/works":
            if request.url.params["query.bibliographic"] == "first":
                entered.set()
                assert release.wait(timeout=10)
            return httpx.Response(200, json={"status": "ok", "message": {"items": []}})
        pytest.fail("Empty query fixture must not resolve DOI metadata")

    with client(handler) as api, ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(search, workspace, "first", study, client=api)
        try:
            assert entered.wait(timeout=10)
            with pytest.raises(ValueError, match="already running"):
                search(workspace, "second", stale, client=api)
        finally:
            release.set()
        running.result(timeout=10)
        search(workspace, "second", stale, client=api)
    current = workspace.get("study", study.id, Study)
    assert len(current.literature_search_ids) == 2
    assert all(verify_search(workspace, id, current.id) == [] for id in current.literature_search_ids)


def test_unknown_study_cannot_start_external_literature_requests(workspace):
    with client(lambda _: pytest.fail("Unknown Study reached provider")) as api:
        with pytest.raises(ValueError, match="Unknown study"):
            search(workspace, "query", Study(project_id="project-test", title="Study", research_question="Question?"), client=api)


@pytest.mark.parametrize("field,value", [
    ("title", "Invented title"), ("authors", ["Invented Author"]),
    ("year", 1900), ("doi", "10.1234/different"),
    ("source_url", "https://attacker.invalid/metadata"), ("verified", False),
])
def test_independent_validation_rejects_tampered_citation_fields(workspace, field, value):
    with client(lambda request: httpx.Response(200, json=work())) as api:
        citation = import_doi(workspace, "10.1234/reproducible", client=api)
    setattr(citation, field, value)
    assert verify_citation(workspace, citation)


def test_independent_validation_detects_raw_metadata_tampering_and_loss(workspace):
    with client(lambda request: httpx.Response(200, json=work())) as api:
        citation = import_doi(workspace, "10.1234/reproducible", client=api)
    path = workspace.path(f"literature/{citation.id}.json")
    path.write_text(json.dumps(work(title="Changed source record")))
    assert any("SHA256" in error for error in verify_citation(workspace, citation))
    path.unlink()
    assert any("no raw metadata" in error for error in verify_citation(workspace, citation))


def test_retrieval_rejects_mismatched_doi_or_missing_author(workspace):
    with client(lambda request: httpx.Response(200, json=work(doi="10.1234/wrong"))) as api, pytest.raises(ValueError, match="different DOI"):
        import_doi(workspace, "10.1234/reproducible", client=api)
    incomplete = work()
    incomplete["message"].pop("author")
    with client(lambda request: httpx.Response(200, json=incomplete)) as api, pytest.raises(ValueError, match="no authors"):
        import_doi(workspace, "10.1234/reproducible", client=api)
    assert workspace.list("citation", Citation) == []


def test_metadata_updates_do_not_overwrite_previously_cited_evidence(workspace):
    with client(lambda request: httpx.Response(200, json=work())) as api:
        original = import_doi(workspace, "10.1234/reproducible", client=api)
    with client(lambda request: httpx.Response(200, json=work(title="Updated title"))) as api:
        updated = import_doi(workspace, "10.1234/reproducible", client=api)
    assert original.id != updated.id
    assert verify_citation(workspace, original) == []
    assert verify_citation(workspace, updated) == []


def perform_search(workspace, items=None):
    study = Study(project_id="project-test", title="Study", research_question="Question?")
    workspace.save("study", study)

    def handler(request):
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": items if items is not None else [{"DOI": "10.1234/reproducible"}]}})
        return httpx.Response(200, json=work())

    with client(handler) as api:
        search(workspace, "query", study, client=api)
    return study, study.literature_search_ids[0]


def test_successful_empty_query_is_auditable_without_proving_novelty(workspace):
    study, search_id = perform_search(workspace, [])
    assert study.citation_ids == []
    assert study.novelty_status == "searched"
    assert verify_search(workspace, search_id, study.id) == []


def test_unrecorded_search_id_is_not_valid_evidence(workspace):
    assert verify_search(workspace, "search-fabricated", "study-test")


@pytest.mark.parametrize("field,value", [
    ("status", "FAILED"), ("provider", "Invented provider"),
    ("study_id", "study-other"), ("source_url", "https://attacker.invalid/works"),
    ("query", "different query"), ("fetched_at", "2024-01-01T12:00:00"),
    ("candidate_dois", []), ("resolved_ids", []),
])
def test_search_audit_changes_cannot_pass_independent_review(workspace, field, value):
    study, search_id = perform_search(workspace)
    path = workspace.path(f"literature/{search_id}.json")
    audit = json.loads(path.read_bytes())
    audit[field] = value
    path.write_text(json.dumps(audit), encoding="utf-8")
    errors = verify_search(workspace, search_id, study.id)
    assert errors
    assert any("persisted record" in error for error in errors)


def test_search_raw_response_hash_and_citation_links_are_revalidated(workspace):
    study, search_id = perform_search(workspace)
    raw_path = workspace.path(f"literature/{search_id}-response.json")
    original = raw_path.read_bytes()
    raw_path.write_text(json.dumps({"status": "ok", "message": {"items": []}}), encoding="utf-8")
    assert any("SHA256" in error for error in verify_search(workspace, search_id, study.id))
    raw_path.write_bytes(original)
    study.citation_ids = []
    workspace.save("study", study)
    assert any("not linked" in error for error in verify_search(workspace, search_id, study.id))


def test_search_review_rejects_missing_citation_metadata(workspace):
    study, search_id = perform_search(workspace)
    workspace.path(f"literature/{study.citation_ids[0]}.json").unlink()
    assert any("no raw metadata" in error for error in verify_search(workspace, search_id, study.id))

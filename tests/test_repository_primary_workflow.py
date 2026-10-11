"""Synthetic repository PDF discovery is independently bound by the native host."""

import copy
import json

import pytest

from paper_factory.workflow import WorkflowError, _retained_primary_body, _verified_repository_pdf
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import digest_file, write_json
from test_autonomous_literature import clock
from test_openalex_discovery import collection
from test_public_pdf_hints import DOI, TEXT
from test_study_literature_followup import REASON, collector, initial, rejected
from test_workflow import STUDY_REVIEW, protocol, setup


def initial_repository(service, identifier, monkeypatch, mutate=None):
    plan = protocol(); plan["literature_queries"] = [DOI]
    service.submit_proposal(identifier, plan)
    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        assert queries == [DOI] and pdf_candidates is None and limit == 6
        evidence, _ = collection(monkeypatch, root)
        if mutate:
            mutate(evidence, root)
        return evidence
    service.collector = retrieve
    return service.collect_literature(identifier)


def test_initial_repository_body_selection_and_approval_bind_exact_originals(setup, monkeypatch, clock):
    service, runner, identifier = setup
    state = initial_repository(service, identifier, monkeypatch)
    source, = state["literature"]["sources"]
    ws = service._workspace(identifier)
    record = ws.latest("workflow", Workflow)
    assert source["publication_version"] == "unknown" and _verified_repository_pdf(ws, source)
    assert _retained_primary_body(ws, record, source, state["literature"])
    material, = state["material_manifest"]["literature"]
    assert material["sha256"] == source["text_sha256"]
    # Select an exact unique body quote spanning existing automatic chunks.
    start = TEXT.index("methods are retained")
    literal = TEXT[start:start + 180]
    # Repetition is deliberately rejected, even when the same phrase was read.
    with pytest.raises(WorkflowError):
        service.select_literature_passages(identifier, [{"source_id": source["id"], "text_sha256": source["text_sha256"],
            "text": literal, "relevance": "Synthetic publication-copy reading does not claim any real scientific quality."}])
    review = copy.deepcopy(STUDY_REVIEW)
    review["selected_sources"][0]["source_id"] = source["id"]
    review["publication_readiness"]["closest_work"][0].update(source_id=source["id"], quote=source["excerpts"][0][:100])
    approved = service.submit_study_review(identifier, review)
    assert approved["stage"] == "planned" and approved["execution_attempt"] == runner.calls == 0
    service._require_study_review(ws, ws.latest("workflow", Workflow))


@pytest.mark.parametrize("defect", ["claimed_location", "candidate", "identity", "redirect", "origin", "version", "discovery_origin", "missing_attempt", "missing_mode", "cap"])
def test_repository_forgeries_never_promote_and_keep_actual_retrieval_files(setup, monkeypatch, clock, defect):
    service, runner, identifier = setup
    retained = {}
    def mutate(evidence, root):
        source = evidence["sources"][0]
        proof_path = root / source["identity_path"]
        proof = json.loads(proof_path.read_bytes())
        if defect == "claimed_location": proof["discovery"]["location_index"] += 1
        elif defect == "candidate": proof["candidate"]["doi"] = "10.1234/another"
        elif defect == "identity": proof["identity"]["doi_ranges"] = []
        elif defect == "redirect": proof["redirects"] = [{"url": source["url"], "status": 302, "location": "https://private.invalid/file.pdf"}]
        elif defect == "origin": source["url"] = "https://zenodo.org/records/999/files/another.pdf"
        elif defect == "version": source["publication_version"] = "accepted"
        elif defect == "discovery_origin": source["discovery_url"] += "?api_key=unverified"
        elif defect == "missing_attempt": evidence["pdf_hint_attempts"] = []
        elif defect == "missing_mode": evidence.pop("pdf_discovery_mode")
        else: evidence["pdf_hint_attempts"] *= 3
        write_json(proof_path, proof)
        source["identity_sha256"] = digest_file(proof_path)
        for attempt in evidence["pdf_hint_attempts"]:
            if attempt.get("identity_path") == source["identity_path"]:
                attempt["identity_sha256"] = source["identity_sha256"]
        retained.update({path.relative_to(root).as_posix(): path.read_bytes() for path in (root / "literature").rglob("*") if path.is_file()})
    with pytest.raises(WorkflowError) as rejected:
        initial_repository(service, identifier, monkeypatch, mutate)
    assert rejected.value.code in {"PUBLICATION_EVIDENCE_INVALID", "LITERATURE_SOURCE_LIMIT"}
    state = service.status(identifier)
    assert "literature" not in state["artifacts"] and state["execution_attempt"] == runner.calls == 0
    assert all(any(artifact["sha256"] == digest_file(service._workspace(identifier).path("research") / name)
                   for artifact in state["artifacts"].values()) for name in retained)
    assert all((service._workspace(identifier).path("research") / name).read_bytes() == raw for name, raw in retained.items())


def test_new_ordinary_followup_discovers_exact_metadata_copy_without_reset_or_rerun(setup, monkeypatch, clock):
    service, runner, identifier, old = initial(setup)
    original = {key: service.artifact_path(identifier, key).read_bytes() for key in ("proposal", "study-review-1", "literature")}
    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        assert queries == [DOI] and pdf_candidates is None and limit == 3
        evidence, _ = collection(monkeypatch, root)
        return evidence
    service.collector = retrieve
    state = service.collect_study_literature(identifier, [DOI], REASON, [])
    source = next(source for source in state["literature"]["sources"] if source.get("doi") == DOI)
    assert _verified_repository_pdf(service._workspace(identifier), source)
    assert state["study_literature_pending"] and state["study_literature_attempt"] == 1
    assert state["proposal_attempt"] == old["proposal_attempt"] == 1
    assert state["execution_attempt"] == runner.calls == 0
    assert all(service.artifact_path(identifier, key).read_bytes() == original[key] for key in ("proposal", "study-review-1"))
    assert service.artifact_path(identifier, "literature-history-" + old["artifacts"]["literature"]["sha256"]).read_bytes() == original["literature"]


@pytest.mark.parametrize("defect", [None, "reserved_title", "missing_attempt", "cap"])
def test_final_reserved_attempt_verifies_repository_identity_and_preserves_budget(setup, monkeypatch, clock, defect):
    service, runner, identifier, _ = initial(setup)
    service.collector = collector(no_sources=True)
    for number in (1, 2):
        service.collect_study_literature(identifier, ["Synthetic no-result related methods " + str(number)], REASON, [])
    before = service.status(identifier)
    kept = service.artifact_path(identifier, "study-review-1").read_bytes()
    hint = {"doi": DOI, "title": "Different reserved complete title" if defect == "reserved_title" else "Verified record title"}
    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        assert queries == [DOI] and pdf_candidates == [hint] and limit == 3
        # A forged collector cannot use a different unreserved whole title.
        evidence, _ = collection(monkeypatch, root, candidates=None if defect in {"reserved_title", "missing_attempt", "cap"} else pdf_candidates)
        if defect == "missing_attempt": evidence["pdf_hint_attempts"] = []
        elif defect == "cap": evidence["pdf_hint_attempts"] *= 3
        return evidence
    service.collector = retrieve
    if defect is not None:
        with pytest.raises(WorkflowError) as failed:
            service.collect_study_literature(identifier, [DOI], REASON, [hint])
        assert failed.value.code in {"PUBLICATION_EVIDENCE_INVALID", "LITERATURE_SOURCE_LIMIT"}
        state = service.status(identifier)
        assert state["artifacts"]["literature"] == before["artifacts"]["literature"]
    else:
        state = service.collect_study_literature(identifier, [DOI], REASON, [hint])
        source = next(source for source in state["literature"]["sources"] if source.get("doi") == DOI)
        assert _verified_repository_pdf(service._workspace(identifier), source, [hint])
        assert state["study_literature_pending"]
        assert state["study_review"] == before["study_review"]
    assert state["study_literature_attempt"] == 3 and state["proposal_attempt"] == before["proposal_attempt"]
    assert service.artifact_path(identifier, "study-review-1").read_bytes() == kept
    assert state["execution_attempt"] == runner.calls == 0

"""Synthetic retained author-copy plumbing; no scholarly judgment or network access."""
import hashlib
import json
import shutil

import pytest

from paper_factory.workflow import WorkflowError, _verified_author_pdf
from paper_factory.workspace import digest_file, write_json
from test_autonomous_literature import clock
from test_initial_author_pdf_discovery import bibliographic, work
from test_public_pdf_hints import DOI, LISTING
from test_workflow import collect, protocol, reject_for_redesign, setup


def initial(service, identifier, monkeypatch, *, mutate=None):
    plan = protocol(); plan["literature_queries"] = ["selective recovery comparison"]
    service.submit_proposal(identifier, plan)
    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        assert queries == plan["literature_queries"] and pdf_candidates is None
        evidence, requests = bibliographic(monkeypatch, root, {DOI: work()}, LISTING)
        assert len(requests) == 4
        if mutate: mutate(evidence, root)
        return evidence
    service.collector = retrieve
    return service.collect_literature(identifier)


def test_fresh_metadata_author_copy_is_independently_verified_before_packet_promotion(setup, monkeypatch, clock):
    service, runner, identifier = setup
    state = initial(service, identifier, monkeypatch)
    source, = state["literature"]["sources"]
    assert source["scope"] == "full_text" and source["publication_version"] == "unknown"
    assert _verified_author_pdf(service._workspace(identifier), source)
    assert (state["stage"], state["execution_attempt"], state["study_literature_attempt"]) == ("proposed", 0, 0)
    for field, digest in (("raw_path", "sha256"), ("metadata_path", "metadata_sha256"), ("text_path", "text_sha256"),
                          ("identity_path", "identity_sha256"), ("discovery_path", "discovery_sha256")):
        assert any(item["sha256"] == source[digest] for item in state["artifacts"].values())
    assert runner.calls == 0


@pytest.mark.parametrize("defect", ["candidate", "listing", "identity", "redirect", "origin", "cap", "reservation", "missing_attempt", "missing_mode", "wrong_mode"])
def test_initial_author_copy_forgery_cannot_promote_a_packet_and_keeps_raw(setup, monkeypatch, clock, defect):
    service, runner, identifier = setup
    retained = {}
    def mutate(evidence, root):
        source = evidence["sources"][0]
        proof_path = root / source["identity_path"]
        proof = json.loads(proof_path.read_bytes())
        if defect == "candidate": proof["candidate"]["title"] = "A different unverified scholarly identity"
        elif defect == "listing": proof["discovery"]["leaf_index"] += 1
        elif defect == "identity": proof["identity"]["doi_ranges"] = []
        elif defect == "redirect": proof["redirects"] = [{"url": proof["retrieved_url"], "status": 302, "location": "https://elsewhere.example/unsupported.pdf"}]
        elif defect == "origin": source["url"] = "https://www.cs.cmu.edu/~NatProg/papers/different.pdf"
        elif defect == "cap": evidence["pdf_hint_attempts"] *= 3
        elif defect == "reservation": evidence["pdf_hint_attempts"][0].pop("pdf_attempted")
        elif defect == "missing_attempt": evidence["pdf_hint_attempts"] = []
        elif defect == "missing_mode": evidence.pop("pdf_discovery_mode")
        else: evidence["pdf_discovery_mode"] = "unsupported_unreserved_origin"
        write_json(proof_path, proof); source["identity_sha256"] = digest_file(proof_path)
        for attempt in evidence["pdf_hint_attempts"]:
            if attempt.get("identity_path") == source["identity_path"]:
                attempt["identity_sha256"] = source["identity_sha256"]
        retained.update({path.relative_to(root).as_posix(): path.read_bytes() for path in (root / "literature").rglob("*") if path.is_file()})
    with pytest.raises(WorkflowError) as rejected:
        initial(service, identifier, monkeypatch, mutate=mutate)
    assert rejected.value.code in {"PUBLICATION_EVIDENCE_INVALID", "LITERATURE_SOURCE_LIMIT"}
    state = service.status(identifier)
    assert "literature" not in state["artifacts"] and runner.calls == 0
    ws = service._workspace(identifier)
    assert all((ws.path("research") / path).read_bytes() == raw for path, raw in retained.items())
    assert all(any(row["sha256"] == hashlib.sha256(raw).hexdigest() for row in state["artifacts"].values()) for raw in retained.values())


def test_nonfresh_collection_retry_explicitly_disables_automatic_author_discovery(setup):
    service, runner, identifier = setup
    service.submit_proposal(identifier, protocol())
    calls = []
    def retrieve(queries, root, **kwargs):
        calls.append(kwargs["pdf_candidates"])
        assert kwargs["limit"] == (6 if len(calls) == 1 else 5)
        evidence = collect(queries, root, limit=6, cancel=kwargs["cancel"])
        evidence["timed_out"] = len(calls) == 1
        return evidence
    service.collector = retrieve
    with pytest.raises(WorkflowError, match="timed-out"): service.collect_literature(identifier)
    service.collect_literature(identifier)
    assert calls == [None, []] and runner.calls == 0


def test_authoring_collection_explicitly_disables_initial_author_discovery(setup):
    service, runner, identifier = setup
    reject_for_redesign(service, identifier)
    def retrieve(queries, root, **kwargs):
        assert kwargs["pdf_candidates"] == []
        return collect(queries, root, limit=kwargs["limit"], cancel=kwargs["cancel"])
    service.collector = retrieve
    state = service.collect_authoring_literature(identifier, ["Another synthetic closest-work methods question"])
    assert state["execution_attempt"] == 1 and runner.calls == 1


def test_new_authoring_collection_cannot_promote_even_a_valid_unreserved_author_body(setup, monkeypatch, clock, tmp_path):
    service, runner, identifier = setup
    prior = reject_for_redesign(service, identifier)
    old_raw = service.artifact_path(identifier, "observations").read_bytes()
    retained = {}
    def retrieve(queries, root, **kwargs):
        assert kwargs["pdf_candidates"] == []
        control = tmp_path / "positive-control"
        evidence, _ = bibliographic(monkeypatch, control, {DOI: work()}, LISTING)
        assert evidence["sources"] and evidence["sources"][0]["scope"] == "full_text", json.dumps(evidence["warnings"])
        for path in (control / "literature").iterdir():
            target = root / "literature" / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        retained.update({path.relative_to(root).as_posix(): path.read_bytes() for path in (root / "literature").rglob("*") if path.is_file()})
        return evidence
    service.collector = retrieve
    with pytest.raises(WorkflowError) as rejected:
        service.collect_authoring_literature(identifier, ["Another synthetic closest-work methods question"])
    assert rejected.value.code == "PUBLICATION_EVIDENCE_INVALID"
    state = service.status(identifier)
    assert "authoring-literature" not in state["artifacts"] and state["execution_attempt"] == 1 and runner.calls == 1
    assert service.artifact_path(identifier, "observations").read_bytes() == old_raw
    assert all(state["artifacts"][key] == value for key, value in prior["artifacts"].items())
    assert all(any(row["sha256"] == hashlib.sha256(raw).hexdigest() for row in state["artifacts"].values()) for raw in retained.values())

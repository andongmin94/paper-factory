"""Synthetic exact-primary reuse contracts; no network or scholarly approval."""

import copy
import hashlib
import pytest

from paper_factory.autonomous import literature
from paper_factory.workflow import WorkflowError, _completed_literature_queries, _has_new_literature, _retained_primary_body
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import digest_file
from test_autonomous_literature import clock
from test_initial_author_pdf_workflow import initial
from test_public_pdf_hints import DOI
from test_workflow import (STUDY_REVIEW, SYNTHETIC_PREFIX, SYNTHETIC_SUFFIX, collect, collect_arxiv_preprint,
                           protocol, rejected_study_review, setup)


ID = "1311.3903v1"
QUERY = "arxiv:" + ID
TITLE = "Synthetic exact-version preprint retention fixture"


def preprint(service, identifier, *, versions=(ID,), mutate=None):
    plan = protocol()
    plan["literature_queries"] = ["arxiv:" + version for version in versions]
    service.submit_proposal(identifier, plan)

    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        assert limit == 6 and pdf_candidates is None
        packet = {"sources": [], "searches": [], "warnings": []}
        for version in versions:
            evidence = collect_arxiv_preprint(["arxiv:" + version], root, limit=6, cancel=cancel, arxiv_id=version)
            if mutate:
                mutate(evidence, root)
            packet["sources"].extend(evidence["sources"])
            packet["searches"].extend(evidence["searches"])
        return packet

    service.collector = retrieve
    return service.collect_literature(identifier)


def revise(service, identifier, state, queries):
    service.submit_study_review(identifier, rejected_study_review())
    old_path = service.artifact_path(identifier, "literature")
    old_bytes = old_path.read_bytes()
    proposal = copy.deepcopy(state["proposal"])
    proposal["expected_contribution"] += " A different synthetic contribution must resolve the retained critique."
    proposal["literature_queries"] = queries
    proposed = service.submit_proposal(identifier, proposal)
    assert proposed["study_review"] is None and "literature" not in proposed["artifacts"]
    return old_path, old_bytes


def approve_reused(service, identifier, state):
    source = state["literature"]["sources"][0]
    review = copy.deepcopy(STUDY_REVIEW)
    review["selected_sources"][0]["source_id"] = source["id"]
    review["publication_readiness"]["closest_work"][0]["source_id"] = source["id"]
    review["publication_readiness"]["closest_work"][0]["quote"] = source["excerpts"][0][:100]
    return service.submit_study_review(identifier, review)


@pytest.mark.parametrize("query", [QUERY, "DOI: 10.48550/arXiv." + ID, TITLE])
def test_exact_retained_primary_replaces_network_query_but_requires_fresh_review(setup, query):
    service, runner, identifier = setup
    original = preprint(service, identifier)
    source = original["literature"]["sources"][0]
    old_path, old_bytes = revise(service, identifier, original, [query])

    def forbidden(*args, **kwargs):
        pytest.fail("An explicitly retained verified body must not repeat network retrieval")

    service.collector = forbidden
    state = service.collect_literature(identifier)
    packet = state["literature"]
    assert packet["sources"] == [source] and packet["searches"] == []
    receipt, = packet["retained_queries"]
    assert receipt == {"query": query, "source_id": source["id"],
        "artifact_id": "literature-history-" + hashlib.sha256(old_bytes).hexdigest(),
        "sha256": hashlib.sha256(old_bytes).hexdigest(), "size": len(old_bytes),
        "proposal_sha256": state["artifacts"]["proposal"]["sha256"]}
    assert state["stage"] == "proposed" and state["study_review"] is None and runner.calls == 0
    assert old_path.read_bytes() == old_bytes
    assert service.collect_literature(identifier)["artifacts"]["literature"] == state["artifacts"]["literature"]
    accepted = approve_reused(service, identifier, state)
    assert accepted["stage"] == "planned" and accepted["proposal_attempt"] == 2 and runner.calls == 0
    assert service.artifact_path(identifier, "study-review-1").read_bytes() != service.artifact_path(identifier, "study-review-2").read_bytes()
    ws = service._workspace(identifier)
    service._require_study_review(ws, ws.latest("workflow", Workflow))


def test_retained_body_counts_toward_six_and_only_missing_queries_are_fetched(setup):
    service, runner, identifier = setup
    original = preprint(service, identifier)
    old_path, old_bytes = revise(service, identifier, original, [QUERY, "new independently relevant method query"])
    calls = []

    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        calls.append((queries, limit, pdf_candidates))
        packet = collect(queries, root, limit=6, cancel=cancel)
        packet["sources"] = [{**packet["sources"][0], "id": f"new-reading-{index}"} for index in range(5)]
        # An untrusted collector cannot manufacture a native reuse receipt.
        packet["retained_queries"] = [{"query": "injected approval", "source_id": "invented"}]
        return packet

    service.collector = retrieve
    state = service.collect_literature(identifier)
    assert calls == [(["new independently relevant method query"], 5, None)]
    assert len(state["literature"]["sources"]) == 6
    assert [row["query"] for row in state["literature"]["retained_queries"]] == [QUERY]
    assert [row["query"] for row in state["literature"]["searches"]] == ["new independently relevant method query"]
    assert old_path.read_bytes() == old_bytes and state["study_literature_attempt"] == 0 and runner.calls == 0


@pytest.mark.parametrize("query", ["arxiv:1311.3903", "arxiv:1311.3903v2", "Synthetic exact-version",
    "methods using DOI: 10.48550/arXiv." + ID, "preprint " + QUERY, "independent software oracle methods", "DOI: 10.1234/../invalid"])
def test_unversioned_wrong_version_partial_title_and_keywords_do_not_reuse(setup, query):
    service, runner, identifier = setup
    original = preprint(service, identifier)
    revise(service, identifier, original, [query])
    calls = []

    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        calls.append((queries, limit))
        return collect(queries, root, limit=limit, cancel=cancel)

    service.collector = retrieve
    state = service.collect_literature(identifier)
    assert calls == [([query], 6)] and "retained_queries" not in state["literature"] and runner.calls == 0


@pytest.mark.parametrize("defect", ["abstract", "metadata", "body_range", "excerpt", "metadata_identity", "not_pdf"])
def test_nonprimary_or_unproved_retained_source_does_not_suppress_a_fresh_lookup(setup, defect):
    service, runner, identifier = setup

    def mutate(packet, root):
        source = packet["sources"][0]
        if defect == "abstract": source["scope"] = "abstract"
        elif defect == "metadata": source.update(scope="metadata_only", excerpts=[])
        elif defect == "body_range": source["body_range"]["start"] += 1
        elif defect == "excerpt": source["excerpts"][0] = "Uninspected invented passage " * 10
        elif defect == "metadata_identity": source["title"] = "Another full title than the retained metadata"
        else:
            path = root / source["raw_path"]
            path.write_bytes(b"This is not a PDF")
            source["sha256"] = digest_file(path)

    if defect == "metadata":
        with pytest.raises(WorkflowError): preprint(service, identifier, mutate=mutate)
        original = service.status(identifier)
    else:
        original = preprint(service, identifier, mutate=mutate)
    revise(service, identifier, original, [QUERY])
    calls = []

    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        calls.append(limit)
        return collect(queries, root, limit=limit, cancel=cancel)

    service.collector = retrieve
    state = service.collect_literature(identifier)
    assert calls == [6] and "retained_queries" not in state["literature"] and runner.calls == 0


def test_equal_whole_title_across_versions_is_ambiguous_and_does_not_reuse(setup):
    service, runner, identifier = setup
    original = preprint(service, identifier, versions=(ID, "1311.3903v2"))
    revise(service, identifier, original, [TITLE])
    calls = []

    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        calls.append(limit)
        return collect(queries, root, limit=limit, cancel=cancel)

    service.collector = retrieve
    assert "retained_queries" not in service.collect_literature(identifier)["literature"]
    assert calls == [6] and runner.calls == 0


@pytest.mark.parametrize("field", ["history", "raw_path", "metadata_path", "text_path"])
def test_missing_or_changed_frozen_history_and_body_fail_closed_before_network(setup, field):
    service, runner, identifier = setup
    original = preprint(service, identifier)
    old_path, old_bytes = revise(service, identifier, original, [QUERY])
    if field == "history": old_path.unlink()
    else:
        source = original["literature"]["sources"][0]
        path = service._workspace(identifier).path("research/" + source[field])
        path.write_bytes(path.read_bytes() + b"tampered")
    service.collector = lambda *args, **kwargs: pytest.fail("Frozen corruption must stop before network")
    with pytest.raises(WorkflowError) as rejected: service.collect_literature(identifier)
    assert rejected.value.code == "ARTIFACT_CHANGED" and runner.calls == 0


@pytest.mark.parametrize("flag", ["cancelled", "timed_out", "rate_limited"])
def test_retained_queries_do_not_hide_incomplete_new_queries_and_retry_disables_auto_pdf(setup, flag):
    service, runner, identifier = setup
    original = preprint(service, identifier)
    revise(service, identifier, original, [QUERY, "new method evidence query"])
    calls = []

    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        calls.append((queries, limit, pdf_candidates))
        packet = collect(queries, root, limit=6, cancel=cancel)
        packet[flag] = len(calls) == 1
        return packet

    service.collector = retrieve
    with pytest.raises(WorkflowError): service.collect_literature(identifier)
    state = service.collect_literature(identifier)
    assert calls == [(["new method evidence query"], 5, None), ([QUERY, "new method evidence query"], 4, [])]
    assert len(state["literature"]["sources"]) == 2 and len(state["literature"]["retained_queries"]) == 1 and runner.calls == 0


def test_reuse_is_not_new_body_and_cannot_reopen_same_proposal_review(setup):
    service, runner, identifier = setup
    original = preprint(service, identifier)
    revise(service, identifier, original, [QUERY])
    service.collector = lambda *args, **kwargs: pytest.fail("Only retained reading is requested")
    state = service.collect_literature(identifier)
    ws = service._workspace(identifier)
    assert not _has_new_literature(ws, state["literature"], original["literature"])
    service.submit_study_review(identifier, rejected_study_review())
    with pytest.raises(WorkflowError) as rejected: service.submit_study_review(identifier, rejected_study_review())
    assert rejected.value.code == "REVIEW_EVIDENCE_CONFLICT" and runner.calls == 0


def test_exact_author_copy_reuses_original_reservation_and_independent_identity(setup, monkeypatch, clock):
    service, runner, identifier = setup
    original = initial(service, identifier, monkeypatch)
    source = original["literature"]["sources"][0]
    old_path, old_bytes = revise(service, identifier, original, [DOI])
    service.collector = lambda *args, **kwargs: pytest.fail("Retained author copy must not request a second PDF")
    state = service.collect_literature(identifier)
    assert state["literature"]["sources"] == [source]
    assert state["literature"]["searches"] == [] and "pdf_hint_attempts" not in state["literature"]
    assert source["publication_version"] == "unknown" and old_path.read_bytes() == old_bytes
    assert state["study_literature_attempt"] == 0 and runner.calls == 0
    assert approve_reused(service, identifier, state)["stage"] == "planned"


@pytest.mark.parametrize("field", ["proposal_sha256", "sha256", "size", "source_id", "query", "artifact_id"])
def test_query_completion_revalidates_native_origin_binding(setup, field):
    service, runner, identifier = setup
    original = preprint(service, identifier)
    revise(service, identifier, original, [QUERY])
    state = service.collect_literature(identifier)
    packet = copy.deepcopy(state["literature"])
    packet["retained_queries"][0][field] = 1 if field == "size" else "forged"
    ws = service._workspace(identifier)
    record = ws.latest("workflow", Workflow)
    with pytest.raises(WorkflowError) as rejected: _completed_literature_queries(ws, record, packet)
    assert rejected.value.code == "PUBLICATION_EVIDENCE_INVALID" and runner.calls == 0


@pytest.mark.parametrize("field", ["year", "published", "updated"])
def test_retained_query_rejects_current_bibliographic_date_tampering(setup, field):
    service, runner, identifier = setup
    original = preprint(service, identifier)
    revise(service, identifier, original, [QUERY])
    state = service.collect_literature(identifier)
    packet = copy.deepcopy(state["literature"])
    packet["sources"][0][field] = 2025 if field == "year" else "2025-01-01T00:00:00Z"
    ws = service._workspace(identifier)
    with pytest.raises(WorkflowError) as rejected:
        _completed_literature_queries(ws, ws.latest("workflow", Workflow), packet)
    assert rejected.value.code == "PUBLICATION_EVIDENCE_INVALID" and runner.calls == 0


def test_collector_cannot_inject_completion_for_an_unattempted_new_query(setup):
    service, runner, identifier = setup
    service.submit_proposal(identifier, protocol())

    def retrieve(queries, root, **kwargs):
        packet = collect(queries, root, limit=6, cancel=kwargs["cancel"])
        packet["searches"][0].update(status="not_attempted", attempted=False)
        packet["retained_queries"] = [{"query": queries[0], "source_id": "fixture-oracle"}]
        return packet

    service.collector = retrieve
    with pytest.raises(WorkflowError) as rejected: service.collect_literature(identifier)
    assert rejected.value.code == "LITERATURE_QUERIES_INCOMPLETE"
    assert "retained_queries" not in service.status(identifier)["literature"] and runner.calls == 0


def test_retention_and_new_sources_cannot_exceed_six(setup):
    service, runner, identifier = setup
    original = preprint(service, identifier)
    revise(service, identifier, original, [QUERY, "new unrelated method query"])

    def retrieve(queries, root, **kwargs):
        assert kwargs["limit"] == 5
        packet = collect(queries, root, limit=6, cancel=kwargs["cancel"])
        packet["sources"] = [{**packet["sources"][0], "id": f"oversized-{index}"} for index in range(6)]
        return packet

    service.collector = retrieve
    with pytest.raises(WorkflowError) as rejected: service.collect_literature(identifier)
    assert rejected.value.code == "LITERATURE_SOURCE_LIMIT" and runner.calls == 0


def test_eight_exact_queries_complete_without_silently_reusing_more_than_six_sources(setup):
    service, runner, identifier = setup
    versions = [f"1311.3903v{index}" for index in range(1, 10)]
    original = preprint(service, identifier, versions=versions[:6])
    service.submit_study_review(identifier, rejected_study_review())

    def supplement(queries, root, *, limit, cancel, pdf_candidates):
        assert limit == 3 and pdf_candidates == []
        packet = {"sources": [], "searches": []}
        for query in queries:
            evidence = collect_arxiv_preprint([query], root, limit=3, cancel=cancel, arxiv_id=query.removeprefix("arxiv:"))
            packet["sources"].extend(evidence["sources"])
            packet["searches"].extend(evidence["searches"])
        return packet

    service.collector = supplement
    supplemented = service.collect_study_literature(identifier, ["arxiv:" + version for version in versions[6:]],
        "Synthetic exact identity capacity fixture; no scholarly relevance or new approval is claimed.", [])
    assert not supplemented["study_literature_pending"]
    proposal = copy.deepcopy(original["proposal"])
    proposal["expected_contribution"] += " A different synthetic contribution preserves bounded retained readings."
    proposal["literature_queries"] = ["arxiv:" + version for version in versions[:8]]
    service.submit_proposal(identifier, proposal)
    calls = []

    def zero_budget(queries, root, *, limit, cancel, pdf_candidates):
        calls.append((queries, limit, pdf_candidates))
        return {"sources": [], "searches": [{"query": query, "status": "succeeded", "attempted": True, "resolved_ids": []}
                                            for query in queries]}

    service.collector = zero_budget
    state = service.collect_literature(identifier)
    assert calls == [(["arxiv:" + version for version in versions[6:8]], 0, [])]
    packet = state["literature"]
    assert len(packet["sources"]) == 6 and len(packet["retained_queries"]) == 6 and len(packet["searches"]) == 2
    assert state["study_literature_attempt"] == 1 and state["proposal_attempt"] == 2 and runner.calls == 0
    ws = service._workspace(identifier)
    assert _completed_literature_queries(ws, ws.latest("workflow", Workflow), packet) == set(proposal["literature_queries"])


def test_targeted_new_body_upgrade_preserves_retained_query_completion_and_requires_new_review(setup):
    service, runner, identifier = setup
    original = preprint(service, identifier)
    old_path, old_bytes = revise(service, identifier, original, [QUERY])
    retained = service.collect_literature(identifier)
    service.submit_study_review(identifier, rejected_study_review())
    fresh_passage = "A separately retained synthetic body passage adds different inspected methods for the orchestration contract. " * 3

    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        assert limit == 3 and pdf_candidates == []
        packet = collect_arxiv_preprint(queries, root, limit=3, cancel=cancel)
        source = packet["sources"][0]
        text = SYNTHETIC_PREFIX + fresh_passage + SYNTHETIC_SUFFIX
        path = root / "literature/new-body-upgrade.txt"
        path.write_bytes(text.encode())
        source.update(text_path="literature/new-body-upgrade.txt", text_sha256=digest_file(path), text_chars=len(text),
            excerpts=[fresh_passage], body_range=literature.full_text_body_range(text),
            excerpt_ranges=[{"start": len(SYNTHETIC_PREFIX), "end": len(SYNTHETIC_PREFIX) + len(fresh_passage)}])
        packet["retained_queries"] = [{"query": "forged native query"}]
        return packet

    service.collector = retrieve
    state = service.collect_study_literature(identifier, [QUERY],
        "An independently retained synthetic body upgrade exercises a fresh review without reusing approval.", [])
    assert state["study_literature_pending"] and state["study_literature_attempt"] == 1
    assert state["literature"]["retained_queries"] == retained["literature"]["retained_queries"]
    assert state["literature"]["sources"][0]["excerpts"] == [fresh_passage]
    accepted = approve_reused(service, identifier, state)
    assert accepted["stage"] == "planned" and "study-review-2-literature-1" in accepted["artifacts"]
    assert old_path.read_bytes() == old_bytes and runner.calls == 0


def test_reuse_seed_does_not_disable_fresh_author_pdf_reservation_cap(setup):
    service, runner, identifier = setup
    original = preprint(service, identifier)
    revise(service, identifier, original, [QUERY, "additional directly related method query"])

    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        assert limit == 5 and pdf_candidates is None
        packet = collect(queries, root, limit=6, cancel=cancel)
        packet.update(pdf_discovery_mode="initial_metadata", pdf_hint_attempts=[{"pdf_attempted": True}] * 3)
        return packet

    service.collector = retrieve
    with pytest.raises(WorkflowError) as rejected: service.collect_literature(identifier)
    assert rejected.value.code == "LITERATURE_SOURCE_LIMIT" and runner.calls == 0


def test_current_author_copy_identity_is_rechecked_at_retained_query_boundary(setup, monkeypatch, clock):
    service, runner, identifier = setup
    original = initial(service, identifier, monkeypatch)
    revise(service, identifier, original, [DOI])
    state = service.collect_literature(identifier)
    packet = copy.deepcopy(state["literature"])
    packet["sources"][0]["url"] = "https://www.cs.cmu.edu/~NatProg/papers/another.pdf"
    ws = service._workspace(identifier)
    with pytest.raises(WorkflowError) as rejected:
        _completed_literature_queries(ws, ws.latest("workflow", Workflow), packet)
    assert rejected.value.code == "PUBLICATION_EVIDENCE_INVALID" and runner.calls == 0


@pytest.mark.parametrize("field", ["identity_path", "identity_sha256", "publication_version", "year"])
def test_retained_author_origin_rejects_missing_identity_and_unknown_version_contract(setup, monkeypatch, clock, field):
    service, runner, identifier = setup
    state = initial(service, identifier, monkeypatch)
    source = copy.deepcopy(state["literature"]["sources"][0])
    if field == "publication_version": source[field] = "published_version"
    elif field == "year": source[field] += 1
    else: source.pop(field)
    ws = service._workspace(identifier)
    assert not _retained_primary_body(ws, ws.latest("workflow", Workflow), source, state["literature"])
    assert runner.calls == 0

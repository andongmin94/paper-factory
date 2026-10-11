"""Bounded provisional retrieval fixtures establish no actual scientific merit."""
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from paper_factory import ipc, workflow as native_workflow
from paper_factory.autonomous import literature
from paper_factory.autonomous.models import FrozenArtifact
from paper_factory.workflow import WorkflowError
from paper_factory.workflow_models import Workflow
from test_planned_claim_projection import COUNTERS
from test_redesign_admission_feedback import held
from test_preexecution_redesign import attach_validation, review as preparation_review
from test_study_repair import successor_repair
from test_redesign_question_preparation import (
    assert_originals, frozen_originals, workflow_comparison, workflow_routes,
)
from test_workflow import collect_arxiv_preprint, setup
from test_autonomous_literature import clock
from test_openalex_discovery import collection as repository_collection


def prepared_hold(setup):
    service, runner, identifier, before, proposed, *_ = held(setup)
    routes = workflow_routes(proposed)
    state = service.prepare_redesign_questions(identifier, routes)
    comparison = workflow_comparison(state, routes, selected=None)
    state = service.select_redesign_question(identifier, comparison)
    return service, runner, identifier, state, routes, proposed


def collector(calls, *, mode="new", arxiv_id="1311.3903v2", source_id=None):
    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        calls.append({"queries": queries, "limit": limit, "pdf_candidates": pdf_candidates})
        packet = collect_arxiv_preprint(queries, root, limit=limit, cancel=cancel, arxiv_id=arxiv_id)
        source = packet["sources"][0]
        if source_id is not None:
            source["id"] = source_id
        source["queries"] = list(queries)
        if mode != "same":
            text = (root / source["text_path"]).read_bytes().decode("utf-8")
            text = text.replace(" ", "  ") if mode == "whitespace" else text.replace(
                "\nReferences", "\nAdditional synthetic retained body for provisional evidence binding. " * 5 + "\nReferences")
            literature._retain_full_text(source, root, text, source["url"], source["raw_path"], source["sha256"])
        if mode == "exception":
            raise OSError("Synthetic interrupted provisional retrieval after retained bytes")
        if mode in {"cancelled", "timed_out", "rate_limited"}:
            packet[mode] = True
        if mode == "metadata":
            source.update(scope="metadata_only", excerpts=[])
        if mode == "invalid_proof":
            source["text_sha256"] = "0" * 64
        return packet
    return retrieve


def basis(service, identifier):
    ws = service._workspace(identifier)
    return service._preparation_redesign_basis(ws, ws.latest("workflow", Workflow))


def test_recovery_uses_only_frozen_queries_once_preserving_original_basis_hold_and_counts(setup):
    service, runner, identifier, before, routes, _ = prepared_hold(setup)
    original = frozen_originals(service, identifier, before)
    old_basis = basis(service, identifier)
    calls = []; service.collector = collector(calls)
    state = service.collect_redesign_question_evidence(identifier)
    recovered = state["redesign_question_evidence"]
    queries = list(dict.fromkeys(query for item in routes["candidates"] for query in item["literature_queries"]))
    assert calls == [{"queries": queries, "limit": 3, "pdf_candidates": None}]
    assert recovered["status"] == "ready" and recovered["collectionCount"] == 1
    assert recovered["newPrimarySourceIds"] == [recovered["literature"]["sources"][0]["id"]]
    assert state["redesign_question_selection"] == before["redesign_question_selection"]
    assert state["redesign_question_selection"]["selected_id"] is None
    assert state["redesign_question_reassessment"] is None
    assert state["literature"] == before["literature"]
    assert tuple(state[name] for name in COUNTERS) == tuple(before[name] for name in COUNTERS)
    assert basis(service, identifier) == old_basis
    assert_originals(service, identifier, original)
    new = [item for item in state["material_manifest"]["literature"] if item["source_id"] in recovered["newPrimarySourceIds"]]
    assert len(new) == 1 and new[0]["name"].startswith("literature-redesign-question-evidence-")
    read = service.read_material(identifier, "evidence", new[0]["name"], limit=32000)
    assert read["sha256"] == new[0]["sha256"] and "Additional synthetic retained body" in read["text"]
    repeated = service.collect_redesign_question_evidence(identifier)
    assert repeated["redesign_question_evidence"] == recovered and len(calls) == 1 and runner.calls == 0


def test_existing_repository_identity_proofs_relocate_without_changing_original_proof_bytes(setup, monkeypatch, clock):
    service, runner, identifier, before, _, _ = prepared_hold(setup)
    saved_proofs = {}
    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        assert limit == 3 and pdf_candidates is None
        packet, _ = repository_collection(monkeypatch, root)
        template = packet["searches"][-1]
        packet["searches"] = [{**copy.deepcopy(template), "query": query, "status": "succeeded", "attempted": True} for query in queries]
        source = packet["sources"][0]
        packet["sources"][0]["queries"] = list(queries)
        saved_proofs.update({path.name: path.read_bytes() for path in (root / "literature").iterdir() if path.is_file()})
        return packet
    service.collector = retrieve
    state = service.collect_redesign_question_evidence(identifier)
    assert state["redesign_question_evidence"]["status"] == "ready"
    source = state["redesign_question_evidence"]["literature"]["sources"][0]
    assert source["copy_type"] == "repository_copy" and source["publication_version"] == "unknown"
    root = service._workspace(identifier).path("research/redesign/question-evidence/literature")
    assert all((root / name).read_bytes() == raw for name, raw in saved_proofs.items())
    assert state["redesign_question_selection"] == before["redesign_question_selection"] and runner.calls == 0


@pytest.mark.parametrize("mode", ["same", "whitespace", "metadata", "cancelled", "timed_out", "rate_limited"])
def test_absent_duplicate_or_incomplete_body_cannot_reassess_or_repeat_collection(setup, mode):
    service, runner, identifier, before, routes, _ = prepared_hold(setup)
    original = frozen_originals(service, identifier, before)
    old_basis = basis(service, identifier)
    calls = []; service.collector = collector(calls, mode=mode)
    state = service.collect_redesign_question_evidence(identifier)
    expected = "held" if mode in {"same", "whitespace", "metadata"} else "incomplete"
    assert state["redesign_question_evidence"]["status"] == expected
    value = workflow_comparison(state, routes, selected=None)
    with pytest.raises(WorkflowError) as blocked:
        service.reassess_redesign_question(identifier, value)
    assert blocked.value.code == "QUESTION_EVIDENCE_INSUFFICIENT"
    service.collect_redesign_question_evidence(identifier)
    assert len(calls) == 1 and basis(service, identifier) == old_basis and runner.calls == 0
    assert_originals(service, identifier, original)


@pytest.mark.parametrize("mode", ["exception", "invalid_proof"])
def test_failed_dispatch_retains_raw_bytes_and_consumes_reservation(setup, mode):
    service, runner, identifier, before, _, _ = prepared_hold(setup)
    old_basis = basis(service, identifier)
    original = frozen_originals(service, identifier, before)
    calls = []; service.collector = collector(calls, mode=mode)
    with pytest.raises((OSError, WorkflowError)):
        service.collect_redesign_question_evidence(identifier)
    state = service.status(identifier)
    assert state["redesign_question_evidence"]["status"] == "incomplete"
    assert state["redesign_question_evidence"]["collectionCount"] == 1
    assert any(key.startswith("literature-redesign-question-evidence-") for key in state["artifacts"])
    service.collect_redesign_question_evidence(identifier)
    assert len(calls) == 1 and basis(service, identifier) == old_basis and runner.calls == 0
    assert_originals(service, identifier, original)


def test_dispatch_only_interruption_publicly_consumes_once_without_inventing_unbound_raw_reading(setup):
    service, runner, identifier, before, _, _ = prepared_hold(setup)
    old_basis = basis(service, identifier)
    calls = []
    finish = service._finish_redesign_question_evidence
    def stopped_finish(*args, **kwargs):
        raise OSError("Synthetic termination before receipt persistence")
    service._finish_redesign_question_evidence = stopped_finish
    service.collector = collector(calls, mode="exception")
    with pytest.raises(OSError): service.collect_redesign_question_evidence(identifier)
    state = service.status(identifier)
    assert "redesign-question-evidence-dispatch" in state["artifacts"]
    assert "redesign-question-evidence" not in state["artifacts"]
    assert state["redesign_question_evidence"]["status"] == "incomplete"
    assert state["redesign_question_evidence"]["collectionCount"] == 1
    assert state["redesign_question_evidence"]["newPrimarySourceIds"] == []
    assert state["redesign_question_evidence"]["literature"]["sources"] == []
    assert state["material_manifest"]["literature"] == before["material_manifest"]["literature"]
    assert basis(service, identifier) == old_basis
    service._finish_redesign_question_evidence = finish
    completed = service.collect_redesign_question_evidence(identifier)
    assert len(calls) == 1 and completed["redesign_question_evidence"]["status"] == "incomplete"
    assert completed["redesign_question_evidence"]["newPrimarySourceIds"] == []
    assert any(key.startswith("literature-redesign-question-evidence-") for key in completed["artifacts"])
    assert completed["material_manifest"]["literature"] == before["material_manifest"]["literature"]
    assert runner.calls == 0


@pytest.mark.parametrize("conflict", ["identity", "full_text"])
def test_same_source_id_conflict_retains_raw_once_without_ready_inventory_or_reassessment(setup, conflict):
    service, runner, identifier, before, routes, _ = prepared_hold(setup)
    original = frozen_originals(service, identifier, before)
    old_basis = basis(service, identifier)
    old_source = before["literature"]["sources"][0]
    calls = []
    service.collector = collector(calls, source_id=old_source["id"],
        arxiv_id=old_source["arxiv_id"] if conflict == "full_text" else "1311.3903v2")
    with pytest.raises(WorkflowError) as invalid:
        service.collect_redesign_question_evidence(identifier)
    assert invalid.value.code == "LITERATURE_SELECTION_INVALID"
    state = service.status(identifier)
    evidence = state["redesign_question_evidence"]
    assert evidence["status"] == "incomplete" and evidence["collectionCount"] == 1
    assert evidence["newPrimarySourceIds"] == []
    assert evidence["literature"]["sources"][0]["id"] == old_source["id"]
    assert any(key.startswith("literature-redesign-question-evidence-") for key in state["artifacts"])
    assert state["material_manifest"]["literature"] == before["material_manifest"]["literature"]
    with pytest.raises(WorkflowError) as blocked:
        service.reassess_redesign_question(identifier, workflow_comparison(state, routes, selected=None))
    assert blocked.value.code == "QUESTION_EVIDENCE_INSUFFICIENT"
    service.collect_redesign_question_evidence(identifier)
    assert len(calls) == 1 and basis(service, identifier) == old_basis and runner.calls == 0
    assert_originals(service, identifier, original)


def test_ready_receipt_rechecks_exact_pool_identity_before_public_or_reassessment(setup, monkeypatch):
    service, runner, identifier, before, routes, _ = prepared_hold(setup)
    old_source = before["literature"]["sources"][0]
    service.collector = collector([], source_id=old_source["id"])
    validate = native_workflow._validate_question_evidence_pool
    monkeypatch.setattr(native_workflow, "_validate_question_evidence_pool", lambda *args: None)
    state = service.collect_redesign_question_evidence(identifier)
    assert state["redesign_question_evidence"]["status"] == "ready"
    monkeypatch.setattr(native_workflow, "_validate_question_evidence_pool", validate)
    with pytest.raises(WorkflowError) as invalid:
        service.status(identifier)
    assert invalid.value.code == "LITERATURE_SELECTION_INVALID"
    with pytest.raises(WorkflowError) as blocked:
        service.reassess_redesign_question(identifier, workflow_comparison(state, routes, selected=None))
    assert blocked.value.code == "LITERATURE_SELECTION_INVALID" and runner.calls == 0


def test_coherent_same_id_metadata_upgrade_and_identical_verified_copy_preserve_identity(monkeypatch):
    source = {"id": "fixture-identity", "doi": "10.1234/fixture", "title": "Synthetic identity fixture",
              "authors": ["Fixture Author"], "year": 2026, "scope": "metadata_only"}
    body = {**source, "scope": "full_text", "sha256": "1" * 64, "text_sha256": "2" * 64}
    record = SimpleNamespace(artifacts={"literature": object(), "authoring-literature": object()})
    packets = {"literature": {"sources": [source]}, "authoring-literature": {"sources": [body]}}
    monkeypatch.setattr(native_workflow, "_read", lambda ws, record, key: packets[key])
    native_workflow._validate_question_evidence_pool(None, record, {"sources": [copy.deepcopy(body)]})
    packets["authoring-literature"]["sources"][0] = source
    native_workflow._validate_question_evidence_pool(None, record, {"sources": [body]})


@pytest.mark.parametrize("field", ["doi", "arxiv_id", "title", "authors", "year", "sha256", "text_sha256"])
def test_pool_identity_gate_covers_authoring_and_each_exact_identity_or_primary_digest(monkeypatch, field):
    source = {"id": "fixture-identity", "doi": "10.1234/fixture", "arxiv_id": "fixture-v1",
              "title": "Synthetic identity fixture", "authors": ["Fixture Author"], "year": 2026,
              "scope": "full_text", "sha256": "1" * 64, "text_sha256": "2" * 64}
    record = SimpleNamespace(artifacts={"authoring-literature": object()})
    monkeypatch.setattr(native_workflow, "_read", lambda *args: {"sources": [source]})
    changed = copy.deepcopy(source)
    changed[field] = ["Other Fixture Author"] if field == "authors" else 2025 if field == "year" else "different"
    with pytest.raises(WorkflowError) as invalid:
        native_workflow._validate_question_evidence_pool(None, record, {"sources": [changed]})
    assert invalid.value.code == "LITERATURE_SELECTION_INVALID"


def test_reassessment_is_new_immutable_decision_including_every_original_route_and_requirement(setup):
    service, runner, identifier, before, routes, _ = prepared_hold(setup)
    original = frozen_originals(service, identifier, before)
    old_basis = basis(service, identifier)
    calls = []; service.collector = collector(calls)
    state = service.collect_redesign_question_evidence(identifier)
    value = workflow_comparison(state, routes, selected=None)
    state = service.reassess_redesign_question(identifier, value)
    assert state["redesign_question_reassessment"] == value
    assert state["redesign_question_selection"] == before["redesign_question_selection"]
    assert state["redesign_question_selection"]["selected_id"] is None
    assert basis(service, identifier) == old_basis
    again = service.reassess_redesign_question(identifier, value)
    assert again["redesign_question_reassessment"] == value
    changed = copy.deepcopy(value); changed["reason"] += " A changed comparison cannot replace retained bytes."
    with pytest.raises(WorkflowError) as conflict:
        service.reassess_redesign_question(identifier, changed)
    assert conflict.value.code == "QUESTION_PREPARATION_CONFLICT"
    assert_originals(service, identifier, original)
    assert runner.calls == 0


def test_recommended_reassessment_authenticates_new_oracle_and_preserves_future_child_lineage(setup):
    service, runner, identifier, before, routes, proposed = prepared_hold(setup)
    original = frozen_originals(service, identifier, before)
    calls = []; service.collector = collector(calls)
    state = service.collect_redesign_question_evidence(identifier)
    value = workflow_comparison(state, routes)
    new_source = state["redesign_question_evidence"]["literature"]["sources"][0]
    for item in value["comparisons"]: item["evidence_sources"] = [new_source["id"]]
    state = service.reassess_redesign_question(identifier, value)
    proposed = attach_validation(service, identifier, proposed)
    proposed["literature_queries"] = routes["candidates"][0]["literature_queries"]
    text = (service._workspace(identifier).path("research") / new_source["text_path"]).read_bytes().decode("utf-8")
    body = new_source["body_range"]
    proposed["validation_contract"]["oracle_sources"] = [{"source_id": new_source["id"],
        "text_sha256": new_source["text_sha256"], "quote": text[body["start"]:body["start"] + 150]}]
    staged = service.submit_redesign_proposal(identifier, proposed, successor_repair(state["study_remediation"]))
    assert staged["redesign_candidate"] == proposed and staged["redesign_question_selection"]["selected_id"] is None
    service.submit_redesign_review(identifier, preparation_review())
    child = service.redesign_study(identifier)
    assert child["proposal_attempt"] == 1 and child["execution_attempt"] == 0
    origin = json.loads(service.artifact_path(child["id"], "redesign-origin").read_bytes())
    for key in ("redesign-questions", "redesign-question-selection", "redesign-question-evidence-dispatch",
                "redesign-question-evidence", "redesign-question-evidence-collection", "redesign-question-reassessment"):
        assert key in origin["parent_evidence"]
    assert any(key.startswith("literature-redesign-question-evidence-") for key in origin["parent_evidence"])
    assert_originals(service, identifier, original)
    assert runner.calls == 0


@pytest.mark.parametrize("defect", ["question", "protocol", "requirement", "unknown_body", "blocker"])
def test_reassessment_cannot_select_without_complete_native_verified_context(setup, defect):
    service, runner, identifier, before, routes, _ = prepared_hold(setup)
    calls = []; service.collector = collector(calls)
    state = service.collect_redesign_question_evidence(identifier)
    value = workflow_comparison(state, routes)
    if defect == "question": value["comparisons"][1]["id"] = "unretained-question"
    elif defect == "protocol": value["comparisons"][0]["prior_proposals"].pop()
    elif defect == "requirement": value["comparisons"][0]["criterion_repairs"][0]["required_change"] += " changed"
    elif defect == "unknown_body": value["comparisons"][0]["evidence_sources"] = ["unverified-body"]
    else: value["comparisons"][0]["generation_blockers"] = ["Required independent oracle is unavailable."]
    with pytest.raises(ValueError): service.reassess_redesign_question(identifier, value)
    assert service.status(identifier)["redesign_question_reassessment"] is None and runner.calls == 0


def test_undeclared_recovery_namespace_cannot_hide_artifacts_from_parent_basis(setup):
    service, runner, identifier, before, _, _ = prepared_hold(setup)
    ws = service._workspace(identifier); record = ws.latest("workflow", Workflow)
    record.artifacts["literature-redesign-question-evidence-" + "0" * 64 + "-" + "0" * 12] = record.artifacts["proposal"]
    service._save(ws, record)
    with pytest.raises(WorkflowError) as invalid: basis(service, identifier)
    assert invalid.value.code == "QUESTION_EVIDENCE_CONFLICT"
    assert runner.calls == 0


def test_recovery_inventory_must_bind_exact_native_path_hash_and_member_set(setup):
    service, runner, identifier, _, _, _ = prepared_hold(setup)
    calls = []; service.collector = collector(calls)
    state = service.collect_redesign_question_evidence(identifier)
    ws = service._workspace(identifier); record = ws.latest("workflow", Workflow)
    source_key = next(key for key in record.artifacts if key.startswith("literature-redesign-question-evidence-"))
    retained = record.artifacts[source_key]
    record.artifacts[source_key] = FrozenArtifact(path=record.artifacts["proposal"].path,
                                                sha256=retained.sha256, size=retained.size)
    service._save(ws, record)
    with pytest.raises(WorkflowError) as invalid: basis(service, identifier)
    assert invalid.value.code in {"QUESTION_EVIDENCE_CONFLICT", "ARTIFACT_CHANGED"}
    assert runner.calls == 0


def test_ipc_derives_recovery_queries_and_cannot_accept_manual_query_or_doi():
    good = {"id": "fixture", "method": "workflow.collectRedesignQuestionEvidence", "params": {"researchId": "research-123456789abc"}}
    assert ipc.request(json.dumps(good).encode())["params"] == good["params"]
    good["params"]["queries"] = ["manual synthetic query"]
    with pytest.raises(ValueError): ipc.request(json.dumps(good).encode())

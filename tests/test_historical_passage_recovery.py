"""Historical literal reading remains bound to its original frozen corpus."""
import copy
import json

import pytest

from paper_factory import workflow as native
from paper_factory.autonomous import literature
from paper_factory.workflow import WorkflowError
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import write_json
from test_literature_passage_selection import body_fixture
from test_planned_claim_projection import COUNTERS
from test_redesign_question_evidence import basis
from test_redesign_question_preparation import assert_originals, frozen_originals
from test_redesign_question_search_repair import diagnosed, repair_collector, reserve_and_plan
from test_workflow import collect_arxiv_preprint, setup
from test_unicode_report_workflow import initial as standard
from test_autonomous_literature import clock


def two_bodies(calls):
    first = repair_collector(calls, mode="new")
    def retrieve(queries, root, **kwargs):
        packet = first(queries, root, **kwargs)
        second = collect_arxiv_preprint(queries, root, limit=kwargs["limit"], cancel=kwargs["cancel"], arxiv_id="2401.00002v1")
        source = second["sources"][0]
        source["queries"] = list(queries)
        text = (root / source["text_path"]).read_text(encoding="utf-8").replace(
            "\nReferences", "\nSecond distinct synthetic reading body, without a scientific finding. " * 5 + "\nReferences")
        literature._retain_full_text(source, root, text, source["url"], source["raw_path"], source["sha256"])
        packet["sources"].append(source)
        packet["searches"] += second["searches"]
        packet["pdf_reservations"].append({"source_id": source["id"], "identity": "arxiv:" + source["arxiv_id"],
            "arxiv_id": source["arxiv_id"], "route": "provider_pdf", "url": source["url"], "pdf_attempted": True})
        return packet
    return retrieve


def test_old_review_and_ready_two_body_repair_project_without_recursion_or_reset(setup, monkeypatch):
    service, runner, identifier = setup
    original_submit = service.submit_study_review
    def reviewed_reading(research_id, value):
        state = service.status(research_id)
        if state["proposal_attempt"] == 3:
            source = next(item for item in state["literature"]["sources"] if item.get("scope") == "full_text")
            service.select_literature_passages(research_id, [{"source_id": source["id"], "text_sha256": source["text_sha256"],
                "text": source["excerpts"][0], "relevance": "An immutable synthetic original reading tests historical admission, not scientific merit."}])
        return original_submit(research_id, value)
    monkeypatch.setattr(service, "submit_study_review", reviewed_reading)
    service, runner, identifier, before, routes, _ = diagnosed(setup)
    monkeypatch.setattr(service, "submit_study_review", original_submit)
    old_review = json.loads(service.artifact_path(identifier, "study-review").read_bytes())
    old_key = old_review["literature_passages_artifact"]
    old_reading = json.loads(service.artifact_path(identifier, old_key).read_bytes())
    assert "redesign_question_search_repair_collection_sha256" not in old_reading["bindings"]
    originals = frozen_originals(service, identifier, before)
    old_basis = basis(service, identifier)
    reserve_and_plan(service, identifier, routes)
    calls = []; service.collector = two_bodies(calls)
    state = service.collect_redesign_question_search_repair(identifier)
    ws = service._workspace(identifier); record = ws.latest("workflow", Workflow)
    assert native._search_repair_members(ws, record)
    assert native._passage_receipt(ws, record, old_key, current=False) == old_reading
    assert native._passage_receipt(ws, record, old_key) is None
    current = native._passage_bindings(ws, record, "study")
    assert current["redesign_question_search_repair_collection_sha256"] == record.artifacts["redesign-question-search-repair-collection"].sha256
    public = service._public(ws, record)
    repair = public["redesign_question_search_repair"]
    assert repair["status"] == "ready" and repair["planCount"] == repair["collectionCount"] == 1
    assert len(repair["newPrimarySourceIds"]) == 2
    materials = [item for item in native._literature_materials(ws, record) if item["name"].startswith(native.SEARCH_REPAIR_PREFIX)]
    assert {item["source_id"] for item in materials} == set(repair["newPrimarySourceIds"])
    for item in materials:
        assert service.read_material(identifier, "evidence", item["name"], limit=32000)["sha256"] == item["sha256"]
    assert tuple(public[name] for name in COUNTERS) == tuple(before[name] for name in COUNTERS)
    assert public["redesign_question_selection"] == before["redesign_question_selection"]
    assert public["redesign_question_evidence"] == before["redesign_question_evidence"]
    assert public["redesign_question_reassessment"] is None and public["redesign_candidate"] is None
    assert basis(service, identifier) == old_basis
    assert_originals(service, identifier, originals)
    assert len(calls) == 1 and runner.calls == 0


def frozen_pool_receipt(setup, *, pool_key="redesign-question-search-repair-collection"):
    service, runner, identifier = setup
    state = body_fixture(service, identifier)
    ws = service._workspace(identifier); record = ws.latest("workflow", Workflow)
    root = ws.path(native.SEARCH_REPAIR_ROOT if pool_key == "redesign-question-search-repair-collection" else native.QUESTION_EVIDENCE_ROOT)
    (root / "literature").mkdir(parents=True)
    packet = collect_arxiv_preprint(["synthetic retained query"], root, limit=3, cancel=lambda: False, arxiv_id="2401.00003v1")
    prefix = root.relative_to(ws.path("research")).as_posix() + "/"
    for source in packet["sources"]:
        for field in ("text_path", "metadata_path", "raw_path"):
            source[field] = prefix + source[field]
    for search in packet["searches"]:
        search["raw_path"] = prefix + search["raw_path"]
    for index, path in enumerate(root.rglob("*")):
        if path.is_file(): native._freeze(ws, record, f"literature-synthetic-historical-pool-raw-{index}", path)
    path = root / "collection.json"; write_json(path, packet)
    native._freeze(ws, record, pool_key, path)
    source = packet["sources"][0]
    choices = [{"source_id": source["id"], "text_sha256": source["text_sha256"], "text": source["excerpts"][0],
                "relevance": "Exact synthetic frozen pool reading asserts no academic approval."}]
    bindings = native._passage_bindings(ws, record, "study", current=False)
    selected, passages = native._resolve_passages(ws, record, choices, "study", bindings, current=False)
    receipt = {"event": "verified-literature-body-selection", "bindings": bindings, "packet": selected, "passages": passages}
    path = ws.path("research/synthetic-historical-pool-reading.json"); write_json(path, receipt)
    native._freeze(ws, record, "synthetic-historical-pool-reading", path)
    return service, runner, ws, record, receipt, path


@pytest.mark.parametrize("pool_key", ["redesign-question-evidence-collection", "redesign-question-search-repair-collection"])
def test_historical_receipt_created_with_new_pool_uses_frozen_proof_and_current_still_checks_eligibility(setup, monkeypatch, pool_key):
    service, runner, ws, record, receipt, _ = frozen_pool_receipt(setup, pool_key=pool_key)
    def current_pool(*args):
        raise RuntimeError("Current pool eligibility was requested")
    monkeypatch.setattr(native, "_search_repair_public", current_pool)
    monkeypatch.setattr(native, "_question_evidence", current_pool)
    assert native._passage_receipt(ws, record, "synthetic-historical-pool-reading", current=False) == receipt
    with pytest.raises(RuntimeError, match="Current pool eligibility"):
        native._passage_receipt(ws, record, "synthetic-historical-pool-reading")
    assert runner.calls == 0


@pytest.mark.parametrize("operation", ["history", "passages"])
@pytest.mark.parametrize("tamper_field", [None, "raw_path", "metadata_path", "text_path", "discovery_path", "identity_path", "revision"])
def test_request_local_unicode_proof_reuse_rechecks_each_frozen_dependency(setup, monkeypatch, clock, operation, tamper_field):
    service, runner, identifier, state = standard(setup, monkeypatch)
    ws = service._workspace(identifier); record = ws.latest("workflow", Workflow)
    source, = state["literature"]["sources"]
    body_calls = []; file_calls = []
    original_body = native._retained_primary_body
    original_files = native._retained_primary_files
    def verify_body(*args, **kwargs):
        body_calls.append(args[2]["id"])
        result = original_body(*args, **kwargs)
        if tamper_field == "revision" and operation == "passages" and len(body_calls) == 1:
            args[2]["revision"] += 1
        return result
    def verify_files(*args, **kwargs):
        file_calls.append(args[2]["id"])
        if tamper_field and tamper_field != "revision" and len(file_calls) == 2:
            ws.path("research/" + source[tamper_field]).write_bytes(b"Changed official publisher original")
        return original_files(*args, **kwargs)
    monkeypatch.setattr(native, "_retained_primary_body", verify_body)
    monkeypatch.setattr(native, "_retained_primary_files", verify_files)
    if operation == "history":
        if tamper_field == "revision":
            changed = copy.deepcopy(state["literature"])
            changed["sources"][0]["revision"] += 1
            path = ws.path("research/synthetic-conflicting-history-identity.json")
            write_json(path, changed)
            native._freeze(ws, record, "literature-history-" + native._json_digest(changed), path)
        else:
            record.artifacts["literature-history-" + record.artifacts["literature"].sha256] = record.artifacts["literature"]
        call = lambda: native._search_repair_history(ws, record)
    else:
        text = ws.path("research/" + source["text_path"]).read_bytes().decode("utf-8")
        choices = [{"source_id": source["id"], "text_sha256": source["text_sha256"],
                    "text": text[section["start"]:section["start"] + 180],
                    "relevance": "Synthetic exact official section selection does not assert scholarly approval."}
                   for section in source["section_ranges"][:2]]
        call = lambda: native._resolve_passages(ws, record, choices, "study", native._passage_bindings(ws, record, "study", current=False), current=False)
    if tamper_field:
        with pytest.raises(WorkflowError) as error:
            call()
        assert error.value.code == ("PUBLICATION_EVIDENCE_INVALID" if tamper_field == "revision" else "ARTIFACT_CHANGED")
    else:
        result = call()
        assert result
    assert len(body_calls) == (2 if tamper_field == "revision" else 1) and len(file_calls) == 2
    assert runner.calls == 0


@pytest.mark.parametrize("defect", ["context", "pool_digest", "body_bytes", "bounds", "packet"])
def test_historical_pool_reading_still_rejects_binding_body_and_receipt_tamper(setup, defect, monkeypatch):
    service, runner, ws, record, receipt, path = frozen_pool_receipt(setup)
    def no_current_pool(*args):
        raise AssertionError("Historical proof must not consult later pool eligibility")
    monkeypatch.setattr(native, "_search_repair_public", no_current_pool)
    if defect == "context":
        record.goal += " Changed retained context."
    elif defect == "body_bytes":
        source = receipt["packet"]["sources"][-1]
        ws.path("research/" + source["text_path"]).write_bytes(b"Forged body bytes")
    else:
        changed = copy.deepcopy(receipt)
        if defect == "pool_digest": changed["bindings"]["redesign_question_search_repair_collection_sha256"] = "0" * 64
        elif defect == "bounds": changed["passages"][0]["start"] += 1
        else: changed["packet"]["sources"][-1]["title"] += " Invented title."
        write_json(path, changed)
        native._freeze(ws, record, "synthetic-historical-pool-reading", path)
    with pytest.raises(WorkflowError):
        native._passage_receipt(ws, record, "synthetic-historical-pool-reading", current=False)
    assert runner.calls == 0

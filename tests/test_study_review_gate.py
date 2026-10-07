"""Retrieval completeness is required even when a model approves a study."""

import copy
import json

import pytest

from paper_factory.workflow import WorkflowError, WorkflowService, _freeze
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import Workspace, write_json
from test_workflow import BUNDLE, REVIEW, STUDY_REVIEW, FixtureRunner, collect, protocol, rejected_study_review


@pytest.fixture
def pending_study(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "transform.js").write_text("export function transform(values) { return values.slice(); }\n", encoding="utf-8")
    runner = FixtureRunner()
    service = WorkflowService(tmp_path / "home", runner=runner, collector=collect)
    research_id = service.create(str(source), "Validate retained literature before approving a controlled study.")["id"]
    proposal = protocol()
    proposal["literature_queries"] = ["first query", "second query"]
    service.submit_proposal(research_id, proposal)
    try:
        yield service, runner, research_id
    finally:
        service.close()


def incomplete_collector(defect):
    def retrieve(queries, root, **options):
        evidence = collect(queries, root, **options)
        if defect == "missing":
            evidence["searches"].pop()
        elif defect == "not_attempted":
            evidence["searches"][-1].update(status="not_attempted", attempted=False)
        elif defect == "false_success":
            evidence["searches"][-1]["attempted"] = False
        else:
            evidence["cancelled"] = True
        return evidence
    return retrieve


@pytest.mark.parametrize("defect", ["missing", "not_attempted", "false_success", "cancelled"])
def test_model_approval_cannot_freeze_incomplete_retrieval(pending_study, defect):
    service, runner, research_id = pending_study
    service.collector = incomplete_collector(defect)
    expected = "LITERATURE_EVIDENCE_INSUFFICIENT" if defect == "cancelled" else "LITERATURE_QUERIES_INCOMPLETE"
    with pytest.raises(WorkflowError) as collection:
        service.collect_literature(research_id)
    assert collection.value.code == expected
    retained = service.artifact_path(research_id, "literature").read_bytes()
    with pytest.raises(WorkflowError) as approval:
        service.submit_study_review(research_id, copy.deepcopy(STUDY_REVIEW))
    assert approval.value.code == expected
    state = service.status(research_id)
    assert state["stage"] == "proposed" and state["study_review"] is None
    assert not {"plan", "selected-literature", "bundle", "observations", "manuscript"} & state["artifacts"].keys()
    assert service.artifact_path(research_id, "literature").read_bytes() == retained and runner.calls == 0


@pytest.mark.parametrize("defect", ["not_attempted", "cancelled"])
def test_incomplete_retrieval_still_retains_a_rejected_assessment(pending_study, defect):
    service, runner, research_id = pending_study
    service.collector = incomplete_collector(defect)
    with pytest.raises(WorkflowError):
        service.collect_literature(research_id)
    rejected = rejected_study_review()
    state = service.submit_study_review(research_id, rejected)
    assert state["stage"] == "proposed" and state["code"] == "STUDY_REJECTED"
    receipt = json.loads(service.artifact_path(research_id, "study-review-1").read_bytes())
    assert receipt["review"] == rejected and "plan" not in state["artifacts"] and runner.calls == 0


def test_failed_provider_attempt_is_recorded_coverage_without_inventing_reading(pending_study):
    service, runner, research_id = pending_study
    def provider_failure(queries, root, **options):
        evidence = collect(queries, root, **options)
        evidence["searches"][-1].update(status="failed", attempted=True, error="HTTPStatusError", resolved_ids=[])
        return evidence
    service.collector = provider_failure
    service.collect_literature(research_id)
    state = service.submit_study_review(research_id, copy.deepcopy(STUDY_REVIEW))
    assert state["stage"] == "planned" and state["study_review"]["accepted"] is True and runner.calls == 0


def test_resumed_resolution_cancellation_recollects_all_queries_and_preserves_partial_bytes(pending_study):
    service, runner, research_id = pending_study
    calls = []
    def resolution_cancelled(queries, root, *, limit, cancel):
        calls.append((queries, limit))
        evidence = collect(queries, root, limit=6, cancel=cancel)
        evidence["cancelled"] = len(calls) == 1
        return evidence
    service.collector = resolution_cancelled
    with pytest.raises(WorkflowError) as interrupted:
        service.collect_literature(research_id)
    assert interrupted.value.code == "LITERATURE_EVIDENCE_INSUFFICIENT"
    partial_path = service.artifact_path(research_id, "literature")
    partial_bytes = partial_path.read_bytes()
    service.cancel(research_id)
    assert service.resume(research_id)["stage"] == "proposed"
    completed = service.collect_literature(research_id)
    assert calls == [(["first query", "second query"], 6), (["first query", "second query"], 5)]
    assert completed["literature"]["cancelled"] is False
    assert service.artifact_path(research_id, "literature") != partial_path
    history = completed["literature"]["history"][0]
    assert service.artifact_path(research_id, history["artifact_id"]).read_bytes() == partial_bytes
    approved = service.submit_study_review(research_id, copy.deepcopy(STUDY_REVIEW))
    assert approved["stage"] == "planned" and runner.calls == 0


@pytest.mark.parametrize("defect", ["not_attempted", "cancelled"])
def test_frozen_approval_rechecks_query_coverage_even_when_receipt_hashes_match(pending_study, defect):
    service, runner, research_id = pending_study
    service.collect_literature(research_id)
    service.submit_study_review(research_id, copy.deepcopy(STUDY_REVIEW))
    ws = Workspace(service.root / research_id)
    record = ws.get("workflow", research_id, Workflow)
    literature_path = service.artifact_path(research_id, "literature")
    evidence = json.loads(literature_path.read_bytes())
    if defect == "cancelled":
        evidence["cancelled"] = True
    else:
        evidence["searches"][-1].update(status="not_attempted", attempted=False)
    write_json(literature_path, evidence)
    _freeze(ws, record, "literature", literature_path)
    review_path = service.artifact_path(research_id, "study-review")
    receipt = json.loads(review_path.read_bytes())
    receipt["literature_sha256"] = record.artifacts["literature"].sha256
    write_json(review_path, receipt)
    for key in ("study-review", "study-review-1"):
        _freeze(ws, record, key, review_path)
    ws.save("workflow", record)
    with pytest.raises(WorkflowError) as rejected:
        service.submit_code(research_id, copy.deepcopy(BUNDLE), REVIEW)
    expected = "LITERATURE_EVIDENCE_INSUFFICIENT" if defect == "cancelled" else "LITERATURE_QUERIES_INCOMPLETE"
    assert rejected.value.code == expected
    assert runner.calls == 0 and "bundle" not in service.status(research_id)["artifacts"]

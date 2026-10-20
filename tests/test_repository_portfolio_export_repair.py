"""Explicit output-only recovery with synthetic conversion diagnostics and bytes."""

import hashlib
import io
import json
from types import SimpleNamespace

import pytest

from paper_factory import ipc
from paper_factory.conversion import WIDE_TABLE_FILTER
from paper_factory.workflow import WorkflowError
from test_repository_portfolio import portfolio, analyze_portfolio, retain_portfolio_response
from test_repository_paper_workflow import study, draft, review


@pytest.fixture
def failed_export(portfolio, monkeypatch, request):
    service, rid, _, _ = portfolio
    analyzed = analyze_portfolio(service, rid)
    venue_id = analyzed["repository_paper"]["portfolio"]["targets"][0]["venue_id"]
    value = draft(service, rid, prepare_analysis=False)
    key, _ = retain_portfolio_response(service, rid, value, "venue-manuscript", venue_id)
    service.submit_portfolio_manuscript(rid, {"venue_id": venue_id, "inference_artifact_id": key, "manuscript": value})
    block = b"\nSynthetic retained byline for output fixture only.\n"
    monkeypatch.setattr(service, "_repository_byline", lambda ws, record, text: (text + block, block, None))
    condition = getattr(request, "param", "eligible")
    calls = []

    def fail(source, output, **kwargs):
        calls.append((source, output))
        lua = output.with_name("paper-table-layout.lua")
        if condition != "missing-proof":
            lua.write_text(WIDE_TABLE_FILTER, encoding="utf-8")
        error_path = output.with_name("unrelated.lua") if condition == "different-path" else lua
        message = f"Pandoc failed (83): Error running filter {error_path.resolve()}:\ncannot open {error_path.resolve()}: No such file or directory\n"
        if condition == "generic-error":
            message = "Synthetic unrelated compiler failure."
        raise ValueError(message)

    monkeypatch.setattr("paper_factory.conversion.convert", fail)
    status = service.export_portfolio_draft(rid, venue_id)
    venue = status["repository_paper"]["portfolio"]["venues"][0]
    if condition == "changed-lua":
        lua_id = f"repository-portfolio-{venue_id}-export-source-paper-table-layout-lua-1"
        service.artifact_path(rid, lua_id).write_text("Explicit synthetic frozen-byte corruption.", encoding="utf-8")
    return service, rid, venue_id, status, venue, calls


def successful_conversion(calls):
    def convert(source, output, **kwargs):
        calls.append((source, output))
        output.write_bytes(b"Synthetic fixture output only: " + output.suffix.encode())
        output.with_name("paper-table-layout.lua").write_text(WIDE_TABLE_FILTER, encoding="utf-8")
        return {"input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "engine": "synthetic-fixture"}
    return convert


def test_export_repair_preserves_original_scientific_and_failed_output_bytes_with_new_ids(failed_export, monkeypatch):
    service, rid, venue_id, before, old_venue, calls = failed_export
    assert old_venue["export_status"] == "failed" and old_venue["export_repair_available"]
    assert old_venue["export_repair_attempts"] == 0
    original = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    original_receipt_id = old_venue["export"]["artifact_id"]
    original_receipt = json.loads(original[original_receipt_id])
    original_input = original[original_receipt["input_artifact_id"]]
    monkeypatch.setattr("paper_factory.conversion.convert", successful_conversion(calls))
    monkeypatch.setattr(service, "_repository_byline", lambda *args: pytest.fail("Repair must copy the existing byline without regenerating it"))
    current = service.repair_portfolio_export(rid, venue_id)
    venue = current["repository_paper"]["portfolio"]["venues"][0]
    assert venue["export_status"] == "completed" and venue["export"]["errors"] == []
    assert venue["export_repair_attempts"] == 1 and not venue["export_repair_available"]
    assert venue["export"]["original_artifact_id"] == original_receipt_id
    assert venue["export"]["original_sha256"] == before["artifacts"][original_receipt_id]["sha256"]
    receipt_id = f"repository-portfolio-{venue_id}-export-repair-1"
    assert venue["export"]["artifact_id"] == receipt_id
    receipt = json.loads(service.artifact_path(rid, receipt_id).read_bytes())
    assert receipt["model_calls"] == 0 and receipt["original_artifacts_preserved"]
    assert service.artifact_path(rid, receipt["input_artifact_id"]).read_bytes() == original_input
    for field in ("author_artifact_id", "author_sha256", "author_block_sha256"):
        assert receipt[field] == original_receipt[field]
    for extension in ("pdf", "docx"):
        assert venue["artifact_ids"][extension] == f"repository-portfolio-{venue_id}-{extension}-repair-1"
        assert receipt["outputs"][extension]["conversion_artifact_id"] == f"repository-portfolio-{venue_id}-{extension}-conversion-repair-1"
        assert service.artifact_path(rid, venue["artifact_ids"][extension]).parent.name == "export-2"
    lua_id = f"repository-portfolio-{venue_id}-export-source-repair-paper-table-layout-lua-1"
    assert service.artifact_path(rid, lua_id).read_bytes() == original[receipt["original_lua_artifact_id"]]
    assert receipt["original_lua_sha256"] == before["artifacts"][receipt["original_lua_artifact_id"]]["sha256"]
    assert len(calls) == 4
    service.repair_portfolio_export(rid, venue_id)
    service.export_portfolio_draft(rid, venue_id)
    assert len(calls) == 4
    assert all(service.artifact_path(rid, key).read_bytes() == value for key, value in original.items())
    for field in ("draft_attempt", "execution_attempt", "study_literature_attempt"):
        assert current[field] == before[field]
    for field in ("analysis_attempts", "analysis", "draft", "review", "manuscript_bindings"):
        assert current["repository_paper"][field] == before["repository_paper"][field]
    for field in ("draft_attempts", "review_attempts", "repair_attempts", "draft", "review", "draft_sha256"):
        assert venue[field] == old_venue[field]
    model_evidence = {key for key in before["artifacts"] if key.startswith("model-evidence-")}
    assert model_evidence and {key for key in current["artifacts"] if key.startswith("model-evidence-")} == model_evidence


@pytest.mark.parametrize("failed_export", ["generic-error", "missing-proof", "different-path", "changed-lua"], indirect=True)
def test_export_repair_rejects_unrelated_error_or_missing_exact_original_lua_proof(failed_export, request):
    service, rid, venue_id, _, _, calls = failed_export
    with pytest.raises(WorkflowError) as rejected:
        service.repair_portfolio_export(rid, venue_id)
    if request.node.callspec.params["failed_export"] == "changed-lua":
        assert rejected.value.code == "ARTIFACT_CHANGED" and len(calls) == 2
        return
    assert rejected.value.code == "PORTFOLIO_EXPORT_REPAIR_UNAVAILABLE" and len(calls) == 2
    venue = service.status(rid)["repository_paper"]["portfolio"]["venues"][0]
    assert not venue["export_repair_available"] and venue["export_repair_attempts"] == 0


def test_failed_export_repair_remains_single_idempotent_attempt(failed_export, monkeypatch):
    service, rid, venue_id, _, venue, calls = failed_export
    original_receipt = service.artifact_path(rid, venue["export"]["artifact_id"]).read_bytes()
    def fail(source, output, **kwargs):
        calls.append((source, output))
        raise ValueError("Synthetic remaining compiler failure, never an automatic rerun.")
    monkeypatch.setattr("paper_factory.conversion.convert", fail)
    current = service.repair_portfolio_export(rid, venue_id)
    venue = current["repository_paper"]["portfolio"]["venues"][0]
    assert venue["export_status"] == "failed" and venue["export_repair_attempts"] == 1
    assert not venue["export_repair_available"]
    repair_receipt = service.artifact_path(rid, venue["export"]["artifact_id"]).read_bytes()
    service.repair_portfolio_export(rid, venue_id)
    assert len(calls) == 4 and service.artifact_path(rid, venue["export"]["artifact_id"]).read_bytes() == repair_receipt
    assert service.artifact_path(rid, venue["export"]["original_artifact_id"]).read_bytes() == original_receipt


def test_unadmitted_export_repair_directory_is_counted_and_never_reexecuted(failed_export, monkeypatch):
    service, rid, venue_id, _, venue, calls = failed_export
    original_receipt = service.artifact_path(rid, venue["export"]["artifact_id"]).read_bytes()
    def uncertain(source, output, **kwargs):
        calls.append((source, output))
        raise RuntimeError("Synthetic interruption after the immutable repair input was saved.")
    monkeypatch.setattr("paper_factory.conversion.convert", uncertain)
    with pytest.raises(RuntimeError):
        service.repair_portfolio_export(rid, venue_id)
    current = service.status(rid)["repository_paper"]["portfolio"]["venues"][0]
    assert current["export_status"] == "interrupted" and current["export"] is None
    assert current["export_repair_attempts"] == 1 and not current["export_repair_available"]
    assert current["artifact_ids"]["pdf"] is None and current["artifact_ids"]["docx"] is None
    with pytest.raises(WorkflowError) as repeated:
        service.repair_portfolio_export(rid, venue_id)
    assert repeated.value.code == "PORTFOLIO_EXPORT_REPAIR_INTERRUPTED" and len(calls) == 3
    assert service.artifact_path(rid, venue["export"]["artifact_id"]).read_bytes() == original_receipt


def test_export_repair_ipc_has_only_explicit_research_and_venue_authority():
    calls = []
    service = SimpleNamespace(repair_portfolio_export=lambda *args: calls.append(args) or {"ok": True})
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), io.BytesIO())
    message = {"id": "repair-export", "method": "workflow.repairPortfolioExport",
        "params": {"researchId": "research-abcdefabcdef", "venueId": "ieee-software"}}
    try:
        assert ipc.request(json.dumps(message).encode()) == message
        assert dispatcher.execute(message["method"], message["params"]) == {"ok": True}
        assert calls == [("research-abcdefabcdef", "ieee-software")]
        for extra in ("reset", "retry", "pdfBudget", "value"):
            with pytest.raises(ValueError):
                ipc.request(json.dumps({**message, "params": {**message["params"], extra: True}}).encode())
    finally:
        dispatcher._pool.shutdown(wait=True)

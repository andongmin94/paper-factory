"""Bibliography-only output recovery keeps every actual scientific and failure artifact."""

import hashlib
import io
import json
import re
from types import SimpleNamespace

import pytest

from paper_factory import ipc
from paper_factory.autonomous import repository_portfolio as native
from paper_factory.autonomous.repository_paper import RepositoryManuscript
from paper_factory.models import Project
from paper_factory.workflow import WorkflowError
from test_repository_paper_workflow import study, draft, review
from test_repository_portfolio import portfolio, analyze_portfolio, retain_portfolio_response
from test_repository_portfolio_export_repair import successful_conversion


@pytest.fixture
def duplicate_export(portfolio, monkeypatch, request):
    service, rid, _, _ = portfolio
    analyzed = analyze_portfolio(service, rid)
    venue_id = analyzed["repository_paper"]["portfolio"]["targets"][0]["venue_id"]
    condition = getattr(request, "param", "eligible")
    original_render = native.render

    def historical_render(value, *args):
        sections = [section for section in value.sections if section.heading != "References"]
        base = original_render(value.model_copy(update={"sections": sections}), *args)
        boundary = base.rfind("## References\n\n")
        model = next((section for section in value.sections if section.heading == "References"), None)
        return base[:boundary] + ("## References\n\n" + model.text + "\n\n" if model else "") + base[boundary:]

    value = draft(service, rid, prepare_analysis=False)
    with service._operation(rid) as (ws, record):
        model = RepositoryManuscript.model_validate(value)
        sources, documents = service._portfolio_evidence(ws, record, model)
        imported = ws.latest("project", Project)
        rendered = original_render(model, imported.source, imported.source_commit, sources, documents, [asset.path for asset in imported.assets])
    canonical = rendered.rsplit("## References\n\n", 1)[1].strip()
    if condition != "no-duplicate":
        value["sections"].append({"heading": "References", "text": "\n\n".join("- " + re.sub(r"^\[\d+\] ", "", entry) for entry in canonical.split("\n\n"))})
    monkeypatch.setattr(native, "render", historical_render)
    key, _ = retain_portfolio_response(service, rid, value, "venue-manuscript", venue_id)
    service.submit_portfolio_manuscript(rid, {"venue_id": venue_id, "inference_artifact_id": key, "manuscript": value})
    assessment = review(True)
    assessment["criteria"]["presentation"]["passed"] = False
    assessment["issues"] = ["The model bibliography duplicates the engine-owned canonical references."]
    assessment["next_actions"] = [{"action": "revise_manuscript", "target": "References",
        "required_change": "Remove only the duplicate model reference block.",
        "verification": "The exact scientific paragraphs and canonical references stay unchanged."}]
    assessment["content_assessment"]["issues"] = list(assessment["issues"])
    assessment["content_assessment"]["next_actions"] = list(assessment["next_actions"])
    assessment["content_assessment"]["revision_outline"] = [{"heading": "Discussion",
        "instruction": "Remove the duplicate bibliography without modifying scientific paragraphs or reference identities."}]
    if condition == "scientific-failure":
        assessment["criteria"]["method"]["passed"] = False
    block = b"\nSynthetic frozen output byline.\n"
    monkeypatch.setattr(service, "_repository_byline", lambda ws, record, text: (text.partition(b"\n")[0] + b"\n" + block + text.partition(b"\n")[2], block, None))
    calls = []
    monkeypatch.setattr("paper_factory.conversion.convert", successful_conversion(calls))
    before = service.export_portfolio_draft(rid, venue_id)
    key, _ = retain_portfolio_response(service, rid, assessment, "venue-manuscript-review", venue_id)
    service.submit_portfolio_review(rid, {"venue_id": venue_id, "inference_artifact_id": key, "review": assessment})
    before = service.status(rid)
    return service, rid, venue_id, before, calls


def test_format_export_preserves_rejected_review_all_old_bytes_counts_and_byline_with_distinct_outputs(duplicate_export, monkeypatch):
    service, rid, venue_id, before, calls = duplicate_export
    old = before["repository_paper"]["portfolio"]["venues"][0]
    assert old["format_export_available"] and old["format_export_attempts"] == 0 and old["format_export"] is None
    assert old["review"]["content_assessment"]["issues"] and old["review"]["content_assessment"]["next_actions"]
    assert old["review"]["content_assessment"]["comparison"]["passed"] and old["review"]["content_assessment"]["contribution"]["passed"]
    originals = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    monkeypatch.setattr(service, "_repository_byline", lambda *args: pytest.fail("Formatting must retain the already exported byline"))
    current = service.reformat_portfolio_draft(rid, venue_id)
    venue = current["repository_paper"]["portfolio"]["venues"][0]
    receipt = venue["format_export"]
    assert receipt["status"] == "completed" and receipt["model_calls"] == 0 and not receipt["scientific_approval_changed"]
    assert venue["format_export_attempts"] == 1 and not venue["format_export_available"]
    assert venue["export"] == old["export"] and venue["review"] == old["review"]
    assert not venue["scientific_ready"] and not venue["content_ready"] and not venue["submission_ready"]
    assert receipt["original_artifact_id"] == old["export"]["artifact_id"]
    assert receipt["original_sha256"] == old["export"]["sha256"]
    assert receipt["original_draft_sha256"] == before["artifacts"][old["artifact_ids"]["draft"]]["sha256"]
    assert receipt["original_markdown_sha256"] == before["artifacts"][old["artifact_ids"]["markdown"]]["sha256"]
    assert receipt["original_review_sha256"] == before["artifacts"][old["artifact_ids"]["review"]]["sha256"]
    proof = receipt["format_proof"]
    assert proof["scientific_body_sha256_before"] == proof["scientific_body_sha256_after"]
    original_input = json.loads(originals[old["export"]["artifact_id"]])
    assert receipt["author_block_sha256"] == original_input["author_block_sha256"]
    output_input = service.artifact_path(rid, receipt["input_artifact_id"]).read_bytes()
    assert output_input.count(b"## References") == 1 and b"Synthetic frozen output byline." in output_input
    assert hashlib.sha256(output_input).hexdigest() == receipt["input_sha256"]
    for extension in ("pdf", "docx"):
        assert venue["artifact_ids"][extension] == f"repository-portfolio-{venue_id}-{extension}-format-1"
        assert service.artifact_path(rid, venue["artifact_ids"][extension]).parent.name == "format-1"
        assert receipt["outputs"][extension]["conversion_artifact_id"] == f"repository-portfolio-{venue_id}-{extension}-conversion-format-1"
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in originals.items())
    for field in ("proposal_attempt", "study_literature_attempt", "draft_attempt", "code_attempt", "execution_attempt", "redesign_attempt"):
        assert current[field] == before[field]
    for field in ("analysis", "analysis_attempts", "draft", "review"):
        assert current["repository_paper"][field] == before["repository_paper"][field]
    for field in ("draft", "review", "draft_attempts", "review_attempts", "repair_attempts", "draft_sha256", "analysis_current"):
        assert venue[field] == old[field]
    assert {key for key in current["artifacts"] if key.startswith("model-evidence-")} == {key for key in before["artifacts"] if key.startswith("model-evidence-")}
    assert current["repository_paper"]["portfolio"]["venues"][1:] == before["repository_paper"]["portfolio"]["venues"][1:]
    service.reformat_portfolio_draft(rid, venue_id)
    service.export_portfolio_draft(rid, venue_id)
    assert len(calls) == 4


@pytest.mark.parametrize("duplicate_export", ["scientific-failure", "no-duplicate"], indirect=True)
def test_format_export_rejects_scientific_failure_or_missing_duplicate_without_new_artifacts(duplicate_export):
    service, rid, venue_id, before, calls = duplicate_export
    venue = before["repository_paper"]["portfolio"]["venues"][0]
    assert not venue["format_export_available"] and venue["format_export_attempts"] == 0
    with pytest.raises(WorkflowError) as rejected:
        service.reformat_portfolio_draft(rid, venue_id)
    assert rejected.value.code == "PORTFOLIO_FORMAT_UNAVAILABLE" and len(calls) == 2
    assert service.status(rid)["artifacts"] == before["artifacts"]


def test_cancelled_format_export_is_output_only_and_never_resumes_common_authoring(duplicate_export):
    service, rid, venue_id, _, calls = duplicate_export
    cancelled = service.cancel(rid)
    original = {key: service.artifact_path(rid, key).read_bytes() for key in cancelled["artifacts"]}
    current = service.reformat_portfolio_draft(rid, venue_id)
    for field in ("status", "code", "cancellation_requested", "stage", "proposal_attempt", "study_literature_attempt", "draft_attempt", "execution_attempt", "code_attempt"):
        assert current[field] == cancelled[field]
    assert len(calls) == 4
    assert not any(key.startswith("repository-resume-") for key in current["artifacts"])
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in original.items())


@pytest.mark.parametrize("failure", ["failed", "interrupted"])
def test_format_export_failure_or_unknown_output_uses_the_only_attempt_without_replacing_old_outputs(duplicate_export, monkeypatch, failure):
    service, rid, venue_id, before, calls = duplicate_export
    old = before["repository_paper"]["portfolio"]["venues"][0]
    original = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    def fail(source, output):
        calls.append((source, output))
        if failure == "interrupted":
            raise RuntimeError("Synthetic unknown converter outcome after immutable formatting intent")
        raise ValueError("Synthetic converter failure")
    monkeypatch.setattr("paper_factory.conversion.convert", fail)
    if failure == "interrupted":
        with pytest.raises(RuntimeError):
            service.reformat_portfolio_draft(rid, venue_id)
    else:
        service.reformat_portfolio_draft(rid, venue_id)
    current = service.status(rid)
    venue = current["repository_paper"]["portfolio"]["venues"][0]
    assert venue["format_export_attempts"] == 1 and not venue["format_export_available"]
    assert venue["artifact_ids"]["pdf"] == old["artifact_ids"]["pdf"] and venue["artifact_ids"]["docx"] == old["artifact_ids"]["docx"]
    if failure == "interrupted":
        assert venue["format_export"] is None
        with pytest.raises(WorkflowError) as rejected:
            service.reformat_portfolio_draft(rid, venue_id)
        assert rejected.value.code == "PORTFOLIO_FORMAT_INTERRUPTED" and len(calls) == 3
    else:
        assert venue["format_export"]["status"] == "failed"
        service.reformat_portfolio_draft(rid, venue_id)
        assert len(calls) == 4
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in original.items())


def test_format_export_ipc_accepts_only_exact_research_and_venue_authority():
    calls = []
    service = SimpleNamespace(reformat_portfolio_draft=lambda *args: calls.append(args) or {"ok": True})
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), io.BytesIO())
    message = {"id": "format-output", "method": "workflow.reformatPortfolioDraft",
        "params": {"researchId": "research-abcdefabcdef", "venueId": "ieee-software"}}
    try:
        assert ipc.request(json.dumps(message).encode()) == message
        assert dispatcher.execute(message["method"], message["params"]) == {"ok": True}
        assert calls == [("research-abcdefabcdef", "ieee-software")]
        for extra in ("reset", "retry", "value", "approve", "model"):
            with pytest.raises(ValueError):
                ipc.request(json.dumps({**message, "params": {**message["params"], extra: True}}).encode())
    finally:
        dispatcher._pool.shutdown(wait=True)

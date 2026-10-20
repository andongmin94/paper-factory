"""Known output defects use one append-only conversion, never new scientific evidence."""

import hashlib
import io
import json
import re
import zipfile
from types import SimpleNamespace

import pytest

from paper_factory import ipc
from paper_factory.autonomous import repository_portfolio as native
from paper_factory.autonomous.repository_paper import RepositoryManuscript
from paper_factory.models import Project
from paper_factory.workflow import WorkflowError
from test_repository_paper_workflow import study, draft, review
from test_repository_portfolio import portfolio, analyze_portfolio, retain_portfolio_response


def docx_bytes(caption="Witness boundary.", extra=""):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:pPr><w:pStyle w:val="TableCaption"/>' + extra + '</w:pPr><w:r><w:t>' + caption +
            '</w:t></w:r></w:p></w:body></w:document>')
    return stream.getvalue()


@pytest.fixture
def layout_export(portfolio, monkeypatch, request):
    service, rid, _, _ = portfolio
    analyzed = analyze_portfolio(service, rid)
    venue_id = analyzed["repository_paper"]["portfolio"]["targets"][0]["venue_id"]
    condition = getattr(request, "param", "after-format")
    original_render = native.render

    def historical_render(value, repository, commit, sources, documents, paths):
        manual = next((section for section in value.sections if section.heading == "References"), None)
        base = original_render(value.model_copy(update={"sections": [section for section in value.sections if section is not manual]}),
            "https://example.test/synthetic-repository", commit, sources, documents, paths)
        if condition in {"after-format", "labels"}:
            base = re.sub(r"\[`([^`]+)`\]\(", r"[\1](", base)
        boundary = base.rfind("## References\n\n")
        return base[:boundary] + ("## References\n\n" + manual.text + "\n\n" if manual else "") + base[boundary:]

    monkeypatch.setattr(native, "render", historical_render)
    value = draft(service, rid, prepare_analysis=False)
    if condition == "after-format":
        with service._operation(rid) as (ws, record):
            model = RepositoryManuscript.model_validate(value)
            sources, documents = service._portfolio_evidence(ws, record, model)
            imported = ws.latest("project", Project)
            rendered = historical_render(model, imported.source, imported.source_commit, sources, documents, [asset.path for asset in imported.assets])
        entries = rendered.rsplit("## References\n\n", 1)[1].strip()
        value["sections"].append({"heading": "References", "text": "\n\n".join("- " + re.sub(r"^\[\d+\] ", "", entry) for entry in entries.split("\n\n"))})
    key, _ = retain_portfolio_response(service, rid, value, "venue-manuscript", venue_id)
    service.submit_portfolio_manuscript(rid, {"venue_id": venue_id, "inference_artifact_id": key, "manuscript": value})
    assessment = review(True)
    assessment["criteria"]["presentation"]["passed"] = False
    assessment["issues"] = ["Synthetic known output formatting defect; no scientific claim is established."]
    assessment["content_assessment"]["issues"] = list(assessment["issues"])
    action = {"action": "revise_manuscript", "target": "References and output captions",
        "required_change": "Correct the known presentation defect without changing scientific or author bytes.",
        "verification": "Canonical reference identities and immutable scientific paragraphs remain exact."}
    assessment["next_actions"] = [action]
    assessment["content_assessment"]["next_actions"] = [action]
    assessment["content_assessment"]["revision_outline"] = [{"heading": "Discussion", "instruction": "Keep the exact scientific prose while correcting known output formatting."}]
    if condition == "science-failure":
        assessment["criteria"]["method"]["passed"] = False
    if condition == "comparison-failure":
        assessment["content_assessment"]["comparison"]["passed"] = False
    block = b"\nSynthetic immutable byline.\n"
    monkeypatch.setattr(service, "_repository_byline", lambda ws, record, text: (text.partition(b"\n")[0] + b"\n" + block + text.partition(b"\n")[2], block, None))
    calls = []

    def convert(source, output, **kwargs):
        calls.append((source, output))
        numbered = output.parent.name == "layout-1" or condition in {"labels", "none"}
        output.write_bytes(docx_bytes("Table 1: Witness boundary." if numbered else "Witness boundary.") if output.suffix == ".docx" else b"Synthetic fixture PDF only.")
        return {"input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "engine": "synthetic-fixture"}

    monkeypatch.setattr("paper_factory.conversion.convert", convert)
    before = service.export_portfolio_draft(rid, venue_id)
    key, _ = retain_portfolio_response(service, rid, assessment, "venue-manuscript-review", venue_id)
    service.submit_portfolio_review(rid, {"venue_id": venue_id, "inference_artifact_id": key, "review": assessment})
    before = service.status(rid)
    if condition == "after-format":
        assert not before["repository_paper"]["portfolio"]["venues"][0]["layout_export_available"]
        before = service.reformat_portfolio_draft(rid, venue_id)
    return service, rid, venue_id, before, calls


@pytest.mark.parametrize("layout_export", ["after-format", "labels", "captions"], indirect=True)
def test_layout_preserves_all_science_author_counts_old_outputs_and_format_scope(layout_export, monkeypatch, request):
    service, rid, venue_id, before, calls = layout_export
    old = before["repository_paper"]["portfolio"]["venues"][0]
    assert old["layout_export_available"] and old["layout_export_attempts"] == 0
    originals = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    monkeypatch.setattr(service, "_repository_byline", lambda *args: pytest.fail("Use the already exported author bytes"))
    prior_calls = len(calls)
    current = service.correct_portfolio_layout(rid, venue_id)
    venue = current["repository_paper"]["portfolio"]["venues"][0]
    receipt = venue["layout_export"]
    assert receipt["status"] == "completed" and receipt["model_calls"] == 0
    assert receipt["scope"] == "canonical-source-labels-and-docx-captions" and receipt["scientific_approval_changed"] is False
    assert venue["layout_export_attempts"] == 1 and not venue["layout_export_available"]
    for field in ("export", "export_status", "format_export", "format_export_attempts", "format_export_available", "draft", "review", "draft_sha256",
                  "draft_attempts", "review_attempts", "repair_attempts", "analysis_current", "scientific_ready", "content_ready", "submission_ready"):
        assert venue[field] == old[field]
    selected = old["format_export"] or old["export"]
    old_receipt = json.loads(originals[selected["artifact_id"]])
    assert receipt["original_artifact_id"] == selected["artifact_id"] and receipt["original_sha256"] == selected["sha256"]
    assert receipt["original_input_artifact_id"] == old_receipt["input_artifact_id"] and receipt["original_input_sha256"] == old_receipt["input_sha256"]
    assert receipt["author_block_sha256"] == old_receipt["author_block_sha256"]
    proof = receipt["layout_proof"]
    assert proof["original_markdown_sha256"] == old_receipt["input_sha256"]
    assert proof["scientific_body_sha256_before"] == proof["scientific_body_sha256_after"]
    assert bool(proof["changed_labels"]) == (request.node.callspec.params["layout_export"] != "captions")
    if request.node.callspec.params["layout_export"] == "captions":
        assert receipt["input_sha256"] == old_receipt["input_sha256"]
    input_raw = service.artifact_path(rid, receipt["input_artifact_id"]).read_bytes()
    assert b"Synthetic immutable byline." in input_raw and input_raw.count(b"## References") == 1
    for extension in ("pdf", "docx"):
        assert venue["artifact_ids"][extension] == f"repository-portfolio-{venue_id}-{extension}-layout-1"
        assert receipt["outputs"][extension]["conversion_artifact_id"] == f"repository-portfolio-{venue_id}-{extension}-conversion-layout-1"
        assert service.artifact_path(rid, venue["artifact_ids"][extension]).parent.name == "layout-1"
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in originals.items())
    for field in ("proposal_attempt", "study_literature_attempt", "draft_attempt", "code_attempt", "execution_attempt", "redesign_attempt"):
        assert current[field] == before[field]
    for field in ("analysis", "analysis_attempts", "draft", "review"):
        assert current["repository_paper"][field] == before["repository_paper"][field]
    assert current["repository_paper"]["portfolio"]["venues"][1:] == before["repository_paper"]["portfolio"]["venues"][1:]
    assert {key for key in current["artifacts"] if key.startswith("model-evidence-")} == {key for key in before["artifacts"] if key.startswith("model-evidence-")}
    service.correct_portfolio_layout(rid, venue_id)
    service.export_portfolio_draft(rid, venue_id)
    assert len(calls) == prior_calls + 2


@pytest.mark.parametrize("layout_export", ["none", "science-failure", "comparison-failure"], indirect=True)
def test_layout_rejects_unproven_defect_or_scientific_content_failure(layout_export):
    service, rid, venue_id, before, calls = layout_export
    venue = before["repository_paper"]["portfolio"]["venues"][0]
    assert not venue["layout_export_available"] and venue["layout_export_attempts"] == 0
    with pytest.raises(WorkflowError) as rejected:
        service.correct_portfolio_layout(rid, venue_id)
    assert rejected.value.code == "PORTFOLIO_LAYOUT_UNAVAILABLE" and len(calls) == 2
    assert service.status(rid)["artifacts"] == before["artifacts"]


@pytest.mark.parametrize("failure", ["failed", "interrupted"])
def test_layout_failed_or_unknown_conversion_keeps_old_format_output_and_one_attempt(layout_export, monkeypatch, failure):
    service, rid, venue_id, before, calls = layout_export
    old = before["repository_paper"]["portfolio"]["venues"][0]
    originals = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    prior_calls = len(calls)
    def fail(source, output, **kwargs):
        calls.append((source, output))
        if failure == "interrupted":
            raise RuntimeError("Synthetic unknown outcome after immutable layout intent")
        raise ValueError("Synthetic conversion failure")
    monkeypatch.setattr("paper_factory.conversion.convert", fail)
    if failure == "interrupted":
        with pytest.raises(RuntimeError):
            service.correct_portfolio_layout(rid, venue_id)
    else:
        service.correct_portfolio_layout(rid, venue_id)
    current = service.status(rid)
    venue = current["repository_paper"]["portfolio"]["venues"][0]
    assert venue["layout_export_attempts"] == 1 and not venue["layout_export_available"]
    assert venue["artifact_ids"] == old["artifact_ids"] and venue["format_export"] == old["format_export"]
    if failure == "interrupted":
        assert venue["layout_export"] is None
        with pytest.raises(WorkflowError) as rejected:
            service.correct_portfolio_layout(rid, venue_id)
        assert rejected.value.code == "PORTFOLIO_LAYOUT_INTERRUPTED" and len(calls) == prior_calls + 1
    else:
        assert venue["layout_export"]["status"] == "failed"
        service.correct_portfolio_layout(rid, venue_id)
        assert len(calls) == prior_calls + 2
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in originals.items())


def test_cancelled_layout_does_not_resume_or_change_research_status(layout_export):
    service, rid, venue_id, _, calls = layout_export
    cancelled = service.cancel(rid)
    current = service.correct_portfolio_layout(rid, venue_id)
    for field in ("status", "code", "cancellation_requested", "stage", "proposal_attempt", "study_literature_attempt", "draft_attempt", "execution_attempt", "code_attempt"):
        assert current[field] == cancelled[field]
    assert not any(key.startswith("repository-resume-") for key in current["artifacts"])
    assert len(calls) == 6


@pytest.mark.parametrize("new_caption", ["Still missing its number.", None])
def test_layout_caption_postcondition_failure_keeps_prior_outputs(layout_export, monkeypatch, new_caption):
    service, rid, venue_id, before, calls = layout_export
    old = before["repository_paper"]["portfolio"]["venues"][0]
    original = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    def defective_conversion(source, output, **kwargs):
        calls.append((source, output))
        if output.suffix == ".docx":
            raw = docx_bytes(new_caption) if new_caption else None
            # The second defect removes the actual caption paragraph style, preserving XML validity.
            if new_caption is None:
                stream = io.BytesIO()
                with zipfile.ZipFile(stream, "w") as archive:
                    archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>')
                raw = stream.getvalue()
            output.write_bytes(raw)
        else:
            output.write_bytes(b"Synthetic fixture PDF only.")
        return {"input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "engine": "synthetic-defective-fixture"}
    monkeypatch.setattr("paper_factory.conversion.convert", defective_conversion)
    current = service.correct_portfolio_layout(rid, venue_id)
    venue = current["repository_paper"]["portfolio"]["venues"][0]
    assert venue["layout_export"]["status"] == "failed" and venue["layout_export_attempts"] == 1
    assert [item["format"] for item in venue["layout_export"]["errors"]] == ["docx"]
    assert venue["artifact_ids"] == old["artifact_ids"] and venue["format_export"] == old["format_export"]
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in original.items())


@pytest.mark.parametrize("caption,extra", [("Table 1: Boundary.", ""), ("TABLE A1. Boundary.", ""), ("Boundary.", '<w:numPr><w:numId w:val="1"/></w:numPr>')])
def test_bounded_docx_caption_evidence_recognizes_numbering_without_false_defect(caption, extra):
    proof = native.RepositoryPortfolioMixin._portfolio_docx_captions(docx_bytes(caption, extra))
    assert proof["missing_numbering"] == 0
    assert native.RepositoryPortfolioMixin._portfolio_docx_captions(b"Not an OOXML document.") is None


def test_layout_ipc_accepts_only_exact_research_and_venue_authority():
    calls = []
    service = SimpleNamespace(correct_portfolio_layout=lambda *args: calls.append(args) or {"ok": True})
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), io.BytesIO())
    message = {"id": "known-layout", "method": "workflow.correctPortfolioLayout", "params": {"researchId": "research-abcdefabcdef", "venueId": "ieee-software"}}
    try:
        assert ipc.request(json.dumps(message).encode()) == message
        assert dispatcher.execute(message["method"], message["params"]) == {"ok": True}
        assert calls == [("research-abcdefabcdef", "ieee-software")]
        for extra in ("reset", "retry", "value", "approve", "model", "scope"):
            with pytest.raises(ValueError):
                ipc.request(json.dumps({**message, "params": {**message["params"], extra: True}}).encode())
    finally:
        dispatcher._pool.shutdown(wait=True)

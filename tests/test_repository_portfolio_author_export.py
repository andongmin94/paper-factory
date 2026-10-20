"""Byline exports retain the exact reviewed body and bounded immutable failures."""

import hashlib
import io
import json
import os
import re
from types import SimpleNamespace

import pytest

from paper_factory import ipc
from paper_factory.autonomous import repository_portfolio as native
from paper_factory.autonomous.repository_paper import RepositoryManuscript
from paper_factory.models import Project
from paper_factory.conversion import convert as native_convert
from paper_factory.workflow import WorkflowError
from test_repository_paper_workflow import study, draft, review
from test_repository_portfolio import portfolio, analyze_portfolio, retain_portfolio_response


PROFILE = {"display_name": "Synthetic Author", "affiliation": "Synthetic Institute",
    "email": "author@example.invalid", "orcid": "0000-0000-0000-0001"}
COUNTS = ("proposal_attempt", "study_literature_attempt", "draft_attempt", "code_attempt", "execution_attempt", "redesign_attempt")


def venue(status):
    return status["repository_paper"]["portfolio"]["venues"][0]


@pytest.fixture
def author_draft(portfolio, monkeypatch, request):
    service, rid, _, _ = portfolio
    analyze_portfolio(service, rid)
    venue_id = venue(service.status(rid))["venue_id"]
    condition = getattr(request, "param", "no-old-author")
    value = draft(service, rid, prepare_analysis=False)
    if condition == "formatted":
        original_render = native.render
        with service._operation(rid) as (ws, record):
            model = RepositoryManuscript.model_validate(value)
            sources, documents = service._portfolio_evidence(ws, record, model)
            imported = ws.latest("project", Project)
            rendered = original_render(model, imported.source, imported.source_commit, sources, documents, [asset.path for asset in imported.assets])
        canonical = rendered.rsplit("## References\n\n", 1)[1].strip()
        value["sections"].append({"heading": "References", "text": "\n\n".join("- " + re.sub(r"^\[\d+\] ", "", entry) for entry in canonical.split("\n\n"))})

        def historical_render(value, *args):
            manual = next(section for section in value.sections if section.heading == "References")
            base = original_render(value.model_copy(update={"sections": [section for section in value.sections if section is not manual]}), *args)
            boundary = base.rfind("## References\n\n")
            return base[:boundary] + "## References\n\n" + manual.text + "\n\n" + base[boundary:]

        monkeypatch.setattr(native, "render", historical_render)
    key, _ = retain_portfolio_response(service, rid, value, "venue-manuscript", venue_id)
    service.submit_portfolio_manuscript(rid, {"venue_id": venue_id, "inference_artifact_id": key, "manuscript": value})
    calls = []

    def convert(source, output, **kwargs):
        calls.append((source, output))
        output.write_bytes(b"Explicitly synthetic native fixture: " + output.suffix.encode() + b"\n" + source.read_bytes())
        return {"input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "engine": "synthetic-fixture"}

    monkeypatch.setattr("paper_factory.conversion.convert", convert)
    if condition == "old-author":
        service.set_author_metadata(rid, {**PROFILE, "display_name": "Previous Synthetic Author"})
    service.export_portfolio_draft(rid, venue_id)
    assessment = review(True)
    if condition == "formatted":
        assessment["criteria"]["presentation"]["passed"] = False
        assessment["issues"] = ["The synthetic manual reference block duplicates canonical references."]
        assessment["next_actions"] = [{"action": "revise_manuscript", "target": "References",
            "required_change": "Remove only the duplicate model reference block.",
            "verification": "Retain all original scientific paragraphs and canonical references."}]
        assessment["content_assessment"]["issues"] = list(assessment["issues"])
        assessment["content_assessment"]["next_actions"] = list(assessment["next_actions"])
        assessment["content_assessment"]["revision_outline"] = [{"heading": "Discussion", "instruction": "Remove duplicate references without changing any science."}]
    key, _ = retain_portfolio_response(service, rid, assessment, "venue-manuscript-review", venue_id)
    service.submit_portfolio_review(rid, {"venue_id": venue_id, "inference_artifact_id": key, "review": assessment})
    if condition == "formatted":
        service.reformat_portfolio_draft(rid, venue_id)
    return service, rid, venue_id, calls


@pytest.mark.parametrize("author_draft", ["no-old-author", "old-author"], indirect=True)
def test_author_export_preserves_science_history_counts_and_latest_explicit_profile(author_draft):
    service, rid, venue_id, calls = author_draft
    if venue(service.status(rid))["author_export_status"] == "unavailable":
        with pytest.raises(WorkflowError) as failure:
            service.export_portfolio_author(rid, venue_id)
        assert failure.value.code == "PORTFOLIO_AUTHOR_UNAVAILABLE"
    before = service.set_author_metadata(rid, PROFILE)
    old = venue(before)
    assert old["author_export_available"] and old["author_export_attempts"] == 0
    originals = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    base = json.loads(originals[old["export"]["artifact_id"]])
    base_input = originals[base["input_artifact_id"]]
    prior_calls = len(calls)
    current = service.export_portfolio_author(rid, venue_id)
    result = venue(current)
    receipt = result["author_export"]
    assert receipt["status"] == "completed" and receipt["current"] is True and receipt["model_calls"] == 0
    assert result["author_export_attempts"] == 1 and not result["author_export_available"]
    assert result["author_export_status"] == "completed"
    assert receipt["scope"] == "explicit-author-block-only" and receipt["scientific_approval_changed"] is False
    assert receipt["bindings"]["author_sha256"] == current["author_metadata"]["sha256"]
    assert receipt["bindings"]["review_sha256"] == before["artifacts"][old["artifact_ids"]["review"]]["sha256"]
    raw = service.artifact_path(rid, receipt["input_artifact_id"]).read_bytes()
    assert raw.count(b"Synthetic Author") == 1 and b"Previous Synthetic Author" not in raw
    literal = raw.replace(b"\\", b"")
    assert b"author@example.invalid" in literal and b"0000-0000-0000-0001" in literal
    assert raw.partition(b"\n")[0] == base_input.partition(b"\n")[0]
    markdown = originals[old["artifact_ids"]["markdown"]]
    assert raw.endswith(markdown.partition(b"\n")[2])
    for extension in ("pdf", "docx"):
        assert result["artifact_ids"][extension] == receipt["outputs"][extension]["artifact_id"]
        assert service.artifact_path(rid, result["artifact_ids"][extension]).parent.name == "author-1"
    assert all(service.artifact_path(rid, key).read_bytes() == saved for key, saved in originals.items())
    assert {name: current[name] for name in COUNTS} == {name: before[name] for name in COUNTS}
    for name in ("draft", "review", "draft_sha256", "draft_attempts", "review_attempts", "content_ready", "scientific_ready", "submission_ready"):
        assert result[name] == old[name]
    assert result["submission_ready"] is False
    assert {key for key in current["artifacts"] if key.startswith("model-evidence-")} == {key for key in before["artifacts"] if key.startswith("model-evidence-")}
    again = service.export_portfolio_author(rid, venue_id)
    assert again["artifacts"] == current["artifacts"] and len(calls) == prior_calls + 2


def test_changed_author_invalidates_current_outputs_and_keeps_old_receipts(author_draft):
    service, rid, venue_id, calls = author_draft
    service.set_author_metadata(rid, PROFILE)
    first = service.export_portfolio_author(rid, venue_id)
    first_venue = venue(first)
    original = {key: service.artifact_path(rid, key).read_bytes() for key in first["artifacts"]}
    changed = service.set_author_metadata(rid, {**PROFILE, "display_name": "Second Synthetic Author"})
    stale = venue(changed)
    assert stale["author_export_status"] == "stale" and stale["author_export"] is None
    assert stale["author_export_attempts"] == 1 and stale["author_export_available"]
    assert stale["artifact_ids"]["pdf"] != first_venue["artifact_ids"]["pdf"]
    current = service.export_portfolio_author(rid, venue_id)
    assert venue(current)["author_export"]["attempt"] == 2
    assert b"Second Synthetic Author" in service.artifact_path(rid, venue(current)["author_export"]["input_artifact_id"]).read_bytes()
    assert all(service.artifact_path(rid, key).read_bytes() == saved for key, saved in original.items())
    # Re-selecting the exact previous profile reuses its completed binding.
    restored = service.set_author_metadata(rid, PROFILE)
    assert venue(restored)["author_export"]["artifact_id"] == first_venue["author_export"]["artifact_id"]
    total = len(calls)
    repeated = service.export_portfolio_author(rid, venue_id)
    assert repeated["artifacts"] == restored["artifacts"] and len(calls) == total


@pytest.mark.parametrize("author_draft", ["formatted"], indirect=True)
def test_author_export_preserves_corrected_bibliography_input_and_unapproved_review(author_draft):
    service, rid, venue_id, _ = author_draft
    before = service.set_author_metadata(rid, PROFILE)
    old = venue(before)
    formatted = old["format_export"]
    assert formatted["status"] == "completed" and not old["content_ready"]
    body = service.artifact_path(rid, formatted["input_artifact_id"]).read_bytes().partition(b"\n")[2]
    assert body.count(b"## References") == 1
    originals = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    current = service.export_portfolio_author(rid, venue_id)
    result = venue(current)
    receipt = result["author_export"]
    raw = service.artifact_path(rid, receipt["input_artifact_id"]).read_bytes()
    assert receipt["bindings"]["base_export_artifact_id"] == formatted["artifact_id"]
    assert receipt["body_sha256"] == hashlib.sha256(body).hexdigest()
    assert raw.endswith(body) and raw.count(b"## References") == 1
    assert result["review"] == old["review"] and result["scientific_ready"] is old["scientific_ready"]
    assert not result["content_ready"] and not result["submission_ready"]
    assert all(service.artifact_path(rid, key).read_bytes() == saved for key, saved in originals.items())


@pytest.mark.parametrize("failure", ["conversion", "interrupted", "orphan-directory"])
def test_author_failed_and_unknown_attempts_preserved_and_bounded_to_three(author_draft, monkeypatch, failure):
    service, rid, venue_id, _ = author_draft
    before = service.set_author_metadata(rid, PROFILE)
    originals = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    parent = service.artifact_path(rid, venue(before)["artifact_ids"]["draft"]).parent
    failures = []

    def fail(source, output, **kwargs):
        failures.append(output)
        output.write_bytes(b"Retained synthetic failure or unknown output bytes.")
        if failure == "interrupted":
            raise RuntimeError("Synthetic interruption")
        raise ValueError("Synthetic converter refusal")

    monkeypatch.setattr("paper_factory.conversion.convert", fail)
    for attempt in range(1, 4):
        if failure == "orphan-directory":
            (parent / f"author-{attempt}").mkdir()
            (parent / f"author-{attempt}" / "partial.raw").write_bytes(b"Retained unknown reservation bytes.")
        elif failure == "interrupted":
            with pytest.raises(RuntimeError, match="Synthetic interruption"):
                service.export_portfolio_author(rid, venue_id)
        else:
            service.export_portfolio_author(rid, venue_id)
        current = service.status(rid)
        result = venue(current)
        assert result["author_export_attempts"] == attempt
        assert result["author_export_available"] is (attempt < 3)
        assert result["author_export_status"] == ("failed" if failure == "conversion" else "interrupted")
        assert result["artifact_ids"]["pdf"] == venue(before)["artifact_ids"]["pdf"]
        assert {name: current[name] for name in COUNTS} == {name: before[name] for name in COUNTS}
    files = {path: path.read_bytes() for attempt in range(1, 4) for path in (parent / f"author-{attempt}").iterdir() if path.is_file()}
    with pytest.raises(WorkflowError) as limit_failure:
        service.export_portfolio_author(rid, venue_id)
    assert limit_failure.value.code == "PORTFOLIO_AUTHOR_LIMIT"
    assert all(path.read_bytes() == saved for path, saved in files.items())
    assert all(service.artifact_path(rid, key).read_bytes() == saved for key, saved in originals.items())
    assert len(failures) == (6 if failure == "conversion" else 3 if failure == "interrupted" else 0)


def test_author_export_keeps_cancelled_research_stopped_and_does_not_invent_approval(author_draft):
    service, rid, venue_id, _ = author_draft
    service.set_author_metadata(rid, PROFILE)
    cancelled = service.cancel(rid)
    current = service.export_portfolio_author(rid, venue_id)
    assert current["status"] == cancelled["status"] and current["code"] == cancelled["code"]
    assert current["author_metadata"]["origin"] == "explicit_human_author_metadata"
    assert not venue(current)["submission_ready"]


def test_author_export_creates_actual_native_word_and_pdf_with_literal_profile(author_draft, monkeypatch, pandoc):
    if os.name != "nt":
        pytest.skip("Official-template native PDF rendering requires Windows and Microsoft Word")
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID"):
            pass
    except FileNotFoundError:
        pytest.skip("Microsoft Word is not installed; publisher DOCX and explicit missing-renderer behavior are tested separately")
    from docx import Document
    from pypdf import PdfReader
    service, rid, venue_id, _ = author_draft
    before = service.set_author_metadata(rid, PROFILE)
    original = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    monkeypatch.setattr("paper_factory.conversion.convert", lambda source, output, **kwargs: native_convert(source, output, **{**kwargs, "pandoc": pandoc}))
    current = service.export_portfolio_author(rid, venue_id)
    result = venue(current)
    assert result["author_export_status"] == "completed"
    for extension in ("pdf", "docx"):
        output = service.artifact_path(rid, result["artifact_ids"][extension])
        text = (" ".join(page.extract_text() or "" for page in PdfReader(output).pages) if extension == "pdf" else
            " ".join(paragraph.text for paragraph in Document(output).paragraphs))
        assert all(value in " ".join(text.split()) for value in PROFILE.values())
    assert all(service.artifact_path(rid, key).read_bytes() == saved for key, saved in original.items())
    assert {name: current[name] for name in COUNTS} == {name: before[name] for name in COUNTS}


def test_author_export_ipc_exact_route_rejects_approval_or_reset_flags():
    calls = []
    service = SimpleNamespace(export_portfolio_author=lambda *args: calls.append(args) or {"ok": True})
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), io.BytesIO())
    params = {"researchId": "research-abcdefabcdef", "venueId": "ieee-software"}
    request = {"id": "author", "method": "workflow.exportPortfolioAuthor", "params": params}
    try:
        assert ipc.request(json.dumps(request).encode()) == request
        for flag in ("reset", "approved", "identityVerified"):
            with pytest.raises(ValueError):
                ipc.request(json.dumps({**request, "params": {**params, flag: True}}).encode())
        assert dispatcher.execute(request["method"], params) == {"ok": True}
        assert calls == [(params["researchId"], params["venueId"])]
    finally:
        dispatcher._pool.shutdown(wait=True)

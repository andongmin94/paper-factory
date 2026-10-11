"""Synthetic export and explicit-human completion checks; no actual study/network."""

import copy
import hashlib
import json
import re

import pytest
from pydantic import ValidationError

from paper_factory import ipc, submission_requirements
from paper_factory.workflow import WorkflowError, _freeze
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import write_json
from test_submission_workflow import assessment, contract, manuscript, measured, observed
from test_workflow import setup

AUTHOR = {"display_name": "Synthetic Author", "email": "synthetic@example.org", "affiliation": "Synthetic Test Institute"}
URL = "https://publisher.example.org/authors/instructions"
BODY = b"<html><body>Official author instructions retained only as a synthetic fixture. Inspect the article type, citations, figures, declarations, author identity and submission forms.</body></html>"


def retained(url):
    return {"url": url, "status": "retained", "http_status": 200, "content_type": "text/html; charset=utf-8",
            "raw": BODY, "text": submission_requirements.requirement_text(BODY, "text/html"),
            "raw_sha256": hashlib.sha256(BODY).hexdigest(), "error": None}


@pytest.fixture
def exported(setup, monkeypatch, pandoc):
    service, runner, identifier = measured(setup)
    service.set_author_metadata(identifier, AUTHOR)
    state = service.submit_manuscript(identifier, manuscript(), assessment(), observed())
    assert state["submission_readiness"]["science_verified"] is True
    monkeypatch.setenv("PYPANDOC_PANDOC", pandoc)
    state = service.export(identifier)
    assert state["stage"] == "exported" and state["code"] == "SUBMISSION_PENDING"
    assert state["submission_readiness"]["ready"] is False
    assert state["submission_readiness"]["visual_pages"]
    monkeypatch.setattr(submission_requirements, "fetch_requirements", retained)
    return service, runner, identifier


def confirmation(state):
    ready = state["submission_readiness"]
    return {**{key: ready[key] for key in ("manuscript_sha256", "pdf_sha256", "package_sha256", "canonical_sha256", "author_sha256")},
            "selected_venue": contract()["venue_candidates"][0]["name"], "requirements_artifact_id": "submission-requirements",
            "requirements_sha256": state["artifacts"]["submission-requirements"]["sha256"],
            "pages": [{key: page[key] for key in ("number", "image_sha256", "text_sha256")} for page in ready["visual_pages"]],
            **{key: True for key in ("official_source_confirmed", "venue_requirements_confirmed", "visual_pages_confirmed",
                                    "author_accuracy_confirmed", "authorship_rights_confirmed", "declarations_confirmed")},
            "reason": "A synthetic explicit human attestation for exactly these retained bytes; no real author, venue or study is approved."}


def test_exact_current_human_checks_can_reach_ready_without_scientific_rerun(exported):
    service, runner, identifier = exported
    before = service.status(identifier)
    state = service.collect_submission_requirements(identifier, contract()["venue_candidates"][0]["name"], URL)
    assert state["submission_requirements"]["status"] == "retained"
    result = service.confirm_submission_readiness(identifier, confirmation(state))
    assert result["status"] == "completed" and result["submission_readiness"]["ready"] is True
    assert all(result["submission_readiness"][key] is True for key in ("science_verified", "formats_verified", "venue_verified", "visual_verified", "author_verified"))
    assert result["submission_confirmation"]["origin"] == "explicit_human_submission_confirmation"
    assert result["execution_attempt"] == runner.calls == 1
    assert {key: result[key] for key in ("proposal_attempt", "code_attempt", "draft_attempt")} == {key: before[key] for key in ("proposal_attempt", "code_attempt", "draft_attempt")}
    assert all(result["artifacts"][key] == item for key, item in before["artifacts"].items())
    assert service.confirm_submission_readiness(identifier, confirmation(state))["artifacts"] == result["artifacts"]
    assert service.export(identifier)["submission_readiness"]["ready"] is True
    with pytest.raises(WorkflowError):
        service.start_experiment(identifier)
    archive = service.artifact_path(identifier, "reproducibility")
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == before["artifacts"]["reproducibility"]["sha256"]


def test_confirmation_a_b_a_restores_exact_earlier_receipt_without_overwrite(exported):
    service, runner, identifier = exported
    state = service.collect_submission_requirements(identifier, contract()["venue_candidates"][0]["name"], URL)
    value_a = confirmation(state)
    first = service.confirm_submission_readiness(identifier, value_a)
    paths = {service.artifact_path(identifier, key): service.artifact_path(identifier, key).read_bytes()
             for key in first["artifacts"] if key.startswith("submission-confirmation-")}
    value_b = {**value_a, "reason": "A different explicit synthetic human confirmation of the same unchanged current package."}
    second = service.confirm_submission_readiness(identifier, value_b)
    assert second["artifacts"]["submission-confirmation"] != first["artifacts"]["submission-confirmation"]
    restored = service.confirm_submission_readiness(identifier, value_a)
    expected = {**second["artifacts"], "submission-confirmation": first["artifacts"]["submission-confirmation"]}
    assert restored["artifacts"] == expected
    assert restored["submission_confirmation"] == first["submission_confirmation"] and restored["submission_readiness"]["ready"] is True
    assert all(path.read_bytes() == raw for path, raw in paths.items())
    assert service.confirm_submission_readiness(identifier, value_a)["artifacts"] == restored["artifacts"]
    assert restored["execution_attempt"] == runner.calls == 1


def test_requirement_switch_holds_until_exact_current_confirmation_and_can_restore_prior_check(exported):
    service, runner, identifier = exported
    venue = contract()["venue_candidates"][0]["name"]
    source_a = service.collect_submission_requirements(identifier, venue, URL)
    value_a = confirmation(source_a)
    first = service.confirm_submission_readiness(identifier, value_a)
    assert service.collect_submission_requirements(identifier, venue, URL)["status"] == "completed"
    paths = {service.artifact_path(identifier, key): service.artifact_path(identifier, key).read_bytes()
             for key in first["artifacts"] if key.startswith(("submission-confirmation-", "submission-requirements-"))}
    source_b = service.collect_submission_requirements(identifier, venue, URL + "?revision=2")
    assert source_b["status"] == "ready" and source_b["code"] == "SUBMISSION_PENDING"
    assert source_b["submission_readiness"]["ready"] is False and source_b["submission_confirmation"] is None
    value_b = confirmation(source_b)
    second = service.confirm_submission_readiness(identifier, value_b)
    assert second["submission_readiness"]["ready"] is True
    restored_requirements = service.collect_submission_requirements(identifier, venue, URL)
    assert restored_requirements["status"] == "ready" and restored_requirements["code"] == "SUBMISSION_PENDING"
    assert restored_requirements["submission_confirmation"] is None
    restored = service.confirm_submission_readiness(identifier, value_a)
    assert restored["status"] == "completed" and restored["code"] is None and restored["submission_readiness"]["ready"] is True
    assert restored["submission_confirmation"] == first["submission_confirmation"]
    assert all(path.read_bytes() == raw for path, raw in paths.items())
    assert restored["execution_attempt"] == runner.calls == 1
    assert {key: restored[key] for key in ("proposal_attempt", "code_attempt", "draft_attempt")} == {key: first[key] for key in ("proposal_attempt", "code_attempt", "draft_attempt")}


@pytest.mark.parametrize("defect", ["missing_page", "page_hash", "pdf", "package", "author", "venue", "requirements", "false_flag"])
def test_confirmation_rejects_incomplete_stale_or_unaffirmed_checks(exported, defect):
    service, runner, identifier = exported
    state = service.collect_submission_requirements(identifier, contract()["venue_candidates"][0]["name"], URL)
    value = confirmation(state)
    if defect == "missing_page":
        value["pages"] = value["pages"][1:]
    elif defect == "page_hash":
        value["pages"][0]["image_sha256"] = "0" * 64
    elif defect in {"pdf", "package", "author"}:
        value[defect + "_sha256"] = "0" * 64
    elif defect == "venue":
        value["selected_venue"] = "Invented new venue"
    elif defect == "requirements":
        value["requirements_sha256"] = "0" * 64
    else:
        value["declarations_confirmed"] = False
    with pytest.raises((WorkflowError, ValidationError)):
        service.confirm_submission_readiness(identifier, value)
    assert service.status(identifier)["submission_confirmation"] is None and runner.calls == 1


def test_failed_requirements_are_retained_and_identical_request_does_not_retry(exported, monkeypatch):
    service, runner, identifier = exported
    calls = []
    def crash(url):
        calls.append(url)
        raise OSError("Synthetic failed HTTPS retrieval")
    monkeypatch.setattr(submission_requirements, "fetch_requirements", crash)
    first = service.collect_submission_requirements(identifier, contract()["venue_candidates"][0]["name"], URL)
    assert first["submission_requirements"]["status"] == "failed"
    assert first["submission_requirements"]["raw_sha256"] == hashlib.sha256(b"").hexdigest()
    assert service.collect_submission_requirements(identifier, contract()["venue_candidates"][0]["name"], URL)["artifacts"] == first["artifacts"]
    assert calls == [URL] and runner.calls == 1
    with pytest.raises(WorkflowError, match="requirements body"):
        service.confirm_submission_readiness(identifier, confirmation(first))


def test_writing_revision_preserves_checks_and_invalidates_current_submission_readiness(exported):
    service, runner, identifier = exported
    collected = service.collect_submission_requirements(identifier, contract()["venue_candidates"][0]["name"], URL)
    approved = service.confirm_submission_readiness(identifier, confirmation(collected))
    revised = service.revise_writing(identifier)
    assert revised["submission_readiness"]["ready"] is False and revised["submission_confirmation"] is None
    assert revised["submission_requirements"] is None
    assert revised["execution_attempt"] == runner.calls == 1
    assert revised["artifacts"]["submission-confirmation"] == approved["artifacts"]["submission-confirmation"]


def test_two_exports_preserve_every_previous_pdf_page_and_typst_source(exported):
    service, runner, identifier = exported
    before = service.status(identifier)
    quality = {key: value for key, value in before["artifacts"].items() if re.fullmatch(r"pdf-quality(?:-source|-[a-f0-9]{12})?", key)}
    bytes_before = {service.artifact_path(identifier, key): service.artifact_path(identifier, key).read_bytes() for key in quality}
    revised = service.revise_writing(identifier)
    revision_id = next(key for key in revised["artifacts"] if re.fullmatch(r"authoring-revision-[a-f0-9]{12}", key))
    receipt = json.loads(service.artifact_path(identifier, revision_id).read_bytes())
    for key, value in quality.items():
        history_key = receipt["preserved_artifacts"][key]
        assert revised["artifacts"][history_key]["sha256"] == value["sha256"]
        assert key not in revised["artifacts"]
    draft = manuscript()
    next(section for section in draft["sections"] if section["heading"] == "Discussion")["text"] += " Revised exposition preserves every former document byte and all actual observed synthetic values."
    service.submit_manuscript(identifier, draft, assessment(), observed())
    exported_again = service.export(identifier)
    for key, value in quality.items():
        history_key = receipt["preserved_artifacts"][key]
        assert exported_again["artifacts"][history_key]["sha256"] == value["sha256"]
    assert all(path.read_bytes() == raw for path, raw in bytes_before.items())
    assert exported_again["artifacts"]["pdf-quality-source"]["sha256"] != quality["pdf-quality-source"]["sha256"]
    assert exported_again["execution_attempt"] == runner.calls == 1
    assert exported_again["proposal_attempt"] == before["proposal_attempt"] and exported_again["draft_attempt"] == before["draft_attempt"] + 1


def test_author_metadata_is_explicit_append_only_and_must_precede_reviewed_export(setup):
    service, runner, identifier = measured(setup)
    first = service.set_author_metadata(identifier, AUTHOR)
    updated = service.set_author_metadata(identifier, {**AUTHOR, "affiliation": "Updated Synthetic Institute"})
    assert all(updated["artifacts"][key] == item for key, item in first["artifacts"].items() if key != "author-metadata")
    value = service.submit_manuscript(identifier, manuscript(), assessment(), observed())
    assert json.loads(service.artifact_path(identifier, "canonical").read_bytes())["author"]["affiliation"] == "Updated Synthetic Institute"
    with pytest.raises(WorkflowError):
        service.set_author_metadata(identifier, AUTHOR)
    assert value["execution_attempt"] == runner.calls == 1


def test_retained_confirmation_cannot_rebind_a_different_page_after_hash_update(exported):
    service, runner, identifier = exported
    state = service.collect_submission_requirements(identifier, contract()["venue_candidates"][0]["name"], URL)
    service.confirm_submission_readiness(identifier, confirmation(state))
    ws = service._workspace(identifier)
    record = ws.get("workflow", identifier, Workflow)
    path = service.artifact_path(identifier, "submission-confirmation")
    receipt = json.loads(path.read_bytes())
    receipt["value"]["pages"][0]["image_sha256"] = "0" * 64
    write_json(path, receipt)
    _freeze(ws, record, "submission-confirmation", path)
    ws.save("workflow", record)
    with pytest.raises(WorkflowError, match="PDF pages"):
        service.status(identifier)
    assert runner.calls == 1


@pytest.mark.parametrize("url", ["http://example.org/rules", "https://127.0.0.1/rules", "https://10.0.0.1/rules",
                                 "https://localhost/rules", "https://test.local/rules", "https://user:pw@example.org/rules",
                                 "https://example.org:8443/rules", "https://example.org/rules#fragment"])
def test_requirements_url_rejects_nonpublic_or_unbounded_routes(url):
    with pytest.raises(ValueError):
        submission_requirements.public_https_url(url)


def test_requirements_dns_is_pinned_and_private_addresses_never_connect(monkeypatch):
    monkeypatch.setattr(submission_requirements.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))])
    monkeypatch.setattr(submission_requirements.http.client, "HTTPSConnection", lambda *args, **kwargs: pytest.fail("Private DNS must never connect"))
    result = submission_requirements.fetch_requirements(URL)
    assert result["status"] == "failed" and "public" in result["error"] and result["raw"] == b""


@pytest.mark.parametrize("failure", ["deadline", "timeout", "redirect"])
def test_requirements_failure_preserves_partial_response_and_refuses_redirect(monkeypatch, failure):
    class Response:
        status = 302 if failure == "redirect" else 200
        calls = 0
        def getheader(self, name, default=""):
            return "text/plain" if name == "Content-Type" else default
        def read1(self, size):
            self.calls += 1
            if self.calls == 1:
                return b"Preserved partial official requirements response. " * 2
            if failure == "timeout":
                raise OSError("Synthetic socket timeout after retained partial response")
            return b""
    class Connection:
        sock = None
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            return Response()
        def close(self):
            pass
    monkeypatch.setattr(submission_requirements.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("8.8.8.8", 443))])
    monkeypatch.setattr(submission_requirements.http.client, "HTTPSConnection", lambda *args, **kwargs: Connection())
    if failure == "deadline":
        ticks = iter((0, 1, 16))
        monkeypatch.setattr(submission_requirements.time, "monotonic", lambda: next(ticks))
    result = submission_requirements.fetch_requirements(URL)
    assert result["status"] == "failed" and result["text"] is None
    assert result["raw"] == b"Preserved partial official requirements response. " * 2
    assert result["raw_sha256"] == hashlib.sha256(result["raw"]).hexdigest()


def test_body_parser_does_not_treat_script_or_empty_html_as_requirements():
    with pytest.raises(ValueError):
        submission_requirements.requirement_text(b"<script>" + b"Invented rules. " * 20 + b"</script>", "text/html")
    with pytest.raises(ValueError):
        submission_requirements.requirement_text(BODY, "application/pdf")


def test_completion_ipc_has_no_optional_scientific_injection():
    params = {"researchId": "research-" + "1" * 12, "venue": "Synthetic pending venue", "url": URL}
    assert ipc.request(json.dumps({"id": "requirements", "method": "workflow.collectSubmissionRequirements", "params": params}).encode())["params"] == params
    with pytest.raises(ValueError):
        ipc.request(json.dumps({"id": "requirements", "method": "workflow.collectSubmissionRequirements", "params": {**params, "oracle": "invented"}}).encode())

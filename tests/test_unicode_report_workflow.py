"""Synthetic official HTML/native contracts; no network or scholarly success."""
import copy
import json

import pytest

from paper_factory.autonomous import literature, science
from paper_factory.workflow import WorkflowError, _retained_primary_body, _verified_unicode_report
from paper_factory.workflow_models import Workflow
from test_autonomous_literature import clock
from test_autonomous_science import valid_draft
from test_unicode_literature import install, public_response
from test_workflow import STUDY_REVIEW, observations, protocol, rejected_study_review, setup


TITLE = "Literal Segmentation Standard"


def initial(setup, monkeypatch, mutate=None):
    service, runner, identifier = setup
    install(monkeypatch, public_response)
    plan = protocol()
    plan["literature_queries"] = [TITLE]
    service.submit_proposal(identifier, plan)

    def retrieve(*args, **kwargs):
        packet = literature.collect(*args, **kwargs)
        if mutate:
            mutate(packet["sources"][0])
        return packet

    service.collector = retrieve
    state = service.collect_literature(identifier)
    return service, runner, identifier, state


def approval(source):
    review = copy.deepcopy(STUDY_REVIEW)
    review["selected_sources"][0]["source_id"] = source["id"]
    review["publication_readiness"]["closest_work"][0].update(source_id=source["id"], quote=source["excerpts"][0][:100])
    return review


def test_official_html_requires_frozen_primary_body_and_fresh_study_review(setup, monkeypatch, clock):
    service, runner, identifier, state = initial(setup, monkeypatch)
    source, = state["literature"]["sources"]
    ws = service._workspace(identifier)
    record = ws.latest("workflow", Workflow)
    extracted = _verified_unicode_report(ws, source, record)
    assert extracted["body_range"] == source["body_range"]
    assert _retained_primary_body(ws, record, source, state["literature"])
    originals = {service.artifact_path(identifier, key): service.artifact_path(identifier, key).read_bytes()
                 for key in state["artifacts"]}
    accepted = service.submit_study_review(identifier, approval(source))
    assert accepted["stage"] == "planned" and accepted["execution_attempt"] == 0 and runner.calls == 0
    assert all(path.read_bytes() == raw for path, raw in originals.items())
    service._require_study_review(ws, ws.latest("workflow", Workflow))


@pytest.mark.parametrize("defect", ["revision", "body", "section", "role", "publisher", "query", "authors"])
def test_model_approval_cannot_replace_official_header_or_dom_boundaries(setup, monkeypatch, clock, defect):
    def mutate(source):
        if defect == "revision": source["revision"] += 1
        elif defect == "body": source["body_range"]["start"] += 1
        elif defect == "section": source["section_ranges"][0]["end"] -= 1
        elif defect == "role": source["author_role"] = "author"
        elif defect == "publisher": source["publisher"] = "Invented authority"
        elif defect == "query": source["queries"] = ["Unrelated title that was never this catalog entry"]
        else: source["authors"] = ["Invented author"]
    service, runner, identifier, state = initial(setup, monkeypatch, mutate)
    with pytest.raises(WorkflowError) as rejected:
        service.submit_study_review(identifier, approval(state["literature"]["sources"][0]))
    assert rejected.value.code in {"PUBLICATION_EVIDENCE_INVALID", "LITERATURE_SELECTION_INVALID"}
    after = service.status(identifier)
    assert after["stage"] == "proposed" and after["artifacts"] == state["artifacts"] and runner.calls == 0


def test_official_proof_cannot_be_reused_without_all_original_native_bindings(setup, monkeypatch, clock):
    service, runner, identifier, state = initial(setup, monkeypatch)
    source, = state["literature"]["sources"]
    ws = service._workspace(identifier)
    record = ws.latest("workflow", Workflow).model_copy(deep=True)
    raw = (ws.path("research") / source["raw_path"]).relative_to(ws.root).as_posix()
    for key in [key for key, value in record.artifacts.items() if value.path == raw]:
        del record.artifacts[key]
    with pytest.raises(WorkflowError, match="frozen"):
        _verified_unicode_report(ws, source, record)
    assert runner.calls == 0


def test_exact_retained_standard_reuses_bytes_but_does_not_inherit_approval(setup, monkeypatch, clock):
    service, runner, identifier, state = initial(setup, monkeypatch)
    source, = state["literature"]["sources"]
    service.submit_study_review(identifier, rejected_study_review())
    old_path = service.artifact_path(identifier, "literature")
    old_bytes = old_path.read_bytes()
    plan = copy.deepcopy(state["proposal"])
    plan["expected_contribution"] += " Independently resolve the retained synthetic critique."
    service.submit_proposal(identifier, plan)
    service.collector = lambda *args, **kwargs: pytest.fail("Verified exact body must not repeat retrieval")
    retained = service.collect_literature(identifier)
    assert retained["literature"]["sources"] == [source] and retained["study_review"] is None
    assert len(retained["literature"]["retained_queries"]) == 1 and old_path.read_bytes() == old_bytes
    assert service.submit_study_review(identifier, approval(source))["stage"] == "planned" and runner.calls == 0


def test_standard_canonical_citation_and_reference_preserve_version_role_and_literal_text(setup, monkeypatch, clock, tmp_path):
    service, runner, identifier, state = initial(setup, monkeypatch)
    source, = state["literature"]["sources"]
    draft = valid_draft()
    for section in draft["sections"]:
        section["text"] = section["text"].replace("{{citation:source-oracle}}", "{{citation:" + source["id"] + "}}")
        if section["heading"] == "Method":
            section["text"] += " Instrumentation was {{parameter:setting.execution_instrumentation}}."
    plan = state["proposal"]
    analysis = science.analyze(observations(), plan, tmp_path / "analysis")
    result = science.validate_and_render(draft, plan, analysis, state["literature"], tmp_path / "draft")
    canonical = json.loads((tmp_path / "draft" / "manuscript.json").read_bytes())
    citation, = canonical["citation_evidence"]
    assert citation["doi"] == "" and citation["standard_version"] == "18.0.0" and citation["revision"] == 7
    assert citation["author_role"] == "editor" and citation["section_ranges"] == source["section_ranges"]
    assert citation["identity_sha256"] == source["identity_sha256"]
    markdown = (tmp_path / "draft" / "manuscript.md").read_text(encoding="utf-8")
    assert "Unicode Consortium, UAX77, Unicode 18.0.0, revision 7" in markdown
    assert "contributors recorded as editor" in markdown and source["url"] in markdown
    assert not result["errors"] and runner.calls == 0

"""Bounded synthetic evidence revisions; no academic merit or actual SCI is asserted."""
import copy
import hashlib
import json
import os
import zipfile

import httpx
import pytest

from paper_factory import ipc
from paper_factory.autonomous import literature, science
from paper_factory.autonomous.models import FrozenArtifact, PublicationReadiness, ResearchPlan, StudyReview
from paper_factory.workflow import WorkflowError
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import digest_file, write_json
from test_workflow import BUNDLE, MANUSCRIPT_REVIEW, REVIEW, STUDY_REVIEW, SYNTHETIC_PREFIX, SYNTHETIC_SUFFIX, collect, manuscript, observations, protocol, retained_authoring_fixture, setup

QUERIES = ["direct closest methods synthetic fixture"]
REASON = "The retained review requires primary methods for its unresolved knowledge difference."
PDF_HINT = {"doi": "10.1234/test", "title": "Verified record title"}
PDF_URL = "https://www.cs.cmu.edu/~NatProg/papers/verified-author.pdf"


def rejected():
    value = copy.deepcopy(STUDY_REVIEW)
    value.update(accepted=False, issues=["Directly inspected closest methods are missing for the proposed contribution."])
    value["contribution"]["passed"] = False
    value["publication_readiness"]["novelty"]["passed"] = False
    return value


def initial(setup):
    service, runner, research_id = setup
    service.submit_proposal(research_id, protocol())
    service.collect_literature(research_id)
    state = service.submit_study_review(research_id, rejected())
    return service, runner, research_id, state


def collector(*, identifier="new-primary", extra=" Additional directly inspected synthetic methods distinguish this evidence packet.", flags=None, no_sources=False, missing_query=False):
    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        assert limit == 3
        assert isinstance(pdf_candidates, list)
        evidence = collect(queries, root, limit=limit, cancel=cancel)
        source = evidence["sources"][0]
        source["id"] = identifier
        if extra:
            passage = source["excerpts"][0] + extra
            full_text = SYNTHETIC_PREFIX + passage + SYNTHETIC_SUFFIX
            path = root / source["text_path"]
            path.write_bytes(full_text.encode())
            source.update(excerpts=[passage], text_sha256=digest_file(path), body_range=literature.full_text_body_range(full_text),
                          excerpt_ranges=[{"start": len(SYNTHETIC_PREFIX), "end": len(SYNTHETIC_PREFIX) + len(passage)}])
        raw_search = root / "literature/search-negative-or-positive.json"
        write_json(raw_search, {"simulation": True, "queries": queries, "matches": [] if no_sources else [identifier]})
        for search in evidence["searches"]:
            search.update(raw_path=raw_search.relative_to(root).as_posix(), sha256=digest_file(raw_search),
                          resolved_ids=[] if no_sources else [identifier])
        if no_sources:
            evidence["sources"] = []
        if missing_query:
            evidence["searches"][0].update(status="not_attempted", attempted=False)
        evidence.update(flags or {})
        return evidence
    return retrieve


def assert_code(code, operation):
    with pytest.raises(WorkflowError) as failure:
        operation()
    assert failure.value.code == code


def test_followup_preserves_proposal_and_old_decision_then_binds_one_fresh_approval(setup):
    service, runner, research_id, old = initial(setup)
    kept = {key: service.artifact_path(research_id, key).read_bytes() for key in ("proposal", "literature", "study-review-1")}
    assert old["resume_kind"] == "preparation" and old["study_literature_attempt"] == 0
    resumed = service.resume(research_id)
    assert resumed["study_review"]["accepted"] is False and resumed["execution_attempt"] == 0
    service.collector = collector()
    state = service.collect_study_literature(research_id, QUERIES, REASON, [])
    assert state["study_literature_pending"] is True and state["study_literature_attempt"] == 1
    assert state["proposal_attempt"] == 1 and state["execution_attempt"] == 0
    assert state["proposal"]["conditions"] == protocol()["conditions"]
    for key in ("proposal", "study-review-1"):
        assert service.artifact_path(research_id, key).read_bytes() == kept[key]
    history = "literature-history-" + old["artifacts"]["literature"]["sha256"]
    assert service.artifact_path(research_id, history).read_bytes() == kept["literature"]
    intent = json.loads(service.artifact_path(research_id, "study-literature-intent-1").read_bytes())
    assert intent["proposal_sha256"] == old["artifacts"]["proposal"]["sha256"]
    assert intent["prior_study_review_sha256"] == old["artifacts"]["study-review-1"]["sha256"]
    assert_code("STUDY_REVIEW_REQUIRED", lambda: service.collect_study_literature(research_id, QUERIES, REASON, []))
    review = copy.deepcopy(STUDY_REVIEW)
    review["selected_sources"][0]["source_id"] = "new-primary"
    review["publication_readiness"]["closest_work"][0]["source_id"] = "new-primary"
    approved = service.submit_study_review(research_id, review)
    assert approved["stage"] == "planned" and approved["study_literature_pending"] is False
    receipt = json.loads(service.artifact_path(research_id, "study-review-1-literature-1").read_bytes())
    assert receipt["prior_study_review_sha256"] == intent["prior_study_review_sha256"]
    assert receipt["literature_sha256"] == state["artifacts"]["literature"]["sha256"]
    assert receipt["study_literature_collection_sha256"] == state["artifacts"]["study-literature-collection-1"]["sha256"]
    assert receipt["protocol_sha256"] == old["artifacts"]["proposal"]["sha256"]
    assert service.artifact_path(research_id, "study-review-1").read_bytes() == kept["study-review-1"]
    assert runner.calls == 0 and "observations" not in approved["artifacts"]


@pytest.mark.parametrize("no_sources", [True, False])
def test_search_changes_without_new_reading_cannot_seek_another_decision(setup, no_sources):
    service, runner, research_id, old = initial(setup)
    service.collector = collector(identifier="fixture-oracle", extra="", no_sources=no_sources)
    for number in (1, 2):
        state = service.collect_study_literature(research_id, [QUERIES[0] + str(number)], REASON, [])
        assert state["study_literature_attempt"] == number and state["study_literature_pending"] is False
        assert state["artifacts"]["literature"]["sha256"] != old["artifacts"]["literature"]["sha256"]
        assert_code("REVIEW_EVIDENCE_CONFLICT", lambda: service.submit_study_review(research_id, rejected()))
    assert state["resume_kind"] == "preparation"
    assert_code("STUDY_LITERATURE_HINT_REQUIRED", lambda: service.collect_study_literature(research_id, QUERIES, REASON, []))
    assert runner.calls == 0


def test_global_attempt_limit_survives_a_substantively_new_proposal(setup):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector(no_sources=True)
    for number in (1, 2):
        service.collect_study_literature(research_id, [QUERIES[0] + str(number)], REASON, [])
    plan = protocol()
    plan["question"] += " A changed mechanism question is separately preregistered."
    plan["conditions"] += ["different-mechanism"]
    service.submit_proposal(research_id, plan)
    service.collector = collect
    service.collect_literature(research_id)
    state = service.submit_study_review(research_id, rejected())
    assert state["proposal_attempt"] == 2 and state["study_literature_attempt"] == 2
    assert state["resume_kind"] == "preparation"
    assert_code("STUDY_LITERATURE_HINT_REQUIRED", lambda: service.collect_study_literature(research_id, QUERIES, REASON, []))
    assert runner.calls == 0


@pytest.mark.parametrize("flags,missing_query", [({"cancelled": True}, False), ({"timed_out": True}, False),
                                                ({"rate_limited": True}, False), ({}, True)])
def test_partial_collection_preserves_raw_evidence_but_cannot_freeze_protocol(setup, flags, missing_query):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector(flags=flags, missing_query=missing_query)
    state = service.collect_study_literature(research_id, QUERIES, REASON, [])
    assert state["study_literature_pending"] is True
    collection = json.loads(service.artifact_path(research_id, "study-literature-collection-1").read_bytes())
    assert collection["quality_status"] == "incomplete"
    assert collection["searches"][0]["sha256"] in {row["sha256"] for row in state["artifacts"].values()}
    review = copy.deepcopy(STUDY_REVIEW)
    code = "LITERATURE_QUERIES_INCOMPLETE" if missing_query else "LITERATURE_EVIDENCE_INSUFFICIENT"
    assert_code(code, lambda: service.submit_study_review(research_id, review))
    held = service.submit_study_review(research_id, rejected())
    assert held["study_literature_pending"] is False and "plan" not in held["artifacts"]
    assert runner.calls == 0


@pytest.mark.parametrize("queries,reason", [([], REASON), (["short"], REASON), ([QUERIES[0]] * 2, REASON),
                                          ([QUERIES[0], " " + QUERIES[0]], REASON), (["bad\nquery text"], REASON),
                                          (["x" * 501], REASON), (["query%04d" % i for i in range(5)], REASON),
                                          (["bad\x7fquery text"], REASON), (QUERIES, "short"), (QUERIES, "x" * 2001)])
def test_bad_requests_do_not_reserve_or_dispatch_collection(setup, queries, reason):
    service, runner, research_id, old = initial(setup)
    service.collector = lambda *args, **kwargs: pytest.fail("Invalid request dispatched collector")
    assert_code("LITERATURE_QUERIES_INVALID", lambda: service.collect_study_literature(research_id, queries, reason, []))
    assert service.status(research_id)["artifacts"] == old["artifacts"]
    assert service.status(research_id)["study_literature_attempt"] == 0 and runner.calls == 0


def test_multiline_reason_is_retained_without_changing_the_query_contract(setup):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector()
    reason = "  " + REASON + "\nA second paragraph identifies the missing directly read methods.\n"
    state = service.collect_study_literature(research_id, QUERIES, reason, [])
    intent = json.loads(service.artifact_path(research_id, "study-literature-intent-1").read_bytes())
    assert intent["reason"] == reason.strip() and state["study_literature_pending"] is True
    assert runner.calls == 0


def test_attempt_is_durably_reserved_before_external_work(setup):
    service, runner, research_id, _ = initial(setup)
    def failed(*args, **kwargs):
        state = service._workspace(research_id).get("workflow", research_id, Workflow)
        assert state.study_literature_attempt == 1
        assert "study-literature-intent-1" in state.artifacts
        raise OSError("Synthetic interrupted provider boundary")
    service.collector = failed
    with pytest.raises(OSError):
        service.collect_study_literature(research_id, QUERIES, REASON, [])
    assert service.status(research_id)["study_literature_attempt"] == 1 and runner.calls == 0


def test_same_source_new_fulltext_reading_replaces_it_without_scope_downgrade(setup):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector(identifier="fixture-oracle", extra=" Additional primary methods establish a different bounded literal passage.")
    state = service.collect_study_literature(research_id, QUERIES, REASON, [])
    assert len(state["literature"]["sources"]) == 1 and state["study_literature_pending"] is True
    retained_text = state["literature"]["sources"][0]["text_sha256"]
    service.submit_study_review(research_id, rejected())
    def abstract(*args, **kwargs):
        evidence = collector(identifier="fixture-oracle")(*args, **kwargs)
        evidence["sources"][0]["scope"] = "abstract"
        return evidence
    service.collector = abstract
    state = service.collect_study_literature(research_id, QUERIES, REASON, [])
    source, = state["literature"]["sources"]
    assert source["scope"] == "full_text" and source["text_sha256"] == retained_text
    assert state["study_literature_pending"] is False and runner.calls == 0


def test_scope_annotations_without_new_literal_reading_cannot_trigger_review(setup):
    service, runner, research_id, _ = initial(setup)
    def annotations(*args, **kwargs):
        evidence = collector(identifier="fixture-oracle", extra="")(*args, **kwargs)
        source = evidence["sources"][0]
        source.update(reading_scope="A changed descriptive scope has no new literal evidence.", body_range=None)
        source["excerpt_ranges"][0].update(page_start=2, page_end=3)
        return evidence
    service.collector = annotations
    state = service.collect_study_literature(research_id, QUERIES, REASON, [])
    assert state["study_literature_pending"] is False
    assert_code("REVIEW_EVIDENCE_CONFLICT", lambda: service.submit_study_review(research_id, rejected()))
    assert runner.calls == 0


@pytest.mark.parametrize("variant", ["alias", "outside_text", "offset", "normalization", "contained_window"])
def test_provenance_or_equivalent_window_changes_are_not_new_reading(setup, variant):
    service, runner, research_id, _ = initial(setup)
    def equivalent(queries, root, **kwargs):
        evidence = collector(extra="")(queries, root, **kwargs)
        source = evidence["sources"][0]
        path = root / source["text_path"]
        original = path.read_text(encoding="utf-8")
        passage = source["excerpts"][0]
        text = original
        start = source["excerpt_ranges"][0]["start"]
        if variant == "outside_text":
            text += "\nA changed footer outside the inspected methods paragraph."
        elif variant == "offset":
            text = "Extra page header.\n" + original
            start += len("Extra page header.\n")
        elif variant == "normalization":
            replacement = passage.replace("SYNTHETIC", "ＳＹＮＴＨＥＴＩＣ").replace(" ", "  ")
            text = original.replace(passage, replacement)
            passage = replacement
        elif variant == "contained_window":
            passage = passage[10:110]
            start += 10
        path.write_bytes(text.encode())
        source.update(excerpts=[passage], text_sha256=digest_file(path), body_range=literature.full_text_body_range(text),
                      excerpt_ranges=[{"start": start, "end": start + len(passage)}])
        return evidence
    service.collector = equivalent
    state = service.collect_study_literature(research_id, QUERIES, REASON, [])
    assert state["study_literature_pending"] is False
    assert_code("REVIEW_EVIDENCE_CONFLICT", lambda: service.submit_study_review(research_id, rejected()))
    assert runner.calls == 0


def test_six_source_packet_prioritizes_new_fulltext_and_retains_evicted_metadata(setup):
    service, runner, research_id = setup
    service.submit_proposal(research_id, protocol())
    def initial_six(*args, **kwargs):
        evidence = collect(*args, **kwargs)
        primary = evidence["sources"][0]
        evidence["sources"] += [{"id": "old-metadata-" + str(number), "scope": "metadata_only",
                                 "title": "Synthetic contextual bibliographic metadata", "excerpts": []}
                                for number in range(5)]
        assert primary["scope"] == "full_text"
        return evidence
    service.collector = initial_six
    old = service.collect_literature(research_id)
    original = service.artifact_path(research_id, "literature").read_bytes()
    service.submit_study_review(research_id, rejected())
    def fresh_three(*args, **kwargs):
        evidence = collector()(*args, **kwargs)
        source = evidence["sources"][0]
        evidence["sources"] = [dict(source, id="new-primary-" + str(number)) for number in range(3)]
        return evidence
    service.collector = fresh_three
    state = service.collect_study_literature(research_id, QUERIES, REASON, [])
    sources = state["literature"]["sources"]
    assert len(sources) == 6
    assert {source["id"] for source in sources[:4]} == {"fixture-oracle", "new-primary-0", "new-primary-1", "new-primary-2"}
    history = "literature-history-" + old["artifacts"]["literature"]["sha256"]
    assert service.artifact_path(research_id, history).read_bytes() == original
    assert len(json.loads(original)["sources"]) == 6
    assert state["study_literature_pending"] is True and runner.calls == 0


@pytest.mark.parametrize("key", ["study-review-1", "study-literature-intent-1", "study-literature-collection-1"])
def test_tampered_frozen_provenance_cannot_receive_another_decision(setup, key):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector()
    service.collect_study_literature(research_id, QUERIES, REASON, [])
    path = service.artifact_path(research_id, key)
    path.write_bytes(path.read_bytes() + b" ")
    assert_code("ARTIFACT_CHANGED", lambda: service.submit_study_review(research_id, rejected()))
    assert runner.calls == 0


@pytest.mark.parametrize("retrieval", ["generic", "public_listing"])
def test_ipc_declares_exact_api_fields_and_dispatches_native_method(setup, monkeypatch, retrieval):
    service, _, research_id, _ = initial(setup)
    service.collector = collector() if retrieval == "generic" else hinted_collector(monkeypatch)
    params = {"researchId": research_id, "queries": QUERIES if retrieval == "generic" else [PDF_HINT["doi"]],
              "reason": REASON, "pdfCandidates": [] if retrieval == "generic" else [PDF_HINT]}
    request = ipc.request(json.dumps({"id": "literature-request", "method": "workflow.collectStudyLiterature", "params": params}).encode())
    runtime = object.__new__(ipc.Dispatcher)
    runtime.service = service
    result = runtime.execute(request["method"], request["params"])
    assert result["study_literature_pending"] is True
    if retrieval == "public_listing":
        obsolete = {**params, "pdfCandidates": [{**PDF_HINT, "url": PDF_URL}]}
        bad = ipc.request(json.dumps({"id": "obsolete-url", "method": request["method"], "params": obsolete}).encode())
        assert_code("LITERATURE_QUERIES_INVALID", lambda: runtime.execute(bad["method"], bad["params"]))
        assert service.status(research_id)["study_literature_attempt"] == 1
    for bad in ({**params, "untrustedPath": "elsewhere"}, {"researchId": research_id, "queries": QUERIES},
                {key: value for key, value in params.items() if key != "pdfCandidates"}):
        with pytest.raises(ValueError):
            ipc.request(json.dumps({"id": "bad", "method": "workflow.collectStudyLiterature", "params": bad}).encode())


@pytest.mark.parametrize("criterion", ["question", "comparison", "sampling", "feasibility", "validation"])
def test_design_or_validation_failures_require_revision_not_evidence_only_resume(setup, criterion):
    service, runner, research_id = setup
    service.submit_proposal(research_id, protocol())
    service.collect_literature(research_id)
    review = rejected()
    if criterion == "validation":
        review["publication_readiness"][criterion]["passed"] = False
    else:
        review[criterion]["passed"] = False
    state = service.submit_study_review(research_id, review)
    assert state["resume_kind"] is None
    assert_code("STUDY_LITERATURE_INELIGIBLE", lambda: service.collect_study_literature(research_id, QUERIES, REASON, []))
    assert_code("INVALID_STATE", lambda: service.resume(research_id))
    assert state["study_literature_attempt"] == 0 and runner.calls == 0


@pytest.mark.parametrize("defect,code", [("executed", "EXPERIMENT_ALREADY_DISPATCHED"),
                                        ("cleanup", "CLEANUP_UNCONFIRMED"), ("control", "CONTROL_FAILED")])
def test_execution_cleanup_and_terminal_guards_prevent_evidence_changes(setup, defect, code):
    service, runner, research_id, _ = initial(setup)
    ws = service._workspace(research_id)
    record = ws.get("workflow", research_id, Workflow)
    if defect == "executed":
        record.execution_attempt = 1
    elif defect == "cleanup":
        record.active_handle = {"synthetic_pid": 1}
    else:
        record.terminal_control_failure = True
    ws.save("workflow", record)
    assert_code(code, lambda: service.collect_study_literature(research_id, QUERIES, REASON, []))
    assert service.status(research_id)["resume_kind"] is None
    assert runner.calls == 0


def test_second_attempt_new_reading_can_resume_once_but_repeated_review_is_forbidden(setup):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector(no_sources=True)
    service.collect_study_literature(research_id, QUERIES, REASON, [])
    service.collector = collector()
    state = service.collect_study_literature(research_id, QUERIES, REASON, [])
    assert state["study_literature_attempt"] == 2 and state["study_literature_pending"] is True
    assert state["resume_kind"] == "preparation"
    service.resume(research_id)
    held = service.submit_study_review(research_id, rejected())
    assert held["study_literature_pending"] is False and held["resume_kind"] == "preparation"
    assert_code("REVIEW_EVIDENCE_CONFLICT", lambda: service.submit_study_review(research_id, rejected()))
    assert runner.calls == 0


def test_original_collector_cannot_bypass_targeted_budget_after_partial_followup(setup):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector(flags={"timed_out": True})
    service.collect_study_literature(research_id, QUERIES, REASON, [])
    assert_code("STUDY_LITERATURE_REQUIRED", lambda: service.collect_literature(research_id))
    state = service.status(research_id)
    assert state["study_literature_attempt"] == 1 and state["study_literature_pending"] is True
    assert runner.calls == 0


def test_newly_received_reading_must_be_reviewed_before_replacing_proposal(setup):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector()
    service.collect_study_literature(research_id, QUERIES, REASON, [])
    service.resume(research_id)
    plan = protocol()
    plan["question"] += " A different controlled question would require a new preregistration."
    assert_code("STUDY_REVIEW_REQUIRED", lambda: service.submit_proposal(research_id, plan))
    assert service.status(research_id)["proposal_attempt"] == 1 and runner.calls == 0


def test_resumed_rejected_proposal_can_be_substantively_revised_before_supplement(setup):
    service, runner, research_id, _ = initial(setup)
    opened = service.resume(research_id)
    assert opened["code"] is None and opened["status"] == "ready"
    plan = protocol()
    plan["question"] += " A substantively revised mechanism question uses its separate remaining proposal budget."
    plan["conditions"] += ["different-mechanism"]
    state = service.submit_proposal(research_id, plan)
    assert state["proposal_attempt"] == 2 and state["study_literature_attempt"] == 0
    assert "study-review-1" in state["artifacts"] and "study-review" not in state["artifacts"]
    assert runner.calls == 0


def test_original_text_hash_tamper_cannot_support_fresh_approval(setup):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector()
    state = service.collect_study_literature(research_id, QUERIES, REASON, [])
    source = next(source for source in state["literature"]["sources"] if source["id"] == "new-primary")
    ws = service._workspace(research_id)
    path = ws.path("research") / source["text_path"]
    path.write_bytes(path.read_bytes() + b"Changed methods.")
    assert_code("ARTIFACT_CHANGED", lambda: service.submit_study_review(research_id, copy.deepcopy(STUDY_REVIEW)))
    assert runner.calls == 0


@pytest.mark.parametrize("retrieval", ["generic", "public_listing"])
def test_reproduction_archive_preserves_original_review_supplement_and_raw_bytes_without_dispatch(setup, monkeypatch, retrieval):
    service, runner, research_id, old = initial(setup)
    original_review = service.artifact_path(research_id, "study-review-1").read_bytes()
    original_literature = service.artifact_path(research_id, "literature").read_bytes()
    excluded = {}
    def retrieve(queries, root, **kwargs):
        excluded.update(root=root, files=excluded_raw(root))
        selected = collector() if retrieval == "generic" else hinted_collector(monkeypatch)
        return selected(queries, root, **kwargs)
    service.collector = retrieve
    state = service.collect_study_literature(research_id, QUERIES if retrieval == "generic" else [PDF_HINT["doi"]],
                                             REASON, [] if retrieval == "generic" else [PDF_HINT])
    source = next(source for source in state["literature"]["sources"] if (
        source["id"] == "new-primary" if retrieval == "generic" else source.get("copy_type") == "author_copy"))
    review = copy.deepcopy(STUDY_REVIEW)
    if retrieval == "public_listing":
        review["selected_sources"][0].update(source_id=source["id"], excerpt_index=0)
        review["publication_readiness"]["closest_work"][0].update(source_id=source["id"], excerpt_index=0, quote=source["excerpts"][0][:200])
    service.submit_study_review(research_id, review)
    service.submit_code(research_id, copy.deepcopy(BUNDLE), REVIEW)
    ws = service._workspace(research_id)
    record = ws.get("workflow", research_id, Workflow)
    raw = observations()
    plan = json.loads(service.artifact_path(research_id, "plan").read_bytes())
    execution = {"status": "succeeded", "cleanup_confirmed": True, "coverage_truncated": False,
                 "coverage_mechanism": "synthetic prior execution fixture",
                 "production_calls": [{"path": "transform.js", "function": "transform", "calls": 6}]}
    for key, value in (("execution", execution), ("observations", raw)):
        path = ws.path("research/" + key + "-synthetic.json")
        write_json(path, value)
        record.artifacts[key] = FrozenArtifact(path=path.relative_to(ws.root).as_posix(), sha256=digest_file(path), size=path.stat().st_size)
    analysis = science._compute(raw, plan)
    analysis.update(raw_sha256=record.artifacts["observations"].sha256, protocol_sha256=record.artifacts["plan"].sha256)
    path = ws.path("research/analysis-synthetic.json")
    write_json(path, analysis)
    record.artifacts["analysis"] = FrozenArtifact(path=path.relative_to(ws.root).as_posix(), sha256=digest_file(path), size=path.stat().st_size)
    record.execution_attempt, record.stage = 1, "analyzed"
    ws.save("workflow", record)
    draft, manuscript_review = manuscript(), copy.deepcopy(MANUSCRIPT_REVIEW)
    if retrieval == "public_listing":
        for section in draft["sections"]:
            section["text"] = section["text"].replace("{{citation:fixture-oracle}}", "{{citation:" + source["id"] + "}}")
        manuscript_review["publication_readiness"]["closest_work"][0].update(
            source_id=source["id"], excerpt_index=0, quote=source["excerpts"][0][:200])
    service.submit_manuscript(research_id, draft, manuscript_review)
    record = ws.get("workflow", research_id, Workflow)
    root = ws.path("research/export-synthetic")
    root.mkdir()
    for key, name in (("export-md", "paper.md"), ("export-pdf", "paper.pdf"), ("export-docx", "paper.docx"),
                      ("export-tex", "paper.tex"), ("conversion", "conversion-receipts.json")):
        path = root / name
        path.write_bytes(b"Synthetic document serialization fixture, not a generated paper.")
        record.artifacts[key] = FrozenArtifact(path=path.relative_to(ws.root).as_posix(), sha256=digest_file(path), size=path.stat().st_size)
    service._bundle(ws, record, root)
    with zipfile.ZipFile(ws.path(record.artifacts["reproducibility"].path)) as archive:
        assert archive.read("research-design/study-review-1.json") == original_review
        assert archive.read("literature/history/" + old["artifacts"]["literature"]["sha256"] + ".json") == original_literature
        for key in ("study-literature-intent-1", "study-literature-collection-1", "study-review-1-literature-1"):
            assert archive.read("research-design/literature/" + key + ".json") == service.artifact_path(research_id, key).read_bytes()
        for field, digest in (("raw_path", "sha256"), ("metadata_path", "metadata_sha256"), ("text_path", "text_sha256"),
                              ("discovery_path", "discovery_sha256"), ("identity_path", "identity_sha256")):
            if field not in source:
                continue
            assert hashlib.sha256(archive.read(source[field])).hexdigest() == source[digest]
        if retrieval == "public_listing":
            collection = json.loads(service.artifact_path(research_id, "study-literature-collection-1").read_bytes())
            assert collection["pdf_listing"]["raw_path"] == source["discovery_path"]
            assert hashlib.sha256(archive.read(collection["pdf_listing"]["raw_path"])).hexdigest() == collection["pdf_listing"]["sha256"]
        for relative, raw in excluded["files"].items():
            member = (excluded["root"] / relative).relative_to(ws.path("research")).as_posix()
            assert archive.read(member) == raw
        assert archive.testzip() is None
    assert runner.calls == 0


@pytest.mark.parametrize("variant", ["abstract", "unknown_body", "wrong_body", "abstract_range", "references_range", "wrong_literal", "invalid_range"])
def test_only_verified_full_body_passages_open_another_review(setup, variant):
    service, runner, research_id, old = initial(setup)
    original_review = service.artifact_path(research_id, "study-review-1").read_bytes()
    def contextual(queries, root, **kwargs):
        evidence = collector()(queries, root, **kwargs)
        source = evidence["sources"][0]
        path = root / source["text_path"]
        text = path.read_text(encoding="utf-8")
        if variant == "abstract":
            source["scope"] = "abstract"
        elif variant == "unknown_body":
            text = text.replace("Introduction", "Unrecognized initial heading")
        elif variant == "wrong_body":
            source["body_range"] = {"start": 0, "end": len(text)}
        elif variant in {"abstract_range", "references_range"}:
            passage = "A new contextual paragraph is not retained methods evidence for this synthetic study. " * 2
            text = SYNTHETIC_PREFIX + source["excerpts"][0] + SYNTHETIC_SUFFIX
            text = (passage + "\n" + text) if variant == "abstract_range" else text + "\n" + passage
            start = text.index(passage)
            source.update(excerpts=[passage], excerpt_ranges=[{"start": start, "end": start + len(passage)}])
        elif variant == "wrong_literal":
            source["excerpts"][0] += " A fabricated statement absent from retained text."
        else:
            source["excerpt_ranges"] = [None]
        path.write_bytes(text.encode())
        source["text_sha256"] = digest_file(path)
        if variant not in {"wrong_body", "invalid_range"}:
            source["body_range"] = literature.full_text_body_range(text)
        return evidence
    service.collector = contextual
    state = service.collect_study_literature(research_id, QUERIES, REASON, [])
    assert state["study_literature_pending"] is False and state["execution_attempt"] == 0
    assert_code("REVIEW_EVIDENCE_CONFLICT", lambda: service.submit_study_review(research_id, rejected()))
    assert service.artifact_path(research_id, "study-review-1").read_bytes() == original_review
    assert state["artifacts"]["proposal"] == old["artifacts"]["proposal"] and runner.calls == 0


def excluded_raw(root):
    folder = root / "literature"
    folder.mkdir(exist_ok=True)
    values = {"excluded-metadata.json": b'{"simulation":true,"excluded":true}',
              "excluded-discovery.xml": b"<feed><entry>Synthetic excluded identity</entry></feed>",
              "excluded-original.pdf": b"%PDF-Synthetic complete excluded author copy",
              "excluded-response.bin": b"Synthetic refused MIME response\x00\x01",
              "excluded-text.txt": b"Synthetic complete text of a rejected identity.",
              "excluded-proof.json": b'{"simulation":true,"status":"rejected"}'}
    for name, raw in values.items():
        (folder / name).write_bytes(raw)
    return {path.relative_to(root).as_posix(): raw for path, raw in ((folder / name, raw) for name, raw in values.items())}


@pytest.mark.parametrize("phase", ["initial", "study", "authoring"])
@pytest.mark.parametrize("outcome", ["complete", "negative", "partial", "failure"])
def test_completed_excluded_raw_files_are_frozen_in_every_new_collection(setup, phase, outcome):
    service, runner, research_id = setup
    if phase == "study":
        initial(setup)
    elif phase == "authoring":
        retained_authoring_fixture(service, research_id)
    else:
        service.submit_proposal(research_id, protocol())
    before = service.status(research_id)["artifacts"]
    kept = {}
    def retrieve(queries, root, **kwargs):
        kept.update(root=root, files=excluded_raw(root))
        if outcome == "failure":
            raise OSError("Synthetic completed response followed by failed provider")
        kwargs.pop("pdf_candidates", None)
        evidence = collect(queries, root, **kwargs)
        if outcome == "negative":
            evidence["sources"] = []
        elif outcome == "partial":
            evidence["timed_out"] = True
        return evidence
    service.collector = retrieve
    operation = (lambda: service.collect_literature(research_id)) if phase == "initial" else (
        (lambda: service.collect_study_literature(research_id, QUERIES, REASON, [])) if phase == "study" else
        (lambda: service.collect_authoring_literature(research_id, QUERIES)))
    if outcome == "failure":
        with pytest.raises(OSError):
            operation()
    elif phase == "initial" and outcome in {"negative", "partial"}:
        with pytest.raises(WorkflowError):
            operation()
    else:
        operation()
    state = service.status(research_id)
    ws = service._workspace(research_id)
    record = ws.get("workflow", research_id, Workflow)
    for relative, raw in kept["files"].items():
        path = kept["root"] / relative
        matches = [key for key, frozen in record.artifacts.items() if frozen.path == path.relative_to(ws.root).as_posix()]
        assert len(matches) == 1 and all(key.startswith("literature-") for key in matches)
        assert all(service.artifact_path(research_id, key).read_bytes() == raw for key in matches)
        assert all(state["artifacts"][key]["sha256"] == hashlib.sha256(raw).hexdigest() for key in matches)
    for key, frozen in before.items():
        if key not in {"literature"}:
            assert state["artifacts"][key] == frozen
    for name in ("literature", "authoring_literature"):
        for source in (state.get(name) or {}).get("sources", []):
            for field, digest in (("raw_path", "sha256"), ("metadata_path", "metadata_sha256"), ("text_path", "text_sha256")):
                if source.get(field):
                    relative = "research/" + source[field]
                    bindings = [artifact for artifact in record.artifacts.values() if artifact.path == relative]
                    assert len(bindings) == 1 and bindings[0].sha256 == source[digest]
    assert runner.calls == 0


def test_new_collection_does_not_implicitly_adopt_legacy_orphan_files(setup):
    service, runner, research_id = setup
    service.submit_proposal(research_id, protocol())
    ws = service._workspace(research_id)
    path = ws.path("research/literature/legacy-untracked.xml")
    path.parent.mkdir(exist_ok=True)
    raw = b"Existing untracked legacy raw bytes; no new retrieval is attested."
    path.write_bytes(raw)
    service.collect_literature(research_id)
    assert path.read_bytes() == raw
    assert not any(artifact.path == path.relative_to(ws.root).as_posix() for artifact in ws.get("workflow", research_id, Workflow).artifacts.values())
    assert runner.calls == 0


def test_collection_refuses_hardlinked_raw_without_adopting_external_bytes(setup, tmp_path):
    service, runner, research_id, _ = initial(setup)
    external = tmp_path / "external-owned-test.txt"
    external.write_bytes(b"External bytes may not be adopted as a retrieved artifact.")
    def linked(queries, root, **kwargs):
        folder = root / "literature"
        folder.mkdir()
        os.link(external, folder / "linked.txt")
        return {"sources": [], "searches": []}
    service.collector = linked
    with pytest.raises(ValueError, match="unlinked"):
        service.collect_study_literature(research_id, QUERIES, REASON, [])
    assert external.read_bytes() == b"External bytes may not be adopted as a retrieved artifact."
    assert service.status(research_id)["study_literature_attempt"] == 1 and runner.calls == 0


def two_negative_attempts(setup):
    service, runner, research_id, old = initial(setup)
    service.collector = collector(no_sources=True)
    for _ in range(2):
        service.collect_study_literature(research_id, QUERIES, REASON, [])
    return service, runner, research_id, old


def hinted_collector(monkeypatch, *, text=None, mutate=None, content_type="application/pdf", handler=None):
    from test_public_pdf_hints import TEXT, collect_hint
    def retrieve(queries, root, *, limit, cancel, pdf_candidates):
        assert queries == [PDF_HINT["doi"]] and pdf_candidates == [PDF_HINT] and limit == 3
        evidence, _ = collect_hint(monkeypatch, root, text=TEXT if text is None else text,
                                  content_type=content_type, handler=handler)
        evidence["searches"][0]["query"] = queries[0]
        if mutate is not None:
            mutate(evidence, root)
        return evidence
    return retrieve


@pytest.mark.parametrize("candidates", [None, {}, [PDF_HINT] * 3, [{**PDF_HINT, "extra": True}],
                                     [{**PDF_HINT, "url": PDF_URL}],
                                     [{**PDF_HINT, "doi": "10.1234/unrequested"}]])
def test_invalid_pdf_hints_are_rejected_before_reservation_or_network(setup, candidates):
    service, runner, research_id, old = initial(setup)
    service.collector = lambda *args, **kwargs: pytest.fail("Invalid PDF hint dispatched collector")
    assert_code("LITERATURE_QUERIES_INVALID", lambda: service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, candidates))
    state = service.status(research_id)
    assert state["study_literature_attempt"] == 0 and state["artifacts"] == old["artifacts"] and runner.calls == 0


@pytest.mark.parametrize("queries,candidates", [(QUERIES, []), ([PDF_HINT["doi"], QUERIES[0]], [PDF_HINT]),
                                              ([PDF_HINT["doi"], "10.1234/unhinted"], [PDF_HINT])])
def test_final_attempt_cannot_become_another_generic_search(setup, queries, candidates):
    service, runner, research_id, _ = two_negative_attempts(setup)
    service.collector = lambda *args, **kwargs: pytest.fail("Invalid final request dispatched collector")
    assert_code("STUDY_LITERATURE_HINT_REQUIRED", lambda: service.collect_study_literature(research_id, queries, REASON, candidates))
    assert service.status(research_id)["study_literature_attempt"] == 2 and runner.calls == 0


def test_final_verified_primary_body_is_bound_to_intent_and_one_fresh_decision(setup, monkeypatch):
    service, runner, research_id, old = two_negative_attempts(setup)
    original = service.artifact_path(research_id, "study-review-1").read_bytes()
    collect_pdf = hinted_collector(monkeypatch)
    def reserved(queries, root, **kwargs):
        ws = service._workspace(research_id)
        record = ws.get("workflow", research_id, Workflow)
        intent = json.loads(ws.path(record.artifacts["study-literature-intent-3"].path).read_bytes())
        assert intent["pdf_candidates"] == [PDF_HINT]
        assert record.study_literature_attempt == 3
        return collect_pdf(queries, root, **kwargs)
    service.collector = reserved
    state = service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, [PDF_HINT])
    assert state["study_literature_attempt"] == 3 and state["study_literature_pending"] is True
    source = next(source for source in state["literature"]["sources"] if source.get("copy_type") == "author_copy")
    ws = service._workspace(research_id)
    proof = json.loads((ws.path("research") / source["identity_path"]).read_bytes())
    assert proof["candidate"] == PDF_HINT and proof["metadata_path"].startswith("literature/")
    assert "url" not in proof["candidate"]
    assert proof["discovery"]["listing_url"] == literature.AUTHOR_PUBLICATIONS
    assert source["discovery_path"].startswith("study-literature/attempt-3/literature/")
    assert hashlib.sha256((ws.path("research") / source["discovery_path"]).read_bytes()).hexdigest() == proof["discovery"]["sha256"]
    assert source["identity_path"].startswith("study-literature/attempt-3/literature/")
    collection = json.loads(service.artifact_path(research_id, "study-literature-collection-3").read_bytes())
    assert collection["pdf_hint_attempts"][0]["identity_path"] == source["identity_path"]
    assert collection["pdf_hint_attempts"][0]["discovery"]["raw_path"] == source["discovery_path"]
    assert collection["pdf_listing"]["raw_path"] == source["discovery_path"]
    record = ws.get("workflow", research_id, Workflow)
    for field, digest in (("discovery_path", "discovery_sha256"), ("identity_path", "identity_sha256")):
        matches = [artifact for artifact in record.artifacts.values() if artifact.path == "research/" + source[field]]
        assert len(matches) == 1 and matches[0].sha256 == source[digest]
    review = copy.deepcopy(STUDY_REVIEW)
    review["selected_sources"][0].update(source_id=source["id"], excerpt_index=0)
    review["publication_readiness"]["closest_work"][0].update(source_id=source["id"], excerpt_index=0, quote=source["excerpts"][0][:200])
    service.resume(research_id)
    accepted = service.submit_study_review(research_id, review)
    assert accepted["stage"] == "planned" and accepted["execution_attempt"] == 0
    receipt = json.loads(service.artifact_path(research_id, "study-review-1-literature-3").read_bytes())
    assert receipt["proposal_sha256"] == old["artifacts"]["proposal"]["sha256"]
    assert receipt["study_literature_collection_sha256"] == state["artifacts"]["study-literature-collection-3"]["sha256"]
    assert service.artifact_path(research_id, "study-review-1").read_bytes() == original and runner.calls == 0


@pytest.mark.parametrize("outcome", ["negative", "cancelled", "failure"])
def test_reserved_final_attempt_is_consumed_even_without_a_verified_new_body(setup, outcome):
    service, runner, research_id, _ = two_negative_attempts(setup)
    def retrieve(queries, root, **kwargs):
        excluded_raw(root)
        if outcome == "failure":
            raise OSError("Synthetic direct PDF interrupted after completed raw")
        return {"sources": [], "searches": [{"query": queries[0], "status": "failed", "attempted": True}],
                "cancelled": outcome == "cancelled"}
    service.collector = retrieve
    operation = lambda: service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, [PDF_HINT])
    if outcome == "failure":
        with pytest.raises(OSError):
            operation()
    else:
        operation()
    state = service.status(research_id)
    assert state["study_literature_attempt"] == 3 and state["study_literature_pending"] is False and state["resume_kind"] is None
    assert_code("STUDY_LITERATURE_LIMIT", operation)
    assert_code("REVIEW_EVIDENCE_CONFLICT", lambda: service.submit_study_review(research_id, rejected()))
    assert_code("INVALID_STATE", lambda: service.resume(research_id))
    assert runner.calls == 0


@pytest.mark.parametrize("variant", ["unverified", "candidate", "identity", "metadata", "pdf", "text", "path"])
def test_final_body_cannot_be_promoted_by_flags_or_forged_proof(setup, monkeypatch, variant):
    service, runner, research_id, _ = two_negative_attempts(setup)
    def forged(evidence, root):
        source = evidence["sources"][0]
        proof_path = root / source["identity_path"]
        proof = json.loads(proof_path.read_bytes())
        if variant == "unverified":
            source.pop("copy_type")
        elif variant == "candidate":
            proof["candidate"]["title"] += " with different methods"
        elif variant == "identity":
            proof["identity"]["title_range"]["end"] -= 1
        elif variant == "path":
            proof["text_path"] = "literature/does-not-match.txt"
        else:
            field, digest = {"metadata": ("metadata_path", "metadata_sha256"), "pdf": ("raw_path", "sha256"), "text": ("text_path", "text_sha256")}[variant]
            path = root / source[field]
            if variant == "metadata":
                value = json.loads(path.read_bytes())
                value["message"]["author"][0]["given"] = "Another"
                write_json(path, value)
            else:
                path.write_bytes(path.read_bytes() + b"\nModified synthetic retained bytes.")
            source[digest] = digest_file(path)
        write_json(proof_path, proof)
        source["identity_sha256"] = digest_file(proof_path)
        # Attempts describe their own saved original response, independently of
        # this intentionally forged source. Avoid overwriting their frozen bytes.
        evidence.pop("pdf_hint_attempts")
    service.collector = hinted_collector(monkeypatch, mutate=forged)
    with pytest.raises((WorkflowError, FileNotFoundError)):
        service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, [PDF_HINT])
    state = service.status(research_id)
    assert state["study_literature_attempt"] == 3 and state["study_literature_pending"] is False
    assert "plan" not in state["artifacts"] and state["execution_attempt"] == 0 and runner.calls == 0


@pytest.mark.parametrize("variant", ["listing_bytes", "listing_status", "listing_origin", "discovery_title", "discovery_href",
                                     "redirect_location", "redirect_status", "redirect_next", "redirect_raw", "missing_redirect"])
def test_native_reparses_listing_and_recomputes_actual_server_redirects(setup, monkeypatch, variant):
    from test_public_pdf_hints import PDF
    service, runner, research_id, old = two_negative_attempts(setup)
    redirected = PDF_URL.replace("/~NatProg/", "/~natprog/").replace("verified-author", "server-declared-copy")
    literal_location = redirected.replace("https://", "http://", 1)
    def respond(request):
        if str(request.url) == PDF_URL:
            return httpx.Response(302, content=b"Literal synthetic server redirect response", headers={"location": literal_location})
        assert str(request.url) == redirected and request.url.scheme == "https"
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    def forged(evidence, root):
        source = evidence["sources"][0]
        path = root / source["identity_path"]
        proof = json.loads(path.read_bytes())
        discovery = proof["discovery"]
        if variant == "listing_bytes":
            listing = root / source["discovery_path"]
            listing.write_bytes(listing.read_bytes().replace(PDF_HINT["title"].encode(), b"A different complete title"))
            discovery["sha256"] = source["discovery_sha256"] = digest_file(listing)
            evidence["pdf_listing"]["sha256"] = discovery["sha256"]
        elif variant == "listing_status":
            discovery["http_status"] = 206
        elif variant == "listing_origin":
            discovery["retrieved_url"] = "https://elsewhere.test/publications.html"
        elif variant == "discovery_title":
            discovery["quoted_title"] += " with a different subtitle"
        elif variant == "discovery_href":
            discovery["literal_href"] = discovery["url"] = redirected
        elif variant == "redirect_location":
            proof["redirects"][0]["location"] = "http://elsewhere.test/server-declared-copy.pdf"
        elif variant == "redirect_status":
            proof["redirects"][0]["status"] = 200
        elif variant == "redirect_next":
            proof["redirects"][0]["next_url"] = PDF_URL
        elif variant == "redirect_raw":
            proof["redirects"][0]["sha256"] = "0" * 64
        else:
            proof["redirects"] = []
        # Mutate retrieved raw bytes directly; atomic workflow JSON publication
        # is not the behavior exercised by this forged collector response.
        path.write_bytes(json.dumps(proof, ensure_ascii=False).encode("utf-8"))
        source["identity_sha256"] = digest_file(path)
        # The collector packet and saved proof are deliberately inconsistent.
        # Keep only the forged source to isolate native discovery verification.
        evidence.pop("pdf_hint_attempts")
    service.collector = hinted_collector(monkeypatch, mutate=forged, handler=respond)
    assert_code("PUBLICATION_EVIDENCE_INVALID", lambda: service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, [PDF_HINT]))
    state = service.status(research_id)
    assert state["study_literature_attempt"] == 3 and state["study_literature_pending"] is False
    assert state["artifacts"]["proposal"] == old["artifacts"]["proposal"] and "plan" not in state["artifacts"]
    assert state["execution_attempt"] == 0 and runner.calls == 0


def test_identical_verified_primary_body_cannot_buy_another_final_decision(setup, monkeypatch):
    service, runner, research_id, _ = initial(setup)
    service.collector = hinted_collector(monkeypatch)
    state = service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, [PDF_HINT])
    assert state["study_literature_pending"] is True
    service.submit_study_review(research_id, rejected())
    service.collector = collector(no_sources=True)
    service.collect_study_literature(research_id, QUERIES, REASON, [])
    service.collector = hinted_collector(monkeypatch)
    state = service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, [PDF_HINT])
    assert state["study_literature_attempt"] == 3 and state["study_literature_pending"] is False and state["resume_kind"] is None
    assert_code("REVIEW_EVIDENCE_CONFLICT", lambda: service.submit_study_review(research_id, rejected()))
    assert_code("STUDY_LITERATURE_LIMIT", lambda: service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, [PDF_HINT]))
    assert runner.calls == 0


def test_final_failed_identity_preserves_original_pdf_text_and_proof_without_review(setup, monkeypatch):
    from test_public_pdf_hints import TEXT
    service, runner, research_id, _ = two_negative_attempts(setup)
    service.collector = hinted_collector(monkeypatch, text=TEXT.replace("Ada Lovelace", "Unrelated author", 1))
    state = service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, [PDF_HINT])
    assert state["study_literature_pending"] is False and state["resume_kind"] is None
    collection = json.loads(service.artifact_path(research_id, "study-literature-collection-3").read_bytes())
    attempt, = collection["pdf_hint_attempts"]
    assert attempt["status"] == "rejected"
    ws = service._workspace(research_id)
    record = ws.get("workflow", research_id, Workflow)
    for field, digest in (("raw_path", "sha256"), ("text_path", "text_sha256"), ("identity_path", "identity_sha256")):
        path = ws.path("research") / attempt[field]
        assert path.is_file() and digest_file(path) == attempt[digest]
        assert any(artifact.path == path.relative_to(ws.root).as_posix() and artifact.sha256 == attempt[digest]
                   for artifact in record.artifacts.values())
    assert all(source["scope"] != "full_text" for source in collection["sources"])
    assert_code("REVIEW_EVIDENCE_CONFLICT", lambda: service.submit_study_review(research_id, rejected()))
    assert runner.calls == 0


@pytest.mark.parametrize("listing_status", [403, 206])
def test_complete_failed_listing_is_preserved_and_consumes_final_attempt_without_review(setup, monkeypatch, listing_status):
    from test_public_pdf_hints import LISTING, collect_hint
    service, runner, research_id, _ = two_negative_attempts(setup)
    def retrieve(queries, root, **kwargs):
        result, _ = collect_hint(monkeypatch, root, listing_status=listing_status)
        result["searches"][0]["query"] = queries[0]
        return result
    service.collector = retrieve
    state = service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, [PDF_HINT])
    assert state["study_literature_attempt"] == 3 and state["study_literature_pending"] is False and state["resume_kind"] is None
    collection = json.loads(service.artifact_path(research_id, "study-literature-collection-3").read_bytes())
    listing = collection["pdf_listing"]
    assert listing["http_status"] == listing_status and listing["status"] == "rejected"
    ws = service._workspace(research_id)
    raw_path = ws.path("research") / listing["raw_path"]
    assert raw_path.read_bytes() == LISTING and digest_file(raw_path) == listing["sha256"]
    matches = [artifact for artifact in ws.get("workflow", research_id, Workflow).artifacts.values()
               if artifact.path == raw_path.relative_to(ws.root).as_posix()]
    assert len(matches) == 1 and matches[0].sha256 == listing["sha256"]
    assert_code("REVIEW_EVIDENCE_CONFLICT", lambda: service.submit_study_review(research_id, rejected()))
    assert_code("STUDY_LITERATURE_LIMIT", lambda: service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, [PDF_HINT]))
    assert runner.calls == 0


@pytest.mark.parametrize("variant", ["octet_stream", "same_origin_redirect", "server_http_alias"])
def test_final_hint_accepts_supported_collector_transport_with_exact_identity(setup, monkeypatch, variant):
    from test_public_pdf_hints import PDF
    service, runner, research_id, _ = two_negative_attempts(setup)
    redirected = PDF_URL.replace("verified-author", "verified-mirror")
    if variant == "server_http_alias":
        redirected = redirected.replace("/~NatProg/", "/~natprog/")
    def respond(request):
        if str(request.url) == PDF_URL:
            location = redirected.replace("https://", "http://", 1) if variant == "server_http_alias" else redirected
            return httpx.Response(302, content=b"Actual synthetic redirect body", headers={"location": location})
        assert str(request.url) == redirected
        assert request.url.scheme == "https"
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    service.collector = hinted_collector(monkeypatch,
        content_type="application/octet-stream" if variant == "octet_stream" else "application/pdf",
        handler=respond if variant != "octet_stream" else None)
    state = service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, [PDF_HINT])
    source = next(source for source in state["literature"]["sources"] if source.get("copy_type") == "author_copy")
    proof = json.loads((service._workspace(research_id).path("research") / source["identity_path"]).read_bytes())
    assert proof["candidate"] == PDF_HINT
    assert source["url"] == (redirected if variant != "octet_stream" else PDF_URL)
    if variant != "octet_stream":
        collection = json.loads(service.artifact_path(research_id, "study-literature-collection-3").read_bytes())
        public_transition, = collection["pdf_hint_attempts"][0]["redirects"]
        original_transition, = proof["redirects"]
        assert original_transition["next_url"] == public_transition["next_url"] == redirected
        assert public_transition["raw_path"].startswith("study-literature/attempt-3/literature/")
        raw = (service._workspace(research_id).path("research") / public_transition["raw_path"]).read_bytes()
        assert raw == b"Actual synthetic redirect body" and hashlib.sha256(raw).hexdigest() == original_transition["sha256"]
    assert state["study_literature_pending"] is True and runner.calls == 0


@pytest.mark.parametrize("variant", ["unfrozen_identity", "unfrozen_listing", "source_metadata", "unverifiable_version", "identity_digest"])
def test_approval_recomputes_author_copy_identity_and_requires_frozen_proof(setup, monkeypatch, variant):
    service, runner, research_id, _ = two_negative_attempts(setup)
    service.collector = hinted_collector(monkeypatch)
    state = service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, [PDF_HINT])
    source = next(source for source in state["literature"]["sources"] if source.get("copy_type") == "author_copy")
    review = copy.deepcopy(STUDY_REVIEW)
    review["selected_sources"][0].update(source_id=source["id"], excerpt_index=0)
    review["publication_readiness"]["closest_work"][0].update(source_id=source["id"], excerpt_index=0, quote=source["excerpts"][0][:200])
    assessment = StudyReview.model_validate(review)
    selected = service._selected_literature(state["literature"], assessment.selected_sources)
    ws = service._workspace(research_id)
    record = ws.get("workflow", research_id, Workflow)
    if variant in {"unfrozen_identity", "unfrozen_listing"}:
        field = "identity_path" if variant == "unfrozen_identity" else "discovery_path"
        path = (ws.path("research") / source[field]).relative_to(ws.root).as_posix()
        record.artifacts = {key: frozen for key, frozen in record.artifacts.items() if frozen.path != path}
    elif variant == "source_metadata":
        selected["sources"][0]["title"] += " A different study"
    elif variant == "unverifiable_version":
        selected["sources"][0]["publication_version"] = "published"
    else:
        selected["sources"][0]["identity_sha256"] = "0" * 64
    code = "ARTIFACT_CHANGED" if variant == "identity_digest" else "PUBLICATION_EVIDENCE_INVALID"
    assert_code(code, lambda: service._publication_gate(ws, record, ResearchPlan.model_validate(protocol()), assessment.publication_readiness, selected))
    assert runner.calls == 0


@pytest.mark.parametrize("variant", ["no_hints", "different_title"])
@pytest.mark.parametrize("number", [1, 2])
def test_every_returned_author_copy_binds_that_rounds_reserved_hint(setup, monkeypatch, variant, number):
    service, runner, research_id, old = initial(setup)
    if number == 2:
        service.collector = collector(no_sources=True)
        service.collect_study_literature(research_id, QUERIES, REASON, [])
    candidates = [] if variant == "no_hints" else [{**PDF_HINT, "title": PDF_HINT["title"] + " with different methods"}]
    actual = hinted_collector(monkeypatch)
    def unbound(queries, root, **kwargs):
        # Simulate a misbound collector result, not a forged scientific model
        # approval: all returned literal identity evidence is otherwise valid.
        assert kwargs["pdf_candidates"] == candidates
        return actual(queries, root, **{**kwargs, "pdf_candidates": [PDF_HINT]})
    service.collector = unbound
    assert_code("PUBLICATION_EVIDENCE_INVALID", lambda: service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, candidates))
    state = service.status(research_id)
    assert state["study_literature_attempt"] == number and state["study_literature_pending"] is False
    assert state["artifacts"]["proposal"] == old["artifacts"]["proposal"] and state["execution_attempt"] == 0
    assert "plan" not in state["artifacts"] and runner.calls == 0

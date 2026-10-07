"""Bounded synthetic evidence revisions; no academic merit or actual SCI is asserted."""
import copy
import hashlib
import json
import zipfile

import pytest

from paper_factory import ipc
from paper_factory.autonomous import literature, science
from paper_factory.autonomous.models import FrozenArtifact
from paper_factory.workflow import WorkflowError
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import digest_file, write_json
from test_workflow import BUNDLE, MANUSCRIPT_REVIEW, REVIEW, STUDY_REVIEW, SYNTHETIC_PREFIX, SYNTHETIC_SUFFIX, collect, manuscript, observations, protocol, setup

QUERIES = ["direct closest methods synthetic fixture"]
REASON = "The retained review requires primary methods for its unresolved knowledge difference."


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
    def retrieve(queries, root, *, limit, cancel):
        assert limit == 3
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
    state = service.collect_study_literature(research_id, QUERIES, REASON)
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
    assert_code("STUDY_REVIEW_REQUIRED", lambda: service.collect_study_literature(research_id, QUERIES, REASON))
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
        state = service.collect_study_literature(research_id, [QUERIES[0] + str(number)], REASON)
        assert state["study_literature_attempt"] == number and state["study_literature_pending"] is False
        assert state["artifacts"]["literature"]["sha256"] != old["artifacts"]["literature"]["sha256"]
        assert_code("REVIEW_EVIDENCE_CONFLICT", lambda: service.submit_study_review(research_id, rejected()))
    assert state["resume_kind"] is None
    assert_code("STUDY_LITERATURE_LIMIT", lambda: service.collect_study_literature(research_id, QUERIES, REASON))
    assert_code("INVALID_STATE", lambda: service.resume(research_id))
    assert runner.calls == 0


def test_global_attempt_limit_survives_a_substantively_new_proposal(setup):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector(no_sources=True)
    for number in (1, 2):
        service.collect_study_literature(research_id, [QUERIES[0] + str(number)], REASON)
    plan = protocol()
    plan["question"] += " A changed mechanism question is separately preregistered."
    plan["conditions"] += ["different-mechanism"]
    service.submit_proposal(research_id, plan)
    service.collector = collect
    service.collect_literature(research_id)
    state = service.submit_study_review(research_id, rejected())
    assert state["proposal_attempt"] == 2 and state["study_literature_attempt"] == 2
    assert state["resume_kind"] is None
    assert_code("STUDY_LITERATURE_LIMIT", lambda: service.collect_study_literature(research_id, QUERIES, REASON))
    assert runner.calls == 0


@pytest.mark.parametrize("flags,missing_query", [({"cancelled": True}, False), ({"timed_out": True}, False),
                                                ({"rate_limited": True}, False), ({}, True)])
def test_partial_collection_preserves_raw_evidence_but_cannot_freeze_protocol(setup, flags, missing_query):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector(flags=flags, missing_query=missing_query)
    state = service.collect_study_literature(research_id, QUERIES, REASON)
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
    assert_code("LITERATURE_QUERIES_INVALID", lambda: service.collect_study_literature(research_id, queries, reason))
    assert service.status(research_id)["artifacts"] == old["artifacts"]
    assert service.status(research_id)["study_literature_attempt"] == 0 and runner.calls == 0


def test_multiline_reason_is_retained_without_changing_the_query_contract(setup):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector()
    reason = "  " + REASON + "\nA second paragraph identifies the missing directly read methods.\n"
    state = service.collect_study_literature(research_id, QUERIES, reason)
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
        service.collect_study_literature(research_id, QUERIES, REASON)
    assert service.status(research_id)["study_literature_attempt"] == 1 and runner.calls == 0


def test_same_source_new_fulltext_reading_replaces_it_without_scope_downgrade(setup):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector(identifier="fixture-oracle", extra=" Additional primary methods establish a different bounded literal passage.")
    state = service.collect_study_literature(research_id, QUERIES, REASON)
    assert len(state["literature"]["sources"]) == 1 and state["study_literature_pending"] is True
    retained_text = state["literature"]["sources"][0]["text_sha256"]
    service.submit_study_review(research_id, rejected())
    def abstract(*args, **kwargs):
        evidence = collector(identifier="fixture-oracle")(*args, **kwargs)
        evidence["sources"][0]["scope"] = "abstract"
        return evidence
    service.collector = abstract
    state = service.collect_study_literature(research_id, QUERIES, REASON)
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
    state = service.collect_study_literature(research_id, QUERIES, REASON)
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
    state = service.collect_study_literature(research_id, QUERIES, REASON)
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
    state = service.collect_study_literature(research_id, QUERIES, REASON)
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
    service.collect_study_literature(research_id, QUERIES, REASON)
    path = service.artifact_path(research_id, key)
    path.write_bytes(path.read_bytes() + b" ")
    assert_code("ARTIFACT_CHANGED", lambda: service.submit_study_review(research_id, rejected()))
    assert runner.calls == 0


def test_ipc_declares_exact_api_fields_and_dispatches_native_method(setup):
    service, _, research_id, _ = initial(setup)
    service.collector = collector()
    params = {"researchId": research_id, "queries": QUERIES, "reason": REASON}
    request = ipc.request(json.dumps({"id": "literature-request", "method": "workflow.collectStudyLiterature", "params": params}).encode())
    runtime = object.__new__(ipc.Dispatcher)
    runtime.service = service
    result = runtime.execute(request["method"], request["params"])
    assert result["study_literature_pending"] is True
    for bad in ({**params, "untrustedPath": "elsewhere"}, {"researchId": research_id, "queries": QUERIES}):
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
    assert_code("STUDY_LITERATURE_INELIGIBLE", lambda: service.collect_study_literature(research_id, QUERIES, REASON))
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
    assert_code(code, lambda: service.collect_study_literature(research_id, QUERIES, REASON))
    assert service.status(research_id)["resume_kind"] is None
    assert runner.calls == 0


def test_second_attempt_new_reading_can_resume_once_but_repeated_review_is_forbidden(setup):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector(no_sources=True)
    service.collect_study_literature(research_id, QUERIES, REASON)
    service.collector = collector()
    state = service.collect_study_literature(research_id, QUERIES, REASON)
    assert state["study_literature_attempt"] == 2 and state["study_literature_pending"] is True
    assert state["resume_kind"] == "preparation"
    service.resume(research_id)
    held = service.submit_study_review(research_id, rejected())
    assert held["study_literature_pending"] is False and held["resume_kind"] is None
    assert_code("REVIEW_EVIDENCE_CONFLICT", lambda: service.submit_study_review(research_id, rejected()))
    assert_code("INVALID_STATE", lambda: service.resume(research_id))
    assert runner.calls == 0


def test_original_collector_cannot_bypass_targeted_budget_after_partial_followup(setup):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector(flags={"timed_out": True})
    service.collect_study_literature(research_id, QUERIES, REASON)
    assert_code("STUDY_LITERATURE_REQUIRED", lambda: service.collect_literature(research_id))
    state = service.status(research_id)
    assert state["study_literature_attempt"] == 1 and state["study_literature_pending"] is True
    assert runner.calls == 0


def test_newly_received_reading_must_be_reviewed_before_replacing_proposal(setup):
    service, runner, research_id, _ = initial(setup)
    service.collector = collector()
    service.collect_study_literature(research_id, QUERIES, REASON)
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
    state = service.collect_study_literature(research_id, QUERIES, REASON)
    source = next(source for source in state["literature"]["sources"] if source["id"] == "new-primary")
    ws = service._workspace(research_id)
    path = ws.path("research") / source["text_path"]
    path.write_bytes(path.read_bytes() + b"Changed methods.")
    assert_code("ARTIFACT_CHANGED", lambda: service.submit_study_review(research_id, copy.deepcopy(STUDY_REVIEW)))
    assert runner.calls == 0


def test_reproduction_archive_preserves_original_review_supplement_and_raw_bytes_without_dispatch(setup):
    service, runner, research_id, old = initial(setup)
    original_review = service.artifact_path(research_id, "study-review-1").read_bytes()
    original_literature = service.artifact_path(research_id, "literature").read_bytes()
    service.collector = collector()
    state = service.collect_study_literature(research_id, QUERIES, REASON)
    source = next(source for source in state["literature"]["sources"] if source["id"] == "new-primary")
    service.submit_study_review(research_id, copy.deepcopy(STUDY_REVIEW))
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
    service.submit_manuscript(research_id, manuscript(), copy.deepcopy(MANUSCRIPT_REVIEW))
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
        for field, digest in (("raw_path", "sha256"), ("metadata_path", "metadata_sha256"), ("text_path", "text_sha256")):
            assert hashlib.sha256(archive.read(source[field])).hexdigest() == source[digest]
        assert archive.testzip() is None
    assert runner.calls == 0

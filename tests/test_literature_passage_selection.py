"""Synthetic body selection contracts, without real literature or execution."""

import copy
import json

import pytest
from pydantic import ValidationError

from paper_factory.autonomous import literature
from paper_factory.ipc import request
from paper_factory.workflow import WorkflowError, _freeze, _read
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import digest_file, write_json
from test_autonomous_literature import clock
from test_retained_primary_literature import approve_reused, preprint
from test_unicode_report_workflow import initial as standard
from test_workflow import (BUNDLE, REVIEW, STUDY_REVIEW, SYNTHETIC_ABSTRACT, SYNTHETIC_PASSAGE,
                           SYNTHETIC_PREFIX, SYNTHETIC_SUFFIX, finished, rejected_study_review, setup)


PASSAGE = ("Synthetic supplementary body 😀 passage establishes a literal Unicode reading contract. "
           "It exercises selected evidence preservation and never establishes real research novelty or an empirical result.")


def body_fixture(service, identifier, *, extra=PASSAGE, mutate=None):
    def update(packet, root):
        source = packet["sources"][0]
        text = SYNTHETIC_PREFIX + SYNTHETIC_PASSAGE + "\n" + extra + SYNTHETIC_SUFFIX
        retained = root / source["text_path"]
        retained.write_bytes(text.encode("utf-8"))
        source.update(text_sha256=digest_file(retained), text_chars=len(text), body_range=literature.full_text_body_range(text))
        if mutate:
            mutate(packet, root)
    return preprint(service, identifier, mutate=update)


def selection(state, text=PASSAGE):
    source = state["literature"]["sources"][0]
    return {"source_id": source["id"], "text_sha256": source["text_sha256"], "text": text,
            "relevance": "Synthetic passage supports a bounded literal-reading product contract, not scientific approval."}


def test_native_selects_nonbmp_outside_automatic_excerpt_and_keeps_originals(setup):
    service, runner, identifier = setup
    state = body_fixture(service, identifier)
    original = {key: service.artifact_path(identifier, key).read_bytes() for key in state["artifacts"]}
    selected = service.select_literature_passages(identifier, [selection(state)])
    passage, = selected["literature_passages"]["passages"]
    assert passage["start"] == len(SYNTHETIC_PREFIX + SYNTHETIC_PASSAGE + "\n")
    assert passage["end"] == passage["start"] + len(PASSAGE)
    assert passage["excerpt_index"] == 1 and passage["text"] == PASSAGE
    assert selected["literature"]["sources"][0]["excerpts"] == [SYNTHETIC_PASSAGE, PASSAGE]
    assert selected["literature"]["sources"][0]["excerpt_ranges"][1] == {"start": passage["start"], "end": passage["end"]}
    assert selected["proposal_attempt"] == 1 and selected["study_literature_attempt"] == selected["execution_attempt"] == 0
    assert selected["study_review"] is None and runner.calls == 0
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in original.items())
    assert _read(service._workspace(identifier), service._workspace(identifier).latest("workflow", Workflow), "literature")["sources"][0]["excerpts"] == [SYNTHETIC_PASSAGE]
    assert service.read_material(identifier, "evidence", "literature-passages")["is_untrusted_data"] is True


@pytest.mark.parametrize("defect", ["unknown_id", "wrong_digest", "abstract", "bibliography", "invented", "normalized", "repeated"])
def test_unverified_or_ambiguous_passages_cannot_be_frozen(setup, defect):
    service, runner, identifier = setup
    state = body_fixture(service, identifier, extra=PASSAGE + "\n" + PASSAGE if defect == "repeated" else PASSAGE)
    choice = selection(state)
    if defect == "unknown_id": choice["source_id"] = "source-from-another-packet"
    elif defect == "wrong_digest": choice["text_sha256"] = "0" * 64
    elif defect == "abstract": choice["text"] = SYNTHETIC_ABSTRACT
    elif defect == "bibliography": choice["text"] = SYNTHETIC_SUFFIX.split("References\n", 1)[1]
    elif defect == "invented": choice["text"] = PASSAGE.replace("Unicode", "invented")
    elif defect == "normalized": choice["text"] = PASSAGE.replace("😀", " ")
    before = service.status(identifier)
    with pytest.raises(WorkflowError, match="current verified|exactly once"):
        service.select_literature_passages(identifier, [choice])
    after = service.status(identifier)
    assert after["artifacts"] == before["artifacts"] and runner.calls == 0


@pytest.mark.parametrize("defect", ["abstract_scope", "invalid_body", "missing_binding", "changed_bytes"])
def test_native_rechecks_current_frozen_identity_and_body(setup, defect):
    service, runner, identifier = setup
    def alter(packet, root):
        source = packet["sources"][0]
        if defect == "abstract_scope": source["scope"] = "abstract"
        elif defect == "invalid_body": source["body_range"]["end"] -= 1
    state = body_fixture(service, identifier, mutate=alter)
    choice = selection(state)
    ws = service._workspace(identifier)
    record = ws.latest("workflow", Workflow)
    if defect == "missing_binding":
        source = state["literature"]["sources"][0]
        for key in list(record.artifacts):
            if record.artifacts[key].sha256 == source["text_sha256"]:
                record.artifacts.pop(key)
        ws.save("workflow", record)
    elif defect == "changed_bytes":
        source = state["literature"]["sources"][0]
        (ws.path("research") / source["text_path"]).write_bytes(b"Changed retained source")
    with pytest.raises(WorkflowError):
        service.select_literature_passages(identifier, [choice])
    assert runner.calls == 0


def test_new_literal_body_allows_one_bound_review_without_resetting_counts(setup):
    service, runner, identifier = setup
    state = body_fixture(service, identifier)
    service.submit_study_review(identifier, rejected_study_review())
    old = service.artifact_path(identifier, "study-review-1").read_bytes()
    selected = service.select_literature_passages(identifier, [selection(state)])
    assert selected["study_literature_pending"] is True
    approved = copy.deepcopy(STUDY_REVIEW)
    source = state["literature"]["sources"][0]
    approved["selected_sources"][0].update(source_id=source["id"], excerpt_index=1)
    approved["publication_readiness"]["closest_work"][0].update(source_id=source["id"], excerpt_index=1, quote=PASSAGE[:100])
    planned = service.submit_study_review(identifier, approved)
    assert planned["stage"] == "planned" and planned["proposal_attempt"] == 1
    assert planned["study_literature_attempt"] == planned["execution_attempt"] == 0 and runner.calls == 0
    assert service.artifact_path(identifier, "study-review-1").read_bytes() == old
    ws = service._workspace(identifier)
    service._require_study_review(ws, ws.latest("workflow", Workflow))


def test_identical_substrings_empty_or_relevance_changes_do_not_unlock_review(setup):
    service, runner, identifier = setup
    state = body_fixture(service, identifier)
    service.submit_study_review(identifier, rejected_study_review())
    empty = service.select_literature_passages(identifier, [])
    assert empty["literature_passages"]["passages"] == [] and not empty["study_literature_pending"]
    automatic = service.select_literature_passages(identifier, [selection(state, SYNTHETIC_PASSAGE[:100])])
    assert not automatic["study_literature_pending"]
    with pytest.raises(WorkflowError) as refused:
        service.submit_study_review(identifier, rejected_study_review())
    assert refused.value.code == "REVIEW_EVIDENCE_CONFLICT"
    selected = service.select_literature_passages(identifier, [selection(state)])
    service.submit_study_review(identifier, rejected_study_review())
    choice = selection(state); choice["relevance"] += " A different explanation cannot create scientific evidence."
    unchanged = service.select_literature_passages(identifier, [choice])
    assert unchanged["artifacts"] == selected["artifacts"] | {key: value for key, value in unchanged["artifacts"].items() if key.startswith("study-review")}
    assert not unchanged["study_literature_pending"]
    assert not service.select_literature_passages(identifier, [selection(state, SYNTHETIC_PASSAGE[:100])])["study_literature_pending"]
    assert not service.select_literature_passages(identifier, [])["study_literature_pending"] and runner.calls == 0


@pytest.mark.parametrize("study_selection", [False, True])
def test_authoring_can_select_current_study_body_without_collection_or_approval_replacement(setup, study_selection):
    service, runner, identifier = setup
    state = body_fixture(service, identifier)
    if study_selection:
        service.select_literature_passages(identifier, [selection(state)])
    approve_reused(service, identifier, state)
    approved = service.artifact_path(identifier, "study-review").read_bytes()
    service.submit_code(identifier, copy.deepcopy(BUNDLE), REVIEW)
    service.start_experiment(identifier)
    analyzed = finished(service, identifier)
    assert analyzed["stage"] == "analyzed"
    snapshots = {key: service.artifact_path(identifier, key).read_bytes() for key in ("study-review", "plan", "observations", "analysis")}
    selected = service.select_literature_passages(identifier, [selection(state)])
    assert selected["authoring_literature"]["sources"][0]["excerpts"][1] == PASSAGE
    chosen = service.select_authoring_literature(identifier, [{"source_id": selection(state)["source_id"], "excerpt_index": 1,
        "relevance": selection(state)["relevance"]}])
    assert chosen["literature"]["sources"][0]["excerpts"] == [SYNTHETIC_PASSAGE, PASSAGE]
    assert chosen["execution_attempt"] == analyzed["execution_attempt"] == runner.calls == 1
    assert chosen["study_literature_attempt"] == analyzed["study_literature_attempt"] == 0
    assert all(service.artifact_path(identifier, key).read_bytes() == raw for key, raw in snapshots.items())
    ws = service._workspace(identifier)
    service._require_study_review(ws, ws.latest("workflow", Workflow))
    assert service.artifact_path(identifier, "study-review").read_bytes() == approved


def test_standard_passage_resolves_combining_codepoints_and_stays_within_one_section(setup, monkeypatch, clock):
    service, runner, identifier, state = standard(setup, monkeypatch)
    source, = state["literature"]["sources"]
    retained = (service._workspace(identifier).path("research") / source["text_path"]).read_text(encoding="utf-8")
    boundary = source["section_ranges"][0]["end"]
    cross_section = retained[boundary - 90:boundary + 90]
    with pytest.raises(WorkflowError, match="anchored body section"):
        service.select_literature_passages(identifier, [selection(state, cross_section)])
    start = source["section_ranges"][1]["start"]
    literal = retained[start:start + 180]
    chosen = service.select_literature_passages(identifier, [selection(state, literal)])
    passage, = chosen["literature_passages"]["passages"]
    assert passage["start"] == start and passage["end"] == start + len(literal)
    assert "Cafe\u0301" in literal and "👩‍💻" in literal and runner.calls == 0


def test_native_rederives_selected_packet_even_if_receipt_descriptor_is_rebound(setup):
    service, runner, identifier = setup
    state = body_fixture(service, identifier)
    selected = service.select_literature_passages(identifier, [selection(state)])
    ws = service._workspace(identifier)
    record = ws.latest("workflow", Workflow)
    path = service.artifact_path(identifier, "literature-passages")
    receipt = json.loads(path.read_bytes())
    receipt["packet"]["sources"][0]["excerpts"][1] = "Invented body text must not become a valid scientific citation. " * 3
    write_json(path, receipt)
    for key, frozen in list(record.artifacts.items()):
        if frozen.path == path.relative_to(ws.root).as_posix():
            _freeze(ws, record, key, path)
    ws.save("workflow", record)
    with pytest.raises(WorkflowError, match="rederive"):
        service.status(identifier)
    assert runner.calls == 0 and selected["execution_attempt"] == 0


@pytest.mark.parametrize("defect", ["terminal_control", "cleanup", "running", "cancelled"])
def test_unsafe_states_cannot_select_passages(setup, defect):
    service, runner, identifier = setup
    state = body_fixture(service, identifier)
    ws = service._workspace(identifier)
    record = ws.latest("workflow", Workflow)
    if defect == "terminal_control": record.terminal_control_failure = True
    elif defect == "cleanup": record.code = "CLEANUP_UNCONFIRMED"
    else: record.status = defect
    ws.save("workflow", record)
    with pytest.raises(WorkflowError): service.select_literature_passages(identifier, [selection(state)])
    assert runner.calls == 0


def test_selection_receipt_cannot_migrate_to_another_proposal_or_be_read_by_undeclared_name(setup):
    service, runner, identifier = setup
    state = body_fixture(service, identifier)
    selected = service.select_literature_passages(identifier, [selection(state)])
    old = service.artifact_path(identifier, "literature-passages").read_bytes()
    service.submit_study_review(identifier, rejected_study_review())
    plan = copy.deepcopy(state["proposal"])
    plan["expected_contribution"] += " A substantively revised synthetic declaration for a later proposal."
    revised = service.submit_proposal(identifier, plan)
    assert revised["literature_passages"] is None and revised["proposal_attempt"] == 2
    assert service.artifact_path(identifier, "literature-passages").read_bytes() == old
    with pytest.raises(WorkflowError) as refused:
        service.read_material(identifier, "evidence", "literature-passages-arbitrary-private-file")
    assert refused.value.code == "MATERIAL_NOT_DECLARED" and runner.calls == 0


def test_ipc_accepts_empty_choice_and_rejects_extra_parameters():
    message = {"id": "body-selection", "method": "workflow.selectLiteraturePassages",
               "params": {"researchId": "research-123456789abc", "passages": []}}
    assert request(json.dumps(message).encode()) == message
    message["params"]["start"] = 1
    with pytest.raises(ValueError): request(json.dumps(message).encode())


@pytest.mark.parametrize("changes", [{"text": "short"}, {"text_sha256": "fake"}, {"start": 0}, {"text": 100},
    {"text": "x" * 80 + "\u0000"}, {"text": "x" * 80 + "\u007f"}, {"text": "x" * 80 + "\ud800"}])
def test_selection_contract_refuses_coercion_ranges_and_malformed_literals(setup, changes):
    service, runner, identifier = setup
    state = body_fixture(service, identifier)
    with pytest.raises(ValidationError): service.select_literature_passages(identifier, [{**selection(state), **changes}])
    assert runner.calls == 0

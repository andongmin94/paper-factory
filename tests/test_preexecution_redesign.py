"""Synthetic product boundaries; these fixtures assert no scientific or journal merit."""
import copy
import json
import stat

import pytest

from paper_factory import ipc
from paper_factory.autonomous.models import FrozenArtifact, StudyRedesignReview
from paper_factory.workflow import WorkflowError, WorkflowService
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import digest_file, write_json
from test_workflow import BUNDLE, REVIEW, STUDY_REVIEW, collect, committed_workflows, evidence_selection_receipt, protocol, reject_for_redesign, setup
from test_study_literature_followup import PDF_HINT, REASON, collector, hinted_collector, rejected


def exhaust(service, research_id, *, final_collector=None):
    """Use real capped service transitions, never manually set attempt counters."""
    state = service.status(research_id)
    if not state["proposal_attempt"]:
        plan = protocol(); plan["parameters"]["fixture_size"] += state["redesign_attempt"]
        service.submit_proposal(research_id, plan)
    service.collector = collect
    service.collect_literature(research_id)
    service.submit_study_review(research_id, rejected())
    for number in (2, 3):
        plan = copy.deepcopy(service.status(research_id)["proposal"])
        plan["question"] += f" Synthetic rejected refinement {number}."
        service.submit_proposal(research_id, plan)
        service.collect_literature(research_id)
        service.submit_study_review(research_id, rejected())
    service.collector = collector(no_sources=True)
    for number in (1, 2):
        service.collect_study_literature(research_id, [f"Synthetic negative methods lookup {number}"], REASON, [])
    if final_collector is not None: service.collector = final_collector
    return service.collect_study_literature(research_id, [PDF_HINT["doi"]], REASON, [PDF_HINT])


def candidate(service, research_id):
    value = copy.deepcopy(service.status(research_id)["proposal"])
    value["parameters"]["fixture_size"] += 7
    value["question"] += " A separately justified synthetic sampling domain changes the design."
    return value


def review(accepted=True):
    return {"accepted": accepted, "issues": [] if accepted else ["The candidate does not establish a separately justified scientific difference."],
            **{name: {"passed": accepted if name == "scientific_difference" else True,
                      "reason": "Synthetic preparation fixture tests immutable decisions and establishes no academic merit."}
               for name in ("scientific_difference", "prior_evidence", "feasibility")}}


def assert_error(code, operation):
    with pytest.raises(WorkflowError) as error:
        operation()
    assert error.value.code == code


def stage(service, research_id):
    service.submit_redesign_proposal(research_id, candidate(service, research_id))
    return service.submit_redesign_review(research_id, review())


def structural_rejection(criterion="question"):
    value = rejected()
    value[criterion] = {"passed": False, "reason": "Synthetic structural deficiency requires a different preregistered design."}
    value["issues"].append("The retained synthetic design has an unresolved structural deficiency.")
    return value


def reject_three_proposals(service, research_id, *, final_review=None, partial_attempts=0, initial_collector=collect):
    """Retain partial searches on the first design, then really reject two revisions."""
    for number in (1, 2, 3):
        plan = protocol() if number == 1 else copy.deepcopy(service.status(research_id)["proposal"])
        if number > 1:
            plan["question"] += f" Synthetic rejected structural revision {number}."
        service.submit_proposal(research_id, plan)
        service.collector = initial_collector
        service.collect_literature(research_id)
        state = service.submit_study_review(research_id, final_review if number == 3 and final_review else rejected())
        if number == 1:
            service.collector = collector(no_sources=True)
            for attempt in range(1, partial_attempts + 1):
                state = service.collect_study_literature(research_id, [f"Synthetic retained partial methods {attempt}"], REASON, [])
                assert not state["study_literature_pending"]
    return state


@pytest.mark.parametrize("criterion", ["question", "comparison", "sampling"])
def test_core_rejection_can_prepare_without_inventing_literature_attempts_and_child_needs_fresh_study_review(setup, criterion):
    service, runner, identifier = setup
    old = reject_three_proposals(service, identifier, final_review=structural_rejection(criterion))
    assert old["preparation_redesign_available"] and old["resume_kind"] is None
    assert (old["proposal_attempt"], old["study_literature_attempt"], old["execution_attempt"]) == (3, 0, 0)
    assert not any(key.startswith("study-literature-") for key in old["artifacts"])
    before = {key: service.artifact_path(identifier, key).read_bytes() for key in old["artifacts"]}
    service.submit_redesign_proposal(identifier, candidate(service, identifier))
    assert_error("STUDY_REDESIGN_REVIEW_REQUIRED", lambda: service.redesign_study(identifier))
    service.submit_redesign_review(identifier, review())
    child = service.redesign_study(identifier)
    basis = json.loads(service.artifact_path(identifier, "redesign-preparation").read_bytes())
    assert (basis["proposal_attempt"], basis["study_literature_attempt"], basis["execution_attempt"]) == (3, 0, 0)
    assert json.loads(service.artifact_path(child["id"], "prior-study-" + identifier + "-redesign-preparation").read_bytes()) == basis
    assert child["study_review"] is None and child.get("literature") is None
    assert (child["proposal_attempt"], child["study_literature_attempt"], child["execution_attempt"]) == (1, 0, 0)
    assert_error("INVALID_STATE", lambda: service.submit_code(child["id"], BUNDLE, REVIEW))
    assert_error("INVALID_STATE", lambda: service.start_experiment(child["id"]))
    service.collector = collect
    service.collect_literature(child["id"])
    assert service.submit_study_review(child["id"], copy.deepcopy(STUDY_REVIEW))["stage"] == "planned"
    assert service.redesign_study(identifier)["id"] == child["id"]
    assert all(service.artifact_path(identifier, key).read_bytes() == data for key, data in before.items())
    assert len(committed_workflows(service)) == 2 and runner.calls == 0


@pytest.mark.parametrize("attempts", [0, 1, 2])
def test_core_passed_body_deficit_cannot_skip_remaining_literature_route(setup, attempts):
    service, runner, identifier = setup
    def abstract(*args, **kwargs):
        evidence = collect(*args, **kwargs)
        evidence["sources"][0]["scope"] = "abstract"
        return evidence
    old = reject_three_proposals(service, identifier, partial_attempts=attempts, initial_collector=abstract)
    assert all(old["study_review"][name]["passed"] for name in ("question", "comparison", "sampling"))
    assert all(source["scope"] == "abstract" for source in old["literature"]["sources"])
    assert old["resume_kind"] == "preparation" and not old["preparation_redesign_available"]
    assert_error("STUDY_REDESIGN_NOT_ALLOWED", lambda: service.submit_redesign_proposal(identifier, candidate(service, identifier)))
    unchanged = service.status(identifier)
    assert unchanged["artifacts"] == old["artifacts"] and unchanged["study_literature_attempt"] == attempts
    assert len(committed_workflows(service)) == 1 and runner.calls == 0


@pytest.mark.parametrize("attempts", [1, 2])
def test_partial_retrieval_chain_survives_structural_successor_with_actual_counts_and_original_bytes(setup, attempts):
    service, runner, identifier = setup
    old = reject_three_proposals(service, identifier, partial_attempts=attempts, final_review=structural_rejection())
    assert old["preparation_redesign_available"] and old["study_literature_attempt"] == attempts
    ws = service._workspace(identifier)
    source_bytes = ws.path("source/transform.js").read_bytes()
    original = {key: service.artifact_path(identifier, key).read_bytes() for key in old["artifacts"]}
    stage(service, identifier)
    basis = json.loads(service.artifact_path(identifier, "redesign-preparation").read_bytes())
    assert basis["study_literature_attempt"] == attempts
    for number in range(1, attempts + 1):
        for kind in ("intent", "collection"):
            key = f"study-literature-{kind}-{number}"
            assert basis["bindings"][key] == {field: old["artifacts"][key][field] for field in ("sha256", "size")}
    assert f"study-literature-intent-{attempts + 1}" not in basis["bindings"]
    child = service.redesign_study(identifier)
    assert json.loads(service.artifact_path(child["id"], "prior-study-" + identifier + "-redesign-preparation").read_bytes()) == basis
    assert child["study_literature_attempt"] == 0
    assert service.status(identifier)["study_literature_attempt"] == attempts
    for key, data in original.items():
        assert service.artifact_path(identifier, key).read_bytes() == data
        retained_key = key if key in {"context", "source-collection"} else "prior-study-" + identifier + "-" + key
        assert service.artifact_path(child["id"], retained_key).read_bytes() == data
    assert service._workspace(child["id"]).path("source/transform.js").read_bytes() == source_bytes
    assert ws.path("source/transform.js").read_bytes() == source_bytes
    assert len(committed_workflows(service)) == 2 and runner.calls == 0


@pytest.mark.parametrize("attempts", [1, 2])
def test_partial_attempt_counter_cannot_be_reset_to_open_preparation(setup, attempts):
    service, runner, identifier = setup
    old = reject_three_proposals(service, identifier, partial_attempts=attempts, final_review=structural_rejection())
    value = candidate(service, identifier)
    ws = service._workspace(identifier); record = ws.get("workflow", identifier, Workflow)
    record.study_literature_attempt = 0
    ws.save("workflow", record)
    assert_error("ARTIFACT_CHANGED", lambda: service.submit_redesign_proposal(identifier, value))
    assert all(key in record.artifacts for key in old["artifacts"])
    assert len(committed_workflows(service)) == 1 and runner.calls == 0


@pytest.mark.parametrize("field", ["proposal_sha256", "prior_study_review_sha256", "prior_literature_sha256"])
def test_partial_intent_must_still_bind_retained_proposal_review_and_literature(setup, field):
    service, runner, identifier = setup
    reject_three_proposals(service, identifier, partial_attempts=1, final_review=structural_rejection())
    value = candidate(service, identifier)
    ws = service._workspace(identifier); record = ws.get("workflow", identifier, Workflow)
    key = "study-literature-intent-1"; path = service.artifact_path(identifier, key)
    intent = json.loads(path.read_bytes()); intent[field] = "0" * 64
    write_json(path, intent)
    record.artifacts[key] = FrozenArtifact(path=record.artifacts[key].path, sha256=digest_file(path), size=path.stat().st_size)
    ws.save("workflow", record)
    assert_error("ARTIFACT_CHANGED", lambda: service.submit_redesign_proposal(identifier, value))
    assert len(committed_workflows(service)) == 1 and runner.calls == 0


def test_partial_new_body_requires_actual_review_before_preparing_structural_successor(setup):
    service, runner, identifier = setup
    reject_three_proposals(service, identifier)
    service.collector = collector(identifier="fixture-oracle")
    pending = service.collect_study_literature(identifier, ["Synthetic new body before structural decision"], REASON, [])
    assert pending["study_literature_pending"] and pending["study_literature_attempt"] == 1
    assert_error("STUDY_REVIEW_REQUIRED", lambda: service.submit_redesign_proposal(identifier, candidate(service, identifier)))
    reviewed = service.submit_study_review(identifier, structural_rejection())
    assert not reviewed["study_literature_pending"] and reviewed["preparation_redesign_available"]
    prepared = stage(service, identifier)
    assert prepared["study_literature_attempt"] == 1 and prepared["execution_attempt"] == 0
    assert len(committed_workflows(service)) == 1 and runner.calls == 0


def test_structural_rejection_cannot_use_stale_literature_review_even_without_new_body(setup):
    service, runner, identifier = setup
    old = reject_three_proposals(service, identifier, partial_attempts=1, final_review=structural_rejection())
    value = candidate(service, identifier)
    ws = service._workspace(identifier); record = ws.get("workflow", identifier, Workflow)
    prior_digest = next(frozen.sha256 for key, frozen in record.artifacts.items()
                        if key.startswith("literature-history-") and frozen.sha256 != old["artifacts"]["literature"]["sha256"])
    path = service.artifact_path(identifier, "study-review")
    receipt = json.loads(path.read_bytes()); receipt["literature_sha256"] = prior_digest
    write_json(path, receipt)
    frozen = FrozenArtifact(path=record.artifacts["study-review"].path, sha256=digest_file(path), size=path.stat().st_size)
    record.artifacts["study-review"] = record.artifacts["study-review-3"] = frozen
    ws.save("workflow", record)
    assert not service.status(identifier)["study_literature_pending"]
    assert_error("STUDY_REVIEW_REQUIRED", lambda: service.submit_redesign_proposal(identifier, value))
    assert len(committed_workflows(service)) == 1 and runner.calls == 0


def test_exact_candidate_becomes_one_child_with_fresh_gates_and_unchanged_parent(setup):
    service, runner, identifier = setup
    old = exhaust(service, identifier)
    assert old["preparation_redesign_available"] and old["resume_kind"] is None
    before = {key: service.artifact_path(identifier, key).read_bytes() for key in old["artifacts"]}
    prepared = stage(service, identifier)
    assert (prepared["stage"], prepared["status"], prepared["proposal_attempt"], prepared["study_literature_attempt"], prepared["execution_attempt"]) == ("proposed", "blocked", 3, 3, 0)
    child = service.redesign_study(identifier)
    assert (child["stage"], child["status"], child["proposal_attempt"], child["study_literature_attempt"], child["execution_attempt"]) == ("proposed", "ready", 1, 0, 0)
    assert child["proposal"] == prepared["redesign_candidate"]
    assert all(child["artifacts"]["proposal"][key] == prepared["artifacts"]["redesign-candidate"][key] for key in ("sha256", "size"))
    assert child["study_review"] is None and child.get("literature") is None
    assert not any(key in child["artifacts"] for key in ("plan", "bundle", "execution", "observations", "analysis"))
    assert child["prior_study"]["execution_attempt"] == 0
    assert not any(key in child["prior_study"] for key in ("protocol", "analysis", "execution", "observations"))
    assert all(service.artifact_path(identifier, key).read_bytes() == data for key, data in before.items())
    assert_error("INVALID_STATE", lambda: service.start_experiment(child["id"]))
    assert_error("INVALID_STATE", lambda: service.submit_code(child["id"], BUNDLE, REVIEW))
    assert service.redesign_study(identifier)["id"] == child["id"]
    assert len(committed_workflows(service)) == 2 and runner.calls == 0
    assert service.status(identifier)["preparation_redesign_available"] is False
    service.collector = collect
    service.collect_literature(child["id"])
    assert service.submit_study_review(child["id"], copy.deepcopy(STUDY_REVIEW))["stage"] == "planned"
    assert runner.calls == 0


def test_rejected_preparation_is_retained_and_cannot_be_replaced_or_create_a_child(setup):
    service, runner, identifier = setup
    exhaust(service, identifier)
    service.submit_redesign_proposal(identifier, candidate(service, identifier))
    denied = service.submit_redesign_review(identifier, review(False))
    raw = service.artifact_path(identifier, "redesign-review").read_bytes()
    assert not denied["preparation_redesign_available"]
    assert_error("REDESIGN_EVIDENCE_CONFLICT", lambda: service.submit_redesign_review(identifier, review()))
    assert_error("STUDY_REDESIGN_NOT_ALLOWED", lambda: service.redesign_study(identifier))
    replacement = candidate(service, identifier); replacement["parameters"]["fixture_size"] += 1
    assert_error("REDESIGN_EVIDENCE_CONFLICT", lambda: service.submit_redesign_proposal(identifier, replacement))
    assert service.submit_redesign_review(identifier, review(False))["redesign_review"] == review(False)
    assert service.artifact_path(identifier, "redesign-review").read_bytes() == raw
    assert len(committed_workflows(service)) == 1 and runner.calls == 0


@pytest.mark.parametrize("change", ["wording", "queries", "seeds", "order", "instrumentation"])
def test_metadata_seed_or_order_changes_cannot_pass_structural_guard(setup, change):
    service, runner, identifier = setup
    exhausted = exhaust(service, identifier)
    value = copy.deepcopy(exhausted["proposal"])
    if change == "wording":
        value["question"] += " Different prose alone cannot establish scientific difference."
        value["expected_contribution"] += " Another description."
    elif change == "queries":
        value["literature_queries"] = ["another synthetic literature query"]
    elif change == "seeds":
        value["seeds"] = [23, 59]; value["parameters"]["resampling_seed"] = 42
    elif change == "order":
        value["conditions"].reverse(); value["metrics"].reverse()
    else:
        value["parameters"]["execution_instrumentation"] = "Another synthetic instrumentation description."
    assert_error("REDESIGN_UNCHANGED", lambda: service.submit_redesign_proposal(identifier, value))
    assert "redesign-candidate" not in service.status(identifier)["artifacts"] and runner.calls == 0


@pytest.mark.parametrize("defect", ["no_candidate", "contradiction", "empty_issues", "blank_issue", "extra_field", "no_criterion", "short_reason"])
def test_preparation_review_requires_complete_consistent_decision(setup, defect):
    service, runner, identifier = setup
    exhaust(service, identifier)
    value = review(False)
    if defect == "no_candidate":
        assert_error("STUDY_REDESIGN_REVIEW_REQUIRED", lambda: service.submit_redesign_review(identifier, value))
        return
    service.submit_redesign_proposal(identifier, candidate(service, identifier))
    if defect == "contradiction": value["accepted"] = True
    elif defect == "empty_issues": value["issues"] = []
    elif defect == "blank_issue": value["issues"] = [" "]
    elif defect == "extra_field": value["publication_approval"] = True
    elif defect == "no_criterion": value.pop("feasibility")
    else: value["prior_evidence"]["reason"] = "short"
    with pytest.raises(ValueError): service.submit_redesign_review(identifier, value)
    assert "redesign-review" not in service.status(identifier)["artifacts"] and runner.calls == 0


@pytest.mark.parametrize("defect", ["proposal_budget", "literature_budget", "active", "control", "execution", "cancel", "source", "proposal"])
def test_unsafe_or_nonexhausted_parent_cannot_stage_a_successor(setup, defect):
    service, runner, identifier = setup
    old = exhaust(service, identifier)
    value = candidate(service, identifier)
    ws = service._workspace(identifier); record = ws.get("workflow", identifier, Workflow)
    if defect == "proposal_budget": record.proposal_attempt = 2
    elif defect == "literature_budget": record.study_literature_attempt = 2
    elif defect == "active": record.active_handle = {"kind": "fixture", "pid": 123}
    elif defect == "control": record.terminal_control_failure = True
    elif defect == "execution": record.execution_attempt = 1
    elif defect == "cancel": record.cancellation_requested = True
    elif defect == "source":
        source = ws.path("source/transform.js"); source.chmod(stat.S_IWRITE | stat.S_IREAD)
        source.write_bytes(b"changed frozen source")
    else: service.artifact_path(identifier, "proposal").write_bytes(b"changed frozen proposal")
    ws.save("workflow", record)
    with pytest.raises(ValueError): service.submit_redesign_proposal(identifier, value)
    assert runner.calls == 0 and len(committed_workflows(service)) == 1


def test_one_executed_origin_plus_two_distinct_successors_preserves_nonzero_and_zero_history(setup):
    service, runner, identifier = setup
    original = reject_for_redesign(service, identifier)
    child = service.redesign_study(identifier)
    exhaust(service, child["id"])
    prepared = stage(service, child["id"])
    last = service.redesign_study(child["id"])
    assert last["redesign_attempt"] == 2 and last["root_research_id"] == identifier
    assert last["prior_study"]["earlier_study"]["analysis"] == original["analysis"]
    assert original["analysis"]["results"]["error.condition_1.mean"]["value"] == 0
    assert original["analysis"]["results"]["error.condition_2.mean"]["value"] > 0
    assert service.artifact_path(last["id"], "prior-study-" + identifier + "-observations").read_bytes() == service.artifact_path(identifier, "observations").read_bytes()
    assert service.artifact_path(last["id"], "prior-study-" + child["id"] + "-redesign-candidate").read_bytes() == service.artifact_path(child["id"], "redesign-candidate").read_bytes()
    assert_error("STUDY_REDESIGN_LIMIT", lambda: service.redesign_study(last["id"]))
    assert last["proposal"] == prepared["redesign_candidate"] and len(committed_workflows(service)) == 3 and runner.calls == 1


@pytest.mark.parametrize("interrupt", ["copy", "first_proposal"])
def test_interrupted_clone_restores_same_candidate_once_after_restart(setup, monkeypatch, interrupt):
    import paper_factory.workflow as module
    service, runner, identifier = setup
    exhaust(service, identifier); prepared = stage(service, identifier)
    with monkeypatch.context() as scope:
        if interrupt == "copy":
            original = module._copy_retained; count = 0
            def copying(*args):
                nonlocal count
                count += 1
                if count == 3: raise OSError("Synthetic interrupted clone")
                return original(*args)
            scope.setattr(module, "_copy_retained", copying)
        else:
            scope.setattr(service, "submit_proposal", lambda *args: (_ for _ in ()).throw(OSError("Synthetic interrupted clone")))
        with pytest.raises(OSError, match="Synthetic interrupted clone"): service.redesign_study(identifier)
    held = service.status(identifier)
    assert held["followup_research_id"] is None and held["redesign_pending"]
    service.close()
    reopened = WorkflowService(service.home, runner=runner, collector=collect)
    try:
        if interrupt == "first_proposal":
            intent = json.loads(reopened.artifact_path(identifier, "redesign-intent").read_bytes())
            pending_id = intent["child_id"]
            pending = reopened.status(pending_id)
            assert (pending["stage"], pending["status"], pending["proposal_attempt"]) == ("created", "ready", 0)
            assert pending["resume_kind"] is None
            pending_ws = reopened._workspace(pending_id)
            before = pending_ws.get("workflow", pending_id, Workflow).model_dump(mode="json")
            assert_error("INVALID_STATE", lambda: reopened.resume(pending_id))
            assert pending_ws.get("workflow", pending_id, Workflow).model_dump(mode="json") == before
            assert not any(key.startswith("workflow-resume-") for key in pending["artifacts"])
        child = reopened.redesign_study(identifier)
        assert child["proposal"] == prepared["redesign_candidate"] and child["proposal_attempt"] == 1
        assert reopened.artifact_path(child["id"], "proposal-1").read_bytes() == reopened.artifact_path(identifier, "redesign-candidate").read_bytes()
        assert child["resume_kind"] == "preparation"
        assert reopened.redesign_study(identifier)["id"] == child["id"]
        assert len(committed_workflows(reopened)) == 2 and runner.calls == 0
    finally: reopened.close()


def test_executed_origin_first_proposal_remains_resumable_without_dispatch(setup):
    service, runner, identifier = setup
    reject_for_redesign(service, identifier)
    child = service.redesign_study(identifier)
    assert (child["stage"], child["proposal_attempt"], child["execution_attempt"]) == ("created", 0, 0)
    assert json.loads(service.artifact_path(child["id"], "redesign-origin").read_bytes())["event"] == "study-redesign"
    assert service.cancel(child["id"])["resume_kind"] == "preparation"
    resumed = service.resume(child["id"])
    assert resumed["resume_kind"] == "preparation" and resumed["status"] == "ready"
    assert resumed["proposal_attempt"] == 0 and resumed["execution_attempt"] == 0
    assert len(committed_workflows(service)) == 2 and runner.calls == 1


def test_preparation_inference_receipts_and_ipc_contracts_are_retained_without_execution(setup):
    service, runner, identifier = setup
    for phase in ("redesign-plan", "redesign-review"):
        value = evidence_selection_receipt(); value["phase"] = phase
        value["id"] = ("12345678" if phase == "redesign-plan" else "87654321") + "-1234-1234-1234-123456789abc"
        receipt = service.record_inference(identifier, value)
        assert json.loads(service.artifact_path(identifier, receipt["artifactId"]).read_bytes())["phase"] == phase
    for method, field, value in (("workflow.submitRedesignProposal", "value", protocol()), ("workflow.submitRedesignReview", "review", review())):
        request = ipc.request(json.dumps({"id": "preparation", "method": method, "params": {"researchId": identifier, field: value}}).encode())
        assert request["params"][field] == value
    assert runner.calls == 0


def test_first_candidate_binding_cannot_be_forged_by_refreezing_first_child_proposal(setup):
    service, runner, identifier = setup
    exhaust(service, identifier); stage(service, identifier)
    child = service.redesign_study(identifier)
    ws = service._workspace(child["id"]); record = ws.get("workflow", child["id"], Workflow)
    path = service.artifact_path(child["id"], "proposal")
    value = json.loads(path.read_bytes()); value["parameters"]["fixture_size"] += 1
    write_json(path, value)
    record.artifacts["proposal"] = record.artifacts["proposal-1"] = FrozenArtifact(path=record.artifacts["proposal"].path, sha256=digest_file(path), size=path.stat().st_size)
    ws.save("workflow", record)
    assert_error("ARTIFACT_CHANGED", lambda: service.collect_literature(child["id"]))
    assert runner.calls == 0


def test_existing_executed_origin_also_refuses_same_ancestor_design_before_new_science(setup):
    service, runner, identifier = setup
    reject_for_redesign(service, identifier)
    child = service.redesign_study(identifier)
    same = protocol(); same["question"] += " Wording and seeds alone cannot justify another execution."
    same["seeds"] = [101, 103]
    assert_error("REDESIGN_UNCHANGED", lambda: service.submit_proposal(child["id"], same))
    assert service.status(child["id"])["proposal_attempt"] == 0 and runner.calls == 1


def test_start_dispatch_independently_rechecks_actual_ancestor_structure(setup):
    """A substituted approved protocol cannot bypass the guard at SCI dispatch."""
    from test_workflow import prepare
    service, runner, identifier = setup
    reject_for_redesign(service, identifier)
    child = service.redesign_study(identifier); prepare(service, child["id"])
    ws = service._workspace(child["id"]); record = ws.get("workflow", child["id"], Workflow)
    root_plan = json.loads(service.artifact_path(identifier, "plan").read_bytes())
    path = service.artifact_path(child["id"], "plan"); write_json(path, root_plan)
    record.artifacts["plan"] = FrozenArtifact(path=record.artifacts["plan"].path, sha256=digest_file(path), size=path.stat().st_size)
    decision = service.artifact_path(child["id"], "study-review")
    receipt = json.loads(decision.read_bytes()); receipt["protocol_sha256"] = record.artifacts["plan"].sha256
    write_json(decision, receipt)
    frozen = FrozenArtifact(path=record.artifacts["study-review"].path, sha256=digest_file(decision), size=decision.stat().st_size)
    record.artifacts["study-review"] = record.artifacts["study-review-1"] = frozen
    ws.save("workflow", record)
    assert_error("REDESIGN_UNCHANGED", lambda: service.start_experiment(child["id"]))
    assert runner.calls == 1 and service.status(child["id"])["execution_attempt"] == 0


def test_new_final_body_requires_its_real_review_before_preparation_can_continue(setup, monkeypatch):
    service, runner, identifier = setup
    held = exhaust(service, identifier, final_collector=hinted_collector(monkeypatch))
    assert held["study_literature_pending"] and not held["preparation_redesign_available"]
    value = candidate(service, identifier)
    assert_error("STUDY_REVIEW_REQUIRED", lambda: service.submit_redesign_proposal(identifier, value))
    reviewed = service.submit_study_review(identifier, rejected())
    assert not reviewed["study_literature_pending"] and reviewed["preparation_redesign_available"]
    prepared = stage(service, identifier)
    assert prepared["proposal_attempt"] == 3 and prepared["study_literature_attempt"] == 3
    assert prepared["execution_attempt"] == 0 and runner.calls == 0

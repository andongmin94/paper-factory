"""The last retained synthetic review is admitted once without another request."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest

from test_research_development_workflow import development, continuation, generated_evidence, study, unwritten_portfolio
from test_research_development_contract import design, audit
from test_manuscript_improvement import current, reserve, retain, revision, assessment


@pytest.mark.parametrize("development", [2], indirect=True)
@pytest.mark.parametrize("unknown_digest", [False, True])
def test_final_review_transport_preserves_raw_judgments_calls_and_prior_history(development, monkeypatch, unknown_digest):
    service, rid, _, _, evidence = development
    result, value = design(service, rid, evidence)
    retain(service, rid, reserve(service, rid), audit(current(result), value, repair=True, ready=False))
    result = retain(service, rid, reserve(service, rid), value)
    result = retain(service, rid, reserve(service, rid), audit(current(result), value))
    task = reserve(service, rid)
    state = current(result)
    mapping = state["research_development"]["write_action_ids"]
    retain(service, rid, task, {"revisions": [revision(service, rid, {**task, "venue_id": venue, "action_id": mapping[venue]}) for venue in state["versions"]]})

    normal_materials = service._development_materials
    def retained_old_request(ws, record, state, purpose):
        material = normal_materials(ws, record, state, purpose)
        if purpose == "develop-review":
            assert "revision_bindings" not in material
            assert all(set(target) == {"venue_id", "manuscript_sha256", "markdown_artifact_id"} for target in material["review_targets"].values())
            assert all("draft_sha256" not in article and "markdown_sha256" not in article for article in material["manuscripts"].values())
            # Reproduce the already-retained old request, not a production grant or new old-format path.
            material["review_targets"] = deepcopy(state["research_development"]["write_versions"])
        return material
    monkeypatch.setattr(service, "_development_materials", retained_old_request)
    task = reserve(service, rid)
    material = json.loads(task["prompt"].split("\n")[-1])["materials"]
    targets = current(service.status(rid))["research_development"]["write_versions"]
    reviews = [assessment({**task, "venue_id": venue, "manuscript_sha256": version["draft_sha256"]}, 8) for venue, version in targets.items()]
    markdown = material["manuscripts"][reviews[1]["venue_id"]]["markdown"]
    literal = "A synthetic additional decision case distinguishes declared configuration from a caller's interpretation."
    assert markdown.count(literal) == 1
    reviews[1]["scores"][4]["passages"] = [literal[0].swapcase() + literal[1:]]
    if unknown_digest:reviews[1]["manuscript_sha256"] = "f" * 64
    original_response = {"assessments": reviews}
    retain(service, rid, task, original_response)
    finished = service.finish_manuscript_improvement(rid)
    with service._operation(rid) as (ws, record):
        before = deepcopy(service._improvement_state(ws, record))
    assert before["calls"][-1]["outcome"] == "rejected"
    repaired = service.repair_manuscript_improvement(rid)
    with service._operation(rid) as (ws, record):
        after = deepcopy(service._improvement_state(ws, record))
    proof_ref = after["research_development"]["review_admission_repairs"][task["call_id"]]
    proof = json.loads(service.artifact_path(rid, proof_ref["artifact_id"]).read_bytes())
    assert before["calls"] == after["calls"] and before["policy"] == after["policy"]
    assert before["versions"] == after["versions"]
    assert before["research_development"]["assessment_errors"] == after["research_development"]["assessment_errors"]
    assert all(after["reviews"][venue][:len(previous)] == previous for venue, previous in before["reviews"].items())
    assert proof["additional_model_requests"] == 0 and proof["remaining_authorized_requests"] == 0
    for key, artifact in finished["artifacts"].items():
        assert repaired["artifacts"][key] == artifact
        assert hashlib.sha256(service.artifact_path(rid, key).read_bytes()).hexdigest() == artifact["sha256"]
    if unknown_digest:
        assert proof_ref["outcome"] == "rejected" and after["reviews"] == before["reviews"]
        assert after["finished"] and after["research_development"]["closed"]
    else:
        assert proof_ref["outcome"] == "admitted" and proof["normalization"]["restores_original_response_exactly"]
        assert current(repaired)["next_task"] is None
        for review in reviews:
            accepted = after["reviews"][review["venue_id"]][-1]
            assert accepted["recommendation"] == review["recommendation"]
            assert [score["score"] for score in accepted["scores"]] == [score["score"] for score in review["scores"]]
            assert accepted["manuscript_sha256"] == targets[review["venue_id"]]["markdown_sha256"]
        completed = service.finish_manuscript_improvement(rid)
        assert current(completed)["research_development"]["status"] == "manuscripts_assessed"
        assert current(completed)["counts"]["model_attempts"] == len(before["calls"])
    snapshot = service.status(rid)["manuscript_improvement_snapshot"]
    assert service.repair_manuscript_improvement(rid)["manuscript_improvement_snapshot"] == snapshot
    home, runner = service.home, service.runner
    service.close()
    from paper_factory.workflow import WorkflowService
    from paper_factory.ipc import Dispatcher
    reopened = WorkflowService(home, runner=runner)
    dispatcher = Dispatcher(SimpleNamespace(service=reopened), None)
    try:
        assert reopened.status(rid)["manuscript_improvement_snapshot"] == snapshot
        listed = dispatcher.execute("workflow.list", {})
        assert len(listed) == 1 and listed[0]["manuscript_improvement_snapshot"] == snapshot
        assert current(listed[0])["research_development"]["review_admission_repairs"][task["call_id"]] == proof_ref
    finally:
        dispatcher._pool.shutdown(wait=True)
        reopened.close()

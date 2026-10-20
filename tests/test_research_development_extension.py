"""A new explicit authorization appends a bounded round without old-state edits."""
import copy
import hashlib
import json
from uuid import uuid4

import pytest

from test_research_development_workflow import (development, continuation, generated_evidence, study, unwritten_portfolio)
from test_research_development_contract import design, audit
from test_manuscript_improvement import current, reserve, retain, revision, assessment
from paper_factory.workflow import _read


def complete(service, rid, evidence):
    result, value = design(service, rid, evidence)
    retain(service, rid, reserve(service, rid), audit(current(result), value))
    task = reserve(service, rid)
    state = current(service.status(rid))
    assert '"allowed_contribution_evidence_ids"' in task["prompt"]
    mapping = state["research_development"]["write_action_ids"]
    retain(service, rid, task, {"revisions": [revision(service, rid, {**task, "venue_id": venue, "action_id": mapping[venue]}) for venue in state["versions"]]})
    task = reserve(service, rid)
    targets = current(service.status(rid))["research_development"]["write_versions"]
    retain(service, rid, task, {"assessments": [assessment({**task, "venue_id": venue,
        "manuscript_sha256": version["markdown_sha256"]}, 8) for venue, version in targets.items()]})
    return service.finish_manuscript_improvement(rid)


def test_exact_eighteen_to_twenty_four_authorization_is_once_and_archives_literal_prior_round(development):
    service, rid, _, _, _ = development
    with service._operation(rid) as (ws, record):
        state = service._improvement_state(ws, record)
        # Synthetic retained canceled reservations exercise additive accounting only.
        while len(state["calls"]) < 18:
            state["calls"].append({"call_id": str(uuid4()), "purpose": "historical-cancelled-reservation",
                "outcome": "interrupted", "dispatch_status": "synthetic_cancelled_before_dispatch", "round_id": None})
        state["research_development"].update(closed=True, completed_stages=["plan", "evidence", "audit", "repair", "write", "review"])
        state["finished"] = True
        state["policy"].update(model_call_limit=18, action_limit=8)
        service._improvement_save(ws, record, state)
        before = copy.deepcopy(state)
    original = service.status(rid)
    with pytest.raises(ValueError, match="exact current prior round"):
        service.extend_research_development_round(rid, "research-development-round-99")
    assert service.status(rid)["manuscript_improvement_snapshot"] == original["manuscript_improvement_snapshot"]
    extended = service.extend_research_development_round(rid, "research-development-round-1")
    state = current(extended)
    with service._operation(rid) as (ws, record):
        private = copy.deepcopy(service._improvement_state(ws, record))
    assert state["policy"]["model_call_limit"] == 24 and len(state["calls"]) == 18
    assert state["research_development"]["id"] == "research-development-round-2"
    history = state["research_development_history"][0]
    assert history["value"] == before["research_development"]
    assert json.loads(service.artifact_path(rid, history["artifact_id"]).read_bytes())["value"] == history["value"]
    for name in ("calls", "actions", "reviews", "versions"):
        assert private[name] == before[name]
    for key, artifact in original["artifacts"].items():
        assert extended["artifacts"][key] == artifact
        assert hashlib.sha256(service.artifact_path(rid, key).read_bytes()).hexdigest() == artifact["sha256"]
    for repeated in (service.extend_research_development_round(rid, "research-development-round-1"),
                     service.grant_research_development_round(rid), service.start_manuscript_improvement(rid)):
        assert repeated["manuscript_improvement_snapshot"] == extended["manuscript_improvement_snapshot"]
    with pytest.raises(ValueError, match="one additional research round"):
        service.extend_research_development_round(rid, "research-development-round-2")


@pytest.mark.parametrize("development", [2], indirect=True)
def test_second_round_namespace_and_question_request_never_mutate_first_round(development):
    service, rid, _, _, evidence = development
    first = complete(service, rid, evidence)
    with service._operation(rid) as (ws, record):
        before = copy.deepcopy(service._improvement_state(ws, record))
    extended = service.extend_research_development_round(rid, before["research_development"]["id"])
    active = current(extended)["research_development"]
    assert active["artifact_prefix"] == "manuscript-improvement-development-round-2"
    assert active["contract_version"] == 3
    assert active["relative_root"].endswith("/round-2")
    assert all(name.startswith("develop-r2-write-") and len(name) <= 60 for name in active["write_action_ids"].values())
    with service._operation(rid) as (ws, record):
        private = service._improvement_state(ws, record)
        materials = service._development_materials(ws, record, private, "develop-design")
        packet = materials["prior_development_evidence"]
        assert packet["value"] == _read(ws, record, before["research_development"]["evidence_artifact_id"])["value"]
        assert "manuscripts" not in materials and "retained_article_bindings" in materials
        assert packet["method_audit"]["sha256"] == before["research_development"]["audit_sha256"]
        assert "generated_states" not in json.dumps(packet["checker"])
    task = reserve(service, rid)
    assert task["purpose"] == "develop-question"
    assert '"source_grounding"' in task["prompt"] and "2-3 genuinely different" in task["prompt"]
    final = service.status(rid)
    after = current(final)
    with service._operation(rid) as (ws, record):
        private = copy.deepcopy(service._improvement_state(ws, record))
    assert private["calls"][:len(before["calls"])] == before["calls"]
    assert private["actions"][:len(before["actions"])] == before["actions"]
    for venue in before["versions"]:
        assert private["versions"][venue][:len(before["versions"][venue])] == before["versions"][venue]
        assert private["reviews"][venue][:len(before["reviews"][venue])] == before["reviews"][venue]
    assert after["research_development_history"][0]["value"] == before["research_development"]
    assert after["counts"]["model_attempts"] == len(before["calls"]) + 1
    assert len([item for item in after["calls"] if item.get("round_id") == active["id"]]) == 1
    for key, artifact in first["artifacts"].items():
        assert final["artifacts"][key] == artifact
        assert hashlib.sha256(service.artifact_path(rid, key).read_bytes()).hexdigest() == artifact["sha256"]
    assert after["research_development"].get("plan_artifact_id") is None


@pytest.mark.parametrize("development", [2], indirect=True)
def test_prompt_limits_reject_before_any_reservation_or_action(development, monkeypatch):
    service, rid, _, granted, _ = development
    before = current(granted)
    for body in ("x" * 710000, "é" * 455000):
        monkeypatch.setattr(service, "_development_materials", lambda *args: {"source_files": [], "body": body})
        with pytest.raises(ValueError, match="before any reservation"):
            reserve(service, rid)
        after = service.status(rid)
        assert after["manuscript_improvement_snapshot"] == granted["manuscript_improvement_snapshot"]
        assert current(after)["calls"] == before["calls"]
        assert current(after)["actions"] == before["actions"]

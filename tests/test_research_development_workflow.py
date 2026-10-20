"""Synthetic native research-development workflow; no provider or project execution."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from test_research_development import evidence as generated_evidence
from test_repository_paper_workflow import study
from test_repository_portfolio import unwritten_portfolio
from test_manuscript_improvement import continuation, current, reserve, retain, revision, assessment
from test_focused_manuscript_round import close_original, synthetic_primary_collection, selection_value
from paper_factory.autonomous.manuscript_improvement import FocusedPriorSelection
from paper_factory.autonomous.research_development import check_development_evidence


def plan_value(evidence):
    case = evidence["cases"][0]
    return {"decision_problem": "Choose a source-bound authorization lifetime for a bounded editor operation.",
        "source_evidence": evidence["source_evidence"], "document_evidence": [],
        "cases": [{"id": case["id"], "reader_decision": case["decision_problem"],
            "alternatives": [{"id": item["id"], "label": item["label"],
                "engineering_choice": "Distinguish current authority from ambient repeated dispatch.",
                "implementation_status": item["implementation_status"],
                "policy_assumptions": item["assumptions"], "costs": item["costs"]} for item in case["alternatives"]],
            "properties": ["Resource equality and recipient currency hold at every modeled dispatch."],
            "evidence_tasks": ["Generate all reachable states and a weakened-guard counterexample."],
            "decisive_condition_flip": "Change the initial expiry condition and recompute two-write progress."}],
        "inspect_source_files": ["tool.js", "README.md"],
        "expected_article_value": "Expose a completed source-to-rule engineering decision rather than a safety slogan.",
        "hard_limits": ["Explicit synthetic fixture, never a claim of actual Frontron execution or efficacy."]}


@pytest.fixture
def development(continuation, generated_evidence, monkeypatch, request):
    service, rid, _, _ = continuation
    old = close_original(service, rid, monkeypatch)
    latest = next(iter(current(old)["versions"].values()))[-1]
    witness = json.loads(service.artifact_path(rid, latest["draft_artifact_id"]).read_bytes())["value"]["source_evidence"][0]
    evidence = copy.deepcopy(generated_evidence)
    evidence["source_evidence"] = [witness]
    for case in evidence["cases"]:
        for alternative in case["alternatives"]:
            for rule in alternative["rules"]:
                rule["evidence_ids"] = [witness["id"]]
    contract = getattr(request, "param", 1)
    options = contract if isinstance(contract, dict) else {"contract_version": contract}
    if options["contract_version"] == 3:
        granted = service.grant_research_development_round(rid)
    else:
        # Reconstruct an already-existing legacy snapshot, never a production grant route.
        with service._operation(rid) as (ws, record):
            state = service._improvement_state(ws, record)
            limit = options.get("call_limit", 6)
            grant = {"id": "research-development-round-1", "origin": "synthetic_retained_legacy_fixture",
                "base_reservations": len(state["calls"]), "additional_call_limit": limit,
                "closed": False, "completed_stages": [], "evidence_versions": [], "repair_required": False}
            if options["contract_version"] == 2:
                grant.update(contract_version=2, authorized_model_call_limit=len(state["calls"]) + limit,
                    write_action_ids={venue: "develop-write-" + venue for venue in state["versions"]})
            service._portfolio_append(ws, record, "manuscript-improvement-development-grant",
                ws.path("research/manuscript-improvement/research-development/grant.json"), grant)
            state["research_development"] = grant
            state["policy"]["model_call_limit"] = len(state["calls"]) + limit
            state["policy"]["action_limit"] = max(state["policy"]["action_limit"], len(state["actions"]) + 2)
            state["finished"] = False
            service._improvement_save(ws, record, state)
            granted = service._public(ws, record)
    def preflight(ws, record, state, venue, markdown, **kwargs):
        key = kwargs["artifact_prefix"]
        report = {"compliance": {"metrics": {"synthetic": True}, "items": []}, "content_format_passed": True,
            "generation": kwargs.get("generation", 1), "converter_binding": service._improvement_converter_binding(venue),
            "scientific_markdown_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
            "scope": "Explicit synthetic preflight, not a native Word measurement."}
        service._portfolio_append(ws, record, key, ws.path(kwargs["relative_root"] + "/preflight.json"), report)
        return markdown, {"artifact_id": key, "sha256": record.artifacts[key].sha256,
                          "content_format_passed": True, "report": report}
    monkeypatch.setattr(service, "_improvement_focused_preflight", preflight)
    return service, rid, old, granted, evidence


def audit_value(state, evidence, repair):
    case = evidence["cases"][0]
    return {"evidence_sha256": state["research_development"]["evidence_sha256"],
        "correspondence": [{"case_id": case["id"], "alternative_id": "guarded", "target_id": "dispatch",
            "verdict": "needs_repair" if repair else "faithful", "reason": "Synthetic independent correspondence fixture does not assert actual source fidelity.",
            "required_repair": "Bind the exact retained source witness and disclose this finite assumption." if repair else ""}],
        "repair_actions": [{"case_id": case["id"], "alternative_id": "guarded", "target_id": "dispatch",
            "issue": "Synthetic actionable source-binding or modeling deficiency is retained.",
            "exact_change": "Use the complete supplied source witness without altering the bounded policy.",
            "available_evidence_ids": [evidence["source_evidence"][0]["id"]], "safely_obtainable": True}] if repair else [],
        "decisive_findings": ["The source-bound comparison remains a bounded synthetic controller test only."],
        "honest_limits": ["No implementation execution, effectiveness or human validation is inferred."],
        "ready_to_write": not repair, "repair_required": repair}


@pytest.mark.parametrize("repair", [False, True])
def test_development_complete_bounded_pipeline_preserves_history_and_replays_without_private_app(development, repair, tmp_path):
    service, rid, old, granted, evidence = development
    assert service.grant_research_development_round(rid)["manuscript_improvement_snapshot"] == granted["manuscript_improvement_snapshot"]
    initial_count = current(old)["counts"]["model_attempts"]
    task = reserve(service, rid)
    assert task["purpose"] == "develop-plan"
    retain(service, rid, task, plan_value(evidence))
    task = reserve(service, rid)
    candidate = copy.deepcopy(evidence)
    if repair:
        candidate["source_evidence"][0]["sha256"] = "0" * 64
    result = retain(service, rid, task, candidate)
    state = current(result)
    if repair:
        assert state["calls"][-1]["outcome"] == "rejected" and state["research_development"]["evidence_failures"]
        assert state["next_task"]["purpose"] == "develop-audit"
    task = reserve(service, rid)
    assert task["phase"] == "quality-review"
    assert "prior_assessments" not in task["prompt"] and '"improvement_plan"' not in task["prompt"]
    retain(service, rid, task, audit_value(current(service.status(rid)), evidence, repair))
    if repair:
        task = reserve(service, rid)
        assert task["purpose"] == "develop-repair"
        retain(service, rid, task, evidence)
    state = current(service.status(rid))
    supplement = state["research_development"]["supplement"]
    with zipfile.ZipFile(service.artifact_path(rid, supplement["artifact_id"])) as archive:
        assert "checker.py" in archive.namelist() and "README.md" in archive.namelist()
        assert not any(name.endswith((".pdf", ".raw")) for name in archive.namelist())
        archive.extractall(tmp_path / "replay")
    replay = subprocess.run([sys.executable, "checker.py", "evidence.json", "--output", "rerun.json", "--graphs"],
        cwd=tmp_path / "replay", capture_output=True, text=True, check=True)
    assert not replay.stderr
    actual = json.loads((tmp_path / "replay/rerun.json").read_bytes())
    expected = json.loads((tmp_path / "replay/generated-graphs.json").read_bytes())
    assert actual["cases"] == expected["cases"] and actual["checker_sha256"] == expected["checker_sha256"]
    if repair:
        assert current(service.status(rid))["next_task"] is None
        finished = service.finish_manuscript_improvement(rid)
        assert current(finished)["research_development"]["status"] == "bounded_research_report"
        assert current(finished)["counts"]["model_attempts"] == initial_count + 4
        return
    task = reserve(service, rid)
    assert task["purpose"] == "develop-write"
    papers = [revision(service, rid, {**task, "venue_id": venue, "action_id": "develop-write-" + venue})
              for venue in current(service.status(rid))["versions"]]
    retain(service, rid, task, {"revisions": papers})
    task = reserve(service, rid)
    assert task["purpose"] == "develop-review" and task["phase"] == "quality-review"
    assert "empty literature_evidence alone is not a defect" in task["prompt"]
    frame = json.loads(task["prompt"][task["prompt"].index('{"research_id":'):])["materials"]
    assert frame["native_format_preflight"] and "prior_assessments" not in frame
    targets = current(service.status(rid))["research_development"]["write_versions"]
    retain(service, rid, task, {"assessments": [assessment({**task, "venue_id": venue,
        "manuscript_sha256": version["markdown_sha256"]}, 8) for venue, version in targets.items()]})
    finished = service.finish_manuscript_improvement(rid)
    state = current(finished)
    assert state["finished"] and state["research_development"]["closed"] and state["next_task"] is None
    assert state["research_development"]["stop_reason"] == "bounded_manuscripts_independently_assessed"
    assert state["counts"]["model_attempts"] == initial_count + (6 if repair else 5)
    assert state["policy"]["model_call_limit"] == initial_count + 6
    assert finished["execution_attempt"] == old["execution_attempt"] == 0
    for key, item in old["artifacts"].items():
        assert finished["artifacts"][key] == item
        assert hashlib.sha256(service.artifact_path(rid, key).read_bytes()).hexdigest() == item["sha256"]


def test_development_context_limit_precedes_reservation_or_action_mutation(development, monkeypatch):
    service, rid, _, granted, _ = development
    monkeypatch.setattr(service, "_development_materials", lambda *args: {"source_files": [], "whole_body": "x" * 701000})
    with pytest.raises(ValueError, match="before any reservation"):
        reserve(service, rid)
    after = service.status(rid)
    assert after["manuscript_improvement_snapshot"] == granted["manuscript_improvement_snapshot"]
    assert current(after)["counts"] == current(granted)["counts"]


def test_development_rejects_changed_planned_case_before_independent_method_audit(development):
    service, rid, _, _, evidence = development
    retain(service, rid, reserve(service, rid), plan_value(evidence))
    task = reserve(service, rid)
    evidence["cases"][0]["id"] = "unplanned-easier-case"
    state = current(retain(service, rid, task, evidence))
    assert state["calls"][-1]["outcome"] == "rejected"
    assert "planned case" in state["calls"][-1]["error"]
    assert state["next_task"]["purpose"] == "develop-audit"
    assert not state["research_development"].get("checker_artifact_id")


def test_audit_repair_can_bind_verified_scholarly_document_without_using_it_as_repository_rule_witness(development):
    service, rid, _, _, evidence = development
    with service._operation(rid) as (ws, record):
        state = service._improvement_state(ws, record)
        collection = synthetic_primary_collection(service, ws, record, FocusedPriorSelection.model_validate(selection_value()))
        state["evidence_collection"] = collection
        service._improvement_save(ws, record, state)
    card = collection["sources"][0]
    evidence["document_evidence"] = [{"source_id": card["id"], "text_sha256": card["text_sha256"],
        "quote": "Authorization must bind the operation intent and its eventual effect.",
        "interpretation": "A validated synthetic scholarly document may support a methodological repair action."}]
    retain(service, rid, reserve(service, rid), plan_value(evidence))
    state = current(retain(service, rid, reserve(service, rid), evidence))
    audit = audit_value(state, evidence, True)
    audit["repair_actions"][0]["available_evidence_ids"] = [card["id"]]
    state = current(retain(service, rid, reserve(service, rid), audit))
    assert state["calls"][-1]["outcome"] == "completed" and state["next_task"]["purpose"] == "develop-repair"
    bad = copy.deepcopy(evidence)
    bad["cases"][0]["alternatives"][0]["rules"][0]["evidence_ids"] = [card["id"]]
    with pytest.raises(ValueError, match="witness|source"):
        check_development_evidence(bad, {evidence["source_evidence"][0]["id"]})


@pytest.mark.parametrize("damage", [None, "target", "support", "wrong_alternative", "evidence_sha"])
def test_exact_retained_audit_target_admission_repair_is_bounded_immutable_and_strict(development, monkeypatch, damage):
    service, rid, _, _, evidence = development
    ambient = evidence["cases"][0]["alternatives"][1]
    next(rule for rule in ambient["rules"] if rule["id"] == "complete")["id"] = "complete_once"
    retain(service, rid, reserve(service, rid), plan_value(evidence))
    retain(service, rid, reserve(service, rid), evidence)
    task = reserve(service, rid)
    audit = audit_value(current(service.status(rid)), evidence, True)
    case_id = evidence["cases"][0]["id"]
    audit["correspondence"][0]["target_id"] = "already-expired"
    audit["repair_actions"][0]["target_id"] = "remove-recipient-check"
    audit["repair_actions"][0]["available_evidence_ids"] = ["complete_once"]
    if damage == "target":
        audit["correspondence"][0]["target_id"] = "invented-missing-flip"
    elif damage == "support":
        audit["repair_actions"][0]["available_evidence_ids"] = ["invented-private-source"]
    elif damage == "wrong_alternative":
        audit["correspondence"][0]["alternative_id"] = "ambient"
    elif damage == "evidence_sha":
        audit["evidence_sha256"] = "0" * 64
    for group in ("correspondence", "repair_actions"):
        for item in audit[group]:
            item["rule_id"] = item.pop("target_id")
    with monkeypatch.context() as patch:
        def old_validator(*args, **kwargs):
            raise ValueError("Methodological correspondence and repair actions must name actual supplied case/alternative/rule IDs")
        patch.setattr(service, "_development_admit_audit", old_validator)
        retained = retain(service, rid, task, audit)
    assert current(retained)["calls"][-1]["outcome"] == "rejected"
    closed = service.finish_manuscript_improvement(rid)
    original_call = copy.deepcopy(current(closed)["calls"][-1])
    repaired = service.repair_manuscript_improvement(rid)
    state = current(repaired)
    proof = state["research_development"]["audit_admission_repairs"][task["call_id"]]
    assert state["calls"][-1] == original_call and state["policy"] == current(closed)["policy"]
    assert state["counts"] == current(closed)["counts"]
    assert proof["outcome"] == ("admitted" if damage is None else "rejected")
    if damage is None:
        assert not state["finished"] and state["next_task"]["purpose"] == "develop-repair"
        assert state["research_development"]["audit"]["correspondence"][0]["target_id"] == "already-expired"
        assert "rule_id" not in state["research_development"]["audit"]["correspondence"][0]
        pending = reserve(service, rid)
        material = json.loads(pending["prompt"][pending["prompt"].index('{"research_id":'):])["materials"]
        assert "constructive model/evidence improvement" in pending["prompt"]
        inspected = material["reproducibility_inspected_files"]
        assert set(inspected) == {"checker-source", "readme", "manifest"}
        for item in inspected.values():
            assert hashlib.sha256(item["text"].encode()).hexdigest() == item["sha256"]
    else:
        assert state["finished"] and state["next_task"] is None
        assert not state["research_development"].get("audit_artifact_id")
    for key, artifact in closed["artifacts"].items():
        assert repaired["artifacts"][key] == artifact
    before_repeat = service.status(rid)["manuscript_improvement_snapshot"]
    assert service.repair_manuscript_improvement(rid)["manuscript_improvement_snapshot"] == before_repeat


@pytest.mark.parametrize("invented", [False, True])
@pytest.mark.parametrize("development", [{"contract_version": 1, "call_limit": 5}], indirect=True)
def test_retained_writer_uses_only_trusted_computed_ids_and_keeps_one_review_slot(development, monkeypatch, invented):
    service, rid, _, _, evidence = development
    retain(service, rid, reserve(service, rid), plan_value(evidence))
    retain(service, rid, reserve(service, rid), evidence)
    retain(service, rid, reserve(service, rid), audit_value(current(service.status(rid)), evidence, False))
    task = reserve(service, rid)
    papers = []
    for venue in current(service.status(rid))["versions"]:
        item = revision(service, rid, {**task, "venue_id": venue, "action_id": "develop-write-" + venue})
        item["contributions"][0]["evidence_ids"].extend(["valid-start", "remove-recipient-check", "already-expired"])
        if invented:
            item["contributions"][0]["evidence_ids"].append("invented-model-finding")
        for section in item["manuscript"]["sections"]:
            section["text"] = section["text"].replace("{{source:configuration}}", "[source:configuration]")
        papers.append(item)
    actual_registry = service._development_computed_evidence
    with monkeypatch.context() as patch:
        patch.setattr(service, "_development_computed_evidence", lambda *args: (set(), actual_registry(*args)[1]))
        rejected = retain(service, rid, task, {"revisions": papers})
    assert current(rejected)["calls"][-1]["outcome"] == "rejected"
    closed = service.finish_manuscript_improvement(rid)
    old_call = copy.deepcopy(current(closed)["calls"][-1])
    repaired = service.repair_manuscript_improvement(rid)
    state = current(repaired)
    proof = state["research_development"]["write_admission_repairs"][task["call_id"]]
    assert state["counts"]["model_attempts"] == current(closed)["counts"]["model_attempts"]
    assert state["calls"][-1] == old_call and state["policy"] == current(closed)["policy"]
    assert proof["outcome"] == ("rejected" if invented else "admitted")
    if not invented:
        assert state["next_task"]["purpose"] == "develop-review" and not state["finished"]
        for original in papers:
            version = state["research_development"]["write_versions"][original["venue_id"]]
            admitted = json.loads(service.artifact_path(rid, version["draft_artifact_id"]).read_bytes())
            assert admitted["contributions"] == original["contributions"]
            assert admitted["value"]["source_evidence"] == original["manuscript"]["source_evidence"]
            for before, after in zip(original["manuscript"]["sections"], admitted["value"]["sections"]):
                assert after["text"] == before["text"].replace("[source:configuration]", "{{source:configuration}}")
    else:
        assert state["finished"] and state["next_task"] is None and not state["research_development"].get("write_versions")
    for key, artifact in closed["artifacts"].items():
        assert repaired["artifacts"][key] == artifact
    assert service.repair_manuscript_improvement(rid)["manuscript_improvement_snapshot"] == repaired["manuscript_improvement_snapshot"]


def test_computed_context_requires_matching_native_input_and_checker_receipts(development):
    service, rid, _, _, evidence = development
    retain(service, rid, reserve(service, rid), plan_value(evidence))
    retain(service, rid, reserve(service, rid), evidence)
    with service._operation(rid) as (ws, record):
        state = service._improvement_state(ws, record)
        identifiers, binding = service._development_computed_evidence(ws, record, state)
        assert "valid-start" in identifiers and binding["input_sha256"]
        bad = copy.deepcopy(state)
        bad["research_development"]["evidence_sha256"] = "0" * 64
        with pytest.raises(ValueError, match="current retained input"):
            service._development_computed_evidence(ws, record, bad)
        bad = copy.deepcopy(state)
        bad["research_development"]["evidence_versions"][-1]["checker_sha256"] = "0" * 64
        with pytest.raises(ValueError, match="current retained input"):
            service._development_computed_evidence(ws, record, bad)


def test_finished_candidate_layout_refresh_preserves_reviewed_versions_and_requests(development, monkeypatch):
    service, rid, _, _, evidence = development
    retain(service, rid, reserve(service, rid), plan_value(evidence))
    retain(service, rid, reserve(service, rid), evidence)
    retain(service, rid, reserve(service, rid), audit_value(current(service.status(rid)), evidence, False))
    task = reserve(service, rid)
    papers = [revision(service, rid, {**task, "venue_id": venue, "action_id": "develop-write-" + venue})
              for venue in current(service.status(rid))["versions"]]
    retain(service, rid, task, {"revisions": papers})
    task = reserve(service, rid)
    targets = current(service.status(rid))["research_development"]["write_versions"]
    retain(service, rid, task, {"assessments": [assessment({**task, "venue_id": venue,
        "manuscript_sha256": version["markdown_sha256"]}, 8) for venue, version in targets.items()]} )
    closed = service.finish_manuscript_improvement(rid)
    before = current(closed)
    binding = service._improvement_converter_binding
    import paper_factory.workflow as engine
    read = engine._read
    old_preflight_ids = {item["artifact_id"] for item in before["research_development"]["format_preflight"].values()}
    def missing_binding(ws, record, key):
        report = read(ws, record, key)
        if key in old_preflight_ids:
            report = {name: value for name, value in report.items() if name != "converter_binding"}
        return report
    monkeypatch.setattr(engine, "_read", missing_binding)
    refreshed = service.finish_manuscript_improvement(rid)
    after = current(refreshed)
    for field in ("calls", "versions", "reviews", "policy", "counts"):
        assert after[field] == before[field]
    for venue, previous in before["research_development"]["format_preflight"].items():
        replacement = after["research_development"]["format_preflight"][venue]
        assert replacement["artifact_id"] == previous["artifact_id"] + "-2"
        assert replacement["report"]["generation"] == 2
        assert replacement["report"]["scientific_markdown_sha256"] == targets[venue]["markdown_sha256"]
    for key, artifact in closed["artifacts"].items():
        assert refreshed["artifacts"][key] == artifact
        assert hashlib.sha256(service.artifact_path(rid, key).read_bytes()).hexdigest() == artifact["sha256"]
    assert service.finish_manuscript_improvement(rid)["manuscript_improvement_snapshot"] == refreshed["manuscript_improvement_snapshot"]
    monkeypatch.setattr(service, "_improvement_converter_binding", lambda venue: {**binding(venue), "layout_only_fixture": True})
    stale = service.finish_manuscript_improvement(rid)
    assert current(stale)["counts"] == before["counts"]
    assert all(item["report"]["generation"] == 3 for item in current(stale)["research_development"]["format_preflight"].values())
    monkeypatch.setattr(service, "_improvement_converter_binding", lambda venue: {**binding(venue), "layout_only_fixture": "second"})
    import paper_factory.journal_compliance as compliance
    monkeypatch.setattr(compliance, "prepare_editorial_markdown", lambda text, **kwargs: {"markdown": text + "Changed scientific body."})
    with pytest.raises(ValueError, match="Layout refresh cannot change"):
        service.finish_manuscript_improvement(rid)

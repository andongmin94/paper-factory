"""Current research contract generates products before exact independent audits."""
import copy
import hashlib
import json
import zipfile

import pytest

from test_research_development_workflow import (development, plan_value, audit_value,
    continuation, generated_evidence, study, unwritten_portfolio)
from test_manuscript_improvement import current, reserve, retain, revision, assessment
from paper_factory.autonomous.research_development import (
    DevelopmentResearchAudit, development_next_task, development_readiness, development_view)


def products(evidence):
    witness = evidence["source_evidence"][0]["id"]
    return {"products": [{"id": "source-choice", "kind": "source_comparison",
        "reader_decision": "Synthetic source-bound choice explicitly scoped to controller verification.",
        "shared_requirements": ["Both synthetic alternatives must retain the same explicit source boundary."],
        "common_conditions": ["Both alternatives inspect exactly the same frozen synthetic source witness."],
        "criteria": [{"id": "approval", "question": "Which explicit approval boundary is represented by the retained source?"}],
        "alternatives": [{"id": name, "label": "Synthetic " + name + " source comparison",
            "implementation_status": status, "evidence_ids": [witness],
            "implementation_steps": ["Explicitly synthetic source-bound " + name + " implementation step."],
            "costs": ["Any added proposed state remains an unimplemented engineering responsibility."],
            "applicability_conditions": ["These are bounded controller fixtures, not actual project findings."]}
            for name, status in [("existing", "retained_source"), ("proposed", "proposed_change")]],
        "observations": [{"id": name + "-observation", "alternative_id": name, "criterion_id": "approval",
            "observation": "Explicitly synthetic " + name + " interpretation, never actual project verification.",
            "evidence_ids": [witness]} for name in ("existing", "proposed")],
        "changed_decisions": [{"id": "explicit-contract", "condition": "The synthetic extension needs an explicit operation boundary.",
            "prior_method_evidence_ids": [], "baseline_decision": "Retain the source-bound eligibility boundary as observed.",
            "additional_analysis": "A proposed extra contract is separately identified and not asserted implemented.",
            "changed_decision": "Keep the proposal conditional rather than infer an implemented extra guarantee.",
            "support_ids": ["existing-observation", "proposed-observation"], "result_refs": [],
            "limitations": ["This is a synthetic transport test, not a temporal-protocol contribution or publication claim."]}],
        "limitations": ["No published-method novelty or actual implementation validation is established by this fixture."]}]}


def design(service, rid, evidence):
    task = reserve(service, rid)
    assert task["purpose"] == "develop-design" and task["phase"] == "quality-plan"
    value = copy.deepcopy(evidence)
    value["work_products"] = products(value)
    plan = plan_value(value)
    plan["inspect_source_files"] = task["inspected_source_files"]
    return retain(service, rid, task, {"plan": plan, "evidence": value}), value


def audit(state, evidence, repair=False, ready=True):
    value = audit_value(state, evidence, repair)
    value["ready_to_write"] = ready
    value["work_product_findings"] = [{"product_id": "source-choice",
        "verdict": "needs_repair" if repair else "faithful",
        "reason": "Synthetic independent inspection of the exact generated comparison dossier.",
        "required_repair": "Make the proposed scope explicit in the retained comparison." if repair else ""}]
    return value


@pytest.mark.parametrize("repair", [False, True])
@pytest.mark.parametrize("development", [2], indirect=True)
def test_current_design_products_reaudit_and_manuscripts_are_bounded_and_preserve_history(development, repair):
    service, rid, old, granted, evidence = development
    assert current(granted)["research_development"]["contract_version"] == 2
    result, value = design(service, rid, evidence)
    state = current(result)
    output = state["research_development"]
    report = output["work_product_report"]
    assert report["products"][0]["matrix"] and report["products"][0]["decision_table"]
    assert report["implementation_validated"] is False and report["publication_quality_assessed"] is False
    with zipfile.ZipFile(service.artifact_path(rid, output["supplement"]["artifact_id"])) as archive:
        for name in ("work-products.json", "work-product-report.json", "research-work-products.md", "research_workproducts.py"):
            assert name in archive.namelist()
        assert json.loads(archive.read("work-products.json")) == value["work_products"]
    task = reserve(service, rid)
    assert task["purpose"] == "develop-audit" and task["phase"] == "quality-review"
    assert '"work_product_report"' in task["prompt"] and "research_workproducts.py" in task["prompt"]
    result = retain(service, rid, task, audit(current(service.status(rid)), value, repair, not repair))
    if repair:
        task = reserve(service, rid)
        assert task["purpose"] == "develop-repair"
        value["work_products"]["products"][0]["observations"][1]["observation"] += " The audit-requested proposal scope is explicitly restricted."
        result = retain(service, rid, task, value)
        assert current(result)["research_development"]["readiness"]["ready_to_write"] is False
        task = reserve(service, rid)
        assert task["purpose"] == "develop-re-audit" and task["phase"] == "quality-review"
        stale = audit(current(result), value)
        stale["evidence_sha256"] = current(granted)["source_digest"]
        with service._operation(rid) as (ws, record):
            private = service._improvement_state(ws, record)
            with pytest.raises(ValueError, match="exact current evidence"):
                service._development_admit_audit(ws, record, private, stale, "never-read", purpose="develop-re-audit")
        result = retain(service, rid, task, audit(current(result), value))
    state = current(result)
    assert state["research_development"]["readiness"]["ready_to_write"]
    task = reserve(service, rid)
    assert task["purpose"] == "develop-write" and "work_product_report" in task["prompt"]
    papers = [revision(service, rid, {**task, "venue_id": venue, "action_id": "develop-write-" + venue}) for venue in state["versions"]]
    retain(service, rid, task, {"revisions": papers})
    task = reserve(service, rid)
    targets = current(service.status(rid))["research_development"]["write_versions"]
    retain(service, rid, task, {"assessments": [assessment({**task, "venue_id": venue,
        "manuscript_sha256": item["markdown_sha256"]}, 8) for venue, item in targets.items()]})
    final = service.finish_manuscript_improvement(rid)
    assert current(final)["research_development"]["status"] == "manuscripts_assessed"
    assert current(final)["counts"]["model_attempts"] - current(old)["counts"]["model_attempts"] == (6 if repair else 4)
    assert len(current(final)["research_development"]["audits"]) == (2 if repair else 1)
    for key, artifact in old["artifacts"].items():
        assert final["artifacts"][key] == artifact
        assert hashlib.sha256(service.artifact_path(rid, key).read_bytes()).hexdigest() == artifact["sha256"]
    assert service.grant_research_development_round(rid)["manuscript_improvement_snapshot"] == final["manuscript_improvement_snapshot"]


@pytest.mark.parametrize("development", [2], indirect=True)
def test_negative_method_audit_finishes_useful_research_without_claiming_manuscript_success(development):
    service, rid, _, _, evidence = development
    result, value = design(service, rid, evidence)
    task = reserve(service, rid)
    result = retain(service, rid, task, audit(current(result), value, ready=False))
    assert current(result)["next_task"] is None
    count = current(result)["counts"]["model_attempts"]
    final = current(service.finish_manuscript_improvement(rid))
    assert final["counts"]["model_attempts"] == count
    assert final["research_development"]["status"] == "bounded_research_report"
    assert final["research_development"]["stop_reason"] == "method_audit_not_ready_to_write"
    assert not final["research_development"].get("write_versions")
    assert final["research_development"]["work_product_report_artifact_id"]


def test_readiness_false_stale_required_repair_and_partial_review_never_become_completion():
    development = {"id": "new", "contract_version": 2, "closed": False, "additional_call_limit": 6,
        "completed_stages": ["design", "audit"], "evidence_artifact_id": "evidence", "evidence_sha256": "a" * 64,
        "work_product_report_artifact_id": "products", "audit_artifact_id": "audit", "audit_sha256": "b" * 64,
        "repair_required": False, "audit": {"evidence_sha256": "a" * 64, "ready_to_write": False, "repair_required": False}}
    state = {"finished": False, "policy": {"model_call_limit": 6}, "calls": [], "research_development": development}
    assert development_next_task(state) is None and not development_readiness(development)["ready_to_write"]
    development["audit"]["ready_to_write"] = True
    assert development_next_task(state)["purpose"] == "develop-write"
    development["evidence_sha256"] = "c" * 64
    assert development_next_task(state) is None
    development.update(completed_stages=["design", "audit", "write", "review"], write_versions={"one": {}, "two": {}}, assessed_venues=["one"])
    assert development_view(state)["status"] == "manuscripts_unassessed"
    legacy = {"contract_version": 1, "closed": True, "completed_stages": ["review"], "preserved": "literal"}
    assert development_view({"research_development": legacy}) == legacy


def test_ready_audit_cannot_hide_required_work_product_or_correspondence_repairs():
    base = {"evidence_sha256": "a" * 64, "correspondence": [{"case_id": "case", "alternative_id": "alt", "target_id": "rule",
        "verdict": "faithful", "reason": "Concrete evidence inspection is explicitly scoped to this fixture.", "required_repair": ""}],
        "repair_actions": [], "decisive_findings": ["A narrow useful paper can still follow an honest independent assessment."],
        "honest_limits": ["No implementation or empirical validation is inferred from native consistency."],
        "ready_to_write": True, "repair_required": False,
        "work_product_findings": [{"product_id": "product", "verdict": "faithful", "reason": "A complete source-bound generated product was inspected.", "required_repair": ""}]}
    DevelopmentResearchAudit.model_validate(base)
    for field in ("correspondence", "work_product_findings"):
        invalid = copy.deepcopy(base)
        invalid[field][0]["verdict"] = "needs_repair"
        with pytest.raises(ValueError, match="preclude ready_to_write"):
            DevelopmentResearchAudit.model_validate(invalid)


@pytest.mark.parametrize("development", [2], indirect=True)
def test_design_gaps_come_only_from_current_review_judgments_not_a_different_repository(development):
    service, rid, _, _, _ = development
    with service._operation(rid) as (ws, record):
        state = service._improvement_state(ws, record)
        expected = []
        for index, (venue, versions) in enumerate(state["versions"].items()):
            version = versions[-1]
            errors = [f"Synthetic unrelated repository concern {index}: generated documentation omits migration ownership."]
            review = assessment({"venue_id": venue, "manuscript_sha256": version["markdown_sha256"]}, 7, errors)
            state["reviews"][venue] = [review]
            expected.append({"venue_id": venue, "manuscript_sha256": version["markdown_sha256"], "essential_errors": errors})
        materials = service._development_materials(ws, record, state, "develop-design")
        assert materials["retained_review_method_gaps"] == expected
        assert "not verified repository facts" in materials["retained_review_method_gaps_scope"]
        assert "verified_method_gaps" not in materials
        assert all(set(item) == {"venue_id", "manuscript_sha256", "essential_errors"} for item in materials["retained_review_method_gaps"])
        state["reviews"] = {venue: [] for venue in state["versions"]}
        assert service._development_materials(ws, record, state, "develop-design")["retained_review_method_gaps"] == []

"""Synthetic submission and manuscript repair contracts; no real study is executed."""

import copy
import base64
import hashlib
import json

import pytest
from pydantic import ValidationError

from paper_factory import ipc
from paper_factory.autonomous import science
from paper_factory.autonomous.models import ManuscriptReview, ResearchPlan
from paper_factory.autonomous.submission import SubmissionContract, ValidationContract
from paper_factory.workflow import WorkflowError, _freeze, _validate_plan_submission, _verified_claim_validation
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import write_json
from test_workflow import (BUNDLE, REVIEW, STUDY_REVIEW, MANUSCRIPT_REVIEW, SYNTHETIC_PASSAGE,
                           SYNTHETIC_PREFIX, SYNTHETIC_SUFFIX, collect, collect_arxiv_preprint, finished,
                           manuscript as legacy_manuscript, prepare, protocol, setup)
from test_retained_primary_literature import preprint


def manuscript():
    original = legacy_manuscript()
    sections = {item["heading"]: item["text"] for item in original["sections"]}
    original["sections"] = [{"heading": heading, "text": sections.get(heading, sections["Experimental Setup"])}
                            for heading in science.FINITE_SECTIONS]
    next(item for item in original["sections"] if item["heading"] == "Method")["text"] += " Recorded instrumentation: {{parameter:setting.execution_instrumentation}}."
    return original


def contract():
    return {"article_type": "finite_enumeration", "language": "English",
            "target_audience": "Synthetic software experiment readers; no actual venue fit is claimed.",
            "core_claim": "Synthetic observed conclusions must remain tied to their retained evidence.",
            "claim_obligations": [{"id": "bounded-domain", "claim": "The declared finite domain must be completely represented by retained units.",
                                   "validation_mode": "finite_enumeration", "required_evidence": "Exact declared unit identities and preserved raw input bytes.",
                                   "importance": "This is a fixture requirement rather than an assertion of scholarly importance."}],
            "venue_candidates": [{"name": "Synthetic pending venue", "rationale": "A test suggestion with no verified journal requirements or suitability.",
                                  "official_requirements_status": "pending", "official_requirements": []}], "selected_venue": None}


def observed(*, outcome="negative"):
    return {"mode": "finite_enumeration", "claim": "The retained synthetic fixture comparisons establish only their observed bounded differences.",
            "scope": protocol()["research_claim"]["scope"], "outcome": outcome,
            "scope_justification": "The conclusion preserves the original synthetic domain and makes no population inference.",
            "analysis_keys": ["error.paired_2_minus_1.mean"], "fixture_labels": [], "proof_section": None, "proof_quote": None}


def assessment(claim=None, *, accepted=True):
    claim = claim or observed()
    review = copy.deepcopy(MANUSCRIPT_REVIEW)
    review["observed_claim"] = copy.deepcopy(claim)
    review["claim_scope"] = {"passed": True, "reason": "Synthetic independent scope assessment; no semantic or scholarly validity is attested."}
    review["publication_readiness"].update(claim=claim["claim"], scope=claim["scope"], evidence_mode=claim["mode"],
                                         analysis_keys=claim["analysis_keys"], fixture_labels=claim["fixture_labels"],
                                         proof_section=claim["proof_section"], proof_quote=claim["proof_quote"])
    if not accepted:
        review.update(accepted=False, issues=["Explain the actual bounded interpretation more clearly."])
        review["presentation"]["passed"] = False
        review["remediation"] = {"strategy": "revise_manuscript", "reason": "The retained measurements permit a precise presentation correction.",
                                 "actions": [{"criterion": "presentation", "action": "Explain the bounded comparison and its retained evidence in Discussion."}], "evidence_gaps": []}
    return review


def measured(setup):
    service, runner, identifier = setup
    prepare(service, identifier)
    service.start_experiment(identifier)  # The fixture runner emits simulated bytes only.
    assert finished(service, identifier)["stage"] == "analyzed"
    service.set_submission_contract(identifier, contract())
    return service, runner, identifier


def repair():
    return {"changes": [{"criterion": "presentation", "required_change": "Explain the bounded comparison and its retained evidence in Discussion.",
                         "actual_change": "Discussion now explains the bounded interpretation of the preserved paired comparison.",
                         "changed_sections": ["Discussion"], "evidence_sources": [], "unresolved": []}]}


def changed_draft():
    draft = manuscript()
    next(item for item in draft["sections"] if item["heading"] == "Discussion")["text"] += " The paired findings apply only to the preserved synthetic input domain."
    return draft


def test_contract_is_source_goal_bound_pending_immutable_and_idempotent(setup):
    service, runner, identifier = setup
    before = service.status(identifier)
    state = service.set_submission_contract(identifier, contract())
    assert state["submission_contract"]["bindings"]["research_id"] == identifier
    assert state["submission_readiness"]["ready"] is False
    assert state["submission_readiness"]["venue_verified"] is False
    assert state["proposal_attempt"] == state["execution_attempt"] == 0
    assert runner.calls == 0
    hashes = state["artifacts"]
    assert service.set_submission_contract(identifier, contract())["artifacts"] == hashes
    changed = contract()
    changed["core_claim"] += " Changed suggestion."
    with pytest.raises(WorkflowError, match="cannot be replaced"):
        service.set_submission_contract(identifier, changed)
    assert all(service.status(identifier)["artifacts"][key] == value for key, value in before["artifacts"].items())


@pytest.mark.parametrize("defect", ["verified", "selected", "requirements"])
def test_model_cannot_attest_official_venue_requirements(setup, defect):
    service, runner, identifier = setup
    value = contract()
    if defect == "verified":
        value["venue_candidates"][0]["official_requirements_status"] = "verified"
    elif defect == "selected":
        value["selected_venue"] = "Synthetic pending venue"
    else:
        value["venue_candidates"][0]["official_requirements"] = ["Invented rule without retained official evidence"]
    with pytest.raises(ValidationError):
        service.set_submission_contract(identifier, value)
    assert service.status(identifier)["submission_contract"] is None and runner.calls == 0


@pytest.mark.parametrize("state", ["control", "cleanup", "running", "cancelled"])
def test_unsafe_state_cannot_set_submission_target(setup, state):
    service, runner, identifier = setup
    ws = service._workspace(identifier)
    record = ws.get("workflow", identifier, Workflow)
    if state == "control":
        record.terminal_control_failure = True
    elif state == "cleanup":
        record.code = "CLEANUP_UNCONFIRMED"
    else:
        record.status = state
    ws.save("workflow", record)
    with pytest.raises(WorkflowError):
        service.set_submission_contract(identifier, contract())
    assert runner.calls == 0


def test_contract_tamper_and_goal_change_are_rejected(setup):
    service, runner, identifier = setup
    service.set_submission_contract(identifier, contract())
    ws = service._workspace(identifier)
    record = ws.get("workflow", identifier, Workflow)
    record.goal += " Changed original goal."
    ws.save("workflow", record)
    with pytest.raises(WorkflowError, match="original source and goal"):
        service.status(identifier)
    assert runner.calls == 0


@pytest.mark.parametrize("outcome", ["negative", "null", "positive", "mixed"])
def test_observed_conclusion_preserves_planned_hypothesis_and_is_separately_reviewed(setup, outcome):
    service, runner, identifier = measured(setup)
    before = service.status(identifier)
    value = observed(outcome=outcome)
    state = service.submit_manuscript(identifier, manuscript(), assessment(value), value)
    assert state["stage"] == "manuscript" and state["manuscript_claim"]["value"] == value
    assert state["artifacts"]["plan"] == before["artifacts"]["plan"]
    assert state["execution_attempt"] == 1 and runner.calls == 1
    assert state["submission_readiness"]["ready"] is False
    assert state["research_ledger"]["entries"][-1]["event"] in {"manuscript-review", "submission-contract"}


@pytest.mark.parametrize("defect", ["missing", "mode", "scope", "review_claim", "result", "fixture", "readiness", "scope_review"])
def test_observed_claim_cannot_expand_scope_or_reuse_another_assessment(setup, defect):
    service, runner, identifier = measured(setup)
    value = observed()
    review = assessment(value)
    if defect == "missing":
        value = None
    elif defect == "mode":
        value["mode"] = "empirical"
        review = assessment(value)
    elif defect == "scope":
        value["scope"] = "All real populations, fonts, browsers and production applications are covered."
        review = assessment(value)
        review["claim_scope"] = {"passed": False, "reason": "This expanded population claim exceeds the actual preserved synthetic fixture evidence."}
    elif defect == "review_claim":
        review["observed_claim"]["claim"] += " Changed conclusion."
    elif defect == "result":
        value["analysis_keys"] = ["missing-result"]
        review = assessment(value)
    elif defect == "fixture":
        value["fixture_labels"] = ["missing-fixture"]
        review = assessment(value)
    elif defect == "readiness":
        review["publication_readiness"]["claim"] = protocol()["research_claim"]["claim"]
    else:
        review.pop("claim_scope")
    before = service.status(identifier)["artifacts"]
    with pytest.raises((WorkflowError, ValidationError)):
        service.submit_manuscript(identifier, manuscript(), review, value)
    assert service.status(identifier)["artifacts"] == before and runner.calls == 1


def test_repair_covers_original_requirements_and_freezes_actual_changes(setup):
    service, runner, identifier = measured(setup)
    first = service.submit_manuscript(identifier, manuscript(), assessment(accepted=False), observed())
    prior = {key: value for key, value in first["artifacts"].items() if key in {"draft-1", "manuscript-review-1", "manuscript-claim-1"}}
    state = service.submit_manuscript(identifier, changed_draft(), assessment(), observed(), repair())
    assert state["manuscript_repair"]["actual_changed_sections"] == ["Discussion"]
    assert state["artifacts"]["manuscript-review"]["sha256"] != prior["manuscript-review-1"]["sha256"]
    assert all(state["artifacts"][key] == value for key, value in prior.items())
    assert state["execution_attempt"] == 1 and state["draft_attempt"] == 2 and runner.calls == 1
    assert any(entry["event"] == "manuscript-repair" for entry in state["research_ledger"]["entries"])


@pytest.mark.parametrize("defect", ["missing", "coverage", "required", "section", "evidence", "unresolved", "unchanged"])
def test_fabricated_or_incomplete_repairs_cannot_request_approval(setup, defect):
    service, runner, identifier = measured(setup)
    service.submit_manuscript(identifier, manuscript(), assessment(accepted=False), observed())
    value = repair()
    draft = changed_draft()
    if defect == "missing":
        value = None
    elif defect == "coverage":
        value["changes"][0]["criterion"] = "interpretation"
    elif defect == "required":
        value["changes"][0]["required_change"] += " Altered prior requirement."
    elif defect == "section":
        value["changes"][0]["changed_sections"] = ["Results"]
    elif defect == "evidence":
        value["changes"][0]["evidence_sources"] = ["invented-primary"]
    elif defect == "unresolved":
        value["changes"][0]["unresolved"] = ["The required comparison remains unexplained."]
    else:
        draft = manuscript()
    before = service.status(identifier)["artifacts"]
    with pytest.raises(WorkflowError):
        service.submit_manuscript(identifier, draft, assessment(), observed(), value)
    assert service.status(identifier)["artifacts"] == before and runner.calls == 1


def test_authoring_collection_reuses_current_queries_and_denies_prior_repetition(setup):
    service, runner, identifier = measured(setup)
    first = service.collect_authoring_literature(identifier, ["synthetic first authoring query"])
    assert service.collect_authoring_literature(identifier, ["synthetic first authoring query"])["artifacts"] == first["artifacts"]
    service.collect_authoring_literature(identifier, ["synthetic second authoring query"])
    with pytest.raises(WorkflowError, match="repeated queries"):
        service.collect_authoring_literature(identifier, ["synthetic first authoring query"])
    third = service.collect_authoring_literature(identifier, ["synthetic third authoring query"])
    assert third["authoring_literature_available"] is False
    with pytest.raises(WorkflowError, match="at most three"):
        service.collect_authoring_literature(identifier, ["synthetic fourth authoring query"])
    assert runner.calls == 1 and third["execution_attempt"] == 1


def test_new_ipc_contract_accepts_bound_inputs_and_rejects_extra_scientific_injection():
    identifier = "research-0123456789ab"
    for method, params in (("workflow.setSubmissionContract", {"researchId": identifier, "value": contract()}),
                           ("workflow.submitManuscript", {"researchId": identifier, "value": manuscript(), "review": assessment(), "claim": observed(), "repair": repair()})):
        assert ipc.request(json.dumps({"id": "fixture", "method": method, "params": params}).encode())["params"] == params
        params["oracle"] = "Manually injected expected observations"
        with pytest.raises(ValueError):
            ipc.request(json.dumps({"id": "fixture", "method": method, "params": params}).encode())


def test_historical_serializer_preserves_absent_new_contract_fields():
    value = protocol()
    assert ResearchPlan.model_validate(value).model_dump(mode="json") == value
    assert ManuscriptReview.model_validate(MANUSCRIPT_REVIEW).model_dump(mode="json") == MANUSCRIPT_REVIEW


def validation_spec():
    return {"mode": "finite_enumeration", "declared_units": [{"seed": seed, "unit_id": f"case-{index}", "stratum": "synthetic"}
             for seed in (11, 37) for index in range(3)], "finite_domain_label": "domain.json", "uncertainty": "none",
            "independent_sampling": False, "sampling_basis": "A fixed synthetic declared domain establishes no population sampling.",
            "bootstrap_seed": 17, "bootstrap_replicates": 200, "confidence_level": .95,
            "oracle_sources": [{"source_id": "source-" + hashlib.sha256(b"arxiv:1311.3903v1").hexdigest()[:20],
                "text_sha256": hashlib.sha256((SYNTHETIC_PREFIX + SYNTHETIC_PASSAGE + SYNTHETIC_SUFFIX).encode()).hexdigest(),
                "quote": SYNTHETIC_PASSAGE[:150]}]}


def fixture(label, raw):
    return {"label": label, "encoding": "base64", "content": base64.b64encode(raw).decode(), "sha256": hashlib.sha256(raw).hexdigest()}


def validated_study(setup):
    service, runner, identifier = setup
    plan = protocol()
    plan["validation_contract"] = validation_spec()
    service.collector = collect_arxiv_preprint
    service.submit_proposal(identifier, plan)
    collected = service.collect_literature(identifier)
    source_id = collected["literature"]["sources"][0]["id"]
    review = copy.deepcopy(STUDY_REVIEW)
    review["selected_sources"][0]["source_id"] = source_id
    review["publication_readiness"]["closest_work"][0]["source_id"] = source_id
    service.submit_study_review(identifier, review)
    service.submit_code(identifier, BUNDLE, REVIEW)
    raw = runner.outputs
    raw["fixtures"] += [fixture("domain.json", json.dumps(plan["validation_contract"]["declared_units"]).encode()),
        fixture("expected.json", b'{"synthetic_expected":true}'), fixture("positive.json", b'{"synthetic_expected":true}'),
        fixture("negative.json", b'{"synthetic_expected":false}')]
    for control, actual, comparison in zip(raw["controls"], ("positive.json", "negative.json"), ("equal", "different")):
        control.update(input_fixture="synthetic-inputs.json", expected_fixture="expected.json", actual_fixture=actual, comparison=comparison)
    return service, runner, identifier, source_id


def test_new_contract_requires_validation_without_spending_proposal_attempt(setup):
    service, runner, identifier = setup
    service.set_submission_contract(identifier, contract())
    with pytest.raises(WorkflowError) as error:
        service.submit_proposal(identifier, protocol())
    assert error.value.code == "VALIDATION_CONTRACT_REQUIRED"
    assert service.status(identifier)["proposal_attempt"] == 0 and runner.calls == 0


@pytest.mark.parametrize("route", ["formal", "insufficient_seed_clusters"])
def test_known_unsupported_validation_is_held_before_proposal_or_execution(setup, route):
    service, runner, identifier = setup
    plan = protocol()
    plan["validation_contract"] = validation_spec()
    if route == "formal":
        plan["research_claim"]["mode"] = "formal"
        plan["validation_contract"].update(mode="formal", finite_domain_label=None)
    else:
        plan["research_claim"]["mode"] = "empirical"
        plan["validation_contract"].update(mode="empirical", finite_domain_label=None, uncertainty="seed_cluster_bootstrap", independent_sampling=True)
    with pytest.raises(WorkflowError) as error:
        service.submit_proposal(identifier, plan)
    assert error.value.code == "VALIDATION_UNSUPPORTED"
    state = service.status(identifier)
    assert state["proposal_attempt"] == state["execution_attempt"] == runner.calls == 0


def test_new_formal_target_cannot_promote_historical_literal_proof_to_verified_submission(setup):
    service, runner, identifier = setup
    plan = protocol()
    plan["research_claim"]["mode"] = "formal"
    study = copy.deepcopy(STUDY_REVIEW)
    study["publication_readiness"]["evidence_mode"] = "formal"
    service.submit_proposal(identifier, plan)
    service.collect_literature(identifier)
    service.submit_study_review(identifier, study)
    service.submit_code(identifier, BUNDLE, REVIEW)
    service.start_experiment(identifier)
    assert finished(service, identifier)["stage"] == "analyzed"
    target = contract()
    target["article_type"] = target["claim_obligations"][0]["validation_mode"] = "formal"
    service.set_submission_contract(identifier, target)
    draft = manuscript()
    value = observed()
    value.update(mode="formal", analysis_keys=[], proof_section="Method",
                 proof_quote=next(section["text"] for section in draft["sections"] if section["heading"] == "Method")[:150])
    before = service.status(identifier)
    with pytest.raises(WorkflowError) as error:
        service.submit_manuscript(identifier, draft, assessment(value), value)
    assert error.value.code == "VALIDATION_UNSUPPORTED"
    result = service.status(identifier)
    assert result["artifacts"] == before["artifacts"] and result["draft_attempt"] == 0
    assert result["execution_attempt"] == runner.calls == 1


def test_typed_submission_instructions_use_finite_headings_after_analysis(setup):
    service, runner, identifier = measured(setup)
    instructions = service.status(identifier)["instructions"]
    assert "Use exactly these headings: " + ", ".join(science.FINITE_SECTIONS) in instructions
    assert runner.calls == 1


def test_rephrased_narrow_observed_scope_requires_fresh_exact_independent_assessment(setup):
    service, runner, identifier = measured(setup)
    before = service.status(identifier)
    value = observed()
    value["scope"] = "Only the two retained seed blocks and their three preserved synthetic input units; no unseen domain is inferred."
    review = assessment(value)
    result = service.submit_manuscript(identifier, manuscript(), review, value)
    assert result["manuscript_claim"]["value"] == value and result["stage"] == "manuscript"
    assert result["artifacts"]["plan"] == before["artifacts"]["plan"] and runner.calls == result["execution_attempt"] == 1


def test_native_validation_cell_is_an_evidence_linked_manuscript_result(setup):
    service, runner, identifier, source_id = validated_study(setup)
    service.start_experiment(identifier)
    state = finished(service, identifier)
    assert "validation.cell_1.mean" in state["analysis"]["results"]
    service.set_submission_contract(identifier, contract())
    value = observed()
    value["analysis_keys"] = ["validation.cell_1.mean"]
    review = assessment(value)
    review["publication_readiness"]["closest_work"][0]["source_id"] = source_id
    draft = manuscript()
    for section in draft["sections"]:
        section["text"] = section["text"].replace("{{citation:fixture-oracle}}", "{{citation:" + source_id + "}}")
        for original, replacement in (("error.condition_1", "validation.cell_1"), ("error.condition_2", "validation.cell_2"),
                                      ("error.paired_2_minus_1", "validation.cell_3")):
            section["text"] = section["text"].replace(original, replacement)
        if section["heading"] in {"Abstract", "Results"}:
            section["text"] += " Native declared stratum mean: {{result:validation.cell_1.mean}}."
    result = service.submit_manuscript(identifier, draft, review, value)
    canonical = json.loads(service.artifact_path(identifier, "canonical").read_bytes())
    assert "validation.cell_1.mean" in canonical["verified_result_refs"]["Results"] and result["execution_attempt"] == runner.calls == 1


@pytest.mark.parametrize("defect", ["source", "hash", "quote", "seed", "units"])
def test_oracle_sources_and_unit_declarations_are_independently_bound(setup, defect):
    service, runner, identifier = setup
    preprint(service, identifier)
    plan = protocol()
    spec = validation_spec()
    if defect == "source":
        spec["oracle_sources"][0]["source_id"] = "invented-primary"
    elif defect == "hash":
        spec["oracle_sources"][0]["text_sha256"] = "0" * 64
    elif defect == "quote":
        spec["oracle_sources"][0]["quote"] = "Invented independent reference content never appeared in the actual retained primary body. " * 2
    elif defect == "seed":
        spec["declared_units"][0]["seed"] = 91
    else:
        spec["declared_units"][0]["unit_id"] = spec["declared_units"][1]["unit_id"]
    plan["validation_contract"] = spec
    with pytest.raises((WorkflowError, ValidationError)):
        _validate_plan_submission(service._workspace(identifier), service._workspace(identifier).get("workflow", identifier, Workflow), ResearchPlan.model_validate(plan), verify_oracles=True)
    assert service.status(identifier)["execution_attempt"] == 0 and runner.calls == 0


def test_declared_domain_and_controls_produce_a_separate_recomputable_receipt(setup):
    service, runner, identifier, source_id = validated_study(setup)
    service.start_experiment(identifier)
    state = finished(service, identifier)
    receipt = state["claim_validation"]
    assert receipt["value"]["supported"] is True and receipt["value"]["passed"] is True
    assert receipt["value"]["complete_declared_domain"] is True
    assert receipt["value"]["uncertainty"] == []
    ws = service._workspace(identifier)
    record = ws.get("workflow", identifier, Workflow)
    assert _verified_claim_validation(ws, record, ResearchPlan.model_validate(state["plan"])) == receipt
    service.set_submission_contract(identifier, contract())
    value = observed()
    value["analysis_keys"] = ["validation.cell_3.mean"]
    review = assessment(value)
    review["publication_readiness"]["closest_work"][0]["source_id"] = source_id
    draft = manuscript()
    for section in draft["sections"]:
        section["text"] = section["text"].replace("{{citation:fixture-oracle}}", "{{citation:" + source_id + "}}")
        for original, replacement in (("error.condition_1", "validation.cell_1"), ("error.condition_2", "validation.cell_2"),
                                      ("error.paired_2_minus_1", "validation.cell_3")):
            section["text"] = section["text"].replace(original, replacement)
    result = service.submit_manuscript(identifier, draft, review, value)
    assert result["execution_attempt"] == runner.calls == 1


def test_rebound_validation_receipt_cannot_invent_verified_support(setup):
    service, runner, identifier, _ = validated_study(setup)
    service.start_experiment(identifier)
    state = finished(service, identifier)
    ws = service._workspace(identifier)
    record = ws.get("workflow", identifier, Workflow)
    path = service.artifact_path(identifier, "claim-validation")
    value = json.loads(path.read_bytes())
    value["value"]["scope"] = "A forged declaration of universal scientific validation."
    path.chmod(0o600)
    write_json(path, value)
    _freeze(ws, record, "claim-validation", path)
    ws.save("workflow", record)
    with pytest.raises(WorkflowError, match="exact declared protocol"):
        _verified_claim_validation(ws, record, ResearchPlan.model_validate(state["plan"]))
    assert runner.calls == 1


def test_false_structured_control_is_terminal_without_retry(setup):
    service, runner, identifier, _ = validated_study(setup)
    runner.outputs["controls"][0]["actual_fixture"] = "negative.json"
    service.start_experiment(identifier)
    state = finished(service, identifier)
    assert state["terminal_control_failure"] is True and state["code"] == "CONTROL_FAILED"
    with pytest.raises(WorkflowError):
        service.start_experiment(identifier)
    assert state["execution_attempt"] == runner.calls == 1

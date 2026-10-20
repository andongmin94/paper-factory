"""Bounded continuation tests use explicit synthetic prose, not actual research claims."""

import copy
import hashlib
import json
from uuid import uuid4

import pytest

from paper_factory.autonomous.manuscript_improvement import (
    CRITERIA, IndependentAssessment, ManuscriptRevision, best_assessment, improvement_view,
    next_task, path_stopped, target_achieved, canonical_quality_revision)
from paper_factory.workflow import WorkflowError
from test_repository_paper_workflow import study, draft
from test_repository_portfolio import unwritten_portfolio, analyze_portfolio, retain_portfolio_response


@pytest.fixture
def continuation(unwritten_portfolio, monkeypatch):
    service, rid, _ = unwritten_portfolio
    # These fixtures deliberately produce non-document bytes. Native Word and
    # publisher compliance have their own real-document test suite.
    monkeypatch.setattr(service, "_improvement_export_compliance", lambda *args, **kwargs: {
        "content_format_passed": True, "submission_ready": False, "blockers": [],
        "pending": [{"id": "synthetic_fixture", "reason": "Explicit synthetic controller test, not publisher approval"}]})
    monkeypatch.setattr(service, "_improvement_converter_binding", lambda venue: {"synthetic_binding": "stable"})
    analyzed = analyze_portfolio(service, rid)
    for target in analyzed["repository_paper"]["portfolio"]["targets"]:
        manuscript = draft(service, rid, prepare_analysis=False)
        key, _ = retain_portfolio_response(service, rid, manuscript, "venue-manuscript", target["venue_id"])
        service.submit_portfolio_manuscript(rid, {"venue_id": target["venue_id"], "inference_artifact_id": key, "manuscript": manuscript})
    before = service.status(rid)
    started = service.start_manuscript_improvement(rid)
    return service, rid, before, started


def current(status):
    return status["repository_paper"]["manuscript_improvement"]


def reserve(service, rid):
    descriptor = current(service.status(rid))["next_task"]
    return service.reserve_manuscript_improvement(rid, {"call_id": str(uuid4()), **descriptor})["task"]


def retain(service, rid, task, value=None, outcome="completed", raw=None):
    receipt = {"id": task["call_id"], "phase": task["phase"], "at": "2026-10-18T00:00:00+00:00",
        "model": "explicit-synthetic-test-model", "profileId": "fixture-profile", "prompt": task["prompt"],
        "promptSha256": hashlib.sha256(task["prompt"].encode()).hexdigest(), "outcome": "started"}
    service.record_inference(rid, receipt)
    final = {**receipt, "outcome": outcome}
    if outcome == "completed":
        text = json.dumps(value) if raw is None else raw
        final.update(text=text, textSha256=hashlib.sha256(text.encode()).hexdigest())
    else:
        final["code"] = "SYNTHETIC_FAILURE"
    retained = service.record_inference(rid, final)
    return service.submit_manuscript_improvement(rid, retained["artifactId"])


def assessment(task, score=6, essential_errors=None):
    passage = "The synthetic article's stated configuration source observation."
    if task.get("prompt"):
        material = json.loads(task["prompt"].split("\n")[-1])["materials"]
        passage = material["manuscripts"][task["venue_id"]]["markdown"][:100]
    return {"venue_id": task["venue_id"], "manuscript_sha256": task["manuscript_sha256"],
        "scores": [{"criterion": name, "score": score, "uncertainty": "medium",
            "passages": [passage],
            "reason": "This fixture does not assert that the article has any actual publication merit.",
            "required_improvement": "Add a substantive supported decision example."} for name in CRITERIA],
        "essential_errors": essential_errors or [], "recommendation": "revise_before_submission",
        "recommendation_reason": "Synthetic assessment only; actual publication merit remains unestablished.",
        "evidence_limits": []}


def improvement_plan():
    return {"directions": [{"id": identifier, "reader_problem": "Configuration choices need an inspectable boundary.",
        "added_value": "Show a concrete decision rather than rephrase implementation.",
        "closest_baseline": "Existing guidance already recommends explicit configuration.",
        "available_evidence": "The frozen tool source and README can support static examples.",
        "missing_evidence": "No deployment or runtime outcome is available in this fixture.",
        "selection_reason": "This is a synthetic comparison, never a journal suitability claim."}
        for identifier in ("operational-boundary", "configuration-guide")],
        "selected_direction_id": "operational-boundary",
        "actions": [{"id": "improve-" + venue, "venue_id": venue, "criterion": "contribution", "kind": "revise_analysis",
            "required_change": "Develop a source-bound concrete configuration counterexample.",
            "completion_condition": "The manuscript includes an inspected source-supported decision example.",
            "evidence_gain": "New reasoning connects the retained source to a bounded concrete decision.",
            "expected_gain": 7, "estimated_cost": 3, "success_likelihood": "medium"}
            for venue in ("ieee-software", "ieee-security-privacy")],
        "inspect_source_files": ["tool.js", "README.md"], "reference_selection": None,
        "scope_and_limits": "Only bounded source analysis is authorized; this fixture does not run project code."}


def revision(service, rid, task):
    status = current(service.status(rid))
    previous = status["versions"][task["venue_id"]][-1]
    saved = json.loads(service.artifact_path(rid, previous["draft_artifact_id"]).read_text(encoding="utf-8"))
    manuscript = copy.deepcopy(saved["value"])
    manuscript["sections"][1]["text"] += " A synthetic additional decision case distinguishes declared configuration from a caller's interpretation."
    manuscript["revision"] = {"prior_draft_sha256": previous["draft_sha256"],
        "changes": ["Added a source-bound synthetic decision example for the bounded fixture."]}
    return {"venue_id": task["venue_id"], "action_id": task["action_id"], "manuscript": manuscript,
        "contributions": [{"claim": "A source-bound configuration decision is presented as a synthetic example.",
            "baseline": "The baseline already documents a configuration transformation.",
            "additional_decision_value": "A caller can distinguish a declared option from an unverified outcome.",
            "evidence_ids": ["configuration"],
            "counterexample_or_failure_condition": "Downstream code may interpret the returned option differently.",
            "applicability_limit": "This example is static and has no measured deployment support."}],
        "actual_work": ["Constructed a synthetic source-grounded decision example; no project execution occurred."],
        "evidence_limits": []}


def test_full_bounded_continuation_preserves_old_bytes_counts_and_selects_best(continuation, monkeypatch):
    service, rid, before, _ = continuation
    for _ in range(2):
        task = reserve(service, rid)
        assert task["purpose"] == "review"
        assert "prior_assessments" not in task["prompt"]
        assert '"improvement_plan"' not in task["prompt"]
        retain(service, rid, task, assessment(task, 7))
    task = reserve(service, rid)
    assert task["purpose"] == "plan"
    retain(service, rid, task, improvement_plan())
    visited = []
    for _ in range(2):
        task = reserve(service, rid)
        assert task["purpose"] == "revise"
        visited.append(task["venue_id"])
        retain(service, rid, task, revision(service, rid, task))
        task = reserve(service, rid)
        assert task["purpose"] == "review"
        retain(service, rid, task, assessment(task, 6))
    assert len(set(visited)) == 2
    state = current(service.status(rid))
    assert state["counts"] == {"model_attempts": 7, "actions": 2, "reviews": 4, "revisions": 2, "format_repairs": 0}
    assert state["next_task"] is None and not state["target_achieved"]
    assert state["stop_reason"] == "planned_actions_completed"

    def convert(source, output, *, venue_id):
        output.write_bytes(b"Explicitly synthetic official-template fixture; " + venue_id.encode())
        return {"input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "engine": "synthetic-fixture"}

    monkeypatch.setattr("paper_factory.conversion.convert", convert)
    finished = service.finish_manuscript_improvement(rid)
    final = current(finished)
    assert final["finished"] and not final["target_achieved"]
    assert all(item["selected_version"]["origin"] == "preserved_baseline" for item in final["exports"].values())
    assert all(set(item["outputs"]) == {"markdown", "docx", "pdf"} for item in final["exports"].values())
    assert {name: finished[name] for name in ("proposal_attempt", "draft_attempt", "execution_attempt")} == {
        name: before[name] for name in ("proposal_attempt", "draft_attempt", "execution_attempt")}
    for key, artifact in before["artifacts"].items():
        assert finished["artifacts"][key] == artifact
        assert hashlib.sha256(service.artifact_path(rid, key).read_bytes()).hexdigest() == artifact["sha256"]
    assert current(service.start_manuscript_improvement(rid))["counts"] == final["counts"]


def test_rejected_and_failed_calls_consume_budget_without_score_reroll(continuation):
    service, rid, _, _ = continuation
    first = reserve(service, rid)
    state = retain(service, rid, first, raw="not valid JSON")
    assert current(state)["calls"][0]["outcome"] == "rejected"
    second = reserve(service, rid)
    assert second["venue_id"] != first["venue_id"]
    state = retain(service, rid, second, outcome="failed")
    assert current(state)["counts"]["model_attempts"] == 2
    assert current(state)["next_task"]["purpose"] == "plan"
    with pytest.raises(WorkflowError, match="outside the fixed native sequence"):
        service.reserve_manuscript_improvement(rid, {"call_id": str(uuid4()), "purpose": "review",
            "venue_id": first["venue_id"], "manuscript_sha256": first["manuscript_sha256"]})


def test_frozen_reservation_requires_exact_prompt_and_original_receipt(continuation):
    service, rid, _, _ = continuation
    task = reserve(service, rid)
    wrong_prompt = task["prompt"] + " changed"
    with pytest.raises(WorkflowError, match="exact frozen native reservation"):
        service.record_inference(rid, {"id": task["call_id"], "phase": task["phase"],
            "at": "2026-10-18T00:00:00+00:00", "model": "synthetic", "profileId": "fixture",
            "prompt": wrong_prompt, "promptSha256": hashlib.sha256(wrong_prompt.encode()).hexdigest(), "outcome": "started"})
    assert current(service.status(rid))["counts"]["model_attempts"] == 1


def test_essential_defects_beat_optimistic_average_and_target_is_separate():
    task = {"venue_id": "ieee-software", "manuscript_sha256": "a" * 64}
    safe, unsafe = assessment(task, 7), assessment(task, 10, ["A central claim contradicts its cited frozen source."])
    assert best_assessment([unsafe, safe]) == safe
    assert not target_achieved(unsafe)
    all_nine = assessment(task, 9)
    assert not target_achieved(all_nine)
    assert all_nine["recommendation"] == "revise_before_submission"
    all_nine["recommendation"] = "consider_submission"
    assert target_achieved(all_nine)
    duplicate = copy.deepcopy(all_nine)
    duplicate["scores"][-1] = duplicate["scores"][0]
    with pytest.raises(ValueError, match="exactly once"):
        IndependentAssessment.model_validate(duplicate)


def test_same_path_two_no_progress_stops_path_but_global_budget_still_applies():
    assert path_stopped([{"path": "revise_analysis:contribution", "completed": True, "material_progress": False}] * 2,
                        "revise_analysis:contribution")
    assert not path_stopped([{"path": "revise_analysis:contribution", "completed": True, "material_progress": False},
                             {"path": "revise_analysis:contribution", "completed": True, "material_progress": True}],
                            "revise_analysis:contribution")


def test_a_writer_is_not_started_without_budget_for_its_reviewer(continuation):
    service, rid, _, started = continuation
    state = current(started)
    state["plan"] = improvement_plan()
    for venue, versions in state["versions"].items():
        task = {"venue_id": venue, "manuscript_sha256": versions[0]["markdown_sha256"]}
        state["reviews"][venue].append(assessment(task))
    state["calls"] = [{"outcome": "failed", "purpose": "plan", "venue_id": None}] * 7
    assert next_task(state) is None
    assert improvement_view(state)["stop_reason"] == "budget_exhausted"


def test_invented_review_passage_is_rejected_and_the_same_article_is_not_rescored(continuation):
    service, rid, _, _ = continuation
    task = reserve(service, rid)
    value = assessment(task)
    value["scores"][0]["passages"] = ["This invented passage does not occur anywhere in the synthetic article."]
    status = retain(service, rid, task, value)
    state = current(status)
    assert state["reviews"][task["venue_id"]] == []
    assert state["calls"][0]["outcome"] == "rejected"
    assert "literal quotations" in state["calls"][0]["error"]
    assert state["next_task"]["venue_id"] != task["venue_id"]


def test_one_bounded_acquisition_retains_success_and_access_failure_separately(continuation, monkeypatch):
    service, rid, _, _ = continuation
    for _ in range(2):
        task = reserve(service, rid)
        retain(service, rid, task, assessment(task))
    fetched = []

    def fetch(url):
        fetched.append(url)
        if "blocked" in url:
            return {"status": "failed", "raw": b"Retained synthetic denial", "http_status": 403,
                    "content_type": "text/plain", "error": "Explicit synthetic access refusal"}
        return {"status": "retained", "raw": ("Synthetic source contract only; this is not an actual API document. " * 20).encode(),
                "http_status": 200, "content_type": "text/plain", "error": None}

    monkeypatch.setattr("paper_factory.submission_requirements.fetch_requirements", fetch)
    plan = improvement_plan()
    plan["reference_selection"] = {"references": [{"url": url, "purpose": "comparison",
        "reason": "Inspect an exact primary contract instead of assuming an unverified API behavior."}
        for url in ("https://example.org/contract", "https://example.org/blocked")], "venue_suggestions": []}
    task = reserve(service, rid)
    state = current(retain(service, rid, task, plan))
    assert len(fetched) == 2 and state["evidence_collection"]["collection_count"] == 1
    first, second = state["evidence_collection"]["sources"]
    assert first["status"] == "retained" and second["status"] == "failed"
    assert "access refusal" in second["failure"]
    task = reserve(service, rid)
    assert "Synthetic source contract only" in task["prompt"]
    assert "quality-document-1" in task["prompt"]
    assert current(service.start_manuscript_improvement(rid))["counts"]["model_attempts"] == 4


def test_finish_resumes_verified_first_format_after_interruption_without_overwrite(continuation, monkeypatch):
    service, rid, _, _ = continuation
    for _ in range(2):
        task = reserve(service, rid)
        review = assessment(task, 9)
        review["recommendation"] = "consider_submission"
        retain(service, rid, task, review)
    assert current(service.status(rid))["next_task"] is None
    converted = []
    interrupted = False

    def convert(source, output, *, venue_id):
        nonlocal interrupted
        converted.append((venue_id, output.suffix))
        if output.suffix == ".pdf" and not interrupted:
            interrupted = True
            raise KeyboardInterrupt("Explicit synthetic process interruption before creating a PDF")
        output.write_bytes(b"Synthetic conversion bytes, never an actual publication file.")
        return {"input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "engine": "synthetic-fixture"}

    monkeypatch.setattr("paper_factory.conversion.convert", convert)
    with pytest.raises(KeyboardInterrupt):
        service.finish_manuscript_improvement(rid)
    partial = current(service.status(rid))
    assert not partial["finished"]
    assert set(next(iter(partial["exports"].values()))["outputs"]) == {"markdown", "docx"}
    final = current(service.finish_manuscript_improvement(rid))
    assert final["finished"] and final["target_achieved"]
    first_venue = next(iter(final["versions"]))
    assert converted.count((first_venue, ".docx")) == 1
    assert all(set(item["outputs"]) == {"markdown", "docx", "pdf"} for item in final["exports"].values())
    assert final["report_artifact_id"] == "manuscript-improvement-quality-report"


def test_bibliography_only_repair_reuses_completed_writer_and_preserves_failed_call(continuation, monkeypatch):
    service, rid, _, _ = continuation
    for _ in range(2):
        task = reserve(service, rid)
        retain(service, rid, task, assessment(task))
    task = reserve(service, rid)
    retain(service, rid, task, improvement_plan())
    task = reserve(service, rid)
    value = revision(service, rid, task)
    value["manuscript"]["sections"].append({"heading": "References", "text":
        "[R1] Synthetic fixture repository metadata. {{citation:R1}} "
        "Citation identifiers refer to the metadata entries rather than an actual inspected scholarly source."})
    with monkeypatch.context() as patch:
        # Preserve an actual pre-fix controller rejection; no fake SDK response is added by repair.
        patch.setattr("paper_factory.autonomous.manuscript_improvement_workflow.canonical_quality_revision",
                      lambda item: (ManuscriptRevision.model_validate(item), None))
        status = retain(service, rid, task, value)
    rejected = current(status)["calls"][-1]
    assert rejected["outcome"] == "rejected"
    assert rejected["error"] == "Model References contain non-bibliographic or ambiguous prose"
    model_artifacts = {key: item for key, item in status["artifacts"].items() if key.startswith(("model-evidence-", "model-journal-"))}
    repaired = service.repair_manuscript_improvement(rid)
    state = current(repaired)
    assert state["counts"]["model_attempts"] == 4
    assert state["counts"]["format_repairs"] == 1 and state["counts"]["revisions"] == 1
    assert state["calls"][-1]["outcome"] == "rejected" and state["calls"][-1]["error"] == rejected["error"]
    version = state["versions"][task["venue_id"]][-1]
    normalized = json.loads(service.artifact_path(rid, version["draft_artifact_id"]).read_text(encoding="utf-8"))
    assert normalized["value"]["sections"] == value["manuscript"]["sections"][:-1]
    assert normalized["bibliography_normalization"]["kind"] == "controller_owned_bibliography"
    for key, item in model_artifacts.items():
        assert repaired["artifacts"][key] == item
    repeated = service.repair_manuscript_improvement(rid)
    assert repeated["manuscript_improvement_snapshot"] == repaired["manuscript_improvement_snapshot"]


def test_quality_resume_consumes_undispatched_reservation_without_fabricating_model_receipts(continuation):
    service, rid, _, _ = continuation
    task = reserve(service, rid)
    before = service.status(rid)
    assert not any(key.startswith("model-evidence-" + task["call_id"]) for key in before["artifacts"])
    service.cancel(rid)
    resumed = service.start_manuscript_improvement(rid)
    state = current(resumed)
    assert resumed["status"] == "ready" and not resumed["cancellation_requested"]
    assert state["counts"]["model_attempts"] == 1
    assert state["calls"][0]["outcome"] == "interrupted"
    assert state["calls"][0]["dispatch_status"] == "cancelled_before_dispatch"
    assert not any(key.startswith("model-evidence-" + task["call_id"]) for key in resumed["artifacts"])
    assert "manuscript-improvement-undispatched-cancellation-" + task["call_id"] in resumed["artifacts"]


def test_canonical_bibliography_removal_does_not_erase_aliases_from_scientific_prose(continuation):
    service, rid, _, _ = continuation
    for _ in range(2):
        task = reserve(service, rid)
        retain(service, rid, task, assessment(task))
    task = reserve(service, rid)
    retain(service, rid, task, improvement_plan())
    task = reserve(service, rid)
    value = revision(service, rid, task)
    value["manuscript"]["sections"][1]["text"] += " {{citation:R1}}"
    value["manuscript"]["sections"].append({"heading": "References", "text":
        "[R1] Synthetic bibliography metadata only; this entry does not identify an actual retained scholarly source."})
    normalized, metadata = canonical_quality_revision(value)
    assert metadata and "{{citation:R1}}" in normalized.manuscript.sections[1].text
    status = retain(service, rid, task, value)
    assert current(status)["calls"][-1]["outcome"] == "rejected"
    assert "Literature citation lacks inspected evidence" in current(status)["calls"][-1]["error"]


def test_best_article_does_not_treat_reviewer_bullet_count_as_defect_severity():
    task = {"venue_id": "ieee-software", "manuscript_sha256": "a" * 64}
    weaker = assessment(task, 5, ["One broad reviewer bullet combines several contribution and evidence issues."])
    stronger = assessment(task, 7, ["The contribution remains bounded to the inspected case.",
        "A separate paragraph identifies a method qualification.", "A third paragraph identifies a presentation correction."])
    assert best_assessment([weaker, stronger]) == stronger
    clean = assessment(task, 6)
    assert best_assessment([stronger, clean]) == clean


def test_finished_exports_refresh_once_per_binding_and_preserve_all_prior_outputs(continuation, monkeypatch):
    service, rid, _, _ = continuation
    for _ in range(2):
        task = reserve(service, rid)
        retain(service, rid, task, {**assessment(task, 9), "recommendation": "consider_submission"})
    conversions = []

    def convert(source, output, *, venue_id):
        conversions.append((venue_id, output.parent.name, output.suffix))
        output.write_bytes(b"Synthetic export generation bytes; no publication assertion.")
        return {"input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "engine": "synthetic-fixture"}

    monkeypatch.setattr("paper_factory.conversion.convert", convert)
    monkeypatch.setattr(service, "_improvement_converter_binding", lambda venue: {"synthetic_version": "one"})
    first = service.finish_manuscript_improvement(rid)
    first_artifacts = copy.deepcopy(first["artifacts"])
    assert current(first)["report_artifact_id"] == "manuscript-improvement-quality-report"
    assert all(item["generation"] == 1 for item in current(first)["exports"].values())
    repeated = service.finish_manuscript_improvement(rid)
    assert len(conversions) == 4 and repeated["manuscript_improvement_snapshot"] == first["manuscript_improvement_snapshot"]
    monkeypatch.setattr(service, "_improvement_converter_binding", lambda venue: {"synthetic_version": "two"})
    second = service.finish_manuscript_improvement(rid)
    assert len(conversions) == 8
    assert current(second)["report_artifact_id"] == "manuscript-improvement-quality-report-2"
    assert all(item["generation"] == 2 and item["artifact_id"].endswith("-export-2") for item in current(second)["exports"].values())
    assert all(item["outputs"]["pdf"]["artifact_id"].endswith("-official-pdf-2") for item in current(second)["exports"].values())
    for key, artifact in first_artifacts.items():
        assert second["artifacts"][key] == artifact
        assert hashlib.sha256(service.artifact_path(rid, key).read_bytes()).hexdigest() == artifact["sha256"]
    assert current(second)["counts"] == current(first)["counts"]
    repeated = service.finish_manuscript_improvement(rid)
    assert len(conversions) == 8 and repeated["manuscript_improvement_snapshot"] == second["manuscript_improvement_snapshot"]
    # Returning to an exact earlier binding reuses those frozen bytes, never reconverts them.
    monkeypatch.setattr(service, "_improvement_converter_binding", lambda venue: {"synthetic_version": "one"})
    reused = service.finish_manuscript_improvement(rid)
    assert len(conversions) == 8 and all(item["generation"] == 1 for item in current(reused)["exports"].values())
    # A changed deterministic editorial input must have its own export identity,
    # even when the scientific source, review, author and converter are identical.
    from paper_factory.journal_compliance import prepare_editorial_markdown
    def prepared_with_separator(markdown, references=None):
        result = prepare_editorial_markdown(markdown, references=references)
        result["markdown"] += "\n"
        result["sha256"] = hashlib.sha256(result["markdown"].encode()).hexdigest()
        return result
    monkeypatch.setattr("paper_factory.journal_compliance.prepare_editorial_markdown", prepared_with_separator)
    editorial = service.finish_manuscript_improvement(rid)
    assert len(conversions) == 12 and all(item["generation"] == 3 for item in current(editorial)["exports"].values())
    assert all(item["bindings"]["prepared_markdown_sha256"] != item["bindings"]["markdown_sha256"]
               for item in current(editorial)["exports"].values())
    unchanged = service.finish_manuscript_improvement(rid)
    assert len(conversions) == 12 and unchanged["manuscript_improvement_snapshot"] == editorial["manuscript_improvement_snapshot"]
    for key, value in reused["artifacts"].items():
        assert editorial["artifacts"][key] == value
    assert current(reused)["report_artifact_id"] == "manuscript-improvement-quality-report-3"


def test_failed_finished_export_is_not_retried_for_the_same_binding(continuation, monkeypatch):
    service, rid, _, _ = continuation
    for _ in range(2):
        task = reserve(service, rid)
        retain(service, rid, task, {**assessment(task, 9), "recommendation": "consider_submission"})
    attempts = []

    def convert(source, output, *, venue_id):
        attempts.append(output.suffix)
        if output.suffix == ".pdf":
            raise ValueError("Explicit synthetic renderer failure; do not retry identical binding")
        output.write_bytes(b"Synthetic Word bytes only.")
        return {"input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "engine": "synthetic-fixture"}

    monkeypatch.setattr("paper_factory.conversion.convert", convert)
    monkeypatch.setattr(service, "_improvement_converter_binding", lambda venue: {"synthetic_version": "fixed"})
    first = service.finish_manuscript_improvement(rid)
    assert len(attempts) == 4 and all(item["errors"] for item in current(first)["exports"].values())
    second = service.finish_manuscript_improvement(rid)
    assert len(attempts) == 4 and second["manuscript_improvement_snapshot"] == first["manuscript_improvement_snapshot"]

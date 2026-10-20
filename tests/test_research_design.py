"""Synthetic research-content contracts, never claims about scholarly merit."""

from copy import deepcopy

import pytest

from paper_factory.autonomous.research_design import ResearchAgenda, ResearchSynthesis, research_design_report, validate_research_agenda


def agenda_value():
    return {"candidates": [{"id": name, "question": question,
        "reader_decision": "Choose whether an operation preserves each request or the latest snapshot.",
        "source_evidence_ids": ["source-1"], "known_approach": "The retained code submits a single explicit operation.",
        "proposed_addition": "Compare the different required service semantics under one shared workload.",
        "falsifier": "Existing closest methods already provide this exact decision under equal assumptions.",
        "method_route": "source_comparison", "literature_queries": [query],
        "evidence_needs": [{"kind": "closest_method", "target": "A complete nearest method for admission semantics.",
            "purpose": "Determine what the established method already provides before claiming a contribution."}]}
        for name, question, query in (("preservation", "When must an operation preserve every submitted request?", "request admission semantics"),
            ("coalescing", "When can the latest snapshot legitimately replace pending work?", "snapshot coalescing policy"))],
        "provisional_selected_id": "preservation", "reason": "Both candidates are provisional until the closest methods are actually read."}


def synthesis_value():
    witness = {"source_id": "primary-1", "text_sha256": "a" * 64,
        "quote": "A synthetic primary passage describes an established admission decision.",
        "interpretation": "Synthetic method evidence exercises exact tuple binding without proving scientific novelty."}
    return {"selected_question_id": "coalescing", "candidate_decisions": [
        {"question_id": "preservation", "decision": "not_supported", "reason": "The closest method already supplies this proposed distinction."},
        {"question_id": "coalescing", "decision": "selected", "reason": "The completed comparison exposes a conditional reader choice."}],
        "closest_methods": [{"id": "admission-method", "evidence": [witness],
            "already_provides": "The established method already differentiates delivery service contracts.",
            "same_conditions": "The same submitted requests and explicit service demands apply to both choices.",
            "difference": "The added case explains a conditional consequence rather than inventing a queue algorithm.",
            "decision_change": "Choose coalescing only when latest snapshot delivery is the actual required service."}],
        "finding_ids": ["conditional-choice"], "product_ids": ["comparison-matrix"],
        "evidence_gaps": [], "strengthening_needed": False, "followup_queries": []}


def analysis_value():
    return {"source_evidence": [{"id": "source-1"}],
        "document_evidence": [synthesis_value()["closest_methods"][0]["evidence"][0]],
        "findings": [{"id": "conditional-choice", "claim": "This synthetic completed comparison changes the service-contract decision.",
            "evidence_ids": ["source-1", "primary-1"]}],
        "work_products": {"products": [{"id": "comparison-matrix", "kind": "source_comparison",
            "observations": [{"id": "observation-1", "observation": "A retained comparison identifies the conditional outcome."}]}]}}


def test_completed_research_brief_carries_changed_question_actual_comparison_and_results():
    agenda, synthesis, analysis = agenda_value(), synthesis_value(), analysis_value()
    before = deepcopy((agenda, synthesis, analysis))
    report = research_design_report(agenda, synthesis, analysis)
    brief = report["writer_brief"]
    assert brief["selected_question"]["id"] == "coalescing"
    assert brief["closest_methods"][0]["already_provides"] == synthesis["closest_methods"][0]["already_provides"]
    assert brief["completed_findings"] == analysis["findings"]
    assert brief["completed_work_products"] == analysis["work_products"]["products"]
    assert (agenda, synthesis, analysis) == before
    brief["completed_findings"][0]["claim"] = "Mutating a writing packet cannot rewrite retained analytical findings."
    assert analysis == before[2]


@pytest.mark.parametrize("defect", ["unknown_source", "unknown_question", "unread_method", "changed_quote", "wrong_body", "invented_finding", "invented_product", "invented_support"])
def test_research_brief_rejects_invented_or_unread_content(defect):
    agenda, synthesis, analysis = agenda_value(), synthesis_value(), analysis_value()
    if defect == "unknown_source":
        agenda["candidates"][0]["source_evidence_ids"] = ["uninspected-source"]
    elif defect == "unknown_question":
        synthesis["candidate_decisions"][0]["question_id"] = "invented-question"
    elif defect == "unread_method":
        analysis["document_evidence"] = []
    elif defect == "changed_quote":
        synthesis["closest_methods"][0]["evidence"][0]["quote"] += " An invented extra conclusion."
    elif defect == "wrong_body":
        synthesis["closest_methods"][0]["evidence"][0]["text_sha256"] = "b" * 64
    elif defect == "invented_finding":
        synthesis["finding_ids"] = ["invented-finding"]
    elif defect == "invented_product":
        synthesis["product_ids"] = ["invented-product"]
    else:
        analysis["findings"][0]["evidence_ids"] = ["invented-observation"]
    with pytest.raises(ValueError):
        research_design_report(agenda, synthesis, analysis)


def test_synthesis_can_honestly_select_no_question_without_score_or_generation_gate():
    synthesis = synthesis_value()
    synthesis.update(selected_question_id=None, closest_methods=[], finding_ids=[], product_ids=[])
    for item in synthesis["candidate_decisions"]:
        item["decision"] = "not_supported"
    brief = research_design_report(agenda_value(), synthesis, analysis_value())["writer_brief"]
    assert brief["selected_question"] is None and brief["completed_findings"] == []
    assert "score" not in brief and "ready_to_write" not in brief


def test_constructive_followup_requires_attainable_evidence_and_unique_bounded_queries():
    synthesis = synthesis_value()
    synthesis.update(strengthening_needed=True, followup_queries=["latest snapshot delivery semantics"],
        evidence_gaps=[{"attainable": True, "needed_evidence": "Read the closest published delivery-contract method.",
            "reason": "The current retained body does not settle this proposed difference."}])
    assert ResearchSynthesis.model_validate(synthesis).strengthening_needed
    synthesis["evidence_gaps"][0]["attainable"] = False
    with pytest.raises(ValueError, match="attainable"):
        ResearchSynthesis.model_validate(synthesis)


def test_agenda_is_bounded_and_all_candidates_use_inspected_sources():
    agenda = validate_research_agenda(agenda_value(), {"source-1"})
    assert agenda.queries() == ["request admission semantics", "snapshot coalescing policy"]
    agenda = agenda_value()
    agenda["candidates"].append({**deepcopy(agenda["candidates"][0]), "id": "third", "question": "What different admission policy changes the outcome?",
        "literature_queries": ["bounded third candidate method", "second third candidate method"]})
    agenda["candidates"][0]["literature_queries"].append("additional fifth distinct method")
    with pytest.raises(ValueError, match="at most four"):
        ResearchAgenda.model_validate(agenda)

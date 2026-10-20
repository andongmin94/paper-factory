"""Actual native service orchestration with injected synthetic research bodies.

No real SDK, network, Word conversion or project execution occurs. Positive
fixtures establish content transport and budget behavior, not scholarly merit.
"""

from copy import deepcopy
import hashlib
import json

import pytest

from paper_factory.autonomous import literature
from paper_factory.workflow import WorkflowService
from paper_factory.workspace import safe_relative
from test_research_development_workflow import development, continuation, generated_evidence, unwritten_portfolio, plan_value
from test_repository_paper_workflow import NoExecutionRunner
from test_research_development_contract import products
from test_research_design import agenda_value, synthesis_value
from test_manuscript_improvement import current, reserve, retain, revision, assessment
from test_workflow import collect_arxiv_preprint


@pytest.fixture
def study(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "tool.js").write_text("export function tool(options) { return { ...options, enabled: true }; }\n", encoding="utf-8")
    (source / "README.md").write_text("The documented tool enables declarative application configuration.\n", encoding="utf-8")
    (source / "extra-guide.md").write_text("A separate retained guide qualifies which downstream effects the declared configuration does not establish.\n", encoding="utf-8")
    service = WorkflowService(tmp_path / "engine", runner=NoExecutionRunner())
    created = service.create(str(source), "Analyze the documented software configuration design and its actual source boundaries.", "repository_analysis")
    yield service, created["id"]
    service.close()


class NativeCollector:
    """Use original native identity/body checking with synthetic retained bytes."""
    def __init__(self):
        self.calls = []

    def __call__(self, queries, root, **kwargs):
        self.calls.append({"queries": list(queries), **kwargs})
        identifier = "1311.3903v1" if len(self.calls) == 1 else "2401.12345v1"
        packet = collect_arxiv_preprint(queries, root, limit=kwargs["limit"], cancel=kwargs["cancel"], arxiv_id=identifier)
        source = packet["sources"][0]
        path = safe_relative(root, source["text_path"])
        text = path.read_bytes().decode("utf-8").replace("\nReferences\n", "\nSynthetic acquired method " + str(len(self.calls)) +
            " distinguishes a source configuration contract from an unverified downstream effect.\nReferences\n")
        path.write_bytes(text.encode("utf-8"))
        source.update(text_sha256=hashlib.sha256(text.encode()).hexdigest(), text_chars=len(text), body_range=literature.full_text_body_range(text))
        packet["pdf_reservations"] = [{"source_id": source["id"], "url": "https://arxiv.org/pdf/" + identifier, "pdf_attempted": True}]
        return packet


def materials(task):
    return json.loads(task["prompt"].rsplit("\n", 1)[1])["materials"]


def grounded_agenda(task):
    value = agenda_value()
    source_ids = [item["id"] for item in materials(task)["source_grounding"]]
    for candidate in value["candidates"]:
        candidate["source_evidence_ids"] = source_ids
    value["candidates"][0]["evidence_needs"].extend([
        {"kind": "source_inspection", "target": "extra-guide.md", "purpose": "Read the complete additional guide before selecting the source-bound research question."},
        {"kind": "source_inspection", "target": "not-present.md", "purpose": "Retain the unavailable source request without inventing its body or evidence."}])
    return value


def question_design(service, rid, task, evidence, *, strengthen=False, improved=False):
    value = deepcopy(evidence)
    frame = materials(task)
    documents = [item for item in frame["documents"] if item.get("source_role") == "primary_full_text"]
    source = documents[-1]
    witness = {"source_id": source["id"], "text_sha256": source["text_sha256"],
        "quote": next(line for line in source["text"].splitlines() if line.startswith("Synthetic acquired method")),
        "interpretation": "Synthetic complete primary evidence grounds an explicit comparison without asserting actual scholarly novelty."}
    synthesis = synthesis_value()
    synthesis["closest_methods"][0]["evidence"] = [witness]
    synthesis.update(finding_ids=["conditional_choice"], product_ids=["source-choice"],
        strengthening_needed=strengthen,
        followup_queries=["conditional configuration downstream contract"] if strengthen else [],
        evidence_gaps=[{"attainable": True, "needed_evidence": "Read the nearest complete downstream configuration method.",
            "reason": "A second acquired comparison can clarify whether the proposed addition is already known."}] if strengthen else [])
    value.update(method_scope="source_comparison_not_project_execution", cases=[], document_evidence=[witness],
        comparisons=[{"source_id": witness["source_id"], "established_method": "The closest method already identifies explicit configuration contracts.",
            "local_difference": "The completed comparison makes a conditional downstream assumption visible.",
            "what_is_not_new": "An explicit contract boundary itself is already an established design principle.",
            "cost_or_limit": "No actual execution or downstream effect is established by the retained fixture."}],
        findings=[{"id": "conditional_choice", "claim": ("The strengthened comparison distinguishes an actual source promise from an unverified downstream effect."
                if improved else "The initial completed comparison distinguishes a declared promise from a downstream assumption."),
            "evidence_ids": [item["id"] for item in value["source_evidence"]] + [witness["source_id"]]}],
        research_design=synthesis)
    value["work_products"] = products(value)
    product = value["work_products"]["products"][0]
    product["changed_decisions"][0]["prior_method_evidence_ids"] = [witness["source_id"]]
    product["changed_decisions"][0]["support_ids"].append(witness["source_id"])
    product["observations"][1]["observation"] = value["findings"][0]["claim"]
    plan = plan_value(evidence)
    plan.update(cases=[], document_evidence=[witness], inspect_source_files=task["inspected_source_files"])
    return {"plan": plan, "evidence": value}


def question_audit(state):
    return {"evidence_sha256": state["research_development"]["evidence_sha256"], "correspondence": [], "repair_actions": [],
        "decisive_findings": ["The synthetic completed source comparison answers the conditional declared-contract question."],
        "honest_limits": ["This is a static synthetic fixture and establishes no actual execution, novelty or publication merit."],
        "ready_to_write": True, "repair_required": False,
        "work_product_findings": [{"product_id": "source-choice", "verdict": "faithful",
            "reason": "The synthetic comparison product refers to its actual retained source and acquired closest-method body.", "required_repair": ""}]}


def research_papers(service, rid, task):
    frame = materials(task)
    brief = frame["completed_research_design"]["writer_brief"]
    witness = brief["closest_methods"][0]["evidence"][0]
    papers = []
    for venue in current(service.status(rid))["versions"]:
        paper = revision(service, rid, {**task, "venue_id": venue, "action_id": frame["development_action_ids"][venue]})
        paper["manuscript"]["document_evidence"].append(deepcopy(witness))
        paper["manuscript"]["sections"][1]["text"] += (" The completed research answers the selected coalescing question with a conditional source contract. "
            + brief["completed_findings"][0]["claim"] + " {{document:" + witness["source_id"] + "}}")
        paper["contributions"][0]["evidence_ids"].append(witness["source_id"])
        papers.append(paper)
    return {"revisions": papers}


@pytest.mark.parametrize("development", [3], indirect=True)
@pytest.mark.parametrize("strengthen", [False, True])
def test_question_led_acquisition_improves_actual_content_before_writing_without_reset(development, strengthen, monkeypatch):
    service, rid, old, granted, evidence = development
    collector = NativeCollector()
    service.collector = collector
    synthetic_preflight = service._improvement_focused_preflight
    def preflight(ws, record, state, venue, markdown, **kwargs):
        # Exercise actual native reference preparation while keeping Word/PDF
        # conversion explicitly synthetic in this orchestration fixture.
        from paper_factory.journal_compliance import prepare_editorial_markdown
        prepared = prepare_editorial_markdown(markdown, references=service._improvement_reference_cards(ws, record, state))
        return synthetic_preflight(ws, record, state, venue, prepared["markdown"], **kwargs)
    monkeypatch.setattr(service, "_improvement_focused_preflight", preflight)
    baseline = current(granted)["counts"]["model_attempts"]
    old_call_count = len(current(granted)["calls"])
    assert current(granted)["research_development"]["contract_version"] == 3
    task = reserve(service, rid)
    assert task["purpose"] == "develop-question"
    assert "extra-guide.md" not in {item["path"] for item in materials(task)["source_files"]}
    result = retain(service, rid, task, grounded_agenda(task))
    assert len(collector.calls) == 1
    task = reserve(service, rid)
    assert task["purpose"] == "develop-design"
    guide = next(item for item in materials(task)["source_files"] if item["path"] == "extra-guide.md")
    retained_guide = service.read_material(rid, "source", "extra-guide.md")
    assert guide["text"] == retained_guide["text"] and guide["sha256"] == retained_guide["sha256"]
    assert [item["target"] for item in materials(task)["unavailable_source_needs"]] == ["not-present.md"]
    assert any("Synthetic acquired method 1" in item.get("text", "") for item in materials(task)["documents"])
    result = retain(service, rid, task, question_design(service, rid, task, evidence, strengthen=strengthen))
    assert current(result)["calls"][-1]["outcome"] == "completed", current(result)["calls"][-1]
    if strengthen:
        assert len(collector.calls) == 2 and collector.calls[1]["pdf_reservation_limit"] == 1
        task = reserve(service, rid)
        assert task["purpose"] == "develop-strengthen"
        assert any("Synthetic acquired method 2" in item.get("text", "") for item in materials(task)["documents"])
        result = retain(service, rid, task, question_design(service, rid, task, evidence, improved=True))
        assert current(result)["calls"][-1]["outcome"] == "completed", current(result)["calls"][-1]
    task = reserve(service, rid)
    assert task["purpose"] == "develop-audit"
    assert materials(task)["completed_research_design"]["writer_brief"]["selected_question"]["id"] == "coalescing"
    result = retain(service, rid, task, question_audit(current(result)))
    assert current(result)["research_development"]["readiness"]["ready_to_write"]
    task = reserve(service, rid)
    assert task["purpose"] == "develop-write"
    brief = materials(task)["completed_research_design"]["writer_brief"]
    assert brief["selected_question"]["id"] != materials(task)["research_agenda"]["provisional_selected_id"]
    assert bool("strengthened" in brief["completed_findings"][0]["claim"]) == strengthen
    result = retain(service, rid, task, research_papers(service, rid, task))
    assert current(result)["calls"][-1]["outcome"] == "completed", current(result)["calls"][-1]
    task = reserve(service, rid)
    assert task["purpose"] == "develop-review"
    assessments = []
    frame = materials(task)
    for venue, target in frame["review_targets"].items():
        value = assessment({**task, "venue_id": venue, "manuscript_sha256": target["manuscript_sha256"]}, 6)
        assessments.append(value)
    result = retain(service, rid, task, {"assessments": assessments})
    final = current(result)
    assert final["next_task"] is None
    assert final["counts"]["model_attempts"] == baseline + (6 if strengthen else 5)
    assert len(final["calls"]) == old_call_count + (6 if strengthen else 5)
    assert len(collector.calls) == (2 if strengthen else 1)
    assert final["research_development"]["evidence"]["case_ids"] == []
    for version in final["research_development"]["write_versions"].values():
        markdown = service.artifact_path(rid, version["markdown_artifact_id"]).read_text(encoding="utf-8")
        assert brief["completed_findings"][0]["claim"] in markdown
        assert "Synthetic exact-version preprint retention fixture" in markdown
        assert "arxiv.org" in markdown and "References" in markdown
    for key, artifact in old["artifacts"].items():
        assert result["artifacts"][key] == artifact
        assert hashlib.sha256(service.artifact_path(rid, key).read_bytes()).hexdigest() == artifact["sha256"]
    assert all(result[key] == old[key] for key in ("proposal_attempt", "draft_attempt", "execution_attempt", "study_literature_attempt"))

"""Synthetic publication-contract tests; passing fixtures attest no scholarly value."""

import copy
import hashlib
import json
from types import SimpleNamespace
import zipfile

import pytest
from pydantic import ValidationError

from paper_factory import ipc
from paper_factory.autonomous import literature
from paper_factory.autonomous.models import ManuscriptReview, ResearchPlan, StudyReview
from paper_factory.workflow import WorkflowError
from paper_factory.workspace import digest_file, write_json
from test_workflow import (MANUSCRIPT_REVIEW, STUDY_REVIEW, SYNTHETIC_ABSTRACT, SYNTHETIC_BODY_START,
                           SYNTHETIC_PASSAGE, SYNTHETIC_PREFIX, SYNTHETIC_SUFFIX, collect, finished,
                           collect_arxiv_preprint, manuscript, prepare, protocol, setup)


def measured(setup):
    service, runner, research_id = setup
    prepare(service, research_id)
    service.start_experiment(research_id)
    assert finished(service, research_id)["stage"] == "analyzed"
    return service, runner, research_id


def test_historical_protocol_and_reviews_keep_readable_identity(setup):
    old_plan = protocol()
    old_plan.pop("research_claim")
    parsed = ResearchPlan.model_validate(old_plan)
    assert parsed.research_claim is None and parsed.model_dump(mode="json") == old_plan
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert hashlib.sha256(canonical(parsed.model_dump(mode="json"))).digest() == hashlib.sha256(canonical(old_plan)).digest()
    for model, original in ((StudyReview, STUDY_REVIEW), (ManuscriptReview, MANUSCRIPT_REVIEW)):
        historical = copy.deepcopy(original)
        historical.pop("publication_readiness")
        assert model.model_validate(historical).accepted is True
    service, runner, research_id = setup
    with pytest.raises(WorkflowError) as missing:
        service.submit_proposal(research_id, old_plan)
    assert missing.value.code == "RESEARCH_CLAIM_REQUIRED" and runner.calls == 0
    assert service.status(research_id)["proposal_attempt"] == 0


@pytest.mark.parametrize("stage", ["study", "manuscript"])
@pytest.mark.parametrize("accepted", [True, False])
def test_every_fresh_review_requires_readiness_even_when_rejected(setup, stage, accepted):
    service, runner, research_id = setup
    if stage == "study":
        service.submit_proposal(research_id, protocol())
        service.collect_literature(research_id)
        review, submit = copy.deepcopy(STUDY_REVIEW), lambda value: service.submit_study_review(research_id, value)
    else:
        measured(setup)
        review, submit = copy.deepcopy(MANUSCRIPT_REVIEW), lambda value: service.submit_manuscript(research_id, manuscript(), value)
    review.pop("publication_readiness")
    if not accepted:
        review.update(accepted=False, issues=["The synthetic claim lacks independently inspected closest work."])
        review["contribution"]["passed"] = False
        if stage == "manuscript":
            review["remediation"] = {"strategy": "revise_manuscript", "reason": "Inspect closest work before claiming a useful knowledge difference.",
                                     "actions": [{"criterion": "contribution", "action": "Retrieve relevant original methods and results before assessing this claim."}],
                                     "evidence_gaps": []}
    before = service.status(research_id)["artifacts"]
    with pytest.raises(WorkflowError) as missing:
        submit(review)
    assert missing.value.code == "PUBLICATION_READINESS_REQUIRED"
    assert service.status(research_id)["artifacts"] == before and runner.calls == (stage == "manuscript")


@pytest.mark.parametrize("nested,criterion", [("novelty", "contribution"), ("significance", "contribution"), ("validation", "interpretation")])
def test_nested_quality_failures_reject_and_require_corresponding_repairs(nested, criterion):
    review = copy.deepcopy(MANUSCRIPT_REVIEW)
    review["publication_readiness"][nested]["passed"] = False
    with pytest.raises(ValidationError, match="acceptance must agree"):
        ManuscriptReview.model_validate(review)
    review.update(accepted=False, issues=["The nested publication criterion lacks supporting evidence."])
    review["remediation"] = {"strategy": "revise_manuscript", "reason": "Retrieve missing literature without repeating the retained experiment.",
                             "actions": [{"criterion": criterion, "action": "Correct the evidence-linked scientific deficiency identified in the nested assessment."}],
                             "evidence_gaps": []}
    assert ManuscriptReview.model_validate(review).accepted is False
    review["remediation"]["actions"][0]["criterion"] = "presentation"
    with pytest.raises(ValidationError, match="every failed criterion"):
        ManuscriptReview.model_validate(review)


@pytest.mark.parametrize("defect", ["abstract", "quote", "range", "unselected", "claim", "scope", "mode", "unretained_text"])
def test_model_approval_cannot_bypass_original_fulltext_claim_binding(setup, defect):
    service, runner, research_id = setup
    if defect in {"abstract", "range", "unretained_text"}:
        def damaged(*args, **kwargs):
            evidence = collect(*args, **kwargs)
            source = evidence["sources"][0]
            if defect == "abstract":
                source["scope"] = "abstract"
            elif defect == "range":
                source["excerpt_ranges"][0]["end"] -= 1
            else:
                source.pop("text_path")
                source.pop("text_sha256")
            return evidence
        service.collector = damaged
    service.submit_proposal(research_id, protocol())
    service.collect_literature(research_id)
    review = copy.deepcopy(STUDY_REVIEW)
    ready = review["publication_readiness"]
    if defect == "quote":
        ready["closest_work"][0]["quote"] = "Invented methods and findings that never appeared in this retrieved primary source. " * 2
    elif defect == "unselected":
        ready["closest_work"][0]["excerpt_index"] = 1
    elif defect in {"claim", "scope"}:
        ready[defect] = "A substituted broader claim lacks the evidence required by the frozen proposal."
    elif defect == "mode":
        ready["evidence_mode"] = "formal"
    before = service.status(research_id)["artifacts"]
    with pytest.raises(WorkflowError) as rejected:
        service.submit_study_review(research_id, review)
    assert rejected.value.code == "PUBLICATION_EVIDENCE_INVALID"
    assert service.status(research_id)["artifacts"] == before and runner.calls == 0


@pytest.mark.parametrize("defect", ["missing_result", "unknown_result", "unknown_fixture", "unknown_proof", "uncited_closest"])
def test_final_claim_support_is_bound_to_retained_results_fixtures_and_candidate(setup, defect):
    service, runner, research_id = measured(setup)
    review, draft = copy.deepcopy(MANUSCRIPT_REVIEW), manuscript()
    ready = review["publication_readiness"]
    if defect == "missing_result":
        ready["analysis_keys"] = []
    elif defect == "unknown_result":
        ready["analysis_keys"] = ["invented.condition_1.mean"]
    elif defect == "unknown_fixture":
        ready["fixture_labels"] = ["invented-evidence.json"]
    elif defect == "unknown_proof":
        ready.update(proof_section="Method", proof_quote="This fabricated proof does not occur in the actual manuscript submitted for review. " * 2)
    else:
        next(section for section in draft["sections"] if section["heading"] == "Related Work")["text"] = "Actual closest work was omitted from the manuscript rather than compared. " * 5
    before = service.status(research_id)["artifacts"]
    with pytest.raises(WorkflowError) as rejected:
        service.submit_manuscript(research_id, draft, review)
    assert rejected.value.code == "PUBLICATION_EVIDENCE_INVALID"
    assert service.status(research_id)["artifacts"] == before and runner.calls == 1


def test_finite_and_formal_support_are_distinguished_without_claiming_machine_proof(setup):
    service, runner, research_id = setup
    plan = protocol()
    plan["research_claim"]["mode"] = "formal"
    study = copy.deepcopy(STUDY_REVIEW)
    study["publication_readiness"]["evidence_mode"] = "formal"
    service.submit_proposal(research_id, plan)
    service.collect_literature(research_id)
    service.submit_study_review(research_id, study)
    from test_workflow import BUNDLE, REVIEW
    service.submit_code(research_id, BUNDLE, REVIEW)
    service.start_experiment(research_id)
    assert finished(service, research_id)["stage"] == "analyzed"
    review = copy.deepcopy(MANUSCRIPT_REVIEW)
    ready = review["publication_readiness"]
    ready.update(evidence_mode="formal", analysis_keys=[])
    with pytest.raises(WorkflowError, match="proof passage"):
        service.submit_manuscript(research_id, manuscript(), review)
    draft = manuscript()
    passage = next(section["text"] for section in draft["sections"] if section["heading"] == "Method")[:150]
    ready.update(proof_section="Method", proof_quote=passage)
    assert service.submit_manuscript(research_id, draft, review)["stage"] == "manuscript"
    assert runner.calls == 1  # This only proves evidence identity plumbing, not a real theorem.


def test_multiple_passages_preserve_original_indices_and_literal_ranges(setup):
    service, runner, research_id = setup
    first, second = SYNTHETIC_PASSAGE.split(". ", 1)
    def multiple(*args, **kwargs):
        evidence = collect(*args, **kwargs)
        evidence["sources"][0].update(excerpts=[first + ".", second],
            excerpt_ranges=[{"start": SYNTHETIC_BODY_START, "end": SYNTHETIC_BODY_START + len(first) + 1},
                            {"start": SYNTHETIC_BODY_START + len(first) + 2, "end": SYNTHETIC_BODY_START + len(SYNTHETIC_PASSAGE)}])
        return evidence
    service.collector = multiple
    service.submit_proposal(research_id, protocol())
    service.collect_literature(research_id)
    review = copy.deepcopy(STUDY_REVIEW)
    review["selected_sources"].append({**review["selected_sources"][0], "excerpt_index": 1})
    state = service.submit_study_review(research_id, review)
    source = state["literature"]["sources"][0]
    assert source["selected_excerpt_indices"] == [0, 1]
    assert source["excerpts"] == [first + ".", second] and len(source["excerpt_ranges"]) == 2
    assert runner.calls == 0


@pytest.mark.parametrize("region", ["abstract", "references", "unknown", "forged_boundary"])
def test_fulltext_badge_and_mixed_excerpt_cannot_certify_abstract_or_bibliography(setup, region):
    service, runner, research_id = setup
    def mixed(*args, **kwargs):
        evidence = collect(*args, **kwargs)
        source = evidence["sources"][0]
        complete = SYNTHETIC_PREFIX + SYNTHETIC_PASSAGE + SYNTHETIC_SUFFIX
        if region == "unknown":
            complete = complete.replace("Introduction", "Unrecognized body heading")
            path = args[1] / source["text_path"]
            path.write_bytes(complete.encode())
            source["text_sha256"] = digest_file(path)
        source.update(excerpts=[complete], excerpt_ranges=[{"start": 0, "end": len(complete)}],
                      body_range=literature.full_text_body_range(complete))
        if region == "forged_boundary":
            source["body_range"] = {"start": 0, "end": len(complete)}
        return evidence
    service.collector = mixed
    service.submit_proposal(research_id, protocol())
    service.collect_literature(research_id)
    review = copy.deepcopy(STUDY_REVIEW)
    quote = SYNTHETIC_ABSTRACT if region in {"abstract", "forged_boundary"} else (
        SYNTHETIC_SUFFIX.split("\nReferences\n")[1] if region == "references" else SYNTHETIC_PASSAGE[:100])
    review["publication_readiness"]["closest_work"][0]["quote"] = quote
    with pytest.raises(WorkflowError) as rejected:
        service.submit_study_review(research_id, review)
    assert rejected.value.code == "PUBLICATION_EVIDENCE_INVALID" and runner.calls == 0


@pytest.mark.parametrize("mode", ["different_fulltext", "abstract_downgrade", "unknown_fulltext"])
def test_same_source_merge_preserves_passages_and_version_index_identity(setup, mode):
    service, runner, research_id = measured(setup)
    original = service.status(research_id)["literature"]["sources"][0]
    replacement = ("A distinct synthetic revised-source body reports another controlled finding. "
                   "Its wording differs from the original passage while preserving an honest source identity.")
    def additional(*args, **kwargs):
        evidence = collect(*args, **kwargs)
        source = evidence["sources"][0]
        if mode == "abstract_downgrade":
            source.update(scope="abstract", excerpts=[SYNTHETIC_ABSTRACT])
            source["excerpt_ranges"] = [{"start": len("Abstract\n"), "end": len("Abstract\n") + len(SYNTHETIC_ABSTRACT)}]
        else:
            complete = SYNTHETIC_PREFIX + replacement + SYNTHETIC_SUFFIX
            if mode == "unknown_fulltext":
                complete = complete.replace("Introduction", "Unrecognized body heading")
            path = args[1] / source["text_path"]
            path.write_bytes(complete.encode())
            start = complete.index(replacement)
            source.update(excerpts=[replacement], text_sha256=digest_file(path),
                          excerpt_ranges=[{"start": start, "end": start + len(replacement)}],
                          body_range=literature.full_text_body_range(complete))
        return evidence
    service.collector = additional
    state = service.collect_authoring_literature(research_id, ["Inspect another exact version of the closest source"])
    assert state["authoring_literature"]["quality_status"] == ("no_full_text" if mode == "abstract_downgrade" else "full_text_available")
    state = service.select_authoring_literature(research_id, copy.deepcopy(STUDY_REVIEW["selected_sources"]))
    merged = state["literature"]["sources"][0]
    assert merged["scope"] == "full_text" and SYNTHETIC_PASSAGE in merged["excerpts"]
    assert len(merged["excerpts"]) == len(merged["passage_provenance"]) == 2
    assert merged["selected_excerpt_indices"] == [0, 0]
    assert merged["passage_provenance"][0]["text_sha256"] == original["text_sha256"]
    assert service.submit_manuscript(research_id, manuscript(), MANUSCRIPT_REVIEW)["stage"] == "manuscript"
    assert runner.calls == 1


def test_identical_text_retrieval_upgrades_legacy_missing_body_metadata_without_replacing_bytes(setup):
    service, runner, research_id = measured(setup)
    from paper_factory.workflow import _freeze
    from paper_factory.workflow_models import Workflow
    from paper_factory.workspace import Workspace
    ws = Workspace(service.root / research_id)
    record = ws.get("workflow", research_id, Workflow)
    selection_path = service.artifact_path(research_id, "selected-literature")
    selection = json.loads(selection_path.read_bytes())
    selection["sources"][0].pop("body_range")
    write_json(selection_path, selection)
    _freeze(ws, record, "selected-literature", selection_path)
    literature_path = service.artifact_path(research_id, "literature")
    evidence = json.loads(literature_path.read_bytes())
    evidence["sources"][0].pop("body_range")
    write_json(literature_path, evidence)
    _freeze(ws, record, "literature", literature_path)
    # This constructs a historical fixture; production APIs never mutate approval.
    receipt_path = service.artifact_path(research_id, "study-review")
    receipt = json.loads(receipt_path.read_bytes())
    receipt.update(literature_sha256=record.artifacts["literature"].sha256,
                   selected_literature_sha256=record.artifacts["selected-literature"].sha256)
    write_json(receipt_path, receipt)
    for key in ("study-review", "study-review-1"):
        _freeze(ws, record, key, receipt_path)
    ws.save("workflow", record)
    retained = {key: service.artifact_path(research_id, key).read_bytes() for key in ("selected-literature", "literature", "study-review", "plan", "observations")}
    service.collect_authoring_literature(research_id, ["Reinspect the same exact source with certified body boundaries"])
    state = service.select_authoring_literature(research_id, copy.deepcopy(STUDY_REVIEW["selected_sources"]))
    source = state["literature"]["sources"][0]
    assert len(source["excerpts"]) == len(source["passage_provenance"]) == 1
    assert source["passage_provenance"][0]["body_range"] is not None
    assert service.submit_manuscript(research_id, manuscript(), MANUSCRIPT_REVIEW)["stage"] == "manuscript"
    assert runner.calls == 1 and all(service.artifact_path(research_id, key).read_bytes() == value for key, value in retained.items())


@pytest.mark.parametrize("outcome", ["no_sources", "abstract_only", "rate_limited", "timed_out"])
def test_bounded_negative_authoring_search_is_retained_without_aborting_usable_evidence(setup, outcome):
    service, runner, research_id = measured(setup)
    before = {key: service.artifact_path(research_id, key).read_bytes() for key in ("plan", "literature", "selected-literature", "observations", "analysis", "execution")}
    def unavailable(*args, **kwargs):
        evidence = collect(*args, **kwargs)
        query = args[0][0]
        empty_feed = b'<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"><opensearch:totalResults>0</opensearch:totalResults></feed>'
        empty_path = args[1] / "empty-title-discovery.xml"
        empty_path.write_bytes(empty_feed)
        evidence["searches"] = [{"query": query, "provider": "arXiv", "lookup": "exact_title",
            "status": "succeeded", "attempted": True, "resolved_ids": [],
            "note": "No unique exact-title preprint was resolved; this is not evidence that relevant work is absent",
            "raw_path": empty_path.name, "sha256": hashlib.sha256(empty_feed).hexdigest()},
            {**evidence["searches"][0], "provider": "Crossref", "lookup": "bibliographic"}]
        if outcome == "no_sources":
            evidence["sources"] = []
        elif outcome == "abstract_only":
            evidence["sources"][0]["scope"] = "abstract"
        else:
            evidence[outcome] = True
        return evidence
    service.collector = unavailable
    state = service.collect_authoring_literature(research_id, ["Retrieve relevant original methods and results"])
    assert state["authoring_literature"]["quality_status"] == ("incomplete" if outcome in {"rate_limited", "timed_out"} else "no_full_text")
    assert state["authoring_selection"] is None and state["stage"] == "analyzed"
    coverage = state["literature"]["authoring_collection"]
    assert coverage["quality_status"] == state["authoring_literature"]["quality_status"]
    assert coverage["searches"][0]["query"] == "Retrieve relevant original methods and results"
    assert [(search["provider"], search["lookup"]) for search in coverage["searches"]] == [
        ("arXiv", "exact_title"), ("Crossref", "bibliographic")]
    assert coverage["searches"][0]["resolved_ids"] == []
    assert "not evidence that relevant work is absent" in coverage["searches"][0]["note"]
    assert not {"raw_path", "sha256"} & coverage["searches"][0].keys()
    assert all(service.artifact_path(research_id, key).read_bytes() == value for key, value in before.items())
    if outcome != "no_sources":
        selected = service.select_authoring_literature(research_id, copy.deepcopy(STUDY_REVIEW["selected_sources"]))
        assert selected["literature"]["authoring_collection"] == coverage
    assert service.submit_manuscript(research_id, manuscript(), MANUSCRIPT_REVIEW)["stage"] == "manuscript"
    assert runner.calls == 1


def test_authoring_collection_selection_and_export_preserve_the_original_study(setup, pandoc, monkeypatch):
    service, runner, research_id = measured(setup)
    before = {key: service.artifact_path(research_id, key).read_bytes() for key in service.status(research_id)["artifacts"]}
    queries = ["Retrieve synthetic closest methods and limitations"]
    state = service.collect_authoring_literature(research_id, queries)
    assert state["authoring_literature"]["sources"][0]["scope"] == "full_text"
    assert state["authoring_selection"] is None and state["execution_attempt"] == 1
    assert "authoring-literature" not in {entry["name"] for entry in state["material_manifest"]["evidence"]}
    index_path = service.artifact_path(research_id, "authoring-literature")
    index_bytes = index_path.read_bytes()
    state = service.select_authoring_literature(research_id, copy.deepcopy(STUDY_REVIEW["selected_sources"]))
    assert len(state["literature"]["sources"]) == 1  # Same source id upgrades writing view; no duplicate citation id.
    assert state["authoring_selection"]["collection_sha256"] == digest_file(index_path)
    assert "authoring-selected-literature" in {entry["name"] for entry in state["material_manifest"]["evidence"]}
    assert all(service.artifact_path(research_id, key).read_bytes() == value for key, value in before.items())
    service.submit_manuscript(research_id, manuscript(), MANUSCRIPT_REVIEW)
    receipt = json.loads(service.artifact_path(research_id, "manuscript-review").read_bytes())
    for key in ("authoring-literature", "authoring-selected-literature"):
        assert receipt[key.replace("-", "_") + "_sha256"] == service.status(research_id)["artifacts"][key]["sha256"]
    monkeypatch.setenv("PYPANDOC_PANDOC", pandoc)
    assert service.export(research_id)["stage"] == "exported"
    with zipfile.ZipFile(service.artifact_path(research_id, "reproducibility")) as archive:
        assert "authoring/literature/authoring-literature.json" in archive.namelist()
        assert "authoring/literature/authoring-selected-literature.json" in archive.namelist()
        assert archive.read("authoring/literature/authoring-literature.json") == index_bytes
        assert "literature/fixture-source.txt" in archive.namelist()
        assert any(name.startswith("authoring-literature/") and name.endswith("fixture-source.txt") for name in archive.namelist())
    assert runner.calls == 1 and all(service.artifact_path(research_id, key).read_bytes() == value for key, value in before.items())


def test_doi_free_versioned_arxiv_preprint_review_and_zip_preserve_xml_pdf_and_text(setup, pandoc, monkeypatch):
    service, runner, research_id = setup
    service.collector = collect_arxiv_preprint
    plan = protocol()
    plan["literature_queries"] = ["arXiv:1311.3903v1"]
    service.submit_proposal(research_id, plan)
    state = service.collect_literature(research_id)
    first = copy.deepcopy(state["literature"]["sources"][0])
    assert "doi" not in first and first["arxiv_id"] == "1311.3903v1"
    study = copy.deepcopy(STUDY_REVIEW)
    study["selected_sources"][0]["source_id"] = first["id"]
    study["publication_readiness"]["closest_work"][0]["source_id"] = first["id"]
    service.submit_study_review(research_id, study)
    from test_workflow import BUNDLE, REVIEW
    service.submit_code(research_id, BUNDLE, REVIEW)
    service.start_experiment(research_id)
    assert finished(service, research_id)["stage"] == "analyzed"
    before = {key: service.artifact_path(research_id, key).read_bytes() for key in service.status(research_id)["artifacts"]}
    service.collector = lambda *args, **kwargs: collect_arxiv_preprint(*args, **kwargs, arxiv_id="1311.3903v2")
    state = service.collect_authoring_literature(research_id, ["10.48550/arXiv.1311.3903v2"])
    second = copy.deepcopy(state["authoring_literature"]["sources"][0])
    assert "doi" not in second and second["arxiv_id"] == "1311.3903v2" and second["id"] != first["id"]
    selected = [{**STUDY_REVIEW["selected_sources"][0], "source_id": second["id"]}]
    state = service.select_authoring_literature(research_id, selected)
    assert {source["id"] for source in state["literature"]["sources"]} == {first["id"], second["id"]}
    review, draft = copy.deepcopy(MANUSCRIPT_REVIEW), manuscript()
    review["publication_readiness"]["closest_work"][0]["source_id"] = second["id"]
    for section in draft["sections"]:
        section["text"] = section["text"].replace("{{citation:fixture-oracle}}", "{{citation:" + first["id"] + "}}")
    next(section for section in draft["sections"] if section["heading"] == "Related Work")["text"] += " {{citation:" + second["id"] + "}}"
    assert service.submit_manuscript(research_id, draft, review)["stage"] == "manuscript"
    receipt = json.loads(service.artifact_path(research_id, "manuscript-review").read_bytes())
    assert receipt["review"]["publication_readiness"]["closest_work"][0]["source_id"] == second["id"]
    expected = {}
    for source in (first, second):
        for field, hash_field in (("metadata_path", "metadata_sha256"), ("raw_path", "sha256"), ("text_path", "text_sha256")):
            bindings = [key for key, artifact in service.status(research_id)["artifacts"].items()
                        if artifact["sha256"] == source[hash_field] and
                        service.artifact_path(research_id, key).relative_to(service.root / research_id).as_posix() == "research/" + source[field]]
            assert len(bindings) == 1
            content = service.artifact_path(research_id, bindings[0]).read_bytes()
            assert hashlib.sha256(content).hexdigest() == source[hash_field]
            expected[source[field]] = content
        assert expected[source["metadata_path"]].startswith(b"<?xml")
        assert source["arxiv_id"].encode() in expected[source["metadata_path"]]
        assert expected[source["raw_path"]].startswith(b"%PDF")
    # Equal extracted text from different versions still needs both exact paths.
    assert first["text_sha256"] == second["text_sha256"] and first["text_path"] != second["text_path"]
    monkeypatch.setenv("PYPANDOC_PANDOC", pandoc)
    assert service.export(research_id)["stage"] == "exported"
    canonical = service.artifact_path(research_id, "manuscript").read_text(encoding="utf-8")
    assert "1311.3903v1" in canonical and "1311.3903v2" in canonical
    with zipfile.ZipFile(service.artifact_path(research_id, "reproducibility")) as archive:
        inventory = json.loads(archive.read("inventory.json"))
        for path, content in expected.items():
            assert archive.read(path) == content
            assert inventory[path]["sha256"] == hashlib.sha256(content).hexdigest()
            assert inventory[path]["size"] == len(content)
        for key in ("authoring-literature", "authoring-selected-literature"):
            assert receipt[key.replace("-", "_") + "_sha256"] == service.status(research_id)["artifacts"][key]["sha256"]
    assert runner.calls == 1 and all(service.artifact_path(research_id, key).read_bytes() == content for key, content in before.items())


def test_arxiv_request_aliases_retain_one_version_and_cannot_select_another_identity(setup):
    service, runner, research_id = measured(setup)
    original = {key: service.artifact_path(research_id, key).read_bytes() for key in ("plan", "observations", "analysis", "execution", "selected-literature")}
    service.collector = collect_arxiv_preprint
    queries = ["arXiv:1311.3903v1", "10.48550/arXiv.1311.3903v1"]
    state = service.collect_authoring_literature(research_id, [queries[0]])
    source = state["authoring_literature"]["sources"][0]
    expected_id = "source-" + hashlib.sha256(b"arxiv:1311.3903v1").hexdigest()[:20]
    assert source["id"] == expected_id and "doi" not in source
    first_index = service.artifact_path(research_id, "authoring-literature")
    first_index_bytes = first_index.read_bytes()
    service.select_authoring_literature(research_id, [{**STUDY_REVIEW["selected_sources"][0], "source_id": expected_id}])
    retained = {key: service.artifact_path(research_id, key).read_bytes() for key in service.status(research_id)["artifacts"]
                if key not in {"authoring-literature", "authoring-selected-literature"}}
    state = service.collect_authoring_literature(research_id, [queries[1]])
    repeated = state["authoring_literature"]["sources"][0]
    assert repeated["id"] == expected_id and repeated["arxiv_id"] == source["arxiv_id"]
    assert repeated["metadata_sha256"] == source["metadata_sha256"]
    assert repeated["metadata_path"] != source["metadata_path"]
    assert state["authoring_selection"] is None
    assert state["authoring_literature"]["searches"][0]["query"] == queries[1]
    assert all(search["resolved_ids"] == [expected_id] for search in state["authoring_literature"]["searches"])
    state = service.select_authoring_literature(research_id, [{**STUDY_REVIEW["selected_sources"][0], "source_id": expected_id}])
    assert {source["id"] for source in state["literature"]["sources"]} == {"fixture-oracle", expected_id}
    assert first_index.read_bytes() == first_index_bytes
    assert all(service.artifact_path(research_id, key).read_bytes() == content for key, content in retained.items())
    for identity in ("arxiv:1311.3903v2", "10.48550/arxiv.1311.3903v1"):
        other_id = "source-" + hashlib.sha256(identity.encode()).hexdigest()[:20]
        assert other_id != expected_id
        invalid = copy.deepcopy(MANUSCRIPT_REVIEW)
        invalid["publication_readiness"]["closest_work"][0]["source_id"] = other_id
        with pytest.raises(WorkflowError) as rejected:
            service.submit_manuscript(research_id, manuscript(), invalid)
        assert rejected.value.code == "PUBLICATION_EVIDENCE_INVALID"
    assert runner.calls == 1 and all(service.artifact_path(research_id, key).read_bytes() == content for key, content in original.items())


def test_unselected_authoring_source_cannot_approve_closest_work_and_new_collections_retain_history(setup):
    service, runner, research_id = measured(setup)
    def distinct(*args, **kwargs):
        evidence = collect(*args, **kwargs)
        evidence["sources"][0]["id"] = "authoring-closest"
        return evidence
    service.collector = distinct
    service.collect_authoring_literature(research_id, ["Retrieve a distinct synthetic closest study"])
    first = service.artifact_path(research_id, "authoring-literature")
    first_bytes = first.read_bytes()
    review = copy.deepcopy(MANUSCRIPT_REVIEW)
    review["publication_readiness"]["closest_work"][0]["source_id"] = "authoring-closest"
    draft = manuscript()
    next(section for section in draft["sections"] if section["heading"] == "Related Work")["text"] += " {{citation:authoring-closest}}"
    with pytest.raises(WorkflowError, match="selected full-text"):
        service.submit_manuscript(research_id, draft, review)
    selected = [{**STUDY_REVIEW["selected_sources"][0], "source_id": "authoring-closest"}]
    service.select_authoring_literature(research_id, selected)
    service.collect_authoring_literature(research_id, ["Retrieve another distinct synthetic closest study"])
    assert service.status(research_id)["authoring_selection"] is None
    assert first.read_bytes() == first_bytes and runner.calls == 1


def test_redesigned_child_copies_parent_authoring_raw_evidence_and_archives_exact_bytes(setup, pandoc, monkeypatch):
    service, runner, research_id = measured(setup)
    from test_workflow import redesign_review
    service.collect_authoring_literature(research_id, ["Inspect closest-work methods before requesting independent validation"])
    service.select_authoring_literature(research_id, copy.deepcopy(STUDY_REVIEW["selected_sources"]))
    service.submit_manuscript(research_id, manuscript(), redesign_review())
    parent = service.status(research_id)
    protocol_bytes = service.artifact_path(research_id, "plan").read_bytes()
    expected = {key: service.artifact_path(research_id, key).read_bytes() for key in parent["artifacts"]
                if key.startswith(("authoring-literature", "authoring-selected-literature", "literature-"))}
    child = service.redesign_study(research_id)
    for key, data in expected.items():
        assert service.artifact_path(child["id"], "prior-study-" + research_id + "-" + key).read_bytes() == data
    assert "selected-literature" not in child["artifacts"] and "study-review" not in child["artifacts"]
    assert child["execution_attempt"] == 0 and runner.calls == 1
    prepare(service, child["id"])
    service.start_experiment(child["id"])
    assert finished(service, child["id"])["stage"] == "analyzed"
    service.submit_manuscript(child["id"], manuscript(), MANUSCRIPT_REVIEW)
    monkeypatch.setenv("PYPANDOC_PANDOC", pandoc)
    service.export(child["id"])
    with zipfile.ZipFile(service.artifact_path(child["id"], "reproducibility")) as archive:
        inventory = json.loads(archive.read("inventory.json"))
        for key, data in expected.items():
            path = parent["artifacts"][key]
            matching = [name for name, entry in inventory.items() if name.startswith("prior-studies/" + research_id + "/") and
                        entry["sha256"] == path["sha256"] and entry["size"] == len(data)]
            assert matching and all(archive.read(name) == data for name in matching)
    assert service.artifact_path(research_id, "plan").read_bytes() == protocol_bytes
    assert service.status(research_id)["execution_attempt"] == 1 and service.status(child["id"])["execution_attempt"] == 1
    assert runner.calls == 2  # Separate synthetic child execution, never redispatch of parent SCI1.


@pytest.mark.parametrize("method,params,operation", [
    ("workflow.collectAuthoringLiterature", {"queries": ["Closest primary methods and findings"]}, "collect_authoring_literature"),
    ("workflow.selectAuthoringLiterature", {"selectedSources": STUDY_REVIEW["selected_sources"]}, "select_authoring_literature"),
])
def test_authoring_literature_ipc_has_explicit_bounded_contract(method, params, operation):
    identifier = "research-abcdefabcdef"
    frame = {"id": "authoring-lit", "method": method, "params": {"researchId": identifier, **params}}
    assert ipc.request(json.dumps(frame).encode()) == frame
    calls = []
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=SimpleNamespace(**{operation: lambda *args: calls.append(args) or {"id": identifier}})), None)
    try:
        assert dispatcher.execute(method, frame["params"]) == {"id": identifier}
    finally:
        dispatcher._pool.shutdown()
    assert calls == [(identifier, next(iter(params.values())))]
    for replacement in ([], [1], ["x"] if "queries" in params else ["untyped"]):
        with pytest.raises(ValueError):
            ipc.request(json.dumps({**frame, "params": {"researchId": identifier, next(iter(params)): replacement}}).encode())

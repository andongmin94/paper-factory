"""Synthetic submission contracts; no scientific result or publication is approved."""

import base64
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from paper_factory import conversion
from paper_factory.author import submission_author_status
from paper_factory.autonomous import science
from paper_factory.autonomous.submission_rendering import prepare_formatting_source
from paper_factory.autonomous.validation import analyze_validation, projected_results
from test_autonomous_science import protocol, observations, literature, valid_draft


def test_planning_guidance_distinguishes_legacy_analysis_from_declared_validation():
    prompt = science.planning_prompt("Synthetic inspected source context.", "Synthetic bounded study goal.")
    legacy = prompt.index("Without validation_contract,")
    supported = prompt.index("With a new source-bound\nSubmissionContract and declared validation_contract,")
    assert "legacy trusted pooled descriptive statistics" in prompt[legacy:supported]
    assert "that route cannot compute bootstrap, confidence intervals" in prompt[legacy:supported]
    assert "native count, mean, min and max within each" in prompt[supported:]
    assert "IEEE-754 binary64 left-fold addition in declared_units" in prompt[supported:]
    assert "All later-minus-earlier condition" in prompt[supported:]
    assert "No pooled, median or stdev summaries" in prompt[supported:]
    assert "conditional seed_cluster_bootstrap intervals" in prompt[supported:]
    assert "at least three distinct seed clusters in every stratum" in prompt[supported:]
    assert "Do not propose arbitrary tests or population generalization from fixed examples." in prompt[supported:]
    assert "Do not request bootstrap, confidence\nintervals, hypothesis tests, or stratified inference." not in prompt


def fixture(label, content):
    return {"label": label, "encoding": "base64", "content": base64.b64encode(content).decode(),
            "sha256": hashlib.sha256(content).hexdigest()}


def validation_data(protocol, observations, *, mode="empirical", bootstrap=False):
    plan, raw = protocol.model_dump(mode="json"), copy.deepcopy(observations)
    if bootstrap:
        plan["seeds"].append(79)
        raw["observations"] += [{**row, "seed": 79, "value": row["value"] + 1}
                                for row in raw["observations"] if row["seed"] == plan["seeds"][0]]
    units = sorted({(row["seed"], row["unit_id"]) for row in raw["observations"]})
    declared = [{"seed": seed, "unit_id": unit, "stratum": "bounded-family"} for seed, unit in units]
    spec = {"mode": mode, "declared_units": declared, "finite_domain_label": "declared-domain" if mode == "finite_enumeration" else None,
            "uncertainty": "seed_cluster_bootstrap" if bootstrap else "none", "independent_sampling": bootstrap,
            "sampling_basis": "Synthetic independent seed-cluster assumption, not a scientific population claim.",
            "bootstrap_seed": 719, "bootstrap_replicates": 200, "confidence_level": .95,
            "oracle_sources": [{"source_id": "synthetic-source", "text_sha256": "a" * 64,
                                "quote": "Synthetic oracle source binding fixture only; its scientific semantics remain unverified. " * 2}]}
    raw["fixtures"] += [fixture("control-input", b"input"), fixture("expected-output", b"expected"),
                        fixture("actual-output", b"expected"), fixture("fault-output", b"intentional fault")]
    raw["controls"] = [{"name": "positive known response", "passed": True, "details": "An actually retained equal fixture comparison.",
                        "input_fixture": "control-input", "expected_fixture": "expected-output", "actual_fixture": "actual-output", "comparison": "equal"},
                       {"name": "negative intentional fault", "passed": True, "details": "An actually retained different fixture comparison.",
                        "input_fixture": "control-input", "expected_fixture": "expected-output", "actual_fixture": "fault-output", "comparison": "different"}]
    if mode == "finite_enumeration":
        raw["fixtures"].append(fixture("declared-domain", json.dumps(declared).encode()))
    plan["validation_contract"] = spec
    return plan, raw, spec


def contract(mode):
    return {"article_type": mode, "language": "English", "selected_venue": None,
            "core_claim": "Synthetic draft structure only; no scientific contribution is approved."}


def claim(mode, *, proof=None):
    return {"mode": mode, "claim": "Synthetic observed-claim binding only; no scientific outcome is asserted.",
            "scope": "Only the declared synthetic retained fixture domain.", "outcome": "negative",
            "analysis_keys": ["error.condition_1.mean"] if mode != "formal" else [],
            "proof_section": "Proof" if proof else None, "proof_quote": proof}


def typed_draft(analysis):
    value = valid_draft()
    replacements = {"error.condition_1": "validation.cell_1", "error.condition_2": "validation.cell_2",
                    "error.paired_2_minus_1": "validation.cell_3"}
    for section in value["sections"]:
        for original, replacement in replacements.items():
            section["text"] = section["text"].replace(original, replacement)
        if section["heading"] == "Results":
            section["text"] += " Complete declared cell means: " + ", ".join(
                "{{result:" + key + "}}" for key in analysis["results"] if key.endswith(".mean")) + "."
    return value


def test_structured_controls_rederive_exact_comparison_and_terminal_false_claim(protocol, observations):
    plan, raw, spec = validation_data(protocol, observations)
    result = science._compute(raw, plan)
    assert result["controls"] == raw["controls"]
    evidence = science.derive_control_comparisons(raw)
    assert all(item["passed"] for item in evidence) and evidence[0]["expected_fixture_sha256"] == evidence[0]["actual_fixture_sha256"]
    raw["controls"][0]["actual_fixture"] = "fault-output"
    with pytest.raises(science.ControlFailure, match="recomputed"):
        science._compute(raw, plan)


def test_retained_stdlib_reproducer_recomputes_structured_control_proof(tmp_path, protocol, observations):
    plan, raw, _ = validation_data(protocol, observations)
    trusted = science.analyze(raw, science.ResearchPlan.model_validate(plan), tmp_path)
    completed = subprocess.run([sys.executable, str(tmp_path / "analysis.py")], capture_output=True,
                               text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert json.loads((tmp_path / "analysis-reproduced.json").read_bytes()) == trusted


@pytest.mark.parametrize("defect", ["inverted_positive", "inverted_negative", "ambiguous_role", "no_negative_role"])
def test_new_structured_controls_require_distinct_consistent_roles(protocol, observations, defect):
    plan, raw, _ = validation_data(protocol, observations)
    if defect == "inverted_positive":
        raw["controls"][0].update(comparison="different", actual_fixture="fault-output")
    elif defect == "inverted_negative":
        raw["controls"][1].update(comparison="equal", actual_fixture="actual-output")
    elif defect == "ambiguous_role": raw["controls"][0]["name"] = "positive negative control"
    else: raw["controls"][1]["name"] = "unnamed generic comparison"
    with pytest.raises(ValueError, match="positive|Positive|negative"):
        science._compute(raw, plan)


def test_legacy_analysis_keeps_original_numerical_json_and_control_contract(protocol, observations):
    baseline = science._compute(copy.deepcopy(observations), protocol.model_dump(mode="json"))
    # Actual pre-projection fixture output retained by the earlier source-frozen
    # attempt-04, normalized to LF for portability; this guards all historical
    # fields and numerical values, not a repeated call.
    original_json = (json.dumps(baseline, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    assert hashlib.sha256(original_json).hexdigest() == "61a6ea17122f8f44d16d054e7798a85e7f54d0ba80083eb5f5216bda530fa437"
    assert baseline["analysis_scope"] == science.ANALYSIS_SCOPE
    assert not any(key.startswith("validation.") for key in baseline["results"])
    assert baseline["results"]["error.condition_1.mean"]["value"] == 0
    assert baseline["results"]["error.condition_2.mean"]["value"] == 2
    assert baseline["controls"] == observations["controls"]


@pytest.mark.parametrize("bootstrap", [False, True])
def test_projected_validation_values_reproduce_without_extra_pooled_statistics(tmp_path, protocol, observations, bootstrap):
    plan, raw, spec = validation_data(protocol, observations, bootstrap=bootstrap)
    analysis = science.analyze(raw, science.ResearchPlan.model_validate(plan), tmp_path)
    receipt = analyze_validation(raw, plan, spec)
    projection = projected_results(receipt)
    assert projection and all(analysis["results"][key] == value for key, value in projection.items())
    assert projection["validation.cell_1.mean"]["value"] == receipt["strata"][0]["mean"]
    assert projection["validation.cell_1.mean"]["stratum"] == "bounded-family"
    assert projection["validation.cell_1.mean"]["validation_spec_sha256"] == receipt["spec_sha256"]
    assert analysis["schema_version"] == receipt["schema_version"] == 2
    assert all(key.startswith("validation.") for key in analysis["results"])
    assert not any(key.endswith((".median", ".stdev")) for key in analysis["results"])
    if bootstrap:
        assert projection["validation.cell_1.interval.lower"]["value"] == receipt["uncertainty"][0]["lower"]
        assert projection["validation.cell_1.interval.upper"]["value"] == receipt["uncertainty"][0]["upper"]
        assert "Conditional" in projection["validation.cell_1.interval.lower"]["scope"]
    else: assert not any(".interval." in key for key in projection)
    completed = subprocess.run([sys.executable, str(tmp_path / "analysis.py")], capture_output=True,
                               text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert json.loads((tmp_path / "analysis-reproduced.json").read_bytes()) == analysis


def test_actual_manuscript_and_citeproc_source_can_quote_bound_conditional_interval(tmp_path, protocol, observations, literature):
    plan, raw, spec = validation_data(protocol, observations, bootstrap=True)
    analysis = science._compute(raw, plan)
    value = typed_draft(analysis)
    for section in value["sections"]:
        if section["heading"] in {"Abstract", "Results"}:
            section["text"] += (" The conditional seed-cluster interval has retained endpoints "
                                "{{result:validation.cell_1.interval.lower}} and {{result:validation.cell_1.interval.upper}} events.")
    observed = claim("empirical")
    observed["analysis_keys"] = ["validation.cell_1.interval.lower", "validation.cell_1.interval.upper"]
    rendered = science.validate_and_render(value, science.ResearchPlan.model_validate(plan), analysis, literature,
                                          tmp_path / "draft", submission=contract("empirical"), observed_claim=observed)
    canonical = json.loads(Path(rendered["canonical_path"]).read_bytes())
    assert observed["analysis_keys"][0] in canonical["verified_result_refs"]["Abstract"]
    assert observed["analysis_keys"][1] in canonical["verified_result_refs"]["Results"]
    markdown = Path(rendered["markdown_path"])
    assert "Conditional cluster estimate / interval" in markdown.read_text(encoding="utf-8")
    assets = prepare_formatting_source(canonical, analysis, literature, markdown, tmp_path / "formatting")
    formatting = Path(assets["source_path"]).read_text(encoding="utf-8")
    assert "Conditional cluster estimate / interval" in formatting and "{{result:" not in formatting
    assert "seed-cluster interval has retained endpoints" in formatting


@pytest.mark.parametrize("defect", ["missing_fixture", "digest", "unsupported_comparison", "legacy_control"])
def test_structured_control_proof_rejects_unbound_or_claimed_only_data(protocol, observations, defect):
    plan, raw, _ = validation_data(protocol, observations)
    if defect == "missing_fixture": raw["controls"][0]["input_fixture"] = "absent"
    elif defect == "digest": raw["fixtures"][-1]["sha256"] = "b" * 64
    elif defect == "unsupported_comparison": raw["controls"][0]["comparison"] = "trust_model"
    else: raw["controls"][0] = {key: raw["controls"][0][key] for key in ("name", "passed", "details")}
    with pytest.raises(ValueError): science._compute(raw, plan)


def test_finite_validation_establishes_only_exact_declared_domain_and_no_uncertainty(protocol, observations):
    plan, raw, spec = validation_data(protocol, observations, mode="finite_enumeration")
    receipt = analyze_validation(raw, plan, spec)
    assert receipt["supported"] and receipt["passed"] and receipt["complete_declared_domain"]
    assert receipt["uncertainty"] == [] and len(receipt["strata"]) == 3
    assert "population" in receipt["scope"] and science._compute(raw, plan)["observation_digest"] == hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


@pytest.mark.parametrize("defect", ["missing_domain", "different_domain", "partial_grid", "duplicate_unit", "undeclared_unit"])
def test_finite_coverage_rejects_incomplete_and_self_relabelled_domain(protocol, observations, defect):
    plan, raw, spec = validation_data(protocol, observations, mode="finite_enumeration")
    if defect == "missing_domain": raw["fixtures"].pop()
    elif defect == "different_domain": raw["fixtures"][-1] = fixture("declared-domain", b"[]")
    elif defect == "partial_grid": raw["observations"].pop()
    elif defect == "duplicate_unit": spec["declared_units"].append(copy.deepcopy(spec["declared_units"][0]))
    else: raw["observations"][0]["unit_id"] = "not-declared"
    if defect in {"duplicate_unit", "undeclared_unit"}:
        with pytest.raises(ValueError): analyze_validation(raw, plan, spec)
    else:
        result = analyze_validation(raw, plan, spec)
        assert not result["passed"] and result["blockers"]


def test_empirical_strata_and_conditional_seed_cluster_uncertainty_are_reproducible(protocol, observations):
    plan, raw, spec = validation_data(protocol, observations, bootstrap=True)
    before = copy.deepcopy(raw)
    receipt = analyze_validation(raw, plan, spec)
    assert receipt == analyze_validation(raw, plan, spec) and raw == before and receipt["passed"]
    assert all(item["seed_clusters"] == 3 and item["replicates"] == 200 and item["lower"] <= item["upper"] for item in receipt["uncertainty"])
    assert all("Conditional" in item["scope"] for item in receipt["uncertainty"])
    assert receipt["strata"][0]["count"] == 9


@pytest.mark.parametrize("defect", ["not_independent", "no_basis", "two_clusters", "finite", "bounds"])
def test_uncertainty_never_promotes_fixed_examples_to_population_inference(protocol, observations, defect):
    plan, raw, spec = validation_data(protocol, observations, bootstrap=defect != "two_clusters")
    spec["uncertainty"] = "seed_cluster_bootstrap"
    if defect == "not_independent": spec["independent_sampling"] = False
    elif defect == "no_basis": spec["sampling_basis"] = ""
    elif defect == "two_clusters": spec["independent_sampling"] = True
    elif defect == "finite": spec["mode"] = "finite_enumeration"
    else: spec["bootstrap_replicates"] = 2001
    if defect == "bounds":
        with pytest.raises(ValueError): analyze_validation(raw, plan, spec)
    else:
        result = analyze_validation(raw, plan, spec)
        assert not result["passed"] and result["blockers"]


def test_arbitrary_formal_proof_is_explicitly_unsupported_not_auto_verified(protocol, observations):
    plan, raw, spec = validation_data(protocol, observations, mode="formal")
    receipt = analyze_validation(raw, plan, spec)
    assert not receipt["supported"] and not receipt["passed"] and receipt["status"] == "unsupported"
    assert "proof correctness" in receipt["blockers"][0]


@pytest.mark.parametrize("mode", ["empirical", "finite_enumeration", "formal"])
def test_manuscript_structure_and_observed_claim_match_article_type(tmp_path, protocol, observations, literature, mode):
    analysis = science._compute(observations, protocol.model_dump(mode="json"))
    value = valid_draft()
    proof = None
    if mode == "finite_enumeration":
        for section in value["sections"]:
            if section["heading"] == "Experimental Setup": section["heading"] = "Domain and Completeness"
        value["sections"] = [item for item in value["sections"] if item["heading"] != "Threats to Validity"]
    elif mode == "formal":
        proof = "This synthetic derivation states assumptions and its logical consequences without asserting a genuine mathematical proof or verified theorem. " * 3
        value["sections"] = [{"heading": heading, "text": proof * 2 + (" {{citation:source-oracle}}" if heading == "Related Work" else "")}
                             for heading in science.FORMAL_SECTIONS]
    rendered = science.validate_and_render(value, protocol, analysis, literature, tmp_path / mode,
                                          submission=contract(mode), observed_claim=claim(mode, proof=proof))
    canonical = json.loads(Path(rendered["canonical_path"]).read_bytes())
    assert {item["heading"] for item in canonical["sections"]} == set(science.manuscript_sections(contract(mode)))
    assert canonical["observed_claim"]["outcome"] == "negative" and canonical["submission_status"] == "venue_and_visual_verification_pending"
    prompt = science.writing_prompt(protocol, analysis, literature, {}, submission=contract(mode), observed_claim=claim(mode, proof=proof))
    assert "EVERY claim obligation" in prompt and "selected_venue=null" in prompt


def test_author_completeness_never_invents_declarations_or_confirms_identity():
    empty = submission_author_status()
    assert not empty["metadata_complete"] and not empty["verified"] and len(empty["missing"]) == 3
    filled = submission_author_status({"display_name": "Synthetic Author", "email": "fixture@example.org", "affiliation": "Synthetic fixture affiliation"})
    assert filled["metadata_complete"] and not filled["verified"] and filled["declarations_status"] == "author_confirmation_pending"


def test_separate_citeproc_assets_preserve_original_science_and_unknown_venue(tmp_path, protocol, observations, literature, pandoc):
    analysis = science._compute(observations, protocol.model_dump(mode="json"))
    rendered = science.validate_and_render(valid_draft(), protocol, analysis, literature, tmp_path / "draft")
    source = Path(rendered["markdown_path"])
    original = source.read_bytes()
    canonical = json.loads(Path(rendered["canonical_path"]).read_bytes())
    assets = prepare_formatting_source(canonical, analysis, literature, source, tmp_path / "formatting")
    assert source.read_bytes() == original and not assets["venue_verified"] and assets["csl_path"] is None
    formatting = Path(assets["source_path"])
    assert "[@source-oracle]" in formatting.read_text(encoding="utf-8")
    assert len(json.loads(Path(assets["bibliography_path"]).read_bytes())) == len(canonical["citation_evidence"])
    output = formatting.with_suffix(".docx")
    receipt = conversion.convert(formatting, output, pandoc=pandoc, bibliography=Path(assets["bibliography_path"]), line_numbers=True)
    assert receipt["bibliography_sha256"] == assets["bibliography_sha256"] and output.is_file()
    from docx import Document
    assert "[@source-oracle]" not in "\n".join(item.text for item in Document(output).paragraphs)


def test_formatting_uses_retained_journal_metadata_and_keeps_unknown_copy_version(tmp_path, protocol, observations, literature):
    literature["sources"][0].update(copy_type="repository_copy", publication_version="unknown",
                                       original_scope="full_text", scope="full_text")
    source = literature["sources"][0]
    # Canonical rendering copy-proof rederivation belongs to native workflow tests.
    # This helper is supplied an already inspected source with complete receipt fields.
    source.update(identity_proof_sha256="b" * 64, discovery_proof_sha256="c" * 64,
                  metadata_sha256="d" * 64, pdf_sha256="e" * 64,
                  text_sha256="f" * 64, copy_url="https://zenodo.org/records/1/files/synthetic.pdf")
    analysis = science._compute(observations, protocol.model_dump(mode="json"))
    rendered = science.validate_and_render(valid_draft(), protocol, analysis, literature, tmp_path / "draft")
    work = {"status": "ok", "message": {"DOI": source["doi"], "title": [source["title"]],
                        "author": [{"given": "Example", "family": "Author"}],
                        "published": {"date-parts": [[2024]]}, "type": "journal-article",
                        "container-title": ["Synthetic retained metadata journal"], "volume": "7", "page": "12-19"}}
    assets = prepare_formatting_source(json.loads(Path(rendered["canonical_path"]).read_bytes()), analysis,
                                      literature, Path(rendered["markdown_path"]), tmp_path / "formatting",
                                      metadata_records={source["id"]: work})
    entry = json.loads(Path(assets["bibliography_path"]).read_bytes())[0]
    assert entry["container-title"] == work["message"]["container-title"][0] and entry["volume"] == "7"
    assert entry["page"] == "12-19" and entry["note"] == "Inspected public copy; publication version unknown"
    assert assets["missing_bibliographic_fields"][0]["fields"] == ["issue"] and not assets["venue_verified"]


def test_every_pdf_page_is_raster_bound_but_visual_review_remains_pending(tmp_path, pandoc):
    source = tmp_path / "pages.md"
    source.write_text("# Synthetic page coverage\n\n" + "Retained synthetic page text for complete raster binding. " * 900, encoding="utf-8")
    pdf = source.with_suffix(".pdf")
    report = conversion.convert(source, pdf, pandoc=pandoc)
    receipt = conversion.inspect_pdf_quality(pdf, tmp_path / "page-images", typst_source=pdf.with_suffix(".typ"))
    assert receipt["page_count"] > 1 and len(receipt["pages"]) == receipt["page_count"]
    assert receipt["automatic_checks"] and receipt["visual_review_status"] == "pending" and receipt["status"] == "pending_visual_review"
    assert all(Path(item["image_path"]).is_file() and item["text_chars"] > 0 for item in receipt["pages"])
    assert receipt["typst_sha256"] == report["typst_sha256"]
    repeat = conversion.inspect_pdf_quality(pdf, tmp_path / "page-images", typst_source=pdf.with_suffix(".typ"))
    assert repeat == receipt
    changed = pdf.with_suffix(".typ")
    changed.write_text(changed.read_text(encoding="utf-8") + "\nUnrelated altered rendering source", encoding="utf-8")
    altered = conversion.inspect_pdf_quality(pdf, tmp_path / "changed-images", typst_source=changed)
    assert altered["status"] == "failed" and not altered["automatic_checks"] and not any("image_path" in item for item in altered["pages"])


def test_missing_pdf_raster_source_is_truthfully_unverified(tmp_path, pandoc):
    source = tmp_path / "page.md"; source.write_text("# Retained text\n\nSynthetic fixture only.", encoding="utf-8")
    pdf = source.with_suffix(".pdf"); conversion.convert(source, pdf, pandoc=pandoc)
    receipt = conversion.inspect_pdf_quality(pdf, tmp_path / "unavailable")
    assert receipt["status"] == "render_unavailable" and not receipt["automatic_checks"] and receipt["visual_review_status"] == "pending"

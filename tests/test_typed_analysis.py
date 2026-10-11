"""Synthetic typed analysis boundaries; no real study or model is executed."""

import copy
import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

from paper_factory.autonomous import science
from paper_factory.autonomous.validation import analyze_validation, projected_results
from paper_factory.workflow import (_claim_validation_bindings, _freeze, _verified_claim_validation, WorkflowError)
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import Workspace, write_json
from test_autonomous_science import protocol, observations, literature
from test_submission_quality import validation_data, typed_draft, contract, claim


def three_condition_strata(protocol, observations):
    plan, raw, spec = validation_data(protocol, observations)
    plan["units_per_seed"] = 6
    plan["conditions"] = ["production", "comparator_a", "comparator_b"]
    spec["declared_units"] = [{"seed": seed, "unit_id": f"{stratum}-{unit}", "stratum": stratum}
                              for seed in plan["seeds"] for stratum in ("alpha", "beta", "gamma") for unit in (0, 1)]
    raw["observations"] = [
        {"seed": item["seed"], "unit_id": item["unit_id"], "condition": condition, "metric": "error",
         "value": index + (0, 2 + index % 3, 9 - index % 2)[condition_index]}
        for index, item in enumerate(spec["declared_units"])
        for condition_index, condition in enumerate(plan["conditions"])
    ]
    return plan, raw, spec


def test_all_pairs_with_explicit_baselines_and_no_extra_statistics(protocol, observations):
    plan, raw, spec = three_condition_strata(protocol, observations)
    before = copy.deepcopy((plan, raw))
    analysis = science._compute(raw, plan)
    receipt = analyze_validation(raw, plan, spec)
    assert analysis["schema_version"] == receipt["schema_version"] == 2
    assert len(analysis["summaries"]) == len(analysis["paired_deltas"]) == 9
    assert len(receipt["strata"]) == 18
    assert all(key.startswith("validation.cell_") for key in analysis["results"])
    assert not any(key.endswith((".median", ".stdev")) for key in analysis["results"])
    assert all(set(cell) == {"stratum", "metric", "condition", "kind", "unit", "baseline", "count", "mean", "min", "max"}
               for cell in receipt["strata"])
    third_pairs = [cell for cell in receipt["strata"] if cell["condition"] == "comparator_b" and cell["baseline"] == "comparator_a"]
    assert len(third_pairs) == 3 and all(cell["count"] == 4 for cell in third_pairs)
    values = {(row["seed"], row["unit_id"], row["condition"]): row["value"] for row in raw["observations"]}
    for cell in third_pairs:
        units = [item for item in spec["declared_units"] if item["stratum"] == cell["stratum"]]
        expected = [values[item["seed"], item["unit_id"], "comparator_b"] - values[item["seed"], item["unit_id"], "comparator_a"] for item in units]
        assert cell["mean"] == sum(expected) / 4 and (cell["min"], cell["max"]) == (min(expected), max(expected))
    assert (plan, raw) == before
    reordered = copy.deepcopy(raw)
    reordered["observations"].reverse()
    assert analyze_validation(reordered, plan, spec) == receipt


def test_binary64_left_fold_matches_declared_order_not_statistics_mean(protocol, observations):
    plan, raw, spec = three_condition_strata(protocol, observations)
    sequence = [1e16, 1.0, -1e16, 1.0]
    units = [item for item in spec["declared_units"] if item["stratum"] == "alpha"]
    by_unit = {(item["seed"], item["unit_id"]): value for item, value in zip(units, sequence)}
    for row in raw["observations"]:
        if row["condition"] == "production" and (row["seed"], row["unit_id"]) in by_unit:
            row["value"] = by_unit[row["seed"], row["unit_id"]]
    receipt = analyze_validation(raw, plan, spec)
    cell = next(cell for cell in receipt["strata"] if cell["stratum"] == "alpha" and cell["condition"] == "production" and cell["kind"] == "level")
    assert cell["mean"] == .25 != statistics.mean(sequence)
    paired = next(cell for cell in receipt["strata"] if cell["stratum"] == "alpha" and cell["condition"] == "comparator_a" and cell["baseline"] == "production")
    comparator = next(cell for cell in receipt["strata"] if cell["stratum"] == "alpha" and cell["condition"] == "comparator_a" and cell["kind"] == "level")
    assert paired["mean"] == 5.25 != comparator["mean"] - cell["mean"]
    reordered_spec = copy.deepcopy(spec)
    reordered_spec["declared_units"] = [item for item in spec["declared_units"] if item["stratum"] != "alpha"] + [units[0], units[2], units[1], units[3]]
    reordered = analyze_validation(raw, plan, reordered_spec)
    other = next(cell for cell in reordered["strata"] if cell["stratum"] == "alpha" and cell["condition"] == "production" and cell["kind"] == "level")
    assert other["mean"] == .5


@pytest.mark.parametrize("defect", ["missing", "duplicate", "unknown_unit", "null", "control"])
def test_whole_grid_failure_has_no_publishable_numeric_projection(protocol, observations, defect):
    plan, raw, spec = three_condition_strata(protocol, observations)
    if defect == "missing": raw["observations"].pop()
    elif defect == "duplicate": raw["observations"][-1] = copy.deepcopy(raw["observations"][0])
    elif defect == "unknown_unit": raw["observations"][0]["unit_id"] = "undeclared"
    elif defect == "null": raw["observations"][0]["value"] = None
    else: raw["controls"][0].update(passed=False, actual_fixture="fault-output")
    before = copy.deepcopy(raw)
    if defect in {"missing", "control"}:
        receipt = analyze_validation(raw, plan, spec)
        assert not receipt["passed"] and receipt["strata"] == [] and projected_results(receipt) == {}
    else:
        with pytest.raises(ValueError): analyze_validation(raw, plan, spec)
    with pytest.raises(ValueError): science._compute(raw, plan)
    assert raw == before


def test_all_pairs_are_retained_reproduced_and_rendered_without_pooled_table(tmp_path, protocol, observations, literature):
    plan, raw, spec = three_condition_strata(protocol, observations)
    analysis = science.analyze(raw, science.ResearchPlan.model_validate(plan), tmp_path / "analysis")
    completed = subprocess.run([sys.executable, str(tmp_path / "analysis" / "analysis.py")], capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert json.loads((tmp_path / "analysis" / "analysis-reproduced.json").read_bytes()) == analysis
    table = science._validation_tables(analysis)
    assert "comparator\\_b minus comparator\\_a" in table and "| Min | Max |" in table
    assert "comparator minus first condition" not in table and science._tables(analysis) == ""
    draft = typed_draft(analysis)
    paired = next(key for key, value in analysis["results"].items() if value.get("baseline") == "comparator_a" and key.endswith(".mean"))
    for section in draft["sections"]:
        if section["heading"] == "Abstract": section["text"] = "Retained synthetic means {{result:validation.cell_1.mean}} and matched third comparison {{result:" + paired + "}} events."
    observed = claim("empirical")
    observed["analysis_keys"] = [paired]
    rendered = science.validate_and_render(draft, science.ResearchPlan.model_validate(plan), analysis, literature, tmp_path / "draft",
                                          submission=contract("empirical"), observed_claim=observed)
    markdown = Path(rendered["markdown_path"]).read_text(encoding="utf-8")
    assert table in markdown and "Mean (SD)" not in markdown and paired in json.loads(Path(rendered["canonical_path"]).read_bytes())["verified_result_refs"]["Abstract"]


def test_typed_manuscript_cannot_omit_a_declared_third_pair(tmp_path, protocol, observations, literature):
    plan, raw, _ = three_condition_strata(protocol, observations)
    analysis = science._compute(raw, plan)
    draft = typed_draft(analysis)
    third = next(key for key, value in analysis["results"].items() if value.get("baseline") == "comparator_a" and key.endswith(".mean"))
    for section in draft["sections"]:
        section["text"] = section["text"].replace("{{result:" + third + "}}", "omitted")
    with pytest.raises(ValueError, match="complete declared cell"):
        science.validate_and_render(draft, science.ResearchPlan.model_validate(plan), analysis, literature, tmp_path)


def test_all_pair_interval_identity_includes_its_baseline(protocol, observations):
    plan, raw, spec = three_condition_strata(protocol, observations)
    plan["seeds"].append(79)
    first = plan["seeds"][0]
    spec["declared_units"] += [{**item, "seed": 79} for item in spec["declared_units"] if item["seed"] == first]
    raw["observations"] += [{**row, "seed": 79, "value": row["value"] + 1} for row in raw["observations"] if row["seed"] == first]
    spec.update(uncertainty="seed_cluster_bootstrap", independent_sampling=True)
    receipt = analyze_validation(raw, plan, spec)
    results = projected_results(receipt)
    assert len(receipt["uncertainty"]) == len(receipt["strata"]) == 18
    for index, cell in enumerate(receipt["strata"], 1):
        interval = next(item for item in receipt["uncertainty"] if all(item[key] == cell[key] for key in ("stratum", "metric", "condition", "kind", "baseline")))
        value = results[f"validation.cell_{index}.interval.lower"]
        assert value["value"] == interval["lower"] and value["baseline"] == cell["baseline"]


def test_left_fold_intermediate_overflow_is_terminal_without_analysis_file(tmp_path, protocol, observations):
    plan, raw, spec = three_condition_strata(protocol, observations)
    units = [item for item in spec["declared_units"] if item["stratum"] == "alpha"]
    by_unit = {(item["seed"], item["unit_id"]): value for item, value in zip(units, [1e308, 1e308, -1e308, -1e308])}
    for row in raw["observations"]:
        if row["condition"] == "production" and (row["seed"], row["unit_id"]) in by_unit:
            row["value"] = by_unit[row["seed"], row["unit_id"]]
    with pytest.raises(ValueError, match="overflowed"):
        science.analyze(raw, science.ResearchPlan.model_validate(plan), tmp_path)
    assert not (tmp_path / "analysis.json").exists()


def test_new_analysis_version_is_native_owned_not_a_research_plan_choice(protocol, observations):
    plan, raw, _ = three_condition_strata(protocol, observations)
    plan["schema_version"] = 1
    with pytest.raises(ValueError): science.ResearchPlan.model_validate(plan)
    plan.pop("schema_version")
    assert science._compute(raw, plan)["schema_version"] == 2


def test_exact_historical_v1_analysis_receipt_is_hash_verified_without_rewrite(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "historical-typed-analysis-v1.json"
    raw = fixture.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "69e662a848a351a019e43ad4855fa3ba21a86cab9c1d416ae5cc4307a4e6ba15"
    frozen = json.loads(raw)
    assert science._compute(frozen["observations"], frozen["protocol"], schema_version=1) == frozen["analysis"]
    assert analyze_validation(frozen["observations"], frozen["protocol"], frozen["protocol"]["validation_contract"], schema_version=1) == frozen["validation"]
    ws = Workspace.create(tmp_path / "historical")
    record = Workflow(project_id="synthetic", goal="Historical synthetic byte preservation only.")
    for key, value in (("plan", frozen["protocol"]), ("observations", frozen["observations"]), ("analysis", frozen["analysis"])):
        path = ws.path(key + ".json"); write_json(path, value); _freeze(ws, record, key, path)
    receipt = {"origin": "native_deterministic_analysis", "bindings": _claim_validation_bindings(ws, record), "value": frozen["validation"]}
    path = ws.path("claim-validation.json"); write_json(path, receipt); _freeze(ws, record, "claim-validation", path)
    before = {key: ws.path(value.path).read_bytes() for key, value in record.artifacts.items()}
    state = record.model_dump(mode="json")
    assert _verified_claim_validation(ws, record, science.ResearchPlan.model_validate(frozen["protocol"])) == receipt
    assert before == {key: ws.path(value.path).read_bytes() for key, value in record.artifacts.items()} and record.model_dump(mode="json") == state
    ws.path("analysis.json").write_bytes(before["analysis"] + b" ")
    with pytest.raises(WorkflowError, match="changed"):
        _verified_claim_validation(ws, record, science.ResearchPlan.model_validate(frozen["protocol"]))

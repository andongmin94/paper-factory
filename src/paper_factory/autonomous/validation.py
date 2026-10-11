"""Deterministic coverage and conditional uncertainty, never scientific approval."""

import base64
import hashlib
import json
import math
import random
import statistics


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _summary(values, *, schema_version=2):
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError("Validation requires finite retained measurements")
    if schema_version == 1:
        value = {"count": len(values), "mean": statistics.mean(values), "median": statistics.median(values),
                 "min": min(values), "max": max(values), "stdev": statistics.stdev(values) if len(values) > 1 else None}
    else:
        total = 0.0
        for item in values:
            total += float(item)
            if not math.isfinite(total):
                raise ValueError("Validation statistics overflowed")
        value = {"count": len(values), "mean": total / len(values), "min": min(values), "max": max(values)}
    if any(type(item) in {int, float} and not math.isfinite(item) for item in value.values()):
        raise ValueError("Validation statistics overflowed")
    return value


def _percentile(values, probability):
    values = sorted(values)
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[min(lower + 1, len(values) - 1)] * fraction


def analyze_validation(observations: dict, protocol: dict, spec: dict, *, control_comparator=None, schema_version=2) -> dict:
    """Recompute a frozen declared-domain contract without altering legacy analysis.

    Bootstrap intervals describe seed-cluster resampling under the declared
    independent sampling assumption. This helper does not prove that assumption
    or turn a benchmark's fixed cases into a population sample.
    """
    if type(schema_version) is not int or schema_version not in {1, 2}:
        raise ValueError("Unsupported native validation schema version")
    mode = spec["mode"]
    receipt = {"supported": True, "passed": False, "status": "incomplete", "blockers": [],
               "scope": "Declared-domain coverage and conditional seed-cluster analysis only; no novelty, oracle semantics, population representativeness or scientific approval is attested.",
               "complete_declared_domain": False, "strata": [], "uncertainty": [], "controls": [],
                "spec_sha256": _digest(spec)}
    if schema_version == 2:
        receipt["schema_version"] = 2
        receipt["statistic_definition"] = ("Only count, mean, min and max within each declared stratum. "
            "Each mean uses binary64 left-fold addition in the frozen declared_units order, then divides by the complete unit count. "
            "Every later declared condition is paired against every earlier condition, subtracting within each identical seed/unit before summarizing. "
            "Incomplete or invalid whole-grid/control evidence supplies no numerical summaries or claim-supporting projection; missing summaries are not zero.")
    if mode not in {"empirical", "finite_enumeration", "formal"}:
        raise ValueError("Unsupported validation mode")
    if mode == "formal":
        receipt.update(supported=False, status="unsupported")
        receipt["blockers"].append("Automatic theorem verification is unavailable; literal proof identity is not proof correctness.")
        return receipt
    units = spec["declared_units"]
    if not isinstance(units, list) or not 1 <= len(units) <= 10000:
        raise ValueError("Declare between one and ten thousand frozen validation units")
    declarations = {}
    for item in units:
        if (not isinstance(item, dict) or set(item) != {"seed", "unit_id", "stratum"} or
                type(item["seed"]) is not int or item["seed"] not in protocol["seeds"] or
                any(not isinstance(item[key], str) or not 1 <= len(item[key].strip()) <= 200
                    or any(ord(char) < 32 for char in item[key]) for key in ("unit_id", "stratum"))):
            raise ValueError("Declared validation units require exact seed, unit_id and stratum")
        key = (item["seed"], item["unit_id"])
        if key in declarations:
            raise ValueError("Declared validation units must be distinct")
        declarations[key] = item["stratum"]
    strata = sorted(set(declarations.values()))
    if len(strata) > 8 or any(sum(seed == value for seed, _ in declarations) != protocol["units_per_seed"]
                             for value in protocol["seeds"]):
        raise ValueError("Validation declarations must match every frozen seed's unit count and at most eight strata")
    values = {}
    for row in observations["observations"]:
        key = (row["seed"], row["unit_id"], row["condition"], row["metric"])
        if (key in values or key[:2] not in declarations or row["condition"] not in protocol["conditions"] or
                row["metric"] not in {metric["name"] for metric in protocol["metrics"]} or
                type(row["value"]) not in {int, float} or not math.isfinite(row["value"])):
            raise ValueError("Validation observations differ from declared units or the frozen measurement grid")
        values[key] = float(row["value"]) if schema_version == 2 else row["value"]
    expected = {(seed, unit, condition, metric["name"]) for seed, unit in declarations
                for condition in protocol["conditions"] for metric in protocol["metrics"]}
    if set(values) != expected:
        receipt["blockers"].append("The declared unit/condition/metric grid was not completely observed.")
        return receipt
    if control_comparator is None:
        from .science import derive_control_comparisons
        control_comparator = derive_control_comparisons
    receipt["controls"] = control_comparator(observations)
    if not all(item["passed"] for item in receipt["controls"]):
        receipt["blockers"].append("A recomputed control comparison failed; execution must remain terminal.")
        return receipt
    if mode == "finite_enumeration":
        fixture = next((item for item in observations["fixtures"] if item["label"] == spec["finite_domain_label"]), None)
        if fixture is None:
            receipt["blockers"].append("Finite completeness requires the retained declared-domain fixture.")
            return receipt
        raw = base64.b64decode(fixture["content"], validate=True)
        if hashlib.sha256(raw).hexdigest() != fixture["sha256"]:
            raise ValueError("Finite-domain fixture digest differs from its actual bytes")
        domain = json.loads(raw.decode("utf-8"))
        if domain != units:
            receipt["blockers"].append("Retained finite domain differs from the exact frozen unit/stratum declaration.")
            return receipt
        receipt["complete_declared_domain"] = True
    uncertainty = spec["uncertainty"]
    if uncertainty not in {"none", "seed_cluster_bootstrap"}:
        raise ValueError("Only explicitly bounded seed-cluster bootstrap is supported")
    if uncertainty != "none" and (mode != "empirical" or spec["independent_sampling"] is not True or
                                  not isinstance(spec["sampling_basis"], str) or len(spec["sampling_basis"].strip()) < 24):
        receipt.update(supported=False, status="unsupported")
        receipt["blockers"].append("Seed-cluster uncertainty needs an independently reviewed frozen sampling basis; finite domains do not imply population sampling.")
        return receipt
    replicates, confidence = spec["bootstrap_replicates"], spec["confidence_level"]
    if (type(replicates) is not int or not 200 <= replicates <= 2000 or type(spec["bootstrap_seed"]) is not int or
            type(confidence) not in {int, float} or not math.isfinite(confidence) or not .8 <= confidence <= .99):
        raise ValueError("Conditional bootstrap parameters exceed their frozen bounds")
    mean = statistics.mean if schema_version == 1 else lambda sample: _summary(sample)["mean"]
    for stratum in strata:
        selected = [(seed, unit) for (seed, unit), label in declarations.items() if label == stratum]
        seeds = sorted({seed for seed, _ in selected})
        if uncertainty != "none" and len(seeds) < 3:
            receipt.update(supported=False, status="unsupported")
            receipt["blockers"].append("Every uncertainty stratum needs at least three distinct seed clusters.")
            return receipt
        for metric in protocol["metrics"]:
            for index, condition in enumerate(protocol["conditions"]):
                series = {(seed, unit): values[(seed, unit, condition, metric["name"])] for seed, unit in selected}
                samples = [("level", None, series)]
                baselines = protocol["conditions"][:index] if schema_version == 2 else protocol["conditions"][:min(index, 1)]
                for baseline in baselines:
                    samples.append(("paired_difference", baseline,
                                    {key: value - values[(*key, baseline, metric["name"])] for key, value in series.items()}))
                for kind, baseline, sample in samples:
                    if sample is None:
                        continue
                    cell = {"stratum": stratum, "metric": metric["name"], "condition": condition,
                            "kind": kind, "unit": metric["unit"], **_summary(list(sample.values()), schema_version=schema_version)}
                    if schema_version == 2:
                        cell["baseline"] = baseline
                    receipt["strata"].append(cell)
                    if uncertainty != "none":
                        seed_means = [mean([value for (seed, _), value in sample.items() if seed == selected_seed])
                                      for selected_seed in seeds]
                        random_seed = int(hashlib.sha256((str(spec["bootstrap_seed"]) + _digest(cell)).encode()).hexdigest(), 16)
                        rng = random.Random(random_seed)
                        draws = [mean([rng.choice(seed_means) for _ in seeds]) for _ in range(replicates)]
                        tail = (1 - confidence) / 2
                        interval = {"stratum": stratum, "metric": metric["name"], "condition": condition,
                            "kind": kind, "method": "seed_cluster_bootstrap", "confidence_level": confidence,
                            "seed_clusters": len(seeds), "replicates": replicates, "estimate": mean(seed_means),
                            "lower": _percentile(draws, tail), "upper": _percentile(draws, 1 - tail),
                            "scope": "Conditional on the independently reviewed seed-cluster sampling assumptions; no population representativeness is inferred."}
                        if schema_version == 2:
                            interval["baseline"] = baseline
                        receipt["uncertainty"].append(interval)
    receipt.update(passed=True, status="verified")
    return receipt


def projected_results(receipt: dict) -> dict:
    """Name finite native values for existing manuscript result placeholders.

    Cell indices follow the rederived receipt's frozen stratum/metric/condition
    order. Every value retains its cell identity and conditional inference scope.
    Unsupported or incomplete validation supplies no claim-supporting numbers.
    """
    if receipt.get("supported") is not True or receipt.get("passed") is not True:
        return {}
    results = {}
    identity_fields = ("stratum", "metric", "condition", "kind") + (("baseline",) if receipt.get("schema_version") == 2 else ())
    intervals = {tuple(item[key] for key in identity_fields): item
                  for item in receipt["uncertainty"]}
    for index, cell in enumerate(receipt["strata"], 1):
        identity = {key: cell[key] for key in identity_fields}
        prefix = f"validation.cell_{index}"
        statistics_names = ("count", "mean", "min", "max") if receipt.get("schema_version") == 2 else ("count", "mean", "median", "min", "max", "stdev")
        comparison = cell["condition"] + (" minus " + cell["baseline"] if cell.get("baseline") is not None else "")
        for name in statistics_names:
            value = cell[name]
            if value is None:
                continue
            if type(value) not in {int, float} or not math.isfinite(value):
                raise ValueError("Validation result projection requires finite native numbers")
            results[prefix + "." + name] = {
                "value": value, "unit": "declared units" if name == "count" else cell["unit"],
                "description": f"{name} of {cell['kind']} {cell['metric']} for {comparison} in declared stratum {cell['stratum']}",
                "source": "claim-validation.json", "validation_spec_sha256": receipt["spec_sha256"],
                "scope": receipt["scope"], **identity}
        interval = intervals.get(tuple(identity.values()))
        if interval is not None:
            for name in ("estimate", "lower", "upper", "confidence_level", "seed_clusters", "replicates"):
                value = interval[name]
                if type(value) not in {int, float} or not math.isfinite(value):
                    raise ValueError("Conditional interval projection requires finite native numbers")
                unit = {"confidence_level": "fraction", "seed_clusters": "seed clusters", "replicates": "resamples"}.get(name, cell["unit"])
                results[prefix + ".interval." + name] = {
                    "value": value, "unit": unit,
                    "description": f"Conditional seed-cluster bootstrap {name} of {cell['kind']} {cell['metric']} for {comparison} in declared stratum {cell['stratum']}",
                    "source": "claim-validation.json", "validation_spec_sha256": receipt["spec_sha256"],
                    "scope": interval["scope"], **identity}
    return results

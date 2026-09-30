"""Claims derive exclusively from revalidated successful, measured outputs."""

import hashlib
import json
import math
from pathlib import PurePosixPath, PureWindowsPath

from .experiments import _validate_manifest, extract_metric, read_json, safe_relative
from .models import Claim, ExperimentManifest, ExperimentRun, Project, Study, StudyState, transition_study
from .project import verify_snapshot
from .workspace import Workspace, digest_file, write_json


def _verify_run(ws: Workspace, run: ExperimentRun) -> tuple[ExperimentManifest | None, dict[str, float], list[str]]:
    errors: list[str] = []
    values: dict[str, float] = {}
    manifest: ExperimentManifest | None = None
    try:
        if ws.get("run", run.id, ExperimentRun) != run:
            errors.append("Run does not match its persisted record")
        if run.status != "SUCCEEDED" or run.exit_code != 0 or not run.ended_at:
            errors.append("A successful completed experiment record is required")
        verify_snapshot(ws)
        project = ws.latest("project", Project)
        if run.source_digest != project.snapshot_digest or run.source_commit != project.source_commit:
            errors.append("Run source version does not match the imported project")
        manifest = ws.get("manifest", run.experiment_id, ExperimentManifest)
        _validate_manifest(ws, manifest)
        directory = safe_relative(ws.root, f"runs/{run.id}")
        pinned_run = ExperimentRun.model_validate_json(safe_relative(directory, "run.json").read_text(encoding="utf-8"))
        if pinned_run != run:
            errors.append("Run artifact does not match its persisted record")
        pinned_manifest = safe_relative(directory, "manifest.json")
        pinned = ExperimentManifest.model_validate_json(pinned_manifest.read_text(encoding="utf-8"))
        if manifest != pinned:
            errors.append("Registered manifest no longer matches the executed manifest")
        if (manifest.study_id != run.study_id or manifest.source_digest != run.source_digest or
                manifest.source_commit != run.source_commit or manifest.command != run.command or manifest.seed != run.seed):
            errors.append("Run provenance does not match its manifest")
        provenance = read_json(safe_relative(directory, "provenance.json"))
        if not isinstance(provenance, dict):
            raise ValueError("Invalid execution provenance")
        working_directory = provenance.get("working_directory")
        if not isinstance(working_directory, str):
            raise ValueError("Execution provenance lacks its working directory")
        original_work = PureWindowsPath(working_directory) if PureWindowsPath(working_directory).is_absolute() else PurePosixPath(working_directory)
        if not original_work.is_absolute() or tuple(original_work.parts[-3:]) != ("runs", run.id, "work"):
            errors.append("Execution working directory is inconsistent")
        effective = [provenance.get("interpreter") if argument == "{python}" else argument for argument in run.command]
        executable = provenance.get("effective_executable")
        if run.command and run.command[0] != "{python}" and not PurePosixPath(run.command[0]).is_absolute() and not PureWindowsPath(run.command[0]).is_absolute():
            if "/" in run.command[0] or "\\" in run.command[0]:
                effective[0] = str(original_work / PurePosixPath(run.command[0].replace("\\", "/")).as_posix())
            elif isinstance(executable, str):
                selected = PureWindowsPath(executable) if PureWindowsPath(executable).is_absolute() else PurePosixPath(executable)
                command_name = run.command[0].casefold()
                if not selected.is_absolute() or selected.name.casefold() not in {command_name, *[command_name + suffix for suffix in (".exe", ".com", ".bat", ".cmd")]}:
                    errors.append("Resolved executable does not match the manifest command")
                effective[0] = executable
        env_hash = hashlib.sha256(json.dumps(run.environment, sort_keys=True).encode()).hexdigest()
        if (provenance.get("manifest_sha256") != digest_file(pinned_manifest) or
                provenance.get("original_command") != run.command or provenance.get("effective_command") != effective or
                provenance.get("environment_sha256") != env_hash or provenance.get("seed") != run.seed or
                not provenance.get("platform") or not provenance.get("python_version") or not provenance.get("effective_executable") or
                not isinstance(provenance.get("package_versions"), dict)):
            errors.append("Execution provenance is inconsistent")
        paths = [asset.path for asset in run.artifacts]
        if len(paths) != len(set(paths)):
            errors.append("Run artifact paths are duplicated")
        assets = {asset.path: asset for asset in run.artifacts}
        required = {f"runs/{run.id}/{name}" for name in ("manifest.json", "provenance.json", "stdout.log", "stderr.log")}
        required.update(f"runs/{run.id}/raw/{output}" for output in manifest.expected_outputs)
        if not required.issubset(assets):
            errors.append("Required raw output or execution provenance is missing")
        for asset in run.artifacts:
            path = safe_relative(ws.root, asset.path)
            if not path.is_relative_to(directory):
                errors.append(f"Artifact belongs outside its run directory: {asset.path}")
            if not path.is_file() or path.stat().st_size != asset.size or digest_file(path) != asset.sha256:
                errors.append(f"Artifact missing or modified: {asset.path}")
        processed_path = safe_relative(ws.root, f"runs/{run.id}/processed.json")
        if not run.processed_sha256 or digest_file(processed_path) != run.processed_sha256:
            errors.append("Processed result is missing or modified")
        processed = read_json(processed_path)
        for metric in manifest.metrics:
            raw = safe_relative(ws.root, f"runs/{run.id}/raw/{metric.output}")
            values[metric.name] = extract_metric(read_json(raw), metric.pointer)
        if values != run.metrics or processed != {"run_id": run.id, "metrics": values}:
            errors.append("Stored metric values differ from raw result extraction")
        if any(not math.isfinite(value) for value in run.metrics.values()):
            errors.append("Run metrics must be finite")
    except (OSError, ValueError, TypeError, KeyError) as error:
        errors.append(str(error))
    return manifest, values, errors


def study_readiness_errors(ws: Workspace, study_id: str) -> list[str]:
    """Preserve past measurements while surfacing unresolved latest attempts."""
    latest = {run.experiment_id: run for run in ws.list("run", ExperimentRun) if run.study_id == study_id}
    return [f"Latest attempt {run.id} for {experiment} is {run.status}: {run.error or 'execution has not completed'}"
            for experiment, run in latest.items() if run.status != "SUCCEEDED"]


def claims_for_run(ws: Workspace, run: ExperimentRun) -> list[Claim]:
    with ws.lock(f"study-{run.study_id}"):
        return _claims_for_run(ws, run)


def _claims_for_run(ws: Workspace, run: ExperimentRun) -> list[Claim]:
    manifest, values, errors = _verify_run(ws, run)
    if errors or manifest is None:
        raise ValueError("Cannot create quantitative claims: " + "; ".join(errors))
    existing = {claim.metric_name: claim for claim in ws.list("claim", Claim) if claim.run_id == run.id}
    assets = {asset.path: asset for asset in run.artifacts}
    claims: list[Claim] = []
    for metric in manifest.metrics:
        artifact = f"runs/{run.id}/raw/{metric.output}"
        claim = existing.get(metric.name) or Claim(
            study_id=run.study_id, run_id=run.id, metric_name=metric.name, value=values[metric.name],
            unit=metric.unit, description=metric.description, raw_artifact=artifact,
            raw_sha256=assets[artifact].sha256, pointer=metric.pointer,
        )
        if (claim.value != values[metric.name] or claim.raw_sha256 != assets[artifact].sha256 or claim.study_id != run.study_id or
                claim.raw_artifact != artifact or claim.pointer != metric.pointer or claim.unit != metric.unit or claim.description != metric.description):
            raise ValueError("Existing claim conflicts with measured evidence")
        ws.save("claim", claim)
        claims.append(claim)
    write_json(ws.path(f"runs/{run.id}/claims.json"), [claim.model_dump(mode="json") for claim in claims])
    study = ws.get("study", run.study_id, Study)
    if study.state != StudyState.EVIDENCE_READY and not study_readiness_errors(ws, study.id):
        transition_study(study, StudyState.EVIDENCE_READY)
        ws.save("study", study)
        write_json(ws.path(f"studies/{study.id}.json"), study)
    return claims


def verify_claim(ws: Workspace, claim: Claim) -> list[str]:
    try:
        if ws.get("claim", claim.id, Claim) != claim:
            return ["Claim does not match its persisted record"]
        run = ws.get("run", claim.run_id, ExperimentRun)
        manifest, values, errors = _verify_run(ws, run)
        if manifest is None:
            return errors
        metric = next((item for item in manifest.metrics if item.name == claim.metric_name), None)
        if metric is None:
            return [*errors, "Claim metric is absent from the executed manifest"]
        expected_path = f"runs/{run.id}/raw/{metric.output}"
        artifact = next((asset for asset in run.artifacts if asset.path == expected_path), None)
        if (claim.study_id != run.study_id or claim.raw_artifact != expected_path or
                claim.pointer != metric.pointer or claim.unit != metric.unit or claim.description != metric.description or
                claim.value != values.get(metric.name) or artifact is None or claim.raw_sha256 != artifact.sha256):
            errors.append("Claim does not match measured evidence and calculation")
        if not math.isfinite(claim.value):
            errors.append("Claim value must be finite")
        return errors
    except (OSError, ValueError, TypeError) as error:
        return [str(error)]

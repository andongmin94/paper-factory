"""Execute trusted research commands in fresh copies and preserve all outcomes.

Working copies protect against accidental source edits. They are not a security
sandbox: a malicious command can access resources with the invoking user's rights.
"""

import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import signal
import shutil
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

from .models import Asset, ExperimentManifest, ExperimentRun, Project, Study, StudyState, now, transition_study
from .project import is_link, verify_snapshot
from .workspace import Workspace, digest_file, safe_relative, write_json


def _credential_name(name: str) -> bool:
    return bool(re.search(r"(?:PASSWORD|PASSWD|TOKEN|SECRET|CREDENTIAL|AUTH|COOKIE|(?:^|_)(?:KEY|PAT|JWT|BEARER|SESSION)(?:_|$))", name, re.IGNORECASE))


def _validate_manifest(ws: Workspace, manifest: ExperimentManifest) -> Study:
    project = ws.latest("project", Project)
    study = ws.get("study", manifest.study_id, Study)
    if study.project_id != project.id or manifest.source_digest != project.snapshot_digest or manifest.source_commit != project.source_commit:
        raise ValueError("Experiment must match the study's imported source version")
    if len(set(manifest.expected_outputs)) != len(manifest.expected_outputs):
        raise ValueError("Expected outputs must be unique")
    names = [metric.name for metric in manifest.metrics]
    if len(set(names)) != len(names) or any(not name.strip() for name in names):
        raise ValueError("Metric names must be nonempty and unique")
    for path in manifest.inputs:
        target = safe_relative(ws.root / "source", path)
        if not target.exists():
            raise ValueError(f"Experiment input is absent from source snapshot: {path}")
    for path in manifest.expected_outputs:
        safe_relative(ws.root / "source", path)
    for metric in manifest.metrics:
        if metric.output not in manifest.expected_outputs:
            raise ValueError("Every metric must reference an expected output")
        if re.search(r"~(?![01])", metric.pointer):
            raise ValueError("Invalid RFC 6901 escape in metric pointer")
    for name, value in manifest.environment.items():
        credential_url = re.search(r"[A-Za-z][A-Za-z0-9+.-]*://[^/\s]+@", value)
        if _credential_name(name) or credential_url or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or "\x00" in value:
            raise ValueError("Credential-like or invalid experiment environment variable")
    if any("\x00" in argument for argument in manifest.command):
        raise ValueError("Command arguments cannot contain NUL bytes")
    if not manifest.command[0].strip():
        raise ValueError("Experiment executable must be nonempty")
    if ".." in re.split(r"[/\\]", manifest.command[0]):
        raise ValueError("Experiment executable must not traverse outside the working copy")
    for argument in manifest.command[1:]:
        # Scripts should use relative inputs in the copy, never absolute original paths.
        if PureWindowsPath(manifest.command[0]).name.casefold() in {"cmd", "cmd.exe"} and argument.casefold() in {"/c", "/k", "/s", "/q", "/d", "/a", "/u"}:
            continue
        value = argument.split("=", 1)[1] if argument.startswith("-") and "=" in argument else argument
        if PurePosixPath(value).is_absolute() or PureWindowsPath(value).root or PureWindowsPath(value).drive:
            raise ValueError("Command arguments must not use absolute filesystem paths")
        if ".." in re.split(r"[/\\]", value):
            raise ValueError("Command path arguments must not traverse outside the working copy")
    original_path = str(Path(project.source).resolve()) if "://" not in project.source and "@" not in project.source else None
    protected_paths = [re.sub(r"[/\\]+", "/", path).casefold() for path in (str(ws.root / "source"), original_path) if path]
    for argument in [*manifest.command, *manifest.environment.values()]:
        normalized = re.sub(r"[/\\]+", "/", argument).casefold()
        if any(path in normalized for path in protected_paths):
            raise ValueError("Command must not reference the original project or immutable source snapshot")
    return study


def register_manifest(ws: Workspace, path: Path) -> ExperimentManifest:
    manifest = ExperimentManifest.model_validate_json(path.read_text(encoding="utf-8"))
    with ws.lock(f"manifest-{manifest.id}"):
        _validate_manifest(ws, manifest)
        verify_snapshot(ws)
        existing = ws.list("manifest", ExperimentManifest)
        if any(item.id == manifest.id and item != manifest for item in existing):
            raise ValueError("Experiment IDs are immutable; use a new ID for a revised manifest")
        write_json(ws.path(f"experiments/{manifest.id}.json"), manifest)
        ws.save("manifest", manifest)
    return manifest


def _human_subjects(study: Study, manifest: ExperimentManifest) -> bool:
    text = " ".join([study.title, study.research_question, *manifest.command, *manifest.inputs]).casefold()
    return study.human_subjects or manifest.human_subjects or bool(re.search(r"\b(?:participants?|human[ _-]subjects?|user[ _-]stud(?:y|ies)|clinical[ _-]trial|recruitment|consent[ _-]form|survey[ _-]responses)\b|사람\s*대상|사용자\s*(?:실험|연구)|참가자|임상\s*시험", text))


def _environment(manifest: ExperimentManifest) -> dict[str, str]:
    # Only operating-system/tool lookup variables cross the subprocess boundary.
    names = ("PATH", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC", "PATHEXT", "TEMP", "TMP", "LANG", "LC_ALL")
    environment = {name: os.environ[name] for name in names if name in os.environ}
    environment.update(manifest.environment)
    environment["PYTHONHASHSEED"] = str(manifest.seed % (2**32))
    environment["PF_SEED"] = str(manifest.seed)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def read_json(path: Path) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError("JSON metric output has duplicate object keys")
            result[key] = value
        return result
    def invalid(value: str) -> object:
        raise ValueError(f"Nonfinite JSON numeric constant: {value}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=invalid)


def extract_metric(data: object, pointer: str) -> float:
    if (pointer and not pointer.startswith("/")) or re.search(r"~(?![01])", pointer):
        raise ValueError("Metric pointer must be a valid RFC 6901 JSON pointer")
    value = data
    for token in pointer[1:].split("/") if pointer else []:
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            if token not in value:
                raise ValueError(f"JSON pointer is absent: {pointer}")
            value = value[token]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", token):
            try:
                value = value[int(token)]
            except IndexError as error:
                raise ValueError(f"JSON pointer is absent: {pointer}") from error
        else:
            raise ValueError(f"JSON pointer is absent: {pointer}")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Metric selector must yield a finite number")
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError("Metric selector must yield a finite number") from error
    if not math.isfinite(number):
        raise ValueError("Metric selector must yield a finite number")
    if isinstance(value, int) and int(number) != value:
        raise ValueError("Integer metric loses precision when represented as a float")
    return number


def _artifact(ws: Workspace, path: Path, kind: str) -> Asset:
    return Asset(path=path.relative_to(ws.root).as_posix(), sha256=digest_file(path), size=path.stat().st_size, kind=kind)


def _stop_process_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False, timeout=15)
        finally:
            if process.poll() is None:
                process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=15)


def _execute(command: list[str], work: Path, environment: dict[str, str], timeout: int, stdout: Path, stderr: Path) -> int:
    # File streams preserve partial/large logs without making wait() depend on
    # captured pipes inherited by descendant processes.
    with stdout.open("wb") as out, stderr.open("wb") as err:
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen(command, cwd=work, env=environment, stdout=out, stderr=err, **options)
        try:
            return process.wait(timeout=timeout)
        except BaseException:
            _stop_process_tree(process)
            raise


def run_experiment(ws: Workspace, manifest: ExperimentManifest) -> ExperimentRun:
    with ws.lock(f"study-{manifest.study_id}"):
        return _run_experiment(ws, manifest)


def _run_experiment(ws: Workspace, manifest: ExperimentManifest) -> ExperimentRun:
    study = _validate_manifest(ws, manifest)
    if ws.get("manifest", manifest.id, ExperimentManifest) != manifest:
        raise ValueError("Only the exact registered manifest may execute")
    if _human_subjects(study, manifest):
        raise ValueError("Human-subject research cannot execute automatically in Phase 1; ethics approval does not enable automatic collection")
    verify_snapshot(ws)
    environment = _environment(manifest)
    command = [sys.executable if argument == "{python}" else argument for argument in manifest.command]
    run = ExperimentRun(experiment_id=manifest.id, study_id=manifest.study_id, source_commit=manifest.source_commit,
                        source_digest=manifest.source_digest, command=manifest.command, environment=environment, seed=manifest.seed)
    directory = ws.path(f"runs/{run.id}")
    work = directory / "work"
    # Holding the study lock proves any previous RUNNING records are abandoned.
    for interrupted in ws.list("run", ExperimentRun):
        if interrupted.study_id == study.id and interrupted.status == "RUNNING":
            interrupted.status, interrupted.ended_at = "FAILED", now()
            interrupted.error = "Previous execution was interrupted before recording completion"
            ws.save("run", interrupted)
            write_json(ws.path(f"runs/{interrupted.id}/run.json"), interrupted)
    ws.save("run", run)
    process_started = False
    try:
        directory.mkdir(parents=True)
        if study.state != StudyState.EXPERIMENTS_RUNNING:
            transition_study(study, StudyState.EXPERIMENTS_RUNNING)
            ws.save("study", study)
            write_json(ws.path(f"studies/{study.id}.json"), study)
        write_json(ws.path(f"runs/{run.id}/manifest.json"), manifest)
        shutil.copytree(ws.path("source"), work)
        # Snapshot files are read-only; only the fresh execution copy is writable.
        for path in work.rglob("*"):
            if is_link(path):
                raise ValueError("Execution copy contains a symlink or junction")
            if path.is_file():
                path.chmod(stat.S_IMODE(path.stat().st_mode) | stat.S_IWUSR)
        relative_executable = not PurePosixPath(command[0]).is_absolute() and not PureWindowsPath(command[0]).is_absolute()
        executable = None
        if relative_executable:
            local_name = PurePosixPath(command[0].replace("\\", "/")).as_posix()
            local_executable = safe_relative(work, local_name)
            if local_executable.is_file():
                executable = str(local_executable.resolve())
        if not executable:
            search_path = os.pathsep.join(str(Path(entry) if Path(entry).is_absolute() else work / entry)
                                          for entry in environment.get("PATH", "").split(os.pathsep))
            executable = shutil.which(command[0], path=search_path)
        if executable:
            executable = str(Path(executable).absolute())
            command[0] = executable
        packages = dict(sorted((distribution.metadata["Name"], distribution.version) for distribution in importlib.metadata.distributions() if distribution.metadata["Name"]))
        write_json(ws.path(f"runs/{run.id}/provenance.json"), {
            "manifest_sha256": digest_file(directory / "manifest.json"), "original_command": manifest.command,
            "effective_command": command, "effective_executable": executable,
            "working_directory": str(work),
            "environment_sha256": hashlib.sha256(json.dumps(environment, sort_keys=True).encode()).hexdigest(),
            "seed": manifest.seed, "platform": platform.platform(), "interpreter": sys.executable, "python_version": platform.python_version(),
            "package_versions": packages, "package_scope": "installed distributions of the Paper Factory invoking Python interpreter",
            "execution_boundary": "trusted subprocess in a fresh copy; not a security sandbox",
        })
        for output in manifest.expected_outputs:
            target = safe_relative(work, output)
            if target.exists():
                if not target.is_file():
                    raise ValueError("Expected output path already exists as a directory")
                target.unlink()
        process_started = True
        run.exit_code = _execute(command, work, environment, manifest.timeout_seconds,
                                 ws.path(f"runs/{run.id}/stdout.log"), ws.path(f"runs/{run.id}/stderr.log"))
        if run.exit_code:
            raise ValueError(f"Experiment process exited with code {run.exit_code}")
        for output in manifest.expected_outputs:
            original = safe_relative(work, output)
            if not original.is_file():
                raise ValueError(f"Expected output was not produced: {output}")
            raw = safe_relative(directory / "raw", output)
            raw.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, raw)
            run.artifacts.append(_artifact(ws, raw, "raw"))
        for metric in manifest.metrics:
            raw = safe_relative(directory / "raw", metric.output)
            run.metrics[metric.name] = extract_metric(read_json(raw), metric.pointer)
        write_json(ws.path(f"runs/{run.id}/processed.json"), {"run_id": run.id, "metrics": run.metrics})
        run.processed_sha256 = digest_file(directory / "processed.json")
        verify_snapshot(ws)
        run.status = "SUCCEEDED"
    except subprocess.TimeoutExpired as error:
        run.status, run.error = "FAILED", f"Experiment timed out after {manifest.timeout_seconds} seconds"
    except Exception as error:
        run.status, run.error = "FAILED", str(error)
    except BaseException as error:
        run.status, run.error = "FAILED", f"Experiment interrupted: {type(error).__name__}"
        raise
    finally:
        finalization_errors: list[str] = []
        for name in ("stdout.log", "stderr.log"):
            try:
                log = ws.path(f"runs/{run.id}/{name}")
                log.parent.mkdir(parents=True, exist_ok=True)
                if not log.exists():
                    log.write_bytes(b"")
            except (OSError, ValueError) as error:
                finalization_errors.append(str(error))
        # Keep produced outputs even when the command failed, without using them as evidence.
        if run.status == "FAILED" and process_started:
            for output in manifest.expected_outputs:
                try:
                    original = safe_relative(work, output)
                    raw = safe_relative(directory / "raw", output)
                    if original.is_file() and not raw.exists():
                        raw.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(original, raw)
                        run.artifacts.append(_artifact(ws, raw, "raw"))
                except (OSError, ValueError):
                    pass
        try:
            verify_snapshot(ws)
        except (OSError, ValueError) as error:
            finalization_errors.append(str(error))
        for name in ("manifest.json", "provenance.json", "stdout.log", "stderr.log"):
            try:
                artifact = ws.path(f"runs/{run.id}/{name}")
                if artifact.is_file():
                    run.artifacts.append(_artifact(ws, artifact, "provenance"))
            except (OSError, ValueError) as error:
                finalization_errors.append(str(error))
        if finalization_errors:
            run.status = "FAILED"
            run.error = "; ".join([*([run.error] if run.error else []), *finalization_errors])
        run.ended_at = now()
        ws.save("run", run)
        try:
            write_json(ws.path(f"runs/{run.id}/run.json"), run)
        except (OSError, ValueError) as error:
            run.status = "FAILED"
            run.error = "; ".join([*([run.error] if run.error else []), str(error)])
            ws.save("run", run)
    return run

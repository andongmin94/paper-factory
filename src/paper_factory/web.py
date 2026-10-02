"""Local web workspace, evidence catalog and bounded asynchronous CLI jobs.

Only typed research actions are exposed. Imported Python scripts execute with
this user's rights, as in the CLI; this server is a local development tool.
"""

from __future__ import annotations

import ipaddress
import json
import mimetypes
import os
import re
import signal
import sqlite3
import stat
import subprocess
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from uuid import uuid4

from . import __version__
from .autonomous.provider import ProviderBlocked
from .experiments import _credential_name
from .manuscript import Document, validate_document
from .models import ExperimentManifest, Paper, PaperState
from .research import INVENTORY_SCRIPT
from .workspace import Workspace, ensure_unlinked, pf_home, safe_relative, write_json

MAX_BODY = 1024 * 1024
MAX_FILE = 64 * 1024 * 1024
MAX_BUNDLE = 96 * 1024 * 1024
MAX_LOG = 256 * 1024
MAX_JOBS = 32
FILE_TYPES = {".pdf", ".md", ".docx", ".tex", ".csv", ".tsv", ".json", ".bib", ".txt", ".png", ".jpg", ".jpeg", ".svg", ".webp", ".zip"}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
ACTIONS = {"research", "register", "run", "literature-search", "literature-doi", "manuscript-build", "manuscript-render", "integrity-check"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("Expected a safe identifier")
    safe_relative(Path("/tmp"), value)
    return value


def _text(value: object, name: str, *, maximum: int = 4096, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError(f"{name} must be a nonempty string of at most {maximum} characters")
    return value.strip()


def _strict_keys(data: dict, allowed: set[str]) -> None:
    if extra := set(data) - allowed:
        raise ValueError("Unsupported fields: " + ", ".join(sorted(extra)))


def _json(path: Path) -> object:
    ensure_unlinked(path)
    if path.stat().st_size > MAX_BODY * 8:
        raise ValueError("JSON document exceeds the supported size")
    def nonfinite(value):
        raise ValueError("JSON numbers must be finite")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=nonfinite)


def _redactor():
    values = set()
    for key, value in os.environ.items():
        if _credential_name(key) and len(value) >= 4:
            values.add(value)
            values.update(part for part in value.splitlines() if len(part) >= 4)
    values = sorted(values, key=len, reverse=True)
    def redact(text: str) -> str:
        for value in values:
            text = text.replace(value, "[redacted]")
        return re.sub(r"(https?://)[^/\s@]+@", r"\1[redacted]@", text)
    redact.maximum_secret_length = max((len(value) for value in values), default=0)
    return redact


def _file_entry(root: Path, relative: str, prefix: str, extra: dict | None = None) -> dict:
    path = safe_relative(root, relative)
    if path.suffix.lower() not in FILE_TYPES or not path.is_file() or path.stat().st_size > _file_limit(path):
        raise ValueError("Artifact is missing, unsupported, or too large")
    return {**(extra or {}), "path": relative, "name": path.name, "size": path.stat().st_size,
            "mime": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "url": prefix + quote(relative, safe="/")}


def _file_limit(path: Path) -> int:
    return MAX_BUNDLE if path.suffix.lower() == ".zip" else MAX_FILE


def _append_file(root: Path, relative: str, prefix: str, files: list, errors: list):
    try:
        files.append(_file_entry(root, relative, prefix))
    except (OSError, ValueError):
        errors.append({"path": relative, "error": "Artifact is unavailable or exceeds the download limit"})


class WebState:
    def __init__(self, studies_root: Path, data_root: Path, static_root: Path,
                 source_roots: list[Path] | None = None, *, resume_jobs: bool = True):
        for root in (studies_root, data_root, static_root):
            ensure_unlinked(root)
        self.studies_root = studies_root.resolve()
        self.data_root = data_root.resolve()
        self.static_root = static_root.resolve()
        self.source_roots = [root.expanduser().resolve() for root in (source_roots if source_roots is not None else [Path.home()])]
        self.data_root.mkdir(parents=True, exist_ok=True)
        for directory in ("jobs", "projects", ".home"):
            safe_relative(self.data_root, directory).mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self._connection = None
        self.redact = _redactor()
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="paperfactory-web")
        self.closed = False
        self.resume_jobs = resume_jobs
        self.started_at = _now()
        self.projects = self._load_projects()
        self.jobs: dict[str, dict] = {}
        interrupted_pipelines: dict[str, set[str]] = {}
        for path in sorted((self.data_root / "jobs").glob("*.json")):
            try:
                value = _json(path)
                if not isinstance(value, dict) or _identifier(value.get("id")) != path.stem:
                    continue
                if value.get("status") in {"queued", "running"}:
                    if value.get("action") in {"autonomous-start", "autonomous-resume"} and isinstance(value.get("project_id"), str) and isinstance(value.get("pipeline_id"), str):
                        interrupted_pipelines.setdefault(value["project_id"], set()).add(_identifier(value["pipeline_id"]))
                    value.update(status="interrupted", finished_at=_now(), error="Server stopped before this job completed; inspect evidence and retry the action.")
                    write_json(path, value)
                self.jobs[value["id"]] = value
            except (OSError, ValueError, TypeError):
                continue
        for record in self.projects.values():
            if record.get("status") == "importing":
                record.update(status="failed", error="Project import was interrupted; create a new import to retry.")
        self._save_projects()
        self._recover_pipelines(interrupted_pipelines)
        for project_id, record in self.projects.items():
            if self.resume_jobs and record.get("status") == "ready" and record.get("pending_autonomous"):
                self._start_pending_pipeline(project_id)

    def _load_projects(self) -> dict:
        path = safe_relative(self.data_root, "projects.json")
        if not path.exists():
            return {}
        value = _json(path)
        if not isinstance(value, dict):
            raise ValueError("Project registry is invalid")
        for key, record in value.items():
            _identifier(key)
            if not isinstance(record, dict) or record.get("id") != key:
                raise ValueError("Project registry has an invalid record")
        return value

    def _save_projects(self):
        write_json(safe_relative(self.data_root, "projects.json"), self.projects)

    def workspace_path(self, project_id: str) -> Path:
        _identifier(project_id)
        if project_id not in self.projects:
            raise KeyError("Unknown project")
        return safe_relative(self.data_root, f"projects/{project_id}")

    def catalog(self, slug: str | None = None) -> dict:
        if slug is not None:
            roots = [safe_relative(self.studies_root, _identifier(slug))]
        elif self.studies_root.is_dir():
            roots = sorted(self.studies_root.iterdir())
        else:
            roots = []
        studies, errors = [], []
        for root in roots:
            try:
                _identifier(root.name)
                ensure_unlinked(root)
                if not root.is_dir() or not (root / "manifest.json").is_file():
                    if slug:
                        raise KeyError("Unknown study")
                    continue
                value = _json(root / "manifest.json")
                if not isinstance(value, dict):
                    raise ValueError("Study manifest must contain an object")
                files = self.catalog_files(root, value)
                studies.append({**value, "slug": root.name, "files": files,
                                "bundle_url": f"/api/studies/{quote(root.name)}/bundle"})
            except (OSError, ValueError, TypeError) as exc:
                if slug:
                    raise ValueError("Study catalog is invalid") from exc
                errors.append({"slug": root.name, "error": "Study manifest or declared artifact is invalid"})
        if slug:
            if not studies:
                raise KeyError("Unknown study")
            return studies[0]
        return {"studies": studies, "errors": errors}

    def catalog_files(self, root: Path, value: dict) -> list[dict]:
        entries = value.get("files", [])
        if not isinstance(entries, list):
            raise ValueError("Manifest files must be a list")
        declared: dict[str, dict] = {}
        for entry in [*entries, *value.get("figures", [])]:
            if isinstance(entry, str):
                declared[entry] = {}
            elif isinstance(entry, dict) and isinstance(entry.get("path"), str):
                declared[entry["path"]] = entry
            else:
                raise ValueError("Artifact declarations require relative paths")
        if bundle := value.get("reproducibility_bundle"):
            if not isinstance(bundle, str) or Path(bundle).suffix.lower() != ".zip":
                raise ValueError("reproducibility_bundle must be a safe relative ZIP path")
            declared.setdefault(bundle, {"role": "reproducibility", "label": "Reproducibility bundle"})
        if len(declared) > 200:
            raise ValueError("Too many study files")
        prefix = f"/api/studies/{quote(root.name)}/files/"
        return [_file_entry(root, relative, prefix, extra) for relative, extra in declared.items()]

    def catalog_file(self, slug: str, relative: str) -> Path:
        study = self.catalog(slug)
        if relative not in {entry["path"] for entry in study["files"]}:
            raise KeyError("Artifact is not declared in the study manifest")
        return safe_relative(safe_relative(self.studies_root, slug), relative)

    def project_detail(self, project_id: str) -> dict:
        root = self.workspace_path(project_id)
        with self.lock:
            value = dict(self.projects[project_id])
        if not (root / "records.sqlite3").is_file():
            return {**value, "records": {}, "files": []}
        ws = Workspace(root)
        with ws._database() as db:
            rows = db.execute("SELECT kind,data FROM records WHERE kind IN ('project','study','manifest','run','paper','citation','claim') ORDER BY rowid").fetchall()
        records: dict[str, list] = {}
        for kind, data in rows:
            record = json.loads(data)
            if kind == "run":
                record.pop("environment", None)
            records.setdefault(kind, []).append(record)
        files, file_errors = [], []
        prefix = f"/api/projects/{project_id}/files/"
        for directory in ("manuscripts", "reports", "experiments"):
            base = safe_relative(root, directory)
            if base.is_dir():
                for path in sorted(base.rglob("*")):
                    if path.suffix.lower() in FILE_TYPES and path.is_file():
                        _append_file(root, path.relative_to(root).as_posix(), prefix, files, file_errors)
                        if len(files) >= 500:
                            break
        for record in records.get("run", []):
            for entry in record.get("artifacts", []):
                relative = entry.get("path", "")
                if relative.startswith(f"runs/{_identifier(record['id'])}/raw/"):
                    _append_file(root, relative, prefix, files, file_errors)
            relative = f"runs/{record['id']}/processed.json"
            if (root / relative).is_file():
                _append_file(root, relative, prefix, files, file_errors)
        pipelines = self.pipelines(project_id)
        for pipeline in pipelines:
            files.extend(pipeline["files"])
            file_errors.extend(pipeline["file_errors"])
        return {**value, "records": records, "files": files, "file_errors": file_errors, "pipelines": pipelines}

    def project_file(self, project_id: str, relative: str) -> Path:
        detail = self.project_detail(project_id)
        if relative not in {entry["path"] for entry in detail["files"]}:
            raise KeyError("Unknown project artifact")
        return safe_relative(self.workspace_path(project_id), relative)

    def source(self, source: str) -> str:
        source = _text(source, "source", maximum=4096)
        if source.startswith("https://"):
            parsed = urlsplit(source)
            if parsed.hostname != "github.com" or parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment or not re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/)?", parsed.path):
                raise ValueError("Git imports require a public/authenticated HTTPS github.com owner/repository URL without embedded credentials")
            return source.rstrip("/")
        if "://" in source or "@" in source:
            raise ValueError("Only GitHub HTTPS URLs or local project directories are supported")
        path = Path(source).expanduser()
        ensure_unlinked(path)
        path = path.resolve()
        from .autonomous.provider import auth_root
        authentication = auth_root().resolve()
        if path.is_relative_to(authentication) or authentication.is_relative_to(path):
            raise ValueError("Local import cannot include the private ChatGPT authentication directory")
        if not path.is_dir() or not any(path != root and path.is_relative_to(root) for root in self.source_roots):
            raise ValueError("Local projects must be directories below the configured import roots")
        if path.is_relative_to(self.data_root) or self.data_root.is_relative_to(path) or any(part.startswith(".") for part in path.parts):
            raise ValueError("Local import cannot use internal configuration or web data directories")
        return str(path)

    def import_project(self, payload: dict) -> dict:
        _strict_keys(payload, {"source", "name", "autonomous"})
        source = self.source(payload.get("source"))
        name = _text(payload.get("name"), "name", maximum=160, required=False) or Path(urlsplit(source).path).name.removesuffix(".git")
        autonomous = None
        if "autonomous" in payload:
            if not isinstance(payload["autonomous"], dict):
                raise ValueError("autonomous must contain an object")
            from .autonomous.models import Budget
            selected = payload["autonomous"]
            _strict_keys(selected, {"goal", "model", "budget"})
            autonomous = {"goal": _text(selected.get("goal"), "goal", maximum=4000),
                          "model": _text(selected.get("model"), "model", maximum=160, required=False),
                          "budget": Budget.model_validate(selected.get("budget", {})).model_dump(mode="json")}
            if len(autonomous["goal"]) < 8:
                raise ValueError("Research goal must contain at least 8 characters")
        project_id = "web-" + uuid4().hex[:12]
        with self.lock:
            self._capacity()
            record = {"id": project_id, "name": name, "source": source, "status": "importing", "created_at": _now()}
            if autonomous is not None:
                record["pending_autonomous"] = autonomous
            self.projects[project_id] = record
            self._save_projects()
            job = self.submit(project_id, "start", ["start", source], timeout=600)
        return {"project": record, "job": job}

    def _capacity(self):
        if self.closed:
            raise ValueError("Server is shutting down")
        if sum(job["status"] in {"queued", "running"} for job in self.jobs.values()) >= MAX_JOBS:
            raise ValueError("Job queue is full; wait for current jobs to finish")

    def _project_available(self, project_id: str) -> Workspace:
        root = self.workspace_path(project_id)
        if self.projects[project_id]["status"] != "ready":
            raise ValueError("Project import must succeed before running actions")
        if any(job["project_id"] == project_id and job["status"] in {"queued", "running"} for job in self.jobs.values()):
            raise ValueError("A job is already active for this project")
        return Workspace(root)

    def agent_status(self) -> dict:
        """Expose readiness only; never CLI output, login files or credentials."""
        from .autonomous.provider import CodexProvider
        from .autonomous.runner import research_runner
        provider = CodexProvider().status()
        return {"provider": provider, "runner": research_runner().status()}

    def connection_manager(self):
        with self.lock:
            if self._connection is None:
                from .autonomous.connection import ConnectionManager
                from .autonomous.provider import auth_root
                self._connection = ConnectionManager(auth_root())
            return self._connection

    def connection_status(self) -> dict:
        return self.connection_manager().status()

    def connection_action(self, action: str, payload: dict) -> dict:
        _strict_keys(payload, set())
        if action not in {"login", "cancel", "probe", "logout"}:
            raise ValueError("Unsupported connection action")
        with self.lock:
            if self.closed:
                raise ValueError("Server is shutting down")
            if action != "cancel":
                from .autonomous.models import PipelineRun
                active = any(job["status"] in {"queued", "running"} for job in self.jobs.values())
                if not active:
                    for project_id, record in self.projects.items():
                        if record.get("status") == "ready" and any(
                                run.status == "running" or run.active_handle or run.code == "CLEANUP_UNCONFIRMED"
                                for run in Workspace(self.workspace_path(project_id)).list("pipeline", PipelineRun)):
                            active = True
                            break
                if active:
                    return {"status": "blocked", "code": "RESEARCH_BUSY", "message": "연구 작업을 중지하고 작업자의 종료를 확인한 뒤 Codex 계정을 변경하거나 로그아웃하세요."}
            return getattr(self.connection_manager(), action)()

    def _research_auth_guard(self, *, uses_codex: bool = False):
        if self._connection is not None:
            connection = self._connection.status()
            if connection.get("code") == "CLEANUP_UNCONFIRMED":
                raise ValueError("이전 Codex 연결 작업자의 종료를 확인하지 못했습니다. 연결 작업을 정리한 뒤 연구를 시작하세요.")
            if connection.get("status") in {"starting", "waiting_user", "probing", "logging_out"}:
                raise ValueError("Codex 계정 연결 작업이 진행 중입니다. 작업이 끝난 뒤 연구를 시작하세요.")
            if uses_codex and connection.get("app_login_required"):
                raise ValueError("이 앱에서 Codex 계정을 연결하고 연결 확인을 완료한 뒤 연구를 시작하세요.")

    def recommend_repositories(self, payload: dict) -> dict:
        from .autonomous.repositories import select_repositories
        _strict_keys(payload, {"owner", "count"})
        owner = _text(payload.get("owner"), "owner", maximum=200)
        count = payload.get("count", 3)
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 3:
            raise ValueError("count must be an integer between 1 and 3")
        return select_repositories(owner, count=count)

    def pipeline_detail(self, project_id: str, pipeline_id: str) -> dict:
        from .autonomous import pipeline
        root = self.workspace_path(project_id)
        value = pipeline.status(Workspace(root), _identifier(pipeline_id))
        # Execution context, generated prompts and raw provider responses are
        # private workspace files. Only final export artifacts are downloadable.
        public = {key: value[key] for key in (
            "id", "goal", "model", "status", "stage", "created_at", "updated_at",
            "started_at", "finished_at", "ended_at", "budget", "usage", "error", "blocker",
            "stages", "study_id", "paper_id", "attempts", "message", "warnings", "code",
            "model_calls", "elapsed_seconds", "code_attempt", "cancellation_requested",
        ) if key in value}
        public["files"] = []
        public["file_errors"] = []
        exports = safe_relative(root, f"autonomous/{_identifier(pipeline_id)}/exports")
        if exports.is_dir():
            for path in sorted(exports.rglob("*")):
                if path.is_file() and path.suffix.lower() in FILE_TYPES:
                    relative = path.relative_to(root).as_posix()
                    if any(part.startswith(".") for part in Path(relative).parts):
                        continue
                    _append_file(root, relative, f"/api/projects/{project_id}/files/", public["files"], public["file_errors"])
                    if len(public["files"]) >= 100:
                        break
        # The pipeline stores bounded, normalized errors; apply the server's
        # credential redactor again before returning any status text.
        return json.loads(self.redact(json.dumps(public, ensure_ascii=False)))

    def pipelines(self, project_id: str) -> list[dict]:
        from .autonomous import pipeline
        ws = Workspace(self.workspace_path(project_id))
        entries = sorted(pipeline.list_runs(ws), key=lambda entry: entry.get("created_at", ""), reverse=True)[:100]
        return [self.pipeline_detail(project_id, entry["id"]) for entry in entries]

    def start_pipeline(self, project_id: str, payload: dict) -> dict:
        from .autonomous import pipeline
        _strict_keys(payload, {"goal", "model", "budget"})
        goal = _text(payload.get("goal"), "goal", maximum=4096)
        model = _text(payload.get("model"), "model", maximum=160, required=False)
        budget = payload.get("budget")
        if budget is not None and not isinstance(budget, dict):
            raise ValueError("budget must contain an object")
        with self.lock:
            self._capacity()
            self._research_auth_guard(uses_codex=True)
            ws = self._project_available(project_id)
            created = pipeline.create(ws, goal, model=model, budget=budget)
            job = self._submit_pipeline(project_id, created.id, "autonomous-start")
            return {"pipeline": self.pipeline_detail(project_id, created.id), "job": job}

    def control_pipeline(self, project_id: str, pipeline_id: str, control: str, payload: dict) -> dict:
        from .autonomous import pipeline
        _strict_keys(payload, set())
        pipeline_id = _identifier(pipeline_id)
        with self.lock:
            if control == "cancel":
                ws = Workspace(self.workspace_path(project_id))
                pipeline.cancel(ws, pipeline_id)
                return {"pipeline": self.pipeline_detail(project_id, pipeline_id)}
            self._capacity()
            self._research_auth_guard(uses_codex=True)
            ws = self._project_available(project_id)
            resumed = pipeline.resume(ws, pipeline_id)
            return {"pipeline": self.pipeline_detail(project_id, resumed.id),
                    "job": self._submit_pipeline(project_id, resumed.id, "autonomous-resume")}

    def _submit_pipeline(self, project_id: str, pipeline_id: str, action: str) -> dict:
        job = {"id": "job-" + uuid4().hex[:12], "project_id": project_id, "action": action,
               "pipeline_id": pipeline_id, "status": "queued", "created_at": _now(),
               "log": "", "result": None}
        self.jobs[job["id"]] = job
        self._save_job(job)
        self.pool.submit(self._run_pipeline_job, job["id"])
        return dict(job)

    def _run_pipeline_job(self, job_id: str):
        from .autonomous import pipeline
        with self.lock:
            job = self.jobs[job_id]
            job.update(status="running", started_at=_now())
            self._save_job(job)
        try:
            ws = Workspace(self.workspace_path(job["project_id"]))
            checkpoint = pipeline.status(ws, job["pipeline_id"])
            if checkpoint.get("status") == "cancelled":
                outcome = "cancelled"
            else:
                result = pipeline.run(ws, job["pipeline_id"])
                outcome = getattr(result.status, "value", result.status)
            with self.lock:
                job.update(status="succeeded" if outcome == "completed" else outcome if outcome in {"cancelled", "blocked", "paused"} else "failed",
                           result=self.pipeline_detail(job["project_id"], job["pipeline_id"]), finished_at=_now())
                if outcome not in {"completed", "cancelled"}:
                    job["error"] = f"Autonomous research {outcome}; inspect its saved status before resuming."
                self._save_job(job)
        except Exception as exc:
            with self.lock:
                # A queued cancellation can race the worker's first checkpoint.
                # Preserve the cancellation outcome rather than reporting a
                # research failure when run() correctly refuses a stopped run.
                try:
                    cancelled = pipeline.status(Workspace(self.workspace_path(job["project_id"])), job["pipeline_id"]).get("status") == "cancelled"
                except Exception:
                    cancelled = False
                job.update(status="cancelled" if cancelled else "failed", finished_at=_now())
                if not cancelled:
                    job["error"] = self.redact(str(exc))[:2000]
                self._save_job(job)
        self._recover_pipelines({})

    def _start_pending_pipeline(self, project_id: str):
        """Persist import-to-research intent across a closed browser/restart."""
        with self.lock:
            record = self.projects[project_id]
            pending = record.get("pending_autonomous")
            if not pending:
                return
            try:
                # A crash after creation but before consuming the intent must
                # not produce a second experiment series on restart.
                existing = [entry for entry in self.pipelines(project_id)
                            if entry.get("goal") == pending["goal"] and entry.get("created_at", "") >= record["created_at"]]
                if not existing:
                    self.start_pipeline(project_id, pending)
                record.pop("pending_autonomous", None)
                record.pop("autonomous_error", None)
            except Exception as exc:
                record["autonomous_error"] = self.redact(str(exc))[:2000]
            self._save_projects()

    def _recover_pipelines(self, interrupted: dict[str, set[str]]):
        """Restart interrupted workers, leaving provider/author stops explicit."""
        from .autonomous import pipeline
        with self.lock:
            if self.closed or not self.resume_jobs:
                return
            projects = list(self.projects.items())
        for project_id, record in projects:
            if record.get("status") != "ready":
                continue
            with self.lock:
                if self.closed:
                    return
                try:
                    ws = Workspace(self.workspace_path(project_id))
                    scheduled = {job.get("pipeline_id") for job in self.jobs.values()
                                 if job.get("project_id") == project_id and job.get("status") in {"queued", "running"}}
                    candidates = set(interrupted.get(project_id, set()))
                    for entry in pipeline.list_runs(ws):
                        if entry.get("created_at", "") <= self.started_at and entry["id"] not in scheduled and (entry.get("status") == "queued" or
                                entry.get("status") == "paused" and entry.get("code") == "INTERRUPTED"):
                            candidates.add(entry["id"])
                    for pipeline_id in sorted(candidates):
                        if any(job.get("project_id") == project_id and job.get("status") in {"queued", "running"} for job in self.jobs.values()):
                            break
                        recovered = pipeline.recover(ws, pipeline_id)
                        if recovered.status != "paused" or recovered.code != "INTERRUPTED" or recovered.cancellation_requested:
                            continue
                        self._capacity()
                        self._research_auth_guard(uses_codex=True)
                        self._project_available(project_id)
                        resumed = pipeline.resume(ws, pipeline_id)
                        self._submit_pipeline(project_id, resumed.id, "autonomous-resume")
                except Exception as exc:
                    record["autonomous_error"] = self.redact(str(exc))[:2000]
                    self._save_projects()

    def submit(self, project_id: str, action: str, args: list[str], *, timeout: int = 600) -> dict:
        with self.lock:
            self._capacity()
            self._research_auth_guard()
            if any(job["project_id"] == project_id and job["status"] in {"queued", "running"} for job in self.jobs.values()):
                raise ValueError("A job is already active for this project")
            job = {"id": "job-" + uuid4().hex[:12], "project_id": project_id, "action": action,
                   "status": "queued", "created_at": _now(), "log": "", "result": None}
            self.jobs[job["id"]] = job
            self._save_job(job)
            self.pool.submit(self._run_job, job["id"], args, timeout)
            return dict(job)

    def _save_job(self, job):
        write_json(safe_relative(self.data_root, f"jobs/{job['id']}.json"), job)

    def job(self, job_id: str) -> dict:
        with self.lock:
            return dict(self.jobs[_identifier(job_id)])

    def _run_job(self, job_id: str, args: list[str], timeout: int):
        with self.lock:
            job = self.jobs[job_id]
            job.update(status="running", started_at=_now())
            self._save_job(job)
        try:
            command = [sys.executable, "-m", "paper_factory.cli", "--workspace", str(self.workspace_path(job["project_id"])), *args]
            environment = dict(os.environ, PF_HOME=str(self.data_root / ".home"), PYTHONUNBUFFERED="1", GIT_TERMINAL_PROMPT="0", NO_COLOR="1")
            from .autonomous.provider import auth_root
            environment["PF_CODEX_AUTH_HOME"] = str(auth_root())
            # A server started with .venv/bin/python need not have an activated
            # shell. Select sibling tools from that same configured environment
            # before system tools, while retaining the user's remaining PATH.
            interpreter_bin = str(Path(sys.executable).absolute().parent)
            inherited_path = environment.get("PATH", "")
            environment["PATH"] = interpreter_bin + (os.pathsep + inherited_path if inherited_path else "")
            code, output = self._execute(command, environment, timeout, job)
            result = None
            # CLI stdout is JSON; diagnostic stderr precedes it in merged logs.
            decoder = json.JSONDecoder()
            for match in re.finditer(r"(?m)^[\[{]", output):
                try:
                    parsed, end = decoder.raw_decode(output[match.start():])
                    if not output[match.start() + end:].strip():
                        result = parsed
                        break
                except ValueError:
                    pass
            with self.lock:
                job.update(status="succeeded" if code == 0 else "failed", result=result, exit_code=code,
                           finished_at=_now())
                if code:
                    job["error"] = "The action failed; inspect the job log and evidence before retrying."
                if job["action"] == "start":
                    self.projects[job["project_id"]]["status"] = "ready" if code == 0 else "failed"
                    if code:
                        self.projects[job["project_id"]]["error"] = job["error"]
                    self._save_projects()
                self._save_job(job)
            if job["action"] == "start" and code == 0:
                self._start_pending_pipeline(job["project_id"])
        except Exception as exc:
            with self.lock:
                job.update(status="failed", finished_at=_now(), error=self.redact(str(exc))[:2000])
                if job["action"] == "start":
                    self.projects[job["project_id"]].update(status="failed", error=job["error"])
                    self._save_projects()
                self._save_job(job)

    def _execute(self, command: list[str], environment: dict, timeout: int, job: dict) -> tuple[int, str]:
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen(command, cwd=self.data_root, env=environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, **options)
        chunks: list[str] = []
        size = 0
        read_limit = MAX_LOG + max(4096, getattr(self.redact, "maximum_secret_length", 0))
        def consume():
            nonlocal size
            assert process.stdout is not None
            # Read beyond the retained-log boundary before redacting, so a
            # credential straddling that boundary cannot leave a visible prefix.
            while data := process.stdout.readline(read_limit):
                value = self.redact(data.decode("utf-8", errors="replace"))
                remaining = MAX_LOG - size
                if remaining > 0:
                    value = value[:remaining]
                    chunks.append(value)
                    size += len(value)
                    with self.lock:
                        job["log"] = "".join(chunks)
                        self._save_job(job)
            process.stdout.close()
        reader = threading.Thread(target=consume, daemon=True)
        reader.start()
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=15, check=False)
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait(timeout=15)
            reader.join(timeout=5)
            raise ValueError(f"Action exceeded the {timeout}-second time limit") from None
        reader.join(timeout=5)
        if reader.is_alive():
            # A child retaining stdout must not leave a job falsely running.
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            reader.join(timeout=5)
        return code, "".join(chunks)

    def _manifest_command(self, root: Path, manifest: ExperimentManifest, *, generated: bool = False):
        if generated and manifest.command == ["{python}", "-c", INVENTORY_SCRIPT]:
            return
        command = manifest.command
        if len(command) < 2 or command[0] not in {"{python}", "python", "python3"} or command[1].startswith("-"):
            raise ValueError("Web experiments require a Python script already present in the imported source; shell and inline commands are unavailable")
        script = safe_relative(root / "source", command[1])
        if script.suffix.lower() != ".py" or not script.is_file():
            raise ValueError("Experiment script must be an existing source-relative .py file")
        if len(command) > 80 or any(len(value) > 1024 or "\x00" in value for value in command):
            raise ValueError("Experiment command exceeds the supported argument limits")
        if manifest.timeout_seconds > 900:
            raise ValueError("Web experiments have a 900-second maximum timeout")

    def action(self, project_id: str, payload: dict) -> dict:
        action = payload.get("action")
        if action not in ACTIONS:
            raise ValueError("Unknown or unsupported research action")
        root = self.workspace_path(project_id)
        if self.projects[project_id]["status"] != "ready":
            raise ValueError("Project import must succeed before running actions")
        ws = Workspace(root)
        args: list[str] = []
        common = {"action"}
        if action == "research":
            _strict_keys(payload, common | {"title", "question", "domain", "candidate"})
            args = ["research"]
            if payload.get("candidate") is not None:
                args.extend(["--candidate", _identifier(payload["candidate"])])
            else:
                args.extend(["--title", _text(payload.get("title"), "title", maximum=500), "--question", _text(payload.get("question"), "question")])
            domain = payload.get("domain", "software_engineering")
            if domain not in {"generic_empirical", "software_engineering"}:
                raise ValueError("Unsupported study domain")
            args.extend(["--domain", domain])
        elif action == "register":
            _strict_keys(payload, common | {"manifest"})
            if not isinstance(payload.get("manifest"), dict):
                raise ValueError("manifest must contain an object")
            manifest = ExperimentManifest.model_validate(payload["manifest"])
            self._manifest_command(root, manifest)
            # Validation and execution remain the CLI's responsibility.
            inbox = safe_relative(root, f"web-inputs/{manifest.id}-{uuid4().hex[:8]}.json")
            write_json(inbox, manifest)
            args = ["experiment", "register", str(inbox)]
        elif action == "run":
            _strict_keys(payload, common | {"experiment"})
            selected = payload.get("experiment")
            manifest = ws.get("manifest", _identifier(selected), ExperimentManifest) if selected else ws.latest("manifest", ExperimentManifest)
            self._manifest_command(root, manifest, generated=True)
            args = ["experiment", "run", manifest.id]
        elif action in {"literature-search", "literature-doi"}:
            _strict_keys(payload, common | {"query", "doi", "study", "limit"})
            field = "query" if action == "literature-search" else "doi"
            value = _text(payload.get(field), field, maximum=500)
            args = ["literature", "search" if field == "query" else "doi"]
            if field == "query":
                limit = payload.get("limit", 5)
                if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
                    raise ValueError("limit must be an integer between 1 and 20")
                args.extend(["--limit", str(limit)])
            if payload.get("study"):
                args.extend(["--study", _identifier(payload["study"])])
            args.extend(["--", value])
        elif action in {"manuscript-build", "manuscript-render"}:
            _strict_keys(payload, common | {"study", "paper", "pdf", "author"})
            args = ["manuscript", "build" if action == "manuscript-build" else "render"]
            field = "study" if action == "manuscript-build" else "paper"
            if payload.get(field):
                args.extend([f"--{field}", _identifier(payload[field])])
            pdf = payload.get("pdf", True)
            if not isinstance(pdf, bool):
                raise ValueError("pdf must be a boolean")
            if pdf:
                args.append("--pdf")
            explicit_pandoc = os.environ.get("PYPANDOC_PANDOC")
            if explicit_pandoc:
                configured = Path(explicit_pandoc).expanduser()
                if configured.is_file() and os.access(configured, os.X_OK):
                    args.extend(["--pandoc", str(configured.resolve())])
            if "author" in payload:
                if action != "manuscript-build" or not isinstance(payload["author"], dict):
                    raise ValueError("author metadata is supported only when building a manuscript")
                from .author import AuthorProfile
                AuthorProfile.model_validate(payload["author"])
                args.extend(["--author-json", json.dumps(payload["author"], ensure_ascii=False)])
        else:
            _strict_keys(payload, common | {"paper"})
            args = ["integrity", "check"]
            if payload.get("paper"):
                args.extend(["--paper", _identifier(payload["paper"])])
        return {"job": self.submit(project_id, action, args, timeout=1000 if action == "run" else 600)}

    def edit_canonical(self, project_id: str, paper_id: str, payload: dict) -> dict:
        _strict_keys(payload, {"canonical"})
        if not isinstance(payload.get("canonical"), dict):
            raise ValueError("canonical must contain an object")
        with self.lock:
            if any(job["project_id"] == project_id and job["status"] in {"queued", "running"} for job in self.jobs.values()):
                raise ValueError("Wait for the project's current job before editing")
            ws = Workspace(self.workspace_path(project_id))
            # Share approval/render's persistent paper lock, in approval's
            # paper→study order. The in-process mutex alone cannot exclude CLI
            # processes that freeze or rebuild the same manuscript.
            with ws.lock(f"paper-{_identifier(paper_id)}"):
                paper = ws.get("paper", paper_id, Paper)
                with ws.lock(f"study-{paper.study_id}"):
                    current = ws.get("paper", paper_id, Paper)
                    if current.study_id != paper.study_id:
                        raise ValueError("Paper study identity changed during editing")
                    if current.state == PaperState.AUTHOR_APPROVED or ws.path(f"freezes/{current.id}").exists():
                        raise ValueError("An approved manuscript is immutable; create a revision through the CLI")
                    from .project import verify_snapshot
                    from .revisions import assert_editable
                    assert_editable(ws, current)
                    verify_snapshot(ws)
                    doc = Document.model_validate(payload["canonical"])
                    if doc.paper_id != current.id or doc.study_id != current.study_id:
                        raise ValueError("Canonical document must retain its paper and study identities")
                    errors = validate_document(ws, doc)
                    if errors:
                        raise ValueError("Canonical validation failed: " + "; ".join(errors)[:4000])
                    write_json(ws.path(f"manuscripts/{current.id}/canonical.json"), doc)
            return {"saved": True, "paper": paper.id, "notice": "Render the edited canonical manuscript, then rerun integrity checks."}

    def close(self):
        with self.lock:
            self.closed = True
            connection = self._connection
        if connection is not None:
            connection.close()
        self.pool.shutdown(wait=True, cancel_futures=False)


class WebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_close(self):
        super().server_close()
        if hasattr(self, "state"):
            self.state.close()


class WebHandler(BaseHTTPRequestHandler):
    server_version = "PaperFactory/" + __version__
    protocol_version = "HTTP/1.0"

    def log_message(self, format, *args):
        # Paths and request bodies may contain personal/project information.
        return

    @property
    def state(self) -> WebState:
        return self.server.state

    def _headers(self, status: int, mime: str, size: int, *, attachment: str | None = None):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(size))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        policy = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self'; frame-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        if mime.startswith("image/svg+xml"):
            policy = "sandbox; default-src 'none'; style-src 'unsafe-inline'"
        self.send_header("Content-Security-Policy", policy)
        if attachment:
            safe = re.sub(r"[^A-Za-z0-9_.-]", "_", attachment)
            self.send_header("Content-Disposition", f'attachment; filename="{safe}"')
        self.end_headers()

    def _reply(self, status: int, value: object):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(data))
        if self.command != "HEAD":
            self.wfile.write(data)

    def _file(self, path: Path, *, download: bool = False):
        ensure_unlinked(path)
        if not path.is_file():
            raise KeyError("Unknown or oversized file")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix.lower() in {".md", ".tex", ".bib"}:
            mime = "text/plain; charset=utf-8"
        with path.open("rb") as stream:
            info = os.fstat(stream.fileno())
            ensure_unlinked(path)
            if not stat.S_ISREG(info.st_mode) or info.st_size > _file_limit(path):
                raise KeyError("Unknown or oversized file")
            self._headers(200, mime, info.st_size, attachment=path.name if download or path.suffix.lower() == ".zip" else None)
            if self.command != "HEAD":
                remaining = info.st_size
                while remaining:
                    chunk = stream.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

    def _parts(self) -> list[str]:
        parsed = urlsplit(self.path)
        if parsed.scheme or parsed.netloc:
            raise ValueError("Request target must be a relative URL")
        decoded = unquote(parsed.path, errors="strict")
        if not decoded.startswith("/") or "\\" in decoded or any(ord(c) < 32 for c in decoded):
            raise ValueError("Invalid request path")
        parts = decoded[1:].split("/")
        if any(part in {".", ".."} for part in parts) or any(not part for part in parts[:-1]):
            raise ValueError("Invalid request path")
        return parts

    def _write_guard(self):
        if not self.server.writes_enabled:
            raise PermissionError("Research writes require a loopback-bound server")
        try:
            if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                raise PermissionError("Research writes require a local connection")
        except ValueError:
            raise PermissionError("Research writes require a local connection") from None
        host = self.headers.get("Host", "")
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}", f"[::1]:{self.server.server_port}"}
        if host not in allowed:
            raise PermissionError("Untrusted Host header")
        if self.headers.get("Origin") != "http://" + host:
            raise PermissionError("Write requests require the server's exact same Origin")
        if self.headers.get("Sec-Fetch-Site") in {"cross-site", "same-site"}:
            raise PermissionError("Cross-site writes are unavailable")
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise ValueError("Write requests require application/json")

    def _host_guard(self):
        # Reject DNS rebinding even for readable project data.
        if self.server.writes_enabled:
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}", f"[::1]:{self.server.server_port}"}
            if self.headers.get("Host", "") not in allowed:
                raise PermissionError("Untrusted Host header")

    def _body(self) -> dict:
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Chunked request bodies are unsupported")
        length = self.headers.get("Content-Length")
        if not length or not length.isdigit() or int(length) <= 0:
            raise ValueError("Request body must be between 1 byte and 1 MiB")
        self.connection.settimeout(10)
        # Consume a bounded overflow byte before replying. Closing with an
        # unread body can reset the Windows connection and hide the HTTP error.
        data = self.rfile.read(min(int(length), MAX_BODY + 1))
        self._body_consumed = len(data) == int(length)
        if int(length) > MAX_BODY:
            raise ValueError("Request body must be between 1 byte and 1 MiB")
        if len(data) != int(length):
            raise ValueError("Incomplete request body")
        def invalid(value):
            raise ValueError("JSON numbers must be finite")
        value = json.loads(data, parse_constant=invalid)
        if not isinstance(value, dict):
            raise ValueError("Request JSON must contain an object")
        return value

    def _drain_denied_body(self):
        """Avoid a Windows reset hiding denials of small, complete requests."""
        if getattr(self, "_body_consumed", False) or self.headers.get("Transfer-Encoding"):
            return
        length = self.headers.get("Content-Length", "")
        if (not length.isdigit() or len(length) > 7 or not 0 < int(length) <= MAX_BODY
                or self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json"):
            return
        previous_timeout = self.connection.gettimeout()
        try:
            remaining = int(length)
            deadline = time.monotonic() + 0.25
            while remaining:
                available = deadline - time.monotonic()
                if available <= 0:
                    break
                self.connection.settimeout(available)
                chunk = self.rfile.read1(min(remaining, 65536))
                if not chunk:
                    break
                remaining -= len(chunk)
            self._body_consumed = remaining == 0
        except (OSError, ValueError):
            pass
        finally:
            self.connection.settimeout(previous_timeout)

    def _dispatch(self):
        self._host_guard()
        parts = self._parts()
        if not self.server.writes_enabled and len(parts) > 1 and parts[:1] == ["api"] and parts[1] in {"projects", "jobs", "agent"}:
            raise PermissionError("Project workspaces and jobs require a loopback-bound server")
        if self.command in {"POST", "PUT"}:
            self._write_guard()
            body = self._body()
            if self.command == "POST" and len(parts) == 4 and parts[:3] == ["api", "agent", "connection"] and parts[3] in {"login", "cancel", "probe", "logout"}:
                result = self.state.connection_action(parts[3], body)
                if result.get("code") in {"CONNECTION_BUSY", "RESEARCH_BUSY"}:
                    return self._reply(409, {"error": result.get("message"), "code": result["code"]})
                if result.get("status") in {"blocked", "failed"} and result.get("code"):
                    return self._reply(400, {"error": result.get("message"), "code": result["code"]})
                return self._reply(202 if parts[3] in {"login", "probe"} else 200, result)
            if self.command == "POST" and parts == ["api", "agent", "repositories"]:
                return self._reply(200, self.state.recommend_repositories(body))
            if self.command == "POST" and parts == ["api", "projects"]:
                return self._reply(202, self.state.import_project(body))
            if self.command == "POST" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "actions":
                return self._reply(202, self.state.action(parts[2], body))
            if self.command == "POST" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "pipelines":
                return self._reply(202, self.state.start_pipeline(parts[2], body))
            if self.command == "POST" and len(parts) == 6 and parts[:2] == ["api", "projects"] and parts[3] == "pipelines" and parts[5] in {"cancel", "resume"}:
                return self._reply(202 if parts[5] == "resume" else 200, self.state.control_pipeline(parts[2], parts[4], parts[5], body))
            if self.command == "PUT" and len(parts) == 6 and parts[:2] == ["api", "projects"] and parts[3] == "manuscripts" and parts[5] == "canonical":
                return self._reply(200, self.state.edit_canonical(parts[2], parts[4], body))
            raise KeyError("Unknown write endpoint")
        if self.command not in {"GET", "HEAD"}:
            return self._reply(405, {"error": "Method is unavailable"})
        if parts == ["api", "health"]:
            return self._reply(200, {"status": "ok", "version": __version__, "writes_enabled": self.server.writes_enabled,
                                     "actions": sorted(ACTIONS), "execution_boundary": "Imported Python scripts run with this user's rights in separate working copies."})
        if parts == ["api", "agent", "status"]:
            return self._reply(200, self.state.agent_status())
        if parts == ["api", "agent", "connection"]:
            return self._reply(200, self.state.connection_status())
        if parts == ["api", "studies"]:
            return self._reply(200, self.state.catalog())
        if len(parts) >= 3 and parts[:2] == ["api", "studies"]:
            slug = _identifier(parts[2])
            if len(parts) == 3:
                return self._reply(200, self.state.catalog(slug))
            if len(parts) >= 5 and parts[3] == "files":
                return self._file(self.state.catalog_file(slug, "/".join(parts[4:])), download=urlsplit(self.path).query == "download=1")
            if len(parts) == 4 and parts[3] == "bundle":
                study = self.state.catalog(slug)
                if bundle := study.get("reproducibility_bundle"):
                    return self._file(self.state.catalog_file(slug, bundle), download=True)
                entries = study["files"]
                if sum(entry["size"] for entry in entries) > MAX_BUNDLE:
                    raise ValueError("Study bundle exceeds 96 MiB; download artifacts individually")
                stream = BytesIO()
                with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("manifest.json", json.dumps(study, indent=2, ensure_ascii=False))
                    for entry in entries:
                        archive.write(self.state.catalog_file(slug, entry["path"]), arcname=entry["path"])
                value = stream.getvalue()
                self._headers(200, "application/zip", len(value), attachment=slug + ".zip")
                if self.command != "HEAD":
                    self.wfile.write(value)
                return
        if parts == ["api", "projects"]:
            with self.state.lock:
                return self._reply(200, {"projects": [dict(value) for value in self.state.projects.values()]})
        if len(parts) >= 3 and parts[:2] == ["api", "projects"]:
            if len(parts) == 3:
                return self._reply(200, self.state.project_detail(parts[2]))
            if len(parts) >= 5 and parts[3] == "files":
                return self._file(self.state.project_file(parts[2], "/".join(parts[4:])), download=urlsplit(self.path).query == "download=1")
            if len(parts) == 4 and parts[3] == "pipelines":
                return self._reply(200, {"pipelines": self.state.pipelines(parts[2])})
            if len(parts) == 5 and parts[3] == "pipelines":
                return self._reply(200, self.state.pipeline_detail(parts[2], parts[4]))
        if parts == ["api", "jobs"]:
            with self.state.lock:
                return self._reply(200, {"jobs": [dict(value) for value in sorted(self.state.jobs.values(), key=lambda value: value["created_at"], reverse=True)][:200]})
        if len(parts) == 3 and parts[:2] == ["api", "jobs"]:
            return self._reply(200, self.state.job(parts[2]))
        if parts and parts[0] == "api":
            raise KeyError("Unknown API endpoint")
        relative = "/".join(parts).rstrip("/") or "index.html"
        path = safe_relative(self.state.static_root, relative)
        if path.suffix.lower() not in {".html", ".css", ".js", ".ico", ".png", ".svg", ".woff", ".woff2"}:
            raise KeyError("Unknown static file")
        return self._file(path)

    def _handle(self):
        self._body_consumed = False
        try:
            self._dispatch()
        except PermissionError as exc:
            self._drain_denied_body()
            self._reply(403, {"error": str(exc)})
        except KeyError:
            self._reply(404, {"error": "Resource was not found"})
        except ProviderBlocked as exc:
            self._reply(400, {"error": exc.message, "code": exc.code})
        except (ValueError, TypeError, UnicodeError) as exc:
            self._reply(400, {"error": self.state.redact(str(exc))[:4000]})
        except (OSError, sqlite3.Error):
            self._reply(500, {"error": "The workspace could not be accessed; inspect server configuration"})

    do_GET = _handle
    do_HEAD = _handle
    do_POST = _handle
    do_PUT = _handle
    do_DELETE = _handle
    do_OPTIONS = _handle


def create_server(host: str = "127.0.0.1", port: int = 8765, *,
                  studies_root: Path | str | None = None,
                  data_root: Path | str | None = None,
                  static_root: Path | str | None = None,
                  source_roots: list[Path] | None = None) -> WebServer:
    """Create a server; nonloopback binds expose an artifact-only preview."""
    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("port must be an integer between 0 and 65535")
    try:
        writes_enabled = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        writes_enabled = False
    # Establish the listening boundary before any durable workers resume. A
    # failed bind must not launch model work in an inaccessible new server.
    server = WebServer((host, port), WebHandler)
    try:
        state = WebState(Path(studies_root) if studies_root is not None else pf_home() / "studies",
                         Path(data_root) if data_root is not None else pf_home() / "web",
                         Path(static_root) if static_root is not None else Path(__file__).parent / "web_static",
                         source_roots, resume_jobs=writes_enabled)
    except Exception:
        server.server_close()
        raise
    server.state = state
    server.writes_enabled = writes_enabled
    return server


def serve(host: str = "127.0.0.1", port: int = 8765, **kwargs):
    """Serve until interrupted; keep jobs and evidence available after restart."""
    server = create_server(host, port, **kwargs)
    print(f"Paper Factory: http://{host}:{server.server_port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

"""Local research controller: the host writes proposals; tools verify evidence.

No model provider, account state, unrestricted execution or model-supplied
measurements are part of this service. CLI and MCP adapters use the same API.
"""

import ast
import codecs
from concurrent.futures import ThreadPoolExecutor, wait
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
import zipfile

from . import conversion, project
from .author import load_author
from .autonomous import literature, science
from .autonomous.models import CodeBundle, FrozenArtifact, ManuscriptDraft, ResearchPlan, ScientificReview
from .autonomous.runner import LIMITS, research_runner
from .models import Project, now, uid
from .workflow_models import Workflow
from .workspace import Workspace, digest_file, ensure_unlinked, loads_json, pf_home, safe_relative, write_json

MAX_BUNDLE_BYTES = 96 * 1024 * 1024
SCHEMAS = {"plan": ResearchPlan.model_json_schema(), "code": CodeBundle.model_json_schema(),
           "review": ScientificReview.model_json_schema(), "manuscript": ManuscriptDraft.model_json_schema()}
READABLE_EVIDENCE = {"plan", "observations", "analysis", "literature", "manuscript", "canonical"}


class WorkflowError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _accepted(value: dict) -> ScientificReview:
    review = ScientificReview.model_validate(value)
    if not review.accepted or review.issues:
        raise WorkflowError("REVIEW_REJECTED", "; ".join(review.issues) or "Native host review did not accept this submission")
    return review


def _diagnostic(value: object, limit: int = 1800) -> str:
    """Bounded contract/runner feedback with host paths and secrets removed."""
    text = science._redact_source(str(value or ""))
    text = re.sub(r"(?i)\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_.-]{16,}", "[REDACTED TOKEN]", text)
    text = re.sub(r"(?i)(?:[a-z]:[\\/]|\\\\)[^\s\"'<>]+", "[private path]", text)
    text = re.sub(r"(?<![A-Za-z0-9:/])/(?:[^\s\"'<>]+)", "[private path]", text)
    return text[:limit]


def _freeze(ws: Workspace, record: Workflow, key: str, path: Path) -> None:
    relative = path.absolute().relative_to(ws.root).as_posix()
    path = ws.path(relative)
    record.artifacts[key] = FrozenArtifact(path=relative, sha256=digest_file(path), size=path.stat().st_size)


def _artifact(ws: Workspace, record: Workflow, key: str) -> Path:
    artifact = record.artifacts.get(key)
    if artifact is None:
        raise WorkflowError("ARTIFACT_MISSING", "Required research artifact is missing: " + key)
    path = ws.path(artifact.path)
    if not path.is_file() or path.stat().st_size != artifact.size or digest_file(path) != artifact.sha256:
        raise WorkflowError("ARTIFACT_CHANGED", "Frozen research artifact changed: " + key)
    return path


def _read(ws: Workspace, record: Workflow, key: str):
    return loads_json(_artifact(ws, record, key).read_bytes())


def _verify_artifacts(ws: Workspace, record: Workflow) -> None:
    project.verify_snapshot(ws)
    for key in record.artifacts:
        _artifact(ws, record, key)
    if "bundle" in record.artifacts:
        metadata = _read(ws, record, "bundle")
        root = _artifact(ws, record, "bundle").parent
        expected = {"bundle.json", "review.json", *(item["path"] for item in metadata["files"])}
        actual = set()
        for path in root.rglob("*"):
            ensure_unlinked(path)
            if path.is_file():
                actual.add(path.relative_to(root).as_posix())
        if actual != expected:
            raise WorkflowError("ARTIFACT_CHANGED", "Frozen experiment file inventory changed")
        for item in metadata["files"]:
            path = safe_relative(root, item["path"])
            if not path.is_file() or digest_file(path) != item["sha256"] or path.stat().st_size != item["size"]:
                raise WorkflowError("ARTIFACT_CHANGED", "Frozen experiment source changed")


def _production_execution(execution: dict, plan: ResearchPlan) -> None:
    if execution.get("coverage_truncated") is not False:
        raise WorkflowError("PRODUCTION_EXECUTION_UNVERIFIED", "Production-call profiling was incomplete")
    source, function = plan.production_entrypoint.rsplit(":", 1)
    calls = execution.get("production_calls")
    if not isinstance(calls, list) or not any(
        isinstance(call, dict) and call.get("path") == source and
        call.get("function") in {function, function.rsplit(".", 1)[-1]} and
        type(call.get("calls")) is int and call["calls"] > 0 for call in calls
    ):
        raise WorkflowError("PRODUCTION_EXECUTION_UNVERIFIED", "No actual call of the frozen production callable was recorded")


def _append_figures(ws: Workspace, record: Workflow, markdown: Path) -> None:
    figures = [_artifact(ws, record, key).name for key in sorted(record.artifacts)
               if key.startswith("analysis-") and record.artifacts[key].path.endswith(".png")]
    if figures:
        with markdown.open("a", encoding="utf-8") as stream:
            stream.write("\n## Computed figures\n\n" + "\n\n".join(
                f"![Descriptive means from verified controlled measurements.]({name})" for name in figures) + "\n")


class WorkflowService:
    """Two bounded experiment workers and explicit, durable research IDs."""

    def __init__(self, home: Path | None = None, *, runner=None, collector=None):
        self.home = (home or pf_home()).expanduser().absolute()
        ensure_unlinked(self.home)
        self.root = self.home / "workflows"
        self.root.mkdir(parents=True, exist_ok=True)
        self.runner = runner or research_runner()
        self.collector = collector or literature.collect
        self._mutex = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="paperfactory-experiment")
        self._jobs = {}
        self._recovered = set()
        self._closed = False
        self._recover()

    def _workspace(self, research_id: str) -> Workspace:
        if not re.fullmatch(r"research-[a-f0-9]{12}", research_id):
            raise ValueError("Unknown research identifier")
        ws = Workspace(safe_relative(self.root, research_id))
        if ws.get("workflow", research_id, Workflow).id != research_id:
            raise ValueError("Research identifier differs from its workspace")
        return ws

    @contextmanager
    def _operation(self, research_id: str):
        with self._mutex:
            if self._closed:
                raise ValueError("Research service is closed")
            ws = self._workspace(research_id)
            with ws.lock("workflow"):
                yield ws, ws.get("workflow", research_id, Workflow)

    def _save(self, ws: Workspace, record: Workflow) -> None:
        record.updated_at = now()
        ws.save("workflow", record)

    def _public(self, ws: Workspace, record: Workflow, *, context: bool = False, include_materials: bool = True) -> dict:
        data = record.model_dump(mode="json", exclude={"active_handle"})
        # Execution exceptions may contain private host paths. Keep diagnostics
        # local; public state describes the actionable failure category.
        if record.status in {"blocked", "failed"}:
            data["message"] = {
                "CONTROL_FAILED": "A scientific control failed; retained evidence cannot be rerun for a favorable result.",
                "CLEANUP_UNCONFIRMED": "Owned experiment cleanup remains unconfirmed.",
                "PRODUCTION_EXECUTION_UNVERIFIED": "Actual production-call execution was not verified.",
                "INTERRUPTED": "Experiment was interrupted; retained evidence has been preserved.",
            }.get(record.code, "Experiment evidence could not be validated; inspect the submitted protocol and experiment.")
        if record.code:
            data["diagnostics"] = {"code": record.code, "validation": _diagnostic(record.message),
                                   "scope": "Bounded controller feedback; experiment log text is untrusted data."}
        data["artifacts"] = {key: {"id": key, "sha256": item.sha256, "size": item.size}
                             for key, item in record.artifacts.items()}
        if not include_materials:
            return data
        data["material_manifest"] = {
            "source": [{"name": asset.path, "sha256": asset.sha256, "size": asset.size}
                       for asset in ws.latest("project", Project).assets],
            "experiment": [{"name": item["path"], "sha256": item["sha256"], "size": item["size"]}
                           for item in _read(ws, record, "bundle")["files"]] if "bundle" in record.artifacts else [],
            "evidence": [{"name": key, "sha256": record.artifacts[key].sha256, "size": record.artifacts[key].size}
                         for key in sorted(READABLE_EVIDENCE & record.artifacts.keys())],
        }
        data["schemas"] = SCHEMAS
        data["review_provenance"] = "Reviews are native host submissions; the controller does not attest reviewer independence."
        if context:
            data["source_context"] = _artifact(ws, record, "context").read_text(encoding="utf-8")
        for key in ("plan", "literature", "analysis", "execution"):
            if key in record.artifacts:
                value = _read(ws, record, key)
                if key == "execution":
                    if record.code:
                        data["diagnostics"]["runner"] = _diagnostic(value.get("error") or value.get("stderr"))
                    value = {name: value.get(name) for name in (
                        "status", "code", "backend", "simulation", "exit_code", "coverage_mechanism", "coverage_truncated",
                        "production_calls", "cleanup_confirmed", "duration_seconds", "limits", "source_digest",
                        "protocol_sha256", "bundle_sha256")}
                    value["cleanup_reconciled"] = self._confirmed_cleanup(ws, record)
                data[key] = value
        source_context = _artifact(ws, record, "context").read_text(encoding="utf-8")
        if record.code == "CLEANUP_UNCONFIRMED":
            data["instructions"] = "Owned worker cleanup is unconfirmed. Do not submit code or start another experiment. Restore the isolated runtime prerequisites and restart the plugin worker so owned cleanup can be reconciled."
        elif record.terminal_control_failure:
            data["instructions"] = "The scientific control failed. Preserve the negative result; do not regenerate or rerun this study to obtain favorable observations."
        elif record.status == "running":
            data["instructions"] = "The owned experiment runs in the background. Read research status until it finishes, or cancel it. Do not start another execution."
        elif record.stage == "created":
            data["instructions"] = science.planning_prompt(source_context, record.goal)
        elif record.stage in {"planned", "code_ready"}:
            if record.stage == "code_ready" and record.status == "ready":
                data["instructions"] = "The reviewed code bundle is frozen. Start the isolated experiment, then read status until analysis is ready."
            else:
                data["instructions"] = science.code_prompt(ResearchPlan.model_validate(data["plan"]), source_context,
                    data.get("diagnostics") if record.code else None)
                data["instructions"] += "\nHave a fresh native host reviewer inspect the complete bundle against the frozen protocol before submitting its ScientificReview. The controller records a host-submitted review and does not attest independence."
        elif record.stage == "analyzed":
            if "literature" not in data:
                data["instructions"] = "Collect literature for the frozen queries before writing; Related Work requires inspected abstract or full-text evidence."
            else:
                data["instructions"] = science.writing_prompt(ResearchPlan.model_validate(data["plan"]), data["analysis"],
                                                               data["literature"], data["execution"])
                data["instructions"] += "\nHave a fresh native host reviewer inspect the manuscript's interpretation against the retained evidence before submitting its ScientificReview. Numerical integrity is not scientific peer review."
        elif record.stage == "manuscript":
            data["instructions"] = "Export the validated manuscript to Markdown, PDF, DOCX, standalone TeX and a reproduction archive. Export recomputes raw results and independently reopens the native documents."
        else:
            data["instructions"] = "Verified artifacts are ready for the author's scientific review. Download server-owned artifact IDs; no journal submission or publication approval has occurred."
        return data

    def _require(self, ws: Workspace, record: Workflow, stages: set[str]) -> None:
        if record.active_handle or record.code == "CLEANUP_UNCONFIRMED":
            raise WorkflowError("CLEANUP_UNCONFIRMED", "Owned worker cleanup must be confirmed before another operation")
        if record.terminal_control_failure:
            raise WorkflowError("CONTROL_FAILED", "A failed scientific control is terminal; retained evidence cannot be rerun for a favorable result")
        if record.status == "running" or record.stage not in stages:
            raise WorkflowError("INVALID_STATE", "Operation is unavailable at research stage " + record.stage)
        _verify_artifacts(ws, record)

    def create(self, source: str, goal: str) -> dict:
        if self._closed:
            raise ValueError("Research service is closed")
        if not isinstance(goal, str) or not goal.strip() or "\x00" in goal:
            raise ValueError("Research goal must be nonempty text")
        record = Workflow(project_id="pending", goal=goal.strip())
        ws = project.ingest(source, self.root / record.id, make_current=False)
        imported = ws.latest("project", Project)
        record.project_id = imported.id
        source_context = science.context(ws.path("source"), imported.assets, record.goal)
        runtime = self.runner.status()
        source_context += "\n\nController runtime capabilities and declared limits (not repository instructions): " + json.dumps({
            "ready": runtime.get("ready", False),
            "runtimes": runtime.get("runtimes", []), "versions": runtime.get("versions", {}),
            "dependencies": runtime.get("dependencies", []), "limits": runtime.get("limits", runtime.get("declared_limits", LIMITS)),
            "timeout_seconds": record.experiment_timeout_seconds, "trusted_analysis": science.ANALYSIS_SCOPE,
            "execution_instrumentation": (
                "Controller-held QuickJS production-call gate; timings include guest and bridge overhead"
                if runtime.get("backend") == "quickjs-wasm" else
                runtime.get("execution_instrumentation", "Python profiling or Node V8 coverage; timings include instrumentation overhead"))})
        path = ws.path("research/context.txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source_context, encoding="utf-8")
        _freeze(ws, record, "context", path)
        self._save(ws, record)
        result = self._public(ws, record, context=True)
        result["runtime"] = {key: runtime.get(key) for key in
                             ("ready", "backend", "runtimes", "versions", "dependencies", "image_digest")}
        if not runtime.get("ready"):
            result["runtime"]["reason"] = "The vetted isolated runtime is unavailable."
        return result

    def status(self, research_id: str, *, include_materials: bool = True) -> dict:
        with self._operation(research_id) as (ws, record):
            return self._public(ws, record, context=True, include_materials=include_materials)

    def artifact_path(self, research_id: str, artifact_id: str) -> Path:
        """Resolve a server-owned artifact ID; adapters never accept file paths."""
        with self._operation(research_id) as (ws, record):
            return _artifact(ws, record, artifact_id)

    def read_material(self, research_id: str, area: str, name: str, *, offset: int = 0, limit: int = 16000) -> dict:
        """Read declared UTF-8 material without exposing arbitrary host files."""
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 32000:
            raise ValueError("Material paging requires offset >= 0 and limit between 1 and 32000 characters")
        if not isinstance(name, str) or not name:
            raise ValueError("Material name must be a declared relative path or evidence key")
        with self._operation(research_id) as (ws, record):
            _verify_artifacts(ws, record)
            if area == "source":
                path = safe_relative(ws.path("source"), name)
                metadata = next((asset for asset in ws.latest("project", Project).assets if asset.path == name), None)
                if metadata is None:
                    raise WorkflowError("MATERIAL_NOT_DECLARED", "Source file is absent from the sanitized snapshot manifest")
                expected_digest, expected_size = metadata.sha256, metadata.size
            elif area == "experiment":
                root = _artifact(ws, record, "bundle").parent
                path = safe_relative(root, name)
                metadata = next((item for item in _read(ws, record, "bundle")["files"] if item["path"] == name), None)
                if metadata is None:
                    raise WorkflowError("MATERIAL_NOT_DECLARED", "Experiment file is absent from the current frozen bundle")
                expected_digest, expected_size = metadata["sha256"], metadata["size"]
            elif area == "evidence":
                if name not in READABLE_EVIDENCE:
                    raise WorkflowError("MATERIAL_NOT_DECLARED", "Only declared scientific evidence keys may be read")
                path = _artifact(ws, record, name)
                metadata = record.artifacts[name]
                expected_digest, expected_size = metadata.sha256, metadata.size
            else:
                raise ValueError("Material area must be source, experiment or evidence")
            digest = hashlib.sha256()
            decoder = codecs.getincrementaldecoder("utf-8")()
            size, total_chars = 0, 0
            fragments = []
            try:
                with path.open("rb") as stream:
                    while True:
                        chunk = stream.read(65536)
                        digest.update(chunk)
                        size += len(chunk)
                        text = decoder.decode(chunk, final=not chunk)
                        if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", text):
                            raise WorkflowError("MATERIAL_NOT_TEXT", "Binary material is unavailable through text reading")
                        start = max(0, offset - total_chars)
                        end = min(len(text), offset + limit - total_chars)
                        if end > start:
                            fragments.append(text[start:end])
                        total_chars += len(text)
                        if not chunk:
                            break
            except UnicodeDecodeError:
                raise WorkflowError("MATERIAL_NOT_TEXT", "Only UTF-8 text material may be read") from None
            actual_digest = digest.hexdigest()
            if size != expected_size or actual_digest != expected_digest:
                raise WorkflowError("ARTIFACT_CHANGED", "Material changed while being read")
            end = min(offset + limit, total_chars)
            return {"research_id": research_id, "area": area, "name": name, "offset": offset, "limit": limit,
                    "total_chars": total_chars, "next_offset": end if end < total_chars else None,
                    "sha256": actual_digest, "text": "".join(fragments), "is_untrusted_data": True}

    def submit_plan(self, research_id: str, value: dict) -> dict:
        plan = ResearchPlan.model_validate(value)
        with self._operation(research_id) as (ws, record):
            self._require(ws, record, {"created"})
            science.validate_plan(plan, ws.path("source"))
            if any(not safe_relative(ws.path("source"), path).is_file() for path in plan.source_files):
                raise WorkflowError("PLAN_SOURCE_MISSING", "Protocol refers to absent source files")
            runtime = self.runner.status()
            if not runtime.get("ready") or plan.runtime not in runtime.get("runtimes", []):
                raise WorkflowError("ISOLATION_UNAVAILABLE", "The required isolated runtime is unavailable")
            missing = set(plan.dependencies) - set(runtime.get("dependencies", []))
            if missing:
                raise WorkflowError("RUNTIME_DEPENDENCY_UNAVAILABLE", "Unprovisioned dependencies: " + ", ".join(sorted(missing)))
            plan.parameters["execution_instrumentation"] = (
                "Controller-held QuickJS production-call gate; timings include guest and bridge overhead"
                if plan.runtime == "quickjs" else
                "Python profiling or Node V8 coverage is enabled; timing includes instrumentation overhead"
            )
            limitation = "Production-call instrumentation affects execution overhead; measurements cannot establish uninstrumented production performance."
            if len(plan.limitations) == 12:
                plan.limitations[-1] += " " + limitation
            else:
                plan.limitations.append(limitation)
            path = ws.path("research/protocol.json")
            write_json(path, plan)
            _freeze(ws, record, "plan", path)
            record.stage = "planned"
            self._save(ws, record)
            return self._public(ws, record)

    def collect_literature(self, research_id: str) -> dict:
        with self._operation(research_id) as (ws, record):
            self._require(ws, record, {"planned", "code_ready", "analyzed"})
            if "literature" in record.artifacts:
                evidence = _read(ws, record, "literature")
                if not any(source.get("scope") in {"abstract", "full_text"} and source.get("excerpts")
                           for source in evidence.get("sources", [])):
                    raise WorkflowError("LITERATURE_EVIDENCE_INSUFFICIENT", "Retained metadata cannot support Related Work")
                return self._public(ws, record)
            plan = ResearchPlan.model_validate(_read(ws, record, "plan"))
            evidence = self.collector(plan.literature_queries, ws.path("research"), limit=6, cancel=lambda: False)
            path = ws.path("research/literature-evidence.json")
            write_json(path, evidence)
            _freeze(ws, record, "literature", path)
            for number, source in enumerate(evidence.get("sources", [])):
                for field, digest in (("raw_path", "sha256"), ("metadata_path", "metadata_sha256"), ("text_path", "text_sha256")):
                    if source.get(field):
                        original = safe_relative(ws.path("research"), source[field])
                        if digest_file(original) != source.get(digest):
                            raise WorkflowError("ARTIFACT_CHANGED", "Literature differs from its retrieval digest")
                        _freeze(ws, record, f"literature-{number}-{field}", original)
            self._save(ws, record)
            if evidence.get("cancelled") or not any(source.get("scope") in {"abstract", "full_text"} and source.get("excerpts")
                                                    for source in evidence.get("sources", [])):
                raise WorkflowError("LITERATURE_EVIDENCE_INSUFFICIENT", "Metadata alone cannot support Related Work; retrieval evidence is retained")
            return self._public(ws, record)

    def submit_code(self, research_id: str, value: dict, review: dict) -> dict:
        bundle = CodeBundle.model_validate(value)
        accepted = _accepted(review)
        with self._operation(research_id) as (ws, record):
            self._require(ws, record, {"planned", "code_ready"})
            plan = ResearchPlan.model_validate(_read(ws, record, "plan"))
            if bundle.runtime != plan.runtime:
                raise ValueError("Experiment runtime differs from frozen protocol")
            for item in bundle.files:
                path = safe_relative(ws.path("research/generated"), item.path)
                if item.path in {"bundle.json", "review.json"}:
                    raise ValueError("Experiment file collides with reserved controller metadata")
                if project._secret(path) or any(part.startswith(".") for part in Path(item.path).parts):
                    raise ValueError("Experiment code must use public declared paths")
                if path.suffix not in {".py", ".js", ".mjs", ".cjs", ".json", ".md", ".txt"}:
                    raise ValueError("Unsupported experiment file type")
                if path.suffix == ".py":
                    ast.parse(item.content, filename=item.path)
            record.code_attempt += 1
            root = ws.path(f"research/generated/attempt-{record.code_attempt}")
            while root.exists():
                record.code_attempt += 1
                root = ws.path(f"research/generated/attempt-{record.code_attempt}")
            root.mkdir(parents=True)
            files = []
            for index, item in enumerate(bundle.files):
                path = safe_relative(root, item.path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(item.content, encoding="utf-8")
                path.chmod(0o444)
                files.append({"path": item.path, "sha256": digest_file(path), "size": path.stat().st_size})
                _freeze(ws, record, f"code-{record.code_attempt}-{index}", path)
            metadata = {"runtime": bundle.runtime, "entrypoint": bundle.entrypoint, "files": files,
                        "source_digest": ws.latest("project", Project).snapshot_digest,
                        "protocol_sha256": record.artifacts["plan"].sha256, "explanation": bundle.explanation}
            write_json(root / "bundle.json", metadata)
            _freeze(ws, record, "bundle", root / "bundle.json")
            _freeze(ws, record, f"bundle-{record.code_attempt}", root / "bundle.json")
            write_json(root / "review.json", {"origin": "native_host_submission", "review": accepted.model_dump(mode="json"),
                       "bundle_sha256": record.artifacts["bundle"].sha256, "protocol_sha256": record.artifacts["plan"].sha256})
            _freeze(ws, record, f"code-review-{record.code_attempt}", root / "review.json")
            record.stage, record.status, record.code, record.message = "code_ready", "ready", None, None
            record.cancellation_requested = False
            self._save(ws, record)
            return self._public(ws, record)

    def start_experiment(self, research_id: str) -> dict:
        with self._operation(research_id) as (ws, record):
            self._require(ws, record, {"code_ready"})
            if not self.runner.status().get("ready"):
                raise WorkflowError("ISOLATION_UNAVAILABLE", "The isolated research worker is unavailable")
            lease = ws.lock("execution")
            lease.__enter__()
            record.status, record.stage = "running", "execute"
            record.cancellation_requested = False
            record.code, record.message = None, None
            record.execution_attempt += 1
            self._save(ws, record)
            try:
                self._jobs[research_id] = self._pool.submit(self._execute, research_id, lease)
            except Exception:
                lease.__exit__(None, None, None)
                record.status, record.stage = "failed", "code_ready"
                self._save(ws, record)
                raise
            return self._public(ws, record)

    def cancel(self, research_id: str) -> dict:
        with self._operation(research_id) as (ws, record):
            if record.status == "completed":
                return self._public(ws, record)
            record.cancellation_requested = True
            if record.status != "running" and not record.terminal_control_failure:
                record.status, record.code = "cancelled", "CANCELLED"
            self._save(ws, record)
            return self._public(ws, record)

    def _execute(self, research_id: str, lease) -> None:
        ws = self._workspace(research_id)

        def stopped():
            return self._closed or ws.get("workflow", research_id, Workflow).cancellation_requested

        def retain(handle):
            with self._mutex, ws.lock("workflow"):
                current = ws.get("workflow", research_id, Workflow)
                current.active_handle = dict(handle)
                self._save(ws, current)

        try:
            record = ws.get("workflow", research_id, Workflow)
            if stopped():
                raise WorkflowError("CANCELLED", "Experiment was cancelled before dispatch")
            _verify_artifacts(ws, record)
            plan = ResearchPlan.model_validate(_read(ws, record, "plan"))
            metadata = _read(ws, record, "bundle")
            output = ws.path(f"research/executions/attempt-{record.execution_attempt}")
            output.mkdir(parents=True, exist_ok=False)
            receipt = self.runner.run(ws.path("source"), _artifact(ws, record, "bundle").parent, output,
                                        runtime=metadata["runtime"], entrypoint=metadata["entrypoint"],
                                        production_entrypoint=plan.production_entrypoint,
                                        timeout_seconds=record.experiment_timeout_seconds, cancel=stopped, on_handle=retain)
            with self._mutex, ws.lock("workflow"):
                record = ws.get("workflow", research_id, Workflow)
                receipt.update(source_digest=metadata["source_digest"], protocol_sha256=metadata["protocol_sha256"],
                               bundle_sha256=record.artifacts["bundle"].sha256)
                write_json(output / "execution.json", receipt)
                _freeze(ws, record, "execution", output / "execution.json")
                _freeze(ws, record, f"execution-{record.execution_attempt}", output / "execution.json")
                observations = output / "observations.json"
                if observations.is_file():
                    _freeze(ws, record, "observations", observations)
                    _freeze(ws, record, f"observations-{record.execution_attempt}", observations)
                if (output / "runtime-manifest.json").is_file():
                    _freeze(ws, record, "runtime-manifest", output / "runtime-manifest.json")
                if receipt.get("cleanup_confirmed") is not True:
                    record.active_handle = receipt.get("active_handle") or record.active_handle
                    self._save(ws, record)
                    raise WorkflowError("CLEANUP_UNCONFIRMED", "Experiment worker cleanup could not be confirmed")
                record.active_handle = {}
                self._save(ws, record)
                # Failed controls override structural/exit errors, and retain raw evidence.
                if observations.is_file():
                    science.reject_failed_controls(_read(ws, record, "observations"))
                if receipt.get("status") != "succeeded":
                    code = "CANCELLED" if stopped() or receipt.get("status") == "cancelled" else "EXPERIMENT_FAILED"
                    raise WorkflowError(code, "Isolated experiment did not complete successfully: " +
                                        _diagnostic(receipt.get("error") or receipt.get("stderr")))
                _verify_artifacts(ws, record)
                self._analyze(ws, record)
                record.status, record.stage, record.code = "ready", "analyzed", None
                record.message = "Retained runner observations have been analyzed; a native host manuscript may be submitted."
                self._save(ws, record)
        except Exception as exc:
            with self._mutex, ws.lock("workflow"):
                record = ws.get("workflow", research_id, Workflow)
                code = getattr(exc, "code", "EXPERIMENT_INVALID")
                if isinstance(exc, science.ControlFailure):
                    record.terminal_control_failure = True
                    code = "CONTROL_FAILED"
                if record.active_handle and code != "CLEANUP_UNCONFIRMED":
                    try:
                        cleaned = self.runner.stop(record.active_handle)
                    except Exception:
                        cleaned = False
                    if cleaned:
                        record.active_handle = {}
                    else:
                        code = "CLEANUP_UNCONFIRMED"
                record.status = "cancelled" if code == "CANCELLED" else "blocked"
                record.stage, record.code, record.message = "code_ready", code, str(exc)[:1500]
                self._save(ws, record)
        finally:
            lease.__exit__(None, None, None)

    def _analyze(self, ws: Workspace, record: Workflow) -> None:
        """Finish retained successful evidence without dispatching another run."""
        _verify_artifacts(ws, record)
        plan = ResearchPlan.model_validate(_read(ws, record, "plan"))
        execution = _read(ws, record, "execution")
        if execution.get("status") != "succeeded" or not self._confirmed_cleanup(ws, record):
            raise WorkflowError("EXPERIMENT_FAILED", "Retained execution was not successful with confirmed cleanup")
        science.reject_failed_controls(_read(ws, record, "observations"))
        _production_execution(execution, plan)
        if "analysis" in record.artifacts:
            return
        analysis_root = ws.path(f"research/analysis/attempt-{record.execution_attempt}")
        if analysis_root.exists():
            # Keep uncheckpointed partial files from a hard interruption.
            analysis_root = ws.path(f"research/analysis/attempt-{record.execution_attempt}-{uid('recovery')}")
        analysis = science.analyze(_read(ws, record, "observations"), plan, analysis_root)
        analysis.update(raw_sha256=record.artifacts["observations"].sha256, protocol_sha256=record.artifacts["plan"].sha256)
        write_json(analysis_root / "analysis.json", analysis)
        _freeze(ws, record, "analysis", analysis_root / "analysis.json")
        for path in sorted(analysis_root.iterdir()):
            if path.is_file() and path.suffix in {".csv", ".png", ".py", ".md", ".json"}:
                _freeze(ws, record, "analysis-" + path.name, path)

    def _confirmed_cleanup(self, ws: Workspace, record: Workflow) -> bool:
        if "execution" not in record.artifacts:
            return False
        if _read(ws, record, "execution").get("cleanup_confirmed") is True:
            return True
        key = f"cleanup-{record.execution_attempt}"
        if key not in record.artifacts:
            return False
        cleanup = _read(ws, record, key)
        return cleanup.get("confirmed") is True and cleanup.get("execution_sha256") == record.artifacts["execution"].sha256

    def _record_cleanup(self, ws: Workspace, record: Workflow) -> None:
        if "execution" in record.artifacts:
            path = ws.path(f"research/executions/cleanup-{record.execution_attempt}.json")
            write_json(path, {"confirmed": True, "origin": "owned_worker_cleanup",
                             "execution_sha256": record.artifacts["execution"].sha256})
            _freeze(ws, record, f"cleanup-{record.execution_attempt}", path)

    def submit_manuscript(self, research_id: str, value: dict, review: dict) -> dict:
        draft = ManuscriptDraft.model_validate(value)
        accepted = _accepted(review)
        with self._operation(research_id) as (ws, record):
            self._require(ws, record, {"analyzed"})
            plan = ResearchPlan.model_validate(_read(ws, record, "plan"))
            record.draft_attempt += 1
            root = ws.path(f"research/drafts/attempt-{record.draft_attempt}")
            while root.exists():
                record.draft_attempt += 1
                root = ws.path(f"research/drafts/attempt-{record.draft_attempt}")
            write_json(root / "draft.json", draft)
            _freeze(ws, record, f"draft-{record.draft_attempt}", root / "draft.json")
            self._save(ws, record)
            rendered = science.validate_and_render(draft.model_dump(mode="json"), plan, _read(ws, record, "analysis"),
                                                  _read(ws, record, "literature"), root,
                                                  author=load_author().model_dump(exclude_defaults=True))
            markdown = Path(rendered["markdown_path"])
            _append_figures(ws, record, markdown)
            _freeze(ws, record, "manuscript", markdown)
            _freeze(ws, record, "canonical", Path(rendered["canonical_path"]))
            write_json(root / "review.json", {"origin": "native_host_submission", "review": accepted.model_dump(mode="json"),
                       "manuscript_sha256": record.artifacts["manuscript"].sha256, "protocol_sha256": record.artifacts["plan"].sha256,
                       "analysis_sha256": record.artifacts["analysis"].sha256, "literature_sha256": record.artifacts["literature"].sha256})
            _freeze(ws, record, "manuscript-review", root / "review.json")
            record.stage = "manuscript"
            self._save(ws, record)
            return self._public(ws, record)

    def export(self, research_id: str) -> dict:
        with self._operation(research_id) as (ws, record):
            self._require(ws, record, {"manuscript", "exported"})
            if record.stage == "exported":
                self._verify(ws, record)
                return self._public(ws, record)
            root = ws.path("research/exports")
            root.mkdir(parents=True, exist_ok=True)
            markdown = root / "paper.md"
            shutil.copyfile(_artifact(ws, record, "manuscript"), markdown)
            _freeze(ws, record, "export-md", markdown)
            for key in list(record.artifacts):
                if key.startswith("analysis-"):
                    source = _artifact(ws, record, key)
                    destination = root / source.name
                    shutil.copyfile(source, destination)
                    if source.suffix == ".png":
                        _freeze(ws, record, "export-" + source.stem, destination)
            receipts, outputs = {}, {}
            for format in ("pdf", "docx", "tex"):
                output = root / ("paper." + format)
                receipts[format] = conversion.convert(markdown, output, pandoc=os.environ.get("PYPANDOC_PANDOC") or None,
                                                       metadata={"mainfont": "Libertinus Serif"} if format == "pdf" else None)
                _freeze(ws, record, "export-" + format, output)
                outputs[format] = output
            write_json(root / "conversion-receipts.json", receipts)
            _freeze(ws, record, "conversion", root / "conversion-receipts.json")
            if errors := conversion.verify_receipts(markdown, outputs, root / "conversion-receipts.json"):
                raise ValueError("; ".join(errors))
            self._bundle(ws, record, root)
            validation = self._verify(ws, record)
            write_json(root / "validation.json", validation)
            _freeze(ws, record, "validation", root / "validation.json")
            record.status, record.stage = "completed", "exported"
            record.message = "Evidence-linked manuscript and reproduction package are ready for author review; not submitted."
            self._save(ws, record)
            return self._public(ws, record)

    def _bundle(self, ws: Workspace, record: Workflow, root: Path) -> None:
        selection = {name: _artifact(ws, record, key) for name, key in {
            "protocol.json": "plan", "observations.json": "observations", "execution.json": "execution",
            "analysis.json": "analysis", "literature-evidence.json": "literature", "canonical.json": "canonical",
            "paper.md": "export-md", "paper.pdf": "export-pdf", "paper.docx": "export-docx", "paper.tex": "export-tex",
            "conversion-receipts.json": "conversion", "manuscript-review.json": "manuscript-review"}.items()}
        if "runtime-manifest" in record.artifacts:
            selection["runtime-manifest.json"] = _artifact(ws, record, "runtime-manifest")
        for key in record.artifacts:
            if key.startswith("export-figure-"):
                path = _artifact(ws, record, key)
                selection[path.name] = path
        cleanup_key = f"cleanup-{record.execution_attempt}"
        if cleanup_key in record.artifacts:
            selection["cleanup.json"] = _artifact(ws, record, cleanup_key)
        bundle = _artifact(ws, record, "bundle").parent
        for path in bundle.rglob("*"):
            if path.is_file():
                selection["generated/" + path.relative_to(bundle).as_posix()] = path
        for key in record.artifacts:
            if key.startswith("analysis-"):
                selection["analysis/" + _artifact(ws, record, key).name] = _artifact(ws, record, key)
            if key.startswith("literature-"):
                path = _artifact(ws, record, key)
                selection["literature/" + path.relative_to(ws.path("research/literature")).as_posix()] = path
        imported = ws.latest("project", Project)
        for asset in imported.assets:
            selection["source/" + asset.path] = safe_relative(ws.path("source"), asset.path)
        provenance = root / "source-provenance.json"
        write_json(provenance, {"repository": imported.source, "commit": imported.source_commit,
                   "snapshot_digest": imported.snapshot_digest, "license_assessment": "not_performed",
                   "license_notice_files": [asset.path for asset in imported.assets
                       if re.search(r"(?:^|/)(?:LICENSE|LICENCE|COPYING|NOTICE)(?:[._-]|$)", asset.path, re.I)],
                   "attribution": "Source provenance does not establish manuscript authorship or redistribution permission."})
        _freeze(ws, record, "source-provenance", provenance)
        selection["source-provenance.json"] = provenance
        if sum(path.stat().st_size for path in selection.values()) > MAX_BUNDLE_BYTES:
            raise WorkflowError("REPRODUCTION_BUNDLE_TOO_LARGE", "Reproduction archive inputs exceed 96 MiB")
        archive = root / "reproducibility.zip"
        runtime = ResearchPlan.model_validate(_read(ws, record, "plan")).runtime
        runtime_instructions = (
            "Use the installed Cloud plugin's verified private interpreter and extracted runtime.\n"
            "Select --runtime-root with scripts/run_workflow.py and require environment ready before creating a study.\n"
            "QuickJS runs frozen source and generated code in separate guests using callProduction and retainFixture.\n"
            "TypeScript is erased by the recorded trusted transformer; inspect original and compiled hashes in runtime-manifest.json.\n"
            if runtime == "quickjs" else
            "Provision the vetted platform runtime before running generated code through its isolated runner.\n"
            "The native runner supplies PF_SOURCE_ROOT, PF_CODE_ROOT, PF_OUTPUT_ROOT and PF_WORK.\n"
        )
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
            output.writestr("README.md", "# Reproduce this controlled software study\n\n"
                "Frozen source, protocol, experiment, observations, analysis and native exports are retained.\n"
                "execution.json records actual isolation, resource limits, production calls and cleanup.\n"
                "runtime-manifest.json, when present, records source and runtime provenance.\n" + runtime_instructions +
                "Recompute results with analysis/analysis.py and its documented arguments.\n"
                "Reviews are native host submissions; reviewer independence is not attested by this controller.\n"
                "Source license authorization has not been assessed. Author review is required; no submission occurred.\n")
            output.writestr("inventory.json", json.dumps({name: {"sha256": digest_file(path), "size": path.stat().st_size}
                                                          for name, path in selection.items()}, indent=2))
            for name, path in sorted(selection.items()):
                ensure_unlinked(path)
                output.write(path, name)
        _freeze(ws, record, "reproducibility", archive)

    def _verify(self, ws: Workspace, record: Workflow) -> dict:
        from docx import Document
        from pypdf import PdfReader

        _verify_artifacts(ws, record)
        plan = ResearchPlan.model_validate(_read(ws, record, "plan"))
        _production_execution(_read(ws, record, "execution"), plan)
        if not self._confirmed_cleanup(ws, record):
            raise WorkflowError("CLEANUP_UNCONFIRMED", "Export requires confirmed experiment cleanup")
        analysis = _read(ws, record, "analysis")
        with tempfile.TemporaryDirectory(prefix="paperfactory-recompute-") as directory:
            computed = science.analyze(_read(ws, record, "observations"), plan, Path(directory))
        for key in ("results", "parameters", "controls", "protocol_digest", "observation_digest", "summaries", "paired_deltas"):
            if computed.get(key) != analysis.get(key):
                raise ValueError("Analysis differs from raw observation recomputation: " + key)
        canonical = _read(ws, record, "canonical")
        with tempfile.TemporaryDirectory(prefix="paperfactory-manuscript-") as directory:
            rendered = science.validate_and_render({"title": canonical["title"], "sections": canonical["sections"]}, plan, analysis,
                _read(ws, record, "literature"), Path(directory), author=canonical.get("author"))
            _append_figures(ws, record, Path(rendered["markdown_path"]))
            if digest_file(Path(rendered["markdown_path"])) != record.artifacts["manuscript"].sha256:
                raise ValueError("Manuscript differs from independent evidence rendering")
        if digest_file(_artifact(ws, record, "export-md")) != record.artifacts["manuscript"].sha256:
            raise ValueError("Export source differs from verified manuscript")
        pdf = PdfReader(_artifact(ws, record, "export-pdf"))
        if pdf.is_encrypted or not pdf.pages or not any(page.extract_text() for page in pdf.pages):
            raise ValueError("Native PDF cannot be independently read")
        word = Document(_artifact(ws, record, "export-docx"))
        if len(" ".join(paragraph.text for paragraph in word.paragraphs).split()) < 1000:
            raise ValueError("Native Word manuscript is incomplete")
        tex = _artifact(ws, record, "export-tex").read_text(encoding="utf-8")
        if "\\begin{document}" not in tex or "\\end{document}" not in tex:
            raise ValueError("Standalone LaTeX export is incomplete")
        if errors := conversion.verify_receipts(_artifact(ws, record, "export-md"),
                {format: _artifact(ws, record, "export-" + format) for format in ("pdf", "docx", "tex")},
                _artifact(ws, record, "conversion")):
            raise ValueError("; ".join(errors))
        with zipfile.ZipFile(_artifact(ws, record, "reproducibility")) as archive:
            if archive.testzip():
                raise ValueError("Reproduction archive has a CRC error")
            for name, item in loads_json(archive.read("inventory.json")).items():
                data = archive.read(name)
                if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                    raise ValueError("Reproduction archive member differs from its inventory")
        return {"passed": True, "research_id": record.id, "results": len(analysis["results"]),
                "pages": len(pdf.pages), "publication": "author review required; not submitted"}

    def _recover(self) -> None:
        for path in self.root.iterdir():
            if not path.is_dir() or not re.fullmatch(r"research-[a-f0-9]{12}", path.name):
                continue
            if not (path / "records.sqlite3").is_file():
                continue
            ws = Workspace(path)
            records = ws.list("workflow", Workflow)
            if not records:
                # Interrupted imports cannot own an experiment: dispatch starts
                # only after its workflow record has been committed.
                continue
            record = ws.get("workflow", path.name, Workflow)
            if record.code == "CLEANUP_UNCONFIRMED" and not record.active_handle:
                self._recovered.add(record.id)
            if record.status != "running" and not record.active_handle:
                continue
            try:
                with ws.lock("execution"), ws.lock("workflow"):
                    record = ws.get("workflow", path.name, Workflow)
                    self._recovered.add(record.id)
                    cleaned = not record.active_handle
                    if record.active_handle:
                        try:
                            cleaned = self.runner.stop(record.active_handle)
                        except Exception:
                            cleaned = False
                    if cleaned:
                        if record.active_handle:
                            self._record_cleanup(ws, record)
                        record.active_handle = {}
                    record.status, record.stage = "blocked", "code_ready"
                    record.code = "INTERRUPTED" if cleaned else "CLEANUP_UNCONFIRMED"
                    record.message = "Interrupted experiment reconciled; retained evidence is preserved."
                    if cleaned and "observations" in record.artifacts:
                        try:
                            science.reject_failed_controls(_read(ws, record, "observations"))
                            if "execution" in record.artifacts and _read(ws, record, "execution").get("status") == "succeeded":
                                self._analyze(ws, record)
                                record.status, record.stage, record.code = "ready", "analyzed", None
                        except science.ControlFailure:
                            record.terminal_control_failure, record.code = True, "CONTROL_FAILED"
                        except ValueError as exc:
                            record.code, record.message = getattr(exc, "code", "EXPERIMENT_INVALID"), str(exc)[:1500]
                    self._save(ws, record)
            except ValueError as exc:
                if "Another operation is already running" not in str(exc):
                    raise

    def close(self) -> None:
        with self._mutex:
            jobs = dict(self._jobs)
            owned_ids = set(jobs) | self._recovered
            for research_id, future in jobs.items():
                if not future.done():
                    ws = self._workspace(research_id)
                    with ws.lock("workflow"):
                        record = ws.get("workflow", research_id, Workflow)
                        record.cancellation_requested = True
                        self._save(ws, record)
            self._closed = True
        _, pending = wait(jobs.values(), timeout=10) if jobs else (set(), set())
        if pending:
            for research_id, future in jobs.items():
                if future in pending:
                    ws = self._workspace(research_id)
                    record = ws.get("workflow", research_id, Workflow)
                    if record.active_handle:
                        try:
                            self.runner.stop(record.active_handle)
                        except Exception:
                            pass
            _, pending = wait(pending, timeout=10)
        self._pool.shutdown(wait=not pending, cancel_futures=False)
        if pending:
            raise WorkflowError("CLEANUP_UNCONFIRMED", "Owned experiment jobs did not finish cleanup before shutdown")
        for research_id in owned_ids:
            ws = self._workspace(research_id)
            with self._mutex, ws.lock("workflow"):
                record = ws.get("workflow", research_id, Workflow)
                if record.active_handle:
                    try:
                        cleaned = self.runner.stop(record.active_handle)
                    except Exception:
                        cleaned = False
                    if cleaned:
                        self._record_cleanup(ws, record)
                        record.active_handle = {}
                        record.code = "INTERRUPTED"
                        try:
                            if "observations" in record.artifacts:
                                science.reject_failed_controls(_read(ws, record, "observations"))
                            if "execution" in record.artifacts and _read(ws, record, "execution").get("status") == "succeeded":
                                self._analyze(ws, record)
                                record.status, record.stage, record.code = "ready", "analyzed", None
                        except science.ControlFailure:
                            record.terminal_control_failure, record.code = True, "CONTROL_FAILED"
                        except ValueError as exc:
                            record.code, record.message = getattr(exc, "code", "EXPERIMENT_INVALID"), str(exc)[:1500]
                        self._save(ws, record)
                if record.active_handle or record.code == "CLEANUP_UNCONFIRMED":
                    raise WorkflowError("CLEANUP_UNCONFIRMED", "Owned experiment cleanup remains unconfirmed")

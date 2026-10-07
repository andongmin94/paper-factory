"""Local research controller: the host writes proposals; tools verify evidence.

No model provider, account state, unrestricted execution or model-supplied
measurements are part of this service. The standalone IPC adapter uses this API.
"""

import base64
import binascii
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
import time
import zipfile

from . import conversion, project
from .author import load_author
from .autonomous import literature, science
from .autonomous.models import CodeBundle, FrozenArtifact, ManuscriptDraft, ManuscriptReview, ResearchPlan, ScientificReview, StudyReview
from .models import Project, now, uid
from .workflow_models import ModelEvidenceReceipt, Workflow
from .workspace import Workspace, digest_file, ensure_unlinked, loads_json, safe_relative, write_json

MAX_BUNDLE_BYTES = 96 * 1024 * 1024
MAX_SUPPORTING_FILES = 8
MAX_SUPPORTING_FILE_BYTES = 128 * 1024
MAX_SUPPORTING_BYTES = 256 * 1024
CANCEL_CLEANUP_SECONDS = 30
CANCEL_STOP_SECONDS = 10  # Owned job stop and process wait each allow five seconds.
SHUTDOWN_CLEANUP_SECONDS = 30
SCHEMAS = {"plan": ResearchPlan.model_json_schema(), "study_review": StudyReview.model_json_schema(),
           "code": CodeBundle.model_json_schema(), "review": ScientificReview.model_json_schema(),
           "manuscript": ManuscriptDraft.model_json_schema(), "manuscript_review": ManuscriptReview.model_json_schema()}
READABLE_EVIDENCE = {"proposal", "plan", "study-review", "selected-literature", "observations", "analysis",
                     "literature", "manuscript", "canonical", "runtime-manifest"}


def _readable_evidence(key: str) -> bool:
    return key in READABLE_EVIDENCE or re.fullmatch(
        r"(?:(?:code|manuscript)-review-[1-9][0-9]*|supporting-document-(?:import-)?[a-f0-9]{12}|authoring-revision-[a-f0-9]{12})", key) is not None


class WorkflowError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _accepted(value: dict, model=ScientificReview) -> ScientificReview:
    review = model.model_validate(value)
    if not review.accepted or review.issues:
        raise WorkflowError("REVIEW_REJECTED", "; ".join(review.issues) or "Native host review did not accept this submission")
    return review


def _attempted_literature_queries(evidence: dict) -> set[str]:
    return {search.get("query") for search in evidence.get("searches", [])
            if search.get("status") in {"succeeded", "failed"} and search.get("attempted") is not False}


def _require_complete_literature(plan: ResearchPlan, evidence: dict) -> None:
    if evidence.get("cancelled"):
        raise WorkflowError("LITERATURE_EVIDENCE_INSUFFICIENT", "Complete the cancelled literature collection before study approval")
    queries = {query.strip() for query in plan.literature_queries}
    if queries - _attempted_literature_queries(evidence):
        raise WorkflowError("LITERATURE_QUERIES_INCOMPLETE", "Some proposed literature queries were not attempted; study approval requires complete retrieval attempts")


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


def _supporting_name(root: Path, name: object) -> str:
    if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}\.(?:md|txt|json)", name, re.I | re.ASCII) is None:
        raise ValueError("Supporting documents require a safe basename ending in .md, .txt or .json")
    safe_relative(root, name)
    return name


def _supporting_documents(ws: Workspace, record: Workflow) -> list[dict]:
    """Derive names only from immutable import receipts bound to document bytes."""
    documents = {}
    for key in sorted(record.artifacts):
        if re.fullmatch(r"supporting-document-import-[a-f0-9]{12}", key) is None:
            continue
        receipt = _read(ws, record, key)
        if (not isinstance(receipt, dict) or receipt.get("id") != key or
                receipt.get("event") != "supporting-document-import" or
                receipt.get("scope") != "external-untrusted-content" or not isinstance(receipt.get("documents"), list)):
            raise WorkflowError("ARTIFACT_CHANGED", "Supporting document import metadata changed")
        for row in receipt["documents"]:
            if (not isinstance(row, dict) or set(row) != {"id", "originalName", "sha256", "size"} or
                    not isinstance(row["id"], str) or re.fullmatch(r"supporting-document-[a-f0-9]{12}", row["id"]) is None or
                    row["id"] in documents):
                raise WorkflowError("ARTIFACT_CHANGED", "Supporting document import inventory changed")
            name = _supporting_name(ws.root, row["originalName"])
            artifact = record.artifacts.get(row["id"])
            if (artifact is None or row["sha256"] != artifact.sha256 or type(row["size"]) is not int or row["size"] != artifact.size or
                    artifact.path != "research/supporting-documents/" + row["id"] + "/" + name):
                raise WorkflowError("ARTIFACT_CHANGED", "Supporting document metadata does not bind retained bytes")
            _artifact(ws, record, row["id"])
            documents[row["id"]] = {"id": row["id"], "name": name, "sha256": artifact.sha256, "size": artifact.size}
    declared = {key for key in record.artifacts if re.fullmatch(r"supporting-document-[a-f0-9]{12}", key)}
    if declared != set(documents):
        raise WorkflowError("ARTIFACT_CHANGED", "Supporting documents require matching immutable import receipts")
    return [documents[key] for key in sorted(documents)]


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

    def __init__(self, home: Path, *, runner, collector=None):
        if runner is None:
            raise ValueError("An explicit QuickJS runner is required")
        self.home = Path(home).expanduser().absolute()
        ensure_unlinked(self.home)
        self.root = self.home / "workflows"
        self.root.mkdir(parents=True, exist_ok=True)
        self.runner = runner
        self.collector = collector or literature.collect
        self._mutex = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="paperfactory-experiment")
        self._jobs = {}
        self._recovered = set()
        self._closing = False
        self._closed = False
        try:
            self._recover()
        except Exception:
            self._pool.shutdown(wait=True)
            raise

    def _workspace(self, research_id: str) -> Workspace:
        if not re.fullmatch(r"research-[a-f0-9]{12}", research_id):
            raise ValueError("Unknown research identifier")
        ws = Workspace(safe_relative(self.root, research_id))
        if ws.get("workflow", research_id, Workflow).id != research_id:
            raise ValueError("Research identifier differs from its workspace")
        return ws

    @contextmanager
    def _operation(self, research_id: str, *, during_shutdown: bool = False):
        with self._mutex:
            if self._closed and not during_shutdown:
                raise ValueError("Research service is closed")
            if self._closing and not during_shutdown:
                raise WorkflowError("ENGINE_CLOSING", "Research shutdown is pending; new operations are unavailable")
            ws = self._workspace(research_id)
            with ws.lock("workflow"):
                yield ws, ws.get("workflow", research_id, Workflow)

    def _save(self, ws: Workspace, record: Workflow) -> None:
        record.updated_at = now()
        ws.save("workflow", record)

    def _public(self, ws: Workspace, record: Workflow, *, context: bool = False, include_materials: bool = True) -> dict:
        data = record.model_dump(mode="json", exclude={"active_handle"})
        future = self._jobs.get(record.id)
        data["cleanup_pending"] = bool(record.status == "running" or record.active_handle or
                                       record.code == "CLEANUP_UNCONFIRMED" or
                                       (future is not None and not future.done()))
        data["resume_kind"] = self._resume_kind(record)
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
        data["supporting_documents"] = _supporting_documents(ws, record)
        data["study_review"] = _read(ws, record, "study-review")["review"] if "study-review" in record.artifacts else None
        manuscript_review = _read(ws, record, "manuscript-review")["review"] if "manuscript-review" in record.artifacts else None
        data["manuscript_review"] = (ManuscriptReview.model_validate(manuscript_review).model_dump(mode="json")
            if manuscript_review and all(name in manuscript_review for name in
                ("contribution", "literature", "interpretation", "presentation")) else None)
        if record.code == "STUDY_REJECTED" and data["study_review"]:
            data["message"] = "연구 적합성 검토에서 보완이 필요합니다. " + _diagnostic("; ".join(data["study_review"]["issues"]))
        if record.code == "MANUSCRIPT_REJECTED" and data["manuscript_review"]:
            data["message"] = "원고 품질 검토에서 보완이 필요합니다. " + _diagnostic("; ".join(data["manuscript_review"]["issues"]))
        if not include_materials:
            return data
        data["material_manifest"] = {
            "source": [{"name": asset.path, "sha256": asset.sha256, "size": asset.size}
                       for asset in ws.latest("project", Project).assets],
            "experiment": [{"name": item["path"], "sha256": item["sha256"], "size": item["size"]}
                           for item in _read(ws, record, "bundle")["files"]] if "bundle" in record.artifacts else [],
            "evidence": [{"name": key, "sha256": record.artifacts[key].sha256, "size": record.artifacts[key].size}
                         for key in sorted(record.artifacts) if _readable_evidence(key)],
        }
        data["schemas"] = SCHEMAS
        data["review_provenance"] = "Reviews are native host submissions; the controller does not attest reviewer independence."
        if context:
            data["source_context"] = _artifact(ws, record, "context").read_text(encoding="utf-8")
        for key in ("proposal", "plan", "literature", "analysis", "execution"):
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
        if "selected-literature" in record.artifacts:
            data["literature"] = _read(ws, record, "selected-literature")
        source_context = _artifact(ws, record, "context").read_text(encoding="utf-8")
        if record.code == "CLEANUP_UNCONFIRMED":
            data["instructions"] = "Owned worker cleanup is unconfirmed. Do not submit code or start another experiment. Restore the bundled runtime and restart the app so owned cleanup can be reconciled."
        elif record.terminal_control_failure:
            data["instructions"] = "The scientific control failed. Preserve the negative result; do not regenerate or rerun this study to obtain favorable observations."
        elif record.status == "running":
            data["instructions"] = "The owned experiment runs in the background. Read research status until it finishes, or cancel it. Do not start another execution."
        elif record.execution_attempt > 0 and record.stage in {"planned", "code_ready"}:
            data["instructions"] = "A scientific execution was already dispatched. Preserve its retained diagnostics and evidence; do not replace its code or rerun this study."
        elif record.stage == "created":
            data["instructions"] = science.planning_prompt(source_context, record.goal)
        elif record.stage == "proposed":
            data["planning_instructions"] = science.planning_prompt(source_context, record.goal)
            data["instructions"] = (science.study_review_prompt(ResearchPlan.model_validate(data["proposal"]),
                                        data["literature"], source_context) if "literature" in data else
                                    "Collect the proposal's literature before assessing its research suitability. No protocol is frozen yet.")
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
                data["instructions"] += "\nHave a fresh native host reviewer assess contribution, literature relevance, interpretation and presentation as ManuscriptReview. Reject a trivial contract test framed as an empirical paper even when numerical integrity passes."
        elif record.stage == "manuscript":
            data["instructions"] = "Export the validated manuscript to Markdown, PDF, DOCX, standalone TeX and a reproduction archive. Export recomputes raw results and independently reopens the native documents."
        else:
            data["instructions"] = "Verified artifacts are ready for the author's scientific review. Download server-owned artifact IDs; no journal submission or publication approval has occurred."
        return data

    def _resume_kind(self, record: Workflow) -> str | None:
        future = self._jobs.get(record.id)
        if (self._closing or self._closed or record.status not in {"ready", "cancelled"} or
                record.active_handle or record.code == "CLEANUP_UNCONFIRMED" or record.terminal_control_failure or
                (future is not None and not future.done())):
            return None
        if record.stage == "proposed" and "study-review" in record.artifacts:
            return None
        if record.execution_attempt == 0 and record.stage in {"created", "proposed", "planned", "code_ready"}:
            if future is not None or any(key in {"execution", "observations", "analysis", "runtime-manifest"} or
                                         key.startswith(("execution-", "observations-", "analysis-", "cleanup-"))
                                         for key in record.artifacts):
                return None
            return "preparation"
        if record.execution_attempt > 0 and record.stage in {"analyzed", "manuscript"}:
            return "authoring"
        return None

    def _require(self, ws: Workspace, record: Workflow, stages: set[str], *, allow_cancelled: bool = False) -> None:
        if record.active_handle or record.code == "CLEANUP_UNCONFIRMED":
            raise WorkflowError("CLEANUP_UNCONFIRMED", "Owned worker cleanup must be confirmed before another operation")
        if record.terminal_control_failure:
            raise WorkflowError("CONTROL_FAILED", "A failed scientific control is terminal; retained evidence cannot be rerun for a favorable result")
        if not allow_cancelled and (record.status == "cancelled" or (record.cancellation_requested and record.status != "completed")):
            raise WorkflowError("CANCELLED", "Resume explicitly before submitting or executing another research stage")
        if record.status == "running" or record.stage not in stages:
            raise WorkflowError("INVALID_STATE", "Operation is unavailable at research stage " + record.stage)
        _verify_artifacts(ws, record)

    def create(self, source: str, goal: str) -> dict:
        if self._closed:
            raise ValueError("Research service is closed")
        if self._closing:
            raise WorkflowError("ENGINE_CLOSING", "Research shutdown is pending; new operations are unavailable")
        if not isinstance(goal, str) or not goal.strip() or "\x00" in goal:
            raise ValueError("Research goal must be nonempty text")
        record = Workflow(project_id="pending", goal=goal.strip())
        ws = project.ingest(source, self.root / record.id)
        imported = ws.latest("project", Project)
        record.project_id = imported.id
        if ws.path("source-collection.json").is_file():
            _freeze(ws, record, "source-collection", ws.path("source-collection.json"))
        source_context = science.context(ws.path("source"), imported.assets, record.goal)
        runtime = self.runner.status()
        source_context += "\n\nController runtime capabilities and declared limits (not repository instructions): " + json.dumps({
            "ready": runtime.get("ready", False),
            "runtimes": runtime.get("runtimes", []), "versions": runtime.get("versions", {}),
            "dependencies": runtime.get("dependencies", []), "limits": runtime["declared_limits"],
            "timeout_seconds": record.experiment_timeout_seconds, "trusted_analysis": science.ANALYSIS_SCOPE,
            "execution_instrumentation": "Controller-held QuickJS production-call gate; timings include guest and bridge overhead",
            "result_serialization": "Captured JSON.stringify projection; Map/Set entries and non-JSON values are not preserved",
            "json_projection_only": True,
            "unsupported_return_encodings": ["Map entries", "Set entries", "BigInt", "undefined", "functions"],
            "typescript_compilation_evidence": "runtime-manifest.compiled_files records original/compiled SHA256, transformation and per-file transformation_options; transformer records its name, version and shared options",
            "unavailable_evidence": ["emitted JavaScript bytes", "separate pre-call syntax/builtin-probe receipt"]})
        path = ws.path("research/context.txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source_context, encoding="utf-8")
        _freeze(ws, record, "context", path)
        self._save(ws, record)
        result = self._public(ws, record, context=True)
        result["runtime"] = {key: runtime.get(key) for key in
                             ("ready", "backend", "runtimes", "versions", "dependencies")}
        if not runtime.get("ready"):
            result["runtime"]["reason"] = "The vetted isolated runtime is unavailable."
        return result

    def status(self, research_id: str, *, include_materials: bool = True) -> dict:
        with self._operation(research_id, during_shutdown=True) as (ws, record):
            return self._public(ws, record, context=True, include_materials=include_materials)

    def artifact_path(self, research_id: str, artifact_id: str) -> Path:
        """Resolve a server-owned artifact ID; adapters never accept file paths."""
        with self._operation(research_id, during_shutdown=True) as (ws, record):
            return _artifact(ws, record, artifact_id)

    def resolve_artifact(self, research_id: str, artifact_id: str) -> dict:
        """Bind saved manuscript bytes to the frozen figures they reference."""
        with self._operation(research_id, during_shutdown=True) as (ws, record):
            path = _artifact(ws, record, artifact_id)
            frozen = record.artifacts[artifact_id]
            companions, names = [], set()
            if artifact_id in {"export-md", "export-tex"}:
                for key in sorted(record.artifacts):
                    if not key.startswith("export-figure-"):
                        continue
                    figure = _artifact(ws, record, key)
                    if (re.fullmatch(r"figure-[0-9]+\.png", figure.name, re.ASCII) is None or
                            key != "export-" + figure.stem or figure.parent != path.parent or figure.name.casefold() in names):
                        raise WorkflowError("ARTIFACT_CHANGED", "Export figures require unique safe names in the manuscript directory")
                    names.add(figure.name.casefold())
                    item = record.artifacts[key]
                    companions.append({"name": figure.name, "path": str(figure), "sha256": item.sha256, "size": item.size})
                markdown = _artifact(ws, record, "export-md")
                references = set(re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown.read_text(encoding="utf-8")))
                if markdown.parent != path.parent or references != names:
                    raise WorkflowError("ARTIFACT_CHANGED", "Markdown figure references differ from the frozen export inventory")
                if artifact_id == "export-tex":
                    references = set(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}", path.read_text(encoding="utf-8")))
                    if references != names:
                        raise WorkflowError("ARTIFACT_CHANGED", "TeX figure references differ from the frozen export inventory")
            return {"path": str(path), "sha256": frozen.sha256, "size": frozen.size, "companions": companions}

    def add_evidence(self, research_id: str, files: list[dict]) -> dict:
        """Append bounded untrusted UTF-8 documents; never infer or dispatch."""
        if not isinstance(files, list) or not 1 <= len(files) <= MAX_SUPPORTING_FILES:
            raise ValueError("Import between one and eight supporting documents")
        decoded, names = [], set()
        for item in files:
            if not isinstance(item, dict) or set(item) != {"name", "contentBase64"}:
                raise ValueError("Supporting documents require name and contentBase64 only")
            name = _supporting_name(self.root, item["name"])
            if name.casefold() in names:
                raise ValueError("Supporting document names must be distinct ignoring case")
            names.add(name.casefold())
            encoded = item["contentBase64"]
            if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_SUPPORTING_FILE_BYTES + 2) // 3):
                raise ValueError("Supporting document content exceeds its encoded byte limit")
            try:
                content = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError):
                raise ValueError("Supporting document content must be strict base64") from None
            if base64.b64encode(content).decode("ascii") != encoded:
                raise ValueError("Supporting document content must be canonical base64")
            if not 1 <= len(content) <= MAX_SUPPORTING_FILE_BYTES:
                raise ValueError("Supporting documents must be nonempty and at most 128 KiB")
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                raise ValueError("Supporting documents must contain UTF-8 text") from None
            if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", text):
                raise ValueError("Supporting documents may contain only readable UTF-8 text controls")
            decoded.append((name, content))
        if sum(len(content) for _, content in decoded) > MAX_SUPPORTING_BYTES:
            raise ValueError("Supporting document import exceeds 256 KiB")
        with self._operation(research_id) as (ws, record):
            if record.status not in {"ready", "cancelled"}:
                raise WorkflowError("INVALID_STATE", "Supporting documents cannot be imported into this research status")
            self._require(ws, record, {"created", "proposed", "planned", "analyzed"}, allow_cancelled=True)
            if record.stage == "analyzed":
                self._require_successful_analysis(ws, record)
            existing = _supporting_documents(ws, record)
            if (len(existing) + len(decoded) > MAX_SUPPORTING_FILES or
                    sum(row["size"] for row in existing) + sum(len(content) for _, content in decoded) > MAX_SUPPORTING_BYTES):
                raise ValueError("Retained supporting documents exceed eight files or 256 KiB")
            if names & {row["name"].casefold() for row in existing}:
                raise ValueError("Supporting document names already exist in this research")
            receipt_id = uid("supporting-document-import")
            receipt_path = ws.path("research/supporting-documents/" + receipt_id + ".json")
            paths, rows, identifiers = [], [], set(record.artifacts)
            identifiers.add(receipt_id)
            for name, content in decoded:
                identifier = uid("supporting-document")
                if identifier in identifiers:
                    raise WorkflowError("EVIDENCE_IMPORT_CONFLICT", "Supporting evidence identifiers must not replace retained artifacts")
                identifiers.add(identifier)
                path = ws.path("research/supporting-documents/" + identifier + "/" + name)
                paths.append((identifier, path, content))
                rows.append({"id": identifier, "originalName": name, "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)})
            receipt = {"event": "supporting-document-import", "id": receipt_id, "importedAt": now(),
                       "scope": "external-untrusted-content",
                       "provenance": "User-supplied supporting documents; embedded sources and timestamps are unverified claims. importedAt records current app import, not pre-experiment inspection.",
                       "stageAtImport": record.stage, "statusAtImport": record.status,
                       "executionAttempt": record.execution_attempt, "documents": rows}
            paths.append((receipt_id, receipt_path, (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8")))
            if receipt_id in record.artifacts or any(path.exists() for _, path, _ in paths):
                raise WorkflowError("EVIDENCE_IMPORT_CONFLICT", "Supporting evidence cannot overwrite retained bytes")
            for identifier, path, content in paths:
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with path.open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                _freeze(ws, record, identifier, path)
            self._save(ws, record)
            return self._public(ws, record)


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
                if not _readable_evidence(name):
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

    def submit_proposal(self, research_id: str, value: dict) -> dict:
        plan = ResearchPlan.model_validate(value)
        with self._operation(research_id) as (ws, record):
            self._require(ws, record, {"created", "proposed"})
            if record.execution_attempt or record.proposal_attempt >= 3:
                raise WorkflowError("PROPOSAL_LIMIT", "Research proposals are limited to three before any execution")
            if record.stage == "proposed" and record.code != "STUDY_REJECTED":
                raise WorkflowError("INVALID_STATE", "Assess the retained proposal before replacing it")
            science.validate_plan(plan, ws.path("source"))
            if any(not safe_relative(ws.path("source"), path).is_file() for path in plan.source_files):
                raise WorkflowError("PLAN_SOURCE_MISSING", "Protocol refers to absent source files")
            runtime = self.runner.status()
            if not runtime.get("ready") or plan.runtime not in runtime.get("runtimes", []):
                raise WorkflowError("ISOLATION_UNAVAILABLE", "The required isolated runtime is unavailable")
            missing = set(plan.dependencies) - set(runtime.get("dependencies", []))
            if missing:
                raise WorkflowError("RUNTIME_DEPENDENCY_UNAVAILABLE", "Unprovisioned dependencies: " + ", ".join(sorted(missing)))
            plan.parameters["execution_instrumentation"] = "Controller-held QuickJS production-call gate; timings include guest and bridge overhead"
            limitation = "Production-call instrumentation affects execution overhead; measurements cannot establish uninstrumented production performance."
            if not any(limitation in text for text in plan.limitations):
                if len(plan.limitations) == 12:
                    plan.limitations[-1] += " " + limitation
                else:
                    plan.limitations.append(limitation)
            if "proposal" in record.artifacts and _read(ws, record, "proposal") == plan.model_dump(mode="json"):
                raise WorkflowError("PROPOSAL_UNCHANGED", "A rejected proposal must be substantively revised before a new review")
            if "literature" in record.artifacts:
                previous = record.artifacts.pop("literature")
                record.artifacts["literature-history-" + previous.sha256] = previous
            record.artifacts.pop("study-review", None)
            record.proposal_attempt += 1
            path = ws.path(f"research/proposals/attempt-{record.proposal_attempt}/proposal.json")
            write_json(path, plan)
            _freeze(ws, record, "proposal", path)
            _freeze(ws, record, f"proposal-{record.proposal_attempt}", path)
            record.stage, record.status, record.code, record.message = "proposed", "ready", None, None
            self._save(ws, record)
            return self._public(ws, record)

    def submit_study_review(self, research_id: str, value: dict) -> dict:
        """Freeze a protocol only after a literature-grounded suitability decision."""
        review = StudyReview.model_validate(value)
        with self._operation(research_id) as (ws, record):
            self._require(ws, record, {"proposed"})
            if record.execution_attempt:
                raise WorkflowError("EXPERIMENT_ALREADY_DISPATCHED", "Research design cannot change after execution")
            key = f"study-review-{record.proposal_attempt}"
            if key in record.artifacts:
                raise WorkflowError("REVIEW_EVIDENCE_CONFLICT", "Each proposal's study decision is append-only")
            evidence = _read(ws, record, "literature")
            if review.accepted:
                _require_complete_literature(ResearchPlan.model_validate(_read(ws, record, "proposal")), evidence)
            selected = self._selected_literature(evidence, review)
            root = _artifact(ws, record, "proposal").parent
            receipt = {"origin": "native_host_submission", "review": review.model_dump(mode="json"),
                       "proposal_sha256": record.artifacts["proposal"].sha256,
                       "literature_sha256": record.artifacts["literature"].sha256}
            if review.accepted:
                plan = ResearchPlan.model_validate(_read(ws, record, "proposal"))
                path = ws.path("research/protocol.json")
                write_json(path, plan)
                _freeze(ws, record, "plan", path)
                write_json(root / "selected-literature.json", selected)
                _freeze(ws, record, "selected-literature", root / "selected-literature.json")
                receipt.update({"protocol_sha256": record.artifacts["plan"].sha256,
                                "selected_literature_sha256": record.artifacts["selected-literature"].sha256})
                record.stage, record.status, record.code, record.message = "planned", "ready", None, None
            else:
                record.status, record.code = "blocked", "STUDY_REJECTED"
                record.message = "; ".join(review.issues)
            write_json(root / "study-review.json", receipt)
            _freeze(ws, record, key, root / "study-review.json")
            _freeze(ws, record, "study-review", root / "study-review.json")
            self._save(ws, record)
            return self._public(ws, record)

    @staticmethod
    def _selected_literature(evidence: dict, review: StudyReview) -> dict:
        sources = science._literature_sources(evidence)
        selected = []
        for selection in review.selected_sources:
            source = sources.get(selection.source_id)
            if source is None:
                raise WorkflowError("LITERATURE_SELECTION_INVALID", "Selected source was not retrieved")
            try:
                science._citation_evidence(source)
            except ValueError as error:
                raise WorkflowError("LITERATURE_SELECTION_INVALID", str(error)) from None
            if selection.excerpt_index >= len(source["excerpts"]) or not source["excerpts"][selection.excerpt_index].strip():
                raise WorkflowError("LITERATURE_SELECTION_INVALID", "Selected excerpt was not inspected")
            if any(item["id"] == source["id"] for item in selected):
                raise WorkflowError("LITERATURE_SELECTION_INVALID", "Select one grounded excerpt per source")
            grounded = {**source, "excerpts": [source["excerpts"][selection.excerpt_index]],
                        "relevance": selection.relevance, "selected_excerpt_index": selection.excerpt_index}
            try:
                science._citation_evidence(grounded)
            except ValueError as error:
                raise WorkflowError("LITERATURE_SELECTION_INVALID", str(error)) from None
            selected.append(grounded)
        return {"sources": selected, "selection": review.model_dump(mode="json")["selected_sources"],
                "scope": "Only sources explicitly selected by the study suitability review may ground the manuscript"}

    def _require_study_review(self, ws: Workspace, record: Workflow) -> None:
        if "study-review" not in record.artifacts or "selected-literature" not in record.artifacts:
            raise WorkflowError("STUDY_REVIEW_REQUIRED", "An approved literature-grounded study review is required before execution or authoring")
        receipt = _read(ws, record, "study-review")
        review = StudyReview.model_validate(receipt.get("review", {}))
        if not review.accepted:
            raise WorkflowError("STUDY_REJECTED", "The retained research design was not accepted")
        evidence = _read(ws, record, "literature")
        if (receipt.get("origin") != "native_host_submission" or
                receipt.get("proposal_sha256") != record.artifacts["proposal"].sha256 or
                receipt.get("protocol_sha256") != record.artifacts["plan"].sha256 or
                receipt.get("literature_sha256") != record.artifacts["literature"].sha256 or
                receipt.get("selected_literature_sha256") != record.artifacts["selected-literature"].sha256 or
                _read(ws, record, "selected-literature") != self._selected_literature(evidence, review)):
            raise WorkflowError("ARTIFACT_CHANGED", "Study approval does not bind the retained protocol and selected literature")
        _require_complete_literature(ResearchPlan.model_validate(_read(ws, record, "plan")), evidence)

    def collect_literature(self, research_id: str) -> dict:
        with self._operation(research_id) as (ws, record):
            self._require(ws, record, {"proposed", "planned", "code_ready", "analyzed"})
            plan = ResearchPlan.model_validate(_read(ws, record, "proposal" if record.stage == "proposed" else "plan"))
            previous = _read(ws, record, "literature") if "literature" in record.artifacts else {}
            queries = list(dict.fromkeys(query.strip() for query in plan.literature_queries))

            # Cancellation can occur during DOI resolution after every search
            # was attempted. A fresh collection must complete before approval;
            # the partial receipt is retained as history rather than cleared.
            missing = queries if previous.get("cancelled") else [
                query for query in queries if query not in _attempted_literature_queries(previous)]
            evidence = previous
            if missing:
                existing_sources = previous.get("sources", [])
                remaining = max(0, 6 - sum(source.get("scope") in {"abstract", "full_text"} and bool(source.get("excerpts"))
                                         for source in existing_sources))
                supplement = self.collector(missing, ws.path("research"), limit=remaining, cancel=lambda: False)
                candidates = list(existing_sources)
                positions = {source.get("id"): index for index, source in enumerate(candidates)}
                reading_scopes = {"abstract": 1, "full_text": 2}
                additions = []
                for source in supplement.get("sources", []):
                    identifier = source.get("id")
                    if identifier not in positions:
                        positions[identifier] = len(candidates)
                        candidates.append(source)
                        additions.append(source)
                    else:
                        index = positions[identifier]
                        existing = candidates[index]
                        scope = reading_scopes.get(source.get("scope"), 0) if source.get("excerpts") else 0
                        prior_scope = reading_scopes.get(existing.get("scope"), 0) if existing.get("excerpts") else 0
                        if scope > prior_scope:
                            science._citation_evidence(source)
                            candidates[index] = source
                if len(additions) > remaining:
                    raise WorkflowError("LITERATURE_SOURCE_LIMIT", "Literature supplement exceeds the remaining source budget")
                inspected = [source for source in candidates if source.get("scope") in {"abstract", "full_text"} and source.get("excerpts")]
                metadata = [source for source in candidates if source not in inspected]
                evidence = {**previous, **{key: value for key, value in supplement.items()
                                           if key not in {"sources", "searches", "warnings", "history"}},
                            "sources": (inspected + metadata)[:6],
                            "searches": previous.get("searches", []) + supplement.get("searches", []),
                            "warnings": previous.get("warnings", []) + supplement.get("warnings", []),
                            "cancelled": supplement.get("cancelled", False)}
                if previous:
                    retained = record.artifacts["literature"]
                    history_key = "literature-history-" + retained.sha256
                    record.artifacts[history_key] = retained
                    evidence["history"] = previous.get("history", []) + [
                        {"artifact_id": history_key, "sha256": retained.sha256, "size": retained.size}]
                    path = ws.path(f"research/literature-evidence-{uid('revision')}.json")
                else:
                    path = ws.path("research/literature-evidence.json")
                    if path.exists():
                        path = ws.path(f"research/literature-evidence-{uid('revision')}.json")
                if path.exists():
                    raise WorkflowError("LITERATURE_EVIDENCE_CONFLICT", "A literature evidence revision cannot overwrite retained bytes")
                write_json(path, evidence)
                _freeze(ws, record, "literature", path)
            for number, search in enumerate(evidence.get("searches", [])):
                if search.get("raw_path"):
                    original = safe_relative(ws.path("research"), search["raw_path"])
                    if digest_file(original) != search.get("sha256"):
                        raise WorkflowError("ARTIFACT_CHANGED", "Literature search differs from its retrieval digest")
                    _freeze(ws, record, "literature-search-" + search["sha256"], original)
            for number, source in enumerate(evidence.get("sources", [])):
                for field, digest in (("raw_path", "sha256"), ("metadata_path", "metadata_sha256"), ("text_path", "text_sha256")):
                    if source.get(field):
                        original = safe_relative(ws.path("research"), source[field])
                        if digest_file(original) != source.get(digest):
                            raise WorkflowError("ARTIFACT_CHANGED", "Literature differs from its retrieval digest")
                        _freeze(ws, record, "literature-" + source[digest] + "-" + field, original)
            self._save(ws, record)
            if evidence.get("cancelled") or not any(source.get("scope") in {"abstract", "full_text"} and source.get("excerpts")
                                                    for source in evidence.get("sources", [])):
                raise WorkflowError("LITERATURE_EVIDENCE_INSUFFICIENT", "Metadata alone cannot support Related Work; retrieval evidence is retained")
            _require_complete_literature(plan, evidence)
            return self._public(ws, record)

    def record_inference(self, research_id: str, value: dict) -> dict:
        receipt = ModelEvidenceReceipt.model_validate(value)
        content = receipt.model_dump(mode="json", exclude_none=True)
        stem = f"{receipt.id}-{receipt.outcome}"
        key = "model-evidence-" + stem
        with self._operation(research_id, during_shutdown=True) as (ws, record):
            path = ws.path(f"research/model-evidence/{stem}.json")
            if key in record.artifacts:
                if _read(ws, record, key) != content:
                    raise WorkflowError("INFERENCE_EVIDENCE_CONFLICT", "Inference evidence is append-only")
                return {"artifactId": key, "sha256": record.artifacts[key].sha256}
            if path.exists():
                if loads_json(path.read_bytes()) != content:
                    raise WorkflowError("INFERENCE_EVIDENCE_CONFLICT", "Retained inference evidence differs")
            else:
                write_json(path, content)
            _freeze(ws, record, key, path)
            event = ws.path(f"research/model-evidence/journal-{stem}.json")
            event_content = {"event": "model-inference", "id": receipt.id, "at": receipt.at,
                             "phase": receipt.phase, "outcome": receipt.outcome,
                             "receipt_sha256": record.artifacts[key].sha256}
            if event.exists():
                if loads_json(event.read_bytes()) != event_content:
                    raise WorkflowError("INFERENCE_EVIDENCE_CONFLICT", "Retained inference journal differs")
            else:
                write_json(event, event_content)
            _freeze(ws, record, "model-journal-" + stem, event)
            self._save(ws, record)
            return {"artifactId": key, "sha256": record.artifacts[key].sha256}

    def submit_code(self, research_id: str, value: dict, review: dict) -> dict:
        bundle = CodeBundle.model_validate(value)
        accepted = _accepted(review)
        with self._operation(research_id) as (ws, record):
            if record.execution_attempt > 0:
                raise WorkflowError("EXPERIMENT_ALREADY_DISPATCHED", "A scientific execution was already dispatched; retained evidence cannot be replaced or rerun")
            self._require(ws, record, {"planned", "code_ready"})
            self._require_study_review(ws, record)
            plan = ResearchPlan.model_validate(_read(ws, record, "plan"))
            if bundle.runtime != plan.runtime:
                raise ValueError("Experiment runtime differs from frozen protocol")
            for item in bundle.files:
                path = safe_relative(ws.path("research/generated"), item.path)
                if item.path in {"bundle.json", "review.json"}:
                    raise ValueError("Experiment file collides with reserved controller metadata")
                if project._secret(path) or any(part.startswith(".") for part in Path(item.path).parts):
                    raise ValueError("Experiment code must use public declared paths")
                if path.suffix not in {".js", ".mjs", ".cjs", ".json", ".md", ".txt"}:
                    raise ValueError("Unsupported experiment file type")
            if Path(bundle.entrypoint).suffix not in {".js", ".mjs", ".cjs"}:
                raise ValueError("Experiment entrypoint must be a JavaScript module")
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
            if record.execution_attempt > 0:
                raise WorkflowError("EXPERIMENT_ALREADY_DISPATCHED", "A scientific execution was already dispatched; retained evidence cannot be replaced or rerun")
            self._require(ws, record, {"code_ready"})
            self._require_study_review(ws, record)
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
        """Acknowledge cancellation only after the owned worker and cleanup settle."""
        deadline = time.monotonic() + CANCEL_CLEANUP_SECONDS
        with self._operation(research_id, during_shutdown=True) as (ws, record):
            if record.status != "completed":
                record.cancellation_requested = True
            if record.status == "ready" and not record.terminal_control_failure and record.code != "CLEANUP_UNCONFIRMED":
                record.status, record.code = "cancelled", "CANCELLED"
            self._save(ws, record)
            future = self._jobs.get(research_id)

        # The worker needs these same workflow locks to commit its final receipt.
        if future is not None and not future.done():
            _, pending = wait((future,), timeout=max(0, deadline - time.monotonic()))
            if pending and not future.done():
                with self._operation(research_id, during_shutdown=True) as (ws, record):
                    record.code = "CLEANUP_UNCONFIRMED"
                    record.message = "Owned experiment did not finish cleanup before the cancellation deadline."
                    self._save(ws, record)
                raise WorkflowError("CLEANUP_UNCONFIRMED", "Owned experiment cleanup remains unconfirmed")

        with self._operation(research_id, during_shutdown=True) as (ws, record):
            handle = dict(record.active_handle)
        stopped = False
        # Native stop uses the private identity and must fit the same deadline.
        if handle and deadline - time.monotonic() >= CANCEL_STOP_SECONDS:
            try:
                stopped = self.runner.stop(handle)
            except Exception:
                pass

        with self._operation(research_id, during_shutdown=True) as (ws, record):
            # Only the exact identity inspected outside the lock may be cleared.
            cleanup_verified = stopped and record.active_handle == handle
            if cleanup_verified:
                self._record_cleanup(ws, record)
                record.active_handle = {}
                # Reconcile retained evidence only; never dispatch another run.
                try:
                    if record.status != "completed" and "observations" in record.artifacts:
                        science.reject_failed_controls(_read(ws, record, "observations"))
                    if (record.status != "completed" and not record.terminal_control_failure and
                            "execution" in record.artifacts and _read(ws, record, "execution").get("status") == "succeeded"):
                        self._analyze(ws, record)
                        record.status, record.stage, record.code = "ready", "analyzed", None
                except science.ControlFailure:
                    record.terminal_control_failure, record.code = True, "CONTROL_FAILED"
                except ValueError as exc:
                    record.code, record.message = getattr(exc, "code", "EXPERIMENT_INVALID"), str(exc)[:1500]
            future = self._jobs.get(research_id)
            cleanup_verified = cleanup_verified or ("execution" in record.artifacts and self._confirmed_cleanup(ws, record))
            future_failed = future is not None and future.done() and (future.cancelled() or future.exception() is not None)
            unresolved = bool(record.active_handle or (future is not None and not future.done()) or
                              (record.status == "running" and future is None and not cleanup_verified) or
                              (future_failed and not cleanup_verified) or
                              (record.code == "CLEANUP_UNCONFIRMED" and not cleanup_verified))
            if unresolved:
                record.code = "CLEANUP_UNCONFIRMED"
                record.message = "Owned experiment cleanup remains unconfirmed."
                self._save(ws, record)
                raise WorkflowError("CLEANUP_UNCONFIRMED", record.message)
            if record.status != "completed":
                if record.terminal_control_failure:
                    record.code = "CONTROL_FAILED"
                elif record.status not in {"blocked", "failed"} or record.code == "CLEANUP_UNCONFIRMED":
                    record.status, record.code = "cancelled", "CANCELLED"
                    if record.stage == "execute":
                        record.stage = "code_ready"
            self._save(ws, record)
            if future_failed:
                self._jobs.pop(research_id, None)
            result = self._public(ws, record)
            result["cleanup_confirmed"] = True
            return result

    def resume(self, research_id: str) -> dict:
        """Explicitly resume preparation or authoring, without dispatching a run."""
        with self._operation(research_id) as (ws, record):
            future = self._jobs.get(research_id)
            if future is not None and not future.done():
                raise WorkflowError("CLEANUP_UNCONFIRMED", "Owned worker completion must be confirmed before resuming")
            self._require(ws, record, {"created", "proposed", "planned", "code_ready", "analyzed", "manuscript"}, allow_cancelled=True)
            kind = self._resume_kind(record)
            if kind is None:
                raise WorkflowError("INVALID_STATE", "Only unexecuted preparation or verified authoring may resume")
            if kind == "authoring":
                self._require_successful_analysis(ws, record)
            else:
                _artifact(ws, record, "context")
                if ws.path("research/executions").exists():
                    raise WorkflowError("EXPERIMENT_ALREADY_DISPATCHED", "Preparation cannot resume over retained execution files")
                if record.stage in {"planned", "code_ready"}:
                    ResearchPlan.model_validate(_read(ws, record, "plan"))
                    self._require_study_review(ws, record)
                elif record.stage == "proposed":
                    ResearchPlan.model_validate(_read(ws, record, "proposal"))
                if record.stage == "code_ready":
                    metadata = _read(ws, record, "bundle")
                    review = _read(ws, record, f"code-review-{record.code_attempt}")
                    _accepted(review.get("review", {}))
                    if (metadata.get("source_digest") != ws.latest("project", Project).snapshot_digest or
                            metadata.get("protocol_sha256") != record.artifacts["plan"].sha256 or
                            review.get("origin") != "native_host_submission" or
                            review.get("bundle_sha256") != record.artifacts["bundle"].sha256 or
                            review.get("protocol_sha256") != record.artifacts["plan"].sha256):
                        raise WorkflowError("ARTIFACT_CHANGED", "Prepared code and its approval must bind the frozen source and protocol")
            identifier = uid("workflow-resume")
            path = ws.path("research/" + identifier + ".json")
            if path.exists() or identifier in record.artifacts:
                raise WorkflowError("RESUME_EVIDENCE_CONFLICT", "A workflow resume receipt cannot overwrite retained bytes")
            receipt = {"event": "workflow-resume", "kind": kind, "at": now(), "previous_status": record.status,
                       "previous_stage": record.stage, "previous_workflow": record.model_dump(mode="json"),
                       "execution_attempt": record.execution_attempt}
            if kind == "authoring":
                receipt.update({name + "_sha256": record.artifacts[key].sha256 for name, key in
                                (("execution", "execution"), ("observations", "observations"), ("analysis", "analysis"))})
            write_json(path, receipt)
            _freeze(ws, record, identifier, path)
            record.status, record.code, record.cancellation_requested = "ready", None, False
            record.message = "Research resumed from verified retained evidence; no experiment was dispatched."
            self._save(ws, record)
            return self._public(ws, record)

    def _require_successful_analysis(self, ws: Workspace, record: Workflow) -> None:
        self._require_study_review(ws, record)
        execution = _read(ws, record, "execution")
        if execution.get("status") != "succeeded":
            raise WorkflowError("EXPERIMENT_FAILED", "Authoring requires a retained successful execution")
        if not self._confirmed_cleanup(ws, record):
            raise WorkflowError("CLEANUP_UNCONFIRMED", "Retained execution cleanup must be confirmed before authoring resumes")
        plan = ResearchPlan.model_validate(_read(ws, record, "plan"))
        _production_execution(execution, plan)
        raw = _read(ws, record, "observations")
        try:
            science.reject_failed_controls(raw)
        except science.ControlFailure as error:
            raise WorkflowError("CONTROL_FAILED", str(error)) from None
        controls = raw.get("controls") if isinstance(raw, dict) else None
        if (not isinstance(controls, list) or not controls or
                any(not isinstance(control, dict) or control.get("passed") is not True or
                    not isinstance(control.get("name"), str) for control in controls) or
                any(not any(re.search(r"(?:^|[ _-])" + kind + r"(?:$|[ _-])", control["name"].casefold())
                            for control in controls) for kind in ("positive", "negative"))):
            raise WorkflowError("CONTROL_FAILED", "Retained positive and intentional-fault negative controls must have actually passed")
        analysis = _read(ws, record, "analysis")
        if (analysis.get("raw_sha256") != record.artifacts["observations"].sha256 or
                analysis.get("protocol_sha256") != record.artifacts["plan"].sha256 or
                analysis.get("controls") != controls):
            raise WorkflowError("ARTIFACT_CHANGED", "Retained analysis does not bind the frozen raw observations, protocol and controls")

    def revise_writing(self, research_id: str) -> dict:
        """Open a new draft while preserving a completed export and its approval."""
        with self._operation(research_id) as (ws, record):
            if record.status != "completed" or record.stage != "exported":
                raise WorkflowError("INVALID_STATE", "Only a completed exported manuscript may be explicitly revised")
            self._require(ws, record, {"exported"})
            self._require_successful_analysis(ws, record)
            for key in ("manuscript", "canonical", "manuscript-review", "export-md", "export-pdf", "export-docx",
                        "export-tex", "conversion", "validation", "reproducibility", "source-provenance"):
                _artifact(ws, record, key)
            validation = _read(ws, record, "validation")
            if (validation.get("passed") is not True or validation.get("research_id") != record.id or
                    validation.get("final_verification_in_archive") is not False or
                    not isinstance(validation.get("verification_journal"), str) or
                    re.fullmatch(r"verification-journal-[a-f0-9]{12}", validation["verification_journal"]) is None):
                raise WorkflowError("REVISION_UNVERIFIED", "Revision requires a retained completed export validation")
            journal = _artifact(ws, record, validation["verification_journal"])
            rows = [loads_json(line) for line in journal.read_text(encoding="utf-8").splitlines()]
            if (not rows or rows[-1].get("phase") != "complete" or
                    any(row.get("research_id") != record.id for row in rows)):
                raise WorkflowError("REVISION_UNVERIFIED", "Revision requires a completed hash-bound export verification journal")
            review = _read(ws, record, "manuscript-review")
            _accepted(review.get("review", {}), ManuscriptReview)
            if (review.get("origin") != "native_host_submission" or any(
                    review.get(field + "_sha256") != record.artifacts[key].sha256
                    for field, key in (("manuscript", "manuscript"), ("protocol", "plan"),
                                       ("analysis", "analysis"), ("literature", "literature")))):
                raise WorkflowError("ARTIFACT_CHANGED", "Retained manuscript approval does not bind the completed evidence")
            identifier = uid("authoring-revision")
            path = ws.path("research/" + identifier + ".json")
            suffix = identifier.removeprefix("authoring-revision-")
            aliases = {key: "authoring-history-" + suffix + "-" + key for key in record.artifacts
                       if key in {"manuscript", "canonical", "manuscript-review", "conversion", "validation",
                                  "reproducibility", "source-provenance"} or
                       (key.startswith("export-") and not key.startswith("export-attempt-"))}
            if path.exists() or identifier in record.artifacts or any(key in record.artifacts for key in aliases.values()):
                raise WorkflowError("REVISION_EVIDENCE_CONFLICT", "A manuscript revision cannot overwrite retained evidence")
            write_json(path, {"id": identifier, "event": "authoring-revision", "at": now(),
                             "previous_status": record.status, "previous_stage": record.stage,
                             "previous_workflow": record.model_dump(mode="json"), "preserved_artifacts": aliases,
                             "execution_attempt": record.execution_attempt,
                             "execution_sha256": record.artifacts["execution"].sha256,
                             "observations_sha256": record.artifacts["observations"].sha256,
                             "analysis_sha256": record.artifacts["analysis"].sha256})
            _freeze(ws, record, identifier, path)
            for key, retained in aliases.items():
                record.artifacts[retained] = record.artifacts.pop(key)
            record.status, record.stage, record.code, record.cancellation_requested = "ready", "analyzed", None, False
            record.message = "A new manuscript draft may be authored from unchanged retained evidence; previous approval and exports are preserved."
            self._save(ws, record)
            return self._public(ws, record)


    def _execute(self, research_id: str, lease) -> None:
        ws = self._workspace(research_id)

        def stopped():
            return self._closing or self._closed or ws.get("workflow", research_id, Workflow).cancellation_requested

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
        assessment = ManuscriptReview.model_validate(review)
        with self._operation(research_id) as (ws, record):
            self._require(ws, record, {"analyzed"})
            self._require_study_review(ws, record)
            plan = ResearchPlan.model_validate(_read(ws, record, "plan"))
            record.draft_attempt += 1
            root = ws.path(f"research/drafts/attempt-{record.draft_attempt}")
            while root.exists():
                record.draft_attempt += 1
                root = ws.path(f"research/drafts/attempt-{record.draft_attempt}")
            write_json(root / "draft.json", draft)
            _freeze(ws, record, f"draft-{record.draft_attempt}", root / "draft.json")
            self._save(ws, record)
            review_receipt = {"origin": "native_host_submission", "review": assessment.model_dump(mode="json"),
                             "draft_sha256": record.artifacts[f"draft-{record.draft_attempt}"].sha256,
                             "protocol_sha256": record.artifacts["plan"].sha256,
                             "analysis_sha256": record.artifacts["analysis"].sha256,
                             "literature_sha256": record.artifacts["literature"].sha256}
            if not assessment.accepted:
                write_json(root / "review.json", review_receipt)
                _freeze(ws, record, f"manuscript-review-{record.draft_attempt}", root / "review.json")
                _freeze(ws, record, "manuscript-review", root / "review.json")
                record.status, record.code, record.message = "blocked", "MANUSCRIPT_REJECTED", "; ".join(assessment.issues)
                self._save(ws, record)
                return self._public(ws, record)
            rendered = science.validate_and_render(draft.model_dump(mode="json"), plan, _read(ws, record, "analysis"),
                                                  _read(ws, record, "selected-literature"), root,
                                                  author=load_author().model_dump(exclude_defaults=True))
            markdown = Path(rendered["markdown_path"])
            _append_figures(ws, record, markdown)
            _freeze(ws, record, "manuscript", markdown)
            _freeze(ws, record, "canonical", Path(rendered["canonical_path"]))
            write_json(root / "review.json", {**review_receipt, "manuscript_sha256": record.artifacts["manuscript"].sha256})
            _freeze(ws, record, "manuscript-review", root / "review.json")
            _freeze(ws, record, f"manuscript-review-{record.draft_attempt}", root / "review.json")
            record.stage, record.status, record.code, record.message = "manuscript", "ready", None, None
            self._save(ws, record)
            return self._public(ws, record)

    def export(self, research_id: str) -> dict:
        with self._operation(research_id) as (ws, record):
            self._require(ws, record, {"manuscript", "exported"})
            self._require_study_review(ws, record)
            if record.stage == "exported":
                root = ws.path("research/exports/" + uid("verification-attempt"))
                root.mkdir(parents=True, exist_ok=False)
                self._verify(ws, record, root / "verification.jsonl")
                self._save(ws, record)
                return self._public(ws, record)
            attempt = uid("export-attempt")
            root = ws.path("research/exports/" + attempt)
            root.mkdir(parents=True, exist_ok=False)
            receipt = root / "attempt.json"
            write_json(receipt, {"event": "export-started", "at": now(),
                                 "manuscript_sha256": record.artifacts["manuscript"].sha256,
                                 "execution_sha256": record.artifacts["execution"].sha256,
                                 "execution_attempt": record.execution_attempt})
            _freeze(ws, record, attempt, receipt)
            self._save(ws, record)
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
                receipts[format] = conversion.convert(markdown, output, pandoc=os.environ.get("PYPANDOC_PANDOC") or None)
                _freeze(ws, record, "export-" + format, output)
                outputs[format] = output
            write_json(root / "conversion-receipts.json", receipts)
            _freeze(ws, record, "conversion", root / "conversion-receipts.json")
            if errors := conversion.verify_receipts(markdown, outputs, root / "conversion-receipts.json"):
                raise ValueError("; ".join(errors))
            self._bundle(ws, record, root)
            validation = self._verify(ws, record, root / "verification.jsonl")
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
            "study-review.json": "study-review", "selected-literature.json": "selected-literature",
            "paper.md": "export-md", "paper.pdf": "export-pdf", "paper.docx": "export-docx", "paper.tex": "export-tex",
            "conversion-receipts.json": "conversion", "manuscript-review.json": "manuscript-review"}.items()}
        if "runtime-manifest" in record.artifacts:
            selection["runtime-manifest.json"] = _artifact(ws, record, "runtime-manifest")
        for key in record.artifacts:
            if re.fullmatch(r"(?:proposal|study-review)-[1-3]", key):
                path = _artifact(ws, record, key)
                selection["research-design/" + key + ".json"] = path
            if re.fullmatch(r"manuscript-review-[1-9][0-9]*", key):
                selection["authoring/retained/" + key + ".json"] = _artifact(ws, record, key)
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
            if key.startswith("export-attempt-"):
                selection["export-attempts/" + key + ".json"] = _artifact(ws, record, key)
            if key.startswith("workflow-resume-"):
                path = _artifact(ws, record, key)
                selection["authoring/" + path.name] = path
            if re.fullmatch(r"authoring-revision-[a-f0-9]{12}", key):
                path = _artifact(ws, record, key)
                selection["authoring/" + path.name] = path
            if key.startswith("authoring-history-") and not key.endswith("-reproducibility"):
                path = _artifact(ws, record, key)
                selection["authoring/history/" + key + "/" + path.name] = path
            if re.fullmatch(r"draft-[1-9][0-9]*|verification-journal-[a-f0-9]{12}", key):
                path = _artifact(ws, record, key)
                selection["authoring/retained/" + key + "/" + path.name] = path
            if key.startswith(("model-evidence-", "model-journal-")):
                path = _artifact(ws, record, key)
                selection["model-evidence/" + path.name] = path
            if re.fullmatch(r"supporting-document-import-[a-f0-9]{12}", key):
                path = _artifact(ws, record, key)
                selection["supporting-documents/imports/" + path.name] = path
            elif re.fullmatch(r"supporting-document-[a-f0-9]{12}", key):
                path = _artifact(ws, record, key)
                selection["supporting-documents/" + key + "/" + path.name] = path
            if key.startswith("analysis-"):
                selection["analysis/" + _artifact(ws, record, key).name] = _artifact(ws, record, key)
            if key.startswith("literature-history-"):
                path = _artifact(ws, record, key)
                selection["literature/history/" + key.removeprefix("literature-history-") + ".json"] = path
            elif key.startswith("literature-"):
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
        if "source-collection" in record.artifacts:
            selection["source-collection.json"] = _artifact(ws, record, "source-collection")
        if sum(path.stat().st_size for path in selection.values()) > MAX_BUNDLE_BYTES:
            raise WorkflowError("REPRODUCTION_BUNDLE_TOO_LARGE", "Reproduction archive inputs exceed 96 MiB")
        archive = root / "reproducibility.zip"
        runtime_instructions = (
            "Use Paper Factory's recorded bundled Python, Node and extracted QuickJS runtime.\n"
            "Inspect runtime-inventory.json from the desktop distribution and require runtime readiness before execution.\n"
            "QuickJS runs frozen source and generated code in separate guests using callProduction and retainFixture.\n"
            "TypeScript is erased by the recorded trusted transformer; inspect original and compiled hashes in runtime-manifest.json.\n"
        )
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
            output.writestr("README.md", "# Reproduce this controlled software study\n\n"
                "Frozen source, protocol, experiment, observations, analysis and native exports are retained.\n"
                "execution.json records actual isolation, resource limits, production calls and cleanup.\n"
                "runtime-manifest.json, when present, records source and runtime provenance.\n" + runtime_instructions +
                "Recompute results with analysis/analysis.py and its documented arguments.\n"
                "The final verification journal and validation are separate frozen artifacts produced after this archive; they are not archive members.\n"
                "Reviews are native host submissions; reviewer independence is not attested by this controller.\n"
                "Explicit authoring revisions retain prior drafts, approvals and exports in authoring/. Revision receipts preserve the full prior frozen artifact inventory. Prior reproduction ZIPs remain separate frozen artifacts and are excluded here to avoid nested archives.\n"
                "Source license authorization has not been assessed. Author review is required; no submission occurred.\n")
            output.writestr("inventory.json", json.dumps({name: {"sha256": digest_file(path), "size": path.stat().st_size}
                                                          for name, path in selection.items()}, indent=2))
            for name, path in sorted(selection.items()):
                ensure_unlinked(path)
                output.write(path, name)
        _freeze(ws, record, "reproducibility", archive)

    def _verify(self, ws: Workspace, record: Workflow, journal: Path) -> dict:
        ensure_unlinked(journal)
        with journal.open("x", encoding="utf-8") as stream:
            def phase(name: str) -> None:
                stream.write(json.dumps({"at": now(), "research_id": record.id, "phase": name}) + "\n")
                stream.flush()
                os.fsync(stream.fileno())

            phase("artifact-source-validation")
            _verify_artifacts(ws, record)
            plan = ResearchPlan.model_validate(_read(ws, record, "plan"))
            _production_execution(_read(ws, record, "execution"), plan)
            if not self._confirmed_cleanup(ws, record):
                raise WorkflowError("CLEANUP_UNCONFIRMED", "Export requires confirmed experiment cleanup")

            phase("trusted-analysis")
            analysis = _read(ws, record, "analysis")
            # Recompute the same trusted values without regenerating analysis files or figures.
            computed = science._compute(_read(ws, record, "observations"), plan.model_dump(mode="json"))
            for key in ("results", "parameters", "controls", "protocol_digest", "observation_digest", "summaries", "paired_deltas"):
                if computed.get(key) != analysis.get(key):
                    raise ValueError("Analysis differs from raw observation recomputation: " + key)

            phase("manuscript-rendering")
            canonical = _read(ws, record, "canonical")
            with tempfile.TemporaryDirectory(prefix="paperfactory-manuscript-") as directory:
                rendered = science.validate_and_render({"title": canonical["title"], "sections": canonical["sections"]}, plan, analysis,
                    _read(ws, record, "selected-literature"), Path(directory), author=canonical.get("author"))
                _append_figures(ws, record, Path(rendered["markdown_path"]))
                if digest_file(Path(rendered["markdown_path"])) != record.artifacts["manuscript"].sha256:
                    raise ValueError("Manuscript differs from independent evidence rendering")
            if digest_file(_artifact(ws, record, "export-md")) != record.artifacts["manuscript"].sha256:
                raise ValueError("Export source differs from verified manuscript")

            phase("pdf")
            from pypdf import PdfReader

            pdf = PdfReader(_artifact(ws, record, "export-pdf"))
            if pdf.is_encrypted or not pdf.pages or not any(page.extract_text() for page in pdf.pages):
                raise ValueError("Native PDF cannot be independently read")

            phase("docx")
            from docx import Document

            word = Document(_artifact(ws, record, "export-docx"))
            word_text = "\n".join(paragraph.text for paragraph in word.paragraphs)
            if (len(re.findall(r"\b[\w'-]+\b", word_text)) < 300 or canonical["title"] not in word_text or
                    any(section["heading"] not in word_text for section in canonical["sections"])):
                raise ValueError("Native Word manuscript is incomplete")

            phase("tex-conversion")
            tex = _artifact(ws, record, "export-tex").read_text(encoding="utf-8")
            if "\\begin{document}" not in tex or "\\end{document}" not in tex:
                raise ValueError("Standalone LaTeX export is incomplete")
            if errors := conversion.verify_receipts(_artifact(ws, record, "export-md"),
                    {format: _artifact(ws, record, "export-" + format) for format in ("pdf", "docx", "tex")},
                    _artifact(ws, record, "conversion")):
                raise ValueError("; ".join(errors))

            phase("zip")
            with zipfile.ZipFile(_artifact(ws, record, "reproducibility")) as archive:
                if archive.testzip():
                    raise ValueError("Reproduction archive has a CRC error")
                for name, item in loads_json(archive.read("inventory.json")).items():
                    data = archive.read(name)
                    if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                        raise ValueError("Reproduction archive member differs from its inventory")
            phase("complete")

        identifier = uid("verification-journal")
        _freeze(ws, record, identifier, journal)
        return {"passed": True, "research_id": record.id, "results": len(analysis["results"]),
                "pages": len(pdf.pages), "publication": "author review required; not submitted",
                "verification_journal": identifier, "final_verification_in_archive": False}

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
                    cleaned = not record.active_handle and self._confirmed_cleanup(ws, record)
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

    def close(self, *, deadline: float | None = None) -> None:
        deadline = deadline if deadline is not None else time.monotonic() + SHUTDOWN_CLEANUP_SECONDS
        with self._mutex:
            if self._closed:
                return
            self._closing = True
            jobs = dict(self._jobs)
            owned_ids = set(jobs) | self._recovered
            for research_id, future in jobs.items():
                if not future.done():
                    ws = self._workspace(research_id)
                    with ws.lock("workflow"):
                        record = ws.get("workflow", research_id, Workflow)
                        record.cancellation_requested = True
                        self._save(ws, record)
        _, pending = wait(jobs.values(), timeout=max(0, deadline - time.monotonic())) if jobs else (set(), set())
        if pending:
            for research_id, future in jobs.items():
                if future in pending and not future.done():
                    ws = self._workspace(research_id)
                    with self._mutex, ws.lock("workflow"):
                        record = ws.get("workflow", research_id, Workflow)
                        record.code = "CLEANUP_UNCONFIRMED"
                        record.message = "Owned experiment did not finish cleanup before the shutdown deadline."
                        self._save(ws, record)
            if any(not future.done() for future in pending):
                raise WorkflowError("CLEANUP_UNCONFIRMED", "Owned experiment jobs did not finish cleanup before shutdown")
        if time.monotonic() >= deadline:
            raise WorkflowError("CLEANUP_UNCONFIRMED", "Owned experiment jobs did not finish cleanup before shutdown")
        for research_id in owned_ids:
            ws = self._workspace(research_id)
            with self._mutex, ws.lock("workflow"):
                record = ws.get("workflow", research_id, Workflow)
                handle = dict(record.active_handle)
            cleaned = False
            if handle and deadline - time.monotonic() >= CANCEL_STOP_SECONDS:
                try:
                    cleaned = self.runner.stop(handle)
                except Exception:
                    pass
            with self._mutex, ws.lock("workflow"):
                record = ws.get("workflow", research_id, Workflow)
                cleanup_verified = cleaned and record.active_handle == handle
                if cleanup_verified:
                    self._record_cleanup(ws, record)
                    record.active_handle = {}
                    if record.status != "completed":
                        record.code = "INTERRUPTED"
                        try:
                            if "observations" in record.artifacts:
                                science.reject_failed_controls(_read(ws, record, "observations"))
                            if (not record.terminal_control_failure and "execution" in record.artifacts and
                                    _read(ws, record, "execution").get("status") == "succeeded"):
                                self._analyze(ws, record)
                                record.status, record.stage, record.code = "ready", "analyzed", None
                        except science.ControlFailure:
                            record.terminal_control_failure, record.code = True, "CONTROL_FAILED"
                        except ValueError as exc:
                            record.code, record.message = getattr(exc, "code", "EXPERIMENT_INVALID"), str(exc)[:1500]
                        if record.terminal_control_failure:
                            record.code = "CONTROL_FAILED"
                    self._save(ws, record)
                cleanup_verified = cleanup_verified or ("execution" in record.artifacts and self._confirmed_cleanup(ws, record))
                future = jobs.get(research_id)
                future_failed = future is not None and (future.cancelled() or future.exception() is not None)
                if (record.active_handle or (future_failed and not cleanup_verified) or
                        (record.status == "running" and future is None and not cleanup_verified) or
                        (record.code == "CLEANUP_UNCONFIRMED" and not cleanup_verified)):
                    record.code = "CLEANUP_UNCONFIRMED"
                    record.message = "Owned experiment cleanup remains unconfirmed."
                    self._save(ws, record)
                    raise WorkflowError("CLEANUP_UNCONFIRMED", "Owned experiment cleanup remains unconfirmed")
        self._pool.shutdown(wait=True, cancel_futures=False)
        self._closed = True

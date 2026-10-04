"""JSON command adapter for an approved, durable research scratch directory.

The host supplies proposals. WorkflowService owns source snapshots, isolated
execution, scientific checks and frozen exports. This adapter imports no MCP,
model provider or account state and never executes submitted code on the host.
"""

import argparse
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

from pydantic import ValidationError

from .autonomous import literature, science
from .workflow import WorkflowError, WorkflowService, _diagnostic
from .workspace import ensure_unlinked, loads_json, safe_relative

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_FIXED_BYTES = 64 * 1024 * 1024


def _bytes(path: Path, maximum: int) -> bytes:
    """Read a bounded, ordinary input without following linked components."""
    ensure_unlinked(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError("Input must be an ordinary, unlinked file")
        if metadata.st_size > maximum:
            raise ValueError("Input exceeds its byte limit")
        content = stream.read(maximum + 1)
    if len(content) > maximum:
        raise ValueError("Input exceeds its byte limit")
    return content


def _input(path: str) -> dict:
    value = loads_json(_bytes(Path(path).expanduser(), MAX_INPUT_BYTES))
    if not isinstance(value, dict):
        raise ValueError("Submitted JSON must contain an object")
    return value


class FixedLiteratureCollector:
    """Import declared private source bytes without inventing retrieval or reading.

    The host selects a fixed manifest. Hash verification establishes byte identity,
    not the truth of a source or reviewer independence. The normal controller still
    freezes every imported raw, metadata and inspected-text artifact.
    """

    def __init__(self, manifest_path: Path):
        self.path = manifest_path.expanduser().absolute()
        content = _bytes(self.path, literature.MAX_JSON_BYTES)
        self.digest = hashlib.sha256(content).hexdigest()
        self.manifest = loads_json(content)
        if not isinstance(self.manifest, dict):
            raise ValueError("Fixed literature manifest must contain an object")
        sources = science._literature_sources(self.manifest)
        if not sources or len(sources) > 6:
            raise ValueError("Fixed literature needs between one and six declared sources")
        for source in sources.values():
            if source.get("scope") not in {"metadata_only", "abstract", "full_text"}:
                raise ValueError("Fixed literature must preserve an explicit inspected scope")
            excerpts = source.get("excerpts", [])
            if (not isinstance(excerpts, list) or len(excerpts) > literature.MAX_EXCERPTS
                    or any(not isinstance(text, str) or len(text) > literature.MAX_EXCERPT_CHARS for text in excerpts)):
                raise ValueError("Fixed literature excerpts exceed the bounded reading contract")
            if source["scope"] != "metadata_only":
                science._citation_evidence(source)
                if not source.get("text_path"):
                    raise ValueError("Inspected fixed literature needs its retained text artifact")
            for field, digest in (("raw_path", "sha256"), ("metadata_path", "metadata_sha256"), ("text_path", "text_sha256")):
                name, expected = source.get(field), source.get(digest)
                if field == "raw_path" or name is not None or expected is not None:
                    if (not isinstance(name, str) or not name.startswith("literature/")
                            or not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected)):
                        raise ValueError("Fixed literature requires declared relative paths and SHA256 digests")
                    safe_relative(self.path.parent, name)
        for field in ("searches", "warnings"):
            if not isinstance(self.manifest.get(field, []), list):
                raise ValueError("Fixed literature searches and warnings must be lists")

    def __call__(self, queries, root, *, limit=6, cancel=None) -> dict:
        if type(limit) is not int or not 1 <= limit <= 6:
            raise ValueError("Fixed literature source limit must be between one and six")
        if hashlib.sha256(_bytes(self.path, literature.MAX_JSON_BYTES)).hexdigest() != self.digest:
            raise WorkflowError("ARTIFACT_CHANGED", "Fixed literature manifest changed before import")
        selected = copy.deepcopy(self.manifest["sources"][:limit])
        files, total = {}, 0
        for source in selected:
            if cancel is not None and cancel():
                return {"sources": [], "searches": [], "warnings": [], "cancelled": True}
            for field, digest in (("raw_path", "sha256"), ("metadata_path", "metadata_sha256"), ("text_path", "text_sha256")):
                if not source.get(field):
                    continue
                name = source[field]
                content = _bytes(safe_relative(self.path.parent, name), literature.MAX_PDF_BYTES)
                if hashlib.sha256(content).hexdigest() != source[digest]:
                    raise WorkflowError("ARTIFACT_CHANGED", "Fixed literature bytes differ from their declared digest")
                if name in files and files[name] != content:
                    raise WorkflowError("ARTIFACT_CHANGED", "Fixed literature file declarations disagree")
                if name not in files:
                    total += len(content)
                    if total > MAX_FIXED_BYTES:
                        raise ValueError("Fixed literature inputs exceed 64 MiB")
                    files[name] = content
            if source.get("scope") != "metadata_only":
                text = files[source["text_path"]].decode("utf-8")
                if len(text) > literature.MAX_TEXT_CHARS:
                    raise ValueError("Fixed literature inspected text exceeds its reading limit")
                normalized = " ".join(text.split())
                if any(" ".join(excerpt.split()) not in normalized for excerpt in source["excerpts"]):
                    raise ValueError("Fixed literature excerpts differ from the retained inspected text")
        if cancel is not None and cancel():
            return {"sources": [], "searches": [], "warnings": [], "cancelled": True}
        root = Path(root)
        ensure_unlinked(root)
        destinations = {}
        for name, content in files.items():
            destination = safe_relative(root, name)
            if destination.exists() and _bytes(destination, literature.MAX_PDF_BYTES) != content:
                raise WorkflowError("ARTIFACT_CHANGED", "Existing literature bytes differ from the fixed input")
            destinations[name] = destination
        for name, destination in destinations.items():
            if destination.exists():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            ensure_unlinked(destination)
            with destination.open("xb") as stream:
                stream.write(files[name])
        return {
            "sources": selected, "searches": copy.deepcopy(self.manifest.get("searches", [])),
            "warnings": [*self.manifest.get("warnings", []),
                         "Fixed input hashes were verified; retrieval and inspected scope remain the retained source provenance, not a new network search."],
            "cancelled": False, "fixed_input_manifest_sha256": self.digest,
            "collection_provenance": copy.deepcopy(self.manifest.get("collection_provenance", {})),
        }


def artifact_bytes(service: WorkflowService, research_id: str, artifact_id: str) -> dict:
    """Transport actual controller-owned bytes, checking the frozen digest again."""
    state = service.status(research_id, include_materials=False)
    artifact = state.get("artifacts", {}).get(artifact_id)
    if not isinstance(artifact, dict):
        raise WorkflowError("ARTIFACT_MISSING", "The requested frozen artifact is unavailable")
    size = artifact.get("size")
    if type(size) is not int or not 0 <= size <= MAX_ARTIFACT_BYTES:
        raise WorkflowError("ARTIFACT_TOO_LARGE", "Artifact transport is limited to 16 MiB")
    content = _bytes(service.artifact_path(research_id, artifact_id), MAX_ARTIFACT_BYTES)
    digest = hashlib.sha256(content).hexdigest()
    if len(content) != size or digest != artifact.get("sha256"):
        raise WorkflowError("ARTIFACT_CHANGED", "Artifact bytes differ from the frozen controller record")
    return {"research_id": research_id, "artifact_id": artifact_id, "size": size, "sha256": digest,
            "encoding": "base64", "content": base64.b64encode(content).decode("ascii"), "is_untrusted_data": True}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="Approved writable research scratch directory.")
    parser.add_argument("--runtime-root", type=Path, help="Extracted, verified QuickJS runtime bundle.")
    parser.add_argument("--literature-manifest", type=Path, help="Explicit fixed primary-source manifest; otherwise use the existing network collector.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("environment")
    create = commands.add_parser("create")
    create.add_argument("--source", required=True, help="Public GitHub URL or approved source snapshot directory.")
    create.add_argument("--goal", required=True)
    for name in ("status", "material", "submit-plan", "collect-literature", "submit-code", "run", "cancel", "submit-manuscript", "export", "artifact-bytes"):
        command = commands.add_parser(name)
        command.add_argument("research_id")
        if name == "status":
            command.add_argument("--include-materials", action="store_true")
        elif name == "material":
            command.add_argument("--area", choices=("source", "experiment", "evidence"), required=True)
            command.add_argument("--name", required=True)
            command.add_argument("--offset", type=int, default=0)
            command.add_argument("--limit", type=int, default=16000)
        elif name in {"submit-plan", "submit-code", "submit-manuscript"}:
            command.add_argument("--input", required=True, help="Trusted host proposal JSON file; not measurements.")
            if name != "submit-plan":
                command.add_argument("--review", required=True, help="Native host ScientificReview JSON file.")
        elif name == "artifact-bytes":
            command.add_argument("artifact_id")
    return parser


def _dispatch(service: WorkflowService, args) -> dict:
    command = args.command
    if command == "environment":
        runtime = service.runner.status()
        result = {key: runtime.get(key) for key in ("ready", "backend", "image_digest", "runtimes", "dependencies", "versions", "limits", "declared_limits", "simulation", "cleanup_confirmed")}
        if not result["ready"]:
            result["reason"] = _diagnostic(runtime.get("reason")) or "The provisioned isolated runtime is unavailable."
            supervisor_instructions = {
                "SUPERVISOR_UNAVAILABLE": "Restore permitted access to the supervisor directory and lease before checking readiness again.",
                "SUPERVISOR_BUSY": "Wait for the existing supervisor owner to finish before checking readiness again.",
                "SUPERVISOR_STATE_INVALID": "Preserve and inspect the invalid supervisor journal before checking readiness again.",
            }
            supervisor_code = runtime.get("code")
            if (runtime.get("backend") == "quickjs-wasm" and isinstance(supervisor_code, str)
                    and supervisor_code in supervisor_instructions
                    and not runtime.get("active_handle")):
                result["code"] = supervisor_code
                result["instructions"] = supervisor_instructions[supervisor_code]
                diagnostic = runtime.get("diagnostic")
                if isinstance(diagnostic, dict):
                    safe = {}
                    if diagnostic.get("stage") == "supervisor-prepare":
                        safe["stage"] = "supervisor-prepare"
                    if isinstance(diagnostic.get("exception_type"), str) and diagnostic["exception_type"] in {"OSError", "PermissionError", "FileNotFoundError", "FileExistsError",
                            "NotADirectoryError", "IsADirectoryError", "BlockingIOError", "TimeoutError", "ValueError", "KeyError", "TypeError"}:
                        safe["exception_type"] = diagnostic["exception_type"]
                    for key, maximum in (("errno", 4095), ("winerror", 65535)):
                        value = diagnostic.get(key)
                        if type(value) is int and 0 <= value <= maximum:
                            safe[key] = value
                    if safe:
                        result["diagnostic"] = safe
            elif result["cleanup_confirmed"] is False:
                result["code"] = "CLEANUP_UNCONFIRMED"
                result["instructions"] = "Reconcile existing owned worker cleanup before checking readiness or starting another experiment."
            else:
                result["instructions"] = "Provision and verify the isolated runtime before submitting a plan or running code."
        return result
    if command == "create":
        return service.create(args.source, args.goal)
    research_id = args.research_id
    if command == "status":
        return service.status(research_id, include_materials=args.include_materials)
    if command == "material":
        return service.read_material(research_id, args.area, args.name, offset=args.offset, limit=args.limit)
    if command == "submit-plan":
        return service.submit_plan(research_id, _input(args.input))
    if command == "collect-literature":
        return service.collect_literature(research_id)
    if command == "submit-code":
        return service.submit_code(research_id, _input(args.input), _input(args.review))
    if command == "run":
        service.start_experiment(research_id)
        while True:
            result = service.status(research_id, include_materials=False)
            if result["status"] != "running":
                return result
            time.sleep(0.1)
    if command == "cancel":
        return service.cancel(research_id)
    if command == "submit-manuscript":
        return service.submit_manuscript(research_id, _input(args.input), _input(args.review))
    if command == "export":
        return service.export(research_id)
    return artifact_bytes(service, research_id, args.artifact_id)


def _error(exc: Exception) -> dict:
    if isinstance(exc, ValidationError):
        details = "; ".join(".".join(map(str, item["loc"])) + ": " + item["msg"]
                            for item in exc.errors(include_input=False, include_url=False, include_context=False)[:6])
        code, message = "INVALID_ARGUMENT", _diagnostic(details)
    elif isinstance(exc, WorkflowError):
        code, message = exc.code, _diagnostic(exc)
    elif isinstance(exc, FileNotFoundError):
        code, message = "INPUT_NOT_FOUND", "A requested input or research artifact is missing."
    elif isinstance(exc, (ImportError, ModuleNotFoundError)):
        code, message = "RUNTIME_UNAVAILABLE", "The requested runtime adapter or its dependencies are not installed."
    elif isinstance(exc, OSError):
        code, message = "INPUT_UNAVAILABLE", "A declared input or retained artifact could not be read or written."
    else:
        code = "INVALID_ARGUMENT" if isinstance(exc, ValueError) else "RESEARCH_FAILED"
        message = _diagnostic(exc) if isinstance(exc, ValueError) else "The controller could not complete this operation."
    instructions = {
        "CONTROL_FAILED": "Preserve the failed scientific control and its evidence. Do not rerun this study for favorable observations.",
        "CLEANUP_UNCONFIRMED": "Confirm owned worker cleanup before submitting code or starting another experiment.",
        "ISOLATION_UNAVAILABLE": "Verify the isolated runtime with environment before continuing; do not execute code on the host.",
        "RUNTIME_UNAVAILABLE": "Provide the verified runtime bundle and its declared dependencies, then check environment before continuing.",
        "ARTIFACT_CHANGED": "Restore the original declared inputs. Changed evidence cannot be used.",
        "INPUT_NOT_FOUND": "Provide the declared JSON or source input file, then retry the unavailable operation.",
        "INPUT_UNAVAILABLE": "Check access to the approved scratch directory and declared ordinary input files before retrying.",
    }.get(code, "Read status with --include-materials and follow the current controller instructions before continuing.")
    return {"error": {"code": code, "message": message}, "instructions": instructions}


def main(argv=None, *, service_factory=None) -> int:
    args = _parser().parse_args(argv)
    service, runner, result, exit_code = None, None, None, 0
    try:
        if args.runtime_root is not None:
            from .autonomous.quickjs_runner import QuickJSRunner

            runner = QuickJSRunner(args.runtime_root, supervisor_root=args.data / "quickjs-supervisor",
                                   host_profile=os.environ.get("PF_HOST_MODE", "private"))
        collector = FixedLiteratureCollector(args.literature_manifest) if args.literature_manifest else None
        service = (service_factory or WorkflowService)(args.data, runner=runner, collector=collector)
        result = _dispatch(service, args)
        if args.command == "run" and result.get("status") in {"blocked", "failed", "cancelled"}:
            exit_code = 1
    except KeyboardInterrupt:
        result, exit_code = {"error": {"code": "CANCELLED", "message": "Execution was interrupted; owned cleanup and retained evidence are preserved."}}, 130
        if service is not None and args.command == "run":
            try:
                service.cancel(args.research_id)
            except Exception as exc:
                result, exit_code = _error(exc), 1
    except Exception as exc:
        result, exit_code = _error(exc), 1
    finally:
        if service is not None:
            try:
                service.close()
            except Exception as exc:
                result, exit_code = _error(exc), 1
        if runner is not None:
            try:
                runner.close()
            except Exception:
                result, exit_code = _error(WorkflowError(
                    "CLEANUP_UNCONFIRMED", "Owned QuickJS worker cleanup remains unconfirmed.")), 1
    # Base64 is an artifact transport for host attachment tools, not a displayed
    # download link. The caller should save/attach decoded bytes and verify SHA256.
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

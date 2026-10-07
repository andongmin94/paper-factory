"""Bounded JSON Lines IPC. OAuth and model calls remain in Electron main."""

import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import json
from pathlib import Path
import re
import sys
import threading
import time

from pydantic import ValidationError

from .standalone_runtime import StandaloneRuntime
from .workflow import SHUTDOWN_CLEANUP_SECONDS, WorkflowError, _diagnostic
from .workflow_models import Workflow
from .workspace import Workspace, ensure_unlinked, loads_json

MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
MAX_QUEUED_REQUESTS = 32
MAX_RECENT_IDS = 1024
SHUTDOWN_ALLOWED = {"shutdown", "runtime.status", "workflow.list", "workflow.status", "workflow.recordInference", "workflow.cancel"}
METHODS = {
    "runtime.status": set(), "workflow.create": {"source", "goal"}, "workflow.list": set(),
    "workflow.status": {"researchId", "includeMaterials"},
    "workflow.readMaterial": {"researchId", "area", "name", "offset", "limit"},
    "workflow.addEvidence": {"researchId", "files"},
    "workflow.submitProposal": {"researchId", "value"}, "workflow.submitStudyReview": {"researchId", "review"},
    "workflow.submitCode": {"researchId", "value", "review"},
    "workflow.collectLiterature": {"researchId"}, "workflow.startExperiment": {"researchId"},
    "workflow.collectAuthoringLiterature": {"researchId", "queries"},
    "workflow.selectAuthoringLiterature": {"researchId", "selectedSources"},
    "workflow.cancel": {"researchId"}, "workflow.resume": {"researchId"}, "workflow.reviseWriting": {"researchId"},
    "workflow.redesignStudy": {"researchId"},
    "workflow.improveWriting": {"researchId"},
    "workflow.submitManuscript": {"researchId", "value", "review"},
    "workflow.export": {"researchId"}, "artifact.resolve": {"researchId", "artifactId"}, "shutdown": set(),
    "workflow.recordInference": {"researchId", "receipt"},
}
OPTIONAL = {"workflow.status": {"includeMaterials"}, "workflow.readMaterial": {"offset", "limit"}}


def request(raw: bytes) -> dict:
    if len(raw) > MAX_INPUT_BYTES:
        raise WorkflowError("INPUT_TOO_LARGE", "IPC request exceeds its byte limit")
    data = loads_json(raw)
    if not isinstance(data, dict) or set(data) != {"id", "method", "params"}:
        raise ValueError("Use id, method and params only")
    if not isinstance(data["id"], str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", data["id"]):
        raise ValueError("Invalid request identifier")
    if not isinstance(data["method"], str) or data["method"] not in METHODS:
        raise WorkflowError("METHOD_NOT_ALLOWED", "IPC method is unavailable")
    params = data["params"]
    allowed = METHODS[data["method"]]
    if (not isinstance(params, dict) or set(params) - allowed or
            allowed - OPTIONAL.get(data["method"], set()) - set(params)):
        raise ValueError("Invalid method parameters")
    if "researchId" in METHODS[data["method"]] and (
        not isinstance(params.get("researchId"), str) or not re.fullmatch(r"research-[a-f0-9]{12}", params["researchId"])
    ):
        raise ValueError("Invalid research identifier")
    if "includeMaterials" in params and type(params["includeMaterials"]) is not bool:
        raise ValueError("includeMaterials must be a boolean")
    for name in ("offset", "limit"):
        if name in params and type(params[name]) is not int:
            raise ValueError("Material bounds must be integers")
    if (("offset" in params and params["offset"] < 0) or
            ("limit" in params and not 1 <= params["limit"] <= 32000)):
        raise ValueError("Material bounds are outside the declared limit")
    for name in ("goal", "area", "name", "artifactId", "source"):
        if name in params and not isinstance(params[name], str):
            raise ValueError("Text parameters must be strings")
    for name in ("value", "review", "receipt"):
        if name in params and not isinstance(params[name], dict):
            raise ValueError("Submissions must be JSON objects")
    if "files" in params and (not isinstance(params["files"], list) or not 1 <= len(params["files"]) <= 8 or
            any(not isinstance(item, dict) or set(item) != {"name", "contentBase64"} or
                not isinstance(item["name"], str) or not isinstance(item["contentBase64"], str) for item in params["files"])):
        raise ValueError("Supporting files require one to eight name/contentBase64 objects")
    if "queries" in params and (not isinstance(params["queries"], list) or not 1 <= len(params["queries"]) <= 4 or
            any(not isinstance(value, str) or not 8 <= len(value.strip()) <= 1000 for value in params["queries"])):
        raise ValueError("Authoring queries require one to four substantive bounded strings")
    if "selectedSources" in params and (not isinstance(params["selectedSources"], list) or
            not 1 <= len(params["selectedSources"]) <= 6 or any(not isinstance(value, dict) for value in params["selectedSources"])):
        raise ValueError("Select one to six authoring source passages")
    return data


def public_error(error: Exception) -> dict:
    if isinstance(error, WorkflowError):
        return {"code": error.code, "message": _diagnostic(error)}
    if isinstance(error, ValidationError):
        issues = error.errors(include_input=False, include_context=False, include_url=False)[:12]
        return {"code": "INVALID_ARGUMENT", "message": _diagnostic("; ".join(
            f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']} ({issue['type']})" for issue in issues))}
    if isinstance(error, ValueError):
        return {"code": "INVALID_ARGUMENT", "message": _diagnostic(error)}
    if isinstance(error, (KeyError, TypeError)):
        return {"code": "INVALID_ARGUMENT", "message": "Request or research submission did not satisfy the declared contract."}
    return {"code": "ENGINE_ERROR", "message": "The local engine operation failed. Retained evidence has been preserved."}


class Dispatcher:
    def __init__(self, runtime, output):
        self.runtime = runtime
        self.service = runtime.service
        self.output = output
        self._write_lock = threading.Lock()
        self._event_lock = threading.Lock()
        self._cancel_events = {}
        self._stopping = threading.Event()
        self._pending = threading.BoundedSemaphore(MAX_QUEUED_REQUESTS)
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="paperfactory-ipc")
        self._active_ids = set()
        self._recent_ids = deque(maxlen=MAX_RECENT_IDS)

    def write(self, value):
        raw = (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        if len(raw) > MAX_OUTPUT_BYTES:
            raw = (json.dumps({"id": value.get("id"), "ok": False,
                "error": {"code": "OUTPUT_TOO_LARGE", "message": "IPC result exceeds its byte limit."}}) + "\n").encode()
        with self._write_lock:
            try:
                self.output.write(raw)
                self.output.flush()
            except (OSError, ValueError):
                self.stop()
                raise

    def submit(self, data):
        identifier, method, params = data["id"], data["method"], data["params"]
        with self._event_lock:
            duplicate = identifier in self._active_ids or identifier in self._recent_ids
        if duplicate:
            self.write({"id": identifier, "ok": False, "error": {"code": "DUPLICATE_REQUEST", "message": "Request identifier was already used."}})
            return
        if method == "workflow.cancel":
            with self._event_lock:
                for event in self._cancel_events.get(params["researchId"], []):
                    event.set()
        if method == "shutdown":
            self.stop()
        if not self._pending.acquire(blocking=False):
            self.write({"id": identifier, "ok": False, "error": {"code": "ENGINE_BUSY", "message": "IPC request queue is full."}})
            return
        with self._event_lock:
            self._active_ids.add(identifier)
        event = threading.Event()
        research_id = params.get("researchId")
        if research_id and method != "workflow.cancel":
            with self._event_lock:
                self._cancel_events.setdefault(research_id, []).append(event)
        deadline = time.monotonic() + SHUTDOWN_CLEANUP_SECONDS if method == "shutdown" else None
        return self._pool.submit(self._run, data, event, deadline)

    def _run(self, data, event, deadline):
        identifier, method, params = data["id"], data["method"], data["params"]
        try:
            if method not in SHUTDOWN_ALLOWED and (event.is_set() or self._stopping.is_set()):
                raise WorkflowError("CANCELLED", "Queued engine request was cancelled")
            self.runtime.set_cancel(lambda: event.is_set() or self._stopping.is_set())
            result = self.execute(method, params, deadline=deadline)
            self.write({"id": identifier, "ok": True, "result": result})
            return method == "shutdown"
        except Exception as error:
            self.write({"id": identifier, "ok": False, "error": public_error(error)})
            return False
        finally:
            research_id = params.get("researchId")
            if research_id and method != "workflow.cancel":
                with self._event_lock:
                    events = self._cancel_events.get(research_id, [])
                    if event in events:
                        events.remove(event)
                    if not events:
                        self._cancel_events.pop(research_id, None)
            self._pending.release()
            with self._event_lock:
                self._active_ids.discard(identifier)
                self._recent_ids.append(identifier)

    def execute(self, method, p, *, deadline=None):
        if method == "runtime.status":
            return self.runtime.runner.status()
        if method == "workflow.create":
            source, goal = p["source"], p["goal"]
            if not isinstance(source, str) or not re.fullmatch(r"https://github\.com/[A-Za-z0-9-]{1,39}/[A-Za-z0-9_.-]{1,100}/?", source):
                raise ValueError("Research input must be a public GitHub repository URL")
            return self.service.create(source.rstrip("/"), goal)
        if method == "workflow.list":
            records = []
            for path in sorted(self.service.root.iterdir()):
                if re.fullmatch(r"research-[a-f0-9]{12}", path.name):
                    # Interrupted imports may have no committed workflow yet.
                    if not path.is_dir() or not (path / "records.sqlite3").is_file():
                        continue
                    ensure_unlinked(path)
                    ws = Workspace(path)
                    if not ws.list("workflow", Workflow):
                        continue
                    with self.service._operation(path.name, during_shutdown=True) as (ws, record):
                        records.append(self.service._public(ws, record, include_materials=False))
                    if len(records) >= 100:
                        break
            return records
        if method == "workflow.status":
            return self.service.status(p["researchId"], include_materials=p.get("includeMaterials", True))
        if method == "workflow.readMaterial":
            return self.service.read_material(p["researchId"], p["area"], p["name"], offset=p.get("offset", 0), limit=p.get("limit", 16000))
        if method == "workflow.addEvidence":
            return self.service.add_evidence(p["researchId"], p["files"])
        if method == "workflow.submitProposal":
            if not isinstance(p["value"], dict) or p["value"].get("runtime") != "quickjs":
                raise ValueError("Standalone research supports QuickJS only")
            return self.service.submit_proposal(p["researchId"], p["value"])
        if method == "workflow.submitStudyReview":
            return self.service.submit_study_review(p["researchId"], p["review"])
        if method == "workflow.collectAuthoringLiterature":
            return self.service.collect_authoring_literature(p["researchId"], p["queries"])
        if method == "workflow.selectAuthoringLiterature":
            return self.service.select_authoring_literature(p["researchId"], p["selectedSources"])
        if method == "workflow.submitCode":
            if not isinstance(p["value"], dict) or p["value"].get("runtime") != "quickjs":
                raise ValueError("Standalone research supports QuickJS only")
            return self.service.submit_code(p["researchId"], p["value"], p["review"])
        if method == "workflow.submitManuscript":
            return self.service.submit_manuscript(p["researchId"], p["value"], p["review"])
        if method == "workflow.recordInference":
            return self.service.record_inference(p["researchId"], p["receipt"])
        if method == "artifact.resolve":
            if not isinstance(p["artifactId"], str) or not 1 <= len(p["artifactId"]) <= 200:
                raise ValueError("Invalid artifact identifier")
            return self.service.resolve_artifact(p["researchId"], p["artifactId"])
        if method == "shutdown":
            self.runtime.close(deadline=deadline)
            return {"closed": True}
        operation = {"workflow.collectLiterature": self.service.collect_literature,
                     "workflow.startExperiment": self.service.start_experiment,
                     "workflow.resume": self.service.resume,
                     "workflow.reviseWriting": self.service.revise_writing,
                     "workflow.redesignStudy": self.service.redesign_study,
                     "workflow.improveWriting": self.service.improve_writing,
                     "workflow.cancel": self.service.cancel, "workflow.export": self.service.export}[method]
        return operation(p["researchId"])

    def stop(self):
        self._stopping.set()
        with self._event_lock:
            for events in self._cancel_events.values():
                for event in events:
                    event.set()

    def finish(self):
        self.stop()
        self._pool.shutdown(wait=True)
        self.runtime.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("home", "runtime-root", "node", "pandoc"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args(argv)
    output = sys.stdout.buffer
    dispatcher = None
    runtime = None
    failed = False
    try:
        with redirect_stdout(sys.stderr):
            runtime = StandaloneRuntime(args.home, args.runtime_root, args.node, args.pandoc)
            dispatcher = Dispatcher(runtime, output)
            for raw in iter(lambda: sys.stdin.buffer.readline(MAX_INPUT_BYTES + 1), b""):
                try:
                    data = request(raw)
                    submitted = dispatcher.submit(data)
                    if data["method"] == "shutdown" and submitted is not None and submitted.result():
                        break
                except Exception as error:
                    identifier = None
                    try:
                        malformed = loads_json(raw)
                        candidate = malformed.get("id") if isinstance(malformed, dict) else None
                        if isinstance(candidate, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", candidate):
                            identifier = candidate
                    except Exception:
                        pass
                    dispatcher.write({"id": identifier, "ok": False, "error": public_error(error)})
                    if len(raw) > MAX_INPUT_BYTES:
                        dispatcher.stop()
                        break
    except Exception as error:
        failed = True
        try:
            raw = json.dumps({"id": None, "ok": False, "error": public_error(error)}) + "\n"
            output.write(raw.encode())
            output.flush()
        except (OSError, ValueError):
            pass
    finally:
        with redirect_stdout(sys.stderr):
            try:
                if dispatcher is not None:
                    if failed:
                        dispatcher.stop()
                    dispatcher.finish()
                elif runtime is not None:
                    runtime.close()
            except Exception as error:
                failed = True
                try:
                    output.write((json.dumps({"id": None, "ok": False, "error": public_error(error)}) + "\n").encode())
                    output.flush()
                except (OSError, ValueError):
                    pass
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())

"""Explicitly bound Chromium workers supervised by private Windows Jobs.

Chromium's renderer policy belongs to the trusted desktop worker. A Job bounds
and terminates the process tree; it is not a filesystem or network sandbox.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import threading
import time
import uuid
from urllib.parse import quote

from ..workspace import ensure_unlinked, file_lock, loads_json, write_json
from . import windows_runtime
from .runner_common import MAX_ARTIFACT_BYTES, MAX_LOG_BYTES, _production_calls, _retain_observations, _safe_tree


PROTOCOL = "paper-factory-chromium-v1"
JOURNAL = "paper-factory-chromium-supervisor-v1"
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_REQUEST_BYTES = 24 * 1024 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
LIMITS = {"artifact_bytes": MAX_ARTIFACT_BYTES, "log_bytes": MAX_LOG_BYTES,
          "request_bytes": MAX_REQUEST_BYTES, "response_frame_bytes": MAX_RESPONSE_BYTES,
          "generated_bundle_bytes": 512 * 1024, "observation_bytes": MAX_ARTIFACT_BYTES,
          "fixture_count": 4096, "trusted_call_and_fixture_record_bytes": 4 * 1024 * 1024,
          "json_nodes": 100000, "json_depth": 32, "startup_timeout_seconds": 15,
          "gate_json_bytes": 1024 * 1024, "production_dispatches": 65536,
          "source_and_scientific_input_bytes": MAX_SOURCE_BYTES, "scientific_inputs": 28,
          "frozen_script_and_scientific_input_bytes": MAX_SOURCE_BYTES,
          "scientific_input_reads": 512, "scientific_input_read_bytes": MAX_SOURCE_BYTES,
          "native_job_memory_bytes": 1024 * 1024 * 1024, "native_job_processes": 16,
          "network": "denied by trusted Chromium worker", "host_filesystem": "not exposed to guests",
          "native_host_rss_limit_claimed": False}
BRIDGE = "controller-held-chromium-call-gate"


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path, limit: int) -> bytes:
    ensure_unlinked(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError("Input must be a bounded, unlinked regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("Input exceeds byte boundary")
        return raw
    finally:
        os.close(descriptor)


def _relative(value: str, extensions: set[str]) -> str:
    if (type(value) is not str or not value or len(value) > 256 or "\\" in value or ":" in value
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError("Module path must be a bounded relative path")
    path = PurePosixPath(value)
    if (path.is_absolute() or any(part in {".", ".."} for part in path.parts)
            or path.as_posix() != value or path.suffix not in extensions):
        raise ValueError("Module must be an original declared JavaScript file")
    return value


def _text(path: Path, limit: int) -> dict:
    raw = _read(path, limit)
    text = raw.decode("utf-8", "strict")
    if "\0" in text:
        raise ValueError("Frozen code contains unsupported NUL text")
    return {"text": text, "sha256": _hash(raw)}


def _inputs(value: dict | None, source_bytes: int) -> dict:
    if source_bytes > MAX_SOURCE_BYTES:
        raise ValueError("Frozen source and generated modules exceed byte boundary")
    value = {} if value is None else value
    if type(value) is not dict or len(value) > LIMITS["scientific_inputs"]:
        raise ValueError("Scientific input map exceeds type or count boundary")
    total = source_bytes
    for key, record in value.items():
        if (type(key) is not str or type(record) is not dict or set(record) != {"name", "text", "sha256"}
                or any(type(record[field]) is not str for field in record)):
            raise ValueError("Scientific input requires exact name, text and SHA-256 fields")
        name, text, digest = (record[field] for field in ("name", "text", "sha256"))
        path = PurePosixPath(name)
        if (not name or len(name) > 256 or path.is_absolute() or path.as_posix() != name
                or "\\" in name or ":" in name or any(part in {".", ".."} for part in path.parts)
                or any(ord(c) < 32 or ord(c) == 127 for c in name)):
            raise ValueError("Scientific input name escapes the frozen input")
        if key != "source/" + name and not (re.fullmatch(r"supporting-document-[a-f0-9]{12}", key) and len(path.parts) == 1):
            raise ValueError("Scientific input key must identify frozen source or a supporting document")
        raw = text.encode("utf-8", "strict")
        if "\0" in text or not re.fullmatch(r"[a-f0-9]{64}", digest) or _hash(raw) != digest:
            raise ValueError("Scientific input bytes differ or contain unsupported text")
        total += len(raw)
        if total > MAX_SOURCE_BYTES:
            raise ValueError("Frozen source and scientific inputs exceed byte boundary")
    return value


class BrowserRunner:
    """Run original classic scripts and async generated modules in Chromium."""

    def __init__(self, binding: dict, *, supervisor_root: Path):
        if (type(binding) is not dict or not {"executable", "worker", "assets"} <= set(binding)
                or set(binding) - {"executable", "worker", "assets", "app_entry"}
                or type(binding["assets"]) is not list or len(binding["assets"]) > 16):
            raise ValueError("Chromium runtime requires explicit file bindings")
        self.binding = json.loads(json.dumps(binding, allow_nan=False))
        records = [binding["executable"], binding["worker"], *binding["assets"]]
        if binding.get("app_entry") is not None:
            records.append(binding["app_entry"])
        paths = set()
        for record in records:
            if (type(record) is not dict or set(record) != {"path", "size", "sha256"}
                    or type(record["path"]) is not str or not Path(record["path"]).is_absolute()
                    or type(record["size"]) is not int or not 0 < record["size"] <= 256 * 1024 * 1024
                    or not re.fullmatch(r"[a-f0-9]{64}", str(record["sha256"]))):
                raise ValueError("Chromium runtime binding must identify absolute regular file bytes")
            identity = os.path.normcase(str(Path(record["path"]).absolute()))
            # app_entry may deliberately be the standalone worker in development.
            if identity in paths and record != binding["worker"]:
                raise ValueError("Duplicate Chromium runtime file binding")
            paths.add(identity)
        self.supervisor_root = Path(supervisor_root).absolute()
        ensure_unlinked(self.supervisor_root)
        supervisor = self.supervisor_root.resolve()
        for record in records:
            path = Path(record["path"]).resolve()
            if path == supervisor or supervisor in path.parents:
                raise ValueError("Supervisor scratch must be separate from immutable runtime assets")
        self.supervisor_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._journal_path = self.supervisor_root / "owned-workers.json"
        self._mutex = threading.RLock()
        self._probe_lock = threading.Lock()
        self._active: dict[str, dict] = {}
        self._lease = None
        self._records = self._load_journal()

    def _runtime(self) -> dict:
        records = [self.binding["executable"], self.binding["worker"], *self.binding["assets"]]
        if self.binding.get("app_entry") is not None:
            records.append(self.binding["app_entry"])
        for record in records:
            raw = _read(Path(record["path"]), 256 * 1024 * 1024)
            if len(raw) != record["size"] or _hash(raw) != record["sha256"]:
                raise ValueError("Configured Chromium runtime file bytes changed")
        return {"file_bindings": self.binding, "binding_scope": "explicit configured files only",
                "entire_electron_binary_closure_verified": False,
                "supervision": {"mechanism": "windows-job", "source_sha256":
                                _hash(_read(Path(windows_runtime.__file__), 128 * 1024))}}

    def _load_journal(self) -> dict:
        try:
            value = loads_json(_read(self._journal_path, 64 * 1024))
        except FileNotFoundError:
            return {}
        if (type(value) is not dict or value.get("format") != JOURNAL
                or type(value.get("workers")) is not list or len(value["workers"]) > 8):
            raise ValueError("Invalid Chromium supervisor journal")
        records = {}
        for record in value["workers"]:
            if (type(record) is not dict or record.get("phase") not in {"starting", "running", "unresolved"}
                    or record.get("purpose") not in {"probe", "experiment"}):
                raise ValueError("Invalid Chromium supervisor worker record")
            handle = record.get("handle")
            nonce = handle.get("owner_nonce") if type(handle) is dict else None
            if not re.fullmatch(r"[a-f0-9]{32}", str(nonce)) or nonce in records:
                raise ValueError("Invalid Chromium supervisor worker identity")
            records[nonce] = record
        return records

    def _persist(self) -> None:
        if self._lease is None:
            raise ValueError("Supervisor journal mutation requires its owner lease")
        value = {"format": JOURNAL, "workers": list(self._records.values())}
        if len(self._records) > 8 or len(json.dumps(value).encode()) > 64 * 1024:
            raise ValueError("Supervisor worker boundary exceeded")
        write_json(self._journal_path, value)

    def _release(self) -> None:
        if self._lease is not None and not self._active:
            lease, self._lease = self._lease, None
            lease.__exit__(None, None, None)

    def _prepare(self) -> bool:
        with self._mutex:
            if self._lease is None:
                lease = file_lock(self.supervisor_root / "supervisor.lock")
                lease.__enter__()
                self._lease = lease
                self._records = self._load_journal()
            for nonce, record in list(self._records.items()):
                if nonce in self._active:
                    if record["phase"] == "unresolved":
                        return False
                    continue
                if not self._recover(record["handle"]):
                    self._release()
                    return False
                self._records.pop(nonce)
                self._persist()
            return True

    def _pending(self) -> dict:
        with self._mutex:
            return next((dict(record["handle"]) for nonce, record in self._records.items()
                         if record["phase"] == "unresolved" or nonce not in self._active), {})

    def _finish(self, nonce: str) -> None:
        with self._mutex:
            if nonce not in self._active and nonce not in self._records:
                return
            entry = self._active.pop(nonce, None)
            if entry:
                entry["job"].close()
            self._records.pop(nonce, None)
            self._persist()
            self._release()

    def _valid_handle(self, handle: dict) -> bool:
        nonce = handle.get("owner_nonce") if type(handle) is dict else None
        return (type(handle) is dict and handle.get("kind") == "chromium-worker"
                and type(handle.get("pid")) is int and handle["pid"] > 1
                and bool(re.fullmatch(r"[a-f0-9]{32}", str(nonce)))
                and handle.get("job_name") == "Local\\paper-factory-research-" + nonce
                and type(handle.get("start_ticks")) is int and handle["start_ticks"] > 0
                and handle.get("executable_path") == self.binding["executable"]["path"]
                and handle.get("executable_sha256") == self.binding["executable"]["sha256"]
                and handle.get("worker_path") == self.binding["worker"]["path"]
                and handle.get("worker_sha256") == self.binding["worker"]["sha256"]
                and handle.get("profile") == str(self.supervisor_root / "profiles" / nonce / "browser"))

    def _recover(self, handle: dict) -> bool:
        if os.name != "nt" or not self._valid_handle(handle):
            return False
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if windows_runtime.stop(handle):
                return True
            time.sleep(0.02)
        return False

    def stop(self, handle: dict) -> bool:
        if not self._valid_handle(handle):
            return False
        with self._mutex:
            entry = self._active.get(handle["owner_nonce"])
            if entry:
                return handle == entry["handle"] and entry["job"].stop()
            try:
                if self._lease is None:
                    lease = file_lock(self.supervisor_root / "supervisor.lock")
                    lease.__enter__()
                    self._lease = lease
                    self._records = self._load_journal()
                record = self._records.get(handle["owner_nonce"])
                if record and record["handle"] != handle:
                    return False
                cleaned = self._recover(handle)
                if cleaned:
                    self._finish(handle["owner_nonce"])
                return cleaned
            except (OSError, ValueError, KeyError, TypeError):
                return False
            finally:
                self._release()

    def close(self, *, deadline: float | None = None) -> None:
        with self._mutex:
            if self._lease is None:
                lease = file_lock(self.supervisor_root / "supervisor.lock")
                lease.__enter__()
                self._lease = lease
                self._records = self._load_journal()
            handles = [dict(record["handle"]) for record in self._records.values()]
        for handle in handles:
            if deadline is not None and deadline - time.monotonic() < 10:
                raise ValueError("Owned Chromium cleanup exceeded the shutdown deadline")
            if self.stop(handle):
                self._finish(handle["owner_nonce"])
        with self._mutex:
            if self._records:
                raise ValueError("Owned Chromium cleanup remains unconfirmed")
            self._release()

    @staticmethod
    def _environment(profile: Path) -> dict:
        home = profile.parent / "home"
        temp = home / "temp"
        temp.mkdir(parents=True)
        result = {"PATH": "", "HOME": str(home), "USERPROFILE": str(home), "APPDATA": str(home),
                  "LOCALAPPDATA": str(home), "TEMP": str(temp), "TMP": str(temp), "TMPDIR": str(temp)}
        for key in ("SystemRoot", "WINDIR"):
            if key in os.environ:
                result[key] = os.environ[key]
        return result

    def _execute(self, request: dict, *, cancel=None, on_handle=None, purpose="experiment") -> dict:
        if os.name != "nt":
            raise ValueError("Chromium process supervision currently requires Windows")
        started, nonce = time.monotonic(), uuid.uuid4().hex
        request = {**request, "protocol": PROTOCOL, "command": "GO", "nonce": nonce}
        payload = json.dumps(request, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
        if len(payload) > MAX_REQUEST_BYTES:
            raise ValueError("Trusted request exceeds byte boundary")
        profile = self.supervisor_root / "profiles" / nonce / "browser"
        handle = {"kind": "chromium-worker", "pid": 0, "owner_nonce": nonce,
                  "profile": str(profile), "executable_path": self.binding["executable"]["path"],
                  "executable_sha256": self.binding["executable"]["sha256"],
                  "worker_path": self.binding["worker"]["path"], "worker_sha256": self.binding["worker"]["sha256"]}
        process = job = None
        assigned = False
        streams = {"stdout": bytearray(), "stderr": bytearray()}
        preamble = []
        overflow, startup, bad_startup = (threading.Event() for _ in range(3))
        feed_done = threading.Event()
        threads = []
        reason = None
        feed_errors = []
        cleaned, forced_stop = False, None
        try:
            with self._mutex:
                if not self._prepare():
                    raise ValueError("Unresolved owned worker blocks another spawn")
                ensure_unlinked(profile)
                profile.mkdir(parents=True, exist_ok=False, mode=0o700)
                environment = self._environment(profile)
                self._records[nonce] = {"phase": "starting", "purpose": purpose, "handle": dict(handle)}
                self._persist()
                job = windows_runtime.WindowsJob(name="Local\\paper-factory-research-" + nonce,
                        limits={"memory_bytes": LIMITS["native_job_memory_bytes"], "pids": LIMITS["native_job_processes"]})
                command = [self.binding["executable"]["path"]]
                if self.binding.get("app_entry") is not None:
                    command.append(self.binding["app_entry"]["path"])
                command += ["--paper-factory-chromium-worker", "--worker", self.binding["worker"]["path"], "--profile", str(profile)]
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        env=environment, cwd=profile, close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)
                handle["pid"] = process.pid
                self._active[nonce] = {"process": process, "job": job, "handle": handle}
                job.assign(process._handle)
                assigned = True
                ticks = windows_runtime.process_ticks(process.pid)
                if type(ticks) is not int or ticks <= 0:
                    raise ValueError("Owned Chromium creation time is unavailable")
                handle.update(job_name=job.name, start_ticks=ticks)
                self._records[nonce] = {"phase": "running", "purpose": purpose, "handle": dict(handle)}
                self._persist()
            if on_handle:
                on_handle(dict(handle))

            def drain_stdout():
                try:
                    line = process.stdout.readline(4097)
                    # This configured Windows Electron build writes one CRLF
                    # before the first JSON line when stdout is a pipe.
                    if line == b"\r\n":
                        preamble.append("electron-win32-crlf")
                        line = process.stdout.readline(4097)
                    try:
                        valid = len(line) <= 4096 and line.endswith(b"\n") and loads_json(line) == {"protocol": PROTOCOL, "phase": "awaiting-go"}
                    except (ValueError, UnicodeError):
                        valid = False
                    if not valid:
                        streams["stdout"].extend(line[:MAX_RESPONSE_BYTES])
                        bad_startup.set()
                        return
                    startup.set()
                    while part := process.stdout.read1(65536):
                        room = max(0, MAX_RESPONSE_BYTES - len(streams["stdout"]))
                        streams["stdout"].extend(part[:room])
                        if len(part) > room:
                            overflow.set()
                            return
                except (OSError, ValueError, UnicodeError):
                    bad_startup.set()
                finally:
                    process.stdout.close()

            def drain_stderr():
                try:
                    while part := process.stderr.read1(65536):
                        room = max(0, MAX_LOG_BYTES - len(streams["stderr"]))
                        streams["stderr"].extend(part[:room])
                        if len(part) > room:
                            overflow.set()
                            return
                finally:
                    process.stderr.close()

            def feed():
                try:
                    process.stdin.write(payload)
                    process.stdin.flush()
                except (BrokenPipeError, OSError, ValueError) as exc:
                    feed_errors.append(type(exc).__name__)
                finally:
                    process.stdin.close()
                    feed_done.set()

            threads = [threading.Thread(target=drain_stdout, daemon=True), threading.Thread(target=drain_stderr, daemon=True)]
            for thread in threads:
                thread.start()
            fed = False
            while process.poll() is None:
                if cancel and cancel():
                    reason = "cancelled"
                    break
                if overflow.is_set() or bad_startup.is_set():
                    reason = "overflow" if overflow.is_set() else "invalid startup frame"
                    break
                if time.monotonic() - started > request["timeout_seconds"] + 3:
                    reason = "timeout"
                    break
                if not feed_done.is_set() and time.monotonic() - started > 15:
                    reason = "startup timeout"
                    break
                if startup.is_set() and not fed:
                    fed = True
                    thread = threading.Thread(target=feed, daemon=True)
                    threads.append(thread)
                    thread.start()
                time.sleep(0.02)
        except Exception as exc:
            reason = "controller failure: " + type(exc).__name__
        finally:
            if process is None:
                if job is not None:
                    job.close()
                self._finish(nonce)
                with self._mutex:
                    self._release()
                cleaned = not bool(self._pending())
            else:
                # Terminate even a naturally exited parent: descendants and pipe
                # writers can otherwise survive the trusted Electron main.
                forced_stop = job.stop() if job is not None else False
                if not assigned:
                    # No GO was sent. Terminate only the exact Popen capability
                    # if Job assignment failed; never signal a recovered PID.
                    try:
                        if process.poll() is None:
                            process.terminate()
                    except OSError:
                        forced_stop = False
                try:
                    process.wait(timeout=5)
                    for thread in threads:
                        thread.join(timeout=2)
                    cleaned = forced_stop and all(not thread.is_alive() for thread in threads)
                    if cleaned:
                        for pipe in (process.stdin, process.stdout, process.stderr):
                            pipe.close()
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    cleaned = False
                if cleaned:
                    self._finish(nonce)
                else:
                    with self._mutex:
                        self._records[nonce] = {"phase": "unresolved", "purpose": purpose, "handle": dict(handle)}
                        self._persist()
        if overflow.is_set() and reason is None:
            reason = "overflow"
        envelope = None
        if not reason and not overflow.is_set():
            try:
                if not startup.is_set() or bad_startup.is_set():
                    raise ValueError("Missing startup acknowledgement")
                envelope = loads_json(bytes(streams["stdout"]).decode("utf-8", "strict"))
                if (type(envelope) is not dict or envelope.get("protocol") != PROTOCOL
                        or envelope.get("phase") != "result" or envelope.get("nonce") != nonce):
                    raise ValueError("Invalid worker result identity")
            except (ValueError, UnicodeError):
                reason = "invalid worker response"
        if cleaned and profile.is_dir():
            # Only the exact random directory created above can be removed.
            ensure_unlinked(profile)
            if profile.resolve() != self.supervisor_root.resolve() / "profiles" / nonce / "browser":
                raise ValueError("Owned profile path changed")
            try:
                ensure_unlinked(profile.parent)
                shutil.rmtree(profile.parent)
            except OSError:
                reason = reason or "owned profile removal failed"
        return {"exit_code": process.returncode if process else None, "envelope": envelope,
                "cleanup_confirmed": cleaned, "active_handle": {} if cleaned else handle,
                "reason": reason, "forced_stop_confirmed": forced_stop,
                "raw_response": bytes(streams["stdout"]),
                "startup_preamble": preamble,
                "input_transport_errors": feed_errors,
                "stderr": bytes(streams["stderr"]).decode("utf-8", "replace"),
                "duration_seconds": round(time.monotonic() - started, 3)}

    def _packet(self, source: Path, bundle: Path, *, source_order: list[str], entrypoint: str,
                production_entrypoint: str, scientific_inputs: dict | None, timeout_seconds: int) -> dict:
        if (type(source_order) is not list or not 1 <= len(source_order) <= 20
                or any(type(name) is not str for name in source_order)
                or len(set(source_order)) != len(source_order)):
            raise ValueError("Chromium requires a unique ordered production script list")
        source_files, total = {}, 0
        for name in source_order:
            _relative(name, {".js"})
            item = _text(source / name, MAX_SOURCE_BYTES)
            total += len(item["text"].encode("utf-8"))
            if total > MAX_SOURCE_BYTES:
                raise ValueError("Original production scripts exceed byte boundary")
            source_files[name] = item
        selected, separator, function = production_entrypoint.rpartition(":")
        if (not separator or selected != source_order[-1]
                or len(function) > 128
                or not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*", function)):
            raise ValueError("Production entrypoint must identify the last original classic script's callable")
        _relative(entrypoint, {".js", ".mjs"})
        experiment_files, size, count = {}, 0, 0
        for path in sorted(bundle.rglob("*")):
            if not path.is_file():
                continue
            if path.relative_to(bundle).as_posix() in {"bundle.json", "review.json"}:
                continue
            name = _relative(path.relative_to(bundle).as_posix(), {".js", ".mjs", ".json", ".md", ".txt"})
            item = _text(path, 512 * 1024)
            size += len(item["text"].encode("utf-8"))
            count += 1
            if count > 12 or size > 512 * 1024:
                raise ValueError("Generated experiment exceeds byte or file boundary")
            if path.suffix in {".js", ".mjs"}:
                experiment_files[name] = item
        if entrypoint not in experiment_files:
            raise ValueError("Generated entrypoint is absent from frozen inventory")
        inputs = _inputs(scientific_inputs, total + size)
        for name, item in source_files.items():
            supplied = inputs.get("source/" + name)
            if supplied is not None and (supplied["text"] != item["text"] or supplied["sha256"] != item["sha256"]):
                raise ValueError("Scientific source input differs from original production bytes")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 3600:
            raise ValueError("Experiment timeout must be between one and 3600 seconds")
        return {"source_files": source_files, "source_order": source_order, "experiment_files": experiment_files,
                "entrypoint": entrypoint, "production_entrypoint": production_entrypoint,
                "scientific_inputs": inputs, "timeout_seconds": timeout_seconds}

    @staticmethod
    def _verify_manifest(envelope: dict, request: dict) -> dict:
        manifest = envelope.get("runtime_manifest")
        if (type(manifest) is not dict or manifest.get("backend") != "chromium-sandbox"
                or manifest.get("bridge") != BRIDGE or manifest.get("production_entrypoint") != request["production_entrypoint"]
                or manifest.get("source_order") != request["source_order"]
                or envelope.get("coverage_truncated") is not False or envelope.get("coverage_mechanism") != BRIDGE
                or any(manifest.get(key) is not True for key in ("distinct_renderer_processes", "separate_nonpersistent_sessions",
                        "sandboxed", "network_denied", "shutdown_windows_closed"))
                or manifest.get("node_integration") is not False):
            raise ValueError("Trusted Chromium boundary receipt is incomplete")
        proxy = manifest.get("owned_deny_proxy")
        if (type(proxy) is not dict or set(proxy) != {"host", "port", "denied_connections", "close_requested", "close_callback_confirmed"}
                or proxy.get("host") != "127.0.0.1" or type(proxy.get("port")) is not int or not 1 <= proxy["port"] <= 65535
                or type(proxy.get("denied_connections")) is not int or not 0 <= proxy["denied_connections"] <= 1_000_000_000
                or proxy.get("close_requested") is not True or type(proxy.get("close_callback_confirmed")) is not bool):
            raise ValueError("Chromium owned network-denial proxy receipt is incomplete")
        for kind, digest in (("source_files", "original_sha256"), ("experiment_files", "sha256")):
            expected = {name: {digest: item["sha256"], "size": len(item["text"].encode("utf-8"))}
                        for name, item in request[kind].items()}
            actual = manifest.get(kind)
            if (actual != expected or type(actual) is not dict
                    or any(type(item) is not dict or type(item.get("size")) is not int for item in actual.values())):
                raise ValueError("Chromium executed-file manifest differs from frozen bytes")
        expected = {key: {"name": value["name"], "sha256": value["sha256"], "size": len(value["text"].encode("utf-8"))}
                    for key, value in request["scientific_inputs"].items()}
        actual = manifest.get("scientific_inputs")
        if (actual != expected or type(actual) is not dict
                or any(type(item) is not dict or type(item.get("size")) is not int for item in actual.values())):
            raise ValueError("Chromium scientific-input manifest differs from frozen bytes")
        input_bytes = sum(item["size"] for item in expected.values())
        if type(manifest.get("scientific_input_bytes")) is not int or manifest["scientific_input_bytes"] != input_bytes:
            raise ValueError("Chromium scientific-input byte total differs")
        for key, maximum in (("production_dispatch_attempts", LIMITS["production_dispatches"]),
                             ("production_completed_calls", LIMITS["production_dispatches"]),
                             ("fixture_count", 4096), ("fixture_bytes", MAX_ARTIFACT_BYTES),
                             ("scientific_input_reads", LIMITS["scientific_input_reads"]),
                             ("scientific_input_read_bytes", LIMITS["scientific_input_read_bytes"])):
            if type(manifest.get(key)) is not int or not 0 <= manifest[key] <= maximum:
                raise ValueError("Chromium trusted receipt count exceeds integer or size boundary")
        attempts, completed = manifest["production_dispatch_attempts"], manifest["production_completed_calls"]
        calls = manifest.get("call_receipts")
        if type(calls) is not list or len(calls) != attempts or completed > attempts:
            raise ValueError("Chromium call receipts do not match dispatch counts")
        successes = 0
        for index, call in enumerate(calls, 1):
            common = {"index", "input_sha256", "input_bytes", "status"}
            if (type(call) is not dict or type(call.get("index")) is not int or call["index"] != index
                    or call.get("status") not in {"succeeded", "rejected"}
                    or type(call.get("input_bytes")) is not int or not 1 <= call["input_bytes"] <= LIMITS["gate_json_bytes"]
                    or not re.fullmatch(r"[a-f0-9]{64}", str(call.get("input_sha256")))):
                raise ValueError("Invalid Chromium production input receipt")
            if call["status"] == "succeeded":
                successes += 1
                if (set(call) != common | {"output_sha256", "output_bytes"}
                        or type(call.get("output_bytes")) is not int or not 1 <= call["output_bytes"] <= LIMITS["gate_json_bytes"]
                        or not re.fullmatch(r"[a-f0-9]{64}", str(call.get("output_sha256")))):
                    raise ValueError("Invalid Chromium production output receipt")
            elif set(call) != common:
                raise ValueError("Rejected Chromium call has unsupported output fields")
        if completed != successes:
            raise ValueError("Chromium completed-call count differs from call receipts")
        capabilities = manifest.get("renderer_capabilities")
        if (type(capabilities) is not dict or set(capabilities) != {"production", "experiment"}
                or any(type(value) is not dict or value.get("require") != "undefined" or value.get("process") != "undefined"
                       for value in capabilities.values())):
            raise ValueError("Chromium renderer Node absence is unverified")
        nonce = envelope.get("nonce")
        if not re.fullmatch(r"[a-f0-9]{32}", str(nonce)):
            raise ValueError("Chromium function provenance lacks owned request identity")
        origin = "pf-science://production-" + nonce + "/"
        loaded = manifest.get("loaded_source_scripts")
        if type(loaded) is not list or len(loaded) != len(request["source_order"]):
            raise ValueError("Chromium loaded-script inventory differs")
        for name, script in zip(request["source_order"], loaded):
            item = request["source_files"][name]
            if (type(script) is not dict or set(script) != {"path", "script_url", "script_id", "sha256", "size"}
                    or script.get("path") != name or script.get("script_url") != origin + quote(name, safe="/~.-_")
                    or type(script.get("script_id")) is not str or not 1 <= len(script["script_id"]) <= 256
                    or script.get("sha256") != item["sha256"] or type(script.get("size")) is not int
                    or script["size"] != len(item["text"].encode("utf-8"))):
                raise ValueError("Chromium parsed script differs from the original production bytes")
        selected = loaded[-1]
        provenance = manifest.get("function_provenance")
        expected_provenance = {"script_url": selected["script_url"], "script_id": selected["script_id"],
                               "script_sha256": selected["sha256"], "size": selected["size"]}
        if provenance != expected_provenance or type(provenance.get("size")) is not int:
            raise ValueError("Chromium selected function is not bound to its parsed original script")
        fixtures = manifest.get("retained_fixtures")
        if type(fixtures) is not list or len(fixtures) != manifest["fixture_count"]:
            raise ValueError("Chromium fixture count differs from trusted retained bytes")
        labels, total = set(), 0
        for fixture in fixtures:
            if (type(fixture) is not dict or set(fixture) != {"label", "encoding", "content", "sha256"}
                    or type(fixture.get("label")) is not str or not 1 <= len(fixture["label"]) <= 200
                    or any(ord(c) < 32 or ord(c) == 127 for c in fixture["label"])
                    or fixture["label"] in labels or fixture.get("encoding") != "base64"
                    or type(fixture.get("content")) is not str
                    or len(fixture["content"]) > (MAX_ARTIFACT_BYTES + 2) // 3 * 4):
                raise ValueError("Invalid Chromium retained fixture")
            labels.add(fixture["label"])
            raw = base64.b64decode(fixture["content"], validate=True)
            total += len(raw)
            if total > MAX_ARTIFACT_BYTES or fixture.get("sha256") != _hash(raw):
                raise ValueError("Chromium fixture bytes differ from trusted hash")
        if total != manifest["fixture_bytes"]:
            raise ValueError("Chromium fixture byte count differs")
        record_bytes = sum(len(json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                           for record in calls + fixtures)
        if record_bytes > LIMITS["trusted_call_and_fixture_record_bytes"]:
            raise ValueError("Chromium combined call and fixture record bytes exceed frame allocation")
        return manifest

    def _status_fields(self) -> dict:
        return {"ready": False, "runtimes": [], "backend": "chromium-sandbox", "reason": None,
                "dependencies": [], "versions": {}, "declared_limits": LIMITS.copy(),
                "recoverable_cleanup": False, "native_host_rss_limit_claimed": False,
                "binary_binding_scope": "explicit configured files only",
                "self_checks": {},
                "recovery_scope": "registered private Job and original process identity; incomplete starting markers block"}

    def status(self) -> dict:
        result, prepared = self._status_fields(), False
        if os.name != "nt":
            result.update(reason="Chromium process supervision currently requires Windows", cleanup_confirmed=True)
            return result
        with self._probe_lock:
            try:
                with self._mutex:
                    prepared = self._prepare()
                    if not prepared:
                        raise ValueError("Owned worker cleanup remains unresolved")
                runtime = self._runtime()
                source = 'const ctx=document.createElement("canvas").getContext("2d");window.J={measure(x){if(typeof process!=="undefined"||typeof require!=="undefined"||typeof readScientificInput!=="undefined")throw Error("host capability");if(x===null)throw Error("original rejection");return {value:x+1,width:ctx.measureText("가").width}}};'
                code = '''export default async function run(){
                  const original=callProduction;
                  const descriptor=Object.getOwnPropertyDescriptor(globalThis,"callProduction");
                  const immutable=descriptor.configurable===false;
                  const value=JSON.parse(await callProduction("[6]"));
                  let rejection=false;try{await callProduction("[null]")}catch(e){rejection=e.message.includes("original rejection")}
                  const input=JSON.parse(await readScientificInput("supporting-document-000000000000"));
                  const fixture=JSON.parse(await retainFixture("unicode","가"));
                  return {value,rejection,immutable:immutable&&callProduction===original,input,fixture,
                    noNode:typeof require==="undefined"&&typeof process==="undefined"};}'''
                input_text = "\ufeff가🙂\r\n"
                input_record = {"name": "check.md", "text": input_text, "sha256": _hash(input_text.encode())}
                packet = {"source_files": {"check.js": {"text": source, "sha256": _hash(source.encode())}},
                          "source_order": ["check.js"], "production_entrypoint": "check.js:J.measure",
                          "experiment_files": {"check.mjs": {"text": code, "sha256": _hash(code.encode())}},
                          "entrypoint": "check.mjs", "timeout_seconds": 10,
                          "scientific_inputs": {"supporting-document-000000000000": input_record}}
                receipt = self._execute(packet, purpose="probe")
                envelope = receipt.get("envelope") or {}
                if receipt["reason"] or not receipt["cleanup_confirmed"] or receipt["exit_code"] != 0 or envelope.get("status") != "succeeded":
                    raise ValueError("Actual Chromium boundary self-check failed")
                manifest = self._verify_manifest(envelope, packet)
                value = loads_json(base64.b64decode(envelope["observation_b64"], validate=True))
                if (value.get("value", {}).get("value") != 7 or not value["value"]["width"] > 0
                        or any(value.get(key) is not True for key in ("noNode", "rejection", "immutable"))
                        or value.get("input") != input_record
                        or envelope.get("production_calls") != [{"path": "check.js", "function": "J.measure", "calls": 2}]
                        or value.get("fixture", {}).get("sha256") != _hash("가".encode())
                        or base64.b64decode(value["fixture"]["content"], validate=True) != "가".encode()):
                    raise ValueError("Actual Chromium gate self-check failed")
                checks = {"canvas_and_held_call": True, "ordinary_production_rejection": True,
                          "no_node_in_renderers": True, "frozen_input_and_fixture": True}
                for name, body, error in (
                    ("caught_gate_replacement_rejected", 'try{globalThis.callProduction=()=>"forged"}catch{}', "Browser capability replacement"),
                    ("caught_fetch_rejected", 'try{await fetch("https://example.invalid/blocked")}catch{}', "Forbidden browser capability"),
                ):
                    negative_code = "export default async function run(){" + body + ";return {caught:true}}"
                    negative_packet = {**packet, "experiment_files": {"check.mjs": {
                        "text": negative_code, "sha256": _hash(negative_code.encode())}}, "scientific_inputs": {}}
                    negative = self._execute(negative_packet, purpose="probe")
                    failed = negative.get("envelope") or {}
                    if (negative["reason"] or not negative["cleanup_confirmed"] or negative["exit_code"] == 0
                            or failed.get("status") != "failed" or error not in str(failed.get("error", ""))):
                        raise ValueError("Actual Chromium caught boundary violation self-check failed")
                    self._verify_manifest(failed, negative_packet)
                    checks[name] = True
                kill_code = "export default async function run(){while(true){}}"
                kill_packet = {**packet, "experiment_files": {"check.mjs": {"text": kill_code, "sha256": _hash(kill_code.encode())}},
                               "scientific_inputs": {}, "timeout_seconds": 10}
                kill_started = time.monotonic()
                stopped = self._execute(kill_packet, purpose="probe", cancel=lambda: time.monotonic() - kill_started > 1)
                if stopped["reason"] != "cancelled" or not stopped["cleanup_confirmed"] or stopped["forced_stop_confirmed"] is not True:
                    raise ValueError("Owned Chromium termination self-check failed")
                checks["owned_tree_termination"] = True
                result.update(ready=True, runtimes=["chromium"], versions=manifest.get("versions", {}),
                              runtime_digest=_hash(json.dumps(runtime, sort_keys=True).encode()), recoverable_cleanup=True,
                              self_checks=checks)
            except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
                result.update(reason="Configured Chromium runtime or owned boundary self-check is unavailable",
                              diagnostic={"stage": "chromium-self-check", "exception_type": type(exc).__name__, "detail": str(exc)[:300]})
            finally:
                with self._mutex:
                    self._release()
            pending = self._pending()
            result["cleanup_confirmed"] = prepared and not bool(pending)
            if pending:
                result.update(ready=False, runtimes=[], code="CLEANUP_UNCONFIRMED", reason="Owned Chromium cleanup remains unconfirmed")
            return result

    def run(self, source_dir: Path, bundle_dir: Path, output_dir: Path, *, runtime: str, entrypoint: str,
            production_entrypoint: str, source_order: list[str], timeout_seconds: int = 300,
            scientific_inputs: dict | None = None, cancel=None, on_handle=None) -> dict:
        if runtime != "chromium":
            raise ValueError("Chromium runner only accepts runtime chromium")
        source, bundle = _safe_tree(Path(source_dir), "source"), _safe_tree(Path(bundle_dir), "bundle")
        packet = self._packet(source, bundle, source_order=source_order, entrypoint=entrypoint,
                              production_entrypoint=production_entrypoint, scientific_inputs=scientific_inputs,
                              timeout_seconds=timeout_seconds)
        output = Path(output_dir)
        ensure_unlinked(output)
        output = output.resolve()
        if output == source or source in output.parents or output == bundle or bundle in output.parents:
            raise ValueError("Output directory must be separate from source and bundle")
        output.mkdir(parents=True, exist_ok=True)
        if not output.is_dir() or any(output.iterdir()):
            raise ValueError("Output directory must be empty")
        result = {"status": "failed", "backend": "chromium-sandbox", "image_digest": None, "runtime_digest": None,
                  "command": ["chromium", entrypoint], "limits": {**LIMITS, "timeout_seconds": timeout_seconds},
                  "artifacts": [], "output_path": None, "stdout": "", "stderr": "", "exit_code": None,
                  "production_entrypoint": production_entrypoint, "production_calls": [], "coverage_truncated": False,
                  "coverage_mechanism": BRIDGE, "cleanup_confirmed": True, "active_handle": {}}
        if cancel and cancel():
            result["status"] = "cancelled"
            return result
        ready = self.status()
        if not ready["ready"]:
            result.update(stderr=ready["reason"], cleanup_confirmed=ready.get("cleanup_confirmed", False))
            if not result["cleanup_confirmed"]:
                result.update(status="blocked", code="CLEANUP_UNCONFIRMED", active_handle=self._pending())
            return result
        metadata = self._runtime()
        execution = self._execute(packet, cancel=cancel, on_handle=on_handle)
        result.update({key: execution[key] for key in ("exit_code", "cleanup_confirmed", "active_handle", "duration_seconds")})
        result["startup_preamble"] = execution.get("startup_preamble", [])
        raw_response = execution.get("raw_response", b"")
        if raw_response:
            path = output / "worker-response.json"
            with path.open("xb") as stream:
                stream.write(raw_response)
            result["artifacts"].append({"path": path.name, "size": len(raw_response), "sha256": _hash(raw_response)})
        if not execution["cleanup_confirmed"]:
            result.update(status="blocked", code="CLEANUP_UNCONFIRMED", stderr="Owned Chromium worker exit could not be confirmed")
            return result
        if execution["reason"]:
            result.update(status=execution["reason"] if execution["reason"] in {"cancelled", "timeout"} else "failed",
                          stderr="Bounded Chromium worker rejected: " + execution["reason"])
            return result
        envelope = execution.get("envelope") or {}
        try:
            encoded = envelope.get("observation_b64")
            if encoded is not None:
                if type(encoded) is not str or len(encoded) > (MAX_ARTIFACT_BYTES + 2) // 3 * 4:
                    raise ValueError("Oversized observation transport")
                retained = _retain_observations(output, base64.b64decode(encoded, validate=True))
                result["output_path"] = retained["output_path"]
                result["artifacts"].extend(retained["artifacts"])
            manifest = self._verify_manifest(envelope, packet)
            if envelope.get("status") == "succeeded":
                observed = loads_json(Path(result["output_path"]).read_bytes()) if result["output_path"] else None
                if type(observed) is not dict or observed.get("fixtures") != manifest["retained_fixtures"]:
                    raise ValueError("Observations do not contain the exact gate-retained fixtures")
            manifest = {**manifest, **metadata}
            raw = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8") + b"\n"
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("Chromium runtime manifest exceeds byte boundary")
            (output / "runtime-manifest.json").write_bytes(raw)
            result["runtime_digest"] = _hash(raw)
            result["production_calls"] = _production_calls(envelope.get("production_calls", []), source)
            selected, function = production_entrypoint.rsplit(":", 1)
            if result["production_calls"] != [{"path": selected, "function": function, "calls": manifest.get("production_dispatch_attempts")}]:
                raise ValueError("Chromium production ledger does not bind the selected callable")
            if envelope.get("status") not in {"succeeded", "failed"}:
                raise ValueError("Invalid trusted Chromium result status")
            if execution["exit_code"] != 0 or envelope["status"] != "succeeded":
                result["stderr"] = str(envelope.get("error") or "Guest execution failed")[:1000]
            elif result["output_path"]:
                result["status"] = "succeeded"
            else:
                result["stderr"] = "Guest did not retain observations"
        except (ValueError, UnicodeError, TypeError, KeyError) as exc:
            result["stderr"] = "Invalid trusted Chromium evidence: " + str(exc)[:300]
        return result

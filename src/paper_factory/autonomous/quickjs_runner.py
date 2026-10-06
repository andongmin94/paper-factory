"""Pinned WebAssembly guests supervised by an owned, bounded trusted process.

Node is the trusted embedder and TypeScript parser, never the source executor.
Guest allocation ceilings are explicit; no native total-host-RSS quota is claimed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid

from ..workspace import ensure_unlinked, file_lock, loads_json, write_json
from .runner_common import MAX_ARTIFACT_BYTES, MAX_LOG_BYTES, _production_calls, _retain_observations, _safe_tree


INVENTORY_SHA256 = "ab3b2f965197a33c3c58ee1ca26b75871e78e8b59e4f09fd24addd6d88d7e51a"
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_REQUEST_BYTES = 24 * 1024 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
LIMITS = {"guest_linear_memory_bytes": 128 * 1024 * 1024,
          "guest_js_heap_bytes": 32 * 1024 * 1024, "guest_stack_per_instance_bytes": 512 * 1024,
          "guest_os_processes": 0, "guest_threads": 0, "network": "none", "host_filesystem": "not exposed",
          "artifact_bytes": MAX_ARTIFACT_BYTES, "log_bytes": MAX_LOG_BYTES,
          "gate_json_bytes": 1024 * 1024, "production_dispatches": 65536,
          "node_embedder_old_heap_bytes": 128 * 1024 * 1024,
          "native_host_rss_limit_claimed": False}
WORKER = Path(__file__).with_name("quickjs_worker.mjs")


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


def _relative(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256 or "\\" in value or ":" in value or any(ord(c) < 32 for c in value):
        raise ValueError("Module path must be a bounded relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(item in {".", ".."} for item in path.parts) or path.as_posix() != value:
        raise ValueError("Module path escapes the frozen input")
    if path.suffix not in {".js", ".mjs", ".cjs", ".ts"}:
        raise ValueError("Module must be JavaScript or erasable TypeScript")
    return value


def _files(root: Path, *, limit: int, count: int) -> dict:
    files = {}
    total = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in {".js", ".mjs", ".cjs", ".ts"}:
            continue
        name = _relative(path.relative_to(root).as_posix())
        raw = _read(path, limit)
        total += len(raw)
        if len(files) >= count or total > limit:
            raise ValueError("Frozen code inventory exceeds byte or file boundary")
        text = raw.decode("utf-8", "strict")
        if "\0" in text:
            raise ValueError("Frozen code contains unsupported NUL text")
        files[name] = {"text": text, "sha256": _hash(raw)}
    return files


def _linux_identity(pid: int) -> dict:
    raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    fields = raw.rsplit(")", 1)[1].split()
    start = fields[19]
    boot = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    owner = Path(f"/proc/{pid}").stat().st_uid
    return {"start_time": start, "boot_id": boot, "owner_uid": owner}


def _namespace() -> dict:
    fields = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines() if ":" in line)
    ids = [int(value) for value in fields["NSpid"].split()]
    matches = [index for index, value in enumerate(ids) if value == os.getpid()]
    if len(matches) != 1 or not ids or ids[0] != int(fields["Pid"]):
        raise ValueError("Caller PID namespace mapping is ambiguous")
    return {"pid_namespace": os.readlink("/proc/self/ns/pid"), "namespace_index": matches[0],
            "proc_pid": int(fields["Pid"]), "namespace_pid": os.getpid()}


def _pidfd_identity(descriptor: int, pid: int, namespace: dict) -> dict:
    fields = dict(line.split(":", 1) for line in Path(f"/proc/self/fdinfo/{descriptor}").read_text(encoding="ascii").splitlines() if ":" in line)
    proc_pid, ids = int(fields["Pid"]), [int(value) for value in fields["NSpid"].split()]
    index = namespace["namespace_index"]
    if proc_pid <= 0 or not ids or ids[0] != proc_pid or len(ids) <= index or ids[index] != pid:
        raise ValueError("Owned pidfd does not match the caller PID namespace")
    if os.readlink(f"/proc/{proc_pid}/ns/pid") != namespace["pid_namespace"]:
        raise ValueError("Owned worker PID namespace differs")
    return {"proc_pid": proc_pid, "pid_namespace": namespace["pid_namespace"], "namespace_index": index}


class QuickJSRunner:
    """Run frozen exports through two capability-free QuickJS Wasm instances."""

    def __init__(self, runtime_root: Path, *, supervisor_root: Path, host_profile: str = "private"):
        if not isinstance(host_profile, str) or host_profile not in {"private", "provided"}:
            raise ValueError("QuickJS host profile must be private or provided")
        self.host_profile = host_profile
        self.runtime_root = Path(runtime_root).absolute()
        self.supervisor_root = Path(supervisor_root).expanduser().absolute()
        ensure_unlinked(self.supervisor_root)
        runtime = self.runtime_root.resolve()
        supervisor = self.supervisor_root.resolve()
        if supervisor == runtime or runtime in supervisor.parents or supervisor in runtime.parents:
            raise ValueError("Supervisor scratch must be separate from immutable runtime assets")
        self.supervisor_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._journal_path = self.supervisor_root / "owned-workers.json"
        self._active: dict[str, dict] = {}
        self._mutex = threading.RLock()
        self._probe_lock = threading.Lock()
        self._lease = None
        self._records = self._load_journal()

    def _load_journal(self) -> dict:
        try:
            raw = _read(self._journal_path, 64 * 1024)
        except FileNotFoundError:
            return {}
        value = loads_json(raw)
        if not isinstance(value, dict) or value.get("format") != "paper-factory-quickjs-supervisor-v1":
            raise ValueError("Invalid supervisor journal")
        workers = value.get("workers")
        if not isinstance(workers, list) or len(workers) > 8:
            raise ValueError("Supervisor journal exceeds worker boundary")
        records = {}
        for record in workers:
            if not isinstance(record, dict) or record.get("phase") not in {"starting", "running", "unresolved"} or record.get("purpose") not in {"probe", "experiment"}:
                raise ValueError("Invalid supervisor worker record")
            handle = record.get("handle")
            nonce = handle.get("owner_nonce") if isinstance(handle, dict) else None
            if not re.fullmatch(r"[a-f0-9]{32}", str(nonce)) or nonce in records:
                raise ValueError("Invalid supervisor worker identity")
            records[nonce] = record
        return records

    def _persist(self) -> None:
        if self._lease is None:
            raise ValueError("Supervisor journal mutation requires its owner lease")
        value = {"format": "paper-factory-quickjs-supervisor-v1", "workers": list(self._records.values())}
        if len(self._records) > 8 or len(json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")) + 1 > 64 * 1024:
            raise ValueError("Supervisor worker boundary exceeded")
        write_json(self._journal_path, value)

    def _release_lease(self) -> None:
        if self._lease is not None and not self._active:
            lease, self._lease = self._lease, None
            lease.__exit__(None, None, None)

    def _prepare(self) -> bool:
        """Only an acquired OS lease permits stale-worker reconciliation."""
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
                if not self._stop_recovered(record["handle"]):
                    self._release_lease()
                    return False
                self._records.pop(nonce, None)
                self._persist()
            return True

    def _finish(self, nonce: str) -> None:
        with self._mutex:
            if nonce not in self._active and nonce not in self._records:
                return
            if self._lease is None:
                raise ValueError("Supervisor journal mutation requires its owner lease")
            entry = self._active.pop(nonce, None)
            if entry and entry["pidfd"] is not None:
                os.close(entry["pidfd"])
            if entry and entry.get("job") is not None:
                entry["job"].close()
            if entry and entry.get("guardian") is not None:
                entry["guardian"].close()
            self._records.pop(nonce, None)
            self._persist()
            self._release_lease()

    def _pending(self) -> dict:
        with self._mutex:
            return next((dict(record["handle"]) for record in self._records.values()
                         if record["phase"] == "unresolved" or record["handle"]["owner_nonce"] not in self._active), {})

    def _verify_worker(self, handle: dict) -> None:
        """Only read the mapped, descriptor-bound worker's private identity."""
        pid = handle["proc_pid"]
        identity = _linux_identity(pid)
        if any(handle.get(key) != identity[key] for key in identity) or identity["owner_uid"] != os.getuid():
            raise ValueError("Owned worker identity differs")
        with Path(f"/proc/{pid}/environ").open("rb") as stream:
            environment = stream.read(65537)
        if len(environment) > 65536 or f'PF_QUICKJS_OWNER={handle["owner_nonce"]}'.encode("ascii") not in environment.split(b"\0"):
            raise ValueError("Owned worker nonce differs")
        with Path(f"/proc/{pid}/cmdline").open("rb") as stream:
            command = stream.read(65537)
        expected = [handle["node_path"], "--max-old-space-size=128", str(WORKER), str(self.runtime_root)]
        if command != b"\0".join(os.fsencode(item) for item in expected) + b"\0":
            raise ValueError("Owned trusted worker command differs")
        if handle.get("worker_sha256") != _hash(_read(WORKER, 128 * 1024)):
            raise ValueError("Owned trusted worker bytes differ")

    def _stop_recovered(self, handle: dict) -> bool:
        """Recover only while holding the supervisor lease and in its PID namespace."""
        if sys.platform == "darwin":
            from . import quickjs_macos
            if (not isinstance(handle, dict) or handle.get("kind") != "quickjs-worker"
                    or type(handle.get("pid")) is not int or handle["pid"] < 0
                    or not re.fullmatch(r"[a-f0-9]{32}", str(handle.get("owner_nonce", "")))):
                return False
            node = shutil.which(os.environ.get("PF_NODE_BIN") or "node")
            if not node:
                return False
            expected = quickjs_macos.identity(self.supervisor_root, handle["owner_nonce"],
                                             Path(node).resolve(), _hash(_read(WORKER, 128 * 1024)))
            return quickjs_macos.recover(self.supervisor_root, handle, expected)
        if not self._valid_handle(handle):
            return False
        if os.name == "nt":
            from . import quickjs_windows
            if not quickjs_windows.valid(handle):
                return False
            node = shutil.which(os.environ.get("PF_NODE_BIN") or "node")
            if (not node or handle.get("node_path") != str(Path(node).resolve())
                    or handle.get("worker_sha256") != _hash(_read(WORKER, 128 * 1024))):
                return False
            return quickjs_windows.recover(handle)
        descriptor = None
        try:
            namespace = _namespace()
            node = shutil.which(os.environ.get("PF_NODE_BIN") or "node")
            if not node:
                return False
            node_path = Path(node).resolve()
            ensure_unlinked(node_path)
            if any(handle.get(key) != namespace[key] for key in ("pid_namespace", "namespace_index")):
                return False
            if (handle.get("boot_id") != Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
                    or type(handle.get("owner_uid")) is not int
                    or handle.get("owner_uid") != os.getuid()
                    or not isinstance(handle.get("start_time"), str) or not handle["start_time"].isdigit()
                    or type(handle.get("proc_pid")) is not int
                    or handle["proc_pid"] <= 0
                    or type(handle.get("namespace_index")) is not int or handle["namespace_index"] < 0
                    or handle.get("node_path") != str(node_path)
                    or handle.get("worker_sha256") != _hash(_read(WORKER, 128 * 1024))):
                return False
            try:
                descriptor = os.pidfd_open(handle["pid"], 0)
            except ProcessLookupError:
                # The recorded namespace-local PID has no process in this boot.
                return True
            mapped = _pidfd_identity(descriptor, handle["pid"], namespace)
            if any(handle.get(key) != mapped[key] for key in mapped):
                return False
            self._verify_worker(handle)
            signal.pidfd_send_signal(descriptor, signal.SIGKILL, None, 0)
            import select
            return bool(select.select([descriptor], [], [], 5)[0])
        except (OSError, ValueError, KeyError, TypeError):
            return False
        finally:
            if descriptor is not None:
                os.close(descriptor)

    @staticmethod
    def _valid_handle(handle: dict) -> bool:
        return (isinstance(handle, dict) and handle.get("kind") == "quickjs-worker"
                and type(handle.get("pid")) is int and handle["pid"] > 0
                and bool(re.fullmatch(r"[a-f0-9]{32}", str(handle.get("owner_nonce", "")))))

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
                raise ValueError("Owned QuickJS worker cleanup exceeded the shutdown deadline")
            if self.stop(handle):
                self._finish(handle["owner_nonce"])
        with self._mutex:
            if self._records:
                raise ValueError("Owned QuickJS worker cleanup remains unconfirmed")
            self._release_lease()

    def _runtime(self) -> tuple[Path, dict]:
        root = _safe_tree(self.runtime_root, "QuickJS runtime")
        raw = _read(root / "inventory.json", 256 * 1024)
        if _hash(raw) != INVENTORY_SHA256:
            raise ValueError("Pinned runtime inventory differs")
        inventory = loads_json(raw.decode("utf-8"))
        expected = inventory["files"]
        for name, item in expected.items():
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                raise ValueError("Runtime inventory escapes the package")
            data = _read(root.joinpath(*path.parts), 2 * 1024 * 1024)
            if len(data) != item["size"] or _hash(data) != item["sha256"]:
                raise ValueError("Pinned runtime asset differs")
        actual = {path.relative_to(root).as_posix() for path in (root / "node_modules").rglob("*") if path.is_file()}
        if actual != {name for name in expected if name.startswith("node_modules/")}:
            raise ValueError("Pinned dependency file inventory differs")
        executable = shutil.which(os.environ.get("PF_NODE_BIN") or "node")
        if not executable:
            raise ValueError("Trusted Node interpreter is unavailable")
        node = Path(executable).resolve()
        ensure_unlinked(node)
        version = subprocess.run([str(node), "--version"], capture_output=True, timeout=5, check=False,
                                 env=self._environment(), close_fds=True)
        text = version.stdout.decode("ascii", "strict").strip()
        match = re.fullmatch(r"v(22|24)\.([0-9]+)\.([0-9]+)", text)
        if version.returncode or not match or (match[1] == "22" and
                (self.host_profile != "provided" or int(match[2]) < 16)):
            raise ValueError("Private hosts require Node 24; provided hosts require Node 22.16+ or 24")
        if os.name == "posix" and sys.platform != "darwin" and (not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal")):
            raise ValueError("Owned worker identity primitives are unavailable")
        resources = []
        mechanism = "linux-pidfd"
        if sys.platform == "darwin":
            mechanism = "macos-liveness-guardian"
            resources = ["quickjs_macos.py", "quickjs_guardian.py"]
        elif os.name == "nt":
            mechanism = "windows-job"
            resources = ["quickjs_windows.py", "windows_runtime.py"]
        return node, {"library_version": "0.32.0", "inventory_sha256": INVENTORY_SHA256,
                      "host_profile": self.host_profile,
                      "node_version": text, "node_sha256": _hash(node.read_bytes()),
                      "worker_sha256": _hash(_read(WORKER, 128 * 1024)),
                      "supervision": {"mechanism": mechanism, "sources_sha256": {
                          name: _hash(_read(WORKER.with_name(name), 128 * 1024)) for name in resources}}}

    @staticmethod
    def _environment(nonce: str = "") -> dict:
        result = {"PATH": os.environ.get("PATH", ""), "NODE_NO_WARNINGS": "1"}
        for key in ("SystemRoot", "WINDIR"):
            if key in os.environ:
                result[key] = os.environ[key]
        if nonce:
            result["PF_QUICKJS_OWNER"] = nonce
        return result

    def _execute(self, node: Path, request: dict, *, cancel=None, on_handle=None, purpose="experiment") -> dict:
        payload = json.dumps(request, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(payload) > MAX_REQUEST_BYTES:
            raise ValueError("Trusted request exceeds byte boundary")
        started = time.monotonic()
        nonce = uuid.uuid4().hex
        handle = {"kind": "quickjs-worker", "pid": 0, "owner_nonce": nonce}
        process = None
        streams = {"stdout": bytearray(), "stderr": bytearray()}
        overflow = threading.Event()
        threads = []
        reason = None
        cleaned = False
        forced_stop = None
        job = None
        guardian = None
        try:
            # Hold one controller lease across all its workers. The mutex makes
            # preparing, crash-marker persistence, fork and registration atomic
            # with respect to this controller's other experiment thread.
            with self._mutex:
                if not self._prepare():
                    raise ValueError("Unresolved owned worker blocks another spawn")
                namespace = None
                if os.name == "posix":
                    if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
                        raise ValueError("Owned worker requires the default SIGCHLD disposition")
                    if sys.platform != "darwin":
                        namespace = _namespace()
                if sys.platform == "darwin":
                    from . import quickjs_macos
                    handle.update(quickjs_macos.identity(self.supervisor_root, nonce, node,
                                                         _hash(_read(WORKER, 128 * 1024))))
                    guardian = quickjs_macos.Guardian()
                self._records[nonce] = {"phase": "starting", "purpose": purpose, "handle": dict(handle)}
                self._persist()
                if os.name == "nt":
                    from . import quickjs_windows
                    job = quickjs_windows.create(nonce)
                if guardian is not None:
                    process = guardian.spawn(node, WORKER, self.runtime_root, self._environment(nonce), handle)
                else:
                    process = subprocess.Popen([str(node), "--max-old-space-size=128", str(WORKER), str(self.runtime_root)],
                                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                               env=self._environment(nonce), close_fds=True,
                                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                handle["pid"] = process.pid
                entry = {"process": process, "pidfd": None, "handle": handle, "job": job, "guardian": guardian}
                self._active[nonce] = entry
                # Retain the kernel capability before poll/wait could reap this
                # child. No caller-provided fd number is ever accepted.
                if os.name == "posix" and guardian is None:
                    entry["pidfd"] = os.pidfd_open(process.pid, 0)
                    handle.update(_pidfd_identity(entry["pidfd"], process.pid, namespace))
                    handle.update(_linux_identity(handle["proc_pid"]))
                    handle.update(worker_sha256=_hash(_read(WORKER, 128 * 1024)), node_path=str(node))
                    self._verify_worker(handle)
                elif job is not None:
                    handle.update(quickjs_windows.attach(job, process))
                    handle.update(worker_sha256=_hash(_read(WORKER, 128 * 1024)), node_path=str(node))
                entry["verified"] = True
                self._records[nonce] = {"phase": "running", "purpose": purpose, "handle": dict(handle)}
                self._persist()
            if on_handle:
                on_handle(handle.copy())

            def drain(pipe, name, limit):
                try:
                    while part := pipe.read(65536):
                        room = max(0, limit - len(streams[name]))
                        streams[name].extend(part[:room])
                        if len(part) > room:
                            overflow.set()
                            return
                finally:
                    pipe.close()

            def feed():
                try:
                    process.stdin.write(payload)
                    process.stdin.flush()
                except (BrokenPipeError, OSError, ValueError):
                    pass
                finally:
                    process.stdin.close()

            for name, pipe, limit in (("stdout", process.stdout, MAX_RESPONSE_BYTES), ("stderr", process.stderr, MAX_LOG_BYTES)):
                threads.append(threading.Thread(target=drain, args=(pipe, name, limit), daemon=True))
            threads.append(threading.Thread(target=feed, daemon=True))
            for thread in threads:
                thread.start()
            while process.poll() is None:
                if cancel and cancel():
                    reason = "cancelled"
                    break
                if overflow.is_set():
                    reason = "overflow"
                    break
                if time.monotonic() - started > request["timeout_seconds"] + 3:
                    reason = "timeout"
                    break
                time.sleep(0.02)
        except Exception:
            reason = "controller failure"
        finally:
            if process is None:
                if job is not None:
                    job.close()
                if guardian is not None:
                    guardian.close()
                # A failed fork did not create a child. A persisted crash marker
                # without this observation remains unresolved in a new process.
                self._finish(nonce)
                with self._mutex:
                    self._release_lease()
                cleaned = not bool(self._pending())
            else:
                # Setup failures must release stdin even before feeder startup;
                # the trusted worker can then observe EOF and exit naturally.
                if not threads:
                    process.stdin.close()
                if process.poll() is None:
                    forced_stop = self.stop(handle)
                try:
                    process.wait(timeout=5)
                    for thread in threads:
                        if thread.ident is not None:
                            thread.join(timeout=2)
                    cleaned = all(not thread.is_alive() for thread in threads)
                    if cleaned and job is not None:
                        with self._mutex:
                            cleaned = job.stop()
                    if cleaned and guardian is not None:
                        expected = quickjs_macos.identity(self.supervisor_root, nonce, node,
                                                           _hash(_read(WORKER, 128 * 1024)))
                        cleaned = quickjs_macos.completed(self.supervisor_root, handle, expected)
                    if cleaned:
                        for pipe in (process.stdin, process.stdout, process.stderr):
                            pipe.close()
                except subprocess.TimeoutExpired:
                    cleaned = False
                if cleaned:
                    self._finish(nonce)
                else:
                    with self._mutex:
                        self._records[nonce] = {"phase": "unresolved", "purpose": purpose, "handle": dict(handle)}
                        self._persist()
        parsed = None
        if not overflow.is_set() and not reason:
            try:
                parsed = loads_json(bytes(streams["stdout"]).decode("utf-8", "strict"))
            except (ValueError, UnicodeError):
                reason = "invalid worker response"
        return {"exit_code": process.returncode if process else None, "envelope": parsed, "cleanup_confirmed": cleaned,
                "active_handle": {} if cleaned else (handle if process else self._pending()), "reason": reason,
                "forced_stop_confirmed": forced_stop,
                "duration_seconds": round(time.monotonic() - started, 3)}

    def stop(self, handle: dict) -> bool:
        if not self._valid_handle(handle):
            return False
        nonce = handle["owner_nonce"]
        descriptor = None
        with self._mutex:
            entry = self._active.get(nonce)
            if entry is None:
                # An unrelated live controller's OS lease forbids recovery.
                try:
                    if self._lease is None:
                        lease = file_lock(self.supervisor_root / "supervisor.lock")
                        lease.__enter__()
                        self._lease = lease
                        self._records = self._load_journal()
                    record = self._records.get(nonce)
                    if record and handle != record["handle"]:
                        return False
                    # Workflow's private on_handle survives the small interval
                    # between worker journal removal and its execution receipt.
                    # It must satisfy the same full namespace-bound identity.
                    stopped = self._stop_recovered(handle)
                    if stopped:
                        self._finish(nonce)
                    return stopped
                except (OSError, ValueError, KeyError, TypeError):
                    return False
                finally:
                    self._release_lease()
            active = entry["process"]
            if active.pid != handle["pid"] or handle != entry["handle"]:
                return False
            if active.poll() is not None:
                if entry.get("guardian") is None:
                    return entry["job"].stop() if entry.get("job") is not None else True
                from . import quickjs_macos
                expected = quickjs_macos.identity(self.supervisor_root, nonce, Path(handle["node_path"]),
                                                 _hash(_read(WORKER, 128 * 1024)))
                return quickjs_macos.completed(self.supervisor_root, handle, expected)
            if not entry.get("verified"):
                return False
            if entry.get("guardian") is not None:
                entry["guardian"].close()
            elif os.name == "posix":
                # Duplicate under the registry mutex, so concurrent finish cannot
                # close and recycle the descriptor before this signal uses it.
                try:
                    descriptor = os.dup(entry["pidfd"])
                except (OSError, TypeError):
                    return False
            elif entry.get("job") is not None:
                # The registry mutex protects the job handle from close/reuse.
                # stop() confirms the entire owned job is empty before returning.
                if not entry["job"].stop():
                    return False
        try:
            if descriptor is not None:
                signal.pidfd_send_signal(descriptor, signal.SIGKILL, None, 0)
            elif os.name == "nt" and entry.get("job") is None and entry.get("guardian") is None:
                return False
            active.wait(timeout=5)
            if entry.get("guardian") is not None:
                from . import quickjs_macos
                expected = quickjs_macos.identity(self.supervisor_root, nonce, Path(handle["node_path"]),
                                                 _hash(_read(WORKER, 128 * 1024)))
                return quickjs_macos.completed(self.supervisor_root, handle, expected)
            return True
        except ProcessLookupError:
            try:
                active.wait(timeout=5)
                if entry.get("guardian") is not None:
                    from . import quickjs_macos
                    expected = quickjs_macos.identity(self.supervisor_root, nonce, Path(handle["node_path"]),
                                                     _hash(_read(WORKER, 128 * 1024)))
                    return quickjs_macos.completed(self.supervisor_root, handle, expected)
                return True
            except subprocess.TimeoutExpired:
                return False
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return False
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def status(self) -> dict:
        # A status request in another process must not classify a live owner's
        # worker as an orphan. Only the supervisor lease permits self-checks.
        with self._probe_lock:
            prepared = False
            try:
                with self._mutex:
                    prepared = self._prepare()
                    if not prepared:
                        raise ValueError("Owned worker cleanup remains unresolved")
                result = self._status()
            except OSError as exc:
                result = self._status_fields()
                result.update(code="SUPERVISOR_UNAVAILABLE",
                              reason="QuickJS supervisor files are unavailable; owned cleanup is unverified",
                              diagnostic={"stage": "supervisor-prepare", "exception_type": type(exc).__name__[:64]})
                for key, maximum in (("errno", 4095), ("winerror", 65535)):
                    value = getattr(exc, key, None)
                    if type(value) is int and 0 <= value <= maximum:
                        result["diagnostic"][key] = value
            except (ValueError, KeyError, TypeError) as exc:
                result = self._status_fields()
                busy = isinstance(exc, ValueError) and str(exc) == "Another operation is already running for supervisor"
                result.update(code="SUPERVISOR_BUSY" if busy else "SUPERVISOR_STATE_INVALID",
                              reason="QuickJS supervisor is busy" if busy else "QuickJS supervisor state could not be verified",
                              diagnostic={"stage": "supervisor-prepare", "exception_type": type(exc).__name__[:64]})
            finally:
                with self._mutex:
                    self._release_lease()
            pending = self._pending()
            result["cleanup_confirmed"] = prepared and not bool(pending)
            if pending:
                result.update(ready=False, runtimes=[], code="CLEANUP_UNCONFIRMED",
                              reason="Owned QuickJS worker exit could not be confirmed")
            return result

    def _status_fields(self) -> dict:
        return {"ready": False, "reason": None, "backend": "quickjs-wasm", "runtimes": [],
                "host_profile": self.host_profile, "typescript_parser_self_check": False,
                "dependencies": [], "versions": {}, "declared_limits": LIMITS.copy(),
                "native_host_rss_limit_claimed": False, "recoverable_cleanup": False}

    def _status(self) -> dict:
        result = self._status_fields()
        try:
            node, runtime = self._runtime()
            source = 'module.exports={calculate(x){if(x===null)throw new Error("original rejection");return x+1}};'
            code = '''export default function run(){
              const unavailable=["process","require","fetch","WebSocket","Worker","WebAssembly"].every(k=>typeof globalThis[k]==="undefined");
              let immutable=false; try{globalThis.callProduction=()=>"forged"}catch{immutable=true}
              const value=JSON.parse(callProduction("[6]"));
              let rejection=false; try{callProduction("[null]")}catch(e){rejection=e.message.includes("original rejection")}
              return {unavailable,immutable,value,rejection,fixture:JSON.parse(retainFixture("unicode","가"))};
            }'''
            packet = {"source_files": {"check.cjs": {"text": source, "sha256": _hash(source.encode())}},
                      "experiment_files": {"check.mjs": {"text": code, "sha256": _hash(code.encode())}},
                      "production_entrypoint": "check.cjs:calculate", "entrypoint": "check.mjs", "timeout_seconds": 5}
            receipt = self._execute(node, packet, purpose="probe")
            envelope = receipt.get("envelope") or {}
            if receipt["exit_code"] != 0 or not receipt["cleanup_confirmed"] or receipt["reason"] or envelope.get("status") != "succeeded":
                raise ValueError("Actual Wasm boundary self-check failed")
            observed = loads_json(base64.b64decode(envelope["observation_b64"], validate=True).decode("utf-8"))
            fixture = observed["fixture"]
            if (observed.get("value") != 7 or not all(observed.get(k) is True for k in ("unavailable", "immutable", "rejection"))
                    or fixture["sha256"] != _hash("가".encode()) or base64.b64decode(fixture["content"], validate=True) != "가".encode()
                    or envelope["production_calls"][0]["calls"] != 2
                    or envelope["runtime_manifest"].get("distinct_wasm_memories") is not True
                    or envelope["runtime_manifest"].get("hard_linear_growth_denied") is not True):
                raise ValueError("Actual Wasm boundary self-check failed")
            # The version gate alone cannot establish the embedder's parser API.
            # Strip fixed TypeScript through the actual worker, then execute only
            # its compiled text in the guest and inspect both module receipts.
            ts_source = 'import {delta} from "./delta.ts"; export function calculate(x:number):number{return x+delta}'
            ts_helper = 'export const delta:number=1;'
            ts_code = 'export default function run(){return {value:JSON.parse(callProduction("[6]"))}}'
            ts_packet = {**packet, "production_entrypoint": "check.ts:calculate",
                         "source_files": {name: {"text": text, "sha256": _hash(text.encode())}
                                          for name, text in (("check.ts", ts_source), ("delta.ts", ts_helper))},
                         "experiment_files": {"check.mjs": {"text": ts_code, "sha256": _hash(ts_code.encode())}}}
            parsed = self._execute(node, ts_packet, purpose="probe")
            parsed_envelope = parsed.get("envelope") or {}
            compiled_manifest = parsed_envelope.get("runtime_manifest") or {}
            transformer = compiled_manifest.get("transformer") or {}
            if (parsed["exit_code"] != 0 or not parsed["cleanup_confirmed"] or parsed["reason"]
                    or parsed_envelope.get("status") != "succeeded"
                    or loads_json(base64.b64decode(parsed_envelope["observation_b64"], validate=True).decode("utf-8")) != {"value": 7}
                    or parsed_envelope.get("production_calls") != [{"path": "check.ts", "function": "calculate", "calls": 1}]
                    or transformer.get("name") != "node:module.stripTypeScriptTypes"
                    or transformer.get("version") != runtime["node_version"]
                    or transformer.get("options") != {"mode": "strip", "sourceMap": False}
                    or transformer.get("options_scope") != "shared"
                    or transformer.get("native_typescript_execution") is not False):
                raise ValueError("Actual TypeScript parser self-check failed")
            for name, item in ts_packet["source_files"].items():
                original = compiled_manifest["source_files"][name]
                compiled = compiled_manifest["compiled_files"][name]
                if (original.get("original_sha256") != item["sha256"]
                        or compiled.get("original_sha256") != item["sha256"]
                        or not re.fullmatch(r"[a-f0-9]{64}", str(compiled.get("compiled_sha256", "")))
                        or compiled["compiled_sha256"] == item["sha256"]
                        or compiled.get("transformation") != "node:module.stripTypeScriptTypes"
                        or compiled.get("transformation_options") != {
                            "mode": "strip", "sourceMap": False, "sourceUrl": "source/" + name}):
                    raise ValueError("Actual TypeScript parser receipt differs")
            # Readiness also proves that this host permits termination through
            # the owned identity path, not just that pidfd APIs are importable.
            kill_code = 'export default function run(){while(true){}}'
            kill_packet = {**packet, "timeout_seconds": 5,
                           "experiment_files": {"check.mjs": {"text": kill_code, "sha256": _hash(kill_code.encode())}}}
            kill_started = time.monotonic()
            killed = self._execute(node, kill_packet, cancel=lambda: time.monotonic() - kill_started > 0.02, purpose="probe")
            if killed["reason"] != "cancelled" or not killed["cleanup_confirmed"] or killed["forced_stop_confirmed"] is not True:
                raise ValueError("Owned worker termination self-check failed")
            result.update(ready=True, runtimes=["quickjs"], versions={"quickjs-emscripten": "0.32.0", "node": runtime["node_version"]},
                          runtime_digest=runtime["inventory_sha256"], recoverable_cleanup=True,
                          typescript_parser_self_check=True)
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            result["reason"] = "Pinned QuickJS assets, supported trusted Node, actual parser or Wasm boundary self-check are unavailable"
        return result

    def run(self, source_dir: Path, bundle_dir: Path, output_dir: Path, *, runtime: str,
            entrypoint: str, production_entrypoint: str = "", timeout_seconds: int = 300,
            cancel=None, on_handle=None) -> dict:
        if runtime != "quickjs":
            raise ValueError("QuickJS runner only accepts runtime quickjs")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 3600:
            raise ValueError("Experiment timeout must be between one and 3600 seconds")
        source, bundle = _safe_tree(Path(source_dir), "source"), _safe_tree(Path(bundle_dir), "bundle")
        entrypoint = _relative(entrypoint)
        if Path(entrypoint).suffix == ".ts":
            raise ValueError("Generated experiments must be JavaScript ES modules")
        selected, separator, function = production_entrypoint.rpartition(":")
        _relative(selected)
        if not separator or not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*", function):
            raise ValueError("Production entrypoint must identify a frozen exported callable")
        source_files, code_files = _files(source, limit=MAX_SOURCE_BYTES, count=2048), _files(bundle, limit=512 * 1024, count=12)
        if selected not in source_files or entrypoint not in code_files:
            raise ValueError("Entrypoint is absent from frozen code inventory")
        output = Path(output_dir)
        ensure_unlinked(output)
        output = output.resolve()
        if output == source or source in output.parents or output == bundle or bundle in output.parents:
            raise ValueError("Output directory must be separate from source and bundle")
        output.mkdir(parents=True, exist_ok=True)
        if not output.is_dir() or any(output.iterdir()):
            raise ValueError("Output directory must be empty")
        result = {"status": "failed", "backend": "quickjs-wasm", "image_digest": None, "runtime_digest": None,
                  "command": ["quickjs", entrypoint], "limits": {**LIMITS, "timeout_seconds": timeout_seconds},
                  "artifacts": [], "output_path": None, "stdout": "", "stderr": "", "exit_code": None,
                  "production_entrypoint": production_entrypoint, "production_calls": [], "coverage_truncated": False,
                  "coverage_mechanism": "controller-held-wasm-call-gate", "cleanup_confirmed": True, "active_handle": {}}
        if cancel and cancel():
            result["status"] = "cancelled"
            return result
        ready = self.status()
        if not ready["ready"]:
            result["stderr"] = ready["reason"]
            result["cleanup_confirmed"] = ready.get("cleanup_confirmed", True)
            if not result["cleanup_confirmed"]:
                result.update(status="blocked", code="CLEANUP_UNCONFIRMED", active_handle=self._pending())
            return result
        node, metadata = self._runtime()
        packet = {"source_files": source_files, "experiment_files": code_files, "entrypoint": entrypoint,
                  "production_entrypoint": production_entrypoint, "timeout_seconds": timeout_seconds}
        execution = self._execute(node, packet, cancel=cancel, on_handle=on_handle)
        result.update({key: execution[key] for key in ("exit_code", "cleanup_confirmed", "active_handle", "duration_seconds")})
        if not execution["cleanup_confirmed"]:
            result.update(status="blocked", code="CLEANUP_UNCONFIRMED", stderr="Owned QuickJS worker exit could not be confirmed")
        if execution["reason"]:
            if execution["cleanup_confirmed"]:
                result["status"] = execution["reason"] if execution["reason"] in {"timeout", "cancelled"} else "failed"
                result["stderr"] = "Bounded QuickJS worker rejected: " + execution["reason"]
            return result
        envelope = execution.get("envelope") or {}
        if envelope.get("protocol") != "paper-factory-quickjs-v1":
            result["stderr"] = "Invalid trusted QuickJS protocol"
            return result
        manifest = envelope.get("runtime_manifest")
        if not isinstance(manifest, dict):
            result["stderr"] = "Missing trusted runtime manifest"
            return result
        manifest.update(metadata)
        raw = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8") + b"\n"
        (output / "runtime-manifest.json").write_bytes(raw)
        result["runtime_digest"] = _hash(raw)
        result["production_calls"] = _production_calls(envelope.get("production_calls", []), source)
        if envelope.get("status") not in {"succeeded", "failed"} or (envelope.get("status") == "succeeded" and result["exit_code"] != 0):
            result["stderr"] = "Guest execution failed without a valid failed-evidence frame"
            return result
        if "observation_b64" in envelope and (manifest.get("production_entrypoint") != production_entrypoint or manifest.get("distinct_wasm_memories") is not True or manifest.get("hard_linear_growth_denied") is not True):
            result["stderr"] = "Trusted runtime binding is incomplete"
            return result
        if "observation_b64" in envelope:
            try:
                encoded = envelope["observation_b64"]
                if not isinstance(encoded, str) or len(encoded) > (MAX_ARTIFACT_BYTES + 2) // 3 * 4:
                    raise ValueError("Oversized observation transport")
                # Failed execution may still have returned actual control evidence.
                # Retaining those bytes never changes its failed status.
                result.update(_retain_observations(output, base64.b64decode(encoded, validate=True)))
            except (ValueError, UnicodeError):
                result["stderr"] = "Invalid bounded observations"
                return result
        if not execution["cleanup_confirmed"]:
            return result
        if result["exit_code"] != 0 or envelope.get("status") != "succeeded":
            result["stderr"] = str(envelope.get("error") or "Guest execution failed")[:1000]
        elif result["output_path"]:
            result["status"] = "succeeded"
        else:
            result["stderr"] = "Invalid bounded observations"
        return result

"""Fail-closed, resource-bounded execution of generated research programs.

Windows selects the native AppContainer worker; Linux selects a provisioned
immutable Docker image. Unavailable isolation blocks generated execution.
Only observations.json and a controller-managed execution receipt cross the
sandbox boundary, through a bounded stream. The receipt catches accidental
replacement of production functions; it is not adversarial code attestation.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import threading
import time
from typing import Callable
import uuid

from ..workspace import ensure_unlinked, is_link


IMAGE_LABEL = "org.paper-factory.research-runtime"
PROTOCOL = "paper-factory-runner-v1"
CONTAINER_PREFIX = "paper-factory-research-"
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_LOG_BYTES = 256 * 1024
MAX_TRANSPORT_BYTES = 12 * 1024 * 1024
MAX_INPUT_BYTES = 256 * 1024 * 1024
MAX_INPUT_FILES = 20_000
MAX_PRODUCTION_FUNCTIONS = 512
_IMMUTABLE_IMAGE = re.compile(r"(?:sha256:[0-9a-f]{64}|[A-Za-z0-9._:/-]+@sha256:[0-9a-f]{64})\Z")
LIMITS = {
    "cpus": 1, "memory_bytes": 512 * 1024 * 1024, "pids": 128,
    "work_bytes": 256 * 1024 * 1024, "output_bytes": 64 * 1024 * 1024,
    "artifact_bytes": MAX_ARTIFACT_BYTES, "log_bytes": MAX_LOG_BYTES,
    "network": "none", "uid": 65532, "read_only_root": True,
}

# Both isolated backends execute the same controller-owned Python profiler.
_PYTHON_DRIVER = r'''
import json, os, pathlib, runpy, sys, threading
source = pathlib.Path(os.environ['PF_SOURCE_ROOT']).resolve()
output = pathlib.Path(os.environ['PF_OUTPUT_ROOT'])
if os.name == 'nt':
    def inherit_private_directory_acl():
        # Windows 0700 replaces the inherited DACL and drops the AppContainer SID.
        # Other modes inherit the controller's private writable-root permissions.
        mkdir = os.mkdir
        roots = tuple(os.path.normcase(os.path.abspath(os.environ[name]))
                      for name in ('PF_WORK', 'PF_OUTPUT_ROOT', 'TEMP'))
        def private_mkdir(path, mode=0o777, *, dir_fd=None):
            if type(mode) is int and mode == 0o700 and dir_fd is None:
                try:
                    candidate = os.path.normcase(os.path.abspath(os.fsdecode(path)))
                    if any(candidate != root and os.path.commonpath((candidate, root)) == root
                           for root in roots):
                        mode = 0o777
                except (TypeError, ValueError):
                    pass
            return mkdir(path, mode, dir_fd=dir_fd)
        os.mkdir = private_mkdir
    inherit_private_directory_acl()
calls, filenames = {}, {}
truncated = False
def profile(frame, event, argument):
    global truncated
    # Module and class-body execution are not calls to production functions.
    if event != 'call' or frame.f_code.co_name == '<module>' or not frame.f_code.co_flags & 0x2: return
    filename = frame.f_code.co_filename
    if filename not in filenames:
        try:
            actual = pathlib.Path(filename).resolve()
            filenames[filename] = actual.relative_to(source).as_posix()
        except (ValueError, OSError): filenames[filename] = None
    path = filenames[filename]
    if path is None or len(path) > 256: return
    function = frame.f_code.co_qualname
    if len(function) > 128: return
    key = (path, function)
    if key not in calls and len(calls) >= 512:
        truncated = True
        return
    calls[key] = min(calls.get(key, 0) + 1, 1_000_000_000)
sys.setprofile(profile)
threading.setprofile(profile)
try:
    # Match direct-script argv/sys.path while retaining the trusted profiler.
    sys.argv = [sys.argv[1]]
    sys.path.insert(0, str(pathlib.Path(sys.argv[0]).parent))
    runpy.run_path(sys.argv[0], run_name='__main__')
finally:
    # Callback errors (including deep recursion) silently detach Python's hook.
    # Retain the measured output, but never describe the partial trace as complete.
    truncated = truncated or sys.getprofile() is not profile
    sys.setprofile(None)
    threading.setprofile(None)
    payload = {'calls':[{'path':path,'function':name,'calls':count}
                        for (path,name),count in sorted(calls.items())], 'truncated':truncated}
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(output / '.paper-factory-python-calls.json', flags, 0o600)
    with os.fdopen(descriptor,'w',encoding='utf-8') as stream: json.dump(payload,stream)
'''

# This controller-owned program runs INSIDE Docker. It neither receives model
# credentials nor executes on the host. The generated child sees fixed paths.
_LAUNCHER = r'''
import base64, json, math, os, pathlib, signal, stat, subprocess, sys, threading, urllib.parse
runtime, entrypoint, timeout = sys.argv[1], sys.argv[2], int(sys.argv[3])
artifact_limit, log_limit = int(sys.argv[4]), int(sys.argv[5])
commands = {"python": "/usr/local/bin/python3", "node": "/usr/local/bin/node"}
env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/work", "LANG": "C.UTF-8",
       "PF_INPUT": "/input", "PF_OUTPUT": "/output", "PF_WORK": "/work",
       "PF_SOURCE_ROOT": "/input", "PF_CODE_ROOT": "/code", "PF_OUTPUT_ROOT": "/output",
       "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}
''' + '\npython_driver = ' + repr(_PYTHON_DRIVER) + r'''
def finite_float(value):
    number = float(value)
    if not math.isfinite(number): raise ValueError('nonfinite JSON number')
    return number

def read_json(path, limit):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError('invalid bounded receipt file')
        with os.fdopen(descriptor,'rb',closefd=False) as stream: data = stream.read(limit + 1)
        if len(data) > limit: raise ValueError('receipt exceeds size limit')
        return json.loads(data.decode('utf-8'),parse_float=finite_float,parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite receipt')))
    finally: os.close(descriptor)
def production_receipt():
    if runtime == 'python':
        payload = read_json('/output/.paper-factory-python-calls.json', 1024*1024)
        return payload['calls'], bool(payload['truncated'])
    directory = pathlib.Path('/output/.paper-factory-node-coverage')
    if directory.is_symlink() or not directory.is_dir(): raise ValueError('invalid coverage directory')
    calls, truncated = {}, False
    files = sorted(directory.glob('coverage-*.json'))
    if len(files) > 32: truncated = True
    for path in files[:32]:
        coverage = read_json(path, 4*1024*1024)
        for script in coverage.get('result',[]):
            url = urllib.parse.urlparse(script.get('url',''))
            if url.scheme != 'file': continue
            try: relative = pathlib.PurePosixPath(urllib.parse.unquote(url.path)).relative_to('/input').as_posix()
            except ValueError: continue
            if '..' in pathlib.PurePosixPath(relative).parts or len(relative) > 256: continue
            for function in script.get('functions',[]):
                name = function.get('functionName','')
                ranges = function.get('ranges',[])
                if not name or len(name) > 128 or not ranges: continue
                count = ranges[0].get('count',0)
                if isinstance(count,bool) or not isinstance(count,int) or count <= 0: continue
                key = (relative,name)
                if key not in calls and len(calls) >= 512:
                    truncated = True
                    continue
                calls[key] = min(calls.get(key,0)+count,1_000_000_000)
    return [{'path':path,'function':name,'calls':count} for (path,name),count in sorted(calls.items())],truncated
logs = {"stdout": bytearray(), "stderr": bytearray()}
truncated = {"stdout": False, "stderr": False}
def drain(pipe, key):
    try:
        while True:
            part = pipe.read(65536)
            if not part: break
            room = max(0, log_limit - len(logs[key]))
            logs[key].extend(part[:room])
            if len(part) > room: truncated[key] = True
    finally: pipe.close()
result = {"protocol": "paper-factory-runner-v1", "exit_code": None,
          "stdout": "", "stderr": "", "observation_b64": None, "error": None,
          "timed_out": False, "production_calls": [], "coverage_truncated": False}
try:
    if runtime == 'python': command = [commands[runtime],'-c',python_driver,'/code/'+entrypoint]
    else:
        env['NODE_V8_COVERAGE']='/output/.paper-factory-node-coverage'
        command = [commands[runtime],'/code/'+entrypoint]
    child = subprocess.Popen(command, cwd="/work",
                             env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             start_new_session=True)
    threads = [threading.Thread(target=drain, args=(child.stdout,"stdout"), daemon=True),
               threading.Thread(target=drain, args=(child.stderr,"stderr"), daemon=True)]
    for thread in threads: thread.start()
    try: child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        result["timed_out"] = True
        os.killpg(child.pid, signal.SIGKILL)
        child.wait()
    # Stop descendants even if their parent completed. They cannot race export.
    try: os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError: pass
    for thread in threads: thread.join(timeout=2)
    result["exit_code"] = child.returncode
    if not result["timed_out"]:
        if child.returncode == 0:
            result['production_calls'],result['coverage_truncated']=production_receipt()
        path = pathlib.Path("/output/observations.json")
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        fd = os.open(path, flags)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("observations.json must be a regular file with exactly one link")
            if info.st_size > artifact_limit: raise ValueError("observations.json exceeds size limit")
            with os.fdopen(fd, "rb", closefd=False) as stream: data = stream.read(artifact_limit + 1)
            if len(data) > artifact_limit: raise ValueError("observations.json exceeds size limit")
            json.loads(data.decode("utf-8"), parse_float=finite_float, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON value: " + value)))
            result["observation_b64"] = base64.b64encode(data).decode("ascii")
        finally: os.close(fd)
        if child.returncode != 0:
            # A missing failure receipt must not discard an already retained
            # negative observation. Successful execution still requires it.
            result['production_calls'],result['coverage_truncated']=production_receipt()
except BaseException as exc:
    result["error"] = type(exc).__name__ + ": " + str(exc)
for key in logs:
    result[key] = bytes(logs[key]).decode("utf-8", "replace")
    if truncated[key]: result[key] += "\n[log truncated]"
print(json.dumps(result, ensure_ascii=True, separators=(",", ":")), flush=True)
sys.exit(0 if result["exit_code"] == 0 and not result["error"] and not result["timed_out"] else 1)
'''


def _safe_tree(path: Path, label: str) -> Path:
    ensure_unlinked(path)
    if is_link(path) or not path.is_dir():
        raise ValueError(f"{label} must be a real directory")
    resolved = path.resolve()
    if "," in str(resolved) or "\n" in str(resolved):
        raise ValueError(f"{label} contains an unsupported mount path")
    count = total = 0
    for parent, directories, files in os.walk(resolved, followlinks=False):
        for name in directories + files:
            item = Path(parent) / name
            info = item.lstat()
            if is_link(item) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError(f"{label} must not contain links or special files")
            if stat.S_ISREG(info.st_mode):
                count += 1
                total += info.st_size
                if count > MAX_INPUT_FILES or total > MAX_INPUT_BYTES:
                    raise ValueError(f"{label} exceeds sandbox input limits")
    return resolved


def _entrypoint(path: str, runtime: str, bundle: Path) -> str:
    item = PurePosixPath(path)
    if (runtime not in {"python", "node"} or not path or item.is_absolute()
            or any(part in {".", ".."} for part in item.parts)
            or "\\" in path or "\x00" in path
            or item.suffix not in {"python": {".py"}, "node": {".js", ".cjs", ".mjs"}}.get(runtime, set())):
        raise ValueError("entrypoint must be a relative Python or JavaScript file for the selected runtime")
    actual = bundle.joinpath(*item.parts)
    if not actual.is_file() or actual.is_symlink():
        raise ValueError("entrypoint is not a regular bundle file")
    return item.as_posix()


def _stage_tree(source: Path, target: Path) -> None:
    """Copy frozen inputs with readable modes without chmodding host originals."""
    target.mkdir(mode=0o755)
    target.chmod(0o755)
    for parent, directories, files in os.walk(source, followlinks=False):
        relative = Path(parent).relative_to(source)
        for name in directories:
            actual = Path(parent) / name
            if is_link(actual):
                raise ValueError("sandbox input changed to a symbolic link")
            destination = target / relative / name
            destination.mkdir(mode=0o755)
            destination.chmod(0o755)
        for name in files:
            actual = Path(parent) / name
            ensure_unlinked(actual)
            before = actual.stat(follow_symlinks=False)
            descriptor = os.open(actual, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
            try:
                info = os.fstat(descriptor)
                ensure_unlinked(actual)
                if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino):
                    raise ValueError("sandbox input changed to a special file")
                with os.fdopen(descriptor, "rb", closefd=False) as stream:
                    destination = target / relative / name
                    with destination.open("xb") as output:
                        shutil.copyfileobj(stream, output)
                destination.chmod(0o755 if info.st_mode & 0o111 else 0o644)
            finally:
                os.close(descriptor)


def _bounded_log(value: str) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= MAX_LOG_BYTES:
        return value
    marker = "\n[log truncated]"
    return encoded[:MAX_LOG_BYTES - len(marker)].decode("utf-8", "ignore") + marker


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Sandbox artifact contains a nonfinite JSON number")
    return number


def _nonfinite_json(value: str):
    raise ValueError("Sandbox artifact contains a nonfinite JSON number")


def _retain_observations(output: Path, data: bytes) -> dict:
    """Retain exact bounded JSON bytes without changing the execution status."""
    if not data or len(data) > MAX_ARTIFACT_BYTES:
        raise ValueError("observation is empty or exceeds size limit")
    json.loads(data.decode("utf-8"), parse_float=_finite_float, parse_constant=_nonfinite_json)
    path = output / "observations.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
    return {"output_path": str(path), "artifacts": [{"path": "observations.json", "size": len(data),
                                                    "sha256": hashlib.sha256(data).hexdigest()}]}


def _production_calls(value: object, source: Path) -> list[dict]:
    if not isinstance(value, list) or len(value) > MAX_PRODUCTION_FUNCTIONS:
        raise ValueError("invalid production execution receipt")
    normalized = []
    identities = set()
    for record in value:
        if not isinstance(record, dict):
            raise ValueError("invalid production execution record")
        path, function, calls = (record.get(key) for key in ("path", "function", "calls"))
        if not isinstance(path, str) or len(path) > 256 or not isinstance(function, str) or not 1 <= len(function) <= 128:
            raise ValueError("invalid production execution identity")
        relative = PurePosixPath(path)
        if (relative.is_absolute() or ".." in relative.parts or "\\" in path or not relative.parts
                or relative.as_posix() != path or any(ord(character) < 32 for character in path + function)
                or function == "<module>"):
            raise ValueError("production receipt escapes the source snapshot")
        if not source.joinpath(*relative.parts).is_file():
            raise ValueError("production receipt does not identify a source snapshot file")
        if isinstance(calls, bool) or not isinstance(calls, int) or not 1 <= calls <= 1_000_000_000:
            raise ValueError("invalid production execution count")
        if (path, function) in identities:
            raise ValueError("duplicate production execution record")
        identities.add((path, function))
        normalized.append({"path": path, "function": function, "calls": calls})
    return normalized


class DockerRunner:
    """A trusted Docker CLI controller, never a generated-code host executor."""

    def __init__(self, image: str | None = None, *, docker: str = "docker") -> None:
        self.image = image if image is not None else os.environ.get("PF_RESEARCH_IMAGE", "")
        self.docker = docker

    def _control(self, args: list[str], *, timeout: int = 15) -> subprocess.CompletedProcess[str]:
        return subprocess.run([self.docker, *args], text=True, capture_output=True,
                              timeout=timeout, check=False)

    def status(self) -> dict:
        result = {"ready": False, "image": self.image or None, "image_digest": None, "reason": None,
                  "runtimes": [], "dependencies": [], "versions": {}}
        if not shutil.which(self.docker):
            result["reason"] = "Docker CLI is not installed; generated code cannot run on the host"
            return result
        if not _IMMUTABLE_IMAGE.fullmatch(self.image):
            result["reason"] = "PF_RESEARCH_IMAGE must identify a provisioned immutable sha256 image"
            return result
        try:
            daemon = self._control(["info", "--format", "{{json .SecurityOptions}}"])
            if daemon.returncode:
                result["reason"] = "Docker daemon is unavailable: " + daemon.stderr.strip()[:500]
                return result
            security = json.loads(daemon.stdout)
            if not isinstance(security, list) or not any(isinstance(item, str) and item == "name=seccomp,profile=builtin" for item in security):
                result["reason"] = "Docker daemon must provide a seccomp profile"
                return result
            inspect = self._control(["image", "inspect", self.image, "--format", "{{json .}}"])
            if inspect.returncode:
                result["reason"] = "Provisioned research image is unavailable locally: " + inspect.stderr.strip()[:500]
                return result
            details = json.loads(inspect.stdout)
            if not isinstance(details, dict):
                raise ValueError("invalid image inspection")
            config = details.get("Config", {})
            if not isinstance(config, dict):
                raise ValueError("invalid image configuration")
            digest = details.get("Id", "")
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                raise ValueError("image does not have a content-addressed digest")
            result["image_digest"] = digest
            if not isinstance(config.get("Labels"), dict) or config["Labels"].get(IMAGE_LABEL) != "1":
                raise ValueError("image is not marked as a provisioned Paper Factory research runtime")
            if config.get("User") not in {"65532", "65532:65532"} or config.get("Entrypoint"):
                raise ValueError("image must use non-root uid 65532 and have no entrypoint")
            if config.get("Volumes"):
                raise ValueError("image must not declare writable Docker volumes")
            if config.get("Healthcheck"):
                raise ValueError("image must not declare background healthcheck commands")
            labels = config["Labels"]
            runtimes = labels.get("org.paper-factory.research-runtimes", "").split(",")
            dependencies = [item for item in labels.get("org.paper-factory.research-dependencies", "").split(",") if item]
            if set(runtimes) != {"python", "node"} or any(not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", item) for item in dependencies):
                raise ValueError("image must declare its vetted runtimes and dependency allowlist")
            result["runtimes"] = runtimes
            result["dependencies"] = dependencies
            result["versions"] = {key: labels.get("org.paper-factory.version-" + key)
                                  for key in runtimes + dependencies}
            result["ready"] = True
        except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, KeyError) as exc:
            result["reason"] = f"Docker prerequisite check failed: {exc}"
        return result

    def stop(self, handle: dict) -> bool:
        """Remove only a persisted handle belonging to this runner after restart."""
        if not isinstance(handle, dict) or handle.get("kind") != "container":
            return False
        identifier, name = handle.get("container_id"), handle.get("container_name")
        if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{64}", identifier):
            return False
        if not isinstance(name, str) or not re.fullmatch(CONTAINER_PREFIX + r"[0-9a-f]{32}", name):
            return False
        try:
            inspection = self._control(["inspect", identifier, "--format", "{{json .Name}}"])
            if inspection.returncode:
                return "No such" in inspection.stderr
            if json.loads(inspection.stdout) != "/" + name:
                return False
            removed = self._control(["rm", "--force", identifier], timeout=5)
            return removed.returncode == 0
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return False

    def run(self, source_dir: Path, bundle_dir: Path, output_dir: Path, *, runtime: str,
            entrypoint: str, timeout_seconds: int = 300, production_entrypoint: str = "",
            cancel: Callable[[], bool] | None = None,
            on_handle: Callable[[dict], None] | None = None) -> dict:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 3600:
            raise ValueError("experiment timeout must be between 1 and 3600 seconds")
        source = _safe_tree(Path(source_dir), "source")
        bundle = _safe_tree(Path(bundle_dir), "bundle")
        entrypoint = _entrypoint(entrypoint, runtime, bundle)
        if production_entrypoint:
            selected_path, separator, selected_function = production_entrypoint.rpartition(":")
            relative = PurePosixPath(selected_path)
            if (not separator or not selected_path or relative.is_absolute() or ".." in relative.parts
                    or "\\" in selected_path or not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$.]*", selected_function)
                    or not source.joinpath(*relative.parts).is_file()):
                raise ValueError("production entrypoint must identify a source file and qualified callable")
        output = Path(output_dir)
        ensure_unlinked(output)
        output = output.resolve()
        if output == source or source in output.parents or output == bundle or bundle in output.parents:
            raise ValueError("output directory must be separate from source and bundle")
        output.mkdir(parents=True, exist_ok=True)
        if not output.is_dir() or any(output.iterdir()):
            raise ValueError("output directory must be empty")
        prerequisite = self.status()
        result = {"status": "failed", "backend": "docker", "image_digest": prerequisite["image_digest"],
                  "command": [runtime, f"/code/{entrypoint}"], "limits": {**LIMITS, "timeout_seconds": timeout_seconds},
                  "artifacts": [], "output_path": None, "stdout": "", "stderr": "", "exit_code": None}
        result.update({"production_entrypoint": production_entrypoint or None, "production_calls": [],
                       "coverage_truncated": False, "coverage_mechanism": {"python": "python-profile", "node": "node-v8-coverage"}[runtime]})
        if not prerequisite["ready"]:
            result["stderr"] = prerequisite["reason"]
            return result
        if cancel and cancel():
            result["status"] = "cancelled"
            return result
        name = CONTAINER_PREFIX + uuid.uuid4().hex
        staging = tempfile.TemporaryDirectory(prefix="paper-factory-sandbox-")
        staged_source, staged_bundle = Path(staging.name) / "input", Path(staging.name) / "code"
        try:
            _stage_tree(source, staged_source)
            _stage_tree(bundle, staged_bundle)
        except BaseException:
            staging.cleanup()
            raise
        options = ["create", "--name", name, "--init", "--network", "none", "--read-only",
                   "--user", "65532:65532", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                   "--pids-limit", "128", "--memory", "512m", "--memory-swap", "512m", "--cpus", "1",
                   "--ulimit", "nofile=256:256", "--ulimit", f"fsize={MAX_ARTIFACT_BYTES}:{MAX_ARTIFACT_BYTES}",
                   "--ipc", "none", "--cgroupns", "private", "--log-driver", "none",
                   "--tmpfs", "/work:rw,nosuid,nodev,noexec,size=256m,uid=65532,gid=65532,mode=0700",
                   "--tmpfs", "/output:rw,nosuid,nodev,noexec,size=64m,uid=65532,gid=65532,mode=0700",
                   "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m,uid=65532,gid=65532,mode=0700",
                   "--mount", f"type=bind,src={staged_source},dst=/input,readonly,bind-propagation=rprivate",
                   "--mount", f"type=bind,src={staged_bundle},dst=/code,readonly,bind-propagation=rprivate",
                   "--workdir", "/work", "--env", "HOME=/work", "--env", "PYTHONDONTWRITEBYTECODE=1",
                   "--env", "PYTHONNOUSERSITE=1", "--env", "PATH=/usr/local/bin:/usr/bin:/bin",
                   prerequisite["image_digest"], "/usr/local/bin/python3", "-c", _LAUNCHER, runtime,
                   entrypoint, str(timeout_seconds), str(MAX_ARTIFACT_BYTES), str(MAX_LOG_BYTES)]
        started = time.monotonic()
        process = None
        container_id = None
        overflow = threading.Event()
        streams = {"stdout": bytearray(), "stderr": bytearray()}
        threads: list[threading.Thread] = []
        try:
            created = self._control(options)
            if created.returncode:
                result["stderr"] = created.stderr[:MAX_LOG_BYTES]
                return result
            container_id = created.stdout.strip()
            if not re.fullmatch(r"[0-9a-f]{64}", container_id):
                result["stderr"] = "Docker returned an invalid container identifier"
                return result
            if on_handle:
                on_handle({"kind": "container", "container_id": container_id, "container_name": name,
                           "image_digest": prerequisite["image_digest"]})
            process = subprocess.Popen([self.docker, "start", "--attach", name],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            def drain(pipe, key: str, limit: int) -> None:
                try:
                    while True:
                        part = pipe.read(65536)
                        if not part:
                            return
                        room = max(0, limit - len(streams[key]))
                        streams[key].extend(part[:room])
                        if len(part) > room:
                            overflow.set()
                            return
                finally:
                    pipe.close()
            for key, pipe, limit in [("stdout", process.stdout, MAX_TRANSPORT_BYTES),
                                     ("stderr", process.stderr, MAX_LOG_BYTES)]:
                thread = threading.Thread(target=drain, args=(pipe, key, limit), daemon=True)
                threads.append(thread)
                thread.start()
            while process.poll() is None:
                if cancel and cancel():
                    result["status"] = "cancelled"
                    break
                if time.monotonic() - started >= timeout_seconds + 3:
                    result["status"] = "timeout"
                    break
                if overflow.is_set():
                    result["stderr"] = "Sandbox output exceeded the bounded transport limit"
                    break
                time.sleep(0.05)
            if process.poll() is None:
                self._control(["kill", name], timeout=5)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            for thread in threads:
                thread.join(timeout=2)
            result["exit_code"] = process.returncode
            if result["status"] in {"cancelled", "timeout"} or overflow.is_set():
                return result
            try:
                envelope = json.loads(streams["stdout"].decode("utf-8"))
                if not isinstance(envelope, dict) or envelope.get("protocol") != PROTOCOL:
                    raise ValueError("invalid runner protocol")
                for key in ("stdout", "stderr"):
                    if not isinstance(envelope.get(key), str):
                        raise ValueError("invalid runner log")
                    result[key] = _bounded_log(envelope[key])
                if envelope.get("timed_out"):
                    result["status"] = "timeout"
                    return result
                exit_code = envelope.get("exit_code")
                if type(exit_code) is not int:
                    raise ValueError("invalid experiment exit code")
                result["exit_code"] = exit_code
                succeeded = process.returncode == 0 and exit_code == 0 and not envelope.get("error")
                if not succeeded:
                    result["stderr"] += "\n" + str(envelope.get("error") or "Experiment exited unsuccessfully")[:1000]
                    if exit_code == 0 or envelope.get("observation_b64") is None:
                        return result
                encoded = envelope.get("observation_b64")
                if not isinstance(encoded, str) or len(encoded) > (MAX_ARTIFACT_BYTES + 2) // 3 * 4:
                    raise ValueError("invalid or oversized observation transport")
                data = base64.b64decode(encoded, validate=True)
                if not succeeded:
                    result.update(_retain_observations(output, data))
                result["production_calls"] = _production_calls(envelope.get("production_calls", []), source)
                if not isinstance(envelope.get("coverage_truncated", False), bool):
                    raise ValueError("invalid coverage truncation marker")
                result["coverage_truncated"] = envelope.get("coverage_truncated", False)
                if succeeded:
                    result.update(_retain_observations(output, data), status="succeeded")
            except (ValueError, UnicodeError, binascii.Error, OSError, RecursionError) as exc:
                result["stderr"] += "\nSandbox artifact export rejected: " + str(exc)[:1000]
            return result
        except (OSError, subprocess.TimeoutExpired) as exc:
            result["stderr"] = "Docker execution failed: " + str(exc)[:1000]
            return result
        finally:
            if process is not None and process.poll() is None:
                try:
                    process.kill()
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    # The Docker removal below is the authoritative cleanup.
                    pass
            try:
                removed = self._control(["rm", "--force", name], timeout=5)
                cleanup_confirmed = removed.returncode == 0 or "No such container" in removed.stderr
            except (OSError, subprocess.TimeoutExpired):
                cleanup_confirmed = False
            result["cleanup_confirmed"] = cleanup_confirmed
            if not cleanup_confirmed:
                result.update(status="blocked", code="CLEANUP_UNCONFIRMED",
                              error="Research container removal could not be confirmed; restore Docker connectivity before resuming.",
                              active_handle={"kind": "container", "container_id": container_id,
                                             "container_name": name, "image_digest": prerequisite["image_digest"]})
            staging.cleanup()
            result["stdout"] = _bounded_log(result["stdout"])
            result["stderr"] = _bounded_log(result["stderr"])
            result["duration_seconds"] = round(time.monotonic() - started, 3)


def research_runner():
    """Select the platform's enforced research boundary without a host fallback."""
    if os.name == "nt":
        from .windows_runner import WindowsRunner
        return WindowsRunner()
    return DockerRunner()

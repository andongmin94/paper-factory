"""Native Windows research execution with AppContainer and a bounded Job Object.

Research inputs use a staged interpreter, its standard library and vetted packages.
Windows may also expose standard OS resources through its AppContainer ACLs.
The native controller denies network
capabilities and confirms termination of the complete process tree before any
observation crosses back into the workspace.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import sysconfig
import tempfile
import time

from ..workspace import ensure_unlinked, loads_json
from .runner import (
    LIMITS, MAX_ARTIFACT_BYTES, _PYTHON_DRIVER, _bounded_log, _entrypoint,
    _production_calls, _retain_observations, _safe_tree, _stage_tree,
)


# The allowlist is controller-owned; generated plans cannot install packages.
_PACKAGE_GROUPS = (
    {
        "mido": ("1.3.3", "mido"),
        "packaging": ("26.3", "packaging"),
    },
    {
        "pydantic": ("2.13.5", "pydantic"),
        "pydantic_core": ("2.46.5", "pydantic_core"),
        "annotated_types": ("0.8.0", "annotated_types"),
        "typing_extensions": ("4.16.0", "typing_extensions.py"),
        "typing_inspection": ("0.4.4", "typing_inspection"),
    },
    {
        "httpx": ("0.28.1", "httpx"),
        "httpcore": ("1.0.9", "httpcore"),
        "certifi": ("2026.7.22", "certifi"),
        "h11": ("0.16.0", "h11"),
        "anyio": ("4.15.1", "anyio"),
        "idna": ("3.20", "idna"),
    },
)
_STAGING_PREFIX = "paper-factory-windows-"
_STAGING_CLEANUP_SECONDS = 3.0


def _read_bytes(path: Path, limit: int) -> bytes:
    ensure_unlinked(path)
    before = path.stat(follow_symlinks=False)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    try:
        info = os.fstat(descriptor)
        ensure_unlinked(path)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit
                or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino)):
            raise ValueError("Sandbox artifact must be an unchanged bounded regular file with one link")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read(limit + 1)
        if len(content) > limit:
            raise ValueError("Sandbox artifact exceeds its size limit")
        return content
    finally:
        os.close(descriptor)


def _json(path: Path, limit: int):
    return loads_json(_read_bytes(path, limit).decode("utf-8"))


def _copy_runtime_tree(source: Path, target: Path) -> None:
    ensure_unlinked(source)
    if not source.is_dir():
        raise ValueError("Native runtime directory is unavailable")
    target.mkdir(parents=True, exist_ok=True)
    excluded = {"site-packages", "__pycache__", "test", "tests", "idlelib", "tkinter", "turtledemo", "ensurepip"}
    for parent, directories, files in os.walk(source, followlinks=False):
        directories[:] = [name for name in directories if name not in excluded]
        relative = Path(parent).relative_to(source)
        for name in directories:
            ensure_unlinked(Path(parent) / name)
            (target / relative / name).mkdir(exist_ok=True)
        for name in files:
            path = Path(parent) / name
            if path.suffix in {".pyc", ".pyo", ".pdb", ".lib"} or name == "direct_url.json" or name.startswith(("_tkinter", "_test", "_ctypes_test")):
                continue
            ensure_unlinked(path)
            if not path.is_file():
                raise ValueError("Native runtime contains a nonregular file")
            shutil.copyfile(path, target / relative / name)


def _packages() -> dict:
    selected = {}
    for group in _PACKAGE_GROUPS:
        found = {}
        try:
            for name, (version, module) in group.items():
                distribution = importlib.metadata.distribution(name)
                path = Path(distribution.locate_file(module))
                ensure_unlinked(path)
                if distribution.version != version or not path.exists():
                    raise ValueError("Vetted dependency version is unavailable")
                metadata = [entry for entry in distribution.files or []
                            if entry.name == "METADATA" and entry.parts[0].endswith(".dist-info")]
                if len(metadata) != 1:
                    raise ValueError("Vetted dependency metadata is unavailable")
                found[name] = {"version": version, "module": path,
                               "metadata": Path(distribution.locate_file(metadata[0])).parent}
        except (importlib.metadata.PackageNotFoundError, OSError, ValueError):
            continue
        selected.update(found)
    return selected


def _node_runtime() -> tuple[Path | None, str | None]:
    executable = shutil.which(os.environ.get("PF_NODE_BIN") or "node")
    if not executable or Path(executable).suffix.casefold() != ".exe":
        return None, None
    path = Path(executable)
    ensure_unlinked(path)
    environment = {name: value for name, value in os.environ.items() if name.upper() in {"SYSTEMROOT", "WINDIR"}}
    try:
        probe = subprocess.run([str(path), "--version"], capture_output=True, timeout=5, check=False, env=environment)
        version = probe.stdout[:100].decode("ascii", "strict").strip()
        if probe.returncode or not version.startswith("v") or any(character not in "0123456789.v-" for character in version):
            return None, None
        return path, version.removeprefix("v")
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        return None, None


def _checked_staging(path: Path) -> None:
    # Cleanup accepts only a direct child of the OS temp directory with the
    # controller's unique prefix; never a linked or arbitrary host directory.
    ensure_unlinked(path)
    if path.parent.resolve() != Path(tempfile.gettempdir()).resolve() or not path.name.startswith(_STAGING_PREFIX):
        raise ValueError("Refusing an unrelated staging cleanup path")


def _remove_staging(path: Path) -> None:
    def writable_retry(function, target, error):
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
        function(target)
    deadline = time.monotonic() + _STAGING_CLEANUP_SECONDS
    while True:
        _checked_staging(path)
        if not path.exists():
            return
        try:
            shutil.rmtree(path, onerror=writable_retry)
            return
        except OSError as error:
            # Loaded DLLs can remain briefly locked after the complete Job
            # tree has exited. Retry only Windows sharing/access violations.
            if getattr(error, "winerror", None) not in {5, 32, 33} or time.monotonic() >= deadline:
                raise
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))


class WindowsRunner:
    """A native restricted worker; unavailable isolation always blocks execution."""

    def status(self) -> dict:
        from . import windows_runtime
        result = {"ready": False, "reason": None, "backend": "windows-appcontainer",
                  "image_digest": None, "runtimes": [], "dependencies": [], "versions": {}}
        if os.name != "nt" or not windows_runtime.available():
            result["reason"] = "Windows AppContainer and Job Object isolation is unavailable"
            return result
        base = Path(sys.base_prefix)
        ensure_unlinked(base)
        if not (base / "python.exe").is_file() or not Path(sysconfig.get_path("stdlib")).is_dir():
            result["reason"] = "A complete native Python runtime and standard library are required"
            return result
        result["runtimes"] = ["python"]
        result["versions"]["python"] = sys.version.split()[0]
        node, node_version = _node_runtime()
        if node:
            result["runtimes"].append("node")
            result["versions"]["node"] = node_version
        packages = _packages()
        result["dependencies"] = list(packages)
        result["versions"].update({name: item["version"] for name, item in packages.items()})
        result["ready"] = True
        return result

    def stop(self, handle: dict) -> bool:
        from . import windows_runtime
        if not isinstance(handle, dict) or handle.get("kind") != "windows-experiment":
            return False
        confirmed = windows_runtime.stop(handle)
        if confirmed and handle.get("staging_root"):
            path = Path(handle["staging_root"])
            try:
                _checked_staging(path)
                if path.exists():
                    # The terminated AppContainer's read ACE remains on this
                    # tree. Restore its private DACL before deleting its files.
                    windows_runtime.private_path(path)
                    if not windows_runtime.is_private_path(path):
                        return False
                    _remove_staging(path)
            except (OSError, ValueError):
                return False
        return confirmed

    def _stage_runtime(self, root: Path) -> tuple[Path, Path | None, dict]:
        base = Path(sys.base_prefix)
        python = root / "python"
        python.mkdir()
        major_minor = f"{sys.version_info.major}{sys.version_info.minor}"
        for name in ("python.exe", "python3.dll", f"python{major_minor}.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
            source = base / name
            if source.exists():
                ensure_unlinked(source)
                shutil.copyfile(source, python / name)
        _copy_runtime_tree(Path(sysconfig.get_path("stdlib")), python / "Lib")
        if (base / "DLLs").is_dir():
            _copy_runtime_tree(base / "DLLs", python / "DLLs")
        # Explicit search paths omit site initialization, user packages and .pth
        # execution even when the original interpreter came from a virtualenv.
        (python / f"python{major_minor}._pth").write_text("Lib\nDLLs\n.\nLib/site-packages\n", encoding="utf-8")
        site = python / "Lib" / "site-packages"
        site.mkdir(exist_ok=True)
        packages = _packages()
        for item in packages.values():
            module = item["module"]
            if module.is_dir():
                _copy_runtime_tree(module, site / module.name)
            else:
                shutil.copyfile(module, site / module.name)
            _copy_runtime_tree(item["metadata"], site / item["metadata"].name)
        node_path, node_version = _node_runtime()
        node = None
        if node_path:
            node = root / "node.exe"
            shutil.copyfile(node_path, node)
        manifest = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(root.rglob("*")) if path.is_file()}
        digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        versions = {"python": sys.version.split()[0], **{name: item["version"] for name, item in packages.items()}}
        if node:
            versions["node"] = node_version
        return python / "python.exe", node, {"sha256": digest, "files_sha256": manifest, "versions": versions}

    def run(self, source_dir: Path, bundle_dir: Path, output_dir: Path, *, runtime: str,
            entrypoint: str, timeout_seconds: int = 300, production_entrypoint: str = "",
            cancel=None, on_handle=None) -> dict:
        from . import windows_runtime
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 3600:
            raise ValueError("experiment timeout must be between 1 and 3600 seconds")
        source, bundle = _safe_tree(Path(source_dir), "source"), _safe_tree(Path(bundle_dir), "bundle")
        entrypoint = _entrypoint(entrypoint, runtime, bundle)
        output = Path(output_dir)
        ensure_unlinked(output)
        output = output.resolve()
        if output == source or source in output.parents or output == bundle or bundle in output.parents:
            raise ValueError("output directory must be separate from source and bundle")
        output.mkdir(parents=True, exist_ok=True)
        if any(output.iterdir()):
            raise ValueError("output directory must be empty")
        result = {"status": "failed", "backend": "windows-appcontainer", "image_digest": None,
                  "runtime_digest": None, "command": [runtime, entrypoint], "artifacts": [], "output_path": None,
                  "stdout": "", "stderr": "", "exit_code": None, "production_calls": [],
                  "production_entrypoint": production_entrypoint or None, "coverage_truncated": False,
                  "coverage_mechanism": "python-profile" if runtime == "python" else "node-v8-coverage",
                  "limits": {**LIMITS, "uid": None, "read_only_root": False, "timeout_seconds": timeout_seconds,
                             "disk_enforcement": "monitored writable-directory bounds; no filesystem quota",
                             "filesystem": "AppContainer ACLs: read-only source/code/runtime; private writable work/output/tmp"}}
        status = self.status()
        if not status["ready"] or runtime not in status["runtimes"]:
            result["stderr"] = status["reason"] or "Requested native runtime is unavailable"
            return result
        if cancel and cancel():
            result["status"] = "cancelled"
            return result
        staging = Path(tempfile.mkdtemp(prefix=_STAGING_PREFIX))
        cleanup_confirmed = True
        execution_handle = {}
        started = time.monotonic()
        try:
            windows_runtime.private_path(staging)
            staged_source, staged_code = staging / "source", staging / "code"
            _stage_tree(source, staged_source)
            _stage_tree(bundle, staged_code)
            native = staging / "runtime"
            native.mkdir()
            python, node, manifest = self._stage_runtime(native)
            result["runtime_digest"] = manifest["sha256"]
            (output / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            work, observations, temporary = staging / "work", staging / "output", staging / "tmp"
            for path in (work, observations, temporary):
                path.mkdir()
            appdata, local_appdata = work / "AppData" / "Roaming", work / "AppData" / "Local"
            appdata.mkdir(parents=True)
            local_appdata.mkdir(parents=True)
            environment = {"SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
                           "WINDIR": os.environ.get("WINDIR", r"C:\Windows"), "HOME": str(work),
                           "USERPROFILE": str(work), "TEMP": str(temporary), "TMP": str(temporary),
                           "APPDATA": str(appdata), "LOCALAPPDATA": str(local_appdata),
                           "PATH": str(python.parent), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
                           "PYTHONHASHSEED": "0", "PF_SOURCE_ROOT": str(staged_source), "PF_CODE_ROOT": str(staged_code),
                           "PF_OUTPUT_ROOT": str(observations), "PF_INPUT": str(staged_source), "PF_OUTPUT": str(observations),
                           "PF_WORK": str(work)}
            if runtime == "python":
                driver = staging / "controller.py"
                driver.write_text(_PYTHON_DRIVER, encoding="utf-8")
                command = [str(python), "-I", str(driver), str(staged_code / entrypoint)]
                readonly = [staging, staged_source, staged_code, native, driver]
            else:
                environment["NODE_V8_COVERAGE"] = str(observations / ".paper-factory-node-coverage")
                # Node's realpath walk otherwise enumerates drive ancestors
                # outside the AppContainer's granted staging tree. All staged
                # inputs already reject links, so preserve their checked paths.
                command = [str(node), "--preserve-symlinks", "--preserve-symlinks-main", str(staged_code / entrypoint)]
                readonly = [staging, staged_source, staged_code, native]
            def retained(handle):
                nonlocal execution_handle
                handle = {**handle, "staging_root": str(staging)}
                execution_handle = handle.copy()
                if on_handle:
                    on_handle(handle)
            # A launch exception is never evidence that its worker terminated.
            # Only the native controller's returned receipt can permit ACL
            # restoration or deletion of a tree already exposed to a worker.
            cleanup_confirmed = False
            execution = windows_runtime.launch(command, cwd=work, environment=environment,
                       read_only_paths=readonly, writable_paths=[work, observations, temporary],
                       timeout_seconds=timeout_seconds, cancel=cancel, on_handle=retained, limits=result["limits"])
            cleanup_confirmed = execution.get("cleanup_confirmed") is True
            execution_handle = {**execution.get("handle", execution_handle), "staging_root": str(staging)}
            result.update({key: execution[key] for key in ("status", "exit_code", "stdout", "stderr") if key in execution})
            result["cleanup_confirmed"] = cleanup_confirmed
            if not cleanup_confirmed:
                result.update(status="blocked", code="CLEANUP_UNCONFIRMED",
                              error="Native research process-tree termination could not be confirmed",
                              active_handle=execution_handle)
                return result
            succeeded = result["status"] == "succeeded" and result["exit_code"] == 0
            failed_exit = result["status"] == "failed" and type(result["exit_code"]) is int and result["exit_code"] != 0
            if not succeeded and not failed_exit:
                return result
            if failed_exit:
                result.update(_retain_observations(output, _read_bytes(observations / "observations.json", MAX_ARTIFACT_BYTES)))
            try:
                if runtime == "python":
                    trace = _json(observations / ".paper-factory-python-calls.json", 1024 * 1024)
                    calls, truncated = trace["calls"], trace["truncated"]
                else:
                    from urllib.parse import unquote, urlsplit
                    coverage = observations / ".paper-factory-node-coverage"
                    ensure_unlinked(coverage)
                    paths = sorted(coverage.glob("coverage-*.json"))
                    totals, truncated = {}, len(paths) > 32
                    for path in paths[:32]:
                        for script in _json(path, 4 * 1024 * 1024).get("result", []):
                            url = urlsplit(script.get("url", ""))
                            if url.scheme != "file" or url.netloc:
                                continue
                            actual = Path(unquote(url.path).lstrip("/"))
                            try:
                                relative = actual.resolve().relative_to(staged_source.resolve()).as_posix()
                            except (ValueError, OSError):
                                continue
                            for function in script.get("functions", []):
                                name, ranges = function.get("functionName", ""), function.get("ranges", [])
                                if not name or not ranges:
                                    continue
                                count = ranges[0].get("count", 0)
                                if type(count) is not int or count < 1:
                                    continue
                                key = (relative, name)
                                if key not in totals and len(totals) >= 512:
                                    truncated = True
                                    continue
                                totals[key] = min(totals.get(key, 0) + count, 1_000_000_000)
                    calls = [{"path": path, "function": name, "calls": count} for (path, name), count in sorted(totals.items())]
                result["production_calls"] = _production_calls(calls, source)
                if type(truncated) is not bool:
                    raise ValueError("Invalid coverage truncation marker")
                result["coverage_truncated"] = truncated
            except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
                if succeeded:
                    raise
                result["stderr"] += "\nFailed execution trace unavailable: " + str(error)[:1000]
                return result
            if succeeded:
                result.update(_retain_observations(output, _read_bytes(observations / "observations.json", MAX_ARTIFACT_BYTES)))
        except Exception as error:
            result.update(status="failed", stderr=result["stderr"] + "\nNative sandbox execution rejected: " + str(error)[:1000])
            if not cleanup_confirmed:
                result.update(status="blocked", code="CLEANUP_UNCONFIRMED", cleanup_confirmed=False,
                              error="Native research launch failed without a confirmed cleanup receipt",
                              active_handle={"kind": "windows-experiment", **execution_handle,
                                             "staging_root": str(staging)})
        finally:
            if cleanup_confirmed:
                try:
                    _checked_staging(staging)
                    windows_runtime.private_path(staging)
                    if not windows_runtime.is_private_path(staging):
                        raise ValueError("Native staging cleanup requires a restored private DACL")
                    _remove_staging(staging)
                except (OSError, ValueError) as error:
                    result.update(status="blocked", code="CLEANUP_UNCONFIRMED", cleanup_confirmed=False,
                                  process_cleanup_confirmed=True,
                                  error="Native research staging cleanup could not be confirmed: " + str(error)[:1000],
                                  active_handle={"kind": "windows-experiment", **execution_handle,
                                                 "staging_root": str(staging)})
            result["stdout"] = _bounded_log(result["stdout"])
            result["stderr"] = _bounded_log(result["stderr"])
            result["duration_seconds"] = round(time.monotonic() - started, 3)
        return result

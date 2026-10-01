"""Structured model generation through the official, already-authenticated CLI.

Authentication files are never inspected, copied, or rewritten by this adapter.
The CLI uses its supplied authentication home, or an explicitly connected
private profile. Only noncredential SQLite/log state is directed to the
disposable call runtime. The process's supplied CODEX_HOME remains unchanged.
"""

from __future__ import annotations

import hashlib
import copy
import json
import math
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
import time
from uuid import uuid4
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from ..workspace import ensure_unlinked, pf_home, safe_relative, write_json

MAX_PROMPT_BYTES = 1024 * 1024
MAX_SCHEMA_BYTES = 256 * 1024
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_LOG_BYTES = 128 * 1024
DISABLED_FEATURES = (
    "shell_tool", "unified_exec", "code_mode", "code_mode_host", "apps", "plugins",
    "remote_plugin", "browser_use", "browser_use_external", "computer_use",
    "multi_agent", "multi_agent_v2", "hooks", "skill_search", "view_image",
    "image_generation", "workspace_dependencies", "memories",
    "in_app_browser", "tool_suggest", "unbounded_connection_retries",
)
SAFE_ENV_NAMES = frozenset({
    "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "SYSTEMROOT", "WINDIR",
    "SYSTEMDRIVE", "COMSPEC", "PATHEXT", "TMP", "TEMP", "TMPDIR", "CODEX_HOME",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY",
    "https_proxy", "http_proxy", "all_proxy", "no_proxy",
    "REQUESTS_CA_BUNDLE", "CODEX_PROXY_CERT", "NODE_EXTRA_CA_CERTS", "GRPC_DEFAULT_SSL_ROOTS_FILE_PATH",
})


class ProviderBlocked(RuntimeError):
    """A classified model prerequisite, interruption, or invalid response."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _private_directory(path: Path) -> Path:
    path = Path(path).expanduser().absolute()
    ensure_unlinked(path)
    metadata = path.stat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_mode & 0o077 or (hasattr(os, "getuid") and metadata.st_uid != os.getuid()):
        raise ValueError("unsafe authentication profile directory")
    # Managed sandboxes can expose empty .git permission placeholders at their
    # writable roots. A checkout has a gitfile or a directory with HEAD state.
    if any((parent / ".git").is_file() or (parent / ".git").is_symlink() or (parent / ".git" / "HEAD").is_file()
           for parent in (path, *path.parents)):
        raise ValueError("authentication profile is inside a Git checkout")
    return path.resolve()


def auth_root() -> Path:
    """Return the explicit private connection root without creating it."""
    try:
        configured = os.environ.get("PF_CODEX_AUTH_HOME")
        root = Path(configured).expanduser() if configured and configured.strip() else pf_home() / "codex-auth"
        ensure_unlinked(root)
        return root.absolute()
    except (OSError, ValueError):
        raise ProviderBlocked("CONFIGURATION_ERROR", "The Codex connection root is unavailable or unsafe.") from None


def resolve_auth_home(root: Path | None = None) -> Path | None:
    """Read only the owned nonsecret selection pointer, never auth files.

    An absent pointer retains the environment's original official CLI binding.
    Selected connections must have been verified by the separate auth manager.
    """
    try:
        if root is None:
            root = auth_root()
        root = Path(root).expanduser().absolute()
        ensure_unlinked(root)
        pointer = root / "active.json"
        ensure_unlinked(pointer)
        if not pointer.exists():
            return None
        root = _private_directory(root)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(pointer, flags), "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 16384 or metadata.st_mode & 0o077 or
                    hasattr(os, "getuid") and metadata.st_uid != os.getuid()):
                raise ValueError("unsafe selection pointer")
            raw = stream.read(16385)
        if len(raw) > 16384:
            raise ValueError("selection pointer too large")
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("duplicate selection field")
                result[key] = value
            return result
        selection = json.loads(raw, object_pairs_hook=pairs)
        if (not isinstance(selection, dict) or set(selection) - {"version", "profile", "verified", "verified_at"} or
                type(selection.get("version")) is not int or selection["version"] != 1 or selection.get("verified") is not True or
                not isinstance(selection.get("profile"), str) or not re.fullmatch(r"profiles/[a-f0-9]{32}", selection["profile"])):
            raise ValueError("invalid selection pointer")
        if "verified_at" in selection:
            timestamp = selection["verified_at"]
            if not isinstance(timestamp, str) or len(timestamp) > 80:
                raise ValueError("invalid verification timestamp")
            verified_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if verified_at.tzinfo is None or verified_at.utcoffset() != timezone.utc.utcoffset(verified_at):
                raise ValueError("verification timestamp must be UTC")
        profiles = _private_directory(root / "profiles")
        home = _private_directory(safe_relative(root, selection["profile"]))
        if home.parent != profiles:
            raise ValueError("selection escaped profiles")
        return home
    except (OSError, ValueError, TypeError, UnicodeError):
        raise ProviderBlocked("CONFIGURATION_ERROR", "The selected Codex connection metadata or private profile directory is invalid.") from None


def _environment(auth_home: Path | None = None) -> dict[str, str]:
    # Keep official authentication bindings and OS transport settings. Author,
    # publication credentials, cloud tokens, and API keys are not inherited.
    environment = {name: value for name, value in os.environ.items() if name in SAFE_ENV_NAMES}
    if auth_home is not None:
        environment["CODEX_HOME"] = str(auth_home)
    return environment


def _sensitive_values() -> list[str]:
    values = set()
    for name, value in os.environ.items():
        if re.search(r"TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|(?:^|_)(?:KEY|PAT|JWT|BEARER|COOKIE)(?:_|$)", name, re.I) and len(value) >= 4:
            values.add(value)
            values.update(line for line in value.splitlines() if len(line) >= 4)
    return sorted(values, key=len, reverse=True)


def _redact(text: str, sensitive: list[str]) -> str:
    for value in sensitive:
        text = text.replace(value, "[redacted]")
    # Bound the scheme scan: an unbounded prefix causes quadratic searching
    # on large lines without any URL and can stall worker supervision.
    text = re.sub(r"([A-Za-z][A-Za-z0-9+.-]{0,31}://)[^/\s@]+@", r"\1[redacted]@", text)
    text = re.sub(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{10,}\b", "[redacted]", text)
    text = re.sub(r"(?i)(bearer\s+)[^\s\"']+", r"\1[redacted]", text)
    text = re.sub(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", "[redacted]", text)
    text = re.sub(r"(?i)([\"']?(?:access_token|refresh_token|id_token|api_key|authorization)[\"']?\s*[:=]\s*[\"']?)[^\s,\"'}]+",
                  r"\1[redacted]", text)
    return text


def _bounded_text(text: str, maximum_bytes: int) -> str:
    """Keep UTF-8 artifacts within their byte limit without split characters."""
    return text.encode("utf-8")[:maximum_bytes].decode("utf-8", errors="ignore")


def _start_ticks(pid: int) -> int | None:
    if os.name != "posix" or not Path("/proc").is_dir():
        return None
    try:
        content = Path(f"/proc/{pid}/stat").read_text()
        # comm can contain spaces or parentheses; subsequent fields begin after
        # its final closing parenthesis. starttime is field 22, index 19 here.
        return int(content.rsplit(")", 1)[1].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _group_running(pgid: int) -> bool:
    if Path("/proc").is_dir():
        for entry in Path("/proc").glob("[0-9]*/stat"):
            try:
                fields = entry.read_text().rsplit(")", 1)[1].split()
                if int(fields[2]) == pgid and fields[0] not in {"Z", "X"}:
                    return True
            except (OSError, ValueError, IndexError):
                continue
        return False
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


def _stop(process: subprocess.Popen) -> bool:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=15, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=5)
    if os.name != "nt":
        # The leader can exit after SIGTERM while its descendants ignore it.
        # Reaping that leader therefore does not establish group termination.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 1
        while _group_running(process.pid) and time.monotonic() < deadline:
            time.sleep(0.02)
        return not _group_running(process.pid)
    return process.poll() is not None


def _try_stop(process: subprocess.Popen) -> bool:
    try:
        return _stop(process)
    except (OSError, subprocess.TimeoutExpired):
        return False


def _classify(diagnostic: str) -> ProviderBlocked:
    value = diagnostic.casefold()
    if any(text in value for text in ("rate limit", "usage limit", "quota", "429", "too many requests")):
        return ProviderBlocked("RATE_LIMITED", "Codex usage is temporarily unavailable; resume after the reported account limit resets.")
    # Proxy CONNECT failures can mention authentication too. Their HTTP status
    # describes a transport denial, rather than the model account's login.
    if "403" in value and ("proxy" in value or "connect" in value):
        return ProviderBlocked("NETWORK_ERROR", "The environment proxy denied the Codex model request with HTTP CONNECT 403.")
    if any(text in value for text in ("not logged in", "unauthorized", "authentication", "please log in", "please login", "401", "refresh token", "invalid api key")):
        return ProviderBlocked("AUTH_REQUIRED", "The official Codex CLI requires a usable existing login; authentication was not modified.")
    if any(text in value for text in ("read-only file system", "failed to initialize", "configuration", "config.toml", "permission denied")):
        return ProviderBlocked("CONFIGURATION_ERROR", "Codex could not initialize its runtime with the available configuration or filesystem permissions.")
    if any(text in value for text in ("schema", "response_format", "invalid json")):
        return ProviderBlocked("SCHEMA_ERROR", "Codex could not produce the required structured response.")
    if any(text in value for text in ("network", "connection", "websocket", "dns", "resolve host", "transport", "proxy", "403", "502", "503", "504")):
        return ProviderBlocked("NETWORK_ERROR", "Codex could not reach its model service; resume after connectivity is restored.")
    return ProviderBlocked("CODEX_FAILED", "The official Codex CLI failed; inspect the bounded, sanitized call diagnostics.")


def _schema_validator(schema: dict) -> Draft202012Validator:
    if not isinstance(schema, dict):
        raise ProviderBlocked("SCHEMA_ERROR", "The generation schema must be a JSON object.")
    def visit(value, depth=0):
        if depth > 80:
            raise ProviderBlocked("SCHEMA_ERROR", "The generation schema exceeds the nesting limit.")
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"$ref", "$dynamicRef"} and isinstance(child, str) and not child.startswith("#"):
                    raise ProviderBlocked("SCHEMA_ERROR", "Generation schemas may reference only local definitions.")
                visit(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                visit(child, depth + 1)
    visit(schema)
    try:
        Draft202012Validator.check_schema(schema)
        encoded = json.dumps(schema, allow_nan=False).encode()
        if len(encoded) > MAX_SCHEMA_BYTES:
            raise ProviderBlocked("SCHEMA_ERROR", "The generation schema exceeds 256 KiB.")
        return Draft202012Validator(schema)
    except (SchemaError, TypeError, ValueError):
        raise ProviderBlocked("SCHEMA_ERROR", "The generation schema is invalid.") from None


def _wire_schema(schema: dict) -> dict:
    """Close structured objects and encode typed arbitrary maps as entry lists."""
    def normalize(node, depth=0):
        if depth > 80 or not isinstance(node, dict):
            raise ProviderBlocked("SCHEMA_ERROR", "Structured generation requires bounded explicit schema objects.")
        result = copy.deepcopy(node)
        result.pop("default", None)
        for name in ("$defs", "definitions", "dependentSchemas"):
            if name in node:
                result[name] = {key: normalize(value, depth + 1) for key, value in node[name].items()}
        for name in ("anyOf", "oneOf", "allOf", "prefixItems"):
            if name in node:
                result[name] = [normalize(value, depth + 1) for value in node[name]]
        for name in ("items", "contains", "not", "if", "then", "else", "propertyNames", "contentSchema"):
            if name in node:
                result[name] = normalize(node[name], depth + 1)
        if node.get("type") == "object" or "properties" in node or "additionalProperties" in node:
            if "patternProperties" in node or isinstance(node.get("type"), list):
                raise ProviderBlocked("SCHEMA_ERROR", "Pattern or mixed-type objects are unsupported by structured generation.")
            properties = node.get("properties", {})
            additional = node.get("additionalProperties", True)
            if isinstance(additional, dict):
                if properties:
                    raise ProviderBlocked("SCHEMA_ERROR", "Objects combining fixed fields with arbitrary keys are unsupported.")
                value_schema = normalize(additional, depth + 1)
                if not value_schema or not any(key in value_schema for key in ("type", "$ref", "anyOf", "oneOf", "allOf", "enum", "const")):
                    raise ProviderBlocked("SCHEMA_ERROR", "Arbitrary map values require an explicit typed schema.")
                mapped = {key: value for key, value in result.items()
                          if key not in {"type", "additionalProperties", "properties", "required", "propertyNames", "minProperties", "maxProperties"}}
                mapped.update(type="array", items={"type": "object", "properties": {
                    "key": result.get("propertyNames", {"type": "string"}), "value": value_schema},
                    "required": ["key", "value"], "additionalProperties": False})
                mapped["items"]["properties"]["key"].setdefault("type", "string")
                for original, replacement in (("minProperties", "minItems"), ("maxProperties", "maxItems")):
                    if original in node:
                        mapped[replacement] = node[original]
                return mapped
            if not properties and additional is not False:
                raise ProviderBlocked("SCHEMA_ERROR", "Untyped arbitrary objects are unsupported by structured generation.")
            result["properties"] = {key: normalize(value, depth + 1) for key, value in properties.items()}
            result["required"] = list(properties)
            result["additionalProperties"] = False
        return result
    return normalize(schema)


def _restore(schema: dict, raw, *, original_root: dict | None = None, wire_root: dict | None = None):
    """Restore map entry lists to caller JSON without accepting duplicate keys."""
    original_root = original_root or schema
    wire_root = wire_root or _wire_schema(original_root)
    wire_validator = Draft202012Validator(wire_root)

    def reference(pointer):
        if not isinstance(pointer, str) or not pointer.startswith("#/"):
            raise ProviderBlocked("SCHEMA_ERROR", "The response schema uses an unsupported local reference.")
        value = original_root
        try:
            for part in pointer[2:].split("/"):
                value = value[part.replace("~1", "/").replace("~0", "~")]
            if not isinstance(value, dict):
                raise ValueError("invalid reference")
            return value
        except (KeyError, TypeError, ValueError):
            raise ProviderBlocked("SCHEMA_ERROR", "The response schema contains an invalid local reference.") from None

    def restore(node, value, depth=0):
        if depth > 80:
            raise ProviderBlocked("SCHEMA_ERROR", "The structured response exceeds the nesting limit.")
        if "$ref" in node:
            return restore(reference(node["$ref"]), value, depth + 1)
        for choice in ("anyOf", "oneOf"):
            if choice in node:
                for branch in node[choice]:
                    if wire_validator.evolve(schema=_wire_schema(branch)).is_valid(value):
                        return restore(branch, value, depth + 1)
                raise ProviderBlocked("SCHEMA_ERROR", "The structured response does not match a declared schema branch.")
        if isinstance(node.get("additionalProperties"), dict) and not node.get("properties"):
            if not isinstance(value, list):
                raise ProviderBlocked("SCHEMA_ERROR", "A structured map response must contain key/value entries.")
            restored = {}
            for entry in value:
                if not isinstance(entry, dict) or set(entry) != {"key", "value"} or not isinstance(entry["key"], str):
                    raise ProviderBlocked("SCHEMA_ERROR", "The structured map contains an invalid entry.")
                if entry["key"] in restored:
                    raise ProviderBlocked("SCHEMA_ERROR", "The structured map contains a duplicate key.")
                restored[entry["key"]] = restore(node["additionalProperties"], entry["value"], depth + 1)
            return restored
        if isinstance(value, dict) and "properties" in node:
            return {key: restore(node["properties"][key], child, depth + 1) for key, child in value.items()}
        if isinstance(value, list) and "items" in node:
            return [restore(node["items"], child, depth + 1) for child in value]
        return value

    return restore(schema, raw)


class CodexProvider:
    def __init__(self, executable: str | Path | None = None, *, auth_home: Path | None = None):
        self.configured_executable = (str(executable) if executable is not None else os.environ.get("PF_CODEX_BIN")) or "codex"
        self._explicit_auth_home = Path(auth_home) if auth_home is not None else None

    def _child_environment(self) -> dict[str, str]:
        try:
            home = _private_directory(self._explicit_auth_home) if self._explicit_auth_home is not None else resolve_auth_home()
            return _environment(home)
        except (OSError, ValueError):
            raise ProviderBlocked("CONFIGURATION_ERROR", "The explicit Codex profile is unavailable or unsafe.") from None

    def _binary(self) -> str | None:
        return shutil.which(self.configured_executable)

    def _cli_metadata(self, binary: str, environment: dict[str, str]) -> dict:
        """Probe public capabilities without reading user config or auth data."""
        version = None
        missing = []
        try:
            texts = {}
            for name, arguments in (("version", ["--version"]), ("global", ["--help"]),
                                    ("exec", ["exec", "--help"]), ("features", ["features", "list"])):
                response = subprocess.run([binary, *arguments], env=environment, stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL, timeout=10, check=False)
                if response.returncode:
                    missing.append(name + "_metadata")
                texts[name] = response.stdout[:MAX_LOG_BYTES].decode("utf-8", errors="replace")
            match = re.search(r"(?m)^codex-cli ([0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?)\s*$", texts["version"])
            version = match.group(1) if match else None
            if version is None:
                missing.append("version_metadata")
            for flag in ("--no-daemon", "--ask-for-approval"):
                if flag not in texts["global"]:
                    missing.append(flag)
            for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral", "--skip-git-repo-check",
                         "--sandbox", "--json", "--output-schema", "--output-last-message", "--disable"):
                if flag not in texts["exec"]:
                    missing.append(flag)
            supported_features = set(re.findall(r"(?m)^([a-z][a-z0-9_.]*)\s+", texts["features"]))
            missing.extend("feature:" + feature for feature in DISABLED_FEATURES if feature not in supported_features)
        except (OSError, subprocess.TimeoutExpired):
            missing.append("capability_metadata")
        return {"cli_version": version, "capabilities_supported": not missing,
                "missing_capabilities": sorted(set(missing))}

    def status(self) -> dict:
        try:
            return self._status(self._child_environment())
        except ProviderBlocked as exc:
            return {"executable_available": bool(self._binary()), "authentication": "unknown", "ready": False,
                    "cli_version": None, "capabilities_supported": False, "missing_capabilities": [],
                    "code": exc.code, "reason": exc.message}

    def _status(self, environment: dict[str, str]) -> dict:
        binary = self._binary()
        if not binary:
            return {"executable_available": False, "authentication": "unknown", "ready": False,
                    "cli_version": None, "capabilities_supported": False, "missing_capabilities": []}
        metadata = self._cli_metadata(binary, environment)
        try:
            response = subprocess.run([binary, "login", "status"], env=environment, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, timeout=15, check=False)
            diagnostic = (response.stdout + response.stderr).decode("utf-8", errors="replace").casefold()
            if "logged in" in diagnostic and "chatgpt" in diagnostic:
                authentication = "chatgpt"
            elif "logged in" in diagnostic and ("api key" in diagnostic or "api_key" in diagnostic):
                authentication = "api_key"
            elif "not logged in" in diagnostic or "logged out" in diagnostic:
                authentication = "logged_out"
            else:
                authentication = "unknown"
            return {"executable_available": True, "authentication": authentication,
                    "ready": metadata["capabilities_supported"] and response.returncode == 0 and authentication in {"chatgpt", "api_key"},
                    **metadata}
        except (OSError, subprocess.TimeoutExpired):
            return {"executable_available": True, "authentication": "unknown", "ready": False, **metadata}

    def _container_command(self, command, root, *, environment: dict[str, str] | None = None):
        """Keep the official auth home at the same path, with no token copying.

        Some managed hosts make CODEX_HOME read-only. Codex nevertheless opens
        its noncredential installation_id for writing during initialization.
        A fresh file overlay permits that operation inside a disposable worker;
        all actual authentication files remain mounted read-only.
        """
        docker = shutil.which("docker")
        environment = environment if environment is not None else self._child_environment()
        home = environment.get("CODEX_HOME")
        if not docker or not home or not Path(home).is_dir():
            raise ProviderBlocked("CONFIGURATION_ERROR", "The read-only Codex authentication home requires the available isolated CLI runtime.")
        try:
            configured_image = os.environ.get("PF_RESEARCH_IMAGE") or "paper-factory-research:local"
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@-]{0,300}", configured_image):
                raise ValueError("invalid image identifier")
            docker_config = safe_relative(root, "runtime/docker-config")
            docker_config.mkdir(mode=0o700)
            inspection = subprocess.run([docker, "image", "inspect", configured_image, "--format", "{{.Id}}"],
                                        env={**environment, "DOCKER_CONFIG": str(docker_config)},
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, check=False)
            image = inspection.stdout.decode().strip()
            if inspection.returncode or not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
                raise ValueError("image unavailable")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise ProviderBlocked("CONFIGURATION_ERROR", "The isolated Codex CLI runtime image is unavailable.") from None
        installation = safe_relative(root, "runtime/installation_id")
        installation.write_text(str(uuid4()), encoding="ascii")
        name = "paper-factory-codex-" + uuid4().hex[:16]
        binary = str(Path(command[0]).absolute())
        if any("," in value or "\n" in value for value in (home, str(installation), binary, str(root))):
            raise ProviderBlocked("CONFIGURATION_ERROR", "The isolated Codex runtime paths contain unsupported characters.")
        wrapper = [docker, "run", "--rm", "-i", "--name", name, "--read-only", "--cap-drop", "ALL",
                   "--security-opt", "no-new-privileges", "--pids-limit", "64", "--memory", "512m",
                   "--cpus", "1", "--user", f"{os.getuid()}:{os.getgid()}", "--network", "host",
                   "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m", "--workdir", "/tmp",
                   "--mount", f"type=bind,src={home},dst={home},readonly",
                   "--mount", f"type=bind,src={installation},dst={home}/installation_id",
                   "--mount", f"type=bind,src={binary},dst={binary},readonly",
                   "--mount", f"type=bind,src={root},dst={root}"]
        certificates = set()
        for variable in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CODEX_PROXY_CERT", "NODE_EXTRA_CA_CERTS", "GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"):
            value = environment.get(variable)
            if value and Path(value).is_file():
                if "," in value or "\n" in value:
                    raise ProviderBlocked("CONFIGURATION_ERROR", "The configured certificate path is unsupported by the isolated runtime.")
                certificates.add(value)
        for certificate in sorted(certificates):
            wrapper.extend(["--mount", f"type=bind,src={certificate},dst={certificate},readonly"])
        for variable in sorted(environment):
            wrapper.extend(["-e", variable])
        inside = list(command)
        inside[inside.index("-C") + 1] = "/tmp"
        wrapper.extend([image, *inside])
        return wrapper, name, image

    def _remove_container(self, name, expected_id=None) -> bool:
        if not name:
            return True
        if not re.fullmatch(r"paper-factory-codex-[a-f0-9]{16}", name) or not (docker := shutil.which("docker")):
            return False
        if expected_id is not None and not re.fullmatch(r"[a-f0-9]{64}", expected_id):
            return False
        try:
            with tempfile.TemporaryDirectory(prefix="paper-factory-docker-config-") as config:
                environment = {**_environment(), "DOCKER_CONFIG": config}
                def absent():
                    response = subprocess.run([docker, "ps", "-aq", "--filter", f"name=^/{name}$"], env=environment,
                                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, check=False)
                    return response.returncode == 0 and not response.stdout.strip()
                inspection = subprocess.run([docker, "container", "inspect", name, "--format", "{{.Id}} {{.Name}}"],
                                            env=environment, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, check=False)
                if inspection.returncode:
                    return absent()
                fields = inspection.stdout.decode("ascii").strip().split()
                if len(fields) != 2 or not re.fullmatch(r"[a-f0-9]{64}", fields[0]) or fields[1] != "/" + name:
                    return False
                if expected_id is not None and fields[0] != expected_id:
                    return False
                # Pin removal to the inspected identity, preventing name reuse
                # from selecting a different worker between these commands.
                removal = subprocess.run([docker, "rm", "-f", fields[0]], env=environment, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL, timeout=15, check=False)
                return removal.returncode == 0 or absent()
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return False

    def cleanup_handle(self, handle: dict) -> bool:
        """Confirm termination of a controller-owned, persisted Codex worker."""
        if not isinstance(handle, dict) or handle.get("kind") != "codex":
            return False
        name, identity = handle.get("container_name"), handle.get("container_id")
        if name is not None and (not isinstance(name, str) or not re.fullmatch(r"paper-factory-codex-[a-f0-9]{16}", name)):
            return False
        if identity is not None and (not name or not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{64}", identity)):
            return False
        pid, pgid, ticks = (handle.get(key) for key in ("pid", "pgid", "start_ticks"))
        if any(isinstance(value, bool) or not isinstance(value, int) for value in (pid, pgid)) or pid <= 1 or pgid != pid:
            return False
        if os.name != "posix" or isinstance(ticks, bool) or not isinstance(ticks, int) or ticks <= 0:
            return False
        try:
            current_ticks = _start_ticks(pid)
            group_confirmed = True
            # A reused process ID is unrelated to this persisted worker.
            if current_ticks is None or current_ticks == ticks:
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                deadline = time.monotonic() + 2
                while _group_running(pgid) and time.monotonic() < deadline:
                    time.sleep(0.02)
                if _group_running(pgid):
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    deadline = time.monotonic() + 1
                    while _group_running(pgid) and time.monotonic() < deadline:
                        time.sleep(0.02)
                group_confirmed = not _group_running(pgid)
            container_confirmed = self._remove_container(handle.get("container_name"), handle.get("container_id"))
            return group_confirmed and container_confirmed
        except OSError:
            return False

    def generate(self, prompt: str, schema: dict, call_dir: Path, *,
                 cancel: Callable[[], bool] | None = None, timeout_seconds: int = 600,
                 model: str | None = None, on_handle: Callable[[dict], None] | None = None) -> dict:
        if not isinstance(prompt, str) or not prompt.strip() or "\x00" in prompt or len(prompt.encode()) > MAX_PROMPT_BYTES:
            raise ProviderBlocked("INVALID_INPUT", "The model prompt must be nonempty bounded text without NUL bytes.")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 3600:
            raise ProviderBlocked("INVALID_INPUT", "Model timeout must be an integer between 1 and 3600 seconds.")
        requested_model = model if model is not None else os.environ.get("PF_CODEX_MODEL") or None
        if requested_model is not None and (not isinstance(requested_model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", requested_model)):
            raise ProviderBlocked("INVALID_INPUT", "The configured Codex model identifier is invalid.")
        validator = _schema_validator(schema)
        wire_schema = _wire_schema(schema)
        wire_validator = _schema_validator(wire_schema)
        wire_prompt = prompt + ("\n\nStructured-output adapter: Return the complete object described by the supplied output schema, "
                                "including every required field. Arbitrary-key maps are encoded as arrays of objects with exactly "
                                "key (a unique string) and value fields. Return those arrays according to the output schema; "
                                "the caller restores them to dictionaries. Do not use tools or inspect local files.")
        if len(wire_prompt.encode()) > MAX_PROMPT_BYTES:
            raise ProviderBlocked("INVALID_INPUT", "The prompt plus structured-output instructions exceeds the model input limit.")
        sensitive = _sensitive_values()
        if any(value in prompt for value in sensitive):
            raise ProviderBlocked("UNSAFE_INPUT", "The model prompt contains an injected credential value and was not sent.")
        root = Path(call_dir).expanduser()
        try:
            ensure_unlinked(root)
            root.mkdir(parents=True, exist_ok=True)
            if any(root.iterdir()):
                raise ProviderBlocked("INVALID_CALL_DIR", "Each model attempt requires a new empty call directory.")
            root = root.resolve()
        except (OSError, ValueError):
            raise ProviderBlocked("CONFIGURATION_ERROR", "The model call directory is unavailable or unsafe.") from None
        started = time.monotonic()
        receipt = {"provider": "codex_cli", "started_at": _now(), "status": "running",
                   "prompt_sha256": _digest(prompt.encode()), "schema_sha256": _digest(json.dumps(schema, sort_keys=True, allow_nan=False).encode()),
                   "model_input_prompt_sha256": _digest(wire_prompt.encode()),
                   "model_input_schema_sha256": _digest(json.dumps(wire_schema, sort_keys=True, allow_nan=False).encode()),
                   "wire_schema_sha256": _digest(json.dumps(wire_schema, sort_keys=True, allow_nan=False).encode()),
                   "requested_model": requested_model, "actual_model": None, "usage": None,
                   "output_sha256": None, "raw_output_sha256": None, "normalized_output_sha256": None, "authentication": "unknown",
                   "policy": {"sandbox": "read-only", "workspace": "disposable_empty", "tools": "disabled_by_cli_features"}}
        write_json(root / "schema.json", wire_schema)
        write_json(root / "original-schema.json", schema)
        receipt["wire_schema_sha256"] = receipt["model_input_schema_sha256"] = _digest((root / "schema.json").read_bytes())
        write_json(root / "receipt.json", receipt)
        output_path = root / "output.json"
        try:
            if cancel and cancel():
                raise ProviderBlocked("CANCELLED", "Model generation was stopped before execution.")
            environment = self._child_environment()
            status = self._status(environment)
            receipt["authentication"] = status["authentication"]
            receipt.update({key: status[key] for key in ("cli_version", "capabilities_supported", "missing_capabilities")})
            if not status["executable_available"]:
                raise ProviderBlocked("CODEX_UNAVAILABLE", "Install or configure the official Codex CLI before starting generation.")
            if not status["capabilities_supported"]:
                raise ProviderBlocked("CODEX_UNSUPPORTED", "The installed Codex CLI lacks required structured-only isolation capabilities; inspect the recorded capability names.")
            if not status["ready"]:
                raise ProviderBlocked("AUTH_REQUIRED", "The official Codex CLI has no confirmed usable existing authentication.")
            with tempfile.TemporaryDirectory(prefix="paperfactory-codex-context-") as temporary:
                work = Path(temporary)
                runtime = safe_relative(root, "runtime")
                runtime.mkdir()
                command = [self._binary(), "--no-daemon", "-a", "never", "exec", "--ignore-user-config",
                           "--ignore-rules", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only",
                           "--json", "--color", "never", "-C", str(work), "--output-schema", str(root / "schema.json"),
                           "-o", str(output_path), "-c", "sqlite_home=" + json.dumps(str(runtime)),
                           "-c", "log_dir=" + json.dumps(str(runtime / "logs")), "-c", "web_search=\"disabled\"",
                           "-c", "mcp_servers={}"]
                for feature in DISABLED_FEATURES:
                    command.extend(["--disable", feature])
                if requested_model:
                    command.extend(["--model", requested_model])
                command.append("-")
                receipt["runtime_backend"] = "host"
                code, diagnostic = self._execute(command, wire_prompt, root, work, receipt, sensitive,
                                                 cancel, timeout_seconds, on_handle, environment=environment)
                # Retry only the known pre-request runtime initialization
                # failure. Network/model errors never dispatch a duplicate call.
                readonly_initialization = re.search(r"(?:^|\n)(?:Error:\s*)?failed to initialize in-process app-server client:[^\n]*read-only file system",
                                                    diagnostic, re.I)
                if code and readonly_initialization and not receipt.get("model_dispatch_observed") and receipt["usage"] is None and receipt["actual_model"] is None and not output_path.exists():
                    for channel in ("stdout", "stderr"):
                        path = root / (channel + ".log")
                        if path.is_file():
                            safe_relative(root, "host-" + channel + ".log").write_bytes(path.read_bytes())
                    container_command, name, image = self._container_command(command, root, environment=environment)
                    receipt.update(runtime_backend="docker", runtime_image=image)
                    code, diagnostic = self._execute(container_command, wire_prompt, root, work, receipt, sensitive,
                                                     cancel, timeout_seconds, on_handle, container_name=name, environment=environment)
                if code:
                    raise _classify(diagnostic)
            if not output_path.exists():
                raise ProviderBlocked("SCHEMA_ERROR", "Codex finished without a structured response file.")
            ensure_unlinked(output_path)
            metadata = output_path.stat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_OUTPUT_BYTES:
                raise ProviderBlocked("SCHEMA_ERROR", "The structured response is not a bounded regular file.")
            raw = output_path.read_bytes()
            receipt["raw_output_sha256"] = _digest(raw)
            if _redact(raw.decode("utf-8", errors="replace"), sensitive) != raw.decode("utf-8", errors="replace"):
                raise ProviderBlocked("UNSAFE_OUTPUT", "The structured response contained a sensitive value and was discarded.")
            def pairs(items):
                result = {}
                for key, value in items:
                    if key in result:
                        raise ValueError("duplicate key")
                    result[key] = value
                return result
            def invalid_constant(value):
                raise ValueError("nonfinite JSON")
            try:
                model_output = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
                def safe_decoded(value, depth=0):
                    if depth > 80:
                        raise ValueError("response depth")
                    if isinstance(value, str):
                        if _redact(value, sensitive) != value:
                            raise ProviderBlocked("UNSAFE_OUTPUT", "The decoded response contained a sensitive value and was discarded.")
                    elif isinstance(value, float) and not math.isfinite(value):
                        raise ValueError("nonfinite number")
                    elif isinstance(value, dict):
                        for key, child in value.items():
                            safe_decoded(key, depth + 1)
                            safe_decoded(child, depth + 1)
                    elif isinstance(value, list):
                        for child in value:
                            safe_decoded(child, depth + 1)
                safe_decoded(model_output)
                wire_validator.validate(model_output)
                output = _restore(schema, model_output, original_root=schema, wire_root=wire_schema)
                validator.validate(output)
                if not isinstance(output, dict):
                    raise ValueError("response must be an object")
            except (ValueError, UnicodeError, ValidationError):
                raise ProviderBlocked("SCHEMA_ERROR", "Codex returned a response that does not match the required JSON schema.") from None
            safe_relative(root, "model-output.json").write_bytes(raw)
            write_json(output_path, output)
            normalized_hash = _digest(output_path.read_bytes())
            receipt.update(status="completed", output_sha256=normalized_hash, normalized_output_sha256=normalized_hash)
            return output
        except ProviderBlocked as exc:
            receipt.update(status="cancelled" if exc.code == "CANCELLED" else "blocked", code=exc.code, message=exc.message)
            output_path.unlink(missing_ok=True)
            raise
        except (OSError, ValueError):
            receipt.update(status="blocked", code="CONFIGURATION_ERROR", message="Codex model call artifacts could not be accessed safely.")
            output_path.unlink(missing_ok=True)
            raise ProviderBlocked("CONFIGURATION_ERROR", receipt["message"]) from None
        finally:
            receipt.update(ended_at=_now(), elapsed_seconds=round(time.monotonic() - started, 3))
            write_json(root / "receipt.json", receipt)

    def _execute(self, command, prompt, root, work, receipt, sensitive, cancel, timeout, on_handle, container_name=None, environment=None):
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        environment = dict(environment) if environment is not None else self._child_environment()
        if container_name:
            environment["DOCKER_CONFIG"] = str(safe_relative(root, "runtime/docker-config"))
        process = subprocess.Popen(command, cwd=work, env=environment, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
        receipt["cleanup_confirmed"] = False
        handle = {"kind": "codex", "pid": process.pid, "pgid": process.pid, "start_ticks": _start_ticks(process.pid)}
        if container_name:
            handle["container_name"] = container_name
        try:
            write_json(root / "runtime-handle.json", handle)
            if on_handle:
                on_handle(dict(handle))
        except Exception:
            group_confirmed = _try_stop(process)
            container_confirmed = self._remove_container(container_name)
            receipt["cleanup_confirmed"] = group_confirmed and container_confirmed
            if not receipt["cleanup_confirmed"]:
                raise ProviderBlocked("CLEANUP_UNCONFIRMED", "Codex worker cleanup could not be confirmed; retain its persisted handle and stop it before resuming.") from None
            raise ProviderBlocked("CONFIGURATION_ERROR", "The model worker ownership could not be recorded.") from None
        logs = {"stdout": [], "stderr": []}
        sizes = {"stdout": 0, "stderr": 0}
        diagnostic = []
        diagnostic_size = 0
        policy_violation = threading.Event()
        terminal_failure = threading.Event()
        hard_blocker = []
        lock = threading.Lock()
        maximum_secret = max((len(value) for value in sensitive), default=0)

        def record_diagnostic(text):
            nonlocal diagnostic_size
            with lock:
                remaining = MAX_LOG_BYTES - diagnostic_size
                if remaining > 0:
                    retained = _bounded_text(text, remaining)
                    diagnostic.append(retained)
                    diagnostic_size += len(retained.encode("utf-8"))
            classification = _classify(text)
            if classification.code in {"RATE_LIMITED", "AUTH_REQUIRED"} or classification.code == "NETWORK_ERROR" and "403" in text:
                if not hard_blocker:
                    hard_blocker.append(classification)

        def consume(name, stream):
            while data := stream.readline(MAX_OUTPUT_BYTES + maximum_secret):
                text = _redact(data.decode("utf-8", errors="replace"), sensitive)
                if name == "stdout":
                    try:
                        event = json.loads(text)
                        if not isinstance(event, dict):
                            raise ValueError("unexpected event")
                        kind = str(event.get("type", "unknown"))[:100]
                        if kind in {"turn.started", "turn.completed"}:
                            receipt["model_dispatch_observed"] = True
                        if kind == "turn.failed":
                            terminal_failure.set()
                        summary = {"type": kind}
                        item = event.get("item")
                        if isinstance(item, dict):
                            item_type = str(item.get("type", "unknown"))[:100]
                            summary["item_type"] = item_type
                            if item_type not in {"agent_message", "reasoning", "todo_list", "error", "warning", "context_compaction"}:
                                policy_violation.set()
                            if item_type in {"agent_message", "reasoning", "todo_list"}:
                                receipt["model_dispatch_observed"] = True
                            if item_type in {"error", "warning"}:
                                message = item.get("message") or item.get("text")
                                if isinstance(message, str):
                                    record_diagnostic(message)
                                summary["diagnostic"] = "CLI reported a generation diagnostic"
                        usage = event.get("usage")
                        if isinstance(usage, dict):
                            clean = {key: value for key, value in usage.items() if key in {"input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"} and isinstance(value, int) and not isinstance(value, bool) and value >= 0}
                            if clean:
                                receipt["usage"] = clean
                                summary["usage"] = clean
                        model_name = event.get("model")
                        if isinstance(model_name, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", model_name):
                            receipt["actual_model"] = model_name
                            summary["model"] = model_name
                        if kind in {"error", "turn.failed"}:
                            error = event.get("error") or event.get("message")
                            record_diagnostic(str(error))
                            summary["diagnostic"] = "CLI reported a generation error"
                        text = json.dumps(summary, ensure_ascii=True) + "\n"
                    except (ValueError, TypeError):
                        text = "[Non-event CLI output omitted]\n"
                else:
                    match = re.search(r"(?m)^model:\s*([A-Za-z0-9][A-Za-z0-9._:/-]{0,199})\s*$", text)
                    if match:
                        receipt["actual_model"] = match.group(1)
                    record_diagnostic(text)
                with lock:
                    remaining = MAX_LOG_BYTES - sizes[name]
                    if remaining > 0:
                        retained = _bounded_text(text, remaining)
                        logs[name].append(retained)
                        sizes[name] += len(retained.encode("utf-8"))
            stream.close()

        threads = [threading.Thread(target=consume, args=(name, stream), daemon=True)
                   for name, stream in (("stdout", process.stdout), ("stderr", process.stderr))]
        for thread in threads:
            thread.start()
        def send_prompt():
            assert process.stdin is not None
            try:
                process.stdin.write(prompt.encode("utf-8"))
            except (BrokenPipeError, OSError):
                pass
            finally:
                try:
                    process.stdin.close()
                except OSError:
                    pass
        writer = threading.Thread(target=send_prompt, daemon=True)
        writer.start()
        began = time.monotonic()
        failure = None
        try:
            while process.poll() is None:
                if hard_blocker:
                    failure = hard_blocker[0]
                    break
                if policy_violation.is_set():
                    failure = ProviderBlocked("POLICY_VIOLATION", "Codex attempted a tool action during a structured-only model call.")
                    break
                if cancel and cancel():
                    failure = ProviderBlocked("CANCELLED", "Model generation was stopped; the active process group was terminated.")
                    break
                if time.monotonic() - began >= timeout:
                    failure = ProviderBlocked("TIMEOUT", "Codex exceeded the model-call deadline.")
                    break
                try:
                    process.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    pass
        except Exception:
            failure = ProviderBlocked("CONFIGURATION_ERROR", "The model call could not be supervised safely.")
        finally:
            group_confirmed = False
            if failure:
                group_confirmed = _try_stop(process)
            writer.join(timeout=2)
            for thread in threads:
                thread.join(timeout=2)
            if any(thread.is_alive() for thread in threads):
                group_confirmed = _try_stop(process)
                for thread in threads:
                    thread.join(timeout=2)
            group_confirmed = _try_stop(process)
            for name in logs:
                (root / (name + ".log")).write_text("".join(logs[name]), encoding="utf-8")
            container_confirmed = self._remove_container(container_name)
            receipt["cleanup_confirmed"] = group_confirmed and container_confirmed
            if not receipt["cleanup_confirmed"]:
                interrupted = failure or _classify("".join(diagnostic))
                receipt.update(interrupted_code=interrupted.code, interrupted_message=interrupted.message)
                raise ProviderBlocked("CLEANUP_UNCONFIRMED", "Codex worker cleanup could not be confirmed; retain its persisted handle and stop it before resuming.")
        if policy_violation.is_set() and failure is None:
            failure = ProviderBlocked("POLICY_VIOLATION", "Codex attempted a tool action during a structured-only model call.")
        if failure:
            raise failure
        if hard_blocker:
            raise hard_blocker[0]
        if terminal_failure.is_set():
            return process.returncode or 1, "".join(diagnostic)[:MAX_LOG_BYTES]
        return process.returncode, "".join(diagnostic)[:MAX_LOG_BYTES]

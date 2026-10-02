"""Explicit official Codex subscription login in private, app-owned profiles.

This manager never reads, copies, edits, or logs authentication files. Device
codes live only in bounded transient memory. A new profile becomes active only
after an explicitly requested, tools-disabled model probe succeeds.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import errno
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import threading
import time
from typing import Callable
from urllib.parse import urlparse
from uuid import uuid4

try:
    import fcntl
except ImportError:
    fcntl = None
if os.name == "nt":
    import msvcrt

from ..workspace import ensure_unlinked, write_json
from .provider import CodexProvider, ProviderBlocked, _authentication_kind, _cli_command, _environment, _process_options, _track_process, _try_stop, _worker_handle
from .windows_runtime import is_private_path, private_path


MAX_DIAGNOSTIC_BYTES = 64 * 1024
DEVICE_URL = "https://auth.openai.com/codex/device"
PROFILE = re.compile(r"profiles/([a-f0-9]{32})\Z")
STATES = {"starting", "waiting_user", "authenticated", "probing", "available", "blocked", "cancelled", "failed", "disconnected", "logging_out", "logged_out"}
PROBE_SCHEMA = {"type": "object", "properties": {"ready": {"type": "boolean", "enum": [True]}},
                "required": ["ready"], "additionalProperties": False}
MESSAGES = {
    "AUTH_REQUIRED": "Codex 구독 로그인이 필요합니다. 공식 로그인 후 연결 확인을 다시 실행하세요.",
    "API_KEY_UNSUPPORTED": "API 키 로그인은 사용할 수 없습니다. ChatGPT 구독 계정으로 로그인하세요.",
    "SUBSCRIPTION_AUTH_REQUIRED": "API 키로 모델을 요청할 수 없습니다. ChatGPT 구독 계정으로 다시 연결하세요.",
    "NETWORK_ERROR": "Codex 인증·모델 서버에 연결하지 못했습니다. 프록시 또는 네트워크 연결을 확인하세요.",
    "PROXY_BLOCKED": "환경 프록시가 Codex 연결을 차단했습니다(HTTP 403).",
    "RATE_LIMITED": "구독 사용량 제한으로 연결 확인을 완료하지 못했습니다. 이용 가능해진 뒤 다시 확인하세요.",
    "LOGIN_TIMEOUT": "공식 기기 로그인의 대기 시간이 끝났습니다. 로그인을 다시 시작하세요.",
    "LOGIN_START_TIMEOUT": "공식 로그인 주소·코드를 받지 못해 시작 대기 시간을 종료했습니다. 인증 서버 연결을 확인한 뒤 다시 시도하세요.",
    "OUTPUT_LIMIT": "공식 로그인 출력이 허용된 크기를 초과하여 중단했습니다.",
    "CODEX_NOT_FOUND": "공식 Codex CLI를 찾을 수 없습니다.",
    "CONFIGURATION_ERROR": "Codex 연결 환경을 초기화하지 못했습니다.",
    "SCHEMA_ERROR": "모델이 올바른 연결 확인 응답을 반환하지 않았습니다.",
    "INTERRUPTED": "이전 연결 작업이 중단되었습니다. 작업자를 정리했으며 로그인을 다시 시작할 수 있습니다.",
    "CLEANUP_UNCONFIRMED": "이전 연결 작업자의 종료를 확인하지 못했습니다. 연결 작업을 재시작하기 전에 정리가 필요합니다.",
    "CONNECTION_BUSY": "다른 연결 작업이 진행 중입니다. 해당 작업이 끝난 뒤 다시 시도하세요.",
    "AUTH_STORAGE_INVALID": "구독 연결 저장 경로 또는 메타데이터가 안전한 개인 경로가 아닙니다.",
    "UNSUPPORTED_PLATFORM": "이 플랫폼은 구독 연결의 파일 잠금을 지원하지 않습니다.",
    "CANCELLED": "구독 연결 작업을 취소했습니다.",
    "CODEX_FAILED": "공식 Codex 연결 작업을 완료하지 못했습니다.",
    "DEVICE_AUTH_UNAVAILABLE": "현재 Codex 서버에서 기기 로그인을 지원하지 않습니다. 공식 서버 설정을 확인하세요.",
    "CANCEL_REQUESTED": "진행 중인 구독 연결 작업에 취소를 요청했습니다.",
    "LOGOUT_TIMEOUT": "Codex 로그아웃 확인 시간이 끝났습니다. 앱의 연구 시작은 차단되어 있으며 다시 로그아웃할 수 있습니다.",
    "LOGOUT_FAILED": "공식 Codex 로그아웃을 확인하지 못했습니다. 앱의 연구 시작은 차단되어 있으며 다시 로그아웃할 수 있습니다.",
}
STATE_MESSAGES = {
    "authenticated": "공식 구독 로그인이 완료되었습니다. 연결 확인을 실행하면 사용할 수 있습니다.",
    "available": "구독 모델의 실제 응답을 확인했습니다.",
    "logged_out": "이 앱의 Codex 계정에서 로그아웃했습니다. 저장된 연구와 논문은 유지됩니다.",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _private_directory(path: Path) -> None:
    ensure_unlinked(path)
    if not path.exists():
        path.mkdir(parents=True, mode=0o700)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or (hasattr(os, "getuid") and info.st_uid != os.getuid()):
        raise ValueError("not an owned directory")
    private_path(path)


def _locking_available() -> bool:
    return os.name == "nt" or fcntl is not None


def _lock_file(descriptor: int, *, blocking: bool = False) -> bool:
    try:
        if os.name == "nt":
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(descriptor, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        return True
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
            return False
        raise


def _unlock_file(descriptor: int) -> None:
    if os.name == "nt":
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(descriptor, fcntl.LOCK_UN)


def _write_metadata(path: Path, value: dict) -> None:
    write_json(path, value)
    private_path(path)


def _read_metadata(path: Path) -> dict | None:
    ensure_unlinked(path)
    if not path.exists():
        return None
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 16 * 1024
                or not is_private_path(path) or (hasattr(os, "getuid") and info.st_uid != os.getuid())):
            raise ValueError("not private metadata")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            data = stream.read(16 * 1024 + 1)
        value = json.loads(data)
        if not isinstance(value, dict) or type(value.get("version")) is not int or value.get("version") != 1:
            raise ValueError("invalid metadata")
        return value
    finally:
        os.close(descriptor)


def _challenge(text: str) -> tuple[str | None, str | None]:
    # Never accept arbitrary URLs, bearer values, OAuth tokens, or query grants.
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
    url = None
    for candidate in re.findall(r"https://[^\s<>\"']+", text):
        parsed = urlparse(candidate.rstrip(".,)"))
        if (parsed.scheme == "https" and parsed.netloc == "auth.openai.com"
                and parsed.path.rstrip("/") == "/codex/device" and not parsed.query and not parsed.fragment):
            url = DEVICE_URL
            break
    if url is None:
        return None, None
    code = re.search(r"(?i:Enter this one-time code)[^\n]{0,120}\n[ \t]*([A-Z0-9]{4}-[A-Z0-9]{4})\b", text)
    if code is None:
        code = re.search(r"(?i:user_code|device_code|enter(?: the| this)? code)\s*[:=]\s*([A-Z0-9]{4}-[A-Z0-9]{4})\b", text)
    return url, code.group(1) if code else None


def _utc(value: object) -> None:
    if not isinstance(value, str):
        raise ValueError("timestamp is not a string")
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp must specify UTC")


class ConnectionManager:
    def __init__(self, root: Path, *, provider_factory: Callable[[Path], object] | None = None,
                 executable: str | Path | None = None, login_timeout_seconds: int = 900,
                 probe_timeout_seconds: int = 90, startup_challenge_timeout_seconds: int = 60,
                 logout_timeout_seconds: int = 30) -> None:
        for timeout in (login_timeout_seconds, probe_timeout_seconds, startup_challenge_timeout_seconds, logout_timeout_seconds):
            if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 1800:
                raise ValueError("connection timeouts must be bounded positive integers")
        self.root = Path(root).expanduser().absolute()
        self.executable = str(executable or os.environ.get("PF_CODEX_BIN") or CodexProvider().configured_executable)
        self.provider_factory = provider_factory or (lambda home: CodexProvider(self.executable, auth_home=home))
        self.login_timeout_seconds = login_timeout_seconds
        self.probe_timeout_seconds = probe_timeout_seconds
        self.startup_challenge_timeout_seconds = startup_challenge_timeout_seconds
        self.logout_timeout_seconds = logout_timeout_seconds
        self._mutex = threading.RLock()
        self._worker: threading.Thread | None = None
        self._cancel = threading.Event()
        self._verification_url = self._user_code = None
        self._initial_error: str | None = None
        self._lock_fd: int | None = None
        self._state_fd: int | None = None
        self._owns_lock = False
        self._closed = False
        try:
            ensure_unlinked(self.root)
            platform = os.environ.get("CODEX_HOME")
            if platform and self.root.resolve().is_relative_to(Path(platform).expanduser().resolve()):
                raise ValueError("platform authentication home cannot be adopted")
            if any((parent / ".git").is_file() or (parent / ".git" / "HEAD").exists()
                   for parent in (self.root, *self.root.parents)):
                raise ValueError("authentication profiles must be outside Git checkouts")
            if self.root.exists():
                allowed = {"profiles", "active.json", "operation.json", ".connection.lock", ".state.lock", ".probe-runtime", ".cancel.json"}
                if any(path.name not in allowed for path in self.root.iterdir()):
                    raise ValueError("authentication root is not an app-owned namespace")
            _private_directory(self.root)
            _private_directory(self.root / "profiles")
            _private_directory(self.root / ".probe-runtime")
            lock = self.root / ".connection.lock"
            ensure_unlinked(lock)
            new_lock = not lock.exists()
            self._lock_fd = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0), 0o600)
            if new_lock:
                private_path(lock)
            info = os.fstat(self._lock_fd)
            if (info.st_nlink != 1 or not stat.S_ISREG(info.st_mode) or not is_private_path(lock)
                    or (hasattr(os, "getuid") and info.st_uid != os.getuid())):
                raise ValueError("unsafe operation lock")
            if os.name == "nt" and info.st_size == 0:
                os.write(self._lock_fd, b"\0")
            state_lock = self.root / ".state.lock"
            ensure_unlinked(state_lock)
            new_lock = not state_lock.exists()
            self._state_fd = os.open(state_lock, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0), 0o600)
            if new_lock:
                private_path(state_lock)
            info = os.fstat(self._state_fd)
            if (info.st_nlink != 1 or not stat.S_ISREG(info.st_mode) or not is_private_path(state_lock)
                    or (hasattr(os, "getuid") and info.st_uid != os.getuid())):
                raise ValueError("unsafe state lock")
            if os.name == "nt" and info.st_size == 0:
                os.write(self._state_fd, b"\0")
            # A lock held by another manager is authoritative ownership. Merely
            # opening status in another server must never interrupt its login.
            if self._acquire():
                try:
                    self._recover()
                finally:
                    self._release()
        except (OSError, ValueError, json.JSONDecodeError):
            self._initial_error = "AUTH_STORAGE_INVALID"

    def _acquire(self) -> bool:
        if not _locking_available() or self._lock_fd is None:
            return False
        if self._owns_lock:
            return True
        if _lock_file(self._lock_fd):
            self._owns_lock = True
            return True
        return False

    def _release(self) -> None:
        if self._owns_lock and self._lock_fd is not None:
            _unlock_file(self._lock_fd)
            self._owns_lock = False

    def _state_acquire(self, *, blocking: bool = False) -> bool:
        if not _locking_available() or self._state_fd is None:
            return False
        return _lock_file(self._state_fd, blocking=blocking)

    def _state_release(self) -> None:
        if self._state_fd is not None:
            _unlock_file(self._state_fd)

    def _home(self, profile: str) -> Path:
        if not isinstance(profile, str) or not PROFILE.fullmatch(profile):
            raise ValueError("invalid profile identity")
        home = self.root / profile
        ensure_unlinked(home)
        info = home.stat()
        if not stat.S_ISDIR(info.st_mode) or not is_private_path(home) or (hasattr(os, "getuid") and info.st_uid != os.getuid()):
            raise ValueError("unsafe profile home")
        return home

    def _selection(self) -> dict | None:
        value = _read_metadata(self.root / "active.json")
        if value is not None:
            if value.get("logged_out") is True:
                profiles = value.get("profiles", [])
                if (set(value) - {"version", "logged_out", "profiles"}
                        or not isinstance(profiles, list) or len(profiles) > 2
                        or not all(isinstance(profile, str) for profile in profiles) or len(set(profiles)) != len(profiles)):
                    raise ValueError("invalid logout selection")
                for profile in profiles:
                    self._home(profile)
                return value
            if (set(value) != {"version", "profile", "verified", "verified_at"}
                    or value.get("verified") is not True or not isinstance(value.get("verified_at"), str)):
                raise ValueError("invalid active profile")
            self._home(value.get("profile"))
            _utc(value["verified_at"])
        return value

    def _active(self) -> dict | None:
        selection = self._selection()
        return selection if selection and selection.get("logged_out") is not True else None

    def initialize_app_login(self) -> dict:
        """Require explicit app login on first start without invoking the CLI."""
        with self._mutex:
            if self._initial_error or not _locking_available():
                return self.status()
            if self._closed or self._worker and self._worker.is_alive() or not self._acquire():
                return self._busy()
            try:
                if self._selection() is None:
                    _write_metadata(self.root / "active.json", {"version": 1, "logged_out": True})
                return self.status()
            except (OSError, ValueError, TypeError):
                return {**self.status(), "status": "blocked", "code": "AUTH_STORAGE_INVALID", "message": MESSAGES["AUTH_STORAGE_INVALID"]}
            finally:
                self._release()

    def _operation(self) -> dict | None:
        value = _read_metadata(self.root / "operation.json")
        if value is not None:
            allowed = {"version", "operation_id", "kind", "profile", "status", "authentication", "started_at", "expires_at", "handle", "code", "message"}
            if set(value) - allowed or value.get("code") not in {None, *MESSAGES}:
                raise ValueError("unexpected operation metadata")
            if value.get("message") not in {None, *MESSAGES.values(), *STATE_MESSAGES.values()}:
                raise ValueError("unexpected operation message")
            if not isinstance(value.get("operation_id"), str) or not re.fullmatch(r"[a-f0-9]{32}", value["operation_id"]):
                raise ValueError("invalid operation identity")
            if value.get("status") not in STATES or value.get("authentication") not in {"unknown", "chatgpt", "logged_out", "api_key"}:
                raise ValueError("invalid operation state")
            for field in ("started_at", "expires_at"):
                _utc(value[field])
            if value.get("profile") is not None:
                self._home(value["profile"])
        return value

    def _write(self, operation: dict) -> None:
        _write_metadata(self.root / "operation.json", operation)

    def _update(self, **changes) -> None:
        with self._mutex:
            operation = self._operation()
            if operation is None:
                raise ValueError("missing owned operation")
            operation.update(changes)
            self._write(operation)

    def _record_handle(self, handle: dict) -> None:
        allowed = {"kind", "pid", "pgid", "start_ticks", "container_name", "container_id", "job_name"}
        if not isinstance(handle, dict) or set(handle) - allowed or handle.get("kind") != "codex":
            raise ValueError("unsafe worker handle")
        for field in ("pid", "pgid", "start_ticks"):
            if type(handle.get(field)) is not int or handle[field] <= (0 if field == "start_ticks" else 1):
                raise ValueError("unsafe worker identity")
        if handle["pid"] != handle["pgid"]:
            raise ValueError("worker does not own its process group")
        if handle.get("container_name") is not None and not re.fullmatch(r"paper-factory-codex-[a-f0-9]{16}", handle["container_name"]):
            raise ValueError("unsafe container identity")
        if handle.get("container_id") is not None and not re.fullmatch(r"[a-f0-9]{64}", handle["container_id"]):
            raise ValueError("unsafe container digest")
        if handle.get("job_name") is not None and (os.name != "nt" or not isinstance(handle["job_name"], str)
                or not re.fullmatch(r"Local\\paper-factory-codex-[a-f0-9]{32}", handle["job_name"])):
            raise ValueError("unsafe Windows worker job")
        self._update(handle=dict(handle))

    def _confirm_cleanup(self, profile: str, process: subprocess.Popen | None = None) -> bool:
        """Confirm ownership cleanup before clearing any persisted capability."""
        try:
            # A reaped leader can still own the original Windows Job handle.
            if (process is not None
                    and (process.poll() is None or getattr(process, "_paper_factory_job", None) is not None)
                    and not _try_stop(process)):
                return False
            operation = self._operation()
            handle = operation.get("handle") if operation else None
            if handle is not None:
                return self.provider_factory(self._home(profile)).cleanup_handle(handle) is True
            return operation is None or operation.get("code") != "CLEANUP_UNCONFIRMED"
        except Exception:
            return False

    def _probe_failure(self, profile: str, code: str, *, status: str = "blocked") -> None:
        if not self._confirm_cleanup(profile):
            self._failure("CLEANUP_UNCONFIRMED")
        else:
            self._failure(code, status=status)

    def _cancel_requested(self) -> bool:
        if self._cancel.is_set():
            return True
        with self._mutex:
            intent = _read_metadata(self.root / ".cancel.json")
            if intent is None:
                return False
            if set(intent) != {"version", "operation_id", "requested_at"}:
                raise ValueError("unsafe cancel intent")
            _utc(intent["requested_at"])
            operation = self._operation()
            if operation and intent.get("operation_id") == operation["operation_id"]:
                self._cancel.set()
                return True
            return False

    def _failure(self, code: str, *, status: str = "blocked") -> None:
        # Never forward arbitrary exception or subprocess text into storage/UI.
        if code not in MESSAGES:
            code = "CODEX_FAILED"
        changes = {"status": status, "code": code, "message": MESSAGES[code]}
        if code != "CLEANUP_UNCONFIRMED":
            changes["handle"] = None
        self._update(**changes)
        with self._mutex:
            self._verification_url = self._user_code = None

    def _recover(self) -> None:
        self._active()
        operation = self._operation()
        if operation is None or (operation["status"] not in {"starting", "waiting_user", "probing", "logging_out"}
                                 and operation.get("code") != "CLEANUP_UNCONFIRMED"):
            return
        handle = operation.get("handle")
        try:
            clean = (handle is None and operation.get("code") != "CLEANUP_UNCONFIRMED") or (handle is not None and self.provider_factory(self._home(operation["profile"])).cleanup_handle(handle))
        except (OSError, ValueError, TypeError, AttributeError):
            clean = False
        code = "INTERRUPTED" if clean else "CLEANUP_UNCONFIRMED"
        operation.update(status="failed" if clean else "blocked", code=code, message=MESSAGES[code])
        if clean:
            operation["handle"] = None
        self._write(operation)

    def status(self) -> dict:
        """Return only local safe metadata; no CLI, model, or token inspection."""
        with self._mutex:
            error = self._initial_error or ("UNSUPPORTED_PLATFORM" if not _locking_available() else None)
            try:
                selection = self._selection() if not error else None
                active = selection if selection and selection.get("logged_out") is not True else None
                operation = self._operation() if not error else None
            except (OSError, ValueError, TypeError, KeyError):
                error, selection, active, operation = "AUTH_STORAGE_INVALID", None, None, None
            connected = active is not None
            model_available = connected
            state = operation["status"] if operation else ("available" if connected else "logged_out" if selection else "disconnected")
            authentication = operation.get("authentication", "unknown") if operation else ("chatgpt" if connected else "logged_out")
            if active and operation and operation.get("profile") == active["profile"] and state in {"blocked", "failed"}:
                model_available = False
            result = {"status": "blocked" if error else state, "authentication": authentication,
                      "model_available": model_available, "connected": connected,
                      "app_login_required": bool(selection and selection.get("logged_out") is True),
                      "verification_url": self._verification_url, "user_code": self._user_code,
                      "code": error or (operation.get("code") if operation else None),
                      "message": MESSAGES[error] if error else (MESSAGES[operation["code"]] if operation and operation.get("code") else STATE_MESSAGES.get(state)),
                      "verified_at": active["verified_at"] if active else None,
                      "active": {"profile_id": PROFILE.fullmatch(active["profile"]).group(1), "verified_at": active["verified_at"]} if active else None,
                      "pending": {"profile_id": PROFILE.fullmatch(operation["profile"]).group(1), "status": state,
                                  "expires_at": operation.get("expires_at")} if operation and operation.get("profile") else None}
            return result

    def _busy(self) -> dict:
        return {**self.status(), "code": "CONNECTION_BUSY", "message": MESSAGES["CONNECTION_BUSY"]}

    def _begin(self, kind: str, profile: str) -> bool:
        if self._closed or self._initial_error or not _locking_available() or (self._worker and self._worker.is_alive()) or not self._acquire():
            return False
        self._cancel = threading.Event()
        self._verification_url = self._user_code = None
        seconds = self.login_timeout_seconds if kind == "login" else self.probe_timeout_seconds
        self._write({"version": 1, "operation_id": uuid4().hex, "kind": kind, "profile": profile,
                     "status": "starting" if kind == "login" else "probing", "authentication": "unknown",
                     "started_at": _now(), "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(),
                     "handle": None, "code": None, "message": None})
        return True

    def login(self) -> dict:
        with self._mutex:
            if self._initial_error or not _locking_available():
                return self.status()
            if (self._worker and self._worker.is_alive()) or not self._acquire():
                return self._busy()
            try:
                self._recover()
                previous = self._operation()
                selection = self._selection()
            except (OSError, ValueError, KeyError, TypeError):
                self._release()
                return {**self.status(), "status": "blocked", "code": "AUTH_STORAGE_INVALID", "message": MESSAGES["AUTH_STORAGE_INVALID"]}
            if previous and previous.get("code") == "CLEANUP_UNCONFIRMED":
                self._release()
                return self.status()
            if selection and selection.get("logged_out") and selection.get("profiles"):
                self._release()
                return {**self.status(), "status": "blocked", "code": "LOGOUT_FAILED", "message": MESSAGES["LOGOUT_FAILED"]}
            binary = shutil.which(self.executable)
            if not binary and Path(self.executable).suffix.casefold() == ".py" and Path(self.executable).is_file():
                binary = str(Path(self.executable).resolve())
            if not binary:
                self._release()
                return {**self.status(), "status": "blocked", "code": "CODEX_NOT_FOUND", "message": MESSAGES["CODEX_NOT_FOUND"]}
            profile = "profiles/" + uuid4().hex
            _private_directory(self.root / profile)
            if not self._begin("login", profile):
                self._release()
                return self._busy()
            self._worker = threading.Thread(target=self._login_worker, args=(binary, profile), daemon=True)
            self._worker.start()
            return self.status()

    def _login_worker(self, binary: str, profile: str) -> None:
        diagnostics = bytearray()
        overflow = threading.Event()
        stop_readers = threading.Event()
        reader_error = threading.Event()
        process = None
        threads = []
        try:
            home = self._home(profile)
            environment = _environment(home)
            command = [*_cli_command(binary), "--no-daemon", "-c", 'cli_auth_credentials_store="file"', "login", "--device-auth"]
            process = subprocess.Popen(command, cwd=home, env=environment, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_process_options(suspended=True))
            _track_process(process, suspended=True)
            self._record_handle(_worker_handle(process))
            operation_id = self._operation()["operation_id"]
            def drain(pipe) -> None:
                try:
                    while True:
                        part = pipe.read1(4096)
                        if not part:
                            return
                        with self._mutex:
                            current = self._operation()
                            if (stop_readers.is_set() or current is None or current["operation_id"] != operation_id
                                    or current.get("profile") != profile or current["status"] not in {"starting", "waiting_user"}):
                                return
                            room = max(0, MAX_DIAGNOSTIC_BYTES - len(diagnostics))
                            diagnostics.extend(part[:room])
                            if len(part) > room:
                                overflow.set()
                                return
                            url, code = _challenge(diagnostics.decode("utf-8", "replace"))
                            if url and code:
                                self._verification_url, self._user_code = url, code
                                if self._operation()["status"] != "waiting_user":
                                    self._update(status="waiting_user")
                except (OSError, ValueError, KeyError, TypeError):
                    reader_error.set()
                finally:
                    pipe.close()
            for pipe in (process.stdout, process.stderr):
                thread = threading.Thread(target=drain, args=(pipe,), daemon=True)
                threads.append(thread)
                thread.start()
            deadline = time.monotonic() + self.login_timeout_seconds
            challenge_deadline = time.monotonic() + self.startup_challenge_timeout_seconds
            challenge_expired = False
            while process.poll() is None:
                with self._mutex:
                    challenge_expired = not self._user_code and time.monotonic() >= challenge_deadline
                if self._cancel_requested() or overflow.is_set() or reader_error.is_set() or challenge_expired or time.monotonic() >= deadline:
                    break
                time.sleep(0.05)
            # A successfully exited leader can leave descendants holding its
            # pipes or writing credentials. Confirm its recorded group ended.
            if not self._confirm_cleanup(profile, process):
                self._failure("CLEANUP_UNCONFIRMED")
                return
            for thread in threads:
                thread.join(timeout=1)
            if self._cancel_requested():
                self._failure("CANCELLED", status="cancelled")
            elif overflow.is_set():
                self._failure("OUTPUT_LIMIT")
            elif reader_error.is_set():
                self._failure("CONFIGURATION_ERROR")
            elif challenge_expired:
                self._failure("LOGIN_START_TIMEOUT")
            elif time.monotonic() >= deadline:
                self._failure("LOGIN_TIMEOUT")
            elif process.returncode:
                text = diagnostics.decode("utf-8", "replace").casefold()
                code = "DEVICE_AUTH_UNAVAILABLE" if "device code login is not enabled" in text else "PROXY_BLOCKED" if "403" in text and ("proxy" in text or "connect" in text) else "AUTH_REQUIRED" if "401" in text or "unauthorized" in text else "NETWORK_ERROR" if any(word in text for word in ("proxy", "network", "connect", "403")) else "CODEX_FAILED"
                self._failure(code)
            else:
                public = self.provider_factory(home).status()
                authentication = public.get("authentication", "unknown")
                self._update(authentication=authentication if authentication in {"chatgpt", "api_key", "logged_out"} else "unknown")
                if self._cancel_requested():
                    self._failure("CANCELLED", status="cancelled")
                elif authentication != "chatgpt" or public.get("ready") is not True:
                    self._failure("API_KEY_UNSUPPORTED" if authentication == "api_key" else "AUTH_REQUIRED")
                else:
                    self._update(status="authenticated", handle=None, code=None,
                                 message="공식 구독 로그인이 완료되었습니다. 연결 확인을 실행하면 사용할 수 있습니다.")
        except Exception:
            self._failure("CONFIGURATION_ERROR" if self._confirm_cleanup(profile, process) else "CLEANUP_UNCONFIRMED")
        finally:
            stop_readers.set()
            if process is not None and process.poll() is None:
                _try_stop(process)
            diagnostics.clear()
            with self._mutex:
                self._verification_url = self._user_code = None
                self._release()

    def probe(self) -> dict:
        with self._mutex:
            if self._initial_error or not _locking_available():
                return self.status()
            if (self._worker and self._worker.is_alive()) or not self._acquire():
                return self._busy()
            try:
                self._recover()
                pending, active = self._operation(), self._active()
                if pending and pending.get("code") == "CLEANUP_UNCONFIRMED":
                    self._release()
                    return self.status()
                profile = pending.get("profile") if pending and pending.get("authentication") == "chatgpt" and pending["status"] not in {"cancelled", "starting", "waiting_user"} else active["profile"] if active else None
                if profile is None:
                    self._release()
                    return {**self.status(), "status": "blocked", "code": "AUTH_REQUIRED", "message": MESSAGES["AUTH_REQUIRED"]}
                if not self._begin("probe", profile):
                    self._release()
                    return self._busy()
                self._worker = threading.Thread(target=self._probe_worker, args=(profile,), daemon=True)
                self._worker.start()
                return self.status()
            except (OSError, ValueError, TypeError, KeyError):
                self._release()
                return {**self.status(), "status": "blocked", "code": "AUTH_STORAGE_INVALID", "message": MESSAGES["AUTH_STORAGE_INVALID"]}

    def _probe_worker(self, profile: str) -> None:
        temporary = None
        cleanup_unconfirmed = False
        try:
            provider = self.provider_factory(self._home(profile))
            public = provider.status()
            authentication = public.get("authentication", "unknown")
            self._update(authentication=authentication if authentication in {"chatgpt", "api_key", "logged_out"} else "unknown")
            if authentication != "chatgpt" or public.get("ready") is not True:
                self._probe_failure(profile, "API_KEY_UNSUPPORTED" if authentication == "api_key" else "AUTH_REQUIRED")
                return
            temporary = Path(tempfile.mkdtemp(prefix="probe-", dir=self.root / ".probe-runtime"))
            response = provider.generate("Without using tools, return exactly the JSON object {\"ready\":true} to confirm that this subscription can make a model request.",
                                         PROBE_SCHEMA, temporary / "call", cancel=self._cancel_requested,
                                         timeout_seconds=self.probe_timeout_seconds,
                                         on_handle=self._record_handle)
            if self._cancel_requested():
                self._probe_failure(profile, "CANCELLED", status="cancelled")
                return
            if not isinstance(response, dict) or set(response) != {"ready"} or response["ready"] is not True:
                self._probe_failure(profile, "SCHEMA_ERROR")
                return
            if not self._confirm_cleanup(profile):
                self._failure("CLEANUP_UNCONFIRMED")
                return
            with self._mutex:
                if not self._state_acquire(blocking=True):
                    self._failure("CONFIGURATION_ERROR")
                    return
                try:
                    if self._cancel_requested():
                        self._failure("CANCELLED", status="cancelled")
                        return
                    verified = _now()
                    _write_metadata(self.root / "active.json", {"version": 1, "profile": profile, "verified": True, "verified_at": verified})
                    self._update(status="available", authentication="chatgpt", handle=None, code=None,
                                 message="구독 모델의 실제 응답을 확인했습니다.")
                finally:
                    self._state_release()
        except ProviderBlocked as exc:
            cleanup_unconfirmed = exc.code == "CLEANUP_UNCONFIRMED"
            if cleanup_unconfirmed:
                # Initialization can fail before the normal callback delivers
                # its capability. Keep it and its private receipts until an
                # explicit recovery confirms the worker tree has terminated.
                if exc.active_handle:
                    try:
                        self._record_handle(exc.active_handle)
                    except (OSError, ValueError, TypeError):
                        pass  # Missing or unpersistable identity must still block recovery.
                self._failure("CLEANUP_UNCONFIRMED")
            else:
                self._probe_failure(profile, exc.code, status="cancelled" if exc.code == "CANCELLED" else "blocked")
        except Exception:
            self._probe_failure(profile, "CONFIGURATION_ERROR")
        finally:
            if temporary is not None and not cleanup_unconfirmed and self._confirm_cleanup(profile):
                try:
                    ensure_unlinked(temporary)
                    shutil.rmtree(temporary)
                except (OSError, ValueError):
                    self._probe_failure(profile, "CONFIGURATION_ERROR")
            with self._mutex:
                self._verification_url = self._user_code = None
                self._release()

    def cancel(self) -> dict:
        with self._mutex:
            if self._worker and self._worker.is_alive():
                self._cancel.set()
                worker = self._worker
            else:
                if self._initial_error:
                    return self.status()
                if not self._acquire():
                    # Explicit cancellation from another CLI/server instance
                    # is a nonce-bound intent, not permission to kill a PID.
                    if not self._state_acquire():
                        return self._busy()
                    try:
                        operation = self._operation()
                        if operation and operation["status"] in {"starting", "waiting_user", "probing"}:
                            _write_metadata(self.root / ".cancel.json", {"version": 1, "operation_id": operation["operation_id"], "requested_at": _now()})
                            return {**self.status(), "code": "CANCEL_REQUESTED", "message": MESSAGES["CANCEL_REQUESTED"]}
                        return self.status()
                    finally:
                        self._state_release()
                try:
                    previous = self._operation()
                    self._recover()
                    operation = self._operation()
                    if operation and operation.get("code") == "CLEANUP_UNCONFIRMED":
                        return self.status()
                    # Completed connections and logout failures are durable
                    # results, not work to cancel during ordinary app shutdown.
                    if previous and previous["status"] in {"starting", "waiting_user", "probing"}:
                        self._failure("CANCELLED", status="cancelled")
                    self._verification_url = self._user_code = None
                finally:
                    self._release()
                return self.status()
        worker.join(timeout=10)
        return self.status()

    def _logout_cli(self, binary: str, profile: str, arguments: list[str], deadline: float,
                    *, capture: bool = False) -> tuple[int, str]:
        """Run a bounded owned CLI worker; keep only the authentication kind."""
        diagnostics = bytearray()
        overflow = threading.Event()
        reader_error = threading.Event()
        process = None
        reader = None
        clean = False
        try:
            if time.monotonic() >= deadline:
                raise ProviderBlocked("LOGOUT_TIMEOUT", MESSAGES["LOGOUT_TIMEOUT"])
            home = self._home(profile)
            command = [*_cli_command(binary), "--no-daemon", "-c", 'cli_auth_credentials_store="file"', *arguments]
            process = subprocess.Popen(command, cwd=home, env=_environment(home), stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                                       stderr=subprocess.STDOUT if capture else subprocess.DEVNULL,
                                       **_process_options(suspended=True))
            _track_process(process, suspended=True)
            self._record_handle(_worker_handle(process))
            if capture:
                def drain():
                    try:
                        while part := process.stdout.read1(4096):
                            room = max(0, MAX_DIAGNOSTIC_BYTES - len(diagnostics))
                            diagnostics.extend(part[:room])
                            if len(part) > room:
                                overflow.set()
                                return
                    except (OSError, ValueError):
                        reader_error.set()
                    finally:
                        process.stdout.close()
                reader = threading.Thread(target=drain, daemon=True)
                reader.start()
            while process.poll() is None and time.monotonic() < deadline and not overflow.is_set() and not reader_error.is_set():
                time.sleep(0.02)
            timed_out = process.poll() is None and time.monotonic() >= deadline
            clean = self._confirm_cleanup(profile, process)
            if not clean:
                raise ProviderBlocked("CLEANUP_UNCONFIRMED", MESSAGES["CLEANUP_UNCONFIRMED"])
            if reader and reader.ident is not None:
                reader.join(timeout=1)
            if timed_out:
                raise ProviderBlocked("LOGOUT_TIMEOUT", MESSAGES["LOGOUT_TIMEOUT"])
            if overflow.is_set():
                raise ProviderBlocked("OUTPUT_LIMIT", MESSAGES["OUTPUT_LIMIT"])
            if reader_error.is_set() or reader and reader.is_alive():
                raise ProviderBlocked("LOGOUT_FAILED", MESSAGES["LOGOUT_FAILED"])
            self._update(handle=None)
            return process.returncode, _authentication_kind(diagnostics.decode("utf-8", "replace"))
        except ProviderBlocked:
            raise
        except Exception:
            clean = self._confirm_cleanup(profile, process)
            code = "CONFIGURATION_ERROR" if clean else "CLEANUP_UNCONFIRMED"
            raise ProviderBlocked(code, MESSAGES[code]) from None
        finally:
            if reader and reader.ident is not None:
                reader.join(timeout=1)
            elif capture and process is not None and process.stdout is not None:
                process.stdout.close()
            diagnostics.clear()

    def logout(self) -> dict:
        with self._mutex:
            if self._initial_error or not _locking_available():
                return self.status()
            if self._closed or (self._worker and self._worker.is_alive()) or not self._acquire():
                return self._busy()
            try:
                self._recover()
                operation = self._operation()
                if operation and operation.get("code") == "CLEANUP_UNCONFIRMED":
                    return self.status()
                selection = self._selection()
                profiles = list(selection.get("profiles", [])) if selection and selection.get("logged_out") else [selection["profile"]] if selection else []
                if operation and operation.get("profile") and operation["profile"] not in profiles:
                    profiles.append(operation["profile"])
                # Disable research before touching credentials, including on
                # timeout/restart. Only the CLI edits its app-owned auth store.
                _write_metadata(self.root / "active.json", {"version": 1, "logged_out": True, "profiles": profiles})
                self._write({"version": 1, "operation_id": uuid4().hex, "kind": "logout", "profile": profiles[0] if profiles else None,
                             "status": "logging_out", "authentication": "unknown", "started_at": _now(),
                             "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=self.logout_timeout_seconds)).isoformat(),
                             "handle": None, "code": None, "message": None})
                binary = shutil.which(self.executable)
                if not binary and Path(self.executable).suffix.casefold() == ".py" and Path(self.executable).is_file():
                    binary = str(Path(self.executable).resolve())
                if profiles and not binary:
                    self._failure("CODEX_NOT_FOUND")
                    return self.status()
                deadline = time.monotonic() + self.logout_timeout_seconds
                for profile in list(profiles):
                    self._update(profile=profile)
                    code, _ = self._logout_cli(binary, profile, ["logout"], deadline)
                    if code != 0:
                        raise ProviderBlocked("LOGOUT_FAILED", MESSAGES["LOGOUT_FAILED"])
                    _, authentication = self._logout_cli(binary, profile, ["login", "status"], deadline, capture=True)
                    if authentication != "logged_out":
                        raise ProviderBlocked("LOGOUT_FAILED", MESSAGES["LOGOUT_FAILED"])
                    profiles.remove(profile)
                    _write_metadata(self.root / "active.json", {"version": 1, "logged_out": True, "profiles": profiles})
                _write_metadata(self.root / "active.json", {"version": 1, "logged_out": True})
                self._update(status="logged_out", profile=None, authentication="logged_out", handle=None, code=None,
                             message=STATE_MESSAGES["logged_out"])
                self._verification_url = self._user_code = None
            except ProviderBlocked as exc:
                self._failure(exc.code)
            except (OSError, ValueError, TypeError):
                return {**self.status(), "status": "blocked", "code": "AUTH_STORAGE_INVALID", "message": MESSAGES["AUTH_STORAGE_INVALID"]}
            finally:
                self._release()
            return self.status()

    def close(self) -> None:
        with self._mutex:
            running = self._worker is not None and self._worker.is_alive()
        if running:
            self.cancel()
        with self._mutex:
            self._closed = True
            if not (self._worker and self._worker.is_alive()):
                self._release()
                if self._lock_fd is not None:
                    os.close(self._lock_fd)
                    self._lock_fd = None
                if self._state_fd is not None:
                    os.close(self._state_fd)
                    self._state_fd = None

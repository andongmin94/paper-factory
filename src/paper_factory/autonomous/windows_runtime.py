"""Windows access control, owned process jobs and networkless AppContainer runs.

No generated program is launched with the controller's token or credentials.
Only copied research/runtime files and dedicated output directories are granted
to the ephemeral AppContainer. The job terminates its entire process tree.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
from functools import lru_cache
import os
from pathlib import Path
import re
import stat
import subprocess
import time
from uuid import uuid4

from ..workspace import ensure_unlinked

MAX_LOG_BYTES = 128 * 1024
JOB_NAME = re.compile(r"Local\\paper-factory-(?:codex|research)-[a-f0-9]{32}\Z")
PROFILE_NAME = re.compile(r"paper-factory-research-[a-f0-9]{32}\Z")


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("length", w.DWORD), ("descriptor", w.LPVOID), ("inherit", w.BOOL)]


class SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [("sid", w.LPVOID), ("capabilities", w.LPVOID), ("count", w.DWORD), ("reserved", w.DWORD)]


class STARTUPINFO(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("reserved", w.LPWSTR), ("desktop", w.LPWSTR), ("title", w.LPWSTR),
               ("x", w.DWORD), ("y", w.DWORD), ("xsize", w.DWORD), ("ysize", w.DWORD),
               ("xchars", w.DWORD), ("ychars", w.DWORD), ("fill", w.DWORD), ("flags", w.DWORD),
               ("show", w.WORD), ("reserved_size", w.WORD), ("reserved_bytes", w.LPVOID),
               ("stdin", w.HANDLE), ("stdout", w.HANDLE), ("stderr", w.HANDLE)]


class STARTUPINFOEX(ctypes.Structure):
    _fields_ = [("startup", STARTUPINFO), ("attributes", w.LPVOID)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("process", w.HANDLE), ("thread", w.HANDLE), ("pid", w.DWORD), ("tid", w.DWORD)]


class THREADENTRY32(ctypes.Structure):
    _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("tid", w.DWORD), ("pid", w.DWORD),
               ("base_priority", w.LONG), ("delta_priority", w.LONG), ("flags", w.DWORD)]


class BASIC_LIMITS(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong), ("flags", w.DWORD),
               ("min_working_set", ctypes.c_size_t), ("max_working_set", ctypes.c_size_t),
               ("active_processes", w.DWORD), ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]


class EXTENDED_LIMITS(ctypes.Structure):
    _fields_ = [("basic", BASIC_LIMITS), ("io", IO_COUNTERS), ("process_memory", ctypes.c_size_t),
               ("job_memory", ctypes.c_size_t), ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]


@lru_cache(maxsize=1)
def _api():
    if os.name != "nt":
        raise OSError("Windows native isolation is only available on Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    userenv = ctypes.WinDLL("userenv", use_last_error=True)
    signatures = {
        kernel: {
            "GetCurrentProcess": ([], w.HANDLE), "CloseHandle": ([w.HANDLE], w.BOOL),
            "LocalFree": ([w.LPVOID], w.LPVOID), "OpenProcess": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            "GetProcessTimes": ([w.HANDLE, *[ctypes.POINTER(w.FILETIME)] * 4], w.BOOL),
            "CreateJobObjectW": ([ctypes.POINTER(SECURITY_ATTRIBUTES), w.LPCWSTR], w.HANDLE),
            "OpenJobObjectW": ([w.DWORD, w.BOOL, w.LPCWSTR], w.HANDLE),
            "SetInformationJobObject": ([w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD], w.BOOL),
            "QueryInformationJobObject": ([w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, w.LPVOID], w.BOOL),
            "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
            "TerminateJobObject": ([w.HANDLE, w.UINT], w.BOOL),
            "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
            "GetExitCodeProcess": ([w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
            "TerminateProcess": ([w.HANDLE, w.UINT], w.BOOL),
            "ResumeThread": ([w.HANDLE], w.DWORD),
            "CreateToolhelp32Snapshot": ([w.DWORD, w.DWORD], w.HANDLE),
            "Thread32First": ([w.HANDLE, ctypes.POINTER(THREADENTRY32)], w.BOOL),
            "Thread32Next": ([w.HANDLE, ctypes.POINTER(THREADENTRY32)], w.BOOL),
            "OpenThread": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            "GetProcessIdOfThread": ([w.HANDLE], w.DWORD),
            "CreateFileW": ([w.LPCWSTR, w.DWORD, w.DWORD, ctypes.POINTER(SECURITY_ATTRIBUTES), w.DWORD, w.DWORD, w.HANDLE], w.HANDLE),
            "InitializeProcThreadAttributeList": ([w.LPVOID, w.DWORD, w.DWORD, ctypes.POINTER(ctypes.c_size_t)], w.BOOL),
            "UpdateProcThreadAttribute": ([w.LPVOID, w.DWORD, ctypes.c_size_t, w.LPVOID, ctypes.c_size_t, w.LPVOID, w.LPVOID], w.BOOL),
            "DeleteProcThreadAttributeList": ([w.LPVOID], None),
            "CreateProcessW": ([w.LPCWSTR, w.LPWSTR, w.LPVOID, w.LPVOID, w.BOOL, w.DWORD, w.LPVOID, w.LPCWSTR, ctypes.POINTER(STARTUPINFOEX), ctypes.POINTER(PROCESS_INFORMATION)], w.BOOL),
        },
        advapi: {
            "OpenProcessToken": ([w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)], w.BOOL),
            "GetTokenInformation": ([w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD)], w.BOOL),
            "ConvertSidToStringSidW": ([w.LPVOID, ctypes.POINTER(w.LPWSTR)], w.BOOL),
            "ConvertStringSecurityDescriptorToSecurityDescriptorW": ([w.LPCWSTR, w.DWORD, ctypes.POINTER(w.LPVOID), w.LPVOID], w.BOOL),
            "GetSecurityDescriptorDacl": ([w.LPVOID, ctypes.POINTER(w.BOOL), ctypes.POINTER(w.LPVOID), ctypes.POINTER(w.BOOL)], w.BOOL),
            "SetNamedSecurityInfoW": ([w.LPWSTR, ctypes.c_int, w.DWORD, w.LPVOID, w.LPVOID, w.LPVOID, w.LPVOID], w.DWORD),
            "GetNamedSecurityInfoW": ([w.LPCWSTR, ctypes.c_int, w.DWORD, ctypes.POINTER(w.LPVOID), w.LPVOID, ctypes.POINTER(w.LPVOID), w.LPVOID, ctypes.POINTER(w.LPVOID)], w.DWORD),
            "GetAce": ([w.LPVOID, w.DWORD, ctypes.POINTER(w.LPVOID)], w.BOOL),
            "FreeSid": ([w.LPVOID], w.LPVOID),
        },
        userenv: {
            "CreateAppContainerProfile": ([w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, w.LPVOID, w.DWORD, ctypes.POINTER(w.LPVOID)], ctypes.c_long),
            "DeleteAppContainerProfile": ([w.LPCWSTR], ctypes.c_long),
        },
    }
    for library, functions in signatures.items():
        for name, (arguments, result) in functions.items():
            function = getattr(library, name)
            function.argtypes, function.restype = arguments, result
    return kernel, advapi, userenv


def _checked(value):
    if not value:
        raise ctypes.WinError(ctypes.get_last_error())
    return value


def _sid_text(sid) -> str:
    kernel, advapi, _ = _api()
    text = w.LPWSTR()
    _checked(advapi.ConvertSidToStringSidW(sid, ctypes.byref(text)))
    try:
        return text.value
    finally:
        kernel.LocalFree(text)


@lru_cache(maxsize=1)
def _user_sid() -> str:
    kernel, advapi, _ = _api()
    token, size = w.HANDLE(), w.DWORD()
    _checked(advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)))
    try:
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value)
        _checked(advapi.GetTokenInformation(token, 1, buffer, size, ctypes.byref(size)))
        return _sid_text(ctypes.cast(buffer, ctypes.POINTER(w.LPVOID))[0])
    finally:
        kernel.CloseHandle(token)


def _descriptor(sddl: str):
    descriptor = w.LPVOID()
    _checked(_api()[1].ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None))
    return descriptor


def _set_acl(path: Path, extra: str = "") -> None:
    kernel, advapi, _ = _api()
    inheritance = "OICI" if path.is_dir() else ""
    descriptor = _descriptor(f"D:P(A;{inheritance};FA;;;{_user_sid()})(A;{inheritance};FA;;;SY)" + extra)
    try:
        present, defaulted, acl = w.BOOL(), w.BOOL(), w.LPVOID()
        _checked(advapi.GetSecurityDescriptorDacl(descriptor, ctypes.byref(present), ctypes.byref(acl), ctypes.byref(defaulted)))
        error = advapi.SetNamedSecurityInfoW(str(path), 1, 0x80000004, None, None, acl, None)
        if error:
            raise ctypes.WinError(error)
    finally:
        kernel.LocalFree(descriptor)


def private_path(path: Path) -> None:
    ensure_unlinked(path)
    if os.name == "nt":
        _set_acl(path)
    else:
        path.chmod(0o700 if path.is_dir() else 0o600)


def is_private_path(path: Path) -> bool:
    ensure_unlinked(path)
    if os.name != "nt":
        info = path.stat()
        return not info.st_mode & 0o077 and (not hasattr(os, "getuid") or info.st_uid == os.getuid())
    kernel, advapi, _ = _api()
    owner, acl, descriptor = w.LPVOID(), w.LPVOID(), w.LPVOID()
    error = advapi.GetNamedSecurityInfoW(str(path), 1, 5, ctypes.byref(owner), None, ctypes.byref(acl), None, ctypes.byref(descriptor))
    if error:
        raise ctypes.WinError(error)
    try:
        if not acl.value or _sid_text(owner) != _user_sid():
            return False
        # ACL header: revision, reserved, size, ACE count, reserved.
        count = ctypes.cast(acl, ctypes.POINTER(ctypes.c_ushort))[2]
        own_access = False
        for index in range(count):
            ace = w.LPVOID()
            _checked(advapi.GetAce(acl, index, ctypes.byref(ace)))
            kind = ctypes.cast(ace, ctypes.POINTER(ctypes.c_ubyte))[0]
            if kind != 0:  # Only ordinary allow entries are used by this store.
                return False
            sid = _sid_text(w.LPVOID(ace.value + 8))
            if sid not in {_user_sid(), "S-1-5-18"}:
                return False
            own_access |= sid == _user_sid()
        return own_access
    finally:
        kernel.LocalFree(descriptor)


def process_ticks(pid: int) -> int | None:
    kernel, _, _ = _api()
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:  # No such process. Access denied is an uncertain outcome.
            return None
        raise ctypes.WinError(error)
    try:
        code = w.DWORD()
        _checked(kernel.GetExitCodeProcess(handle, ctypes.byref(code)))
        if code.value != 259:  # STILL_ACTIVE
            return None
        created, exited, system, user = (w.FILETIME() for _ in range(4))
        _checked(kernel.GetProcessTimes(handle, *[ctypes.byref(item) for item in (created, exited, system, user)]))
        return (created.dwHighDateTime << 32) | created.dwLowDateTime
    finally:
        kernel.CloseHandle(handle)


def resume_process(pid: int) -> None:
    """Resume the initial thread of a held, controller-created suspended process."""
    if type(pid) is not int or pid <= 1:
        raise ValueError("Invalid owned suspended process identity")
    kernel, _, _ = _api()
    snapshot = kernel.CreateToolhelp32Snapshot(0x4, 0)  # TH32CS_SNAPTHREAD
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = THREADENTRY32()
        entry.size = ctypes.sizeof(entry)
        threads = []
        found = kernel.Thread32First(snapshot, ctypes.byref(entry))
        while found:
            if entry.pid == pid:
                threads.append(entry.tid)
            entry.size = ctypes.sizeof(entry)
            found = kernel.Thread32Next(snapshot, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(ctypes.get_last_error())
        if len(threads) != 1:
            raise OSError("Suspended process must have exactly one initial thread")
        # Recheck ownership after opening: snapshot thread IDs can be reused.
        thread = _checked(kernel.OpenThread(0x0802, False, threads[0]))
        try:
            if kernel.GetProcessIdOfThread(thread) != pid:
                raise OSError("Suspended thread no longer belongs to its owned process")
            previous = kernel.ResumeThread(thread)
            if previous == 0xFFFFFFFF:
                raise ctypes.WinError(ctypes.get_last_error())
            if previous != 1:
                raise OSError("Owned initial thread was not suspended exactly once")
        finally:
            kernel.CloseHandle(thread)
    finally:
        kernel.CloseHandle(snapshot)


class WindowsJob:
    def __init__(self, *, name: str | None = None, limits: dict | None = None):
        kernel, _, _ = _api()
        self.name = name or "Local\\paper-factory-codex-" + uuid4().hex
        if not JOB_NAME.fullmatch(self.name):
            raise ValueError("Invalid owned Windows job name")
        descriptor = _descriptor(f"D:P(A;;GA;;;{_user_sid()})(A;;GA;;;SY)")
        attributes = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), descriptor, False)
        try:
            self.handle = _checked(kernel.CreateJobObjectW(ctypes.byref(attributes), self.name))
        finally:
            kernel.LocalFree(descriptor)
        information = EXTENDED_LIMITS()
        information.basic.flags = 0x2000  # KILL_ON_JOB_CLOSE
        if limits:
            information.basic.flags |= 0x8 | 0x100 | 0x200
            information.basic.active_processes = limits.get("pids", 128)
            information.process_memory = limits.get("memory_bytes", 512 * 1024 * 1024)
            information.job_memory = information.process_memory
            if limits.get("cpu_seconds"):
                information.basic.flags |= 0x2  # Per-process user-mode CPU deadline.
                information.basic.process_time = int(limits["cpu_seconds"] * 10_000_000)
        try:
            _checked(kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(information), ctypes.sizeof(information)))
            if limits and limits.get("cpus"):
                rate = (w.DWORD * 2)(5, min(10000, max(1, int(10000 * limits["cpus"] / (os.cpu_count() or 1)))))
                _checked(kernel.SetInformationJobObject(self.handle, 15, rate, ctypes.sizeof(rate)))
        except BaseException:
            self.close()
            raise

    def assign(self, process_handle) -> None:
        _checked(_api()[0].AssignProcessToJobObject(self.handle, process_handle))

    def stop(self) -> bool:
        return _stop_job(self.handle)

    def close(self) -> None:
        if self.handle:
            _api()[0].CloseHandle(self.handle)
            self.handle = None


def _stop_job(handle) -> bool:
    kernel, _, _ = _api()
    if not kernel.TerminateJobObject(handle, 1):
        return False
    deadline = time.monotonic() + 5
    # JOBOBJECT_BASIC_ACCOUNTING_INFORMATION.ActiveProcesses is at offset 40.
    buffer = ctypes.create_string_buffer(48)
    while time.monotonic() < deadline:
        if not kernel.QueryInformationJobObject(handle, 1, buffer, len(buffer), None):
            return False
        if ctypes.c_uint32.from_buffer(buffer, 40).value == 0:
            return True
        time.sleep(0.02)
    return False


def stop(handle: dict) -> bool:
    name, pid, ticks = (handle.get(key) for key in ("job_name", "pid", "start_ticks"))
    if (not isinstance(name, str) or not JOB_NAME.fullmatch(name) or type(pid) is not int or pid <= 1
            or type(ticks) is not int or ticks <= 0):
        return False
    kernel, _, userenv = _api()
    try:
        job = kernel.OpenJobObjectW(0x000C, False, name)
        if job:
            try:
                clean = _stop_job(job)
            finally:
                kernel.CloseHandle(job)
        elif ctypes.get_last_error() == 2:
            current = process_ticks(pid)
            clean = current is None or current != ticks
        else:
            clean = False
        profile = handle.get("profile_name")
        if clean and profile:
            if not isinstance(profile, str) or not PROFILE_NAME.fullmatch(profile):
                return False
            result = userenv.DeleteAppContainerProfile(profile)
            clean = result in (0, -2147024894)  # success or already absent
        return clean
    except OSError:
        return False


def available() -> bool:
    try:
        _api()
        return True
    except (OSError, AttributeError):
        return False


def launch(command: list[str], *, cwd: Path, environment: dict[str, str], read_only_paths: list[Path],
           writable_paths: list[Path], timeout_seconds: int, cancel=None, on_handle=None, limits=None) -> dict:
    """Start suspended, assign the job, then resume with zero network capabilities."""
    kernel, advapi, userenv = _api()
    profile = "paper-factory-research-" + uuid4().hex
    sid = w.LPVOID()
    result = {"status": "failed", "exit_code": None, "stdout": "", "stderr": "", "cleanup_confirmed": False}
    job = None
    process = PROCESS_INFORMATION()
    handles = []
    attributes = None
    attributes_initialized = False
    profile_created = False
    handle_record = None
    assigned = False
    logs = [cwd / ".controller-stdout.log", cwd / ".controller-stderr.log"]
    try:
        error = userenv.CreateAppContainerProfile(profile, "Paper Factory research", "Isolated generated research", None, 0, ctypes.byref(sid))
        if error:
            raise OSError(f"Cannot create Windows AppContainer (HRESULT {error & 0xffffffff:#x})")
        profile_created = True
        sid_text = _sid_text(sid)
        for root in read_only_paths:
            ensure_unlinked(root)
            _set_acl(root, f"(A;OICI;FRFX;;;{sid_text})")
        for root in writable_paths:
            ensure_unlinked(root)
            _set_acl(root, f"(A;OICI;FA;;;{sid_text})")
        security = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), None, True)
        for path, access, disposition in [("NUL", 0x80000000, 3), *[(str(path), 0x40000000, 2) for path in logs]]:
            opened = kernel.CreateFileW(path, access, 3, ctypes.byref(security), disposition, 0x80, None)
            if opened == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            handles.append(opened)
        size = ctypes.c_size_t()
        kernel.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
        storage = ctypes.create_string_buffer(size.value)
        attributes = ctypes.cast(storage, w.LPVOID)
        _checked(kernel.InitializeProcThreadAttributeList(attributes, 2, 0, ctypes.byref(size)))
        attributes_initialized = True
        capabilities = SECURITY_CAPABILITIES(sid, None, 0, 0)
        _checked(kernel.UpdateProcThreadAttribute(attributes, 0, 0x20009, ctypes.byref(capabilities), ctypes.sizeof(capabilities), None, None))
        inherited = (w.HANDLE * len(handles))(*handles)
        _checked(kernel.UpdateProcThreadAttribute(attributes, 0, 0x20002, inherited, ctypes.sizeof(inherited), None, None))
        startup = STARTUPINFOEX()
        startup.startup.cb = ctypes.sizeof(startup)
        startup.startup.flags = 0x100
        startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = handles
        startup.attributes = attributes
        job = WindowsJob(name="Local\\" + profile, limits=limits or {"memory_bytes": 512 * 1024 * 1024, "pids": 128})
        env = ctypes.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in sorted(environment.items(), key=lambda item: item[0].upper())) + "\0\0")
        args = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
        _checked(kernel.CreateProcessW(command[0], args, None, None, True, 0x00080000 | 0x00000400 | 0x00000004 | 0x08000000,
                                      env, str(cwd), ctypes.byref(startup), ctypes.byref(process)))
        handle_record = {"kind": "windows-experiment", "pid": process.pid, "start_ticks": process_ticks(process.pid),
                         "job_name": job.name, "profile_name": profile}
        result["handle"] = handle_record
        job.assign(process.process)
        assigned = True
        if on_handle:
            on_handle(dict(handle_record))
        if kernel.ResumeThread(process.thread) == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        deadline = time.monotonic() + timeout_seconds
        while kernel.WaitForSingleObject(process.process, 100) == 0x102:
            if cancel and cancel():
                result["status"] = "cancelled"
                break
            if time.monotonic() >= deadline:
                result["status"], result["stderr"] = "timeout", "Windows experiment exceeded its deadline"
                break
            if any(path.stat().st_size > MAX_LOG_BYTES for path in logs):
                result["stderr"] = "Windows experiment exceeded its log limit"
                break
            if limits:
                for root in writable_paths:
                    maximum = limits.get("output_bytes" if root.name == "output" else "work_bytes")
                    if maximum and _directory_bytes(root, maximum) > maximum:
                        result["stderr"] = "Windows experiment exceeded its monitored writable-directory limit"
                        break
                if result["stderr"]:
                    break
        else:
            code = w.DWORD()
            _checked(kernel.GetExitCodeProcess(process.process, ctypes.byref(code)))
            result["exit_code"] = code.value
            result["status"] = "succeeded" if code.value == 0 else "failed"
    except Exception as exc:
        result["stderr"] = "Windows isolation failed: " + str(exc)[:1000]
    finally:
        unassigned_confirmed = True
        if process.process and not assigned:
            kernel.TerminateProcess(process.process, 1)
            unassigned_confirmed = kernel.WaitForSingleObject(process.process, 5000) == 0
        if job is not None:
            result["cleanup_confirmed"] = job.stop() and unassigned_confirmed
            job.close()
        else:
            result["cleanup_confirmed"] = not process.process
        for opened in (process.thread, process.process, *handles):
            if opened:
                kernel.CloseHandle(opened)
        if attributes_initialized:
            kernel.DeleteProcThreadAttributeList(attributes)
        if profile_created and result["cleanup_confirmed"]:
            error = userenv.DeleteAppContainerProfile(profile)
            result["cleanup_confirmed"] = error in (0, -2147024894)
        if sid:
            advapi.FreeSid(sid)
        for key, path in zip(("stdout", "stderr"), logs, strict=True):
            if path.exists():
                try:
                    result[key] = (result[key] + "\n" + _log_text(path)).strip()
                except (OSError, ValueError) as error:
                    result["status"] = "failed"
                    result["stderr"] = "Native log rejected: " + str(error)[:1000]
        if not result["cleanup_confirmed"]:
            result["status"], result["code"] = "blocked", "CLEANUP_UNCONFIRMED"
    return result


def _log_text(path: Path) -> str:
    ensure_unlinked(path)
    before = path.stat(follow_symlinks=False)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(descriptor)
        ensure_unlinked(path)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino)):
            raise ValueError("Native log must be an unchanged regular file with one link")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read(MAX_LOG_BYTES).decode("utf-8", "replace")
    finally:
        os.close(descriptor)


def _directory_bytes(root: Path, maximum: int) -> int:
    total = 0
    for directory, directories, files in os.walk(root, followlinks=False):
        for name in [*directories, *files]:
            path = Path(directory) / name
            ensure_unlinked(path)
            if path.is_file():
                total += path.stat().st_size
                if total > maximum:
                    return total
    return total

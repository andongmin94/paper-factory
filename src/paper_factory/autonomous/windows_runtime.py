"""Owned Windows Job Objects and process identities for trusted bounded workers."""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
from functools import lru_cache
import os
import re
import time
from uuid import uuid4

JOB_NAME = re.compile(r"Local\\paper-factory-(?:codex|research)-[a-f0-9]{32}\Z")


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("length", w.DWORD), ("descriptor", w.LPVOID), ("inherit", w.BOOL)]


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
        raise OSError("Windows owned process jobs require Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
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
            "GetExitCodeProcess": ([w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
        },
        advapi: {
            "OpenProcessToken": ([w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)], w.BOOL),
            "GetTokenInformation": ([w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD)], w.BOOL),
            "ConvertSidToStringSidW": ([w.LPVOID, ctypes.POINTER(w.LPWSTR)], w.BOOL),
            "ConvertStringSecurityDescriptorToSecurityDescriptorW": ([w.LPCWSTR, w.DWORD, ctypes.POINTER(w.LPVOID), w.LPVOID], w.BOOL),
        },
    }
    for library, functions in signatures.items():
        for name, (arguments, result) in functions.items():
            function = getattr(library, name)
            function.argtypes, function.restype = arguments, result
    return kernel, advapi


def _checked(value):
    if not value:
        raise ctypes.WinError(ctypes.get_last_error())
    return value


def _sid_text(sid) -> str:
    kernel, advapi = _api()
    text = w.LPWSTR()
    _checked(advapi.ConvertSidToStringSidW(sid, ctypes.byref(text)))
    try:
        return text.value
    finally:
        kernel.LocalFree(text)


@lru_cache(maxsize=1)
def _user_sid() -> str:
    kernel, advapi = _api()
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


def process_ticks(pid: int) -> int | None:
    kernel, _ = _api()
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


class WindowsJob:
    def __init__(self, *, name: str | None = None, limits: dict | None = None):
        kernel, _ = _api()
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
    kernel, _ = _api()
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
    kernel, _ = _api()
    try:
        job = kernel.OpenJobObjectW(0x000C, False, name)
        if job:
            try:
                return _stop_job(job)
            finally:
                kernel.CloseHandle(job)
        if ctypes.get_last_error() == 2:
            current = process_ticks(pid)
            return current is None or current != ticks
        return False
    except OSError:
        return False

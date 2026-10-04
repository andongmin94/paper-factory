"""Trusted macOS child owner; controller EOF terminates and reaps its Node child.

This standalone helper evaluates no source, generated code, or request payload.
The Node child's standard streams go directly to the original controller.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".writing")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write((json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            raise ValueError("Guardian completion receipt already exists")
        os.rename(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def supervise(command: list[str], control, completion: dict) -> int:
    if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
        raise ValueError("Guardian must exclusively own its child reaping")
    child = None
    stopping = False

    def request_stop(*_args):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    completion.update(guardian_pid=os.getpid(), worker_pid=0, worker_exit_code=None, cleanup_confirmed=False)
    try:
        # The inherited endpoint is the actual liveness capability. It is never
        # passed to Node, and no recovered PID is accepted for signalling.
        if select.select([control], [], [], 0)[0] and control.recv(1, socket.MSG_PEEK) == b"":
            completion["cleanup_confirmed"] = True
            return 1
        child = subprocess.Popen(command, stdin=sys.stdin.buffer, stdout=sys.stdout.buffer,
                                 stderr=sys.stderr.buffer, close_fds=True,
                                 env={**os.environ, "PF_QUICKJS_GUARDIAN": str(os.getpid())})
        completion["worker_pid"] = child.pid
        while child.poll() is None:
            readable = select.select([control], [], [], 0.02)[0]
            if stopping or (readable and control.recv(1) == b""):
                # This exact child cannot be reused while the guardian retains
                # its unreaped Popen and the default SIGCHLD disposition.
                child.kill()
                break
        child.wait(timeout=5)
        completion.update(worker_exit_code=child.returncode, cleanup_confirmed=True)
        return child.returncode if child.returncode >= 0 else 128 - child.returncode
    finally:
        if child is None:
            completion["cleanup_confirmed"] = True
        elif child.poll() is not None:
            completion.update(worker_exit_code=child.returncode, cleanup_confirmed=True)
        else:
            try:
                child.kill()
                child.wait(timeout=5)
                completion.update(worker_exit_code=child.returncode, cleanup_confirmed=True)
            except (OSError, subprocess.TimeoutExpired):
                completion["cleanup_confirmed"] = False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-fd", type=int, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--worker-sha256", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if sys.platform != "darwin" or args.control_fd < 3:
        raise ValueError("This guardian requires macOS and its inherited control endpoint")
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if len(command) != 4 or command[1] != "--max-old-space-size=128":
        raise ValueError("Guardian accepts only the fixed trusted Node worker command")
    worker = Path(__file__).with_name("quickjs_worker.mjs")
    if command[2] != str(worker) or digest(worker) != args.worker_sha256:
        raise ValueError("Trusted worker bytes differ")
    completion = {"format": "paper-factory-quickjs-guardian-v1", "owner_nonce": args.nonce,
                  "guardian_sha256": digest(Path(__file__)), "worker_sha256": args.worker_sha256,
                  "node_path": command[0], "owner_uid": os.getuid()}
    with socket.socket(fileno=args.control_fd) as control:
        try:
            return supervise(command, control, completion)
        finally:
            record(args.receipt, completion)


if __name__ == "__main__":
    raise SystemExit(main())

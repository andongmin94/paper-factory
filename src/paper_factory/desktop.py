"""Private, token-gated backend owned by the Windows desktop application."""
from __future__ import annotations

import argparse
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
import threading
import time

from .autonomous.connection import ConnectionManager
from .autonomous.provider import ProviderBlocked, auth_root
from .web import WebHandler, WebServer, WebState
from .workspace import Workspace, pf_home


class DesktopState(WebState):
    def _recover_pipelines(self, interrupted: dict[str, set[str]]):
        """Reconcile abandoned workers without restarting subscription work."""
        from .autonomous import pipeline
        from .autonomous.models import PipelineRun
        with self.lock:
            if self.closed:
                return
            for project_id, project in self.projects.items():
                if project.get("status") != "ready":
                    continue
                try:
                    ws = Workspace(self.workspace_path(project_id))
                    scheduled = {job.get("pipeline_id") for job in self.jobs.values()
                                 if job.get("project_id") == project_id and job.get("status") in {"queued", "running"}}
                    for saved in ws.list("pipeline", PipelineRun):
                        if saved.id not in scheduled and saved.status in {"queued", "running"}:
                            pipeline.recover(ws, saved.id)
                except (OSError, ValueError) as exc:
                    project["autonomous_error"] = self.redact(str(exc))[:2000]
                    self._save_projects()

    def agent_status(self) -> dict:
        status = super().agent_status()
        status["tools"] = {
            "git": shutil.which("git") is not None,
            "pandoc": shutil.which(os.environ.get("PYPANDOC_PANDOC") or "pandoc") is not None,
        }
        return status

    def request_shutdown(self, *, timeout: float = 20) -> dict:
        """Stop owned research before allowing Electron to close its backend."""
        from .autonomous import pipeline
        from .autonomous.models import PipelineRun
        with self.lock:
            if self.closed:
                return {"ready": False, "code": "SHUTDOWN_BUSY", "error": "앱 종료가 이미 진행 중입니다. 종료 확인을 기다려 주세요."}
            active = [dict(job) for job in self.jobs.values() if job["status"] in {"queued", "running"}]
            if any("pipeline_id" not in job for job in active):
                return {"ready": False, "code": "SHUTDOWN_BUSY", "error": "프로젝트 가져오기가 끝난 뒤 앱을 닫아 주세요."}
            self.closed = True
        ready = False
        try:
            for job in active:
                ws = Workspace(self.workspace_path(job["project_id"]))
                try:
                    pipeline.cancel(ws, job["pipeline_id"])
                except ValueError:
                    # Completion can win the race between the job snapshot and
                    # cancellation. A completed run already needs no request.
                    if ws.get("pipeline", job["pipeline_id"], PipelineRun).status != "completed":
                        raise
            deadline = time.monotonic() + timeout
            while True:
                with self.lock:
                    remaining = any(job["status"] in {"queued", "running"} for job in self.jobs.values())
                if not remaining or time.monotonic() >= deadline:
                    break
                time.sleep(0.05)
            if remaining:
                return {"ready": False, "code": "SHUTDOWN_BUSY", "error": "연구 중단을 요청했습니다. 작업자가 종료된 뒤 다시 닫아 주세요."}
            for project_id, project in self.projects.items():
                if project.get("status") != "ready":
                    continue
                ws = Workspace(self.workspace_path(project_id))
                for entry in pipeline.list_runs(ws):
                    saved = ws.get("pipeline", entry["id"], PipelineRun)
                    if saved.active_handle or saved.code == "CLEANUP_UNCONFIRMED":
                        return {"ready": False, "code": "CLEANUP_UNCONFIRMED", "error": "연구 작업자의 종료를 확인하지 못했습니다. 앱을 유지하고 작업 상태를 확인해 주세요."}
            if self._connection is not None:
                result = self._connection.cancel()
                if result.get("status") in {"starting", "waiting_user", "probing", "logging_out"} or result.get("code") in {"CLEANUP_UNCONFIRMED", "CONNECTION_BUSY", "CANCEL_REQUESTED"}:
                    return {"ready": False, "code": "CLEANUP_UNCONFIRMED", "error": "Codex 연결 작업자의 종료를 확인하지 못했습니다. 잠시 뒤 다시 닫아 주세요."}
            ready = True
            return {"ready": True}
        except (OSError, ValueError, KeyError):
            return {"ready": False, "code": "CLEANUP_UNCONFIRMED", "error": "작업 상태와 종료를 확인하지 못했습니다. 앱을 유지하고 다시 시도해 주세요."}
        finally:
            # A failed close remains usable; the cancellation request is retained.
            if not ready:
                self.closed = False


class DesktopHandler(WebHandler):
    def _dispatch(self):
        self._host_guard()
        supplied = self.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied, "Bearer " + self.server.desktop_token):
            raise PermissionError("Desktop requests require the private application session")
        if self._parts() == ["api", "desktop", "shutdown"]:
            if self.command != "POST":
                return self._reply(405, {"error": "Method is unavailable"})
            self._write_guard()
            if self._body():
                raise ValueError("Shutdown does not accept fields")
            result = self.state.request_shutdown()
            self._reply(200 if result["ready"] else 409, result)
            if result["ready"]:
                self.state.closed = True
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        return super()._dispatch()


def create_desktop_server(*, port: int = 0, home: Path | None = None) -> WebServer:
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("port must be an integer between 0 and 65535")
    home = home or pf_home()
    server = WebServer(("127.0.0.1", port), DesktopHandler)
    server.writes_enabled = True
    server.desktop_token = secrets.token_hex(32)
    try:
        selected_root = auth_root()
        if selected_root.absolute() != (home / "codex-auth").absolute():
            raise ProviderBlocked("AUTH_STORAGE_INVALID", "데스크톱은 앱 전용 Codex 연결 경로만 사용할 수 있습니다.")
        # Desktop startup never spends a subscription budget by resuming work.
        state = DesktopState(home / "studies", home / "web", Path(__file__).parent / "web_static", resume_jobs=False)
        server.state = state
        manager = ConnectionManager(selected_root)
        state._connection = manager
        initialized = manager.initialize_app_login()
        if (initialized.get("code") in {"AUTH_STORAGE_INVALID", "UNSUPPORTED_PLATFORM", "CONNECTION_BUSY"}
                or not (initialized.get("app_login_required") or initialized.get("connected"))):
            raise ProviderBlocked("AUTH_STORAGE_INVALID", "앱 전용 Codex 연결을 안전하게 초기화하지 못했습니다.")
    except BaseException:
        server.server_close()
        raise
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    os.environ["PF_CODEX_AUTH_HOME"] = str(pf_home() / "codex-auth")
    # The packaged converter is a dependency, not an additional installation.
    if not os.environ.get("PYPANDOC_PANDOC"):
        try:
            import pypandoc
            pandoc = Path(pypandoc.get_pandoc_path())
            os.environ["PYPANDOC_PANDOC"] = str(pandoc if pandoc.is_file() else pandoc.with_suffix(".exe"))
        except (ImportError, OSError, RuntimeError):
            pass  # Readiness UI reports the missing converter.
    server = create_desktop_server(port=args.port)

    def parent_closed():
        # A crashed Electron process closes its pipe. Stop research as on exit.
        # Do not hold a buffered stdin lock in a daemon thread at interpreter exit.
        descriptor = sys.stdin.fileno()
        try:
            while os.read(descriptor, 4096):
                pass
        except OSError:
            pass  # A broken parent pipe also requires owned worker shutdown.
        while not server.state.request_shutdown()["ready"]:
            time.sleep(1)
        server.shutdown()

    threading.Thread(target=parent_closed, daemon=True).start()
    print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}", "token": server.desktop_token}), flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

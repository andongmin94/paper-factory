"""Connection HTTP boundaries use a synthetic authentication manager."""

import threading
import time

import httpx
import pytest

from paper_factory import project
from paper_factory.web import create_server


class FixtureConnection:
    def __init__(self):
        self.calls = []
        self.closed = False

    def status(self):
        return {"status": "disconnected", "authentication": "logged_out", "model_available": False}

    def login(self):
        self.calls.append("login")
        return {"status": "waiting_user", "authentication": "unknown", "model_available": False,
                "verification_url": "https://auth.openai.com/codex/device", "user_code": "TEST-CODE"}

    def probe(self):
        self.calls.append("probe")
        return {"status": "probing", "model_available": False}

    def cancel(self):
        self.calls.append("cancel")
        return {"status": "cancelled", "model_available": False}

    def logout(self):
        self.calls.append("logout")
        return self.status()

    def close(self):
        self.closed = True


@pytest.fixture
def connection_web(tmp_path, monkeypatch):
    auth_root = tmp_path / "private-worker"
    monkeypatch.setenv("PF_HOME", str(tmp_path / "application-home"))
    monkeypatch.setenv("PF_CODEX_AUTH_HOME", str(auth_root))
    server = create_server(port=0, studies_root=tmp_path / "studies", data_root=tmp_path / "web", source_roots=[tmp_path])
    manager = FixtureConnection()
    server.state._connection = manager
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    with httpx.Client(base_url=origin, headers={"Origin": origin}, timeout=10) as client:
        yield server, client, manager, auth_root
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
    assert manager.closed


def test_reading_connection_does_not_start_login_or_model_requests(connection_web):
    _, client, manager, _ = connection_web
    for _ in range(3):
        response = client.get("/api/agent/connection")
        assert response.status_code == 200 and response.json()["model_available"] is False
        assert response.headers["Cache-Control"] == "no-store"
    assert manager.calls == []


@pytest.mark.parametrize("action,status", [("login", 202), ("probe", 202), ("cancel", 200), ("logout", 200)])
def test_explicit_connection_actions_use_typed_endpoints(connection_web, action, status):
    _, client, manager, _ = connection_web
    response = client.post(f"/api/agent/connection/{action}", json={})
    assert response.status_code == status
    assert manager.calls == [action]


@pytest.mark.parametrize("action", ["login", "probe", "cancel", "logout"])
def test_authentication_actions_require_same_origin_and_empty_payload(connection_web, action):
    _, client, manager, _ = connection_web
    route = f"/api/agent/connection/{action}"
    assert client.post(route, json={}, headers={"Origin": "https://foreign.example"}).status_code == 403
    assert client.post(route, json={"auth_home": "/untrusted", "token": "synthetic-token"}).status_code == 400
    assert manager.calls == []


def test_read_only_preview_cannot_read_or_change_connection(connection_web):
    server, client, manager, _ = connection_web
    server.writes_enabled = False
    assert client.get("/api/agent/connection").status_code == 403
    assert client.post("/api/agent/connection/login", json={}).status_code == 403
    assert manager.calls == []


@pytest.mark.parametrize("code,http_status", [("CONNECTION_BUSY", 409), ("CODEX_NOT_FOUND", 400)])
def test_connection_preflight_failure_is_visible_without_starting_a_job(connection_web, monkeypatch, code, http_status):
    _, client, manager, _ = connection_web
    monkeypatch.setattr(manager, "login", lambda: {"status": "blocked", "code": code, "message": "Synthetic connection prerequisite failure"})
    response = client.post("/api/agent/connection/login", json={})
    assert response.status_code == http_status and response.json()["code"] == code


@pytest.mark.parametrize("action", ["login", "probe", "logout"])
def test_account_changes_are_blocked_while_research_is_queued_or_running(connection_web, action):
    server, client, manager, _ = connection_web
    server.state.jobs["job-fixture"] = {"status": "running", "project_id": "fixture"}
    response = client.post(f"/api/agent/connection/{action}", json={})
    assert response.status_code == 409 and response.json()["code"] == "RESEARCH_BUSY"
    assert manager.calls == []
    assert client.post("/api/agent/connection/cancel", json={}).status_code == 200
    assert manager.calls == ["cancel"]
    server.state.jobs.clear()


def test_saved_unconfirmed_research_handle_blocks_account_logout(connection_web, tmp_path):
    from paper_factory.autonomous.models import PipelineRun
    from paper_factory.workspace import Workspace
    server, client, manager, _ = connection_web
    source = tmp_path / "source"; source.mkdir(); (source / "module.py").write_text("pass\n")
    destination = server.state.data_root / "projects" / "fixture"
    project.ingest(str(source), destination)
    server.state.projects["fixture"] = {"id": "fixture", "status": "ready"}
    ws = Workspace(destination)
    run = PipelineRun(project_id="fixture", goal="A synthetic research goal", status="blocked", code="CLEANUP_UNCONFIRMED")
    ws.save("pipeline", run)
    response = client.post("/api/agent/connection/logout", json={})
    assert response.status_code == 409 and response.json()["code"] == "RESEARCH_BUSY"
    assert manager.calls == []


@pytest.mark.parametrize("status", ["starting", "waiting_user", "probing", "logging_out"])
def test_research_submission_cannot_race_account_connection(connection_web, monkeypatch, status):
    server, _, manager, _ = connection_web
    monkeypatch.setattr(manager, "status", lambda: {"status": status})
    with pytest.raises(ValueError, match="계정 연결 작업"):
        server.state.submit("fixture", "research", ["research"])
    with pytest.raises(ValueError, match="계정 연결 작업"):
        server.state.start_pipeline("fixture", {"goal": "A synthetic research goal"})
    with pytest.raises(ValueError, match="계정 연결 작업"):
        server.state.control_pipeline("fixture", "pipeline-fixture", "resume", {})
    assert server.state.jobs == {}


def test_logged_out_app_cannot_create_or_resume_research(connection_web, monkeypatch):
    server, _, manager, _ = connection_web
    monkeypatch.setattr(manager, "status", lambda: {"status": "logged_out", "app_login_required": True})
    with pytest.raises(ValueError, match="연결 확인"):
        server.state.start_pipeline("fixture", {"goal": "A synthetic research goal"})
    with pytest.raises(ValueError, match="연결 확인"):
        server.state.control_pipeline("fixture", "pipeline-fixture", "resume", {})
    assert server.state.jobs == {}


def test_unconfirmed_connection_worker_blocks_new_research(connection_web, monkeypatch):
    server, _, manager, _ = connection_web
    monkeypatch.setattr(manager, "status", lambda: {"status": "blocked", "connected": True, "code": "CLEANUP_UNCONFIRMED"})
    with pytest.raises(ValueError, match="작업자의 종료"):
        server.state.start_pipeline("fixture", {"goal": "A synthetic research goal"})
    with pytest.raises(ValueError, match="작업자의 종료"):
        server.state.submit("fixture", "research", ["research"])
    assert server.state.jobs == {}


def test_local_project_import_cannot_include_private_worker_credentials(connection_web):
    server, _, _, auth_root = connection_web
    auth_root.mkdir()
    (auth_root / "auth.json").write_text('{"token":"synthetic-token"}')
    with pytest.raises(ValueError, match="private ChatGPT"):
        server.state.source(str(auth_root))


def test_child_jobs_keep_connection_store_when_their_application_home_changes(connection_web, tmp_path, monkeypatch):
    server, _, _, auth_root = connection_web
    source = tmp_path / "source"
    source.mkdir()
    (source / "subject.py").write_text("print('synthetic test')\n")
    destination = server.state.data_root / "projects" / "test-project"
    project.ingest(str(source), destination)
    server.state.projects["test-project"] = {"id": "test-project", "name": "Fixture", "status": "ready"}
    observed = {}

    def execute(command, environment, timeout, job):
        observed.update(environment)
        return 0, '{"fixture":true}'

    monkeypatch.setattr(server.state, "_execute", execute)
    job = server.state.submit("test-project", "research", ["research"], timeout=10)
    deadline = time.monotonic() + 5
    while server.state.job(job["id"])["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.state.job(job["id"])["status"] == "succeeded"
    assert observed["PF_HOME"] == str(server.state.data_root / ".home")
    assert observed["PF_CODEX_AUTH_HOME"] == str(auth_root)

"""The desktop session protects reads, writes and shutdown, including on restart."""
import threading

import httpx
import pytest

from paper_factory.desktop import create_desktop_server


@pytest.fixture
def desktop(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("PF_HOME", str(home))
    monkeypatch.setenv("PF_CODEX_AUTH_HOME", str(home / "codex-auth"))
    server = create_desktop_server(home=home)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    with httpx.Client(base_url=url, headers={"Origin": url}, timeout=5) as client:
        yield server, client, thread
    if thread.is_alive():
        server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_desktop_requires_session_even_for_readable_artifacts(desktop):
    server, client, _ = desktop
    assert client.get("/api/health").status_code == 403
    assert client.get("/api/projects").status_code == 403
    assert client.get("/").status_code == 403
    assert client.post("/api/desktop/shutdown", json={}).status_code == 403
    client.headers["Authorization"] = "Bearer " + server.desktop_token
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/projects").json() == {"projects": []}
    assert server.state.resume_jobs is False


def test_desktop_bootstrap_does_not_use_inherited_account(desktop):
    from paper_factory.autonomous.provider import ProviderBlocked, resolve_auth_home
    server, _, _ = desktop
    with pytest.raises(ProviderBlocked) as caught:
        resolve_auth_home(server.state._connection.root)
    assert caught.value.code == "AUTH_REQUIRED"


def test_desktop_shutdown_blocks_when_import_worker_is_active(desktop):
    server, client, _ = desktop
    client.headers["Authorization"] = "Bearer " + server.desktop_token
    server.state.jobs["fake"] = {"status": "running", "action": "start"}
    reply = client.post("/api/desktop/shutdown", json={})
    assert reply.status_code == 409
    assert reply.json()["ready"] is False
    assert server.state.closed is False
    server.state.jobs.clear()


def test_desktop_shutdown_requires_origin_and_exits_cleanly(desktop):
    server, client, thread = desktop
    client.headers["Authorization"] = "Bearer " + server.desktop_token
    origin = client.headers.pop("Origin")
    assert client.post("/api/desktop/shutdown", json={}).status_code == 403
    client.headers["Origin"] = origin
    assert client.post("/api/desktop/shutdown", json={"force": True}).status_code == 400
    assert client.post("/api/desktop/shutdown", json={}).json() == {"ready": True}
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_desktop_reconciles_queued_research_without_starting_it(tmp_path, monkeypatch):
    from paper_factory.autonomous.models import PipelineRun
    from paper_factory.autonomous import pipeline
    from paper_factory.workspace import Workspace, write_json
    home = tmp_path / "home"
    monkeypatch.setenv("PF_HOME", str(home))
    monkeypatch.setenv("PF_CODEX_AUTH_HOME", str(home / "codex-auth"))
    ws = Workspace.create(home / "web" / "projects" / "project-fixture")
    saved = PipelineRun(project_id="source-fixture", goal="Synthetic recovery fixture")
    ws.save("pipeline", saved)
    write_json(home / "web" / "projects.json", {"project-fixture": {"id": "project-fixture", "name": "Fixture", "status": "ready"}})
    monkeypatch.setattr(pipeline, "run", lambda *_: pytest.fail("Reopening the app must not start model work"))
    server = create_desktop_server(home=home)
    try:
        recovered = ws.get("pipeline", saved.id, PipelineRun)
        assert recovered.status == "paused" and recovered.code == "INTERRUPTED"
        assert server.state.jobs == {}
    finally:
        server.server_close()


def test_desktop_shutdown_does_not_claim_unfinished_auth_cleanup(desktop, monkeypatch):
    server, client, _ = desktop
    client.headers["Authorization"] = "Bearer " + server.desktop_token
    monkeypatch.setattr(server.state._connection, "cancel", lambda: {"status": "probing", "code": "CANCEL_REQUESTED"})
    reply = client.post("/api/desktop/shutdown", json={})
    assert reply.status_code == 409
    assert reply.json()["code"] == "CLEANUP_UNCONFIRMED"
    assert server.state.closed is False


def test_desktop_shutdown_retains_uncertain_research_handle(desktop):
    from paper_factory.autonomous.models import PipelineRun
    from paper_factory.workspace import Workspace
    server, client, _ = desktop
    ws = Workspace.create(server.state.data_root / "projects" / "project-fixture")
    saved = PipelineRun(project_id="source-fixture", goal="Synthetic cleanup fixture", status="blocked", code="CLEANUP_UNCONFIRMED",
                        active_handle={"kind": "unknown", "pid": 123})
    ws.save("pipeline", saved)
    server.state.projects["project-fixture"] = {"id": "project-fixture", "status": "ready"}
    client.headers["Authorization"] = "Bearer " + server.desktop_token
    reply = client.post("/api/desktop/shutdown", json={})
    assert reply.status_code == 409
    assert reply.json()["code"] == "CLEANUP_UNCONFIRMED"
    assert ws.get("pipeline", saved.id, PipelineRun).active_handle == saved.active_handle
    assert server.state.closed is False


@pytest.mark.parametrize("claimed_selection", [False, True])
def test_desktop_refuses_failed_explicit_login_initialization(tmp_path, monkeypatch, claimed_selection):
    from paper_factory.autonomous.connection import ConnectionManager
    from paper_factory.autonomous.provider import ProviderBlocked
    home = tmp_path / "home"
    monkeypatch.setenv("PF_HOME", str(home))
    monkeypatch.setenv("PF_CODEX_AUTH_HOME", str(home / "codex-auth"))
    monkeypatch.setattr(ConnectionManager, "initialize_app_login", lambda _: {"status": "blocked", "code": "AUTH_STORAGE_INVALID", "app_login_required": claimed_selection})
    with pytest.raises(ProviderBlocked) as caught:
        create_desktop_server(home=home)
    assert caught.value.code == "AUTH_STORAGE_INVALID"


def test_desktop_refuses_auth_root_outside_its_workspace(tmp_path, monkeypatch):
    from paper_factory.autonomous.provider import ProviderBlocked
    home = tmp_path / "home"
    foreign = tmp_path / "other-account"
    monkeypatch.setenv("PF_HOME", str(home))
    monkeypatch.setenv("PF_CODEX_AUTH_HOME", str(foreign))
    with pytest.raises(ProviderBlocked) as caught:
        create_desktop_server(home=home)
    assert caught.value.code == "AUTH_STORAGE_INVALID"
    assert not foreign.exists()


def test_desktop_serializes_concurrent_shutdown_without_reopening_state(desktop, monkeypatch):
    server, _, _ = desktop
    entered, release = threading.Event(), threading.Event()
    outcomes = []
    def slow_cancel():
        entered.set()
        assert release.wait(timeout=3)
        return {"status": "logged_out"}
    monkeypatch.setattr(server.state._connection, "cancel", slow_cancel)
    worker = threading.Thread(target=lambda: outcomes.append(server.state.request_shutdown()))
    worker.start()
    try:
        assert entered.wait(timeout=3)
        refused = server.state.request_shutdown()
        assert refused["ready"] is False and refused["code"] == "SHUTDOWN_BUSY"
        assert server.state.closed is True
    finally:
        release.set()
        worker.join(timeout=3)
    assert outcomes == [{"ready": True}] and not worker.is_alive()
    assert server.state.closed is True


def test_desktop_shutdown_tolerates_research_finishing_before_cancellation(desktop, monkeypatch):
    from paper_factory.autonomous import pipeline
    from paper_factory.autonomous.models import PipelineRun
    from paper_factory.workspace import Workspace
    server, _, _ = desktop
    ws = Workspace.create(server.state.data_root / "projects" / "project-fixture")
    saved = PipelineRun(project_id="source-fixture", goal="Synthetic finish race", status="running")
    ws.save("pipeline", saved)
    server.state.projects["project-fixture"] = {"id": "project-fixture", "status": "ready"}
    server.state.jobs["job-fixture"] = {"status": "running", "project_id": "project-fixture", "pipeline_id": saved.id}
    def completed_before_cancel(workspace, pipeline_id):
        saved.status = "completed"
        ws.save("pipeline", saved)
        server.state.jobs["job-fixture"]["status"] = "succeeded"
        raise ValueError("Completed research cannot be cancelled")
    monkeypatch.setattr(pipeline, "cancel", completed_before_cancel)
    assert server.state.request_shutdown() == {"ready": True}
    assert ws.get("pipeline", saved.id, PipelineRun).status == "completed"


def test_desktop_shutdown_retains_app_when_worker_state_cannot_be_read(desktop, monkeypatch):
    from paper_factory.autonomous import pipeline
    from paper_factory.workspace import Workspace
    server, _, _ = desktop
    Workspace.create(server.state.data_root / "projects" / "project-fixture")
    server.state.projects["project-fixture"] = {"id": "project-fixture", "status": "ready"}
    def unavailable(workspace):
        raise OSError("synthetic unreadable checkpoint")
    monkeypatch.setattr(pipeline, "list_runs", unavailable)
    result = server.state.request_shutdown()
    assert result["ready"] is False and result["code"] == "CLEANUP_UNCONFIRMED"
    assert server.state.closed is False

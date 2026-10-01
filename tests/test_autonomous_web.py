"""HTTP orchestration, durable import intent and private-file boundaries.

The model/experiment worker is replaced in these endpoint tests; scientific and
isolated execution behavior are exercised by their own integration tests.
"""

import json
import sys
import threading
import time
from types import ModuleType, SimpleNamespace

import httpx
import pytest

from paper_factory import autonomous
from paper_factory.project import ingest
from paper_factory.web import WebState, create_server
from paper_factory.workspace import write_json


@pytest.fixture
def autonomous_web(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "subject.py").write_text("def calculate(x): return x * 2\n", encoding="utf-8")
    source_root = tmp_path / "data" / "projects" / "web-test"
    ingest(str(source), source_root)
    write_json(tmp_path / "data" / "projects.json", {
        "web-test": {"id": "web-test", "name": "Test", "source": str(source),
                     "status": "ready", "created_at": "2026-01-01T00:00:00Z"}})
    fake = ModuleType("paper_factory.autonomous.pipeline")
    stored = {}
    proceed = threading.Event()

    def create(ws, goal, *, model=None, budget=None):
        if budget and any(key not in {"max_model_calls", "wall_seconds", "repair_attempts", "model_timeout_seconds", "experiment_timeout_seconds"} for key in budget):
            raise ValueError("Unsupported budget")
        item = {"id": f"pipeline-{len(stored) + 1}", "goal": goal, "status": "queued", "stage": "assess",
                "created_at": "2026-02-01T00:00:00Z", "budget": budget or {}, "model_calls": 0,
                "active_handle": {"private": "do-not-expose"}, "provider_output": "private-provider-text"}
        stored[item["id"]] = item
        return SimpleNamespace(**item)

    def run(ws, pipeline_id):
        item = stored[pipeline_id]
        item.update(status="running", stage="execute")
        proceed.wait(timeout=10)
        if item["status"] != "cancelled":
            item.update(status="completed", stage="done")
            output = ws.path(f"autonomous/{pipeline_id}/exports/paper.md")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("# Endpoint fixture\n", encoding="utf-8")
            private = ws.path(f"autonomous/{pipeline_id}/context.json")
            private.write_text('{"private":"private-context"}', encoding="utf-8")
        return SimpleNamespace(**item)

    def cancel(ws, pipeline_id):
        stored[pipeline_id].update(status="cancelled", cancellation_requested=True)
        proceed.set()
        return dict(stored[pipeline_id])

    def resume(ws, pipeline_id):
        stored[pipeline_id].update(status="queued", cancellation_requested=False)
        return SimpleNamespace(**stored[pipeline_id])

    def recover(ws, pipeline_id):
        item = stored[pipeline_id]
        if item["status"] in {"queued", "running"}:
            item.update(status="paused", code="INTERRUPTED", cancellation_requested=False)
        return SimpleNamespace(**{"code": None, "cancellation_requested": False, **item})

    fake.create, fake.run, fake.cancel, fake.resume = create, run, cancel, resume
    fake.recover = recover
    fake.status = lambda ws, pipeline_id: dict(stored[pipeline_id])
    fake.list_runs = lambda ws: [dict(item) for item in stored.values()]
    monkeypatch.setitem(sys.modules, "paper_factory.autonomous.pipeline", fake)
    monkeypatch.setattr(autonomous, "pipeline", fake, raising=False)
    server = create_server(port=0, studies_root=tmp_path / "studies", data_root=tmp_path / "data", source_roots=[tmp_path])
    monkeypatch.setattr(server.state, "agent_status", lambda: {
        "provider": {"ready": True, "authentication": "chatgpt"},
        "runner": {"ready": True, "reason": None}})
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{server.server_port}"
    with httpx.Client(base_url=address, timeout=20, headers={"Origin": address}) as client:
        yield server, client, source, stored, proceed
    proceed.set()
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def wait_job(client, job_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        item = client.get(f"/api/jobs/{job_id}").json()
        if item["status"] not in {"queued", "running"}:
            return item
        time.sleep(0.02)
    pytest.fail("The endpoint worker did not complete")


def test_pipeline_start_cancel_resume_export_and_private_boundary(autonomous_web):
    server, client, _, stored, proceed = autonomous_web
    assert client.get("/api/agent/status").json()["provider"]["ready"] is True
    response = client.post("/api/projects/web-test/pipelines", json={"goal": "Evaluate the actual source behavior", "budget": {"max_model_calls": 8}})
    assert response.status_code == 202, response.text
    result = response.json()
    pipeline_id = result["pipeline"]["id"]
    assert "active_handle" not in result["pipeline"]
    assert "provider_output" not in result["pipeline"]
    assert client.post("/api/projects/web-test/pipelines", json={"goal": "Another actual experiment"}).status_code == 400
    assert client.post(f"/api/projects/web-test/pipelines/{pipeline_id}/resume", json={}).status_code == 400
    assert client.post(f"/api/projects/web-test/pipelines/{pipeline_id}/cancel", json={}).status_code == 200
    assert wait_job(client, result["job"]["id"])["status"] == "cancelled"
    assert client.get(f"/api/projects/web-test/pipelines/{pipeline_id}").json()["status"] == "cancelled"
    resumed = client.post(f"/api/projects/web-test/pipelines/{pipeline_id}/resume", json={})
    assert resumed.status_code == 202, resumed.text
    assert wait_job(client, resumed.json()["job"]["id"])["status"] == "succeeded"
    detail = client.get("/api/projects/web-test").json()
    assert detail["pipelines"][0]["status"] == "completed"
    entry = next(file for file in detail["files"] if file["path"].endswith("exports/paper.md"))
    assert client.get(entry["url"]).text == "# Endpoint fixture\n"
    assert client.get(f"/api/projects/web-test/files/autonomous/{pipeline_id}/context.json").status_code == 404
    assert "private-provider-text" not in json.dumps(detail)
    assert "do-not-expose" not in json.dumps(detail)


@pytest.mark.parametrize("payload", [
    {"goal": "Valid research goal", "command": "shell"},
    {"goal": "Valid research goal", "budget": []},
    {"goal": "Valid research goal", "budget": {"command": "shell"}},
    {"goal": ""},
    {"goal": "Valid research goal", "model": ""},
])
def test_pipeline_input_is_typed_and_bounded(autonomous_web, payload):
    server, client, _, stored, _ = autonomous_web
    assert client.post("/api/projects/web-test/pipelines", json=payload).status_code == 400
    assert stored == {}


def test_pipeline_writes_require_same_origin_and_agent_is_local_only(autonomous_web):
    server, client, _, stored, _ = autonomous_web
    response = client.post("/api/projects/web-test/pipelines", json={"goal": "Run a bounded research study"}, headers={"Origin": "https://foreign.example"})
    assert response.status_code == 403
    assert not stored
    server.writes_enabled = False
    assert client.get("/api/agent/status").status_code == 403
    assert client.get("/api/projects/web-test/pipelines").status_code == 403


def test_import_with_autonomous_intent_starts_after_browser_request(autonomous_web):
    server, client, source, stored, proceed = autonomous_web
    proceed.set()
    response = client.post("/api/projects", json={"source": str(source), "autonomous": {"goal": "Compare actual source behavior with an independent oracle"}})
    assert response.status_code == 202, response.text
    imported = response.json()
    assert wait_job(client, imported["job"]["id"])["status"] == "succeeded"
    deadline = time.monotonic() + 10
    while not stored and time.monotonic() < deadline:
        time.sleep(0.02)
    assert len(stored) == 1
    with server.state.lock:
        assert "pending_autonomous" not in server.state.projects[imported["project"]["id"]]
        jobs = [job for job in server.state.jobs.values() if job["action"] == "autonomous-start"]
    assert len(jobs) == 1
    assert wait_job(client, jobs[0]["id"])["status"] == "succeeded"


def test_repository_selection_input_and_origin(autonomous_web, monkeypatch):
    _, client, _, _, _ = autonomous_web
    module = ModuleType("paper_factory.autonomous.repositories")
    seen = []
    def select(owner, count=3):
        seen.append((owner, count))
        return {"owner": owner, "repositories": [{"name": "owner/project", "url": "https://github.com/owner/project", "reason": "Runnable supported repository", "score": 10}], "considered": 1, "limitations": []}
    module.select_repositories = select
    monkeypatch.setitem(sys.modules, "paper_factory.autonomous.repositories", module)
    response = client.post("/api/agent/repositories", json={"owner": "owner", "count": 3})
    assert response.status_code == 200
    assert seen == [("owner", 3)]
    for payload in ({"owner": "owner", "count": True}, {"owner": "owner", "count": 4}, {"owner": "owner", "api_key": "x"}):
        assert client.post("/api/agent/repositories", json=payload).status_code == 400
    assert client.post("/api/agent/repositories", json={"owner": "owner"}, headers={"Origin": "https://foreign.example"}).status_code == 403


def test_restart_consumes_pending_import_without_duplicate_research(autonomous_web):
    server, client, _, stored, proceed = autonomous_web
    proceed.set()
    goal = "Preserve one registered research series after a restart"
    created = client.post("/api/projects/web-test/pipelines", json={"goal": goal}).json()
    assert wait_job(client, created["job"]["id"])["status"] == "succeeded"
    with server.state.lock:
        server.state.projects["web-test"]["pending_autonomous"] = {"goal": goal}
        server.state._save_projects()
    restored = WebState(server.state.studies_root, server.state.data_root, server.state.static_root)
    try:
        assert len(stored) == 1
        assert "pending_autonomous" not in restored.projects["web-test"]
    finally:
        restored.close()


def test_exports_cannot_follow_links_into_private_files(autonomous_web, tmp_path):
    server, client, _, stored, proceed = autonomous_web
    proceed.set()
    created = client.post("/api/projects/web-test/pipelines", json={"goal": "Keep exported files inside the workspace"}).json()
    assert wait_job(client, created["job"]["id"])["status"] == "succeeded"
    pipeline_id = created["pipeline"]["id"]
    outside = tmp_path / "private.txt"
    outside.write_text("private-linked-content", encoding="utf-8")
    link = server.state.workspace_path("web-test") / f"autonomous/{pipeline_id}/exports/linked.txt"
    link.symlink_to(outside)
    response = client.get(f"/api/projects/web-test/pipelines/{pipeline_id}")
    assert response.status_code == 400
    assert "private-linked-content" not in response.text
    assert client.get(f"/api/projects/web-test/files/autonomous/{pipeline_id}/exports/linked.txt").status_code == 400


def test_cancelled_queued_worker_does_not_start_research(autonomous_web, monkeypatch):
    server, client, _, stored, _ = autonomous_web
    monkeypatch.setattr(server.state.pool, "submit", lambda *args, **kwargs: None)
    started = client.post("/api/projects/web-test/pipelines", json={"goal": "Cancel a queued experiment before it starts"}).json()
    pipeline_id = started["pipeline"]["id"]
    assert client.post(f"/api/projects/web-test/pipelines/{pipeline_id}/cancel", json={}).status_code == 200
    calls = []
    monkeypatch.setattr(autonomous.pipeline, "run", lambda *args, **kwargs: calls.append(True))
    server.state._run_pipeline_job(started["job"]["id"])
    assert calls == []
    assert client.get(f"/api/jobs/{started['job']['id']}").json()["status"] == "cancelled"
    assert stored[pipeline_id]["status"] == "cancelled"


def test_provider_block_is_visible_as_a_recoverable_condition(autonomous_web, monkeypatch):
    server, client, _, stored, _ = autonomous_web
    def blocked_run(ws, pipeline_id):
        stored[pipeline_id].update(status="blocked", code="NETWORK_BLOCKED", message="The authenticated CLI request was refused by the network.")
        return SimpleNamespace(**stored[pipeline_id])
    monkeypatch.setattr(autonomous.pipeline, "run", blocked_run)
    started = client.post("/api/projects/web-test/pipelines", json={"goal": "Keep evidence when a configured provider is unavailable"}).json()
    outcome = wait_job(client, started["job"]["id"])
    assert outcome["status"] == "blocked"
    assert outcome["result"]["code"] == "NETWORK_BLOCKED"
    assert outcome["result"]["status"] == "blocked"
    assert client.post(f"/api/projects/web-test/pipelines/{started['pipeline']['id']}/resume", json={}).status_code == 202


@pytest.mark.parametrize("saved_job", [True, False])
def test_restart_resumes_a_queued_worker_or_orphan_without_a_new_series(autonomous_web, monkeypatch, saved_job):
    from paper_factory.workspace import Workspace
    server, client, _, stored, proceed = autonomous_web
    monkeypatch.setattr(server.state.pool, "submit", lambda *args, **kwargs: None)
    if saved_job:
        started = client.post("/api/projects/web-test/pipelines", json={"goal": "Resume queued work after the server restarts"}).json()
        pipeline_id = started["pipeline"]["id"]
    else:
        created = autonomous.pipeline.create(Workspace(server.state.workspace_path("web-test")), "Resume an orphan checkpoint after the server restarts")
        pipeline_id = created.id
    proceed.set()
    restored = WebState(server.state.studies_root, server.state.data_root, server.state.static_root)
    try:
        deadline = time.monotonic() + 5
        while stored[pipeline_id]["status"] != "completed" and time.monotonic() < deadline:
            time.sleep(0.02)
        assert stored[pipeline_id]["status"] == "completed"
        assert len(stored) == 1
        assert sum(job["action"] == "autonomous-resume" for job in restored.jobs.values()) == 1
        if saved_job:
            assert restored.jobs[started["job"]["id"]]["status"] == "interrupted"
    finally:
        restored.close()


def test_restart_does_not_retry_a_provider_block(autonomous_web):
    from paper_factory.workspace import Workspace
    server, _, _, stored, _ = autonomous_web
    created = autonomous.pipeline.create(Workspace(server.state.workspace_path("web-test")), "Keep a provider quota stop explicit after a restart")
    stored[created.id].update(status="blocked", code="USAGE_LIMIT", message="Account usage is limited.")
    restored = WebState(server.state.studies_root, server.state.data_root, server.state.static_root)
    try:
        assert stored[created.id]["status"] == "blocked"
        assert restored.jobs == {}
    finally:
        restored.close()


def test_restart_drains_multiple_orphans_serially_for_one_project(autonomous_web, monkeypatch):
    from paper_factory.workspace import Workspace
    server, _, _, stored, proceed = autonomous_web
    ws = Workspace(server.state.workspace_path("web-test"))
    autonomous.pipeline.create(ws, "Recover the first orphan research checkpoint")
    autonomous.pipeline.create(ws, "Recover the second orphan research checkpoint")
    original = autonomous.pipeline.run
    active = 0
    maximum = 0
    def measured_run(*args, **kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        try:
            time.sleep(0.03)
            return original(*args, **kwargs)
        finally:
            active -= 1
    monkeypatch.setattr(autonomous.pipeline, "run", measured_run)
    proceed.set()
    restored = WebState(server.state.studies_root, server.state.data_root, server.state.static_root)
    try:
        deadline = time.monotonic() + 5
        while any(item["status"] != "completed" for item in stored.values()) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert all(item["status"] == "completed" for item in stored.values())
        assert len(stored) == 2
        assert maximum == 1
        assert sum(job["action"] == "autonomous-resume" for job in restored.jobs.values()) == 2
        assert "autonomous_error" not in restored.projects["web-test"]
    finally:
        restored.close()


def test_artifact_only_preview_does_not_resume_private_research(autonomous_web):
    from paper_factory.workspace import Workspace
    server, _, _, stored, _ = autonomous_web
    created = autonomous.pipeline.create(Workspace(server.state.workspace_path("web-test")), "Preserve queued research when serving a public artifact preview")
    preview = create_server(host="0.0.0.0", port=0, studies_root=server.state.studies_root,
                            data_root=server.state.data_root, static_root=server.state.static_root)
    try:
        assert preview.writes_enabled is False
        assert preview.state.resume_jobs is False
        assert stored[created.id]["status"] == "queued"
        assert preview.state.jobs == {}
    finally:
        preview.server_close()

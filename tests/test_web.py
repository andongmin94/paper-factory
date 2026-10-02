"""Exercise the local HTTP boundary and a real research CLI workflow."""

import json
import socket
import threading
import time
import zipfile
from io import BytesIO
from pathlib import Path

import httpx
import pytest

from paper_factory.web import MAX_BODY, WebHandler, WebState, create_server
from paper_factory.workspace import write_json


@pytest.fixture
def web_case(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_HOME", str(tmp_path / "global-home"))
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.csv").write_text("x\n1\n2\n", encoding="utf-8")
    (source / "analysis.py").write_text("import json\nfrom pathlib import Path\nPath('result.json').write_text(json.dumps({'count': 2}))\n", encoding="utf-8")
    (source / ".env").write_text("SECRET_TOKEN=never-import-this\n", encoding="utf-8")
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>Paper Factory</title>", encoding="utf-8")
    studies = tmp_path / "studies"
    study = studies / "sample-study"
    study.mkdir(parents=True)
    (study / "manuscript.md").write_text("# Evidence-backed article\n", encoding="utf-8", newline="\n")
    (study / "results.csv").write_text("metric,value\ncount,2\n", encoding="utf-8", newline="\n")
    (study / "undeclared.txt").write_text("Not exposed", encoding="utf-8")
    write_json(study / "manifest.json", {"id": "sample-study", "title": "Sample study", "status": "complete", "repository": {"name": "owner/sample"}, "files": [{"path": "manuscript.md", "role": "manuscript"}, {"path": "results.csv", "role": "data"}]})
    server = create_server(port=0, studies_root=studies, data_root=tmp_path / "data", static_root=static, source_roots=[tmp_path])
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{server.server_port}"
    with httpx.Client(base_url=address, timeout=20, headers={"Origin": address}) as client:
        yield server, client, source, tmp_path
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def finished(client, job_id):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        reply = client.get(f"/api/jobs/{job_id}")
        assert reply.status_code == 200
        job = reply.json()
        if job["status"] not in {"queued", "running"}:
            return job
        time.sleep(0.02)
    pytest.fail("Job did not complete before the test deadline")


def import_project(client, source):
    response = client.post("/api/projects", json={"source": str(source)})
    assert response.status_code == 202, response.text
    value = response.json()
    job = finished(client, value["job"]["id"])
    assert job["status"] == "succeeded", job
    return value["project"]["id"]


def action_ok(client, project_id, action, **kwargs):
    response = client.post(f"/api/projects/{project_id}/actions", json={"action": action, **kwargs})
    assert response.status_code == 202, response.text
    job = finished(client, response.json()["job"]["id"])
    assert job["status"] == "succeeded", job
    return job["result"]


def test_python_web_api_defaults_to_application_home(tmp_path, monkeypatch):
    home = tmp_path / "application-home"
    monkeypatch.setenv("PF_HOME", str(home))
    server = create_server(port=0)
    try:
        assert server.state.studies_root == (home / "studies").resolve()
        assert server.state.data_root == (home / "web").resolve()
    finally:
        server.server_close()


def test_download_growth_cannot_exceed_declared_content_length(tmp_path):
    path = tmp_path / "growing.txt"
    original = b"Recorded observation\n"
    path.write_bytes(original)
    handler = object.__new__(WebHandler)
    handler.command = "GET"
    handler.wfile = BytesIO()
    declared = []
    def headers(status, mime, size, **kwargs):
        declared.append(size)
        with path.open("ab") as stream:
            stream.write(b"New observations added during download\n")
    handler._headers = headers
    handler._file(path)
    assert declared == [len(original)]
    assert handler.wfile.getvalue() == original


def test_catalog_static_download_and_bundle_are_useful(web_case):
    _, client, _, _ = web_case
    assert client.get("/").status_code == 200
    assert client.get("/api/health").json()["writes_enabled"] is True
    catalog = client.get("/api/studies").json()
    assert catalog["errors"] == []
    study = catalog["studies"][0]
    assert study["slug"] == "sample-study"
    assert study["files"][0]["role"] == "manuscript"
    artifact = client.get(study["files"][0]["url"])
    assert artifact.text == "# Evidence-backed article\n"
    assert artifact.headers["x-content-type-options"] == "nosniff"
    archive = client.get(study["bundle_url"])
    assert archive.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(archive.content)) as bundle:
        assert sorted(bundle.namelist()) == ["manifest.json", "manuscript.md", "results.csv"]
        assert bundle.read("results.csv") == b"metric,value\ncount,2\n"
    assert client.head(study["files"][0]["url"]).content == b""


@pytest.mark.parametrize("path", ["/api/studies/sample-study/files/undeclared.txt", "/api/studies/sample-study/files/%2e%2e/secret.txt", "/%2e%2e/secret.txt", "/api/studies/sample-study/files/%5csecret.txt", "/api/studies/unknown", "/api/no-such-resource"])
def test_paths_do_not_escape_declared_artifacts(web_case, path):
    _, client, _, _ = web_case
    assert client.get(path).status_code in {400, 404}


def test_symlink_artifact_rejected_without_exposing_target(web_case):
    server, client, _, temporary = web_case
    outside = temporary / "private.txt"
    outside.write_text("private-target-value", encoding="utf-8")
    symlink = server.state.studies_root / "sample-study" / "linked.txt"
    try:
        symlink.symlink_to(outside)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows symlink creation requires Developer Mode or elevated permission")
        raise
    write_json(symlink.parent / "manifest.json", {"title": "Unsafe", "files": [{"path": "linked.txt"}]})
    response = client.get("/api/studies/sample-study/files/linked.txt")
    assert response.status_code == 400
    assert "private-target-value" not in response.text
    assert client.get("/api/studies").json()["errors"]


@pytest.mark.parametrize("headers", [{"Origin": "https://evil.example"}, {"Origin": "null"}, {"Origin": ""}, {"Sec-Fetch-Site": "cross-site"}, {"Host": "evil.example"}])
def test_write_origin_and_host_boundary(web_case, headers):
    server, client, source, _ = web_case
    response = client.post("/api/projects", json={"source": str(source)}, headers=headers)
    assert response.status_code == 403
    assert server.state.projects == {}


def test_denied_small_json_body_returns_http_error_repeatedly_on_windows(web_case):
    server, client, source, _ = web_case
    for _ in range(20):
        response = client.post("/api/projects", json={"source": str(source)}, headers={"Origin": "https://foreign.example"})
        assert response.status_code == 403 and "Origin" in response.json()["error"]
    assert server.state.projects == {}


@pytest.mark.parametrize("length,extra", [("20", ""), (str(MAX_BODY + 1), ""), ("20", "Transfer-Encoding: chunked\r\n")])
def test_denied_missing_or_unsupported_body_has_bounded_response(web_case, length, extra):
    server, _, _, _ = web_case
    request = (f"POST /api/projects HTTP/1.0\r\nHost: 127.0.0.1:{server.server_port}\r\n"
               f"Origin: https://foreign.example\r\nContent-Type: application/json\r\nContent-Length: {length}\r\n{extra}\r\n")
    started = time.monotonic()
    with socket.create_connection(("127.0.0.1", server.server_port), timeout=2) as transport:
        transport.sendall(request.encode("ascii"))
        assert b"403" in transport.recv(4096).split(b"\r\n", 1)[0]
    assert time.monotonic() - started < 1.5


def test_permission_denial_after_body_read_does_not_read_again(web_case, monkeypatch):
    server, client, source, _ = web_case
    def denied(payload):
        raise PermissionError("Synthetic post-body denial")
    monkeypatch.setattr(server.state, "import_project", denied)
    started = time.monotonic()
    response = client.post("/api/projects", json={"source": str(source)})
    assert response.status_code == 403 and response.json()["error"] == "Synthetic post-body denial"
    assert time.monotonic() - started < 1.5


def test_dns_rebinding_read_and_json_size_boundary(web_case):
    server, client, source, _ = web_case
    assert client.get("/api/projects", headers={"Host": "evil.example"}).status_code == 403
    assert client.post("/api/projects", content='{"source":"x"}', headers={"Content-Type": "text/plain"}).status_code == 400
    assert client.post("/api/projects", content=b"x" * (MAX_BODY + 1), headers={"Content-Type": "application/json"}).status_code == 400
    assert client.post("/api/projects", content="[]", headers={"Content-Type": "application/json"}).status_code == 400
    assert client.post("/api/projects", content="{\"source\":NaN}", headers={"Content-Type": "application/json"}).status_code == 400
    assert server.state.projects == {}


def test_import_restrictions_and_no_arbitrary_action(web_case):
    server, client, source, temporary = web_case
    for candidate in ["/etc", str(temporary), "ssh://git@github.com/owner/repo", "https://token@github.com/owner/repo", "https://github.com/owner/repo?token=x", "https://localhost/repo"]:
        assert client.post("/api/projects", json={"source": candidate}).status_code == 400
    project_id = import_project(client, source)
    assert client.post(f"/api/projects/{project_id}/actions", json={"action": "shell", "command": "touch secret"}).status_code == 400
    assert client.post(f"/api/projects/{project_id}/actions", json={"action": "manuscript-approve"}).status_code == 400
    assert client.post(f"/api/projects/{project_id}/actions", json={"action": "research", "title": "Title", "question": "Question", "command": "x"}).status_code == 400
    assert client.get(f"/api/projects/{project_id}/files/records.sqlite3").status_code == 404
    assert not (server.state.workspace_path(project_id) / "source" / ".env").exists()


def test_default_import_root_accepts_local_projects_under_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    source = home / "Desktop" / "project"
    source.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    state = WebState(tmp_path / "studies", tmp_path / "web", tmp_path / "static", resume_jobs=False)
    try:
        assert state.source(str(source)) == str(source.resolve())
        outside = tmp_path / "outside"
        outside.mkdir()
        with pytest.raises(ValueError, match="configured import roots"):
            state.source(str(outside))
    finally:
        state.close()


def test_unavailable_project_artifact_does_not_block_other_downloads(web_case, monkeypatch):
    import paper_factory.web as web
    server, client, source, _ = web_case
    project_id = import_project(client, source)
    monkeypatch.setattr(web, "MAX_FILE", 64)
    root = server.state.workspace_path(project_id)
    oversized = root / "reports" / "large.csv"
    oversized.write_bytes(b"x" * 65)
    available = root / "reports" / "small.txt"
    available.write_text("available", encoding="utf-8")
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200, response.text
    detail = response.json()
    assert any(item["path"] == "reports/large.csv" for item in detail["file_errors"])
    assert all(item["path"] != "reports/large.csv" for item in detail["files"])
    assert client.get(f"/api/projects/{project_id}/files/reports/small.txt").text == "available"
    assert client.get(f"/api/projects/{project_id}/files/reports/large.csv").status_code == 404


def test_zip_downloads_use_bundle_limit(web_case, monkeypatch):
    import paper_factory.web as web
    server, client, source, _ = web_case
    project_id = import_project(client, source)
    monkeypatch.setattr(web, "MAX_FILE", 64)
    monkeypatch.setattr(web, "MAX_BUNDLE", 96)
    root = server.state.workspace_path(project_id)
    accepted = root / "reports" / "reproducibility.zip"
    accepted.write_bytes(b"z" * 96)
    oversized = root / "reports" / "oversized.zip"
    oversized.write_bytes(b"z" * 97)
    detail = client.get(f"/api/projects/{project_id}").json()
    assert any(item["path"] == "reports/reproducibility.zip" for item in detail["files"])
    assert any(item["path"] == "reports/oversized.zip" for item in detail["file_errors"])
    response = client.get(f"/api/projects/{project_id}/files/reports/reproducibility.zip")
    assert response.status_code == 200
    assert response.content == accepted.read_bytes()
    assert client.head(f"/api/projects/{project_id}/files/reports/reproducibility.zip").headers["Content-Length"] == "96"
    assert client.get(f"/api/projects/{project_id}/files/reports/oversized.zip").status_code == 404


def test_oversized_processed_run_does_not_hide_project_records(web_case, monkeypatch):
    import paper_factory.web as web
    server, client, source, _ = web_case
    project_id = import_project(client, source)
    action_ok(client, project_id, "research", candidate="asset-inventory")
    run = action_ok(client, project_id, "run")
    relative = f"runs/{run['id']}/processed.json"
    (server.state.workspace_path(project_id) / relative).write_bytes(b"x" * 65)
    monkeypatch.setattr(web, "MAX_FILE", 64)
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["records"]["run"][0]["id"] == run["id"]
    assert any(item["path"] == relative for item in detail["file_errors"])


def test_real_pipeline_can_create_run_build_edit_render_and_check(web_case):
    server, client, source, _ = web_case
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    project_id = import_project(client, source)
    selected = action_ok(client, project_id, "research", candidate="asset-inventory")
    assert selected["study"]
    run = action_ok(client, project_id, "run")
    assert run["status"] == "SUCCEEDED"
    assert run["metrics"]["file_count"] == 2
    built = action_ok(client, project_id, "manuscript-build", pdf=False)
    report = action_ok(client, project_id, "integrity-check")
    assert report["passed"] is True
    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["status"] == "ready"
    assert "environment" not in detail["records"]["run"][0]
    assert any(file["path"].endswith("manuscript.md") for file in detail["files"])
    paper_id = built["paper"]
    canonical_url = f"/api/projects/{project_id}/files/manuscripts/{paper_id}/canonical.json"
    canonical = client.get(canonical_url).json()
    canonical["title"] = "An evidence linked asset inventory"
    response = client.put(f"/api/projects/{project_id}/manuscripts/{paper_id}/canonical", json={"canonical": canonical})
    assert response.status_code == 200, response.text
    rendered = action_ok(client, project_id, "manuscript-render", paper=paper_id, pdf=False)
    assert rendered["paper"] == paper_id
    assert action_ok(client, project_id, "integrity-check", paper=paper_id)["passed"] is True
    assert {p.name: p.read_bytes() for p in source.iterdir()} == before
    assert not (source / "records.sqlite3").exists()


def test_substantive_script_manifest_register_and_run(web_case):
    _, client, source, _ = web_case
    project_id = import_project(client, source)
    selected = action_ok(client, project_id, "research", title="Count data", question="How many entries are in the fixture?")
    project = client.get(f"/api/projects/{project_id}").json()["records"]["project"][0]
    manifest = {"id": "fixture-count", "study_id": selected["study"], "source_digest": project["snapshot_digest"], "source_commit": project["source_commit"], "command": ["{python}", "analysis.py"], "inputs": ["data.csv"], "expected_outputs": ["result.json"], "metrics": [{"name": "count", "output": "result.json", "pointer": "/count", "description": "Entry count"}]}
    registered = action_ok(client, project_id, "register", manifest=manifest)
    assert registered["experiment"] == "fixture-count"
    run = action_ok(client, project_id, "run", experiment="fixture-count")
    assert run["metrics"] == {"count": 2.0}
    detail = client.get(f"/api/projects/{project_id}").json()
    data_file = next(file for file in detail["files"] if file["path"].endswith("raw/result.json"))
    assert client.get(data_file["url"]).json() == {"count": 2}
    manifest["id"] = "evil"
    manifest["command"] = ["{python}", "-c", "print('untrusted inline')"]
    assert client.post(f"/api/projects/{project_id}/actions", json={"action": "register", "manifest": manifest}).status_code == 400
    manifest["command"] = ["bash", "analysis.py"]
    assert client.post(f"/api/projects/{project_id}/actions", json={"action": "register", "manifest": manifest}).status_code == 400


def test_failed_job_and_cli_argument_allowlist(web_case, monkeypatch):
    server, client, source, _ = web_case
    project_id = import_project(client, source)
    seen = []
    def fake_execute(command, environment, timeout, job):
        seen.append(command)
        return 1, "Error: controlled provider failure\n"
    monkeypatch.setattr(server.state, "_execute", fake_execute)
    response = client.post(f"/api/projects/{project_id}/actions", json={"action": "literature-search", "query": "--help", "limit": 3})
    assert response.status_code == 202
    job = finished(client, response.json()["job"]["id"])
    assert job["status"] == "failed"
    assert job["exit_code"] == 1
    assert seen[0][-2:] == ["--", "--help"]
    persisted = json.loads((server.state.data_root / "jobs" / f"{job['id']}.json").read_text())
    assert persisted["status"] == "failed"


def test_restart_marks_abandoned_jobs_and_imports_interrupted(tmp_path):
    data = tmp_path / "data"
    (data / "jobs").mkdir(parents=True)
    write_json(data / "projects.json", {"web-example": {"id": "web-example", "name": "Example", "status": "importing"}})
    write_json(data / "jobs" / "job-example.json", {"id": "job-example", "project_id": "web-example", "action": "start", "status": "running", "created_at": "2026-01-01", "log": "partial output"})
    state = WebState(tmp_path / "studies", data, tmp_path / "static", [tmp_path])
    try:
        job = state.job("job-example")
        assert job["status"] == "interrupted"
        assert job["log"] == "partial output"
        assert state.projects["web-example"]["status"] == "failed"
        assert json.loads((data / "jobs" / "job-example.json").read_text())["status"] == "interrupted"
    finally:
        state.close()


def test_nonloopback_preview_disables_workspace_access(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("Preview")
    server = create_server(host="0.0.0.0", port=0, studies_root=tmp_path / "studies", data_root=tmp_path / "data", static_root=static)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}") as client:
            assert client.get("/").status_code == 200
            assert client.get("/api/health").json()["writes_enabled"] is False
            assert client.get("/api/projects").status_code == 403
            assert client.get("/api/jobs").status_code == 403
            assert client.post("/api/projects", json={"source": "/workspace/example"}).status_code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_subprocess_log_redacts_injected_credentials(web_case, monkeypatch):
    server, _, _, _ = web_case
    monkeypatch.setenv("TEST_PRIVATE_TOKEN", "sensitive-token-value")
    from paper_factory.web import _redactor
    server.state.redact = _redactor()
    job = {"id": "job-redact", "project_id": "unused", "action": "fixture", "status": "running"}
    import os
    import sys
    code, output = server.state._execute([sys.executable, "-c", "print('sensitive-token-value https://user:password@github.com/x/y')"], dict(os.environ), 10, job)
    assert code == 0
    assert "sensitive-token-value" not in output
    assert "user:password" not in output
    assert "[redacted]" in output
    persisted = (server.state.data_root / "jobs" / "job-redact.json").read_text()
    assert "sensitive-token-value" not in persisted


def test_existing_reproducibility_zip_is_served_with_harness(web_case):
    server, client, _, _ = web_case
    study_root = server.state.studies_root / "sample-study"
    archive = study_root / "reproducibility.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("reproduce.py", "print('reproduce measurements')\n")
        bundle.writestr("seed.json", '{"seed":42}\n')
        bundle.writestr("manuscript.md", "# Measured study\n")
    write_json(study_root / "manifest.json", {"title": "Sample", "files": [{"path": "manuscript.md"}], "reproducibility_bundle": "reproducibility.zip"})
    study = client.get("/api/studies/sample-study").json()
    bundle_entry = next(file for file in study["files"] if file["path"] == "reproducibility.zip")
    assert bundle_entry["role"] == "reproducibility"
    response = client.get(study["bundle_url"])
    assert response.content == archive.read_bytes()
    assert response.headers["content-disposition"] == 'attachment; filename="reproducibility.zip"'
    assert client.get(bundle_entry["url"]).content == archive.read_bytes()
    with zipfile.ZipFile(BytesIO(response.content)) as downloaded:
        assert "reproduce.py" in downloaded.namelist()
        assert json.loads(downloaded.read("seed.json")) == {"seed": 42}


@pytest.mark.parametrize("bundle_path", ["../private.zip", "/tmp/private.zip", "source/../../private.zip", "private.txt"])
def test_reproducibility_bundle_cannot_escape_study(web_case, bundle_path):
    server, client, _, _ = web_case
    study_root = server.state.studies_root / "sample-study"
    write_json(study_root / "manifest.json", {"title": "Invalid", "files": [], "reproducibility_bundle": bundle_path})
    assert client.get("/api/studies/sample-study/bundle").status_code == 400


def test_failed_actual_cli_job_preserves_diagnostics(web_case):
    _, client, source, _ = web_case
    project_id = import_project(client, source)
    action_ok(client, project_id, "research", candidate="asset-inventory")
    response = client.post(f"/api/projects/{project_id}/actions", json={"action": "manuscript-build", "pdf": False})
    job = finished(client, response.json()["job"]["id"])
    assert job["status"] == "failed"
    assert "No successful experimental evidence" in job["log"]
    assert job["result"] is None


def test_project_jobs_cannot_race(web_case, monkeypatch):
    server, client, source, _ = web_case
    project_id = import_project(client, source)
    started = threading.Event()
    release = threading.Event()
    def hold_job(command, environment, timeout, job):
        started.set()
        assert release.wait(timeout=5)
        return 0, '{"fixture": true}\n'
    monkeypatch.setattr(server.state, "_execute", hold_job)
    first = client.post(f"/api/projects/{project_id}/actions", json={"action": "research", "candidate": "asset-inventory"})
    assert first.status_code == 202
    assert started.wait(timeout=2)
    try:
        second = client.post(f"/api/projects/{project_id}/actions", json={"action": "research", "candidate": "asset-inventory"})
        assert second.status_code == 400
        assert "already active" in second.json()["error"]
    finally:
        release.set()
    assert finished(client, first.json()["job"]["id"])["status"] == "succeeded"


@pytest.mark.parametrize("approval_kind", ["record", "freeze"])
def test_canonical_edit_reloads_approval_when_acquiring_persistent_lock(web_case, monkeypatch, approval_kind):
    """An external approval committed just before locking must win the edit."""
    server, client, source, _ = web_case
    project_id = import_project(client, source)
    action_ok(client, project_id, "research", candidate="asset-inventory")
    action_ok(client, project_id, "run")
    built = action_ok(client, project_id, "manuscript-build", pdf=False)
    paper_id = built["paper"]
    workspace_root = server.state.workspace_path(project_id)
    canonical_path = workspace_root / "manuscripts" / paper_id / "canonical.json"
    before = canonical_path.read_bytes()
    canonical = json.loads(before)
    canonical["title"] = "An author edit after approval"
    from contextlib import contextmanager
    from paper_factory.models import Paper, PaperState
    from paper_factory.workspace import Workspace
    ws = Workspace(workspace_root)
    original_lock = Workspace.lock
    injected = False
    lock_names = []

    @contextmanager
    def racing_lock(selected_ws, name):
        nonlocal injected
        if selected_ws.root == workspace_root:
            lock_names.append(name)
            if not injected and name.startswith(("paper-", "study-")):
                injected = True
                # Represents another process having completed approval before
                # the editor obtains the shared persistent paper lock.
                if approval_kind == "record":
                    paper = ws.get("paper", paper_id, Paper)
                    paper.state = PaperState.AUTHOR_APPROVED
                    ws.save("paper", paper)
                else:
                    (workspace_root / "freezes" / paper_id).mkdir()
        with original_lock(selected_ws, name):
            yield

    monkeypatch.setattr(Workspace, "lock", racing_lock)
    response = client.put(f"/api/projects/{project_id}/manuscripts/{paper_id}/canonical", json={"canonical": canonical})
    assert injected
    assert response.status_code == 400
    assert "immutable" in response.json()["error"]
    assert canonical_path.read_bytes() == before
    assert lock_names[0] == f"paper-{paper_id}"


def test_canonical_edit_rejects_modified_source_snapshot(web_case):
    server, client, source, _ = web_case
    project_id = import_project(client, source)
    action_ok(client, project_id, "research", candidate="asset-inventory")
    action_ok(client, project_id, "run")
    built = action_ok(client, project_id, "manuscript-build", pdf=False)
    paper_id = built["paper"]
    workspace_root = server.state.workspace_path(project_id)
    canonical_path = workspace_root / "manuscripts" / paper_id / "canonical.json"
    before = canonical_path.read_bytes()
    canonical = json.loads(before)
    canonical["title"] = "An edited title"
    tampered = workspace_root / "source" / "data.csv"
    tampered.chmod(0o600)
    tampered.write_text("x\n99\n", encoding="utf-8")
    response = client.put(f"/api/projects/{project_id}/manuscripts/{paper_id}/canonical", json={"canonical": canonical})
    assert response.status_code == 400
    assert "snapshot was modified" in response.json()["error"]
    assert canonical_path.read_bytes() == before


def test_canonical_edit_uses_shared_cli_paper_lock(web_case):
    server, client, source, _ = web_case
    project_id = import_project(client, source)
    action_ok(client, project_id, "research", candidate="asset-inventory")
    action_ok(client, project_id, "run")
    built = action_ok(client, project_id, "manuscript-build", pdf=False)
    paper_id = built["paper"]
    from paper_factory.workspace import Workspace
    ws = Workspace(server.state.workspace_path(project_id))
    canonical_path = ws.path(f"manuscripts/{paper_id}/canonical.json")
    before = canonical_path.read_bytes()
    canonical = json.loads(before)
    canonical["title"] = "A blocked concurrent edit"
    with ws.lock(f"paper-{paper_id}"):
        response = client.put(f"/api/projects/{project_id}/manuscripts/{paper_id}/canonical", json={"canonical": canonical})
    assert response.status_code == 400
    assert f"Another operation is already running for paper-{paper_id}" in response.json()["error"]
    assert canonical_path.read_bytes() == before


@pytest.mark.parametrize("explicit_override", [False, True])
def test_bare_interpreter_invocation_preserves_pdf_tool_discovery(web_case, monkeypatch, explicit_override, pandoc):
    """No shell activation is required for a web job to find its PDF tools."""
    server, client, source, _ = web_case
    import os
    import shutil
    import sys
    interpreter_bin = Path(sys.executable).absolute().parent
    pandoc_path = Path(pandoc).resolve()
    pytest.importorskip("typst")
    pypdf = pytest.importorskip("pypdf")
    # Deliberately omit the invoking virtualenv's bin directory, reproducing a
    # direct .venv/bin/paperfactory serve invocation from an unactivated shell.
    inherited_entries = [
        entry for entry in os.environ.get("PATH", "").split(os.pathsep)
        if Path(entry).absolute() != interpreter_bin
    ]
    # Pandoc may be an external installation or supplied by pypandoc_binary.
    # Preserve its external discovery path without activating the virtualenv.
    if pandoc_path.parent != interpreter_bin:
        inherited_entries.insert(0, str(pandoc_path.parent))
    inherited_path = os.pathsep.join(inherited_entries)
    monkeypatch.setenv("PATH", inherited_path)
    monkeypatch.delenv("PYPANDOC_PANDOC", raising=False)
    if explicit_override:
        monkeypatch.setenv("PYPANDOC_PANDOC", str(pandoc_path))
    executed = []
    original_execute = server.state._execute
    def inspect_execute(command, environment, timeout, job):
        if job["action"] in {"manuscript-build", "manuscript-render"}:
            assert environment["PATH"].split(os.pathsep)[0] == str(interpreter_bin)
            assert environment["PATH"] == str(interpreter_bin) + (os.pathsep + inherited_path if inherited_path else "")
            assert Path(shutil.which("pandoc", path=environment["PATH"])).resolve() == pandoc_path
            if explicit_override:
                assert command[command.index("--pandoc") + 1] == str(pandoc_path)
            else:
                assert "--pandoc" not in command
            executed.append(job["action"])
        return original_execute(command, environment, timeout, job)
    monkeypatch.setattr(server.state, "_execute", inspect_execute)
    project_id = import_project(client, source)
    action_ok(client, project_id, "research", candidate="asset-inventory")
    action_ok(client, project_id, "run")
    built = action_ok(client, project_id, "manuscript-build", pdf=True)
    assert built["compile_report"]["status"] == "COMPILED"
    assert Path(built["compile_report"]["command"][0]).resolve() == pandoc_path
    paper_id = built["paper"]
    pdf_response = client.get(f"/api/projects/{project_id}/files/manuscripts/{paper_id}/manuscript.pdf")
    assert pdf_response.status_code == 200
    assert len(pypdf.PdfReader(BytesIO(pdf_response.content)).pages) > 0
    action_ok(client, project_id, "manuscript-render", paper=paper_id, pdf=True)
    assert action_ok(client, project_id, "integrity-check", paper=paper_id)["passed"] is True
    assert executed == ["manuscript-build", "manuscript-render"]

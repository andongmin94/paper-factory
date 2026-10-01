import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from paper_factory import literature, manuscript, project, venues
from paper_factory.author import AuthorProfile
from paper_factory.cli import app
from paper_factory.models import Claim, Paper, Study, Provenance, Submission
from paper_factory.venue_policy import VenuePolicy
from paper_factory.workspace import Workspace


@pytest.fixture
def cli_case(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_HOME", str(tmp_path / "home"))
    for field in AuthorProfile.model_fields:
        monkeypatch.delenv(f"PF_AUTHOR_{field.upper()}", raising=False)
    monkeypatch.delenv("PF_AUTHOR_PROFILE_JSON", raising=False)
    monkeypatch.setenv("PF_AUTHOR_DISPLAY_NAME", "CLI Researcher")
    monkeypatch.setenv("PF_AUTHOR_EMAIL", "cli@example.org")
    monkeypatch.setenv("PF_AUTHOR_AFFILIATION", "Example University")
    original_which = manuscript.shutil.which
    monkeypatch.setattr(manuscript.shutil, "which", lambda command, *args, **kwargs: None if command == "pandoc" else original_which(command, *args, **kwargs))
    source = tmp_path / "project"
    source.mkdir()
    (source / "analysis.py").write_text("print('fixture')\n", encoding="utf-8")
    (source / "data.csv").write_text("x\n1\n2\n", encoding="utf-8")
    (source / ".env").write_text("PRIVATE_TOKEN=not-exported\n", encoding="utf-8")
    return CliRunner(), source, tmp_path / "workspace"


def invoke_ok(runner, arguments):
    result = runner.invoke(app, arguments)
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_cli_help_exposes_phase_one_commands():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("start", "status", "research", "experiment", "manuscript", "integrity"):
        assert command in result.output


def test_cli_official_device_login_waits_for_actual_probe(monkeypatch):
    from paper_factory import cli

    class FixtureConnection:
        def __init__(self):
            self.states = iter([
                {"status": "waiting_user", "model_available": False, "user_code": "TEST-CODE", "verification_url": "https://auth.openai.com/codex/device"},
                {"status": "authenticated", "model_available": False},
                {"status": "probing", "model_available": False},
                {"status": "available", "model_available": True},
            ])
            self.calls = []

        def login(self):
            self.calls.append("login")

        def status(self):
            return next(self.states)

        def probe(self):
            self.calls.append("probe")

        def close(self):
            self.calls.append("close")

    connection = FixtureConnection()
    monkeypatch.setattr(cli, "_connection_manager", lambda: connection)
    monkeypatch.setattr(cli.time, "sleep", lambda delay: None)
    result = CliRunner().invoke(app, ["auto", "login"])
    assert result.exit_code == 0, result.output
    assert connection.calls == ["login", "probe", "close"]
    assert "https://auth.openai.com/codex/device" in result.stdout
    assert '"model_available": true' in result.stdout


def test_cli_probe_failure_is_not_success_with_an_existing_connection(monkeypatch):
    from paper_factory import cli

    class FixtureConnection:
        closed = False

        def probe(self):
            pass

        def status(self):
            return {"status": "blocked", "code": "AUTH_REQUIRED", "model_available": True,
                    "message": "Synthetic pending probe failed; the earlier connection is retained."}

        def close(self):
            self.closed = True

    connection = FixtureConnection()
    monkeypatch.setattr(cli, "_connection_manager", lambda: connection)
    result = CliRunner().invoke(app, ["auto", "probe"])
    assert result.exit_code == 1 and connection.closed
    assert '"code": "AUTH_REQUIRED"' in result.stdout


def test_cli_login_preflight_failure_does_not_wait_on_someone_else_session(monkeypatch):
    from paper_factory import cli

    class FixtureConnection:
        closed = False

        def login(self):
            return {"status": "waiting_user", "code": "CONNECTION_BUSY", "message": "Synthetic other login already running"}

        def status(self):
            pytest.fail("A preflight failure must not poll the existing login")

        def close(self):
            self.closed = True

    connection = FixtureConnection()
    monkeypatch.setattr(cli, "_connection_manager", lambda: connection)
    result = CliRunner().invoke(app, ["auto", "login"])
    assert result.exit_code == 1 and connection.closed
    assert '"code": "CONNECTION_BUSY"' in result.stdout


@pytest.mark.parametrize("command,method", [("connection", "status"), ("disconnect", "disconnect"), ("login-cancel", "cancel")])
def test_cli_connection_controls_do_not_generate_models(monkeypatch, command, method):
    from paper_factory import cli

    class FixtureConnection:
        def __init__(self):
            self.calls = []

        def __getattr__(self, name):
            def action():
                self.calls.append(name)
                return {"status": "disconnected", "model_available": False}
            return action

    connection = FixtureConnection()
    monkeypatch.setattr(cli, "_connection_manager", lambda: connection)
    result = CliRunner().invoke(app, ["auto", command])
    assert result.exit_code == 0, result.output
    assert connection.calls == [method, "close"]


def test_cli_local_end_to_end_keeps_source_separate(cli_case):
    runner, source, destination = cli_case
    before = project.inventory(source)
    start = invoke_ok(runner, ["--workspace", str(destination), "start", str(source)])
    assert start["workspace"] == str(destination.resolve())
    assert start["assets"] == 2
    ws = Workspace(destination)
    status = invoke_ok(runner, ["status"])
    assert status["studies"] == [] and status["papers"] == []
    candidates = invoke_ok(runner, ["--workspace", str(destination), "research", "--list"])
    assert candidates[0]["id"] == "asset-inventory"
    assert ws.list("study", Study) == []
    selected = invoke_ok(runner, ["research", "--candidate", candidates[0]["id"]])
    assert selected["study"]
    run = invoke_ok(runner, ["experiment", "run"])
    assert run["status"] == "SUCCEEDED"
    assert run["metrics"]["file_count"] == 2
    built = invoke_ok(runner, ["manuscript", "build"])
    assert built["compile_report"]["status"] == "COMPILE_READY"
    report = invoke_ok(runner, ["integrity", "check"])
    assert report["passed"] is True and report["claim_count"] == 2
    status = invoke_ok(runner, ["status"])
    assert status["papers"][0]["state"] == "INTEGRITY_CHECKED"
    assert status["experiments"] == {"succeeded": 1, "failed": 0, "running": 0}
    assert project.inventory(source) == before
    assert not (destination / "source" / ".env").exists()
    assert not (source / "records.sqlite3").exists()


def test_cli_rejects_workspace_inside_source_without_modifying_project(cli_case):
    runner, source, _ = cli_case
    before = project.inventory(source)
    result = runner.invoke(app, ["--workspace", str(source / "workspace"), "start", str(source)])
    assert result.exit_code == 1
    assert "separate directories" in result.output
    assert project.inventory(source) == before
    assert not (source / "workspace").exists()


def test_cli_missing_evidence_and_approval_are_actionable_errors(cli_case):
    runner, source, destination = cli_case
    invoke_ok(runner, ["--workspace", str(destination), "start", str(source)])
    invoke_ok(runner, ["research"])
    missing = runner.invoke(app, ["manuscript", "build"])
    assert missing.exit_code == 1
    assert "No successful experimental evidence" in missing.output
    ws = Workspace(destination)
    assert ws.list("claim", Claim) == [] and ws.list("paper", Paper) == []
    invoke_ok(runner, ["experiment", "run"])
    invoke_ok(runner, ["manuscript", "build"])
    approval = runner.invoke(app, ["manuscript", "approve", "--assessment", "Reviewed scientific limitations."])
    assert approval.exit_code == 1
    assert "--approve" in approval.output
    search = runner.invoke(app, ["manuscript", "approve", "--approve", "--assessment", "Reviewed scientific limitations."])
    assert search.exit_code == 1
    assert "literature search" in search.output
    assert list((destination / "freezes").iterdir()) == []


def test_cli_integrity_failure_returns_nonzero_and_report(cli_case):
    runner, source, destination = cli_case
    invoke_ok(runner, ["--workspace", str(destination), "start", str(source)])
    invoke_ok(runner, ["research"])
    invoke_ok(runner, ["experiment", "run"])
    built = invoke_ok(runner, ["manuscript", "build"])
    path = destination / "manuscripts" / built["paper"] / "manuscript.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nUnsupported inserted result.\n", encoding="utf-8")
    checked = runner.invoke(app, ["integrity", "check"])
    assert checked.exit_code == 1
    report = json.loads(checked.stdout)
    assert report["passed"] is False
    assert "Rendered manuscript changed after build" in report["errors"]
    assert (destination / "reports" / f"{built['paper']}-integrity.json").is_file()


def test_cli_fails_cleanly_without_current_workspace(cli_case):
    runner, _, _ = cli_case
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 1
    assert "Run paperfactory start" in result.output


def record_empty_search(ws):
    """Record a genuine mocked provider response without making a network call."""
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"status": "ok", "message": {"items": []}}))
    with httpx.Client(transport=transport) as client:
        literature.search(ws, "reproducible research", ws.latest("study", Study), client=client)


def test_cli_explicit_author_json_overrides_environment_in_build_and_approval(cli_case):
    runner, source, destination = cli_case
    invoke_ok(runner, ["--workspace", str(destination), "start", str(source)])
    invoke_ok(runner, ["research"])
    invoke_ok(runner, ["experiment", "run"])
    record_empty_search(Workspace(destination))
    author = {"display_name": "Explicit Researcher", "email": "explicit@example.org", "affiliation": "Explicit University"}
    argument = json.dumps(author)
    built = invoke_ok(runner, ["manuscript", "build", "--author-json", argument])
    canonical = json.loads((destination / "manuscripts" / built["paper"] / "canonical.json").read_text(encoding="utf-8"))
    assert all(canonical["author"][field] == value for field, value in author.items())
    without_override = runner.invoke(app, ["manuscript", "approve", "--approve", "--assessment", "Reviewed related work and limitations."])
    assert without_override.exit_code == 1
    assert "Author profile differs" in without_override.output
    approved = invoke_ok(runner, ["manuscript", "approve", "--approve", "--assessment", "Reviewed related work and limitations.", "--author-json", argument])
    assert approved["state"] == "AUTHOR_APPROVED"
    approval = json.loads((destination / "freezes" / built["paper"] / "approval.json").read_text(encoding="utf-8"))
    assert approval["approved_by"] == "Explicit Researcher"


@pytest.mark.parametrize("command", ["build", "approve"])
@pytest.mark.parametrize("author_json", ["{", "[]"])
def test_cli_invalid_explicit_author_json_fails_cleanly(cli_case, command, author_json):
    runner, source, destination = cli_case
    invoke_ok(runner, ["--workspace", str(destination), "start", str(source)])
    invoke_ok(runner, ["research"])
    invoke_ok(runner, ["experiment", "run"])
    if command == "approve":
        record_empty_search(Workspace(destination))
        invoke_ok(runner, ["manuscript", "build"])
    arguments = ["manuscript", command, "--author-json", author_json]
    if command == "approve":
        arguments += ["--approve", "--assessment", "Reviewed related work and limitations."]
    result = runner.invoke(app, arguments)
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "Traceback" not in result.output
    if author_json == "[]":
        assert "object" in result.output or "mapping" in result.output
    else:
        assert "Expecting" in result.output or "JSON" in result.output
    assert list((destination / "freezes").iterdir()) == []


@pytest.mark.parametrize("complete", [False, True])
def test_cli_explicit_author_metadata_must_still_satisfy_required_profile(cli_case, monkeypatch, complete):
    runner, source, destination = cli_case
    for field in AuthorProfile.model_fields:
        monkeypatch.delenv(f"PF_AUTHOR_{field.upper()}", raising=False)
    invoke_ok(runner, ["--workspace", str(destination), "start", str(source)])
    invoke_ok(runner, ["research"])
    invoke_ok(runner, ["experiment", "run"])
    record_empty_search(Workspace(destination))
    author = {"display_name": "Explicit Researcher"}
    if complete:
        author.update(email="explicit@example.org", affiliation="Explicit University")
    argument = json.dumps(author)
    built = invoke_ok(runner, ["manuscript", "build", "--author-json", argument])
    result = runner.invoke(app, ["manuscript", "approve", "--approve", "--assessment", "Reviewed related work and limitations.", "--author-json", argument])
    if complete:
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["state"] == "AUTHOR_APPROVED"
        assert (destination / "freezes" / built["paper"] / "approval.json").is_file()
    else:
        assert result.exit_code == 1
        assert "Required author metadata missing" in result.output
        assert "email" in result.output and "affiliation" in result.output
        assert list((destination / "freezes").iterdir()) == []


def save_venue(ws):
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": [{
        "id": "https://openalex.org/S100", "type": "journal", "display_name": "CLI Journal", "issn": ["1234-5678"],
        "homepage_url": "https://example.org/journal", "host_organization_name": "CLI Publisher",
    }]}))) as client:
        return venues.discover(ws, "software", client=client)[0]


def test_cli_phase_two_help_schema_and_uninvented_editable_inputs(cli_case):
    runner, source, destination = cli_case
    invoke_ok(runner, ["--workspace", str(destination), "start", str(source)])
    ws = Workspace(destination)
    venue = save_venue(ws)
    help_result = runner.invoke(app, ["--help"])
    assert "venue" in help_result.output and "submission" in help_result.output
    schema = invoke_ok(runner, ["venue", "policy", "schema"])
    assert "PolicyValues" in schema["$defs"]
    result = invoke_ok(runner, ["venue", "policy", "init", venue.id, "--source", "https://example.org/guidelines"])
    spec = json.loads(Path(result["spec"]).read_bytes())
    assert spec["reviewed_by"] is None and not spec["evidence"]
    assert spec["values"]["indexing"] == "unknown" and spec["values"]["ai_use_allowed"] is None
    policy = VenuePolicy(venue_id=venue.id, status="review_needed", ttl_days=7, evidence={}, reviewed_by=None, official_origins=[], issues=["Incomplete fixture policy"], spec_path="unused.json", spec_sha256="unused", receipt_path="unused-receipt.json", receipt_sha256="unused", verified_at="2026-09-30T00:00:00+00:00", sources=[], values={"required_declarations": ["funding", "conflict_of_interest"]})
    ws.save("policy", policy)
    candidate = Submission(paper_id="paper-fixture", venue_id=venue.id, policy_id=policy.id, candidate_digest="synthetic")
    ws.save("submission", candidate)
    result = invoke_ok(runner, ["submission", "settings", candidate.id])
    settings = json.loads(Path(result["settings"]).read_bytes())
    assert settings["declarations"] == {"funding": "", "conflict_of_interest": ""}
    assert not settings["scope_fit"] and not settings["cover_letter"]
    repeated = runner.invoke(app, ["submission", "settings", candidate.id])
    assert repeated.exit_code == 1 and "already exists" in repeated.output


@pytest.mark.parametrize("protected", ["original", "source", "freezes", "runs"])
def test_cli_editable_specs_cannot_modify_protected_assets(cli_case, protected):
    runner, source, destination = cli_case
    invoke_ok(runner, ["--workspace", str(destination), "start", str(source)])
    ws = Workspace(destination)
    venue = save_venue(ws)
    folder = source if protected == "original" else destination / protected
    target = folder / "policy-edit.json"
    result = runner.invoke(app, ["venue", "policy", "init", venue.id, "--output", str(target)])
    assert result.exit_code == 1 and "outside original/source" in result.output
    assert not target.exists()


def test_cli_render_preserves_author_edit_and_ai_record_has_study_scope(cli_case):
    runner, source, destination = cli_case
    invoke_ok(runner, ["--workspace", str(destination), "start", str(source)])
    study = invoke_ok(runner, ["research"])
    invoke_ok(runner, ["experiment", "run"])
    built = invoke_ok(runner, ["manuscript", "build"])
    path = destination / "manuscripts" / built["paper"] / "canonical.json"
    doc = json.loads(path.read_bytes())
    doc["title"] = "Author revised descriptive analysis"
    path.write_text(json.dumps(doc), encoding="utf-8")
    invoke_ok(runner, ["manuscript", "render"])
    assert Workspace(destination).latest("paper", Paper).title == doc["title"]
    activity = invoke_ok(runner, ["record-ai-use", "language editing", "--tool", "Fixture AI", "--model", "fixture-only"])
    record = Workspace(destination).get("provenance", activity["activity"], Provenance)
    assert record.inputs == [study["study"]]


def test_cli_explicit_env_file_supplies_author_but_explicit_json_still_wins(cli_case, monkeypatch):
    runner, source, destination = cli_case
    for field in AuthorProfile.model_fields:
        monkeypatch.delenv(f"PF_AUTHOR_{field.upper()}", raising=False)
    env_file = destination.parent / "private-author.env"
    env_file.write_text("PF_AUTHOR_DISPLAY_NAME=Private Researcher\nPF_AUTHOR_EMAIL=private@example.org\nPF_AUTHOR_AFFILIATION=Independent Research\n", encoding="utf-8")
    invoke_ok(runner, ["--workspace", str(destination), "start", str(source)])
    invoke_ok(runner, ["research"])
    invoke_ok(runner, ["experiment", "run"])
    built = invoke_ok(runner, ["--env-file", str(env_file), "manuscript", "build"])
    canonical_path = destination / "manuscripts" / built["paper"] / "canonical.json"
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    assert canonical["author"]["display_name"] == "Private Researcher"
    assert canonical["author"]["email"] == "private@example.org"
    assert canonical["author"]["affiliation"] == "Independent Research"
    override = {"display_name": "Explicit Researcher"}
    invoke_ok(runner, ["--env-file", str(env_file), "manuscript", "build", "--author-json", json.dumps(override)])
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    assert canonical["author"]["display_name"] == "Explicit Researcher"
    assert canonical["author"]["email"] == "private@example.org"
    assert env_file.read_text(encoding="utf-8").startswith("PF_AUTHOR_DISPLAY_NAME=Private Researcher")


def test_cli_does_not_discover_dotenv_or_print_malformed_secret(cli_case, monkeypatch):
    runner, source, destination = cli_case
    current_directory = destination.parent / "current-directory"
    current_directory.mkdir()
    (current_directory / ".env").write_text("PF_AUTHOR_EMAIL=unexpected@example.org\n", encoding="utf-8")
    monkeypatch.chdir(current_directory)
    import os
    before = os.environ["PF_AUTHOR_EMAIL"]
    invoke_ok(runner, ["--workspace", str(destination), "start", str(source)])
    assert os.environ["PF_AUTHOR_EMAIL"] == before
    malformed = current_directory / "malformed.env"
    malformed.write_text("PF_AUTHOR_EMAIL='private-secret-value\n", encoding="utf-8")
    result = runner.invoke(app, ["--env-file", str(malformed), "status"])
    assert result.exit_code == 1
    assert "line 1" in result.output
    assert "private-secret-value" not in result.output
    assert "Traceback" not in result.output


def test_cli_env_file_is_inherited_by_real_web_cli_workers(cli_case, monkeypatch):
    """Startup configuration reaches worker subprocesses without file discovery."""
    runner, source, destination = cli_case
    for field in AuthorProfile.model_fields:
        monkeypatch.delenv(f"PF_AUTHOR_{field.upper()}", raising=False)
    monkeypatch.delenv("PF_HOME", raising=False)
    monkeypatch.setenv("PF_OJS_API_TOKEN", "temporary-before-test")
    monkeypatch.delenv("PF_OJS_API_TOKEN", raising=False)
    home = destination.parent / "private-home"
    env_file = destination.parent / "private-web.env"
    env_file.write_text(
        "PF_AUTHOR_DISPLAY_NAME=Web Private Researcher\nPF_AUTHOR_EMAIL=web-private@example.org\n"
        "PF_AUTHOR_AFFILIATION=Independent Research\nPF_OJS_API_TOKEN=secret-must-not-appear-in-jobs\n"
        f"PF_HOME={home}\n", encoding="utf-8",
    )
    from paper_factory import web
    import threading
    import time
    verified = {}

    def exercise_web_startup(**kwargs):
        assert kwargs["data_root"] == home / "web"
        server = web.create_server(port=0, data_root=kwargs["data_root"], studies_root=destination.parent / "studies", source_roots=[destination.parent])
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        address = f"http://127.0.0.1:{server.server_port}"
        try:
            with httpx.Client(base_url=address, headers={"Origin": address}, timeout=20) as client:
                def wait(job):
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        value = client.get(f"/api/jobs/{job}").json()
                        if value["status"] not in {"queued", "running"}:
                            assert value["status"] == "succeeded", value
                            assert "secret-must-not-appear-in-jobs" not in value["log"]
                            return value["result"]
                        time.sleep(0.02)
                    pytest.fail("Configured web job did not complete")
                response = client.post("/api/projects", json={"source": str(source)})
                assert response.status_code == 202, response.text
                value = response.json()
                project_id = value["project"]["id"]
                wait(value["job"]["id"])
                built = None
                for payload in ({"action": "research", "candidate": "asset-inventory"}, {"action": "run"}, {"action": "manuscript-build", "pdf": False}):
                    response = client.post(f"/api/projects/{project_id}/actions", json=payload)
                    assert response.status_code == 202, response.text
                    built = wait(response.json()["job"]["id"])
                canonical = client.get(f"/api/projects/{project_id}/files/manuscripts/{built['paper']}/canonical.json").json()
                verified["author"] = canonical["author"]
                assert not (server.state.workspace_path(project_id) / "source" / env_file.name).exists()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    monkeypatch.setattr(web, "serve", exercise_web_startup)
    result = runner.invoke(app, ["--env-file", str(env_file), "serve"])
    assert result.exit_code == 0, result.output
    assert verified["author"]["display_name"] == "Web Private Researcher"
    assert verified["author"]["email"] == "web-private@example.org"
    assert verified["author"]["affiliation"] == "Independent Research"
    assert "secret-must-not-appear-in-jobs" not in result.output

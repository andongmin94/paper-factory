"""A local CLI with explicit boundaries for network lookup and author approval."""

import functools
import json
import sqlite3
import time
from pathlib import Path
from typing import Annotated

import httpx
import typer

from . import __version__
from .autonomous.provider import ProviderBlocked
from . import experiments, integrity, literature, manuscript, project, research as research_engine
from . import venues, venue_policy, venue_compiler, submission_package, publication, preprints, revisions, revision_submission, portal
from .evidence import claims_for_run, study_readiness_errors
from .models import ExperimentManifest, ExperimentRun, Paper, Project, Provenance, Study, Submission
from .workspace import Workspace, ensure_unlinked, write_json

app = typer.Typer(no_args_is_help=True, help="Evidence-first research, submission packages and guarded publication tracking.")
experiment_app = typer.Typer(no_args_is_help=True, help="Plan and run experiments in isolated working copies.")
literature_app = typer.Typer(no_args_is_help=True, help="Explicit network requests: only query/DOI goes to Crossref.")
manuscript_app = typer.Typer(no_args_is_help=True, help="Build, review and freeze a canonical manuscript.")
integrity_app = typer.Typer(no_args_is_help=True, help="Check evidence, citations and manuscript consistency.")
venue_app = typer.Typer(no_args_is_help=True, help="Discover venues via OpenAlex and select an approved paper's venue.")
policy_app = typer.Typer(no_args_is_help=True, help="Review typed requirements against live official policy pages.")
submission_app = typer.Typer(no_args_is_help=True, help="Prepare packages, reserve one peer-review slot and record confirmed journal events.")
preprint_app = typer.Typer(no_args_is_help=True, help="Prepare permitted preprints and record actual postings separately from peer review.")
revision_app = typer.Typer(no_args_is_help=True, help="Link actual referee comments to verified manuscript changes and responses.")
revision_submission_app = typer.Typer(no_args_is_help=True, help="Prepare and record a revised delivery within the original journal submission.")
portal_app = typer.Typer(no_args_is_help=True, help="Explicit OJS 3.5 draft upload, inspected final Submit and read-only reconciliation.")
auto_app = typer.Typer(no_args_is_help=True, help="Autonomous research using official Codex subscription authentication and isolated experiments.")
app.add_typer(experiment_app, name="experiment")
app.add_typer(literature_app, name="literature")
app.add_typer(manuscript_app, name="manuscript")
app.add_typer(integrity_app, name="integrity")
app.add_typer(venue_app, name="venue")
venue_app.add_typer(policy_app, name="policy")
app.add_typer(submission_app, name="submission")
app.add_typer(preprint_app, name="preprint")
app.add_typer(revision_app, name="revision")
revision_app.add_typer(revision_submission_app, name="submission")
submission_app.add_typer(portal_app, name="portal")
app.add_typer(auto_app, name="auto")


def handled(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, OSError, sqlite3.Error, httpx.HTTPError, ProviderBlocked) as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1) from None
    return wrapped


def workspace(ctx: typer.Context) -> Workspace:
    return Workspace.current(ctx.obj.get("workspace"))


def selected_study(ws: Workspace, id: str | None) -> Study:
    return ws.get("study", id, Study) if id else ws.latest("study", Study)


def selected_paper(ws: Workspace, id: str | None) -> Paper:
    return ws.get("paper", id, Paper) if id else ws.latest("paper", Paper)


def output(value) -> None:
    # JSON escapes preserve Unicode without depending on Windows console code pages.
    typer.echo(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False, default=str))


def author_fields(value: str | None) -> dict | None:
    if value is None:
        return None
    fields = json.loads(value)
    if not isinstance(fields, dict):
        raise ValueError("--author-json must contain a JSON object")
    return fields


def editable_destination(ws: Workspace, destination: Path) -> Path:
    """Keep editable configuration outside originals and scientific artifacts."""
    ensure_unlinked(destination.expanduser())
    target = destination.expanduser().resolve()
    protected = [ws.root / name for name in ("source", "runs", "freezes", "manuscripts", "submissions", "publication", "preprints", "revisions", "revision-deliveries", "portals")]
    original = Path(ws.latest("project", Project).source)
    if original.is_dir():
        protected.append(original.resolve())
    if any(target.is_relative_to(directory) for directory in protected):
        raise ValueError("Editable configuration must be outside original/source and scientific artifact directories")
    if target.exists():
        raise ValueError("Configuration already exists; edit it or choose another --output")
    return target


@app.callback()
@handled
def main(ctx: typer.Context,
         workspace: Annotated[Path | None, typer.Option("--workspace", "-w", help="External workspace; defaults to last imported project.")] = None,
         env_file: Annotated[Path | None, typer.Option("--env-file", help="Explicit private dotenv file; existing process settings take precedence. No automatic .env lookup.")] = None):
    if env_file is not None:
        from .config import load_env_file
        load_env_file(env_file)
    ctx.obj = {"workspace": workspace}


@app.command()
@handled
def start(ctx: typer.Context, source: Annotated[str, typer.Argument(help="Local directory or Git URL. Git uses existing configured credentials.")]):
    ws = project.ingest(source, ctx.obj.get("workspace"))
    ws.make_current()
    record = ws.latest("project", Project)
    output({"project": record.id, "workspace": str(ws.root), "assets": len(record.assets), "source_commit": record.source_commit, "snapshot_digest": record.snapshot_digest, "next": "paperfactory research"})


@auto_app.command("doctor")
@handled
def auto_doctor():
    """Inspect official CLI authentication and the provisioned isolated runtime."""
    from .autonomous.provider import CodexProvider
    from .autonomous.runner import research_runner
    codex, isolation = CodexProvider().status(), research_runner().status()
    output({"codex": codex, "isolation": isolation, "ready": codex.get("authentication") == "chatgpt" and codex.get("ready") and isolation.get("ready")})


def _connection_manager():
    from .autonomous.connection import ConnectionManager
    from .autonomous.provider import auth_root
    return ConnectionManager(auth_root())


def _wait_connection(manager, *, authenticate: bool) -> dict:
    deadline = time.monotonic() + 1080
    previous = None
    while time.monotonic() < deadline:
        state = manager.status()
        marker = (state.get("status"), state.get("user_code"), state.get("code"))
        if marker != previous:
            output(state)
            previous = marker
        if authenticate and state.get("status") == "authenticated":
            started = manager.probe()
            if started and started.get("code"):
                if started["code"] != "CONNECTION_BUSY":
                    output(started)
                    return started
            else:
                authenticate = False
        elif state.get("status") not in {"starting", "waiting_user", "authenticated", "probing"}:
            return state
        time.sleep(0.2)
    manager.cancel()
    return manager.status()


@auto_app.command("connection")
@handled
def auto_connection():
    """Show the selected official ChatGPT worker connection without a model call."""
    manager = _connection_manager()
    try:
        output(manager.status())
    finally:
        manager.close()


@auto_app.command("login")
@handled
def auto_login():
    """Start official device login, then verify a real bounded model response."""
    _connect_subscription(login=True)


@auto_app.command("probe")
@handled
def auto_probe():
    """Explicitly verify model access for the authenticated worker connection."""
    _connect_subscription(login=False)


def _connect_subscription(*, login: bool) -> None:
    manager = _connection_manager()
    try:
        started = manager.login() if login else manager.probe()
        if started and started.get("code"):
            output(started)
            raise typer.Exit(1)
        result = _wait_connection(manager, authenticate=login)
        if result.get("status") != "available":
            raise typer.Exit(1)
    finally:
        manager.close()


@auto_app.command("logout")
@handled
def auto_logout():
    """Log out app-owned Codex profiles; preserve platform authentication."""
    manager = _connection_manager()
    try:
        result = manager.logout()
        output(result)
        if result.get("code"):
            raise typer.Exit(1)
    finally:
        manager.close()


@auto_app.command("login-cancel")
@handled
def auto_login_cancel():
    """Cancel the pending official login or model-access verification."""
    manager = _connection_manager()
    try:
        output(manager.cancel())
    finally:
        manager.close()


@auto_app.command("run")
@handled
def auto_run(ctx: typer.Context,
             source: Annotated[str | None, typer.Argument(help="Optional repository URL/local directory; otherwise use the selected workspace.")] = None,
             goal: Annotated[str, typer.Option(help="Research goal; the app selects a feasible substantive controlled software study.")] = "Conduct a controlled empirical study of actual production software behavior with an independent oracle and a meaningful comparator.",
             model: Annotated[str | None, typer.Option(help="Optional Codex model identifier; otherwise the official CLI default.")] = None,
             max_model_calls: Annotated[int, typer.Option(min=1, max=40)] = 12,
             repair_attempts: Annotated[int, typer.Option(min=0, max=5)] = 2,
             wall_seconds: Annotated[int, typer.Option(min=60, max=86400)] = 3600,
             experiment_timeout: Annotated[int, typer.Option(min=1, max=3600)] = 300):
    """Import, design, execute, analyze, write and export one study without this chat."""
    from .autonomous import pipeline
    ws = project.ingest(source, ctx.obj.get("workspace")) if source else workspace(ctx)
    record = pipeline.create(ws, goal, model=model, budget={"max_model_calls": max_model_calls, "repair_attempts": repair_attempts,
                                                          "wall_seconds": wall_seconds, "experiment_timeout_seconds": experiment_timeout})
    typer.echo(f"Autonomous research {record.id}; workspace {ws.root}", err=True)
    result = pipeline.run(ws, record.id)
    output(pipeline.status(ws, result.id))
    if result.status != "completed":
        raise typer.Exit(1)


@auto_app.command("status")
@handled
def auto_status(ctx: typer.Context, pipeline_id: Annotated[str | None, typer.Argument()] = None):
    from .autonomous import pipeline
    ws = workspace(ctx)
    output(pipeline.status(ws, pipeline_id) if pipeline_id else {"pipelines": pipeline.list_runs(ws)})


@auto_app.command("cancel")
@handled
def auto_cancel(ctx: typer.Context, pipeline_id: str):
    from .autonomous import pipeline
    output(pipeline.cancel(workspace(ctx), pipeline_id))


@auto_app.command("resume")
@handled
def auto_resume(ctx: typer.Context, pipeline_id: str):
    from .autonomous import pipeline
    ws = workspace(ctx)
    record = pipeline.resume(ws, pipeline_id)
    result = pipeline.run(ws, record.id)
    output(pipeline.status(ws, result.id))
    if result.status != "completed":
        raise typer.Exit(1)


@auto_app.command("verify")
@handled
def auto_verify(ctx: typer.Context, pipeline_id: str):
    from .autonomous import pipeline
    output(pipeline.verify(workspace(ctx), pipeline_id))


@auto_app.command("select")
@handled
def auto_select(owner: str, count: Annotated[int, typer.Option(min=1, max=3)] = 3):
    from .autonomous.repositories import select_repositories
    output(select_repositories(owner, count=count))


@auto_app.command("batch")
@handled
def auto_batch(owner: str,
               goal: Annotated[str, typer.Option()] = "Conduct a controlled empirical study of actual production software behavior with an independent oracle and a meaningful comparator.",
               count: Annotated[int, typer.Option(min=1, max=3)] = 3,
               max_model_calls: Annotated[int, typer.Option(min=1, max=40)] = 12,
               model: Annotated[str | None, typer.Option()] = None):
    """Select repositories from a public GitHub profile and run separate studies."""
    from .autonomous import pipeline
    from .autonomous.repositories import select_repositories
    selected = select_repositories(owner, count=count)
    results = []
    shared_blocker = None
    for repository in selected["repositories"]:
        if shared_blocker:
            results.append({"repository": repository["name"], "status": "not_started", "code": "SHARED_PROVIDER_BLOCKER",
                            "message": f"The shared subscription worker is blocked by {shared_blocker}; no additional model request was attempted."})
            continue
        ws = project.ingest(repository["url"])
        record = pipeline.create(ws, goal, model=model, budget={"max_model_calls": max_model_calls})
        result = pipeline.run(ws, record.id)
        results.append({"repository": repository["name"], "workspace": str(ws.root), "pipeline": result.id,
                        "status": result.status, "code": result.code, "message": result.message})
        if result.code in {"CODEX_AUTH_REQUIRED", "SUBSCRIPTION_AUTH_REQUIRED", "AUTH_REQUIRED", "NETWORK_ERROR", "RATE_LIMITED", "CODEX_UNAVAILABLE", "CODEX_UNSUPPORTED", "ISOLATION_UNAVAILABLE", "CLEANUP_UNCONFIRMED"}:
            shared_blocker = result.code
    output({"selection": selected, "results": results})
    if len(results) != count or any(item["status"] != "completed" for item in results):
        raise typer.Exit(1)


@app.command()
@handled
def status(ctx: typer.Context):
    ws = workspace(ctx)
    studies = ws.list("study", Study)
    papers = ws.list("paper", Paper)
    runs = ws.list("run", ExperimentRun)
    submissions = ws.list("submission", Submission)
    history = [publication.check(ws, record) for record in submissions]
    preprint_records = ws.list("preprint", preprints.Preprint)
    revision_records = ws.list("revision", revisions.Revision)
    deliveries = ws.list("revision_delivery", revision_submission.RevisionDelivery)
    portal_reports = [portal.check(ws, plan) for plan in portal._plans(ws)]
    output({"version": __version__, "scope": "Evidence-linked research, venue packages, revision and explicit OJS 3.5 submission", "workspace": str(ws.root), "project": ws.latest("project", Project).name, "studies": [{"id": study.id, "title": study.title, "state": study.state, "novelty": study.novelty_status, "experiment_issues": study_readiness_errors(ws, study.id)} for study in studies], "papers": [{"id": paper.id, "state": paper.state} for paper in papers], "experiments": {"succeeded": sum(run.status == "SUCCEEDED" for run in runs), "failed": sum(run.status == "FAILED" for run in runs), "running": sum(run.status == "RUNNING" for run in runs)}, "venues": len(ws.list("venue", venues.Venue)), "policies": len(ws.list("policy", venue_policy.VenuePolicy)), "submissions": [record.model_dump(mode="json") for record in submissions], "publication_history": history, "revisions": [record.model_dump(mode="json") for record in revision_records], "revision_deliveries": [revision_submission.check(ws, record) for record in deliveries], "preprints": [record.model_dump(mode="json") for record in preprint_records], "portals": portal_reports, "external_submission_recorded": any(report.get("external_submission_recorded") for report in history), "external_submission_performed": any(report.get("submission_confirmed") for report in portal_reports)})


@app.command()
@handled
def research(ctx: typer.Context, list_only: Annotated[bool, typer.Option("--list", help="Show ranked candidates without creating a study.")] = False, candidate: Annotated[str | None, typer.Option(help="Candidate ID returned by --list.")] = None, question: Annotated[str | None, typer.Option(help="Explicit research question.")] = None, title: Annotated[str | None, typer.Option()] = None, domain: Annotated[str, typer.Option(help="generic_empirical or software_engineering.")] = "generic_empirical", human_subjects: Annotated[bool, typer.Option(help="Flag human-subject study; automatic experiments blocked.")] = False):
    ws = workspace(ctx)
    candidates = research_engine.discover(ws)
    if list_only:
        output([item.model_dump() for item in candidates])
        return
    study = research_engine.create_study(ws, candidate_id=candidate, question=question, title=title, domain=domain, human_subjects=human_subjects)
    manifest = research_engine.plan(ws, study) if study.research_question == research_engine.INVENTORY_QUESTION else None
    output({"study": study.id, "title": study.title, "research_question": study.research_question, "manifest": str(ws.root / "experiments" / f"{manifest.id}.json") if manifest else None, "notice": "Generated plan is a descriptive asset inventory." if manifest else "A substantive question requires a project-specific experiment manifest; the inventory cannot answer it.", "next": "paperfactory literature search <explicit-query>; paperfactory experiment run" if manifest else "paperfactory experiment register <manifest.json>"})


@literature_app.command("search")
@handled
def search_literature(ctx: typer.Context, query: str, study: Annotated[str | None, typer.Option()] = None, limit: Annotated[int, typer.Option(min=1, max=20)] = 5):
    ws = workspace(ctx)
    selected = selected_study(ws, study)
    typer.echo("Network boundary: sending the supplied query and returned DOIs to Crossref; no project files are sent.", err=True)
    citations = literature.search(ws, query, selected, limit=limit)
    output({"study": selected.id, "citations": [item.model_dump() for item in citations], "notice": "Metadata verified only; full-text findings and novelty require author assessment."})


@literature_app.command("doi")
@handled
def import_doi(ctx: typer.Context, doi: str, study: Annotated[str | None, typer.Option()] = None):
    ws = workspace(ctx)
    selected = selected_study(ws, study)
    citation = literature.import_into_study(ws, doi, selected)
    output(citation.model_dump())


@experiment_app.command("plan")
@handled
def plan_experiment(ctx: typer.Context, study: Annotated[str | None, typer.Option()] = None):
    ws = workspace(ctx)
    manifest = research_engine.plan(ws, selected_study(ws, study))
    output(manifest.model_dump())


@experiment_app.command("register")
@handled
def register_experiment(ctx: typer.Context, path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]):
    ws = workspace(ctx)
    manifest = experiments.register_manifest(ws, path)
    output({"experiment": manifest.id, "study": manifest.study_id})


@experiment_app.command("run")
@handled
def run_experiment(ctx: typer.Context, experiment: Annotated[str | None, typer.Argument()] = None):
    ws = workspace(ctx)
    manifest = ws.get("manifest", experiment, ExperimentManifest) if experiment else ws.latest("manifest", ExperimentManifest)
    run = experiments.run_experiment(ws, manifest)
    if run.status == "SUCCEEDED":
        claims_for_run(ws, run)
    output(run.model_dump())
    if run.status != "SUCCEEDED":
        raise typer.Exit(1)


@manuscript_app.command("build")
@handled
def build_manuscript(ctx: typer.Context, study: Annotated[str | None, typer.Option()] = None, pandoc: Annotated[str | None, typer.Option(help="Path to Pandoc; otherwise use PATH.")] = None, pdf: Annotated[bool, typer.Option(help="Compile PDF with Pandoc and the optional Typst PDF extra.")] = False, author_json: Annotated[str | None, typer.Option(help="Explicit author field JSON; takes priority over environment.")] = None):
    ws = workspace(ctx)
    paper, root = manuscript.build(ws, selected_study(ws, study), pandoc=pandoc, pdf=pdf, author_values=author_fields(author_json))
    issues = study_readiness_errors(ws, paper.study_id)
    output({"paper": paper.id, "canonical": str(root / "canonical.json"), "manuscript": str(root / "manuscript.md"), "compile_report": json.loads((root / "compile-report.json").read_text(encoding="utf-8")), "experiment_review": {"ready": not issues, "issues": issues}, "next": "paperfactory integrity check"})


@manuscript_app.command("render")
@handled
def render_manuscript(ctx: typer.Context, paper: Annotated[str | None, typer.Option()] = None, pandoc: Annotated[str | None, typer.Option()] = None, pdf: Annotated[bool, typer.Option()] = False):
    """Validate and render author edits to canonical.json before approval."""
    ws = workspace(ctx)
    record, root = manuscript.refresh(ws, selected_paper(ws, paper), pandoc=pandoc, pdf=pdf)
    output({"paper": record.id, "canonical": str(root / "canonical.json"), "manuscript": str(root / "manuscript.md"), "experiment_issues": study_readiness_errors(ws, record.study_id), "next": "paperfactory integrity check"})


@integrity_app.command("check")
@handled
def check_integrity(ctx: typer.Context, paper: Annotated[str | None, typer.Option()] = None):
    ws = workspace(ctx)
    report = integrity.check(ws, selected_paper(ws, paper))
    output(report)
    if not report["passed"]:
        raise typer.Exit(1)


@manuscript_app.command("approve")
@handled
def approve_manuscript(ctx: typer.Context, assessment: Annotated[str, typer.Option(help="Author's assessment of related work, novelty, limitations and scientific responsibility.")], approve: Annotated[bool, typer.Option("--approve", help="Explicitly approve the final manuscript and accept scientific responsibility.")] = False, paper: Annotated[str | None, typer.Option()] = None, author_json: Annotated[str | None, typer.Option(help="Explicit author field JSON, matching the approved manuscript.")] = None):
    ws = workspace(ctx)
    path = integrity.approve(ws, selected_paper(ws, paper), approved=approve, assessment=assessment, author_values=author_fields(author_json))
    output({"freeze": str(path), "state": "AUTHOR_APPROVED", "review_warnings": json.loads((path / "approval.json").read_text(encoding="utf-8"))["integrity"]["warnings"], "notice": "No external submission performed."})


@app.command("record-ai-use")
@handled
def record_ai_use(ctx: typer.Context, role: str, tool: Annotated[str, typer.Option()], model: Annotated[str, typer.Option()], inputs: Annotated[list[str] | None, typer.Option("--input")] = None, outputs: Annotated[list[str] | None, typer.Option("--output")] = None, study: Annotated[str | None, typer.Option(help="Study scope; defaults to latest study.")] = None):
    ws = workspace(ctx)
    scoped_inputs = list(inputs or [])
    if study or ws.list("study", Study):
        study_id = selected_study(ws, study).id
        if study_id not in scoped_inputs:
            scoped_inputs.append(study_id)
    activity = Provenance(role=role, tool=tool, model=model, inputs=scoped_inputs, outputs=outputs or [], ai=True)
    ws.save("provenance", activity)
    output({"activity": activity.id, "notice": "Rebuild manuscript to include this AI-use record."})


@venue_app.command("discover")
@handled
def discover_venues(ctx: typer.Context, query: str, limit: Annotated[int, typer.Option(min=1, max=20)] = 5):
    """Send only supplied field/topic keywords to the live OpenAlex directory."""
    ws = workspace(ctx)
    typer.echo("Network boundary: only the supplied query is sent to OpenAlex; publisher rules and indexing still require verification.", err=True)
    output([record.model_dump(mode="json") for record in venues.discover(ws, query, limit=limit)])


@venue_app.command("show")
@handled
def show_venue(ctx: typer.Context, venue: str):
    output(workspace(ctx).get("venue", venue, venues.Venue).model_dump(mode="json"))


@policy_app.command("schema")
def policy_schema():
    """Show typed facts, source evidence and reviewer requirements."""
    output(venue_policy.PolicySpec.model_json_schema())


@policy_app.command("init")
@handled
def init_policy(ctx: typer.Context, venue: str, source: Annotated[list[str] | None, typer.Option("--source", help="Official HTTPS author guideline/policy URL.")] = None, path: Annotated[Path | None, typer.Option("--output")] = None):
    ws = workspace(ctx)
    record = ws.get("venue", venue, venues.Venue)
    destination = editable_destination(ws, path or ws.root / "policy-specs" / f"{record.id}.json")
    write_json(destination, venue_policy.PolicySpec(venue_id=record.id, sources=source or []).model_dump(mode="json"))
    output({"spec": str(destination.resolve()), "next": "Fill typed values and exact visible source excerpts, supply reviewed_by, then run venue policy verify.", "notice": "Null facts are unknown unless supported by evidence; indexing requires current Clarivate evidence."})


@policy_app.command("verify")
@handled
def verify_venue_policy(ctx: typer.Context, venue: str, path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]):
    ws = workspace(ctx)
    typer.echo("Network boundary: fetching supplied public official policy URLs; no manuscript or author information is sent.", err=True)
    policy = venue_policy.verify_policy(ws, ws.get("venue", venue, venues.Venue), path)
    output(policy.model_dump(mode="json"))
    if policy.status != "verified":
        raise typer.Exit(1)


@policy_app.command("show")
@handled
def show_policy(ctx: typer.Context, policy: str):
    ws = workspace(ctx)
    record = ws.get("policy", policy, venue_policy.VenuePolicy)
    output({"policy": record.model_dump(mode="json"), "validation_errors": venue_policy.validate_policy(ws, record)})


@venue_app.command("select")
@handled
def select_venue(ctx: typer.Context, venue: str, policy: Annotated[str, typer.Option()], paper: Annotated[str | None, typer.Option()] = None):
    ws = workspace(ctx)
    record = venue_compiler.select(ws, selected_paper(ws, paper), ws.get("venue", venue, venues.Venue), ws.get("policy", policy, venue_policy.VenuePolicy))
    output(record.model_dump(mode="json"))


@submission_app.command("settings")
@handled
def init_submission_settings(ctx: typer.Context, submission: str, path: Annotated[Path | None, typer.Option("--output")] = None):
    """Prepare editable author statements; never invent declarations."""
    ws = workspace(ctx)
    record = ws.get("submission", submission, Submission)
    policy = ws.get("policy", record.policy_id, venue_policy.VenuePolicy)
    destination = editable_destination(ws, path or ws.root / "submission-settings" / f"{record.id}.json")
    write_json(destination, {"article_type": "", "keywords": [], "scope_fit": "", "cover_letter": "", "declarations": {name: "" for name in policy.values.required_declarations or []}, "csl": None, "csl_license": None, "csl_source_url": None})
    output({"settings": str(destination.resolve()), "accepted_article_types": policy.values.article_types, "notice": "Fill actual author statements before compilation. Final submission attestation is separate."})


@submission_app.command("compile")
@handled
def compile_submission(ctx: typer.Context, submission: str, settings: Annotated[Path, typer.Argument(exists=True, dir_okay=False)], pandoc: Annotated[str | None, typer.Option()] = None):
    ws = workspace(ctx)
    typer.echo("Network boundary: official policy pages are fetched again before compilation.", err=True)
    record, root = venue_compiler.compile_submission(ws, ws.get("submission", submission, Submission), settings, pandoc=pandoc)
    report = ws.get("compilation", record.id, venue_compiler.Compilation)
    output({"submission": record.model_dump(mode="json"), "directory": str(root), "compliance": report.model_dump(mode="json")})
    if report.errors:
        raise typer.Exit(1)


@submission_app.command("package")
@handled
def package_submission(ctx: typer.Context, submission: str):
    ws = workspace(ctx)
    typer.echo("Network boundary: official policy pages are fetched again before packaging.", err=True)
    record, root = submission_package.build(ws, ws.get("submission", submission, Submission))
    output({"package": record.model_dump(mode="json"), "directory": str(root), "archive": str(root / "submission.zip"), "external_submission_performed": False})
    if not record.ready:
        raise typer.Exit(1)


@submission_app.command("check")
@handled
def check_submission(ctx: typer.Context, submission: str):
    ws = workspace(ctx)
    report = submission_package.verify(ws, ws.get("submission", submission, Submission))
    output(report)
    if not report["ready"]:
        raise typer.Exit(1)


def read_record_input(path: Path, model):
    ensure_unlinked(path)
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("Record input must be a regular JSON file no larger than 1 MiB")
    return model.model_validate_json(path.read_bytes())


@submission_app.command("attestation")
@handled
def init_attestation(ctx: typer.Context, submission: str, path: Annotated[Path | None, typer.Option("--output")] = None):
    """Prepare factual declarations for the final package; every answer starts false."""
    ws = workspace(ctx)
    record = ws.get("submission", submission, Submission)
    paper = ws.get("paper", record.paper_id, Paper)
    destination = editable_destination(ws, path or ws.root / "attestations" / f"{record.id}.json")
    write_json(destination, attestation_template(ws, record, paper))
    output({"attestation": str(destination), "next": "Review the package and all six facts, then run submission attest <id> <json> --approve.", "notice": "Attesting reserves this Study's sole peer-review slot. It does not submit or upload the paper."})


def attestation_template(ws: Workspace, record: Submission, paper: Paper) -> dict:
    values = {"actor": paper.approved_by or "", "all_authors_approved": False, "not_under_review_elsewhere": False, "coi_correct": False, "funding_correct": False, "ai_disclosure_correct": False, "author_information_correct": False}
    postings = [item for item in ws.list("preprint", preprints.Preprint) if item.study_id == paper.study_id and item.state == "PREPRINTED"]
    if postings:
        policy = ws.get("policy", record.policy_id, venue_policy.VenuePolicy)
        evidence = policy.evidence.get("preprint_policy")
        values["preprint_review"] = {"decision": "unknown", "preprint_ids": [item.id for item in postings], "evidence": evidence.model_dump(mode="json") if evidence else {"source_url": "", "excerpt": "", "interpretation": ""}}
    return values


@submission_app.command("attestation-schema")
def attestation_schema():
    output(publication.AttestationInput.model_json_schema())


@submission_app.command("attest")
@handled
def attest_submission(ctx: typer.Context, submission: str, path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)], approve: Annotated[bool, typer.Option("--approve", help="Confirm all factual declarations and reserve the sole peer-review slot.")] = False):
    if not approve:
        raise ValueError("Final author attestation requires explicit --approve after reviewing the package and factual declarations")
    ws = workspace(ctx)
    values = read_record_input(path, publication.AttestationInput)
    typer.echo("Network boundary: official policies are fetched again; no manuscript is uploaded.", err=True)
    record = publication.attest(ws, ws.get("submission", submission, Submission), values)
    output({"attestation": record.model_dump(mode="json"), "external_submission_performed": False})


@submission_app.command("receipt-schema")
def receipt_schema():
    """Show the structured journal event fields; a separate actual receipt is required."""
    output(publication.ReceiptInput.model_json_schema())


@submission_app.command("record-receipt")
@handled
def record_submission_receipt(ctx: typer.Context, submission: str, path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)], evidence: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Actual journal receipt/decision file, preserved as evidence.")], confirm: Annotated[bool, typer.Option("--confirm", help="Confirm that this actual receipt establishes the declared journal event.")] = False):
    if not confirm:
        raise ValueError("Recording an external journal event requires explicit --confirm after reviewing the actual receipt")
    ws = workspace(ctx)
    values = read_record_input(path, publication.ReceiptInput)
    record = publication.record_receipt(ws, ws.get("submission", submission, Submission), values, evidence)
    output({"event": record.model_dump(mode="json"), "external_submission_performed": False, "verification": "Author-confirmed imported receipt; Paper Factory did not contact or submit to the journal."})


@submission_app.command("cancel-attestation")
@handled
def cancel_submission_attestation(ctx: typer.Context, submission: str, actor: Annotated[str, typer.Option(help="Approved author's identity.")], reason: Annotated[str, typer.Option(help="Why the reserved candidate was not submitted.")]):
    ws = workspace(ctx)
    record = publication.cancel_attestation(ws, ws.get("submission", submission, Submission), actor, reason)
    output({"event": record.model_dump(mode="json"), "notice": "Only an unsubmitted author attestation can be cancelled. A submitted paper requires confirmed rejection or withdrawal."})


@submission_app.command("history")
@handled
def submission_history(ctx: typer.Context, submission: str):
    ws = workspace(ctx)
    report = publication.check(ws, ws.get("submission", submission, Submission))
    output(report)
    if not report["passed"]:
        raise typer.Exit(1)


@preprint_app.command("schema")
def preprint_schema():
    output({"settings": preprints.PreprintSettings.model_json_schema(), "posting_receipt": preprints.PostingReceipt.model_json_schema()})


@preprint_app.command("settings")
@handled
def init_preprint_settings(ctx: typer.Context, policy: Annotated[str, typer.Option(help="Reviewed target venue policy.")], paper: Annotated[str | None, typer.Option()] = None, path: Annotated[Path | None, typer.Option("--output")] = None):
    ws = workspace(ctx)
    selected = selected_paper(ws, paper)
    reviewed = ws.get("policy", policy, venue_policy.VenuePolicy)
    destination = editable_destination(ws, path or ws.root / "preprint-settings" / f"{selected.id}.json")
    evidence = reviewed.evidence.get("preprint_policy")
    write_json(destination, {"paper_id": selected.id, "policy_id": reviewed.id, "server": "", "server_url": "", "license": "", "reviewed_by": selected.approved_by or "", "decision": "unknown", "evidence": evidence.model_dump(mode="json") if evidence else {"source_url": "", "excerpt": "", "interpretation": ""}, "author_approval": False, "authorized_to_post": False, "policy_interpretation_confirmed": False})
    output({"settings": str(destination), "next": "Review the official preprint policy, server, license and posting permissions; then run preprint prepare <json> --approve."})


@preprint_app.command("prepare")
@handled
def prepare_preprint(ctx: typer.Context, path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)], approve: Annotated[bool, typer.Option("--approve", help="Approve the manuscript, release permission and reviewed preprint policy.")] = False, pandoc: Annotated[str | None, typer.Option(help="Installed Pandoc executable for local preprint exports.")] = None):
    if not approve:
        raise ValueError("Preprint preparation requires explicit --approve and true author declarations")
    ws = workspace(ctx)
    ensure_unlinked(path)
    typer.echo("Network boundary: official preprint policies are fetched again; no manuscript is uploaded.", err=True)
    record, root = preprints.prepare(ws, path, pandoc=pandoc)
    output({"preprint": record.model_dump(mode="json"), "directory": str(root), "external_upload_performed": False})


@preprint_app.command("record")
@handled
def record_preprint(ctx: typer.Context, path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)], evidence: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Actual preprint server posting receipt.")], confirm: Annotated[bool, typer.Option("--confirm", help="Confirm the external posting receipt and version binding.")] = False):
    ws = workspace(ctx)
    ensure_unlinked(path)
    record, root = preprints.record_posting(ws, path, evidence, confirmed=confirm)
    output({"preprint": record.model_dump(mode="json"), "directory": str(root), "external_upload_performed": False, "verification": "Author-confirmed posting receipt; peer-review status is separate."})


@preprint_app.command("check")
@handled
def check_preprint(ctx: typer.Context, preprint: str):
    ws = workspace(ctx)
    report = preprints.check(ws, ws.get("preprint", preprint, preprints.Preprint))
    output(report)
    if not report["valid"]:
        raise typer.Exit(1)


@revision_app.command("schema")
def revision_schema():
    output({"review": revisions.ReviewSpec.model_json_schema(),
            "response_plan": revisions.ResponsePlan.model_json_schema()})


@revision_app.command("import")
@handled
def import_revision(ctx: typer.Context, submission: str,
                    spec: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
                    report: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
                    confirm: Annotated[bool, typer.Option("--confirm", help="Confirm actual referee excerpts and targets after a journal REVISION or REJECTED decision.")] = False):
    ws = workspace(ctx)
    record, root = revisions.import_review(ws, ws.get("submission", submission, Submission), spec, report, confirmed=confirm)
    output({"revision": record.model_dump(mode="json"), "directory": str(root),
            "next": f"paperfactory revision draft {record.id}"})


@revision_app.command("draft")
@handled
def draft_revision(ctx: typer.Context, revision: str,
                   pandoc: Annotated[str | None, typer.Option()] = None,
                   pdf: Annotated[bool, typer.Option()] = False):
    ws = workspace(ctx)
    paper, root = revisions.draft(ws, ws.get("revision", revision, revisions.Revision), pandoc=pandoc, pdf=pdf)
    output({"paper": paper.model_dump(mode="json"), "directory": str(root),
            "next": f"paperfactory revision plan {revision}"})


@revision_app.command("plan")
@handled
def init_revision_plan(ctx: typer.Context, revision: str,
                       path: Annotated[Path | None, typer.Option("--output")] = None):
    ws = workspace(ctx)
    record = ws.get("revision", revision, revisions.Revision)
    destination = editable_destination(ws, path or ws.root / "revision-plans" / f"{record.id}.json")
    write_json(destination, revisions.plan_template(ws, record))
    output({"plan": str(destination), "notice": "Author responses start pending. Supply actual edits, rationale and verified evidence."})


@revision_app.command("apply")
@handled
def apply_revision_plan(ctx: typer.Context, revision: str,
                        plan: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
                        pandoc: Annotated[str | None, typer.Option()] = None,
                        pdf: Annotated[bool, typer.Option()] = False):
    ws = workspace(ctx)
    paper, root = revisions.apply_plan(ws, ws.get("revision", revision, revisions.Revision), plan, pandoc=pandoc, pdf=pdf)
    output({"paper": paper.model_dump(mode="json"), "directory": str(root),
            "next": f"paperfactory integrity check --paper {paper.id}"})


@revision_app.command("experiment")
@handled
def run_revision_experiment(ctx: typer.Context, revision: str,
                            manifest: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]):
    ws = workspace(ctx)
    record = ws.get("revision", revision, revisions.Revision)
    audit = revisions.check(ws, record)
    if not audit["passed"]:
        raise ValueError("Revision review is invalid: " + "; ".join(audit["errors"]))
    values = read_record_input(manifest, ExperimentManifest)
    if values.study_id != record.study_id:
        raise ValueError("Revision experiments must belong to the original Study")
    registered = experiments.register_manifest(ws, manifest)
    run = experiments.run_experiment(ws, registered)
    claims = claims_for_run(ws, run) if run.status == "SUCCEEDED" else []
    output({"run": run.model_dump(mode="json"), "claims": [claim.model_dump(mode="json") for claim in claims]})
    if run.status != "SUCCEEDED":
        raise typer.Exit(1)


@revision_app.command("check")
@handled
def check_revision(ctx: typer.Context, revision: str,
                   historical: Annotated[bool, typer.Option(help="Verify preserved artifacts after the revision round has closed.")] = False):
    ws = workspace(ctx)
    report = revisions.check(ws, ws.get("revision", revision, revisions.Revision), require_active=not historical)
    output(report)
    if not report["passed"]:
        raise typer.Exit(1)


@revision_app.command("response")
@handled
def build_revision_response(ctx: typer.Context, revision: str,
                            plan: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
                            pandoc: Annotated[str | None, typer.Option()] = None):
    ws = workspace(ctx)
    response, root = revisions.build_response(ws, ws.get("revision", revision, revisions.Revision), plan, pandoc=pandoc)
    output({"response": response.model_dump(mode="json"), "directory": str(root),
            "external_submission_performed": False})
    if not response.ready:
        raise typer.Exit(1)


@revision_app.command("response-check")
@handled
def check_revision_response(ctx: typer.Context, response: str,
                            approved: Annotated[bool, typer.Option(help="Require the revised manuscript's scientific author approval.")] = False):
    ws = workspace(ctx)
    report = revisions.verify_response(ws, ws.get("revision_response", response, revisions.ResponseBuild), require_approved=approved)
    output(report)
    if not report["passed"] or not report["ready"]:
        raise typer.Exit(1)


@revision_submission_app.command("prepare")
@handled
def prepare_revision_submission(ctx: typer.Context, revision: str,
                                settings: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
                                response: Annotated[str | None, typer.Option()] = None,
                                policy: Annotated[str | None, typer.Option(help="Explicitly reviewed updated policy for the same journal.")] = None,
                                pandoc: Annotated[str | None, typer.Option()] = None):
    ws = workspace(ctx)
    selected = ws.get("revision_response", response, revisions.ResponseBuild) if response else None
    reviewed = ws.get("policy", policy, venue_policy.VenuePolicy) if policy else None
    typer.echo("Network boundary: official policy pages are fetched again for the revised local package.", err=True)
    record, root = revision_submission.prepare(ws, ws.get("revision", revision, revisions.Revision), settings, response=selected, policy=reviewed, pandoc=pandoc)
    output({"delivery": record.model_dump(mode="json"), "directory": str(root),
            "revision_portal_requirements_verified": False, "external_submission_performed": False})


@revision_submission_app.command("attestation")
@handled
def init_revision_attestation(ctx: typer.Context, delivery: str,
                             path: Annotated[Path | None, typer.Option("--output")] = None):
    ws = workspace(ctx)
    record = ws.get("revision_delivery", delivery, revision_submission.RevisionDelivery)
    candidate = ws.get("submission", record.candidate_id, Submission)
    paper = ws.get("paper", record.revised_paper_id, Paper)
    destination = editable_destination(ws, path or ws.root / "attestations" / f"{record.id}.json")
    write_json(destination, attestation_template(ws, candidate, paper))
    output({"attestation": str(destination), "notice": "Review the revised manuscript, responses and all six facts. Actual portal requirements still need verification."})


@revision_submission_app.command("attest")
@handled
def attest_revision_submission(ctx: typer.Context, delivery: str,
                               path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
                               approve: Annotated[bool, typer.Option("--approve")] = False):
    if not approve:
        raise ValueError("Revised author attestation requires explicit --approve after reviewing the revised package and facts")
    ws = workspace(ctx)
    typer.echo("Network boundary: official policies are fetched again; no manuscript is uploaded.", err=True)
    record = revision_submission.attest(ws, ws.get("revision_delivery", delivery, revision_submission.RevisionDelivery), read_record_input(path, publication.AttestationInput))
    output({"attestation": record.model_dump(mode="json"), "external_submission_performed": False})


@revision_submission_app.command("record")
@handled
def record_revision_submission(ctx: typer.Context, delivery: str,
                               path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
                               evidence: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
                               confirm: Annotated[bool, typer.Option("--confirm")] = False):
    if not confirm:
        raise ValueError("Recording resubmission requires explicit --confirm after reviewing the actual journal receipt")
    ws = workspace(ctx)
    record = revision_submission.record(ws, ws.get("revision_delivery", delivery, revision_submission.RevisionDelivery), read_record_input(path, publication.ReceiptInput), evidence)
    output({"event": record.model_dump(mode="json"), "external_submission_performed": False})


@revision_submission_app.command("check")
@handled
def check_revision_submission(ctx: typer.Context, delivery: str):
    ws = workspace(ctx)
    report = revision_submission.check(ws, ws.get("revision_delivery", delivery, revision_submission.RevisionDelivery))
    output(report)
    if not report["passed"]:
        raise typer.Exit(1)




@portal_app.command("schema")
def portal_schema():
    output(portal.PortalSettings.model_json_schema())


@portal_app.command("settings")
@handled
def portal_settings(ctx: typer.Context, submission: str,
                    api_url: Annotated[str, typer.Option(help="Actual reviewed journal HTTPS /api/v1 endpoint.")],
                    section: Annotated[int, typer.Option(min=1, help="Actual OJS section ID.")],
                    locale: Annotated[str, typer.Option(help="Actual journal submission locale, e.g. en.")],
                    genre: Annotated[int, typer.Option(min=1, help="Actual manuscript genre ID; inspect its reviewer visibility.")],
                    remote: Annotated[int | None, typer.Option(min=1, help="Existing draft ID instead of creating a new draft.")] = None,
                    path: Annotated[Path | None, typer.Option("--output")] = None):
    ws = workspace(ctx)
    record = ws.get("submission", submission, Submission)
    package_root = ws.path(f"submissions/{record.id}/package")
    readme = json.loads((package_root / "package-readme.json").read_bytes())
    manuscripts = readme["accepted_manuscript_files"]
    if not manuscripts:
        raise ValueError("Ready package has no accepted manuscript format")
    values = portal.PortalSettings(connection=portal.OJSSettings(api_url=api_url),
        draft=portal.OJSDraft(sectionId=section, locale=locale),
        uploads=[portal.Upload(path=manuscripts[0], genre_id=genre)], remote_submission_id=remote)
    destination = editable_destination(ws, path or ws.root / "portal-settings" / f"{record.id}.json")
    write_json(destination, values)
    output({"settings": str(destination), "notice": "Review the actual journal version, context, section, locale and reviewer genre. No credentials or uploads are written."})


@portal_app.command("prepare")
@handled
def prepare_portal(ctx: typer.Context, submission: str,
                   path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]):
    ws = workspace(ctx)
    ensure_unlinked(path)
    plan = portal.prepare(ws, ws.get("submission", submission, Submission),
        portal.PortalSettings.model_validate_json(path.read_bytes()))
    output({"plan": plan.model_dump(mode="json"), "external_upload_performed": False,
        "next": f"paperfactory submission portal upload {plan.id} --upload"})


@portal_app.command("upload")
@handled
def upload_portal(ctx: typer.Context, plan: str,
                  upload: Annotated[bool, typer.Option("--upload", help="Authorize sending reviewed files and metadata to the actual journal.")] = False):
    if not upload:
        raise ValueError("Remote draft creation and upload require explicit --upload")
    ws = workspace(ctx)
    record = ws.get("portal_plan", plan, portal.StoredPlan)
    with portal.client_from_environment(record) as client:
        output(portal.connect(ws, record, client, upload=upload))


@portal_app.command("inspect")
@handled
def inspect_portal(ctx: typer.Context, plan: str):
    ws = workspace(ctx)
    record = ws.get("portal_plan", plan, portal.StoredPlan)
    with portal.client_from_environment(record) as client:
        output(portal.inspect(ws, record, client))


@portal_app.command("submit")
@handled
def submit_portal(ctx: typer.Context, plan: str,
                  attestation: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
                  review_sha256: Annotated[str, typer.Option(help="Exact hash of the remote snapshot you inspected.")],
                  approve: Annotated[bool, typer.Option("--approve", help="Confirm all six factual author declarations and the inspected journal material.")] = False,
                  submit: Annotated[bool, typer.Option("--submit", help="Perform the actual journal's final Submit.")] = False,
                  confirm_copyright: Annotated[bool, typer.Option("--confirm-copyright", help="Explicitly accept this journal's reviewed copyright terms.")] = False):
    if not approve or not submit:
        raise ValueError("Actual final submission requires both --approve and --submit after factual and remote review")
    ws = workspace(ctx)
    ensure_unlinked(attestation)
    record = ws.get("portal_plan", plan, portal.StoredPlan)
    values = publication.AttestationInput.model_validate_json(attestation.read_bytes())
    with portal.client_from_environment(record) as client:
        output(portal.submit(ws, record, client, values, review_sha256=review_sha256,
            approve=approve, final_submit=submit, confirm_copyright=confirm_copyright))


@portal_app.command("reconcile")
@handled
def reconcile_portal(ctx: typer.Context, plan: str,
                     actor: Annotated[str, typer.Option(help="Approved author's actual identity.")],
                     remote: Annotated[int | None, typer.Option(min=1, help="Explicitly inspected draft ID after uncertain creation.")] = None,
                     confirm: Annotated[bool, typer.Option("--confirm", help="Confirm a remote draft or preserved local recovery evidence.")] = False,
                     recover_local: Annotated[bool, typer.Option("--recover-local", help="Import verified preserved event evidence after a failed local database acknowledgement; requires --confirm.")] = False):
    if recover_local and not confirm:
        raise ValueError("Local delivery event recovery requires --confirm after reviewing the preserved evidence")
    ws = workspace(ctx)
    record = ws.get("portal_plan", plan, portal.StoredPlan)
    with portal.client_from_environment(record) as client:
        output(portal.reconcile(ws, record, client, actor=actor, remote_submission_id=remote,
            confirm=confirm, recover_local=recover_local))


@portal_app.command("check")
@handled
def check_portal(ctx: typer.Context, plan: str):
    ws = workspace(ctx)
    report = portal.check(ws, ws.get("portal_plan", plan, portal.StoredPlan))
    output(report)
    if not report["passed"]:
        raise typer.Exit(1)


@app.command("serve")
@handled
def serve_web(
    host: Annotated[str, typer.Option(help="Loopback address for the local research workspace.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(min=1, max=65535, help="Local HTTP server port.")] = 8765,
    studies: Annotated[Path | None, typer.Option(help="Directory containing study artifacts and manifests.")] = None,
    data: Annotated[Path | None, typer.Option(help="Directory for web projects and persistent jobs.")] = None,
    source_root: Annotated[list[Path] | None, typer.Option("--source-root", help="Allowed local import directory; repeat to allow several roots. Defaults to your home directory.")] = None,
):
    """Open the research workspace, run experiments and review paper artifacts."""
    from . import web
    from .workspace import pf_home

    studies_root = studies or pf_home() / "studies"
    data_root = data or pf_home() / "web"
    typer.echo(f"Paper Factory research workspace: {host}, port {port}")
    web.serve(host=host, port=port, studies_root=studies_root, data_root=data_root, source_roots=source_root)


if __name__ == "__main__":
    app()

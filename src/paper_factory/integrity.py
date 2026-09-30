"""Independent review and explicit, content-bound scientific freeze."""

import json
import shutil
import stat
import tempfile
from pathlib import Path

from .author import load_author
from .evidence import study_readiness_errors
from .experiments import safe_relative
from .literature import _SearchRecord, verify_search
from .manuscript import Document, render, validate_document
from .models import Claim, Citation, ExperimentManifest, ExperimentRun, Paper, PaperState, Project, Provenance, Study, now, transition_paper
from .workspace import Workspace, digest_file, write_json


def check(ws: Workspace, paper: Paper) -> dict:
    with ws.lock(f"paper-{paper.id}"):
        return _check(ws, paper)


def _check(ws: Workspace, paper: Paper) -> dict:
    paper = ws.get("paper", paper.id, Paper)
    if paper.state == PaperState.AUTHOR_APPROVED:
        report = check_frozen(ws, paper)
        write_json(ws.root / "reports" / f"{paper.id}-integrity.json", report)
        return report
    root = ws.root / "manuscripts" / paper.id
    problems: list[str] = []
    warnings: list[str] = []
    doc: Document | None = None
    try:
        allowed_files = {"canonical.json", "manuscript.md", "author.json", "paper.json", "compile-report.json", "compile-command.json", "manuscript.tex", "manuscript.pdf", "manuscript.typ", "manuscript-pandoc-metadata.json"}
        for path in root.rglob("*"):
            safe_relative(root, path.relative_to(root).as_posix())
            if path.is_file() and path.name not in allowed_files or path.is_dir():
                problems.append("Unexpected manuscript artifact; move extra files outside the canonical output directory")
        for name in ("canonical.json", "manuscript.md", "author.json", "compile-report.json", "compile-command.json"):
            safe_relative(root, name)
        doc = Document.model_validate_json((root / "canonical.json").read_text(encoding="utf-8"))
        if json.loads((root / "author.json").read_text(encoding="utf-8")) != doc.author:
            problems.append("Author metadata sidecar differs from canonical author")
        if doc.paper_id != paper.id or doc.study_id != paper.study_id or doc.title != paper.title:
            problems.append("Canonical identity differs from Paper record")
        problems.extend(validate_document(ws, doc))
        if digest_file(root / "canonical.json") != paper.document_sha256:
            problems.append("Canonical document changed after build; rebuild before review")
        manuscript = (root / "manuscript.md").read_text(encoding="utf-8")
        if digest_file(root / "manuscript.md") != paper.manuscript_sha256:
            problems.append("Rendered manuscript changed after build")
        if not problems and render(ws, doc) != manuscript:
            problems.append("Rendered manuscript differs from canonical evidence and references")
        doc_claims = {block.ref for section in doc.sections for block in section.blocks if block.kind == "claim"}
        doc_citations = {block.ref for section in doc.sections for block in section.blocks if block.kind == "citation"}
        if doc_claims != set(paper.claim_ids) or doc_citations != set(paper.citation_ids):
            problems.append("Paper claim/reference registry differs from canonical manuscript")
        compile_report = json.loads((root / "compile-report.json").read_text(encoding="utf-8"))
        if compile_report.get("status") not in {"FAILED", "COMPILED", "COMPILE_READY"}:
            problems.append("Unknown compiler status")
        if compile_report.get("input_sha256") != paper.manuscript_sha256 or compile_report.get("document_sha256") != paper.document_sha256:
            problems.append("Compile report does not match canonical input")
        if compile_report["status"] == "FAILED":
            problems.append("Manuscript compiler reported failure")
        if compile_report["status"] == "COMPILED":
            if compile_report.get("output") not in {"manuscript.pdf", "manuscript.tex"}:
                raise ValueError("Compile report does not identify a supported output artifact")
            output = root / compile_report["output"]
            if digest_file(output) != compile_report["sha256"]:
                problems.append("Compiled artifact changed after build")
        else:
            warnings.append("Pandoc not available; source and compile command are prepared, PDF/TeX output unverified")
        try:
            load_author(project_metadata=doc.author, environ={}, require=True)
        except ValueError as exc:
            warnings.append(f"Author metadata incomplete: {exc}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        problems.append(str(exc))
    study = ws.get("study", paper.study_id, Study)
    experiment_issues = study_readiness_errors(ws, study.id)
    warnings.extend(experiment_issues)
    for search_id in study.literature_search_ids:
        problems.extend(verify_search(ws, search_id, study.id))
    if not study.literature_search_ids:
        warnings.append("Literature search not performed; novelty remains unassessed")
    if study.novelty_status != "author_assessed":
        warnings.append("Author scientific assessment of related work/novelty is pending")
    warnings.append("PASS checks evidence/metadata consistency; it does not certify scientific merit or venue readiness")
    report = {"paper_id": paper.id, "checked_at": now(), "passed": not problems, "errors": sorted(set(problems)), "warnings": warnings,
              "experiment_review": {"ready": not experiment_issues, "issues": experiment_issues},
              "claim_count": len(paper.claim_ids), "verified_reference_count": len(paper.citation_ids), "manuscript_sha256": paper.manuscript_sha256, "document_sha256": paper.document_sha256}
    write_json(ws.root / "reports" / f"{paper.id}-integrity.json", report)
    if paper.state != PaperState.AUTHOR_APPROVED:
        if report["passed"] and paper.state == PaperState.MANUSCRIPT_DRAFTED:
            transition_paper(paper, PaperState.INTEGRITY_CHECKED)
            ws.save("paper", paper)
        elif not report["passed"] and paper.state == PaperState.INTEGRITY_CHECKED:
            transition_paper(paper, PaperState.MANUSCRIPT_DRAFTED)
            ws.save("paper", paper)
    return report


class FrozenWorkspace(Workspace):
    """Read-only record/artifact view consumed by the existing validators."""

    is_frozen = True

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.records = json.loads(safe_relative(self.root, "records.json").read_text(encoding="utf-8"))
        if not isinstance(self.records, dict):
            raise ValueError("Frozen record registry must be an object")

    def get(self, kind, id, model):
        try:
            return model.model_validate(self.records[kind][id])
        except KeyError as exc:
            raise ValueError(f"Unknown frozen {kind}: {id}") from exc

    def list(self, kind, model):
        return [model.model_validate(record) for record in self.records.get(kind, {}).values()]

    def save(self, kind, record):
        raise ValueError("Frozen scientific records are read-only")

    def path(self, relative):
        return safe_relative(self.root, relative)


def verify_freeze(ws: Workspace, paper: Paper) -> list[str]:
    errors: list[str] = []
    try:
        root = safe_relative(ws.root, f"freezes/{paper.id}")
        approval_path = safe_relative(root, "approval.json")
        if digest_file(approval_path) != paper.freeze_digest:
            errors.append("Frozen author approval changed")
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        expected = {"paper_id": paper.id, "study_id": paper.study_id, "title": paper.title,
                    "manuscript_sha256": paper.manuscript_sha256, "document_sha256": paper.document_sha256,
                    "approved_at": paper.approved_at, "approved_by": paper.approved_by}
        if approval.get("scientific_responsibility_accepted") is not True or any(approval.get(key) != value for key, value in expected.items()):
            errors.append("Frozen author attestation differs from Paper")
        files = approval["files"]
        if not isinstance(files, dict) or not files:
            raise ValueError("Frozen file manifest is missing")
        for path in root.rglob("*"):
            safe_relative(root, path.relative_to(root).as_posix())
        actual_files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()} - {"approval.json"}
        if set(files) != actual_files:
            errors.append("Frozen candidate file set changed")
        for relative, expected in files.items():
            if digest_file(safe_relative(root, relative)) != expected:
                errors.append(f"Frozen candidate changed: {relative}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"Frozen candidate invalid: {exc}")
    return errors


def _check_snapshot(snapshot: FrozenWorkspace, paper: Paper) -> list[str]:
    root = snapshot.root
    errors: list[str] = []
    try:
        doc = Document.model_validate_json((root / "canonical.json").read_text(encoding="utf-8"))
        if doc.paper_id != paper.id or doc.study_id != paper.study_id or doc.title != paper.title:
            errors.append("Frozen canonical identity differs from Paper")
        if digest_file(root / "canonical.json") != paper.document_sha256 or digest_file(root / "manuscript.md") != paper.manuscript_sha256:
            errors.append("Frozen scientific content differs from approved Paper hashes")
        if json.loads((root / "author.json").read_text(encoding="utf-8")) != doc.author:
            errors.append("Frozen author sidecar differs from canonical author")
        profile = load_author(project_metadata=doc.author, environ={}, require=True)
        if paper.approved_by and paper.approved_by != profile.display_name:
            errors.append("Frozen author differs from approval identity")
        doc_claims = {block.ref for section in doc.sections for block in section.blocks if block.kind == "claim"}
        doc_citations = {block.ref for section in doc.sections for block in section.blocks if block.kind == "citation"}
        if doc_claims != set(paper.claim_ids) or doc_citations != set(paper.citation_ids):
            errors.append("Frozen paper claim/reference registry differs from manuscript")
        errors.extend(validate_document(snapshot, doc))
        if not errors and render(snapshot, doc) != (root / "manuscript.md").read_text(encoding="utf-8"):
            errors.append("Frozen rendered manuscript differs from canonical evidence")
        study = snapshot.get("study", paper.study_id, Study)
        if not study.literature_search_ids:
            errors.append("Frozen study has no literature search")
        for search_id in study.literature_search_ids:
            errors.extend(verify_search(snapshot, search_id, study.id))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"Frozen scientific evidence invalid: {exc}")
    return sorted(set(errors))


def check_frozen(ws: Workspace, paper: Paper) -> dict:
    """Independently check the approved science without mutable live records."""
    errors = verify_freeze(ws, paper)
    experiment_issues: list[str] = []
    if not errors:
        try:
            snapshot = FrozenWorkspace(ws.root / "freezes" / paper.id)
            errors.extend(_check_snapshot(snapshot, paper))
            experiment_issues = study_readiness_errors(snapshot, paper.study_id)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"Frozen scientific evidence invalid: {exc}")
    return {"paper_id": paper.id, "checked_at": now(), "passed": not errors,
            "errors": sorted(set(errors)), "warnings": [*experiment_issues, "Frozen evidence is consistent; this does not certify scientific merit or venue readiness"],
            "experiment_review": {"ready": not experiment_issues, "issues": experiment_issues},
            "claim_count": len(paper.claim_ids), "verified_reference_count": len(paper.citation_ids),
            "manuscript_sha256": paper.manuscript_sha256, "document_sha256": paper.document_sha256}


def frozen_workspace(ws: Workspace, paper: Paper) -> FrozenWorkspace:
    """Return verified, immutable scientific inputs for venue compilation."""
    current = ws.get("paper", paper.id, Paper)
    if current.state != PaperState.AUTHOR_APPROVED:
        raise ValueError("Scientific author approval is required before venue compilation")
    report = check_frozen(ws, current)
    if not report["passed"]:
        raise ValueError("Frozen scientific evidence failed verification: " + "; ".join(report["errors"]))
    return FrozenWorkspace(ws.root / "freezes" / current.id)


def _remove_staging(root: Path) -> None:
    """Imported source files can be read-only on Windows."""
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            path.chmod(stat.S_IREAD | stat.S_IWRITE)
    shutil.rmtree(root)


def approve(ws: Workspace, paper: Paper, approved: bool, assessment: str, author_values: dict | None = None) -> Path:
    if not approved:
        raise ValueError("Explicit author approval required: pass --approve")
    current = ws.get("paper", paper.id, Paper)
    with ws.lock(f"paper-{paper.id}"), ws.lock(f"study-{current.study_id}"):
        return _approve(ws, paper, assessment, author_values)


def _approve(ws: Workspace, paper: Paper, assessment: str, author_values: dict | None) -> Path:
    destination = ws.root / "freezes" / paper.id
    staging: Path | None = None
    published = False
    try:
        current = ws.get("paper", paper.id, Paper)
        if current.state == PaperState.AUTHOR_APPROVED:
            raise ValueError("Paper already approved and frozen")
        from .revisions import assert_editable
        assert_editable(ws, current)
        if destination.exists():
            raise ValueError("A freeze snapshot already exists; will not overwrite it")
        report = _check(ws, current)
        if not report["passed"]:
            raise ValueError("Scientific freeze blocked by integrity errors")
        current = ws.get("paper", current.id, Paper)
        study = ws.get("study", current.study_id, Study)
        if any(run.study_id == study.id and run.status == "RUNNING" for run in ws.list("run", ExperimentRun)):
            raise ValueError("Scientific freeze blocked by an incomplete experiment attempt; complete or retry the experiment first")
        if not study.literature_search_ids:
            raise ValueError("Scientific freeze requires a recorded literature search")
        if not assessment.strip():
            raise ValueError("Scientific freeze requires an author's related-work/limitations assessment")
        profile = load_author(explicit=author_values, require=True)
        source = safe_relative(ws.root, f"manuscripts/{current.id}")
        doc = Document.model_validate_json((source / "canonical.json").read_text(encoding="utf-8"))
        if doc.author != profile.model_dump():
            raise ValueError("Author profile differs from built manuscript; rebuild with current author environment")
        staging = Path(tempfile.mkdtemp(prefix=f".{paper.id}-", dir=destination.parent))
        shutil.copytree(source, staging, dirs_exist_ok=True)
        records: dict[str, dict[str, dict]] = {}

        def pin(kind, record):
            records.setdefault(kind, {})[record.id] = record.model_dump(mode="json")

        def copy(relative):
            target = safe_relative(staging, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(safe_relative(ws.root, relative), target)

        pin("project", ws.get("project", study.project_id, Project))
        pin("study", study)
        for activity in ws.list("provenance", Provenance):
            if activity.id in {entry["id"] for entry in doc.ai_provenance}:
                pin("provenance", activity)
        claims = [ws.get("claim", id, Claim) for id in current.claim_ids]
        for claim in claims:
            pin("claim", claim)
        for path in (ws.root / "source").rglob("*"):
            safe_relative(ws.root, path.relative_to(ws.root).as_posix())
        shutil.copytree(ws.root / "source", staging / "source")
        claimed_runs = {claim.run_id for claim in claims}
        audit_notes: list[str] = []
        # Preserve the order used to identify each manifest's latest attempt.
        for run in ws.list("run", ExperimentRun):
            if run.study_id != study.id:
                continue
            run_id = run.id
            pin("run", run)
            pin("manifest", ws.get("manifest", run.experiment_id, ExperimentManifest))
            if run_id in claimed_runs:
                for relative in [asset.path for asset in run.artifacts] + [f"runs/{run_id}/processed.json", f"runs/{run_id}/run.json"]:
                    copy(relative)
            else:
                write_json(safe_relative(staging, f"runs/{run_id}/run.json"), run)
                for name in ("manifest.json", "provenance.json", "stdout.log", "stderr.log"):
                    relative = f"runs/{run_id}/{name}"
                    try:
                        copy(relative)
                    except (OSError, ValueError) as exc:
                        audit_notes.append(f"Unclaimed attempt audit artifact could not be copied: {relative}: {exc}")
        if audit_notes:
            write_json(staging / "experiment-audit-notes.json", audit_notes)
        # Searches can resolve citations that the author omitted from prose.
        for id in study.citation_ids:
            pin("citation", ws.get("citation", id, Citation))
            copy(f"literature/{id}.json")
        for id in study.literature_search_ids:
            pin("search", ws.get("search", id, _SearchRecord))
            copy(f"literature/{id}.json")
            copy(f"literature/{id}-response.json")
        write_json(staging / "records.json", records)
        snapshot_errors = _check_snapshot(FrozenWorkspace(staging), current)
        if snapshot_errors:
            raise ValueError("Scientific freeze changed during copying: " + "; ".join(snapshot_errors))
        if ws.get("paper", current.id, Paper) != current:
            raise ValueError("Paper changed while preparing scientific freeze")
        approved_at = now()
        current.approved_at = approved_at
        current.approved_by = profile.display_name
        transition_paper(current, PaperState.AUTHOR_APPROVED)
        freeze_files = {p.relative_to(staging).as_posix(): digest_file(p) for p in staging.rglob("*") if p.is_file()}
        approval = {"paper_id": current.id, "study_id": current.study_id, "title": current.title,
                    "manuscript_sha256": current.manuscript_sha256, "document_sha256": current.document_sha256,
                    "approved_at": approved_at, "approved_by": profile.display_name, "assessment": assessment.strip(),
                    "scientific_responsibility_accepted": True, "files": freeze_files, "integrity": report}
        write_json(staging / "approval.json", approval)
        current.freeze_digest = digest_file(staging / "approval.json")
        ws.rename_artifact(staging, destination)
        staging = None
        published = True
        study.novelty_status = "author_assessed"
        activity = Provenance(role="scientific author approval", tool="paperfactory explicit author gate", inputs=[current.id, current.manuscript_sha256], outputs=[str(destination.relative_to(ws.root))])
        # The record gate and its assessment commit together.
        with ws._database() as db:
            for kind, record in (("paper", current), ("study", study), ("provenance", activity)):
                db.execute("INSERT INTO records VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data", (kind, record.id, record.model_dump_json()))
        paper.state = current.state
        paper.approved_at = current.approved_at
        paper.approved_by = current.approved_by
        paper.freeze_digest = current.freeze_digest
        return destination
    except BaseException:
        if published:
            _remove_staging(destination)
        raise
    finally:
        if staging is not None:
            _remove_staging(staging)

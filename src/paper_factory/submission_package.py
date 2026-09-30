"""Local, verified submission archives. Never contact a submission system."""

import json
import shutil
import tempfile
import zipfile
from pathlib import Path

import httpx

from .models import Record, Submission, SubmissionState, now, transition_submission, uid
from .venue_compiler import Compilation, policy_fingerprint, verify_compilation
from .venue_policy import VenuePolicy, refresh_policy, validate_policy
from .workspace import Workspace, digest_file, write_json


class Package(Record):
    id: str
    submission_id: str
    policy_id: str
    compilation_digest: str
    ready: bool
    errors: list[str]
    warnings: list[str]
    files: dict[str, str]
    archive_sha256: str
    manifest_sha256: str
    built_at: str


def build(ws: Workspace, submission: Submission, *, client: httpx.Client | None = None) -> tuple[Package, Path]:
    with ws.lock(f"submission-{submission.id}"):
        submission = ws.get("submission", submission.id, Submission)
        if submission.state != SubmissionState.VENUE_COMPILED:
            raise ValueError("Package requires a compiled candidate; ready packages are immutable")
        errors = verify_compilation(ws, submission, check_compliance=False)
        if errors:
            raise ValueError("Package blocked by corrupted compilation: " + "; ".join(errors))
        compilation = ws.get("compilation", submission.id, Compilation)
        original = ws.get("policy", compilation.policy_id, VenuePolicy)
        # TTL alone cannot establish current submission-time rules. Always refetch.
        current = refresh_policy(ws, original, client=client)
        errors = list(compilation.errors) + validate_policy(ws, current)
        if policy_fingerprint(current) != policy_fingerprint(original):
            errors.append("Official policy content changed after compilation; reselect and recompile before readiness")
        ready = not errors
        source = ws.path(f"submissions/{submission.id}/compiled")
        destination = ws.path(f"submissions/{submission.id}/package")
        if destination.exists():
            raise ValueError("Package already exists; select a new candidate for a new package")
        stage = Path(tempfile.mkdtemp(prefix=".packaging-", dir=destination.parent))
        published = False
        try:
            # Administrative files are intentionally separate from blinded review files.
            for relative in compilation.files:
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ws.path(f"submissions/{submission.id}/compiled/{relative}"), target)
                if digest_file(target) != compilation.files[relative]:
                    raise ValueError(f"Compilation changed during packaging: {relative}")
            write_json(stage / "compliance.json", {"ready": ready, "errors": list(dict.fromkeys(errors)), "warnings": compilation.warnings, "policy_verified_at": current.verified_at, "policy_id": current.id, "canonical_digest": compilation.canonical_digest, "final_author_attestation_required": True, "external_submission_performed": False})
            write_json(stage / "current-policy.json", current)
            # Include captured official evidence so package decisions can be audited.
            (stage / "policy-evidence").mkdir()
            for index, policy_source in enumerate(current.sources):
                if policy_source.raw_path:
                    target = stage / "policy-evidence" / f"{index}{Path(policy_source.raw_path).suffix}"
                    shutil.copyfile(ws.path(policy_source.raw_path), target)
                    if digest_file(target) != policy_source.raw_sha256:
                        raise ValueError("Official policy evidence changed during packaging")
                if policy_source.text_path:
                    target = stage / "policy-evidence" / f"{index}.readable.txt"
                    shutil.copyfile(ws.path(policy_source.text_path), target)
                    if digest_file(target) != policy_source.text_sha256:
                        raise ValueError("Readable policy evidence changed during packaging")
            supported = [f"manuscript.{suffix}" for suffix in ("pdf", "docx", "tex") if suffix in (current.values.accepted_formats or [])]
            write_json(stage / "package-readme.json", {"manuscript": supported[0] if supported else None, "accepted_manuscript_files": supported, "administrative_files": ["author.json", "metadata.json", "cover-letter.md", "declarations.json"], "reviewer_files": [*supported, "tables/results.csv"], "source": "source.zip", "supplement": "supplement/evidence-map.json", "warning": "Do not upload this whole archive as a blinded-review document. Author metadata and cover letter are administrative files. The evidence-map supplement is an administrative audit artifact; review its identifying labels before any public release. Final attestations and any data-release permission remain the author's responsibility."})
            with zipfile.ZipFile(stage / "source.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name in ("manuscript.md", "manuscript.tex", "manuscript.typ", "references.json", "references.csl"):
                    path = stage / name
                    if path.is_file():
                        archive.write(path, name)
            files = {path.relative_to(stage).as_posix(): digest_file(path) for path in stage.rglob("*") if path.is_file()}
            manifest = {"submission_id": submission.id, "ready": ready, "files": files, "built_at": now(), "canonical_digest": submission.candidate_digest, "policy_id": current.id}
            write_json(stage / "manifest.json", manifest)
            with zipfile.ZipFile(stage / "submission.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for relative in [*sorted(files), "manifest.json"]:
                    archive.write(stage / relative, relative)
            package = Package(id=submission.id, submission_id=submission.id, policy_id=current.id, compilation_digest=submission.compilation_digest, ready=ready, errors=list(dict.fromkeys(errors)), warnings=compilation.warnings, files=files, archive_sha256=digest_file(stage / "submission.zip"), manifest_sha256=digest_file(stage / "manifest.json"), built_at=manifest["built_at"])
            ws.rename_artifact(stage, destination)
            published = True
            submission.policy_id = current.id
            submission.package_digest = package.manifest_sha256
            if ready:
                transition_submission(submission, SubmissionState.SUBMISSION_READY)
            with ws._database() as db:
                for kind, record in (("package", package), ("submission", submission)):
                    db.execute("INSERT INTO records VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data", (kind, record.id, record.model_dump_json()))
            return package, destination
        except Exception as exc:
            if published:
                shutil.rmtree(destination)
            elif stage.exists():
                write_json(stage / "failure.json", {"error": str(exc), "failed_at": now(), "submission_id": submission.id})
                ws.rename_artifact(stage, destination.parent / uid("failed-package"))
            raise
        finally:
            if stage.exists():
                if not stage.resolve().is_relative_to(destination.parent.resolve()):
                    raise ValueError("Unexpected package staging path")
                shutil.rmtree(stage)


def verify(ws: Workspace, submission: Submission, *, fresh: bool = True) -> dict:
    submission = ws.get("submission", submission.id, Submission)
    errors = verify_compilation(ws, submission)
    try:
        package = ws.get("package", submission.id, Package)
        if package.id != submission.id or package.submission_id != submission.id or package.compilation_digest != submission.compilation_digest or package.policy_id != submission.policy_id:
            errors.append("Package identity/policy/compilation binding differs")
        preparation_states = {SubmissionState.VENUE_SELECTED, SubmissionState.VENUE_COMPILED}
        if package.ready != (submission.state not in preparation_states):
            errors.append("Package readiness differs from submission state")
        root = ws.path(f"submissions/{submission.id}/package")
        if digest_file(root / "manifest.json") != package.manifest_sha256 or submission.package_digest != package.manifest_sha256:
            errors.append("Package manifest changed")
        manifest = json.loads((root / "manifest.json").read_bytes())
        if manifest["submission_id"] != submission.id or manifest["policy_id"] != package.policy_id or manifest["built_at"] != package.built_at or manifest["files"] != package.files or manifest["ready"] != package.ready or manifest["canonical_digest"] != submission.candidate_digest:
            errors.append("Package manifest identity/content differs")
        actual_files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()} - {"manifest.json", "submission.zip"}
        if actual_files != set(package.files):
            errors.append("Package file set changed")
        for relative, expected in package.files.items():
            if digest_file(ws.path(f"submissions/{submission.id}/package/{relative}")) != expected:
                errors.append(f"Package artifact changed: {relative}")
        compilation = ws.get("compilation", submission.id, Compilation)
        for relative, expected in compilation.files.items():
            if package.files.get(relative) != expected:
                errors.append(f"Package differs from its verified compilation: {relative}")
        if digest_file(root / "submission.zip") != package.archive_sha256:
            errors.append("Submission archive changed")
        with zipfile.ZipFile(root / "submission.zip") as archive:
            if set(archive.namelist()) != {*package.files, "manifest.json"} or len(archive.namelist()) != len(package.files) + 1:
                errors.append("Submission archive file set differs")
            for relative, expected in {**package.files, "manifest.json": package.manifest_sha256}.items():
                import hashlib
                if hashlib.sha256(archive.read(relative)).hexdigest() != expected:
                    errors.append(f"Archived artifact differs: {relative}")
        current = ws.get("policy", package.policy_id, VenuePolicy)
        if json.loads((root / "current-policy.json").read_bytes()) != current.model_dump(mode="json"):
            errors.append("Packaged current policy differs from verified capture")
        for index, source in enumerate(current.sources):
            for relative, expected in ((f"policy-evidence/{index}{Path(source.raw_path).suffix}" if source.raw_path else None, source.raw_sha256), (f"policy-evidence/{index}.readable.txt" if source.text_path else None, source.text_sha256)):
                if relative and package.files.get(relative) != expected:
                    errors.append("Packaged policy evidence differs from its official capture")
        errors.extend(validate_policy(ws, current, fresh=fresh))
        if policy_fingerprint(current) != policy_fingerprint(ws.get("policy", compilation.policy_id, VenuePolicy)):
            errors.append("Official policy content changed after compilation; reselect and recompile before readiness")
        errors.extend(package.errors)
        return {"submission_id": submission.id, "passed": not errors, "ready": package.ready and not errors, "errors": list(dict.fromkeys(errors)), "warnings": package.warnings, "archive": str(root / "submission.zip"), "external_submission_performed": False}
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        return {"submission_id": submission.id, "passed": False, "ready": False, "errors": [*errors, str(exc)]}

"""Author-written, evidence-linked responses to actual journal referee reports.

Review observations and response builds are immutable artifacts. Revision drafts
use a new Paper identity; the submitted scientific freeze is never edited.
"""

import csv
from datetime import datetime
import difflib
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
from typing import Literal

from pydantic import Field, model_validator

from . import integrity, manuscript, publication
from .conversion import convert
from .evidence import verify_claim, _verify_run
from .manuscript import Block, Document
from .models import Claim, ExperimentManifest, ExperimentRun, Paper, PaperState, Record, Submission, SubmissionState, now, uid
from .workspace import Workspace, digest_file, ensure_unlinked, write_json


MAX_REPORT_BYTES = 20 * 1024 * 1024


class ReviewComment(Record):
    id: str
    excerpt: str = Field(min_length=1, max_length=100000)
    sections: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    experiment_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def linked(self):
        if not self.excerpt.strip() or not (self.sections or self.claim_ids or self.experiment_ids):
            raise ValueError("Each reviewer comment needs an exact excerpt and manuscript/evidence targets")
        return self


class ReviewSpec(Record):
    reviewed_by: str = Field(min_length=1)
    comments: list[ReviewComment] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique(self):
        if len({comment.id for comment in self.comments}) != len(self.comments):
            raise ValueError("Reviewer comment identifiers must be unique")
        return self


class ReviewData(Record):
    id: str = Field(default_factory=lambda: uid("revision"))
    base_submission_id: str
    base_paper_id: str
    study_id: str
    base_freeze_digest: str
    decision_event_id: str
    revised_paper_id: str = Field(default_factory=lambda: uid("paper"))
    reviewed_by: str
    received_at: str
    imported_at: str = Field(default_factory=now)
    report_name: str
    report_format: Literal["text", "pdf"]
    report_sha256: str
    spec_sha256: str
    text_sha256: str


class Revision(ReviewData):
    artifact_sha256: str


class SectionEdit(Record):
    section: str = Field(min_length=1)
    blocks: list[Block] = Field(min_length=1)


class CommentResponse(Record):
    comment_id: str
    disposition: Literal["pending", "accept", "partially_accept", "disagree"] = "pending"
    reply: str = ""
    justification: str = ""
    sections: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    experiment_ids: list[str] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)
    additional_experiments_required: bool = Field(strict=True)
    edits: list[SectionEdit] = Field(default_factory=list)


class ResponsePlan(Record):
    revision_id: str
    author: str
    responses: list[CommentResponse] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique(self):
        if len({response.comment_id for response in self.responses}) != len(self.responses):
            raise ValueError("Each reviewer comment must have exactly one response")
        edited = [edit.section for response in self.responses for edit in response.edits]
        if len(set(edited)) != len(edited):
            raise ValueError("A section may be replaced only once in a response plan")
        return self


class ResponseData(Record):
    id: str = Field(default_factory=lambda: uid("revision-response"))
    revision_id: str
    revised_paper_id: str
    document_sha256: str
    ready: bool
    errors: list[str]
    files: dict[str, str]
    created_at: str = Field(default_factory=now)


class ResponseBuild(ResponseData):
    artifact_sha256: str


def _read_bounded(path: Path) -> bytes:
    path = path.absolute()
    ensure_unlinked(path)
    with path.open("rb") as stream:
        content = stream.read(MAX_REPORT_BYTES + 1)
    if not content or len(content) > MAX_REPORT_BYTES:
        raise ValueError("Review inputs must be nonempty and at most 20 MiB")
    return content


def _report_text(raw: bytes, format: str) -> str:
    if format == "pdf":
        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise ValueError("Install the PDF extra to import a PDF referee report") from error
        try:
            reader = PdfReader(io.BytesIO(raw))
            if getattr(reader, "is_encrypted", False):
                raise ValueError("Encrypted referee reports must be decrypted by the author first")
            if len(reader.pages) > 500:
                raise ValueError("Referee report exceeds the 500-page extraction limit")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as error:
            raise ValueError(f"Referee PDF extraction failed: {error}") from error
    else:
        text = raw.decode("utf-8-sig")
    if not text.strip() or len(text.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError("Referee report has no extractable text or exceeds the text limit; provide an author-prepared text report")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _root(ws: Workspace, revision: Revision) -> Path:
    return ws.path(f"revisions/{revision.id}")


def response_root(ws: Workspace, response: ResponseBuild) -> Path:
    return ws.path(f"revisions/{response.revision_id}/responses/{response.id}")


def _registry(ws: Workspace) -> None:
    """A deleted DB row cannot hide a review or a completed response."""
    indexed = {revision.id for revision in ws.list("revision", Revision)}
    root = ws.path("revisions")
    actual = set()
    response_actual = set()
    if root.exists():
        for path in root.iterdir():
            path = ws.path(path.relative_to(ws.root).as_posix())
            if path.name.startswith(".revision-"):
                continue
            if not path.is_dir():
                raise ValueError("Revision journal contains an unexpected artifact")
            actual.add(path.name)
            responses = ws.path(f"revisions/{path.name}/responses")
            if responses.exists():
                for response in responses.iterdir():
                    response = ws.path(response.relative_to(ws.root).as_posix())
                    if response.name.startswith(".response-"):
                        continue
                    if not response.is_dir():
                        raise ValueError("Revision response journal contains an unexpected artifact")
                    response_actual.add((path.name, response.name))
    if actual != indexed:
        raise ValueError("Revision journal and record index differ; missing or orphaned review")
    response_indexed = {(item.revision_id, item.id) for item in ws.list("revision_response", ResponseBuild)}
    if response_actual != response_indexed:
        raise ValueError("Revision response journal and record index differ; missing or orphaned response")


def _reviewed_paper(ws: Workspace, submission: Submission, decision: publication.PublicationEvent) -> Paper:
    """Resolve the science actually resubmitted before this round's decision."""
    prior = [event for event in ws.list("publication_event", publication.PublicationEvent)
        if event.submission_id == submission.id and event.sequence < decision.sequence and event.kind == "revision_submission"]
    paper_id = submission.paper_id
    if prior:
        from .revision_submission import DeliveryData, RevisionDelivery
        event = max(prior, key=lambda item: item.sequence)
        delivery = ws.get("revision_delivery", event.values["delivery_id"], RevisionDelivery)
        manifest = ws.path(f"revision-deliveries/{delivery.id}/manifest.json")
        if delivery.state != "RESUBMITTED" or delivery.publication_event_id != event.id or delivery.original_submission_id != submission.id or digest_file(manifest) != delivery.manifest_sha256 or json.loads(manifest.read_bytes()) != delivery.model_dump(mode="json", include=set(DeliveryData.model_fields)):
            raise ValueError("Prior revised scientific delivery binding changed")
        if event.values.get("manifest_sha256") != delivery.manifest_sha256:
            raise ValueError("Prior resubmission event differs from its scientific delivery")
        paper_id = delivery.revised_paper_id
    paper = ws.get("paper", paper_id, Paper)
    original = ws.get("paper", submission.paper_id, Paper)
    if paper.study_id != original.study_id:
        raise ValueError("Review scientific lineage crossed Study identities")
    return paper


def _base(ws: Workspace, revision: Revision):
    submission = ws.get("submission", revision.base_submission_id, Submission)
    decision = ws.get("publication_event", revision.decision_event_id, publication.PublicationEvent)
    paper = _reviewed_paper(ws, submission, decision)
    if paper.id != revision.base_paper_id or paper.study_id != revision.study_id or paper.freeze_digest != revision.base_freeze_digest:
        raise ValueError("Revision submitted-paper/study/freeze binding differs")
    snapshot = integrity.frozen_workspace(ws, paper)
    doc = Document.model_validate_json(snapshot.path("canonical.json").read_bytes())
    return submission, paper, snapshot, doc


def _spec_errors(spec: ReviewSpec, text: str, doc: Document, snapshot) -> list[str]:
    headings = {section.heading for section in doc.sections}
    claims = {block.ref for section in doc.sections for block in section.blocks if block.kind == "claim"}
    experiments = {item.id for item in snapshot.list("manifest", ExperimentManifest) if item.study_id == doc.study_id}
    errors = []
    for comment in spec.comments:
        if comment.excerpt not in text:
            errors.append(f"Comment {comment.id}: excerpt is not present exactly in the actual referee report")
        if set(comment.sections) - headings or set(comment.claim_ids) - claims or set(comment.experiment_ids) - experiments:
            errors.append(f"Comment {comment.id}: target is absent from the submitted scientific freeze")
    return errors


def _active(ws: Workspace, revision: Revision) -> None:
    submission = ws.get("submission", revision.base_submission_id, Submission)
    report = publication.check(ws, submission)
    if not report["passed"]:
        raise ValueError("Publication history is invalid: " + "; ".join(report["errors"]))
    if report["state"] not in {SubmissionState.REVISION, SubmissionState.REJECTED} or not report["events"] or report["events"][-1]["id"] != revision.decision_event_id:
        raise ValueError("Revision preparation requires the current confirmed journal review decision (REVISION or REJECTED)")
    if report["state"] == SubmissionState.REJECTED and publication.active_for_study(ws, revision.study_id):
        raise ValueError("Rejected-feedback edits are blocked while another active peer-reviewed submission occupies this Study")


def assert_editable(ws: Workspace, paper: Paper) -> None:
    """Apply the rejected-feedback gate to the ordinary canonical edit path too."""
    if not ws.path("revisions").exists():
        return
    _registry(ws)
    for revision in ws.list("revision", Revision):
        if revision.revised_paper_id == paper.id:
            decision = ws.get("publication_event", revision.decision_event_id, publication.PublicationEvent)
            if decision.to_state == SubmissionState.REJECTED:
                problems = verify_review(ws, revision)
                if problems:
                    raise ValueError("Revision history is invalid: " + "; ".join(problems))
                _active(ws, revision)


def _validated_review(ws: Workspace, revision: Revision):
    """Return the local verified context for reuse within this one operation."""
    _registry(ws)
    if ws.get("revision", revision.id, Revision) != revision:
        raise ValueError("Revision differs from its indexed immutable observation")
    root = _root(ws, revision)
    expected = {"review.json", "spec.json", "report.bin", "report-text.txt"}
    actual = {path.name for path in root.iterdir() if path.name != "responses"}
    if actual != expected or any(not ws.path(path.relative_to(ws.root).as_posix()).is_file() for path in root.iterdir() if path.name in expected):
        raise ValueError("Immutable revision file set differs")
    data = root / "review.json"
    if digest_file(data) != revision.artifact_sha256 or json.loads(data.read_bytes()) != revision.model_dump(mode="json", exclude={"artifact_sha256"}):
        raise ValueError("Revision observation artifact changed")
    for filename, expected_hash in (("report.bin", revision.report_sha256), ("spec.json", revision.spec_sha256), ("report-text.txt", revision.text_sha256)):
        if digest_file(ws.path(f"revisions/{revision.id}/{filename}")) != expected_hash:
            raise ValueError(f"Revision input changed: {filename}")
    text = (root / "report-text.txt").read_text(encoding="utf-8")
    if _report_text(_read_bounded(root / "report.bin"), revision.report_format) != text:
        raise ValueError("Referee report text does not derive from its preserved raw report")
    spec = ReviewSpec.model_validate_json(_read_bounded(root / "spec.json"))
    _, paper, snapshot, doc = _base(ws, revision)
    if revision.reviewed_by != paper.approved_by or spec.reviewed_by != paper.approved_by:
        raise ValueError("Referee review must be confirmed by the approved named author")
    event = ws.get("publication_event", revision.decision_event_id, publication.PublicationEvent)
    path = ws.path(f"publication/{revision.base_submission_id}/{event.id}/event.json")
    if digest_file(path) != event.artifact_sha256 or json.loads(path.read_bytes()) != event.model_dump(mode="json", exclude={"artifact_sha256"}):
        raise ValueError("Revision decision artifact changed")
    submission = ws.get("submission", revision.base_submission_id, Submission)
    if event.kind != "receipt" or event.to_state not in {SubmissionState.REVISION, SubmissionState.REJECTED} or event.submission_id != revision.base_submission_id or event.paper_id != submission.paper_id or event.study_id != revision.study_id or event.actor != revision.reviewed_by or event.values.get("occurred_at") != revision.received_at:
        raise ValueError("Revision observation is not bound to its confirmed journal decision")
    evidence = ws.path(f"publication/{revision.base_submission_id}/{event.id}/evidence.bin")
    if not event.evidence_sha256 or digest_file(evidence) != event.evidence_sha256:
        raise ValueError("Revision decision evidence changed")
    errors = _spec_errors(spec, text, doc, snapshot)
    if errors:
        raise ValueError("; ".join(errors))
    return paper, snapshot, doc, spec


def verify_review(ws: Workspace, revision: Revision) -> list[str]:
    """Validate immutable observation without checking the current journal state."""
    try:
        _validated_review(ws, revision)
        return []
    except (ValueError, OSError, KeyError, TypeError, UnicodeError) as error:
        return [str(error)]


def import_review(ws: Workspace, submission: Submission, spec_path: Path, report_path: Path, confirmed: bool = False) -> tuple[Revision, Path]:
    if not confirmed:
        raise ValueError("Explicit author confirmation is required to import the actual referee report")
    spec_raw = _read_bounded(spec_path)
    report_raw = _read_bounded(report_path)
    spec = ReviewSpec.model_validate_json(spec_raw)
    format = "pdf" if report_path.suffix.casefold() == ".pdf" else "text"
    text = _report_text(report_raw, format)
    with ws.lock(f"revision-{submission.id}"):
        _registry(ws)
        current = ws.get("submission", submission.id, Submission)
        history = publication.check(ws, current)
        if not history["passed"]:
            raise ValueError("Publication history is invalid: " + "; ".join(history["errors"]))
        if current.state not in {SubmissionState.REVISION, SubmissionState.REJECTED} or not history["events"]:
            raise ValueError("Import requires a confirmed journal REVISION or REJECTED decision")
        decision = publication.PublicationEvent.model_validate(history["events"][-1])
        for record in ws.list("revision", Revision):
            if record.base_submission_id == current.id and record.decision_event_id == decision.id:
                raise ValueError("This confirmed decision already has an open revision")
            problems = verify_review(ws, record)
            if problems:
                raise ValueError("Existing revision history is invalid: " + "; ".join(problems))
        paper = _reviewed_paper(ws, current, decision)
        if not paper.approved_by or spec.reviewed_by != paper.approved_by:
            raise ValueError("Referee review must be confirmed by the approved named author")
        snapshot = integrity.frozen_workspace(ws, paper)
        doc = Document.model_validate_json(snapshot.path("canonical.json").read_bytes())
        problems = _spec_errors(spec, text, doc, snapshot)
        if problems:
            raise ValueError("Referee report rejected: " + "; ".join(problems))
        data = ReviewData(base_submission_id=current.id, base_paper_id=paper.id, study_id=paper.study_id,
            base_freeze_digest=paper.freeze_digest, decision_event_id=decision.id, reviewed_by=spec.reviewed_by,
            received_at=decision.values["occurred_at"], report_name=report_path.name, report_format=format,
            report_sha256=hashlib.sha256(report_raw).hexdigest(), spec_sha256=hashlib.sha256(spec_raw).hexdigest(),
            text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())
        parent = ws.path("revisions")
        parent.mkdir(exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".revision-", dir=parent))
        destination = ws.path(f"revisions/{data.id}")
        published = False
        try:
            (stage / "report.bin").write_bytes(report_raw)
            (stage / "spec.json").write_bytes(spec_raw)
            (stage / "report-text.txt").write_text(text, encoding="utf-8", newline="")
            write_json(stage / "review.json", data)
            revision = Revision(**data.model_dump(), artifact_sha256=digest_file(stage / "review.json"))
            with ws._database() as db:
                db.execute("BEGIN IMMEDIATE")
                _active(ws, revision)
                ws.rename_artifact(stage, destination)
                published = True
                db.execute("INSERT INTO records VALUES (?,?,?)", ("revision", revision.id, revision.model_dump_json()))
            return revision, destination
        except Exception:
            if published:
                ws.discard_uncommitted_artifact(destination, kind="revision",
                    record_id=revision.id, field="artifact_sha256",
                    expected_value=revision.artifact_sha256)
            raise
        finally:
            if stage.exists():
                shutil.rmtree(ws.path(stage.relative_to(ws.root).as_posix()))


def _child(ws: Workspace, revision: Revision):
    paper = ws.get("paper", revision.revised_paper_id, Paper)
    if paper.study_id != revision.study_id or paper.id == revision.base_paper_id:
        raise ValueError("Revised paper must be a distinct identity in the original Study")
    if paper.state == PaperState.AUTHOR_APPROVED:
        snapshot = integrity.frozen_workspace(ws, paper)
        path = snapshot.path("canonical.json")
        doc = Document.model_validate_json(path.read_bytes())
    else:
        snapshot = ws
        path = ws.path(f"manuscripts/{paper.id}/canonical.json")
        doc = Document.model_validate_json(path.read_bytes())
        root = path.parent
        if digest_file(root / "manuscript.md") != paper.manuscript_sha256 or manuscript.render(ws, doc) != (root / "manuscript.md").read_text(encoding="utf-8"):
            raise ValueError("Revised rendered manuscript differs from its canonical evidence")
        report = json.loads((root / "compile-report.json").read_bytes())
        if report.get("input_sha256") != paper.manuscript_sha256 or report.get("document_sha256") != paper.document_sha256 or report.get("status") not in {"COMPILE_READY", "COMPILED"}:
            raise ValueError("Revised manuscript has no matching successful/prepared compiler report")
        if report["status"] == "COMPILED" and (report.get("output") not in {"manuscript.pdf", "manuscript.tex"} or digest_file(ws.path(f"manuscripts/{paper.id}/{report['output']}")) != report.get("sha256")):
            raise ValueError("Revised compiled manuscript artifact changed")
    if doc.paper_id != paper.id or doc.study_id != revision.study_id or doc.title != paper.title or digest_file(path) != paper.document_sha256:
        raise ValueError("Revised canonical manuscript identity/hash differs from Paper")
    if doc.author.get("display_name") != revision.reviewed_by:
        raise ValueError("Revised manuscript must retain the approved named author")
    errors = manuscript.validate_document(snapshot, doc)
    if errors:
        raise ValueError("Revised manuscript rejected: " + "; ".join(errors))
    return paper, doc, snapshot


def check(ws: Workspace, revision: Revision, *, require_active: bool = True) -> dict:
    errors = verify_review(ws, revision)
    child = None
    try:
        if require_active:
            _active(ws, revision)
        if any(paper.id == revision.revised_paper_id for paper in ws.list("paper", Paper)):
            child, _, _ = _child(ws, revision)
    except (ValueError, OSError, KeyError, TypeError) as error:
        errors.append(str(error))
    return {"revision_id": revision.id, "passed": not errors, "errors": sorted(set(errors)),
        "revised_paper_id": revision.revised_paper_id, "drafted": child is not None,
        "author_approved": child is not None and child.state == PaperState.AUTHOR_APPROVED,
        "automatic_external_submission_performed": False}


def draft(ws: Workspace, revision: Revision, pandoc: str | None = None, pdf: bool = False) -> tuple[Paper, Path]:
    with ws.lock(f"revision-{revision.base_submission_id}"):
        problems = verify_review(ws, revision)
        if problems:
            raise ValueError("Revision history is invalid: " + "; ".join(problems))
        _active(ws, revision)
        if any(paper.id == revision.revised_paper_id for paper in ws.list("paper", Paper)):
            raise ValueError("Revision draft already exists; edit its canonical document or apply its response plan")
        _, base, _, source = _base(ws, revision)
        doc = source.model_copy(deep=True)
        doc.paper_id = revision.revised_paper_id
        doc.ai_provenance = manuscript.ai_activities(ws, revision.study_id, doc.paper_id)
        content = manuscript.render(ws, doc)
        paper = Paper(id=revision.revised_paper_id, study_id=revision.study_id, title=doc.title,
            claim_ids=list(base.claim_ids), citation_ids=list(base.citation_ids), manuscript_sha256="", document_sha256="")
        root = ws.path(f"manuscripts/{paper.id}")
        if root.exists():
            raise ValueError("Unindexed revision draft artifact already exists")
        root.mkdir()
        try:
            write_json(root / "canonical.json", doc)
            (root / "manuscript.md").write_text(content, encoding="utf-8")
            write_json(root / "author.json", doc.author)
            paper.document_sha256 = digest_file(root / "canonical.json")
            paper.manuscript_sha256 = digest_file(root / "manuscript.md")
            write_json(root / "paper.json", paper)
            ws.save("paper", paper)
        except Exception:
            if paper.document_sha256:
                ws.discard_uncommitted_artifact(root, kind="paper",
                    record_id=paper.id, field="document_sha256",
                    expected_value=paper.document_sha256)
            else:
                shutil.rmtree(ws.path(f"manuscripts/{paper.id}"))
            raise
        manuscript.compile_manuscript(ws, paper, pandoc=pandoc, pdf=pdf)
        return paper, root


def plan_template(ws: Workspace, revision: Revision) -> ResponsePlan:
    problems = verify_review(ws, revision)
    if problems:
        raise ValueError("Revision history is invalid: " + "; ".join(problems))
    spec = ReviewSpec.model_validate_json((_root(ws, revision) / "spec.json").read_bytes())
    return ResponsePlan(revision_id=revision.id, author=revision.reviewed_by, responses=[
        CommentResponse(comment_id=comment.id, sections=comment.sections, claim_ids=comment.claim_ids,
            experiment_ids=comment.experiment_ids, additional_experiments_required=False) for comment in spec.comments])


def _plan(ws: Workspace, revision: Revision, raw: bytes) -> ResponsePlan:
    plan = ResponsePlan.model_validate_json(raw)
    spec = ReviewSpec.model_validate_json((_root(ws, revision) / "spec.json").read_bytes())
    if plan.revision_id != revision.id or plan.author != revision.reviewed_by:
        raise ValueError("Response plan must name this revision and its approved author")
    if {response.comment_id for response in plan.responses} != {comment.id for comment in spec.comments}:
        raise ValueError("Response plan must cover every actual reviewer comment exactly once")
    return plan


def apply_plan(ws: Workspace, revision: Revision, plan_path: Path, pandoc: str | None = None, pdf: bool = False) -> tuple[Paper, Path]:
    """Apply only author-provided section replacements after validating all edits."""
    with ws.lock(f"revision-{revision.base_submission_id}"):
        problems = verify_review(ws, revision)
        if problems:
            raise ValueError("Revision history is invalid: " + "; ".join(problems))
        _active(ws, revision)
        plan = _plan(ws, revision, _read_bounded(plan_path))
        paper, doc, _ = _child(ws, revision)
        if paper.state == PaperState.AUTHOR_APPROVED:
            raise ValueError("Approved revised manuscript is frozen; cannot apply edits")
        headings = {section.heading: section for section in doc.sections}
        for response in plan.responses:
            for edit in response.edits:
                if response.disposition == "pending" or edit.section not in response.sections or edit.section not in headings:
                    raise ValueError("Section edits must target an existing section linked to an answered comment")
                headings[edit.section].blocks = [block.model_copy(deep=True) for block in edit.blocks]
        doc.ai_provenance = manuscript.ai_activities(ws, revision.study_id, paper.id)
        manuscript.render(ws, doc)  # All targets, quantities and evidence pass before writing.
        with ws.lock(f"paper-{paper.id}"):
            path = ws.path(f"manuscripts/{paper.id}/canonical.json")
            original = path.read_bytes()
            write_json(path, doc)
            try:
                return manuscript._refresh(ws, paper, pandoc, pdf)
            except Exception:
                # Export failures preserve the author-approved canonical edits and
                # their FAILED report, exactly as the ordinary manuscript edit path.
                # Rejected edits never reached this write.
                current = ws.get("paper", paper.id, Paper)
                if current.document_sha256 != digest_file(path):
                    path.write_bytes(original)
                raise


def _response_errors(ws: Workspace, revision: Revision, plan: ResponsePlan, doc: Document, snapshot, base: Document, spec: ReviewSpec) -> tuple[list[str], list[dict]]:
    comments = {comment.id: comment for comment in spec.comments}
    old = {section.heading: section.model_dump(mode="json") for section in base.sections}
    sections = {section.heading: section for section in doc.sections}
    doc_claims = {block.ref for section in doc.sections for block in section.blocks if block.kind == "claim"}
    changed = {section.heading for section in doc.sections if section.model_dump(mode="json") != old.get(section.heading)}
    errors = []
    rows = []
    for response in plan.responses:
        comment = comments[response.comment_id]
        prefix = f"Comment {comment.id}: "
        if response.disposition == "pending" or not response.reply.strip():
            errors.append(prefix + "a substantive author response and disposition are pending")
        if response.disposition in {"partially_accept", "disagree"} and not response.justification.strip():
            errors.append(prefix + "partial acceptance/disagreement requires an author justification")
        for text in (response.reply, response.justification):
            if manuscript.CITATION_TOKEN.search(text):
                errors.append(prefix + "inline scholarly citations must use verified manuscript citation records")
            if manuscript.QUANTITY.search(text) and manuscript.EMPIRICAL.search(text):
                errors.append(prefix + "unsupported quantitative author response; link verified claim records instead")
            if manuscript.NOVELTY.search(text):
                errors.append(prefix + "unsupported novelty/conclusion wording in author response")
        if set(response.sections) - sections.keys():
            errors.append(prefix + "response section does not exist")
        if not (set(response.sections) & set(comment.sections) or set(response.claim_ids) & set(comment.claim_ids) or set(response.experiment_ids) & set(comment.experiment_ids)):
            errors.append(prefix + "response must retain a link to an actual original reviewer target")
        if response.disposition in {"accept", "partially_accept"} and not (set(response.sections) & changed):
            errors.append(prefix + "accepted changes must link an actually changed manuscript section")
        for edit in response.edits:
            if edit.section not in response.sections or edit.section not in sections or sections[edit.section].blocks != edit.blocks:
                errors.append(prefix + "planned section replacement has not been applied to the manuscript")
        valid_claims = []
        valid_runs = {}
        for claim_id in response.claim_ids:
            try:
                claim = snapshot.get("claim", claim_id, Claim)
                problems = verify_claim(snapshot, claim)
                if claim.study_id != revision.study_id or claim.id not in doc_claims or problems:
                    raise ValueError("Response claim is not valid same-Study evidence present in the revised manuscript" + (": " + "; ".join(problems) if problems else ""))
                valid_claims.append(claim)
            except (ValueError, OSError, KeyError, TypeError) as error:
                errors.append(prefix + str(error))
        for run_id in response.run_ids:
            try:
                run = snapshot.get("run", run_id, ExperimentRun)
                _, _, problems = _verify_run(snapshot, run)
                if run.study_id != revision.study_id or problems:
                    raise ValueError("Response run must be a verified successful experiment of the original Study" + (": " + "; ".join(problems) if problems else ""))
                valid_runs[run.id] = run
            except (ValueError, OSError, KeyError, TypeError) as error:
                errors.append(prefix + str(error))
        for experiment_id in response.experiment_ids:
            try:
                experiment = snapshot.get("manifest", experiment_id, ExperimentManifest)
                if experiment.study_id != revision.study_id:
                    raise ValueError("Response experiment belongs to another Study")
            except (ValueError, OSError, KeyError, TypeError) as error:
                errors.append(prefix + str(error))
        if response.additional_experiments_required:
            received = datetime.fromisoformat(revision.received_at)
            qualifying = [run for run in valid_runs.values() if run.ended_at and datetime.fromisoformat(run.ended_at) >= received and datetime.fromisoformat(run.started_at) >= received and run.experiment_id in response.experiment_ids and any(claim.run_id == run.id for claim in valid_claims)]
            if not response.experiment_ids or {run.experiment_id for run in qualifying} != set(response.experiment_ids):
                errors.append(prefix + "each requested additional experiment requires an actual post-review successful run and its linked manuscript claim")
        rows.append({"comment_id": comment.id, "disposition": response.disposition, "changed_sections": sorted(set(response.sections) & changed),
            "claim_ids": list(response.claim_ids), "experiment_ids": list(response.experiment_ids), "run_ids": list(response.run_ids),
            "additional_experiments_required": response.additional_experiments_required})
    return sorted(set(errors)), rows


def _letter(revision: Revision, plan: ResponsePlan, spec: ReviewSpec, rows: list[dict], errors: list[str], snapshot) -> str:
    comments = {comment.id: comment for comment in spec.comments}
    bindings = {row["comment_id"]: row for row in rows}
    lines = ["# Response to reviewers", "", f"Author: {manuscript.escape_md(plan.author)}", "",
        f"Submitted paper: `{revision.base_paper_id}`; revised paper: `{revision.revised_paper_id}`.", "",
        "This response contains author-written replies to excerpts from the preserved referee report. Scientific values are supplied only by linked verified manuscript claims.", ""]
    if errors:
        lines += ["**DRAFT — unresolved response blockers**", "", *["- " + manuscript.escape_md(error) for error in errors], ""]
    for response in plan.responses:
        comment = comments[response.comment_id]
        row = bindings[comment.id]
        lines += [f"## Comment {manuscript.escape_md(comment.id)}", "", "Reviewer excerpt:", ""]
        lines += ["> " + manuscript.escape_md(line) for line in comment.excerpt.splitlines()]
        lines += ["", f"Disposition: **{response.disposition}**", "", manuscript.escape_md(response.reply or "Author response pending."), ""]
        if response.justification:
            lines += ["Author justification: " + manuscript.escape_md(response.justification), ""]
        lines += ["Changed manuscript sections: " + (", ".join(manuscript.escape_md(section) for section in row["changed_sections"]) or "none") + ".", "",
            "Linked claims: " + (", ".join(f"`{id}`" for id in row["claim_ids"]) or "none") + ".", "",
            "Linked experiment runs: " + (", ".join(f"`{id}`" for id in row["run_ids"]) or "none") + ".", ""]
        for claim_id in row["claim_ids"]:
            try:
                claim = snapshot.get("claim", claim_id, Claim)
                if claim.study_id == revision.study_id and not verify_claim(snapshot, claim):
                    lines += [manuscript.claim_text(claim), ""]
            except (ValueError, OSError, KeyError, TypeError):
                pass  # A failed link is visibly blocked above, never rendered as a result.
    return "\n".join(lines)


def _diff(base: Document, base_snapshot, doc: Document, snapshot) -> str:
    before = manuscript.render(base_snapshot, base, include_audit=False).splitlines(keepends=True)
    after = manuscript.render(snapshot, doc, include_audit=False).splitlines(keepends=True)
    return "".join(difflib.unified_diff(before, after, fromfile=f"submitted/{base.paper_id}.md", tofile=f"revised/{doc.paper_id}.md"))


def _changes(rows: list[dict]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["comment_id", "disposition", "changed_sections", "claim_ids", "experiment_ids", "run_ids", "additional_experiments_required"])
    for row in rows:
        writer.writerow([row["comment_id"], row["disposition"], " | ".join(row["changed_sections"]), " | ".join(row["claim_ids"]), " | ".join(row["experiment_ids"]), " | ".join(row["run_ids"]), str(row["additional_experiments_required"]).lower()])
    return stream.getvalue()


def build_response(ws: Workspace, revision: Revision, plan_path: Path, pandoc: str | None = None) -> tuple[ResponseBuild, Path]:
    with ws.lock(f"revision-{revision.base_submission_id}"):
        try:
            _, base_snapshot, base, spec = _validated_review(ws, revision)
        except (ValueError, OSError, KeyError, TypeError, UnicodeError) as error:
            raise ValueError("Revision history is invalid: " + str(error)) from error
        _active(ws, revision)
        raw = _read_bounded(plan_path)
        plan = _plan(ws, revision, raw)
        paper, doc, snapshot = _child(ws, revision)
        errors, rows = _response_errors(ws, revision, plan, doc, snapshot, base, spec)
        data = ResponseData(revision_id=revision.id, revised_paper_id=paper.id, document_sha256=paper.document_sha256,
            ready=not errors, errors=errors, files={})
        parent = ws.path(f"revisions/{revision.id}/responses")
        parent.mkdir(exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".response-", dir=parent))
        destination = parent / data.id
        published = False
        try:
            (stage / "plan.json").write_bytes(raw)
            (stage / "letter.md").write_text(_letter(revision, plan, spec, rows, errors, snapshot), encoding="utf-8", newline="")
            (stage / "changes.csv").write_text(_changes(rows), encoding="utf-8", newline="")
            (stage / "manuscript.diff").write_text(_diff(base, base_snapshot, doc, snapshot), encoding="utf-8", newline="")
            write_json(stage / "bindings.json", {"revision_artifact_sha256": revision.artifact_sha256,
                "base_freeze_digest": revision.base_freeze_digest, "decision_event_id": revision.decision_event_id,
                "revised_paper_id": paper.id, "document_sha256": paper.document_sha256, "comments": rows})
            if pandoc:
                for suffix in (".pdf", ".docx"):
                    convert(stage / "letter.md", stage / f"letter{suffix}", pandoc=pandoc)
            data.files = {path.relative_to(stage).as_posix(): digest_file(path) for path in stage.rglob("*") if path.is_file()}
            write_json(stage / "response.json", data)
            response = ResponseBuild(**data.model_dump(), artifact_sha256=digest_file(stage / "response.json"))
            with ws._database() as db:
                db.execute("BEGIN IMMEDIATE")
                _active(ws, revision)
                if ws.get("paper", paper.id, Paper).document_sha256 != paper.document_sha256:
                    raise ValueError("Revised manuscript changed while building its response")
                ws.rename_artifact(stage, destination)
                published = True
                db.execute("INSERT INTO records VALUES (?,?,?)", ("revision_response", response.id, response.model_dump_json()))
            return response, destination
        except Exception:
            if published:
                ws.discard_uncommitted_artifact(destination, kind="revision_response",
                    record_id=response.id, field="artifact_sha256",
                    expected_value=response.artifact_sha256)
            raise
        finally:
            if stage.exists():
                shutil.rmtree(ws.path(stage.relative_to(ws.root).as_posix()))


def verify_response(ws: Workspace, response: ResponseBuild, *, require_approved: bool = False, require_active: bool = False) -> dict:
    errors = []
    try:
        revision = ws.get("revision", response.revision_id, Revision)
        _, base_snapshot, base, spec = _validated_review(ws, revision)
        if require_active:
            _active(ws, revision)
        if ws.get("revision_response", response.id, ResponseBuild) != response:
            raise ValueError("Response differs from its immutable indexed build")
        root = response_root(ws, response)
        for path in root.rglob("*"):
            ws.path(path.relative_to(ws.root).as_posix())
        actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
        if actual != set(response.files) | {"response.json"} or digest_file(root / "response.json") != response.artifact_sha256 or json.loads((root / "response.json").read_bytes()) != response.model_dump(mode="json", exclude={"artifact_sha256"}):
            raise ValueError("Immutable revision response artifact or file set changed")
        for name, expected in response.files.items():
            if digest_file(ws.path(f"revisions/{revision.id}/responses/{response.id}/{name}")) != expected:
                raise ValueError(f"Revision response artifact changed: {name}")
        if not {"plan.json", "letter.md", "changes.csv", "bindings.json", "manuscript.diff"}.issubset(response.files):
            raise ValueError("Required revision response artifacts are missing")
        plan = _plan(ws, revision, _read_bounded(root / "plan.json"))
        paper, doc, snapshot = _child(ws, revision)
        if response.revised_paper_id != paper.id or response.document_sha256 != paper.document_sha256:
            raise ValueError("Response is stale: revised manuscript changed after response build")
        if require_approved and paper.state != PaperState.AUTHOR_APPROVED:
            errors.append("Revised manuscript requires separate scientific author approval")
        computed, rows = _response_errors(ws, revision, plan, doc, snapshot, base, spec)
        if response.errors != computed or response.ready != (not computed):
            raise ValueError("Response readiness differs from actual reviewer/evidence checks")
        errors.extend(computed)
        if (root / "letter.md").read_text(encoding="utf-8") != _letter(revision, plan, spec, rows, computed, snapshot) or (root / "changes.csv").read_text(encoding="utf-8") != _changes(rows) or (root / "manuscript.diff").read_text(encoding="utf-8") != _diff(base, base_snapshot, doc, snapshot):
            raise ValueError("Derived response letter/change table differs from author plan and actual changes")
        expected = {"revision_artifact_sha256": revision.artifact_sha256, "base_freeze_digest": revision.base_freeze_digest,
            "decision_event_id": revision.decision_event_id, "revised_paper_id": paper.id,
            "document_sha256": paper.document_sha256, "comments": rows}
        if json.loads((root / "bindings.json").read_bytes()) != expected:
            raise ValueError("Response scientific/reviewer binding changed")
    except (ValueError, OSError, KeyError, TypeError, UnicodeError) as error:
        errors.append(str(error))
    return {"response_id": response.id, "revision_id": response.revision_id, "passed": not errors, "ready": not errors,
        "errors": sorted(set(errors)), "automatic_external_submission_performed": False}

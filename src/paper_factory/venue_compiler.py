"""Venue-specific derivatives of an approved canonical manuscript."""

import csv
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from xml.etree import ElementTree
from pathlib import Path

import httpx
from pydantic import Field, field_validator

from .conversion import convert, verify_receipts
from .integrity import frozen_workspace
from .manuscript import Document, claim_text, escape_md, number_text
from .models import Citation, Claim, Paper, PaperState, Record, Submission, SubmissionState, now, transition_submission, uid
from .venue_policy import VenuePolicy, refresh_policy, validate_policy
from .venues import Venue
from .workspace import Workspace, digest_file, write_json


class CompilerSettings(Record):
    article_type: str
    keywords: list[str] = Field(default_factory=list)
    declarations: dict[str, str]
    scope_fit: str
    cover_letter: str
    csl: str | None = None
    csl_license: str | None = None
    csl_source_url: str | None = None

    @field_validator("article_type", "scope_fit", "cover_letter")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Compiler settings require actual nonempty author statements")
        return value.strip()

    @field_validator("keywords")
    @classmethod
    def actual_keywords(cls, value: list[str]) -> list[str]:
        value = [word.strip() for word in value]
        if any(not word for word in value) or len({word.casefold() for word in value}) != len(value):
            raise ValueError("Keywords must be nonempty and unique")
        return value


class Compilation(Record):
    id: str
    paper_id: str
    policy_id: str
    canonical_digest: str
    settings_sha256: str
    files: dict[str, str]
    errors: list[str]
    warnings: list[str]
    word_counts: dict[str, int]
    compiled_at: str = Field(default_factory=now)


def select(ws: Workspace, paper: Paper, venue: Venue, policy: VenuePolicy) -> Submission:
    paper = ws.get("paper", paper.id, Paper)
    if paper.state != PaperState.AUTHOR_APPROVED:
        raise ValueError("Venue compilation requires explicit scientific author approval")
    frozen_workspace(ws, paper)
    if policy.venue_id != venue.id:
        raise ValueError("Venue and policy identities differ")
    submission = Submission(paper_id=paper.id, venue_id=venue.id, policy_id=policy.id, candidate_digest=paper.freeze_digest)
    ws.save("submission", submission)
    return submission


def policy_fingerprint(policy: VenuePolicy) -> str:
    payload = {"values": policy.values.model_dump(mode="json"), "evidence": {key: record.model_dump(mode="json") for key, record in policy.evidence.items()}, "sources": [(source.url, source.text_sha256, source.status) for source in policy.sources]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _bibliography(snapshot: Workspace, doc: Document) -> list[dict]:
    ids = list(dict.fromkeys(block.ref for section in doc.sections for block in section.blocks if block.kind == "citation"))
    entries = []
    for id in ids:
        citation = snapshot.get("citation", id, Citation)
        metadata = json.loads(snapshot.path(f"literature/{id}.json").read_bytes())["message"]
        # Crossref and CSL use different work-type names. Unknown types retain
        # a neutral CSL document type rather than inventing a journal article.
        types = {"journal-article": "article-journal", "proceedings-article": "paper-conference", "book-chapter": "chapter", "book": "book", "monograph": "book", "dissertation": "thesis", "report": "report", "dataset": "dataset", "posted-content": "article"}
        entry = {"id": id, "type": types.get(metadata.get("type"), "document"), "title": citation.title, "author": [{"literal": author} for author in citation.authors], "DOI": citation.doi, **({"issued": {"date-parts": [[citation.year]]}} if citation.year else {})}
        for source, target in (("volume", "volume"), ("issue", "issue"), ("page", "page"), ("publisher", "publisher")):
            if isinstance(metadata.get(source), str) and metadata[source].strip():
                entry[target] = metadata[source]
        if isinstance(metadata.get("container-title"), list) and metadata["container-title"] and isinstance(metadata["container-title"][0], str):
            entry["container-title"] = metadata["container-title"][0]
        entries.append(entry)
    return entries


def _identity_tokens(doc: Document) -> list[str]:
    return sorted({value for key, value in doc.author.items() if key in {"display_name", "given_name", "family_name", "email", "orcid", "affiliation", "department", "scholar_id", "github", "homepage"} and value.strip()}, key=len, reverse=True)


def _identity_pattern(value: str) -> str:
    return (r"(?<!\w)" if value[0].isalnum() else "") + re.escape(value) + (r"(?!\w)" if value[-1].isalnum() else "")


def _contains_identity(text: str, doc: Document) -> bool:
    return any(re.search(_identity_pattern(value), text, re.I) for token in _identity_tokens(doc) for value in {token, escape_md(token)})


def _redact(text: str, doc: Document) -> str:
    for value in _identity_tokens(doc):
        for encoded in sorted({value, escape_md(value)}, key=len, reverse=True):
            text = re.sub(_identity_pattern(encoded), "[redacted for review]", text, flags=re.I)
    return text


def _review_identification_errors(root: Path, doc: Document, *, stem: str = "manuscript") -> list[str]:
    """Inspect rendered review documents as well as their metadata."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(root / f"{stem}.pdf")
        pdf_text = " ".join(page.extract_text() or "" for page in reader.pages) + str(reader.metadata)
        errors = ["Author-identifying content remains in the blinded manuscript PDF"] if _contains_identity(pdf_text, doc) else []
        with zipfile.ZipFile(root / f"{stem}.docx") as archive:
            parts = []
            for name in archive.namelist():
                if name.endswith((".xml", ".rels")):
                    tree = ElementTree.fromstring(archive.read(name))
                    parts.append("".join(tree.itertext()))
                    parts.extend(value for element in tree.iter() for value in element.attrib.values())
        if _contains_identity(" ".join(parts), doc):
            errors.append("Author-identifying content remains in the blinded manuscript DOCX")
        return errors
    except Exception as exc:
        raise ValueError(f"Blinded document identification review failed: {exc}") from exc


def _rendered_word_count(root: Path) -> int:
    try:
        from pypdf import PdfReader
        return _word_count(" ".join(page.extract_text() or "" for page in PdfReader(root / "manuscript.pdf").pages))
    except Exception as exc:
        raise ValueError(f"Rendered manuscript word-count review failed: {exc}") from exc


def render_article(snapshot: Workspace, doc: Document, settings: CompilerSettings, anonymized: bool) -> tuple[str, dict, list[Claim]]:
    lines = [f"# {escape_md(doc.title)}", ""]
    if not anonymized:
        lines += [escape_md(doc.author["display_name"]), "", escape_md(doc.author["affiliation"]), ""]
    if settings.keywords:
        lines += ["Keywords: " + "; ".join(escape_md(word) for word in settings.keywords), ""]
    mapping: dict[str, list[str]] = {}
    claims: list[Claim] = []
    for section in doc.sections:
        lines += [f"## {escape_md(section.heading)}", ""]
        mapping[section.heading] = []
        for block in section.blocks:
            if block.kind == "prose":
                lines += [escape_md(block.text), ""]
            elif block.kind == "claim":
                claim = snapshot.get("claim", block.ref, Claim)
                lines += [claim_text(claim).split(" [Evidence:", 1)[0], ""]
                mapping[section.heading].append(claim.id)
                if all(item.id != claim.id for item in claims):
                    claims.append(claim)
            else:
                lines += [f"[@{block.ref}]", ""]
    lines += ["## Results table", "", "| Measurement | Value | Unit |", "|---|---:|---|"]
    for claim in claims:
        lines.append(f"| {escape_md(claim.description)} | {number_text(claim.value)} | {escape_md(claim.unit)} |")
    lines += ["", "## Declarations", ""]
    for name, statement in settings.declarations.items():
        lines += ["### " + escape_md(name.replace("_", " ").title()), "", escape_md(statement), ""]
    if doc.ai_provenance:
        lines += ["### Recorded AI assistance", ""]
        for activity in doc.ai_provenance:
            lines += [f"- {escape_md(activity['role'])}: {escape_md(activity['tool'])}, model {escape_md(activity['model'] or 'unspecified')}.", ""]
    lines += ["## References", "", "::: {#refs}", ":::", ""]
    text = "\n".join(lines)
    return (_redact(text, doc) if anonymized else text), mapping, claims


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w]+(?:[-'][\w]+)*\b", text))


def _compliance(snapshot: Workspace, doc: Document, settings: CompilerSettings, policy: VenuePolicy, article: str) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    values = policy.values
    counts = {"manuscript": _word_count(article)}
    abstract = next((section for section in doc.sections if section.heading == "Abstract"), None)
    abstract_text = " ".join(block.text if block.kind == "prose" else claim_text(snapshot.get("claim", block.ref, Claim)).split(" [Evidence:", 1)[0] if block.kind == "claim" else "" for block in abstract.blocks) if abstract else ""
    # Quantitative blocks count their actual visible text, not record IDs.
    counts["abstract"] = _word_count(abstract_text)
    if values.article_types is None or settings.article_type.casefold() not in {item.casefold() for item in values.article_types}:
        errors.append("Article type is not verified as accepted by this venue")
    if values.keyword_limit is not None and len(settings.keywords) > values.keyword_limit:
        errors.append("Keyword limit exceeded")
    if values.manuscript_word_limit is not None and counts["manuscript"] > values.manuscript_word_limit:
        errors.append("Manuscript word limit exceeded")
    if values.abstract_word_limit is not None and counts["abstract"] > values.abstract_word_limit:
        errors.append("Abstract word limit exceeded")
    for name in values.required_declarations or []:
        if not settings.declarations.get(name, "").strip():
            errors.append(f"Missing required author declaration: {name}")
    for name, statement in settings.declarations.items():
        if not statement.strip() or re.search(r"\b(?:TODO|TBD|REPLACE_WITH|PLACEHOLDER)\b", statement, re.I):
            errors.append(f"Empty or placeholder author declaration: {name}")
    if doc.ai_provenance and values.ai_use_allowed is not True:
        errors.append("Recorded AI use is not permitted by the verified policy")
    if doc.ai_provenance and values.ai_disclosure_required and not settings.declarations.get("ai_disclosure", "").strip():
        errors.append("The venue requires an author-confirmed AI disclosure")
    if values.free_initial_submission is False or values.template_requirements:
        errors.append("An exact publisher layout/template is required; this compiler supports verified free initial formats")
    elif values.free_initial_submission is not True:
        errors.append("Free initial submission format rules have not been verified")
    if values.accepted_formats is None or not {"pdf", "tex", "docx"}.intersection(values.accepted_formats):
        errors.append("No supported manuscript format is verified for this venue")
    if values.indexing == "unknown":
        warnings.append("SCIE/ESCI indexing has not been verified; no indexing claim is made")
    for heading in getattr(values, "required_sections", None) or []:
        if heading.casefold() not in {section.heading.casefold() for section in doc.sections}:
            errors.append(f"Missing venue-required section: {heading}")
    if getattr(values, "required_supplements", None):
        errors.append("Venue requires additional supplements that this canonical manuscript does not supply")
    if getattr(values, "abstract_character_limit", None) is not None and len(abstract_text) > values.abstract_character_limit:
        errors.append("Abstract character limit exceeded")
    if getattr(values, "title_character_limit", None) is not None and len(doc.title) > values.title_character_limit:
        errors.append("Title character limit exceeded")
    warnings.append("Scope fit and factual declarations require author review; preparing a package does not constitute final submission attestation")
    warnings.append("Word counts use source text; the author must check the final cited document against the venue's reference/caption counting rules")
    return errors, warnings, counts


def compile_submission(ws: Workspace, submission: Submission, settings_path: Path, *, pandoc: str | None = None, client: httpx.Client | None = None) -> tuple[Submission, Path]:
    with ws.lock(f"submission-{submission.id}"):
        submission = ws.get("submission", submission.id, Submission)
        if submission.state != SubmissionState.VENUE_SELECTED:
            raise ValueError("Compiled candidates are immutable; select a new candidate to change settings")
        paper = ws.get("paper", submission.paper_id, Paper)
        if paper.freeze_digest != submission.candidate_digest:
            raise ValueError("Selected canonical approval changed")
        snapshot = frozen_workspace(ws, paper)
        doc = Document.model_validate_json(snapshot.path("canonical.json").read_bytes())
        settings = CompilerSettings.model_validate_json(settings_path.read_bytes())
        policy = refresh_policy(ws, ws.get("policy", submission.policy_id, VenuePolicy), client=client)
        submission.policy_id = policy.id
        policy_errors = validate_policy(ws, policy)
        anonymized = policy.values.anonymization_required is True
        article, mapping, claims = render_article(snapshot, doc, settings, anonymized)
        errors, warnings, counts = _compliance(snapshot, doc, settings, policy, article)
        errors = list(dict.fromkeys(policy_errors + errors))
        destination = ws.path(f"submissions/{submission.id}/compiled")
        if destination.exists():
            raise ValueError("Compilation destination already exists; select a new candidate")
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".compiling-", dir=destination.parent))
        published = False
        try:
            write_json(stage / "settings.json", settings)
            write_json(stage / "policy.json", policy)
            write_json(stage / "canonical-binding.json", {"paper_id": paper.id, "freeze_digest": paper.freeze_digest, "document_sha256": paper.document_sha256, "claim_map": mapping, "policy_fingerprint": policy_fingerprint(policy)})
            (stage / "manuscript.md").write_text(article, encoding="utf-8")
            bibliography = _bibliography(snapshot, doc)
            if anonymized:
                for entry in bibliography:
                    # Self-citation must follow its official review instructions;
                    # silently corrupting bibliographic metadata is prohibited.
                    if _contains_identity(json.dumps(entry, ensure_ascii=False), doc):
                        errors.append("Self-identifying bibliography requires author anonymization review")
            write_json(stage / "references.json", bibliography)
            csl = None
            if settings.csl:
                csl = Path(settings.csl).expanduser().resolve()
                if not csl.is_file() or not settings.csl_license or not settings.csl_source_url:
                    raise ValueError("CSL must be an existing file with its source URL and verified license recorded")
                shutil.copyfile(csl, stage / "references.csl")
                csl = stage / "references.csl"
            elif policy.values.citation_style and policy.values.citation_style.casefold() not in {"any", "free", "unrestricted"}:
                errors.append("A verified citation style is required; supply an upstream CSL file and its license/source")
            reports = {}
            for suffix in ("pdf", "tex", "docx"):
                reports[suffix] = convert(stage / "manuscript.md", stage / f"manuscript.{suffix}", pandoc=pandoc, bibliography=stage / "references.json", csl=csl, line_numbers=getattr(policy.values, "line_numbers_required", False) is True, page_numbers=getattr(policy.values, "page_numbers_required", True) is not False)
            counts["rendered_manuscript"] = _rendered_word_count(stage)
            if policy.values.manuscript_word_limit is not None and counts["rendered_manuscript"] > policy.values.manuscript_word_limit:
                errors.append("Manuscript word limit exceeded in the final cited PDF")
            write_json(stage / "conversion.json", reports)
            (stage / "cover-letter.md").write_text(settings.cover_letter + "\n", encoding="utf-8")
            write_json(stage / "author.json", doc.author)
            write_json(stage / "declarations.json", settings.declarations)
            write_json(stage / "metadata.json", {"title": doc.title, "venue_id": submission.venue_id, "article_type": settings.article_type, "keywords": settings.keywords, "scope_fit": settings.scope_fit, "submission_url": policy.values.submission_url, "anonymized_manuscript": anonymized, "not_finally_attested": True})
            (stage / "tables").mkdir()
            with (stage / "tables" / "results.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["measurement", "value", "unit"])
                writer.writerows([[_redact(claim.description, doc) if anonymized else claim.description, number_text(claim.value), _redact(claim.unit, doc) if anonymized else claim.unit] for claim in claims])
            (stage / "figures").mkdir()
            (stage / "figures" / "README.txt").write_text("This canonical manuscript contains no figure blocks. Results are supplied as an evidence-backed table.\n", encoding="utf-8")
            (stage / "supplement").mkdir()
            write_json(stage / "supplement" / "evidence-map.json", {"canonical_digest": paper.freeze_digest, "claims": [claim.model_dump(mode="json") for claim in claims]})
            if anonymized:
                errors.extend(_review_identification_errors(stage, doc))
            files = {path.relative_to(stage).as_posix(): digest_file(path) for path in stage.rglob("*") if path.is_file()}
            compilation = Compilation(id=submission.id, paper_id=paper.id, policy_id=policy.id, canonical_digest=paper.freeze_digest, settings_sha256=digest_file(stage / "settings.json"), files=files, errors=list(dict.fromkeys(errors)), warnings=warnings, word_counts=counts)
            write_json(stage / "compliance.json", compilation)
            compilation_digest = digest_file(stage / "compliance.json")
            ws.rename_artifact(stage, destination)
            published = True
            submission.compilation_digest = compilation_digest
            transition_submission(submission, SubmissionState.VENUE_COMPILED)
            with ws._database() as db:
                for kind, record in (("compilation", compilation), ("submission", submission)):
                    db.execute("INSERT INTO records VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data", (kind, record.id, record.model_dump_json()))
            return submission, destination
        except Exception as exc:
            if published:
                ws.discard_uncommitted_artifact(destination, kind="submission",
                    record_id=submission.id, field="compilation_digest",
                    expected_value=compilation_digest)
            elif stage.exists():
                write_json(stage / "failure.json", {"error": str(exc), "failed_at": now(), "submission_id": submission.id})
                ws.rename_artifact(stage, destination.parent / uid("failed-compilation"))
            raise
        finally:
            if stage.exists():
                # Staging is a known newly-created descendant of this workspace.
                if not stage.resolve().is_relative_to(destination.parent.resolve()):
                    raise ValueError("Unexpected compilation staging directory")
                shutil.rmtree(stage)


def verify_compilation(ws: Workspace, submission: Submission, *, check_compliance: bool = True) -> list[str]:
    errors: list[str] = []
    try:
        submission = ws.get("submission", submission.id, Submission)
        if submission.state == SubmissionState.VENUE_SELECTED or not submission.compilation_digest:
            return ["Submission has not been compiled"]
        compilation = ws.get("compilation", submission.id, Compilation)
        root = ws.path(f"submissions/{submission.id}/compiled")
        if digest_file(root / "compliance.json") != submission.compilation_digest or json.loads((root / "compliance.json").read_bytes()) != compilation.model_dump(mode="json"):
            errors.append("Compilation compliance record changed")
        if compilation.id != submission.id or compilation.paper_id != submission.paper_id or compilation.canonical_digest != submission.candidate_digest:
            errors.append("Compiled output differs from its selected canonical approval")
        actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()} - {"compliance.json"}
        if actual != set(compilation.files):
            errors.append("Compilation file set changed")
        for relative, expected in compilation.files.items():
            if digest_file(ws.path(f"submissions/{submission.id}/compiled/{relative}")) != expected:
                errors.append(f"Compilation output changed: {relative}")
        errors.extend(verify_receipts(root / "manuscript.md",
            {format: root / f"manuscript.{format}" for format in ("pdf", "tex", "docx")},
            root / "conversion.json"))
        snapshot = frozen_workspace(ws, ws.get("paper", submission.paper_id, Paper))
        doc = Document.model_validate_json(snapshot.path("canonical.json").read_bytes())
        settings = CompilerSettings.model_validate_json((root / "settings.json").read_bytes())
        policy = ws.get("policy", compilation.policy_id, VenuePolicy)
        if policy.venue_id != submission.venue_id or json.loads((root / "policy.json").read_bytes()) != policy.model_dump(mode="json"):
            errors.append("Compiled venue policy identity/content differs")
        errors.extend(validate_policy(ws, policy, fresh=False, check_compliance=check_compliance))
        if digest_file(root / "settings.json") != compilation.settings_sha256:
            errors.append("Compiled author settings changed")
        article, mapping, claims = render_article(snapshot, doc, settings, policy.values.anonymization_required is True)
        required_errors, _, counts = _compliance(snapshot, doc, settings, policy, article)
        counts["rendered_manuscript"] = _rendered_word_count(root)
        if policy.values.manuscript_word_limit is not None and counts["rendered_manuscript"] > policy.values.manuscript_word_limit:
            required_errors.append("Manuscript word limit exceeded in the final cited PDF")
        required_errors.extend(validate_policy(ws, policy, fresh=False))
        if policy.values.citation_style and policy.values.citation_style.casefold() not in {"any", "free", "unrestricted"} and not (root / "references.csl").is_file():
            required_errors.append("A verified citation style is required; supply an upstream CSL file and its license/source")
        if policy.values.anonymization_required and any(_contains_identity(json.dumps(entry, ensure_ascii=False), doc) for entry in _bibliography(snapshot, doc)):
            required_errors.append("Self-identifying bibliography requires author anonymization review")
        if policy.values.anonymization_required:
            required_errors.extend(_review_identification_errors(root, doc))
        if set(required_errors) - set(compilation.errors) or compilation.word_counts != counts:
            errors.append("Compilation omitted required compliance blockers or changed its word counts")
        if (root / "manuscript.md").read_text(encoding="utf-8") != article:
            errors.append("Compiled scientific prose/results differ from the approved canonical manuscript")
        binding = json.loads((root / "canonical-binding.json").read_bytes())
        expected_binding = {"paper_id": submission.paper_id, "freeze_digest": submission.candidate_digest, "document_sha256": digest_file(snapshot.path("canonical.json")), "claim_map": mapping, "policy_fingerprint": policy_fingerprint(policy)}
        if binding != expected_binding:
            errors.append("Compiled canonical/policy binding differs")
        if json.loads((root / "references.json").read_bytes()) != _bibliography(snapshot, doc):
            errors.append("Compiled bibliography differs from verified canonical references")
        with (root / "tables" / "results.csv").open(newline="", encoding="utf-8") as stream:
            actual_rows = list(csv.reader(stream))
        anonymized = policy.values.anonymization_required is True
        expected_rows = [["measurement", "value", "unit"], *[[_redact(claim.description, doc) if anonymized else claim.description, number_text(claim.value), _redact(claim.unit, doc) if anonymized else claim.unit] for claim in claims]]
        if actual_rows != expected_rows:
            errors.append("Compiled results table differs from the approved evidence")
        if json.loads((root / "author.json").read_bytes()) != doc.author or json.loads((root / "declarations.json").read_bytes()) != settings.declarations:
            errors.append("Compiled author/declaration metadata differs")
        if check_compliance:
            errors.extend([*compilation.errors, *required_errors])
    except (ValueError, OSError, TypeError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        errors.append(f"Invalid compilation: {exc}")
    return list(dict.fromkeys(errors))

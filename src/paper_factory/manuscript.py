"""Canonical structured manuscripts rendered exclusively from verified records."""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import Field

from .author import AuthorProfile, load_author
from .conversion import convert
from .evidence import claims_for_run, verify_claim
from .literature import verify_citation
from .models import Claim, Citation, ExperimentRun, Paper, PaperState, Project, Provenance, Record, Study
from .workspace import Workspace, digest_file, write_json


class Block(Record):
    kind: Literal["prose", "claim", "citation"]
    text: str = ""
    ref: str = ""


class Section(Record):
    heading: str
    blocks: list[Block]


class Document(Record):
    paper_id: str
    study_id: str
    title: str
    domain: str
    author: dict[str, str]
    sections: list[Section]
    limitations: list[str] = Field(min_length=1)
    ai_provenance: list[dict] = Field(default_factory=list)


def ai_activities(ws: Workspace, study_id: str | None = None, paper_id: str | None = None) -> list[dict]:
    """Select assistance linked to the study and its evidence, in stable order.

    Empty inputs identify an explicitly workspace-wide disclosure. Activities
    attached to other studies or venue submissions do not alter this paper.
    """
    linked = {study_id, paper_id} - {None}
    if study_id:
        linked.update(run.id for run in ws.list("run", ExperimentRun) if run.study_id == study_id)
        linked.update(claim.id for claim in ws.list("claim", Claim) if claim.study_id == study_id)
        linked.update(ws.get("study", study_id, Study).citation_ids)
    records = [record for record in ws.list("provenance", Provenance) if record.ai and (
        getattr(ws, "is_frozen", False) or study_id is None or not record.inputs or linked.intersection(record.inputs + record.outputs)
    )]
    return [record.model_dump(mode="json") for record in sorted(records, key=lambda record: record.id)]


# Conservative lint for editable prose. It supplements typed result blocks;
# semantic scientific assessment remains the author's responsibility.
QUANTITY = re.compile(r"\d|%|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|percent|percentage|twice|half)\b", re.I)
EMPIRICAL = re.compile(r"%|\b(?:percent(?:age)?|accuracy|precision|recall|latency|throughput|recovery|succeeded|failed|improved|reduced|increased|decreased|measured|observed|achieved|averaged|scored|rate|mean|median|variance|samples?|participants?|cases|milliseconds?|seconds?|bytes|files)\b|\b[nN]\s*=", re.I)
NOVELTY = re.compile(r"\b(?:first|novel|unprecedented|state.of.the.art|outperform\w*|prove[sd]?)\b", re.I)
CITATION_TOKEN = re.compile(r"\[@|\bdoi\s*:|https?://(?:dx\.)?doi\.org|\b10\.\d{4,9}/", re.I)


def prose(text: str) -> Block:
    return Block(kind="prose", text=text)


def quantitative_label(text: str) -> bool:
    """Keep standard metric identifiers distinct from an asserted result.

    A metric's measured value belongs in its Claim, not its editable label.
    Ordinal percentiles, F1/P95 identifiers and bare percentage units describe
    measurements without asserting an additional measured outcome.
    """
    label = re.sub(r"\b\d+(?:st|nd|rd|th)[ -]+percentile\b|\btop[ -]*\d+\b|\b[A-Za-z]+\d+[A-Za-z\d]*\b", "identifier", text, flags=re.I)
    label = re.sub(r"\bpercent(?:age)?s?\b|%", "unit", label, flags=re.I)
    return bool(QUANTITY.search(label) and EMPIRICAL.search(text))


def validate_document(ws: Workspace, doc: Document) -> list[str]:
    issues: list[str] = []
    study = ws.get("study", doc.study_id, Study)
    if doc.domain != study.domain:
        issues.append("Document domain differs from study")
    project = ws.get("project", study.project_id, Project)
    texts = [doc.title.replace(project.name, "project"), *doc.limitations]
    novelty_texts = list(texts)
    quantitative_texts: list[str] = list(texts)
    try:
        AuthorProfile.model_validate(doc.author)
    except ValueError as exc:
        issues.append(f"Canonical author metadata invalid: {exc}")
    if doc.ai_provenance != ai_activities(ws, doc.study_id, doc.paper_id):
        issues.append("AI-use provenance changed after drafting; rebuild and review disclosure")
    seen: set[str] = set()
    claim_sections: dict[str, set[str]] = {}
    for section in doc.sections:
        texts.append(section.heading)
        novelty_texts.append(section.heading)
        quantitative_texts.append(section.heading)
        claim_sections.setdefault(section.heading, set())
        for block in section.blocks:
            if block.kind == "prose":
                if block.ref or not block.text.strip():
                    issues.append("Prose must contain text and no record reference")
                normalized = " ".join(block.text.casefold().split())
                if normalized in seen:
                    issues.append("Duplicated prose block")
                seen.add(normalized)
                texts.append(block.text)
                if section.heading != "Research Questions":
                    novelty_texts.append(block.text)
                if section.heading != "Research Questions":
                    quantitative_texts.append(block.text)
            else:
                if block.text or not block.ref:
                    issues.append("Result/citation blocks must contain a reference and no free text")
                try:
                    if block.kind == "claim":
                        claim = ws.get("claim", block.ref, Claim)
                        if claim.study_id != doc.study_id:
                            issues.append(f"Claim {claim.id} belongs to a different study")
                        issues.extend(verify_claim(ws, claim))
                        for label in (claim.description, claim.unit):
                            if quantitative_label(label):
                                issues.append(f"Unsupported quantitative metric label: {label[:100]}")
                            if CITATION_TOKEN.search(label):
                                issues.append("Unverified inline citation in metric label; use a citation record block")
                            novelty_label = re.sub(r"\b(?:time[ -]to[ -])?first[ -]byte\b", "response byte", label, flags=re.I)
                            if NOVELTY.search(novelty_label):
                                issues.append(f"Unsupported novelty/conclusion wording in metric label: {label[:100]}")
                        claim_sections[section.heading].add(claim.id)
                    else:
                        citation = ws.get("citation", block.ref, Citation)
                        if citation.id not in study.citation_ids:
                            issues.append(f"Citation {citation.id} is not linked to study")
                        issues.extend(verify_citation(ws, citation))
                except (ValueError, OSError, KeyError, TypeError) as exc:
                    issues.append(str(exc))
    for text in texts:
        if CITATION_TOKEN.search(text):
            issues.append("Unverified inline citation; use a citation record block")
    for text in novelty_texts:
        if NOVELTY.search(text):
            issues.append(f"Unsupported novelty/conclusion wording: {text[:100]}")
    for text in quantitative_texts:
        if QUANTITY.search(text) and EMPIRICAL.search(text):
            issues.append(f"Unsupported quantitative prose: {text[:100]}")
    if not claim_sections.get("Results"):
        issues.append("Results has no evidence-backed claims")
    if claim_sections.get("Abstract", set()) != claim_sections.get("Results", set()):
        issues.append("Abstract and Results claim sets differ")
    required = {"Abstract", "Introduction", "Related Work", "Research Questions", "Method", "Experimental Setup", "Results", "Discussion", "Limitations", "Conclusion"}
    if doc.domain == "software_engineering":
        required.add("Threats to Validity")
    missing = required - {section.heading for section in doc.sections}
    if missing:
        issues.append(f"Missing sections: {', '.join(sorted(missing))}")
    if len({section.heading for section in doc.sections}) != len(doc.sections):
        issues.append("Duplicate section headings")
    for section in doc.sections:
        if section.heading in required and not section.blocks:
            issues.append(f"Required section is empty: {section.heading}")
    return sorted(set(issues))


def escape_md(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]<>#|])", r"\\\1", " ".join(value.split()))


def claim_text(claim: Claim) -> str:
    unit = f" {escape_md(claim.unit)}" if claim.unit else ""
    return f"{escape_md(claim.description)}: **{number_text(claim.value)}{unit}**. [Evidence: `{claim.id}`; run `{claim.run_id}`.]"


def number_text(value: float) -> str:
    return str(int(value)) if value.is_integer() else repr(value)


def render(ws: Workspace, doc: Document, *, include_audit: bool = True, include_author: bool = True) -> str:
    problems = validate_document(ws, doc)
    if problems:
        raise ValueError("Manuscript rejected: " + "; ".join(problems))
    lines = [f"# {escape_md(doc.title)}", ""]
    if include_author and doc.author.get("display_name"):
        lines += [escape_md(doc.author["display_name"]), ""]
    if include_author and doc.author.get("affiliation"):
        lines += [escape_md(doc.author["affiliation"]), ""]
    for section in doc.sections:
        lines += [f"## {escape_md(section.heading)}", ""]
        for block in section.blocks:
            if block.kind == "prose":
                lines += [escape_md(block.text), ""]
            elif block.kind == "claim":
                lines += [claim_text(ws.get("claim", block.ref, Claim)), ""]
            else:
                citation = ws.get("citation", block.ref, Citation)
                authors = "; ".join(citation.authors)
                lines += [f"- {escape_md(authors)}. {escape_md(citation.title)} ({citation.year or 'year unavailable'}). DOI: [{escape_md(citation.doi)}](https://doi.org/{quote(citation.doi, safe='/')}). Metadata verified; full-text findings unassessed.", ""]
    if not include_audit:
        return "\n".join(lines)
    lines += ["## Evidence table", "", "| Claim | Metric | Value | Unit | Run |", "|---|---|---:|---|---|"]
    claim_ids = sorted({block.ref for section in doc.sections for block in section.blocks if block.kind == "claim"})
    for id in claim_ids:
        claim = ws.get("claim", id, Claim)
        lines.append(f"| {id} | {escape_md(claim.metric_name)} | {number_text(claim.value)} | {escape_md(claim.unit)} | {claim.run_id} |")
    lines += ["", "## Reproducibility record", ""]
    project = ws.get("project", ws.get("study", doc.study_id, Study).project_id, Project)
    lines += [f"Source commit: `{project.source_commit or 'not a Git project'}`.", f"Snapshot SHA-256: `{project.snapshot_digest}`.", ""]
    for run_id in sorted({ws.get("claim", id, Claim).run_id for id in claim_ids}):
        run = ws.get("run", run_id, ExperimentRun)
        lines += [f"Run `{run.id}` ({run.status}); seed `{run.seed}`; UTC start `{run.started_at}`.", "", "```json", json.dumps({"command": run.command, "environment": run.environment, "raw_artifacts": [asset.model_dump() for asset in run.artifacts], "processed_sha256": run.processed_sha256}, indent=2), "```", ""]
    lines += ["## Automation provenance", "", "Draft generated with Paper Factory's deterministic templates. These templates do not assess scientific merit, literature coverage or publication readiness.", ""]
    if doc.ai_provenance:
        lines += ["The author recorded the following AI assistance. Venue-specific disclosure requirements have not yet been checked.", ""]
        for activity in doc.ai_provenance:
            lines += [f"- {escape_md(activity['role'])}: {escape_md(activity['tool'])}; model {escape_md(activity['model'] or 'unspecified')}; record `{activity['id']}`.", ""]
    else:
        lines += ["No AI activity was recorded for this study. The author must confirm the accuracy of this record before scientific freeze.", ""]
    return "\n".join(lines)


def build(ws: Workspace, study: Study, pandoc: str | None = None, pdf: bool = False, author_values: dict | None = None) -> tuple[Paper, Path]:
    with ws.lock(f"draft-{study.id}"):
        existing = [paper for paper in ws.list("paper", Paper) if paper.study_id == study.id]
        if existing:
            with ws.lock(f"paper-{existing[0].id}"):
                return _build(ws, study, pandoc, pdf, author_values)
        return _build(ws, study, pandoc, pdf, author_values)


def _build(ws: Workspace, study: Study, pandoc: str | None, pdf: bool, author_values: dict | None) -> tuple[Paper, Path]:
    existing = [paper for paper in ws.list("paper", Paper) if paper.study_id == study.id]
    paper = existing[0] if existing else None
    if paper and (paper.state == PaperState.AUTHOR_APPROVED or (ws.root / "freezes" / paper.id).exists()):
        raise ValueError("Approved manuscript is frozen; Phase 1 cannot rewrite it")
    claims: list[Claim] = []
    for run in ws.list("run", ExperimentRun):
        if run.study_id == study.id and run.status == "SUCCEEDED":
            claims.extend(claims_for_run(ws, run))
    if not claims:
        raise ValueError("No successful experimental evidence. Run an experiment before drafting.")
    if paper is None:
        paper = Paper(study_id=study.id, title=study.title, claim_ids=[], citation_ids=[], manuscript_sha256="", document_sha256="")
    blocks = [Block(kind="claim", ref=claim.id) for claim in claims]
    sections = [
        Section(heading="Abstract", blocks=[prose("We present a reproducible descriptive analysis of the supplied research assets. The measured outcomes below are limited to the recorded commands and inputs."), *blocks]),
        Section(heading="Introduction", blocks=[prose("A transparent account of available research assets can support study planning. This report documents observations and their provenance, without establishing scientific originality.")]),
        Section(heading="Related Work", blocks=[prose("Bibliographic metadata can identify potentially relevant work. The records below have been checked against the registry; their full text and specific findings have not been assessed."), *[Block(kind="citation", ref=id) for id in study.citation_ids]]),
        Section(heading="Research Questions", blocks=[prose(study.research_question)]),
        Section(heading="Method", blocks=[prose("The configured analysis commands were executed on isolated copies of the imported snapshot. Named numeric outputs were extracted using declared JSON pointers without estimating missing measurements.")]),
        Section(heading="Experimental Setup", blocks=[prose("The reproducibility record identifies the source version, command, environment, seed, timestamps and artifact checksums. The execution environment isolates working files but is not a security sandbox.")]),
        Section(heading="Results", blocks=blocks),
        Section(heading="Discussion", blocks=[prose("The observations answer only the operational measurements defined in the experiment manifests. Broader interpretation requires appropriate baselines, domain knowledge and independent validation.")]),
    ]
    if study.domain == "software_engineering":
        sections.append(Section(heading="Threats to Validity", blocks=[prose("Repository composition is sensitive to file inclusion rules. Static asset counts do not measure software quality or user outcomes. Independent projects and runtime evaluations are required for general conclusions.")]))
    sections += [Section(heading="Limitations", blocks=[prose(text) for text in study.limitations]), Section(heading="Conclusion", blocks=[prose("This report provides an auditable descriptive record. Further research is required before interpreting the measurements as a publishable contribution.")])]
    root = ws.root / "manuscripts" / paper.id
    root.mkdir(parents=True, exist_ok=True)
    if (root / "canonical.json").is_file():
        doc = Document.model_validate_json((root / "canonical.json").read_text(encoding="utf-8"))
        if doc.paper_id != paper.id or doc.study_id != study.id:
            raise ValueError("Canonical manuscript identity differs from its paper")
        for section in doc.sections:
            if section.heading in {"Abstract", "Results"}:
                section.blocks = [block for block in section.blocks if block.kind != "claim"] + blocks
            elif section.heading == "Related Work":
                section.blocks = [block for block in section.blocks if block.kind != "citation"] + [Block(kind="citation", ref=id) for id in study.citation_ids]
        profile = load_author(explicit=author_values, project_metadata=doc.author)
        doc.author = profile.model_dump()
        doc.ai_provenance = ai_activities(ws, study.id, paper.id)
    else:
        profile = load_author(explicit=author_values)
        doc = Document(paper_id=paper.id, study_id=study.id, title=study.title, domain=study.domain, author=profile.model_dump(), sections=sections, limitations=study.limitations, ai_provenance=ai_activities(ws, study.id, paper.id))
    content = render(ws, doc)
    write_json(root / "canonical.json", doc)
    (root / "manuscript.md").write_text(content, encoding="utf-8")
    write_json(root / "author.json", profile.model_dump())
    paper.state = PaperState.MANUSCRIPT_DRAFTED
    paper.title = doc.title
    paper.claim_ids = list(dict.fromkeys(block.ref for section in doc.sections for block in section.blocks if block.kind == "claim"))
    paper.citation_ids = list(dict.fromkeys(block.ref for section in doc.sections for block in section.blocks if block.kind == "citation"))
    paper.manuscript_sha256 = digest_file(root / "manuscript.md")
    paper.document_sha256 = digest_file(root / "canonical.json")
    ws.save("paper", paper)
    write_json(root / "paper.json", paper)
    ws.save("provenance", Provenance(role="manuscript drafting", tool="paperfactory deterministic renderer", inputs=[study.id, *paper.claim_ids, *paper.citation_ids], outputs=[paper.id]))
    compile_manuscript(ws, paper, pandoc=pandoc, pdf=pdf)
    return paper, root


def refresh(ws: Workspace, paper: Paper, pandoc: str | None = None, pdf: bool = False) -> tuple[Paper, Path]:
    """Validate and render the author's edited canonical document.

    This is the explicit edit path: templates are not regenerated and evidence
    references are verified before the edited version becomes reviewable.
    """
    with ws.lock(f"paper-{paper.id}"):
        return _refresh(ws, paper, pandoc, pdf)


def _refresh(ws: Workspace, paper: Paper, pandoc: str | None, pdf: bool) -> tuple[Paper, Path]:
    current = ws.get("paper", paper.id, Paper)
    if current.state == PaperState.AUTHOR_APPROVED or (ws.root / "freezes" / paper.id).exists():
        raise ValueError("Approved manuscript is frozen; cannot render author edits")
    from .revisions import assert_editable
    assert_editable(ws, current)
    root = ws.root / "manuscripts" / paper.id
    doc = Document.model_validate_json((root / "canonical.json").read_text(encoding="utf-8"))
    if doc.paper_id != current.id or doc.study_id != current.study_id:
        raise ValueError("Canonical manuscript identity differs from its paper")
    content = render(ws, doc)
    (root / "manuscript.md").write_text(content, encoding="utf-8")
    write_json(root / "author.json", doc.author)
    current.title = doc.title
    current.claim_ids = list(dict.fromkeys(block.ref for section in doc.sections for block in section.blocks if block.kind == "claim"))
    current.citation_ids = list(dict.fromkeys(block.ref for section in doc.sections for block in section.blocks if block.kind == "citation"))
    current.manuscript_sha256 = digest_file(root / "manuscript.md")
    current.document_sha256 = digest_file(root / "canonical.json")
    current.state = PaperState.MANUSCRIPT_DRAFTED
    ws.save("paper", current)
    write_json(root / "paper.json", current)
    ws.save("provenance", Provenance(role="author manuscript revision", tool="paperfactory canonical renderer", inputs=[current.id, current.document_sha256], outputs=[current.id]))
    compile_manuscript(ws, current, pandoc=pandoc, pdf=pdf)
    return current, root


def compile_manuscript(ws: Workspace, paper: Paper, pandoc: str | None = None, pdf: bool = False) -> dict:
    current = ws.get("paper", paper.id, Paper)
    if current.state == PaperState.AUTHOR_APPROVED or (ws.root / "freezes" / paper.id).exists():
        raise ValueError("Approved manuscript is frozen; use a separate venue compilation")
    root = ws.root / "manuscripts" / paper.id
    binary = pandoc or shutil.which("pandoc")
    if binary:
        located = shutil.which(binary) or binary
        if Path(located).is_file():
            binary = str(Path(located).resolve())
    output = root / ("manuscript.pdf" if pdf else "manuscript.tex")
    for stale in (root / "manuscript.tex", root / "manuscript.pdf", root / "manuscript.typ", root / "manuscript-pandoc-metadata.json"):
        stale.unlink(missing_ok=True)
    command = [binary or "pandoc", str(root / "manuscript.md"), "--from=markdown-smart-raw_tex-raw_html", "--standalone", "--to=latex", "-V", "geometry:margin=1in", "-o", str(output)]
    report = {"status": "COMPILE_READY", "command": command, "message": "Install Pandoc for standalone LaTeX; install the optional PDF extra for Pandoc/Typst PDF compilation."}
    if binary:
        try:
            if pdf:
                result = convert(root / "manuscript.md", output, pandoc=binary)
                command = result["command"]
                report = {"status": "COMPILED", "command": command, "output": output.name, "engine": result["engine"], "exit_code": 0, "sha256": result["output_sha256"], "diagnostics": result["diagnostics"]}
            else:
                result = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, check=False)
                report = {"status": "COMPILED" if result.returncode == 0 and output.is_file() else "FAILED", "command": command, "output": output.name, "exit_code": result.returncode, "diagnostics": result.stderr}
                if report["status"] == "COMPILED":
                    report["sha256"] = digest_file(output)
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            report = {"status": "FAILED", "command": command, "message": str(exc)}
    report["input_sha256"] = digest_file(root / "manuscript.md")
    report["document_sha256"] = digest_file(root / "canonical.json")
    (root / "compile-command.json").write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8")
    write_json(root / "compile-report.json", report)
    if report["status"] == "FAILED":
        raise ValueError("Pandoc export failed; canonical manuscript preserved. See compile-report.json")
    return report

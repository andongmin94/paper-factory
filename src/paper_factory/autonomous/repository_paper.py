"""Source-bound papers about software design; no experiment authority."""

from typing import Annotated, Literal
import hashlib
import re
from urllib.parse import urlparse

from pydantic import Field, ValidationInfo, model_validator

from ..models import Record
from ..publication_venues import publication_catalog

Text = Annotated[str, Field(min_length=12, max_length=6000)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SECTIONS = ("Abstract", "Introduction", "Related Work", "Method", "Repository Analysis",
            "Discussion", "Limitations", "Conclusion")


class SourceEvidence(Record):
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,79}$")
    path: str = Field(min_length=1, max_length=300)
    sha256: Digest
    quote: str = Field(min_length=12, max_length=6000)
    interpretation: Text


class PublicationCandidate(Record):
    venue_id: str = Field(min_length=3, max_length=100)
    fit: Literal["suitable", "needs_evidence", "out_of_scope"]
    reason: Text
    missing_evidence: list[Text] = Field(max_length=12)


class PublicationTarget(Record):
    venue_id: str = Field(min_length=3, max_length=100)
    article_category: str = Field(min_length=3, max_length=100)
    selection_reason: Text
    candidates: list[PublicationCandidate] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def supported_target(self, info: ValidationInfo):
        catalog = info.context["publication_catalog"] if info.context and "publication_catalog" in info.context else publication_catalog()
        venues = {venue["id"]: venue for venue in catalog["venues"]}
        allowed = set(venues)
        ids = [candidate.venue_id for candidate in self.candidates]
        if len(set(ids)) != len(ids) or set(ids) != allowed:
            raise ValueError("Publication selection must assess every supported IEEE magazine exactly once")
        selected = next((candidate for candidate in self.candidates if candidate.venue_id == self.venue_id), None)
        if selected is None or selected.fit != "suitable":
            raise ValueError("The selected publication target must be a suitable supported journal")
        if self.article_category not in venues[self.venue_id]["article_categories"]:
            raise ValueError("The selected article category is not supported by this journal")
        return self


class RepositoryPlan(Record):
    publication_target: PublicationTarget
    article_type: Literal["software_tool", "design_case_study", "technical_analysis"]
    title: str = Field(min_length=8, max_length=300)
    question: Text
    contribution: Text
    analysis_method: Text
    comparison_dimensions: list[Text] = Field(min_length=1, max_length=12)
    source_files: list[str] = Field(min_length=1, max_length=20)
    source_evidence: list[SourceEvidence] = Field(min_length=1, max_length=24)
    literature_queries: list[str] = Field(min_length=1, max_length=4)
    limitations: list[Text] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def unique_evidence(self):
        if len(set(self.source_files)) != len(self.source_files) or len({e.id for e in self.source_evidence}) != len(self.source_evidence):
            raise ValueError("Source files and evidence IDs must be unique")
        if any(e.path not in self.source_files for e in self.source_evidence):
            raise ValueError("Plan evidence must use the selected source files")
        return self


class LiteratureEvidence(Record):
    source_id: str = Field(min_length=1, max_length=100)
    text_sha256: Digest
    quote: str = Field(min_length=24, max_length=6000)
    interpretation: Text


EvidenceIds = Annotated[list[str], Field(min_length=1, max_length=40)]


class AnalysisDimension(Record):
    dimension: str = Field(min_length=3, max_length=100)
    definition: Text


class AnalysisObservation(Record):
    dimension: str = Field(min_length=3, max_length=100)
    finding: Text
    evidence_ids: EvidenceIds


class AnalysisUnit(Record):
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,79}$")
    label: str = Field(min_length=3, max_length=300)
    evidence_ids: EvidenceIds
    observations: list[AnalysisObservation] = Field(min_length=1, max_length=20)


class AnalysisFinding(Record):
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,79}$")
    claim: Text
    unit_ids: EvidenceIds
    evidence_ids: EvidenceIds
    limitations: Text


class AnalysisCounterexample(Record):
    finding_id: str = Field(min_length=1, max_length=80)
    condition: Text
    evidence_ids: EvidenceIds
    implication: Text


class RepositoryAnalysis(Record):
    """Actual coded observations precede manuscript prose and remain auditable."""
    method: Text
    codebook: list[AnalysisDimension] = Field(min_length=1, max_length=12)
    units: list[AnalysisUnit] = Field(min_length=1, max_length=24)
    findings: list[AnalysisFinding] = Field(min_length=1, max_length=20)
    counterexamples: list[AnalysisCounterexample] = Field(min_length=1, max_length=20)
    source_evidence: list[SourceEvidence] = Field(min_length=1, max_length=40)
    literature_evidence: list[LiteratureEvidence] = Field(max_length=20)
    document_evidence: list[LiteratureEvidence] = Field(max_length=20)
    limitations: list[Text] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def connected_analysis(self):
        groups = ([item.dimension for item in self.codebook], [item.id for item in self.units],
                  [item.id for item in self.findings], [item.id for item in self.source_evidence])
        if any(len(set(items)) != len(items) for items in groups):
            raise ValueError("Analysis dimensions, units, findings and source evidence IDs must be unique")
        dimensions, units, findings, evidence = map(set, groups)
        used_evidence, used_units, used_dimensions = set(), set(), set()

        def known(ids, allowed, label):
            if len(set(ids)) != len(ids) or not set(ids).issubset(allowed):
                raise ValueError("Analysis " + label + " must bind unique existing identifiers")
            return set(ids)

        by_unit = {}
        for unit in self.units:
            by_unit[unit.id] = known(unit.evidence_ids, evidence, "unit evidence")
            used_evidence.update(unit.evidence_ids)
            for observation in unit.observations:
                if observation.dimension not in dimensions:
                    raise ValueError("Analysis observation must use a defined codebook dimension")
                used_dimensions.add(observation.dimension)
                used_evidence.update(known(observation.evidence_ids, by_unit[unit.id], "observation evidence"))
        for finding in self.findings:
            used_units.update(known(finding.unit_ids, units, "finding units"))
            unit_evidence = set().union(*(by_unit[identifier] for identifier in finding.unit_ids))
            used_evidence.update(known(finding.evidence_ids, unit_evidence, "finding evidence"))
        for counterexample in self.counterexamples:
            if counterexample.finding_id not in findings:
                raise ValueError("Analysis counterexample must qualify an existing finding")
            used_evidence.update(known(counterexample.evidence_ids, evidence, "counterexample evidence"))
        if used_units != units or used_evidence != evidence or used_dimensions != dimensions:
            raise ValueError("Every retained analysis dimension, unit and witness must support an actual result")
        if any(len({(item.source_id, item.text_sha256, item.quote) for item in items}) != len(items)
               for items in (self.literature_evidence, self.document_evidence)):
            raise ValueError("Analysis comparison passages must not repeat the same source, digest and literal quote")
        return self


class RepositoryReference(Record):
    url: str = Field(min_length=12, max_length=2048)
    purpose: Literal["comparison", "venue"]
    reason: Text


class RepositoryVenueSuggestion(Record):
    name: str = Field(min_length=3, max_length=300)
    url: str = Field(min_length=12, max_length=2048)
    reason: Text


class RepositoryReferenceSelection(Record):
    references: list[RepositoryReference] = Field(min_length=1, max_length=5)
    venue_suggestions: list[RepositoryVenueSuggestion] = Field(max_length=3)


class RepositorySection(Record):
    heading: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=80, max_length=30000)


class RepositoryRevision(Record):
    prior_draft_sha256: Digest
    changes: list[Text] = Field(min_length=1, max_length=12)


class RepositoryManuscript(Record):
    title: str = Field(min_length=8, max_length=300)
    sections: list[RepositorySection] = Field(min_length=4, max_length=12)
    source_evidence: list[SourceEvidence] = Field(min_length=1, max_length=40)
    literature_evidence: list[LiteratureEvidence] = Field(max_length=20)
    document_evidence: list[LiteratureEvidence] = Field(max_length=20)
    revision: RepositoryRevision | None

    @model_validator(mode="after")
    def complete_sections(self):
        headings = [s.heading for s in self.sections]
        scientific = [heading for heading in headings if heading.casefold() not in {"acknowledgments", "reference", "references"}]
        if len(set(heading.casefold() for heading in headings)) != len(headings) or scientific[0] != "Abstract" or len(scientific) < 4:
            raise ValueError("A Feature Article requires Abstract first and at least three uniquely titled full body sections")
        ids = [e.id for e in self.source_evidence]
        if len(set(ids)) != len(ids):
            raise ValueError("Manuscript source evidence IDs must be unique")
        return self


class RepositoryCriterion(Record):
    passed: bool
    reason: Text


class RepositoryCriteria(Record):
    venue_fit: RepositoryCriterion
    supported_findings: RepositoryCriterion
    contribution: RepositoryCriterion
    literature: RepositoryCriterion
    method: RepositoryCriterion
    presentation: RepositoryCriterion
    empirical_claims_absent: RepositoryCriterion


class RepositoryAction(Record):
    action: Literal["revise_source_analysis", "retrieve_literature", "retrieve_documentation", "revise_manuscript", "human_validation", "infeasible"]
    target: str = Field(min_length=3, max_length=300)
    required_change: Text
    verification: Text


class RepositoryRevisionOutline(Record):
    heading: str = Field(min_length=1, max_length=100)
    instruction: Text


class RepositoryRevisionFeedback(Record):
    issues: list[Text] = Field(min_length=1, max_length=12)
    next_actions: list[RepositoryAction] = Field(min_length=1, max_length=12)
    revision_outline: list[RepositoryRevisionOutline] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def actual_revision_actions(self):
        if any(item.action in {"human_validation", "infeasible"} for item in self.next_actions):
            raise ValueError("External feedback must request actual source, evidence or manuscript revision")
        return self


class RepositoryPdfCandidate(Record):
    doi: str = Field(min_length=8, max_length=500)
    title: str = Field(min_length=8, max_length=500)
    url: str = Field(min_length=12, max_length=2048)


class RepositoryContentAssessment(Record):
    comparison: RepositoryCriterion
    contribution: RepositoryCriterion
    issues: list[Text] = Field(max_length=12, description="Blocking comparison or contribution defects only. Return [] when both criteria pass; place optional advice in criterion reasons.")
    next_actions: list[RepositoryAction] = Field(max_length=12, description="Required actions that resolve blocking content defects; return [] when content passes.")
    literature_queries: list[Annotated[str, Field(min_length=8, max_length=200)]] = Field(max_length=2)
    pdf_candidates: list[RepositoryPdfCandidate] = Field(max_length=2)
    revision_outline: list[RepositoryRevisionOutline] = Field(max_length=4)

    @property
    def content_ready(self):
        return self.comparison.passed and self.contribution.passed and not self.issues

    @model_validator(mode="after")
    def actionable_outline(self):
        if self.content_ready and (self.next_actions or self.literature_queries or self.pdf_candidates or self.revision_outline):
            raise ValueError("Ready content cannot retain blocking repair plans")
        if not self.content_ready and (not self.issues or not self.next_actions or not self.revision_outline):
            raise ValueError("Content gaps require a concrete repair outline and retained actions")
        retrieval = any(item.action == "retrieve_literature" for item in self.next_actions)
        if retrieval != bool(self.literature_queries) or self.pdf_candidates and not retrieval:
            raise ValueError("Content retrieval actions must bind their exact planned queries and PDF candidates")
        if len(set(self.literature_queries)) != len(self.literature_queries):
            raise ValueError("Content retrieval queries must be unique")
        return self


class RepositoryReview(Record):
    criteria: RepositoryCriteria
    issues: list[Text] = Field(max_length=20, description="Blocking scientific defects only. Return [] when all criteria pass; optional advice and statements that no blocker exists belong in criterion reasons.")
    next_actions: list[RepositoryAction] = Field(max_length=12)
    content_assessment: RepositoryContentAssessment | None = None

    @property
    def scientific_ready(self):
        return all(item.passed for item in self.criteria.__dict__.values()) and not self.issues

    @model_validator(mode="after")
    def concrete_repair(self):
        if not self.scientific_ready and (not self.issues or not self.next_actions):
            raise ValueError("A rejected repository manuscript needs concrete issues and next actions")
        return self


_MARKDOWN_LITERALS = re.compile(
    r"^ {0,3}(?P<tildes>~{3,})[^\n]*\n.*?^ {0,3}(?P=tildes)~*[ \t]*(?:\n|$)"
    r"|(?P<ticks>`+).*?(?P=ticks)"
    r"|!?\[(?:\\.|[^\]\\\n])*\](?:\((?:\\.|[^)\\\n])*\)|\[(?:\\.|[^\]\\\n])*\])"
    r"|<[^>\n]+>|https?://\S+", re.MULTILINE | re.DOTALL)


def literal_source_paths(text: str, source_paths: list[str]) -> str:
    """Render known source paths literally, leaving existing Markdown literals intact."""
    if not source_paths:
        return text
    paths = re.compile(r"(?<![\w./\\-])(?:" + "|".join(re.escape(path) for path in sorted(set(source_paths), key=len, reverse=True)) +
                       r")(?=$|[^\w/\\.-]|\.(?=\s|$))")

    def code(match):
        path = match.group()
        fence = "`" * (max((len(run) for run in re.findall(r"`+", path)), default=0) + 1)
        padding = " " if path.startswith("`") or path.endswith("`") else ""
        return fence + padding + path + padding + fence

    parts, end = [], 0
    for protected in _MARKDOWN_LITERALS.finditer(text):
        parts.extend((paths.sub(code, text[end:protected.start()]), protected.group()))
        end = protected.end()
    parts.append(paths.sub(code, text[end:]))
    return "".join(parts)


_REFERENCE_NOTE = "Repository witnesses are linked to the frozen source revision; literal quotations and bounded interpretations accompany the evidence records."


def _model_references(draft: RepositoryManuscript):
    sections = [section for section in draft.sections if section.heading.casefold() in {"reference", "references"}]
    if len(sections) > 1:
        raise ValueError("Only one model bibliography section may be formatted")
    return sections[0] if sections else None


def _reference_entries(canonical: str, draft: RepositoryManuscript) -> list[str]:
    entries = canonical.removeprefix("## References\n\n").rstrip("\n").split("\n\n")
    count = (len({(item.path, item.sha256) for item in draft.source_evidence}) +
             len({item.source_id for item in draft.literature_evidence}) +
             len({item.source_id for item in draft.document_evidence}))
    if len(entries) != count or any(not item.startswith(f"[{index}] ") or "\n" in item
                                    for index, item in enumerate(entries, 1)):
        raise ValueError("Canonical references must retain every numbered evidence identity")
    return [item.split(" ", 1)[1] for item in entries]


def _reference_path(label: str) -> str | None:
    # Plain escaped labels belong to explicitly retained historical renderings.
    if not label.startswith("`"):
        return re.sub(r"\\([\\`*_\[\]])", r"\1", label)
    code = re.fullmatch(r"(`+)([^\n]+?)\1", label)
    if code is None or code[1] in code[2]:
        return None
    value = code[2]
    return value[1:-1] if value.startswith(" ") and value.endswith(" ") and value.strip(" ") else value


def _source_code_label(path: str) -> str:
    fence = "`" * (max((len(run) for run in re.findall(r"`+", path)), default=0) + 1)
    padding = " " if (path.startswith("`") or path.endswith("`") or
                      (path.strip(" ") and (path.startswith(" ") or path.endswith(" ")))) else ""
    return fence + padding + path + padding + fence


def _bibliography_only(text: str, entries: list[str]) -> int:
    """Accept duplicate bibliography records, never interpret arbitrary prose as removable."""
    lines = [line for line in text.splitlines() if line.strip()]
    if lines and lines[0] == _REFERENCE_NOTE:
        lines.pop(0)
    identities = []
    for line in lines:
        if not line.startswith(("- ", "* ")):
            raise ValueError("Model References contain non-bibliographic or ambiguous prose")
        entry = line[2:]
        matches = []
        for index, canonical in enumerate(entries):
            if entry == canonical:
                matches.append(index)
                continue
            source = re.fullmatch(r"\[([^\n]+)\]\((https?://[^\s)]+)\)\. Repository revision: [^.]+\.", canonical)
            manual_source = re.fullmatch(r"\[(`+[^\n]+?`+)\]\((https?://[^\s)]+)\)\.", entry)
            if source and manual_source and _reference_path(source[1]) is not None and (
                    _reference_path(source[1]), source[2]) == (_reference_path(manual_source[1]), manual_source[2]):
                matches.append(index)
                continue
            document = re.fullmatch(r"\[(https?://[^\s\]]+)\]\(\1\)\. Accessed \d{4}-\d{2}-\d{2}\.", canonical)
            manual_document = re.fullmatch(r'([\w-]+) contributors, [“"]([^”"\n]+?)(?:,[”"]|[”"],) inspected documentation snapshot, (https?://[^\s]+)\.', entry)
            if document and manual_document:
                url = urlparse(document[1])
                normalized = lambda value: re.sub(r"\W", "", value).casefold()
                if (manual_document[3] == document[1] and normalized(manual_document[1]) in normalized(url.hostname or "")
                        and normalized(manual_document[2]) == normalized(url.path.rsplit("/", 1)[-1])):
                    matches.append(index)
                    continue
            article = re.fullmatch(r"(.+)\. (.+) \((\d{4})\)\. https://arxiv\.org/(?:pdf|abs)/(\d{4}\.\d{4,5}v\d+)\.", canonical)
            manual_article = re.fullmatch(r'([^\n]+), [“"]([^”"\n]+?)(?:,[”"]|[”"],) arXiv:(\d{4}\.\d{4,5}v\d+), (\d{4})\.', entry)
            if article and manual_article and (manual_article[2], manual_article[3], manual_article[4]) == (article[2], article[4], article[3]):
                names = re.findall(r"\w+", article[1].casefold())
                allowed = {*names, *(name[0] for name in names), "and"}
                if set(re.findall(r"\w+", manual_article[1].casefold())).issubset(allowed):
                    matches.append(index)
        if len(matches) != 1:
            raise ValueError("Model bibliography entry must duplicate one canonical reference without scientific prose")
        identities.append(matches[0])
    if sorted(identities) != list(range(len(entries))):
        raise ValueError("Model bibliography must duplicate every canonical identity exactly once")
    return len(identities)


def format_references_only(draft: RepositoryManuscript, markdown: str) -> tuple[str, dict]:
    """Remove one proven duplicate bibliography from an immutable admitted rendering."""
    manual = _model_references(draft)
    if manual is None:
        raise ValueError("No duplicate model bibliography is available to format")
    newline = "\r\n" if "\r\n" in markdown else "\n"
    if newline == "\r\n" and "\n" in markdown.replace("\r\n", ""):
        raise ValueError("Mixed Markdown line endings cannot be formatted safely")
    literals = [match.span() for match in _MARKDOWN_LITERALS.finditer(markdown)]
    headings = [match for match in re.finditer(r"^## ([^\r\n]+)\r?\n", markdown, re.MULTILINE)
                if not any(start <= match.start() < end for start, end in literals)]
    if [match[1] for match in headings] != [section.heading for section in draft.sections] + ["References"]:
        raise ValueError("Retained Markdown must match every typed section and final canonical References")
    index = next(i for i, section in enumerate(draft.sections) if section is manual)
    start, end = headings[index].start(), headings[index + 1].start()
    removed = markdown[start:end]
    expected = "## " + manual.heading + newline * 2 + literal_source_paths(manual.text, [item.path for item in draft.source_evidence]).replace("\n", newline) + newline * 2
    if removed != expected:
        raise ValueError("Retained model bibliography differs from its immutable typed section")
    canonical = markdown[headings[-1].start():]
    entries = _reference_entries(canonical.replace(newline, "\n"), draft)
    removed_entries = _bibliography_only(manual.text, entries)
    formatted = markdown[:start] + markdown[end:]
    before = markdown[:start] + markdown[end:headings[-1].start()]
    after = formatted[:-len(canonical)]
    digest = lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
    return formatted, {"original_markdown_sha256": digest(markdown), "formatted_markdown_sha256": digest(formatted),
        "removed_block_sha256": digest(removed), "canonical_references_sha256": digest(canonical),
        "scientific_body_sha256_before": digest(before), "scientific_body_sha256_after": digest(after),
        "removed_heading": manual.heading, "removed_entries": removed_entries, "reference_numbers": list(range(1, len(entries) + 1))}


def format_source_reference_labels(draft: RepositoryManuscript, markdown: str) -> tuple[str, dict]:
    """Protect source-path labels in one final bibliography, preserving every other byte."""
    newline = "\r\n" if "\r\n" in markdown else "\n"
    if "\r" in markdown.replace("\r\n", "") or (newline == "\r\n" and "\n" in markdown.replace("\r\n", "")):
        raise ValueError("Mixed Markdown line endings cannot be formatted safely")
    literals = [match.span() for match in _MARKDOWN_LITERALS.finditer(markdown)]
    headings = [match for match in re.finditer(r"^## ([^\r\n]+)\r?\n", markdown, re.MULTILINE)
                if not any(start <= match.start() < end for start, end in literals)]
    manual = _model_references(draft)
    if [match[1] for match in headings] != [section.heading for section in draft.sections if section is not manual] + ["References"]:
        raise ValueError("Source-label formatting requires one final canonical bibliography and unchanged typed sections")
    start = headings[-1].start()
    body, canonical = markdown[:start], markdown[start:]
    _reference_entries(canonical.replace(newline, "\n"), draft)
    source_paths = {}
    for item in draft.source_evidence:
        if item.path in source_paths and source_paths[item.path] != item.sha256:
            raise ValueError("Source bibliography has ambiguous retained path identities")
        source_paths[item.path] = item.sha256
    header = "## References" + newline * 2
    records = canonical.removeprefix(header)
    trailing = records[len(records.rstrip("\r\n")):]
    entries = records.rstrip("\r\n").split(newline * 2)
    changed, sources, seen, repositories = [], [], set(), set()
    for index, entry in enumerate(entries, 1):
        if "Repository revision:" not in entry:
            continue
        source = re.fullmatch(r"\[(\d+)\] \[([^\r\n]+)\]\((https?://[^\s)]+)\)\. Repository revision: ([^.\r\n]+)\.", entry)
        if source is None:
            raise ValueError("Source bibliography entry must be an unambiguous canonical record")
        path, url, revision = _reference_path(source[2]), source[3], source[4]
        if path not in source_paths or path in seen:
            raise ValueError("Source bibliography must contain each retained literal path exactly once")
        parsed = urlparse(url)
        repository, marker, target = parsed.path.partition("/blob/")
        expected_revision = "HEAD" if revision == "retained snapshot" else revision
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or
                not marker or target != expected_revision + "/" + path):
            raise ValueError("Source reference URL must retain the same literal path and repository revision")
        repositories.add((parsed.scheme, parsed.netloc, repository, revision))
        seen.add(path)
        identity = {"number": index, "path": path, "url": url, "sha256": source_paths[path]}
        sources.append(identity)
        if not source[2].startswith("`"):
            label = _source_code_label(path)
            entries[index - 1] = entry[:source.start(2)] + label + entry[source.end(2):]
            changed.append({**identity, "original_label": source[2], "formatted_label": label})
    if seen != source_paths.keys() or len(repositories) != 1:
        raise ValueError("Canonical bibliography must retain every source identity from one repository revision")
    formatted_references = header + (newline * 2).join(entries) + trailing
    formatted = body + formatted_references
    digest = lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
    return formatted, {"original_markdown_sha256": digest(markdown), "formatted_markdown_sha256": digest(formatted),
        "scientific_body_sha256_before": digest(body), "scientific_body_sha256_after": digest(formatted[:start]),
        "original_references_sha256": digest(canonical), "formatted_references_sha256": digest(formatted_references),
        "changed_labels": changed, "source_references": sources, "reference_numbers": list(range(1, len(entries) + 1))}


def render(draft: RepositoryManuscript, repository_url: str, commit: str | None, sources: dict, documents: dict,
           source_paths: list[str]) -> str:
    """Number verified citations by first appearance without rewriting prose."""
    evidence = {e.id: e for e in draft.source_evidence}
    source_refs = {(item.path, item.sha256): item for item in draft.source_evidence}
    citations = {e.source_id for e in draft.literature_evidence}
    document_ids = {e.source_id for e in draft.document_evidence}
    literal_paths = list(dict.fromkeys([*source_paths, *(documents[identifier]["path"] for identifier in document_ids
        if identifier in documents and documents[identifier].get("path"))]))
    used_source, used_literature, used_documents = set(), set(), set()
    numbers = {}

    def number(identity):
        if identity not in numbers:
            numbers[identity] = len(numbers) + 1
        return "[" + str(numbers[identity]) + "]"

    def token(match):
        kind, identifier = match.groups()
        if kind == "source":
            if identifier not in evidence:
                raise ValueError("Source citation lacks literal evidence: " + identifier)
            used_source.add(identifier)
            item = evidence[identifier]
            return number(("source", item.path, item.sha256))
        if kind == "document":
            if identifier not in document_ids or identifier not in documents:
                raise ValueError("Documentation citation lacks inspected retained evidence: " + identifier)
            used_documents.add(identifier)
            return number(("document", identifier))
        if identifier not in citations or identifier not in sources:
            raise ValueError("Literature citation lacks inspected evidence: " + identifier)
        used_literature.add(identifier)
        return number(("citation", identifier))

    evidence_token = re.compile(r"\{\{(source|citation|document):([^{}]+)\}\}")
    token_series = re.compile(r"(?:\{\{(?:source|citation|document):[^{}]+\}\}[ \t]*)+")

    def series(match):
        text, parts, end, previous = match.group(), [], 0, None
        for witness in evidence_token.finditer(text):
            label = token(witness)
            if label != previous:
                parts.extend((text[end:witness.start()], label))
            previous, end = label, witness.end()
        parts.append(text[end:])
        return "".join(parts)

    manual = _model_references(draft)
    paragraphs = ["# " + literal_source_paths(draft.title, literal_paths), *["## " + section.heading + "\n\n" + literal_source_paths(re.sub(
        token_series, series, section.text), literal_paths) for section in draft.sections if section is not manual]]
    if not used_source:
        raise ValueError("Repository findings require at least one source citation in the manuscript")
    if citations - used_literature:
        raise ValueError("Retained literature evidence must be cited by the manuscript")
    if document_ids - used_documents:
        raise ValueError("Retained documentation evidence must be cited by the manuscript")
    if any("{{" in paragraph for paragraph in paragraphs):
        raise ValueError("Unknown or unresolved manuscript evidence token")
    refs = {}
    for item in source_refs.values():
        url = repository_url.rstrip("/") + "/blob/" + (commit or "HEAD") + "/" + item.path
        label = _source_code_label(item.path)
        refs[("source", item.path, item.sha256)] = f"[{label}]({url}). Repository revision: {commit or 'retained snapshot'}."
    for identifier in sorted(citations):
        source = sources[identifier]
        authors = source.get("authors", [])
        names = [value if isinstance(value, str) else " ".join(value.get(key, "") for key in ("given", "family")).strip()
                 for value in authors]
        author_text = "; ".join(name for name in names if name)
        refs[("citation", identifier)] = (f"{author_text + '. ' if author_text else ''}{source.get('title', identifier)} ({source.get('year', 'n.d.')}). "
                                         f"{source.get('url') or ('https://doi.org/' + source['doi'] if source.get('doi') else '')}.")
    for identifier in sorted(document_ids):
        source = documents[identifier]
        if "kind" in source:
            label = _source_code_label(source["path"]) if source.get("path") else source["title"]
            revision = f" Repository revision: {source['commit']}." if source.get("commit") else ""
            case = f" Case: {source['case_id']}." if source.get("case_id") else ""
            refs[("document", identifier)] = (f"[{label}]({source['url']}). Supplied {source['kind']}: {source['title']}."
                f"{case}{revision} Provenance: {source['provenance']}. Imported {source['imported_at'][:10]}.")
        else:
            refs[("document", identifier)] = f"[{source['url']}]({source['url']}). Accessed {source['fetched_at'][:10]}."
    # Keep every retained source reference, including any not cited in prose;
    # formatting cannot silently remove evidence to meet a venue limit.
    order = [*numbers, *(identity for identity in refs if identity not in numbers)]
    canonical = "## References\n\n" + "\n\n".join(number(identity) + " " + refs[identity] for identity in order)
    if manual is not None:
        _bibliography_only(manual.text, _reference_entries(canonical, draft))
    paragraphs.append(canonical)
    return "\n\n".join(paragraphs) + "\n"

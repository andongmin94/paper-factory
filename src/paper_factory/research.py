"""Conservative study discovery and a real descriptive baseline experiment."""

import re

from .models import Candidate, ExperimentManifest, Metric, Project, Study
from .project import verify_snapshot
from .workspace import Workspace, write_json

INVENTORY_QUESTION = "What assets and file sizes are present in this sanitized project snapshot?"


def discover(ws: Workspace) -> list[Candidate]:
    verify_snapshot(ws)
    project = ws.latest("project", Project)
    kinds = {asset.kind for asset in project.assets}
    candidates = [Candidate(
        id="asset-inventory", title=f"Descriptive asset inventory of {project.name}",
        research_question=INVENTORY_QUESTION,
        why_it_matters="An auditable inventory establishes which research assets are available before planning substantive studies.",
        what_is_new="No novelty is established. This is a descriptive feasibility baseline, not a publication contribution.",
        required_evidence=["Content hashes and measured file counts and sizes from the imported snapshot"],
        required_experiments=["Run the built-in asset inventory in an isolated copy"],
        likely_field="generic empirical", estimated_additional_work="The baseline runs immediately; publication requires a substantive question, related work and further experiments.",
        incremental_risk="High: an inventory alone is insufficient for a publishable scientific contribution.", score=30,
    )]
    if "code" in kinds:
        candidates.append(Candidate(
            id="code-behavior", title=f"Measured behavior of {project.name}",
            research_question="Under explicitly defined workloads, what measurable behavior does the project exhibit?",
            why_it_matters="Reproducible behavior measurements can establish evidence for a precise research question.",
            what_is_new="Unknown until the mechanism, baseline and related work are assessed.",
            required_evidence=["Real workload definitions", "An appropriate comparison or baseline", "Repeated measured outputs"],
            required_experiments=["Author a project-specific manifest using existing analysis or test scripts"],
            likely_field="software engineering", estimated_additional_work="Define workload, baselines and metrics; the automatic inventory does not answer this question.",
            incremental_risk="Unknown; ordinary engineering validation may not establish a distinct scientific contribution.", score=20,
        ))
    if "data" in kinds:
        candidates.append(Candidate(
            id="data-characterization", title=f"Data characterization in {project.name}",
            research_question="What reproducible properties of the project's data support a substantive domain question?",
            why_it_matters="A validated data analysis can support defensible empirical claims.",
            what_is_new="Unknown; data semantics, permissions and related work need assessment.",
            required_evidence=["Dataset provenance and documented semantics", "Validated analysis outputs", "Appropriate uncertainty estimates"],
            required_experiments=["Author a data-specific analysis manifest after checking provenance and human-subject requirements"],
            likely_field="generic empirical", estimated_additional_work="Inspect dataset meaning and permissions, specify a question and supply a real analysis script.",
            incremental_risk="Unknown; descriptive summaries alone may not be a publication contribution.", score=15,
        ))
    for candidate in candidates:
        ws.save("candidate", candidate)
    write_json(ws.path("studies/candidates.json"), [candidate.model_dump(mode="json") for candidate in candidates])
    return candidates


def _normalize_question(question: str) -> str:
    return " ".join(re.findall(r"\w+", question.casefold(), re.UNICODE))


def create_study(ws: Workspace, candidate_id: str | None = None, question: str | None = None, title: str | None = None,
                 domain: str = "generic_empirical", human_subjects: bool = False) -> Study:
    verify_snapshot(ws)
    project = ws.latest("project", Project)
    with ws.lock(f"project-{project.id}"):
        return _create_study(ws, candidate_id, question, title, domain, human_subjects)


def _create_study(ws: Workspace, candidate_id: str | None, question: str | None, title: str | None,
                  domain: str, human_subjects: bool) -> Study:
    project = ws.latest("project", Project)
    if question is None:
        candidates = ws.list("candidate", Candidate) or discover(ws)
        candidate = next((candidate for candidate in candidates if candidate.id == (candidate_id or "asset-inventory")), None)
        if candidate is None:
            raise ValueError(f"Unknown study candidate: {candidate_id}")
        question = candidate.research_question
        title = title or candidate.title
    if not _normalize_question(question):
        raise ValueError("A nonempty research question is required")
    for existing in ws.list("study", Study):
        if existing.project_id == project.id and _normalize_question(existing.research_question) == _normalize_question(question):
            raise ValueError(f"Duplicate study question and project assets: {existing.id}")
    study = Study(project_id=project.id, title=title or question, research_question=question, domain=domain, human_subjects=human_subjects)
    ws.save("study", study)
    write_json(ws.path(f"studies/{study.id}.json"), study)
    return study


INVENTORY_SCRIPT = '''import hashlib, json, os
from pathlib import Path
root = Path.cwd()
files = []
for directory, dirs, names in os.walk(root, followlinks=False):
    dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
    for name in sorted(names):
        path = Path(directory) / name
        if path.is_file() and not path.is_symlink():
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            files.append({"path": path.relative_to(root).as_posix(), "size": path.stat().st_size, "sha256": digest})
files.sort(key=lambda item: item["path"])
result = {"file_count": len(files), "total_bytes": sum(item["size"] for item in files), "files": files,
          "scope": "descriptive sanitized snapshot inventory; no novelty or causal inference"}
output = root / ".paperfactory-results" / "inventory.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\\n", encoding="utf-8")
'''


def plan(ws: Workspace, study: Study) -> ExperimentManifest:
    verify_snapshot(ws)
    stored = ws.get("study", study.id, Study)
    if stored != study:
        raise ValueError("Study does not match its persisted record")
    project = ws.latest("project", Project)
    if study.project_id != project.id:
        raise ValueError("Study belongs to a different project")
    if _normalize_question(study.research_question) != _normalize_question(INVENTORY_QUESTION):
        raise ValueError("The automatic plan only answers the descriptive asset-inventory question; register a real study-specific experiment manifest for this question")
    if (ws.root / "source" / ".paperfactory-results" / "inventory.json").exists():
        raise ValueError("Source already contains the built-in inventory output path; use a custom manifest with a distinct output")
    manifest = ExperimentManifest(
        study_id=study.id, source_commit=project.source_commit, source_digest=project.snapshot_digest,
        command=["{python}", "-c", INVENTORY_SCRIPT], inputs=[asset.path for asset in project.assets],
        expected_outputs=[".paperfactory-results/inventory.json"],
        metrics=[Metric(name="file_count", output=".paperfactory-results/inventory.json", pointer="/file_count", unit="files", description="Number of regular files in the sanitized snapshot"),
                 Metric(name="total_bytes", output=".paperfactory-results/inventory.json", pointer="/total_bytes", unit="bytes", description="Sum of file sizes in the sanitized snapshot")],
        human_subjects=study.human_subjects,
    )
    write_json(ws.path(f"experiments/{manifest.id}.json"), manifest)
    ws.save("manifest", manifest)
    return manifest

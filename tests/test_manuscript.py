import json
import stat

import httpx
import pytest

from paper_factory import evidence, experiments, integrity, literature, manuscript, project, research
from paper_factory.author import AuthorProfile
from paper_factory.models import Claim, ExperimentRun, Paper, PaperState, Provenance, Study, uid
from paper_factory.workspace import digest_file, write_json


@pytest.fixture
def workspace_case(tmp_path, monkeypatch):
    for field in AuthorProfile.model_fields:
        monkeypatch.delenv(f"PF_AUTHOR_{field.upper()}", raising=False)
    monkeypatch.delenv("PF_AUTHOR_PROFILE_JSON", raising=False)
    monkeypatch.setenv("PF_AUTHOR_DISPLAY_NAME", "Example Researcher")
    monkeypatch.setenv("PF_AUTHOR_EMAIL", "researcher@example.org")
    monkeypatch.setenv("PF_AUTHOR_AFFILIATION", "Example University")
    monkeypatch.setenv("PF_HOME", str(tmp_path / "home"))
    original_which = manuscript.shutil.which
    monkeypatch.setattr(manuscript.shutil, "which", lambda command, *args, **kwargs: None if command == "pandoc" else original_which(command, *args, **kwargs))
    source = tmp_path / "fixture-project"
    source.mkdir()
    (source / "analysis.py").write_text("print('analysis fixture')\n", encoding="utf-8")
    (source / "data.csv").write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
    (source / "notes.md").write_text("Documented local research assets.\n", encoding="utf-8")
    ws = project.ingest(str(source), tmp_path / "workspace")
    research.discover(ws)
    study = research.create_study(ws, domain="software_engineering")
    manifest = research.plan(ws, study)
    return source, ws, study, manifest


@pytest.fixture
def built_case(workspace_case):
    source, ws, study, manifest = workspace_case
    run = experiments.run_experiment(ws, manifest)
    assert run.status == "SUCCEEDED", run.error
    paper, root = manuscript.build(ws, study)
    return source, ws, study, run, paper, root


def mocked_search(ws, study):
    def respond(request):
        if request.url.path == "/works":
            return httpx.Response(200, json={"status": "ok", "message": {"items": [{"DOI": "10.1234/reproducibility"}]}})
        return httpx.Response(200, json={
            "status": "ok", "message": {
                "DOI": "10.1234/reproducibility", "title": ["Auditable Research Practices"],
                "author": [{"given": "Example", "family": "Scholar"}], "published": {"date-parts": [[2025]]},
            },
        })
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        return literature.search(ws, "auditable research", study, client=client)


def freeze_ready(workspace_case):
    _, ws, study, manifest = workspace_case
    mocked_search(ws, study)
    assert experiments.run_experiment(ws, manifest).status == "SUCCEEDED"
    paper, root = manuscript.build(ws, study)
    return ws, study, paper, root


def replace_canonical(ws, paper, root, change):
    """Update the build checksum too, so the semantic guard itself is exercised."""
    document = json.loads((root / "canonical.json").read_text(encoding="utf-8"))
    change(document)
    write_json(root / "canonical.json", document)
    paper.document_sha256 = digest_file(root / "canonical.json")
    ws.save("paper", paper)


def test_local_end_to_end_has_measured_claims_and_compile_ready_manuscript(built_case):
    source, ws, study, run, paper, root = built_case
    original = project.inventory(source)
    report = integrity.check(ws, paper)
    assert report["passed"], report["errors"]
    assert report["claim_count"] == 2
    assert ws.get("paper", paper.id, Paper).state is PaperState.INTEGRITY_CHECKED
    raw = json.loads((ws.root / "runs" / run.id / "raw" / ".paperfactory-results" / "inventory.json").read_text(encoding="utf-8"))
    assert raw["file_count"] == len(original) == run.metrics["file_count"]
    assert raw["total_bytes"] == sum(asset.size for asset in original)
    assert all(not evidence.verify_claim(ws, claim) for claim in ws.list("claim", Claim))
    text = (root / "manuscript.md").read_text(encoding="utf-8")
    assert "## Threats to Validity" in text
    assert "## Evidence table" in text
    assert "Snapshot SHA-256" in text
    assert json.loads((root / "compile-report.json").read_text(encoding="utf-8"))["status"] == "COMPILE_READY"
    assert (root / "compile-command.json").is_file()
    assert project.inventory(source) == original
    assert not (source / ".paper-factory").exists()


@pytest.mark.parametrize("heading", ["Accuracy achieved 99 percent", "The first novel experimental approach"])
def test_new_section_headings_cannot_introduce_unsupported_results_or_novelty(built_case, heading):
    _, ws, _, _, paper, root = built_case
    doc = manuscript.Document.model_validate_json((root / "canonical.json").read_bytes())
    doc.sections.append(manuscript.Section(heading=heading, blocks=[manuscript.prose("This additional interpretation is presented for author review.")]))
    write_json(root / "canonical.json", doc)
    with pytest.raises(ValueError, match="Unsupported quantitative prose|Unsupported novelty"):
        manuscript.refresh(ws, paper)


@pytest.mark.parametrize("description", ["Accuracy achieved 99 percent", "Latency reduced by ninety percent", "The first novel performance measure", "See DOI: 10.1234/unverified"])
def test_actual_metric_results_do_not_license_unverified_claims_in_description(workspace_case, description):
    _, ws, study, source = workspace_case
    manifest = source.model_copy(update={"id": uid("experiment")}, deep=True)
    manifest.metrics[0].description = description
    manifest_path = ws.path("metric-description-test.json")
    write_json(manifest_path, manifest)
    experiments.register_manifest(ws, manifest_path)
    assert experiments.run_experiment(ws, manifest).status == "SUCCEEDED"
    with pytest.raises(ValueError, match="metric label"):
        manuscript.build(ws, study)


@pytest.mark.parametrize("unit", ["files; accuracy improved 99 percent", "Latency reduced by ninety percent", "The first novel method", "See DOI: 10.1234/unverified"])
def test_actual_metric_results_do_not_license_unverified_claims_in_unit(workspace_case, unit):
    _, ws, study, source = workspace_case
    manifest = source.model_copy(update={"id": uid("experiment")}, deep=True)
    manifest.metrics[0].unit = unit
    manifest_path = ws.path("metric-unit-test.json")
    write_json(manifest_path, manifest)
    experiments.register_manifest(ws, manifest_path)
    assert experiments.run_experiment(ws, manifest).status == "SUCCEEDED"
    with pytest.raises(ValueError, match="metric label"):
        manuscript.build(ws, study)


@pytest.mark.parametrize("unit", ["%", "m2", "ms", "files", "s^-1", "MiB/s"])
def test_valid_measurement_units_still_render(workspace_case, unit):
    _, ws, study, source = workspace_case
    manifest = source.model_copy(update={"id": uid("experiment")}, deep=True)
    manifest.metrics[0].unit = unit
    manifest_path = ws.path("metric-unit-test.json")
    write_json(manifest_path, manifest)
    experiments.register_manifest(ws, manifest_path)
    assert experiments.run_experiment(ws, manifest).status == "SUCCEEDED"
    paper, _ = manuscript.build(ws, study)
    assert integrity.check(ws, paper)["passed"]


@pytest.mark.parametrize("description", ["P95 latency", "95th percentile latency", "F1 score", "Top-5 accuracy", "Accuracy (%)", "Percentage of successful recoveries", "Time to first byte"])
def test_valid_numeric_metric_identifiers_and_units_still_render(workspace_case, description):
    _, ws, study, source = workspace_case
    manifest = source.model_copy(update={"id": uid("experiment")}, deep=True)
    manifest.metrics[0].description = description
    manifest_path = ws.path("metric-description-test.json")
    write_json(manifest_path, manifest)
    experiments.register_manifest(ws, manifest_path)
    assert experiments.run_experiment(ws, manifest).status == "SUCCEEDED"
    paper, _ = manuscript.build(ws, study)
    assert integrity.check(ws, paper)["passed"]


def test_missing_evidence_rejects_manuscript(workspace_case):
    _, ws, study, _ = workspace_case
    with pytest.raises(ValueError, match="No successful experimental evidence"):
        manuscript.build(ws, study)
    assert ws.list("paper", Paper) == []
    assert ws.list("claim", Claim) == []


def test_failed_run_and_partial_output_never_become_claims(workspace_case, tmp_path):
    _, ws, study, manifest = workspace_case
    failed = manifest.model_copy(deep=True)
    failed.id = uid("experiment")
    failed.command = ["{python}", "-c", "from pathlib import Path; import sys; p=Path('.paperfactory-results'); p.mkdir(); (p/'inventory.json').write_text('{\"file_count\": 999, \"total_bytes\": 999}'); print('partial output'); sys.exit(7)"]
    path = tmp_path / "failed.json"
    write_json(path, failed)
    experiments.register_manifest(ws, path)
    run = experiments.run_experiment(ws, failed)
    assert run.status == "FAILED" and run.exit_code == 7
    assert (ws.root / "runs" / run.id / "raw" / ".paperfactory-results" / "inventory.json").is_file()
    assert "partial output" in (ws.root / "runs" / run.id / "stdout.log").read_text(encoding="utf-8")
    assert ws.get("run", run.id, ExperimentRun).status == "FAILED"
    with pytest.raises(ValueError, match="successful completed experiment"):
        evidence.claims_for_run(ws, run)
    with pytest.raises(ValueError, match="No successful experimental evidence"):
        manuscript.build(ws, study)


def test_unverified_citation_cannot_enter_manuscript(workspace_case):
    _, ws, study, manifest = workspace_case
    citations = mocked_search(ws, study)
    citation = citations[0]
    citation.verified = False
    ws.save("citation", citation)
    assert experiments.run_experiment(ws, manifest).status == "SUCCEEDED"
    with pytest.raises(ValueError, match="Citation is not verified"):
        manuscript.build(ws, study)


@pytest.mark.parametrize("tamper", ["numeric_prose", "novelty", "conclusion", "duplicate_prose", "missing_limitations", "empty_limitations", "empty_limitations_section", "abstract_claims", "inline_citation"])
def test_semantic_manuscript_tampering_blocks_integrity_and_freeze(built_case, tamper):
    _, ws, _, _, paper, root = built_case

    def change(doc):
        sections = {section["heading"]: section for section in doc["sections"]}
        if tamper == "numeric_prose":
            sections["Discussion"]["blocks"][0]["text"] = "Recovery succeeded in ninety percent of the cases."
        elif tamper == "novelty":
            sections["Introduction"]["blocks"][0]["text"] = "We present the first unprecedented approach to this problem."
        elif tamper == "conclusion":
            sections["Conclusion"]["blocks"][0]["text"] = "These measurements prove that the method is universally effective."
        elif tamper == "duplicate_prose":
            sections["Discussion"]["blocks"][0]["text"] = sections["Introduction"]["blocks"][0]["text"]
        elif tamper == "missing_limitations":
            doc["sections"] = [section for section in doc["sections"] if section["heading"] != "Limitations"]
        elif tamper == "empty_limitations":
            doc["limitations"] = []
        elif tamper == "empty_limitations_section":
            sections["Limitations"]["blocks"] = []
        elif tamper == "abstract_claims":
            sections["Abstract"]["blocks"] = [block for block in sections["Abstract"]["blocks"] if block["kind"] != "claim"]
        elif tamper == "inline_citation":
            sections["Discussion"]["blocks"][0]["text"] = "An unsupported reference [@imaginary] is presented here."

    replace_canonical(ws, paper, root, change)
    if tamper == "empty_limitations_section":
        document = manuscript.Document.model_validate_json((root / "canonical.json").read_text(encoding="utf-8"))
        assert any("limitation" in issue.casefold() for issue in manuscript.validate_document(ws, document))
    report = integrity.check(ws, paper)
    assert not report["passed"]
    assert report["errors"]
    with pytest.raises(ValueError, match="integrity errors"):
        integrity.approve(ws, paper, approved=True, assessment="Reviewed the scientific limitations.")
    assert not (ws.root / "freezes" / paper.id).exists()


@pytest.mark.parametrize("tamper", ["rendered", "table"])
def test_rendered_manuscript_and_table_must_match_canonical_even_with_updated_checksum(built_case, tamper):
    _, ws, _, _, paper, root = built_case
    path = root / "manuscript.md"
    text = path.read_text(encoding="utf-8")
    if tamper == "rendered":
        text += "\nAn unsupported result was inserted after rendering.\n"
    else:
        claim = ws.get("claim", paper.claim_ids[0], Claim)
        old = f"| {claim.id} | {manuscript.escape_md(claim.metric_name)} | {claim.value:.12g} |"
        assert old in text
        text = text.replace(old, f"| {claim.id} | {manuscript.escape_md(claim.metric_name)} | 999 |")
    path.write_text(text, encoding="utf-8")
    paper.manuscript_sha256 = digest_file(path)
    ws.save("paper", paper)
    report = integrity.check(ws, paper)
    assert not report["passed"]
    assert any("differs from canonical" in error for error in report["errors"])


@pytest.mark.parametrize("tamper", ["database_metrics", "raw_artifact", "processed_artifact", "claim", "source_snapshot"])
def test_evidence_tampering_is_detected_by_independent_review(built_case, tamper):
    _, ws, _, run, paper, _ = built_case
    if tamper == "database_metrics":
        run.metrics["file_count"] = 999
        ws.save("run", run)
    elif tamper == "raw_artifact":
        raw = ws.root / "runs" / run.id / "raw" / ".paperfactory-results" / "inventory.json"
        data = json.loads(raw.read_text(encoding="utf-8"))
        data["file_count"] = 999
        write_json(raw, data)
    elif tamper == "processed_artifact":
        write_json(ws.root / "runs" / run.id / "processed.json", {"run_id": run.id, "metrics": {"file_count": 999}})
    elif tamper == "claim":
        claim = ws.get("claim", paper.claim_ids[0], Claim)
        claim.value = 999
        ws.save("claim", claim)
    else:
        path = ws.root / "source" / "notes.md"
        path.chmod(stat.S_IREAD | stat.S_IWRITE)
        path.write_text("Modified snapshot.\n", encoding="utf-8")
    report = integrity.check(ws, paper)
    assert not report["passed"]
    assert report["errors"]


def test_relative_experiment_edits_only_execution_copy(workspace_case, tmp_path):
    source, ws, _, manifest = workspace_case
    original = (source / "notes.md").read_bytes()
    edited = manifest.model_copy(deep=True)
    edited.id = uid("experiment")
    edited.command = ["{python}", "-c", "from pathlib import Path; Path('notes.md').write_text('Experiment-only mutation');\n" + research.INVENTORY_SCRIPT]
    path = tmp_path / "edited.json"
    write_json(path, edited)
    experiments.register_manifest(ws, path)
    run = experiments.run_experiment(ws, edited)
    assert run.status == "SUCCEEDED", run.error
    assert (source / "notes.md").read_bytes() == original
    assert (ws.root / "source" / "notes.md").read_bytes() == original
    assert (ws.root / "runs" / run.id / "work" / "notes.md").read_text() == "Experiment-only mutation"
    project.verify_snapshot(ws)


def test_freeze_requires_explicit_approval(built_case):
    _, ws, _, _, paper, _ = built_case
    with pytest.raises(ValueError, match="Explicit author approval"):
        integrity.approve(ws, paper, approved=False, assessment="Reviewed limitations.")
    assert not (ws.root / "freezes" / paper.id).exists()


def test_freeze_requires_a_recorded_literature_search(built_case):
    _, ws, _, _, paper, _ = built_case
    with pytest.raises(ValueError, match="literature search"):
        integrity.approve(ws, paper, approved=True, assessment="Reviewed limitations.")


@pytest.mark.parametrize("kind", ["missing", "failed"])
def test_missing_or_failed_literature_audit_cannot_satisfy_freeze_gate(built_case, kind):
    _, ws, study, _, paper, _ = built_case
    current = ws.get("study", study.id, Study)
    current.literature_search_ids = ["search-invalid"]
    ws.save("study", current)
    if kind == "failed":
        write_json(ws.root / "literature" / "search-invalid.json", {"id": "search-invalid", "study_id": current.id, "status": "FAILED", "provider": "Crossref", "query": "auditable research"})
    report = integrity.check(ws, paper)
    assert not report["passed"]
    assert any("search" in error.casefold() or "literature" in error.casefold() for error in report["errors"])
    with pytest.raises(ValueError, match="integrity errors"):
        integrity.approve(ws, paper, approved=True, assessment="Reviewed limitations.")
    assert not (ws.root / "freezes" / paper.id).exists()


def test_freeze_requires_scientific_assessment(workspace_case):
    ws, _, paper, _ = freeze_ready(workspace_case)
    with pytest.raises(ValueError, match="assessment"):
        integrity.approve(ws, paper, approved=True, assessment="  ")


def test_freeze_requires_current_complete_author_profile(workspace_case, monkeypatch):
    ws, _, paper, _ = freeze_ready(workspace_case)
    monkeypatch.delenv("PF_AUTHOR_EMAIL")
    with pytest.raises(ValueError, match="author metadata missing"):
        integrity.approve(ws, paper, approved=True, assessment="Reviewed limitations.")
    assert not (ws.root / "freezes" / paper.id).exists()


def test_changed_author_requires_rebuild_before_approval(workspace_case, monkeypatch):
    ws, _, paper, _ = freeze_ready(workspace_case)
    monkeypatch.setenv("PF_AUTHOR_AFFILIATION", "Different University")
    with pytest.raises(ValueError, match="Author profile differs"):
        integrity.approve(ws, paper, approved=True, assessment="Reviewed limitations.")


def test_author_sidecar_must_match_canonical_profile(built_case):
    _, ws, _, _, paper, root = built_case
    author = json.loads((root / "author.json").read_text(encoding="utf-8"))
    author["affiliation"] = "Altered Affiliation"
    write_json(root / "author.json", author)
    report = integrity.check(ws, paper)
    assert not report["passed"]
    assert any("author" in error.casefold() for error in report["errors"])


def test_unrecognized_manuscript_extras_are_not_silently_frozen(built_case):
    _, ws, _, _, paper, root = built_case
    (root / "unreviewed-notes.txt").write_text("Unreviewed private notes.\n", encoding="utf-8")
    report = integrity.check(ws, paper)
    assert not report["passed"]
    assert report["errors"]


def test_recompile_removes_stale_tex_and_pdf_outputs(built_case):
    _, ws, _, _, paper, root = built_case
    (root / "manuscript.tex").write_text("Stale manuscript.\n", encoding="utf-8")
    (root / "manuscript.pdf").write_bytes(b"stale PDF")
    report = manuscript.compile_manuscript(ws, paper)
    assert report["status"] == "COMPILE_READY"
    assert not (root / "manuscript.tex").exists()
    assert not (root / "manuscript.pdf").exists()
    assert report["input_sha256"] == paper.manuscript_sha256
    assert report["document_sha256"] == paper.document_sha256


def test_compiler_failure_preserves_canonical_and_blocks_integrity(built_case, tmp_path):
    _, ws, _, _, paper, root = built_case
    with pytest.raises(ValueError, match="Pandoc export failed"):
        manuscript.compile_manuscript(ws, paper, pandoc=str(tmp_path / "absent-pandoc"))
    assert (root / "canonical.json").is_file() and (root / "manuscript.md").is_file()
    assert json.loads((root / "compile-report.json").read_text(encoding="utf-8"))["status"] == "FAILED"
    report = integrity.check(ws, paper)
    assert not report["passed"]
    assert "Manuscript compiler reported failure" in report["errors"]


def test_unknown_compiler_status_cannot_be_reported_as_integrity_pass(built_case):
    _, ws, _, _, paper, root = built_case
    path = root / "compile-report.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report["status"] = "UNRECOGNIZED"
    write_json(path, report)
    checked = integrity.check(ws, paper)
    assert not checked["passed"]
    assert any("compil" in error.casefold() for error in checked["errors"])


def test_explicit_freeze_is_content_bound_and_prevents_rebuilding(workspace_case):
    ws, study, paper, root = freeze_ready(workspace_case)
    frozen = integrity.approve(ws, paper, approved=True, assessment="Related work and limitations were assessed; descriptive results do not establish novelty.")
    record = ws.get("paper", paper.id, Paper)
    assert record.state is PaperState.AUTHOR_APPROVED
    assert record.approved_by == "Example Researcher"
    assert record.freeze_digest == digest_file(frozen / "approval.json")
    approval = json.loads((frozen / "approval.json").read_text(encoding="utf-8"))
    assert approval["scientific_responsibility_accepted"] is True
    assert approval["files"]["manuscript.md"] == digest_file(root / "manuscript.md")
    assert ws.get("study", study.id, Study).novelty_status == "author_assessed"
    with pytest.raises(ValueError, match="frozen"):
        manuscript.build(ws, study)


@pytest.mark.parametrize("after_commit", [False, True])
def test_freeze_commit_outcome_preserves_or_rolls_back_its_artifacts(workspace_case, fail_transaction, after_commit):
    ws, study, paper, _ = freeze_ready(workspace_case)
    assert integrity.check(ws, paper)["passed"]
    paper = ws.get("paper", paper.id, Paper)
    fail_transaction(ws, "paper", after_commit=after_commit)
    with pytest.raises(OSError, match="failure"):
        integrity.approve(ws, paper, approved=True, assessment="Reviewed related work and limitations.")
    current = ws.get("paper", paper.id, Paper)
    frozen = ws.path(f"freezes/{paper.id}")
    if after_commit:
        assert current.state == PaperState.AUTHOR_APPROVED
        assert frozen.is_dir()
        assert current.freeze_digest == digest_file(frozen / "approval.json")
        assert ws.get("study", study.id, Study).novelty_status == "author_assessed"
        assert integrity.check_frozen(ws, current)["passed"]
    else:
        assert current.state == PaperState.INTEGRITY_CHECKED
        assert current.freeze_digest is None
        assert not frozen.exists()
        integrity.approve(ws, current, approved=True, assessment="Reviewed related work and limitations.")
        assert integrity.check_frozen(ws, ws.get("paper", paper.id, Paper))["passed"]


def test_tampering_with_frozen_snapshot_is_detected(workspace_case):
    ws, _, paper, _ = freeze_ready(workspace_case)
    frozen = integrity.approve(ws, paper, approved=True, assessment="Reviewed related work and limitations.")
    (frozen / "manuscript.md").write_text("A replaced frozen manuscript.\n", encoding="utf-8")
    report = integrity.check(ws, paper)
    assert not report["passed"]
    assert any("froze" in error.casefold() or "freeze" in error.casefold() for error in report["errors"])


def test_freeze_rejects_symlinked_manuscript_extras(workspace_case, tmp_path):
    ws, _, paper, root = freeze_ready(workspace_case)
    external = tmp_path / "outside-private.txt"
    external.write_text("Private data outside the manuscript.\n", encoding="utf-8")
    try:
        (root / "linked-private.txt").symlink_to(external)
    except OSError:
        pytest.skip("OS does not permit symlink creation for this test account")
    with pytest.raises(ValueError, match="symlink|integrity"):
        integrity.approve(ws, paper, approved=True, assessment="Reviewed related work and limitations.")
    assert not (ws.root / "freezes" / paper.id / "linked-private.txt").exists()


def test_manuscript_discloses_recorded_ai_usage(workspace_case):
    _, ws, study, manifest = workspace_case
    ws.save("provenance", Provenance(role="language editing", tool="Example AI Editor", model="Example Model", inputs=[study.id], outputs=["edited prose"], ai=True))
    assert experiments.run_experiment(ws, manifest).status == "SUCCEEDED"
    _, root = manuscript.build(ws, study)
    text = (root / "manuscript.md").read_text(encoding="utf-8")
    assert "Example AI Editor" in text and "Example Model" in text
    assert "language editing" in text
    assert "no language model was used by this workflow" not in text


def test_ai_usage_added_after_drafting_requires_disclosure_rebuild(built_case):
    _, ws, study, _, paper, _ = built_case
    ws.save("provenance", Provenance(role="language editing", tool="Late AI Editor", model="Example Model", inputs=[study.id], outputs=["edited prose"], ai=True))
    report = integrity.check(ws, paper)
    assert not report["passed"]
    assert any("AI-use provenance changed" in error for error in report["errors"])


def test_unrelated_ai_activity_does_not_invalidate_a_draft(built_case):
    _, ws, _, _, paper, _ = built_case
    ws.save("provenance", Provenance(role="venue discovery", tool="AI", inputs=["another-study"], outputs=["other-venue"], ai=True))
    assert integrity.check(ws, paper)["passed"]


def test_author_can_render_edits_and_rebuild_without_losing_prose(built_case):
    _, ws, study, _, paper, root = built_case
    document = manuscript.Document.model_validate_json((root / "canonical.json").read_text(encoding="utf-8"))
    introduction = next(section for section in document.sections if section.heading == "Introduction")
    introduction.blocks = [manuscript.prose("The research asset collection supports transparent examination of the available software and data.")]
    document.title = "Author-revised descriptive study"
    write_json(root / "canonical.json", document)
    assert not integrity.check(ws, paper)["passed"]
    revised, _ = manuscript.refresh(ws, paper)
    assert integrity.check(ws, revised)["passed"]
    rebuilt, _ = manuscript.build(ws, study)
    text = (root / "manuscript.md").read_text(encoding="utf-8")
    assert introduction.blocks[0].text in text
    assert rebuilt.title == document.title
    assert integrity.check(ws, rebuilt)["passed"]


def test_quantitative_lint_allows_identifiers_questions_and_units(workspace_case):
    _, ws, study, manifest = workspace_case
    study.title = "Research assets collected in 2025"
    study.research_question = "How do Python 3 assets differ from Python 2 assets, and could a first baseline outperform an alternative?"
    ws.save("study", study)
    manifest.metrics[0].unit = "m2"
    manifest.metrics[0].description = "Inventory for Python 3 assets"
    ws.save("manifest", manifest)
    assert experiments.run_experiment(ws, manifest).status == "SUCCEEDED"
    paper, _ = manuscript.build(ws, study)
    assert integrity.check(ws, paper)["passed"]


@pytest.mark.parametrize("location", ["Method", "Experimental Setup", "title", "limitations"])
def test_unsupported_quantitative_results_cannot_hide_in_other_sections(built_case, location):
    _, ws, _, _, paper, root = built_case
    doc = manuscript.Document.model_validate_json((root / "canonical.json").read_bytes())
    unsupported = "Recovery succeeded in ninety percent of cases."
    if location == "title":
        doc.title = unsupported
    elif location == "limitations":
        doc.limitations = [unsupported]
    else:
        next(section for section in doc.sections if section.heading == location).blocks.append(manuscript.prose(unsupported))
    write_json(root / "canonical.json", doc)
    before = (root / "manuscript.md").read_bytes()
    with pytest.raises(ValueError, match="Unsupported quantitative prose"):
        manuscript.refresh(ws, paper)
    assert (root / "manuscript.md").read_bytes() == before


def test_frozen_science_is_independent_of_live_records(workspace_case):
    ws, study, paper, root = freeze_ready(workspace_case)
    integrity.approve(ws, paper, approved=True, assessment="Reviewed metadata, operational evidence and limitations.")
    ws.save("provenance", Provenance(role="new study assistance", tool="Later AI", inputs=[study.id], outputs=["new draft"], ai=True))
    study.citation_ids = []
    study.literature_search_ids = ["later-failed-search"]
    ws.save("study", study)
    run = ws.get("run", ws.get("claim", paper.claim_ids[0], Claim).run_id, ExperimentRun)
    run.metrics["file_count"] = 999
    ws.save("run", run)
    (root / "manuscript.md").write_text("Working files changed after the scientific freeze.", encoding="utf-8")
    report = integrity.check(ws, paper)
    assert report["passed"], report["errors"]
    snapshot = integrity.frozen_workspace(ws, paper)
    assert snapshot.get("study", study.id, Study).citation_ids
    assert snapshot.get("run", run.id, ExperimentRun).metrics["file_count"] != 999
    with pytest.raises(ValueError, match="read-only"):
        snapshot.save("run", run)
    with pytest.raises(ValueError, match="frozen"):
        manuscript.refresh(ws, paper)
    with pytest.raises(ValueError, match="frozen"):
        manuscript.compile_manuscript(ws, paper)


def test_freeze_copy_failure_leaves_no_partial_snapshot_and_can_retry(workspace_case, monkeypatch):
    ws, _, paper, _ = freeze_ready(workspace_case)
    copy = integrity.shutil.copyfile

    def fail_raw_copy(source, target, *args, **kwargs):
        if "/raw/" in str(source).replace("\\", "/"):
            raise OSError("Injected copying failure")
        return copy(source, target, *args, **kwargs)

    monkeypatch.setattr(integrity.shutil, "copyfile", fail_raw_copy)
    with pytest.raises(OSError, match="Injected"):
        integrity.approve(ws, paper, approved=True, assessment="Reviewed metadata, operational evidence and limitations.")
    assert not (ws.root / "freezes" / paper.id).exists()
    assert not list((ws.root / "freezes").iterdir())
    assert ws.get("paper", paper.id, Paper).state is PaperState.INTEGRITY_CHECKED
    monkeypatch.setattr(integrity.shutil, "copyfile", copy)
    integrity.approve(ws, paper, approved=True, assessment="Reviewed metadata, operational evidence and limitations.")
    assert integrity.check_frozen(ws, paper)["passed"]


def test_freeze_revalidates_evidence_copied_after_review(workspace_case, monkeypatch):
    ws, _, paper, _ = freeze_ready(workspace_case)
    copy = integrity.shutil.copyfile

    def corrupt_copied_output(source, target, *args, **kwargs):
        result = copy(source, target, *args, **kwargs)
        if "/raw/" in str(source).replace("\\", "/"):
            Path(target).write_text('{"file_count": 999, "total_bytes": 999}', encoding="utf-8")
        return result

    from pathlib import Path
    monkeypatch.setattr(integrity.shutil, "copyfile", corrupt_copied_output)
    with pytest.raises(ValueError, match="changed during copying"):
        integrity.approve(ws, paper, approved=True, assessment="Reviewed metadata, operational evidence and limitations.")
    assert not list((ws.root / "freezes").iterdir())
    assert ws.get("paper", paper.id, Paper).state is PaperState.INTEGRITY_CHECKED


def test_frozen_claims_reject_semantically_corrupt_snapshot_even_with_rebound_hashes(workspace_case):
    ws, _, paper, _ = freeze_ready(workspace_case)
    frozen = integrity.approve(ws, paper, approved=True, assessment="Reviewed metadata, operational evidence and limitations.")
    records_path = frozen / "records.json"
    records = json.loads(records_path.read_text(encoding="utf-8"))
    records["claim"][paper.claim_ids[0]]["value"] = 999
    write_json(records_path, records)
    approval_path = frozen / "approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["files"]["records.json"] = digest_file(records_path)
    write_json(approval_path, approval)
    paper.freeze_digest = digest_file(approval_path)
    ws.save("paper", paper)
    report = integrity.check_frozen(ws, paper)
    assert not report["passed"]
    assert any("evidence" in issue.casefold() for issue in report["errors"])

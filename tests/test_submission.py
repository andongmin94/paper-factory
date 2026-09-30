import json
from pathlib import Path
import re
import shutil
import sys
from types import SimpleNamespace
import zipfile
from xml.sax.saxutils import escape

import httpx
import pytest

from paper_factory import experiments, integrity, manuscript, project, research, submission_package, venue_compiler
from paper_factory.models import Paper, Project, Submission, SubmissionState
from paper_factory.venue_compiler import Compilation, CompilerSettings
from paper_factory.venue_policy import verify_policy
from paper_factory.workspace import digest_file, write_json
from test_manuscript import mocked_search
from test_venue_policy import setup_policy


@pytest.fixture
def prepared(setup_policy, tmp_path, monkeypatch, request):
    ws, venue, spec_path, spec, handler = setup_policy
    for field in manuscript.AuthorProfile.model_fields:
        monkeypatch.delenv(f"PF_AUTHOR_{field.upper()}", raising=False)
    monkeypatch.delenv("PF_AUTHOR_PROFILE_JSON", raising=False)
    monkeypatch.setenv("PF_AUTHOR_DISPLAY_NAME", "Example Scholar" if getattr(request, "param", None) == "self-citation" else "Fixture [Author]")
    monkeypatch.setenv("PF_AUTHOR_EMAIL", "author@example.org")
    monkeypatch.setenv("PF_AUTHOR_AFFILIATION", "Fixture *University*")
    monkeypatch.setenv("PF_HOME", str(tmp_path / "home"))
    actual_which = manuscript.shutil.which
    monkeypatch.setattr(manuscript.shutil, "which", lambda command, *args, **kwargs: None if command == "pandoc" else actual_which(command, *args, **kwargs))
    source = tmp_path / "assets"
    source.mkdir()
    (source / "analysis.py").write_text("print('fixture')\n", encoding="utf-8")
    imported = project.ingest(str(source), tmp_path / "imported")
    shutil.copytree(imported.root / "source", ws.root / "source", dirs_exist_ok=True)
    ws.save("project", imported.latest("project", Project))
    research.discover(ws)
    study = research.create_study(ws, domain="software_engineering")
    mocked_search(ws, study)
    manifest = research.plan(ws, study)
    manifest.metrics[0].description = "Files at Fixture *University*"
    ws.save("manifest", manifest)
    assert experiments.run_experiment(ws, manifest).status == "SUCCEEDED"
    paper, _ = manuscript.build(ws, study)
    integrity.approve(ws, paper, approved=True, assessment="The related metadata, evidence and limitations were reviewed.")
    spec["values"]["required_sections"] = ["Abstract", "Introduction", "Method", "Results", "Discussion"]
    excerpt = "required_sections: " + json.dumps(spec["values"]["required_sections"])
    spec["evidence"]["required_sections"]["excerpt"] = excerpt
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    def policies(request):
        return httpx.Response(200, text=handler(request).text + f"<p>{excerpt}</p>", headers={"content-type": "text/html"})

    def policy_for(blind=False, changes=None):
        spec["values"]["anonymization_required"] = blind
        spec["values"].update(changes or {})
        extra = []
        for name in {"anonymization_required", *(changes or {})}:
            text = f"{name}: {json.dumps(spec['values'][name])}"
            spec["evidence"][name]["excerpt"] = text
            extra.append(text)
        spec_path.write_text(json.dumps(spec), encoding="utf-8")

        def active(request):
            return httpx.Response(200, text=policies(request).text + "".join(f"<p>{text}</p>" for text in extra), headers={"content-type": "text/html"})

        with httpx.Client(transport=httpx.MockTransport(active)) as client:
            policy = verify_policy(ws, venue, spec_path, client=client)
        return policy, active

    settings = CompilerSettings(article_type="Research Article", keywords=["reproducibility", "software"], declarations={"funding": "No external funding was received.", "conflict_of_interest": "The author declares no competing interests.", "data_availability": "The supplied assets are available under their original permissions.", "ai_disclosure": "No AI assistance was recorded for this study."}, scope_fit="The manuscript describes reproducible inspection of software research assets.", cover_letter="Please consider this descriptive manuscript and its stated limitations.")
    settings_path = tmp_path / "compiler.json"
    write_json(settings_path, settings)
    return ws, venue, paper, settings_path, policy_for


@pytest.fixture
def mock_conversion(monkeypatch):
    calls = []

    def convert(markdown, output, **kwargs):
        calls.append((output.suffix, kwargs))
        text = markdown.read_text(encoding="utf-8")
        if output.suffix == ".docx":
            with zipfile.ZipFile(output, "w") as archive:
                archive.writestr("word/document.xml", "<document><p>" + escape(text) + "</p></document>")
                archive.writestr("docProps/core.xml", "<core/>")
        else:
            output.write_text(text, encoding="utf-8")
        return {"engine": "test converter", "input_sha256": digest_file(markdown), "output_sha256": digest_file(output)}

    class Reader:
        def __init__(self, path):
            self.pages = [SimpleNamespace(extract_text=lambda: Path(path).read_text(encoding="utf-8"))]
            self.metadata = {}

    monkeypatch.setattr(venue_compiler, "convert", convert)
    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=Reader))
    return calls


def compile_case(prepared, blind=False, changes=None, settings_change=None):
    ws, venue, paper, settings_path, policy_for = prepared
    if settings_change:
        settings = json.loads(settings_path.read_bytes())
        settings_change(settings)
        write_json(settings_path, settings)
    policy, handler = policy_for(blind, changes)
    candidate = venue_compiler.select(ws, paper, venue, policy)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        submission, root = venue_compiler.compile_submission(ws, candidate, settings_path, client=client)
    return ws, paper, submission, root, handler


def test_compile_and_package_are_bound_to_frozen_science(prepared, mock_conversion):
    ws, paper, submission, compiled, handler = compile_case(prepared)
    frozen_hash = digest_file(ws.path(f"freezes/{paper.id}/canonical.json"))
    assert submission.state is SubmissionState.VENUE_COMPILED
    assert not venue_compiler.verify_compilation(ws, submission)
    assert all(kwargs["line_numbers"] for _, kwargs in mock_conversion)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        package, root = submission_package.build(ws, submission, client=client)
    assert package.ready and submission_package.verify(ws, submission)["ready"]
    assert ws.get("submission", submission.id, Submission).state is SubmissionState.SUBMISSION_READY
    assert digest_file(ws.path(f"freezes/{paper.id}/canonical.json")) == frozen_hash
    with zipfile.ZipFile(root / "submission.zip") as archive:
        assert "manifest.json" in archive.namelist()
    assert json.loads((root / "compliance.json").read_bytes())["external_submission_performed"] is False
    with pytest.raises(ValueError, match="immutable"):
        submission_package.build(ws, submission)
    with pytest.raises(ValueError, match="immutable"):
        venue_compiler.compile_submission(ws, submission, prepared[3])


def test_blind_review_redacts_escaped_names_and_measurement_labels(prepared, mock_conversion):
    ws, _, submission, root, handler = compile_case(prepared, blind=True)
    assert not venue_compiler.verify_compilation(ws, submission)
    for name in ("manuscript.md", "manuscript.pdf", "manuscript.tex", "tables/results.csv"):
        text = (root / name).read_text(encoding="utf-8")
        assert "Fixture" not in text and "University" not in text and "Author" not in text
    assert "Fixture [Author]" in (root / "author.json").read_text(encoding="utf-8")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        package, root = submission_package.build(ws, submission, client=client)
    assert package.ready
    guide = json.loads((root / "package-readme.json").read_bytes())
    assert "author.json" in guide["administrative_files"]
    assert "author.json" not in guide["reviewer_files"]


@pytest.mark.parametrize("change,expected", [
    ({"abstract_word_limit": 1}, "Abstract word limit"),
    ({"keyword_limit": 1}, "Keyword limit"),
    ({"free_initial_submission": False, "template_requirements": ["Publisher standard research template"]}, "exact publisher layout"),
    ({"accepted_formats": ["rtf"]}, "No supported manuscript format"),
])
def test_noncompliant_candidates_never_become_ready(prepared, mock_conversion, change, expected):
    ws, _, submission, root, handler = compile_case(prepared, changes=change)
    assert any(expected in error for error in venue_compiler.verify_compilation(ws, submission))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        package, _ = submission_package.build(ws, submission, client=client)
    assert not package.ready
    assert ws.get("submission", submission.id, Submission).state is SubmissionState.VENUE_COMPILED
    assert not submission_package.verify(ws, submission)["ready"]


def test_missing_author_declaration_blocks_readiness(prepared, mock_conversion):
    ws, _, submission, _, handler = compile_case(prepared, settings_change=lambda settings: settings["declarations"].pop("funding"))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        package, _ = submission_package.build(ws, submission, client=client)
    assert not package.ready and any("funding" in error for error in package.errors)


def test_final_cited_pdf_can_exceed_word_limit_even_when_source_fits(prepared, mock_conversion, monkeypatch):
    convert = venue_compiler.convert

    def expanded_citations(markdown, output, **kwargs):
        result = convert(markdown, output, **kwargs)
        if output.suffix == ".pdf":
            with output.open("a", encoding="utf-8") as stream:
                stream.write("\n" + " cited " * 3000)
            result["output_sha256"] = digest_file(output)
        return result

    monkeypatch.setattr(venue_compiler, "convert", expanded_citations)
    ws, _, submission, root, handler = compile_case(prepared, changes={"manuscript_word_limit": 1000})
    record = ws.get("compilation", submission.id, Compilation)
    assert record.word_counts["manuscript"] < 1000 < record.word_counts["rendered_manuscript"]
    assert any("final cited PDF" in issue for issue in venue_compiler.verify_compilation(ws, submission))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        package, _ = submission_package.build(ws, submission, client=client)
    assert not package.ready


def test_changed_live_policy_after_compilation_blocks_readiness(prepared, mock_conversion):
    ws, _, submission, _, _ = compile_case(prepared)
    changed = lambda _: httpx.Response(200, text="<p>The publisher changed its policy.</p>", headers={"content-type": "text/html"})
    with httpx.Client(transport=httpx.MockTransport(changed)) as client:
        package, _ = submission_package.build(ws, submission, client=client)
    assert not package.ready and any("changed after compilation" in error for error in package.errors)


def test_incomplete_policy_produces_a_blocked_inspectable_package(prepared, mock_conversion):
    ws, _, submission, _, handler = compile_case(prepared, changes={"ai_use_allowed": None})
    assert not venue_compiler.verify_compilation(ws, submission, check_compliance=False)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        package, root = submission_package.build(ws, submission, client=client)
    assert not package.ready and (root / "submission.zip").is_file()
    assert package.errors


@pytest.mark.parametrize("prepared", ["self-citation"], indirect=True)
def test_blinded_self_citations_require_author_review_without_corrupting_bibliography(prepared, mock_conversion):
    ws, _, submission, root, handler = compile_case(prepared, blind=True)
    assert "Example Scholar" in (root / "references.json").read_text(encoding="utf-8")
    assert any("Self-identifying bibliography" in error for error in venue_compiler.verify_compilation(ws, submission))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        package, _ = submission_package.build(ws, submission, client=client)
    assert not package.ready


@pytest.mark.parametrize("target", ["manuscript.md", "tables/results.csv", "author.json"])
def test_compilation_tampering_is_detected(prepared, mock_conversion, target):
    ws, _, submission, root, _ = compile_case(prepared)
    (root / target).write_text("tampered", encoding="utf-8")
    assert venue_compiler.verify_compilation(ws, submission)
    with pytest.raises(ValueError, match="corrupted compilation"):
        submission_package.build(ws, submission)


def test_rebound_hashes_cannot_hide_changed_quantitative_results(prepared, mock_conversion):
    ws, _, submission, root, _ = compile_case(prepared)
    path = root / "tables" / "results.csv"
    path.write_text("measurement,value,unit\nFabricated result,999,files\n", encoding="utf-8")
    compilation = ws.get("compilation", submission.id, Compilation)
    compilation.files["tables/results.csv"] = digest_file(path)
    write_json(root / "compliance.json", compilation)
    submission.compilation_digest = digest_file(root / "compliance.json")
    ws.save("submission", submission)
    ws.save("compilation", compilation)
    assert any("approved evidence" in issue for issue in venue_compiler.verify_compilation(ws, submission))


@pytest.mark.parametrize("format", ["pdf", "tex", "docx"])
def test_rebound_native_export_must_match_its_conversion_receipt(prepared, mock_conversion, format):
    ws, _, submission, root, _ = compile_case(prepared)
    path = root / f"manuscript.{format}"
    if format == "docx":
        with zipfile.ZipFile(path) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        files["word/document.xml"], count = re.subn(rb"\b1\b", b"999", files["word/document.xml"], count=1)
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in files.items():
                archive.writestr(name, content)
    else:
        changed, count = re.subn(r"\b1\b", "999", path.read_text(encoding="utf-8"), count=1)
        path.write_text(changed, encoding="utf-8")
    assert count == 1  # Same word count, different measured result.
    compilation = ws.get("compilation", submission.id, Compilation)
    compilation.files[path.name] = digest_file(path)
    write_json(root / "compliance.json", compilation)
    submission.compilation_digest = digest_file(root / "compliance.json")
    ws.save("submission", submission)
    ws.save("compilation", compilation)
    assert any("Conversion receipt" in issue for issue in venue_compiler.verify_compilation(ws, submission))


@pytest.mark.parametrize("mutation", ["input", "formats"])
def test_rebound_conversion_receipt_must_retain_the_actual_source_and_formats(prepared, mock_conversion, mutation):
    ws, _, submission, root, _ = compile_case(prepared)
    path = root / "conversion.json"
    reports = json.loads(path.read_bytes())
    if mutation == "input":
        reports["pdf"]["input_sha256"] = "0" * 64
    else:
        reports.pop("docx")
    write_json(path, reports)
    compilation = ws.get("compilation", submission.id, Compilation)
    compilation.files[path.name] = digest_file(path)
    write_json(root / "compliance.json", compilation)
    submission.compilation_digest = digest_file(root / "compliance.json")
    ws.save("submission", submission)
    ws.save("compilation", compilation)
    assert any("Conversion receipt" in issue for issue in venue_compiler.verify_compilation(ws, submission))


def test_rebound_hashes_cannot_remove_required_compliance_blockers(prepared, mock_conversion):
    ws, _, submission, root, _ = compile_case(prepared, settings_change=lambda settings: settings["declarations"].pop("funding"))
    compilation = ws.get("compilation", submission.id, Compilation)
    compilation.errors = []
    write_json(root / "compliance.json", compilation)
    submission.compilation_digest = digest_file(root / "compliance.json")
    ws.save("submission", submission)
    ws.save("compilation", compilation)
    assert any("omitted required compliance" in issue for issue in venue_compiler.verify_compilation(ws, submission, check_compliance=False))


@pytest.mark.parametrize("target", ["submission.zip", "manuscript.pdf", "manifest.json"])
def test_package_tampering_is_detected(prepared, mock_conversion, target):
    ws, _, submission, _, handler = compile_case(prepared)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        _, root = submission_package.build(ws, submission, client=client)
    (root / target).write_bytes(b"tampered")
    assert not submission_package.verify(ws, submission)["ready"]


def test_package_copy_race_is_detected_and_retryable(prepared, mock_conversion, monkeypatch):
    ws, _, submission, _, handler = compile_case(prepared)
    copy = submission_package.shutil.copyfile

    def corrupt(source, target, *args, **kwargs):
        result = copy(source, target, *args, **kwargs)
        if str(target).endswith("manuscript.md"):
            Path(target).write_text("changed during copy", encoding="utf-8")
        return result

    monkeypatch.setattr(submission_package.shutil, "copyfile", corrupt)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="changed during packaging"):
            submission_package.build(ws, submission, client=client)
    assert not ws.path(f"submissions/{submission.id}/package").exists()
    assert list(ws.path(f"submissions/{submission.id}").glob("failed-package-*/failure.json"))
    monkeypatch.setattr(submission_package.shutil, "copyfile", copy)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        package, _ = submission_package.build(ws, submission, client=client)
    assert package.ready


def test_failed_conversion_is_preserved_and_can_be_retried(prepared, mock_conversion, monkeypatch):
    ws, venue, paper, settings_path, policy_for = prepared
    policy, handler = policy_for()
    submission = venue_compiler.select(ws, paper, venue, policy)
    convert = venue_compiler.convert
    monkeypatch.setattr(venue_compiler, "convert", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("Injected conversion failure")))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="Injected conversion failure"):
            venue_compiler.compile_submission(ws, submission, settings_path, client=client)
    assert ws.get("submission", submission.id, Submission).state is SubmissionState.VENUE_SELECTED
    assert list(ws.path(f"submissions/{submission.id}").glob("failed-compilation-*/failure.json"))
    monkeypatch.setattr(venue_compiler, "convert", convert)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        compiled, _ = venue_compiler.compile_submission(ws, submission, settings_path, client=client)
    assert not venue_compiler.verify_compilation(ws, compiled)


@pytest.mark.parametrize("after_commit", [False, True])
def test_compilation_commit_outcome_preserves_or_rolls_back_its_artifacts(prepared, mock_conversion, fail_transaction, after_commit):
    ws, venue, paper, settings, policy_for = prepared
    policy, handler = policy_for()
    candidate = venue_compiler.select(ws, paper, venue, policy)
    fail_transaction(ws, "compilation", after_commit=after_commit)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OSError, match="failure"):
            venue_compiler.compile_submission(ws, candidate, settings, client=client)
        current = ws.get("submission", candidate.id, Submission)
        if after_commit:
            assert current.state == SubmissionState.VENUE_COMPILED
            assert not venue_compiler.verify_compilation(ws, current)
        else:
            assert current.state == SubmissionState.VENUE_SELECTED
            assert not ws.path(f"submissions/{candidate.id}/compiled").exists()
            current, _ = venue_compiler.compile_submission(ws, current, settings, client=client)
            assert not venue_compiler.verify_compilation(ws, current)


@pytest.mark.parametrize("after_commit", [False, True])
def test_package_commit_outcome_preserves_or_rolls_back_its_artifacts(prepared, mock_conversion, fail_transaction, after_commit):
    ws, _, candidate, _, handler = compile_case(prepared)
    fail_transaction(ws, "package", after_commit=after_commit)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OSError, match="failure"):
            submission_package.build(ws, candidate, client=client)
        current = ws.get("submission", candidate.id, Submission)
        if after_commit:
            assert current.state == SubmissionState.SUBMISSION_READY
            assert submission_package.verify(ws, current)["ready"]
        else:
            assert current.state == SubmissionState.VENUE_COMPILED
            assert not ws.path(f"submissions/{candidate.id}/package").exists()
            package, _ = submission_package.build(ws, current, client=client)
            assert package.ready


def test_package_readiness_cannot_diverge_from_candidate_state(prepared, mock_conversion):
    ws, _, submission, _, handler = compile_case(prepared)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        submission_package.build(ws, submission, client=client)
    current = ws.get("submission", submission.id, Submission)
    current.state = SubmissionState.VENUE_COMPILED
    ws.save("submission", current)
    report = submission_package.verify(ws, current)
    assert not report["ready"] and "Package readiness differs from submission state" in report["errors"]


def test_rebound_package_hashes_cannot_hide_scientific_drift(prepared, mock_conversion):
    ws, _, submission, _, handler = compile_case(prepared)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        package, root = submission_package.build(ws, submission, client=client)
    (root / "tables/results.csv").write_text("measurement,value,unit\nFabrication,999,files\n", encoding="utf-8")
    package.files["tables/results.csv"] = digest_file(root / "tables/results.csv")
    manifest = json.loads((root / "manifest.json").read_bytes())
    manifest["files"] = package.files
    write_json(root / "manifest.json", manifest)
    package.manifest_sha256 = digest_file(root / "manifest.json")
    with zipfile.ZipFile(root / "submission.zip", "w") as archive:
        for name in [*package.files, "manifest.json"]:
            archive.write(root / name, name)
    package.archive_sha256 = digest_file(root / "submission.zip")
    current = ws.get("submission", submission.id, Submission)
    current.package_digest = package.manifest_sha256
    ws.save("submission", current)
    ws.save("package", package)
    report = submission_package.verify(ws, current)
    assert not report["ready"]
    assert any("verified compilation" in error for error in report["errors"])


@pytest.mark.parametrize("suffix", [".pdf", ".docx"])
def test_exported_identity_metadata_blocks_blind_readiness(prepared, mock_conversion, monkeypatch, suffix):
    convert = venue_compiler.convert

    def identifying(markdown, output, **kwargs):
        result = convert(markdown, output, **kwargs)
        if output.suffix == suffix:
            if suffix == ".pdf":
                with output.open("a", encoding="utf-8") as stream:
                    stream.write("Fixture [Author]")
            else:
                with zipfile.ZipFile(output, "a") as archive:
                    archive.writestr("docProps/custom.xml", "<creator>Fixture [Author]</creator>")
            result["output_sha256"] = digest_file(output)
        return result

    monkeypatch.setattr(venue_compiler, "convert", identifying)
    ws, _, submission, _, handler = compile_case(prepared, blind=True)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        package, _ = submission_package.build(ws, submission, client=client)
    assert not package.ready
    assert any("Author-identifying content remains" in error for error in package.errors)


@pytest.mark.parametrize("blind", [False, True])
def test_real_pandoc_typst_compile_creates_readable_pdf(prepared, blind, pandoc):
    pytest.importorskip("typst")
    from pypdf import PdfReader
    ws, venue, paper, settings_path, policy_for = prepared
    policy, handler = policy_for(blind)
    candidate = venue_compiler.select(ws, paper, venue, policy)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        submission, root = venue_compiler.compile_submission(ws, candidate, settings_path, pandoc=str(pandoc), client=client)
    reader = PdfReader(root / "manuscript.pdf")
    text = " ".join(page.extract_text() or "" for page in reader.pages)
    assert "Results" in text and "Auditable Research Practices" in text
    if blind:
        assert "Fixture" not in text and "University" not in text
    assert not venue_compiler.verify_compilation(ws, submission)

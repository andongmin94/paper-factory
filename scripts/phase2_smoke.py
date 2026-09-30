"""Real execution/PDF/package smoke with clearly identified synthetic reviewers.

The default run is offline: scholarly services and journal policy are synthetic
HTTP fixtures, while corpus execution, evidence checks, conversion, PDF parsing,
scientific freezing and archive verification use the real application modules.
--live additionally retrieves a real PLOS candidate and official policy pages.
Neither path logs into a journal, uploads a manuscript, or submits anything.
"""

import argparse
import json
import os
from pathlib import Path
import socket
import tempfile
from unittest.mock import patch

import httpx

from paper_factory import evidence, experiments, integrity, literature, manuscript, project, research
from paper_factory.models import Paper, Project, Submission
from paper_factory.submission_package import build as build_package, verify as verify_package
from paper_factory.venue_compiler import compile_submission, select
from paper_factory.venue_policy import verify_policy
from paper_factory.venues import discover
from paper_factory.workspace import write_json

SYNTHETIC_AUTHOR = {
    "display_name": "Synthetic Smoke Reviewer",
    "email": "synthetic-smoke@example.org",
    "affiliation": "Synthetic Smoke Test Institution",
}


def synthetic_policy(venue_id: str) -> tuple[dict, str]:
    """A deliberately synthetic complete policy, never a real venue assertion."""
    values = dict(
        scope="Synthetic software and empirical workflow smoke research",
        article_types=["Research Article"], indexing="SCIE", publisher="Synthetic Test Publisher",
        oa_model="open", apc={"status": "none"}, preprint_policy="Synthetic policy permits preprints",
        ai_policy="Synthetic policy permits disclosed AI assistance", ai_use_allowed=True,
        ai_disclosure_required=True, data_code_policy="Synthetic policy requires reproducible data and code",
        manuscript_word_limit=None, abstract_word_limit=1000, abstract_character_limit=None,
        title_character_limit=250, keyword_limit=6, review_model="Single anonymous",
        anonymization_required=False,
        required_declarations=["funding", "conflict_of_interest", "data_availability", "code_availability", "ai_disclosure"],
        submission_url="https://submission.synthetic.example.org/",
        submission_system="Synthetic Test System", free_initial_submission=True,
        template_requirements=[], accepted_formats=["pdf", "docx", "tex"], citation_style=None,
        figure_formats=["png", "tiff"], line_numbers_required=True, page_numbers_required=True,
        required_sections=["Abstract", "Introduction", "Related Work", "Method", "Results", "Discussion", "Limitations", "Conclusion"],
        required_supplements=[],
    )
    excerpts = {field: f"Synthetic reviewed {field}: {json.dumps(value)}" for field, value in values.items()}
    excerpts["indexing"] = "Synthetic Test Journal ISSN 1234-5678 Science Citation Index Expanded SCIE"
    spec = {
        "venue_id": venue_id,
        "sources": ["https://synthetic.example.org/guidelines", "https://mjl.clarivate.com/synthetic-smoke-fixture"],
        "values": values,
        "reviewed_by": SYNTHETIC_AUTHOR["display_name"],
        "evidence": {field: {
            "source_url": "https://mjl.clarivate.com/synthetic-smoke-fixture" if field == "indexing" else "https://synthetic.example.org/guidelines",
            "excerpt": text, "interpretation": f"Synthetic test reviewer interpretation of {field}; this is fixture data.",
        } for field, text in excerpts.items()},
    }
    body = "<html><h1>SYNTHETIC TEST FIXTURE; NOT A REAL JOURNAL POLICY</h1>" + "".join(f"<p>{text}</p>" for text in excerpts.values()) + "</html>"
    return spec, body


def mock_directory(request: httpx.Request) -> httpx.Response:
    if request.url.host != "api.openalex.org" or request.url.path != "/sources":
        raise AssertionError("Unexpected synthetic directory request")
    return httpx.Response(200, json={"results": [{
        "id": "https://openalex.org/S123", "type": "journal", "display_name": "Synthetic Test Journal",
        "issn": ["1234-5678"], "host_organization_name": "Synthetic Test Publisher",
        "homepage_url": "https://synthetic.example.org/journal", "relevance_score": 1.0,
    }]})


def public_fixture_dns(host, port, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


def prepare_scientific_fixture(root: Path, pandoc: str | None):
    source = Path(__file__).resolve().parents[1] / "examples" / "text-study"
    ws = project.ingest(str(source), root / "workspace")
    imported = ws.latest("project", Project)
    study = research.create_study(ws,
        question="How does lossless compression change the byte length of the supplied text corpus?",
        title="Synthetic workflow validation using measured corpus compression")
    # No fake citation or novelty conclusion: only a labelled empty search fixture.
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "ok", "message": {"items": []}}))) as client:
        literature.search(ws, "synthetic smoke test empty literature fixture", study, client=client)
    manifest_path = root / "compression-manifest.json"
    write_json(manifest_path, {
        "id": "smoke-corpus-compression", "study_id": study.id,
        "source_commit": imported.source_commit, "source_digest": imported.snapshot_digest,
        "command": ["{python}", "analyze.py"], "inputs": ["analyze.py", "corpus.txt"],
        "expected_outputs": ["results.json"], "metrics": [
            {"name": "original_bytes", "output": "results.json", "pointer": "/observations/original_bytes", "unit": "bytes", "description": "Measured corpus byte length"},
            {"name": "compressed_bytes", "output": "results.json", "pointer": "/observations/compressed_bytes", "unit": "bytes", "description": "Measured compressed corpus byte length"},
            {"name": "compression_ratio", "output": "results.json", "pointer": "/metrics/compression_ratio", "unit": "ratio", "description": "Ratio of compressed length to corpus length"},
        ],
    })
    run = experiments.run_experiment(ws, experiments.register_manifest(ws, manifest_path))
    if run.status != "SUCCEEDED":
        raise RuntimeError(f"Real compression experiment failed: {run.error}")
    claims = evidence.claims_for_run(ws, run)
    paper, _ = manuscript.build(ws, study, pandoc=pandoc, author_values=SYNTHETIC_AUTHOR)
    report = integrity.check(ws, paper)
    if not report["passed"]:
        raise RuntimeError(f"Fixture scientific integrity failed: {report['errors']}")
    integrity.approve(ws, paper, approved=True,
        assessment="Synthetic integration-test reviewer only. The actual compression observations are limited to the included corpus; the mocked empty literature search establishes no novelty. This test approval authorizes local pipeline verification, never real journal submission or publication.",
        author_values=SYNTHETIC_AUTHOR)
    paper = ws.get("paper", paper.id, Paper)
    return ws, paper, run, claims


def settings(root: Path) -> Path:
    path = root / "compiler-settings.json"
    write_json(path, {
        "article_type": "Research Article", "keywords": ["reproducibility", "compression"],
        "scope_fit": "Synthetic reviewer: this fixture exercises an empirical measurement workflow; it makes no claim of publishable merit.",
        "cover_letter": "SYNTHETIC INTEGRATION TEST ONLY. This package demonstrates the Paper Factory workflow using actual local compression measurements. It is not a request for journal review and must not be submitted externally.",
        "declarations": {
            "funding": "Synthetic smoke fixture only; no external funding is asserted.",
            "conflict_of_interest": "Synthetic smoke fixture only; no real author conflict attestation is asserted.",
            "data_availability": "The bundled text-study fixture and actual local run artifacts supply the test data.",
            "code_availability": "The bundled analysis script and recorded manifest supply the local reproduction code.",
            "ai_disclosure": "Paper Factory deterministic templates generated this synthetic workflow manuscript; this is not an author certification for publication.",
        },
    })
    return path


def offline_package(root, ws, paper, settings_path, pandoc):
    with httpx.Client(transport=httpx.MockTransport(mock_directory)) as client:
        venue = discover(ws, "synthetic smoke research", 1, client=client)[0]
    spec, body = synthetic_policy(venue.id)
    path = root / "synthetic-policy.json"
    write_json(path, spec)
    requests = []

    def policy_response(request):
        if request.url.host != "93.184.216.34" or request.headers.get("Host") not in {"synthetic.example.org", "mjl.clarivate.com"}:
            raise AssertionError("Unexpected synthetic policy request")
        requests.append(request.headers["Host"])
        return httpx.Response(200, text=body, headers={"content-type": "text/html"})

    with patch("socket.getaddrinfo", public_fixture_dns), httpx.Client(transport=httpx.MockTransport(policy_response)) as client:
        policy = verify_policy(ws, venue, path, client=client)
        if policy.status != "verified":
            raise RuntimeError(f"Synthetic reviewed policy failed: {policy.issues}")
        submission = select(ws, paper, venue, policy)
        submission, compiled_root = compile_submission(ws, submission, settings_path, pandoc=pandoc, client=client)
        package, package_root = build_package(ws, submission, client=client)
    submission = ws.get("submission", submission.id, Submission)
    report = verify_package(ws, submission)
    if not report["ready"] or submission.state != "SUBMISSION_READY":
        raise RuntimeError(f"Synthetic package is not ready: {report['errors']}")
    # Detect an actual package alteration, then restore the artifact so the
    # delivered fixture remains a working, valid product example.
    target = package_root / "tables" / "results.csv"
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"synthetic tamper detection\n")
        tamper = verify_package(ws, submission)
        if tamper["ready"] or not any("artifact changed" in error for error in tamper["errors"]):
            raise RuntimeError("Package alteration was not detected")
    finally:
        target.write_bytes(original)
    restored = verify_package(ws, submission)
    if not restored["ready"]:
        raise RuntimeError(f"Package restoration failed: {restored['errors']}")
    from pypdf import PdfReader
    pdf = PdfReader(compiled_root / "manuscript.pdf")
    text = " ".join(page.extract_text() for page in pdf.pages)
    if not pdf.pages or "Measured corpus byte length" not in text:
        raise RuntimeError("Actual PDF lacks the evidence-backed measurement")
    return {
        "synthetic_service_and_reviewer_fixture": True, "submission_id": submission.id, "state": submission.state,
        "policy_requests": requests, "policy_refetched_for_compile_and_package": len(requests) == 6,
        "package": str(package_root), "archive": str(package_root / "submission.zip"),
        "pdf": str(compiled_root / "manuscript.pdf"), "pdf_pages": len(pdf.pages),
        "ready": restored["ready"], "tamper_detected": not tamper["ready"], "external_submission_performed": False,
    }


def live_package(root, ws, paper, settings_path, pandoc):
    venue = discover(ws, "PLOS ONE", 1)[0]
    path = root / "live-plos-policy.json"
    write_json(path, {
        "venue_id": venue.id,
        "sources": ["https://www.plosone.org/", "https://journals.plos.org/plosone/s/submission-guidelines"],
        "official_origins": [{
            "origin": "https://journals.plos.org", "rationale": "Old discovered journal homepage redirects to the current publisher journal website",
            "evidence_url": "https://www.plosone.org/", "evidence_excerpt": "PLOS One Skip to main content",
        }],
        # This narrow supplied excerpt is checked against the newly fetched page.
        "values": {"manuscript_word_limit": None},
        "evidence": {"manuscript_word_limit": {
            "source_url": "https://journals.plos.org/plosone/s/submission-guidelines",
            "excerpt": "There are no restrictions on word count, number of figures, or amount of supporting information.",
            "interpretation": "This reviewed rule does not set a manuscript word maximum; all other requirements are unreviewed.",
        }},
        "reviewed_by": "Synthetic Smoke Reviewer; limited excerpt fixture only",
    })
    policy = verify_policy(ws, venue, path)
    submission = select(ws, paper, venue, policy)
    submission, compiled_root = compile_submission(ws, submission, settings_path, pandoc=pandoc)
    package, package_root = build_package(ws, submission)
    report = verify_package(ws, ws.get("submission", submission.id, Submission))
    if package.ready or report["ready"]:
        raise RuntimeError("Incomplete real journal policy was falsely marked submission ready")
    return {"real_discovery_and_official_pages": True, "venue": venue.name, "venue_id": venue.id,
            "policy_status": policy.status, "policy_sources": [source.model_dump(mode="json") for source in policy.sources],
            "submission_id": submission.id, "ready": False, "blockers": report["errors"],
            "package": str(package_root), "pdf": str(compiled_root / "manuscript.pdf"),
            "external_submission_performed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Empty external output directory; default is a new temporary directory")
    parser.add_argument("--pandoc", help="Installed Pandoc executable; required if Pandoc is not on PATH")
    parser.add_argument("--live", action="store_true", help="Also make explicit keyless PLOS discovery and official public-page requests")
    args = parser.parse_args()
    root = args.root.resolve() if args.root else Path(tempfile.mkdtemp(prefix="paperfactory-phase2-smoke-"))
    if root.exists() and any(root.iterdir()):
        raise ValueError("Smoke output root must be empty")
    root.mkdir(parents=True, exist_ok=True)
    # Do not mix a synthetic review test with a user's real author identity.
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("PF_AUTHOR_")}
    environment["PF_HOME"] = str(root / "home")
    with patch.dict(os.environ, environment, clear=True):
        ws, paper, run, claims = prepare_scientific_fixture(root, args.pandoc)
        settings_path = settings(root)
        summary = {"workspace": str(ws.root), "scientific_fixture_approval_only": True,
                   "actual_experiment": {"id": run.id, "status": run.status, "metrics": run.metrics, "source_digest": run.source_digest,
                                         "artifacts": [asset.model_dump(mode="json") for asset in run.artifacts if asset.kind == "raw"]},
                   "actual_claim_ids": [claim.id for claim in claims],
                   "freeze": paper.freeze_digest, "offline": offline_package(root, ws, paper, settings_path, args.pandoc)}
        if args.live:
            summary["live"] = live_package(root, ws, paper, settings_path, args.pandoc)
    write_json(root / "phase2-smoke-result.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

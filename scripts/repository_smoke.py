"""Explicit live Git+Crossref smoke; never execute imported repository code."""

import argparse
import json
import os
import tempfile
from pathlib import Path

from smoke import run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Explicit local path or public/private Git URL")
    parser.add_argument("--query", required=True, help="Only this query and resulting DOIs go to Crossref")
    parser.add_argument("--pandoc", help="Optional Pandoc executable")
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix="paperfactory-repository-smoke-"))
    workspace = root / "workspace"
    env = dict(os.environ, PF_HOME=str(root / "home"), PYTHONIOENCODING="utf-8")
    imported = run(["start", args.source], env, workspace)
    study = run(["research", "--domain", "software_engineering"], env, workspace)
    citations = run(["literature", "search", args.query, "--limit", "2"], env, workspace)
    experiment = run(["experiment", "run"], env, workspace)
    command = ["manuscript", "build"]
    if args.pandoc:
        command += ["--pandoc", args.pandoc]
    manuscript = run(command, env, workspace)
    integrity = run(["integrity", "check"], env, workspace)
    summary = {"project": imported, "study": study, "verified_references": len(citations["citations"]), "experiment_status": experiment["status"], "metrics": experiment["metrics"], "manuscript": manuscript, "integrity": integrity}
    (root / "smoke-result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

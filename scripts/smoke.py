"""Exercise the installed CLI on a real local fixture; artifacts stay external."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run(arguments: list[str], environment: dict, workspace: Path | None = None) -> dict:
    prefix = [sys.executable, "-m", "paper_factory.cli"]
    if workspace:
        prefix += ["--workspace", str(workspace)]
    result = subprocess.run(prefix + arguments, capture_output=True, text=True, encoding="utf-8", env=environment, check=False)
    if result.returncode:
        raise RuntimeError(f"{arguments[0]} failed: {result.stderr}\n{result.stdout}")
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, help="Empty external output directory; defaults to a new temporary directory.")
    parser.add_argument("--pandoc", help="Optional Pandoc executable to verify standalone TeX export.")
    parser.add_argument("--query", help="Optional explicit live Crossref query; no project files are transmitted.")
    args = parser.parse_args()
    root = args.root.resolve() if args.root else Path(tempfile.mkdtemp(prefix="paperfactory-smoke-"))
    workspace = root / "workspace"
    env = dict(os.environ, PF_HOME=str(root / "home"), PYTHONIOENCODING="utf-8")
    fixture = Path(__file__).resolve().parents[1] / "examples" / "text-study"
    imported = run(["start", str(fixture)], env, workspace)
    study = run(["research"], env, workspace)
    literature = None
    inventory = run(["experiment", "run"], env, workspace)
    study = run(["research", "--question", "How does lossless compression change the byte length of the supplied text corpus?", "--title", "A descriptive analysis of corpus compression"], env, workspace)
    if args.query:
        literature = run(["literature", "search", args.query, "--limit", "2"], env, workspace)
    manifest = {
        "id": "corpus-compression", "study_id": study["study"], "source_commit": imported["source_commit"],
        "source_digest": imported["snapshot_digest"], "command": ["{python}", "analyze.py"],
        "inputs": ["analyze.py", "corpus.txt"], "expected_outputs": ["results.json"],
        "metrics": [
            {"name": "original_bytes", "output": "results.json", "pointer": "/observations/original_bytes", "unit": "bytes", "description": "Measured corpus byte length"},
            {"name": "compressed_bytes", "output": "results.json", "pointer": "/observations/compressed_bytes", "unit": "bytes", "description": "Measured compressed corpus byte length"},
            {"name": "compression_ratio", "output": "results.json", "pointer": "/metrics/compression_ratio", "unit": "ratio", "description": "Ratio of compressed length to corpus length"},
        ],
    }
    path = root / "compression-manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    run(["experiment", "register", str(path)], env, workspace)
    compression = run(["experiment", "run", manifest["id"]], env, workspace)
    command = ["manuscript", "build"]
    if args.pandoc:
        command += ["--pandoc", args.pandoc]
    manuscript = run(command, env, workspace)
    report = run(["integrity", "check"], env, workspace)
    status = run(["status"], env, workspace)
    summary = {"workspace": str(workspace), "project": imported, "study": study, "literature": literature, "inventory": inventory["status"], "compression": compression["metrics"], "manuscript": manuscript, "integrity": report, "status": status}
    (root / "smoke-result.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

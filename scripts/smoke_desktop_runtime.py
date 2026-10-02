"""Exercise bundled native tools without accounts, model calls or real research."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    from paper_factory.autonomous.provider import CodexProvider, _cli_command
    from paper_factory.autonomous.windows_runner import WindowsRunner
    from paper_factory.conversion import convert
    import pypandoc
    from pypdf import PdfReader
    from docx import Document

    runtime = Path(sys.executable).resolve().parents[1]
    os.environ["PF_NODE_BIN"] = str(runtime / "node" / "node.exe")
    os.environ["PATH"] = os.pathsep.join([str(runtime / "node"), str(runtime / "git" / "cmd"), os.environ["SystemRoot"], str(Path(os.environ["SystemRoot"]) / "System32")])
    pandoc = Path(pypandoc.get_pandoc_path())
    pandoc = pandoc if pandoc.is_file() else pandoc.with_suffix(".exe")
    assert shutil.which("python") is None, "The smoke PATH must not provide a system Python"
    git = subprocess.check_output(["git", "--version"], text=True).strip()
    # Exercise the application's configured launcher, including Windows
    # environments that omit .CMD from PATHEXT, instead of bypassing resolution.
    os.environ["PATHEXT"] = ".EXE"
    cli = runtime / "codex" / "node_modules" / ".bin" / "codex.cmd"
    binary = CodexProvider(cli)._binary()
    assert binary is not None, "The bundled Codex launcher must resolve without .CMD in PATHEXT"
    codex = subprocess.check_output([*_cli_command(binary), "--version"], text=True, timeout=15).strip()
    runner = WindowsRunner()
    assert runner.status()["ready"] and set(runner.status()["runtimes"]) == {"python", "node"}
    with tempfile.TemporaryDirectory(prefix="paperfactory-desktop-smoke-") as temporary:
        root = Path(temporary)
        source, code = root / "source", root / "code"
        source.mkdir()
        code.mkdir()
        (source / "production.py").write_text("def transform(value):\n    return value * 2\n", encoding="utf-8")
        (source / "production.cjs").write_text("module.exports = value => value * 2;\n", encoding="utf-8")
        (code / "experiment.py").write_text(
            "import json, os, sys\nfrom pathlib import Path\n"
            "sys.path.insert(0, os.environ['PF_SOURCE_ROOT'])\nfrom production import transform\n"
            "value = transform(2)\nassert value == 4\n"
            "Path(os.environ['PF_OUTPUT_ROOT'], 'observations.json').write_text(json.dumps({'value':value}), encoding='utf-8')\n",
            encoding="utf-8")
        (code / "experiment.cjs").write_text(
            "const fs = require('node:fs'); const path = require('node:path');\n"
            "const transform = require(path.join(process.env.PF_SOURCE_ROOT, 'production.cjs'));\n"
            "const value = transform(2); if (value !== 4) throw new Error('Smoke oracle failed');\n"
            "fs.writeFileSync(path.join(process.env.PF_OUTPUT_ROOT, 'observations.json'), JSON.stringify({value}));\n",
            encoding="utf-8")
        for language, entry, production in [("python", "experiment.py", "production.py:transform"), ("node", "experiment.cjs", "production.cjs")]:
            result = runner.run(source, code, root / language, runtime=language, entrypoint=entry, production_entrypoint=production, timeout_seconds=15)
            assert result["status"] == "succeeded", result
            assert result["cleanup_confirmed"] is True and result["production_calls"], result
            assert json.loads(Path(result["output_path"]).read_text(encoding="utf-8"))["value"] == 4
        markdown = root / "smoke.md"
        markdown.write_text("# Bundled runtime smoke\n\nThis is a synthetic converter check.\n", encoding="utf-8")
        convert(markdown, root / "smoke.pdf", pandoc=str(pandoc))
        convert(markdown, root / "smoke.docx", pandoc=str(pandoc))
        assert len(PdfReader(root / "smoke.pdf").pages) == 1
        assert any("synthetic converter check" in paragraph.text for paragraph in Document(root / "smoke.docx").paragraphs)
    print(json.dumps({"passed": True, "python": sys.version.split()[0], "node": runner.status()["versions"]["node"], "git": git, "codex": codex,
                      "native_workers": ["python", "node"], "cleanup_confirmed": True, "exports": ["pdf", "docx"], "model_calls": 0}))


if __name__ == "__main__":
    main()

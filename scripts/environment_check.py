"""Read-only diagnostics for the skill's local document prerequisites.

Does not install software, launch Word, contact services, or inspect credentials.
Detected prerequisites do not establish a successful native export.
"""

import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

from _publication_convert import pandoc_binary, pandoc_version
from _publication_files import ensure_unlinked
from _publication_templates import official_template


def _packages() -> list[dict]:
    rows = []
    requirements = Path(__file__).resolve().parents[1] / "requirements.txt"
    for line in requirements.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        match = re.fullmatch(r"([\w-]+)>=(\d+(?:\.\d+)*),<(\d+(?:\.\d+)*)", line.strip())
        if not match:
            raise ValueError(f"Unsupported requirement in package: {line}")
        name, floor, ceiling = match.groups()
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            rows.append({"name": name, "requirement": line, "version": None, "status": "missing"})
            continue
        # Restrict verification to release versions; unusual versions remain visible.
        if re.fullmatch(r"\d+(?:\.\d+)*", version):
            numbers = lambda value: tuple(int(x) for x in value.split(".")) + (0,) * (4 - len(value.split(".")))
            status = "detected" if numbers(floor) <= numbers(version) < numbers(ceiling) else "incompatible"
        else:
            status = "unverified_version"
        rows.append({"name": name, "requirement": line, "version": version, "status": status})
    return rows


def _word_registration() -> dict:
    if sys.platform != "win32":
        return {"status": "unsupported_platform", "method": "Windows COM registry; Word not launched"}
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID") as key:
            class_id = winreg.QueryValueEx(key, None)[0]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{class_id}\LocalServer32") as key:
            command = winreg.QueryValueEx(key, None)[0]
        return {"status": "detected", "registered_command": command,
                "method": "COM registration only; startup, license and rendering not tested"}
    except OSError as exc:
        return {"status": "missing", "method": "Windows COM registry; Word not launched", "detail": str(exc)}


def diagnose(pandoc: str | None = None) -> dict:
    packages = _packages()
    try:
        binary = pandoc_binary(pandoc)
        pandoc_result = {"status": "detected", "path": str(binary), "version": pandoc_version(binary)}
    except (ValueError, OSError, subprocess.SubprocessError, IndexError) as exc:
        pandoc_result = {"status": "missing_or_unusable", "detail": str(exc)}
    templates = []
    for venue in ("ieee-software", "ieee-security-privacy"):
        try:
            path, record = official_template(venue)
            templates.append({"venue": venue, "status": "verified", "path": str(path), "sha256": record["sha256"]})
        except (ValueError, OSError, KeyError) as exc:
            templates.append({"venue": venue, "status": "missing_or_changed", "detail": str(exc)})
    word = _word_registration()
    powershell = shutil.which("powershell.exe") if sys.platform == "win32" else None
    python_ok = sys.version_info >= (3, 11)
    for package in packages:
        package["required_for_export"] = package["name"] != "pypandoc_binary"
    detected = (python_ok and sys.platform == "win32" and bool(powershell) and
                word["status"] == "detected" and pandoc_result["status"] == "detected" and
                all(x["status"] == "detected" for x in packages if x["required_for_export"]) and
                all(x["status"] == "verified" for x in templates))
    return {"created_at": datetime.now(timezone.utc).isoformat(),
            "python": {"executable": sys.executable, "version": platform.python_version(), "supported": python_ok},
            "platform": platform.platform(), "skill_directory": str(Path(__file__).resolve().parents[1]),
            "packages": packages, "pandoc": pandoc_result, "powershell": powershell,
            "word": word, "official_templates": templates,
            "native_export_prerequisites_detected": detected,
            "native_export_verified": False,
            "limitations": ["Registration and package metadata do not verify imports, Word licensing or PDF rendering.",
                            "pypandoc_binary is an optional Pandoc provider when a usable executable is already selected.",
                            "Font substitution and all final pages must be checked during actual export.",
                            "No software installation, account connection, credential inspection or network request was performed."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New absolute directory outside the installed skill")
    parser.add_argument("--pandoc", help="Existing absolute Pandoc executable; no download")
    args = parser.parse_args()
    try:
        target = args.output_dir
        if not target.is_absolute():
            raise ValueError("Use an absolute output directory")
        ensure_unlinked(target)
        target = target.resolve()
        skill = Path(__file__).resolve().parents[1]
        if target.is_relative_to(skill):
            raise ValueError("Keep diagnostics outside the skill directory")
        if target.exists():
            raise ValueError("Output directory must be new")
        result = diagnose(args.pandoc)
        target.mkdir(parents=True, exist_ok=False)
        (target / "environment.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        lines = ["# Local document environment", "", f"Python: {result['python']['executable']} ({result['python']['version']})",
                 f"Skill: {result['skill_directory']}", f"Native export prerequisites detected: {result['native_export_prerequisites_detected']}",
                 "Native export verified: False", "", "| Component | Status |", "| --- | --- |"]
        lines += [f"| {x['name']} {x['version'] or ''} | {x['status']} |" for x in result["packages"]]
        lines += [f"| Pandoc | {result['pandoc']['status']} |", f"| Word registration | {result['word']['status']} |",
                  f"| PowerShell | {'detected' if result['powershell'] else 'missing'} |"]
        lines += [f"| {x['venue']} template | {x['status']} |" for x in result["official_templates"]]
        lines += ["", *result["limitations"]]
        (target / "environment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(json.dumps({"output_dir": str(target), "native_export_prerequisites_detected": result["native_export_prerequisites_detected"]}))
        return 0 if result["native_export_prerequisites_detected"] else 1
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

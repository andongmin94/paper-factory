"""Verify a source-built private macOS plugin and retain bounded CI evidence.

This runs trusted preparation, isolation diagnostics and repository tests only.
It creates no scientific study, uses no model provider and publishes nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MAX_CAPTURE = 2 * 1024 * 1024
SUITES = (
    "test_quickjs_runner.py", "test_quickjs_platforms.py", "test_host_context.py",
    "test_cloud_packaging.py", "test_provided_probe.py", "test_cloud.py", "test_conversion.py",
)
REQUIRED_CASES = (
    "test_macos_guardian_normal_guest_has_actual_bound_completion",
    "test_macos_controller_crash_eof_reaps_owned_worker_and_recovers",
    "test_pdf_export_keeps_complete_long_title_in_one_typst_heading",
    "test_docx_export_uses_native_line_and_page_settings",
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def safe_log(raw: bytes) -> bool:
    # Our fixed commands do not dump the environment. Do not upload an
    # unexpected credential-bearing log while calling it an original receipt.
    return not re.search(rb"(?i)(?:https?|socks5h?)://[^\s/@]+(?::[^\s/@]*)?@|\b(?:ghp_|github_pat_|sk-)[A-Za-z0-9_-]{16,}", raw)


def capture(command: list[str], destination: Path, report: dict, *, timeout: int) -> dict:
    label = f"{len(report['commands']) + 1:02d}"
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=timeout, check=False)
        stdout, stderr, exit_code = result.stdout, result.stderr, result.returncode
        failure = None
    except subprocess.TimeoutExpired as error:
        stdout, stderr, exit_code = error.stdout or b"", error.stderr or b"", None
        failure = "timeout"
    except OSError as error:
        stdout, stderr, exit_code = b"", b"", None
        failure = type(error).__name__
    retained = len(stdout) <= MAX_CAPTURE and len(stderr) <= MAX_CAPTURE and safe_log(stdout) and safe_log(stderr)
    receipt = {"argv": command, "cwd": str(ROOT), "exit_code": exit_code,
               "failure": failure, "raw_bytes_retained": retained,
               "stdout": {"size": len(stdout), "sha256": digest(stdout)},
               "stderr": {"size": len(stderr), "sha256": digest(stderr)}}
    if retained:
        for name, raw in (("stdout", stdout), ("stderr", stderr)):
            path = destination / f"{label}.{name}.bin"
            path.write_bytes(raw)
            receipt[name]["file"] = path.name
    report["commands"].append(receipt)
    write_json(destination / f"{label}.command.json", receipt)
    if not retained:
        raise ValueError("Command log was not safe or bounded for artifact retention")
    if exit_code != 0:
        raise ValueError("The recorded verification command failed; no retry or fallback was attempted")
    return {"stdout": stdout, "stderr": stderr}


def checked_file(path: Path, *, root: Path, limit: int = 16 * 1024 * 1024) -> bytes:
    if (not path.is_absolute() or not path.is_file() or not path.resolve().is_relative_to(root.resolve())
            or path.is_symlink() or path.stat().st_nlink != 1 or path.stat().st_size > limit):
        raise ValueError("Verification artifact is outside its ordinary bounded scope")
    return path.read_bytes()


def retain(source: Path, destination: Path, *, root: Path, expected: dict | None = None, limit: int = 16 * 1024 * 1024) -> dict:
    raw = checked_file(source, root=root, limit=limit)
    if expected and (expected["size"] != len(raw) or expected["sha256"] != digest(raw)):
        raise ValueError("Actual artifact differs from its native receipt")
    if destination.suffix in {".json", ".md", ".tex", ".typ", ".xml"} and not safe_log(raw):
        raise ValueError("Unexpected sensitive diagnostic content was not retained")
    destination.write_bytes(raw)
    return {"file": destination.name, "size": len(raw), "sha256": digest(raw)}


def verify(data: Path, expected_machine: str) -> dict:
    data = data.absolute()
    if (data.exists() or any(path.is_symlink() for path in (data, *data.parents))
            or data == ROOT or data in ROOT.parents):
        raise ValueError("Use a new ordinary CI scratch directory")
    data.mkdir(parents=True)
    diagnostics, distribution = data / "diagnostics", data / "distribution"
    diagnostics.mkdir()
    distribution.mkdir()
    report = {"ok": False, "scope": "Native macOS CI preparation and diagnostics only; no research paper or Chat execution proof.",
              "stage": "host", "host": {"system": platform.system(), "machine": platform.machine(),
                 "python": platform.python_version(), "expected_machine": expected_machine},
              "source": {name: os.environ.get(name) for name in ("GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")},
              "commands": [], "artifacts": {}, "scientific_studies_executed": 0,
              "model_calls": 0, "research_sources_bundled": False, "fallback_used": False}
    prepared = {}
    try:
        if sys.platform != "darwin" or platform.machine() != expected_machine:
            raise ValueError("The actual macOS architecture differs from the declared matrix")
        if sys.version_info[:2] != (3, 12) or sys.implementation.name != "cpython":
            raise ValueError("This verification requires its selected CPython3.12 host")
        report["stage"] = "source-package"
        build = json.loads(capture([sys.executable, "scripts/build_plugin.py"], diagnostics, report, timeout=120)["stdout"])
        if build.get("ok") is not True or build.get("mcp_bundled") is not False or build.get("research_inputs_bundled") is not False:
            raise ValueError("Source package did not satisfy the declared general distribution scope")
        archive = Path(build["archive"])
        raw = checked_file(archive, root=ROOT / "dist", limit=100 * 1024 * 1024)
        if digest(raw) != build["archive_sha256"] or len(raw) != build["archive_bytes"]:
            raise ValueError("Built plugin ZIP differs from its original build report")
        with zipfile.ZipFile(archive) as bundle:
            if bundle.testzip():
                raise ValueError("Plugin ZIP CRC validation failed")
            inventory = bundle.read("skills/paper-factory/inventory.json")
            if digest(inventory) != build["inventory_sha256"]:
                raise ValueError("Plugin inventory differs from the build report")
        skill = Path(build["plugin"]) / "skills/paper-factory"
        report["package"] = {"version": build["version"], "sha256": digest(raw), "size": len(raw),
                             "inventory_sha256": digest(inventory), "files": build["declared_files"]}
        report["stage"] = "private-preparation"
        preparation = json.loads(capture([sys.executable, str(skill / "scripts/prepare_host.py"),
            "--mode", "private", "--data", str(data / "host")], diagnostics, report, timeout=1200)["stdout"])
        if preparation.get("ok") is not True:
            raise ValueError("Actual private preparation is not ready")
        prepared = preparation["result"]
        python, environment_file = prepared["python"], prepared["environment_file"]
        if prepared.get("mode") != "private" or prepared.get("controller_imported") is not True:
            raise ValueError("Preparation did not import the actual private controller")
        report["prepared_environment_sha256"] = prepared["environment_sha256"]
        report["stage"] = "runtime-extraction"
        runtime = json.loads(capture([python, str(skill / "scripts/prepare_runtime.py"), "--data", str(data / "runtime")],
                                    diagnostics, report, timeout=60)["stdout"])
        if runtime.get("ok") is not True:
            raise ValueError("Pinned runtime extraction failed")
        report["stage"] = "actual-launcher-readiness"
        readiness = json.loads(capture([python, str(skill / "scripts/run_workflow.py"), "--environment-file", environment_file,
            "--data", str(data / "controller"), "--runtime-root", runtime["runtime_root"], "environment"],
            diagnostics, report, timeout=120)["stdout"])
        if readiness.get("ready") is not True or readiness.get("cleanup_confirmed") is not True or readiness.get("backend") != "quickjs-wasm":
            raise ValueError("Actual selected native readiness or owned cleanup failed")
        journal = data / "controller/quickjs-supervisor/owned-workers.json"
        if json.loads(checked_file(journal, root=data)).get("workers") != []:
            raise ValueError("The exact launcher left unresolved worker records")
        report["readiness"] = readiness
        report["stage"] = "native-regression-suites"
        junit = data / "native-tests.xml"
        capture([sys.executable, "-m", "pytest", "-q", "--tb=short", "--junitxml=" + str(junit),
                 "--basetemp=" + str(data / "tests"), *(str(ROOT / "tests" / name) for name in SUITES)],
                diagnostics, report, timeout=1200)
        cases = ET.fromstring(checked_file(junit, root=data)).findall(".//testcase")
        for required in REQUIRED_CASES:
            matches = [case for case in cases if case.attrib.get("name", "").split("[")[0] == required]
            if not matches or any(case.find(tag) is not None for case in matches for tag in ("skipped", "failure", "error")):
                raise ValueError("A mandatory actual macOS or native converter test did not pass")
        report["tests"] = {"cases": len(cases), "skipped": sum(case.find("skipped") is not None for case in cases),
                           "required_actual_cases": list(REQUIRED_CASES), "junit_sha256": digest(junit.read_bytes())}
        report["artifacts"][archive.name] = retain(archive, distribution / archive.name, root=ROOT / "dist", limit=100 * 1024 * 1024)
        report["artifacts"]["build-report.json"] = retain(ROOT / "dist/build-report.json", distribution / "build-report.json", root=ROOT / "dist")
        report.update(ok=True, stage="verified", artifact_scope="Exact original plugin ZIP and build report; diagnostics contain no private runtime binaries, caches, environment files or research inputs.")
    except Exception as error:
        reason = str(error) if safe_log(str(error).encode("utf-8")) else "Sensitive error details were not retained"
        report["error"] = {"exception": type(error).__name__, "message": reason[:1000]}
    # Preserve exact diagnostic outputs and unresolved journals even when an
    # earlier stage failed. Never traverse caches, runtime binaries or test data.
    expected = prepared.get("converter_check", {})
    declared = expected.get("outputs", {})
    report["diagnostic_files_absent"] = []
    sources = [(name, data / "host" / name) for name in (
        "bootstrap-result.json", "prepared-modules.json", "converter-check.md", "converter-check.typ",
        "converter-check.pdf", "converter-check.docx", "converter-check.tex", "converter-check.png")]
    sources += [("owned-workers.json", data / "controller/quickjs-supervisor/owned-workers.json"),
                ("native-tests.xml", data / "native-tests.xml")]
    for name, source in sources:
        if not source.exists():
            report["diagnostic_files_absent"].append(name)
            continue
        try:
            binding = expected.get("png") if name == "converter-check.png" else declared.get(source.suffix[1:])
            report["artifacts"][name] = retain(source, diagnostics / name, root=data, expected=binding)
        except Exception as error:
            report["retention_error"] = {"file": name, "exception": type(error).__name__}
            if report["ok"]:
                report.update(ok=False, stage="diagnostic-retention", error={"exception": type(error).__name__,
                              "message": "A required native diagnostic could not be retained"})
    if report["ok"] and report["diagnostic_files_absent"]:
        report.update(ok=False, stage="diagnostic-retention", error={"exception": "ValueError",
                      "message": "Required native diagnostic outputs are missing"})
    write_json(diagnostics / "verification.json", report)
    if report["ok"]:
        shutil.copyfile(diagnostics / "verification.json", distribution / "verification.json")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--expected-machine", required=True, choices=("arm64", "x86_64"))
    args = parser.parse_args()
    try:
        result = verify(args.data, args.expected_machine)
        print(json.dumps({"ok": result["ok"], "stage": result["stage"], "diagnostics": str(args.data / "diagnostics")}))
        raise SystemExit(0 if result["ok"] else 1)
    except (ValueError, OSError) as error:
        print(json.dumps({"ok": False, "exception": type(error).__name__, "message": "Use the declared native CI host and new scratch directory."}))
        raise SystemExit(1)

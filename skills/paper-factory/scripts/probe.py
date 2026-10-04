"""Inspect packaged bytes and host prerequisites without running a study."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
SKILL_ROOT = Path(__file__).resolve().parents[1]
CORE_MODULES = {"pydantic": "pydantic", "httpx": "httpx", "socksio": "socksio", "beautifulsoup4": "bs4"}
ANALYSIS_MODULES = {"matplotlib": "matplotlib", "numpy": "numpy"}
EXPORT_MODULES = {"typst": "typst", "pypdf": "pypdf", "python-docx": "docx"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_error(error):
    message = str(error)
    message = re.sub(r"(?i)(?:[a-z]:[\\/]|\\\\)[^\s\"'<>]+", "[runtime path]", message)
    message = re.sub(r"(?<![A-Za-z0-9:/])/(?:[^\s\"'<>]+)", "[runtime path]", message)
    message = re.sub(r"(?i)\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_.-]{16,}", "[token]", message)
    return {"code": getattr(error, "code", type(error).__name__), "message": message[:1200]}


def package_access():
    manifest = json.loads((SKILL_ROOT / "inventory.json").read_text(encoding="utf-8"))
    errors = []
    for name, item in manifest["files"].items():
        relative = Path(name)
        if (relative.is_absolute() or "\\" in name or ":" in name
                or any(part in {"", ".", ".."} for part in name.split("/"))):
            raise ValueError("Invalid package inventory name")
        path = SKILL_ROOT / relative
        linked = any(part.is_symlink() or getattr(part, "is_junction", lambda: False)()
                     for part in (path, *path.parents))
        if (linked or not path.is_file() or path.stat().st_nlink != 1
                or path.stat().st_size != item["size"] or digest(path) != item["sha256"]):
            errors.append(name)
    return {"verified": not errors, "files_checked": len(manifest["files"]),
            "changed_or_missing": errors[:20], "inventory_sha256": digest(SKILL_ROOT / "inventory.json"),
            "bundled_core": manifest["core_files"], "package_contains_mcp": False}


def modules(group, *, optional=()):
    result = {}
    for distribution, module in group.items():
        available = importlib.util.find_spec(module) is not None
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            version = None
        result[distribution] = {"importable": available, "version": version,
                                "required": distribution not in optional}
    return result


def http_client():
    """Initialize and close the real inherited HTTP transport without a request."""
    result = {"ready": False, "request_executed": False, "environment_settings_inherited": True}
    try:
        import httpx
        # Preserve the collector's environment-driven proxy/certificate policy.
        # Initialization exercises optional transports; no request is sent.
        with httpx.Client(trust_env=True):
            pass
        result["ready"] = True
    except Exception as error:
        # Proxy URLs, credentials and certificate paths can occur in exceptions.
        # Do not stringify them or serialize a client/configuration object.
        result["error"] = {"code": "HTTP_CLIENT_INIT_FAILED", "exception": type(error).__name__,
                           "message": "HTTPX client initialization failed with inherited environment settings. Provide the declared proxy transport and certificate dependencies, then recheck capabilities."}
    return result


def command(argv, timeout=4):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return {"executed": True, "returncode": result.returncode, "stdout": result.stdout[:2000]}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"executed": False, "error": safe_error(error)}


def pandoc_available():
    """Use the existing converter's actual PATH-or-bundled executable contract."""
    sys.path.insert(0, str(SKILL_ROOT / "src"))
    from paper_factory.conversion import pandoc_binary
    try:
        executable = pandoc_binary(os.environ.get("PYPANDOC_PANDOC") or None)
        result = command([executable, "--version"])
        return {"ready": result.get("returncode") == 0, "version": result}
    except (ImportError, ValueError, OSError) as error:
        return {"ready": False, "error": safe_error(error)}


def capabilities():
    mode = os.environ.get("PF_HOST_MODE", "private")
    engine = os.environ.get("PF_PDF_ENGINE", "typst")
    if mode not in {"private", "provided"} or engine not in {"typst", "pdflatex"}:
        raise ValueError("Unsupported explicitly selected host mode or PDF engine")
    if mode == "private" and engine != "typst":
        raise ValueError("Private preparation requires its pinned Typst engine")
    report = {
        "scope": "Current package/host prerequisites only; installation, isolation and research success are separate checks.",
        "platform": {"system": platform.system(), "release": platform.release(),
                     "machine": platform.machine(), "python": platform.python_version(),
                     "implementation": platform.python_implementation()},
        "package": package_access(),
        "host_mode": mode,
        "pdf_engine": engine,
        "dependencies": {
            "core": modules(CORE_MODULES, optional=("socksio",) if mode == "provided" else ()),
            "analysis": modules(ANALYSIS_MODULES),
            "exports": modules(EXPORT_MODULES, optional=("typst",) if engine == "pdflatex" else ())},
        "http_client": http_client(),
        "tools": {name: bool(shutil.which(name)) for name in ("node", "pandoc", "git")},
        "controller_imported": False,
        "pandoc": {"ready": False, "reason": "Core prerequisites or package inventory unavailable"},
        "isolation_checked": False, "experiment_executed": False,
        "network_access_tested": False, "public_install_tested": False,
    }
    if (report["package"]["verified"] and sys.version_info >= (3, 11)
            and all(item["importable"] for item in report["dependencies"]["core"].values() if item["required"])
            and (mode == "private" or report["http_client"]["ready"])):
        try:
            sys.path.insert(0, str(SKILL_ROOT / "src"))
            from paper_factory.workflow import WorkflowService
            report["controller_imported"] = WorkflowService is not None
            report["pandoc"] = pandoc_available()
        except Exception as error:
            report["controller_error"] = safe_error(error)
    report["mcp_imported"] = any(name == "mcp" or name.startswith("mcp.") for name in sys.modules)
    report["instructions"] = "Use the reported preparation interpreter and explicitly selected QuickJS environment command to check current isolation."
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capabilities",))
    args = parser.parse_args()
    try:
        print(json.dumps({"ok": True, "action": args.action, "result": capabilities()}, allow_nan=False))
    except Exception as error:
        print(json.dumps({"ok": False, "action": args.action, "error": safe_error(error)}))
        raise SystemExit(1)

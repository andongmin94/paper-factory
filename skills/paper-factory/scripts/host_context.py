"""Bind the controller to the actual selected host and module bytes."""
from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import sys


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def capture_modules(pdf_engine: str) -> dict:
    """Record actual imported third-party files, without installing anything."""
    required = ("pydantic", "pydantic_core", "httpx", "bs4", "matplotlib.pyplot",
                "numpy", "pypdf", "docx", "lxml.etree")
    if pdf_engine == "typst":
        required += ("typst",)
    elif pdf_engine != "pdflatex":
        raise ValueError("Unsupported selected PDF engine")
    for name in required:
        importlib.import_module(name)
    distributions = {"pydantic", "pydantic_core", "httpx", "beautifulsoup4", "matplotlib",
                     "numpy", "pypdf", "python-docx", "lxml"}
    if pdf_engine == "typst":
        distributions.add("typst")
    roots, versions, records = set(), {}, {}
    for name in sorted(distributions):
        distribution = importlib.metadata.distribution(name)
        versions[name] = distribution.version
        roots.add(Path(distribution.locate_file("")).resolve())
        for item in distribution.files or ():
            if str(item).endswith((".dist-info/METADATA", ".dist-info/RECORD")):
                path = Path(distribution.locate_file(item)).resolve()
                if path.is_file():
                    records[str(path)] = {"size": path.stat().st_size,
                                          "sha256": _digest(path)}
    modules = {}
    for name, module in tuple(sys.modules.items()):
        location = getattr(module, "__file__", None)
        if not location:
            continue
        path = Path(location).resolve()
        if path.is_file() and any(path.is_relative_to(root) for root in roots):
            modules[name] = str(path)
            records[str(path)] = {"size": path.stat().st_size,
                                  "sha256": _digest(path)}
    if not all(name in modules for name in required) or len(records) > 4096:
        raise ValueError("Required installed module identities are unavailable")
    return {"schema_version": 1, "distributions": versions, "modules": modules,
            "files": dict(sorted(records.items())),
            "scope": "Actual imported third-party and native-extension files plus selected metadata; not upstream wheel authentication or every installed resource."}


def _binary(record: dict, label: str) -> Path:
    if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
        raise ValueError(f"Invalid prepared {label} record")
    if not isinstance(record["path"], str) or not Path(record["path"]).is_absolute():
        raise ValueError(f"Prepared {label} path must be absolute")
    expected = record["sha256"]
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError(f"Invalid prepared {label} digest")
    path = Path(record["path"])
    if not path.is_file() or _digest(path) != expected:
        raise ValueError(f"Prepared {label} bytes changed")
    return path


def apply_prepared_host(environment_file: str | Path) -> dict:
    path = Path(environment_file)
    if not path.is_absolute() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError("Use the exact environment_file returned by prepare_host")
    if any(item.is_symlink() or getattr(item, "is_junction", lambda: False)()
           for item in (path, *path.parents)):
        raise ValueError("Prepared environment path is linked")
    config = json.loads(path.read_bytes())
    if (not isinstance(config, dict) or set(config) != {
            "schema_version", "mode", "python", "node", "pandoc", "pdf_engine", "pdflatex", "modules", "variables"}
            or type(config["schema_version"]) is not int or config["schema_version"] != 2
            or not isinstance(config["mode"], str) or config["mode"] not in {"private", "provided"}
            or not isinstance(config["pdf_engine"], str) or config["pdf_engine"] not in {"typst", "pdflatex"}
            or config["mode"] == "private" and config["pdf_engine"] != "typst"):
        raise ValueError("Unsupported selected host environment format")
    python = config["python"]
    if not isinstance(python, dict) or set(python) != {"path", "prefix", "sha256"}:
        raise ValueError("Invalid prepared Python record")
    executable = _binary({key: python[key] for key in ("path", "sha256")}, "Python")
    if not isinstance(python["prefix"], str):
        raise ValueError("Invalid selected Python prefix")
    prefix = Path(python["prefix"])
    if (not prefix.is_absolute() or not prefix.is_dir()
            or prefix.resolve() != Path(sys.prefix).resolve()
            or not os.path.samefile(executable, sys.executable)):
        raise ValueError("Run the controller with the selected Python returned by prepare_host")
    node = _binary(config["node"], "Node")
    pandoc = _binary(config["pandoc"], "Pandoc")
    for binary in (node, pandoc):
        if any(item.is_symlink() or getattr(item, "is_junction", lambda: False)()
               for item in (binary, *binary.parents)):
            raise ValueError("Prepared executable path is linked")
    latex = None
    if config["pdf_engine"] == "pdflatex":
        item = config["pdflatex"]
        if not isinstance(item, dict) or set(item) != {"path", "target_path", "sha256"}:
            raise ValueError("Invalid prepared pdflatex identity")
        latex = _binary({key: item[key] for key in ("path", "sha256")}, "pdflatex")
        if not isinstance(item["target_path"], str):
            raise ValueError("Invalid prepared pdflatex target")
        target = Path(item["target_path"])
        if (not target.is_absolute() or target != latex.resolve()
                or any(p.is_symlink() or getattr(p, "is_junction", lambda: False)() for p in (target, *target.parents))):
            raise ValueError("Prepared pdflatex target changed")
    elif config["pdflatex"] is not None:
        raise ValueError("Typst preparation cannot declare a pdflatex executable")
    manifest_path = _binary(config["modules"], "module manifest")
    if manifest_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Prepared module manifest exceeds its boundary")
    manifest = json.loads(manifest_path.read_bytes())
    if (not isinstance(manifest, dict) or set(manifest) != {"schema_version", "distributions", "modules", "files", "scope"}
            or type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1
            or not isinstance(manifest["files"], dict) or not 1 <= len(manifest["files"]) <= 4096
            or not isinstance(manifest["modules"], dict) or not isinstance(manifest["distributions"], dict)
            or not isinstance(manifest["scope"], str)
            or not all(isinstance(name, str) and isinstance(version, str)
                       for name, version in manifest["distributions"].items())
            or not all(isinstance(name, str) and isinstance(location, str) and location in manifest["files"]
                       for name, location in manifest["modules"].items())):
        raise ValueError("Invalid prepared module manifest")
    for filename, item in manifest["files"].items():
        if not isinstance(item, dict) or set(item) != {"size", "sha256"}:
            raise ValueError("Invalid prepared module file record")
        module_path = _binary({"path": filename, "sha256": item["sha256"]}, "module")
        if type(item["size"]) is not int or module_path.stat().st_size != item["size"]:
            raise ValueError("Prepared module size changed")
    variables = config["variables"]
    if not isinstance(variables, dict) or set(variables) - {"MPLCONFIGDIR"}:
        raise ValueError("Private preparation declares unsupported environment variables")
    selected = {"PF_NODE_BIN": str(node), "PYPANDOC_PANDOC": str(pandoc),
                "PF_HOST_MODE": config["mode"], "PF_PDF_ENGINE": config["pdf_engine"],
                "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    if latex is not None:
        selected["PF_PDFLATEX_BIN"] = str(latex)
    if "MPLCONFIGDIR" in variables:
        if not isinstance(variables["MPLCONFIGDIR"], str):
            raise ValueError("Invalid selected Matplotlib cache path")
        directory = Path(variables["MPLCONFIGDIR"])
        if not directory.is_absolute() or not directory.is_dir():
            raise ValueError("Prepared Matplotlib cache directory is unavailable")
        selected["MPLCONFIGDIR"] = str(directory)
    # Native imports may initialize Matplotlib's cache. Use only the approved
    # directory during the check, and restore the process environment on failure.
    previous_cache = os.environ.get("MPLCONFIGDIR")
    try:
        if "MPLCONFIGDIR" in selected:
            os.environ["MPLCONFIGDIR"] = selected["MPLCONFIGDIR"]
        actual = capture_modules(config["pdf_engine"])
        if actual["distributions"] != manifest["distributions"]:
            raise ValueError("Selected installed distribution versions changed")
        if (any(manifest["modules"].get(name) != location for name, location in actual["modules"].items())
                or any(manifest["files"].get(name) != item for name, item in actual["files"].items())):
            raise ValueError("Selected imported module identities changed")
    finally:
        if previous_cache is None:
            os.environ.pop("MPLCONFIGDIR", None)
        else:
            os.environ["MPLCONFIGDIR"] = previous_cache
    # Proxies, certificates and every unrelated host variable remain inherited.
    # No system configuration or PATH is changed.
    os.environ.update(selected)
    if latex is None:
        os.environ.pop("PF_PDFLATEX_BIN", None)
    return {"environment_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "python": str(executable), "node": str(node), "pandoc": str(pandoc),
            "mode": config["mode"], "pdf_engine": config["pdf_engine"],
            "module_files_verified": len(manifest["files"])}


def consume_environment_argument(arguments: list[str]) -> tuple[str, list[str]]:
    positions = [index for index, value in enumerate(arguments) if value == "--environment-file"]
    if len(positions) != 1 or positions[0] + 1 >= len(arguments):
        raise ValueError("Specify --environment-file exactly once using prepare_host's returned path")
    index = positions[0]
    value = arguments[index + 1]
    if value.startswith("--"):
        raise ValueError("Missing prepared environment file")
    return value, arguments[:index] + arguments[index + 2:]

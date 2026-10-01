#!/usr/bin/env python3
"""Provision a local research image without registry access or copied secrets.

Only interpreter binaries, Python's standard library, their dynamic libraries,
and explicitly requested, pinned dependency allowlists are admitted. Every
copied file is hashed. Docker builds FROM scratch with network disabled. The
resulting immutable image ID, not its convenience tag, is used by Paper Factory.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile


# Deliberate, narrow additions for the selected repository's original Python
# modules. No package names can be supplied by generated plans or programs.
APP_PACKAGES = {
    "pydantic": ("2.13.5", "pydantic"),
    "pydantic_core": ("2.46.5", "pydantic_core"),
    "annotated_types": ("0.8.0", "annotated_types"),
    "typing_extensions": ("4.16.0", "typing_extensions.py"),
    "typing_inspection": ("0.4.4", "typing_inspection"),
    "httpx": ("0.28.1", "httpx"),
    "httpcore": ("1.0.9", "httpcore"),
    "certifi": ("2026.7.22", "certifi"),
    "h11": ("0.16.0", "h11"),
    "anyio": ("4.15.1", "anyio"),
    "idna": ("3.20", "idna"),
}


def copy_file(source: Path, root: Path, destination: str) -> None:
    target = root / destination.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source.resolve(strict=True), target)


def copy_tree(source: Path, root: Path, destination: str) -> None:
    # No host package discovery, virtualenv, configuration, cache, or home data.
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in {"__pycache__", "site-packages", "test", "tests", "idlelib", "tkinter", "turtledemo"}
               for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"Runtime tree contains an unexpected symbolic link: {relative}")
        if (path.is_file() and path.suffix not in {".pyc", ".pyo"}
                and path.name != "direct_url.json" and not path.name.startswith("_tkinter")):
            copy_file(path, root, destination + "/" + relative.as_posix())


def dynamic_dependencies(binary: Path) -> set[Path]:
    result = subprocess.run(["ldd", str(binary)], capture_output=True, text=True, check=False)
    if result.returncode:
        if "not a dynamic executable" in result.stderr or "statically linked" in result.stdout:
            return set()
        raise RuntimeError(f"Cannot inspect dynamic dependencies of {binary.name}")
    if "not found" in result.stdout:
        raise RuntimeError(f"Runtime has unresolved dynamic dependencies: {binary.name}")
    return {Path(name) for name in re.findall(r"(?:=>\s+)?(/[^\s()]+)", result.stdout)}


def copy_application_dependencies(root: Path) -> dict[str, str]:
    versions = {}
    for name, (expected, module) in APP_PACKAGES.items():
        distribution = importlib.metadata.distribution(name)
        if distribution.version != expected:
            raise ValueError(f"Vetted runtime requires {name}=={expected}; installed version differs")
        module_path = Path(distribution.locate_file(module))
        if module_path.is_symlink() or not module_path.exists():
            raise ValueError(f"Vetted runtime module is missing or linked: {name}")
        destination = "/usr/local/lib/python3.12/site-packages/" + module
        if module_path.is_dir():
            copy_tree(module_path, root, destination)
        else:
            copy_file(module_path, root, destination)
        metadata = [path for path in distribution.files or []
                    if path.name == "METADATA" and path.parts[0].endswith(".dist-info")]
        if len(metadata) != 1:
            raise ValueError(f"Vetted runtime has unexpected distribution metadata: {name}")
        metadata_path = Path(distribution.locate_file(metadata[0])).parent
        copy_tree(metadata_path, root, "/usr/local/lib/python3.12/site-packages/" + metadata_path.name)
        versions[name] = distribution.version
    return versions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", type=Path, default=Path(shutil.which("node") or ""))
    parser.add_argument("--mido-site-packages", type=Path)
    parser.add_argument("--with-application-dependencies", action="store_true",
                        help="Admit the pinned Pydantic/httpx dependency allowlist; no arbitrary installs")
    parser.add_argument("--manifest", type=Path, required=True)
    options = parser.parse_args()
    python_binary = Path(sys.executable).resolve()
    # Use the selected interpreter's base stdlib even when invoked in a venv.
    stdlib = Path(sysconfig.get_path("stdlib"))
    node_binary = options.node.resolve(strict=True)
    if not node_binary.is_file():
        raise ValueError("A vetted local Node interpreter is required")
    with tempfile.TemporaryDirectory(prefix="paper-factory-image-") as temporary:
        context = Path(temporary)
        root = context / "rootfs"
        root.mkdir()
        copy_file(python_binary, root, "/usr/local/bin/python3")
        copy_file(node_binary, root, "/usr/local/bin/node")
        copy_tree(stdlib, root, "/usr/local/lib/python3.12")
        if sys.version_info[:2] != (3, 12):
            raise ValueError("This provisioner requires a vetted Python 3.12 interpreter")
        packages: dict[str, str] = {}
        if options.with_application_dependencies:
            packages.update(copy_application_dependencies(root))
        if options.mido_site_packages:
            site = options.mido_site_packages.resolve(strict=True)
            metadata = site / "mido-1.3.3.dist-info" / "METADATA"
            if not metadata.is_file() or "Version: 1.3.3\n" not in metadata.read_text(encoding="utf-8"):
                raise ValueError("Only explicitly selected Mido 1.3.3 is supported")
            for name in ("mido", "mido-1.3.3.dist-info", "packaging"):
                copy_tree(site / name, root, "/usr/local/lib/python3.12/site-packages/" + name)
            package_metadata = sorted(site.glob("packaging-*.dist-info"))
            if len(package_metadata) != 1:
                raise ValueError("Exactly one vetted packaging distribution is required")
            copy_tree(package_metadata[0], root, "/usr/local/lib/python3.12/site-packages/" + package_metadata[0].name)
            packages.update({"mido": "1.3.3", "packaging": package_metadata[0].name.removeprefix("packaging-").removesuffix(".dist-info")})
        binaries = [python_binary, node_binary, *sorted((root / "usr/local/lib/python3.12").rglob("*.so"))]
        for binary in binaries:
            for library in dynamic_dependencies(binary):
                copy_file(library, root, str(library))
        for path in ("work", "output", "tmp", "input", "code", "etc"):
            (root / path).mkdir(exist_ok=True)
        (root / "etc/passwd").write_text("research:x:65532:65532::/work:/nonexistent\n", encoding="utf-8")
        (root / "etc/group").write_text("research:x:65532:\n", encoding="utf-8")
        for path in root.rglob("*"):
            if path.is_dir():
                path.chmod(0o755)
            elif path.is_file():
                path.chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)
        file_hashes = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in sorted(root.rglob("*")) if path.is_file()}
        versions = {"python": sys.version.split()[0], "node": subprocess.check_output([str(node_binary), "--version"], text=True).strip().removeprefix("v"), **packages}
        version_labels = "".join('LABEL org.paper-factory.version-' + key + '="' + value + '"\n'
                                 for key, value in versions.items())
        (context / "Dockerfile").write_text(
            'FROM scratch\nCOPY rootfs /\nUSER 65532:65532\n'
            'LABEL org.paper-factory.research-runtime="1"\n'
            'LABEL org.paper-factory.research-runtimes="python,node"\n'
            'LABEL org.paper-factory.research-dependencies="' + ",".join(packages) + '"\n' + version_labels +
            'ENV PATH=/usr/local/bin:/usr/bin:/bin HOME=/work PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1\n'
            'WORKDIR /work\n', encoding="utf-8")
        (context / ".dockerignore").write_text("*\n!Dockerfile\n!rootfs\n!rootfs/**\n", encoding="utf-8")
        # Buildx writes its cache/config. Keep it in the writable temporary
        # directory and do not load any existing registry login credentials.
        docker_config = context / "docker-config"
        docker_config.mkdir()
        build_environment = {**os.environ, "DOCKER_CONFIG": str(docker_config)}
        built = subprocess.run(["docker", "build", "--network", "none", "--pull=false", "--tag",
                                "paper-factory-research:local", str(context)], check=False, env=build_environment)
        if built.returncode:
            raise RuntimeError("Docker runtime image build failed")
        image = subprocess.check_output(["docker", "image", "inspect", "paper-factory-research:local",
                                         "--format", "{{.Id}}"], text=True, env=build_environment).strip()
        manifest = {"image": image, "python": sys.version.split()[0],
                    "node": subprocess.check_output([str(node_binary), "--version"], text=True).strip(),
                    "packages": packages, "file_count": len(file_hashes), "files_sha256": file_hashes,
                    "provisioning": "allowlisted local runtime; FROM scratch; network disabled"}
        options.manifest.parent.mkdir(parents=True, exist_ok=True)
        options.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("PF_RESEARCH_IMAGE=" + image)


if __name__ == "__main__":
    main()

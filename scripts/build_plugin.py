"""Build the skills-only package from declared, verified release inputs.

This packages bytes only: no dependency installation, research, model call,
account action or publishing. --check verifies inputs without writing outputs.
"""

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tomllib
import uuid
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SKILL = "skills/paper-factory/"
MAX_PACKAGE_BYTES = 100 * 1024 * 1024
HOST_DEPENDENCIES_SHA256 = "1ad1145cca20dc66784b9b96d5d4438153fe1427f9daf63d444bd097bd8ff9ed"
TRANSPORT = {"httpx", "httpcore", "h11", "anyio", "idna", "certifi", "typing-extensions", "socksio"}
CORE = (
    "__init__.py", "author.py", "models.py", "workspace.py", "project.py", "conversion.py",
    "literature.py", "workflow.py", "workflow_models.py", "autonomous/__init__.py",
    "autonomous/models.py", "autonomous/science.py", "autonomous/literature.py",
    "autonomous/runner.py", "autonomous/windows_runner.py", "autonomous/windows_runtime.py",
    "cloud.py", "autonomous/quickjs_runner.py", "autonomous/quickjs_worker.mjs",
    "autonomous/quickjs_windows.py", "autonomous/quickjs_macos.py", "autonomous/quickjs_guardian.py",
)
HELPERS = ("scripts/probe.py", "scripts/prepare_host.py", "scripts/host_context.py",
           "scripts/prepare_runtime.py", "scripts/run_workflow.py")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value: dict) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def safe_name(name: str) -> str:
    relative = PurePosixPath(name)
    if (not name or relative.is_absolute() or "\\" in name or ":" in name
            or any(part in {"", ".", ".."} for part in name.split("/"))):
        raise ValueError("Unsafe package input name: " + name)
    return name


def unlinked(path: Path) -> Path:
    path = path.absolute()
    if any(part.is_symlink() or getattr(part, "is_junction", lambda: False)() for part in (path, *path.parents)):
        raise ValueError("Linked package path: " + str(path))
    return path


def regular(path: Path) -> bytes:
    path = unlinked(path)
    if not path.is_file():
        raise ValueError("Required release input is missing; prepare the reviewed input first: " + str(path))
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_size > MAX_PACKAGE_BYTES:
        raise ValueError("Release input is not a bounded ordinary file: " + str(path))
    return path.read_bytes()


def runtime_assets(skill: Path, runner: bytes) -> dict[str, bytes]:
    metadata_raw = regular(skill / "assets/quickjs-runtime.json")
    metadata = json.loads(metadata_raw)
    archive_raw = regular(skill / "assets/quickjs-runtime.zip")
    tree = ast.parse(runner)
    pin = next((item.value.value for item in tree.body if isinstance(item, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "INVENTORY_SHA256" for target in item.targets)
                and isinstance(item.value, ast.Constant)), None)
    if (metadata["root_directory"] != "quickjs-runtime" or metadata["inventory_sha256"] != pin
            or len(archive_raw) != metadata["archive_size"]
            or digest(archive_raw) != metadata["archive_sha256"]):
        raise ValueError("Generic QuickJS archive, metadata and production inventory pin disagree")
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as archive:
        entries = archive.infolist()
        names = {item.filename for item in entries}
        if (len(entries) != metadata["entries"] or len(names) != len(entries)
                or sum(item.file_size for item in entries) > 2 * 1024 * 1024 or archive.testzip()):
            raise ValueError("Generic QuickJS archive failed bounded inventory/CRC checks")
        for item in entries:
            name = safe_name(item.filename)
            if item.is_dir() or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("Unsafe QuickJS archive entry")
            if name not in {"quickjs-runtime/package.json", "quickjs-runtime/package-lock.json",
                            "quickjs-runtime/inventory.json"} and not name.startswith("quickjs-runtime/node_modules/"):
                raise ValueError("Generic runtime contains a diagnostic, repository source or undeclared input")
        inventory_raw = archive.read("quickjs-runtime/inventory.json")
        if digest(inventory_raw) != pin:
            raise ValueError("Generic runtime inventory differs from the production pin")
        expected = json.loads(inventory_raw)["files"]
        if names != {"quickjs-runtime/inventory.json", *("quickjs-runtime/" + safe_name(name) for name in expected)}:
            raise ValueError("Generic runtime entries differ from the complete inventory")
        for name, record in expected.items():
            raw = archive.read("quickjs-runtime/" + name)
            if len(raw) != record["size"] or digest(raw) != record["sha256"]:
                raise ValueError("Generic runtime resource changed: " + name)
    return {"assets/quickjs-runtime.json": metadata_raw, "assets/quickjs-runtime.zip": archive_raw}


def inputs(root: Path) -> tuple[dict[str, bytes], dict[Path, str], dict]:
    files, originals = {}, {}
    skill = root / "skills/paper-factory"

    def add(name, raw, source=None):
        safe_name(name)
        if name.casefold() in {item.casefold() for item in files}:
            raise ValueError("Duplicate package resource: " + name)
        if name.endswith(".py"):
            ast.parse(raw, filename=name)
        files[name] = raw
        if source is not None:
            originals[source] = digest(raw)

    def copy(source, name):
        add(name, regular(source), source)

    project_raw = regular(root / "pyproject.toml")
    originals[root / "pyproject.toml"] = digest(project_raw)
    project = tomllib.loads(project_raw.decode())
    version = project["project"]["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("The plugin release version must be a three-part numeric version")
    plugin_raw = regular(root / "plugin.json")
    originals[root / "plugin.json"] = digest(plugin_raw)
    plugin = json.loads(plugin_raw)
    if plugin.get("name") != "paper-factory" or plugin.get("skills") != "./skills/":
        raise ValueError("Root manifest must identify the skills-only Paper Factory package")
    plugin["version"] = version  # pyproject.toml is the release version source.
    add("plugin.json", encoded(plugin))
    for name in ("README.md", "LICENSE", "docs/plugin.md"):
        copy(root / name, name)
    copy(root / "LICENSE", SKILL + "LICENSE")
    copy(skill / "SKILL.md", SKILL + "SKILL.md")
    copy(skill / "references/workflow.md", SKILL + "references/workflow.md")
    for name in HELPERS:
        copy(skill / name, SKILL + name)
    for name in CORE:
        copy(root / "src/paper_factory" / name, SKILL + "src/paper_factory/" + name)

    manifest_raw = regular(skill / "host-dependencies.json")
    if digest(manifest_raw) != HOST_DEPENDENCIES_SHA256:
        raise ValueError("Reviewed host dependency manifest changed")
    manifest = json.loads(manifest_raw)
    if manifest.get("schema") != 1 or len(manifest["profiles"]) != 12:
        raise ValueError("Host dependency profiles differ from the reviewed release")
    for name, profile in manifest["profiles"].items():
        expected = set(manifest["pins"]) - ({'pypandoc-binary'} if name.startswith('macos-') else set())
        if {manifest["wheels"][name]["name"] for name in profile["wheels"]} != expected:
            raise ValueError("Host profile omits a declared dependency")
    for filename, dependency in manifest["wheels"].items():
        safe_name(filename)
        if (dependency["filename"] != filename or dependency["version"] != manifest["pins"][dependency["name"]]
                or not dependency["url"].startswith("https://files.pythonhosted.org/")
                or not re.fullmatch("[0-9a-f]{64}", dependency["sha256"]) or dependency["size"] > MAX_PACKAGE_BYTES):
            raise ValueError("Host dependency declaration differs from its reviewed artifact")
    add(SKILL + "host-dependencies.json", manifest_raw, skill / "host-dependencies.json")
    if set(manifest['pandoc']) != {'macos-arm64', 'macos-x86_64'}:
        raise ValueError('The reviewed native macOS Pandoc assets are incomplete')
    notices = {}
    for family, asset in manifest['pandoc'].items():
        machine = family.removeprefix('macos-')
        pandoc_version = asset['version']
        filename = f'pandoc-{pandoc_version}-{machine}-macOS.zip'
        if (not re.fullmatch('[0-9.]+', pandoc_version) or asset['filename'] != filename
                or asset['url'] != f'https://github.com/jgm/pandoc/releases/download/{pandoc_version}/{filename}'
                or not re.fullmatch('[0-9a-f]{64}', asset['sha256']) or not 0 < asset['size'] <= MAX_PACKAGE_BYTES
                or asset['binary']['member'] != f'pandoc-{pandoc_version}-{machine}/bin/pandoc'
                or not re.fullmatch('[0-9a-f]{64}', asset['binary']['sha256'])
                or not 0 < asset['binary']['size'] <= 256 * 1024 * 1024
                or not re.fullmatch('[0-9a-f]{40}', asset['source_commit'])
                or set(asset['licenses']) != {'licenses/pandoc/COPYING.md', 'licenses/pandoc/COPYRIGHT'}):
            raise ValueError('Native Pandoc declaration differs from the reviewed artifact')
        for name, declaration in asset['licenses'].items():
            if declaration['source_url'] != f'https://raw.githubusercontent.com/jgm/pandoc/{asset["source_commit"]}/{PurePosixPath(name).name}':
                raise ValueError('Pandoc upstream notice lacks immutable original provenance')
            raw = regular(skill / name)
            if len(raw) != declaration['size'] or digest(raw) != declaration['sha256']:
                raise ValueError('Pandoc original upstream notice differs from its reviewed bytes')
            if name in notices and notices[name] != raw:
                raise ValueError('Pandoc native profiles disagree on their original notice bytes')
            notices[name] = raw
    for name, raw in notices.items():
        add(SKILL + name, raw, skill / name)
    transport = {name: dependency for name, dependency in manifest["wheels"].items() if dependency["name"] in TRANSPORT}
    if {dependency["name"] for dependency in transport.values()} != TRANSPORT or len(transport) != len(TRANSPORT):
        raise ValueError("Bootstrap transport must be one complete portable pure-wheel closure")
    for filename, dependency in transport.items():
        if not filename.endswith("-py3-none-any.whl"):
            raise ValueError("Bootstrap transport includes a native or unreviewed wheel")
        path = skill / "wheelhouse" / filename
        raw = regular(path)
        if len(raw) != dependency["size"] or digest(raw) != dependency["sha256"]:
            raise ValueError("Bootstrap transport wheel differs from its official release")
        add(SKILL + "wheelhouse/" + filename, raw, path)
    for name, raw in runtime_assets(skill, files[SKILL + "src/paper_factory/autonomous/quickjs_runner.py"]).items():
        add(SKILL + name, raw, skill / name)
    inventory = {"version": version, "resource_root": "skills/paper-factory", "whitelist_only": True,
                 "core_files": ["src/paper_factory/" + name for name in CORE],
                 "files": {name[len(SKILL):]: {"size": len(raw), "sha256": digest(raw)}
                           for name, raw in sorted(files.items()) if name.startswith(SKILL)},
                 "mcp_bundled": False, "model_provider_bundled": False, "research_inputs_bundled": False,
                 "validation_scope": "Packaging is not evidence of Cloud research or public installation."}
    add(SKILL + "inventory.json", encoded(inventory))
    if sum(map(len, files.values())) > MAX_PACKAGE_BYTES:
        raise ValueError("Declared package exceeds the 100 MiB upload bound")
    return files, originals, {"version": version, "core_files": len(CORE),
                             "dependency_profiles": len(manifest["profiles"]),
                             "pinned_dependency_wheels": len(manifest["wheels"]), "dependency_wheels": len(transport)}


def build(root: Path = ROOT, *, check_only: bool = False) -> dict:
    root = unlinked(root).resolve()
    files, originals, summary = inputs(root)
    for source, expected in originals.items():
        if digest(regular(source)) != expected:
            raise ValueError("Release input changed while building: " + str(source))
    report = {"ok": True, "check_only": check_only, **summary, "declared_files": len(files),
              "uncompressed_bytes": sum(map(len, files.values())), "research_inputs_bundled": False,
              "mcp_bundled": False, "experiments_executed": False, "public_install_tested": False,
              "source_core": {name: {"size": len(files[SKILL + "src/paper_factory/" + name]),
                                      "sha256": digest(files[SKILL + "src/paper_factory/" + name])} for name in CORE}}
    if check_only:
        return report
    distribution = unlinked(root / "dist")
    distribution.mkdir(exist_ok=True)
    token = uuid.uuid4().hex
    staging = distribution / (".paper-factory-build-" + token)
    temporary_archive = distribution / (".paper-factory-build-" + token + ".zip")
    staging.mkdir()
    for name, raw in files.items():
        destination = staging.joinpath(*PurePosixPath(name).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as output:
            output.write(raw)
    with zipfile.ZipFile(temporary_archive, "x", zipfile.ZIP_DEFLATED) as bundle:
        for name, raw in sorted(files.items()):
            bundle.writestr(name, raw)
    if temporary_archive.stat().st_size > MAX_PACKAGE_BYTES:
        raise ValueError("Built ZIP exceeds the upload bound; retained staging is not a release")
    with zipfile.ZipFile(temporary_archive) as bundle:
        if bundle.testzip() or bundle.namelist() != sorted(files):
            raise ValueError("Built ZIP inventory/CRC differs")
        for name, raw in files.items():
            if bundle.read(name) != raw or (staging / name).read_bytes() != raw:
                raise ValueError("Built package bytes changed: " + name)
    for source, expected in originals.items():
        if digest(regular(source)) != expected:
            raise ValueError("Release input changed before finalization: " + str(source))
    target = distribution / "paper-factory"
    archive = distribution / ("paper-factory-" + summary["version"] + ".zip")
    report_path = distribution / "build-report.json"
    # Preserve earlier generated artifacts; never recursively delete a checkout.
    prior = unlinked(distribution / "previous" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + token)).resolve()
    if not prior.is_relative_to(distribution.resolve()):
        raise ValueError("Generated output backup would leave the verified dist directory")
    for path in (target, archive, report_path):
        checked = unlinked(path).resolve()
        if not checked.is_relative_to(distribution.resolve()) or checked == distribution.resolve():
            raise ValueError("Generated output move would leave the verified dist directory")
        if path.exists():
            prior.mkdir(parents=True, exist_ok=True)
            path.rename(prior / path.name)
    staging.rename(target)
    temporary_archive.rename(archive)
    report.update(plugin=str(target), archive=str(archive), archive_bytes=archive.stat().st_size,
                  archive_sha256=digest(regular(archive)), inventory_sha256=digest(files[SKILL + "inventory.json"]))
    if prior.exists():
        report["prior_artifacts"] = str(prior)
    report_path.write_bytes(encoded(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(build(check_only=args.check), indent=2))
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        print(json.dumps({"ok": False, "error": type(error).__name__, "message": str(error)}))
        raise SystemExit(1)

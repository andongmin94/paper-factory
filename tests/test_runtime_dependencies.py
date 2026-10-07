"""Check the offline runtime catalog against its active platform dependencies."""

import ast
import hashlib
import json
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version
import pytest


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "desktop/runtime-inputs/host-dependencies.json"


def test_runtime_catalog_matches_maintainer_pins_and_verified_font_source():
    catalog = json.loads(CATALOG.read_bytes())
    module = ast.parse((ROOT / "scripts/generate_host_dependencies.py").read_text(encoding="utf-8"))
    pins = next(ast.literal_eval(node.value) for node in module.body
                if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "PINS"
                                                       for target in node.targets))
    assert catalog["pins"] == pins
    manifest = json.loads((ROOT / "desktop/runtime-manifest.json").read_bytes())
    assert manifest["hostDependencies"]["sha256"] == hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    assert manifest["fontSource"] == "paper_factory/fonts"
    font_root = ROOT / "src" / manifest["fontSource"]
    provenance = json.loads((font_root / "provenance.json").read_bytes())
    for asset in provenance["files"]:
        raw = (font_root / asset["destination"]).read_bytes()
        assert len(raw) == asset["size"] and hashlib.sha256(raw).hexdigest() == asset["sha256"]


@pytest.mark.parametrize("profile_name", ["windows-x86_64-cp314", "macos-x86_64-cp314", "macos-arm64-cp314"])
def test_runtime_profile_contains_its_active_wheel_dependency_closure(profile_name):
    catalog = json.loads(CATALOG.read_bytes())
    profile = catalog["profiles"][profile_name]
    selected = {catalog["wheels"][filename]["name"]: catalog["wheels"][filename]
                for filename in profile["wheels"]}
    environment = default_environment()
    windows = profile_name.startswith("windows-")
    environment.update(extra="", python_version="3.14", python_full_version="3.14.0",
                       sys_platform="win32" if windows else "darwin",
                       platform_system="Windows" if windows else "Darwin",
                       platform_machine=profile_name.rsplit("-cp", 1)[0].split("-", 1)[1],
                       os_name="nt" if windows else "posix")
    for wheel in selected.values():
        assert catalog["pins"][wheel["name"]] == wheel["version"]
        for declaration in wheel["requires_dist"]:
            requirement = Requirement(declaration)
            if requirement.marker and not requirement.marker.evaluate(environment):
                continue
            dependency = canonicalize_name(requirement.name)
            assert dependency in selected, (wheel["name"], declaration)
            assert Version(selected[dependency]["version"]) in requirement.specifier

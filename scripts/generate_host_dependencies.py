"""Resolve reviewed release pins to official platform wheels, without installing.

Run this maintainer command when intentionally updating standalone runtime pins.
The desktop builder validates this catalog; installed apps never run this command.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.tags import compatible_tags, cpython_tags, mac_platforms
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "pydantic": "2.13.5", "pydantic-core": "2.46.5", "annotated-types": "0.8.0",
    "typing-inspection": "0.4.4", "typing-extensions": "4.16.0",
    "numpy": "2.5.3", "matplotlib": "3.11.2", "contourpy": "1.4.0",
    "cycler": "0.12.1", "fonttools": "4.66.1", "kiwisolver": "1.5.1",
    "packaging": "26.3", "pillow": "12.3.0", "pyparsing": "3.3.3",
    "python-dateutil": "2.9.0.post0", "six": "1.17.0", "pypdf": "6.19.0",
    "python-docx": "1.2.0", "lxml": "6.1.3", "typst": "0.15.0",
    "pypandoc-binary": "1.17", "httpx": "0.28.1", "httpcore": "1.0.9",
    "anyio": "4.15.1", "certifi": "2026.7.22", "h11": "0.16.0",
    "idna": "3.20", "socksio": "1.0.0", "beautifulsoup4": "4.15.0",
    "soupsieve": "2.10",
}
NODE_VERSION = "24.21.0"
PANDOC_VERSION = "3.9"
PANDOC_COMMIT = "19c1f6552b12c70741674f509f8064ae506f29db"
PANDOC_BINARIES = {
    "arm64": (189626864, "140353e19f2518a76aa144ce90a7afcb6f485ba94d0dbe069e77c805277908c3"),
    "x86_64": (119565632, "d7b1e75cd20ee6a788a1399492be07d4559949e18e55f34cfc5c91807fdfa90d"),
}
PANDOC_NOTICES = {
    "COPYING.md": (17787, "9d56cac92294e206af026a5502bee0fed77200b08b51ec28aa63c9efda4dcfdd"),
    "COPYRIGHT": (9598, "842e33ef01625e93f85bebb8bac83aa570186b7aa77a09971257cc29f8f60740"),
}
PLATFORMS = {
    "windows-x86_64": ["win_amd64"],
    "macos-x86_64": list(mac_platforms((14, 0), "x86_64")),
    "macos-arm64": list(mac_platforms((14, 0), "arm64")),
}


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read(8 * 1024 * 1024 + 1)


def pandoc_declarations():
    release_url = f"https://api.github.com/repos/jgm/pandoc/releases/tags/{PANDOC_VERSION}"
    raw = fetch(release_url)
    release = json.loads(raw)
    if release['tag_name'] != PANDOC_VERSION:
        raise ValueError("Official Pandoc release differs from the reviewed version")
    licenses = {}
    for name, (size, expected) in PANDOC_NOTICES.items():
        path = "licenses/pandoc/" + name
        original = (ROOT / "desktop/runtime-inputs" / path).read_bytes()
        if len(original) != size or hashlib.sha256(original).hexdigest() != expected:
            raise ValueError("Reviewed original Pandoc upstream notice changed")
        licenses[path] = {"size": size, "sha256": expected,
                          "source_url": f"https://raw.githubusercontent.com/jgm/pandoc/{PANDOC_COMMIT}/{name}"}
    result = {}
    for machine, (size, expected) in PANDOC_BINARIES.items():
        filename = f"pandoc-{PANDOC_VERSION}-{machine}-macOS.zip"
        asset = next(item for item in release['assets'] if item['name'] == filename)
        url = f"https://github.com/jgm/pandoc/releases/download/{PANDOC_VERSION}/{filename}"
        if asset['browser_download_url'] != url or not asset['digest'].startswith('sha256:'):
            raise ValueError("Official Pandoc asset lacks the reviewed origin or digest")
        result['macos-' + machine] = {"version": PANDOC_VERSION, "filename": filename, "url": url,
            "size": asset['size'], "sha256": asset['digest'][7:], "release_url": release_url,
            "release_sha256": hashlib.sha256(raw).hexdigest(), "source_commit": PANDOC_COMMIT,
            "binary": {"member": f"pandoc-{PANDOC_VERSION}-{machine}/bin/pandoc", "size": size, "sha256": expected},
            "licenses": licenses}
    return result


def generate():
    releases = {}
    for name, version in PINS.items():
        url = f"https://pypi.org/pypi/{name}/{version}/json"
        raw = fetch(url)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("Unexpected PyPI metadata size")
        releases[name] = (json.loads(raw), url, hashlib.sha256(raw).hexdigest())
    wheels, profiles = {}, {}
    for system, platforms in PLATFORMS.items():
        for minor in (14,):
            version = (3, minor)
            tags = list(cpython_tags(version, abis=[f"cp3{minor}"], platforms=platforms))
            tags += list(compatible_tags(version, interpreter=f"cp3{minor}", platforms=platforms))
            rank = {tag: i for i, tag in reversed(list(enumerate(tags)))}
            selected = []
            environment = default_environment()
            environment.update(python_version=f"3.{minor}", python_full_version=f"3.{minor}.0", extra="",
                               sys_platform={"windows": "win32", "linux": "linux", "macos": "darwin"}[system.split('-')[0]],
                               platform_system={"windows": "Windows", "linux": "Linux", "macos": "Darwin"}[system.split('-')[0]],
                               platform_machine=system.split('-')[1], implementation_name="cpython",
                               platform_python_implementation="CPython", os_name="nt" if system.startswith("windows") else "posix")
            for name, (release, url, metadata_hash) in releases.items():
                # The upstream macOS wheel omits notices, and its arm64 tag
                # contains an Intel binary. Use reviewed native official assets.
                if system.startswith('macos-') and name == 'pypandoc-binary':
                    continue
                candidates = []
                for artifact in release["urls"]:
                    if artifact["packagetype"] != "bdist_wheel" or artifact.get("yanked"):
                        continue
                    _, _, _, artifact_tags = parse_wheel_filename(artifact["filename"])
                    compatible = [rank[tag] for tag in artifact_tags if tag in rank]
                    if compatible:
                        candidates.append((min(compatible), artifact["filename"], artifact))
                if not candidates:
                    raise ValueError(f"No official binary wheel for {name} on {system} CPython3.{minor}")
                artifact = min(candidates)[2]
                info = release["info"]
                for declaration in info.get("requires_dist") or []:
                    requirement = Requirement(declaration)
                    if requirement.marker and not requirement.marker.evaluate(environment):
                        continue
                    dependency = canonicalize_name(requirement.name)
                    if dependency not in PINS or Version(PINS[dependency]) not in requirement.specifier:
                        raise ValueError(f"Unpinned dependency for {name}/{system}/3.{minor}: {declaration}")
                filename = artifact["filename"]
                wheels[filename] = {"name": name, "version": PINS[name], "filename": filename,
                                    "url": artifact["url"], "size": artifact["size"],
                                    "sha256": artifact["digests"]["sha256"], "release_url": url,
                                    "release_sha256": metadata_hash,
                                    "license": info.get("license_expression") or info.get("license"),
                                    "requires_python": artifact.get("requires_python"),
                                    "requires_dist": info.get("requires_dist") or []}
                selected.append(filename)
            profiles[f"{system}-cp3{minor}"] = {"wheels": sorted(selected), "actual_host_tested": False}
    node_base = f"https://nodejs.org/dist/v{NODE_VERSION}/"
    checksum_raw = fetch(node_base + "SHASUMS256.txt")
    checksums = dict((line.split()[1], line.split()[0]) for line in checksum_raw.decode("ascii").splitlines())
    node = {}
    for system, suffix in {"windows-x86_64": "win-x64.zip",
                           "macos-x86_64": "darwin-x64.tar.xz", "macos-arm64": "darwin-arm64.tar.xz"}.items():
        filename = f"node-v{NODE_VERSION}-{suffix}"
        node[system] = {"version": NODE_VERSION, "filename": filename, "url": node_base + filename,
                        "sha256": checksums[filename], "checksum_url": node_base + "SHASUMS256.txt",
                        "checksum_file_sha256": hashlib.sha256(checksum_raw).hexdigest(),
                        "max_bytes": 100 * 1024 * 1024}
    return {"schema": 1, "scope": "Maintainer-only pinned standalone runtime catalog for Windows x64 and macOS Intel/ARM; installed apps never download dependencies.",
            "pins": PINS, "profiles": profiles, "wheels": dict(sorted(wheels.items())), "node": node,
            "pandoc": pandoc_declarations(),
            "network_policy": "Only manifest-pinned official artifact URLs; inherited proxy/certificate settings."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "desktop/runtime-inputs/host-dependencies.json")
    args = parser.parse_args()
    result = generate()
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "profiles": len(result["profiles"]),
                      "wheels": len(result["wheels"]), "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))

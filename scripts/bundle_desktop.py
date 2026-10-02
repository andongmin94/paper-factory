"""Build a self-contained Windows x64 runtime; never copy user environments."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import zipfile

import httpx


ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
VERSIONS = json.loads((DESKTOP / "runtime-versions.json").read_text(encoding="utf-8"))


def copy_tree(source: Path, target: Path, *, standard_library: bool = False):
    excluded = {"__pycache__", ".git"}
    if standard_library:
        excluded |= {"site-packages", "test", "tests", "idlelib", "tkinter", "turtledemo", "ensurepip"}
    def ignore(directory, names):
        return [name for name in names if name in excluded or name.endswith((".pyc", ".pyo", ".pdb", ".lib"))]
    shutil.copytree(source, target, ignore=ignore)


def checked_output(path: Path) -> Path:
    """Deletion/replacement is restricted to the one build resource directory."""
    expected = (DESKTOP / "resources").absolute()
    if path.absolute() != expected or path.is_symlink() or path.resolve().parent != DESKTOP.resolve():
        raise ValueError("Refusing an unrelated runtime output path")
    # Reject junctions, including ancestors, before removing anything.
    from paper_factory.workspace import ensure_unlinked
    ensure_unlinked(path)
    return path


def bundle(destination: Path):
    if os.name != "nt" or sys.maxsize <= 2**32:
        raise SystemExit("Build the desktop runtime with native Windows x64 Python.")
    lock = DESKTOP / "backend-requirements.txt"
    if not lock.is_file():
        raise ValueError("The checked-in desktop/backend-requirements.txt is required for runtime builds.")
    runtime = destination / "runtime"
    python = runtime / "python"
    python.mkdir(parents=True)
    base = Path(sys.base_prefix)
    major_minor = f"{sys.version_info.major}{sys.version_info.minor}"
    for name in ("python.exe", "python3.dll", f"python{major_minor}.dll", "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt"):
        source = base / name
        if source.is_file():
            shutil.copyfile(source, python / name)
    if not (python / "python.exe").is_file():
        raise ValueError("A complete native Python installation is required by the build machine.")
    copy_tree(Path(sysconfig.get_path("stdlib")), python / "Lib", standard_library=True)
    copy_tree(base / "DLLs", python / "DLLs", standard_library=True)
    (python / f"python{major_minor}._pth").write_text("Lib\nDLLs\n.\nLib/site-packages\n../../backend\n", encoding="utf-8")
    site = python / "Lib" / "site-packages"
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-compile", "--target", str(site), "-r", str(lock)], check=True, cwd=ROOT)
    shutil.copyfile(lock, runtime / "backend-requirements.txt")
    copy_tree(ROOT / "src" / "paper_factory", destination / "backend" / "paper_factory")
    shutil.copyfile(ROOT / "LICENSE", destination / "LICENSE")

    node = shutil.which("node.exe")
    npm = shutil.which("npm.cmd")
    if not node or not npm:
        raise ValueError("Node.js and npm are required only on the build machine.")
    (runtime / "node").mkdir()
    shutil.copyfile(node, runtime / "node" / "node.exe")
    node_version = subprocess.check_output([node, "--version"], text=True).strip().removeprefix("v")
    # Include the license from the exact official release of the copied binary.
    with httpx.Client(follow_redirects=True, timeout=60) as client:
        license_reply = client.get(f"https://raw.githubusercontent.com/nodejs/node/v{node_version}/LICENSE")
        license_reply.raise_for_status()
        (runtime / "node" / "LICENSE").write_bytes(license_reply.content)
        git_reply = client.get(VERSIONS["git"]["url"])
        git_reply.raise_for_status()
    if hashlib.sha256(git_reply.content).hexdigest() != VERSIONS["git"]["sha256"]:
        raise ValueError("The official MinGit archive did not match its release checksum.")
    from io import BytesIO
    with zipfile.ZipFile(BytesIO(git_reply.content)) as archive:
        for item in archive.infolist():
            target = runtime / "git" / item.filename
            if not target.resolve().is_relative_to((runtime / "git").resolve()):
                raise ValueError("Unsafe archive member")
        archive.extractall(runtime / "git")
    subprocess.run([npm, "install", "--prefix", str(runtime / "codex"), "--no-audit", "--no-fund", f"@openai/codex@{VERSIONS['codex']}"], check=True)
    licenses = destination / "licenses"
    licenses.mkdir()
    (licenses / "RUNTIME-NOTICES.txt").write_text(
        "Python: runtime/python/LICENSE.txt\nNode.js: runtime/node/LICENSE\n"
        "Python distributions: licenses and notices in runtime/python/Lib/site-packages/*dist-info/\n"
        "Codex: runtime/codex/node_modules/@openai/codex/LICENSE\n"
        "Git for Windows: original license notices are retained in runtime/git/\n"
        f"Git corresponding release source: https://github.com/git-for-windows/git/archive/refs/tags/v{VERSIONS['git']['version']}.tar.gz\n",
        encoding="utf-8")
    files = {}
    for path in sorted(destination.rglob("*")):
        if path.is_file():
            with path.open("rb") as stream:
                files[path.relative_to(destination).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = {"python": sys.version.split()[0], "node": node_version, "codex": VERSIONS["codex"], "git": VERSIONS["git"]["version"], "files": files}
    (destination / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main():
    DESKTOP.mkdir(exist_ok=True)
    output = checked_output(DESKTOP / "resources")
    with tempfile.TemporaryDirectory(prefix=".runtime-build-", dir=DESKTOP) as temporary:
        staged = Path(temporary) / "resources"
        staged.mkdir()
        bundle(staged)
        if output.exists():
            checked_output(output)
            shutil.rmtree(output)
        shutil.move(str(staged), str(output))
    print(f"Desktop runtime ready: {output}")


if __name__ == "__main__":
    main()

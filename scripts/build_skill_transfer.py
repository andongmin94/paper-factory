"""Encode verified original UTF-8 files as deterministic, hash-pinned resources.

Generated transport resources are not included in their own payload. This builds
bytes only; it never runs package code, installs dependencies or publishes files.
"""

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FORMAT = "paper-factory-text-transfer-v1"
CHUNK_BYTES = 6144  # 8192 base64 characters: bounded text resource reads.
MAX_TEXT = 2 * 1024 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def relative(name):
    if (not name or name.startswith("/") or "\\" in name or ":" in name
            or any(ord(char) < 32 for char in name)
            or any(part in {"", ".", ".."} for part in name.split("/"))):
        raise ValueError("Unsafe transfer file name")
    for part in name.split("/"):
        if (part.endswith((".", " ")) or any(char in '<>"|?*' for char in part)
                or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", part.split(".")[0], re.IGNORECASE)):
            raise ValueError("Unsafe transfer file name")
    return name


def build_transfer(files, *, version, inventory_path=None):
    if not isinstance(version, str) or not files or len(files) > 512:
        raise ValueError("Invalid transfer snapshot")
    if len({name.casefold() for name in files}) != len(files):
        raise ValueError("Duplicate transfer file name")
    if sum(map(len, files.values())) > MAX_TEXT:
        raise ValueError("Transfer text exceeds its bound")
    for name, raw in files.items():
        relative(name)
        if not isinstance(raw, bytes):
            raise ValueError("Transfer requires original bytes")
        raw.decode("utf-8")
    if inventory_path is not None and inventory_path not in files:
        raise ValueError("Executable inventory must be an original declared file")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o444) << 16
            archive.writestr(info, raw, compresslevel=9)
    archive_raw = buffer.getvalue()
    resources, chunks = {}, []
    for index, offset in enumerate(range(0, len(archive_raw), CHUNK_BYTES)):
        part = archive_raw[offset:offset + CHUNK_BYTES]
        text = base64.b64encode(part) + b"\n"
        name = f"chunks/{index:06d}.txt"
        resources[name] = text
        chunks.append({"index": index, "path": name,
                       "text": {"size": len(text), "sha256": digest(text)},
                       "decoded": {"size": len(part), "sha256": digest(part)}})
    manifest = {"format": FORMAT, "version": version,
                "archive": {"size": len(archive_raw), "sha256": digest(archive_raw)},
                "files": {name: {"size": len(raw), "sha256": digest(raw)} for name, raw in sorted(files.items())},
                "chunks": chunks, "inventory_path": inventory_path,
                "scope": "Original UTF-8 text bytes only; binary assets and executable readiness are separate."}
    resources["manifest.json"] = (json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode()
    return resources


def preview():
    # A known original 1 KiB text fixture; this is not controller or research code.
    raw = (b"Paper Factory original-byte transport preview.\n" * 30)[:1024]
    return build_transfer({"preview.txt": raw}, version="transport-preview")


def preview_plugin():
    resources = preview()
    manifest = json.loads(resources["manifest.json"])
    manifest_sha = digest(resources["manifest.json"])
    chunk = manifest["chunks"][0]
    original = manifest["files"]["preview.txt"]
    skill = f"""---
name: paper-factory-byte-probe
description: Verify installed original text-resource bytes reaching the ordinary Chat execution container using one 1 KiB fixture. Use for this transport diagnostic, without dependency setup or research.
---

# Original byte transfer diagnostic

This private diagnostic contains one original 1024-byte UTF-8 fixture. It contains
no controller, research source, experiment, dependency wheel or QuickJS runtime.
It tests one small opaque transfer, not full package delivery or platform support.

Read [the transfer manifest](assets/transfer/manifest.json) and its listed
[chunk](assets/transfer/chunks/000000.txt) through the actual installed skill
resource tool. Preserve the original UTF-8 response contents. Do not use a local
checkout, prior chat attachment, invented download URL or model-written replacement.

The expected manifest UTF-8 SHA256 is `{manifest_sha}`.
The chunk must be {chunk['text']['size']} UTF-8 bytes including its final LF, with
SHA256 `{chunk['text']['sha256']}`. Base64-decode the original chunk (only its
single final LF is removed), requiring decoded size {manifest['archive']['size']}
and SHA256 `{manifest['archive']['sha256']}`.

Using the ordinary Chat's actual script tool and an approved new writable scratch,
perform only trusted standard-library data decoding and checks: `hashlib`, strict
`base64.b64decode(..., validate=True)`, and `zipfile.ZipFile(io.BytesIO(...))`.
This decoding code is transport plumbing; do not execute any decoded content.
Require exactly one regular archive entry named `preview.txt`, no directories or
links, and read its original bytes. Require exactly {original['size']} bytes and
SHA256 `{original['sha256']}` before writing a new scratch file with exclusive
creation. Re-read the saved file and require the same size/SHA again.

If a programmable original-response-to-script bridge is available, use it. If only
the host assistant can relay this small base64 string, copy it as opaque data and
report that mechanism honestly. A successful manual relay of this tiny fixture
does not prove that a full controller or megabyte runtime can be transferred with
acceptable latency/context cost. Missing/truncated/rewritten data is a failed
transfer, never a reason to regenerate source or skip an integrity check.

Preserve actual tool calls, source resource URI, transfer mechanism, stdout/stderr,
exit code, and the saved original bytes with size/SHA. Report whether each phase
was actually observed. No network, installation, bootstrap, runtime self-check,
research, account change or publication is part of this diagnostic. Leave the
existing Paper Factory package and scientific evidence unchanged.
"""
    plugin = {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
              "name": "paper-factory-transfer-probe", "version": "0.0.1", "skills": "./skills/",
              "description": "Private one-KiB original resource transfer diagnostic; no research or dependencies."}
    files = {"plugin.json": (json.dumps(plugin, indent=2) + "\n").encode(),
             "skills/paper-factory-byte-probe/SKILL.md": skill.encode()}
    files.update({"skills/paper-factory-byte-probe/assets/transfer/" + name: raw
                  for name, raw in resources.items()})
    return files


def write_preview_plugin(output):
    files = preview_plugin()
    output = Path(output).absolute()
    if output.exists() or any(part.is_symlink() or getattr(part, "is_junction", lambda: False)()
                              for part in (output, *output.parents)):
        raise ValueError("Preview ZIP must be a new unlinked owned file")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o444) << 16
            archive.writestr(info, raw, compresslevel=9)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() or set(archive.namelist()) != set(files):
            raise ValueError("Preview ZIP failed complete inventory/CRC checks")
        for name, raw in files.items():
            if archive.read(name) != raw:
                raise ValueError("Preview ZIP bytes changed")
    return {"ok": True, "archive": str(output), "bytes": output.stat().st_size,
            "sha256": digest(output.read_bytes()), "entries": len(files), "fixture_bytes": 1024,
            "code_executed": False, "network_accessed": False, "published": False}


def write_resources(resources, output):
    output = Path(output).absolute()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Transfer output must be a new or empty owned directory")
    if any(part.is_symlink() or getattr(part, "is_junction", lambda: False)() for part in (output, *output.parents)):
        raise ValueError("Linked transfer output")
    output.mkdir(parents=True, exist_ok=True)
    for name, raw in resources.items():
        target = output / relative(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
    manifest = json.loads(resources["manifest.json"])
    return {"ok": True, "output": str(output), "manifest_sha256": digest(resources["manifest.json"]),
            "original_files": len(manifest["files"]), "chunks": len(manifest["chunks"]),
            "archive_bytes": manifest["archive"]["size"], "code_executed": False,
            "network_accessed": False, "published": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true")
    mode.add_argument("--preview-plugin", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(write_preview_plugin(args.output) if args.preview_plugin
                     else write_resources(preview(), args.output)))

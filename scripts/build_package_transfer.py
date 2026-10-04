"""Build a private, original-byte archive transfer diagnostic without publishing."""

import argparse
import base64
import io
import json
from pathlib import Path
import stat
import zipfile

import verify_archive_transfer as verifier


CHUNK_BYTES = 12288  # 16,384 Base64 bytes plus a single final LF.
PLUGIN_NAME = "paper-factory-package-transfer-probe"
SKILL_NAME = "paper-factory-package-byte-probe"


def resources(archive_raw, *, archive_sha256, version, inventory_path):
    verifier.hash_value(archive_sha256)
    if verifier.digest(archive_raw) != archive_sha256:
        raise ValueError("Frozen original package SHA256 mismatch")
    contents = verifier.archive_files(archive_raw)
    verifier.inventory_check(contents, inventory_path)
    output, chunks = {}, []
    for index, offset in enumerate(range(0, len(archive_raw), CHUNK_BYTES)):
        raw = base64.b64encode(archive_raw[offset:offset + CHUNK_BYTES]) + b"\n"
        output[f"chunks/{index:06d}.txt"] = raw
        chunks.append(verifier.digest(raw))
    manifest = {"format": verifier.FORMAT, "version": version,
                "archive": {"size": len(archive_raw), "sha256": archive_sha256},
                "chunk_bytes": CHUNK_BYTES, "chunks": chunks,
                "files": {name: {"size": len(raw), "sha256": verifier.digest(raw)}
                          for name, raw in sorted(contents.items())},
                "inventory_path": inventory_path}
    output["manifest.json"] = (json.dumps(manifest, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode()
    if len(output["manifest.json"]) > verifier.MAX_MANIFEST or any(len(raw) > verifier.MAX_CHUNK_TEXT for raw in output.values()):
        raise ValueError("Transfer metadata or chunks exceed resource-read bounds")
    return output


def plugin_files(archive_raw, *, archive_sha256, version, inventory_path):
    original = resources(archive_raw, archive_sha256=archive_sha256, version=version, inventory_path=inventory_path)
    manifest = json.loads(original["manifest.json"])
    helper = Path(verifier.__file__).read_bytes()
    if len(helper) > verifier.MAX_CHUNK_TEXT:
        raise ValueError("Trusted verifier helper exceeds the text-resource read bound")
    manifest_pin, helper_pin = verifier.digest(original["manifest.json"]), verifier.digest(helper)
    count = len(manifest["chunks"])
    encoded_bytes = sum(len(raw) for name, raw in original.items() if name.startswith("chunks/"))
    skill = f"""---
name: {SKILL_NAME}
description: Privately test original whole-package byte delivery from installed text resources into ordinary Chat's script container. Use only for the requested chunk pilot or complete archive transfer, without setup or research execution.
---

# Private whole-package transport diagnostic

This prototype encodes the exact frozen Paper Factory {version} package ZIP,
including original controller, QuickJS archive and all wheel bytes. It is a
transport test only. It does not install dependencies, import decoded controller
code, run a runtime self-check, execute research or prove platform support.
It contains {count} opaque Base64 chunks ({encoded_bytes} ASCII bytes in total),
which may be impractical to relay through a model. A tiny earlier transfer is not
evidence that this whole archive has reached the execution container.

Use the actual installed skill resource tool to read
[manifest.json](assets/transfer/manifest.json). Preserve its exact UTF-8 content:
{len(original['manifest.json'])} bytes, SHA256 `{manifest_pin}`.
The frozen archive itself is {manifest['archive']['size']} bytes,
SHA256 `{archive_sha256}`. The compact manifest has {count} ordered chunk SHA256
strings; chunk i has the fixed resource path `assets/transfer/chunks/NNNNNN.txt`
using a zero-padded six-digit index. Every chunk is at most 16385 ASCII bytes,
including its single final LF. Its decoded width is {CHUNK_BYTES} bytes except
the last chunk. Do not add a BOM, wrap Base64 lines, normalize LF, pretty-print
the manifest, rewrite source, or substitute download URLs or earlier attachments.

Read the original trusted transport helper
[verify_archive_transfer.py](scripts/verify_archive_transfer.py), preserving
exact UTF-8 bytes. Before executing that helper, use the native host's trusted
stdlib hashlib to verify its {len(helper)} bytes and SHA256 `{helper_pin}`.
It contains transport validation only; decoded package code must never execute
during this diagnostic. Missing original helper bytes is a failed transfer, not
authorization to recreate its code from an explanation or omit its checks.

## First three chunks only

Start in a new approved writable scratch with separate `responses`, `attempts`
and still-empty `package` directories. Save actual manifest/helper responses with
exclusive creation and validate the pins above. Read these three resources
individually, preserving the exact original contents:

- [000000](assets/transfer/chunks/000000.txt)
- [000001](assets/transfer/chunks/000001.txt)
- [000002](assets/transfer/chunks/000002.txt)

Store them under `responses/chunks/` with their listed names. Do not request all
chunks in one response. Run only the verified helper using the actual host Python:

```text
python verified-helper.py --manifest responses/manifest.json --manifest-sha256 {manifest_pin} --data package --pilot-chunks 3
```

Preserve exact resource URIs, tool calls, transfer mechanism, helper stdout/stderr
and exit code in a new numbered attempt. Require exit 0, `ok=true`,
`stage=chunk-pilot`, `chunks_verified=3`, `chunks_total={count}` and
`package_verified=false`; `package` must remain empty. Each original text chunk
is size/SHA checked before strict canonical Base64 decoding. Record the actual
decoded size/SHA independently. The text pin already uniquely binds decoded bytes;
the complete archive pin is additionally required only after all chunks arrive.

If a programmable original-resource-to-script bridge is absent, disclose the
opaque model relay and its measured cost. Do not say resources automatically
appeared in the execution filesystem. Preserve the first failure, including
truncated/changed responses and stdout/stderr. Do not overwrite evidence, change
hash expectations or silently retry. A later authorized retry gets a new numbered
attempt; reuse earlier good chunks only after rechecking their original pins.

## Whole archive, only when requested

Continue one bounded resource response at a time through index {count - 1:06d}.
Re-run the same verified helper without `--pilot-chunks`, targeting a new approved
empty `package` directory. It checks every original chunk, concatenated archive
size/SHA, complete regular-file ZIP inventory, safe paths, per-file hashes and
every original canonical inventory resource, including the QuickJS ZIP and wheels.
Only then may it write exact original files with exclusive creation and re-read
their hashes. Require `package_verified=true`, all {len(manifest['files'])} original
files verified, and the returned original inventory count. This reports byte
delivery only: `dependencies_prepared=false`, `execution_ready=false`,
`code_executed=false`, `network_accessed=false`. Do not bootstrap or execute the
delivered package as an automatic follow-up. A first-three pilot remains incomplete
even if its three chunks pass. Leave frozen packages and scientific inputs unchanged.
"""
    plugin = {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
              "name": PLUGIN_NAME, "version": "0.0.1", "skills": "./skills/",
              "description": "Private exact-package resource byte transport prototype; no research or dependency setup."}
    prefix = f"skills/{SKILL_NAME}/"
    files = {"plugin.json": (json.dumps(plugin, indent=2) + "\n").encode(),
             prefix + "SKILL.md": skill.encode(), prefix + "scripts/verify_archive_transfer.py": helper}
    files.update({prefix + "assets/transfer/" + name: raw for name, raw in original.items()})
    return files


def write_plugin(files, output):
    output = verifier.unlinked(output)
    if output.exists():
        raise ValueError("Private prototype output must be a new owned file")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(files.items()):
            item = zipfile.ZipInfo(verifier.relative(name), (1980, 1, 1, 0, 0, 0))
            item.create_system = 3
            item.external_attr = (stat.S_IFREG | 0o444) << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, raw, compresslevel=9)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(files):
            raise ValueError("Private prototype ZIP failed CRC/inventory")
        if any(archive.read(name) != raw for name, raw in files.items()):
            raise ValueError("Private prototype ZIP changed original resource bytes")
    return {"ok": True, "output": str(output), "size": output.stat().st_size,
            "sha256": verifier.digest(output.read_bytes()), "entries": len(files),
            "published": False, "package_code_executed": False, "dependencies_prepared": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--inventory-path", default="skills/paper-factory/inventory.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = verifier.bounded(args.archive, verifier.MAX_ARCHIVE)
    files = plugin_files(raw, archive_sha256=args.archive_sha256, version=args.version, inventory_path=args.inventory_path)
    print(json.dumps(write_plugin(files, args.output)))

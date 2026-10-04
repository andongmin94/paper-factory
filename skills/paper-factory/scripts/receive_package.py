"""Verify and materialize original text-package bytes; never execute them.

The manifest SHA must come from the installed skill's reviewed transfer metadata.
Resource responses must be saved as their exact UTF-8 text, without rewriting.
Binary dependencies are separate: an incomplete package is never reported ready.
"""

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile


FORMAT = "paper-factory-text-transfer-v1"
MAX_ARCHIVE = 4 * 1024 * 1024
MAX_TEXT = 2 * 1024 * 1024
MAX_RESOURCES = 512


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def relative(name):
    if (not isinstance(name, str) or not name or "\\" in name or ":" in name
            or any(ord(char) < 32 for char in name) or PurePosixPath(name).is_absolute()
            or any(part in {"", ".", ".."} for part in name.split("/"))):
        raise ValueError("Unsafe transfer path")
    for part in name.split("/"):
        if (part.endswith((".", " ")) or any(char in '<>"|?*' for char in part)
                or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", part.split(".")[0], re.IGNORECASE)):
            raise ValueError("Unsafe transfer path")
    return name


def unlinked(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise ValueError("Linked transfer path")
    return path


def bounded(path, limit):
    path = unlinked(path)
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_size > limit:
        raise ValueError("Transfer input is not a bounded ordinary file")
    raw = path.read_bytes()
    if len(raw) != metadata.st_size:
        raise ValueError("Transfer input changed while reading")
    return raw


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate transfer JSON key")
        result[key] = value
    return result


def decode_json(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Invalid JSON number")))


def record(value, maximum):
    if (not isinstance(value, dict) or type(value.get("size")) is not int
            or not 0 <= value["size"] <= maximum
            or not isinstance(value.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"])):
        raise ValueError("Invalid transfer digest record")


def checked(raw, expected):
    if len(raw) != expected["size"] or digest(raw) != expected["sha256"]:
        raise ValueError("Transfer size or SHA256 mismatch")
    return raw


def load_transfer(manifest_path, manifest_sha256):
    if not isinstance(manifest_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256):
        raise ValueError("A reviewed manifest SHA256 is required")
    manifest_path = unlinked(manifest_path)
    raw = bounded(manifest_path, MAX_TEXT)
    if digest(raw) != manifest_sha256:
        raise ValueError("Transfer manifest SHA256 mismatch")
    manifest = decode_json(raw)
    if (not isinstance(manifest, dict) or manifest.get("format") != FORMAT
            or not isinstance(manifest.get("version"), str)
            or not isinstance(manifest.get("files"), dict)
            or not 1 <= len(manifest["files"]) <= MAX_RESOURCES
            or not isinstance(manifest.get("chunks"), list)
            or not 1 <= len(manifest["chunks"]) <= MAX_RESOURCES):
        raise ValueError("Invalid transfer manifest")
    record(manifest.get("archive"), MAX_ARCHIVE)
    files = manifest["files"]
    for name, item in files.items():
        relative(name)
        record(item, MAX_TEXT)
    if len({name.casefold() for name in files}) != len(files) or sum(x["size"] for x in files.values()) > MAX_TEXT:
        raise ValueError("Transfer file names or total size invalid")
    inventory_path = manifest.get("inventory_path")
    if inventory_path is not None and relative(inventory_path) not in files:
        raise ValueError("Transfer inventory is not a declared file")
    parts = []
    seen = set()
    for index, chunk in enumerate(manifest["chunks"]):
        if not isinstance(chunk, dict) or type(chunk.get("index")) is not int or chunk["index"] != index:
            raise ValueError("Transfer chunks are not in exact order")
        name = relative(chunk.get("path"))
        if name.casefold() in seen:
            raise ValueError("Duplicate transfer chunk")
        seen.add(name.casefold())
        record(chunk.get("text"), 128 * 1024)
        record(chunk.get("decoded"), 96 * 1024)
        text = checked(bounded(manifest_path.parent / name, 128 * 1024), chunk["text"])
        if not text.endswith(b"\n") or b"\n" in text[:-1] or b"\r" in text:
            raise ValueError("Transfer resource text was rewritten")
        try:
            part = base64.b64decode(text[:-1], validate=True)
        except ValueError as error:
            raise ValueError("Invalid transfer base64") from error
        parts.append(checked(part, chunk["decoded"]))
        if sum(map(len, parts)) > MAX_ARCHIVE:
            raise ValueError("Transfer archive exceeds its bound")
    archive_raw = checked(b"".join(parts), manifest["archive"])
    contents = {}
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as archive:
        entries = archive.infolist()
        if len(entries) != len(files) or {item.filename for item in entries} != set(files):
            raise ValueError("Transfer archive differs from its complete file manifest")
        for item in entries:
            relative(item.filename)
            if (item.is_dir() or stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1
                    or item.file_size != files[item.filename]["size"]):
                raise ValueError("Unsafe transfer archive entry")
            content = checked(archive.read(item), files[item.filename])
            content.decode("utf-8")
            contents[item.filename] = content
    return manifest, contents


def verify_inventory(data, inventory_path):
    """Check the executable snapshot inventory, including separately fetched assets."""
    if inventory_path is None:
        return {"package_verified": False, "reason": "Preview has no executable package inventory", "missing_assets": []}
    inventory = decode_json(bounded(data / relative(inventory_path), MAX_TEXT))
    if (not isinstance(inventory, dict) or not isinstance(inventory.get("files"), dict)
            or not 1 <= len(inventory["files"]) <= MAX_RESOURCES
            or len({name.casefold() for name in inventory["files"]}) != len(inventory["files"])):
        raise ValueError("Invalid executable package inventory")
    resource_root = data / PurePosixPath(inventory_path).parent
    missing = []
    for name, expected in inventory["files"].items():
        relative(name)
        record(expected, 100 * 1024 * 1024)
        path = unlinked(resource_root / name)
        if not path.exists():
            missing.append(name)
        else:
            checked(bounded(path, 100 * 1024 * 1024), expected)
    return {"package_verified": not missing, "files_checked": len(inventory["files"]),
            "missing_assets": missing, "inventory_sha256": digest(bounded(data / inventory_path, MAX_TEXT))}


def receive(manifest_path, manifest_sha256, data, *, verify_only=False):
    manifest, contents = load_transfer(manifest_path, manifest_sha256)
    data = unlinked(data)
    if verify_only:
        if not data.is_dir():
            raise ValueError("Transferred package directory is unavailable")
        for name, raw in contents.items():
            if bounded(data / name, MAX_TEXT) != raw:
                raise ValueError("Transferred package text changed")
    else:
        if data.exists():
            if not data.is_dir() or any(data.iterdir()):
                raise ValueError("Transfer destination must be an approved empty directory")
        else:
            data.mkdir()  # Its approved parent must already exist; no path discovery.
        for name, raw in contents.items():
            path = data.joinpath(*PurePosixPath(name).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(raw)
            if bounded(path, MAX_TEXT) != raw:
                raise ValueError("Transferred output bytes changed")
            path.chmod(0o444)
    return {"ok": True, "action": "receive-package", "version": manifest["version"],
            "text_files_verified": len(contents), "archive_sha256": manifest["archive"]["sha256"],
            "data": str(data), "code_executed": False, "network_accessed": False,
            **verify_inventory(data, manifest.get("inventory_path"))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(receive(args.manifest, args.manifest_sha256, args.data, verify_only=args.verify_only)))
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print(json.dumps({"ok": False, "action": "receive-package", "error": type(error).__name__,
                          "message": "Original resource transfer could not be verified; do not execute the package."}))
        raise SystemExit(2)

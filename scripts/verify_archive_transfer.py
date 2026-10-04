"""Verify opaque original package archive bytes; never execute package contents."""

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import zipfile


FORMAT = "paper-factory-package-byte-transfer-v1"
MAX_ARCHIVE = 8 * 1024 * 1024
MAX_FILES = 512
MAX_MANIFEST = 18000
MAX_CHUNK_TEXT = 18000


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def relative(name):
    if (not isinstance(name, str) or not name or name.startswith("/") or "\\" in name or ":" in name
            or any(ord(char) < 32 for char in name)
            or any(part in {"", ".", ".."} for part in name.split("/"))):
        raise ValueError("Unsafe original package path")
    for part in name.split("/"):
        if (part.endswith((".", " ")) or any(char in '<>"|?*' for char in part)
                or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", part.split(".")[0], re.I)):
            raise ValueError("Unsafe original package path")
    return name


def unlinked(path):
    path = Path(path).absolute()
    if any(p.is_symlink() or getattr(p, "is_junction", lambda: False)() for p in (path, *path.parents)):
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


def pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValueError("Duplicate transfer JSON key")
        result[key] = value
    return result


def decode_json(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Invalid JSON number")))


def hash_value(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("A trusted SHA256 is required")


def checked(raw, record):
    if (not isinstance(record, dict) or type(record.get("size")) is not int
            or not 0 <= record["size"] <= MAX_ARCHIVE):
        raise ValueError("Invalid original digest record")
    hash_value(record.get("sha256"))
    if len(raw) != record["size"] or digest(raw) != record["sha256"]:
        raise ValueError("Original byte size or SHA256 mismatch")
    return raw


def archive_files(raw):
    if len(raw) > MAX_ARCHIVE:
        raise ValueError("Original package archive is oversized")
    result = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if not 1 <= len(entries) <= MAX_FILES or sum(x.file_size for x in entries) > MAX_ARCHIVE:
            raise ValueError("Original package member bounds exceeded")
        seen = set()
        for item in entries:
            if item.orig_filename != item.filename:
                raise ValueError("Unsafe original package member name normalization")
            name = relative(item.filename)
            mode = stat.S_IFMT(item.external_attr >> 16)
            if (name.casefold() in seen or item.is_dir() or item.flag_bits & 1
                    or mode not in {0, stat.S_IFREG} or not 0 <= item.file_size <= MAX_ARCHIVE):
                raise ValueError("Unsafe original package member")
            seen.add(name.casefold())
            content = archive.read(item)
            if len(content) != item.file_size:
                raise ValueError("Original package member size changed")
            result[name] = content
    return result


def inventory_check(contents, inventory_path):
    inventory_path = relative(inventory_path)
    if inventory_path not in contents:
        raise ValueError("Original inventory is absent")
    inventory = decode_json(contents[inventory_path])
    files = inventory.get("files") if isinstance(inventory, dict) else None
    if (not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES
            or len({name.casefold() for name in files}) != len(files)):
        raise ValueError("Original inventory is invalid")
    resource_root = inventory_path.rpartition("/")[0]
    for name, expected in files.items():
        path = (resource_root + "/" if resource_root else "") + relative(name)
        if path not in contents:
            raise ValueError("Original inventoried resource is missing")
        checked(contents[path], expected)
    return len(files)


def load_manifest(path, pin):
    hash_value(pin)
    path = unlinked(path)
    raw = bounded(path, MAX_MANIFEST)
    if digest(raw) != pin:
        raise ValueError("Original manifest SHA256 mismatch")
    value = decode_json(raw)
    if not isinstance(value, dict) or value.get("format") != FORMAT or not isinstance(value.get("version"), str):
        raise ValueError("Invalid transfer format")
    archive = value.get("archive")
    if not isinstance(archive, dict) or type(archive.get("size")) is not int or not 1 <= archive["size"] <= MAX_ARCHIVE:
        raise ValueError("Invalid original archive bound")
    hash_value(archive.get("sha256"))
    width, chunks, files = value.get("chunk_bytes"), value.get("chunks"), value.get("files")
    if type(width) is not int or not 1 <= width <= 12288:
        raise ValueError("Invalid transfer chunk width")
    if (not isinstance(chunks, list) or len(chunks) != (archive["size"] + width - 1) // width
            or not 1 <= len(chunks) <= MAX_FILES):
        raise ValueError("Invalid complete chunk count")
    for pin in chunks:
        hash_value(pin)
    if (not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES
            or len({name.casefold() for name in files}) != len(files)):
        raise ValueError("Invalid original file manifest")
    for name, record in files.items():
        relative(name)
        if not isinstance(record, dict) or type(record.get("size")) is not int or not 0 <= record["size"] <= MAX_ARCHIVE:
            raise ValueError("Invalid original file bounds")
        hash_value(record.get("sha256"))
    if sum(r["size"] for r in files.values()) > MAX_ARCHIVE or relative(value.get("inventory_path")) not in files:
        raise ValueError("Invalid original inventory declaration")
    return value, path.parent


def read_chunks(value, root, count):
    parts, records = [], []
    for index in range(count):
        name = f"chunks/{index:06d}.txt"
        text = bounded(root / name, MAX_CHUNK_TEXT)
        expected_bytes = min(value["chunk_bytes"], value["archive"]["size"] - index * value["chunk_bytes"])
        if len(text) != ((expected_bytes + 2) // 3) * 4 + 1 or digest(text) != value["chunks"][index]:
            raise ValueError("Original chunk size or SHA256 mismatch")
        if not text.endswith(b"\n") or b"\n" in text[:-1] or b"\r" in text:
            raise ValueError("Original chunk text was rewritten")
        raw = base64.b64decode(text[:-1], validate=True)
        if len(raw) != expected_bytes or base64.b64encode(raw) + b"\n" != text:
            raise ValueError("Original chunk encoding is not canonical")
        parts.append(raw)
        records.append({"index": index, "path": name, "text_size": len(text), "text_sha256": digest(text),
                        "decoded_size": len(raw), "decoded_sha256": digest(raw)})
    return parts, records


def receive(manifest_path, manifest_sha256, data, *, pilot_chunks=None):
    value, resources = load_manifest(manifest_path, manifest_sha256)
    if pilot_chunks is not None and (type(pilot_chunks) is not int or not 1 <= pilot_chunks <= len(value["chunks"])):
        raise ValueError("Invalid chunk pilot count")
    parts, records = read_chunks(value, resources, pilot_chunks or len(value["chunks"]))
    result = {"ok": True, "action": "verify-original-package-transfer", "version": value["version"],
              "chunks_verified": len(records), "chunks_total": len(value["chunks"]), "chunks": records,
              "package_verified": False, "code_executed": False, "network_accessed": False,
              "dependencies_prepared": False, "execution_ready": False}
    if pilot_chunks is not None:
        result["stage"] = "chunk-pilot"
        return result  # Never extract partial bytes or claim a complete original package.
    archive = checked(b"".join(parts), value["archive"])
    contents = archive_files(archive)
    if set(contents) != set(value["files"]):
        raise ValueError("Original archive differs from the complete file manifest")
    for name, raw in contents.items():
        checked(raw, value["files"][name])
    inventory_count = inventory_check(contents, value["inventory_path"])
    data = unlinked(data)
    if data.exists():
        if not data.is_dir() or any(data.iterdir()):
            raise ValueError("Original package destination must be an approved empty directory")
    else:
        data.mkdir()  # Require an existing approved scratch parent.
    for name, raw in contents.items():
        target = data / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
        checked(bounded(target, MAX_ARCHIVE), value["files"][name])
    result.update(stage="whole-package", package_verified=True, original_files_verified=len(contents),
                  inventory_files_verified=inventory_count, archive_sha256=digest(archive), data=str(data))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--pilot-chunks", type=int)
    args = parser.parse_args()
    try:
        print(json.dumps(receive(args.manifest, args.manifest_sha256, args.data, pilot_chunks=args.pilot_chunks)))
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(json.dumps({"ok": False, "action": "verify-original-package-transfer", "error": type(exc).__name__,
                          "package_verified": False, "execution_ready": False,
                          "message": "Preserve the first failed transfer and its raw responses; do not execute package content."}))
        raise SystemExit(2)

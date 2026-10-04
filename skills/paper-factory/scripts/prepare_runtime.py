"""Extract verified generic runtime bytes; execute no diagnostic or study."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def prepare(data):
    from probe import package_access
    if not package_access()["verified"]:
        raise ValueError("Installed workflow resources differ from their inventory")
    metadata = json.loads((ROOT / "assets/quickjs-runtime.json").read_text(encoding="utf-8"))
    content = (ROOT / "assets/quickjs-runtime.zip").read_bytes()
    if (metadata["root_directory"] != "quickjs-runtime"
            or len(content) != metadata["archive_size"]
            or hashlib.sha256(content).hexdigest() != metadata["archive_sha256"]):
        raise ValueError("Pinned generic runtime archive changed")
    data = data.expanduser().absolute()
    if any(path.is_symlink() or getattr(path, "is_junction", lambda: False)() for path in (data, *data.parents)):
        raise ValueError("Linked scratch path is forbidden")
    data = data.resolve()
    if data == ROOT or ROOT in data.parents or data in ROOT.parents:
        raise ValueError("Scratch must be outside installed resources")
    if data.exists() and (not data.is_dir() or any(data.iterdir())):
        raise ValueError("Use empty approved runtime scratch; retain existing attempts")
    with zipfile.ZipFile(io.BytesIO(content)) as bundle:
        entries = bundle.infolist()
        names = {item.filename for item in entries}
        if (len(entries) != metadata["entries"] or len({name.casefold() for name in names}) != len(entries)
                or sum(item.file_size for item in entries) > 2 * 1024 * 1024 or bundle.testzip()):
            raise ValueError("Unexpected bounded runtime archive inventory")
        for item in entries:
            path = PurePosixPath(item.filename)
            if (path.is_absolute() or any(part in {"", ".", ".."} for part in item.filename.split("/"))
                    or "\\" in item.filename or ":" in item.filename or item.is_dir()
                    or stat.S_ISLNK(item.external_attr >> 16)
                    or (item.filename not in {"quickjs-runtime/package.json", "quickjs-runtime/package-lock.json", "quickjs-runtime/inventory.json"}
                        and not item.filename.startswith("quickjs-runtime/node_modules/"))):
                raise ValueError("Unsafe or non-runtime archive entry")
        inventory_raw = bundle.read("quickjs-runtime/inventory.json")
        if hashlib.sha256(inventory_raw).hexdigest() != metadata["inventory_sha256"]:
            raise ValueError("Pinned runtime inventory changed")
        expected = json.loads(inventory_raw)["files"]
        if names != {"quickjs-runtime/inventory.json", *("quickjs-runtime/" + name for name in expected)}:
            raise ValueError("Runtime entries differ from the full inventory")
        for name, value in expected.items():
            raw = bundle.read("quickjs-runtime/" + name)
            if len(raw) != value["size"] or hashlib.sha256(raw).hexdigest() != value["sha256"]:
                raise ValueError("Runtime resource differs from its inventory")
        data.mkdir(parents=True, exist_ok=True)
        for item in entries:
            destination = data.joinpath(*PurePosixPath(item.filename).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as output:
                output.write(bundle.read(item.filename))
    return {"ok": True, "runtime_root": str(data / "quickjs-runtime"),
            "archive_sha256": metadata["archive_sha256"], "inventory_sha256": metadata["inventory_sha256"],
            "files_verified": len(entries), "runtime_readiness_checked": False,
            "diagnostic_executed": False, "experiment_executed": False,
            "instructions": "Use the verified private interpreter and this --runtime-root with the controller environment command."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.data)))
    except Exception as error:
        from probe import safe_error
        print(json.dumps({"ok": False, "error": safe_error(error)}))
        raise SystemExit(1)

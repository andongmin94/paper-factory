"""Original resource byte transport; no research or decoded code execution."""

import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


builder = module("skill_transfer_builder", ROOT / "scripts/build_skill_transfer.py")
receiver = module("skill_transfer_receiver", ROOT / "skills/paper-factory/scripts/receive_package.py")


@pytest.fixture
def packet(tmp_path):
    created = []

    def prepare(files=None, inventory_path=None):
        directory = tmp_path / f"packet-{len(created)}"
        resources = builder.preview() if files is None else builder.build_transfer(
            files, version="test", inventory_path=inventory_path)
        builder.write_resources(resources, directory)
        created.append(directory)
        return directory, json.loads(resources["manifest.json"])

    yield prepare
    # Windows cannot remove read-only generated files during pytest cleanup.
    for path in tmp_path.rglob("*"):
        if path.is_file() and not path.is_symlink():
            path.chmod(0o600)


def save_manifest(directory, manifest):
    raw = (json.dumps(manifest, indent=2) + "\n").encode()
    (directory / "manifest.json").write_bytes(raw)
    return receiver.digest(raw)


def receive(directory, data, **options):
    return receiver.receive(directory / "manifest.json",
                            receiver.digest((directory / "manifest.json").read_bytes()), data, **options)


def rewrite_archive(directory, manifest, raw):
    assert len(manifest["chunks"]) == 1
    chunk = manifest["chunks"][0]
    encoded = base64.b64encode(raw) + b"\n"
    (directory / chunk["path"]).write_bytes(encoded)
    chunk["text"] = {"size": len(encoded), "sha256": receiver.digest(encoded)}
    chunk["decoded"] = {"size": len(raw), "sha256": receiver.digest(raw)}
    manifest["archive"] = chunk["decoded"].copy()
    save_manifest(directory, manifest)


def test_original_one_kib_fixture_roundtrip(packet, tmp_path):
    directory, manifest = packet()
    data = tmp_path / "received"
    result = receive(directory, data)
    raw = (data / "preview.txt").read_bytes()
    assert len(raw) == 1024
    assert receiver.digest(raw) == manifest["files"]["preview.txt"]["sha256"]
    assert result["ok"] and result["text_files_verified"] == 1
    assert not result["package_verified"] and not result["code_executed"] and not result["network_accessed"]


def test_unicode_bom_crlf_and_code_bytes_retained_without_execution(packet, tmp_path):
    raw = b"\xef\xbb\xbf" + "한글 \U0001f680\r\n".encode() + b"raise RuntimeError('must never execute')\r\n"
    directory, _ = packet({"src/original.py": raw})
    assert receive(directory, tmp_path / "received")["ok"]
    assert (tmp_path / "received/src/original.py").read_bytes() == raw


def test_resources_deterministic_across_input_order():
    files = {"z.txt": b"z\n", "a.txt": b"a\r\n"}
    assert builder.build_transfer(files, version="test") == builder.build_transfer(
        dict(reversed(list(files.items()))), version="test")


def test_wrong_manifest_pin_rejected_before_write(packet, tmp_path):
    directory, _ = packet()
    with pytest.raises(ValueError, match="manifest SHA256"):
        receiver.receive(directory / "manifest.json", "0" * 64, tmp_path / "received")
    assert not (tmp_path / "received").exists()


@pytest.mark.parametrize("change", [lambda b: b[:-8], lambda b: b[:-1], lambda b: b + b"\n"])
def test_changed_or_truncated_chunk_rejected_before_write(packet, tmp_path, change):
    directory, manifest = packet()
    path = directory / manifest["chunks"][0]["path"]
    path.write_bytes(change(path.read_bytes()))
    with pytest.raises(ValueError):
        receive(directory, tmp_path / "received")
    assert not (tmp_path / "received").exists()


def test_missing_chunk_rejected_before_write(packet, tmp_path):
    directory, manifest = packet()
    (directory / manifest["chunks"][0]["path"]).unlink()
    with pytest.raises(FileNotFoundError):
        receive(directory, tmp_path / "received")
    assert not (tmp_path / "received").exists()


def test_decoded_hash_verified_even_when_text_digest_updated(packet, tmp_path):
    directory, manifest = packet()
    chunk = manifest["chunks"][0]
    original = base64.b64decode((directory / chunk["path"]).read_bytes())
    encoded = base64.b64encode(original[:-1] + bytes([original[-1] ^ 1])) + b"\n"
    (directory / chunk["path"]).write_bytes(encoded)
    chunk["text"] = {"size": len(encoded), "sha256": receiver.digest(encoded)}
    save_manifest(directory, manifest)
    with pytest.raises(ValueError, match="SHA256"):
        receive(directory, tmp_path / "received")
    assert not (tmp_path / "received").exists()


def test_invalid_base64_rejected_even_when_text_digest_matches(packet, tmp_path):
    directory, manifest = packet()
    chunk = manifest["chunks"][0]
    encoded = b"*" + (directory / chunk["path"]).read_bytes()[1:]
    (directory / chunk["path"]).write_bytes(encoded)
    chunk["text"] = {"size": len(encoded), "sha256": receiver.digest(encoded)}
    save_manifest(directory, manifest)
    with pytest.raises(ValueError, match="base64"):
        receive(directory, tmp_path / "received")


def test_multiple_chunks_exact_order_required(packet, tmp_path):
    directory, manifest = packet({"data.txt": os.urandom(18000).hex().encode()})
    assert len(manifest["chunks"]) > 1
    manifest["chunks"].reverse()
    save_manifest(directory, manifest)
    with pytest.raises(ValueError, match="exact order"):
        receive(directory, tmp_path / "received")


@pytest.mark.parametrize("name", ["../escape.txt", "/absolute.txt", "C:/drive.txt", "a\\b.txt", "a/./b.txt", "a//b.txt",
                                  "a/.. /escape.txt", "trailing./file.txt", "CON.txt", "a/NUL"])
def test_unsafe_manifest_path_rejected_before_write(packet, tmp_path, name):
    directory, manifest = packet()
    manifest["files"] = {name: manifest["files"]["preview.txt"]}
    save_manifest(directory, manifest)
    with pytest.raises(ValueError, match="Unsafe transfer path"):
        receive(directory, tmp_path / "received")
    assert not (tmp_path / "received").exists()


def test_case_conflicts_rejected_in_builder():
    with pytest.raises(ValueError, match="Duplicate"):
        builder.build_transfer({"A.txt": b"a", "a.txt": b"b"}, version="test")


def test_original_file_hash_verified_inside_archive(packet, tmp_path):
    directory, manifest = packet()
    manifest["files"]["preview.txt"]["sha256"] = "0" * 64
    save_manifest(directory, manifest)
    with pytest.raises(ValueError, match="SHA256"):
        receive(directory, tmp_path / "received")
    assert not (tmp_path / "received").exists()


def test_archive_symlink_rejected(packet, tmp_path):
    directory, manifest = packet()
    original = zipfile.ZipFile(io.BytesIO(base64.b64decode(
        (directory / manifest["chunks"][0]["path"]).read_bytes()))).read("preview.txt")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        item = zipfile.ZipInfo("preview.txt")
        item.create_system = 3
        item.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(item, original)
    rewrite_archive(directory, manifest, buffer.getvalue())
    with pytest.raises(ValueError, match="Unsafe transfer archive"):
        receive(directory, tmp_path / "received")
    assert not (tmp_path / "received").exists()


def test_nonempty_destination_preserved(packet, tmp_path):
    directory, _ = packet()
    data = tmp_path / "received"
    data.mkdir()
    (data / "existing.txt").write_bytes(b"preserve")
    with pytest.raises(ValueError, match="empty directory"):
        receive(directory, data)
    assert (data / "existing.txt").read_bytes() == b"preserve"
    assert list(data.iterdir()) == [data / "existing.txt"]


def test_missing_binary_inventory_never_claims_package_ready(packet, tmp_path):
    core = b"raise RuntimeError('not execution')\n"
    asset = b"\x00original binary bytes"
    inventory = {"files": {"src/core.py": {"size": len(core), "sha256": receiver.digest(core)},
                           "assets/runtime.zip": {"size": len(asset), "sha256": receiver.digest(asset)}}}
    directory, _ = packet({"skills/example/src/core.py": core,
                           "skills/example/inventory.json": json.dumps(inventory).encode()},
                          inventory_path="skills/example/inventory.json")
    data = tmp_path / "received"
    result = receive(directory, data)
    assert not result["package_verified"] and result["missing_assets"] == ["assets/runtime.zip"]
    (data / "skills/example/assets").mkdir()
    (data / "skills/example/assets/runtime.zip").write_bytes(asset)
    result = receive(directory, data, verify_only=True)
    assert result["package_verified"] and result["files_checked"] == 2
    assert not result["code_executed"] and not result["network_accessed"]


def test_inventory_tamper_and_changed_transferred_source_rejected(packet, tmp_path):
    directory, _ = packet()
    data = tmp_path / "received"
    receive(directory, data)
    (data / "preview.txt").chmod(0o600)
    (data / "preview.txt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="text changed"):
        receive(directory, data, verify_only=True)


def test_preview_plugin_crc_and_declared_chunk_bytes(tmp_path):
    path = tmp_path / "preview.zip"
    report = builder.write_preview_plugin(path)
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None and len(archive.namelist()) == 4
        for name, raw in builder.preview_plugin().items():
            assert archive.read(name) == raw
    assert report["fixture_bytes"] == 1024 and not report["published"]


def test_cli_failure_safe_and_nonzero(packet, tmp_path):
    directory, _ = packet()
    run = subprocess.run([sys.executable, str(ROOT / "skills/paper-factory/scripts/receive_package.py"),
                          "--manifest", str(directory / "manifest.json"), "--manifest-sha256", "0" * 64,
                          "--data", str(tmp_path / "received")], capture_output=True, text=True, check=False)
    output = json.loads(run.stdout)
    assert run.returncode == 2 and output["ok"] is False
    assert str(tmp_path) not in run.stdout and not run.stderr
    assert not (tmp_path / "received").exists()

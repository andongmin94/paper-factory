"""Exact binary archive transport only; decoded controller content never runs."""

import base64
import io
import json
import os
from pathlib import Path
import stat
import sys
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_package_transfer as builder
import verify_archive_transfer as verifier
sys.path.pop(0)


def zipped(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
    return output.getvalue()


@pytest.fixture
def packet(tmp_path):
    created = []

    def prepare(binary=None):
        core = b"raise RuntimeError('decoded core must never execute')\n"
        binary = os.urandom(40000) if binary is None else binary
        inventory = {"files": {"src/core.py": {"size": len(core), "sha256": verifier.digest(core)},
                               "assets/runtime.zip": {"size": len(binary), "sha256": verifier.digest(binary)}}}
        files = {"skills/example/src/core.py": core, "skills/example/assets/runtime.zip": binary,
                 "skills/example/inventory.json": json.dumps(inventory).encode()}
        original = zipped(files)
        resources = builder.resources(original, archive_sha256=verifier.digest(original), version="test",
                                      inventory_path="skills/example/inventory.json")
        directory = tmp_path / f"resources-{len(created)}"
        directory.mkdir()
        for name, raw in resources.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        created.append(directory)
        return directory, resources, original, files

    return prepare


def receive(directory, data, **options):
    return verifier.receive(directory / "manifest.json", verifier.digest((directory / "manifest.json").read_bytes()),
                            data, **options)


def test_binary_originals_full_inventory_roundtrip_no_execution(packet, tmp_path):
    directory, resources, original, files = packet(b"\x00\xfforiginal binary\x80\0")
    result = receive(directory, tmp_path / "package")
    assert result["package_verified"] and result["original_files_verified"] == 3
    assert result["inventory_files_verified"] == 2 and result["archive_sha256"] == verifier.digest(original)
    assert not result["code_executed"] and not result["execution_ready"] and not result["dependencies_prepared"]
    for name, raw in files.items():
        assert (tmp_path / "package" / name).read_bytes() == raw
    assert max(len(raw) for raw in resources.values()) <= 18000


def test_three_chunk_pilot_never_extracts_or_claims_package_complete(packet, tmp_path):
    directory, _, _, _ = packet()
    result = receive(directory, tmp_path / "not-created", pilot_chunks=3)
    assert result["ok"] and result["stage"] == "chunk-pilot" and result["chunks_verified"] == 3
    assert result["chunks_total"] > 3 and not result["package_verified"]
    assert not (tmp_path / "not-created").exists()


@pytest.mark.parametrize("change", [lambda raw: raw[:-1], lambda raw: raw + b"\n", lambda raw: b"x" + raw[1:]])
def test_changed_chunk_preserved_and_rejected_before_extraction(packet, tmp_path, change):
    directory, _, _, _ = packet()
    path = directory / "chunks/000000.txt"
    failed = change(path.read_bytes())
    path.write_bytes(failed)
    with pytest.raises(ValueError, match="chunk"):
        receive(directory, tmp_path / "package", pilot_chunks=3)
    assert path.read_bytes() == failed and not (tmp_path / "package").exists()


def test_missing_later_chunk_cannot_be_silently_omitted(packet, tmp_path):
    directory, _, _, _ = packet()
    (directory / "chunks/000003.txt").unlink()
    assert receive(directory, tmp_path / "package", pilot_chunks=3)["ok"]
    with pytest.raises(FileNotFoundError):
        receive(directory, tmp_path / "package")
    assert not (tmp_path / "package").exists()


def test_frozen_package_hash_rejected_in_builder(packet):
    _, _, original, _ = packet()
    with pytest.raises(ValueError, match="Frozen original"):
        builder.resources(original, archive_sha256="0" * 64, version="test", inventory_path="skills/example/inventory.json")


def test_manifest_pin_is_mandatory_before_any_original_data_reads(packet, tmp_path):
    directory, _, _, _ = packet()
    with pytest.raises(ValueError, match="manifest SHA256"):
        verifier.receive(directory / "manifest.json", "0" * 64, tmp_path / "package")
    assert not (tmp_path / "package").exists()


@pytest.mark.parametrize("name", ["../escape", "C:/drive", "a\\b", "CON.txt", "trailing./x"])
def test_unsafe_archive_paths_rejected_without_extraction(name):
    raw = zipped({name: b"no-execution"})
    if "\\" in name:
        # Windows ZipInfo normalizes its OS separator during creation; restore
        # the actual unsafe ZIP header spelling to exercise the reader boundary.
        raw = raw.replace(name.replace("\\", "/").encode(), name.encode())
    with pytest.raises(ValueError, match="Unsafe original package"):
        verifier.archive_files(raw)


def test_link_and_case_duplicate_members_are_not_materialized():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        item = zipfile.ZipInfo("linked")
        item.create_system = 3
        item.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(item, b"target")
    with pytest.raises(ValueError, match="Unsafe original package member"):
        verifier.archive_files(output.getvalue())
    with pytest.raises(ValueError, match="Unsafe original package member"):
        verifier.archive_files(zipped({"A.txt": b"a", "a.txt": b"b"}))


def test_inventory_missing_binary_is_blocker_not_ready(packet):
    _, _, _, files = packet()
    files.pop("skills/example/assets/runtime.zip")
    original = zipped(files)
    with pytest.raises(ValueError, match="inventoried resource is missing"):
        builder.resources(original, archive_sha256=verifier.digest(original), version="test",
                          inventory_path="skills/example/inventory.json")


def test_full_archive_and_per_member_hashes_are_both_checked(packet, tmp_path):
    directory, resources, _, _ = packet()
    value = json.loads(resources["manifest.json"])
    value["files"]["skills/example/src/core.py"]["sha256"] = "0" * 64
    (directory / "manifest.json").write_bytes(json.dumps(value).encode())
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        receive(directory, tmp_path / "package")
    assert not (tmp_path / "package").exists()


def test_nonempty_existing_destination_preserved(packet, tmp_path):
    directory, _, _, _ = packet()
    data = tmp_path / "package"
    data.mkdir()
    (data / "first-failure.json").write_bytes(b"preserve")
    with pytest.raises(ValueError, match="empty directory"):
        receive(directory, data)
    assert (data / "first-failure.json").read_bytes() == b"preserve"
    assert len(list(data.iterdir())) == 1


def test_prototype_zip_deterministic_and_full_resource_bytes(packet, tmp_path):
    _, _, original, _ = packet()
    files = builder.plugin_files(original, archive_sha256=verifier.digest(original), version="test",
                                 inventory_path="skills/example/inventory.json")
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    a, b = builder.write_plugin(files, first), builder.write_plugin(files, second)
    assert first.read_bytes() == second.read_bytes() and a["sha256"] == b["sha256"]
    with zipfile.ZipFile(first) as archive:
        assert archive.testzip() is None
        assert all(archive.read(name) == raw for name, raw in files.items())
    assert not a["published"] and not a["package_code_executed"]

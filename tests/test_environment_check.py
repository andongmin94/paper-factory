"""Prerequisite detection must not imply a verified render or mutate a setup."""

import importlib
from importlib import metadata
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
environment = importlib.import_module("environment_check")


def test_missing_package_is_reported(monkeypatch):
    def missing(name):
        raise metadata.PackageNotFoundError(name)
    monkeypatch.setattr(environment.metadata, "version", missing)
    rows = environment._packages()
    assert len(rows) == 4
    assert all(row["status"] == "missing" for row in rows)


def test_incompatible_and_unusual_versions_remain_visible(monkeypatch):
    versions = {"python-docx": "0.8.11", "pypdfium2": "5.14.1", "Pillow": "13.0.0", "pypandoc_binary": "1.17rc1"}
    monkeypatch.setattr(environment.metadata, "version", versions.__getitem__)
    rows = {row["name"]: row for row in environment._packages()}
    assert rows["python-docx"]["status"] == "incompatible"
    assert rows["pypdfium2"]["status"] == "detected"
    assert rows["Pillow"]["status"] == "incompatible"
    assert rows["pypandoc_binary"]["status"] == "unverified_version"


def test_detected_prerequisites_do_not_certify_native_export(monkeypatch):
    monkeypatch.setattr(environment, "_packages", lambda: [{"name": "example", "status": "detected"}])
    monkeypatch.setattr(environment.sys, "platform", "win32")
    monkeypatch.setattr(environment, "_word_registration", lambda: {"status": "detected"})
    monkeypatch.setattr(environment.shutil, "which", lambda name: "C:/Windows/powershell.exe")
    monkeypatch.setattr(environment, "pandoc_binary", lambda explicit: Path("C:/pandoc.exe"))
    monkeypatch.setattr(environment.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 0, "pandoc 3.8\n", ""))
    monkeypatch.setattr(environment, "official_template", lambda venue: (Path("C:/template.docx"), {"sha256": "a" * 64}))
    result = environment.diagnose()
    assert result["native_export_prerequisites_detected"] is True
    assert result["native_export_verified"] is False


def test_failed_pandoc_probe_produces_a_diagnostic(monkeypatch):
    monkeypatch.setattr(environment, "pandoc_binary", lambda explicit: (_ for _ in ()).throw(ValueError("Unavailable")))
    result = environment.diagnose()
    assert result["pandoc"]["status"] == "missing_or_unusable"
    assert not result["native_export_prerequisites_detected"]


def test_python_version_banner_is_not_pandoc():
    result = environment.diagnose(sys.executable)
    assert result["pandoc"]["status"] == "missing_or_unusable"
    assert not result["native_export_prerequisites_detected"]


def test_existing_pandoc_does_not_require_a_second_provider(monkeypatch):
    monkeypatch.setattr(environment, "_packages", lambda: [{"name": "python-docx", "status": "detected"},
                                                           {"name": "pypandoc_binary", "status": "missing"}])
    monkeypatch.setattr(environment.sys, "platform", "win32")
    monkeypatch.setattr(environment, "_word_registration", lambda: {"status": "detected"})
    monkeypatch.setattr(environment.shutil, "which", lambda name: "C:/Windows/powershell.exe")
    monkeypatch.setattr(environment, "pandoc_binary", lambda explicit: Path("C:/pandoc.exe"))
    monkeypatch.setattr(environment.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 0, "pandoc 3.8\n", ""))
    monkeypatch.setattr(environment, "official_template", lambda venue: (Path("C:/template.docx"), {"sha256": "a" * 64}))
    result = environment.diagnose("C:/pandoc.exe")
    assert result["native_export_prerequisites_detected"]
    assert result["packages"][1]["status"] == "missing"
    assert not result["packages"][1]["required_for_export"]


def test_cli_retains_existing_output(tmp_path):
    folder = tmp_path / "existing"
    folder.mkdir()
    marker = folder / "keep.txt"
    marker.write_text("unchanged")
    script = Path(environment.__file__)
    result = subprocess.run([sys.executable, str(script), "--output-dir", str(folder)], capture_output=True, text=True)
    assert result.returncode == 2
    assert marker.read_text() == "unchanged"
    assert list(folder.iterdir()) == [marker]


def test_windows_bundled_pandoc_suffix_is_resolved(tmp_path, monkeypatch):
    if sys.platform != "win32":
        return
    from types import SimpleNamespace
    converter = importlib.import_module("_publication_convert")
    binary = tmp_path / "pandoc.exe"
    binary.write_bytes(b"test executable placeholder; never run")
    monkeypatch.delenv("PYPANDOC_PANDOC", raising=False)
    monkeypatch.setattr(converter.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "pypandoc", SimpleNamespace(get_pandoc_path=lambda: str(binary.with_suffix(""))))
    assert converter.pandoc_binary() == binary.resolve()

"""Provided-host prerequisite selection keeps inherited HTTP policy blocking."""

import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("mode, client_ready, imported", [
    ("private", True, False), ("provided", True, True), ("provided", False, False),
])
def test_optional_socks_transport_does_not_bypass_client_failure(monkeypatch, mode, client_ready, imported):
    path = Path(__file__).resolve().parents[1] / "skills/paper-factory/scripts/probe.py"
    spec = importlib.util.spec_from_file_location("provided_probe", path)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    original = probe.importlib.util.find_spec
    monkeypatch.setattr(probe.importlib.util, "find_spec", lambda name: None if name == "socksio" else original(name))
    monkeypatch.setattr(probe, "package_access", lambda: {"verified": True})
    monkeypatch.setattr(probe, "http_client", lambda: {"ready": client_ready, "request_executed": False})
    monkeypatch.setattr(probe, "pandoc_available", lambda: {"ready": True})
    monkeypatch.setenv("PF_HOST_MODE", mode)
    monkeypatch.setenv("PF_PDF_ENGINE", "pdflatex" if mode == "provided" else "typst")
    report = probe.capabilities()
    assert report["controller_imported"] is imported
    socks = report["dependencies"]["core"]["socksio"]
    assert socks["importable"] is False and socks["required"] is (mode == "private")
    assert report["dependencies"]["exports"]["typst"]["required"] is (mode == "private")
    assert report["isolation_checked"] is False and report["experiment_executed"] is False


def test_private_probe_cannot_silently_select_a_provided_pdf_engine(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "skills/paper-factory/scripts/probe.py"
    spec = importlib.util.spec_from_file_location("invalid_provided_probe", path)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    monkeypatch.setenv("PF_HOST_MODE", "private")
    monkeypatch.setenv("PF_PDF_ENGINE", "pdflatex")
    with pytest.raises(ValueError, match="Private preparation"):
        probe.capabilities()

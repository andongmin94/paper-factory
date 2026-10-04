"""Private execution configuration binds the controller to prepared binaries."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

SPEC = importlib.util.spec_from_file_location(
    "host_context", Path(__file__).resolve().parents[1] / "skills/paper-factory/scripts/host_context.py")
context = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(context)


@pytest.fixture
def preparation(tmp_path, monkeypatch):
    node = tmp_path / "node"
    pandoc = tmp_path / "pandoc"
    node.write_bytes(b"trusted node fixture")
    pandoc.write_bytes(b"trusted pandoc fixture")
    cache = tmp_path / "matplotlib"
    cache.mkdir()
    def record(path):
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    native = tmp_path / "actual-native-extension.fixture"
    native.write_bytes(b"actual installed bytes fixture; not executed")
    modules = {"schema_version": 1, "distributions": {"fixture": "1"},
               "modules": {"fixture": str(native)}, "files": {str(native): {
                   "size": native.stat().st_size, "sha256": record(native)["sha256"]}}, "scope": "test binding"}
    manifest = tmp_path / "prepared-modules.json"
    manifest.write_text(json.dumps(modules), encoding="utf-8")
    monkeypatch.setattr(context, "capture_modules", lambda engine: modules)
    config = {"schema_version": 2, "mode": "provided", "pdf_engine": "typst", "pdflatex": None,
              "python": {**record(Path(sys.executable)), "prefix": sys.prefix},
              "node": record(node), "pandoc": record(pandoc),
              "modules": record(manifest),
              "variables": {"MPLCONFIGDIR": str(cache)}}
    path = tmp_path / "host-environment.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path, config


def test_prepared_configuration_keeps_network_policy_and_selects_exact_tools(preparation, monkeypatch):
    path, config = preparation
    monkeypatch.setattr(context.os, "environ", {
        "PATH": "host-search-path", "ALL_PROXY": "fixture-proxy",
        "SSL_CERT_FILE": "fixture-certificate", "UNRELATED": "retained"})
    report = context.apply_prepared_host(path)
    assert report["environment_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert os.environ["PF_NODE_BIN"] == config["node"]["path"]
    assert os.environ["PYPANDOC_PANDOC"] == config["pandoc"]["path"]
    assert os.environ["ALL_PROXY"] == "fixture-proxy"
    assert os.environ["SSL_CERT_FILE"] == "fixture-certificate"
    assert os.environ["PATH"] == "host-search-path"
    assert os.environ["UNRELATED"] == "retained"
    assert os.environ["PF_HOST_MODE"] == "provided" and os.environ["PF_PDF_ENGINE"] == "typst"


@pytest.mark.parametrize("binary", ["node", "pandoc"])
def test_changed_tool_is_rejected_before_any_environment_mutation(preparation, monkeypatch, binary):
    path, config = preparation
    Path(config[binary]["path"]).write_bytes(b"changed")
    monkeypatch.setattr(context.os, "environ", {"PATH": "unchanged"})
    with pytest.raises(ValueError, match="bytes changed"):
        context.apply_prepared_host(path)
    assert os.environ == {"PATH": "unchanged"}


def test_wrong_interpreter_environment_is_rejected(preparation, tmp_path):
    path, config = preparation
    config["python"]["prefix"] = str(tmp_path)
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="selected Python"):
        context.apply_prepared_host(path)


def test_preparation_cannot_replace_proxy_or_path(preparation):
    path, config = preparation
    config["variables"]["PATH"] = "untrusted"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported environment"):
        context.apply_prepared_host(path)


@pytest.mark.parametrize("arguments", [[], ["--environment-file"],
    ["--environment-file", "--data"], ["--environment-file", "one", "--environment-file", "two"]])
def test_missing_or_ambiguous_preparation_is_rejected(arguments):
    with pytest.raises(ValueError):
        context.consume_environment_argument(arguments)


def test_launcher_consumes_only_the_preparation_argument():
    path, remaining = context.consume_environment_argument(
        ["--data", "research", "--environment-file", "prepared.json", "--runtime-root", "wasm", "environment"])
    assert path == "prepared.json"
    assert remaining == ["--data", "research", "--runtime-root", "wasm", "environment"]


def test_changed_native_module_is_rejected_before_environment_selection(preparation, monkeypatch):
    path, config = preparation
    modules = json.loads(Path(config['modules']['path']).read_bytes())
    Path(next(iter(modules['files']))).write_bytes(b'changed installed native bytes')
    monkeypatch.setattr(context.os, 'environ', {'ALL_PROXY': 'preserved', 'PF_HOST_MODE': 'private'})
    with pytest.raises(ValueError, match='module bytes changed'):
        context.apply_prepared_host(path)
    assert os.environ == {'ALL_PROXY': 'preserved', 'PF_HOST_MODE': 'private'}


def test_import_origin_change_is_rejected_and_temporary_cache_is_restored(preparation, monkeypatch):
    path, config = preparation
    actual = json.loads(Path(config['modules']['path']).read_bytes())
    actual['modules']['fixture'] = 'different installed module'
    monkeypatch.setattr(context, 'capture_modules', lambda _: actual)
    monkeypatch.setattr(context.os, 'environ', {'MPLCONFIGDIR': 'prior-cache', 'ALL_PROXY': 'preserved'})
    with pytest.raises(ValueError, match='module identities changed'):
        context.apply_prepared_host(path)
    assert os.environ == {'MPLCONFIGDIR': 'prior-cache', 'ALL_PROXY': 'preserved'}


def test_explicit_pdflatex_target_is_bound_and_typst_clears_stale_selection(preparation, monkeypatch, tmp_path):
    path, config = preparation
    engine = tmp_path / 'pdflatex'
    engine.write_bytes(b'provided TeX engine fixture')
    config.update(pdf_engine='pdflatex', pdflatex={'path': str(engine), 'target_path': str(engine.resolve()),
                                                 'sha256': hashlib.sha256(engine.read_bytes()).hexdigest()})
    path.write_text(json.dumps(config), encoding='utf-8')
    monkeypatch.setattr(context.os, 'environ', {'PATH': 'unchanged'})
    context.apply_prepared_host(path)
    assert os.environ['PF_PDFLATEX_BIN'] == str(engine) and os.environ['PF_PDF_ENGINE'] == 'pdflatex'
    config.update(pdf_engine='typst', pdflatex=None)
    path.write_text(json.dumps(config), encoding='utf-8')
    context.apply_prepared_host(path)
    assert 'PF_PDFLATEX_BIN' not in os.environ and os.environ['PATH'] == 'unchanged'


@pytest.mark.parametrize('field,value', [('mode', 'automatic'), ('schema_version', True), ('mode', ['provided'])])
def test_selected_host_format_rejects_implicit_or_malformed_modes(preparation, field, value):
    path, config = preparation
    config[field] = value
    path.write_text(json.dumps(config), encoding='utf-8')
    with pytest.raises(ValueError, match='format'):
        context.apply_prepared_host(path)

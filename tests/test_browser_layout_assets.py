"""Pure font-packet admission: no Electron, models, workflow, or SCI."""
import base64
import hashlib
import os

import pytest

from paper_factory.autonomous import browser_runner


def packet(tmp_path, fonts=None):
    source, bundle = tmp_path / "source", tmp_path / "bundle"
    source.mkdir(exist_ok=True)
    bundle.mkdir(exist_ok=True)
    (source / "original.js").write_text("window.J={measure(){return 1}};", encoding="utf-8")
    (bundle / "run.mjs").write_text("export default async function run(){return {}}", encoding="utf-8")
    return browser_runner.BrowserRunner._packet(None, source, bundle, source_order=["original.js"],
        production_entrypoint="original.js:J.measure", entrypoint="run.mjs", scientific_inputs={},
        timeout_seconds=10, browser_fonts=fonts)


def test_font_packet_binds_original_binary_bytes_without_newline_or_unicode_conversion(tmp_path):
    packet(tmp_path)
    raw = b"\x00\xff\x80\r\nfont packet fixture, not a runnable font"
    (tmp_path / "source/font.woff2").write_bytes(raw)
    before = (tmp_path / "source/font.woff2").read_bytes()
    result = packet(tmp_path, ["font.woff2"])
    assert result["fonts"] == {"font.woff2": {"content": base64.b64encode(raw).decode(),
        "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}}
    assert (tmp_path / "source/font.woff2").read_bytes() == before


def test_empty_font_packet_is_explicit_and_not_an_ambient_system_font_identity(tmp_path):
    assert packet(tmp_path)["fonts"] == {}


@pytest.mark.parametrize("fonts", [["../font.ttf"], ["C:/font.ttf"], ["font.exe"],
    ["font.ttf", "font.ttf"], "font.ttf", [False], [f"font-{i}.ttf" for i in range(9)]])
def test_font_packet_rejects_escape_format_duplicate_and_count_before_dispatch(tmp_path, fonts):
    with pytest.raises(ValueError):
        packet(tmp_path, fonts)


def test_font_packet_rejects_hard_linked_source_and_oversized_assets(tmp_path, monkeypatch):
    packet(tmp_path)
    source = tmp_path / "source"
    (source / "font.ttf").write_bytes(b"fixture")
    os.link(source / "font.ttf", source / "linked.ttf")
    with pytest.raises(ValueError, match="unlinked"):
        packet(tmp_path, ["font.ttf"])
    (source / "linked.ttf").unlink()
    monkeypatch.setitem(browser_runner.LIMITS, "font_bytes", 4)
    with pytest.raises(ValueError, match="bounded"):
        packet(tmp_path, ["font.ttf"])

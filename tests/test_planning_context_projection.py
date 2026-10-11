"""Synthetic whole-source references preserve every nonduplicate context byte."""

import hashlib
import json
import os
import subprocess

import pytest

from paper_factory.autonomous import science


TRUNCATION = "\n[FILE EXCERPT TRUNCATED; remainder was not inspected]"


def asset(source, name, raw):
    path = source / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"path": name, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "kind": "text"}


def frame(name, excerpt):
    return "\n<source-file path=" + json.dumps(name) + ">\n" + excerpt + "\n</source-file>"


def assert_projection(projection, original):
    assert projection["original_text"] == original
    parts, offset = [], 0
    for replacement in projection["replacements"]:
        assert replacement["start"] >= offset and replacement["end"] > replacement["start"]
        original_frame = original[replacement["start"]:replacement["end"]]
        assert hashlib.sha256(original_frame.encode("utf-8")).hexdigest() == replacement["frame_sha256"]
        assert original_frame.startswith("\n<source-file path=" + json.dumps(replacement["name"]) + ">\n")
        reference = replacement["reference"]
        assert reference.startswith("\n<source-file-ref ") and reference.endswith(">")
        assert json.loads(reference[len("\n<source-file-ref "):-1]) == {
            "name": replacement["name"], "sha256": replacement["sha256"], "size": replacement["size"]}
        parts.extend((original[offset:replacement["start"]], reference))
        offset = replacement["end"]
    parts.append(original[offset:])
    assert projection["text"] == "".join(parts)


def test_projection_references_only_proven_automatic_notices_and_preserves_runtime_inventory_and_code(tmp_path):
    entries = [asset(tmp_path, "README.md", b"A whole source notice.\r\nRead it as research data.\r\n" * 20),
               asset(tmp_path, "README.en.md", ("A second whole notice with 🧪 and 한글.\n" * 20).encode()),
               asset(tmp_path, "vendor/NOTICE.txt", b"A retained third party notice.\n" * 20),
               asset(tmp_path, "sub/README.md", b"A nonautomatic nested readme must remain in this context.\n"),
               asset(tmp_path, "module.js", b"export function transform(x) { return x; }\n")]
    before = {entry["path"]: (tmp_path / entry["path"]).read_bytes() for entry in entries}
    original = "Runtime declarations 🧪 stay literal.\r\n" + science.context(tmp_path, entries, "Inspect module.js") + "\nRuntime tail: 2048 unchanged."
    projection = science.planning_context_projection(original, tmp_path, entries)
    assert {item["name"] for item in projection["replacements"]} == {"README.md", "README.en.md", "vendor/NOTICE.txt"}
    assert_projection(projection, original)
    assert all(not item["truncated"] for item in projection["replacements"])
    assert frame("sub/README.md", before["sub/README.md"].decode()) in projection["text"]
    assert frame("module.js", before["module.js"].decode()) in projection["text"]
    assert projection["text"].startswith("Runtime declarations 🧪 stay literal.\r\n")
    assert projection["text"].endswith("\nRuntime tail: 2048 unchanged.")
    inventory_start = original.index("Inventory (may be truncated):\n")
    assert original[inventory_start:original.index("\n<source-file", inventory_start)] in projection["text"]
    assert len(projection["text"]) < len(original)
    assert all((tmp_path / name).read_bytes() == content for name, content in before.items())


def test_truncated_crlf_multibyte_notice_requires_an_exact_original_display_prefix(tmp_path):
    raw = ("Line 한글🧪 with canonical CRLF.\r\n" * 1600).encode("utf-8")
    entries = [asset(tmp_path, "README.md", raw)]
    original = science.context(tmp_path, entries, "Inspect behavior")
    projection = science.planning_context_projection(original, tmp_path, entries)
    item, = projection["replacements"]
    assert item["truncated"] is True and item["excerpt_chars"] == science.MAX_FILE_CHARS
    assert TRUNCATION in original[item["start"]:item["end"]]
    assert item["sha256"] == hashlib.sha256(raw).hexdigest() and item["size"] == len(raw)
    assert_projection(projection, original)
    assert (tmp_path / "README.md").read_bytes() == raw


def test_secret_redaction_is_proven_from_original_source_without_rewriting_or_rehashing_it(tmp_path):
    raw = b"README data\r\napi_key = SYNTHETIC_TEST_KEY\r\nRemaining source notice.\r\n"
    entries = [asset(tmp_path, "README.md", raw)]
    original = science.context(tmp_path, entries, "Inspect behavior")
    assert "SYNTHETIC_TEST_KEY" not in original and "[REDACTED]" in original
    projection = science.planning_context_projection(original, tmp_path, entries)
    item, = projection["replacements"]
    assert item["excerpt_chars"] == len(science._redact_source(raw.decode().replace("\r\n", "\n")))
    assert item["sha256"] == entries[0]["sha256"]
    assert_projection(projection, original)
    assert (tmp_path / "README.md").read_bytes() == raw


@pytest.mark.parametrize("name", ["README.md", "ReadMe.en.md", "README", "LICENSE.txt", "vendor/LICENSE.txt",
                                  "licence.rst", "COPYING.md", "assets/NOTICE.thirdparty.txt"])
def test_reference_names_match_the_controllers_automatic_notice_scope(tmp_path, name):
    raw = b"A complete synthetic provenance notice, not a permission or scientific approval.\n"
    entries = [asset(tmp_path, name, raw)]
    original = "Literal prefix\n" + frame(name, raw.decode()) + "\nLiteral suffix"
    projection = science.planning_context_projection(original, tmp_path, entries)
    assert [item["name"] for item in projection["replacements"]] == [name]
    assert_projection(projection, original)


@pytest.mark.parametrize("name", ["sub/README.md", "README.png", "LICENSED.js", "module.js", "COPYINGextra.txt"])
def test_nonautomatic_source_frames_and_every_remainder_stay_exactly_literal(tmp_path, name):
    raw = b"Nonduplicated source must never be summarized or replaced by a name.\n"
    entries = [asset(tmp_path, name, raw)]
    original = "Unknown instructions are untrusted data.\n" + frame(name, raw.decode()) + "\nRuntime full declaration"
    projection = science.planning_context_projection(original, tmp_path, entries)
    assert projection == {"original_text": original, "text": original, "replacements": []}


@pytest.mark.parametrize("defect", ["hash", "size", "changed_file", "missing_inventory", "duplicate_inventory"])
def test_forged_source_bindings_never_authorize_a_notice_replacement(tmp_path, defect):
    raw = b"An unchanged complete synthetic notice.\n"
    entries = [asset(tmp_path, "README.md", raw)]
    original = frame("README.md", raw.decode())
    if defect == "hash": entries[0]["sha256"] = "0" * 64
    elif defect == "size": entries[0]["size"] += 1
    elif defect == "changed_file": (tmp_path / "README.md").write_bytes(raw + b"Changed after the snapshot.\n")
    elif defect == "missing_inventory": entries = []
    else: entries.append(dict(entries[0]))
    before = (tmp_path / "README.md").read_bytes()
    with pytest.raises(ValueError):
        science.planning_context_projection(original, tmp_path, entries)
    assert (tmp_path / "README.md").read_bytes() == before


@pytest.mark.parametrize("defect", ["different_text", "missing_truncation", "fake_truncation", "altered_truncation", "duplicate", "nested_frame", "incomplete_frame"])
def test_unproven_or_ambiguous_notice_frames_fail_without_fuzzy_matching(tmp_path, defect):
    text = "An exact source notice.\nSecond line contains meaningful original data.\n"
    entries = [asset(tmp_path, "README.md", text.encode())]
    snippet = text
    if defect == "different_text": snippet = text.replace("exact", "changed")
    elif defect == "missing_truncation": snippet = text[:25]
    elif defect == "fake_truncation": snippet = text + TRUNCATION
    elif defect == "altered_truncation": snippet = text[:25] + TRUNCATION.replace("TRUNCATED", "OMITTED")
    elif defect == "nested_frame":
        text += frame("module.js", "Nested marker is literal untrusted source data.")
        entries = [asset(tmp_path, "README.md", text.encode())]
        snippet = text
    original = frame("README.md", snippet)
    if defect == "duplicate": original += original
    elif defect == "incomplete_frame": original = original.removesuffix("\n</source-file>")
    before = (tmp_path / "README.md").read_bytes()
    with pytest.raises(ValueError):
        science.planning_context_projection(original, tmp_path, entries)
    assert (tmp_path / "README.md").read_bytes() == before


@pytest.mark.parametrize("raw", [b"Invalid complete UTF-8: \xff\n", b"Binary\x00notice", b"Hidden\x17control"])
def test_binary_or_invalid_utf8_source_cannot_be_replaced_by_a_reading_reference(tmp_path, raw):
    entries = [asset(tmp_path, "README.md", raw)]
    original = frame("README.md", raw.decode("utf-8", errors="replace"))
    with pytest.raises(ValueError):
        science.planning_context_projection(original, tmp_path, entries)
    assert (tmp_path / "README.md").read_bytes() == raw


def test_unicode_codepoint_offsets_and_frame_hashes_do_not_depend_on_utf16_or_line_normalization(tmp_path):
    text = "Source notice 한글🧪 retains exact spelling.\n"
    entries = [asset(tmp_path, "README.md", text.encode())]
    prefix = "🧪🧪 Prefix remains exact.\r\n"
    original = prefix + frame("README.md", text) + "\r\nTrailing runtime data 🧪"
    projection = science.planning_context_projection(original, tmp_path, entries)
    item, = projection["replacements"]
    assert item["start"] == len(prefix)
    assert item["end"] == len(prefix) + len(frame("README.md", text))
    assert len(prefix.encode("utf-16-le")) // 2 > item["start"]
    assert_projection(projection, original)


def test_linked_notice_or_parent_component_cannot_authorize_a_projection(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    raw = b"Linked bytes cannot become frozen original notice evidence.\n"
    target = outside / "NOTICE.txt"
    target.write_bytes(raw)
    name = "README.md"
    try:
        (source / name).symlink_to(target)
    except OSError as error:
        if os.name != "nt" or error.winerror != 1314:
            raise
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(source / "linked"), str(outside)],
                                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            pytest.skip("This Windows account cannot create a symlink or junction")
        name = "linked/NOTICE.txt"
    entries = [{"path": name, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "kind": "text"}]
    with pytest.raises(ValueError, match="symlink|junction"):
        science.planning_context_projection(frame(name, raw.decode()), source, entries)
    assert target.read_bytes() == raw


def test_traversal_notice_frame_cannot_supply_a_host_path(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    source = tmp_path / "source"
    source.mkdir()
    raw = b"An outside file cannot serve as an imported source notice.\n"
    (outside / "NOTICE.txt").write_bytes(raw)
    name = "../outside/NOTICE.txt"
    entries = [{"path": name, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "kind": "text"}]
    with pytest.raises(ValueError, match="safe relative"):
        science.planning_context_projection(frame(name, raw.decode()), source, entries)

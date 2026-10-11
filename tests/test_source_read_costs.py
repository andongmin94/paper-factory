"""Exact planning costs on disposable source bytes; no model or science dispatch."""

import hashlib
import json
import subprocess

import pytest

from paper_factory.workflow import WorkflowError, _source_read_costs
from paper_factory.workspace import Workspace
from test_planned_claim_projection import COUNTERS, listed, retained_bytes
from test_workflow import protocol, setup


def source_workspace(tmp_path, contents):
    ws = Workspace.create(tmp_path / "workspace")
    inventory = []
    for name, raw in contents.items():
        path = ws.path("source") / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        inventory.append({"name": name, "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)})
    return ws, inventory


def test_costs_match_real_json_stringify_and_independent_codepoint_page_receipts(tmp_path):
    texts = ["", "plain ASCII", 'quotes " and backslash \\\r\n\t preserved', "한글 😀 𐐀 \u2028 \u2029",
             "x" * 31999 + "😀" + "\r\n" + '"\\', "😀" * 32001]
    contents = {f"source-{index}.js": text.encode("utf-8") for index, text in enumerate(texts)}
    ws, inventory = source_workspace(tmp_path, contents)
    actual = _source_read_costs(ws, inventory)
    script = """
const fs = require('node:fs'), crypto = require('node:crypto');
const items = JSON.parse(fs.readFileSync(0, 'utf8'));
const result = items.map(({row, text}) => {
  const points = Array.from(text), pages = [];
  for (let offset = 0; offset < points.length || (offset === 0 && !points.length); offset += 32000) {
    const page = points.slice(offset, offset + 32000).join('');
    const chars = Array.from(page).length;
    pages.push({offset, limit:32000, chars, size:Buffer.byteLength(page, 'utf8'),
      sha256:crypto.createHash('sha256').update(page, 'utf8').digest('hex'),
      nextOffset:offset + chars < points.length ? offset + chars : null});
  }
  return {...row, readable:true, total_chars:points.length,
    json_text_utf16:JSON.stringify(text).length,
    read_receipt_utf16:JSON.stringify({...row, totalChars:points.length, pages}).length};
});
process.stdout.write(JSON.stringify(result));
"""
    payload = [{"row": row, "text": text} for row, text in zip(inventory, texts)]
    result = subprocess.run(["node", "-e", script], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                            capture_output=True, check=True)
    assert actual == json.loads(result.stdout)
    assert actual[-1]["total_chars"] == 32001
    assert actual[-1]["json_text_utf16"] == 64004
    assert set(actual[0]) == {"name", "sha256", "size", "readable", "total_chars",
                             "json_text_utf16", "read_receipt_utf16"}


@pytest.mark.parametrize("raw", [b"\xff\xfe", b"valid UTF-8\x00binary", b"DEL\x7f", b"form\x0cfeed"])
def test_unreadable_assets_keep_exact_identity_without_text_costs(tmp_path, raw):
    ws, inventory = source_workspace(tmp_path, {"asset.woff2": raw})
    before = retained_bytes_at(ws.root)
    cost, = _source_read_costs(ws, inventory)
    assert cost == {**inventory[0], "readable": False, "total_chars": None,
                    "json_text_utf16": None, "read_receipt_utf16": None}
    assert retained_bytes_at(ws.root) == before


def retained_bytes_at(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("defect", ["same_size_changed_bytes", "wrong_size", "missing"])
def test_cost_projection_fails_closed_before_using_changed_source(tmp_path, defect):
    ws, inventory = source_workspace(tmp_path, {"original.js": b"original"})
    path = ws.path("source/original.js")
    if defect == "same_size_changed_bytes":
        path.write_bytes(b"modified")
    elif defect == "wrong_size":
        inventory[0]["size"] += 1
    else:
        path.unlink()
    before = retained_bytes_at(ws.root)
    with pytest.raises(WorkflowError) as denied:
        _source_read_costs(ws, inventory)
    assert denied.value.code == "ARTIFACT_CHANGED"
    assert retained_bytes_at(ws.root) == before


def test_created_and_proposed_full_costs_preserve_manifest_compact_reads_and_counts(setup):
    service, runner, identifier = setup
    for proposal in (None, protocol()):
        if proposal is not None:
            service.submit_proposal(identifier, proposal)
        service.status(identifier)  # Acquire the established empty lease before the byte baseline.
        before = retained_bytes(service, identifier)
        full = service.status(identifier)
        compact = service.status(identifier, include_materials=False)
        item, = listed(service)
        inventory = full["material_manifest"]["source"]
        costs = full["material_manifest"]["read_costs"]["source"]
        assert len(costs) == len(inventory) == 1
        assert [{key: cost[key] for key in ("name", "sha256", "size")} for cost in costs] == inventory
        assert all(set(row) == {"name", "sha256", "size"} for row in inventory)
        assert "material_manifest" not in compact and "material_manifest" not in item
        assert full["artifacts"] == compact["artifacts"] == item["artifacts"]
        assert tuple(full[name] for name in COUNTERS) == tuple(compact[name] for name in COUNTERS)
        assert service.status(identifier)["material_manifest"] == full["material_manifest"]
        assert retained_bytes(service, identifier) == before and runner.calls == 0


def test_full_status_rejects_source_tamper_without_state_or_scientific_writes(setup):
    service, runner, identifier = setup
    service.status(identifier)
    path = service._workspace(identifier).path("source/transform.js")
    original = path.read_bytes()
    path.chmod(0o644)  # Only this disposable frozen fixture is deliberately corrupted.
    path.write_bytes(original.replace(b"slice", b"splice"))
    before = retained_bytes(service, identifier)
    with pytest.raises(WorkflowError) as denied:
        service.status(identifier)
    assert denied.value.code == "ARTIFACT_CHANGED"
    assert retained_bytes(service, identifier) == before and runner.calls == 0

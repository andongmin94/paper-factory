"""Frozen collection JSON can be read without a new scientific operation."""

import hashlib
import json

import pytest

from paper_factory import workflow as native
from paper_factory.workflow import WorkflowError
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import write_json
from test_workflow import setup


COLLECTIONS = (
    ("redesign-question-evidence-collection", native.QUESTION_EVIDENCE_ROOT),
    ("redesign-question-search-repair-collection", native.SEARCH_REPAIR_ROOT),
)


def frozen_archive(setup, name, root):
    service, runner, identifier = setup
    ws = service._workspace(identifier)
    record = ws.latest("workflow", Workflow)
    record.proposal_attempt = 3
    record.study_literature_attempt = 2
    packet = {
        "queries": ["Synthetic immutable archive query"],
        "sources": [],
        "searches": [{"status": "failed", "attempted": True, "error": "SyntheticFailure"}],
        "warnings": ["Synthetic preserved UTF-8 archive 한🙂\r\n" * 1400],
        "scope": "An archival read is not primary evidence, inspection or scientific approval.",
    }
    path = ws.path(root + "/collection.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, packet)
    native._freeze(ws, record, name, path)
    service._save(ws, record)
    with service._operation(identifier):
        pass  # Initialize the ordinary operation lock before immutable-data snapshots.
    service.collector = lambda *args, **kwargs: pytest.fail("An archival read must not recollect evidence")
    return service, runner, identifier, ws, record, packet, path


def bytes_inventory(ws):
    return {path.relative_to(ws.root).as_posix(): path.read_bytes()
            for path in ws.root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("name,root", COLLECTIONS)
def test_frozen_comparison_collection_reads_exact_multipage_utf8_without_writes_or_attempts(setup, name, root):
    service, runner, identifier, ws, record, packet, path = frozen_archive(setup, name, root)
    original = path.read_bytes()
    before = bytes_inventory(ws)
    parts, offset, pages = [], 0, []
    while True:
        page = service.read_material(identifier, "evidence", name, offset=offset, limit=32000)
        assert page["research_id"] == identifier and page["area"] == "evidence" and page["name"] == name
        assert page["offset"] == offset and page["limit"] == 32000 and page["is_untrusted_data"] is True
        assert page["sha256"] == hashlib.sha256(original).hexdigest()
        assert page["total_chars"] == len(original.decode("utf-8"))
        assert len(page["text"]) == min(32000, page["total_chars"] - offset)
        parts.append(page["text"]); pages.append(page)
        if page["next_offset"] is None:
            break
        assert page["next_offset"] == offset + len(page["text"])
        offset = page["next_offset"]
    assert len(pages) > 1
    assert "".join(parts).encode("utf-8") == original
    assert json.loads("".join(parts)) == packet
    assert bytes_inventory(ws) == before
    assert ws.latest("workflow", Workflow) == record and runner.calls == 0


@pytest.mark.parametrize("name,root", COLLECTIONS)
@pytest.mark.parametrize("defect", ["same_size_bytes", "size", "missing"])
def test_frozen_comparison_collection_changed_original_fails_without_rebinding(setup, name, root, defect):
    service, runner, identifier, ws, record, _, path = frozen_archive(setup, name, root)
    frozen = record.artifacts[name].model_dump(mode="json")
    database = ws.path("records.sqlite3").read_bytes()
    original = path.read_bytes()
    if defect == "same_size_bytes":
        changed = original.replace(b"Synthetic", b"Forged___", 1)
        assert len(changed) == len(original) and changed != original
        path.write_bytes(changed)
    elif defect == "size":
        path.write_bytes(original + b" ")
    else:
        path.unlink()
    with pytest.raises(WorkflowError) as rejected:
        service.read_material(identifier, "evidence", name, limit=32000)
    assert rejected.value.code == "ARTIFACT_CHANGED"
    assert ws.path("records.sqlite3").read_bytes() == database
    assert ws.latest("workflow", Workflow).artifacts[name].model_dump(mode="json") == frozen
    assert runner.calls == 0


@pytest.mark.parametrize("name,root", COLLECTIONS)
def test_comparison_collection_whitelist_does_not_authorize_similarly_named_frozen_artifacts(setup, name, root):
    service, runner, identifier = setup
    ws = service._workspace(identifier)
    record = ws.latest("workflow", Workflow)
    unselected = name + "-copy"
    path = ws.path("research/synthetic-unselected-archive.json")
    write_json(path, {"scope": "Synthetic undeclared archival JSON must remain unavailable."})
    native._freeze(ws, record, unselected, path)
    service._save(ws, record)
    with service._operation(identifier):
        pass
    before = bytes_inventory(ws)
    with pytest.raises(WorkflowError) as rejected:
        service.read_material(identifier, "evidence", unselected)
    assert rejected.value.code == "MATERIAL_NOT_DECLARED"
    assert bytes_inventory(ws) == before and runner.calls == 0

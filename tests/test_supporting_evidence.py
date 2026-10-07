"""Supporting documents use temporary synthetic studies, never real execution."""

import base64
import hashlib
import io
import json
import re
from datetime import datetime
from types import SimpleNamespace
import zipfile

import pytest

from paper_factory import ipc, workflow as workflow_module
from paper_factory.autonomous.models import FrozenArtifact
from paper_factory.workflow import WorkflowError
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import Workspace, digest_file, write_json

from test_workflow import approve_study, retained_authoring_fixture, setup


FILE_LIMIT = 128 * 1024
TOTAL_LIMIT = 256 * 1024


def supplied(name="notes.md", content=b"# External notes\n"):
    return {"name": name, "contentBase64": base64.b64encode(content).decode("ascii")}


def workspace(service, research_id):
    return Workspace(service.root / research_id)


def retained_state(ws, research_id):
    record = ws.get("workflow", research_id, Workflow)
    root = ws.path("research/supporting-documents")
    return {
        "record": record.model_dump(mode="json"),
        "artifacts": {key: ws.path(value.path).read_bytes() for key, value in record.artifacts.items()},
        "supporting_files": {path.relative_to(root).as_posix(): path.read_bytes()
                             for path in root.rglob("*") if path.is_file()} if root.exists() else {},
        "supporting_directories": {path.relative_to(root).as_posix()
                                   for path in root.rglob("*") if path.is_dir()} if root.exists() else set(),
        "supporting_directory_exists": root.exists(),
    }


def forbid_execution(service, runner, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Supporting-document import dispatched science or authoring")

    monkeypatch.setattr(runner, "run", forbidden)
    monkeypatch.setattr(service, "start_experiment", forbidden)
    monkeypatch.setattr(service, "_analyze", forbidden)
    monkeypatch.setattr(service, "resume", forbidden)


def freeze_json(ws, record, key, value):
    path = ws.path(record.artifacts[key].path)
    write_json(path, value)
    record.artifacts[key] = FrozenArtifact(path=path.relative_to(ws.root).as_posix(),
                                           sha256=digest_file(path), size=path.stat().st_size)


@pytest.mark.parametrize("stage", ["created", "planned", "analyzed"])
@pytest.mark.parametrize("status", ["ready", "cancelled"])
def test_import_preserves_allowed_workflow_and_all_prior_artifacts(setup, monkeypatch, stage, status):
    service, runner, research_id = setup
    if stage == "planned":
        approve_study(service, research_id)
    elif stage == "analyzed":
        retained_authoring_fixture(service, research_id)
    ws = workspace(service, research_id)
    record = ws.get("workflow", research_id, Workflow)
    record.status = status
    if status == "cancelled":
        record.code = "CANCELLED"
        record.message = "Retained synthetic cancellation."
        record.cancellation_requested = True
    ws.save("workflow", record)
    before = retained_state(ws, research_id)
    forbid_execution(service, runner, monkeypatch)

    result = service.add_evidence(research_id, [supplied()])

    after = ws.get("workflow", research_id, Workflow)
    for field in ("status", "stage", "code", "message", "cancellation_requested",
                  "execution_attempt", "code_attempt", "draft_attempt"):
        assert getattr(after, field) == before["record"][field]
    assert result["status"] == status and result["stage"] == stage
    assert runner.calls == 0
    assert len(result["supporting_documents"]) == 1
    for key, content in before["artifacts"].items():
        assert ws.path(after.artifacts[key].path).read_bytes() == content
        assert after.artifacts[key].model_dump(mode="json") == before["record"]["artifacts"][key]


def test_import_retains_original_bytes_and_readable_hash_bound_receipt(setup):
    service, runner, research_id = setup
    originals = {"notes.MD": b"\xef\xbb\xbf# Notes\r\nA claimed 1999 timestamp.\t\r\n" + "한글🙂".encode(),
                 "reading.json": b'{ "timestamp": "1999-01-01", "source": "unverified" }\r\n',
                 "draft.txt": b"User supplied text.\n"}
    result = service.add_evidence(research_id, [supplied(name, content) for name, content in originals.items()])
    ws = workspace(service, research_id)
    record = ws.get("workflow", research_id, Workflow)
    documents = result["supporting_documents"]
    assert {item["name"] for item in documents} == set(originals)
    assert service.status(research_id)["supporting_documents"] == documents
    manifest = {item["name"]: item for item in result["material_manifest"]["evidence"]}
    for item in documents:
        identifier, content = item["id"], originals[item["name"]]
        assert re.fullmatch(r"supporting-document-[a-f0-9]{12}", identifier)
        assert item["sha256"] == hashlib.sha256(content).hexdigest()
        assert item["size"] == len(content)
        assert record.artifacts[identifier].path == f"research/supporting-documents/{identifier}/{item['name']}"
        assert service.artifact_path(research_id, identifier).read_bytes() == content
        assert manifest[identifier]["sha256"] == item["sha256"]
        assert manifest[identifier]["size"] == item["size"]
        pages, offset = [], 0
        while True:
            page = service.read_material(research_id, "evidence", identifier, offset=offset, limit=7)
            assert page["is_untrusted_data"] is True and page["sha256"] == item["sha256"]
            pages.append(page["text"])
            if page["next_offset"] is None:
                break
            offset = page["next_offset"]
        assert "".join(pages).encode("utf-8") == content

    receipts = [key for key in record.artifacts if re.fullmatch(r"supporting-document-import-[a-f0-9]{12}", key)]
    assert len(receipts) == 1
    identifier = receipts[0]
    receipt = json.loads(service.artifact_path(research_id, identifier).read_bytes())
    assert receipt["event"] == "supporting-document-import" and receipt["id"] == identifier
    assert datetime.fromisoformat(receipt["importedAt"]).tzinfo is not None
    assert receipt["stageAtImport"] == "created" and receipt["statusAtImport"] == "ready"
    assert receipt["executionAttempt"] == 0 and receipt["scope"] == "external-untrusted-content"
    assert "unverified claims" in receipt["provenance"]
    assert "not pre-experiment inspection" in receipt["provenance"]
    assert {item["originalName"] for item in receipt["documents"]} == set(originals)
    assert {item["id"] for item in receipt["documents"]} == {item["id"] for item in documents}
    assert {item["id"]: (item["originalName"], item["sha256"], item["size"])
            for item in receipt["documents"]} == {
                item["id"]: (item["name"], item["sha256"], item["size"]) for item in documents}
    assert identifier in manifest
    page = service.read_material(research_id, "evidence", identifier, limit=32000)
    assert json.loads(page["text"]) == receipt and page["is_untrusted_data"] is True
    assert runner.calls == 0


@pytest.mark.parametrize("files", [
    None, {}, "notes.md", [], [supplied() for _ in range(9)],
    [None], [{"name": "notes.md"}], [{"contentBase64": "YQ=="}],
    [{**supplied(), "path": "C:/private"}],
    [{"name": True, "contentBase64": "YQ=="}], [{"name": "notes.md", "contentBase64": 1}],
    [{"name": "notes.md", "contentBase64": ""}],
    [{"name": "notes.md", "contentBase64": "YQ==\n"}],
    [{"name": "notes.md", "contentBase64": "YQ"}],
    [{"name": "notes.md", "contentBase64": "YQ==="}],
    [{"name": "notes.md", "contentBase64": "YR=="}],
    [{"name": "notes.md", "contentBase64": "_w=="}],
    [{"name": "notes.md", "contentBase64": "한글"}],
    [supplied(content=b"\xff")], [supplied(content=b"valid\x00hidden")],
    [supplied(content=b"valid\x01hidden")], [supplied(content=b"valid\x7fhidden")],
    [supplied(content=b"x" * (FILE_LIMIT + 1))],
    [supplied("a.txt", b"a" * FILE_LIMIT), supplied("b.txt", b"b" * FILE_LIMIT), supplied("c.txt", b"c")],
])
def test_invalid_batch_is_rejected_before_any_mutation(setup, files):
    service, _, research_id = setup
    ws = workspace(service, research_id)
    before = retained_state(ws, research_id)
    # A valid first document must not be written before a later defect is found.
    batch = [supplied("first.txt"), *files] if isinstance(files, list) and files and len(files) < 8 else files
    with pytest.raises(ValueError):
        service.add_evidence(research_id, batch)
    assert retained_state(ws, research_id) == before


@pytest.mark.parametrize("name", [
    "../notes.md", "folder/notes.md", r"folder\notes.md", "/notes.md", "C:/notes.md", "notes:stream.md",
    "CON.md", "aux.TXT", "NUL.json", "COM1.md", "LPT9.txt", "notes.md.", "notes.md ",
    " notes.md", ".notes.md", "notes.pdf", "notes", "note?.md", "한글.md", "K.md", "İ.txt", "ſ.json", "ı.md",
    "x" * 121 + ".md",
])
def test_unsafe_names_leave_an_existing_import_unchanged(setup, name):
    service, _, research_id = setup
    service.add_evidence(research_id, [supplied("retained.txt")])
    ws = workspace(service, research_id)
    before = retained_state(ws, research_id)
    with pytest.raises(ValueError):
        service.add_evidence(research_id, [supplied("valid.md"), supplied(name)])
    assert retained_state(ws, research_id) == before


def test_each_byte_and_document_limit_is_inclusive_and_cumulative(setup):
    service, _, research_id = setup
    service.add_evidence(research_id, [supplied(f"small-{index}.md", b"x") for index in range(6)])
    remaining = TOTAL_LIMIT - 6
    result = service.add_evidence(research_id, [supplied("large-a.txt", b"a" * FILE_LIMIT),
                                              supplied("large-b.txt", b"b" * (remaining - FILE_LIMIT))])
    assert len(result["supporting_documents"]) == 8
    assert sum(item["size"] for item in result["supporting_documents"]) == TOTAL_LIMIT
    ws = workspace(service, research_id)
    before = retained_state(ws, research_id)
    with pytest.raises(ValueError):
        service.add_evidence(research_id, [supplied("ninth.md", b"x")])
    assert retained_state(ws, research_id) == before


def test_cumulative_byte_limit_rejects_before_document_count_limit(setup):
    service, _, research_id = setup
    service.add_evidence(research_id, [supplied("a.txt", b"a" * FILE_LIMIT),
                                      supplied("b.txt", b"b" * (FILE_LIMIT - 1))])
    ws = workspace(service, research_id)
    before = retained_state(ws, research_id)
    with pytest.raises(ValueError):
        service.add_evidence(research_id, [supplied("c.txt", b"xx")])
    assert retained_state(ws, research_id) == before


def test_cumulative_document_limit_rejects_small_ninth_document(setup):
    service, _, research_id = setup
    service.add_evidence(research_id, [supplied(f"note-{index}.md", b"x") for index in range(7)])
    result = service.add_evidence(research_id, [supplied("eighth.md", b"x")])
    assert len(result["supporting_documents"]) == 8
    assert sum(item["size"] for item in result["supporting_documents"]) == 8
    ws = workspace(service, research_id)
    before = retained_state(ws, research_id)
    with pytest.raises(ValueError):
        service.add_evidence(research_id, [supplied("ninth.md", b"x")])
    assert retained_state(ws, research_id) == before


@pytest.mark.parametrize("existing", [False, True])
def test_casefold_duplicate_names_are_rejected_without_overwriting(setup, existing):
    service, _, research_id = setup
    if existing:
        service.add_evidence(research_id, [supplied("Notes.MD", b"Original retained notes.")])
    ws = workspace(service, research_id)
    before = retained_state(ws, research_id)
    batch = [supplied("notes.md", b"Replacement.")] if existing else [supplied("Notes.MD"), supplied("notes.md")]
    with pytest.raises(ValueError):
        service.add_evidence(research_id, batch)
    assert retained_state(ws, research_id) == before


@pytest.mark.parametrize("conflict", ["artifact_id", "document_path", "receipt_path"])
def test_import_cannot_replace_existing_identifiers_or_bytes(setup, monkeypatch, conflict):
    service, _, research_id = setup
    imported = service.add_evidence(research_id, [supplied("retained.md")])
    ws = workspace(service, research_id)
    document_id = "supporting-document-000000000000"
    receipt_id = "supporting-document-import-000000000000"
    if conflict == "artifact_id":
        document_id = imported["supporting_documents"][0]["id"]
    else:
        relative = (f"research/supporting-documents/{document_id}/new.md" if conflict == "document_path"
                    else f"research/supporting-documents/{receipt_id}.json")
        path = ws.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"Existing bytes cannot be overwritten.\n")
    before = retained_state(ws, research_id)
    monkeypatch.setattr(workflow_module, "uid", lambda prefix:
                        receipt_id if prefix == "supporting-document-import" else document_id)
    with pytest.raises(WorkflowError):
        service.add_evidence(research_id, [supplied("new.md")])
    assert retained_state(ws, research_id) == before


@pytest.mark.parametrize("stage,status", [
    ("code_ready", "ready"), ("execute", "running"), ("manuscript", "ready"), ("exported", "completed"),
    ("created", "running"), ("created", "blocked"), ("planned", "failed"), ("analyzed", "blocked"),
])
def test_unavailable_workflow_states_cannot_import(setup, stage, status):
    service, _, research_id = setup
    ws = workspace(service, research_id)
    record = ws.get("workflow", research_id, Workflow)
    record.stage, record.status = stage, status
    ws.save("workflow", record)
    before = retained_state(ws, research_id)
    with pytest.raises(WorkflowError):
        service.add_evidence(research_id, [supplied()])
    assert retained_state(ws, research_id) == before


@pytest.mark.parametrize("defect", ["terminal_control", "active_handle", "cleanup_code", "tampered_context"])
def test_existing_integrity_and_terminal_guards_apply_before_import(setup, defect):
    service, _, research_id = setup
    ws = workspace(service, research_id)
    record = ws.get("workflow", research_id, Workflow)
    if defect == "terminal_control":
        record.terminal_control_failure = True
    elif defect == "active_handle":
        record.active_handle = {"kind": "fixture", "pid": 123}
    elif defect == "cleanup_code":
        record.code = "CLEANUP_UNCONFIRMED"
    else:
        ws.path(record.artifacts["context"].path).write_bytes(b"Changed retained context.")
    ws.save("workflow", record)
    before = retained_state(ws, research_id)
    try:
        with pytest.raises(WorkflowError):
            service.add_evidence(research_id, [supplied()])
        assert retained_state(ws, research_id) == before
    finally:
        if defect == "active_handle":
            record.active_handle = {}
            ws.save("workflow", record)


@pytest.mark.parametrize("defect", ["failed_execution", "cleanup", "cleanup_hash", "raw", "analysis", "missing_raw", "missing_analysis"])
def test_analyzed_import_requires_successful_unchanged_execution_and_cleanup(setup, monkeypatch, defect):
    service, runner, research_id = setup
    ws = retained_authoring_fixture(service, research_id)
    record = ws.get("workflow", research_id, Workflow)
    if defect in {"failed_execution", "cleanup", "cleanup_hash"}:
        execution = json.loads(ws.path(record.artifacts["execution"].path).read_bytes())
        if defect == "failed_execution":
            execution["status"] = "failed"
        else:
            execution["cleanup_confirmed"] = False
        freeze_json(ws, record, "execution", execution)
        if defect == "cleanup_hash":
            cleanup = ws.path("research/cleanup-fixture.json")
            write_json(cleanup, {"confirmed": True, "execution_sha256": "0" * 64})
            record.artifacts["cleanup-1"] = FrozenArtifact(path=cleanup.relative_to(ws.root).as_posix(),
                                                          sha256=digest_file(cleanup), size=cleanup.stat().st_size)
    elif defect in {"missing_raw", "missing_analysis"}:
        del record.artifacts["observations" if defect == "missing_raw" else "analysis"]
    else:
        key = "observations" if defect == "raw" else "analysis"
        ws.path(record.artifacts[key].path).write_bytes(b"{}")
    ws.save("workflow", record)
    before = retained_state(ws, research_id)
    forbid_execution(service, runner, monkeypatch)
    with pytest.raises(WorkflowError):
        service.add_evidence(research_id, [supplied()])
    assert retained_state(ws, research_id) == before and runner.calls == 0


def test_analyzed_import_accepts_hash_bound_reconciled_cleanup_without_resuming(setup, monkeypatch):
    service, runner, research_id = setup
    ws = retained_authoring_fixture(service, research_id)
    record = ws.get("workflow", research_id, Workflow)
    execution = json.loads(ws.path(record.artifacts["execution"].path).read_bytes())
    execution["cleanup_confirmed"] = False
    freeze_json(ws, record, "execution", execution)
    cleanup = ws.path("research/cleanup-fixture.json")
    write_json(cleanup, {"confirmed": True, "execution_sha256": record.artifacts["execution"].sha256})
    record.artifacts["cleanup-1"] = FrozenArtifact(path=cleanup.relative_to(ws.root).as_posix(),
                                                  sha256=digest_file(cleanup), size=cleanup.stat().st_size)
    record.status, record.code, record.cancellation_requested = "cancelled", "CANCELLED", True
    ws.save("workflow", record)
    forbid_execution(service, runner, monkeypatch)
    result = service.add_evidence(research_id, [supplied()])
    assert result["status"] == "cancelled" and result["stage"] == "analyzed"
    assert result["code"] == "CANCELLED" and result["cancellation_requested"] is True
    assert result["execution_attempt"] == 1 and runner.calls == 0


def test_reproduction_zip_retains_documents_receipts_and_original_science(setup, monkeypatch):
    service, runner, research_id = setup
    ws = retained_authoring_fixture(service, research_id)
    forbid_execution(service, runner, monkeypatch)
    originals = {"notes.md": b"# Supplied notes\r\n", "claims.json": b'{ "claim": "unverified" }\n'}
    result = service.add_evidence(research_id, [supplied(name, content) for name, content in originals.items()])
    record = ws.get("workflow", research_id, Workflow)
    before = {key: ws.path(record.artifacts[key].path).read_bytes() for key in ("plan", "observations", "analysis")}
    source = ws.path("source/transform.js").read_bytes()
    for key in ("canonical", "export-md", "export-pdf", "export-docx", "export-tex", "conversion", "manuscript-review"):
        path = ws.path(f"research/{key}-archive-fixture.txt")
        path.write_bytes(b"Unexecuted synthetic archive fixture.\n")
        record.artifacts[key] = FrozenArtifact(path=path.relative_to(ws.root).as_posix(),
                                               sha256=digest_file(path), size=path.stat().st_size)
    root = ws.path("research/exports/supporting-fixture")
    root.mkdir(parents=True)
    service._bundle(ws, record, root)
    with zipfile.ZipFile(root / "reproducibility.zip") as archive:
        assert archive.testzip() is None
        inventory = json.loads(archive.read("inventory.json"))
        assert archive.read("source/transform.js") == source
        for key, member in (("plan", "protocol.json"), ("observations", "observations.json"), ("analysis", "analysis.json")):
            assert archive.read(member) == before[key]
        for item in result["supporting_documents"]:
            member = f"supporting-documents/{item['id']}/{item['name']}"
            content = originals[item["name"]]
            assert archive.read(member) == content
            assert inventory[member] == {"sha256": item["sha256"], "size": len(content)}
        for key in record.artifacts:
            if re.fullmatch(r"supporting-document-import-[a-f0-9]{12}", key):
                member = f"supporting-documents/imports/{key}.json"
                content = ws.path(record.artifacts[key].path).read_bytes()
                assert archive.read(member) == content
                assert inventory[member] == {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
        assert len(archive.namelist()) == len(set(archive.namelist()))
    assert runner.calls == 0


def test_add_evidence_ipc_accepts_only_declared_shape_and_maps_to_service():
    research_id = "research-abcdefabcdef"
    files = [supplied()]
    valid = {"id": "import", "method": "workflow.addEvidence", "params": {"researchId": research_id, "files": files}}
    assert ipc.request(json.dumps(valid).encode()) == valid
    for params in ({}, {"researchId": research_id}, {"files": files},
                   {"researchId": "../private", "files": files},
                   {"researchId": research_id, "files": files, "path": "C:/private"},
                   {"researchId": research_id, "files": None},
                   {"researchId": research_id, "files": []},
                   {"researchId": research_id, "files": files * 9},
                   {"researchId": research_id, "files": [{**files[0], "path": "C:/private"}]},
                   {"researchId": research_id, "files": [{"name": "notes.md", "contentBase64": True}]}):
        with pytest.raises(ValueError):
            ipc.request(json.dumps({**valid, "params": params}).encode())
    calls = []
    service = SimpleNamespace(add_evidence=lambda identifier, documents:
                              calls.append((identifier, documents)) or {"supporting_documents": [{"name": "notes.md"}]})
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), io.BytesIO())
    try:
        assert dispatcher.execute(valid["method"], valid["params"]) == {"supporting_documents": [{"name": "notes.md"}]}
        assert calls == [(research_id, files)]
    finally:
        dispatcher._pool.shutdown(wait=True)

"""Synthetic retained-body paging contracts; no network or scientific execution."""

import copy
import hashlib

import pytest

import paper_factory.workflow as workflow
from paper_factory.autonomous import literature
from paper_factory.workflow import WorkflowError, _freeze
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import digest_file, write_json
from test_autonomous_literature import clock
from test_retained_primary_literature import preprint, revise
from test_unicode_report_workflow import initial as standard
from test_workflow import SYNTHETIC_PREFIX, SYNTHETIC_SUFFIX, rejected_study_review, setup


def replace_packet(service, identifier, key, packet):
    """Publish a synthetic current packet without changing its frozen originals."""
    with service._operation(identifier) as (ws, record):
        folder = ws.path("research/material-reading-fixtures")
        folder.mkdir(exist_ok=True)
        path = folder / (key + "-" + hashlib.sha256(str(packet).encode()).hexdigest() + ".json")
        write_json(path, packet)
        _freeze(ws, record, key, path)
        service._save(ws, record)


@pytest.fixture
def body(setup):
    service, runner, identifier = setup
    state = preprint(service, identifier)
    return service, runner, identifier, state


def test_current_body_manifest_resolves_original_retained_key_and_pages_all_text(body):
    service, runner, identifier, state = body
    source, = state["literature"]["sources"]
    entry, = state["material_manifest"]["literature"]
    path = service._workspace(identifier).path("research/" + source["text_path"])
    assert "-retained-" in entry["name"]
    assert entry == {"name": entry["name"], "source_id": source["id"], "title": source["title"],
                     "sha256": source["text_sha256"], "size": path.stat().st_size,
                     "body_range": source["body_range"]}
    assert entry["name"] not in {row["name"] for row in state["material_manifest"]["evidence"]}
    parts, offset = [], 0
    while True:
        page = service.read_material(identifier, "evidence", entry["name"], offset=offset, limit=19)
        assert page["sha256"] == entry["sha256"] and page["is_untrusted_data"] is True
        parts.append(page["text"])
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    assert "".join(parts).encode("utf-8") == path.read_bytes()
    assert page["total_chars"] == len(path.read_bytes().decode("utf-8"))
    assert runner.calls == 0


def test_current_authoring_body_is_exposed_without_history_and_identical_entry_is_deduplicated(body):
    service, runner, identifier, state = body
    replace_packet(service, identifier, "authoring-literature", state["literature"])
    assert service.status(identifier)["material_manifest"]["literature"] == state["material_manifest"]["literature"]
    with service._operation(identifier) as (ws, record):
        previous = record.artifacts.pop("literature")
        record.artifacts["literature-history-" + previous.sha256] = previous
        service._save(ws, record)
    entry, = service.status(identifier)["material_manifest"]["literature"]
    assert service.read_material(identifier, "evidence", entry["name"])["sha256"] == entry["sha256"]
    assert runner.calls == 0


def test_same_frozen_text_cannot_claim_conflicting_current_source_identities(body):
    service, runner, identifier, state = body
    packet = copy.deepcopy(state["literature"])
    packet["sources"][0]["id"] = "different-synthetic-source"
    replace_packet(service, identifier, "authoring-literature", packet)
    with pytest.raises(WorkflowError, match="conflicting") as rejected:
        service.status(identifier)
    assert rejected.value.code == "PUBLICATION_EVIDENCE_INVALID" and runner.calls == 0


def test_history_raw_metadata_and_unselected_retained_text_are_not_readable(body):
    service, runner, identifier, state = body
    entry, = state["material_manifest"]["literature"]
    for name in state["artifacts"]:
        if name.startswith("literature-") and name != entry["name"]:
            with pytest.raises(WorkflowError) as rejected:
                service.read_material(identifier, "evidence", name)
            assert rejected.value.code == "MATERIAL_NOT_DECLARED"
    revise(service, identifier, state, ["a different synthetic literature query"])
    assert service.status(identifier)["material_manifest"]["literature"] == []
    with pytest.raises(WorkflowError) as rejected:
        service.read_material(identifier, "evidence", entry["name"])
    assert rejected.value.code == "MATERIAL_NOT_DECLARED" and runner.calls == 0


@pytest.mark.parametrize("defect", ["abstract", "metadata_only", "body", "missing_body", "excerpt", "identity", "host_path"])
def test_unverified_current_source_is_not_advertised_or_readable(body, defect):
    service, runner, identifier, state = body
    packet = copy.deepcopy(state["literature"])
    source = packet["sources"][0]
    if defect in {"abstract", "metadata_only"}:
        source["scope"] = defect
    elif defect == "body":
        source["body_range"]["start"] += 1
    elif defect == "missing_body":
        source["body_range"] = None
    elif defect == "excerpt":
        source["excerpts"][0] = "Invented synthetic passage that does not exist in frozen body text. " * 3
    elif defect == "identity":
        source["title"] = "Different title from exact frozen metadata"
    else:
        source["text_path"] = "C:/Users/private.txt"
    replace_packet(service, identifier, "literature", packet)
    assert service.status(identifier)["material_manifest"]["literature"] == []
    name = state["material_manifest"]["literature"][0]["name"]
    with pytest.raises(WorkflowError) as rejected:
        service.read_material(identifier, "evidence", name)
    assert rejected.value.code == "MATERIAL_NOT_DECLARED" and runner.calls == 0


def test_missing_native_binding_does_not_advertise_or_read_body(body):
    service, runner, identifier, state = body
    name = state["material_manifest"]["literature"][0]["name"]
    with service._operation(identifier) as (ws, record):
        del record.artifacts[name]
        service._save(ws, record)
    assert service.status(identifier)["material_manifest"]["literature"] == []
    with pytest.raises(WorkflowError) as rejected:
        service.read_material(identifier, "evidence", name)
    assert rejected.value.code == "MATERIAL_NOT_DECLARED" and runner.calls == 0


@pytest.mark.parametrize("field", ["raw_path", "metadata_path", "text_path"])
def test_tampered_originals_fail_before_body_reading(body, field):
    service, runner, identifier, state = body
    source = state["literature"]["sources"][0]
    path = service._workspace(identifier).path("research/" + source[field])
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(WorkflowError) as rejected:
        service.read_material(identifier, "evidence", state["material_manifest"]["literature"][0]["name"])
    assert rejected.value.code == "ARTIFACT_CHANGED" and runner.calls == 0


@pytest.mark.parametrize("name", ["../records.sqlite3", "C:/Users/private.txt", "/private.txt", "literature-invented-text_path"])
def test_body_reader_does_not_accept_host_paths_or_guessed_keys(body, name):
    service, runner, identifier, state = body
    with pytest.raises(WorkflowError) as rejected:
        service.read_material(identifier, "evidence", name)
    assert rejected.value.code == "MATERIAL_NOT_DECLARED" and runner.calls == 0


@pytest.mark.parametrize("offset,limit", [(-1, 10), (True, 10), (0, False), (0, 0), (0, 32001), (0.5, 10)])
def test_body_paging_preserves_exact_integer_32k_limit(body, offset, limit):
    service, runner, identifier, state = body
    with pytest.raises(ValueError, match="paging"):
        service.read_material(identifier, "evidence", state["material_manifest"]["literature"][0]["name"],
                              offset=offset, limit=limit)
    assert runner.calls == 0


def test_body_paging_keeps_utf8_non_bmp_crlf_and_32k_pages(setup):
    service, runner, identifier = setup
    text = SYNTHETIC_PREFIX + ("한🙂\r\n" * 18000) + SYNTHETIC_SUFFIX

    def mutate(packet, root):
        source = packet["sources"][0]
        path = root / source["text_path"]
        path.write_bytes(text.encode("utf-8"))
        source.update(text_sha256=digest_file(path), text_chars=len(text),
                      body_range=literature.full_text_body_range(text),
                      excerpts=[text[len(SYNTHETIC_PREFIX):len(SYNTHETIC_PREFIX) + 100]],
                      excerpt_ranges=[{"start": len(SYNTHETIC_PREFIX), "end": len(SYNTHETIC_PREFIX) + 100}])

    state = preprint(service, identifier, mutate=mutate)
    entry, = state["material_manifest"]["literature"]
    first = service.read_material(identifier, "evidence", entry["name"], limit=32000)
    assert first["text"] == text[:32000] and first["next_offset"] == 32000
    second = service.read_material(identifier, "evidence", entry["name"], offset=first["next_offset"], limit=32000)
    last = service.read_material(identifier, "evidence", entry["name"], offset=second["next_offset"], limit=32000)
    assert first["text"] + second["text"] + last["text"] == text
    assert last["next_offset"] is None and last["total_chars"] == len(text)
    assert last["sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest() and runner.calls == 0


def test_verified_body_reader_preserves_literal_controls_without_normalizing(setup):
    service, runner, identifier = setup

    def mutate(packet, root):
        source = packet["sources"][0]
        path = root / source["text_path"]
        text = path.read_bytes().decode("utf-8").replace("\nReferences", "\x00\nReferences")
        path.write_bytes(text.encode("utf-8"))
        source.update(text_sha256=digest_file(path), text_chars=len(text),
                      body_range=literature.full_text_body_range(text))

    state = preprint(service, identifier, mutate=mutate)
    entry, = state["material_manifest"]["literature"]
    page = service.read_material(identifier, "evidence", entry["name"], limit=32000)
    expected = service._workspace(identifier).path("research/" + state["literature"]["sources"][0]["text_path"]).read_bytes()
    assert "\x00" in page["text"] and page["text"].encode("utf-8") == expected
    assert page["sha256"] == hashlib.sha256(expected).hexdigest() and runner.calls == 0


def test_current_literal_body_controls_unicode_and_pages_round_trip_exactly(setup):
    service, runner, identifier = setup
    text = SYNTHETIC_PREFIX + ("한🙂\r\n\x17\x00\x7f" * 12000) + SYNTHETIC_SUFFIX

    def mutate(packet, root):
        source = packet["sources"][0]
        path = root / source["text_path"]
        path.write_bytes(text.encode("utf-8"))
        source.update(text_sha256=digest_file(path), text_chars=len(text),
                      body_range=literature.full_text_body_range(text),
                      excerpts=[text[len(SYNTHETIC_PREFIX):len(SYNTHETIC_PREFIX) + 100]],
                      excerpt_ranges=[{"start": len(SYNTHETIC_PREFIX), "end": len(SYNTHETIC_PREFIX) + 100}])

    state = preprint(service, identifier, mutate=mutate)
    entry, = state["material_manifest"]["literature"]
    ws = service._workspace(identifier)
    record = ws.get("workflow", identifier, Workflow)
    before = {key: ws.path(value.path).read_bytes() for key, value in record.artifacts.items()}
    fragments, offset, pages = [], 0, []
    while offset is not None:
        page = service.read_material(identifier, "evidence", entry["name"], offset=offset, limit=32000)
        assert page["text"] == text[offset:offset + 32000]
        assert page["total_chars"] == len(text) and page["sha256"] == entry["sha256"]
        assert page["research_id"] == identifier and page["area"] == "evidence" and page["name"] == entry["name"]
        assert page["offset"] == offset and page["limit"] == 32000 and page["is_untrusted_data"] is True
        fragments.append(page["text"]); pages.append(page)
        offset = page["next_offset"]
    assert len(pages) >= 3 and "".join(fragments).encode("utf-8") == text.encode("utf-8")
    assert before == {key: ws.path(value.path).read_bytes() for key, value in record.artifacts.items()}
    after = service.status(identifier)
    for name in ("proposal_attempt", "study_literature_attempt", "code_attempt", "execution_attempt", "draft_attempt", "redesign_attempt"):
        assert after[name] == state[name]
    assert after["artifacts"] == state["artifacts"] and runner.calls == 0
    revise(service, identifier, state, ["Different synthetic primary query without old text selection"])
    with pytest.raises(WorkflowError) as denied:
        service.read_material(identifier, "evidence", entry["name"])
    assert denied.value.code == "MATERIAL_NOT_DECLARED"


@pytest.mark.parametrize("area", ["experiment", "evidence"])
def test_literal_primary_exception_does_not_allow_other_declared_binary_material(setup, area):
    service, runner, identifier = setup
    with service._operation(identifier) as (ws, record):
        root = ws.path("research/binary-material-fixture"); root.mkdir()
        path = root / "binary.mjs"; path.write_bytes(b"declared but binary\x00\x17\x7f")
        if area == "experiment":
            bundle = root / "bundle.json"
            write_json(bundle, {"files": [{"path": "binary.mjs", "sha256": digest_file(path), "size": path.stat().st_size}]})
            write_json(root / "review.json", {})
            _freeze(ws, record, "bundle", bundle)
            name = "binary.mjs"
        else:
            _freeze(ws, record, "manuscript", path)
            name = "manuscript"
        service._save(ws, record)
    with pytest.raises(WorkflowError) as denied:
        service.read_material(identifier, area, name)
    assert denied.value.code == "MATERIAL_NOT_TEXT" and runner.calls == 0


def test_invalid_utf8_extracted_text_is_not_a_verified_readable_primary(setup):
    service, runner, identifier = setup

    def mutate(packet, root):
        source = packet["sources"][0]
        path = root / source["text_path"]
        path.write_bytes(path.read_bytes() + b"\xff")
        source["text_sha256"] = digest_file(path)

    state = preprint(service, identifier, mutate=mutate)
    source, = state["literature"]["sources"]
    assert state["material_manifest"]["literature"] == []
    record = service._workspace(identifier).get("workflow", identifier, Workflow)
    name = next(name for name, artifact in record.artifacts.items() if artifact.path == "research/" + source["text_path"])
    with pytest.raises(WorkflowError) as denied:
        service.read_material(identifier, "evidence", name)
    assert denied.value.code == "MATERIAL_NOT_DECLARED" and runner.calls == 0


def test_standard_body_uses_existing_original_dom_identity_and_offsets(setup, monkeypatch, clock):
    service, runner, identifier, state = standard(setup, monkeypatch)
    source, = state["literature"]["sources"]
    entry, = state["material_manifest"]["literature"]
    page = service.read_material(identifier, "evidence", entry["name"], offset=entry["body_range"]["start"], limit=32000)
    text = service._workspace(identifier).path("research/" + source["text_path"]).read_bytes().decode("utf-8")
    assert page["text"] == text[page["offset"]:page["offset"] + 32000]
    assert entry["sha256"] == source["text_sha256"] and entry["body_range"] == source["body_range"]
    packet = copy.deepcopy(state["literature"])
    packet["sources"][0]["body_range"]["start"] = False
    replace_packet(service, identifier, "literature", packet)
    assert service.status(identifier)["material_manifest"]["literature"] == []
    with pytest.raises(WorkflowError) as rejected:
        service.read_material(identifier, "evidence", entry["name"])
    assert rejected.value.code == "MATERIAL_NOT_DECLARED"
    assert runner.calls == 0


def test_reading_preserves_old_reviews_excerpts_artifacts_and_all_attempt_counts(body):
    service, runner, identifier, state = body
    service.submit_study_review(identifier, rejected_study_review())
    before = service.status(identifier)
    originals = {name: service.artifact_path(identifier, name).read_bytes() for name in before["artifacts"]}
    entry, = before["material_manifest"]["literature"]
    service.read_material(identifier, "evidence", entry["name"], limit=32000)
    after = service.status(identifier)
    assert after == before
    assert all(service.artifact_path(identifier, name).read_bytes() == data for name, data in originals.items())
    assert after["literature"]["sources"] == state["literature"]["sources"]
    assert (after["proposal_attempt"], after["study_literature_attempt"], after["execution_attempt"], after["draft_attempt"]) == (1, 0, 0, 0)
    assert runner.calls == 0


def test_lightweight_status_does_not_compute_literature_materials(body, monkeypatch):
    service, runner, identifier, state = body

    def forbidden(*args):
        pytest.fail("Lightweight status must not resolve or validate literature body manifests")

    monkeypatch.setattr(workflow, "_literature_materials", forbidden)
    compact = service.status(identifier, include_materials=False)
    assert "material_manifest" not in compact and compact["execution_attempt"] == 0 and runner.calls == 0

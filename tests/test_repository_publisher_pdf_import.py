"""Whole supplied publisher PDFs retain their five original proof bindings and text."""

import copy
import hashlib
import json

import pytest

from paper_factory.autonomous import literature
from paper_factory.workflow import WorkflowError, WorkflowService, _freeze, _retained_primary_body, _verified_repository_pdf
from paper_factory.workflow_models import Workflow
from paper_factory.workspace import Workspace
from test_autonomous_literature import clock
from test_publisher_pdf import HINT, TITLE, collection


def complete_pdf():
    """Small valid PDF fixture, with real extractable identity and scientific body."""
    lines = [TITLE, "Ada Lovelace, Grace Hopper", "USENIX 2024", "Abstract",
             "This synthetic PDF tests provenance, not an actual research result.", "1 Introduction"]
    lines += [f"Synthetic bounded source comparison row {number} retains explicit assumptions." for number in range(12)]
    lines += ["2 Methods", "Complete source paths and counterexamples are retained without observed execution.",
              "References", "A bibliography does not establish inspection of another body."]
    stream = "BT /F1 10 Tf 11 TL 20 780 Td\n" + "\n".join("(" + line + ") Tj T*" for line in lines) + "\nET"
    data = stream.encode("ascii")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(data)).encode() + b" >>\nstream\n" + data + b"\nendstream"]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, item in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += str(number).encode() + b" 0 obj\n" + item + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 6\n0000000000 65535 f \n"
    pdf += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    pdf += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(pdf)


@pytest.fixture
def imported(tmp_path, monkeypatch, clock):
    raw = complete_pdf()
    text = literature._extract_pdf(raw)
    bounded_extract = literature._pdf_text
    origin = tmp_path / "captured-publisher"
    origin.mkdir()
    packet, requests = collection(monkeypatch, origin, raw=raw, text=text)
    assert len(requests) == 2  # Both requests use the synthetic HTTP transport.
    monkeypatch.setattr(literature, "_pdf_text", bounded_extract)
    source, = packet["sources"]
    assert source["scope"] == "full_text" and source["page_count"] == 1
    ws = Workspace.create(tmp_path / "temporary-study")
    record = Workflow(project_id="synthetic", goal="Supplied publisher import contract only")
    files, members, originals = {}, [], {}
    for field in ("raw_path", "metadata_path", "text_path", "discovery_path", "identity_path"):
        raw = (origin / source[field]).read_bytes()
        path = ws.path("research/supplied-publisher/files/" + field + (".pdf" if field == "raw_path" else ".txt"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        key = "repository-portfolio-supplement-1-" + field
        _freeze(ws, record, key, path)
        frozen = record.artifacts[key]
        files[source[field]] = {"artifact_id": key, "sha256": frozen.sha256, "size": frozen.size}
        members.append({"name": path.name, "original_path": source[field], **files[source[field]]})
        originals[key] = raw
    material = {"id": source["id"], "kind": "primary_body", "name": "text_path.txt", "sha256": source["text_sha256"],
        "title": source["title"], "url": source["url"], "provenance": "supplied_primary_copy",
        "primary_source": source, "primary_proof": {"pdf_hint_attempts": copy.deepcopy(packet["pdf_hint_attempts"])}}
    return ws, record, source, packet, files, members, material, originals


def test_whole_publisher_copy_reverifies_actual_extraction_without_changing_origin_or_counts(imported):
    ws, record, source, packet, files, members, material, originals = imported
    before = record.model_dump(mode="json")
    assert not ws.path("research/" + source["raw_path"]).exists()
    assert _verified_repository_pdf(ws, source, [HINT], record=record, imported_files=files)
    assert _retained_primary_body(ws, record, source, packet, imported_files=files)
    assert WorkflowService._portfolio_verify_supplement_primary(ws, record, material, members)
    assert record.model_dump(mode="json") == before
    assert all(ws.path(record.artifacts[key].path).read_bytes() == raw for key, raw in originals.items())


@pytest.mark.parametrize("defect", ["missing_member", "extra_member", "wrong_sha", "wrong_size", "wrong_artifact", "raw_bytes"])
def test_import_requires_exact_registered_five_original_byte_bindings(imported, defect):
    ws, record, source, packet, files, _, _, _ = imported
    files = copy.deepcopy(files)
    member = files[source["raw_path"]]
    if defect == "missing_member": files.pop(source["metadata_path"])
    elif defect == "extra_member": files["literature/extra.pdf"] = copy.deepcopy(member)
    elif defect == "wrong_sha": member["sha256"] = "0" * 64
    elif defect == "wrong_size": member["size"] += 1
    elif defect == "wrong_artifact": member["artifact_id"] = files[source["text_path"]]["artifact_id"]
    else:
        path = ws.path(record.artifacts[member["artifact_id"]].path)
        path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(WorkflowError) as error:
        _retained_primary_body(ws, record, source, packet, imported_files=files)
    assert error.value.code in {"PUBLICATION_EVIDENCE_INVALID", "ARTIFACT_CHANGED"}


def rewrite(imported, field, data):
    ws, record, source, _, files, _, _, _ = imported
    member = files[source[field]]
    path = ws.path(record.artifacts[member["artifact_id"]].path)
    path.write_bytes(data)
    _freeze(ws, record, member["artifact_id"], path)
    digest_field = {"text_path": "text_sha256", "identity_path": "identity_sha256"}[field]
    source[digest_field] = hashlib.sha256(data).hexdigest()
    member.update(sha256=source[digest_field], size=len(data))


@pytest.mark.parametrize("defect", ["text_rebound", "proof_path", "identity", "publisher_url", "direct_route", "openalex_route", "author_copy", "arxiv_copy"])
def test_coherent_supplied_claims_cannot_replace_pdf_body_identity_or_origin(imported, defect):
    ws, record, source, packet, files, _, _, _ = imported
    identity_member = files[source["identity_path"]]
    proof = json.loads(ws.path(record.artifacts[identity_member["artifact_id"]].path).read_bytes())
    if defect == "text_rebound":
        text_member = files[source["text_path"]]
        text = ws.path(record.artifacts[text_member["artifact_id"]].path).read_text(encoding="utf8")
        text = text.replace("Complete source paths", "An invented scientific finding replaces source paths")
        rewrite(imported, "text_path", text.encode("utf8"))
        proof["text_sha256"] = source["text_sha256"]
        rewrite(imported, "identity_path", json.dumps(proof).encode("utf8"))
    elif defect == "proof_path":
        proof["raw_path"] = "literature/a-different-original.pdf"
        rewrite(imported, "identity_path", json.dumps(proof).encode("utf8"))
    elif defect == "identity":
        proof["identity"]["title_range"]["start"] += 1
        rewrite(imported, "identity_path", json.dumps(proof).encode("utf8"))
    elif defect == "publisher_url": source["publisher_url"] = "https://unrelated.example/paper"
    elif defect in {"direct_route", "openalex_route"}:
        proof["route"] = "direct_public_pdf" if defect == "direct_route" else "openalex_repository"
        rewrite(imported, "identity_path", json.dumps(proof).encode("utf8"))
    elif defect == "author_copy": source["copy_type"] = "author_copy"
    else:
        source.pop("copy_type")
        source["arxiv_id"] = "2606.22504v1"
    try:
        valid = _retained_primary_body(ws, record, source, packet, imported_files=files)
    except WorkflowError as error:
        assert error.code == "PUBLICATION_EVIDENCE_INVALID"
        if defect == "text_rebound": assert "complete original extracted text" in str(error)
    else:
        assert not valid


def test_primary_packet_attempt_and_body_ranges_remain_required(imported):
    ws, record, source, packet, files, _, _, _ = imported
    packet["pdf_hint_attempts"][0]["status"] = "failed"
    assert not _retained_primary_body(ws, record, source, packet, imported_files=files)
    packet["pdf_hint_attempts"][0]["status"] = "verified"
    source["body_range"]["start"] += 1
    assert not _retained_primary_body(ws, record, source, packet, imported_files=files)

"""Transport limits are distinct from the later publisher identity/body verification."""

import base64
import copy
import hashlib

import pytest

from paper_factory.autonomous.repository_supplement import PortfolioSupplement, decode_supplement_files


def packet():
    body = b"The complete scientific body is supplied for structural transport tests only."
    parts = {"raw_path": ("paper.pdf", b"%PDF-1.7\n" + b"0" * 180000),
        "metadata_path": ("metadata.html", b"<html>Official publisher metadata fixture</html>"),
        "text_path": ("body.txt", body), "discovery_path": ("selection.json", b"{}"),
        "identity_path": ("identity.json", b"{}")}
    source = {"id": "source-0123456789abcdef0123", "copy_type": "repository_copy",
        "publisher_url": "https://www.usenix.org/conference/example/presentation/paper",
        "url": "https://www.usenix.org/system/files/example.pdf", "body_range": {"start": 0, "end": len(body)}}
    members, files = [], []
    for field, (name, raw) in parts.items():
        digest = {"raw_path": "sha256", "metadata_path": "metadata_sha256", "text_path": "text_sha256",
            "discovery_path": "discovery_sha256", "identity_path": "identity_sha256"}[field]
        source[field], source[digest] = "literature/" + name, hashlib.sha256(raw).hexdigest()
        members.append({"name": name, "sha256": source[digest], "size": len(raw), "original_path": source[field]})
        files.append({"name": name, "contentBase64": base64.b64encode(raw).decode("ascii")})
    material = {"id": source["id"], "kind": "primary_body", "name": "body.txt", "sha256": source["text_sha256"],
        "title": "Structural fixture only", "url": source["url"], "provenance": "supplied_primary_copy",
        "primary_source": source, "primary_proof": {"pdf_hint_attempts": [{"source_id": source["id"]}]}}
    value = {"prior_analysis_sha256": "a" * 64, "prior_literature_sha256": "b" * 64,
        "reviews": [{"venue_id": "science-computer-programming", "draft_artifact_id": "draft",
            "draft_sha256": "c" * 64, "review_artifact_id": "review", "review_sha256": "d" * 64}],
        "members": members, "materials": [material],
        "selection": {"rationale": "This is a structural fixture, never an authenticated publication.",
            "lineage": "Synthetic transport bytes only; native publication verification must reject its fake identity."},
        "comparison": {"protocol": "Read the entire supplied scientific fixture and test only the transport role and bounds.",
            "provenance": "supplied_interpretation", "witnesses": [{"id": "body", "material_id": source["id"], "quote": body.decode()}],
            "results": [{"claim": "This fixture exercises transport binding without asserting a scientific result.",
                "evidence_ids": ["body"], "limitations": "No publication identity or actual research admission is established by this fixture."}]}}
    return value, files


def replace(value, files, index, raw):
    member = value["members"][index]
    member.update(sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
    files[index]["contentBase64"] = base64.b64encode(raw).decode("ascii")
    field = {0: "sha256", 1: "metadata_sha256", 2: "text_sha256", 3: "discovery_sha256", 4: "identity_sha256"}[index]
    value["materials"][0]["primary_source"][field] = member["sha256"]
    if index == 2:
        value["materials"][0]["sha256"] = member["sha256"]


def append_requirement(value, files, index, raw):
    name, identity = f"requirement-{index}.txt", f"supplement-requirement-{index}"
    digest = hashlib.sha256(raw).hexdigest()
    value["members"].append({"name": name, "sha256": digest, "size": len(raw)})
    files.append({"name": name, "contentBase64": base64.b64encode(raw).decode("ascii")})
    value["materials"].append({"id": identity, "kind": "requirement", "name": name,
        "sha256": digest, "title": "Complete requirement fixture", "url": "https://example.org/requirements",
        "provenance": "supplied_snapshot"})
    value["comparison"]["witnesses"].append({"id": identity, "material_id": identity, "quote": raw[:40].decode()})
    value["comparison"]["results"][0]["evidence_ids"].append(identity)


def test_bound_raw_pdf_has_separate_allowance_without_expanding_text_limits():
    value, files = packet()
    decoded = decode_supplement_files(PortfolioSupplement.model_validate(value), files)
    assert len(decoded["paper.pdf"]) > 128 * 1024
    # Native proof validation is separate; these synthetic PDF bytes are not admitted here.
    assert decoded["body.txt"].decode() == value["comparison"]["witnesses"][0]["quote"]


@pytest.mark.parametrize("defect", ["not_publisher", "arxiv", "unbound_pdf", "raw_too_big", "text_too_big", "text_total"])
def test_only_exact_publisher_raw_role_can_use_the_pdf_allowance(defect):
    value, files = packet()
    source = value["materials"][0]["primary_source"]
    if defect == "not_publisher":
        del source["publisher_url"]
    elif defect == "arxiv":
        source["copy_type"] = "preprint"
    elif defect == "unbound_pdf":
        value["members"][1]["name"] = "metadata.pdf"
    elif defect == "raw_too_big":
        replace(value, files, 0, b"%PDF-1.7\n" + b"0" * (1024 * 1024))
    elif defect == "text_too_big":
        replace(value, files, 2, b"x" * (128 * 1024 + 1))
    else:
        for index in (1, 2, 3, 4):
            replace(value, files, index, b"x" * (128 * 1024))
        append_requirement(value, files, 1, b"Complete additional requirement above the aggregate limit.")
    with pytest.raises(ValueError):
        PortfolioSupplement.model_validate(value)


@pytest.mark.parametrize("defect", ["signature", "digest", "pdf_as_text"])
def test_pdf_binary_role_and_exact_bytes_are_checked_before_proof_verification(defect):
    value, files = packet()
    if defect == "signature":
        replace(value, files, 0, b"This has matching digests but is not a PDF.")
    elif defect == "digest":
        files[0]["contentBase64"] = base64.b64encode(b"%PDF-1.7\nchanged").decode("ascii")
    else:
        replace(value, files, 2, b"%PDF-1.7\nnot scientific UTF-8 text")
    with pytest.raises(ValueError):
        decode_supplement_files(PortfolioSupplement.model_validate(value), files)


def test_two_bound_pdf_originals_share_one_mib_total_allowance():
    value, files = packet()
    replace(value, files, 0, b"%PDF-1.7\n" + b"0" * 600000)
    second = copy.deepcopy(value["materials"][0])
    second["id"] = second["primary_source"]["id"] = "source-fedcba98765432100123"
    second["primary_source"]["raw_path"] = "literature/second.pdf"
    value["members"].append({**value["members"][0], "name": "second.pdf", "original_path": "literature/second.pdf"})
    value["materials"].append(second)
    value["comparison"]["witnesses"].append({**value["comparison"]["witnesses"][0], "id": "second", "material_id": second["id"]})
    value["comparison"]["results"][0]["evidence_ids"].append("second")
    with pytest.raises(ValueError):
        PortfolioSupplement.model_validate(value)


def test_complete_multifile_case_can_exceed_old_count_and_aggregate_without_fragments():
    value, files = packet()
    for index in range(4):
        append_requirement(value, files, index, b"Complete source requirement witness: " + b"x" * 80000)
    assert len(files) == 9
    ordinary = sum(member["size"] for member in value["members"][1:])
    assert 256 * 1024 < ordinary < 512 * 1024
    decoded = decode_supplement_files(PortfolioSupplement.model_validate(value), files)
    assert len(decoded) == 9
    assert all(decoded[f"requirement-{index}.txt"] == b"Complete source requirement witness: " + b"x" * 80000 for index in range(4))


@pytest.mark.parametrize("kind", ["case_source", "requirement", "supplied_result"])
def test_only_commit_bound_whole_case_sources_can_preserve_large_router_files(kind):
    value, files = packet()
    raw = b"Complete source requirement witness: " + b"x" * 152900
    append_requirement(value, files, 1, raw)
    material = value["materials"][-1]
    material["kind"] = kind
    if kind == "case_source":
        material.update(case_id="case-fixture", path="server/server.go", commit="a" * 40,
            url="https://github.com/fixture/repository/blob/" + "a" * 40 + "/server/server.go")
        decoded = decode_supplement_files(PortfolioSupplement.model_validate(value), files)
        assert decoded["requirement-1.txt"] == raw
    else:
        if kind == "supplied_result":
            material["provenance"] = "supplied_interpretation"
        with pytest.raises(ValueError):
            PortfolioSupplement.model_validate(value)


def test_case_source_allowance_remains_bounded_by_single_file_and_total_text():
    value, files = packet()
    append_requirement(value, files, 1, b"Complete source requirement witness: " + b"x" * (256 * 1024))
    value["materials"][-1].update(kind="case_source", case_id="case-fixture", path="server/server.go", commit="a" * 40,
        url="https://github.com/fixture/repository/blob/" + "a" * 40 + "/server/server.go")
    with pytest.raises(ValueError):
        PortfolioSupplement.model_validate(value)

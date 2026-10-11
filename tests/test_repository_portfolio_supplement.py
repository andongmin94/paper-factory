"""Immutable supplied-evidence admissions; temporary synthetic studies, no real SDK or execution."""

import base64
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from paper_factory.autonomous.repository_portfolio import (
    RepositoryPortfolioMixin, START_KEY, ANALYSIS_KEY, GUIDANCE_KEY, SUPPLEMENT_KEY, SUPPLEMENT_INTENT,
    PORTFOLIO_MARKER, MATERIAL_HEADER,
)
from paper_factory.autonomous.repository_supplement import PortfolioSupplement, decode_supplement_files
from paper_factory.workflow import WorkflowError, _inference_read
from test_repository_paper_workflow import study, review
from test_repository_portfolio import portfolio, retain_portfolio_response
from test_repository_portfolio_revision import reviewed_portfolio
from test_repository_portfolio_followup import repair, revised_draft
from test_scholarly_html import HINT, HTML, collection, clock


@pytest.fixture
def negative_second(reviewed_portfolio):
    service, rid = reviewed_portfolio
    current = repair(service, rid)
    service.collector = lambda queries, root, **kwargs: {"sources": [], "searches": [{"query": query} for query in queries],
        "warnings": [], "pdf_reservations": []}
    current = service.collect_portfolio_literature(rid, ["a retained final synthetic nearest-method search without a new body"])
    venue = current["repository_paper"]["portfolio"]["venues"][0]
    value = revised_draft(service, rid, venue)
    key, _ = retain_portfolio_response(service, rid, value, "venue-manuscript", venue["venue_id"])
    service.submit_portfolio_manuscript(rid, {"venue_id": venue["venue_id"], "inference_artifact_id": key, "manuscript": value})
    negative = review(False)
    negative["content_assessment"]["next_actions"] = [{"action": "retrieve_literature", "target": "Closest method and differing case",
        "required_change": "Compare actual primary bodies and a genuine separately declared case, without inventing validation.",
        "verification": "Inspect unchanged full source bytes and compare literal counterexamples with explicit supplied lineage."}]
    negative["content_assessment"]["literature_queries"] = [HINT["title"]]
    key, _ = retain_portfolio_response(service, rid, negative, "venue-manuscript-review", venue["venue_id"])
    service.submit_portfolio_review(rid, {"venue_id": venue["venue_id"], "inference_artifact_id": key, "review": negative})
    return service, rid


def case_package(status):
    pf = status["repository_paper"]["portfolio"]
    venue = pf["venues"][0]
    raw = b"// Synthetic supplied case: not a real measured project or independent validation.\nfunction delegate(resource) { return resource.read(); }\n"
    sha = hashlib.sha256(raw).hexdigest()
    material = {"id": "supplement-case-b", "kind": "case_source", "name": "case-b.txt", "sha256": sha,
        "title": "Explicitly synthetic separate-case source fixture", "case_id": "case-b", "path": "delegate.js", "commit": "b" * 40,
        "url": "https://github.com/synthetic-fixture/separate-case/blob/" + "b" * 40 + "/delegate.js", "provenance": "supplied_snapshot"}
    value = {"prior_analysis_sha256": pf["analysis_sha256"], "prior_literature_sha256": pf["literature_sha256"],
        "reviews": [{"venue_id": venue["venue_id"], "draft_artifact_id": venue["artifact_ids"]["draft"], "draft_sha256": venue["draft_sha256"],
            "review_artifact_id": venue["artifact_ids"]["review"], "review_sha256": status["artifacts"][venue["artifact_ids"]["review"]]["sha256"]}],
        "members": [{"name": material["name"], "sha256": sha, "size": len(raw)}], "materials": [material],
        "selection": {"rationale": "This synthetic fixture is selected to verify a separately bound supplied case, not generalizability.",
            "lineage": "The origin declaration is supplied and unverified; no independence, author participation or execution is asserted."},
        "comparison": {"protocol": "Read the literal supplied delegation function and distinguish returned capability from main-repository configuration; this is a synthetic protocol test only.",
            "witnesses": [{"id": "delegation", "material_id": material["id"], "quote": "function delegate(resource) { return resource.read(); }"}],
            "results": [{"claim": "The synthetic supplied bytes express a resource read call, not a verified execution result or research novelty.",
                "evidence_ids": ["delegation"], "limitations": "Supplied lineage and interpretation are unverified; this temporary fixture establishes no scientific validation."}],
            "provenance": "supplied_interpretation"}}
    return value, [{"name": material["name"], "contentBase64": base64.b64encode(raw).decode()}]


def supplementary_read(service, rid):
    status = service.status(rid)
    packet = status["repository_paper"]["portfolio"]["supplementary_evidence"]
    text = service.artifact_path(rid, packet["artifact_id"]).read_bytes().decode("utf-8")
    bodies = []
    for material in packet["materials"]:
        body = service.artifact_path(rid, material["artifact_id"]).read_bytes().decode("utf-8")
        bodies.append({"source_id": material["id"], "name": material["artifact_id"], "sha256": material["sha256"],
            "text": body, **_inference_read(body)})
    return {"artifact_id": packet["artifact_id"], "sha256": packet["sha256"], "text": text, **_inference_read(text), "materials": bodies}


@pytest.mark.parametrize("reviewed_portfolio", [{"precollect": True, "human_elsewhere": True}], indirect=True)
def test_supplied_case_third_writer_and_independent_review_preserve_spent_history(negative_second):
    service, rid = negative_second
    before = service.status(rid)
    prior = before["repository_paper"]["portfolio"]
    assert prior["literature_budget"] == {"used": 3, "limit": 3} and before["repository_paper"]["analysis_attempts"] == 3
    assert prior["supplementary_evidence_available"] and not prior["venues"][0]["revise_available"]
    original = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    value, files = case_package(before)
    for corruption in ("member_sha", "file_bytes", "review", "quote", "origin", "notes"):
        bad, bad_files = copy.deepcopy(value), copy.deepcopy(files)
        if corruption == "member_sha": bad["members"][0]["sha256"] = "0" * 64
        elif corruption == "file_bytes": bad_files[0]["contentBase64"] = base64.b64encode(b"Fabricated different case source").decode()
        elif corruption == "review": bad["reviews"][0]["review_sha256"] = "0" * 64
        elif corruption == "quote": bad["comparison"]["witnesses"][0]["quote"] = "Fabricated nonliteral comparative witness"
        elif corruption == "origin": bad["materials"][0]["commit"] = "c" * 40
        else:
            bad["materials"][0].update(kind="supplied_result", provenance="supplied_interpretation")
            for field in ("case_id", "path", "commit"): bad["materials"][0].pop(field)
        with pytest.raises((ValueError, WorkflowError)):
            service.admit_portfolio_evidence(rid, bad, bad_files)
        current = service.status(rid)
        assert current["artifacts"] == before["artifacts"] and current["repository_paper"]["portfolio"]["supplementary_evidence_budget"]["used"] == 0
    admitted = service.admit_portfolio_evidence(rid, value, files)
    pf = admitted["repository_paper"]["portfolio"]
    assert pf["supplementary_evidence_budget"] == {"used": 1, "limit": 1} and not pf["supplementary_evidence_available"]
    venue = pf["venues"][0]
    assert venue["revise_available"] and venue["writer_binding"]["attempt"] == 3
    assert venue["writer_binding"]["supplementary_evidence_sha256"] == pf["supplementary_evidence"]["sha256"]
    assert venue["writer_binding"]["prior_review_sha256"] == value["reviews"][0]["review_sha256"]
    assert pf["venues"][1] == prior["venues"][1] and not venue["scientific_ready"] and not venue["content_ready"]
    assert pf["literature_budget"] == prior["literature_budget"] and pf["pdf_budget"] == prior["pdf_budget"]
    assert pf["analysis_sha256"] == prior["analysis_sha256"]
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in original.items())
    receipt = json.loads(service.artifact_path(rid, SUPPLEMENT_KEY).read_bytes())
    assert "value" not in receipt
    assert json.loads(service.artifact_path(rid, SUPPLEMENT_INTENT).read_bytes())["value"] == value
    assert receipt["reviews"] == value["reviews"]
    assert all(set(row) == {"venue_id", "draft_artifact_id", "draft_sha256", "review_artifact_id", "review_sha256"}
        for row in receipt["reviews"])
    assert service.admit_portfolio_evidence(rid, value, files)["artifacts"] == admitted["artifacts"]
    delivered = supplementary_read(service, rid)
    third = revised_draft(service, rid, venue)
    third["sections"][3]["text"] += " The new separately declared synthetic case is supplied evidence, not executed or independently validated. {{document:supplement-case-b}}"
    third["document_evidence"] = [{"source_id": "supplement-case-b", "text_sha256": value["materials"][0]["sha256"],
        "quote": value["comparison"]["witnesses"][0]["quote"], "interpretation": "This static supplied fixture differs from the main repository but cannot establish scientific generalization or native execution."}]
    large_notice = "Explicitly synthetic expanded-context test; no SDK or project execution.\n" + " " * 701000 + "\n"
    for corruption in ("unbound", "sha"):
        def change_binding(binding):
            if corruption == "unbound": binding.pop("supplementary_evidence_sha256")
            else: binding["supplementary_evidence_sha256"] = "0" * 64
        with pytest.raises(WorkflowError) as failure:
            retain_portfolio_response(service, rid, third, "venue-manuscript", venue["venue_id"],
                material_change=lambda materials: materials.update(portfolioSupplement=delivered), material_notice=large_notice,
                model="gpt-6.1-sol", binding_change=change_binding)
        assert failure.value.code == "PORTFOLIO_SUPPLEMENT_BINDINGS_INVALID"
        assert service.status(rid)["artifacts"] == admitted["artifacts"]
    for corruption in ("receipt", "omitted", "body_eof"):
        def change(materials):
            body = copy.deepcopy(delivered)
            if corruption == "receipt": body["text"] += " Invented evidence."
            elif corruption == "omitted": return
            else: body["materials"][0]["pages"][-1]["nextOffset"] = 32000
            materials["portfolioSupplement"] = body
        with pytest.raises(WorkflowError) as failure:
            retain_portfolio_response(service, rid, third, "venue-manuscript", venue["venue_id"], material_change=change)
        assert failure.value.code == ("ANALYSIS_READING_INVALID" if corruption == "omitted" else "PORTFOLIO_SUPPLEMENT_READING_INVALID")
        assert service.status(rid)["artifacts"] == admitted["artifacts"]
    key, started = retain_portfolio_response(service, rid, third, "venue-manuscript", venue["venue_id"],
        material_change=lambda materials: materials.update(portfolioSupplement=delivered), material_notice=large_notice, model="gpt-6.1-sol")
    assert len(started["prompt"]) > 700000 and len(started["prompt"].encode("utf-8")) <= 900000
    saved = service.submit_portfolio_manuscript(rid, {"venue_id": venue["venue_id"], "inference_artifact_id": key, "manuscript": third})
    latest = saved["repository_paper"]["portfolio"]["venues"][0]
    markdown = service.artifact_path(rid, latest["artifact_ids"]["markdown"]).read_text(encoding="utf-8")
    assert value["materials"][0]["url"] in markdown and "case-b" in markdown and "supplied_snapshot" in markdown
    assert latest["draft_attempts"] == latest["admitted_drafts"] == 3 and latest["reviewer_binding"]["supplementary_evidence_sha256"] == pf["supplementary_evidence"]["sha256"]
    negative = review(False)
    key, _ = retain_portfolio_response(service, rid, negative, "venue-manuscript-review", venue["venue_id"], material_change=lambda materials: materials.update(portfolioSupplement=delivered))
    final = service.submit_portfolio_review(rid, {"venue_id": venue["venue_id"], "inference_artifact_id": key, "review": negative})
    latest = final["repository_paper"]["portfolio"]["venues"][0]
    assert latest["review_attempts"] == 3 and latest["draft_attempts"] == 3 and latest["writer_binding"] is None and not latest["scientific_ready"]
    assert final["repository_paper"]["analysis_attempts"] == 3 and final["study_literature_attempt"] == 3 and final["execution_attempt"] == 0
    assert all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in original.items())


def html_package(status, tmp_path, monkeypatch, *, corrupt=False):
    # Original Latin1 raw HTML is copied without transcoding; the extracted
    # scientific text and the original selection/identity files are UTF-8.
    packet, _ = collection(monkeypatch, tmp_path, body=HTML.replace(b"</body>", b"<p>caf\xe9</p></body>"))
    source, = packet["sources"]
    value, _ = case_package(status)
    members, files = [], []
    for index, (field, digest) in enumerate((("raw_path", "sha256"), ("metadata_path", "metadata_sha256"), ("text_path", "text_sha256"),
            ("discovery_path", "discovery_sha256"), ("identity_path", "identity_sha256")), 1):
        raw = (tmp_path / source[field]).read_bytes()
        name = f"primary-{index}" + (".html" if index <= 2 else ".txt" if index == 3 else ".json")
        if corrupt and field == "identity_path":
            proof = json.loads(raw)
            proof["identity"]["authors"] = ["Fabricated Author"]
            raw = json.dumps(proof).encode()
            source[digest] = hashlib.sha256(raw).hexdigest()
        members.append({"name": name, "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw), "original_path": source[field]})
        files.append({"name": name, "contentBase64": base64.b64encode(raw).decode()})
    value["members"] = members
    value["materials"] = [{"id": source["id"], "kind": "primary_body", "name": members[2]["name"], "sha256": source["text_sha256"],
        "title": source["title"], "url": source["url"], "provenance": "supplied_primary_copy", "primary_source": source,
        "primary_proof": {"html_attempts": packet["html_attempts"]}}]
    text = (tmp_path / source["text_path"]).read_text(encoding="utf-8")
    body = source["body_range"]
    quote = text[body["start"]:body["start"] + 180]
    value["comparison"]["witnesses"] = [{"id": "delegation", "material_id": source["id"], "quote": quote}]
    return value, files


@pytest.mark.parametrize("reviewed_portfolio", [{"precollect": True}], indirect=True)
@pytest.mark.parametrize("corrupt", [False, True])
def test_original_html_primary_proof_is_rederived_and_failed_admission_is_spent(negative_second, tmp_path, monkeypatch, clock, corrupt):
    service, rid = negative_second
    before = service.status(rid)
    original = {key: service.artifact_path(rid, key).read_bytes() for key in before["artifacts"]}
    value, files = html_package(before, tmp_path / "outside-study", monkeypatch, corrupt=corrupt)
    if corrupt:
        with pytest.raises(WorkflowError) as rejected:
            service.admit_portfolio_evidence(rid, value, files)
        assert rejected.value.code == "PORTFOLIO_SUPPLEMENT_INVALID"
        admitted = service.status(rid)
        assert admitted["repository_paper"]["portfolio"]["supplementary_evidence"]["status"] == "failed"
        receipt = json.loads(service.artifact_path(rid, SUPPLEMENT_KEY).read_bytes())
        assert "value" not in receipt and receipt["reviews"] == value["reviews"]
        with pytest.raises(WorkflowError) as replay:
            service.admit_portfolio_evidence(rid, value, files)
        assert replay.value.code == "PORTFOLIO_SUPPLEMENT_LIMIT"
        assert service.status(rid)["artifacts"] == admitted["artifacts"]
    else:
        admitted = service.admit_portfolio_evidence(rid, value, files)
        supplement = admitted["repository_paper"]["portfolio"]["supplementary_evidence"]
        assert supplement["status"] == "admitted" and len(supplement["all_materials"]) == 5
        with service._operation(rid) as (ws, record):
            sources, docs, mappings = service._portfolio_supplement_evidence(ws, record, supplement["sha256"])
            assert not docs and sources[value["materials"][0]["id"]] == value["materials"][0]["primary_source"]
            assert len(mappings[value["materials"][0]["id"]]) == 5
        material = supplement["materials"][0]
        assert service.artifact_path(rid, material["artifact_id"]).read_bytes() == base64.b64decode(files[2]["contentBase64"])
        raw = service.artifact_path(rid, supplement["all_materials"][0]["artifact_id"]).read_bytes()
        assert b"caf\xe9" in raw
        with pytest.raises(UnicodeDecodeError): raw.decode("utf-8")
        assert admitted["repository_paper"]["portfolio"]["venues"][0]["writer_binding"]["supplementary_evidence_sha256"] == supplement["sha256"]
    assert admitted["repository_paper"]["portfolio"]["supplementary_evidence_budget"] == {"used": 1, "limit": 1}
    assert admitted["repository_paper"]["analysis_attempts"] == before["repository_paper"]["analysis_attempts"] == 3
    assert admitted["study_literature_attempt"] == before["study_literature_attempt"] == 3
    assert admitted["repository_paper"]["portfolio"]["pdf_budget"] == before["repository_paper"]["portfolio"]["pdf_budget"]
    assert admitted["execution_attempt"] == 0 and all(service.artifact_path(rid, key).read_bytes() == raw for key, raw in original.items())


def test_manifest_rejects_unsafe_paths_raw_binary_and_unlinked_notes():
    status = {"repository_paper": {"portfolio": {"analysis_sha256": "a" * 64, "literature_sha256": "b" * 64,
        "venues": [{"venue_id": "fixture-venue", "artifact_ids": {"draft": "draft-2", "review": "review-2"}, "draft_sha256": "c" * 64}]}},
        "artifacts": {"review-2": {"sha256": "d" * 64}}}
    value, files = case_package(status)
    assert decode_supplement_files(PortfolioSupplement.model_validate(value), files)
    for update in ({"name": "../case.txt"}, {"name": "CON.txt"}, {"name": "receipt.json"}, {"original_path": "../source.txt"}, {"size": 262145}):
        bad = copy.deepcopy(value)
        bad["members"][0].update(update)
        with pytest.raises(ValueError): PortfolioSupplement.model_validate(bad)
    for raw in (b"%PDF-1.7\nnot HTML", b"opaque\x00binary", b"Latin1 caf\xe9 without primary HTML proof"):
        bad = copy.deepcopy(value)
        bad["members"][0].update(size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        bad["materials"][0]["sha256"] = bad["members"][0]["sha256"]
        with pytest.raises(ValueError): decode_supplement_files(PortfolioSupplement.model_validate(bad), [{"name": "case-b.txt", "contentBase64": base64.b64encode(raw).decode()}])


def test_primary_mapping_excludes_other_cases_and_false_reverification_is_rejected():
    service = RepositoryPortfolioMixin()
    paths = ["original/" + name for name in ("raw", "metadata", "text", "discovery", "identity")]
    source = {field: path for field, path in zip(("raw_path", "metadata_path", "text_path", "discovery_path", "identity_path"), paths)}
    members = [{"original_path": path, "artifact_id": "member-" + str(index), "sha256": "a" * 64, "size": 10}
        for index, path in enumerate([*paths, "other-case/main.js"])]
    packet = {"status": "admitted", "all_materials": members, "materials": [{"id": "source-test", "kind": "primary_body", "primary_source": source}]}
    service._portfolio_supplement = lambda *args: packet
    service._portfolio_verify_supplement_primary = lambda *args: True
    sources, docs, imported = service._portfolio_supplement_evidence(None, None, "bound-sha")
    assert sources == {"source-test": source} and docs == {} and set(imported["source-test"]) == set(paths)
    service._portfolio_verify_supplement_primary = lambda *args: False
    with pytest.raises(WorkflowError) as failure:
        service._portfolio_supplement_evidence(None, None, "bound-sha")
    assert failure.value.code == "PORTFOLIO_SUPPLEMENT_INVALID"


@pytest.mark.parametrize("change", ["null", "str", "bool", "float"])
def test_coercion_or_optional_null_is_rejected_before_any_admission_reservation(change):
    status = {"repository_paper": {"portfolio": {"analysis_sha256": "a" * 64, "literature_sha256": "b" * 64,
        "venues": [{"venue_id": "fixture-venue", "artifact_ids": {"draft": "draft-2", "review": "review-2"}, "draft_sha256": "c" * 64}]}},
        "artifacts": {"review-2": {"sha256": "d" * 64}}}
    value, files = case_package(status)
    if change == "null": value["materials"][0]["primary_source"] = None
    else:
        size = value["members"][0]["size"]
        value["members"][0]["size"] = str(size) if change == "str" else True if change == "bool" else float(size)
    service = RepositoryPortfolioMixin()
    service._operation = lambda *args: pytest.fail("Malformed normalized input cannot reserve an admission")
    with pytest.raises(ValueError): service.admit_portfolio_evidence("not-a-real-study", value, files)


def test_initial_portfolio_without_second_review_does_not_reread_every_prior_draft():
    service = RepositoryPortfolioMixin()
    service._portfolio_reservations = lambda *args: pytest.fail("No second review exists; avoid rereading original model outcomes")
    assert service._portfolio_supplement_candidates(None, SimpleNamespace(artifacts={"repository-portfolio-fixture-review-1": object()})) == []


@pytest.fixture
def frozen_supplement(tmp_path):
    """Whole large original reviews remain separately frozen, without copied bodies."""
    record = SimpleNamespace(artifacts={})
    ws = SimpleNamespace(path=lambda relative: tmp_path / relative)
    originals = {}
    def freeze(key, value):
        raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode("utf-8")
        path = tmp_path / (key + ".json")
        path.write_bytes(raw)
        record.artifacts[key] = SimpleNamespace(path=path.name, size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        originals[key] = raw
        return record.artifacts[key].sha256
    start_sha = freeze(START_KEY, {"scope": "Explicitly synthetic frozen portfolio basis"})
    analysis_sha = freeze(ANALYSIS_KEY, {"method": "Explicitly synthetic whole common analysis"})
    literature_key = "repository-portfolio-literature-3"
    literature_sha = freeze(literature_key, {"sources": [], "scope": "Explicitly synthetic whole literature packet"})
    reviews = []
    for index in range(7):
        venue = "fixture-venue-" + str(index)
        draft_key = RepositoryPortfolioMixin._portfolio_key(venue, "draft", 2)
        review_key = RepositoryPortfolioMixin._portfolio_key(venue, "review", 2)
        bindings = {"venue_id": venue, "portfolio_start_sha256": start_sha, "attempt": 2}
        draft_sha = freeze(draft_key, {"value": {"text": "원고 본문 전체. " * 7000}, "bindings": bindings})
        review_sha = freeze(review_key, {"value": {"text": "심사 본문 전체. " * 7000}, "bindings": bindings, "draft_sha256": draft_sha})
        reviews.append({"venue_id": venue, "draft_artifact_id": draft_key, "draft_sha256": draft_sha,
            "review_artifact_id": review_key, "review_sha256": review_sha})
    value, files = case_package({"repository_paper": {"portfolio": {"analysis_sha256": analysis_sha, "literature_sha256": literature_sha,
        "venues": [{"venue_id": reviews[0]["venue_id"], "artifact_ids": {"draft": reviews[0]["draft_artifact_id"], "review": reviews[0]["review_artifact_id"]},
            "draft_sha256": reviews[0]["draft_sha256"]}]}}, "artifacts": {reviews[0]["review_artifact_id"]: {"sha256": reviews[0]["review_sha256"]}}})
    value["reviews"] = copy.deepcopy(reviews)
    member_key = "repository-portfolio-supplement-member-1"
    freeze(member_key, base64.b64decode(files[0]["contentBase64"]))
    member = {**value["members"][0], "artifact_id": member_key}
    intent_sha = freeze(SUPPLEMENT_INTENT, {"value": value, "portfolio_start_sha256": start_sha})
    packet = {"reviews": copy.deepcopy(reviews), "portfolio_start_sha256": start_sha,
        "prior_analysis_sha256": analysis_sha, "prior_literature_sha256": literature_sha,
        "intent_sha256": intent_sha, "status": "admitted", "affected_venues": [row["venue_id"] for row in reviews],
        "materials": [{**value["materials"][0], "artifact_id": member_key, "size": member["size"]}], "all_materials": [member],
        "selection": copy.deepcopy(value["selection"]), "comparison": copy.deepcopy(value["comparison"])}
    freeze(SUPPLEMENT_KEY, packet)
    return RepositoryPortfolioMixin(), ws, record, packet, originals, freeze, literature_key, value


def test_supplement_refs_read_all_seven_whole_original_drafts_and_reviews(frozen_supplement, monkeypatch):
    from paper_factory import workflow as engine
    service, ws, record, packet, originals, _, literature_key, value = frozen_supplement
    read = engine._read
    delivered = {}
    def inspect(workspace, workflow, key):
        value = read(workspace, workflow, key)
        delivered[key] = value
        return value
    monkeypatch.setattr(engine, "_read", inspect)
    retained = service._portfolio_supplement(ws, record, record.artifacts[SUPPLEMENT_KEY].sha256)
    assert retained["reviews"] == value["reviews"] and len(retained["reviews"]) == 7 and "value" not in retained
    assert record.artifacts[SUPPLEMENT_KEY].size < 12000
    assert ANALYSIS_KEY in delivered and literature_key in delivered
    for row in retained["reviews"]:
        assert set(row) == {"venue_id", "draft_artifact_id", "draft_sha256", "review_artifact_id", "review_sha256"}
        for key in (row["draft_artifact_id"], row["review_artifact_id"]):
            assert delivered[key] == json.loads(originals[key])
            assert ws.path(record.artifacts[key].path).read_bytes() == originals[key]
            assert len(delivered[key]["value"]["text"]) > 32000


@pytest.mark.parametrize("target", ["draft", "review", "analysis", "literature", "member"])
def test_supplement_ref_cannot_mask_changed_original_bytes(frozen_supplement, target):
    service, ws, record, packet, _, _, literature_key, _ = frozen_supplement
    key = (ANALYSIS_KEY if target == "analysis" else literature_key if target == "literature" else
        packet["all_materials"][0]["artifact_id"] if target == "member" else
        packet["reviews"][0][target + "_artifact_id"])
    with ws.path(record.artifacts[key].path).open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(WorkflowError) as failure:
        service._portfolio_supplement(ws, record)
    assert failure.value.code == "ARTIFACT_CHANGED"


@pytest.mark.parametrize("corruption", ["review_copy", "binding_copy", "draft_sha", "review_sha", "binding", "venue", "attempt"])
def test_supplement_refs_reject_obsolete_copies_and_changed_original_binding(frozen_supplement, corruption):
    service, ws, record, packet, originals, freeze, _, value = frozen_supplement
    row = packet["reviews"][0]
    if corruption in {"review_copy", "binding_copy"}:
        row["review" if corruption == "review_copy" else "draft_bindings"] = {}
    elif corruption in {"draft_sha", "review_sha"}:
        row[corruption + "256"] = "0" * 64
        value["reviews"] = copy.deepcopy(packet["reviews"])
    elif corruption == "binding":
        review = json.loads(originals[row["review_artifact_id"]])
        review["bindings"]["attempt"] = 1
        row["review_sha256"] = freeze(row["review_artifact_id"], review)
        value["reviews"] = copy.deepcopy(packet["reviews"])
    elif corruption == "venue":
        row["venue_id"] = "different-fixture-venue"
        value["reviews"] = copy.deepcopy(packet["reviews"])
    else:
        draft_key = row["draft_artifact_id"].removesuffix("2") + "1"
        row["draft_sha256"] = freeze(draft_key, json.loads(originals[row["draft_artifact_id"]]))
        row["draft_artifact_id"] = draft_key
        value["reviews"] = copy.deepcopy(packet["reviews"])
    packet["intent_sha256"] = freeze(SUPPLEMENT_INTENT, {"value": value, "portfolio_start_sha256": packet["portfolio_start_sha256"]})
    freeze(SUPPLEMENT_KEY, packet)
    with pytest.raises(WorkflowError) as failure:
        service._portfolio_supplement(ws, record)
    assert failure.value.code == "ARTIFACT_CHANGED"


@pytest.mark.parametrize("corruption", ["selection", "comparison", "member_metadata", "member_id", "material_metadata",
    "prior_sha", "affected_venues", "value_copy", "lost_member", "lost_material"])
def test_supplement_receipt_fields_cannot_change_its_original_manifest(frozen_supplement, corruption):
    service, ws, record, packet, _, freeze, _, value = frozen_supplement
    if corruption == "selection": packet["selection"]["lineage"] += " Invented independent validation."
    elif corruption == "comparison": packet["comparison"]["results"][0]["claim"] += " Invented measured outcome."
    elif corruption == "member_metadata": packet["all_materials"][0]["name"] = "renamed-case.txt"
    elif corruption == "member_id": packet["all_materials"][0]["artifact_id"] = "other-frozen-member"
    elif corruption == "material_metadata": packet["materials"][0]["commit"] = "c" * 40
    elif corruption == "prior_sha": packet["prior_analysis_sha256"] = "0" * 64
    elif corruption == "affected_venues": packet["affected_venues"] = []
    elif corruption == "value_copy": packet["value"] = value
    elif corruption == "lost_member": packet["all_materials"] = []
    else: packet["materials"] = []
    freeze(SUPPLEMENT_KEY, packet)
    with pytest.raises(WorkflowError) as failure:
        service._portfolio_supplement(ws, record)
    assert failure.value.code == "ARTIFACT_CHANGED"


@pytest.mark.parametrize("retained_member", [False, True])
def test_failed_supplement_keeps_exact_partial_member_and_original_manifest_proof(frozen_supplement, retained_member):
    service, ws, record, packet, _, freeze, _, value = frozen_supplement
    packet.update(status="failed", materials=[])
    if not retained_member: packet["all_materials"] = []
    for key in ("selection", "comparison"): packet.pop(key)
    freeze(SUPPLEMENT_KEY, packet)
    retained = service._portfolio_supplement(ws, record)
    assert retained["status"] == "failed" and not retained["materials"] and "value" not in retained
    assert bool(retained["all_materials"]) == retained_member
    public = service._portfolio_supplement_public(ws, record)
    assert public["selection"] == value["selection"] and public["comparison"] == value["comparison"]
    with pytest.raises(WorkflowError) as failure:
        service._portfolio_supplement_evidence(ws, record, record.artifacts[SUPPLEMENT_KEY].sha256)
    assert failure.value.code == "PORTFOLIO_SUPPLEMENT_BINDINGS_INVALID"


@pytest.mark.parametrize("bound_sha", [None, "0" * 64])
def test_expanded_context_without_exact_supplement_is_rejected_before_reservation(frozen_supplement, bound_sha):
    from paper_factory.workflow_models import ModelEvidenceReceipt
    service, ws, record, packet, _, _, _, _ = frozen_supplement
    service._require = lambda *args, **kwargs: None
    service._portfolio_start = lambda *args: None
    service._portfolio_attempts = lambda *args: pytest.fail("Reject invalid expanded context before reading or reserving model attempts")
    binding = {"venue_id": packet["reviews"][0]["venue_id"]}
    if bound_sha is not None: binding["supplementary_evidence_sha256"] = bound_sha
    prompt = PORTFOLIO_MARKER + json.dumps(binding) + MATERIAL_HEADER + " " * 701000 + "\n{}"
    receipt = ModelEvidenceReceipt.model_validate({"id": "00000000-0000-0000-0000-000000000001",
        "phase": "venue-manuscript", "at": "2026-10-11T00:00:00+00:00", "model": "gpt-6.1-sol", "profileId": "fixture-profile",
        "prompt": prompt, "promptSha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(), "outcome": "started"})
    before = dict(record.artifacts)
    with pytest.raises(WorkflowError) as failure:
        service._portfolio_inference_guard(ws, record, receipt)
    assert failure.value.code == "PORTFOLIO_SUPPLEMENT_BINDINGS_INVALID" and record.artifacts == before


def test_exact_supplementary_context_enforces_utf8_byte_limit_below_character_limit(frozen_supplement):
    from paper_factory.workflow_models import ModelEvidenceReceipt
    service, ws, record, packet, _, _, _, _ = frozen_supplement
    service._require = lambda *args, **kwargs: None
    service._portfolio_start = lambda *args: None
    service._portfolio_attempts = lambda *args: pytest.fail("Reject oversized exact context before any attempt reservation")
    binding = {"venue_id": packet["reviews"][0]["venue_id"], "supplementary_evidence_sha256": record.artifacts[SUPPLEMENT_KEY].sha256}
    prompt = PORTFOLIO_MARKER + json.dumps(binding) + MATERIAL_HEADER + "😀" * 230000 + "\n{}"
    assert len(prompt) < 700000 and len(prompt.encode("utf-8")) > 900000
    receipt = ModelEvidenceReceipt.model_validate({"id": "00000000-0000-0000-0000-000000000002",
        "phase": "venue-manuscript", "at": "2026-10-11T00:00:00+00:00", "model": "gpt-6.1-sol", "profileId": "fixture-profile",
        "prompt": prompt, "promptSha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(), "outcome": "started"})
    before = dict(record.artifacts)
    with pytest.raises(WorkflowError) as failure:
        service._portfolio_inference_guard(ws, record, receipt)
    assert failure.value.code == "PORTFOLIO_CONTEXT_LIMIT" and record.artifacts == before


@pytest.mark.parametrize("corruption", [None, "id", "sha", "text", "page", "eof", "structured_copy"])
def test_portfolio_draft_requires_complete_exact_markdown_descriptor(tmp_path, corruption):
    service = RepositoryPortfolioMixin()
    record = SimpleNamespace(artifacts={})
    ws = SimpleNamespace(path=lambda relative: tmp_path / relative)
    key = "repository-portfolio-fixture-venue-markdown-2"
    # Multiple whole pages, including non-BMP Unicode, preserve the native read contract.
    text = "# Explicitly synthetic whole manuscript\n" + "논문 본문 😀. " * 9000 + "\nFinal retained sentence.\n"
    for artifact_id, raw in ((key, text.encode("utf-8")), (GUIDANCE_KEY, b'{"sources": []}')):
        path = tmp_path / (artifact_id + ".txt")
        path.write_bytes(raw)
        record.artifacts[artifact_id] = SimpleNamespace(path=path.name, sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
    service._repository_materials = lambda *args, **kwargs: None
    service._portfolio_latest = lambda *args: (2, {"markdown": key}, {"value": {"text": text}}, None)
    descriptor = {"artifact_id": key, "sha256": record.artifacts[key].sha256, "text": text, **_inference_read(text)}
    if corruption == "id": descriptor["artifact_id"] = "other-venue-markdown-2"
    elif corruption == "sha": descriptor["sha256"] = "0" * 64
    elif corruption == "text": descriptor["text"] = text[:-1]
    elif corruption == "page": descriptor["pages"][1]["sha256"] = "0" * 64
    elif corruption == "eof": descriptor["pages"][-1]["nextOffset"] = len(text)
    elif corruption == "structured_copy": descriptor["value"] = {"text": text}
    binding = {"phase": "venue-manuscript-review", "venue_id": "fixture-venue"}
    materials = {"retainedGuidance": [], "portfolioDraft": descriptor}
    if corruption is None:
        service._portfolio_materials(ws, record, {}, None, binding, materials)
        assert descriptor["pages"][-1]["nextOffset"] is None and len(descriptor["pages"]) == 3
    else:
        with pytest.raises(WorkflowError) as failure:
            service._portfolio_materials(ws, record, {}, None, binding, materials)
        assert failure.value.code == "PORTFOLIO_DRAFT_READING_INVALID"

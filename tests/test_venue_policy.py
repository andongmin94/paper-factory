from datetime import datetime, timedelta, timezone
import json
import socket

import httpx
import pytest

from paper_factory.venue_policy import PolicySpec, PolicyValues, VenuePolicy, refresh_policy, validate_policy, verify_policy
from paper_factory.venues import discover
from paper_factory.workspace import Workspace, digest_file, write_json


@pytest.fixture
def setup_policy(tmp_path, monkeypatch):
    ws = Workspace.create(tmp_path / "workspace")
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))])
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": [{
        "id": "https://openalex.org/S123", "display_name": "Example Journal", "type": "journal",
        "issn": ["1234-5678"], "host_organization_name": "Example Publisher", "homepage_url": "https://example.org/journal",
    }]}))) as client:
        venue = discover(ws, "research", client=client)[0]
    values = dict(
        scope="Software engineering research", article_types=["Research Article"], indexing="SCIE",
        publisher="Example Publisher", oa_model="open", apc={"status": "none"},
        preprint_policy="Preprints are permitted", ai_policy="Disclose AI assistance", ai_use_allowed=True,
        ai_disclosure_required=True, data_code_policy="Share data and code", manuscript_word_limit=None,
        abstract_word_limit=300, abstract_character_limit=None, title_character_limit=250, keyword_limit=6,
        review_model="Single anonymous", anonymization_required=False,
        required_declarations=["funding", "conflict_of_interest", "data_availability", "ai_disclosure"],
        submission_url="https://submit.example.org/", submission_system="Example submission system",
        free_initial_submission=True, template_requirements=[], accepted_formats=["pdf", "docx"],
        citation_style=None, figure_formats=["tiff", "png"], line_numbers_required=True,
        page_numbers_required=True, required_sections=["Abstract", "Introduction", "Methods", "Results", "Discussion"],
        required_supplements=[],
    )
    excerpts = {name: f"{name}: {json.dumps(value)}" for name, value in values.items()}
    excerpts["indexing"] = "Example Journal ISSN 1234-5678 Science Citation Index Expanded SCIE"
    evidence = {name: {"source_url": "https://mjl.clarivate.com/journal/123" if name == "indexing" else "https://example.org/guidelines",
                       "excerpt": text, "interpretation": f"Researcher reviewed the {name} requirement"} for name, text in excerpts.items()}
    spec = dict(venue_id=venue.id, sources=["https://example.org/guidelines", "https://mjl.clarivate.com/journal/123"],
                values=values, evidence=evidence, reviewed_by="Example Researcher")
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    body = "<html>" + "".join(f"<p>{text}</p>" for text in excerpts.values()) + "</html>"

    def handler(request):
        assert request.url.host == "93.184.216.34"  # DNS validation pins the actual connection.
        assert request.extensions["sni_hostname"] == request.headers["Host"]
        return httpx.Response(200, text=body, headers={"content-type": "text/html"})

    return ws, venue, path, spec, handler


def test_reviewed_policy_captures_sources_and_rechecks_integrity(setup_policy):
    ws, venue, path, spec, handler = setup_policy
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        policy = verify_policy(ws, venue, path, client=client)
    assert policy.status == "verified"
    assert not policy.issues and not validate_policy(ws, policy)
    assert all(source.status == "fetched" for source in policy.sources)
    assert ws.get("policy", policy.id, VenuePolicy) == policy
    assert policy.values.manuscript_word_limit is None  # Explicit unlimited with reviewed evidence.
    assert policy.values.ai_disclosure_required is True


def test_retrieval_without_review_or_facts_never_verifies(setup_policy):
    ws, venue, path, spec, handler = setup_policy
    path.write_text(json.dumps({"venue_id": venue.id, "sources": spec["sources"]}), encoding="utf-8")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        policy = verify_policy(ws, venue, path, client=client)
    assert policy.status == "review_needed"
    assert any("researcher review" in issue for issue in policy.issues)
    assert any("indexing is unknown" in issue for issue in policy.issues)
    assert not validate_policy(ws, policy, check_compliance=False)
    ws.path(policy.sources[0].raw_path).write_text("tampered", encoding="utf-8")
    assert validate_policy(ws, policy, check_compliance=False)


def test_changed_official_rules_invalidate_previous_interpretation_on_refresh(setup_policy):
    ws, venue, path, spec, handler = setup_policy
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        old = verify_policy(ws, venue, path, client=client)
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text="<p>The publisher changed its requirements.</p>", headers={"content-type": "text/html"}))) as client:
        refreshed = refresh_policy(ws, old, client=client)
    assert refreshed.id != old.id and refreshed.status == "review_needed"
    assert any("does not contain" in issue for issue in refreshed.issues)
    assert ws.get("policy", old.id, VenuePolicy) == old
    assert not validate_policy(ws, old)


@pytest.mark.parametrize("artifact", ["spec", "raw", "readable"])
def test_tampered_sources_or_spec_block_policy(setup_policy, artifact):
    ws, venue, path, spec, handler = setup_policy
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        policy = verify_policy(ws, venue, path, client=client)
    selected = {"spec": policy.spec_path, "raw": policy.sources[0].raw_path, "readable": policy.sources[0].text_path}[artifact]
    ws.path(selected).write_text("tampered", encoding="utf-8")
    assert validate_policy(ws, policy)


def test_record_timestamp_edit_is_detected_by_capture_receipt(setup_policy):
    ws, venue, path, spec, handler = setup_policy
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        policy = verify_policy(ws, venue, path, client=client)
    policy.sources[0].fetched_at = "2030-01-01T00:00:00+00:00"
    assert "receipt changed" in validate_policy(ws, policy)[0]


def test_stale_and_naive_capture_dates_block_readiness(setup_policy):
    ws, venue, path, spec, handler = setup_policy
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        policy = verify_policy(ws, venue, path, client=client)
    policy.sources[0].fetched_at = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    # A historical receipt represents an intact capture which has simply aged.
    write_json(ws.path(policy.receipt_path), policy.model_dump(mode="json", exclude={"receipt_sha256"}))
    policy.receipt_sha256 = digest_file(ws.path(policy.receipt_path))
    assert any("stale" in issue for issue in validate_policy(ws, policy))
    assert not validate_policy(ws, policy, fresh=False)


def test_indexing_cannot_be_inferred_from_publisher_or_directory(setup_policy):
    ws, venue, path, spec, handler = setup_policy
    spec["evidence"]["indexing"]["source_url"] = "https://example.org/guidelines"
    path.write_text(json.dumps(spec), encoding="utf-8")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        policy = verify_policy(ws, venue, path, client=client)
    assert policy.status == "review_needed"
    assert any("Clarivate" in issue for issue in policy.issues)


@pytest.mark.parametrize("quote", [
    "Example Journal ISSN 1234-5678 Science publication website information",
    "A different journal ISSN 9999-9999 Science Citation Index Expanded SCIE",
])
def test_indexing_excerpt_requires_exact_collection_and_this_journals_issn(setup_policy, quote):
    ws, venue, path, spec, handler = setup_policy
    spec["evidence"]["indexing"]["excerpt"] = quote
    path.write_text(json.dumps(spec), encoding="utf-8")

    def indexed(request):
        return httpx.Response(200, text=handler(request).text + f"<p>{quote}</p>", headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(indexed)) as client:
        policy = verify_policy(ws, venue, path, client=client)
    assert policy.status == "review_needed"
    assert any("exact SCIE/ESCI collection" in issue for issue in policy.issues)


@pytest.mark.parametrize("url", ["https://localhost/policy", "https://127.0.0.1/policy", "http://example.org/policy", "https://user:secret@example.org/policy", "https://example.org:8443/policy"])
def test_unsafe_source_never_contacts_network(setup_policy, url):
    ws, venue, path, spec, handler = setup_policy
    spec["sources"] = [url]
    path.write_text(json.dumps(spec), encoding="utf-8")
    with httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail("unsafe request"))) as client:
        with pytest.raises(ValueError):
            verify_policy(ws, venue, path, client=client)


def test_dns_private_address_is_preserved_as_failed_evidence(setup_policy, monkeypatch):
    ws, venue, path, spec, handler = setup_policy
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", port))])
    with httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail("private request"))) as client:
        policy = verify_policy(ws, venue, path, client=client)
    assert policy.status == "review_needed"
    assert all(source.status == "failed" and "non-public" in source.error for source in policy.sources)


def test_redirect_to_unapproved_origin_is_blocked(setup_policy):
    ws, venue, path, spec, handler = setup_policy
    requests = []

    def redirect(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "https://attacker.example/policy"})

    with httpx.Client(transport=httpx.MockTransport(redirect)) as client:
        policy = verify_policy(ws, venue, path, client=client)
    assert policy.status == "review_needed"
    assert len(requests) == 2 and all(source.status == "failed" for source in policy.sources)


def test_linked_publisher_origin_requires_real_official_link_and_reviewed_excerpt(setup_policy):
    ws, venue, path, spec, handler = setup_policy
    spec["sources"].append("https://publisher.example/policy")
    spec["official_origins"] = [{"origin": "https://publisher.example", "rationale": "Journal links publisher policy", "evidence_url": "https://example.org/guidelines", "evidence_excerpt": "Official publisher policy"}]
    path.write_text(json.dumps(spec), encoding="utf-8")

    def linked(request):
        response = handler(request)
        return httpx.Response(200, text=response.text + '<a href="https://publisher.example/policy">Official publisher policy</a>', headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(linked)) as client:
        policy = verify_policy(ws, venue, path, client=client)
    assert policy.status == "verified" and len(policy.sources) == 3
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        blocked = verify_policy(ws, venue, path, client=client)
    assert blocked.status == "review_needed"
    assert any("verified journal-origin link" in issue for issue in blocked.issues)
    assert blocked.sources[-1].status == "failed"


def test_script_contents_and_absent_excerpt_do_not_support_policy(setup_policy):
    ws, venue, path, spec, handler = setup_policy
    spec["evidence"]["ai_policy"]["excerpt"] = "This quotation occurs only inside JavaScript."
    path.write_text(json.dumps(spec), encoding="utf-8")

    def scripted(request):
        return httpx.Response(200, text=handler(request).text + '<script>This quotation occurs only inside JavaScript.</script>', headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(scripted)) as client:
        policy = verify_policy(ws, venue, path, client=client)
    assert policy.status == "review_needed"
    assert "ai_policy" in " ".join(policy.issues)


def test_invalid_typed_policies_cannot_be_converted_into_ready_facts():
    with pytest.raises(ValueError):
        PolicyValues(ai_use_allowed="yes")
    with pytest.raises(ValueError):
        PolicyValues(apc={"status": "charged", "amount": 100, "currency": "made-up"})
    with pytest.raises(ValueError):
        PolicySpec(venue_id="venue-test", evidence={"fabricated": {"source_url": "https://example.org", "excerpt": "Official excerpt here", "interpretation": "Test"}})


@pytest.mark.parametrize("field", ["values", "evidence", "reviewed_by", "ttl_days", "venue_id", "sources", "official_origins"])
def test_rehashed_policy_record_cannot_override_its_reviewed_specification(setup_policy, field):
    ws, venue, path, _, handler = setup_policy
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        policy = verify_policy(ws, venue, path, client=client)
    original_spec = ws.path(policy.spec_path).read_bytes()
    if field == "values":
        policy.values.anonymization_required = True
    elif field == "evidence":
        policy.evidence["ai_policy"].interpretation = "An unreviewed replacement interpretation."
    elif field == "sources":
        policy.sources = policy.sources[:-1]
    elif field == "official_origins":
        policy.official_origins = [{"origin": "https://unreviewed.example.org", "rationale": "Unreviewed added authority",
            "evidence_url": "https://example.org/guidelines", "evidence_excerpt": "An unreviewed publisher origin"}]
    else:
        setattr(policy, field, {"reviewed_by": "Unreviewed Researcher", "ttl_days": 30, "venue_id": "venue-other"}[field])
    write_json(ws.path(policy.receipt_path), policy.model_dump(mode="json", exclude={"receipt_sha256"}))
    policy.receipt_sha256 = digest_file(ws.path(policy.receipt_path))
    ws.save("policy", policy)
    assert ws.path(policy.spec_path).read_bytes() == original_spec
    assert validate_policy(ws, policy)
    assert validate_policy(ws, policy, check_compliance=False)

"""Provider tests use conspicuous synthetic credentials and MockTransport only."""

from contextlib import contextmanager
import hashlib
import json
import socket

import httpx
from pydantic import ValidationError
import pytest

from paper_factory import ojs
from paper_factory.ojs import (
    OJSAffiliation, OJSClient, OJSContributor, OJSDraft, OJSError,
    OJSKeyword, OJSPublicationMetadata, OJSSettings,
)

TOKEN = "synthetic-test-token-never-a-real-credential"
API = "https://journal.example.org/index.php/journal/api/v1"


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, **kwargs:
                        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))])


@contextmanager
def provider(handler):
    with httpx.Client(transport=httpx.MockTransport(handler), trust_env=False) as transport:
        with OJSClient(OJSSettings(api_url=API), TOKEN, client=transport) as client:
            yield client


def submission(**changes):
    result = {"id": 12, "currentPublicationId": 34, "status": 1,
              "submissionProgress": "start", "locale": "en", "dateSubmitted": None,
              "publications": [{"id": 34, "submissionId": 12, "title": {"en": "Synthetic manuscript"}}]}
    return result | changes


def publication(**changes):
    return {"id": 34, "submissionId": 12, "title": {"en": "Synthetic manuscript"},
            "abstract": {"en": "Synthetic abstract"}, "authors": []} | changes


def remote_file(**changes):
    return {"id": 56, "fileId": 78, "submissionId": 12, "fileStage": 2,
            "genreId": 5, "name": {"en": "manuscript.pdf"}} | changes


def contributor(**changes):
    return {"id": 90, "publicationId": 34, "givenName": {"en": "Synthetic"},
            "familyName": {"en": "Author"}, "email": "synthetic@example.org",
            "userGroupId": 6, "affiliations": []} | changes


def test_exact_official_vertical_routes_and_payloads(tmp_path):
    path = tmp_path / "manuscript.pdf"
    path.write_bytes(b"synthetic PDF fixture bytes")
    observed = []

    def handler(request):
        assert request.url.host == "93.184.216.34"
        assert request.headers["Host"] == "journal.example.org"
        assert request.extensions["sni_hostname"] == "journal.example.org"
        assert request.headers["Authorization"] == "Bearer " + TOKEN
        assert request.headers["Accept-Encoding"] == "identity"
        prefix = "/index.php/journal/api/v1"
        route = request.url.path.removeprefix(prefix)
        observed.append((request.method, route))
        if route == "/submissions":
            assert request.method == "POST"
            assert json.loads(request.content) == {"sectionId": 7, "locale": "en", "userGroupId": 6}
            return httpx.Response(200, json=submission())
        if route == "/submissions/12":
            assert request.method == "GET"
            return httpx.Response(200, json=submission())
        if route == "/submissions/12/files":
            if request.method == "POST":
                content = request.read()
                assert b'name="file"; filename="manuscript.pdf"' in content
                assert path.read_bytes() in content
                assert b'name="fileStage"\r\n\r\n2' in content
                assert b'name="genreId"\r\n\r\n5' in content
                return httpx.Response(200, json=remote_file())
            return httpx.Response(200, json={"itemsMax": 1, "items": [remote_file()]})
        if route == "/submissions/12/publications/34":
            if request.method == "PUT":
                assert json.loads(request.content) == {"title": {"en": "Synthetic manuscript"}, "abstract": {"en": "Synthetic abstract"}, "keywords": {"en": [{"name": "synthetic"}]}}
            return httpx.Response(200, json=publication())
        if route == "/submissions/12/publications/34/contributors":
            return httpx.Response(200, json={"itemsMax": 1, "items": [contributor()]})
        assert route == "/submissions/12/submit" and request.method == "PUT"
        payload = json.loads(request.content)
        if payload == {"_validateOnly": True}:
            return httpx.Response(200, json=[])
        assert payload == {"confirmCopyright": True}
        return httpx.Response(200, json=submission(submissionProgress="", dateSubmitted="2026-09-30 09:00:00"))

    with provider(handler) as client:
        draft = client.create_draft(OJSDraft(sectionId=7, locale="en", userGroupId=6))
        assert draft.submission_id == 12 and draft.publication_id == 34
        assert client.get_submission(12).data["submissionProgress"] == "start"
        uploaded = client.upload_file(12, path, 5)
        assert uploaded.file_id == 56 and uploaded.data["fileId"] == 78
        assert uploaded.upload_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
        assert client.get_submission_files(12).data["items"][0]["id"] == 56
        metadata = OJSPublicationMetadata(title={"en": "Synthetic manuscript"}, abstract={"en": "Synthetic abstract"}, keywords={"en": [OJSKeyword(name="synthetic")]})
        assert client.update_publication(12, 34, metadata).publication_id == 34
        assert client.get_publication(12, 34).data["abstract"]["en"] == "Synthetic abstract"
        assert client.get_contributors(12, 34).data["items"][0]["email"] == "synthetic@example.org"
        assert client.validate_submission(12).data == []
        final = client.final_submit(12, approved=True, confirm_copyright=True)
        assert final.data["submissionProgress"] == "" and final.data["dateSubmitted"] == "2026-09-30 09:00:00"
        assert final.received_at.endswith("+00:00")
    assert observed[-2:] == [("PUT", "/submissions/12/submit"), ("PUT", "/submissions/12/submit")]


def test_explicit_contributor_create_update_fields_and_binding():
    calls = []
    author = OJSContributor(givenName={"en": "Synthetic"}, familyName={"en": "Author"},
                            email="synthetic@example.org", userGroupId=6, affiliations=[],
                            competingInterests={"en": "Synthetic test declaration"})

    def handler(request):
        data = json.loads(request.content)
        calls.append((request.method, request.url.path, data))
        if request.method == "POST":
            assert data.pop("orcid") is None
        assert data == author.model_dump(exclude_none=True)
        return httpx.Response(200, json=contributor())

    with provider(handler) as client:
        assert client.create_contributor(12, 34, author).contributor_id == 90
        assert client.update_contributor(12, 34, 90, author).contributor_id == 90
    assert [call[0] for call in calls] == ["POST", "PUT"]


@pytest.mark.parametrize("url", ["http://journal.example.org/api/v1", "https://localhost/api/v1",
    "https://127.0.0.1/api/v1", "https://10.1.2.3/api/v1", "https://journal.local/api/v1",
    "https://user:secret@journal.example.org/api/v1", "https://journal.example.org:444/api/v1",
    "https://journal.example.org/api/v1?token=secret", "https://journal.example.org/api/v1#fragment",
    "https://journal.example.org/../api/v1", "https://journal.example.org/%2e%2e/api/v1",
    "https://journal.example.org//api/v1", "https://journal.example.org/api/v2"])
def test_unsafe_or_non_api_configuration_rejected(url):
    with pytest.raises(ValidationError):
        OJSSettings(api_url=url)


def test_only_explicit_version_secret_reference_and_writable_fields():
    settings = OJSSettings(api_url=API + "/")
    assert settings.api_url == API and TOKEN not in settings.model_dump_json()
    for change in [{"version": "3.4"}, {"token_env": "HOME"}, {"token": TOKEN}]:
        with pytest.raises(ValidationError):
            OJSSettings(api_url=API, **change)
    for payload in [{"sectionId": True, "locale": "en"}, {"sectionId": 7, "locale": "en", "submissionProgress": ""}, {"sectionId": 7, "locale": "not/a/locale"}]:
        with pytest.raises(ValidationError):
            OJSDraft.model_validate(payload)
    for payload in [{"authors": []}, {"status": 3}, {"title": {"en": "line\nbreak"}}, {}]:
        with pytest.raises(ValidationError):
            OJSPublicationMetadata.model_validate(payload)
    with pytest.raises(ValidationError):
        OJSAffiliation(name={"en": "Synthetic institute"}, ror="https://example.org/invalid")


@pytest.mark.parametrize("address", ["127.0.0.1", "10.1.2.3", "::1", "169.254.169.254"])
def test_private_dns_stops_before_provider_call(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, **kwargs:
                        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))])
    with provider(lambda request: pytest.fail("Private provider call must not occur")) as client:
        with pytest.raises(OJSError, match="public_destination_check_failed") as caught:
            client.create_draft(OJSDraft(sectionId=7, locale="en"))
    assert not caught.value.reconciliation_required


def test_mixed_dns_and_rebinding_is_not_followed(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, **kwargs:
        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ("93.184.216.34", "127.0.0.1")])
    with provider(lambda request: pytest.fail("Mixed DNS must not be used")) as client:
        with pytest.raises(OJSError):
            client.get_submission(12)


def test_redirect_never_forwards_credential_and_write_requires_reconcile():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(307, headers={"location": "https://other.example.org/steal?token=" + TOKEN})
    with provider(handler) as client:
        with pytest.raises(OJSError, match="redirect_forbidden") as caught:
            client.create_draft(OJSDraft(sectionId=7, locale="en"))
    assert len(calls) == 1 and caught.value.reconciliation_required
    assert TOKEN not in str(caught.value)


@pytest.mark.parametrize("status, uncertain", [(201, True), (202, True), (204, True), (400, False), (401, False), (403, False), (404, False), (500, True), (503, True)])
def test_provider_failure_redacts_every_error_and_never_retries(status, uncertain):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"title": ["Request payload and bearer " + TOKEN], "apiToken": TOKEN, TOKEN: TOKEN})
    with provider(handler) as client:
        with pytest.raises(OJSError) as caught:
            client.create_draft(OJSDraft(sectionId=7, locale="en"))
    error = caught.value
    assert len(calls) == 1 and error.status_code == status and error.reconciliation_required is uncertain
    assert error.validation_fields == (("title",) if status == 400 else ())
    assert TOKEN not in repr(error) and "Request payload" not in str(error)


def test_partial_contributor_400_requires_reconciliation():
    with provider(lambda request: httpx.Response(400, json={"affiliations": ["Synthetic rejected affiliation"]})) as client:
        with pytest.raises(OJSError) as caught:
            client.create_contributor(12, 34, OJSContributor(givenName={"en": "Synthetic"}, email="synthetic@example.org", userGroupId=6, affiliations=[]))
    assert caught.value.reconciliation_required and caught.value.validation_fields == ("affiliations",)


def test_timeout_write_is_ambiguous_without_secret_or_retry():
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("Synthetic transport echoed " + TOKEN, request=request)
    with provider(handler) as client:
        with pytest.raises(OJSError) as caught:
            client.create_draft(OJSDraft(sectionId=7, locale="en"))
    assert len(calls) == 1 and caught.value.reconciliation_required
    assert TOKEN not in str(caught.value) and caught.value.__suppress_context__


@pytest.mark.parametrize("body", [b"<html>credential</html>", b'{"id":12,"id":13}', b'{"id":NaN}', b'"not-an-object"'])
def test_malformed_success_is_ambiguous_write(body):
    with provider(lambda request: httpx.Response(200, content=body)) as client:
        with pytest.raises(OJSError, match="invalid_provider_json") as caught:
            client.create_draft(OJSDraft(sectionId=7, locale="en"))
    assert caught.value.reconciliation_required


def test_success_receipt_preserves_metadata_and_redacts_known_secrets():
    raw = submission(extra={"apiKey": "another secret", "password": "another password",
                           "authors": [{"givenName": {"en": "Synthetic"}, "orcidAccessToken": "other token"}],
                           "literal": "Echo " + TOKEN})
    with provider(lambda request: httpx.Response(200, json=raw)) as client:
        receipt = client.get_submission(12)
    assert receipt.data["locale"] == "en"
    extra = receipt.data["extra"]
    assert extra["apiKey"] == extra["password"] == "[REDACTED]"
    assert extra["authors"][0]["orcidAccessToken"] == "[REDACTED]"
    assert extra["literal"] == "Echo [REDACTED]" and TOKEN not in receipt.model_dump_json()


@pytest.mark.parametrize("body, headers", [(b"x" * 81, {}), (b"{}", {"content-length": "81"}),
                                         (b"{}", {"content-length": "garbage"}), (b"{}", {"content-encoding": "gzip"})])
def test_bounded_uncompressed_response(monkeypatch, body, headers):
    monkeypatch.setattr(ojs, "MAX_SOURCE_BYTES", 80)
    with provider(lambda request: httpx.Response(200, content=body, headers=headers)) as client:
        with pytest.raises(OJSError) as caught:
            client.create_draft(OJSDraft(sectionId=7, locale="en"))
    assert caught.value.reconciliation_required


@pytest.mark.parametrize("changes", [{"id": 13}, {"id": True}, {"currentPublicationId": None},
                                    {"submissionProgress": "unknown"}, {"status": True}])
def test_remote_submission_binding_and_supported_feature_shape(changes):
    with provider(lambda request: httpx.Response(200, json=submission(**changes))) as client:
        with pytest.raises(OJSError, match="unsupported_or_mismatched_submission_response"):
            client.get_submission(12)


@pytest.mark.parametrize("items, count", [([remote_file(submissionId=13)], 1), ([remote_file(), remote_file()], 2), ([], 1), ([remote_file(id=True)], 1)])
def test_collection_members_and_count_fail_closed(items, count):
    with provider(lambda request: httpx.Response(200, json={"itemsMax": count, "items": items})) as client:
        with pytest.raises(OJSError):
            client.get_submission_files(12)


def test_final_submit_requires_explicit_boolean_approval():
    with provider(lambda request: pytest.fail("Unapproved final submit must not call provider")) as client:
        for approved in (False, None, 1, "true"):
            with pytest.raises(OJSError, match="explicit_final_submission_approval_required"):
                client.final_submit(12, approved=approved)


def test_final_submit_validation_failure_blocks_final_write():
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(400, json={"files": ["Synthetic required genre missing"]})
    with provider(handler) as client:
        with pytest.raises(OJSError) as caught:
            client.final_submit(12, approved=True)
    assert calls == [{"_validateOnly": True}] and not caught.value.reconciliation_required


def test_wrong_validation_response_may_have_ignored_validate_only():
    with provider(lambda request: httpx.Response(200, json=submission(submissionProgress="", dateSubmitted="2026-09-30 09:00:00"))) as client:
        with pytest.raises(OJSError, match="unsupported_validation_response") as caught:
            client.validate_submission(12)
    assert caught.value.reconciliation_required


@pytest.mark.parametrize("result", [submission(), submission(submissionProgress="", dateSubmitted=None), submission(id=13, submissionProgress="", dateSubmitted="2026-09-30 09:00:00")])
def test_final_receipt_must_show_same_id_and_completed_submission(result):
    calls = []
    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, json=[] if body.get("_validateOnly") else result)
    with provider(handler) as client:
        with pytest.raises(OJSError, match="unsupported_or_mismatched_submission_response") as caught:
            client.final_submit(12, approved=True)
    assert calls == [{"_validateOnly": True}, {}] and caught.value.reconciliation_required


def test_upload_caps_unsupported_stage_and_provider_mismatch(tmp_path, monkeypatch):
    path = tmp_path / "manuscript.pdf"
    path.write_bytes(b"fixture")
    monkeypatch.setattr(ojs, "MAX_UPLOAD_BYTES", 6)
    with provider(lambda request: pytest.fail("Invalid upload must not call provider")) as client:
        with pytest.raises(OJSError, match="upload_file_invalid_or_too_large"):
            client.upload_file(12, path, 5)
        with pytest.raises(OJSError, match="unsupported_author_upload_stage"):
            client.upload_file(12, path, 5, file_stage=15)
    monkeypatch.setattr(ojs, "MAX_UPLOAD_BYTES", 20)
    with provider(lambda request: httpx.Response(200, json=remote_file(genreId=6))) as client:
        with pytest.raises(OJSError, match="mismatched_uploaded_file_response") as caught:
            client.upload_file(12, path, 5)
    assert caught.value.reconciliation_required


def test_upload_link_is_rejected_before_read(tmp_path, monkeypatch):
    path = tmp_path / "manuscript.pdf"
    path.write_bytes(b"fixture")
    monkeypatch.setattr(ojs, "ensure_unlinked", lambda path: (_ for _ in ()).throw(ValueError("Synthetic linked file")))
    with provider(lambda request: pytest.fail("Linked upload must not call provider")) as client:
        with pytest.raises(OJSError, match="upload_file_invalid_or_too_large"):
            client.upload_file(12, path, 5)


def test_live_client_enforces_tls_no_proxy_and_context_closes_secret(monkeypatch):
    actual_client = httpx.Client
    received = []
    def factory(**kwargs):
        received.append(kwargs)
        return actual_client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=submission())), trust_env=False)
    monkeypatch.setattr(ojs.httpx, "Client", factory)
    with OJSClient(OJSSettings(api_url=API), TOKEN) as client:
        assert client.get_submission(12).submission_id == 12
    assert received == [{"verify": True, "trust_env": False, "follow_redirects": False, "timeout": 20}]
    assert client._token == "" and client._client.is_closed
    with pytest.raises(OJSError, match="client_closed"):
        client.get_submission(12)


def test_injected_real_transport_is_not_a_tls_proxy_escape():
    with httpx.Client(verify=False, trust_env=False) as insecure:
        with pytest.raises(OJSError, match="injected_client_must_use_only_mock_transport"):
            OJSClient(OJSSettings(api_url=API), TOKEN, client=insecure)


@pytest.mark.parametrize("token", ["", "Bearer credential", "credential\r\nInjected: secret", "x" * 8193])
def test_bad_credentials_fail_without_echo(token):
    with pytest.raises(OJSError, match="invalid_bearer_credential") as caught:
        OJSClient(OJSSettings(api_url=API), token)
    assert token not in str(caught.value) if token else True

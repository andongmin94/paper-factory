"""Behavioral checks of the independent public-ORCID script; no network calls."""

import copy
from email.message import Message
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/lookup_orcid.py"
spec = importlib.util.spec_from_file_location("skill_orcid", SCRIPT)
orcid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orcid)
ID = "0009-0009-8671-9967"
WHEN = "2026-10-28T04:00:00+00:00"


def records():
    return {
        "person": {"path": f"/{ID}/person", "name": {"visibility": "public", "given-names": {"value": "Sanghoon"}, "family-name": {"value": "Kim"}}, "emails": {"email": []}},
        "employments": {"path": f"/{ID}/employments", "affiliation-group": []},
        "educations": {"path": f"/{ID}/educations", "affiliation-group": []},
    }


class Response(io.BytesIO):
    def __init__(self, url, payload, *, mime="application/json", length=None):
        super().__init__(payload)
        self.status = 200
        self.url = url
        self.headers = Message()
        self.headers["Content-Type"] = mime
        if length is not None:
            self.headers["Content-Length"] = str(length)

    def geturl(self):
        return self.url


class FakeOpener:
    def __init__(self, data=None, responder=None):
        self.data = data or records()
        self.responder = responder
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        if self.responder:
            return self.responder(request)
        return Response(request.full_url, json.dumps(self.data[request.full_url.rsplit("/", 1)[-1]]).encode())


@pytest.mark.parametrize("value,expected", [(ID, ID), (f" https://orcid.org/{ID}/ ", ID), ("0000-0002-1694-233x", "0000-0002-1694-233X"), (f"https://orcid.org/my-orcid?orcid={ID}", ID)])
def test_normalizes_public_identity_without_fetching_account_page(value, expected):
    assert orcid.normalize_orcid_input(value) == expected


@pytest.mark.parametrize("value", [None, {}, "", "0009-0009-8671-9966", f"http://orcid.org/{ID}", f"https://user:secret@orcid.org/{ID}", f"https://orcid.org/{ID}?token=secret", f"https://orcid.org/{ID}#private", f"https://example.org/{ID}", f"https://orcid.org/my-orcid?orcid={ID}&token=secret", f"https://orcid.org/my-orcid?orcid={ID}&orcid={ID}", ID + "\nsecret"])
def test_invalid_identity_never_reaches_network(value):
    opener = FakeOpener()
    with pytest.raises(orcid.OrcidLookupError):
        orcid.lookup_public_orcid(value, opener=opener)
    assert opener.calls == []


@pytest.mark.parametrize("decimal_digits", ["０１２３４５６７８９", "٠١٢٣٤٥٦٧٨٩", "०१२३४५६७८९"])
@pytest.mark.parametrize("wrapper", ["{}", "https://orcid.org/{}", "https://orcid.org/my-orcid?orcid={}"])
def test_non_ascii_decimal_identity_is_rejected_before_network(decimal_digits, wrapper):
    # Keep the valid ASCII check digit: the old Unicode \d pattern accepted this.
    noncanonical = ID[:-1].translate(str.maketrans("0123456789", decimal_digits)) + ID[-1]
    opener = FakeOpener()
    with pytest.raises(orcid.OrcidLookupError):
        orcid.lookup_public_orcid(wrapper.format(noncanonical), opener=opener)
    assert opener.calls == []


def test_only_three_fixed_anonymous_endpoints_and_missing_fields_are_honest():
    opener = FakeOpener()
    result = orcid.lookup_public_orcid(f"https://orcid.org/my-orcid?orcid={ID}", opener=opener, retrieved_at=WHEN)
    assert [req.full_url for req, _ in opener.calls] == [f"https://pub.orcid.org/v3.0/{ID}/{part}" for part in orcid.SECTIONS]
    assert all(0 < timeout <= 20 for _, timeout in opener.calls)
    assert all("Authorization" not in req.headers and "Cookie" not in req.headers for req, _ in opener.calls)
    assert result["display_name"] == "Sanghoon Kim"
    assert result["emails"] == [] and result["affiliations"] == [] and result["biography"] is None
    assert result["missing_public_fields"] == ["emails", "biography", "affiliations"]
    assert result["public_only"] is True and result["authenticated"] is False
    assert result["author_confirmation_required"] is True
    assert "funding" not in result and "approved" not in result


def test_private_name_bio_and_unverified_or_private_email_are_not_returned():
    data = records()
    data["person"]["name"]["credit-name"] = {"value": "  Public Credit Name "}
    data["person"]["emails"]["email"] = [
        {"email": "public@example.org", "visibility": "PUBLIC", "verified": True},
        {"email": "public@example.org", "visibility": "public", "verified": True},
        {"email": "secret@example.org", "visibility": "private", "verified": True},
        {"email": "unverified@example.org", "visibility": "public", "verified": False},
        {"email": "bad mail@example.org", "visibility": "public", "verified": True},
    ]
    data["person"]["biography"] = {"visibility": "public", "content": "Paragraph one.\nParagraph two."}
    result = orcid.lookup_public_orcid(ID, opener=FakeOpener(data), retrieved_at=WHEN)
    assert result["display_name"] == "Public Credit Name"
    assert result["emails"] == ["public@example.org"]
    assert result["biography"] == "Paragraph one.\nParagraph two."
    data["person"]["name"]["visibility"] = "limited"
    data["person"]["biography"]["visibility"] = "private"
    result = orcid.lookup_public_orcid(ID, opener=FakeOpener(data), retrieved_at=WHEN)
    assert result["display_name"] is result["given_name"] is result["family_name"] is result["biography"] is None


def affiliation(code, **changes):
    value = {"put-code": code, "path": f"/{ID}/employment/{code}", "visibility": "public", "organization": {"name": "University", "address": {"city": "Andong", "country": "KR"}}, "start-date": None, "end-date": None}
    value.update(changes)
    return {"employment-summary": value}


def test_public_affiliation_dates_are_retained_without_inventing_current_status():
    data = records()
    data["employments"]["affiliation-group"] = [{"summaries": [
        affiliation(1, **{"role-title": "Researcher", "start-date": {"year": {"value": "2020"}}}),
        affiliation(2, **{"end-date": {"year": {"value": "2001"}}}),
        affiliation(3, **{"start-date": {"year": {"value": "2099"}}}),
        affiliation(4, visibility="private"),
        affiliation(5, path="/different/employment/5"),
        affiliation(6, **{"start-date": {"year": {"value": "2020"}, "month": {"value": "02"}, "day": {"value": "31"}}}),
    ]}]
    result = orcid.lookup_public_orcid(ID, opener=FakeOpener(data), retrieved_at=WHEN)
    assert [v["id"] for v in result["affiliations"]] == ["employment-1", "employment-2", "employment-3"]
    assert [v["date_status"] for v in result["affiliations"]] == ["not_recorded_as_ended", "past", "future"]
    assert result["affiliations"][0]["start_date"] == "2020"
    assert result["affiliations"][0]["city"] == "Andong" and result["affiliations"][0]["country"] == "KR"
    assert result["affiliations"][0]["department"] is None
    assert "current" not in result["affiliations"][0]


@pytest.mark.parametrize("response", [
    lambda url: Response(url, b"SECRET_BODY", mime="text/html"),
    lambda url: Response(url, b"SECRET_BODY"),
    lambda url: Response(url, b'{}'),
    lambda url: Response(url, json.dumps({"path": "/different/person"}).encode()),
    lambda url: Response("https://example.org/redirect", b'{}'),
    lambda url: Response(url, b'{}', length=1024 * 1024 + 1),
    lambda url: Response(url, b" " * (1024 * 1024 + 1)),
])
def test_malformed_or_oversized_response_is_rejected_without_body_leak(response):
    with pytest.raises(orcid.OrcidLookupError) as error:
        orcid.lookup_public_orcid(ID, opener=FakeOpener(responder=lambda request: response(request.full_url)))
    assert "SECRET_BODY" not in str(error.value)


@pytest.mark.parametrize("failure", [HTTPError("https://pub.orcid.org", 404, "SECRET", {}, None), HTTPError("https://pub.orcid.org", 302, "SECRET", {}, None), HTTPError("https://pub.orcid.org", 429, "SECRET", {}, None), URLError("https://user:SECRET@proxy.invalid"), TimeoutError("SECRET_TIMEOUT")])
def test_http_and_transport_errors_are_controlled(failure):
    def fail(_):
        raise failure
    with pytest.raises(orcid.OrcidLookupError) as error:
        orcid.lookup_public_orcid(ID, opener=FakeOpener(responder=fail))
    assert "SECRET" not in str(error.value)


def test_default_opener_rejects_redirect_before_another_network_request(monkeypatch):
    opener = build_opener(orcid._NoRedirects())
    request = Request(f"https://pub.orcid.org/v3.0/{ID}/person")
    request.timeout = 20
    headers = Message()
    headers["Location"] = "https://example.org/should-not-be-requested"
    monkeypatch.setattr(opener, "open", lambda *_args, **_kwargs: pytest.fail("redirect must not issue a request"))
    with pytest.raises(HTTPError) as error:
        opener.error("http", request, io.BytesIO(b"not JSON"), 302, "Found", headers)
    assert error.value.code == 302


def test_expired_lookup_budget_does_not_accept_or_continue_responses(monkeypatch):
    ticks = iter([0, 0.5, 21])
    monkeypatch.setattr(orcid.time, "monotonic", lambda: next(ticks))
    opener = FakeOpener()
    with pytest.raises(orcid.OrcidLookupError, match="timed out"):
        orcid.lookup_public_orcid(ID, opener=opener)
    assert len(opener.calls) == 1


def test_cli_refuses_existing_output_before_lookup(tmp_path, monkeypatch, capsys):
    target = tmp_path / "author.json"
    target.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(orcid, "lookup_public_orcid", lambda *_: pytest.fail("network should not be reached"))
    assert orcid.main([ID, "--output", str(target)]) == 2
    assert target.read_text(encoding="utf-8") == "keep"
    assert "error" in json.loads(capsys.readouterr().err)


def test_cli_retains_exact_public_json_and_outputs_stdout(tmp_path, monkeypatch, capsys):
    target = tmp_path / "author.json"
    result = orcid.lookup_public_orcid(ID, opener=FakeOpener(), retrieved_at=WHEN)
    monkeypatch.setattr(orcid, "lookup_public_orcid", lambda _: copy.deepcopy(result))
    assert orcid.main([ID, "--output", str(target)]) == 0
    assert json.loads(target.read_text(encoding="utf-8")) == result
    assert json.loads(capsys.readouterr().out) == result


def test_script_runs_from_an_unrelated_location_without_old_checkout(tmp_path):
    copied = tmp_path / "lookup_orcid.py"
    copied.write_bytes(SCRIPT.read_bytes())
    run = subprocess.run([sys.executable, "-I", str(copied), "--help"], cwd=tmp_path,
                         capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    assert "ORCID" in run.stdout and "--output" in run.stdout

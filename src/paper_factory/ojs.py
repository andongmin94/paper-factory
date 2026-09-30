"""Narrow author submission client for the pinned official OJS 3.5 API.

This module performs provider calls, not local publication state transitions.
Callers must bind final approval to the exact journal, metadata and file bytes.
No write is retried: an ambiguous outcome requires provider reconciliation.
"""

from datetime import datetime, timezone
import hashlib
import json
import mimetypes
from pathlib import Path
import re
from typing import Annotated, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import __version__
from .venue_policy import MAX_SOURCE_BYTES, _origin, _public_ip
from .workspace import ensure_unlinked

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
OJS_COMMIT = "040e9163780bcf9ca5c614d8588688f6c324d4da"
PKP_COMMIT = "8809a197de7c5f677428172bf5e6b4a5013460d6"
PositiveId = Annotated[int, Field(strict=True, gt=0)]
_LOCALE = re.compile(r"[A-Za-z]{2,4}(?:[_-](?:[A-Za-z]{4,5}|[0-9]{4}))?(?:[_-](?:[A-Za-z]{2}|[0-9]{3}))?(?:@[a-z]{2,30}(?:[_-](?:[A-Za-z]{4,5}|[0-9]{4}))?)?")
_PROGRESS = {"", "start", "details", "files", "contributors", "editors", "review"}
_VALIDATION_FIELDS = {"title", "abstract", "contributors", "files", "sectionId", "userGroupId", "locale", "keywords", "citations", "agencies", "subjects", "disciplines", "coverage", "rights", "languages", "type", "source", "supportingAgencies", "primaryContactId", "givenName", "familyName", "email", "affiliations", "genreId", "fileStage", "name"}


def _locale(value: str) -> str:
    if not isinstance(value, str) or not _LOCALE.fullmatch(value):
        raise ValueError("OJS locale must be an explicitly reviewed locale code")
    return value


class _APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class OJSSettings(_APIModel):
    api_url: str
    version: Literal["3.5"] = "3.5"
    token_env: str = "PF_OJS_API_TOKEN"

    @field_validator("api_url")
    @classmethod
    def public_journal_api(cls, value: str) -> str:
        _origin(value)
        parsed = urlsplit(value)
        path = parsed.path.rstrip("/")
        if (parsed.query or parsed.fragment or not path.endswith("/api/v1") or
                "%" in path or any(part in {".", ".."} for part in path.split("/")) or
                "//" in path or any(character.isspace() for character in value)):
            raise ValueError("OJS URL must be an exact public journal HTTPS /api/v1 endpoint")
        return value.rstrip("/")

    @field_validator("token_env")
    @classmethod
    def secret_reference(cls, value: str) -> str:
        if not re.fullmatch(r"PF_OJS_[A-Z0-9_]{1,100}", value):
            raise ValueError("OJS credentials must be referenced by a PF_OJS_ environment variable")
        return value


class OJSDraft(_APIModel):
    sectionId: PositiveId
    locale: str
    userGroupId: PositiveId | None = None

    _valid_locale = field_validator("locale")(_locale)


class OJSKeyword(_APIModel):
    name: str = Field(min_length=1, max_length=500)
    source: str | None = Field(default=None, max_length=2000)
    identifier: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def readable(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("OJS keyword cannot be whitespace")
        return value


class OJSPublicationMetadata(_APIModel):
    title: dict[str, str] | None = None
    abstract: dict[str, str] | None = None
    keywords: dict[str, list[OJSKeyword]] | None = None
    primaryContactId: PositiveId | None = None

    @model_validator(mode="after")
    def bounded_metadata(self):
        if all(getattr(self, name) is None for name in type(self).model_fields):
            raise ValueError("OJS metadata update must contain a reviewed field")
        for name in ("title", "abstract", "keywords"):
            value = getattr(self, name)
            if value is None:
                continue
            if not value or len(value) > 20:
                raise ValueError("OJS multilingual metadata must contain 1 to 20 locales")
            for locale, item in value.items():
                _locale(locale)
                if name == "keywords":
                    if len(item) > 100:
                        raise ValueError("OJS keyword list exceeds the client limit")
                elif not item.strip() or len(item) > (2000 if name == "title" else 100000):
                    raise ValueError("OJS title or abstract is empty or exceeds the client limit")
                elif name == "title" and any(c in item for c in "\r\n"):
                    raise ValueError("OJS titles must not contain new lines")
        return self


def _multilingual(value: dict[str, str] | None):
    if value is None:
        return value
    if not value or len(value) > 20:
        raise ValueError("OJS multilingual field needs 1 to 20 reviewed locales")
    for locale, text in value.items():
        _locale(locale)
        if not text.strip() or len(text) > 12000:
            raise ValueError("OJS multilingual field is empty or exceeds the client limit")
    return value


class OJSAffiliation(_APIModel):
    name: dict[str, str]
    ror: str | None = None

    _valid_name = field_validator("name")(_multilingual)

    @field_validator("ror")
    @classmethod
    def reviewed_ror(cls, value):
        if value is not None and not re.fullmatch(r"https://ror\.org/0[^ILOU\W_]{6}\d{2}", value):
            raise ValueError("OJS affiliation requires a valid reviewed ROR identifier")
        return value


class OJSContributor(_APIModel):
    givenName: dict[str, str]
    familyName: dict[str, str] | None = None
    email: str = Field(min_length=3, max_length=254)
    userGroupId: PositiveId
    affiliations: list[OJSAffiliation] = Field(max_length=50)
    preferredPublicName: dict[str, str] | None = None
    competingInterests: dict[str, str] | None = None
    includeInBrowse: bool = True
    seq: Annotated[int, Field(strict=True, ge=0)] | None = None

    _valid_names = field_validator("givenName", "familyName", "preferredPublicName", "competingInterests")(_multilingual)

    @field_validator("email")
    @classmethod
    def explicit_email(cls, value):
        if not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value):
            raise ValueError("OJS contributor requires an explicitly reviewed email address")
        return value


class OJSReceipt(_APIModel):
    method: str
    route: str
    status_code: int
    received_at: str
    data: dict | list
    submission_id: PositiveId | None = None
    publication_id: PositiveId | None = None
    file_id: PositiveId | None = None
    contributor_id: PositiveId | None = None
    upload_sha256: str | None = None


class OJSError(ValueError):
    """Safe failure metadata, deliberately excluding provider bodies/headers."""

    def __init__(self, code: str, *, status_code: int | None = None,
                 reconciliation_required: bool = False, validation_fields: tuple[str, ...] = ()):
        self.code = code
        self.status_code = status_code
        self.reconciliation_required = reconciliation_required
        self.validation_fields = validation_fields
        message = f"OJS request failed: {code}"
        if status_code is not None:
            message += f" (HTTP {status_code})"
        if validation_fields:
            message += "; validation fields: " + ", ".join(validation_fields)
        if reconciliation_required:
            message += "; the write may have succeeded: reconcile the provider record before another write"
        super().__init__(message)


def _positive(value: int) -> int:
    if type(value) is not int or value <= 0:
        raise OJSError("invalid_remote_identifier")
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _safe_json(value, token: str, depth: int = 0):
    if depth > 30:
        raise ValueError("Provider JSON nesting exceeds the client limit")
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            safe_key = key.replace(token, "[REDACTED]")
            normalized = re.sub(r"[^a-z]", "", key.lower())
            if any(part in normalized for part in ("password", "secret", "authorization", "cookie", "apikey", "token")):
                result[safe_key] = "[REDACTED]"
            else:
                result[safe_key] = _safe_json(item, token, depth + 1)
        return result
    if isinstance(value, list):
        return [_safe_json(item, token, depth + 1) for item in value]
    if isinstance(value, str):
        return value.replace(token, "[REDACTED]")
    return value


class OJSClient:
    def __init__(self, settings: OJSSettings, token: str, *, client: httpx.Client | None = None):
        if not isinstance(settings, OJSSettings):
            raise OJSError("invalid_settings")
        # Copy even frozen models: caller-owned nested values may otherwise change.
        self._settings = OJSSettings.model_validate(settings.model_dump())
        if not isinstance(token, str) or not 1 <= len(token) <= 8192 or not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token):
            raise OJSError("invalid_bearer_credential")
        # Injection is intentionally a test seam, never a proxy/TLS bypass.
        if client is not None and (not isinstance(client, httpx.Client) or
                not isinstance(client._transport, httpx.MockTransport) or client._mounts):
            raise OJSError("injected_client_must_use_only_mock_transport")
        self._token = token
        self._owned = client is None
        self._client = client or httpx.Client(verify=True, trust_env=False, follow_redirects=False, timeout=20)
        self._closed = False

    @property
    def settings(self) -> OJSSettings:
        return self._settings

    def __enter__(self):
        if self._closed:
            raise OJSError("client_closed")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        if self._owned:
            self._client.close()
        self._token = ""
        self._closed = True

    def _request(self, method: str, route: str, *, mutation: bool = False,
                 uncertain_rejection: bool = False,
                 payload: dict | None = None, data: dict | None = None, files: dict | None = None,
                 submission_id: int | None = None, publication_id: int | None = None,
                 file_id: int | None = None, upload_sha256: str | None = None) -> OJSReceipt:
        if self._closed:
            raise OJSError("client_closed")
        try:
            canonical = httpx.URL(self.settings.api_url + route)
            connection = canonical.copy_with(host=_public_ip(str(canonical)))
        except (ValueError, OSError, httpx.InvalidURL):
            raise OJSError("public_destination_check_failed") from None
        response_received = False
        status = None
        try:
            with self._client.stream(method, connection,
                    headers={"Host": canonical.host, "Authorization": "Bearer " + self._token,
                             "Accept": "application/json", "Accept-Encoding": "identity", "User-Agent": f"PaperFactory/{__version__}"},
                    extensions={"sni_hostname": canonical.host}, follow_redirects=False, timeout=20,
                    json=payload, data=data, files=files) as response:
                response_received = True
                status = response.status_code
                if response.url != connection:
                    raise OJSError("response_destination_mismatch", status_code=status, reconciliation_required=mutation)
                if 300 <= status < 400:
                    raise OJSError("redirect_forbidden", status_code=status, reconciliation_required=mutation)
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise OJSError("compressed_response_forbidden", status_code=status, reconciliation_required=mutation)
                declared_size = response.headers.get("content-length")
                if declared_size is not None and (not declared_size.isdecimal() or int(declared_size) > MAX_SOURCE_BYTES):
                    raise OJSError("response_size_limit", status_code=status, reconciliation_required=mutation)
                chunks = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_SOURCE_BYTES:
                        raise OJSError("response_size_limit", status_code=status, reconciliation_required=mutation)
                    chunks.append(chunk)
                body = b"".join(chunks)
                try:
                    parsed = json.loads(body, object_pairs_hook=_pairs,
                                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")))
                    if not isinstance(parsed, (dict, list)):
                        raise ValueError("Expected JSON object or list")
                    safe = _safe_json(parsed, self._token)
                except (ValueError, UnicodeError, RecursionError):
                    if status != 200:
                        raise OJSError("provider_rejected_request", status_code=status, reconciliation_required=mutation and (status < 400 or status >= 500 or uncertain_rejection)) from None
                    raise OJSError("invalid_provider_json", status_code=status, reconciliation_required=mutation) from None
                if status != 200:
                    fields = tuple(sorted(set(parsed) & _VALIDATION_FIELDS)) if status == 400 and isinstance(parsed, dict) else ()
                    raise OJSError("provider_rejected_request", status_code=status,
                                   reconciliation_required=mutation and (status < 400 or status >= 500 or uncertain_rejection), validation_fields=fields)
                return OJSReceipt(method=method, route=route, status_code=status,
                                  received_at=datetime.now(timezone.utc).isoformat(), data=safe,
                                  submission_id=submission_id, publication_id=publication_id,
                                  file_id=file_id, upload_sha256=upload_sha256)
        except OJSError:
            raise
        except (httpx.HTTPError, OSError, ValueError):
            # Timeout/connection errors do not prove a write was rejected.
            raise OJSError("provider_transport_failed", status_code=status if response_received else None,
                           reconciliation_required=mutation) from None

    @staticmethod
    def _submission(receipt: OJSReceipt, expected: int | None = None, *, draft: bool = False, submitted: bool = False) -> OJSReceipt:
        value = receipt.data
        valid = (isinstance(value, dict) and type(value.get("id")) is int and value["id"] > 0 and
                 type(value.get("currentPublicationId")) is int and value["currentPublicationId"] > 0 and
                 type(value.get("status")) is int and value["status"] in {1, 2, 3, 4, 5} and
                 isinstance(value.get("submissionProgress"), str) and value["submissionProgress"] in _PROGRESS and
                 isinstance(value.get("locale"), str) and _LOCALE.fullmatch(value["locale"]) is not None and
                 (expected is None or value["id"] == expected))
        if draft:
            valid = valid and value.get("status") == 1 and bool(value.get("submissionProgress")) and not value.get("dateSubmitted")
        if submitted:
            valid = valid and value.get("submissionProgress") == "" and isinstance(value.get("dateSubmitted"), str) and bool(value["dateSubmitted"].strip())
        if not valid:
            raise OJSError("unsupported_or_mismatched_submission_response", status_code=receipt.status_code,
                           reconciliation_required=receipt.method != "GET")
        return receipt.model_copy(update={"submission_id": value["id"], "publication_id": value["currentPublicationId"]})

    def get_submission(self, submission_id: int) -> OJSReceipt:
        submission_id = _positive(submission_id)
        return self._submission(self._request("GET", f"/submissions/{submission_id}", submission_id=submission_id), submission_id)

    def get_publication(self, submission_id: int, publication_id: int) -> OJSReceipt:
        submission_id, publication_id = _positive(submission_id), _positive(publication_id)
        receipt = self._request("GET", f"/submissions/{submission_id}/publications/{publication_id}",
                                submission_id=submission_id, publication_id=publication_id)
        return self._publication(receipt, submission_id, publication_id)

    @staticmethod
    def _publication(receipt: OJSReceipt, submission_id: int, publication_id: int) -> OJSReceipt:
        value = receipt.data
        if (not isinstance(value, dict) or type(value.get("id")) is not int or value["id"] != publication_id or
                type(value.get("submissionId")) is not int or value["submissionId"] != submission_id):
            raise OJSError("mismatched_publication_response", status_code=200, reconciliation_required=receipt.method != "GET")
        return receipt

    @staticmethod
    def _collection(receipt: OJSReceipt, foreign_key: str, parent_id: int) -> OJSReceipt:
        value = receipt.data
        if (not isinstance(value, dict) or type(value.get("itemsMax")) is not int or
                not isinstance(value.get("items"), list) or value["itemsMax"] != len(value["items"])):
            raise OJSError("unsupported_collection_response", status_code=200)
        identifiers = set()
        for item in value["items"]:
            if (not isinstance(item, dict) or type(item.get("id")) is not int or item["id"] <= 0 or
                    item["id"] in identifiers or type(item.get(foreign_key)) is not int or item[foreign_key] != parent_id):
                raise OJSError("mismatched_collection_item", status_code=200)
            identifiers.add(item["id"])
        return receipt

    def get_contributors(self, submission_id: int, publication_id: int) -> OJSReceipt:
        submission_id, publication_id = _positive(submission_id), _positive(publication_id)
        receipt = self._request("GET", f"/submissions/{submission_id}/publications/{publication_id}/contributors",
                                submission_id=submission_id, publication_id=publication_id)
        return self._collection(receipt, "publicationId", publication_id)

    def get_submission_files(self, submission_id: int) -> OJSReceipt:
        submission_id = _positive(submission_id)
        receipt = self._request("GET", f"/submissions/{submission_id}/files", submission_id=submission_id)
        return self._collection(receipt, "submissionId", submission_id)

    def create_draft(self, payload: OJSDraft) -> OJSReceipt:
        if not isinstance(payload, OJSDraft):
            raise OJSError("draft_requires_typed_reviewed_payload")
        receipt = self._submission(self._request("POST", "/submissions", mutation=True,
                                                payload=payload.model_dump(exclude_none=True)), draft=True)
        if receipt.data["locale"] != payload.locale:
            raise OJSError("draft_locale_mismatch", status_code=200, reconciliation_required=True)
        return receipt

    def upload_file(self, submission_id: int, path: Path, genre_id: int, file_stage: int = 2,
                    *, expected_sha256: str | None = None) -> OJSReceipt:
        submission_id, genre_id = _positive(submission_id), _positive(genre_id)
        if type(file_stage) is not int or file_stage != 2:
            raise OJSError("unsupported_author_upload_stage")
        if expected_sha256 is not None and (not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)):
            raise OJSError("invalid_expected_upload_digest")
        try:
            path = Path(path)
            ensure_unlinked(path)
            if not path.is_file() or not 0 < path.stat().st_size <= MAX_UPLOAD_BYTES or any(ord(c) < 32 for c in path.name):
                raise ValueError("Invalid upload")
            with path.open("rb") as stream:
                content = stream.read(MAX_UPLOAD_BYTES + 1)
            ensure_unlinked(path)
            if not 0 < len(content) <= MAX_UPLOAD_BYTES:
                raise ValueError("Invalid upload size")
        except (ValueError, OSError, TypeError):
            raise OJSError("upload_file_invalid_or_too_large") from None
        content_digest = hashlib.sha256(content).hexdigest()
        if expected_sha256 is not None and content_digest != expected_sha256:
            # HTTPX receives this immutable buffer, never a subsequently reopened
            # path. A changed file must be rejected before sending any bytes.
            raise OJSError("upload_bytes_differ_from_approved_digest")
        receipt = self._request("POST", f"/submissions/{submission_id}/files", mutation=True,
                                data={"fileStage": str(file_stage), "genreId": str(genre_id)},
                                files={"file": (path.name, content, mimetypes.guess_type(path.name)[0] or "application/octet-stream")},
                                submission_id=submission_id, upload_sha256=content_digest)
        value = receipt.data
        if (not isinstance(value, dict) or type(value.get("id")) is not int or value["id"] <= 0 or
                type(value.get("fileId")) is not int or value["fileId"] <= 0 or
                type(value.get("submissionId")) is not int or value["submissionId"] != submission_id or
                type(value.get("genreId")) is not int or value["genreId"] != genre_id or
                type(value.get("fileStage")) is not int or value["fileStage"] != file_stage):
            raise OJSError("mismatched_uploaded_file_response", status_code=200, reconciliation_required=True)
        # id identifies the submission-file API resource; fileId is storage data.
        return receipt.model_copy(update={"file_id": value["id"]})

    def update_publication(self, submission_id: int, publication_id: int, metadata: OJSPublicationMetadata) -> OJSReceipt:
        submission_id, publication_id = _positive(submission_id), _positive(publication_id)
        if not isinstance(metadata, OJSPublicationMetadata):
            raise OJSError("publication_requires_typed_reviewed_metadata")
        payload = metadata.model_dump(exclude_none=True)
        receipt = self._request("PUT", f"/submissions/{submission_id}/publications/{publication_id}", mutation=True,
                                payload=payload, submission_id=submission_id, publication_id=publication_id)
        return self._publication(receipt, submission_id, publication_id)

    @staticmethod
    def _contributor(receipt: OJSReceipt, publication_id: int, expected: int | None = None) -> OJSReceipt:
        value = receipt.data
        if (not isinstance(value, dict) or type(value.get("id")) is not int or value["id"] <= 0 or
                type(value.get("publicationId")) is not int or value["publicationId"] != publication_id or
                (expected is not None and value["id"] != expected)):
            raise OJSError("mismatched_contributor_response", status_code=200, reconciliation_required=True)
        return receipt.model_copy(update={"contributor_id": value["id"]})

    def create_contributor(self, submission_id: int, publication_id: int, payload: OJSContributor) -> OJSReceipt:
        submission_id, publication_id = _positive(submission_id), _positive(publication_id)
        if not isinstance(payload, OJSContributor):
            raise OJSError("contributor_requires_typed_reviewed_payload")
        data = payload.model_dump(exclude_none=True)
        data["orcid"] = None  # Never claim an unverified ORCID or send verification email.
        receipt = self._request("POST", f"/submissions/{submission_id}/publications/{publication_id}/contributors",
                                mutation=True, uncertain_rejection=True, payload=data,
                                submission_id=submission_id, publication_id=publication_id)
        return self._contributor(receipt, publication_id)

    def update_contributor(self, submission_id: int, publication_id: int, contributor_id: int, payload: OJSContributor) -> OJSReceipt:
        submission_id, publication_id, contributor_id = _positive(submission_id), _positive(publication_id), _positive(contributor_id)
        if not isinstance(payload, OJSContributor):
            raise OJSError("contributor_requires_typed_reviewed_payload")
        receipt = self._request("PUT", f"/submissions/{submission_id}/publications/{publication_id}/contributors/{contributor_id}",
                                mutation=True, payload=payload.model_dump(exclude_none=True),
                                submission_id=submission_id, publication_id=publication_id)
        return self._contributor(receipt, publication_id, contributor_id)

    def validate_submission(self, submission_id: int) -> OJSReceipt:
        submission_id = _positive(submission_id)
        # The documented 3.5 implementation is read-only with this flag, but an
        # unrecognized installation may ignore it. Ambiguous outcomes therefore
        # need the same conservative reconciliation treatment as final Submit.
        receipt = self._request("PUT", f"/submissions/{submission_id}/submit", mutation=True,
                                payload={"_validateOnly": True}, submission_id=submission_id)
        if receipt.data != []:
            # A mismatched installation may have ignored the validation flag.
            raise OJSError("unsupported_validation_response", status_code=200, reconciliation_required=True)
        return receipt

    def final_submit(self, submission_id: int, *, approved: bool, confirm_copyright: bool = False) -> OJSReceipt:
        submission_id = _positive(submission_id)
        if approved is not True or type(confirm_copyright) is not bool:
            raise OJSError("explicit_final_submission_approval_required")
        # Always ask the provider to validate the current stored draft first.
        self.validate_submission(submission_id)
        payload = {"confirmCopyright": True} if confirm_copyright else {}
        receipt = self._request("PUT", f"/submissions/{submission_id}/submit", mutation=True,
                                payload=payload, submission_id=submission_id)
        return self._submission(receipt, submission_id, submitted=True)

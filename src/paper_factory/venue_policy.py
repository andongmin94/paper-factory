"""Review publisher policy against freshly retrieved, immutable source evidence.

Retrieval never interprets journal rules. A researcher supplies typed facts and
reviewed exact excerpts; missing facts, stale captures, and changed quotations
block readiness. Network access is bounded and pinned to public resolved IPs.
"""

from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
import re
import socket
from typing import Literal
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import httpx
from pydantic import ConfigDict, Field, field_validator, model_validator

from .models import Record, now, uid
from .venues import Venue, validate_venue
from .workspace import Workspace, digest_file, write_json

MAX_SOURCE_BYTES = 4 * 1024 * 1024
INDEXING_ORIGIN = "https://mjl.clarivate.com"


def normalize_text(text: str) -> str:
    """Match visible text while disregarding HTML's incidental whitespace."""
    return " ".join(text.split())


def _origin(url: str, *, allow_http: bool = False) -> str:
    if not isinstance(url, str) or any(ord(c) < 32 or c in "\\" for c in url):
        raise ValueError("Policy URL is malformed")
    parsed = urlsplit(url)
    schemes = {"https", "http"} if allow_http else {"https"}
    if parsed.scheme not in schemes or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError("Policy sources require HTTPS URLs without credentials")
    try:
        if parsed.port not in {None, 443} and not (allow_http and parsed.scheme == "http" and parsed.port == 80):
            raise ValueError("Policy URL must use the standard HTTPS port")
    except ValueError as error:
        raise ValueError("Policy URL has an invalid port") from error
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Policy URL must address a public host")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Policy URL must address a public host")
    # Directory homepages often contain an old HTTP URL. HTTPS on the same
    # explicitly named host is the only implicit upgrade we permit.
    return f"https://{host}"


class APC(Record):
    status: Literal["charged", "none", "waived"]
    amount: float | None = Field(default=None, ge=0, allow_inf_nan=False, strict=True)
    currency: str | None = None

    @model_validator(mode="after")
    def valid_price(self):
        if self.status == "charged" and (self.amount is None or self.amount <= 0 or self.currency is None or not re.fullmatch("[A-Z]{3}", self.currency)):
            raise ValueError("Charged APC needs a positive amount and ISO currency")
        if self.status in {"none", "waived"} and self.amount not in {None, 0}:
            raise ValueError("A none/waived APC cannot carry a positive charge")
        if self.currency is not None and not re.fullmatch("[A-Z]{3}", self.currency):
            raise ValueError("APC currency must be a three-letter uppercase ISO code")
        return self


class PolicyValues(Record):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, strict=True)
    scope: str | None = None
    article_types: list[str] | None = None
    indexing: Literal["SCIE", "ESCI", "unknown"] = "unknown"
    publisher: str | None = None
    oa_model: Literal["open", "hybrid", "subscription"] | None = None
    apc: APC | None = None
    preprint_policy: str | None = None
    ai_policy: str | None = None
    ai_use_allowed: bool | None = None
    ai_disclosure_required: bool | None = None
    data_code_policy: str | None = None
    manuscript_word_limit: int | None = Field(default=None, ge=1, strict=True)
    abstract_word_limit: int | None = Field(default=None, ge=1, strict=True)
    abstract_character_limit: int | None = Field(default=None, ge=1, strict=True)
    title_character_limit: int | None = Field(default=None, ge=1, strict=True)
    keyword_limit: int | None = Field(default=None, ge=0, strict=True)
    review_model: str | None = None
    anonymization_required: bool | None = None
    required_declarations: list[str] | None = None
    submission_url: str | None = None
    submission_system: str | None = None
    free_initial_submission: bool | None = None
    template_requirements: list[str] | None = None
    accepted_formats: list[Literal["pdf", "docx", "tex", "rtf"]] | None = None
    citation_style: str | None = None
    figure_formats: list[str] | None = None
    line_numbers_required: bool | None = None
    page_numbers_required: bool | None = None
    required_sections: list[str] | None = None
    required_supplements: list[str] | None = None

    @field_validator("scope", "publisher", "preprint_policy", "ai_policy", "data_code_policy", "review_model", "submission_system", "citation_style")
    @classmethod
    def nonempty(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Known policy text cannot be empty")
        return value

    @field_validator("article_types", "required_declarations", "template_requirements", "figure_formats", "required_sections", "required_supplements")
    @classmethod
    def nonempty_items(cls, value):
        if value is not None and any(not x.strip() for x in value):
            raise ValueError("Policy list items cannot be empty")
        return value

    @field_validator("submission_url")
    @classmethod
    def safe_submission_url(cls, value):
        if value is not None:
            _origin(value)
        return value


class PolicyEvidence(Record):
    source_url: str
    excerpt: str = Field(min_length=10, max_length=12000)
    interpretation: str = Field(min_length=1, max_length=4000)

    @field_validator("excerpt", "interpretation")
    @classmethod
    def readable_nonempty(cls, value):
        if not normalize_text(value):
            raise ValueError("Reviewed evidence cannot be whitespace")
        return value


class OfficialOrigin(Record):
    origin: str
    rationale: str = Field(min_length=1)
    evidence_url: str
    evidence_excerpt: str = Field(min_length=10)

    @field_validator("rationale", "evidence_excerpt")
    @classmethod
    def readable_nonempty(cls, value):
        if not normalize_text(value):
            raise ValueError("Official-origin evidence cannot be whitespace")
        return value


class PolicySpec(Record):
    venue_id: str
    sources: list[str] = Field(default_factory=list, max_length=20)
    official_origins: list[OfficialOrigin] = Field(default_factory=list, max_length=10)
    values: PolicyValues = Field(default_factory=PolicyValues)
    evidence: dict[str, PolicyEvidence] = Field(default_factory=dict)
    reviewed_by: str | None = None
    ttl_days: int = Field(default=7, ge=1, le=30, strict=True)

    @model_validator(mode="after")
    def known_fields(self):
        if set(self.evidence) - set(PolicyValues.model_fields):
            raise ValueError("Policy evidence contains an unknown field")
        if len(set(self.sources)) != len(self.sources):
            raise ValueError("Policy sources must not contain duplicate URLs")
        if self.reviewed_by is not None and not self.reviewed_by.strip():
            raise ValueError("Policy reviewer cannot be empty")
        return self


class PolicySource(Record):
    url: str
    final_url: str | None = None
    status: Literal["fetched", "failed"]
    fetched_at: str
    raw_path: str | None = None
    raw_sha256: str | None = None
    text_path: str | None = None
    text_sha256: str | None = None
    content_type: str | None = None
    error: str | None = None


class VenuePolicy(Record):
    id: str = Field(default_factory=lambda: uid("policy"))
    venue_id: str
    status: Literal["review_needed", "verified"]
    verified_at: str
    ttl_days: int
    values: PolicyValues
    evidence: dict[str, PolicyEvidence]
    reviewed_by: str | None
    official_origins: list[OfficialOrigin]
    sources: list[PolicySource]
    spec_path: str
    spec_sha256: str
    receipt_path: str
    receipt_sha256: str = ""
    issues: list[str]


def _public_ip(url: str) -> str:
    host = urlsplit(url).hostname
    try:
        resolved = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as error:
        raise ValueError("Policy host could not be resolved") from error
    addresses = sorted({item[4][0] for item in resolved})
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("Policy host resolves to a non-public address")
    return addresses[0]


def _fetch(client: httpx.Client, url: str, origins: set[str]) -> tuple[bytes, str, str]:
    """Resolve each redirect ourselves and pin the connection, retaining TLS SNI."""
    current = url
    for _ in range(6):
        if _origin(current) not in origins:
            raise ValueError("Policy request or redirect escaped the verified official origins")
        address = _public_ip(current)
        canonical = httpx.URL(current)
        connection = canonical.copy_with(host=address)
        # Connecting to the checked IP prevents DNS rebinding between validation
        # and connection. HTTPcore uses this extension for hostname TLS checking.
        with client.stream("GET", connection, headers={"Host": canonical.host, "Accept": "text/html,text/plain", "User-Agent": "PaperFactory/0.2"}, extensions={"sni_hostname": canonical.host}, follow_redirects=False, timeout=20) as response:
            if response.url != connection:
                raise ValueError("Policy response did not match the pinned request")
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("Policy redirect lacks a destination")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
                raise ValueError("Policy evidence must be readable HTML or plain text")
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > MAX_SOURCE_BYTES:
                    raise ValueError("Policy source exceeds the size limit")
            return bytes(raw), current, content_type
    raise ValueError("Policy source exceeded the redirect limit")


def _readable(raw: bytes, content_type: str) -> tuple[str, set[str]]:
    if content_type == "text/plain":
        return normalize_text(raw.decode("utf-8", errors="replace")), set()
    soup = BeautifulSoup(raw, "html.parser")
    for element in soup(["script", "style", "template", "noscript"]):
        element.decompose()
    links = {element.get("href") for element in soup.find_all("a", href=True)}
    return normalize_text(soup.get_text(" ")), links


def _source_capture(ws: Workspace, policy_id: str, index: int, url: str, active: httpx.Client, origins: set[str]) -> tuple[PolicySource, str, set[str]]:
    try:
        raw, final_url, content_type = _fetch(active, url, origins)
        text, links = _readable(raw, content_type)
        if not text:
            raise ValueError("Policy source contains no readable text")
        prefix = f"policies/{policy_id}/source-{index}"
        raw_path = prefix + ".html" if content_type != "text/plain" else prefix + ".txt"
        text_path = prefix + ".readable.txt"
        ws.path(raw_path).write_bytes(raw)
        ws.path(text_path).write_text(text, encoding="utf-8")
        return PolicySource(url=url, final_url=final_url, status="fetched", fetched_at=now(), raw_path=raw_path,
                            raw_sha256=hashlib.sha256(raw).hexdigest(), text_path=text_path,
                            text_sha256=digest_file(ws.path(text_path)), content_type=content_type), text, links
    except (ValueError, httpx.HTTPError) as error:
        # Preserve the attempt but never label a blocked/error response verified.
        return PolicySource(url=url, status="failed", fetched_at=now(), error=f"{type(error).__name__}: {error}"), "", set()


def _policy_issues(spec: PolicySpec, venue: Venue, sources: list[PolicySource], texts: dict[str, str]) -> list[str]:
    issues = [f"Source retrieval failed: {source.url}" for source in sources if source.status != "fetched"]
    if not spec.reviewed_by:
        issues.append("Policy interpretation requires a named researcher review")
    nullable = {"manuscript_word_limit", "abstract_word_limit", "abstract_character_limit", "title_character_limit", "keyword_limit", "citation_style"}
    for field in PolicyValues.model_fields:
        value = getattr(spec.values, field)
        if field not in spec.values.model_fields_set or (value is None and field not in nullable):
            issues.append(f"Unknown policy field: {field}")
        evidence = spec.evidence.get(field)
        if evidence is None:
            issues.append(f"Missing official evidence: {field}")
            continue
        if normalize_text(evidence.excerpt) not in texts.get(evidence.source_url, ""):
            issues.append(f"Official source does not contain the reviewed excerpt: {field}")
        if field == "indexing" and value != "unknown":
            if _origin(evidence.source_url) != INDEXING_ORIGIN:
                issues.append("SCIE/ESCI requires current Clarivate Master Journal List evidence")
            excerpt = normalize_text(evidence.excerpt).casefold()
            label = {"SCIE": "science citation index expanded", "ESCI": "emerging sources citation index"}[value]
            collection_present = bool(re.search(r"\b" + re.escape(value.casefold()) + r"\b", excerpt)) or label in excerpt
            journal_present = any(re.search(r"(?<![0-9])" + re.escape(issn.casefold()) + r"(?![0-9x])", excerpt) for issn in venue.issns)
            if not collection_present or not journal_present:
                issues.append("Indexing excerpt must identify this journal's ISSN and exact SCIE/ESCI collection")
    if spec.values.indexing == "unknown":
        issues.append("Current SCIE/ESCI indexing is unknown")
    if spec.values.article_types == []:
        issues.append("At least one supported article type is required")
    if spec.values.accepted_formats == []:
        issues.append("At least one accepted manuscript format is required")
    if spec.values.free_initial_submission is False and not spec.values.template_requirements:
        issues.append("A prescribed submission format requires explicit template requirements")
    return issues


def verify_policy(ws: Workspace, venue: Venue, policy_spec_path, *, client: httpx.Client | None = None) -> VenuePolicy:
    """Fetch every specified source anew, validate reviewed evidence, save a snapshot."""
    from pathlib import Path
    spec_bytes = Path(policy_spec_path).read_bytes()
    spec = PolicySpec.model_validate_json(spec_bytes)
    stored_venue = ws.get("venue", venue.id, Venue)
    if stored_venue != venue or spec.venue_id != venue.id:
        raise ValueError("Policy must target the stored discovered venue")
    if not venue.official_url:
        raise ValueError("A venue without an official homepage cannot verify policy")
    venue_errors = validate_venue(ws, venue)
    if venue_errors:
        raise ValueError("; ".join(venue_errors))
    primary = _origin(venue.official_url, allow_http=True)
    origins = {primary, INDEXING_ORIGIN}
    for url in spec.sources:
        _origin(url)
    for authority in spec.official_origins:
        if _origin(authority.origin) != authority.origin or urlsplit(authority.origin).path:
            raise ValueError("Additional official origin must be an exact HTTPS origin")
        if _origin(authority.evidence_url) != primary:
            raise ValueError("Additional official origins require evidence on the discovered journal's official host")
        if authority.evidence_url not in spec.sources:
            raise ValueError("Additional origin authority page must be a fetched policy source")
    nominated = origins | {authority.origin for authority in spec.official_origins}
    if any(_origin(url) not in nominated for url in spec.sources):
        raise ValueError("Policy source is outside the discovered or explicitly nominated official origins")
    for field, evidence in spec.evidence.items():
        if evidence.source_url not in spec.sources:
            raise ValueError(f"Policy evidence source was not requested: {field}")
        if _origin(evidence.source_url) == INDEXING_ORIGIN and field != "indexing":
            raise ValueError("Clarivate is an authority for indexing, not publisher policy")
    policy_id = uid("policy")
    destination = ws.path(f"policies/{policy_id}")
    destination.mkdir(parents=True)
    sources, texts, links = [], {}, {}
    authority_issues = []
    manager = nullcontext(client) if client is not None else httpx.Client(trust_env=False, timeout=20, follow_redirects=False)
    with manager as active:
        # Fetch journal-origin pages first, then prove each extra host by a real
        # link plus the reviewed authority excerpt on a journal-origin page.
        base_urls = [url for url in spec.sources if _origin(url) in origins]
        # Old directory homepages may redirect to a publisher's current host.
        # Permit only explicitly nominated hosts while following that original
        # homepage; no policy page on an extra host is fetched before proving it.
        redirect_origins = nominated
        for url in base_urls:
            allowed = redirect_origins if _origin(url) == primary else origins
            capture, text, source_links = _source_capture(ws, policy_id, len(sources), url, active, allowed)
            sources.append(capture)
            texts[url], links[url] = text, source_links
        for authority in spec.official_origins:
            candidates = links.get(authority.evidence_url, set())
            origin_capture = next(source for source in sources if source.url == authority.evidence_url)
            resolved_url = origin_capture.final_url or authority.evidence_url
            linked = any(_safe_link_origin(urljoin(resolved_url, href)) == authority.origin for href in candidates)
            linked = linked or (origin_capture.status == "fetched" and _origin(resolved_url) == authority.origin)
            if normalize_text(authority.evidence_excerpt) not in texts.get(authority.evidence_url, "") or not linked:
                authority_issues.append(f"Additional publisher origin lacks a verified journal-origin link and excerpt: {authority.origin}")
            else:
                origins.add(authority.origin)
        for url in spec.sources:
            if url in base_urls:
                continue
            if _origin(url) not in origins:
                sources.append(PolicySource(url=url, status="failed", fetched_at=now(), error="Official origin proof failed; request was not sent"))
                texts[url], links[url] = "", set()
                continue
            capture, text, source_links = _source_capture(ws, policy_id, len(sources), url, active, origins)
            sources.append(capture)
            texts[url], links[url] = text, source_links
    issues = authority_issues + _policy_issues(spec, venue, sources, texts)
    spec_path = f"policies/{policy_id}/spec.json"
    ws.path(spec_path).write_bytes(spec_bytes)
    policy = VenuePolicy(id=policy_id, venue_id=venue.id, status="review_needed" if issues else "verified", verified_at=now(),
                         ttl_days=spec.ttl_days, values=spec.values, evidence=spec.evidence, reviewed_by=spec.reviewed_by,
                         official_origins=spec.official_origins, sources=sources, spec_path=spec_path,
                         spec_sha256=hashlib.sha256(spec_bytes).hexdigest(), receipt_path=f"policies/{policy_id}/receipt.json", issues=issues)
    write_json(ws.path(policy.receipt_path), policy.model_dump(mode="json", exclude={"receipt_sha256"}))
    policy.receipt_sha256 = digest_file(ws.path(policy.receipt_path))
    ws.save("policy", policy)
    return policy


def _safe_link_origin(url: str) -> str | None:
    try:
        return _origin(url)
    except ValueError:
        return None


def validate_policy(ws: Workspace, policy: VenuePolicy, *, fresh: bool = True, check_compliance: bool = True) -> list[str]:
    """Check artifacts, plus readiness when requested; make no network requests.

    An intact incomplete snapshot is useful for a blocked draft package.
    ``check_compliance=False`` retains all evidence/receipt corruption checks
    without treating missing policy review as damaged artifacts.
    """
    errors = []
    try:
        receipt = ws.path(policy.receipt_path)
        if digest_file(receipt) != policy.receipt_sha256 or json.loads(receipt.read_text(encoding="utf-8")) != policy.model_dump(mode="json", exclude={"receipt_sha256"}):
            return ["Policy receipt changed or does not match the stored record"]
        spec_path = ws.path(policy.spec_path)
        if digest_file(spec_path) != policy.spec_sha256:
            return ["Policy specification changed"]
        spec = PolicySpec.model_validate_json(spec_path.read_bytes())
        venue = ws.get("venue", policy.venue_id, Venue)
        errors.extend(validate_venue(ws, venue))
        texts = {}
        for source in policy.sources:
            if source.status != "fetched":
                continue
            if not source.raw_path or not source.text_path or digest_file(ws.path(source.raw_path)) != source.raw_sha256 or digest_file(ws.path(source.text_path)) != source.text_sha256:
                errors.append(f"Policy source evidence changed: {source.url}")
                continue
            raw_text, _ = _readable(ws.path(source.raw_path).read_bytes(), source.content_type)
            stored_text = ws.path(source.text_path).read_text(encoding="utf-8")
            if raw_text != stored_text:
                errors.append(f"Readable policy text does not match raw evidence: {source.url}")
            texts[source.url] = stored_text
            if fresh and check_compliance:
                fetched = datetime.fromisoformat(source.fetched_at)
                if fetched.tzinfo is None or fetched > datetime.now(timezone.utc) + timedelta(minutes=1) or datetime.now(timezone.utc) - fetched > timedelta(days=policy.ttl_days):
                    errors.append(f"Policy source is stale or has an invalid retrieval date: {source.url}")
        if check_compliance:
            errors.extend(_policy_issues(spec, venue, policy.sources, texts))
            if policy.status != "verified":
                errors.append("Policy requires researcher review before submission readiness")
        return list(dict.fromkeys(errors))
    except (OSError, ValueError, TypeError) as error:
        return [f"Policy artifact validation failed: {error}"]


def refresh_policy(ws: Workspace, policy: VenuePolicy, *, client: httpx.Client | None = None) -> VenuePolicy:
    """Always re-fetch for a new compilation/package; retain the prior snapshot."""
    path = ws.path(policy.spec_path)
    if not path.is_file() or digest_file(path) != policy.spec_sha256:
        raise ValueError("Cannot refresh a changed or missing policy specification")
    return verify_policy(ws, ws.get("venue", policy.venue_id, Venue), path, client=client)

"""Dynamic journal discovery through OpenAlex's maintained CC0 directory.

Directory metadata is a candidate lead, never verified publisher policy or WoS
coverage. Only the explicitly supplied search string leaves the workspace.
"""

from contextlib import nullcontext
import hashlib
import json
import math
import re
from urllib.parse import urlsplit

import httpx
from pydantic import Field

from .models import Record, now, uid
from .workspace import Workspace, digest_file, write_json

API_URL = "https://api.openalex.org/sources"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class Venue(Record):
    id: str = Field(default_factory=lambda: uid("venue"))
    openalex_id: str
    name: str
    issns: list[str]
    publisher: str | None = None
    official_url: str | None = None
    query: str
    rank: int = Field(ge=1)
    relevance_score: float | None = None
    relevance_explanation: str
    indexing: str = "unknown"
    directory_url: str
    raw_path: str
    raw_sha256: str
    retrieved_at: str = Field(default_factory=now)


def _homepage(value: object) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("OpenAlex homepage URL is malformed")
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("OpenAlex homepage must be an HTTP(S) URL without credentials")
    try:
        if parsed.port not in {None, 80, 443}:
            raise ValueError("OpenAlex homepage has an unsupported port")
    except ValueError as error:
        raise ValueError("OpenAlex homepage has an unsupported port") from error
    return value


def _candidate(raw: object, *, query: str, rank: int, audit: dict) -> Venue:
    if not isinstance(raw, dict) or raw.get("type") != "journal":
        raise ValueError("OpenAlex returned a non-journal or malformed source")
    identity = raw.get("id")
    name = raw.get("display_name")
    issns = raw.get("issn")
    publisher = raw.get("host_organization_name")
    if not isinstance(identity, str) or not re.fullmatch(r"https://openalex\.org/S[0-9]+", identity):
        raise ValueError("OpenAlex source identity is malformed")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("OpenAlex source has no journal name")
    if issns is None:
        issns = []
    if not isinstance(issns, list) or any(not isinstance(x, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{3}[0-9X]", x) for x in issns):
        raise ValueError("OpenAlex ISSNs are malformed")
    if publisher is not None and (not isinstance(publisher, str) or not publisher.strip()):
        raise ValueError("OpenAlex publisher name is malformed")
    score = raw.get("relevance_score")
    if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or score < 0):
        raise ValueError("OpenAlex relevance score is malformed")
    return Venue(
        openalex_id=identity, name=name.strip(), issns=issns,
        publisher=publisher, official_url=_homepage(raw.get("homepage_url")),
        query=query, rank=rank, relevance_score=score,
        relevance_explanation="OpenAlex source-name/alternate-title search order; journal filter. This is directory text relevance, not an assessment of manuscript fit, quality, acceptance probability, or current indexing.",
        **audit,
    )


def discover(ws: Workspace, query: str, limit: int = 5, *, client: httpx.Client | None = None) -> list[Venue]:
    """Retrieve bounded journal candidates; no manuscript or automatic paid key."""
    query = query.strip()
    if not query or len(query) > 500:
        raise ValueError("Venue query must contain 1 to 500 characters")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("Venue limit must be between 1 and 50")
    manager = nullcontext(client) if client is not None else httpx.Client(
        timeout=20, follow_redirects=False, trust_env=False,
        headers={"User-Agent": "PaperFactory/0.2 (local research CLI)"},
    )
    try:
        with manager as active:
            with active.stream("GET", API_URL, params={"search": query, "filter": "type:journal", "per_page": limit}, follow_redirects=False) as response:
                response.raise_for_status()
                if response.url.scheme != "https" or response.url.host != "api.openalex.org" or response.url.port not in {None, 443} or response.url.path != "/sources":
                    raise ValueError("OpenAlex response escaped its official API endpoint")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise ValueError("OpenAlex response exceeds the size limit")
                directory_url = str(response.url)
    except httpx.HTTPError as error:
        raise ValueError(f"OpenAlex request failed: {type(error).__name__}") from error
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("OpenAlex response is not valid JSON") from error
    if not isinstance(data, dict) or not isinstance(data.get("results"), list) or len(data["results"]) > limit:
        raise ValueError("OpenAlex results are malformed or exceed the requested limit")
    search_id = uid("venue-search")
    raw_path = f"venues/{search_id}/response.json"
    audit = dict(directory_url=directory_url, raw_path=raw_path,
                 raw_sha256=hashlib.sha256(raw).hexdigest(), retrieved_at=now())
    # Validate the whole response before saving any candidate records.
    venues = [_candidate(item, query=query, rank=rank, audit=audit) for rank, item in enumerate(data["results"], 1)]
    if len({v.openalex_id for v in venues}) != len(venues):
        raise ValueError("OpenAlex returned duplicate source identities")
    destination = ws.path(raw_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    write_json(destination.with_name("search.json"), {"query": query, "limit": limit, "provider": "OpenAlex", **audit, "venue_ids": [v.id for v in venues]})
    for venue in venues:
        ws.save("venue", venue)
    return venues


def validate_venue(ws: Workspace, venue: Venue) -> list[str]:
    """Ensure editable records still describe their captured provider response."""
    try:
        raw = ws.path(venue.raw_path)
        if digest_file(raw) != venue.raw_sha256:
            return ["Venue directory evidence changed"]
        data = json.loads(raw.read_bytes())
        source = data["results"][venue.rank - 1]
        expected = _candidate(source, query=venue.query, rank=venue.rank, audit={
            "directory_url": venue.directory_url, "raw_path": venue.raw_path,
            "raw_sha256": venue.raw_sha256, "retrieved_at": venue.retrieved_at,
        })
        fields = ("openalex_id", "name", "issns", "publisher", "official_url", "relevance_score", "relevance_explanation", "indexing")
        if any(getattr(venue, field) != getattr(expected, field) for field in fields):
            return ["Venue record does not match its captured directory metadata"]
        audit = json.loads(raw.with_name("search.json").read_text(encoding="utf-8"))
        if audit["query"] != venue.query or audit["directory_url"] != venue.directory_url or audit["retrieved_at"] != venue.retrieved_at or venue.id not in audit["venue_ids"]:
            return ["Venue record does not match its directory search receipt"]
        return []
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        return [f"Venue directory validation failed: {error}"]

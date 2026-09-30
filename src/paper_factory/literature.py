"""Crossref discovery and independently auditable bibliographic verification.

Only an explicit search query or DOI leaves the local workspace. Metadata
verification does not verify a paper's scientific results or establish novelty.
"""

import hashlib
import json
import re
import unicodedata
from contextlib import nullcontext
from datetime import datetime, timedelta
from urllib.parse import quote

import httpx

from .models import Citation, Provenance, Record, Study, now, uid
from .workspace import Workspace, digest_file, write_json

API_ORIGIN = "https://api.crossref.org"


class _SearchRecord(Record):
    id: str
    audit: dict[str, object]
    audit_sha256: str


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _doi(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"10\.\d{4,9}/[^\s\x00-\x1f\x7f]+", value):
        raise ValueError("Expected a DOI identifier such as 10.1234/example, not a URL")
    if any(part in {".", ".."} for part in value.split("/")):
        raise ValueError("DOI cannot contain dot path segments")
    return value


def _source_url(doi: str) -> str:
    return f"{API_ORIGIN}/works/{quote(_doi(doi), safe='')}"


def _metadata(data: object) -> tuple[str, str, list[str], int | None]:
    if not isinstance(data, dict) or data.get("status") != "ok":
        raise ValueError("Crossref did not return a successful metadata record")
    message = data.get("message")
    if not isinstance(message, dict):
        raise ValueError("Crossref metadata is missing its work record")
    returned_doi = message.get("DOI")
    if not isinstance(returned_doi, str):
        raise ValueError("Crossref work record has no DOI")
    doi = _doi(returned_doi)
    titles = message.get("title")
    if not isinstance(titles, list) or not titles or not isinstance(titles[0], str) or not titles[0].strip():
        raise ValueError("Crossref work record has no title")
    title = titles[0].strip()
    author_records = message.get("author")
    if not isinstance(author_records, list) or not author_records:
        raise ValueError("Crossref work record has no authors")
    authors = []
    for author in author_records:
        if not isinstance(author, dict):
            raise ValueError("Crossref author record is malformed")
        names = [author.get("given", ""), author.get("family", "")]
        if any(not isinstance(name, str) for name in names):
            raise ValueError("Crossref author names are malformed")
        name = " ".join(part.strip() for part in names if part.strip())
        if not name and isinstance(author.get("name"), str):
            name = author["name"].strip()
        if not name:
            raise ValueError("Crossref author record has no name")
        authors.append(name)
    year = None
    for field in ("published-print", "published-online", "published", "issued"):
        publication = message.get(field)
        if not isinstance(publication, dict):
            continue
        parts = publication.get("date-parts")
        if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
            candidate = parts[0][0]
            if isinstance(candidate, int) and not isinstance(candidate, bool) and 1 <= candidate <= 9999:
                year = candidate
                break
    return doi, title, authors, year


def _request(client: httpx.Client, url: str, params: dict | None = None) -> httpx.Response:
    try:
        response = client.get(url, params=params, follow_redirects=False)
        response.raise_for_status()
        # Injected clients must obey the same provider boundary as default clients.
        if response.url.scheme != "https" or response.url.host != "api.crossref.org":
            raise ValueError("Crossref response escaped the official API origin")
        return response
    except httpx.HTTPError as error:
        raise ValueError(f"Crossref request failed: {type(error).__name__}") from error


def _json(response: httpx.Response) -> object:
    try:
        return response.json()
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("Crossref response is not valid JSON") from error


def _client(client: httpx.Client | None):
    return nullcontext(client) if client is not None else httpx.Client(
        timeout=20.0,
        follow_redirects=False,
        headers={"User-Agent": "PaperFactory/0.1 (local research CLI)"},
    )


def _import(ws: Workspace, doi: str, client: httpx.Client) -> Citation:
    doi = _doi(doi)
    source_url = _source_url(doi)
    response = _request(client, source_url)
    resolved_doi, title, authors, year = _metadata(_json(response))
    if resolved_doi != doi:
        raise ValueError("Crossref returned metadata for a different DOI")
    metadata_sha256 = hashlib.sha256(response.content).hexdigest()
    # Re-fetching changed metadata creates a new record rather than mutating
    # bibliography evidence already referenced by a manuscript.
    identity = hashlib.sha256(f"{doi}\0{metadata_sha256}".encode()).hexdigest()[:20]
    citation = Citation(
        id=f"citation-{identity}",
        doi=doi,
        title=title,
        authors=authors,
        year=year,
        source_url=source_url,
        verified_at=now(),
        metadata_sha256=metadata_sha256,
    )
    ws.path(f"literature/{citation.id}.json").write_bytes(response.content)
    ws.save("citation", citation)
    ws.save("provenance", Provenance(
        role="citation metadata verification",
        tool="Crossref REST API",
        inputs=[doi, source_url],
        outputs=[citation.id, f"literature/{citation.id}.json"],
    ))
    return citation


def import_doi(ws: Workspace, doi: str, *, client: httpx.Client | None = None) -> Citation:
    """Resolve an explicitly requested DOI against Crossref, without guessing."""
    _doi(doi)  # Validate before opening a network client.
    with _client(client) as active_client:
        return _import(ws, doi, active_client)


def search(
    ws: Workspace,
    query: str,
    study: Study,
    limit: int = 5,
    *,
    client: httpx.Client | None = None,
) -> list[Citation]:
    """Search metadata and resolve every candidate DOI before citing it."""
    query = query.strip()
    if not query or len(query) > 1000:
        raise ValueError("Literature query must contain 1 to 1000 characters")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("Literature search limit must be between 1 and 50")
    search_id = uid("search")
    audit = {
        "id": search_id,
        "study_id": study.id,
        "query": query,
        "limit": limit,
        "provider": "Crossref",
        "fetched_at": now(),
        "source_url": f"{API_ORIGIN}/works",
        "candidate_dois": [],
        "resolved_ids": [],
        "candidates": [],
        "status": "FAILED",
        "verification_scope": "metadata_only",
        "novelty_proven": False,
    }
    citations = []
    audit_path = ws.path(f"literature/{search_id}.json")
    with _client(client) as active_client:
        try:
            response = _request(active_client, f"{API_ORIGIN}/works", {
                "query.bibliographic": query, "rows": limit,
            })
            audit["source_url"] = str(response.url)
            raw_path = ws.path(f"literature/{search_id}-response.json")
            raw_path.write_bytes(response.content)
            audit["response_sha256"] = digest_file(raw_path)
            data = _json(response)
            message = data.get("message") if isinstance(data, dict) and data.get("status") == "ok" else None
            items = message.get("items") if isinstance(message, dict) else None
            if not isinstance(items, list):
                raise ValueError("Crossref search response contains no result list")
            seen_dois = set()
            for item in items[:limit]:
                candidate_doi = item.get("DOI") if isinstance(item, dict) else None
                candidate = {"doi": candidate_doi, "citation_id": None, "error": None}
                audit["candidates"].append(candidate)
                if not isinstance(candidate_doi, str):
                    candidate["error"] = "Search candidate has no DOI"
                    continue
                audit["candidate_dois"].append(candidate_doi)
                try:
                    normalized_doi = _doi(candidate_doi)
                    if normalized_doi in seen_dois:
                        candidate["error"] = "Duplicate DOI in search results"
                        continue
                    seen_dois.add(normalized_doi)
                    citation = _import(ws, normalized_doi, active_client)
                    candidate["citation_id"] = citation.id
                    citations.append(citation)
                    audit["resolved_ids"].append(citation.id)
                except ValueError as error:
                    candidate["error"] = str(error)
            audit["status"] = "SUCCEEDED"
        except ValueError as error:
            audit["error"] = str(error)
            raise
        finally:
            write_json(audit_path, audit)
            ws.save("search", _SearchRecord(id=search_id, audit=audit, audit_sha256=digest_file(audit_path)))
            ws.save("provenance", Provenance(
                role="literature discovery",
                tool="Crossref REST API",
                inputs=[query, str(audit["source_url"])],
                outputs=[f"literature/{search_id}.json"],
            ))
    study.literature_search_ids.append(search_id)
    study.citation_ids = list(dict.fromkeys(study.citation_ids + [citation.id for citation in citations]))
    study.novelty_status = "searched"
    ws.save("study", study)
    return citations


def verify_citation(ws: Workspace, citation: Citation) -> list[str]:
    """Validate local evidence independently; never re-query or trust a flag."""
    errors = []
    if not citation.verified:
        errors.append("Citation is not verified")
    try:
        if ws.get("citation", citation.id, Citation) != citation:
            errors.append("Citation differs from its persisted verified record")
        expected_url = _source_url(citation.doi)
        if citation.source_url != expected_url:
            errors.append("Citation source URL is not its official DOI metadata endpoint")
        path = ws.path(f"literature/{citation.id}.json")
        if not path.is_file():
            errors.append("Citation has no raw metadata record")
            return errors
        if digest_file(path) != citation.metadata_sha256:
            errors.append("Citation raw metadata SHA256 does not match")
        doi, title, authors, year = _metadata(json.loads(path.read_bytes()))
        if doi != _doi(citation.doi):
            errors.append("Citation DOI does not match verified metadata")
        if _normalized(title) != _normalized(citation.title):
            errors.append("Citation title does not match verified metadata")
        if [_normalized(author) for author in authors] != [_normalized(author) for author in citation.authors]:
            errors.append("Citation authors do not match verified metadata")
        if year != citation.year:
            errors.append("Citation year does not match verified metadata")
    except (ValueError, OSError, UnicodeDecodeError) as error:
        errors.append(f"Citation metadata is invalid: {error}")
    return errors


def verify_search(ws: Workspace, search_id: str, study_id: str) -> list[str]:
    """Revalidate a persisted successful query, including its raw response."""
    errors = []
    try:
        record = ws.get("search", search_id, _SearchRecord)
        path = ws.path(f"literature/{search_id}.json")
        if not path.is_file():
            return ["Literature search has no audit file"]
        audit = json.loads(path.read_bytes())
        if digest_file(path) != record.audit_sha256 or audit != record.audit:
            errors.append("Literature search audit differs from its persisted record")
        if not isinstance(audit, dict):
            return [*errors, "Literature search audit is malformed"]
        if audit.get("id") != search_id or audit.get("study_id") != study_id:
            errors.append("Literature search identity does not match study")
        if audit.get("status") != "SUCCEEDED":
            errors.append("Literature search did not succeed")
        if audit.get("provider") != "Crossref" or audit.get("verification_scope") != "metadata_only" or audit.get("novelty_proven") is not False:
            errors.append("Literature search provider or verification scope is invalid")
        query, limit = audit.get("query"), audit.get("limit")
        if not isinstance(query, str) or not query.strip() or query.strip() != query or len(query) > 1000:
            errors.append("Literature search query is invalid")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            errors.append("Literature search limit is invalid")
        expected_url = httpx.URL(f"{API_ORIGIN}/works", params={"query.bibliographic": query, "rows": limit})
        if not isinstance(audit.get("source_url"), str) or httpx.URL(audit["source_url"]) != expected_url:
            errors.append("Literature search URL does not match its official query endpoint")
        fetched_at = audit.get("fetched_at")
        timestamp = datetime.fromisoformat(fetched_at) if isinstance(fetched_at, str) else None
        if timestamp is None or timestamp.utcoffset() != timedelta(0):
            errors.append("Literature search timestamp must be UTC")
        raw_path = ws.path(f"literature/{search_id}-response.json")
        if not raw_path.is_file():
            return [*errors, "Literature search has no raw API response"]
        if digest_file(raw_path) != audit.get("response_sha256"):
            errors.append("Literature search response SHA256 does not match")
        data = json.loads(raw_path.read_bytes())
        message = data.get("message") if isinstance(data, dict) and data.get("status") == "ok" else None
        items = message.get("items") if isinstance(message, dict) else None
        if not isinstance(items, list) or not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            return [*errors, "Literature search raw results are malformed"]
        selected = items[:limit]
        expected_dois = [item["DOI"] for item in selected if isinstance(item, dict) and isinstance(item.get("DOI"), str)]
        if audit.get("candidate_dois") != expected_dois:
            errors.append("Literature search candidate DOIs differ from its raw results")
        candidates = audit.get("candidates")
        if not isinstance(candidates, list) or len(candidates) != len(selected):
            return [*errors, "Literature search resolution audit is malformed"]
        resolved_ids = []
        study = ws.get("study", study_id, Study)
        if search_id not in study.literature_search_ids:
            errors.append("Literature search is not linked to its study")
        for candidate, hit in zip(candidates, selected, strict=True):
            if not isinstance(candidate, dict) or candidate.get("doi") != (hit.get("DOI") if isinstance(hit, dict) else None):
                errors.append("Literature search candidate record differs from its raw result")
                continue
            citation_id = candidate.get("citation_id")
            if citation_id is None:
                if not isinstance(candidate.get("error"), str) or not candidate["error"]:
                    errors.append("Unresolved literature candidate has no failure reason")
                continue
            if not isinstance(citation_id, str) or candidate.get("error") is not None:
                errors.append("Literature search resolved candidate is malformed")
                continue
            resolved_ids.append(citation_id)
            citation = ws.get("citation", citation_id, Citation)
            if not isinstance(candidate.get("doi"), str) or citation.doi != _doi(candidate["doi"]):
                errors.append("Literature search resolved citation differs from candidate DOI")
            if citation_id not in study.citation_ids:
                errors.append("Literature search citation is not linked to its study")
            errors.extend(verify_citation(ws, citation))
        if audit.get("resolved_ids") != resolved_ids or len(resolved_ids) != len(set(resolved_ids)):
            errors.append("Literature search resolved IDs differ from verified candidates")
    except (ValueError, OSError, TypeError, KeyError, httpx.InvalidURL) as error:
        errors.append(f"Literature search evidence is invalid: {error}")
    return sorted(set(errors))

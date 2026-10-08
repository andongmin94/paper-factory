"""Bounded literature retrieval with an explicit distinction between metadata and reading.

Only Crossref records, Crossref-provided abstracts, identity-bound arXiv metadata,
and allowlisted public PDFs are fetched. Bibliographic candidates resolve by DOI;
explicit arXiv identifiers resolve to a fixed preprint version before reading.
The collector does not infer a finding from a title or identifier.
"""

from __future__ import annotations

import hashlib
import io
import ipaddress
import json
import os
import re
import signal
import socket
import subprocess
import sys
import sysconfig
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable, TypedDict
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import getproxies_environment, proxy_bypass_environment
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup

from ..literature import _doi, _metadata
from ..workspace import ensure_unlinked, is_link
from .windows_runtime import WindowsJob

CROSSREF = "https://api.crossref.org"
ARXIV = "https://export.arxiv.org/api/query"
# Fixed provider boundaries prevent a metadata link from requesting local services.
PDF_HOSTS = frozenset({"arxiv.org", "export.arxiv.org", "joss.theoj.org"})
AUTHOR_PDF_HOST = "www.cs.cmu.edu"
AUTHOR_PUBLICATIONS = "https://www.cs.cmu.edu/~bam/resume.html"
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGES = 40
MAX_TEXT_CHARS = 200_000
MAX_EXCERPTS = 12
MAX_EXCERPT_CHARS = 1_500
ARXIV_ID = r"(?:\d{2}(?:0[1-9]|1[0-2])\.\d{4,5}|[a-z-]+/\d{2}(?:0[1-9]|1[0-2])\d{3})(?:v[1-9]\d*)?"
ATOM = "{http://www.w3.org/2005/Atom}"


class _Cancelled(Exception):
    pass


class _DeadlineExceeded(Exception):
    pass


class _RateLimited(Exception):
    pass


class _CollectionBudget:
    def __init__(self):
        self.deadline = time.monotonic() + 90
        self.next_request = 0.0
        self.next_arxiv_request = 0.0
        self.retries = 0
        self.requests = 0

    def wait(self, seconds: float, cancel: Callable[[], bool] | None) -> None:
        end = time.monotonic() + seconds
        while True:
            _check_cancel(cancel)
            current = time.monotonic()
            if current >= self.deadline:
                raise _DeadlineExceeded
            if current >= end:
                return
            time.sleep(min(0.05, end - current, self.deadline - current))

    def request_timeout(self, *, pdf: bool, arxiv: bool = False, cancel: Callable[[], bool] | None) -> httpx.Timeout:
        next_request = self.next_arxiv_request if arxiv else self.next_request
        self.wait(0 if pdf else max(0, next_request - time.monotonic()), cancel)
        if arxiv:
            self.next_arxiv_request = time.monotonic() + 3
        elif not pdf:
            self.next_request = time.monotonic() + 0.5
        remaining = self.deadline - time.monotonic()
        return httpx.Timeout(min(15, remaining), connect=min(5, remaining))

    def rate_delay(self, value: str | None) -> float:
        delay = 2.0
        if value is not None:
            try:
                if value.isdecimal():
                    delay = float(value)
                else:
                    date = parsedate_to_datetime(value)
                    if date.tzinfo is not None:
                        delay = max(0, date.timestamp() - time.time())
            except (ValueError, TypeError, OverflowError):
                pass
        if delay > 10 or delay >= self.deadline - time.monotonic():
            raise _RateLimited
        return delay


def _check_cancel(cancel: Callable[[], bool] | None) -> None:
    if cancel is not None and cancel():
        raise _Cancelled


def _author_pdf_url(url: str) -> str:
    """Pure validation for the audited institution's public author-paper directory."""
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 32 or ord(c) == 127 for c in url):
        raise ValueError("Invalid author PDF URL")
    parts = urlsplit(url)
    try:
        port = parts.port
    except ValueError as error:
        raise ValueError("Invalid author PDF URL port") from error
    if (parts.scheme != "https" or parts.hostname != AUTHOR_PDF_HOST or parts.username is not None
            or parts.password is not None or port not in (None, 443) or parts.query or parts.fragment
            or not re.fullmatch(r"/~(?:NatProg|natprog)/papers/[A-Za-z0-9][A-Za-z0-9_.-]{0,179}\.pdf", parts.path)):
        raise ValueError("Author PDF URL is outside the audited public-paper boundary")
    return "https://" + AUTHOR_PDF_HOST + parts.path


def author_pdf_redirect(url: str, location: str) -> str:
    """Keep an audited server's literal path; never make a plain HTTP request."""
    url = _author_pdf_url(url)
    if not isinstance(location, str) or not location or len(location) > 2048 or any(ord(c) < 32 or ord(c) == 127 for c in location):
        raise ValueError("Invalid author PDF redirect Location")
    following = urljoin(url, location)
    parts = urlsplit(following)
    if parts.scheme == "http":
        # Only the fixed author host/directory may upgrade its server Location.
        # The HTTPS validator below still checks auth, port, path and parameters.
        following = "https:" + following[len("http:"):]
    return _author_pdf_url(following)


def _checked_url(url: str, *, pdf: bool = False, author_pdf: bool = False, author_listing: bool = False) -> str:
    """Reject untrusted authorities before DNS or HTTP and private DNS answers."""
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 32 for c in url):
        raise ValueError("Invalid literature URL")
    parts = urlsplit(url)
    if author_listing and (pdf or author_pdf or url != AUTHOR_PUBLICATIONS):
        raise ValueError("Only the fixed official author publication list is allowed")
    if author_pdf:
        if not pdf:
            raise ValueError("Author-paper requests must be bounded PDF requests")
        url = _author_pdf_url(url)
        parts = urlsplit(url)
    hosts = frozenset({AUTHOR_PDF_HOST}) if author_pdf or author_listing else PDF_HOSTS if pdf else frozenset({"api.crossref.org", "export.arxiv.org"})
    try:
        port = parts.port
    except ValueError as error:
        raise ValueError("Invalid literature URL port") from error
    if (
        parts.scheme != "https" or parts.hostname not in hosts or parts.username is not None
        or parts.password is not None or port not in (None, 443) or parts.fragment
    ):
        raise ValueError("Literature URL is outside the allowed provider boundary")
    if parts.query and pdf:
        raise ValueError("Open-access PDF URLs cannot contain credentials or query parameters")
    if author_pdf or author_listing:
        pass  # The fixed author directory/listing boundary was checked above.
    elif pdf:
        if parts.hostname in {"arxiv.org", "export.arxiv.org"}:
            if not re.fullmatch(r"/pdf/(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?(?:\.pdf)?", parts.path):
                raise ValueError("Only an arXiv paper PDF endpoint is allowed")
        elif not re.fullmatch(r"/papers/(?:10\.21105/joss\.\d{5}|[a-f0-9]{40})\.pdf", parts.path):
            raise ValueError("Only a JOSS paper PDF endpoint is allowed")
    elif parts.hostname == "export.arxiv.org":
        if parts.path != "/api/query":
            raise ValueError("Only the arXiv discovery endpoint is allowed")
    elif parts.path != "/works" and not parts.path.startswith("/works/10."):
        raise ValueError("Only Crossref work endpoints are allowed")
    try:
        addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
    except OSError as error:
        # Managed cloud egress may delegate DNS to its configured HTTPS proxy.
        # This exception applies only to the fixed provider allowlist above,
        # never to arbitrary publisher hosts, addresses, or redirects.
        proxies = getproxies_environment()
        if not (author_pdf or author_listing) and proxies.get("https") and not proxy_bypass_environment(parts.hostname, proxies):
            return url
        raise ValueError("Literature provider DNS lookup failed") from error
    if not addresses or any(not ipaddress.ip_address(record[4][0]).is_global for record in addresses):
        raise ValueError("Literature provider resolved to a non-public address")
    return url


def _fetch(
    client: httpx.Client, url: str, *, budget: _CollectionBudget, pdf: bool = False,
    params: dict[str, object] | None = None, cancel: Callable[[], bool] | None = None,
    author_pdf: bool = False, author_listing: bool = False,
    retain_response: Callable[[bytes, str, str, int], None] | None = None,
    redirects: list[dict] | None = None,
) -> tuple[bytes, str, str]:
    """Stream into a hard bound; validate every redirect before requesting it."""
    maximum = MAX_PDF_BYTES if pdf else MAX_JSON_BYTES
    redirect, retried = 0, False
    while True:
        _check_cancel(cancel)
        url = _checked_url(url, pdf=pdf, author_pdf=author_pdf, author_listing=author_listing)
        timeout = budget.request_timeout(pdf=pdf, arxiv=not pdf and urlsplit(url).hostname == "export.arxiv.org", cancel=cancel)
        budget.requests += 1
        with client.stream("GET", url, params=params, follow_redirects=False, timeout=timeout) as response:
            budget.wait(0, cancel)
            hosts = {AUTHOR_PDF_HOST} if author_pdf or author_listing else PDF_HOSTS if pdf else {"api.crossref.org", "export.arxiv.org"}
            if response.url.scheme != "https" or response.url.host not in hosts:
                raise ValueError("Literature response escaped its allowed provider boundary")
            if author_pdf:
                _author_pdf_url(str(response.url))
            if author_listing and str(response.url) != AUTHOR_PUBLICATIONS:
                raise ValueError("Author publication-list response escaped its fixed endpoint")

            def content() -> bytes:
                length = response.headers.get("content-length")
                if length and (not length.isdecimal() or int(length) > maximum):
                    raise ValueError("Literature response exceeds its size limit")
                body = bytearray()
                for chunk in response.iter_bytes():
                    budget.wait(0, cancel)
                    body.extend(chunk)
                    if len(body) > maximum:
                        raise ValueError("Literature response exceeds its size limit")
                return bytes(body)

            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                trace = None
                if author_pdf and redirects is not None:
                    trace = {"url": str(response.url), "status": response.status_code,
                             "location": location, "next_url": None}
                    redirects.append(trace)
                try:
                    if author_pdf or author_listing:
                        raw = content()
                        if retain_response is not None:
                            retain_response(raw, str(response.url), response.headers.get("content-type", "").lower(), response.status_code)
                    if not pdf or not location or redirect == 3:
                        raise ValueError("Literature provider redirect was refused")
                    url = author_pdf_redirect(str(response.url), location) if author_pdf else urljoin(str(response.url), location)
                    if trace is not None:
                        trace["next_url"] = url
                except ValueError:
                    if trace is not None:
                        trace["error"] = "ValueError"
                    raise
                params = None
                redirect, retried = redirect + 1, False
                continue
            if response.status_code == 429 and not pdf and not author_listing:
                delay = budget.rate_delay(response.headers.get("retry-after"))
                response.close()
                budget.wait(delay, cancel)
                if not retried and budget.retries < 3:
                    budget.retries += 1
                    retried = True
                    continue
            if retain_response is None:
                response.raise_for_status()
            raw, retrieved_url, content_type = content(), str(response.url), response.headers.get("content-type", "").lower()
            if retain_response is not None:
                retain_response(raw, retrieved_url, content_type, response.status_code)
                response.raise_for_status()
            return raw, retrieved_url, content_type


def _prepare_root(root: Path) -> Path:
    root = Path(os.path.abspath(root))
    for part in (root, *root.parents):
        if is_link(part):
            raise ValueError("Literature output path cannot contain symbolic links")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not root.is_dir():
        raise ValueError("Literature output root is not a directory")
    destination = root / "literature"
    if is_link(destination):
        raise ValueError("Literature output directory cannot be a symbolic link")
    destination.mkdir(exist_ok=True, mode=0o700)
    return root


def _save(root: Path, prefix: str, suffix: str, content: bytes) -> tuple[str, str]:
    digest = hashlib.sha256(content).hexdigest()
    relative = f"literature/{prefix}-{digest[:16]}.{suffix}"
    path = root / relative
    # Check the final component too: Windows os.open has no O_NOFOLLOW.
    ensure_unlinked(path)
    # POSIX NOFOLLOW additionally guards the final component during creation.
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        if is_link(path) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Existing literature artifact does not match the fetched evidence") from None
    else:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
    return relative, digest


def _abstract(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT_CHARS:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())


def _excerpts(text: str) -> list[str]:
    """Preserve bounded literal passages, never a model-generated summary."""
    text = text[:MAX_TEXT_CHARS]
    paragraphs = [" ".join(p.split()) for p in text.split("\n\n") if p.strip()]
    output: list[str] = []
    for paragraph in paragraphs:
        for start in range(0, len(paragraph), MAX_EXCERPT_CHARS):
            output.append(paragraph[start:start + MAX_EXCERPT_CHARS])
            if len(output) == MAX_EXCERPTS:
                return output
    return output


def _full_text_excerpts(text: str, queries: list[str]) -> tuple[list[str], list[dict[str, int]]]:
    """Sample literal body passages across repeated methods/results sections."""
    body = full_text_body_range(text)
    lower, upper = (body["start"], body["end"]) if body else (0, len(text))
    last = max(lower, upper - MAX_EXCERPT_CHARS)
    starts = [lower] if last == lower else [lower, last]

    def add(start: int) -> None:
        start = min(max(start, lower), last)
        if len(starts) < MAX_EXCERPTS and all(abs(start - previous) >= MAX_EXCERPT_CHARS for previous in starts):
            starts.append(start)

    def outer_first(positions: list[int]) -> list[int]:
        # First, last, second, penultimate: late sections cannot be crowded out
        # by a long run of earlier sections or equally scored query windows.
        return [positions[index // 2 if index % 2 == 0 else -1 - index // 2] for index in range(len(positions))]

    headings = ("related work|background", "method(?:s|ology)?|analysis design", "results?|evaluation",
                "discussions?|implications?", "threats? to validity|limitations?", "conclusions?")
    groups = []
    for heading in headings:
        # Unnumbered headings must occupy their entire line. Numbered headings
        # may have a title suffix, but prose such as "results of ..." is not a heading.
        pattern = (r"(?mi)^[ \t]*(?:(?:\d+(?:\.\d+)*|[IVX]+)\.?[ \t]+(?:" + heading +
                   r")\b[^\n]{0,100}|(?:" + heading + r")[ \t]*)$")
        groups.append(outer_first([match.start() for match in re.finditer(pattern, text)
                                   if lower <= match.start() < upper]))
    for rank in range(max(map(len, groups), default=0)):
        for positions in groups:
            if rank < len(positions):
                add(positions[rank])

    stop_words = {"https", "http", "with", "from", "that", "this", "different", "which", "using", "study", "arxiv", "doi"}
    semantic_queries = [query for query in queries if not _is_arxiv_query(query) and _query_doi(query) is None]
    terms = {term.casefold() for query in semantic_queries for term in re.findall(r"[^\W\d_]{4,}", query)
             if term.casefold() not in stop_words}
    scores = [(sum(term in text[start:min(start + MAX_EXCERPT_CHARS, upper)].casefold() for term in terms), start)
              for start in range(lower, upper, MAX_EXCERPT_CHARS)]
    for score in sorted({score for score, _ in scores if score > 0}, reverse=True):
        for start in outer_first([start for value, start in scores if value == score]):
            if len(starts) >= MAX_EXCERPTS - 3:
                break
            add(start)
    remaining = MAX_EXCERPTS - len(starts)
    for index in range(1, remaining + 1):
        add(lower + index * (upper - lower) // (remaining + 1))
    excerpts, ranges = [], []
    pages = [(match.start(), int(match.group(1))) for match in re.finditer(r"\[Page (\d+)\]\n", text)]
    for start in sorted(starts):
        end = min(start + MAX_EXCERPT_CHARS, upper)
        location = {"start": start, "end": end}
        for key, offset in (("page_start", start), ("page_end", end - 1)):
            page = next((page for position, page in reversed(pages) if position <= offset), None)
            if page is not None:
                location[key] = page
        excerpts.append(text[start:end])
        ranges.append(location)
    return excerpts, ranges


def full_text_body_range(text: str) -> dict[str, int] | None:
    """Locate a recognizable paper body; an unknown layout certifies nothing.

    A PDF can contain both an abstract and a bibliography. Merely retrieving
    its full text does not make either a methods/results passage. Offsets are
    derived from the retained literal text and can be recomputed at review.
    """
    numbering = r"(?:(?:\d+(?:\.\d+)*|[IVX]+)\.?[ \t]+|(?:\d+|[IVX]+)\.?[ \t]*\n[ \t]*)?"
    introduction = re.search(r"(?mi)^[ \t]*" + numbering + r"(?:introduction|서론)[ \t]*$", text)
    first_section = r"(?:(?:1|I)\.?[ \t]+|(?:1|I)\.?[ \t]*\n[ \t]*)"
    background = re.search(r"(?mi)^[ \t]*" + first_section + r"background(?: and terminologies)?[ \t]*$", text)
    openings = [match for match in (introduction, background) if match is not None]
    if not openings:
        return None
    opening = min(openings, key=lambda match: match.start())
    references = re.search(r"(?mi)^[ \t]*" + numbering + r"(?:references(?: and notes)?|bibliography|literature cited|참고문헌)[ \t]*$",
                           text[opening.end():])
    if references is None:
        return None
    end = opening.end() + references.start()
    return {"start": opening.end(), "end": end}


def _title_key(title: str) -> str:
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", title).casefold()))


def _arxiv_entries(content: bytes) -> list[ET.Element]:
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("arXiv discovery XML must use UTF-8") from error
    if len(content) > MAX_JSON_BYTES or re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", decoded, re.I):
        raise ValueError("arXiv discovery XML contains a refused declaration or exceeds its limit")
    try:
        feed = ET.fromstring(decoded)
    except ET.ParseError as error:
        raise ValueError("arXiv discovery returned invalid XML") from error
    if feed.tag != ATOM + "feed":
        raise ValueError("arXiv discovery did not return an Atom feed")
    entries = feed.findall(ATOM + "entry")
    if len(entries) > 3:
        raise ValueError("arXiv discovery exceeds its candidate limit")
    return entries


def _arxiv_match(content: bytes, doi: str, title: str) -> tuple[str, str] | None:
    """A similar title is discovery, never identity: require the exact journal DOI."""
    atom, arxiv = ATOM, "{http://arxiv.org/schemas/atom}"
    matches = []
    for entry in _arxiv_entries(content):
        if any(len(entry.findall(field)) != 1 for field in (arxiv + "doi", atom + "title", atom + "id")):
            continue
        returned_doi, returned_title = entry.findtext(arxiv + "doi"), entry.findtext(atom + "title")
        if not returned_doi or not returned_title:
            continue
        try:
            if _doi(returned_doi) != doi or _title_key(returned_title) != _title_key(title):
                continue
        except ValueError:
            continue
        identifier = entry.findtext(atom + "id", "")
        # Atom IDs historically use HTTP; they are parsed as identifiers, never
        # requested. Construct only the fixed HTTPS PDF endpoint ourselves.
        match = re.fullmatch(r"https?://arxiv\.org/abs/((?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})v\d+)", identifier)
        if match:
            matches.append(("https://arxiv.org/pdf/" + match.group(1), match.group(1)))
    if len(set(matches)) != 1:
        return None
    return matches[0]


def _arxiv_record(entry: ET.Element) -> dict:
    """Validate one canonical preprint entry without a journal publication claim."""
    values = {}
    for field in ("id", "title", "published", "updated"):
        elements = entry.findall(ATOM + field)
        if len(elements) != 1 or len(elements[0]) or not elements[0].text or not elements[0].text.strip():
            raise ValueError("arXiv entry has missing or duplicate identity metadata")
        values[field] = elements[0].text.strip()
    match = re.fullmatch(r"https?://arxiv\.org/abs/(" + ARXIV_ID + r")", values["id"])
    if match is None or not re.search(r"v[1-9]\d*$", match.group(1)):
        raise ValueError("arXiv entry has no canonical versioned identifier")
    identifier = match.group(1)
    title = " ".join(values["title"].split())
    if len(title) > 4000:
        raise ValueError("arXiv title exceeds its metadata limit")
    dates = {}
    for field in ("published", "updated"):
        value = values[field]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})", value):
            raise ValueError("arXiv entry has an invalid publication date")
        dates[field] = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dates["updated"] < dates["published"]:
        raise ValueError("arXiv version predates its first publication")
    author_records = entry.findall(ATOM + "author")
    if not 1 <= len(author_records) <= 100:
        raise ValueError("arXiv entry requires bounded author metadata")
    authors = []
    for author in author_records:
        names = author.findall(ATOM + "name")
        if len(names) != 1 or len(names[0]) or not names[0].text or not names[0].text.strip() or len(names[0].text) > 1000:
            raise ValueError("arXiv author metadata is missing or ambiguous")
        authors.append(" ".join(names[0].text.split()))
    summaries = entry.findall(ATOM + "summary")
    if len(summaries) > 1:
        raise ValueError("arXiv entry has duplicate abstracts")
    summary = (summaries[0].text or "") if summaries else ""
    # Optional journal DOI and journal_ref remain in the original XML. They do
    # not turn this inspected preprint into a verified journal publication.
    return {"arxiv_id": identifier, "title": title, "authors": authors,
            "year": dates["published"].year, "published": values["published"], "updated": values["updated"],
            "provider": "arXiv", "publication_type": "preprint", "abstract": _abstract(summary)}


def _arxiv_metadata(content: bytes, requested: str) -> dict:
    """Bind one explicit lookup to its actual version, without a publication claim."""
    entries = _arxiv_entries(content)
    if len(entries) != 1:
        raise ValueError("An explicit arXiv lookup requires one unambiguous entry")
    record = _arxiv_record(entries[0])
    identifier = record["arxiv_id"]
    if (identifier if re.search(r"v[1-9]\d*$", requested) else re.sub(r"v[1-9]\d*$", "", identifier)) != requested:
        raise ValueError("arXiv resolved a different identifier or version")
    return record


def _arxiv_title_metadata(content: bytes, title: str) -> dict | None:
    """A complete small feed must have exactly one normalized full-title match."""
    entries = _arxiv_entries(content)
    feed = ET.fromstring(content.decode("utf-8-sig"))
    totals = feed.findall("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
    if (len(totals) != 1 or not totals[0].text or not totals[0].text.isdecimal() or
            int(totals[0].text) != len(entries) or int(totals[0].text) > 3):
        raise ValueError("arXiv exact-title lookup requires a complete bounded result set")
    titles = [entry.findall(ATOM + "title") for entry in entries]
    if any(len(fields) != 1 or len(fields[0]) or not fields[0].text or not fields[0].text.strip() for fields in titles):
        raise ValueError("arXiv exact-title candidates require single nonempty plain-text titles")
    matches = [entry for entry in entries if _title_key(entry.findtext(ATOM + "title", "")) == _title_key(title)]
    if len(matches) > 1:
        raise ValueError("arXiv exact title is ambiguous; provide an explicit identifier")
    return _arxiv_record(matches[0]) if matches else None


def _arxiv_title_lookup(client: httpx.Client, query: str, root: Path, search: dict, *, budget: _CollectionBudget,
                        cancel: Callable[[], bool] | None, warnings: list[str]) -> tuple[bytes, str, dict] | None:
    """Preserve each exact-title attempt, including failed or empty discovery."""
    search.update(provider="arXiv", lookup="exact_title")
    initial_requests = budget.requests
    try:
        title_query = " ".join(re.findall(r"\w+", query))
        if not title_query:
            raise ValueError("arXiv exact-title query has no searchable title")
        content, url, content_type = _fetch(client, ARXIV, budget=budget, cancel=cancel,
            params={"search_query": 'ti:"' + title_query + '"', "max_results": 3})
        if content_type.split(";", 1)[0].strip() not in {"application/atom+xml", "application/xml", "text/xml"}:
            raise ValueError("arXiv lookup did not return XML content")
        path, digest = _save(root, "search-" + hashlib.sha256(query.encode()).hexdigest()[:16], "xml", content)
        search.update(url=url, raw_path=path, sha256=digest)
        details = _arxiv_title_metadata(content, query)
        search["status"] = "succeeded"
        if details is None:
            search["note"] = "No unique exact-title preprint was resolved; this is not evidence that relevant work is absent"
        return (content, url, details) if details is not None else None
    except (_Cancelled, _DeadlineExceeded, _RateLimited) as error:
        if budget.requests == initial_requests:
            search.update(status="not_attempted", attempted=False)
        elif isinstance(error, _RateLimited):
            search.update(error="HTTPStatusError", http_status=429)
        raise
    except (ValueError, OSError, httpx.HTTPError) as error:
        search["error"] = type(error).__name__
        search["note"] = "Exact-title identity could not be established; provide an explicit arXiv identifier if known"
        if isinstance(error, httpx.HTTPStatusError):
            search["http_status"] = error.response.status_code
        warnings.append(f"arXiv exact-title discovery unavailable ({type(error).__name__}); no preprint identity was assumed")
        return None


def _arxiv_pdf(client: httpx.Client, source: dict, root: Path, *, budget: _CollectionBudget,
               cancel: Callable[[], bool] | None) -> str | None:
    title_query = " ".join(re.findall(r"\w+", source["title"]))
    if not title_query or len(title_query) > 500:
        return None
    content, url, content_type = _fetch(client, ARXIV, budget=budget, cancel=cancel,
                                      params={"search_query": 'ti:"' + title_query + '"', "max_results": 3})
    if content_type.split(";", 1)[0].strip() not in {"application/atom+xml", "application/xml", "text/xml"}:
        raise ValueError("arXiv discovery did not return XML content")
    path, digest = _save(root, source["id"] + "-discovery", "xml", content)
    source.update(discovery_path=path, discovery_sha256=digest, discovery_url=url)
    match = _arxiv_match(content, source["doi"], source["title"])
    if match is None:
        return None
    pdf_url, identifier = match
    source["arxiv_id"] = identifier
    return pdf_url


def _extract_pdf(content: bytes) -> str:
    if not content.startswith(b"%PDF-"):
        raise ValueError("Open-access response is not a PDF document")
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise ValueError("PDF reading requires the installed pdf extra") from error
    reader = PdfReader(io.BytesIO(content), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PDF_PAGES:
        raise ValueError("Open-access PDF is encrypted or exceeds the page limit")
    passages: list[str] = []
    total = 0
    for index, page in enumerate(reader.pages, 1):
        # Decompression has its own bound before invoking the text extractor.
        page_content = page.get_contents()
        if page_content is not None and len(page_content.get_data()) > 4 * 1024 * 1024:
            raise ValueError("Open-access PDF page exceeds the extraction limit")
        text = page.extract_text() or ""
        total += len(text)
        if total > MAX_TEXT_CHARS:
            raise ValueError("Open-access PDF text exceeds the extraction limit")
        passages.append(f"[Page {index}]\n{text}")
    combined = "\n\n".join(passages)
    if len(combined.strip()) < 200:
        raise ValueError("Open-access PDF has insufficient extractable text")
    return combined


def _stop_pdf_process(process: subprocess.Popen) -> bool:
    """Confirm termination of the PDF worker's owned job or process group."""
    try:
        if os.name == "nt":
            job = getattr(process, "_paper_factory_job", None)
            if job is None or not job.stop():
                return False
            process.wait(timeout=5)
            return True
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
        deadline = time.monotonic() + 1
        while True:
            if Path("/proc").is_dir():
                running = False
                for entry in Path("/proc").glob("[0-9]*/stat"):
                    try:
                        fields = entry.read_text().rsplit(")", 1)[1].split()
                        if int(fields[2]) == process.pid and fields[0] not in {"Z", "X"}:
                            running = True
                            break
                    except (OSError, ValueError, IndexError):
                        continue
            else:
                try:
                    os.killpg(process.pid, 0)
                    running = True
                except ProcessLookupError:
                    running = False
            if not running:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.02)
    except (OSError, subprocess.TimeoutExpired):
        return False


def _pdf_text(content: bytes) -> str:
    """Parse untrusted PDFs in a resource-limited child with no inherited secrets."""

    if not content.startswith(b"%PDF-"):
        raise ValueError("Open-access response is not a PDF document")
    if len(content) > MAX_PDF_BYTES:
        raise ValueError("Open-access PDF exceeds its size limit")
    source_directory = str(Path(__file__).resolve().parents[2])
    package_directory = sysconfig.get_path("purelib")
    worker = f"""
import json, sys
if sys.platform != "win32":
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
# Input is supplied only after the controller has assigned the Windows job.
content = sys.stdin.buffer.read({MAX_PDF_BYTES + 1})
sys.path.insert(0, {package_directory!r})
sys.path.insert(0, {source_directory!r})
from paper_factory.autonomous.literature import _extract_pdf
try:
    text = _extract_pdf(content)
    sys.stdout.write(json.dumps(text))
except Exception:
    sys.exit(2)
"""
    process = None
    job = None
    cleanup_confirmed = True
    try:
        if os.name == "nt":
            job = WindowsJob(name="Local\\paper-factory-research-" + uuid4().hex,
                             limits={"memory_bytes": 512 * 1024 * 1024, "pids": 1, "cpu_seconds": 8})
        options = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
                   if os.name == "nt" else {"start_new_session": True})
        # Windows venv redirectors spawn a second process before job assignment.
        # Start the native interpreter directly and add our installed packages above.
        interpreter = str(Path(sys.base_prefix) / "python.exe") if os.name == "nt" else sys.executable
        process = subprocess.Popen(
            [interpreter, "-I", "-B", "-c", worker], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={"PYTHONIOENCODING": "utf-8"}, **options,
        )
        if job is not None:
            job.assign(process._handle)
            process._paper_factory_job = job
        output, _ = process.communicate(content, timeout=12)
        returncode = process.returncode
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("Open-access PDF extraction failed or exceeded its resource limit") from error
    finally:
        try:
            if process is not None:
                # A completed leader can leave descendants behind. Reuse the
                # whole-tree cleanup, attaching a job only after assignment.
                if job is not None and getattr(process, "_paper_factory_job", None) is None:
                    # No PDF input was sent to this unassigned worker.
                    process.kill()
                    process.wait(timeout=5)
                    cleanup_confirmed = job.stop()
                else:
                    cleanup_confirmed = _stop_pdf_process(process)
                for stream in (process.stdin, process.stdout):
                    if stream is not None:
                        stream.close()
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError("Open-access PDF extraction cleanup could not be confirmed") from error
        finally:
            if job is not None:
                job.close()
    if not cleanup_confirmed:
        raise ValueError("Open-access PDF extraction cleanup could not be confirmed")
    if returncode != 0 or len(output) > MAX_TEXT_CHARS * 8:
        raise ValueError("Open-access PDF could not be safely extracted")
    try:
        text = json.loads(output)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("Open-access PDF extraction returned invalid text") from error
    if not isinstance(text, str) or len(text) > MAX_TEXT_CHARS + 1000:
        raise ValueError("Open-access PDF text exceeds the extraction limit")
    return text


def _pdf_links(message: dict) -> list[str]:
    links: list[str] = []
    for link in message.get("link", [])[:8] if isinstance(message.get("link"), list) else []:
        if isinstance(link, dict) and link.get("content-type") == "application/pdf" and isinstance(link.get("URL"), str):
            links.append(link["URL"])
    doi = message.get("DOI", "")
    if isinstance(doi, str) and re.fullmatch(r"10\.21105/joss\.\d{5}", doi.lower()):
        links.append(f"https://joss.theoj.org/papers/{doi.lower()}.pdf")
    return list(dict.fromkeys(links))[:2]


def _query_doi(query: str) -> str | None:
    """Recognize an explicitly requested DOI without guessing one from a title."""
    match = re.fullmatch(r"(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?(10\.\d{4,9}/\S+)", query, re.I)
    if match is None:
        match = re.search(r"(?:\bdoi:\s*|https?://(?:dx\.)?doi\.org/)(10\.\d{4,9}/\S+)", query, re.I)
    return _doi(match.group(1)) if match is not None else None


class PdfCandidate(TypedDict):
    doi: str
    title: str


def normalize_pdf_candidates(value: object, queries: list[str]) -> list[PdfCandidate]:
    """Validate untrusted model hints before reserving an intent or doing I/O."""
    if not isinstance(value, list) or len(value) > 2:
        raise ValueError("Provide at most two public PDF candidates")
    explicit_dois = {_query_doi(query.strip()) for query in queries if isinstance(query, str)}
    candidates: list[PdfCandidate] = []
    for item in value:
        if (not isinstance(item, dict) or set(item) != {"doi", "title"}
                or any(not isinstance(item[key], str) for key in ("doi", "title"))):
            raise ValueError("Public PDF candidates require only doi and title strings")
        if any(ord(c) < 32 or ord(c) == 127 for key in ("doi", "title") for c in item[key]):
            raise ValueError("Public PDF candidate fields cannot contain control characters")
        title = item["title"].strip()
        if not title or len(title) > 500 or not _title_key(title):
            raise ValueError("Public PDF candidate title must contain 1 to 500 printable characters")
        doi = _doi(item["doi"])
        if len(doi) > 500 or doi not in explicit_dois:
            raise ValueError("Public PDF candidate DOI must be explicitly requested in the literature queries")
        candidate: PdfCandidate = {"doi": doi, "title": title}
        if any(previous["doi"] == doi for previous in candidates):
            raise ValueError("Public PDF candidates cannot repeat a DOI")
        candidates.append(candidate)
    return candidates


def discover_author_pdf(content: bytes, candidate: PdfCandidate) -> dict:
    """Parse one exact quoted title and one literal PDF link from a leaf li.

    The official list discovers a URL; it never establishes inspected findings.
    Native verification reparses these same retained bytes, without HTML crawling.
    """
    if (not isinstance(candidate, dict) or normalize_pdf_candidates([candidate], [candidate.get("doi", "")]) != [candidate]
            or not isinstance(content, bytes) or len(content) > MAX_JSON_BYTES):
        raise ValueError("Author publication discovery requires bounded bytes and a canonical candidate")
    soup = BeautifulSoup(content, "html.parser")
    for element in soup(["script", "style", "template"]):
        element.decompose()
    matches = []
    # Index all li elements, then require a leaf: nested lists cannot mix papers.
    for index, leaf in enumerate(soup.find_all("li")):
        if leaf.find("li") is not None:
            continue
        titles = re.findall(r'"([^"\n]{1,500})"|“([^“”\n]{1,500})”', leaf.get_text(" ", strip=True))
        quoted = [left or right for left, right in titles]
        exact = [title for title in quoted if _title_key(title) == _title_key(candidate["title"])]
        if exact:
            matches.append((index, leaf, quoted, exact))
    if len(matches) != 1:
        raise ValueError("Official author list has no unique exact quoted whole title")
    index, leaf, quoted, exact = matches[0]
    if len(quoted) != 1 or len(exact) != 1:
        raise ValueError("Official publication leaf contains ambiguous quoted titles")
    hrefs = [link.get("href") for link in leaf.find_all("a") if isinstance(link.get("href"), str)
             and urlsplit(link["href"]).path.lower().endswith(".pdf")]
    if len(hrefs) != 1:
        raise ValueError("Official publication leaf has no unique PDF href")
    href = hrefs[0]
    # Only a literal root-relative audited path or a complete HTTPS URL.
    # urljoin would silently normalize control characters or dot segments.
    url = _author_pdf_url("https://" + AUTHOR_PDF_HOST + href if href.startswith("/") and not href.startswith("//") else href)
    return {"provider": "CMU publications", "listing_url": AUTHOR_PUBLICATIONS, "leaf_index": index,
            "quoted_title": exact[0], "literal_href": href, "url": url}


def _author_listing(client: httpx.Client, root: Path, cache: dict, *, budget: _CollectionBudget,
                    cancel: Callable[[], bool] | None) -> bytes:
    """At most one anonymous fixed-list request in this collection, even on failure."""
    record = cache["record"]
    if not record["attempted"]:
        record.update(attempted=True, status="rejected")

        def retain(raw: bytes, url: str, content_type: str, status: int) -> None:
            path, digest = _save(root, "author-publications", "html", raw)
            record.update(raw_path=path, sha256=digest, retrieved_url=url, content_type=content_type, http_status=status)

        try:
            raw, _, content_type = _fetch(client, AUTHOR_PUBLICATIONS, author_listing=True,
                                         retain_response=retain, budget=budget, cancel=cancel)
            if record["http_status"] != 200 or content_type.split(";", 1)[0].strip() != "text/html":
                raise ValueError("Official author publication list is not a complete HTML response")
            cache["content"] = raw
            record["status"] = "succeeded"
        except (_Cancelled, _DeadlineExceeded, _RateLimited) as error:
            record.update(status="interrupted", error=type(error).__name__)
            raise
        except (ValueError, OSError, httpx.HTTPError, httpx.InvalidURL) as error:
            record["error"] = type(error).__name__
            raise
    if "content" not in cache:
        raise ValueError("Official author publication list was unavailable in this collection")
    return cache["content"]


def author_pdf_identity(text: str, source: dict) -> dict:
    """Recomputable literal identity; neither a model flag nor substring matching."""
    if (not isinstance(source, dict) or not isinstance(source.get("doi"), str)
            or not isinstance(source.get("title"), str) or not 1 <= len(source["title"]) <= 500
            or not isinstance(source.get("authors"), list) or not 1 <= len(source["authors"]) <= 50
            or any(not isinstance(author, str) or not 1 <= len(author) <= 500 for author in source["authors"])):
        raise ValueError("Author PDF identity requires bounded exact bibliographic fields")
    if _doi(source["doi"]) != source["doi"]:
        raise ValueError("Author PDF identity requires a canonical DOI")
    author_keys = [_title_key(author) for author in source["authors"]]
    if not _title_key(source["title"]) or any(not key for key in author_keys) or len(set(author_keys)) != len(author_keys):
        raise ValueError("Author PDF identity requires distinct nonempty bibliographic names")
    if not isinstance(text, str) or len(text) > MAX_TEXT_CHARS + 1000 or not text.startswith("[Page 1]\n"):
        raise ValueError("Author PDF extraction has no first-page boundary")
    following = re.search(r"(?m)^\[Page 2\]\n", text)
    end = following.start() if following else len(text)
    first = text[:end]
    abstract = re.search(r"(?mi)^[ \t]*abstract(?:[ \t]*$|[ \t]*[—–:.-])", first)
    if abstract is None or abstract.start() > 8_000:
        raise ValueError("Author PDF has no bounded first-page front matter")
    lines = [(match.group(), match.start(), match.end()) for match in re.finditer(r"[^\r\n]+", first[:abstract.start()])
             if match.group().strip() and match.group().strip() != "[Page 1]"]
    author_ranges = []
    author_indices = []
    for author in source["authors"]:
        matches = [(index, line) for index, line in enumerate(lines) if _title_key(line[0]) == _title_key(author)]
        if len(matches) != 1:
            raise ValueError("Author PDF front-matter authors differ from Crossref")
        index, line = matches[0]
        author_indices.append(index)
        author_ranges.append({"author": author, "start": line[1], "end": line[2]})
    first_author = min(author_indices)
    # Consume the complete initial block up to the first exact author name:
    # accepting an expected-title prefix would hide a wrapped conflicting subtitle.
    if not 1 <= first_author <= 3 or _title_key(" ".join(line[0] for line in lines[:first_author])) != _title_key(source["title"]):
        raise ValueError("Author PDF initial whole title differs from Crossref")
    title_range = {"start": lines[0][1], "end": lines[first_author - 1][2]}
    doi_ranges = []
    for match in re.finditer(r"(?i)(?<![\w.])10\.\d{4,9}/[^\s<>\"()]+", first):
        literal = match.group().rstrip(",;.")
        if _doi(literal) != source["doi"]:
            raise ValueError("Author PDF first page prints a conflicting DOI")
        doi_ranges.append({"start": match.start(), "end": match.start() + len(literal)})
    if not doi_ranges:
        raise ValueError("Author PDF first page does not print the exact Crossref DOI")
    body = full_text_body_range(text)
    if body is None or len(text[body["start"]:body["end"]].strip()) < 200:
        raise ValueError("Author PDF has no bounded substantive body beyond its front matter")
    return {"first_page_range": {"start": 0, "end": end}, "front_matter_end": abstract.start(),
            "title_range": title_range, "author_ranges": author_ranges, "doi_ranges": doi_ranges}


def _retain_full_text(source: dict, root: Path, text: str, url: str, raw_path: str, raw_digest: str) -> None:
    text_path, text_digest = _save(root, source["id"] + "-text", "txt", text.encode())
    excerpts, ranges = _full_text_excerpts(text, source["queries"])
    source.update({"scope": "full_text", "url": url, "raw_path": raw_path,
                   "sha256": raw_digest, "excerpts": excerpts, "excerpt_ranges": ranges,
                   "body_range": full_text_body_range(text), "text_chars": len(text),
                   "reading_scope": "Only the located literal excerpts were inspected; the complete extracted text is retained separately",
                   "text_path": text_path, "text_sha256": text_digest})


def _promote_hinted_pdf(client: httpx.Client, source: dict, hints: list[PdfCandidate], root: Path, *, listing: dict,
                        budget: _CollectionBudget, cancel: Callable[[], bool] | None,
                        warnings: list[str], attempts: list[dict]) -> None:
    for hint in hints:
        attempt = {"source_id": source["id"], "candidate": hint, "status": "rejected", "redirects": [],
                   "metadata_path": source["metadata_path"], "metadata_sha256": source["metadata_sha256"]}
        attempts.append(attempt)

        def retain(raw: bytes, url: str, content_type: str, status: int) -> None:
            path, digest = _save(root, source["id"] + "-hint-response", "pdf" if raw.startswith(b"%PDF-") else "bin", raw)
            if status in (301, 302, 303, 307, 308):
                attempt["redirects"][-1].update(raw_path=path, sha256=digest, content_type=content_type)
            else:
                attempt.update(raw_path=path, sha256=digest, retrieved_url=url, content_type=content_type, http_status=status)

        try:
            budget.wait(0, cancel)
            if _title_key(hint["title"]) != _title_key(source["title"]) or hint["doi"] != source.get("doi"):
                raise ValueError("Public PDF hint identity differs from exact Crossref metadata")
            try:
                listing_bytes = _author_listing(client, root, listing, budget=budget, cancel=cancel)
            finally:
                attempt["discovery"] = {key: value for key, value in listing["record"].items()
                                        if key in {"raw_path", "sha256", "retrieved_url", "content_type", "http_status"}}
            discovered = discover_author_pdf(listing_bytes, hint)
            attempt["discovery"].update(discovered)
            if sum(previous.get("pdf_attempted") is True for previous in attempts) >= 2:
                raise ValueError("Public author PDF attempt budget was exhausted")
            # Reserve before DNS, cancellation checks or GET. A matched URL
            # consumes one attempt even when retrieval or identity fails.
            attempt["pdf_attempted"] = True
            raw, url, content_type = _fetch(client, discovered["url"], pdf=True, author_pdf=True,
                                           redirects=attempt["redirects"], retain_response=retain, cancel=cancel, budget=budget)
            if attempt["http_status"] != 200:
                raise ValueError("Author-paper provider did not return a complete HTTP 200 response")
            if content_type.split(";", 1)[0].strip() not in {"application/pdf", "application/octet-stream"}:
                raise ValueError("Author-paper provider did not return PDF content")
            if budget.deadline - time.monotonic() < 18:
                raise _DeadlineExceeded
            text = _pdf_text(raw)
            # Keep completed extraction even when identity or cancellation fails.
            text_path, text_digest = _save(root, source["id"] + "-text", "txt", text.encode())
            attempt.update(text_path=text_path, text_sha256=text_digest)
            budget.wait(0, cancel)
            attempt["identity"] = author_pdf_identity(text, source)
            _retain_full_text(source, root, text, url, attempt["raw_path"], attempt["sha256"])
            source.update(copy_type="author_copy", publication_version="unknown",
                          discovery_path=attempt["discovery"]["raw_path"], discovery_sha256=attempt["discovery"]["sha256"],
                          discovery_url=AUTHOR_PUBLICATIONS)
            # A failed arXiv PDF may have preceded this separate author copy.
            # Its discovery bytes remain retained, but do not describe this PDF.
            source.pop("arxiv_id", None)
            attempt["status"] = "verified"
        except (_Cancelled, _DeadlineExceeded, _RateLimited) as error:
            attempt.update(status="interrupted", error=type(error).__name__)
            raise
        except (ValueError, OSError, httpx.HTTPError, httpx.InvalidURL) as error:
            attempt["error"] = type(error).__name__
            attempt["note"] = str(error)[:300] if isinstance(error, ValueError) else "Public PDF retrieval or extraction failed"
            warnings.append(f"Public PDF hint unavailable for {source['id']} ({type(error).__name__}); reading scope was not upgraded")
        finally:
            path, digest = _save(root, source["id"] + "-hint-identity", "json", json.dumps(attempt, ensure_ascii=False, sort_keys=True).encode())
            attempt.update(identity_path=path, identity_sha256=digest)
            if attempt["status"] == "verified":
                source.update(identity_path=path, identity_sha256=digest)
        if attempt["status"] == "verified":
            break


def _is_arxiv_query(query: str) -> bool:
    return bool(re.match(r"arxiv\s*:", query, re.I) or re.search(r"10\.48550/arxiv\.", query, re.I))


def _query_arxiv(query: str) -> str:
    match = re.fullmatch(r"arxiv\s*:\s*(\S+)", query, re.I)
    doi = _query_doi(query) if match is None else None
    identifier = match.group(1).lower() if match else (doi.removeprefix("10.48550/arxiv.") if doi else "")
    if len(identifier) > 100 or not re.fullmatch(ARXIV_ID, identifier):
        raise ValueError("Expected an explicit arXiv identifier or arXiv DOI")
    return identifier


def _promote_full_text(client: httpx.Client, source: dict, pdf_urls: list[str], root: Path,
                       *, budget: _CollectionBudget, cancel: Callable[[], bool] | None, warnings: list[str]) -> None:
    """Use the same bounded PDF reading and evidence retention for every source."""
    for pdf_url in pdf_urls:
        budget.wait(0, cancel)
        try:
            raw_pdf, retrieved_url, content_type = _fetch(client, pdf_url, pdf=True, cancel=cancel, budget=budget)
            if "pdf" not in content_type and content_type != "application/octet-stream":
                raise ValueError("Open-access provider did not return a PDF content type")
            # Reserve bounded extraction and owned-child cleanup before dispatch.
            if budget.deadline - time.monotonic() < 18:
                raise _DeadlineExceeded
            full_text = _pdf_text(raw_pdf)
            budget.wait(0, cancel)
            raw_path, raw_digest = _save(root, source["id"] + "-fulltext", "pdf", raw_pdf)
            _retain_full_text(source, root, full_text, retrieved_url, raw_path, raw_digest)
            break
        except (ValueError, OSError, httpx.HTTPError) as error:
            warnings.append(f"Open-access text unavailable for {source['id']} ({type(error).__name__}); reading scope was not upgraded")


def collect(
    queries: list[str], root: Path, *, limit: int = 6,
    cancel: Callable[[], bool] | None = None,
    pdf_candidates: list[PdfCandidate] | None = None,
) -> dict:
    """Collect actual fetched evidence; no network failure becomes a fake source.

    ``raw_path`` is relative to ``root`` and points to the artifact supporting
    the declared reading scope. Metadata remains separately recorded when an
    allowed full text is fetched. All queries are attempted before candidates
    are resolved in round-robin order. Explicit and unique exact-title arXiv
    lookups bind the actual preprint version and precede bibliographic candidates.
    Other DOIs use an exact Crossref lookup;
    bibliographic searches do not exclude records without Crossref abstracts.
    Explicit DOI-bound author PDF hints precede generic candidates and use their
    strict identity route exclusively, retaining completed rejected responses.
    A fresh collection (``pdf_candidates=None``) can also discover exact Crossref
    records in the fixed official author list after generic full text fails.
    At most two matched author PDFs are attempted; unmatched titles consume no
    PDF attempt. Explicit empty or reserved candidate lists disable this route.
    Cancellation and the shared 90-second deadline preserve partial evidence,
    with distinct ``cancelled`` and ``timed_out`` flags. A provider cooldown
    beyond the remaining wait budget sets ``rate_limited``. Query provenance is not relevance.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 12:
        raise ValueError("Literature source limit must be between 0 and 12")
    if not isinstance(queries, list) or not 1 <= len(queries) <= 8:
        raise ValueError("Provide between 1 and 8 literature queries")
    if any(not isinstance(query, str) or not query.strip() or len(query) > 500 or any(ord(c) < 32 for c in query) for query in queries):
        raise ValueError("Literature queries must contain 1 to 500 printable characters")
    queries = list(dict.fromkeys(query.strip() for query in queries))
    hints = normalize_pdf_candidates([] if pdf_candidates is None else pdf_candidates, queries)
    root = _prepare_root(root)
    result: dict = {"sources": [], "searches": [
        {"query": query, "provider": "arXiv" if _is_arxiv_query(query) else "Crossref",
         "status": "not_attempted", "attempted": False, "resolved_ids": []}
        for query in sorted(queries, key=lambda query: not _is_arxiv_query(query))], "warnings": []}
    seen: set[str] = set()
    if hints or pdf_candidates is None:
        result["pdf_hint_attempts"] = []
    listing = {"record": {"provider": "CMU publications", "listing_url": AUTHOR_PUBLICATIONS,
                          "attempted": False, "status": "not_attempted"}}
    if hints or pdf_candidates is None:
        result["pdf_listing"] = listing["record"]
    if pdf_candidates is None:
        result["pdf_discovery_mode"] = "initial_metadata"
    candidates: list[list[str]] = []
    candidate_queries: dict[str, list[dict]] = {}
    exact_metadata: dict[str, tuple[bytes, str]] = {}
    arxiv_metadata: dict[str, tuple[bytes, str, dict]] = {}
    exact_arxiv: dict[str, tuple[bytes, str, dict]] = {}
    budget = _CollectionBudget()
    try:
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=False,
                          headers={"User-Agent": "PaperFactory/0.6 (bounded literature collector)"}) as client:
            for search in list(result["searches"]):
                budget.wait(0, cancel)
                query = search["query"]
                search.update(status="failed", attempted=True)
                query_candidates: list[str] = []
                candidates.append(query_candidates)
                initial_requests = budget.requests
                try:
                    if search["provider"] == "arXiv":
                        identifier = _query_arxiv(query)
                        search.update(lookup="arxiv_id", requested_arxiv_id=identifier)
                        if identifier in exact_arxiv:
                            content, url, details = exact_arxiv[identifier]
                        else:
                            content, url, content_type = _fetch(client, ARXIV, budget=budget, cancel=cancel,
                                params={"id_list": identifier, "max_results": 1})
                            if content_type.split(";", 1)[0].strip() not in {"application/atom+xml", "application/xml", "text/xml"}:
                                raise ValueError("arXiv lookup did not return XML content")
                            details = None
                        path, digest = _save(root, "search-" + hashlib.sha256(query.encode()).hexdigest()[:16], "xml", content)
                        search.update(url=url, raw_path=path, sha256=digest)
                        details = details or _arxiv_metadata(content, identifier)
                        exact_arxiv[identifier] = (content, url, details)
                        key = "arxiv:" + details["arxiv_id"]
                        arxiv_metadata.setdefault(key, (content, url, details))
                        if limit:
                            query_candidates.append(key)
                            candidate_queries.setdefault(key, []).append(search)
                        search["status"] = "succeeded"
                        continue
                    exact_doi = _query_doi(query)
                    if exact_doi is None:
                        resolved = _arxiv_title_lookup(client, query, root, search, budget=budget, cancel=cancel,
                                                       warnings=result["warnings"])
                        if resolved is not None:
                            content, url, details = resolved
                            key = "arxiv:" + details["arxiv_id"]
                            arxiv_metadata.setdefault(key, (content, url, details))
                            if limit:
                                query_candidates.append(key)
                                candidate_queries.setdefault(key, []).append(search)
                            continue
                        if search["provider"] == "arXiv":
                            # Retain negative discovery separately before the
                            # original query continues as a Crossref search.
                            result["searches"].append(dict(search))
                            search.clear()
                            search.update(query=query, provider="Crossref", status="failed", attempted=True, resolved_ids=[])
                        initial_requests = budget.requests
                    search["lookup"] = "doi" if exact_doi else "bibliographic"
                    if exact_doi:
                        search["requested_doi"] = exact_doi
                        if exact_doi not in exact_metadata:
                            content, url, _ = _fetch(client, CROSSREF + "/works/" + quote(exact_doi, safe=""), cancel=cancel, budget=budget)
                        else:
                            content, url = exact_metadata[exact_doi]
                    else:
                        content, url, _ = _fetch(client, CROSSREF + "/works", params={"query.bibliographic": query, "rows": max(1, limit)}, cancel=cancel, budget=budget)
                    path, digest = _save(root, "search-" + hashlib.sha256(query.encode()).hexdigest()[:16], "json", content)
                    search.update({"url": url, "raw_path": path, "sha256": digest})
                    data = json.loads(content)
                    if exact_doi:
                        resolved_doi, _, _, _ = _metadata(data)
                        if resolved_doi != exact_doi:
                            raise ValueError("Crossref resolved a different DOI")
                        exact_metadata[exact_doi] = (content, url)
                        items = [{"DOI": exact_doi}]
                    else:
                        message = data.get("message") if isinstance(data, dict) and data.get("status") == "ok" else None
                        items = message.get("items") if isinstance(message, dict) else None
                        if not isinstance(items, list):
                            raise ValueError("Crossref search did not return a result list")
                    search["status"] = "succeeded"
                except (_Cancelled, _DeadlineExceeded, _RateLimited) as error:
                    if budget.requests == initial_requests:
                        search.update(status="not_attempted", attempted=False)
                    elif isinstance(error, _RateLimited):
                        search.update(error="HTTPStatusError", http_status=429)
                    raise
                except (ValueError, OSError, httpx.HTTPError) as error:
                    search["error"] = type(error).__name__
                    if isinstance(error, httpx.HTTPStatusError):
                        search["http_status"] = error.response.status_code
                    result["warnings"].append(f"{search['provider']} search failed ({type(error).__name__}); no results were inferred")
                    continue
                for item in items[:limit]:
                    try:
                        candidate_doi = item.get("DOI") if isinstance(item, dict) else None
                        if not isinstance(candidate_doi, str):
                            raise ValueError("Crossref candidate has no DOI identifier")
                        doi = _doi(candidate_doi)
                        if doi not in query_candidates:
                            query_candidates.append(doi)
                            candidate_queries.setdefault(doi, []).append(search)
                    except ValueError as error:
                        result["warnings"].append(f"Crossref candidate verification failed ({type(error).__name__}); candidate was omitted")

            hint_dois = {hint["doi"] for hint in hints}
            candidates.sort(key=lambda batch: (not batch or batch[0] not in hint_dois,
                                                not batch or batch[0] not in arxiv_metadata))
            for rank in range(limit):
                if sum(source["scope"] != "metadata_only" for source in result["sources"]) >= limit:
                    break
                for query_candidates in candidates:
                    budget.wait(0, cancel)
                    if rank >= len(query_candidates):
                        continue
                    if sum(source["scope"] != "metadata_only" for source in result["sources"]) >= limit:
                        break
                    candidate = query_candidates[rank]
                    try:
                        if candidate in seen:
                            continue
                        source_id = "source-" + hashlib.sha256(candidate.encode()).hexdigest()[:20]
                        if candidate in arxiv_metadata:
                            metadata, metadata_url, details = arxiv_metadata[candidate]
                            metadata_path, metadata_digest = _save(root, source_id + "-metadata", "xml", metadata)
                            abstract = details["abstract"]
                            source = {key: value for key, value in details.items() if key != "abstract"}
                            document = None
                            pdf_urls = ["https://arxiv.org/pdf/" + source["arxiv_id"]]
                        else:
                            if candidate in exact_metadata:
                                metadata, metadata_url = exact_metadata[candidate]
                            else:
                                metadata, metadata_url, _ = _fetch(client, CROSSREF + "/works/" + quote(candidate, safe=""), cancel=cancel, budget=budget)
                            document = json.loads(metadata)
                            resolved_doi, title, authors, year = _metadata(document)
                            if resolved_doi != candidate:
                                raise ValueError("Crossref resolved a different DOI")
                            metadata_path, metadata_digest = _save(root, source_id + "-metadata", "json", metadata)
                            abstract = _abstract(document["message"].get("abstract"))
                            source = {"doi": candidate, "title": title, "authors": authors, "year": year}
                            pdf_urls = _pdf_links(document["message"])
                        source.update({"id": source_id, "url": metadata_url,
                                        "scope": "abstract" if abstract else "metadata_only",
                                        "excerpts": _excerpts(abstract) if abstract else [],
                                        "raw_path": metadata_path, "sha256": metadata_digest,
                                        "metadata_path": metadata_path, "metadata_sha256": metadata_digest,
                                        "queries": [search["query"] for search in candidate_queries[candidate]]})
                        try:
                            source_hints = [hint for hint in hints if hint["doi"] == candidate]
                            if source_hints:
                                _promote_hinted_pdf(client, source, source_hints, root, listing=listing, budget=budget, cancel=cancel,
                                                    warnings=result["warnings"], attempts=result["pdf_hint_attempts"])
                                # A hinted DOI has one strict route, even when it
                                # fails: it cannot become another generic search.
                                continue
                            if (document is not None and document["message"].get("type") in {"journal-article", "proceedings-article", "posted-content"}
                                    and not any(urlsplit(url).scheme == "https" and urlsplit(url).hostname in PDF_HOSTS
                                                for url in pdf_urls)):
                                try:
                                    arxiv_pdf = _arxiv_pdf(client, source, root, budget=budget, cancel=cancel)
                                    if arxiv_pdf:
                                        # The other URLs are outside the permitted
                                        # provider boundary and remain in raw metadata.
                                        pdf_urls = [arxiv_pdf]
                                except (ValueError, OSError, httpx.HTTPError) as error:
                                    result["warnings"].append(f"arXiv identity-bound discovery unavailable for {source_id} ({type(error).__name__}); reading scope was not upgraded")
                            _promote_full_text(client, source, pdf_urls, root, budget=budget, cancel=cancel, warnings=result["warnings"])
                            if (pdf_candidates is None and document is not None and source["scope"] != "full_text"
                                    and sum(attempt.get("pdf_attempted") is True for attempt in result["pdf_hint_attempts"]) < 2):
                                _promote_hinted_pdf(client, source, [{"doi": source["doi"], "title": source["title"]}], root,
                                                    listing=listing, budget=budget, cancel=cancel,
                                                    warnings=result["warnings"], attempts=result["pdf_hint_attempts"])
                        finally:
                            seen.add(candidate)
                            if len(result["sources"]) < limit:
                                result["sources"].append(source)
                            elif source["scope"] != "metadata_only":
                                replace = next((index for index, existing in enumerate(result["sources"])
                                                if existing["scope"] == "metadata_only"), None)
                                if replace is not None:
                                    result["sources"][replace] = source
                            for search in candidate_queries[candidate]:
                                search["resolved_ids"].append(source_id)
                    except (ValueError, OSError, httpx.HTTPError) as error:
                        result["warnings"].append(f"Literature candidate verification failed ({type(error).__name__}); candidate was omitted")
            budget.wait(0, cancel)
    except (ValueError, OSError, httpx.HTTPError) as error:
        for search in result["searches"]:
            if not search["attempted"]:
                search.update(status="failed", error=type(error).__name__)
        result["warnings"].append(f"Literature provider initialization failed ({type(error).__name__}); no results were inferred")
    except _Cancelled:
        result["cancelled"] = True
        result["warnings"].append("Literature collection was cancelled; partial evidence was preserved")
    except _DeadlineExceeded:
        result["timed_out"] = True
        result["warnings"].append("Literature collection exceeded its time budget; partial evidence was preserved")
    except _RateLimited:
        result["rate_limited"] = True
        result["warnings"].append("Literature provider cooldown exceeded the wait budget; partial evidence was preserved")
    if not any(source["scope"] in {"abstract", "full_text"} for source in result["sources"]):
        result["warnings"].append("No abstract or full text was inspected in this collection attempt. Metadata does not establish related-work findings or novelty")
    return result

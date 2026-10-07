"""Bounded literature retrieval with an explicit distinction between metadata and reading.

Only Crossref records, Crossref-provided abstracts, and allowlisted open-access
PDFs are fetched. Bibliographic search candidates are resolved by DOI before
they become sources. The collector does not infer a finding from a title or DOI.
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
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import getproxies_environment, proxy_bypass_environment
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup

from ..literature import _doi, _metadata
from ..workspace import ensure_unlinked, is_link
from .windows_runtime import WindowsJob

CROSSREF = "https://api.crossref.org"
# Fixed provider boundaries prevent a metadata link from requesting local services.
PDF_HOSTS = frozenset({"arxiv.org", "export.arxiv.org", "joss.theoj.org"})
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGES = 40
MAX_TEXT_CHARS = 90_000
MAX_EXCERPTS = 12
MAX_EXCERPT_CHARS = 1_500


class _Cancelled(Exception):
    pass


def _check_cancel(cancel: Callable[[], bool] | None) -> None:
    if cancel is not None and cancel():
        raise _Cancelled


def _checked_url(url: str, *, pdf: bool = False) -> str:
    """Reject untrusted authorities before DNS or HTTP and private DNS answers."""
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 32 for c in url):
        raise ValueError("Invalid literature URL")
    parts = urlsplit(url)
    hosts = PDF_HOSTS if pdf else frozenset({"api.crossref.org"})
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
    if pdf:
        if parts.hostname in {"arxiv.org", "export.arxiv.org"}:
            if not re.fullmatch(r"/pdf/(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?(?:\.pdf)?", parts.path):
                raise ValueError("Only an arXiv paper PDF endpoint is allowed")
        elif not re.fullmatch(r"/papers/(?:10\.21105/joss\.\d{5}|[a-f0-9]{40})\.pdf", parts.path):
            raise ValueError("Only a JOSS paper PDF endpoint is allowed")
    elif parts.path != "/works" and not parts.path.startswith("/works/10."):
        raise ValueError("Only Crossref work endpoints are allowed")
    try:
        addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
    except OSError as error:
        # Managed cloud egress may delegate DNS to its configured HTTPS proxy.
        # This exception applies only to the fixed provider allowlist above,
        # never to arbitrary publisher hosts, addresses, or redirects.
        proxies = getproxies_environment()
        if proxies.get("https") and not proxy_bypass_environment(parts.hostname, proxies):
            return url
        raise ValueError("Literature provider DNS lookup failed") from error
    if not addresses or any(not ipaddress.ip_address(record[4][0]).is_global for record in addresses):
        raise ValueError("Literature provider resolved to a non-public address")
    return url


def _fetch(
    client: httpx.Client, url: str, *, pdf: bool = False,
    params: dict[str, object] | None = None, cancel: Callable[[], bool] | None = None,
) -> tuple[bytes, str, str]:
    """Stream into a hard bound; validate every redirect before requesting it."""
    maximum = MAX_PDF_BYTES if pdf else MAX_JSON_BYTES
    for redirect in range(4):
        _check_cancel(cancel)
        _checked_url(url, pdf=pdf)
        with client.stream("GET", url, params=params, follow_redirects=False) as response:
            if response.url.scheme != "https" or response.url.host not in (PDF_HOSTS if pdf else {"api.crossref.org"}):
                raise ValueError("Literature response escaped its allowed provider boundary")
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not pdf or not location or redirect == 3:
                    raise ValueError("Literature provider redirect was refused")
                url = urljoin(str(response.url), location)
                params = None
                continue
            response.raise_for_status()
            length = response.headers.get("content-length")
            if length and (not length.isdecimal() or int(length) > maximum):
                raise ValueError("Literature response exceeds its size limit")
            content = bytearray()
            for chunk in response.iter_bytes():
                _check_cancel(cancel)
                content.extend(chunk)
                if len(content) > maximum:
                    raise ValueError("Literature response exceeds its size limit")
            return bytes(content), str(response.url), response.headers.get("content-type", "").lower()
    raise ValueError("Literature provider redirect limit exceeded")


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
            [interpreter, "-I", "-c", worker], stdin=subprocess.PIPE,
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
    # arXiv DOIs have a fixed paper identifier; no guessed DOI or bibliography.
    if isinstance(doi, str) and re.fullmatch(r"10\.48550/arxiv\.\d{4}\.\d{4,5}(?:v\d+)?", doi.lower()):
        identifier = doi.lower().split("arxiv.", 1)[1]
        links.append(f"https://arxiv.org/pdf/{identifier}")
    return list(dict.fromkeys(links))[:2]


def _query_doi(query: str) -> str | None:
    """Recognize an explicitly requested DOI without guessing one from a title."""
    match = re.fullmatch(r"(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?(10\.\d{4,9}/\S+)", query, re.I)
    if match is None:
        match = re.search(r"(?:\bdoi:\s*|https?://(?:dx\.)?doi\.org/)(10\.\d{4,9}/\S+)", query, re.I)
    return _doi(match.group(1)) if match is not None else None


def collect(
    queries: list[str], root: Path, *, limit: int = 6,
    cancel: Callable[[], bool] | None = None,
) -> dict:
    """Collect actual fetched evidence; no network failure becomes a fake source.

    ``raw_path`` is relative to ``root`` and points to the artifact supporting
    the declared reading scope. Metadata remains separately recorded when an
    allowed full text is fetched. All queries are attempted before candidates
    are resolved in round-robin order. Explicit DOIs use an exact lookup;
    bibliographic searches do not exclude records without Crossref abstracts.
    ``cancelled`` preserves partial evidence. Query provenance is not relevance.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 12:
        raise ValueError("Literature source limit must be between 0 and 12")
    if not isinstance(queries, list) or not 1 <= len(queries) <= 8:
        raise ValueError("Provide between 1 and 8 literature queries")
    if any(not isinstance(query, str) or not query.strip() or len(query) > 500 or any(ord(c) < 32 for c in query) for query in queries):
        raise ValueError("Literature queries must contain 1 to 500 printable characters")
    queries = list(dict.fromkeys(query.strip() for query in queries))
    root = _prepare_root(root)
    result: dict = {"sources": [], "searches": [
        {"query": query, "provider": "Crossref", "status": "not_attempted", "attempted": False, "resolved_ids": []}
        for query in queries], "warnings": []}
    seen: set[str] = set()
    candidates: list[list[str]] = []
    candidate_queries: dict[str, list[dict]] = {}
    exact_metadata: dict[str, tuple[bytes, str]] = {}
    try:
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=False,
                          headers={"User-Agent": "PaperFactory/0.6 (bounded literature collector)"}) as client:
            for search in result["searches"]:
                _check_cancel(cancel)
                query = search["query"]
                search.update(status="failed", attempted=True)
                query_candidates: list[str] = []
                candidates.append(query_candidates)
                try:
                    exact_doi = _query_doi(query)
                    search["lookup"] = "doi" if exact_doi else "bibliographic"
                    if exact_doi:
                        search["requested_doi"] = exact_doi
                        if exact_doi not in exact_metadata:
                            content, url, _ = _fetch(client, CROSSREF + "/works/" + quote(exact_doi, safe=""), cancel=cancel)
                        else:
                            content, url = exact_metadata[exact_doi]
                    else:
                        content, url, _ = _fetch(client, CROSSREF + "/works", params={"query.bibliographic": query, "rows": max(1, limit)}, cancel=cancel)
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
                except (ValueError, OSError, httpx.HTTPError) as error:
                    search["error"] = type(error).__name__
                    result["warnings"].append(f"Crossref search failed ({type(error).__name__}); no results were inferred")
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

            for rank in range(limit):
                if sum(source["scope"] != "metadata_only" for source in result["sources"]) >= limit:
                    break
                for query_candidates in candidates:
                    _check_cancel(cancel)
                    if rank >= len(query_candidates):
                        continue
                    if sum(source["scope"] != "metadata_only" for source in result["sources"]) >= limit:
                        break
                    doi = query_candidates[rank]
                    try:
                        if doi in seen:
                            continue
                        if doi in exact_metadata:
                            metadata, metadata_url = exact_metadata[doi]
                        else:
                            metadata, metadata_url, _ = _fetch(client, CROSSREF + "/works/" + quote(doi, safe=""), cancel=cancel)
                        document = json.loads(metadata)
                        resolved_doi, title, authors, year = _metadata(document)
                        if resolved_doi != doi:
                            raise ValueError("Crossref resolved a different DOI")
                        source_id = "source-" + hashlib.sha256(doi.encode()).hexdigest()[:20]
                        metadata_path, metadata_digest = _save(root, source_id + "-metadata", "json", metadata)
                        abstract = _abstract(document["message"].get("abstract"))
                        source: dict = {"id": source_id, "doi": doi, "title": title, "authors": authors,
                                        "year": year, "url": metadata_url,
                                        "scope": "abstract" if abstract else "metadata_only",
                                        "excerpts": _excerpts(abstract) if abstract else [],
                                        "raw_path": metadata_path, "sha256": metadata_digest,
                                        "metadata_path": metadata_path, "metadata_sha256": metadata_digest,
                                        "queries": [search["query"] for search in candidate_queries[doi]]}
                        for pdf_url in _pdf_links(document["message"]):
                            _check_cancel(cancel)
                            try:
                                raw_pdf, retrieved_url, content_type = _fetch(client, pdf_url, pdf=True, cancel=cancel)
                                if "pdf" not in content_type and content_type != "application/octet-stream":
                                    raise ValueError("Open-access provider did not return a PDF content type")
                                full_text = _pdf_text(raw_pdf)
                                raw_path, raw_digest = _save(root, source_id + "-fulltext", "pdf", raw_pdf)
                                text_path, text_digest = _save(root, source_id + "-text", "txt", full_text.encode())
                                source.update({"scope": "full_text", "url": retrieved_url, "raw_path": raw_path,
                                               "sha256": raw_digest, "excerpts": _excerpts(full_text),
                                               "text_path": text_path, "text_sha256": text_digest})
                                break
                            except (ValueError, OSError, httpx.HTTPError) as error:
                                result["warnings"].append(f"Open-access text unavailable for {source_id} ({type(error).__name__}); reading scope was not upgraded")
                        seen.add(doi)
                        if len(result["sources"]) < limit:
                            result["sources"].append(source)
                        elif source["scope"] != "metadata_only":
                            replace = next((index for index, existing in enumerate(result["sources"])
                                            if existing["scope"] == "metadata_only"), None)
                            if replace is not None:
                                result["sources"][replace] = source
                        for search in candidate_queries[doi]:
                            search["resolved_ids"].append(source_id)
                    except (ValueError, OSError, httpx.HTTPError) as error:
                        result["warnings"].append(f"Crossref candidate verification failed ({type(error).__name__}); candidate was omitted")
    except (ValueError, OSError, httpx.HTTPError) as error:
        for search in result["searches"]:
            if not search["attempted"]:
                search.update(status="failed", error=type(error).__name__)
        result["warnings"].append(f"Literature provider initialization failed ({type(error).__name__}); no results were inferred")
    except _Cancelled:
        result["cancelled"] = True
        result["warnings"].append("Literature collection was cancelled; partial evidence was preserved")
    if not any(source["scope"] in {"abstract", "full_text"} for source in result["sources"]):
        result["warnings"].append("No abstract or full text was inspected in this collection attempt. Metadata does not establish related-work findings or novelty")
    return result

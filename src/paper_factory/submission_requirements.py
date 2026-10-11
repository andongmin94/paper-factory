"""Bounded public HTTPS documents for explicit human submission checks.

Fetched bytes establish origin and content identity, not official authority or
the correctness of a person's interpretation. This route has no scientific use.
"""

import hashlib
import http.client
from html.parser import HTMLParser
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit

MAX_REQUIREMENT_BYTES = 2 * 1024 * 1024


def public_https_url(value: str) -> tuple[str, str, str]:
    if not isinstance(value, str) or not 12 <= len(value) <= 2048 or any(ord(c) <= 32 for c in value):
        raise ValueError("Use a bounded public HTTPS requirements URL")
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment
            or parts.port not in (None, 443) or "." not in parts.hostname):
        raise ValueError("Requirements must use a public HTTPS host on port 443 without credentials or fragments")
    host = parts.hostname.encode("idna").decode("ascii")
    if host.endswith(".") or host.lower().endswith((".localhost", ".local", ".internal")):
        raise ValueError("A public requirements host is required")
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError("Local or private requirements addresses are unavailable")
    except ValueError:
        if host.replace(".", "").isdigit() or ":" in host:
            raise ValueError("A public requirements host is required")
    target = (parts.path or "/") + ("?" + parts.query if parts.query else "")
    return value, host, target


class _BodyText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, text):
        if not self.hidden:
            self.chunks.append(text)


def requirement_text(raw: bytes, content_type: str) -> str:
    media = content_type.split(";", 1)[0].strip().lower()
    if media not in {"text/html", "text/plain", "application/xhtml+xml"}:
        raise ValueError("Retain an official HTML or plain-text requirements document")
    text = raw.decode("utf-8-sig", errors="strict")
    if media != "text/plain":
        parser = _BodyText()
        parser.feed(text)
        text = "\n".join(chunk.strip() for chunk in parser.chunks if chunk.strip())
    if len(text.strip()) < 80:
        raise ValueError("The requirements document has insufficient readable body text")
    return text


def fetch_requirements(url: str) -> dict:
    _, host, target = public_https_url(url)
    result = {"status": "failed", "url": url, "http_status": None, "content_type": None,
              "raw": b"", "text": None, "error": None}
    connection = None
    started = time.monotonic()
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        ips = list(dict.fromkeys(item[4][0] for item in addresses))
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise ValueError("Requirements DNS must resolve exclusively to public addresses")
        # Pin the checked address while TLS verifies the original public hostname.
        connection = http.client.HTTPSConnection(host, timeout=5, context=ssl.create_default_context())
        connection._create_connection = lambda address, timeout, source_address=None: socket.create_connection(
            (ips[0], 443), timeout, source_address)
        connection.request("GET", target, headers={"Accept": "text/html,text/plain,application/xhtml+xml",
                                                   "Accept-Encoding": "identity", "User-Agent": "PaperFactory/SubmissionRequirements"})
        response = connection.getresponse()
        result.update(http_status=response.status, content_type=response.getheader("Content-Type", ""))
        chunks, size = [], 0
        while True:
            remaining = 15 - (time.monotonic() - started)
            if remaining <= 0:
                raise ValueError("Requirements retrieval exceeded its total deadline")
            if connection.sock is not None:
                connection.sock.settimeout(min(5, remaining))
            chunk = response.read1(min(64 * 1024, MAX_REQUIREMENT_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            # Preserve partial bytes immediately, including on timeout/overflow.
            result["raw"] = b"".join(chunks)[:MAX_REQUIREMENT_BYTES]
            if size > MAX_REQUIREMENT_BYTES:
                raise ValueError("Requirements body exceeds its retained byte boundary")
        raw = result["raw"]
        if response.status != 200:
            raise ValueError("Requirements HTTP status is not 200; redirects are refused")
        if response.getheader("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("Encoded requirements responses are unavailable")
        result.update(text=requirement_text(raw, result["content_type"]), status="retained")
    except (OSError, ValueError, http.client.HTTPException) as error:
        result["error"] = str(error)[:1000]
    finally:
        if connection is not None:
            connection.close()
    result["raw_sha256"] = hashlib.sha256(result["raw"]).hexdigest()
    return result

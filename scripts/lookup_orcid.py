"""Read public ORCID author facts without authentication or author approval.

Usage: python scripts/lookup_orcid.py ORCID_OR_PROFILE_URL [--output NEW_JSON]
Only the fixed public JSON API is contacted. Existing files are never replaced.
"""

import argparse
import calendar
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_RESPONSE_BYTES = 1024 * 1024
REQUEST_TIMEOUT = 20
SECTIONS = ("person", "employments", "educations")
ORCID_PATTERN = re.compile(r"[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9Xx]")


class OrcidLookupError(ValueError):
    """A controlled public-read error without transport credentials or bodies."""


def normalize_orcid_input(value: str) -> str:
    """Validate ISO 7064 checksum and discard the account-page URL wrapper."""
    if not isinstance(value, str) or len(value) > 256:
        raise OrcidLookupError("Provide a valid ORCID number or HTTPS ORCID profile URL.")
    candidate = value.strip()
    if not ORCID_PATTERN.fullmatch(candidate):
        try:
            url = urlsplit(candidate)
        except ValueError:
            raise OrcidLookupError("Provide a valid ORCID number or HTTPS ORCID profile URL.") from None
        if url.scheme != "https" or url.netloc.lower() != "orcid.org" or url.fragment:
            raise OrcidLookupError("Provide a valid ORCID number or HTTPS ORCID profile URL.")
        if url.path in ("/my-orcid", "/my-orcid/"):
            query = parse_qs(url.query, keep_blank_values=True)
            if set(query) != {"orcid"} or len(query["orcid"]) != 1:
                raise OrcidLookupError("The ORCID account URL must contain only one ORCID number.")
            candidate = query["orcid"][0]
        else:
            if url.query:
                raise OrcidLookupError("Use the ORCID profile URL without query parameters.")
            candidate = url.path.strip("/")
    if not ORCID_PATTERN.fullmatch(candidate):
        raise OrcidLookupError("The ORCID number has an invalid format or checksum.")
    candidate = candidate.upper()
    digits = candidate.replace("-", "")
    total = 0
    for digit in digits[:15]:
        total = (total + int(digit)) * 2
    checksum = (12 - total % 11) % 11
    if digits[-1] != ("X" if checksum == 10 else str(checksum)):
        raise OrcidLookupError("The ORCID number has an invalid format or checksum.")
    return candidate


def _object(value):
    return value if isinstance(value, dict) else {}


def _text(value, maximum=500, *, multiline=False):
    if not isinstance(value, str) or len(value) > maximum or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value):
        return None
    result = value.strip() if multiline else " ".join(value.split())
    return result or None


def _public(value):
    return isinstance(value, str) and value.lower() == "public"


def _date(value):
    """Return the recorded partial date and bounds, without filling its precision."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Invalid ORCID date")
    year, month, day = (_object(value.get(field)).get("value") for field in ("year", "month", "day"))
    if all(value is None for value in (year, month, day)):
        return None
    if not isinstance(year, str) or not re.fullmatch(r"\d{4}", year) or int(year) < 1000:
        raise ValueError("Invalid ORCID date")
    if month is not None and (not isinstance(month, str) or not re.fullmatch(r"0[1-9]|1[0-2]", month)):
        raise ValueError("Invalid ORCID date")
    if day is not None and (month is None or not isinstance(day, str) or not re.fullmatch(r"0[1-9]|[12]\d|3[01]", day)):
        raise ValueError("Invalid ORCID date")
    first_month, last_month = int(month or "1"), int(month or "12")
    last_day = calendar.monthrange(int(year), last_month)[1]
    if day is not None and int(day) > last_day:
        raise ValueError("Invalid ORCID date")
    recorded = year + ("-" + month if month else "") + ("-" + day if day else "")
    return recorded, date(int(year), first_month, int(day or "1")), date(int(year), last_month, int(day or last_day))


def _affiliations(data, orcid, kind, today):
    groups = data.get("affiliation-group")
    if not isinstance(groups, list):
        raise OrcidLookupError("The ORCID public affiliation response is malformed.")
    result = {}
    for group in groups:
        summaries = _object(group).get("summaries")
        if not isinstance(summaries, list):
            continue
        for entry in summaries:
            item = _object(_object(entry).get(kind + "-summary"))
            code = item.get("put-code")
            if not _public(item.get("visibility")) or type(code) is not int or code < 1 or item.get("path") != f"/{orcid}/{kind}/{code}":
                continue
            organization = _object(item.get("organization"))
            name = _text(organization.get("name"))
            try:
                start, end = _date(item.get("start-date")), _date(item.get("end-date"))
            except ValueError:
                continue
            if not name or start and end and start[1] > end[2]:
                continue
            status = "future" if start and start[1] > today else "past" if end and end[2] < today else "not_recorded_as_ended"
            address = _object(organization.get("address"))
            country = _text(address.get("country"), 2)
            result[f"{kind}-{code}"] = {
                "id": f"{kind}-{code}", "kind": kind, "organization": name,
                "department": _text(item.get("department-name")), "role": _text(item.get("role-title")),
                "city": _text(address.get("city")), "region": _text(address.get("region")),
                "country": country if country and re.fullmatch(r"[A-Z]{2}", country) else None,
                "start_date": start[0] if start else None, "end_date": end[0] if end else None,
                "date_status": status, "source_url": f"https://orcid.org/{orcid}",
            }
    return list(result.values())


def _profile(orcid, records, retrieved_at):
    person = records["person"]
    name = _object(person.get("name"))
    visible_name = _public(name.get("visibility"))
    given = _text(_object(name.get("given-names")).get("value"), 250) if visible_name else None
    family = _text(_object(name.get("family-name")).get("value"), 250) if visible_name else None
    credit = _text(_object(name.get("credit-name")).get("value")) if visible_name else None
    display = credit or " ".join(x for x in (given, family) if x) or None
    emails = []
    email_list = _object(person.get("emails")).get("email", [])
    for entry in email_list if isinstance(email_list, list) else []:
        item = _object(entry)
        email = _text(item.get("email"), 254)
        if _public(item.get("visibility")) and item.get("verified") is True and email and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) and email not in emails:
            emails.append(email)
    bio = _object(person.get("biography"))
    biography = _text(bio.get("content"), 10000, multiline=True) if _public(bio.get("visibility")) else None
    today = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00")).date()
    affiliations = _affiliations(records["employments"], orcid, "employment", today) + _affiliations(records["educations"], orcid, "education", today)
    public_fields = {"display_name": display, "emails": emails, "biography": biography, "affiliations": affiliations}
    return {
        "orcid": orcid, "source_url": f"https://orcid.org/{orcid}", "retrieved_at": retrieved_at,
        "public_only": True, "authenticated": False, "given_name": given, "family_name": family,
        **public_fields, "missing_public_fields": [key for key, value in public_fields.items() if not value],
        "author_confirmation_required": True,
        "affiliation_scope": "Public records, including dated history. No recorded end is not proof of a current affiliation; the author must select and confirm the submission affiliation.",
    }


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _public_record(orcid, section, opener, deadline):
    url = f"https://pub.orcid.org/v3.0/{orcid}/{section}"
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise OrcidLookupError("The ORCID public lookup timed out.")
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Paper-Factory-Public-ORCID"})
    try:
        # Subtracting float clock values can round just above the request limit.
        with opener.open(request, timeout=min(remaining, REQUEST_TIMEOUT)) as response:
            if response.status != 200 or response.geturl() != url:
                raise OrcidLookupError("The ORCID public response did not match the requested endpoint.")
            mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if mime not in ("application/json", "application/vnd.orcid+json"):
                raise OrcidLookupError("The ORCID public response is not JSON.")
            length = response.headers.get("Content-Length")
            if length is not None and (not re.fullmatch(r"\d+", length) or int(length) > MAX_RESPONSE_BYTES):
                raise OrcidLookupError("The ORCID public response exceeds its size limit.")
            chunks, size = [], 0
            while True:
                if time.monotonic() >= deadline:
                    raise OrcidLookupError("The ORCID public lookup timed out.")
                chunk = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise OrcidLookupError("The ORCID public response exceeds its size limit.")
                chunks.append(chunk)
            try:
                data = json.loads(b"".join(chunks).decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                raise OrcidLookupError("The ORCID public response is malformed JSON.") from None
            if not isinstance(data, dict) or data.get("path") != f"/{orcid}/{section}":
                raise OrcidLookupError("The public response identifier does not match the requested ORCID.")
            return data
    except HTTPError as error:
        message = "The ORCID public record was not found." if error.code == 404 else "The ORCID public request failed; redirects are not followed."
        if error.fp is not None:
            error.close()
        raise OrcidLookupError(message) from None
    except (TimeoutError, URLError, OSError):
        raise OrcidLookupError("Could not read the ORCID public record within the network time limit.") from None


def lookup_public_orcid(value, *, opener=None, retrieved_at=None):
    """Fetch only anonymous public facts, preserving absent data and provenance."""
    orcid = normalize_orcid_input(value)
    opener = opener or build_opener(_NoRedirects())
    deadline = time.monotonic() + REQUEST_TIMEOUT
    records = {section: _public_record(orcid, section, opener, deadline) for section in SECTIONS}
    retrieved_at = retrieved_at or datetime.now(timezone.utc).isoformat()
    return _profile(orcid, records, retrieved_at)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("orcid", help="ORCID number or HTTPS profile URL")
    parser.add_argument("--output", type=Path, help="Optional new JSON file; existing files are refused")
    args = parser.parse_args(argv)
    try:
        if args.output is not None and (args.output.exists() or args.output.is_symlink()):
            raise OrcidLookupError("The output already exists; existing files are never replaced.")
        result = lookup_public_orcid(args.orcid)
        content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output is not None:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
        print(content, end="")
        return 0
    except OrcidLookupError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except OSError:
        print(json.dumps({"error": "Could not create the new output file; no existing file was replaced."}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

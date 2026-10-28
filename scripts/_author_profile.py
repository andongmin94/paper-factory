"""Explicit reusable author facts shared by preparation and native export."""

import re

BIOGRAPHY_FIELDS = ("role", "location", "research_interests", "highest_degree", "degree_institution", "professional_membership")

def _text(value, label, *, required=False):
    if not isinstance(value, str) or any(ord(c) < 32 and c not in "\n\r\t" or ord(c) == 127 for c in value):
        raise ValueError(label + " must be text without prohibited controls")
    result = value.strip()
    if required and not result:
        raise ValueError(label + " must not be empty")
    return result


def profile_completeness(profile):
    """Presence of facts, never confirmation that a person approved them."""
    rows = []
    for entry in (profile or {}).get("authors", []):
        author = entry["author"]
        missing = [key for key in ("display_name", "affiliation", "email", "orcid", "biography") if not author.get(key)]
        missing += ["biography_details." + key for key in BIOGRAPHY_FIELDS if not (author.get("biography_details") or {}).get(key)]
        rows.append({"id": entry["id"], "display_name": author.get("display_name"), "missing_fields": missing,
                     "supplied_fields_complete": not missing, "author_confirmation_required": True})
    return rows

def _explicit_author(value: object) -> dict:
    """Validate explicit facts without ambient profiles or inferred consent.

    Ordinary fields are single-line and reject C0/DEL characters. Biography
    and its factual detail values may contain LF, CR and TAB, but reject all
    other C0 characters and DEL. Validation precedes boundary-whitespace trim.
    """
    def clean_text(name: str, item: object, *, multiline: bool = False) -> str:
        if not isinstance(item, str):
            raise ValueError(f"Author field {name} must be text")
        if any((ord(c) < 32 and not (multiline and c in "\n\r\t")) or ord(c) == 127 for c in item):
            raise ValueError(f"Author field {name} contains a prohibited control character")
        if not multiline and any(c in "\x85\u2028\u2029" for c in item):
            raise ValueError(f"Author field {name} must be single-line text")
        return item.strip()

    if not isinstance(value, dict):
        raise ValueError("Author input must be a JSON object")
    fields = {"given_name", "family_name", "display_name", "email", "orcid", "affiliation",
              "department", "city", "country", "scholar_id", "github", "homepage", "biography"}
    if set(value) - fields - {"biography_details"}:
        raise ValueError("Unknown author input fields: " + ", ".join(sorted(set(value) - fields - {"biography_details"})))
    result = {}
    for name, item in value.items():
        if name == "biography_details":
            if not isinstance(item, dict):
                raise ValueError("biography_details must map field names to factual text")
            details = {}
            for key, text in item.items():
                clean_text("biography_details key", key)
                cleaned = clean_text("biography_details." + key, text, multiline=True)
                if cleaned:
                    details[key] = cleaned
            result[name] = details
            continue
        cleaned = clean_text(name, item, multiline=name == "biography")
        if cleaned:
            result[name] = cleaned
    if result.get("email") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", result["email"]):
        raise ValueError("Author email requires a local name and domain")
    if result.get("orcid"):
        identifier = result["orcid"].upper()
        if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", identifier, re.ASCII):
            raise ValueError("ORCID must use the 0000-0000-0000-0000 format")
        digits, total = identifier.replace("-", ""), 0
        for digit in digits[:15]:
            total = (total + int(digit)) * 2
        check = (12 - total % 11) % 11
        if digits[-1] != ("X" if check == 10 else str(check)):
            raise ValueError("ORCID checksum is invalid")
        result["orcid"] = identifier
    if not result.get("display_name") and result.get("given_name") and result.get("family_name"):
        result["display_name"] = result["given_name"] + " " + result["family_name"]
    return result


def normalize_profile(value):
    if not isinstance(value, dict) or not isinstance(value.get("authors"), list) or not value["authors"]:
        raise ValueError("Profile requires a non-empty authors list")
    authors, identifiers = [], set()
    for entry in value["authors"]:
        if not isinstance(entry, dict):
            raise ValueError("Each author must be an object")
        identifier = _text(entry.get("id"), "author id", required=True)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", identifier) or identifier in identifiers:
            raise ValueError("Author ids must be unique simple identifiers")
        identifiers.add(identifier)
        author = _explicit_author(entry.get("author"))
        contributions = entry.get("contributions", [])
        if not isinstance(contributions, list):
            raise ValueError("contributions must be a list of supplied role names")
        authors.append({"id": identifier, "author": author,
                        "contributions": [_text(x, "contribution", required=True) for x in contributions]})
    order = value.get("order")
    if not isinstance(order, list) or any(not isinstance(x, str) for x in order) or len(order) != len(identifiers) or set(order) != identifiers:
        raise ValueError("order must contain each author id exactly once")
    corresponding = value.get("corresponding_author")
    if corresponding is not None and (not isinstance(corresponding, str) or corresponding not in identifiers):
        raise ValueError("corresponding_author must name an author id or be null")
    ordered = sorted(authors, key=lambda author: order.index(author["id"]))
    result = {"authors": ordered, "order": order, "corresponding_author": corresponding}
    for name in ("funding", "conflicts"):
        result[name] = None if value.get(name) is None else _text(value[name], name)
    return result

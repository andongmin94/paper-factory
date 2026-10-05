"""Strict Crossref DOI and bibliographic metadata parsing for the collector."""

import re


def _doi(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"10\.\d{4,9}/[^\s\x00-\x1f\x7f]+", value):
        raise ValueError("Expected a DOI identifier such as 10.1234/example, not a URL")
    if any(part in {".", ".."} for part in value.split("/")):
        raise ValueError("DOI cannot contain dot path segments")
    return value


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

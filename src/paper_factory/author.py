"""Load author metadata from explicit inputs and the environment, without side effects."""

import json
import os
import re
from collections.abc import Mapping
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, field_validator


class AuthorProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)

    given_name: str = ""
    family_name: str = ""
    display_name: str = ""
    email: str = ""
    orcid: str = ""
    affiliation: str = ""
    department: str = ""
    city: str = ""
    country: str = ""
    scholar_id: str = ""
    github: str = ""
    homepage: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            if any(ord(character) < 32 and not character.isspace() or ord(character) == 127 for character in value):
                raise ValueError("Author metadata cannot contain control characters")
            return value.strip()
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        if value and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Author email must contain a local name and domain, e.g. name@example.org")
        return value

    @field_validator("orcid")
    @classmethod
    def valid_orcid(cls, value: str) -> str:
        if not value:
            return value
        value = value.upper()
        if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", value, re.ASCII):
            raise ValueError("ORCID must use the format 0000-0000-0000-0000")
        digits = value.replace("-", "")
        total = 0
        for digit in digits[:15]:
            total = (total + int(digit)) * 2
        check = (12 - total % 11) % 11
        expected = "X" if check == 10 else str(check)
        if digits[-1] != expected:
            raise ValueError("ORCID checksum is invalid")
        return value

    @field_validator("github", "homepage")
    @classmethod
    def valid_url(cls, value: str) -> str:
        if not value:
            return value
        try:
            parts = urlsplit(value)
            valid = parts.scheme in {"https", "http"} and bool(parts.hostname)
            # Accessing the port also validates malformed URL port values.
            _ = parts.port
        except ValueError:
            valid = False
        if not valid or any(character.isspace() for character in value):
            raise ValueError("Author URLs must be absolute http:// or https:// URLs")
        return value


def _author_values(value: object, source: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{source} must be a JSON object or author field mapping")
    unknown = set(value) - set(AuthorProfile.model_fields)
    if unknown:
        raise ValueError(f"Unknown author fields in {source}: {', '.join(sorted(map(str, unknown)))}")
    result = {}
    for field, item in value.items():
        if not isinstance(item, str):
            raise ValueError(f"{source}.{field} must be a string")
        result[field] = item.strip()
    return result


def load_author(
    explicit: dict | None = None,
    project_metadata: dict | None = None,
    environ: Mapping | None = None,
    require: bool = False,
) -> AuthorProfile:
    """Use nonempty explicit > individual env > JSON env > project values.

    No files are read or written, and .env is never loaded automatically. The
    supplied project metadata is an author field mapping, not the whole project.
    Empty values do not erase a value from a lower-priority source.
    """
    environment = os.environ if environ is None else environ
    values = _author_values(project_metadata if project_metadata is not None else {}, "project metadata")
    profile_json = environment.get("PF_AUTHOR_PROFILE_JSON", "")
    if not isinstance(profile_json, str):
        raise ValueError("PF_AUTHOR_PROFILE_JSON must be a string containing a JSON object")
    if profile_json.strip():
        try:
            decoded = json.loads(profile_json)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid PF_AUTHOR_PROFILE_JSON: {error.msg}") from error
        json_values = _author_values(decoded, "PF_AUTHOR_PROFILE_JSON")
        values.update({field: value for field, value in json_values.items() if value})

    for field in AuthorProfile.model_fields:
        variable = f"PF_AUTHOR_{field.upper()}"
        value = environment.get(variable, "")
        if not isinstance(value, str):
            raise ValueError(f"{variable} must be a string")
        if value.strip():
            values[field] = value.strip()

    explicit_values = _author_values(explicit if explicit is not None else {}, "explicit author values")
    values.update({field: value for field, value in explicit_values.items() if value})
    profile = AuthorProfile.model_validate(values)
    if require:
        missing = []
        if not profile.display_name and not (profile.given_name and profile.family_name):
            missing.append("display_name or both given_name and family_name")
        missing.extend(field for field in ("email", "affiliation") if not getattr(profile, field))
        if missing:
            raise ValueError(f"Required author metadata missing: {', '.join(missing)}")
    if not profile.display_name and profile.given_name and profile.family_name:
        profile.display_name = f"{profile.given_name} {profile.family_name}"
    return profile

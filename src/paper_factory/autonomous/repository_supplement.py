"""Bounded supplied evidence; imported bytes are not a native fetch or a new experiment."""

import base64
import hashlib
import re
from typing import Literal
from urllib.parse import unquote, urlsplit

from pydantic import Field, model_validator

from ..models import Record

class SupplementReview(Record):
    venue_id: str = Field(min_length=3, max_length=100)
    draft_artifact_id: str
    draft_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_artifact_id: str
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SupplementMember(Record):
    name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}\.(?:md|txt|json|html|pdf)$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=1, le=1024 * 1024)
    original_path: str | None = None

    @model_validator(mode="after")
    def relative_original(self):
        device = self.name.split(".", 1)[0].upper()
        if self.name.lower() in {"intent.json", "receipt.json"} or device in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}:
            raise ValueError("Supplement names cannot use native receipt or Windows device names")
        if self.original_path is not None and (not self.original_path or "\\" in self.original_path or
                self.original_path.startswith("/") or ":" in self.original_path or
                any(part in {"", ".", ".."} for part in self.original_path.split("/"))):
            raise ValueError("Original paths must be exact research-relative file paths")
        return self


class SupplementMaterial(Record):
    id: str = Field(pattern=r"^(?:supplement-[A-Za-z0-9_-]{1,80}|source-[a-f0-9]{20})$")
    kind: Literal["case_source", "requirement", "primary_body", "supplied_result"]
    name: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str = Field(min_length=3, max_length=500)
    url: str = Field(min_length=8, max_length=2000)
    provenance: Literal["supplied_snapshot", "supplied_primary_copy", "supplied_interpretation"]
    case_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,80}$")
    path: str | None = None
    commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    primary_source: dict | None = None
    primary_proof: dict | None = None

    @model_validator(mode="after")
    def provenance_identity(self):
        url = urlsplit(self.url)
        if (any(character.isspace() for character in self.url) or "\n" in self.title or "\r" in self.title or
                url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment):
            raise ValueError("Supplied origins must be explicit HTTPS URLs without credentials or fragments")
        if self.kind == "primary_body":
            if (self.provenance != "supplied_primary_copy" or self.primary_source is None or self.primary_proof is None or
                    self.primary_source.get("id") != self.id or self.primary_source.get("text_sha256") != self.sha256 or
                    self.primary_source.get("url") != self.url or
                    any(value is not None for value in (self.case_id, self.path, self.commit))):
                raise ValueError("A primary copy requires its unchanged source and original attempt proof")
            copy_type = self.primary_source.get("copy_type")
            proof_kind = "html_attempts" if copy_type == "scholarly_html" else "pdf_hint_attempts"
            if (copy_type not in {"scholarly_html", "repository_copy"} or
                    copy_type == "repository_copy" and not self.primary_source.get("publisher_url") or
                    set(self.primary_proof) != {proof_kind} or not isinstance(self.primary_proof[proof_kind], list) or
                    len(self.primary_proof[proof_kind]) != 1):
                raise ValueError("A primary copy requires exact scholarly HTML or official publisher PDF attempt proof")
        else:
            if not self.id.startswith("supplement-") or self.primary_source is not None or self.primary_proof is not None:
                raise ValueError("Supplied case documents cannot impersonate a primary literature source")
            expected = "supplied_interpretation" if self.kind == "supplied_result" else "supplied_snapshot"
            if self.provenance != expected:
                raise ValueError("Supplied origin and interpretation must be distinguished")
            if self.kind == "case_source":
                if (not self.case_id or not self.path or not self.commit or url.hostname != "github.com" or url.query or
                        any(part in {"", ".", ".."} for part in self.path.split("/")) or "\\" in self.path or
                        not re.fullmatch(r"/[^/]+/[^/]+/blob/" + self.commit + r"/" + re.escape(self.path), unquote(url.path))):
                    raise ValueError("A supplied case source must bind its own GitHub URL, exact path and commit")
            elif any(value is not None for value in (self.case_id, self.path, self.commit)):
                raise ValueError("Case identities belong to supplied case sources only")
        return self


class SupplementSelection(Record):
    rationale: str = Field(min_length=30, max_length=10000)
    lineage: str = Field(min_length=30, max_length=10000)


class SupplementWitness(Record):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    material_id: str
    quote: str = Field(min_length=20, max_length=12000)


class SupplementResult(Record):
    claim: str = Field(min_length=30, max_length=12000)
    evidence_ids: list[str] = Field(min_length=1, max_length=30)
    limitations: str = Field(min_length=30, max_length=12000)


class SupplementComparison(Record):
    protocol: str = Field(min_length=50, max_length=20000)
    witnesses: list[SupplementWitness] = Field(min_length=1, max_length=30)
    results: list[SupplementResult] = Field(min_length=1, max_length=20)
    provenance: Literal["supplied_interpretation"]


class PortfolioSupplement(Record):
    prior_analysis_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prior_literature_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviews: list[SupplementReview] = Field(min_length=1, max_length=9)
    members: list[SupplementMember] = Field(min_length=1, max_length=32)
    materials: list[SupplementMaterial] = Field(min_length=1, max_length=32)
    selection: SupplementSelection
    comparison: SupplementComparison

    @model_validator(mode="after")
    def linked_members(self):
        members = {item.name: item for item in self.members}
        materials = {item.id: item for item in self.materials}
        witnesses = {item.id: item for item in self.comparison.witnesses}
        originals = [item.original_path for item in self.members if item.original_path is not None]
        if (len({name.lower() for name in members}) != len(self.members) or len(materials) != len(self.materials) or
                len(witnesses) != len(self.comparison.witnesses) or len(set(originals)) != len(originals) or
                len({item.venue_id for item in self.reviews}) != len(self.reviews)):
            raise ValueError("Supplement members, identities and review targets must be unique and bounded")
        pdf_members = {item.name for item in self.members if _publisher_pdf_member(item, self.materials)}
        if (sum(item.size for item in self.members if item.name in pdf_members) > 1024 * 1024 or
                sum(item.size for item in self.members if item.name not in pdf_members) > 512 * 1024 or
                any(item.size > _text_member_limit(item, self.materials) or item.name.endswith(".pdf") for item in self.members if item.name not in pdf_members) or
                any(not item.name.endswith(".pdf") for item in self.members if item.name in pdf_members)):
            raise ValueError("Bound publisher PDFs share 1 MiB; text shares 512 KiB, exact whole case sources allow 256 KiB and other text 128 KiB")
        if any(item.name not in members or item.sha256 != members[item.name].sha256 for item in self.materials):
            raise ValueError("Each scientific material requires an exact declared member and SHA")
        if not any(item.kind in {"case_source", "primary_body"} for item in self.materials):
            raise ValueError("Protocol notes and supplied interpretations alone are not new primary or case evidence")
        if any(item.material_id not in materials for item in self.comparison.witnesses):
            raise ValueError("Every comparison witness must identify a retained scientific material")
        used = {name for item in self.comparison.results for name in item.evidence_ids}
        if used != set(witnesses) or any(len(set(item.evidence_ids)) != len(item.evidence_ids) for item in self.comparison.results):
            raise ValueError("Every declared witness must support an explicit, limited comparison result")
        if {item.material_id for item in self.comparison.witnesses} != set(materials):
            raise ValueError("Every supplied scientific material must have a literal comparison witness")
        used_members = {item.name for item in self.materials}
        for item in self.materials:
            if item.kind == "primary_body":
                for field in ("raw_path", "metadata_path", "text_path", "discovery_path", "identity_path"):
                    matches = [member.name for member in self.members if member.original_path == item.primary_source.get(field)]
                    if len(matches) != 1:
                        raise ValueError("A scholarly primary copy requires all five exact original proof members")
                    used_members.update(matches)
        if used_members != set(members):
            raise ValueError("Unbound auxiliary files cannot be imported as scientific evidence")
        return self


def _publisher_pdf_member(member: SupplementMember, materials: list[SupplementMaterial]) -> bool:
    return any(material.kind == "primary_body" and material.primary_source.get("copy_type") == "repository_copy" and
        member.original_path == material.primary_source.get("raw_path") and member.sha256 == material.primary_source.get("sha256")
        for material in materials)


def _text_member_limit(member: SupplementMember, materials: list[SupplementMaterial]) -> int:
    return (256 if any(material.kind == "case_source" and material.name == member.name and
        material.sha256 == member.sha256 for material in materials) else 128) * 1024


def decode_supplement_files(value: PortfolioSupplement, files: list[dict]) -> dict[str, bytes]:
    """Match a complete manifest before reserving an admission; no IO or acquisition."""
    if not isinstance(files, list) or len(files) != len(value.members):
        raise ValueError("Supply each declared member exactly once")
    declared = {item.name: item for item in value.members}
    decoded = {}
    for item in files:
        if not isinstance(item, dict) or set(item) != {"name", "contentBase64"} or item["name"] not in declared or item["name"] in decoded:
            raise ValueError("Supplied files must match the named manifest exactly")
        encoded = item["contentBase64"]
        member = declared[item["name"]]
        publisher_pdf = _publisher_pdf_member(member, value.materials)
        byte_limit = 1024 * 1024 if publisher_pdf else _text_member_limit(member, value.materials)
        if not isinstance(encoded, str) or len(encoded) > 4 * ((byte_limit + 2) // 3):
            raise ValueError("Supplement files exceed the existing supporting-file byte boundary")
        raw = base64.b64decode(encoded, validate=True)
        if (base64.b64encode(raw).decode("ascii") != encoded or len(raw) != member.size or
                hashlib.sha256(raw).hexdigest() != member.sha256):
            raise ValueError("Supplied file size, canonical base64 and SHA must match")
        if publisher_pdf:
            if not raw.startswith(b"%PDF-"):
                raise ValueError("Bound publisher raw PDF members must preserve the original PDF signature")
            decoded[item["name"]] = raw
            continue
        if raw.startswith(b"%PDF-"):
            raise ValueError("Binary PDF bytes require their exact official publisher proof binding")
        proof_html = any(material.kind == "primary_body" and any(
            member.original_path == material.primary_source.get(path) and member.sha256 == material.primary_source.get(digest)
            for path, digest in (("raw_path", "sha256"), ("metadata_path", "metadata_sha256"))) for material in value.materials)
        if proof_html:
            # Frozen publisher HTML can use Latin1. Its exact original bytes
            # are subsequently decoded and re-derived by the scholarly verifier.
            if not re.search(br"<(?:!doctype\s+html|html|head|body)\b", raw[:4096], re.I):
                raise ValueError("Original HTML proof members must contain HTML, not arbitrary binary")
        else:
            text = raw.decode("utf-8")
            if not text.strip() or any(ord(character) < 32 and character not in "\n\r\t" for character in text):
                raise ValueError("Scientific material and identity files must be complete readable UTF-8")
        decoded[item["name"]] = raw
    for witness in value.comparison.witnesses:
        material = next(item for item in value.materials if item.id == witness.material_id)
        body = decoded[material.name].decode("utf-8")
        if material.kind == "primary_body":
            bounds = material.primary_source.get("body_range", {})
            start, end = bounds.get("start"), bounds.get("end")
            if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(body):
                raise ValueError("Primary witnesses require their original full scientific body range")
            body = body[start:end]
        if witness.quote not in body:
            raise ValueError("Comparison witnesses must be literal spans of the supplied immutable material")
    return decoded

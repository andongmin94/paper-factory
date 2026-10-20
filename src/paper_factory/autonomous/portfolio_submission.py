"""Human-confirmed submission packages and portal records for one IEEE venue.

Packaging is deterministic file assembly, never a model request or a portal
submission. Every human declaration is retained separately from research evidence.
"""

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

from ..models import Record, now
from ..publication_venues import CATALOG_PATH, publication_catalog
from .repository_paper import RepositoryReview

PORTALS = {
    "ieee-software": "https://ieee.atyponrex.com/journal/sw-cs",
    "ieee-security-privacy": "https://ieee.atyponrex.com/journal/sp-cs",
}
PREFIX = "repository-portfolio-submission-"
ROOT = "research/repository/portfolio/submission"
SHA = Annotated[StrictStr, Field(pattern=r"^[a-f0-9]{64}$")]
ShortText = Annotated[StrictStr, Field(min_length=1, max_length=4000)]


class SubmissionPhoto(Record):
    filename: StrictStr = Field(min_length=5, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:png|jpg|jpeg)$")
    media_type: Literal["image/png", "image/jpeg"]
    base64: StrictStr = Field(min_length=8, max_length=699052)


class SubmissionBiographyDetails(Record):
    role: ShortText
    location: ShortText
    research_interests: ShortText
    highest_degree: ShortText
    degree_institution: ShortText
    professional_membership: ShortText

    @field_validator("*")
    @classmethod
    def actual_fact(cls, value):
        text = value.strip()
        if not text or re.fullmatch(r"(?i)(?:tbd|pending|미정|확인 대기)", text) or any(ord(char) < 32 for char in text):
            raise ValueError("Supply actual biography facts, or explicitly state none/not applicable when true")
        return text


class SubmissionFileQA(Record):
    word_count: StrictInt = Field(ge=1, le=100000)
    docx_pages: StrictInt = Field(ge=1, le=100)
    pdf_pages: StrictInt = Field(ge=1, le=100)
    table_count: StrictInt = Field(ge=0, le=50)
    figure_count: StrictInt = Field(ge=0, le=50)


class SubmissionDeclarations(Record):
    identity_confirmed: StrictBool
    all_authors_approved: StrictBool
    originality_confirmed: StrictBool
    rights_confirmed: StrictBool
    ai_disclosure_reviewed: StrictBool
    guidelines_reviewed: StrictBool
    all_pages_reviewed: StrictBool

    @model_validator(mode="after")
    def explicit_approval(self):
        if not all(getattr(self, field) for field in type(self).model_fields):
            raise ValueError("Submission preparation requires every explicit affirmative human confirmation")
        return self


class PortfolioSubmissionPreparation(Record):
    expected_draft_sha256: SHA
    expected_review_sha256: SHA
    expected_author_sha256: SHA
    expected_pdf_sha256: SHA
    expected_docx_sha256: SHA
    author_biography: StrictStr = Field(min_length=40, max_length=4000)
    biography_details: SubmissionBiographyDetails
    keywords: list[Annotated[StrictStr, Field(min_length=2, max_length=100)]] = Field(min_length=3, max_length=8)
    photo: SubmissionPhoto | None
    funding_statement: ShortText
    conflicts_statement: ShortText
    cover_letter_note: StrictStr = Field(max_length=4000)

    @field_validator("author_biography", "funding_statement", "conflicts_statement", "cover_letter_note")
    @classmethod
    def literal_text(cls, value):
        if any(ord(char) < 32 and char not in "\n\t\r" or ord(char) == 127 for char in value):
            raise ValueError("Submission text must not contain control characters")
        if not value.strip() and value:
            raise ValueError("Submission statements must contain meaningful text")
        return value.strip()

    @field_validator("keywords")
    @classmethod
    def distinct_keywords(cls, value):
        stripped = [word.strip() for word in value]
        if any(len(word) < 2 or any(ord(char) < 32 for char in word) for word in stripped) or len({word.casefold() for word in stripped}) != len(value):
            raise ValueError("Submission keywords must be distinct nonempty phrases")
        return stripped


class PortfolioSubmissionConfirmation(Record):
    preparation_sha256: SHA
    expected_docx_sha256: SHA
    expected_pdf_sha256: SHA
    qa: SubmissionFileQA
    declarations: SubmissionDeclarations


class PortfolioSubmissionRecord(Record):
    preparation_sha256: SHA
    status: Literal["submitted", "withdrawn", "rejected"]
    manuscript_id: StrictStr = Field(max_length=200)
    occurred_at: StrictStr = Field(min_length=10, max_length=64)
    confirmed: StrictBool
    note: StrictStr = Field(min_length=8, max_length=4000)

    @field_validator("manuscript_id", "note")
    @classmethod
    def record_text(cls, value):
        return value.strip()

    @model_validator(mode="after")
    def human_record(self):
        if not self.confirmed:
            raise ValueError("Portal status requires an explicit actual human confirmation")
        if len(self.note) < 8 or any(ord(char) < 32 for char in self.manuscript_id):
            raise ValueError("Submission records require literal meaningful identifiers and notes")
        if self.status == "submitted" and not self.manuscript_id:
            raise ValueError("Submitted status requires the manuscript ID issued by the actual portal")
        try:
            instant = datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Submission occurrence must be an ISO timestamp with a timezone") from None
        if instant.tzinfo is None or instant > datetime.now(timezone.utc):
            raise ValueError("Submission occurrence must be a past or present timestamp with a timezone")
        return self


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _plain_markdown(value):
    """Treat biography/keyword text as text, never executable markup."""
    return re.sub(r"([\\`*_{}\[\]()<>#!|$+.\-])", r"\\\1", value)


def _submission_manuscript(original, biography, keywords, *, funding_statement=None, conflicts_statement=None):
    """Replace editorial metadata once; retain the original and scientific prose."""
    retained_original = original
    replaced = []
    existing_keywords = list(re.finditer(rb"(?m)^Keywords:[^\r\n]*(?:\r?\n)?", original))
    if len(existing_keywords) > 1:
        raise ValueError("Resolve duplicate keyword paragraphs before submission preparation")
    if existing_keywords:
        match = existing_keywords[0]
        replaced.append({"kind": "keywords", "sha256": hashlib.sha256(match[0]).hexdigest()})
        original = original[:match.start()] + original[match.end():]
    existing_bio = re.search(rb"(?m)^## Author Biography\r?$", original)
    if existing_bio:
        if re.search(rb"(?m)^## ", original[existing_bio.end():]):
            raise ValueError("The author biography must be the final editorial section")
        replaced.append({"kind": "biography", "sha256": hashlib.sha256(original[existing_bio.start():]).hexdigest()})
        original = original[:existing_bio.start()].rstrip() + b"\n"
    supplements = []
    if funding_statement is not None or conflicts_statement is not None:
        statements = [("Funding", funding_statement), ("Conflicts of interest", conflicts_statement)]
        text = "\n\n".join(label + ": " + _plain_markdown(value) for label, value in statements if value is not None)
        references = re.search(rb"(?m)^## References\r?$", original)
        if references is None:
            raise ValueError("Submission funding/conflict supplements require the retained References boundary")
        acknowledgment = list(re.finditer(rb"(?mi)^## Acknowledg(?:e)?ments?\r?$", original[:references.start()]))
        if len(acknowledgment) > 1:
            raise ValueError("Resolve duplicate acknowledgment sections before adding author-supplied declarations")
        if acknowledgment:
            following = re.search(rb"(?m)^## ", original[acknowledgment[0].end():])
            offset = acknowledgment[0].end() + following.start() if following else references.start()
            addition = ("\n" + text + "\n\n").encode()
        else:
            offset = references.start()
            addition = ("## Acknowledgments\n\n" + text + "\n\n").encode()
        original = original[:offset] + addition + original[offset:]
        supplements.append({"kind": "author_funding_conflicts", "insertion_offset": offset,
                            "sha256": hashlib.sha256(addition).hexdigest()})
    abstract = re.search(rb"(?m)^## Abstract\r?$", original)
    boundary = re.search(rb"(?m)^## ", original[abstract.end():]) if abstract else None
    if boundary is None:
        raise ValueError("Submission supplement requires the exact retained Abstract and following section boundary")
    offset = abstract.end() + boundary.start()
    insertion = ("Keywords: " + "; ".join(_plain_markdown(word) for word in keywords) + "\n\n").encode()
    suffix = ("\n\n## Author Biography\n\n" + _plain_markdown(biography) + "\n").encode()
    output = original[:offset] + insertion + original[offset:] + suffix
    if output[:offset] + output[offset + len(insertion):-len(suffix)] != original:
        raise ValueError("Submission supplements must preserve every original manuscript byte")
    transformation = {"insertion_offset": offset, "insertion_sha256": hashlib.sha256(insertion).hexdigest(),
        "suffix_sha256": hashlib.sha256(suffix).hexdigest(), "original_sha256": hashlib.sha256(original).hexdigest(),
        "scope": "plain-keywords-after-abstract-and-plain-biography-after-bibliography; exact original bytes reversible"}
    if replaced:
        transformation.update(original_sha256=hashlib.sha256(retained_original).hexdigest(),
            editorial_base_sha256=hashlib.sha256(original).hexdigest(), replaced_metadata=replaced,
            scope="Replace existing editorial keyword/biography metadata exactly once; scientific prose retained and exact original artifact preserved")
    if supplements:
        transformation.update(original_sha256=hashlib.sha256(retained_original).hexdigest(),
            editorial_base_sha256=hashlib.sha256(original).hexdigest(), declaration_supplements=supplements,
            scope="Add actual supplied funding/conflict declarations and replace editorial keywords/biography; scientific prose and original artifact retained")
    return output, transformation


def _submission_biography(prose, details):
    """Render the six supplied facts without inferring an author fact or consent."""
    labels = {"role": "Role", "location": "Location", "research_interests": "Research interests",
              "highest_degree": "Highest degree", "degree_institution": "Degree institution",
              "professional_membership": "Professional membership"}
    supplied = " ".join(prose.split())
    facts = "; ".join(label + ": " + details[key] for key, label in labels.items())
    return supplied + " " + facts + "."


def _photo_bytes(photo):
    if photo is None:
        return None
    try:
        raw = base64.b64decode(photo.base64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Author photo must contain valid base64 image bytes") from None
    if not 1 <= len(raw) <= 512 * 1024:
        raise ValueError("Author photo must contain at most 512 KiB")
    from docx.image.image import Image
    try:
        image = Image.from_blob(raw)
        valid = image.content_type == photo.media_type and image.px_width > 0 and image.px_height > 0
    except Exception:
        valid = False
    extension = photo.filename.rsplit(".", 1)[-1]
    if not valid or (photo.media_type == "image/png") != (extension == "png"):
        raise ValueError("Author photo must be a valid PNG or JPEG matching its filename and media type")
    return raw


def _word_visual_counts(content):
    """Count actual manuscript tables/drawings; the separate portrait is excluded."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as document:
            info = document.getinfo("word/document.xml")
            if info.file_size > 16 * 1024 * 1024:
                raise ValueError("Submission Word XML exceeds the supported size")
            tree = ET.fromstring(document.read(info))
    except (KeyError, ValueError, zipfile.BadZipFile, ET.ParseError):
        raise ValueError("Submission file QA requires the actual complete native Word document") from None
    names = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    return len(tree.findall(".//w:tbl", names)), len(tree.findall(".//w:drawing", names)) + len(tree.findall(".//w:pict", names))


class PortfolioSubmissionMixin:
    """No scientific admission, model call, author consent inference or HTTP action."""

    def _submission_preparations(self, ws, record):
        from .. import workflow as engine
        keys = sorted((key for key in record.artifacts if re.fullmatch(PREFIX + r"preparation-[1-9]\d*", key)),
            key=lambda key: int(key.rsplit("-", 1)[-1]))
        preparations = []
        for key in keys:
            value = engine._read(ws, record, key)
            if (value.get("origin") != "explicit_human_submission_preparation" or value.get("model_calls") != 0 or
                    value.get("externally_verified") is not False or value.get("scientific_approval_changed") is not False):
                raise engine.WorkflowError("ARTIFACT_CHANGED", "Submission preparation must retain its original human provenance")
            for artifact_id, sha in value["bindings"]["artifacts"].items():
                if artifact_id not in record.artifacts or record.artifacts[artifact_id].sha256 != sha:
                    raise engine.WorkflowError("ARTIFACT_CHANGED", "Submission preparation differs from an exact frozen input")
                engine._artifact(ws, record, artifact_id)
            for output in value["outputs"].values():
                if output["artifact_id"] not in record.artifacts or record.artifacts[output["artifact_id"]].sha256 != output["sha256"]:
                    raise engine.WorkflowError("ARTIFACT_CHANGED", "Submission preparation differs from a retained generated file")
                engine._artifact(ws, record, output["artifact_id"])
            original = engine._artifact(ws, record, value["outputs"]["source"]["artifact_id"]).read_bytes()
            author_export = engine._read(ws, record, value["bindings"]["author_export_artifact_id"])
            if original != engine._artifact(ws, record, author_export["input_artifact_id"]).read_bytes():
                raise engine.WorkflowError("ARTIFACT_CHANGED", "Submission source copy differs from its exact reviewed author Markdown")
            generated, transformation = _submission_manuscript(original, value["author_biography"], value["keywords"], **value.get("supplements", {}))
            if (generated != engine._artifact(ws, record, value["outputs"]["md"]["artifact_id"]).read_bytes() or
                    transformation != value["transformation"]):
                raise engine.WorkflowError("ARTIFACT_CHANGED", "Submission supplement changed an original manuscript byte or its literal biography/keywords")
            preparations.append({**value, "artifact_id": key, "sha256": record.artifacts[key].sha256})
        return preparations

    def _submission_confirmations(self, ws, record, preparations):
        from .. import workflow as engine
        by_sha = {item["sha256"]: item for item in preparations}
        confirmed = {}
        for key in record.artifacts:
            if not re.fullmatch(PREFIX + r"confirmation-[1-9]\d*", key):
                continue
            value = engine._read(ws, record, key)
            preparation = by_sha.get(value.get("preparation_sha256"))
            if (not preparation or value.get("origin") != "explicit_human_submission_file_confirmation" or
                    value.get("venue_id") != preparation["venue_id"] or value.get("model_calls") != 0 or
                    value.get("externally_verified") is not False or set(value["outputs"]) != {"package", "manifest", "metadata", "cover_letter"}):
                raise engine.WorkflowError("ARTIFACT_CHANGED", "Submission confirmation differs from its exact human-reviewed generated files")
            parsed = PortfolioSubmissionConfirmation.model_validate({name: value[name] for name in PortfolioSubmissionConfirmation.model_fields})
            if any(parsed.model_dump()["expected_" + kind + "_sha256"] != preparation["outputs"][kind]["sha256"] for kind in ("docx", "pdf")):
                raise engine.WorkflowError("ARTIFACT_CHANGED", "Submission file confirmation differs from its generated Word/PDF SHA")
            for output in value["outputs"].values():
                if output["artifact_id"] not in record.artifacts or record.artifacts[output["artifact_id"]].sha256 != output["sha256"]:
                    raise engine.WorkflowError("ARTIFACT_CHANGED", "Confirmed submission package differs from its immutable output")
                engine._artifact(ws, record, output["artifact_id"])
            if value["preparation_sha256"] in confirmed:
                raise engine.WorkflowError("ARTIFACT_CHANGED", "One submission preparation retains exactly one file confirmation")
            confirmed[value["preparation_sha256"]] = {**value, "artifact_id": key, "sha256": record.artifacts[key].sha256}
        return confirmed

    def _submission_events(self, ws, record, preparations):
        from .. import workflow as engine
        by_sha = {item["sha256"]: item for item in preparations}
        keys = sorted((key for key in record.artifacts if re.fullmatch(PREFIX + r"event-[1-9]\d*", key)),
            key=lambda key: int(key.rsplit("-", 1)[-1]))
        events = []
        for key in keys:
            event = engine._read(ws, record, key)
            preparation = by_sha.get(event.get("preparation_sha256"))
            if (event.get("origin") != "explicit_human_submission_record" or event.get("externally_verified") is not False or not preparation or
                    event.get("venue_id") != preparation["venue_id"] or event.get("portal_url") != PORTALS.get(event.get("venue_id"))):
                raise engine.WorkflowError("ARTIFACT_CHANGED", "Submission event differs from its retained preparation and official portal")
            PortfolioSubmissionRecord.model_validate({name: event[name] for name in PortfolioSubmissionRecord.model_fields})
            events.append({**event, "artifact_id": key, "sha256": record.artifacts[key].sha256})
        return events

    def _submission_candidate(self, ws, record, venue_id):
        from .. import workflow as engine
        catalog = publication_catalog()
        venue = next(item for item in catalog["venues"] if item["id"] == venue_id)
        quality = self._improvement_state(ws, record)
        if quality is not None:
            number, keys, draft, review, author, exported, missing = self._quality_submission_inputs(ws, record, venue_id, quality)
        else:
            number, keys, draft, review = self._portfolio_latest(ws, record, venue_id)
            missing = []
            assessed = RepositoryReview.model_validate(review["value"]) if review else None
            if not draft or not assessed or not assessed.scientific_ready or not assessed.content_assessment or not assessed.content_assessment.content_ready:
                missing.append("최신 원고가 독립 심사에서 내용과 근거 검토를 통과해야 합니다.")
            analysis_key = self._portfolio_analysis_key(record)
            if not analysis_key or not draft or draft["bindings"]["portfolio_analysis_sha256"] != record.artifacts[analysis_key].sha256:
                missing.append("최신 분석을 반영한 원고를 작성하고 다시 심사해야 합니다.")
            if self._portfolio_revision_feedback(ws, record, venue_id, latest=(number, keys, draft, review)):
                missing.append("요청한 원고 보완을 마치고 다시 심사해야 합니다.")
            author = self._repository_author_metadata(ws, record)
            author_state = self._portfolio_author_state(ws, record, venue_id, number, keys, draft, review)
            exported = author_state["author_export"] if author_state["author_export_status"] == "completed" else None
            if not author or not exported:
                missing.append("저자 정보를 저장하고 최신 Word·PDF의 저자 정보를 반영해야 합니다.")
        expected = None
        bindings = None
        if draft and review and author and exported:
            artifact_ids = [keys["draft"], keys["review"], keys["markdown"], author["artifact_id"], exported["artifact_id"],
                exported["input_artifact_id"], *(item["artifact_id"] for item in exported["outputs"].values())]
            artifacts = {key: record.artifacts[key].sha256 for key in artifact_ids}
            for key in artifacts:
                engine._artifact(ws, record, key)
            expected = {"expected_draft_sha256": artifacts[keys["draft"]], "expected_review_sha256": artifacts[keys["review"]],
                "expected_author_sha256": author["sha256"], "expected_pdf_sha256": exported["outputs"]["pdf"]["sha256"],
                "expected_docx_sha256": exported["outputs"]["docx"]["sha256"]}
            bindings = {"study": engine._submission_bindings(ws, record), "draft_attempt": number,
                "artifacts": artifacts, "author_export_artifact_id": exported["artifact_id"],
                "catalog_sha256": hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest(), "expected": expected}
        return {"venue_id": venue_id, "name": venue["name"], "portal_url": PORTALS[venue_id],
            "guidelines_url": venue["guidelines_url"], "requirements_checked_at": catalog["checked_at"],
            "limits": venue["verified_limits"], "expected_binding": expected, "missing": missing,
            "prepare_available": not missing, "bindings": bindings, "draft": draft, "exported": exported, "author": author}

    def _quality_submission_inputs(self, ws, record, venue_id, state):
        """Use the exact assessed best version, never an earlier permissive PASS."""
        from .. import workflow as engine
        from .manuscript_improvement import IndependentAssessment, best_assessment

        missing = []
        versions = state["versions"].get(venue_id, [])
        best = best_assessment(state["reviews"].get(venue_id, []))
        selected = next((item for item in versions if best and item["markdown_sha256"] == best["manuscript_sha256"]), None)
        keys, draft, review, exported, number = {}, None, None, None, 0
        author = self._repository_author_metadata(ws, record)
        if not state["finished"]:
            missing.append("항목별 품질 보완과 독립 평가를 마친 뒤 최선 원고를 확정해야 합니다.")
        if not best or not selected:
            missing.append("보존된 최선 원고에 결속된 독립 품질 평가가 필요합니다.")
        else:
            assessed = IndependentAssessment.model_validate(best)
            if assessed.venue_id != venue_id or assessed.manuscript_sha256 != selected["markdown_sha256"]:
                raise engine.WorkflowError("ARTIFACT_CHANGED", "The selected quality assessment belongs to a different venue or manuscript")
            if assessed.essential_errors or assessed.recommendation != "consider_submission":
                missing.append("현재 독립 품질 평가가 투고 검토를 권하지 않습니다. 평가 이유와 필요한 보완을 확인하세요.")
            review_key = state.get("review_artifact_ids", {}).get(venue_id, {}).get(selected["markdown_sha256"])
            if not review_key or review_key not in record.artifacts:
                missing.append("선택한 원고의 정확한 독립 평가 원문이 보존되어야 합니다.")
            else:
                review = engine._read(ws, record, review_key)
                if review.get("value") != best:
                    raise engine.WorkflowError("ARTIFACT_CHANGED", "The selected submission quality assessment differs from its frozen review")
                keys = {"draft": selected["draft_artifact_id"], "markdown": selected["markdown_artifact_id"], "review": review_key}
                if any(key not in record.artifacts or record.artifacts[key].sha256 != selected[field]
                       for key, field in ((keys["draft"], "draft_sha256"), (keys["markdown"], "markdown_sha256"))):
                    raise engine.WorkflowError("ARTIFACT_CHANGED", "The selected quality manuscript differs from its exact frozen version")
                draft = engine._read(ws, record, keys["draft"])
                baseline_attempt = int(versions[0]["draft_artifact_id"].rsplit("-", 1)[-1])
                number = baseline_attempt + versions.index(selected)
        analysis_key = self._portfolio_analysis_key(record)
        if not analysis_key or record.artifacts[analysis_key].sha256 != state["analysis_sha256"]:
            missing.append("품질 평가가 현재 보존된 공통 분석과 일치해야 합니다.")
        export = state["exports"].get(venue_id)
        if (not export or not selected or export.get("selected_version") != selected or export.get("errors") or
                set(export.get("outputs", {})) != {"markdown", "docx", "pdf"} or
                export.get("review_artifact_id") != keys.get("review") or
                export.get("quality_status") != "assessed_manuscript" or
                export.get("recommendation") != (best or {}).get("recommendation") or
                not export.get("artifact_id") or export["artifact_id"] not in record.artifacts):
            missing.append("선택한 최선 원고의 공식 템플릿 Word·PDF와 정확한 출력 기록이 필요합니다.")
        elif (not author or export.get("author_artifact_id") != author["artifact_id"] or
                export.get("author_sha256") != author["sha256"]):
            missing.append("저자 정보를 저장하고 최선 원고의 공식 템플릿 출력에 반영해야 합니다.")
        else:
            saved = engine._read(ws, record, export["artifact_id"])
            if (record.artifacts[export["artifact_id"]].sha256 != export.get("sha256") or
                    saved != {key: value for key, value in export.items() if key not in {"artifact_id", "sha256"}}):
                raise engine.WorkflowError("ARTIFACT_CHANGED", "The selected quality export differs from its frozen receipt")
            if (export.get("input_artifact_id") not in record.artifacts or
                    record.artifacts[export["input_artifact_id"]].sha256 != export.get("input_sha256") or
                    export["outputs"]["markdown"]["artifact_id"] != export["input_artifact_id"] or
                    export["outputs"]["markdown"]["sha256"] != export["input_sha256"]):
                raise engine.WorkflowError("ARTIFACT_CHANGED", "The quality export requires its exact author-bound Markdown input")
            for output in export["outputs"].values():
                if output["artifact_id"] not in record.artifacts or record.artifacts[output["artifact_id"]].sha256 != output["sha256"]:
                    raise engine.WorkflowError("ARTIFACT_CHANGED", "The official quality manuscript output differs from its frozen bytes")
                engine._artifact(ws, record, output["artifact_id"])
            editorial = export.get("editorial_preparation")
            if editorial and editorial.get("sha256") != selected["markdown_sha256"]:
                missing.append("공식 출력에 반영한 본문·참고문헌 형식 보완본의 정확한 독립 평가가 필요합니다.")
            exported = export
        return number, keys, draft, review, author, exported, missing

    def _portfolio_submission_public(self, ws, record):
        preparations = self._submission_preparations(ws, record)
        confirmations = self._submission_confirmations(ws, record, preparations)
        events = self._submission_events(ws, record, preparations)
        candidates = [self._submission_candidate(ws, record, target["venue_id"])
            for target in self._portfolio_start(ws, record)["targets"]]
        latest = preparations[-1] if preparations else None
        confirmation = confirmations.get(latest["sha256"]) if latest else None
        event = next((item for item in reversed(events) if latest and item["preparation_sha256"] == latest["sha256"]), None)
        status = event["status"] if event else "prepared" if confirmation else (
            "generation_failed" if latest and latest["errors"] else "awaiting_file_check" if latest else "not_started")
        current = False
        if latest:
            candidate = next(item for item in candidates if item["venue_id"] == latest["venue_id"])
            current = not candidate["missing"] and latest["bindings"] == candidate["bindings"]
            if status in {"prepared", "awaiting_file_check", "generation_failed"} and not current:
                status = "stale"
        active = latest and status in {"prepared", "stale", "submitted", "awaiting_file_check", "generation_failed"}
        for candidate in candidates:
            if active and (status == "submitted" or candidate["venue_id"] != latest["venue_id"]):
                candidate["missing"].append("다른 학술지를 선택하려면 현재 준비를 철회하거나 실제 투고의 철회·거절을 기록해야 합니다.")
            candidate["prepare_available"] = not candidate["missing"]
        visible = None
        if latest:
            visible = {key: value for key, value in latest.items() if key not in {"bindings", "outputs", "model_calls"}}
            visible.update(current=current, generation_status="failed" if latest["errors"] else "completed")
            for name in ("source", "md", "docx", "pdf"):
                output = latest["outputs"].get(name)
                visible[name + "_artifact_id"] = output["artifact_id"] if output else None
                if name in {"docx", "pdf"}:
                    visible[name + "_sha256"] = output["sha256"] if output else None
            for name in ("package", "manifest", "metadata", "cover_letter"):
                output = confirmation["outputs"][name] if confirmation else None
                visible[name + "_artifact_id"] = output["artifact_id"] if output else None
                if name == "package":
                    visible["package_sha256"] = output["sha256"] if output else None
            visible["confirmation"] = {key: value for key, value in confirmation.items() if key != "outputs"} if confirmation else None
        return {"status": status, "selected_venue_id": latest["venue_id"] if latest else None,
            "preparation": visible, "portal_record": event, "history": events,
            "candidates": [{key: value for key, value in item.items() if key not in {"bindings", "draft", "exported", "author"}} for item in candidates]}

    def prepare_portfolio_submission(self, research_id, venue_id, value):
        """Generate supplemental submission files; no approval or package yet."""
        from .. import workflow as engine
        from ..conversion import convert
        from ..journal_compliance import compliance_report
        submitted = PortfolioSubmissionPreparation.model_validate(value)
        photo = _photo_bytes(submitted.photo)
        with self._operation(research_id) as (ws, record):
            self._require(ws, record, {"repository_manuscript"}, allow_cancelled=True)
            if venue_id not in {target["venue_id"] for target in self._portfolio_start(ws, record)["targets"]}:
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_VENUE", "Submission must select one eligible IEEE portfolio venue")
            state = self._portfolio_submission_public(ws, record)
            public = next(item for item in state["candidates"] if item["venue_id"] == venue_id)
            if not public["prepare_available"]:
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_BLOCKED", "; ".join(public["missing"]))
            candidate = self._submission_candidate(ws, record, venue_id)
            expected = {field: getattr(submitted, field) for field in candidate["expected_binding"]}
            if expected != candidate["expected_binding"]:
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_STALE", "Supplement preparation differs from the exact current manuscript, review, author or Word/PDF SHA")
            if venue_id == "ieee-software" and photo is None:
                raise ValueError("IEEE Software preparation requires an explicit author photograph")
            number = len(self._submission_preparations(ws, record)) + 1
            root = ws.path(f"{ROOT}/preparation-{number}")
            if root.exists():
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_INTERRUPTED", "Preserve an interrupted submission preparation instead of replacing unknown bytes")
            original = engine._artifact(ws, record, candidate["exported"]["input_artifact_id"]).read_bytes()
            biography = _submission_biography(submitted.author_biography, submitted.biography_details.model_dump(mode="json"))
            supplements = {"funding_statement": submitted.funding_statement, "conflicts_statement": submitted.conflicts_statement}
            markdown, transformation = _submission_manuscript(original, biography, submitted.keywords, **supplements)
            root.mkdir(parents=True)
            outputs = {}

            def retain(kind, filename, content):
                path = root / filename
                path.write_bytes(content)
                key = f"{PREFIX}{kind}-{number}"
                engine._freeze(ws, record, key, path)
                outputs[kind] = {"artifact_id": key, "sha256": record.artifacts[key].sha256}
                return path

            retain("source", "original-reviewed-author.md", original)
            source = retain("md", "submission.md", markdown)
            photo_info = None
            if photo is not None:
                retain("photo", "author-photo." + submitted.photo.filename.rsplit(".", 1)[-1], photo)
                photo_info = {"filename": submitted.photo.filename, "media_type": submitted.photo.media_type,
                    "sha256": hashlib.sha256(photo).hexdigest(), "size": len(photo)}
            errors = []
            conversion_receipts = {}
            for extension in ("docx", "pdf"):
                path = root / ("submission." + extension)
                conversion = None
                error = None
                try:
                    conversion = convert(source, path, venue_id=venue_id)
                    conversion_receipts[extension] = conversion
                    if (conversion["input_sha256"] != outputs["md"]["sha256"] or
                            conversion["output_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest()):
                        raise ValueError("Submission conversion must preserve its exact input and output SHA")
                except Exception as failure:
                    error = engine._diagnostic(failure)
                    errors.append(extension + ": " + error)
                engine._artifact(ws, record, outputs["md"]["artifact_id"])
                if path.is_file():
                    key = f"{PREFIX}{extension}-{number}"
                    engine._freeze(ws, record, key, path)
                    outputs[extension] = {"artifact_id": key, "sha256": record.artifacts[key].sha256}
                self._portfolio_append(ws, record, f"{PREFIX}{extension}-conversion-{number}", root / (extension + "-conversion.json"), {
                    "input_sha256": outputs["md"]["sha256"], "output_sha256": outputs.get(extension, {}).get("sha256"),
                    "status": "failed" if error else "completed", "conversion": conversion, "error": error,
                    "model_calls": 0, "scope": "Supplement-only native conversion; scientific originals remain immutable"})
                key = f"{PREFIX}{extension}-conversion-{number}"
                outputs[extension + "-conversion"] = {"artifact_id": key, "sha256": record.artifacts[key].sha256}
            author = {**candidate["author"]["value"], "biography": biography,
                      "biography_details": submitted.biography_details.model_dump(mode="json")}
            compliance = compliance_report(source, root / "submission.docx" if "docx" in outputs else None, venue_id,
                pdf=root / "submission.pdf" if "pdf" in outputs else None, qa_root=root / "page-qa",
                author_metadata=author, conversion_receipts=conversion_receipts)
            retain("compliance", "journal-compliance.json", _json_bytes(compliance))
            for page in (compliance.get("page_qa") or {}).get("pages", []):
                path = Path(page["image_path"])
                if not path.resolve().is_relative_to((root / "page-qa").resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != page["image_sha256"]:
                    raise engine.WorkflowError("ARTIFACT_CHANGED", "Submission page QA must bind the exact local rendered image")
                key = f"{PREFIX}page-{page['number']}-{number}"
                engine._freeze(ws, record, key, path)
                outputs[f"page-{page['number']}"] = {"artifact_id": key, "sha256": record.artifacts[key].sha256}
            if not compliance["content_format_passed"]:
                errors.extend("투고 규정: " + reason for reason in compliance["blockers"])
                if not compliance["blockers"]:
                    errors.append("투고 규정: 실제 Word·PDF 검사를 모두 완료해야 합니다.")
            for generated in sorted(root.iterdir()):
                if generated.suffix in {".typ", ".lua"} or generated.name.endswith("-pandoc-metadata.json"):
                    kind = "generated-" + generated.name.replace(".", "-")
                    key = f"{PREFIX}{kind}-{number}"
                    engine._freeze(ws, record, key, generated)
                    outputs[kind] = {"artifact_id": key, "sha256": record.artifacts[key].sha256}
            self._portfolio_append(ws, record, f"{PREFIX}preparation-{number}", root / "preparation.json", {
                "at": now(), "venue_id": venue_id, "bindings": candidate["bindings"], "outputs": outputs,
                "title": candidate["draft"]["value"]["title"], "author": candidate["author"]["value"],
                "author_biography": biography, "provided_author_biography": submitted.author_biography,
                "keywords": submitted.keywords, "photo": photo_info, "supplements": supplements,
                "biography_details": submitted.biography_details.model_dump(mode="json"), "compliance": compliance,
                "funding_statement": submitted.funding_statement, "conflicts_statement": submitted.conflicts_statement,
                "cover_letter_note": submitted.cover_letter_note, "transformation": transformation, "errors": errors,
                "origin": "explicit_human_submission_preparation", "externally_verified": False,
                "scientific_approval_changed": False, "model_calls": 0})
            self._save(ws, record)
            return self._public(ws, record)

    def confirm_portfolio_submission(self, research_id, value):
        """Package only the exact generated files after explicit human file QA."""
        from .. import workflow as engine
        submitted = PortfolioSubmissionConfirmation.model_validate(value)
        with self._operation(research_id) as (ws, record):
            self._require(ws, record, {"repository_manuscript"}, allow_cancelled=True)
            state = self._portfolio_submission_public(ws, record)
            visible = state["preparation"]
            if not visible or visible["sha256"] != submitted.preparation_sha256:
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_STALE", "File confirmation requires the exact latest preparation SHA")
            if state["status"] != "awaiting_file_check" or not visible["current"] or visible["generation_status"] != "completed":
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_STATE", "File confirmation requires current successfully generated submission Word/PDF, once")
            preparation = self._submission_preparations(ws, record)[-1]
            if any(getattr(submitted, "expected_" + kind + "_sha256") != preparation["outputs"][kind]["sha256"] for kind in ("docx", "pdf")):
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_STALE", "Human file review differs from the exact new submission Word/PDF SHA")
            compliance = engine._read(ws, record, preparation["outputs"]["compliance"]["artifact_id"])
            expected_format = {name + "_sha256": preparation["outputs"][key]["sha256"] for name, key in (("markdown", "md"), ("docx", "docx"), ("pdf", "pdf"))}
            if compliance != preparation["compliance"] or not compliance["content_format_passed"] or any(
                    compliance["binding"].get(key) != value for key, value in expected_format.items()):
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_FORMAT", "Current submission files must pass their exact bound native journal compliance report")
            actual = compliance["metrics"]["native_word"]
            if (submitted.qa.word_count != actual["whole_words"] or submitted.qa.docx_pages != actual["pages"] or
                    submitted.qa.pdf_pages != compliance["page_qa"]["page_count"]):
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_QA", "Human Word/PDF counts must match the exact native measurements and rendered page count")
            pending = re.compile(r"(?i)^(?:tbd|pending|to be confirmed|author confirmation pending|미정|확인 대기|저자 확인 대기)$")
            if any(pending.fullmatch(preparation[name].strip()) for name in ("funding_statement", "conflicts_statement")):
                raise ValueError("Confirm explicit funding and conflict statements before creating a final submission package")
            venue_id = preparation["venue_id"]
            candidate = self._submission_candidate(ws, record, venue_id)
            word = engine._artifact(ws, record, preparation["outputs"]["docx"]["artifact_id"]).read_bytes()
            tables, figures = _word_visual_counts(word)
            generated_markdown = engine._artifact(ws, record, preparation["outputs"]["md"]["artifact_id"]).read_bytes().decode("utf-8")
            markdown_figures = len(re.findall(r"(?<!\\)!\[[^\]]*\]\([^)]+\)", generated_markdown))
            if markdown_figures > figures:
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_VISUALS", "The native Word document is missing a figure retained in the submission Markdown")
            if (submitted.qa.table_count, submitted.qa.figure_count) != (tables, figures):
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_VISUALS", "Human visual counts must match the actual new Word document tables and figures; the separate author portrait is excluded")
            metrics = {"biography_words": len(preparation["author_biography"].split()),
                "visual_words": (submitted.qa.table_count + submitted.qa.figure_count) * candidate["limits"]["visual_word_cost"],
                "abstract_words": actual["abstract_words"], "reference_count": actual["reference_count"],
                "actual_table_count": tables, "actual_figure_count": figures, "markdown_figure_count": markdown_figures,
                "count_scope": "human_reported_complete_new_Word_article_including_biography_keywords_references_and_table_text_plus_visual_cost"}
            metrics["effective_words"] = compliance["metrics"]["effective_words"]
            metrics["count_scope"] = compliance["metrics"]["word_count_formula"]
            limits = candidate["limits"]
            if (metrics["effective_words"] > limits["max_words"] or metrics["effective_words"] < limits.get("min_words", 0) or
                    metrics["abstract_words"] > limits["max_abstract_words"] or metrics["reference_count"] > limits["max_references"]):
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_LENGTH", "Human-reported complete new Word total plus visual cost, actual abstract or references violates current verified numeric requirements")
            if not metrics["reference_count"]:
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_REFERENCES", "Submission requires its actual retained canonical bibliography")
            confirmed_compliance = json.loads(json.dumps(compliance))
            human_checks = {"author_identity": submitted.declarations.identity_confirmed,
                "author_declarations": all(submitted.declarations.model_dump().values()),
                "author_photo": bool(preparation["photo"]) and submitted.declarations.identity_confirmed,
                "visual_review": submitted.declarations.all_pages_reviewed}
            for item in confirmed_compliance["items"]:
                if item["stage"] == "submission" and item["id"] in human_checks:
                    item["status"] = "passed" if human_checks[item["id"]] else "pending"
                    item["confirmation_origin"] = "explicit_human_submission_file_confirmation"
            confirmed_compliance["pending"] = [item["reason"] for item in confirmed_compliance["items"] if item["status"] == "pending"]
            confirmed_compliance["submission_ready"] = all(item["status"] == "passed" for item in confirmed_compliance["items"])
            confirmed_compliance["human_confirmation"] = submitted.model_dump(mode="json")
            confirmed_compliance["scope"] = "Native format checks plus explicit author reports bound to these exact submission files; no external verification or journal acceptance."
            if not confirmed_compliance["submission_ready"]:
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_FORMAT", "Complete every remaining journal preparation item before creating the final submission package")
            number = int(preparation["artifact_id"].rsplit("-", 1)[-1])
            root = ws.path(f"{ROOT}/preparation-{number}/confirmed")
            if root.exists():
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_INTERRUPTED", "Preserve an interrupted confirmed submission package instead of replacing unknown bytes")
            root.mkdir()
            author = preparation["author"]
            metadata = {"schema_version": 1, "venue_id": venue_id, "journal": candidate["name"], "article_category": "Feature Article",
                "title": preparation["title"], "author": author, "author_biography": preparation["author_biography"],
                "biography_details": preparation["biography_details"], "keywords": preparation["keywords"],
                "photo": preparation["photo"], "funding_statement": preparation["funding_statement"], "conflicts_statement": preparation["conflicts_statement"],
                "portal_url": candidate["portal_url"], "guidelines_url": candidate["guidelines_url"],
                "requirements_checked_at": candidate["requirements_checked_at"], "limits": limits, "metrics": metrics,
                "native_compliance": confirmed_compliance, "original_native_compliance_sha256": preparation["outputs"]["compliance"]["sha256"],
                "human_confirmation": submitted.model_dump(mode="json"), "origin": "explicit_human_submission_file_confirmation", "externally_verified": False,
                "scope": "New Word/PDF include plain author biography and keywords; original scientific manuscript and review bytes remain unchanged. Human confirmations are reports, not externally verified facts. Actual portal instructions govern uploads."}
            declaration_text = ("Human-confirmed submission declarations\n\n"
                "The named author explicitly confirmed identity/metadata accuracy, all authors' approval, originality and no concurrent submission, source/third-party rights, review of AI assistance disclosure, current official guidelines, and every new Word/PDF page. These are human reports, not external verification.\n\n"
                f"Funding: {preparation['funding_statement']}\n\nConflicts of interest: {preparation['conflicts_statement']}\n")
            cover = (f"Dear Editors of {candidate['name']},\n\nPlease consider the Feature Article \"{preparation['title']}\".\n\n"
                f"Corresponding author: {author['display_name']}\nAffiliation: {author['affiliation']}\nContact: {author['email']}\n"
                + (f"ORCID: {author['orcid']}\n" if author.get("orcid") else "")
                + "\nThe manuscript concerns the retained repository study. Its scientific claims and limitations remain those of the exact independently reviewed manuscript.\n\n"
                + declaration_text + (f"\nAuthor's note: {preparation['cover_letter_note']}\n" if preparation["cover_letter_note"] else "")
                + f"\nSincerely,\n{author['display_name']}\n")
            files = {"author-biography.txt": (preparation["author_biography"] + "\n").encode(),
                "keywords.txt": ("\n".join(preparation["keywords"]) + "\n").encode(), "declarations.txt": declaration_text.encode(),
                "metadata.json": _json_bytes(metadata), "cover-letter.txt": cover.encode(),
                "journal-compliance.json": _json_bytes(confirmed_compliance),
                "submission-guide.txt": (f"Selected journal: {candidate['name']}\nOfficial portal: {candidate['portal_url']}\nGuidelines: {candidate['guidelines_url']}\n\n"
                    "Review the generated Word/PDF, author biography/photo/keywords and declarations against current portal instructions. Log in yourself, review all forms and files, and submit only after your final approval. Opening a portal or exporting this ZIP does not submit anything. Record submitted status only after receiving a real manuscript ID. Alternative venue manuscripts from this same study must not be submitted concurrently. Human declarations are retained reports, not external verification.\n").encode()}
            for kind in ("md", "docx", "pdf"):
                files["paper." + kind] = engine._artifact(ws, record, preparation["outputs"][kind]["artifact_id"]).read_bytes()
            if preparation["photo"]:
                files["author-photo." + preparation["photo"]["filename"].rsplit(".", 1)[-1]] = engine._artifact(ws, record, preparation["outputs"]["photo"]["artifact_id"]).read_bytes()
            manifest = {"schema_version": 1, "venue_id": venue_id, "preparation_sha256": preparation["sha256"],
                "bindings": preparation["bindings"], "generated_outputs": preparation["outputs"],
                "files": [{"name": name, "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)} for name, raw in sorted(files.items())],
                "scope": "Exact retained supplement-bearing native manuscripts plus explicit human submission confirmations; no portal submission or model approval."}
            files["manifest.json"] = _json_bytes(manifest)
            outputs = {}
            for kind, name in (("manifest", "manifest.json"), ("metadata", "metadata.json"), ("cover_letter", "cover-letter.txt")):
                path = root / name
                path.write_bytes(files[name])
                key = f"{PREFIX}{kind.replace('_', '-')}-{number}"
                engine._freeze(ws, record, key, path)
                outputs[kind] = {"artifact_id": key, "sha256": record.artifacts[key].sha256}
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
                for name, raw in sorted(files.items()):
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    bundle.writestr(info, raw)
            path = root / "submission-package.zip"
            path.write_bytes(archive.getvalue())
            key = f"{PREFIX}package-{number}"
            engine._freeze(ws, record, key, path)
            outputs["package"] = {"artifact_id": key, "sha256": record.artifacts[key].sha256}
            self._portfolio_append(ws, record, f"{PREFIX}confirmation-{number}", root / "confirmation.json", {
                **submitted.model_dump(mode="json"), "at": now(), "venue_id": venue_id, "outputs": outputs, "metrics": metrics,
                "origin": "explicit_human_submission_file_confirmation", "externally_verified": False, "model_calls": 0})
            self._save(ws, record)
            return self._public(ws, record)


    def record_portfolio_submission(self, research_id, value):
        from .. import workflow as engine
        submitted = PortfolioSubmissionRecord.model_validate(value)
        with self._operation(research_id) as (ws, record):
            self._require(ws, record, {"repository_manuscript"}, allow_cancelled=True)
            self._portfolio_start(ws, record)
            state = self._portfolio_submission_public(ws, record)
            preparation = state["preparation"]
            if not preparation or submitted.preparation_sha256 != preparation["sha256"]:
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_STALE", "Portal tracking requires the exact latest immutable preparation SHA")
            current = state["status"]
            if submitted.status == "submitted" and (current != "prepared" or not preparation["current"]):
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_STATE", "Actual submission can only be recorded for a current prepared package, once")
            if submitted.status == "rejected" and current != "submitted":
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_STATE", "Rejection requires an existing human-recorded actual submission")
            if submitted.status == "withdrawn" and current not in {"prepared", "stale", "submitted", "awaiting_file_check", "generation_failed"}:
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_STATE", "Withdrawal requires an active prepared or submitted venue")
            previous = state["portal_record"]
            if current == "submitted" and submitted.manuscript_id != previous["manuscript_id"]:
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_ID", "Withdrawal or rejection must preserve the actual portal manuscript ID")
            if previous and datetime.fromisoformat(submitted.occurred_at.replace("Z", "+00:00")) < datetime.fromisoformat(previous["occurred_at"].replace("Z", "+00:00")):
                raise engine.WorkflowError("PORTFOLIO_SUBMISSION_TIME", "Portal events must follow the recorded submission chronology")
            number = len(state["history"]) + 1
            self._portfolio_append(ws, record, f"{PREFIX}event-{number}", ws.path(f"{ROOT}/event-{number}.json"), {
                **submitted.model_dump(mode="json"), "at": now(), "venue_id": preparation["venue_id"],
                "portal_url": PORTALS[preparation["venue_id"]], "origin": "explicit_human_submission_record", "externally_verified": False,
                "scope": "Human-recorded portal action, not externally verified" if current == "submitted" or submitted.status == "submitted" else "Human release of prepared venue selection; no portal submission is claimed"})
            self._save(ws, record)
            return self._public(ws, record)

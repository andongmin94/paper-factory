"""Synthetic receipt validation only; no source selection, model or research execution."""

import hashlib
import json

import pytest
from pydantic import ValidationError

from paper_factory.workflow_models import ModelEvidenceReceipt


def source_selection_receipt(outcome="completed"):
    prompt = "Select exact names from the supplied frozen source inventory. 원문을 확인하세요."
    text = json.dumps({"source_files": ["src/layout.js"],
                       "reason": "Inspect this synthetic inventory entry before proposing any research."},
                      ensure_ascii=False)
    value = {"id": "12345678-1234-1234-1234-123456789abc", "phase": "source-selection",
             "at": "2026-10-08T00:00:00Z", "model": "gpt-6-astra", "profileId": "synthetic-owned-profile",
             "prompt": prompt, "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(), "outcome": outcome}
    if outcome == "completed":
        value.update(text=text, textSha256=hashlib.sha256(text.encode()).hexdigest())
    return value


@pytest.mark.parametrize("outcome", ["started", "completed", "failed", "interrupted"])
def test_source_selection_phase_retains_exact_hash_bound_receipt(outcome):
    value = source_selection_receipt(outcome)
    retained = ModelEvidenceReceipt.model_validate_json(json.dumps(value, ensure_ascii=False))
    assert retained.model_dump(mode="json", exclude_none=True) == value


@pytest.mark.parametrize("phase", ["source_selection", "SOURCE-SELECTION", "selection", "unknown-phase", ""])
def test_source_selection_receipt_rejects_unknown_phase(phase):
    value = source_selection_receipt()
    value["phase"] = phase
    with pytest.raises(ValidationError) as invalid:
        ModelEvidenceReceipt.model_validate(value)
    assert any(error["loc"] == ("phase",) and error["type"] == "literal_error" for error in invalid.value.errors())


@pytest.mark.parametrize("defect", ["prompt", "text", "missing_text_hash", "missing_completed_text", "extra_field"])
def test_source_selection_phase_preserves_existing_strict_receipt_contract(defect):
    value = source_selection_receipt()
    if defect in {"prompt", "text"}:
        value[defect] += "changed original bytes"
    elif defect == "missing_text_hash":
        value.pop("textSha256")
    elif defect == "missing_completed_text":
        value.pop("text")
        value.pop("textSha256")
    else:
        value["source_files"] = ["unattested.js"]
    with pytest.raises(ValidationError):
        ModelEvidenceReceipt.model_validate(value)

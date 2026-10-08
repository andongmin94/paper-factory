"""Synthetic HTTP receipt boundaries; no SDK, network, account or SCI calls."""
import copy
import hashlib
import json
import os

import pytest

from paper_factory import ipc
from paper_factory.workflow import WorkflowError
from paper_factory.workflow_models import ModelEvidenceReceipt
from paper_factory.workspace import digest_file
from test_workflow import setup


def receipt(outcome="failed", diagnostics=None):
    prompt = "Synthetic original source-selection prompt. 원본 파일 목록만 선택하세요."
    value = {"id": "12345678-1234-1234-1234-123456789abc", "phase": "source-selection",
             "at": "2026-10-08T00:00:00Z", "model": "gpt-6-astra", "profileId": "synthetic-owned-profile",
             "prompt": prompt, "promptSha256": hashlib.sha256(prompt.encode()).hexdigest()}
    if outcome == "completed":
        value["text"] = '{"files":[{"name":"transform.js","reason":"Synthetic reading scope only, not scientific approval."}]}'
        value["textSha256"] = hashlib.sha256(value["text"].encode()).hexdigest()
    value["outcome"] = outcome
    if outcome in {"failed", "interrupted"}:
        value["code"] = "invalid_request"
    if diagnostics is not None:
        value["diagnostics"] = diagnostics
    return value


SAFE_DIAGNOSTICS = {"httpStatus": 400, "requestId": "req_synthetic.1:[2]-3",
                    "param": "input[0].content[1].type",
                    "responseShape": "{detail:[{type:string,loc:array,input:redacted,ctx:redacted}]}"}


@pytest.mark.parametrize("outcome", ["failed", "interrupted"])
def test_safe_http_diagnostics_are_hash_bound_append_only_and_cannot_authorize_science(setup, outcome):
    service, runner, identifier = setup
    before = service.status(identifier, include_materials=False)
    value = receipt(outcome, copy.deepcopy(SAFE_DIAGNOSTICS))
    envelope = ipc.request(json.dumps({"id": "synthetic-diagnostics", "method": "workflow.recordInference",
                                      "params": {"researchId": identifier, "receipt": value}}).encode())
    saved = service.record_inference(identifier, envelope["params"]["receipt"])
    path = service.artifact_path(identifier, saved["artifactId"])
    raw = path.read_bytes()
    assert json.loads(raw) == value and digest_file(path) == saved["sha256"]
    assert raw == (json.dumps(value, indent=2, ensure_ascii=False) + "\n").replace("\n", os.linesep).encode()
    journal = service.artifact_path(identifier, f'model-journal-{value["id"]}-{outcome}')
    assert json.loads(journal.read_bytes())["receipt_sha256"] == saved["sha256"]
    assert service.record_inference(identifier, value) == saved
    with pytest.raises(WorkflowError) as conflict:
        service.record_inference(identifier, {**value, "diagnostics": {**SAFE_DIAGNOSTICS, "httpStatus": 429}})
    assert conflict.value.code == "INFERENCE_EVIDENCE_CONFLICT" and path.read_bytes() == raw
    after = service.status(identifier, include_materials=False)
    assert (after["stage"], after["status"], after["proposal_attempt"], after["execution_attempt"]) == ("created", "ready", 0, 0)
    assert all(after["artifacts"][key] == artifact for key, artifact in before["artifacts"].items())
    assert len(after["artifacts"]) == len(before["artifacts"]) + 2 and runner.calls == 0


@pytest.mark.parametrize("outcome", ["started", "completed", "failed", "interrupted"])
def test_legacy_receipts_keep_exact_serialization_and_artifact_bytes_without_diagnostics(setup, outcome):
    service, runner, identifier = setup
    original = receipt(outcome)
    assert ModelEvidenceReceipt.model_validate(original).model_dump(mode="json", exclude_none=True) == original
    saved = service.record_inference(identifier, original)
    raw = service.artifact_path(identifier, saved["artifactId"]).read_bytes()
    assert raw == (json.dumps(original, indent=2, ensure_ascii=False) + "\n").replace("\n", os.linesep).encode()
    assert b'"diagnostics"' not in raw and hashlib.sha256(raw).hexdigest() == saved["sha256"]
    assert service.record_inference(identifier, original) == saved and runner.calls == 0


@pytest.mark.parametrize("diagnostics", [
    {"httpStatus": 100}, {"httpStatus": 599}, {"requestId": "_"}, {"requestId": "r" * 160},
    {"param": "model"}, {"param": "tools[99999].parameters"}, {"param": "reasoning.effort"},
    {"responseShape": "{error:{code:string,message:string,param:string,input:redacted,ctx:redacted,other:1}}"},
    {"responseShape": "{other:1000000}"}, {"responseShape": "{other:0}"},
    {"responseShape": "{}"}, {"responseShape": "[]"}, {"responseShape": "redacted"},
])
def test_safe_sdk_identifiers_field_paths_and_type_only_shapes_are_retained(diagnostics):
    value = receipt(diagnostics=diagnostics)
    assert ModelEvidenceReceipt.model_validate(value).model_dump(mode="json", exclude_none=True) == value


UNSAFE_DIAGNOSTICS = [
    {}, None, [], "synthetic-private-body", {"httpStatus": None}, {"httpStatus": 400, "param": None},
    {"httpStatus": True}, {"httpStatus": False}, {"httpStatus": 400.0}, {"httpStatus": "400"},
    {"httpStatus": 99}, {"httpStatus": 600}, {"httpStatus": float("nan")},
    {"requestId": ""}, {"requestId": ".synthetic"}, {"requestId": "-synthetic"},
    {"requestId": "r" * 161}, {"requestId": "req_synthetic\n"}, {"requestId": "https://private.example"},
    {"requestId": 123}, {"requestId": {"value": "synthetic-private-marker"}},
    {"param": ""}, {"param": "synthetic_private_marker"}, {"param": "input[0].access_token"},
    {"param": "input[123456].type"}, {"param": "input[١].type"}, {"param": "model\nsynthetic_private_marker"},
    {"param": "model?code=synthetic_private_marker"}, {"param": "input" + ".content" * 30},
    {"param": ["model"]}, {"responseShape": ""}, {"responseShape": {"error": "synthetic-private-marker"}},
    {"responseShape": "{error:{access_token:string}}"}, {"responseShape": "{error:{message:synthetic_private_marker}}"},
    {"responseShape": '{error:{message:"synthetic-private-marker"}}'},
    {"responseShape": "{detail:string}synthetic_private_marker"},
    {"responseShape": "{error:{response:{error:{code:string}}}}"}, {"responseShape": "{other:1000001}"},
    {"responseShape": "{other:01}"}, {"responseShape": "{other:1١}"}, {"responseShape": "{other:-1}"},
    {"responseShape": "{error:string,}"}, {"responseShape": "{detail:string}\n"},
    {"responseShape": "string" * 500}, {"responseShape": "{" + ",".join(["code:string"] * 14) + "}"},
    {"responseShape": "[string,string]"}, {"responseShape": "{message:123}"},
    {"httpStatus": 400, "message": "synthetic-private-marker"},
    {"httpStatus": 400, "body": {"access_token": "synthetic-private-marker"}},
    {"httpStatus": 400, "url": "https://private.example"},
    {"httpStatus": 400, "credentials": "synthetic-private-marker"},
]


@pytest.mark.parametrize("diagnostics", UNSAFE_DIAGNOSTICS)
def test_hostile_diagnostics_are_rejected_before_any_receipt_or_workflow_mutation(setup, diagnostics):
    service, runner, identifier = setup
    before = service.status(identifier, include_materials=False)
    value = receipt()
    value["diagnostics"] = diagnostics
    with pytest.raises(ValueError) as invalid:
        service.record_inference(identifier, value)
    public = ipc.public_error(invalid.value)
    assert public["code"] == "INVALID_ARGUMENT"
    assert "synthetic-private-marker" not in public["message"]
    after = service.status(identifier, include_materials=False)
    assert after["artifacts"] == before["artifacts"]
    assert (after["stage"], after["proposal_attempt"], after["execution_attempt"]) == ("created", 0, 0) and runner.calls == 0


@pytest.mark.parametrize("outcome", ["started", "completed"])
def test_diagnostics_cannot_be_added_to_started_or_completed_inference(setup, outcome):
    service, runner, identifier = setup
    before = service.status(identifier, include_materials=False)
    with pytest.raises(ValueError, match="only failed or interrupted"):
        service.record_inference(identifier, receipt(outcome, SAFE_DIAGNOSTICS))
    after = service.status(identifier, include_materials=False)
    assert after["artifacts"] == before["artifacts"] and after["execution_attempt"] == 0 and runner.calls == 0

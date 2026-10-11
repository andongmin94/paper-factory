"""Transport dispatch only; no actual account, retained study or model calls."""

import json
from types import SimpleNamespace

import pytest

from paper_factory import ipc


def encoded(**params):
    return json.dumps({"id": "supplement-test", "method": "workflow.admitPortfolioEvidence", "params": params}).encode()


def test_supplement_dispatch_preserves_complete_manifest_and_original_file_bytes():
    calls = []
    service = SimpleNamespace(admit_portfolio_evidence=lambda *args: calls.append(args) or {"status": "synthetic-admission"})
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), None)
    try:
        params = {"researchId": "research-123456abcdef", "value": {"selection": "complete synthetic manifest"},
                  "files": [{"name": "original.html", "contentBase64": "6Q=="}]}
        request = ipc.request(encoded(**params))
        assert dispatcher.execute(request["method"], request["params"]) == {"status": "synthetic-admission"}
        assert calls == [(params["researchId"], params["value"], params["files"])]
    finally:
        dispatcher._pool.shutdown(wait=True)


@pytest.mark.parametrize("change", [
    {"files": []}, {"files": [{"name": "copy.txt", "contentBase64": "YQ==", "path": "untrusted"}]},
    {"value": "not an object"}, {"unknown": True},
])
def test_malformed_supplement_transport_never_reaches_admission(change):
    params = {"researchId": "research-123456abcdef", "value": {}, "files": [{"name": "copy.txt", "contentBase64": "YQ=="}]}
    with pytest.raises(ValueError):
        ipc.request(encoded(**{**params, **change}))


def test_complete_supplement_has_its_own_bound_without_expanding_general_uploads():
    files = [{"name": f"source-{index}.txt", "contentBase64": "YQ=="} for index in range(9)]
    params = {"researchId": "research-123456abcdef", "value": {}, "files": files}
    assert ipc.request(encoded(**params))["params"]["files"] == files
    ordinary = json.dumps({"id": "general", "method": "workflow.addEvidence",
                          "params": {"researchId": params["researchId"], "files": files}}).encode()
    with pytest.raises(ValueError):
        ipc.request(ordinary)
    params["files"] = files * 4
    with pytest.raises(ValueError):
        ipc.request(encoded(**params))

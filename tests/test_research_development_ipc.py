"""Exercise the real new RPC gateway; never access a retained study/account."""
import json
from types import SimpleNamespace

import pytest

from paper_factory import ipc


def encoded(params):
    return json.dumps({'id': 'development-gateway', 'method': 'workflow.grantResearchDevelopmentRound',
                       'params': params}).encode()


def test_development_grant_crosses_request_allowlist_and_dispatch_once():
    calls = []
    service = SimpleNamespace(grant_research_development_round=lambda rid: calls.append(rid) or {'synthetic': True})
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), None)
    try:
        parsed = ipc.request(encoded({'researchId': 'research-123456abcdef'}))
        assert dispatcher.execute(parsed['method'], parsed['params']) == {'synthetic': True}
        assert calls == ['research-123456abcdef']
    finally:
        dispatcher._pool.shutdown(wait=True)


@pytest.mark.parametrize('params', [{}, {'researchId': 'invalid'},
                                  {'researchId': 'research-123456abcdef', 'reset': True}])
def test_development_grant_rejects_missing_invalid_or_extra_parameters(params):
    with pytest.raises(ValueError):
        ipc.request(encoded(params))


def test_explicit_development_extension_has_its_own_bound_dispatch():
    calls = []
    service = SimpleNamespace(extend_research_development_round=lambda rid, prior: calls.append((rid, prior)) or {"synthetic": True})
    dispatcher = ipc.Dispatcher(SimpleNamespace(service=service), None)
    try:
        raw = json.dumps({"id": "extension", "method": "workflow.extendResearchDevelopmentRound",
            "params": {"researchId": "research-123456abcdef", "priorRoundId": "research-development-round-1"}}).encode()
        parsed = ipc.request(raw)
        assert dispatcher.execute(parsed["method"], parsed["params"]) == {"synthetic": True}
        assert calls == [("research-123456abcdef", "research-development-round-1")]
    finally:
        dispatcher._pool.shutdown(wait=True)


@pytest.mark.parametrize("prior", [None, 1, "", "../round-1", "research-development-round-0"])
def test_explicit_extension_rejects_missing_or_malformed_authorization(prior):
    params = {"researchId": "research-123456abcdef"}
    if prior is not None:
        params["priorRoundId"] = prior
    raw = json.dumps({"id": "extension", "method": "workflow.extendResearchDevelopmentRound", "params": params}).encode()
    with pytest.raises(ValueError):
        ipc.request(raw)

"""Injected native acquisition tests; no real network, SDK or project execution."""

from copy import deepcopy
import hashlib
from types import SimpleNamespace

import pytest

from paper_factory import workflow as engine
from paper_factory.autonomous.research_acquisition import ResearchAcquisitionMixin
from paper_factory.workspace import Workspace, write_json
from test_research_design import agenda_value, analysis_value, synthesis_value
from test_workflow import collect_arxiv_preprint


class Harness(ResearchAcquisitionMixin):
    def __init__(self, collector):
        self.collector = collector
        self.snapshots = []

    @staticmethod
    def _development_prefix(state):
        return "synthetic-research-development"

    @staticmethod
    def _development_root(state):
        return "research/synthetic-research-development"

    @staticmethod
    def _portfolio_literature(ws, record):
        return None, {}

    @staticmethod
    def _portfolio_append(ws, record, key, path, value):
        if key in record.artifacts or path.exists():
            raise ValueError("Synthetic harness forbids overwriting prior research bytes")
        write_json(path, value)
        engine._freeze(ws, record, key, path)

    def _improvement_save(self, ws, record, state):
        self.snapshots.append(deepcopy(state))


@pytest.fixture
def acquisition(tmp_path):
    ws = Workspace.create(tmp_path / "workspace")
    record = SimpleNamespace(artifacts={})
    original = ws.path("research/previous-paper.md")
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"Existing scientific manuscript must remain unchanged.\r\n")
    engine._freeze(ws, record, "previous-paper", original)
    state = {"calls": [{"id": "original-call", "outcome": "accepted"}], "reviews": [{"score": 6}],
        "policy": {"model_call_limit": 24}, "preserved_counters": {"sdk": 35, "native": 24},
        "research_development": {"id": "research-development-round-3"}}
    return ws, record, state


def collector_fixture(calls, *, reservations=1, identifier="1311.3903v1", abstract_only=False):
    def collect(queries, root, **kwargs):
        calls.append({"queries": list(queries), **kwargs})
        packet = collect_arxiv_preprint(queries, root, limit=kwargs["limit"], cancel=kwargs["cancel"], arxiv_id=identifier)
        packet["pdf_reservations"] = [{"source_id": packet["sources"][0]["id"], "url": "https://arxiv.org/pdf/" + identifier,
            "pdf_attempted": True} for _ in range(reservations)]
        if abstract_only:
            packet["sources"][0]["scope"] = "abstract"
        return packet
    return collect


def test_native_acquisition_retains_new_complete_body_and_preserves_all_old_records(acquisition):
    ws, record, state = acquisition
    before, old_bytes = deepcopy(state), ws.path("research/previous-paper.md").read_bytes()
    calls, harness = [], None
    harness = Harness(collector_fixture(calls))
    receipt = harness._research_acquire(ws, record, state, agenda_value())
    assert receipt["status"] == "completed" and len(calls) == 1
    assert calls[0]["queries"] == ["request admission semantics", "snapshot coalescing policy"]
    assert calls[0]["limit"] == 6 and calls[0]["pdf_reservation_limit"] == 2
    cards = harness._research_acquisition_cards(ws, record, state)
    assert len(cards) == 1 and cards[0]["source_role"] == "primary_full_text" and cards[0]["complete_body"]
    assert cards[0]["url"] == "https://arxiv.org/abs/1311.3903v1"
    assert cards[0]["collector_source_url"] == "https://arxiv.org/pdf/1311.3903v1" and cards[0]["fetched_at"]
    text = engine._artifact(ws, record, cards[0]["text_artifact_id"]).read_text(encoding="utf-8")
    assert "Synthetic passage: independent software test oracles" in text
    assert hashlib.sha256(text.encode()).hexdigest() == cards[0]["text_sha256"]
    assert all(state[key] == before[key] for key in before if key != "research_development")
    assert ws.path("research/previous-paper.md").read_bytes() == old_bytes
    assert harness._research_acquire(ws, record, state, agenda_value()) == receipt and len(calls) == 1
    # Actual acquired body and exact witness can flow into a changed research
    # question and writing brief; a search title is never the body evidence.
    from paper_factory.autonomous.research_design import research_design_report
    synthesis, analysis = synthesis_value(), analysis_value()
    witness = synthesis["closest_methods"][0]["evidence"][0]
    witness.update(source_id=cards[0]["id"], text_sha256=cards[0]["text_sha256"], quote=text[text.index("Synthetic passage:"):text.index("Synthetic passage:") + 120])
    analysis["document_evidence"] = [deepcopy(witness)]
    analysis["findings"][0]["evidence_ids"] = ["source-1", cards[0]["id"]]
    brief = research_design_report(agenda_value(), synthesis, analysis)["writer_brief"]
    assert brief["closest_methods"][0]["evidence"][0] == witness
    assert brief["completed_findings"] == analysis["findings"]


def test_followup_shares_pdf_budget_and_cannot_replay_a_previous_query_or_collection(acquisition):
    ws, record, state = acquisition
    calls = []
    harness = Harness(collector_fixture(calls))
    harness._research_acquire(ws, record, state, agenda_value())
    with pytest.raises(ValueError, match="changed queries"):
        harness._research_acquire(ws, record, state, agenda_value(), followup_queries=["request admission semantics"])
    harness.collector = collector_fixture(calls, identifier="2401.12345v1")
    receipt = harness._research_acquire(ws, record, state, agenda_value(), followup_queries=["conditional asynchronous service contracts"])
    assert receipt["status"] == "completed" and calls[-1]["pdf_reservation_limit"] == 1
    assert "arxiv:1311.3903v1" in calls[-1]["excluded_identities"]
    assert "https://arxiv.org/pdf/1311.3903v1" in calls[-1]["excluded_urls"]
    assert len(calls) == 2
    harness._research_acquire(ws, record, state, agenda_value(), followup_queries=["conditional asynchronous service contracts"])
    assert len(calls) == 2
    with pytest.raises(ValueError, match="original exact queries"):
        harness._research_acquire(ws, record, state, agenda_value(), followup_queries=["invented third collection query"])


def test_retained_acquisition_and_strengthening_preserve_original_agenda(acquisition):
    ws, record, state = acquisition
    calls = []
    harness = Harness(collector_fixture(calls))
    harness._research_acquire(ws, record, state, agenda_value())
    changed = agenda_value()
    changed["candidates"][0]["proposed_addition"] = "An unrelated proposal cannot silently replace the original question selection."
    with pytest.raises(ValueError, match="original exact queries"):
        harness._research_acquire(ws, record, state, changed)
    with pytest.raises(ValueError, match="original research agenda"):
        harness._research_acquire(ws, record, state, changed, followup_queries=["conditional asynchronous service contracts"])
    assert len(calls) == 1


def test_abstract_only_and_partial_results_never_become_completed_primary_methods(acquisition):
    ws, record, state = acquisition
    calls = []
    base = collector_fixture(calls, abstract_only=True)
    def partial(*args, **kwargs):
        packet = base(*args, **kwargs)
        packet["timed_out"] = True
        return packet
    harness = Harness(partial)
    receipt = harness._research_acquire(ws, record, state, agenda_value())
    assert receipt["status"] == "partial" and receipt["sources"] == []
    assert receipt["outcomes"][0]["status"] == "not_read_in_full"
    assert harness._research_acquisition_cards(ws, record, state) == []
    assert engine._read(ws, record, receipt["raw_result_artifact_id"])["timed_out"]


def test_interrupted_and_failed_acquisition_preserve_raw_without_redispatch_or_replenishment(acquisition):
    ws, record, state = acquisition
    calls = []
    def interrupted(queries, root, **kwargs):
        calls.append(queries)
        raw = root / "literature" / "partial-response.json"
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(b'{"actual_partial_response":true}')
        raise RuntimeError("Synthetic interrupted collector; retained partial bytes must survive")
    harness = Harness(interrupted)
    receipt = harness._research_acquire(ws, record, state, agenda_value())
    assert receipt["status"] == "partial" and receipt["pdf_reservations_consumed"] == 2
    assert any(engine._artifact(ws, record, key).read_bytes() == b'{"actual_partial_response":true}' for key in record.artifacts)
    harness._research_acquire(ws, record, state, agenda_value())
    assert len(calls) == 1


def test_acquired_body_tampering_is_detected_on_reuse(acquisition):
    ws, record, state = acquisition
    harness = Harness(collector_fixture([]))
    harness._research_acquire(ws, record, state, agenda_value())
    card = harness._research_acquisition_cards(ws, record, state)[0]
    engine._artifact(ws, record, card["text_artifact_id"]).write_bytes(b"An altered extraction cannot support a current comparison.")
    with pytest.raises(ValueError, match="changed|binding"):
        harness._research_acquisition_cards(ws, record, state)


@pytest.mark.parametrize("state", [{}, {"research_development": None}, {"research_development": {"contract_version": 1}}])
def test_existing_non_question_led_studies_have_no_acquisition_cards(acquisition, state):
    ws, record, _ = acquisition
    assert Harness(lambda *args, **kwargs: pytest.fail("Reading cards cannot collect new evidence"))._research_acquisition_cards(ws, record, state) == []


def test_process_interruption_retains_intent_partial_bytes_and_never_replays_network(acquisition):
    ws, record, state = acquisition
    calls = []
    def abort(queries, root, **kwargs):
        calls.append(queries)
        path = root / "literature" / "completed-before-interruption.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"Actual completed provider bytes remain after abrupt cancellation.")
        raise KeyboardInterrupt
    harness = Harness(abort)
    with pytest.raises(KeyboardInterrupt):
        harness._research_acquire(ws, record, state, agenda_value())
    assert len(calls) == 1 and state["research_development"]["acquisitions"][0]["status"] == "reserved"
    entry = harness._research_acquire(ws, record, state, agenda_value())
    assert entry["status"] == "interrupted" and entry["pdf_reservations_consumed"] == 2 and len(calls) == 1
    assert harness._research_acquisition_cards(ws, record, state) == []
    assert any(engine._artifact(ws, record, key).read_bytes() == b"Actual completed provider bytes remain after abrupt cancellation." for key in record.artifacts)

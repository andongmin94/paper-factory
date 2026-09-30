from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

import httpx
import pytest
from pydantic import ValidationError

from paper_factory import experiments, integrity, manuscript, publication, research, submission_package, venue_compiler, venue_policy
from paper_factory.models import ExperimentManifest, Paper, Study, Submission, SubmissionState, now, uid
from paper_factory.publication import AttestationInput, PreprintReview, PublicationEvent, ReceiptInput
from paper_factory.venue_policy import VenuePolicy
from paper_factory.workspace import digest_file, write_json
from test_submission import compile_case, mock_conversion, prepared
from test_manuscript import mocked_search
from test_venue_policy import setup_policy


def author_values():
    return AttestationInput(actor="Fixture [Author]", all_authors_approved=True,
        not_under_review_elsewhere=True, coi_correct=True, funding_correct=True,
        ai_disclosure_correct=True, author_information_correct=True)


def ready_case(prepared):
    ws, paper, submission, _, handler = compile_case(prepared)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        package, _ = submission_package.build(ws, submission, client=client)
    assert package.ready
    return ws, paper, ws.get("submission", submission.id, Submission), handler


def attest(ws, submission, handler):
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        return publication.attest(ws, submission, author_values(), client=client)


def receipt(ws, submission, target, tmp_path, **changes):
    values = dict(target_state=target, external_id="FIXTURE-JOURNAL-123",
        external_url="https://submit.example.org/manuscript/123", occurred_at=now(),
        verified_by="Fixture [Author]", note=f"Synthetic fixture confirming journal status {target}.")
    values.update(changes)
    path = tmp_path / "decision.txt"
    path.write_text("Synthetic test evidence: " + json.dumps(values), encoding="utf-8")
    return publication.record_receipt(ws, submission, ReceiptInput(**values), path)


@pytest.mark.parametrize("name", [name for name in AttestationInput.model_fields if name not in {"actor", "preprint_review"}])
@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_final_attestation_needs_six_explicit_strict_true_booleans(name, value):
    values = author_values().model_dump()
    values[name] = value
    with pytest.raises(ValidationError):
        AttestationInput(**values)


def test_ready_package_gets_separate_final_author_attestation_and_reservation(prepared, mock_conversion):
    ws, paper, submission, handler = ready_case(prepared)
    freeze_before = paper.freeze_digest
    package_before = submission.package_digest
    event = attest(ws, submission, handler)
    assert event.kind == "attestation" and event.to_state == SubmissionState.AUTHOR_ATTESTED
    report = publication.check(ws, submission)
    assert report["passed"] and report["active"] and not report["external_submission_recorded"]
    assert report["guard_scope"] == "current_workspace"
    assert not report["automatic_external_submission_performed"]
    assert ws.get("paper", paper.id, Paper).freeze_digest == freeze_before
    assert ws.get("submission", submission.id, Submission).package_digest == package_before
    assert submission_package.verify(ws, submission)["ready"]
    assert publication.active_for_study(ws, paper.study_id)[0].id == submission.id
    live = ws.get("policy", event.values["policy_id"], VenuePolicy)
    assert live.id != submission.policy_id


def test_changed_live_policy_or_wrong_author_blocks_final_attestation(prepared, mock_conversion):
    ws, _, submission, handler = ready_case(prepared)
    wrong = author_values().model_copy(update={"actor": "Different Author"})
    with pytest.raises(ValueError, match="approved named author"):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            publication.attest(ws, submission, wrong, client=client)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, text="Changed requirements", headers={"content-type": "text/html"}))) as client:
        with pytest.raises(ValueError, match="official policy changed"):
            publication.attest(ws, submission, author_values(), client=client)
    assert ws.get("submission", submission.id, Submission).state == SubmissionState.SUBMISSION_READY
    assert not ws.list("publication_event", PublicationEvent)


def test_second_candidate_cannot_reserve_same_study(prepared, mock_conversion):
    ws, _, first, handler = ready_case(prepared)
    _, _, second, handler2 = ready_case(prepared)
    attest(ws, first, handler)
    with pytest.raises(ValueError, match="active peer-reviewed submission"):
        attest(ws, second, handler2)
    assert publication.check(ws, first)["passed"]
    assert ws.get("submission", second.id, Submission).state == SubmissionState.SUBMISSION_READY


def test_unused_reservation_can_be_cancelled_and_reattested_with_history(prepared, mock_conversion):
    ws, _, submission, handler = ready_case(prepared)
    first = attest(ws, submission, handler)
    cancelled = publication.cancel_attestation(ws, submission, "Fixture [Author]", "This unused test reservation is cancelled.")
    assert cancelled.previous_sha256 == first.artifact_sha256
    assert not publication.check(ws, submission)["active"]
    attest(ws, submission, handler)
    assert len(publication.check(ws, submission)["events"]) == 3


def test_cancellation_cannot_release_confirmed_external_submission(prepared, mock_conversion, tmp_path):
    ws, _, submission, handler = ready_case(prepared)
    attest(ws, submission, handler)
    receipt(ws, submission, SubmissionState.SUBMITTED, tmp_path)
    with pytest.raises(ValueError, match="unused author attestation"):
        publication.cancel_attestation(ws, submission, "Fixture [Author]", "Cannot cancel an actual journal submission.")
    assert publication.check(ws, submission)["active"]


@pytest.mark.parametrize("terminal", [SubmissionState.REJECTED, SubmissionState.WITHDRAWN_CONFIRMED])
def test_actual_rejection_or_confirmed_withdrawal_releases_guard(prepared, mock_conversion, tmp_path, terminal):
    ws, _, first, handler = ready_case(prepared)
    _, _, second, handler2 = ready_case(prepared)
    attest(ws, first, handler)
    receipt(ws, first, SubmissionState.SUBMITTED, tmp_path)
    receipt(ws, first, SubmissionState.UNDER_REVIEW, tmp_path)
    if terminal == SubmissionState.WITHDRAWN_CONFIRMED:
        receipt(ws, first, SubmissionState.WITHDRAWAL_REQUESTED, tmp_path)
        with pytest.raises(ValueError, match="active peer-reviewed submission"):
            attest(ws, second, handler2)
    decision = receipt(ws, first, terminal, tmp_path)
    assert decision.evidence_sha256
    assert not publication.check(ws, first)["active"]
    attest(ws, second, handler2)
    assert publication.check(ws, second)["active"]


def test_acceptance_proofs_publication_remain_occupied(prepared, mock_conversion, tmp_path):
    ws, _, first, handler = ready_case(prepared)
    _, _, second, handler2 = ready_case(prepared)
    attest(ws, first, handler)
    for state in (SubmissionState.SUBMITTED, SubmissionState.ACCEPTED, SubmissionState.PROOF, SubmissionState.PUBLISHED):
        receipt(ws, first, state, tmp_path)
        with pytest.raises(ValueError, match="active peer-reviewed submission"):
            attest(ws, second, handler2)
    assert publication.check(ws, first)["external_submission_recorded"]


def test_revision_reentry_requires_receipts_and_cannot_reset_to_ready(prepared, mock_conversion, tmp_path):
    ws, _, submission, handler = ready_case(prepared)
    attest(ws, submission, handler)
    for state in (SubmissionState.SUBMITTED, SubmissionState.UNDER_REVIEW, SubmissionState.REVISION):
        receipt(ws, submission, state, tmp_path)
    with pytest.raises(ValueError, match="verified revision delivery"):
        receipt(ws, submission, SubmissionState.UNDER_REVIEW, tmp_path)
    assert ws.get("submission", submission.id, Submission).state == SubmissionState.REVISION
    assert publication.check(ws, submission)["passed"]
    with pytest.raises(ValueError, match="Invalid submission transition"):
        receipt(ws, submission, SubmissionState.WITHDRAWN_CONFIRMED, tmp_path)
    assert publication.check(ws, submission)["passed"]


def test_historical_observed_review_reentry_keeps_its_immutable_receipt_valid(prepared, mock_conversion, tmp_path):
    ws, paper, submission, handler = ready_case(prepared)
    attest(ws, submission, handler)
    for state in (SubmissionState.SUBMITTED, SubmissionState.UNDER_REVIEW, SubmissionState.REVISION):
        receipt(ws, submission, state, tmp_path)
    # A preserved observation is still a journal fact. The current public import
    # gate requires a delivery, while historical receipt validation stays intact.
    values = ReceiptInput(target_state=SubmissionState.UNDER_REVIEW, external_id="FIXTURE-JOURNAL-123",
        external_url="https://submit.example.org/manuscript/123", occurred_at=now(),
        verified_by="Fixture [Author]", note="Synthetic historical observed review receipt.")
    with publication._write_transaction(ws) as (db, published):
        submissions, histories = publication._audit(ws, db)
        current, history = submissions[submission.id], histories[submission.id]
        with pytest.raises(ValueError, match="verified revision delivery"):
            publication._append(ws, db, current, paper, history,
                kind="receipt", target=SubmissionState.UNDER_REVIEW, actor=values.verified_by,
                values=values.model_dump(mode="json"), evidence=b"Unverified new receipt")
    # Reconstruct an existing observed event in the persisted format, without
    # routing it through the new writer. Reading old observations remains valid.
    data = publication.EventData(id=uid("publication-event"), submission_id=submission.id, paper_id=paper.id,
        study_id=paper.study_id, sequence=len(history) + 1, kind="receipt",
        from_state=SubmissionState.REVISION, to_state=SubmissionState.UNDER_REVIEW,
        actor=values.verified_by, recorded_at=now(), previous_sha256=history[-1].artifact_sha256,
        values=values.model_dump(mode="json"))
    root = ws.path(f"publication/{submission.id}/{data.id}")
    root.mkdir()
    (root / "evidence.bin").write_bytes(b"Synthetic historical receipt only")
    data.evidence_sha256 = digest_file(root / "evidence.bin")
    write_json(root / "event.json", data)
    event = PublicationEvent(**data.model_dump(), artifact_sha256=digest_file(root / "event.json"))
    ws.save("publication_event", event)
    current.state = SubmissionState.UNDER_REVIEW
    ws.save("submission", current)
    report = publication.check(ws, submission)
    assert report["passed"] and report["active"] and report["state"] == SubmissionState.UNDER_REVIEW


def test_missing_empty_unapproved_and_changed_identity_receipts_do_not_advance(prepared, mock_conversion, tmp_path):
    ws, _, submission, handler = ready_case(prepared)
    with pytest.raises(ValueError, match="Invalid submission transition"):
        receipt(ws, submission, SubmissionState.SUBMITTED, tmp_path)
    attest(ws, submission, handler)
    with pytest.raises(ValueError, match="approved named author"):
        receipt(ws, submission, SubmissionState.SUBMITTED, tmp_path, verified_by="Unknown Actor")
    with pytest.raises(ValueError, match="verified submission service"):
        receipt(ws, submission, SubmissionState.SUBMITTED, tmp_path, external_url="https://unrelated.example.org/status")
    with pytest.raises(ValueError, match="precedes author attestation"):
        receipt(ws, submission, SubmissionState.SUBMITTED, tmp_path, occurred_at="2000-01-01T00:00:00+00:00")
    receipt(ws, submission, SubmissionState.SUBMITTED, tmp_path)
    with pytest.raises(ValueError, match="manuscript ID changed"):
        receipt(ws, submission, SubmissionState.REJECTED, tmp_path, external_id="OTHER-ID")
    assert publication.check(ws, submission)["state"] == SubmissionState.SUBMITTED


@pytest.mark.parametrize("attack", ["submission_state", "deleted_submission", "deleted_event", "event_artifact", "receipt_evidence"])
def test_corrupt_or_missing_history_fails_closed_before_reserving_new_candidate(prepared, mock_conversion, tmp_path, attack):
    ws, _, first, handler = ready_case(prepared)
    _, _, second, handler2 = ready_case(prepared)
    attest(ws, first, handler)
    decision = receipt(ws, first, SubmissionState.SUBMITTED, tmp_path)
    if attack == "submission_state":
        current = ws.get("submission", first.id, Submission)
        current.state = SubmissionState.REJECTED
        ws.save("submission", current)
    elif attack == "deleted_submission":
        with ws._database() as db:
            db.execute("DELETE FROM records WHERE kind='submission' AND id=?", (first.id,))
    elif attack == "deleted_event":
        with ws._database() as db:
            db.execute("DELETE FROM records WHERE kind='publication_event' AND id=?", (decision.id,))
    elif attack == "event_artifact":
        ws.path(f"publication/{first.id}/{decision.id}/event.json").write_text("{}", encoding="utf-8")
    else:
        ws.path(f"publication/{first.id}/{decision.id}/evidence.bin").write_bytes(b"changed")
    assert not publication.check(ws, first)["passed"]
    with pytest.raises(ValueError):
        attest(ws, second, handler2)
    assert ws.get("submission", second.id, Submission).state == SubmissionState.SUBMISSION_READY


def test_competing_threads_atomically_reserve_only_one_candidate(prepared, mock_conversion, monkeypatch):
    ws, _, first, handler = ready_case(prepared)
    _, _, second, handler2 = ready_case(prepared)
    barrier = threading.Barrier(2)
    original = publication.refresh_policy

    def synchronized(*args, **kwargs):
        result = original(*args, **kwargs)
        barrier.wait(timeout=10)
        return result

    monkeypatch.setattr(publication, "refresh_policy", synchronized)

    def reserve(candidate, active):
        try:
            attest(ws, candidate, active)
            return "reserved"
        except ValueError as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(reserve, first, handler), executor.submit(reserve, second, handler2)]
        outcomes = [future.result(timeout=30) for future in futures]
    assert outcomes.count("reserved") == 1
    assert any("active peer-reviewed submission" in outcome for outcome in outcomes)
    assert len(ws.list("publication_event", PublicationEvent)) == 1


def test_receipt_evidence_is_copied_and_not_overwritten_by_later_import(prepared, mock_conversion, tmp_path):
    ws, _, submission, handler = ready_case(prepared)
    attest(ws, submission, handler)
    submitted = receipt(ws, submission, SubmissionState.SUBMITTED, tmp_path)
    original = ws.path(f"publication/{submission.id}/{submitted.id}/evidence.bin").read_bytes()
    receipt(ws, submission, SubmissionState.UNDER_REVIEW, tmp_path)
    assert ws.path(f"publication/{submission.id}/{submitted.id}/evidence.bin").read_bytes() == original
    assert publication.check(ws, submission)["passed"]


def test_stale_package_policy_does_not_block_historical_decision(prepared, mock_conversion, tmp_path, monkeypatch):
    ws, _, submission, handler = ready_case(prepared)
    attest(ws, submission, handler)
    receipt(ws, submission, SubmissionState.SUBMITTED, tmp_path)
    future = datetime.now(timezone.utc) + timedelta(days=8)

    class FutureDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return future.astimezone(tz or timezone.utc)

    monkeypatch.setattr(venue_policy, "datetime", FutureDateTime)
    monkeypatch.setattr(publication, "datetime", FutureDateTime)
    monkeypatch.setattr(publication, "now", lambda: future.isoformat())
    report = submission_package.verify(ws, submission)
    assert not report["ready"] and any("stale" in error for error in report["errors"])
    receipt(ws, submission, SubmissionState.REJECTED, tmp_path, occurred_at=future.isoformat())
    assert publication.check(ws, submission)["passed"]


@pytest.mark.parametrize("identical_evidence", [True, False])
def test_new_study_id_cannot_bypass_exact_evidence_overlap_but_independent_evidence_can(prepared, mock_conversion, identical_evidence):
    ws, paper, first, handler = ready_case(prepared)
    attest(ws, first, handler)
    study = research.create_study(ws, question="Which source measurements follow the separate fixture protocol?", title="Separate fixture study")
    mocked_search(ws, study)
    source = ws.get("manifest", ws.list("manifest", ExperimentManifest)[0].id, ExperimentManifest)
    manifest = source.model_copy(update={"id": uid("experiment"), "study_id": study.id})
    if not identical_evidence:
        manifest.command = ["{python}", "-c", "import json; from pathlib import Path; p=Path('.paperfactory-results/inventory.json'); p.parent.mkdir(); p.write_text(json.dumps({'file_count':42,'total_bytes':84}))"]
    ws.save("manifest", manifest)
    write_json(ws.path(f"experiments/{manifest.id}.json"), manifest)
    assert experiments.run_experiment(ws, manifest).status == "SUCCEEDED"
    other, _ = manuscript.build(ws, study)
    integrity.approve(ws, other, approved=True, assessment="Synthetic independent fixture evidence and related-work metadata were reviewed.")
    policy, active = prepared[4]()
    candidate = venue_compiler.select(ws, other, prepared[1], policy)
    with httpx.Client(transport=httpx.MockTransport(active)) as client:
        candidate, _ = venue_compiler.compile_submission(ws, candidate, prepared[3], client=client)
        package, _ = submission_package.build(ws, candidate, client=client)
    assert package.ready
    candidate = ws.get("submission", candidate.id, Submission)
    if identical_evidence:
        with pytest.raises(ValueError, match="Approved evidence overlaps"):
            attest(ws, candidate, active)
    else:
        attest(ws, candidate, active)
        assert len(publication.active_for_study(ws, study.id)) == 1


def test_existing_preprint_requires_complete_explicit_review_against_target_policy(prepared, mock_conversion, tmp_path):
    from paper_factory import preprints
    ws, paper, submission, handler = ready_case(prepared)
    receipt_path = tmp_path / "preprint-observation.json"
    write_json(receipt_path, preprints.PostingReceipt(paper_id=paper.id, remote_identifier="fixture-preprint-v1",
        source_url="https://preprints.example.net/fixture-v1", posted_at=now(), recorded_by=paper.approved_by,
        statement="Synthetic observation of an existing public preprint posting.", content_digest=paper.freeze_digest))
    evidence = tmp_path / "preprint-evidence.txt"
    evidence.write_text("Synthetic preprint observation receipt.", encoding="utf-8")
    posting, _ = preprints.record_posting(ws, receipt_path, evidence, confirmed=True)
    with pytest.raises(ValueError, match="Every existing Study preprint"):
        attest(ws, submission, handler)
    policy = ws.get("policy", submission.policy_id, VenuePolicy)
    values = author_values()
    values.preprint_review = PreprintReview(decision="unknown", preprint_ids=[posting.id], evidence=policy.evidence["preprint_policy"])
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="explicit allowed decision"):
            publication.attest(ws, submission, values, client=client)
    values.preprint_review = PreprintReview(decision="allowed", preprint_ids=[posting.id], evidence=policy.evidence["preprint_policy"])
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        event = publication.attest(ws, submission, values, client=client)
    assert event.values["preprint_records"][posting.id]
    assert publication.check(ws, submission)["passed"]
    later = json.loads(receipt_path.read_bytes())
    later["remote_identifier"] = "fixture-preprint-v2"
    later["source_url"] = "https://preprints.example.net/fixture-v2"
    later["posted_at"] = now()
    write_json(receipt_path, later)
    preprints.record_posting(ws, receipt_path, evidence, confirmed=True)
    # History binds facts reviewed at that event; a later posting is reviewed
    # at its own authorization boundary and cannot rewrite the old attestation.
    assert publication.check(ws, submission)["passed"]
    ws.path(f"preprints/{posting.id}/posting/evidence.bin").write_text("Tampered posting receipt.", encoding="utf-8")
    assert not publication.check(ws, submission)["passed"]


def test_new_posting_blocks_outbound_action_but_does_not_erase_observed_submission(prepared, mock_conversion, tmp_path):
    from paper_factory import preprints
    ws, paper, submission, handler = ready_case(prepared)
    event = attest(ws, submission, handler)
    assert publication.assert_current_attestation(ws, submission).id == event.id
    receipt_path = tmp_path / "new-posting.json"
    write_json(receipt_path, preprints.PostingReceipt(paper_id=paper.id, remote_identifier="new-fixture-preprint",
        source_url="https://preprints.example.net/new-fixture-preprint", posted_at=now(), recorded_by=paper.approved_by,
        statement="Synthetic observation of a preprint posted after final author attestation.", content_digest=paper.freeze_digest))
    evidence = tmp_path / "new-posting.txt"
    evidence.write_text("Synthetic newly observed posting evidence.", encoding="utf-8")
    preprints.record_posting(ws, receipt_path, evidence, confirmed=True)
    with ws._database() as db:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError, match="preprint"):
            publication.assert_current_attestation(ws, submission, db=db)
    assert publication.check(ws, submission)["passed"]
    # An actual imported journal observation remains recordable even when the
    # author did not use Paper Factory's outbound preparation checks.
    receipt(ws, submission, SubmissionState.SUBMITTED, tmp_path)
    assert publication.check(ws, submission)["state"] == SubmissionState.SUBMITTED
    with pytest.raises(ValueError, match="current final author attestation"):
        publication.assert_current_attestation(ws, submission)


def test_outbound_boundary_rechecks_the_author_reviewed_preprint_set(prepared, mock_conversion, tmp_path):
    from paper_factory import preprints
    ws, paper, submission, handler = ready_case(prepared)
    receipt_path = tmp_path / "reviewed-posting.json"
    write_json(receipt_path, preprints.PostingReceipt(paper_id=paper.id, remote_identifier="reviewed-fixture-preprint",
        source_url="https://preprints.example.net/reviewed-fixture-preprint", posted_at=now(), recorded_by=paper.approved_by,
        statement="Synthetic observed posting reviewed against the target journal policy.", content_digest=paper.freeze_digest))
    evidence = tmp_path / "reviewed-posting.txt"
    evidence.write_text("Synthetic reviewed posting evidence.", encoding="utf-8")
    posting, _ = preprints.record_posting(ws, receipt_path, evidence, confirmed=True)
    policy = ws.get("policy", submission.policy_id, VenuePolicy)
    values = author_values()
    values.preprint_review = PreprintReview(decision="allowed", preprint_ids=[posting.id], evidence=policy.evidence["preprint_policy"])
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        event = publication.attest(ws, submission, values, client=client)
    assert publication.assert_current_attestation(ws, submission).id == event.id
    publication.cancel_attestation(ws, submission, paper.approved_by, "This unsubmitted fixture author attestation is cancelled.")
    with pytest.raises(ValueError, match="current final author attestation"):
        publication.assert_current_attestation(ws, submission)


def test_deleting_preprint_record_cannot_hide_posting_before_first_attestation(prepared, mock_conversion, tmp_path):
    from paper_factory import preprints
    ws, paper, submission, handler = ready_case(prepared)
    receipt_path = tmp_path / "posting.json"
    write_json(receipt_path, preprints.PostingReceipt(paper_id=paper.id, remote_identifier="hidden-fixture",
        source_url="https://preprints.example.net/hidden-fixture", posted_at=now(), recorded_by=paper.approved_by,
        statement="Synthetic posting observation cannot be erased from registry.", content_digest=paper.freeze_digest))
    evidence = tmp_path / "posting.txt"
    evidence.write_text("Synthetic posting evidence.", encoding="utf-8")
    record, _ = preprints.record_posting(ws, receipt_path, evidence, confirmed=True)
    with ws._database() as db:
        db.execute("DELETE FROM records WHERE kind='preprint' AND id=?", (record.id,))
    with pytest.raises(ValueError, match="registry|index|orphan|artifact"):
        attest(ws, submission, handler)
    assert ws.get("submission", submission.id, Submission).state == SubmissionState.SUBMISSION_READY


@pytest.mark.parametrize("operation", ["attestation", "receipt"])
def test_database_commit_failure_rolls_back_owned_event_without_losing_history(prepared, mock_conversion, tmp_path, monkeypatch, operation):
    ws, _, submission, handler = ready_case(prepared)
    if operation == "receipt":
        attest(ws, submission, handler)
    initial = ws.get("submission", submission.id, Submission).state
    count = len(ws.list("publication_event", PublicationEvent))
    original = ws._database
    failed = False

    @contextmanager
    def failure_at_commit():
        nonlocal failed
        with original() as db:
            yield db
            event_count = db.execute("SELECT count(*) FROM records WHERE kind='publication_event'").fetchone()[0]
            if event_count > count and not failed:
                failed = True
                raise OSError("Synthetic transaction commit failure")

    monkeypatch.setattr(ws, "_database", failure_at_commit)
    with pytest.raises(OSError, match="Synthetic transaction commit failure"):
        if operation == "attestation":
            attest(ws, submission, handler)
        else:
            receipt(ws, submission, SubmissionState.SUBMITTED, tmp_path)
    assert ws.get("submission", submission.id, Submission).state == initial
    assert len(ws.list("publication_event", PublicationEvent)) == count
    assert publication.check(ws, submission)["passed"]
    if operation == "attestation":
        attest(ws, submission, handler)
    else:
        receipt(ws, submission, SubmissionState.SUBMITTED, tmp_path)
    assert publication.check(ws, submission)["passed"]


def test_competing_processes_atomically_reserve_only_one_candidate(prepared, mock_conversion, tmp_path):
    ws, _, first, handler = ready_case(prepared)
    _, _, second, _ = ready_case(prepared)
    synchronization = tmp_path / "race"
    synchronization.mkdir()
    worker = tmp_path / "race_worker.py"
    worker.write_text('''import json, socket, sys, time
from pathlib import Path
from types import SimpleNamespace
import httpx
from paper_factory import publication
from paper_factory.models import Submission
from paper_factory.venue_policy import VenuePolicy
from paper_factory.workspace import Workspace
class Reader:
    def __init__(self, path):
        self.pages = [SimpleNamespace(extract_text=lambda: Path(path).read_text(encoding="utf-8"))]
        self.metadata = {}
sys.modules["pypdf"] = SimpleNamespace(PdfReader=Reader)
socket.getaddrinfo = lambda host, port, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
ws = Workspace(Path(sys.argv[1]))
candidate = ws.get("submission", sys.argv[2], Submission)
policy = ws.get("policy", candidate.policy_id, VenuePolicy)
body = ws.path(policy.sources[0].raw_path).read_text(encoding="utf-8")
sync = Path(sys.argv[3])
original = publication.refresh_policy
def wait_for_start(*args, **kwargs):
    result = original(*args, **kwargs)
    (sync / (candidate.id + ".ready")).touch()
    deadline = time.monotonic() + 30
    while not (sync / "go").exists():
        if time.monotonic() > deadline: raise RuntimeError("Race barrier timed out")
        time.sleep(.01)
    return result
publication.refresh_policy = wait_for_start
values = publication.AttestationInput(actor="Fixture [Author]", all_authors_approved=True, not_under_review_elsewhere=True, coi_correct=True, funding_correct=True, ai_disclosure_correct=True, author_information_correct=True)
try:
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, text=body, headers={"content-type":"text/html"}))) as client:
        publication.attest(ws, candidate, values, client=client)
    print("reserved")
except ValueError as error:
    print(str(error))
''', encoding="utf-8")
    processes = [subprocess.Popen([sys.executable, str(worker), str(ws.root), candidate.id, str(synchronization)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for candidate in (first, second)]
    try:
        deadline = time.monotonic() + 30
        while not all((synchronization / f"{candidate.id}.ready").exists() for candidate in (first, second)):
            assert all(process.poll() is None for process in processes), "Race worker exited before its barrier"
            assert time.monotonic() < deadline, "Race workers did not reach the barrier"
            time.sleep(.01)
        (synchronization / "go").touch()
        outputs = [process.communicate(timeout=30) for process in processes]
        assert all(process.returncode == 0 and not error for process, (_, error) in zip(processes, outputs))
        assert sum(output.strip() == "reserved" for output, _ in outputs) == 1
        assert any("active peer-reviewed submission" in output for output, _ in outputs)
        assert len(ws.list("publication_event", PublicationEvent)) == 1
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate()

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import sqlite3
import zipfile

import httpx
import pytest

from paper_factory import preprints, publication, venue_compiler
from paper_factory.models import Submission, SubmissionState
from paper_factory.preprints import PostingReceipt, Preprint, PreprintSettings
from paper_factory.venue_policy import VenuePolicy
from paper_factory.workspace import digest_file, write_json
from test_submission import mock_conversion, prepared
from test_venue_policy import setup_policy


@pytest.fixture
def preprint_case(prepared, tmp_path, monkeypatch, mock_conversion):
    ws, venue, paper, _, policy_for = prepared
    policy, handler = policy_for()
    settings = PreprintSettings(paper_id=paper.id, policy_id=policy.id, server="Example preprint server",
                               server_url="https://preprints.example.org/", license="CC BY 4.0",
                               reviewed_by=paper.approved_by, decision="allowed",
                               evidence=policy.evidence["preprint_policy"].model_copy(update={"interpretation": "The author reviewed the official conditions for this server and license."}),
                               author_approval=True, authorized_to_post=True, policy_interpretation_confirmed=True)
    path = tmp_path / "preprint-settings.json"
    write_json(path, settings)
    monkeypatch.setattr(preprints, "convert", venue_compiler.convert)
    return ws, paper, policy, handler, settings, path


def prepare_case(case):
    ws, _, _, handler, _, path = case
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        return preprints.prepare(ws, path, client=client)


def receipt_case(case, tmp_path, record=None):
    _, paper, _, _, _, _ = case
    receipt = PostingReceipt(paper_id=paper.id, remote_identifier="example.0001v1",
                             source_url="https://preprints.example.org/abs/example.0001v1",
                             posted_at=datetime.now(timezone.utc).isoformat(), recorded_by=paper.approved_by,
                             statement="The author inspected the posting confirmation and approved content.",
                             content_digest=paper.freeze_digest, preparation_id=record.id if record else None)
    path = tmp_path / "posting-observation.json"
    evidence = tmp_path / "server-receipt.txt"
    write_json(path, receipt)
    evidence.write_text("Synthetic test receipt: example.0001v1 is posted on the fixture server.", encoding="utf-8")
    return path, evidence, receipt


def expire_policy(ws, policy):
    for source in policy.sources:
        source.fetched_at = (datetime.now(timezone.utc) - timedelta(days=policy.ttl_days + 1)).isoformat()
    write_json(ws.path(policy.receipt_path), policy.model_dump(mode="json", exclude={"receipt_sha256"}))
    policy.receipt_sha256 = digest_file(ws.path(policy.receipt_path))
    ws.save("policy", policy)


def test_preprint_public_bundle_and_observed_posting_stay_separate_from_peer_review(preprint_case, tmp_path):
    ws, paper, _, _, _, _ = preprint_case
    submission = Submission(paper_id=paper.id, venue_id="venue-fixture", policy_id="policy-fixture", candidate_digest=paper.freeze_digest)
    ws.save("submission", submission)
    before = ws.get("submission", submission.id, Submission)
    record, root = prepare_case(preprint_case)
    report = preprints.check(ws, record)
    assert report["valid"] and report["upload_authorized"] and not report["posting_recorded"]
    assert not report["peer_reviewed"] and not report["external_upload_performed"]
    with zipfile.ZipFile(root / "source.zip") as archive:
        assert set(archive.namelist()) == {"manuscript.md", "manuscript.tex", "metadata.json"}
        public = "\n".join(archive.read(name).decode() for name in archive.namelist())
    assert "author@example.org" not in public
    assert "raw_artifacts" not in public and "[Evidence:" not in public
    assert (root / "manuscript.md").read_text(encoding="utf-8").count("## Limitations") == 1
    receipt, evidence, _ = receipt_case(preprint_case, tmp_path, record)
    posted, _ = preprints.record_posting(ws, receipt, evidence, confirmed=True)
    report = preprints.check(ws, posted)
    assert posted.id == record.id and posted.state == "PREPRINTED"
    assert report["valid"] and report["posting_recorded"] and not report["upload_authorized"]
    assert ws.get("submission", submission.id, Submission) == before
    assert (root / "posting/evidence.bin").read_bytes() == evidence.read_bytes()


@pytest.mark.parametrize("decision", ["forbidden", "unknown"])
def test_unknown_or_forbidden_preprint_permission_blocks_preparation(preprint_case, decision):
    ws, _, _, _, settings, path = preprint_case
    settings.decision = decision
    write_json(path, settings)
    with pytest.raises(ValueError, match="explicit allowed"):
        prepare_case(preprint_case)
    assert not ws.list("preprint", Preprint)


@pytest.mark.parametrize("field", ["author_approval", "authorized_to_post", "policy_interpretation_confirmed"])
def test_each_preprint_attestation_requires_strict_explicit_true(preprint_case, field):
    _, _, _, _, settings, path = preprint_case
    setattr(settings, field, False)
    write_json(path, settings)
    with pytest.raises(ValueError, match="every explicit"):
        prepare_case(preprint_case)
    values = settings.model_dump()
    values[field] = "true"
    with pytest.raises(ValueError):
        PreprintSettings.model_validate(values)


def test_preprint_decision_must_quote_captured_official_evidence(preprint_case):
    _, _, _, _, settings, path = preprint_case
    settings.evidence.excerpt = "A different webpage says that preprints are permitted."
    write_json(path, settings)
    with pytest.raises(ValueError, match="captured official"):
        prepare_case(preprint_case)


def test_preprint_requires_the_actual_approved_author(preprint_case):
    _, _, _, _, settings, path = preprint_case
    settings.reviewed_by = "Someone else"
    write_json(path, settings)
    with pytest.raises(ValueError, match="approved scientific author"):
        prepare_case(preprint_case)


def test_changed_live_policy_blocks_even_when_previous_capture_was_valid(preprint_case):
    ws, _, _, _, _, path = preprint_case
    changed = lambda request: httpx.Response(200, text="<p>The publisher changed the preprint rules.</p>", headers={"content-type": "text/html"})
    with httpx.Client(transport=httpx.MockTransport(changed)) as client:
        with pytest.raises(ValueError, match="Live preprint policy changed"):
            preprints.prepare(ws, path, client=client)
    assert not ws.list("preprint", Preprint)


def test_expired_intact_prior_policy_can_be_refreshed_before_preparation(preprint_case):
    ws, _, policy, _, _, _ = preprint_case
    expire_policy(ws, policy)
    record, _ = prepare_case(preprint_case)
    assert record.policy_id != policy.id
    assert preprints.check(ws, record)["upload_authorized"]


def test_posting_audit_survives_policy_expiry_without_reauthorizing_upload(preprint_case, tmp_path):
    ws, _, _, _, _, _ = preprint_case
    record, _ = prepare_case(preprint_case)
    policy = ws.get("policy", record.policy_id, VenuePolicy)
    expire_policy(ws, policy)
    report = preprints.check(ws, record)
    assert report["valid"] and not report["upload_authorized"] and report["permission_errors"]
    receipt, evidence, _ = receipt_case(preprint_case, tmp_path, record)
    posted, _ = preprints.record_posting(ws, receipt, evidence, confirmed=True)
    report = preprints.check(ws, posted)
    assert report["valid"] and report["posting_recorded"] and not report["upload_authorized"]


def test_existing_posting_is_an_observed_fact_without_policy_permission(preprint_case, tmp_path):
    ws, _, _, _, settings, path = preprint_case
    settings.decision = "forbidden"
    write_json(path, settings)
    receipt, evidence, _ = receipt_case(preprint_case, tmp_path)
    posted, _ = preprints.record_posting(ws, receipt, evidence, confirmed=True)
    report = preprints.check(ws, posted)
    assert report["valid"] and report["posting_recorded"] and not report["upload_authorized"]
    assert not posted.policy_id and not posted.files
    with pytest.raises(ValueError, match="already recorded"):
        preprints.record_posting(ws, receipt, evidence, confirmed=True)


def test_posting_import_requires_author_confirmation_and_actual_nonempty_receipt(preprint_case, tmp_path):
    ws, _, _, _, _, _ = preprint_case
    receipt, evidence, _ = receipt_case(preprint_case, tmp_path)
    with pytest.raises(ValueError, match="Explicit author confirmation"):
        preprints.record_posting(ws, receipt, evidence)
    evidence.write_bytes(b"")
    with pytest.raises(ValueError, match="nonempty ordinary file"):
        preprints.record_posting(ws, receipt, evidence, confirmed=True)
    assert not ws.list("preprint", Preprint)


@pytest.mark.parametrize("field,value", [("recorded_by", "Another Author"), ("content_digest", "0" * 64)])
def test_posting_receipt_cannot_rebind_author_or_frozen_content(preprint_case, tmp_path, field, value):
    ws, _, _, _, _, _ = preprint_case
    receipt_path, evidence, receipt = receipt_case(preprint_case, tmp_path)
    setattr(receipt, field, value)
    write_json(receipt_path, receipt)
    with pytest.raises(ValueError, match="approved"):
        preprints.record_posting(ws, receipt_path, evidence, confirmed=True)


def test_posting_cannot_reuse_preparation_for_a_different_server(preprint_case, tmp_path):
    ws, _, _, _, _, _ = preprint_case
    record, _ = prepare_case(preprint_case)
    path, evidence, receipt = receipt_case(preprint_case, tmp_path, record)
    receipt.source_url = "https://unrelated.example.org/abs/0001"
    write_json(path, receipt)
    with pytest.raises(ValueError, match="prepared preprint server"):
        preprints.record_posting(ws, path, evidence, confirmed=True)


@pytest.mark.parametrize("name", ["manuscript.md", "source.zip", "manifest.json"])
def test_preparation_artifact_tampering_is_detected(preprint_case, name):
    ws, _, _, _, _, _ = preprint_case
    record, root = prepare_case(preprint_case)
    (root / name).write_bytes(b"tampered")
    assert not preprints.check(ws, record)["valid"]


@pytest.mark.parametrize("name", ["receipt.json", "evidence.bin"])
def test_imported_posting_receipt_tampering_is_detected(preprint_case, tmp_path, name):
    ws, _, _, _, _, _ = preprint_case
    receipt, evidence, _ = receipt_case(preprint_case, tmp_path)
    record, root = preprints.record_posting(ws, receipt, evidence, confirmed=True)
    (root / "posting" / name).write_bytes(b"tampered")
    assert not preprints.check(ws, record)["valid"]


def test_rebound_artifact_hashes_cannot_hide_scientific_drift(preprint_case):
    ws, _, _, _, _, _ = preprint_case
    record, root = prepare_case(preprint_case)
    (root / "manuscript.md").write_text("Invented result: 999 measurements.", encoding="utf-8")
    record.files["manuscript.md"] = digest_file(root / "manuscript.md")
    write_json(root / "manifest.json", preprints._preparation_manifest(record))
    record.manifest_sha256 = digest_file(root / "manifest.json")
    ws.save("preprint", record)
    report = preprints.check(ws, record)
    assert not report["valid"] and any("frozen scientific manuscript" in error for error in report["errors"])


def test_active_venue_cannot_be_bypassed_and_later_attestation_revokes_other_permission(preprint_case, monkeypatch):
    ws, paper, policy, _, _, _ = preprint_case
    active = Submission(paper_id=paper.id, venue_id="another-venue", policy_id=policy.id,
                        candidate_digest=paper.freeze_digest, state=SubmissionState.AUTHOR_ATTESTED)
    record, _ = prepare_case(preprint_case)
    monkeypatch.setattr(publication, "active_for_study", lambda workspace, study_id: [active])
    report = preprints.check(ws, record)
    assert report["valid"] and not report["upload_authorized"] and report["permission_errors"]
    with pytest.raises(ValueError, match="currently active peer-reviewed venue"):
        prepare_case(preprint_case)


def test_active_venue_is_rechecked_after_conversion_before_record_is_published(preprint_case, monkeypatch):
    ws, paper, policy, _, _, _ = preprint_case
    active = Submission(paper_id=paper.id, venue_id="another-venue", policy_id=policy.id,
                        candidate_digest=paper.freeze_digest, state=SubmissionState.AUTHOR_ATTESTED)
    conversion = preprints.convert

    def racing_conversion(*args, **kwargs):
        result = conversion(*args, **kwargs)
        monkeypatch.setattr(publication, "active_for_study", lambda workspace, study_id: [active])
        return result

    monkeypatch.setattr(preprints, "convert", racing_conversion)
    with pytest.raises(ValueError, match="currently active peer-reviewed venue"):
        prepare_case(preprint_case)
    assert not ws.list("preprint", Preprint)


def test_posting_database_failure_rolls_back_artifacts_and_remains_retryable(preprint_case, tmp_path, monkeypatch):
    ws, _, _, _, _, _ = preprint_case
    record, root = prepare_case(preprint_case)
    receipt, evidence, _ = receipt_case(preprint_case, tmp_path, record)
    original = ws._database

    @contextmanager
    def failing_database():
        with original() as db:
            class Database:
                def execute(self, command, parameters=()):
                    if command.startswith("INSERT INTO records"):
                        raise sqlite3.OperationalError("Injected database failure")
                    return db.execute(command, parameters)
            yield Database()

    monkeypatch.setattr(ws, "_database", failing_database)
    with pytest.raises(ValueError, match="Injected database failure"):
        preprints.record_posting(ws, receipt, evidence, confirmed=True)
    assert not (root / "posting").exists()
    monkeypatch.setattr(ws, "_database", original)
    assert preprints.check(ws, record)["valid"]
    posted, _ = preprints.record_posting(ws, receipt, evidence, confirmed=True)
    assert preprints.check(ws, posted)["posting_recorded"]


def test_preparation_database_failure_rolls_back_published_bundle_and_can_retry(preprint_case, monkeypatch):
    ws, _, _, _, _, _ = preprint_case
    original = ws._database

    @contextmanager
    def failing_database():
        with original() as db:
            class Database:
                def execute(self, command, parameters=()):
                    if command.startswith("INSERT INTO records") and parameters[0] == "preprint":
                        raise sqlite3.OperationalError("Injected preparation persistence failure")
                    return db.execute(command, parameters)
            yield Database()

    monkeypatch.setattr(ws, "_database", failing_database)
    with pytest.raises(ValueError, match="Injected preparation persistence failure"):
        prepare_case(preprint_case)
    monkeypatch.setattr(ws, "_database", original)
    assert not ws.list("preprint", Preprint)
    assert not [path for path in ws.path("preprints").iterdir() if path.name.startswith("preprint-")]
    record, _ = prepare_case(preprint_case)
    assert preprints.check(ws, record)["upload_authorized"]


def test_invalid_receipt_dates_and_private_hosts_are_rejected(preprint_case, tmp_path):
    _, _, _, _, _, _ = preprint_case
    _, _, receipt = receipt_case(preprint_case, tmp_path)
    values = receipt.model_dump()
    for posted_at in ("2020-01-01T00:00:00", (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()):
        with pytest.raises(ValueError, match="timezone"):
            PostingReceipt.model_validate({**values, "posted_at": posted_at})
    for source_url in ("http://preprints.example.org/abs/1", "https://127.0.0.1/receipt", "https://user:secret@example.org/receipt"):
        with pytest.raises(ValueError):
            PostingReceipt.model_validate({**values, "source_url": source_url})


def test_deleted_posting_index_cannot_hide_existing_external_facts(preprint_case, tmp_path):
    ws, _, _, _, _, _ = preprint_case
    prepared, _ = prepare_case(preprint_case)
    receipt, evidence, _ = receipt_case(preprint_case, tmp_path)
    posted, _ = preprints.record_posting(ws, receipt, evidence, confirmed=True)
    with ws._database() as db:
        db.execute("DELETE FROM records WHERE kind='preprint' AND id=?", (posted.id,))
    with pytest.raises(ValueError, match="missing or orphaned"):
        preprints.audit_registry(ws)
    report = preprints.check(ws, prepared)
    assert report["valid"] and not report["upload_authorized"]
    assert any("registry audit failed" in error for error in report["permission_errors"])
    with pytest.raises(ValueError, match="missing or orphaned"):
        prepare_case(preprint_case)


def test_missing_committed_preprint_artifacts_fail_registry_audit(preprint_case):
    ws, _, _, _, _, _ = preprint_case
    record, root = prepare_case(preprint_case)
    preprints._remove_published(ws, root)
    with pytest.raises(ValueError, match="missing or orphaned"):
        preprints.audit_registry(ws)

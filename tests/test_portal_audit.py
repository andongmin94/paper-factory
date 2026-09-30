"""Regression cases for local OJS ownership and the final outbound boundary."""

import json
import html

import httpx
import pytest

from paper_factory import portal, publication, submission_package, venue_compiler
from paper_factory.integrity import frozen_workspace
from paper_factory.manuscript import Block, Document, number_text
from paper_factory.models import Claim, Submission, SubmissionState, now
from paper_factory.venues import Venue
from paper_factory.venue_policy import VenuePolicy
from paper_factory.workspace import write_json
from test_portal import Journal, deliver, final, portal_case
from test_publication import author_values
from test_submission import mock_conversion, prepared
from test_venue_policy import setup_policy


class BrokenValidation(Journal):
    def __init__(self, mode):
        super().__init__()
        self.mode = mode

    def handler(self, request):
        if request.url.path.endswith("/submit") and json.loads(request.content).get("_validateOnly"):
            self.calls.append((request.method, "/submissions/123/submit"))
            # A mismatched installation ignored _validateOnly and submitted.
            self.submission.update(submissionProgress="", dateSubmitted="2026-09-30 01:02:03")
            self.submit_count += 1
            if self.mode == "timeout":
                raise httpx.ReadTimeout("Synthetic ignored validation flag and lost response")
            return httpx.Response(200, json=self.submission)
        return super().handler(request)


@pytest.mark.parametrize("mode", ["response", "timeout"])
def test_ambiguous_validate_only_preserves_reservation_and_durable_intent(portal_case, mode):
    ws, paper, submission, plan, handler = portal_case
    journal = BrokenValidation(mode)
    reviewed = deliver(ws, plan, journal)
    with pytest.raises(portal.OJSError) as error:
        final(ws, plan, journal, handler, reviewed["review_sha256"])
    assert error.value.reconciliation_required
    assert ws.get("submission", submission.id, Submission).state == SubmissionState.AUTHOR_ATTESTED
    assert portal.check(ws, plan)["uncertain_operations"] == ["submit"]
    with pytest.raises(ValueError, match="cannot be cancelled"):
        publication.cancel_attestation(ws, submission, paper.approved_by, "The provider result must first be confirmed.")
    with journal.client(plan) as client:
        assert portal.reconcile(ws, plan, client, actor=paper.approved_by)["state"] == "SUBMITTED"
    assert journal.submit_count == 1


def test_public_inspection_uses_the_same_lock_as_portal_writes(portal_case):
    ws, _, _, plan, _ = portal_case
    journal = Journal()
    deliver(ws, plan, journal)
    count = len(journal.calls)
    with ws.lock(f"portal-{plan.id}"), journal.client(plan) as client:
        with pytest.raises(ValueError, match="Another operation"):
            portal.inspect(ws, plan, client)
    assert len(journal.calls) == count
    assert portal.check(ws, plan)["passed"]


def another_candidate(case):
    ws, paper, submission, _, handler = case
    venue = ws.get("venue", submission.venue_id, Venue)
    policy = ws.get("policy", submission.policy_id, VenuePolicy)
    current = venue_compiler.select(ws, paper, venue, policy)
    settings = ws.path(f"submissions/{submission.id}/compiled/settings.json")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        venue_compiler.compile_submission(ws, current, settings, client=client)
        submission_package.build(ws, current, client=client)
    return ws.get("submission", current.id, Submission)


@pytest.mark.parametrize("boundary", ["prepare", "adopt", "modify"])
def test_an_owned_ojs_draft_cannot_be_reused_by_another_plan(portal_case, boundary):
    ws, paper, _, owner, _ = portal_case
    journal = Journal()
    deliver(ws, owner, journal)
    candidate = another_candidate(portal_case)
    settings = owner.settings.model_copy(deep=True)
    if boundary == "prepare":
        settings.remote_submission_id = 123
        with pytest.raises(ValueError, match="already bound"):
            portal.prepare(ws, candidate, settings)
        return
    second = portal.prepare(ws, candidate, settings)
    if boundary == "adopt":
        journal.fail = "create"
        with pytest.raises(portal.OJSError):
            deliver(ws, second, journal)
        journal.fail = None
        with journal.client(second) as client:
            with pytest.raises(ValueError, match="already bound"):
                portal.reconcile(ws, second, client, actor=paper.approved_by,
                                 remote_submission_id=123, confirm=True)
    else:
        # A provider response reuses the owned ID: no metadata or file write may follow.
        with pytest.raises(ValueError, match="already bound"):
            deliver(ws, second, journal)
    assert journal.calls.count(("PUT", "/submissions/123/publications/456")) == 1
    assert journal.calls.count(("POST", "/submissions/123/files")) == 1


@pytest.mark.parametrize("kind", ["directory", "event"])
def test_orphan_portal_registry_evidence_blocks_writes_and_slot_release(portal_case, kind):
    ws, paper, submission, plan, handler = portal_case
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        publication.attest(ws, submission, author_values(), client=client)
    if kind == "directory":
        ws.path("portals/orphan-plan").mkdir()
    else:
        ws.save("portal_event", portal.PortalEvent(plan_id="missing-plan", sequence=1,
            previous_sha256=None, kind="intent", operation="submit", recorded_at=now(),
            values={}, artifact_sha256="0" * 64))
    assert not portal.check(ws, plan)["passed"]
    with pytest.raises(ValueError, match="registry|unregistered"):
        publication.cancel_attestation(ws, submission, paper.approved_by, "Unindexed evidence cannot be ignored.")


@pytest.mark.parametrize("field", ["section", "keywords"])
def test_newly_inspected_managed_metadata_still_must_match_the_approved_plan(portal_case, field):
    ws, _, _, plan, handler = portal_case
    journal = Journal()
    deliver(ws, plan, journal)
    if field == "section":
        journal.publication["sectionId"] = 99
        with journal.client(plan) as client:
            with pytest.raises(ValueError, match="section"):
                portal.inspect(ws, plan, client)
    else:
        journal.publication["keywords"]["en"] = [{"name": "Unapproved keyword"}]
        with journal.client(plan) as client:
            reviewed = portal.inspect(ws, plan, client)
        with pytest.raises(ValueError, match="keywords"):
            final(ws, plan, journal, handler, reviewed["review_sha256"])
    assert journal.submit_count == 0


def test_remote_review_material_is_reread_after_policy_and_author_verification(portal_case, monkeypatch):
    ws, paper, submission, plan, handler = portal_case
    journal = Journal()
    reviewed = deliver(ws, plan, journal)
    actual_attest = publication.attest

    def changed_during_verification(*args, **kwargs):
        result = actual_attest(*args, **kwargs)
        journal.authors[0]["affiliations"][0]["name"]["en"] = "Changed after official-policy verification"
        return result

    monkeypatch.setattr(publication, "attest", changed_during_verification)
    with pytest.raises(ValueError, match="changed during"):
        final(ws, plan, journal, handler, reviewed["review_sha256"])
    assert journal.submit_count == 0
    assert ws.get("submission", submission.id, Submission).state == SubmissionState.AUTHOR_ATTESTED
    assert not portal.check(ws, plan)["final_submit_attempted"]
    publication.cancel_attestation(ws, submission, paper.approved_by, "Remote review material changed before any final request.")


def test_review_digest_ignores_nested_housekeeping_but_retains_publication_facts():
    material = {"submission": {"id": 123, "dateSubmitted": None, "lastModified": "old"},
        "publication": {"title": {"en": "Approved title"}, "_href": "old-link"},
        "contributors": {"items": [{"email": "author@example.org", "_href": "old-contributor-link"}]},
        "files": {"items": [{"id": 15, "lastModified": "old"}]}}
    before = portal._review_digest(material)
    material["publication"]["_href"] = "new-link"
    material["contributors"]["items"][0]["_href"] = "new-contributor-link"
    material["files"]["items"][0]["lastModified"] = "new"
    material["submission"]["lastModified"] = "new"
    assert portal._review_digest(material) == before
    material["contributors"]["items"][0]["email"] = "other@example.org"
    assert portal._review_digest(material) != before
    material["contributors"]["items"][0]["email"] = "author@example.org"
    material["submission"]["dateSubmitted"] = "2026-09-30 01:02:03"
    assert portal._review_digest(material) != before


def test_blind_portal_metadata_uses_the_same_identity_redaction_as_the_manuscript(portal_case):
    ws, paper, _, plan, _ = portal_case
    canonical = ws.path(f"freezes/{paper.id}/canonical.json").read_bytes()
    assert b"Fixture *University*" in canonical
    metadata = plan.metadata.model_dump_json()
    assert "[redacted for review]" in metadata
    assert "Fixture *University*" not in metadata and "Fixture [Author]" not in metadata
    journal = Journal()
    deliver(ws, plan, journal)
    exported = json.dumps({key: journal.publication[key] for key in ("title", "abstract", "keywords")})
    assert "Fixture *University*" not in exported and "Fixture [Author]" not in exported
    assert ws.path(f"freezes/{paper.id}/canonical.json").read_bytes() == canonical


def test_html_abstract_keeps_literal_prose_and_verified_numbers_without_markdown(portal_case):
    ws, paper, _, plan, _ = portal_case
    snapshot = frozen_workspace(ws, paper)
    doc = Document.model_validate_json(snapshot.path("canonical.json").read_bytes())
    abstract = next(section for section in doc.sections if section.heading == "Abstract")
    abstract.blocks.insert(0, Block(kind="prose", text="A < B & C > D; <script>literal content</script>; author's quoted \"prose\"."))
    result = portal._abstract(doc, snapshot, anonymized=True)
    assert "A &lt; B &amp; C &gt; D" in result and "&lt;script&gt;literal content&lt;/script&gt;" in result
    assert "<script>" not in result and "**" not in result and "[Evidence:" not in result
    assert "author's quoted \"prose\"" in result
    doc.title = "A < B & C > D: author's \"title\""
    assert portal._review_html(doc.title, doc, anonymized=True) == "A &lt; B &amp; C &gt; D: author's \"title\""
    claim = snapshot.get("claim", next(block.ref for block in abstract.blocks if block.kind == "claim"), Claim)
    assert number_text(claim.value) in html.unescape(result)
    assert "**" not in plan.metadata.abstract["en"] and "[Evidence:" not in plan.metadata.abstract["en"]


@pytest.mark.parametrize("after_commit", [False, True])
def test_portal_plan_commit_outcome_is_retryable_or_preserves_the_committed_plan(portal_case, fail_transaction, after_commit):
    ws, _, _, first, _ = portal_case
    candidate = another_candidate(portal_case)
    fail_transaction(ws, "portal_plan", after_commit=after_commit)
    with pytest.raises(OSError, match="Injected"):
        portal.prepare(ws, candidate, first.settings)
    plans = [plan for plan in ws.list("portal_plan", portal.StoredPlan) if plan.submission_id == candidate.id]
    if after_commit:
        assert len(plans) == 1 and portal.check(ws, plans[0])["passed"]
        with pytest.raises(ValueError, match="already has a portal plan"):
            portal.prepare(ws, candidate, first.settings)
    else:
        assert not plans
        assert {path.name for path in ws.path("portals").iterdir()} == {first.id}
        assert portal.check(ws, portal.prepare(ws, candidate, first.settings))["passed"]


def fail_success_save(ws, monkeypatch, operation, after_commit):
    original = ws.save
    armed = True

    def save(kind, record):
        nonlocal armed
        if armed and kind == "portal_event" and record.kind == "success" and record.operation == operation:
            armed = False
            if after_commit:
                original(kind, record)
            raise OSError("Injected local receipt save failure")
        return original(kind, record)

    monkeypatch.setattr(ws, "save", save)


@pytest.mark.parametrize("after_commit", [False, True])
@pytest.mark.parametrize("operation", ["upload:manuscript.pdf", "submit"])
def test_local_receipt_recovery_never_repeats_remote_upload_or_final_submit(portal_case, monkeypatch, operation, after_commit):
    ws, paper, _, plan, handler = portal_case
    journal = Journal()
    if operation == "submit":
        reviewed = deliver(ws, plan, journal)
    fail_success_save(ws, monkeypatch, operation, after_commit)
    with pytest.raises(OSError, match="local receipt save"):
        if operation == "submit":
            final(ws, plan, journal, handler, reviewed["review_sha256"])
        else:
            deliver(ws, plan, journal)
    if not after_commit:
        assert not portal.check(ws, plan)["passed"]
        requests = len(journal.calls)
        with pytest.raises(ValueError, match="explicit author confirmation"):
            portal.recover_local_events(ws, plan, actor=paper.approved_by)
        assert len(journal.calls) == requests
    with journal.client(plan) as client:
        report = portal.reconcile(ws, plan, client, actor=paper.approved_by,
                                  recover_local=True, confirm=True)
    assert report["state"] == ("SUBMITTED" if operation == "submit" else "DRAFT")
    assert portal.check(ws, plan)["passed"]
    assert portal.recover_local_events(ws, plan, actor=paper.approved_by, confirmed=True) == []
    if operation != "submit":
        deliver(ws, plan, journal)
    assert journal.calls.count(("POST", "/submissions/123/files")) == 1
    assert journal.submit_count == (1 if operation == "submit" else 0)


@pytest.mark.parametrize("mutation", ["operation", "upload_sha", "previous", "canonical"])
def test_local_recovery_rejects_rebound_unrelated_or_noncanonical_receipts(portal_case, monkeypatch, mutation):
    ws, paper, _, plan, _ = portal_case
    journal = Journal()
    fail_success_save(ws, monkeypatch, "upload:manuscript.pdf", False)
    with pytest.raises(OSError):
        deliver(ws, plan, journal)
    root = ws.path(f"portals/{plan.id}")
    indexed = {event.id for event in ws.list("portal_event", portal.PortalEvent)}
    path = next(path for path in root.glob("*.json") if path.name != "plan.json" and json.loads(path.read_bytes())["id"] not in indexed)
    data = json.loads(path.read_bytes())
    if mutation == "canonical":
        path.write_bytes(path.read_bytes() + b" ")
    else:
        if mutation == "operation":
            data["operation"] = "metadata"
        elif mutation == "upload_sha":
            data["values"]["receipt"]["upload_sha256"] = "0" * 64
        else:
            data["previous_sha256"] = "0" * 64
        write_json(path, data)
    before = ws.list("portal_event", portal.PortalEvent)
    requests = len(journal.calls)
    with pytest.raises(ValueError, match="Preserved portal evidence"):
        portal.recover_local_events(ws, plan, actor=paper.approved_by, confirmed=True)
    assert ws.list("portal_event", portal.PortalEvent) == before
    assert path.is_file() and len(journal.calls) == requests


def test_recovered_draft_adoption_settles_creation_without_a_second_create(portal_case, monkeypatch):
    ws, paper, _, plan, _ = portal_case
    journal = Journal()
    journal.fail = "create"
    with pytest.raises(portal.OJSError):
        deliver(ws, plan, journal)
    original = ws.save
    armed = True

    def interrupted_adoption(kind, record):
        nonlocal armed
        if armed and kind == "portal_event" and record.kind == "reconciliation" and record.operation == "attach":
            armed = False
            raise OSError("Interrupted local adoption receipt save")
        return original(kind, record)

    monkeypatch.setattr(ws, "save", interrupted_adoption)
    journal.fail = None
    with journal.client(plan) as client:
        with pytest.raises(OSError, match="Interrupted"):
            portal.reconcile(ws, plan, client, actor=paper.approved_by, remote_submission_id=123, confirm=True)
        report = portal.reconcile(ws, plan, client, actor=paper.approved_by, recover_local=True, confirm=True)
    assert report["state"] == "DRAFT" and not portal.check(ws, plan)["uncertain_operations"]
    deliver(ws, plan, journal)
    assert journal.calls.count(("POST", "/submissions")) == 1


def test_preserved_inspection_is_recovered_without_repeating_remote_requests(portal_case, monkeypatch):
    ws, paper, _, plan, _ = portal_case
    journal = Journal()
    original = ws.save
    armed = True

    def interrupted_inspection(kind, record):
        nonlocal armed
        if armed and kind == "portal_event" and record.kind == "inspection":
            armed = False
            raise OSError("Interrupted local inspection save")
        return original(kind, record)

    monkeypatch.setattr(ws, "save", interrupted_inspection)
    with pytest.raises(OSError, match="Interrupted"):
        deliver(ws, plan, journal)
    requests = len(journal.calls)
    recovered = portal.recover_local_events(ws, plan, actor=paper.approved_by, confirmed=True)
    assert len(recovered) == 1 and recovered[0].kind == "inspection"
    assert len(journal.calls) == requests and portal.check(ws, plan)["passed"]

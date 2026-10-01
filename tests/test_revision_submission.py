from concurrent.futures import ThreadPoolExecutor
import json
import zipfile

import httpx
import pytest

from paper_factory import evidence, experiments, integrity, manuscript, preprints, publication, research, revision_submission, revisions, submission_package, venue_compiler
from paper_factory.manuscript import Block, Document
from paper_factory.models import ExperimentManifest, Paper, Submission, SubmissionState, now, uid
from paper_factory.publication import ReceiptInput
from paper_factory.revision_submission import RevisionDelivery
from paper_factory.revisions import ReviewComment, ReviewSpec, SectionEdit
from paper_factory.venue_policy import VenuePolicy
from paper_factory.workspace import digest_file, write_json
from test_publication import author_values, attest, ready_case, receipt
from test_manuscript import mocked_search
from test_submission import compile_case, mock_conversion, prepared
from test_venue_policy import setup_policy


def revision_case(prepared, tmp_path, *, submission=None, handler=None, approve=True,
                  additional_evidence=False, blind=False, receipt_url=None):
    later_round = submission is not None
    if submission is None:
        if blind:
            ws, base, submission, _, handler = compile_case(prepared, blind=True)
            with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                package, _ = submission_package.build(ws, submission, client=client)
            assert package.ready
            submission = ws.get("submission", submission.id, Submission)
        else:
            ws, base, submission, handler = ready_case(prepared)
        attest(ws, submission, handler)
        for state in (SubmissionState.SUBMITTED, SubmissionState.UNDER_REVIEW):
            receipt(ws, submission, state, tmp_path)
    else:
        ws = prepared[0]
        base = ws.get("paper", submission.paper_id, Paper)
    receipt(ws, submission, SubmissionState.REVISION, tmp_path,
        **({"external_url": receipt_url} if receipt_url else {}))
    excerpt = "Please clarify the analysis method."
    spec = ReviewSpec(reviewed_by=base.approved_by,
        comments=[ReviewComment(id="comment-method", excerpt=excerpt, sections=["Method"])])
    spec_path = tmp_path / "review.json"
    report_path = tmp_path / "referee.txt"
    write_json(spec_path, spec)
    report_path.write_text("Synthetic referee report. " + excerpt, encoding="utf-8")
    revision, _ = revisions.import_review(ws, submission, spec_path, report_path, confirmed=True)
    revisions.draft(ws, revision)
    plan = revisions.plan_template(ws, revision)
    response = plan.responses[0]
    response.disposition = "accept"
    response.reply = "The analysis method now clarifies how the registered inspection is performed."
    response.edits = [SectionEdit(section="Method", blocks=[Block(kind="prose",
        text="The analysis follows the registered descriptive inspection protocol and retains its source evidence."
            + (" The procedure records the methodological assumptions." if later_round else ""))])]
    if additional_evidence:
        source = ws.list("manifest", ExperimentManifest)[0]
        added = source.model_copy(update={"id": uid("experiment"), "command": ["{python}", "-c",
            "import json; from pathlib import Path; p=Path('.paperfactory-results/inventory.json'); p.parent.mkdir(); p.write_text(json.dumps({'file_count':42,'total_bytes':84}))"]})
        ws.save("manifest", added)
        write_json(ws.path(f"experiments/{added.id}.json"), added)
        run = experiments.run_experiment(ws, added)
        assert run.status == "SUCCEEDED"
        claims = evidence.claims_for_run(ws, run)
        doc = Document.model_validate_json(ws.path(f"manuscripts/{revision.revised_paper_id}/canonical.json").read_bytes())
        for heading in ("Abstract", "Results"):
            section = next(section for section in doc.sections if section.heading == heading)
            response.sections.append(heading)
            response.edits.append(SectionEdit(section=heading, blocks=[*section.blocks,
                *[Block(kind="claim", ref=claim.id) for claim in claims]]))
        response.claim_ids = [claim.id for claim in claims]
        response.experiment_ids = [added.id]
        response.run_ids = [run.id]
        response.additional_experiments_required = True
    plan_path = tmp_path / "response-plan.json"
    write_json(plan_path, plan)
    child, _ = revisions.apply_plan(ws, revision, plan_path)
    response_build, _ = revisions.build_response(ws, revision, plan_path)
    assert response_build.ready, response_build.errors
    if approve:
        integrity.approve(ws, child, approved=True,
            assessment="The revised scientific content, related metadata and limitations were reviewed.")
    return ws, base, submission, handler, revision, response_build, child


def delivery_case(prepared, tmp_path, *, additional_evidence=False, blind=False):
    values = revision_case(prepared, tmp_path, additional_evidence=additional_evidence, blind=blind)
    ws, _, _, handler, revision, response, _ = values
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        delivery, root = revision_submission.prepare(ws, revision, prepared[3], response=response, client=client)
    return (*values, delivery, root)


@pytest.mark.parametrize("after_commit", [False, True])
def test_delivery_commit_outcome_preserves_or_removes_only_owned_artifacts(
    prepared, mock_conversion, tmp_path, fail_transaction, after_commit
):
    ws, base, original, handler, revision, response, _ = revision_case(prepared, tmp_path)
    base_digest = digest_file(ws.path(f"freezes/{base.id}/canonical.json"))
    fail_transaction(ws, "revision_delivery", after_commit=after_commit)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OSError, match="Injected"):
            revision_submission.prepare(ws, revision, prepared[3], response=response, client=client)

    deliveries = ws.list("revision_delivery", RevisionDelivery)
    assert len(deliveries) == int(after_commit)
    assert digest_file(ws.path(f"freezes/{base.id}/canonical.json")) == base_digest
    assert ws.get("submission", original.id, Submission).state == SubmissionState.REVISION
    assert {path.name for path in ws.path("revision-deliveries").iterdir()} == {item.id for item in deliveries}
    if after_commit:
        assert revision_submission.check(ws, deliveries[0])["passed"]
    assert publication.check(ws, original)["passed"]


def attest_delivery(ws, delivery, handler):
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        return revision_submission.attest(ws, delivery, author_values(), client=client)


def revision_receipt(ws, delivery, tmp_path, **changes):
    fields = dict(target_state=SubmissionState.UNDER_REVIEW, external_id="FIXTURE-JOURNAL-123",
        external_url="https://submit.example.org/manuscript/123", occurred_at=now(),
        verified_by="Fixture [Author]", note="Synthetic fixture confirming the revised journal manuscript was resubmitted.")
    fields.update(changes)
    source = tmp_path / "revision-receipt.txt"
    source.write_text("Synthetic test confirmation: " + json.dumps(fields), encoding="utf-8")
    return revision_submission.record(ws, delivery, ReceiptInput(**fields), source)


def test_preparation_keeps_original_active_and_preserves_original_freeze_and_package(prepared, mock_conversion, tmp_path):
    ws, base, original, handler, revision, response, child, delivery, root = delivery_case(prepared, tmp_path)
    assert revision.base_paper_id == base.id and child.id != base.id
    assert child.study_id == base.study_id
    assert delivery.original_submission_id == original.id
    assert ws.get("submission", original.id, Submission).state == SubmissionState.REVISION
    assert publication.active_for_study(ws, base.study_id)[0].id == original.id
    assert digest_file(root / "submission.zip") == delivery.archive_sha256
    assert (root / "response" / "letter.md").is_file()
    assert submission_package.verify(ws, original)["ready"]
    report = revision_submission.check(ws, delivery)
    assert report["passed"] and report["local_review_bundle_ready"]
    assert not report["revision_portal_requirements_verified"]
    assert not report["automatic_external_submission_performed"]
    candidate = ws.get("submission", delivery.candidate_id, Submission)
    with pytest.raises(ValueError, match="same-journal revision delivery"):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            publication.attest(ws, candidate, author_values(), client=client)


def test_ready_response_does_not_replace_separate_revised_scientific_approval(prepared, mock_conversion, tmp_path):
    ws, _, _, handler, revision, response, _ = revision_case(prepared, tmp_path, approve=False)
    with pytest.raises(ValueError, match="scientific author approval"):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            revision_submission.prepare(ws, revision, prepared[3], response=response, client=client)
    assert not ws.list("revision_delivery", RevisionDelivery)


def test_blinded_journal_gets_separate_anonymized_response_exports(prepared, mock_conversion, tmp_path, monkeypatch):
    original_convert = venue_compiler.convert

    def with_intermediates(markdown, output, **kwargs):
        result = original_convert(markdown, output, **kwargs)
        if output.name == "letter.pdf":
            output.with_suffix(".typ").write_text("Synthetic Typst intermediate", encoding="utf-8")
            output.with_name("letter-pandoc-metadata.json").write_text("{}", encoding="utf-8")
        return result

    monkeypatch.setattr(venue_compiler, "convert", with_intermediates)
    ws, _, _, handler, _, _, child, delivery, root = delivery_case(prepared, tmp_path, blind=True)
    doc = Document.model_validate_json(ws.path(f"freezes/{child.id}/canonical.json").read_bytes())
    assert venue_compiler._contains_identity((root / "response" / "letter.md").read_text(encoding="utf-8"), doc)
    for suffix in ("md", "pdf"):
        assert not venue_compiler._contains_identity((root / "reviewer-response" / f"letter.{suffix}").read_text(encoding="utf-8"), doc)
    assert not venue_compiler._review_identification_errors(root / "reviewer-response", doc, stem="letter")
    assert not (root / "reviewer-response" / "letter.typ").exists()
    assert not (root / "reviewer-response" / "letter-pandoc-metadata.json").exists()
    guide = json.loads((root / "delivery-readme.json").read_bytes())
    assert guide["anonymized"]
    assert "response/plan.json" in guide["administrative_response_files"]
    assert "response/letter.md" in guide["administrative_response_files"]
    assert guide["reviewer_response_files"] == [f"reviewer-response/letter.{suffix}" for suffix in ("md", "pdf", "docx")]
    assert revision_submission.check(ws, delivery)["passed"]
    attest_delivery(ws, delivery, handler)
    revision_receipt(ws, delivery, tmp_path)
    assert revision_submission.check(ws, delivery)["passed"]


def test_identifying_export_metadata_blocks_blinded_revision_delivery(prepared, mock_conversion, tmp_path, monkeypatch):
    ws, _, original, handler, revision, response, _ = revision_case(prepared, tmp_path, blind=True)
    original_convert = venue_compiler.convert

    def identifying_metadata(markdown, output, **kwargs):
        result = original_convert(markdown, output, **kwargs)
        if output.name == "letter.docx":
            with zipfile.ZipFile(output) as archive:
                contents = {name: archive.read(name) for name in archive.namelist()}
            contents["docProps/core.xml"] = b"<core>Fixture [Author]</core>"
            with zipfile.ZipFile(output, "w") as archive:
                for name, content in contents.items():
                    archive.writestr(name, content)
        return result

    monkeypatch.setattr(venue_compiler, "convert", identifying_metadata)
    with pytest.raises(ValueError, match="identifying content"):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            revision_submission.prepare(ws, revision, prepared[3], response=response, client=client)
    assert not ws.list("revision_delivery", RevisionDelivery)
    assert ws.get("submission", original.id, Submission).state == SubmissionState.REVISION


def test_revised_journal_policy_can_be_explicitly_reviewed_without_mutating_initial_policy(prepared, mock_conversion, tmp_path):
    ws, _, original, _, revision, response, child = revision_case(prepared, tmp_path)
    initial_policy = original.policy_id
    revised_policy, handler = prepared[4](blind=True,
        changes={"submission_url": "https://new-submit.example.org/manuscript"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        delivery, root = revision_submission.prepare(ws, revision, prepared[3], response=response,
            policy=revised_policy, client=client)
    assert json.loads((root / "delivery-readme.json").read_bytes())["anonymized"]
    assert ws.get("submission", original.id, Submission).policy_id == initial_policy
    attest_delivery(ws, delivery, handler)
    revision_receipt(ws, delivery, tmp_path, external_url="https://new-submit.example.org/manuscript/123")
    _, _, _, _, later_revision, later_response, child = revision_case(prepared, tmp_path,
        submission=original, handler=handler, receipt_url="https://new-submit.example.org/manuscript/123")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        delivery, root = revision_submission.prepare(ws, later_revision, prepared[3],
            response=later_response, client=client)
    assert json.loads((root / "delivery-readme.json").read_bytes())["anonymized"]
    attest_delivery(ws, delivery, handler)
    revision_receipt(ws, delivery, tmp_path, external_url="https://new-submit.example.org/manuscript/123")
    receipt(ws, original, SubmissionState.ACCEPTED, tmp_path,
        external_url="https://new-submit.example.org/manuscript/123")
    assert publication.check(ws, original)["passed"]
    candidate = ws.get("submission", delivery.candidate_id, Submission)
    assert preprints._active_venue_errors(ws, child, ws.get("policy", candidate.policy_id, VenuePolicy)) == []
    assert preprints._active_venue_errors(ws, child, ws.get("policy", initial_policy, VenuePolicy))


def test_explicit_revised_policy_cannot_change_journal(prepared, mock_conversion, tmp_path):
    ws, _, _, handler, revision, response, _ = revision_case(prepared, tmp_path)
    policy, _ = prepared[4]()
    policy = policy.model_copy(update={"id": uid("policy"), "venue_id": uid("venue")})
    ws.save("policy", policy)
    with pytest.raises(ValueError, match="original journal"):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            revision_submission.prepare(ws, revision, prepared[3], response=response, policy=policy, client=client)
    assert not ws.list("revision_delivery", RevisionDelivery)


def test_revised_attestation_and_same_journal_receipt_advance_only_original_submission(prepared, mock_conversion, tmp_path):
    ws, base, original, handler, _, _, child, delivery, _ = delivery_case(prepared, tmp_path)
    original_before = ws.get("submission", original.id, Submission)
    freeze = base.freeze_digest
    with pytest.raises(ValueError, match="separate final revised author attestation"):
        revision_receipt(ws, delivery, tmp_path)
    author_event = attest_delivery(ws, delivery, handler)
    assert author_event.values.actor == child.approved_by
    assert ws.get("submission", original.id, Submission).state == SubmissionState.REVISION
    event = revision_receipt(ws, delivery, tmp_path)
    assert event.kind == "revision_submission" and event.paper_id == base.id
    assert event.values["receipt"]["external_id"] == delivery.external_id
    current = ws.get("submission", original.id, Submission)
    assert current.state == SubmissionState.UNDER_REVIEW
    assert current.paper_id == original_before.paper_id and current.package_digest == original_before.package_digest
    assert ws.get("paper", base.id, Paper).freeze_digest == freeze
    assert ws.get("submission", delivery.candidate_id, Submission).state == SubmissionState.SUBMISSION_READY
    assert revision_submission.check(ws, delivery)["resubmission_recorded"]
    assert publication.check(ws, original)["passed"]
    assert len(publication.active_for_study(ws, base.study_id)) == 1


@pytest.mark.parametrize("change,expected", [
    ({"external_id": "DIFFERENT-MANUSCRIPT"}, "manuscript/package binding"),
    ({"verified_by": "Unapproved Person"}, "manuscript/package binding"),
    ({"external_url": "https://other.example.org/receipt"}, "verified submission service"),
    ({"occurred_at": "2000-01-01T00:00:00+00:00"}, "chronology moved backwards"),
])
def test_wrong_revised_receipt_keeps_original_revision_slot(prepared, mock_conversion, tmp_path, change, expected):
    ws, base, original, handler, _, _, _, delivery, _ = delivery_case(prepared, tmp_path)
    attest_delivery(ws, delivery, handler)
    with pytest.raises(ValueError, match=expected):
        revision_receipt(ws, delivery, tmp_path, **change)
    assert publication.check(ws, original)["state"] == SubmissionState.REVISION
    assert publication.active_for_study(ws, base.study_id)[0].id == original.id
    assert revision_submission.check(ws, delivery)["passed"]


def test_fresh_policy_change_blocks_revised_attestation(prepared, mock_conversion, tmp_path):
    ws, _, original, _, _, _, _, delivery, _ = delivery_case(prepared, tmp_path)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200,
            text="<p>Changed policy requirements</p>", headers={"content-type": "text/html"}))) as client:
        with pytest.raises(ValueError, match="official policy changed"):
            revision_submission.attest(ws, delivery, author_values(), client=client)
    assert ws.get("revision_delivery", delivery.id, RevisionDelivery).state == "PREPARED"
    assert ws.get("submission", original.id, Submission).state == SubmissionState.REVISION


@pytest.mark.parametrize("boundary", ["attest", "record"])
def test_orphaned_delivery_evidence_blocks_mutations(prepared, mock_conversion, tmp_path, boundary):
    ws, _, original, handler, _, _, _, delivery, _ = delivery_case(prepared, tmp_path)
    if boundary == "record":
        attest_delivery(ws, delivery, handler)
    orphan = ws.path("revision-deliveries/orphaned-delivery")
    orphan.mkdir()
    (orphan / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="registry and artifacts differ"):
        if boundary == "attest":
            attest_delivery(ws, delivery, handler)
        else:
            revision_receipt(ws, delivery, tmp_path)
    assert ws.get("submission", original.id, Submission).state == SubmissionState.REVISION


def test_failed_revised_attestation_update_preserves_prepared_bundle(prepared, mock_conversion, tmp_path):
    ws, _, original, handler, _, _, _, delivery, root = delivery_case(prepared, tmp_path)
    with ws._database() as db:
        db.execute("CREATE TRIGGER fail_attestation BEFORE UPDATE ON records WHEN NEW.kind='revision_delivery' BEGIN SELECT RAISE(ABORT,'fixture attestation failure'); END")
    with pytest.raises(ValueError, match="fixture attestation failure"):
        attest_delivery(ws, delivery, handler)
    assert not (root / "attestation.json").exists()
    assert ws.get("revision_delivery", delivery.id, RevisionDelivery).state == "PREPARED"
    assert revision_submission.check(ws, delivery)["passed"]
    assert ws.get("submission", original.id, Submission).state == SubmissionState.REVISION


@pytest.mark.parametrize("artifact", ["manifest.json", "submission.zip", "response/letter.md", "attestation.json"])
def test_changed_delivery_blocks_confirmation_and_preserves_slot(prepared, mock_conversion, tmp_path, artifact):
    ws, _, original, handler, _, _, _, delivery, root = delivery_case(prepared, tmp_path)
    attest_delivery(ws, delivery, handler)
    (root / artifact).write_bytes(b"changed")
    assert not revision_submission.check(ws, delivery)["passed"]
    with pytest.raises(ValueError):
        revision_receipt(ws, delivery, tmp_path)
    assert ws.get("submission", original.id, Submission).state == SubmissionState.REVISION


@pytest.mark.parametrize("attack", ["response", "delivery_state"])
def test_historical_revised_response_damage_fails_publication_audit(prepared, mock_conversion, tmp_path, attack):
    ws, _, original, handler, _, _, _, delivery, root = delivery_case(prepared, tmp_path)
    attest_delivery(ws, delivery, handler)
    revision_receipt(ws, delivery, tmp_path)
    if attack == "response":
        (root / "response" / "letter.md").write_text("Changed response", encoding="utf-8")
    else:
        changed = ws.get("revision_delivery", delivery.id, RevisionDelivery)
        changed.state = "AUTHOR_ATTESTED"
        changed.publication_event_id = None
        ws.save("revision_delivery", changed)
    assert not publication.check(ws, original)["passed"]
    assert not revision_submission.check(ws, delivery)["passed"]


def test_rejection_before_resubmission_keeps_candidate_out_of_ordinary_submission_flow(prepared, mock_conversion, tmp_path):
    ws, _, original, handler, _, _, _, delivery, _ = delivery_case(prepared, tmp_path)
    attest_delivery(ws, delivery, handler)
    receipt(ws, original, SubmissionState.REJECTED, tmp_path)
    with pytest.raises(ValueError, match="current journal revision decision"):
        revision_receipt(ws, delivery, tmp_path)
    candidate = ws.get("submission", delivery.candidate_id, Submission)
    with pytest.raises(ValueError, match="same-journal revision delivery"):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            publication.attest(ws, candidate, author_values(), client=client)


def test_duplicate_revision_confirmation_is_atomic(prepared, mock_conversion, tmp_path):
    ws, base, original, handler, _, _, _, delivery, _ = delivery_case(prepared, tmp_path)
    attest_delivery(ws, delivery, handler)
    values = ReceiptInput(target_state=SubmissionState.UNDER_REVIEW, external_id=delivery.external_id,
        external_url="https://submit.example.org/manuscript/123", occurred_at=now(), verified_by=base.approved_by,
        note="Synthetic fixture receipt confirms this same-journal revised manuscript.")
    path = tmp_path / "concurrent-confirmation.txt"
    path.write_text("Synthetic confirmed revised submission", encoding="utf-8")

    def confirm():
        try:
            revision_submission.record(ws, delivery, values, path)
            return "recorded"
        except ValueError as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: confirm(), range(2)))
    assert outcomes.count("recorded") == 1
    assert publication.check(ws, original)["passed"]
    assert ws.get("revision_delivery", delivery.id, RevisionDelivery).state == "RESUBMITTED"


def test_failed_delivery_db_update_rolls_back_publication_event(prepared, mock_conversion, tmp_path):
    ws, _, original, handler, _, _, _, delivery, _ = delivery_case(prepared, tmp_path)
    attest_delivery(ws, delivery, handler)
    before = len(publication.check(ws, original)["events"])
    with ws._database() as db:
        db.execute("CREATE TRIGGER fail_revision BEFORE UPDATE ON records WHEN NEW.kind='revision_delivery' BEGIN SELECT RAISE(ABORT,'fixture write failure'); END")
    with pytest.raises(ValueError, match="fixture write failure"):
        revision_receipt(ws, delivery, tmp_path)
    assert len(publication.check(ws, original)["events"]) == before
    assert ws.get("submission", original.id, Submission).state == SubmissionState.REVISION
    assert ws.get("revision_delivery", delivery.id, RevisionDelivery).state == "AUTHOR_ATTESTED"
    assert revision_submission.check(ws, delivery)["passed"]


def test_later_round_uses_previous_revised_freeze_without_changing_original_binding(prepared, mock_conversion, tmp_path):
    ws, initial, original, handler, _, _, first_child, delivery, _ = delivery_case(prepared, tmp_path)
    attest_delivery(ws, delivery, handler)
    revision_receipt(ws, delivery, tmp_path)
    ws, _, _, _, revision, response, second_child = revision_case(prepared, tmp_path,
        submission=original, handler=handler)
    assert revision.base_paper_id == first_child.id
    assert revision.base_freeze_digest == ws.get("paper", first_child.id, Paper).freeze_digest
    assert second_child.id not in {initial.id, first_child.id}
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        second_delivery, _ = revision_submission.prepare(ws, revision, prepared[3], response=response, client=client)
    attest_delivery(ws, second_delivery, handler)
    revision_receipt(ws, second_delivery, tmp_path)
    assert publication.check(ws, original)["passed"]
    assert ws.get("submission", original.id, Submission).paper_id == initial.id
    assert len(publication.active_for_study(ws, initial.study_id)) == 1


@pytest.mark.parametrize("other_state", ["before_revision_attestation", "after_revision_attestation", "after_revision_receipt"])
def test_revision_only_evidence_participates_in_overlap_guard_in_both_directions(prepared, mock_conversion, tmp_path, other_state):
    ws, initial, original, handler, revision, response, child, delivery, _ = delivery_case(prepared, tmp_path,
        additional_evidence=True)
    new_claims = set(child.claim_ids) - set(initial.claim_ids)
    assert new_claims
    study = research.create_study(ws, question="Which source measurements follow the independent revision fixture protocol?",
        title="Independent revision fixture study")
    mocked_search(ws, study)
    response_plan = json.loads(ws.path(f"revisions/{revision.id}/responses/{response.id}/plan.json").read_bytes())
    added_id = response_plan["responses"][0]["experiment_ids"][0]
    added = ws.get("manifest", added_id, ExperimentManifest)
    copied = added.model_copy(update={"id": uid("experiment"), "study_id": study.id})
    ws.save("manifest", copied)
    write_json(ws.path(f"experiments/{copied.id}.json"), copied)
    assert experiments.run_experiment(ws, copied).status == "SUCCEEDED"
    other, _ = manuscript.build(ws, study)
    integrity.approve(ws, other, approved=True,
        assessment="Synthetic independent fixture evidence and related-work metadata were reviewed.")
    policy, active = prepared[4]()
    candidate = venue_compiler.select(ws, other, prepared[1], policy)
    with httpx.Client(transport=httpx.MockTransport(active)) as client:
        candidate, _ = venue_compiler.compile_submission(ws, candidate, prepared[3], client=client)
        package, _ = submission_package.build(ws, candidate, client=client)
    assert package.ready
    if other_state == "before_revision_attestation":
        attest(ws, candidate, active)
        with pytest.raises(ValueError, match="Approved evidence overlaps"):
            attest_delivery(ws, delivery, handler)
    else:
        attest_delivery(ws, delivery, handler)
        if other_state == "after_revision_receipt":
            revision_receipt(ws, delivery, tmp_path)
        with pytest.raises(ValueError, match="Approved evidence overlaps"):
            attest(ws, candidate, active)
    assert publication.check(ws, original)["passed"]

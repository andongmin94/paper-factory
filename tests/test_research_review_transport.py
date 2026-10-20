"""Review identity/locator transport never changes an independent judgment."""
from copy import deepcopy
import hashlib
import pytest

from paper_factory.autonomous.research_development import canonical_review_transport
from paper_factory.autonomous.manuscript_improvement import CRITERIA


def fixture():
    markdowns = {venue: "A frozen opening. Finally, latest-state semantics cannot override revocation. A different exact closing."
                 for venue in ("ieee-software", "ieee-security-privacy")}
    targets = {venue: {"markdown_sha256": hashlib.sha256(text.encode()).hexdigest(), "draft_sha256": str(index + 1) * 64}
               for index, (venue, text) in enumerate(markdowns.items())}
    assessments = [{"venue_id": venue, "manuscript_sha256": targets[venue]["draft_sha256"],
        "scores": [{"criterion": criterion, "score": 7, "uncertainty": "high", "passages": ["A different exact closing."],
            "reason": "This synthetic independent assessment is not a publication recommendation.", "required_improvement": "Add adequate actual evidence rather than inflate the result."} for criterion in CRITERIA],
        "essential_errors": ["This is an explicitly synthetic independent assessment only."],
        "recommendation": "revise_before_submission", "recommendation_reason": "No actual publication merit is asserted by this controller fixture.", "evidence_limits": []}
        for venue in markdowns]
    assessments[1]["scores"][4]["passages"] = ["Latest-state semantics cannot override revocation."]
    return {"assessments": assessments}, targets, markdowns


def test_exact_current_draft_and_unique_locator_restore_entire_original_object():
    value, targets, markdowns = fixture()
    original = deepcopy((value, targets, markdowns))
    normalized, proof = canonical_review_transport(value, targets, markdowns)
    restored = deepcopy(normalized)
    for edit in reversed(proof["edits"]):
        row = restored
        for key in edit["path"][:-1]:row = row[key]
        row[edit["path"][-1]] = edit["before"]
    assert restored == value and proof["restores_original_response_exactly"]
    assert proof["original_response_object_sha256"] == proof["restored_response_object_sha256"]
    assert len(proof["edits"]) == 3
    for before, after in zip(value["assessments"], normalized["assessments"]):
        assert before["recommendation"] == after["recommendation"]
        assert before["essential_errors"] == after["essential_errors"]
        for old, new in zip(before["scores"], after["scores"]):
            assert {key: value for key, value in old.items() if key != "passages"} == {key: value for key, value in new.items() if key != "passages"}
            assert all(passage in markdowns[after["venue_id"]] for passage in new["passages"])
    assert (value, targets, markdowns) == original


@pytest.mark.parametrize("damage", ["unknown-sha", "older-sha", "wrong-word", "later-case", "unicode-first", "ambiguous", "changed-bytes", "wrong-venue", "unrequested-draft"])
def test_unknown_identity_or_nonexact_locator_is_never_admitted(damage):
    value, targets, markdowns = fixture()
    review = value["assessments"][1]
    if damage in {"unknown-sha", "older-sha"}:review["manuscript_sha256"] = "f" * 64
    elif damage == "wrong-word":review["scores"][4]["passages"][0] = "Latest-state semantics should override revocation."
    elif damage == "later-case":review["scores"][4]["passages"][0] = "latest-state Semantics cannot override revocation."
    elif damage == "unicode-first":review["scores"][4]["passages"][0] = "Łatest-state semantics cannot override revocation."
    elif damage == "ambiguous":
        markdowns[review["venue_id"]] += " latest-state semantics cannot override revocation."
        targets[review["venue_id"]]["markdown_sha256"] = hashlib.sha256(markdowns[review["venue_id"]].encode()).hexdigest()
    elif damage == "changed-bytes":markdowns[review["venue_id"]] += " Another unsupported sentence."
    elif damage == "wrong-venue":review["venue_id"] = value["assessments"][0]["venue_id"]
    else:targets[review["venue_id"]].pop("draft_sha256")
    with pytest.raises(ValueError):canonical_review_transport(value, targets, markdowns)

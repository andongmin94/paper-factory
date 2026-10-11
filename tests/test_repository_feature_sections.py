"""Feature Articles retain whole evidence-bound prose without fixed research headings."""

import copy

import pytest

from paper_factory.autonomous.repository_paper import RepositoryManuscript, RepositoryReview, render
from test_repository_paper_workflow import review
from test_repository_references_format import references_fixture


def feature_fixture():
    original, _, _, args = references_fixture()
    value = original.model_dump()
    headings = ["Abstract", "A Practical Design Problem", "Comparing Authority Decisions", "Costs, Limits and Takeaways"]
    value["sections"] = [{"heading": heading, "text": value["sections"][index]["text"]}
                         for index, heading in enumerate(headings)]
    return value, args


def test_feature_article_custom_headings_and_complete_prose_are_byte_exact():
    value, args = feature_fixture()
    original = copy.deepcopy(value)
    article = RepositoryManuscript.model_validate(value)
    assert article.model_dump() == original and value == original
    rendered = render(article, *args)
    for section in original["sections"]:
        assert "## " + section["heading"] + "\n\n" + section["text"].split(" {{", 1)[0] in rendered


@pytest.mark.parametrize("damage", ["no_abstract", "abstract_not_first", "duplicate", "case_duplicate", "too_few", "ack_as_body", "incomplete_body"])
def test_feature_article_structure_does_not_admit_missing_or_duplicate_body(damage):
    value, _ = feature_fixture()
    if damage == "no_abstract":
        value["sections"][0]["heading"] = "Overview"
    elif damage == "abstract_not_first":
        value["sections"][0], value["sections"][1] = value["sections"][1], value["sections"][0]
    elif damage in {"duplicate", "case_duplicate"}:
        value["sections"][2]["heading"] = value["sections"][1]["heading"]
        if damage == "case_duplicate":
            value["sections"][2]["heading"] = value["sections"][2]["heading"].upper()
    elif damage == "too_few":
        value["sections"].pop()
    elif damage == "ack_as_body":
        value["sections"][-1]["heading"] = "Acknowledgments"
    else:
        value["sections"][-1]["text"] = "Incomplete body."
    with pytest.raises(ValueError):
        RepositoryManuscript.model_validate(value)


def test_body_responsibilities_can_share_one_section_without_canonical_inner_headings():
    value, _ = feature_fixture()
    value["sections"][-1]["text"] += " The retained analysis explains assumptions, limits, counterexamples and practical recommendations together."
    assert RepositoryManuscript.model_validate(value).model_dump() == value


def test_negative_review_can_request_repairs_to_actual_feature_article_headings():
    value = review(False)
    value["content_assessment"]["revision_outline"] = [{"heading": "Costs, Limits and Takeaways",
        "instruction": "Explain the retained case assumptions and boundary conditions before giving practical recommendations."}]
    assert RepositoryReview.model_validate(value).model_dump() == value

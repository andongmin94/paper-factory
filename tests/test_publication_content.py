"""Publication checks must inspect actual prose and each author's own block."""

import importlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
checks = importlib.import_module("_publication_checks")
facts = importlib.import_module("_author_profile")

ARTICLE = """# Shared configuration lifecycle

## Abstract

A static example supports a bounded maintenance decision.

Keywords: maintenance; configuration; ownership

## Analysis

The surviving consumer still needs the setting. [1]

## Actionable insights

- Identify the consumer.
- Preserve the original value.
- Refuse uncertain restoration.

## Acknowledgments

OpenAI Codex assisted with analysis and drafting throughout this article.

## References

[1] Source Authors, A retained implementation, 2025. https://example.org/source
"""


def item(result, name):
    return next(row for row in result["items"] if row["id"] == name)


@pytest.mark.parametrize("fence", ["```", "~~~~", "    "])
def test_code_examples_do_not_replace_abstract_or_bibliography(fence):
    if fence == "    ":
        # Indented code cannot masquerade as the supported top-level headings.
        example = "\n## Example\n\n    ## Abstract\n    Example only.\n    ## References\n    [99] Not a reference.\n"
    else:
        example = "\n## Example\n\n" + fence + "markdown\n## Abstract\nExample only.\n## References\n[99] Not a reference.\n" + fence + "\n"
    before = checks.validate_manuscript(ARTICLE, "ieee-software")
    after = checks.validate_manuscript(ARTICLE + example, "ieee-software")
    assert after["metrics"]["abstract_words_estimate"] == before["metrics"]["abstract_words_estimate"]
    assert after["metrics"]["reference_count"] == before["metrics"]["reference_count"] == 1
    assert item(after, "reference_count")["status"] == "passed"


def test_code_cannot_supply_keywords_visuals_insights_or_disclosure():
    no_actual_keywords = ARTICLE.replace("Keywords: maintenance; configuration; ownership\n", "")
    example = """
## Example

````markdown
Keywords: invented; keyword; values
| Fake | Table |
| --- | --- |
![Not a figure](missing.png)
## Actionable insights
- A
- B
- C
## Acknowledgments
OpenAI assisted with drafting throughout this article.
```
## Abstract
This heading is still inside the longer fence.
````
"""
    result = checks.validate_manuscript(no_actual_keywords + example, "ieee-software")
    assert result["metrics"]["keywords"] == []
    assert result["metrics"]["visual_count_estimate"] == 0
    assert result["metrics"]["actionable_insights"] == 3
    assert item(result, "keywords")["status"] == "failed"
    without_actual_disclosure = ARTICLE.replace("OpenAI Codex assisted with analysis and drafting throughout this article.", "No disclosure supplied.")
    assert item(checks.validate_manuscript(without_actual_disclosure + example, "ieee-software"), "ai_disclosure")["status"] == "failed"


def profile():
    return facts.normalize_profile({"authors": [
        {"id": "alice", "author": {"display_name": "Alice Research", "affiliation": "Lab A", "email": "alice@example.org", "biography": "Studies maintenance."}},
        {"id": "bob", "author": {"display_name": "Bob Scientist", "affiliation": "Lab B", "email": "bob@example.org", "biography": "Studies concurrency."}},
    ], "order": ["alice", "bob"]})


def with_authors(blocks, *, marked=True):
    front = "\n\n".join(blocks)
    if marked:
        front = "<!-- paper-factory:authors:start -->\n\n" + front + "\n\n<!-- paper-factory:authors:end -->"
    return ARTICLE.replace("\n\n## Abstract", "\n\n" + front + "\n\n## Abstract", 1)


def test_coauthor_facts_must_belong_to_the_named_person():
    article = with_authors(["Alice Research | Lab B | bob@example.org", "Bob Scientist | Lab A | alice@example.org"])
    result = checks.validate_manuscript(article, "ieee-software", profile())
    assert item(result, "author_profile_binding")["status"] == "pending"
    assert all(set(row["missing_byline_values"]) == {"affiliation", "email"} for row in result["metrics"]["authors"])


def test_coauthor_order_and_duplicate_byline_are_not_silently_accepted():
    alice, bob = "Alice Research | Lab A | alice@example.org", "Bob Scientist | Lab B | bob@example.org"
    for blocks in ([bob, alice], [alice, bob, alice]):
        result = checks.validate_manuscript(with_authors(blocks), "ieee-software", profile())
        assert item(result, "author_profile_binding")["status"] == "pending"
        assert not all(row["byline_order_matches"] for row in result["metrics"]["authors"])


def test_similar_affiliation_or_email_is_not_the_supplied_fact():
    article = with_authors(["Alice Research | Lab A Extended | alice@example.org.imposter", "Bob Scientist | Lab B | bob@example.org"])
    result = checks.validate_manuscript(article, "ieee-software", profile())
    assert set(result["metrics"]["authors"][0]["missing_byline_values"]) == {"affiliation", "email"}
    assert item(result, "author_profile_binding")["status"] == "pending"


@pytest.mark.parametrize("marked", [True, False])
def test_actual_ordered_byline_is_supported_with_or_without_markers(marked):
    result = checks.validate_manuscript(with_authors(["Alice Research | Lab A | alice@example.org", "Bob Scientist | Lab B | bob@example.org"], marked=marked), "ieee-software", profile())
    assert item(result, "author_profile_binding")["status"] == "passed"
    assert all(not row["missing_byline_values"] for row in result["metrics"]["authors"])
    assert result["author_approval_inferred"] is False


def test_names_or_controls_in_code_cannot_supply_byline_facts():
    example = "```markdown\n<!-- paper-factory:authors:start -->\nAlice Research | Lab A | alice@example.org\nBob Scientist | Lab B | bob@example.org\n<!-- paper-factory:authors:end -->\n```"
    result = checks.validate_manuscript(ARTICLE.replace("\n\n## Abstract", "\n\n" + example + "\n\n## Abstract", 1), "ieee-software", profile())
    assert item(result, "author_profile_binding")["status"] == "pending"
    assert all("display_name" in row["missing_byline_values"] for row in result["metrics"]["authors"])


def test_biography_is_associated_with_the_named_author():
    correct = with_authors(["Alice Research | Lab A | alice@example.org", "Bob Scientist | Lab B | bob@example.org"])
    swapped = "\n\n## Author biographies\n\nAlice Research. Studies concurrency.\n\nBob Scientist. Studies maintenance.\n"
    result = checks.validate_manuscript(correct + swapped, "ieee-software", profile())
    assert all(not row["supplied_biography_in_manuscript"] for row in result["metrics"]["authors"])


def test_actual_single_author_legacy_byline_is_retained():
    supplied = facts.normalize_profile({"authors": [{"id": "sanghoon", "author": {"display_name": "Sanghoon Kim", "orcid": "0009-0009-8671-9967"}}], "order": ["sanghoon"]})
    article = with_authors(["Sanghoon Kim | ORCID 0009-0009-8671-9967"], marked=False)
    result = checks.validate_manuscript(article, "ieee-software", supplied)
    assert item(result, "author_profile_binding")["status"] == "passed"
    assert result["metrics"]["authors"][0]["missing_fields"]
    assert not result["submission_ready"]


def test_inline_technical_words_still_count_in_the_actual_abstract_estimate():
    article = ARTICLE.replace("A static example supports a bounded maintenance decision.", "An inline `setting` remains a word.")
    result = checks.validate_manuscript(article, "ieee-software")
    assert result["metrics"]["abstract_words_estimate"] == 6

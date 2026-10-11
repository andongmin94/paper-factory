"""Immutable output-only source labels preserve the whole author/scientific prefix."""

import copy
import hashlib
import re

import pytest

from paper_factory.autonomous.repository_paper import RepositoryManuscript, format_source_reference_labels, render
from test_repository_references_format import references_fixture


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def label_fixture():
    draft, _, expected, _ = references_fixture()
    title, rest = expected.split("\n", 1)
    expected = title + "\n\nAuthor: Synthetic Name; exact retained affiliation.\nORCID: 0000-0000-0000-0000\n" + rest
    body, references = expected.rsplit("## References\n\n", 1)
    for item in draft.source_evidence:
        escaped = re.sub(r"([\\`*_\[\]])", r"\\\1", item.path)
        references = references.replace(f"[`{item.path}`]", f"[{escaped}]")
    return draft, body + "## References\n\n" + references, expected


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_formats_only_plain_source_labels_preserving_author_science_non_source_records_numbers_and_urls(newline):
    draft, original, expected = label_fixture()
    original, expected = original.replace("\n", newline), expected.replace("\n", newline)
    before = copy.deepcopy(draft.model_dump())
    formatted, proof = format_source_reference_labels(draft, original)
    assert formatted == expected
    prefix = original.rsplit("## References" + newline * 2, 1)[0]
    assert formatted.startswith(prefix)
    assert proof["scientific_body_sha256_before"] == proof["scientific_body_sha256_after"] == digest(prefix)
    assert proof["original_markdown_sha256"] == digest(original)
    assert proof["formatted_markdown_sha256"] == digest(formatted)
    assert len(proof["changed_labels"]) == 5
    assert proof["reference_numbers"] == list(range(1, 10))
    assert [record["number"] for record in proof["source_references"]] == [1, 2, 7, 8, 9]
    assert [record["path"] for record in proof["source_references"]] == [item.path for item in draft.source_evidence]
    old_entries = original.rsplit("## References" + newline * 2, 1)[1].strip().split(newline * 2)
    new_entries = formatted.rsplit("## References" + newline * 2, 1)[1].strip().split(newline * 2)
    for index in (2, 3, 4, 5):
        assert old_entries[index] == new_entries[index]
    assert draft.model_dump() == before
    no_op, next_proof = format_source_reference_labels(draft, formatted)
    assert no_op == formatted and next_proof["changed_labels"] == []
    assert next_proof["original_markdown_sha256"] == next_proof["formatted_markdown_sha256"]


@pytest.mark.parametrize("path,expected_label", [
    ("src/name`part.ts", "``src/name`part.ts``"),
    ("src/name``part.ts", "```src/name``part.ts```"),
    ("src/[file]*_name.ts", "`src/[file]*_name.ts`"),
    ("`file.ts", "`` `file.ts ``"),
])
def test_output_helper_reuses_variable_code_fence_without_altering_source_identity(path, expected_label):
    original, _, _, args = references_fixture()
    value = original.model_dump()
    value["sections"] = [section for section in value["sections"] if section["heading"] != "References"]
    value["source_evidence"][0]["path"] = path
    draft = RepositoryManuscript.model_validate(value)
    rendered = render(draft, *args[:-1], [path, *args[-1][1:]])
    body, references = rendered.rsplit("## References\n\n", 1)
    escaped = re.sub(r"([\\`*_\[\]])", r"\\\1", path)
    old = body + "## References\n\n" + references.replace(f"[{expected_label}]", f"[{escaped}]")
    formatted, proof = format_source_reference_labels(draft, old)
    assert formatted == rendered
    assert proof["changed_labels"][0]["path"] == path
    assert proof["changed_labels"][0]["url"] == f"{args[0]}/blob/{args[1]}/{path}"


@pytest.mark.parametrize("change", [
    lambda text: text.replace("[1] [src/preload.ts]", "[1] [src/uninspected.ts]"),
    lambda text: text.replace("[2] [src/ipc.ts]", "[2] [src/preload.ts]"),
    lambda text: text.replace("[2] [src/ipc.ts]", "[3] [src/ipc.ts]"),
    lambda text: text.replace("/blob/" + "a" * 40 + "/src/ipc.ts", "/blob/" + "b" * 40 + "/src/ipc.ts"),
    lambda text: text.replace("https://github.com/fixture/project/blob/", "https://github.com/fixture/other/blob/", 1),
    lambda text: text.replace("/src/ipc.ts)", "/src/other.ts)"),
    lambda text: text.replace("/src/ipc.ts)", "/src/ipc.ts?other=true)"),
    lambda text: text.replace(". Repository revision: " + "a" * 40 + ".", ". Repository revision: " + "a" * 40 + ". Extra scientific claim.", 1),
    lambda text: text + "\n## References\n\nUnowned duplicate bibliography.\n",
    lambda text: text.replace("## Abstract\n", "## Abstract\r\n", 1),
    lambda text: text.replace("## References\n\n[1]", "## References\n[1]", 1),
])
def test_wrong_path_number_url_revision_structure_and_mixed_newlines_fail_closed(change):
    draft, original, _ = label_fixture()
    with pytest.raises(ValueError):
        format_source_reference_labels(draft, change(original))


def test_duplicate_model_bibliography_and_ambiguous_source_hashes_fail_closed():
    draft, original, _ = label_fixture()
    manual = next(section for section in draft.sections if section.heading == "References")
    duplicate = original.replace("## Acknowledgments\n", "## References\n\n" + manual.text + "\n\n## Acknowledgments\n")
    with pytest.raises(ValueError, match="one final canonical bibliography"):
        format_source_reference_labels(draft, duplicate)
    value = draft.model_dump()
    repeated = {**value["source_evidence"][0], "id": "ambiguous_source", "sha256": "f" * 64}
    value["source_evidence"].append(repeated)
    with pytest.raises(ValueError):
        format_source_reference_labels(RepositoryManuscript.model_validate(value), original)

"""References ownership and immutable bibliography-only output formatting."""

import copy
import hashlib
import json

import pytest

from paper_factory.autonomous.repository_paper import (
    SECTIONS, RepositoryManuscript, format_references_only, render,
)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def references_fixture(*, exact_entries=False, heading="References"):
    paths = ["src/preload.ts", "src/ipc.ts", "src/window.ts", "src/main.ts", "src/__tests__/sample.ts"]
    repository = "https://github.com/fixture/project"
    commit = "a" * 40
    paragraph = "This synthetic source analysis makes no execution or effectiveness claim; its bounded interpretation remains unchanged."
    evidence = [{"id": "s" + str(i), "path": path, "sha256": str(i + 1) * 64,
        "quote": "export const retainedSource = true;", "interpretation": paragraph} for i, path in enumerate(paths)]
    witness = {"source_id": "paper", "text_sha256": "8" * 64,
        "quote": "This synthetic primary-body passage supplies only a citation-formatting fixture.", "interpretation": paragraph}
    documents = {"d" + str(i): {"url": "https://www.electronjs.org/docs/latest/" + suffix,
        "fetched_at": "2026-10-11T00:00:00Z"} for i, suffix in enumerate(("tutorial/security", "api/context-bridge", "api/dialog"))}
    sources = {"paper": {"authors": ["Shutong Jin", "Ruiyi Guo", "Ray C. C. Cheung"],
        "title": "Synthetic Citation Identity", "year": 2026, "url": "https://arxiv.org/pdf/2604.16762v1"}}
    value = {"title": "Synthetic Immutable Bibliography Formatting Fixture",
        "sections": [{"heading": name, "text": paragraph} for name in SECTIONS],
        "source_evidence": evidence, "literature_evidence": [witness],
        "document_evidence": [{**witness, "source_id": identifier} for identifier in documents], "revision": None}
    value["sections"][1]["text"] += " {{source:s0}} {{source:s1}} {{document:d0}} {{document:d1}} {{document:d2}} {{citation:paper}} {{source:s2}} {{source:s3}} {{source:s4}}."
    value["sections"][3]["text"] += "\n\n```text\n## References\nThis is protected literal code, not a bibliography heading.\n```"
    value["sections"].append({"heading": "Acknowledgments", "text": paragraph + " AI assistance and absent human approval remain disclosed."})
    plain = RepositoryManuscript.model_validate(value)
    canonical_md = render(plain, repository, commit, sources, documents, paths)
    if exact_entries:
        entries = canonical_md.rsplit("## References\n\n", 1)[1].strip().split("\n\n")
        manual = "\n".join("- " + entry.split(" ", 1)[1] for entry in entries)
    else:
        manual = "Repository witnesses are linked to the frozen source revision; literal quotations and bounded interpretations accompany the evidence records.\n\n"
        manual += "\n".join(f"- [`{path}`]({repository}/blob/{commit}/{path})." for path in paths)
        manual += "\n" + "\n".join(f'- Electron contributors, “{title},” inspected documentation snapshot, {documents[identifier]["url"]}.'
            for identifier, title in zip(documents, ("Security", "contextBridge", "dialog")))
        manual += '\n- S. Jin, R. Guo, and R. C. C. Cheung, “Synthetic Citation Identity,” arXiv:2604.16762v1, 2026.'
    value["sections"].insert(-1, {"heading": heading, "text": manual})
    draft = RepositoryManuscript.model_validate(value)
    # Reproduce the preceding renderer's duplicate block without touching any
    # actual study, preserving the originally admitted scientific byte order.
    historical = canonical_md.replace("## Acknowledgments\n", "## " + heading + "\n\n" + manual + "\n\n## Acknowledgments\n", 1)
    return draft, historical, canonical_md, (repository, commit, sources, documents, paths)


@pytest.mark.parametrize("exact_entries", [False, True])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_format_only_removes_duplicate_and_preserves_all_science_citations_evidence_and_canonical_bytes(exact_entries, newline):
    draft, old, expected, arguments = references_fixture(exact_entries=exact_entries)
    old, expected = old.replace("\n", newline), expected.replace("\n", newline)
    frozen = json.dumps(draft.model_dump(), sort_keys=True)
    formatted, proof = format_references_only(draft, old)
    assert formatted == expected
    assert proof["scientific_body_sha256_before"] == proof["scientific_body_sha256_after"]
    assert proof["original_markdown_sha256"] == digest(old)
    assert proof["formatted_markdown_sha256"] == digest(expected)
    canonical = "## References" + newline + old.rsplit("## References" + newline, 1)[1]
    assert proof["canonical_references_sha256"] == digest(canonical)
    assert proof["removed_entries"] == 9 and proof["reference_numbers"] == list(range(1, 10))
    assert json.dumps(draft.model_dump(), sort_keys=True) == frozen
    assert render(draft, *arguments) == expected.replace("\r\n", "\n")
    # The literal fenced heading survives along with the single real References.
    assert formatted.count("## References") == 2


@pytest.mark.parametrize("text", [
    "This method proves a scientific superiority claim outside the bibliography.",
    "- [Uninspected method](https://example.test/method). It proves superiority.",
    "- Electron contributors, “Security,” inspected documentation snapshot, https://www.electronjs.org/docs/latest/tutorial/security. Our method is better.",
    "## New Scientific Finding\nA finding must never be deleted by formatting.",
    "{{source:s0}} is a substantive source interpretation, not a bibliography entry.",
])
def test_scientific_or_ambiguous_model_references_fail_closed(text):
    draft, old, _, arguments = references_fixture()
    manual = next(section for section in draft.sections if section.heading == "References")
    original = manual.text
    manual.text += "\n\n" + text
    old = old.replace(original, manual.text)
    with pytest.raises(ValueError, match="bibliograph|typed section"):
        format_references_only(draft, old)
    with pytest.raises(ValueError, match="bibliograph"):
        render(draft, *arguments)


@pytest.mark.parametrize("change", ["wrong_version", "unknown_identity", "duplicate_identity", "missing_identity"])
def test_manual_bibliography_must_duplicate_every_exact_canonical_identity_once(change):
    draft, old, _, _ = references_fixture(exact_entries=True)
    manual = next(section for section in draft.sections if section.heading == "References")
    original = manual.text
    lines = original.splitlines()
    if change == "wrong_version":
        manual.text = original.replace("2604.16762v1", "2604.16762v2")
    elif change == "unknown_identity":
        manual.text = original.replace("/blob/" + "a" * 40, "/blob/" + "b" * 40, 1)
    elif change == "duplicate_identity":
        lines[-1] = lines[0]
        manual.text = "\n".join(lines)
    else:
        manual.text = "\n".join(lines[:-1])
    with pytest.raises(ValueError, match="bibliograph"):
        format_references_only(draft, old.replace(original, manual.text))


@pytest.mark.parametrize("change", ["body", "number", "missing_section", "extra_section", "mixed_newlines"])
def test_retained_rendering_structure_and_reference_numbers_cannot_be_rewritten(change):
    draft, old, _, _ = references_fixture()
    if change == "body":
        old = old.replace("- Electron contributors", "- Changed contributors", 1)
    elif change == "number":
        old = old.replace("\n[9] ", "\n[8] ")
    elif change == "missing_section":
        old = old.replace("## Method\n", "## Missing Method\n")
    elif change == "extra_section":
        old += "\n## Additional References\n\nUnexpected duplicate bibliography.\n"
    else:
        old = old.replace("\n", "\r\n", 1)
    with pytest.raises(ValueError):
        format_references_only(draft, old)


def test_no_model_duplicate_or_multiple_typed_bibliographies_are_not_formatting_candidates():
    draft, old, _, _ = references_fixture()
    original = copy.deepcopy(draft)
    draft.sections = [section for section in draft.sections if section.heading != "References"]
    with pytest.raises(ValueError, match="No duplicate"):
        format_references_only(draft, old)
    original.sections.append(copy.deepcopy(next(section for section in original.sections if section.heading == "References")))
    original.sections[-1].heading = "Reference"
    with pytest.raises(ValueError, match="Only one"):
        format_references_only(original, old)


def test_singular_typed_reference_heading_has_one_engine_owned_final_bibliography():
    draft, old, expected, arguments = references_fixture(heading="Reference")
    formatted, proof = format_references_only(draft, old)
    assert formatted == expected and proof["removed_heading"] == "Reference"
    assert render(draft, *arguments) == expected

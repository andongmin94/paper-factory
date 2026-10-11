"""Canonical repository labels protect filenames without changing evidence identity."""

import copy
import re

import pytest

from paper_factory.autonomous.repository_paper import RepositoryManuscript, format_references_only, render
from test_repository_references_format import references_fixture


def test_code_labels_preserve_all_reference_urls_numbers_order_and_scientific_body():
    draft, _, expected, arguments = references_fixture()
    rendered = render(draft, *arguments)
    assert rendered == expected
    bibliography = rendered.rsplit("## References\n\n", 1)[1].strip().split("\n\n")
    assert [int(re.match(r"\[(\d+)\]", entry)[1]) for entry in bibliography] == list(range(1, 10))
    paths = arguments[-1]
    source_entries = [entry for entry in bibliography if "Repository revision:" in entry]
    assert len(source_entries) == len(paths)
    for path, entry in zip(paths, source_entries):
        assert f"[`{path}`]({arguments[0]}/blob/{arguments[1]}/{path})" in entry
    assert "src/__tests__/sample.ts" in source_entries[-1]
    assert "\\_" not in source_entries[-1]


@pytest.mark.parametrize("path,label", [
    ("src/file[1]*_name.ts", "`src/file[1]*_name.ts`"),
    ("src/name`part.ts", "``src/name`part.ts``"),
    ("src/name``part.ts", "```src/name``part.ts```"),
    ("`file.ts", "`` `file.ts ``"),
    ("src/file.ts`", "`` src/file.ts` ``"),
])
def test_literal_code_fence_accepts_same_duplicate_path_but_not_a_different_url_or_name(path, label):
    original, _, _, arguments = references_fixture()
    value = original.model_dump()
    value["sections"] = [section for section in value["sections"] if section["heading"] != "References"]
    value["source_evidence"][0]["path"] = path
    paths = [path, *arguments[-1][1:]]
    args = (*arguments[:-1], paths)
    plain = RepositoryManuscript.model_validate(value)
    expected = render(plain, *args)
    url = f"{arguments[0]}/blob/{arguments[1]}/{path}"
    assert f"[{label}]({url}). Repository revision:" in expected
    entries = expected.rsplit("## References\n\n", 1)[1].strip().split("\n\n")
    manual = "\n".join("- " + entry.split(" ", 1)[1] for entry in entries)
    # Exercise identity matching instead of the exact canonical-entry fast path.
    canonical = f"[{label}]({url}). Repository revision: {arguments[1]}."
    duplicate = f"[{label}]({url})."
    manual = manual.replace(canonical, duplicate)
    value["sections"].insert(-1, {"heading": "References", "text": manual})
    draft = RepositoryManuscript.model_validate(value)
    assert render(draft, *args) == expected
    for replacement in (duplicate.replace(url, url + "/wrong"), duplicate.replace(label, label.replace("file", "other") if "file" in label else label.replace("name", "other"))):
        changed = copy.deepcopy(value)
        changed["sections"][-2]["text"] = manual.replace(duplicate, replacement)
        with pytest.raises(ValueError, match="duplicate one canonical reference"):
            render(RepositoryManuscript.model_validate(changed), *args)


def test_explicit_historical_plain_labels_keep_original_format_proof_and_scientific_bytes():
    draft, old, expected, _ = references_fixture()
    paths = [item.path for item in draft.source_evidence]
    for path in paths:
        escaped = re.sub(r"([\\`*_\[\]])", r"\\\1", path)
        old = old.replace(f"[`{path}`]", f"[{escaped}]")
        expected = expected.replace(f"[`{path}`]", f"[{escaped}]")
    # Manual labels must still reproduce the immutable model section exactly.
    manual = next(section for section in draft.sections if section.heading == "References")
    body = "## References\n\n" + manual.text + "\n\n"
    old_start = old.index("## References\n\n", old.index("## Limitations"))
    old_end = old.index("## Acknowledgments\n", old_start)
    old = old[:old_start] + body + old[old_end:]
    formatted, proof = format_references_only(draft, old)
    assert formatted == expected
    assert proof["scientific_body_sha256_before"] == proof["scientific_body_sha256_after"]
    assert proof["reference_numbers"] == list(range(1, 10))

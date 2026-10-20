from paper_factory.autonomous.repository_paper import RepositoryManuscript, render


def test_one_repository_snapshot_reference_keeps_all_path_witnesses():
    explanation = "Synthetic explanation of two inspected paths and their separate, bounded source observations. "
    value = {
        "title": "Synthetic repository snapshot citation example",
        "sections": [{"heading": heading, "text": explanation + tokens} for heading, tokens in [
            ("Abstract", "This fixture establishes no publication finding or quality assessment."),
            ("First path", "{{source:first}}"), ("Second path", "{{source:second}}"),
            ("Limitations", "The two source paths belong to one snapshot, not two independent cases.")]],
        "source_evidence": [{"id": key, "path": f"src/{key}.ts", "sha256": digest * 64,
            "quote": "Synthetic literal source witness for citation rendering only.", "interpretation": explanation}
            for key, digest in [("first", "a"), ("second", "b")]],
        "literature_evidence": [], "document_evidence": [], "revision": None,
    }
    draft = RepositoryManuscript.model_validate(value)
    original = draft.model_dump()
    markdown = render(draft, "https://github.com/example/synthetic", "c" * 40, {}, {},
                      ["src/first.ts", "src/second.ts"], group_repository_citations=True)
    assert markdown.count("Repository revision:") == 1
    assert "[2]" not in markdown
    assert "/tree/" + "c" * 40 in markdown
    assert draft.model_dump() == original
    assert len(draft.source_evidence) == 2

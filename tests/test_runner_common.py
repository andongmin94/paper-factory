"""Portable boundaries retained after removing native generated-code runners."""
import hashlib

import pytest

from paper_factory.autonomous import runner_common as runner


def test_retains_exact_negative_observations_without_rewriting_bytes(tmp_path):
    raw = b'{"controls":[{"passed":false}],"detail":"negative finding"}\r\n'
    result = runner._retain_observations(tmp_path, raw)
    assert (tmp_path / "observations.json").read_bytes() == raw
    assert result["artifacts"] == [{"path": "observations.json", "size": len(raw),
                                    "sha256": hashlib.sha256(raw).hexdigest()}]
    with pytest.raises(FileExistsError):
        runner._retain_observations(tmp_path, b'{"replacement":true}')
    assert (tmp_path / "observations.json").read_bytes() == raw


@pytest.mark.parametrize("raw", [b"", b"not-json", b'{"duplicate":1,"duplicate":2}', b'{"value":NaN}'])
def test_invalid_observations_never_create_an_artifact(tmp_path, raw):
    with pytest.raises(ValueError):
        runner._retain_observations(tmp_path, raw)
    assert not (tmp_path / "observations.json").exists()


def test_observation_limit_is_checked_before_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "MAX_ARTIFACT_BYTES", 4)
    with pytest.raises(ValueError, match="size limit"):
        runner._retain_observations(tmp_path, b'{"value":1}')
    assert not (tmp_path / "observations.json").exists()


def test_source_tree_boundaries_preserve_originals(tmp_path, monkeypatch):
    source = tmp_path / "source, with spaces"
    source.mkdir()
    original = source / "production.js"
    original.write_bytes(b"export const identity = value => value;\n")
    assert runner._safe_tree(source, "source") == source.resolve()
    monkeypatch.setattr(runner, "MAX_INPUT_BYTES", 8)
    with pytest.raises(ValueError, match="input limits"):
        runner._safe_tree(source, "source")
    assert original.read_bytes() == b"export const identity = value => value;\n"


def test_source_tree_file_count_is_bounded(tmp_path, monkeypatch):
    (tmp_path / "first.js").write_bytes(b"1")
    (tmp_path / "second.js").write_bytes(b"2")
    monkeypatch.setattr(runner, "MAX_INPUT_FILES", 1)
    with pytest.raises(ValueError, match="input limits"):
        runner._safe_tree(tmp_path, "source")


def test_source_tree_rejects_linked_inputs(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.js"
    outside.write_bytes(b"private")
    try:
        (source / "linked.js").symlink_to(outside)
    except OSError:
        pytest.skip("This account cannot create symbolic links")
    with pytest.raises(ValueError, match="links"):
        runner._safe_tree(source, "source")
    assert outside.read_bytes() == b"private"


@pytest.mark.parametrize("change", [
    {"path": "../production.js"}, {"path": "absent.js"}, {"path": "production\\.js"},
    {"function": "<module>"}, {"function": "bad\nname"}, {"calls": True}, {"calls": 0},
])
def test_production_receipts_cannot_forge_source_identity_or_calls(tmp_path, change):
    (tmp_path / "production.js").write_bytes(b"export const transform = value => value;\n")
    receipt = {"path": "production.js", "function": "transform", "calls": 6, **change}
    with pytest.raises(ValueError):
        runner._production_calls([receipt], tmp_path)


def test_production_receipt_rejects_duplicate_or_unbounded_entries(tmp_path, monkeypatch):
    (tmp_path / "production.js").write_bytes(b"original")
    receipt = {"path": "production.js", "function": "transform", "calls": 6}
    assert runner._production_calls([receipt], tmp_path) == [receipt]
    with pytest.raises(ValueError, match="duplicate"):
        runner._production_calls([receipt, receipt], tmp_path)
    monkeypatch.setattr(runner, "MAX_PRODUCTION_FUNCTIONS", 0)
    with pytest.raises(ValueError, match="receipt"):
        runner._production_calls([receipt], tmp_path)

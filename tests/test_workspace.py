from contextlib import contextmanager

from paper_factory.workspace import Workspace


def test_unknown_commit_outcome_preserves_owned_artifacts(tmp_path, monkeypatch):
    ws = Workspace.create(tmp_path / "workspace")
    destination = ws.path("artifacts/owned-receipt")
    destination.mkdir(parents=True)
    evidence = destination / "evidence.bin"
    evidence.write_bytes(b"Actual evidence must survive an unavailable record store.")

    @contextmanager
    def unavailable():
        raise OSError("Record store temporarily unavailable")
        yield

    monkeypatch.setattr(ws, "_database", unavailable)
    assert not ws.discard_uncommitted_artifact(destination, kind="receipt", record_id="receipt-one",
        field="sha256", expected_value="1" * 64)
    assert evidence.read_bytes() == b"Actual evidence must survive an unavailable record store."


def test_commit_cleanup_cannot_delete_outside_the_workspace(tmp_path):
    ws = Workspace.create(tmp_path / "workspace")
    outside = tmp_path / "outside"
    outside.mkdir()
    evidence = outside / "evidence.bin"
    evidence.write_bytes(b"Outside evidence")
    assert not ws.discard_uncommitted_artifact(outside, kind="receipt", record_id="receipt-one",
        field="sha256", expected_value="1" * 64)
    assert evidence.read_bytes() == b"Outside evidence"

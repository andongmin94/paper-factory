from contextlib import ExitStack, closing, contextmanager
import sqlite3

import pytest

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


@pytest.mark.parametrize("failure", ["corrupt", "locked"])
def test_real_sqlite_failure_preserves_artifacts_and_the_original_operation_error(tmp_path, failure):
    ws = Workspace.create(tmp_path / "workspace")
    destination = ws.path("artifacts/owned-receipt")
    destination.mkdir(parents=True)
    evidence = destination / "evidence.bin"
    content = b"Evidence must survive an unknown SQLite commit outcome."
    evidence.write_bytes(content)
    store = ws.path("records.sqlite3")

    with ExitStack() as resources:
        if failure == "corrupt":
            store.write_bytes(b"This is not a SQLite database.")
        else:
            locked = resources.enter_context(closing(sqlite3.connect(store)))
            locked.execute("BEGIN EXCLUSIVE")

        with pytest.raises(ValueError, match="record store is unavailable or corrupt") as wrapped:
            with ws._database() as db:
                db.execute("SELECT data FROM records")
        assert isinstance(wrapped.value.__cause__, sqlite3.DatabaseError)
        if failure == "locked":
            assert isinstance(wrapped.value.__cause__, sqlite3.OperationalError)

        with pytest.raises(RuntimeError, match="Original transaction error"):
            try:
                raise RuntimeError("Original transaction error")
            except RuntimeError:
                assert not ws.discard_uncommitted_artifact(destination,
                    kind="receipt", record_id="receipt-one", field="sha256", expected_value="1" * 64)
                raise

        assert evidence.read_bytes() == content


def test_commit_cleanup_cannot_delete_outside_the_workspace(tmp_path):
    ws = Workspace.create(tmp_path / "workspace")
    outside = tmp_path / "outside"
    outside.mkdir()
    evidence = outside / "evidence.bin"
    evidence.write_bytes(b"Outside evidence")
    assert not ws.discard_uncommitted_artifact(outside, kind="receipt", record_id="receipt-one",
        field="sha256", expected_value="1" * 64)
    assert evidence.read_bytes() == b"Outside evidence"

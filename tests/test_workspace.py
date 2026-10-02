from contextlib import ExitStack, closing, contextmanager
import os
import sqlite3

import pytest

from paper_factory.workspace import Workspace, loads_json


@pytest.mark.parametrize("payload", [
    '{"passed": false, "passed": true}',
    '{"control": {"passed": false, "passed": true}}',
    '{"passed": false, "pass\\u0065d": true}',
])
def test_json_evidence_rejects_duplicate_keys(payload):
    with pytest.raises(ValueError, match="duplicate object keys"):
        loads_json(payload)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_json_evidence_rejects_nonfinite_numbers_in_any_field(token):
    with pytest.raises(ValueError, match="Nonfinite JSON"):
        loads_json('{"units": [1, {"unused": ' + token + '}]}')


def test_json_evidence_preserves_valid_types_and_exact_integers():
    assert loads_json('{"control":true,"label":"가","units":[null,1.25,9007199254740993]}'.encode("utf-8")) == {
        "control": True, "label": "가", "units": [None, 1.25, 9007199254740993],
    }


@pytest.mark.skipif(os.name != "nt", reason="Windows byte-range locking regression")
def test_empty_lock_contender_reports_concurrency_and_can_retry_after_release(tmp_path):
    import msvcrt
    ws = Workspace.create(tmp_path / "workspace")
    path = ws.path("locks/study.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as holder:
        msvcrt.locking(holder.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            with pytest.raises(ValueError, match="Another operation is already running"):
                with ws.lock("study"):
                    pytest.fail("A competing operation acquired the held lock")
        finally:
            holder.seek(0)
            msvcrt.locking(holder.fileno(), msvcrt.LK_UNLCK, 1)
    with ws.lock("study"):
        pass


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

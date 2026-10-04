from contextlib import ExitStack, closing, contextmanager
import errno
import os
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from paper_factory.workspace import Workspace, loads_json
from paper_factory import workspace as module


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


@pytest.mark.parametrize("platform_name,error_number,is_contention", [
    ("nt", errno.EACCES, True),
    ("nt", errno.EAGAIN, False),
    ("nt", errno.EDEADLK, False),
    ("posix", errno.EAGAIN, True),
    ("posix", errno.EWOULDBLOCK, True),
    ("posix", errno.EACCES, False),
    *[(platform_name, error_number, False)
      for platform_name in ("nt", "posix")
      for error_number in (errno.EIO, errno.EINVAL, errno.ENOSYS, errno.EBADF)],
])
def test_native_lease_errors_only_classify_documented_nonblocking_contention(
        tmp_path, monkeypatch, platform_name, error_number, is_contention):
    """Simulated native APIs; real Windows contention is checked separately."""
    failure = OSError(error_number, "Native lock failure")
    attempts = []

    def fail(*args):
        attempts.append(args)
        raise failure

    monkeypatch.setattr(module, "os", SimpleNamespace(name=platform_name, fstat=os.fstat))
    if platform_name == "nt":
        monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(locking=fail, LK_NBLCK=2, LK_UNLCK=0))
    else:
        monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(flock=fail, LOCK_EX=2, LOCK_NB=4, LOCK_UN=8))
    with pytest.raises(ValueError if is_contention else OSError) as caught:
        with module.file_lock(tmp_path / "supervisor.lock"):
            pytest.fail("Failed native locking must not yield a lease")
    if is_contention:
        assert str(caught.value) == "Another operation is already running for supervisor"
    else:
        assert caught.value is failure
    assert len(attempts) == 1  # No retry or unlock of an unacquired lease.


def test_lease_open_permission_error_is_not_native_lock_contention(tmp_path, monkeypatch):
    from pathlib import Path
    path = tmp_path / "supervisor.lock"
    failure = PermissionError(errno.EACCES, "Private lease path")
    original = Path.open

    def denied(candidate, *args, **kwargs):
        if candidate == path:
            raise failure
        return original(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(PermissionError) as caught:
        with module.file_lock(path):
            pytest.fail("An inaccessible lease must not be acquired")
    assert caught.value is failure


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

import errno
import hashlib
import os
from pathlib import Path
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


def test_long_artifact_paths_preserve_relative_identity_and_verified_io(tmp_path):
    ws = Workspace.create(tmp_path / "workspace")
    relative = "/".join(["retained-" + "a" * 64] * 3 + ["evidence.json"])
    path = ws.path(relative)
    assert len(str(path)) > 260
    assert str(path) == str(ws.root / relative)
    assert path.relative_to(ws.root).as_posix() == relative
    assert path.resolve() == ws.root / relative
    module.write_json(path, {"retained": "exact synthetic evidence"})
    content = path.read_bytes()
    assert loads_json(content) == {"retained": "exact synthetic evidence"}
    assert module.digest_file(path) == hashlib.sha256(content).hexdigest()
    assert path.stat().st_size == len(content)
    staging = ws.path("staging.json")
    staging.write_bytes(content)
    target = path.with_name("atomic-copy.json")
    os.replace(staging, target)
    target.chmod(0o444)
    assert target.read_bytes() == content and not staging.exists()
    assert not str(target).startswith("\\\\?\\")
    assert Path(str(target)).relative_to(ws.root).as_posix().endswith("atomic-copy.json")


def test_long_relative_artifact_checks_absolute_ancestors_without_changing_identity(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Workspace.create(tmp_path / "workspace")
    relative = "/".join(["retained-" + "a" * 64] * 3 + ["evidence.txt"])
    path = module.safe_relative(Path("workspace"), relative)
    assert not path.is_absolute()
    assert path.absolute() == tmp_path / "workspace" / relative
    assert not str(path.absolute()).startswith("\\\\?\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"relative identity, absolute verified IO")
    assert path.resolve().is_relative_to((tmp_path / "workspace").resolve())
    assert path.read_bytes() == b"relative identity, absolute verified IO"


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

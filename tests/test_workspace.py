import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
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


def test_json_writer_keeps_short_temporary_name_at_windows_path_boundary(tmp_path, monkeypatch):
    ws = Workspace.create(tmp_path / "workspace")
    filename = "journal-12345678-1234-1234-1234-123456789abc-completed.json"
    parent_length = 248 - len(filename) - 1
    padding = parent_length - len(str(ws.root)) - 1
    assert padding > 0
    relative = "p" + "x" * (padding - 1) + "/" + filename
    path = ws.path(relative)
    assert len(str(path)) == 248 and len(str(path.parent)) < 248
    # The former target-derived temporary name exceeded normal Windows IO limits.
    assert len(str(path.parent / ("." + filename + ".12345678.tmp"))) == 262
    assert path.relative_to(ws.root).as_posix() == relative
    expected, retained, replacements = [], [], []
    replace = os.replace

    def observe_replace(source, target):
        assert Path(str(source)).parent == path.parent
        assert len(str(source)) < 248
        assert Path(source).read_bytes() == expected[-1]
        assert path.read_bytes() == retained[-1] if retained else not path.exists()
        replacements.append(str(source))
        return replace(source, target)

    monkeypatch.setattr(module.os, "replace", observe_replace)
    for value in ({"retained": "정확한 원문", "version": 1}, {"retained": "새 원문", "version": 2}):
        expected.append((json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").replace("\n", os.linesep).encode("utf-8"))
        module.write_json(path, value)
        raw = path.read_bytes()
        assert raw == expected[-1] and loads_json(raw) == value
        assert module.digest_file(path) == hashlib.sha256(raw).hexdigest()
        assert str(path) == str(ws.root / relative) and path.relative_to(ws.root).as_posix() == relative
        assert list(path.parent.iterdir()) == [path]
        retained.append(raw)
    assert len(replacements) == 2 and all(not Path(name).exists() for name in replacements)


def _json_path_with_parent_length(tmp_path, length, filename):
    padding = length - len(str(tmp_path)) - 1
    assert 0 < padding < 256
    return tmp_path / ("p" * padding) / filename


@pytest.mark.parametrize("parent_length,filename,artifact_path", [
    (247, "result.json", True),
    (247, "retained-evidence.json", False),
    (274, "result.json", True),
])
def test_json_writer_atomically_replaces_exact_evidence_across_windows_io_boundaries(
        tmp_path, monkeypatch, parent_length, filename, artifact_path):
    path = _json_path_with_parent_length(tmp_path, parent_length, filename)
    assert len(str(path.parent)) == parent_length
    if not artifact_path:
        assert len(str(path)) == 270 and type(path) is type(tmp_path)
    target = module._ArtifactPath(path)
    candidate = target if artifact_path else path
    values = [{"version": 1, "label": "정확한 원문"}, {"version": 2, "label": "교체된 원문"}]
    expected = [(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
                .replace("\n", os.linesep).encode("utf-8") for value in values]
    replacements, synced = [], []
    replace, fsync = os.replace, os.fsync

    def durable_sync(descriptor):
        assert os.fstat(descriptor).st_size == len(expected[len(synced)])
        fsync(descriptor)
        synced.append(descriptor)

    def atomic_replace(source, destination):
        index = len(replacements)
        assert len(synced) == index + 1
        assert str(destination) == str(path)
        assert Path(str(source)).parent == path.parent
        assert module._ArtifactPath(source).read_bytes() == expected[index]
        if index:
            assert target.read_bytes() == expected[index - 1]
        else:
            assert not target.exists()
        replacements.append(source)
        return replace(source, destination)

    monkeypatch.setattr(module.os, "fsync", durable_sync)
    monkeypatch.setattr(module.os, "replace", atomic_replace)
    for value, raw in zip(values, expected, strict=True):
        module.write_json(candidate, value)
        assert target.read_bytes() == raw and loads_json(raw) == value
        assert module.digest_file(target) == hashlib.sha256(raw).hexdigest()
        assert str(candidate) == str(path)
        assert list(target.parent.iterdir()) == [target]
    assert len(replacements) == len(synced) == 2
    assert all(not source.exists() for source in replacements)


@pytest.mark.parametrize("failure_stage", ["fsync", "replace", "scanner"])
def test_json_writer_io_failure_preserves_existing_evidence_and_cleans_long_temporary(
        tmp_path, monkeypatch, failure_stage):
    path = _json_path_with_parent_length(tmp_path, 247, "retained-evidence.json")
    assert len(str(path)) == 270
    target = module._ArtifactPath(path)
    module.write_json(path, {"retained": "immutable previous evidence"})
    before = target.read_bytes()
    attempts, delays = [], []
    failure = (PermissionError(errno.EACCES, "Synthetic scanner hold") if failure_stage == "scanner"
               else OSError(errno.EIO, "Synthetic persistence failure"))

    def fail(*args):
        attempts.append(args)
        raise failure

    monkeypatch.setattr(module.os, "fsync" if failure_stage == "fsync" else "replace", fail)
    monkeypatch.setattr(module.time, "sleep", delays.append)
    with pytest.raises(OSError) as caught:
        module.write_json(path, {"retained": "must not replace previous evidence"})
    assert caught.value is failure
    assert target.read_bytes() == before
    assert list(target.parent.iterdir()) == [target]
    expected_attempts = 5 if failure_stage == "scanner" and os.name == "nt" else 1
    assert len(attempts) == expected_attempts and len(delays) == expected_attempts - 1


@pytest.mark.parametrize("link_location", ["ancestor", "target", "target_after_sync"])
def test_json_writer_keeps_link_checks_before_creation_and_atomic_replacement(
        tmp_path, monkeypatch, link_location):
    path = _json_path_with_parent_length(tmp_path, 247, "retained-evidence.json")
    target = module._ArtifactPath(path)
    module.write_json(path, {"retained": "original evidence"})
    before = target.read_bytes()
    linked = link_location != "target_after_sync"
    is_link, fsync = module.is_link, os.fsync

    def detect_link(candidate):
        guarded = target.parent if link_location == "ancestor" else target
        return (linked and candidate == guarded) or is_link(candidate)

    def expose_link(descriptor):
        nonlocal linked
        fsync(descriptor)
        linked = True

    monkeypatch.setattr(module, "is_link", detect_link)
    monkeypatch.setattr(module.os, "fsync", expose_link)
    with pytest.raises(ValueError, match="symlinks or junctions"):
        module.write_json(path, {"retained": "must not traverse a link"})
    assert target.read_bytes() == before and list(target.parent.iterdir()) == [target]


@pytest.mark.skipif(os.name != "nt", reason="Windows junction regression")
def test_plain_long_json_path_refuses_a_real_windows_junction(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    junction = tmp_path / "linked"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    path = _json_path_with_parent_length(junction, 274, "retained-evidence.json")
    assert len(str(path)) > 260
    with pytest.raises(ValueError, match="symlinks or junctions"):
        module.write_json(path, {"retained": "must not enter the linked directory"})
    assert list(outside.iterdir()) == []


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

"""Small SQLite record store and workspace-local artifacts; no source writes."""

import errno
import hashlib
import json
import math
import os
import sqlite3
import stat
import tempfile
import time
from contextlib import closing, contextmanager
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TypeVar

from .models import Record

T = TypeVar("T", bound=Record)


def is_link(path: Path) -> bool:
    """Include Windows junctions and other reparse points."""
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(metadata.st_mode) or bool(getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def ensure_unlinked(path: Path) -> None:
    # Check lexical components before resolve() can hide an internal link.
    absolute = path.absolute()
    if any(is_link(component) for component in (absolute, *absolute.parents)):
        raise ValueError("Artifact paths must not traverse symlinks or junctions")


@contextmanager
def file_lock(path: Path):
    """Fail fast on concurrent owners; the OS releases the lease on exit."""
    ensure_unlinked(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError("Lease must be an ordinary, unlinked file")
        # A byte-range lock may extend past EOF; initializing it can race with
        # another Windows handle already locking that region.
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            contention = {errno.EACCES} if os.name == "nt" else {errno.EAGAIN, errno.EWOULDBLOCK}
            if exc.errno not in contention:
                raise
            raise ValueError(f"Another operation is already running for {path.stem}") from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def safe_relative(root: Path, relative: str) -> Path:
    """Portable artifact paths, checked without following linked components."""
    posix = PurePosixPath(relative)
    devices = {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}
    if (not relative or any(character in relative for character in '\\:<>"|?*') or any(ord(character) < 32 for character in relative) or
            posix.is_absolute() or PureWindowsPath(relative).is_absolute() or
            any(part in {"", ".", ".."} or part.endswith((".", " ")) or part.split(".", 1)[0].upper() in devices for part in relative.split("/"))):
        raise ValueError(f"Expected a safe relative artifact path: {relative!r}")
    path = root / relative
    ensure_unlinked(path)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes its working directory")
    return path


def digest_file(path: Path) -> str:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256")
    return digest.hexdigest()


def loads_json(content: str | bytes) -> object:
    """Decode evidence without ambiguous keys or nonfinite numbers."""
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError("JSON has duplicate object keys")
            result[key] = value
        return result

    def finite_number(token: str) -> float:
        value = float(token)
        if not math.isfinite(value):
            raise ValueError(f"Nonfinite JSON numeric value: {token}")
        return value

    return json.loads(content, object_pairs_hook=pairs,
        parse_float=finite_number, parse_constant=finite_number)


def write_json(path: Path, value: object) -> None:
    ensure_unlinked(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value.model_dump(mode="json") if isinstance(value, Record) else value
    content = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        ensure_unlinked(path)
        for attempt in range(5):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                # Windows scanners can briefly hold newly closed files open.
                if os.name != "nt" or attempt == 4:
                    raise
                time.sleep(0.025 * (attempt + 1))
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)



class Workspace:
    def __init__(self, root: Path):
        ensure_unlinked(root.expanduser())
        self.root = root.expanduser().resolve()
        if not self.path("records.sqlite3").is_file():
            raise ValueError(f"Not a Paper Factory workspace: {self.root}.")

    @classmethod
    def create(cls, root: Path) -> "Workspace":
        ensure_unlinked(root.expanduser())
        root = root.expanduser().resolve()
        if root.exists() and (not root.is_dir() or any(root.iterdir())):
            raise ValueError("Workspace destination must be an empty directory")
        root.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(root / "records.sqlite3")) as db, db:
            db.execute("CREATE TABLE records (kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(kind,id))")
        for name in ("source", "literature", "manuscripts", "reports"):
            (root / name).mkdir(exist_ok=True)
        return cls(root)


    def save(self, kind: str, record: Record) -> None:
        with self._database() as db:
            db.execute("INSERT INTO records VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data", (kind, record.id, record.model_dump_json()))

    def get(self, kind: str, id: str, model: type[T]) -> T:
        with self._database() as db:
            row = db.execute("SELECT data FROM records WHERE kind=? AND id=?", (kind, id)).fetchone()
        if row is None:
            raise ValueError(f"Unknown {kind}: {id}")
        record = model.model_validate_json(row[0])
        if record.id != id:
            raise ValueError(f"Persisted {kind} identifier does not match its record key")
        return record

    def list(self, kind: str, model: type[T]) -> list[T]:
        with self._database() as db:
            rows = db.execute("SELECT id,data FROM records WHERE kind=? ORDER BY rowid", (kind,)).fetchall()
        records = []
        for id, data in rows:
            record = model.model_validate_json(data)
            if record.id != id:
                raise ValueError(f"Persisted {kind} identifier does not match its record key")
            records.append(record)
        return records

    @contextmanager
    def _database(self):
        try:
            with closing(sqlite3.connect(self.path("records.sqlite3"))) as db, db:
                yield db
        except sqlite3.Error as error:
            raise ValueError(f"Workspace record store is unavailable or corrupt: {error}") from error

    def latest(self, kind: str, model: type[T]) -> T:
        records = self.list(kind, model)
        if not records:
            raise ValueError(f"No {kind} records yet")
        return records[-1]

    def path(self, relative: str) -> Path:
        return safe_relative(self.root, relative)


    @contextmanager
    def lock(self, name: str):
        """Fail fast on concurrent research operations; OS releases locks on exit."""
        path = self.path(f"locks/{name}.lock")
        with file_lock(path):
            yield

from contextlib import contextmanager
from pathlib import Path
import shutil

import pytest


@pytest.fixture
def pandoc():
    """Use an actual external Pandoc on every supported test platform."""
    binary = shutil.which("pandoc")
    if binary:
        return binary
    try:
        import pypandoc
        binary = pypandoc.get_pandoc_path()
    except (ImportError, OSError):
        pytest.skip("External Pandoc is unavailable; install Pandoc or test-only pypandoc_binary")
    if not Path(binary).is_file() and Path(binary).with_suffix(".exe").is_file():
        binary = str(Path(binary).with_suffix(".exe"))
    if not Path(binary).is_file():
        pytest.skip("External Pandoc executable is unavailable")
    return binary


@pytest.fixture
def fail_transaction(monkeypatch):
    """Inject one failure before commit or after its durable acknowledgement."""
    def install(ws, kind, *, after_commit=False, on_commit=None):
        original = ws._database
        armed = True

        @contextmanager
        def failing_database():
            nonlocal armed
            with original() as db:
                before = db.execute("SELECT id,data FROM records WHERE kind=? ORDER BY rowid", (kind,)).fetchall()
                yield db
                changed = before != db.execute("SELECT id,data FROM records WHERE kind=? ORDER BY rowid", (kind,)).fetchall()
                if armed and changed and not after_commit:
                    armed = False
                    raise OSError("Injected transaction failure before commit")
            if armed and changed and after_commit:
                armed = False
                if on_commit is not None:
                    on_commit()
                raise OSError("Injected acknowledgement failure after durable commit")

        monkeypatch.setattr(ws, "_database", failing_database)
    return install

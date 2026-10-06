"""Explicit bundled executables and one app-owned research controller."""

from contextlib import ExitStack
import os
from pathlib import Path
import stat
import time

from .autonomous import literature
from .autonomous.quickjs_runner import QuickJSRunner
from .workflow import SHUTDOWN_CLEANUP_SECONDS, WorkflowError, WorkflowService
from .workspace import ensure_unlinked, file_lock, loads_json, write_json

OWNER = {"format": "paper-factory-standalone-engine-v1", "app_id": "com.andongmin.paperfactory.standalone"}


def absolute_path(value: str | Path, *, file: bool = False) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("Runtime and data paths must be absolute")
    ensure_unlinked(path)
    path = path.resolve()
    if file:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Bundled executable must be an ordinary unlinked file")
    elif path.exists() and not path.is_dir():
        raise ValueError("Runtime and data directories must be directories")
    return path


class StandaloneRuntime:
    """Acquire home ownership before any service or supervisor recovery."""

    def __init__(self, home: Path, runtime_root: Path, node: Path, pandoc: Path):
        self.home = absolute_path(home)
        self.runtime_root = absolute_path(runtime_root)
        self.node = absolute_path(node, file=True)
        self.pandoc = absolute_path(pandoc, file=True)
        if not self.runtime_root.is_dir():
            raise ValueError("Bundled QuickJS runtime is missing")
        for immutable in (self.runtime_root, self.node, self.pandoc):
            if immutable == self.home or immutable.is_relative_to(self.home) or self.home.is_relative_to(immutable):
                raise ValueError("App data must be separate from immutable runtime resources")
        self._stack = ExitStack()
        self.service = None
        self.runner = None
        self._closed = False
        self._cancel = lambda: False
        try:
            # Fail closed on an existing unmarked directory. Never adopt plugin data.
            marker = self.home / "owner.json"
            ensure_unlinked(marker)
            if self.home.exists() and not marker.is_file():
                for child in self.home.iterdir():
                    ensure_unlinked(child)
                    if child.name not in {"temp", "matplotlib"} or not child.is_dir() or any(child.iterdir()):
                        raise ValueError("Existing engine data has no standalone ownership record")
            self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._stack.enter_context(file_lock(self.home / "engine.lock"))
            ensure_unlinked(marker)
            if marker.exists():
                if marker.stat().st_size > 1024 or loads_json(marker.read_bytes()) != OWNER:
                    raise ValueError("Engine data belongs to a different owner")
            else:
                write_json(marker, OWNER)
            # QuickJS and conversion receive checked absolute bundled executable
            # paths; neither path is discovered through the host environment.
            os.environ["PF_NODE_BIN"] = str(self.node)
            os.environ["PYPANDOC_PANDOC"] = str(self.pandoc)
            os.environ["MPLCONFIGDIR"] = str(self.home / "matplotlib")
            fonts = os.environ.get("TYPST_FONT_PATHS")
            if fonts:
                font_root = absolute_path(fonts)
                if not font_root.is_dir():
                    raise ValueError("Bundled fonts directory is missing")
                os.environ["TYPST_FONT_PATHS"] = str(font_root)
            # Prepare native plotting on the IPC main thread before its stdin
            # loop can block while an experiment worker imports NumPy.
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot
            self.runner = QuickJSRunner(self.runtime_root, supervisor_root=self.home / "supervisor", host_profile="private")
            self.service = WorkflowService(self.home, runner=self.runner, collector=self._collect)
        except Exception:
            try:
                if self.runner is not None:
                    self.runner.close()
            finally:
                self._stack.close()
            raise

    def _collect(self, queries, output_root, **options):
        options["cancel"] = self._cancel
        return literature.collect(queries, output_root, **options)

    def set_cancel(self, callback):
        # The command executor is serial; the input thread only sets its Event.
        self._cancel = callback

    def close(self, *, deadline: float | None = None):
        if self._closed:
            return
        deadline = deadline if deadline is not None else time.monotonic() + SHUTDOWN_CLEANUP_SECONDS
        error = None
        try:
            if self.service is not None:
                self.service.close(deadline=deadline)
        except Exception as exc:
            error = exc
        try:
            if self.runner is not None:
                self.runner.close(deadline=deadline)
        except Exception as exc:
            error = error or exc
        if error:
            if isinstance(error, WorkflowError):
                raise error
            raise WorkflowError("CLEANUP_UNCONFIRMED", "Local engine shutdown remains unconfirmed; retry shutdown") from error
        if time.monotonic() >= deadline:
            raise WorkflowError("CLEANUP_UNCONFIRMED", "Local engine shutdown did not finish before its deadline")
        self._stack.close()
        self._closed = True

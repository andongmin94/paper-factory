"""Explicit, bounded dotenv loading for application startup.

Library author loading remains side-effect free. Only a file named by the user
is read; current-directory and parent-directory dotenv discovery never occurs.
"""

import os
import re
import stat
from collections.abc import MutableMapping
from io import StringIO
from pathlib import Path

from dotenv.parser import parse_stream

from .author import AuthorProfile
from .workspace import ensure_unlinked

MAX_ENV_FILE_BYTES = 64 * 1024
ALLOWED_ENV_NAMES = frozenset({
    *(f"PF_AUTHOR_{field.upper()}" for field in AuthorProfile.model_fields),
    "PF_AUTHOR_PROFILE_JSON", "PF_HOME", "PF_OJS_API_TOKEN", "PYPANDOC_PANDOC",
    "PF_CODEX_BIN", "PF_CODEX_MODEL", "PF_CODEX_AUTH_HOME", "PF_RESEARCH_IMAGE",
})


def load_env_file(path: Path | str, *, environ: MutableMapping[str, str] | None = None) -> None:
    """Load allowed settings from an explicit UTF-8 dotenv file.

    Existing environment bindings, including empty ones, take precedence.
    Python-dotenv parses quotes and escapes, but interpolation and shell
    evaluation are never performed. Validate the whole file before mutation so
    a malformed later line cannot leave a partially applied configuration.
    Error messages identify the file and line without exposing setting values.
    """
    selected = Path(path).expanduser()
    ensure_unlinked(selected)
    try:
        metadata = selected.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"Environment file must be a regular file: {selected}")
        if metadata.st_size > MAX_ENV_FILE_BYTES:
            raise ValueError(f"Environment file exceeds 64 KiB: {selected}")
        with selected.open("rb") as stream:
            raw = stream.read(MAX_ENV_FILE_BYTES + 1)
    except OSError:
        raise OSError(f"Cannot read environment file: {selected}") from None
    if len(raw) > MAX_ENV_FILE_BYTES:
        raise ValueError(f"Environment file exceeds 64 KiB: {selected}")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"Environment file must contain UTF-8 text: {selected}") from None
    if "\x00" in text:
        line = len(re.findall(r"\r\n|\r|\n", text[:text.index("\x00")])) + 1
        raise ValueError(f"Invalid dotenv syntax in {selected}, line {line}")
    pending = {}
    for binding in parse_stream(StringIO(text)):
        # The parser's binding can include preceding blank lines. Report the
        # setting's actual line rather than the start of that whitespace.
        original = binding.original.string
        leading = original[:len(original) - len(original.lstrip())]
        line = binding.original.line + len(re.findall(r"\r\n|\r|\n", leading))
        if binding.error:
            raise ValueError(f"Invalid dotenv syntax in {selected}, line {line}")
        if binding.key in ALLOWED_ENV_NAMES:
            if binding.value is None:
                raise ValueError(f"Missing dotenv setting value in {selected}, line {line}")
            pending[binding.key] = binding.value
    environment = os.environ if environ is None else environ
    for key, value in pending.items():
        environment.setdefault(key, value)

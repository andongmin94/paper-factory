"""Private dotenv settings are explicit, bounded, and never executable."""

import os
from pathlib import Path

import pytest

from paper_factory.author import AuthorProfile, load_author
from paper_factory.config import ALLOWED_ENV_NAMES, MAX_ENV_FILE_BYTES, load_env_file


def test_known_settings_load_quotes_and_author_json_without_interpolation(tmp_path):
    path = tmp_path / "private.env"
    marker = tmp_path / "must-not-exist"
    path.write_text(
        "export PF_AUTHOR_DISPLAY_NAME='Private Researcher'\n"
        "PF_AUTHOR_EMAIL=researcher@example.org\n"
        "PF_AUTHOR_PROFILE_JSON='{" + '"affiliation":"Independent research","city":"Seoul"' + "}'\n"
        f"PF_HOME='$(touch {marker})'\n"
        "PF_AUTHOR_DEPARTMENT='${PRIVATE_VARIABLE}'\n"
        "PF_OJS_API_TOKEN='secret token # preserved'\n",
        encoding="utf-8",
    )
    environment = {"PRIVATE_VARIABLE": "must-not-expand"}
    assert load_env_file(path, environ=environment) is None
    assert environment["PF_HOME"] == f"$(touch {marker})"
    assert environment["PF_AUTHOR_DEPARTMENT"] == "${PRIVATE_VARIABLE}"
    assert environment["PF_OJS_API_TOKEN"] == "secret token # preserved"
    assert not marker.exists()
    profile = load_author(environ=environment)
    assert profile.display_name == "Private Researcher"
    assert profile.affiliation == "Independent research"
    assert profile.city == "Seoul"


def test_existing_bindings_including_empty_take_precedence(tmp_path):
    path = tmp_path / "private.env"
    path.write_text("PF_AUTHOR_DISPLAY_NAME=File name\nPF_AUTHOR_EMAIL=file@example.org\nPF_HOME=/tmp/file-home\n", encoding="utf-8")
    environment = {"PF_AUTHOR_DISPLAY_NAME": "Process name", "PF_AUTHOR_EMAIL": "", "PF_HOME": "/tmp/process-home"}
    before = dict(environment)
    load_env_file(path, environ=environment)
    assert environment == before
    profile = load_author(environ=environment, project_metadata={"email": "project@example.org"})
    assert profile.email == "project@example.org"


def test_worker_authentication_root_loads_without_replacing_platform_home(tmp_path):
    path = tmp_path / "private.env"
    path.write_text("PF_CODEX_AUTH_HOME=/tmp/private-worker\nCODEX_HOME=/untrusted/platform\n")
    environment = {"CODEX_HOME": "/platform/authentication"}
    load_env_file(path, environ=environment)
    assert environment == {"CODEX_HOME": "/platform/authentication", "PF_CODEX_AUTH_HOME": "/tmp/private-worker"}


def test_unknown_system_and_credential_settings_are_ignored(tmp_path):
    path = tmp_path / "private.env"
    path.write_text(
        "PATH=/untrusted/bin\nHOME=/untrusted/home\nPYTHONPATH=/untrusted/package\n"
        "LD_PRELOAD=/untrusted/library\nGITHUB_TOKEN=unknown-secret\nPF_AUTHOR_TOKEN=unknown-secret\n"
        "PF_AUTHOR_DISPLAY_NAME=Known setting\nPYPANDOC_PANDOC=/configured/pandoc\n",
        encoding="utf-8",
    )
    environment = {"PATH": "/trusted/bin", "HOME": "/trusted/home"}
    load_env_file(path, environ=environment)
    assert environment == {"PATH": "/trusted/bin", "HOME": "/trusted/home", "PF_AUTHOR_DISPLAY_NAME": "Known setting", "PYPANDOC_PANDOC": "/configured/pandoc"}
    assert {f"PF_AUTHOR_{name.upper()}" for name in AuthorProfile.model_fields}.issubset(ALLOWED_ENV_NAMES)


@pytest.mark.parametrize("malformed", ["PF_AUTHOR_EMAIL='private-secret-email", "PF_AUTHOR_EMAIL secret-value", "PF_AUTHOR_EMAIL", "PF_AUTHOR_EMAIL=private\x00secret"])
def test_malformed_diagnostics_show_file_and_line_without_values_or_partial_changes(tmp_path, malformed, caplog):
    path = tmp_path / "private.env"
    path.write_text("PF_AUTHOR_DISPLAY_NAME=Partial value must not apply\n" + malformed + "\n", encoding="utf-8")
    environment = {"PF_HOME": "/tmp/original-home"}
    before = dict(environment)
    with pytest.raises(ValueError) as raised:
        load_env_file(path, environ=environment)
    message = str(raised.value)
    assert str(path) in message
    assert "line 2" in message
    assert "private" not in message.replace(str(path), "")
    assert "secret-value" not in message
    assert "Partial value" not in message
    assert environment == before
    assert caplog.text == ""


def test_missing_nonregular_oversized_and_nonutf8_files_fail_privately(tmp_path):
    missing = tmp_path / "missing.env"
    with pytest.raises(OSError, match="Cannot read environment file"):
        load_env_file(missing, environ={})
    with pytest.raises(ValueError, match="regular file"):
        load_env_file(tmp_path, environ={})
    oversized = tmp_path / "large.env"
    oversized.write_bytes(b"x" * (MAX_ENV_FILE_BYTES + 1))
    with pytest.raises(ValueError, match="64 KiB"):
        load_env_file(oversized, environ={})
    invalid = tmp_path / "invalid.env"
    invalid.write_bytes(b"PF_OJS_API_TOKEN=private-secret\xff")
    with pytest.raises(ValueError) as raised:
        load_env_file(invalid, environ={})
    assert "UTF-8" in str(raised.value)
    assert "private-secret" not in str(raised.value)


def test_symlink_env_file_is_rejected(tmp_path):
    private = tmp_path / "private.env"
    private.write_text("PF_OJS_API_TOKEN=private-secret\n")
    linked = tmp_path / "linked.env"
    try:
        linked.symlink_to(private)
    except OSError:
        pytest.skip("Symlinks are unavailable on this platform")
    with pytest.raises(ValueError, match="symlinks"):
        load_env_file(linked, environ={})


def test_default_mapping_updates_process_environment_only_when_called(tmp_path, monkeypatch):
    # Record an undo operation even when the setting was originally absent;
    # the loader mutates os.environ outside monkeypatch's own methods.
    monkeypatch.setenv("PF_AUTHOR_CITY", "temporary-before-test")
    monkeypatch.delenv("PF_AUTHOR_CITY", raising=False)
    path = tmp_path / "private.env"
    path.write_text("PF_AUTHOR_CITY=Seoul\n")
    assert "PF_AUTHOR_CITY" not in os.environ
    load_env_file(path)
    assert os.environ["PF_AUTHOR_CITY"] == "Seoul"


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_malformed_line_number_accounts_for_preceding_blank_lines(tmp_path, newline):
    path = tmp_path / "private.env"
    path.write_bytes((newline + newline + "  PF_AUTHOR_EMAIL='private-secret" + newline).encode())
    with pytest.raises(ValueError) as raised:
        load_env_file(path, environ={})
    assert "line 3" in str(raised.value)
    assert "private-secret" not in str(raised.value)

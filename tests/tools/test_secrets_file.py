# SYNTHETIC: every credential and id below is a made-up placeholder.
"""Secrets file support in app.config (T-039): location rules, precedence, file format."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import (
    REPO_ROOT,
    SecretsFileError,
    Settings,
    default_secrets_file,
    resolve_secrets_file,
)

ID = "synthetic-client-id-7"
SECRET = "synthetic#secret=7"  # '#' and '=' must survive the quoting
USER_ID = "900000123"


def ps_style_file(path: Path, *, bom: bool = False, extra: str = "") -> Path:
    """Exactly the layout scripts/windows/setup-avito-credentials.ps1 writes: two Turkish comment
    lines, KEY='value' lines, CRLF, UTF-8 (the script writes no BOM; Notepad may add one)."""
    lines = [
        "# Avito Müşteri Asistanı — gizli ayarlar. Git'e eklemeyin, kimseyle paylaşmayın.",
        "# Oluşturan: scripts/windows/setup-avito-credentials.ps1 (yeniden çalıştırarak "
        "güncelleyin).",
        f"AVITO_CLIENT_ID='{ID}'",
        f"AVITO_CLIENT_SECRET='{SECRET}'",
        f"AVITO_USER_ID='{USER_ID}'",
    ]
    if extra:
        lines.append(extra)
    data = ("\r\n".join(lines) + "\r\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)
    return path


@pytest.mark.parametrize("bom", [False, True])
def test_loads_file_written_by_setup_script(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bom: bool
) -> None:
    secrets = ps_style_file(tmp_path / "local" / "secrets.env", bom=bom)
    monkeypatch.setenv("ASSISTANT_SECRETS_FILE", str(secrets))
    settings = Settings()
    assert settings.avito_client_id is not None
    assert settings.avito_client_id.get_secret_value() == ID
    assert settings.avito_client_secret is not None
    assert settings.avito_client_secret.get_secret_value() == SECRET
    assert settings.avito_user_id == int(USER_ID)


def test_secret_values_and_user_id_not_in_repr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secrets = ps_style_file(tmp_path / "local" / "secrets.env")
    monkeypatch.setenv("ASSISTANT_SECRETS_FILE", str(secrets))
    text = repr(Settings()) + str(Settings())
    for value in (ID, SECRET, USER_ID, str(secrets)):
        assert value not in text


def test_precedence_environment_then_secrets_file_then_dotenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ASSISTANT_SECRETS_FILE")  # read from .env in this test
    secrets = ps_style_file(tmp_path / "local" / "secrets.env", extra="DATA_DIR=")
    Path(".env").write_text(
        f"ASSISTANT_SECRETS_FILE={secrets}\n"
        "AVITO_CLIENT_ID=from-dotenv\nAVITO_CLIENT_SECRET=from-dotenv\n"
        "AUTOMATION_MODE=approve_to_send\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AVITO_CLIENT_SECRET", "from-environment")
    settings = Settings()
    assert settings.avito_client_id is not None
    assert settings.avito_client_id.get_secret_value() == ID  # file beats .env
    assert settings.avito_client_secret is not None
    assert settings.avito_client_secret.get_secret_value() == "from-environment"
    assert settings.automation_mode.value == "approve_to_send"  # .env still used


def test_explicit_path_must_exist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASSISTANT_SECRETS_FILE", str(tmp_path / "missing.env"))
    with pytest.raises(SecretsFileError):
        Settings()


def test_none_disables_the_secrets_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ps_style_file(tmp_path / "AvitoAssistant" / "secrets.env")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("ASSISTANT_SECRETS_FILE", "None")
    assert Settings().avito_client_id is None


def test_refuses_file_inside_repository() -> None:
    # The location check runs before the existence check: nothing is written into the repo.
    with pytest.raises(SecretsFileError, match="outside the git repository"):
        resolve_secrets_file(str(REPO_ROOT / "secrets.env"))
    with pytest.raises(SecretsFileError):
        resolve_secrets_file(str(REPO_ROOT / "data" / "private" / "secrets.env"))


def test_refuses_file_inside_repository_via_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSISTANT_SECRETS_FILE", str(REPO_ROOT / "tests" / "secrets.env"))
    with pytest.raises(SecretsFileError):
        Settings()


@pytest.mark.parametrize("marker", [".git", ".obsidian"])
def test_refuses_file_inside_other_git_tree_or_vault(tmp_path: Path, marker: str) -> None:
    root = tmp_path / "somewhere"
    (root / marker).mkdir(parents=True)
    secrets = ps_style_file(root / "notes" / "secrets.env")
    with pytest.raises(SecretsFileError):
        resolve_secrets_file(str(secrets))


def test_expands_environment_variables(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    secrets = ps_style_file(tmp_path / "AvitoAssistant" / "secrets.env")
    monkeypatch.setenv("SYNTHETIC_BASE", str(tmp_path))
    assert resolve_secrets_file("$SYNTHETIC_BASE/AvitoAssistant/secrets.env") == secrets.resolve()


def test_windows_default_location(tmp_path: Path) -> None:
    environ = {"LOCALAPPDATA": str(tmp_path)}
    expected = tmp_path / "AvitoAssistant" / "secrets.env"
    assert default_secrets_file(environ, "win32") == expected
    assert default_secrets_file(environ, "linux") is None
    assert default_secrets_file({}, "win32") is None
    # Used only when it exists.
    assert resolve_secrets_file(None, environ, "win32") is None
    ps_style_file(expected)
    assert resolve_secrets_file(None, environ, "win32") == expected.resolve()
    assert resolve_secrets_file("", environ, "win32") == expected.resolve()
    assert resolve_secrets_file(None, environ, "linux") is None


def test_windows_default_is_loaded_by_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ASSISTANT_SECRETS_FILE")
    ps_style_file(tmp_path / "AvitoAssistant" / "secrets.env")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "platform", "win32")
    settings = Settings()
    assert settings.avito_client_id is not None
    assert settings.avito_client_id.get_secret_value() == ID


def test_no_default_file_means_no_secrets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ASSISTANT_SECRETS_FILE")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "platform", "win32")
    assert Settings().avito_client_id is None


@pytest.mark.parametrize("value", ["abc", "0", "-5"])
def test_rejects_invalid_user_id(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("AVITO_USER_ID", value)
    with pytest.raises(ValidationError):
        Settings()


def test_root_fixture_disables_secrets_file_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """tests/conftest.py sets ASSISTANT_SECRETS_FILE=none: even an existing Windows default
    file is ignored unless a test unsets the variable."""
    ps_style_file(tmp_path / "AvitoAssistant" / "secrets.env")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "platform", "win32")
    assert os.environ["ASSISTANT_SECRETS_FILE"] == "none"
    assert Settings().avito_client_id is None

# SYNTHETIC: all setting values below are placeholders, not real credentials.
"""Tests for app.config.Settings."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import REPO_ROOT, AutomationMode, Settings

ENV_NAMES = [
    "AVITO_CLIENT_ID",
    "AVITO_CLIENT_SECRET",
    "DATABASE_URL",
    "DATA_DIR",
    "AUTOMATION_MODE",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    # Run from an empty directory so a developer's local .env is not picked up.
    monkeypatch.chdir(tmp_path)


def test_defaults_are_draft_only_and_unset() -> None:
    settings = Settings()
    assert settings.automation_mode is AutomationMode.DRAFT_ONLY
    assert settings.avito_client_id is None
    assert settings.data_dir is None


def test_reads_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AVITO_CLIENT_SECRET", "synthetic-secret")
    monkeypatch.setenv("AUTOMATION_MODE", "approve_to_send")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    settings = Settings()
    assert settings.automation_mode is AutomationMode.APPROVE_TO_SEND
    assert settings.avito_client_secret is not None
    assert settings.avito_client_secret.get_secret_value() == "synthetic-secret"
    assert settings.data_dir == (tmp_path / "data").resolve()


def test_reads_dotenv_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("AVITO_CLIENT_ID=synthetic-id\nDATA_DIR=\n", encoding="utf-8")
    settings = Settings()
    assert settings.avito_client_id is not None
    assert settings.avito_client_id.get_secret_value() == "synthetic-id"
    assert settings.data_dir is None  # empty value means "not set"


def test_secrets_not_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AVITO_CLIENT_SECRET", "synthetic-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:synthetic-pw@localhost/db")
    text = repr(Settings())
    assert "synthetic-secret" not in text
    assert "synthetic-pw" not in text


def test_rejects_unknown_automation_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOMATION_MODE", "send_everything")
    with pytest.raises(ValidationError):
        Settings()


def test_rejects_data_dir_inside_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(REPO_ROOT / "data"))
    with pytest.raises(ValidationError):
        Settings()

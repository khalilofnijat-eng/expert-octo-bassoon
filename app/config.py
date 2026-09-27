"""Application settings, read from environment variables and an optional local ``.env`` file.

The ``.env`` file is never committed (see ``.env.example`` for the variable names). Secret
values are wrapped in ``SecretStr`` so they do not appear in ``repr()`` or logs.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class AutomationMode(StrEnum):
    """How far the assistant may act on its own (docs/DECISIONS.md D-006). Pilot modes only.

    ``auto_scoped`` is a future, post-pilot value (ARCHITECTURE §15, MA-2) and is deliberately not
    accepted here. The source of truth at runtime is ``system_setting.automation_mode`` in the
    database; this environment value only seeds that row when the first migration runs.
    """

    DRAFT_ONLY = "draft_only"
    APPROVE_TO_SEND = "approve_to_send"


class AppEnv(StrEnum):
    """Runtime environment, from ``APP_ENV``. Same values and fail-safe rule as
    ``app.catalog.runtime``: unset, empty or unknown means ``production``."""

    PRODUCTION = "production"
    DEVELOPMENT = "development"
    TEST = "test"


class Settings(BaseSettings):
    """Runtime configuration. All fields are optional so the app can start without secrets."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # An empty value (as in a copied .env.example) means "not set".
        env_ignore_empty=True,
    )

    avito_client_id: SecretStr | None = None
    avito_client_secret: SecretStr | None = None
    # May contain a password, therefore treated as a secret.
    database_url: SecretStr | None = None
    # Live data (database files, raw Avito data, photo cache). Must live outside git and the vault.
    data_dir: Path | None = None
    # Seed for system_setting.automation_mode only (see AutomationMode).
    automation_mode: AutomationMode = AutomationMode.DRAFT_ONLY
    app_env: AppEnv = AppEnv.PRODUCTION
    # Worker (docs/ARCHITECTURE.md §6.1): how often the singleton connection is checked (each check
    # has the same hard deadline), and how long a job waits when its conversation lock is busy.
    # A new worker waits 2 x worker_singleton_poll_s after taking the singleton before recovery.
    worker_singleton_poll_s: float = 5.0
    worker_lock_busy_delay_s: float = 5.0

    @field_validator("app_env", mode="before")
    @classmethod
    def _unknown_env_is_production(cls, value: object) -> object:
        text = str(value or "").strip().lower()
        return text if text in {e.value for e in AppEnv} else AppEnv.PRODUCTION

    @field_validator("data_dir")
    @classmethod
    def _data_dir_outside_repo(cls, value: Path | None) -> Path | None:
        if value is None:
            return None
        resolved = value.expanduser().resolve()
        if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
            raise ValueError("DATA_DIR must be outside the git repository")
        return resolved


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()

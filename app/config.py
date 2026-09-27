"""Application settings, read from environment variables, an optional secrets file and an
optional local ``.env`` file.

The ``.env`` file is never committed (see ``.env.example`` for the variable names). Secret
values are wrapped in ``SecretStr`` so they do not appear in ``repr()`` or logs.

Secrets file (T-039): a dotenv-format file outside the repository and outside the Obsidian vault,
written on Windows by ``scripts/windows/setup-avito-credentials.ps1``. Its path is
``ASSISTANT_SECRETS_FILE`` (process environment or ``.env``); if that is unset, the platform default
(Windows: ``%LOCALAPPDATA%\\AvitoAssistant\\secrets.env``) is used when the file exists.
``ASSISTANT_SECRETS_FILE=none`` turns the file off (e.g. for tests). Precedence, highest first:
constructor arguments, process environment, secrets file, ``.env``, field defaults. A secrets file
inside this repository, another git working tree or an Obsidian vault is refused
(:class:`SecretsFileError`); so is an ``ASSISTANT_SECRETS_FILE`` that points to a missing file.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

SECRETS_FILE_ENV = "ASSISTANT_SECRETS_FILE"
# ``ASSISTANT_SECRETS_FILE=none`` disables the secrets file, platform default included.
SECRETS_FILE_DISABLED = "none"
SECRETS_DIR_NAME = "AvitoAssistant"
SECRETS_FILE_NAME = "secrets.env"


class SecretsFileError(ValueError):
    """The secrets file is missing (explicit path) or in a place where it must not be."""


def default_secrets_file(
    environ: Mapping[str, str] | None = None, platform: str | None = None
) -> Path | None:
    """The platform default location, whether or not the file exists.

    Windows only: ``%LOCALAPPDATA%\\AvitoAssistant\\secrets.env``. Other platforms have no
    default (use ``ASSISTANT_SECRETS_FILE``).
    """
    environ = os.environ if environ is None else environ
    platform = sys.platform if platform is None else platform
    if platform != "win32":
        return None
    local = environ.get("LOCALAPPDATA", "").strip()
    if not local:
        return None
    return Path(local) / SECRETS_DIR_NAME / SECRETS_FILE_NAME


def check_secrets_location(path: Path) -> Path:
    """Resolve ``path`` and refuse it inside this repository, any git working tree or an
    Obsidian vault (a folder with ``.obsidian``). Returns the resolved path."""
    resolved = path.expanduser().resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise SecretsFileError("secrets file must be outside the git repository")
    for parent in resolved.parents:
        if (parent / ".git").exists():
            raise SecretsFileError("secrets file must not be inside a git working tree")
        if (parent / ".obsidian").is_dir():
            raise SecretsFileError("secrets file must not be inside an Obsidian vault")
    return resolved


def resolve_secrets_file(
    configured: str | None,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> Path | None:
    """The secrets file to load, or ``None``.

    ``configured`` is the ``ASSISTANT_SECRETS_FILE`` value (environment or ``.env``). Set: it must
    exist (``%VAR%``/``$VAR`` and ``~`` are expanded). Unset or empty: the platform default is
    used if it exists. ``none``: no file.
    """
    text = (configured or "").strip()
    if text.lower() == SECRETS_FILE_DISABLED:
        return None
    if text:
        path = Path(os.path.expandvars(text))
        resolved = check_secrets_location(path)
        if not resolved.is_file():
            raise SecretsFileError(f"{SECRETS_FILE_ENV} points to a file that does not exist")
        return resolved
    default = default_secrets_file(environ, platform)
    if default is None or not default.is_file():
        return None
    return check_secrets_location(default)


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
    # Numeric Avito account id (``user_id``). Optional: ``GET /core/v1/accounts/self`` returns it.
    # Not a secret, but an identifier: kept out of repr.
    avito_user_id: int | None = Field(default=None, gt=0, repr=False)
    # Where the secrets file is (see the module docstring). Only read to locate that file.
    assistant_secrets_file: str | None = Field(default=None, repr=False)
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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        configured: object = None
        for source in (init_settings, env_settings, dotenv_settings):
            configured = source().get("assistant_secrets_file")
            if configured:
                break
        path = resolve_secrets_file(str(configured) if configured else None)
        if path is None:
            return init_settings, env_settings, dotenv_settings, file_secret_settings
        # utf-8-sig: a byte order mark (Windows Notepad) must not become part of the first key.
        secrets_file = DotEnvSettingsSource(
            settings_cls, env_file=path, env_file_encoding="utf-8-sig"
        )
        return init_settings, env_settings, secrets_file, dotenv_settings, file_secret_settings

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

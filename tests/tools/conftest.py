# SYNTHETIC: all data used by tests/tools is made up (see scripts/dev/avito_mock).
"""Shared fixtures for tests/tools. No test here touches the network or a real secrets file."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

SETTINGS_ENV = [
    "AVITO_CLIENT_ID",
    "AVITO_CLIENT_SECRET",
    "AVITO_USER_ID",
    "ASSISTANT_SECRETS_FILE",
    "DATABASE_URL",
    "DATA_DIR",
    "AUTOMATION_MODE",
    "APP_ENV",
    "LOCALAPPDATA",
    "AVITO_GATEWAY_BASE_URL",
]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No developer or owner settings leak in: clean environment, empty working directory."""
    for name in SETTINGS_ENV:
        monkeypatch.delenv(name, raising=False)
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)


@pytest.fixture(autouse=True)
def _restore_logger_levels() -> Iterator[None]:
    """main() quiets the gateway and httpx loggers; other tests must not inherit that."""
    names = ["app.avito_gateway", "httpx"]
    levels = {name: logging.getLogger(name).level for name in names}
    yield
    for name, level in levels.items():
        logging.getLogger(name).setLevel(level)

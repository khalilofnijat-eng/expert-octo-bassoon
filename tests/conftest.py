"""Root test fixtures shared by every test directory."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_real_secrets_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never load the owner's secrets file (T-039b).

    On Windows, ``app.config`` would otherwise pick up ``%LOCALAPPDATA%\\AvitoAssistant\\
    secrets.env`` whenever it exists. A test that needs another value sets or deletes
    ``ASSISTANT_SECRETS_FILE`` itself; monkeypatch undoes it after that test.
    """
    monkeypatch.setenv("ASSISTANT_SECRETS_FILE", "none")

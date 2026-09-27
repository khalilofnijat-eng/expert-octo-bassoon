# SYNTHETIC: all data used by tests/avito is made up (see scripts/dev/avito_mock).
"""Async tests run on anyio's pytest plugin with the asyncio backend."""

from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

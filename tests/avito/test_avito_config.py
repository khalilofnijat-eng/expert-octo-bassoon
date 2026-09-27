# SYNTHETIC: no real credentials or hosts.
"""Gateway config: defaults, URL checks, env tunables."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.avito_gateway import GatewayConfig


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import os

    for name in list(os.environ):
        if name.startswith("AVITO_GATEWAY_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)  # no developer .env


def test_defaults() -> None:
    cfg = GatewayConfig()
    assert cfg.base_url == "https://api.avito.ru"
    assert cfg.page_limit_default == 50
    assert cfg.page_limit_max == 99
    assert cfg.offset_max == 1000
    assert cfg.bulk_share == 0.5
    assert cfg.rate_limit_for("items_list").per_minute == 25
    assert cfg.rate_limit_for("item_detail").per_minute == 500
    assert cfg.rate_limit_for("unknown") == cfg.default_rate_limit


def test_env_tunables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AVITO_GATEWAY_READ_TIMEOUT_S", "3.5")
    monkeypatch.setenv("AVITO_GATEWAY_BULK_SHARE", "0.25")
    monkeypatch.setenv("AVITO_GATEWAY_BASE_URL", "https://avito-mock.invalid/")
    cfg = GatewayConfig()
    assert cfg.read_timeout_s == 3.5
    assert cfg.bulk_share == 0.25
    assert cfg.base_url == "https://avito-mock.invalid"


@pytest.mark.parametrize(
    "url",
    [
        "http://api.avito.ru",
        "ftp://api.avito.ru",
        "api.avito.ru",
        "https://api.avito.ru/v1",
        "https://api.avito.ru?x=1",
    ],
)
def test_bad_base_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        GatewayConfig(base_url=url)


def test_http_only_when_allowed() -> None:
    cfg = GatewayConfig(base_url="http://127.0.0.1:8081", allow_insecure_http=True)
    assert cfg.base_url == "http://127.0.0.1:8081"


@pytest.mark.parametrize(
    "overrides",
    [
        {"page_limit_max": 101},
        {"bulk_share": 0},
        {"bulk_share": 1.5},
        {"page_limit_default": 99, "page_limit_max": 50},
    ],
)
def test_invalid_values(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        GatewayConfig(**overrides)

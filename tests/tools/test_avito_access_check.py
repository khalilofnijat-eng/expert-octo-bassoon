# SYNTHETIC: credentials, tokens, ids, names and texts come from the mock and are made up.
"""scripts/avito_access_check.py (T-039): at most four read calls, statuses only, no secrets."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from app.avito_gateway import AvitoReadClient, GatewayConfig
from app.avito_gateway.http import silence_httpx_url_logs
from app.config import REPO_ROOT
from scripts import avito_access_check as check
from scripts.dev.avito_mock import (
    MOCK_BASE_URL,
    SYNTHETIC_CLIENT_ID,
    SYNTHETIC_CLIENT_SECRET,
    SYNTHETIC_USER_ID,
    AvitoMock,
    config_for_mock,
    forbidden,
    rate_limited,
    unauthorized,
)

ALLOWED_ENDPOINTS = {"token", "accounts_self", "items_list", "chats_list"}


def make_mock() -> AvitoMock:
    return AvitoMock.with_synthetic_data(n_chats=3, messages_per_chat=4, n_items=2)


def client_for(mock: AvitoMock) -> AvitoReadClient:
    return AvitoReadClient(
        config_for_mock(refresh_on_401=False), mock.credentials(), transport=mock.transport()
    )


async def run(mock: AvitoMock, configured_user_id: int | None = None) -> check.AccessReport:
    async with client_for(mock) as client:
        return await check.run_access_check(client, configured_user_id=configured_user_id)


def sensitive_values(mock: AvitoMock) -> list[str]:
    """Everything that must never appear in the output or logs."""
    values = [SYNTHETIC_CLIENT_ID, SYNTHETIC_CLIENT_SECRET, str(SYNTHETIC_USER_ID)]
    values += mock.issued_tokens
    for chat in mock.chats.values():
        values += [chat.id, chat.customer_name, str(chat.customer_id)]
        for message in chat.messages:
            values += [message["id"], message["content"]["text"]]
    for item in mock.items:
        values += [str(item["id"]), item["title"], item["url"]]
    values += ["70000000000", "seller@example.com", "Синтетический продавец", MOCK_BASE_URL]
    return values


def assert_only_allowed_calls(mock: AvitoMock) -> None:
    assert mock.forbidden_hits == []
    assert {r.endpoint for r in mock.requests} <= ALLOWED_ENDPOINTS
    for endpoint in ALLOWED_ENDPOINTS:
        assert mock.count(endpoint) <= 1, endpoint
    assert all(r.method == "GET" for r in mock.requests if r.endpoint != "token")
    assert not any(r.path.endswith("/read") for r in mock.requests)  # chatRead never called


@pytest.mark.anyio
async def test_all_ok() -> None:
    mock = make_mock()
    report = await run(mock)
    assert report.all_ok
    assert report.account_id_tail == str(SYNTHETIC_USER_ID)[-3:]
    assert [mock.count(e) for e in ("token", "accounts_self", "items_list", "chats_list")] == [
        1,
        1,
        1,
        1,
    ]
    assert_only_allowed_calls(mock)
    items = next(r for r in mock.requests if r.endpoint == "items_list")
    chats = next(r for r in mock.requests if r.endpoint == "chats_list")
    assert items.query["per_page"] == ["1"]
    assert chats.query["limit"] == ["1"]
    text = "\n".join(check.format_report(report, dry_run=False))
    assert "Token: OK" in text
    assert f"son 3 hane …{str(SYNTHETIC_USER_ID)[-3:]}" in text
    assert "Items API erişilebilir: evet (HTTP 200)" in text
    assert "Messenger API erişilebilir: evet (HTTP 200)" in text
    assert "KURU ÇALIŞTIRMA" not in text


@pytest.mark.anyio
async def test_messenger_403_reports_tariff_hint() -> None:
    mock = make_mock()
    mock.inject(forbidden(), endpoint="chats_list")
    report = await run(mock)
    assert not report.all_ok
    assert report.items is not None and report.items.ok
    assert report.messenger is not None and report.messenger.status == 403
    assert mock.count("chats_list") == 1  # no retry
    assert_only_allowed_calls(mock)
    text = "\n".join(check.format_report(report, dry_run=False))
    assert "Messenger API erişilebilir: hayır (HTTP 403" in text
    assert check.MESSENGER_403_HINT in text


@pytest.mark.anyio
async def test_token_401_stops_without_retry() -> None:
    mock = make_mock()
    mock.inject(unauthorized(), endpoint="token")
    report = await run(mock)
    assert not report.token.ok and report.token.status == 401
    assert report.account is None and report.items is None and report.messenger is None
    assert len(mock.requests) == 1 and mock.requests[0].endpoint == "token"
    text = "\n".join(check.format_report(report, dry_run=False))
    assert "Token: BAŞARISIZ (HTTP 401)" in text
    assert "Diğer kontroller yapılmadı." in text


@pytest.mark.anyio
async def test_accounts_self_failure_uses_configured_user_id() -> None:
    mock = make_mock()
    mock.inject(forbidden(), endpoint="accounts_self")
    report = await run(mock, configured_user_id=SYNTHETIC_USER_ID)
    assert report.account is not None and report.account.status == 403
    assert report.messenger is not None and report.messenger.ok
    assert_only_allowed_calls(mock)


@pytest.mark.anyio
async def test_no_user_id_skips_messenger() -> None:
    mock = make_mock()
    mock.inject(forbidden(), endpoint="accounts_self")
    report = await run(mock)
    assert report.messenger is not None and report.messenger.skipped
    assert mock.count("chats_list") == 0
    assert "Messenger API erişilebilir: denenmedi" in "\n".join(
        check.format_report(report, dry_run=False)
    )


@pytest.mark.anyio
async def test_rate_limited_items_is_reported_not_retried() -> None:
    mock = make_mock()
    mock.inject(rate_limited("1"), endpoint="items_list")
    report = await run(mock)
    assert report.items is not None and report.items.status == 429
    assert mock.count("items_list") == 1
    assert report.messenger is not None and report.messenger.ok


@pytest.mark.anyio
async def test_configured_user_id_mismatch_is_reported_without_values() -> None:
    mock = make_mock()
    report = await run(mock, configured_user_id=SYNTHETIC_USER_ID + 1)
    assert report.configured_id_matches is False
    text = "\n".join(check.format_report(report, dry_run=False))
    assert "AYNI DEĞİL" in text
    assert str(SYNTHETIC_USER_ID + 1) not in text


@pytest.mark.anyio
@pytest.mark.parametrize("fault", [None, "messenger-403", "token-401", "self-403"])
async def test_no_secrets_or_ids_in_output_or_logs(
    caplog: pytest.LogCaptureFixture, fault: str | None
) -> None:
    caplog.set_level(logging.DEBUG)  # every logger, httpx included
    silence_httpx_url_logs()
    mock = make_mock()
    if fault == "messenger-403":
        mock.inject(forbidden(), endpoint="chats_list")
    elif fault == "token-401":
        mock.inject(unauthorized(), endpoint="token")
    elif fault == "self-403":
        mock.inject(forbidden(), endpoint="accounts_self")
    report = await run(mock, configured_user_id=SYNTHETIC_USER_ID)
    output = "\n".join(check.format_report(report, dry_run=False)) + repr(report)
    logs = caplog.text
    for value in sensitive_values(mock):
        assert value not in output, value
        assert value not in logs, value


def test_dry_run_main_scenarios(capsys: pytest.CaptureFixture[str]) -> None:
    assert check.main(["--dry-run"]) == check.EXIT_OK
    out = capsys.readouterr().out
    assert out.startswith("KURU ÇALIŞTIRMA")
    assert "Messenger API erişilebilir: evet" in out

    assert check.main(["--dry-run", "--scenario", "messenger-403"]) == check.EXIT_ACCESS_PROBLEM
    assert check.MESSENGER_403_HINT in capsys.readouterr().out

    assert check.main(["--dry-run", "--scenario", "token-401"]) == check.EXIT_ACCESS_PROBLEM
    out = capsys.readouterr().out
    assert "Token: BAŞARISIZ (HTTP 401)" in out
    for value in (SYNTHETIC_CLIENT_ID, SYNTHETIC_CLIENT_SECRET, str(SYNTHETIC_USER_ID)):
        assert value not in out


def test_live_path_with_settings_against_mock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The non-dry-run path end to end: credentials from a secrets file, the default gateway
    config (real rate limits, refresh_on_401=False), transport swapped for the mock."""
    secrets = tmp_path / "local" / "secrets.env"
    secrets.parent.mkdir()
    secrets.write_text(
        f"AVITO_CLIENT_ID='{SYNTHETIC_CLIENT_ID}'\r\n"
        f"AVITO_CLIENT_SECRET='{SYNTHETIC_CLIENT_SECRET}'\r\n"
        f"AVITO_USER_ID='{SYNTHETIC_USER_ID}'\r\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ASSISTANT_SECRETS_FILE", str(secrets))
    monkeypatch.setenv("AVITO_GATEWAY_BASE_URL", MOCK_BASE_URL)
    mock = make_mock()
    seen: list[GatewayConfig] = []

    def fake_client(config: GatewayConfig, credentials: Any, **_: Any) -> AvitoReadClient:
        seen.append(config)
        return AvitoReadClient(config, credentials, transport=mock.transport())

    monkeypatch.setattr(check, "AvitoReadClient", fake_client)
    assert check.main([]) == check.EXIT_OK
    out = capsys.readouterr().out
    assert seen and seen[0].refresh_on_401 is False
    assert "Gizli dosya: bulundu" in out
    assert "AVITO_USER_ID: ayarlı ve API'nin döndürdüğü kimlikle aynı" in out
    assert "KURU ÇALIŞTIRMA" not in out
    assert_only_allowed_calls(mock)
    for value in [*sensitive_values(mock), str(secrets)]:
        assert value not in out, value


def test_missing_credentials_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    assert check.main([]) == check.EXIT_CONFIG_PROBLEM
    assert "AVITO_CLIENT_ID / AVITO_CLIENT_SECRET ayarlı değil" in capsys.readouterr().out


def test_secrets_file_inside_repo_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ASSISTANT_SECRETS_FILE", str(REPO_ROOT / "secrets.env"))
    assert check.main([]) == check.EXIT_CONFIG_PROBLEM
    assert "gizli dosya kullanılamıyor" in capsys.readouterr().out


def test_invalid_setting_reports_field_name_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AVITO_USER_ID", "not-a-number-synthetic")
    assert check.main([]) == check.EXIT_CONFIG_PROBLEM
    out = capsys.readouterr().out
    assert "avito_user_id" in out
    assert "not-a-number-synthetic" not in out


def test_scenario_requires_dry_run() -> None:
    with pytest.raises(SystemExit):
        check.main(["--scenario", "token-401"])

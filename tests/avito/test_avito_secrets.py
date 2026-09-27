# SYNTHETIC: credentials, tokens, texts and phone numbers below are made up.
"""Secrets (client id/secret, access tokens) never reach logs, exceptions or repr."""

from __future__ import annotations

import logging

import pytest
from pydantic import SecretStr

from app.avito_gateway import (
    AvitoApiError,
    AvitoReadClient,
    Credentials,
    MissingCredentialsError,
    paginate_messages,
)
from app.config import Settings
from scripts.dev.avito_mock import (
    SYNTHETIC_CLIENT_ID,
    SYNTHETIC_CLIENT_SECRET,
    SYNTHETIC_USER_ID,
    AvitoMock,
    connect_error,
    malformed_json,
    rate_limited,
    server_error,
    timeout,
    unauthorized,
    wrong_shape,
)
from tests.avito.helpers import make_client

pytestmark = pytest.mark.anyio

U = SYNTHETIC_USER_ID
CHAT = "u2i-synthetic0000~chat"
PHONE = "+7 900 000-00-99"


async def test_no_secret_in_logs_exceptions_or_repr(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)  # every logger, httpx included
    mock = AvitoMock.with_synthetic_data(n_chats=2, messages_per_chat=6)
    mock.add_message(CHAT, f"Синтетика: позвоните {PHONE}")
    errors: list[AvitoApiError] = []
    reprs: list[str] = []
    async with make_client(mock, max_retry_after_s=0.01) as client:
        me = await client.get_self()
        reprs += [repr(client), repr(client.tokens), repr(me), repr(client.config)]
        reprs.append(repr(await client.tokens.get()))
        async for page in paginate_messages(client, U, CHAT, limit=3):
            reprs.append(repr(page))
        mock.revoke_tokens()  # 401 → refresh → new token
        await client.list_chats(U)
        for fault, endpoint in [
            (unauthorized(), "chats_list"),
            (unauthorized(), "chats_list"),
            (rate_limited("1"), "chats_list"),
            (server_error(503), "chats_list"),
            (timeout(), "chats_list"),
            (connect_error(), "chats_list"),
            (malformed_json(), "chats_list"),
            (wrong_shape({"access_token": mock.issued_tokens[-1]}), "chats_list"),
            (server_error(500), "token"),
        ]:
            mock.inject(fault, endpoint=endpoint, times=1)
            if endpoint == "token":
                client.tokens.invalidate()
            try:
                await client.list_chats(U)
            except AvitoApiError as exc:
                errors.append(exc)
        reprs.append(repr(client.tokens))

    assert len(errors) == 7  # the two single 401s recover through a token refresh
    assert len(mock.issued_tokens) >= 2
    secrets = [SYNTHETIC_CLIENT_ID, SYNTHETIC_CLIENT_SECRET, *mock.issued_tokens]
    haystacks = {
        "log text": caplog.text,
        "log args": " ".join(repr(r.args) for r in caplog.records),
        "exceptions": " ".join(f"{e!s} {e!r} {e.args!r}" for e in errors),
        "reprs": " ".join(reprs),
    }
    for where, text in haystacks.items():
        for secret in secrets:
            assert secret not in text, f"secret leaked into {where}"
    # Chained httpx exceptions would carry the request and its Authorization header.
    assert all(e.__cause__ is None for e in errors)
    # Our own log lines carry no message text, phone numbers or raw bodies either.
    ours = " ".join(r.getMessage() for r in caplog.records if r.name.startswith("app."))
    assert PHONE not in ours
    assert "Синтетика" not in ours
    assert CHAT not in ours


def test_credentials_repr_and_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    creds = Credentials(SecretStr(SYNTHETIC_CLIENT_ID), SecretStr(SYNTHETIC_CLIENT_SECRET))
    text = f"{creds!r} {creds!s}"
    assert SYNTHETIC_CLIENT_ID not in text
    assert SYNTHETIC_CLIENT_SECRET not in text

    settings = Settings(
        avito_client_id=SecretStr(SYNTHETIC_CLIENT_ID),
        avito_client_secret=SecretStr(SYNTHETIC_CLIENT_SECRET),
    )
    from_settings = Credentials.from_settings(settings)
    assert from_settings.client_secret.get_secret_value() == SYNTHETIC_CLIENT_SECRET


def test_missing_credentials_names_only(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    for name in ("AVITO_CLIENT_ID", "AVITO_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)  # no developer .env
    settings = Settings(avito_client_id=SecretStr(SYNTHETIC_CLIENT_ID))
    with pytest.raises(MissingCredentialsError) as info:
        Credentials.from_settings(settings)
    assert "AVITO_CLIENT_SECRET" in str(info.value)
    assert SYNTHETIC_CLIENT_ID not in str(info.value)
    with pytest.raises(MissingCredentialsError):
        AvitoReadClient.from_settings(settings)


async def test_silence_httpx_url_logs(caplog: pytest.LogCaptureFixture) -> None:
    import logging as _logging

    from app.avito_gateway.http import silence_httpx_url_logs

    logger = _logging.getLogger("httpx")
    previous = logger.level
    try:
        silence_httpx_url_logs()
        caplog.set_level(_logging.INFO, logger="app.avito_gateway")
        mock = AvitoMock.with_synthetic_data()
        async with make_client(mock) as client:
            await client.get_chat(U, CHAT)
        assert CHAT not in caplog.text
        assert str(U) not in caplog.text
        assert "endpoint=chat_detail" in caplog.text
    finally:
        logger.setLevel(previous)

# SYNTHETIC: credentials and tokens are made up by the mock.
"""TokenManager: expires_in + margin, one refresh on 401, single-flight under concurrency."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import SecretStr

from app.avito_gateway import (
    AvitoAuthError,
    AvitoReadClient,
    AvitoServerError,
    AvitoUnexpectedPayloadError,
    Credentials,
)
from app.avito_gateway.http import AttemptRecord
from scripts.dev.avito_mock import (
    SYNTHETIC_CLIENT_ID,
    SYNTHETIC_CLIENT_SECRET,
    SYNTHETIC_USER_ID,
    AvitoMock,
    config_for_mock,
    forbidden,
    server_error,
    unauthorized,
    wrong_shape,
)
from tests.avito.helpers import make_client

pytestmark = pytest.mark.anyio

U = SYNTHETIC_USER_ID


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def test_token_fetched_once_and_sent_as_form_body() -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        await client.get_self()
        await client.list_chats(U)
    assert mock.token_requests == 1
    token_request = mock.requests[0]
    assert token_request.endpoint == "token"
    # Secrets travel in the form body, never in the URL.
    assert token_request.query == {}
    assert token_request.form["client_secret"] == [SYNTHETIC_CLIENT_SECRET]
    assert token_request.form["grant_type"] == ["client_credentials"]
    assert all(r.authorized for r in mock.requests[1:])


@pytest.mark.parametrize(
    ("expires_in", "margin", "reuse_at", "refresh_at"),
    [
        (600, 300, 299.0, 301.0),  # margin applies
        (100, 300, 49.0, 51.0),  # short life: margin capped at half the life
    ],
)
async def test_refresh_before_expiry(
    expires_in: float, margin: float, reuse_at: float, refresh_at: float
) -> None:
    clock = Clock()
    mock = AvitoMock.with_synthetic_data(token_expires_in=expires_in)
    async with make_client(mock, clock=clock, token_safety_margin_s=margin) as client:
        await client.get_self()
        start = clock.now
        clock.now = start + reuse_at
        await client.get_self()
        assert mock.token_requests == 1
        clock.now = start + refresh_at
        await client.get_self()
        assert mock.token_requests == 2


async def test_missing_expires_in_uses_fallback() -> None:
    clock = Clock()
    mock = AvitoMock.with_synthetic_data(token_expires_in=None)
    async with make_client(
        mock, clock=clock, token_ttl_fallback_s=1000, token_safety_margin_s=100
    ) as client:
        await client.get_self()
        clock.now += 899
        await client.get_self()
        assert mock.token_requests == 1
        clock.now += 2
        await client.get_self()
        assert mock.token_requests == 2


async def test_single_flight_initial_fetch() -> None:
    mock = AvitoMock.with_synthetic_data(token_delay_s=0.02)
    async with make_client(mock) as client:
        results = await asyncio.gather(*(client.get_self() for _ in range(25)))
    assert len(results) == 25
    assert mock.token_requests == 1


async def test_401_refreshes_once_then_succeeds() -> None:
    attempts: list[AttemptRecord] = []
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock, attempts=attempts) as client:
        await client.get_self()
        mock.inject(unauthorized(), endpoint="chats_list")
        page = await client.list_chats(U)
    assert page.items
    assert mock.token_requests == 2
    chat_attempts = [a for a in attempts if a.endpoint == "chats_list"]
    assert [(a.attempt, a.outcome) for a in chat_attempts] == [(1, "auth"), (2, "ok")]


async def test_401_twice_raises_without_further_retry() -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        await client.get_self()
        mock.inject(unauthorized(), endpoint="chats_list", times=2)
        with pytest.raises(AvitoAuthError) as info:
            await client.list_chats(U)
    assert info.value.status == 401
    assert mock.count("chats_list") == 2
    assert mock.token_requests == 2


async def test_403_does_not_refresh() -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        await client.get_self()
        mock.inject(forbidden(), endpoint="chats_list")
        with pytest.raises(AvitoAuthError) as info:
            await client.list_chats(U)
    assert info.value.status == 403
    assert mock.count("chats_list") == 1
    assert mock.token_requests == 1


async def test_single_flight_refresh_after_concurrent_401() -> None:
    mock = AvitoMock.with_synthetic_data(token_delay_s=0.02, response_delay_s=0.01)
    async with make_client(mock) as client:
        await client.get_self()
        mock.revoke_tokens()  # every in-flight request now gets 401
        results = await asyncio.gather(*(client.list_chats(U) for _ in range(15)))
    assert all(r.items for r in results)
    assert mock.token_requests == 2  # initial + exactly one refresh
    assert mock.count("chats_list") == 30  # each call: one 401 attempt + one repeat


async def test_token_errors_are_shared_by_waiters() -> None:
    mock = AvitoMock.with_synthetic_data(token_delay_s=0.01)
    mock.inject(server_error(503), endpoint="token")
    async with make_client(mock) as client:
        results = await asyncio.gather(
            *(client.get_self() for _ in range(8)), return_exceptions=True
        )
        assert all(isinstance(r, AvitoServerError) for r in results)
        assert mock.token_requests == 1
        # The next call starts a fresh fetch.
        await client.get_self()
    assert mock.token_requests == 2


async def test_bad_credentials_are_auth_errors() -> None:
    mock = AvitoMock.with_synthetic_data()
    wrong = Credentials(SecretStr(SYNTHETIC_CLIENT_ID), SecretStr("a-wrong-synthetic-secret"))
    async with AvitoReadClient(config_for_mock(), wrong, transport=mock.transport()) as client:
        with pytest.raises(AvitoAuthError) as info:
            await client.get_self()
    assert info.value.endpoint == "token"
    assert info.value.status == 400
    assert mock.count("accounts_self") == 0


async def test_token_reply_without_access_token() -> None:
    mock = AvitoMock.with_synthetic_data()
    mock.inject(wrong_shape({"expires_in": 3600}), endpoint="token")
    async with make_client(mock) as client:
        with pytest.raises(AvitoUnexpectedPayloadError) as info:
            await client.get_self()
    assert info.value.fields == ("access_token",)


async def test_cancelled_waiter_does_not_cancel_shared_refresh() -> None:
    mock = AvitoMock.with_synthetic_data(token_delay_s=0.05)
    async with make_client(mock) as client:
        first = asyncio.create_task(client.get_self())
        second = asyncio.create_task(client.get_self())
        await asyncio.sleep(0.01)
        first.cancel()
        result = await second
        assert result.data.id == U
        with pytest.raises(asyncio.CancelledError):
            await first
    assert mock.token_requests == 1


async def test_refresh_on_401_can_be_disabled() -> None:
    """The T-010 script stops on the first 401 (no refresh, no repeat)."""
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock, refresh_on_401=False) as client:
        await client.get_self()
        mock.inject(unauthorized(), endpoint="chats_list")
        with pytest.raises(AvitoAuthError):
            await client.list_chats(U)
    assert mock.count("chats_list") == 1
    assert mock.token_requests == 1

# SYNTHETIC: faults are injected by the in-process mock; nothing reaches the network.
"""Every failure maps to one typed error, after exactly one HTTP attempt (no transport retry)."""

from __future__ import annotations

import pytest

from app.avito_gateway import (
    AvitoAuthError,
    AvitoClientError,
    AvitoNetworkError,
    AvitoRateLimitedError,
    AvitoServerError,
    AvitoTimeoutError,
    AvitoUnexpectedPayloadError,
    ErrorKind,
    ReadErrorClass,
)
from app.avito_gateway.errors import AvitoApiError
from app.avito_gateway.http import AttemptRecord
from scripts.dev.avito_mock import (
    SYNTHETIC_USER_ID,
    AvitoMock,
    Fault,
    client_error,
    connect_error,
    forbidden,
    malformed_json,
    rate_limited,
    redirect,
    server_error,
    timeout,
    unauthorized,
    wrong_shape,
)
from tests.avito.helpers import make_client

pytestmark = pytest.mark.anyio

U = SYNTHETIC_USER_ID

CASES: list[tuple[str, Fault, int, type[AvitoApiError], ErrorKind, ReadErrorClass]] = [
    ("401x2", unauthorized(), 2, AvitoAuthError, ErrorKind.AUTH, ReadErrorClass.AUTH),
    ("403", forbidden(), 1, AvitoAuthError, ErrorKind.AUTH, ReadErrorClass.AUTH),
    (
        "429",
        rate_limited("5"),
        1,
        AvitoRateLimitedError,
        ErrorKind.RATE_LIMITED,
        ReadErrorClass.RATE_LIMITED,
    ),
    (
        "429-no-header",
        rate_limited(None),
        1,
        AvitoRateLimitedError,
        ErrorKind.RATE_LIMITED,
        ReadErrorClass.RATE_LIMITED,
    ),
    ("404", client_error(404), 1, AvitoClientError, ErrorKind.CLIENT, ReadErrorClass.PERMANENT),
    ("400", client_error(400), 1, AvitoClientError, ErrorKind.CLIENT, ReadErrorClass.PERMANENT),
    ("302", redirect(), 1, AvitoClientError, ErrorKind.CLIENT, ReadErrorClass.PERMANENT),
    (
        "500",
        server_error(500),
        1,
        AvitoServerError,
        ErrorKind.SERVER,
        ReadErrorClass.RETRYABLE_READ,
    ),
    (
        "503",
        server_error(503),
        1,
        AvitoServerError,
        ErrorKind.SERVER,
        ReadErrorClass.RETRYABLE_READ,
    ),
    (
        "timeout",
        timeout(),
        1,
        AvitoTimeoutError,
        ErrorKind.TIMEOUT,
        ReadErrorClass.RETRYABLE_READ,
    ),
    (
        "connect",
        connect_error(),
        1,
        AvitoNetworkError,
        ErrorKind.NETWORK,
        ReadErrorClass.RETRYABLE_READ,
    ),
    (
        "malformed-json",
        malformed_json(),
        1,
        AvitoUnexpectedPayloadError,
        ErrorKind.UNEXPECTED_PAYLOAD,
        ReadErrorClass.PERMANENT,
    ),
    (
        "wrong-shape",
        wrong_shape({"result": []}),
        1,
        AvitoUnexpectedPayloadError,
        ErrorKind.UNEXPECTED_PAYLOAD,
        ReadErrorClass.PERMANENT,
    ),
    (
        "wrong-shape-list-type",
        wrong_shape({"chats": {"not": "a list"}}),
        1,
        AvitoUnexpectedPayloadError,
        ErrorKind.UNEXPECTED_PAYLOAD,
        ReadErrorClass.PERMANENT,
    ),
]


@pytest.mark.parametrize(
    ("fault", "times", "error_type", "kind", "read_class"),
    [c[1:] for c in CASES],
    ids=[c[0] for c in CASES],
)
async def test_error_classes(
    fault: Fault,
    times: int,
    error_type: type[AvitoApiError],
    kind: ErrorKind,
    read_class: ReadErrorClass,
) -> None:
    attempts: list[AttemptRecord] = []
    mock = AvitoMock.with_synthetic_data()
    # A tiny Retry-After cap keeps the 429 pause from slowing the "still works" check below.
    async with make_client(mock, attempts=attempts, max_retry_after_s=0.01) as client:
        await client.get_self()
        mock.inject(fault, endpoint="chats_list", times=times)
        with pytest.raises(error_type) as info:
            await client.list_chats(U, limit=10)
        err = info.value
        assert err.kind is kind
        assert err.read_class is read_class
        assert err.retryable == (read_class is ReadErrorClass.RETRYABLE_READ)
        assert err.endpoint == "chats_list"
        # Exactly one HTTP attempt, or two for 401 (one token refresh, one repeat).
        assert mock.count("chats_list") == times
        chat_attempts = [a for a in attempts if a.endpoint == "chats_list"]
        # Attempt records describe the HTTP exchange: a 200 with a bad body is an "ok" attempt.
        http_outcome = "ok" if kind is ErrorKind.UNEXPECTED_PAYLOAD else kind.value
        assert [a.outcome for a in chat_attempts] == [http_outcome] * times
        # httpx exceptions are not chained: they reference the request and its headers.
        assert err.__cause__ is None
        assert err.__suppress_context__ is True or err.__context__ is None
        # The client still works afterwards.
        page = await client.list_chats(U, limit=10)
        assert page.items


async def test_redirect_is_not_followed() -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        await client.get_self()
        mock.inject(redirect(f"https://avito-mock.invalid/messenger/v2/accounts/{U}/chats"))
        with pytest.raises(AvitoClientError) as info:
            await client.list_chats(U)
    assert info.value.status == 302
    assert mock.count("chats_list") == 1


async def test_error_body_shapes_give_api_code() -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        await client.get_self()
        for body, code in [
            ({"error": {"code": 404, "message": "x"}}, "404"),
            ({"code": "not_found", "message": "x"}, "not_found"),
            ({"errors": [{"code": 17, "message": "x"}]}, "17"),
            ({"unexpected": True}, None),
        ]:
            mock.inject(Fault.json_status("custom", 404, body), endpoint="chat_detail")
            with pytest.raises(AvitoClientError) as info:
                await client.get_chat(U, "u2i-synthetic0000~chat")
            assert info.value.api_code == code


async def test_timeouts_come_from_config() -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock, connect_timeout_s=1.5, read_timeout_s=7.0) as client:
        timeout_cfg = client._http.client.timeout
    assert timeout_cfg.connect == 1.5
    assert timeout_cfg.read == 7.0

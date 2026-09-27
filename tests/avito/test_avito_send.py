# SYNTHETIC: texts, ids, credentials and tokens are made up; the mock is in-process.
"""Send client (T-018): classification, exactly one request, allowlist, authorization, no text
or secrets in logs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from app.avito_gateway import AvitoReadClient, ForbiddenEndpointError
from app.avito_gateway import send as send_module
from app.avito_gateway.send import (
    PART_LIMITS,
    SEND_TEXT,
    WRITE_ALLOWLIST,
    AvitoSendClient,
    SendAttemptRecord,
    SendAuthorization,
    SendClientUsedError,
    SendOutcome,
    SendTextRejected,
    text_sha256,
)
from app.avito_gateway.token import TokenManager
from app.safety.filter import measure_part
from scripts.dev.avito_mock import (
    SYNTHETIC_CLIENT_ID,
    SYNTHETIC_CLIENT_SECRET,
    SYNTHETIC_USER_ID,
    AvitoMock,
    Fault,
    client_error,
    config_for_mock,
    connect_error,
    delivered_then_timeout,
    forbidden,
    malformed_2xx,
    ok_without_id,
    rate_limited,
    redirect,
    reset_after_store,
    send_authorization,
    server_error,
    server_error_after_store,
    timeout,
    unauthorized,
)
from tests.avito.helpers import make_client

pytestmark = pytest.mark.anyio

U = SYNTHETIC_USER_ID
CHAT = "u2i-synthetic0000~chat"
TEXT = "Синтетический ответ: деталь есть, уточните VIN-SYNTH-MARKER"


def make_sender(
    mock: AvitoMock,
    text: str = TEXT,
    *,
    records: list[SendAttemptRecord] | None = None,
    tokens: TokenManager | None = None,
    authorization: SendAuthorization | None = None,
    **config: Any,
) -> AvitoSendClient:
    return AvitoSendClient.for_authorized_send(
        authorization if authorization is not None else send_authorization(mock, text),
        config=config_for_mock(**config),
        credentials=None if tokens is not None else mock.credentials(),
        tokens=tokens,
        transport=mock.transport(),
        on_attempt=records.append if records is not None else None,
    )


async def test_delivered_and_visible_to_reconciliation_reads() -> None:
    mock = AvitoMock.with_synthetic_data()
    records: list[SendAttemptRecord] = []
    async with make_sender(mock, records=records) as sender:
        result = await sender.send_text(TEXT)
    assert result.outcome is SendOutcome.DELIVERED
    assert result.request_sent is True
    assert result.status == 200
    assert result.message_id == mock.sent_messages[0]["id"]
    assert result.created == mock.sent_messages[0]["created"]
    assert mock.count("send_text") == 1
    request = next(r for r in mock.requests if r.endpoint == "send_text")
    # Body: type/message, not the spec copy's erroneous required "url".
    assert request.json_body == {"type": "text", "message": {"text": TEXT}}
    assert request.authorized
    assert [(r.outcome, r.reason, r.attempt) for r in records] == [
        (SendOutcome.DELIVERED, "http_200", 1)
    ]
    # The stored send shows up in the chat's message list (T-025 reconciliation).
    async with make_client(mock) as reader:
        page = await reader.list_messages(U, CHAT, limit=5)
    newest = page.items[0]
    assert newest.id == result.message_id
    assert newest.direction == "out"
    assert newest.author_id == U
    assert newest.content is not None and newest.content.text == TEXT


# (fault, expected outcome, reason, request_sent, messages stored by the mock)
CASES: list[tuple[str, Fault, SendOutcome, str, bool, int]] = [
    (
        "delivered-then-timeout",
        delivered_then_timeout(),
        SendOutcome.UNKNOWN,
        "timeout_after_send",
        True,
        1,
    ),
    (
        "reset-after-store",
        reset_after_store(),
        SendOutcome.UNKNOWN,
        "connection_lost_after_send",
        True,
        1,
    ),
    ("5xx-after-store", server_error_after_store(500), SendOutcome.UNKNOWN, "http_500", True, 1),
    ("5xx-before-store", server_error(503), SendOutcome.UNKNOWN, "http_503", True, 0),
    ("malformed-2xx", malformed_2xx(), SendOutcome.UNKNOWN, "malformed_2xx", True, 1),
    ("2xx-without-id", ok_without_id(), SendOutcome.UNKNOWN, "malformed_2xx", True, 1),
    (
        "2xx-not-an-object",
        Fault.json_status("list", 200, ["x"]),
        SendOutcome.UNKNOWN,
        "malformed_2xx",
        True,
        0,
    ),
    ("timeout-no-store", timeout(), SendOutcome.UNKNOWN, "timeout_after_send", True, 0),
    (
        "write-timeout",
        Fault(name="wt", raise_exc=httpx.WriteTimeout),
        SendOutcome.UNKNOWN,
        "write_incomplete",
        True,
        0,
    ),
    (
        "read-error",
        Fault(name="re", raise_exc=httpx.ReadError),
        SendOutcome.UNKNOWN,
        "connection_lost_after_send",
        True,
        0,
    ),
    ("429-retry-after", rate_limited("5"), SendOutcome.NOT_DELIVERED, "http_429", True, 0),
    ("429-no-header", rate_limited(None), SendOutcome.NOT_DELIVERED, "http_429", True, 0),
    ("401", unauthorized(), SendOutcome.NOT_DELIVERED, "http_401", True, 0),
    ("403", forbidden(), SendOutcome.NOT_DELIVERED, "http_403", True, 0),
    ("400", client_error(400), SendOutcome.NOT_DELIVERED, "http_400", True, 0),
    ("404", client_error(404), SendOutcome.NOT_DELIVERED, "http_404", True, 0),
    ("422", client_error(422), SendOutcome.NOT_DELIVERED, "http_422", True, 0),
    ("405-unlisted", client_error(405), SendOutcome.UNKNOWN, "http_405", True, 0),
    ("408-unlisted", client_error(408), SendOutcome.UNKNOWN, "http_408", True, 0),
    ("409-unlisted", client_error(409), SendOutcome.UNKNOWN, "http_409", True, 0),
    ("302-not-followed", redirect(), SendOutcome.UNKNOWN, "http_302", True, 0),
    (
        "proxy-error-is-unknown",  # T-018b: not provably "not sent"
        Fault(name="proxy", raise_exc=httpx.ProxyError),
        SendOutcome.UNKNOWN,
        "transport_error",
        True,
        0,
    ),
    ("connect-error", connect_error(), SendOutcome.NOT_DELIVERED, "not_sent_connect", False, 0),
    (
        "connect-timeout",
        Fault(name="ct", raise_exc=httpx.ConnectTimeout),
        SendOutcome.NOT_DELIVERED,
        "not_sent_connect",
        False,
        0,
    ),
]


@pytest.mark.parametrize(
    ("fault", "outcome", "reason", "request_sent", "stored"),
    [c[1:] for c in CASES],
    ids=[c[0] for c in CASES],
)
async def test_classification_and_exactly_one_request(
    fault: Fault, outcome: SendOutcome, reason: str, request_sent: bool, stored: int
) -> None:
    mock = AvitoMock.with_synthetic_data()
    mock.inject(fault, endpoint="send_text")
    records: list[SendAttemptRecord] = []
    async with make_sender(mock, records=records, max_retry_after_s=0.01) as sender:
        result = await sender.send_text(TEXT)
    assert (result.outcome, result.reason, result.request_sent) == (outcome, reason, request_sent)
    # No automatic retry of any kind: one HTTP request to the send endpoint per call.
    assert mock.count("send_text") == 1
    assert len(mock.sent_messages) == stored
    assert len(records) == 1
    assert (records[0].outcome, records[0].reason) == (outcome, reason)
    if outcome is not SendOutcome.DELIVERED:
        assert result.message_id is None


async def test_429_pauses_the_send_bucket_and_reports_retry_after() -> None:
    mock = AvitoMock.with_synthetic_data()
    mock.inject(rate_limited("7"), endpoint="send_text")
    async with make_sender(mock) as sender:
        result = await sender.send_text(TEXT)
        assert result.retry_after == 7.0
        assert sender._limiter.blocked_for(SEND_TEXT.name) == pytest.approx(7.0, abs=0.5)


async def test_401_forgets_token_without_fetching_during_the_call() -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as reader:
        await reader.get_self()  # shared token manager now holds token #1
        assert mock.token_requests == 1
        mock.revoke_tokens()
        async with make_sender(mock, tokens=reader.tokens) as sender:
            result = await sender.send_text(TEXT)
        assert (result.outcome, result.reason) == (SendOutcome.NOT_DELIVERED, "http_401")
        assert mock.token_requests == 1  # no refresh inside the send call
        assert mock.count("send_text") == 1
        # The next authorized send fetches a fresh token first.
        auth = send_authorization(mock, TEXT, outbound_message_id="outbox-synthetic-2")
        async with make_sender(mock, tokens=reader.tokens, authorization=auth) as sender:
            again = await sender.send_text(TEXT)
    assert again.outcome is SendOutcome.DELIVERED
    assert mock.token_requests == 2
    assert mock.count("send_text") == 2


async def test_token_failure_is_not_delivered_without_send_request() -> None:
    mock = AvitoMock.with_synthetic_data()
    mock.inject(server_error(503), endpoint="token")
    records: list[SendAttemptRecord] = []
    async with make_sender(mock, records=records) as sender:
        result = await sender.send_text(TEXT)
    assert (result.outcome, result.reason, result.request_sent) == (
        SendOutcome.NOT_DELIVERED,
        "token_server",
        False,
    )
    assert mock.count("send_text") == 0
    assert records[0].request_sent is False


async def test_client_is_single_use() -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_sender(mock) as sender:
        await sender.send_text(TEXT)
        with pytest.raises(SendClientUsedError):
            await sender.send_text(TEXT)
    assert mock.count("send_text") == 1


# -- text validation -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("", "empty"),
        ("   \n\t ", "empty"),
        ("a" * 1001, "too long"),  # 1001 units, 1001 bytes
        ("я" * 1000, "too long"),  # 1000 UTF-16 units but 2000 UTF-8 bytes
        ("я" * 501, "too long"),  # 1002 bytes
        ("😀" * 251, "too long"),  # 502 units, 1004 bytes
        ("€" * 334, "too long"),  # 334 units, 1002 bytes
    ],
)
async def test_text_refused_before_any_request(text: str, why: str) -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_sender(mock, text) as sender:
        with pytest.raises(SendTextRejected) as info:
            await sender.send_text(text)
    assert why in str(info.value)
    assert mock.requests == []


@pytest.mark.parametrize(
    "text",
    [
        "a" * 1000,  # 1000 units, 1000 bytes
        "я" * 500,  # 500 units, 1000 bytes
        "😀" * 250,  # 500 units, 1000 bytes
        "€" * 333 + "a",  # 334 units, 1000 bytes
    ],
)
async def test_limits_are_inclusive(text: str) -> None:
    size = measure_part(text)
    assert size.utf16_units <= PART_LIMITS.max_utf16_units
    assert size.utf8_bytes == PART_LIMITS.max_utf8_bytes == 1000
    mock = AvitoMock.with_synthetic_data()
    async with make_sender(mock, text) as sender:
        result = await sender.send_text(text)
    assert result.outcome is SendOutcome.DELIVERED
    assert mock.sent_messages[0]["content"]["text"] == text


def test_send_uses_the_filter_measure() -> None:
    """One measuring function for splitter, filter and send client (no local copy)."""
    from app.safety import filter as safety_filter

    assert vars(send_module)["measure_part"] is safety_filter.measure_part
    assert vars(send_module)["part_fits"] is safety_filter.part_fits
    assert "unicodedata" not in vars(send_module)  # the old local NFC/NFKC copy is gone
    assert (PART_LIMITS.max_utf16_units, PART_LIMITS.max_utf8_bytes) == (1000, 1000)


async def test_text_must_match_authorization() -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_sender(mock, "Синтетика: разрешённый текст") as sender:
        with pytest.raises(SendTextRejected) as info:
            await sender.send_text("Синтетика: другой текст")
    assert "authorization" in str(info.value)
    assert "Синтетика" not in str(info.value)
    assert mock.requests == []


# -- construction ----------------------------------------------------------------------------


def test_direct_construction_is_impossible() -> None:
    with pytest.raises(TypeError):
        AvitoSendClient()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        AvitoSendClient(
            _factory_key=object(),
            authorization=None,  # type: ignore[arg-type]
            config=config_for_mock(),
            tokens=None,  # type: ignore[arg-type]
            http=None,  # type: ignore[arg-type]
            limiter=None,  # type: ignore[arg-type]
            owned=[],
            on_attempt=None,
        )


@pytest.mark.parametrize("authorization", [None, {}, "outbox-1", object()])
def test_factory_requires_send_authorization(authorization: object) -> None:
    mock = AvitoMock.with_synthetic_data()
    with pytest.raises(TypeError):
        AvitoSendClient.for_authorized_send(
            authorization,  # type: ignore[arg-type]
            config=config_for_mock(),
            credentials=mock.credentials(),
            transport=mock.transport(),
        )


def test_factory_needs_exactly_one_token_source() -> None:
    mock = AvitoMock.with_synthetic_data()
    auth = send_authorization(mock, TEXT)
    with pytest.raises(ValueError):
        AvitoSendClient.for_authorized_send(auth, config=config_for_mock())


@pytest.mark.parametrize(
    "overrides",
    [
        {"chat_id": "../read"},
        {"chat_id": "a/b"},
        {"chat_id": ""},
        {"attempt": 0},
        {"outbound_message_id": ""},
        {"text_sha256": "abc"},
        {"text_sha256": "G" * 64},
        {"intent_at": datetime(2026, 1, 1)},  # naive
        {"user_id": "900000001"},
    ],
)
def test_authorization_validation(overrides: dict[str, Any]) -> None:
    values: dict[str, Any] = {
        "outbound_message_id": "outbox-synthetic-1",
        "user_id": U,
        "chat_id": CHAT,
        "text_sha256": text_sha256(TEXT),
        "attempt": 1,
        "intent_at": datetime.now(UTC),
    }
    values.update(overrides)
    with pytest.raises(ValueError):
        SendAuthorization(**values)


# -- allowlist -------------------------------------------------------------------------------


def test_write_allowlist_is_only_send_text() -> None:
    assert WRITE_ALLOWLIST == (SEND_TEXT,)
    assert SEND_TEXT.method == "POST"
    assert SEND_TEXT.template == "/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages"
    public = {n for n in dir(AvitoSendClient) if not n.startswith("_")}
    assert public == {"aclose", "for_authorized_send", "send_text"}


OTHER_PATHS = [
    ("GET", f"/messenger/v1/accounts/{U}/chats/{CHAT}/messages"),
    ("POST", f"/messenger/v1/accounts/{U}/chats/{CHAT}/messages/image"),
    ("POST", f"/messenger/v1/accounts/{U}/chats/{CHAT}/messages/msg-1"),  # delete
    ("POST", f"/messenger/v1/accounts/{U}/chats/{CHAT}/read"),
    ("POST", f"/messenger/v1/accounts/{U}/uploadImages"),
    ("POST", "/messenger/v3/webhook"),
    ("POST", "/messenger/v1/webhook/unsubscribe"),
    ("POST", f"/messenger/v2/accounts/{U}/blacklist"),
    ("GET", f"/messenger/v3/accounts/{U}/chats/{CHAT}/messages/"),  # reads are not allowed here
    ("GET", "/core/v1/accounts/self"),
    ("POST", "/token"),  # the send transport does not even reach /token
    ("POST", f"/messenger/v1/accounts/{U}/chats/{CHAT}/messages/"),  # trailing slash
]


@pytest.mark.parametrize(("method", "path"), OTHER_PATHS)
async def test_send_transport_refuses_everything_else(method: str, path: str) -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_sender(mock) as sender:
        with pytest.raises(ForbiddenEndpointError):
            await sender._http.request(method, path, json={"type": "text"})
    assert mock.requests == []


async def test_send_transport_refuses_other_hosts_and_token_transport_only_tokens() -> None:
    mock = AvitoMock.with_synthetic_data()
    send_path = SEND_TEXT.path(user_id=U, chat_id=CHAT)
    async with make_sender(mock) as sender:
        with pytest.raises(ForbiddenEndpointError):
            await sender._http.post(f"https://elsewhere.invalid{send_path}", json={})
        token_http = sender._owned[0].client
        with pytest.raises(ForbiddenEndpointError):
            await token_http.post(send_path, json={"type": "text"})
    assert mock.requests == []


async def test_read_client_still_cannot_send() -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as reader:
        with pytest.raises(ForbiddenEndpointError):
            await reader._http.client.post(SEND_TEXT.path(user_id=U, chat_id=CHAT), json={})
    assert mock.requests == []
    assert not hasattr(AvitoReadClient, "send_text")


# -- logs ------------------------------------------------------------------------------------


async def test_no_text_or_secrets_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    text = "Синтетика SECRET-TEXT-MARKER позвоните +7 900 000-00-77"
    mock = AvitoMock.with_synthetic_data()
    results = []
    faults: list[Fault | None] = [
        None,
        delivered_then_timeout(),
        server_error_after_store(502),
        malformed_2xx(),
        rate_limited("1"),
        unauthorized(),
        connect_error(),
    ]
    for i, fault in enumerate(faults):
        if fault is not None:
            mock.inject(fault, endpoint="send_text")
        auth = send_authorization(mock, text, outbound_message_id=f"outbox-synthetic-{i}")
        async with make_sender(mock, text, authorization=auth, max_retry_after_s=0.01) as s:
            results.append(await s.send_text(text))
            reprs = repr(s) + repr(auth) + repr(results[-1])
            assert "SECRET-TEXT-MARKER" not in reprs
    for bad in ("", "x" * 1001):
        with pytest.raises(SendTextRejected) as info:
            async with make_sender(mock, bad) as s:
                await s.send_text(bad)
        assert "x" * 20 not in str(info.value)
    assert {r.outcome for r in results} == set(SendOutcome)
    everything = caplog.text + " ".join(repr(r.args) for r in caplog.records)
    for secret in ("SECRET-TEXT-MARKER", "+7 900", SYNTHETIC_CLIENT_ID, SYNTHETIC_CLIENT_SECRET):
        assert secret not in everything
    for token in mock.issued_tokens:
        assert token not in everything
    ours = " ".join(r.getMessage() for r in caplog.records if r.name.startswith("app."))
    assert "outbound_message_id=outbox-synthetic-0" in ours
    assert CHAT not in ours  # our log lines carry no chat id either
    assert send_module.logger.name == "app.avito_gateway.send"


def test_proxy_error_is_not_in_not_sent_errors() -> None:
    not_sent: tuple[type[BaseException], ...] = send_module._NOT_SENT_ERRORS
    assert not any(issubclass(httpx.ProxyError, e) for e in not_sent)

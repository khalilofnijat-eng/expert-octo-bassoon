"""Text-only send client (T-018; docs/ARCHITECTURE.md §6.5 items 4–5).

Scope: ``POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/messages`` with a text body and
nothing else. Image upload/send and delete are out of scope (images stay disabled,
``images_enabled=false``; delete belongs to the future admin UI). The read client
(:class:`app.avito_gateway.client.AvitoReadClient`) is unchanged and still cannot write.

Guarantees
----------
* **Separate write allowlist** (:data:`WRITE_ALLOWLIST`) with this single endpoint. The send
  client's httpx transport refuses every other path and host before network I/O; its tokens come
  from a token-only transport (``/token``) or a shared :class:`TokenManager`.
* **Construction only through** :meth:`AvitoSendClient.for_authorized_send`, which requires a
  :class:`SendAuthorization`. The outbox (T-025) builds that object *after* its intent CAS
  succeeded; this client never checks the database. A client is **single use**: one
  ``send_text`` call, for the chat and the exact text (SHA-256) the authorization names.
* **Exactly one HTTP request per call.** No transport retry (``retries=0``), no retry middleware,
  no redirect following, no 401 refresh-and-repeat (a 401 only makes the token manager forget
  the token; the next authorized send fetches a new one). Every attempt produces a
  :class:`SendAttemptRecord`.
* **No message text in logs, exceptions or repr**, ever. Logs carry the outbox row id, attempt
  number, HTTP status, outcome, reason and duration only.

Outcome of an attempt (:class:`SendOutcome`)
--------------------------------------------
``delivered``
    2xx whose body is a JSON object with a non-empty ``id`` (the spec copy's reply is
    ``{id, created, type, direction, content}``).
``not_delivered`` – a definite "no message went out":
    * 400, 404, 422: the request was rejected as invalid (bad body, unknown chat) before any
      message was created.
    * 401, 403: authentication/authorisation failed; the request was not processed.
    * 429: refused by rate limiting before processing.
    * the request never left this process: connection could not be established
      (``ConnectError``, ``ConnectTimeout``, ``PoolTimeout``, ``UnsupportedProtocol``,
      ``LocalProtocolError``), or no token could be obtained.

    Treating 401/403/429 as "not delivered" is valid **only because there is no transport
    retry**: this call sent exactly one request and it is the one that was rejected, so no earlier
    hidden attempt could have delivered the text. Any change that adds retries below this layer
    invalidates this table.
``unknown`` – the server may or may not have stored the message; the outbox reconciles by
reading the chat (§6.5 item 6) and never resends automatically (MA-1):
    * 5xx: the server may fail after storing.
    * timeout or connection loss after the request was (partly) sent: ``ReadTimeout``,
      ``WriteTimeout``, ``ReadError``, ``WriteError``, ``RemoteProtocolError``, ``CloseError``
      and any other transport error.
    * ``ProxyError`` (T-018b): whether a proxy failure happens before any request byte reaches
      Avito depends on the proxy and is not verified, so it is ``unknown`` (reason
      ``transport_error``). A false "unknown" costs one reconciliation read; a false
      "not delivered" risks a duplicate message.
    * a 2xx that is not JSON, not an object, or has no ``id`` ("malformed 2xx").
    * every other status (1xx, 3xx – redirects are not followed –, and 4xx codes not listed
      above, e.g. 405/408/409/410/413): not a documented definite rejection, so the safe answer
      is "unknown" (a wrong "not delivered" risks a duplicate message; a wrong "unknown" costs
      one reconciliation read).

Text validation: empty or whitespace-only text, and text that does not fit the part size limits
of the output filter – ``app.safety.filter.part_fits``: at most 1000 UTF-16 code units **and** at
most 1000 UTF-8 bytes (``FilterConfig`` defaults; the splitter and the filter use the same
``measure_part``) – are refused before any request (:class:`SendTextRejected`).

Body: ``{"type": "text", "message": {"text": ...}}``. The spec copy's request schema says
``required: ["url"]``, which is a known error in that spec (INTEGRATIONS §3.1); the body is built
here directly and never validated against that schema.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import TracebackType
from typing import Any, Final

import httpx

from app.avito_gateway import endpoints
from app.avito_gateway.config import Credentials, GatewayConfig
from app.avito_gateway.endpoints import Endpoint
from app.avito_gateway.errors import AvitoApiError, AvitoGatewayError
from app.avito_gateway.http import (
    AttemptHook,
    GatewayHTTP,
    build_http_client,
    default_limiter,
    parse_retry_after,
)
from app.avito_gateway.ratelimit import Clock, Priority, PriorityRateLimiter
from app.avito_gateway.token import TokenManager
from app.safety.filter import FilterConfig, measure_part, part_fits

logger = logging.getLogger("app.avito_gateway.send")

SEND_TEXT: Final = Endpoint(
    "send_text", "POST", "/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages"
)
# The only endpoint the send client may reach. Kept apart from the read allowlist on purpose.
WRITE_ALLOWLIST: Final[tuple[Endpoint, ...]] = (SEND_TEXT,)
# Part size limits: the output filter's defaults (≤ 1000 UTF-16 units and ≤ 1000 UTF-8 bytes).
PART_LIMITS: Final = FilterConfig()

_NOT_SENT_ERRORS: Final = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    # httpx.ProxyError is deliberately absent (T-018b): it falls through to "unknown".
    httpx.UnsupportedProtocol,
    httpx.LocalProtocolError,
)
_DEFINITE_REJECTIONS: Final = frozenset({400, 401, 403, 404, 422, 429})


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SendOutcome(StrEnum):
    DELIVERED = "delivered"
    NOT_DELIVERED = "not_delivered"
    UNKNOWN = "unknown"


class SendTextRejected(ValueError):
    """The text was refused before any request (empty, too long, or not the authorized text).
    The message names the reason only, never the text."""


class SendClientUsedError(AvitoGatewayError):
    """A send client is single use; a new send needs a new authorization (a new intent CAS)."""


@dataclass(frozen=True)
class SendAuthorization:
    """Proof that the outbox claimed this send (intent CAS succeeded) – built by T-025 only.

    Binds one outbox row, one chat and one exact text (by SHA-256; the text itself is not kept).
    """

    outbound_message_id: str
    user_id: int
    chat_id: str
    text_sha256: str
    attempt: int
    intent_at: datetime

    def __post_init__(self) -> None:
        if not self.outbound_message_id:
            raise ValueError("outbound_message_id is required")
        if isinstance(self.user_id, bool) or not isinstance(self.user_id, int):
            raise ValueError("user_id must be an int")
        if len(self.text_sha256) != 64 or any(
            c not in "0123456789abcdef" for c in self.text_sha256
        ):
            raise ValueError("text_sha256 must be a lowercase hex SHA-256")
        if self.attempt < 1:
            raise ValueError("attempt must be >= 1")
        if self.intent_at.tzinfo is None:
            raise ValueError("intent_at must be timezone-aware")
        # Validates the chat id as a path segment now, not at send time.
        SEND_TEXT.path(user_id=self.user_id, chat_id=self.chat_id)

    @classmethod
    def for_text(
        cls,
        *,
        outbound_message_id: str,
        user_id: int,
        chat_id: str,
        text: str,
        attempt: int,
        intent_at: datetime,
    ) -> SendAuthorization:
        return cls(
            outbound_message_id=outbound_message_id,
            user_id=user_id,
            chat_id=chat_id,
            text_sha256=text_sha256(text),
            attempt=attempt,
            intent_at=intent_at,
        )


@dataclass(frozen=True)
class SendAttemptRecord:
    """One send attempt, for the outbox's audit (no text, no chat id, no token)."""

    outbound_message_id: str
    attempt: int
    started_at: datetime
    duration_s: float
    status: int | None
    outcome: SendOutcome
    reason: str
    request_sent: bool


SendAttemptHook = Callable[[SendAttemptRecord], None]


@dataclass(frozen=True)
class SendResult:
    outcome: SendOutcome
    # Machine-readable: "http_200", "http_429", "malformed_2xx", "timeout_after_send",
    # "connection_lost_after_send", "write_incomplete", "not_sent_connect", "token_auth", ...
    reason: str
    # False only when no request to the send endpoint was made (token failure, connect failure).
    request_sent: bool
    status: int | None = None
    message_id: str | None = None
    created: int | None = None
    retry_after: float | None = None


_FACTORY_KEY: Final = object()


class AvitoSendClient:
    """Use :meth:`for_authorized_send`; direct construction raises ``TypeError``."""

    def __init__(
        self,
        *,
        _factory_key: object,
        authorization: SendAuthorization,
        config: GatewayConfig,
        tokens: TokenManager,
        http: httpx.AsyncClient,
        limiter: PriorityRateLimiter,
        owned: list[GatewayHTTP],
        on_attempt: SendAttemptHook | None,
    ) -> None:
        if _factory_key is not _FACTORY_KEY:
            raise TypeError("use AvitoSendClient.for_authorized_send(authorization, ...)")
        self._authorization = authorization
        self._config = config
        self._tokens = tokens
        self._http = http
        self._limiter = limiter
        self._owned = owned
        self._on_attempt = on_attempt
        self._used = False

    @classmethod
    def for_authorized_send(
        cls,
        authorization: SendAuthorization,
        *,
        config: GatewayConfig,
        credentials: Credentials | None = None,
        tokens: TokenManager | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        limiter: PriorityRateLimiter | None = None,
        on_attempt: SendAttemptHook | None = None,
        on_token_attempt: AttemptHook | None = None,
        clock: Clock = time.monotonic,
    ) -> AvitoSendClient:
        """Build a single-use client for one authorized send.

        Tokens: pass ``tokens`` to share the read client's :class:`TokenManager` (one token for
        the process; whether Avito invalidates older tokens on a new ``/token`` call is
        UNVERIFIED), or ``credentials`` to use a separate token-only transport.
        """
        if not isinstance(authorization, SendAuthorization):
            raise TypeError("a SendAuthorization is required")
        if (tokens is None) == (credentials is None):
            raise ValueError("pass exactly one of tokens= or credentials=")
        limiter = limiter if limiter is not None else default_limiter(config)
        owned: list[GatewayHTTP] = []
        if tokens is None:
            assert credentials is not None
            token_http = GatewayHTTP(
                config,
                transport=transport,
                limiter=limiter,
                on_attempt=on_token_attempt,
                allowlist=(endpoints.TOKEN,),
            )
            owned.append(token_http)
            tokens = TokenManager(token_http, credentials, clock=clock)
        http = build_http_client(config, transport, allowlist=WRITE_ALLOWLIST)
        return cls(
            _factory_key=_FACTORY_KEY,
            authorization=authorization,
            config=config,
            tokens=tokens,
            http=http,
            limiter=limiter,
            owned=owned,
            on_attempt=on_attempt,
        )

    def __repr__(self) -> str:
        return (
            f"AvitoSendClient(outbound_message_id={self._authorization.outbound_message_id!r}, "
            f"used={self._used})"
        )

    async def __aenter__(self) -> AvitoSendClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()
        for owned in self._owned:
            await owned.aclose()

    async def send_text(self, text: str) -> SendResult:
        """Send the authorized text once. Never raises for HTTP/transport outcomes; raises
        :class:`SendTextRejected` / :class:`SendClientUsedError` before any request."""
        if self._used:
            raise SendClientUsedError("this send client was already used")
        self._used = True
        auth = self._authorization
        self._validate(text)
        path = SEND_TEXT.path(user_id=auth.user_id, chat_id=auth.chat_id)

        started_at = datetime.now(UTC)
        start = time.monotonic()
        try:
            token = await self._tokens.get()
        except AvitoApiError as exc:
            return self._finish(
                SendResult(SendOutcome.NOT_DELIVERED, f"token_{exc.kind.value}", False),
                started_at,
                start,
            )

        await self._limiter.acquire(SEND_TEXT.name, Priority.LIVE)
        request = self._http.build_request(
            SEND_TEXT.method,
            path,
            json={"type": "text", "message": {"text": text}},
            headers={"Authorization": token.header()},
        )
        started_at = datetime.now(UTC)
        start = time.monotonic()
        try:
            response = await self._http.send(request)
        except _NOT_SENT_ERRORS:
            result = SendResult(SendOutcome.NOT_DELIVERED, "not_sent_connect", False)
        except httpx.ReadTimeout:
            # The request went out; the reply did not come in time.
            result = SendResult(SendOutcome.UNKNOWN, "timeout_after_send", True)
        except (httpx.ReadError, httpx.RemoteProtocolError, httpx.CloseError):
            # Connection reset / closed after the request went out.
            result = SendResult(SendOutcome.UNKNOWN, "connection_lost_after_send", True)
        except (httpx.WriteTimeout, httpx.WriteError):
            result = SendResult(SendOutcome.UNKNOWN, "write_incomplete", True)
        except httpx.TransportError:
            result = SendResult(SendOutcome.UNKNOWN, "transport_error", True)
        else:
            result = self._classify(response)
            if result.status == 401:
                self._tokens.mark_unauthorized(token.generation)
            if result.status == 429:
                cooldown = (
                    result.retry_after
                    if result.retry_after is not None
                    else self._config.default_429_cooldown_s
                )
                self._limiter.penalize(SEND_TEXT.name, cooldown)
        return self._finish(result, started_at, start)

    def _validate(self, text: str) -> None:
        if not isinstance(text, str) or not text.strip():
            raise SendTextRejected("empty text")
        if not part_fits(text, PART_LIMITS):
            size = measure_part(text)
            raise SendTextRejected(
                f"text too long: {size.utf16_units} UTF-16 units / {size.utf8_bytes} UTF-8 bytes "
                f"(limits {PART_LIMITS.max_utf16_units} / {PART_LIMITS.max_utf8_bytes})"
            )
        if text_sha256(text) != self._authorization.text_sha256:
            raise SendTextRejected("text does not match the authorization")

    def _classify(self, response: httpx.Response) -> SendResult:
        status = response.status_code
        if 200 <= status <= 299:
            message_id, created = _parse_reply(response)
            if message_id is None:
                return SendResult(SendOutcome.UNKNOWN, "malformed_2xx", True, status=status)
            return SendResult(
                SendOutcome.DELIVERED,
                f"http_{status}",
                True,
                status=status,
                message_id=message_id,
                created=created,
            )
        if status in _DEFINITE_REJECTIONS:
            retry_after = None
            if status == 429:
                retry_after = parse_retry_after(response.headers.get("Retry-After"))
                if retry_after is not None:
                    retry_after = min(retry_after, self._config.max_retry_after_s)
            return SendResult(
                SendOutcome.NOT_DELIVERED,
                f"http_{status}",
                True,
                status=status,
                retry_after=retry_after,
            )
        return SendResult(SendOutcome.UNKNOWN, f"http_{status}", True, status=status)

    def _finish(self, result: SendResult, started_at: datetime, start: float) -> SendResult:
        duration = time.monotonic() - start
        auth = self._authorization
        record = SendAttemptRecord(
            outbound_message_id=auth.outbound_message_id,
            attempt=auth.attempt,
            started_at=started_at,
            duration_s=duration,
            status=result.status,
            outcome=result.outcome,
            reason=result.reason,
            request_sent=result.request_sent,
        )
        log = logger.info if result.outcome is SendOutcome.DELIVERED else logger.warning
        log(
            "avito send outbound_message_id=%s attempt=%d status=%s outcome=%s reason=%s ms=%d",
            auth.outbound_message_id,
            auth.attempt,
            result.status if result.status is not None else "-",
            result.outcome.value,
            result.reason,
            int(duration * 1000),
        )
        if self._on_attempt is not None:
            self._on_attempt(record)
        return result


def _parse_reply(response: httpx.Response) -> tuple[str | None, int | None]:
    try:
        body: Any = response.json()
    except ValueError:  # JSONDecodeError and UnicodeDecodeError are ValueErrors
        return None, None
    if not isinstance(body, dict):
        return None, None
    raw_id = body.get("id")
    if isinstance(raw_id, bool) or not isinstance(raw_id, str | int) or raw_id == "":
        return None, None
    created = body.get("created")
    if isinstance(created, bool) or not isinstance(created, int):
        created = None
    return str(raw_id), created

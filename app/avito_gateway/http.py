"""HTTP plumbing shared by the token manager and the read client.

Rules (ARCHITECTURE §6.5 item 4, applied to reads as well):

* no transport-level retries (``retries=0``), no retry middleware, no redirect following;
* every HTTP attempt is reported as an :class:`AttemptRecord` (``on_attempt`` hook), so retries,
  which only happen in *our* layers, are explicit;
* every outgoing request passes :class:`AllowlistTransport`, which refuses anything that is not on
  the read allowlist or not addressed to the configured host, before any network I/O;
* log lines carry the endpoint name, status, attempt number and duration only: no URL (it holds
  ids), no headers (token), no body.
"""

from __future__ import annotations

import email.utils
import json
import logging
import math
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.avito_gateway import endpoints
from app.avito_gateway.config import GatewayConfig
from app.avito_gateway.endpoints import Endpoint
from app.avito_gateway.errors import (
    AvitoApiError,
    AvitoAuthError,
    AvitoClientError,
    AvitoNetworkError,
    AvitoRateLimitedError,
    AvitoServerError,
    AvitoTimeoutError,
    AvitoUnexpectedPayloadError,
    ErrorKind,
    ForbiddenEndpointError,
)
from app.avito_gateway.models import RateLimitInfo
from app.avito_gateway.ratelimit import Priority, PriorityRateLimiter

logger = logging.getLogger("app.avito_gateway")

QueryValue = str | int | float | bool | Sequence[str | int]


@dataclass(frozen=True)
class AttemptRecord:
    """One HTTP attempt. Contains no ids, URLs, headers or bodies."""

    endpoint: str
    attempt: int
    priority: Priority
    started_at: datetime
    duration_s: float
    status: int | None
    outcome: str  # "ok" or an ErrorKind value


AttemptHook = Callable[[AttemptRecord], None]


class AllowlistTransport(httpx.AsyncBaseTransport):
    """Wraps the real transport; refuses every request that is not on the read allowlist."""

    def __init__(self, inner: httpx.AsyncBaseTransport, *, host: str, port: int | None) -> None:
        self._inner = inner
        self._host = host
        self._port = port

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != self._host or request.url.port != self._port:
            raise ForbiddenEndpointError("request to a host other than the configured Avito host")
        endpoints.check_allowed(request.method, request.url.path)
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


def build_http_client(
    config: GatewayConfig, transport: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    """An httpx client with the gateway's rules: allowlist guard, no retries, no redirects."""
    parts = urlsplit(config.base_url)
    assert parts.hostname is not None  # checked by GatewayConfig
    inner = transport if transport is not None else httpx.AsyncHTTPTransport(retries=0)
    return httpx.AsyncClient(
        base_url=config.base_url,
        transport=AllowlistTransport(inner, host=parts.hostname, port=parts.port),
        timeout=httpx.Timeout(
            connect=config.connect_timeout_s,
            read=config.read_timeout_s,
            write=config.write_timeout_s,
            pool=config.pool_timeout_s,
        ),
        follow_redirects=False,
        headers={"Accept": "application/json"},
    )


def silence_httpx_url_logs() -> None:
    """httpx logs every request URL at INFO. Our URLs hold ``user_id``/``chat_id`` values, so
    callers that must keep ids out of logs (e.g. the T-010 script) call this once at start-up.
    Not done on import: changing a third-party logger is the application's decision."""
    logging.getLogger("httpx").setLevel(logging.WARNING)


def parse_retry_after(value: str | None, *, now: float | None = None) -> float | None:
    """``Retry-After`` as seconds (delta-seconds or HTTP-date); ``None`` if absent or unusable."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        seconds = float(text)
    except ValueError:
        try:
            when = email.utils.parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        current = now if now is not None else time.time()
        seconds = when.timestamp() - current
    if math.isnan(seconds):
        return None
    return max(0.0, seconds)  # a date in the past means "now"


def _int_header(headers: httpx.Headers, name: str) -> int | None:
    value = headers.get(name)
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def rate_limit_info(headers: httpx.Headers) -> RateLimitInfo:
    return RateLimitInfo(
        limit=_int_header(headers, "X-RateLimit-Limit"),
        remaining=_int_header(headers, "X-RateLimit-Remaining"),
    )


def _api_code(response: httpx.Response) -> str | None:
    """Avito's error code from the three body shapes seen in the spec copy (INTEGRATIONS §3.2)."""
    try:
        body = response.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    code: Any = None
    if isinstance(body, dict):
        if isinstance(body.get("error"), dict):
            code = body["error"].get("code")
        elif "code" in body:
            code = body.get("code")
        elif isinstance(body.get("errors"), list) and body["errors"]:
            first = body["errors"][0]
            code = first.get("code") if isinstance(first, dict) else None
        elif isinstance(body.get("error"), str):
            code = body["error"]
    if code is None or isinstance(code, dict | list):
        return None
    return str(code)[:64]


def classify(endpoint: str, response: httpx.Response, config: GatewayConfig) -> AvitoApiError:
    """Map a non-2xx reply to a typed error."""
    status = response.status_code
    code = _api_code(response)
    if status in (401, 403):
        return AvitoAuthError(endpoint, status=status, api_code=code)
    if status == 429:
        retry_after = parse_retry_after(response.headers.get("Retry-After"))
        if retry_after is not None:
            retry_after = min(retry_after, config.max_retry_after_s)
        info = rate_limit_info(response.headers)
        return AvitoRateLimitedError(
            endpoint,
            api_code=code,
            retry_after=retry_after,
            limit=info.limit,
            remaining=info.remaining,
        )
    if 500 <= status <= 599:
        return AvitoServerError(endpoint, status=status, api_code=code)
    if 300 <= status <= 399:
        return AvitoClientError(endpoint, status=status, detail="redirect not followed")
    return AvitoClientError(endpoint, status=status, api_code=code)


class GatewayHTTP:
    """Sends one allowlisted request per call: rate limit → one HTTP attempt → classify."""

    def __init__(
        self,
        config: GatewayConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        limiter: PriorityRateLimiter | None = None,
        on_attempt: AttemptHook | None = None,
    ) -> None:
        self.config = config
        self.client = build_http_client(config, transport)
        self.limiter = limiter or PriorityRateLimiter(
            config.rate_limits, default=config.default_rate_limit, bulk_share=config.bulk_share
        )
        self._on_attempt = on_attempt
        # Attempts per endpoint name (T-010 reports request counts per endpoint).
        self.attempt_counts: Counter[str] = Counter()

    def __repr__(self) -> str:
        return f"GatewayHTTP(base_url={self.config.base_url!r})"

    async def aclose(self) -> None:
        await self.client.aclose()

    async def send(
        self,
        endpoint: Endpoint,
        *,
        path: str,
        priority: Priority,
        attempt: int,
        params: Mapping[str, QueryValue] | None = None,
        headers: Mapping[str, str] | None = None,
        form: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """Return a 2xx reply or raise a typed error. Exactly one HTTP attempt is made."""
        # Checked here as well as in the transport so a mistake fails before rate limiting.
        if endpoints.match(endpoint.method, path) is not endpoint:
            raise ForbiddenEndpointError(f"{endpoint.method} request is not on the read allowlist")
        await self.limiter.acquire(endpoint.name, priority)
        request = self.client.build_request(
            endpoint.method,
            path,
            params=httpx.QueryParams(_encode_params(params)) if params else None,
            headers=dict(headers) if headers else None,
            data=dict(form) if form else None,
        )
        started_at = datetime.now(UTC)
        start = time.monotonic()
        status: int | None = None
        outcome = "ok"
        try:
            try:
                response = await self.client.send(request)
            except httpx.TimeoutException:
                outcome = ErrorKind.TIMEOUT.value
                raise AvitoTimeoutError(endpoint.name) from None
            except httpx.TransportError as exc:
                outcome = ErrorKind.NETWORK.value
                raise AvitoNetworkError(endpoint.name, detail=type(exc).__name__) from None
            status = response.status_code
            if not 200 <= status <= 299:
                error = classify(endpoint.name, response, self.config)
                outcome = error.kind.value
                if isinstance(error, AvitoRateLimitedError):
                    cooldown = (
                        error.retry_after
                        if error.retry_after is not None
                        else self.config.default_429_cooldown_s
                    )
                    self.limiter.penalize(endpoint.name, cooldown)
                raise error
            return response
        finally:
            duration = time.monotonic() - start
            self.attempt_counts[endpoint.name] += 1
            record = AttemptRecord(
                endpoint=endpoint.name,
                attempt=attempt,
                priority=priority,
                started_at=started_at,
                duration_s=duration,
                status=status,
                outcome=outcome,
            )
            log = logger.info if outcome == "ok" else logger.warning
            log(
                "avito request endpoint=%s attempt=%d priority=%s status=%s outcome=%s ms=%d",
                endpoint.name,
                attempt,
                priority.value,
                status if status is not None else "-",
                outcome,
                int(duration * 1000),
            )
            if self._on_attempt is not None:
                self._on_attempt(record)


def _encode_params(
    params: Mapping[str, QueryValue],
) -> list[tuple[str, str | int | float | bool | None]]:
    """Booleans as ``true``/``false``; sequences as repeated keys (OpenAPI form/explode default,
    UNVERIFIED for Avito arrays such as ``chat_types``, ``item_ids``, ``voice_ids``)."""
    pairs: list[tuple[str, str | int | float | bool | None]] = []
    for key, value in params.items():
        if isinstance(value, bool):
            pairs.append((key, "true" if value else "false"))
        elif isinstance(value, str | int | float):
            pairs.append((key, str(value)))
        else:
            pairs.extend((key, str(v)) for v in value)
    return pairs


def decode_json(endpoint: str, response: httpx.Response) -> Any:
    """Decode a 2xx body; malformed JSON → :class:`AvitoUnexpectedPayloadError`."""
    try:
        return response.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise AvitoUnexpectedPayloadError(
            endpoint, status=response.status_code, reason="invalid_json"
        ) from None

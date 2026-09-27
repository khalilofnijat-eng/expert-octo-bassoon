"""Typed gateway errors (docs/ARCHITECTURE.md §3, read side).

Messages carry only the endpoint *name*, the HTTP status and Avito's short error code. They never
carry request URLs (ids), headers (token), bodies or credentials. Transport exceptions from httpx
are not chained (``raise ... from None``) because they hold a reference to the request, including
its ``Authorization`` header.
"""

from __future__ import annotations

from enum import StrEnum


class ErrorKind(StrEnum):
    AUTH = "auth"
    RATE_LIMITED = "rate_limited"
    CLIENT = "client"
    SERVER = "server"
    TIMEOUT = "timeout"
    NETWORK = "network"
    UNEXPECTED_PAYLOAD = "unexpected_payload"


class ReadErrorClass(StrEnum):
    """What the caller's own retry layer should do (ARCHITECTURE §3 error classes, read side)."""

    RETRYABLE_READ = "retryable_read"
    AUTH = "auth"
    RATE_LIMITED = "rate_limited"
    PERMANENT = "permanent"


_READ_CLASS: dict[ErrorKind, ReadErrorClass] = {
    ErrorKind.AUTH: ReadErrorClass.AUTH,
    ErrorKind.RATE_LIMITED: ReadErrorClass.RATE_LIMITED,
    ErrorKind.CLIENT: ReadErrorClass.PERMANENT,
    ErrorKind.SERVER: ReadErrorClass.RETRYABLE_READ,
    ErrorKind.TIMEOUT: ReadErrorClass.RETRYABLE_READ,
    ErrorKind.NETWORK: ReadErrorClass.RETRYABLE_READ,
    ErrorKind.UNEXPECTED_PAYLOAD: ReadErrorClass.PERMANENT,
}


class AvitoGatewayError(Exception):
    """Base class for everything this package raises on purpose."""


class ForbiddenEndpointError(AvitoGatewayError):
    """A request outside the read allowlist was attempted. No network request was made."""


class MissingCredentialsError(AvitoGatewayError):
    """``AVITO_CLIENT_ID`` / ``AVITO_CLIENT_SECRET`` are not configured (BLOCKERS B-011)."""


class AvitoApiError(AvitoGatewayError):
    """A failed call to Avito. ``kind`` is the classification; ``status`` is None if no reply."""

    kind: ErrorKind = ErrorKind.CLIENT

    def __init__(
        self,
        endpoint: str,
        *,
        status: int | None = None,
        api_code: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.status = status
        # Avito's short error code from the body (``code`` / ``error.code``), if any.
        self.api_code = api_code
        parts = [f"{self.kind.value}", f"endpoint={endpoint}"]
        if status is not None:
            parts.append(f"status={status}")
        if api_code is not None:
            parts.append(f"api_code={api_code}")
        if detail:
            parts.append(detail)
        super().__init__(" ".join(parts))

    @property
    def read_class(self) -> ReadErrorClass:
        return _READ_CLASS[self.kind]

    @property
    def retryable(self) -> bool:
        return self.read_class is ReadErrorClass.RETRYABLE_READ


class AvitoAuthError(AvitoApiError):
    """401 (after one token refresh) or 403; also a rejected token request."""

    kind = ErrorKind.AUTH


class AvitoRateLimitedError(AvitoApiError):
    """429. ``retry_after`` is set only if Avito sent a usable ``Retry-After`` header (UNVERIFIED
    whether it ever does); ``limit``/``remaining`` mirror ``X-RateLimit-*`` if present."""

    kind = ErrorKind.RATE_LIMITED

    def __init__(
        self,
        endpoint: str,
        *,
        status: int | None = 429,
        api_code: str | None = None,
        retry_after: float | None = None,
        limit: int | None = None,
        remaining: int | None = None,
    ) -> None:
        detail = f"retry_after={retry_after:g}s" if retry_after is not None else None
        super().__init__(endpoint, status=status, api_code=api_code, detail=detail)
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining


class AvitoClientError(AvitoApiError):
    """Other 4xx, and unexpected 1xx/3xx (redirects are never followed)."""

    kind = ErrorKind.CLIENT


class AvitoServerError(AvitoApiError):
    kind = ErrorKind.SERVER


class AvitoTimeoutError(AvitoApiError):
    kind = ErrorKind.TIMEOUT


class AvitoNetworkError(AvitoApiError):
    kind = ErrorKind.NETWORK


class AvitoUnexpectedPayloadError(AvitoApiError):
    """A 2xx reply whose body is not JSON or whose top-level shape does not fit the spec copy.

    ``fields`` lists field *names* only; values are never included.
    """

    kind = ErrorKind.UNEXPECTED_PAYLOAD

    def __init__(
        self, endpoint: str, *, status: int | None, reason: str, fields: tuple[str, ...] = ()
    ) -> None:
        detail = f"reason={reason}"
        if fields:
            detail += f" fields={','.join(fields)}"
        super().__init__(endpoint, status=status, detail=detail)
        self.reason = reason
        self.fields = fields

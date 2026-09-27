"""Thin Avito API client written from the spec: tokens, rate limiting, error classes.

Read side only (T-017). Modules:

* ``endpoints``  – the read allowlist; the only POST is ``/token``.
* ``config``     – ``GatewayConfig`` (``AVITO_GATEWAY_*``), ``Credentials`` from ``app.config``.
* ``http``       – allowlist transport guard, one-attempt sending, error classification.
* ``token``      – ``TokenManager`` (``expires_in`` minus margin, single-flight refresh).
* ``ratelimit``  – per-endpoint buckets, ``live`` before ``bulk``, bulk share cap, 429 pause.
* ``client``     – ``AvitoReadClient``: accounts/self, chats, chat, messages, voice files, items.
* ``pagination`` – ``paginate_chats`` / ``paginate_messages`` with guaranteed termination.
* ``send``       – T-018 text-only ``AvitoSendClient`` with its own one-endpoint write
                   allowlist. Deliberately not re-exported here: importing it is an explicit act,
                   and the read modules never import it.

Everything about Avito here comes from a community copy of the official spec and is not verified
live (docs/INTEGRATIONS.md §3); assumptions are marked ``UNVERIFIED (T-010 M#)`` in the code.
"""

from app.avito_gateway.client import AvitoReadClient
from app.avito_gateway.config import Credentials, GatewayConfig, RateLimit
from app.avito_gateway.errors import (
    AvitoApiError,
    AvitoAuthError,
    AvitoClientError,
    AvitoGatewayError,
    AvitoNetworkError,
    AvitoRateLimitedError,
    AvitoServerError,
    AvitoTimeoutError,
    AvitoUnexpectedPayloadError,
    ErrorKind,
    ForbiddenEndpointError,
    MissingCredentialsError,
    ReadErrorClass,
)
from app.avito_gateway.http import AttemptRecord
from app.avito_gateway.pagination import Paginator, StopReason, paginate_chats, paginate_messages
from app.avito_gateway.ratelimit import Priority, PriorityRateLimiter

__all__ = [
    "AttemptRecord",
    "AvitoApiError",
    "AvitoAuthError",
    "AvitoClientError",
    "AvitoGatewayError",
    "AvitoNetworkError",
    "AvitoRateLimitedError",
    "AvitoReadClient",
    "AvitoServerError",
    "AvitoTimeoutError",
    "AvitoUnexpectedPayloadError",
    "Credentials",
    "ErrorKind",
    "ForbiddenEndpointError",
    "GatewayConfig",
    "MissingCredentialsError",
    "Paginator",
    "Priority",
    "PriorityRateLimiter",
    "RateLimit",
    "ReadErrorClass",
    "StopReason",
    "paginate_chats",
    "paginate_messages",
]

"""Access token for ``client_credentials`` (docs/ARCHITECTURE.md §6.9).

* The token lives in memory only, as ``SecretStr``; it never appears in logs, exceptions or repr.
* Validity comes from the reply's ``expires_in`` minus a safety margin (at most half the life).
* Refresh is single-flight: however many callers need a new token at once, one ``POST /token``
  is made and every caller gets its result (or its error).
* After a 401 the client calls :meth:`TokenManager.refresh_after_unauthorized` with the
  generation of the token that failed; if another caller has already replaced it, no new request
  is made.
* Credentials go in a form body, never in the query string (the spec copy lists them as query
  parameters, but its own curl example and the auth section use a form body; a query string
  would put the secret into URLs and access logs).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from pydantic import SecretStr, ValidationError

from app.avito_gateway import endpoints
from app.avito_gateway.config import Credentials
from app.avito_gateway.errors import AvitoAuthError, AvitoClientError, AvitoUnexpectedPayloadError
from app.avito_gateway.http import GatewayHTTP, decode_json
from app.avito_gateway.models import TokenResponse
from app.avito_gateway.ratelimit import Clock, Priority

logger = logging.getLogger("app.avito_gateway")


@dataclass(frozen=True, repr=False)
class AccessToken:
    value: SecretStr
    expires_at: float  # on the manager's clock
    refresh_at: float
    generation: int

    def __repr__(self) -> str:
        return f"AccessToken(generation={self.generation}, value=**********)"

    def header(self) -> str:
        return f"Bearer {self.value.get_secret_value()}"


class TokenManager:
    def __init__(
        self, http: GatewayHTTP, credentials: Credentials, *, clock: Clock = time.monotonic
    ) -> None:
        self._http = http
        self._credentials = credentials
        self._clock = clock
        self._token: AccessToken | None = None
        self._generation = 0
        self._inflight: asyncio.Task[AccessToken] | None = None
        # Number of POST /token requests made (tests and T-010 request counts).
        self.fetch_count = 0

    def __repr__(self) -> str:
        state = "none" if self._token is None else f"generation={self._token.generation}"
        return f"TokenManager(token={state})"

    def _usable(self, token: AccessToken | None) -> bool:
        return token is not None and self._clock() < token.refresh_at

    async def get(self) -> AccessToken:
        """A token that is not within the safety margin of expiry."""
        token = self._token
        if token is not None and self._usable(token):
            return token
        return await self._refresh()

    async def refresh_after_unauthorized(self, failed_generation: int) -> AccessToken:
        """Replace the token that got a 401, unless someone already did."""
        token = self._token
        if token is not None and token.generation != failed_generation and self._usable(token):
            return token
        if token is not None and token.generation == failed_generation:
            self._token = None
        return await self._refresh()

    def invalidate(self) -> None:
        self._token = None

    async def _refresh(self) -> AccessToken:
        if self._inflight is None:
            self._inflight = asyncio.ensure_future(self._fetch())
            self._inflight.add_done_callback(self._clear_inflight)
        # shield: a cancelled caller must not cancel the refresh other callers are waiting for.
        return await asyncio.shield(self._inflight)

    def _clear_inflight(self, task: asyncio.Task[AccessToken]) -> None:
        if self._inflight is task:
            self._inflight = None
        if not task.cancelled():
            # Mark the exception as retrieved even if every waiter was cancelled.
            task.exception()

    async def _fetch(self) -> AccessToken:
        self.fetch_count += 1
        try:
            response = await self._http.send(
                endpoints.TOKEN,
                path=endpoints.TOKEN.path(),
                priority=Priority.LIVE,
                attempt=1,
                form={
                    "grant_type": "client_credentials",
                    "client_id": self._credentials.client_id.get_secret_value(),
                    "client_secret": self._credentials.client_secret.get_secret_value(),
                },
            )
        except AvitoClientError as exc:
            # OAuth servers usually answer bad credentials with 400 (invalid_client); which status
            # Avito uses is UNVERIFIED, so 400 on /token counts as an auth failure too.
            if exc.status == 400:
                raise AvitoAuthError(
                    endpoints.TOKEN.name, status=400, api_code=exc.api_code
                ) from None
            raise
        body = decode_json(endpoints.TOKEN.name, response)
        if not isinstance(body, dict):
            raise AvitoUnexpectedPayloadError(
                endpoints.TOKEN.name, status=response.status_code, reason="shape"
            )
        try:
            parsed = TokenResponse.model_validate(body)
        except ValidationError as exc:
            fields = tuple(sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()}))
            raise AvitoUnexpectedPayloadError(
                endpoints.TOKEN.name, status=response.status_code, reason="shape", fields=fields
            ) from None
        if not parsed.access_token.get_secret_value():
            raise AvitoUnexpectedPayloadError(
                endpoints.TOKEN.name,
                status=response.status_code,
                reason="empty",
                fields=("access_token",),
            )
        ttl = parsed.expires_in
        if ttl is None or ttl <= 0:
            logger.warning("avito token reply without usable expires_in; using fallback ttl")
            ttl = self._http.config.token_ttl_fallback_s
        margin = min(self._http.config.token_safety_margin_s, ttl / 2)
        now = self._clock()
        self._generation += 1
        token = AccessToken(
            value=parsed.access_token,
            expires_at=now + ttl,
            refresh_at=now + ttl - margin,
            generation=self._generation,
        )
        self._token = token
        logger.info("avito token obtained generation=%d ttl_s=%d", token.generation, int(ttl))
        return token

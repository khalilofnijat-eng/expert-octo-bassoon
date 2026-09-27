"""Read-only Avito API client (T-017).

Only the GET endpoints of :data:`app.avito_gateway.endpoints.ALLOWLIST` have methods here; there
is deliberately no method for sending, deleting, ``chatRead``, uploads, webhooks or blacklist
(AGENTS.md §6). Retries are the caller's job, with one exception: after a 401 the token is
refreshed once and the request is repeated once (two attempt records); a second 401 raises
:class:`AvitoAuthError`. ``GatewayConfig.refresh_on_401=False`` turns that off (T-010 stops on
the first 401).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.avito_gateway import endpoints
from app.avito_gateway.config import Credentials, GatewayConfig
from app.avito_gateway.endpoints import Endpoint
from app.avito_gateway.errors import AvitoAuthError, AvitoUnexpectedPayloadError
from app.avito_gateway.http import AttemptHook, GatewayHTTP, QueryValue, decode_json
from app.avito_gateway.http import rate_limit_info as _rate_limit_info
from app.avito_gateway.models import (
    Account,
    Chat,
    Item,
    ItemDetail,
    ItemsMeta,
    Message,
    Page,
    Result,
    SchemaIssue,
    VoiceFiles,
)
from app.avito_gateway.ratelimit import Clock, Priority, PriorityRateLimiter
from app.avito_gateway.token import TokenManager
from app.config import Settings

logger = logging.getLogger("app.avito_gateway")

M = TypeVar("M", bound=BaseModel)


def _error_fields(exc: ValidationError) -> tuple[str, ...]:
    """Field paths of a validation error. Never the input values."""
    return tuple(sorted({".".join(str(p) for p in err["loc"]) or "<root>" for err in exc.errors()}))


class AvitoReadClient:
    def __init__(
        self,
        config: GatewayConfig,
        credentials: Credentials,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        limiter: PriorityRateLimiter | None = None,
        on_attempt: AttemptHook | None = None,
        clock: Clock = time.monotonic,
    ) -> None:
        self._config = config
        self._http = GatewayHTTP(
            config, transport=transport, limiter=limiter, on_attempt=on_attempt
        )
        self._tokens = TokenManager(self._http, credentials, clock=clock)

    @classmethod
    def from_settings(
        cls,
        settings: Settings | None = None,
        *,
        config: GatewayConfig | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        on_attempt: AttemptHook | None = None,
    ) -> AvitoReadClient:
        """Credentials from ``app.config`` (``AVITO_CLIENT_ID``/``AVITO_CLIENT_SECRET``)."""
        return cls(
            config if config is not None else GatewayConfig(),
            Credentials.from_settings(settings),
            transport=transport,
            on_attempt=on_attempt,
        )

    def __repr__(self) -> str:
        return f"AvitoReadClient(base_url={self._config.base_url!r})"

    async def __aenter__(self) -> AvitoReadClient:
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

    @property
    def config(self) -> GatewayConfig:
        return self._config

    @property
    def limiter(self) -> PriorityRateLimiter:
        return self._http.limiter

    @property
    def tokens(self) -> TokenManager:
        return self._tokens

    @property
    def attempt_counts(self) -> dict[str, int]:
        """HTTP attempts per endpoint name so far, ``token`` included."""
        return dict(self._http.attempt_counts)

    # -- endpoints ---------------------------------------------------------------------------

    async def get_self(self, *, priority: Priority = Priority.LIVE) -> Result[Account]:
        """``GET /core/v1/accounts/self`` → the numeric ``user_id`` (``data.id``)."""
        ep = endpoints.ACCOUNT_SELF
        response = await self._get(ep, ep.path(), priority=priority)
        return self._parse_object(ep, response, Account)

    async def list_chats(
        self,
        user_id: int,
        *,
        limit: int | None = None,
        offset: int = 0,
        item_ids: Sequence[int] | None = None,
        unread_only: bool | None = None,
        chat_types: Sequence[str] | None = None,
        priority: Priority = Priority.LIVE,
    ) -> Page[Chat]:
        """One page of ``GET /messenger/v2/accounts/{user_id}/chats``.

        Ordering is UNVERIFIED (T-010 M1). Omitting ``chat_types`` means the server default,
        which the spec copy gives as ``u2i`` only.
        """
        ep = endpoints.CHATS_LIST
        limit = self._check_page(limit, offset)
        params: dict[str, QueryValue] = {"limit": limit, "offset": offset}
        if item_ids:
            params["item_ids"] = list(item_ids)
        if unread_only is not None:
            params["unread_only"] = unread_only
        if chat_types:
            params["chat_types"] = list(chat_types)
        response = await self._get(ep, ep.path(user_id=user_id), params=params, priority=priority)
        body = decode_json(ep.name, response)
        raw_items = self._list_field(ep, response, body, "chats")
        return self._page(ep, response, body, raw_items, Chat, limit=limit, offset=offset)

    async def get_chat(
        self, user_id: int, chat_id: str, *, priority: Priority = Priority.LIVE
    ) -> Result[Chat]:
        """``GET /messenger/v2/accounts/{user_id}/chats/{chat_id}``."""
        ep = endpoints.CHAT_DETAIL
        response = await self._get(ep, ep.path(user_id=user_id, chat_id=chat_id), priority=priority)
        return self._parse_object(ep, response, Chat)

    async def list_messages(
        self,
        user_id: int,
        chat_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
        priority: Priority = Priority.LIVE,
    ) -> Page[Message]:
        """One page of ``GET /messenger/v3/accounts/{user_id}/chats/{chat_id}/messages/``.

        Does not mark the chat read (spec copy; T-010 verifies live). Ordering and offset
        stability are UNVERIFIED (T-010 M2). The spec copy types the reply as a bare JSON array;
        a ``{"messages": [...]}`` object is accepted too (UNVERIFIED which one Avito sends).
        """
        ep = endpoints.MESSAGES_LIST
        limit = self._check_page(limit, offset)
        response = await self._get(
            ep,
            ep.path(user_id=user_id, chat_id=chat_id),
            params={"limit": limit, "offset": offset},
            priority=priority,
        )
        body = decode_json(ep.name, response)
        raw_items = (
            body if isinstance(body, list) else self._list_field(ep, response, body, "messages")
        )
        return self._page(ep, response, body, raw_items, Message, limit=limit, offset=offset)

    async def get_voice_files(
        self, user_id: int, voice_ids: Sequence[str], *, priority: Priority = Priority.LIVE
    ) -> Result[VoiceFiles]:
        """``GET /messenger/v1/accounts/{user_id}/getVoiceFiles`` → temporary URLs (1 hour)."""
        if not voice_ids or any(not isinstance(v, str) or not v for v in voice_ids):
            raise ValueError("voice_ids must be a non-empty list of non-empty strings")
        ep = endpoints.VOICE_FILES
        response = await self._get(
            ep, ep.path(user_id=user_id), params={"voice_ids": list(voice_ids)}, priority=priority
        )
        return self._parse_object(ep, response, VoiceFiles)

    async def list_items(
        self,
        *,
        per_page: int | None = None,
        page: int = 1,
        status: str | Sequence[str] | None = None,
        updated_at_from: str | None = None,
        category: int | None = None,
        priority: Priority = Priority.LIVE,
    ) -> Page[Item]:
        """One page of ``GET /core/v1/items`` (own ads; 25 requests/min per the spec copy)."""
        ep = endpoints.ITEMS_LIST
        per_page = per_page if per_page is not None else self._config.page_limit_default
        if not 1 <= per_page <= self._config.page_limit_max:
            raise ValueError(f"per_page must be between 1 and {self._config.page_limit_max}")
        if page < 1:
            raise ValueError("page must be >= 1")
        params: dict[str, QueryValue] = {"per_page": per_page, "page": page}
        if status:
            # The spec copy's example is a comma-separated string ("active,old").
            params["status"] = status if isinstance(status, str) else ",".join(status)
        if updated_at_from:
            params["updatedAtFrom"] = updated_at_from
        if category is not None:
            params["category"] = category
        response = await self._get(ep, ep.path(), params=params, priority=priority)
        body = decode_json(ep.name, response)
        raw_items = self._list_field(ep, response, body, "resources")
        meta = None
        if isinstance(body, dict) and isinstance(body.get("meta"), dict):
            try:
                meta = ItemsMeta.model_validate(body["meta"])
            except ValidationError as exc:
                self._log_issue(ep, None, _error_fields(exc))
        return self._page(ep, response, body, raw_items, Item, limit=per_page, meta=meta)

    async def get_item(
        self, user_id: int, item_id: int, *, priority: Priority = Priority.LIVE
    ) -> Result[ItemDetail]:
        """``GET /core/v1/accounts/{user_id}/items/{item_id}/`` (partial; 500/min per spec)."""
        ep = endpoints.ITEM_DETAIL
        response = await self._get(ep, ep.path(user_id=user_id, item_id=item_id), priority=priority)
        return self._parse_object(ep, response, ItemDetail)

    # -- internals ---------------------------------------------------------------------------

    def _check_page(self, limit: int | None, offset: int) -> int:
        limit = limit if limit is not None else self._config.page_limit_default
        if not 1 <= limit <= self._config.page_limit_max:
            raise ValueError(f"limit must be between 1 and {self._config.page_limit_max}")
        if not 0 <= offset <= self._config.offset_max:
            raise ValueError(f"offset must be between 0 and {self._config.offset_max}")
        return limit

    async def _get(
        self,
        endpoint: Endpoint,
        path: str,
        *,
        priority: Priority,
        params: Mapping[str, QueryValue] | None = None,
    ) -> httpx.Response:
        token = await self._tokens.get()
        try:
            return await self._http.send(
                endpoint,
                path=path,
                priority=priority,
                attempt=1,
                params=params,
                headers={"Authorization": token.header()},
            )
        except AvitoAuthError as exc:
            if exc.status != 401 or not self._config.refresh_on_401:
                raise
        # One refresh, one repeat; a second 401 propagates.
        token = await self._tokens.refresh_after_unauthorized(token.generation)
        return await self._http.send(
            endpoint,
            path=path,
            priority=priority,
            attempt=2,
            params=params,
            headers={"Authorization": token.header()},
        )

    def _log_issue(self, endpoint: Endpoint, index: int | None, fields: tuple[str, ...]) -> None:
        logger.warning(
            "avito schema mismatch endpoint=%s index=%s fields=%s",
            endpoint.name,
            "-" if index is None else index,
            ",".join(fields),
        )

    def _parse_object(
        self, endpoint: Endpoint, response: httpx.Response, model: type[M]
    ) -> Result[M]:
        body = decode_json(endpoint.name, response)
        if not isinstance(body, dict):
            raise AvitoUnexpectedPayloadError(
                endpoint.name, status=response.status_code, reason="shape"
            )
        try:
            data = model.model_validate(body)
        except ValidationError as exc:
            fields = _error_fields(exc)
            self._log_issue(endpoint, None, fields)
            raise AvitoUnexpectedPayloadError(
                endpoint.name, status=response.status_code, reason="shape", fields=fields
            ) from None
        return Result(
            endpoint=endpoint.name,
            status=response.status_code,
            data=data,
            raw=body,
            rate_limit=_rate_limit_info(response.headers),
        )

    def _list_field(
        self, endpoint: Endpoint, response: httpx.Response, body: Any, key: str
    ) -> list[Any]:
        if isinstance(body, dict) and key in body:
            value = body[key]
            if value is None:  # treated as an empty page (UNVERIFIED whether Avito sends null)
                return []
            if isinstance(value, list):
                return value
        raise AvitoUnexpectedPayloadError(
            endpoint.name, status=response.status_code, reason="shape", fields=(key,)
        )

    def _page(
        self,
        endpoint: Endpoint,
        response: httpx.Response,
        body: Any,
        raw_items: list[Any],
        model: type[M],
        *,
        limit: int | None = None,
        offset: int | None = None,
        meta: ItemsMeta | None = None,
    ) -> Page[M]:
        items: list[M] = []
        issues: list[SchemaIssue] = []
        for index, raw in enumerate(raw_items):
            try:
                items.append(model.model_validate(raw))
            except ValidationError as exc:
                issue = SchemaIssue(index=index, fields=_error_fields(exc))
                issues.append(issue)
                self._log_issue(endpoint, index, issue.fields)
        return Page(
            endpoint=endpoint.name,
            status=response.status_code,
            items=items,
            raw_items=raw_items,
            raw=body,
            issues=tuple(issues),
            limit=limit,
            offset=offset,
            meta=meta,
            rate_limit=_rate_limit_info(response.headers),
        )

# SYNTHETIC: every id, name, text, phone and URL produced here is made up.
"""In-process Avito API mock for tests and dry runs (T-017; reused by T-010, T-020, ...).

Shapes follow the community copy of the official spec (docs/INTEGRATIONS.md §3; unverified).
Use it as an httpx transport::

    mock = AvitoMock.with_synthetic_data()
    client = AvitoReadClient(config_for(mock), mock.credentials(), transport=mock.transport())

Behaviour switches for things the spec does not settle (all UNVERIFIED, see T-010):

* ``chat_order``: ``"updated_desc"`` | ``"updated_asc"`` | ``"insertion"`` (M1)
* ``message_order``: ``"newest_first"`` | ``"oldest_first"`` (M2)
* ``messages_envelope``: ``"array"`` (spec copy) | ``"object"`` (``{"messages": [...]}``)
* ``ignore_offset``: the server returns the first page for any offset
* ``on_messages_request``: hook run before a messages page is served, e.g. to add a message
  and so simulate a sliding offset (M2)

Sending (T-018): ``POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/messages`` stores the
text as an outgoing message of the chat, so later ``messages_list`` reads show it (reconciliation
tests, T-025); stored sends are also listed in :attr:`AvitoMock.sent_messages`. A fault with
``store_first=True`` is applied *after* the message was stored (delivered-then-timeout, 5xx after
store, connection reset after store, malformed 2xx); without it the fault replaces processing
(nothing stored).

Fault injection: :meth:`AvitoMock.inject` queues a :class:`Fault` for an endpoint (or any
endpoint); it is consumed by the next matching request(s). Every request that reaches the mock is
recorded in :attr:`AvitoMock.requests`; requests that match no read endpoint are also counted in
:attr:`AvitoMock.forbidden_hits` (a correct client makes none: its guard stops them first).
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import parse_qs, unquote

import httpx
from pydantic import SecretStr

from app.avito_gateway.config import Credentials, GatewayConfig, RateLimit
from app.avito_gateway.send import SendAuthorization

MOCK_BASE_URL = "https://avito-mock.invalid"
SYNTHETIC_CLIENT_ID = "synthetic-client-id-0001"
SYNTHETIC_CLIENT_SECRET = "synthetic-client-secret-0001"  # not a real secret
SYNTHETIC_USER_ID = 900000001
BASE_TS = 1_750_000_000  # arbitrary synthetic epoch seconds

ChatOrder = Literal["updated_desc", "updated_asc", "insertion"]
MessageOrder = Literal["newest_first", "oldest_first"]
Envelope = Literal["array", "object"]

_ROUTES: list[tuple[str, str, re.Pattern[str]]] = [
    ("token", "POST", re.compile(r"^/token$")),
    ("accounts_self", "GET", re.compile(r"^/core/v1/accounts/self$")),
    ("chats_list", "GET", re.compile(r"^/messenger/v2/accounts/(?P<user_id>\d+)/chats$")),
    (
        "chat_detail",
        "GET",
        re.compile(r"^/messenger/v2/accounts/(?P<user_id>\d+)/chats/(?P<chat_id>[^/]+)$"),
    ),
    (
        "messages_list",
        "GET",
        re.compile(r"^/messenger/v3/accounts/(?P<user_id>\d+)/chats/(?P<chat_id>[^/]+)/messages/$"),
    ),
    ("voice_files", "GET", re.compile(r"^/messenger/v1/accounts/(?P<user_id>\d+)/getVoiceFiles$")),
    ("items_list", "GET", re.compile(r"^/core/v1/items$")),
    (
        "send_text",
        "POST",
        re.compile(r"^/messenger/v1/accounts/(?P<user_id>\d+)/chats/(?P<chat_id>[^/]+)/messages$"),
    ),
    (
        "item_detail",
        "GET",
        re.compile(r"^/core/v1/accounts/(?P<user_id>\d+)/items/(?P<item_id>\d+)/$"),
    ),
]


def _error_body(code: int, message: str) -> dict[str, Any]:
    # ``{"error": {"code", "message"}}`` is the messenger/core shape in the spec copy.
    return {"error": {"code": code, "message": message}}


@dataclass
class Fault:
    """What the mock does instead of answering normally.

    ``raise_exc`` makes the transport raise (timeout / connection error); otherwise the mock
    answers ``status`` with ``body`` (raw bytes, may be invalid JSON) and ``headers``.
    """

    name: str
    status: int = 200
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    raise_exc: type[httpx.TransportError] | None = None
    delay_s: float = 0.0
    # send_text only: process (and store) the message normally first, then apply the fault.
    store_first: bool = False

    @staticmethod
    def json_status(
        name: str, status: int, body: Any, headers: dict[str, str] | None = None
    ) -> Fault:
        return Fault(
            name=name,
            status=status,
            body=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", **(headers or {})},
        )


def unauthorized() -> Fault:
    return Fault.json_status("unauthorized", 401, _error_body(401, "Unauthorized"))


def forbidden() -> Fault:
    return Fault.json_status("forbidden", 403, _error_body(403, "Forbidden"))


def rate_limited(retry_after: str | None = None) -> Fault:
    """429. Whether Avito sends ``Retry-After`` is UNVERIFIED; ``X-RateLimit-*`` are in the spec
    copy for items."""
    headers = {"X-RateLimit-Limit": "25", "X-RateLimit-Remaining": "0"}
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return Fault.json_status(
        "rate_limited", 429, _error_body(429, "Too Many Requests"), headers=headers
    )


def server_error(status: int = 500) -> Fault:
    return Fault.json_status(f"server_{status}", status, _error_body(status, "Error"))


def client_error(status: int = 404) -> Fault:
    return Fault.json_status(f"client_{status}", status, _error_body(status, "Not found"))


def timeout() -> Fault:
    return Fault(name="timeout", raise_exc=httpx.ReadTimeout)


def connect_error() -> Fault:
    return Fault(name="connect_error", raise_exc=httpx.ConnectError)


def malformed_json() -> Fault:
    return Fault(
        name="malformed_json",
        status=200,
        body=b'{"chats": [{"id": "u2i-broken"',
        headers={"Content-Type": "application/json"},
    )


def wrong_shape(body: Any) -> Fault:
    return Fault.json_status("wrong_shape", 200, body)


def delivered_then_timeout() -> Fault:
    """send_text: the message is stored, then the client times out waiting for the reply."""
    return Fault(name="delivered_then_timeout", raise_exc=httpx.ReadTimeout, store_first=True)


def reset_after_store() -> Fault:
    """send_text: the message is stored, then the connection is reset."""
    return Fault(name="reset_after_store", raise_exc=httpx.RemoteProtocolError, store_first=True)


def server_error_after_store(status: int = 500) -> Fault:
    """send_text: the message is stored, then the server answers 5xx."""
    fault = server_error(status)
    fault.name = f"server_{status}_after_store"
    fault.store_first = True
    return fault


def malformed_2xx(body: bytes = b'{"id": "msg-') -> Fault:
    """send_text: the message is stored, then a 200 with a body that is not valid JSON."""
    return Fault(
        name="malformed_2xx",
        status=200,
        body=body,
        headers={"Content-Type": "application/json"},
        store_first=True,
    )


def ok_without_id() -> Fault:
    """send_text: the message is stored, then a 200 JSON object without ``id``."""
    fault = Fault.json_status("ok_without_id", 200, {"created": BASE_TS, "type": "text"})
    fault.store_first = True
    return fault


def redirect(location: str = "https://elsewhere.invalid/") -> Fault:
    return Fault(name="redirect", status=302, headers={"Location": location})


@dataclass
class RecordedRequest:
    method: str
    path: str
    endpoint: str | None
    query: dict[str, list[str]]
    authorized: bool
    form: dict[str, list[str]] = field(default_factory=dict, repr=False)
    json_body: Any = field(default=None, repr=False)


@dataclass
class MockChat:
    index: int
    id: str
    created: int
    updated: int
    item_id: int
    customer_id: int | str
    customer_name: str
    # Stored oldest → newest.
    messages: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _QueuedFault:
    fault: Fault
    endpoint: str | None
    remaining: int


class AvitoMock:
    def __init__(
        self,
        *,
        user_id: int = SYNTHETIC_USER_ID,
        client_id: str = SYNTHETIC_CLIENT_ID,
        client_secret: str = SYNTHETIC_CLIENT_SECRET,
        token_expires_in: float | None = 86400,
        token_delay_s: float = 0.0,
        response_delay_s: float = 0.0,
        chat_order: ChatOrder = "updated_desc",
        message_order: MessageOrder = "newest_first",
        messages_envelope: Envelope = "array",
        ignore_offset: bool = False,
    ) -> None:
        self.user_id = user_id
        self._client_id = client_id
        self._client_secret = client_secret
        self.token_expires_in = token_expires_in
        self.token_delay_s = token_delay_s
        # Delay before answering any non-token request (lets concurrent requests overlap).
        self.response_delay_s = response_delay_s
        self.chat_order: ChatOrder = chat_order
        self.message_order: MessageOrder = message_order
        self.messages_envelope: Envelope = messages_envelope
        self.ignore_offset = ignore_offset
        self.on_messages_request: Callable[[AvitoMock, str, int], None] | None = None

        self.chats: dict[str, MockChat] = {}
        self.items: list[dict[str, Any]] = []
        self.requests: list[RecordedRequest] = []
        self.forbidden_hits: list[RecordedRequest] = []
        # Messages stored through send_text, in order (each also appended to its chat).
        self.sent_messages: list[dict[str, Any]] = []
        self.issued_tokens: list[str] = []
        self._valid_tokens: set[str] = set()
        self._faults: list[_QueuedFault] = []
        self._next_ts = BASE_TS

    # -- construction ------------------------------------------------------------------------

    @classmethod
    def with_synthetic_data(
        cls,
        *,
        n_chats: int = 5,
        messages_per_chat: int = 12,
        n_items: int = 3,
        hashed_customer_ids: bool = False,
        **kwargs: Any,
    ) -> AvitoMock:
        mock = cls(**kwargs)
        for i in range(n_items):
            mock.add_item(title=f"Синтетическая деталь {i + 1}", price=1000 + 100 * i)
        for c in range(n_chats):
            customer: int | str = f"{c:02d}" + "ab" * 15 if hashed_customer_ids else 800000000 + c
            chat = mock.add_chat(
                item_id=mock.items[c % len(mock.items)]["id"] if mock.items else 700000000,
                customer_id=customer,
                customer_name=f"Покупатель {c + 1}",
            )
            for m in range(messages_per_chat):
                if m % 2 == 0:
                    mock.add_message(chat.id, f"Здравствуйте, деталь в наличии? #{c}.{m}")
                else:
                    mock.add_message(chat.id, f"Да, есть. Ответ #{c}.{m}", from_seller=True)
        return mock

    def _tick(self) -> int:
        self._next_ts += 37
        return self._next_ts

    def add_item(self, *, title: str, price: int, status: str = "active") -> dict[str, Any]:
        item_id = 700000000 + len(self.items)
        item = {
            "id": item_id,
            "title": title,
            "price": price,
            "status": status,
            "url": f"{MOCK_BASE_URL}/items/{item_id}",
            "category": {"id": 10, "name": "Запчасти и аксессуары"},
            "address": "Синтетический город, ул. Примерная 1",
        }
        self.items.append(item)
        return item

    def add_chat(self, *, item_id: int, customer_id: int | str, customer_name: str) -> MockChat:
        index = len(self.chats)
        ts = self._tick()
        chat = MockChat(
            index=index,
            id=f"u2i-synthetic{index:04d}~chat",
            created=ts,
            updated=ts,
            item_id=item_id,
            customer_id=customer_id,
            customer_name=customer_name,
        )
        self.chats[chat.id] = chat
        return chat

    def add_message(
        self,
        chat_id: str,
        text: str | None = None,
        *,
        from_seller: bool = False,
        msg_type: str = "text",
        content: dict[str, Any] | None = None,
        created: int | None = None,
    ) -> dict[str, Any]:
        chat = self.chats[chat_id]
        ts = created if created is not None else self._tick()
        body: dict[str, Any] = content if content is not None else {"text": text}
        message = {
            "id": f"msg-{chat.index:04d}-{len(chat.messages):05d}",
            "author_id": self.user_id if from_seller else chat.customer_id,
            "created": ts,
            "direction": "out" if from_seller else "in",
            "type": msg_type,
            "content": body,
            "is_read": from_seller,
            "read": None,
        }
        chat.messages.append(message)
        chat.updated = max(chat.updated, ts)
        return message

    # -- control -----------------------------------------------------------------------------

    def credentials(self) -> Credentials:
        return Credentials(SecretStr(self._client_id), SecretStr(self._client_secret))

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def inject(self, fault: Fault, *, endpoint: str | None = None, times: int = 1) -> None:
        """Queue ``fault`` for the next ``times`` requests to ``endpoint`` (None = any)."""
        self._faults.append(_QueuedFault(fault, endpoint, times))

    def revoke_tokens(self) -> None:
        """Every issued token now gets 401 (simulates expiry or revocation)."""
        self._valid_tokens.clear()

    @property
    def token_requests(self) -> int:
        return sum(1 for r in self.requests if r.endpoint == "token")

    def count(self, endpoint: str) -> int:
        return sum(1 for r in self.requests if r.endpoint == endpoint)

    # -- request handling --------------------------------------------------------------------

    def _take_fault(self, endpoint: str | None) -> Fault | None:
        for queued in self._faults:
            if queued.endpoint is None or queued.endpoint == endpoint:
                queued.remaining -= 1
                if queued.remaining <= 0:
                    self._faults.remove(queued)
                return queued.fault
        return None

    async def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        endpoint: str | None = None
        params: dict[str, str] = {}
        for name, method, pattern in _ROUTES:
            found = pattern.match(path)
            if found and request.method == method:
                endpoint = name
                params = {k: unquote(v) for k, v in found.groupdict().items()}
                break
        query = parse_qs(request.url.query.decode(), keep_blank_values=True)
        form: dict[str, list[str]] = {}
        json_body: Any = None
        if endpoint == "token":
            form = parse_qs(request.content.decode(), keep_blank_values=True)
        elif endpoint == "send_text":
            try:
                json_body = json.loads(request.content or b"null")
            except ValueError:
                json_body = None
        auth = request.headers.get("Authorization", "")
        authorized = auth.startswith("Bearer ") and auth[7:] in self._valid_tokens
        record = RecordedRequest(request.method, path, endpoint, query, authorized, form, json_body)
        self.requests.append(record)
        if endpoint is None:
            self.forbidden_hits.append(record)
            return httpx.Response(405, json=_error_body(405, "Not allowed by mock"))

        fault = self._take_fault(endpoint)
        if fault is not None and fault.store_first and endpoint == "send_text":
            normal = self._respond(endpoint, params, query, authorized, json_body)
            if not 200 <= normal.status_code <= 299:
                return normal  # nothing stored: the fault does not apply
        if fault is not None:
            if fault.delay_s:
                await asyncio.sleep(fault.delay_s)
            if fault.raise_exc is not None:
                raise fault.raise_exc(f"mock {fault.name}", request=request)
            return httpx.Response(fault.status, content=fault.body, headers=fault.headers)

        if endpoint == "token":
            return await self._token(form)
        if self.response_delay_s:
            await asyncio.sleep(self.response_delay_s)
            authorized = auth.startswith("Bearer ") and auth[7:] in self._valid_tokens
        return self._respond(endpoint, params, query, authorized, json_body)

    def _respond(
        self,
        endpoint: str,
        params: dict[str, str],
        query: dict[str, list[str]],
        authorized: bool,
        json_body: Any,
    ) -> httpx.Response:
        if not authorized:
            return httpx.Response(401, json=_error_body(401, "Unauthorized"))
        if "user_id" in params and int(params["user_id"]) != self.user_id:
            return httpx.Response(403, json=_error_body(403, "Forbidden"))
        if endpoint == "send_text":
            return self._send_text(params, json_body)
        handler = getattr(self, f"_{endpoint}")
        response: httpx.Response = handler(params, query)
        return response

    def _send_text(self, params: dict[str, str], body: Any) -> httpx.Response:
        chat = self.chats.get(params["chat_id"])
        if chat is None:
            return httpx.Response(404, json=_error_body(404, "Not found"))
        message = body.get("message") if isinstance(body, dict) else None
        text = message.get("text") if isinstance(message, dict) else None
        if (
            not isinstance(body, dict)
            or body.get("type") != "text"
            or not isinstance(text, str)
            or not text.strip()
            or len(text.encode("utf-16-le")) // 2 > 1000
        ):
            return httpx.Response(400, json=_error_body(400, "Bad request"))
        stored = self.add_message(chat.id, text, from_seller=True)
        self.sent_messages.append(stored)
        # Reply shape from the spec copy: {id, created, type, direction, content}.
        return httpx.Response(
            200,
            json={
                "id": stored["id"],
                "created": stored["created"],
                "type": "text",
                "direction": "out",
                "content": {"text": text},
            },
        )

    async def _token(self, form: dict[str, list[str]]) -> httpx.Response:
        if self.token_delay_s:
            await asyncio.sleep(self.token_delay_s)
        ok = (
            form.get("grant_type") == ["client_credentials"]
            and form.get("client_id") == [self._client_id]
            and form.get("client_secret") == [self._client_secret]
        )
        if not ok:
            # The real status/body for bad credentials is UNVERIFIED; OAuth servers use 400.
            return httpx.Response(400, json={"error": "invalid_client"})
        token = f"mock-access-token-{len(self.issued_tokens) + 1:04d}-synthetic"
        self.issued_tokens.append(token)
        self._valid_tokens.add(token)
        body: dict[str, Any] = {"access_token": token, "token_type": "Bearer"}
        if self.token_expires_in is not None:
            body["expires_in"] = self.token_expires_in
        return httpx.Response(200, json=body)

    @staticmethod
    def _int_param(query: dict[str, list[str]], name: str, default: int) -> int | None:
        values = query.get(name)
        if not values:
            return default
        try:
            return int(values[0])
        except ValueError:
            return None

    def _limit_offset(self, query: dict[str, list[str]]) -> tuple[int, int] | httpx.Response:
        # Ranges from the spec copy's schema: limit 1..100 (default 100), offset 0..1000.
        limit = self._int_param(query, "limit", 100)
        offset = self._int_param(query, "offset", 0)
        if limit is None or offset is None or not 1 <= limit <= 100 or not 0 <= offset <= 1000:
            return httpx.Response(400, json=_error_body(400, "Bad request"))
        return limit, (0 if self.ignore_offset else offset)

    def _chat_json(self, chat: MockChat) -> dict[str, Any]:
        last = chat.messages[-1] if chat.messages else None
        item = next((i for i in self.items if i["id"] == chat.item_id), None)
        return {
            "id": chat.id,
            "created": chat.created,
            "updated": chat.updated,
            "context": {
                "type": "item",
                "value": {
                    "id": chat.item_id,
                    "title": item["title"] if item else "Синтетическая деталь",
                    "price_string": f"{item['price'] if item else 1000} ₽",
                    "status_id": 0,
                    "url": f"{MOCK_BASE_URL}/items/{chat.item_id}",
                    "user_id": self.user_id,
                    "images": {
                        "count": 1,
                        "main": {"140x105": f"{MOCK_BASE_URL}/img/{chat.item_id}.jpg"},
                    },
                },
            },
            "users": [
                {
                    "id": self.user_id,
                    "name": "Синтетический продавец",
                    "public_user_profile": {
                        "user_id": self.user_id,
                        "item_id": chat.item_id,
                        "url": f"{MOCK_BASE_URL}/user/seller",
                        "avatar": {"default": f"{MOCK_BASE_URL}/avatar/s.png", "images": {}},
                    },
                },
                {
                    "id": chat.customer_id,
                    "name": chat.customer_name,
                    "public_user_profile": {
                        "user_id": chat.customer_id,
                        "item_id": chat.item_id,
                        "url": f"{MOCK_BASE_URL}/user/customer",
                        "avatar": {"default": f"{MOCK_BASE_URL}/avatar/c.png", "images": {}},
                    },
                },
            ],
            "last_message": (
                {k: last[k] for k in ("id", "author_id", "created", "direction", "type", "content")}
                if last
                else None
            ),
        }

    def _accounts_self(self, params: dict[str, str], query: dict[str, list[str]]) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": self.user_id,
                "name": "Синтетический продавец",
                "email": "seller@example.com",
                "phone": "70000000000",
                "phones": ["70000000000"],
                "profile_url": f"{MOCK_BASE_URL}/user/seller/profile",
            },
        )

    def _chats_list(self, params: dict[str, str], query: dict[str, list[str]]) -> httpx.Response:
        page = self._limit_offset(query)
        if isinstance(page, httpx.Response):
            return page
        limit, offset = page
        chats = list(self.chats.values())
        if self.chat_order == "updated_desc":
            chats.sort(key=lambda c: c.updated, reverse=True)
        elif self.chat_order == "updated_asc":
            chats.sort(key=lambda c: c.updated)
        if query.get("unread_only") == ["true"]:
            chats = [c for c in chats if any(not m["is_read"] for m in c.messages)]
        if "item_ids" in query:
            wanted = {int(v) for v in query["item_ids"]}
            chats = [c for c in chats if c.item_id in wanted]
        return httpx.Response(
            200, json={"chats": [self._chat_json(c) for c in chats[offset : offset + limit]]}
        )

    def _chat_detail(self, params: dict[str, str], query: dict[str, list[str]]) -> httpx.Response:
        chat = self.chats.get(params["chat_id"])
        if chat is None:
            return httpx.Response(404, json=_error_body(404, "Not found"))
        return httpx.Response(200, json=self._chat_json(chat))

    def _messages_list(self, params: dict[str, str], query: dict[str, list[str]]) -> httpx.Response:
        chat = self.chats.get(params["chat_id"])
        if chat is None:
            return httpx.Response(404, json=_error_body(404, "Not found"))
        page = self._limit_offset(query)
        if isinstance(page, httpx.Response):
            return page
        limit, offset = page
        if self.on_messages_request is not None:
            self.on_messages_request(self, chat.id, offset)
        ordered = list(chat.messages)
        if self.message_order == "newest_first":
            ordered.reverse()
        chunk = ordered[offset : offset + limit]
        body: Any = chunk if self.messages_envelope == "array" else {"messages": chunk}
        return httpx.Response(200, json=body)

    def _voice_files(self, params: dict[str, str], query: dict[str, list[str]]) -> httpx.Response:
        ids = query.get("voice_ids", [])
        if not ids:
            return httpx.Response(400, json=_error_body(400, "Bad request"))
        return httpx.Response(
            200, json={"voices_urls": {v: f"{MOCK_BASE_URL}/voice/{v}.mp4" for v in ids}}
        )

    def _items_list(self, params: dict[str, str], query: dict[str, list[str]]) -> httpx.Response:
        per_page = self._int_param(query, "per_page", 25) or 25
        page = self._int_param(query, "page", 1) or 1
        start = (page - 1) * per_page
        return httpx.Response(
            200,
            json={
                "meta": {"page": page, "per_page": per_page},
                "resources": self.items[start : start + per_page],
            },
        )

    def _item_detail(self, params: dict[str, str], query: dict[str, list[str]]) -> httpx.Response:
        item_id = int(params["item_id"])
        item = next((i for i in self.items if i["id"] == item_id), None)
        if item is None:
            return httpx.Response(200, json={"status": "not_found"})
        return httpx.Response(
            200,
            json={
                "status": item["status"],
                "url": item["url"],
                "start_time": "2025-06-01T10:00:00+03:00",
                "finish_time": "2025-07-01T10:00:00+03:00",
                "autoload_item_id": None,
                "vas": [],
            },
        )


def send_authorization(
    mock: AvitoMock,
    text: str,
    *,
    chat_id: str = "u2i-synthetic0000~chat",
    outbound_message_id: str = "outbox-synthetic-1",
    attempt: int = 1,
) -> SendAuthorization:
    """A synthetic stand-in for what the outbox builds after its intent CAS (tests only)."""
    return SendAuthorization.for_text(
        outbound_message_id=outbound_message_id,
        user_id=mock.user_id,
        chat_id=chat_id,
        text=text,
        attempt=attempt,
        intent_at=datetime.now(UTC),
    )


def config_for_mock(**overrides: Any) -> GatewayConfig:
    """A gateway config pointing at :data:`MOCK_BASE_URL` with rate limits high enough that
    tests are not slowed down. Override anything via keyword arguments."""
    fast = RateLimit(per_minute=60_000, burst=1_000)
    values: dict[str, Any] = {
        "base_url": MOCK_BASE_URL,
        "rate_limits": {},
        "default_rate_limit": fast,
        "default_429_cooldown_s": 0.0,
    }
    values.update(overrides)
    return GatewayConfig(**values)

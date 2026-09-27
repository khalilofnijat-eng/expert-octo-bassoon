"""Typed read models, shaped after the community copy of the official spec (INTEGRATIONS §3).

The spec copy is unofficial and unverified, so the models are lenient: unknown fields are kept
(``extra="allow"``), almost everything is optional, and ids that the spec types as integers but
that may be hashed (T-010 M7/M9) accept ``int | str``. Free text and personal data fields use
``repr=False`` so a stray ``repr()`` in a log line does not leak them.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, SecretStr

# UNVERIFIED (T-010 M7, M9): user ids may be hashed strings rather than int64.
UserId = int | str

# Message types listed by the spec copy. ``Message.type`` stays a plain string so a new type
# does not break parsing; compare against this set where needed.
KNOWN_MESSAGE_TYPES = frozenset(
    {"text", "image", "link", "item", "location", "call", "deleted", "voice", "system"}
)


class _Model(BaseModel):
    # ``coerce_numbers_to_str``: the spec copy shows e.g. ``phone`` typed string with a numeric
    # example; a number where a string is expected must not fail the whole reply.
    model_config = ConfigDict(extra="allow", populate_by_name=True, coerce_numbers_to_str=True)

    def __repr_args__(self) -> Iterator[tuple[str | None, Any]]:
        # Unknown fields are kept but never shown: their content is not known to be safe to log.
        extra = self.model_extra or {}
        for key, value in super().__repr_args__():
            if key not in extra:
                yield key, value


class TokenResponse(_Model):
    access_token: SecretStr
    expires_in: float | None = None
    token_type: str | None = None


class Account(_Model):
    """``GET /core/v1/accounts/self``."""

    id: int
    name: str | None = Field(default=None, repr=False)
    email: str | None = Field(default=None, repr=False)
    phone: str | None = Field(default=None, repr=False)
    phones: list[str] | None = Field(default=None, repr=False)
    profile_url: str | None = Field(default=None, repr=False)


class MessageContent(_Model):
    text: str | None = Field(default=None, repr=False)
    flow_id: str | None = None
    image: dict[str, Any] | None = Field(default=None, repr=False)
    item: dict[str, Any] | None = Field(default=None, repr=False)
    link: dict[str, Any] | None = Field(default=None, repr=False)
    location: dict[str, Any] | None = Field(default=None, repr=False)
    call: dict[str, Any] | None = None
    voice: dict[str, Any] | None = None


class MessageQuote(_Model):
    id: str | None = None
    author_id: UserId | None = None
    created: int | None = None
    type: str | None = None
    content: MessageContent | None = Field(default=None, repr=False)


class Message(_Model):
    """One entry of ``GET /messenger/v3/.../messages/``. Does not mark the chat read (spec copy)."""

    id: str
    created: int
    author_id: UserId | None = None
    direction: str | None = None
    type: str | None = None
    content: MessageContent | None = Field(default=None, repr=False)
    is_read: bool | None = None
    read: int | None = None
    quote: MessageQuote | None = Field(default=None, repr=False)


class LastMessage(_Model):
    id: str | None = None
    author_id: UserId | None = None
    created: int | None = None
    direction: str | None = None
    type: str | None = None
    content: MessageContent | None = Field(default=None, repr=False)


class ChatItemContext(_Model):
    """``context.value`` for ``type == "item"``: the ad the chat is about."""

    id: int | None = None
    title: str | None = Field(default=None, repr=False)
    price_string: str | None = Field(default=None, repr=False)
    status_id: int | None = None
    url: str | None = Field(default=None, repr=False)
    user_id: UserId | None = None
    # {"count": n, "main": {"140x105": url}}
    images: dict[str, Any] | None = Field(default=None, repr=False)


class ChatContext(_Model):
    type: str | None = None
    value: ChatItemContext | None = None


class ChatUser(_Model):
    id: UserId | None = None
    name: str | None = Field(default=None, repr=False)
    public_user_profile: dict[str, Any] | None = Field(default=None, repr=False)


class Chat(_Model):
    """``GET /messenger/v2/.../chats`` entry and ``GET /messenger/v2/.../chats/{chat_id}``."""

    id: str
    created: int | None = None
    updated: int | None = None
    context: ChatContext | None = None
    users: list[ChatUser] | None = None
    last_message: LastMessage | None = None


class VoiceFiles(_Model):
    """``voices_urls``: voice_id → temporary URL (valid one hour per the spec copy)."""

    voices_urls: dict[str, str] = Field(default_factory=dict, repr=False)


class ItemCategory(_Model):
    id: int | None = None
    name: str | None = None


class Item(_Model):
    """``GET /core/v1/items`` entry (own ads)."""

    id: int
    title: str | None = Field(default=None, repr=False)
    price: int | float | None = None
    status: str | None = None
    url: str | None = Field(default=None, repr=False)
    category: ItemCategory | None = None
    address: str | None = Field(default=None, repr=False)


class ItemsMeta(_Model):
    page: int | None = None
    per_page: int | None = None


class ItemDetail(_Model):
    """``GET /core/v1/accounts/{user_id}/items/{item_id}/``: partial (no title/price/photos)."""

    status: str | None = None
    url: str | None = Field(default=None, repr=False)
    start_time: str | None = None
    finish_time: str | None = None
    autoload_item_id: str | None = None
    vas: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class RateLimitInfo:
    """``X-RateLimit-*`` headers as seen on a reply (documented for items; UNVERIFIED elsewhere)."""

    limit: int | None = None
    remaining: int | None = None


T = TypeVar("T", bound=BaseModel)
D = TypeVar("D")


@dataclass(frozen=True)
class SchemaIssue:
    """A list entry that did not fit its model. Only field names are kept, never values."""

    index: int
    fields: tuple[str, ...]


@dataclass(frozen=True)
class Result(Generic[D]):
    """A parsed reply. ``raw`` is the decoded JSON body for a future raw store; never log it."""

    endpoint: str
    status: int
    data: D
    raw: Any = field(repr=False)
    rate_limit: RateLimitInfo = RateLimitInfo()


@dataclass(frozen=True)
class Page(Generic[T]):
    """One page of a list endpoint.

    ``items`` holds the entries that parsed; entries that did not are listed in ``issues`` and
    remain available in ``raw_items`` (same indexes). ``raw_count`` is the number of entries the
    server returned, which is what pagination decisions must use.
    """

    endpoint: str
    status: int
    items: list[T]
    raw_items: list[Any] = field(repr=False)
    raw: Any = field(repr=False)
    issues: tuple[SchemaIssue, ...] = ()
    limit: int | None = None
    offset: int | None = None
    meta: ItemsMeta | None = None
    rate_limit: RateLimitInfo = RateLimitInfo()

    @property
    def raw_count(self) -> int:
        return len(self.raw_items)

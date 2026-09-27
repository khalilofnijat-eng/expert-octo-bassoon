"""``limit``/``offset`` pagination for chats and messages, with guaranteed termination.

Nothing here assumes an ordering (newest-first or otherwise): Avito's ordering and the stability
of ``offset`` under new traffic are UNVERIFIED (T-010 M1 for chats, M2 for messages). Stopping on
"older than X" is therefore the caller's decision, not this helper's. The helper only walks
offsets and stops on the first of:

* ``empty_page``     – the server returned no entries;
* ``short_page``     – fewer entries than ``limit`` (UNVERIFIED that a short page means the end;
                       disable with ``stop_on_short_page=False``, then ``empty_page`` ends it);
* ``no_new_ids``     – every id on the page was already seen (guards against a server that
                       ignores ``offset``, which would otherwise loop forever);
* ``offset_cap``     – the next offset would exceed ``offset_max`` (spec copy: 1000, UNVERIFIED);
* ``max_pages`` / ``max_items`` – caller's caps.

Duplicate ids across pages are counted (``duplicates``) but still yielded, because with a sliding
offset a duplicate is information the caller (dedup, T-010 M2) needs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel

from app.avito_gateway.client import AvitoReadClient
from app.avito_gateway.models import Chat, Message, Page
from app.avito_gateway.ratelimit import Priority

M = TypeVar("M", bound=BaseModel)

FetchPage = Callable[[int, int], Awaitable[Page[M]]]


class StopReason(StrEnum):
    EMPTY_PAGE = "empty_page"
    SHORT_PAGE = "short_page"
    NO_NEW_IDS = "no_new_ids"
    OFFSET_CAP = "offset_cap"
    MAX_PAGES = "max_pages"
    MAX_ITEMS = "max_items"


@dataclass
class Paginator(Generic[M]):
    """Async-iterate to get pages; afterwards ``stop_reason`` says why it ended."""

    fetch: FetchPage[M]
    id_of: Callable[[M], str]
    limit: int
    start_offset: int = 0
    offset_max: int = 1000
    max_pages: int | None = None
    max_items: int | None = None
    stop_on_short_page: bool = True

    stop_reason: StopReason | None = field(default=None, init=False)
    pages: int = field(default=0, init=False)
    items_seen: int = field(default=0, init=False)
    duplicates: int = field(default=0, init=False)
    next_offset: int = field(default=0, init=False)
    _seen: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("limit must be >= 1")
        if not 0 <= self.start_offset <= self.offset_max:
            raise ValueError("start_offset must be between 0 and offset_max")
        self.next_offset = self.start_offset

    def __aiter__(self) -> AsyncIterator[Page[M]]:
        return self._run()

    async def _run(self) -> AsyncIterator[Page[M]]:
        while True:
            if self.max_pages is not None and self.pages >= self.max_pages:
                self.stop_reason = StopReason.MAX_PAGES
                return
            page = await self.fetch(self.limit, self.next_offset)
            self.pages += 1
            new_ids = 0
            for item in page.items:
                item_id = self.id_of(item)
                if item_id in self._seen:
                    self.duplicates += 1
                else:
                    self._seen.add(item_id)
                    new_ids += 1
            self.items_seen += page.raw_count
            yield page
            # Decisions use the number of entries the server sent, not how many parsed.
            if page.raw_count == 0:
                self.stop_reason = StopReason.EMPTY_PAGE
                return
            if page.items and new_ids == 0:
                self.stop_reason = StopReason.NO_NEW_IDS
                return
            if self.stop_on_short_page and page.raw_count < self.limit:
                self.stop_reason = StopReason.SHORT_PAGE
                return
            if self.max_items is not None and self.items_seen >= self.max_items:
                self.stop_reason = StopReason.MAX_ITEMS
                return
            following = self.next_offset + page.raw_count
            if following > self.offset_max:
                self.stop_reason = StopReason.OFFSET_CAP
                return
            self.next_offset = following


def paginate_chats(
    client: AvitoReadClient,
    user_id: int,
    *,
    limit: int | None = None,
    start_offset: int = 0,
    max_pages: int | None = None,
    max_items: int | None = None,
    stop_on_short_page: bool = True,
    item_ids: Sequence[int] | None = None,
    unread_only: bool | None = None,
    chat_types: Sequence[str] | None = None,
    priority: Priority = Priority.LIVE,
) -> Paginator[Chat]:
    async def fetch(page_limit: int, offset: int) -> Page[Chat]:
        return await client.list_chats(
            user_id,
            limit=page_limit,
            offset=offset,
            item_ids=item_ids,
            unread_only=unread_only,
            chat_types=chat_types,
            priority=priority,
        )

    return Paginator(
        fetch=fetch,
        id_of=lambda chat: chat.id,
        limit=limit if limit is not None else client.config.page_limit_default,
        start_offset=start_offset,
        offset_max=client.config.offset_max,
        max_pages=max_pages,
        max_items=max_items,
        stop_on_short_page=stop_on_short_page,
    )


def paginate_messages(
    client: AvitoReadClient,
    user_id: int,
    chat_id: str,
    *,
    limit: int | None = None,
    start_offset: int = 0,
    max_pages: int | None = None,
    max_items: int | None = None,
    stop_on_short_page: bool = True,
    priority: Priority = Priority.LIVE,
) -> Paginator[Message]:
    async def fetch(page_limit: int, offset: int) -> Page[Message]:
        return await client.list_messages(
            user_id, chat_id, limit=page_limit, offset=offset, priority=priority
        )

    return Paginator(
        fetch=fetch,
        id_of=lambda message: message.id,
        limit=limit if limit is not None else client.config.page_limit_default,
        start_offset=start_offset,
        offset_max=client.config.offset_max,
        max_pages=max_pages,
        max_items=max_items,
        stop_on_short_page=stop_on_short_page,
    )

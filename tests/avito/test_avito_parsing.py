# SYNTHETIC: payloads come from tests/fixtures/avito (made-up, spec-shaped).
"""Typed models tolerate unknown fields and per-entry mismatches; raw JSON stays available."""

from __future__ import annotations

import logging

import pytest

from app.avito_gateway import AvitoUnexpectedPayloadError
from app.avito_gateway.models import KNOWN_MESSAGE_TYPES
from scripts.dev.avito_mock import SYNTHETIC_USER_ID, AvitoMock, Fault
from tests.avito.helpers import load_fixture, make_client

pytestmark = pytest.mark.anyio

U = SYNTHETIC_USER_ID
CHAT = "u2i-synthetic0000~chat"


def _serve(mock: AvitoMock, endpoint: str, body: object) -> None:
    mock.inject(Fault.json_status("fixture", 200, body), endpoint=endpoint)


async def test_chats_page_tolerates_unknown_fields_and_hashed_ids(
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = load_fixture("chats_page.json")["body"]
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        _serve(mock, "chats_list", body)
        with caplog.at_level(logging.WARNING, logger="app.avito_gateway"):
            page = await client.list_chats(U)
    assert page.raw_count == 3
    assert [c.id for c in page.items] == ["u2i-fixture0001~chat", "u2i-fixture0002~chat"]
    # Unknown field kept, not dropped.
    assert page.items[1].model_extra == {"future_field_not_in_spec": {"anything": True}}
    # Hashed-looking id stays a string; numeric id stays an int (UNVERIFIED, T-010 M7/M9).
    users = page.items[1].users or []
    assert users[1].id == "3f2a9c0e5b7d41a8b6c2d9e0f1a2b3c4"
    assert users[0].id == 900000001
    # Third entry lacks ``id``: reported by index and field name, raw entry kept.
    assert [(i.index, i.fields) for i in page.issues] == [(2, ("id",))]
    assert page.raw_items[2]["created"] == 1750000300
    assert page.raw == body
    assert "fields=id" in caplog.text
    # Nothing of the entry's content in the log.
    assert "1750000300" not in caplog.text
    assert "Синтетический" not in caplog.text


async def test_messages_page_all_types_and_issues(caplog: pytest.LogCaptureFixture) -> None:
    body = load_fixture("messages_page.json")["body"]
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        _serve(mock, "messages_list", body)
        with caplog.at_level(logging.WARNING, logger="app.avito_gateway"):
            page = await client.list_messages(U, CHAT)
    assert page.raw_count == 13
    assert len(page.items) == 11
    issues = sorted((i.index, i.fields) for i in page.issues)
    assert issues == [(11, ("created",)), (12, ("created",))]
    types = {m.type for m in page.items}
    assert types >= KNOWN_MESSAGE_TYPES
    assert "video_note" in types  # a type the spec copy does not list still parses
    system = next(m for m in page.items if m.type == "system")
    assert system.content is not None and system.content.flow_id == "flower_000000"
    voice = next(m for m in page.items if m.type == "voice")
    assert voice.content is not None and voice.content.voice == {"voice_id": "voice-fx-0001"}
    quoted = next(m for m in page.items if m.quote is not None)
    assert quoted.quote is not None and quoted.quote.id == "msg-fx-0001"
    # Field names only: no values, no message text.
    assert "not-a-timestamp" not in caplog.text
    assert "Синтетика" not in caplog.text
    assert "+7 900" not in caplog.text


async def test_repr_hides_text_and_unknown_fields() -> None:
    body = load_fixture("messages_page.json")["body"]
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        _serve(mock, "messages_list", body)
        page = await client.list_messages(U, CHAT)
    text = repr(page) + "".join(repr(m) for m in page.items)
    assert "Синтетика" not in text
    assert "brand_new_field" not in text
    assert "msg-fx-0001" in text  # ids and types are fine to show


@pytest.mark.parametrize("envelope", ["array", "object"])
async def test_messages_envelopes(envelope: str) -> None:
    mock = AvitoMock.with_synthetic_data(messages_envelope=envelope)
    async with make_client(mock) as client:
        page = await client.list_messages(U, CHAT, limit=5)
    assert len(page.items) == 5


async def test_messages_wrong_shape() -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        _serve(mock, "messages_list", {"items": []})
        with pytest.raises(AvitoUnexpectedPayloadError) as info:
            await client.list_messages(U, CHAT)
    assert info.value.fields == ("messages",)


async def test_single_objects_from_fixtures() -> None:
    objects = load_fixture("objects.json")
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        _serve(mock, "accounts_self", objects["account_self"])
        me = await client.get_self()
        _serve(mock, "chat_detail", objects["chat_detail"])
        chat = await client.get_chat(U, CHAT)
        _serve(mock, "voice_files", objects["voice_files"])
        voice = await client.get_voice_files(U, ["voice-fx-0001"])
        _serve(mock, "items_list", objects["items_page"])
        items = await client.list_items()
        _serve(mock, "item_detail", objects["item_detail"])
        detail = await client.get_item(U, 700000001)
    assert me.data.id == U
    assert me.data.phone == "70000000000"  # numeric in the fixture, coerced to str
    assert "seller@example.com" not in repr(me.data)
    assert chat.data.context is not None and chat.data.context.value is not None
    assert chat.data.context.value.images == {
        "count": 3,
        "main": {"140x105": "https://avito-mock.invalid/img/1.jpg"},
    }
    assert set(voice.data.voices_urls) == {"voice-fx-0001"}
    assert [i.id for i in items.items] == [700000001, 700000002]
    assert items.meta is not None and items.meta.per_page == 25
    assert items.items[1].price is None
    assert detail.data.status == "active"
    assert detail.raw == objects["item_detail"]


async def test_single_object_missing_required_field() -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        _serve(mock, "chat_detail", {"created": 1})
        with pytest.raises(AvitoUnexpectedPayloadError) as info:
            await client.get_chat(U, CHAT)
    assert info.value.fields == ("id",)


async def test_query_parameters_sent() -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        await client.list_chats(
            U, limit=20, offset=40, unread_only=True, chat_types=["u2i", "u2u"], item_ids=[1, 2]
        )
        await client.get_voice_files(U, ["v1", "v2"])
        await client.list_items(per_page=10, page=2, status=["active", "old"])
    chats = next(r for r in mock.requests if r.endpoint == "chats_list")
    assert chats.query == {
        "limit": ["20"],
        "offset": ["40"],
        "unread_only": ["true"],
        "chat_types": ["u2i", "u2u"],
        "item_ids": ["1", "2"],
    }
    voice = next(r for r in mock.requests if r.endpoint == "voice_files")
    assert voice.query == {"voice_ids": ["v1", "v2"]}
    items = next(r for r in mock.requests if r.endpoint == "items_list")
    assert items.query == {"per_page": ["10"], "page": ["2"], "status": ["active,old"]}


@pytest.mark.parametrize(("limit", "offset"), [(0, 0), (100, 0), (50, -1), (50, 1001)])
async def test_page_bounds_checked_locally(limit: int, offset: int) -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        with pytest.raises(ValueError):
            await client.list_chats(U, limit=limit, offset=offset)
        with pytest.raises(ValueError):
            await client.list_messages(U, CHAT, limit=limit, offset=offset)
    assert mock.requests == []

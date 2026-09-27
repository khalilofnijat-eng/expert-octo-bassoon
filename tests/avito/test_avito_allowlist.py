# SYNTHETIC: ids and paths below are made up.
"""The gateway can reach no Avito endpoint that writes or changes anything (AGENTS.md §6)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from app.avito_gateway import AvitoReadClient, ForbiddenEndpointError, endpoints
from scripts.dev.avito_mock import SYNTHETIC_USER_ID, AvitoMock
from tests.avito.helpers import make_client

pytestmark = pytest.mark.anyio

U = SYNTHETIC_USER_ID
C = "u2i-synthetic0000~chat"

# Every write/side-effect endpoint of docs/INTEGRATIONS.md §3.1, plus a few near misses.
WRITE_ENDPOINTS = [
    ("POST", f"/messenger/v1/accounts/{U}/chats/{C}/messages"),  # send text
    ("POST", f"/messenger/v1/accounts/{U}/uploadImages"),  # upload image
    ("POST", f"/messenger/v1/accounts/{U}/chats/{C}/messages/image"),  # send image
    ("POST", f"/messenger/v1/accounts/{U}/chats/{C}/messages/msg-1"),  # delete message
    ("POST", f"/messenger/v1/accounts/{U}/chats/{C}/read"),  # chatRead
    ("POST", "/messenger/v3/webhook"),  # webhook subscribe
    ("POST", "/messenger/v1/subscriptions"),  # webhook list (POST)
    ("POST", "/messenger/v1/webhook/unsubscribe"),  # webhook unsubscribe
    ("POST", f"/messenger/v2/accounts/{U}/blacklist"),  # blacklist
]
NOT_ALLOWED = [
    *WRITE_ENDPOINTS,
    ("GET", f"/messenger/v1/accounts/{U}/chats/{C}/read"),
    ("GET", f"/messenger/v2/accounts/{U}/blacklist"),
    ("GET", "/messenger/v1/subscriptions"),
    ("PUT", f"/messenger/v2/accounts/{U}/chats/{C}"),
    ("DELETE", f"/messenger/v2/accounts/{U}/chats/{C}"),
    ("PATCH", "/core/v1/accounts/self"),
    ("POST", f"/messenger/v2/accounts/{U}/chats"),
    ("POST", f"/messenger/v3/accounts/{U}/chats/{C}/messages/"),
    ("GET", f"/messenger/v3/accounts/{U}/chats/{C}/messages/extra"),
    ("GET", f"/messenger/v2/accounts/{U}/chats/{C}/read"),
    ("GET", "/autoload/v2/items/avito_ids"),  # read-only, but not needed: not allowlisted
    ("GET", "/token"),
]


def test_only_post_is_token() -> None:
    non_get = [e for e in endpoints.ALLOWLIST if e.method != "GET"]
    assert non_get == [endpoints.TOKEN]
    assert endpoints.TOKEN.template == "/token"


@pytest.mark.parametrize(("method", "path"), NOT_ALLOWED)
def test_check_allowed_rejects(method: str, path: str) -> None:
    with pytest.raises(ForbiddenEndpointError):
        endpoints.check_allowed(method, path)


@pytest.mark.parametrize(("method", "path"), NOT_ALLOWED)
async def test_transport_guard_blocks_before_network(method: str, path: str) -> None:
    """Even bypassing the public API, the underlying httpx client cannot reach a write endpoint."""
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        raw_http = client._http.client  # deliberately reaching past the public API
        with pytest.raises(ForbiddenEndpointError):
            await raw_http.request(method, path, json={"type": "text"})
    assert mock.requests == []
    assert mock.forbidden_hits == []


async def test_transport_guard_blocks_other_hosts() -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        with pytest.raises(ForbiddenEndpointError):
            await client._http.client.get("https://elsewhere.invalid/core/v1/accounts/self")
    assert mock.requests == []


def test_client_public_surface_is_read_only() -> None:
    """Adding any public method to the client must be a deliberate, reviewed change."""
    public = {
        name
        for name, member in inspect.getmembers(AvitoReadClient)
        if not name.startswith("_") and callable(member)
    }
    assert public == {
        "aclose",
        "from_settings",
        "get_chat",
        "get_item",
        "get_self",
        "get_voice_files",
        "list_chats",
        "list_items",
        "list_messages",
    }
    forbidden_words = (
        "send",
        "upload",
        "delete",
        "read_chat",
        "mark",
        "webhook",
        "subscri",
        "black",
    )
    assert not [n for n in public if any(w in n.lower() for w in forbidden_words)]


def test_gateway_source_has_no_write_calls() -> None:
    """No module calls httpx's post/put/patch/delete/stream helpers or spells a write method
    anywhere except the ``/token`` endpoint definition."""
    package = Path(endpoints.__file__).resolve().parent
    offenders: list[str] = []
    for source in sorted(package.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"post", "put", "patch", "delete", "stream"}
            ):
                offenders.append(f"{source.name}:{node.lineno} .{node.func.attr}()")
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.upper() in {"POST", "PUT", "PATCH", "DELETE"}
            ):
                offenders.append(f"{source.name}:{node.lineno} {node.value!r}")
    assert offenders == ["endpoints.py:" + str(_token_line()) + " 'POST'"]


def _token_line() -> int:
    source = Path(endpoints.__file__).read_text(encoding="utf-8").splitlines()
    return next(i for i, line in enumerate(source, 1) if line.startswith("TOKEN"))


@pytest.mark.parametrize(
    "chat_id", ["../read", "..", ".", "a/b", "x%2Fread", "a?b=1", "a#b", "a b", "a\\b", ""]
)
async def test_path_injection_rejected_without_request(chat_id: str) -> None:
    mock = AvitoMock.with_synthetic_data()
    async with make_client(mock) as client:
        with pytest.raises(ValueError):
            await client.get_chat(U, chat_id)
        with pytest.raises(ValueError):
            await client.list_messages(U, chat_id)
    assert mock.requests == []


def test_allowlist_matches_every_endpoint_path() -> None:
    samples = {
        "token": ("POST", "/token"),
        "accounts_self": ("GET", "/core/v1/accounts/self"),
        "chats_list": ("GET", f"/messenger/v2/accounts/{U}/chats"),
        "chat_detail": ("GET", f"/messenger/v2/accounts/{U}/chats/{C}"),
        "messages_list": ("GET", f"/messenger/v3/accounts/{U}/chats/{C}/messages/"),
        "voice_files": ("GET", f"/messenger/v1/accounts/{U}/getVoiceFiles"),
        "items_list": ("GET", "/core/v1/items"),
        "item_detail": ("GET", f"/core/v1/accounts/{U}/items/700000001/"),
    }
    assert set(samples) == set(endpoints.BY_NAME)
    for name, (method, path) in samples.items():
        assert endpoints.check_allowed(method, path).name == name

"""The only Avito endpoints this gateway may call: a read-only allowlist.

Source: docs/INTEGRATIONS.md §3.1 (community copy of the official spec, not verified live).
AGENTS.md §6 forbids every call that writes or changes anything on Avito: sending, deleting,
``chatRead``, image upload, webhook (un)subscription, blacklist. None of those endpoints exist
here, and :func:`check_allowed` rejects any request that does not match an entry of
:data:`ALLOWLIST` *before* it reaches the network (it is also enforced by the transport guard in
``app.avito_gateway.http``). The single POST is ``/token``, which only issues an access token.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final
from urllib.parse import quote

from app.avito_gateway.errors import ForbiddenEndpointError

# Path parameter shapes. ``user_id`` and ``item_id`` are int64 in the spec copy. The format of
# ``chat_id`` is not documented (UNVERIFIED): any single path segment is accepted, but values
# that could change the path structure are refused (see ``_check_segment``).
_PARAM_PATTERNS: Final[dict[str, str]] = {
    "user_id": r"[0-9]+",
    "item_id": r"[0-9]+",
    "chat_id": r"[^/]+",
}
_FORBIDDEN_SEGMENT_CHARS: Final = frozenset("/\\?#%")
_SEGMENT_SAFE_CHARS: Final = "-_.~:=@+"


@dataclass(frozen=True)
class Endpoint:
    """One allowed (method, path template) pair."""

    name: str
    method: str
    template: str
    requires_auth: bool = True
    _regex: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        pattern = re.sub(
            r"\\\{(\w+)\\\}",
            lambda m: f"(?P<{m.group(1)}>{_PARAM_PATTERNS[m.group(1)]})",
            re.escape(self.template),
        )
        object.__setattr__(self, "_regex", re.compile(f"^{pattern}$"))

    def path(self, **params: int | str) -> str:
        """Fill the template. Path values are validated and percent-encoded."""
        names = set(re.findall(r"\{(\w+)\}", self.template))
        if names != set(params):
            raise ValueError(f"{self.name}: expected path params {sorted(names)}")
        encoded = {key: _encode_segment(key, value) for key, value in params.items()}
        path = self.template.format(**encoded)
        if not self.matches(self.method, path):
            raise ValueError(f"{self.name}: path params do not fit the template")
        return path

    def matches(self, method: str, path: str) -> bool:
        return method.upper() == self.method and self._regex.match(path) is not None


def _encode_segment(name: str, value: int | str) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{name} must not be a bool")
    if name in ("user_id", "item_id"):
        if isinstance(value, int):
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
            return str(value)
        if not value.isdigit():
            raise ValueError(f"{name} must be numeric")
        return value
    text = str(value)
    _check_segment(name, text)
    return quote(text, safe=_SEGMENT_SAFE_CHARS)


def _check_segment(name: str, text: str) -> None:
    """Refuse values that could escape their path segment (e.g. ``../read``)."""
    if not text or text in (".", "..") or ".." in text:
        raise ValueError(f"{name} is not a valid path segment")
    if any(ch in _FORBIDDEN_SEGMENT_CHARS or ch.isspace() or ord(ch) < 0x20 for ch in text):
        raise ValueError(f"{name} contains characters that are not allowed in a path segment")


TOKEN: Final = Endpoint("token", "POST", "/token", requires_auth=False)
ACCOUNT_SELF: Final = Endpoint("accounts_self", "GET", "/core/v1/accounts/self")
CHATS_LIST: Final = Endpoint("chats_list", "GET", "/messenger/v2/accounts/{user_id}/chats")
CHAT_DETAIL: Final = Endpoint(
    "chat_detail", "GET", "/messenger/v2/accounts/{user_id}/chats/{chat_id}"
)
# The trailing slash is part of the path in the spec copy.
MESSAGES_LIST: Final = Endpoint(
    "messages_list", "GET", "/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages/"
)
VOICE_FILES: Final = Endpoint(
    "voice_files", "GET", "/messenger/v1/accounts/{user_id}/getVoiceFiles"
)
ITEMS_LIST: Final = Endpoint("items_list", "GET", "/core/v1/items")
ITEM_DETAIL: Final = Endpoint("item_detail", "GET", "/core/v1/accounts/{user_id}/items/{item_id}/")

ALLOWLIST: Final[tuple[Endpoint, ...]] = (
    TOKEN,
    ACCOUNT_SELF,
    CHATS_LIST,
    CHAT_DETAIL,
    MESSAGES_LIST,
    VOICE_FILES,
    ITEMS_LIST,
    ITEM_DETAIL,
)
BY_NAME: Final[dict[str, Endpoint]] = {e.name: e for e in ALLOWLIST}


def match(method: str, path: str, allowlist: tuple[Endpoint, ...] = ALLOWLIST) -> Endpoint | None:
    """Return the endpoint of ``allowlist`` (default: the read allowlist) for a request."""
    for endpoint in allowlist:
        if endpoint.matches(method, path):
            return endpoint
    return None


def check_allowed(method: str, path: str, allowlist: tuple[Endpoint, ...] = ALLOWLIST) -> Endpoint:
    """Return the matching endpoint or raise :class:`ForbiddenEndpointError` (no network I/O)."""
    endpoint = match(method, path, allowlist)
    if endpoint is None:
        # The concrete path may carry ids; only the method goes into the message.
        raise ForbiddenEndpointError(f"{method.upper()} request is not on the allowlist")
    return endpoint

"""Deterministic, regex-based PII masker for Russian-context customer messages.

``mask(text)`` replaces personal data with typed tokens such as ``[PHONE_1]`` and returns the
masked text together with typed spans (offsets into the *original* text). The same value
appearing twice in one text gets the same token. Numbering follows the order of appearance.

Detected types
--------------
- ``PHONE``: Russian numbers: ``+7`` / ``7`` / ``8`` prefix plus 10 digits, or a bare 10-digit
  mobile number starting with 9. Spaces, dashes, dots and brackets are accepted as separators,
  including one digit per group (``8 9 0 0 ...``).
- ``EMAIL``: ``local@domain.tld``, including Cyrillic domains (``.рф``).
- ``CARD``: 13-19 digit payment card numbers that pass the Luhn check.
- ``VIN``: 17 characters without I/O/Q, at least one letter, ending in 4 digits. Cyrillic
  look-alike letters (``ХТА...``) are accepted.
- ``PLATE``: standard Russian car plates ``A123BC77`` / ``A123BC777`` in Cyrillic, Latin
  look-alikes or a mix of both.
- ``SOCIAL``: Telegram/VK/WhatsApp (and similar) links such as ``t.me/...``, ``vk.com/...``,
  ``wa.me/...``; ``@handles``; and ``tg: handle`` style mentions.
- ``URL``: ``http(s)://...``, ``www....`` and bare domains with common TLDs.

Deliberately NOT masked (false-positive guards)
-----------------------------------------------
OEM part numbers (``A2138851400``, ``213 885 14 00``, ``A 960 880 01 05``), 5-5 grouped part
numbers (``90915-10003``), body/chassis codes (``W213``, ``X253``), years, prices and mileage.

Known limitations
-----------------
- Regex cannot reliably find personal names or postal addresses; they are NOT masked.
- Numbers written as words (``восемь девятьсот ...``), digits replaced by letters
  (``8 9OO ...``) and spelled-out e-mails (``ivan собака mail точка ru``) are NOT masked.
- Short city numbers without area code (``123-45-67``) and foreign numbers are NOT masked.
- A contiguous 11-digit number starting with 7/8, or a contiguous 10-digit number starting with
  9, is always treated as a phone, even if it is really a part or order number.
- Only the standard private-car plate format is covered (no trailer, motorcycle, taxi, diplomatic
  or military plates). Plates written with spaces must use upper-case letters.
- VINs whose last four characters are not digits are NOT masked.
- A 13-19 digit number that happens to pass the Luhn check is masked as ``CARD``.

Privacy
-------
The token-to-original mapping is built only when ``keep_mapping=True``. It lives in memory only,
is excluded from ``repr()`` and must never be logged or persisted. This module does not log.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum

__all__ = ["MaskResult", "PiiSpan", "PiiType", "mask"]


class PiiType(StrEnum):
    """Kinds of personal data the masker detects. The value is used in the token."""

    EMAIL = "EMAIL"
    SOCIAL = "SOCIAL"
    URL = "URL"
    CARD = "CARD"
    PHONE = "PHONE"
    VIN = "VIN"
    PLATE = "PLATE"


# Tie-breaker when two overlapping candidate spans have the same length: lower number wins.
_PRIORITY: dict[PiiType, int] = {
    PiiType.EMAIL: 0,
    PiiType.SOCIAL: 1,
    PiiType.URL: 2,
    PiiType.CARD: 3,
    PiiType.PHONE: 4,
    PiiType.VIN: 5,
    PiiType.PLATE: 6,
}


@dataclass(frozen=True, slots=True)
class PiiSpan:
    """One masked fragment: offsets refer to the original text; the original value is not kept."""

    type: PiiType
    start: int
    end: int
    token: str


@dataclass(frozen=True, slots=True)
class MaskResult:
    """Masked text, typed spans and (optionally) the in-memory token-to-original mapping."""

    text: str
    spans: tuple[PiiSpan, ...]
    mapping: dict[str, str] | None = field(default=None, repr=False, compare=False)


# ---------------------------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------------------------

_DIGITS = "0123456789"
_TRAILING_PUNCT = ".,;:!?)]}»\"'…"

_EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[^\W\d_]{2,}(?![\w-])")

_SOCIAL_HOSTS = (
    r"t\.me|telegram\.me|telegram\.dog|vk\.com|vk\.ru|vk\.me|wa\.me|api\.whatsapp\.com"
    r"|chat\.whatsapp\.com|whatsapp\.com|instagram\.com|ok\.ru|viber\.click"
)
_SOCIAL_LINK_RE = re.compile(
    rf"(?<![\w.@])(?:https?://)?(?:www\.|m\.)?(?:{_SOCIAL_HOSTS})/[^\s<>\"'«»]+",
    re.IGNORECASE,
)
_HANDLE_RE = re.compile(r"(?<![\w@.])@[A-Za-z][A-Za-z0-9_]{2,31}(?![\w@])")
_KEYWORD_HANDLE_RE = re.compile(
    r"(?<!\w)(?:telegram|tg|телеграмм?|телега|тг|whatsapp|вотсап|ватсап|вацап|viber|вайбер"
    r"|vk|вк|вконтакте|instagram|инстаграм|инста)[ \t]*:[ \t]*"
    r"(?P<handle>[A-Za-z][A-Za-z0-9_.]{2,31})(?![\w@])",
    re.IGNORECASE,
)

_URL_SCHEME_RE = re.compile(r"(?<![\w@])(?:https?://|www\.)[^\s<>\"'«»]+", re.IGNORECASE)
_URL_BARE_RE = re.compile(
    r"(?<![\w@./-])(?:[a-zа-яё0-9](?:[a-zа-яё0-9-]{0,61}[a-zа-яё0-9])?\.)+"
    r"(?:ru|su|com|net|org|info|biz|pro|me|io|shop|store|online|site|рф)"
    r"(?![\w-])(?:/[^\s<>\"'«»]*)?",
    re.IGNORECASE,
)

_CARD_RUN_RE = re.compile(r"(?<![0-9A-Za-z])[0-9](?:[ \t\-]?[0-9]){12,18}(?![0-9A-Za-z])")
_CARD_GROUPED_RE = re.compile(r"(?<![0-9A-Za-z])[0-9]{4}(?:[ \-][0-9]{4}){3}(?![0-9A-Za-z])")

_PHONE_RE = re.compile(
    r"(?<![0-9A-Za-z+])(?:\+[ \t]?)?\(?[0-9](?:[ \t \-.()]{0,3}[0-9]){9,10}(?![0-9A-Za-z])"
)
# Separator positions allowed inside the 10-digit core of a phone (after the 7/8 prefix):
# 3|3|2|2, 3|3|4, 3|7, 3|2|2|3 ... A boundary at position 3 is required when any separator is used.
_PHONE_CORE_BOUNDARIES = frozenset({3, 5, 6, 7, 8})
# Obfuscation "9 0 0 1 2 3 4 5 6 7": every digit is its own group.
_ONE_DIGIT_GROUPS = frozenset(range(1, 10))

_VIN_CHARS = "A-HJ-NPR-Z0-9АВЕКМНРСТХ"
_VIN_RE = re.compile(rf"(?<!\w)[{_VIN_CHARS}]{{13}}[0-9]{{4}}(?!\w)", re.IGNORECASE)

_PLATE_LETTERS = "АВЕКМНОРСТУХABEKMHOPCTYX"
_PLATE_RE = re.compile(
    rf"(?<!\w)[{_PLATE_LETTERS}][ \t]?(?!000)[0-9]{{3}}[ \t]?[{_PLATE_LETTERS}]{{2}}"
    rf"[ \t]?(?:[1279][0-9]{{2}}|(?!00)[0-9]{{2}})(?!\w)",
    re.IGNORECASE,
)

_CYR_TO_LAT = str.maketrans("АВЕКМНОРСТУХ", "ABEKMHOPCTYX")


# ---------------------------------------------------------------------------------------------
# Validators and normalisers
# ---------------------------------------------------------------------------------------------


def _only_digits(value: str) -> str:
    return "".join(ch for ch in value if ch in _DIGITS)


def _luhn_ok(digits: str) -> bool:
    total = 0
    for index, ch in enumerate(reversed(digits)):
        n = ord(ch) - 48
        if index % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _digit_boundaries(value: str) -> tuple[str, set[int]]:
    """Return the digits of ``value`` and the digit positions preceded by a separator."""
    digits: list[str] = []
    boundaries: set[int] = set()
    pending_separator = False
    for ch in value:
        if ch in _DIGITS:
            if pending_separator and digits:
                boundaries.add(len(digits))
            digits.append(ch)
            pending_separator = False
        else:
            pending_separator = True
    return "".join(digits), boundaries


def _is_phone(value: str) -> bool:
    has_plus = value.lstrip("(").startswith("+")
    digits, boundaries = _digit_boundaries(value)
    if len(digits) == 11:
        if digits[0] not in ("7" if has_plus else "78") or digits[1] not in "3456789":
            return False
        core_boundaries = {b - 1 for b in boundaries if b > 1}
    elif len(digits) == 10 and not has_plus:
        if digits[0] != "9":
            return False
        core_boundaries = boundaries
    else:
        return False
    if not core_boundaries or core_boundaries == _ONE_DIGIT_GROUPS:
        return True
    return 3 in core_boundaries and core_boundaries <= _PHONE_CORE_BOUNDARIES


def _preceded_by_oem_prefix(text: str, start: int) -> bool:
    """True for ``A 960 880 01 05``: a lone Latin letter + space before the number (OEM style)."""
    if start < 2 or text[start - 1] not in " \t":
        return False
    letter = text[start - 2]
    if not (letter.isascii() and letter.isalpha()):
        return False
    return start < 3 or not text[start - 3].isalnum()


def _is_card(value: str) -> bool:
    digits = _only_digits(value)
    return 13 <= len(digits) <= 19 and _luhn_ok(digits)


def _is_vin(value: str) -> bool:
    return any(ch.isalpha() for ch in value)


def _is_plate(value: str) -> bool:
    if any(ch in " \t" for ch in value):
        return value == value.upper()
    return True


def _normalize(pii_type: PiiType, value: str) -> str:
    """Key used to give identical values the same token within one text."""
    if pii_type is PiiType.PHONE:
        return _only_digits(value)[-10:]
    if pii_type is PiiType.CARD:
        return _only_digits(value)
    if pii_type in (PiiType.VIN, PiiType.PLATE):
        return "".join(value.split()).upper().translate(_CYR_TO_LAT)
    if pii_type is PiiType.SOCIAL:
        lowered = value.lower().removeprefix("@")
        for prefix in ("https://", "http://"):
            lowered = lowered.removeprefix(prefix)
        return lowered.removeprefix("www.").rstrip("/")
    if pii_type is PiiType.URL:
        lowered = value.lower()
        for prefix in ("https://", "http://"):
            lowered = lowered.removeprefix(prefix)
        return lowered.removeprefix("www.").rstrip("/")
    return value.lower()


# ---------------------------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Candidate:
    type: PiiType
    start: int
    end: int


def _trim_trailing(text: str, start: int, end: int) -> int:
    while end > start and text[end - 1] in _TRAILING_PUNCT:
        end -= 1
    return end


def _from_regex(
    text: str,
    pattern: re.Pattern[str],
    pii_type: PiiType,
    *,
    group: str | int = 0,
    validate: Callable[[str], bool] | None = None,
    trim: bool = False,
) -> Iterator[_Candidate]:
    for match in pattern.finditer(text):
        start, end = match.span(group)
        if trim:
            end = _trim_trailing(text, start, end)
        value = text[start:end]
        if not value or (validate is not None and not validate(value)):
            continue
        yield _Candidate(pii_type, start, end)


def _phone_candidates(text: str) -> Iterator[_Candidate]:
    for match in _PHONE_RE.finditer(text):
        start, end = match.span()
        value = match.group()
        # A leading "(" belongs to the number only when a matching ")" follows inside it.
        if value.startswith("(") and ")" not in value:
            start += 1
            value = value[1:]
        if not value.startswith("+") and _preceded_by_oem_prefix(text, start):
            continue
        if _is_phone(value):
            yield _Candidate(PiiType.PHONE, start, end)


def _candidates(text: str) -> Iterator[_Candidate]:
    yield from _from_regex(text, _EMAIL_RE, PiiType.EMAIL)
    yield from _from_regex(text, _SOCIAL_LINK_RE, PiiType.SOCIAL, trim=True)
    yield from _from_regex(text, _HANDLE_RE, PiiType.SOCIAL)
    yield from _from_regex(text, _KEYWORD_HANDLE_RE, PiiType.SOCIAL, group="handle", trim=True)
    yield from _from_regex(text, _URL_SCHEME_RE, PiiType.URL, trim=True)
    yield from _from_regex(text, _URL_BARE_RE, PiiType.URL, trim=True)
    yield from _from_regex(text, _CARD_RUN_RE, PiiType.CARD, validate=_is_card)
    yield from _from_regex(text, _CARD_GROUPED_RE, PiiType.CARD, validate=_is_card)
    yield from _phone_candidates(text)
    yield from _from_regex(text, _VIN_RE, PiiType.VIN, validate=_is_vin)
    yield from _from_regex(text, _PLATE_RE, PiiType.PLATE, validate=_is_plate)


def _select(candidates: Iterator[_Candidate]) -> list[_Candidate]:
    """Resolve overlaps: the longer span wins (so an e-mail or link inside a URL stays inside it);
    on equal length the higher-priority type wins, then the earlier span."""
    ordered = sorted(
        set(candidates), key=lambda c: (-(c.end - c.start), _PRIORITY[c.type], c.start)
    )
    chosen: list[_Candidate] = []
    for cand in ordered:
        if all(cand.end <= kept.start or cand.start >= kept.end for kept in chosen):
            chosen.append(cand)
    chosen.sort(key=lambda c: c.start)
    return chosen


# ---------------------------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------------------------


def mask(text: str, *, keep_mapping: bool = False) -> MaskResult:
    """Mask PII in ``text``.

    Args:
        text: Untrusted free text (customer message, listing text, log line).
        keep_mapping: When true, ``MaskResult.mapping`` maps each token to the first original
            value seen for it. Keep it in memory only; never log or store it.
    """
    selected = _select(_candidates(text))

    counters: dict[PiiType, int] = {}
    tokens_by_key: dict[tuple[PiiType, str], str] = {}
    mapping: dict[str, str] = {}
    spans: list[PiiSpan] = []
    parts: list[str] = []
    cursor = 0

    for cand in selected:
        original = text[cand.start : cand.end]
        key = (cand.type, _normalize(cand.type, original))
        token = tokens_by_key.get(key)
        if token is None:
            counters[cand.type] = counters.get(cand.type, 0) + 1
            token = f"[{cand.type.value}_{counters[cand.type]}]"
            tokens_by_key[key] = token
            if keep_mapping:
                mapping[token] = original
        spans.append(PiiSpan(cand.type, cand.start, cand.end, token))
        parts.append(text[cursor : cand.start])
        parts.append(token)
        cursor = cand.end

    parts.append(text[cursor:])
    return MaskResult(
        text="".join(parts),
        spans=tuple(spans),
        mapping=mapping if keep_mapping else None,
    )

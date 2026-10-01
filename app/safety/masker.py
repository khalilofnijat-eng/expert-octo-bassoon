"""Deterministic, regex-based PII masker for Russian-context customer messages.

``mask(text)`` replaces personal data with typed tokens such as ``[PHONE_1]`` and returns the
masked text together with typed spans (offsets into the *original* text). The same value
appearing twice in one text gets the same token. Numbering follows the order of appearance.

Detection runs on the shared normalization layer (``app.safety.normalize``, T-034 / D-a):
fullwidth, superscript, circled and other compatibility digits count as digits, invisible
characters (zero-width space, soft hyphen, ...) are ignored, and look-alike Cyrillic letters in
Latin handles/links are folded. Spans are mapped back to the original text, so a masked span
includes any invisible characters inside it.

Detected types
--------------
- ``PHONE``: Russian numbers: ``+7`` / ``7`` / ``8`` prefix plus 10 digits, or a bare 10-digit
  mobile number starting with 9. Spaces, newlines, dashes, dots, slashes, underscores and
  brackets are accepted as separators, including one digit per group (``8 9 0 0 ...``). An
  11-digit ``89…``/``79…`` mobile number is a phone whatever its grouping. The letter O
  (Latin or Cyrillic) is read as zero inside a phone-like run (``8 9OO OOO OO O1``). Foreign
  numbers are recognised only with a leading ``+`` (``+375 …``, 10-13 digits).
- ``EMAIL``: ``local@domain.tld``, including Cyrillic and punycode (``xn--…``) domains.
- ``CARD``: 13-19 digit payment card numbers that pass the Luhn check; groups of four may be
  separated by spaces, dashes, dots or underscores.
- ``VIN``: 17 characters without I/O/Q, at least one letter, ending in 4 digits. Cyrillic
  look-alike letters (``ХТА...``, ``У``) are accepted.
- ``PLATE``: standard Russian car plates ``A123BC77`` / ``A123BC777`` in Cyrillic, Latin
  look-alikes or a mix of both.
- ``SOCIAL``: Telegram/VK/WhatsApp (and similar) links such as ``t.me/...``, ``vk.com/...``,
  ``wa.me/...``; ``@handles`` (Latin or Cyrillic, dots allowed); and handles after a channel
  or account keyword separated by a space, colon or dash: ``tg: handle``, ``тг handle``,
  ``Телеграм - handle``, ``Telegram @ handle``, ``ник: handle``, ``логин handle``.
- ``URL``: ``http(s)://...``, ``www....`` and bare domains with common TLDs (including
  ``.kz``, ``.by``, ``.de``, ``.ly``, ``.cc``, ``.рус``, ``.москва`` and punycode TLDs).

Deliberately NOT masked (false-positive guards)
-----------------------------------------------
OEM part numbers (``A2138851400``, ``213 885 14 00``, ``A 960 880 01 05``), 5-5 grouped part
numbers (``90915-10003``), body/chassis codes (``W213``, ``X253``), years, prices and mileage.
The orchestrator runs ``app.safety.part_numbers.extract_part_number_candidates`` on the
UNMASKED text before masking, so catalog matching still sees numbers the masker takes for a
phone (decision D-i).

Known limitations
-----------------
- Regex cannot reliably find personal names, postal addresses, passport, СНИЛС or ИНН numbers;
  they are NOT masked.
- Numbers written as words (``восемь девятьсот ...``) and spelled-out e-mails
  (``ivan собака mail точка ru``, ``ivan at example dot com``) are NOT masked. E-mails without
  a TLD (``ivan@mail``) and IP-literal domains are NOT masked. Domains with an obfuscated dot
  (``example[.]com``, ``example .com``) are NOT masked. (The output filter denies all of these
  in outgoing text.)
- Short city numbers without area code (``123-45-67``) and foreign numbers without ``+`` are
  NOT masked.
- A contiguous 11-digit number starting with 7/8, a 10-digit number starting with 9, and any
  11-digit ``89…``/``79…`` number are always treated as phones, even if they are really a part
  or order number.
- Only the standard private-car plate format is covered (no trailer, motorcycle, taxi, diplomatic
  or military plates). Plates written with spaces must use upper-case letters; plates without
  a region are NOT masked.
- VINs whose last four characters are not digits are NOT masked.
- A 13-19 digit number that happens to pass the Luhn check (e.g. an EAN barcode) is masked as
  ``CARD``.
- ``@`` handles need at least three characters after the ``@``; a keyword handle must be Latin.

Privacy
-------
The token-to-original mapping is built only when ``keep_mapping=True``. It lives in memory only,
is excluded from ``repr()`` and must never be logged or persisted. This module does not log.
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from app.safety.normalize import NormalizedText, normalize

__all__ = [
    "MAX_MASK_INPUT",
    "MaskInputTooLong",
    "MaskResult",
    "PiiSpan",
    "PiiType",
    "detect_normalized",
    "mask",
]

#: Longest text ``mask()`` accepts (T-041 / Y-12). Longer input raises ``MaskInputTooLong``;
#: the caller routes the message to the owner. Nothing is partially masked.
MAX_MASK_INPUT = 50_000


class MaskInputTooLong(ValueError):
    """The text is longer than ``MAX_MASK_INPUT``; route it to the owner unmasked-unprocessed."""


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
# Patterns (matched on normalized views; see app.safety.normalize)
# ---------------------------------------------------------------------------------------------

_DIGITS = "0123456789"
_TRAILING_PUNCT = ".,;:!?)]}»\"'…"

_TLD_EXTRA = r"|xn--[a-z0-9-]{1,59}"
_EMAIL_RE = re.compile(
    rf"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.(?:[^\W\d_]{{2,}}{_TLD_EXTRA})(?![\w-])",
    re.IGNORECASE,
)

_SOCIAL_HOSTS = (
    r"t\.me|telegram\.me|telegram\.dog|vk\.com|vk\.ru|vk\.me|vk\.cc|wa\.me|api\.whatsapp\.com"
    r"|chat\.whatsapp\.com|whatsapp\.com|instagram\.com|ok\.ru|viber\.click|max\.ru"
)
_SOCIAL_LINK_RE = re.compile(
    rf"(?<![\w.@])(?:https?://)?(?:www\.|m\.)?(?:{_SOCIAL_HOSTS})/[^\s<>\"'«»]+",
    re.IGNORECASE,
)
_HANDLE_RE = re.compile(r"(?<![\w@.])@[^\W\d_][\w.]{2,31}(?![\w@])")
_KEYWORDS = (
    r"telegram|tg|телег(?:а|и|у|е|ой)|телеграмм?\w*|тг|whats\s?app|в[оа]т?[сц]\s?ап\w*"
    r"|вацап\w*|viber|вайбер\w*|vk|вк|вконтакте|instagram|insta|инст(?:а|у|е|ы|ой)|инстаграм\w*"
    r"|discord|дискорд\w*|skype|скайп\w*|ник(?:нейм\w*|а|е|ом)?|nick(?:name)?|логин\w*|login"
    r"|аккаунт\w*|акк|account|username|юзернейм\w*"
)
_KEYWORD_HANDLE_RE = re.compile(
    rf"(?<!\w)(?:{_KEYWORDS})[ \t]*[:\-—–]?[ \t]*@?[ \t]*"
    r"(?P<handle>(?!avito\b)[A-Za-z][A-Za-z0-9_.]{2,31})(?![\w@])",
    re.IGNORECASE,
)

_URL_SCHEME_RE = re.compile(r"(?<![\w@])(?:https?://|www\.)[^\s<>\"'«»]+", re.IGNORECASE)
_URL_BARE_RE = re.compile(
    r"(?<![\w@./-])(?:[a-zа-яё0-9](?:[a-zа-яё0-9-]{0,61}[a-zа-яё0-9])?\.)+"
    r"(?:ru|su|com|net|org|info|biz|pro|me|io|shop|store|online|site"
    r"|kz|by|ua|uz|de|ly|cc|xyz|market" + _TLD_EXTRA + r")"
    r"(?![\w-])(?:/[^\s<>\"'«»]*)?",
    re.IGNORECASE,
)
# Cyrillic TLDs need a label of two or more characters: "г.Москва" is a city, not a domain.
_URL_BARE_CYR_RE = re.compile(
    r"(?<![\w@./-])(?:[a-zа-яё0-9][a-zа-яё0-9-]{0,61}[a-zа-яё0-9]\.)+(?:рф|рус|москва)"
    r"(?![\w-])(?:/[^\s<>\"'«»]*)?",
    re.IGNORECASE,
)

_CARD_RUN_RE = re.compile(r"(?<![0-9A-Za-z])[0-9](?:[ \t\-]?[0-9]){12,18}(?![0-9A-Za-z])")
_CARD_GROUPED_RE = re.compile(
    r"(?<![0-9A-Za-z])[0-9]{4}(?:[ \t\-._]{1,2}[0-9]{4}){3}(?![0-9A-Za-z])"
)

_PHONE_SEP = r"[ \t\r\n\-.()/_]"
_PHONE_RE = re.compile(
    rf"(?<![0-9A-Za-z+])(?:\+[ \t]?)?\(?[0-9](?:{_PHONE_SEP}{{0,3}}[0-9]){{9,10}}(?![0-9A-Za-z])"
)
_PLUS_PHONE_RE = re.compile(
    rf"(?<![0-9A-Za-z+])\+[ \t]?\(?[0-9](?:{_PHONE_SEP}{{0,3}}[0-9]){{9,12}}(?![0-9A-Za-z])"
)
# A phone-like run in which the letter O (Latin or Cyrillic) may stand for zero.
_O_PHONE_RUN_RE = re.compile(
    rf"(?<![^\W\d_])[0-9OoОо](?:{_PHONE_SEP}{{0,3}}[0-9OoОо]){{9,12}}(?![^\W\d_])"
)
_O_TO_ZERO = str.maketrans("OoОо", "0000")
# Separator positions allowed inside the 10-digit core of a phone (after the 7/8 prefix):
# 3|3|2|2, 3|3|4, 3|7, 3|2|2|3 ... A boundary at position 3 is required when any separator is used.
_PHONE_CORE_BOUNDARIES = frozenset({3, 5, 6, 7, 8})
# Obfuscation "9 0 0 1 2 3 4 5 6 7": every digit is its own group.
_ONE_DIGIT_GROUPS = frozenset(range(1, 10))

_VIN_CHARS = "A-HJ-NPR-Z0-9АВЕКМНРСТХУ"
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
    if len(digits) == 11 and digits[0] in "78" and digits[1] == "9":
        # Mobile number: accepted whatever the grouping ("89 000 000 001").
        return has_plus is False or digits[0] == "7"
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


def _is_foreign_phone(value: str) -> bool:
    digits = _only_digits(value)
    return 10 <= len(digits) <= 13 and not digits.startswith("7")


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
# Candidate generation (normalized coordinates)
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


def _phone_view(text: str) -> str:
    """``text`` with the letter O read as zero inside phone-like runs (same length)."""
    parts: list[str] = []
    cursor = 0
    for match in _O_PHONE_RUN_RE.finditer(text):
        run = match.group()
        if sum(ch in _DIGITS for ch in run) < 2:
            continue
        parts.append(text[cursor : match.start()])
        parts.append(run.translate(_O_TO_ZERO))
        cursor = match.end()
    parts.append(text[cursor:])
    return "".join(parts)


def _phone_candidates(text: str) -> Iterator[_Candidate]:
    for match in _PHONE_RE.finditer(text):
        start, end = match.span()
        value = match.group()
        # A leading "(" belongs to the number only when a matching ")" follows inside it.
        if value.startswith("(") and ")" not in value:
            start += 1
            value = value[1:]
        if (
            not value.startswith("+")
            and len(_only_digits(value)) == 10
            and _preceded_by_oem_prefix(text, start)
        ):
            continue
        if _is_phone(value):
            yield _Candidate(PiiType.PHONE, start, end)
    yield from _from_regex(text, _PLUS_PHONE_RE, PiiType.PHONE, validate=_is_foreign_phone)


def _link_candidates(view: str) -> Iterator[_Candidate]:
    yield from _from_regex(view, _EMAIL_RE, PiiType.EMAIL)
    yield from _from_regex(view, _SOCIAL_LINK_RE, PiiType.SOCIAL, trim=True)
    yield from _from_regex(view, _HANDLE_RE, PiiType.SOCIAL, trim=True)
    yield from _from_regex(view, _KEYWORD_HANDLE_RE, PiiType.SOCIAL, group="handle", trim=True)
    yield from _from_regex(view, _URL_SCHEME_RE, PiiType.URL, trim=True)
    yield from _from_regex(view, _URL_BARE_RE, PiiType.URL, trim=True)
    yield from _from_regex(view, _URL_BARE_CYR_RE, PiiType.URL, trim=True)


def _candidates(nt: NormalizedText) -> Iterator[_Candidate]:
    text = nt.text
    yield from _link_candidates(text)
    if nt.lat != text:
        yield from _link_candidates(nt.lat)
    yield from _from_regex(text, _CARD_RUN_RE, PiiType.CARD, validate=_is_card)
    yield from _from_regex(text, _CARD_GROUPED_RE, PiiType.CARD, validate=_is_card)
    yield from _phone_candidates(_phone_view(text))
    yield from _from_regex(text, _VIN_RE, PiiType.VIN, validate=_is_vin)
    yield from _from_regex(text, _PLATE_RE, PiiType.PLATE, validate=_is_plate)


def _select(candidates: Iterator[_Candidate]) -> list[_Candidate]:
    """Resolve overlaps: the longer span wins (so an e-mail or link inside a URL stays inside it);
    on equal length the higher-priority type wins, then the earlier span.

    O(k log k) comparisons (T-041 / Y-12): the chosen spans are kept sorted and never overlap,
    so a candidate only has to be compared with its two neighbours."""
    ordered = sorted(
        set(candidates), key=lambda c: (-(c.end - c.start), _PRIORITY[c.type], c.start)
    )
    starts: list[int] = []
    chosen: list[_Candidate] = []
    for cand in ordered:
        i = bisect.bisect_right(starts, cand.start)
        if i > 0 and chosen[i - 1].end > cand.start:
            continue
        if i < len(chosen) and chosen[i].start < cand.end:
            continue
        starts.insert(i, cand.start)
        chosen.insert(i, cand)
    return chosen


# ---------------------------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------------------------


def detect_normalized(nt: NormalizedText) -> list[tuple[PiiType, int, int]]:
    """Non-overlapping PII detections as ``(type, start, end)`` in *normalized* coordinates
    (``nt.text`` / ``nt.cyr`` / ``nt.lat``). Used by the output filter."""
    return [(c.type, c.start, c.end) for c in _select(_candidates(nt))]


def mask(text: str, *, keep_mapping: bool = False) -> MaskResult:
    """Mask PII in ``text``.

    Args:
        text: Untrusted free text (customer message, listing text, log line).
        keep_mapping: When true, ``MaskResult.mapping`` maps each token to the first original
            value seen for it. Keep it in memory only; never log or store it.

    Raises:
        MaskInputTooLong: ``text`` is longer than ``MAX_MASK_INPUT`` characters.
    """
    if len(text) > MAX_MASK_INPUT:
        raise MaskInputTooLong(f"text longer than {MAX_MASK_INPUT} characters")
    nt = normalize(text)
    counters: dict[PiiType, int] = {}
    tokens_by_key: dict[tuple[PiiType, str], str] = {}
    mapping: dict[str, str] = {}
    spans: list[PiiSpan] = []
    parts: list[str] = []
    cursor = 0

    for pii_type, n_start, n_end in detect_normalized(nt):
        start, end = nt.to_original(n_start, n_end)
        original = text[start:end]
        key = (pii_type, _normalize(pii_type, nt.text[n_start:n_end]))
        token = tokens_by_key.get(key)
        if token is None:
            counters[pii_type] = counters.get(pii_type, 0) + 1
            token = f"[{pii_type.value}_{counters[pii_type]}]"
            tokens_by_key[key] = token
            if keep_mapping:
                mapping[token] = original
        spans.append(PiiSpan(pii_type, start, end, token))
        parts.append(text[cursor:start])
        parts.append(token)
        cursor = end

    parts.append(text[cursor:])
    return MaskResult(
        text="".join(parts),
        spans=tuple(spans),
        mapping=mapping if keep_mapping else None,
    )

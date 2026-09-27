"""Output filter (docs/ARCHITECTURE.md §7.2): a pure, deterministic check of outgoing text.

``check_parts(parts, allowed_literals=..., context=..., config=...)`` receives the final message
parts exactly as they would be sent (placeholders already rendered, text already split) and
returns one verdict per part: allowed or denied, with machine-readable reason codes and spans
(offsets into that part). It never changes the text, never logs and keeps no matched values:
the caller already holds the text and can slice it with the spans.

All matching runs on the shared normalization layer (``app.safety.normalize``): NFKC,
invisible characters removed, look-alike letters folded; spans are mapped back to the part.

Inputs and contracts
--------------------
- ``parts``: the rendered parts (a sequence of ``str``; a bare ``str`` or a non-``str`` element
  raises ``TypeError``).
- ``allowed_literals``: the fact sheet's ``allowed_literals`` (§3.1). **Contract (D-j):** they
  come only from fact-sheet and product records (code placeholders, catalog OEM/SKU, body code,
  year, quantity) and are NEVER derived from customer free text. Use
  ``app.safety.literals.literal_variants`` to add the usual spellings of a value. Digits,
  currency words/symbols and number words are allowed only inside an occurrence of one of these
  strings. A bare ``str`` or a non-``str`` element raises ``TypeError``.
- ``context`` (``FilterContext``):

  - ``template_spans`` (**contract, D-f**): per part, the ``(start, end)`` offsets of
    code-owned, constant template text in that final part (``{{rule:…}}`` business-rule text,
    the fixed words of an offer/confirmation block, the bot-disclosure template). Supplied by
    the renderer (T-023). Interpolated untrusted values (listing titles, customer text, LLM
    text) must never lie inside a span: the renderer splits a template around them. Text that
    merely repeats template wording gets no exemption.
  - ``is_owner_edit`` (**contract, D-g**): set only by code, and only for text that comes from
    the owner's admin-UI edit. Never derive it from message content.
  - ``completion_confirmed`` / ``payment_confirmed`` / ``fitment_verified``: record flags.
  - ``automation_mode`` does not relax any rule; it is carried for the audit trail only.
- ``config`` (``FilterConfig``): URL host allowlist (empty by default: every URL is denied) and
  the part size limits.

Reason codes
------------
Hard block (never overridable, also in owner-edit mode):

- ``EMPTY_PART``: nothing visible is left after removing invisible characters.
- ``PART_TOO_LONG``: more than ``max_utf16_units`` UTF-16 code units OR more than
  ``max_utf8_bytes`` UTF-8 bytes (both 1000 by default, D-k; Avito's counting unit is not
  verified). The span starts at the first character beyond a limit. ``measure_part()`` gives
  the same numbers to the splitter. A part longer than four times the limit is checked only
  for size, invisible and invalid characters (it cannot be sent in any case).
- ``INVALID_TEXT``: lone surrogates or control characters (other than tab/newline/CR).

Obfuscation and rendering:

- ``OBFUSCATION``: an invisible/format character (Cf, Hangul filler, Braille blank, …), a word
  mixing Latin/Cyrillic/Greek letters ("Cкидка"), or a word spelled out letter by letter
  ("З в о н и т е"). Emoji ZWJ sequences also contain a Cf character and are denied.
- ``UNRENDERED_TOKEN``: a ``{{placeholder}}`` left unrendered or a masker token (``[PHONE_1]``).

Contacts and channels (never exempt, not even inside ``allowed_literals`` or template spans,
except where noted):

- ``CONTACT_PHONE``: phone number (masker detector). Exempt only when the whole number lies
  inside an ``allowed_literals`` occurrence (an OEM number the masker reads as a phone).
- ``CONTACT_EMAIL``: e-mail address (masker detector) or a spelled-out one ("ivan(at)…",
  "собака … точка").
- ``CONTACT_SOCIAL``: messenger/social link, ``@handle`` or keyword handle (masker detector), or
  any other ``@`` sign.
- ``CONTACT_CHANNEL``: an off-platform channel is named (WhatsApp, Telegram, ВК, MAX, e-mail,
  "в личку", …).
- ``CONTACT_REDIRECT``: a request for, or a redirect to, off-platform contact ("позвоните",
  "дайте номер", "напишите на почту", "напрямую", "без Авито", "наш сайт", "call me").
- ``URL_NOT_ALLOWED``: a URL, any ``scheme://``, ``//host``, ``label.tld`` with any TLD, or a
  domain with an obfuscated dot (``[.]``, ``(.)``, " точка ", " dot ") whose host is not on
  ``FilterConfig.url_allowlist``. An allowlisted URL must also be clean: strict host syntax
  (``\\``, ``@``, ``%``, ``;`` … anywhere means "not allowed"), no ``//`` in the path and no
  domain in the query.

Payment:

- ``PAYMENT_CARD``: a payment card number (masker detector, Luhn-checked). Exempt only inside an
  ``allowed_literals`` occurrence, like ``CONTACT_PHONE``.
- ``PAYMENT_OFF_PLATFORM``: an off-platform payment offer ("переведите на карту", "предоплата",
  СБП, QR, bank names, "аванс", crypto, "без безопасной сделки"). Not exempt inside templates.
- ``PAYMENT_TERMS_UNCONFIRMED``: cash / payment on meeting / card on receipt (D-l): denied
  until the owner's payment rules are known (B-005). Not exempt inside templates.

Numbers and money (exempt inside ``allowed_literals`` occurrences and template spans):

- ``DIGITS_NOT_ALLOWED``: a run of digits (after NFKC, so ``⁸``, ``８``, ``①``, ``٤`` count).
  Digits inside a reported contact/card/URL/token span are not reported again.
- ``CURRENCY``: currency symbol or word (₽, руб, коп., $, евро, USD, "500р", "т.р.", "рэ").
- ``NUMBER_WORD``: a number written as a word or money slang ("пятьсот", "две тысячи",
  "полторы", "тыс", "косарь", "пятихатка", "пол цены", "процент", "%"), best effort.

Promises (exempt only inside template spans; negated or platform-rule wording passes):

- ``PROMISE_DISCOUNT``: discount, bargaining or free-of-charge offer ("скину цену", "торг",
  "бесплатно", "доставка за наш счёт").
- ``PROMISE_RETURN``: return, refund or exchange ("вернём деньги", "заменим"). "Возврат по
  правилам Авито" passes.
- ``PROMISE_WARRANTY``: warranty or guarantee ("гарантия", "ручаюсь").
- ``PROMISE_DELIVERY_DATE``: a concrete delivery/dispatch time ("доставим завтра", "будет у
  вас в пятницу").
- ``UNVERIFIED_FITMENT``: an affirmative fitment claim ("подойдёт", "подходит", "встанет",
  "совместима"), D-c; allowed when ``context.fitment_verified`` is true, when negated ("не
  подойдёт") or in a question/hedge sentence (ли, "?", если, проверим/уточним).

Completion claims (allowed only when the flag is set AND the claim lies inside a template span;
negated wording such as "ещё не оформлен" passes):

- ``COMPLETION_CLAIM``: "заказ оформлен", "забронировал", "отложил/держу для вас",
  "отправил", "в пути"; flag ``context.completion_confirmed``.
- ``PAYMENT_RECEIVED_CLAIM``: "оплата получена", "деньги пришли"; flag
  ``context.payment_confirmed``.

Honesty:

- ``HUMAN_CLAIM``: the text claims to be a human or a named person, or denies being a bot
  ("я живой человек", "я менеджер", "на связи Иван", "я не бот"). The honest disclosure
  ("я автоматический помощник продавца, не человек", "я продавец-бот") passes.

Modes (D-g, fail-closed)
------------------------
A part with any finding has ``allowed=False`` in every mode. In owner-edit mode
(``is_owner_edit=True``) such a part is ``overridable=True`` unless it has a hard-block code;
the send path then requires an audited owner override token for it. ``FilterResult.allowed`` is
true only when every part is allowed.

Matching rules
--------------
- ``allowed_literals`` match case-insensitively on the normalized, Latin-folded text; any
  whitespace run in a literal matches any whitespace run in the text; trailing punctuation of a
  literal is ignored ("2 шт." also matches "2 шт,"). A literal edge may not touch a letter or
  digit on the left; on the right a digit edge may not touch a digit and a letter edge may not
  touch a letter or digit: ``2018`` does not cover ``20185``, ``4`` does not cover ``x4``,
  ``W213`` does not cover ``W2130``, but ``2020`` covers ``2020г``. Literals without any letter
  or digit are ignored.
- A finding is exempt only when it lies entirely inside one literal occurrence / template span.

Known limitations (tested as strict xfail)
------------------------------------------
- Number words are a stem list: typos ("пятсот"), "штука"/"один" (too common), Roman numerals
  and Turkish "bir/on/yüz/bin/altı" are NOT detected.
- An allowed literal is not tied to its meaning: a year literal reused as a price ("отдам за
  2018") passes (D-j contract: literals only from records).
- Phrase patterns are best effort; missed cases must become new patterns plus eval scenarios.
  Negation is recognised only right before/after a phrase; "Мы не используем WhatsApp" is still
  denied (channel names never pass).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.config import AutomationMode
from app.safety import filter_patterns as fp
from app.safety.masker import PiiType, detect_normalized
from app.safety.normalize import (
    NormalizedText,
    mixed_script_spans,
    normalize,
    spaced_letter_spans,
)

__all__ = [
    "HARD_BLOCK_CODES",
    "RULES_VERSION",
    "FilterConfig",
    "FilterContext",
    "FilterResult",
    "Finding",
    "PartSize",
    "PartVerdict",
    "ReasonCode",
    "check_parts",
    "measure_part",
    "part_fits",
]

RULES_VERSION = f"filter-{fp.PATTERNS_VERSION}"


class ReasonCode(StrEnum):
    """Why a part was denied. See the module docstring."""

    EMPTY_PART = "EMPTY_PART"
    PART_TOO_LONG = "PART_TOO_LONG"
    INVALID_TEXT = "INVALID_TEXT"
    OBFUSCATION = "OBFUSCATION"
    UNRENDERED_TOKEN = "UNRENDERED_TOKEN"
    CONTACT_PHONE = "CONTACT_PHONE"
    CONTACT_EMAIL = "CONTACT_EMAIL"
    CONTACT_SOCIAL = "CONTACT_SOCIAL"
    CONTACT_CHANNEL = "CONTACT_CHANNEL"
    CONTACT_REDIRECT = "CONTACT_REDIRECT"
    URL_NOT_ALLOWED = "URL_NOT_ALLOWED"
    PAYMENT_CARD = "PAYMENT_CARD"
    PAYMENT_OFF_PLATFORM = "PAYMENT_OFF_PLATFORM"
    PAYMENT_TERMS_UNCONFIRMED = "PAYMENT_TERMS_UNCONFIRMED"
    DIGITS_NOT_ALLOWED = "DIGITS_NOT_ALLOWED"
    CURRENCY = "CURRENCY"
    NUMBER_WORD = "NUMBER_WORD"
    PROMISE_DISCOUNT = "PROMISE_DISCOUNT"
    PROMISE_RETURN = "PROMISE_RETURN"
    PROMISE_WARRANTY = "PROMISE_WARRANTY"
    PROMISE_DELIVERY_DATE = "PROMISE_DELIVERY_DATE"
    UNVERIFIED_FITMENT = "UNVERIFIED_FITMENT"
    COMPLETION_CLAIM = "COMPLETION_CLAIM"
    PAYMENT_RECEIVED_CLAIM = "PAYMENT_RECEIVED_CLAIM"
    HUMAN_CLAIM = "HUMAN_CLAIM"


#: Codes that can never be overridden by the owner.
HARD_BLOCK_CODES = frozenset(
    {ReasonCode.EMPTY_PART, ReasonCode.PART_TOO_LONG, ReasonCode.INVALID_TEXT}
)

_HOST_RE = r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.){1,10}[a-z]{2,24}"
_HOST_ONLY_RE = re.compile(_HOST_RE)
_CLEAN_URL_RE = re.compile(
    rf"(?:https?://)?(?P<host>{_HOST_RE})(?::[0-9]{{1,5}})?"
    r"(?P<path>/[a-z0-9._~/-]{0,2000})?(?:\?(?P<query>[a-z0-9._~=&-]{0,2000}))?",
    re.IGNORECASE,
)
_DOMAIN_IN_QUERY_RE = re.compile(r"[a-z0-9-]+\.[a-z]{2,}", re.IGNORECASE)
_TRAILING_PUNCT = ".,;:!?)]}»\"'…"
_SENTENCE_END = ".!?\n"
# A part longer than this many times the size limit is only checked for size, invisible and
# invalid characters: it is a hard, non-overridable PART_TOO_LONG in any case.
_SCAN_LIMIT_FACTOR = 4


# ---------------------------------------------------------------------------------------------
# Size
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PartSize:
    """Size of a part in the units Avito might count. Computed without encoding, so lone
    surrogates do not raise (they count as 1 UTF-16 unit and 3 UTF-8 bytes)."""

    code_points: int
    utf16_units: int
    utf8_bytes: int


def _utf16(ch: str) -> int:
    return 2 if ord(ch) > 0xFFFF else 1


def _utf8(ch: str) -> int:
    cp = ord(ch)
    return 1 if cp < 0x80 else 2 if cp < 0x800 else 3 if cp < 0x10000 else 4


def measure_part(text: str) -> PartSize:
    """Measure one part; the splitter must use the same function as the filter (D-k)."""
    return PartSize(
        code_points=len(text),
        utf16_units=sum(_utf16(ch) for ch in text),
        utf8_bytes=sum(_utf8(ch) for ch in text),
    )


@dataclass(frozen=True, slots=True)
class FilterConfig:
    """Versioned filter configuration.

    ``url_allowlist`` holds host names; a URL passes when its host equals an entry or is a
    subdomain of it (``www.avito.ru`` matches ``avito.ru``) and the URL is clean. Empty by
    default. Entries must be plain host names (``ValueError`` otherwise).
    """

    url_allowlist: tuple[str, ...] = ()
    max_utf16_units: int = 1000
    max_utf8_bytes: int = 1000

    def __post_init__(self) -> None:
        entries: object = self.url_allowlist  # guard against a bare string at runtime
        if isinstance(entries, str):
            raise TypeError("url_allowlist must be a tuple of host names, not a string")
        cleaned = tuple(str(entry).strip().lower() for entry in self.url_allowlist)
        for entry in cleaned:
            if not _HOST_ONLY_RE.fullmatch(entry):
                raise ValueError(f"url_allowlist entry is not a plain host name: {entry!r}")
        object.__setattr__(self, "url_allowlist", cleaned)
        if self.max_utf16_units < 1 or self.max_utf8_bytes < 1:
            raise ValueError("part size limits must be positive")


def part_fits(text: str, config: FilterConfig | None = None) -> bool:
    """True when ``text`` is within both part size limits."""
    cfg = config if config is not None else FilterConfig()
    size = measure_part(text)
    return size.utf16_units <= cfg.max_utf16_units and size.utf8_bytes <= cfg.max_utf8_bytes


def _first_index_beyond(text: str, cfg: FilterConfig) -> int:
    units = 0
    size = 0
    for index, ch in enumerate(text):
        units += _utf16(ch)
        size += _utf8(ch)
        if units > cfg.max_utf16_units or size > cfg.max_utf8_bytes:
            return index
    return len(text)


# ---------------------------------------------------------------------------------------------
# Context and results
# ---------------------------------------------------------------------------------------------

_Span = tuple[int, int]


@dataclass(frozen=True, slots=True)
class FilterContext:
    """Per-draft context. Every flag defaults to the strict value. See the module docstring
    for the ``template_spans`` and ``is_owner_edit`` contracts."""

    automation_mode: AutomationMode = AutomationMode.DRAFT_ONLY
    is_owner_edit: bool = False
    #: Per part: (start, end) offsets of code-owned constant template text in the final part.
    template_spans: tuple[tuple[_Span, ...], ...] = ()
    #: The related hold/order record is ``confirmed_by_owner``.
    completion_confirmed: bool = False
    #: ``payment_status=confirmed``.
    payment_confirmed: bool = False
    #: Every product this text is about has a ``verified`` fitment fact.
    fitment_verified: bool = False


@dataclass(frozen=True, slots=True)
class Finding:
    """One rule hit; ``start``/``end`` are offsets into the part. The matched value is not kept."""

    code: ReasonCode
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class PartVerdict:
    """Verdict for one part. ``allowed`` is false whenever there is a finding (fail-closed);
    ``overridable`` is true only for an owner edit without hard-block codes."""

    index: int
    allowed: bool
    findings: tuple[Finding, ...]
    overridable: bool = False

    @property
    def codes(self) -> tuple[ReasonCode, ...]:
        """Distinct reason codes in order of first appearance."""
        return tuple(dict.fromkeys(f.code for f in self.findings))


@dataclass(frozen=True, slots=True)
class FilterResult:
    """Verdicts for all parts of one draft."""

    parts: tuple[PartVerdict, ...]
    warn_only: bool
    rules_version: str = RULES_VERSION

    @property
    def allowed(self) -> bool:
        """True when every part may be sent without an override."""
        return all(part.allowed for part in self.parts)

    @property
    def reason_codes(self) -> tuple[ReasonCode, ...]:
        """Distinct reason codes over all parts, in order of first appearance."""
        return tuple(dict.fromkeys(code for part in self.parts for code in part.codes))

    @property
    def overridable(self) -> bool:
        """Owner edit that is denied, but every denied part may be sent with an audited owner
        override token."""
        return (
            self.warn_only
            and not self.allowed
            and all(part.allowed or part.overridable for part in self.parts)
        )


# ---------------------------------------------------------------------------------------------
# Helpers (normalized coordinates unless noted)
# ---------------------------------------------------------------------------------------------

_MASKER_CODES: dict[PiiType, ReasonCode] = {
    PiiType.PHONE: ReasonCode.CONTACT_PHONE,
    PiiType.EMAIL: ReasonCode.CONTACT_EMAIL,
    PiiType.SOCIAL: ReasonCode.CONTACT_SOCIAL,
    PiiType.URL: ReasonCode.URL_NOT_ALLOWED,
    PiiType.CARD: ReasonCode.PAYMENT_CARD,
}
# Masker types that may be exempt when they lie inside an allowed literal (OEM look-alikes).
_LITERAL_EXEMPT_TYPES = frozenset({PiiType.PHONE, PiiType.CARD})

_ALWAYS_PATTERNS: tuple[tuple[ReasonCode, re.Pattern[str]], ...] = (
    (ReasonCode.UNRENDERED_TOKEN, fp.UNRENDERED_TOKEN_RE),
    (ReasonCode.CONTACT_CHANNEL, fp.CONTACT_CHANNEL_RE),
    (ReasonCode.CONTACT_EMAIL, fp.EMAIL_OBFUSCATED_RE),
    (ReasonCode.PAYMENT_OFF_PLATFORM, fp.PAYMENT_OFF_PLATFORM_RE),
    (ReasonCode.PAYMENT_TERMS_UNCONFIRMED, fp.PAYMENT_TERMS_RE),
    (ReasonCode.HUMAN_CLAIM, fp.HUMAN_CLAIM_RE),
    (ReasonCode.HUMAN_CLAIM, fp.HUMAN_CLAIM_CASED_RE),
)
_PROMISE_PATTERNS: tuple[tuple[ReasonCode, re.Pattern[str]], ...] = (
    (ReasonCode.PROMISE_DISCOUNT, fp.DISCOUNT_RE),
    (ReasonCode.PROMISE_RETURN, fp.RETURN_RE),
    (ReasonCode.PROMISE_WARRANTY, fp.WARRANTY_RE),
    (ReasonCode.PROMISE_DELIVERY_DATE, fp.DELIVERY_DATE_RE),
)


def _matches(nt: NormalizedText, pattern: re.Pattern[str]) -> list[_Span]:
    """Non-empty matches on the Cyrillic-folded and the Latin-folded view, deduplicated."""
    spans: set[_Span] = set()
    for view in (nt.cyr,) if nt.lat == nt.cyr else (nt.cyr, nt.lat):
        for match in pattern.finditer(view):
            if match.end() > match.start():
                spans.add(match.span())
    return sorted(spans)


def _inside(span: _Span, regions: Iterable[_Span]) -> bool:
    start, end = span
    return any(r_start <= start and end <= r_end for r_start, r_end in regions)


def _trim(text: str, start: int, end: int) -> int:
    while end > start and text[end - 1] in _TRAILING_PUNCT:
        end -= 1
    return end


def _literal_pattern(literal: str) -> re.Pattern[str] | None:
    folded = normalize(literal).lat.strip().rstrip(_TRAILING_PUNCT)
    pieces = folded.split()
    if not pieces or not any(ch.isalnum() for ch in folded):
        return None
    body = r"\s+".join(re.escape(piece) for piece in pieces)
    first, last = pieces[0][0], pieces[-1][-1]
    left = r"(?<![^\W_])" if first.isalnum() else ""
    right = r"(?!\d)" if last.isdigit() else r"(?![^\W_])" if last.isalnum() else ""
    return re.compile(left + body + right, re.IGNORECASE)


def _url_allowed(url: str, allowlist: tuple[str, ...]) -> bool:
    """Strict check (D-d): the whole URL must be a clean http(s) URL on an allowlisted host."""
    if not allowlist:
        return False
    match = _CLEAN_URL_RE.fullmatch(url)
    if match is None:
        return False
    path = match.group("path") or ""
    query = match.group("query") or ""
    if "//" in path or _DOMAIN_IN_QUERY_RE.search(query):
        return False
    host = match.group("host").lower()
    return any(host == entry or host.endswith("." + entry) for entry in allowlist)


def _negated(nt: NormalizedText, span: _Span) -> bool:
    start, end = span
    before = nt.cyr[max(0, start - 60) : start]
    after = nt.cyr[end : end + 80]
    return bool(fp.NEGATION_BEFORE_RE.search(before) or fp.NEGATION_AFTER_RE.search(after))


def _sentence(view: str, span: _Span) -> str:
    start, end = span
    left = max(view.rfind(ch, 0, start) for ch in _SENTENCE_END) + 1
    rights = [i for i in (view.find(ch, end) for ch in _SENTENCE_END) if i != -1]
    right = min(rights) + 1 if rights else len(view)
    return view[left:right]


def _hedged(nt: NormalizedText, span: _Span) -> bool:
    return any(fp.FITMENT_HEDGE_RE.search(_sentence(view, span)) for view in (nt.cyr, nt.lat))


# ---------------------------------------------------------------------------------------------
# Per-part check
# ---------------------------------------------------------------------------------------------


def _check_part(
    text: str,
    literals: tuple[re.Pattern[str], ...],
    template_spans: tuple[_Span, ...],
    context: FilterContext,
    config: FilterConfig,
) -> list[Finding]:
    nt = normalize(text)
    # Findings already in original coordinates.
    original: list[Finding] = [Finding(ReasonCode.INVALID_TEXT, s, e) for s, e in nt.invalid]
    original += [Finding(ReasonCode.OBFUSCATION, s, e) for s, e in nt.hidden]
    if not nt.text.strip():
        original.append(Finding(ReasonCode.EMPTY_PART, 0, len(text)))
        return sorted(set(original), key=lambda f: (f.start, f.end, f.code.value))
    if not part_fits(text, config):
        original.append(
            Finding(ReasonCode.PART_TOO_LONG, _first_index_beyond(text, config), len(text))
        )
        if len(text) > _SCAN_LIMIT_FACTOR * max(config.max_utf16_units, config.max_utf8_bytes):
            # Hard-blocked anyway; do not spend time scanning a huge input.
            return sorted(set(original), key=lambda f: (f.start, f.end, f.code.value))

    # Findings in normalized coordinates, mapped at the end.
    found: list[tuple[ReasonCode, int, int]] = []

    def add(code: ReasonCode, span: _Span) -> None:
        found.append((code, span[0], span[1]))

    for span in mixed_script_spans(nt.text) + spaced_letter_spans(nt.text):
        add(ReasonCode.OBFUSCATION, span)

    literal_regions = [m.span() for p in literals for m in p.finditer(nt.lat)]
    template_regions = [nt.from_original(s, e) for s, e in template_spans]
    template_regions = [r for r in template_regions if r[1] > r[0]]
    code_regions = literal_regions + template_regions
    consumed: list[_Span] = []

    # Masker detectors (phones, e-mails, handles, links, cards).
    for pii_type, start, end in detect_normalized(nt):
        code = _MASKER_CODES.get(pii_type)
        if code is None:  # VIN and plate: their digits fall under the digit rule.
            continue
        span = (start, end)
        consumed.append(span)
        if pii_type in _LITERAL_EXEMPT_TYPES and _inside(span, literal_regions):
            continue
        if pii_type is PiiType.URL and _url_allowed(nt.text[start:end], config.url_allowlist):
            continue
        add(code, span)

    # URLs the masker does not know (any scheme, any TLD, obfuscated dots).
    for start, end in _matches(nt, fp.URL_GENERIC_RE):
        end = _trim(nt.text, start, end)
        if end <= start:
            continue
        consumed.append((start, end))
        if not _url_allowed(nt.text[start:end], config.url_allowlist):
            add(ReasonCode.URL_NOT_ALLOWED, (start, end))

    for span in _matches(nt, fp.AT_SIGN_RE):
        if not _inside(span, consumed):
            add(ReasonCode.CONTACT_SOCIAL, span)

    for code, pattern in _ALWAYS_PATTERNS:
        for span in _matches(nt, pattern):
            add(code, span)
            if code is ReasonCode.UNRENDERED_TOKEN:
                consumed.append(span)

    for span in _matches(nt, fp.CONTACT_REDIRECT_RE):
        if not _negated(nt, span):
            add(ReasonCode.CONTACT_REDIRECT, span)

    for code, pattern in _PROMISE_PATTERNS:
        for span in _matches(nt, pattern):
            if _inside(span, template_regions) or _negated(nt, span):
                continue
            if code is ReasonCode.PROMISE_RETURN and fp.PLATFORM_RULES_AFTER_RE.search(
                nt.cyr[span[1] : span[1] + 80]
            ):
                continue
            add(code, span)

    if not context.fitment_verified:
        for span in _matches(nt, fp.FITMENT_RE):
            before = nt.cyr[max(0, span[0] - 20) : span[0]]
            if fp.NEGATION_BEFORE_RE.search(before) or _hedged(nt, span):
                continue
            add(ReasonCode.UNVERIFIED_FITMENT, span)

    claims = (
        (ReasonCode.COMPLETION_CLAIM, fp.COMPLETION_RE, context.completion_confirmed),
        (ReasonCode.PAYMENT_RECEIVED_CLAIM, fp.PAYMENT_RECEIVED_RE, context.payment_confirmed),
    )
    for code, pattern, confirmed in claims:
        for span in _matches(nt, pattern):
            if confirmed and _inside(span, template_regions):
                continue
            if _negated(nt, span):
                continue
            add(code, span)

    for span in _matches(nt, fp.DIGITS_RE):
        if not _inside(span, code_regions) and not _inside(span, consumed):
            add(ReasonCode.DIGITS_NOT_ALLOWED, span)

    for start, end in _matches(nt, fp.CURRENCY_RE):
        # "руб." -> "руб": literals are matched without their trailing punctuation.
        span = (start, _trim(nt.text, start, end) if end - start > 1 else end)
        if not _inside(span, code_regions) and not _inside(span, consumed):
            add(ReasonCode.CURRENCY, span)

    for span in _matches(nt, fp.NUMBER_WORD_RE):
        if nt.text[span[0] : span[1]] in fp.NUMBER_WORD_SKIP_EXACT:
            continue
        if not _inside(span, code_regions) and not _inside(span, consumed):
            add(ReasonCode.NUMBER_WORD, span)

    for code, start, end in found:
        o_start, o_end = nt.to_original(start, end)
        original.append(Finding(code, o_start, o_end))
    return sorted(set(original), key=lambda f: (f.start, f.end, f.code.value))


# ---------------------------------------------------------------------------------------------
# Input validation (D-e)
# ---------------------------------------------------------------------------------------------


def _str_sequence(value: object, name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be a sequence of strings, not a single string")
    if not isinstance(value, Iterable):
        raise TypeError(f"{name} must be a sequence of strings")
    items = tuple(value)
    for item in items:
        if not isinstance(item, str):
            raise TypeError(f"{name} must contain only strings, got {type(item).__name__}")
    return items


def _validated_spans(spans: object, parts: tuple[str, ...]) -> tuple[tuple[_Span, ...], ...]:
    if isinstance(spans, (str, bytes)) or not isinstance(spans, Iterable):
        raise TypeError("template_spans must be a sequence (one entry per part)")
    per_part = tuple(spans)
    if len(per_part) > len(parts):
        raise ValueError("template_spans has more entries than there are parts")
    result: list[tuple[_Span, ...]] = []
    for index, entry in enumerate(per_part):
        if isinstance(entry, (str, bytes)) or not isinstance(entry, Iterable):
            raise TypeError("each template_spans entry must be a sequence of (start, end)")
        checked: list[_Span] = []
        for span in entry:
            if (
                not isinstance(span, tuple)
                or len(span) != 2
                or not all(isinstance(v, int) and not isinstance(v, bool) for v in span)
            ):
                raise TypeError("a template span must be a (start, end) tuple of ints")
            start, end = span
            if not 0 <= start < end <= len(parts[index]):
                raise ValueError(f"template span {span} is out of range for part {index}")
            checked.append((start, end))
        result.append(tuple(checked))
    return tuple(result)


# ---------------------------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------------------------


def check_parts(
    parts: Sequence[str],
    *,
    allowed_literals: Iterable[str] = (),
    context: FilterContext | None = None,
    config: FilterConfig | None = None,
) -> FilterResult:
    """Check the final rendered parts of one outgoing message.

    Pure and deterministic: the same arguments always give the same result; nothing is logged,
    stored or sent. Raises ``TypeError``/``ValueError`` for malformed input (never for odd text:
    lone surrogates and control characters become ``INVALID_TEXT``).
    """
    texts = _str_sequence(parts, "parts")
    literal_values = _str_sequence(allowed_literals, "allowed_literals")
    ctx = context if context is not None else FilterContext()
    cfg = config if config is not None else FilterConfig()
    spans = _validated_spans(ctx.template_spans, texts)

    literals = tuple(
        p for p in (_literal_pattern(v) for v in dict.fromkeys(literal_values)) if p is not None
    )

    verdicts: list[PartVerdict] = []
    for index, text in enumerate(texts):
        part_spans = spans[index] if index < len(spans) else ()
        findings = _check_part(text, literals, part_spans, ctx, cfg)
        hard = any(f.code in HARD_BLOCK_CODES for f in findings)
        verdicts.append(
            PartVerdict(
                index=index,
                allowed=not findings,
                findings=tuple(findings),
                overridable=ctx.is_owner_edit and bool(findings) and not hard,
            )
        )
    return FilterResult(parts=tuple(verdicts), warn_only=ctx.is_owner_edit)

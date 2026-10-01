"""Output filter (docs/ARCHITECTURE.md §7.2): a pure, deterministic check of outgoing text.

``check_parts(parts, allowed_literals=..., context=..., config=...)`` receives the final message
parts exactly as they would be sent (placeholders already rendered, text already split) and
returns one verdict per part: allowed or denied, with machine-readable reason codes and spans
(offsets into that part). It never changes the text, never logs and keeps no matched values:
the caller already holds the text and can slice it with the spans.

All matching runs on the shared normalization layer (``app.safety.normalize``): NFKC,
invisible characters removed, look-alike letters folded; spans are mapped back to the part.
Patterns are script-tagged (``app.safety.filter_patterns``, T-041 / Y-7).

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

  - ``template_spans`` (**contract, D-f / Y-8**): per part, ``TemplateSpan(kind, start, end)``
    for each piece of code-owned, constant template text in that final part. Supplied by the
    renderer (T-023). Interpolated untrusted values (listing titles, customer text, LLM text)
    must never lie inside a span: the renderer splits a template around them. Text that merely
    repeats template wording gets no exemption. What a span exempts depends on its kind (table
    below).
  - ``is_owner_edit`` (**contract, D-g**): set only by code, and only for text that comes from
    the owner's admin-UI edit. Never derive it from message content.
  - ``completion_confirmed`` / ``payment_confirmed`` / ``fitment_verified``: record flags.
  - ``automation_mode`` does not relax any rule; it is carried for the audit trail only.
- ``config`` (``FilterConfig``): URL host allowlist (empty by default: every URL is denied) and
  the part size limits.

Exemption table (Y-8)
---------------------
A finding is exempt only when it lies entirely inside one template span of a listed kind (and,
for claims, the flag is set). Every other code is NEVER exempt in any span, in particular
``PAYMENT_CARD``, ``CONTACT_PHONE`` and all ``CONTACT_*`` codes.

=============================  ===============================================================
Code                           Exempt inside span kinds
=============================  ===============================================================
PAYMENT_OFF_PLATFORM           rule_payment
PAYMENT_TERMS_OUTSIDE_RULE     rule_payment
DIGITS_NOT_ALLOWED             rule_payment, rule_generic, offer, confirmation
NUMBER_WORD                    rule_generic, offer, confirmation; "%" also in rule_payment
CURRENCY                       rule_generic, offer, confirmation
PROMISE_* (4 codes)            rule_generic
COMPLETION_CLAIM               confirmation, and only with ``completion_confirmed``
PAYMENT_RECEIVED_CLAIM         confirmation, and only with ``payment_confirmed``
=============================  ===============================================================

``bot_disclosure`` and ``wait_message`` spans exempt nothing; they are recorded for the audit.
The owner's payment rule text belongs in a ``rule_payment`` span, e.g. "Оплата: наличными при
получении, по QR-коду (СБП), переводом на карту; для юрлиц — безналичный расчёт по счёту
(+10%)." (it must not say "по номеру телефона": contact wording is never exempt).

Reason codes
------------
Hard block (never overridable, also in owner-edit mode): ``EMPTY_PART``, ``PART_TOO_LONG``,
``INVALID_TEXT``, ``PAYMENT_CARD``, ``CONTACT_PHONE`` (Y-9: the assistant system never sends a
card or phone number; the owner can still write in Avito directly).

- ``EMPTY_PART``: nothing visible is left after removing invisible characters.
- ``PART_TOO_LONG``: more than ``max_utf16_units`` UTF-16 code units OR more than
  ``max_utf8_bytes`` UTF-8 bytes (both 1000 by default, D-k; Avito's counting unit is not
  verified). The span starts at the first character beyond a limit. ``measure_part()`` gives
  the same numbers to the splitter. A part longer than four times the limit is checked only
  for size, invisible and invalid characters (it cannot be sent in any case).
- ``INVALID_TEXT``: lone surrogates or control characters (other than tab/newline/CR).
- ``OBFUSCATION``: an invisible/format/unassigned/private-use character or U+FFFC; a letter
  outside the allowed sets (ASCII, Latin-1, Turkish, Russian Cyrillic + ё: Y-3); a word mixing
  Latin and Cyrillic (a Latin brand plus a Russian case ending such as "Mercedesа" passes); a
  word spelled letter by letter (Y-4); a high-risk stem split across words ("Позв оните",
  "бес платно": also reported with the stem's own code). Emoji ZWJ sequences contain a Cf
  character and are denied (decision).
- ``UNRENDERED_TOKEN``: a ``{{placeholder}}`` left unrendered or a masker token (``[PHONE_1]``).
- ``CONTACT_PHONE``: phone number (masker detector). Exempt only when the whole number lies
  inside an ``allowed_literals`` occurrence (an OEM number the masker reads as a phone).
- ``CONTACT_EMAIL``: e-mail address (masker detector) or a spelled-out one.
- ``CONTACT_SOCIAL``: messenger/social link, ``@handle`` or keyword handle, or any ``@`` sign.
- ``CONTACT_CHANNEL``: an off-platform channel is named (WhatsApp, Telegram, ВК, MAX, …).
- ``CONTACT_REDIRECT``: a request for, or a redirect to, off-platform contact ("позвоните",
  "дайте номер", "напишите в <channel>", "напрямую", "без Авито", "наш сайт", "call me").
  "Пишите в чат Авито / в любое время / в рабочее время" passes.
- ``URL_NOT_ALLOWED``: a URL, any ``scheme://``, ``//host``, ``label.tld`` with any Latin TLD,
  a Cyrillic TLD after a label of two or more letters ("г.Москва" passes), or a domain with an
  obfuscated dot, whose host is not on ``FilterConfig.url_allowlist``. An allowlisted URL must
  also be clean: strict host syntax, no ``//`` in the path, no domain in the query, no run of
  five or more digits and no channel name in the path or query (Y-10).
- ``PAYMENT_CARD``: a payment card number (masker detector, Luhn-checked); never exempt, not
  even as an allowed literal (Y-9).
- ``PAYMENT_OFF_PLATFORM``: an off-platform payment offer ("переведите на карту", "предоплата",
  СБП, QR, bank names, "аванс", crypto, "без безопасной сделки").
- ``PAYMENT_TERMS_OUTSIDE_RULE``: payment-method wording (cash, "при встрече", card on
  receipt) outside a ``rule_payment`` span (Y-8).
- ``DIGITS_NOT_ALLOWED``: a run of digits (after NFKC). Digits inside a reported contact, card,
  URL or token span are not reported again.
- ``CURRENCY``: currency symbol or word (₽, руб, коп., $, евро, USD, "500р", "т.р.", "тыр").
- ``NUMBER_WORD``: a number written as a word or money slang ("пятьсот", "две", "полторы",
  "косарь", "чирик", "лям", "процент", "%"), best effort. Small numbers ("две фары") stay
  denied for the pilot; the cost of that is measured there (label 2).
- ``PROMISE_DISCOUNT`` / ``PROMISE_RETURN`` / ``PROMISE_WARRANTY`` /
  ``PROMISE_DELIVERY_DATE``: discount/bargaining/free-of-charge, return/refund/exchange,
  warranty/guarantee/inspection period, a concrete delivery time.
- ``UNVERIFIED_FITMENT``: an affirmative fitment claim ("подойдёт", "подходит", "встанет",
  "совместима"), D-c, also as a product-attribute claim without a fact ("подходит для обеих
  сторон", label 3). Allowed when ``context.fitment_verified`` is true, when negated ("не
  подойдёт": allowed by design, the only risk is a lost sale, label 7), or in a sentence that
  is a question (ли, "?") or announces a FUTURE verification (проверим/уточним/проверю/уточню/
  подтвердит продавец) (Y-1). Past tense ("проверено"), "если"/"если что" and negated hedges
  do not count.
- ``COMPLETION_CLAIM`` / ``PAYMENT_RECEIVED_CLAIM``: "заказ оформлен", "держу для вас",
  "отправил", "в пути" / "оплата получена", "спасибо за оплату".
- ``HUMAN_CLAIM``: the text claims to be a human or a named person, or denies being a bot
  ("я менеджер", "на связи Иван", "Иван на связи", "С уважением, Иван", "Ivan here", "я не
  бот", "Робот? Нет."). The honest disclosure ("я автоматический помощник продавца, не
  человек", "я продавец-бот", "С уважением, помощник продавца") passes. Signatures in style
  examples are stripped at ingestion (T-028); the filter is only the backstop.

Negation and platform rules (Y-2)
---------------------------------
Promises, completion claims and contact redirects pass when negated right before ("не делаем
скидок", "ещё не оформлен") or right after ("Гарантии от продавца нет", "Торг не уместен").
"нет проблем/вопросов" is not a negation, and a clause with two negation tokens cancels the
exception ("Не уступить вам просто нельзя!"). "Возврат по правилам Авито" passes only when "по
правилам Авито" directly follows the promise word (only whitespace/punctuation in between).

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
  literal is ignored. A literal edge may not touch a letter or digit on the left; on the right a
  digit edge may not touch a digit and a letter edge may not touch a letter or digit. Literals
  without any letter or digit are ignored.
- A finding is exempt only when it lies entirely inside one literal occurrence / template span.

Known limitations (tested as strict xfail)
------------------------------------------
- Number words are a stem list: typos ("пятсот"), "штука"/"один", Roman numerals and Turkish
  "bir/on/yüz/bin/altı" are NOT detected.
- An allowed literal is not tied to its meaning (a year literal reused as a price passes).
- Reversed text, bare "за вами" and condition statements ("проверено, рабочее") pass.
- Phrase patterns are best effort; missed cases must become new patterns plus eval scenarios.
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.config import AutomationMode
from app.safety import filter_patterns as fp
from app.safety.masker import PiiType, detect_normalized
from app.safety.normalize import (
    NormalizedText,
    compact,
    foreign_letter_spans,
    mixed_script_spans,
    normalize,
    spaced_letter_spans,
)

__all__ = [
    "EXEMPT_IN",
    "HARD_BLOCK_CODES",
    "RULES_VERSION",
    "FilterConfig",
    "FilterContext",
    "FilterResult",
    "Finding",
    "PartSize",
    "PartVerdict",
    "ReasonCode",
    "SpanKind",
    "TemplateSpan",
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
    PAYMENT_TERMS_OUTSIDE_RULE = "PAYMENT_TERMS_OUTSIDE_RULE"
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


#: Codes that can never be overridden by the owner (Y-9 added card and phone).
HARD_BLOCK_CODES = frozenset(
    {
        ReasonCode.EMPTY_PART,
        ReasonCode.PART_TOO_LONG,
        ReasonCode.INVALID_TEXT,
        ReasonCode.PAYMENT_CARD,
        ReasonCode.CONTACT_PHONE,
    }
)


class SpanKind(StrEnum):
    """Kind of a code-owned template span (Y-8)."""

    RULE_PAYMENT = "rule_payment"
    RULE_GENERIC = "rule_generic"
    OFFER = "offer"
    CONFIRMATION = "confirmation"
    BOT_DISCLOSURE = "bot_disclosure"
    WAIT_MESSAGE = "wait_message"


@dataclass(frozen=True, slots=True)
class TemplateSpan:
    """A code-owned constant template region of a final part (offsets into that part)."""

    kind: SpanKind
    start: int
    end: int


_K = SpanKind
#: Per-code exemption table (see the module docstring). Codes not listed are never exempt.
EXEMPT_IN: dict[ReasonCode, frozenset[SpanKind]] = {
    ReasonCode.PAYMENT_OFF_PLATFORM: frozenset({_K.RULE_PAYMENT}),
    ReasonCode.PAYMENT_TERMS_OUTSIDE_RULE: frozenset({_K.RULE_PAYMENT}),
    ReasonCode.DIGITS_NOT_ALLOWED: frozenset(
        {_K.RULE_PAYMENT, _K.RULE_GENERIC, _K.OFFER, _K.CONFIRMATION}
    ),
    ReasonCode.NUMBER_WORD: frozenset({_K.RULE_GENERIC, _K.OFFER, _K.CONFIRMATION}),
    ReasonCode.CURRENCY: frozenset({_K.RULE_GENERIC, _K.OFFER, _K.CONFIRMATION}),
    ReasonCode.PROMISE_DISCOUNT: frozenset({_K.RULE_GENERIC}),
    ReasonCode.PROMISE_RETURN: frozenset({_K.RULE_GENERIC}),
    ReasonCode.PROMISE_WARRANTY: frozenset({_K.RULE_GENERIC}),
    ReasonCode.PROMISE_DELIVERY_DATE: frozenset({_K.RULE_GENERIC}),
    ReasonCode.COMPLETION_CLAIM: frozenset({_K.CONFIRMATION}),
    ReasonCode.PAYMENT_RECEIVED_CLAIM: frozenset({_K.CONFIRMATION}),
}

_HOST_RE = r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.){1,10}[a-z]{2,24}"
_HOST_ONLY_RE = re.compile(_HOST_RE)
_CLEAN_URL_RE = re.compile(
    rf"(?:https?://)?(?P<host>{_HOST_RE})(?::[0-9]{{1,5}})?"
    r"(?P<path>/[a-z0-9._~/-]{0,2000})?(?:\?(?P<query>[a-z0-9._~=&-]{0,2000}))?",
    re.IGNORECASE,
)
_DOMAIN_IN_QUERY_RE = re.compile(r"[a-z0-9-]+\.[a-z]{2,}", re.IGNORECASE)
_LONG_DIGITS_RE = re.compile(r"[0-9]{5,}")
_URL_WORD_SPLIT_RE = re.compile(r"[-_/.?=&~]+")
_TRAILING_PUNCT = ".,;:!?)]}»\"'…"
_SENTENCE_END = frozenset(".!?\n")
_CLAUSE_END = frozenset(".!?\n;,—–")
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
    #: Per part: the typed code-owned template spans of that final part.
    template_spans: tuple[tuple[TemplateSpan, ...], ...] = ()
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

_ALWAYS_PATTERNS: tuple[tuple[ReasonCode, fp.ScriptPattern], ...] = (
    (ReasonCode.UNRENDERED_TOKEN, fp.UNRENDERED_TOKEN_RE),
    (ReasonCode.CONTACT_CHANNEL, fp.CONTACT_CHANNEL_RE),
    (ReasonCode.CONTACT_EMAIL, fp.EMAIL_OBFUSCATED_RE),
    (ReasonCode.PAYMENT_OFF_PLATFORM, fp.PAYMENT_OFF_PLATFORM_RE),
    (ReasonCode.PAYMENT_TERMS_OUTSIDE_RULE, fp.PAYMENT_TERMS_RE),
    (ReasonCode.HUMAN_CLAIM, fp.HUMAN_CLAIM_RE),
    (ReasonCode.HUMAN_CLAIM, fp.HUMAN_CLAIM_CASED_RE),
)
_PROMISE_PATTERNS: tuple[tuple[ReasonCode, fp.ScriptPattern], ...] = (
    (ReasonCode.PROMISE_DISCOUNT, fp.DISCOUNT_RE),
    (ReasonCode.PROMISE_RETURN, fp.RETURN_RE),
    (ReasonCode.PROMISE_WARRANTY, fp.WARRANTY_RE),
    (ReasonCode.PROMISE_DELIVERY_DATE, fp.DELIVERY_DATE_RE),
)
_CYRILLIC_RE = re.compile(r"[а-яё]", re.IGNORECASE)


def _matches(nt: NormalizedText, pattern: fp.ScriptPattern) -> list[_Span]:
    return sorted(set(pattern.spans(nt.cyr, nt.lat, nt.text)))


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
    """Strict check (D-d, Y-10): the whole URL must be a clean http(s) URL on an allowlisted
    host, without five or more digits in a row and without a channel name in path or query."""
    if not allowlist:
        return False
    match = _CLEAN_URL_RE.fullmatch(url)
    if match is None:
        return False
    path = match.group("path") or ""
    query = match.group("query") or ""
    if "//" in path or _DOMAIN_IN_QUERY_RE.search(query):
        return False
    if _LONG_DIGITS_RE.search(path + query):
        return False
    words = _URL_WORD_SPLIT_RE.sub(" ", f"{path} {query}")
    if any(fp.CONTACT_CHANNEL_RE.spans(words, words, words)):
        return False
    host = match.group("host").lower()
    return any(host == entry or host.endswith("." + entry) for entry in allowlist)


class _Segments:
    """Sentence or clause bounds of one view, computed once (Y-12)."""

    def __init__(self, view: str, ends: frozenset[str]) -> None:
        self._view = view
        self._ends = [i for i, ch in enumerate(view) if ch in ends]

    def bounds(self, span: _Span) -> _Span:
        """Bounds of the segment containing ``span``, including its terminating character."""
        start, end = span
        i = bisect.bisect_left(self._ends, start)
        left = self._ends[i - 1] + 1 if i > 0 else 0
        j = bisect.bisect_left(self._ends, end)
        right = self._ends[j] + 1 if j < len(self._ends) else len(self._view)
        return left, right

    def around(self, span: _Span) -> str:
        """The segment containing ``span``, including its terminating character."""
        left, right = self.bounds(span)
        return self._view[left:right]


@dataclass(slots=True)
class _Context:
    nt: NormalizedText
    sentences_cyr: _Segments
    clauses: _Segments
    hedge_cache: dict[_Span, bool] = field(default_factory=dict)


def _negated(ctx: _Context, span: _Span) -> bool:
    """Negated right before or after, unless the clause holds a double negation (Y-2)."""
    start, end = span
    cyr = ctx.nt.cyr
    before = cyr[max(0, start - 60) : start]
    after = cyr[end : end + 80]
    if not (fp.NEGATION_BEFORE_RE.search(before) or fp.NEGATION_AFTER_RE.search(after)):
        return False
    return len(fp.NEGATION_TOKEN_RE.findall(ctx.clauses.around(span))) < 2


def _hedged(ctx: _Context, span: _Span) -> bool:
    # One regex search per sentence, not per match (Y-12: fitment-dense parts stay linear).
    bounds = ctx.sentences_cyr.bounds(span)
    cached = ctx.hedge_cache.get(bounds)
    if cached is None:
        left, right = bounds
        cached = bool(
            fp.FITMENT_HEDGE_RE.search(ctx.nt.cyr[left:right])
            or fp.FITMENT_HEDGE_RE.search(ctx.nt.lat[left:right])
        )
        ctx.hedge_cache[bounds] = cached
    return cached


def _typed_regions(
    nt: NormalizedText, spans: tuple[TemplateSpan, ...]
) -> dict[SpanKind, list[_Span]]:
    regions: dict[SpanKind, list[_Span]] = {}
    for span in spans:
        region = nt.from_original(span.start, span.end)
        if region[1] > region[0]:
            regions.setdefault(span.kind, []).append(region)
    return regions


def _exempt(
    code: ReasonCode, span: _Span, regions: dict[SpanKind, list[_Span]], nt: NormalizedText
) -> bool:
    kinds = set(EXEMPT_IN.get(code, frozenset()))
    if code is ReasonCode.NUMBER_WORD and nt.text[span[0] : span[1]] == "%":
        kinds.add(SpanKind.RULE_PAYMENT)
    return any(_inside(span, regions.get(kind, ())) for kind in kinds)


# ---------------------------------------------------------------------------------------------
# Per-part check
# ---------------------------------------------------------------------------------------------


def _check_part(
    text: str,
    literals: tuple[re.Pattern[str], ...],
    template_spans: tuple[TemplateSpan, ...],
    context: FilterContext,
    config: FilterConfig,
) -> list[Finding]:
    nt = normalize(text)
    # Findings already in original coordinates.
    original: list[Finding] = [Finding(ReasonCode.INVALID_TEXT, s, e) for s, e in nt.invalid]
    original += [Finding(ReasonCode.OBFUSCATION, s, e) for s, e in nt.hidden]

    def done() -> list[Finding]:
        return sorted(set(original), key=lambda f: (f.start, f.end, f.code.value))

    if not nt.text.strip():
        original.append(Finding(ReasonCode.EMPTY_PART, 0, len(text)))
        return done()
    if not part_fits(text, config):
        original.append(
            Finding(ReasonCode.PART_TOO_LONG, _first_index_beyond(text, config), len(text))
        )
        if len(text) > _SCAN_LIMIT_FACTOR * max(config.max_utf16_units, config.max_utf8_bytes):
            # Hard-blocked anyway; do not spend time scanning a huge input.
            return done()

    ctx = _Context(
        nt=nt,
        sentences_cyr=_Segments(nt.cyr, _SENTENCE_END),
        clauses=_Segments(nt.cyr, _CLAUSE_END),
    )
    regions = _typed_regions(nt, template_spans)
    # Findings in normalized coordinates, mapped at the end.
    found: list[tuple[ReasonCode, int, int]] = []

    def add(code: ReasonCode, span: _Span) -> None:
        if not _exempt(code, span, regions, nt):
            found.append((code, span[0], span[1]))

    for span in (
        foreign_letter_spans(nt.text) + mixed_script_spans(nt.text) + spaced_letter_spans(nt.text)
    ):
        add(ReasonCode.OBFUSCATION, span)

    # High-risk stems split across words (Y-4): only when the match crosses a removed separator.
    compacted = {view: compact(view) for view in {nt.cyr, nt.lat}}
    for code_name, stem in fp.COMPACT_STEMS:
        view = nt.cyr if _CYRILLIC_RE.search(stem.pattern) else nt.lat
        joined, index = compacted[view]
        for match in stem.finditer(joined):
            a, b = match.span()
            start, end = index[a], index[b - 1] + 1
            if end - start > b - a:
                add(ReasonCode(code_name), (start, end))
                add(ReasonCode.OBFUSCATION, (start, end))

    literal_regions = [m.span() for p in literals for m in p.finditer(nt.lat)]
    consumed: list[_Span] = []

    # Masker detectors (phones, e-mails, handles, links, cards).
    for pii_type, start, end in detect_normalized(nt):
        code = _MASKER_CODES.get(pii_type)
        if code is None:  # VIN and plate: their digits fall under the digit rule.
            continue
        span = (start, end)
        consumed.append(span)
        if pii_type is PiiType.PHONE and _inside(span, literal_regions):
            continue  # an OEM number from the records that looks like a phone
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
        if not _negated(ctx, span):
            add(ReasonCode.CONTACT_REDIRECT, span)

    for code, pattern in _PROMISE_PATTERNS:
        for span in _matches(nt, pattern):
            if _negated(ctx, span):
                continue
            if code is ReasonCode.PROMISE_RETURN and fp.PLATFORM_RULES_AFTER_RE.search(
                nt.cyr[span[1] : span[1] + 80]
            ):
                continue
            add(code, span)

    if not context.fitment_verified:
        for span in _matches(nt, fp.FITMENT_RE):
            before = nt.cyr[max(0, span[0] - 20) : span[0]]
            if fp.NEGATION_BEFORE_RE.search(before) or _hedged(ctx, span):
                continue
            add(ReasonCode.UNVERIFIED_FITMENT, span)

    claims = (
        (ReasonCode.COMPLETION_CLAIM, fp.COMPLETION_RE, context.completion_confirmed),
        (ReasonCode.PAYMENT_RECEIVED_CLAIM, fp.PAYMENT_RECEIVED_RE, context.payment_confirmed),
    )
    for code, pattern, confirmed in claims:
        for span in _matches(nt, pattern):
            if _negated(ctx, span):
                continue
            if confirmed and _exempt(code, span, regions, nt):
                continue
            found.append((code, span[0], span[1]))  # never exempt without the flag

    for span in _matches(nt, fp.DIGITS_RE):
        if not _inside(span, literal_regions) and not _inside(span, consumed):
            add(ReasonCode.DIGITS_NOT_ALLOWED, span)

    for start, end in _matches(nt, fp.CURRENCY_RE):
        # "руб." -> "руб": literals are matched without their trailing punctuation.
        span = (start, _trim(nt.text, start, end) if end - start > 1 else end)
        if not _inside(span, literal_regions) and not _inside(span, consumed):
            add(ReasonCode.CURRENCY, span)

    for span in _matches(nt, fp.NUMBER_WORD_RE):
        if nt.text[span[0] : span[1]] in fp.NUMBER_WORD_SKIP_EXACT:
            continue
        if not _inside(span, literal_regions) and not _inside(span, consumed):
            add(ReasonCode.NUMBER_WORD, span)

    for code, start, end in found:
        o_start, o_end = nt.to_original(start, end)
        original.append(Finding(code, o_start, o_end))
    return done()


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


def _validated_spans(spans: object, parts: tuple[str, ...]) -> tuple[tuple[TemplateSpan, ...], ...]:
    if isinstance(spans, (str, bytes)) or not isinstance(spans, Iterable):
        raise TypeError("template_spans must be a sequence (one entry per part)")
    per_part = tuple(spans)
    if len(per_part) > len(parts):
        raise ValueError("template_spans has more entries than there are parts")
    result: list[tuple[TemplateSpan, ...]] = []
    for index, entry in enumerate(per_part):
        if isinstance(entry, (str, bytes)) or not isinstance(entry, Iterable):
            raise TypeError("each template_spans entry must be a sequence of TemplateSpan")
        checked: list[TemplateSpan] = []
        for span in entry:
            if not isinstance(span, TemplateSpan) or not isinstance(span.kind, SpanKind):
                raise TypeError("a template span must be a TemplateSpan with a SpanKind")
            start, end = span.start, span.end
            if not all(isinstance(v, int) and not isinstance(v, bool) for v in (start, end)):
                raise TypeError("template span offsets must be ints")
            if not 0 <= start < end <= len(parts[index]):
                raise ValueError(f"template span ({start}, {end}) is out of range for part {index}")
            checked.append(span)
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

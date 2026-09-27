"""Output filter (docs/ARCHITECTURE.md §7.2): a pure, deterministic check of outgoing text.

``check_parts(parts, allowed_literals=..., context=..., config=...)`` receives the final message
parts exactly as they would be sent (placeholders already rendered, text already split) and
returns one verdict per part: allowed or denied, with machine-readable reason codes and spans
(offsets into that part). It never changes the text, never logs and keeps no matched values:
the caller already holds the text and can slice it with the spans.

Inputs
------
- ``parts``: the rendered parts, each meant to be at most 1000 characters (Avito text limit).
- ``allowed_literals``: the fact sheet's ``allowed_literals`` (§3.1): price strings produced by
  code placeholders, OEM numbers, SKUs, body codes (``W213``), years, quantities. Digits, currency
  words/symbols and number words are allowed only inside an occurrence of one of these strings.
- ``context`` (``FilterContext``): automation mode, owner-edit flag, the exact texts rendered
  from code templates (``template_texts``: ``{{rule:…}}`` business-rule text, offer/confirmation
  blocks, the bot-disclosure template) and the confirmation flags that unlock completion,
  payment and fitment statements.
- ``config`` (``FilterConfig``): URL host allowlist (empty by default: every URL is denied; the
  architecture does not allowlist avito.ru links) and the part length limit.

Reason codes
------------
Rendering and size (hard block, also in owner-edit mode):

- ``EMPTY_PART``: the part is empty or whitespace only.
- ``PART_TOO_LONG``: longer than ``FilterConfig.max_part_units`` (1000) UTF-16 code units. The
  span starts at the first character beyond the limit.

Contacts and channels (never exempt, not even inside ``allowed_literals`` or templates, except
where noted):

- ``UNRENDERED_TOKEN``: a ``{{placeholder}}`` left unrendered or a masker token (``[PHONE_1]``).
- ``CONTACT_PHONE``: phone number (masker detector). Exempt only when the whole number lies
  inside an ``allowed_literals`` occurrence (e.g. an 11-digit OEM number the masker would read
  as a phone).
- ``CONTACT_EMAIL``: e-mail address (masker detector).
- ``CONTACT_SOCIAL``: messenger/social link or ``@handle`` (masker detector).
- ``CONTACT_CHANNEL``: an off-platform channel is named (WhatsApp, Telegram, ВК, e-mail, …).
- ``CONTACT_REDIRECT``: a request for, or redirect to, off-platform contact ("позвоните",
  "мой номер", "напишите на почту", "call me", "outside Avito").
- ``URL_NOT_ALLOWED``: a URL whose host is not on ``FilterConfig.url_allowlist``.

Payment:

- ``PAYMENT_CARD``: a payment card number (masker detector, Luhn-checked). Exempt only inside an
  ``allowed_literals`` occurrence, like ``CONTACT_PHONE``.
- ``PAYMENT_OFF_PLATFORM``: an off-platform payment offer ("переведите на карту", "предоплата",
  СБП, "реквизиты", bank names). Not exempt inside templates.

Numbers and money (exempt inside ``allowed_literals`` and ``template_texts`` occurrences):

- ``DIGITS_NOT_ALLOWED``: a run of digits. Digits inside a reported contact/card/URL/token span
  are not reported again.
- ``CURRENCY``: currency symbol or word (₽, руб, рублей, коп., $, евро, USD, "500р").
- ``NUMBER_WORD``: a number written as a word ("пятьсот", "две тысячи", "полторы", "тыс",
  "пол цены"), best effort.

Promises (exempt only inside ``template_texts``, i.e. business-rule text rendered by code):

- ``PROMISE_DISCOUNT``: discount or free-of-charge offer ("сделаю скидку", "бесплатно", "торг").
- ``PROMISE_RETURN``: return, refund or exchange ("вернём деньги", "возврат", "обмен").
- ``PROMISE_WARRANTY``: warranty or guarantee ("гарантия").
- ``PROMISE_DELIVERY_DATE``: a concrete delivery/dispatch time ("доставим завтра").
- ``UNVERIFIED_FITMENT``: certainty about fitment ("точно подойдёт"); allowed only when
  ``context.fitment_verified`` is true.

Completion claims (allowed only when the flag is set AND the claim lies inside a
``template_texts`` occurrence, per §7.2 "confirmed_by_owner … ve şablondan geliyorsa"):

- ``COMPLETION_CLAIM``: "заказ оформлен", "забронировал", "отложил для вас", "отправлен";
  flag ``context.completion_confirmed``.
- ``PAYMENT_RECEIVED_CLAIM``: "оплата получена", "деньги пришли"; flag
  ``context.payment_confirmed``.

Honesty:

- ``HUMAN_CLAIM``: the text claims to be a human or denies being a bot ("я живой человек",
  "я не бот", "с вами общается менеджер", "I'm a real person"). The honest disclosure template
  ("я автоматический помощник продавца, не человек") passes.

Modes
-----
- Normal (``is_owner_edit=False``): a part with any finding is denied (``allowed=False``).
- Owner edit (``is_owner_edit=True``, §7.2 / §6.6): warn mode. The same findings are returned but
  the part stays allowed, except for the hard-block codes ``EMPTY_PART`` and ``PART_TOO_LONG``
  (Avito cannot send such a part at all). ``FilterResult.needs_owner_confirmation`` is true when
  anything was found, so the UI asks for an explicit "send anyway" (and audits it).
- ``automation_mode`` does not relax any rule; it is carried for the audit trail only.

Matching rules
--------------
- ``allowed_literals`` and ``template_texts`` match case-insensitively; any whitespace run in them
  matches any whitespace run in the text (so a normal space matches a non-breaking space). An
  edge character that is a digit may not touch another digit, a letter edge may not touch
  another letter or digit: ``2018`` does not cover ``20185`` and ``W213`` does not cover
  ``W2130``. Literals without any letter or digit (e.g. a bare ``₽``) are ignored.
- The whole finding must lie inside one literal/template occurrence to be exempt.

Known limitations (tested as strict xfail)
------------------------------------------
- Number words are a stem list: typos, slang ("пятихатка"), Turkish "bir/on/yüz/bin/altı" and
  "один/одна/одно" (too common in ordinary text) are NOT detected.
- An OEM number written in a different format than its ``allowed_literals`` entry
  (``A 213 885 14 00`` vs ``A2138851400``) is denied: literals must match as written.
- Look-alike letters (Cyrillic "а" inside "WhatsApp") and zero-width characters hide channel
  names. Spelled-out e-mails and phones written with letters are left to the number-word rule.
- Negation is not understood: "ещё не забронировано" is a ``COMPLETION_CLAIM``, "Мы не
  используем WhatsApp" is a ``CONTACT_CHANNEL``. These fail safe (the draft goes to the owner).
- Phrase patterns are best effort; missed cases must become new patterns plus eval scenarios.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.config import AutomationMode
from app.safety import filter_patterns as fp
from app.safety.masker import PiiType, mask

__all__ = [
    "HARD_BLOCK_CODES",
    "RULES_VERSION",
    "FilterConfig",
    "FilterContext",
    "FilterResult",
    "Finding",
    "PartVerdict",
    "ReasonCode",
    "check_parts",
]

RULES_VERSION = f"filter-{fp.PATTERNS_VERSION}"


class ReasonCode(StrEnum):
    """Why a part was denied (or, in owner-edit mode, warned about). See the module docstring."""

    EMPTY_PART = "EMPTY_PART"
    PART_TOO_LONG = "PART_TOO_LONG"
    UNRENDERED_TOKEN = "UNRENDERED_TOKEN"
    CONTACT_PHONE = "CONTACT_PHONE"
    CONTACT_EMAIL = "CONTACT_EMAIL"
    CONTACT_SOCIAL = "CONTACT_SOCIAL"
    CONTACT_CHANNEL = "CONTACT_CHANNEL"
    CONTACT_REDIRECT = "CONTACT_REDIRECT"
    URL_NOT_ALLOWED = "URL_NOT_ALLOWED"
    PAYMENT_CARD = "PAYMENT_CARD"
    PAYMENT_OFF_PLATFORM = "PAYMENT_OFF_PLATFORM"
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


#: Codes that block a part even in owner-edit (warn) mode.
HARD_BLOCK_CODES = frozenset({ReasonCode.EMPTY_PART, ReasonCode.PART_TOO_LONG})


@dataclass(frozen=True, slots=True)
class FilterConfig:
    """Versioned filter configuration.

    ``url_allowlist`` holds lower-case host names; a URL passes when its host equals an entry or
    is a subdomain of it (``www.avito.ru`` matches ``avito.ru``). Empty by default.
    """

    url_allowlist: tuple[str, ...] = ()
    max_part_units: int = 1000


@dataclass(frozen=True, slots=True)
class FilterContext:
    """Per-draft context. Every flag defaults to the strict value."""

    automation_mode: AutomationMode = AutomationMode.DRAFT_ONLY
    is_owner_edit: bool = False
    #: Exact texts rendered by code templates into these parts ({{rule:…}}, offer block, …).
    template_texts: tuple[str, ...] = ()
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
    """Verdict for one part. ``allowed`` already accounts for warn mode."""

    index: int
    allowed: bool
    findings: tuple[Finding, ...]

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
        """True when every part may be sent."""
        return all(part.allowed for part in self.parts)

    @property
    def reason_codes(self) -> tuple[ReasonCode, ...]:
        """Distinct reason codes over all parts, in order of first appearance."""
        return tuple(dict.fromkeys(code for part in self.parts for code in part.codes))

    @property
    def needs_owner_confirmation(self) -> bool:
        """Owner edit with findings: the UI must ask for an explicit "send anyway"."""
        return self.warn_only and any(part.findings for part in self.parts)


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------

_Region = tuple[int, int]

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
    (ReasonCode.CONTACT_CHANNEL, fp.CONTACT_CHANNEL_RE),
    (ReasonCode.CONTACT_REDIRECT, fp.CONTACT_REDIRECT_RE),
    (ReasonCode.PAYMENT_OFF_PLATFORM, fp.PAYMENT_OFF_PLATFORM_RE),
    (ReasonCode.HUMAN_CLAIM, fp.HUMAN_CLAIM_RE),
)
_PROMISE_PATTERNS: tuple[tuple[ReasonCode, re.Pattern[str]], ...] = (
    (ReasonCode.PROMISE_DISCOUNT, fp.DISCOUNT_RE),
    (ReasonCode.PROMISE_RETURN, fp.RETURN_RE),
    (ReasonCode.PROMISE_WARRANTY, fp.WARRANTY_RE),
    (ReasonCode.PROMISE_DELIVERY_DATE, fp.DELIVERY_DATE_RE),
)


def _utf16_units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _first_index_beyond(text: str, limit: int) -> int:
    """Index of the first character that does not fit into ``limit`` UTF-16 code units."""
    units = 0
    for index, ch in enumerate(text):
        units += 2 if ord(ch) > 0xFFFF else 1
        if units > limit:
            return index
    return len(text)


def _literal_pattern(literal: str) -> re.Pattern[str] | None:
    pieces = literal.split()
    if not pieces or not any(ch.isalnum() for ch in literal):
        return None
    body = r"\s+".join(re.escape(piece) for piece in pieces)
    first, last = pieces[0][0], pieces[-1][-1]
    left = r"(?<!\d)" if first.isdigit() else r"(?<![^\W_])" if first.isalnum() else ""
    right = r"(?!\d)" if last.isdigit() else r"(?![^\W_])" if last.isalnum() else ""
    return re.compile(left + body + right, re.IGNORECASE)


def _compile_all(texts: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    compiled = (_literal_pattern(text) for text in dict.fromkeys(texts))
    return tuple(p for p in compiled if p is not None)


def _occurrences(text: str, patterns: Iterable[re.Pattern[str]]) -> list[_Region]:
    return [m.span() for pattern in patterns for m in pattern.finditer(text)]


def _inside(start: int, end: int, regions: Iterable[_Region]) -> bool:
    return any(r_start <= start and end <= r_end for r_start, r_end in regions)


def _url_allowed(url: str, allowlist: tuple[str, ...]) -> bool:
    if not allowlist:
        return False
    rest = re.sub(r"^[a-z][a-z0-9+.-]*://", "", url.lower())
    host = re.split(r"[/?#]", rest, maxsplit=1)[0]
    host = host.rsplit("@", 1)[-1].split(":", 1)[0].rstrip(".")
    return any(host == entry or host.endswith("." + entry) for entry in allowlist)


def _matches(text: str, pattern: re.Pattern[str]) -> Iterator[_Region]:
    for match in pattern.finditer(text):
        if match.end() > match.start():
            yield match.span()


# ---------------------------------------------------------------------------------------------
# Per-part check
# ---------------------------------------------------------------------------------------------


def _check_part(
    text: str,
    literals: tuple[re.Pattern[str], ...],
    templates: tuple[re.Pattern[str], ...],
    context: FilterContext,
    config: FilterConfig,
) -> list[Finding]:
    if not text.strip():
        return [Finding(ReasonCode.EMPTY_PART, 0, len(text))]

    findings: list[Finding] = []
    if _utf16_units(text) > config.max_part_units:
        cut = _first_index_beyond(text, config.max_part_units)
        findings.append(Finding(ReasonCode.PART_TOO_LONG, cut, len(text)))

    literal_regions = _occurrences(text, literals)
    template_regions = _occurrences(text, templates)
    code_regions = literal_regions + template_regions
    # Spans already explained by a contact/URL/card/token finding (or an allowed URL): the
    # digits inside them are not reported a second time.
    consumed: list[_Region] = []

    for start, end in _matches(text, fp.UNRENDERED_TOKEN_RE):
        findings.append(Finding(ReasonCode.UNRENDERED_TOKEN, start, end))
        consumed.append((start, end))

    for span in mask(text).spans:
        code = _MASKER_CODES.get(span.type)
        if code is None:  # VIN and plate: their digits fall under the digit rule.
            continue
        consumed.append((span.start, span.end))
        if span.type in _LITERAL_EXEMPT_TYPES and _inside(span.start, span.end, literal_regions):
            continue
        if span.type is PiiType.URL and _url_allowed(
            text[span.start : span.end], config.url_allowlist
        ):
            continue
        findings.append(Finding(code, span.start, span.end))

    for code, pattern in _ALWAYS_PATTERNS:
        findings.extend(Finding(code, s, e) for s, e in _matches(text, pattern))

    for code, pattern in _PROMISE_PATTERNS:
        for start, end in _matches(text, pattern):
            if not _inside(start, end, template_regions):
                findings.append(Finding(code, start, end))

    if not context.fitment_verified:
        findings.extend(
            Finding(ReasonCode.UNVERIFIED_FITMENT, s, e) for s, e in _matches(text, fp.FITMENT_RE)
        )

    claims = (
        (ReasonCode.COMPLETION_CLAIM, fp.COMPLETION_RE, context.completion_confirmed),
        (ReasonCode.PAYMENT_RECEIVED_CLAIM, fp.PAYMENT_RECEIVED_RE, context.payment_confirmed),
    )
    for code, pattern, confirmed in claims:
        for start, end in _matches(text, pattern):
            if not (confirmed and _inside(start, end, template_regions)):
                findings.append(Finding(code, start, end))

    for start, end in _matches(text, fp.DIGITS_RE):
        if not _inside(start, end, code_regions) and not _inside(start, end, consumed):
            findings.append(Finding(ReasonCode.DIGITS_NOT_ALLOWED, start, end))

    for start, end in _matches(text, fp.CURRENCY_RE):
        if not _inside(start, end, code_regions) and not _inside(start, end, consumed):
            findings.append(Finding(ReasonCode.CURRENCY, start, end))

    for start, end in _matches(text, fp.NUMBER_WORD_RE):
        if text[start:end] in fp.NUMBER_WORD_SKIP_EXACT:
            continue
        if not _inside(start, end, code_regions) and not _inside(start, end, consumed):
            findings.append(Finding(ReasonCode.NUMBER_WORD, start, end))

    return sorted(set(findings), key=lambda f: (f.start, f.end, f.code.value))


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
    stored or sent.
    """
    if isinstance(parts, str):
        raise TypeError("parts must be a sequence of strings, not a single string")
    ctx = context if context is not None else FilterContext()
    cfg = config if config is not None else FilterConfig()
    allowlist_cfg = FilterConfig(
        url_allowlist=tuple(entry.lower().strip().strip(".") for entry in cfg.url_allowlist),
        max_part_units=cfg.max_part_units,
    )
    literals = _compile_all(allowed_literals)
    templates = _compile_all(ctx.template_texts)

    verdicts: list[PartVerdict] = []
    for index, text in enumerate(parts):
        findings = _check_part(text, literals, templates, ctx, allowlist_cfg)
        if ctx.is_owner_edit:
            allowed = not any(f.code in HARD_BLOCK_CODES for f in findings)
        else:
            allowed = not findings
        verdicts.append(PartVerdict(index=index, allowed=allowed, findings=tuple(findings)))

    return FilterResult(parts=tuple(verdicts), warn_only=ctx.is_owner_edit)

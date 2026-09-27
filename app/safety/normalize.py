"""Shared text normalization for the PII masker and the output filter (T-034, decision D-a).

``normalize(text)`` returns a ``NormalizedText``: three same-length views of the text plus an
offset map back to the original, so every detector can match on a clean view and still report
spans in the original text.

Steps, per grapheme cluster (a base character and the combining marks that follow it):

1. Lone surrogates and control characters (Cc other than tab, newline, carriage return) are
   removed and recorded in ``invalid`` (the filter reports ``INVALID_TEXT``).
2. Invisible characters are removed and recorded in ``hidden`` (the filter reports
   ``OBFUSCATION``): every format character (Unicode category Cf: zero-width space/joiner,
   soft hyphen, BOM, word joiner, bidi controls, ...) plus the invisible fillers that are not
   Cf: Hangul fillers, Braille blank, combining grapheme joiner, Khmer inherent vowels.
3. NFKC: fullwidth, superscript, subscript, circled and mathematical digits/letters become
   plain ASCII (``⁸``, ``８``, ``①``, ``𝟖`` -> ``8``), ``＠`` -> ``@``, ``．`` -> ``.``,
   non-breaking spaces -> space. ``№`` is kept as is (NFKC would turn it into ``No``).
4. Remaining combining marks (e.g. stress accents) and variation selectors are dropped.
5. Any other Unicode decimal digit (Arabic-Indic ``٤``, ...) becomes the ASCII digit.

Views (all the same length as ``text``, one character per normalized character):

- ``text``: the result of the steps above; case is preserved.
- ``cyr``: Latin and Greek look-alike letters folded to Cyrillic (``Cкидка`` -> ``Скидка``).
  Russian patterns match on this view.
- ``lat``: Cyrillic and Greek look-alike letters folded to Latin (``WhаtsApp`` -> ``WhatsApp``).
  Latin patterns (English, URLs, handles) match on this view.

``to_original(start, end)`` maps a span of the views back to the original text. A removed
character that sits between two kept characters of a span is inside the mapped span.

Pure and deterministic; nothing is logged.
"""

from __future__ import annotations

import bisect
import re
import unicodedata
from dataclasses import dataclass

__all__ = [
    "NormalizedText",
    "mixed_script_spans",
    "normalize",
    "spaced_letter_spans",
]

# Invisible characters that are not in category Cf.
_INVISIBLE_EXTRA = frozenset(
    {
        0x034F,  # combining grapheme joiner
        0x115F,  # Hangul choseong filler
        0x1160,  # Hangul jungseong filler
        0x17B4,  # Khmer vowel inherent AQ
        0x17B5,  # Khmer vowel inherent AA
        0x2800,  # Braille pattern blank
        0x3164,  # Hangul filler
        0xFFA0,  # halfwidth Hangul filler
    }
)
_ALLOWED_CONTROLS = frozenset("\t\n\r")
_KEEP_AS_IS = frozenset("№")
_MARK_CATEGORIES = frozenset({"Mn", "Mc", "Me"})

_LAT_TO_CYR = str.maketrans(
    "aceopxykABCEHKMOPTXYαοεκρτυχΑΒΕΗΙΚΜΝΟΡΤΧΥ",
    "асеорхукАВСЕНКМОРТХУаоекртухАВЕНІКМНОРТХУ",
)
_CYR_TO_LAT = str.maketrans(
    "аеорсухкіјѕԁӏАВЕКМНОРСТХУІЈЅαοεκρτυχνΑΒΕΗΙΚΜΝΟΡΤΧΥΖ",
    "aeopcyxkijsdlABEKMHOPCTXYIJSaoekptyxvABEHIKMNOPTXYZ",
)


@dataclass(frozen=True, slots=True)
class NormalizedText:
    """Normalized views of one text with an offset map back to the original."""

    original: str
    text: str
    cyr: str
    lat: str
    starts: tuple[int, ...]
    ends: tuple[int, ...]
    hidden: tuple[tuple[int, int], ...]
    invalid: tuple[tuple[int, int], ...]

    def to_original(self, start: int, end: int) -> tuple[int, int]:
        """Map a non-empty span of the views to the original text."""
        if not 0 <= start < end <= len(self.text):
            raise ValueError("span out of range")
        return self.starts[start], self.ends[end - 1]

    def from_original(self, start: int, end: int) -> tuple[int, int]:
        """The normalized span covering exactly the characters that lie inside [start, end)
        of the original. Empty (``(i, i)``) when no normalized character lies inside."""
        first = bisect.bisect_left(self.starts, start)
        last = bisect.bisect_right(self.ends, end)
        if last < first:
            return first, first
        return first, last


def _script(ch: str) -> str | None:
    cp = ord(ch)
    if ch.isascii():
        return "latin" if ch.isalpha() else None
    if 0x0400 <= cp <= 0x052F or 0x1C80 <= cp <= 0x1C8F or 0xA640 <= cp <= 0xA69F:
        return "cyrillic"
    if 0x0370 <= cp <= 0x03FF or 0x1F00 <= cp <= 0x1FFF:
        return "greek"
    if (0x00C0 <= cp <= 0x024F and cp not in (0xD7, 0xF7)) or 0x1E00 <= cp <= 0x1EFF:
        return "latin"
    return None


def _is_invisible(ch: str, category: str) -> bool:
    return category == "Cf" or ord(ch) in _INVISIBLE_EXTRA


def _is_variation_selector(ch: str) -> bool:
    cp = ord(ch)
    return 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF


def _clean(chunk: str) -> str:
    out: list[str] = []
    for ch in chunk:
        category = unicodedata.category(ch)
        if category in _MARK_CATEGORIES or category == "Cf":
            continue
        if category == "Nd" and not ch.isascii():
            ch = str(unicodedata.decimal(ch))
        out.append(ch)
    return "".join(out)


def normalize(text: str) -> NormalizedText:
    """Normalize ``text`` (see the module docstring)."""
    out: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    hidden: list[tuple[int, int]] = []
    invalid: list[tuple[int, int]] = []
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        cp = ord(ch)
        category = unicodedata.category(ch)
        if 0xD800 <= cp <= 0xDFFF or (category == "Cc" and ch not in _ALLOWED_CONTROLS):
            invalid.append((i, i + 1))
            i += 1
            continue
        if _is_invisible(ch, category):
            hidden.append((i, i + 1))
            i += 1
            continue
        j = i + 1
        while j < n:
            nxt = text[j]
            nxt_category = unicodedata.category(nxt)
            if nxt_category not in _MARK_CATEGORIES or _is_invisible(nxt, nxt_category):
                break
            j += 1
        cluster = text[i:j]
        # "№" is kept: NFKC would turn it into "No".
        normalized = ch if ch in _KEEP_AS_IS else _clean(unicodedata.normalize("NFKC", cluster))
        for piece in normalized:
            out.append(piece)
            starts.append(i)
            ends.append(j)
        i = j

    view = "".join(out)
    return NormalizedText(
        original=text,
        text=view,
        cyr=view.translate(_LAT_TO_CYR),
        lat=view.translate(_CYR_TO_LAT),
        starts=tuple(starts),
        ends=tuple(ends),
        hidden=tuple(hidden),
        invalid=tuple(invalid),
    )


_LETTER_RUN_RE = re.compile(r"[^\W\d_]+")
# Four or more single letters separated by one separator: "т е л е г р а м", "П-о-з-в-о-н-и".
_SPACED_LETTERS_RE = re.compile(r"(?<![^\W\d_])(?:[^\W\d_][ \-._*·/]){3,}[^\W\d_](?![^\W\d_])")


def mixed_script_spans(text: str) -> list[tuple[int, int]]:
    """Spans of letter runs that mix Latin, Cyrillic and/or Greek letters ("Cкидка")."""
    spans: list[tuple[int, int]] = []
    for match in _LETTER_RUN_RE.finditer(text):
        scripts = {_script(ch) for ch in match.group()}
        scripts.discard(None)
        if len(scripts) > 1:
            spans.append(match.span())
    return spans


def spaced_letter_spans(text: str) -> list[tuple[int, int]]:
    """Spans of words spelled out letter by letter ("З в о н и т е")."""
    return [m.span() for m in _SPACED_LETTERS_RE.finditer(text)]

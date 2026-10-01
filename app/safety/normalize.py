"""Shared text normalization for the PII masker and the output filter (T-034, decision D-a).

``normalize(text)`` returns a ``NormalizedText``: three same-length views of the text plus an
offset map back to the original, so every detector can match on a clean view and still report
spans in the original text.

Steps, per grapheme cluster (a base character and the combining marks that follow it):

1. Lone surrogates and control characters (Cc other than tab, newline, carriage return) are
   removed and recorded in ``invalid`` (the filter reports ``INVALID_TEXT``).
2. Invisible characters are removed and recorded in ``hidden`` (the filter reports
   ``OBFUSCATION``): every format character (Unicode category Cf: zero-width space/joiner,
   soft hyphen, BOM, word joiner, bidi controls, ...), unassigned (Cn) and private-use (Co)
   code points, the object replacement character U+FFFC (T-041 / Y-13), and the invisible
   fillers that are not Cf: Hangul fillers, Braille blank, combining grapheme joiner, Khmer
   inherent vowels.
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

Detectors for the filter's ``OBFUSCATION`` code (T-041):

- ``foreign_letter_spans``: any letter outside the allowed sets (Y-3): ASCII, Latin-1, Turkish
  (ğ ı İ ş), Russian Cyrillic and ё. IPA, small caps, Greek, Coptic, Armenian, Cherokee, Lisu,
  non-Russian Cyrillic ("ѕ", "і") and every other script are foreign.
- ``mixed_script_spans``: a word mixing Latin and Cyrillic, except a Latin brand name plus a
  Russian case ending ("Mercedesа", "BMWшный").
- ``spaced_letter_spans``: a word spelled letter by letter with 1-3 whitespace characters or
  one of ``- . _ * · / | + ~`` between the letters (Y-4).
- ``compact``: a view without whitespace and those separators, used to find high-risk stems
  split across words ("Позв оните", "бес платно").

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
    "compact",
    "foreign_letter_spans",
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
        0xFFFC,  # object replacement character
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
    # Cf format characters, invisible fillers, unassigned (Cn) and private-use (Co) code points
    # and the object replacement character (Y-13).
    return category in ("Cf", "Cn", "Co") or ord(ch) in _INVISIBLE_EXTRA


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
# Single letters separated by 1-3 whitespace characters or one of - . _ * · / | + ~
# ("т е л е г р а м", "П-о-з-в-о-н-и", "т|е|л|е|г|р|а|м").
_SPACED_LETTERS_RE = re.compile(
    r"(?<![^\W\d_])(?:[^\W\d_](?:\s{1,3}|[-._*·/|+~])){3,}[^\W\d_](?![^\W\d_])"
)
# Latin brand name + Russian case ending ("Mercedesа", "BMWшный") is ordinary Russian usage.
_BRAND_SUFFIX_RE = re.compile(
    r"[A-Za-z]{3,}(?:а|у|е|ом|ой|ы|ов|ам|ами|ах|ский|ская|ское|ские|шный|шная|шное|шные)"
)
# Separators removed in the compacted view (Y-4): whitespace and - | + ~ _ * · .
_COMPACT_SEPARATORS = frozenset("-|+~_*·.")


def _allowed_letter(ch: str) -> bool:
    """Letters of the allowed sets (Y-3): ASCII, Latin-1, Turkish, Russian Cyrillic + ё."""
    cp = ord(ch)
    return (
        ch.isascii()
        or (0x00C0 <= cp <= 0x00FF and cp not in (0xD7, 0xF7))
        or cp in (0x011E, 0x011F, 0x0130, 0x0131, 0x015E, 0x015F)
        or 0x0410 <= cp <= 0x044F
        or cp in (0x0401, 0x0451)
    )


def foreign_letter_spans(text: str) -> list[tuple[int, int]]:
    """Spans of letters outside the allowed sets (IPA, small caps, Coptic, Greek, Armenian,
    Cherokee, Lisu, CJK, non-Russian Cyrillic such as "ѕ", ...): all of them are obfuscation."""
    spans: list[tuple[int, int]] = []
    for index, ch in enumerate(text):
        if ch.isalpha() and not _allowed_letter(ch):
            if spans and spans[-1][1] == index:
                spans[-1] = (spans[-1][0], index + 1)
            else:
                spans.append((index, index + 1))
    return spans


def mixed_script_spans(text: str) -> list[tuple[int, int]]:
    """Spans of letter runs that mix Latin and Cyrillic letters ("Cкидка"), except a Latin
    brand name followed by a Russian case ending ("Mercedesа")."""
    spans: list[tuple[int, int]] = []
    for match in _LETTER_RUN_RE.finditer(text):
        scripts = {_script(ch) for ch in match.group()}
        scripts.discard(None)
        if len(scripts) > 1 and not _BRAND_SUFFIX_RE.fullmatch(match.group()):
            spans.append(match.span())
    return spans


def spaced_letter_spans(text: str) -> list[tuple[int, int]]:
    """Spans of words spelled out letter by letter ("З в о н и т е"): at least four letters
    when one of them is Cyrillic, at least six when all are Latin ("A B C D" is a marking)."""
    spans: list[tuple[int, int]] = []
    for match in _SPACED_LETTERS_RE.finditer(text):
        letters = [ch for ch in match.group() if ch.isalpha()]
        cyrillic = any(_script(ch) == "cyrillic" for ch in letters)
        if len(letters) >= (4 if cyrillic else 6):
            spans.append(match.span())
    return spans


def compact(view: str) -> tuple[str, tuple[int, ...]]:
    """``view`` without whitespace and the separators - | + ~ _ * · . (Y-4), plus the index in
    ``view`` of every kept character. Used to find high-risk stems split across words."""
    index = tuple(i for i, ch in enumerate(view) if not (ch.isspace() or ch in _COMPACT_SEPARATORS))
    return "".join(view[i] for i in index), index

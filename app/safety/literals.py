"""Spelling variants of fact-sheet literals for the output filter (T-034, decision D-j).

The output filter allows digits, currency and number words only inside an occurrence of an
``allowed_literals`` string, matched as written (case-insensitive, flexible whitespace, trailing
punctuation ignored). ``literal_variants(value, kind)`` produces the usual spellings of one
record value so the LLM may write "15000 ₽" when the placeholder rendered "15 000 ₽".

**Contract:** call it only with values from fact-sheet or product records (code placeholders,
catalog OEM/SKU, body codes, years, quantities). Never with customer free text: a literal is a
permission to print that number.

Pure and deterministic; unknown formats return just the value itself.
"""

from __future__ import annotations

import re
from enum import StrEnum

__all__ = ["LiteralKind", "literal_variants"]


class LiteralKind(StrEnum):
    """What a literal is; decides which spellings are generated."""

    PRICE = "price"  # "15 000 ₽" / "15000 ₽" / "15 000₽" / "15 000 руб."
    QUANTITY = "quantity"  # "2 шт" / "2 шт." / "2шт"
    MODEL = "model"  # "E200" / "E 200", "220d" / "220 d"
    TIRE = "tire"  # "205/55 R16" / "205/55R16" / "205 / 55 R16"
    OEM = "oem"  # "90915-10003" / "90915 10003" / "9091510003"; "A2138851400" / "A 213 885 14 00"
    ENGINE_VOLUME = "engine_volume"  # "2.0" / "2,0"
    OTHER = "other"  # year, body code, SKU: used as written


_SPACES = "   "
_PRICE_RE = re.compile(r"(?P<num>\d[\d ]*)\s*(?P<cur>₽|руб\.?|р\.?)?", re.IGNORECASE)
_QUANTITY_RE = re.compile(r"(?P<num>\d+)\s*(?P<unit>шт\.?)?", re.IGNORECASE)
_MODEL_LETTERS_FIRST_RE = re.compile(r"(?P<a>[^\W\d_]{1,4})\s?(?P<b>\d{2,4})")
_MODEL_DIGITS_FIRST_RE = re.compile(r"(?P<a>\d{2,4})\s?(?P<b>[^\W\d_]{1,4})")
_TIRE_RE = re.compile(r"(?P<w>\d{3})\s*/\s*(?P<h>\d{2})\s*(?P<r>Z?R)\s*(?P<d>\d{2})", re.IGNORECASE)
_OEM_GROUPS_RE = re.compile(r"[A-Za-z0-9]+")
_MERCEDES_RE = re.compile(r"[A-Z]\d{10}")
_DECIMAL_RE = re.compile(r"(?P<i>\d+)[.,](?P<f>\d+)")


def _group_thousands(digits: str) -> str:
    groups: list[str] = []
    while len(digits) > 3:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    groups.insert(0, digits)
    return " ".join(groups)


def _price(value: str) -> list[str]:
    match = _PRICE_RE.fullmatch(value)
    if match is None:
        return []
    digits = match.group("num").replace(" ", "")
    numbers = [_group_thousands(digits), digits]
    out: list[str] = []
    for number in numbers:
        out += [f"{number} ₽", f"{number}₽", f"{number} руб.", f"{number} руб"]
    return out


def _quantity(value: str) -> list[str]:
    match = _QUANTITY_RE.fullmatch(value)
    if match is None or match.group("unit") is None:
        return []
    n = match.group("num")
    return [f"{n} шт.", f"{n} шт", f"{n}шт.", f"{n}шт"]


def _model(value: str) -> list[str]:
    for pattern in (_MODEL_LETTERS_FIRST_RE, _MODEL_DIGITS_FIRST_RE):
        match = pattern.fullmatch(value)
        if match is not None:
            a, b = match.group("a"), match.group("b")
            return [f"{a}{b}", f"{a} {b}"]
    return []


def _tire(value: str) -> list[str]:
    match = _TIRE_RE.fullmatch(value)
    if match is None:
        return []
    w, h, r, d = match.group("w", "h", "r", "d")
    r = r.upper()
    return [f"{w}/{h} {r}{d}", f"{w}/{h}{r}{d}", f"{w} / {h} {r}{d}"]


def _oem(value: str) -> list[str]:
    groups = _OEM_GROUPS_RE.findall(value)
    if not groups:
        return []
    joined = "".join(groups)
    out = [joined, " ".join(groups), "-".join(groups)]
    upper = joined.upper()
    if _MERCEDES_RE.fullmatch(upper):
        d = upper[1:]
        out.append(f"{upper[0]} {d[0:3]} {d[3:6]} {d[6:8]} {d[8:10]}")
    return out


def _engine_volume(value: str) -> list[str]:
    match = _DECIMAL_RE.fullmatch(value)
    if match is None:
        return []
    i, f = match.group("i", "f")
    return [f"{i}.{f}", f"{i},{f}"]


_GENERATORS = {
    LiteralKind.PRICE: _price,
    LiteralKind.QUANTITY: _quantity,
    LiteralKind.MODEL: _model,
    LiteralKind.TIRE: _tire,
    LiteralKind.OEM: _oem,
    LiteralKind.ENGINE_VOLUME: _engine_volume,
}


def literal_variants(value: str, kind: LiteralKind | str) -> tuple[str, ...]:
    """The value itself followed by its usual spellings for ``kind`` (no duplicates)."""
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    kind = LiteralKind(kind)
    cleaned = " ".join(value.translate({ord(ch): " " for ch in _SPACES}).split())
    generator = _GENERATORS.get(kind)
    variants = [value, *(generator(cleaned) if generator is not None and cleaned else [])]
    return tuple(dict.fromkeys(v for v in variants if v))

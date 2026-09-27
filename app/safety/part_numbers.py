"""Part-number candidates from raw customer text (T-034, decision D-i).

The PII masker deliberately masks some part numbers as phones (a 10-digit number starting with
9, an 11-digit ``89…`` number, ...). The orchestrator therefore calls
``extract_part_number_candidates(raw_text)`` on the UNMASKED customer text, before masking,
and uses the result only for catalog lookup: a candidate that matches a catalog record becomes a
fact (and may then enter ``allowed_literals`` from that record); unmatched candidates are
dropped.

**Privacy:** candidates can be phone numbers. Never log them, store them, show them to the LLM
or put them into ``allowed_literals`` directly. The result keeps only offsets and the
normalized key, not the raw text.

A candidate is a run of Latin letters/digits groups separated by single spaces, dashes, dots or
slashes (``A 213 885 14 00``, ``90915-10003``, ``5Q0 407 271 AH``), or any contiguous window of
up to six space-separated groups of such a run, whose normalized key (upper-case letters and
digits only) is 6-20 characters long with at least 5 digits. Cyrillic look-alike letters are
read as Latin and fullwidth/superscript digits as digits (``app.safety.normalize``).

Pure and deterministic; results are sorted by position.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.safety.normalize import normalize

__all__ = ["PartNumberCandidate", "extract_part_number_candidates"]

# Runs must not touch a letter or digit of any script ("км" after a number is not part of it).
_RUN_RE = re.compile(r"(?<![^\W_])[A-Za-z0-9]+(?:[ \-./][A-Za-z0-9]+){0,15}(?![^\W_])")
_GROUP_RE = re.compile(r"[A-Za-z0-9]+(?:[\-./][A-Za-z0-9]+)*")
_MAX_GROUPS = 6


@dataclass(frozen=True, slots=True)
class PartNumberCandidate:
    """``start``/``end`` are offsets into the raw text; ``key`` is upper-case A-Z0-9 only."""

    start: int
    end: int
    key: str


def _key(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isascii() and ch.isalnum())


def _acceptable(key: str) -> bool:
    return 6 <= len(key) <= 20 and sum(ch.isdigit() for ch in key) >= 5


def extract_part_number_candidates(raw_text: str) -> tuple[PartNumberCandidate, ...]:
    """Candidate part numbers in ``raw_text`` (see the module docstring)."""
    if not isinstance(raw_text, str):
        raise TypeError("raw_text must be a string")
    nt = normalize(raw_text)
    view = nt.lat
    seen: dict[str, PartNumberCandidate] = {}
    for run in _RUN_RE.finditer(view):
        groups = [
            (m.start() + run.start(), m.end() + run.start())
            for m in _GROUP_RE.finditer(run.group())
        ]
        for i in range(len(groups)):
            for j in range(i, min(i + _MAX_GROUPS, len(groups))):
                start, end = groups[i][0], groups[j][1]
                key = _key(view[start:end])
                if not _acceptable(key) or key in seen:
                    continue
                o_start, o_end = nt.to_original(start, end)
                seen[key] = PartNumberCandidate(o_start, o_end, key)
    return tuple(sorted(seen.values(), key=lambda c: (c.start, c.end, c.key)))

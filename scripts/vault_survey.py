"""Read-only, anonymised structure survey of an Obsidian vault (T-043).

Run on the owner's PC (after ``uv sync``, see docs/SETUP_WINDOWS.md)::

    uv run python scripts/vault_survey.py "C:\\...\\Vault" [--out C:\\...\\kasa_raporu.md]

The report (Turkish, Markdown) describes the vault's *structure* so an inventory adapter can be
designed without seeing business data. It never contains values: no prices, quantities, SKUs,
titles, file names or the vault path. Only folder names (hashable with ``--redact-names``), key
/ column names, inferred types, counts, ratios and value *shapes* (``A###-###-##-##``) appear.
Key-like names that look like values (4+ digits, URLs, very long text) are replaced by a shape.

Safety rules (docs/VAULT_SURVEY.md):
- strictly read-only: files are opened with mode ``"rb"`` only; nothing is written in the vault;
- ``.obsidian/`` and every other hidden folder is never entered or listed;
- symlinks and junctions are never followed, and every path is checked to stay inside the vault;
- ``--out`` must point outside the vault.

Standard library only (no PyYAML): frontmatter is read with a small tolerant parser.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import io
import os
import re
import secrets
import stat
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TextIO

REPORT_VERSION = "1"
EXIT_OK = 0
EXIT_USAGE = 2

DEFAULT_MAX_FILES = 50_000
DEFAULT_MAX_NOTE_BYTES = 2_000_000
DEFAULT_DEPTH = 3
DEFAULT_MAX_CHILDREN = 25
DEFAULT_MIN_HEADING_NOTES = 3
MAX_WALK_DEPTH = 64
PROGRESS_EVERY = 250
MAX_DISTINCT = 200_000

IMAGE_EXTS = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".bmp", ".svg", ".avif", ".tif"}
    | {".tiff"}
)
# Names of hidden folders that may be shown; any other hidden folder is only counted.
KNOWN_HIDDEN = frozenset({".obsidian", ".trash", ".git", ".stfolder"})
# Windows reparse tags for symlinks and junctions (mount points). Cloud placeholders (OneDrive)
# are reparse points too but are ordinary files, so only these two are treated as links.
_LINK_REPARSE_TAGS = frozenset({0xA000000C, 0xA0000003})
# Code block languages worth naming; any other language is only counted as "(diğer)".
KNOWN_CODE_LANGS = frozenset({"dataview", "dataviewjs", "base", "bases", "query", "tasks", "csv"})
ID_NAME_HINTS = ("sku", "oem", "артик", "код", "номер", "parça", "parca", "art", "part", "каталож")
_BOOL_WORDS = frozenset({"true", "false", "yes", "no", "да", "нет", "evet", "hayır"})

T_EMPTY, T_BOOL, T_NUMBER, T_MONEY, T_DATE, T_CODE = (
    "boş",
    "evet/hayır",
    "sayı",
    "para",
    "tarih",
    "kod",
)
T_TEXT, T_LIST, T_OBJECT, T_LINK, T_IMAGE, T_URL = (
    "metin",
    "liste",
    "nesne",
    "bağlantı",
    "görsel",
    "url",
)

_WIKILINK = re.compile(r"(!?)\[\[([^\]\n]+?)\]\]")
_MDLINK = re.compile(r"(!?)\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_URL = re.compile(r"^(https?|ftp)://\S+$|^www\.\S+$", re.IGNORECASE)
_DATE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?$"
    r"|^\d{1,2}[./]\d{1,2}[./]\d{2,4}$"
)
_NUMBER = re.compile(r"^[+-]?(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,]\d+)?$")
_CURRENCY = re.compile(r"(₽|руб\.?|р\.|\bр\b|rub|usd|eur|\$|€|₺|\btl\b)", re.IGNORECASE)
_ID_CHARS = re.compile(r"^[0-9A-Za-zА-Яа-яЁё][0-9A-Za-zА-Яа-яЁё\-./ _]{3,34}$")
_LETTER_RUN = re.compile(r"[^\W\d_]{5,}")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```+|~~~+)\s*([\w-]*)")
_INLINE_LINE = re.compile(
    r"^\s*(?:[-*+]\s+|\d+[.)]\s+|>\s*)?(?:\*\*|__)?([^\[\]()`:|*_\n][^\[\]()`:|\n]{0,59}?)"
    r"(?:\*\*|__)?::(?!:)\s*(.*)$"
)
_INLINE_BRACKET = re.compile(r"[\[(]([^\[\]()`:|\n]{1,60}?)::\s*([^\[\]()\n]*)[\])]")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{1,}:?\s*)*\|?\s*$")
_FM_KEY = re.compile(
    r"^(\"(?:[^\"\\]|\\.)*\"|'[^']*'|[^\s#'\"\-{}\[\]][^:]*?|-[^\s:][^:]*?)\s*:(?:\s+(.*)|\s*)$"
)
_TAG = re.compile(r"(?<![\w/#&])#[^\s#\[\](){}.,;:!?\"'`]+")


# --------------------------------------------------------------------------------------------
# Value shapes and classification. Values are only ever inspected, never stored or printed.
# --------------------------------------------------------------------------------------------


def shape(value: str, limit: int = 32) -> str:
    """``A 213 885-14 00`` → ``A ### ###-## ##``. Latin → A, Cyrillic → Я, other letters → Ω."""
    out = []
    text = value.strip()
    for ch in text[:limit]:
        if ch.isdigit():
            out.append("#")
        elif ch.isalpha():
            if ch.isascii():
                out.append("A")
            elif "\u0400" <= ch <= "\u04ff":
                out.append("Я")
            else:
                out.append("Ω")
        elif ch in " -./_":
            out.append(ch)
        else:
            out.append("?")
    return "".join(out) + ("…" if len(text) > limit else "")


def normalize_id(value: str) -> str:
    return re.sub(r"[\s\-./_]+", "", value).upper()


def is_idlike(value: str) -> bool:
    """Does the value look like a SKU / OEM / part number (not a price, date or word)?"""
    s = value.strip()
    if not _ID_CHARS.match(s) or s.count(" ") > 4 or _DATE.match(s):
        return False
    alnum = [c for c in s if c.isalnum()]
    digits = sum(c.isdigit() for c in alnum)
    if digits < 3 or digits / len(alnum) < 0.4 or _LETTER_RUN.search(s):
        return False
    return not (_NUMBER.match(s) and digits < 7)


def _links_only(value: str) -> str | None:
    """``T_IMAGE``/``T_LINK`` when the value is nothing but wikilinks / Markdown links."""
    targets = [m.group(2) for m in _WIKILINK.finditer(value)]
    targets += [m.group(2) for m in _MDLINK.finditer(value)]
    if not targets:
        return None
    rest = _MDLINK.sub("", _WIKILINK.sub("", value))
    if rest.strip(" ,;\t"):
        return None
    return T_IMAGE if any(_is_image_target(t) for t in targets) else T_LINK


def _is_image_target(target: str) -> bool:
    name = target.split("|", 1)[0].split("#", 1)[0].strip()
    return os.path.splitext(name)[1].lower() in IMAGE_EXTS


def classify(value: str) -> str:
    s = value.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()
    if not s or s.lower() in {"null", "~"}:
        return T_EMPTY
    if s.lower() in _BOOL_WORDS:
        return T_BOOL
    linked = _links_only(s)
    if linked:
        return linked
    if _URL.match(s):
        return T_URL
    if _DATE.match(s):
        return T_DATE
    if _CURRENCY.search(s) and _NUMBER.match(_CURRENCY.sub("", s).strip()):
        return T_MONEY
    if is_idlike(s):
        return T_CODE
    if _NUMBER.match(s):
        return T_NUMBER
    return T_TEXT


def _unquote(value: str) -> str:
    s = value.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def safe_label(name: str, limit: int = 48) -> str:
    """A key / column / folder name for the report, or a shape if it looks like a value."""
    n = " ".join(name.replace("`", "'").split())
    if not n:
        return "<boş ad>"
    if len(n) > limit:
        return f"<uzun ad: {len(n)} karakter>"
    if sum(c.isdigit() for c in n) >= 4 or "@" in n or "://" in n or n.lower().startswith("www."):
        return f"<değer benzeri ad: {shape(n)}>"
    return n


def md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


# --------------------------------------------------------------------------------------------
# File access: read-only, no links, never outside the vault.
# --------------------------------------------------------------------------------------------


def is_inside(root_real: str, path: str) -> bool:
    real = os.path.normcase(os.path.realpath(path))
    root = os.path.normcase(root_real)
    try:
        return os.path.commonpath([root, real]) == root
    except ValueError:  # different drives on Windows
        return False


def _is_link(entry: os.DirEntry[str]) -> bool:
    if entry.is_symlink():
        return True
    try:
        st = entry.stat(follow_symlinks=False)
    except OSError:
        return True
    return getattr(st, "st_reparse_tag", 0) in _LINK_REPARSE_TAGS


def read_text(path: str, max_bytes: int) -> tuple[str, str, bool]:
    """Read at most ``max_bytes`` (mode ``rb``) and decode: UTF-8 (±BOM), UTF-16 BOM, cp1251."""
    with open(path, "rb") as fh:
        data = fh.read(max_bytes + 1)
    cut = len(data) > max_bytes
    data = data[:max_bytes]
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace"), "utf-16", cut
    enc = "utf-8"
    if data.startswith(b"\xef\xbb\xbf"):
        data, enc = data[3:], "utf-8-bom"
    try:
        return data.decode("utf-8"), enc, cut
    except UnicodeDecodeError as exc:
        if cut and exc.start >= len(data) - 3:
            return data[: exc.start].decode("utf-8", errors="replace"), enc, cut
        return data.decode("cp1251", errors="replace"), "cp1251", cut


@dataclass
class DirStat:
    md_direct: int = 0
    other_direct: int = 0
    children: set[str] = field(default_factory=set)


@dataclass
class FileEntry:
    path: str  # absolute, used for reading only; never rendered
    rel: tuple[str, ...]
    size: int
    ext: str


@dataclass
class WalkResult:
    files: list[FileEntry] = field(default_factory=list)
    dirs: dict[tuple[str, ...], DirStat] = field(default_factory=dict)
    skipped_links: int = 0
    hidden_dirs: Counter[str] = field(default_factory=Counter)
    hidden_files: int = 0
    special_files: int = 0
    errors: int = 0
    too_deep: int = 0
    truncated: bool = False


class Progress:
    """File counter on stderr (the report goes to stdout or ``--out``)."""

    def __init__(self, enabled: bool, stream: TextIO) -> None:
        self.enabled = enabled
        self.stream = stream
        self.shown = False

    def tick(self, phase: str, n: int, total: int | None = None, force: bool = False) -> None:
        if not self.enabled or (not force and n % PROGRESS_EVERY):
            return
        suffix = f"/{total}" if total else ""
        self.stream.write(f"\r[vault_survey] {phase}: {n}{suffix} dosya   ")
        self.stream.flush()
        self.shown = True

    def done(self) -> None:
        if self.shown:
            self.stream.write("\n")
            self.stream.flush()


def walk_vault(root_real: str, max_files: int, progress: Progress) -> WalkResult:
    res = WalkResult()
    res.dirs[()] = DirStat()
    stack: list[tuple[str, tuple[str, ...]]] = [(root_real, ())]
    while stack:
        path, rel = stack.pop()
        try:
            with os.scandir(path) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError:
            res.errors += 1
            continue
        subdirs: list[tuple[str, tuple[str, ...]]] = []
        for entry in entries:
            if entry.name.startswith(".") and entry.is_dir(follow_symlinks=False):
                res.hidden_dirs[entry.name if entry.name in KNOWN_HIDDEN else "<gizli>"] += 1
                continue
            if _is_link(entry):
                res.skipped_links += 1
                continue
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                res.errors += 1
                continue
            if stat.S_ISDIR(st.st_mode):
                if len(rel) + 1 > MAX_WALK_DEPTH:
                    res.too_deep += 1
                    continue
                if not is_inside(root_real, entry.path):
                    res.skipped_links += 1
                    continue
                child = (*rel, entry.name)
                res.dirs[rel].children.add(entry.name)
                res.dirs[child] = DirStat()
                subdirs.append((entry.path, child))
            elif stat.S_ISREG(st.st_mode):
                if entry.name.startswith("."):
                    res.hidden_files += 1
                    continue
                if len(res.files) >= max_files:
                    res.truncated = True
                    return res
                ext = os.path.splitext(entry.name)[1].lower()
                res.files.append(FileEntry(entry.path, (*rel, entry.name), st.st_size, ext))
                if ext == ".md":
                    res.dirs[rel].md_direct += 1
                else:
                    res.dirs[rel].other_direct += 1
                progress.tick("taranıyor", len(res.files))
            else:
                res.special_files += 1
        stack.extend(reversed(subdirs))
    return res


# --------------------------------------------------------------------------------------------
# Parsing: tolerant frontmatter, inline fields, tables.
# --------------------------------------------------------------------------------------------


@dataclass
class FmValue:
    kind: str  # scalar | list | object | block
    items: list[str]


def _split_flow(text: str) -> list[str]:
    """Split ``a, "b, c", [[x|y]]`` on top-level commas."""
    items, buf, depth, quote = [], [], 0, ""
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    items.append("".join(buf))
    return [_unquote(i) for i in items if i.strip()]


def _strip_comment(value: str) -> str:
    if value[:1] in "\"'":
        return value
    return re.split(r"\s+#", value, maxsplit=1)[0]


def split_frontmatter(text: str) -> tuple[list[str] | None, list[str], bool]:
    """(frontmatter lines or None, body lines, malformed)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, lines, False
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return lines[1:i], lines[i + 1 :], False
    return None, lines, True


def parse_frontmatter(lines: Sequence[str]) -> dict[str, FmValue]:
    """Top-level keys of a YAML mapping, tolerant of what Obsidian and people write. Nested
    mappings add ``parent.child`` keys (one level)."""
    out: dict[str, FmValue] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith("#") or line[:1] in " \t-":
            continue
        m = _FM_KEY.match(line)
        if not m:
            continue
        key = _unquote(m.group(1)).strip()
        rest = _strip_comment((m.group(2) or "").strip()).strip()
        block: list[str] = []
        while i < len(lines) and (lines[i][:1] in " \t-" or not lines[i].strip()):
            if lines[i].strip():
                block.append(lines[i])
            i += 1
        if rest[:1] in "|>" and re.fullmatch(r"[|>][+-]?\d*", rest):
            out[key] = FmValue("block", [" ".join(b.strip() for b in block)])
        elif rest.startswith("["):
            out[key] = FmValue("list", _split_flow(rest.strip()[1:].rstrip().rstrip("]")))
        elif rest.startswith("{"):
            children = _split_flow(rest.strip()[1:].rstrip().rstrip("}"))
            out[key] = FmValue("object", [c for c in children if c])
            for child in children:
                ck, _, cv = child.partition(":")
                if ck.strip():
                    out[f"{key}.{_unquote(ck).strip()}"] = FmValue("scalar", [cv.strip()])
        elif rest:
            cont = " ".join(b.strip() for b in block)
            out[key] = FmValue("scalar", [f"{rest} {cont}".strip()])
        elif block and block[0].lstrip().startswith("-"):
            items = []
            for b in block:
                s = b.strip()
                if s.startswith("-"):
                    items.append(_unquote(_strip_comment(s[1:].strip())))
            out[key] = FmValue("list", items)
        elif block:
            out[key] = FmValue("object", ["x"])
            indent = min(len(b) - len(b.lstrip()) for b in block)
            for b in block:
                if len(b) - len(b.lstrip()) != indent:
                    continue
                cm = _FM_KEY.match(b.strip())
                if cm:
                    val = _strip_comment((cm.group(2) or "").strip())
                    out[f"{key}.{_unquote(cm.group(1)).strip()}"] = FmValue("scalar", [val])
        else:
            out[key] = FmValue("scalar", [""])
    return out


def split_cells(line: str) -> list[str]:
    """Split a Markdown table row on ``|`` except escaped ``\\|`` and inside ``[[...]]``."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, buf, depth, i = [], [], 0, 0
    while i < len(s):
        ch = s[i]
        if s.startswith("[[", i):
            depth += 1
            buf.append("[[")
            i += 2
            continue
        if s.startswith("]]", i) and depth:
            depth -= 1
            buf.append("]]")
            i += 2
            continue
        if ch == "\\" and s.startswith("\\|", i):
            buf.append("|")
            i += 2
            continue
        if ch == "|" and not depth:
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    cells.append("".join(buf).strip())
    return cells


# --------------------------------------------------------------------------------------------
# Aggregation.
# --------------------------------------------------------------------------------------------


@dataclass
class FieldStat:
    """One key (frontmatter / inline) or column (table / CSV). No values are kept: only types,
    shapes of identifier-like values and hashes for a uniqueness ratio (in memory)."""

    present: int = 0
    filled: int = 0
    types: Counter[str] = field(default_factory=Counter)
    item_types: Counter[str] = field(default_factory=Counter)
    values: int = 0
    idlike: int = 0
    shapes: Counter[str] = field(default_factory=Counter)
    distinct: set[int] = field(default_factory=set)
    images: int = 0

    def observe_value(self, value: str) -> str | None:
        """Count one scalar for id detection; return its normalized id if id-like."""
        v = _unquote(value).strip()
        if not v:
            return None
        self.values += 1
        if _is_image_value(v) or _links_only(v) == T_IMAGE:
            self.images += 1
        if not is_idlike(v):
            return None
        self.idlike += 1
        self.shapes[shape(v)] += 1
        norm = normalize_id(v)
        if len(self.distinct) < MAX_DISTINCT:
            self.distinct.add(hash(norm))
        return norm

    def observe(self, fv: FmValue) -> list[str]:
        self.present += 1
        nonempty = [x for x in fv.items if _unquote(x).strip()]
        if fv.kind == "list":
            self.types[T_LIST] += 1
            for x in nonempty:
                self.item_types[classify(x)] += 1
        elif fv.kind == "object":
            self.types[T_OBJECT] += 1
        elif fv.kind == "block":
            self.types[T_TEXT] += 1
        else:
            self.types[classify(fv.items[0] if fv.items else "")] += 1
        if nonempty:
            self.filled += 1
        if fv.kind in ("block", "object"):
            return []
        return [n for n in (self.observe_value(x) for x in nonempty) if n]


def _is_image_value(value: str) -> bool:
    return any(m.group(1) == "!" or _is_image_target(m.group(2)) for m in _WIKILINK.finditer(value))


@dataclass
class TableGroup:
    header: tuple[str, ...]
    tables: int = 0
    rows: int = 0
    max_rows: int = 0
    notes: set[int] = field(default_factory=set)
    columns: list[FieldStat] = field(default_factory=list)
    id_image_rows: int = 0

    def add(self, rows: Sequence[Sequence[str]], note: int) -> list[str]:
        if not self.columns:
            self.columns = [FieldStat() for _ in self.header]
        self.tables += 1
        self.rows += len(rows)
        self.max_rows = max(self.max_rows, len(rows))
        self.notes.add(note)
        ids: list[str] = []
        for row in rows:
            row_has_id = row_has_image = False
            for idx, col in enumerate(self.columns):
                cell = row[idx] if idx < len(row) else ""
                norm = _observe_cell(col, cell)
                if norm:
                    ids.append(norm)
                    row_has_id = True
                if _is_image_value(cell) or classify(cell) == T_IMAGE:
                    row_has_image = True
            if row_has_id and row_has_image:
                self.id_image_rows += 1
        return ids


def _observe_cell(col: FieldStat, cell: str) -> str | None:
    col.present += 1
    kind = classify(cell)
    col.types[kind] += 1
    if kind != T_EMPTY:
        col.filled += 1
    return col.observe_value(cell)


@dataclass
class NoteRecord:
    top: str
    signature: tuple[str, ...]
    id_fields: frozenset[tuple[str, str]]
    has_image: bool
    image_matches_id: bool
    stem_idlike: bool
    tables: tuple[tuple[str, ...], ...]


@dataclass
class Survey:
    walk: WalkResult
    notes: list[NoteRecord] = field(default_factory=list)
    encodings: Counter[str] = field(default_factory=Counter)
    cut_notes: int = 0
    read_errors: int = 0
    outside: int = 0
    fm_notes: int = 0
    fm_malformed: int = 0
    fm: dict[str, FieldStat] = field(default_factory=dict)
    inline: dict[str, FieldStat] = field(default_factory=dict)
    inline_notes: int = 0
    tables: dict[tuple[str, ...], TableGroup] = field(default_factory=dict)
    heading_levels: Counter[int] = field(default_factory=Counter)
    heading_notes: Counter[str] = field(default_factory=Counter)
    code_blocks: Counter[str] = field(default_factory=Counter)
    inline_queries: int = 0
    template_markers: int = 0
    tags_inline: int = 0
    notes_with_tags: int = 0
    links: Counter[str] = field(default_factory=Counter)
    embeds_per_note: Counter[str] = field(default_factory=Counter)
    embed_targets: set[str] = field(default_factory=set)
    csv_files: list[tuple[str, TableGroup, str]] = field(default_factory=list)
    stem_stat: FieldStat = field(default_factory=FieldStat)
    image_stem_stat: FieldStat = field(default_factory=FieldStat)
    image_dir_stat: FieldStat = field(default_factory=FieldStat)


def _bucket(n: int) -> str:
    for hi, label in ((1, "1"), (3, "2–3"), (6, "4–6"), (10, "7–10")):
        if n <= hi:
            return label
    return "11+"


def analyse_note(sv: Survey, idx: int, entry: FileEntry, text: str) -> None:
    fm_lines, body, malformed = split_frontmatter(text)
    sv.template_markers += "{{" in text or "<%" in text
    sv.fm_malformed += malformed
    ids: set[str] = set()
    id_fields: set[tuple[str, str]] = set()
    sig: list[str] = []
    has_image = False
    image_names: list[str] = []

    if fm_lines is not None:
        sv.fm_notes += 1
        for key, fv in parse_frontmatter(fm_lines).items():
            label = ".".join(safe_label(part) for part in key.split("."))
            sig.append(label)
            found = sv.fm.setdefault(label, FieldStat()).observe(fv)
            if found:
                ids.update(found)
                id_fields.add(("frontmatter", label))
            for item in fv.items:
                for m in _WIKILINK.finditer(item):
                    sv.links["fm_link"] += 1
                    sv.embed_targets.add(_target_name(m.group(2)))
                    if _is_image_target(m.group(2)):
                        sv.links["fm_image"] += 1
                        has_image = True
                        image_names.append(_target_name(m.group(2)))

    fence = ""
    inline_seen: dict[str, list[str]] = {}
    headings: set[str] = set()
    table_sigs: list[tuple[str, ...]] = []
    image_embeds = 0
    tags = 0
    i = 0
    while i < len(body):
        line = body[i]
        fm = _FENCE.match(line)
        if fence:
            if fm and fm.group(1)[0] == fence[0] and len(fm.group(1)) >= len(fence):
                fence = ""
            i += 1
            continue
        if fm:
            fence = fm.group(1)
            if fm.group(2):
                lang = fm.group(2).lower()
                sv.code_blocks[lang if lang in KNOWN_CODE_LANGS else "(diğer)"] += 1
            i += 1
            continue
        if "|" in line and i + 1 < len(body) and _TABLE_SEP.match(body[i + 1]):
            header = tuple(safe_label(c) for c in split_cells(line))
            rows = []
            j = i + 2
            while j < len(body) and "|" in body[j] and body[j].strip():
                rows.append(split_cells(body[j]))
                j += 1
            group = sv.tables.setdefault(header, TableGroup(header))
            ids.update(group.add(rows, idx))
            table_sigs.append(header)
            for row in [line, *body[i + 2 : j]]:
                image_embeds += _count_links(sv, row, image_names, in_table=True)
            i = j
            continue
        hm = _HEADING.match(line)
        if hm:
            sv.heading_levels[len(hm.group(1))] += 1
            headings.add(" ".join(hm.group(2).split()))
            i += 1
            continue
        im = _INLINE_LINE.match(line)
        if im and "://" not in im.group(1):
            inline_seen.setdefault(safe_label(im.group(1).strip("*_ ")), []).append(im.group(2))
        for bm in _INLINE_BRACKET.finditer(line):
            inline_seen.setdefault(safe_label(bm.group(1).strip("*_ ")), []).append(bm.group(2))
        if "`=" in line or "`$=" in line:
            sv.inline_queries += 1
        tags += len(_TAG.findall(_WIKILINK.sub("", _MDLINK.sub("", line))))
        image_embeds += _count_links(sv, line, image_names, in_table=False)
        i += 1

    if inline_seen:
        sv.inline_notes += 1
    for key, values in inline_seen.items():
        sig.append(f"{key}::")
        stat_ = sv.inline.setdefault(key, FieldStat())
        kind = "list" if len(values) > 1 else "scalar"
        found = stat_.observe(FmValue(kind, values))
        if found:
            ids.update(found)
            id_fields.add(("satır içi", key))
    for h in headings:
        sv.heading_notes[h] += 1
    sv.tags_inline += tags
    sv.notes_with_tags += tags > 0
    if image_embeds:
        has_image = True
        sv.embeds_per_note[_bucket(image_embeds)] += 1
    stem = os.path.splitext(entry.rel[-1])[0]
    stem_norm = sv.stem_stat.observe_value(stem)
    if stem_norm:
        ids.add(stem_norm)
    long_ids = [x for x in ids if len(x) >= 5]
    matches = any(any(x in normalize_id(n) for x in long_ids) for n in image_names)
    sv.notes.append(
        NoteRecord(
            top=entry.rel[0] if len(entry.rel) > 1 else "",
            signature=tuple(sorted(sig)),
            id_fields=frozenset(id_fields),
            has_image=has_image,
            image_matches_id=matches,
            stem_idlike=stem_norm is not None,
            tables=tuple(table_sigs),
        )
    )


def _target_name(target: str) -> str:
    name = target.split("|", 1)[0].split("#", 1)[0].strip().replace("\\", "/")
    return name.rsplit("/", 1)[-1].lower()


def _count_links(sv: Survey, line: str, image_names: list[str], *, in_table: bool) -> int:
    images = 0
    for m in _WIKILINK.finditer(line):
        target = m.group(2)
        name = _target_name(target)
        if m.group(1):
            sv.embed_targets.add(name)
            if _is_image_target(target):
                images += 1
                image_names.append(name)
                sv.links["image_embed_table" if in_table else "image_embed_body"] += 1
            else:
                sv.links["other_embed"] += 1
        else:
            sv.links["wikilink"] += 1
            sv.links["alias"] += "|" in target
            sv.links["heading_link"] += "#" in target
            sv.embed_targets.add(name if "." in name else name + ".md")
    for m in _MDLINK.finditer(line):
        target = m.group(2)
        if re.match(r"^[a-z]+://", target, re.IGNORECASE):
            sv.links["url_link"] += 1
            continue
        name = _target_name(target.replace("%20", " "))
        sv.embed_targets.add(name)
        if m.group(1) and _is_image_target(target):
            images += 1
            image_names.append(name)
            sv.links["image_embed_md"] += 1
        else:
            sv.links["md_local_link"] += 1
    return images


def analyse_csv(sv: Survey, entry: FileEntry, text: str) -> None:
    first = text.split("\n", 1)[0]
    delim = max((",", ";", "\t"), key=first.count)
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    if not rows:
        return
    header = tuple(safe_label(c) for c in rows[0])
    group = TableGroup(header)
    group.add(rows[1:], -1)
    sv.csv_files.append(("sekme" if delim == "\t" else delim, group, _parent_key(entry)))


def _parent_key(entry: FileEntry) -> str:
    return "/".join(entry.rel[:-1])


def survey_vault(
    root_real: str, *, max_files: int, max_note_bytes: int, progress: Progress
) -> Survey:
    walk = walk_vault(root_real, max_files, progress)
    sv = Survey(walk=walk)
    readable = [f for f in walk.files if f.ext in (".md", ".csv")]
    for n, entry in enumerate(readable, 1):
        progress.tick("okunuyor", n, len(readable))
        if not is_inside(root_real, entry.path):
            sv.outside += 1
            continue
        try:
            text, enc, cut = read_text(entry.path, max_note_bytes)
        except OSError:
            sv.read_errors += 1
            continue
        sv.encodings[enc] += 1
        sv.cut_notes += cut
        if entry.ext == ".md":
            analyse_note(sv, len(sv.notes), entry, text)
        else:
            analyse_csv(sv, entry, text)
    for f in walk.files:
        if f.ext in IMAGE_EXTS:
            sv.image_stem_stat.observe_value(os.path.splitext(f.rel[-1])[0])
            if len(f.rel) > 1:
                sv.image_dir_stat.observe_value(f.rel[-2])
    progress.tick("okunuyor", len(readable), len(readable), force=True)
    return sv


# --------------------------------------------------------------------------------------------
# Report (Turkish Markdown). Only names that passed ``safe_label``/``Labeler``, counts, ratios,
# types and shapes are written.
# --------------------------------------------------------------------------------------------


def pct(a: int, b: int) -> str:
    return f"%{round(100 * a / b)}" if b else "—"


def _types(c: Counter[str], total: int) -> str:
    return ", ".join(f"{k} {pct(v, total)}" for k, v in c.most_common(3)) or "—"


def _shapes(c: Counter[str], total: int) -> str:
    return ", ".join(f"`{k}` {pct(v, total)}" for k, v in c.most_common(3)) or "—"


class Labeler:
    """Folder / heading names, optionally replaced by salted hashes (``--redact-names``)."""

    def __init__(self, redact: bool) -> None:
        self.redact = redact
        self.salt = secrets.token_bytes(16)

    def __call__(self, name: str, prefix: str = "K") -> str:
        if not self.redact:
            return safe_label(name)
        digest = hashlib.sha256(self.salt + name.encode("utf-8")).hexdigest()[:6]
        return f"{prefix}-{digest}"


@dataclass(frozen=True)
class Options:
    depth: int = DEFAULT_DEPTH
    max_children: int = DEFAULT_MAX_CHILDREN
    min_heading_notes: int = DEFAULT_MIN_HEADING_NOTES
    redact_names: bool = False
    max_files: int = DEFAULT_MAX_FILES
    max_note_bytes: int = DEFAULT_MAX_NOTE_BYTES


def _tree(sv: Survey, opts: Options, label: Labeler) -> list[str]:
    dirs = sv.walk.dirs
    tot_md: dict[tuple[str, ...], int] = {}
    tot_other: dict[tuple[str, ...], int] = {}
    for rel in sorted(dirs, key=len, reverse=True):
        d = dirs[rel]
        tot_md[rel] = d.md_direct + sum(tot_md[(*rel, c)] for c in d.children)
        tot_other[rel] = d.other_direct + sum(tot_other[(*rel, c)] for c in d.children)

    lines = ["```text"]

    def walk(rel: tuple[str, ...], depth: int) -> None:
        d = dirs[rel]
        name = "(kasa kökü)" if not rel else label(rel[-1]) + "/"
        info = f"{d.md_direct} not burada, toplam {tot_md[rel]} not, {tot_other[rel]} ek dosya"
        kids = sorted(d.children, key=lambda c: (-tot_md[(*rel, c)], c))
        if kids and depth >= opts.depth:
            info += f", {len(kids)} alt klasör (derinlik sınırı)"
        lines.append(f"{'  ' * depth}{name}  — {info}")
        if depth >= opts.depth:
            return
        for c in kids[: opts.max_children]:
            walk((*rel, c), depth + 1)
        rest = kids[opts.max_children :]
        if rest:
            n = sum(tot_md[(*rel, c)] for c in rest)
            lines.append(f"{'  ' * (depth + 1)}… ve {len(rest)} klasör daha (toplam {n} not)")

    walk((), 0)
    lines.append("```")
    return lines


SIZE_BUCKETS: tuple[tuple[int, str], ...] = (
    (100_000, "<100 KB"),
    (1_000_000, "100 KB–1 MB"),
    (5_000_000, "1–5 MB"),
    (20_000_000, "5–20 MB"),
)


def _size_bucket(size: int) -> str:
    for hi, lab in SIZE_BUCKETS:
        if size < hi:
            return lab
    return ">20 MB"


def _ext_label(ext: str) -> str:
    if not ext:
        return "(uzantısız)"
    return ext if re.fullmatch(r"\.[a-z0-9]{1,8}", ext) else "(diğer)"


def _field_table(fields: dict[str, FieldStat], base: int, base_name: str) -> list[str]:
    lines = [
        f"| Anahtar | Not sayısı | Kapsama ({base_name}) | Doluluk | Tür dağılımı |",
        "|---|---|---|---|---|",
    ]
    for key, st in sorted(fields.items(), key=lambda kv: (-kv[1].present, kv[0])):
        types = _types(st.types, st.present)
        if st.item_types:
            types += f" (öğeler: {_types(st.item_types, sum(st.item_types.values()))})"
        lines.append(
            f"| `{md_cell(key)}` | {st.present} | {pct(st.present, base)} | "
            f"{pct(st.filled, st.present)} | {types} |"
        )
    return lines


def _id_candidates(sv: Survey) -> list[tuple[str, str, FieldStat]]:
    sources: list[tuple[str, str, FieldStat]] = [("frontmatter", k, s) for k, s in sv.fm.items()]
    sources += [("satır içi", k, s) for k, s in sv.inline.items()]
    for n, g in enumerate(sv.tables.values(), 1):
        sources += [(f"tablo Tb{n}", h, c) for h, c in zip(g.header, g.columns, strict=False)]
    for n, (_, g, _) in enumerate(sv.csv_files, 1):
        sources += [(f"CSV-{n}", h, c) for h, c in zip(g.header, g.columns, strict=False)]
    sources += [
        ("dosya adı", "(not dosyası adı)", sv.stem_stat),
        ("dosya adı", "(görsel dosyası adı)", sv.image_stem_stat),
        ("klasör adı", "(görselin klasörü)", sv.image_dir_stat),
    ]
    out = []
    for src, key, st in sources:
        if not st.values:
            continue
        share = st.idlike / st.values
        hint = any(h in key.lower() for h in ID_NAME_HINTS)
        if share >= 0.5 or (hint and share >= 0.2):
            out.append((src, key, st))
    return sorted(out, key=lambda t: -t[2].idlike)


def render_report(sv: Survey, opts: Options, label: Labeler) -> str:
    w = sv.walk
    notes = len(sv.notes)
    files = len(w.files)
    r: list[str] = []
    add = r.append
    add("# Obsidian kasası yapı raporu (anonim)")
    add("")
    add(
        "> **Bu rapor hiçbir değer içermez:** fiyat, adet, parça/OEM numarası, ürün adı, dosya "
        "adı, not içeriği ve kasanın yolu yoktur. Yalnızca klasör adları"
        + (" (karmalanmış)" if opts.redact_names else "")
        + ", alan/sütun adları, türler, sayılar, oranlar ve değerlerin *biçimi* (ör. "
        "`A###-###-##-##`: A = Latin harf, Я = Kiril harf, # = rakam) vardır. Sohbete "
        "yapıştırmak güvenlidir; yine de göndermeden önce bir göz atın."
    )
    add("")
    add(
        f"Oluşturulma: {datetime.now(UTC):%Y-%m-%d} (UTC) · vault_survey sürüm {REPORT_VERSION}"
        " · kasa salt okunur tarandı"
    )
    add("")
    add("## 1. Genel özet")
    add("")
    add(f"- Taranan dosya: {files} (not: {notes}, CSV: {len(sv.csv_files)})")
    add(f"- Klasör: {len(w.dirs)}")
    if w.truncated:
        add(
            f"- **Dosya sınırına ulaşıldı ({opts.max_files}); rapor KISMİ.** `--max-files` artırın."
        )
    add(f"- Frontmatter (Properties) olan not: {sv.fm_notes} ({pct(sv.fm_notes, notes)})")
    add(
        f"- Satır içi alan (`anahtar:: değer`) olan not: {sv.inline_notes} "
        f"({pct(sv.inline_notes, notes)})"
    )
    with_img = sum(n.has_image for n in sv.notes)
    add(f"- Görsel gömen not: {with_img} ({pct(with_img, notes)})")
    add(f"- Tablo biçimi (farklı başlık dizisi): {len(sv.tables)}")
    enc = ", ".join(f"{k}: {v}" for k, v in sorted(sv.encodings.items())) or "—"
    add(f"- Karakter kodlaması (okunan not/CSV): {enc}")
    add(
        "- Obsidian ayar klasörü (`.obsidian`) var mı: "
        f"{'evet' if w.hidden_dirs['.obsidian'] else 'hayır'} (içine girilmedi)"
    )
    add("")

    add("## 2. Klasör ağacı")
    add("")
    add(f"Derinlik sınırı: {opts.depth}. Sayılar alt klasörleri de kapsar (toplam).")
    add("")
    r.extend(_tree(sv, opts, label))
    add("")

    add("## 3. Ekler (not dışı dosyalar)")
    add("")
    exts: dict[str, Counter[str]] = {}
    for f in w.files:
        if f.ext != ".md":
            exts.setdefault(_ext_label(f.ext), Counter())[_size_bucket(f.size)] += 1
    if exts:
        add("| Uzantı | Adet | Boyut dağılımı |")
        add("|---|---|---|")
        for ext, c in sorted(exts.items(), key=lambda kv: -sum(kv[1].values())):
            sizes = ", ".join(f"{k}: {v}" for k, v in c.most_common())
            add(f"| `{ext}` | {sum(c.values())} | {sizes} |")
    else:
        add("Ek dosya yok.")
    img_dirs: Counter[str] = Counter()
    for f in w.files:
        if f.ext in IMAGE_EXTS:
            parts = f.rel[:-1][: opts.depth]
            key = "/".join(label(p) for p in parts) or "(kasa kökü)"
            img_dirs[key + ("/…" if len(f.rel) - 1 > opts.depth else "")] += 1
    if img_dirs:
        add("")
        add("Görsellerin bulunduğu klasörler (en çok 8):")
        add("")
        for k, v in img_dirs.most_common(8):
            add(f"- `{md_cell(k)}`: {v}")
    add("")

    add("## 4. Frontmatter (Properties) anahtarları")
    add("")
    if sv.fm:
        add(
            "Kapsama: anahtarın bulunduğu not / frontmatter'lı not. Doluluk: değeri boş olmayan "
            "/ anahtarın bulunduğu not. `ebeveyn.alt` = iç içe anahtar."
        )
        add("")
        r.extend(_field_table(sv.fm, sv.fm_notes, "frontmatter'lı notlar"))
    else:
        add("Frontmatter bulunamadı.")
    if sv.fm_malformed:
        add("")
        add(f"Kapanmamış frontmatter (yok sayıldı): {sv.fm_malformed} not.")
    add("")

    add("## 5. Satır içi alanlar (Dataview `anahtar:: değer`)")
    add("")
    if sv.inline:
        r.extend(_field_table(sv.inline, notes, "tüm notlar"))
    else:
        add("Satır içi alan bulunamadı.")
    add("")

    add("## 6. Şablon grupları (aynı anahtar kümesine sahip notlar)")
    add("")
    groups = Counter(n.signature for n in sv.notes)
    table_ids = {h: f"Tb{i}" for i, h in enumerate(sv.tables, 1)}
    shown = [(s, c) for s, c in groups.most_common(12) if c >= 2]
    if shown:
        add("`::` ile biten anahtarlar satır içi alandır.")
        add("")
        add("| Grup | Not | Pay | Anahtarlar | Üst klasörler | Görselli | Tablolar |")
        add("|---|---|---|---|---|---|---|")
        for n, (sig, count) in enumerate(shown, 1):
            members = [x for x in sv.notes if x.signature == sig]
            keys = ", ".join(f"`{md_cell(k)}`" for k in sig[:20]) or "(anahtar yok)"
            if len(sig) > 20:
                keys += f" … (+{len(sig) - 20})"
            tops = Counter(label(x.top) if x.top else "(kök)" for x in members)
            top_s = ", ".join(f"{md_cell(k)} ({v})" for k, v in tops.most_common(3))
            tabs = Counter(table_ids[t] for x in members for t in x.tables)
            tab_s = ", ".join(f"{k}×{v}" for k, v in tabs.most_common(4)) or "—"
            img = pct(sum(x.has_image for x in members), count)
            add(f"| Ş{n} | {count} | {pct(count, notes)} | {keys} | {top_s} | {img} | {tab_s} |")
        covered = sum(c for _, c in groups.most_common(3))
        add("")
        add(
            f"En büyük 3 grup notların {pct(covered, notes)}'ini kapsıyor; tek başına kalan "
            f"anahtar kümesi: {sum(1 for c in groups.values() if c == 1)}."
        )
    else:
        add("Tekrarlanan anahtar kümesi yok (şablon kullanımı görünmüyor).")
    add(f"Şablon işaretleri (`{{{{…}}}}` / Templater `<%`) içeren not: {sv.template_markers}.")
    add("")

    add("## 7. Başlıklar ve tablolar")
    add("")
    levels = ", ".join(f"H{k}: {v}" for k, v in sorted(sv.heading_levels.items())) or "—"
    add(f"Başlık seviyeleri: {levels}")
    min_h = opts.min_heading_notes
    common = [(t, k) for t, k in sv.heading_notes.most_common(25) if k >= min_h]
    hidden = sum(1 for k in sv.heading_notes.values() if k < min_h)
    if common:
        add("")
        add(f"En az {opts.min_heading_notes} notta tekrar eden başlıklar (şablon bölümleri):")
        add("")
        for heading, cnt in common:
            add(f"- `{md_cell(label(heading, 'B'))}`: {cnt} not")
    add("")
    add(f"Daha az tekrar eden {hidden} farklı başlık gösterilmedi (değer içerebilir).")
    add("")
    if sv.tables:
        add(
            "| Tablo | Adet | Not | Satır (toplam / en çok) | Görsel+kod aynı satırda "
            "| Sütunlar (tür, doluluk) |"
        )
        add("|---|---|---|---|---|---|")
        for hdr, g in sv.tables.items():
            cols = "; ".join(
                f"`{md_cell(name)}`: {_types(c.types, c.present)}, dolu {pct(c.filled, c.present)}"
                for name, c in zip(hdr, g.columns, strict=False)
            )
            add(
                f"| {table_ids[hdr]} | {g.tables} | {len(g.notes)} | {g.rows} / {g.max_rows} | "
                f"{g.id_image_rows} | {cols} |"
            )
    else:
        add("Markdown tablosu yok.")
    add("")

    add("## 8. Bağlantılar ve gömülü görseller")
    add("")
    lk = sv.links
    img_total = lk["image_embed_body"] + lk["image_embed_table"] + lk["image_embed_md"]
    add(
        f"- Wikilink `[[…]]`: {lk['wikilink']} (takma adlı: {lk['alias']}, "
        f"başlığa: {lk['heading_link']})"
    )
    add(
        f"- Görsel gömme: {img_total} (metinde `![[…]]`: {lk['image_embed_body']}, "
        f"tabloda: {lk['image_embed_table']}, Markdown `![](…)`: {lk['image_embed_md']})"
    )
    add(f"- Frontmatter'da bağlantı: {lk['fm_link']} (görsele: {lk['fm_image']})")
    add(
        f"- Diğer gömmeler (not/PDF vb.): {lk['other_embed']}; yerel Markdown bağlantısı: "
        f"{lk['md_local_link']}; web bağlantısı: {lk['url_link']}"
    )
    per = ", ".join(f"{k}: {v}" for k, v in sorted(sv.embeds_per_note.items()))
    add(f"- Not başına görsel gömme (not sayısı): {per or '—'}")
    names = {f.rel[-1].lower() for f in w.files}
    images = [f for f in w.files if f.ext in IMAGE_EXTS]
    used = sum(f.rel[-1].lower() in sv.embed_targets for f in images)
    add(
        f"- Herhangi bir notta geçen görsel dosyası: {used} / {len(images)} "
        f"({pct(used, len(images))})"
    )
    targets = [t for t in sv.embed_targets if os.path.splitext(t)[1].lower() in IMAGE_EXTS]
    missing = sum(t not in names for t in targets)
    add(f"- Kasada bulunamayan görsel hedefi: {missing} / {len(targets)}")
    add("")
    add("**Görseller ve kimlik alanı ilişkisi**")
    add("")
    cand = _id_candidates(sv)
    cand_keys = {(src, key) for src, key, _ in cand}
    img_notes = [n for n in sv.notes if n.has_image]
    near = sum(bool(n.id_fields & cand_keys) for n in img_notes)
    add(
        "- Görsel gömen notlardan kimlik adayı alan (frontmatter/satır içi) içeren: "
        f"{near} / {len(img_notes)} ({pct(near, len(img_notes))})"
    )
    stem_id = sum(n.stem_idlike for n in img_notes)
    add(
        f"- Görsel gömen notlardan dosya adı kod biçimli olan: {stem_id} / {len(img_notes)} "
        f"({pct(stem_id, len(img_notes))})"
    )
    match = sum(n.image_matches_id for n in img_notes)
    add(
        f"- Görsel adı notun kendi kodunu içeren not: {match} / {len(img_notes)} "
        f"({pct(match, len(img_notes))})"
    )
    add(
        "- Tablo satırında kod ve görsel birlikte: "
        f"{sum(g.id_image_rows for g in sv.tables.values())} satır"
    )
    add("")

    add("## 9. Aday kimlik alanları (SKU/OEM biçimli değerler)")
    add("")
    if cand:
        add(
            "Yalnızca biçim gösterilir, değer asla gösterilmez. "
            "Benzersizlik: farklı kod / kod biçimli değer."
        )
        add("")
        add("| Kaynak | Alan | Değer | Kod biçimli | Benzersizlik | En sık biçimler |")
        add("|---|---|---|---|---|---|")
        for src, key, st in cand:
            add(
                f"| {src} | `{md_cell(key)}` | {st.values} | {pct(st.idlike, st.values)} | "
                f"{pct(len(st.distinct), st.idlike)} | {_shapes(st.shapes, st.idlike)} |"
            )
    else:
        add("Kod biçimli değer taşıyan alan bulunamadı.")
    add("")

    add("## 10. Dataview / Bases / CSV / Canvas ipuçları")
    add("")
    count_ext = Counter(f.ext for f in w.files)
    add(
        f"- `.csv`: {count_ext['.csv']}, `.base` (Bases): {count_ext['.base']}, "
        f"`.canvas`: {count_ext['.canvas']}"
    )
    office = sum(count_ext[e] for e in (".xlsx", ".xls", ".ods"))
    add(f"- Tablo dosyası (`.xlsx`/`.xls`/`.ods`): {office}")
    blocks = ", ".join(f"`{md_cell(safe_label(k))}`: {v}" for k, v in sv.code_blocks.most_common(8))
    add(f"- Kod blokları (dile göre): {blocks or '—'}")
    add(f"- Satır içi Dataview sorgusu (`` `= `` / `` `$= ``): {sv.inline_queries}")
    add(
        f"- Etiket (#etiket) kullanımı: {sv.tags_inline} etiket, {sv.notes_with_tags} not "
        "(etiket adları gösterilmez)"
    )
    for n, (delim, g, _) in enumerate(sv.csv_files[:10], 1):
        cols = "; ".join(
            f"`{md_cell(h)}`: {_types(c.types, c.present)}"
            for h, c in zip(g.header, g.columns, strict=False)
        )
        add(f"- CSV-{n}: ayraç `{delim}`, {g.rows} veri satırı, sütunlar: {cols}")
    add("")

    add("## 11. Atlananlar ve uyarılar")
    add("")
    add(f"- İzlenmeyen kısayol/sembolik bağlantı/junction: {w.skipped_links}")
    hidden_s = ", ".join(f"`{k}`: {v}" for k, v in sorted(w.hidden_dirs.items())) or "—"
    add(f"- Girilmeyen gizli klasörler: {hidden_s}; gizli dosya: {w.hidden_files}")
    add(f"- Okuma hatası: {sv.read_errors + w.errors}; kasa dışına çıkan yol: {sv.outside}")
    add(
        f"- Boyut sınırı ({opts.max_note_bytes} bayt) nedeniyle kısmen okunan dosya: {sv.cut_notes}"
    )
    add(
        f"- Derinlik sınırı ({MAX_WALK_DEPTH}) aşan klasör: {w.too_deep}; "
        f"özel dosya: {w.special_files}"
    )
    add("")
    return "\n".join(r)


# --------------------------------------------------------------------------------------------
# CLI.
# --------------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Obsidian kasasının salt okunur, anonim yapı raporu (değer içermez)."
    )
    p.add_argument("vault", help='Kasa klasörünün yolu (ör. "C:\\Users\\...\\Kasa")')
    p.add_argument("--out", help="Raporu bu dosyaya yaz (kasanın DIŞINDA olmalı)")
    p.add_argument("--depth", type=int, default=DEFAULT_DEPTH, help="Klasör ağacı derinliği")
    p.add_argument("--max-children", type=int, default=DEFAULT_MAX_CHILDREN)
    p.add_argument(
        "--max-files", type=int, default=DEFAULT_MAX_FILES, help="Taranacak en çok dosya"
    )
    p.add_argument("--max-note-bytes", type=int, default=DEFAULT_MAX_NOTE_BYTES)
    p.add_argument("--min-heading-notes", type=int, default=DEFAULT_MIN_HEADING_NOTES)
    p.add_argument("--redact-names", action="store_true", help="Klasör/başlık adlarını karmala")
    p.add_argument("--quiet", action="store_true", help="İlerleme göstergesini kapat")
    return p


def main(argv: Sequence[str] | None = None, *, stdout: TextIO | None = None) -> int:
    args = build_parser().parse_args(argv)
    err = sys.stderr
    root = os.path.abspath(os.path.expanduser(args.vault))
    if not os.path.isdir(root):
        err.write("Hata: kasa klasörü bulunamadı veya klasör değil.\n")
        return EXIT_USAGE
    root_real = os.path.realpath(root)
    out_path: str | None = None
    if args.out:
        out_path = os.path.abspath(os.path.expanduser(args.out))
        if is_inside(root_real, out_path) or is_inside(root_real, os.path.dirname(out_path)):
            err.write("Hata: --out kasanın içini gösteriyor. Raporu kasanın DIŞINA yazın.\n")
            return EXIT_USAGE
        if os.path.isdir(out_path):
            err.write("Hata: --out bir klasör; bir dosya adı verin.\n")
            return EXIT_USAGE
    if min(args.depth, args.max_children, args.max_files, args.max_note_bytes) < 1:
        err.write("Hata: sınırlar en az 1 olmalı.\n")
        return EXIT_USAGE
    opts = Options(
        depth=args.depth,
        max_children=args.max_children,
        min_heading_notes=args.min_heading_notes,
        redact_names=args.redact_names,
        max_files=args.max_files,
        max_note_bytes=args.max_note_bytes,
    )
    progress = Progress(not args.quiet, err)
    sv = survey_vault(
        root_real, max_files=opts.max_files, max_note_bytes=opts.max_note_bytes, progress=progress
    )
    progress.done()
    report = render_report(sv, opts, Labeler(opts.redact_names))
    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(report)
        err.write(f"Rapor yazıldı: {out_path}\n")
        return EXIT_OK
    stream = stdout or sys.stdout
    reconfigure: Callable[..., object] | None = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        with contextlib.suppress(OSError, ValueError):
            reconfigure(encoding="utf-8")
    stream.write(report)
    stream.flush()
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

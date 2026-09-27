# SYNTHETIC: every vault used here (tests/fixtures/synthetic_vault and generated ones) is made up.
"""scripts/vault_survey.py (T-043): read-only, skips .obsidian and links, never prints values."""

from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from app.config import REPO_ROOT
from scripts import vault_survey as vs

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "synthetic_vault" / "vault"
OBSIDIAN_MARKER = "OBSMARKER7781"
OUTSIDE_MARKER = "OUTSIDEMARKER4417"
CP1251_NOTE = Path("Запчасти", "Фары", "SYN-LMP-0002.md")
IMAGES = ("SYN-BMP-0001-1.jpg", "SYN-BMP-0002-1.jpg", "SYN-LMP-0001-1.jpg", "SYN-GRL-0001-1.jpg")


def build_vault(tmp_path: Path) -> tuple[Path, bool]:
    """Copy the fixture and add what is never committed: .obsidian/, placeholder images and
    symlinks pointing outside the vault. Returns (vault, symlinks_created)."""
    vault = tmp_path / "vault"
    shutil.copytree(FIXTURE, vault)
    # Committed as UTF-8 (ruff reads .md files); the vault copy gets the cp1251 bytes.
    cp = vault / CP1251_NOTE
    cp.write_bytes(cp.read_text(encoding="utf-8").encode("cp1251"))
    obs = vault / ".obsidian"
    obs.mkdir()
    (obs / "app.json").write_text(f'{{"gizliAyar": "{OBSIDIAN_MARKER}"}}', encoding="utf-8")
    (obs / "ayar.md").write_text(
        f"---\nobsidianGizliAnahtar: {OBSIDIAN_MARKER}\n---\n", encoding="utf-8"
    )
    att = vault / "Вложения"
    att.mkdir()
    for name in IMAGES:
        (att / name).write_bytes(b"SYNTHETIC placeholder, not an image")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text(
        f"---\ndisariGizliAnahtar: {OUTSIDE_MARKER}\n---\n# {OUTSIDE_MARKER}\n", encoding="utf-8"
    )
    try:
        os.symlink(outside, vault / "Внешнее", target_is_directory=True)
        os.symlink(outside / "secret.md", vault / "Склад" / "утечка.md")
    except (OSError, NotImplementedError):
        return vault, False
    return vault, True


def run(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    code = vs.main([*argv, "--quiet"], stdout=buf)
    return code, buf.getvalue()


def snapshot(root: Path) -> dict[str, tuple[Any, ...]]:
    out: dict[str, tuple[Any, ...]] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in dirnames + filenames:
            p = Path(dirpath) / name
            st = p.lstat()
            digest = ""
            if p.is_file() and not p.is_symlink():
                digest = hashlib.sha256(p.read_bytes()).hexdigest()
            out[str(p.relative_to(root))] = (p.is_symlink(), st.st_size, st.st_mtime_ns, digest)
    return out


# ------------------------------------------------------------------------------------------
# Read-only guarantees
# ------------------------------------------------------------------------------------------


def test_tree_and_mtimes_unchanged(tmp_path: Path) -> None:
    vault, _ = build_vault(tmp_path)
    before = snapshot(tmp_path)
    code, report = run([str(vault)])
    assert code == 0 and report
    assert snapshot(tmp_path) == before


def test_opens_read_only_and_never_enters_obsidian_or_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, linked = build_vault(tmp_path)
    opened: list[tuple[str, str]] = []
    scanned: list[str] = []
    real_open, real_scandir = open, os.scandir

    def spy_open(path: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        opened.append((str(path), mode))
        return real_open(path, mode, *args, **kwargs)

    def spy_scandir(path: Any = ".") -> Any:
        scanned.append(str(path))
        return real_scandir(path)

    monkeypatch.setattr(vs, "open", spy_open, raising=False)
    monkeypatch.setattr(vs.os, "scandir", spy_scandir)
    code, report = run([str(vault)])
    assert code == 0
    assert opened, "notes should have been read"
    assert {mode for _, mode in opened} == {"rb"}
    vault_real = os.path.realpath(vault)
    for path in [p for p, _ in opened] + scanned:
        assert ".obsidian" not in Path(path).parts
        assert "outside" not in Path(path).parts
        assert os.path.realpath(path).startswith(vault_real)
    assert OBSIDIAN_MARKER not in report and "obsidianGizliAnahtar" not in report
    assert OUTSIDE_MARKER not in report and "disariGizliAnahtar" not in report
    assert "`.obsidian`: 1" in report
    if linked:
        assert "İzlenmeyen kısayol/sembolik bağlantı/junction: 2" in report


def test_out_inside_vault_is_refused(tmp_path: Path) -> None:
    vault, _ = build_vault(tmp_path)
    before = snapshot(vault)
    for target in (vault / "rapor.md", vault / "Склад" / "rapor.md"):
        code, report = run([str(vault), "--out", str(target)])
        assert code == vs.EXIT_USAGE and report == ""
        assert not target.exists()
    assert snapshot(vault) == before


def test_out_outside_vault_writes_file(tmp_path: Path) -> None:
    vault, _ = build_vault(tmp_path)
    out = tmp_path / "rapor.md"
    code, stdout = run([str(vault), "--out", str(out)])
    assert code == 0 and stdout == ""
    assert out.read_text(encoding="utf-8").startswith("# Obsidian kasası yapı raporu (anonim)")


def test_missing_vault_is_usage_error(tmp_path: Path) -> None:
    assert run([str(tmp_path / "yok")])[0] == vs.EXIT_USAGE


# ------------------------------------------------------------------------------------------
# No values in the output
# ------------------------------------------------------------------------------------------


def fixture_values() -> set[str]:
    """Every value in the fixture, extracted independently of the script (min. 4 chars:
    shorter values such as quantities collide with the report's own counts)."""
    values: set[str] = set()
    for path in FIXTURE.rglob("*"):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1251")
        values.add(path.stem)
        lines = text.splitlines()
        for i, line in enumerate(lines):
            s = line.strip()
            header = i == 0 and path.suffix == ".csv"
            if header or (i + 1 < len(lines) and lines[i + 1].startswith("|---")):
                continue  # table/CSV header row: column names are structure, not values
            if s.startswith(("#", "---", "%%", "```", "|---")) and not s.startswith("# "):
                continue
            if s.startswith("# "):
                values.add(s[2:])
            elif s.startswith("|"):
                values.update(c.strip() for c in s.strip("|").split("|"))
            elif path.suffix == ".csv":
                values.update(s.split(";"))
            elif "::" in s:
                values.update(re.findall(r"::\s*([^\])]+)", s))
            elif s.startswith("- "):
                values.add(s[2:])
            elif ":" in s:
                values.add(s.split(":", 1)[1])
    cleaned: set[str] = set()
    for v in values:
        v = v.strip().strip("\"'[]!").strip()
        for part in [v, *re.split(r"[\[\]|,]+", v)]:
            part = part.strip().removesuffix(".jpg").removesuffix("-1").strip()
            if len(part) >= 4:
                cleaned.add(part)
    return cleaned


def test_no_fixture_value_appears_in_report(tmp_path: Path) -> None:
    vault, _ = build_vault(tmp_path)
    code, report = run([str(vault)])
    assert code == 0
    values = fixture_values()
    # Sanity: the extraction found the kinds of values we care about.
    for expected in ("SYN-BMP-0001", "48731", "Стеллаж Альфа", "SYN-DV-4242", "12345 ₽"):
        assert expected in values
    # Structural names that are allowed (key/column names and folder names) are not values.
    body = "\n".join(line for line in report.splitlines() if not line.startswith("Oluşturulma"))
    leaked = sorted(v for v in values if v in body)
    assert leaked == []
    assert str(vault) not in report and str(tmp_path) not in report


CANARY = "ZQXV"


def build_canary_vault(tmp_path: Path) -> Path:
    """Every value, file name, folder name and unique heading is a canary token."""
    vault = tmp_path / f"{CANARY}root"
    for n in range(4):
        folder = vault / f"{CANARY}dir{n}" / f"{CANARY}sub{n}"
        folder.mkdir(parents=True)
        (folder / f"{CANARY}img{n}.png").write_bytes(b"SYNTHETIC placeholder")
        c = f"{CANARY}{n}"
        note = f"""---
sku: {c}-000{n}
price: "{c}price"
list: [{c}a, "{c}b"]
block: |
  {c}block text
nested:
  inner: {c}nested
  {CANARY}12345: 3
tags:
  - {c}tag
photo: "[[{c}img{n}.png]]"
---
# {c} heading
## {c} unique section
Key:: {c}inline
Part [Oem:: {c}-777-{n}]
| Код | Фото |
|---|---|
| {c}-cell-{n}1 | ![[{c}img{n}.png]] |
#{c}hashtag
```{c}lang
{c} code
```
"""
        (folder / f"{CANARY}note{n}.md").write_text(note, encoding="utf-8")
    (vault / f"{CANARY}data.csv").write_text(f"a;b\n{CANARY}x;{CANARY}y\n", encoding="utf-8")
    return vault


def test_no_canary_appears_in_redacted_report(tmp_path: Path) -> None:
    vault = build_canary_vault(tmp_path)
    code, report = run([str(vault), "--redact-names", "--min-heading-notes", "2"])
    assert code == 0
    assert CANARY not in report.upper()
    assert "K-" in report  # folders are shown as salted hashes
    # Structure is still reported.
    assert "`sku`" in report and "`nested.inner`" in report and "`Oem`" in report
    assert "<değer benzeri ad: AAAA#####>" in report


def test_folder_names_shown_without_redaction(tmp_path: Path) -> None:
    vault, _ = build_vault(tmp_path)
    _, plain = run([str(vault)])
    _, redacted = run([str(vault), "--redact-names"])
    for name in ("Запчасти", "Бамперы", "Склад", "Шаблоны"):
        assert name in plain
    for name in ("Запчасти", "Бамперы", "Шаблоны", "Вложения", "Отчёты"):
        assert name not in redacted


# ------------------------------------------------------------------------------------------
# Report content on the fixture
# ------------------------------------------------------------------------------------------


def test_fixture_report_structure(tmp_path: Path) -> None:
    vault, _ = build_vault(tmp_path)
    code, report = run([str(vault)])
    assert code == 0
    assert "Bu rapor hiçbir değer içermez" in report
    # Encodings: one cp1251 note, one with BOM, both parsed like the others.
    assert "cp1251: 1" in report and "utf-8-bom: 1" in report
    assert "| `цена` | 6 | %100 | %83 | sayı %83, boş %17 |" in report
    assert "| `фото` | 6 | %100 | %83 | görsel %83, boş %17 |" in report
    assert "| `oem` | 6 | %100 | %83 | liste %100 (öğeler: kod %100) |" in report
    assert "`проверено`" in report and "tarih %83" in report
    # Inline fields, key names only.
    for key in ("`Артикул`", "`Цена`", "`Остаток`", "`Износ`", "`Цвет`"):
        assert key in report
    # Template group across the product notes and the template.
    assert re.search(r"\| Ş1 \| 6 \|", report)
    # Tables and CSV with column types.
    assert "`Цена`: para %100" in report and "`Кол-во`: sayı %100" in report
    assert "CSV-1: ayraç `;`, 2 veri satırı" in report
    # Identifier candidates by shape.
    assert "| frontmatter | `артикул` | 5 | %100 | %100 | `AAA-AAA-####` %100 |" in report
    assert "`AAA ### ### ####`" in report
    assert "(görsel dosyası adı)" in report
    # Images and links.
    assert "Görsel adı notun kendi kodunu içeren not: 6 / 6 (%100)" in report
    assert "- `.csv`: 1, `.base` (Bases): 1, `.canvas`: 1" in report
    assert "`dataview`: 1" in report
    assert "| `.jpg` | 4 | <100 KB: 4 |" in report
    assert "Шаблоны/  — 1 not burada" in report
    # Headings: template sections shown, unique titles hidden.
    assert "`Применимость`: 6 not" in report
    assert "Şablon işaretleri (`{{…}}` / Templater `<%`) içeren not: 1" in report


def test_max_files_cap_marks_report_partial(tmp_path: Path) -> None:
    vault, _ = build_vault(tmp_path)
    code, report = run([str(vault), "--max-files", "3"])
    assert code == 0
    assert "Dosya sınırına ulaşıldı (3); rapor KISMİ" in report
    assert "Taranan dosya: 3" in report


def test_progress_goes_to_stderr(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault, _ = build_vault(tmp_path)
    buf = io.StringIO()
    assert vs.main([str(vault)], stdout=buf) == 0
    err = capsys.readouterr().err
    assert "[vault_survey] okunuyor" in err
    assert "[vault_survey]" not in buf.getvalue()


# ------------------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("A2138851400", True),
        ("A 213 885 14 00", True),
        ("1K0-807-217", True),
        ("5G0 807 221 GRU", True),
        ("2138851400", True),
        ("48731", False),  # price-like
        ("2024-05-01", False),
        ("W213 бампер", False),
        ("Бампер", False),
        ("12 500", False),
    ],
)
def test_is_idlike(value: str, expected: bool) -> None:
    assert vs.is_idlike(value) is expected


def test_shape_and_safe_label() -> None:
    assert vs.shape("A 213 885-14 00") == "A ### ###-## ##"
    assert vs.shape("Ф12") == "Я##"
    assert vs.safe_label("цена") == "цена"
    assert vs.safe_label("A2138851400") == "<değer benzeri ad: A##########>"
    assert vs.safe_label("x" * 60) == "<uzun ad: 60 karakter>"
    assert vs.safe_label("http://example.com").startswith("<değer benzeri ad")


def test_classify() -> None:
    assert vs.classify("12345 ₽") == vs.T_MONEY
    assert vs.classify("12 500") == vs.T_NUMBER
    assert vs.classify("true") == vs.T_BOOL
    assert vs.classify("01.05.2024") == vs.T_DATE
    assert vs.classify('"[[a.jpg]]"') == vs.T_IMAGE
    assert vs.classify("[[Другая заметка]]") == vs.T_LINK
    assert vs.classify("") == vs.T_EMPTY


def test_parse_frontmatter_is_tolerant() -> None:
    lines = [
        "# comment",
        "a: 1",
        "b:",
        "  - x",
        "  - y",
        "c: [p, \"q, r\", '[[s|t]]']",
        "d: |",
        "  line one",
        "  line two",
        "e:",
        "  inner: 5",
        '"quoted key": v # trailing comment',
        "   stray indented line",
        "not a key line",
        "f: {g: 1, h: 2}",
    ]
    fm = vs.parse_frontmatter(lines)
    assert fm["a"] == vs.FmValue("scalar", ["1"])
    assert fm["b"] == vs.FmValue("list", ["x", "y"])
    assert fm["c"].kind == "list" and len(fm["c"].items) == 3
    assert fm["d"].kind == "block"
    assert fm["e"].kind == "object" and fm["e.inner"].items == ["5"]
    # Plain YAML scalars continue on indented lines; the trailing comment is dropped.
    assert fm["quoted key"].items == ["v stray indented line"]
    assert fm["f"].kind == "object" and "f.g" in fm and "f.h" in fm


def test_read_text_encodings(tmp_path: Path) -> None:
    samples = {
        "bom.md": (b"\xef\xbb\xbf" + "цена: 1".encode(), "utf-8-bom"),
        "cp.md": ("цена: 1".encode("cp1251"), "cp1251"),
        "u8.md": ("цена: 1".encode(), "utf-8"),
    }
    for name, (data, enc) in samples.items():
        (tmp_path / name).write_bytes(data)
        text, got, cut = vs.read_text(str(tmp_path / name), 1000)
        assert (text, got, cut) == ("цена: 1", enc, False)
    text, _, cut = vs.read_text(str(tmp_path / "u8.md"), 4)
    assert cut and text == "це"


def test_is_inside_handles_other_drive_and_parent(tmp_path: Path) -> None:
    assert vs.is_inside(str(tmp_path), str(tmp_path / "a" / "b"))
    assert not vs.is_inside(str(tmp_path / "a"), str(tmp_path / "b"))
    assert not vs.is_inside(str(tmp_path / "a"), str(tmp_path / "a" / ".." / "b"))

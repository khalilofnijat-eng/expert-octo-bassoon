# SYNTHETIC: every text, number, handle and URL below (and in tests/fixtures/filter/) is invented
# test data taken from the T-032 review's reproduction scripts. No real customer data.
"""T-034 regression tests for the T-032 security review of the masker and the output filter.

Every reproduced input is a case in ``tests/fixtures/filter/t032_cases.json``: "deny" cases must
be denied, "allow" cases allowed; a case with an ``xfail`` reason is a documented limitation and
runs as a strict xfail.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from app.safety.filter import (
    FilterConfig,
    FilterContext,
    ReasonCode,
    check_parts,
)
from app.safety.literals import LiteralKind, literal_variants
from app.safety.masker import mask
from app.safety.normalize import mixed_script_spans, normalize, spaced_letter_spans

R = ReasonCode
FIXTURE = Path(__file__).parent / "fixtures" / "filter" / "t032_cases.json"
DATA: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
LIT: tuple[str, ...] = tuple(DATA["LIT"])
L_VARIANTS: tuple[str, ...] = tuple(
    variant for value, kind in DATA["L"] for variant in literal_variants(value, kind)
)


def _params() -> list[Any]:
    params = []
    counters: dict[str, int] = {}
    for case in DATA["cases"]:
        group = case["group"]
        counters[group] = counters.get(group, 0) + 1
        marks = []
        if "xfail" in case:
            marks.append(pytest.mark.xfail(reason=case["xfail"], strict=True))
        params.append(pytest.param(case, id=f"{group}-{counters[group]}", marks=marks))
    return params


@pytest.mark.parametrize("case", _params())
def test_t032_case(case: dict[str, Any]) -> None:
    literals = L_VARIANTS if case["literals"] == "L_VARIANTS" else LIT
    config = FilterConfig(url_allowlist=tuple(case.get("url_allowlist", ())))
    verdict = check_parts([case["text"]], allowed_literals=literals, config=config).parts[0]
    if case["expect"] == "deny":
        assert not verdict.allowed, case["text"]
    else:
        assert verdict.allowed, (case["text"], verdict.codes)


def test_fixture_is_complete() -> None:
    groups = {case["group"] for case in DATA["cases"]}
    assert len(DATA["cases"]) >= 690
    assert len(groups) == 13


# --- Reason codes for the key bypass families --------------------------------------------------


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("Позво​ните мне", R.OBFUSCATION),
        ("Cкидка", R.OBFUSCATION),  # Latin C
        ("З в о н и т е", R.OBFUSCATION),
        ("П-о-з-в-о-н-и-т-е", R.OBFUSCATION),
        ("Cкидка", R.PROMISE_DISCOUNT),  # folded to Cyrillic and still recognised
        ("WhаtsApp", R.CONTACT_CHANNEL),  # Cyrillic а, folded to Latin
        ("ｗｈａｔｓａｐｐ", R.CONTACT_CHANNEL),  # fullwidth
        ("Звоните ⁸ ⁹⁰⁰ ⁰⁰⁰ ⁰⁰ ⁰¹", R.CONTACT_PHONE),
        ("Итого ①⑤⓪⓪⓪ рэ", R.DIGITS_NOT_ALLOWED),
        ("Цена ٤٥٠٠", R.DIGITS_NOT_ALLOWED),
        ("ivan @ example.com", R.CONTACT_SOCIAL),
        ("ivan[at]example[dot]com", R.CONTACT_EMAIL),
        ("Каталог: syn-parts[.]ru", R.URL_NOT_ALLOWED),
        ("Каталог: syn-parts точка ру", R.URL_NOT_ALLOWED),
        ("Каталог: ftp://syn-parts.ru", R.URL_NOT_ALLOWED),
        ("Каталог: //syn-parts.ru", R.URL_NOT_ALLOWED),
        ("Каталог: syn-parts.xyz", R.URL_NOT_ALLOWED),
        ("дайте номер", R.CONTACT_REDIRECT),
        ("лучше напрямую", R.CONTACT_REDIRECT),
        ("давайте без авито", R.CONTACT_REDIRECT),
        ("наличными при встрече", R.PAYMENT_TERMS_UNCONFIRMED),
        ("картой при получении", R.PAYMENT_TERMS_UNCONFIRMED),
        ("С Б П", R.PAYMENT_OFF_PLATFORM),
        ("подойдёт", R.UNVERIFIED_FITMENT),
        ("на связи Иван", R.HUMAN_CLAIM),
        ("мой номер 8 9ОО ООО ОО О1", R.CONTACT_PHONE),
    ],
)
def test_reason_code(text: str, code: ReasonCode) -> None:
    assert code in check_parts([text]).parts[0].codes


# --- D-1 / D-2: invalid and invisible-only text ------------------------------------------------


@pytest.mark.parametrize("text", ["​", "⠀", "ㅤ", "\xad", "﻿", "​" * 3, "⁠"])
def test_invisible_only_part_is_empty_and_obfuscated(text: str) -> None:
    codes = set(check_parts([text]).parts[0].codes)
    assert codes == {R.EMPTY_PART, R.OBFUSCATION}


def test_lone_surrogate_is_invalid_text_without_exception() -> None:
    text = "Позвоните 8 900 000 00 01 \ud800"
    verdict = check_parts([text]).parts[0]
    assert R.INVALID_TEXT in verdict.codes
    assert R.CONTACT_PHONE in verdict.codes
    surrogate = next(f for f in verdict.findings if f.code is R.INVALID_TEXT)
    assert (surrogate.start, surrogate.end) == (len(text) - 1, len(text))


def test_control_character_is_invalid_text() -> None:
    assert R.INVALID_TEXT in check_parts(["Фара\x07 есть"]).parts[0].codes


def test_obfuscation_span_points_at_the_invisible_character() -> None:
    text = "Гаран​тия"
    verdict = check_parts([text]).parts[0]
    spans = {(f.start, f.end) for f in verdict.findings if f.code is R.OBFUSCATION}
    assert (5, 6) in spans
    warranty = next(f for f in verdict.findings if f.code is R.PROMISE_WARRANTY)
    assert text[warranty.start : warranty.end] == text  # the finding spans the hidden char


# --- D-e / O-4: input validation ---------------------------------------------------------------


@pytest.mark.parametrize("parts", [[None], [b"bytes"], [123], "W213", b"W213"])
def test_bad_parts_raise_type_error(parts: Any) -> None:
    with pytest.raises(TypeError):
        check_parts(parts)


@pytest.mark.parametrize("literals", ["2018", [2018], ["2018", None], b"2018"])
def test_bad_allowed_literals_raise_type_error(literals: Any) -> None:
    with pytest.raises(TypeError):
        check_parts(["2018"], allowed_literals=literals)


@pytest.mark.parametrize(
    ("spans", "error"),
    [
        ("Гарантия", TypeError),
        ((("x",),), TypeError),
        ((((0, "1"),),), TypeError),
        ((((0, True),),), TypeError),
        ((((0, 99),),), ValueError),
        ((((3, 3),),), ValueError),
        ((((0, 1),), ((0, 1),)), ValueError),  # more entries than parts
    ],
)
def test_bad_template_spans_raise(spans: Any, error: type[Exception]) -> None:
    with pytest.raises(error):
        check_parts(["Гарантия"], context=FilterContext(template_spans=spans))


def test_bad_url_allowlist_raises() -> None:
    with pytest.raises(TypeError):
        FilterConfig(url_allowlist="avito.ru")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        FilterConfig(url_allowlist=("avito.ru/path",))


def test_exception_messages_do_not_echo_the_text() -> None:
    with pytest.raises(TypeError) as info:
        check_parts(["Позвоните 8 900 000 00 01", 5])  # type: ignore[list-item]
    assert "900" not in str(info.value)


# --- O-5 / D-f: templates are spans, untrusted interpolation is never exempt -------------------


def test_customer_text_inside_a_template_block_is_not_exempt() -> None:
    customer = "скидка пятьдесят процентов и возврат денег гарантирован"
    prefix = "Вы выбрали: Фара W213. Комментарий: "
    block = f"{prefix}{customer}."
    spans = (((0, len(prefix)),),)  # only the constant words are code-owned
    codes = set(
        check_parts(
            [block], allowed_literals=("W213",), context=FilterContext(template_spans=spans)
        )
        .parts[0]
        .codes
    )
    assert {R.PROMISE_DISCOUNT, R.PROMISE_RETURN, R.PROMISE_WARRANTY, R.NUMBER_WORD} <= codes


def test_listing_title_inside_offer_block_is_not_exempt() -> None:
    title = "Фара W213 — гарантия 6 мес, торг"
    block = f"1) {title} — 15 000 ₽"
    spans = (((0, 3), (len(block) - len(" — 15 000 ₽"), len(block))),)
    verdict = check_parts(
        [block], allowed_literals=("15 000 ₽", "W213"), context=FilterContext(template_spans=spans)
    ).parts[0]
    assert {R.PROMISE_WARRANTY, R.PROMISE_DISCOUNT, R.DIGITS_NOT_ALLOWED} <= set(verdict.codes)


def test_completion_flag_covers_only_the_template_span() -> None:
    text = "Заказ оформлен. Также забронировал вторую фару."
    ctx = FilterContext(completion_confirmed=True, template_spans=(((0, 15),),))
    verdict = check_parts([text], context=ctx).parts[0]
    assert [text[f.start : f.end] for f in verdict.findings] == ["забронировал"]


def test_oem_literal_does_not_hide_contact_context() -> None:
    lit = ("83212365946",)
    assert (
        R.CONTACT_REDIRECT
        in check_parts(["Для связи: 83212365946"], allowed_literals=lit).parts[0].codes
    )
    assert (
        R.CONTACT_CHANNEL
        in check_parts(["Пишите в WA: 83212365946"], allowed_literals=lit).parts[0].codes
    )


@pytest.mark.xfail(
    reason="D-j: a literal is not tied to its meaning (year reused as price)", strict=True
)
def test_year_literal_reused_as_price() -> None:
    assert not check_parts(["Отдам за 2018, забирайте"], allowed_literals=("2018",)).allowed


# --- D-g: owner edit is fail-closed ------------------------------------------------------------


def test_owner_edit_with_contacts_is_not_allowed() -> None:
    result = check_parts(
        ["Мой телефон 8 900 000 00 01, предоплата на Сбер"],
        context=FilterContext(is_owner_edit=True),
    )
    assert not result.allowed
    assert result.overridable


# --- D-d / O-3: strict allowlisted URLs --------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://www.avito.ru/moskva/zapchasti/fara_w213",
        "https://m.avito.ru/x",
        "avito.ru/item",
        "https://avito.ru:443/item?context=abc",
    ],
)
def test_clean_allowlisted_url_passes(url: str) -> None:
    config = FilterConfig(url_allowlist=("avito.ru",))
    assert check_parts([f"Ссылка: {url}"], config=config).allowed


# --- D-k: part size is counted without encoding ------------------------------------------------


def test_combining_marks_count_toward_the_limit() -> None:
    assert R.PART_TOO_LONG in check_parts(["е́" * 600]).parts[0].codes


# --- Normalization layer (D-a) -----------------------------------------------------------------


def test_normalize_views_and_offsets() -> None:
    nt = normalize("Cкид​ка ⁸№")
    assert nt.text == "Cкидка 8№"
    assert nt.cyr == "Скидка 8№"
    assert nt.hidden == ((4, 5),)
    assert nt.to_original(0, 6) == (0, 7)
    assert nt.from_original(0, 7) == (0, 6)
    assert len(nt.text) == len(nt.cyr) == len(nt.lat) == len(nt.starts) == len(nt.ends)


def test_normalize_composes_decomposed_letters_and_drops_stress_marks() -> None:
    assert normalize("й").text == "й"
    assert normalize("позвони́те").text == "позвоните"


def test_mixed_script_and_spaced_letters() -> None:
    assert mixed_script_spans("Cкидка E-класс W213") == [(0, 6)]
    assert spaced_letter_spans("т е л е г а и в с") == [(0, 17)]
    assert spaced_letter_spans("и т.д. в т.ч.") == []


def test_masker_uses_the_normalization_layer() -> None:
    assert mask("Мой номер ⁸⁹⁰⁰⁰⁰⁰⁰⁰⁰¹").text == "Мой номер [PHONE_1]"


# --- D-j: literal variants ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "kind", "expected"),
    [
        ("15 000 ₽", LiteralKind.PRICE, {"15 000 ₽", "15000 ₽", "15 000₽", "15 000 руб."}),
        ("2 шт.", LiteralKind.QUANTITY, {"2 шт", "2 шт.", "2шт"}),
        ("E200", LiteralKind.MODEL, {"E200", "E 200"}),
        ("220d", LiteralKind.MODEL, {"220d", "220 d"}),
        ("205/55 R16", LiteralKind.TIRE, {"205/55 R16", "205/55R16"}),
        ("90915-10003", LiteralKind.OEM, {"90915-10003", "90915 10003", "9091510003"}),
        ("A2138851400", LiteralKind.OEM, {"A2138851400", "A 213 885 14 00"}),
        ("2.0", LiteralKind.ENGINE_VOLUME, {"2.0", "2,0"}),
        ("W213", LiteralKind.OTHER, {"W213"}),
    ],
)
def test_literal_variants(value: str, kind: LiteralKind, expected: set[str]) -> None:
    variants = literal_variants(value, kind)
    assert variants[0] == value
    assert expected <= set(variants)
    assert len(variants) == len(set(variants))


def test_literal_variants_unknown_format_returns_value_only() -> None:
    assert literal_variants("примерно пятнадцать", LiteralKind.PRICE) == ("примерно пятнадцать",)
    with pytest.raises(ValueError):
        literal_variants("1", "nonsense")


def test_trailing_punctuation_of_a_literal_is_ignored() -> None:
    assert check_parts(["Есть 2 шт, левая и правая"], allowed_literals=("2 шт.",)).allowed


# --- ReDoS: the review's pathological inputs ---------------------------------------------------

N = 20_000
PATHOLOGICAL = {
    "a*N": "a" * N,
    "a.*N": "a." * (N // 2),
    "a-*N": "a-" * (N // 2),
    "a.-": "a-a." * (N // 4),
    "dig": "1" * N,
    "dig sp": "1 " * (N // 2),
    "dig-": "1-" * (N // 2),
    "dig(": "1(" * (N // 2),
    "dig( )": "1 ( " * (N // 4),
    "email-ish": "a." * (N // 2) + "@",
    "email2": "a@" + "a-" * (N // 2),
    "email3": "a@a" + ".a" * (N // 2) + ".1",
    "@": "@" * N,
    "cyr": "я " * (N // 2),
    "дост": "доставим " * (N // 9),
    "дост2": "доставим" + " ," * (N // 2),
    "напиш": "напишите " * (N // 9),
    "{{": "{{" * (N // 2),
    "http": "http://" + "a" * N,
    "url-dots": ("ab-" * 20 + ".") * (N // 61),
    "vin": "A" * N,
    "plate": "А123ВС" * (N // 6),
    "urlnoTLD": "a" * 61 + "." + "b" * 61 + "." + "x" * N,
    "mixed": "Cкидка " * (N // 7),
    "spaced": "з в " * (N // 4),
    "zero-width": "а​" * (N // 2),
}


@pytest.mark.parametrize("text", list(PATHOLOGICAL.values()), ids=list(PATHOLOGICAL))
def test_no_redos_masker_and_filter(text: str) -> None:
    start = time.perf_counter()
    mask(text)
    assert time.perf_counter() - start < 0.5
    start = time.perf_counter()
    check_parts([text])
    assert time.perf_counter() - start < 0.5
    # Below the scan limit every pattern runs: 4000 characters is the largest fully scanned part.
    start = time.perf_counter()
    check_parts([text[:4000]])
    assert time.perf_counter() - start < 0.5

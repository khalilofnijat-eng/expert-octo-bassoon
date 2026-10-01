# SYNTHETIC: every text, number, handle and URL below (and in tests/fixtures/filter/) is invented
# test data taken from the T-032b verification scripts. No real customer data, no real business
# rules: the payment rule text is the Main Agent's canonical example (Y-8), not the owner's rule.
"""T-041 regression tests for the T-032b verification of the masker and the output filter.

Every reproduced input is a case in ``tests/fixtures/filter/t032b_cases.json``: "deny" cases must
be denied, "allow" cases allowed; a case with an ``xfail`` reason is a documented limitation or
decision and runs as a strict xfail.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from app.safety.filter import (
    HARD_BLOCK_CODES,
    FilterConfig,
    FilterContext,
    ReasonCode,
    SpanKind,
    TemplateSpan,
    check_parts,
)
from app.safety.masker import MAX_MASK_INPUT, MaskInputTooLong, mask
from app.safety.part_numbers import extract_part_number_candidates

R = ReasonCode
K = SpanKind
FIXTURE = Path(__file__).parent / "fixtures" / "filter" / "t032b_cases.json"
DATA: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
LIT: tuple[str, ...] = tuple(DATA["LIT"])


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
def test_t032b_case(case: dict[str, Any]) -> None:
    literals = tuple(case.get("literals", LIT))
    config = FilterConfig(url_allowlist=tuple(case.get("url_allowlist", ())))
    verdict = check_parts([case["text"]], allowed_literals=literals, config=config).parts[0]
    if case["expect"] == "deny":
        assert not verdict.allowed, case["text"]
    else:
        assert verdict.allowed, (case["text"], verdict.codes)


def test_fixture_is_complete() -> None:
    assert len(DATA["cases"]) >= 560


def one(text: str, spans: tuple[TemplateSpan, ...] = (), **kw: Any) -> set[ReasonCode]:
    lits = kw.pop("lits", ())
    config = kw.pop("config", None)
    ctx = FilterContext(template_spans=(spans,), **kw)
    return set(
        check_parts([text], allowed_literals=lits, context=ctx, config=config).parts[0].codes
    )


def span(text: str, fragment: str, kind: SpanKind) -> TemplateSpan:
    start = text.index(fragment)
    return TemplateSpan(kind, start, start + len(fragment))


# --- Y-8: typed spans and the owner's payment rule -----------------------------------------------

PAYMENT_RULE = (
    "Оплата: наличными при получении, по QR-коду (СБП), переводом на карту; "
    "для юрлиц — безналичный расчёт по счёту (+10%)."
)


def test_canonical_payment_rule_passes_inside_a_rule_payment_span() -> None:
    assert one(PAYMENT_RULE, (TemplateSpan(K.RULE_PAYMENT, 0, len(PAYMENT_RULE)),)) == set()


@pytest.mark.parametrize("kind", [k for k in SpanKind if k is not SpanKind.RULE_PAYMENT])
def test_canonical_payment_rule_is_denied_in_other_spans(kind: SpanKind) -> None:
    codes = one(PAYMENT_RULE, (TemplateSpan(kind, 0, len(PAYMENT_RULE)),))
    assert {R.PAYMENT_OFF_PLATFORM, R.PAYMENT_TERMS_OUTSIDE_RULE} <= codes


def test_canonical_payment_rule_is_denied_outside_a_span() -> None:
    codes = one(PAYMENT_RULE)
    assert {R.PAYMENT_OFF_PLATFORM, R.PAYMENT_TERMS_OUTSIDE_RULE, R.DIGITS_NOT_ALLOWED} <= codes


def test_payment_rule_with_phone_number_wording_is_denied() -> None:
    rule = "Принимаем оплату по СБП по номеру телефона."
    assert R.CONTACT_REDIRECT in one(rule, (TemplateSpan(K.RULE_PAYMENT, 0, len(rule)),))


def test_span_covering_everything_exempts_only_its_kind() -> None:
    text = (
        "Гарантия 1 год. Звоните 8 900 000 00 01. Предоплата на карту. Я менеджер. "
        "Заказ оформлен. Наличными при встрече."
    )
    codes = one(text, (TemplateSpan(K.RULE_GENERIC, 0, len(text)),), completion_confirmed=True)
    assert {
        R.CONTACT_PHONE,
        R.CONTACT_REDIRECT,
        R.PAYMENT_OFF_PLATFORM,
        R.HUMAN_CLAIM,
        R.COMPLETION_CLAIM,
        R.PAYMENT_TERMS_OUTSIDE_RULE,
    } <= codes
    assert R.PROMISE_WARRANTY not in codes


def test_promises_are_exempt_only_in_rule_generic_spans() -> None:
    text = "Гарантия 6 месяцев."
    assert one(text, (TemplateSpan(K.RULE_GENERIC, 0, len(text)),)) == set()
    assert R.PROMISE_WARRANTY in one(text, (TemplateSpan(K.OFFER, 0, len(text)),))
    assert R.PROMISE_WARRANTY in one(text, (TemplateSpan(K.RULE_PAYMENT, 0, len(text)),))


def test_completion_needs_confirmation_span_and_flag() -> None:
    text = "Заказ оформлен."
    confirmation = (TemplateSpan(K.CONFIRMATION, 0, len(text)),)
    generic = (TemplateSpan(K.RULE_GENERIC, 0, len(text)),)
    assert one(text, confirmation, completion_confirmed=True) == set()
    assert R.COMPLETION_CLAIM in one(text, confirmation)
    assert R.COMPLETION_CLAIM in one(text, generic, completion_confirmed=True)


@pytest.mark.parametrize("prefix", ["ﬁ ", "½ ", "㎏ ", "​", "е́"])
def test_span_offsets_survive_nfkc_expansion_before_the_span(prefix: str) -> None:
    rule = "Гарантия 6 месяцев."
    text = prefix + "Итого 15 000 ₽. " + rule + " Скидка 10%."
    verdict = check_parts(
        [text],
        allowed_literals=("15 000 ₽",),
        context=FilterContext(template_spans=((span(text, rule, K.RULE_GENERIC),),)),
    ).parts[0]
    inside = [f for f in verdict.findings if text.index(rule) <= f.start < text.index(" Скидка")]
    assert inside == []
    assert R.PROMISE_DISCOUNT in verdict.codes


def test_span_ending_inside_a_cluster_does_not_exempt() -> None:
    text = "Гарантия́ навсегда"
    assert R.PROMISE_WARRANTY in one(text, (TemplateSpan(K.RULE_GENERIC, 0, 8),))
    assert one(text, (TemplateSpan(K.RULE_GENERIC, 0, 9),)) == set()


def test_adjacent_spans_do_not_combine() -> None:
    spans = (TemplateSpan(K.RULE_GENERIC, 0, 4), TemplateSpan(K.RULE_GENERIC, 4, 8))
    assert R.PROMISE_WARRANTY in one("Гарантия год", spans)


def test_hidden_character_after_a_span_is_reported() -> None:
    text = "Гарантия​ год"
    assert one(text, (TemplateSpan(K.RULE_GENERIC, 0, 8),)) == {R.OBFUSCATION}


def test_expanded_character_inside_a_span() -> None:
    text = "Срок ㉑ день"
    assert R.DIGITS_NOT_ALLOWED not in one(text, (TemplateSpan(K.OFFER, 5, 6),))
    assert R.DIGITS_NOT_ALLOWED in one(text)


# --- Y-9: card and phone are hard blocks; a card is never an allowed literal ---------------------


def test_card_number_is_never_an_allowed_literal() -> None:
    codes = one("Карта 4111 1111 1111 1111", lits=("4111 1111 1111 1111",))
    assert R.PAYMENT_CARD in codes


def test_card_and_phone_are_not_overridable() -> None:
    assert {R.PAYMENT_CARD, R.CONTACT_PHONE} <= HARD_BLOCK_CODES
    for text in ("Карта 4111 1111 1111 1111", "Тел 8 900 000 00 01"):
        result = check_parts([text], context=FilterContext(is_owner_edit=True))
        assert not result.allowed
        assert not result.overridable


# --- Y-10: allowlisted URLs may not smuggle numbers or channels --------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://avito.ru/89000000001",
        "https://www.avito.ru/item?phone=89000000001",
        "https://avito.ru/15000",
        "https://avito.ru/pishite-v-telegram",
        "https://avito.ru/user/syn_parts_tg",
    ],
)
def test_allowlisted_url_with_digits_or_channel_is_denied(url: str) -> None:
    config = FilterConfig(url_allowlist=("avito.ru",))
    assert not check_parts([f"Ссылка: {url}"], config=config).allowed


def test_allowlisted_url_with_short_digits_passes() -> None:
    config = FilterConfig(url_allowlist=("avito.ru",))
    assert check_parts(["Ссылка: https://www.avito.ru/moskva/fara_w213"], config=config).allowed


# --- Y-12: masker input cap and performance ----------------------------------------------------


def test_mask_rejects_input_over_the_cap_without_partial_masking() -> None:
    assert mask("a" * MAX_MASK_INPUT).text == "a" * MAX_MASK_INPUT
    with pytest.raises(MaskInputTooLong):
        mask("8 900 000 00 01 " + "a" * MAX_MASK_INPUT)


N = 20_000
PATHOLOGICAL = {
    "O-run": "O " * (N // 2),
    "O0-run": "0O" * (N // 2),
    "fitment": "подойдёт " * (N // 9),
    "not": "не " * (N // 3),
    "write-in": "пишите в " * (N // 9),
    "spaced": "а " * (N // 2),
    "spaced-": "а-" * (N // 2),
    "mixed": "aа" * (N // 2),
    "combining": "а́" * (N // 2),
    "zwj": "‍" * N,
    "dots": "a . " * (N // 4),
    "tochka": "a точка " * (N // 8),
    "brackets": "a[.]" * (N // 4),
    "sup": "⁸" * N,
    "tg-kw": "тг " * (N // 3),
    "handle-kw": "ник a" * (N // 5),
    "plus": "+7 " * (N // 3),
    "sentences": "подойдёт" + "." * N,
    "hedge": "подойдёт " + "а " * (N // 2),
    "slashes": "/" * N,
    "scheme": "ab://" * (N // 5),
    "digits+O": "8 9OO " * (N // 6),
    "phones": "8 900 000 00 01 " * (N // 16),
}


@pytest.mark.parametrize("text", list(PATHOLOGICAL.values()), ids=list(PATHOLOGICAL))
def test_no_redos(text: str) -> None:
    for run in (
        lambda: mask(text),
        lambda: check_parts([text[:4000]]),
        lambda: check_parts([text]),
        lambda: extract_part_number_candidates(text),
    ):
        assert best_of_two(run) < 0.5


def best_of_two(run: Any) -> float:
    """Best of two timings: absorbs GC/scheduler noise, still catches super-linear behaviour."""
    timings = []
    for _ in range(2):
        start = time.perf_counter()
        run()
        timings.append(time.perf_counter() - start)
    return min(timings)


def test_fitment_dense_part_below_the_scan_limit() -> None:
    for text in (("Подойдёт? Проверим. " * 200)[:4000], ("подойдёт " * 500)[:4000]):
        assert best_of_two(lambda text=text: check_parts([text])) < 0.5

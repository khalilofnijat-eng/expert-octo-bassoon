# SYNTHETIC: every text, price, OEM number, phone, e-mail, card, handle and URL below is invented
# test data. Card numbers are public test numbers; domains are example.*. No real customer data,
# no real business rules, prices or templates (the disclosure template is a stand-in).
"""Unit tests for app.safety.filter (T-019, docs/ARCHITECTURE.md §7.2)."""

from __future__ import annotations

import dataclasses

import pytest

from app.config import AutomationMode
from app.safety.filter import (
    HARD_BLOCK_CODES,
    RULES_VERSION,
    FilterConfig,
    FilterContext,
    ReasonCode,
    check_parts,
)

R = ReasonCode

# Synthetic fact-sheet literals used by many cases.
LITERALS = (
    "W213",  # SYNTHETIC body code
    "2018",
    "2016",
    "2020",
    "A2138851400",  # SYNTHETIC OEM
    "90915-10003",  # SYNTHETIC OEM
    "15 000 ₽",  # SYNTHETIC price rendered by {{total}}
    "2 шт.",  # SYNTHETIC quantity
)

# SYNTHETIC stand-in for the owner-approved template:bot_disclosure (§7.3).
BOT_DISCLOSURE = (
    "Здравствуйте! Я — автоматический помощник продавца, не человек. "
    "Наличие, цену и заказ подтверждает продавец."
)

# SYNTHETIC stand-ins for {{rule:…}} business-rule texts; NOT the owner's real rules (B-008).
RULE_WARRANTY = "Условия гарантии уточняйте у продавца."
RULE_CONFIRMED = "Ваш заказ оформлен продавцом."
RULE_PAYMENT = "Оплата получена, спасибо."


def codes_of(text: str, literals: tuple[str, ...] = LITERALS, **ctx: object) -> set[ReasonCode]:
    context = FilterContext(**ctx)  # type: ignore[arg-type]
    result = check_parts([text], allowed_literals=literals, context=context)
    return set(result.parts[0].codes)


# --- Allowed: ordinary replies and false-positive guards ---------------------------------------

ALLOW = [
    pytest.param("Здравствуйте! Фара на W213 2018 рестайлинг есть в наличии.", id="w213-year"),
    pytest.param("W213 2018 рестайлинг", id="w213-2018-restyle"),
    pytest.param("Подскажите VIN, пожалуйста, проверим совместимость.", id="ask-vin"),
    pytest.param("OEM A2138851400, оригинал.", id="oem-literal"),
    pytest.param("oem a2138851400", id="oem-literal-lower-case"),
    pytest.param("Фильтр 90915-10003 есть.", id="oem-dash-literal"),
    pytest.param("Кузов W213, годы 2016–2020.", id="year-range"),
    pytest.param("Итого: 15 000 ₽.", id="price-literal"),
    pytest.param("Итого: 15 000 ₽.", id="price-literal-nbsp"),
    pytest.param("В наличии 2 шт.", id="quantity-literal"),
    pytest.param(BOT_DISCLOSURE, id="bot-disclosure-template"),
    pytest.param("Я бот-помощник продавца. Ответ продавца придёт позже.", id="honest-bot"),
    pytest.param("Сейчас уточню наличие и вернусь с ответом.", id="vernus-not-refund"),
    pytest.param("Сегодня уточню и отправлю фото.", id="send-photo-today"),
    pytest.param("Отправим вам фото сегодня.", id="send-photo-today-2"),
    pytest.param("Установить можно на любом СТО, один момент.", id="sto-and-odin"),
    pytest.param("Бронированное стекло не продаём.", id="armored-glass-not-booking"),
    pytest.param("Контакты разъёма целые, держатель телефона тоже есть.", id="connector-contacts"),
    pytest.param("Отправка Авито Доставкой после оформления на Авито.", id="avito-delivery"),
    pytest.param("Отправляем Почтой России или СДЭК.", id="russian-post"),
    pytest.param("Уточните, пожалуйста, ваш номер заказа в Авито.", id="order-number-question"),
    pytest.param("Заказ ещё не оформлен, сначала подтвердите выбор.", id="not-yet-ordered"),
    pytest.param("Stok var, W213 için uygun olup olmadığını kontrol edeceğim.", id="turkish-mix"),
    pytest.param("Hello! I am the seller's assistant, not a human.", id="english-honest-bot"),
    pytest.param("Цену и наличие подтвердит продавец.", id="price-confirmed-by-seller"),
    pytest.param("Фара подходит для W213 2018 по каталогу? Уточняю.", id="fitment-question"),
]


@pytest.mark.parametrize("text", ALLOW)
def test_allows(text: str) -> None:
    result = check_parts([text], allowed_literals=LITERALS)
    assert result.parts[0].findings == ()
    assert result.allowed


# --- Denied: (text, expected reason code) ------------------------------------------------------

DENY = [
    # Contacts: masker detectors
    pytest.param("Мой телефон 8 900 000-00-01", R.CONTACT_PHONE, id="phone"),
    pytest.param("+7 (900) 000 00 02, звоните", R.CONTACT_PHONE, id="phone-plus7"),
    pytest.param("почта ivan.syn@example.com", R.CONTACT_EMAIL, id="email"),
    pytest.param("пишите @syn_parts_shop", R.CONTACT_SOCIAL, id="handle"),
    pytest.param("наш канал t.me/syn_parts_shop", R.CONTACT_SOCIAL, id="tme-link"),
    pytest.param("wa.me/79000000014", R.CONTACT_SOCIAL, id="wa-link"),
    # Contacts: channel names and redirect phrases
    pytest.param("Напишите мне в WhatsApp", R.CONTACT_CHANNEL, id="write-whatsapp"),
    pytest.param("Пишите в телегу, там быстрее", R.CONTACT_CHANNEL, id="telega"),
    pytest.param("Добавьтесь в вотсап", R.CONTACT_CHANNEL, id="votsap"),
    pytest.param("Есть группа ВКонтакте", R.CONTACT_CHANNEL, id="vkontakte"),
    pytest.param("Write me on Telegram please", R.CONTACT_CHANNEL, id="en-telegram"),
    pytest.param("Позвоните мне, обсудим", R.CONTACT_REDIRECT, id="call-me-ru"),
    pytest.param("Оставьте ваш номер телефона", R.CONTACT_REDIRECT, id="ask-phone"),
    pytest.param("Напишите на почту", R.CONTACT_REDIRECT, id="write-to-mail"),
    pytest.param("Давайте вне Авито договоримся", R.CONTACT_REDIRECT, id="outside-avito"),
    pytest.param("Just call me, it is faster", R.CONTACT_REDIRECT, id="en-call-me"),
    pytest.param("Bana telefon numaranı yaz", R.CONTACT_REDIRECT, id="tr-phone-number"),
    # URLs
    pytest.param("Каталог тут: https://example.com/catalog", R.URL_NOT_ALLOWED, id="url"),
    pytest.param("Смотрите syn-parts.ru/sale", R.URL_NOT_ALLOWED, id="bare-domain"),
    pytest.param("Объявление: https://www.avito.ru/item", R.URL_NOT_ALLOWED, id="avito-default"),
    # Off-platform payment
    pytest.param("Переведите на карту, пожалуйста", R.PAYMENT_OFF_PLATFORM, id="to-card"),
    pytest.param("Нужна предоплата на карту", R.PAYMENT_OFF_PLATFORM, id="prepay-card"),
    pytest.param("Можно по СБП", R.PAYMENT_OFF_PLATFORM, id="sbp"),
    pytest.param("Скиньте на Сбер", R.PAYMENT_OFF_PLATFORM, id="to-sber"),
    pytest.param("Пришлю реквизиты", R.PAYMENT_OFF_PLATFORM, id="requisites"),
    pytest.param("карта 4111 1111 1111 1111", R.PAYMENT_CARD, id="card-number"),
    pytest.param("Bank transfer is fine", R.PAYMENT_OFF_PLATFORM, id="en-bank-transfer"),
    # Digits, currency and number words
    pytest.param("Цена 14 500 ₽", R.DIGITS_NOT_ALLOWED, id="price-not-in-literals"),
    pytest.param("Цена 14 500 ₽", R.CURRENCY, id="ruble-sign"),
    pytest.param("Итого 15 000 рублей", R.DIGITS_NOT_ALLOWED, id="price-other-format"),
    pytest.param("Отдам за пятьсот", R.NUMBER_WORD, id="pyatsot"),
    pytest.param("Две тысячи и забирайте", R.NUMBER_WORD, id="dve-tysyachi"),
    pytest.param("Полторы тысячи", R.NUMBER_WORD, id="poltory"),
    pytest.param("Цена 3 тыс.", R.NUMBER_WORD, id="tys-abbrev"),
    pytest.param("Стоит пару сотен руб", R.CURRENCY, id="rub"),
    pytest.param("Отдам за пол цены", R.NUMBER_WORD, id="pol-ceny"),
    pytest.param("Цена 500р", R.CURRENCY, id="500r"),
    pytest.param("Two thousand rubles", R.NUMBER_WORD, id="en-number-words"),
    pytest.param("Kuzov W212", R.DIGITS_NOT_ALLOWED, id="body-code-not-in-literals"),
    pytest.param("Год 20185", R.DIGITS_NOT_ALLOWED, id="literal-inside-longer-number"),
    pytest.param("Кузов W2130", R.DIGITS_NOT_ALLOWED, id="literal-prefix-only"),
    pytest.param("восемь девятьсот ноль ноль", R.NUMBER_WORD, id="phone-as-words"),
    # Promises
    pytest.param("Сделаю скидку, если возьмёте два", R.PROMISE_DISCOUNT, id="discount"),
    pytest.param("Доставка бесплатно", R.PROMISE_DISCOUNT, id="free"),
    pytest.param("Отдам дешевле", R.PROMISE_DISCOUNT, id="cheaper"),
    pytest.param("Не подойдёт — вернём деньги", R.PROMISE_RETURN, id="refund"),
    pytest.param("Возврат без проблем", R.PROMISE_RETURN, id="vozvrat"),
    pytest.param("Гарантия полгода", R.PROMISE_WARRANTY, id="warranty"),
    pytest.param("Доставим завтра", R.PROMISE_DELIVERY_DATE, id="deliver-tomorrow"),
    pytest.param("В пятницу будет у вас", R.PROMISE_DELIVERY_DATE, id="friday-at-yours"),
    pytest.param("Отправим сегодня же", R.PROMISE_DELIVERY_DATE, id="send-today"),
    pytest.param("We can ship it tomorrow", R.PROMISE_DELIVERY_DATE, id="en-ship-tomorrow"),
    pytest.param("Точно подойдёт на ваш W213", R.UNVERIFIED_FITMENT, id="fits-for-sure"),
    # Completion claims
    pytest.param("Заказ оформлен, ждите", R.COMPLETION_CLAIM, id="order-placed"),
    pytest.param("Забронировал для вас", R.COMPLETION_CLAIM, id="booked"),
    pytest.param("Отложил для вас до вечера", R.COMPLETION_CLAIM, id="put-aside"),
    pytest.param("Товар уже отправлен", R.COMPLETION_CLAIM, id="shipped"),
    pytest.param("Your order has been placed", R.COMPLETION_CLAIM, id="en-order-placed"),
    pytest.param("Оплата получена", R.PAYMENT_RECEIVED_CLAIM, id="payment-received"),
    # Claims to be human
    pytest.param("Я живой человек, не робот", R.HUMAN_CLAIM, id="alive-human"),
    pytest.param("Нет, я не бот", R.HUMAN_CLAIM, id="not-a-bot"),
    pytest.param("С вами общается менеджер", R.HUMAN_CLAIM, id="manager-speaking"),
    pytest.param("I'm a real person", R.HUMAN_CLAIM, id="en-real-person"),
    pytest.param("Bot değilim, gerçek insanım", R.HUMAN_CLAIM, id="tr-not-bot"),
    # Rendering leftovers
    pytest.param("Итого {{total}}", R.UNRENDERED_TOKEN, id="placeholder-left"),
    pytest.param("Перезвоню на [PHONE_1]", R.UNRENDERED_TOKEN, id="masker-token-left"),
]


@pytest.mark.parametrize(("text", "code"), DENY)
def test_denies(text: str, code: ReasonCode) -> None:
    result = check_parts([text], allowed_literals=LITERALS)
    assert not result.allowed
    assert code in result.parts[0].codes


# --- Structure and spans -----------------------------------------------------------------------


def test_spans_point_into_the_part_and_values_are_not_kept() -> None:
    text = "Звоните 8 900 000-00-01 или пишите ivan@example.com"
    verdict = check_parts([text]).parts[0]
    by_code = {f.code: text[f.start : f.end] for f in verdict.findings}
    assert by_code[R.CONTACT_PHONE] == "8 900 000-00-01"
    assert by_code[R.CONTACT_EMAIL] == "ivan@example.com"
    assert "ivan@example.com" not in repr(verdict)
    assert "900" not in repr(verdict)


def test_digits_inside_contact_span_are_not_reported_twice() -> None:
    assert codes_of("тел 8 900 000-00-01") == {R.CONTACT_PHONE}


def test_findings_are_sorted_and_unique() -> None:
    verdict = check_parts(["Скидка! Скидка! Доставим завтра"]).parts[0]
    starts = [f.start for f in verdict.findings]
    assert starts == sorted(starts)
    assert len(verdict.findings) == len(set(verdict.findings))


def test_each_part_gets_its_own_verdict() -> None:
    result = check_parts(
        ["Фара на W213 есть.", "Звоните 8 900 000-00-01", "Итого: 15 000 ₽."],
        allowed_literals=LITERALS,
    )
    assert [p.index for p in result.parts] == [0, 1, 2]
    assert [p.allowed for p in result.parts] == [True, False, True]
    assert not result.allowed
    assert result.reason_codes == (R.CONTACT_REDIRECT, R.CONTACT_PHONE)


def test_is_deterministic() -> None:
    parts = ["Сделаю скидку 10%, звоните 8 900 000-00-01", "W213 2018"]
    first = check_parts(parts, allowed_literals=LITERALS)
    assert check_parts(parts, allowed_literals=LITERALS) == first
    assert first.rules_version == RULES_VERSION


def test_single_string_instead_of_parts_is_rejected() -> None:
    with pytest.raises(TypeError):
        check_parts("W213")


def test_no_parts_is_trivially_allowed() -> None:
    assert check_parts([]).allowed


# --- Length and empty parts --------------------------------------------------------------------


def test_part_of_exactly_1000_chars_passes() -> None:
    assert check_parts(["а" * 1000]).allowed


def test_part_over_1000_chars_is_denied_with_span_at_the_limit() -> None:
    verdict = check_parts(["а" * 1001]).parts[0]
    assert verdict.codes == (R.PART_TOO_LONG,)
    assert (verdict.findings[0].start, verdict.findings[0].end) == (1000, 1001)


def test_length_counts_utf16_units() -> None:
    # An emoji outside the BMP is two UTF-16 code units.
    verdict = check_parts(["а" * 999 + "🙂"]).parts[0]
    assert verdict.codes == (R.PART_TOO_LONG,)
    assert verdict.findings[0].start == 999


def test_max_part_units_is_configurable() -> None:
    config = FilterConfig(max_part_units=10)
    assert not check_parts(["а" * 11], config=config).allowed


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_empty_part_is_denied(text: str) -> None:
    assert check_parts([text]).parts[0].codes == (R.EMPTY_PART,)


# --- Allowed literals --------------------------------------------------------------------------


def test_allowed_literal_phone_lookalike_oem_is_exempt() -> None:
    # The masker reads a contiguous 11-digit 8-prefixed number as a phone (T-014 limitation).
    assert codes_of("BMW 83212365946") == {R.CONTACT_PHONE}
    assert codes_of("BMW 83212365946", literals=("83212365946",)) == set()


def test_allowed_literal_does_not_exempt_email_or_social() -> None:
    assert R.CONTACT_EMAIL in codes_of("ivan@example.com", literals=("ivan@example.com",))


def test_literal_without_letters_or_digits_is_ignored() -> None:
    assert codes_of("Цена в ₽", literals=("₽",)) == {R.CURRENCY}


def test_price_literal_does_not_cover_a_different_currency_word() -> None:
    assert codes_of("15 000 ₽ или 15 000 руб", literals=("15 000 ₽",)) == {
        R.DIGITS_NOT_ALLOWED,
        R.CURRENCY,
    }


# --- URL allowlist -----------------------------------------------------------------------------


def test_url_allowlist_allows_host_and_subdomains() -> None:
    config = FilterConfig(url_allowlist=("avito.ru",))
    result = check_parts(
        ["Ссылка: https://www.avito.ru/moskva/zapchasti/syn_123 и avito.ru/item"],
        config=config,
    )
    assert result.allowed


@pytest.mark.parametrize(
    "url",
    [
        "https://avito.ru@example.com/x",
        "https://avito.ru.example.com/x",
        "https://evilavito.ru/x",
        "https://example.com/?next=avito.ru",
    ],
)
def test_url_allowlist_is_not_fooled(url: str) -> None:
    config = FilterConfig(url_allowlist=("avito.ru",))
    verdict = check_parts([f"Ссылка: {url}"], config=config).parts[0]
    assert R.URL_NOT_ALLOWED in verdict.codes


def test_allowlist_never_allows_social_links() -> None:
    config = FilterConfig(url_allowlist=("t.me",))
    assert R.CONTACT_SOCIAL in check_parts(["t.me/syn_parts_shop"], config=config).parts[0].codes


# --- Templates and confirmation flags ----------------------------------------------------------


def test_rule_template_may_carry_promises_and_numbers() -> None:
    text = f"Фара есть. {RULE_WARRANTY}"
    assert codes_of(text) == {R.PROMISE_WARRANTY}
    assert codes_of(text, template_texts=(RULE_WARRANTY,)) == set()


def test_same_promise_outside_the_template_is_still_denied() -> None:
    text = f"{RULE_WARRANTY} Гарантия год!"
    assert codes_of(text, template_texts=(RULE_WARRANTY,)) == {R.PROMISE_WARRANTY}


def test_template_does_not_exempt_contacts_or_payment() -> None:
    rule = "Предоплата на карту, звоните 8 900 000-00-01"
    assert codes_of(rule, template_texts=(rule,)) >= {
        R.PAYMENT_OFF_PLATFORM,
        R.CONTACT_PHONE,
        R.CONTACT_REDIRECT,
    }


def test_completion_claim_needs_flag_and_template() -> None:
    assert codes_of(RULE_CONFIRMED) == {R.COMPLETION_CLAIM}
    assert codes_of(RULE_CONFIRMED, completion_confirmed=True) == {R.COMPLETION_CLAIM}
    assert codes_of(RULE_CONFIRMED, template_texts=(RULE_CONFIRMED,)) == {R.COMPLETION_CLAIM}
    ok = codes_of(RULE_CONFIRMED, completion_confirmed=True, template_texts=(RULE_CONFIRMED,))
    assert ok == set()


def test_payment_claim_needs_its_own_flag() -> None:
    kwargs: dict[str, object] = {"template_texts": (RULE_PAYMENT,)}
    assert codes_of(RULE_PAYMENT, completion_confirmed=True, **kwargs) == {R.PAYMENT_RECEIVED_CLAIM}
    assert codes_of(RULE_PAYMENT, payment_confirmed=True, **kwargs) == set()


def test_fitment_certainty_needs_verified_flag() -> None:
    text = "Точно подойдёт на W213 2018"
    assert codes_of(text) == {R.UNVERIFIED_FITMENT}
    assert codes_of(text, fitment_verified=True) == set()


# --- Owner edit (warn mode) and automation mode ------------------------------------------------


def test_owner_edit_warns_but_does_not_block() -> None:
    text = "Звоните 8 900 000-00-01, сделаю скидку"
    normal = check_parts([text])
    edit = check_parts([text], context=FilterContext(is_owner_edit=True))
    assert not normal.allowed
    assert edit.allowed
    assert edit.warn_only
    assert edit.needs_owner_confirmation
    assert edit.parts[0].findings == normal.parts[0].findings


def test_owner_edit_without_findings_needs_no_confirmation() -> None:
    ctx = FilterContext(is_owner_edit=True)
    edit = check_parts(["W213 есть"], allowed_literals=LITERALS, context=ctx)
    assert edit.allowed
    assert not edit.needs_owner_confirmation


def test_owner_edit_still_hard_blocks_length_and_empty() -> None:
    assert frozenset({R.EMPTY_PART, R.PART_TOO_LONG}) == HARD_BLOCK_CODES
    edit = check_parts(["а" * 1001, ""], context=FilterContext(is_owner_edit=True))
    assert [p.allowed for p in edit.parts] == [False, False]


@pytest.mark.parametrize("mode", list(AutomationMode))
def test_automation_mode_relaxes_nothing(mode: AutomationMode) -> None:
    context = FilterContext(automation_mode=mode)
    assert not check_parts(["Звоните 8 900 000-00-01"], context=context).allowed


def test_context_defaults_are_strict() -> None:
    fields = {f.name: f.default for f in dataclasses.fields(FilterContext)}
    assert fields["automation_mode"] is AutomationMode.DRAFT_ONLY
    assert fields["is_owner_edit"] is False
    assert fields["completion_confirmed"] is False
    assert fields["payment_confirmed"] is False
    assert fields["fitment_verified"] is False
    assert FilterConfig().url_allowlist == ()


# --- Known limitations (documented in the module docstring) -----------------------------------
# strict xfail: if one of these starts passing, the test fails and the docstring must be updated.

MISSED = [
    pytest.param("Отдам за пятихатку", id="slang-pyatikhatka"),
    pytest.param("Цена пятсот", id="typo-pyatsot"),
    pytest.param("Fiyatı on bin", id="turkish-on-bin"),
    pytest.param("Остался всего один", id="odin-quantity"),
    pytest.param("Пишите в WhatsАpp", id="homoglyph-channel"),
    pytest.param("Пишите в What​sApp", id="zero-width-channel"),
]


@pytest.mark.xfail(reason="known limitation: not detected", strict=True)
@pytest.mark.parametrize("text", MISSED)
def test_known_limitations_missed(text: str) -> None:
    assert not check_parts([text]).allowed


OVERBLOCKED = [
    pytest.param("OEM A 213 885 14 00", id="oem-other-format"),
    pytest.param("Пока ещё не забронировано", id="negated-booking"),
    pytest.param("Мы не используем WhatsApp", id="negated-channel"),
]


@pytest.mark.xfail(reason="known limitation: fails safe (denied)", strict=True)
@pytest.mark.parametrize("text", OVERBLOCKED)
def test_known_limitations_overblocked(text: str) -> None:
    assert check_parts([text], allowed_literals=LITERALS).allowed

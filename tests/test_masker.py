# SYNTHETIC: every phone, e-mail, card, VIN, plate, handle and URL below is invented test data.
# Card numbers are public test numbers; domains are example.* / пример.рф. No real customer data.
"""Unit tests for app.safety.masker."""

from __future__ import annotations

import pytest

from app.safety.masker import PiiType, mask

# --- Positive cases: (input, expected masked text) -------------------------------------------

POSITIVE = [
    # Phones: +7 / 8 / 7 prefixes, brackets, dashes, dots, spaces
    ("Звоните +7 900 000-00-01", "Звоните [PHONE_1]"),
    ("тел. 8 (900) 000-00-02", "тел. [PHONE_1]"),
    ("+7(900)0000003 после 18:00", "[PHONE_1] после 18:00"),
    ("номер 89000000004", "номер [PHONE_1]"),
    ("пишите 7 900 000 00 05", "пишите [PHONE_1]"),
    ("8-900-000-0006 Иван", "[PHONE_1] Иван"),
    ("мой 8.900.000.00.07", "мой [PHONE_1]"),
    ("мобильный 900 000 00 08", "мобильный [PHONE_1]"),
    ("(900) 000-00-09 whatsapp", "[PHONE_1] whatsapp"),
    ("городской +7 495 000-00-10", "городской [PHONE_1]"),
    ("звони8 900 000 00 11", "звони[PHONE_1]"),
    ("(8 900 000 00 12)", "([PHONE_1])"),
    # Obfuscation that IS supported: one digit per group
    ("8 9 0 0 0 0 0 0 0 1 3", "[PHONE_1]"),
    # E-mail, including upper case and a Cyrillic domain
    ("почта ivan.syn@example.com.", "почта [EMAIL_1]."),
    ("IVAN_SYN+avito@EXAMPLE.ORG", "[EMAIL_1]"),
    ("пишите на почта@пример.рф", "пишите на [EMAIL_1]"),
    # Payment cards (Luhn-valid public test numbers)
    ("переведите на карту 4111 1111 1111 1111", "переведите на карту [CARD_1]"),
    ("карта 5555-5555-5555-4444!", "карта [CARD_1]!"),
    ("2 4111 1111 1111 1111", "2 [CARD_1]"),
    # VIN: Latin, lower case, Cyrillic look-alikes
    ("VIN WDD2130001A000001", "VIN [VIN_1]"),
    ("вин: wdd2130001a000002", "вин: [VIN_1]"),
    ("ХТА210990Y0000003 (кириллица)", "[VIN_1] (кириллица)"),
    # Plates: Cyrillic, Latin, mixed, 2- and 3-digit region, spaced upper case
    ("госномер А123ВС77", "госномер [PLATE_1]"),
    ("номер A123BC777", "номер [PLATE_1]"),
    ("машина а001мр199", "машина [PLATE_1]"),
    ("смешанный А123BC50", "смешанный [PLATE_1]"),
    ("номер К 456 ОР 750", "номер [PLATE_1]"),
    # Social handles and links
    ("мой тг @syn_parts_shop", "мой тг [SOCIAL_1]"),
    ("tg: syn_parts_shop", "tg: [SOCIAL_1]"),
    ("пишите в телегу t.me/syn_parts_shop.", "пишите в телегу [SOCIAL_1]."),
    ("https://vk.com/id000000 или vk.com/syn.parts", "[SOCIAL_1] или [SOCIAL_2]"),
    ("ватсап wa.me/79000000014", "ватсап [SOCIAL_1]"),
    ("вк: syn_parts", "вк: [SOCIAL_1]"),
    # URLs
    ("смотри https://example.com/catalog?id=1, там всё", "смотри [URL_1], там всё"),
    ("сайт www.example.org", "сайт [URL_1]"),
    ("магазин syn-parts.ru/sale", "магазин [URL_1]"),
    ("зайдите на пример.рф", "зайдите на [URL_1]"),
    ("https://example.com/?u=ivan@example.com", "[URL_1]"),
]


@pytest.mark.parametrize(("text", "expected"), POSITIVE)
def test_masks_pii(text: str, expected: str) -> None:
    assert mask(text).text == expected


# --- Negative cases: auto-parts identifiers and ordinary numbers stay untouched ---------------

NEGATIVE = [
    "Нужна фара на W213, OEM A2138851400",
    "номер детали 213 885 14 00",
    "A 213 885 14 00 оригинал",
    "каталожный A 960 880 01 05",
    "фильтр 90915-10003",
    "BMW 11 42 7 953 129",
    "BMW 83 21 2 365 946",
    "кузов X253, GLC 2016 года",
    "W213 E200 2017-2020",
    "цена 15 000 ₽, со скидкой 12 500 руб.",
    "пробег 150 000 км",
    "доставка в 100 км 20 минут",
    "дата 27.09.2026, время 10:30",
    "A2138851400 9999 цвет",
    "номер A123BC без региона",
    "WDD213042IA123456 содержит I, это не VIN",
    "WDD2130421A12345 (16 символов)",
    "4111 1111 1111 1112 (не проходит Луна)",
    "артикул 2138851400",
    "email без домена: ivan@localhost",
    "Здравствуйте! Есть в наличии?",
]


@pytest.mark.parametrize("text", NEGATIVE)
def test_does_not_mask_non_pii(text: str) -> None:
    result = mask(text)
    assert result.text == text
    assert result.spans == ()


# --- Structure: tokens, spans, mapping ----------------------------------------------------------


def test_same_value_gets_same_token_and_numbering_follows_order() -> None:
    text = "8 900 000-00-01, +7 (900) 000 00 01, 8 900 000 00 02"
    assert mask(text).text == "[PHONE_1], [PHONE_1], [PHONE_2]"


def test_same_plate_in_cyrillic_and_latin_gets_same_token() -> None:
    assert mask("А123ВС77 = A123BC77").text == "[PLATE_1] = [PLATE_1]"


def test_spans_are_typed_and_point_into_original_text() -> None:
    text = "Иван, 8 900 000 00 01, ivan@example.com, А123ВС77"
    result = mask(text)
    assert [s.type for s in result.spans] == [PiiType.PHONE, PiiType.EMAIL, PiiType.PLATE]
    assert [text[s.start : s.end] for s in result.spans] == [
        "8 900 000 00 01",
        "ivan@example.com",
        "А123ВС77",
    ]
    assert [s.token for s in result.spans] == ["[PHONE_1]", "[EMAIL_1]", "[PLATE_1]"]


def test_mapping_is_off_by_default() -> None:
    assert mask("ivan@example.com").mapping is None


def test_mapping_when_requested_and_not_in_repr() -> None:
    result = mask("ivan@example.com, 8 900 000 00 01", keep_mapping=True)
    assert result.mapping == {"[EMAIL_1]": "ivan@example.com", "[PHONE_1]": "8 900 000 00 01"}
    assert "ivan@example.com" not in repr(result)
    assert "900" not in repr(result)


def test_masking_is_deterministic_and_idempotent() -> None:
    text = "тел 8 900 000 00 01, VIN WDD2130001A000001"
    first = mask(text)
    assert mask(text) == first
    assert mask(first.text).text == first.text


def test_mixed_message_keeps_part_numbers() -> None:
    text = "W213 A2138851400 цена 15 000 ₽, звоните 8 900 000 00 01 или @syn_parts_shop"
    assert mask(text).text == "W213 A2138851400 цена 15 000 ₽, звоните [PHONE_1] или [SOCIAL_1]"


def test_empty_text() -> None:
    assert mask("") == mask("")
    assert mask("").text == ""


# --- Known limitations (documented in the module docstring) -----------------------------------
# strict xfail: if one of these starts passing, the test fails and the docstring must be updated.

LIMITATIONS = [
    pytest.param("восемь девятьсот ноль ноль ноль ноль ноль ноль один", id="phone-as-words"),
    pytest.param("8 9OO OOO OO O1", id="letter-O-for-zero"),
    pytest.param("ivan собака example точка com", id="spelled-out-email"),
    pytest.param("меня зовут Иван Петров", id="personal-name"),
    pytest.param("адрес: ул. Ленина, д. 1, кв. 2", id="postal-address"),
    pytest.param("городской 000-00-01", id="short-city-number"),
]


@pytest.mark.xfail(reason="known limitation of regex masking", strict=True)
@pytest.mark.parametrize("text", LIMITATIONS)
def test_known_limitations_not_masked(text: str) -> None:
    assert mask(text).spans != ()


@pytest.mark.xfail(reason="contiguous 11-digit 8/7-prefixed numbers are always phones", strict=True)
def test_known_limitation_contiguous_bmw_number() -> None:
    assert mask("BMW 83212365946").spans == ()

# SYNTHETIC: every phone, e-mail, card, VIN, plate, handle and URL below is invented test data.
# Card numbers are public test numbers; domains are example.* / пример.рф. No real customer data.
"""Unit tests for app.safety.masker."""

from __future__ import annotations

import pytest

from app.safety.masker import PiiType, mask
from app.safety.normalize import normalize
from app.safety.part_numbers import extract_part_number_candidates

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
    # T-034: the letter O for zero is read as zero inside a phone-like run (was a T-014 xfail)
    ("8 9OO OOO OO O1", "[PHONE_1]"),
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


# --- T-034: regressions from the T-032 security review -----------------------------------------
# SYNTHETIC inputs from the review's reproduction scripts (m2.py, sup.py, mfp.py).

T032_MUST_MASK = [
    # Normalization (D-a): compatibility digits, invisible characters, newlines
    ("Мой номер ⁸⁹⁰⁰⁰⁰⁰⁰⁰⁰¹", PiiType.PHONE),
    ("Мой номер ８９００００００００１", PiiType.PHONE),
    ("+7 ９００ ０００ ００ ０１", PiiType.PHONE),
    ("Мой номер 8​900​000​00​01", PiiType.PHONE),
    ("Мой номер 8\n900\n000\n00\n01", PiiType.PHONE),
    ("мой номер 8 9ОО ООО ОО О1", PiiType.PHONE),
    ("+7 900 ООО ОО О1", PiiType.PHONE),
    # Separators "/" and "_" (D-h), any grouping of an 89…/79… mobile number
    ("мой номер 8/900/000/00/01", PiiType.PHONE),
    ("мой номер 8_900_000_00_01", PiiType.PHONE),
    ("8 9000 00 00 01", PiiType.PHONE),
    ("89 000 000 001", PiiType.PHONE),
    ("8 90 00 00 00 01", PiiType.PHONE),
    ("8 9000 000 001", PiiType.PHONE),
    ("89-00-00-00-00-1", PiiType.PHONE),
    ("тел8900000000 1", PiiType.PHONE),
    ("WhatsApp: a 89000000001", PiiType.PHONE),
    ("звоните x 8 900 000 00 01", PiiType.PHONE),
    # Foreign numbers with "+"
    ("+375 29 000 00 01", PiiType.PHONE),
    ("+998 90 000 00 01", PiiType.PHONE),
    # Keyword + space/colon/dash + handle; ник/логин/аккаунт (D-h)
    ("мой тг ivan_petrov", PiiType.SOCIAL),
    ("телега ivan_petrov", PiiType.SOCIAL),
    ("ник в телеге: ivan_petrov", PiiType.SOCIAL),
    ("Телеграм - syn_parts", PiiType.SOCIAL),
    ("Telegram @ syn_parts", PiiType.SOCIAL),
    ("тг — syn_parts", PiiType.SOCIAL),
    ("тг syn_parts", PiiType.SOCIAL),
    ("ник: syn_parts", PiiType.SOCIAL),
    ("логин syn.parts", PiiType.SOCIAL),
    ("аккаунт synparts в тг", PiiType.SOCIAL),
    ("@Иван_Петров", PiiType.SOCIAL),
    # E-mail/URL: punycode TLD, more TLDs, look-alike letters in a link
    ("ivan@example.xn--p1ai", PiiType.EMAIL),
    ("сайт example.kz", PiiType.URL),
    ("сайт example.by", PiiType.URL),
    ("сайт example.de", PiiType.URL),
    ("bit.ly/abc", PiiType.URL),
    ("vk.cc/abc", PiiType.SOCIAL),
    ("t.mе/syn_parts", PiiType.SOCIAL),  # Cyrillic "е"
    # Cards with ".", "_" or double-space separators; Cyrillic "У" in a VIN
    ("карта 4111.1111.1111.1111", PiiType.CARD),
    ("карта 4111_1111_1111_1111", PiiType.CARD),
    ("карта 4111  1111  1111  1111", PiiType.CARD),
    ("ВИН ХТА210990У1234567", PiiType.VIN),
]


@pytest.mark.parametrize(("text", "pii_type"), T032_MUST_MASK)
def test_t032_masks(text: str, pii_type: PiiType) -> None:
    assert pii_type in {span.type for span in mask(text).spans}


def test_t032_dotted_handle_is_masked_whole() -> None:
    assert mask("@ivan.petrov").text == "[SOCIAL_1]"


def test_spans_include_invisible_characters_and_map_to_original() -> None:
    text = "Мой номер 8​900​000​00​01!"
    result = mask(text)
    assert result.text == "Мой номер [PHONE_1]!"
    span = result.spans[0]
    assert text[span.start : span.end] == "8​900​000​00​01"


def test_lone_surrogate_does_not_raise() -> None:
    assert mask("8 900 000 00 01 \ud800").text == "[PHONE_1] \ud800"


def test_keyword_handle_does_not_take_avito() -> None:
    assert mask("аккаунт Avito").spans == ()


T032_STILL_LEAKING = [
    # Documented masker limitations; the output filter denies all of them in outgoing text.
    pytest.param("ivan_petrov@yandex", id="email-without-tld"),
    pytest.param("ivan@[127.0.0.1]", id="email-ip-literal"),
    pytest.param("сайт: example .com", id="obfuscated-dot-space"),
    pytest.param("сайт: example[.]com", id="obfuscated-dot-brackets"),
    pytest.param("сайт: example,com", id="obfuscated-dot-comma"),
    pytest.param("сайт example.ру", id="cyrillic-fake-tld"),
    pytest.param("t .me/syn", id="social-link-with-space"),
    pytest.param("@sy", id="two-letter-handle"),
    pytest.param("VIN WDD2130421A12345Z", id="vin-ending-with-letter"),
    pytest.param("номер а 123 вс 77", id="lowercase-spaced-plate"),
    pytest.param("номер А123ВС", id="plate-without-region"),
    pytest.param("паспорт 4510 123456", id="passport"),
    pytest.param("СНИЛС 112-233-445 95", id="snils"),
    pytest.param("ИНН 7707083893", id="inn"),
]


@pytest.mark.xfail(reason="known limitation of regex masking (T-032)", strict=True)
@pytest.mark.parametrize("text", T032_STILL_LEAKING)
def test_t032_known_leaks(text: str) -> None:
    assert mask(text).spans != ()


def test_not_a_card_when_luhn_fails() -> None:
    assert mask("карта 4111 1111 1111 111").spans == ()


# --- T-034 / D-i: masker false positives stay; part-number candidates come from raw text --------

# The masker keeps masking these (accepted false positives, D-i) ...
ACCEPTED_MASKER_FALSE_POSITIVES = [
    ("9091510003", PiiType.PHONE),
    ("Lexus 9008091210", PiiType.PHONE),
    ("961 480 42 80", PiiType.PHONE),
    ("EAN 4006633150043", PiiType.CARD),
    ("артикул @W213", PiiType.SOCIAL),
]


@pytest.mark.parametrize(("text", "pii_type"), ACCEPTED_MASKER_FALSE_POSITIVES)
def test_accepted_masker_false_positives(text: str, pii_type: PiiType) -> None:
    assert pii_type in {span.type for span in mask(text).spans}


# ... and extract_part_number_candidates() finds the numbers in the raw text before masking.
PART_NUMBER_CASES = [
    ("9091510003", "9091510003"),
    ("Toyota 90915 10003", "9091510003"),
    ("Toyota 04465-33450", "0446533450"),
    ("Bosch 0 986 494 123", "0986494123"),
    ("BMW 34 11 6 794 300", "34116794300"),
    ("BMW 83 21 2 365 946", "83212365946"),
    ("A 960 880 01 05", "A9608800105"),
    ("MB А2138851400", "A2138851400"),  # Cyrillic "А"
    ("VAG 5Q0 407 271 AH", "5Q0407271AH"),
    ("Hyundai 58101-3KA00", "581013KA00"),
    ("Febi ９００２３４５６７８", "9002345678"),  # fullwidth digits
    ("961 480 42 80", "9614804280"),
]


@pytest.mark.parametrize(("text", "key"), PART_NUMBER_CASES)
def test_part_number_candidates(text: str, key: str) -> None:
    candidates = extract_part_number_candidates(text)
    assert key in {c.key for c in candidates}
    match = next(c for c in candidates if c.key == key)
    raw = normalize(text[match.start : match.end]).lat.upper()
    assert "".join(ch for ch in raw if ch.isascii() and ch.isalnum()) == key


@pytest.mark.parametrize("text", ["Пробег 90 000 км", "Цена 15 000", "Здравствуйте!", "W213"])
def test_no_part_number_candidates(text: str) -> None:
    assert extract_part_number_candidates(text) == ()


def test_part_number_candidates_are_deterministic_and_sorted() -> None:
    text = "A2138851400 и 90915-10003, ещё 0 986 494 123"
    first = extract_part_number_candidates(text)
    assert first == extract_part_number_candidates(text)
    assert [c.start for c in first] == sorted(c.start for c in first)
    assert {"A2138851400", "9091510003", "0986494123"} <= {c.key for c in first}


def test_part_number_candidates_reject_non_str() -> None:
    with pytest.raises(TypeError):
        extract_part_number_candidates(b"90915-10003")  # type: ignore[arg-type]

"""Phrase and token patterns used by the output filter (``app.safety.filter``).

Each public ``*_RE`` constant belongs to exactly one reason code of the filter; the mapping is in
``app.safety.filter``. The patterns are deliberately conservative: a false positive sends the
draft to the owner, a false negative could send a banned message. Every new failure type gets a
pattern here and a test case (docs/ARCHITECTURE.md §7.2). Bump ``PATTERNS_VERSION`` whenever a
pattern changes, so filter results stay traceable.

All patterns are case-insensitive. Russian first, then English and Turkish (best effort).
"""

from __future__ import annotations

import re

__all__ = [
    "COMPLETION_RE",
    "CONTACT_CHANNEL_RE",
    "CONTACT_REDIRECT_RE",
    "CURRENCY_RE",
    "DELIVERY_DATE_RE",
    "DIGITS_RE",
    "DISCOUNT_RE",
    "FITMENT_RE",
    "HUMAN_CLAIM_RE",
    "NUMBER_WORD_RE",
    "NUMBER_WORD_SKIP_EXACT",
    "PATTERNS_VERSION",
    "PAYMENT_OFF_PLATFORM_RE",
    "PAYMENT_RECEIVED_RE",
    "RETURN_RE",
    "UNRENDERED_TOKEN_RE",
    "WARRANTY_RE",
]

PATTERNS_VERSION = "1"


def _any(*alternatives: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{alt})" for alt in alternatives), re.IGNORECASE)


# --- Rendering leftovers ----------------------------------------------------------------------

# ``{{total}}`` style placeholders that were not rendered, and masker tokens such as ``[PHONE_1]``
# that the LLM copied from the masked conversation.
UNRENDERED_TOKEN_RE = _any(
    r"\{\{[^{}]*\}\}",
    r"\[(?:EMAIL|SOCIAL|URL|CARD|PHONE|VIN|PLATE)_\d+\]",
)

# --- Contacts and off-platform channels --------------------------------------------------------

# Names of off-platform channels. Any mention is denied: the assistant has no reason to name them.
CONTACT_CHANNEL_RE = _any(
    r"\bwhats\s?app\w*",
    r"\bв[оа]тс?ап\w*",
    r"\bвацап\w*",
    r"\btelegram\w*",
    r"\bтелеграм\w*",
    r"\bтелег[аиуе]\b",
    r"\bтг\b",
    r"\btg\b",
    r"\bviber\b",
    r"\bвайбер\w*",
    r"\bvk\b",
    r"\bвк\b",
    r"\bвконтакт\w*",
    r"\binstagram\w*",
    r"\bинстаграм\w*",
    r"\bинст[аеуы]\b",
    r"\bskype\b",
    r"\bскайп\w*",
    r"\bfacebook\b",
    r"\bфейсбук\w*",
    r"\bмессенджер\w*",
    r"\bmessenger\b",
    r"\be-?mail\w*",
    r"\bимейл\w*",
    r"\bемейл\w*",
    r"\bэлектронн\w*\s+почт\w*",
)

# "Call me", "my number", "write to my e-mail", "outside Avito" and similar redirections or
# requests for contact details.
CONTACT_REDIRECT_RE = _any(
    r"\b(?:позвон|перезвон)\w*",
    r"\bзвон(?:ите|и|ить)\b",
    r"\bнабер(?:ите|и)\b",
    r"\b(?:мой|моя|мою|наш|наша|нашу|ваш|ваша|вашу|свой|свою|твой)\s+(?:контактн\w*\s+)?"
    r"(?:номер|телефон|почт[аул]|e-?mail|контакт\w*)\b"
    r"(?!\s+(?:заказ|детал|запчаст|объявлени|кузов|двигател|vin|вин|артикул|позици|вариант)\w*)",
    r"\bномер\w*\s+(?:телефон|мобильн|сотов)\w*",
    r"\bтелефон\w*\s+для\s+связи\b",
    r"\bпо\s+телефону\b",
    r"\bконтактн(?:ый|ые|ого|ых|ую)\s+(?:телефон|номер|данн)\w*",
    r"\b(?:напиш|пиш|свяж|связ|добав|стуч)\w*\s+(?:\w+\s+){0,2}?(?:в|на|по)\s+(?:личк|почт|лс\b)\w*",
    r"\b(?:вне|мимо|минуя)\s+авито\b",
    r"\bв\s+обход\s+авито\b",
    r"\bне\s+через\s+авито\b",
    # English
    r"\b(?:call|text|phone|ring|message)\s+me\b",
    r"\bmy\s+(?:phone|number|cell|mobile|email|e-mail|whatsapp|telegram)\b",
    r"\b(?:phone|cell|mobile)\s+number\b",
    r"\b(?:contact|reach)\s+me\b",
    r"\bdm\s+me\b",
    r"\boutside\s+(?:of\s+)?avito\b",
    # Turkish
    r"\btelefon\s+numara\w*",
    r"\bbeni\s+ara\w*",
    r"\bnumaram\w*",
    r"\bavito\s+dışında\b",
)

# --- Off-platform payment ----------------------------------------------------------------------

PAYMENT_OFF_PLATFORM_RE = _any(
    r"\bна\s+(?:\w+\s+){0,2}?карт(?:у|очку)\b",
    r"\b(?:перев(?:[её]д|од|ест)\w*|скин\w*|кин(?:ь|ьте|уть)|закин\w*)\s+(?:\w+\s+){0,3}?"
    r"(?:на\s+)?(?:карт\w*|сч[её]т\w*|сбер\w*|т-?банк\w*|тинькоф\w*|киви|qiwi|юmoney|юмани)",
    r"\bпредоплат\w*",
    r"\bсбп\b",
    r"\bсистем\w*\s+быстрых\s+платеж\w*",
    r"\bпо\s+номеру\s+(?:телефона|карты)\b",
    r"\bномер\w*\s+(?:вашей\s+|моей\s+|банковской\s+)?карт\w*",
    r"\bреквизит\w*",
    r"\bсбер(?:банк\w*|а|у|ом|е)?\b",
    r"\bтинькофф?\w*",
    r"\bт-банк\w*",
    r"\b(?:qiwi|киви|юmoney|юмани|webmoney|вебмани|paypal|пейпал)\b",
    # English
    r"\b(?:card|bank|wire)\s+transfer\b",
    r"\bsend\s+(?:me\s+)?(?:the\s+)?money\b",
    r"\bprepay\w*",
    r"\bpay\s+(?:to\s+)?(?:my|the)\s+card\b",
    # Turkish
    r"\bhavale\b",
    r"\biban\b",
    r"\beft\b",
    r"\bön\s*ödeme\w*",
    r"\bkart(?:ıma|a)\s+(?:gönder|yatır)\w*",
)

# --- Numbers and money -------------------------------------------------------------------------

DIGITS_RE = re.compile(r"\d+")

CURRENCY_RE = _any(
    r"[₽$€£¥₺₸₴]",
    r"\bруб(?:л[ьеяюи]\w*)?\b\.?",
    r"(?<=\d)\s?р\.?(?!\w)",
    r"\bкоп(?:еек|ейк\w*|\.)",
    r"\bдоллар\w*",
    r"\bбакс\w*",
    r"\bевро\b",
    r"\brub(?:les?)?\b",
    r"\brur\b",
    r"\broubles?\b",
    r"\busd\b",
    r"\beur\b",
    r"\bdollars?\b",
    r"\beuros?\b",
    r"\bbucks?\b",
    r"\blira\b",
)

# Russian number words (best effort, ARCHITECTURE §7.2). "один/одна/одно" are NOT included: they
# are too common in ordinary sentences ("один момент"). Ordinals ("второй") are not included.
_RU_NUMBER_WORDS = (
    r"ноль|нол[яюе]|нул[ьяюе]|нул[её]м"
    r"|дв[ае]|двух|двум|двумя|двое"
    r"|три|тр[её]х|тр[её]м|тремя|трое"
    r"|четыре|четыр[её]х|четыр[её]м|четырьмя"
    r"|пять|пяти|пятью|шесть|шести|шестью|семь|семи|семью"
    r"|восемь|восьми|восемью|девять|девяти|девятью"
    r"|десять|десяти|десятью|десят(?:ок|ка|ку|ки)"
    r"|(?:одинн|двен|трин|четырн|пятн|шестн|семн|восемн|девятн)адцат\w*"
    r"|(?:дв|тр)адцат\w*"
    r"|сорок|сорока|пятьдесят|пятидесят\w*|шестьдесят|шестидесят\w*|семьдесят|семидесят\w*"
    r"|восемьдесят|восьмидесят\w*|девяносто|девяноста"
    r"|сто|ста|сотн\w*|сот(?:к[аиуе]|ен)"
    r"|двести|двухсот\w*|триста|тр[её]хсот\w*|четыреста|четыр[её]хсот\w*"
    r"|пятьсот|пятисот\w*|шестьсот|шестисот\w*|семьсот|семисот\w*"
    r"|восемьсот|восьмисот\w*|девятьсот|девятисот\w*"
    r"|тысяч\w*|тыщ\w*|тыс|косар\w*"
    r"|миллион\w*|млн|миллиард\w*|млрд"
    r"|полтора|полторы|полутора|полтинник\w*|пол[- ]?цен\w*|половин\w*"
)
_EN_NUMBER_WORDS = (
    r"two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
    r"|(?:thir|four|fif|six|seven|eigh|nine)teen"
    r"|(?:twen|thir|for|fif|six|seven|eigh|nine)ty"
    r"|hundred\w*|thousand\w*|million\w*|grand"
)
# Turkish "bir", "altı", "on", "yüz" and "bin" are also ordinary words and are NOT included.
_TR_NUMBER_WORDS = (
    r"iki|üç|dört|beş|yedi|sekiz|dokuz|yirmi|otuz|kırk|elli|altmış|yetmiş|seksen|doksan|milyon"
)
NUMBER_WORD_RE = _any(rf"\b(?:{_RU_NUMBER_WORDS}|{_EN_NUMBER_WORDS}|{_TR_NUMBER_WORDS})\b")
# Exact (case-sensitive) matches of NUMBER_WORD_RE that are not numbers: "СТО" is a service
# station (станция техобслуживания).
NUMBER_WORD_SKIP_EXACT = frozenset({"СТО"})

# --- Promises that only a business-rule template may make ---------------------------------------

DISCOUNT_RE = _any(
    r"\bскид(?:к|оч)\w*",
    r"\bуступ(?:лю|им|ите|ить|аю|аем|к\w*)\b",
    r"\b(?:отдам|отдадим|сделаю|сделаем|продам|продадим)\s+(?:\w+\s+){0,2}?"
    r"(?:дешевле|подешевле|со\s+скидкой)\b",
    r"\bбесплатн\w*",
    r"\bдаром\b",
    r"\bторг\b",
    r"\bdiscount\w*",
    r"\bfor\s+free\b",
    r"\bfree\s+(?:delivery|shipping)\b",
    r"\bindirim\w*",
    r"\bbedava\b",
    r"\bücretsiz\b",
)

RETURN_RE = _any(
    r"\bвозвра[тщ]\w*",
    r"\bверн[её]м\b",
    r"\bверну\b",
    r"\bвернуть\s+(?:деньги|средства|товар|оплату)\b",
    r"\bденьги\s+(?:назад|обратно)\b",
    r"\bприм(?:ем|у)\s+(?:\w+\s+)?обратно\b",
    r"\bобмен\w*",
    r"\brefund\w*",
    r"\bmoney\s+back\b",
    r"\breturn\w*",
    r"\biade\w*",
)

WARRANTY_RE = _any(
    r"\bгарант\w*",
    r"\bwarrant\w*",
    r"\bguarant\w*",
    r"\bgaranti\w*",
)

# A delivery/dispatch verb near a concrete time ("доставим завтра", "в пятницу будет у вас").
# Sending photos, links or answers is not delivery ("сегодня отправлю фото" passes).
_DELIVERY_VERB = (
    r"(?:достав\w*|отправ(?:им|лю|ят|ка|ляем|ляется|ится)|отгруз\w*|привез\w*|привоз\w*|вышлем"
    r"|прид[её]т|придут|приед\w*|доед\w*|дойд[её]т|получите|будет\s+у\s+вас)"
    r"(?!\s+(?:вам\s+)?(?:фото|фотк|снимк|видео|ссылк|инф|ответ|сообщ)\w*)"
)
_DELIVERY_TIME = (
    r"(?:сегодня|завтра|послезавтра"
    r"|в\s+(?:понедельник|вторник|среду|четверг|пятницу|субботу|воскресенье)"
    r"|на\s+(?:этой|следующей)\s+неделе"
    r"|через\s+(?:день|неделю|пару\s+дней|несколько\s+дней|час|пару\s+часов)"
    r"|к\s+(?:утру|вечеру|обеду|выходным|понедельнику|пятнице)"
    r"|в\s+течение\s+(?:дня|суток|недели|часа)"
    r"|день\s+в\s+день|до\s+конца\s+(?:дня|недели))"
)
DELIVERY_DATE_RE = _any(
    rf"\b{_DELIVERY_VERB}(?:\W+\w+){{0,3}}?\W+{_DELIVERY_TIME}\b",
    rf"\b{_DELIVERY_TIME}(?:\W+\w+){{0,3}}?\W+{_DELIVERY_VERB}",
    r"\b(?:deliver|ship|send|arriv)\w*\s+(?:\w+\s+){0,3}?(?:today|tomorrow|tonight)\b",
    r"\b(?:today|tomorrow)\s+(?:\w+\s+){0,3}?(?:deliver|ship|arriv)\w*",
    r"\b(?:yarın|bugün)\b[^.!?]{0,30}?\b(?:teslim|kargo|gönder)\w*",
)

# Certainty about fitment ("точно подойдёт"): only allowed when the fitment fact is verified.
FITMENT_RE = _any(
    r"\b(?:точно|однозначно|гарантированно|стопроцентно|обязательно|на\s+100\s*%|100\s*%)\s+"
    r"(?:\w+\s+)?подо(?:йд|шл|ш[её]л)\w*",
    r"\bподойд\w*\s+(?:точно|однозначно|на\s+100\s*%|100\s*%)",
    r"\bточно\s+подходит\b",
    r"\b(?:definitely|surely|certainly)\s+fits?\b",
    r"\bwill\s+(?:definitely|surely|certainly)\s+fit\b",
    r"\b100\s*%\s+fit\w*",
    r"\bkesin(?:likle)?\s+uy(?:ar|umlu)\w*",
)

# --- Completion claims -------------------------------------------------------------------------

COMPLETION_RE = _any(
    r"\bзаказ\w*\s+(?:уже\s+|успешно\s+)?"
    r"(?:оформлен|создан|принят|подтвержд[её]н|собран|отправлен|размещ[её]н)\w*",
    r"\b(?:оформил|оформили|оформила|создал|создали|разместил\w*)\s+(?:\w+\s+){0,2}?заказ\w*",
    r"\bзабронир\w*",
    r"\bбронир(?:ую|уем|овал|овала|овали)\b",
    r"\bбронь\b",
    r"\bзарезерв\w*",
    r"\bрезервир\w*",
    r"\bв\s+резерв[еу]\b",
    r"\bотлож(?:ил|ила|или|ено|ена|ены|ен|у|им)\b",
    r"(?<!будет\s)(?<!будут\s)\bотправлен[аоы]?\b",
    r"\bуже\s+(?:отправил\w*|выслал\w*|отгрузил\w*)",
    # English
    r"\b(?:reserved|booked)\b",
    r"\border\s+(?:is\s+|has\s+been\s+|was\s+)?(?:placed|confirmed|created)\b",
    r"\bput\s+(?:it\s+)?aside\b",
    r"\b(?:has\s+been|was)\s+shipped\b",
    # Turkish
    r"\brezerve\s+(?:ettim|ettik|edildi)\b",
    r"\bayırdı[mk]\b",
    r"\bsipariş\w*\s+(?:oluşturuldu|alındı|onaylandı)",
)

PAYMENT_RECEIVED_RE = _any(
    r"\bоплат\w*\s+(?:уже\s+|успешно\s+)?(?:получен|поступил|прошл|пришл|зачислен)\w*",
    r"\b(?:получил|получили|получила)\s+(?:\w+\s+)?(?:оплату|деньги|перевод|платёж|платеж)\b",
    r"\bденьги\s+(?:уже\s+)?(?:пришли|поступили|получены|зачислены)\b",
    r"(?<!будет\s)(?<!будут\s)\bоплачен[оаы]?\b",
    r"\bpayment\s+(?:has\s+been\s+|was\s+|is\s+)?(?:received|confirmed)\b",
    r"\breceived\s+(?:the\s+|your\s+)?payment\b",
    r"\bödeme\w*\s+(?:alındı|geldi|onaylandı)",
)

# --- Claims to be human (ARCHITECTURE §7.3) ----------------------------------------------------

HUMAN_CLAIM_RE = _any(
    r"\bя\s*(?:[—–-]\s*)?(?:(?:живой|реальный|настоящий|обычный)\s+)?"
    r"(?:человек|менеджер|продавец|сотрудник|консультант)\b",
    r"\bя\s+(?:[—–-]\s*)?живой\b",
    r"\bне\s+(?:бот|робот|нейросеть|программа|автоответчик)\b",
    r"\b(?:с\s+вами|вам)\s+(?:пишет|отвечает|общается|говорит|переписывается)\s+"
    r"(?:(?:живой|реальный|настоящий)\s+)?(?:человек|менеджер|продавец|сотрудник)\b",
    # English
    r"\bi(?:['’]m|\s+am)\s+(?:a\s+)?(?:(?:real|live|actual)\s+)?"
    r"(?:human|person|man|woman|manager|seller)\b",
    r"\bnot\s+a\s+(?:bot|robot|machine)\b",
    r"\bi(?:['’]m|\s+am)\s+not\s+(?:an?\s+)?(?:bot|robot|ai|machine|program)\b",
    # Turkish
    r"\bbot\s+değilim\b",
    r"\binsan(?:ım|im)\b",
    r"\bgerçek\s+(?:bir\s+)?insan\w*",
)

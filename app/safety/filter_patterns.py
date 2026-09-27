"""Phrase and token patterns used by the output filter (``app.safety.filter``).

Each public ``*_RE`` constant belongs to exactly one reason code of the filter; the mapping is in
``app.safety.filter``. Patterns match on the normalized views of ``app.safety.normalize``: the
filter runs every pattern on both the Cyrillic-folded and the Latin-folded view, so look-alike
letters do not hide a phrase. The patterns are deliberately conservative: a false positive sends
the draft to the owner, a false negative could send a banned message. Every new failure type
gets a pattern here and a test case (docs/ARCHITECTURE.md §7.2). Bump ``PATTERNS_VERSION``
whenever a pattern changes, so filter results stay traceable.

All patterns are case-insensitive unless noted. Russian first, then English and Turkish (best
effort). Every repetition is bounded, so matching stays linear in the text length.
"""

from __future__ import annotations

import re

__all__ = [
    "AT_SIGN_RE",
    "COMPLETION_RE",
    "CONTACT_CHANNEL_RE",
    "CONTACT_REDIRECT_RE",
    "CURRENCY_RE",
    "DELIVERY_DATE_RE",
    "DIGITS_RE",
    "DISCOUNT_RE",
    "EMAIL_OBFUSCATED_RE",
    "FITMENT_HEDGE_RE",
    "FITMENT_RE",
    "HUMAN_CLAIM_CASED_RE",
    "HUMAN_CLAIM_RE",
    "NEGATION_AFTER_RE",
    "NEGATION_BEFORE_RE",
    "NUMBER_WORD_RE",
    "NUMBER_WORD_SKIP_EXACT",
    "PATTERNS_VERSION",
    "PAYMENT_OFF_PLATFORM_RE",
    "PAYMENT_RECEIVED_RE",
    "PAYMENT_TERMS_RE",
    "PLATFORM_RULES_AFTER_RE",
    "RETURN_RE",
    "UNRENDERED_TOKEN_RE",
    "URL_GENERIC_RE",
    "WARRANTY_RE",
]

PATTERNS_VERSION = "2"


def _any(*alternatives: str, flags: re.RegexFlag = re.IGNORECASE) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{alt})" for alt in alternatives), flags)


# Nouns after "номер"/"по номеру" that are about the part or the order, not a contact.
_NOT_CONTACT_NOUN = (
    r"(?!\s+(?:заказ|детал|запчаст|объявлени|кузов|двигател|vin|вин|артикул|позици|вариант"
    r"|шасси|краск|птс|стс|оем|oem|каталог|[a-z0-9])\w*)"
)

# --- Rendering leftovers ----------------------------------------------------------------------

# ``{{total}}`` style placeholders that were not rendered, and masker tokens such as ``[PHONE_1]``
# that the LLM copied from the masked conversation.
UNRENDERED_TOKEN_RE = _any(
    r"\{\{[^{}]{0,200}\}\}",
    r"\[(?:EMAIL|SOCIAL|URL|CARD|PHONE|VIN|PLATE)_\d{1,4}\]",
)

# --- Contacts and off-platform channels --------------------------------------------------------

# Names of off-platform channels. Any mention is denied: the assistant has no reason to name them.
CONTACT_CHANNEL_RE = _any(
    r"\bwhat['’]?s\s?app\w*",
    r"\bwa\b",
    r"\bв[оа]т?[сц]\s?[аa]п+\w*",
    r"\btelegram\w*",
    r"\bтелег(?:а|и|у|е|ой)\b",
    r"\bтелеграм\w*",
    r"\bтг\w*",
    r"\btg\b",
    r"\bviber\b",
    r"\bвайбер\w*",
    r"\bvk\b",
    r"\bвк\b",
    r"\bвконтакт\w*",
    r"\bв\s?контакте\b",
    r"\binstagram\w*",
    r"\binsta\w*",
    r"\bинстаграм\w*",
    r"\bинст(?:а|е|у|ы|ой)\b",
    r"\bодноклассник\w*",
    r"\b(?:в|на)\s+ok\b",
    r"\bok\.ru\b",
    r"\bskype\b",
    r"\bскайп\w*",
    r"\bdiscord\w*",
    r"\bдискорд\w*",
    r"\bfacebook\b",
    r"\bфейсбук\w*",
    r"\bмессенджер\w*",
    r"\bmessenger\b",
    r"\b(?:в|на|через)\s+(?:макс|max)\b",
    r"\b(?:в|на|через)\s+(?:signal|сигнал[еу]?)\b",
    r"\be-?mail\w*",
    r"\bимейл\w*",
    r"\bемейл\w*",
    r"\bэлектронн\w*\s+почт\w*",
    r"\bмыл[оау]\b",
    r"\bличк[аеиу]\b",
    r"\b(?:в|на)\s+лс\b",
    r"\bличн\w*\s+сообщ\w*",
    r"\bв\s+директ\w*",
    r"\bdirect\s+messag\w*",
    r"\bdm\b",
)

# "Call me", "my number", "write to my e-mail", "outside Avito", "directly" and similar
# redirections or requests for contact details.
CONTACT_REDIRECT_RE = _any(
    r"\b(?:позвон|перезвон|созвон)\w*",
    r"\bзвон(?:ите|и|ить)\b",
    r"\bзвякн\w*",
    r"\bнабер(?:ите|и)\b",
    r"\b(?:мой|моя|мою|наш|наша|нашу|ваш|ваша|вашу|свой|свою|твой)\s+(?:контактн\w*\s+)?"
    r"(?:номер\w*|телефон\w*|почт[аул]|e-?mail|контакт\w*)\b" + _NOT_CONTACT_NOUN,
    r"\b(?:скин|кин|дай|дайте|давайте|остав|пришл|сообщ|продикт|отправ)\w*\s+(?:\w+\s+)?"
    r"(?:номер\w*|телефон\w*|контакт\w*)\b" + _NOT_CONTACT_NOUN,
    r"\bномер\w*\s+(?:телефон|мобильн|сотов)\w*",
    r"\bтелефон\w*\s+для\s+связи\b",
    r"\bдля\s+связи\b",
    r"\bпо\s+телефону\b",
    r"\bконтактн(?:ый|ые|ого|ых|ую)\s+(?:телефон|номер|данн)\w*",
    r"\b(?:телефон|номер|контакт|почт|e-?mail)\w*\s+(?:есть\s+|указан\w*\s+)?"
    r"в\s+(?:профил|описани|объявлени|шапк)\w*",
    r"\bв\s+описании\s+профил\w*",
    # "write/add/contact us IN/ON <somewhere>" unless it is this chat or Avito itself
    r"\b(?:напиш|пиш|черкн|добав|стуч|свяж|связыв)\w*\s+(?:мне\s+|нам\s+|нас\s+|меня\s+)?"
    r"(?:в|во|на)\s+(?!(?:чат|этот|этом|эту|авито|avito|любое|любой|ответ|приложени|корзин"
    r"|поддержк|комментари|течение|свободн|удобн)\w*)[\w-]+",
    r"\bнапрямую\b",
    r"\bбез\s+авито\b",
    r"\b(?:вне|мимо|минуя)\s+авито\b",
    r"\bв\s+обход\s+авито\b",
    r"\bне\s+через\s+авито\b",
    r"\b(?:ищ|найд|поищ)\w*\s+(?:нас|меня|магазин\w*|по\s+названию)\b",
    r"\bв\s+поиск[еу]\b",
    r"\b(?:за|по)гугл\w*",
    r"\bнаш\w*\s+сайт\w*",
    r"\bдомен\w*",
    r"\bпочт\w*\s+(?:\w+\s+){0,2}?на\s+(?:яндекс|гугл|gmail|мейл|mail|рамблер)\w*",
    # English
    r"\b(?:call|text|phone|ring|message)\s+me\b",
    r"\bmy\s+(?:phone|number|cell|mobile|email|e-mail|whatsapp|telegram)\b",
    r"\b(?:phone|cell|mobile)\s+number\b",
    r"\b(?:contact|reach)\s+me\b",
    r"\bdm\s+me\b",
    r"\boutside\s+(?:of\s+)?avito\b",
    r"\bdirectly\b",
    # Turkish
    r"\btelefon\s+numara\w*",
    r"\bbeni\s+ara\w*",
    r"\bnumaram\w*",
    r"\bavito\s+dışında\b",
)

# Spelled-out or split e-mail addresses: "ivan(at)example", "ivan @ example.com", "собака".
EMAIL_OBFUSCATED_RE = _any(
    r"[\[({]\s*(?:at|dot|собака|точка)\s*[\])}]",
    r"\w\s+(?:at|собака)\s+\w+\s+(?:dot|точка)\s+\w",
    r"\bсобак[аеу]\b",
)
AT_SIGN_RE = re.compile(r"@")

# URLs the masker's host list does not know: any scheme, "//host", any Latin TLD, Cyrillic TLDs
# and domains with an obfuscated dot ("example[.]com", "example .com", "example точка ру").
_KNOWN_TLDS = (
    r"ru|рф|ру|su|com|ком|net|org|info|biz|pro|me|io|shop|store|online|site|xyz|by|kz|ua|uz"
    r"|de|рус|москва|market|ly|cc|tk|ws"
)
_OBFUSCATED_DOT = (
    r"(?:\s*[\[({]\s*(?:\.|dot|точка)\s*[\])}]\s*|\s+\.\s*|\.\s+|\s+(?:dot|точка|тчк)\s+"
    r"|[,。ˌ·•・‧⸳])"
)
URL_GENERIC_RE = _any(
    r"\b[a-z][a-z0-9+.-]{1,15}://[^\s<>\"'«»]{0,2000}",
    r"(?<![\w/:])//[a-z0-9а-яё][^\s<>\"'«»]{0,2000}",
    r"(?<![\w@.-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.){1,10}"
    r"(?:[a-z]{2,24}|xn--[a-z0-9-]{1,59})(?![\w-])(?:[/?#][^\s<>\"'«»]{0,2000})?",
    r"(?<![\w@.-])(?:[а-яё0-9](?:[а-яё0-9-]{0,61}[а-яё0-9])?\.){1,10}"
    r"(?:рф|рус|москва|ру|бел|укр|онлайн|сайт|орг|ком|дети)(?![\w-])(?:/[^\s<>\"'«»]{0,2000})?",
    rf"(?<![\w.-])[a-zа-яё0-9][a-zа-яё0-9-]{{0,62}}{_OBFUSCATED_DOT}(?:{_KNOWN_TLDS})(?![\w-])",
)

# --- Off-platform payment ----------------------------------------------------------------------

_PAY_TARGET = (
    r"(?:карт\w*|сч[её]т\w*|сбер\w*|т-?банк\w*|тинь?к\w*|тинек\w*|альф\w*|втб|райф\w*"
    r"|газпром\w*|озон\w*|киви|qiwi|юmoney|юмани|номер\w*|телефон\w*|кошел\w*)"
)
PAYMENT_OFF_PLATFORM_RE = _any(
    r"\bна\s+(?:\w+\s+){0,2}?карт(?:у|очку)\b",
    r"\bсберкарт\w*",
    rf"\b(?:перев(?:[её]д|од|ест)\w*|скин\w*|кин(?:ь|ьте|уть)|закин\w*)\s+(?:\w+\s+){{0,3}}?"
    rf"(?:на\s+|по\s+)?{_PAY_TARGET}",
    r"\bпереводом\b",
    r"\bпред[\s-]?оплат\w*",
    r"\bс\W?б\W?п\w*",
    r"\bсистем\w*\s+быстрых\s+платеж\w*",
    r"\bпо\s+номеру\b" + _NOT_CONTACT_NOUN,
    r"\bномер\w*\s+(?:вашей\s+|моей\s+|банковской\s+)?карт\w*",
    r"\bреквизит\w*",
    r"\bсбер(?:банк\w*|а|у|ом|е)?\b",
    r"\bтинь?к\w*",
    r"\bтинек\w*",
    r"\bт-?банк\w*",
    r"\bальф(?:а|у|е|ой)?[\s-]?банк\w*",
    r"\b(?:на|в)\s+альф[уе]\b",
    r"\bвтб\b",
    r"\bрайф\w*",
    r"\bгазпромбанк\w*",
    r"\bозон\s*банк\w*",
    r"\bюкасс\w*",
    r"\b(?:qiwi|киви|юmoney|юмани|webmoney|вебмани|paypal|пейпал)\b",
    r"\bqr\b",
    r"\bqr-?код\w*",
    r"\bкуар\w*",
    r"\bна\s+(?:\w+\s+)?(?:расч[её]тный\s+)?сч[её]т\b",
    r"\bкошел[её]к\w*",
    r"\bкошельк\w*",
    r"\bкрипт\w*",
    r"\b(?:usdt|btc)\b",
    r"\bбиткоин\w*",
    r"\bаванс\w*",
    r"\bзадат(?:ок|ка|ком|ку)\b",
    r"\bоплат\w*\s+(?:вперёд|вперед|заранее|напрямую)\b",
    r"\bоплатите\s+(?:мне\s+)?напрямую\b",
    r"\bчастичн\w*\s+оплат\w*",
    r"\bполовин\w*\s+сразу\b",
    r"\bбез\s+безопасн\w*\s+сделк\w*",
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

# Payment terms the owner has not confirmed yet (decision D-l, B-005): cash, payment on meeting,
# card on receipt. Denied until the owner's business rules are known.
PAYMENT_TERMS_RE = _any(
    r"\bналичн\w*",
    r"\bналичк\w*",
    r"\bнал(?:ом|ик\w*)\b",
    r"\bпри\s+встрече\b",
    r"\b(?:картой|карточкой|переводом)\s+при\s+получени\w*",
    r"\bcash\b",
    r"\bnakit\b",
)

# --- Numbers and money -------------------------------------------------------------------------

DIGITS_RE = re.compile(r"[0-9]+")

CURRENCY_RE = _any(
    r"[₽$€£¥₺₸₴]",
    r"\bруб(?:л[ьеяюи]\w*)?\b\.?",
    r"(?<=\d)\s?р\.?(?!\w)",
    r"\bт\.?\s?р\.?(?!\w)",
    r"\bрэ\b",
    r"\bдеревянн\w*",
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

# Russian number words and money slang (best effort, ARCHITECTURE §7.2). "один/одна/одно" and
# "штука" are NOT included: they are too common in ordinary sentences ("один момент", "одна
# штука"). Ordinals ("второй") are not included.
_RU_NUMBER_WORDS = (
    r"ноль|нол[яюе]|нул[ьяюе]|нул[её]м"
    r"|дв[ае]|двух|двум|двумя|двое|двуш(?:ка|ку|ки|кой)"
    r"|три|тр[её]х|тр[её]м|тремя|трое|тр[её]ш(?:ка|ку|ки|кой)"
    r"|четыре|четыр[её]х|четыр[её]м|четырьмя"
    r"|пять|пяти|пятью|шесть|шести|шестью|семь|семи|семью"
    r"|пят[её]р(?:ка|ку|ки|кой)|пятихат\w*|пятнаш\w*"
    r"|восемь|восьми|восемью|девять|девяти|девятью"
    r"|десять|десяти|десятью|десят(?:ок|ка|ку|ки)|десяточк\w*"
    r"|(?:одинн|двен|трин|четырн|пятн|шестн|семн|восемн|девятн)адцат\w*"
    r"|(?:дв|тр)адцат\w*"
    r"|сорок|сорока|пятьдесят|пятидесят\w*|шестьдесят|шестидесят\w*|семьдесят|семидесят\w*"
    r"|восемьдесят|восьмидесят\w*|девяносто|девяноста|полтос\w*"
    r"|сто|ста|сотн\w*|сот(?:к[аиуе]|ен)|пол[\s-]?сотн\w*"
    r"|двести|двухсот\w*|триста|тр[её]хсот\w*|четыреста|четыр[её]хсот\w*"
    r"|пятьсот|пятисот\w*|шестьсот|шестисот\w*|семьсот|семисот\w*"
    r"|восемьсот|восьмисот\w*|девятьсот|девятисот\w*"
    r"|тысяч\w*|тысч\w*|тыщ\w*|тыс|косар\w*|косых"
    r"|миллион\w*|млн|миллиард\w*|млрд"
    r"|полтора|полторы|полутора|полтинник\w*|пол[- ]?цен\w*|половин\w*"
    r"|треть|трети|третью|четверть|четверти"
    r"|процент\w*"
)
_EN_NUMBER_WORDS = (
    r"two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
    r"|(?:thir|four|fif|six|seven|eigh|nine)teen"
    r"|(?:twen|thir|for|fif|six|seven|eigh|nine)ty"
    r"|hundred\w*|thousand\w*|million\w*|grand|percent"
)
# Turkish "bir", "altı", "on", "yüz" and "bin" are also ordinary words and are NOT included.
_TR_NUMBER_WORDS = (
    r"iki|üç|dört|beş|yedi|sekiz|dokuz|yirmi|otuz|kırk|elli|altmış|yetmiş|seksen|doksan|milyon"
)
NUMBER_WORD_RE = _any(
    rf"\b(?:{_RU_NUMBER_WORDS}|{_EN_NUMBER_WORDS}|{_TR_NUMBER_WORDS})\b",
    r"%",
)
# Exact (case-sensitive) matches of NUMBER_WORD_RE that are not numbers: "СТО" is a service
# station (станция техобслуживания).
NUMBER_WORD_SKIP_EXACT = frozenset({"СТО"})

# --- Promises that only a business-rule template may make ---------------------------------------

DISCOUNT_RE = _any(
    r"\bскид(?:к|оч)\w*",
    r"\bуступ\w*",
    r"\bдоговорим\w*",
    r"\bцен\w*\s+(?:обсужда\w*|договорн\w*)",
    r"\bобсуждаем\w*",
    r"\bподвин\w*",
    r"\bскину\s+(?:немного|цену|пару|до|ещё|еще|чуть|вам)\b",
    r"\bсбро(?:шу|сим)\s+(?:цену|немного|пару|чуть)\b",
    r"\bсбав\w*",
    r"\b(?:можно|могу|сделаю|сделаем|отдам|отдадим|продам|продадим|будет)\s+(?:\w+\s+){0,2}?"
    r"(?:по)?дешевле\b",
    r"\bдешевле\s+(?:отдам|отдадим|продам|сделаю|сделаем)\b",
    r"\bуценк\w*",
    r"\bакци[яиюей]\w*",
    r"\bспец\s?цен\w*",
    r"\bспециальн\w*\s+цен\w*",
    r"\bсебестоимост\w*",
    r"\bв\s+подарок\b",
    r"\bподар(?:ю|им)\b",
    r"\bза\s+(?:наш|мой|свой)\s+сч[её]т\b",
    r"\bбесплатн\w*",
    r"\bдаром\b",
    r"\bторг\b",
    r"\bминус\s+(?:\w+\s+)?процент\w*",
    r"\bdiscount\w*",
    r"\bfor\s+free\b",
    r"\bfree\s+(?:delivery|shipping)\b",
    r"\bindirim\w*",
    r"\bbedava\b",
    r"\bücretsiz\b",
)

RETURN_RE = _any(
    r"\bвозврат(?!н)\w*",
    r"\bвозвращ\w*",
    r"\bверн[её]м\b",
    r"\bверну\b(?!\s+(?:вам\s+)?ответ)",
    r"\bвернуть\b",
    r"\bденьги\s+(?:назад|обратно)\b",
    r"\b(?:прим|забер)(?:ем|ём|у)\s+(?:\w+\s+)?(?:обратно|назад)\b",
    r"\bобмен\w*",
    r"\bзамен(?:им|ю)\b",
    r"\bзамена\b(?=\s*(?:[.!,;]|$))",
    r"\bпоменя(?:ем|ю)\b",
    r"\brefund\w*",
    r"\bmoney\s+back\b",
    r"\breturn\w*",
    r"\biade\w*",
)

WARRANTY_RE = _any(
    r"\bгарант\w*",
    r"\bручаюсь\b",
    r"\bотвечаю\s+за\s+качеств\w*",
    r"\bбудет\s+работать\b",
    r"\bwarrant\w*",
    r"\bguarant\w*",
    r"\bgaranti\w*",
)

# A delivery/dispatch verb near a concrete time ("доставим завтра", "в пятницу будет у вас").
# Sending photos, links or answers is not delivery ("сегодня отправлю фото" passes).
_DELIVERY_VERB = (
    r"(?:достав\w*|отправ(?:им|лю|ят|ка|ку|ляем|ляется|ится)|отгруз\w*|привез\w*|привоз\w*"
    r"|вышлем|прид[её]т|придут|приед\w*|доед\w*|дойд[её]т|получите|будет\s+у\s+вас|у\s+вас"
    r"|будет|успе\w*|займ[её]т)"
    r"(?!\s+(?:вам\s+)?(?:фото|фотк|снимк|видео|ссылк|инф|ответ|сообщ)\w*)"
)
_WEEKDAY = r"(?:понедельник|вторник|сред|четверг|пятниц|суббот|воскресень)\w*"
_DELIVERY_TIME = (
    r"(?:сегодня|завтра|послезавтра"
    rf"|в\s+{_WEEKDAY}|до\s+{_WEEKDAY}|к\s+{_WEEKDAY}"
    r"|на\s+(?:этой|следующей)\s+неделе|на\s+днях|на\s+следующий\s+день"
    r"|через\s+(?:\w+\s+)?(?:день|дня|дней|недел\w*|час\w*|сутки|суток)"
    r"|за\s+(?:\w+\s+)?(?:день|дня|дней|сутки|суток|час\w*)"
    r"|к\s+(?:утру|вечеру|обеду|выходным)|до\s+(?:выходных|вечера)"
    r"|в\s+течение\s+(?:\w+\s+)?(?:дня|дней|суток|недел\w*|час\w*)"
    r"|день\s+в\s+день|до\s+конца\s+(?:дня|недели)|день)"
)
DELIVERY_DATE_RE = _any(
    rf"\b{_DELIVERY_VERB}(?:\W+\w+){{0,3}}?\W+{_DELIVERY_TIME}\b",
    rf"\b{_DELIVERY_TIME}(?:\W+\w+){{0,3}}?\W+{_DELIVERY_VERB}",
    r"\b(?:deliver|ship|send|arriv)\w*\s+(?:\w+\s+){0,3}?(?:today|tomorrow|tonight)\b",
    r"\b(?:today|tomorrow)\s+(?:\w+\s+){0,3}?(?:deliver|ship|arriv)\w*",
    r"\b(?:yarın|bugün)\b[^.!?]{0,30}?\b(?:teslim|kargo|gönder)\w*",
)

# Affirmative fitment claims (decision D-c). Allowed only when the fitment fact is verified, or in
# a question/hedge sentence (FITMENT_HEDGE_RE), or negated ("не подойдёт").
FITMENT_RE = _any(
    r"\bподо(?:йд[её]т|йдут|шл[аио]|ш[её]л)\b",
    r"\bподход(?:ит|ят)\b",
    r"\bвстан(?:ет|ут)\b",
    r"\bсовместим\w*",
    r"\bfits?\b",
    r"\bwill\s+fit\b",
    r"\bcompatible\b",
    r"\buyumlu\w*",
    r"\buyar\b",
)
FITMENT_HEDGE_RE = _any(
    r"\bли\b",
    r"\?",
    r"\bесли\b",
    r"\bпровер\w*",
    r"\bуточн\w*",
    r"\bif\b",
    r"\bcheck\w*",
)

# --- Completion claims -------------------------------------------------------------------------

COMPLETION_RE = _any(
    r"\bзаказ\w*\s+(?:уже\s+|успешно\s+)?"
    r"(?:оформлен|создан|принят|подтвержд[её]н|собран|отправлен|размещ[её]н|готов)\w*",
    r"\bзаказ\w*\s+(?:ваш|за\s+вами)\b",
    r"\b(?:оформил|оформили|оформила|создал|создали|разместил\w*|собрал\w*|подтвердил\w*"
    r"|принял\w*)\s+(?:\w+\s+){0,2}?заказ\w*",
    r"\bоформил[аи]?\b",
    r"(?<!будет\s)(?<!будут\s)\bоформлен[оаы]?\b",
    r"\bзабронир\w*",
    r"\bбронир(?:ую|уем|овал|овала|овали)\b",
    r"\bбронь\b",
    r"\bзарезерв\w*",
    r"\bрезервир\w*",
    r"\bрезерв(?:е|у|а|ом)?\b",
    r"\bотлож(?:ил|ила|или|ено|ена|ены|ен|у|им)\b",
    r"\bпридерж\w*",
    r"\bдержу\s+(?:\w+\s+)?для\b",
    r"\bоставил\w*\s+(?:\w+\s+)?для\b",
    r"\bоставлю\s+(?:\w+\s+)?(?:для|за)\b",
    r"\b(?:закрепил|записал)\w*\s+за\b",
    r"\bникому\s+не\s+продам\b",
    r"\bснял\w*\s+(?:с\s+продажи|объявлени\w*)",
    r"\b(?:вс[её])\s+готово\b",
    r"(?<!будет\s)(?<!будут\s)\bотправлен[аоы]?\b",
    r"\bотправил[аи]?\b",
    r"\bвыслал\w*",
    r"\bупакова\w*",
    r"\bпередал\w*\s+в\b",
    r"\bсдал\w*\s+в\b",
    r"\bв\s+пути\b",
    r"\bтрек\w*",
    r"\bпосылк\w*\s+(?:уже\s+)?едет\b",
    r"\bуже\s+(?:отправил\w*|выслал\w*|отгрузил\w*)",
    # English
    r"\b(?:reserved|booked|shipped|sent|dispatched)\b",
    r"\border\s+(?:is\s+|has\s+been\s+|was\s+)?(?:placed|confirmed|created)\b",
    r"\bput\s+(?:it\s+)?aside\b",
    r"\bset\s+aside\b",
    r"\bon\s+hold\b",
    r"\bit['’]?s\s+yours\b",
    # Turkish
    r"\brezerve\s+(?:ettim|ettik|edildi)\b",
    r"\bayırdı[mk]\b",
    r"\bsipariş\w*\s+(?:oluşturuldu|alındı|onaylandı)",
)

PAYMENT_RECEIVED_RE = _any(
    r"\bоплат\w*\s+(?:уже\s+|успешно\s+)?(?:получен|поступил|прошл|пришл|зачислен|вижу|есть)\w*",
    r"\b(?:получил|получили|получила|вижу)\s+(?:\w+\s+)?(?:оплату|деньги|перевод|платёж|платеж)\b",
    r"\bденьги\s+(?:уже\s+)?(?:получил\w*|пришли|поступили|получены|зачислены|дошли)\b",
    r"\bплат[её]ж\w*\s+(?:уже\s+)?(?:прош[её]л|поступил|получен)\w*",
    r"(?<!будет\s)(?<!будут\s)\bоплачен[оаы]?\b",
    r"\bpayment\s+(?:has\s+been\s+|was\s+|is\s+)?(?:received|confirmed)\b",
    r"\breceived\s+(?:the\s+|your\s+)?payment\b",
    r"\bödeme\w*\s+(?:alındı|geldi|onaylandı)",
)

# --- Negation and platform-rule context --------------------------------------------------------
# Applied to promises, completion claims and contact redirects (not to channels, payment or
# claims to be human). NEGATION_BEFORE_RE must match right before the finding, NEGATION_AFTER_RE
# right after it.

NEGATION_BEFORE_RE = _any(
    r"\b(?:не|нет|нельзя)\s+(?:(?:ещё|еще|пока|уже)\s+)?$",
    r"\bне\s+(?:делаем|даём|даем|предоставляем|принимаем|работаем|берём|берем|оформляем"
    r"|предусмотрен\w*)\s+$",
)
NEGATION_AFTER_RE = _any(
    r"^\s*(?:[\w-]+\s+)?(?:нет|нельзя|отсутству\w*|невозможн\w*)\b",
    r"^\s*(?:[\w-]+\s+)?не\s+(?:предусмотрен|да[её]м|дела|предоставля|возможн|бывает|работа"
    r"|принима|нуж|получится|требу|оформля|производ)\w*",
)
# "Возврат по правилам Авито": a reference to Avito's own rules, not a promise of ours.
PLATFORM_RULES_AFTER_RE = _any(r"^[^.!?\n]{0,40}?\bпо\s+правилам\s+авито")

# --- Claims to be human (ARCHITECTURE §7.3) ----------------------------------------------------

_ROLES = (
    r"(?:человек|менеджер|продавец|продавщица|сотрудник|консультант|владелец|хозяин|оператор"
    r"|специалист|мастер|механик|администратор|директор)"
)
# "Я продавец-бот", "я консультант, бот" are honest (decision D-4).
_NOT_BOT_AFTER = r"(?![-‐–]?\s*(?:бот|робот|помощник|ассистент|автомат)\w*)"
_BOT_WORDS = (
    r"(?:бот|робот|нейросеть|программа|автоответ\w*|автоматическ\w*(?:\s+помощник)?|ии|ai"
    r"|искусственн\w*\s+интеллект)"
)
HUMAN_CLAIM_RE = _any(
    r"\bя\s*(?:[—–-]\s*)?(?:(?:живой|реальный|настоящий|обычный|сам|тут|здесь)\s+)?"
    + _ROLES
    + r"\b"
    + _NOT_BOT_AFTER,
    r"\bя\s*(?:[—–-]\s*)?живой\b",
    r"\b(?:с\s+вами|вам)\s+(?:на\s+связи\s+|пишет\s+|отвечает\s+|общается\s+|говорит\s+"
    r"|переписывается\s+)?(?:(?:живой|реальный|настоящий)\s+)?" + _ROLES + r"\b" + _NOT_BOT_AFTER,
    # "не бот" as a statement, but not "не программа лояльности" / "не робот-пылесос" (D-6)
    rf"\bне\s+{_BOT_WORDS}(?=\s*(?:[,.!?;)]|$)|\s+(?:а|и)\b)",
    r"\bникакой\s+(?:я\s+)?не\s+бот",
    r"\bменя\s+зовут\s+(?!(?:помощник|бот|ассистент|виртуальн|автоматическ)\w*)",
    r"\bя\s+(?:\w+\s+)?сам\b",
    r"\bсам\s+отвечаю\b",
    r"\bотвечаю\s+лично\b",
    r"\bлично\s+я\b",
    r"\bпишу\s+(?:вам\s+)?сам\b",
    r",\s+(?:менеджер|продавец|владелец|сотрудник|консультант)\s+(?:магазина|компании)\b",
    # English
    r"\bi(?:['’]m|\s+am)\s+(?:the\s+|a\s+|an\s+)?(?:(?:real|live|actual)\s+)?"
    r"(?:human|person|man|woman|manager|seller|owner|operator)\b(?!['’]s)",
    r"\bnot\s+a\s+(?:bot|robot|machine)\b",
    r"\bi(?:['’]m|\s+am)\s+not\s+(?:an?\s+)?(?:bot|robot|ai|machine|program)\b",
    # Turkish
    r"\bbot\s+değilim\b",
    r"\binsan(?:ım|im)\b",
    r"\bgerçek\s+(?:bir\s+)?insan\w*",
    r"\bsatıcı(?:yım|yim)\b",
)
# Case-sensitive: a capitalised first name introducing the writer ("на связи Иван", "это Иван",
# "I'm Ivan"). Only when the name ends the phrase (comma, "!" or end of text).
HUMAN_CLAIM_CASED_RE = _any(
    r"(?i:\b(?:это|пишет|с\s+вами|на\s+связи|я))\s+[А-ЯЁ][а-яё]{2,}(?=\s*(?:[,!]|$))",
    r"(?i:\bi(?:['’]m|\s+am))\s+[A-Z][a-z]{2,}\b(?!['’]s)",
    flags=re.NOFLAG,
)

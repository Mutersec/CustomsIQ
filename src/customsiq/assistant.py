"""A free, rule-based assistant: plain-language cost questions and site help.

No language model is involved. A message such as "10 t of apples from Turkey,
1000 EUR per tonne, what does it cost?" is taken apart with regular expressions
and word lists into the facts a duty calculation needs (goods, origin, quantity,
price), and the answer comes from the same `classify` and `calculate_duty`
functions the rest of the app uses. Nothing is invented: when a fact is missing
the assistant asks for it, and when no duty rate is on record for a code it says
so instead of guessing one.

The conversation is stateless on the server. Each reply carries a `context`
(the facts gathered so far) that the page sends back with the next message.
"""

import re
import sqlite3
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

from src.customsiq.assistant_glossary import (
    COUNTRY_LABELS,
    COUNTRY_NAMES,
    EU_MEMBERS,
    PRODUCTS_DE,
    PRODUCTS_TR,
)
from src.customsiq.assistant_texts import (
    FAQ,
    SUGGESTIONS,
    SUPPORT_FALLBACK,
    SUPPORT_SUGGESTIONS,
    TEXT,
)
from src.customsiq.cn_classifier import classify
from src.customsiq.embargo_screener import screen_entity
from src.customsiq.exceptions import InvalidQueryError, RateNotFoundError
from src.customsiq.tariff_calculator import calculate_duty

LANGUAGES = ("en", "tr", "de")
MAX_MESSAGE = 300

_LETTER = "a-zçğıöşüäß"
_CENTS = Decimal("0.01")


def normalize(text: str) -> str:
    """Lower-case with Turkish rules (İ -> i, I -> ı) and one kind of apostrophe."""
    # "Iran", "Indien", "Italy": a capital I opening a lower-case word is a dotted
    # i in every language but Turkish, and no Turkish place or product name in the
    # glossary starts with ı. ponytail: all-caps "IRAN" still becomes "ıran".
    text = re.sub(r"\bI(?=[a-zçğöşüäß])", "i", text)
    text = text.replace("İ", "i").replace("I", "ı").lower()
    return re.sub(r"[’‘`´]", "'", text)


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

_NUMBER = r"\d+(?:[.,\s]\d{3})*(?:[.,]\d+)?|\d+"


def parse_number(raw: str) -> Optional[Decimal]:
    """Read "10.000,50", "10,000.50", "2,5", "2.5" or "1 000" as a Decimal."""
    raw = raw.strip().replace(" ", "")
    if not raw:
        return None
    if "," in raw and "." in raw:
        decimal_mark = "," if raw.rfind(",") > raw.rfind(".") else "."
        thousands = "." if decimal_mark == "," else ","
        raw = raw.replace(thousands, "").replace(decimal_mark, ".")
    elif "," in raw or "." in raw:
        mark = "," if "," in raw else "."
        parts = raw.split(mark)
        # "10.000" / "1,250,000": every group after the first is three digits.
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]) and len(parts[0]) <= 3:
            raw = "".join(parts)
        else:
            raw = raw.replace(mark, ".")
    try:
        return Decimal(raw)
    except ArithmeticError:
        return None


# ---------------------------------------------------------------------------
# Parsing a message into facts
# ---------------------------------------------------------------------------

_UNITS = {
    "t": ("ton", "tons", "tonne", "tonnes", "tonnen", "t", "tonluk"),
    "kg": ("kg", "kilo", "kilogram", "kilogramm", "kilos", "kgs", "kiloluk"),
    "piece": (
        "adet",
        "tane",
        "pcs",
        "pc",
        "piece",
        "pieces",
        "units",
        "unit",
        "stück",
        "stk",
        "parça",
    ),
}
_UNIT_OF = {word: unit for unit, words in _UNITS.items() for word in words}
_UNIT_WORDS = "|".join(sorted(_UNIT_OF, key=len, reverse=True))

_CURRENCIES = {
    "EUR": ("€", "eur", "euro", "euros", "avro"),
    "USD": ("$", "usd", "dolar", "dollar", "dollars"),
    "GBP": ("£", "gbp", "sterlin", "pound", "pounds", "pfund"),
    "TRY": ("₺", "tl", "try", "lira"),
}
_CURRENCY_OF = {word: code for code, words in _CURRENCIES.items() for word in words}
_CURRENCY_WORDS = "|".join(re.escape(w) for w in sorted(_CURRENCY_OF, key=len, reverse=True))

_QUANTITY = re.compile(rf"(?<![\d.,])({_NUMBER})\s*({_UNIT_WORDS})(?![{_LETTER}-])")
#: "500 t-shirts": a count straight before a word is a number of pieces.
_COUNT = re.compile(rf"(?<![\d.,])(\d+)\s+(?=[{_LETTER}])")
#: "1000 dolarlık", "500 euroluk": Turkish "worth of" suffix after the currency.
_MONEY_AFTER = re.compile(
    rf"(?<![\d.,])({_NUMBER})\s*({_CURRENCY_WORDS})(?:l[ıiuü]k)?(?![{_LETTER}])"
)
_MONEY_BEFORE = re.compile(rf"({_CURRENCY_WORDS})\s*({_NUMBER})")

#: Words right next to a price that say it is per unit, and of which unit.
_PER_UNIT = {
    "t": (
        "ton fiyat",
        "tonu",
        "tonunu",
        "tonuna",
        "/ton",
        "/t",
        "per ton",
        "per tonne",
        "a ton",
        "a tonne",
        "pro tonne",
        "je tonne",
        "/tonne",
        "tonbaşı",
        "ton başı",
        "ton başına",
    ),
    "kg": (
        "kg fiyat",
        "kilo fiyat",
        "kilosu",
        "kilogramı",
        "/kg",
        "per kg",
        "a kilo",
        "pro kg",
        "je kg",
        "kg başı",
        "kilo başı",
    ),
    "piece": (
        "tanesi",
        "adedi",
        "adet fiyat",
        "birim fiyat",
        "tane başı",
        "/adet",
        "/pc",
        "/piece",
        "each",
        "apiece",
        "per piece",
        "per unit",
        "unit price",
        "pro stück",
        "je stück",
        "stückpreis",
        "/stück",
    ),
}
_TOTAL_WORDS = ("toplam", "total", "insgesamt", "gesamt", "hepsi", "tamamı", "in total")

_CODE_HINT = re.compile(
    r"(?:gtip|gtıp|hs|cn|taric|kod|kodu|code|zolltarif\w*|tarifnummer)\s*(?:no\.?|numarası|:)?\s*"
    r"(\d{4}(?:[.\s]?\d{2}){1,3})"
)
_DOTTED_CODE = re.compile(r"(?<![\d.,])(\d{4}\.\d{2}(?:\.\d{2}){0,2})(?![\d,])")

_ABLATIVE = ("dan", "den", "tan", "ten")
_TR_SUFFIXES = (
    "dan",
    "den",
    "tan",
    "ten",
    "ya",
    "ye",
    "a",
    "e",
    "da",
    "de",
    "ta",
    "te",
    "dayım",
    "deyim",
    "dayız",
    "deyiz",
    "nın",
    "nin",
    "ın",
    "in",
    "lı",
    "li",
)
_SUFFIX_PATTERN = "|".join(sorted(_TR_SUFFIXES, key=len, reverse=True))
_FROM_WORDS = ("from", "aus", "von", "menşei", "menşe", "origin", "ursprung")
_TO_WORDS = ("to", "into", "nach", "in die", "in den")

_COUNTRY_PATTERNS = sorted(
    ((name, code) for code, names in COUNTRY_NAMES.items() for name in names),
    key=lambda pair: len(pair[0]),
    reverse=True,
)

_INTENT_WORDS = {
    "screen": (
        "yaptırım",
        "yaptirim",
        "sanction",
        "sanktion",
        "embargo",
        "screen",
        "taramas",
        "tara ",
        "denied party",
        "yasaklı",
        "kara liste",
    ),
    "cost": (
        "maliyet",
        "hesapla",
        "vergi",
        "gümrük",
        "ne kadar",
        "tutar",
        "cost",
        "duty",
        "how much",
        "tariff",
        "landed",
        "zoll",
        "kosten",
        "abgabe",
        "wie viel",
        "berechne",
    ),
    "classify": (
        "gtip",
        "gtıp",
        "hs kod",
        "hs code",
        "cn kod",
        "cn code",
        "hangi kod",
        "kodu ne",
        "classify",
        "sınıflandır",
        "which code",
        "zolltarifnummer",
        "einreihung",
        "welche nummer",
    ),
}

#: Words that are never part of a product name.
_STOPWORDS = set(
    """
    ben biz sen siz o bu şu bir iki ve ile için ama de da mi mı mu mü ne kaç nasıl
    getireceğim getirmek getiriyorum getirdim getirece getir ithal ithalat ithalatı
    yapacağım yapmak istiyorum istiyoruz alacağım almak satın aldım sipariş ettim
    maliyeti maliyetini maliyet hesapla hesaplar hesaplayın hesaplayabilir misin
    vergi vergisi vergisini gümrük gümrüğü tutar tutarı toplam fiyat fiyatı fiyatıyla
    fiyatla bedeli bedel tonu tonunu kilosu tanesi adedi başı başına birim olarak
    türkiyedeyim buradayım lütfen acaba kadar tutacak eder olur öder ödeyeceğim
    gtip kodu kod hangi nedir sınıflandır
    i we you it the a an of for and to from into at in per each with my our me
    import importing imported buy buying bought order ordered want would like
    calculate calculation cost costs price priced total duty tariff how much what is
    please can could will need landed value worth code which classify
    ich wir sie es der die das dem den des ein eine einen einem einer
    von aus nach mit und für pro je zu im
    importieren import kaufe kaufen berechne berechnen kosten preis gesamt insgesamt
    zoll wie viel welche nummer bitte
    """.split()
)


def _find_countries(text: str) -> tuple[Optional[str], Optional[str], list[tuple[int, int]]]:
    """Return (origin, destination, spans to blank out) from a normalized message."""
    found: list[tuple[int, str, str, int]] = []  # (start, code, role, end)
    taken: list[tuple[int, int]] = []
    for name, code in _COUNTRY_PATTERNS:
        pattern = re.compile(
            rf"(?<![{_LETTER}]){re.escape(name)}(?:'?({_SUFFIX_PATTERN}))?(?![{_LETTER}])"
        )
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            if any(s < span[1] and span[0] < e for s, e in taken):
                continue
            taken.append(span)
            suffix = match.group(1) or ""
            before = text[max(0, span[0] - 12) : span[0]]
            if suffix in _ABLATIVE or any(before.rstrip().endswith(w) for w in _FROM_WORDS):
                role = "origin"
            elif suffix in ("ya", "ye", "a", "e") or any(
                before.rstrip().endswith(w) for w in _TO_WORDS
            ):
                role = "destination"
            elif suffix in ("dayım", "deyim", "dayız", "deyiz", "da", "de", "ta", "te"):
                role = "location"
            else:
                role = "unmarked"
            found.append((span[0], code, role, span[1]))
    found.sort()
    origin = next((c for _, c, r, _ in found if r == "origin"), None)
    destination = next((c for _, c, r, _ in found if r in ("destination", "location")), None)
    if origin is None:
        unmarked = [c for _, c, r, _ in found if r == "unmarked" and c != destination]
        if unmarked:
            origin = unmarked[0]
    return origin, destination, taken


def _find_price(text: str) -> tuple[Optional[dict], list[tuple[int, int]]]:
    """Return the first money amount with its basis ("unit" per t/kg/piece, or "total")."""
    candidates = []
    for match in _MONEY_AFTER.finditer(text):
        candidates.append((match.start(), match.end(), match.group(1), match.group(2)))
    for match in _MONEY_BEFORE.finditer(text):
        candidates.append((match.start(), match.end(), match.group(2), match.group(1)))
    if not candidates:
        return None, []
    candidates.sort()
    start, end, number, currency_word = candidates[0]
    amount = parse_number(number)
    if amount is None:
        return None, []
    window = text[max(0, start - 22) : min(len(text), end + 16)]
    basis, unit = "total", None
    for unit_name, markers in _PER_UNIT.items():
        if any(marker in window for marker in markers):
            basis, unit = "unit", unit_name
            break
    explicit_total = any(word in window for word in _TOTAL_WORDS)
    if explicit_total:
        basis, unit = "total", None
    return (
        {
            "amount": str(amount),
            "currency": _CURRENCY_OF.get(currency_word, "EUR"),
            "basis": basis,
            "unit": unit,
            "assumed_total": basis == "total" and not explicit_total,
        },
        [(start, end)],
    )


def _find_code(text: str) -> tuple[Optional[str], list[tuple[int, int]]]:
    for pattern in (_CODE_HINT, _DOTTED_CODE):
        match = pattern.search(text)
        if match:
            code = re.sub(r"\D", "", match.group(1))
            if len(code) in (6, 8, 10):
                return code, [match.span()]
    return None, []


def _blank(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in spans:
        for i in range(start, min(end, len(chars))):
            chars[i] = " "
    return "".join(chars)


def _product_terms(text: str) -> tuple[Optional[str], Optional[str]]:
    """Return (the product as typed, the English term to classify) from leftover text."""
    words = [w for w in re.findall(rf"[{_LETTER}0-9-]+", text) if w not in _STOPWORDS]
    words = [w for w in words if not w.isdigit() and len(w) > 1]
    if not words:
        return None, None
    joined = " ".join(words)
    # Multi-word glossary entries first ("antep fıstığı", "cep telefonu").
    for glossary in (PRODUCTS_TR, PRODUCTS_DE):
        for key in sorted(glossary, key=len, reverse=True):
            if " " in key and key in joined:
                return key, glossary[key]
    for word in words:
        for glossary in (PRODUCTS_TR, PRODUCTS_DE):
            if word in glossary:
                return word, glossary[word]
            if len(word) > 4:
                # Turkish suffixes: "elmalar", "elmayı", "tişörtler".
                for key in glossary:
                    if len(key) >= 3 and word.startswith(key) and len(word) - len(key) <= 4:
                        return word, glossary[key]
    return joined, joined


def parse(message: str) -> dict:
    """Take a message apart into the facts a cost question needs.

    Returns a dict with any of: product, product_query, code, origin,
    destination, quantity, unit, price (a dict), intents (a list).
    """
    text = normalize(message)
    facts: dict[str, Any] = {}
    spans: list[tuple[int, int]] = []

    code, code_spans = _find_code(text)
    if code:
        facts["code"] = code
    spans += code_spans

    price, price_spans = _find_price(_blank(text, spans))
    if price:
        facts["price"] = price
    spans += price_spans

    for match in _QUANTITY.finditer(_blank(text, spans)):
        amount = parse_number(match.group(1))
        if amount is not None:
            facts["quantity"] = str(amount)
            facts["unit"] = _UNIT_OF[match.group(2)]
            spans.append(match.span())
            break
    else:
        count = _COUNT.search(_blank(text, spans))
        if count:
            facts["quantity"] = count.group(1)
            facts["unit"] = "piece"
            spans.append(count.span())

    origin, destination, country_spans = _find_countries(text)
    if origin:
        facts["origin"] = origin
    if destination:
        facts["destination"] = destination
    spans += country_spans

    leftover = _blank(text, spans)
    for markers in _PER_UNIT.values():
        for marker in markers:
            leftover = leftover.replace(marker, " ")
    for words in _INTENT_WORDS.values():
        for word in words:
            leftover = leftover.replace(word.strip(), " ")
    product, product_query = _product_terms(leftover)
    if product and not code:
        facts["product"] = product
        facts["product_query"] = product_query

    facts["intents"] = [
        name for name, words in _INTENT_WORDS.items() if any(w in f" {text} " for w in words)
    ]
    return facts


# ---------------------------------------------------------------------------
# Answering
# ---------------------------------------------------------------------------

_UNIT_LABEL = {
    "en": {"t": "t", "kg": "kg", "piece": "pieces"},
    "tr": {"t": "ton", "kg": "kg", "piece": "adet"},
    "de": {"t": "t", "kg": "kg", "piece": "Stück"},
}


def _t(lang: str, key: str, **params: Any) -> str:
    return TEXT.get(lang, TEXT["en"])[key].format(**params)


def country_name(code: str, lang: str) -> str:
    """A readable country name; the ISO code when the name lists don't carry one."""
    names = COUNTRY_NAMES.get(code)
    if not names or code not in COUNTRY_LABELS:
        return code
    if lang == "tr":
        return " ".join(part[:1].upper() + part[1:] for part in names[0].split())
    english, german = COUNTRY_LABELS[code]
    return german if lang == "de" else english


def money(amount: Decimal, currency: str, lang: str) -> str:
    """Format money the way each language writes it: 10,000.00 / 10.000,00."""
    text = f"{amount.quantize(_CENTS, ROUND_HALF_UP):,.2f}"
    if lang in ("tr", "de"):
        text = text.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return f"{text} {currency}"


def _to_unit(quantity: Decimal, unit: str, target: str) -> Optional[Decimal]:
    if unit == target:
        return quantity
    if {unit, target} == {"t", "kg"}:
        return quantity * 1000 if unit == "t" else quantity / 1000
    return None


def _rate_codes(code: str) -> list[str]:
    """Codes to try for a rate: the code itself, then its CN-8 parent in 10 digits."""
    tries = [code]
    if len(code) == 10:
        tries.append(code[:8] + "00")
    if len(code) >= 8:
        tries.append(code[:8])
    return list(dict.fromkeys(tries))


def _classify(conn: sqlite3.Connection, query: str, lang: str) -> list:
    """Up to three candidates, dropping any far weaker than the best one."""
    try:
        results = classify(conn, query, top_n=3)
        if not results and lang == "de":
            results = classify(conn, query, top_n=3, language="de")
    except InvalidQueryError:
        return []
    return [r for r in results if r.score >= 0.75 * results[0].score] if results else []


def _merge(context: dict, facts: dict) -> dict:
    """Combine the facts gathered so far with this message's.

    A message that names goods together with a price, quantity or origin is a
    new question, not a follow-up: it starts from scratch, so nothing from the
    previous one (a destination, a price) leaks into it.
    """
    goods = facts.get("product") or facts.get("code")
    fresh = goods and any(facts.get(k) for k in ("price", "quantity", "origin"))
    merged = {} if fresh else {k: v for k, v in (context or {}).items() if k != "intents"}
    awaiting = merged.pop("awaiting", None)
    for key, value in facts.items():
        if key != "intents" and value:
            merged[key] = value
    return {**merged, "_awaiting": awaiting}


def _fill_bare_answer(merged: dict, message: str) -> None:
    """A reply like "10" or "1000" to the question just asked."""
    awaiting = merged.get("_awaiting")
    bare = re.fullmatch(rf"\s*({_NUMBER})\s*", normalize(message))
    if not awaiting or not bare:
        return
    amount = parse_number(bare.group(1))
    if amount is None:
        return
    if awaiting == "quantity" and not merged.get("quantity"):
        merged["quantity"] = str(amount)
        merged["unit"] = (merged.get("price") or {}).get("unit") or "t"
    elif awaiting == "price" and not merged.get("price"):
        merged["price"] = {
            "amount": str(amount),
            "currency": "EUR",
            "basis": "unit" if merged.get("unit") else "total",
            "unit": merged.get("unit"),
            "assumed_total": False,
        }


def _ask(lang: str, merged: dict, slot: str) -> dict:
    context = {k: v for k, v in merged.items() if not k.startswith("_")}
    context["awaiting"] = slot
    return {"reply": _t(lang, f"ask_{slot}"), "context": context, "result": None}


def _cost(conn: sqlite3.Connection, merged: dict, lang: str) -> dict:
    """Answer a cost question, or ask for the first missing fact."""
    code = merged.get("code")
    candidates: list[dict] = []
    if not code:
        if not merged.get("product_query"):
            return _ask(lang, merged, "product")
        results = _classify(conn, merged["product_query"], lang)
        if not results:
            reply = _t(lang, "unknown_product", product=merged.get("product"))
            context = {k: v for k, v in merged.items() if not k.startswith("_")}
            context.pop("product", None)
            context.pop("product_query", None)
            context["awaiting"] = "product"
            return {"reply": reply, "context": context, "result": None}
        code = results[0].hs_code.code
        candidates = [
            {"code": r.hs_code.code, "description": r.hierarchy_path, "score": r.score}
            for r in results
        ]
    if not merged.get("origin"):
        return _ask(lang, merged, "origin")
    price = merged.get("price")
    if not price:
        return _ask(lang, merged, "price")
    if price["basis"] == "unit" and not merged.get("quantity"):
        return _ask(lang, merged, "quantity")

    amount = Decimal(price["amount"])
    currency = price["currency"]
    if price["basis"] == "unit":
        quantity = _to_unit(Decimal(merged["quantity"]), merged["unit"], price["unit"])
        if quantity is None:
            units = _UNIT_LABEL.get(lang, _UNIT_LABEL["en"])
            reply = _t(
                lang, "unit_mismatch", price_unit=units[price["unit"]], unit=units[merged["unit"]]
            )
            return {
                "reply": reply,
                "context": {k: v for k, v in merged.items() if not k.startswith("_")},
                "result": None,
            }
        value = (quantity * amount).quantize(_CENTS, ROUND_HALF_UP)
    else:
        value = amount.quantize(_CENTS, ROUND_HALF_UP)

    origin = merged["origin"]
    destination = merged.get("destination")
    notes: list[str] = []
    rate = rate_type = agreement = duty = total = None
    intra_eu = origin in EU_MEMBERS
    if intra_eu:
        notes.append(_t(lang, "intra_eu", origin=country_name(origin, lang)))
    if destination and destination not in EU_MEMBERS:
        notes.append(_t(lang, "non_eu_destination", destination=country_name(destination, lang)))
    if price.get("assumed_total"):
        notes.append(_t(lang, "assumed_total", amount=money(amount, currency, lang)))
    if intra_eu:
        rate, duty, total = 0.0, Decimal("0.00"), value
    else:
        for candidate in _rate_codes(code):
            try:
                result = calculate_duty(conn, candidate, origin, float(value))
            except (RateNotFoundError, InvalidQueryError):
                continue
            rate, rate_type, agreement = (
                result.rate_percent,
                result.rate_type,
                result.trade_agreement,
            )
            duty, total = result.duty_amount, result.total_payable
            break
        if duty is None:
            notes.append(_t(lang, "no_rate", code=code))
    if currency != "EUR":
        notes.append(_t(lang, "currency_note", currency=currency))
    notes.append(_t(lang, "disclaimer"))

    product = merged.get("product") or code
    lines = [_t(lang, "intro", product=product, origin=country_name(origin, lang))]
    lines.append(f"{_t(lang, 'goods_value')}: {money(value, currency, lang)}")
    if duty is not None:
        lines.append(
            f"{_t(lang, 'duty')} ({_t(lang, 'rate')} %{rate:g}): {money(duty, currency, lang)}"
            if lang == "tr"
            else f"{_t(lang, 'duty')} ({rate:g}%): {money(duty, currency, lang)}"
        )
        lines.append(f"{_t(lang, 'total')}: {money(total or value, currency, lang)}")
    context = {k: v for k, v in merged.items() if not k.startswith("_")}
    return {
        "reply": "\n".join(lines + notes),
        "context": context,
        "result": {
            "kind": "cost",
            "code": code,
            "candidates": candidates,
            "origin": origin,
            "destination": destination,
            "intra_eu": intra_eu,
            "quantity": merged.get("quantity"),
            "unit": merged.get("unit"),
            "currency": currency,
            "customs_value": str(value),
            "rate_percent": rate,
            "rate_type": rate_type,
            "trade_agreement": agreement,
            "duty_amount": None if duty is None else str(duty),
            "total": None if total is None else str(total),
        },
    }


def _classify_answer(conn: sqlite3.Connection, merged: dict, lang: str) -> dict:
    query = merged.get("product_query")
    product = merged.get("product")
    context = {k: v for k, v in merged.items() if not k.startswith("_")}
    results = _classify(conn, query, lang) if query else []
    if not results:
        reply = _t(lang, "unknown_product", product=product) if product else _t(lang, "help")
        return {"reply": reply, "context": context, "result": None}
    candidates = [
        {"code": r.hs_code.code, "description": r.hierarchy_path, "score": r.score} for r in results
    ]
    lines = [_t(lang, "classify_intro", product=product)]
    lines += [f"{c['code']} — {c['description']}" for c in candidates]
    return {
        "reply": "\n".join(lines),
        "context": context,
        "result": {"kind": "classify", "code": candidates[0]["code"], "candidates": candidates},
    }


_SCREEN_STRIP = re.compile(
    r"(?i)\b(yaptırım\w*|yaptirim\w*|taramas\w*|tara|sanctions?|sanktion\w*|embargo|screen\w*|"
    r"listesi\w*|list|check|prüfe\w*|kontrol\w*|et|eder\s*misin|misin|please|lütfen|bitte|"
    r"denied\s+party|kara\s+liste\w*|yasaklı)\b"
)


def _screen_answer(conn: sqlite3.Connection, message: str, lang: str) -> dict:
    quoted = re.search(r"[\"“”'‘’«»](.+?)[\"“”'‘’«»]", message)
    name = quoted.group(1) if quoted else _SCREEN_STRIP.sub(" ", message)
    name = " ".join(name.replace(":", " ").split())[:60]
    if len(name) < 3:
        return {"reply": _t(lang, "screen_ask"), "context": {}, "result": None}
    try:
        matches = screen_entity(conn, name)
    except InvalidQueryError:
        return {"reply": _t(lang, "screen_ask"), "context": {}, "result": None}
    if not matches:
        return {
            "reply": _t(lang, "screen_none", name=name),
            "context": {},
            "result": {"kind": "screen", "name": name, "matches": []},
        }
    hits = [
        {
            "name": m.entity.name,
            "country": m.entity.country,
            "list_source": m.entity.list_source,
            "score": m.score,
        }
        for m in matches[:5]
    ]
    lines = [_t(lang, "screen_hits", name=name)]
    lines += [
        f"{m.entity.name} ({m.entity.country}, {m.entity.list_source}) — {round(m.score * 100)}%"
        for m in matches[:5]
    ]
    return {
        "reply": "\n".join(lines),
        "context": {},
        "result": {"kind": "screen", "name": name, "matches": hits},
    }


#: Greetings, thanks and "what can you do": answered with the help text.
_SMALL_TALK = re.compile(
    r"(?:h[iı]|hey|hello|hello there|good morning|selam|merhaba|meraba|slm|iyi günler|hallo|"
    r"guten tag|moin|thanks?|thank you|thx|teşekkürler|teşekkür ederim|sağ ?ol|danke|"
    r"what can you do|what do you do|ne yapabilirsin|neler yapabilirsin|ne yaparsın|"
    r"was kannst du)[\s!?.,]*"
)


def answer(
    conn: sqlite3.Connection, message: str, context: Optional[dict] = None, lang: str = "en"
) -> dict:
    """Reply to one message of the "ask" assistant.

    Returns `{"reply", "context", "result", "suggestions"}`. `context` is what the
    page must send back with the next message so a follow-up ("10 t") completes
    the earlier question.
    """
    lang = lang if lang in LANGUAGES else "en"
    if _SMALL_TALK.fullmatch(normalize(message).strip()):
        # "hi" would otherwise be classified (to "Hi-Lok" bolts).
        return {
            "reply": _t(lang, "help"),
            "context": {},
            "result": None,
            "suggestions": SUGGESTIONS[lang],
        }
    facts = parse(message)
    intents = facts.get("intents", [])
    if "screen" in intents:
        reply = _screen_answer(conn, message, lang)
    else:
        merged = _merge(context or {}, facts)
        _fill_bare_answer(merged, message)
        wants_cost = (
            "cost" in intents
            or bool(merged.get("price"))
            or bool(merged.get("quantity"))
            or merged.get("_awaiting") in ("origin", "price", "quantity")
        )
        support = support_answer(message, lang)
        has_goods_facts = any(facts.get(k) for k in ("code", "price", "quantity", "origin"))
        from_glossary = facts.get("product") != facts.get("product_query")
        if (
            support["matched"]
            and not has_goods_facts
            and not from_glossary
            and not {"cost", "classify"} & set(intents)
            and not merged.get("_awaiting")
        ):
            # "şifremi unuttum" typed into the question card: a help-desk question.
            reply = {"reply": support["reply"], "context": {}, "result": None}
        elif "cost" in intents or (
            wants_cost
            and (merged.get("product_query") or merged.get("code") or merged.get("price"))
        ):
            reply = _cost(conn, merged, lang)
        elif merged.get("product_query") or merged.get("code"):
            if merged.get("code") and not merged.get("product_query"):
                merged["product_query"] = merged["code"]
                merged["product"] = merged["code"]
            reply = _classify_answer(conn, merged, lang)
        else:
            reply = {"reply": _t(lang, "help"), "context": {}, "result": None}
    reply["suggestions"] = SUGGESTIONS[lang] if reply.get("result") is None else []
    return reply


# ---------------------------------------------------------------------------
# The help-desk bot
# ---------------------------------------------------------------------------


def support_answer(message: str, lang: str = "en") -> dict:
    """Answer a help-desk question from the FAQ, or fall back to the contact address."""
    lang = lang if lang in LANGUAGES else "en"
    text = f" {normalize(message)} "
    best, best_score = None, 0
    for keywords, answers in FAQ:
        score = sum(len(k) for k in keywords if k in text)
        if score > best_score:
            best, best_score = answers, score
    if best is None:
        return {
            "reply": SUPPORT_FALLBACK[lang],
            "matched": False,
            "suggestions": SUPPORT_SUGGESTIONS[lang],
            "context": {},
            "result": None,
        }
    return {
        "reply": best[lang],
        "matched": True,
        "suggestions": [],
        "context": {},
        "result": None,
    }

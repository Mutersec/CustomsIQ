"""The free, rule-based assistant: parsing a plain-language shipment, and answering it.

No language model is involved, so every answer here is deterministic: the
facts are pulled out with word lists and patterns, and the figures come from
the same `classify` and `calculate_duty` the rest of the app uses.
"""

import json
import re
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.customsiq import assistant
from src.customsiq.api import _conn, app
from src.customsiq.assistant_glossary import COUNTRY_LABELS, COUNTRY_NAMES, PRODUCTS_TR
from src.customsiq.assistant_texts import (
    FAQ,
    SMALLTALK,
    SUGGESTIONS,
    SUPPORT_FALLBACK,
    SUPPORT_SMALLTALK,
    SUPPORT_SUGGESTIONS,
    TEXT,
)
from src.customsiq.cn_classifier import classify
from src.customsiq.database import (
    fetch_activity,
    get_connection,
    load_bundled_cn_nomenclature,
    load_bundled_hs_supplement,
    load_bundled_sanctions,
    seed,
)
from tests.helpers import signed_in_test_client

INDEX = Path(__file__).parent.parent / "src" / "customsiq" / "static" / "index.html"


@pytest.fixture(scope="module")
def conn() -> sqlite3.Connection:
    connection = get_connection(":memory:")
    seed(connection)
    load_bundled_cn_nomenclature(connection)
    load_bundled_hs_supplement(connection)
    load_bundled_sanctions(connection)
    return connection


class TestNumbers:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1000", "1000"),
            ("10.000", "10000"),
            ("10,000", "10000"),
            ("10.000,50", "10000.50"),
            ("10,000.50", "10000.50"),
            ("2,5", "2.5"),
            ("2.5", "2.5"),
            ("1.250.000", "1250000"),
        ],
    )
    def test_turkish_german_and_english_formats(self, raw: str, expected: str) -> None:
        assert assistant.parse_number(raw) == Decimal(expected)

    def test_money_is_written_the_way_each_language_writes_it(self) -> None:
        assert assistant.money(Decimal("10000"), "EUR", "en") == "10,000.00 EUR"
        assert assistant.money(Decimal("10000"), "EUR", "tr") == "10.000,00 EUR"
        assert assistant.money(Decimal("10000"), "EUR", "de") == "10.000,00 EUR"


class TestParsing:
    def test_the_users_own_sentence(self) -> None:
        facts = assistant.parse(
            "ben türkiyedeyim almanyadan elma getireceğim 10 ton ton fiyatı 1000euro "
            "maliyetini hesapla"
        )
        assert facts["origin"] == "DE"
        assert facts["destination"] == "TR"
        assert facts["quantity"] == "10" and facts["unit"] == "t"
        assert facts["price"] == {
            "amount": "1000",
            "currency": "EUR",
            "basis": "unit",
            "unit": "t",
            "assumed_total": False,
        }
        assert facts["product"] == "elma" and facts["product_query"] == "fresh apples"

    @pytest.mark.parametrize(
        ("message", "origin"),
        [
            ("Türkiye'den 10 ton elma", "TR"),
            ("Çin’den 500 adet tişört", "CN"),
            ("10 t apples from Turkey", "TR"),
            ("10 t Äpfel aus der Türkei", "TR"),
            ("Hindistandan pamuk", "IN"),
        ],
    )
    def test_origin_in_three_languages(self, message: str, origin: str) -> None:
        assert assistant.parse(message)["origin"] == origin

    @pytest.mark.parametrize(
        ("message", "quantity", "unit"),
        [
            ("2.500 kg pamuk", "2500", "kg"),
            ("3 t steel", "3", "t"),
            ("200 adet çanta", "200", "piece"),
            ("200 Stück Taschen", "200", "piece"),
            ("500 t-shirts", "500", "piece"),
        ],
    )
    def test_quantities_and_units(self, message: str, quantity: str, unit: str) -> None:
        facts = assistant.parse(message)
        assert (facts["quantity"], facts["unit"]) == (quantity, unit)

    @pytest.mark.parametrize(
        ("message", "basis", "unit", "currency"),
        [
            ("tonu 1000 euro", "unit", "t", "EUR"),
            ("1000 EUR per tonne", "unit", "t", "EUR"),
            ("1000 EUR pro Tonne", "unit", "t", "EUR"),
            ("tanesi 4 $", "unit", "piece", "USD"),
            ("kilosu 2 euro", "unit", "kg", "EUR"),
            ("toplam 10.000 €", "total", None, "EUR"),
            ("insgesamt 5000 GBP", "total", None, "GBP"),
        ],
    )
    def test_price_basis(self, message: str, basis: str, unit: str, currency: str) -> None:
        price = assistant.parse(message)["price"]
        assert (price["basis"], price["unit"], price["currency"]) == (basis, unit, currency)

    def test_a_bare_price_is_taken_as_the_total_and_flagged(self) -> None:
        price = assistant.parse("10 ton elma 1000 euro")["price"]
        assert price["basis"] == "total" and price["assumed_total"] is True

    @pytest.mark.parametrize("typed", ["kod 0808.10", "GTİP 080810", "HS code 0808 10"])
    def test_a_typed_code_is_used_directly(self, typed: str) -> None:
        facts = assistant.parse(typed)
        assert facts["code"] == "080810"
        assert "product" not in facts

    def test_a_large_plain_number_is_not_mistaken_for_a_code(self) -> None:
        facts = assistant.parse("toplam 100000 euro")
        assert "code" not in facts
        assert facts["price"]["amount"] == "100000"


class TestCostAnswers:
    def test_the_users_example_in_its_eu_version(self, conn: sqlite3.Connection) -> None:
        """Apples from Turkey into the EU: the value is exact, the rate is not invented."""
        reply = assistant.answer(
            conn,
            "Türkiye'den elma getireceğim 10 ton, ton fiyatı 1000 euro, maliyeti hesapla",
            {},
            "tr",
        )
        result = reply["result"]
        assert result["origin"] == "TR" and not result["intra_eu"]
        assert result["code"].startswith("0808")
        assert result["customs_value"] == "10000.00"
        assert result["rate_percent"] is None and result["duty_amount"] is None
        assert "kayıtlı bir vergi oranı yok" in reply["reply"]
        assert "10.000,00 EUR" in reply["reply"]

    def test_the_users_original_sentence_is_intra_eu(self, conn: sqlite3.Connection) -> None:
        reply = assistant.answer(
            conn,
            "ben türkiyedeyim almanyadan elma getireceğim 10 ton ton fiyatı 1000euro "
            "maliyetini hesapla",
            {},
            "tr",
        )
        assert reply["result"]["intra_eu"] is True
        assert reply["result"]["duty_amount"] == "0.00"
        assert "AB içi ticaret" in reply["reply"]
        # And it is honest that Turkey's own import duty is not in the system.
        assert "Türkiye ithalat vergileri bu sistemde yok" in reply["reply"]

    @pytest.mark.parametrize(
        ("message", "lang", "total_text"),
        [
            ("Çin'den 500 adet tişört, tanesi 4 euro", "tr", "2.240,00 EUR"),
            ("500 t-shirts from China, 4 EUR each", "en", "2,240.00 EUR"),
            ("500 T-Shirts aus China, 4 EUR pro Stück", "de", "2.240,00 EUR"),
        ],
    )
    def test_a_code_with_a_rate_on_record(
        self, conn: sqlite3.Connection, message: str, lang: str, total_text: str
    ) -> None:
        result = assistant.answer(conn, message, {}, lang)
        assert result["result"]["code"].startswith("6109")
        assert result["result"]["rate_percent"] == 12.0
        assert result["result"]["duty_amount"] == "240.00"
        assert result["result"]["total"] == "2240.00"
        assert total_text in result["reply"]

    def test_the_rate_is_found_on_the_cn8_parent_of_a_taric_subcode(
        self, conn: sqlite3.Connection
    ) -> None:
        assert assistant._rate_codes("6109100010") == ["6109100010", "6109100000", "61091000"]

    def test_a_new_question_does_not_inherit_the_previous_ones_facts(
        self, conn: sqlite3.Connection
    ) -> None:
        first = assistant.answer(
            conn, "Almanya'dan Türkiye'ye 10 ton elma, tonu 1000 euro", {}, "tr"
        )
        assert first["context"]["destination"] == "TR"
        second = assistant.answer(
            conn, "Çin'den 500 adet tişört, tanesi 4 euro", first["context"], "tr"
        )
        assert second["result"]["destination"] is None
        assert "Türkiye ithalat" not in second["reply"]

    def test_weak_candidates_are_dropped(self, conn: sqlite3.Connection) -> None:
        reply = assistant.answer(conn, "Çin'den 500 adet tişört, tanesi 4 euro", {}, "tr")
        assert all(c["code"].startswith("6109") for c in reply["result"]["candidates"])

    def test_kg_and_tonnes_convert(self, conn: sqlite3.Connection) -> None:
        reply = assistant.answer(conn, "Çin'den 2500 kg tişört, tonu 1000 euro", {}, "tr")
        assert reply["result"]["customs_value"] == "2500.00"

    def test_pieces_against_a_price_per_tonne_is_refused(self, conn: sqlite3.Connection) -> None:
        reply = assistant.answer(conn, "Çin'den 500 adet tişört, tonu 1000 euro", {}, "tr")
        assert reply["result"] is None
        assert "aynı birimle" in reply["reply"]

    def test_missing_facts_are_asked_for_one_at_a_time(self, conn: sqlite3.Connection) -> None:
        first = assistant.answer(conn, "Çin'den 10 ton elma", {}, "tr")
        assert first["result"] is None
        assert first["context"]["awaiting"] == "price"
        second = assistant.answer(conn, "1000", first["context"], "tr")
        assert second["result"]["customs_value"] == "10000.00"

    def test_a_follow_up_with_the_origin_completes_it(self, conn: sqlite3.Connection) -> None:
        first = assistant.answer(conn, "10 t apples, 1000 EUR per tonne, cost?", {}, "en")
        assert first["context"]["awaiting"] == "origin"
        second = assistant.answer(conn, "from Chile", first["context"], "en")
        assert second["result"]["origin"] == "CL"

    def test_an_unknown_product_asks_again(self, conn: sqlite3.Connection) -> None:
        reply = assistant.answer(conn, "Çin'den 10 ton qqzzxx, tonu 5 euro", {}, "tr")
        assert reply["result"] is None
        assert reply["context"]["awaiting"] == "product"

    def test_cost_with_no_goods_asks_for_the_goods(self, conn: sqlite3.Connection) -> None:
        reply = assistant.answer(conn, "maliyet hesapla", {}, "tr")
        assert reply["context"]["awaiting"] == "product"


class TestOtherQuestions:
    def test_a_code_question(self, conn: sqlite3.Connection) -> None:
        reply = assistant.answer(conn, "Dizüstü bilgisayarın GTİP kodu nedir?", {}, "tr")
        assert reply["result"]["kind"] == "classify"
        assert reply["result"]["code"] == "8471300000"

    def test_a_screening_question(self, conn: sqlite3.Connection) -> None:
        reply = assistant.answer(conn, 'yaptırım taraması: "Example Trading Co"', {}, "tr")
        assert reply["result"]["kind"] == "screen"
        assert reply["result"]["name"] == "Example Trading Co"

    def test_a_help_question_typed_into_the_question_card(self, conn: sqlite3.Connection) -> None:
        reply = assistant.answer(conn, "şifremi unuttum", {}, "tr")
        assert "support@customsiq.org" in reply["reply"]


class TestSupportBot:
    @pytest.mark.parametrize(
        ("message", "lang", "expected"),
        [
            ("şifremi unuttum", "tr", "support@customsiq.org"),
            ("I forgot my password", "en", "support@customsiq.org"),
            ("nasıl arama yaparım", "tr", "HS / CN kodu arama"),
            ("Google ile giriş", "tr", "Google ile devam et"),
            ("kod gelmedi", "tr", "spam"),
            ("Was bedeutet HS-6?", "de", "HS-2022"),
        ],
    )
    def test_questions_reach_the_right_answer(self, message: str, lang: str, expected: str) -> None:
        reply = assistant.support_answer(message, lang)
        assert reply["matched"] is True
        assert expected in reply["reply"]

    def test_an_unrecognised_question_offers_topics_and_contact(self) -> None:
        reply = assistant.support_answer("qqzzxx", "tr")
        assert reply["matched"] is False
        assert "support@customsiq.org" in reply["reply"]
        assert reply["suggestions"]


class TestTheWordLists:
    def test_every_turkish_product_classifies_to_something(self, conn: sqlite3.Connection) -> None:
        missing = [k for k, v in PRODUCTS_TR.items() if not classify(conn, v, top_n=1)]
        assert not missing

    def test_every_country_has_english_and_german_labels(self) -> None:
        assert set(COUNTRY_LABELS) == set(COUNTRY_NAMES)

    def test_every_text_exists_in_all_three_languages(self) -> None:
        assert set(TEXT["en"]) == set(TEXT["tr"]) == set(TEXT["de"])
        for _, answers in FAQ:
            assert set(answers) == {"en", "tr", "de"}
        for table in (SUGGESTIONS, SUPPORT_SUGGESTIONS):
            assert set(table) == {"en", "tr", "de"}


class TestTheApi:
    def test_ask(self) -> None:
        client = signed_in_test_client()
        body = client.post(
            "/assistant",
            json={"message": "Çin'den 500 adet tişört, tanesi 4 euro", "language": "tr"},
        ).json()
        assert body["result"]["total"] == "2240.00"

    def test_a_follow_up_through_the_api(self) -> None:
        client = signed_in_test_client()
        first = client.post("/assistant", json={"message": "Çin'den 10 ton elma"}).json()
        second = client.post(
            "/assistant", json={"message": "1000", "context": first["context"]}
        ).json()
        assert second["result"]["customs_value"] == "10000.00"

    def test_support_mode(self) -> None:
        client = signed_in_test_client()
        body = client.post(
            "/assistant", json={"message": "şifremi unuttum", "mode": "support", "language": "tr"}
        ).json()
        assert "support@customsiq.org" in body["reply"]

    def test_requires_sign_in(self) -> None:
        assert TestClient(app).post("/assistant", json={"message": "hi"}).status_code == 401

    def test_message_length_is_capped(self) -> None:
        client = signed_in_test_client()
        response = client.post("/assistant", json={"message": "x" * 301})
        assert response.status_code == 422

    def test_it_is_logged_for_the_owner(self) -> None:
        client = signed_in_test_client()
        username = client.get("/auth/me").json()["user"]["username"]
        client.post("/assistant", json={"message": "Çin'den 500 adet tişört, tanesi 4 euro"})
        row = fetch_activity(_conn, username=username, action="assistant")[0][0]
        assert row.detail == "Çin'den 500 adet tişört, tanesi 4 euro"
        assert row.top_code and row.top_code.startswith("6109")


class TestThePage:
    def test_both_assistants_are_on_the_page(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        assert 'id="ask-panel"' in html and 'id="support-fab"' in html
        # The question card sits right under the dashboard.
        assert html.index('id="ask-panel"') < html.index('data-i18n="search.title"')
        # The script looks both widgets up once when it runs, so their markup
        # must come before it; placed after, the lookup returned null and the
        # exception stopped the rest of the page script.
        script = html.index("<script>")
        assert html.index('id="support-panel"') < script
        assert html.index('id="ask-form"') < script

    def test_every_assistant_string_exists_in_all_three_languages(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        for section in ("ask", "support"):
            blocks = re.findall(rf"\n      {section}: \{{\n(.*?)\n      \}},", html, re.S)
            assert len(blocks) == 3, section
            keys = [set(re.findall(r"^\s+(\w+):", block, re.M)) for block in blocks]
            assert keys[0] == keys[1] == keys[2], section


# ---------------------------------------------------------------------------
# The seven reported chat failures, one class each
# ---------------------------------------------------------------------------


def _no_classify(*_args: object, **_kwargs: object) -> list:
    raise AssertionError("small talk must never reach classify()")


class TestFailure1GreetingsNeverReachClassify:
    """ "hi" used to answer "closest codes for hi: Hi-Lok bolts"."""

    @pytest.mark.parametrize(
        ("message", "lang", "key"),
        [
            ("hi", "en", "hello"),
            ("Hello!", "en", "hello"),
            ("hi there", "en", "hello"),
            ("merhaba", "tr", "hello"),
            ("Selam", "tr", "hello"),
            ("İyi günler", "tr", "hello"),
            ("hallo", "de", "hello"),
            ("Guten Tag!", "de", "hello"),
            ("help", "en", "capabilities"),
            ("what can you do?", "en", "capabilities"),
            ("yardım", "tr", "capabilities"),
            ("Ne yapabilirsin?", "tr", "capabilities"),
            ("Hilfe", "de", "capabilities"),
            ("Hallo, was kannst du?", "de", "capabilities"),
            ("thanks!", "en", "thanks"),
            ("teşekkürler", "tr", "thanks"),
            ("danke schön", "de", "thanks"),
        ],
    )
    def test_small_talk_gets_a_friendly_reply_in_the_ui_language(
        self,
        conn: sqlite3.Connection,
        monkeypatch: pytest.MonkeyPatch,
        message: str,
        lang: str,
        key: str,
    ) -> None:
        monkeypatch.setattr(assistant, "classify", _no_classify)
        reply = assistant.answer(conn, message, {}, lang)
        assert reply["reply"] == TEXT[lang][key]
        assert reply["result"] is None
        assert reply["suggestions"] == SUGGESTIONS[lang]

    @pytest.mark.parametrize("lang", ["en", "tr", "de"])
    def test_the_greeting_lists_what_the_bot_can_do(self, lang: str) -> None:
        words = {"en": ("duty", "CN code", "sanctions"), "tr": ("vergi", "GTİP", "yaptırım")}
        words["de"] = ("Zoll", "KN-Nummer", "Sanktionsliste")
        assert all(w in TEXT[lang]["hello"] for w in words[lang])

    def test_a_greeting_mid_question_keeps_the_question(self, conn: sqlite3.Connection) -> None:
        first = assistant.answer(conn, "laptops from China, calculate the cost", {}, "en")
        second = assistant.answer(conn, "thanks", first["context"], "en")
        assert second["context"]["product"] == "laptops"
        assert second["context"]["awaiting"] == "price"

    def test_a_greeting_in_front_of_a_shipment_is_not_small_talk(
        self, conn: sqlite3.Connection
    ) -> None:
        reply = assistant.answer(conn, "hi, 500 t-shirts from China, 4 EUR each", {}, "en")
        assert reply["result"]["total"] == "2240.00"
        assert assistant.smalltalk_kind("hi, 500 t-shirts from China") is None

    def test_hi_lok_bolts_are_still_found_when_asked_for(self, conn: sqlite3.Connection) -> None:
        reply = assistant.answer(conn, "Which code is a Hi-Lok bolt?", {}, "en")
        assert reply["result"]["kind"] == "classify"

    def test_the_api_answers_hi_with_the_greeting(self) -> None:
        client = signed_in_test_client()
        body = client.post("/assistant", json={"message": "hi", "language": "en"}).json()
        assert body["reply"] == TEXT["en"]["hello"]
        assert body["result"] is None


class TestFailure2HelpWidgetSmallTalk:
    """ "help" and "hi" in the help widget used to get the "didn't find an answer" fallback."""

    @pytest.mark.parametrize(
        ("message", "lang", "kind"),
        [
            ("hi", "en", "greeting"),
            ("help", "en", "help"),
            ("merhaba", "tr", "greeting"),
            ("yardım", "tr", "help"),
            ("hallo", "de", "greeting"),
            ("Hilfe", "de", "help"),
            ("thank you", "en", "thanks"),
        ],
    )
    def test_small_talk_is_answered(self, message: str, lang: str, kind: str) -> None:
        reply = assistant.support_answer(message, lang)
        assert reply["matched"] is True
        assert reply["reply"] == SUPPORT_SMALLTALK[kind][lang]
        assert reply["reply"] != SUPPORT_FALLBACK[lang]
        assert reply["suggestions"] == SUPPORT_SUGGESTIONS[lang]

    def test_every_small_talk_reply_exists_in_all_three_languages(self) -> None:
        for answers in SUPPORT_SMALLTALK.values():
            assert set(answers) == {"en", "tr", "de"}
        assert set(SUPPORT_SMALLTALK) == set(SMALLTALK)

    def test_through_the_api(self) -> None:
        client = signed_in_test_client()
        body = client.post(
            "/assistant", json={"message": "help", "mode": "support", "language": "de"}
        ).json()
        assert body["reply"] == SUPPORT_SMALLTALK["help"]["de"]


class TestFailure3Amounts:
    """ "Its price is 1.2 million dollars." used to be ignored and the question repeated."""

    @pytest.mark.parametrize(
        ("typed", "amount", "currency"),
        [
            ("1.2 million dollars", "1200000", "USD"),
            ("1,2 milyon dolar", "1200000", "USD"),
            ("1.2 Mio. Dollar", "1200000", "USD"),
            ("1.200.000 EUR", "1200000", "EUR"),
            ("1,200,000 euro", "1200000", "EUR"),
            ("$1.2M", "1200000", "USD"),
            ("10k EUR", "10000", "EUR"),
            ("250 bin TL", "250000", "TRY"),
            ("3 Mrd. Euro", "3000000000", "EUR"),
            ("£2.5m", "2500000", "GBP"),
            ("500 lira", "500", "TRY"),
            ("700 pounds", "700", "GBP"),
            ("1.5 billion USD", "1500000000", "USD"),
        ],
    )
    def test_amount_formats_and_currency_words(
        self, typed: str, amount: str, currency: str
    ) -> None:
        price = assistant.parse(f"laptops {typed}")["price"]
        assert (price["amount"], price["currency"]) == (amount, currency)

    def test_the_last_separator_is_the_decimal_point(self) -> None:
        assert assistant.parse("1,2 Mio. EUR")["price"]["amount"] == "1200000"
        assert assistant.parse("1.25 million EUR")["price"]["amount"] == "1250000"

    def test_a_million_is_not_a_count_of_pieces(self) -> None:
        assert "quantity" not in assistant.parse("laptops 10 million")

    @pytest.mark.parametrize(
        ("first", "reply", "lang", "value_text", "currency_note"),
        [
            (
                "laptops from China, calculate the cost",
                "Its price is 1.2 million dollars.",
                "en",
                "1,200,000.00 USD",
                "in USD. CustomsIQ does not convert currencies.",
            ),
            (
                "Çin'den laptop, maliyeti hesapla",
                "Fiyatı 1,2 milyon dolar.",
                "tr",
                "1.200.000,00 USD",
                "USD cinsinden hesaplandı. CustomsIQ döviz çevirisi yapmaz.",
            ),
            (
                "Laptops aus China, Kosten berechnen",
                "Der Preis ist 1,2 Mio. Dollar.",
                "de",
                "1.200.000,00 USD",
                "in USD berechnet. CustomsIQ rechnet keine Währungen um.",
            ),
        ],
    )
    def test_the_reported_conversation_completes(
        self,
        conn: sqlite3.Connection,
        first: str,
        reply: str,
        lang: str,
        value_text: str,
        currency_note: str,
    ) -> None:
        asked = assistant.answer(conn, first, {}, lang)
        assert asked["context"]["awaiting"] == "price"
        done = assistant.answer(conn, reply, asked["context"], lang)
        assert done["result"]["kind"] == "cost"
        assert done["result"]["customs_value"] == "1200000.00"
        assert done["result"]["currency"] == "USD"
        assert done["result"]["code"].startswith("8471")
        assert value_text in done["reply"] and currency_note in done["reply"]

    @pytest.mark.parametrize("lang", ["en", "tr", "de"])
    def test_an_amount_without_a_currency_is_taken_as_given(
        self, conn: sqlite3.Connection, lang: str
    ) -> None:
        asked = assistant.answer(conn, "laptops from China, calculate the cost", {}, lang)
        done = assistant.answer(conn, "10k", asked["context"], lang)
        assert done["result"]["customs_value"] == "10000.00"
        assert done["result"]["currency_assumed"] is True
        assert TEXT[lang]["currency_assumed"] in done["reply"]

    @pytest.mark.parametrize("lang", ["en", "tr", "de"])
    def test_an_unreadable_price_is_never_asked_again_verbatim(
        self, conn: sqlite3.Connection, lang: str
    ) -> None:
        asked = assistant.answer(conn, "laptops from China, calculate the cost", {}, lang)
        again = assistant.answer(conn, "not sure yet", asked["context"], lang)
        assert again["reply"] != asked["reply"]
        assert "not sure yet" in again["reply"]
        assert again["context"]["product"] == "laptops"
        third = assistant.answer(conn, "dunno", again["context"], lang)
        assert third["reply"] not in (asked["reply"], again["reply"])
        assert TEXT[lang]["start_over"] in third["reply"]


class TestFailure4GoodsAreAskedFirst:
    """The bot used to take filler ("customs", "pay") as goods and skip to origin/price."""

    @pytest.mark.parametrize(
        ("message", "lang"),
        [
            ("I want to calculate customs duty", "en"),
            ("how much duty will I pay?", "en"),
            ("I want to import something from China", "en"),
            ("Gümrük vergisi ne kadar tutar?", "tr"),
            ("Çin'den bir şey getireceğim, vergisi ne kadar?", "tr"),
            ("Wie viel Zoll muss ich zahlen?", "de"),
            ("Ich importiere etwas aus China, was kostet der Zoll?", "de"),
        ],
    )
    def test_the_goods_are_asked_for_before_anything_else(
        self, conn: sqlite3.Connection, message: str, lang: str
    ) -> None:
        reply = assistant.answer(conn, message, {}, lang)
        assert reply["context"]["awaiting"] == "product"
        assert reply["reply"] == TEXT[lang]["ask_product"]
        assert "product" not in reply["context"]

    def test_goods_then_origin_then_price(self, conn: sqlite3.Connection) -> None:
        step = assistant.answer(conn, "calculate the cost", {}, "en")
        assert step["context"]["awaiting"] == "product"
        step = assistant.answer(conn, "laptops", step["context"], "en")
        assert step["context"]["awaiting"] == "origin"
        step = assistant.answer(conn, "from China", step["context"], "en")
        assert step["context"]["awaiting"] == "price"
        step = assistant.answer(conn, "5000 EUR", step["context"], "en")
        assert step["result"]["customs_value"] == "5000.00"

    def test_english_i_is_not_read_as_turkish_dotless_i(self) -> None:
        facts = assistant.parse("Its price is 1.2 million dollars.")
        assert "product" not in facts

    @pytest.mark.parametrize(
        ("message", "lang", "note"),
        [
            ("bolts from China to Luxembourg, 5000 EUR total", "en", "Luxembourg is an EU"),
            ("Çin'den Lüksemburg'a cıvata, toplam 5000 euro", "tr", "Lüksemburg bir AB üyesi"),
            ("Schrauben aus China nach Luxemburg, insgesamt 5000 EUR", "de", "Luxemburg ist EU"),
        ],
    )
    def test_origin_and_an_eu_destination(
        self, conn: sqlite3.Connection, message: str, lang: str, note: str
    ) -> None:
        reply = assistant.answer(conn, message, {}, lang)
        assert reply["result"]["origin"] == "CN"
        assert reply["result"]["destination"] == "LU"
        assert note in reply["reply"]

    @pytest.mark.parametrize("lang", ["en", "tr", "de"])
    def test_an_unknown_country_is_explained_not_re_asked(
        self, conn: sqlite3.Connection, lang: str
    ) -> None:
        asked = assistant.answer(conn, "laptops, 1000 EUR, calculate", {}, lang)
        assert asked["context"]["awaiting"] == "origin"
        again = assistant.answer(conn, "from Narnia", asked["context"], lang)
        assert again["reply"] != asked["reply"] and "from Narnia" in again["reply"]
        assert again["context"]["product"] == "laptops"


class TestFailure5HonestCopy:
    """The intro claimed "it uses the EU tariff data"; the rates are demo data."""

    def test_the_overclaim_is_gone_in_every_language(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        for phrase in ("uses the EU tariff data", "AB tarife verisini kullanır", "EU-Tarifdaten"):
            assert phrase not in html

    def test_the_hint_says_rates_are_demo_data_in_every_language(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        hints = re.findall(r"\n      ask: \{\n\s+title: .*\n\s+hint: \"(.*)\",", html)
        assert len(hints) == 3
        assert "demo data" in hints[0] and "Combined Nomenclature" in hints[0]
        assert "demo verisidir" in hints[1] and "Kombine Nomenklatürü" in hints[1]
        assert "Demodaten" in hints[2] and "Kombinierten Nomenklatur" in hints[2]

    @pytest.mark.parametrize(
        ("lang", "phrase"),
        [("en", "demo data"), ("tr", "demo verisidir"), ("de", "Demodaten")],
    )
    def test_every_estimate_says_the_rates_are_demo_data(
        self, conn: sqlite3.Connection, lang: str, phrase: str
    ) -> None:
        message = {
            "en": "500 t-shirts from China, 4 EUR each",
            "tr": "Çin'den 500 adet tişört, tanesi 4 euro",
            "de": "500 T-Shirts aus China, 4 EUR pro Stück",
        }[lang]
        assert phrase in assistant.answer(conn, message, {}, lang)["reply"]

    def test_the_faq_no_longer_calls_the_rates_the_eu_tariff(self) -> None:
        answers = " ".join(a["en"] for _, a in FAQ)
        assert "The duty uses the EU tariff" not in answers
        assert "demo data" in answers


class TestFailure6PasswordAndSupport:
    """No reset flow exists (audit finding #8): the chat must not promise one."""

    @pytest.mark.parametrize(
        ("message", "lang"),
        [("Forgot my password?", "en"), ("Şifremi unuttum?", "tr"), ("Passwort vergessen?", "de")],
    )
    def test_the_password_chip_gets_an_honest_answer(self, message: str, lang: str) -> None:
        assert message in SUPPORT_SUGGESTIONS[lang]
        reply = assistant.support_answer(message, lang)["reply"]
        assert "support@customsiq.org" in reply and "Google" in reply
        for promise in ("not self-service yet", "henüz", "noch nicht", "reset link"):
            assert promise not in reply

    def test_no_reset_route_exists(self) -> None:
        paths = {route.path for route in app.routes}  # type: ignore[attr-defined]
        assert not any("reset" in path or "forgot" in path for path in paths)

    def test_the_page_chips_match_the_server_chips(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        for lang in ("en", "tr", "de"):
            assert json.dumps(SUPPORT_SUGGESTIONS[lang], ensure_ascii=False) in html
            assert json.dumps(SUGGESTIONS[lang], ensure_ascii=False) in html


class TestFailure7Security:
    """Echoed text stays text, the input is capped, and a tampered context is harmless."""

    @pytest.mark.parametrize(
        "context",
        [
            {"product": "x", "product_query": "x", "origin": "CN", "price": {"amount": "abc"}},
            {
                "product": "laptops",
                "product_query": "laptops",
                "origin": "CN",
                "price": {"amount": "1e999999", "currency": "EUR", "basis": "total", "unit": None},
            },
            {"price": "x", "awaiting": "<script>", "tries": "9", "origin": "ZZ"},
            {"quantity": "NaN", "unit": "t", "code": "12'; drop"},
        ],
    )
    def test_a_tampered_context_is_a_normal_reply_not_a_500(self, context: dict) -> None:
        client = signed_in_test_client()
        response = client.post(
            "/assistant", json={"message": "10", "language": "en", "context": context}
        )
        assert response.status_code == 200
        assert "Traceback" not in response.text

    def test_a_script_tag_is_echoed_as_plain_text_only(self, conn: sqlite3.Connection) -> None:
        asked = assistant.answer(conn, "laptops from China, calculate the cost", {}, "en")
        probe = "<script>alert('x')</script>"
        again = assistant.answer(conn, probe, asked["context"], "en")
        assert again["result"] is None
        # Echoed verbatim as data; the page decides how to render it (as text).
        assert probe in again["reply"]
        html = INDEX.read_text(encoding="utf-8")
        chat = html[html.index("function createChat(") : html.index("const assistants = [")]
        # Replies, user text and chips are written with textContent; the only
        # innerHTML is the one that empties the chip row.
        assert re.findall(r"innerHTML\s*=", chat) == ["innerHTML ="]
        assert 'suggest.innerHTML = "";' in chat
        assert "el.textContent = text;" in chat and "btn.textContent = text;" in chat

    def test_both_inputs_are_capped_like_the_server(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        for field in ("ask-input", "support-input"):
            tag = re.search(rf'<input[^>]*id="{field}"[^>]*>', html)
            assert tag and f'maxlength="{assistant.MAX_MESSAGE}"' in tag.group(0)

    def test_support_mode_is_capped_rate_limited_and_signed_in_only(self) -> None:
        client = signed_in_test_client()
        long = client.post("/assistant", json={"message": "x" * 301, "mode": "support"})
        assert long.status_code == 422
        anonymous = TestClient(app).post("/assistant", json={"message": "hi", "mode": "support"})
        assert anonymous.status_code == 401
        route = next(r for r in app.routes if getattr(r, "path", None) == "/assistant")
        names = {d.call.__name__ for d in route.dependant.dependencies}  # type: ignore[attr-defined]
        assert "_check_search_rate_limit" in names


class TestLowConfidenceLeads:
    def test_the_threshold_matches_the_page(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        match = re.search(r"const LOW_CONFIDENCE_THRESHOLD = ([\d.]+);", html)
        assert match and float(match.group(1)) == assistant.LOW_CONFIDENCE

    @pytest.mark.parametrize(
        ("lang", "phrase"),
        [("en", "best lead"), ("tr", "En iyi ipucu"), ("de", "beste Hinweis")],
    )
    def test_a_weak_match_is_a_lead_not_the_closest_codes(
        self, conn: sqlite3.Connection, lang: str, phrase: str
    ) -> None:
        reply = assistant.answer(conn, "Which code is a zzyzx flurble bolt?", {}, lang)
        assert reply["result"]["low_confidence"] is True
        assert phrase in reply["reply"]
        closest = {"en": "closest codes", "tr": "en yakın kodlar", "de": "passendsten Codes"}
        assert closest[lang] not in reply["reply"]

    def test_a_strong_match_keeps_the_closest_codes_wording(self, conn: sqlite3.Connection) -> None:
        reply = assistant.answer(conn, "Which code is a laptop?", {}, "en")
        assert reply["result"]["low_confidence"] is False
        assert reply["reply"].startswith('The closest codes for "laptop"')

    @pytest.mark.parametrize(
        "message",
        ["hi", "ok", "is", "it", "a b", "its price is", "customs"],
    )
    def test_chatter_is_not_a_product_query(self, message: str) -> None:
        assert "product" not in assistant.parse(message)

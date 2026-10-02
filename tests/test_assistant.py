"""The free, rule-based assistant: parsing a plain-language shipment, and answering it.

No language model is involved, so every answer here is deterministic: the
facts are pulled out with word lists and patterns, and the figures come from
the same `classify` and `calculate_duty` the rest of the app uses.
"""

import re
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.customsiq import assistant
from src.customsiq.api import _conn, app
from src.customsiq.assistant_glossary import COUNTRY_LABELS, COUNTRY_NAMES, PRODUCTS_TR
from src.customsiq.assistant_texts import FAQ, SUGGESTIONS, SUPPORT_SUGGESTIONS, TEXT
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

    def test_solar_panels_have_a_rate_on_record(self, conn: sqlite3.Connection) -> None:
        """8541 used to classify but stop at "no duty rate"; PV modules are duty-free."""
        reply = assistant.answer(conn, "solar panel from China 2000 EUR", {}, "en")
        assert reply["result"]["code"] == "854143"
        assert reply["result"]["rate_percent"] == 0.0
        assert reply["result"]["duty_amount"] == "0.00"
        assert "No duty rate" not in reply["reply"]

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
        assert html.index('id="ask-panel"') < html.index('id="search-panel"')
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

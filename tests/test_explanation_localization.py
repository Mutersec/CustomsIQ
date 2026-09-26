"""Tests for QA audit Bug #8: server-generated explanations render per-language.

The backend now sends each explanation twice: the pre-rendered English
sentence it always sent (unchanged — the CLI and plain API clients still
read it), plus the same reasoning as `explanation_key` + `explanation_params`
so the browser can render it in the viewer's own language.

These tests cover both halves: that the structured form is correct and
complete on the Python side, and that the three JS templates actually
produce idiomatic sentences rather than an English frame with a number
spliced into it.
"""

import json
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from src.customsiq.database import get_connection, seed
from src.customsiq.risk import assess_shipment
from src.customsiq.sap_gts_bridge import compliance_check
from src.customsiq.tariff_calculator import calculate_duty

INDEX = Path(__file__).resolve().parents[1] / "src" / "customsiq" / "static" / "index.html"
LANGUAGES = ("en", "tr", "de")


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = get_connection(":memory:")
    seed(connection)
    return connection


class TestDutyExplanationIsStructured:
    """tariff_calculator.py carries the reasoning as key + params."""

    def test_standard_rate_branch(self, conn: sqlite3.Connection) -> None:
        result = calculate_duty(conn, "8517120000", "CN", 1000)
        assert result.explanation_key == "standard"
        assert result.explanation_params == {"rate": result.rate_percent, "origin": "CN"}

    def test_preferential_rate_branch(self, conn: sqlite3.Connection) -> None:
        result = calculate_duty(conn, "6109100000", "NO", 1000)
        assert result.explanation_key == "preferential"
        assert result.explanation_params == {
            "rate": result.rate_percent,
            "agreement": result.trade_agreement,
            "origin": "NO",
        }

    def test_the_english_sentence_is_unchanged(self, conn: sqlite3.Connection) -> None:
        """The pre-existing text contract: the CLI and API clients still read this."""
        result = calculate_duty(conn, "8517120000", "CN", 1000)
        assert result.explanation == (
            "Standard MFN rate of 0% applied — no preferential agreement "
            "covers origin CN for this code."
        )


class TestRiskExplanationsAreStructured:
    """Every risk.py branch names itself, and the params carry real values."""

    def test_screening_hit(self, conn: sqlite3.Connection) -> None:
        factors = {
            f.name: f
            for f in assess_shipment(
                conn, "NO", "Northwind Maritime", 1000, description="cotton t-shirt"
            ).factors
        }
        screening = factors["screening"]
        assert screening.explanation_key == "screeningHit"
        assert screening.explanation_params["name"] == "Northwind Maritime Holdings Ltd"
        assert screening.explanation_params["score"] == pytest.approx(1.0)

    def test_screening_clean(self, conn: sqlite3.Connection) -> None:
        factors = {
            f.name: f
            for f in assess_shipment(
                conn, "NO", "Quokka Beachwear", 1000, description="cotton t-shirt"
            ).factors
        }
        assert factors["screening"].explanation_key == "screeningClean"
        assert factors["screening"].explanation_params == {}

    def test_classification_top_match(self, conn: sqlite3.Connection) -> None:
        factors = {
            f.name: f
            for f in assess_shipment(
                conn, "NO", "Quokka Beachwear", 1000, description="cotton t-shirt"
            ).factors
        }
        classification = factors["classification"]
        assert classification.explanation_key == "classificationTop"
        assert classification.explanation_params["code"] == "6109100000"
        # The factor's own score is 1 - confidence; the param is the confidence.
        assert classification.explanation_params["confidence"] == pytest.approx(
            1 - classification.score
        )

    def test_classification_direct_and_none(self, conn: sqlite3.Connection) -> None:
        direct = {
            f.name: f
            for f in assess_shipment(
                conn, "NO", "Quokka Beachwear", 1000, hs_code="6109100000"
            ).factors
        }
        assert direct["classification"].explanation_key == "classificationDirect"

        unknown = {
            f.name: f
            for f in assess_shipment(
                conn, "CN", "Quokka Beachwear", 100, description="device"
            ).factors
        }
        assert unknown["classification"].explanation_key == "classificationNone"
        assert unknown["duty"].explanation_key == "dutyNotAssessed"

    def test_duty_rate_carries_its_discriminator(self, conn: sqlite3.Connection) -> None:
        factors = {
            f.name: f
            for f in assess_shipment(
                conn, "NO", "Quokka Beachwear", 1000, description="cotton t-shirt"
            ).factors
        }
        duty = factors["duty"]
        assert duty.explanation_key == "dutyRate"
        assert duty.explanation_params["rate_type"] in {"preferential", "standard"}
        assert isinstance(duty.explanation_params["rate"], float)

    def test_every_factor_names_a_key_and_keeps_its_english(self, conn: sqlite3.Connection) -> None:
        for factor in assess_shipment(
            conn, "NO", "Northwind Maritime", 1000, description="cotton t-shirt"
        ).factors:
            assert factor.explanation_key, f"{factor.name} has no explanation_key"
            assert factor.explanation, f"{factor.name} lost its English sentence"


class TestGtsRoutingSurvivedTheDiscriminatorSwap:
    """sap_gts_bridge.render_duty used to branch on English prose.

    It now reads `explanation_params["rate_type"]`. The emitted BAPIRET2
    codes must be byte-identical — that is the whole point of the change.
    """

    def _duty_row(self, conn: sqlite3.Connection, **kwargs) -> dict:
        assessment = assess_shipment(conn, **kwargs)
        document = compliance_check(assessment, kwargs["party_name"], "ref-1")
        rows = [r for r in document.as_payload()["RETURN"] if r["FIELD"] == "duty"]
        assert rows, "no duty row rendered"
        return rows[0]

    def test_preferential_rate_still_emits_S_020(self, conn: sqlite3.Connection) -> None:
        row = self._duty_row(
            conn,
            country_of_origin="NO",
            party_name="Quokka Beachwear",
            customs_value=1000,
            description="cotton t-shirt",
        )
        assert (row["TYPE"], row["NUMBER"]) == ("S", "020")

    def test_standard_rate_still_emits_I_021(self, conn: sqlite3.Connection) -> None:
        row = self._duty_row(
            conn,
            country_of_origin="CN",
            party_name="Quokka Beachwear",
            customs_value=1000,
            hs_code="8517120000",
        )
        assert (row["TYPE"], row["NUMBER"]) == ("I", "021")

    def test_no_rate_still_emits_W_022(self, conn: sqlite3.Connection) -> None:
        row = self._duty_row(
            conn,
            country_of_origin="CN",
            party_name="Quokka Beachwear",
            customs_value=100,
            description="device",
        )
        assert (row["TYPE"], row["NUMBER"]) == ("W", "022")


# --------------------------------------------------------------------------
# Frontend rendering
# --------------------------------------------------------------------------


def _block(text: str, start: int) -> str:
    """Return the `{...}` block starting at `start`, brace-matched."""
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError("unbalanced braces in the translation dictionary")


def _strings_source() -> str:
    """The whole `STRINGS = {...}` literal, lifted out of index.html."""
    source = INDEX.read_text(encoding="utf-8")
    match = re.search(r"const STRINGS = \{", source)
    assert match, "STRINGS object not found"
    return _block(source, match.end() - 1)


def _render(lang: str, table: str, key: str, params: dict) -> str:
    """Render one explanation template through node, exactly as the page would."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed; skipping the live render check")
    script = f"""
      const STRINGS = {_strings_source()};
      const lang = {json.dumps(lang)};
      function t(key) {{
        const parts = key.split(".");
        let value = STRINGS[lang];
        for (const part of parts) value = value ? value[part] : undefined;
        if (value === undefined) {{
          value = STRINGS.en;
          for (const part of parts) value = value ? value[part] : undefined;
        }}
        return value;
      }}
      const template = t({json.dumps(table)})[{json.dumps(key)}];
      process.stdout.write(template({json.dumps(params)}));
    """
    completed = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


class TestExplanationsRenderIdiomaticallyPerLanguage:
    """The point of the whole change: each language gets its own sentence.

    Not an English frame with a number dropped into it — the percent sign and
    the decimal separator move too, which is exactly what these pin.
    """

    @pytest.mark.parametrize(
        ("lang", "expected"),
        [("en", "12%"), ("tr", "%12"), ("de", "12 %")],
    )
    def test_the_percent_sign_follows_each_locale(self, lang: str, expected: str) -> None:
        rendered = _render(lang, "duty.explanation", "standard", {"rate": 12, "origin": "CN"})
        assert expected in rendered
        assert "CN" in rendered

    def test_each_language_produces_a_different_sentence(self) -> None:
        params = {"rate": 12, "agreement": "EEA", "origin": "NO"}
        rendered = {
            lang: _render(lang, "duty.explanation", "preferential", params) for lang in LANGUAGES
        }
        assert len({*rendered.values()}) == 3, "two languages rendered identically"
        for text in rendered.values():
            assert "EEA" in text and "NO" in text

    @pytest.mark.parametrize(
        ("lang", "expected"),
        [("en", "0.82"), ("tr", "0,82"), ("de", "0,82")],
    )
    def test_the_decimal_separator_follows_each_locale(self, lang: str, expected: str) -> None:
        rendered = _render(
            lang,
            "risk.explanation",
            "screeningNearMiss",
            {"name": "Northwind Maritime", "score": 0.8217},
        )
        assert expected in rendered
        assert "Northwind Maritime" in rendered

    def test_risk_duty_explanation_reuses_the_translated_rate_type(self) -> None:
        """German says "Präferenzsatz", not the raw English enum value."""
        rendered = _render(
            "de", "risk.explanation", "dutyRate", {"rate_type": "preferential", "rate": 5}
        )
        assert "Präferenzsatz" in rendered
        assert "preferential" not in rendered


class TestIndexedTranslationTablesAgreeAcrossLanguages:
    """Close the blind spot the key-scan can't see.

    tests/test_frontend_i18n.py only verifies keys written as a literal
    t("a.b.c"). Tables indexed by a server-supplied value — the new
    explanation tables, and the pre-existing invoice.fields / risk.factor /
    risk.level / duty.rateType — are looked up dynamically, so a key missing
    from one language would go unnoticed until it rendered as `undefined`.
    Comparing the three languages' leaf sets catches exactly that.
    """

    TABLES = (
        "duty.explanation",
        "risk.explanation",
        "duty.rateType",
        "risk.factor",
        "risk.level",
        "invoice.fields",
    )

    @pytest.fixture(scope="class")
    def dictionaries(self) -> dict:
        source = INDEX.read_text(encoding="utf-8")
        blocks = {}
        for language in LANGUAGES:
            match = re.search(rf"\n    {language}: {{", source)
            assert match, f"no {language} block in STRINGS"
            blocks[language] = _block(source, match.end() - 1)
        return blocks

    def _leaf_keys(self, block: str, dotted: str) -> set:
        current = block
        for part in dotted.split("."):
            match = re.search(rf"\b{re.escape(part)}: {{", current)
            assert match, f"{dotted!r} is missing at {part!r}"
            current = _block(current, match.end() - 1)
        # Only the table's own direct keys, not anything nested deeper.
        return set(re.findall(r"^\s{10}(\w+):", current, re.MULTILINE)) or set(
            re.findall(r"[{,]\s*(\w+):", current)
        )

    @pytest.mark.parametrize("table", TABLES)
    def test_all_three_languages_define_the_same_keys(self, dictionaries: dict, table: str) -> None:
        keys = {lang: self._leaf_keys(dictionaries[lang], table) for lang in LANGUAGES}
        assert keys["en"], f"{table} looks empty — the extraction regex missed it"
        assert keys["en"] == keys["tr"] == keys["de"], (
            f"{table} differs across languages: "
            f"en-only={keys['en'] - keys['tr'] - keys['de']}, "
            f"missing-from-tr={keys['en'] - keys['tr']}, "
            f"missing-from-de={keys['en'] - keys['de']}"
        )

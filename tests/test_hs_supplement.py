"""The HS 2022 supplement: HS-6 subheadings the EU CN bundle does not cover.

The CN bundle misses 359 of the 1,229 HS headings (4014, 8541, ...). The
supplement fills every uncovered HS-6 subheading from the public-domain WCO
HS 2022 list (data/hs2022_source.csv), built by scripts/build_hs_supplement.py.
"""

import csv
import sqlite3
from pathlib import Path

import pytest

from scripts.build_hs_supplement import build_rows
from src.customsiq.database import (
    fetch_all_contexts,
    get_by_code,
    get_connection,
    load_bundled_cn_nomenclature,
    load_bundled_hs_supplement,
    seed,
)
from src.customsiq.exceptions import RateNotFoundError
from src.customsiq.risk import assess_shipment
from src.customsiq.search import search
from src.customsiq.tariff_calculator import calculate_duty
from src.utils.validators import validate_cn_code, validate_hs_code
from tests.helpers import signed_in_test_client

DATA = Path(__file__).parent.parent / "data"


def _read(name: str) -> list:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def supplement() -> list:
    return _read("hs2022_supplement.csv")


@pytest.fixture(scope="module")
def source() -> list:
    return _read("hs2022_source.csv")


@pytest.fixture(scope="module")
def cn_codes() -> set:
    return {row["cn_code"] for row in _read("cn_nomenclature_2026.csv")}


@pytest.fixture(scope="module")
def catalogue() -> sqlite3.Connection:
    conn = get_connection(":memory:")
    seed(conn)
    load_bundled_cn_nomenclature(conn)
    load_bundled_hs_supplement(conn)
    return conn


class TestTheCommittedData:
    def test_the_source_is_the_full_hs_2022(self, source: list) -> None:
        levels = [row["level"] for row in source]
        assert levels.count("4") == 1229
        assert levels.count("6") == 5613

    def test_the_supplement_is_exactly_what_the_builder_produces(
        self, supplement: list, source: list, cn_codes: set
    ) -> None:
        """The committed file is reproducible from the committed inputs."""
        assert build_rows(source, cn_codes) == supplement

    def test_every_row_is_a_real_six_digit_hs_code(self, supplement: list, source: list) -> None:
        hs6 = {row["hscode"] for row in source if row["level"] == "6"}
        assert len(supplement) == 2897
        for row in supplement:
            assert len(row["hs_code"]) == 6 and row["hs_code"].isdigit()
            assert row["hs_code"] in hs6
            assert row["description_en"] and row["context_en"] and row["category"]

    def test_nothing_overlaps_the_eu_bundle(self, supplement: list, cn_codes: set) -> None:
        covered = {code[:6] for code in cn_codes}
        assert not [row["hs_code"] for row in supplement if row["hs_code"] in covered]

    def test_together_they_cover_every_hs_subheading(
        self, supplement: list, source: list, cn_codes: set
    ) -> None:
        covered = {code[:6] for code in cn_codes} | {row["hs_code"] for row in supplement}
        hs6 = {row["hscode"] for row in source if row["level"] == "6"}
        assert hs6 <= covered


class TestTheLoadedCatalogue:
    @pytest.mark.parametrize(
        ("code", "words"),
        [
            ("401410", "sheath contraceptives"),
            ("854143", "photovoltaic cells assembled in modules"),
        ],
    )
    def test_the_missing_headings_are_now_there(
        self, catalogue: sqlite3.Connection, code: str, words: str
    ) -> None:
        assert words in get_by_code(catalogue, code).description

    def test_a_supplement_row_carries_its_heading_as_context(
        self, catalogue: sqlite3.Connection
    ) -> None:
        context = fetch_all_contexts(catalogue, "en")["401410"]
        assert context.startswith("Hygienic or pharmaceutical articles")

    @pytest.mark.parametrize("typed", ["401410", "4014.10", "4014 10", "4014-10"])
    def test_a_six_digit_code_is_looked_up_directly(
        self, catalogue: sqlite3.Connection, typed: str
    ) -> None:
        results = search(catalogue, typed)
        assert [r.hs_code.code for r in results] == ["401410"]
        assert results[0].score == 1.0

    @pytest.mark.parametrize(
        ("query", "prefix"),
        [("photovoltaic panel", "8541"), ("pacemaker", "9021"), ("sulphuric acid", "2807")],
    )
    def test_queries_into_formerly_missing_headings(
        self, catalogue: sqlite3.Connection, query: str, prefix: str
    ) -> None:
        codes = [r.hs_code.code for r in search(catalogue, query, limit=5)]
        assert any(code.startswith(prefix) for code in codes), codes


class TestSixDigitCodesDownstream:
    def test_the_validators(self) -> None:
        assert validate_hs_code("401410")
        assert validate_hs_code("40141000") and validate_hs_code("4014100000")
        assert not validate_hs_code("4014") and not validate_hs_code("40141")
        # Invoice extraction keeps the strict CN rule: a six-digit number on a
        # document (a postcode, a date) must not be read as a tariff code.
        assert not validate_cn_code("401410")

    def test_duty_on_an_hs6_code_is_rate_not_found_not_invalid(
        self, catalogue: sqlite3.Connection
    ) -> None:
        with pytest.raises(RateNotFoundError):
            calculate_duty(catalogue, "401410", "CN", 100.0)

    def test_risk_still_scores_a_description_that_classifies_to_hs6(
        self, catalogue: sqlite3.Connection
    ) -> None:
        result = assess_shipment(
            catalogue,
            country_of_origin="CN",
            party_name="Example Trading Co",
            customs_value=1000.0,
            description="condom",
        )
        assert result.hs_code == "401410"

    def test_the_live_app_serves_them(self) -> None:
        client = signed_in_test_client()
        body = client.get("/search", params={"q": "condom", "limit": 1}).json()
        assert body[0]["code"] == "401410"
        assert client.get("/codes/401410/history").status_code in (200, 404)

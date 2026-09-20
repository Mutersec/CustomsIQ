"""Tests for the composite shipment risk scoring layer."""

import sqlite3

import pytest

from src.customsiq.database import get_connection, seed
from src.customsiq.exceptions import InvalidQueryError
from src.customsiq.models import TariffRate
from src.customsiq.risk import assess_shipment


@pytest.fixture
def conn() -> sqlite3.Connection:
    """An in-memory database, seeded like the other modules' tests."""
    connection = get_connection(":memory:")
    seed(connection)
    return connection


class TestWorkedExamples:
    """The pinned worked-example table from the plan, as real assertions."""

    def test_clean_shipment_is_low(self, conn: sqlite3.Connection) -> None:
        """Clean screening, confident classification, 0% preferential duty."""
        result = assess_shipment(conn, "NO", "Quokka Beachwear", 1000, description="cotton t-shirt")
        assert result.composite_score == pytest.approx(0.0609, abs=1e-4)
        assert result.level == "low"
        assert result.hs_code == "6109100000"

    def test_combined_moderate_factors_is_medium(self, conn: sqlite3.Connection) -> None:
        """Near-miss screening + low confidence + missing rate: none alone disqualifying."""
        result = assess_shipment(
            conn, "CN", "Northwind Logistics", 500, description="plastic thing"
        )
        assert result.composite_score == pytest.approx(0.4989, abs=1e-4)
        assert result.level == "medium"
        assert result.hs_code == "3926909700"

    def test_real_screening_hit_is_high(self, conn: sqlite3.Connection) -> None:
        """A real sanctions hit alone pushes an otherwise clean shipment to high."""
        result = assess_shipment(
            conn, "NO", "Northwind Maritime", 1000, description="cotton t-shirt"
        )
        assert result.composite_score == pytest.approx(0.6609, abs=1e-4)
        assert result.level == "high"

    def test_unclassifiable_description_is_medium(self, conn: sqlite3.Connection) -> None:
        """No shared term at all is treated as maximum classification risk."""
        result = assess_shipment(conn, "CN", "Quokka Beachwear", 100, description="device")
        assert result.composite_score == pytest.approx(0.25, abs=1e-4)
        assert result.level == "medium"
        assert result.hs_code is None
        by_name = {f.name: f for f in result.factors}
        assert by_name["classification"].score == 1.0
        assert by_name["duty"].score == 0.0


class TestWeights:
    """Screening dominates: a real hit alone is enough to reach 'high'."""

    def test_real_hit_alone_reaches_high(self, conn: sqlite3.Connection) -> None:
        """Even with clean classification and duty, a real hit crosses the high threshold."""
        result = assess_shipment(conn, "NO", "Northwind Maritime", 1000, hs_code="6109100000")
        by_name = {f.name: f for f in result.factors}
        assert by_name["screening"].score == 1.0
        assert by_name["classification"].score == 0.0  # hs_code given directly
        assert result.level == "high"


class TestScreeningTiers:
    """The visible difference between clean, near-miss and a real hit."""

    def test_clean_scores_zero(self, conn: sqlite3.Connection) -> None:
        result = assess_shipment(conn, "NO", "Quokka Beachwear", 100, hs_code="6109100000")
        assert {f.name: f.score for f in result.factors}["screening"] == 0.0

    def test_near_miss_scores_moderate(self, conn: sqlite3.Connection) -> None:
        result = assess_shipment(conn, "NO", "Northwind Logistics", 100, hs_code="6109100000")
        assert {f.name: f.score for f in result.factors}["screening"] == 0.4

    def test_real_hit_scores_maximum(self, conn: sqlite3.Connection) -> None:
        result = assess_shipment(conn, "NO", "Northwind Maritime", 100, hs_code="6109100000")
        assert {f.name: f.score for f in result.factors}["screening"] == 1.0


class TestValidation:
    """Exactly one of description/hs_code, and bad input still surfaces."""

    def test_neither_given_raises(self, conn: sqlite3.Connection) -> None:
        with pytest.raises(InvalidQueryError):
            assess_shipment(conn, "NO", "Quokka Beachwear", 100)

    def test_both_given_raises(self, conn: sqlite3.Connection) -> None:
        with pytest.raises(InvalidQueryError):
            assess_shipment(
                conn,
                "NO",
                "Quokka Beachwear",
                100,
                description="cotton t-shirt",
                hs_code="6109100000",
            )

    def test_malformed_hs_code_propagates_from_calculate_duty(
        self, conn: sqlite3.Connection
    ) -> None:
        with pytest.raises(InvalidQueryError):
            assess_shipment(conn, "NO", "Quokka Beachwear", 100, hs_code="not-a-code")


class TestMissingRate:
    """A code with no tariff rate on record scores the duty factor, not an error."""

    def test_missing_rate_scores_0_6(self, conn: sqlite3.Connection) -> None:
        # 3004900000 (Medicaments) is seeded in hs_codes but has no tariff_rates row.
        result = assess_shipment(conn, "CN", "Quokka Beachwear", 100, hs_code="3004900000")
        assert {f.name: f.score for f in result.factors}["duty"] == 0.6


class TestDutyScoreClamp:
    """The duty factor never exceeds 1.0, even for a high preferential rate."""

    def test_high_preferential_rate_clamps_to_1(self, conn: sqlite3.Connection) -> None:
        # Synthetic rate today's real seed data doesn't contain: 90% preferential.
        rate = TariffRate("6109100000", "XX", "preferential", 90.0, "Test Agreement", "2024-01-01")
        conn.execute(
            "INSERT INTO tariff_rates "
            "(hs_code, country_of_origin, rate_type, rate_percent, trade_agreement, valid_from) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                rate.hs_code,
                rate.country_of_origin,
                rate.rate_type,
                rate.rate_percent,
                rate.trade_agreement,
                rate.valid_from,
            ),
        )
        conn.commit()

        result = assess_shipment(conn, "XX", "Quokka Beachwear", 100, hs_code="6109100000")
        duty_score = {f.name: f.score for f in result.factors}["duty"]
        assert duty_score == 1.0

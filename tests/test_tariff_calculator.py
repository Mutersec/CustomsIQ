"""Tests for the customs duty calculation module."""

import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from src.customsiq.database import TARIFF_RATES, fetch_rates_for_code, get_connection, seed
from src.customsiq.exceptions import InvalidQueryError, RateNotFoundError
from src.customsiq.models import TariffRate
from src.customsiq.tariff_calculator import calculate_duty, select_rate


@pytest.fixture
def conn() -> sqlite3.Connection:
    """An in-memory database pre-seeded with the mock tariff rates."""
    connection = get_connection(":memory:")
    seed(connection)
    return connection


class TestSeeding:
    """The tariff_rates table alongside the other two."""

    def test_seed_populates_tariff_rates(self, conn: sqlite3.Connection) -> None:
        """Every mock rate is stored, and rates are retrievable per code."""
        rates = fetch_rates_for_code(conn, "6109100000")
        assert {r.rate_type for r in rates} == {"standard", "preferential"}

    def test_seed_is_idempotent(self, conn: sqlite3.Connection) -> None:
        """Re-seeding must not duplicate rates."""
        seed(conn)
        total = sum(len(fetch_rates_for_code(conn, r.hs_code)) for r in TARIFF_RATES)
        seed(conn)
        assert sum(len(fetch_rates_for_code(conn, r.hs_code)) for r in TARIFF_RATES) == total


class TestRateSelection:
    """Which of a code's rates applies to a given origin."""

    def test_standard_rate_for_an_uncovered_origin(self, conn: sqlite3.Connection) -> None:
        """An origin with no agreement gets the MFN rate."""
        rate = select_rate(fetch_rates_for_code(conn, "6109100000"), "CN")
        assert rate is not None
        assert rate.rate_type == "standard"
        assert rate.rate_percent == 12.0
        assert rate.trade_agreement is None

    def test_preferential_rate_beats_standard(self, conn: sqlite3.Connection) -> None:
        """A covered origin gets the preferential rate instead."""
        rate = select_rate(fetch_rates_for_code(conn, "6109100000"), "NO")
        assert rate is not None
        assert rate.rate_type == "preferential"
        assert rate.rate_percent == 0.0
        assert rate.trade_agreement == "EU-Solvia Free Trade Agreement"

    def test_origin_matching_is_case_insensitive(self, conn: sqlite3.Connection) -> None:
        """Lowercase origin codes still match their agreement."""
        rate = select_rate(fetch_rates_for_code(conn, "6109100000"), "no")
        assert rate is not None
        assert rate.rate_type == "preferential"

    def test_future_dated_rate_is_ignored(self, conn: sqlite3.Connection) -> None:
        """A rate that is not yet in force must not be applied."""
        rates = fetch_rates_for_code(conn, "6402990000")
        assert any(r.valid_from == "2030-01-01" for r in rates)  # it is in the data

        rate = select_rate(rates, "JP", as_of=date(2025, 6, 1))
        assert rate is not None
        assert rate.rate_type == "standard"  # falls back, not the future preference

    def test_future_dated_rate_applies_once_in_force(self, conn: sqlite3.Connection) -> None:
        """The same rate does apply on a date after it enters into force."""
        rate = select_rate(fetch_rates_for_code(conn, "6402990000"), "JP", as_of=date(2031, 1, 1))
        assert rate is not None
        assert rate.rate_type == "preferential"


class TestCalculation:
    """The duty arithmetic and its explanation."""

    def test_standard_duty(self, conn: sqlite3.Connection) -> None:
        """1000 at the 12% MFN rate is 120."""
        result = calculate_duty(conn, "6109100000", "CN", 1000.0)
        assert result.duty_amount == Decimal("120.00")
        assert result.total_payable == Decimal("1120.00")
        assert result.rate_type == "standard"
        assert "Standard MFN rate" in result.explanation

    def test_preferential_duty_is_zero_under_the_agreement(self, conn: sqlite3.Connection) -> None:
        """The same goods from a covered origin attract no duty."""
        result = calculate_duty(conn, "6109100000", "NO", 1000.0)
        assert result.duty_amount == Decimal("0.00")
        assert result.rate_type == "preferential"
        assert result.trade_agreement == "EU-Solvia Free Trade Agreement"
        assert "Preferential rate" in result.explanation
        assert "NO" in result.explanation

    def test_partial_preference_still_charges_duty(self, conn: sqlite3.Connection) -> None:
        """A reduced-but-nonzero preferential rate is applied as given."""
        result = calculate_duty(conn, "6203420000", "NO", 500.0)
        assert result.rate_percent == 4.0
        assert result.duty_amount == Decimal("20.00")

    def test_amount_is_rounded_to_cents(self, conn: sqlite3.Connection) -> None:
        """A rate producing fractions of a cent rounds half-up to 2 dp."""
        result = calculate_duty(conn, "8544421000", "CN", 99.99)  # 3.3%
        assert result.duty_amount == Decimal("3.30")

    def test_zero_value_yields_zero_duty(self, conn: sqlite3.Connection) -> None:
        """A zero customs value is valid and owes nothing."""
        result = calculate_duty(conn, "6109100000", "CN", 0.0)
        assert result.duty_amount == Decimal("0.00")
        assert result.total_payable == Decimal("0.00")

    def test_origin_is_normalised_in_the_result(self, conn: sqlite3.Connection) -> None:
        """The reported origin is upper-cased regardless of input."""
        assert calculate_duty(conn, "6109100000", "cn", 10.0).country_of_origin == "CN"


class TestFailureModes:
    """Bad input and missing data."""

    def test_negative_value_is_rejected(self, conn: sqlite3.Connection) -> None:
        """A negative customs value is not a refund."""
        with pytest.raises(InvalidQueryError, match="negative"):
            calculate_duty(conn, "6109100000", "CN", -1.0)

    def test_invalid_hs_code_is_rejected(self, conn: sqlite3.Connection) -> None:
        """A malformed code fails before any lookup."""
        with pytest.raises(InvalidQueryError, match="not a valid"):
            calculate_duty(conn, "6109", "CN", 100.0)

    def test_invalid_country_code_is_rejected(self, conn: sqlite3.Connection) -> None:
        """The origin must be an ISO 3166-1 alpha-2 code."""
        with pytest.raises(InvalidQueryError, match="country code"):
            calculate_duty(conn, "6109100000", "NORWAY", 100.0)

    def test_missing_rate_raises_rather_than_returning_zero(self, conn: sqlite3.Connection) -> None:
        """A code with no rate on record is a data gap, not a free import."""
        with pytest.raises(RateNotFoundError, match="No tariff rate on record"):
            calculate_duty(conn, "99999999", "CN", 100.0)

    def test_no_rate_in_force_yet_raises(self) -> None:
        """A code whose only rate is future-dated has none in force today."""
        connection = get_connection(":memory:")
        seed(
            connection,
            records=[],
            entities=[],
            rates=[TariffRate("12345678", "ALL", "standard", 5.0, None, "2099-01-01")],
        )
        with pytest.raises(RateNotFoundError, match="in force"):
            calculate_duty(connection, "12345678", "CN", 100.0)

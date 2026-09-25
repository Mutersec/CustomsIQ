"""Tests for the CustomsIQ HS code database and search module."""

import sqlite3

import pytest

from src.customsiq.database import SAMPLE_DATA, fetch_all, get_by_code, get_connection, seed
from src.customsiq.exceptions import HSCodeNotFoundError, InvalidQueryError
from src.customsiq.matching import MAX_QUERY_LENGTH
from src.customsiq.models import HSCode
from src.customsiq.search import search


@pytest.fixture
def conn() -> sqlite3.Connection:
    """An in-memory database pre-seeded with sample HS codes."""
    connection = get_connection(":memory:")
    seed(connection)
    return connection


def test_get_connection_creates_schema() -> None:
    """A fresh connection should expose an empty, queryable hs_codes table."""
    connection = get_connection(":memory:")
    assert fetch_all(connection) == []


def test_seed_inserts_sample_data(conn: sqlite3.Connection) -> None:
    """Seeding should load every sample record exactly once."""
    records = fetch_all(conn)
    assert len(records) == len(SAMPLE_DATA)
    assert HSCode("8517120000", "Mobile phones and smartphones", "Electronics") in records


def test_seed_is_idempotent(conn: sqlite3.Connection) -> None:
    """Seeding an already-populated table must not duplicate rows."""
    seed(conn)
    assert len(fetch_all(conn)) == len(SAMPLE_DATA)


def test_search_finds_best_match(conn: sqlite3.Connection) -> None:
    """A query close to a known description should rank that code first."""
    results = search(conn, "cotton t-shirt knitted")
    assert results[0].hs_code.code == "6109100000"
    assert results[0].score > 0.5


def test_search_respects_limit(conn: sqlite3.Connection) -> None:
    """search() should never return more than `limit` results."""
    results = search(conn, "phone", limit=3)
    assert len(results) <= 3


def test_search_rejects_empty_query(conn: sqlite3.Connection) -> None:
    """Blank/whitespace-only queries must raise InvalidQueryError."""
    with pytest.raises(InvalidQueryError):
        search(conn, "   ")


def test_search_rejects_too_long_query(conn: sqlite3.Connection) -> None:
    """Queries longer than MAX_QUERY_LENGTH must raise InvalidQueryError."""
    with pytest.raises(InvalidQueryError):
        search(conn, "x" * (MAX_QUERY_LENGTH + 1))


def test_search_handles_special_characters(conn: sqlite3.Connection) -> None:
    """Special/SQL-injection-shaped input must not raise or corrupt data."""
    results = search(conn, "'; DROP TABLE hs_codes; --")
    assert isinstance(results, list)
    assert len(fetch_all(conn)) == len(SAMPLE_DATA)  # table untouched

    emoji_results = search(conn, "📱 Handy-Ladegerät")
    assert isinstance(emoji_results, list)


def test_get_by_code_found(conn: sqlite3.Connection) -> None:
    """get_by_code() should return the exact record for a known code."""
    record = get_by_code(conn, "8517120000")
    assert record.category == "Electronics"


def test_get_by_code_not_found(conn: sqlite3.Connection) -> None:
    """get_by_code() should raise HSCodeNotFoundError for an unknown code."""
    with pytest.raises(HSCodeNotFoundError):
        get_by_code(conn, "0000000000")


class TestCodeShapedQuery:
    """A code typed into search must be an exact lookup, not fuzzy noise.

    Regression guard for QA audit Critical Bug #3: an all-digit query scored
    against all-letter descriptions via difflib came back with an arbitrary,
    unrelated top result, since digits share almost nothing with letters.
    """

    def test_known_code_returns_the_exact_record_only(self, conn: sqlite3.Connection) -> None:
        results = search(conn, "8517120000")
        assert len(results) == 1
        assert results[0].hs_code.code == "8517120000"
        assert results[0].hs_code.category == "Electronics"
        assert results[0].score == 1.0

    @pytest.mark.parametrize("formatted", ["8517.12.0000", "8517 12 0000", "8517-12-0000"])
    def test_separators_are_normalized_before_lookup(
        self, conn: sqlite3.Connection, formatted: str
    ) -> None:
        results = search(conn, formatted)
        assert len(results) == 1
        assert results[0].hs_code.code == "8517120000"

    def test_code_shaped_but_nonexistent_code_returns_empty(self, conn: sqlite3.Connection) -> None:
        """Code-shaped and absent must come back clean, not as fuzzy garbage."""
        assert search(conn, "9999999999") == []

    def test_numeric_but_not_code_shaped_still_falls_through_to_fuzzy_scoring(
        self, conn: sqlite3.Connection
    ) -> None:
        """Wrong length (not 8 or 10 digits): unchanged pre-fix behavior."""
        results = search(conn, "12345")
        assert len(results) == 5
        assert all(isinstance(r.score, float) for r in results)

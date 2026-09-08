"""Tests for the sanctions / denied-party screening module."""

import sqlite3

import pytest

from src.customsiq.database import SANCTIONED_ENTITIES, fetch_all_entities, get_connection, seed
from src.customsiq.embargo_screener import screen_entity
from src.customsiq.exceptions import InvalidQueryError
from src.customsiq.matching import MAX_QUERY_LENGTH


@pytest.fixture
def conn() -> sqlite3.Connection:
    """An in-memory database pre-seeded with the mock sanctions list."""
    connection = get_connection(":memory:")
    seed(connection)
    return connection


def test_seed_populates_sanctioned_entities(conn: sqlite3.Connection) -> None:
    """Seeding should load every mock entity exactly once."""
    entities = fetch_all_entities(conn)
    assert len(entities) == len(SANCTIONED_ENTITIES)


def test_seed_is_idempotent(conn: sqlite3.Connection) -> None:
    """Re-seeding a populated table must not duplicate entities."""
    seed(conn)
    assert len(fetch_all_entities(conn)) == len(SANCTIONED_ENTITIES)


def test_exact_name_matches_with_top_score(conn: sqlite3.Connection) -> None:
    """An exact listed name scores 1.0 and ranks first."""
    matches = screen_entity(conn, "Northwind Maritime Holdings Ltd")
    assert matches[0].entity.name == "Northwind Maritime Holdings Ltd"
    assert matches[0].score == pytest.approx(1.0)
    assert matches[0].entity.country == "CY"


def test_partial_company_name_matches(conn: sqlite3.Connection) -> None:
    """A partial company name still surfaces the listed entity.

    Both the plain and token-sorted ratios score this pair at 0.73, below the
    0.75 threshold — only the token-overlap signal catches it.
    """
    matches = screen_entity(conn, "Northwind Maritime")
    assert "Northwind Maritime Holdings Ltd" in [m.entity.name for m in matches]


def test_reversed_word_order_matches(conn: sqlite3.Connection) -> None:
    """A name given first-name-first matches a surname-first list entry."""
    matches = screen_entity(conn, "Aleksandr Voronin-Teske")
    assert matches[0].entity.name == "Voronin-Teske, Aleksandr"


def test_unrelated_name_returns_no_matches(conn: sqlite3.Connection) -> None:
    """A name with nothing in common with the list returns an empty result."""
    assert screen_entity(conn, "Quokka Beachwear Collective") == []


def test_results_are_sorted_by_descending_score(conn: sqlite3.Connection) -> None:
    """Every returned match is above the threshold, best first."""
    matches = screen_entity(conn, "Maritime Holdings", threshold=0.4)
    scores = [m.score for m in matches]
    assert scores == sorted(scores, reverse=True)
    assert all(score >= 0.4 for score in scores)


def test_threshold_controls_sensitivity(conn: sqlite3.Connection) -> None:
    """Lowering the threshold can only widen the result set."""
    strict = screen_entity(conn, "Meridian Cargo", threshold=0.95)
    loose = screen_entity(conn, "Meridian Cargo", threshold=0.5)
    assert len(loose) >= len(strict)


def test_special_characters_are_handled(conn: sqlite3.Connection) -> None:
    """Punctuation-heavy and non-ASCII input is scored without crashing."""
    assert isinstance(screen_entity(conn, "!@#$%^&*() -- ';"), list)
    assert isinstance(screen_entity(conn, "Ünal Çelik Ticaret A.Ş."), list)

    injection = screen_entity(conn, "'; DROP TABLE sanctioned_entities; --")
    assert isinstance(injection, list)
    assert len(fetch_all_entities(conn)) == len(SANCTIONED_ENTITIES)  # table intact


def test_empty_name_is_rejected(conn: sqlite3.Connection) -> None:
    """Blank or whitespace-only input raises InvalidQueryError."""
    with pytest.raises(InvalidQueryError):
        screen_entity(conn, "   ")


def test_overlong_name_is_rejected(conn: sqlite3.Connection) -> None:
    """Input beyond MAX_QUERY_LENGTH raises InvalidQueryError."""
    with pytest.raises(InvalidQueryError):
        screen_entity(conn, "x" * (MAX_QUERY_LENGTH + 1))

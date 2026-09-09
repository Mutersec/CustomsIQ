"""Tests for TF-IDF based CN code classification."""

import sqlite3

import pytest

from src.customsiq.cn_classifier import _singular, classify
from src.customsiq.database import get_connection, seed
from src.customsiq.exceptions import InvalidQueryError
from src.customsiq.matching import MAX_QUERY_LENGTH
from src.customsiq.search import search


@pytest.fixture
def conn() -> sqlite3.Connection:
    """An in-memory database pre-seeded with the sample CN codes."""
    connection = get_connection(":memory:")
    seed(connection)
    return connection


class TestRanking:
    """Which codes come back, and in what order."""

    def test_rare_terms_outrank_common_ones(self, conn: sqlite3.Connection) -> None:
        """The defining word wins over the merely shared one.

        Regression guard for the case that justifies this module existing:
        difflib ranks "Men's cotton trousers" first here because of raw
        character overlap, while term weighting picks the knitted T-shirt.
        """
        top = classify(conn, "knitted cotton shirt")[0]
        assert top.hs_code.code == "6109100000"

        assert search(conn, "knitted cotton shirt")[0].hs_code.code == "6203420000"

    def test_scores_are_ordered_and_bounded(self, conn: sqlite3.Connection) -> None:
        """Confidence decreases down the list and stays a cosine in (0, 1]."""
        results = classify(conn, "cotton trousers for men")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
        assert all(0 < score <= 1.0000001 for score in scores)

    def test_top_n_is_respected(self, conn: sqlite3.Connection) -> None:
        """Never more suggestions than asked for."""
        assert len(classify(conn, "cotton", top_n=2)) <= 2

    def test_obvious_description_classifies_correctly(self, conn: sqlite3.Connection) -> None:
        """A clear description lands on the right code."""
        assert classify(conn, "lithium ion battery")[0].hs_code.code == "8507600000"
        assert classify(conn, "wooden furniture for an office")[0].hs_code.code == "9403300000"


class TestPluralFolding:
    """Descriptions are written in the plural; users type the singular."""

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("cable", "8544421000"),
            ("biscuit", "1905310000"),
            ("laptop", "8471300000"),
            ("battery", "8507600000"),  # needs the -ies -> y rule
        ],
    )
    def test_singular_query_matches_plural_description(
        self, conn: sqlite3.Connection, query: str, expected: str
    ) -> None:
        """Without folding every one of these scores zero against everything."""
        results = classify(conn, query)
        assert results, f"{query!r} returned nothing"
        assert results[0].hs_code.code == expected

    @pytest.mark.parametrize(
        ("plural", "singular"),
        [
            ("cables", "cable"),  # plain -s: must not lose the "e"
            ("batteries", "battery"),
            ("boxes", "box"),  # -es only after a sibilant
            ("dishes", "dish"),
            ("glasses", "glass"),
            ("glass", "glass"),  # -ss is not a plural
            ("gas", "gas"),  # too short to fold
        ],
    )
    def test_plural_rules(self, plural: str, singular: str) -> None:
        """The folding rules, including the sibilant case that "cables" broke."""
        assert _singular(plural) == singular


class TestExplainability:
    """Every suggestion must say why it was suggested."""

    def test_matched_terms_come_from_the_query(self, conn: sqlite3.Connection) -> None:
        """Reported terms are real, and are drawn from the input."""
        result = classify(conn, "portable data processing machine")[0]
        assert result.hs_code.code == "8471300000"
        assert result.matched_terms
        assert set(result.matched_terms) <= {"portable", "data", "processing", "machine"}

    def test_terms_are_capped(self, conn: sqlite3.Connection) -> None:
        """A long description still reports a readable handful of terms."""
        result = classify(conn, "cotton knitted t-shirts vests and other similar garments")[0]
        assert len(result.matched_terms) <= 3


class TestNoMatch:
    """The case the measurement spike exposed."""

    def test_unrelated_description_returns_nothing(self, conn: sqlite3.Connection) -> None:
        """Zero-overlap input yields an empty list, not zero-score noise."""
        assert classify(conn, "zephyr quokka bagpipes") == []

    def test_empty_corpus_returns_nothing(self) -> None:
        """Classifying against an unseeded database does not crash."""
        assert classify(get_connection(":memory:"), "cotton shirt") == []

    def test_description_with_no_words_returns_nothing(self, conn: sqlite3.Connection) -> None:
        """Input that tokenises to nothing yields an empty, zero-length vector."""
        assert classify(conn, "!!! ??? ---") == []


class TestValidation:
    """Input handling, reusing the shared validator."""

    def test_blank_description_is_rejected(self, conn: sqlite3.Connection) -> None:
        """Whitespace-only input raises rather than scanning the corpus."""
        with pytest.raises(InvalidQueryError):
            classify(conn, "   ")

    def test_overlong_description_is_rejected(self, conn: sqlite3.Connection) -> None:
        """The shared length cap applies here too."""
        with pytest.raises(InvalidQueryError):
            classify(conn, "x" * (MAX_QUERY_LENGTH + 1))

    def test_punctuation_and_non_ascii_are_tolerated(self, conn: sqlite3.Connection) -> None:
        """Odd input is tokenised away rather than crashing."""
        assert isinstance(classify(conn, "!!! ??? --- '; DROP TABLE hs_codes;"), list)
        assert isinstance(classify(conn, "Baumwoll-T-Shirts, gewirkt 📦"), list)

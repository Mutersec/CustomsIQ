"""Tests for the human-review / audit-trail layer."""

import sqlite3

import pytest

from src.customsiq.database import get_connection, seed
from src.customsiq.exceptions import InvalidQueryError
from src.customsiq.review import (
    get_review_history,
    reference_for_classification,
    reference_for_duty,
    reference_for_screening,
    submit_review,
)


@pytest.fixture
def conn() -> sqlite3.Connection:
    """An in-memory database, seeded like the other modules' tests."""
    connection = get_connection(":memory:")
    seed(connection)
    return connection


class TestDeterminism:
    """subject_reference must be a deterministic hash of the reviewed input."""

    def test_classification_reference_is_stable(self) -> None:
        """The same description twice gives the same reference."""
        assert reference_for_classification("knitted cotton shirt") == reference_for_classification(
            "knitted cotton shirt"
        )

    def test_classification_reference_matches_known_hash(self) -> None:
        """Pinned against the worked example in the plan/README, not just self-consistency."""
        assert (
            reference_for_classification("knitted cotton shirt")
            == "ca8b1b958f7a9136035ce4106495b252851544092bdce2797bc30b8687fc3407"
        )

    def test_classification_reference_folds_case(self) -> None:
        """Case is folded before hashing: it's the same decision either way."""
        assert reference_for_classification("KNITTED COTTON SHIRT") == reference_for_classification(
            "knitted cotton shirt"
        )

    def test_screening_reference_is_stable_and_case_folded(self) -> None:
        """Same rule as classification, applied to screening queries."""
        assert reference_for_screening("Northwind Maritime") == reference_for_screening(
            "northwind maritime"
        )
        assert (
            reference_for_screening("Northwind Maritime")
            == "fa9ec5ed3f84ae68c8c5729faa18e043297e7ec78aae9ab89bebeef82b32c38c"
        )

    def test_duty_reference_is_stable(self) -> None:
        """The same hs_code/country/value triple twice gives the same reference."""
        assert reference_for_duty("6109100000", "DE", 1000.00) == reference_for_duty(
            "6109100000", "DE", 1000.00
        )
        assert (
            reference_for_duty("6109100000", "DE", 1000.00)
            == "8e4b03f6c0353ab018c024b6e7045251867255b083df5637f5d01ef5602e3c2e"
        )

    def test_duty_reference_changes_with_value(self) -> None:
        """A different customs_value is a different decision to audit."""
        assert reference_for_duty("6109100000", "DE", 1000.00) != reference_for_duty(
            "6109100000", "DE", 1000.01
        )

    def test_different_subject_types_never_collide(self) -> None:
        """The subject_type prefix keeps classification and screening apart."""
        assert reference_for_classification("northwind maritime") != reference_for_screening(
            "northwind maritime"
        )


class TestSubmitReview:
    """Recording a reviewer's decision."""

    def test_submit_and_round_trip(self, conn: sqlite3.Connection) -> None:
        """A submitted decision is retrievable via get_review_history."""
        ref = reference_for_classification("cotton t-shirt")
        result = submit_review(conn, "classification", ref, "approved", "alice", "looks right")
        assert result.id is not None
        history = get_review_history(conn, subject_reference=ref)
        assert len(history) == 1
        assert history[0].decision == "approved"
        assert history[0].reviewer_name == "alice"
        assert history[0].comment == "looks right"

    def test_comment_is_optional(self, conn: sqlite3.Connection) -> None:
        """A review with no comment stores None."""
        ref = reference_for_screening("Quokka Beachwear")
        result = submit_review(conn, "screening", ref, "approved", "bob")
        assert result.comment is None

    def test_invalid_subject_type_rejected(self, conn: sqlite3.Connection) -> None:
        """Only the three known subject types are accepted."""
        with pytest.raises(InvalidQueryError, match="subject_type"):
            submit_review(conn, "bogus", "ref", "approved", "alice")

    def test_invalid_decision_rejected(self, conn: sqlite3.Connection) -> None:
        """Only approved/rejected/flagged are accepted."""
        with pytest.raises(InvalidQueryError, match="decision"):
            submit_review(conn, "classification", "ref", "maybe", "alice")

    def test_blank_reviewer_name_rejected(self, conn: sqlite3.Connection) -> None:
        """An empty reviewer_name is not a valid sign-off."""
        with pytest.raises(InvalidQueryError, match="reviewer_name"):
            submit_review(conn, "classification", "ref", "approved", "   ")

    def test_blank_subject_reference_rejected(self, conn: sqlite3.Connection) -> None:
        """An empty subject_reference has nothing to audit against."""
        with pytest.raises(InvalidQueryError, match="subject_reference"):
            submit_review(conn, "classification", "   ", "approved", "alice")


class TestAppendOnly:
    """review_decisions is an audit log: nothing is ever edited or deleted."""

    def test_two_decisions_on_same_subject_both_persist(self, conn: sqlite3.Connection) -> None:
        """A corrected decision is a new row, not an update."""
        ref = reference_for_duty("6109100000", "NO", 1000.0)
        submit_review(conn, "duty", ref, "flagged", "alice", "needs a second look")
        submit_review(conn, "duty", ref, "approved", "bob", "confirmed correct")
        history = get_review_history(conn, subject_reference=ref)
        assert len(history) == 2
        assert [h.decision for h in history] == ["approved", "flagged"]  # most recent first


class TestFiltering:
    """get_review_history filters by subject_type and subject_reference."""

    def test_filter_by_subject_type(self, conn: sqlite3.Connection) -> None:
        """Only decisions of the requested type come back."""
        submit_review(
            conn, "classification", reference_for_classification("a"), "approved", "alice"
        )
        submit_review(conn, "screening", reference_for_screening("b"), "approved", "alice")
        history = get_review_history(conn, subject_type="screening")
        assert len(history) == 1
        assert history[0].subject_type == "screening"

    def test_filter_by_subject_reference(self, conn: sqlite3.Connection) -> None:
        """Only decisions for the requested subject come back."""
        ref_a = reference_for_classification("a")
        ref_b = reference_for_classification("b")
        submit_review(conn, "classification", ref_a, "approved", "alice")
        submit_review(conn, "classification", ref_b, "approved", "alice")
        history = get_review_history(conn, subject_reference=ref_a)
        assert len(history) == 1
        assert history[0].subject_reference == ref_a

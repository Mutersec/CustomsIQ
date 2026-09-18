"""Tests for the read-only dashboard aggregation layer."""

import sqlite3

import pytest

from src.customsiq.dashboard import get_dashboard_stats
from src.customsiq.database import (
    SAMPLE_DATA,
    SANCTIONED_ENTITIES,
    TARIFF_RATES,
    get_connection,
    record_cn_import,
    seed,
    upsert_hs_codes_with_history,
)
from src.customsiq.models import HSCode
from src.customsiq.review import (
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


class TestReferenceDataCounts:
    """Counts over the seeded hs_codes / sanctioned_entities / tariff_rates."""

    def test_counts_match_the_seed_data(self, conn: sqlite3.Connection) -> None:
        """Reference-data counts reflect exactly what was seeded, nothing more."""
        stats = get_dashboard_stats(conn)
        assert stats.hs_code_count == len(SAMPLE_DATA)
        assert stats.sanctioned_entity_count == len(SANCTIONED_ENTITIES)
        assert stats.tariff_rate_count == len(TARIFF_RATES)


class TestZeroData:
    """A freshly seeded database has no reviews and no import runs yet."""

    def test_review_activity_is_all_zero_not_missing(self, conn: sqlite3.Connection) -> None:
        """Every breakdown key is present at 0, not omitted."""
        stats = get_dashboard_stats(conn)
        assert stats.review_total == 0
        assert stats.review_by_decision == {"approved": 0, "rejected": 0, "flagged": 0}
        assert stats.review_by_subject_type == {
            "classification": 0,
            "screening": 0,
            "duty": 0,
        }
        assert stats.recent_reviews == []

    def test_import_pipeline_is_empty(self, conn: sqlite3.Connection) -> None:
        """No import runs yet means empty lists and zero counts, not an error."""
        stats = get_dashboard_stats(conn)
        assert stats.import_run_count == 0
        assert stats.recent_import_runs == []
        assert stats.versioned_code_count == 0


class TestReviewBreakdown:
    """Aggregating a known set of review decisions."""

    def test_breakdown_matches_known_submissions(self, conn: sqlite3.Connection) -> None:
        """2 approved classifications, 1 rejected screening, 1 flagged duty."""
        submit_review(
            conn, "classification", reference_for_classification("a"), "approved", "alice"
        )
        submit_review(
            conn, "classification", reference_for_classification("b"), "approved", "alice"
        )
        submit_review(conn, "screening", reference_for_screening("c"), "rejected", "bob")
        submit_review(
            conn, "duty", reference_for_duty("6109100000", "DE", 1000.0), "flagged", "carol"
        )

        stats = get_dashboard_stats(conn)
        assert stats.review_total == 4
        assert stats.review_by_decision == {"approved": 2, "rejected": 1, "flagged": 1}
        assert stats.review_by_subject_type == {
            "classification": 2,
            "screening": 1,
            "duty": 1,
        }

    def test_recent_reviews_is_newest_first_and_capped(self, conn: sqlite3.Connection) -> None:
        """recent_reviews respects the requested limit and ordering."""
        for i in range(3):
            submit_review(
                conn, "classification", reference_for_classification(str(i)), "approved", "alice"
            )
        stats = get_dashboard_stats(conn, recent_reviews=2)
        assert len(stats.recent_reviews) == 2
        assert stats.recent_reviews[0].subject_reference == reference_for_classification("2")


class TestImportPipeline:
    """Aggregating CN import runs and version history."""

    def test_changed_and_unchanged_counts_per_run(self, conn: sqlite3.Connection) -> None:
        """A new code, an identical re-import, then a real change across three runs."""
        record = HSCode("11112222", "Desc A", "CatA")
        changed = HSCode("11112222", "Desc A2", "CatA")

        upsert_hs_codes_with_history(conn, [record], "V1")
        record_cn_import(conn, "V1", "v1.csv", "2026-01-01T00:00:00+00:00", 1)

        upsert_hs_codes_with_history(conn, [record], "V1-rerun")
        record_cn_import(conn, "V1-rerun", "v1.csv", "2026-01-02T00:00:00+00:00", 1)

        upsert_hs_codes_with_history(conn, [changed], "V2")
        record_cn_import(conn, "V2", "v2.csv", "2026-01-03T00:00:00+00:00", 1)

        stats = get_dashboard_stats(conn)
        assert stats.import_run_count == 3
        assert stats.versioned_code_count == 1  # 11112222 now has 2 history versions

        by_label = {s.run.version_label: s for s in stats.recent_import_runs}
        assert by_label["V1"].changed_count == 1
        assert by_label["V1"].unchanged_count == 0
        assert by_label["V1-rerun"].changed_count == 0
        assert by_label["V1-rerun"].unchanged_count == 1
        assert by_label["V2"].changed_count == 1
        assert by_label["V2"].unchanged_count == 0

    def test_recent_import_runs_is_newest_first(self, conn: sqlite3.Connection) -> None:
        """recent_import_runs is ordered newest first, matching fetch_cn_import_runs."""
        record_cn_import(conn, "V1", "a.csv", "2026-01-01T00:00:00+00:00", 5)
        record_cn_import(conn, "V2", "b.csv", "2026-01-02T00:00:00+00:00", 5)
        stats = get_dashboard_stats(conn)
        assert [s.run.version_label for s in stats.recent_import_runs] == ["V2", "V1"]

"""Parity tests against a real PostgreSQL server — opt-in, skipped by default.

Set CUSTOMSIQ_TEST_POSTGRES_URL to run them, e.g. against the compose service:

    docker compose --profile postgres up -d postgres
    CUSTOMSIQ_TEST_POSTGRES_URL=postgresql://customsiq:customsiq@localhost:5432/customsiq_test \\
        pytest tests/test_postgres.py

The default `pytest` run needs no server and no psycopg install. These tests
assert field-by-field values, not just row counts: every fixture column holds a
distinct value, so a shifted or swapped column cannot pass unnoticed.
"""

import os
from collections.abc import Iterator

import pytest

from src.customsiq import auth
from src.customsiq.dashboard import get_dashboard_stats
from src.customsiq.database import (
    SAMPLE_DATA,
    SANCTIONED_ENTITIES,
    TARIFF_RATES,
    count_history_rows_by_version_label,
    count_versioned_codes,
    fetch_all,
    fetch_all_entities,
    fetch_all_rates,
    fetch_authored_review_ids,
    fetch_cn_import_runs,
    fetch_hs_code_history,
    fetch_rates_for_code,
    fetch_review_decisions,
    get_by_code,
    get_connection,
    record_cn_import,
    seed,
    upsert_hs_codes_with_history,
)
from src.customsiq.exceptions import InvalidQueryError
from src.customsiq.models import HSCode
from src.customsiq.review import reference_for_classification, submit_review
from src.customsiq.risk import assess_shipment

POSTGRES_URL = os.environ.get("CUSTOMSIQ_TEST_POSTGRES_URL")

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not POSTGRES_URL,
        reason="set CUSTOMSIQ_TEST_POSTGRES_URL to run the PostgreSQL parity tests",
    ),
]

_TABLES = (
    "hs_codes",
    "sanctioned_entities",
    "tariff_rates",
    "review_decisions",
    "hs_code_history",
    "cn_code_versions",
    "users",
    "sessions",
    "review_authorship",
)


@pytest.fixture
def conn() -> Iterator[object]:
    """A seeded PostgreSQL connection, wiped between tests.

    Refuses to touch a database whose name doesn't contain "test": this
    fixture drops every table, which must never hit a real database.
    """
    assert POSTGRES_URL is not None
    database_name = POSTGRES_URL.rsplit("/", 1)[-1].split("?")[0]
    if "test" not in database_name:
        pytest.fail(
            f"refusing to run destructive tests against database {database_name!r} — "
            "CUSTOMSIQ_TEST_POSTGRES_URL must point at a database whose name contains 'test'"
        )

    connection = get_connection(POSTGRES_URL)
    for table in _TABLES:
        connection.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    connection.close()

    connection = get_connection(POSTGRES_URL)  # recreates the schema
    try:
        yield connection
    finally:
        connection.close()


class TestSchemaAndSeeding:
    """The translated DDL produces a working, seedable schema."""

    def test_seed_populates_every_reference_table(self, conn) -> None:
        seed(conn)
        assert len(fetch_all(conn)) == len(SAMPLE_DATA)
        assert len(fetch_all_entities(conn)) == len(SANCTIONED_ENTITIES)
        assert len(fetch_all_rates(conn)) == len(TARIFF_RATES)

    def test_seed_is_idempotent(self, conn) -> None:
        """Re-seeding must not duplicate rows, same as on SQLite."""
        seed(conn)
        seed(conn)
        assert len(fetch_all(conn)) == len(SAMPLE_DATA)


class TestPositionalRowReads:
    """Every column must land in the right dataclass field, not just the right count."""

    def test_hs_code_fields_are_not_shifted(self, conn) -> None:
        """description != category, so a swap would be visible."""
        seed(conn)
        record = get_by_code(conn, "6109100000")
        assert record == HSCode("6109100000", "Cotton T-shirts, knitted", "Textile")

    def test_sanctioned_entity_fields_are_not_shifted(self, conn) -> None:
        seed(conn)
        entity = next(e for e in fetch_all_entities(conn) if e.name.startswith("Northwind"))
        assert entity.name == "Northwind Maritime Holdings Ltd"
        assert entity.country == "CY"
        assert entity.list_source == "EU Consolidated Financial Sanctions List"
        assert entity.date_added == "2023-04-12"

    def test_tariff_rate_fields_including_none_trade_agreement(self, conn) -> None:
        """Covers both a NULL and a populated nullable column."""
        seed(conn)
        rates = {r.rate_type: r for r in fetch_rates_for_code(conn, "6109100000")}
        standard = rates["standard"]
        assert standard.hs_code == "6109100000"
        assert standard.country_of_origin == "ALL"
        assert standard.trade_agreement is None
        assert standard.valid_from == "2024-01-01"
        assert rates["preferential"].trade_agreement == "EU-Solvia Free Trade Agreement"

    def test_rate_percent_keeps_full_double_precision(self, conn) -> None:
        """REAL would be float4 here and read 16.9 back as 16.899999618530273."""
        seed(conn)
        footwear = next(
            r for r in fetch_rates_for_code(conn, "6402990000") if r.rate_type == "standard"
        )
        assert footwear.rate_percent == 16.9

    def test_review_decision_fields_including_generated_id(self, conn) -> None:
        """id comes from RETURNING on Postgres rather than lastrowid."""
        seed(conn)
        stored = submit_review(conn, "duty", "ref-1", "flagged", "alice", "needs a look")
        assert isinstance(stored.id, int)

        fetched = fetch_review_decisions(conn, subject_reference="ref-1")[0]
        assert fetched.id == stored.id
        assert fetched.subject_type == "duty"
        assert fetched.subject_reference == "ref-1"
        assert fetched.decision == "flagged"
        assert fetched.reviewer_name == "alice"
        assert fetched.comment == "needs a look"
        assert fetched.reviewed_at == stored.reviewed_at

    def test_null_comment_round_trips_as_none(self, conn) -> None:
        seed(conn)
        submit_review(conn, "screening", "ref-2", "approved", "bob")
        assert fetch_review_decisions(conn, subject_reference="ref-2")[0].comment is None


class TestVersioningParity:
    """The SCD Type 2 write path behaves identically on Postgres."""

    def test_changed_code_closes_old_version_and_opens_a_new_one(self, conn) -> None:
        record = HSCode("11112222", "Desc A", "CatA")
        changed = HSCode("11112222", "Desc A2", "CatA")

        stats_new = upsert_hs_codes_with_history(conn, [record], "V1")
        stats_same = upsert_hs_codes_with_history(conn, [record], "V1-rerun")
        stats_changed = upsert_hs_codes_with_history(conn, [changed], "V2")

        assert (stats_new.new_count, stats_new.changed_count) == (1, 0)
        assert stats_same.unchanged_count == 1
        assert stats_changed.changed_count == 1

        history = fetch_hs_code_history(conn, "11112222")
        assert [h.description for h in history] == ["Desc A", "Desc A2"]
        assert history[0].valid_to is not None
        assert history[0].version_label == "V1"
        assert history[1].valid_to is None
        assert history[1].version_label == "V2"
        assert history[1].category == "CatA"
        assert len(fetch_all(conn)) == 1  # hs_codes still holds one current row

    def test_count_versioned_codes_subquery_alias_works(self, conn) -> None:
        """PostgreSQL before 16 rejects an unaliased subquery."""
        upsert_hs_codes_with_history(conn, [HSCode("11112222", "A", "C")], "V1")
        assert count_versioned_codes(conn) == 0
        upsert_hs_codes_with_history(conn, [HSCode("11112222", "B", "C")], "V2")
        assert count_versioned_codes(conn) == 1

    def test_import_run_fields_and_label_counts(self, conn) -> None:
        upsert_hs_codes_with_history(conn, [HSCode("11112222", "A", "C")], "CN2026")
        record_cn_import(conn, "CN2026", "cn2026.csv", "2026-02-01T09:00:00+00:00", 10)

        run = fetch_cn_import_runs(conn)[0]
        assert run.version_label == "CN2026"
        assert run.source_description == "cn2026.csv"
        assert run.imported_at == "2026-02-01T09:00:00+00:00"
        assert run.row_count == 10
        assert isinstance(run.id, int)
        assert count_history_rows_by_version_label(conn) == {"CN2026": 1}


class TestAuthOnPostgres:
    """Accounts, sessions and authorship work on the second backend too."""

    def test_account_round_trip_and_login(self, conn) -> None:
        user = auth.create_user(conn, "alice", "test-password-123", auth.COMPLIANCE_OFFICER)
        assert user.id > 0
        assert auth.authenticate(conn, "alice", "test-password-123").role == (
            auth.COMPLIANCE_OFFICER
        )

    def test_duplicate_usernames_are_refused(self, conn) -> None:
        """The UNIQUE constraint survives the DDL translation."""
        auth.create_user(conn, "alice", "test-password-123")
        with pytest.raises(InvalidQueryError, match="already taken"):
            auth.create_user(conn, "alice", "test-password-123")

    def test_session_create_resolve_and_logout(self, conn) -> None:
        user = auth.create_user(conn, "alice", "test-password-123", auth.ANALYST)
        token = auth.create_session(conn, user)
        resolved = auth.user_for_token(conn, token)
        assert resolved is not None and resolved.username == "alice"
        auth.logout(conn, token)
        assert auth.user_for_token(conn, token) is None

    def test_authorship_separates_authenticated_from_legacy_rows(self, conn) -> None:
        """The flag that keeps a free-text name from being claimed by an account."""
        seed(conn)
        user = auth.create_user(conn, "alice", "test-password-123", auth.ANALYST)
        authored = submit_review(
            conn, "duty", "ref-auth", "approved", user.username, None, reviewer_user_id=user.id
        )
        legacy = submit_review(conn, "duty", "ref-legacy", "approved", "alice", None)

        ids = fetch_authored_review_ids(conn, [authored.id, legacy.id])
        assert ids == {authored.id}


class TestModulesOnPostgres:
    """The seven unmodified modules work through the Postgres connection."""

    def test_dashboard_stats(self, conn) -> None:
        seed(conn)
        submit_review(conn, "classification", reference_for_classification("a"), "approved", "eve")

        stats = get_dashboard_stats(conn)
        assert stats.hs_code_count == len(SAMPLE_DATA)
        assert stats.tariff_rate_count == len(TARIFF_RATES)
        assert stats.review_total == 1
        assert stats.review_by_decision == {"approved": 1, "rejected": 0, "flagged": 0}
        assert stats.recent_reviews[0].reviewer_name == "eve"

    def test_risk_assessment_end_to_end(self, conn) -> None:
        """Same pinned composite score the SQLite suite asserts."""
        seed(conn)
        result = assess_shipment(
            conn, "NO", "Northwind Maritime", 1000, description="cotton t-shirt"
        )
        assert result.level == "high"
        assert result.composite_score == pytest.approx(0.6609, abs=1e-4)
        assert result.hs_code == "6109100000"

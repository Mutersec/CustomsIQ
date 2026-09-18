"""Read-only aggregation of Phase 1/2 data into dashboard summary stats.

No new business logic and no new decisions are made here — everything below
composes what src.customsiq.database already stores and exposes.
"""

import sqlite3
from collections import Counter
from typing import NamedTuple

from src.customsiq import database
from src.customsiq.models import ImportRun, ReviewDecision

_DECISIONS = ("approved", "rejected", "flagged")
_SUBJECT_TYPES = ("classification", "screening", "duty")

# ponytail: pulls every review/import row into Python to count — fine at demo
# scale; switch to a SQL GROUP BY (see database.count_history_rows_by_version_label
# for the pattern) if either table gets large.
_ALL = 1_000_000


class ImportRunSummary(NamedTuple):
    """One import run, enriched with how many codes it actually versioned."""

    run: ImportRun
    changed_count: int  # hs_code_history rows stamped with this run's version_label
    unchanged_count: int  # run.row_count - changed_count


class DashboardStats(NamedTuple):
    """Everything the dashboard panel needs, in one call."""

    hs_code_count: int
    sanctioned_entity_count: int
    tariff_rate_count: int
    review_total: int
    review_by_decision: dict[str, int]
    review_by_subject_type: dict[str, int]
    recent_reviews: list[ReviewDecision]
    import_run_count: int
    recent_import_runs: list[ImportRunSummary]
    versioned_code_count: int


def get_dashboard_stats(
    conn: sqlite3.Connection, recent_reviews: int = 10, recent_import_runs: int = 10
) -> DashboardStats:
    """Aggregate reference-data, review-activity and CN-pipeline stats.

    Args:
        conn: An open database connection.
        recent_reviews: How many of the most recent review decisions to include.
        recent_import_runs: How many of the most recent import runs to include.

    Returns:
        A DashboardStats snapshot. Breakdown dicts always contain every known
        key (0 if unused), so a fresh database renders cleanly rather than
        forcing the caller to guard against missing keys.
    """
    all_reviews = database.fetch_review_decisions(conn, limit=_ALL)
    all_runs = database.fetch_cn_import_runs(conn, limit=_ALL)
    changed_by_run = database.count_history_rows_by_version_label(conn)

    by_decision = {d: 0 for d in _DECISIONS}
    by_decision.update(Counter(r.decision for r in all_reviews))
    by_subject_type = {s: 0 for s in _SUBJECT_TYPES}
    by_subject_type.update(Counter(r.subject_type for r in all_reviews))

    run_summaries = []
    for run in all_runs[:recent_import_runs]:
        changed = changed_by_run.get(run.version_label, 0)
        run_summaries.append(ImportRunSummary(run, changed, run.row_count - changed))

    return DashboardStats(
        hs_code_count=len(database.fetch_all(conn)),
        sanctioned_entity_count=len(database.fetch_all_entities(conn)),
        tariff_rate_count=len(database.fetch_all_rates(conn)),
        review_total=len(all_reviews),
        review_by_decision=by_decision,
        review_by_subject_type=by_subject_type,
        recent_reviews=all_reviews[:recent_reviews],
        import_run_count=len(all_runs),
        recent_import_runs=run_summaries,
        versioned_code_count=database.count_versioned_codes(conn),
    )

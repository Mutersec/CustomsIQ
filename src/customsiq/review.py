"""Human-review / audit-trail layer sitting on top of the three decision features.

Models the "four-eyes principle" common in trade compliance tools: a reviewer can
approve, reject or flag a past classification, screening or duty result. Decisions
are append-only — a corrected decision is a new row, never an edit.
"""

import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from src.customsiq import database
from src.customsiq.exceptions import InvalidQueryError
from src.customsiq.models import ReviewDecision

#: Public: the API reads this to reject an unknown subject type before
#: it reaches the permission check, so a typo is a 400 and not a 403.
VALID_SUBJECT_TYPES = {"classification", "screening", "duty"}
_VALID_DECISIONS = {"approved", "rejected", "flagged"}


def _hash(subject_type: str, normalized: str) -> str:
    return hashlib.sha256(f"{subject_type}:{normalized}".encode()).hexdigest()


def reference_for_classification(description: str) -> str:
    """Deterministic subject_reference for a classification query.

    Case-folded before hashing: the TF-IDF decision is case-insensitive, so
    "Cotton Shirt" and "cotton shirt" audit the same underlying decision.
    """
    return _hash("classification", description.strip().lower())


def reference_for_screening(name: str) -> str:
    """Deterministic subject_reference for a sanctions screening query.

    Case-folded before hashing, for the same reason as classification: the
    fuzzy matcher already treats case as irrelevant.
    """
    return _hash("screening", name.strip().lower())


def reference_for_duty(hs_code: str, country_of_origin: str, customs_value: float) -> str:
    """Deterministic subject_reference for a duty calculation.

    customs_value is fixed to 2 decimals before hashing (money has no
    meaningful precision beyond cents), so 1000 and 1000.00 are the same
    subject but 1000.01 is a different one — a different value is a
    different decision to audit.
    """
    normalized = (
        f"{hs_code.strip().upper()}|{country_of_origin.strip().upper()}|{customs_value:.2f}"
    )
    return _hash("duty", normalized)


def submit_review(
    conn: sqlite3.Connection,
    subject_type: str,
    subject_reference: str,
    decision: str,
    reviewer_name: str,
    comment: Optional[str] = None,
    reviewer_user_id: Optional[int] = None,
) -> ReviewDecision:
    """Record a reviewer's decision on a subject. Always inserts, never updates.

    Args:
        conn: An open database connection.
        subject_type: "classification" | "screening" | "duty".
        subject_reference: The deterministic hash identifying what was reviewed.
        decision: "approved" | "rejected" | "flagged".
        reviewer_name: Who signed off. The API passes the authenticated user's
            username here; the CLI still passes free text.
        comment: Optional free-text note.
        reviewer_user_id: The authenticated author's `users.id`, when there is
            one. Given, the row is linked in `review_authorship` and reads back
            as authenticated; omitted (CLI, and every row written before
            accounts existed), the name stands on its own and is reported as
            unauthenticated rather than being matched to a user by name.

    Returns:
        The stored ReviewDecision, including its assigned id and timestamp.

    Raises:
        InvalidQueryError: If subject_type, decision or reviewer_name is invalid.
    """
    if subject_type not in VALID_SUBJECT_TYPES:
        raise InvalidQueryError(
            f"subject_type must be one of {sorted(VALID_SUBJECT_TYPES)}, got {subject_type!r}"
        )
    if decision not in _VALID_DECISIONS:
        raise InvalidQueryError(
            f"decision must be one of {sorted(_VALID_DECISIONS)}, got {decision!r}"
        )
    if not reviewer_name or not reviewer_name.strip():
        raise InvalidQueryError("reviewer_name must not be blank")
    if not subject_reference or not subject_reference.strip():
        raise InvalidQueryError("subject_reference must not be blank")

    reviewed_at = datetime.now(timezone.utc).isoformat()
    new_id = database.insert_review_decision(
        conn, subject_type, subject_reference, decision, reviewer_name, comment, reviewed_at
    )
    if reviewer_user_id is not None:
        database.insert_review_authorship(conn, new_id, reviewer_user_id)
    return ReviewDecision(
        id=new_id,
        subject_type=subject_type,
        subject_reference=subject_reference,
        decision=decision,
        reviewer_name=reviewer_name,
        comment=comment,
        reviewed_at=reviewed_at,
    )


def authored_review_ids(conn: sqlite3.Connection, decisions: list[ReviewDecision]) -> set:
    """Return which of these decisions were signed off by an authenticated user.

    One query for the whole page rather than one per row. Callers use it to
    label the rest honestly as legacy/unauthenticated instead of implying an
    account behind every historical name.
    """
    return database.fetch_authored_review_ids(conn, [decision.id for decision in decisions])


def get_review_history(
    conn: sqlite3.Connection,
    subject_type: Optional[str] = None,
    subject_reference: Optional[str] = None,
    limit: int = 50,
) -> list[ReviewDecision]:
    """Return recorded review decisions, most recently reviewed first."""
    return database.fetch_review_decisions(conn, subject_type, subject_reference, limit)

"""Star ratings and comments about the service, published after the owner approves them.

One rating per account. A new or edited rating is 'pending' and visible only to
its author and the site owner; the owner approves or rejects it from the admin
panel. Only approved ratings count towards the average and are shown to other
users. Not to be confused with review decisions (sign-offs on results).
"""

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from src.customsiq import database
from src.customsiq.models import User

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
STATUSES = (PENDING, APPROVED, REJECTED)

MIN_COMMENT = 10
MAX_COMMENT = 500
MAX_COMPANY = 80
PUBLIC_LIMIT = 50


def _public(row: database.SiteRating) -> dict:
    """What other users see: no user id, no status."""
    return {
        "username": row.username,
        "rating": row.rating,
        "comment": row.comment,
        "company": row.company,
        "date": row.updated_at,
    }


def _own(row: Optional[database.SiteRating]) -> Optional[dict]:
    if row is None:
        return None
    return {**_public(row), "status": row.status}


def overview(conn: sqlite3.Connection, user: User) -> dict:
    """Approved ratings with their average and distribution, plus the caller's own rating."""
    distribution = database.rating_distribution(conn, APPROVED)
    count = sum(distribution.values())
    total = sum(stars * n for stars, n in distribution.items())
    return {
        "average": round(total / count, 1) if count else None,
        "count": count,
        "distribution": {str(stars): n for stars, n in distribution.items()},
        "items": [_public(r) for r in database.fetch_ratings(conn, APPROVED, PUBLIC_LIMIT)],
        "mine": _own(database.get_rating_for_user(conn, user.id)),
    }


def submit(
    conn: sqlite3.Connection, user: User, rating: int, comment: str, company: Optional[str]
) -> dict:
    """Save the caller's rating as pending (a new one, or an edit that needs re-approval)."""
    company = (company or "").strip() or None
    database.upsert_rating(
        conn,
        user.id,
        user.username,
        rating,
        comment.strip(),
        company,
        PENDING,
        datetime.now(timezone.utc).isoformat(),
    )
    return _own(database.get_rating_for_user(conn, user.id)) or {}


def for_owner(conn: sqlite3.Connection, status: Optional[str]) -> list[dict]:
    """Ratings for the admin panel, with ids and statuses."""
    return [
        {**_public(r), "id": r.id, "status": r.status, "created_at": r.created_at}
        for r in database.fetch_ratings(conn, status, limit=500)
    ]

"""The site owner's admin panel: who the owner is, the activity log, and its reports.

The panel is locked to e-mail addresses, not to a role. `admin` is a role any
account can be given, and the published `demo_admin` account has its password
in the source code; "only the site owner" therefore means "a signed-in account
whose verified e-mail is in `CUSTOMSIQ_OWNER_EMAILS`".

The activity log records what signed-in users do so the owner can see it:
the text they searched for, how many results came back and the top code,
uploads (as a field count only), review sign-offs and sign-ins. It never
records a password, a verification code, invoice content or an IP address.
"""

import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.customsiq import auth, database
from src.customsiq.config import settings
from src.customsiq.models import User

logger = logging.getLogger(__name__)

#: Actions whose `detail` is a query the user typed; the "searches" counters.
SEARCH_ACTIONS = ("search", "classify", "screen", "risk")

#: Product searches whose empty result means the catalogue lacks a word. A
#: screening with no hit is the good outcome, not a gap, so it is left out.
UNMATCHED_ACTIONS = ("search", "classify")

#: Every action the log records, in the order the panel's filter lists them.
ACTIONS = (
    "search",
    "classify",
    "screen",
    "duty",
    "risk",
    "invoice",
    "review",
    "login",
    "google",
    "signup",
    "logout",
)

#: A query is clipped to this length before it is stored.
MAX_DETAIL = 200

_PRUNE_EVERY_SECONDS = 3600.0
_last_prune = 0.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_owner(conn: sqlite3.Connection, user: Optional[User]) -> bool:
    """Whether this account's verified e-mail is one of the configured owner e-mails."""
    if user is None or not settings.owner_email_set:
        return False
    email = database.get_email_for_user(conn, user.id)
    return email is not None and email.lower() in settings.owner_email_set


def prune(conn: sqlite3.Connection, now: Optional[datetime] = None) -> int:
    """Delete activity older than the retention period, returning how many rows went."""
    cutoff = (now or _now()) - timedelta(days=settings.activity_retention_days)
    return database.delete_activity_before(conn, cutoff.isoformat())


def record(
    conn: sqlite3.Connection,
    user: Optional[User],
    action: str,
    detail: Optional[str] = None,
    result_count: Optional[int] = None,
    top_code: Optional[str] = None,
) -> None:
    """Append one activity row for a signed-in user.

    Never raises: the log is bookkeeping, and a failure to write it must not
    fail the search or sign-in it describes. Old rows are pruned at most once
    an hour, piggybacking on a write rather than needing a scheduler.
    """
    global _last_prune
    if user is None:
        return
    try:
        clipped = detail.strip()[:MAX_DETAIL] if detail else None
        database.insert_activity(
            conn,
            user.id,
            user.username,
            action,
            clipped or None,
            result_count,
            top_code,
            _now().isoformat(),
        )
        if time.monotonic() - _last_prune > _PRUNE_EVERY_SECONDS:
            _last_prune = time.monotonic()
            prune(conn)
    except Exception:  # noqa: BLE001 — see the docstring
        logger.exception("could not record %s activity", action)


def overview(conn: sqlite3.Connection, version: str) -> dict:
    """Headline numbers and system status for the panel's first tab."""
    now = _now()
    iso_now = now.isoformat()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    day_ago = (now - timedelta(days=1)).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()
    return {
        "users_total": database.count_users(conn),
        "users_new_today": database.count_rows(conn, "users", "created_at >= ?", (today,)),
        "users_new_week": database.count_rows(conn, "users", "created_at >= ?", (week_ago,)),
        "pending_signups": database.count_rows(
            conn, "pending_signups", "expires_at > ?", (iso_now,)
        ),
        "active_sessions": database.count_rows(conn, "sessions", "expires_at > ?", (iso_now,)),
        "searches_day": database.count_activity_since(conn, day_ago, SEARCH_ACTIONS),
        "searches_week": database.count_activity_since(conn, week_ago, SEARCH_ACTIONS),
        "actions_day": database.count_activity_since(conn, day_ago, ACTIONS),
        "actions_week": database.count_activity_since(conn, week_ago, ACTIONS),
        "system": {
            "version": version,
            "database": getattr(conn, "dialect", "sqlite"),
            "mail_configured": bool(settings.brevo_api_key),
            "google_configured": bool(settings.google_client_id),
            "demo_users_enabled": settings.seed_demo_users,
            "cn_codes": database.count_rows(conn, "hs_codes", "LENGTH(code) >= 8"),
            "hs6_codes": database.count_rows(conn, "hs_codes", "LENGTH(code) = 6"),
            "sanctioned_entities": database.count_rows(conn, "sanctioned_entities"),
            "activity_rows": database.count_rows(conn, "activity_log"),
            "retention_days": settings.activity_retention_days,
        },
    }


def _sign_up_method(user: User, email: Optional[tuple[str, bool]]) -> str:
    if email is not None:
        return "google" if email[1] else "email"
    if user.username in {name for name, _, _ in auth.DEMO_USERS}:
        return "demo"
    return "password"


def list_users(conn: sqlite3.Connection) -> list[dict]:
    """Every account with its e-mail, sign-up method and last activity, newest first."""
    emails = database.fetch_user_emails(conn)
    last_seen = database.fetch_last_activity_by_user(conn)
    owners = settings.owner_email_set
    rows = []
    for user in reversed(database.fetch_users(conn)):
        email = emails.get(user.id)
        rows.append(
            {
                "username": user.username,
                "email": email[0] if email else None,
                "method": _sign_up_method(user, email),
                "role": user.role,
                "created_at": user.created_at,
                "last_activity": last_seen.get(user.id),
                "is_owner": bool(email and email[0].lower() in owners),
            }
        )
    return rows


def activity_page(
    conn: sqlite3.Connection,
    username: Optional[str],
    action: Optional[str],
    text: Optional[str],
    zero_only: bool,
    limit: int,
    offset: int,
) -> dict:
    """One filtered page of the activity log, newest first."""
    entries, total = database.fetch_activity(
        conn, username or None, action or None, text or None, zero_only, limit, offset
    )
    return {
        "total": total,
        "items": [entry._asdict() for entry in entries],
    }


def unmatched_searches(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    """Queries that found nothing, most often searched first."""
    return [
        {"query": query, "count": count, "last_searched": last}
        for query, count, last in database.fetch_unmatched_searches(conn, UNMATCHED_ACTIONS, limit)
    ]

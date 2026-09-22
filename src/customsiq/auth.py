"""Accounts, sessions and role-based access control.

The layer the audit trail was always missing: `review_decisions.reviewer_name`
used to be whatever the client typed, and now it is whoever is signed in.

Deliberately dependency-free. Everything here is stdlib — `hashlib`, `hmac`,
`secrets`, `base64` — so `requirements.txt` (the file the live deployment's
build installs) is untouched by this phase. See the README's
"🔐 Authentication without a dependency" section for why passlib/argon2/bcrypt
were each rejected, and what PBKDF2 costs in exchange.

Sessions are opaque random tokens stored hashed in the `sessions` table, not
signed cookies or JWTs: that makes logout and role changes take effect on the
very next request, which a self-contained token cannot do without a denylist —
and a denylist is this table wearing a hat.
"""

import base64
import hashlib
import hmac
import logging
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.customsiq import database
from src.customsiq.config import settings
from src.customsiq.exceptions import AuthenticationError, InvalidQueryError
from src.customsiq.models import User

logger = logging.getLogger(__name__)

VIEWER = "viewer"
ANALYST = "analyst"
COMPLIANCE_OFFICER = "compliance_officer"
ADMIN = "admin"

#: Roles from least to most privileged. A role covers every action assigned to
#: a role at or below its index.
ROLE_ORDER = (VIEWER, ANALYST, COMPLIANCE_OFFICER, ADMIN)

#: The one place permissions are defined — routes ask `can()`, they don't
#: hardcode role names. Signing off on a *screening* result needs a compliance
#: officer because denied-party screening is the regulated decision of the
#: three; classification and duty sign-offs are analyst work.
PERMISSIONS = {
    "review:classification": ANALYST,
    "review:duty": ANALYST,
    "review:screening": COMPLIANCE_OFFICER,
    "audit:read": VIEWER,
    "users:manage": ADMIN,
}

#: Role handed out by self-registration. Demo-friendliness, not realism: a real
#: trade-compliance system grants roles administratively after verifying the
#: person, rather than letting a signup form pick one. Set this to VIEWER to
#: get the production-shaped flow (register, then wait for an admin promotion).
SELF_REGISTRATION_ROLE = ANALYST

#: Published demo accounts, seeded only into an empty `users` table so a
#: visitor can experience every role. Mock data, public passwords — the README
#: says so loudly; `CUSTOMSIQ_SEED_DEMO_USERS=false` turns them off.
DEMO_USERS = (
    ("demo_viewer", "viewer-demo-2026", VIEWER),
    ("demo_analyst", "analyst-demo-2026", ANALYST),
    ("demo_officer", "officer-demo-2026", COMPLIANCE_OFFICER),
    ("demo_admin", "admin-demo-2026", ADMIN),
)

_ALGORITHM = "pbkdf2_sha256"
_SALT_BYTES = 16
_MIN_PASSWORD_LENGTH = 8
_MAX_USERNAME_LENGTH = 32

# A real-shaped hash to verify against when the username is unknown, so a login
# attempt costs the same either way and timing can't enumerate accounts.
_DUMMY_PASSWORD = "customsiq-dummy-password"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def hash_password(password: str, iterations: Optional[int] = None) -> str:
    """Hash a password for storage.

    The result is self-describing — `pbkdf2_sha256$<iterations>$<salt>$<hash>` —
    so the algorithm and work factor travel with each row and can be raised
    later without a migration: an old hash still verifies, and can be rewritten
    on the user's next successful login.

    Args:
        password: The plaintext password. Never stored anywhere.
        iterations: Work factor; defaults to `settings.password_iterations`.

    Returns:
        The encoded hash string.
    """
    # ponytail: PBKDF2 is not memory-hard, so GPUs get a better cost ratio
    # against it than against argon2id. Upgrade path is argon2-cffi + a new
    # branch keyed on the algorithm prefix already stored in every hash.
    rounds = settings.password_iterations if iterations is None else iterations
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"{_ALGORITHM}${rounds}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    """Check a password against a stored hash, in constant time.

    A malformed or unknown-algorithm hash returns False rather than raising:
    this runs on the login path, where the caller must not be able to tell a
    corrupt row from a wrong password.
    """
    try:
        algorithm, rounds, salt_b64, digest_b64 = encoded.split("$")
        if algorithm != _ALGORITHM:
            return False
        expected = base64.b64decode(digest_b64)
        salt = base64.b64decode(salt_b64)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
    except (ValueError, TypeError):
        logger.warning("stored password hash is malformed")
        return False
    return hmac.compare_digest(candidate, expected)


def can(role: str, action: str) -> bool:
    """Return whether a role covers an action.

    Args:
        role: One of ROLE_ORDER.
        action: A key of PERMISSIONS, e.g. "review:screening".

    Returns:
        True if the role ranks at or above the action's requirement. An unknown
        role or action is always False — a typo denies rather than grants.
    """
    required = PERMISSIONS.get(action)
    if required is None or role not in ROLE_ORDER:
        return False
    return ROLE_ORDER.index(role) >= ROLE_ORDER.index(required)


def _validate_credentials(username: str, password: str) -> str:
    """Return the normalized username, or raise InvalidQueryError."""
    normalized = username.strip().lower()
    if not normalized:
        raise InvalidQueryError("username must not be blank")
    if len(normalized) > _MAX_USERNAME_LENGTH:
        raise InvalidQueryError(f"username must be at most {_MAX_USERNAME_LENGTH} characters")
    if not all(character.isalnum() or character in "_-." for character in normalized):
        raise InvalidQueryError("username may only contain letters, digits, '_', '-' and '.'")
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise InvalidQueryError(f"password must be at least {_MIN_PASSWORD_LENGTH} characters")
    return normalized


def create_user(
    conn: sqlite3.Connection, username: str, password: str, role: str = SELF_REGISTRATION_ROLE
) -> User:
    """Create an account.

    Args:
        conn: An open database connection.
        username: Login name; case-folded, and unique.
        password: Plaintext password, hashed before it touches the database.
        role: One of ROLE_ORDER.

    Returns:
        The stored User.

    Raises:
        InvalidQueryError: If the username or password is unusable, the role is
            unknown, or the username is already taken.
    """
    normalized = _validate_credentials(username, password)
    if role not in ROLE_ORDER:
        raise InvalidQueryError(f"role must be one of {list(ROLE_ORDER)}, got {role!r}")
    if database.get_user_by_username(conn, normalized) is not None:
        raise InvalidQueryError(f"username '{normalized}' is already taken")

    created_at = datetime.now(timezone.utc).isoformat()
    new_id = database.insert_user(conn, normalized, hash_password(password), role, created_at)
    logger.info("created user %s with role %s", normalized, role)
    return User(id=new_id, username=normalized, role=role, created_at=created_at)


def authenticate(conn: sqlite3.Connection, username: str, password: str) -> User:
    """Verify a username and password.

    Args:
        conn: An open database connection.
        username: Login name, matched case-insensitively.
        password: Plaintext password to check.

    Returns:
        The authenticated User.

    Raises:
        AuthenticationError: If either the username or the password is wrong.
            One message covers both, so the error can't be used to discover
            which usernames exist.
    """
    normalized = username.strip().lower()
    stored = database.get_password_hash(conn, normalized)
    if stored is None:
        # Spend the same time as a real verification: without this, a fast
        # rejection would tell an attacker the username doesn't exist.
        verify_password(password, hash_password(_DUMMY_PASSWORD))
        raise AuthenticationError("invalid username or password")
    if not verify_password(password, stored):
        raise AuthenticationError("invalid username or password")

    user = database.get_user_by_username(conn, normalized)
    assert user is not None  # the hash lookup above just found this row
    return user


def _token_hash(token: str) -> str:
    """Hash a session token for storage.

    Plain SHA-256 with no salt or stretching is correct here and nowhere else
    in this module: the token is 256 bits of CSPRNG output, so there is no
    low-entropy secret for a slow KDF to protect.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(conn: sqlite3.Connection, user: User) -> str:
    """Start a session and return its token (the only time it exists in clear).

    Args:
        conn: An open database connection.
        user: The user the session belongs to.

    Returns:
        The opaque session token to hand back as a cookie.
    """
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    expires_at = (now + timedelta(hours=settings.session_ttl_hours)).isoformat()
    database.insert_session(conn, _token_hash(token), user.id, now.isoformat(), expires_at)
    # Opportunistic cleanup: expired rows are already unusable, this just stops
    # the table growing forever. Cheap enough to do on a login.
    database.delete_expired_sessions(conn, now.isoformat())
    return token


def user_for_token(conn: sqlite3.Connection, token: Optional[str]) -> Optional[User]:
    """Return the signed-in user behind a session token, or None.

    None covers every "not signed in" case — no cookie, unknown token, expired
    session, or a user deleted since — so callers need one check, not four.
    """
    if not token:
        return None
    now = datetime.now(timezone.utc).isoformat()
    user_id = database.fetch_session_user_id(conn, _token_hash(token), now)
    if user_id is None:
        return None
    return database.get_user_by_id(conn, user_id)


def logout(conn: sqlite3.Connection, token: Optional[str]) -> None:
    """End a session. Unknown or missing tokens are a no-op, never an error."""
    if token:
        database.delete_session(conn, _token_hash(token))


def seed_demo_users(conn: sqlite3.Connection) -> int:
    """Create the published demo accounts, but only into an empty users table.

    Mirrors `database._seed_if_empty`: once anything real exists, this never
    touches it again, so a deployment that created its own accounts can't be
    handed public credentials by a later restart.

    Args:
        conn: An open database connection.

    Returns:
        How many accounts were created (0 if any account already existed).
    """
    if database.count_users(conn):
        logger.debug("users already populated, skipping demo accounts")
        return 0
    for username, password, role in DEMO_USERS:
        create_user(conn, username, password, role)
    logger.info("seeded %d demo accounts", len(DEMO_USERS))
    return len(DEMO_USERS)

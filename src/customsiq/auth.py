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
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import cache
from typing import Optional

from src.customsiq import database, mailer
from src.customsiq.config import settings
from src.customsiq.database import PendingSignup
from src.customsiq.exceptions import (
    AuthenticationError,
    InvalidQueryError,
    VerificationCooldownError,
)
from src.customsiq.google_identity import GoogleIdentity
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
    # Uploading a document is the one endpoint that spends CPU parsing
    # attacker-supplied binary, so it is the one analysis feature that isn't
    # anonymous. Viewer is deliberately the floor: the demo accounts are
    # published, so the feature stays tryable by anyone who signs in.
    "document:extract": VIEWER,
    "users:manage": ADMIN,
}

#: Role handed out by self-registration, from `CUSTOMSIQ_SELF_REGISTRATION_ROLE`
#: (default `viewer`). A real trade-compliance system grants roles
#: administratively after verifying the person, rather than letting a signup
#: form pick one — so the default is the production-shaped flow: register, then
#: wait for an admin promotion. It used to default to ANALYST, which meant one
#: anonymous POST bought the ability to write permanent, append-only rows into
#: the compliance audit trail; a security audit called that in, and this is the
#: fix. The value stays a module constant so callers and tests refer to it by
#: name rather than hardcoding a role string.
SELF_REGISTRATION_ROLE = settings.self_registration_role

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


@cache
def _dummy_hash(rounds: int) -> str:
    """A throwaway hash to verify against when the username doesn't exist.

    Generated once per work factor and reused. That matters for the property
    it exists to provide: this used to be recomputed per request, so an unknown
    username cost *two* PBKDF2 runs (one to build the hash, one to check it)
    against a known username's one — a 2x timing difference that enumerated
    accounts just as effectively as the fast rejection the dummy was meant to
    prevent. Cached by `rounds` rather than computed at import so the test
    suite's lowered work factor doesn't pay the production cost.
    """
    return hash_password(_DUMMY_PASSWORD, iterations=rounds)


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
    """Verify a username (or verified e-mail) and password.

    Args:
        conn: An open database connection.
        username: Login name, or the verified e-mail of an account, matched
            case-insensitively.
        password: Plaintext password to check.

    Returns:
        The authenticated User.

    Raises:
        AuthenticationError: If either the username or the password is wrong.
            One message covers both, so the error can't be used to discover
            which usernames exist.
    """
    normalized = username.strip().lower()
    if "@" in normalized:
        user_id = database.get_user_id_by_email(conn, normalized)
        owner = database.get_user_by_id(conn, user_id) if user_id is not None else None
        normalized = owner.username if owner else ""
    stored = database.get_password_hash(conn, normalized) if normalized else None
    if stored is None:
        # Spend the same time as a real verification: without this, a fast
        # rejection would tell an attacker the username doesn't exist. Exactly
        # one verification, against a cached dummy — see `_dummy_hash`.
        verify_password(password, _dummy_hash(settings.password_iterations))
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


# ---------------------------------------------------------------------------
# Sign-up with e-mail verification
#
# No account exists until the person proves they can read mail sent to the
# address they gave: a sign-up is parked in `pending_signups` with a hash of a
# six-digit code, and only `confirm_signup` turns it into a `users` row.
# Google sign-ups skip the code: Google has already proved the address, and
# `google_identity.verify_credential` only accepts a token whose signature,
# audience, issuer and `email_verified` claim all check out (see
# `google_sign_in` below).
#
# What makes a six-digit code safe is not the hash — a million candidates are
# trivial to try offline — but the limits around it: it expires after
# `verification_code_ttl_minutes`, dies after `verification_max_attempts`
# wrong guesses, a new one cannot be requested for
# `verification_resend_seconds`, and every route involved sits behind the
# per-IP auth rate limit. Hashing only keeps the code out of the database in
# clear.
# ---------------------------------------------------------------------------

_EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
_MAX_EMAIL_LENGTH = 254
_CODE_DIGITS = 6


def normalize_email(email: str) -> str:
    """Return the case-folded e-mail, or raise InvalidQueryError if it isn't one."""
    normalized = email.strip().lower()
    if len(normalized) > _MAX_EMAIL_LENGTH or not _EMAIL_PATTERN.match(normalized):
        raise InvalidQueryError("please enter a valid e-mail address")
    return normalized


def _code_hash(email: str, code: str) -> str:
    return hashlib.sha256(f"{email}:{code}".encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _check_cooldown(conn: sqlite3.Connection, email: str) -> None:
    pending = database.get_pending_signup(conn, email)
    if pending is None:
        return
    elapsed = (_now() - datetime.fromisoformat(pending.sent_at)).total_seconds()
    wait = settings.verification_resend_seconds - int(elapsed)
    if wait > 0:
        raise VerificationCooldownError(wait)


def _issue_code(
    conn: sqlite3.Connection,
    email: str,
    username: str,
    password_hash: str,
    google_sub: Optional[str],
    language: str,
    attempts: int = 0,
) -> None:
    """Store a fresh code for this e-mail and send it. Raises if the mail fails."""
    code = f"{secrets.randbelow(10**_CODE_DIGITS):0{_CODE_DIGITS}d}"
    now = _now()
    pending = PendingSignup(
        email=email,
        username=username,
        password_hash=password_hash,
        google_sub=google_sub,
        code_hash=_code_hash(email, code),
        language=language if language in mailer.LANGUAGES else "en",
        attempts=attempts,
        sent_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=settings.verification_code_ttl_minutes)).isoformat(),
    )
    database.upsert_pending_signup(conn, pending)
    try:
        mailer.send_verification_code(email, code, pending.language)
    except Exception:
        # A code nobody received must not block a retry behind the cooldown.
        database.delete_pending_signup(conn, email)
        raise


def _ensure_available(conn: sqlite3.Connection, username: str, email: str) -> None:
    if database.get_user_by_username(conn, username) is not None:
        raise InvalidQueryError(f"username '{username}' is already taken")
    if database.pending_username_taken(conn, username, email):
        raise InvalidQueryError(f"username '{username}' is already taken")
    if database.get_user_id_by_email(conn, email) is not None:
        raise InvalidQueryError("an account with this e-mail already exists")


def start_signup(
    conn: sqlite3.Connection, username: str, email: str, password: str, language: str = "en"
) -> str:
    """Begin an e-mail/password sign-up: validate, park it, and e-mail a code.

    Returns:
        The normalized e-mail the code was sent to.

    Raises:
        InvalidQueryError: Unusable username, password or e-mail, or one taken.
        VerificationCooldownError: A code was sent to this e-mail very recently.
        mailer.MailNotConfiguredError / mailer.MailDeliveryError: Sending failed.
    """
    normalized = _validate_credentials(username, password)
    email = normalize_email(email)
    _ensure_available(conn, normalized, email)
    _check_cooldown(conn, email)
    _issue_code(conn, email, normalized, hash_password(password), None, language)
    return email


def resend_code(conn: sqlite3.Connection, email: str) -> None:
    """Send a new code for a pending sign-up, keeping its attempt count.

    Raises:
        AuthenticationError: There is no live pending sign-up for this e-mail.
        VerificationCooldownError: The last code was sent too recently.
    """
    email = normalize_email(email)
    pending = database.get_pending_signup(conn, email)
    if pending is None or pending.expires_at <= _now().isoformat():
        raise AuthenticationError("this sign-up has expired; please start again")
    _check_cooldown(conn, email)
    _issue_code(
        conn,
        email,
        pending.username,
        pending.password_hash,
        pending.google_sub,
        pending.language,
        attempts=pending.attempts,
    )


def confirm_signup(conn: sqlite3.Connection, email: str, code: str) -> User:
    """Check a sign-up's code and, if right, create the account.

    Raises:
        AuthenticationError: No live sign-up, the code is wrong, or the attempts
            are used up (which also discards the sign-up).
        InvalidQueryError: The username or e-mail was taken in the meantime.
    """
    email = normalize_email(email)
    pending = database.get_pending_signup(conn, email)
    if pending is None or pending.expires_at <= _now().isoformat():
        if pending is not None:
            database.delete_pending_signup(conn, email)
        raise AuthenticationError("this code has expired; please start again")
    if pending.attempts >= settings.verification_max_attempts:
        database.delete_pending_signup(conn, email)
        raise AuthenticationError("too many wrong codes; please start again")
    if not hmac.compare_digest(pending.code_hash, _code_hash(email, code.strip())):
        database.record_failed_code_attempt(conn, email)
        if pending.attempts + 1 >= settings.verification_max_attempts:
            database.delete_pending_signup(conn, email)
            raise AuthenticationError("too many wrong codes; please start again")
        raise AuthenticationError("that code is not correct")

    _ensure_available(conn, pending.username, email)
    created_at = _now().isoformat()
    user_id = database.insert_user(
        conn, pending.username, pending.password_hash, SELF_REGISTRATION_ROLE, created_at
    )
    database.insert_user_email(conn, user_id, email, pending.google_sub, created_at)
    database.delete_pending_signup(conn, email)
    logger.info("created verified user %s", pending.username)
    return User(
        id=user_id, username=pending.username, role=SELF_REGISTRATION_ROLE, created_at=created_at
    )


def _username_from_email(conn: sqlite3.Connection, email: str) -> str:
    """A free username derived from an e-mail's local part (for Google sign-ups)."""
    base = "".join(c for c in email.split("@")[0].lower() if c.isalnum() or c in "_-.")
    base = (base or "user")[: _MAX_USERNAME_LENGTH - 4]
    candidate, suffix = base, 1
    while database.get_user_by_username(conn, candidate) is not None or (
        database.pending_username_taken(conn, candidate, email)
    ):
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def google_sign_in(conn: sqlite3.Connection, identity: GoogleIdentity) -> User:
    """Sign in with a verified Google identity, creating the account if needed.

    No e-mail code is involved: `google_identity.verify_credential` has already
    checked Google's signature, that the token was issued for this app, and
    that Google verified the address. An e-mailed code would prove the same
    thing a second time.

    Returns:
        The existing account — matched by Google account id, or by a verified
        e-mail equal to Google's (which then gets linked) — or a new one with
        `SELF_REGISTRATION_ROLE` and a username derived from the e-mail.
    """
    user_id = database.get_user_id_by_google_sub(conn, identity.sub)
    if user_id is None:
        user_id = database.get_user_id_by_email(conn, identity.email)
        if user_id is not None:
            database.link_google_account(conn, user_id, identity.sub)
    if user_id is not None:
        user = database.get_user_by_id(conn, user_id)
        assert user is not None  # user_emails rows are only written for real users
        return user

    username = _username_from_email(conn, identity.email)
    created_at = _now().isoformat()
    # Google accounts sign in through Google; this password exists only because
    # users.password_hash is NOT NULL, and nobody ever learns it.
    unusable = hash_password(secrets.token_urlsafe(32))
    new_id = database.insert_user(conn, username, unusable, SELF_REGISTRATION_ROLE, created_at)
    database.insert_user_email(conn, new_id, identity.email, identity.sub, created_at)
    # A half-finished e-mail sign-up for the same address is now moot.
    database.delete_pending_signup(conn, identity.email)
    logger.info("created Google user %s", username)
    return User(id=new_id, username=username, role=SELF_REGISTRATION_ROLE, created_at=created_at)

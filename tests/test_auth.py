"""Tests for accounts, password hashing, sessions and the role model."""

import sqlite3
import time

import pytest

from src.customsiq import auth, database
from src.customsiq.config import Settings, settings
from src.customsiq.database import get_connection
from src.customsiq.exceptions import AuthenticationError, InvalidQueryError

PASSWORD = "correct-horse-battery"


@pytest.fixture
def conn() -> sqlite3.Connection:
    """An in-memory database, like the other modules' tests."""
    return get_connection(":memory:")


class TestPasswordStorage:
    """A password must never be recoverable from what we store."""

    def test_stored_value_contains_neither_the_password_nor_a_bare_digest(self) -> None:
        """The hash is salted and labelled, not the password and not sha256(password)."""
        import hashlib

        encoded = auth.hash_password(PASSWORD, iterations=1000)
        assert PASSWORD not in encoded
        assert hashlib.sha256(PASSWORD.encode()).hexdigest() not in encoded
        assert encoded.startswith("pbkdf2_sha256$1000$")
        assert len(encoded.split("$")) == 4

    def test_the_same_password_hashes_differently_every_time(self) -> None:
        """A fresh random salt per hash — so equal passwords aren't visibly equal."""
        assert auth.hash_password(PASSWORD, 1000) != auth.hash_password(PASSWORD, 1000)

    def test_verify_accepts_the_right_password_and_rejects_others(self) -> None:
        encoded = auth.hash_password(PASSWORD, 1000)
        assert auth.verify_password(PASSWORD, encoded)
        assert not auth.verify_password("wrong", encoded)
        assert not auth.verify_password(PASSWORD.upper(), encoded)

    def test_a_malformed_stored_hash_fails_closed(self) -> None:
        """Corrupt rows must deny, not raise, on the login path."""
        assert not auth.verify_password(PASSWORD, "not-a-hash")
        assert not auth.verify_password(PASSWORD, "bcrypt$12$salt$digest")

    def test_the_work_factor_travels_with_the_hash(self) -> None:
        """An old hash still verifies after the default is raised."""
        old = auth.hash_password(PASSWORD, iterations=1000)
        assert auth.verify_password(PASSWORD, old)

    def test_production_default_is_the_owasp_figure_and_works_at_full_cost(self) -> None:
        """The suite lowers iterations; this proves the real setting is usable.

        Reads the default off a fresh Settings rather than the (test-lowered)
        singleton, then actually hashes at that cost once.
        """
        assert Settings().password_iterations == 600_000
        encoded = auth.hash_password(PASSWORD, iterations=600_000)
        assert auth.verify_password(PASSWORD, encoded)

    def test_the_database_never_sees_a_plaintext_password(self, conn: sqlite3.Connection) -> None:
        """Inspect the stored column itself, not just the API around it."""
        auth.create_user(conn, "alice", PASSWORD, auth.ANALYST)
        stored = database.get_password_hash(conn, "alice")
        assert stored is not None
        assert PASSWORD not in stored
        assert auth.verify_password(PASSWORD, stored)

    def test_the_user_record_carries_no_password_hash(self, conn: sqlite3.Connection) -> None:
        """So a hash can't leak by being serialized into a response."""
        user = auth.create_user(conn, "alice", PASSWORD, auth.ANALYST)
        assert not hasattr(user, "password_hash")
        assert PASSWORD not in repr(user)


class TestRegistration:
    """Creating accounts, and refusing to create bad ones."""

    def test_creates_a_user_with_the_requested_role(self, conn: sqlite3.Connection) -> None:
        user = auth.create_user(conn, "alice", PASSWORD, auth.COMPLIANCE_OFFICER)
        assert user.username == "alice"
        assert user.role == auth.COMPLIANCE_OFFICER
        assert isinstance(user.id, int)

    def test_usernames_are_case_folded(self, conn: sqlite3.Connection) -> None:
        """So "Alice" and "alice" are one account, not two look-alikes."""
        auth.create_user(conn, "Alice", PASSWORD)
        assert database.get_user_by_username(conn, "alice") is not None
        with pytest.raises(InvalidQueryError, match="already taken"):
            auth.create_user(conn, "ALICE", PASSWORD)

    def test_self_registration_defaults_to_the_documented_role(
        self, conn: sqlite3.Connection
    ) -> None:
        assert auth.create_user(conn, "alice", PASSWORD).role == auth.SELF_REGISTRATION_ROLE

    @pytest.mark.parametrize("username", ["", "   ", "a" * 33, "alice smith", "alice;drop"])
    def test_rejects_unusable_usernames(self, conn: sqlite3.Connection, username: str) -> None:
        with pytest.raises(InvalidQueryError, match="username"):
            auth.create_user(conn, username, PASSWORD)

    def test_rejects_a_short_password(self, conn: sqlite3.Connection) -> None:
        with pytest.raises(InvalidQueryError, match="password"):
            auth.create_user(conn, "alice", "short")

    def test_rejects_an_unknown_role(self, conn: sqlite3.Connection) -> None:
        with pytest.raises(InvalidQueryError, match="role"):
            auth.create_user(conn, "alice", PASSWORD, "superuser")


class TestAuthentication:
    """Logging in, and failing to."""

    def test_correct_credentials_return_the_user(self, conn: sqlite3.Connection) -> None:
        auth.create_user(conn, "alice", PASSWORD, auth.ANALYST)
        assert auth.authenticate(conn, "alice", PASSWORD).role == auth.ANALYST

    def test_wrong_password_is_rejected(self, conn: sqlite3.Connection) -> None:
        auth.create_user(conn, "alice", PASSWORD)
        with pytest.raises(AuthenticationError):
            auth.authenticate(conn, "alice", "wrong-password")

    def test_unknown_user_gives_the_same_error_as_a_wrong_password(
        self, conn: sqlite3.Connection
    ) -> None:
        """The message must not reveal which usernames exist."""
        auth.create_user(conn, "alice", PASSWORD)
        with pytest.raises(AuthenticationError) as wrong_password:
            auth.authenticate(conn, "alice", "wrong-password")
        with pytest.raises(AuthenticationError) as unknown_user:
            auth.authenticate(conn, "nobody", PASSWORD)
        assert str(wrong_password.value) == str(unknown_user.value)

    def test_an_unknown_user_still_costs_a_key_derivation(
        self, conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Otherwise a fast rejection would enumerate accounts by timing."""
        calls = []
        real_verify = auth.verify_password

        def counting_verify(password: str, encoded: str) -> bool:
            calls.append(password)
            return real_verify(password, encoded)

        monkeypatch.setattr(auth, "verify_password", counting_verify)
        with pytest.raises(AuthenticationError):
            auth.authenticate(conn, "nobody-at-all", PASSWORD)
        assert calls, "no hash was computed for an unknown username"


class TestSessions:
    """Opaque tokens, stored hashed, revocable."""

    def test_a_session_resolves_back_to_its_user(self, conn: sqlite3.Connection) -> None:
        user = auth.create_user(conn, "alice", PASSWORD, auth.ANALYST)
        token = auth.create_session(conn, user)
        resolved = auth.user_for_token(conn, token)
        assert resolved is not None
        assert resolved.username == "alice"

    def test_the_raw_token_is_never_stored(self, conn: sqlite3.Connection) -> None:
        """A leaked database must not hand over usable sessions."""
        user = auth.create_user(conn, "alice", PASSWORD)
        token = auth.create_session(conn, user)
        stored = conn.execute("SELECT token_hash FROM sessions").fetchall()
        assert [row[0] for row in stored] != [token]
        assert all(token not in row[0] for row in stored)

    @pytest.mark.parametrize("token", [None, "", "not-a-real-token"])
    def test_missing_or_bogus_tokens_resolve_to_nobody(
        self, conn: sqlite3.Connection, token: object
    ) -> None:
        assert auth.user_for_token(conn, token) is None  # type: ignore[arg-type]

    def test_logout_invalidates_the_token_immediately(self, conn: sqlite3.Connection) -> None:
        user = auth.create_user(conn, "alice", PASSWORD)
        token = auth.create_session(conn, user)
        auth.logout(conn, token)
        assert auth.user_for_token(conn, token) is None

    def test_logout_of_an_unknown_token_is_not_an_error(self, conn: sqlite3.Connection) -> None:
        auth.logout(conn, "never-existed")
        auth.logout(conn, None)

    def test_an_expired_session_stops_working(
        self, conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TTL is enforced on read, not by a background job."""
        monkeypatch.setattr(settings, "session_ttl_hours", 0)
        user = auth.create_user(conn, "alice", PASSWORD)
        token = auth.create_session(conn, user)
        time.sleep(0.01)
        assert auth.user_for_token(conn, token) is None

    def test_expired_rows_are_swept_on_the_next_login(
        self, conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = auth.create_user(conn, "alice", PASSWORD)
        monkeypatch.setattr(settings, "session_ttl_hours", 0)
        auth.create_session(conn, user)
        time.sleep(0.01)
        monkeypatch.setattr(settings, "session_ttl_hours", 12)
        auth.create_session(conn, user)
        assert database.count_users(conn) == 1
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


class TestRoleModel:
    """`can()` is the single source of truth the routes ask."""

    @pytest.mark.parametrize(
        ("role", "action", "allowed"),
        [
            # review:classification and review:duty — analyst and up
            (auth.VIEWER, "review:classification", False),
            (auth.ANALYST, "review:classification", True),
            (auth.COMPLIANCE_OFFICER, "review:classification", True),
            (auth.ADMIN, "review:classification", True),
            (auth.VIEWER, "review:duty", False),
            (auth.ANALYST, "review:duty", True),
            (auth.COMPLIANCE_OFFICER, "review:duty", True),
            (auth.ADMIN, "review:duty", True),
            # review:screening — the regulated one, compliance officer and up
            (auth.VIEWER, "review:screening", False),
            (auth.ANALYST, "review:screening", False),
            (auth.COMPLIANCE_OFFICER, "review:screening", True),
            (auth.ADMIN, "review:screening", True),
            # audit:read — any signed-in role
            (auth.VIEWER, "audit:read", True),
            (auth.ANALYST, "audit:read", True),
            (auth.COMPLIANCE_OFFICER, "audit:read", True),
            (auth.ADMIN, "audit:read", True),
            # users:manage — admin only
            (auth.VIEWER, "users:manage", False),
            (auth.ANALYST, "users:manage", False),
            (auth.COMPLIANCE_OFFICER, "users:manage", False),
            (auth.ADMIN, "users:manage", True),
        ],
    )
    def test_permission_matrix(self, role: str, action: str, allowed: bool) -> None:
        """Every role x action cell of the documented matrix."""
        assert auth.can(role, action) is allowed

    def test_an_unknown_role_or_action_denies(self) -> None:
        """A typo must fail closed, never grant."""
        assert not auth.can("superuser", "audit:read")
        assert not auth.can(auth.ADMIN, "review:everything")
        assert not auth.can("", "")

    def test_every_permission_names_a_real_role(self) -> None:
        """Guards against a permission that can never be satisfied."""
        assert set(auth.PERMISSIONS.values()) <= set(auth.ROLE_ORDER)

    def test_every_reviewable_subject_type_has_a_permission(self) -> None:
        """review.py and auth.py must not drift apart."""
        from src.customsiq.review import VALID_SUBJECT_TYPES

        assert {f"review:{s}" for s in VALID_SUBJECT_TYPES} <= set(auth.PERMISSIONS)


class TestDemoAccounts:
    """Seeded only into an empty table, and only when enabled."""

    def test_seeds_one_account_per_role(self, conn: sqlite3.Connection) -> None:
        assert auth.seed_demo_users(conn) == len(auth.DEMO_USERS)
        assert {u.role for u in database.fetch_users(conn)} == set(auth.ROLE_ORDER)

    def test_the_seeded_credentials_actually_work(self, conn: sqlite3.Connection) -> None:
        """The README publishes these; they must be true."""
        auth.seed_demo_users(conn)
        for username, password, role in auth.DEMO_USERS:
            assert auth.authenticate(conn, username, password).role == role

    def test_never_seeds_into_a_database_that_already_has_accounts(
        self, conn: sqlite3.Connection
    ) -> None:
        """A real deployment can't be handed public credentials by a restart."""
        auth.create_user(conn, "alice", PASSWORD)
        assert auth.seed_demo_users(conn) == 0
        assert database.count_users(conn) == 1

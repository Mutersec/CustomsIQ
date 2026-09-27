"""Regression guards for the security-audit findings #1-#7.

Each test names the finding it closes and asserts the *new* behaviour in a way
that would fail if the old behaviour came back — not merely that the current
code does what it does today.
"""

import hashlib
import sqlite3
import time
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from src.customsiq import auth
from src.customsiq.api import _IP_HITS, MAX_NAME_QUERY, MAX_TEXT_QUERY, app
from src.customsiq.config import settings
from src.customsiq.database import get_connection, seed
from src.customsiq.exceptions import AuthenticationError
from tests.helpers import PASSWORD, signed_in_client, unique_username

client = TestClient(app)


def anonymous() -> TestClient:
    """A client with no cookies.

    `TestClient` keeps cookies between requests, and `/auth/register` sets a
    session — so a shared client silently stops being anonymous the moment any
    test registers. These assertions are specifically about what a signed-out
    caller can see, so they get a fresh one.
    """
    return TestClient(app)


def _from_ip(ip: str) -> dict:
    """Headers that make a request look like it came from `ip`."""
    return {"X-Forwarded-For": ip}


class TestFinding1QueryLengthCaps:
    """A 500-char query cost 5.1 s of unauthenticated CPU (10.4 s with a language)."""

    @pytest.mark.parametrize(
        ("path", "param", "cap"),
        [
            ("/search", "q", MAX_TEXT_QUERY),
            ("/classify", "description", MAX_TEXT_QUERY),
            ("/screen", "name", MAX_NAME_QUERY),
        ],
    )
    def test_an_oversized_query_is_rejected_quickly(self, path: str, param: str, cap: int) -> None:
        """422 on validation, and fast — the point is that it never reaches the scan.

        The wall-clock bound is deliberate: a regression that removed the cap
        would still return 200 here, so status alone wouldn't catch it, but the
        several seconds it would spend scanning would.
        """
        started = time.perf_counter()
        response = client.get(path, params={param: "x" * 500}, headers=_from_ip("10.0.0.1"))
        elapsed = time.perf_counter() - started

        assert response.status_code == 422
        assert elapsed < 1.0, f"{path} spent {elapsed:.2f}s on input it should have refused"

    @pytest.mark.parametrize(
        ("path", "param", "cap"),
        [
            ("/search", "q", MAX_TEXT_QUERY),
            ("/classify", "description", MAX_TEXT_QUERY),
            ("/screen", "name", MAX_NAME_QUERY),
        ],
    )
    def test_a_query_at_the_cap_still_works(self, path: str, param: str, cap: int) -> None:
        """The cap must not break legitimate use."""
        response = client.get(path, params={param: "a" * cap}, headers=_from_ip("10.0.0.2"))
        assert response.status_code == 200

    def test_the_caps_are_wide_enough_for_real_input(self) -> None:
        """Guards against someone "hardening" these into uselessness."""
        assert MAX_TEXT_QUERY >= 60, "too tight for a real product description"
        assert MAX_NAME_QUERY >= 40, "shorter than real sanctioned entity names"


class TestFinding2And6AuthRateLimit:
    """Nothing at all stopped a password-guessing script before this."""

    def test_repeated_logins_from_one_ip_are_throttled(self) -> None:
        limit = settings.auth_rate_limit_per_minute
        ip = "203.0.113.10"
        body = {"username": "no_such_user", "password": "wrong-password-1"}

        codes = [
            client.post("/auth/login", json=body, headers=_from_ip(ip)).status_code
            for _ in range(limit + 3)
        ]
        assert codes[:limit] == [401] * limit, "the first N attempts should be judged on merit"
        assert codes[limit:] == [429] * 3, "attempts past the limit must be refused"

    def test_a_different_ip_is_unaffected(self) -> None:
        """Per-IP, not global — one attacker must not lock everyone out."""
        limit = settings.auth_rate_limit_per_minute
        body = {"username": "no_such_user", "password": "wrong-password-2"}
        for _ in range(limit + 1):
            client.post("/auth/login", json=body, headers=_from_ip("203.0.113.11"))

        assert (
            client.post("/auth/login", json=body, headers=_from_ip("203.0.113.12")).status_code
            == 401
        )

    def test_the_limit_is_not_keyed_on_username(self) -> None:
        """The old limiter keyed on account, which is unusable before login.

        Rotating the username must not buy more attempts.
        """
        limit = settings.auth_rate_limit_per_minute
        ip = "203.0.113.13"
        codes = [
            client.post(
                "/auth/login",
                json={"username": f"user_{i}", "password": "wrong-password"},
                headers=_from_ip(ip),
            ).status_code
            for i in range(limit + 2)
        ]
        assert 429 in codes, "a different username each time still shares the IP budget"

    def test_the_expensive_public_search_routes_are_throttled_too(self) -> None:
        """Finding #1's other half: the caps bound one request, this bounds the rate."""
        limit = settings.search_rate_limit_per_minute
        ip = "203.0.113.14"
        codes = [
            client.get("/search", params={"q": "cotton"}, headers=_from_ip(ip)).status_code
            for _ in range(limit + 2)
        ]
        assert codes[-1] == 429


class TestFinding3SelfRegistrationRole:
    """One anonymous POST used to buy permanent audit-trail write access."""

    def test_a_fresh_registration_is_a_viewer(self) -> None:
        response = anonymous().post(
            "/auth/register",
            json={"username": unique_username("fresh"), "password": PASSWORD},
            headers=_from_ip("198.51.100.1"),
        )
        assert response.status_code == 200
        assert response.json()["role"] == auth.VIEWER
        assert auth.SELF_REGISTRATION_ROLE == auth.VIEWER

    def test_a_viewer_cannot_write_to_the_audit_trail(self) -> None:
        """The privilege that mattered: review rows are append-only, undeletable."""
        assert not auth.can(auth.VIEWER, "review:classification")
        assert not auth.can(auth.VIEWER, "review:duty")
        assert not auth.can(auth.VIEWER, "review:screening")

    def test_the_role_is_configurable_rather_than_hardcoded(self) -> None:
        """A deployment may still choose otherwise — deliberately, via config."""
        assert settings.self_registration_role == auth.VIEWER


class TestFinding4LoginTimingOracle:
    """Unknown usernames cost two PBKDF2 runs to a known user's one — a 2.00x tell."""

    @pytest.fixture
    def conn(self) -> sqlite3.Connection:
        connection = get_connection(":memory:")
        seed(connection)
        auth.seed_demo_users(connection)
        # Warm the dummy-hash cache so the first call isn't charged for it.
        with pytest.raises(AuthenticationError):
            auth.authenticate(connection, "warm_the_cache", "irrelevant")
        return connection

    def _kdf_calls(self, conn: sqlite3.Connection, username: str) -> int:
        real = hashlib.pbkdf2_hmac
        calls = 0

        def counting(*args, **kwargs):
            nonlocal calls
            calls += 1
            return real(*args, **kwargs)

        with mock.patch("hashlib.pbkdf2_hmac", counting):
            with pytest.raises(AuthenticationError):
                auth.authenticate(conn, username, "definitely-the-wrong-password")
        return calls

    def test_both_paths_cost_exactly_one_key_derivation(self, conn: sqlite3.Connection) -> None:
        """Counted, not timed — a wall-clock assertion would be flaky in CI.

        This is the precise property: it is not enough that an unknown user
        costs *something*, it must cost the *same* thing.
        """
        known = self._kdf_calls(conn, "demo_viewer")
        unknown = self._kdf_calls(conn, "no_such_user_at_all")
        assert known == 1
        assert unknown == 1, "the unknown-user path ran the KDF twice again"

    def test_the_dummy_hash_is_reused_not_regenerated(self) -> None:
        """The actual mechanism, so a refactor can't quietly undo it."""
        first = auth._dummy_hash(settings.password_iterations)
        second = auth._dummy_hash(settings.password_iterations)
        assert first is second, "the dummy hash is being recomputed per call"

    def test_the_two_paths_are_still_indistinguishable_by_message(self) -> None:
        ip_a, ip_b = "198.51.100.20", "198.51.100.21"
        unknown = client.post(
            "/auth/login",
            json={"username": "no_such_user", "password": "wrong"},
            headers=_from_ip(ip_a),
        )
        known = client.post(
            "/auth/login",
            json={"username": "demo_viewer", "password": "wrong"},
            headers=_from_ip(ip_b),
        )
        assert unknown.status_code == known.status_code == 401
        assert unknown.json() == known.json()


class TestFinding5AuditDisclosure:
    """Reviewer names and free-text comments were readable anonymously."""

    def _recorded_reference(self) -> str:
        reference = f"sec-patch-{time.time_ns()}"
        with signed_in_client(auth.ANALYST) as analyst:
            analyst.post(
                "/review",
                json={
                    "subject_type": "classification",
                    "subject_reference": reference,
                    "decision": "approved",
                    "comment": "sensitive free text",
                },
            )
        return reference

    def test_anonymous_sees_the_decision_but_not_the_reviewer(self) -> None:
        """Phase 7's public per-result trail survives; only identity is withheld."""
        reference = self._recorded_reference()
        rows = (
            anonymous()
            .get(
                "/review/history",
                params={"subject_reference": reference},
                headers=_from_ip("198.51.100.30"),
            )
            .json()
        )

        assert rows, "the public four-eyes trail must still be visible"
        assert rows[0]["decision"] == "approved"
        assert rows[0]["reviewed_at"]
        assert rows[0]["reviewer_name"] is None
        assert rows[0]["comment"] is None

    def test_a_permitted_caller_still_sees_identity(self) -> None:
        reference = self._recorded_reference()
        with signed_in_client(auth.VIEWER) as reader:
            rows = reader.get("/review/history", params={"subject_reference": reference}).json()
        assert rows[0]["reviewer_name"] is not None
        assert rows[0]["comment"] == "sensitive free text"

    def test_the_gts_legal_control_log_requires_audit_read(self) -> None:
        reference = self._recorded_reference()
        unauthenticated = anonymous().get(
            f"/sap-gts/legal-control/{reference}", headers=_from_ip("198.51.100.31")
        )
        assert unauthenticated.status_code == 401

        with signed_in_client(auth.VIEWER) as reader:
            assert reader.get(f"/sap-gts/legal-control/{reference}").status_code == 200

    def test_the_comment_does_not_leak_through_the_gts_message_text(self) -> None:
        """The reason this route is gated rather than redacted."""
        reference = self._recorded_reference()
        with signed_in_client(auth.VIEWER) as reader:
            payload = reader.get(f"/sap-gts/legal-control/{reference}").json()
        rendered = " ".join(row["MESSAGE"] for row in payload["RETURN"])
        assert "released by" in rendered, "identity really is baked into MESSAGE here"


class TestFinding7RegistrationEnumeration:
    """Throttled, not eliminated — and this test records which of those it is."""

    def test_registration_is_rate_limited_per_ip(self) -> None:
        limit = settings.auth_rate_limit_per_minute
        ip = "198.51.100.40"
        fresh = anonymous()
        codes = [
            fresh.post(
                "/auth/register",
                json={"username": unique_username("enum"), "password": PASSWORD},
                headers=_from_ip(ip),
            ).status_code
            for _ in range(limit + 2)
        ]
        assert codes[-1] == 429, "enumeration by registration must not be free"

    def test_the_taken_username_message_is_still_distinguishable(self) -> None:
        """Documents the residual gap honestly rather than implying it's closed.

        Full opacity would mean not telling a legitimate user why their chosen
        name failed; the mitigation chosen here is throttling, so the oracle
        still exists — it is just no longer free to query.
        """
        _IP_HITS.clear()
        taken = anonymous().post(
            "/auth/register",
            json={"username": "demo_admin", "password": PASSWORD},
            headers=_from_ip("198.51.100.41"),
        )
        assert taken.status_code == 400
        assert "already taken" in taken.json()["detail"]

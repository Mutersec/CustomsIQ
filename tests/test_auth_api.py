"""Tests for the auth endpoints and for RBAC enforcement on every gated route.

One test per non-trivial cell of the README's permission matrix, asserting 401
(not signed in) and 403 (signed in, wrong role) separately — a client needs to
tell "log in" from "you can't do that", so the two must not be interchangeable.

Like tests/test_api.py these run against the app's shared connection, so every
account and subject reference is uuid-unique rather than isolated.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from src.customsiq import auth
from src.customsiq.api import SESSION_COOKIE, _conn, app
from tests.helpers import PASSWORD, create_test_user, signed_in_client, unique_username

#: Stays anonymous for the whole module: never used to register or sign in,
#: because TestClient keeps cookies and one stray login would silently
#: authenticate every "anonymous" assertion below.
client = TestClient(app)


def _ref() -> str:
    """A subject reference no other test will touch."""
    return f"test-ref-{uuid.uuid4()}"


class TestRegistration:
    """POST /auth/register."""

    def test_creates_an_account_and_signs_it_in(self) -> None:
        with TestClient(app) as fresh:
            username = unique_username("newbie")
            response = fresh.post(
                "/auth/register", json={"username": username, "password": PASSWORD}
            )
            assert response.status_code == 200
            assert response.json() == {
                "username": username,
                "role": auth.SELF_REGISTRATION_ROLE,
                "created_at": response.json()["created_at"],
            }
            assert fresh.get("/auth/me").json()["user"]["username"] == username

    def test_the_session_cookie_is_httponly(self) -> None:
        """So script on the page can never read it — this is why it isn't a JWT in JS."""
        with TestClient(app) as fresh:
            response = fresh.post(
                "/auth/register",
                json={"username": unique_username("cookie"), "password": PASSWORD},
            )
            cookie_header = response.headers["set-cookie"]
            assert SESSION_COOKIE in cookie_header
            assert "HttpOnly" in cookie_header
            assert "SameSite=lax" in cookie_header.replace("samesite", "SameSite")

    def test_a_duplicate_username_is_refused(self) -> None:
        username = unique_username("dup")
        with TestClient(app) as first:
            first.post("/auth/register", json={"username": username, "password": PASSWORD})
        with TestClient(app) as second:
            response = second.post(
                "/auth/register", json={"username": username, "password": PASSWORD}
            )
        assert response.status_code == 400
        assert "already taken" in response.json()["detail"]

    @pytest.mark.parametrize("password", ["", "short"])
    def test_a_weak_password_is_refused(self, password: str) -> None:
        response = client.post(
            "/auth/register", json={"username": unique_username("weak"), "password": password}
        )
        assert response.status_code == 400
        assert "password" in response.json()["detail"]

    def test_registration_never_grants_a_role_the_client_asks_for(self) -> None:
        """An extra field must not be a privilege-escalation path."""
        username = unique_username("sneaky")
        with TestClient(app) as fresh:
            response = fresh.post(
                "/auth/register",
                json={"username": username, "password": PASSWORD, "role": "admin"},
            )
        assert response.status_code == 200
        assert response.json()["role"] == auth.SELF_REGISTRATION_ROLE


class TestLoginLogout:
    """POST /auth/login, /auth/logout, GET /auth/me."""

    def test_login_succeeds_with_the_right_password(self) -> None:
        user = create_test_user(_conn, auth.VIEWER)
        with TestClient(app) as fresh:
            response = fresh.post(
                "/auth/login", json={"username": user.username, "password": PASSWORD}
            )
            assert response.status_code == 200
            assert response.json()["role"] == auth.VIEWER

    def test_login_fails_with_a_wrong_password(self) -> None:
        user = create_test_user(_conn, auth.VIEWER)
        response = client.post(
            "/auth/login", json={"username": user.username, "password": "not-the-password"}
        )
        assert response.status_code == 401

    def test_login_fails_for_an_unknown_user_with_the_same_message(self) -> None:
        user = create_test_user(_conn, auth.VIEWER)
        wrong_password = client.post(
            "/auth/login", json={"username": user.username, "password": "nope-nope-nope"}
        )
        unknown_user = client.post(
            "/auth/login", json={"username": unique_username("ghost"), "password": PASSWORD}
        )
        assert wrong_password.status_code == unknown_user.status_code == 401
        assert wrong_password.json()["detail"] == unknown_user.json()["detail"]

    def test_me_is_200_with_a_null_user_when_anonymous(self) -> None:
        """Not a 401: the frontend calls this for visitors who never sign in."""
        response = client.get("/auth/me")
        assert response.status_code == 200
        assert response.json() == {"user": None}

    def test_logout_ends_the_session(self) -> None:
        with signed_in_client(auth.ANALYST) as signed_in:
            assert signed_in.get("/auth/me").json()["user"] is not None
            assert signed_in.post("/auth/logout").json() == {"signed_out": True}
            assert signed_in.get("/auth/me").json()["user"] is None
            # and the token is dead server-side, not just dropped by the client
            assert signed_in.get("/review/history").status_code == 401

    def test_logout_while_anonymous_is_harmless(self) -> None:
        assert client.post("/auth/logout").status_code == 200


class TestPublicEndpointsStayPublic:
    """The demo's whole pitch: no account needed to try the compute endpoints."""

    @pytest.mark.parametrize(
        ("path", "params"),
        [
            ("/health", {}),
            ("/search", {"q": "cotton"}),
            ("/classify", {"description": "cotton t-shirt"}),
            ("/screen", {"name": "Northwind Maritime"}),
            (
                "/calculate-duty",
                {"hs_code": "6109100000", "country_of_origin": "NO", "customs_value": 1000},
            ),
            (
                "/assess-risk",
                {
                    "country_of_origin": "NO",
                    "party_name": "Northwind Maritime",
                    "customs_value": 1000,
                    "description": "cotton t-shirt",
                },
            ),
            ("/codes/6109100000/history", {}),
            ("/dashboard/stats", {}),
        ],
    )
    def test_anonymous_access_is_allowed(self, path: str, params: dict) -> None:
        assert client.get(path, params=params).status_code == 200


class TestReviewWriteRequiresTheRightRole:
    """POST /review — 401 anonymous, 403 under-ranked, 200 otherwise."""

    def test_anonymous_submission_is_401(self) -> None:
        response = client.post(
            "/review",
            json={"subject_type": "duty", "subject_reference": _ref(), "decision": "approved"},
        )
        assert response.status_code == 401

    @pytest.mark.parametrize("subject_type", ["classification", "duty"])
    def test_viewer_cannot_review_anything(self, subject_type: str) -> None:
        with signed_in_client(auth.VIEWER) as viewer:
            response = viewer.post(
                "/review",
                json={
                    "subject_type": subject_type,
                    "subject_reference": _ref(),
                    "decision": "approved",
                },
            )
        assert response.status_code == 403
        assert "viewer" in response.json()["detail"]

    @pytest.mark.parametrize("subject_type", ["classification", "duty"])
    def test_analyst_may_review_classification_and_duty(self, subject_type: str) -> None:
        with signed_in_client(auth.ANALYST) as analyst:
            response = analyst.post(
                "/review",
                json={
                    "subject_type": subject_type,
                    "subject_reference": _ref(),
                    "decision": "approved",
                },
            )
        assert response.status_code == 200

    def test_analyst_may_not_sign_off_a_screening(self) -> None:
        """Sanctions screening is the regulated decision — officer and up."""
        with signed_in_client(auth.ANALYST) as analyst:
            response = analyst.post(
                "/review",
                json={
                    "subject_type": "screening",
                    "subject_reference": _ref(),
                    "decision": "approved",
                },
            )
        assert response.status_code == 403

    @pytest.mark.parametrize("role", [auth.COMPLIANCE_OFFICER, auth.ADMIN])
    def test_officer_and_admin_may_sign_off_a_screening(self, role: str) -> None:
        with signed_in_client(role) as reviewer:
            response = reviewer.post(
                "/review",
                json={
                    "subject_type": "screening",
                    "subject_reference": _ref(),
                    "decision": "approved",
                },
            )
        assert response.status_code == 200

    def test_an_unknown_subject_type_is_400_not_403(self) -> None:
        """A typo is a bad request, not a permission problem."""
        with signed_in_client(auth.ADMIN) as admin:
            response = admin.post(
                "/review",
                json={
                    "subject_type": "vibes",
                    "subject_reference": _ref(),
                    "decision": "approved",
                },
            )
        assert response.status_code == 400
        assert "subject_type" in response.json()["detail"]

    def test_a_promotion_takes_effect_on_the_next_request(self) -> None:
        """Sessions are revocable state, not a token frozen at login time."""
        user = create_test_user(_conn, auth.ANALYST)
        with TestClient(app) as analyst:
            analyst.post("/auth/login", json={"username": user.username, "password": PASSWORD})
            body = {
                "subject_type": "screening",
                "subject_reference": _ref(),
                "decision": "approved",
            }
            assert analyst.post("/review", json=body).status_code == 403

            with signed_in_client(auth.ADMIN) as admin:
                promoted = admin.post(
                    f"/auth/users/{user.username}/role",
                    json={"role": auth.COMPLIANCE_OFFICER},
                )
                assert promoted.status_code == 200

            assert analyst.post("/review", json=body).status_code == 200


class TestReviewerNameComesFromTheSession:
    """The audit trail names the account, not whatever the client sent."""

    def test_the_stored_name_is_the_signed_in_user(self) -> None:
        reference = _ref()
        with signed_in_client(auth.ANALYST) as analyst:
            username = analyst.get("/auth/me").json()["user"]["username"]
            response = analyst.post(
                "/review",
                json={
                    "subject_type": "duty",
                    "subject_reference": reference,
                    "decision": "approved",
                },
            )
        assert response.json()["reviewer_name"] == username
        assert response.json()["authenticated"] is True

    def test_a_client_supplied_reviewer_name_is_ignored(self) -> None:
        """The field is gone from the model; sending it must change nothing."""
        with signed_in_client(auth.ANALYST) as analyst:
            username = analyst.get("/auth/me").json()["user"]["username"]
            response = analyst.post(
                "/review",
                json={
                    "subject_type": "duty",
                    "subject_reference": _ref(),
                    "decision": "approved",
                    "reviewer_name": "someone-else",
                },
            )
        assert response.json()["reviewer_name"] == username

    def test_a_free_text_row_stays_unauthenticated_and_is_never_claimed(self) -> None:
        """A legacy name must not be absorbed by a later registration of it.

        Writes a CLI-style row (no user id), then registers that exact username
        and confirms the historical row is still reported as unauthenticated.
        """
        from src.customsiq import review

        legacy_name = unique_username("legacy")
        reference = _ref()
        review.submit_review(_conn, "duty", reference, "approved", legacy_name, "typed by hand")

        rows = client.get("/review/history", params={"subject_reference": reference}).json()
        assert [r["reviewer_name"] for r in rows] == [legacy_name]
        assert rows[0]["authenticated"] is False

        auth.create_user(_conn, legacy_name, PASSWORD, auth.ANALYST)
        rows = client.get("/review/history", params={"subject_reference": reference}).json()
        assert rows[0]["authenticated"] is False, "a legacy row was claimed by name"


class TestAuditReads:
    """The full log needs an account; one result's own trail does not."""

    def test_the_full_log_is_401_when_anonymous(self) -> None:
        assert client.get("/review/history").status_code == 401

    def test_one_subjects_trail_stays_public(self) -> None:
        reference = _ref()
        with signed_in_client(auth.ANALYST) as analyst:
            analyst.post(
                "/review",
                json={
                    "subject_type": "duty",
                    "subject_reference": reference,
                    "decision": "approved",
                },
            )
        response = client.get("/review/history", params={"subject_reference": reference})
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_a_viewer_may_read_the_full_log(self) -> None:
        """This is what makes 'viewer' a real role rather than a decoration."""
        with signed_in_client(auth.VIEWER) as viewer:
            assert viewer.get("/review/history").status_code == 200

    def test_dashboard_hides_reviewer_identities_from_anonymous_callers(self) -> None:
        stats = client.get("/dashboard/stats").json()
        assert stats["recent_reviews"] == []
        assert stats["recent_reviews_restricted"] is True
        assert stats["hs_code_count"] > 0  # the counts themselves stay public

    def test_dashboard_shows_reviewer_identities_to_a_signed_in_user(self) -> None:
        with signed_in_client(auth.VIEWER) as viewer:
            stats = viewer.get("/dashboard/stats").json()
        assert stats["recent_reviews_restricted"] is False
        if stats["review_total"]:
            assert stats["recent_reviews"]


class TestUserAdministration:
    """/auth/users and role changes — admin only."""

    def test_anonymous_listing_is_401(self) -> None:
        assert client.get("/auth/users").status_code == 401

    @pytest.mark.parametrize("role", [auth.VIEWER, auth.ANALYST, auth.COMPLIANCE_OFFICER])
    def test_non_admins_get_403(self, role: str) -> None:
        with signed_in_client(role) as user:
            assert user.get("/auth/users").status_code == 403

    def test_an_admin_can_list_users(self) -> None:
        with signed_in_client(auth.ADMIN) as admin:
            response = admin.get("/auth/users")
        assert response.status_code == 200
        assert all("password" not in row for row in response.json())

    def test_an_admin_can_change_a_role(self) -> None:
        user = create_test_user(_conn, auth.VIEWER)
        with signed_in_client(auth.ADMIN) as admin:
            response = admin.post(f"/auth/users/{user.username}/role", json={"role": "admin"})
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    def test_an_unknown_role_is_rejected(self) -> None:
        user = create_test_user(_conn, auth.VIEWER)
        with signed_in_client(auth.ADMIN) as admin:
            response = admin.post(f"/auth/users/{user.username}/role", json={"role": "superuser"})
        assert response.status_code == 400

    def test_an_unknown_user_is_404(self) -> None:
        with signed_in_client(auth.ADMIN) as admin:
            response = admin.post("/auth/users/nobody-here/role", json={"role": "viewer"})
        assert response.status_code == 404


class TestConcurrentRequests:
    """Regression guard for the crash RBAC surfaced.

    The app shares one SQLite connection across FastAPI's threadpool. This
    machine's SQLite is built THREADSAFE=2 (one connection per thread) and
    Python reports sqlite3.threadsafety == 1, so unserialized sharing corrupts
    reads and then segfaults — which is exactly what happened once a session
    lookup landed on every request. database._SerializedConnection is the fix;
    without it this test fails or takes the interpreter down with it.
    """

    def test_parallel_requests_do_not_corrupt_reads(self) -> None:
        from concurrent.futures import ThreadPoolExecutor

        user = create_test_user(_conn, auth.COMPLIANCE_OFFICER)
        with TestClient(app) as signed_in:
            signed_in.post("/auth/login", json={"username": user.username, "password": PASSWORD})

            def one_round(index: int) -> tuple:
                me = signed_in.get("/auth/me")
                review = signed_in.post(
                    "/review",
                    json={
                        "subject_type": "screening",
                        "subject_reference": f"{_ref()}-{index}",
                        "decision": "approved",
                    },
                )
                stats = signed_in.get("/dashboard/stats")
                return me.json()["user"]["username"], review.status_code, stats.status_code

            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(one_round, range(24)))

        assert all(name == user.username for name, _, _ in results)
        assert all(status == 200 for _, status, _ in results)
        assert all(status == 200 for _, _, status in results)

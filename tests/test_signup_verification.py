"""Sign-in gate, e-mail-verified sign-up, Google sign-in, and the mailer.

The `outbox` fixture (tests/conftest.py) captures every verification e-mail
the mailer would have sent through Brevo.
"""

import logging
import sqlite3
import urllib.error

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.customsiq import auth, google_identity, mailer
from src.customsiq.api import _is_public, app
from src.customsiq.config import settings
from src.customsiq.database import get_connection, get_pending_signup
from src.customsiq.exceptions import (
    AuthenticationError,
    InvalidQueryError,
    VerificationCooldownError,
)
from src.customsiq.google_identity import GoogleIdentity
from tests.helpers import PASSWORD, code_sent_to, unique_email, unique_username

CLIENT_ID = "test-client.apps.googleusercontent.com"


@pytest.fixture
def conn() -> sqlite3.Connection:
    return get_connection(":memory:")


def _start(conn: sqlite3.Connection, email: str = "ada@example.com") -> str:
    return auth.start_signup(conn, "ada", email, PASSWORD)


class TestCodeRules:
    def test_nothing_exists_until_the_code_is_confirmed(
        self, conn: sqlite3.Connection, outbox: list
    ) -> None:
        email = _start(conn)
        assert auth.database.get_user_by_username(conn, "ada") is None
        user = auth.confirm_signup(conn, email, code_sent_to(outbox, email))
        assert user.username == "ada"
        assert user.role == auth.SELF_REGISTRATION_ROLE
        assert get_pending_signup(conn, email) is None
        assert auth.database.get_email_for_user(conn, user.id) == email

    def test_the_code_is_six_digits_and_never_stored_in_clear(
        self, conn: sqlite3.Connection, outbox: list
    ) -> None:
        email = _start(conn)
        code = code_sent_to(outbox, email)
        assert len(code) == 6 and code.isdigit()
        row = conn.execute("SELECT * FROM pending_signups").fetchone()
        assert code not in " ".join(str(value) for value in row)

    def test_a_wrong_code_counts_an_attempt(self, conn: sqlite3.Connection, outbox: list) -> None:
        email = _start(conn)
        wrong = "000000" if code_sent_to(outbox, email) != "000000" else "111111"
        with pytest.raises(AuthenticationError, match="not correct"):
            auth.confirm_signup(conn, email, wrong)
        assert get_pending_signup(conn, email).attempts == 1

    def test_attempts_run_out_and_kill_the_signup(
        self, conn: sqlite3.Connection, outbox: list
    ) -> None:
        email = _start(conn)
        code = code_sent_to(outbox, email)
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(settings.verification_max_attempts - 1):
            with pytest.raises(AuthenticationError, match="not correct"):
                auth.confirm_signup(conn, email, wrong)
        with pytest.raises(AuthenticationError, match="too many"):
            auth.confirm_signup(conn, email, wrong)
        with pytest.raises(AuthenticationError, match="expired"):
            auth.confirm_signup(conn, email, code)  # even the right code is dead now

    def test_an_expired_code_is_refused(
        self, conn: sqlite3.Connection, outbox: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "verification_code_ttl_minutes", 0)
        email = _start(conn)
        with pytest.raises(AuthenticationError, match="expired"):
            auth.confirm_signup(conn, email, code_sent_to(outbox, email))

    def test_a_new_code_cannot_be_requested_immediately(
        self, conn: sqlite3.Connection, outbox: list
    ) -> None:
        email = _start(conn)
        with pytest.raises(VerificationCooldownError) as raised:
            auth.resend_code(conn, email)
        assert 0 < raised.value.retry_after <= settings.verification_resend_seconds
        with pytest.raises(VerificationCooldownError):
            _start(conn, email)

    def test_resend_replaces_the_code_but_keeps_the_attempt_count(
        self, conn: sqlite3.Connection, outbox: list, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "verification_resend_seconds", 0)
        email = _start(conn)
        first = code_sent_to(outbox, email)
        with pytest.raises(AuthenticationError):
            auth.confirm_signup(conn, email, "000000" if first != "000000" else "111111")
        auth.resend_code(conn, email)
        assert len(outbox) == 2
        assert get_pending_signup(conn, email).attempts == 1
        assert auth.confirm_signup(conn, email, code_sent_to(outbox, email)).username == "ada"

    @pytest.mark.parametrize("email", ["", "no-at-sign", "a@b", "two@@example.com"])
    def test_an_invalid_email_is_refused(self, conn: sqlite3.Connection, email: str) -> None:
        with pytest.raises(InvalidQueryError, match="e-mail"):
            auth.start_signup(conn, "ada", email, PASSWORD)

    def test_an_email_can_only_have_one_account(
        self, conn: sqlite3.Connection, outbox: list
    ) -> None:
        email = _start(conn)
        auth.confirm_signup(conn, email, code_sent_to(outbox, email))
        with pytest.raises(InvalidQueryError, match="already exists"):
            auth.start_signup(conn, "someone-else", email.upper(), PASSWORD)

    def test_a_username_held_by_a_pending_signup_is_taken(
        self, conn: sqlite3.Connection, outbox: list
    ) -> None:
        _start(conn)
        with pytest.raises(InvalidQueryError, match="already taken"):
            auth.start_signup(conn, "ada", "other@example.com", PASSWORD)

    def test_signing_in_by_email_works_once_verified(
        self, conn: sqlite3.Connection, outbox: list
    ) -> None:
        email = _start(conn)
        auth.confirm_signup(conn, email, code_sent_to(outbox, email))
        assert auth.authenticate(conn, "ADA@example.com", PASSWORD).username == "ada"
        with pytest.raises(AuthenticationError):
            auth.authenticate(conn, "nobody@example.com", PASSWORD)


class TestMailer:
    def test_the_brevo_payload(self, outbox: list, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict = {}
        monkeypatch.setattr(
            mailer, "transport", lambda url, headers, payload: seen.update(url=url, h=headers)
        )
        mailer.send_verification_code("ada@example.com", "123456", "en")
        assert seen["url"] == "https://api.brevo.com/v3/smtp/email"
        assert seen["h"]["api-key"] == "test-key"

    @pytest.mark.parametrize(
        ("language", "word"), [("en", "verification"), ("tr", "doğrulama"), ("de", "Bestätigung")]
    )
    def test_each_language_gets_its_own_text(self, outbox: list, language: str, word: str) -> None:
        mailer.send_verification_code("ada@example.com", "123456", language)
        assert word in outbox[-1]["subject"]
        assert "123456" in outbox[-1]["textContent"]
        assert outbox[-1]["sender"]["email"] == settings.mail_from

    def test_no_key_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "brevo_api_key", None)
        with pytest.raises(mailer.MailNotConfiguredError):
            mailer.send_verification_code("ada@example.com", "123456")

    def test_the_dev_switch_logs_the_code_instead(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setattr(settings, "brevo_api_key", None)
        monkeypatch.setattr(settings, "mail_dev_log_codes", True)
        with caplog.at_level(logging.WARNING):
            mailer.send_verification_code("ada@example.com", "123456")
        assert "123456" in caplog.text

    def test_a_failed_send_does_not_leave_a_signup_behind(
        self, conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def unreachable(url: str, headers: dict, payload: bytes) -> None:
            raise urllib.error.URLError("down")

        monkeypatch.setattr(mailer, "transport", unreachable)
        with pytest.raises(mailer.MailDeliveryError):
            _start(conn)
        assert get_pending_signup(conn, "ada@example.com") is None


def _claims(**overrides: object) -> dict:
    claims = {
        "aud": CLIENT_ID,
        "iss": "https://accounts.google.com",
        "sub": "google-123",
        "email": "Ada@Example.com",
        "email_verified": True,
        "name": "Ada",
    }
    claims.update(overrides)
    return claims


class TestGoogleCredential:
    def test_a_valid_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(google_identity, "verify_token", lambda token, cid: _claims())
        identity = google_identity.verify_credential("token", CLIENT_ID)
        assert identity == GoogleIdentity("google-123", "ada@example.com", "Ada")

    @pytest.mark.parametrize(
        "claims",
        [
            _claims(aud="someone-elses-app"),
            _claims(iss="https://evil.example.com"),
            _claims(email_verified=False),
            _claims(email=""),
        ],
    )
    def test_untrustworthy_tokens_are_refused(
        self, monkeypatch: pytest.MonkeyPatch, claims: dict
    ) -> None:
        monkeypatch.setattr(google_identity, "verify_token", lambda token, cid: claims)
        with pytest.raises(AuthenticationError):
            google_identity.verify_credential("token", CLIENT_ID)

    def test_a_bad_signature_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def reject(token: str, cid: str) -> dict:
            raise ValueError("Could not verify token signature.")

        monkeypatch.setattr(google_identity, "verify_token", reject)
        with pytest.raises(AuthenticationError):
            google_identity.verify_credential("token", CLIENT_ID)


class TestGoogleSignIn:
    IDENTITY = GoogleIdentity("google-123", "ada@example.com", "Ada")

    def test_a_new_google_user_must_also_confirm_the_code(
        self, conn: sqlite3.Connection, outbox: list
    ) -> None:
        assert auth.google_sign_in(conn, self.IDENTITY) is None
        user = auth.confirm_signup(conn, "ada@example.com", code_sent_to(outbox, "ada@example.com"))
        assert user.username == "ada"
        assert auth.database.get_user_id_by_google_sub(conn, "google-123") == user.id

    def test_afterwards_google_signs_in_without_a_code(
        self, conn: sqlite3.Connection, outbox: list
    ) -> None:
        auth.google_sign_in(conn, self.IDENTITY)
        auth.confirm_signup(conn, "ada@example.com", code_sent_to(outbox, "ada@example.com"))
        sent = len(outbox)
        assert auth.google_sign_in(conn, self.IDENTITY).username == "ada"
        assert len(outbox) == sent

    def test_an_existing_verified_email_is_linked_not_duplicated(
        self, conn: sqlite3.Connection, outbox: list
    ) -> None:
        email = _start(conn, "ada@example.com")
        created = auth.confirm_signup(conn, email, code_sent_to(outbox, email))
        assert auth.google_sign_in(conn, self.IDENTITY).id == created.id
        assert auth.database.get_user_id_by_google_sub(conn, "google-123") == created.id

    def test_a_google_username_never_collides(self, conn: sqlite3.Connection, outbox: list) -> None:
        auth.create_user(conn, "ada", PASSWORD)
        auth.google_sign_in(conn, self.IDENTITY)
        user = auth.confirm_signup(conn, "ada@example.com", code_sent_to(outbox, "ada@example.com"))
        assert user.username == "ada-2"


class TestAuthRoutes:
    def test_config_hides_google_until_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = TestClient(app)
        assert client.get("/auth/config").json() == {"google_client_id": None}
        monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
        assert client.get("/auth/config").json() == {"google_client_id": CLIENT_ID}
        monkeypatch.setattr(settings, "google_client_id", None)
        assert client.post("/auth/google", json={"credential": "x"}).status_code == 404

    def test_the_google_flow_end_to_end(
        self, monkeypatch: pytest.MonkeyPatch, outbox: list
    ) -> None:
        email = unique_email("google")
        claims = _claims(sub=f"sub-{email}", email=email)
        monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
        monkeypatch.setattr(google_identity, "verify_token", lambda token, cid: claims)
        with TestClient(app) as browser:
            started = browser.post("/auth/google", json={"credential": "t", "language": "tr"})
            assert started.json() == {"status": "pending", "user": None, "email": email}
            assert "doğrulama" in outbox[-1]["subject"]
            verified = browser.post(
                "/auth/verify", json={"email": email, "code": code_sent_to(outbox, email)}
            )
            assert verified.status_code == 200
        with TestClient(app) as later:
            again = later.post("/auth/google", json={"credential": "t"})
            assert again.json()["status"] == "signed_in"
            assert later.get("/search", params={"q": "honey"}).status_code == 200

    def test_register_is_503_without_a_mail_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "brevo_api_key", None)
        response = TestClient(app).post(
            "/auth/register",
            json={"username": unique_username("x"), "email": unique_email(), "password": PASSWORD},
        )
        assert response.status_code == 503

    def test_asking_again_too_soon_is_429_with_retry_after(self, outbox: list) -> None:
        email = unique_email("again")
        body = {"username": unique_username("again"), "email": email, "password": PASSWORD}
        client = TestClient(app)
        assert client.post("/auth/register", json=body).status_code == 202
        response = client.post("/auth/resend", json={"email": email})
        assert response.status_code == 429
        assert int(response.headers["retry-after"]) > 0

    def test_a_wrong_code_is_400(self, outbox: list) -> None:
        email = unique_email("wrong")
        client = TestClient(app)
        client.post(
            "/auth/register",
            json={"username": unique_username("wrong"), "email": email, "password": PASSWORD},
        )
        code = code_sent_to(outbox, email)
        response = client.post(
            "/auth/verify", json={"email": email, "code": "000000" if code != "000000" else "1"}
        )
        assert response.status_code == 400


class TestSignInGate:
    def test_the_app_page_redirects_to_sign_in(self) -> None:
        response = TestClient(app).get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"
        assert response.headers["x-frame-options"] == "DENY"  # headers still applied

    def test_the_sign_in_page_and_its_assets_are_open(self) -> None:
        client = TestClient(app)
        assert client.get("/login").status_code == 200
        assert client.get("/static/harbor-scene.svg").status_code == 200

    def test_every_other_route_is_closed(self) -> None:
        """Enumerated from the app itself, so a new route is covered automatically."""
        client = TestClient(app)
        closed = [
            route
            for route in app.routes
            if isinstance(route, APIRoute) and not _is_public(route.path) and route.path != "/"
        ]
        assert len(closed) >= 15
        for route in closed:
            path = (
                route.path.replace("{code}", "6109100000")
                .replace("{subject_reference}", "x")
                .replace("{username}", "x")
            )
            method = sorted(route.methods)[0]
            response = client.request(method, path)
            assert response.status_code == 401, (method, path)

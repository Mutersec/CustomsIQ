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

    def test_the_sender_defaults_to_the_support_address(self) -> None:
        assert settings.mail_from == "support@customsiq.org"

    def test_the_sender_is_customsiq_at_the_support_address(self, outbox: list) -> None:
        mailer.send_verification_code("ada@example.com", "123456", "en")
        assert outbox[-1]["sender"] == {"email": "support@customsiq.org", "name": "CustomsIQ"}


class TestVerificationEmailTemplate:
    """The card-style HTML body sent as Brevo's `htmlContent`."""

    @pytest.mark.parametrize(
        ("language", "heading", "expiry"),
        [
            ("en", "Verify your e-mail address", "This code is valid for 10 minutes."),
            ("tr", "E-posta adresinizi doğrulayın", "Bu kod 10 dakika geçerlidir."),
            ("de", "Bestätigen Sie Ihre E-Mail-Adresse", "Dieser Code ist 10 Minuten gültig."),
        ],
    )
    def test_each_language_gets_the_card_with_the_code_and_expiry(
        self, outbox: list, language: str, heading: str, expiry: str
    ) -> None:
        mailer.send_verification_code("ada@example.com", "407183", language)
        body = outbox[-1]["htmlContent"]
        assert f'<html lang="{language}">' in body
        assert heading in body
        assert expiry in body
        assert ">407183</span>" in body
        assert "border:2px dashed" in body  # the dashed code box
        assert "background-color:#f3f5f8" in body  # light grey page
        assert "background-color:#ffffff" in body  # white card

    def test_it_is_responsive(self) -> None:
        _, _, body = mailer._render("407183", "en")
        assert "max-width:480px" in body
        assert 'width="100%"' in body
        assert "@media only screen and (max-width: 520px)" in body
        assert '<meta name="viewport"' in body

    def test_the_expiry_follows_the_setting(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "verification_code_ttl_minutes", 15)
        _, text, body = mailer._render("407183", "tr")
        assert "Bu kod 15 dakika geçerlidir." in body
        assert "15 dakika" in text

    @pytest.mark.parametrize("language", ["en", "tr", "de", "unknown"])
    def test_no_placeholder_is_left_unfilled(self, language: str) -> None:
        _, _, body = mailer._render("407183", language)
        assert "$" not in body

    def test_an_unknown_language_falls_back_to_english(self) -> None:
        _, _, body = mailer._render("407183", "xx")
        assert '<html lang="en">' in body
        assert "Verify your e-mail address" in body

    def test_inserted_values_are_escaped(self) -> None:
        _, _, body = mailer._render("<b>1</b>", "en")
        assert "<b>1</b>" not in body
        assert "&lt;b&gt;1&lt;/b&gt;" in body

    def test_the_plain_text_alternative_is_still_sent(self, outbox: list) -> None:
        mailer.send_verification_code("ada@example.com", "407183", "en")
        text = outbox[-1]["textContent"]
        assert "407183" in text
        assert "<" not in text

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
    """Google sign-in creates or finds the account at once, with no e-mail code.

    These used to pin a second proof: a new Google user had to confirm an
    e-mailed code before the account existed. That step was dropped — Google's
    signed `email_verified` claim (checked in TestGoogleCredential) already
    proves the address — so these now pin "signed in immediately, nothing sent".
    """

    IDENTITY = GoogleIdentity("google-123", "ada@example.com", "Ada")

    def test_a_new_google_user_is_signed_in_at_once_and_no_mail_is_sent(
        self, conn: sqlite3.Connection, outbox: list
    ) -> None:
        user = auth.google_sign_in(conn, self.IDENTITY)
        assert user.username == "ada"
        assert user.role == auth.SELF_REGISTRATION_ROLE
        assert auth.database.get_user_id_by_google_sub(conn, "google-123") == user.id
        assert auth.database.get_email_for_user(conn, user.id) == "ada@example.com"
        assert outbox == []

    def test_the_second_sign_in_finds_the_same_account(
        self, conn: sqlite3.Connection, outbox: list
    ) -> None:
        first = auth.google_sign_in(conn, self.IDENTITY)
        assert auth.google_sign_in(conn, self.IDENTITY).id == first.id
        assert auth.database.count_users(conn) == 1

    def test_an_existing_verified_email_is_linked_not_duplicated(
        self, conn: sqlite3.Connection, outbox: list
    ) -> None:
        email = _start(conn, "ada@example.com")
        created = auth.confirm_signup(conn, email, code_sent_to(outbox, email))
        assert auth.google_sign_in(conn, self.IDENTITY).id == created.id
        assert auth.database.get_user_id_by_google_sub(conn, "google-123") == created.id

    def test_a_half_finished_email_signup_does_not_block_google(
        self, conn: sqlite3.Connection, outbox: list
    ) -> None:
        _start(conn, "ada@example.com")
        user = auth.google_sign_in(conn, self.IDENTITY)
        # The pending sign-up is for the very address Google just proved, so the
        # same person may take the username it had reserved.
        assert user.username == "ada"
        assert get_pending_signup(conn, "ada@example.com") is None

    def test_a_google_username_never_collides(self, conn: sqlite3.Connection) -> None:
        auth.create_user(conn, "ada", PASSWORD)
        assert auth.google_sign_in(conn, self.IDENTITY).username == "ada-2"

    def test_a_google_account_has_no_usable_password(self, conn: sqlite3.Connection) -> None:
        auth.google_sign_in(conn, self.IDENTITY)
        with pytest.raises(AuthenticationError):
            auth.authenticate(conn, "ada", "")
        with pytest.raises(AuthenticationError):
            auth.authenticate(conn, "ada@example.com", PASSWORD)


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
        """One request: verified token in, session out. It used to be two (plus a code)."""
        email = unique_email("google")
        claims = _claims(sub=f"sub-{email}", email=email)
        monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
        monkeypatch.setattr(google_identity, "verify_token", lambda token, cid: claims)
        with TestClient(app) as browser:
            response = browser.post("/auth/google", json={"credential": "t", "language": "tr"})
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "signed_in"
            assert body["email"] == email
            assert body["user"]["role"] == auth.SELF_REGISTRATION_ROLE
            assert outbox == []
            assert browser.get("/search", params={"q": "honey"}).status_code == 200
        with TestClient(app) as later:
            again = later.post("/auth/google", json={"credential": "t"})
            assert again.json()["user"]["username"] == body["user"]["username"]

    def test_google_works_without_any_mail_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """So "Continue with Google" needs only the client ID, not Brevo."""
        monkeypatch.setattr(settings, "brevo_api_key", None)
        monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
        email = unique_email("nomail")
        monkeypatch.setattr(
            google_identity, "verify_token", lambda t, c: _claims(sub=f"s-{email}", email=email)
        )
        response = TestClient(app).post("/auth/google", json={"credential": "t"})
        assert response.status_code == 200
        assert response.json()["status"] == "signed_in"

    def test_an_unverified_google_email_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
        monkeypatch.setattr(
            google_identity, "verify_token", lambda t, c: _claims(email_verified=False)
        )
        response = TestClient(app).post("/auth/google", json={"credential": "t"})
        assert response.status_code == 400
        assert "set-cookie" not in response.headers

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

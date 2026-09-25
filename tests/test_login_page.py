"""Tests for the dedicated /login page and the demo-credential removal.

The four demo accounts (auth.DEMO_USERS) must keep working via the API even
though nothing on the page displays their values any more.
"""

from fastapi.testclient import TestClient

from src.customsiq import auth
from src.customsiq.api import app

client = TestClient(app)

#: The literal values that must never appear in served HTML again.
_DEMO_SECRETS = [
    value for username, password, _role in auth.DEMO_USERS for value in (username, password)
]


class TestLoginPage:
    def test_returns_200_with_a_login_form(self) -> None:
        response = client.get("/login")
        assert response.status_code == 200
        html = response.text
        assert 'id="auth-form"' in html
        assert 'id="auth-username-input"' in html
        assert 'type="password"' in html
        assert 'id="auth-submit"' in html

    def test_not_included_in_the_openapi_schema(self) -> None:
        schema = client.get("/openapi.json").json()
        assert "/login" not in schema["paths"]


class TestDemoCredentialsAreNotPublished:
    def test_absent_from_the_login_page(self) -> None:
        html = client.get("/login").text
        for secret in _DEMO_SECRETS:
            assert secret not in html

    def test_absent_from_the_main_page(self) -> None:
        html = client.get("/").text
        for secret in _DEMO_SECRETS:
            assert secret not in html

    def test_every_demo_account_still_authenticates(self) -> None:
        for username, password, _role in auth.DEMO_USERS:
            with TestClient(app) as fresh:
                response = fresh.post(
                    "/auth/login", json={"username": username, "password": password}
                )
                assert response.status_code == 200, username
                assert response.json()["username"] == username

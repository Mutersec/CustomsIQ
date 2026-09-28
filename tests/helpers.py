"""Shared helpers for the API tests.

`tests/test_api.py` drives the app through one module-level TestClient against
the real shared connection (see its own note about uuid-based subject
references). Now that writing a review needs an account, these helpers create
throwaway users with unique names so tests stay independent of each other and
of whatever is already in the database.
"""

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from src.customsiq import auth
from src.customsiq.api import app
from src.customsiq.models import User

PASSWORD = "test-password-123"


def unique_username(role: str) -> str:
    """A username nothing else in the suite will collide with."""
    return f"{role}-{uuid.uuid4().hex[:10]}"


def create_test_user(conn: sqlite3.Connection, role: str) -> User:
    """Create a throwaway account with the given role."""
    return auth.create_user(conn, unique_username(role), PASSWORD, role)


@contextmanager
def signed_in_client(role: str) -> Iterator[TestClient]:
    """Yield a TestClient signed in as a fresh account with `role`.

    Its own client instance, so the session cookie can't leak into the shared
    anonymous `client` the other tests use.
    """
    from src.customsiq.api import _conn

    user = create_test_user(_conn, role)
    with TestClient(app) as signed_in:
        response = signed_in.post(
            "/auth/login", json={"username": user.username, "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        yield signed_in


def signed_in_test_client(role: str = auth.VIEWER) -> TestClient:
    """A module-level TestClient already signed in as a fresh account with `role`.

    Every route except the sign-in page and its auth routes now requires a
    session, so test modules that exercise the API as an ordinary user use
    this instead of an anonymous `TestClient(app)`. Anonymous behaviour is
    tested explicitly, with a bare `TestClient(app)`.
    """
    from src.customsiq.api import _conn

    user = create_test_user(_conn, role)
    signed_in = TestClient(app)
    response = signed_in.post("/auth/login", json={"username": user.username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return signed_in


def code_sent_to(outbox: list, email: str) -> str:
    """The six-digit code in the most recent verification e-mail to `email`."""
    import re

    for message in reversed(outbox):
        if message["to"][0]["email"] == email.lower():
            return re.search(r"\b(\d{6})\b", message["textContent"]).group(1)
    raise AssertionError(f"no verification e-mail was sent to {email}")


def unique_email(prefix: str = "user") -> str:
    """An e-mail address nothing else in the suite will collide with."""
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def register_and_verify(client: TestClient, outbox: list, username: str) -> dict:
    """Run the full e-mail sign-up through the API; returns the /auth/verify body."""
    email = unique_email(username)
    response = client.post(
        "/auth/register", json={"username": username, "email": email, "password": PASSWORD}
    )
    assert response.status_code == 202, response.text
    verified = client.post(
        "/auth/verify", json={"email": email, "code": code_sent_to(outbox, email)}
    )
    assert verified.status_code == 200, verified.text
    return verified.json()

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

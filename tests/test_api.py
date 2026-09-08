"""Tests for the FastAPI /search endpoint."""

from fastapi.testclient import TestClient

from src.customsiq.api import app

client = TestClient(app)


def test_search_endpoint_happy_path() -> None:
    """A close query should return the matching HS code first."""
    response = client.get("/search", params={"q": "cotton t-shirt"})
    assert response.status_code == 200
    body = response.json()
    assert body[0]["code"] == "6109100000"


def test_search_endpoint_rejects_empty_query() -> None:
    """An empty query should surface as HTTP 400, not a 500."""
    response = client.get("/search", params={"q": "   "})
    assert response.status_code == 400


def test_search_endpoint_no_match_returns_empty_list() -> None:
    """An unrelated query returns low-score results, not an error."""
    response = client.get("/search", params={"q": "xyz", "limit": 1})
    assert response.status_code == 200
    assert len(response.json()) == 1

"""Tests for the FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.customsiq.api import app

client = TestClient(app)


def test_root_serves_the_web_frontend() -> None:
    """The root URL returns the HTML page, not JSON."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "CustomsIQ" in response.text


def test_health_endpoint_returns_service_info() -> None:
    """Service info moved off the root and lives at /health."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_api_docs_are_not_shadowed_by_the_root_route() -> None:
    """Serving a page at '/' must not swallow the API docs."""
    assert client.get("/docs").status_code == 200


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


def test_screen_endpoint_returns_match() -> None:
    """A listed name is returned with its list metadata and score."""
    response = client.get("/screen", params={"name": "Northwind Maritime Holdings Ltd"})
    assert response.status_code == 200
    hit = response.json()[0]
    assert hit["name"] == "Northwind Maritime Holdings Ltd"
    assert hit["country"] == "CY"
    assert hit["list_source"] == "EU Consolidated Financial Sanctions List"
    assert hit["score"] == pytest.approx(1.0)


def test_screen_endpoint_clean_name_returns_empty_list() -> None:
    """A name that matches nothing screens clean with HTTP 200."""
    response = client.get("/screen", params={"name": "Quokka Beachwear Collective"})
    assert response.status_code == 200
    assert response.json() == []


def test_screen_endpoint_rejects_empty_name() -> None:
    """A blank name should surface as HTTP 400, not a 500."""
    response = client.get("/screen", params={"name": "   "})
    assert response.status_code == 400

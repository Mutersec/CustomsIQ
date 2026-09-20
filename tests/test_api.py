"""Tests for the FastAPI endpoints."""

import uuid

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


def test_classify_endpoint_ranks_with_reasoning() -> None:
    """Suggestions come back scored and carry the terms that drove them."""
    response = client.get("/classify", params={"description": "knitted cotton shirt"})
    assert response.status_code == 200
    top = response.json()[0]
    assert top["code"] == "6109100000"
    assert top["matched_terms"]
    assert 0 < top["score"] <= 1


def test_classify_endpoint_respects_top_n() -> None:
    """The result count is bounded by top_n."""
    response = client.get("/classify", params={"description": "cotton", "top_n": 2})
    assert response.status_code == 200
    assert len(response.json()) <= 2


def test_classify_endpoint_returns_empty_for_unrelated_input() -> None:
    """No shared term means an empty list, not zero-confidence noise."""
    response = client.get("/classify", params={"description": "zephyr quokka bagpipes"})
    assert response.status_code == 200
    assert response.json() == []


def test_classify_endpoint_rejects_blank_input() -> None:
    """A blank description surfaces as HTTP 400."""
    assert client.get("/classify", params={"description": "   "}).status_code == 400


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


def test_duty_endpoint_applies_the_standard_rate() -> None:
    """An uncovered origin is charged the MFN rate, with an explanation."""
    response = client.get(
        "/calculate-duty",
        params={"hs_code": "6109100000", "country_of_origin": "CN", "customs_value": 1000},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rate_type"] == "standard"
    assert body["duty_amount"] == pytest.approx(120.0)
    assert body["trade_agreement"] is None
    assert "MFN" in body["explanation"]


def test_duty_endpoint_applies_a_preferential_rate() -> None:
    """A covered origin gets the agreement rate and the agreement is named."""
    response = client.get(
        "/calculate-duty",
        params={"hs_code": "6109100000", "country_of_origin": "NO", "customs_value": 1000},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rate_type"] == "preferential"
    assert body["duty_amount"] == pytest.approx(0.0)
    assert body["trade_agreement"] == "EU-Solvia Free Trade Agreement"


def test_duty_endpoint_returns_404_when_no_rate_exists() -> None:
    """A missing rate is a data gap, reported as 404 rather than zero duty."""
    response = client.get(
        "/calculate-duty",
        params={"hs_code": "99999999", "country_of_origin": "CN", "customs_value": 100},
    )
    assert response.status_code == 404


def test_duty_endpoint_rejects_a_negative_value() -> None:
    """A negative customs value surfaces as HTTP 400."""
    response = client.get(
        "/calculate-duty",
        params={"hs_code": "6109100000", "country_of_origin": "CN", "customs_value": -5},
    )
    assert response.status_code == 400


def test_classify_endpoint_includes_subject_reference() -> None:
    """Each classify result carries the deterministic audit reference."""
    response = client.get("/classify", params={"description": "knitted cotton shirt"})
    assert response.status_code == 200
    assert response.json()[0]["subject_reference"]


def test_screen_endpoint_includes_subject_reference() -> None:
    """Each screen result carries the deterministic audit reference."""
    response = client.get("/screen", params={"name": "Northwind Maritime Holdings Ltd"})
    assert response.status_code == 200
    assert response.json()[0]["subject_reference"]


def test_duty_endpoint_includes_subject_reference() -> None:
    """The duty result carries the deterministic audit reference."""
    response = client.get(
        "/calculate-duty",
        params={"hs_code": "6109100000", "country_of_origin": "CN", "customs_value": 1000},
    )
    assert response.status_code == 200
    assert response.json()["subject_reference"]


def test_review_endpoint_records_a_decision() -> None:
    """POST /review stores a decision and returns it."""
    subject_reference = f"test-ref-{uuid.uuid4()}"
    response = client.post(
        "/review",
        json={
            "subject_type": "duty",
            "subject_reference": subject_reference,
            "decision": "approved",
            "reviewer_name": "alice",
            "comment": "looks fine",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "approved"
    assert body["reviewer_name"] == "alice"

    history = client.get("/review/history", params={"subject_reference": subject_reference})
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_review_endpoint_rejects_invalid_decision() -> None:
    """An unknown decision value surfaces as HTTP 400."""
    response = client.post(
        "/review",
        json={
            "subject_type": "duty",
            "subject_reference": f"test-ref-{uuid.uuid4()}",
            "decision": "maybe",
            "reviewer_name": "alice",
        },
    )
    assert response.status_code == 400


def test_review_history_filters_by_subject_type() -> None:
    """GET /review/history only returns decisions of the requested type."""
    subject_reference = f"test-ref-{uuid.uuid4()}"
    client.post(
        "/review",
        json={
            "subject_type": "screening",
            "subject_reference": subject_reference,
            "decision": "flagged",
            "reviewer_name": "bob",
        },
    )
    response = client.get(
        "/review/history",
        params={"subject_type": "screening", "subject_reference": subject_reference},
    )
    assert response.status_code == 200
    assert all(row["subject_type"] == "screening" for row in response.json())
    assert len(response.json()) == 1


def test_code_history_returns_empty_for_a_never_versioned_code() -> None:
    """A seeded code with no recorded imports has an empty, not erroring, history."""
    response = client.get("/codes/6109100000/history")
    assert response.status_code == 200
    assert response.json() == []


def test_code_history_returns_404_for_an_unknown_code() -> None:
    """A code that doesn't exist in hs_codes at all surfaces as HTTP 404."""
    response = client.get("/codes/00000000/history")
    assert response.status_code == 404


def test_dashboard_stats_returns_the_expected_shape() -> None:
    """The dashboard endpoint returns every field, with sane types.

    Exact counts aren't asserted here: _conn is the shared, persistent
    customsiq.db that accumulates rows across the whole test session (the
    same reason the /review tests above use uuid-based data instead of
    exact totals). tests/test_dashboard.py covers exact-count behaviour
    against an isolated in-memory database.
    """
    response = client.get("/dashboard/stats")
    assert response.status_code == 200
    body = response.json()

    assert body["hs_code_count"] >= 0
    assert body["sanctioned_entity_count"] >= 0
    assert body["tariff_rate_count"] >= 0
    assert body["review_total"] >= 0
    assert set(body["review_by_decision"]) == {"approved", "rejected", "flagged"}
    assert set(body["review_by_subject_type"]) == {"classification", "screening", "duty"}
    assert isinstance(body["recent_reviews"], list)
    assert body["import_run_count"] >= 0
    assert isinstance(body["recent_import_runs"], list)
    assert body["versioned_code_count"] >= 0


def test_assess_risk_happy_path() -> None:
    """A composite risk assessment returns the expected shape."""
    response = client.get(
        "/assess-risk",
        params={
            "description": "cotton t-shirt",
            "country_of_origin": "NO",
            "party_name": "Quokka Beachwear",
            "customs_value": 1000,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["level"] in {"low", "medium", "high"}
    assert body["hs_code"] == "6109100000"
    assert {f["name"] for f in body["factors"]} == {"screening", "classification", "duty"}


def test_assess_risk_rejects_neither_description_nor_hs_code() -> None:
    """Omitting both description and hs_code surfaces as HTTP 400."""
    response = client.get(
        "/assess-risk",
        params={
            "country_of_origin": "NO",
            "party_name": "Quokka Beachwear",
            "customs_value": 1000,
        },
    )
    assert response.status_code == 400


def test_assess_risk_rejects_both_description_and_hs_code() -> None:
    """Giving both description and hs_code surfaces as HTTP 400."""
    response = client.get(
        "/assess-risk",
        params={
            "description": "cotton t-shirt",
            "hs_code": "6109100000",
            "country_of_origin": "NO",
            "party_name": "Quokka Beachwear",
            "customs_value": 1000,
        },
    )
    assert response.status_code == 400

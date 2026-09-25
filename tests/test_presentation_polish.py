"""Tests for the presentation-polish phase: OG/favicon tags, typed API
responses, security headers, and the LICENSE file.

Nothing here tests decision logic — every route's actual behavior is already
covered elsewhere (test_api.py and friends). These tests are about how the
app *presents* itself: the HTML head, the OpenAPI schema, and response
headers.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.customsiq.api import app
from tests.helpers import signed_in_client

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "src" / "customsiq" / "static"


class TestFaviconAndOpenGraph:
    """The <head> block the brief is actually about: what a link-preview crawler reads."""

    @pytest.fixture(scope="class")
    def html(self) -> str:
        return client.get("/").text

    def test_favicon_link_is_present(self, html: str) -> None:
        assert '<link rel="icon" type="image/png" href="/static/favicon.png">' in html

    def test_apple_touch_icon_is_present(self, html: str) -> None:
        assert '<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">' in html

    def test_meta_description_is_present_and_non_generic(self, html: str) -> None:
        assert '<meta name="description" content="' in html
        assert "trade-compliance" in html.lower()

    @pytest.mark.parametrize(
        "tag",
        [
            '<meta property="og:type" content="website">',
            '<meta property="og:title" content="CustomsIQ — EU Trade Compliance Toolkit">',
            '<meta property="og:url" content="https://customsiq-gs0u.onrender.com/">',
            '<meta name="twitter:card" content="summary_large_image">',
        ],
    )
    def test_open_graph_tag_is_present(self, html: str, tag: str) -> None:
        assert tag in html

    def test_og_description_matches_the_meta_description(self, html: str) -> None:
        """One source of truth for the one-liner, not two texts to keep in sync."""
        import re

        meta = re.search(r'<meta name="description" content="([^"]+)">', html)
        og = re.search(r'<meta property="og:description" content="([^"]+)">', html)
        assert meta and og
        assert meta.group(1) == og.group(1)

    def test_og_image_is_an_absolute_https_url(self, html: str) -> None:
        """A relative path is invalid per the OG spec — crawlers won't resolve it."""
        import re

        match = re.search(r'<meta property="og:image" content="([^"]+)">', html)
        assert match
        assert match.group(1).startswith("https://")

    @pytest.mark.parametrize(
        "path",
        ["/static/favicon.png", "/static/apple-touch-icon.png", "/static/og-image.png"],
    )
    def test_asset_is_served_as_a_real_png(self, path: str) -> None:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert len(response.content) > 500  # rules out an empty/placeholder file
        assert response.content[:8] == b"\x89PNG\r\n\x1a\n"  # the real PNG magic bytes

    def test_og_image_is_1200_by_630(self) -> None:
        """The standard Open Graph / Twitter card size."""
        pytest.importorskip(
            "PIL", reason="Pillow is a one-off asset-generation tool, not a project dependency"
        )
        from PIL import Image

        with Image.open(STATIC_DIR / "og-image.png") as img:
            assert img.size == (1200, 630)


class TestTypedResponseSchemas:
    """/openapi.json shows real field schemas, not additionalProperties: true."""

    @pytest.fixture(scope="class")
    def openapi(self) -> dict:
        return client.get("/openapi.json").json()

    def test_app_has_a_description_and_version(self, openapi: dict) -> None:
        assert openapi["info"]["description"]
        assert openapi["info"]["version"]

    @pytest.mark.parametrize(
        ("path", "method", "ref_name"),
        [
            ("/search", "get", "SearchResult"),
            ("/classify", "get", "ClassificationResultResponse"),
            ("/screen", "get", "ScreeningResultResponse"),
            ("/calculate-duty", "get", "DutyCalculationResponse"),
            ("/assess-risk", "get", "RiskAssessmentResponse"),
            ("/sap-gts/compliance-check", "get", "GtsDocumentResponse"),
            ("/dashboard/stats", "get", "DashboardStatsResponse"),
            ("/auth/me", "get", "WhoAmIResponse"),
        ],
    )
    def test_route_has_a_typed_response_schema(
        self, openapi: dict, path: str, method: str, ref_name: str
    ) -> None:
        schema = openapi["paths"][path][method]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        # A list-returning route wraps the ref in {"type": "array", "items": {"$ref": ...}}.
        ref = schema.get("$ref") or schema.get("items", {}).get("$ref")
        assert ref == f"#/components/schemas/{ref_name}"

    def test_the_sap_gts_schema_exposes_real_bapiret2_field_names(self, openapi: dict) -> None:
        """The one place a typed schema does real demonstrative work."""
        row_schema = openapi["components"]["schemas"]["GtsReturnRow"]["properties"]
        for field in ("TYPE", "NUMBER", "MESSAGE", "MESSAGE_V1", "PARAMETER", "SYSTEM"):
            assert field in row_schema

    def test_no_response_schema_is_a_bare_additional_properties_object(self, openapi: dict) -> None:
        """The exact regression this phase fixes, checked across every JSON route."""
        for path, methods in openapi["paths"].items():
            for method, operation in methods.items():
                if method not in ("get", "post"):
                    continue
                responses = operation.get("responses", {})
                ok = responses.get("200") or responses.get("201")
                if not ok:
                    continue
                schema = ok.get("content", {}).get("application/json", {}).get("schema")
                if schema is None:
                    continue  # e.g. "/" serves HTML, not JSON
                assert (
                    schema.get("additionalProperties") is not True
                ), f"{method.upper()} {path} still has an untyped response"


class TestResponseBodyUnchanged:
    """response_model= is typing only — the actual JSON must be unchanged."""

    def test_search_response_has_exactly_the_expected_fields(self) -> None:
        body = client.get("/search", params={"q": "cotton t-shirt"}).json()
        assert body
        assert set(body[0]) == {"code", "description", "category", "score"}

    def test_assess_risk_response_has_exactly_the_expected_fields(self) -> None:
        body = client.get(
            "/assess-risk",
            params={
                "country_of_origin": "NO",
                "party_name": "Northwind Maritime",
                "customs_value": 1000,
                "description": "cotton t-shirt",
            },
        ).json()
        assert set(body) == {"level", "composite_score", "hs_code", "factors"}
        assert set(body["factors"][0]) == {"name", "score", "weight", "explanation"}

    def test_sap_gts_response_shape_is_unchanged(self) -> None:
        body = client.get(
            "/sap-gts/compliance-check",
            params={
                "country_of_origin": "NO",
                "party_name": "Northwind Maritime",
                "customs_value": 1000,
                "description": "cotton t-shirt",
            },
        ).json()
        assert set(body) == {"HEADER", "RETURN"}
        assert body["HEADER"]["SIMULATION"] is True
        row = body["RETURN"][0]
        assert set(row) == {
            "TYPE",
            "ID",
            "NUMBER",
            "MESSAGE",
            "LOG_NO",
            "LOG_MSG_NO",
            "MESSAGE_V1",
            "MESSAGE_V2",
            "MESSAGE_V3",
            "MESSAGE_V4",
            "PARAMETER",
            "ROW",
            "FIELD",
            "SYSTEM",
        }

    def test_auth_me_still_returns_null_user_when_anonymous(self) -> None:
        assert client.get("/auth/me").json() == {"user": None}

    def test_dashboard_stats_field_set_is_unchanged(self) -> None:
        body = client.get("/dashboard/stats").json()
        assert set(body) == {
            "hs_code_count",
            "sanctioned_entity_count",
            "tariff_rate_count",
            "review_total",
            "review_by_decision",
            "review_by_subject_type",
            "recent_reviews",
            "recent_reviews_restricted",
            "import_run_count",
            "recent_import_runs",
            "versioned_code_count",
        }


class TestSecurityHeaders:
    """Applied globally, via middleware, including on error responses."""

    EXPECTED = {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "strict-origin-when-cross-origin",
        "x-xss-protection": "0",
    }

    def test_headers_present_on_a_normal_response(self) -> None:
        response = client.get("/health")
        for header, value in self.EXPECTED.items():
            assert response.headers.get(header) == value

    def test_headers_present_on_a_404(self) -> None:
        response = client.get("/codes/00000000/history")
        assert response.status_code == 404
        for header, value in self.EXPECTED.items():
            assert response.headers.get(header) == value

    def test_headers_present_on_a_400(self) -> None:
        response = client.get("/search", params={"q": ""})
        assert response.status_code == 400
        for header, value in self.EXPECTED.items():
            assert response.headers.get(header) == value

    def test_no_content_security_policy_is_set(self) -> None:
        """Deliberately omitted — see the middleware's docstring and the README."""
        response = client.get("/health")
        assert "content-security-policy" not in {k.lower() for k in response.headers}


class TestLicenseAndRepoMetadata:
    """The gap the audit actually found: a claimed license with no file."""

    def test_license_file_exists(self) -> None:
        assert (REPO_ROOT / "LICENSE").exists()

    def test_license_is_mit_matching_the_readme_badge(self) -> None:
        text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
        assert text.startswith("MIT License")

    def test_pyproject_declares_the_same_license(self) -> None:
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "[project]" in pyproject
        assert 'license = { text = "MIT" }' in pyproject


def test_a_signed_in_role_still_works_end_to_end_after_the_schema_change() -> None:
    """One deeper smoke test: a real POST /review round-trip under its new model."""
    import uuid

    from src.customsiq import auth

    with signed_in_client(auth.ANALYST) as reviewer:
        response = reviewer.post(
            "/review",
            json={
                "subject_type": "duty",
                "subject_reference": f"polish-check-{uuid.uuid4()}",
                "decision": "approved",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "id",
        "subject_type",
        "subject_reference",
        "decision",
        "reviewer_name",
        "comment",
        "reviewed_at",
        "authenticated",
    }
    assert body["authenticated"] is True

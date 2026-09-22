"""Tests for the SAP GTS terminology rendering layer.

The worked examples are the ones already pinned in tests/test_risk.py and quoted
in the READMEs — nothing new is invented here, because this layer must not change
any number it is handed.

Several tests exist to keep the *honesty* properties from eroding: every payload
carries its disclaimer, and the module never turns into a second decision engine.
"""

import inspect
import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.customsiq import sap_gts_bridge
from src.customsiq.api import app
from src.customsiq.database import get_connection, seed
from src.customsiq.models import ReviewDecision
from src.customsiq.review import reference_for_classification
from src.customsiq.risk import assess_shipment
from src.customsiq.sap_gts_bridge import (
    DISCLAIMER,
    FIELD_LENGTHS,
    MESSAGE_CLASS,
    compliance_check,
    legal_control_log,
)

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[1]
READMES = ("README.md", "README.tr.md", "README.de.md")


@pytest.fixture
def conn() -> sqlite3.Connection:
    """An in-memory database, seeded like the other modules' tests."""
    connection = get_connection(":memory:")
    seed(connection)
    return connection


def rows_of(document) -> list:
    """The RETURN table of a rendered document."""
    return document.as_payload()["RETURN"]


def decision(subject_type: str, verdict: str, reviewer: str = "officer_kim") -> ReviewDecision:
    """A ReviewDecision built the way database rows produce them."""
    return ReviewDecision(
        id=1,
        subject_type=subject_type,
        subject_reference="ref-1",
        decision=verdict,
        reviewer_name=reviewer,
        comment=None,
        reviewed_at="2026-01-01T12:00:00+00:00",
    )


class TestPinnedWorkedExamples:
    """The examples already pinned by test_risk.py, rendered in GTS terms."""

    def test_sanctions_hit_renders_as_a_blocked_document(self, conn: sqlite3.Connection) -> None:
        """The README's headline example: 0.6609, high, Northwind Maritime."""
        assessment = assess_shipment(
            conn, "NO", "Northwind Maritime", 1000, description="cotton t-shirt"
        )
        assert assessment.composite_score == pytest.approx(0.6609, abs=1e-4)

        document = compliance_check(
            assessment, "Northwind Maritime", reference_for_classification("cotton t-shirt")
        )
        payload = document.as_payload()

        assert payload["HEADER"]["DOCUMENT_STATUS"] == "BLOCKED"
        assert payload["HEADER"]["FUNCTIONAL_AREAS"] == [
            "COMPLIANCE_MGMT",
            "CUSTOMS_MGMT",
            "RISK_MGMT",
        ]
        assert [(r["TYPE"], r["NUMBER"], r["PARAMETER"]) for r in payload["RETURN"]] == [
            ("E", "001", "SPL_SCREENING"),
            ("I", "010", "CLASSIFICATION"),
            ("S", "020", "PREFERENCE_DUTY"),
            ("E", "030", "RISK_ASSESSMENT"),
        ]

    def test_the_rendered_numbers_are_the_assessment_s_own(self, conn: sqlite3.Connection) -> None:
        """This layer renames and reshapes; it must never re-derive a score."""
        assessment = assess_shipment(
            conn, "NO", "Northwind Maritime", 1000, description="cotton t-shirt"
        )
        overall = rows_of(compliance_check(assessment, "Northwind Maritime", "ref-1"))[-1]
        assert "0.6609" in overall["MESSAGE"]
        assert overall["MESSAGE_V2"] == "0.6609"
        assert overall["MESSAGE_V1"] == "HIGH"

    def test_clean_shipment_renders_as_not_blocked(self, conn: sqlite3.Connection) -> None:
        """0.0609, low — nothing to block, and no error-severity message."""
        assessment = assess_shipment(
            conn, "NO", "Quokka Beachwear", 1000, description="cotton t-shirt"
        )
        assert assessment.composite_score == pytest.approx(0.0609, abs=1e-4)

        document = compliance_check(assessment, "Quokka Beachwear", "ref-1")
        assert document.as_payload()["HEADER"]["DOCUMENT_STATUS"] == "NOT_BLOCKED"
        assert [r["TYPE"] for r in rows_of(document)] == ["S", "I", "S", "S"]

    def test_unclassifiable_description_warns_on_classification(
        self, conn: sqlite3.Connection
    ) -> None:
        """0.25, medium — classification failed, so the document needs a human."""
        assessment = assess_shipment(conn, "CN", "Quokka Beachwear", 100, description="device")
        assert assessment.composite_score == pytest.approx(0.25, abs=1e-4)
        assert assessment.hs_code is None

        rows = rows_of(compliance_check(assessment, "Quokka Beachwear", "ref-1"))
        classification = next(r for r in rows if r["PARAMETER"] == "CLASSIFICATION")
        assert (classification["TYPE"], classification["NUMBER"]) == ("W", "011")
        assert rows[-1]["NUMBER"] == "031"  # medium
        assert compliance_check(assessment, "Q", "ref-1").status == "PENDING"

    def test_a_supplied_code_is_information_not_a_determination(
        self, conn: sqlite3.Connection
    ) -> None:
        """GTS only 'classifies' when it determines a code; a given one is a fact."""
        assessment = assess_shipment(conn, "NO", "Quokka Beachwear", 1000, hs_code="6109100000")
        rows = rows_of(compliance_check(assessment, "Quokka Beachwear", "ref-1"))
        classification = next(r for r in rows if r["PARAMETER"] == "CLASSIFICATION")
        assert (classification["TYPE"], classification["NUMBER"]) == ("I", "012")
        assert classification["MESSAGE_V1"] == "6109100000"


class TestBapiret2Fidelity:
    """The RETURN rows must match the real structure, names and lengths."""

    def test_every_row_has_exactly_the_documented_fields(self, conn: sqlite3.Connection) -> None:
        assessment = assess_shipment(conn, "NO", "Quokka Beachwear", 1000, hs_code="6109100000")
        expected = set(FIELD_LENGTHS) | {"ROW"}
        for row in rows_of(compliance_check(assessment, "Quokka Beachwear", "ref-1")):
            assert set(row) == expected

    def test_field_values_respect_the_real_lengths(self, conn: sqlite3.Connection) -> None:
        """A 120-character party name must truncate to MESSAGE_V1's 50."""
        long_name = "Northwind " * 12
        assessment = assess_shipment(conn, "NO", long_name, 1000, hs_code="6109100000")
        rows = rows_of(compliance_check(assessment, long_name, "x" * 80))

        for row in rows:
            for field, length in FIELD_LENGTHS.items():
                assert len(row[field]) <= length, f"{field} exceeds {length}"
        assert len(rows[0]["MESSAGE_V1"]) == 50
        assert len(rows[0]["LOG_NO"]) == 20

    def test_message_type_is_always_a_valid_sap_severity(self, conn: sqlite3.Connection) -> None:
        assessment = assess_shipment(conn, "CN", "Northwind Maritime", 500, description="plastic")
        for row in rows_of(compliance_check(assessment, "Northwind Maritime", "ref-1")):
            assert row["TYPE"] in {"S", "E", "W", "I", "A"}

    def test_number_is_three_digits_and_the_class_is_customer_namespace(
        self, conn: sqlite3.Connection
    ) -> None:
        """A Z-prefixed message class is SAP's own way of saying 'not standard'."""
        assessment = assess_shipment(conn, "NO", "Quokka Beachwear", 1000, hs_code="6109100000")
        for row in rows_of(compliance_check(assessment, "Quokka Beachwear", "ref-1")):
            assert re.fullmatch(r"\d{3}", row["NUMBER"])
            assert row["ID"] == MESSAGE_CLASS
            assert row["ID"].startswith("Z")
            assert row["SYSTEM"] == "CUSTOMSIQ"

    def test_rows_are_numbered_from_one(self, conn: sqlite3.Connection) -> None:
        assessment = assess_shipment(conn, "NO", "Quokka Beachwear", 1000, hs_code="6109100000")
        rows = rows_of(compliance_check(assessment, "Quokka Beachwear", "ref-1"))
        assert [r["ROW"] for r in rows] == [1, 2, 3, 4]
        assert [r["LOG_MSG_NO"] for r in rows] == ["000001", "000002", "000003", "000004"]


class TestLegalControlLog:
    """Review decisions rendered as the block/release check log."""

    def test_a_rejection_blocks_the_document(self) -> None:
        document = legal_control_log([decision("classification", "rejected")], "ref-1")
        payload = document.as_payload()
        assert payload["HEADER"]["DOCUMENT_STATUS"] == "BLOCKED"
        assert payload["RETURN"][0]["TYPE"] == "E"
        assert payload["RETURN"][0]["NUMBER"] == "041"
        assert payload["RETURN"][0]["MESSAGE_V1"] == "officer_kim"

    def test_an_approval_releases_it(self) -> None:
        document = legal_control_log([decision("screening", "approved")], "ref-1")
        assert document.as_payload()["HEADER"]["DOCUMENT_STATUS"] == "RELEASED"
        assert document.as_payload()["RETURN"][0]["TYPE"] == "S"

    def test_a_flag_leaves_it_pending(self) -> None:
        document = legal_control_log([decision("duty", "flagged")], "ref-1")
        assert document.as_payload()["HEADER"]["DOCUMENT_STATUS"] == "PENDING"
        assert document.as_payload()["RETURN"][0]["TYPE"] == "W"

    def test_the_most_recent_decision_sets_the_status(self) -> None:
        """History arrives newest-first, and a release supersedes an old block."""
        document = legal_control_log(
            [decision("classification", "approved"), decision("classification", "rejected")],
            "ref-1",
        )
        assert document.as_payload()["HEADER"]["DOCUMENT_STATUS"] == "RELEASED"
        assert len(document.as_payload()["RETURN"]) == 2

    def test_no_decisions_is_a_valid_document_not_an_error(self) -> None:
        payload = legal_control_log([], "ref-1").as_payload()
        assert payload["HEADER"]["DOCUMENT_STATUS"] == "NOT_BLOCKED"
        assert payload["RETURN"][0]["NUMBER"] == "043"


class TestHonestyIsMachineChecked:
    """The disclaimer must not be quietly droppable."""

    def test_every_payload_declares_itself_a_simulation(self, conn: sqlite3.Connection) -> None:
        assessment = assess_shipment(conn, "NO", "Quokka Beachwear", 1000, hs_code="6109100000")
        for payload in (
            compliance_check(assessment, "Quokka Beachwear", "ref-1").as_payload(),
            legal_control_log([], "ref-1").as_payload(),
            legal_control_log([decision("duty", "approved")], "ref-1").as_payload(),
        ):
            assert payload["HEADER"]["SIMULATION"] is True
            assert payload["HEADER"]["DISCLAIMER"] == DISCLAIMER

    def test_the_payload_disclaimer_denies_both_claims_that_matter(self) -> None:
        """'Not an SAP export' and 'not a valid BAPI/IDoc payload'."""
        assert "Not an SAP system export" in DISCLAIMER
        assert "not a valid BAPI or IDoc payload" in DISCLAIMER

    def test_the_api_responses_carry_it_too(self) -> None:
        response = client.get(
            "/sap-gts/compliance-check",
            params={
                "country_of_origin": "NO",
                "party_name": "Northwind Maritime",
                "customs_value": 1000,
                "description": "cotton t-shirt",
            },
        )
        assert response.json()["HEADER"]["SIMULATION"] is True
        assert response.json()["HEADER"]["DISCLAIMER"] == DISCLAIMER

    @pytest.mark.parametrize("readme", READMES)
    def test_each_readme_denies_being_an_integration(self, readme: str) -> None:
        """The section must say what it is not, in every language."""
        text = (REPO_ROOT / readme).read_text(encoding="utf-8")
        assert "BAPIRET2" in text
        assert "SAP BTP" in text
        assert text.count("IDoc") >= 1

    def test_the_ui_shows_a_disclaimer_in_all_three_languages(self) -> None:
        """Visible in the panel itself, not only in the README."""
        page = (REPO_ROOT / "src" / "customsiq" / "static" / "index.html").read_text(
            encoding="utf-8"
        )
        assert page.count("sapGts.disclaimer") >= 1
        assert page.count("BAPIRET2") >= 3  # one per language block
        assert 'class="sim-notice"' in page


class TestReadOnlyBoundary:
    """A rendering layer, not a decision engine."""

    def test_no_function_takes_a_database_connection(self) -> None:
        """Checked on the signatures, so prose mentioning 'connected' can't pass it."""
        functions = [
            member
            for _, member in inspect.getmembers(sap_gts_bridge, inspect.isfunction)
            if member.__module__ == sap_gts_bridge.__name__
        ]
        assert functions, "expected to find functions to inspect"
        for function in functions:
            parameters = set(inspect.signature(function).parameters)
            assert not parameters & {"conn", "connection", "db"}, function.__name__

        source = Path(sap_gts_bridge.__file__).read_text(encoding="utf-8")
        assert "import sqlite3" not in source
        assert "from src.customsiq.database" not in source

    def test_it_calls_none_of_the_decision_functions(self) -> None:
        """Type imports are fine; calling into the decision layer is not."""
        source = Path(sap_gts_bridge.__file__).read_text(encoding="utf-8")
        for call in (
            "classify(",
            "screen_entity(",
            "calculate_duty(",
            "assess_shipment(",
            "submit_review(",
        ):
            assert call not in source

    def test_every_public_renderer_is_pure(self) -> None:
        """No hidden I/O: the only impurity allowed is the timestamp."""
        source = Path(sap_gts_bridge.__file__).read_text(encoding="utf-8")
        for forbidden in ("open(", "requests", "urllib", "execute("):
            assert forbidden not in source
        assert "datetime.now" in inspect.getsource(sap_gts_bridge._now)


class TestEndpoints:
    """Both routes are public, matching the data they reshape."""

    def test_compliance_check_is_public(self) -> None:
        response = client.get(
            "/sap-gts/compliance-check",
            params={
                "country_of_origin": "NO",
                "party_name": "Northwind Maritime",
                "customs_value": 1000,
                "description": "cotton t-shirt",
            },
        )
        assert response.status_code == 200
        assert response.json()["HEADER"]["DOCUMENT_STATUS"] == "BLOCKED"
        assert len(response.json()["RETURN"]) == 4

    def test_compliance_check_rejects_bad_input_like_assess_risk(self) -> None:
        """Neither description nor hs_code — a 400, same as /assess-risk."""
        response = client.get(
            "/sap-gts/compliance-check",
            params={"country_of_origin": "NO", "party_name": "x", "customs_value": 1000},
        )
        assert response.status_code == 400

    def test_legal_control_is_public_and_empty_is_not_a_404(self) -> None:
        response = client.get("/sap-gts/legal-control/no-such-reference-at-all")
        assert response.status_code == 200
        assert response.json()["HEADER"]["DOCUMENT_STATUS"] == "NOT_BLOCKED"
        assert response.json()["RETURN"][0]["NUMBER"] == "043"

    def test_the_export_matches_the_underlying_assess_risk_result(self) -> None:
        """Same inputs, same numbers — the export adds no arithmetic."""
        params = {
            "country_of_origin": "NO",
            "party_name": "Northwind Maritime",
            "customs_value": 1000,
            "description": "cotton t-shirt",
        }
        risk = client.get("/assess-risk", params=params).json()
        gts = client.get("/sap-gts/compliance-check", params=params).json()
        assert f"{risk['composite_score']:.4f}" in gts["RETURN"][-1]["MESSAGE"]
        assert risk["level"].upper() in gts["RETURN"][-1]["MESSAGE"]

"""Tests for QA audit Bug #6: a confirmed sanctions hit is an absolute stop.

The weighted composite is deliberately untouched — 0.6609 is still 0.6609,
and "high" is still "high". What's new is a categorical `override` layered on
top, so a confirmed match reads as "blocked", not merely "elevated".

These tests pin three things: that the override fires on the screening factor
alone, that the score it sits beside is unchanged, and that GTS now blocks
*because of* the override rather than because a blend happened to clear a
threshold.
"""

import sqlite3

import pytest

from src.customsiq import risk as risk_module
from src.customsiq.database import get_connection, seed
from src.customsiq.risk import assess_shipment
from src.customsiq.sap_gts_bridge import compliance_check

#: On the denied-party list — `screen_entity` matches it at the normal
#: compliance threshold, so the screening factor scores 1.0.
SANCTIONED = "Northwind Maritime"
#: Matches only at the 0.55 near-miss tier: screening scores 0.4.
NEAR_MISS = "Northwind Logistics"
CLEAN = "Quokka Beachwear"


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = get_connection(":memory:")
    seed(connection)
    return connection


class TestTheTriggerIsScreeningAlone:
    """A real hit is absolute on its own, whatever the other two factors say."""

    @pytest.mark.parametrize(
        ("label", "kwargs"),
        [
            # classification 0.0 — the code was supplied, nothing to be unsure about
            ("code supplied", {"hs_code": "6109100000"}),
            # classification 1.0 — nothing in the corpus shares a term
            ("unclassifiable", {"description": "device"}),
            # a normal, confidently classified description
            ("classified", {"description": "cotton t-shirt"}),
        ],
    )
    def test_a_confirmed_hit_always_overrides(
        self, conn: sqlite3.Connection, label: str, kwargs: dict
    ) -> None:
        result = assess_shipment(conn, "NO", SANCTIONED, 1000, **kwargs)
        assert result.override == "sanctions_hit", label
        # ...and it really is varying the other factors, not testing one case
        # three times.
        assert {f.name: f.score for f in result.factors}["screening"] == 1.0

    def test_the_other_factors_genuinely_differ_across_those_cases(
        self, conn: sqlite3.Connection
    ) -> None:
        """Guards the parametrisation above from quietly testing one scenario."""
        scores = set()
        for kwargs in ({"hs_code": "6109100000"}, {"description": "device"}):
            result = assess_shipment(conn, "NO", SANCTIONED, 1000, **kwargs)
            scores.add({f.name: f.score for f in result.factors}["classification"])
        assert scores == {0.0, 1.0}

    def test_a_near_miss_does_not_override(self, conn: sqlite3.Connection) -> None:
        """The 0.4 tier is a prompt to look closer, not a decision."""
        result = assess_shipment(conn, "NO", NEAR_MISS, 1000, description="plastic thing")
        assert {f.name: f.score for f in result.factors}["screening"] == 0.4
        assert result.override is None

    def test_a_clean_party_does_not_override(self, conn: sqlite3.Connection) -> None:
        result = assess_shipment(conn, "NO", CLEAN, 1000, description="cotton t-shirt")
        assert result.override is None

    def test_a_high_score_without_a_hit_does_not_override(self, conn: sqlite3.Connection) -> None:
        """The override tracks the finding, not the number.

        An unclassifiable, no-rate shipment scores well above the near-miss
        case, but nothing was actually found against the party — so there is
        no absolute stop to declare.
        """
        result = assess_shipment(conn, "CN", CLEAN, 100, description="device")
        assert result.override is None


class TestTheWeightedScoreIsUntouched:
    """The whole point of layering rather than replacing."""

    def test_the_pinned_worked_example_is_unchanged_and_gains_the_override(
        self, conn: sqlite3.Connection
    ) -> None:
        """README's headline example: 0.6609 / high, now also an absolute stop."""
        result = assess_shipment(conn, "NO", SANCTIONED, 1000, description="cotton t-shirt")
        assert result.composite_score == pytest.approx(0.6609, abs=1e-4)
        assert result.level == "high"
        assert result.override == "sanctions_hit"

    def test_the_override_does_not_round_the_score_up(self, conn: sqlite3.Connection) -> None:
        """A blocked shipment still reports its real, explainable score."""
        result = assess_shipment(conn, "NO", SANCTIONED, 1000, description="cotton t-shirt")
        assert result.composite_score < 1.0


class TestGtsBlocksBecauseOfTheOverride:
    """sap_gts_bridge derives BLOCKED from the override, not from the level."""

    def _status(self, conn: sqlite3.Connection, party: str, **kwargs) -> str:
        assessment = assess_shipment(conn, "NO", party, 1000, **kwargs)
        return compliance_check(assessment, party, "ref-1").status

    def test_a_confirmed_hit_blocks(self, conn: sqlite3.Connection) -> None:
        assert self._status(conn, SANCTIONED, description="cotton t-shirt") == "BLOCKED"

    def test_a_near_miss_is_still_only_pending(self, conn: sqlite3.Connection) -> None:
        assert self._status(conn, NEAR_MISS, description="plastic thing") == "PENDING"

    def test_a_clean_party_is_still_not_blocked(self, conn: sqlite3.Connection) -> None:
        assert self._status(conn, CLEAN, description="cotton t-shirt") == "NOT_BLOCKED"

    def test_the_pinned_message_sequence_is_byte_identical(self, conn: sqlite3.Connection) -> None:
        """Only the status derivation changed basis; the rows did not change."""
        assessment = assess_shipment(conn, "NO", SANCTIONED, 1000, description="cotton t-shirt")
        payload = compliance_check(assessment, SANCTIONED, "ref-1").as_payload()
        assert [(r["TYPE"], r["NUMBER"], r["PARAMETER"]) for r in payload["RETURN"]] == [
            ("E", "001", "SPL_SCREENING"),
            ("I", "010", "CLASSIFICATION"),
            ("S", "020", "PREFERENCE_DUTY"),
            ("E", "030", "RISK_ASSESSMENT"),
        ]
        assert payload["HEADER"]["DOCUMENT_STATUS"] == "BLOCKED"

    def test_blocking_no_longer_rides_on_the_threshold_arithmetic(
        self, conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The regression this fix actually prevents.

        A confirmed hit contributes 0.6, which cleared the 0.5 "high" line on
        its own — so BLOCKED used to be correct by arithmetic accident of two
        independently tunable constants. Lift the threshold above 0.6 and the
        level drops to "medium"; the document must still be BLOCKED, because
        the block now follows the finding rather than the blend.
        """
        monkeypatch.setattr(risk_module, "_LEVEL_HIGH", 0.95)
        assessment = assess_shipment(conn, "NO", SANCTIONED, 1000, description="cotton t-shirt")

        assert assessment.level == "medium"  # the retuned threshold took effect
        assert assessment.override == "sanctions_hit"
        assert compliance_check(assessment, SANCTIONED, "ref-1").status == "BLOCKED"

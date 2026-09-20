"""Composite shipment risk scoring over the four decision modules.

No new decisions are made here — this only calls classify(), screen_entity()
and calculate_duty() and combines their outputs into one explainable score.
"""

import sqlite3
from typing import NamedTuple, Optional

from src.customsiq.cn_classifier import classify
from src.customsiq.embargo_screener import screen_entity
from src.customsiq.exceptions import InvalidQueryError, RateNotFoundError
from src.customsiq.tariff_calculator import PREFERENTIAL, calculate_duty

_WEIGHT_SCREENING = 0.6
_WEIGHT_CLASSIFICATION = 0.25
_WEIGHT_DUTY = 0.15

_NEAR_MISS_THRESHOLD = 0.55
_SCREENING_HIT = 1.0
_SCREENING_NEAR_MISS = 0.4
_SCREENING_CLEAN = 0.0

_DUTY_RATE_CEILING = 20.0
_DUTY_PREFERENTIAL_BUMP = 0.15
_DUTY_MISSING_RATE_SCORE = 0.6

_LEVEL_HIGH = 0.5
_LEVEL_MEDIUM = 0.2


class RiskFactor(NamedTuple):
    """One sub-factor's contribution to a composite risk score."""

    name: str  # "screening" | "classification" | "duty"
    score: float  # 0..1, before weighting
    weight: float
    explanation: str


class RiskAssessment(NamedTuple):
    """A shipment's composite risk score, with each factor's contribution shown."""

    level: str  # "low" | "medium" | "high"
    composite_score: float
    hs_code: Optional[str]  # resolved from description, given directly, or None
    factors: list[RiskFactor]


def _screening_factor(conn: sqlite3.Connection, party_name: str) -> RiskFactor:
    """Score a party name: real hit dominates, near-miss is moderate, clean is 0."""
    real_matches = screen_entity(conn, party_name)
    if real_matches:
        top = real_matches[0]
        return RiskFactor(
            "screening",
            _SCREENING_HIT,
            _WEIGHT_SCREENING,
            f"real sanctions match: {top.entity.name} ({top.score:.2f})",
        )

    near_matches = screen_entity(conn, party_name, threshold=_NEAR_MISS_THRESHOLD)
    if near_matches:
        top = near_matches[0]
        return RiskFactor(
            "screening",
            _SCREENING_NEAR_MISS,
            _WEIGHT_SCREENING,
            f"near-miss: {top.entity.name} ({top.score:.2f}, below the compliance threshold)",
        )

    return RiskFactor("screening", _SCREENING_CLEAN, _WEIGHT_SCREENING, "no sanctions match")


def _classification_factor(
    conn: sqlite3.Connection, description: Optional[str], hs_code: Optional[str]
) -> tuple[RiskFactor, Optional[str]]:
    """Score classification uncertainty; returns the factor and the resolved code."""
    if hs_code is not None:
        return (
            RiskFactor("classification", 0.0, _WEIGHT_CLASSIFICATION, "HS code given directly"),
            hs_code,
        )

    results = classify(conn, description, top_n=1)  # type: ignore[arg-type]
    if not results:
        return (
            RiskFactor(
                "classification",
                1.0,
                _WEIGHT_CLASSIFICATION,
                "no code shares a term with the description",
            ),
            None,
        )

    top = results[0]
    return (
        RiskFactor(
            "classification",
            1 - top.score,
            _WEIGHT_CLASSIFICATION,
            f"top match {top.hs_code.code} at {top.score:.2%} confidence",
        ),
        top.hs_code.code,
    )


def _duty_factor(
    conn: sqlite3.Connection,
    resolved_code: Optional[str],
    country_of_origin: str,
    customs_value: float,
) -> RiskFactor:
    """Score duty exposure: high/preferential rates and missing data raise risk."""
    if resolved_code is None:
        return RiskFactor("duty", 0.0, _WEIGHT_DUTY, "not assessed: no HS code available")

    try:
        result = calculate_duty(conn, resolved_code, country_of_origin, customs_value)
    except RateNotFoundError:
        return RiskFactor(
            "duty",
            _DUTY_MISSING_RATE_SCORE,
            _WEIGHT_DUTY,
            "no tariff rate on record for this code",
        )

    score = min(result.rate_percent / _DUTY_RATE_CEILING, 1.0)
    if result.rate_type == PREFERENTIAL:
        score = min(score + _DUTY_PREFERENTIAL_BUMP, 1.0)
    return RiskFactor(
        "duty", score, _WEIGHT_DUTY, f"{result.rate_type} rate {result.rate_percent}%"
    )


def _level_for(composite_score: float) -> str:
    if composite_score >= _LEVEL_HIGH:
        return "high"
    if composite_score >= _LEVEL_MEDIUM:
        return "medium"
    return "low"


def assess_shipment(
    conn: sqlite3.Connection,
    country_of_origin: str,
    party_name: str,
    customs_value: float,
    description: Optional[str] = None,
    hs_code: Optional[str] = None,
) -> RiskAssessment:
    """Assess a shipment's composite risk across screening, classification and duty.

    Exactly one of `description` or `hs_code` must be given: a description is
    classified internally to resolve a code, or the code can be supplied
    directly (in which case classification contributes no risk — there is no
    uncertainty to score).

    Args:
        conn: An open database connection.
        country_of_origin: ISO 3166-1 alpha-2 origin code.
        party_name: Person or organisation to screen.
        customs_value: Declared customs value.
        description: Free-text description of the goods, if the HS code isn't known.
        hs_code: The HS code directly, if already known.

    Returns:
        A RiskAssessment with the composite score, level, and each factor's
        contribution.

    Raises:
        InvalidQueryError: If neither or both of description/hs_code are given,
            or if any sub-factor's own input validation fails (e.g. a malformed
            HS code or country, via calculate_duty).
    """
    if (description is None) == (hs_code is None):
        raise InvalidQueryError("Provide exactly one of description or hs_code")

    screening = _screening_factor(conn, party_name)
    classification, resolved_code = _classification_factor(conn, description, hs_code)
    duty = _duty_factor(conn, resolved_code, country_of_origin, customs_value)

    composite = (
        screening.score * screening.weight
        + classification.score * classification.weight
        + duty.score * duty.weight
    )
    return RiskAssessment(
        level=_level_for(composite),
        composite_score=composite,
        hs_code=resolved_code,
        factors=[screening, classification, duty],
    )

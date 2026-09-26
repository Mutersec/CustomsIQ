"""Customs duty calculation against the stored tariff rates."""

import logging
import sqlite3
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple, Optional

from src.customsiq.database import ALL_ORIGINS, fetch_rates_for_code
from src.customsiq.exceptions import InvalidQueryError, RateNotFoundError
from src.customsiq.models import TariffRate
from src.utils.validators import validate_cn_code, validate_country_code

logger = logging.getLogger(__name__)

PREFERENTIAL = "preferential"
STANDARD = "standard"

_CENTS = Decimal("0.01")


class DutyCalculation(NamedTuple):
    """The duty owed on a consignment, and the reasoning behind the rate.

    `explanation` is the rendered English sentence, kept for the CLI and for
    API clients that just want text. `explanation_key` and `explanation_params`
    are the same reasoning in structured form, so a UI can render it in the
    viewer's own language instead — see the localization note in the README.
    """

    hs_code: str
    country_of_origin: str
    customs_value: Decimal
    rate_percent: float
    rate_type: str
    trade_agreement: Optional[str]
    duty_amount: Decimal
    total_payable: Decimal
    explanation: str
    explanation_key: str
    explanation_params: dict


def _applicable(rates: list[TariffRate], as_of: date) -> list[TariffRate]:
    """Drop rates that have not entered into force yet, newest first."""
    in_force = [rate for rate in rates if rate.valid_from <= as_of.isoformat()]
    return sorted(in_force, key=lambda rate: rate.valid_from, reverse=True)


def select_rate(
    rates: list[TariffRate], country_of_origin: str, as_of: Optional[date] = None
) -> Optional[TariffRate]:
    """Pick the rate that applies to an origin: preferential first, else standard.

    Args:
        rates: Every stored rate for one HS code.
        country_of_origin: ISO 3166-1 alpha-2 origin code.
        as_of: Date to judge `valid_from` against. Defaults to today.

    Returns:
        The applicable rate, or None if the code has no rate in force.
    """
    in_force = _applicable(rates, as_of or date.today())
    origin = country_of_origin.upper()

    preferential = [
        rate
        for rate in in_force
        if rate.rate_type == PREFERENTIAL and rate.country_of_origin.upper() == origin
    ]
    if preferential:
        return preferential[0]

    standard = [
        rate
        for rate in in_force
        if rate.rate_type == STANDARD and rate.country_of_origin.upper() == ALL_ORIGINS
    ]
    return standard[0] if standard else None


def _explain(rate: TariffRate, origin: str) -> tuple[str, str, dict]:
    """Describe why this rate was applied, in English and in structured form.

    Returns (english_sentence, translation_key, params). Both come off the
    same inputs in the same branch, so the rendered text and the structured
    form can't drift apart. The frontend renders `params` through its own
    per-language template; the sentence stays for the CLI and API clients.
    """
    if rate.rate_type == PREFERENTIAL:
        return (
            (
                f"Preferential rate of {rate.rate_percent:g}% applied under the "
                f"{rate.trade_agreement}, for which origin {origin} qualifies."
            ),
            PREFERENTIAL,
            {
                "rate": rate.rate_percent,
                "agreement": rate.trade_agreement,
                "origin": origin,
            },
        )
    return (
        (
            f"Standard MFN rate of {rate.rate_percent:g}% applied — no preferential "
            f"agreement covers origin {origin} for this code."
        ),
        STANDARD,
        {"rate": rate.rate_percent, "origin": origin},
    )


def calculate_duty(
    conn: sqlite3.Connection,
    hs_code: str,
    country_of_origin: str,
    customs_value: float,
    as_of: Optional[date] = None,
) -> DutyCalculation:
    """Work out the customs duty owed on a consignment.

    A preferential rate wins whenever the origin qualifies for one; otherwise
    the standard MFN rate applies. The result carries the reasoning, so the
    figure can be shown to an auditor rather than taken on trust.

    Money is handled in `Decimal` internally and rounded to two decimal places,
    since binary floats are the wrong tool for a legally consequential amount.

    Args:
        conn: An open database connection.
        hs_code: CN-8 or TARIC-10 code of the goods.
        country_of_origin: ISO 3166-1 alpha-2 origin code.
        customs_value: Declared customs value; zero is valid, negative is not.
        as_of: Date to judge rate validity against. Defaults to today.

    Returns:
        The duty owed, the rate applied, and why it applied.

    Raises:
        InvalidQueryError: If the code, origin or value is unusable.
        RateNotFoundError: If no rate is on record for the code.
    """
    if not validate_cn_code(hs_code):
        raise InvalidQueryError(f"{hs_code!r} is not a valid CN-8 or TARIC-10 code.")
    if not validate_country_code(country_of_origin):
        raise InvalidQueryError(
            f"{country_of_origin!r} is not a valid ISO 3166-1 alpha-2 country code."
        )
    if customs_value < 0:
        raise InvalidQueryError("Customs value must not be negative.")

    rates = fetch_rates_for_code(conn, hs_code)
    if not rates:
        raise RateNotFoundError(f"No tariff rate on record for HS code {hs_code}.")

    rate = select_rate(rates, country_of_origin, as_of)
    if rate is None:
        raise RateNotFoundError(f"No tariff rate in force for HS code {hs_code}.")

    origin = country_of_origin.upper()
    value = Decimal(str(customs_value))
    duty = (value * Decimal(str(rate.rate_percent)) / Decimal(100)).quantize(
        _CENTS, rounding=ROUND_HALF_UP
    )

    logger.info(
        "duty for %s from %s: %s%% (%s) on %s = %s",
        hs_code,
        origin,
        rate.rate_percent,
        rate.rate_type,
        value,
        duty,
    )
    explanation, explanation_key, explanation_params = _explain(rate, origin)
    return DutyCalculation(
        hs_code=hs_code,
        country_of_origin=origin,
        customs_value=value.quantize(_CENTS, rounding=ROUND_HALF_UP),
        rate_percent=rate.rate_percent,
        rate_type=rate.rate_type,
        trade_agreement=rate.trade_agreement,
        duty_amount=duty,
        total_payable=(value + duty).quantize(_CENTS, rounding=ROUND_HALF_UP),
        explanation=explanation,
        explanation_key=explanation_key,
        explanation_params=explanation_params,
    )

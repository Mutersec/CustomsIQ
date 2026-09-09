"""Command-line interface for CN code search, sanctions screening and duty calculation."""

import logging
import sqlite3

from src.customsiq.config import settings
from src.customsiq.database import get_connection, seed
from src.customsiq.embargo_screener import screen_entity
from src.customsiq.exceptions import InvalidQueryError, RateNotFoundError
from src.customsiq.logging_config import configure_logging
from src.customsiq.search import search
from src.customsiq.tariff_calculator import calculate_duty

logger = logging.getLogger(__name__)

SCREEN_COMMAND = "screen "
DUTY_COMMAND = "duty "


def _run_search(conn: sqlite3.Connection, query: str) -> None:
    """Search CN codes for a product description and log the ranked results."""
    results = search(conn, query)
    if not results:
        logger.info("No matches found.")
        return
    for rank, result in enumerate(results, start=1):
        logger.info(
            "%d. %s  (%.0f%%)  %s  [%s]",
            rank,
            result.hs_code.code,
            result.score * 100,
            result.hs_code.description,
            result.hs_code.category,
        )


def _run_screening(conn: sqlite3.Connection, name: str) -> None:
    """Screen a name against the sanctions list and log every hit."""
    matches = screen_entity(conn, name)
    if not matches:
        logger.info("No sanctions match for %r.", name)
        return
    logger.warning("%d potential sanctions match(es) for %r:", len(matches), name)
    for rank, match in enumerate(matches, start=1):
        logger.info(
            "%d. %s  (%.0f%%)  [%s]  %s  listed %s",
            rank,
            match.entity.name,
            match.score * 100,
            match.entity.country,
            match.entity.list_source,
            match.entity.date_added,
        )


def _run_duty(conn: sqlite3.Connection, arguments: str) -> None:
    """Calculate duty from a 'duty <hs_code> <country> <value>' command."""
    parts = arguments.split()
    if len(parts) != 3:
        logger.warning("Usage: duty <hs_code> <country_of_origin> <customs_value>")
        return
    hs_code, country, raw_value = parts
    try:
        value = float(raw_value)
    except ValueError:
        logger.warning("%r is not a number.", raw_value)
        return

    result = calculate_duty(conn, hs_code, country, value)
    logger.info(
        "Duty on %s from %s: %s (%.2f%% %s)",
        result.hs_code,
        result.country_of_origin,
        result.duty_amount,
        result.rate_percent,
        result.rate_type,
    )
    logger.info("  %s", result.explanation)
    logger.info(
        "  Customs value %s + duty %s = %s",
        result.customs_value,
        result.duty_amount,
        result.total_payable,
    )


def run(db_path: str = settings.database_path) -> None:
    """Start an interactive loop offering search, screening and duty calculation.

    Args:
        db_path: Path to the SQLite database file to use.
    """
    configure_logging()
    conn = get_connection(db_path)
    seed(conn)
    logger.info("CustomsIQ (type 'quit' to exit)")
    logger.info("Enter a product description to search CN codes,")
    logger.info("'screen <name>' to run a sanctions check,")
    logger.info("or 'duty <hs_code> <country> <value>' to calculate customs duty.")
    while True:
        entry = input("\n> ").strip()
        if entry.lower() in {"quit", "exit"}:
            break
        if not entry:
            continue
        try:
            if entry.lower().startswith(SCREEN_COMMAND):
                _run_screening(conn, entry[len(SCREEN_COMMAND) :].strip())
            elif entry.lower().startswith(DUTY_COMMAND):
                _run_duty(conn, entry[len(DUTY_COMMAND) :].strip())
            else:
                _run_search(conn, entry)
        except (InvalidQueryError, RateNotFoundError) as exc:
            logger.warning("%s", exc)


if __name__ == "__main__":
    run()

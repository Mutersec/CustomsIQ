"""SQLite persistence layer for HS (GTİP) code records."""

import logging
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Union

from src.customsiq.exceptions import HSCodeNotFoundError
from src.customsiq.models import HSCode

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS hs_codes (
    code TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    category TEXT NOT NULL
);
"""

# Sample/demo data spanning several trade categories.
SAMPLE_DATA: list[HSCode] = [
    HSCode("8517120000", "Mobile phones and smartphones", "Electronics"),
    HSCode("8471300000", "Portable automatic data processing machines (laptops)", "Electronics"),
    HSCode("8528721000", "Color television receivers", "Electronics"),
    HSCode("8544421000", "USB cables and data cables", "Electronics"),
    HSCode("8507600000", "Lithium-ion batteries", "Electronics"),
    HSCode("6109100000", "Cotton T-shirts, knitted", "Textile"),
    HSCode("6203420000", "Men's cotton trousers", "Textile"),
    HSCode("6204620000", "Women's cotton trousers", "Textile"),
    HSCode("6110200000", "Cotton pullovers and sweaters", "Textile"),
    HSCode("6402990000", "Footwear with rubber or plastic soles", "Textile"),
    HSCode("0901210000", "Roasted coffee, not decaffeinated", "Food"),
    HSCode("1806320000", "Chocolate blocks, not filled", "Food"),
    HSCode("2009110000", "Frozen orange juice", "Food"),
    HSCode("0406100000", "Fresh cheese", "Food"),
    HSCode("1905310000", "Sweet biscuits", "Food"),
    HSCode("3004900000", "Medicaments for therapeutic use", "Pharmaceutical"),
    HSCode("4011100000", "New pneumatic tires for cars", "Automotive"),
    HSCode("9403300000", "Wooden office furniture", "Furniture"),
    HSCode("3926909700", "Plastic household articles", "Plastics"),
    HSCode("7326909800", "Miscellaneous articles of iron or steel", "Metals"),
]


def get_connection(db_path: Union[str, Path] = ":memory:") -> sqlite3.Connection:
    """Open a SQLite connection and ensure the schema exists.

    Args:
        db_path: Path to the SQLite file, or ":memory:" for an in-memory database.

    Returns:
        An open connection with the hs_codes table ready.
    """
    # ponytail: single shared connection, check_same_thread=False so FastAPI's
    # threadpool can use it; move to a connection pool if concurrent writes appear.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def seed(conn: sqlite3.Connection, records: Iterable[HSCode] = SAMPLE_DATA) -> None:
    """Insert sample HS code records if the table is currently empty.

    Args:
        conn: An open database connection.
        records: HS code records to insert.
    """
    if conn.execute("SELECT 1 FROM hs_codes LIMIT 1").fetchone():
        logger.debug("hs_codes already populated, skipping seed")
        return
    rows = [(r.code, r.description, r.category) for r in records]
    conn.executemany("INSERT INTO hs_codes (code, description, category) VALUES (?, ?, ?)", rows)
    conn.commit()
    logger.info("seeded %d HS code records", len(rows))


def fetch_all(conn: sqlite3.Connection) -> list[HSCode]:
    """Return every HS code record in the database.

    Args:
        conn: An open database connection.

    Returns:
        All stored HSCode records.
    """
    rows = conn.execute("SELECT code, description, category FROM hs_codes").fetchall()
    return [HSCode(*row) for row in rows]


def get_by_code(conn: sqlite3.Connection, code: str) -> HSCode:
    """Look up a single HS code record by its exact code.

    Args:
        conn: An open database connection.
        code: The exact HS/GTİP code to look up.

    Returns:
        The matching HSCode record.

    Raises:
        HSCodeNotFoundError: If no record has that exact code.
    """
    row = conn.execute(
        "SELECT code, description, category FROM hs_codes WHERE code = ?", (code,)
    ).fetchone()
    if row is None:
        raise HSCodeNotFoundError(f"No HS code found for '{code}'")
    return HSCode(*row)

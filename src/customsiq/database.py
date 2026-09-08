"""SQLite persistence layer for HS/CN code and sanctions records."""

import logging
import sqlite3
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Union

from src.customsiq.exceptions import HSCodeNotFoundError
from src.customsiq.models import HSCode, SanctionedEntity

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS hs_codes (
    code TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    category TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sanctioned_entities (
    name TEXT PRIMARY KEY,
    country TEXT NOT NULL,
    list_source TEXT NOT NULL,
    date_added TEXT NOT NULL
);
"""

# Sample/demo data spanning several trade categories. Codes follow the EU
# Combined Nomenclature (TARIC-10) format; production data comes from the EU
# TARIC database (https://ec.europa.eu/taxation_customs/dds2/taric).
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


_EU_CFSL = "EU Consolidated Financial Sanctions List"
_EU_DUAL_USE = "EU Dual-Use Export Control Watchlist"

# ---------------------------------------------------------------------------
# FICTIONAL DEMO DATA — every name below is invented for development and
# testing. None of these entities are real, and none correspond to any real
# sanctioned person or organisation. Never use this list for actual screening:
# production data must come from the EU Consolidated Financial Sanctions List.
# Persons are stored surname-first, the way real sanctions lists publish them.
# ---------------------------------------------------------------------------
SANCTIONED_ENTITIES: list[SanctionedEntity] = [
    SanctionedEntity("Northwind Maritime Holdings Ltd", "CY", _EU_CFSL, "2023-04-12"),
    SanctionedEntity("Zenith Petrochemical Trading FZE", "AE", _EU_CFSL, "2022-11-30"),
    SanctionedEntity("Aurora Precision Components GmbH", "DE", _EU_DUAL_USE, "2024-02-19"),
    SanctionedEntity("Meridian Cargo Logistics DOO", "RS", _EU_CFSL, "2023-09-05"),
    SanctionedEntity("Blackvale Shipping Agency Ltd", "MT", _EU_CFSL, "2022-06-21"),
    SanctionedEntity("Kestrel Industrial Supply SARL", "LU", _EU_DUAL_USE, "2024-07-08"),
    SanctionedEntity("Solenne Chemical Works SA", "CH", _EU_CFSL, "2023-01-17"),
    SanctionedEntity("Ironclad Machine Tools Kft", "HU", _EU_DUAL_USE, "2025-03-24"),
    SanctionedEntity("Vantage Aero Spares BV", "NL", _EU_DUAL_USE, "2024-10-02"),
    SanctionedEntity("Halcyon Marine Services Ltd", "LR", _EU_CFSL, "2022-08-14"),
    SanctionedEntity("Redstone Metallurgical Trading LLC", "KZ", _EU_CFSL, "2023-12-01"),
    SanctionedEntity("Pallas Electronics Import OOO", "BY", _EU_DUAL_USE, "2024-05-16"),
    SanctionedEntity("Cobalt Line Freight Forwarding SL", "ES", _EU_CFSL, "2025-01-09"),
    SanctionedEntity("Tidewater Bunkering Pte Ltd", "SG", _EU_CFSL, "2023-07-27"),
    SanctionedEntity("Voronin-Teske, Aleksandr", "PA", _EU_CFSL, "2022-10-11"),
    SanctionedEntity("Ivankovic-Radu, Mirela", "RS", _EU_CFSL, "2024-03-06"),
    SanctionedEntity("van Aalsburg, Hendrik", "NL", _EU_DUAL_USE, "2023-05-30"),
    SanctionedEntity("Petrovski-Lund, Dragan", "MK", _EU_CFSL, "2025-02-13"),
]


def get_connection(db_path: Union[str, Path] = ":memory:") -> sqlite3.Connection:
    """Open a SQLite connection and ensure the schema exists.

    Args:
        db_path: Path to the SQLite file, or ":memory:" for an in-memory database.

    Returns:
        An open connection with the hs_codes and sanctioned_entities tables ready.
    """
    # ponytail: single shared connection, check_same_thread=False so FastAPI's
    # threadpool can use it; move to a connection pool if concurrent writes appear.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _seed_if_empty(
    conn: sqlite3.Connection, table: str, columns: Sequence[str], rows: list[tuple]
) -> None:
    """Insert rows into a table, but only when that table is currently empty.

    `table` and `columns` are module-internal literals, never user input; the
    row values themselves are always passed as bound parameters.
    """
    if conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
        logger.debug("%s already populated, skipping seed", table)
        return
    placeholders = ", ".join("?" for _ in columns)
    conn.executemany(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", rows)
    conn.commit()
    logger.info("seeded %d rows into %s", len(rows), table)


def seed(
    conn: sqlite3.Connection,
    records: Iterable[HSCode] = SAMPLE_DATA,
    entities: Iterable[SanctionedEntity] = SANCTIONED_ENTITIES,
) -> None:
    """Insert sample data into any of the tables that are currently empty.

    Args:
        conn: An open database connection.
        records: HS code records to insert.
        entities: Sanctioned entity records to insert.
    """
    _seed_if_empty(
        conn,
        "hs_codes",
        ("code", "description", "category"),
        [(r.code, r.description, r.category) for r in records],
    )
    _seed_if_empty(
        conn,
        "sanctioned_entities",
        ("name", "country", "list_source", "date_added"),
        [(e.name, e.country, e.list_source, e.date_added) for e in entities],
    )


def upsert_hs_codes(conn: sqlite3.Connection, records: Iterable[HSCode]) -> int:
    """Insert HS code records, updating any whose code is already stored.

    Used by the CN import tool (scripts/import_cn_codes.py) so re-running an
    import refreshes existing rows instead of duplicating or failing on them.

    Args:
        conn: An open database connection.
        records: HS code records to write.

    Returns:
        The number of rows written.
    """
    rows = [(r.code, r.description, r.category) for r in records]
    conn.executemany(
        "INSERT INTO hs_codes (code, description, category) VALUES (?, ?, ?) "
        "ON CONFLICT(code) DO UPDATE SET "
        "description = excluded.description, category = excluded.category",
        rows,
    )
    conn.commit()
    return len(rows)


def fetch_all(conn: sqlite3.Connection) -> list[HSCode]:
    """Return every HS code record in the database.

    Args:
        conn: An open database connection.

    Returns:
        All stored HSCode records.
    """
    rows = conn.execute("SELECT code, description, category FROM hs_codes").fetchall()
    return [HSCode(*row) for row in rows]


def fetch_all_entities(conn: sqlite3.Connection) -> list[SanctionedEntity]:
    """Return every sanctioned entity record in the database.

    Args:
        conn: An open database connection.

    Returns:
        All stored SanctionedEntity records.
    """
    rows = conn.execute(
        "SELECT name, country, list_source, date_added FROM sanctioned_entities"
    ).fetchall()
    return [SanctionedEntity(*row) for row in rows]


def get_by_code(conn: sqlite3.Connection, code: str) -> HSCode:
    """Look up a single HS code record by its exact code.

    Args:
        conn: An open database connection.
        code: The exact CN/TARIC code to look up.

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

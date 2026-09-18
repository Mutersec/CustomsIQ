"""SQLite persistence layer for HS/CN codes, sanctions records and tariff rates."""

import logging
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple, Optional, Union

from src.customsiq.exceptions import HSCodeNotFoundError
from src.customsiq.models import (
    HSCode,
    HSCodeVersion,
    ImportRun,
    ReviewDecision,
    SanctionedEntity,
    TariffRate,
)

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

CREATE TABLE IF NOT EXISTS tariff_rates (
    hs_code TEXT NOT NULL,
    country_of_origin TEXT NOT NULL,
    rate_type TEXT NOT NULL,
    rate_percent REAL NOT NULL,
    trade_agreement TEXT,
    valid_from TEXT NOT NULL,
    PRIMARY KEY (hs_code, country_of_origin, valid_from)
);

CREATE TABLE IF NOT EXISTS review_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_type TEXT NOT NULL,
    subject_reference TEXT NOT NULL,
    decision TEXT NOT NULL,
    reviewer_name TEXT NOT NULL,
    comment TEXT,
    reviewed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hs_code_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_to TEXT,
    version_label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cn_code_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_label TEXT NOT NULL,
    source_description TEXT,
    imported_at TEXT NOT NULL,
    row_count INTEGER NOT NULL
);
"""

# Sentinel origin for a standard (MFN) rate, which applies whatever the origin.
ALL_ORIGINS = "ALL"

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


_SOLVIA = "EU-Solvia Free Trade Agreement"
_MERIDIAN = "EU-Meridian Economic Partnership"

# ---------------------------------------------------------------------------
# FICTIONAL DEMO DATA — the duty rates below are illustrative and the two trade
# agreements are invented. Real duty rates and preferential origins come from
# the EU TARIC database; never use these figures for an actual declaration.
# Standard (MFN) rates use ALL_ORIGINS, since they apply whatever the origin.
# ---------------------------------------------------------------------------
TARIFF_RATES: list[TariffRate] = [
    TariffRate("8517120000", ALL_ORIGINS, "standard", 0.0, None, "2024-01-01"),
    TariffRate("8528721000", ALL_ORIGINS, "standard", 14.0, None, "2024-01-01"),
    TariffRate("8544421000", ALL_ORIGINS, "standard", 3.3, None, "2024-01-01"),
    TariffRate("8507600000", ALL_ORIGINS, "standard", 2.7, None, "2024-01-01"),
    TariffRate("6109100000", ALL_ORIGINS, "standard", 12.0, None, "2024-01-01"),
    TariffRate("6203420000", ALL_ORIGINS, "standard", 12.0, None, "2024-01-01"),
    TariffRate("6402990000", ALL_ORIGINS, "standard", 16.9, None, "2024-01-01"),
    TariffRate("0901210000", ALL_ORIGINS, "standard", 7.5, None, "2024-01-01"),
    TariffRate("1806320000", ALL_ORIGINS, "standard", 8.3, None, "2024-01-01"),
    TariffRate("4011100000", ALL_ORIGINS, "standard", 4.5, None, "2024-01-01"),
    TariffRate("9403300000", ALL_ORIGINS, "standard", 0.0, None, "2024-01-01"),
    TariffRate("7326909800", ALL_ORIGINS, "standard", 2.7, None, "2024-01-01"),
    TariffRate("6109100000", "NO", "preferential", 0.0, _SOLVIA, "2024-01-01"),
    TariffRate("6203420000", "NO", "preferential", 4.0, _SOLVIA, "2024-01-01"),
    TariffRate("8528721000", "CH", "preferential", 7.0, _SOLVIA, "2024-01-01"),
    TariffRate("8544421000", "JP", "preferential", 0.0, _MERIDIAN, "2024-01-01"),
    TariffRate("4011100000", "KR", "preferential", 2.0, _MERIDIAN, "2024-01-01"),
    # Not yet in force: exercises the valid_from filter, which must ignore it.
    TariffRate("6402990000", "JP", "preferential", 8.5, _MERIDIAN, "2030-01-01"),
]


def get_connection(db_path: Union[str, Path] = ":memory:") -> sqlite3.Connection:
    """Open a SQLite connection and ensure the schema exists.

    Args:
        db_path: Path to the SQLite file, or ":memory:" for an in-memory database.

    Returns:
        An open connection with all three tables ready.
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
    rates: Iterable[TariffRate] = TARIFF_RATES,
) -> None:
    """Insert sample data into any of the tables that are currently empty.

    Args:
        conn: An open database connection.
        records: HS code records to insert.
        entities: Sanctioned entity records to insert.
        rates: Tariff rate records to insert.
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
    _seed_if_empty(
        conn,
        "tariff_rates",
        (
            "hs_code",
            "country_of_origin",
            "rate_type",
            "rate_percent",
            "trade_agreement",
            "valid_from",
        ),
        [
            (
                t.hs_code,
                t.country_of_origin,
                t.rate_type,
                t.rate_percent,
                t.trade_agreement,
                t.valid_from,
            )
            for t in rates
        ],
    )


def upsert_hs_codes(conn: sqlite3.Connection, records: Iterable[HSCode]) -> int:
    """Insert HS code records, updating any whose code is already stored.

    Low-level primitive: writes only the current value, no history. New code
    should prefer `upsert_hs_codes_with_history`, which wraps this and also
    records the SCD Type 2 version trail; this stays for that wrapper to call.

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


def fetch_rates_for_code(conn: sqlite3.Connection, hs_code: str) -> list[TariffRate]:
    """Return every stored tariff rate for one HS code.

    Args:
        conn: An open database connection.
        hs_code: The CN/TARIC code to look up rates for.

    Returns:
        All matching TariffRate records, in no particular order.
    """
    rows = conn.execute(
        "SELECT hs_code, country_of_origin, rate_type, rate_percent, trade_agreement, valid_from "
        "FROM tariff_rates WHERE hs_code = ?",
        (hs_code,),
    ).fetchall()
    return [TariffRate(*row) for row in rows]


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


def insert_review_decision(
    conn: sqlite3.Connection,
    subject_type: str,
    subject_reference: str,
    decision: str,
    reviewer_name: str,
    comment: Optional[str],
    reviewed_at: str,
) -> int:
    """Append one review decision. Audit rows are never updated or deleted.

    Args:
        conn: An open database connection.
        subject_type: "classification" | "screening" | "duty".
        subject_reference: Deterministic hash identifying the reviewed input.
        decision: "approved" | "rejected" | "flagged".
        reviewer_name: Free text identifying who reviewed it.
        comment: Optional free-text note.
        reviewed_at: ISO 8601 timestamp.

    Returns:
        The autoincrement id of the new row.
    """
    cursor = conn.execute(
        "INSERT INTO review_decisions "
        "(subject_type, subject_reference, decision, reviewer_name, comment, reviewed_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (subject_type, subject_reference, decision, reviewer_name, comment, reviewed_at),
    )
    conn.commit()
    assert cursor.lastrowid is not None  # always set after a successful INSERT
    return cursor.lastrowid


def fetch_review_decisions(
    conn: sqlite3.Connection,
    subject_type: Optional[str] = None,
    subject_reference: Optional[str] = None,
    limit: int = 50,
) -> list[ReviewDecision]:
    """Return review decisions, most recently reviewed first.

    Args:
        conn: An open database connection.
        subject_type: Restrict to this subject type, if given.
        subject_reference: Restrict to this subject reference, if given.
        limit: Maximum number of rows to return.

    Returns:
        Matching ReviewDecision records, newest first.
    """
    clauses = []
    params: list = []
    if subject_type is not None:
        clauses.append("subject_type = ?")
        params.append(subject_type)
    if subject_reference is not None:
        clauses.append("subject_reference = ?")
        params.append(subject_reference)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = conn.execute(
        "SELECT id, subject_type, subject_reference, decision, reviewer_name, comment, reviewed_at "
        f"FROM review_decisions {where} ORDER BY reviewed_at DESC, id DESC LIMIT ?",
        params,
    ).fetchall()
    return [ReviewDecision(*row) for row in rows]


class ImportStats(NamedTuple):
    """Counts of what one upsert_hs_codes_with_history() call actually changed."""

    new_count: int
    changed_count: int
    unchanged_count: int


def upsert_hs_codes_with_history(
    conn: sqlite3.Connection, records: Iterable[HSCode], version_label: str
) -> ImportStats:
    """Upsert HS codes into hs_codes, and version any new or changed ones.

    hs_codes itself ends up exactly as `upsert_hs_codes` would leave it — one
    current row per code. Separately, for every code whose description or
    category is new or different from what's currently stored, the previous
    open hs_code_history row (if any) is closed and a new one opened. A code
    reimported with identical data gets no new history row.

    Args:
        conn: An open database connection.
        records: HS code records to write.
        version_label: Label identifying this import run (e.g. "CN2026"),
            stamped onto any history rows this call creates.

    Returns:
        How many codes were new, changed, or unchanged by this call.
    """
    records = list(records)
    existing = {r.code: r for r in fetch_all(conn)}

    new_count = changed_count = unchanged_count = 0
    to_version: list[HSCode] = []
    for record in records:
        prior = existing.get(record.code)
        if prior is None:
            new_count += 1
            to_version.append(record)
        elif prior != record:
            changed_count += 1
            to_version.append(record)
        else:
            unchanged_count += 1

    upsert_hs_codes(conn, records)

    if to_version:
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany(
            "UPDATE hs_code_history SET valid_to = ? WHERE code = ? AND valid_to IS NULL",
            [(now, r.code) for r in to_version],
        )
        conn.executemany(
            "INSERT INTO hs_code_history "
            "(code, description, category, valid_from, valid_to, version_label) "
            "VALUES (?, ?, ?, ?, NULL, ?)",
            [(r.code, r.description, r.category, now, version_label) for r in to_version],
        )
        conn.commit()

    return ImportStats(new_count, changed_count, unchanged_count)


def record_cn_import(
    conn: sqlite3.Connection,
    version_label: str,
    source_description: Optional[str],
    imported_at: str,
    row_count: int,
) -> int:
    """Log one completed CN import run. Called once per run, regardless of changes.

    Args:
        conn: An open database connection.
        version_label: Label identifying this import run (e.g. "CN2026").
        source_description: The imported file's name, if known.
        imported_at: ISO 8601 timestamp the run completed.
        row_count: Number of leaf CN code records processed in this run.

    Returns:
        The autoincrement id of the new row.
    """
    cursor = conn.execute(
        "INSERT INTO cn_code_versions (version_label, source_description, imported_at, row_count) "
        "VALUES (?, ?, ?, ?)",
        (version_label, source_description, imported_at, row_count),
    )
    conn.commit()
    assert cursor.lastrowid is not None  # always set after a successful INSERT
    return cursor.lastrowid


def fetch_hs_code_history(conn: sqlite3.Connection, code: str) -> list[HSCodeVersion]:
    """Return one HS code's version timeline, oldest first.

    Args:
        conn: An open database connection.
        code: The CN/TARIC code to look up history for.

    Returns:
        Matching HSCodeVersion records, oldest first (empty if the code was
        never touched by a versioned import).
    """
    rows = conn.execute(
        "SELECT id, code, description, category, valid_from, valid_to, version_label "
        "FROM hs_code_history WHERE code = ? ORDER BY valid_from ASC",
        (code,),
    ).fetchall()
    return [HSCodeVersion(*row) for row in rows]


def fetch_cn_import_runs(conn: sqlite3.Connection, limit: int = 50) -> list[ImportRun]:
    """Return CN import runs, most recently imported first.

    Args:
        conn: An open database connection.
        limit: Maximum number of runs to return.

    Returns:
        Matching ImportRun records, newest first.
    """
    rows = conn.execute(
        "SELECT id, version_label, source_description, imported_at, row_count "
        "FROM cn_code_versions ORDER BY imported_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [ImportRun(*row) for row in rows]


def fetch_all_rates(conn: sqlite3.Connection) -> list[TariffRate]:
    """Return every tariff rate record in the database.

    Args:
        conn: An open database connection.

    Returns:
        All stored TariffRate records.
    """
    rows = conn.execute(
        "SELECT hs_code, country_of_origin, rate_type, rate_percent, trade_agreement, valid_from "
        "FROM tariff_rates"
    ).fetchall()
    return [TariffRate(*row) for row in rows]


def count_versioned_codes(conn: sqlite3.Connection) -> int:
    """Return how many HS codes have more than one recorded history version.

    Args:
        conn: An open database connection.

    Returns:
        The number of distinct codes that have actually changed over time.
    """
    row = conn.execute(
        "SELECT COUNT(*) FROM ("
        "SELECT code FROM hs_code_history GROUP BY code HAVING COUNT(*) > 1"
        ")"
    ).fetchone()
    return row[0]


def count_history_rows_by_version_label(conn: sqlite3.Connection) -> dict[str, int]:
    """Return how many hs_code_history rows each import run produced.

    That count is exactly how many codes were new or changed in that run,
    since unchanged codes never get a history row — see
    upsert_hs_codes_with_history.

    Args:
        conn: An open database connection.

    Returns:
        {version_label: row count}, for every version_label seen in the history table.
    """
    rows = conn.execute(
        "SELECT version_label, COUNT(*) FROM hs_code_history GROUP BY version_label"
    ).fetchall()
    return dict(rows)

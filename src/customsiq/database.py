"""Persistence layer for HS/CN codes, sanctions records and tariff rates.

SQLite is the default and the backend every test runs against. PostgreSQL is
an opt-in alternative, selected by handing `get_connection` a `postgresql://`
URL instead of a file path (see `src/customsiq/config.py` for precedence and
`src/customsiq/pg_adapter.py` for the dialect differences). Every statement
below is written once and shared by both backends.
"""

import csv
import logging
import sqlite3
import threading
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple, Optional, Union, cast

from src.customsiq.exceptions import HSCodeNotFoundError
from src.customsiq.models import (
    HSCode,
    HSCodeVersion,
    ImportRun,
    ReviewDecision,
    SanctionedEntity,
    TariffRate,
    User,
)
from src.customsiq.pg_adapter import is_postgres_url

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

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_authorship (
    review_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL
);

-- A verified e-mail address (and, for Google sign-ups, the Google account id)
-- per user. A separate table rather than columns on users, because
-- CREATE TABLE IF NOT EXISTS never adds a column to an existing database.
-- Accounts created before e-mail verification existed (the demo accounts)
-- simply have no row here.
CREATE TABLE IF NOT EXISTS user_emails (
    user_id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    google_sub TEXT UNIQUE,
    verified_at TEXT NOT NULL
);

-- A sign-up waiting for its e-mail code. No users row exists until the code
-- is confirmed. Only a hash of the code is stored.
CREATE TABLE IF NOT EXISTS pending_signups (
    email TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    google_sub TEXT,
    code_hash TEXT NOT NULL,
    language TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    sent_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

-- What signed-in users did: searches, calculations, uploads, sign-ins. Read
-- only by the site owner's admin panel. `detail` is the query a user typed, or
-- a short summary — never a password, a code, or invoice content. `username`
-- is copied in so a row still reads after its account is deleted.
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT,
    result_count INTEGER,
    top_code TEXT,
    created_at TEXT NOT NULL
);

-- Star ratings and comments about the service itself, one per account. Not to
-- be confused with review_decisions (sign-offs on individual results). A
-- rating is shown to other users only once the site owner has approved it;
-- editing an approved one sends it back to 'pending'.
CREATE TABLE IF NOT EXISTS site_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    username TEXT NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT NOT NULL,
    company TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Supplementary German/French descriptions for hs_codes. A separate table,
-- not description_de/description_fr columns on hs_codes, for the same reason
-- hs_code_history is separate from hs_codes: CREATE TABLE IF NOT EXISTS never
-- adds a column to anyone's existing database file.
CREATE TABLE IF NOT EXISTS hs_code_translations (
    code TEXT NOT NULL,
    language TEXT NOT NULL,
    description TEXT NOT NULL,
    PRIMARY KEY (code, language)
);

-- The ancestor text a leaf's own description leaves out. Its own table rather
-- than a column on `hs_codes` so that an already-deployed database needs no
-- ALTER TABLE: `CREATE TABLE IF NOT EXISTS` covers a fresh install and an
-- existing one identically. English is a real row here, unlike in
-- `hs_code_translations` where English is the base `hs_codes.description`
-- column, because a leaf's *context* is missing in every language including
-- English. Only rows that need context have one — see `needs_context` in
-- scripts/import_cn_codes.py.
CREATE TABLE IF NOT EXISTS hs_code_contexts (
    code TEXT NOT NULL,
    language TEXT NOT NULL,
    context TEXT NOT NULL,
    PRIMARY KEY (code, language)
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
# FIXTURE DATA, NOT THE LIVE LIST — every name below is invented. None of them
# are real and none correspond to any real sanctioned person or organisation.
#
# These 18 stopped being the live sanctions list when the real OFAC SDN bundle
# landed: `load_bundled_sanctions` adds ~5,100 genuinely listed entities on top
# of these at startup, and that is what the running app screens against. What
# these are *for* now is the pinned worked examples — "Northwind Maritime" is
# the name behind the 0.6609 composite documented in all three READMEs, and it
# is the example in `matching.name_similarity`'s own docstring. Tests build a
# `:memory:` connection and call `seed()` alone, so they see exactly these 18
# and no real data, which is what keeps every pinned score reproducible and
# independent of whatever OFAC published this month.
#
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
    # Real, not illustrative: photovoltaic modules are duty-free under the WTO ITA.
    # HS-6 because the CN bundle lacks heading 8541; the code comes from the HS supplement.
    TariffRate("854143", ALL_ORIGINS, "standard", 0.0, None, "2024-01-01"),
    TariffRate("6109100000", "NO", "preferential", 0.0, _SOLVIA, "2024-01-01"),
    TariffRate("6203420000", "NO", "preferential", 4.0, _SOLVIA, "2024-01-01"),
    TariffRate("8528721000", "CH", "preferential", 7.0, _SOLVIA, "2024-01-01"),
    TariffRate("8544421000", "JP", "preferential", 0.0, _MERIDIAN, "2024-01-01"),
    TariffRate("4011100000", "KR", "preferential", 2.0, _MERIDIAN, "2024-01-01"),
    # Not yet in force: exercises the valid_from filter, which must ignore it.
    TariffRate("6402990000", "JP", "preferential", 8.5, _MERIDIAN, "2030-01-01"),
]


class _Result:
    """One statement's already-fetched rows, plus the cursor fields we use.

    Returned instead of a live `sqlite3.Cursor` so that nothing reads from the
    database after `_SerializedConnection` has released its lock — a cursor
    fetched later would be doing exactly the concurrent access the lock exists
    to prevent.
    """

    def __init__(self, rows: list, lastrowid: Optional[int], rowcount: int) -> None:
        self._rows = rows
        self.lastrowid = lastrowid
        self.rowcount = rowcount

    def fetchone(self) -> Any:
        """Return the first row, or None if the statement produced none."""
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list:
        """Return every row."""
        return self._rows


class _SerializedConnection:
    """A `sqlite3.Connection` that is actually safe to share between threads.

    The app keeps one connection for the process and FastAPI runs its sync
    routes in a threadpool, so several requests really do touch this object at
    once. That is not allowed: this machine's SQLite is built with
    `SQLITE_THREADSAFE=2` (multi-thread — one connection per thread), and
    Python reports `sqlite3.threadsafety == 1`, meaning threads may share the
    module but *not* a connection. Sharing one anyway produced exactly the
    symptoms you would predict — a garbled read ("Could not decode to UTF-8
    column 'username'") and then a segfault — once RBAC put a session lookup on
    every request and made concurrent access routine.

    So every statement runs under one lock, and its rows are fetched before the
    lock is released. Only the narrow surface this module uses is implemented,
    the same approach `pg_adapter.PgConnection` takes for Postgres.

    # ponytail: one global lock, which is the right size for a read-mostly
    # single-node demo — SQLite serializes writes anyway. A connection pool (or
    # a thread-local connection) is the upgrade path if read concurrency ever
    # actually matters.
    """

    dialect = "sqlite"

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._lock = threading.Lock()

    def _run(self, method: str, *args: Any) -> _Result:
        with self._lock:
            cursor = getattr(self._connection, method)(*args)
            return _Result(cursor.fetchall(), cursor.lastrowid, cursor.rowcount)

    def execute(self, sql: str, parameters: Sequence[Any] = ()) -> _Result:
        """Run one statement and return its already-fetched result."""
        return self._run("execute", sql, parameters)

    def executemany(self, sql: str, seq_of_parameters: Iterable[Sequence[Any]]) -> _Result:
        """Run one statement once per parameter row."""
        return self._run("executemany", sql, list(seq_of_parameters))

    def executescript(self, script: str) -> _Result:
        """Run a multi-statement script."""
        return self._run("executescript", script)

    def commit(self) -> None:
        """Commit the open transaction."""
        with self._lock:
            self._connection.commit()

    def close(self) -> None:
        """Close the underlying connection."""
        with self._lock:
            self._connection.close()


def get_connection(db_path: Union[str, Path] = ":memory:") -> sqlite3.Connection:
    """Open a database connection and ensure the schema exists.

    Args:
        db_path: Path to the SQLite file, ":memory:" for an in-memory database,
            or a `postgresql://` / `postgres://` URL for the opt-in Postgres
            backend.

    Returns:
        An open connection with every table in SCHEMA ready.
    """
    # Postgres is imported lazily and only on this branch, so the SQLite path
    # never touches the adapter and psycopg stays an optional extra.
    if isinstance(db_path, str) and is_postgres_url(db_path):
        from src.customsiq.pg_adapter import connect_postgres, to_postgres_ddl

        pg_conn = connect_postgres(db_path)
        pg_conn.executescript(to_postgres_ddl(SCHEMA))
        # The seven decision modules only pass `conn` straight back into this
        # module, so the duck-typed subset PgConnection implements is what
        # actually matters; the cast keeps their annotations untouched.
        return cast(sqlite3.Connection, pg_conn)

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.executescript(SCHEMA)
    conn.commit()
    # check_same_thread=False only silences Python's guard; it doesn't make the
    # connection safe to share. Hence the lock — see _SerializedConnection.
    return cast(sqlite3.Connection, _SerializedConnection(conn))


def _insert_returning_id(conn: sqlite3.Connection, sql: str, parameters: Sequence[Any]) -> int:
    """Run an INSERT and return the generated id, on either backend.

    SQLite reads it off the cursor afterwards; psycopg has no `lastrowid`, so
    Postgres asks for it in the statement itself with RETURNING.
    """
    if getattr(conn, "dialect", "sqlite") == "postgresql":
        row = conn.execute(f"{sql} RETURNING id", parameters).fetchone()
        return int(row[0])

    cursor = conn.execute(sql, parameters)
    conn.commit()
    assert cursor.lastrowid is not None  # always set after a successful INSERT
    return cursor.lastrowid


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


def upsert_translations(conn: sqlite3.Connection, rows: Sequence[tuple]) -> int:
    """Insert or update supplementary-language descriptions for HS codes.

    Args:
        conn: An open database connection.
        rows: (code, language, description) tuples, e.g. ("6109100000", "de", "...").

    Returns:
        The number of rows written.
    """
    rows = list(rows)
    conn.executemany(
        "INSERT INTO hs_code_translations (code, language, description) VALUES (?, ?, ?) "
        "ON CONFLICT(code, language) DO UPDATE SET description = excluded.description",
        rows,
    )
    conn.commit()
    return len(rows)


def fetch_translations(conn: sqlite3.Connection, code: str) -> dict:
    """Return every supplementary-language description recorded for one code.

    Args:
        conn: An open database connection.
        code: The HS code to look up. Not required to exist in hs_codes; a
            code with no translations simply has an empty result.

    Returns:
        {language: description}, e.g. {"de": "...", "fr": "..."}. Empty if
        no translations are recorded for this code.
    """
    rows = conn.execute(
        "SELECT language, description FROM hs_code_translations WHERE code = ?", (code,)
    ).fetchall()
    return {language: description for language, description in rows}


def fetch_all_translations(conn: sqlite3.Connection, language: Optional[str]) -> dict:
    """Return every stored description in one language, keyed by HS code.

    The bulk counterpart to `fetch_translations`, which answers for a single
    code. Matching needs the whole column at once: scoring a query against
    13.7k codes one `SELECT` at a time would dominate the search itself.

    English is the base `hs_codes.description` column rather than a
    translation, so asking for it — or for no language at all — is answered
    with an empty mapping rather than a query. That is what lets a caller
    pass the UI's language straight through without special-casing English.

    Args:
        conn: An open database connection.
        language: Language code to fetch, e.g. "de" or "fr". None or "en"
            returns {} without touching the database.

    Returns:
        {code: description} for every code that has text in `language`.
        Empty when the language isn't stored — which is what makes matching
        fall back to English-only rather than fail.
    """
    if language is None or language == "en":
        return {}
    rows = conn.execute(
        "SELECT code, description FROM hs_code_translations WHERE language = ?",
        (language,),
    ).fetchall()
    return {code: description for code, description in rows}


def upsert_contexts(conn: sqlite3.Connection, rows: Sequence[tuple]) -> int:
    """Insert or update the hierarchical context of HS codes.

    Args:
        conn: An open database connection.
        rows: (code, language, context) tuples, e.g.
            ("0106900090", "en", "Other live animals").

    Returns:
        The number of rows written.
    """
    rows = list(rows)
    conn.executemany(
        "INSERT INTO hs_code_contexts (code, language, context) VALUES (?, ?, ?) "
        "ON CONFLICT(code, language) DO UPDATE SET context = excluded.context",
        rows,
    )
    conn.commit()
    return len(rows)


def fetch_all_contexts(conn: sqlite3.Connection, language: Optional[str]) -> dict:
    """Return every stored hierarchical context in one language, keyed by HS code.

    The counterpart to `fetch_all_translations`, and read the same way: in bulk,
    because the classifier needs the whole column at once. Two differences from
    it, both deliberate:

    - `None` and "en" are answered from the table rather than with `{}`. A
      leaf's context is missing from its English description just as much as
      from its German one, so English has real rows here.
    - A code absent from the result has no *usable* context, not an untranslated
      one. Roughly half the corpus is absent by design: a leaf whose own text
      stands alone ("Hazelnuts") is deliberately left exactly as it is.

    Args:
        conn: An open database connection.
        language: Language code, e.g. "en", "de" or "fr". None means English.

    Returns:
        {code: context} for every code that has context in `language`. Empty for
        a corpus with no contexts stored at all — SAMPLE_DATA, for instance,
        which is what makes matching fall back to bare descriptions unchanged.
    """
    rows = conn.execute(
        "SELECT code, context FROM hs_code_contexts WHERE language = ?",
        (language or "en",),
    ).fetchall()
    return {code: context for code, context in rows}


def upsert_entities(conn: sqlite3.Connection, entities: Iterable[SanctionedEntity]) -> int:
    """Insert sanctioned-entity records, updating any whose name is already stored.

    The counterpart to `upsert_hs_codes`, and needed for the same reason: the
    only other way into this table is `_seed_if_empty`, which writes solely into
    an empty table and so can never add the real bundle on top of the fixture
    rows `seed()` has already written.

    Keyed on `name`, which is the table's primary key. A screening list has no
    better natural key — OFAC's own `ent_num` is not carried in this schema, and
    two records with the same name screen identically anyway.

    Args:
        conn: An open database connection.
        entities: Records to write.

    Returns:
        The number of rows written.
    """
    rows = [(e.name, e.country, e.list_source, e.date_added) for e in entities]
    conn.executemany(
        "INSERT INTO sanctioned_entities (name, country, list_source, date_added) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET "
        "country = excluded.country, list_source = excluded.list_source, "
        "date_added = excluded.date_added",
        rows,
    )
    conn.commit()
    return len(rows)


def load_bundled_sanctions(conn: sqlite3.Connection, path: Optional[Path] = None) -> int:
    """Load the committed OFAC SDN bundle into sanctioned_entities.

    The sanctions counterpart to `load_bundled_cn_nomenclature`, and deliberately
    identical in shape: the bundle (`data/sanctions_ofac_2026.csv`) is built once,
    offline, by `scripts/build_sanctions_bundle.py` from OFAC's published SDN
    List, then committed — so this needs no network access and survives a
    filesystem reset.

    Safe to call on every startup: `upsert_entities` is an idempotent
    ON CONFLICT DO UPDATE, not the empty-table-only `_seed_if_empty` gate that
    `seed()` uses. That gate would never fire here, because `seed()` has already
    written `SANCTIONED_ENTITIES` moments earlier. The bundle *adds* to those 18
    fixture rows rather than replacing them, which is what lets the pinned
    worked examples keep working while live screening runs against real data.

    Args:
        conn: An open database connection.
        path: Override for the bundle's location. Defaults to the file shipped
            alongside this module, resolved from the module rather than the
            working directory.

    Returns:
        The number of entities loaded.
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "data" / "sanctions_ofac_2026.csv"

    with path.open(newline="", encoding="utf-8") as handle:
        entities = [
            SanctionedEntity(row["name"], row["country"], row["list_source"], row["date_added"])
            for row in csv.DictReader(handle)
        ]

    count = upsert_entities(conn, entities)
    logger.info("loaded %d bundled sanctioned entities from %s", count, path)
    return count


def load_bundled_cn_nomenclature(conn: sqlite3.Connection, path: Optional[Path] = None) -> int:
    """Load the committed EU Combined Nomenclature bundle into hs_codes.

    The bundle (`data/cn_nomenclature_2026.csv`) is built once, offline, by
    `scripts/import_cn_codes.py build-bundle` from the official EU CIRCABC
    export, then committed to the repo — so this needs no network access and
    survives a filesystem reset, the same "process once, commit the result"
    approach `tests/fixtures/make_invoice_pdfs.py` uses for its fixtures.

    Safe to call on every startup: `upsert_hs_codes` is an idempotent
    ON CONFLICT DO UPDATE, not the empty-table-only `_seed_if_empty` gate
    `seed()` uses — that gate would never fire here, since `seed()` already
    populated `hs_codes` with `SAMPLE_DATA` moments earlier. The bundle adds
    to that 20-row set rather than replacing it; none of its codes collide
    with the mock ones (verified — they're different values entirely).

    Args:
        conn: An open database connection.
        path: Override for the bundle's location. Defaults to the file
            shipped alongside this module (resolved from this module's own
            location, not the working directory, the same reasoning
            `api.py`'s `_STATIC_DIR` already uses).

    Returns:
        The number of HS codes loaded (== the number of translation rows / 2).
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "data" / "cn_nomenclature_2026.csv"

    records = []
    translations: list[tuple] = []
    contexts: list[tuple] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            records.append(HSCode(row["cn_code"], row["description_en"], row["category"]))
            translations.append((row["cn_code"], "de", row["description_de"]))
            translations.append((row["cn_code"], "fr", row["description_fr"]))
            # Only about half the rows carry context, and an empty string is
            # not stored: "has no usable ancestor" and "has context that is
            # blank" would otherwise be indistinguishable to the classifier.
            for language in ("en", "de", "fr"):
                context = row.get(f"context_{language}") or ""
                if context:
                    contexts.append((row["cn_code"], language, context))

    count = upsert_hs_codes(conn, records)
    upsert_translations(conn, translations)
    upsert_contexts(conn, contexts)
    logger.info("loaded %d bundled CN codes from %s", count, path)
    return count


def load_bundled_hs_supplement(conn: sqlite3.Connection, path: Optional[Path] = None) -> int:
    """Load the HS-6 subheadings the EU CN bundle does not cover.

    The CN bundle turned out to miss 359 of the 1,229 HS headings (4014, 8541,
    ...). `data/hs2022_supplement.csv` fills every uncovered HS-6 subheading
    from the public-domain WCO HS 2022 nomenclature; it is built offline by
    `scripts/build_hs_supplement.py` and committed. Its codes are six digits
    on purpose (a real HS code, not an invented CN-8), English only, and each
    carries its heading's text as context, so the classifier reads it exactly
    like a dependent CN leaf.

    Call after `load_bundled_cn_nomenclature`. Idempotent for the same reason.

    Args:
        conn: An open database connection.
        path: Override for the supplement's location.

    Returns:
        The number of HS-6 codes loaded.
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "data" / "hs2022_supplement.csv"

    records = []
    contexts: list[tuple] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            records.append(HSCode(row["hs_code"], row["description_en"], row["category"]))
            if row["context_en"]:
                contexts.append((row["hs_code"], "en", row["context_en"]))

    count = upsert_hs_codes(conn, records)
    upsert_contexts(conn, contexts)
    logger.info("loaded %d HS-6 supplement codes from %s", count, path)
    return count


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
    return _insert_returning_id(
        conn,
        "INSERT INTO review_decisions "
        "(subject_type, subject_reference, decision, reviewer_name, comment, reviewed_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (subject_type, subject_reference, decision, reviewer_name, comment, reviewed_at),
    )


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


def insert_review_authorship(conn: sqlite3.Connection, review_id: int, user_id: int) -> None:
    """Record that an authenticated user wrote one review row.

    A review row with no entry here was written without authentication — the
    CLI, or any row predating accounts. The link is by row id on purpose: a
    historical free-text `reviewer_name` can never be claimed by someone who
    later registers that same username.

    Args:
        conn: An open database connection.
        review_id: The `review_decisions` row this authorship belongs to.
        user_id: The authenticated author's `users.id`.
    """
    conn.execute(
        "INSERT INTO review_authorship (review_id, user_id) VALUES (?, ?)",
        (review_id, user_id),
    )
    conn.commit()


def fetch_authored_review_ids(conn: sqlite3.Connection, review_ids: Sequence[int]) -> set:
    """Return which of the given review ids were written by an authenticated user.

    Args:
        conn: An open database connection.
        review_ids: Review row ids to look up.

    Returns:
        The subset of `review_ids` that has an authorship record.
    """
    if not review_ids:
        return set()
    # Placeholders are generated from the id count, never from caller strings;
    # every value itself is still bound.
    placeholders = ", ".join("?" for _ in review_ids)
    rows = conn.execute(
        f"SELECT review_id FROM review_authorship WHERE review_id IN ({placeholders})",
        tuple(review_ids),
    ).fetchall()
    return {row[0] for row in rows}


def insert_user(
    conn: sqlite3.Connection, username: str, password_hash: str, role: str, created_at: str
) -> int:
    """Create one account.

    Args:
        conn: An open database connection.
        username: Unique login name.
        password_hash: The encoded PBKDF2 hash — never a plaintext password.
        role: One of the roles in `auth.ROLE_ORDER`.
        created_at: ISO 8601 timestamp.

    Returns:
        The autoincrement id of the new row.
    """
    return _insert_returning_id(
        conn,
        "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
        (username, password_hash, role, created_at),
    )


def get_user_by_username(conn: sqlite3.Connection, username: str) -> Optional[User]:
    """Return the account with this username, or None if there is none."""
    row = conn.execute(
        "SELECT id, username, role, created_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    return User(*row) if row else None


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> Optional[User]:
    """Return the account with this id, or None if there is none."""
    row = conn.execute(
        "SELECT id, username, role, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return User(*row) if row else None


def get_password_hash(conn: sqlite3.Connection, username: str) -> Optional[str]:
    """Return one account's stored password hash, or None if the user is unknown.

    Deliberately separate from `get_user_by_username`: the hash is needed by
    exactly one function (login verification) and has no business riding along
    inside the `User` records that routes hand back to clients.
    """
    row = conn.execute(
        "SELECT password_hash FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    return str(row[0]) if row else None


def fetch_users(conn: sqlite3.Connection) -> list[User]:
    """Return every account, oldest first."""
    rows = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY id").fetchall()
    return [User(*row) for row in rows]


def count_users(conn: sqlite3.Connection) -> int:
    """Return how many accounts exist."""
    row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    return int(row[0])


def update_user_role(conn: sqlite3.Connection, username: str, role: str) -> bool:
    """Set one account's role.

    Args:
        conn: An open database connection.
        username: The account to change.
        role: The new role.

    Returns:
        True if an account was updated, False if the username is unknown.
    """
    cursor = conn.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
    conn.commit()
    return bool(cursor.rowcount)


def insert_session(
    conn: sqlite3.Connection, token_hash: str, user_id: int, created_at: str, expires_at: str
) -> None:
    """Store one session.

    Only the hash of the token is stored, never the token itself, so a leaked
    database yields no usable session.
    """
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token_hash, user_id, created_at, expires_at),
    )
    conn.commit()


def fetch_session_user_id(conn: sqlite3.Connection, token_hash: str, now: str) -> Optional[int]:
    """Return the user id behind an unexpired session token hash, else None.

    Args:
        conn: An open database connection.
        token_hash: SHA-256 hex digest of the presented token.
        now: ISO 8601 timestamp to compare `expires_at` against. ISO 8601 in
            UTC sorts lexicographically, which is why a string compare is
            correct here on both backends.
    """
    row = conn.execute(
        "SELECT user_id FROM sessions WHERE token_hash = ? AND expires_at > ?",
        (token_hash, now),
    ).fetchone()
    return int(row[0]) if row else None


def delete_session(conn: sqlite3.Connection, token_hash: str) -> None:
    """Remove one session, making its token immediately unusable."""
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
    conn.commit()


def delete_expired_sessions(conn: sqlite3.Connection, now: str) -> int:
    """Delete sessions that have expired, returning how many were removed."""
    cursor = conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
    conn.commit()
    return int(cursor.rowcount)


class PendingSignup(NamedTuple):
    """One row of `pending_signups`: a sign-up waiting for its e-mail code."""

    email: str
    username: str
    password_hash: str
    google_sub: Optional[str]
    code_hash: str
    language: str
    attempts: int
    sent_at: str
    expires_at: str


_PENDING_COLUMNS = (
    "email, username, password_hash, google_sub, code_hash, language, attempts, sent_at, expires_at"
)


def upsert_pending_signup(conn: sqlite3.Connection, pending: PendingSignup) -> None:
    """Store a pending sign-up, replacing any earlier one for the same e-mail."""
    conn.execute("DELETE FROM pending_signups WHERE email = ?", (pending.email,))
    conn.execute(
        f"INSERT INTO pending_signups ({_PENDING_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuple(pending),
    )
    conn.commit()


def get_pending_signup(conn: sqlite3.Connection, email: str) -> Optional[PendingSignup]:
    """Return the pending sign-up for this e-mail, or None."""
    row = conn.execute(
        f"SELECT {_PENDING_COLUMNS} FROM pending_signups WHERE email = ?", (email,)
    ).fetchone()
    return PendingSignup(*row) if row else None


def record_failed_code_attempt(conn: sqlite3.Connection, email: str) -> None:
    """Count one wrong code against a pending sign-up."""
    conn.execute("UPDATE pending_signups SET attempts = attempts + 1 WHERE email = ?", (email,))
    conn.commit()


def delete_pending_signup(conn: sqlite3.Connection, email: str) -> None:
    """Remove a pending sign-up (confirmed, expired, or out of attempts)."""
    conn.execute("DELETE FROM pending_signups WHERE email = ?", (email,))
    conn.commit()


def pending_username_taken(conn: sqlite3.Connection, username: str, email: str) -> bool:
    """Whether another e-mail's unexpired sign-up has already claimed this username."""
    now = datetime.now(timezone.utc).isoformat()
    row = conn.execute(
        "SELECT 1 FROM pending_signups WHERE username = ? AND email <> ? AND expires_at > ?",
        (username, email, now),
    ).fetchone()
    return row is not None


def insert_user_email(
    conn: sqlite3.Connection,
    user_id: int,
    email: str,
    google_sub: Optional[str],
    verified_at: str,
) -> None:
    """Attach a verified e-mail (and optional Google account id) to a user."""
    conn.execute(
        "INSERT INTO user_emails (user_id, email, google_sub, verified_at) VALUES (?, ?, ?, ?)",
        (user_id, email, google_sub, verified_at),
    )
    conn.commit()


def link_google_account(conn: sqlite3.Connection, user_id: int, google_sub: str) -> None:
    """Record the Google account id on a user who verified their e-mail another way."""
    conn.execute("UPDATE user_emails SET google_sub = ? WHERE user_id = ?", (google_sub, user_id))
    conn.commit()


def get_user_id_by_email(conn: sqlite3.Connection, email: str) -> Optional[int]:
    """Return the id of the user with this verified e-mail, or None."""
    row = conn.execute("SELECT user_id FROM user_emails WHERE email = ?", (email,)).fetchone()
    return int(row[0]) if row else None


def get_user_id_by_google_sub(conn: sqlite3.Connection, google_sub: str) -> Optional[int]:
    """Return the id of the user linked to this Google account, or None."""
    row = conn.execute(
        "SELECT user_id FROM user_emails WHERE google_sub = ?", (google_sub,)
    ).fetchone()
    return int(row[0]) if row else None


def get_email_for_user(conn: sqlite3.Connection, user_id: int) -> Optional[str]:
    """Return a user's verified e-mail, or None for accounts that have none."""
    row = conn.execute("SELECT email FROM user_emails WHERE user_id = ?", (user_id,)).fetchone()
    return str(row[0]) if row else None


class ActivityEntry(NamedTuple):
    """One row of `activity_log`."""

    id: int
    user_id: Optional[int]
    username: str
    action: str
    detail: Optional[str]
    result_count: Optional[int]
    top_code: Optional[str]
    created_at: str


_ACTIVITY_COLUMNS = "id, user_id, username, action, detail, result_count, top_code, created_at"


def insert_activity(
    conn: sqlite3.Connection,
    user_id: Optional[int],
    username: str,
    action: str,
    detail: Optional[str],
    result_count: Optional[int],
    top_code: Optional[str],
    created_at: str,
) -> None:
    """Append one activity row."""
    conn.execute(
        "INSERT INTO activity_log (user_id, username, action, detail, result_count, top_code,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, username, action, detail, result_count, top_code, created_at),
    )
    conn.commit()


def delete_activity_before(conn: sqlite3.Connection, cutoff: str) -> int:
    """Delete activity rows older than `cutoff` (ISO 8601), returning how many."""
    cursor = conn.execute("DELETE FROM activity_log WHERE created_at < ?", (cutoff,))
    conn.commit()
    return int(cursor.rowcount)


def fetch_activity(
    conn: sqlite3.Connection,
    username: Optional[str] = None,
    action: Optional[str] = None,
    text: Optional[str] = None,
    zero_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ActivityEntry], int]:
    """Return one page of activity, newest first, and the total matching count."""
    clauses: list[str] = []
    params: list[Any] = []
    if username:
        clauses.append("username = ?")
        params.append(username)
    if action:
        clauses.append("action = ?")
        params.append(action)
    if text:
        clauses.append("LOWER(detail) LIKE ?")
        params.append("%" + text.lower() + "%")
    if zero_only:
        clauses.append("result_count = 0")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    total = int(conn.execute(f"SELECT COUNT(*) FROM activity_log{where}", params).fetchone()[0])
    rows = conn.execute(
        f"SELECT {_ACTIVITY_COLUMNS} FROM activity_log{where} ORDER BY id DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ).fetchall()
    return [ActivityEntry(*row) for row in rows], total


def count_activity_since(conn: sqlite3.Connection, since: str, actions: Sequence[str]) -> int:
    """Count activity rows of the given actions at or after `since`."""
    placeholders = ", ".join("?" for _ in actions)
    row = conn.execute(
        f"SELECT COUNT(*) FROM activity_log WHERE created_at >= ? AND action IN ({placeholders})",
        (since, *actions),
    ).fetchone()
    return int(row[0])


def fetch_unmatched_searches(
    conn: sqlite3.Connection, actions: Sequence[str], limit: int = 100
) -> list[tuple[str, int, str]]:
    """Group searches that returned nothing: (query, times, last searched), most frequent first."""
    placeholders = ", ".join("?" for _ in actions)
    rows = conn.execute(
        "SELECT LOWER(detail), COUNT(*), MAX(created_at) FROM activity_log"
        f" WHERE result_count = 0 AND detail IS NOT NULL AND action IN ({placeholders})"
        " GROUP BY LOWER(detail) ORDER BY COUNT(*) DESC, MAX(created_at) DESC LIMIT ?",
        (*actions, limit),
    ).fetchall()
    return [(str(r[0]), int(r[1]), str(r[2])) for r in rows]


def fetch_last_activity_by_user(conn: sqlite3.Connection) -> dict[int, str]:
    """Return each user's most recent activity timestamp, keyed by user id."""
    rows = conn.execute(
        "SELECT user_id, MAX(created_at) FROM activity_log"
        " WHERE user_id IS NOT NULL GROUP BY user_id"
    ).fetchall()
    return {int(r[0]): str(r[1]) for r in rows}


def fetch_user_emails(conn: sqlite3.Connection) -> dict[int, tuple[str, bool]]:
    """Return every verified e-mail as {user_id: (email, signed up with Google)}."""
    rows = conn.execute("SELECT user_id, email, google_sub FROM user_emails").fetchall()
    return {int(r[0]): (str(r[1]), r[2] is not None) for r in rows}


def count_rows(conn: sqlite3.Connection, table: str, where: str = "", params: Sequence = ()) -> int:
    """COUNT(*) over a table. `table` and `where` are module-internal literals only."""
    clause = f" WHERE {where}" if where else ""
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}{clause}", tuple(params)).fetchone()[0])


def delete_user(conn: sqlite3.Connection, user_id: int) -> None:
    """Delete an account with its sessions and e-mail.

    Review decisions and activity rows are kept: they are the audit trail and
    carry the username as text, so they still read after the account is gone.
    The account's public star rating is not an audit record and goes with it.
    """
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM user_emails WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM site_ratings WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()


class SiteRating(NamedTuple):
    """One row of `site_ratings`."""

    id: int
    user_id: int
    username: str
    rating: int
    comment: str
    company: Optional[str]
    status: str
    created_at: str
    updated_at: str


_RATING_COLUMNS = "id, user_id, username, rating, comment, company, status, created_at, updated_at"


def upsert_rating(
    conn: sqlite3.Connection,
    user_id: int,
    username: str,
    rating: int,
    comment: str,
    company: Optional[str],
    status: str,
    now: str,
) -> None:
    """Create or replace one account's rating, keeping its original created_at."""
    existing = get_rating_for_user(conn, user_id)
    if existing is None:
        conn.execute(
            "INSERT INTO site_ratings (user_id, username, rating, comment, company, status,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, rating, comment, company, status, now, now),
        )
    else:
        conn.execute(
            "UPDATE site_ratings SET username = ?, rating = ?, comment = ?, company = ?,"
            " status = ?, updated_at = ? WHERE user_id = ?",
            (username, rating, comment, company, status, now, user_id),
        )
    conn.commit()


def get_rating_for_user(conn: sqlite3.Connection, user_id: int) -> Optional[SiteRating]:
    """Return one account's rating, or None."""
    row = conn.execute(
        f"SELECT {_RATING_COLUMNS} FROM site_ratings WHERE user_id = ?", (user_id,)
    ).fetchone()
    return SiteRating(*row) if row else None


def fetch_ratings(
    conn: sqlite3.Connection, status: Optional[str] = None, limit: int = 50
) -> list[SiteRating]:
    """Return ratings, most recently updated first, optionally of one status."""
    if status:
        rows = conn.execute(
            f"SELECT {_RATING_COLUMNS} FROM site_ratings WHERE status = ?"
            " ORDER BY updated_at DESC, id DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT {_RATING_COLUMNS} FROM site_ratings ORDER BY updated_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [SiteRating(*row) for row in rows]


def rating_distribution(conn: sqlite3.Connection, status: str) -> dict[int, int]:
    """Count ratings of one status by star value: {5: n, 4: n, ..., 1: n}."""
    rows = conn.execute(
        "SELECT rating, COUNT(*) FROM site_ratings WHERE status = ? GROUP BY rating", (status,)
    ).fetchall()
    counts = {stars: 0 for stars in range(5, 0, -1)}
    for stars, count in rows:
        counts[int(stars)] = int(count)
    return counts


def set_rating_status(conn: sqlite3.Connection, rating_id: int, status: str) -> bool:
    """Set one rating's status; False if there is no such rating."""
    cursor = conn.execute("UPDATE site_ratings SET status = ? WHERE id = ?", (status, rating_id))
    conn.commit()
    return bool(cursor.rowcount)


def delete_rating(conn: sqlite3.Connection, rating_id: int) -> bool:
    """Delete one rating by id; False if there is no such rating."""
    cursor = conn.execute("DELETE FROM site_ratings WHERE id = ?", (rating_id,))
    conn.commit()
    return bool(cursor.rowcount)


def delete_rating_for_user(conn: sqlite3.Connection, user_id: int) -> bool:
    """Delete one account's own rating; False if it had none."""
    cursor = conn.execute("DELETE FROM site_ratings WHERE user_id = ?", (user_id,))
    conn.commit()
    return bool(cursor.rowcount)


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
    return _insert_returning_id(
        conn,
        "INSERT INTO cn_code_versions (version_label, source_description, imported_at, row_count) "
        "VALUES (?, ?, ?, ?)",
        (version_label, source_description, imported_at, row_count),
    )


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
    # The subquery alias is optional on SQLite but required by PostgreSQL
    # before 16 — harmless on both, so it's written once with the alias.
    row = conn.execute(
        "SELECT COUNT(*) FROM ("
        "SELECT code FROM hs_code_history GROUP BY code HAVING COUNT(*) > 1"
        ") AS changed_codes"
    ).fetchone()
    return int(row[0])


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

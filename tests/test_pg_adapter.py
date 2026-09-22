"""Tests for the PostgreSQL dialect adapter — no PostgreSQL server needed.

These run in the default suite: everything here is either a pure string
translation or exercised against a recording fake connection. The tests that
need a real server live in tests/test_postgres.py and skip without one.
"""

import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest

from src.customsiq import database, pg_adapter
from src.customsiq.config import Settings
from src.customsiq.database import SCHEMA, get_connection
from src.customsiq.pg_adapter import (
    PgConnection,
    connect_postgres,
    is_postgres_url,
    to_postgres_ddl,
    translate_placeholders,
)

PG_URL = "postgresql://customsiq:customsiq@localhost:5432/customsiq"


class FakeCursor:
    """Records every statement it is given and returns canned rows."""

    def __init__(self, recorder: list[tuple[str, Any]]) -> None:
        self._recorder = recorder
        self._row: tuple = (1,)

    def execute(self, sql: str, parameters: Any = ()) -> "FakeCursor":
        self._recorder.append((sql, parameters))
        return self

    def executemany(self, sql: str, seq: Any = ()) -> "FakeCursor":
        self._recorder.append((sql, list(seq)))
        return self

    def fetchone(self) -> tuple:
        return self._row

    def fetchall(self) -> list:
        return []


class FakeConnection:
    """Stands in for a psycopg connection, recording the SQL it receives."""

    def __init__(self) -> None:
        self.statements: list[tuple[str, Any]] = []
        self.commits = 0
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.statements)

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_pg() -> tuple[PgConnection, FakeConnection]:
    """A PgConnection over a recording fake, plus the fake itself."""
    inner = FakeConnection()
    return PgConnection(inner), inner


class TestUrlDetection:
    """Which targets route to PostgreSQL rather than SQLite."""

    def test_postgres_schemes_detected(self) -> None:
        """Both spellings of the scheme count as a Postgres URL."""
        assert is_postgres_url("postgresql://host/db")
        assert is_postgres_url("postgres://host/db")

    def test_file_paths_are_not_postgres(self) -> None:
        """Ordinary SQLite targets are left alone."""
        assert not is_postgres_url(":memory:")
        assert not is_postgres_url("customsiq.db")
        assert not is_postgres_url("/data/customsiq.db")


class TestPlaceholderTranslation:
    """SQLite's `?` markers become psycopg's `%s`."""

    def test_question_marks_become_percent_s(self) -> None:
        assert translate_placeholders("SELECT 1 WHERE a = ? AND b = ?") == (
            "SELECT 1 WHERE a = %s AND b = %s"
        )

    def test_statements_without_placeholders_are_unchanged(self) -> None:
        assert translate_placeholders("SELECT code FROM hs_codes") == "SELECT code FROM hs_codes"


class TestDdlTranslation:
    """The Postgres schema is derived from the one SQLite SCHEMA, not copied."""

    def test_autoincrement_becomes_identity(self) -> None:
        """Postgres has no AUTOINCREMENT; identity columns replace it."""
        ddl = to_postgres_ddl(SCHEMA)
        assert "AUTOINCREMENT" not in ddl
        assert ddl.count("INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY") == 4

    def test_real_becomes_double_precision(self) -> None:
        """REAL is 4-byte float4 on Postgres, which would corrupt 16.9."""
        ddl = to_postgres_ddl(SCHEMA)
        assert not re.search(r"\bREAL\b", ddl)
        assert "rate_percent DOUBLE PRECISION NOT NULL" in ddl

    def test_every_table_survives_translation(self) -> None:
        """All nine tables are still created, none dropped by the rewrite."""
        ddl = to_postgres_ddl(SCHEMA)
        for table in (
            "hs_codes",
            "sanctioned_entities",
            "tariff_rates",
            "review_decisions",
            "hs_code_history",
            "cn_code_versions",
            "users",
            "sessions",
            "review_authorship",
        ):
            assert f"CREATE TABLE IF NOT EXISTS {table}" in ddl


class TestPgConnection:
    """The narrow sqlite3-shaped surface database.py actually uses."""

    def test_execute_translates_placeholders(
        self, fake_pg: tuple[PgConnection, FakeConnection]
    ) -> None:
        conn, inner = fake_pg
        conn.execute("SELECT 1 FROM hs_codes WHERE code = ?", ("6109100000",))
        assert inner.statements == [("SELECT 1 FROM hs_codes WHERE code = %s", ("6109100000",))]

    def test_executemany_translates_and_passes_every_row(
        self, fake_pg: tuple[PgConnection, FakeConnection]
    ) -> None:
        conn, inner = fake_pg
        conn.executemany("INSERT INTO t VALUES (?, ?)", [("a", 1), ("b", 2)])
        sql, rows = inner.statements[0]
        assert sql == "INSERT INTO t VALUES (%s, %s)"
        assert rows == [("a", 1), ("b", 2)]

    def test_executescript_splits_into_separate_statements(
        self, fake_pg: tuple[PgConnection, FakeConnection]
    ) -> None:
        """psycopg has no executescript, so the adapter runs each statement."""
        conn, inner = fake_pg
        conn.executescript("CREATE TABLE a (x INT);\n\nCREATE TABLE b (y INT);\n")
        assert [sql for sql, _ in inner.statements] == [
            "CREATE TABLE a (x INT)",
            "CREATE TABLE b (y INT)",
        ]

    def test_dialect_is_postgresql(self, fake_pg: tuple[PgConnection, FakeConnection]) -> None:
        """database.py branches on this attribute for RETURNING."""
        conn, _ = fake_pg
        assert conn.dialect == "postgresql"

    def test_close_closes_the_underlying_connection(
        self, fake_pg: tuple[PgConnection, FakeConnection]
    ) -> None:
        conn, inner = fake_pg
        conn.close()
        assert inner.closed


class TestConnectPostgres:
    """Driver wiring: tuple rows and autocommit, both deliberate."""

    def test_connects_with_tuple_rows_and_autocommit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """dict rows would make `HSCode(*row)` unpack column names into fields."""
        captured: dict[str, Any] = {}
        sentinel = object()

        fake_rows = type(sys)("psycopg.rows")
        fake_rows.tuple_row = sentinel  # type: ignore[attr-defined]
        fake_psycopg = type(sys)("psycopg")
        fake_psycopg.rows = fake_rows  # type: ignore[attr-defined]

        def fake_connect(url: str, **kwargs: Any) -> FakeConnection:
            captured["url"] = url
            captured.update(kwargs)
            return FakeConnection()

        fake_psycopg.connect = fake_connect  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
        monkeypatch.setitem(sys.modules, "psycopg.rows", fake_rows)

        conn = connect_postgres(PG_URL)

        assert isinstance(conn, PgConnection)
        assert captured["url"] == PG_URL
        assert captured["autocommit"] is True
        assert captured["row_factory"] is sentinel

    def test_missing_driver_explains_how_to_install_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A helpful error beats an ImportError traceback from deep in the stack."""
        monkeypatch.setitem(sys.modules, "psycopg", None)
        with pytest.raises(RuntimeError, match="requirements-postgres.txt"):
            connect_postgres(PG_URL)


class TestGetConnectionRouting:
    """get_connection picks a backend from the shape of its argument."""

    def test_sqlite_targets_return_a_thread_safe_sqlite_connection(self) -> None:
        """The SQLite path returns the lock-guarded wrapper over a real connection.

        Not a bare sqlite3.Connection: this machine's SQLite is built
        THREADSAFE=2, so the shared connection has to serialize access itself
        (see database._SerializedConnection).
        """
        conn = get_connection(":memory:")
        assert isinstance(conn, database._SerializedConnection)
        assert isinstance(conn._connection, sqlite3.Connection)
        assert conn.dialect == "sqlite"
        conn.close()

    def test_postgres_url_goes_through_the_adapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A URL target builds the translated schema on a PgConnection."""
        inner = FakeConnection()
        monkeypatch.setattr(pg_adapter, "connect_postgres", lambda url: PgConnection(inner))

        conn = get_connection(PG_URL)

        assert isinstance(conn, PgConnection)
        created = [sql for sql, _ in inner.statements if sql.startswith("CREATE TABLE")]
        assert len(created) == 9
        assert not any("AUTOINCREMENT" in sql for sql in created)


class TestInsertReturningId:
    """Generated ids come from lastrowid on SQLite, RETURNING on Postgres."""

    def test_postgres_appends_returning_id(
        self, fake_pg: tuple[PgConnection, FakeConnection]
    ) -> None:
        conn, inner = fake_pg
        new_id = database._insert_returning_id(conn, "INSERT INTO t (a) VALUES (?)", ("x",))
        assert new_id == 1
        assert inner.statements[0][0] == "INSERT INTO t (a) VALUES (%s) RETURNING id"

    def test_sqlite_uses_lastrowid_without_returning(self) -> None:
        """The SQLite branch keeps its existing execute/commit/lastrowid sequence."""
        conn = get_connection(":memory:")
        new_id = database._insert_returning_id(
            conn,
            "INSERT INTO cn_code_versions "
            "(version_label, source_description, imported_at, row_count) VALUES (?, ?, ?, ?)",
            ("CN2026", "cn.csv", "2026-01-01T00:00:00+00:00", 1),
        )
        assert new_id == 1
        conn.close()


class TestSqlPortability:
    """Guards the naive-translation ceiling the adapter documents."""

    def test_no_sql_string_contains_a_literal_percent_or_star_select(self) -> None:
        """`?`->`%s` is only safe while no statement carries a literal % itself.

        `SELECT *` would break the other half of the contract: every row is
        unpacked positionally, so column order must be fixed by the query.
        """
        source = Path(database.__file__).read_text(encoding="utf-8")
        sql_lines = [
            line
            for line in source.splitlines()
            if re.search(r'"\s*(SELECT|INSERT|UPDATE|DELETE|CREATE)', line, re.IGNORECASE)
            or re.search(r'"(FROM|WHERE|VALUES|ON CONFLICT|ORDER BY|SET)\b', line)
        ]
        assert sql_lines, "expected to find SQL strings to scan"
        assert not [line for line in sql_lines if "%" in line]
        assert "SELECT *" not in source

    def test_every_write_path_translates_cleanly(
        self, fake_pg: tuple[PgConnection, FakeConnection]
    ) -> None:
        """Run the write functions against the fake; no `?` may survive."""
        conn, inner = fake_pg
        database.insert_review_decision(
            conn, "duty", "ref", "approved", "alice", None, "2026-01-01T00:00:00+00:00"
        )
        database.record_cn_import(conn, "CN2026", "cn.csv", "2026-01-01T00:00:00+00:00", 10)
        database.upsert_hs_codes(conn, [database.SAMPLE_DATA[0]])
        assert inner.statements
        assert not [sql for sql, _ in inner.statements if "?" in sql]


class TestConfigPrecedence:
    """CUSTOMSIQ_DATABASE_URL wins over CUSTOMSIQ_DATABASE_PATH."""

    def test_path_is_used_when_no_url_is_set(self) -> None:
        assert Settings(database_path="customsiq.db").database_target == "customsiq.db"

    def test_url_overrides_path(self) -> None:
        settings = Settings(database_path="customsiq.db", database_url=PG_URL)
        assert settings.database_target == PG_URL

    def test_empty_url_is_treated_as_unset(self) -> None:
        """An exported-but-blank env var must not switch backends."""
        settings = Settings(database_path="customsiq.db", database_url="")
        assert settings.database_url is None
        assert settings.database_target == "customsiq.db"

    def test_non_postgres_url_is_rejected(self) -> None:
        """Fail loudly rather than silently treating a typo'd URL as a file path."""
        with pytest.raises(ValueError, match="postgresql://"):
            Settings(database_url="mysql://host/db")

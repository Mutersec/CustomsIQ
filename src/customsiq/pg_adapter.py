"""PostgreSQL dialect adapter — the opt-in alternative to the default SQLite backend.

Nothing here is imported unless `CUSTOMSIQ_DATABASE_URL` is set: `database.py`
imports this module lazily inside its Postgres branch, so the SQLite path (and
the live deployment) never touches it, and `psycopg` stays an optional extra
(`requirements-postgres.txt`) rather than a production dependency — the same
treatment `openpyxl` already gets in the CN importer.

The adapter is deliberately thin: `database.py` keeps one set of SQL strings,
and only the handful of genuine dialect differences are translated here.

# ponytail: naive `?` -> `%s` replacement and two DDL substitutions, which is
# enough while every statement in database.py is plain SQL with no literal
# '?'/'%' and no dialect-specific constructs. If that stops being true, move to
# a real translator (sqlglot) or SQLAlchemy Core rather than growing regexes.
"""

import logging
import re
from collections.abc import Callable, Iterable, Sequence
from types import TracebackType
from typing import Any, Optional

logger = logging.getLogger(__name__)

POSTGRES_SCHEMES = ("postgres://", "postgresql://")

_MISSING_DRIVER = (
    "PostgreSQL support needs 'pip install -r requirements-postgres.txt'. "
    "Unset CUSTOMSIQ_DATABASE_URL to use the default SQLite backend instead."
)


def is_postgres_url(target: str) -> bool:
    """Return whether a connection target is a PostgreSQL URL rather than a file path."""
    return target.startswith(POSTGRES_SCHEMES)


def translate_placeholders(sql: str) -> str:
    """Rewrite SQLite's `?` parameter markers as psycopg's `%s`.

    Safe because every statement in `database.py` is plain SQL holding no
    literal '?' or '%' — enforced by a test that sweeps all of them.
    """
    return sql.replace("?", "%s")


def to_postgres_ddl(schema: str) -> str:
    """Translate the SQLite `SCHEMA` script into its PostgreSQL equivalent.

    Derived from the one schema in `database.py` rather than kept as a second
    copy, so the two backends cannot drift apart. Two substitutions are needed:

    - `INTEGER PRIMARY KEY AUTOINCREMENT` has no Postgres equivalent; identity
      columns are the modern replacement for serials.
    - `REAL` means an 8-byte float in SQLite but a 4-byte `float4` in Postgres,
      which would read `16.9` back as `16.899999618530273` and quietly corrupt
      duty and risk arithmetic. `DOUBLE PRECISION` matches SQLite's width (and
      keeps SQLite's own REAL affinity if ever used there).
    """
    ddl = re.sub(
        r"INTEGER PRIMARY KEY AUTOINCREMENT",
        "INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY",
        schema,
    )
    return re.sub(r"\bREAL\b", "DOUBLE PRECISION", ddl)


class PgConnection:
    """A `sqlite3.Connection`-shaped wrapper over a psycopg connection.

    Only the narrow surface `database.py` actually uses is implemented:
    `execute`, `executemany`, `executescript`, `commit`, `close`. Statements
    run with autocommit on, so one failed statement can't leave this shared
    connection in Postgres's "current transaction is aborted" state — SQLite
    has no such mode, and the rest of the app assumes it doesn't exist.
    """

    dialect = "postgresql"

    def __init__(self, connection: Any, url: Optional[str] = None) -> None:
        self._connection = connection
        self._url = url

    def _run(self, work: Callable[[Any], None]) -> Any:
        """Run `work` on a fresh cursor, reconnecting once if the server dropped us.

        The app holds this one connection for its whole life, and hosted Postgres
        closes idle ones (Neon's free tier suspends after five idle minutes), so
        without this every query after the first nap fails until a restart.
        Only a *broken* connection is retried, never a failing statement.
        """
        import psycopg

        try:
            cursor = self._connection.cursor()
            work(cursor)
            return cursor
        except psycopg.OperationalError:
            if self._url is None or not (self._connection.closed or self._connection.broken):
                raise
            # ponytail: a statement cut off mid-flight is re-sent; with autocommit
            # that can double one insert in a rare race. A pool fixes it if it matters.
            logger.warning("PostgreSQL connection lost, reconnecting")
            self._connection = _open(self._url)
            cursor = self._connection.cursor()
            work(cursor)
            return cursor

    def execute(self, sql: str, parameters: Sequence[Any] = ()) -> Any:
        """Run one statement and return its cursor (already executed, like sqlite3)."""
        return self._run(lambda c: c.execute(translate_placeholders(sql), tuple(parameters)))

    def executemany(self, sql: str, seq_of_parameters: Iterable[Sequence[Any]]) -> Any:
        """Run one statement for each parameter row (psycopg has this on the cursor)."""
        rows = [tuple(p) for p in seq_of_parameters]
        return self._run(lambda c: c.executemany(translate_placeholders(sql), rows))

    def executescript(self, script: str) -> Any:
        """Run a multi-statement script; psycopg has no executescript of its own."""

        def run_all(cursor: Any) -> None:
            for statement in (s.strip() for s in script.split(";")):
                if statement:
                    cursor.execute(statement)

        return self._run(run_all)

    def commit(self) -> None:
        """No-op in practice (autocommit), kept so callers need no dialect branch."""
        self._connection.commit()

    def close(self) -> None:
        """Close the underlying psycopg connection."""
        self._connection.close()

    def __enter__(self) -> "PgConnection":
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.close()


def connect_postgres(url: str) -> PgConnection:
    """Open a PostgreSQL connection wrapped to look like the SQLite one.

    Args:
        url: A `postgresql://` / `postgres://` connection URL.

    Returns:
        A PgConnection ready for `database.py` to use.

    Raises:
        RuntimeError: If the optional psycopg driver isn't installed.
    """
    try:
        import psycopg  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(_MISSING_DRIVER) from exc

    connection = _open(url)
    logger.info("connected to PostgreSQL")
    return PgConnection(connection, url)


def _open(url: str) -> Any:
    """Open the raw psycopg connection (also used to reconnect)."""
    import psycopg
    from psycopg.rows import tuple_row

    # tuple_row is psycopg's default, but it is set explicitly here because
    # database.py reads every row positionally (`HSCode(*row)`, `row[0]`): with
    # dict rows those unpack the column *names* and silently produce garbage.
    return psycopg.connect(url, autocommit=True, row_factory=tuple_row)

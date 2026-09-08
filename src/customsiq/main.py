"""Command-line interface for interactive HS/CN code search."""

import logging

from src.customsiq.config import settings
from src.customsiq.database import get_connection, seed
from src.customsiq.exceptions import InvalidQueryError
from src.customsiq.logging_config import configure_logging
from src.customsiq.search import search

logger = logging.getLogger(__name__)


def run(db_path: str = settings.database_path) -> None:
    """Start an interactive loop that searches HS codes by product description.

    Args:
        db_path: Path to the SQLite database file to use.
    """
    configure_logging()
    conn = get_connection(db_path)
    seed(conn)
    logger.info("CustomsIQ - HS Code Search (type 'quit' to exit)")
    while True:
        query = input("\nProduct description: ").strip()
        if query.lower() in {"quit", "exit"}:
            break
        if not query:
            continue
        try:
            results = search(conn, query)
        except InvalidQueryError as exc:
            logger.warning("%s", exc)
            continue
        if not results:
            logger.info("No matches found.")
            continue
        for rank, result in enumerate(results, start=1):
            logger.info(
                "%d. %s  (%.0f%%)  %s  [%s]",
                rank,
                result.hs_code.code,
                result.score * 100,
                result.hs_code.description,
                result.hs_code.category,
            )


if __name__ == "__main__":
    run()

"""Fuzzy search over HS code descriptions using the standard library."""

import logging
import sqlite3
from typing import NamedTuple

from src.customsiq.database import fetch_all
from src.customsiq.matching import similarity, validate_query
from src.customsiq.models import HSCode

logger = logging.getLogger(__name__)


class SearchResult(NamedTuple):
    """A single search match paired with its similarity score."""

    hs_code: HSCode
    score: float


def search(conn: sqlite3.Connection, query: str, limit: int = 5) -> list[SearchResult]:
    """Find the HS codes whose description best matches a free-text product query.

    Args:
        conn: An open database connection.
        query: Product description entered by the user.
        limit: Maximum number of results to return.

    Returns:
        Matching HS codes ordered by descending similarity score.

    Raises:
        InvalidQueryError: If the query is empty/whitespace-only, or longer
            than MAX_QUERY_LENGTH characters.
    """
    validate_query(query)

    logger.debug("searching for query=%r limit=%d", query, limit)
    records = fetch_all(conn)
    scored = [SearchResult(record, similarity(query, record.description)) for record in records]
    scored.sort(key=lambda result: result.score, reverse=True)
    return scored[:limit]

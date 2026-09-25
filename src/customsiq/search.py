"""Fuzzy search over HS code descriptions using the standard library."""

import logging
import sqlite3
from typing import NamedTuple

from src.customsiq.database import fetch_all, get_by_code
from src.customsiq.exceptions import HSCodeNotFoundError
from src.customsiq.matching import as_code, similarity, validate_query
from src.customsiq.models import HSCode

logger = logging.getLogger(__name__)


class SearchResult(NamedTuple):
    """A single search match paired with its similarity score."""

    hs_code: HSCode
    score: float


def search(conn: sqlite3.Connection, query: str, limit: int = 5) -> list[SearchResult]:
    """Find the HS codes whose description best matches a free-text product query.

    A query that is itself a CN-8/TARIC-10 code (regardless of formatting,
    e.g. "9505.90.00" or "9505 90 00") is not scored as text: an all-digit
    query would otherwise be compared against every description by raw
    character overlap and come back with an arbitrary, unrelated top result,
    since digits share almost nothing with letters. Instead it's routed to
    an exact lookup.

    Args:
        conn: An open database connection.
        query: Product description entered by the user, or an HS/CN code.
        limit: Maximum number of results to return.

    Returns:
        A single exact match at score 1.0 if `query` is a known code; an
        empty list if `query` is code-shaped but no such code exists;
        otherwise matching HS codes ordered by descending similarity score.

    Raises:
        InvalidQueryError: If the query is empty/whitespace-only, or longer
            than MAX_QUERY_LENGTH characters.
    """
    validate_query(query)

    code = as_code(query)
    if code is not None:
        try:
            return [SearchResult(get_by_code(conn, code), 1.0)]
        except HSCodeNotFoundError:
            return []

    logger.debug("searching for query=%r limit=%d", query, limit)
    records = fetch_all(conn)
    scored = [SearchResult(record, similarity(query, record.description)) for record in records]
    scored.sort(key=lambda result: result.score, reverse=True)
    return scored[:limit]

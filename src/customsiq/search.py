"""Fuzzy search over HS code descriptions using the standard library."""

import logging
import sqlite3
from typing import NamedTuple, Optional

from src.customsiq.database import fetch_all, fetch_all_translations, get_by_code
from src.customsiq.exceptions import HSCodeNotFoundError
from src.customsiq.matching import as_code, similarity, validate_query
from src.customsiq.models import HSCode

logger = logging.getLogger(__name__)


class SearchResult(NamedTuple):
    """A single search match paired with its similarity score."""

    hs_code: HSCode
    score: float


def search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 5,
    language: Optional[str] = None,
) -> list[SearchResult]:
    """Find the HS codes whose description best matches a free-text product query.

    A query that is itself a CN-8/TARIC-10 code (regardless of formatting,
    e.g. "9505.90.00" or "9505 90 00") is not scored as text: an all-digit
    query would otherwise be compared against every description by raw
    character overlap and come back with an arbitrary, unrelated top result,
    since digits share almost nothing with letters. Instead it's routed to
    an exact lookup.

    With `language`, each code is scored against its English description
    *and* its description in that language, keeping whichever fits better.
    English is never dropped: someone reading the German UI may still type an
    English product name, and taking the better of the two costs nothing when
    they do. A code with no text in that language, or a language with no
    stored text at all, simply scores on English as before.

    Args:
        conn: An open database connection.
        query: Product description entered by the user, or an HS/CN code.
        limit: Maximum number of results to return.
        language: Also score against this language's bundled descriptions,
            e.g. "de". Defaults to English-only.

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

    logger.debug("searching for query=%r limit=%d language=%r", query, limit, language)
    records = fetch_all(conn)
    translations = fetch_all_translations(conn, language)

    scored = []
    for record in records:
        score = similarity(query, record.description)
        translated = translations.get(record.code)
        if translated:
            score = max(score, similarity(query, translated))
        scored.append(SearchResult(record, score))

    scored.sort(key=lambda result: result.score, reverse=True)
    return scored[:limit]

"""HS/CN code search: a thin adapter over the one scoring engine in cn_classifier.

Search used to be a second algorithm (difflib character overlap), kept
deliberately separate from classification. That design was reversed: on the
real nomenclature character overlap put "Brie" under "bicycle" and "Not painted"
under "solar panel". Search now reuses `classify()` wholesale, including its
cached TF-IDF index, hierarchical context and curated aliases. It only drops
the per-term reasoning, which the Search panel does not show. See the README's
"/search and /classify — one engine" section.
"""

import sqlite3
from typing import NamedTuple, Optional

from src.customsiq.cn_classifier import classify
from src.customsiq.models import HSCode


class SearchResult(NamedTuple):
    """A single search match, its score, and where it sits in the tariff."""

    hs_code: HSCode
    score: float
    hierarchy_path: str
    alias: Optional[str] = None


def search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 5,
    language: Optional[str] = None,
) -> list[SearchResult]:
    """Find the HS codes whose description best matches a free-text product query.

    Exactly `classify(conn, query, top_n=limit, language=language)`, so a
    code-shaped query is still an exact lookup, `language` still adds that
    language's text, and scores and ranking are identical between the two
    routes by construction.

    A query sharing no word with any code returns an empty list. The old
    character-overlap search always filled `limit` rows, even when none of
    them had anything to do with the query.

    Args:
        conn: An open database connection.
        query: Product description entered by the user, or an HS/CN code.
        limit: Maximum number of results to return.
        language: Also score against this language's bundled descriptions,
            e.g. "de". Defaults to English-only.

    Returns:
        Matching HS codes, most likely first.

    Raises:
        InvalidQueryError: If the query is empty/whitespace-only, or longer
            than MAX_QUERY_LENGTH characters.
    """
    return [
        SearchResult(r.hs_code, r.score, r.hierarchy_path, r.alias)
        for r in classify(conn, query, top_n=limit, language=language)
    ]

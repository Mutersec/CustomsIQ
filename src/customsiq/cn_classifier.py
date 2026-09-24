"""CN classification by term-frequency weighting (TF-IDF over the stored codes).

A deliberate counterpart to `search.py`, not a duplicate of it. Search ranks by
raw character overlap, which is fooled by long shared substrings; this weighs
each word by how rare it is across the corpus, so an unusual term like
"knitted" outranks a common one like "cotton".
"""

import logging
import math
import re
import sqlite3
from collections import Counter
from typing import NamedTuple

from src.customsiq.database import fetch_all
from src.customsiq.matching import validate_query
from src.customsiq.models import HSCode

logger = logging.getLogger(__name__)

TOP_TERMS = 3

_WORD = re.compile(r"[a-z0-9]+")

# ponytail: this index used to be rebuilt unconditionally on every call — fine
# at 0.1 ms for the 20-code mock catalog, but ~150 ms/call once the real CN
# nomenclature (13.7k codes) is loaded, which is noticeable enough to act on.
# `fetch_all(conn)` still runs every time regardless (records are
# always needed), so the cache below reuses that read as its own freshness
# check: if the freshly-fetched records are byte-for-byte what was cached last
# time, the (comparatively expensive) tokenize-and-weight rebuild is skipped.
# That is deliberately NOT a row-count or last-modified check — either would
# miss an in-place description update that leaves the row count unchanged,
# and silently serve a stale index. A plain dict keyed by id(conn), never
# evicted: bounded by how many distinct connections a process ever opens,
# which in practice is one (the live app's singleton) plus however many a
# test run creates — a WeakKeyDictionary is the upgrade path if that ever
# stops being negligible.
_index_cache: dict = {}


def _index_for(conn: sqlite3.Connection, records: list[HSCode]) -> tuple:
    """Return (idf, vectors) for `records`, rebuilding only if they changed."""
    cached = _index_cache.get(id(conn))
    if cached is not None and cached[0] == records:
        return cached[1], cached[2]
    idf, vectors = _build_index(records)
    _index_cache[id(conn)] = (records, idf, vectors)
    return idf, vectors


class ClassificationResult(NamedTuple):
    """A suggested code, its confidence, and the terms that drove the match."""

    hs_code: HSCode
    score: float
    matched_terms: list[str]


def _singular(word: str) -> str:
    """Fold the common English plural endings onto their singular form.

    Not a stemmer — just the rule the corpus demands. Descriptions are written
    in the plural ("cables", "biscuits", "batteries") while users type the
    singular, and without this every such query scores zero against everything.
    """
    if len(word) <= 3 or word.endswith("ss"):
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    # "-es" is only its own plural marker after a sibilant (boxes, dishes);
    # elsewhere it is just "-s" on a word already ending in "e" (cables).
    if word.endswith(("ses", "xes", "zes", "ches", "shes")):
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word


def _tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, and singularise."""
    return [_singular(word) for word in _WORD.findall(text.lower())]


def _normalise(weights: dict[str, float]) -> dict[str, float]:
    """Scale a weight vector to unit length so dot products are cosines."""
    length = math.sqrt(sum(weight * weight for weight in weights.values()))
    if not length:
        return {}
    return {term: weight / length for term, weight in weights.items()}


def _build_index(records: list[HSCode]) -> tuple[dict[str, float], list[dict[str, float]]]:
    """Compute inverse document frequencies and unit document vectors.

    Uses the smoothed IDF `log((N + 1) / (df + 1)) + 1`, which keeps terms that
    appear in every document at a small positive weight instead of zero.

    Args:
        records: The corpus to index.

    Returns:
        The IDF per term, and one normalised weight vector per record.
    """
    tokenised = [_tokenize(record.description) for record in records]
    total = len(records)
    frequencies = Counter(term for tokens in tokenised for term in set(tokens))
    idf = {term: math.log((total + 1) / (count + 1)) + 1 for term, count in frequencies.items()}

    vectors = []
    for tokens in tokenised:
        counts = Counter(tokens)
        vectors.append(_normalise({term: counts[term] * idf[term] for term in counts}))
    return idf, vectors


def classify(
    conn: sqlite3.Connection, description: str, top_n: int = 5
) -> list[ClassificationResult]:
    """Suggest the CN codes a product description most likely belongs to.

    Scores every stored code by cosine similarity between TF-IDF vectors, so
    rare, informative words count for more than common ones. Each suggestion
    reports the input terms that contributed most to it, so a classification
    can be audited rather than taken on trust.

    Codes sharing no term with the description score zero and are dropped: an
    empty result is the honest answer, where returning zero-confidence rows
    would dress noise up as a suggestion.

    Args:
        conn: An open database connection.
        description: Free-text description of the goods.
        top_n: Maximum number of suggestions to return.

    Returns:
        Suggestions above zero confidence, most likely first.

    Raises:
        InvalidQueryError: If the description is blank or too long.
    """
    validate_query(description)

    records = fetch_all(conn)
    idf, vectors = _index_for(conn, records)

    counts = Counter(_tokenize(description))
    unseen = math.log(len(records) + 1) + 1  # IDF for a term absent from the corpus
    query = _normalise({term: count * idf.get(term, unseen) for term, count in counts.items()})

    results = []
    for record, vector in zip(records, vectors):
        shared = query.keys() & vector.keys()
        if not shared:
            continue
        # Every weight is positive (TF >= 1, smoothed IDF >= 1), so a shared
        # term guarantees a positive score — no zero-score guard needed here.
        contributions = {term: query[term] * vector[term] for term in shared}
        score = sum(contributions.values())
        terms = sorted(contributions, key=lambda term: contributions[term], reverse=True)
        results.append(ClassificationResult(record, score, terms[:TOP_TERMS]))

    results.sort(key=lambda result: result.score, reverse=True)
    logger.debug("classified %r into %d suggestion(s)", description, len(results))
    return results[:top_n]

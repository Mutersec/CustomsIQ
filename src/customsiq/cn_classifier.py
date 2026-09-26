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
from typing import NamedTuple, Optional

from src.customsiq.database import fetch_all, fetch_all_translations, get_by_code
from src.customsiq.exceptions import HSCodeNotFoundError
from src.customsiq.matching import as_code, validate_query
from src.customsiq.models import HSCode

logger = logging.getLogger(__name__)

TOP_TERMS = 3

# Unicode-aware rather than [a-z0-9]+: the ASCII form split every accented
# word into fragments, which mattered even for the English corpus — "Gruyère"
# tokenized as "gruy" + "re", "Bergkäse" as "bergk" + "se" (260 of the 13,753
# bundled English descriptions were affected). Those fragments then collide
# across unrelated words, which is how "grüne Küchengeräte" used to top-match
# "Drehspäne, Frässpäne, Hobelspäne". `[^\W_]` is `\w` minus the underscore,
# so it keeps letters and digits in any script and still splits on punctuation.
# Verified: this changes the tokenization of 0 of the 20 SAMPLE_DATA rows, so
# every pinned score built on that corpus is untouched.
_WORD = re.compile(r"[^\W_]+", re.UNICODE)

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


def _index_for(conn: sqlite3.Connection, texts: list, language: Optional[str] = None) -> tuple:
    """Return (idf, vectors) for `texts`, rebuilding only if they changed.

    Keyed by language as well as connection, so the English index and a
    translated one are cached side by side rather than evicting each other.
    `texts` is what was actually read this call — including translated text
    when there is any — so an edited translation invalidates the index for
    exactly the same reason an edited description does.
    """
    cached = _index_cache.get((id(conn), language))
    if cached is not None and cached[0] == texts:
        return cached[1], cached[2]
    idf, vectors = _build_index(texts)
    _index_cache[(id(conn), language)] = (texts, idf, vectors)
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


def _build_index(texts: list) -> tuple[dict[str, float], list[dict[str, float]]]:
    """Compute inverse document frequencies and unit document vectors.

    Uses the smoothed IDF `log((N + 1) / (df + 1)) + 1`, which keeps terms that
    appear in every document at a small positive weight instead of zero.

    Args:
        texts: One string per code — the text to index, in whichever language
            is being indexed. Parallel to the record list it was built from.

    Returns:
        The IDF per term, and one normalised weight vector per text.
    """
    tokenised = [_tokenize(text) for text in texts]
    total = len(texts)
    frequencies = Counter(term for tokens in tokenised for term in set(tokens))
    idf = {term: math.log((total + 1) / (count + 1)) + 1 for term, count in frequencies.items()}

    vectors = []
    for tokens in tokenised:
        counts = Counter(tokens)
        vectors.append(_normalise({term: counts[term] * idf[term] for term in counts}))
    return idf, vectors


def _score_against(
    conn: sqlite3.Connection, texts: list, language: Optional[str], counts: Counter
) -> dict:
    """Score one already-tokenized query against one language's index.

    Returns {position: (score, matched_terms)} for the codes that share at
    least one term, keyed by position in the record list so a caller can
    merge the results of several languages.
    """
    idf, vectors = _index_for(conn, texts, language)
    unseen = math.log(len(texts) + 1) + 1  # IDF for a term absent from the corpus
    query = _normalise({term: count * idf.get(term, unseen) for term, count in counts.items()})

    scored = {}
    for position, vector in enumerate(vectors):
        shared = query.keys() & vector.keys()
        if not shared:
            continue
        # Every weight is positive (TF >= 1, smoothed IDF >= 1), so a shared
        # term guarantees a positive score — no zero-score guard needed here.
        contributions = {term: query[term] * vector[term] for term in shared}
        terms = sorted(contributions, key=lambda term: contributions[term], reverse=True)
        scored[position] = (sum(contributions.values()), terms[:TOP_TERMS])
    return scored


def classify(
    conn: sqlite3.Connection,
    description: str,
    top_n: int = 5,
    language: Optional[str] = None,
) -> list[ClassificationResult]:
    """Suggest the CN codes a product description most likely belongs to.

    Scores every stored code by cosine similarity between TF-IDF vectors, so
    rare, informative words count for more than common ones. Each suggestion
    reports the input terms that contributed most to it, so a classification
    can be audited rather than taken on trust.

    Codes sharing no term with the description score zero and are dropped: an
    empty result is the honest answer, where returning zero-confidence rows
    would dress noise up as a suggestion. A description with no token longer
    than one character gets the same honest empty result, before scoring is
    even attempted: real documents in the corpus are sometimes short enough
    ("175|g or more", "For a current exceeding 16|A...") that a single
    stray character would otherwise dominate their normalized vector and
    produce a confident-looking but meaningless top match.

    A description that is itself a CN-8/TARIC-10 code is not tokenized and
    scored: it would become one opaque token sharing no vocabulary with any
    description, scoring zero against everything and vanishing under the
    same "no match" rule above even though the code exists. Instead it's
    routed to an exact lookup.

    With `language`, each code is also scored against its description in that
    language and keeps whichever score is higher. English is never dropped —
    someone reading the German UI may still type an English product name —
    and `matched_terms` comes from whichever language actually won, so the
    reasoning stays readable either way.

    Args:
        conn: An open database connection.
        description: Free-text description of the goods, or an HS/CN code.
        top_n: Maximum number of suggestions to return.
        language: Also score against this language's bundled descriptions,
            e.g. "de". Defaults to English-only.

    Returns:
        A single exact match at score 1.0, matched_terms=[], if `description`
        is a known code; an empty list if it's code-shaped but no such code
        exists; otherwise suggestions above zero confidence, most likely
        first.

    Raises:
        InvalidQueryError: If the description is blank or too long.
    """
    validate_query(description)

    code = as_code(description)
    if code is not None:
        try:
            return [ClassificationResult(get_by_code(conn, code), 1.0, [])]
        except HSCodeNotFoundError:
            return []

    tokens = _tokenize(description)
    if not any(len(token) > 1 for token in tokens):
        logger.debug("no token longer than one character in %r; nothing to classify", description)
        return []

    records = fetch_all(conn)
    counts = Counter(tokens)
    scored = _score_against(conn, [record.description for record in records], None, counts)

    translations = fetch_all_translations(conn, language)
    if translations:
        texts = [translations.get(record.code, "") for record in records]
        for position, hit in _score_against(conn, texts, language, counts).items():
            best = scored.get(position)
            if best is None or hit[0] > best[0]:
                scored[position] = hit

    # Sorted by position first so ties break on record order, then stably by
    # score — which leaves the English-only path ordered exactly as before.
    results = [
        ClassificationResult(records[position], *scored[position]) for position in sorted(scored)
    ]
    results.sort(key=lambda result: result.score, reverse=True)
    logger.debug("classified %r into %d suggestion(s)", description, len(results))
    return results[:top_n]

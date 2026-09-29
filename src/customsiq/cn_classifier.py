"""CN matching by term-frequency weighting (TF-IDF over the stored codes).

The one scoring engine behind both `/classify` and `/search`. `search.py` is a
thin adapter over `classify()` below; it used to be a second, deliberately
different algorithm (difflib character overlap), and that design was reversed
once real everyday queries showed what character overlap does on the real
nomenclature — "bicycle" matching "Brie", "solar panel" matching "Not painted".
See the README's "/search and /classify — one engine" section.

Each word is weighted by how rare it is across the corpus, so an unusual term
like "knitted" outranks a common one like "cotton", and each code is scored
together with the ancestor context its own text leaves out.
"""

import logging
import math
import re
import sqlite3
from collections import Counter
from typing import NamedTuple, Optional

from src.customsiq.database import (
    fetch_all,
    fetch_all_contexts,
    fetch_all_translations,
    get_by_code,
)
from src.customsiq.exceptions import HSCodeNotFoundError
from src.customsiq.matching import as_code, validate_query
from src.customsiq.models import HSCode

logger = logging.getLogger(__name__)

TOP_TERMS = 3

# At most this many suggestions from one 4-digit heading. Result lists are a
# shortlist a person picks from, and on the real nomenclature a single heading
# can supply five near-identical siblings that crowd out an adjacent heading
# entirely: "bicycle" returned five 8714 bicycle *parts* rows and pushed 8712
# (bicycles themselves) to #6; "leather shoes" returned the same "Sports
# footwear; tennis shoes" text five times. Three rather than two because two
# measurably dropped correct sibling rows ("leather shoes" lost a 6403 row,
# "knitted cotton shirt" a 6109 one). Only rows are skipped, never reordered,
# so the top suggestion is always exactly what it was without the cap.
MAX_PER_HEADING = 3

# A hand-curated alias table: everyday words that share no vocabulary at all
# with the official CN text of the code they mean, so no amount of term
# weighting can connect them. "leech" is the motivating case — no row of the EU
# nomenclature contains the word, so "leeches" can only ever fall to 0106900090,
# "Other live animals > Other".
#
# THIS IS A DEMO-SCALE ILLUSTRATION OF THE CONCEPT, NOT A SYNONYM DICTIONARY.
# A dozen entries cannot cover commercial and colloquial product language; real
# coverage needs a maintained terminology database or a licensed thesaurus,
# which is out of scope for this project. Every entry is checked by a test:
# its target code must exist in the bundled nomenclature, and none of its words
# may appear in that code's own hierarchy text (an alias for a word the corpus
# already contains would only paper over the scorer). Keys are mostly English,
# with a few everyday Turkish/German words where the official DE/FR text uses a
# different term.
#
# An alias is a signal blended into the results, not a shortcut: when every
# word of a key appears in the query, its code joins the ranked list at
# ALIAS_SCORE and the ordinary TF-IDF suggestions still follow it, so the
# person sees the curated hit *and* the evidence around it.
_ALIASES: dict[str, str] = {
    "leech": "0106900090",  # Other live animals > Other
    "drone": "8806920090",  # Unmanned aircraft > 250 g - 7 kg > Other
    "nappy": "96190081",  # Napkins and napkin liners for babies
    "crisps": "20052020",  # Thin slices (of potato), fried or baked
    "jeans": "62034231",  # Of cotton > Trousers and breeches > Of denim
    "popcorn": "19041010",  # Prepared foods obtained by swelling cereals > maize
    "sneakers": "64041990",  # Footwear, rubber/plastics soles, textile uppers
    "earbuds": "8518300090",  # Headphones and earphones > Other
    "biro": "96081099",  # Ballpoint pens > Other
    "power bank": "8507600090",  # Electric accumulators > Lithium-ion > Other
    # The CN calls condoms "sheath contraceptives". Latex ones are 4014 10 00,
    # but heading 4014 is missing from the bundled data (a known bundle gap,
    # like 8541), so these point at the only condom code the bundle has.
    "condom": "3926909760",  # Sheath contraceptives of polyurethane
    "prezervatif": "3926909760",  # Turkish for condom
    "kondom": "3926909760",  # German and Turkish for condom
}

# The score an alias hit is reported at. A curator's explicit mapping is not a
# text-similarity estimate, so it takes the same flat 1.0 an exact code lookup
# already does rather than a made-up cosine.
ALIAS_SCORE = 1.0

# Joins a leaf's hierarchical context to its own description. Purely cosmetic:
# `_WORD` below splits on non-word characters, so the ">" never reaches the
# index. Kept as a visible separator anyway because this is the string that
# shows up when an indexed document is printed while debugging a ranking.
_CONTEXT_SEPARATOR = " > "

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
    """A suggested code, its confidence, and the terms that drove the match.

    `hierarchy_path` is the code's English description with its ancestor
    context in front ("Other live animals > Other"), i.e. exactly the text it
    was scored against. `alias` is the curated alias key that produced this
    suggestion, or None for an ordinary scored match.
    """

    hs_code: HSCode
    score: float
    matched_terms: list[str]
    hierarchy_path: str
    alias: Optional[str] = None


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


def _with_context(description: str, context: Optional[str]) -> str:
    """Prepend a leaf's ancestor context to its own description.

    Half of the real nomenclature's leaves describe themselves only relative to
    a parent they never name — "Other", "For feeding purpose" — because the
    source sheets are hierarchical and a child row does not repeat its
    ancestors. Scoring those against a query means scoring a fragment, which is
    how "live leeches for medical purposes" used to reach four petroleum
    residues called "For other purposes". This is the whole of the fix on the
    reading side: the classifier receives richer text, and weighs it with
    exactly the same TF-IDF it always did.

    A leaf that stands on its own has no stored context and is returned
    untouched, which is what keeps "Hazelnuts" and "Optical glass" scoring a
    flat 1.0 against their own names.

    Args:
        description: The code's own description, in some language.
        context: Its ancestor text in the same language, or None.

    Returns:
        The text to index. `description` unchanged when there is no context, or
        when `description` is itself empty — a code with no text in this
        language must not be resurrected by its ancestors alone.
    """
    if not context or not description:
        return description
    return f"{context}{_CONTEXT_SEPARATOR}{description}"


def _alias_hits(tokens: list[str]) -> list[tuple[str, str]]:
    """Return (alias key, code) for every alias whose words all appear in `tokens`.

    Keys go through the same `_tokenize` as the query, so "leeches" in a query
    meets the "leech" key and "sneaker" meets "sneakers".
    """
    present = set(tokens)
    return [(key, code) for key, code in _ALIASES.items() if set(_tokenize(key)) <= present]


def _diversify(results: list, top_n: int) -> list:
    """Take the first `top_n` results, at most MAX_PER_HEADING per 4-digit heading."""
    kept: list = []
    per_heading: Counter = Counter()
    for result in results:
        heading = result.hs_code.code[:4]
        if per_heading[heading] >= MAX_PER_HEADING:
            continue
        per_heading[heading] += 1
        kept.append(result)
        if len(kept) == top_n:
            break
    return kept


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

    Two steps follow the scoring. A curated alias (see `_ALIASES`) whose words
    all appear in the description adds its code at ALIAS_SCORE, replacing that
    code's own score if it had one. Then the ranked list is thinned to at most
    MAX_PER_HEADING suggestions per 4-digit heading before `top_n` is applied.

    Args:
        conn: An open database connection.
        description: Free-text description of the goods, or an HS/CN code.
        top_n: Maximum number of suggestions to return.
        language: Also score against this language's bundled descriptions,
            e.g. "de". Defaults to English-only.

    Returns:
        A single exact match at score 1.0, matched_terms=[], if `description`
        is a known code (its hierarchy_path included); an empty list if it's
        code-shaped but no such code exists; otherwise suggestions above zero
        confidence, most likely first.

    Raises:
        InvalidQueryError: If the description is blank or too long.
    """
    validate_query(description)

    code = as_code(description)
    if code is not None:
        try:
            record = get_by_code(conn, code)
        except HSCodeNotFoundError:
            return []
        context = fetch_all_contexts(conn, "en").get(record.code)
        return [ClassificationResult(record, 1.0, [], _with_context(record.description, context))]

    tokens = _tokenize(description)
    if not any(len(token) > 1 for token in tokens):
        logger.debug("no token longer than one character in %r; nothing to classify", description)
        return []

    records = fetch_all(conn)
    counts = Counter(tokens)

    english_contexts = fetch_all_contexts(conn, "en")
    # Also each result's hierarchy_path: the text a code is scored against is
    # the breadcrumb a person needs to read it, so it is built exactly once.
    english_texts = [
        _with_context(record.description, english_contexts.get(record.code)) for record in records
    ]
    scored = _score_against(conn, english_texts, None, counts)

    translations = fetch_all_translations(conn, language)
    if translations:
        contexts = fetch_all_contexts(conn, language)
        texts = [
            _with_context(translations.get(record.code, ""), contexts.get(record.code))
            for record in records
        ]
        for position, hit in _score_against(conn, texts, language, counts).items():
            best = scored.get(position)
            if best is None or hit[0] > best[0]:
                scored[position] = hit

    aliased = {}
    hits = _alias_hits(tokens)
    if hits:
        positions = {record.code: position for position, record in enumerate(records)}
        for key, alias_code in hits:
            # A corpus without the target (the 20-row mock catalog) simply
            # has nothing to add; the alias never invents a record.
            if alias_code in positions:
                scored[positions[alias_code]] = (ALIAS_SCORE, [key])
                aliased[positions[alias_code]] = key

    # Sorted by position first so ties break on record order, then stably by
    # score — which leaves the English-only path ordered exactly as before.
    results = [
        ClassificationResult(
            hs_code=records[position],
            score=scored[position][0],
            matched_terms=scored[position][1],
            hierarchy_path=english_texts[position],
            alias=aliased.get(position),
        )
        for position in sorted(scored)
    ]
    results.sort(key=lambda result: result.score, reverse=True)
    logger.debug("classified %r into %d suggestion(s)", description, len(results))
    return _diversify(results, top_n)

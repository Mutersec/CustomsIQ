"""Shared text validation and fuzzy-matching primitives.

Used by both HS/CN code search and sanctions screening so the two features
score text the same way and validate input in exactly one place.
"""

import re
from difflib import SequenceMatcher

from src.customsiq.exceptions import InvalidQueryError

MAX_QUERY_LENGTH = 500

# A name must have at least this many tokens before the token-overlap signal
# in name_similarity() is trusted (see the comment there).
_MIN_OVERLAP_TOKENS = 2


def validate_query(text: str) -> None:
    """Reject blank or oversized free-text input.

    Args:
        text: Raw user input (a product description or an entity name).

    Raises:
        InvalidQueryError: If the input is empty/whitespace-only, or longer
            than MAX_QUERY_LENGTH characters.
    """
    if not text.strip():
        raise InvalidQueryError("Query must not be empty.")
    if len(text) > MAX_QUERY_LENGTH:
        raise InvalidQueryError(f"Query must be at most {MAX_QUERY_LENGTH} characters.")


def similarity(a: str, b: str) -> float:
    """Return a case-insensitive similarity ratio between two strings, in [0, 1]."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _normalize(name: str) -> str:
    """Lowercase a name, drop punctuation, and collapse whitespace."""
    return " ".join(re.sub(r"[^\w\s]", " ", name.lower()).split())


def name_similarity(a: str, b: str) -> float:
    """Score two entity names, tolerating word order and partial names.

    A single positional ratio is not enough for names, so this takes the best
    of three signals (measured against the demo list):

    - plain ratio        "John Smith" vs "Jane Smith"          -> 0.80
    - token-sorted ratio "John Smith" vs "Smith, John"         -> 1.00 (plain: 0.50)
    - token overlap      "Northwind Maritime" vs
                         "Northwind Maritime Holdings Ltd"     -> 1.00 (plain: 0.73)

    The overlap term is what catches partial company names, which both other
    signals score below a 0.75 threshold. It is only trusted when the shorter
    name has >= 2 tokens, otherwise a lone common surname ("Smith") would
    overlap fully with every record containing it.

    Returns:
        The highest of the applicable signals, in [0, 1].
    """
    norm_a, norm_b = _normalize(a), _normalize(b)
    tokens_a, tokens_b = norm_a.split(), norm_b.split()

    scores = [
        similarity(norm_a, norm_b),
        similarity(" ".join(sorted(tokens_a)), " ".join(sorted(tokens_b))),
    ]

    shortest = min(len(tokens_a), len(tokens_b))
    if shortest >= _MIN_OVERLAP_TOKENS:
        shared = set(tokens_a) & set(tokens_b)
        scores.append(len(shared) / shortest)

    return max(scores)

"""Sanctions / denied-party screening against the stored entity list."""

import logging
import sqlite3
from typing import NamedTuple, Optional

from src.customsiq.config import settings
from src.customsiq.database import fetch_all_entities
from src.customsiq.matching import _normalize, name_similarity, validate_query
from src.customsiq.models import SanctionedEntity

logger = logging.getLogger(__name__)

#: A one-word query ("Sberbank") hits every record carrying that word, but only
#: when the word is distinctive: on the OFAC bundle sberbank is in 15 records,
#: vtb 17, gazprom 10, while company is in 573, bank 124 and mohammad 73.
#: Measured against the bundle; re-check if the list grows a lot.
_RARE_TOKEN_MAX_RECORDS = 25


class ScreeningMatch(NamedTuple):
    """A sanctioned entity that a screened name may refer to."""

    entity: SanctionedEntity
    score: float


def screen_entity(
    conn: sqlite3.Connection, name: str, threshold: Optional[float] = None
) -> list[ScreeningMatch]:
    """Screen a name against the sanctions list and return every plausible hit.

    Unlike `search.search`, this takes no `limit`: an analyst has to see every
    entity above the threshold, since a silently truncated hit list would be a
    compliance failure rather than just a worse ranking.

    Args:
        conn: An open database connection.
        name: Person or organisation name to screen.
        threshold: Minimum similarity score to report. Defaults to
            `settings.screening_threshold`.

    Returns:
        Matches scoring at or above the threshold, highest score first.

    Raises:
        InvalidQueryError: If the name is empty/whitespace-only, or longer
            than MAX_QUERY_LENGTH characters.
    """
    validate_query(name)
    cutoff = settings.screening_threshold if threshold is None else threshold

    logger.debug("screening name=%r threshold=%.2f", name, cutoff)
    entities = fetch_all_entities(conn)
    tokens = _normalize(name).split()
    word_hits: set[int] = set()
    if len(tokens) == 1 and len(tokens[0]) >= 3:
        holders = {id(e) for e in entities if tokens[0] in _normalize(e.name).split()}
        if len(holders) <= _RARE_TOKEN_MAX_RECORDS:
            word_hits = holders
    matches = [
        ScreeningMatch(entity, score)
        for entity in entities
        if (score := 1.0 if id(entity) in word_hits else name_similarity(name, entity.name))
        >= cutoff
    ]
    matches.sort(key=lambda match: match.score, reverse=True)
    if matches:
        logger.info("screening hit: %r matched %d listed record(s)", name, len(matches))
    return matches

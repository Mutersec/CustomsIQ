"""FastAPI HTTP surface for HS code search."""

import sqlite3

from fastapi import FastAPI, HTTPException, Query

from src.customsiq.config import settings
from src.customsiq.database import get_connection, seed
from src.customsiq.exceptions import InvalidQueryError
from src.customsiq.search import search

app = FastAPI(title="CustomsIQ")

_conn: sqlite3.Connection = get_connection(settings.database_path)
seed(_conn)


@app.get("/search")
def search_hs_codes(
    q: str = Query(..., description="Free-text product description"),
    limit: int = Query(5, ge=1, le=50),
) -> list[dict]:
    """Return the HS codes whose description best matches `q`.

    Reuses `src.customsiq.search.search`, the same function the CLI calls,
    so ranking logic is defined in exactly one place.
    """
    try:
        results = search(_conn, q, limit=limit)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        {
            "code": r.hs_code.code,
            "description": r.hs_code.description,
            "category": r.hs_code.category,
            "score": r.score,
        }
        for r in results
    ]

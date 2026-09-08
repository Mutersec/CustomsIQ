"""FastAPI HTTP surface for HS code search and sanctions screening."""

import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.customsiq.config import settings
from src.customsiq.database import get_connection, seed
from src.customsiq.embargo_screener import screen_entity
from src.customsiq.exceptions import InvalidQueryError
from src.customsiq.search import search

app = FastAPI(title="CustomsIQ")

# Resolved from this module, not the working directory: the deployed process
# may be started from anywhere, and a missing directory would raise on import.
_STATIC_DIR = Path(__file__).parent / "static"

_conn: sqlite3.Connection = get_connection(settings.database_path)
seed(_conn)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/", response_class=FileResponse, include_in_schema=False)
def index() -> FileResponse:
    """Serve the single-page web frontend.

    An explicit route rather than mounting StaticFiles at "/", which would be
    greedy enough to shadow /docs and the API routes.
    """
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    """Liveness check and basic service info."""
    return {"service": "CustomsIQ API", "docs": "/docs", "status": "running"}


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


@app.get("/screen")
def screen_name(
    name: str = Query(..., description="Person or organisation name to screen"),
) -> list[dict]:
    """Return every sanctioned entity that `name` may refer to.

    Reuses `src.customsiq.embargo_screener.screen_entity`, the same function
    the CLI calls, so screening logic is defined in exactly one place.
    """
    try:
        matches = screen_entity(_conn, name)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        {
            "name": m.entity.name,
            "country": m.entity.country,
            "list_source": m.entity.list_source,
            "date_added": m.entity.date_added,
            "score": m.score,
        }
        for m in matches
    ]

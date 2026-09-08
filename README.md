# CustomsIQ

A trade-compliance toolkit for customs and foreign-trade operations. This
repository's first module, **HS Code Search** (Turkish: *GTİP*), lets a user
type a free-text product description and get back the closest-matching
Harmonized System tariff codes — via CLI or HTTP.

## Problem

Classifying a product under the correct HS/GTİP code is a manual,
error-prone step in customs declarations: an operator has to search a
multi-thousand-entry tariff schedule by memory or keyword guesswork.
Misclassification causes wrong duty rates, customs delays, and compliance
risk. This module automates the first pass — given a plain-language product
description, rank the tariff codes most likely to apply.

## Architecture

```
src/customsiq/
├── models.py           # HSCode: the (code, description, category) record
├── database.py          # SQLite schema, connection, seed data, get_by_code()
├── search.py            # Query validation + similarity ranking
├── exceptions.py         # InvalidQueryError, HSCodeNotFoundError
├── config.py             # pydantic-settings, reads .env
├── logging_config.py     # logging setup shared by CLI and API
├── main.py               # Interactive CLI entry point
└── api.py                # FastAPI /search endpoint (reuses search.py)
```

- **Storage**: SQLite (`sqlite3`, standard library) — a single `hs_codes`
  table (`code TEXT PRIMARY KEY`, `description TEXT`, `category TEXT`).
- **Matching**: `difflib.SequenceMatcher` (standard library) scores each
  stored description against the query and returns the top N by similarity.
- **Config**: `pydantic-settings` reads `CUSTOMSIQ_*` environment variables
  (or a `.env` file — see `.env.example`) instead of hardcoded paths.
- **Errors**: `InvalidQueryError` (bad input) and `HSCodeNotFoundError`
  (unknown code) are raised from `search.py`/`database.py` and translated to
  HTTP 400 in the API; the CLI catches and logs them instead of crashing.
- **CLI and API share one `search()` function** — no duplicated ranking logic.
- **Sample data**: 20 representative HS codes across Electronics, Textile,
  Food, Pharmaceutical, Automotive, Furniture, Plastics, and Metals, used to
  seed the database on first run.

## Architecture Decisions

**Why `difflib` and not `rapidfuzz`/`thefuzz`:** `difflib.SequenceMatcher` is
standard library — zero extra dependency, zero install/version-pinning
surface, and its O(n·m) per-comparison cost is negligible at the current
scale (tens to low-thousands of records, scored linearly on every query).
It's also "good enough" for descriptions that are mostly literal product
names, which is what the seed data and expected queries look like.

**When to migrate to `rapidfuzz`:** swap `_similarity()` in `search.py` for
`rapidfuzz.fuzz.WRatio` (or a token-sort/token-set scorer) once any of these
hold:
- the real GTİP dataset (tens of thousands of rows) makes linear-scan search
  measurably slow — `rapidfuzz` is C-optimized and meaningfully faster;
- queries need to be robust to word order or extra/missing tokens (e.g.
  "trousers cotton men's" vs. "men's cotton trousers"), which token-based
  scorers handle and `SequenceMatcher` does not;
- fuzzy matching needs to run against thousands of queries per second (a
  batch reclassification job), where `rapidfuzz.process.extract` with its
  C implementation clearly outperforms pure-Python `difflib`.

The change is contained to one function, so the migration is a small, later
decision — not a design commitment made now.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # optional: override CUSTOMSIQ_DATABASE_PATH / CUSTOMSIQ_LOG_LEVEL
```

## Usage

### CLI

```bash
python -m src.customsiq.main
```

```
CustomsIQ - HS Code Search (type 'quit' to exit)

Product description: cotton t-shirt
1. 6109100000  (78%)  Cotton T-shirts, knitted  [Textile]
2. 6110200000  (52%)  Cotton pullovers and sweaters  [Textile]
...
```

### API

```bash
uvicorn src.customsiq.api:app --reload
curl "http://localhost:8000/search?q=cotton+t-shirt&limit=3"
```

### As a library

```python
from src.customsiq.database import get_connection, seed
from src.customsiq.search import search

conn = get_connection("customsiq.db")
seed(conn)
results = search(conn, "lithium battery", limit=3)
for r in results:
    print(r.hs_code.code, r.score, r.hs_code.description)
```

## Development

```bash
ruff check .              # lint
black .                   # format
mypy src                  # type check
pytest --cov --cov-report=term-missing --cov-fail-under=80   # tests + coverage gate
```

CI (`.github/workflows/ci.yml`) runs all four on every push and pull request.

## License

MIT

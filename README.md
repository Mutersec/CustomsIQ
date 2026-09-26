<div align="center">

# 🛃 CustomsIQ

### Trade compliance toolkit for customs & foreign trade operations
**Classify goods under the right HS / CN tariff code, screen counterparties against sanctions
lists, and calculate the duty owed.**

[![CI](https://github.com/Mutersec/CustomsIQ/actions/workflows/ci.yml/badge.svg)](https://github.com/Mutersec/CustomsIQ/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)
![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen)
![Tests](https://img.shields.io/badge/tests-420%20passing-brightgreen)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![Ruff](https://img.shields.io/badge/lint-ruff-261230?logo=ruff&logoColor=white)
![Black](https://img.shields.io/badge/style-black-000000)
![Mypy](https://img.shields.io/badge/typed-mypy-2A6DB2)
![License](https://img.shields.io/badge/license-MIT-green)

**[🌐 Live demo](https://customsiq-gs0u.onrender.com/)** · [📖 API reference](https://customsiq-gs0u.onrender.com/docs)

<sub>Hosted on a free Render instance that sleeps when idle — the first request may take ~30 s to wake.</sub>

**🇬🇧 English** · [🇹🇷 Türkçe](README.tr.md) · [🇩🇪 Deutsch](README.de.md)

</div>

---

> **ℹ️ About the demo dataset.** The live demo's tariff-code catalog is now **real**: the full
> EU Combined Nomenclature 2026, 13,753 codes, trilingual (EN/DE/FR) — see
> [🌍 The real EU Combined Nomenclature 2026](#-the-real-eu-combined-nomenclature-2026) below for
> exactly what that means and how it's kept working on Render's ephemeral free tier (it's
> committed to the repo, not fetched — survives every restart with zero network access).
> **The sanctioned-party list and duty/tariff rates are still fictional mock data** — only the
> product-code catalog is real; production use of any part of this tool still requires the
> official sources linked throughout this README.

---

## 📑 Table of contents

| | | |
|---|---|---|
| [🎯 Problem](#-problem) | [✨ Features](#-features) | [🏗️ Architecture](#️-architecture) |
| [🧠 Design decisions](#-design-decisions) | [⚙️ Setup](#️-setup) | [🚀 Usage](#-usage) |
| [🌐 API reference](#-api-reference) | [🧪 Quality & testing](#-quality--testing) | [🌍 The real EU Combined Nomenclature 2026](#-the-real-eu-combined-nomenclature-2026) |
| [🗺️ Roadmap](#️-roadmap) | [📁 Project layout](#-project-layout) | [📄 License](#-license) |

---

## 🎯 Problem

Assigning the correct **CN code** (the EU *Combined Nomenclature*, which extends the international
HS code to 8 digits, and to 10 in TARIC) is one of the slowest and most error-prone steps in a
customs declaration. Today it is done by hand, against a tariff schedule with tens of thousands of
lines.

| Pain point | Business consequence |
|---|---|
| 🔍 Manual lookup across a huge tariff schedule | Slow declarations; results depend on which operator is on shift |
| ❌ Misclassification | Wrong duty rate, penalties, held shipments |
| 🧠 Knowledge locked in people's heads | Slow onboarding, no auditable rationale for a chosen code |

**CustomsIQ automates the first pass:** give it a plain-language product description, get back a
ranked shortlist of tariff codes with a similarity score — a starting point a human expert confirms,
not a black box that decides alone.

---

## ✨ Features

| | Feature | Description |
|---|---|---|
| 🔍 | **Fuzzy search** | Free-text description → CN/TARIC codes ranked by similarity score |
| 🧠 | **Code classification** | TF-IDF suggestions with a confidence score and the terms behind each |
| 🚫 | **Sanctions screening** | Name → denied-party hits, tolerant of word order and partial names |
| 💶 | **Duty calculation** | Code + origin + value → duty owed, with the rate and reason explained |
| 📋 | **Human-review audit trail** | Approve/reject/flag any classification, screening or duty result — append-only |
| 🕘 | **Versioned CN codes (SCD Type 2)** | Every changed description/category keeps its prior value, timestamped, via `GET /codes/{code}/history` |
| 📊 | **Analytics dashboard** | Read-only overview of reference data, review activity and import runs via `GET /dashboard/stats` |
| ⚠️ | **Composite risk scoring** | One explainable score combining classification confidence, screening and duty — `GET /assess-risk` |
| 🖥️ | **Web UI** | Single-page frontend served at `/` — no build step, no framework, no CDN |
| 📥 | **Real-data import** | Load the official EU CN nomenclature from a local file, versioning any changes |
| 💻 | **Interactive CLI** | Search codes or run `screen <name>` from the same prompt |
| 🌐 | **REST API** | `GET /search` and `GET /screen` on FastAPI, with auto-generated `/docs` |
| 🗄️ | **Zero-setup storage** | SQLite via the standard library, seeded with 20 codes + 18 mock entities |
| 🧩 | **SAP GTS terminology view** | Renders results in SAP GTS vocabulary and a BAPIRET2-shaped structure — a labelled simulation, not a system connection |
| 📄 | **Invoice extraction** | Upload a PDF invoice and the classification, duty and risk forms arrive pre-filled — text-layer PDFs, pure Python, nothing stored |
| 🔐 | **RBAC** | Four roles over real accounts — sanctions sign-off needs a compliance officer, and the audit trail names the session, not a text box |
| 🐘 | **Dual backend** | The same SQL runs on PostgreSQL — opt in with one env var, SQLite stays the default |
| ⚙️ | **Env-based config** | `pydantic-settings` reads `.env` — no hardcoded paths or thresholds |
| 🚨 | **Typed errors** | `InvalidQueryError`, `HSCodeNotFoundError` → clean HTTP 400 / 404 semantics |
| 🧪 | **Enforced quality** | ruff + black + mypy + 98% coverage, gated in CI on every push |

---

## 🏗️ Architecture

Two features — **CN code search** and **sanctions screening** — sit on one shared matching layer.
The CLI and the HTTP API are thin adapters over `search()` and `screen_entity()`; scoring and
validation logic exists in exactly one place and is never duplicated.

```mermaid
flowchart LR
    subgraph Interfaces
        CLI["💻 main.py<br/>Interactive CLI"]
        API["🌐 api.py<br/>FastAPI /search · /classify<br/>· /screen · /calculate-duty · /review<br/>· /codes/{code}/history · /dashboard/stats<br/>· /assess-risk"]
        IMPORT["📥 import_cn_codes.py<br/>CLI import tool"]
    end

    SEARCH["🔍 search.py<br/>rank CN codes"]
    CLS["🧠 cn_classifier.py<br/>TF-IDF + explain"]
    SCREEN["🚫 embargo_screener.py<br/>rank sanctions hits"]
    DUTY["💶 tariff_calculator.py<br/>select rate + compute"]
    REVIEW["📋 review.py<br/>submit + fetch decisions"]
    DASH["📊 dashboard.py<br/>aggregate stats"]
    RISK["⚠️ risk.py<br/>composite assessment"]
    MATCH["🧩 matching.py<br/>validate + similarity"]
    DB[("🗄️ database.py<br/>SQLite · hs_codes · sanctioned_entities<br/>· tariff_rates · review_decisions<br/>· hs_code_history · cn_code_versions")]
    EXC["🚨 exceptions.py"]
    CFG["⚙️ config.py<br/>.env"]

    CLI --> SEARCH
    CLI --> CLS
    CLI --> SCREEN
    CLI --> DUTY
    CLI --> REVIEW
    CLI --> RISK
    API --> SEARCH
    API --> CLS
    API --> SCREEN
    API --> DUTY
    API --> REVIEW
    API --> DASH
    API --> RISK
    API --> DB
    IMPORT --> DB
    DASH --> DB
    RISK --> CLS
    RISK --> SCREEN
    RISK --> DUTY
    SEARCH --> MATCH
    CLS --> MATCH
    SCREEN --> MATCH
    SEARCH --> DB
    CLS --> DB
    SCREEN --> DB
    DUTY --> DB
    REVIEW --> DB
    DUTY -. raises .-> EXC
    MATCH -. raises .-> EXC
    DB -. raises .-> EXC
    REVIEW -. raises .-> EXC
    CFG --> CLI
    CFG --> API
    CFG --> SCREEN
```

### Module responsibilities

| Module | Responsibility |
|---|---|
| `models.py` | `HSCode`, `SanctionedEntity`, `TariffRate`, `ReviewDecision`, `HSCodeVersion` and `ImportRun` — the immutable records |
| `database.py` | SQLite schema, connection, seed data, `fetch_all*()`, `get_by_code()`, `upsert_hs_codes_with_history()` (SCD Type 2) |
| `matching.py` | Input validation + similarity scoring (**shared by both features**) |
| `search.py` | Ranks CN codes by description similarity |
| `cn_classifier.py` | Suggests codes by TF-IDF term weighting, reporting the terms that matched |
| `embargo_screener.py` | Ranks sanctions-list hits by name similarity |
| `tariff_calculator.py` | Selects the applicable duty rate and computes what is owed |
| `review.py` | Records and lists human reviewer sign-offs on past decisions (audit trail) |
| `dashboard.py` | Read-only aggregation of reference data, review activity and CN imports for `/dashboard/stats` |
| `risk.py` | Composes classify/screen/duty into one explainable composite risk score |
| `exceptions.py` | `CustomsIQError` → `InvalidQueryError`, `HSCodeNotFoundError`, `RateNotFoundError` |
| `config.py` | `pydantic-settings`; reads `CUSTOMSIQ_*` env vars and `.env` |
| `logging_config.py` | Shared logging setup — plain formatter to stdout, no `print()` anywhere |
| `main.py` | Interactive CLI entry point (search + `screen <name>`) |
| `api.py` | FastAPI app: serves the frontend at `/`, plus `/search`, `/classify`, `/screen`, `/calculate-duty`, `/review`, `/review/history`, `/codes/{code}/history`, `/dashboard/stats`, `/assess-risk`, `/health` |
| `scripts/import_cn_codes.py` | CLI import tool: parses a CN export and versions any changes via `upsert_hs_codes_with_history()` |
| `static/index.html` | The whole web frontend — inline CSS, vanilla `fetch()`, zero dependencies |

### Data model

```sql
CREATE TABLE hs_codes (
    code        TEXT PRIMARY KEY,   -- e.g. "6109100000"
    description TEXT NOT NULL,      -- e.g. "Cotton T-shirts, knitted"
    category    TEXT NOT NULL       -- e.g. "Textile"
);

CREATE TABLE sanctioned_entities (
    name        TEXT PRIMARY KEY,   -- e.g. "Northwind Maritime Holdings Ltd"
    country     TEXT NOT NULL,      -- ISO 3166-1 alpha-2, e.g. "CY"
    list_source TEXT NOT NULL,      -- e.g. "EU Consolidated Financial Sanctions List"
    date_added  TEXT NOT NULL       -- ISO 8601 date, e.g. "2023-04-12"
);

CREATE TABLE tariff_rates (
    hs_code           TEXT NOT NULL,  -- e.g. "6109100000"
    country_of_origin TEXT NOT NULL,  -- ISO alpha-2, or "ALL" for a standard MFN rate
    rate_type         TEXT NOT NULL,  -- "standard" or "preferential"
    rate_percent      REAL NOT NULL,  -- e.g. 12.0
    trade_agreement   TEXT,           -- NULL for standard rates
    valid_from        TEXT NOT NULL,  -- ISO 8601 date the rate takes effect
    PRIMARY KEY (hs_code, country_of_origin, valid_from)
);

CREATE TABLE review_decisions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,  -- audit rows have no natural key
    subject_type       TEXT NOT NULL,   -- "classification" | "screening" | "duty"
    subject_reference  TEXT NOT NULL,   -- sha256(subject_type + normalized input), see below
    decision           TEXT NOT NULL,   -- "approved" | "rejected" | "flagged"
    reviewer_name      TEXT NOT NULL,   -- the authenticated username (API), or free text (CLI/pre-RBAC)
    comment            TEXT,            -- optional note
    reviewed_at        TEXT NOT NULL    -- ISO 8601 timestamp
);

-- Who signed off, when the signer was an authenticated account. A review row
-- with no entry here was written without authentication (the CLI, or before
-- accounts existed) and is reported as such. Keyed by row id, never by name,
-- so a historical free-text "alice" can't be claimed by someone registering
-- that username later. A separate table rather than a column on
-- review_decisions for the same reason hs_code_history is separate: CREATE
-- TABLE IF NOT EXISTS never alters an existing database.
CREATE TABLE review_authorship (
    review_id  INTEGER PRIMARY KEY,  -- the review_decisions row
    user_id    INTEGER NOT NULL      -- the authenticated author
);

CREATE TABLE users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT NOT NULL UNIQUE,  -- case-folded on the way in
    password_hash  TEXT NOT NULL,         -- pbkdf2_sha256$<iterations>$<salt>$<hash>
    role           TEXT NOT NULL,         -- viewer | analyst | compliance_officer | admin
    created_at     TEXT NOT NULL
);

CREATE TABLE sessions (
    token_hash  TEXT PRIMARY KEY,  -- sha256 of the token; the token itself is never stored
    user_id     INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL      -- checked on read, so logout and expiry are immediate
);

CREATE TABLE hs_code_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,  -- history rows have no natural key
    code          TEXT NOT NULL,     -- the hs_codes.code this version belongs to
    description   TEXT NOT NULL,     -- the description as it read during this version
    category      TEXT NOT NULL,     -- the category as it read during this version
    valid_from    TEXT NOT NULL,     -- ISO 8601 timestamp this version became current
    valid_to      TEXT,              -- ISO 8601 timestamp superseded, NULL if still current
    version_label TEXT NOT NULL      -- the import run that produced this version, e.g. "CN2026"
);

CREATE TABLE cn_code_versions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    version_label       TEXT NOT NULL,     -- e.g. "CN2026"
    source_description  TEXT,              -- e.g. the imported file's name
    imported_at         TEXT NOT NULL,     -- ISO 8601 timestamp the run completed
    row_count           INTEGER NOT NULL   -- leaf CN codes processed in this run
);
```

---

## 🧠 Design decisions

### Why `difflib` instead of `rapidfuzz` / `thefuzz`?

`difflib.SequenceMatcher` ships with Python. That means **zero extra dependencies**, nothing to pin
or audit, and no install friction — while being entirely adequate at the current data scale.

| | `difflib` *(chosen)* | `rapidfuzz` |
|---|---|---|
| **Dependency** | ✅ Standard library | ⚠️ Third-party + C extension |
| **Speed at ~10² rows** | ✅ Imperceptible | ✅ Imperceptible |
| **Speed at ~10⁵ rows** | ❌ Noticeably slow | ✅ C-optimized, far faster |
| **Word-order tolerance** | ❌ Positional matching only | ✅ `token_sort` / `token_set` scorers |
| **Batch throughput** | ❌ Pure Python | ✅ `process.extract`, multi-threaded |

### 🔀 When to migrate

Swap `similarity()` in `matching.py` for `rapidfuzz.fuzz.WRatio` as soon as **any** of these becomes true:

1. **📈 Scale** — the real tariff schedule (tens of thousands of rows) makes the linear scan measurably slow.
2. **🔤 Word order** — queries like *"trousers cotton men's"* must match *"Men's cotton trousers"*, which positional matching handles poorly.
3. **⚡ Throughput** — a batch reclassification job needs thousands of queries per second.

> The swap is contained to **one function**, so this stays a cheap decision to make later — not a
> design commitment being made today.

### Other deliberate calls

| Decision | Rationale | Upgrade path |
|---|---|---|
| **SQLite by default, Postgres optional** | Single-node, read-mostly reference data; zero ops overhead. The connection layer now speaks both — `CUSTOMSIQ_DATABASE_URL` switches backends without touching a module | Make Postgres the default if multi-writer concurrency or durable hosted state arrives |
| **One shared connection** with `check_same_thread=False` | Simple, works with FastAPI's threadpool | Connection pool once concurrent writes appear |
| **Logging, not `print()`** | Same output path for CLI and API; level controlled by config | — |
| **No `EmbargoScreeningError`** | Screening's input validation is identical to search's, so it reuses `InvalidQueryError` rather than duplicating a class | Add one if screening grows a genuinely distinct failure mode |
| **Validation inside `matching.py`** | Search, screening, CLI and API all inherit it; impossible to bypass by adding a new caller | — |
| **`review_decisions` uses `INTEGER PRIMARY KEY AUTOINCREMENT`**, unlike the other three tables | Audit rows aren't naturally unique — the same `subject_reference` can legitimately get several decisions over time | — |
| **`review_decisions` is append-only** | Models the four-eyes / human-review principle common in trade compliance tools like SAP GTS: a corrected decision is a new row, never an edit, so the history is never lost. `reviewer_name` is now the authenticated account for anything submitted through the API (see [🔐 Authentication](#-authentication-without-a-dependency)); CLI and pre-RBAC rows keep their free text and are labelled as unauthenticated rather than reinterpreted | Tie accounts to an external IdP (SSO/SCIM) instead of local passwords |
| **CN code history lives in a separate `hs_code_history` table**, not `valid_from`/`valid_to` columns added onto `hs_codes` itself | `hs_codes` keeps its existing `code TEXT PRIMARY KEY` and its two read functions (`fetch_all`, `get_by_code`) stay byte-for-byte unchanged — nothing to filter, nothing to forget. It's also the only migration-safe option: this project has no schema migrations, and `CREATE TABLE IF NOT EXISTS` never alters an existing table, so columns added to `hs_codes` would never appear in anyone's existing `customsiq.db` file | Backfill an opening history row per pre-existing code if a real deployment needs full-depth history from day one |

### 🕘 Versioned CN codes (SCD Type 2)

Re-importing CN reference data used to silently overwrite `hs_codes` in place
(`ON CONFLICT DO UPDATE`) — if a classification or duty decision was made against an old
description and the nomenclature was later re-imported with changed data, there was no way to
reconstruct what the system "knew" at decision time. `scripts/import_cn_codes.py` now versions
every actual change using the SCD Type 2 pattern common in BI/data-warehouse tooling (SAP BW's
change-document tables are the same idea): `hs_codes` still holds one current row per code, exactly
as before, while `hs_code_history` keeps every prior value, closed rather than deleted.

Importing "CN2025" (a new code), then "CN2026" (the same code, description reworded):

| Table | After CN2025 | After CN2026 |
|---|---|---|
| `hs_codes` | `6109100000` → *"Cotton T-shirts, knitted"* | `6109100000` → *"Cotton T-shirts, knitted or crocheted"* (old value gone here, exactly like today) |
| `hs_code_history` | one open row: *"...knitted"*, `valid_to = NULL`, `version_label = "CN2025"` | that row now **closed** (`valid_to` set) **plus a new open row**: *"...knitted or crocheted"*, `version_label = "CN2026"` |
| `cn_code_versions` | `CN2025`, `row_count = 1` | `CN2026`, `row_count = 1` |

`GET /codes/6109100000/history` returns both `hs_code_history` rows, oldest first — the old
description survives, it isn't deleted. Re-importing "CN2026" a second time with **identical**
data adds nothing to either history table: only `cn_code_versions` logs that the run happened,
with 0 changes. `search.py`, `cn_classifier.py`, `tariff_calculator.py` and `embargo_screener.py`
are untouched by any of this — `tariff_calculator.py` never reads `hs_codes` at all, and the other
two already call `fetch_all()`/nothing-else, which returns exactly what it always did.

This also strengthens the audit trail from the human-review layer: `review_decisions` records
*that* a decision was reviewed, and CN code history now makes it possible to reconstruct what
nomenclature data was active at that time.

### 📊 Dashboard: the reporting layer over Phases 1 & 2

`dashboard.py` adds no new business logic and makes no decisions — it's a read-only aggregation
of what `review.py` and the CN pipeline already recorded, composing existing `database.py` reads
(`fetch_all`, `fetch_all_entities`, `fetch_review_decisions`, `fetch_cn_import_runs`, plus two
small new counting primitives) into one `GET /dashboard/stats` call for the frontend's Dashboard
panel. One adaptation worth noting: `cn_code_versions` (Phase 2) only ever stored `row_count`
per import run, not a new/changed/unchanged split — that split existed only transiently inside
`upsert_hs_codes_with_history()` and was never persisted. Rather than add columns to store it
retroactively, the dashboard derives **changed vs. unchanged** per run from how many
`hs_code_history` rows carry that run's `version_label` (one `GROUP BY` query, not three
separate counts) — an honest reading of what was actually recorded, not a fabricated breakdown.

### ⚠️ Composite risk scoring

Real risk-based customs controls (SAP GTS Compliance Management included) don't score
classification, screening and duty independently — a shipment's overall risk is a function of
all three together. `risk.py` adds `assess_shipment()`, which calls `classify()`,
`screen_entity()` and `calculate_duty()` — their existing public signatures, nothing new — and
combines the three into one composite score:

```
composite = 0.6 × screening + 0.25 × classification + 0.15 × duty      (each factor in [0, 1])
level = "high" if composite ≥ 0.5, "medium" if ≥ 0.2, else "low"
```

| Factor | Weight | Rule | Why |
|---|---|---|---|
| **Screening** | 0.6 | Real hit → `1.0`; near-miss (a hit only at a lower watch threshold, `0.55` vs. the compliance threshold of `0.75`) → `0.4`; nothing → `0.0` | A real hit is disqualifying, not just risky — at 0.6 weight, a hit alone (`0.6`) already clears "high" on its own, regardless of how clean the other two factors are |
| **Classification** | 0.25 | `1 − top_confidence`; no match at all → `1.0`; code given directly (nothing to infer) → `0.0` | Low confidence means the wrong HS code might get applied — a data-quality problem, not a compliance violation, hence well below screening's weight |
| **Duty** | 0.15 | `min(rate_percent / 20, 1.0)`, `+0.15` if preferential, clamped to `1.0`; missing rate → flat `0.6` | 20% sits above every seeded standard rate (16.9%, footwear, is the highest); the preferential bump reflects a real fraud vector — a trade-agreement claim is exactly what gets re-verified in an audit, even at a low or zero resulting rate |

Two things worth being explicit about, not left implicit:

- **The duty factor is clamped**, `min(min(rate_percent/20, 1) + 0.15, 1.0)`, not just
  `+ 0.15` unclamped. Nothing in the data model caps `TariffRate.rate_percent`, so a preferential
  rate at or above the 20% ceiling is a real possibility the schema allows, even though today's
  seed data doesn't happen to contain one — the clamp is correct on the data model's terms, not
  just today's fixtures, and is covered by a dedicated test using a synthetic 90% rate.
- **No audit record.** A risk assessment is not persisted and is not reviewable via
  `review_decisions` — recomputing it is cheap (three existing function calls, no new I/O), and
  making it reviewable would mean widening `review.py`'s closed `_VALID_SUBJECT_TYPES` set, which
  this phase deliberately doesn't touch. A risk assessment isn't a new kind of decision anyway —
  it's a lens over the three decisions that are already reviewable, telling a reviewer *which* of
  those three to look at first, not adding a fourth thing to approve or reject.

`InvalidQueryError` from any of the three underlying calls (a malformed HS code, bad country,
negative value) is never caught and converted into a score — bad input is a request problem, and
surfaces as HTTP `400` exactly like every other endpoint. The CLI's `risk` command only supports
the HS-code path, not free-text description: a flat REPL line can't unambiguously hold two
separate free-text fields (description and party name) the way `duty <code> <country> <value>`
and `screen <name>` can each hold one. The API and frontend (structured form fields) support both.

### 🛑 QA audit Bug #6: some findings are absolute, and a blend can't say so

**What was wrong.** A shipment with a confirmed denied-party match scored `0.6609` — over the
"high" line, and correctly so. But a blended number still *reads* as "elevated, use judgement",
and there is no judgement to use: a confirmed sanctions hit is a stop, full stop. The weighted
score was answering a question ("how much total risk is here?") that isn't the question a
compliance officer needs answered first ("may this ship at all?").

**Why the score was kept anyway.** The obvious fix — force the composite to `1.0` on a hit — was
rejected. It would destroy the very thing the score is for: the weights make the reasoning
auditable, and flattening them throws away the classification and duty evidence that is still
worth reading *about a shipment that happens to be blocked*. The two answers are different
kinds of statement, so they're now two fields, not one number carrying both jobs:

| | |
|---|---|
| `composite_score` / `level` | unchanged, still `0.6609` / `high` — how much risk, and why |
| `override` | `"sanctions_hit"` or `null` — whether the answer is already settled |

The trigger is the **screening factor alone**: `screening.score == 1.0`, a match at
`screen_entity()`'s normal compliance threshold. It is deliberately independent of the other
two factors — no confidently classified, low-duty shipment can soften a confirmed match — and
the 0.4 near-miss tier deliberately doesn't qualify, because a near miss is a prompt to look
closer, not a decision. A string rather than a boolean, because it records *which* rule fired:
"blocked because of a confirmed hit" is a different audit statement from "blocked because a
blend crossed 0.5", and the frontend uses the same value to pick its message.

**What it caught.** `sap_gts_bridge` derived `DOCUMENT_STATUS` from the level, mapping
`high → BLOCKED`. That was already right for every confirmed hit — but only by arithmetic
accident: a hit contributes `1.0 × 0.6 = 0.6`, which clears the `0.5` threshold on its own.
Those are two independently tunable constants. Rebalance the weights to `0.45`, or lift the
threshold to `0.65` — both ordinary tuning changes — and a confirmed sanctions match would
quietly stop being BLOCKED, with no test to catch it. GTS now reads the override, so the block
follows the finding rather than the blend. Emitted `TYPE`/`NUMBER`/`MESSAGE` values and row
order are byte-identical; only the status derivation's basis changed. There's a regression test
that retunes the threshold and asserts the document is still BLOCKED.

In the UI the override is a solid red banner **above** the score, never instead of it — the
categorical answer first, the weighted evidence for it immediately underneath. Translated
EN/TR/DE like the rest of the interface.

### ☁️ What RBAC needs on Render: nothing

**No new environment variable is required for login to work on the live demo, and
nothing in `requirements.txt` changed** — so Render's build is byte-identical to the
one before this phase, and no dashboard action is needed. That is a direct consequence
of the session design: opaque tokens stored in the database need no signing secret, so
there is no `SECRET_KEY` to set, rotate or leak. (A JWT or Starlette's signed-cookie
middleware would have required exactly that variable to be configured by hand before
login worked live.)

Two honest caveats, both consequences of the free tier this demo already documents:

- **Accounts are ephemeral.** The filesystem resets, so registrations and role changes
  disappear on restart and the demo accounts are re-seeded — the same behaviour the
  rest of the seeded data already has. Don't reuse a real password.
- **`Secure` on the session cookie is derived, not hardcoded**, from `X-Forwarded-Proto`
  (Render terminates TLS at a proxy, so the app itself sees plain HTTP). Hardcoding it
  would have broken `http://localhost`; ignoring it would have sent the cookie in the
  clear.

As after Phases 5 and 6, the one thing worth a human glance: confirm the service's
Runtime and build command are unchanged. Nothing here should have touched them.

### 🐳 Docker for local dev, not for Render (yet)

Adding a `Dockerfile` to a repo whose Render service was never configured with one is exactly
the kind of change worth reasoning about before making, not after — Render *can* build from a
`Dockerfile` if a service's Language is set to Docker, and getting that wrong could mean the live
demo tries to build/start differently than it does today. Researched against Render's own docs
before writing anything: enabling Docker is described as a **service-creation-time** dashboard
setting (*"apply the following settings in the Render Dashboard during service creation: 1. Set
the Language field to Docker"*) — there's no documented mechanism for an *already-created*
service to re-detect and switch runtime because a `Dockerfile` shows up in a later push. This
repo also has no `render.yaml` or `Procfile`, confirming the live service's build/start commands
and runtime live entirely in Render's dashboard, outside this repo — pushing files here cannot
rewrite that.

Given that, `Dockerfile`/`docker-compose.yml` live at the repo root (the conventional location)
rather than tucked into a subdirectory to dodge a detection mechanism the research above says
doesn't apply to an existing service anyway. The one thing worth a human, one-time check: open
the Render dashboard for this service and confirm Language/Runtime is still its current native
setting, not "Docker" — a zero-cost confirmation given the reasoning above, not an expected
problem, since I can't see that dashboard myself to verify it directly.

### 🧵 One shared SQLite connection, now actually thread-safe

Found while building this phase, and worth writing down because the symptom was
alarming and the cause was latent long before RBAC: the app keeps **one** SQLite
connection for the process and FastAPI runs sync routes in a threadpool, so several
requests genuinely touch it at once. `check_same_thread=False` only silences Python's
guard — it does not make sharing safe. This machine's SQLite is compiled
`SQLITE_THREADSAFE=2` (multi-thread: one connection per thread) and Python reports
`sqlite3.threadsafety == 1`, meaning threads may share the module but **not** a
connection.

Before this phase the app got away with it because concurrent database work was rare.
RBAC put a session lookup on *every* request, and the latent race became routine:
first a garbled read (`Could not decode to UTF-8 column 'username'`), then a
segfault — a `SIGSEGV` that took the whole server down mid-login.

The fix is a lock-guarded proxy (`database._SerializedConnection`), the same shape
`pg_adapter.PgConnection` already uses for Postgres: every statement runs under one
lock, and its rows are **fetched before the lock is released** — returning a live
cursor would have moved the unsafe read outside the lock and fixed nothing. A
regression test drives 24 parallel signed-in request rounds through a threadpool; with
the wrapper removed it reproduces the segfault, so the guard is verified rather than
assumed. The Postgres path is untouched (psycopg handles this itself).

### 🐘 Dual-backend: SQLite default, Postgres opt-in

Postgres was added *alongside* SQLite, not instead of it, and the reasoning is a cost argument
rather than a taste one.

**Why not switch outright.** The whole suite runs against `:memory:` in well under a second with
no server and no driver; a full switch would make every local `pytest` depend on a live
PostgreSQL (or testcontainers) to test code whose behaviour is identical either way. The live
demo gains nothing either — it intentionally serves mock data with fast cold starts on a
filesystem that resets, so re-seeding is the design, not a defect Postgres would fix. And the
hosting cost is real: **Render's free PostgreSQL expires 30 days after creation** (inaccessible
unless upgraded to a paid plan, with a 14-day grace period before deletion, one free database per
workspace, 1 GB) — [Render docs](https://render.com/docs/free). A portfolio link that quietly
breaks every month is worse than one that stays up. Running one set of SQL on two backends also
demonstrates more than picking either one: it shows the data layer is genuinely abstracted.

**Why a ~150-line adapter and not SQLAlchemy Core.** Same test the `openpyxl` and scikit-learn
calls got: does the dependency remove the problem? It doesn't. The hardest dialect difference
here — `ON CONFLICT … DO UPDATE` — is *identical* on both backends, while Core's upsert is
dialect-specific (`dialects.postgresql.insert` vs `dialects.sqlite.insert`), so the branch stays
either way. Meanwhile Core would rewrite all ~18 statements on the SQLite path — the path the
live site runs — and land a new import in every default test run. `src/customsiq/pg_adapter.py`
is imported lazily, only inside `get_connection`'s Postgres branch, so `psycopg` stays an
optional extra. Its ceiling is marked in the source: the `?` → `%s` translation is a naive
replace, fine while no statement holds a literal `?` or `%` (there's a test sweeping all of them);
past that, sqlglot or Core, not more regexes.

**What actually differs, verified against a real `postgres:16` container — not assumed:**

| | SQLite | PostgreSQL | Handling |
|---|---|---|---|
| Placeholders | `?` | `%s` | translated in the adapter |
| `id` columns | `INTEGER PRIMARY KEY AUTOINCREMENT` | no equivalent | rewritten to `GENERATED ALWAYS AS IDENTITY` |
| `rate_percent REAL` | 8-byte float | **4-byte `float4`** — `16.9` reads back as `16.899999618…` | rewritten to `DOUBLE PRECISION`; a test asserts `== 16.9` exactly |
| New row id | `cursor.lastrowid` | psycopg has none | `… RETURNING id` on Postgres only; the SQLite path keeps its exact existing sequence |
| `FROM (SELECT …)` | alias optional | alias required before PG 16 | added `AS changed_codes` (valid on both) |
| Multi-statement `SCHEMA` | `executescript` | no such method | adapter splits and runs each statement |
| Text `ORDER BY` | byte order | collation-dependent | the compose database is created with `--locale=C` |
| Row shape | tuples | tuples *(psycopg's default)* | pinned explicitly to `tuple_row` — every row here is read positionally (`HSCode(*row)`), so `dict_row` would unpack column **names** into fields and silently succeed with garbage |

Unordered `SELECT`s have no guaranteed row order on either backend, so ties in search ranking may
come out in a different order there. No `ORDER BY` was added to "fix" that — it would change
today's SQLite behaviour — and the parity tests deliberately assert no tie ordering.

**The Postgres schema is derived from the single SQLite `SCHEMA` string**, not kept as a second
copy, so the two backends cannot drift apart. The seven decision modules are unchanged down to
their `sqlite3.Connection` annotations: none of them runs SQL, they only hand `conn` back to
`database.py`, so the Postgres branch returns the wrapper via `cast`.

### 🧩 SAP GTS terminology view — a simulation, not an integration

> ⚠️ **This is a terminology and data-shape simulation, not an SAP integration.**
> CustomsIQ is not connected to any SAP system and never has been. This layer reshapes
> CustomsIQ's own results into structures whose field names and vocabulary mirror
> SAP GTS — the documented `BAPIRET2` return structure and GTS's own functional-area
> and document-status terminology — so that the domain concepts are recognisable at a
> glance. **The output is not a valid IDoc or BAPI payload and no real SAP system would
> accept it.** Real integration would require licensed SAP GTS plus an SAP BTP ABAP
> Environment (or an on-premise SAP system reachable over RFC/OData) — none of which
> this project has, uses, or claims. It exists to demonstrate familiarity with SAP GTS
> concepts, nothing more.

The same sentence travels *inside every payload* (`"SIMULATION": true` and a
`DISCLAIMER` string in the `HEADER`) and sits at the top of the UI panel, so the
output stays self-labelling if it is ever copied somewhere this README isn't.

**What maps to what.** SAP GTS is organised into three functional areas: **Compliance
Management** (SPL screening, embargo checks, Legal Control), **Customs Management**
(declarations, classification, duty determination) and **Risk Management** (Preference
Processing, letters of credit, restitution).

| CustomsIQ | Existing function | SAP GTS equivalent | Area |
|---|---|---|---|
| Denied-party screening | `embargo_screener.screen_entity()` | **Sanctioned Party List (SPL) Screening** — compares partner data against uploaded list entries and blocks the document on a hit | Compliance Mgmt |
| Human review / audit trail | `review.submit_review()` | The **block / release decision and its check log** — GTS blocks a document when a check fails, and it stays blocked until someone releases it | Compliance Mgmt |
| Classification | `cn_classifier.classify()` | **Classification** — determining a commodity code for a product | Customs Mgmt |
| Duty calculation | `tariff_calculator.calculate_duty()` | **Duty determination**; where a preferential rate applies, the *result* of **Preference Processing** | Customs Mgmt / Risk Mgmt |
| Composite risk | `risk.assess_shipment()` | No single GTS object — the outcome across all three areas, which is why it renders as a multi-area document |

Two details worth being precise about, because they are the kind of thing an SAP
reviewer checks:

- **Preference Processing is GTS *Risk* Management, not Customs Management.** Duty
  determination belongs to Customs Management; preferential-origin determination is a
  Risk Management function. `calculate_duty` touches both, so its rendered message is
  tagged to whichever applied.
- **`review_decisions` is not Legal Control.** Legal Control specifically means
  export-licence determination for dual-use goods: GTS blocks an item when no licence
  can be assigned, and only assigning one lifts the block. CustomsIQ has **no licence
  master data, no dual-use classification and no embargo-by-country check**, so
  claiming that mapping would be false precision. What `review_decisions` genuinely
  models is the block/release workflow and check log that sits on top of *any* failed
  compliance check.

**The output shape.** `BAPIRET2` is SAP's standard return structure, and it is
reproduced field-for-field, including the real lengths — values are truncated to them
rather than emitted at arbitrary width:

| Field | Type | Len | Used for |
|---|---|---|---|
| `TYPE` | CHAR | 1 | `S` success · `E` error · `W` warning · `I` info · `A` abort |
| `ID` | CHAR | 20 | Message class `ZCUSTOMSIQ_GTS`. The `Z` prefix is SAP's customer namespace — the conventional way of saying "not a standard SAP object" |
| `NUMBER` | NUMC | 3 | Stable number per outcome (`001` SPL hit, `020` preferential rate applied, …) |
| `MESSAGE` | CHAR | 220 | The rendered text |
| `LOG_NO` | CHAR | 20 | The CustomsIQ `subject_reference`, truncated to the real width |
| `LOG_MSG_NO` | NUMC | 6 | Serial within the log |
| `MESSAGE_V1`–`V4` | CHAR | 50 | The substituted variables, the way SAP composes messages |
| `PARAMETER` | CHAR | 32 | Which GTS service produced it |
| `ROW` | INT4 | — | Position in the RETURN table |
| `FIELD` | CHAR | 30 | The CustomsIQ factor behind it |
| `SYSTEM` | CHAR | 10 | `CUSTOMSIQ` — a logical-system name, not a real SAP SID |

What is real: those field names, types and lengths, and the GTS area names. What is
CustomsIQ's own construction: the message class, the message numbers, the header
envelope and the `BLOCKED` / `PENDING` / `RELEASED` / `NOT_BLOCKED` status vocabulary.

**Worked example** — the same pinned assessment the risk section and the CLI examples
already use (`assess_shipment(conn, "NO", "Northwind Maritime", 1000, description="cotton t-shirt")`
→ `0.6609`, high):

| ROW | TYPE | NUMBER | PARAMETER | MESSAGE |
|---|---|---|---|---|
| 1 | `E` | `001` | `SPL_SCREENING` | Sanctioned party list hit for 'Northwind Maritime' — real sanctions match: Northwind Maritime Holdings Ltd (1.00) |
| 2 | `I` | `010` | `CLASSIFICATION` | Commodity code 6109100000 determined — top match 6109100000 at 84.65% confidence |
| 3 | `S` | `020` | `PREFERENCE_DUTY` | Preferential duty rate applied — preferential rate 0.0% |
| 4 | `E` | `030` | `RISK_ASSESSMENT` | Composite risk HIGH (0.6609) — document blocked pending review |

`DOCUMENT_STATUS: "BLOCKED"`. Every number there comes from the existing assessment;
`sap_gts_bridge.py` performs no arithmetic of its own — it takes already-computed
result objects, never a database connection, and calls none of the decision
functions. Tests assert exactly that, on the function signatures and the source.

### 📄 Invoice extraction: what it reads, and what it can't

Upload a commercial invoice and the classification, duty and risk forms arrive
pre-filled. It is a **convenience layer, not a decision engine**:
`document_extraction.py` turns a PDF into strings and numbers, and the decisions stay
where they already live. The module imports none of the seven decision modules — a
test asserts that — so it cannot quietly become a second classifier. It also never
calls them itself: the endpoint returns fields, the user reviews and edits them, and
then presses the buttons that already existed. Thin composable pieces beat one opaque
action that decides on a document's behalf.

**The one production dependency, and why it was allowed.** This is the first phase to
add a package to `requirements.txt` — the file Render's build installs, which Phases 6
and 7 deliberately kept untouched. Unavoidable here, since the feature *is* PDF
parsing, so the choice was verified rather than assumed before committing to it:
`pypdf==6.19.0` ships a `py3-none-any` wheel (**no platform-specific wheel exists at
all**, so nothing compiles), requires Python ≥3.9 which matches this project's floor,
and has exactly one runtime dependency — `typing_extensions`, already present via
pydantic. Checked after installing, not just on PyPI: the installed package contains
no `.so`, `.pyd` or `.dylib`. No Tesseract, no poppler, no system library.

**Fields, and where each one goes.** Every field exists because an existing function
already takes it as an argument:

| Field | Labels matched | Feeds |
|---|---|---|
| `description` | Description of Goods · Goods Description · Description · Product · Commodity | `classify()` / `assess_shipment(description=)` |
| `hs_code` | HS Code · Commodity Code · Tariff Code · CN Code | `calculate_duty()` / `assess_shipment(hs_code=)` |
| `customs_value` | Invoice Value · Customs Value · Total Amount · Total | `calculate_duty()` / `assess_shipment()` |
| `currency` | read from the value line (EUR/USD/GBP, €/$/£) | display only — this project does no currency conversion, and pretending otherwise would invent one |
| `country_of_origin` | Country of Origin · Origin · Made In | `calculate_duty()` / `assess_shipment()` |
| `party_name` | **Consignee** · Supplier · Exporter · Seller · Shipper | `assess_shipment()` → `screen_entity()` |

`party_name` prefers **Consignee** even when an Exporter line comes first, because
denied-party screening is about the counterparty. Values are normalized only where
this project already defines "valid": `validate_cn_code` for codes,
`validate_country_code` for origins (so `Norway` and `NO` both give `NO`).

**Field detection is labelled-line regex, and that is a deliberate ceiling.** One
pattern per field over a synonym list, plus small normalizers — about 60 lines, no
dependency. The alternative (LayoutLM, donut, spaCy) means model weights and a
torch/transformers stack in a project that **rejected scikit-learn for a 20-row
TF-IDF**, and would still need supervision to beat a labelled match on structured
documents. Stated plainly rather than sold around: **this works on invoices that label
their fields, one per line.** It will *not* read a value out of a borderless table
column, a two-column layout where label and value land far apart in the text stream, a
freeform paragraph, or a non-English document — the labels are English, and TR/DE
labels are a deliberate non-goal. Partial extraction is the normal case, which is why
`missing` and `completeness` are part of every response and why nothing is ever
auto-submitted. One real ambiguity is handled explicitly: `1.234,56` and `12,450.00`
are both understood, by treating whichever separator comes **last** as the decimal
point.

Every field reports the label it matched and the line it came from, the same
explainability contract as `classify`'s `matched_terms` and `risk`'s factor breakdown —
so a reviewer can see *why* a value was picked, not just what it was.

**Scanned PDFs are detected, not silently mishandled.** A page with no text layer comes
back with `has_text_layer: false` and a note saying so, instead of an empty field list
that looks like a parser bug. OCR is **not built** — it is a documented extension
point: `pytesseract` needs the `tesseract-ocr` **system binary**, and Render's native
Python buildpack has no apt layer to install one. That is the same reasoning that keeps
Postgres and Docker off the live path; adding a half-built hook nobody uses would be
worse than naming the boundary.

**Upload security**, in the order it executes:

| Control | Behaviour |
|---|---|
| Authentication | Signed in, any role (`document:extract` → `viewer`). Anonymous callers get `401` **before a byte is read**. Demo accounts are available on request, so the feature stays tryable by anyone who signs in |
| Size | 2 MB, counted over the incoming stream and aborted mid-transfer → `413`. Deliberately not `Content-Length` — a header can lie, and buffering first is the bug worth not having |
| Type | The bytes must start with `%PDF-` → `415`. The filename and the declared `Content-Type` are never trusted, and the filename is never used in a path |
| Structure | At most 10 pages read; encrypted PDFs refused; any parse failure becomes a clean `400`, never a traceback |
| Rate | 10 uploads per account per minute |
| Storage | **Nothing is stored, ever.** The bytes live in a `BytesIO` for one request. No `tempfile`, no `open()`, no upload directory, no database row, no filename or document text in the logs. Two tests enforce it: a source scan for file-writing calls, and a snapshot of the working and temp directories around a real upload |

**Transport is a raw body, not multipart** — `Content-Type: application/pdf` with the
PDF as the request body. FastAPI needs `python-multipart` for multipart uploads, and
the fix for its current DoS advisory (CVE-2026-42561, unbounded part headers) landed in
0.0.27, which requires Python ≥3.10 — above this project's 3.9 floor. Every version
installable here carries an unpatched parser DoS, on the one endpoint that accepts
attacker-controlled bytes. Skipping multipart removes that entire class of parser bug
from the attack surface and costs only the Swagger file-picker widget.

The rate limit is **application memory only** — one dict in the app process, keyed by
username. It touches no database, so the Phase 6 backend choice changes nothing about
it and cannot bypass or duplicate it. What *does* change the effective limit is process
count: two instances would each allow the full quota, and a restart clears it. Correct
for the single instance this runs on; shared state (Redis, or a table) is the upgrade
path if that ever stops being true.

### 🔐 Authentication without a dependency

`reviewer_name` used to be whatever the client typed. Five places in this repo said
so and promised this phase; it is now the signed-in account, and the whole thing
adds **zero packages** — `requirements.txt` is untouched, so the live deployment's
build is byte-identical.

**Sessions, not JWTs.** A session is an opaque `secrets.token_urlsafe(32)` in an
`HttpOnly` cookie; the database stores only its SHA-256, so a database leak yields
no usable session. Plain SHA-256 is right *here* and nowhere else in the auth code:
the token is 256 bits of CSPRNG output, and a slow KDF buys nothing against a secret
that isn't guessable. The reason to prefer this over a JWT is revocation — logout and
role changes take effect on the very next request, where a self-contained token stays
valid until it expires unless you bolt on a denylist, which is a sessions table
wearing a hat. Starlette's own `SessionMiddleware` was not used: it is signed-cookie
based and needs `itsdangerous` (verified: not installed) — a new dependency for a
weaker model. CSRF is covered by `SameSite=Lax`, which keeps the cookie off
cross-site POSTs; `Secure` is set from `X-Forwarded-Proto` (Render terminates TLS at
a proxy) so `http://localhost` still works.

**Passwords: `hashlib.pbkdf2_hmac`, 600,000 iterations.** Same scrutiny the
scikit-learn and openpyxl calls got — and settled by a measurement rather than taste:

| Option | Verdict |
|---|---|
| `argon2-cffi` (argon2id) | The best algorithm, memory-hard, OWASP's first choice. Rejected: a C-extension dependency on the **production** path, to guard mock-data passwords on a demo. |
| `bcrypt` / `passlib` | C extension too; passlib 1.7.4 (2020) is effectively unmaintained and breaks against bcrypt 4.x, and bcrypt silently truncates at 72 bytes. |
| `hashlib.scrypt` | The stdlib memory-hard option and my first choice — **but it does not exist on this project's own interpreter.** Measured: this venv's Python 3.9.6 links LibreSSL 2.8.3, where `hasattr(hashlib, "scrypt")` is `False`. It would work in CI and Docker and fail on the maintainer's laptop. Disqualified on portability, not merit. |
| **`hashlib.pbkdf2_hmac` ✅** | Always present, zero dependencies, OWASP's recommended 600,000 iterations for SHA-256. Measured here: 600k ≈ **160 ms**, 210k ≈ 57 ms. |

The honest cost: **PBKDF2 is not memory-hard**, so an attacker with GPUs gets a
better cost ratio against it than against argon2id. What makes that cheap to revisit
is the storage format — `pbkdf2_sha256$600000$<salt>$<hash>`, Django-style — so the
algorithm and work factor are read back per row and can be upgraded on a user's next
login with no migration. A login for an unknown username still runs the KDF against a
dummy hash, so timing can't enumerate accounts, and the "wrong password" and "no such
user" errors are the same string.

`Settings.password_iterations` keeps the suite fast (`tests/conftest.py` lowers it,
the way Django documents for its own test settings) while one test asserts the
production default really is 600,000 and hashes once at full cost.

### 🛡️ Permission matrix

Four roles, ordered `viewer < analyst < compliance_officer < admin`. The set earns
its keep because one split is real rather than decorative: **denied-party screening
is the regulated sign-off**, so it needs a compliance officer, while classification
and duty are analyst work — a distinction that maps onto the three existing
`subject_type` values instead of inventing new concepts.

Every compute endpoint stays **public**. That is the demo's whole point, and none of
it needs an identity. Authentication guards writes, the firehose read of who-reviewed-what,
and account administration.

| Endpoint | anonymous | viewer | analyst | compliance officer | admin |
|---|:--:|:--:|:--:|:--:|:--:|
| `GET /search` · `/classify` · `/screen` · `/calculate-duty` · `/assess-risk` · `/codes/{code}/history` · `/codes/{code}/translations` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /dashboard/stats` — counts | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /dashboard/stats` — `recent_reviews` (names + comments) | ❌ | ✅ | ✅ | ✅ | ✅ |
| `GET /review/history?subject_reference=…` (one result's trail) | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /review/history` (full audit log) | ❌ 401 | ✅ | ✅ | ✅ | ✅ |
| `POST /review` — `classification`, `duty` | ❌ 401 | ❌ 403 | ✅ | ✅ | ✅ |
| `POST /review` — `screening` | ❌ 401 | ❌ 403 | ❌ 403 | ✅ | ✅ |
| `POST /extract-invoice` (upload) | ❌ 401 | ✅ | ✅ | ✅ | ✅ |
| `POST /auth/register` · `/auth/login` · `/auth/logout` · `GET /auth/me` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /auth/users` · `POST /auth/users/{username}/role` | ❌ 401 | ❌ 403 | ❌ 403 | ❌ 403 | ✅ |

`401` means "not signed in" and `403` means "signed in, wrong role" — a client needs
to tell those apart to decide between showing a login form and showing an
explanation, so they are never interchangeable. Anonymous callers get
`/dashboard/stats` with `recent_reviews: []` and `recent_reviews_restricted: true`;
the counts stay public. Permissions live in one dict in `auth.py`, and an unknown
role or action always denies — a typo can't grant. `dashboard.py` is not involved in
any of this: the redaction happens in the route.

### 👤 Self-registration grants `analyst` — a demo choice, not a model of real onboarding

Signing up gives you the `analyst` role immediately, so a visitor can approve a
classification *and* be refused a sanctions sign-off without anyone provisioning an
account for them. **This is not how RBAC onboarding works in a real trade-compliance
system, and it isn't meant to be.** There, roles are *granted*, never chosen: an
administrator or an IdP/HR group mapping assigns one after the person is verified,
and self-registration either doesn't exist or lands in a pending, no-privileges state
until someone approves it. Handing a signup form the power to sign off on customs
classifications would be a finding in any real audit.

The production-shaped version is one line — set `auth.SELF_REGISTRATION_ROLE` to
`VIEWER`, and new accounts can read the audit trail and nothing else until an admin
promotes them through `POST /auth/users/{username}/role`, which already exists and is
already admin-only. The same reasoning covers the demo accounts existing at all:
appropriate for a mock-data portfolio demo, indefensible anywhere else.

### 🕰️ Historical free-text reviewers are left alone

Rows written before accounts existed — and rows the CLI still writes — carry a name
nobody can vouch for. They are kept exactly as they are, and labelled: the API reports
`"authenticated": false` and the UI shows a neutral **legacy** badge next to the name.

Three things this deliberately does **not** do:

- It doesn't backfill, guess, or delete them.
- It doesn't match on name. `review_authorship` is keyed by **row id**, so a legacy
  row reading `alice` is *not* attributed to someone who later registers as `alice` —
  impersonation-by-registration is impossible by construction, not by policy. There is
  a test that registers the exact legacy name and asserts the row stays unauthenticated.
- It doesn't pretend the CLI is authenticated. Anyone who can run the CLI can already
  write to the database file, so a password prompt there would be theater; its rows
  are labelled like any other unauthenticated row.

### 🔗 Deterministic `subject_reference`

Every reviewable result carries a `subject_reference` — `sha256(f"{subject_type}:{normalized_input}")`
— so that submitting the *same* query twice always audits the *same* subject, letting repeat
submissions link to one shared review history instead of forking a new one each time. The
`subject_type` prefix keeps the three features from ever colliding on the same hash.

Normalization is deliberately case-folding for text inputs (the underlying decision doesn't change
with capitalization) but exact for money (a different customs value **is** a different decision):

| Subject type | Input | `subject_reference` | Same input again? |
|---|---|---|---|
| classification | `"knitted cotton shirt"` | `ca8b1b95…fc3407` | Identical |
| classification | `"KNITTED COTTON SHIRT"` | `ca8b1b95…fc3407` | **Same as above** — case is folded before hashing |
| screening | `"Northwind Maritime"` | `fa9ec5ed…b32c38c` | Identical |
| duty | `hs_code=6109100000, country=DE, value=1000.00` | `8e4b03f6…602e3c2e` | Identical |
| duty | `hs_code=6109100000, country=DE, value=1000.01` | `0a16c715…9c8f53` | **Different** — a different value is a different decision to audit |

(Full hashes and the same assertions live in `tests/test_review.py::TestDeterminism`.)

### 🧠 `/search` vs `/classify` — two algorithms, one dataset

Both rank the same `hs_codes` table, but they answer different questions and fail in different
ways. `/search` is a **lookup**: fast character overlap, good when you roughly know the wording.
`/classify` is a **suggestion engine**: it weighs how *rare* each word is across the nomenclature,
so a distinctive term counts for more than a common one, and it reports which of your terms drove
each hit.

Measured on the sample corpus:

| Query | `/search` (difflib) | `/classify` (TF-IDF) | |
|---|---|---|---|
| `knitted cotton shirt` | `6203420000` Men's cotton **trousers** | `6109100000` **Cotton T-shirts, knitted** | ✅ classify right |
| `lithium battery` | `8507600000` Lithium-ion batteries | same | tie |
| `laptop` | `3926909700` Plastic household articles | `8471300000` laptops | ✅ classify right |

Row 1 is the case that justifies the module: `knitted` appears in only one description, so term
weighting lets it dominate, while character overlap is swayed by the bulk of letters shared with
"cotton trousers". Row 3 shows the reverse failure — difflib returns *something* regardless, where
classify returns nothing when no term is shared rather than dressing noise up as a suggestion.

**Why hand-rolled TF-IDF and not scikit-learn.** The implementation is sklearn's own formula
(smoothed IDF `log((N+1)/(df+1))+1`, L2-normalised vectors, cosine via dot product) in ~40 lines of
stdlib arithmetic, so `TfidfVectorizer` would rank this data near-identically — there is no
accuracy gap to close. Against that: scikit-learn pulls numpy and scipy (~100 MB) into the
production image to rank a 20-row table. And decisively, **explainability would cost more code with
sklearn, not less** — here each term's contribution is `query_weight × doc_weight`, already computed
on the way to the score; with sklearn it would mean reaching into `vectorizer.vocabulary_` and
indexing back into a sparse matrix to recover the same numbers.

Adopt scikit-learn if the corpus passes ~10⁵ rows, or if n-grams or sublinear term frequency are
needed. The classifier index used to be rebuilt on every call — fine at 20 mock codes, ~68 ms at
10,000 — and once the real 13,733-code EU Combined Nomenclature was bundled (see
[🌍 The real EU Combined Nomenclature 2026](#-the-real-eu-combined-nomenclature-2026)) that became
~150 ms per call, so the caching this note already anticipated was implemented: a per-connection
cache correctness-checked against the freshly-fetched rows on every call, not a new dependency.

**One measured wrinkle:** CN descriptions are written in the plural ("cables", "batteries") while
users type the singular. Without plural folding, `cable`, `biscuit`, `laptop` and `battery` each
scored **zero against every code**. The tokenizer therefore folds `-ies → y`, sibilant `-es`, and
`-s`. It is not a stemmer — just the English plural rule the corpus demands.

**QA audit Critical Bug #3: a code typed into either field was scored as if it were a
description.** Both functions assumed their input was always free text. A bare code like
`9505900000` went through the same paths as any description: `/search` diffed its digits
character-by-character against every letters-only description and returned whatever scored
marginally higher — an arbitrary, unrelated top result, the "laptop" row above in miniature but
worse, since digits share almost nothing with letters rather than merely the wrong amount.
`/classify` tokenized it into one opaque number that matched no term in any description's
vocabulary, so — correctly, by its own "no shared term" rule — it dropped the row and returned
`[]`, silently hiding a code that was sitting right there in the table. Neither function called the
project's own `validate_cn_code` (`src/utils/validators.py`) or `database.get_by_code()`, both of
which already existed and were already used elsewhere (`tariff_calculator.py`, invoice extraction,
the `/codes/{code}/history` route) — this reference data just never had a code-lookup path *into*
it. The fix: both functions now check, before scoring, whether the input (separators stripped, the
same convention `document_extraction.py` already used) is a valid CN-8/TARIC-10 code, and if so
return the exact `get_by_code()` hit — or a clean empty result if the code doesn't exist — instead
of running it through text-similarity scoring at all. Free-text input is completely unaffected: the
check is a pure early return that a real description never satisfies.

**QA audit Bug #5: a bare single-character query classified confidently, but wrongly.** The
tokenizer (`_WORD = re.compile(r"[a-z0-9]+")`) has no minimum token length, and `_singular()` only
folds words longer than three characters — so a one-character token, however it arises, flows
straight into the TF-IDF index like any real word. The real 13,753-code EU CN bundle contains 36
distinct single-character tokens (digits `0`–`9`, letters `a`–`z`), mostly stray fragments a hyphen
or apostrophe splits off ("T-shirts" → `t` + `shirts`; "Men's" → `men` + `s`) or unit symbols inside
short descriptions ("175|g or more", "For a current exceeding 16|A..."). IDF weighting discounts a
common token like `a` but does nothing about *how short the document is*: in `"175|g or more"`
(four tokens total) the normalized weight of `g` alone is `0.509` — the dominant term in the whole
vector. Measured before the fix: `classify("g")` returned a confident `0.5885` top match against an
unrelated DNA-sequence chemical code, and `classify("a")` returned `0.4959` against an unrelated
ampere-rating fragment — both indistinguishable, by score alone, from a genuine match. The fix adds
one check to `classify()`: if a query's tokenization produces no token longer than one character, it
returns the same honest `[]` already documented and tested for zero-term-overlap input, before
scoring is even attempted — no new exception type, since this is the same "nothing to classify"
case, just caught earlier. Critically, this is a query-side guard only: the corpus index itself is
untouched, so a real query that merely *contains* an incidental single-character fragment — like
`"cotton t-shirt"` itself — still classifies exactly as before (`0.8464917087617252` against
`6109100000`, byte-for-byte). An index-time fix (stripping single-char tokens from every document,
not just short queries) was measured and rejected: it would have shifted the README's own pinned
`0.6609`/`0.0609` risk-score examples (which use the description `"cotton t-shirt"`) to
`0.6781`/`0.0781` — a real behavior change for no additional protection the query-side guard doesn't
already provide.

### 🌍 QA audit Bug #8: localizing text the server generates

**What was wrong.** All translation in this project happens client-side, in
`static/index.html`'s `STRINGS`/`t()` dictionary. Anything Python *composed* —
the duty explanation, each risk factor's explanation, GTS message text,
exception messages — was injected into the page raw, so it stayed English no
matter which of EN/TR/DE the viewer had selected. Half a sentence would flip
language and the other half wouldn't.

**The fix, and why it's additive.** Duty and risk explanations now travel
twice over: the pre-rendered English sentence, unchanged, plus
`explanation_key` and `explanation_params` carrying the same reasoning
structurally (`{"rate": 12.0, "agreement": "EEA", "origin": "NO"}`). The
browser renders the params through its own per-language template; the CLI and
plain API clients keep reading the sentence. Adding rather than replacing was
forced by a real constraint — `main.py` prints `result.explanation` to a CLI
that has no i18n system at all — and it pays off twice: the REST API stays
backwards compatible, and every existing test that asserts on the English
text kept passing untouched.

This matters more than splicing a number into a translated frame would.
The percent sign alone moves in all three languages — EN `12%`, TR `%12`,
DE `12 %` (DIN 5008) — and the decimal separator with it (`0.82` vs `0,82`),
so each language owns its whole sentence, including word order. The frontend
looks the template up as `t("duty.explanation")[key]`, mirroring the existing
`t("duty.rateType")[rate_type]` idiom, which keeps the key literal in the
source where the i18n completeness test can see it.

**What deliberately stays English, and why.** The SAP GTS `MESSAGE` field.
BAPIRET2 *already is* a key-plus-parameters design — `NUMBER` with
`MESSAGE_V1..V4` — and real SAP resolves message text from T100 tables in a
single session language, not per request; translating per request would make
the simulation less faithful, not more. This panel's whole invariant is that
chrome is translated and payload contents are verbatim: `DOCUMENT_STATUS`,
`FUNCTIONAL_AREAS`, `SOURCE_SYSTEM` and the disclaimer are all already
untranslated, rendered monospace as raw system output. A consumer wanting
localized text uses `NUMBER` + the variables against their own message table,
exactly as they would against a real system. There's a practical reason too:
`MESSAGE` is truncated to its real 220-character BAPIRET2 length, and German
renderings run longer than English, so translations would be silently cut
mid-word.

Exception messages (`InvalidQueryError` and friends) and invoice-extraction
notes also stay English **for now** — 13 of the 20 raise sites live in
modules outside this change's scope, and FastAPI's own 422 validation text is
Pydantic-generated and needs a custom exception handler. Translating a third
of the error surface would leave the app answering some errors in Turkish and
others in English, which is worse than answering all of them consistently.
This is a known remaining gap, not a finished job.

**Two things found while doing it.** `sap_gts_bridge.render_duty` was
branching on English prose — `explanation.startswith("preferential")` —
against the very sentence being localized, so the first translation would
have silently routed every duty message to the "could not be determined"
warning and flipped its `TYPE`/`NUMBER` codes. It now reads the structured
discriminator; the emitted codes are byte-identical, pinned by tests. And the
frontend's `payload.detail || t(...)` treated a 422's `detail` — a *list* of
Pydantic error objects, which is truthy — as a string, rendering the literal
text `[object Object]` in the error box. It now checks the type first, so the
one error class that can never be translated server-side is at least
translated client-side.

### 🚫 Name matching is not product matching

Sanctions screening reuses the same `difflib` core for consistency and zero dependencies, but
names needed two extra signals on top of the plain ratio. Measured against the demo list:

| Query vs. listed name | plain | token-sorted | token overlap |
|---|---|---|---|
| `John Smith` vs `Smith, John` | 0.50 ❌ | **1.00** ✅ | 1.00 |
| `Northwind Maritime` vs `Northwind Maritime Holdings Ltd` | 0.73 ❌ | 0.73 ❌ | **1.00** ✅ |
| `Smith` vs `John Smith` | 0.67 | 0.67 | 1.00 ⚠️ |

Word-order variants need **token sorting**; partial company names need a **token-overlap** term,
since at a 0.75 threshold both other signals miss row 2 outright. The overlap term is only trusted
when the shorter name has ≥ 2 tokens — otherwise a lone surname (row 3) matches every record
containing it. Screening takes the max of the applicable signals and is deliberately
over-inclusive: a false negative lets a sanctioned party through, a false positive costs an
analyst one glance.

QA audit Bug #4 flagged that the screening panel's own copy didn't mention this 2-token floor,
claiming unqualified "partial name" tolerance — fixed by stating the limitation in the UI itself
rather than changing the matching behavior, since the behavior was correct all along.

**This — not product search — is what will justify `rapidfuzz` first.** Those two signals are
hand-rolled versions of its `token_sort_ratio` and `token_set_ratio`, and it also brings
`partial_ratio` and far faster scanning. The real EU Consolidated Financial Sanctions List holds
thousands of entries, rescanned on every screen, and needs alias and transliteration handling that
`difflib` has no answer for.

### 🇪🇺 EU alignment

> Data model and terminology align with EU Combined Nomenclature and EU trade compliance
> frameworks, reflecting the target market (EU-based trade compliance roles).

Concretely, this means:

| Concern | Source of truth |
|---|---|
| Tariff codes & nomenclature | [EU TARIC database](https://ec.europa.eu/taxation_customs/dds2/taric) — CN-8 codes, TARIC-10 with EU subheadings |
| Sanctions & embargo screening | EU Consolidated Financial Sanctions List |
| Preferential duty rates | EU trade agreements |

---

## ⚙️ Setup

```bash
# 1. Clone
git clone https://github.com/Mutersec/CustomsIQ.git
cd CustomsIQ

# 2. Virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Dependencies
pip install -r requirements.txt

# 4. (Optional) configuration
cp .env.example .env
```

### Configuration

All settings are read from environment variables or `.env`:

| Variable | Default | Description |
|---|---|---|
| `CUSTOMSIQ_DATABASE_PATH` | `customsiq.db` | SQLite file path (`:memory:` for an ephemeral DB) |
| `CUSTOMSIQ_DATABASE_URL` | *(unset)* | `postgresql://…` URL. **Takes precedence over `CUSTOMSIQ_DATABASE_PATH` when set**; unset or empty ⇒ SQLite, exactly as before. Any other scheme is rejected at startup |
| `CUSTOMSIQ_LOG_LEVEL` | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, …) |
| `CUSTOMSIQ_SCREENING_THRESHOLD` | `0.75` | Minimum name-similarity score (0–1) for a screening hit |
| `CUSTOMSIQ_PASSWORD_ITERATIONS` | `600000` | PBKDF2-HMAC-SHA256 work factor (OWASP's figure; ≈160 ms per hash) |
| `CUSTOMSIQ_SESSION_TTL_HOURS` | `12` | How long a session cookie stays valid |
| `CUSTOMSIQ_SEED_DEMO_USERS` | `true` | Seed the four published demo accounts into an **empty** users table. Set `false` for a real deployment |
| `CUSTOMSIQ_UPLOAD_MAX_BYTES` | `2097152` | Largest accepted invoice upload (2 MB), enforced while streaming the body |
| `CUSTOMSIQ_UPLOAD_RATE_LIMIT_PER_MINUTE` | `10` | Uploads allowed per account per minute |

### 📄 Extracting an invoice

Sign in (any role), choose a PDF in the **Invoice Extraction** panel and press
**Extract fields**. Each field is shown with the label it was matched on, alongside a
list of anything that wasn't found. **Pre-fill the forms** then writes the values into
the classification, duty and risk inputs — and stops there. Nothing is submitted for
you: review or edit the values, then press the button you already know.

```bash
curl -c cookies.txt -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "<username>", "password": "<password>"}'

curl -b cookies.txt -X POST "http://localhost:8000/extract-invoice" \
  -H "Content-Type: application/pdf" \
  --data-binary @invoice.pdf
```

```json
{
  "fields": [
    {"name": "country_of_origin", "value": "NO", "label": "Country of Origin",
     "source_line": "Country of Origin:    Norway"},
    {"name": "customs_value", "value": "12450.0", "label": "Invoice Value",
     "source_line": "Invoice Value:        EUR 12,450.00"},
    {"name": "hs_code", "value": "6109100000", "label": "HS Code",
     "source_line": "HS Code:              6109100000"}
  ],
  "missing": [],
  "completeness": 1.0,
  "page_count": 1,
  "has_text_layer": true,
  "notes": []
}
```

The sample invoice this produces is committed at `tests/fixtures/sample_invoice.pdf`,
and `tests/fixtures/make_invoice_pdfs.py` regenerates it — so the fixture isn't an
opaque binary in the repo.

### 🔐 Signing in

Reading and computing needs no account. Recording a review does. Login now has its
own page (`GET /login`) rather than a panel on the main app — the header's **Sign
in** link navigates there, and a successful sign-in redirects back to `/`.

Four demo accounts are seeded on first start — one per role, so the permission model
can actually be tried rather than just read about. Their credentials are **available
on request** rather than published here or on the page; they're seeded only when the
`users` table is empty, so a deployment with real accounts can't be handed them by a
restart, and `CUSTOMSIQ_SEED_DEMO_USERS=false` turns them off entirely.

Registering gives you `analyst` — see [why that's a demo choice](#-self-registration-grants-analyst--a-demo-choice-not-a-model-of-real-onboarding).

```bash
# sign in (or register), keeping the session cookie
curl -c cookies.txt -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "<username>", "password": "<password>"}'

# the cookie is what authorises a sign-off
curl -b cookies.txt -X POST "http://localhost:8000/review" \
  -H "Content-Type: application/json" \
  -d '{"subject_type": "screening", "subject_reference": "<from the /screen response>", "decision": "flagged"}'

curl -b cookies.txt "http://localhost:8000/auth/me"
curl -b cookies.txt -X POST "http://localhost:8000/auth/logout"
```

In the browser this is the **/login** page; once signed in, the header shows your
username and role, and review controls appear on exactly the results your role may
sign off on. Everything is translated (EN/TR/DE) like the rest of the UI.

### 🐳 Running with Docker

Local development only — **the [live demo](https://customsiq-gs0u.onrender.com/) keeps using
Render's existing native Python deploy, unchanged by this.** No `render.yaml`, no Procfile; this
repo has never told Render how to deploy, so adding a `Dockerfile` here doesn't touch that. See
[🐳 Docker for local dev, not for Render (yet)](#-docker-for-local-dev-not-for-render-yet) below
for the reasoning. Still worth having: environment parity for anyone reviewing or running this
project without setting up a Python venv by hand, and it's what the optional PostgreSQL
service builds on — see [🐘 Running with PostgreSQL](#-running-with-postgresql) below.

```bash
docker build -t customsiq .
docker run -p 8000:8000 customsiq
```

Or for local development, `docker-compose.yml` wires the same three settings as `.env.example`
and adds a named volume so the seeded database survives restarts:

```bash
docker compose up
```

Both serve the same app at **http://localhost:8000/** as running `uvicorn` directly. Multi-stage
build, `python:3.11-slim` (pinned to match CI's `actions/setup-python` version, not this
machine's incidental local one) — the production image installs only the five runtime packages
(`requirements-runtime.txt`), never the dev tooling (ruff/black/mypy/pytest) or test-only deps
(`httpx`, needed solely by `fastapi.testclient.TestClient`). No hot-reload wired up — rebuild
after code changes, a deliberate simplification for what "local dev" needed here, not an
oversight.

### 🐘 Running with PostgreSQL

**Optional, local only. The [live demo](https://customsiq-gs0u.onrender.com/) stays on SQLite** —
see [🐘 Dual-backend: SQLite default, Postgres opt-in](#-dual-backend-sqlite-default-postgres-opt-in)
for why that's a deliberate call rather than an unfinished migration.

`docker-compose.yml` carries a `postgres:16-alpine` service behind a **profile**, so a plain
`docker compose up` is byte-for-byte the SQLite setup it has always been. Opt in with the profile
*and* the URL:

```bash
CUSTOMSIQ_DATABASE_URL=postgresql://customsiq:customsiq@postgres:5432/customsiq \
  docker compose --profile postgres up
```

Outside Docker, install the optional driver first (it is **not** in `requirements.txt`):

```bash
pip install -r requirements-postgres.txt
CUSTOMSIQ_DATABASE_URL=postgresql://customsiq:customsiq@localhost:5432/customsiq \
  uvicorn src.customsiq.api:app
```

The schema is created on first connect, the same way the SQLite file is. To run the PostgreSQL
parity tests, point them at a database whose name contains `test` — the fixture drops every table
and refuses to run otherwise:

```bash
docker compose --profile postgres up -d postgres
docker exec customsiq-postgres-1 psql -U customsiq -d customsiq -c "CREATE DATABASE customsiq_test;"
CUSTOMSIQ_TEST_POSTGRES_URL=postgresql://customsiq:customsiq@localhost:5432/customsiq_test \
  pytest tests/test_postgres.py
```

Without that variable they skip, so the default `pytest` run stays fast and dependency-free.

---

## 🚀 Usage

### 💻 Interactive CLI

```bash
python -m src.customsiq.main
```

```text
seeded 20 rows into hs_codes
seeded 18 rows into sanctioned_entities
CustomsIQ (type 'quit' to exit)
Enter a product description to search CN codes,
'classify <description>' for ranked suggestions with reasoning,
'screen <name>' to run a sanctions check,
or 'duty <hs_code> <country> <value>' to calculate customs duty.

> cotton t-shirt
1. 6109100000  (74%)  Cotton T-shirts, knitted        [Textile]
2. 6203420000  (57%)  Men's cotton trousers           [Textile]
3. 6204620000  (54%)  Women's cotton trousers         [Textile]
4. 6110200000  (42%)  Cotton pullovers and sweaters   [Textile]
5. 8528721000  (35%)  Color television receivers      [Electronics]

> screen Northwind Maritime
1 potential sanctions match(es) for 'Northwind Maritime':
1. Northwind Maritime Holdings Ltd  (100%)  [CY]  EU Consolidated Financial Sanctions List  listed 2023-04-12

> classify knitted cotton shirt
1. 6109100000  (85% confidence)  Cotton T-shirts, knitted  [Textile]  via: shirt, knitted, cotton
2. 6203420000  (19% confidence)  Men's cotton trousers  [Textile]  via: cotton

> screen Quokka Beachwear
No sanctions match for 'Quokka Beachwear'.

> duty 6109100000 NO 1000
Duty on 6109100000 from NO: 0.00 (0.00% preferential)
  Preferential rate of 0% applied under the EU-Solvia Free Trade Agreement, for which origin NO qualifies.
  Customs value 1000.00 + duty 0.00 = 1000.00

> review duty 8e4b03f6c0353ab018c024b6e7045251867255b083df5637f5d01ef5602e3c2e approved alice confirmed correct
Recorded: approved 1 on duty:8e4b03f6c0353ab018c024b6e7045251867255b083df5637f5d01ef5602e3c2e by alice at 2026-01-01T12:00:00+00:00

> review-history
2026-01-01T12:00:00+00:00  duty:8e4b03f6c0353ab018c024b6e7045251867255b083df5637f5d01ef5602e3c2e  approved  by alice  (confirmed correct)

> risk 6109100000 NO 1000 Northwind Maritime
Risk for 6109100000 from NO, party 'Northwind Maritime': HIGH (0.6609)
  screening       1.0000 (weight 0.60)  real sanctions match: Northwind Maritime Holdings Ltd (1.00)
  classification  0.0000 (weight 0.25)  HS code given directly
  duty            0.1500 (weight 0.15)  preferential rate 0.0%
```

The CLI's `risk` command only supports the HS-code path (`risk <hs_code> <country> <value>
<party_name>`), not free-text description — see [⚠️ Composite risk scoring](#️-composite-risk-scoring)
for why. The API and web UI support a description too.

### 🖥️ Web interface

```bash
uvicorn src.customsiq.api:app --reload
```

Try the **[live demo](https://customsiq-gs0u.onrender.com/)**, or open **http://localhost:8000/** for the web UI
when running locally — both features in one page.

### 🌐 REST API

The same server exposes the JSON API:

Then open **http://localhost:8000/docs** for the interactive Swagger UI.

```bash
curl "http://localhost:8000/search?q=cotton+t-shirt&limit=2"
```

```json
[
  {
    "code": "6109100000",
    "description": "Cotton T-shirts, knitted",
    "category": "Textile",
    "score": 0.7368421052631579
  },
  {
    "code": "6203420000",
    "description": "Men's cotton trousers",
    "category": "Textile",
    "score": 0.5714285714285714
  }
]
```

### 🐍 As a library

```python
from src.customsiq.database import get_connection, seed
from src.customsiq.search import search

conn = get_connection("customsiq.db")
seed(conn)

for result in search(conn, "lithium battery", limit=3):
    print(f"{result.hs_code.code}  {result.score:.0%}  {result.hs_code.description}")
```

---

## 🌐 API reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | **Web frontend** (HTML page) |
| `GET` | `/health` | Liveness check — `{"service": "CustomsIQ API", "docs": "/docs", "status": "running"}` |
| `GET` | `/search` | Ranked CN code matches for a product description |
| `GET` | `/classify` | Ranked code suggestions with confidence and matched terms |
| `GET` | `/screen` | Sanctions-list hits for a person or organisation name |
| `GET` | `/calculate-duty` | Duty owed on a consignment, with the applied rate explained |
| `POST` | `/review` | Record a reviewer's sign-off on a past classification, screening or duty result |
| `GET` | `/review/history` | Recorded review decisions, most recently reviewed first |
| `GET` | `/codes/{code}/history` | One CN code's SCD Type 2 version timeline, oldest first |
| `GET` | `/codes/{code}/translations` | A CN code's German/French descriptions alongside the English one |
| `GET` | `/dashboard/stats` | Aggregate stats: reference data, review activity, CN import runs |
| `GET` | `/assess-risk` | Composite risk score combining classification, screening and duty |
| `POST` | `/extract-invoice` | Read an uploaded invoice PDF and return the fields found in it (sign-in required) |
| `GET` | `/sap-gts/compliance-check` | The same risk assessment, rendered in SAP GTS terminology (simulation) |
| `GET` | `/sap-gts/legal-control/{subject_reference}` | A subject's review decisions as a block/release check log (simulation) |
| `GET` | `/docs` | Interactive Swagger UI (auto-generated) |

**Typed responses.** Every route above declares a Pydantic `response_model`, so `/docs` and
`/openapi.json` show real field schemas — including the BAPIRET2 field names on the two
`/sap-gts/*` routes — rather than an untyped `additionalProperties: true`. This is a typing
addition only: every response body is unchanged, verified by diffing each route's actual JSON
before and after the models were added.

**Security headers.** Every response (successes and errors alike) carries `X-Content-Type-Options:
nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin` and
`X-XSS-Protection: 0`, added by a small global middleware. Deliberately **not** included: a
Content-Security-Policy. The frontend is one file with a large inline `<script>`/`<style>` block,
so a CSP strict enough to mean anything would need `'unsafe-inline'` on both `script-src` and
`style-src` — defeating most of what a CSP is for — or a restructuring of the frontend into
external files, which is real, separate work outside "low-effort headers." Shipping a CSP that's
security theater would be worse than naming the gap.

**`GET /search` parameters**

| Parameter | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `q` | `str` | *required* | 1–500 chars, not blank | Free-text product description |
| `limit` | `int` | `5` | 1–50 | Maximum number of results |

**`GET /classify` parameters**

| Parameter | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `description` | `str` | *required* | 1–500 chars, not blank | Free-text description of the goods |
| `top_n` | `int` | `5` | 1–50 | Maximum number of suggestions |

```bash
curl "http://localhost:8000/classify?description=knitted+cotton+shirt&top_n=2"
```

```json
[
  {
    "code": "6109100000",
    "description": "Cotton T-shirts, knitted",
    "category": "Textile",
    "score": 0.8464917087617252,
    "matched_terms": ["shirt", "knitted", "cotton"],
    "subject_reference": "ca8b1b958f7a9136035ce4106495b252851544092bdce2797bc30b8687fc3407"
  },
  {
    "code": "6203420000",
    "description": "Men's cotton trousers",
    "category": "Textile",
    "score": 0.18940799593138907,
    "matched_terms": ["cotton"],
    "subject_reference": "ca8b1b958f7a9136035ce4106495b252851544092bdce2797bc30b8687fc3407"
  }
]
```

The runner-up scores far lower because it only shares the *common* word `cotton`, while the winner
also matched the rare `knitted` — `matched_terms` makes that visible rather than implicit.

**`GET /screen` parameters**

| Parameter | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `name` | `str` | *required* | 1–500 chars, not blank | Person or organisation name to screen |

Screening takes no `limit`: every hit above the threshold is returned, since a silently truncated
hit list would be a compliance failure rather than just a worse ranking.

**`GET /calculate-duty` parameters**

| Parameter | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `hs_code` | `str` | *required* | CN-8 or TARIC-10 | Code of the goods being imported |
| `country_of_origin` | `str` | *required* | ISO 3166-1 alpha-2 | Where the goods originate |
| `customs_value` | `float` | *required* | >= 0 | Declared customs value |

A preferential rate wins whenever the origin qualifies for one; otherwise the standard MFN rate
applies. A code with **no** rate on record returns `404` rather than zero duty — a gap in the
tariff data is not a duty-free import.

**`POST /review` body**

| Field | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `subject_type` | `str` | *required* | `classification` \| `screening` \| `duty` | What kind of result is being reviewed |
| `subject_reference` | `str` | *required* | not blank | The `subject_reference` from that result — never re-typed, always the value the API already returned |
| `decision` | `str` | *required* | `approved` \| `rejected` \| `flagged` | The reviewer's verdict |
| `comment` | `str \| null` | `null` | — | Optional free-text note |

There is no `reviewer_name` field any more: the reviewer is whoever the session
cookie says it is. It was **removed** rather than accepted-and-ignored, so no client
can believe it set the name on an audit row. Requires a signed-in account —
`analyst` for `classification` and `duty`, `compliance_officer` for `screening`
(see the [permission matrix](#-permission-matrix)); anonymous callers get `401`
and under-ranked ones `403`.

```bash
curl -X POST "http://localhost:8000/review" \
  -H "Content-Type: application/json" \
  -H "Cookie: customsiq_session=$TOKEN" \
  -d '{"subject_type": "duty", "subject_reference": "8e4b03f6c0353ab018c024b6e7045251867255b083df5637f5d01ef5602e3c2e", "decision": "approved", "comment": "confirmed correct"}'
```

```json
{
  "id": 1,
  "subject_type": "duty",
  "subject_reference": "8e4b03f6c0353ab018c024b6e7045251867255b083df5637f5d01ef5602e3c2e",
  "decision": "approved",
  "reviewer_name": "alice",
  "comment": "confirmed correct",
  "reviewed_at": "2026-01-01T12:00:00+00:00",
  "authenticated": true
}
```

**`GET /review/history` parameters**

| Parameter | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `subject_type` | `str \| null` | `null` | `classification` \| `screening` \| `duty` | Restrict to this subject type |
| `subject_reference` | `str \| null` | `null` | — | Restrict to this subject |
| `limit` | `int` | `50` | 1–200 | Maximum number of decisions returned |

```bash
curl "http://localhost:8000/review/history?subject_type=duty&limit=10"
```

**`GET /codes/{code}/history`** — no parameters beyond the code itself. `404` if the code is
unknown; a code that exists but was never touched by a versioned import (e.g. the seeded demo
data) returns `200 []`, not an error — same "empty list, never an error" convention as `/search`.

```bash
curl "http://localhost:8000/codes/6109100000/history"
```

```json
[
  {
    "code": "6109100000",
    "description": "Cotton T-shirts, knitted",
    "category": "Textile",
    "valid_from": "2025-01-15T09:00:00+00:00",
    "valid_to": "2026-02-01T09:00:00+00:00",
    "version_label": "CN2025"
  },
  {
    "code": "6109100000",
    "description": "Cotton T-shirts, knitted or crocheted",
    "category": "Textile",
    "valid_from": "2026-02-01T09:00:00+00:00",
    "valid_to": null,
    "version_label": "CN2026"
  }
]
```

**`GET /dashboard/stats`** — no parameters, no input to validate. `review_by_decision` and
`review_by_subject_type` always carry all three keys, defaulted to `0`, so a fresh database
renders cleanly rather than forcing the caller to guard against missing keys.

```bash
curl "http://localhost:8000/dashboard/stats"
```

```json
{
  "hs_code_count": 20,
  "sanctioned_entity_count": 18,
  "tariff_rate_count": 18,
  "review_total": 2,
  "review_by_decision": { "approved": 1, "rejected": 0, "flagged": 1 },
  "review_by_subject_type": { "classification": 1, "screening": 0, "duty": 1 },
  "recent_reviews": [ { "id": 2, "subject_type": "duty", "decision": "flagged", "...": "..." } ],
  "import_run_count": 1,
  "recent_import_runs": [
    {
      "version_label": "CN2026",
      "source_description": "cn2026.csv",
      "imported_at": "2026-02-01T09:00:00+00:00",
      "row_count": 10,
      "changed_count": 1,
      "unchanged_count": 9
    }
  ],
  "versioned_code_count": 1
}
```

**`GET /assess-risk`** — exactly one of `description`/`hs_code` is required (`400` if neither or
both are given); `country_of_origin`, `party_name` and `customs_value` are always required.
Combines `classify()`, `screen_entity()` and `calculate_duty()` — see
[⚠️ Composite risk scoring](#️-composite-risk-scoring) for the weights and the reasoning behind
them. This worked example is a real sanctions hit against otherwise clean classification/duty
data — screening alone (weight 0.6) is enough to reach "high":

```bash
curl "http://localhost:8000/assess-risk?description=cotton+t-shirt&country_of_origin=NO&party_name=Northwind+Maritime&customs_value=1000"
```

```json
{
  "level": "high",
  "composite_score": 0.6608770728095686,
  "hs_code": "6109100000",
  "factors": [
    {
      "name": "screening",
      "score": 1.0,
      "weight": 0.6,
      "explanation": "real sanctions match: Northwind Maritime Holdings Ltd (1.00)"
    },
    {
      "name": "classification",
      "score": 0.1535082912382748,
      "weight": 0.25,
      "explanation": "top match 6109100000 at 84.65% confidence"
    },
    {
      "name": "duty",
      "score": 0.15,
      "weight": 0.15,
      "explanation": "preferential rate 0.0%"
    }
  ]
}
```

```bash
curl "http://localhost:8000/calculate-duty?hs_code=6109100000&country_of_origin=NO&customs_value=1000"
```

```json
{
  "hs_code": "6109100000",
  "country_of_origin": "NO",
  "customs_value": 1000.0,
  "rate_percent": 0.0,
  "rate_type": "preferential",
  "trade_agreement": "EU-Solvia Free Trade Agreement",
  "duty_amount": 0.0,
  "total_payable": 1000.0,
  "explanation": "Preferential rate of 0% applied under the EU-Solvia Free Trade Agreement, for which origin NO qualifies.",
  "subject_reference": "8e4b03f6c0353ab018c024b6e7045251867255b083df5637f5d01ef5602e3c2e"
}
```

```bash
curl "http://localhost:8000/screen?name=Northwind+Maritime"
```

```json
[
  {
    "name": "Northwind Maritime Holdings Ltd",
    "country": "CY",
    "list_source": "EU Consolidated Financial Sanctions List",
    "date_added": "2023-04-12",
    "score": 1.0,
    "subject_reference": "fa9ec5ed3f84ae68c8c5729faa18e043297e7ec78aae9ab89bebeef82b32c38c"
  }
]
```

**Status codes**

| Code | Meaning |
|---|---|
| `200` | Success — array of matches (may be empty) |
| `400` | `InvalidQueryError` — blank/oversized query, malformed code, or negative value |
| `404` | `RateNotFoundError` — no duty rate on record for that HS code, or `HSCodeNotFoundError` on `/codes/{code}/history` |
| `422` | Missing/invalid parameter type (FastAPI validation) |

---

## 🧪 Quality & testing

Every push and pull request runs the full gate via [GitHub Actions](.github/workflows/ci.yml):

```mermaid
flowchart LR
    A["📥 Checkout"] --> B["🐍 Python 3.11"] --> C["📦 Install"]
    C --> D["🔎 ruff"] --> E["🎨 black --check"] --> F["🏷️ mypy"] --> G["🧪 pytest ≥80%"]
```

```bash
ruff check .                                                  # lint
black .                                                       # format
mypy src                                                      # type check
pytest --cov --cov-report=term-missing --cov-fail-under=80    # tests + coverage gate
```

### Current coverage

| Module | Coverage |
|---|---|
| `api.py` · `config.py` · `database.py` · `embargo_screener.py` · `matching.py` | 🟢 100% |
| `cn_classifier.py` · `exceptions.py` · `models.py` · `search.py` · `tariff_calculator.py` · `review.py` · `dashboard.py` · `risk.py` | 🟢 100% |
| `scripts/import_cn_codes.py` | 🟢 91% |
| `logging_config.py` | 🟢 100% |
| `main.py` | 🟢 98% |
| `pg_adapter.py` | 🟢 96% |
| `auth.py` | 🟢 100% |
| `document_extraction.py` | 🟢 99% |
| **Total** | **🟢 96.28%** (420 tests in ~5.7 s, gate at 80%) — **no module is excluded from the gate**. `scripts/import_cn_codes.py`'s openpyxl-dependent Excel-reading path is the reason the total isn't higher: openpyxl is optional and not installed in CI, so that code is untested there — the same treatment its pre-existing `_read_excel_rows` already had. The suffix-collapse and leaf-selection *logic* that path calls is extracted into pure functions and fully tested. |

The 13 PostgreSQL parity tests are *not* in that count: they skip unless `CUSTOMSIQ_TEST_POSTGRES_URL`
points at a real server (CI sets it; a plain local `pytest` needs no Postgres and no driver).

### Edge cases under test

| Case | Expected behaviour |
|---|---|
| Empty / whitespace-only query or name | `InvalidQueryError` → HTTP `400` |
| Query longer than 500 characters | `InvalidQueryError` → HTTP `400` |
| SQL-injection-shaped input (`'; DROP TABLE hs_codes; --`) | Handled safely by parameterized queries; table intact |
| Emoji & non-ASCII input (`📱 Handy-Ladegerät`, `Ünal Çelik A.Ş.`) | Scored normally, no crash |
| Reversed name order (`Aleksandr Voronin-Teske`) | Matches the surname-first list entry |
| Partial company name (`Northwind Maritime`) | Matches the full listed name |
| Name matching nothing on the list | Empty result, not an error |
| Unknown exact code lookup | `HSCodeNotFoundError` |
| Description sharing no term with any code | Empty list, never a zero-confidence suggestion |
| Singular query against a plural description (`cable`, `battery`) | Folded and matched |
| Preferential rate available for the origin | Beats the standard MFN rate |
| Rate not yet in force (`valid_from` in the future) | Ignored; falls back to the rate in force |
| HS code with no rate on record | `RateNotFoundError` → HTTP `404`, never zero duty |
| Negative customs value | `InvalidQueryError` → HTTP `400` |
| Zero customs value | Valid — zero duty owed |
| Re-seeding a populated database | Idempotent — no duplicate rows in any table |
| Same classification/screening query, different case | Same `subject_reference` — case is folded before hashing |
| Same duty inputs, different `customs_value` | Different `subject_reference` — a different value is a different decision |
| Two review decisions on the same `subject_reference` | Both persist, most recent first — audit rows are never overwritten |
| Unknown `subject_type` or `decision` on `POST /review` | `InvalidQueryError` → HTTP `400` |
| Re-importing a code with a changed description/category | Old `hs_code_history` row closed (`valid_to` set), new one opened — never deleted |
| Re-importing a code with identical data | No new `hs_code_history` row; `hs_codes` gets a harmless no-op upsert |
| `GET /codes/{code}/history` for a seeded-but-never-versioned code | `200 []`, not an error |
| `GET /codes/{code}/history` for an unknown code | `HSCodeNotFoundError` → HTTP `404` |
| `GET /dashboard/stats` on a fresh database (no reviews, no imports) | All counts `0`, breakdown keys present not missing, empty lists — never `NaN%` on the frontend |
| A real sanctions hit, otherwise clean classification/duty | Screening alone (`0.6 × 1.0`) reaches "high" — the other factors can't dilute it |
| Near-miss + low classification confidence + missing tariff rate together | Land at "medium" (`0.4989`) though none alone would be remarkable |
| Description sharing no term with any code, in a risk assessment | Classification factor scores maximum risk (`1.0`); duty is skipped, not conflated with "rate not found" |
| Neither or both of `description`/`hs_code` given to `/assess-risk` | `InvalidQueryError` → HTTP `400` |
| A preferential duty rate at or above the risk ceiling (synthetic 90% in tests) | Duty factor clamps to `1.0`, never exceeds the documented 0–1 contract |

---

## 🌍 The real EU Combined Nomenclature 2026

Every earlier phase ran the classification/search endpoints against 20 invented codes — good
enough to demonstrate the algorithms, useless for actually finding a real product. This phase
closes that gap **permanently**, not with a live import step: the official EU Combined
Nomenclature 2026 is processed once, bundled as a file committed to this repo
(`data/cn_nomenclature_2026.csv`, 3.1 MB), and loaded into `hs_codes` on every app startup —
including on Render, whose free tier resets the filesystem on every restart. No network access,
no dependency on anything surviving between deploys; the same "process once, commit the result"
approach `tests/fixtures/sample_invoice.pdf` already uses for the invoice-extraction fixtures.

**Real, measured numbers, not estimates:**

| | |
|---|---|
| Source | EU Combined Nomenclature 2026, official Eurostat/DG TAXUD export via [CIRCABC](https://circabc.europa.eu/), English/German/French |
| Leaf codes bundled | **13,733** — every genuinely declarable code, CN-8 and TARIC-10 combined (see the methodology below) |
| Bundle size | 3.1 MB CSV, committed to the repo |
| Added to every cold start | **~90 ms** (CSV parse + upsert into `hs_codes` + upsert into `hs_code_translations`, measured) |
| `classify()` cost at this scale | ~150 ms cold, **~20 ms** once its per-connection cache is warm — see below |
| `search()` cost at this scale | ~440–490 ms per call — no equivalent cache is possible for its character-overlap algorithm; a known, accepted cost of the larger real catalog, stated here rather than left unexplained |

`cn_classifier.py` already carried a comment from an earlier phase naming this exact scenario:
*"the index is rebuilt per call — 0.1 ms at 20 codes, ~68 ms at 10k. Cache it per connection if a
full CN import makes that noticeable."* This import did, so the pre-authorized fix is implemented:
a per-connection cache that compares the freshly-fetched rows against the last-built index and
only recomputes when they actually differ — **not** a row-count check, which would miss an
in-place description update that leaves the count unchanged and serve a stale result. Verified
directly, not just reasoned about: an in-place update was made after populating the cache, and the
very next `classify()` call correctly rebuilt rather than returning the old text. Scores and
rankings are unchanged from before — only the redundant rebuild is skipped. `search.py` has no
equivalent fix: its character-overlap comparison is query-dependent, not corpus-dependent, so
there's no index to cache, and its ~450 ms cost is stated here rather than silently left as-is.

**Where it lives, and why not as new columns.** `hs_codes.description` stays English-only and
unchanged; German and French descriptions live in a **new, separate**
`hs_code_translations(code, language, description)` table, following the exact precedent
[🕘 Versioned CN codes](#-versioned-cn-codes-scd-type-2) already set for `hs_code_history`:
`CREATE TABLE IF NOT EXISTS hs_codes (...)` can never add a column to anyone's existing database
file, so a new table is the only way that reliably reaches every already-created `customsiq.db`.
Fetch a code's translations at `GET /codes/{code}/translations`; a code with none (any of the 20
mock rows below) returns `null` for `de`/`fr`, not an error.

**What "leaf code" actually means, worked out against the real file rather than assumed.** The
source export lists every hierarchy level in one sheet, flagged by a `Hier. Pos.` column: `8` for
CN-8 (Combined Nomenclature) and `10` for TARIC-10 (the EU's more granular customs-declaration
codes). A CN-8 code that has TARIC-10 subdivisions **isn't actually declarable on its own** — real
declarations require the most detailed code available — so it's dropped in favour of its
children; a CN-8 code with no further subdivision is kept as-is. One more wrinkle, verified by
direct inspection rather than assumed away: the two-digit token trailing each code
(`"0101291000 80"`) is a Eurostat *statistical suffix*, not part of the commodity code itself, and
1,098 codes have multiple suffix variants with genuinely different descriptions (weight bands,
"for slaughter" vs. "other"). Since `hs_codes.code` is a primary key, one has to be picked:
suffix `80` (the "no supplementary unit" default, present for every such code) wins; otherwise
whichever variant appeared first. The result: **4,173 CN-8-only leaves + 9,560 TARIC-10 codes =
13,733**, not the ~9,700 a naive `Hier. Pos. == 8` filter would have produced.

**Regenerating the bundle** (a future annual update, or a different language set):

```bash
python scripts/import_cn_codes.py build-bundle \
  Nomenclature_EN.xlsx Nomenclature_DE.xlsx Nomenclature_FR.xlsx \
  --output data/cn_nomenclature_2026.csv
```

This is a one-time/occasional build step — the app never runs it; it only reads the committed
CSV. `scripts/import_cn_codes.py`'s original single-language `import` command (below) is
unchanged and still works for a routine annual refresh once a bundle already exists.

The 20-row mock catalog below is **kept, unchanged, alongside the real data** — not replaced.
`seed()`'s default stays the same 20 codes it has always been (every test fixture in this repo
depends on that, and continues to pass completely unmodified); the real 13,733-code bundle is
added on top, in the live app only. None of the mock codes collide with real ones — verified, not
assumed: `8517120000`, `6109100000` and the rest were invented for earlier phases and don't
correspond to real 2026 CN-8 entries. One honest, minor side effect worth naming: the mock data's
category labels predate `import_cn_codes.py`'s chapter-derived mapping and disagree with it in two
places — chapter 64 (footwear) is `"Textile"` in the mock set but `"Footwear"` in the real one;
chapter 09 (coffee) is `"Food"` in the mock set but `"Vegetable Products"` in the real one. Both
labels appear on the live catalog for their respective chapters, unreconciled — the mock rows are
also used by name in several pinned tests, so "fixing" them was out of scope here.

The database is seeded with **20 representative CN/TARIC codes across 8 categories**, written in
EU Combined Nomenclature style — the original mock set, described above:

| Category | Codes |
|---|---|
| 📱 Electronics | 5 |
| 👕 Textile | 5 |
| 🍫 Food | 5 |
| 💊 Pharmaceutical · 🚗 Automotive · 🪑 Furniture · 🧴 Plastics · 🔩 Metals | 1 each |

<details>
<summary><b>Show all 20 seeded codes</b></summary>

| CN/TARIC code | Description | Category |
|---|---|---|
| `8517120000` | Mobile phones and smartphones | Electronics |
| `8471300000` | Portable automatic data processing machines (laptops) | Electronics |
| `8528721000` | Color television receivers | Electronics |
| `8544421000` | USB cables and data cables | Electronics |
| `8507600000` | Lithium-ion batteries | Electronics |
| `6109100000` | Cotton T-shirts, knitted | Textile |
| `6203420000` | Men's cotton trousers | Textile |
| `6204620000` | Women's cotton trousers | Textile |
| `6110200000` | Cotton pullovers and sweaters | Textile |
| `6402990000` | Footwear with rubber or plastic soles | Textile |
| `0901210000` | Roasted coffee, not decaffeinated | Food |
| `1806320000` | Chocolate blocks, not filled | Food |
| `2009110000` | Frozen orange juice | Food |
| `0406100000` | Fresh cheese | Food |
| `1905310000` | Sweet biscuits | Food |
| `3004900000` | Medicaments for therapeutic use | Pharmaceutical |
| `4011100000` | New pneumatic tires for cars | Automotive |
| `9403300000` | Wooden office furniture | Furniture |
| `3926909700` | Plastic household articles | Plastics |
| `7326909800` | Miscellaneous articles of iron or steel | Metals |

</details>

> ⚠️ This is **demo data** for development and testing. Production use requires the official
> nomenclature from the [EU TARIC database](https://ec.europa.eu/taxation_customs/dds2/taric).

### Sanctions list

The `sanctioned_entities` table is seeded with **18 entries** styled after EU Consolidated
Financial Sanctions List rows — invented trading, shipping and engineering companies plus a few
synthetic person names, stored surname-first the way real lists publish them.

| Field | Example |
|---|---|
| `name` | `Northwind Maritime Holdings Ltd` · `Voronin-Teske, Aleksandr` |
| `country` | `CY`, `AE`, `DE`, `RS`, `MT`, `NL`, … |
| `list_source` | `EU Consolidated Financial Sanctions List` · `EU Dual-Use Export Control Watchlist` |
| `date_added` | `2023-04-12` |

> 🚨 **Every name in this list is fictional.** None correspond to any real sanctioned person or
> organisation, and the list must never be used for actual screening. Production screening
> requires the official EU Consolidated Financial Sanctions List.

### Tariff rates

The `tariff_rates` table is seeded with **18 rows**: standard MFN rates for codes already in the
sample above, plus preferential rates under two trade agreements — including a 0% preference and
one future-dated rate that the `valid_from` filter correctly ignores.

| Field | Example |
|---|---|
| `hs_code` | `6109100000` |
| `country_of_origin` | `NO`, `CH`, `JP`, `KR` — or `ALL` for a standard MFN rate |
| `rate_type` | `standard` · `preferential` |
| `rate_percent` | `12.0` · `0.0` |
| `trade_agreement` | `EU-Solvia Free Trade Agreement` · `EU-Meridian Economic Partnership` · `null` |

> 🚨 **The rates and both trade agreements are fictional.** Real duty rates and preferential
> origins come from the EU TARIC database; never use these figures for an actual declaration.

### Importing a CN nomenclature update

The live demo already runs the real 13,733-code EU Combined Nomenclature 2026 (see
[🌍 The real EU Combined Nomenclature 2026](#-the-real-eu-combined-nomenclature-2026) above) — this
section is for refreshing it, or importing a different single-language CN export locally:

**1. Get the file** (manual — the importer never touches the network):

| Source | What to take |
|---|---|
| [Eurostat RAMON](https://ec.europa.eu/eurostat/ramon/) → *Nomenclatures* → *CN* | The current year's CN, exported as CSV or Excel |
| [TARIC consultation](https://ec.europa.eu/taxation_customs/dds2/taric/) | A goods-code export with English descriptions |

**2. Import it:**

```bash
python scripts/import_cn_codes.py path/to/cn_codes.csv
```

| Option | Default | Purpose |
|---|---|---|
| `--db` | `CUSTOMSIQ_DATABASE_PATH` | Target database; import into a separate file to keep the mock DB intact |
| `--code-column` | auto-detected | Override when the export uses an unfamiliar header |
| `--description-column` | auto-detected | Same, for the description column |
| `--batch-size` | `1000` | Rows written per upsert |
| `--version-label` | a timestamp | Label for this run (e.g. `CN2026`), recorded against any code that changed |

The importer auto-detects the usual RAMON/TARIC column names, derives each code's category from
its HS chapter (the first two digits), skips the chapter/heading rows above the 8-digit leaves,
logs and skips malformed rows rather than aborting, and **upserts `hs_codes` on the code — so
re-running it refreshes the current data instead of duplicating it, exactly as before**. What's
new: any code whose description or category actually changed also gets a closed-and-reopened
entry in `hs_code_history` (see [🕘 Versioned CN codes](#-versioned-cn-codes-scd-type-2) above),
so re-importing never silently loses what a code used to say. Fetch `GET /codes/{code}/history`
to see a code's full timeline — that's also the demo's visible proof of versioning.

Point the app at the imported database to use it:

```bash
CUSTOMSIQ_DATABASE_PATH=cn_full.db uvicorn src.customsiq.api:app
```

Excel input additionally needs `pip install openpyxl`; it is deliberately not a project
dependency, since only this tool would ever use it. Exporting the sheet to CSV avoids it entirely.

> 📜 **Attribution.** The Combined Nomenclature is public reference data of the European Union
> (© European Union), reusable — including redistribution of derived extracts, with attribution —
> under the [Commission's reuse policy](https://ec.europa.eu/info/legal-notice_en).
> `data/cn_nomenclature_2026.csv` **is** such an extract: 13,733 leaf codes and their English,
> German and French descriptions, derived from the official Eurostat/DG TAXUD CIRCABC export and
> committed to this repo under that policy — a change from earlier phases, which only referenced
> the official sources rather than bundling data from them. The sanctioned-party list and duty
> rates elsewhere on this page remain entirely fictional and are unaffected by this.

---

## 🗺️ Roadmap

**Every planned phase has shipped — no scaffolds remain**, and every module is measured by the
coverage gate:

| Module | Status | Scope |
|---|---|---|
| `search.py` | ✅ **Shipped** | Fuzzy CN code search via CLI and REST |
| `cn_classifier.py` | ✅ **Shipped** | TF-IDF classification with confidence and matched terms |
| `embargo_screener.py` | ✅ **Shipped** | Denied-party name screening via CLI and REST |
| `tariff_calculator.py` | ✅ **Shipped** | Duty calculation with preferential-rate selection |
| `review.py` | ✅ **Shipped** | Four-eyes human-review audit trail on all three decisions |
| CN code versioning (SCD Type 2) | ✅ **Shipped** | `hs_code_history` + `cn_code_versions`, surfaced at `GET /codes/{code}/history` |
| `dashboard.py` | ✅ **Shipped** | Read-only reporting layer over Phases 1 & 2, via `GET /dashboard/stats` |
| `risk.py` | ✅ **Shipped** | Composite shipment risk score over classification, screening and duty, via `GET /assess-risk` |
| `auth.py` (RBAC) | ✅ **Shipped** | Accounts, sessions and four roles; `reviewer_name` now comes from the session |
| `document_extraction.py` | ✅ **Shipped** | Invoice PDF upload that pre-fills the classification, duty and risk forms |
| `sap_gts_bridge.py` | ✅ **Shipped** | SAP GTS terminology view over existing results — a labelled simulation, not an integration |
| Real EU Combined Nomenclature 2026 | ✅ **Shipped** | 13,733 real, trilingual leaf codes bundled and loaded at every startup, alongside the original mock data |

Planned extensions: country-level embargo checks and product/destination restrictions, alias and
transliteration handling for entity names, quota/anti-dumping components on top of the duty
calculation, caching the classifier index once a full CN import makes the per-call rebuild
noticeable, **single sign-on against an external identity provider** (SSO/SCIM) in place of
the local password store now that [RBAC ships](#-authentication-without-a-dependency),
per-account lockout or rate limiting on repeated failed logins (today the 160 ms KDF is the
only brake), a CLI `history <code>` command mirroring the API endpoint, a paginated `GET /cn-imports`
endpoint for browsing the full `cn_code_versions` log (`/dashboard/stats` now surfaces the
`fetch_cn_import_runs` data that used to be unexposed, but only the most recent handful — a
dedicated, filterable endpoint is still open if the list needs to be browsed in full), a CLI
`risk` path that accepts a free-text description (today limited to the HS-code path — see
[⚠️ Composite risk scoring](#️-composite-risk-scoring)), and persisted/reviewable risk
assessments if a real deployment ever needs to audit the score itself rather than just the
three decisions it summarizes. Pointing the live deployment at PostgreSQL is deliberately *not*
on this list — the backend already works (see
[🐘 Dual-backend](#-dual-backend-sqlite-default-postgres-opt-in)); what's missing is a database
that doesn't expire after 30 days on a free plan.

---

## 📁 Project layout

```text
CustomsIQ/
├── .github/workflows/ci.yml     # ruff → black → mypy → pytest
├── Dockerfile                   # local-dev image — see 🐳 Running with Docker
├── docker-compose.yml           # app + an optional Postgres service (--profile postgres)
├── .dockerignore
├── requirements-runtime.txt     # runtime-only subset of requirements.txt, used by Dockerfile
├── requirements-postgres.txt    # optional psycopg driver — deliberately NOT in requirements.txt
├── src/
│   ├── customsiq/
│   │   ├── models.py            # HSCode + SanctionedEntity + TariffRate + ReviewDecision + HSCodeVersion + ImportRun records
│   │   ├── database.py          # SQLite/Postgres layer + seed data + SCD Type 2 versioning
│   │   ├── pg_adapter.py        # PostgreSQL dialect adapter — imported only when a URL is set
│   │   ├── matching.py          # shared validation + similarity scoring
│   │   ├── search.py            # CN code ranking
│   │   ├── cn_classifier.py     # TF-IDF classification + explanation
│   │   ├── embargo_screener.py  # sanctions name screening
│   │   ├── tariff_calculator.py # duty rate selection + calculation
│   │   ├── review.py            # human-review audit trail (four-eyes)
│   │   ├── auth.py              # accounts, sessions, roles — stdlib only, no new deps
│   │   ├── document_extraction.py # invoice PDF → fields (pypdf + labelled-line regex)
│   │   ├── sap_gts_bridge.py     # renders results in SAP GTS terms — simulation, not an integration
│   │   ├── dashboard.py         # read-only aggregation over Phases 1 & 2
│   │   ├── risk.py              # composite shipment risk score
│   │   ├── exceptions.py        # typed error hierarchy
│   │   ├── config.py            # pydantic-settings / .env
│   │   ├── logging_config.py    # shared logging setup
│   │   ├── main.py              # CLI entry point
│   │   ├── api.py               # FastAPI app (also serves the frontend)
│   │   ├── api_schemas.py       # Pydantic response models — typing only, no logic
│   │   └── static/
│   │       ├── index.html       # web frontend — single file, no build step
│   │       ├── favicon.png · apple-touch-icon.png · og-image.png  # brand assets (generated once)
│   └── utils/validators.py      # CN/TARIC format & country code validation
├── data/cn_nomenclature_2026.csv # bundled EU Combined Nomenclature 2026 — 13,733 leaf codes, EN/DE/FR
├── scripts/import_cn_codes.py   # official CN file → hs_codes, versioning changes (SCD Type 2);
│                                #   also builds the data/ bundle above (build-bundle subcommand)
├── tests/                       # 358 tests — unit, API, CLI, classification, screening, duty, review, import, dashboard, risk, auth/RBAC, extraction
│   └── fixtures/                #   sample CN export + invoice PDFs (make_invoice_pdfs.py regenerates them)
│   ├── conftest.py              #   lowers the password work factor for the suite
│   ├── helpers.py               #   signed-in TestClient helpers
│                                #   + 13 Postgres parity tests, skipped unless a server is configured
│   └── fixtures/                # sample CN export for the importer's tests
├── pyproject.toml               # ruff · black · mypy · pytest · coverage · [project] metadata
├── requirements.txt
├── LICENSE                      # MIT
└── .env.example
```

---

## 📄 License

Released under the **MIT License**.

<div align="center">

**🇬🇧 English** · [🇹🇷 Türkçe](README.tr.md) · [🇩🇪 Deutsch](README.de.md)

</div>

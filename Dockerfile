# syntax=docker/dockerfile:1
#
# Local-development image, not wired to the live Render deploy (see the
# "🐳 Docker for local dev, not for Render (yet)" section of the README).
#
# Multi-stage even though today's runtime deps are all pure-Python wheels —
# no compiler is strictly needed yet — because it (a) keeps pip's build
# metadata/cache out of the final image regardless, and (b) establishes the
# pattern before a dependency that DOES need a build step (e.g. psycopg2 for
# Phase 6's Postgres migration) shows up.

# Pinned to match .github/workflows/ci.yml's actions/setup-python version —
# the version this project actually verifies against on every push, not the
# incidental version a local venv happens to run, and not pyproject.toml's
# target-version = "py39" (a ruff/black/mypy *syntax-compatibility floor*,
# not a statement about which version runs the code).
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements-runtime.txt .
RUN pip install --no-cache-dir --user -r requirements-runtime.txt

FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

# Only src/ — scripts/ (the CN import CLI tool) and tests/ aren't needed to
# run the web service, so they stay out of the image, same lean-surface
# discipline requirements-runtime.txt already applies to dependencies.
COPY src/ src/

EXPOSE 8000

# Same command documented in the README for local use, bound to 0.0.0.0 as
# any containerized service needs; no --reload — this is a production-style
# start command, not a dev one. Render's own configured start command lives
# in its dashboard (no render.yaml/Procfile in this repo), so this mirrors
# the standard pattern rather than a confirmed exact match — and is never
# used by Render's deploy regardless.
CMD ["uvicorn", "src.customsiq.api:app", "--host", "0.0.0.0", "--port", "8000"]

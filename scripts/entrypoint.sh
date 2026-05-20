#!/bin/bash
# =============================================================================
# Container entrypoint — initialises DB, runs migrations, starts the app.
#
# Order matters:
#   1. init_db  — creates the base schema for SQLite (dev/test).
#                 For MSSQL/PostgreSQL this is a no-op; Alembic owns the DDL.
#   2. alembic upgrade head — apply incremental migrations (idempotent).
#                 Migration 001 is safe if the table was pre-created by
#                 create_all — it checks for existence before creating.
#   3. seed     — optional: run if SEED_ON_STARTUP=true (no-op otherwise).
#   4. uvicorn  — serve the app.
# =============================================================================
set -euo pipefail

echo "=== Azure Governance Platform startup ==="
echo "Environment : ${ENVIRONMENT:-development}"
# Log DB host without password
DB_HOST=$(echo "${DATABASE_URL:-sqlite}" | sed 's|.*@||' | cut -d'/' -f1)
echo "DB host     : ${DB_HOST}"

# Ensure ODBC libraries are found - refresh library cache
echo "--- Refreshing library cache for ODBC ---"
if command -v ldconfig &> /dev/null; then
    ldconfig 2>/dev/null || echo "Note: ldconfig not available (expected for non-root users)"
fi

# Set library path if not already set
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-/usr/lib/x86_64-linux-gnu:/usr/lib:/lib}"
echo "LD_LIBRARY_PATH: $LD_LIBRARY_PATH"

# Test pyodbc import
echo "--- Testing database driver ---"
python -c "import pyodbc; print(f'pyodbc version: {pyodbc.version}')" 2>&1 || echo "WARNING: pyodbc import failed - database may not be accessible"

# 1 — Create base schema tables (idempotent — skips tables that exist)
echo "--- Initialising base schema ---"
python - <<'PYEOF'
from app.core.database import init_db
init_db()
print("Base schema ready.")
PYEOF

# 2 — Run Alembic incremental migrations
echo "--- Running Alembic migrations ---"
if python -m alembic upgrade head; then
    echo "--- Migrations complete ---"
else
    echo "WARNING: Alembic migration failed - schema may be stale."
    echo "         App will attempt to start. Check DB connectivity."
    echo "         Run 'python -m alembic upgrade head' manually once DB is reachable."
fi

# 3 — Optionally seed reference data (run once on fresh deployments)
if [ "${SEED_ON_STARTUP:-false}" = "true" ]; then
    SEED_ARGS=""
    if [ "${SEED_RESET_ALL:-false}" = "true" ]; then
        SEED_ARGS="--reset-all"
        echo "--- SEED_ON_STARTUP=true, SEED_RESET_ALL=true: Seeding (purge + recreate) ---"
    elif [ "${SEED_RESET:-false}" = "true" ]; then
        SEED_ARGS="--reset"
        echo "--- SEED_ON_STARTUP=true, SEED_RESET=true: Seeding (reset mode) ---"
    else
        echo "--- SEED_ON_STARTUP=true: Seeding Riverside tenants ---"
    fi
    if python scripts/seed_riverside_tenants.py ${SEED_ARGS}; then
        echo "--- Seed complete ---"
    else
        echo "WARNING: Seed script failed - app will still start"
    fi
fi

# 4 — Start the application
PORT="${PORT:-8000}"
echo "--- Starting uvicorn on port ${PORT} ---"
# Single worker: APScheduler has no distributed lock; 2+ workers fire
# duplicate sync jobs, causing FK-violation races on riverside_mfa.
exec python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --workers 1 \
    --loop uvloop \
    --http httptools \
    --log-level "$(echo ${LOG_LEVEL:-info} | tr A-Z a-z)"

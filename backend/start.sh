#!/usr/bin/env bash
# Production start script — used by Render Web Service.
# Runs DB migrations then starts uvicorn (no --reload in production).
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Applying database migrations..."
alembic upgrade head

# Seed demo accounts/hospitals if the DB is empty (idempotent — seeds check
# for existing rows before inserting, so re-running on an existing DB is safe).
if [ "${SEED_DEMO:-true}" = "true" ]; then
  echo "==> Seeding demo data (SEED_DEMO=true)..."
  python seed_demo_richness.py || echo "Seed skipped or already seeded."
fi

PORT="${PORT:-${API_PORT:-8000}}"
echo "==> Starting GoldenLine API on port $PORT ..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"

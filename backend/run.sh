#!/usr/bin/env bash
# Convenience launcher for local development.
# Usage: ./run.sh
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install --quiet -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

echo "Applying database migrations..."
alembic upgrade head

if [ "${SEED_DEMO:-true}" = "true" ]; then
  echo "Seeding rich per-hospital demo data (all 25 hospitals, ~50% bed/staff/inventory fill — idempotent, safe to re-run)..."
  python3 seed_demo_richness.py || echo "Richness seed skipped or failed (non-fatal)."
fi

echo "Starting API on http://localhost:8000 (docs at /docs) ..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
API_PID=$!

if [ "${SEED_DEMO:-true}" = "true" ]; then
  echo "Waiting for the API to come up before seeding demo cases..."
  python3 - <<'PY'
import time, urllib.request
for _ in range(30):
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2)
        break
    except Exception:
        time.sleep(1)
PY
  echo "Seeding demo cases/activity (idempotent — safe to re-run)..."
  python3 ../seed_demo.py || echo "Seed skipped or failed (non-fatal)."
  echo "Demo data ready — every console (admin/hospital/control-room/blood-bank/helper) now has data to show."
fi

wait "$API_PID"

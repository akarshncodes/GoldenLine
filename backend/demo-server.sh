#!/usr/bin/env bash
# Demo launcher for the backend API (used by .claude/launch.json).
set -e
cd "$(dirname "$0")"
.venv/bin/python -m alembic upgrade head

if [ "${SEED_DEMO:-true}" = "true" ]; then
  echo "Seeding rich per-hospital demo data (idempotent — safe to re-run)..."
  .venv/bin/python seed_demo_richness.py || echo "Richness seed skipped or failed (non-fatal)."
fi

.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

if [ "${SEED_DEMO:-true}" = "true" ]; then
  .venv/bin/python - <<'PY'
import time, urllib.request
for _ in range(30):
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2)
        break
    except Exception:
        time.sleep(1)
PY
  echo "Seeding demo cases/activity (idempotent — safe to re-run)..."
  .venv/bin/python ../seed_demo.py || echo "Seed skipped or failed (non-fatal)."
fi

wait "$API_PID"

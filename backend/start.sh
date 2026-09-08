#!/usr/bin/env bash
# Production start script — used by Render Web Service.
# Runs DB migrations, starts uvicorn on $PORT (Render's env var), then seeds
# demo data once the API is actually answering (seed_demo.py talks to the
# real HTTP API, not the DB directly).
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Applying database migrations..."
alembic upgrade head

PORT="${PORT:-${API_PORT:-8000}}"
echo "==> Starting GoldenLine API on port $PORT ..."
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" &
API_PID=$!

if [ "${SEED_DEMO:-true}" = "true" ]; then
  echo "==> Waiting for the API to come up before seeding..."
  python - "$PORT" <<'PY'
import sys, time, urllib.request

port = sys.argv[1]
for _ in range(30):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
        break
    except Exception:
        time.sleep(1)
PY
  echo "==> Seeding demo data (SEED_DEMO=true, idempotent — safe to re-run)..."
  SEED_API="http://127.0.0.1:${PORT}" python ../seed_demo.py || echo "Seed skipped or failed (non-fatal)."
fi

wait "$API_PID"

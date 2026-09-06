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

echo "Starting API on http://localhost:8000 (docs at /docs) ..."
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

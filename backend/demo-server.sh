#!/usr/bin/env bash
# Demo launcher for the backend API (used by .claude/launch.json).
set -e
cd "/Users/akarshn/Desktop/SIH /Software/Project/backend"
.venv/bin/python -m alembic upgrade head
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

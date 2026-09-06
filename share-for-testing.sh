#!/usr/bin/env bash
# Expose the locally-running GoldenLine backend + client to the internet via
# free Cloudflare "quick tunnels" (no account needed), so remote teammates can
# test it without being on the same network.
#
# This does NOT start the backend/client dev servers themselves — start those
# first (see memory/project-overview.md's "Run + demo" section), then run:
#
#   ./share-for-testing.sh start
#   ...share the printed client URL with teammates...
#   ./share-for-testing.sh stop
#
# `start` patches the client's hardcoded `http://localhost:8000` API URL to
# point at the backend's public tunnel URL instead (otherwise a teammate's
# browser would try to call their OWN localhost and every request would fail).
# `stop` kills both tunnels and restores the original files.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
CLIENT_DIR="$ROOT/client"
STATE_DIR="/tmp/goldenline-share"
mkdir -p "$STATE_DIR"

PID_FILE="$STATE_DIR/pids"
BACKEND_LOG="$STATE_DIR/tunnel-backend.log"
CLIENT_LOG="$STATE_DIR/tunnel-client.log"

API_FILES=("$CLIENT_DIR/console/console.js" "$CLIENT_DIR/login.js" "$CLIENT_DIR/tracking-page/tracking.js")
OLD_API="http://localhost:8000"

require_cloudflared() {
  if ! command -v cloudflared >/dev/null 2>&1; then
    echo "cloudflared not found. Install it with: brew install cloudflared" >&2
    exit 1
  fi
}

require_servers_up() {
  if ! curl -s -o /dev/null "http://127.0.0.1:8000/health"; then
    echo "Backend isn't running on :8000 — start it first, then re-run this script." >&2
    exit 1
  fi
  if ! curl -s -o /dev/null "http://127.0.0.1:5180/index.html"; then
    echo "Client isn't running on :5180 — start it first, then re-run this script." >&2
    exit 1
  fi
}

restore_api_files() {
  for f in "${API_FILES[@]}"; do
    if [ -f "$f.orig" ]; then
      mv "$f.orig" "$f"
    fi
  done
}

wait_for_url() {
  local log_file="$1"
  local url=""
  for _ in $(seq 1 30); do
    url="$(grep -o 'https://[a-zA-Z0-9.-]*\.trycloudflare\.com' "$log_file" 2>/dev/null | head -1 || true)"
    if [ -n "$url" ]; then
      echo "$url"
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for a tunnel URL — check $log_file" >&2
  return 1
}

cmd_start() {
  require_cloudflared
  require_servers_up

  # Always start from a clean, unpatched copy of the API files.
  restore_api_files

  echo "Starting backend tunnel..."
  nohup cloudflared tunnel --url http://localhost:8000 >"$BACKEND_LOG" 2>&1 &
  local backend_tunnel_pid=$!

  echo "Starting client tunnel..."
  nohup cloudflared tunnel --url http://localhost:5180 >"$CLIENT_LOG" 2>&1 &
  local client_tunnel_pid=$!

  echo "$backend_tunnel_pid $client_tunnel_pid" >"$PID_FILE"

  echo "Waiting for tunnel URLs..."
  local backend_url client_url
  backend_url="$(wait_for_url "$BACKEND_LOG")"
  client_url="$(wait_for_url "$CLIENT_LOG")"

  echo "Pointing the client at the public backend URL..."
  for f in "${API_FILES[@]}"; do
    cp "$f" "$f.orig"
    sed -i '' "s|$OLD_API|$backend_url|" "$f"
  done

  echo
  echo "================================================================"
  echo " Share this link with your teammates:"
  echo
  echo "   $client_url"
  echo
  echo " Backend (for reference, not needed by teammates): $backend_url"
  echo
  echo " Anyone with this link can reach the app while it's up — it's an"
  echo " unguessable random URL, not indexed, but still real login is"
  echo " required for anything sensitive. Run './share-for-testing.sh stop'"
  echo " when your teammates are done testing."
  echo "================================================================"
}

cmd_stop() {
  if [ -f "$PID_FILE" ]; then
    # shellcheck disable=SC2046
    kill $(cat "$PID_FILE") 2>/dev/null || true
    rm -f "$PID_FILE"
  fi
  pkill -f "cloudflared tunnel --url http://localhost:8000" 2>/dev/null || true
  pkill -f "cloudflared tunnel --url http://localhost:5180" 2>/dev/null || true
  restore_api_files
  echo "Tunnels stopped, client files restored to localhost:8000."
}

case "${1:-}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  *)
    echo "Usage: $0 {start|stop}" >&2
    exit 1
    ;;
esac

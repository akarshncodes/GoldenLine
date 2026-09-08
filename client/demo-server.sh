#!/usr/bin/env bash
# Demo static server for the GoldenLine client (used by .claude/launch.json).
# serve.py = http.server + Cache-Control: no-store (avoids stale <script>/CSS).
set -e
cd "/Users/akarshn/Desktop/SIH /Software/Project/client"
exec python3 serve.py 5180

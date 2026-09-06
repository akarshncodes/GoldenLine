#!/usr/bin/env bash
# Demo static server for the helper app (used by .claude/launch.json).
set -e
cd "/Users/akarshn/Desktop/SIH /Software/Project/client"
exec python3 -m http.server 5180

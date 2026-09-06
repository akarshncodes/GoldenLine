#!/usr/bin/env bash
# FR-15 guard: fails if the helper app grows a countdown timer, a single-number
# ETA, or any driver speed-ranking / leaderboard. See SAFE_DRIVING.md.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
flag() { echo "SAFE-DRIVING VIOLATION: $1"; fail=1; }

# grep across the app's *.js code (excluding i18n JSON strings)
code_grep() {
  find "$ROOT/js" -name '*.js' -not -path '*/i18n/*' -exec grep -nE "$1" {} +
}
all_grep() {
  find "$ROOT/js" -type f -exec grep -niE "$1" {} +
}

# 1. speed leaderboard / driver ranking (code OR translation strings)
if all_grep 'leaderboard|driver[_ ]?rank|speed[_ ]?rank|fastest[_ ]?driver|top[_ ]?drivers|driverscore' ; then
  flag "speed-ranking / leaderboard reference found"
fi

# 2. countdown timers / decrementing-ETA logic (code only)
if code_grep 'countdown|timeRemaining|secondsLeft|etaSeconds|eta--|--eta|startCountdown|tickEta|setInterval\([^,]*eta' ; then
  flag "countdown / decrementing-ETA logic found"
fi

# 3. ETA formatting must go through formatEtaRange only
if code_grep 'formatEta[A-Za-z]*\(' | grep -vE 'formatEtaRange\(' ; then
  flag "an ETA formatter other than formatEtaRange() exists"
fi

# 4. route framing must not sell an unsafe shortcut as fastest
if grep -qiE '"route\.[a-z]*":\s*"[^"]*(aggressive|risky shortcut)' "$ROOT/js/i18n/en.json" ; then
  flag "route text frames an unsafe shortcut as fastest"
fi

[ "$fail" -eq 0 ] && echo "safe-driving check: OK"
exit "$fail"

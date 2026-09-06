# FR-15 — Safe-Driving Design: rules for this codebase

These are enforced by `scripts/check-safe-driving.sh` (run in CI / `pytest`
`tests/test_fr13_fr14_fr15_client.py`).

## 1. ETA is always a range, never a countdown

- The **only** function that turns an ETA into display text is
  `js/eta.js::formatEtaRange(min, max)`. It always yields `"12–16 minutes"`.
- Do **not** add `formatEta(single)`, a `setInterval` that decrements an ETA/seconds
  value, an element whose text is a single live-updating minute number, or any
  "countdown" / "time remaining" widget.

## 2. No speed leaderboards or driver ranking

- Do **not** add any feature that ranks, scores, sorts, or compares drivers /
  helpers by speed, time, ETA beaten, or "fastest". No leaderboard, no badges
  for speed, no per-driver stats screen.
- Banned identifiers: `leaderboard`, `driverRank`, `speedRank`, `fastestDriver`,
  `driverScore` (speed-based), `topDrivers`.

## 3. Driver judgment overrides the app

- The suggested route is framed as the **fastest safe route** (`route.fastestSafe`
  i18n key), never "fastest" alone or an "aggressive shortcut".
- `js/safe-driving.js::acknowledgeDeviation()` handles the driver going a
  different way. It returns `{ blocked: false, penalty: null, ... }` and only
  recomputes the ETA range. Nothing may block, warn against, or record a penalty
  for a deviation.

If you need to bend one of these rules, change this file **and** the check in the
same PR, and get a second reviewer — that's the point of keeping them together.

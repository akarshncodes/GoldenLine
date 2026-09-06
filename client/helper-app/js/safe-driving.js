// FR-15: Safe-Driving Design helpers.
//
// SAFE-DRIVING INVARIANTS (do not break — scripts/check-safe-driving.sh enforces;
// full rules in SAFE_DRIVING.md):
//   1. ETA is only ever rendered via eta.js::formatEtaRange() — a RANGE, never a
//      single ticking-down minute number.
//   2. No component ranks / scores / compares drivers by speed or time. Ever.
//   3. The suggested route is framed as the fastest SAFE route. The driver may
//      deviate at any time; the app just recomputes the ETA range and carries on.
import { formatEtaRange } from './eta.js';
import { t } from './i18n.js';

export const ROUTE_FRAMING_KEY = 'route.fastestSafe';

// Called when the driver tells the app they're going a different way.
// It must NOT block, warn, or record a "penalty" — only recompute the ETA range.
export function acknowledgeDeviation(route, { detourFactor = 1.15 } = {}) {
  const min = Math.round(route.eta_min_minutes * detourFactor);
  const max = Math.round(route.eta_max_minutes * detourFactor) + 1;
  return {
    accepted: true,
    blocked: false,
    penalty: null,
    etaRangeText: formatEtaRange(min, max),
    message: t('route.deviated', { min, max }),
    eta_min_minutes: min,
    eta_max_minutes: max,
  };
}

export function routeSummary(route) {
  return {
    framing: t(ROUTE_FRAMING_KEY),
    etaRangeText: formatEtaRange(route.eta_min_minutes, route.eta_max_minutes),
    source: route.route_source,
  };
}

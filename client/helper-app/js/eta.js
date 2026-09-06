// FR-15 item 1: THE ONLY place ETA is turned into display text.
//
// ETA is ALWAYS shown as a range ("12–16 minutes"), never as a single
// ticking-down minute number. There is deliberately no single-value formatter
// here or anywhere else — scripts/check-safe-driving.sh fails if one appears.
import { t } from './i18n.js';

export function formatEtaRange(minMinutes, maxMinutes) {
  const lo = Math.max(1, Math.round(Number(minMinutes)));
  let hi = Math.round(Number(maxMinutes));
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return t('route.etaRange', { min: '?', max: '?' });
  if (hi <= lo) hi = lo + 1; // never collapse to a single number
  return t('route.etaRange', { min: lo, max: hi });
}

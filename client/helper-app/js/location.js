// FR-13 item 2: live GPS with a last-known fallback that is NEVER rendered like
// a live position — callers must show the `estimated` flag.
import { STORAGE_KEYS } from './config.js';
import { t } from './i18n.js';

function saveLastKnown(coords) {
  try {
    localStorage.setItem(
      STORAGE_KEYS.lastLocation,
      JSON.stringify({ latitude: coords.latitude, longitude: coords.longitude, at: Date.now() })
    );
  } catch { /* ignore */ }
}

function readLastKnown() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.lastLocation) || 'null');
  } catch {
    return null;
  }
}

function ageLabel(ms) {
  const mins = Math.round(ms / 60000);
  if (mins < 1) return 'moments ago';
  if (mins < 60) return `${mins} min ago`;
  return `${Math.round(mins / 60)} h ago`;
}

// Resolves to { latitude, longitude, estimated: bool, label, timestamp }.
export function getLocation({ timeoutMs = 6000 } = {}) {
  return new Promise((resolve) => {
    const fallback = () => {
      const lk = readLastKnown();
      if (lk) {
        resolve({
          latitude: lk.latitude,
          longitude: lk.longitude,
          estimated: true,
          label: t('loc.estimated', { age: ageLabel(Date.now() - lk.at) }),
          timestamp: lk.at,
        });
      } else {
        resolve({ latitude: null, longitude: null, estimated: true, label: t('loc.unavailable'), timestamp: null });
      }
    };

    if (!('geolocation' in navigator)) return fallback();

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        saveLastKnown(pos.coords);
        resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          estimated: false,
          label: t('loc.live'),
          timestamp: Date.now(),
        });
      },
      fallback,
      { timeout: timeoutMs, maximumAge: 0, enableHighAccuracy: true }
    );
  });
}

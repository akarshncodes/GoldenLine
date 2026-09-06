// FR-13 item 4: keep a small on-device hospital list so a basic list is available
// even if live ranking (FR-2) can't be reached.
import { API_BASE, HOSPITAL_SNAPSHOT_TTL_MS, STORAGE_KEYS } from './config.js';

async function bundledSnapshot() {
  try {
    const r = await fetch(new URL('../data/offline-hospitals.json', import.meta.url));
    const data = await r.json();
    return { hospitals: data.hospitals, source: 'bundled', captured_at: data.captured_at };
  } catch {
    return { hospitals: [], source: 'bundled', captured_at: null };
  }
}

function readStored() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEYS.hospitalSnapshot) || 'null'); }
  catch { return null; }
}

function store(snapshot) {
  try { localStorage.setItem(STORAGE_KEYS.hospitalSnapshot, JSON.stringify(snapshot)); }
  catch { /* ignore */ }
}

// Best snapshot available right now, no network needed.
export async function getOfflineHospitalList() {
  return readStored() || (await bundledSnapshot());
}

// Refresh the snapshot from the API if online and the stored copy is stale.
export async function refreshHospitalSnapshot(getToken) {
  const stored = readStored();
  if (stored && Date.now() - (stored.refreshed_at || 0) < HOSPITAL_SNAPSHOT_TTL_MS) return stored;
  if (!navigator.onLine) return stored || (await bundledSnapshot());
  try {
    const token = getToken?.();
    const r = await fetch(`${API_BASE}/hospitals`, {
      headers: token ? { authorization: `Bearer ${token}` } : {},
    });
    if (!r.ok) throw new Error(String(r.status));
    const hospitals = await r.json();
    const snap = { hospitals, source: 'live', refreshed_at: Date.now() };
    store(snap);
    return snap;
  } catch {
    return stored || (await bundledSnapshot());
  }
}

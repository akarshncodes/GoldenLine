// Network layer. Mutations made while offline are handed to the offline queue
// (FR-13) instead of failing; reads fall back to caches where the caller provides one.
import { API_BASE, STORAGE_KEYS } from './config.js';
import { enqueue } from './offline-queue.js';

export function getToken() {
  try { return localStorage.getItem(STORAGE_KEYS.token) || null; } catch { return null; }
}

export function setToken(tok) {
  try { tok ? localStorage.setItem(STORAGE_KEYS.token, tok) : localStorage.removeItem(STORAGE_KEYS.token); }
  catch { /* ignore */ }
}

// FR-13: a manual switch so the demo can be tested without touching real network.
export function isOffline() {
  try { if (localStorage.getItem(STORAGE_KEYS.simulateOffline) === '1') return true; } catch { /* ignore */ }
  return !navigator.onLine;
}

export function setSimulateOffline(on) {
  try { on ? localStorage.setItem(STORAGE_KEYS.simulateOffline, '1') : localStorage.removeItem(STORAGE_KEYS.simulateOffline); }
  catch { /* ignore */ }
  if (!on) window.dispatchEvent(new Event('online'));
}

async function request(method, path, body) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'content-type': 'application/json',
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.detail || res.statusText), { status: res.status, data });
  return data;
}

export async function get(path) {
  if (isOffline()) throw Object.assign(new Error('offline'), { offline: true });
  return request('GET', path);
}

// A mutation: if offline, queue it and report `queued` so the UI can say
// "saved, will sync automatically".
export async function mutate(path, body, { label } = {}) {
  if (isOffline()) {
    enqueue({ method: 'POST', path, body, label: label || path });
    return { queued: true };
  }
  try {
    return { queued: false, data: await request('POST', path, body) };
  } catch (err) {
    if (err.offline || err.message === 'Failed to fetch') {
      enqueue({ method: 'POST', path, body, label: label || path });
      return { queued: true };
    }
    throw err;
  }
}

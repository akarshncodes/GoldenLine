// FR-13 item 1: offline-first action queue.
//
// Any mutating action (symptom log, hospital selection, ...) taken while offline
// is stored here and REPLAYED automatically the moment connectivity returns —
// the user never has to tap "retry". Persisted in localStorage so it survives an
// app restart.
import { API_BASE, STORAGE_KEYS } from './config.js';

const subscribers = new Set();

function read() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEYS.queue) || '[]'); }
  catch { return []; }
}

function write(items) {
  try { localStorage.setItem(STORAGE_KEYS.queue, JSON.stringify(items)); } catch { /* ignore */ }
  subscribers.forEach((fn) => fn(items));
}

export function pendingCount() {
  return read().length;
}

export function onQueueChange(fn) {
  subscribers.add(fn);
  fn(read());
  return () => subscribers.delete(fn);
}

export function enqueue(action) {
  const items = read();
  items.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    queued_at: Date.now(),
    ...action, // { method, path, body, label }
  });
  write(items);
}

let flushing = false;

// Replays queued actions in order. Stops on the first network failure and
// leaves the rest queued for the next attempt. Returns { synced, remaining }.
export async function flushQueue(getToken) {
  if (flushing) return { synced: 0, remaining: pendingCount() };
  flushing = true;
  let synced = 0;
  try {
    let items = read();
    while (items.length) {
      const action = items[0];
      try {
        const token = getToken?.();
        const res = await fetch(`${API_BASE}${action.path}`, {
          method: action.method || 'POST',
          headers: {
            'content-type': 'application/json',
            ...(token ? { authorization: `Bearer ${token}` } : {}),
          },
          body: action.body ? JSON.stringify(action.body) : undefined,
        });
        // 2xx or a definitive 4xx (bad/duplicate request) -> drop it, don't loop forever
        if (res.ok || (res.status >= 400 && res.status < 500)) {
          items.shift();
          write(items);
          synced += 1;
        } else {
          break; // 5xx / transient -> retry later
        }
      } catch {
        break; // offline again
      }
      items = read();
    }
    return { synced, remaining: read().length };
  } finally {
    flushing = false;
  }
}

// Wire automatic sync: on 'online', on visibility, and a slow poll as a safety net.
export function startAutoSync(getToken, { onStatus } = {}) {
  const run = async () => {
    if (!navigator.onLine) return;
    onStatus?.('syncing');
    const r = await flushQueue(getToken);
    onStatus?.(r.remaining ? 'queued' : 'synced');
  };
  window.addEventListener('online', run);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) run(); });
  setInterval(run, 8000);
  run();
}

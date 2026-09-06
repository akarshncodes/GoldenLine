// FR-13 item 3: when data connectivity is unavailable, critical status updates
// go out over SMS instead. Reuses the Phase 8 backend SMS stub — the app POSTs to
// a small backend relay which calls sendSMS(). If even that can't be reached, the
// message is queued (offline-queue.js) so it still sends once the link returns.
import { API_BASE, STORAGE_KEYS } from './config.js';
import { enqueue } from './offline-queue.js';

// A real build would hand this to the device's native SMS composer as a final
// resort. Here we route through the backend's existing stub.
export async function sendCriticalUpdateBySms({ toPhone, message, caseId }) {
  const body = { to_phone: toPhone, message, case_id: caseId, category: 'critical_update' };
  try {
    const token = localStorage.getItem(STORAGE_KEYS.token);
    const res = await fetch(`${API_BASE}/sms/fallback`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...(token ? { authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(String(res.status));
    return { sent: true, channel: 'sms', queued: false };
  } catch {
    enqueue({ method: 'POST', path: '/sms/fallback', body, label: 'critical SMS update' });
    return { sent: false, channel: 'sms', queued: true };
  }
}

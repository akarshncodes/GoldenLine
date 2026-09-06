/* GoldenLine — Path B family tracking page (FR-9).
 *
 * No login, no case_id, no patient data — this page renders exactly what
 * GET /track/{token} returns, nothing more. See backend/app/schemas/tracking.py
 * for the whitelist this is built against.
 */
const API = 'http://localhost:8000';
const POLL_MS = 8000;

document.addEventListener('alpine:init', () => {
  Alpine.data('trackingApp', () => ({
    state: 'loading', // loading | active | expired | notfound | error
    view: null,
    token: null,
    _pollId: null,

    init() {
      this.token = new URLSearchParams(location.search).get('token');
      if (!this.token) { this.state = 'notfound'; return; }
      this.fetchStatus();
      this._pollId = setInterval(() => this.fetchStatus(), POLL_MS);
    },

    async fetchStatus() {
      try {
        const res = await fetch(`${API}/track/${encodeURIComponent(this.token)}`);
        if (res.status === 410) { this.state = 'expired'; this._stopPolling(); return; }
        if (res.status === 404) { this.state = 'notfound'; this._stopPolling(); return; }
        if (!res.ok) { this.state = 'error'; return; }
        this.view = await res.json();
        this.state = 'active';
        if (this.view.stage === 'discharged') this._stopPolling();
      } catch {
        this.state = 'error';
      }
    },

    _stopPolling() {
      if (this._pollId != null) clearInterval(this._pollId);
      this._pollId = null;
    },

    stageLabel(s) {
      return { en_route: 'En route', arrived: 'Arrived at hospital', discharged: 'Discharged' }[s] || s;
    },
    stageBadgeClass(s) {
      return { en_route: 'gl-badge-sky', arrived: 'gl-badge-gold', discharged: 'gl-badge-slate' }[s] || 'gl-badge-slate';
    },
  }));
});

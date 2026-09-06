/* GoldenLine — Operator Console
 *
 * One page, auto-role from whoever signed in on the landing page (client/index.html).
 * Talks to the FastAPI backend on :8000. Every failed request surfaces a toast —
 * nothing fails silently.
 */
const API = 'http://localhost:8000';
const TOKEN_KEY = 'goldenline.token';
const FAMILY_OTP_KEY = 'goldenline.family.otpId';
const FAMILY_PHONE_KEY = 'goldenline.family.phone';
const LANG_KEY = 'goldenline.lang';
const NATIVE_NAMES = { en: 'English', hi: 'हिन्दी', ta: 'தமிழ்', bn: 'বাংলা' };

// Backend Role (from /auth/me) -> this console's view key.
const ROLE_TO_VIEW = {
  helper: 'helper',
  family: 'family',
  hospital_receptionist: 'hospital',
  blood_bank_coordinator: 'bloodbank',
  control_room: 'controlroom',
  admin: 'admin',
};

const VIEW_LABEL_KEYS = {
  helper: 'console.role.helper',
  family: 'console.role.family',
  hospital: 'console.role.hospital',
  bloodbank: 'console.role.bloodbank',
  controlroom: 'console.role.controlroom',
  admin: 'console.role.admin',
};

const NAV = {
  helper:    [['cases', 'console.nav.cases']],
  family:      [['sos', 'console.nav.sos']],
  hospital:    [['beds', 'console.nav.beds'], ['census', 'console.nav.census'], ['roster', 'console.nav.roster'],
                ['inventory', 'console.nav.inventory'], ['import', 'console.nav.import'], ['incoming', 'console.nav.incoming']],
  bloodbank:   [['holds', 'console.nav.holds']],
  controlroom: [['flags', 'console.nav.flags'], ['oversight', 'console.nav.oversight'], ['map', 'console.nav.map']],
  admin:       [['cases', 'console.nav.allCases'], ['beds', 'console.nav.beds'], ['census', 'console.nav.census'],
                ['roster', 'console.nav.roster'], ['inventory', 'console.nav.inventory'], ['import', 'console.nav.import'],
                ['incoming', 'console.nav.incoming'],
                ['holds', 'console.nav.holds'], ['flags', 'console.nav.flags'], ['oversight', 'console.nav.oversight'],
                ['hospitals', 'console.nav.hospitals'], ['map', 'console.nav.map']],
};

// Fallback location for a helper-created Path B case before their device has
// reported a real GPS fix (see _startLiveLocation) — Dindigul town centre.
const DINDIGUL_TOWN_CENTER = { latitude: 10.3673, longitude: 77.9803 };

// The full backend SymptomTag enum (app/models/assessment.py) — every one of
// these is checkable in the tap checklist, matching everything voice input
// can already derive (previously only 7 of 14 had a checkbox here).
const SYMPTOM_TAGS = [
  'chest_pain', 'breathing_difficulty', 'visible_bleeding', 'trauma',
  'unconsciousness', 'seizure', 'severe_pain', 'burns', 'pregnancy_labour',
  'stroke_signs', 'high_fever', 'vomiting', 'allergic_reaction', 'poisoning',
];

// Small hand-drawn 20x20 monoline icons, one per nav item (currentColor stroke —
// no icon-font/CDN dependency, matches the "no build" ethos of the rest of the client).
const NAV_ICONS = {
  cases: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="3" width="12" height="14" rx="1.5"/><path d="M7.5 3V2.6A1.1 1.1 0 0 1 8.6 1.5h2.8a1.1 1.1 0 0 1 1.1 1.1V3"/><path d="M7 9h6M7 12h6M7 15h3"/></svg>',
  case: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="3" width="12" height="14" rx="1.5"/><path d="M7 9h6M7 12h6M7 15h3"/></svg>',
  sos: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2.3 17 15a1 1 0 0 1-.9 1.5H3.9A1 1 0 0 1 3 15L10 2.3z"/><path d="M10 7.8v3.6"/><circle cx="10" cy="13.6" r=".2" fill="currentColor"/></svg>',
  beds: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 16.5V8a1 1 0 0 1 1-1H8a1 1 0 0 1 1 1v2.7"/><path d="M2.5 16.5v-3.2A1.3 1.3 0 0 1 3.8 12h12.4a1.8 1.8 0 0 1 1.8 1.8v2.7"/><path d="M2.5 13.2h15"/><circle cx="5.8" cy="7" r="1.2"/></svg>',
  incoming: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 3.5h13v10a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 3.5 13.5v-10Z"/><path d="M3.5 10.5h3.8l1.1 1.8h3.2l1.1-1.8h3.3"/></svg>',
  holds: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2.5s5.2 6 5.2 9.7a5.2 5.2 0 1 1-10.4 0C4.8 8.5 10 2.5 10 2.5Z"/></svg>',
  flags: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 2v16"/><path d="M4.5 3.2h10.2l-2.3 3 2.3 3H4.5"/></svg>',
  oversight: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1.7 10S4.8 4.3 10 4.3 18.3 10 18.3 10 15.2 15.7 10 15.7 1.7 10 1.7 10Z"/><circle cx="10" cy="10" r="2.2"/></svg>',
  hospitals: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.2 17.2V5.8a1 1 0 0 1 1-1h11.6a1 1 0 0 1 1 1v11.4"/><path d="M1.7 17.2h16.6"/><path d="M10 7.5v4.4M7.8 9.7h4.4"/></svg>',
  map: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2.5c-3 0-5.3 2.3-5.3 5.3 0 4 5.3 9.7 5.3 9.7s5.3-5.7 5.3-9.7C15.3 4.8 13 2.5 10 2.5Z"/><circle cx="10" cy="7.8" r="1.8"/></svg>',
  census: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="7" cy="6" r="2.2"/><path d="M2.5 16.5c0-2.8 2-4.5 4.5-4.5s4.5 1.7 4.5 4.5"/><circle cx="14.5" cy="6.8" r="1.7"/><path d="M12.8 12.3c1.9.3 3.2 1.8 3.2 4.2"/></svg>',
  roster: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="6" r="2.8"/><path d="M4 17c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5"/><path d="M14.2 2.3a2.8 2.8 0 0 1 0 5.4"/></svg>',
  inventory: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6.5 10 3l7 3.5-7 3.5-7-3.5Z"/><path d="M3 6.5v7L10 17l7-3.5v-7"/><path d="M10 10v7"/></svg>',
  import: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2.5v10.5"/><path d="M6.3 9.3 10 13l3.7-3.7"/><path d="M3.5 15v1.3a1.2 1.2 0 0 0 1.2 1.2h10.6a1.2 1.2 0 0 0 1.2-1.2V15"/></svg>',
};

// FR-22: which fields a receptionist can map a source column to, per target
// table. Mirrors backend/app/services/import_matching.py's TARGET_FIELD_ALIASES
// keys (source of truth for validity) — this list is only for building the
// mapping-override dropdown, matching stays server-validated on commit.
const IMPORT_TARGET_FIELDS = {
  patients: ['full_name', 'approx_age', 'gender', 'phone_number', 'patient_type'],
  hospital_staff: ['full_name', 'staff_category', 'specialty', 'phone_number'],
  hospital_inventory_items: ['item_name', 'category', 'unit', 'quantity_on_hand', 'low_stock_threshold'],
  bed_categories: ['category_code', 'label', 'total_beds'],
};

document.addEventListener('alpine:init', () => {
  Alpine.data('consoleApp', () => ({
    // ---- i18n ----
    lang: 'en',
    dict: {},
    langOptions: Object.entries(NATIVE_NAMES).map(([code, label]) => ({ code, label })),

    // ---- auth / role (established on the landing page, client/index.html) ----
    session: null,                       // { token, user_id, role, hospital_id, blood_bank_id, phone_number, display_name }
    viewRole: 'helper',                // derived from session.role via ROLE_TO_VIEW
    bootFailed: false,

    // ---- ui ----
    screen: 'cases',
    loading: false,
    apiUp: true,
    toasts: [],
    newCaseOpen: false,
    editSymptoms: false,
    resetConfirming: false,

    // ---- data ----
    cases: [],
    hospitals: [],
    activeCase: null,
    ac: {},                              // active-case bundle (case, assessment, ranking, bedLock, route, blood, prep, qr, feedbackInvite)
    nc: { name: '', age: 45, gender: 'male', nok: '9123456780' },
    sym: { crit: 'Serious', list: ['chest_pain'] },
    voice: { supported: !!(window.SpeechRecognition || window.webkitSpeechRecognition), listening: false, busy: false, transcript: '', matches: [], heardSnapshot: '' },
    _recognition: null,
    // Follow-up "case updates" — an append-only log the helper can add to at
    // any point during a case (separate from the one-time initial transcript).
    notes: [],
    newNote: { text: '', listening: false },
    _noteRecognition: null,
    // Live ambulance location (helper's own device GPS) — reported for as
    // long as a case is open, so hospital-ranking distance is real haversine
    // distance from wherever the ambulance actually is, not a mock estimate.
    geo: { supported: !!navigator.geolocation, watching: false, coords: null, updatedAt: null, error: null },
    _geoWatchId: null,

    // family — the OTP round-trip happened on the landing page; we just read what it left us
    fam: { phone: '', gps: null, otpMissing: false },
    familyCaseId: null,
    _familyCaseWatchId: null,

    // map overview (admin / control_room)
    mapData: { hospitals: [], bloodBanks: [], ambulances: [] },

    // hospital
    hospDash: null,
    syncStatus: null,
    sheetUrl: 'https://sheets.example/h?general=9&icu=4',
    report: { gen: 0, icu: 0 },
    hc: {},                              // hospital's active case (case, prep, admitOk)
    scan: { caseId: '', token: '' },
    bedCategories: [],                   // FR-17: room/bed categories beyond general+ICU
    newCategory: { code: '', label: '', total_beds: 0 },
    census: [],                          // FR-18: hospital-wide patient census
    censusFilter: '',                    // '' = all statuses
    newPatient: { full_name: '', approx_age: null, gender: 'male', patient_type: 'walk_in' },
    admitCategory: {},                   // { [patient_id]: category_code } — per-row admit form input
    roster: [],                          // FR-19: hospital doctor/staff roster
    newStaff: { full_name: '', staff_category: 'doctor', specialty: '', phone_number: '' },
    attendanceOpenFor: null,             // staff_id whose attendance history panel is expanded
    attendanceHistory: [],               // history rows for attendanceOpenFor
    inventory: [],                       // FR-21: hospital medical resource/inventory
    newInvItem: { item_name: '', category: 'medicine', unit: '', quantity_on_hand: 0, low_stock_threshold: null },
    importTargetTable: 'patients',       // FR-22: rule-based fuzzy import
    importSheetUrl: '',
    importReport: null,                  // {import_session_id, target_table, row_count, columns, unmatched_columns}
    importMapping: {},                   // editable {source_column: field_or_null}, seeded from importReport
    importResult: null,                  // {imported, skipped} after commit

    // blood bank
    holds: [],

    // control room
    flags: [], conflicts: [], rateFlags: [], deletions: [],
    resolveNotes: {},

    // ─────────────────────────── lifecycle ───────────────────────────
    async init() {
      this.health();
      setInterval(() => this.health(), 15000);

      let saved;
      try { saved = localStorage.getItem(LANG_KEY); } catch { saved = null; }
      await this.setLang(saved || (navigator.language || 'en').slice(0, 2));

      await this.bootSession();
    },

    async health() {
      try { const r = await fetch(`${API}/health`); this.apiUp = r.ok; }
      catch { this.apiUp = false; }
    },

    t(key) {
      return this.dict[key] || key;
    },

    async setLang(code) {
      if (!NATIVE_NAMES[code]) code = 'en';
      try {
        const res = await fetch(`../i18n/${code}.json`);
        this.dict = await res.json();
        this.lang = code;
        document.documentElement.lang = code;
        try { localStorage.setItem(LANG_KEY, code); } catch {}
      } catch {
        if (code !== 'en') await this.setLang('en');
      }
    },

    roleLabel(k) { return this.t(VIEW_LABEL_KEYS[k]) || k; },
    nav() { return (NAV[this.viewRole] || []).map(([key, labelKey]) => ({ key, label: this.t(labelKey) })); },
    navIcon(key) { return NAV_ICONS[key] || ''; },
    symptomTags() { return SYMPTOM_TAGS; },

    async bootSession() {
      let token;
      try { token = localStorage.getItem(TOKEN_KEY); } catch { token = null; }
      if (!token) { this.bootFailed = true; window.location.replace('../index.html'); return; }

      try {
        const r = await fetch(`${API}/auth/me`, { headers: { authorization: `Bearer ${token}` } });
        if (!r.ok) throw new Error('session invalid');
        const me = await r.json();
        this.session = { token, ...me };
      } catch {
        try { localStorage.removeItem(TOKEN_KEY); } catch {}
        this.bootFailed = true;
        window.location.replace('../index.html');
        return;
      }

      this.viewRole = ROLE_TO_VIEW[this.session.role] || 'admin';
      if (this.viewRole === 'family') {
        try {
          this.fam.phone = localStorage.getItem(FAMILY_PHONE_KEY) || this.session.phone_number || '';
        } catch {}
      }
      this.screen = (NAV[this.viewRole]?.[0] || ['cases'])[0];
      this.go(this.screen);
    },

    signOut() {
      this._stopLiveLocation();
      this._stopFamilyCaseWatch();
      try {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(FAMILY_OTP_KEY);
        localStorage.removeItem(FAMILY_PHONE_KEY);
      } catch {}
      window.location.replace('../index.html');
    },

    // ─────────────────────────── live ambulance location (helper's device GPS) ───────────────────────────
    // Reported for the whole time a case is open — the browser's own
    // Geolocation API, no server-side simulation. FR-2's ranking recomputes
    // hospital distance/ETA from wherever this lands (see distance_source in
    // the ranking response); until the first fix comes in, ranking uses each
    // hospital's static mock distance as a fallback estimate.
    _startLiveLocation() {
      if (!this.geo.supported || this._geoWatchId != null) return;
      this.geo.error = null;
      this._geoWatchId = navigator.geolocation.watchPosition(
        (pos) => this._reportHelperLocation(pos.coords.latitude, pos.coords.longitude),
        (err) => { this.geo.error = err.message || 'unavailable'; },
        { enableHighAccuracy: true, maximumAge: 10000, timeout: 15000 },
      );
      this.geo.watching = true;
    },
    _stopLiveLocation() {
      if (this._geoWatchId != null) navigator.geolocation.clearWatch(this._geoWatchId);
      this._geoWatchId = null;
      this.geo.watching = false;
    },
    async _reportHelperLocation(lat, lon) {
      this.geo.coords = { lat, lon };
      this.geo.updatedAt = new Date();
      if (!this.activeCase) return;
      try {
        await this.api('POST', `/cases/${this.activeCase}/helper-location`, {
          helper_id: this.session.user_id,
          gps: { latitude: lat, longitude: lon },
        }, { quiet: true });
        if (this.ac.case) { this.ac.case.gps_latitude = lat; this.ac.case.gps_longitude = lon; }
        // re-rank with the fresh location — only while it can still change anything
        if (this.ac.assessment && !this.ac.case?.selected_hospital_id) {
          this.ac.ranking = await this.api(
            'GET', `/cases/${this.activeCase}/hospital-ranking`, null, { quiet: true },
          ).catch(() => this.ac.ranking);
        }
      } catch {}
      this._syncCaseMap();
    },
    geoAgeSeconds() {
      if (!this.geo.updatedAt) return null;
      return Math.max(0, Math.round((Date.now() - this.geo.updatedAt.getTime()) / 1000));
    },

    // ─────────────────────────── map: family SOS location picker ───────────────────────────
    // Replaces the old 2-item location dropdown: try the browser's own GPS
    // first to drop a starting pin, then let the family drag it or tap
    // elsewhere on the map to correct it. Either way `fam.gps` is what gets
    // sent with the SOS.
    // Deliberately NOT stored as `this._sosMap`: a Leaflet instance is a large
    // stateful object with internal DOM/event wiring that Alpine's reactivity
    // proxy would wrap if it lived in x-data (see map.js's own note on this).
    // GLMap.getOrCreate is idempotent per element, so re-fetching it each call
    // is both simpler and safer than caching the reference on `this`.
    _initSosMap() {
      const el = this.$refs.sosMap;
      if (!el || typeof GLMap === 'undefined') return;
      const map = GLMap.getOrCreate(el, { center: GLMap.DINDIGUL_CENTER, zoom: 13 });
      map.on('click', (e) => this._setSosPin(e.latlng.lat, e.latlng.lng));
      this._renderSosPin();

      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (pos) => this._setSosPin(pos.coords.latitude, pos.coords.longitude),
          () => {}, // denied/unavailable: leave it for the family to tap
          { enableHighAccuracy: true, timeout: 6000, maximumAge: 30000 },
        );
      }
    },
    _setSosPin(lat, lng) {
      this.fam.gps = { latitude: lat, longitude: lng };
      this._renderSosPin();
    },
    _renderSosPin() {
      const el = this.$refs.sosMap;
      if (!el || typeof GLMap === 'undefined') return;
      const map = GLMap.getOrCreate(el, { center: GLMap.DINDIGUL_CENTER, zoom: 13 });
      const gps = this.fam.gps;
      GLMap.setPins(map, gps ? [{
        lat: gps.latitude, lng: gps.longitude, kind: 'incident', pulse: true, draggable: true,
        onDrag: (lat, lng) => this._setSosPin(lat, lng),
      }] : []);
    },

    // ─────────────────────────── api helper ───────────────────────────
    async api(method, path, body, { quiet = false } = {}) {
      this.loading = true;
      try {
        const res = await fetch(`${API}${path}`, {
          method,
          headers: {
            'content-type': 'application/json',
            ...(this.session ? { authorization: `Bearer ${this.session.token}` } : {}),
          },
          body: body ? JSON.stringify(body) : undefined,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          const msg = typeof data.detail === 'string' ? data.detail
            : (data.detail?.message || JSON.stringify(data.detail || data).slice(0, 200));
          if (!quiet) this.toast(`${res.status} · ${msg}`, 'error');
          throw Object.assign(new Error(msg), { status: res.status, data });
        }
        return data;
      } catch (e) {
        if (e.status === undefined && !quiet) this.toast(this.t('console.toast.networkError'), 'error');
        throw e;
      } finally {
        this.loading = false;
      }
    },

    // FR-22: multipart upload — api() above always JSON-encodes, which can't
    // carry a File. No content-type header here on purpose: the browser sets
    // the multipart boundary itself when the body is a FormData.
    async apiUpload(method, path, formData) {
      this.loading = true;
      try {
        const res = await fetch(`${API}${path}`, {
          method,
          headers: { ...(this.session ? { authorization: `Bearer ${this.session.token}` } : {}) },
          body: formData,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          const msg = typeof data.detail === 'string' ? data.detail
            : (data.detail?.message || JSON.stringify(data.detail || data).slice(0, 200));
          this.toast(`${res.status} · ${msg}`, 'error');
          throw Object.assign(new Error(msg), { status: res.status, data });
        }
        return data;
      } catch (e) {
        if (e.status === undefined) this.toast(this.t('console.toast.networkError'), 'error');
        throw e;
      } finally {
        this.loading = false;
      }
    },

    toast(msg, kind = 'info') {
      const id = Math.random().toString(36).slice(2);
      this.toasts.push({ id, msg, kind });
      setTimeout(() => { this.toasts = this.toasts.filter(t => t.id !== id); }, kind === 'error' ? 6000 : 3500);
    },

    // ─────────────────────────── router ───────────────────────────
    go(screen) {
      this.screen = screen;
      if (screen === 'case' && this.viewRole === 'helper') this._startLiveLocation();
      else this._stopLiveLocation();
      if (screen !== 'case') this._stopFamilyCaseWatch();
      if (screen === 'sos') setTimeout(() => this._initSosMap(), 0);
      const load = {
        cases: () => this.loadCases(),
        sos: () => {},
        beds: () => this.loadBeds(),
        census: () => this.loadCensus(),
        roster: () => this.loadRoster(),
        inventory: () => this.loadInventory(),
        import: () => this.resetImport(),
        incoming: () => this.loadCases(),
        holds: () => this.loadHolds(),
        flags: () => this.loadFlags(),
        oversight: () => this.loadOversight(),
        hospitals: () => this.loadHospitals(),
        map: () => this.loadMapScreen(),
      }[screen];
      load && load();
    },

    // ─────────────────────────── cases (helper / admin / hospital list) ───────────────────────────
    async loadCases() {
      try { this.cases = await this.api('GET', '/cases'); } catch { this.cases = []; }
    },

    async createCase() {
      try {
        const c = await this.api('POST', '/cases', {
          next_of_kin_phone_number: this.nc.nok.trim(),
          patient: { name: this.nc.name || null, approx_age: this.nc.age, gender: this.nc.gender },
          helper_id: this.session.user_id,
          helper_gps: DINDIGUL_TOWN_CENTER,
        });
        this.toast(this.t('console.toast.caseCreated'), 'ok');
        this.newCaseOpen = false;
        await this.loadCases();
        this.openCase(c.case_id);
      } catch {}
    },

    async openCase(id) {
      this.editSymptoms = false;
      this.activeCase = id;
      this.ac = {};
      this.notes = [];
      this.newNote = { text: '', listening: false };
      this.voice.matches = [];
      this.voice.heardSnapshot = '';
      this.screen = 'case';
      if (this.viewRole === 'helper') this._startLiveLocation();
      if (this.viewRole === 'family') this._startFamilyCaseWatch();
      await this.refreshCase();
    },

    // Family isn't the one carrying the GPS (the helper is), so seeing the
    // ambulance approach means re-polling the case + route on an interval
    // instead of a geolocation watch. Console-only, per the case's own
    // access.can_see_case scoping — no new endpoint, no privacy-boundary change.
    _startFamilyCaseWatch() {
      if (this._familyCaseWatchId != null) return;
      this._familyCaseWatchId = setInterval(() => {
        if (this.screen === 'case' && this.activeCase) this.refreshCase();
        else this._stopFamilyCaseWatch();
      }, 6000);
    },
    _stopFamilyCaseWatch() {
      if (this._familyCaseWatchId != null) clearInterval(this._familyCaseWatchId);
      this._familyCaseWatchId = null;
    },

    async refreshCase() {
      const id = this.activeCase;
      const ac = { deviationNote: this.ac.deviationNote, qr: this.ac.qr };
      ac.case = await this.api('GET', `/cases/${id}`);
      if (ac.case.creation_path === 'B' && this.viewRole !== 'family') {
        ac.trackingLink = await this.api('GET', `/cases/${id}/tracking-link`, null, { quiet: true }).catch(() => null);
      }
      ac.assessment = await this.api('GET', `/cases/${id}/assessment`, null, { quiet: true }).catch(() => null);
      if (ac.assessment) {
        ac.ranking = await this.api('GET', `/cases/${id}/hospital-ranking`, null, { quiet: true }).catch(() => null);
        this.notes = await this.api('GET', `/cases/${id}/notes`, null, { quiet: true }).catch(() => []);
      }
      if (ac.case.selected_hospital_id) {
        ac.bedLock = await this.api('GET', `/cases/${id}/bed-lock`, null, { quiet: true }).catch(() => null);
        ac.route = await this.api('GET', `/cases/${id}/route`, null, { quiet: true }).catch(() => null);
        ac.blood = await this.api('GET', `/cases/${id}/blood-check`, null, { quiet: true }).catch(() => null);
        ac.prep = await this.api('GET', `/cases/${id}/prep-actions`, null, { quiet: true }).catch(() => null);
      }
      if (ac.case.status === 'DISCHARGED') {
        ac.feedbackInvite = await this.api('GET', `/cases/${id}/feedback-invite`, null, { quiet: true }).catch(() => null);
      }
      // Which ambulance is assigned + its live position — helper IS the
      // ambulance, so this is only meaningful for everyone else (family,
      // admin/control_room viewing a case), and only while still in transit.
      if (this.viewRole !== 'helper' && ac.case.helper_id && !['ADMITTED', 'DISCHARGED'].includes(ac.case.status)) {
        ac.ambulance = await this.api('GET', `/cases/${id}/ambulance`, null, { quiet: true }).catch(() => null);
      }
      this.ac = ac;
      // Keep the edit form in sync with what's actually saved, so re-opening
      // "edit" shows the real current values instead of stale local state
      // left over from a previous case.
      if (ac.assessment) {
        this.sym.crit = ac.assessment.criticality_level;
        this.sym.list = [...ac.assessment.symptom_checklist];
        this.voice.transcript = ac.assessment.raw_voice_transcript || '';
      }
      setTimeout(() => this._syncCaseMap(), 0);
    },

    // ─────────────────────────── map: case-detail (helper + family) ───────────────────────────
    // One map for the whole case: before a hospital is chosen it shows the
    // helper's live position plus the up-to-3 candidate classes (so "closest
    // wins" is visible, not just a number); once a hospital is confirmed it
    // switches to that hospital + the route line. Family sees the same map
    // via the same RBAC-scoped case data — no separate tracking surface.
    // No `this._caseMap` field — see the note on _initSosMap above; the map
    // instance is never stored in Alpine's reactive x-data.
    _selfPoint() {
      // Only ever the VIEWER's own device — the case's gps_latitude/longitude
      // is the helper's (ambulance's) position, not the family's. It used to
      // be used as a fallback here for everyone, which silently mislabeled
      // the ambulance's position as "you" on the family's map; see
      // _ambulancePoint() below for the correct, separate pin.
      if (this.viewRole === 'helper' && this.geo.coords) return { lat: this.geo.coords.lat, lng: this.geo.coords.lon };
      return null;
    },
    _ambulancePoint() {
      if (this.viewRole === 'helper') return null; // that's "self" above
      const c = this.ac.case;
      if (c?.gps_latitude != null && c?.gps_longitude != null) return { lat: c.gps_latitude, lng: c.gps_longitude };
      return null;
    },
    _ambulanceLabel() {
      const amb = this.ac.ambulance;
      return amb ? `${amb.vehicle_number} · ${amb.driver_name}` : this.t('console.map.ambulance');
    },
    _syncCaseMap() {
      const el = this.$refs.caseMap;
      if (!el || typeof GLMap === 'undefined' || !this.ac.case) return;
      const map = GLMap.getOrCreate(el, { center: GLMap.DINDIGUL_CENTER, zoom: 13 });
      const self = this._selfPoint();
      const ambulance = this._ambulancePoint();
      const pins = [];
      if (self) pins.push({ lat: self.lat, lng: self.lng, kind: 'self', pulse: true, label: this.t('console.map.you') });
      if (ambulance) pins.push({ lat: ambulance.lat, lng: ambulance.lng, kind: 'ambulance-live', pulse: true, label: this._ambulanceLabel() });

      if (this.ac.case.selected_hospital_id && this.ac.ranking?.classes) {
        const chosen = Object.values(this.ac.ranking.classes)
          .find(h => h && h.hospital_id === this.ac.case.selected_hospital_id);
        if (chosen?.latitude != null) {
          pins.push({ lat: chosen.latitude, lng: chosen.longitude, kind: 'hospital-selected', label: chosen.name });
        }
        GLMap.setPins(map, pins);
        GLMap.drawRoute(map, this.ac.route?.route_path);
      } else {
        for (const cls of ['economical', 'moderate', 'expensive']) {
          const h = this.ac.ranking?.classes?.[cls];
          if (h?.latitude != null) pins.push({ lat: h.latitude, lng: h.longitude, kind: 'hospital', label: `${h.name} (${this.t('console.case.class' + cls[0].toUpperCase() + cls.slice(1))})` });
        }
        GLMap.drawRoute(map, null);
        GLMap.setPins(map, pins);
      }
    },

    async logSymptoms() {
      try {
        const checklist = this.sym.list.length ? this.sym.list : ['chest_pain'];
        if (this.voice.transcript) {
          // Voice method (FR-1 step 2): the helper reviewed/edited the derived
          // fields below — this persists them plus the original transcript.
          await this.api('POST', `/cases/${this.activeCase}/assessment/confirm`, {
            criticality_level: this.sym.crit,
            symptom_checklist: checklist,
            raw_voice_transcript: this.voice.transcript,
            confirm: true,
          });
        } else {
          await this.api('POST', `/cases/${this.activeCase}/assessment/checklist`, {
            criticality_level: this.sym.crit,
            symptom_checklist: checklist,
            confirm: true,
          });
        }
        this.editSymptoms = false;
        this.voice.transcript = '';
        this.toast(this.t('console.toast.assessmentSaved'), 'ok');
        await this.refreshCase();
      } catch {}
    },

    // ─────────────────────────── voice symptom input (FR-1 / FR-14) ───────────────────────────
    // Browser Web Speech API does the actual speech-to-text (client-side, free,
    // no key needed) — the backend's /assessment/voice stays a pure keyword
    // deriver over whatever transcript it's given (see hospital_ranking-style
    // "explainable, no ML" design). Always a proposal: the helper still reviews
    // and taps Save, same as the tap method.
    _speechLang() {
      return { en: 'en-IN', hi: 'hi-IN', ta: 'ta-IN', bn: 'bn-IN' }[this.lang] || 'en-IN';
    },
    // Shared factory: both the initial-assessment mic and the follow-up-note
    // mic use the browser's own speech recognizer, just with a different
    // result handler (one calls /assessment/voice to derive fields, the other
    // just appends plain text to a note draft).
    _recognizeSpeech(onText) {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) return null;
      const rec = new SR();
      rec.lang = this._speechLang();
      rec.interimResults = false;
      rec.maxAlternatives = 1;
      rec.onresult = (e) => {
        const text = [...e.results].map((r) => r[0].transcript).join(' ').trim();
        if (text) onText(text);
      };
      return rec;
    },
    toggleVoiceInput() {
      if (this.voice.listening) { this._recognition?.stop(); this.voice.listening = false; return; }
      const rec = this._recognizeSpeech((text) => this._applyVoiceTranscript(text));
      if (!rec) return;
      rec.onerror = () => { this.voice.listening = false; this.toast(this.t('console.voice.error'), 'error'); };
      rec.onend = () => { this.voice.listening = false; };
      this._recognition = rec;
      this.voice.listening = true;
      rec.start();
    },
    async _applyVoiceTranscript(text) {
      this.voice.busy = true;
      try {
        const d = await this.api('POST', `/cases/${this.activeCase}/assessment/voice`, {
          transcript: text,
          language_code: this.lang,
        });
        this.voice.transcript = d.raw_voice_transcript;
        // A separate snapshot+matches pair, kept distinct from the editable
        // `voice.transcript` above: this is "what we heard and matched, right
        // now" for trust/transparency, not itself editable — if the helper
        // edits the notes box afterward the two are free to diverge.
        this.voice.heardSnapshot = d.raw_voice_transcript;
        this.voice.matches = d.matched_keywords || [];
        if (d.criticality_level) this.sym.crit = d.criticality_level;
        if (d.symptom_checklist?.length) this.sym.list = d.symptom_checklist;
      } catch {} finally {
        this.voice.busy = false;
      }
    },
    _escapeHtml(s) {
      return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    },
    // Wraps every matched keyword occurrence in <mark> so the helper can see
    // *why* something was derived — purely presentational, never changes what
    // gets saved. Longest keywords first so an overlapping short one (e.g.
    // "vomit" inside a longer phrase) doesn't split a longer match apart.
    _highlightKeywords(text, matches) {
      if (!text) return '';
      let html = this._escapeHtml(text);
      const keywords = [...new Set((matches || []).map((m) => m.keyword))].sort((a, b) => b.length - a.length);
      for (const kw of keywords) {
        const escaped = this._escapeHtml(kw).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        html = html.replace(new RegExp(`(${escaped})`, 'gi'), '<mark class="gl-note-highlight">$1</mark>');
      }
      return html;
    },
    highlightedHeardSnapshot() {
      return this._highlightKeywords(this.voice.heardSnapshot, this.voice.matches);
    },
    noteHtml(note) {
      return this._highlightKeywords(note.text, note.matched_keywords);
    },

    // ─────────────────────────── follow-up case notes (FR-1 refinement) ───────────────────────────
    // Append-only updates a helper can log at any point during a case — never
    // overwrites the initial assessment, never itself changes the saved
    // symptom_checklist/criticality_level.
    toggleNoteVoiceInput() {
      if (this.newNote.listening) { this._noteRecognition?.stop(); this.newNote.listening = false; return; }
      const rec = this._recognizeSpeech((text) => {
        this.newNote.text = this.newNote.text ? `${this.newNote.text} ${text}` : text;
      });
      if (!rec) return;
      rec.onerror = () => { this.newNote.listening = false; this.toast(this.t('console.voice.error'), 'error'); };
      rec.onend = () => { this.newNote.listening = false; };
      this._noteRecognition = rec;
      this.newNote.listening = true;
      rec.start();
    },
    async addNote() {
      const text = this.newNote.text.trim();
      if (!text) return;
      try {
        await this.api('POST', `/cases/${this.activeCase}/notes`, {
          author_id: this.session.user_id,
          text,
        });
        this.newNote.text = '';
        this.notes = await this.api('GET', `/cases/${this.activeCase}/notes`, null, { quiet: true }).catch(() => this.notes);
        this.toast(this.t('console.toast.noteAdded'), 'ok');
      } catch {}
    },

    // Both paths: the helper taps one of the 3 cost-class hospitals shown,
    // after asking the family inside the ambulance which class they'd like.
    // Family never selects — see ranking-distance-over-scheme / this session's
    // "helper picks a class" redesign.
    async selectHospitalClass(hospitalId) {
      try {
        const path = this.ac.case?.creation_path === 'A' ? 'select-hospital' : 'confirm-hospital';
        await this.api('POST', `/cases/${this.activeCase}/${path}`, {
          hospital_id: hospitalId,
          helper_id: this.session.user_id,
        });
        this.toast(this.t('console.toast.hospitalConfirmed'), 'ok');
        await this.refreshCase();
      } catch {}
    },

    deviate() {
      // FR-15: never blocks — just widen the ETA range slightly and note it.
      const r = this.ac.route;
      if (!r) return;
      r.eta_min_minutes = r.eta_min_minutes + 1;
      r.eta_max_minutes = r.eta_max_minutes + 3;
      this.ac.deviationNote = this.t('console.case.deviationNote');
    },

    async genQr() {
      try {
        const d = await this.api('POST', `/cases/${this.activeCase}/qr-handoff`);
        this.ac.qr = { case_id: d.case_id, token: d.token };
        this.toast(this.t('console.toast.qrMinted'), 'ok');
      } catch {}
    },

    async discharge() {
      try {
        await this.api('POST', `/cases/${this.activeCase}/trigger-discharge`);
        this.toast(this.t('console.toast.discharged'), 'ok');
        await this.refreshCase();
      } catch {}
    },

    // ─────────────────────────── family / SOS ───────────────────────────
    // Phone verification happened on the landing page (client/index.html); it
    // left the verified otp_verification_id here for this one SOS trigger.
    _familyOtpId() {
      try {
        const id = localStorage.getItem(FAMILY_OTP_KEY);
        if (!id) this.fam.otpMissing = true;
        return id;
      } catch { this.fam.otpMissing = true; return null; }
    },
    async triggerSos() {
      const otpId = this._familyOtpId();
      if (!otpId || !this.fam.gps) return;
      try {
        const d = await this.api('POST', '/cases/sos', {
          family_phone_number: this.fam.phone.trim(),
          family_gps: this.fam.gps,
          otp_verification_id: otpId,
        });
        this.familyCaseId = d.case.case_id;
        try { localStorage.removeItem(FAMILY_OTP_KEY); } catch {}   // one-time use, consumed server-side too
        this.toast(d.merged_into_existing_case ? this.t('console.toast.mergedSos') : this.t('console.toast.dispatched'), 'ok');
      } catch {}
    },

    // ─────────────────────────── hospital: beds ───────────────────────────
    async loadBeds() {
      const hid = this.session.hospital_id;
      try {
        const dash = await this.api('GET', '/hospitals/dashboard');
        this.hospDash = dash.find(d => d.hospital_id === hid) || dash[0];
        // admin has no hospital_id of its own — fall back to whichever
        // hospital ended up in hospDash (see the line above) so this never
        // requests /hospitals/null/sync-status.
        const resolvedHid = this.hospDash?.hospital_id || hid;
        this.syncStatus = resolvedHid ? await this.api('GET', `/hospitals/${resolvedHid}/sync-status`) : null;
        await this.loadBedCategories();
      } catch {}
    },
    async loadBedCategories() {
      const hid = this.hospDash?.hospital_id || this.session.hospital_id;
      if (!hid) return;
      try { this.bedCategories = await this.api('GET', `/hospitals/${hid}/bed-categories`); } catch { this.bedCategories = []; }
    },
    async saveBedCategory(code, label, totalBeds) {
      const hid = this.hospDash?.hospital_id || this.session.hospital_id;
      try {
        await this.api('PUT', `/hospitals/${hid}/bed-categories/${code}`, { label, total_beds: Number(totalBeds) });
        await this.loadBedCategories();
      } catch {}
    },
    async addBedCategory() {
      const code = this.newCategory.code.trim().toLowerCase().replace(/\s+/g, '_');
      if (!code || !this.newCategory.label.trim()) return;
      await this.saveBedCategory(code, this.newCategory.label.trim(), this.newCategory.total_beds);
      this.newCategory = { code: '', label: '', total_beds: 0 };
    },

    // ─────────────────────────── hospital: patient census (FR-18) ───────────────────────────
    async loadCensus() {
      // Admin/control_room have no hospital_id of their own — they get the
      // unscoped cross-hospital view (same pattern as /blood-bank-holds).
      const path = this.session.hospital_id
        ? `/hospitals/${this.session.hospital_id}/patients${this.censusFilter ? '?status=' + this.censusFilter : ''}`
        : '/patients';
      try { this.census = await this.api('GET', path); } catch { this.census = []; }
    },
    async addPatient() {
      if (!this.newPatient.full_name.trim() || !this.session.hospital_id) return;
      try {
        await this.api('POST', `/hospitals/${this.session.hospital_id}/patients`, {
          full_name: this.newPatient.full_name.trim(),
          approx_age: this.newPatient.approx_age || null,
          gender: this.newPatient.gender,
          patient_type: this.newPatient.patient_type,
        });
        this.newPatient = { full_name: '', approx_age: null, gender: 'male', patient_type: 'walk_in' };
        await this.loadCensus();
      } catch {}
    },
    async admitPatient(patientId) {
      const categoryCode = (this.admitCategory[patientId] || 'general').trim();
      try {
        await this.api('POST', `/patients/${patientId}/admit`, { category_code: categoryCode });
        this.toast(this.t('console.census.admittedToast'), 'ok');
        await this.loadCensus();
      } catch {}
    },
    async dischargePatient(patientId) {
      try {
        await this.api('POST', `/patients/${patientId}/discharge`);
        this.toast(this.t('console.census.dischargedToast'), 'ok');
        await this.loadCensus();
      } catch {}
    },

    // ─────────────────────────── hospital: staff roster (FR-19) ───────────────────────────
    async loadRoster() {
      // Admin/control_room have no hospital_id of their own — unscoped view.
      const path = this.session.hospital_id ? `/hospitals/${this.session.hospital_id}/staff` : '/staff';
      try { this.roster = await this.api('GET', path); } catch { this.roster = []; }
    },
    async addStaff() {
      if (!this.newStaff.full_name.trim() || !this.session.hospital_id) return;
      try {
        await this.api('POST', `/hospitals/${this.session.hospital_id}/staff`, {
          full_name: this.newStaff.full_name.trim(),
          staff_category: this.newStaff.staff_category,
          specialty: this.newStaff.specialty.trim() || null,
          phone_number: this.newStaff.phone_number.trim() || null,
        });
        this.newStaff = { full_name: '', staff_category: 'doctor', specialty: '', phone_number: '' };
        await this.loadRoster();
      } catch {}
    },
    async setOnDuty(staffId, status) {
      try {
        await this.api('PATCH', `/staff/${staffId}/on-duty-status`, { on_duty_status: status });
        await this.loadRoster();
      } catch {}
    },
    async removeStaff(staffId) {
      try {
        await this.api('DELETE', `/staff/${staffId}`);
        this.toast(this.t('console.roster.removedToast'), 'ok');
        await this.loadRoster();
      } catch {}
    },

    // ─────────────────────────── hospital: staff attendance (FR-20) ───────────────────────────
    async clockIn(staffId) {
      try {
        await this.api('POST', `/staff/${staffId}/clock-in`, {});
        this.toast(this.t('console.roster.clockedInToast'), 'ok');
        await this.loadRoster();
        if (this.attendanceOpenFor === staffId) await this.loadAttendanceHistory(staffId);
      } catch {}
    },
    async clockOut(staffId) {
      try {
        await this.api('POST', `/staff/${staffId}/clock-out`);
        this.toast(this.t('console.roster.clockedOutToast'), 'ok');
        await this.loadRoster();
        if (this.attendanceOpenFor === staffId) await this.loadAttendanceHistory(staffId);
      } catch {}
    },
    async loadAttendanceHistory(staffId) {
      try { this.attendanceHistory = await this.api('GET', `/staff/${staffId}/attendance`); }
      catch { this.attendanceHistory = []; }
    },
    async toggleAttendanceHistory(staffId) {
      if (this.attendanceOpenFor === staffId) { this.attendanceOpenFor = null; return; }
      this.attendanceOpenFor = staffId;
      await this.loadAttendanceHistory(staffId);
    },

    // ─────────────────────────── hospital: inventory (FR-21) ───────────────────────────
    async loadInventory() {
      // Admin/control_room have no hospital_id of their own — unscoped view.
      const path = this.session.hospital_id ? `/hospitals/${this.session.hospital_id}/inventory` : '/inventory';
      try { this.inventory = await this.api('GET', path); } catch { this.inventory = []; }
    },
    async addInventoryItem() {
      if (!this.newInvItem.item_name.trim() || !this.newInvItem.unit.trim() || !this.session.hospital_id) return;
      try {
        await this.api('POST', `/hospitals/${this.session.hospital_id}/inventory`, {
          item_name: this.newInvItem.item_name.trim(),
          category: this.newInvItem.category,
          unit: this.newInvItem.unit.trim(),
          quantity_on_hand: this.newInvItem.quantity_on_hand || 0,
          low_stock_threshold: this.newInvItem.low_stock_threshold || null,
        });
        this.newInvItem = { item_name: '', category: 'medicine', unit: '', quantity_on_hand: 0, low_stock_threshold: null };
        await this.loadInventory();
      } catch {}
    },
    async adjustInventory(itemId, delta, reason) {
      try {
        await this.api('POST', `/inventory/${itemId}/adjust`, { delta, reason });
        await this.loadInventory();
      } catch {}
    },

    // ─────────────────────────── hospital: rule-based fuzzy import (FR-22) ───────────────────────────
    importTargetFields() {
      return IMPORT_TARGET_FIELDS[this.importTargetTable] || [];
    },
    resetImport() {
      this.importReport = null;
      this.importMapping = {};
      this.importResult = null;
      this.importSheetUrl = '';
    },
    _seedMappingFromReport() {
      this.importMapping = Object.fromEntries(
        this.importReport.columns.map(c => [c.source_column, c.matched_field])
      );
      // The <select x-model>'s <option>s are built by a sibling x-for over
      // importTargetFields() in the same render pass — Alpine can set the
      // select's displayed value before those options exist yet, leaving it
      // showing "ignore" even though the underlying model is correct. A
      // setTimeout(…,0) (not $nextTick — see the map-view gotcha in project
      // memory) re-nudges the reactive object once the DOM has settled, which
      // makes the <select>s pick up the right displayed option.
      setTimeout(() => { this.importMapping = { ...this.importMapping }; }, 0);
    },
    async previewImportFile(fileInputEl) {
      const file = fileInputEl?.files?.[0];
      if (!file || !this.session.hospital_id) return;
      const form = new FormData();
      form.append('target_table', this.importTargetTable);
      form.append('file', file);
      try {
        this.importResult = null;
        this.importReport = await this.apiUpload('POST', `/hospitals/${this.session.hospital_id}/import/preview-file`, form);
        this._seedMappingFromReport();
      } catch {}
    },
    async previewImportSheet() {
      if (!this.importSheetUrl.trim() || !this.session.hospital_id) return;
      try {
        this.importResult = null;
        this.importReport = await this.api('POST', `/hospitals/${this.session.hospital_id}/import/preview-sheet`, {
          sheet_url: this.importSheetUrl.trim(), target_table: this.importTargetTable,
        });
        this._seedMappingFromReport();
      } catch {}
    },
    async commitImport() {
      if (!this.importReport) return;
      try {
        this.importResult = await this.api(
          'POST',
          `/hospitals/${this.session.hospital_id}/import/${this.importReport.import_session_id}/commit`,
          { column_mapping: this.importMapping },
        );
        this.toast(this.t('console.import.committedToast'), 'ok');
      } catch {}
    },
    async discardImport() {
      if (!this.importReport) return;
      try {
        await this.api('DELETE', `/hospitals/${this.session.hospital_id}/import/${this.importReport.import_session_id}`);
      } catch {}
      this.resetImport();
    },
    async adjustBeds(bedType, delta) {
      const hid = this.hospDash?.hospital_id || this.session.hospital_id;
      try {
        await this.api('POST', `/hospitals/${hid}/beds/adjust`, { bed_type: bedType, delta });
        await this.loadBeds();
      } catch {}
    },
    async syncHms() {
      const hid = this.hospDash?.hospital_id || this.session.hospital_id;
      try { const d = await this.api('POST', `/hospitals/${hid}/sync/hms`); this.toast(d.event.note, 'ok'); await this.loadBeds(); } catch {}
    },
    async syncSheet() {
      const hid = this.hospDash?.hospital_id || this.session.hospital_id;
      try { const d = await this.api('POST', `/hospitals/${hid}/sync/sheet`, { sheet_url: this.sheetUrl }); this.toast(d.event.note, 'ok'); await this.loadBeds(); } catch {}
    },
    async reportUsage() {
      const hid = this.hospDash?.hospital_id || this.session.hospital_id;
      try {
        await this.api('PUT', `/hospitals/${hid}/reported-bed-usage`, { reported_general_in_use: this.report.gen, reported_icu_in_use: this.report.icu });
        this.toast(this.t('console.toast.reportedControlRoom'), 'ok');
      } catch {}
    },

    // ─────────────────────────── hospital: incoming case ───────────────────────────
    async openHospCase(id, { keepAdmit = false } = {}) {
      const wasAdmit = keepAdmit && this.hc.admitOk;
      this.hc = { admitOk: wasAdmit };
      try {
        this.hc.case = await this.api('GET', `/cases/${id}`);
        this.hc.assessment = await this.api('GET', `/cases/${id}/assessment`, null, { quiet: true }).catch(() => null);
        this.hc.notes = await this.api('GET', `/cases/${id}/notes`, null, { quiet: true }).catch(() => []);
        this.hc.prep = await this.api('GET', `/cases/${id}/prep-actions`, null, { quiet: true }).catch(() => null);
        this.scan.caseId = id;
      } catch {}
    },
    async confirmPrep(prepId) {
      try {
        await this.api('POST', `/prep-actions/${prepId}/confirm`, { receptionist_id: this.session.user_id });
        this.toast(this.t('console.toast.prepConfirmed'), 'ok');
        if (this.hc.case) this.hc.prep = await this.api('GET', `/cases/${this.hc.case.case_id}/prep-actions`);
      } catch {}
    },
    async scanQr() {
      try {
        await this.api('POST', '/qr-handoff/scan', { case_id: this.scan.caseId.trim(), token: this.scan.token.trim(), scanned_by: this.session.user_id });
        this.hc.admitOk = true;
        this.toast(this.t('console.toast.admitted'), 'ok');
        if (this.hc.case) await this.openHospCase(this.hc.case.case_id, { keepAdmit: true });
        this.scan.token = '';
        await this.loadBeds();
      } catch {}
    },

    // ─────────────────────────── blood bank ───────────────────────────
    async loadHolds() {
      // Admin has no blood_bank_id of its own — it gets the unscoped
      // all-banks view instead of the coordinator's single-bank one.
      const path = this.session.blood_bank_id
        ? `/blood-banks/${this.session.blood_bank_id}/holds`
        : '/blood-bank-holds';
      try { this.holds = await this.api('GET', path); } catch { this.holds = []; }
    },
    async decideHold(id, decision) {
      try {
        await this.api('POST', `/blood-bank-holds/${id}/${decision}`, { coordinator_id: this.session.user_id });
        this.toast(this.t(decision === 'confirm' ? 'console.toast.holdConfirmed' : 'console.toast.holdRejected'), 'ok');
        await this.loadHolds();
      } catch {}
    },

    // ─────────────────────────── control room ───────────────────────────
    async runScan() {
      try {
        const d = await this.api('POST', '/control-room/scan');
        const msg = this.t('console.toast.scanResult')
          .replace('{total}', d.total)
          .replace('{anomaly}', d.anomaly_flag_ids.length)
          .replace('{conflict}', d.conflict_flag_ids.length)
          .replace('{reconciliation}', d.reconciliation_flag_ids.length);
        this.toast(msg, 'ok');
        await this.loadFlags();
      } catch {}
    },
    async loadFlags() {
      try { this.flags = await this.api('GET', '/control-room/flags?include_resolved=true'); } catch { this.flags = []; }
    },
    async resolveFlag(id) {
      try {
        await this.api('POST', `/control-room/flags/${id}/resolve`, { resolution_note: this.resolveNotes[id] || 'reviewed by operator' });
        this.toast(this.t('console.toast.flagResolved'), 'ok');
        await this.loadFlags();
      } catch {}
    },
    async loadOversight() {
      this.conflicts = await this.api('GET', '/bed-locks/conflicts', null, { quiet: true }).catch(() => []);
      this.rateFlags = await this.api('GET', '/rate-limit-flags', null, { quiet: true }).catch(() => []);
      this.deletions = await this.api('GET', '/deletion-requests', null, { quiet: true }).catch(() => []);
    },
    async processDeletion(id) {
      try { await this.api('POST', `/deletion-requests/${id}/process`); this.toast(this.t('console.toast.deletionProcessed'), 'ok'); await this.loadOversight(); } catch {}
    },

    // ─────────────────────────── admin: hospitals ───────────────────────────
    async loadHospitals() {
      try { this.hospitals = await this.api('GET', '/hospitals'); } catch { this.hospitals = []; }
    },
    async setTier(hid, tier) {
      try {
        await this.api('PUT', `/hospitals/${hid}/sync-tier`, { hospital_sync_tier: tier });
        this.toast(`${hid} → ${tier}`, 'ok');
        await this.loadHospitals();
      } catch {}
    },
    async resetDemoData() {
      try {
        await this.api('POST', '/admin/reset-demo-data');
        this.resetConfirming = false;
        this.toast(this.t('console.reset.done'), 'ok');
        this.activeCase = null;
        this.ac = {};
        await this.loadHospitals();
      } catch {}
    },

    // ─────────────────────────── admin/control-room: map overview ───────────────────────────
    async loadMapScreen() {
      try {
        const [hospitals, bloodBanks, ambulances] = await Promise.all([
          this.api('GET', '/hospitals', null, { quiet: true }),
          this.api('GET', '/blood-banks', null, { quiet: true }),
          this.api('GET', '/ambulances', null, { quiet: true }),
        ]);
        this.mapData = { hospitals, bloodBanks, ambulances };
      } catch { this.mapData = { hospitals: [], bloodBanks: [], ambulances: [] }; }
      setTimeout(() => this._renderOverviewMap(), 0);
    },
    _renderOverviewMap() {
      const el = this.$refs.overviewMap;
      if (!el || typeof GLMap === 'undefined') return;
      const map = GLMap.getOrCreate(el, { center: GLMap.DINDIGUL_CENTER, zoom: 12 });
      const pins = [
        ...this.mapData.hospitals.filter(h => h.latitude != null).map(h => ({
          lat: h.latitude, lng: h.longitude, kind: 'hospital', label: `${h.name} · ${h.cost_tier}`,
        })),
        ...this.mapData.bloodBanks.map(b => ({
          lat: b.latitude, lng: b.longitude, kind: 'blood', label: b.name,
        })),
        ...this.mapData.ambulances.map(a => ({
          lat: a.status === 'idle' ? a.base_latitude : a.current_latitude,
          lng: a.status === 'idle' ? a.base_longitude : a.current_longitude,
          kind: this.ambulanceFleetPinKind(a.status),
          pulse: a.status !== 'idle',
          alert: a.has_stale_gps_flag,
          label: `${a.vehicle_number} · ${this.ambulanceStatusLabel(a.status)}`
            + (a.has_stale_gps_flag ? ` — ${this.t('console.map.staleGps')}` : ''),
        })),
      ];
      GLMap.setPins(map, pins);
    },

    // ─────────────────────────── formatters ───────────────────────────
    statusClass(s) {
      return {
        SOS_TRIGGERED: 'gl-badge-amber',
        AMBULANCE_DISPATCHED: 'gl-badge-sky',
        OPEN: 'gl-badge-sky',
        ADMITTED: 'gl-badge-gold',
        DISCHARGED: 'gl-badge-slate',
        // FR-18 patient census statuses (lowercase — no collision with the case ones above)
        waiting: 'gl-badge-amber',
        admitted: 'gl-badge-gold',
        discharged: 'gl-badge-slate',
        cancelled: 'gl-badge-rose',
        // FR-19 on-duty statuses
        on_duty: 'gl-badge-emerald',
        off_duty: 'gl-badge-slate',
        on_leave: 'gl-badge-amber',
      }[s] || 'gl-badge-slate';
    },
    statusLabel(s) { return this.dict[`console.status.${s}`] || s; },
    ambulanceFleetPinKind(status) {
      return { idle: 'ambulance-idle', en_route_to_pickup: 'ambulance-en-route-pickup',
        en_route_to_hospital: 'ambulance-en-route-hospital' }[status] || 'ambulance-idle';
    },
    ambulanceStatusLabel(status) { return this.t('console.ambulanceStatus.' + status); },
    criticalityLabel(lvl) { return this.dict[`console.criticality.${lvl}`] || lvl; },
    symptomLabel(sym) { return this.dict[`console.symptom.${sym}`] || sym.replace(/_/g, ' '); },
    symptomListLabel(list) { return (list || []).map(s => this.symptomLabel(s)).join(', '); },
    fmtTime(t) { if (!t) return ''; try { return new Date(t).toLocaleTimeString(); } catch { return t; } },

    trackingLinkUrl() {
      if (!this.ac.trackingLink) return '';
      const base = new URL('../tracking-page/index.html', window.location.href);
      base.searchParams.set('token', this.ac.trackingLink.token);
      return base.toString();
    },
    async copyTrackingLink() {
      try {
        await navigator.clipboard.writeText(this.trackingLinkUrl());
        this.toast(this.t('console.toast.linkCopied'), 'ok');
      } catch {
        this.toast(this.trackingLinkUrl(), 'info');
      }
    },

    hospitalLine(h) {
      const gen = h.available_general_beds ?? h.live_bed_count;
      const icu = h.available_icu_beds ?? h.live_icu_count;
      return `${h.cost_tier} · ${h.eta_minutes} ${this.t('console.unit.min')} / ${h.distance_km} ${this.t('console.unit.km')} · `
        + `${this.t('console.unit.rating')} ${h.rating} · ${gen} ${this.t('console.unit.gen')} / ${icu} ${this.t('console.unit.icuFree')}`;
    },
    bedLockLine(bl) {
      return `${bl.bed_type} ${this.t('console.unit.bedAt')} ${bl.hospital_id}`;
    },
    conflictLine(c) {
      return `${c.hospital_id} · ${c.bed_type} ${this.t('console.unit.bedCases')} `
        + `${(c.case_id_a || '').slice(0, 8)} ${this.t('console.unit.vs')} ${(c.case_id_b || '').slice(0, 8)}`;
    },
    rateFlagLine(r) {
      return `${r.source} · ${r.request_count} ${this.t('console.unit.reqsPer')} ${r.window_seconds}${this.t('console.unit.seconds')}`;
    },
    deletionLine(d) {
      return `${this.t('console.case.caseIdLabel')} ${d.case_id.slice(0, 8)} · ${this.statusLabel(d.status)}`;
    },
  }));
});

// Helper app configuration.
export const API_BASE = 'http://localhost:8000';

// Demo helper account (FR-11: staff log in with id + password; seeded dev
// password is "<user_id>.sih2026"). A real build collects these on a login screen.
export const DEMO_HELPER = { user_id: 'HLP-001', password: 'HLP-001.sih2026' };

// FR-14: fallback list used only if GET /languages can't be reached. The backend
// (app/config.py::SUPPORTED_LANGUAGES) is the source of truth; loadLanguages()
// in i18n.js refreshes this from the API so the UI + FR-1 voice input stay in sync.
export const FALLBACK_LANGUAGES = { en: 'English', hi: 'Hindi', ta: 'Tamil', bn: 'Bengali' };

export const STORAGE_KEYS = {
  lang: 'helper.lang',
  queue: 'helper.offlineQueue',
  lastLocation: 'helper.lastKnownLocation',
  hospitalSnapshot: 'helper.offlineHospitalList',
  token: 'helper.token',
  simulateOffline: 'helper.simulateOffline',
};

// FR-13 item 4: how often to refresh the on-device hospital snapshot.
export const HOSPITAL_SNAPSHOT_TTL_MS = 15 * 60 * 1000;

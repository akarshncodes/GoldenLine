import { API_BASE, DEMO_HELPER } from './config.js';
import {
  applyTranslations, currentLanguage, loadLanguages, onLanguageChange,
  setLanguage, supportedLanguages, t,
} from './i18n.js';
import { getToken, isOffline, mutate, setSimulateOffline, setToken } from './api.js';
import { onQueueChange, pendingCount, startAutoSync } from './offline-queue.js';
import { getLocation } from './location.js';
import { getOfflineHospitalList, refreshHospitalSnapshot } from './hospital-cache.js';
import { formatEtaRange } from './eta.js';
import { acknowledgeDeviation, routeSummary } from './safe-driving.js';
import { sendCriticalUpdateBySms } from './sms-fallback.js';

const $ = (sel) => document.querySelector(sel);
const state = { caseId: null, hospitalId: null, route: null, screen: 'new-case', voiceLang: 'en' };

// ---------- connection + location chrome ----------------------------------
function renderConnBar(status) {
  const bar = $('#conn-bar');
  const n = pendingCount();
  bar.dataset.state = isOffline() ? 'offline' : status || 'online';
  if (isOffline()) bar.textContent = `⚠ ${t('conn.offline')}` + (n ? ` — ${t('conn.queued', { count: n })}` : '');
  else if (status === 'syncing') bar.textContent = `↻ ${t('conn.syncing', { count: n })}`;
  else if (n) bar.textContent = `↻ ${t('conn.queued', { count: n })}`;
  else bar.textContent = `● ${t('conn.online')}`;
}

async function renderLocationChip() {
  const chip = $('#loc-chip');
  const loc = await getLocation();
  chip.textContent = (loc.estimated ? '≈ ' : '◉ ') + loc.label;
  chip.dataset.estimated = String(loc.estimated); // FR-13: estimated never looks like live
  return loc;
}

// ---------- screens ------------------------------------------------------
function screenNewCase() {
  return `
    <h2 data-i18n="case.start"></h2>
    <label data-i18n="case.nokPhone" for="nok"></label>
    <input id="nok" inputmode="numeric" value="9123456780" />
    <button id="do-create" class="primary" data-i18n="nav.newCase"></button>
    <p id="new-case-out" class="out"></p>`;
}

function screenSymptoms() {
  const opts = ['critical', 'serious', 'stable']
    .map((k) => `<label><input type="radio" name="crit" value="${k === 'critical' ? 'Critical' : k === 'serious' ? 'Serious' : 'Stable'}" ${k === 'serious' ? 'checked' : ''}/> <span data-i18n="sym.${k}"></span></label>`)
    .join('');
  const syms = ['chest_pain', 'breathing_difficulty', 'visible_bleeding', 'trauma', 'high_fever']
    .map((s) => `<label><input type="checkbox" name="sym" value="${s}"/> ${s.replace(/_/g, ' ')}</label>`)
    .join('');
  return `
    <h2 data-i18n="nav.symptoms"></h2>
    <fieldset><legend data-i18n="sym.criticality"></legend>${opts}</fieldset>
    <fieldset><legend data-i18n="sym.checklist"></legend>${syms}</fieldset>
    <p class="hint" data-i18n="sym.voiceHint"></p>
    <button id="do-symptoms" class="primary" data-i18n="sym.confirm"></button>
    <p id="sym-out" class="out"></p>`;
}

async function screenHospital() {
  let live = null;
  try { if (state.caseId) live = await (await fetch(`${API_BASE}/cases/${state.caseId}/hospital-ranking`, { headers: { authorization: `Bearer ${getToken()}` } })).json(); } catch { /* offline */ }
  let list, offline = false;
  if (live && live.classes && Object.values(live.classes).some(Boolean)) {
    // Only the 3 cost-class picks are selectable now — ask the family which
    // class, then tap that one (see backend HospitalSelectionRequest).
    list = Object.values(live.classes).filter(Boolean);
  } else {
    offline = true;
    list = (await getOfflineHospitalList()).hospitals;
  }
  const cards = list.map((h) => `
    <div class="hosp">
      <strong>${h.name}</strong>
      <div class="meta">${t('hosp.tier')}: ${h.cost_tier} · ${t('hosp.rating')}: ${h.rating}
        · ${h.available_general_beds ?? h.live_bed_count} ${t('hosp.bedGeneral')}
        · ${h.available_icu_beds ?? h.live_icu_count} ${t('hosp.bedIcu')}</div>
      <button class="pick" data-h="${h.hospital_id}" data-i18n="hosp.select"></button>
    </div>`).join('');
  return `
    <h2 data-i18n="hosp.ranked"></h2>
    ${offline ? `<p class="warn" data-i18n="hosp.offlineList"></p>` : ''}
    ${cards}
    <p id="hosp-out" class="out"></p>`;
}

async function screenRoute() {
  if (!state.route && state.caseId) {
    try { state.route = await (await fetch(`${API_BASE}/cases/${state.caseId}/route`, { headers: { authorization: `Bearer ${getToken()}` } })).json(); }
    catch { state.route = { eta_min_minutes: 12, eta_max_minutes: 16, route_source: 'stub' }; }
  }
  const r = state.route || { eta_min_minutes: 12, eta_max_minutes: 16, route_source: 'stub' };
  const sum = routeSummary(r);
  return `
    <h2 data-i18n="route.title"></h2>
    <div class="eta-range" id="eta-display">${sum.etaRangeText}</div>
    <p class="framing">${sum.framing}</p>
    <p class="hint" data-i18n="route.rangeNote"></p>
    <button id="do-deviate" data-i18n="route.deviate"></button>
    <p id="route-out" class="out"></p>`;
}

function screenSettings() {
  const langs = supportedLanguages();
  const langOpts = Object.entries(langs)
    .map(([code, name]) => `<option value="${code}" ${code === currentLanguage() ? 'selected' : ''}>${name}</option>`)
    .join('');
  return `
    <h2 data-i18n="nav.settings"></h2>
    <label data-i18n="set.language" for="lang"></label>
    <select id="lang">${langOpts}</select>
    <p class="hint" data-i18n="set.languageHint"></p>

    <label data-i18n="set.voiceLanguage" for="voice-lang"></label>
    <select id="voice-lang">${langOpts.replace(/selected/g, '').replace(`value="${state.voiceLang}"`, `value="${state.voiceLang}" selected`)}</select>
    <p class="hint" data-i18n="set.voiceLanguageNote"></p>

    <label class="toggle"><input type="checkbox" id="sim-offline" ${isOffline() ? 'checked' : ''}/> <span data-i18n="conn.simulateOffline"></span></label>`;
}

async function render() {
  // ensure we have an helper token for the demo
  if (!getToken()) {
    try {
      const r = await fetch(`${API_BASE}/auth/login`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(DEMO_HELPER) });
      if (r.ok) setToken((await r.json()).access_token);
    } catch { /* offline first launch */ }
  }

  const view = $('#view');
  const builders = {
    'new-case': screenNewCase, symptoms: screenSymptoms, hospital: screenHospital,
    route: screenRoute, settings: screenSettings,
  };
  view.innerHTML = await builders[state.screen]();
  applyTranslations(view);
  wireScreen();
  document.querySelectorAll('nav button').forEach((b) => b.classList.toggle('active', b.dataset.screen === state.screen));
  renderConnBar();
  renderLocationChip();
}

function wireScreen() {
  const el = (id) => document.getElementById(id);

  el('do-create')?.addEventListener('click', async () => {
    const loc = await renderLocationChip();
    const res = await mutate('/cases', {
      next_of_kin_phone_number: el('nok').value.trim(),
      patient: { approx_age: 55, gender: 'male' },
      helper_id: 'HLP-001',
      helper_gps: { latitude: loc.latitude ?? 10.3673, longitude: loc.longitude ?? 77.9803 },
    }, { label: t('case.start') });
    if (res.queued) el('new-case-out').textContent = '↻ ' + t('conn.queued', { count: pendingCount() });
    else { state.caseId = res.data.case_id; el('new-case-out').textContent = '✓ ' + t('case.created') + ' — ' + state.caseId.slice(0, 8); }
    renderConnBar();
  });

  el('do-symptoms')?.addEventListener('click', async () => {
    const crit = document.querySelector('input[name=crit]:checked')?.value || 'Serious';
    const syms = [...document.querySelectorAll('input[name=sym]:checked')].map((c) => c.value);
    if (!state.caseId) { el('sym-out').textContent = '⚠ start a case first'; return; }
    const res = await mutate(`/cases/${state.caseId}/assessment/checklist`,
      { criticality_level: crit, symptom_checklist: syms.length ? syms : ['chest_pain'], confirm: true },
      { label: t('nav.symptoms') });
    el('sym-out').textContent = res.queued
      ? '↻ ' + t('conn.queued', { count: pendingCount() })
      : '✓ ' + t('sym.saved');
    renderConnBar();
  });

  document.querySelectorAll('.pick').forEach((btn) => btn.addEventListener('click', async () => {
    state.hospitalId = btn.dataset.h;
    if (!state.caseId) { el('hosp-out').textContent = '⚠ start a case first'; return; }
    const res = await mutate(`/cases/${state.caseId}/confirm-hospital`,
      { hospital_id: state.hospitalId, helper_id: 'HLP-001' }, { label: t('nav.hospital') });
    el('hosp-out').textContent = res.queued
      ? '↻ ' + t('conn.queued', { count: pendingCount() })
      : '✓ ' + t('hosp.selected');
    renderConnBar();
  }));

  el('do-deviate')?.addEventListener('click', () => {
    const r = state.route || { eta_min_minutes: 12, eta_max_minutes: 16 };
    const d = acknowledgeDeviation(r);        // FR-15: never blocks, just recalculates
    state.route = { ...r, eta_min_minutes: d.eta_min_minutes, eta_max_minutes: d.eta_max_minutes };
    el('eta-display').textContent = d.etaRangeText;
    el('route-out').textContent = d.message;
  });

  el('lang')?.addEventListener('change', (e) => setLanguage(e.target.value));
  el('voice-lang')?.addEventListener('change', (e) => { state.voiceLang = e.target.value; });
  el('sim-offline')?.addEventListener('change', (e) => { setSimulateOffline(e.target.checked); renderConnBar(); });
}

// ---------- boot -------------------------------------------------------
async function boot() {
  const { current } = await loadLanguages();
  state.voiceLang = current;
  document.documentElement.lang = current;

  applyTranslations(document);
  onLanguageChange(() => { applyTranslations(document); render(); });
  onQueueChange(() => renderConnBar());
  window.addEventListener('online', () => renderConnBar());
  window.addEventListener('offline', () => renderConnBar());

  document.querySelectorAll('nav button').forEach((b) =>
    b.addEventListener('click', () => { state.screen = b.dataset.screen; render(); }));

  startAutoSync(getToken, { onStatus: (s) => renderConnBar(s) });
  refreshHospitalSnapshot(getToken);

  await render();
}

boot();

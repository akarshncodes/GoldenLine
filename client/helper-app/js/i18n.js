// FR-14: i18n engine. Every user-facing string comes from js/i18n/<lang>.json —
// UI components must resolve every string through t(...), never embed literals.
import { API_BASE, FALLBACK_LANGUAGES, STORAGE_KEYS } from './config.js';

let bundles = {};          // { en: {...}, hi: {...}, ... }
let supported = { ...FALLBACK_LANGUAGES };
let current = 'en';
const listeners = new Set();

async function fetchJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return r.json();
}

// FR-14 item 3: the supported-language list comes from the SAME backend config
// that FR-1 voice input validates against (GET /languages).
export async function loadLanguages() {
  try {
    const data = await fetchJson(`${API_BASE}/languages`);
    supported = data.supported;
  } catch {
    supported = { ...FALLBACK_LANGUAGES };
  }
  await Promise.all(
    Object.keys(supported).map(async (code) => {
      try {
        bundles[code] = await fetchJson(new URL(`./i18n/${code}.json`, import.meta.url));
      } catch {
        bundles[code] = bundles[code] || {};
      }
    })
  );
  const saved = localStorage.getItem(STORAGE_KEYS.lang);
  current = supported[saved] ? saved : 'en';
  return { supported, current };
}

export function supportedLanguages() {
  return { ...supported };
}

export function currentLanguage() {
  return current;
}

export function setLanguage(code) {
  if (!supported[code]) return;
  current = code;
  try { localStorage.setItem(STORAGE_KEYS.lang, code); } catch { /* private mode */ }
  document.documentElement.lang = code;
  listeners.forEach((fn) => fn(code));
}

export function onLanguageChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

// t('route.etaRange', { min: 12, max: 16 }) -> "ETA 12–16 minutes"
export function t(key, params = {}) {
  const bundle = bundles[current] || {};
  const fallback = bundles.en || {};
  let str = bundle[key] ?? fallback[key] ?? key;
  return str.replace(/\{(\w+)\}/g, (_, name) => (name in params ? String(params[name]) : `{${name}}`));
}

// Apply translations to any element carrying data-i18n / data-i18n-attr.
export function applyTranslations(root = document) {
  root.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  root.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    el.setAttribute('placeholder', t(el.dataset.i18nPlaceholder));
  });
  root.querySelectorAll('[data-i18n-aria-label]').forEach((el) => {
    el.setAttribute('aria-label', t(el.dataset.i18nAriaLabel));
  });
}

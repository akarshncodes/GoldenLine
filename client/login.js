/* GoldenLine — landing / login page logic.
 *
 * Establishes ONE real session (staff password login, family OTP, or a
 * password reset) and hands off to the Operator Console. The console itself
 * has no login UI any more — it just reads the token this page writes and
 * auto-detects the account's role.
 */
const API = 'http://localhost:8000';
const TOKEN_KEY = 'goldenline.token';
const FAMILY_OTP_KEY = 'goldenline.family.otpId';
const FAMILY_PHONE_KEY = 'goldenline.family.phone';
const LANG_KEY = 'goldenline.lang';

const NATIVE_NAMES = { en: 'English', hi: 'हिन्दी', ta: 'தமிழ்', bn: 'বাংলা' };
const DEMO_SUFFIX = '.sih2026';
const DEMO_ACCOUNTS = [
  { id: 'HLP-001', roleKey: 'helper' },
  { id: 'recep-hosp-001', roleKey: 'hospital' },
  { id: 'coord-bb-01', roleKey: 'bloodbank' },
  { id: 'control-room', roleKey: 'controlroom' },
  { id: 'admin', roleKey: 'admin' },
];

document.addEventListener('alpine:init', () => {
  Alpine.data('loginApp', () => ({
    // ---- i18n ----
    lang: 'en',
    dict: {},
    langOptions: Object.entries(NATIVE_NAMES).map(([code, label]) => ({ code, label })),

    // ---- ui ----
    apiUp: true,
    checkingSession: true,
    tab: 'staff',        // 'staff' | 'family'
    forgotOpen: false,
    forgotStep: 1,        // 1 = enter account id, 2 = enter code + new password

    // ---- forms ----
    staff: { id: '', pw: '', loading: false, error: '' },
    family: {
      phone: '', otpId: null, devCode: null, code: '', sentTo: '',
      loading: false, error: '', verified: false,
    },
    forgot: {
      id: '', resetTokenId: null, devCode: null, code: '',
      newPw: '', confirmPw: '', loading: false, error: '',
    },

    demoAccounts: DEMO_ACCOUNTS,

    // ─────────────────────────── lifecycle ───────────────────────────
    async init() {
      this.health();
      setInterval(() => this.health(), 20000);

      let saved;
      try { saved = localStorage.getItem(LANG_KEY); } catch { saved = null; }
      await this.setLang(saved || (navigator.language || 'en').slice(0, 2));

      await this.maybeAutoRedirect();
      this.checkingSession = false;
    },

    async health() {
      try { const r = await fetch(`${API}/health`); this.apiUp = r.ok; }
      catch { this.apiUp = false; }
    },

    t(key) {
      return this.dict[key] || key;
    },

    // Deterministic pseudo-random layout for the floating background particles
    // (no Math.random() so the scene doesn't jump on every Alpine re-render).
    particleStyle(i) {
      const seed = i * 137.5;
      const left = seed % 100;
      const top = (seed * 1.7) % 100;
      const size = 4 + (i % 5) * 2;
      const durY = 12 + (i % 6) * 2;
      const durX = 16 + (i % 5) * 2;
      const delay = (i % 7) * 0.6;
      return `left:${left}%; top:${top}%; width:${size}px; height:${size}px; `
        + `--gl-dur-y:${durY}s; --gl-dur-x:${durX}s; --gl-delay:${delay}s;`;
    },

    async setLang(code) {
      if (!NATIVE_NAMES[code]) code = 'en';
      try {
        const res = await fetch(`i18n/${code}.json`);
        this.dict = await res.json();
        this.lang = code;
        document.documentElement.lang = code;
        try { localStorage.setItem(LANG_KEY, code); } catch {}
      } catch {
        if (code !== 'en') await this.setLang('en');
      }
    },

    // Already signed in (valid token) -> skip straight to the console.
    async maybeAutoRedirect() {
      let token;
      try { token = localStorage.getItem(TOKEN_KEY); } catch { token = null; }
      if (!token) return;
      try {
        const r = await fetch(`${API}/auth/me`, { headers: { authorization: `Bearer ${token}` } });
        if (r.ok) { window.location.href = 'console/index.html'; return; }
      } catch { /* API down — let them see the login page */ }
      try { localStorage.removeItem(TOKEN_KEY); } catch {}
    },

    goConsole(token) {
      try { localStorage.setItem(TOKEN_KEY, token); } catch {}
      window.location.href = 'console/index.html';
    },

    // ─────────────────────────── staff login ───────────────────────────
    async signInStaff() {
      this.staff.error = '';
      this.staff.loading = true;
      try {
        const res = await fetch(`${API}/auth/login`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ user_id: this.staff.id.trim(), password: this.staff.pw }),
        });
        if (res.status === 401) { this.staff.error = this.t('auth.invalidCredentials'); return; }
        if (!res.ok) { this.staff.error = this.t('error.generic'); return; }
        const data = await res.json();
        this.goConsole(data.access_token);
      } catch {
        this.staff.error = this.t('auth.networkError');
      } finally {
        this.staff.loading = false;
      }
    },

    pickDemo(account) {
      this.tab = 'staff';
      this.forgotOpen = false;
      this.staff.id = account.id;
      this.staff.pw = `${account.id}${DEMO_SUFFIX}`;
      this.signInStaff();
    },

    // ─────────────────────────── family / OTP ───────────────────────────
    async sendFamilyOtp() {
      this.family.error = '';
      const phone = this.family.phone.trim();
      if (!/^[6-9]\d{9}$/.test(phone)) { this.family.error = this.t('error.generic'); return; }
      this.family.loading = true;
      try {
        const res = await fetch(`${API}/otp/request`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ phone_number: phone }),
        });
        if (!res.ok) { this.family.error = this.t('error.generic'); return; }
        const data = await res.json();
        this.family.otpId = data.otp_verification_id;
        this.family.devCode = data.dev_code;
        this.family.code = data.dev_code || '';
        this.family.sentTo = phone;
      } catch {
        this.family.error = this.t('auth.networkError');
      } finally {
        this.family.loading = false;
      }
    },

    async verifyFamilyOtp() {
      this.family.error = '';
      this.family.loading = true;
      try {
        const res = await fetch(`${API}/otp/verify`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ otp_verification_id: this.family.otpId, code: this.family.code.trim() }),
        });
        if (!res.ok) { this.family.error = this.t('auth.otpInvalid'); return; }
        const data = await res.json();
        // Hand off the verified OTP + phone to the console's SOS screen — a
        // Path A case still needs `otp_verification_id` at /cases/sos time.
        try {
          localStorage.setItem(FAMILY_OTP_KEY, this.family.otpId);
          localStorage.setItem(FAMILY_PHONE_KEY, this.family.sentTo);
        } catch {}
        this.goConsole(data.access_token);
      } catch {
        this.family.error = this.t('auth.networkError');
      } finally {
        this.family.loading = false;
      }
    },

    // ─────────────────────────── forgot password ───────────────────────────
    openForgot() {
      this.forgotOpen = true;
      this.forgotStep = 1;
      this.forgot = { id: this.staff.id || '', resetTokenId: null, devCode: null, code: '', newPw: '', confirmPw: '', loading: false, error: '' };
    },
    closeForgot() { this.forgotOpen = false; },

    async requestReset() {
      this.forgot.error = '';
      this.forgot.loading = true;
      try {
        const res = await fetch(`${API}/auth/forgot-password`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ user_id: this.forgot.id.trim() }),
        });
        if (res.status === 404) { this.forgot.error = this.t('auth.unknownAccount'); return; }
        if (!res.ok) { this.forgot.error = this.t('error.generic'); return; }
        const data = await res.json();
        this.forgot.resetTokenId = data.reset_token_id;
        this.forgot.devCode = data.dev_code;
        this.forgot.code = data.dev_code || '';
        this.forgotStep = 2;
      } catch {
        this.forgot.error = this.t('auth.networkError');
      } finally {
        this.forgot.loading = false;
      }
    },

    async submitReset() {
      this.forgot.error = '';
      if (this.forgot.newPw.length < 8) { this.forgot.error = this.t('forgot.tooShort'); return; }
      if (this.forgot.newPw !== this.forgot.confirmPw) { this.forgot.error = this.t('forgot.mismatch'); return; }
      this.forgot.loading = true;
      try {
        const res = await fetch(`${API}/auth/reset-password`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            reset_token_id: this.forgot.resetTokenId,
            code: this.forgot.code.trim(),
            new_password: this.forgot.newPw,
          }),
        });
        if (!res.ok) { this.forgot.error = this.t('forgot.codeInvalid'); return; }
        const data = await res.json();
        this.goConsole(data.access_token);
      } catch {
        this.forgot.error = this.t('auth.networkError');
      } finally {
        this.forgot.loading = false;
      }
    },
  }));
});

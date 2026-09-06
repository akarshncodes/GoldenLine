# Clients

| Folder / file | What it is |
|---|---|
| **`index.html`** | **The GoldenLine sign-in page — the site's front door, use this for the demo.** Animated dark/gold hero with marketing copy, a centered glass login card with **Staff Login** and **Family / OTP** tabs, one-click demo-account chips, a full **forgot-password** flow, and a 4-language switcher (English/Hindi/Tamil/Bengali — `i18n/*.json`). On success it stores one token and hands off to `console/`. If you're already signed in, it skips straight there. `login.js` + `login.css`. |
| **`console/`** | **The Operator Console** — same dark/gold theme as the sign-in page (see `theme.css` below). No login UI of its own — it reads the token `index.html` left behind, calls `GET /auth/me`, and **auto-maps the account's role to its dashboard** (helper / family / hospital receptionist / blood bank coordinator / control room / admin — no manual switcher; admin sees every dashboard combined). No valid session → bounced back to `index.html`. Drives the whole FR‑0…FR‑16 pipeline visibly: SOS/case creation → symptoms → ranking → hospital selection → bed lock → route/ETA → blood check → prep confirmation → QR handoff → bed decrement → discharge → feedback, plus the Control Room and hospital/blood‑bank dashboards. Vanilla JS + Alpine.js + Tailwind (all CDN, no build). Every failed request shows a toast — nothing fails silently. Soft fade transitions between screens; small hand-drawn SVG icons per nav item. |
| **`theme.css`** | Shared design tokens (`--gl-gold`, `--gl-deep`, …) and reusable component classes (`.gl-card`, `.gl-input`, `.gl-btn-primary/secondary/danger`, `.gl-badge` + colour modifiers, `.gl-fade-up`, …) used by **both** `index.html` and `console/` — the two pages are built from the same design system, not just similar-looking by coincidence. |
| `helper-app/` | The **FR‑13/14/15 reference client** (built in Phase 10): offline‑first sync queue, last‑known location, SMS fallback, cached hospital list; i18n (en/hi/ta/bn) whole‑app language switch; ETA‑as‑a‑range + safe‑driving guardrails. Kept as the proof of those three FRs; the sign-in page + console are the primary demo. (Not yet on the GoldenLine dark theme — plain light UI.) |
| `web-dashboard/`, `family-app/`, `tracking-page/` | Phase‑0 placeholders. Their audiences are now served by roles inside `console/`. |

## Run

```bash
# 1. backend
cd ../backend && source .venv/bin/activate && alembic upgrade head && uvicorn app.main:app --port 8000
# 2. clients (any static server), from the repo's client/ dir
python3 -m http.server 5180
```

Open **http://localhost:5180/** — the GoldenLine sign-in page.
(`/console/index.html` requires a session and redirects here if you don't have
one; `/helper-app/index.html` for the FR‑13/14/15 client.)

## Demo accounts

Staff sign in with an account id + password (`<id>.sih2026`, PBKDF2‑hashed in the
DB) — or just click a demo-account chip on the sign-in page. Family authenticates
by phone OTP (the dev code is shown on screen, no real SMS needed).

| Role | Account |
|---|---|
| Ambulance Helper | `HLP-001` |
| Hospital Receptionist | `recep-hosp-001` (Government Medical College & Hospital, Dindigul) |
| Blood Bank Coordinator | `coord-bb-01` (Govt Head Quarters Hospital Blood Bank) |
| Control Room | `control-room` |
| Admin | `admin` |

Forgot your password? Use the link on the sign-in page — it's a real flow
(`POST /auth/forgot-password` → `POST /auth/reset-password`), just with the reset
code shown on-screen instead of a real SMS/email in this dev build.

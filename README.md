# GoldenLine — Real-Time Emergency Capacity Coordination Platform (SIH 2026)

**GoldenLine** — *the golden thread between every emergency and the right bed* —
helps families and hospitals coordinate scarce emergency capacity in real time:
password login for staff (PBKDF2-hashed, with a real forgot-password flow) and
OTP-based access for families, case management, short-lived bed and blood-unit
locks, a background Control Room supervisor, tiered hospital data sync, and SMS
notifications with tracking links. Built feature-by-feature against a Functional
Requirements Plan (`docs/FRP.md`). **Current state: FR-0 … FR-16 complete (175
backend tests) + a branded landing/login page and a unified web console
(`client/index.html` → `client/console/`) that demo the whole pipeline across
every role.**

## Demo

```bash
# terminal 1 — backend
cd backend && source .venv/bin/activate && rm -f dev.db && alembic upgrade head && uvicorn app.main:app --port 8000
# terminal 2 — clients
cd client && python3 -m http.server 5180
```

Open **http://localhost:5180/** — the GoldenLine sign-in page (animated,
multi-language: English/Hindi/Tamil/Bengali). Sign in with a demo account chip
(or manually: staff password is `<account>.sih2026`; family verifies by the
on-screen OTP code) and you land straight in the **Operator Console**, auto-scoped
to that account's role (Helper / Family / Hospital Receptionist / Blood Bank /
Control Room / Admin — no manual role picker). Walk a case end to end. API docs
at http://localhost:8000/docs. See [`client/README.md`](client/README.md).

## Stack

- **Backend:** Python + FastAPI (auto OpenAPI docs at `/docs`), SQLAlchemy 2.0 ORM.
- **Database:** SQLite for local dev (zero setup); PostgreSQL-ready via `DATABASE_URL`.
- **Migrations:** Alembic.
- **Clients:** `client/index.html` (the GoldenLine sign-in page — staff login, family OTP, forgot password, 4-language i18n) → `client/console/` (unified operator console, auto-scoped by role — Alpine.js + Tailwind, CDN, no build) and `client/helper-app/` (the FR-13/14/15 reference client).

## Project structure

```
backend/            FastAPI app
  app/
    main.py         app entrypoint + router registration
    config.py       env-driven settings
    database.py     engine, session, declarative Base
    routers/        API routes (health.py for now)
    models/         ORM models (empty in Phase 0)
    schemas/        Pydantic schemas (empty in Phase 0)
    services/       business logic (empty in Phase 0)
  alembic/          migration environment + versions/
  requirements.txt
  .env.example
client/             front-end placeholders (see client/README.md)
docs/               planning documents (FRP.md, Complete_Project_Picture_v3.md)
```

## Run the backend locally

Requires Python 3.11+ (tested on 3.14).

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Or use the helper script, which does all of the above:

```bash
cd backend
./run.sh
```

Then:

- API root: http://localhost:8000/
- Interactive docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Health check

`GET /health` returns `200` with `{"status":"ok","database":"up",...}` when the API
and database are both reachable, and `503` with `"status":"degraded"` otherwise.

## Phase 1 — FR-0 Case Creation

One `cases` table, `creation_path` = `A` or `B`. Endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/cases/sos` | Path A — family SOS |
| `POST` | `/cases` | Path B — helper starts a case directly |
| `POST` | `/cases/{case_id}/helper-location` | report case location from the helper device |
| `GET`  | `/cases/{case_id}` | fetch a case |

Location rule (FRP FR-0 line 85): the authoritative case location (`gps_*`) always
comes from the helper's device. In Path A the family's phone GPS is stored only
in `sos_trigger_*` (audit) and used to pick the ambulance — it never becomes the
case location. There is no self-transport fallback.

### Run the tests

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

### Manual test — Path A (SOS creates a case + dispatches an ambulance)

```bash
curl -s -X POST http://localhost:8000/cases/sos \
  -H 'content-type: application/json' \
  -d '{"family_phone_number":"9876543210","family_gps":{"latitude":28.61,"longitude":77.20}}'
```

Expect `201`: a case with `creation_path":"A"`, `status":"AMBULANCE_DISPATCHED"`,
a `dispatched_ambulance`, `gps_latitude":null` (not taken from the family phone),
and `sos_trigger_latitude":28.61`.

Then attach the helper device location (copy `case.case_id` from above):

```bash
curl -s -X POST http://localhost:8000/cases/<CASE_ID>/helper-location \
  -H 'content-type: application/json' \
  -d '{"helper_id":"HLP-002","gps":{"latitude":19.07,"longitude":72.87}}'
```

Expect `200` with `gps_source":"helper_device"` and the new coordinates.

### Manual test — Path B rejected without a valid next-of-kin number

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/cases \
  -H 'content-type: application/json' \
  -d '{"next_of_kin_phone_number":"12345","patient":{"approx_age":40,"gender":"male"},"helper_id":"HLP-001","helper_gps":{"latitude":12.97,"longitude":77.59}}'
```

Expect `422`. Same result if `next_of_kin_phone_number` is omitted entirely.

### Manual test — Path B succeeds with a valid next-of-kin number

```bash
curl -s -X POST http://localhost:8000/cases \
  -H 'content-type: application/json' \
  -d '{"next_of_kin_phone_number":"9123456780","patient":{"name":"Asha","approx_age":40,"gender":"female"},"helper_id":"HLP-001","helper_gps":{"latitude":12.97,"longitude":77.59}}'
```

Expect `201`: `creation_path":"B"`, `status":"OPEN"`, `gps_source":"helper_device"`.

## Phase 2 — FR-1 On-Scene Assessment

One symptom log per case (1:1 with a `case_id` from FR-0). Fixed data only — a
`criticality_level` enum (`Critical` / `Serious` / `Stable`) and a fixed
`symptom_checklist` of tags. **There is no free-text diagnosis field anywhere**
(request bodies reject unknown keys). Supported voice languages live in one
constant: `SUPPORTED_LANGUAGES` in [app/config.py](backend/app/config.py).

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/cases/{case_id}/assessment/checklist` | Tap method — saves directly (`confirm:true` required) |
| `POST` | `/cases/{case_id}/assessment/voice` | Voice method step 1 — transcribe (stub) + derive checklist, **not saved** |
| `POST` | `/cases/{case_id}/assessment/confirm` | Voice method step 2 — persist the reviewed checklist (`confirm:true` required) |
| `GET`  | `/cases/{case_id}/assessment` | Fetch the case's assessment |

Speech-to-text is stubbed behind `transcribe_voice(audio_or_text, language_code)`
in [app/services/assessment.py](backend/app/services/assessment.py) — it currently
returns the already-transcribed text unchanged. The checklist is derived by plain
keyword matching (no LLM).

### Full flow — create a case, log via voice, confirm

```bash
# 1. Create a case (FR-0 Path B) and capture its id
CASE_ID=$(curl -s -X POST http://localhost:8000/cases \
  -H 'content-type: application/json' \
  -d '{"next_of_kin_phone_number":"9123456780","patient":{"name":"Asha","approx_age":60,"gender":"male"},"helper_id":"HLP-001","helper_gps":{"latitude":12.97,"longitude":77.59}}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])')

# 2a. Log symptoms via checklist (tap) — saves immediately
curl -s -X POST http://localhost:8000/cases/$CASE_ID/assessment/checklist \
  -H 'content-type: application/json' \
  -d '{"criticality_level":"Serious","symptom_checklist":["chest_pain","breathing_difficulty"],"confirm":true}'

# 2b. OR log via voice-stub — returns a DERIVED checklist, saves nothing
curl -s -X POST http://localhost:8000/cases/$CASE_ID/assessment/voice \
  -H 'content-type: application/json' \
  -d '{"transcript":"Male, roughly 60, severe chest pain and breathing difficulty","language_code":"en"}'
# -> {"criticality_level":"Critical","symptom_checklist":["chest_pain","breathing_difficulty"],"saved":false,...}

# GET now returns 404 — nothing persisted from voice yet
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/cases/$CASE_ID/assessment

# 3. Confirm — persists the reviewed checklist (input_method=voice)
curl -s -X POST http://localhost:8000/cases/$CASE_ID/assessment/confirm \
  -H 'content-type: application/json' \
  -d '{"criticality_level":"Critical","symptom_checklist":["chest_pain","breathing_difficulty"],"raw_voice_transcript":"Male, roughly 60, severe chest pain and breathing difficulty","confirm":true}'

# 4. Fetch it
curl -s http://localhost:8000/cases/$CASE_ID/assessment
```

Rejections to expect: `422` for `confirm:false`, an unknown symptom tag, an
unsupported `language_code`, or any extra key such as `diagnosis`; `404` for an
assessment against a non-existent `case_id`.

## Phase 3 — FR-2 AI Hospital Ranking

Explainable in one sentence: **closest, cheapest-tier-appropriate, best-rated,
capable hospital.** No probability/ML model — STEP 1 is a lookup table
([app/services/hospital_ranking.py](backend/app/services/hospital_ranking.py)
`SYMPTOM_REQUIRED_SPECIALTY`), STEP 2 is a weighted sort (ETA + distance +
rating), STEP 3 gives scheme-accepting hospitals a **bounded nudge within their
own cost tier** — distance/time/rating stay dominant, so a clearly closer
non-scheme hospital still ranks first; the nudge never moves a hospital across
tiers. 25 real Dindigul, Tamil Nadu hospitals are seeded (migration `0006` originally seeded 10 fictional ones; migration `0024` replaced them with this real-city dataset — see [app/services/hospital_seed.py](backend/app/services/hospital_seed.py)'s module docstring for sourcing/judgment-call notes). Helper picks a cost class ("helper-driven hospital classes") instead of the family choosing.

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/hospitals` | the mock hospital dataset |
| `PUT`  | `/cases/{case_id}/scheme` | record/clear the government scheme (`ayushman_bharat`, `state_scheme`, or `null`) |
| `GET`  | `/cases/{case_id}/hospital-ranking` | ranked list for the case — **read-only, never selects** |
| `POST` | `/cases/{case_id}/select-hospital` | **Path A** — family taps a `hospital_id` from the list |
| `POST` | `/cases/{case_id}/confirm-hospital` | **Path B** — helper taps to confirm the #1 ranked hospital |

Selection is stored on the case: `selected_hospital_id`, `selected_by`,
`selected_via` (`family_choice` / `helper_confirm`), `selection_timestamp`.
A ranked list is never a selection — one of the two POSTs must be called.

### Full flow — ranked list, then select (Path A) and confirm (Path B)

```bash
# --- Path A: family picks ---
A=$(curl -s -X POST http://localhost:8000/cases/sos -H 'content-type: application/json' \
  -d '{"family_phone_number":"9876543210","family_gps":{"latitude":28.61,"longitude":77.20}}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["case"]["case_id"])')

curl -s -X POST http://localhost:8000/cases/$A/assessment/checklist -H 'content-type: application/json' \
  -d '{"criticality_level":"Serious","symptom_checklist":["chest_pain"],"confirm":true}' >/dev/null

# (optional) record a scheme so scheme hospitals float up within their tier
curl -s -X PUT http://localhost:8000/cases/$A/scheme -H 'content-type: application/json' \
  -d '{"government_scheme":"ayushman_bharat"}' >/dev/null

curl -s http://localhost:8000/cases/$A/hospital-ranking          # ranked list + excluded_hospital_ids + explanation

curl -s -X POST http://localhost:8000/cases/$A/select-hospital -H 'content-type: application/json' \
  -d '{"hospital_id":"HOSP-004","family_user_id":"FAM-1"}'        # 201, selected_via=family_choice

# --- Path B: helper confirms #1 ---
B=$(curl -s -X POST http://localhost:8000/cases -H 'content-type: application/json' \
  -d '{"next_of_kin_phone_number":"9123456780","patient":{"approx_age":60,"gender":"male"},"helper_id":"HLP-001","helper_gps":{"latitude":12.97,"longitude":77.59}}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])')

curl -s -X POST http://localhost:8000/cases/$B/assessment/checklist -H 'content-type: application/json' \
  -d '{"criticality_level":"Critical","symptom_checklist":["chest_pain","breathing_difficulty"],"confirm":true}' >/dev/null

curl -s http://localhost:8000/cases/$B/hospital-ranking
curl -s -X POST http://localhost:8000/cases/$B/confirm-hospital -H 'content-type: application/json' \
  -d '{"helper_id":"HLP-001","confirm_top_ranked":true}'          # 201, picks rank #1, selected_via=helper_confirm
```

Rejections: `409` for ranking/selection before symptoms are logged, using the
wrong path's endpoint, or a second selection; `400` for selecting a hospital not
in the case's ranked list; `422` for an unknown scheme or `confirm_top_ranked:false`.

## Phase 4 — FR-3 Bed Lock

The instant a hospital is selected/confirmed (Phase 3), one bed is **atomically
held** for that case. Bed type is derived from criticality: `Critical` → `ICU`,
otherwise `general`. Availability is derived, never stored twice:

```
available <type> beds  =  hospital.live_<type>_count  −  COUNT(active locks of that type)
```

The lock is a single guarded statement in
[app/services/bed_lock.py](backend/app/services/bed_lock.py) —
`INSERT ... SELECT ... WHERE capacity > active_locks`. The database evaluates the
capacity check and inserts as one indivisible operation and SQLite serialises
writers, so two simultaneous requests can never both take the same last bed; the
loser inserts zero rows, gets a `409`, and a `conflict_logs` row is written
(`case_id_a`, `case_id_b`, `hospital_id`, `bed_type`, `detected_at`) — never
silently swallowed.

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/hospitals/dashboard` | per-hospital live available beds + which case holds each lock |
| `GET`  | `/cases/{case_id}/bed-lock` | the case's active lock |
| `POST` | `/cases/{case_id}/bed-lock/release` | free the bed (cancel/reassign) + clear the case's selection |
| `GET`  | `/bed-locks/conflicts` | every recorded bed-lock collision |

A hospital with no free bed of the type a case needs is excluded from that
case's ranking (`excluded_no_capacity_ids`) and can't be selected.

### Full flow — select, confirm lock, watch the count, release, race

```bash
# 1. case + symptoms + selection (Phase 1-3) -> a bed lock is placed automatically
C=$(curl -s -X POST http://localhost:8000/cases -H 'content-type: application/json' \
  -d '{"next_of_kin_phone_number":"9123456780","patient":{"approx_age":50,"gender":"male"},"helper_id":"ATT-3","helper_gps":{"latitude":12.97,"longitude":77.59}}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])')
curl -s -X POST http://localhost:8000/cases/$C/assessment/checklist -H 'content-type: application/json' \
  -d '{"criticality_level":"Serious","symptom_checklist":["chest_pain"],"confirm":true}' >/dev/null

curl -s http://localhost:8000/hospitals/dashboard          # note available_general_beds for the top hospital
curl -s -X POST http://localhost:8000/cases/$C/confirm-hospital -H 'content-type: application/json' \
  -d '{"helper_id":"ATT-3","confirm_top_ranked":true}'   # 201, response includes "bed_lock"

curl -s http://localhost:8000/cases/$C/bed-lock            # the active lock
curl -s http://localhost:8000/hospitals/dashboard          # that hospital's available count is now 1 lower

# 2. release -> count goes back up, selection cleared
curl -s -X POST http://localhost:8000/cases/$C/bed-lock/release
curl -s http://localhost:8000/hospitals/dashboard          # count restored

# 3. concurrency (bash): two cases race the same last bed
pytest tests/test_fr3_concurrency.py -q                    # threaded proof: 1 wins, 1 conflicts, 1 conflict_log row
curl -s http://localhost:8000/bed-locks/conflicts          # the captured collision(s)
```

## Phase 5 — FR-4 Route/Traffic/Waypoint + FR-5 Blood Check

Both run **automatically the moment a hospital is selected + bed-locked** (Phase
3/4). They attach to the existing case/hospital rows — the hospital seed was
extended with `latitude`/`longitude` and `blood_stock_by_group`; the case row
gained `ambulance_level` (default `BLS`).

### FR-4 — Route, Traffic, Waypoint

- **Route + ETA** come from `get_route()` in
  [app/services/maps.py](backend/app/services/maps.py) — a genuine
  `httpx` call to `https://maps.googleapis.com/maps/api/directions/json` when
  `GOOGLE_MAPS_API_KEY` is set, otherwise a clearly-labelled `route_source:"stub"`
  (never a hand-rolled routing calc). ETA is always stored as a **range**
  (`eta_min_minutes` / `eta_max_minutes`), never a single ticking number.
- **Traffic alert** — one `traffic_alerts` row per case, Path A and Path B alike,
  with `traffic_alert_recipients` (mock: "Local Traffic Control", …) and
  `traffic_alert_sent_at`.
- **Waypoint suggestion** — if the symptoms are ALS-risk (fixed rule:
  `chest_pain`+`breathing_difficulty`, or `unconsciousness`, or `seizure`, or
  `visible_bleeding`+`trauma`) **and** `ambulance_level == BLS`, the nearest
  PHC/CHC with oxygen+doctor to the trip midpoint is **suggested**. Never applied
  — the helper must `POST /cases/{id}/waypoint-suggestion/accept`.

| Method | Path | Purpose |
|---|---|---|
| `PUT`  | `/cases/{id}/ambulance-level` | set BLS/ALS (default BLS) |
| `GET`  | `/cases/{id}/route` | route + ETA range + `route_source` |
| `GET`  | `/cases/{id}/traffic-alert` | the auto-created alert |
| `GET`  | `/cases/{id}/waypoint-suggestion` | the suggested stop (404 if none) |
| `POST` | `/cases/{id}/waypoint-suggestion/accept` · `/decline` | helper decision |

### FR-5 — Blood Check (conditional)

- Runs **only** when `visible_bleeding` or `trauma` is in the symptom checklist —
  never unconditionally.
- Checks the destination hospital's `blood_stock_by_group` first (universal donor
  `O-`, ≥ 2 units, since the patient's group isn't captured yet).
- If short/unconfirmed → a `pending` `blood_bank_holds` row at a **linked** blood
  bank (seeded: BB-01/02/03), which the coordinator confirms or rejects.

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/blood-banks` · `/blood-banks/{id}/holds` | banks + coordinator dashboard |
| `GET`  | `/cases/{id}/blood-check` | the check result (404 if not triggered) |
| `GET`  | `/cases/{id}/blood-bank-hold` | the hold for this case (404 if none) |
| `POST` | `/blood-bank-holds/{hold_id}/confirm` · `/reject` | coordinator decision |

### Full flow

```bash
mkcase() {  # $1 = symptoms JSON, $2 = criticality -> prints case_id
  cid=$(curl -s -X POST http://localhost:8000/cases -H 'content-type: application/json' \
    -d '{"next_of_kin_phone_number":"9123456780","patient":{"approx_age":45,"gender":"male"},"helper_id":"HLP-001","helper_gps":{"latitude":12.97,"longitude":77.59}}' \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])')
  curl -s -X POST http://localhost:8000/cases/$cid/assessment/checklist -H 'content-type: application/json' \
    -d "{\"criticality_level\":\"$2\",\"symptom_checklist\":$1,\"confirm\":true}" >/dev/null
  curl -s -X POST http://localhost:8000/cases/$cid/confirm-hospital -H 'content-type: application/json' \
    -d '{"helper_id":"HLP-001","confirm_top_ranked":true}' >/dev/null
  echo $cid
}

# A) chest pain + breathing difficulty on a (default) BLS ambulance -> waypoint suggestion
WP=$(mkcase '["chest_pain","breathing_difficulty"]' Critical)
curl -s http://localhost:8000/cases/$WP/route              # route_source:"stub", eta_min/max range
curl -s http://localhost:8000/cases/$WP/traffic-alert      # auto-created
curl -s http://localhost:8000/cases/$WP/waypoint-suggestion            # status:"suggested"
curl -s -X POST http://localhost:8000/cases/$WP/waypoint-suggestion/accept \
  -H 'content-type: application/json' -d '{"helper_id":"HLP-001"}'     # status:"accepted"

# B) visible bleeding -> blood check; HOSP-001 (ranked #1) has O-:1 -> blood bank hold
BL=$(mkcase '["visible_bleeding","trauma"]' Serious)
curl -s http://localhost:8000/cases/$BL/blood-check        # outcome:"blood_bank_hold_requested"
curl -s http://localhost:8000/cases/$BL/blood-bank-hold    # pending at BB-01
curl -s http://localhost:8000/blood-banks/BB-01/holds      # coordinator dashboard
HOLD=$(curl -s http://localhost:8000/cases/$BL/blood-bank-hold | python3 -c 'import sys,json;print(json.load(sys.stdin)["blood_bank_hold_id"])')
curl -s -X POST http://localhost:8000/blood-bank-holds/$HOLD/confirm \
  -H 'content-type: application/json' -d '{"coordinator_id":"COORD-1"}'   # hold_status:"confirmed"

# C) neither symptom -> route + traffic alert only, both extras skipped
N=$(mkcase '["high_fever"]' Serious)
curl -s -o /dev/null -w 'waypoint %{http_code}\n'  http://localhost:8000/cases/$N/waypoint-suggestion  # 404
curl -s -o /dev/null -w 'blood    %{http_code}\n'  http://localhost:8000/cases/$N/blood-check           # 404
```

To use a real Google Maps key: `export GOOGLE_MAPS_API_KEY=...` (or put it in
`backend/.env`) and re-run — `route_source` becomes `"google_maps"` with a real
polyline and traffic-aware ETA range.

## Phase 6 — FR-6 Hospital Pre-Arrival Preparation

Runs **automatically the moment a hospital is selected + bed-locked** (Phase 3/4).
Reads the case's `symptom_checklist` (FR-1); creates `prep_actions` rows the
hospital receptionist works through on their dashboard.

- **3 baseline actions for every bed-locked case**, all `status:"pending"`:
  `prepare_bed`, `notify_general_duty_staff`, `check_standard_equipment`.
- **Symptom-based actions layered on top** from ONE editable config table —
  `BASELINE_PREP_ACTIONS` + `SYMPTOM_TO_PREP_ACTIONS` in
  [app/config.py](backend/app/config.py) (no inference logic anywhere):
  `chest_pain → cardiology_standby`, `visible_bleeding`/`trauma →
  blood_bank_alert + surgical_standby`, `breathing_difficulty →
  oxygen_ventilator_check`. Same rules for every hospital.
- **Hard rule — no silent auto-firing:** a `prep_action` only ever reaches
  `status:"confirmed"` through `POST /prep-actions/{id}/confirm` (the explicit
  receptionist tap). `test_only_the_confirm_service_assigns_confirmed_status`
  scans the whole `app/` tree to enforce this.

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/cases/{case_id}/prep-actions` | dashboard read — `{pending: [...], confirmed: [...]}` |
| `POST` | `/prep-actions/{prep_action_id}/confirm` | receptionist confirms one (`pending → confirmed`, records `confirmed_by`/`confirmed_at`) |

### Full chain — create → symptoms (chest pain) → select+lock → prep actions → confirm one

```bash
C=$(curl -s -X POST http://localhost:8000/cases -H 'content-type: application/json' \
  -d '{"next_of_kin_phone_number":"9123456780","patient":{"approx_age":55,"gender":"male"},"helper_id":"HLP-001","helper_gps":{"latitude":12.97,"longitude":77.59}}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])')
curl -s -X POST http://localhost:8000/cases/$C/assessment/checklist -H 'content-type: application/json' \
  -d '{"criticality_level":"Serious","symptom_checklist":["chest_pain"],"confirm":true}' >/dev/null
curl -s -X POST http://localhost:8000/cases/$C/confirm-hospital -H 'content-type: application/json' \
  -d '{"helper_id":"HLP-001","confirm_top_ranked":true}' >/dev/null

curl -s http://localhost:8000/cases/$C/prep-actions
#  -> pending: prepare_bed, notify_general_duty_staff, check_standard_equipment, cardiology_standby   (confirmed: [])

PID=$(curl -s http://localhost:8000/cases/$C/prep-actions \
  | python3 -c 'import sys,json;print([a["prep_action_id"] for a in json.load(sys.stdin)["pending"] if a["action_key"]=="prepare_bed"][0])')
curl -s -X POST http://localhost:8000/prep-actions/$PID/confirm -H 'content-type: application/json' \
  -d '{"receptionist_id":"RECEP-1"}'                        # status:"confirmed", confirmed_by:"RECEP-1"

curl -s http://localhost:8000/cases/$C/prep-actions
#  -> confirmed: [prepare_bed]   pending: the other 3, untouched
```

A case logged without `chest_pain` (e.g. `["high_fever"]`) gets only the 3
baseline actions — no `cardiology_standby`.

## Phase 7 — FR-7 QR Handoff + FR-8 Discharge Feedback

### FR-7 — QR Handoff at Arrival

- `POST /cases/{id}/qr-handoff` (helper app, on arrival) mints a
  `qr_handoff_tokens` row: a random `secrets.token_urlsafe` string with
  `expires_at` (`QR_TOKEN_TTL_MINUTES`, default 15). The `qr_payload` the app
  encodes is **only** `{"case_id","token"}` — no patient data. Regenerating
  invalidates the previous unused token.
- `POST /qr-handoff/scan` `{case_id, token, scanned_by}` — validates the token is
  for that case, not expired, not used. On success it returns the full bundle:
  `transit_timeline` (derived in [app/services/timeline.py](backend/app/services/timeline.py)
  purely from timestamps already stored across FR-0…FR-6), `logged_symptoms`, and
  `admission_ready_data` (patient identity, `known_allergies`,
  `current_medications`, `blood_group`, next-of-kin, `scheme_status`).
- An expired / reused / wrong-case token → `403` with a fixed generic message —
  **no case data in the error**.
- A valid scan sets `case.status = "ADMITTED"` (+ `admitted_at`/`admitted_by`) —
  the "confirmed admission" event later phases key off.
- `PATCH /cases/{id}/clinical-info` — the helper records
  `known_allergies` / `current_medications` / `blood_group` / `patient_name`
  during transit (all optional).

### FR-8 — Discharge Feedback

- `POST /cases/{id}/trigger-discharge` — manual stand-in for the "days later"
  scheduler. Requires the case to be `ADMITTED`; sets `status = "DISCHARGED"` and
  creates a `feedback_invites` row (token + link + mock SMS to the family/NOK
  number).
- `POST /cases/{id}/feedback` `{token, wait_time_tag, staff_behavior_tag,
  cleanliness_tag, billing_tag (1–5), ready_as_shown_tag (yes/no/somewhat)}` —
  **structured tags only**, `extra="forbid"` blocks any freeform field.
- **One submission per case, at the database level**: `case_feedback.case_id` has
  a real `UNIQUE` constraint; a second submit is caught as an `IntegrityError` →
  `409` (the row is never overwritten). Stored with `hospital_id` denormalised for
  the future reliability-score feature.

### Full loop test

```bash
C=$(curl -s -X POST http://localhost:8000/cases -H 'content-type: application/json' \
  -d '{"next_of_kin_phone_number":"9123456780","patient":{"name":"Meera K","approx_age":58,"gender":"female"},"helper_id":"HLP-001","helper_gps":{"latitude":12.97,"longitude":77.59}}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])')
curl -s -X POST http://localhost:8000/cases/$C/assessment/checklist -H 'content-type: application/json' \
  -d '{"criticality_level":"Serious","symptom_checklist":["chest_pain"],"confirm":true}' >/dev/null
curl -s -X PATCH http://localhost:8000/cases/$C/clinical-info -H 'content-type: application/json' \
  -d '{"known_allergies":"sulfa","current_medications":"metformin","blood_group":"B+"}' >/dev/null
curl -s -X POST http://localhost:8000/cases/$C/confirm-hospital -H 'content-type: application/json' \
  -d '{"helper_id":"HLP-001","confirm_top_ranked":true}' >/dev/null

# FR-7: QR + scan
TOK=$(curl -s -X POST http://localhost:8000/cases/$C/qr-handoff | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s -X POST http://localhost:8000/qr-handoff/scan -H 'content-type: application/json' \
  -d "{\"case_id\":\"$C\",\"token\":\"$TOK\",\"scanned_by\":\"NURSE-7\"}"       # -> full admission bundle, status ADMITTED
curl -s -o /dev/null -w 'reuse: %{http_code}\n' -X POST http://localhost:8000/qr-handoff/scan \
  -H 'content-type: application/json' -d "{\"case_id\":\"$C\",\"token\":\"$TOK\",\"scanned_by\":\"NURSE-8\"}"   # 403

# FR-8: discharge + feedback once
FTOK=$(curl -s -X POST http://localhost:8000/cases/$C/trigger-discharge \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["link"].rsplit("/",1)[-1])')
curl -s -X POST http://localhost:8000/cases/$C/feedback -H 'content-type: application/json' \
  -d "{\"token\":\"$FTOK\",\"wait_time_tag\":4,\"staff_behavior_tag\":5,\"cleanliness_tag\":3,\"billing_tag\":4,\"ready_as_shown_tag\":\"yes\"}"   # 201
curl -s -o /dev/null -w 'second feedback: %{http_code}\n' -X POST http://localhost:8000/cases/$C/feedback \
  -H 'content-type: application/json' \
  -d "{\"token\":\"$FTOK\",\"wait_time_tag\":1,\"staff_behavior_tag\":1,\"cleanliness_tag\":1,\"billing_tag\":1,\"ready_as_shown_tag\":\"no\"}"   # 409, original row untouched
```

## Phase 8 — FR-9 Family SMS Tracking Link (Path B only)

The instant a **Path B** case is created ([app/services/cases.py](backend/app/services/cases.py)),
`create_for_path_b_case` mints a `case_tracking_tokens` row — a
`secrets.token_urlsafe(32)` string (**never** the `case_id`) with
`token_created_at` and a placeholder far-future `token_expires_at` — and fires the
mock SMS. Path A cases never get one.

- **One messaging system:** [app/services/sms.py](backend/app/services/sms.py)
  `send_sms(db, phone, message, category=..., case_id=...)` logs to the console
  and an `sms_messages` row. FR-8 discharge feedback now routes through it too. A
  real gateway swaps in here without callers changing.
- **On discharge** ([app/services/feedback.py](backend/app/services/feedback.py)),
  `token_expires_at` is recomputed to `discharged_at +
  TRACKING_TOKEN_EXPIRY_HOURS_AFTER_CLOSE` (36h — inside the FRP's 24–48h window).

### `GET /track/{token}` — strictly read-only, token-scoped

Looks the case up **by token only**. Returns exactly this whitelist and nothing
else — no `case_id`, patient data, phone numbers, symptoms, GPS, or other cases:

```
{ status, stage,                       # stage: en_route | arrived | discharged
  hospital: { name, distance_km, rating, cost_tier, why_chosen },
  eta: { min_minutes, max_minutes },   # the FR-4 range, never a single number
  bed_lock_status,                     # confirmed | not_yet
  prep_status: { total, confirmed, updates: [{item, status}] },
  qr_handoff_status }                  # confirmed | not_yet
```

- Unknown / made-up token → `404 {"detail":"not found"}` (no hint other tokens exist).
- Past `token_expires_at` → `410 {"status":"expired","message":"This link has expired"}` — **no case data**.
- `POST`/`PUT`/`PATCH`/`DELETE` on `/track/{token}` → `405`. There is no other endpoint or field reachable via the token.

### Test the flow

```bash
# 1. Path B case -> token + SMS created immediately
B=$(curl -s -X POST http://localhost:8000/cases -H 'content-type: application/json' \
  -d '{"next_of_kin_phone_number":"9123409999","patient":{"name":"Devi","approx_age":52,"gender":"female"},"helper_id":"HLP-001","helper_gps":{"latitude":12.97,"longitude":77.59}}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])')

sqlite3 dev.db "select token from case_tracking_tokens where case_id='$B'"      # the random token (not $B)
sqlite3 dev.db "select category,to_phone,message from sms_messages where case_id='$B'"   # the 'sent' SMS
TOK=$(sqlite3 dev.db "select token from case_tracking_tokens where case_id='$B'")

# 2. progress the case, then watch live status
curl -s -X POST http://localhost:8000/cases/$B/assessment/checklist -H 'content-type: application/json' \
  -d '{"criticality_level":"Serious","symptom_checklist":["chest_pain"],"confirm":true}' >/dev/null
curl -s -X POST http://localhost:8000/cases/$B/confirm-hospital -H 'content-type: application/json' \
  -d '{"helper_id":"HLP-001","confirm_top_ranked":true}' >/dev/null
curl -s http://localhost:8000/track/$TOK          # hospital + why, eta range, bed_lock_status=confirmed, prep_status, ...

# 3. read-only + bad token
curl -s -o /dev/null -w 'POST /track: %{http_code}\n' -X POST http://localhost:8000/track/$TOK   # 405
curl -s -o /dev/null -w 'bad token:  %{http_code}\n' http://localhost:8000/track/made-up-token   # 404

# 4. close the case -> expiry recomputed to 24-48h after discharge
T7=$(curl -s -X POST http://localhost:8000/cases/$B/qr-handoff | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s -X POST http://localhost:8000/qr-handoff/scan -H 'content-type: application/json' \
  -d "{\"case_id\":\"$B\",\"token\":\"$T7\",\"scanned_by\":\"NURSE\"}" >/dev/null
curl -s -X POST http://localhost:8000/cases/$B/trigger-discharge >/dev/null
sqlite3 dev.db "select discharged_at, (select token_expires_at from case_tracking_tokens where case_id='$B') from cases where case_id='$B'"
# expiry - discharged_at is between 24h and 48h
```

## Phase 9 — FR-11 Privacy/DPDP + FR-12 Abuse Prevention (security layer)

### Auth (FR-11)

Every endpoint now needs a bearer token except: `/health`, `/`, `/auth/login`,
`/otp/*`, `POST /cases/sos` (OTP-gated instead), `GET /track/{token}` and
`POST /cases/{id}/feedback` (both token-gated). Staff log in with an **account id
+ password**; the password is checked against a **PBKDF2-HMAC-SHA256** hash
(`users.password_hash`) in constant time — plain-text passwords are never stored
(NFR 7.1). Seeded demo accounts use the password `"<user_id>.sih2026"`.

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"user_id":"recep-hosp-001","password":"recep-hosp-001.sih2026"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/auth/me
```

Wrong password, missing password, and unknown account all return the same generic
`401` (no user enumeration; the verify runs against a dummy hash when the account
is missing so timing doesn't leak either). Hashing lives in
`app/services/security.py` (`hash_password` / `verify_password` / `needs_rehash`,
480 000 PBKDF2 iterations); migration `0020` adds the column and backfills the
seed accounts. `family` accounts authenticate by phone OTP, not a password.

Seeded roles: `admin`, `control-room`, `HLP-001`/`HLP-002` (helper),
`recep-hosp-001/004/007` (hospital_receptionist), `coord-bb-01/02`
(blood_bank_coordinator). `family` accounts are created automatically on OTP verify.

### Forgot password (FR-11)

Mirrors the FR-12 OTP shape exactly — two steps, both required:

```bash
B=http://localhost:8000
FP=$(curl -s -XPOST $B/auth/forgot-password -H 'content-type: application/json' -d '{"user_id":"HLP-001"}')
# {"reset_token_id": "...", "dev_code": "123456", ...}  — dev_code only when ENV=development,
# same convention as OTP. A registered phone also gets the code over the shared SMS seam.
curl -s -XPOST $B/auth/reset-password -H 'content-type: application/json' -d "{
  \"reset_token_id\": \"$(echo "$FP" | python3 -c 'import sys,json;print(json.load(sys.stdin)["reset_token_id"])')\",
  \"code\": \"$(echo "$FP" | python3 -c 'import sys,json;print(json.load(sys.stdin)["dev_code"])')\",
  \"new_password\": \"a-new-8-char-password\"
}"
# -> a fresh access_token, already signed in with the new password
```

`app/services/password_reset.py` + migration `0022` (`password_reset_tokens`
table, one-time use, short-lived). Unknown account → `404` (staff account ids are
internal usernames, not secrets — see the code comment for the trade-off vs. the
no-enumeration stance on `/auth/login`). The GoldenLine sign-in page
(`client/index.html`) drives this flow end to end with the code shown on-screen.

### Role scoping (FR-11)

`app/middleware.py` enforces scoping on **every** `/cases/{id}*` route in one
place (`app/services/access.py::can_see_case`):

| role | sees |
|---|---|
| `family` | only cases where `family_user_id` is theirs |
| `helper` | only cases they are the helper on |
| `hospital_receptionist` | only cases routed to **their** hospital; `/hospitals`, `/hospitals/dashboard` filtered to their row |
| `blood_bank_coordinator` | only holds/inventory at **their** bank |
| `control_room`, `admin` | everything |

`/bed-locks/conflicts` is control-room/admin only. **`GET /cases`** returns a
compact list filtered through the same `can_see_case` rule (admin/control-room →
all; helper → their own; receptionist → cases routed to their hospital; etc.) —
there is no unscoped "all cases" query. A wrong-scope request gets `403`, never data.

### HTTPS (FR-11)

Off for local dev (HTTP). Set `FORCE_HTTPS=true` (see `.env.example`) and the
`SecurityMiddleware` rejects any non-`https` request (checking
`X-Forwarded-Proto`) with `426`. Production must terminate TLS at a proxy.

### Data deletion (FR-11)

```bash
curl -s -X POST http://localhost:8000/cases/$CASE_ID/deletion-request -H "Authorization: Bearer $OWNER"   # 201 pending (case must be discharged)
curl -s -X POST http://localhost:8000/deletion-requests/$ID/process    -H "Authorization: Bearer $ADMIN"  # scrubs patient_name/allergies/meds/phones + drops the tracking token
```

### OTP on Path A (FR-12)

```bash
RQ=$(curl -s -X POST http://localhost:8000/otp/request -H 'content-type: application/json' -d '{"phone_number":"9876543210"}')
#  -> {"otp_verification_id":"...", "dev_code":"481920", ...}   (dev_code only in ENV=development; prod reads the SMS)
OID=$(echo $RQ | python3 -c 'import sys,json;print(json.load(sys.stdin)["otp_verification_id"])')
CODE=$(echo $RQ | python3 -c 'import sys,json;print(json.load(sys.stdin)["dev_code"])')
VID=$(curl -s -X POST http://localhost:8000/otp/verify -H 'content-type: application/json' \
  -d "{\"otp_verification_id\":\"$OID\",\"code\":\"$CODE\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["otp_verification_id"])')
curl -s -X POST http://localhost:8000/cases/sos -H 'content-type: application/json' \
  -d "{\"family_phone_number\":\"9876543210\",\"family_gps\":{\"latitude\":28.61,\"longitude\":77.20},\"otp_verification_id\":\"$VID\"}"
```

`POST /cases/sos` without a **verified, unused** OTP for that phone → `422`/`401`.
Path B (`POST /cases`) needs an authenticated **helper** token (no per-case OTP).

### Duplicate auto-merge (FR-12)

A second Path A SOS within `DUPLICATE_MERGE_RADIUS_METERS` (300 m) **and**
`DUPLICATE_MERGE_WINDOW_MINUTES` (10 min) of an open one returns the **existing**
case (`merged_into_existing_case: true`) and writes a `duplicate_merge_logs` row —
no second case. Far-apart or old requests are not merged.

### Rate-limit flagging (FR-12)

`app/services/ratelimit.py` — an in-process sliding window per source. Above
`RATE_LIMIT_THRESHOLD` (5) requests in `RATE_LIMIT_WINDOW_SECONDS` (60) it writes a
`rate_limit_flags` row for review (`GET /rate-limit-flags`, admin/control-room).
**It never blocks** — every emergency request still returns `201`.

## Phase 10 — FR-13 Connectivity + FR-14 Multi-language + FR-15 Safe-Driving

Almost entirely client-side, in **[`client/helper-app/`](client/helper-app/)** —
a vanilla-JS helper app. The backend only adds `GET /languages` (public) so the
UI language list and the FR-1 voice-input list share one source of truth
(`app/config.py::SUPPORTED_LANGUAGES`).

### FR-13 — Connectivity Resilience

| file | what |
|---|---|
| [js/offline-queue.js](client/helper-app/js/offline-queue.js) | actions taken offline are saved in `localStorage` and **replayed automatically** on `window 'online'` / visibility / a slow poll — no user "retry" control anywhere |
| [js/api.js](client/helper-app/js/api.js) | `mutate()` queues instead of failing when offline (or on `Failed to fetch`); a **"Simulate offline"** toggle for testing |
| [js/location.js](client/helper-app/js/location.js) | live GPS → last-known fallback that returns `estimated:true` + an age label; the location chip renders **dashed/italic/amber** for estimated vs solid green for live — never identical |
| [js/sms-fallback.js](client/helper-app/js/sms-fallback.js) → `POST /sms/fallback` | critical updates go out via the Phase-8 SMS stub when data is down; if even that fails, they queue |
| [js/hospital-cache.js](client/helper-app/js/hospital-cache.js) + [data/offline-hospitals.json](client/helper-app/data/offline-hospitals.json) | a bundled 6-hospital snapshot, refreshed from `/hospitals` every 15 min — the Hospital screen falls back to it when live ranking can't be reached |

### FR-14 — Multi-language

- Every string is a key in [`js/i18n/{en,hi,ta,bn}.json`](client/helper-app/js/i18n/) — UI components carry `data-i18n="key"` / call `t('key')`, never literals. `test_no_hardcoded_english_sentences_in_screen_markup` + `test_every_data_i18n_key_in_the_ui_is_defined` guard this; `test_all_four_language_files_have_identical_keys` guards coverage.
- Settings → **Language** switches every screen at once (`onLanguageChange` re-renders + `document.documentElement.lang`).
- Settings → **Voice-input language** uses the same list (both come from `GET /languages`).

### FR-15 — Safe-Driving

- ETA is only ever rendered by **`formatEtaRange(min,max)`** in [js/eta.js](client/helper-app/js/eta.js) → `"ETA 12–16 minutes"`, always a range, even for a degenerate input. No countdown, no single ticking number.
- **No speed leaderboard / driver ranking** anywhere. [SAFE_DRIVING.md](client/helper-app/SAFE_DRIVING.md) + [scripts/check-safe-driving.sh](client/helper-app/scripts/check-safe-driving.sh) (run by `test_safe_driving_check_script_passes`) fail the build if one is added.
- The route is framed as the **fastest safe route** (`route.fastestSafe`). `acknowledgeDeviation()` returns `{ blocked:false, penalty:null }` and only recomputes the ETA range — the driver can go a different way anytime.

### How to test

```bash
# terminal 1 — backend
cd backend && source .venv/bin/activate && alembic upgrade head && uvicorn app.main:app --reload --port 8000
# terminal 2 — serve the client
cd client && python3 -m http.server 5180
# open http://localhost:5180/helper-app/index.html
```

1. **Language** — Settings → change Language to Tamil/Hindi/Bengali → the header,
   nav, and current screen text all change together. Change "Voice-input language"
   and note it offers the same list.
2. **Offline sync** — Settings → tick **"Simulate offline"** → go to "New case",
   tap "New case" → the status bar shows *"1 action(s) saved on this device,
   waiting to sync"* → untick "Simulate offline" → within a few seconds the bar
   returns to "Online" and the case exists on the backend
   (`sqlite3 backend/dev.db "select count(*) from cases"`).
3. **ETA range** — Route & ETA screen shows `ETA N–M minutes` (never one number);
   tap "I'm taking a different road" → it recalculates to a new range, no warning.
4. `bash client/helper-app/scripts/check-safe-driving.sh` → `safe-driving check: OK`.

## Phase 11 — FR-10 Control Room (Background Supervisor)

A backend-only **monitoring** service. It has **no chat interface** with families
or hospitals — it only watches the data Phases 1–10 already produce and raises
internal **flags** to a human contact. Migration `0018` adds `flags` +
`hospital_bed_reports`.

### The `flags` table

`flag_id, flag_type (anomaly|conflict|reconciliation), related_case_ids (JSON
list), related_hospital_id, details, status (open|escalated|resolved),
escalated_to, escalated_at, created_at, resolved_at, resolved_by,
resolution_note`. A `dedup_key` makes re-running the scan idempotent.

### The three checks — [`app/services/control_room.py`](backend/app/services/control_room.py)

| check | what it scans | flag raised when |
|---|---|---|
| **anomaly watching** | active in-transit cases (hospital selected, not yet admitted/discharged) | the case's ambulance/helper GPS `gps_timestamp` is older than `CONTROL_ROOM_LOCATION_STALL_MINUTES` (10), or never reported past that window; or no activity of any kind for `CONTROL_ROOM_CASE_QUIET_MINUTES` (15) |
| **conflict resolution** | Phase-4 `conflict_logs` rows | any collision that doesn't yet have a `conflict` flag — the raw log is *promoted* to a proper flag, so it never lives only in the log |
| **data reconciliation** | `hospital_bed_reports` vs active `bed_locks` | a hospital's self-reported in-use bed count disagrees with the platform's active-lock count for that hospital |

There is no real scheduler yet: **`POST /control-room/scan`** runs all three now
(a cron/APScheduler job would call `run_all_checks()` on an interval).

### Escalation is mandatory; only a human resolves

* `create_flag()` **always** sets `status='escalated'` and `escalated_to`
  (the hardcoded `CONTROL_ROOM_ESCALATION_CONTACT` — the team, for the prototype).
  No code path creates a flag `open` or `resolved`.
* The **only** assignment of `status='resolved'` in the whole codebase is
  `control_room.resolve_flag()`, reached solely via
  **`POST /control-room/flags/{id}/resolve`** (requires a human actor;
  `resolved_by` = the caller). `test_only_control_room_resolve_service_assigns_resolved_status`
  regex-scans `app/` to enforce this.

### Endpoints (all `control_room` / `admin` only, except the bed report)

| method + path | purpose |
|---|---|
| `POST /control-room/scan` | run the 3 checks now → `{anomaly_flag_ids, conflict_flag_ids, reconciliation_flag_ids, total}` |
| `GET /control-room/flags` | the human's review dashboard — open/escalated flags, newest first (`?include_resolved=true`, `?flag_type=`) |
| `GET /control-room/flags/{id}` | one flag |
| `POST /control-room/flags/{id}/resolve` | **the only** path to `resolved` (`409` if already resolved, `404` if unknown) |
| `PUT /hospitals/{id}/reported-bed-usage` | a hospital receptionist (own hospital) / control-room posts its live in-use bed counts — the input reconciliation observes (FR-16 will automate this) |

### How to test all three flag types + the resolve guarantee

```bash
cd backend && source .venv/bin/activate && rm -f dev.db && alembic upgrade head
uvicorn app.main:app --port 8000  # terminal 1
```

```bash
# terminal 2
B=http://localhost:8000
CR=$(curl -s -XPOST $B/auth/login -H 'content-type: application/json' -d '{"user_id":"control-room","password":"control-room.sih2026"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
h=(-H "Authorization: Bearer $CR" -H 'content-type: application/json')

# a Path-B case, assessed + hospital confirmed (gives an active bed lock)
CID=$(curl -s "${h[@]}" -XPOST $B/cases -d '{"next_of_kin_phone_number":"9123456780","patient":{"approx_age":50,"gender":"male"},"helper_id":"HLP-001","helper_gps":{"latitude":12.97,"longitude":77.59}}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])')
curl -s "${h[@]}" -XPOST $B/cases/$CID/assessment/checklist -d '{"criticality_level":"Serious","symptom_checklist":["chest_pain"],"confirm":true}' >/dev/null
HID=$(curl -s "${h[@]}" -XPOST $B/cases/$CID/confirm-hospital -d '{"helper_id":"HLP-001","confirm_top_ranked":true}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["selected_hospital_id"])')

# 1) ANOMALY — stall the ambulance location 25 min into the past
sqlite3 dev.db "update cases set gps_timestamp = datetime('now','-25 minutes') where case_id='$CID'"

# 2) CONFLICT — reuse Phase-4's collision: a 1-bed hospital + a raw conflict_log row
sqlite3 dev.db "insert into hospitals (hospital_id,name,specialties,live_bed_count,live_icu_count,distance_km,eta_minutes,rating,cost_tier,accepted_schemes,blood_stock_by_group,hospital_sync_tier) values('HOSP-DEMO','Demo One Bed','[\"emergency\"]',1,0,1.0,5,4.0,'Government-Low','[]','{}','manual_counter')"
sqlite3 dev.db "insert into conflict_logs values(lower(hex(randomblob(16))),'CASE-LOSER','$CID','HOSP-DEMO','general',datetime('now'))"

# 3) RECONCILIATION — hospital reports 0 beds in use, platform holds 1 lock
curl -s "${h[@]}" -XPUT $B/hospitals/$HID/reported-bed-usage -d '{"reported_general_in_use":0,"reported_icu_in_use":0}'

# run the supervisor
curl -s "${h[@]}" -XPOST $B/control-room/scan | python3 -m json.tool
#   -> anomaly_flag_ids:[1], conflict_flag_ids:[1], reconciliation_flag_ids:[1]

curl -s "${h[@]}" $B/control-room/flags | python3 -m json.tool
#   -> every flag: "status":"escalated", "escalated_to":"SIH Control Room Team <...>"

# the ONLY way to 'resolved' — the explicit human endpoint
FID=$(curl -s "${h[@]}" $B/control-room/flags | python3 -c 'import sys,json;print(json.load(sys.stdin)[0]["flag_id"])')
curl -s "${h[@]}" -XPOST $B/control-room/flags/$FID/resolve -d '{"resolution_note":"called the driver, ambulance fine"}' | python3 -m json.tool
#   -> "status":"resolved", "resolved_by":"control-room", "resolved_at":"..."
curl -s "${h[@]}" -XPOST $B/control-room/flags/$FID/resolve -d '{}' -o /dev/null -w '%{http_code}\n'   # 409 — already resolved
```

Re-running `POST /control-room/scan` never duplicates a still-open flag and never
flips one to `resolved`. `tests/test_fr10_control_room.py` (12 tests) proves each
acceptance criterion; the cross-phase [`integration_test.sh`](#) covers it live.

## Phase 12 — FR-16 Hospital Data Sync (final phase)

Every hospital is on one **sync tier** (`hospital_sync_tier`), most→least
automated. Whichever tier a hospital uses, the bed counts land in the **same**
structure FR-2 ranking reads — `Hospital.bed_count_by_type == {"general":
live_bed_count, "ICU": live_icu_count}` — via the single writer
[`hospital_sync.apply_bed_counts`](backend/app/services/hospital_sync.py). There
is no per-tier ranking path. Migration `0019` adds the columns + `hospital_sync_events`.

| tier | trigger | how it gets counts |
|---|---|---|
| `hms_api` | `POST /hospitals/{id}/sync/hms` | `_fetch_hms_counts(id)` — **stub** (mock feed); a real HMS client drops in behind that seam |
| `google_sheets` | `POST /hospitals/{id}/sync/sheet` `{sheet_url?}` | `_fetch_sheet_counts(url)` — **stub** (reads `?general=&icu=` off the URL); a real Sheets read drops in behind that seam |
| `manual_counter` | `POST /hospitals/{id}/beds/adjust` `{bed_type, delta:±1}` | the receptionist's one-tap counter |

Each write stamps `last_synced_at` (every tier) and appends a
`hospital_sync_events` audit row. `GET /hospitals/{id}/sync-status` shows tier +
last sync + `bed_count_by_type` + recent events. `PUT /hospitals/{id}/sync-tier`
(admin) configures the tier. Calling the wrong tier's endpoint → `409`.

**RBAC:** receptionist → their own hospital only (`require_hospital_scope`);
blood-bank coordinator / family → `403`; admin & control-room → any.

### (4) Auto-decrement on confirmed admission — tied to the QR handoff only

Wired inside [`handoff.scan()`](backend/app/services/handoff.py), in the branch
that first sets a case `ADMITTED`. `hospital_sync.record_admission_decrement()`:

- decrements the admitting hospital's live count for the **bed type that was
  actually locked** (from the active `BedLock` row),
- writes a `hospital_sync_events` row with `source='qr_handoff_admission'`,
  `related_case_id`, `related_handoff_token_id` and the scanning nurse as `actor`
  — **traceable to that exact handoff**, never silent,
- **releases the now-fulfilled bed lock** so availability
  (`live_count − active_locks`) doesn't drop twice — a reserved bed simply
  becomes an occupied one.

It is never inferred from case status alone. The **counterpart** —
`record_discharge_increment()` — runs only from `feedback.trigger_discharge()`
(FR-8): it credits the bed back (`source='discharge_bed_released'`, tied to the
case, idempotent), so the two count changes are symmetric and both audited. The
hospital's own sync tier stays authoritative and corrects either on its next sync.

### Tier 1 & 2 are real integrations with a labelled fallback

Same degrade-to-stub pattern as the FR-4 Google Maps seam:

- **HMS API** — when `HMS_API_BASE_URL` is set, `_fetch_hms_counts()` does a real
  `GET {base}/hospitals/{id}/beds` (optional `HMS_API_TOKEN` bearer); otherwise a
  labelled mock feed. The sync event's `note` says which path ran.
- **Google Sheets** — a real `docs.google.com/spreadsheets/d/<id>` URL is fetched
  via the public CSV export and parsed as `label,count` rows; any other URL is a
  demo URL carrying `?general=&icu=`.

### How to test all three tiers + the QR-handoff decrement

```bash
cd backend && source .venv/bin/activate && rm -f dev.db && alembic upgrade head
uvicorn app.main:app --port 8000   # terminal 1
```

```bash
# terminal 2
B=http://localhost:8000
A=$(curl -s -XPOST $B/auth/login -H 'content-type: application/json' -d '{"user_id":"admin","password":"admin.sih2026"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
h=(-H "Authorization: Bearer $A" -H 'content-type: application/json')

# tier 3 — manual one-tap counter (HOSP-007 is manual_counter)
curl -s "${h[@]}" -XPOST $B/hospitals/HOSP-007/beds/adjust -d '{"bed_type":"general","delta":1}' | python3 -m json.tool
# tier 1 — HMS API (HOSP-001); no HMS_API_BASE_URL -> labelled mock feed
curl -s "${h[@]}" -XPOST $B/hospitals/HOSP-001/sync/hms | python3 -m json.tool
# tier 2 — Google Sheets (HOSP-002); a demo URL carries ?general=&icu=
curl -s "${h[@]}" -XPOST $B/hospitals/HOSP-002/sync/sheet -d '{"sheet_url":"https://sheets.example/hosp2?general=4&icu=1"}' | python3 -m json.tool

# all three now show in ONE ranking query, same bed_count_by_type structure
CID=$(curl -s "${h[@]}" -XPOST $B/cases -d '{"next_of_kin_phone_number":"9123456780","patient":{"approx_age":40,"gender":"male"},"helper_id":"HLP-001","helper_gps":{"latitude":12.97,"longitude":77.59}}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])')
curl -s "${h[@]}" -XPOST $B/cases/$CID/assessment/checklist -d '{"criticality_level":"Serious","symptom_checklist":["high_fever"],"confirm":true}' >/dev/null
curl -s "${h[@]}" $B/cases/$CID/hospital-ranking | python3 -c 'import sys,json;[print(r["hospital_id"], r["live_bed_count"]) for r in json.load(sys.stdin)["ranked"]]'

# QR-handoff decrement: progress a case to a bed lock, then scan
HC=$(curl -s "${h[@]}" -XPOST $B/cases -d '{"next_of_kin_phone_number":"9123456780","patient":{"approx_age":50,"gender":"male"},"helper_id":"HLP-001","helper_gps":{"latitude":12.97,"longitude":77.59}}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])')
curl -s "${h[@]}" -XPOST $B/cases/$HC/assessment/checklist -d '{"criticality_level":"Serious","symptom_checklist":["chest_pain"],"confirm":true}' >/dev/null
HID=$(curl -s "${h[@]}" -XPOST $B/cases/$HC/confirm-hospital -d '{"helper_id":"HLP-001","confirm_top_ranked":true}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["selected_hospital_id"])')
sqlite3 dev.db "select hospital_id, live_bed_count from hospitals where hospital_id='$HID'"   # before
TOK=$(curl -s "${h[@]}" -XPOST $B/cases/$HC/qr-handoff | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s "${h[@]}" -XPOST $B/qr-handoff/scan -d "{\"case_id\":\"$HC\",\"token\":\"$TOK\",\"scanned_by\":\"NURSE-1\"}" >/dev/null
sqlite3 dev.db "select hospital_id, live_bed_count from hospitals where hospital_id='$HID'"   # -1
curl -s "${h[@]}" $B/hospitals/$HID/sync-status | python3 -c 'import sys,json;e=json.load(sys.stdin)["recent_events"][0];print(e["source"], e["related_case_id"], e["related_handoff_token_id"], e["actor"])'
#   -> qr_handoff_admission <case_id> <token_id> NURSE-1
```

`tests/test_fr16_hospital_sync.py` proves both acceptance criteria (plus the real
HMS/Sheets fetch paths and the discharge credit-back); the cross-phase
`integration_test.sh` runs full Path A **and** Path B pipelines end-to-end
(SOS/helper → … → QR handoff → bed-count decrement → discharge → bed returned →
feedback) — 176 checks, 0 failures.

## Phase 13 — FR-17 Bed/Room Categories

The first phase of a post-FR-16 expansion into a fuller hospital-wide
dashboard (patient census, staff roster/attendance, inventory, HMS import —
see the project plan for the full FR-17..FR-22 roadmap). This phase adds
hospital-defined room/bed **categories beyond general+ICU** (private,
semi-private, ward, isolation, ...).

**Deliberately additive**, not a replacement: `Hospital.live_bed_count` /
`live_icu_count` remain the sole source of truth FR-2 ranking and FR-3 bed-lock
read from (`bed_count_by_type`). The new `bed_categories` table
(migration `0029`) never touches those columns, and the emergency pipeline
never routes an ambulance into one of these categories — they're for the
hospital's own front-desk/census use only.

- `GET /hospitals/{id}/bed-categories` / `PUT .../bed-categories/{code}` —
  hospital-scoped (receptionist → own hospital only, via
  `require_hospital_scope`; admin/control_room → any).
- `GET /hospitals/{id}/bed-categories/snapshot` — merges the existing
  general/ICU totals with the new categories in one response.
- `GET /bed-categories` — admin/control_room unscoped view across every
  hospital (same pattern as `/blood-bank-holds`).
- Client: the existing hospital "Bed capacity" screen gained a **Room
  categories** panel — inline-editable list + an add-category form, styled
  entirely from the existing `theme.css` tokens.

`tests/test_fr17_bed_categories.py` covers CRUD, cross-hospital 403s, the
snapshot merge, and the admin-only unscoped list. 223 backend tests passing
(up from 216); `integration_test.sh` unaffected (31/31 still passing).

## Phase 14 — FR-18 Patient Census + Manual Admit/Discharge/Bed-Assignment

The core piece of the post-FR-16 expansion: a **hospital-wide patient census**
covering walk-ins and scheduled admissions, not just cases that arrive through
the emergency pipeline — plus the write-path staff need to admit/discharge
them (`patients` + `bed_assignments`, migration `0030`).

**The hard problem this phase solves:** a walk-in occupying a general/ICU bed
has to reduce what FR-2 ranking and FR-3 bed-lock see as available, or the
census isn't really a single source of truth. The fix routes walk-in
admit/discharge through the exact SAME `Hospital.live_bed_count` /
`live_icu_count` columns those already read — `hospital_sync.py` gained
`record_walkin_admission_decrement()` / `record_walkin_discharge_increment()`,
audited through the same `hospital_sync_events` mechanism as every other bed-
count change. **Zero changes were needed in `hospital_ranking.py` or
`bed_lock.py`** — both already read those columns fresh at call time.

The atomic guard is the interesting part. A naive `WHERE live_bed_count > 0`
check would let a walk-in claim a bed a pending ambulance dispatch has already
*reserved* — `bed_lock.acquire_lock()` reserves a slot against the total
capacity **without decrementing it** (the decrement only happens later, at QR-
handoff admission), so `live_bed_count` alone doesn't reflect reservations.
The real guard checks `live_bed_count > active bed_locks of that type`:

```sql
UPDATE hospitals SET live_bed_count = live_bed_count - 1
WHERE hospital_id = :hid AND live_bed_count > (
    SELECT COUNT(*) FROM bed_locks
    WHERE hospital_id = :hid AND bed_type = :bed_type AND lock_status = 'active'
)
```

One indivisible `UPDATE`, same technique as `acquire_lock`'s guarded `INSERT`
— SQLite serialises the two on its write lock, so a walk-in admit and an
ambulance's bed-lock acquire can never both claim the same last physical bed.
`tests/test_fr18_patient_census.py` proves this with a real threaded race
(one general bed, a walk-in admit and a `bed_lock.acquire_lock()` firing
simultaneously — exactly one wins, the invariant holds either way).

Every QR-handoff-admitted case also gets a **visibility-only** census entry
(`patient_type='emergency_case'`) — hooked into `handoff.scan()` and
`feedback.trigger_discharge()`, right next to the existing
`record_admission_decrement`/`record_discharge_increment` calls. These hooks
never decrement/increment a second time; they only make the case's patient
show up in the same hospital-wide list walk-ins appear in, so the census
genuinely covers everyone.

- `POST/GET /hospitals/{id}/patients`, `GET /patients/{id}`,
  `POST /patients/{id}/admit` / `/discharge` — hospital-scoped
  (`require_hospital_scope`); `GET /patients` — admin/control_room unscoped.
- Admitting into an FR-17 bed category (private/ward/etc.) never touches
  `live_bed_count`/`live_icu_count` — purely local bookkeeping, same boundary
  as Phase 13.
- Client: a new **Patient census** screen (hospital + admin nav) — add a
  patient, filter by status, admit into a bed category, discharge.

15 new backend tests (238 total, up from 223); `integration_test.sh` unaffected
(31/31 still passing).

## Phase 15 — FR-19 Doctor/Staff Roster + On-Duty Status

A hospital-managed doctor/staff roster (`hospital_staff`, migration `0031`) —
who's on staff, their category (doctor/nurse/technician/support/admin_staff),
optional specialty/phone, and their on-duty status (on_duty/off_duty/on_leave).

**Design decision, explicitly not the obvious approach:** staff are a
lightweight new table, **not** new `User` rows with a new `Role`. Nothing in
this phase needs individual doctor/nurse login — the hospital_receptionist (or
admin) manages the roster on their behalf, same as a blood-bank coordinator
manages bank stock on behalf of the bank rather than individual donors.
Adding a `Role` value would have meant repeating the transitional
CHECK-constraint migration dance from the "attender"→"helper" rename (Phase
9's follow-up work) for zero functional benefit here, plus seeding a password
for every doctor/nurse. The design stays reversible: an optional nullable
`user_id` FK could be added later if a future phase needs staff self-service,
without reworking anything built now.

- `POST/GET /hospitals/{id}/staff`, `PATCH /staff/{id}/on-duty-status`,
  `DELETE /staff/{id}` (soft delete — flips `is_active=False` and clears
  on-duty status, never removes the row, so FR-20 attendance history keeps
  working for a departed staff member) — hospital-scoped via
  `require_hospital_scope`. `GET /staff` — admin/control_room unscoped view
  (same three-part pattern as `/patients`, `/bed-categories`).
- Client: a new **Staff roster** screen (hospital + admin nav) — add staff,
  set on-duty status inline, remove (soft delete).

7 new backend tests (245 total, up from 238); `integration_test.sh` unaffected
(31/31 still passing).

## Phase 16 — FR-20 Staff Attendance / Clock-in-out

A time-stamped clock-in/clock-out log (`staff_attendance`, migration `0032`),
deliberately **separate** from FR-19's `on_duty_status` flag per the
requirement — a status field and a history log are different features, not
the same thing wearing two names.

Clock-in/out keeps the two in sync explicitly: `staff_attendance.clock_in()` /
`clock_out()` call `hospital_staff.set_on_duty_status()` directly — a
service-to-service call, not a DB trigger — matching the project's existing
"explicit, audited, never inferred" philosophy (the same reasoning behind
FR-16's bed-count writes). One open (`clock_out_at IS NULL`) attendance row per
staff member at a time; clocking in while already clocked in, or clocking out
without an open row, both 409.

- `POST /staff/{id}/clock-in` (optional `shift_label`/`notes` — free text, no
  shift-scheduling engine), `POST /staff/{id}/clock-out`,
  `GET /staff/{id}/attendance`, `GET /hospitals/{id}/attendance` — all
  hospital-scoped via `require_hospital_scope`.
- Client: the **Staff roster** screen gained a clock-in/out button per row
  (swaps based on current `on_duty_status`) and an expandable attendance
  history panel.

6 new backend tests (251 total, up from 245); `integration_test.sh` unaffected
(31/31 still passing).

## Phase 17 — FR-21 Medical Resource/Inventory

Hospital-defined stock items (`hospital_inventory_items`, migration `0033`) —
medicine/consumable/equipment/ppe/other, each with a unit, quantity on hand,
and an optional low-stock threshold — plus a full movement audit trail
(`hospital_inventory_movements`, one row per quantity change: delta, reason,
actor, timestamp).

**Chose a real table over another `Hospital.*_by_group` JSON blob** (unlike
`blood_stock_by_group`), for the same reason FR-17's bed categories got their
own table: inventory items are an open-ended, hospital-defined list needing
per-item metadata and a history, not a fixed small set of keys.

- `POST/GET /hospitals/{id}/inventory`, `POST /inventory/{id}/adjust`
  (`{delta, reason}` — floors at 0, always writes an audited movement row even
  when the delta gets clamped), `GET /inventory/{id}/movements` — all
  hospital-scoped. `GET /inventory` — admin/control_room unscoped.
- `is_low_stock` is a derived property (`quantity_on_hand <= low_stock_threshold`
  when a threshold is set), not a stored flag — always consistent, never stale.
- Client: a new **Inventory** screen (hospital + admin nav) — add an item,
  one-tap +1/−1 adjust (mirrors the FR-16 bed counter's UX), a low-stock badge.

9 new backend tests (260 total, up from 251), including a regression guard for
a real Python-keyword gotcha: `MovementReason`'s `import` reason can't be a
Python identifier (`import` is reserved), so the enum member is named
`import_` — without `values_callable` (same fix as `assessment.py`'s
`CriticalityLevel`/`InputMethod`), SQLAlchemy would have stored the literal
string `'import_'` instead of `'import'`. `integration_test.sh` unaffected
(31/31 still passing).

## Phase 18 — FR-22 Rule-Based Fuzzy Import (final phase of the FR-17..22 expansion)

The last piece of the post-FR-16 HMS expansion: a **one-time bootstrap import**
from a CSV upload or a Google Sheet, into any of `patients` (FR-18),
`hospital_staff` (FR-19), `hospital_inventory_items` (FR-21), or
`bed_categories` (FR-17). FR-20 (staff attendance) is deliberately excluded —
a live clock-in/out feed isn't sensibly bulk-imported from a static export.

**"AI-assisted" means rule-based, not an LLM call** — a deliberate scoping
decision (confirmed with the user before building anything, alongside the
rest of the FR-17..22 roadmap): stdlib `difflib.get_close_matches` against a
per-target-field alias dictionary (`app/services/import_matching.py`, pure,
DB-free, unit-tested standalone). Deterministic, zero ML, zero new dependency
— matches the project's "explainable, no ML" design elsewhere (FR-2's
specialty lookup). Below a 0.6 similarity cutoff a column is left unmatched
and must be resolved by hand; nothing auto-commits past the threshold.

**Two-step preview/confirm flow, never auto-commits:**
1. `POST /hospitals/{id}/import/preview-file` (multipart CSV) or
   `/preview-sheet` (`{sheet_url, target_table}`, real Google Sheets only —
   fetched via the public CSV export, same technique as FR-16's Sheets tier)
   parses the file and returns a match report — matched field + confidence +
   sample values per column — backed by a new `import_sessions` staging row
   (migration `0034`) so the review step survives without re-uploading.
2. The review UI shows every column's suggested match with an editable
   override dropdown ("— ignore —" or any valid target field).
3. `POST /hospitals/{id}/import/{session_id}/commit` with the (possibly
   user-edited) mapping loops each row through the **target table's own
   create-service function** (`patients.create_patient`,
   `hospital_staff.create_staff`, `hospital_inventory.create_item`,
   `bed_categories.upsert_category`) — reusing FR-17/18/19/21's own
   validation rather than duplicating it. One bad row never aborts the whole
   import; it's recorded in `skipped: [{row, reason}]`.
4. `DELETE /hospitals/{id}/import/{session_id}` discards a session.

This is also the project's **first file-upload endpoint** — added
`python-multipart` to `requirements.txt` (the only new dependency this whole
expansion needed), and the client gained an `apiUpload()` sibling to the
existing JSON-only `api()` helper (`console.js`) to POST a `FormData` body.

- Client: a new **Import data** screen (hospital receptionist only — this is
  a self-service bootstrap tool, same reasoning as FR-16's sync-tier
  endpoints not being admin-gated) — target-table picker, file/sheet inputs,
  an editable mapping-review table, commit/discard, and a result summary.

16 new backend tests (276 total, up from 260), including a fixture-CSV match-
report check, a mocked Google-Sheets path (same `monkeypatch.setattr(hi.httpx,
"get", ...)` style as `test_fr16_hospital_sync.py`), and a regression guard
confirming `staff_attendance` is rejected as a target table.
`integration_test.sh` unaffected (31/31 still passing).

**A real client-side bug caught and fixed during live browser verification**
(not by the test suite, which only exercises the API): the mapping-review
`<select x-model>`'s `<option>`s are built by a sibling `x-for`, and Alpine
was setting the select's displayed value before those options existed yet —
every dropdown silently showed "ignore" even though the underlying model
(and the eventual commit) was correct. Same root cause as the `$nextTick`
gotcha hit building the map view: fixed with a `setTimeout(…, 0)` re-nudge
in `_seedMappingFromReport()`, not `$nextTick`. Verified by driving the real
`preview-file` → review table → `Confirm import` button through the actual
DOM (a synthetic `FormData`+`Blob` upload, since native file-picker dialogs
aren't scriptable in this sandbox) and confirming the imported row via a
direct API call.

## FR-17..22 expansion complete

All six phases of the post-FR-16 HMS-style expansion are built: room/bed
categories, a hospital-wide patient census with manual admit/discharge, a
doctor/staff roster, staff attendance, medical inventory, and this rule-based
import. 276 backend tests, `integration_test.sh` still 31/31.

## Live ambulance tracking + fleet monitoring (2026-09-05, post-expansion)

A standalone enhancement request, not part of the FR-17..22 roadmap: the
family had no way to see *which* ambulance was coming or where it actually
was, and the admin/control-room fleet map (built earlier alongside the FR
work) only distinguished idle vs dispatched — not the finer role ("picking up
the patient" vs "heading to the hospital") needed to actually monitor a city's
fleet. Both gaps closed with **zero new database state** — everything is
derived from data the pipeline already produces.

**Which ambulance, and where** — `GET /cases/{id}/ambulance` resolves the
case's assigned ambulance via `helper_id` (works for both creation paths;
Path B never sets `dispatched_ambulance_id`, only Path A does) and returns
`{vehicle_number, driver_name, latitude, longitude, gps_timestamp}` — the
same `case.gps_latitude/longitude` FR-2 ranking already reads, just resolved
to a human identity. **Deliberately no driver phone number** — family sees
who's coming, not a way to call them directly, avoiding a real prank-call/
harassment surface for a feature with no undo.

**A real pre-existing bug fixed along the way**: the family's case-detail map
used to fall back to the case's own GPS as the "self" pin when the family's
own device location wasn't available (it never is — only the helper's app
watches live geolocation) — silently mislabeling the *ambulance's* position
as "you." Fixed by splitting `self` (viewer's own device, helper-only) from a
new, correctly-labelled `ambulance-live` pin fed by the exact same data.

**Three-state fleet status, still zero new persistence** — `GET /ambulances`
now derives `idle` | `en_route_to_pickup` | `en_route_to_hospital` from
existing case state (no active case / no hospital selected yet / hospital
selected) instead of the old binary idle/dispatched — matching exactly what
a helper's own case-detail screen already shows, so there's no separate
"ambulance status" concept to ever drift out of sync. Idle ambulances are
shown parked at their fixed base coordinates (not live-tracked while off
dispatch — an explicit, honest scope decision, not a missing feature).

**Bonus: existing Control Room flags surfaced on the map** — FR-10's
anomaly detector already flags a case whose ambulance GPS has gone stale;
`GET /ambulances` now cross-references currently-escalated anomaly flags and
returns `has_stale_gps_flag`, drawn as a pulsing red ring on that ambulance's
fleet-map pin. Connects two systems that already existed but never talked to
each other — no new detection logic.

10 new backend tests (283 total, up from 276); `integration_test.sh`
unaffected (31/31 still passing). Verified live in the browser for both the
family case view (ambulance identity card + live pin) and the control-room
fleet map (3-state colour coding, pulsing dispatched pins) — hit and worked
around a genuine browser-cache staleness issue along the way (the sandbox's
`<script src>` tags can serve a stale cached copy across a plain navigation;
a fresh document URL, not just a reload, was needed to pick up the change).

## Build complete — FR-0 … FR-16

All 16 functional requirements are built, tested (175 backend tests), and covered
by the end-to-end integration script (176 checks). Post-build hardening pass:

- **Password login + forgot password** — staff authenticate with an account id
  **+ password**, verified against a PBKDF2-HMAC-SHA256 hash; plain-text
  passwords are never stored (NFR 7.1). A full forgot/reset-password flow
  mirrors the FR-12 OTP pattern (migration `0022`). (Was: passwordless dev login.)
- **HMS + Google Sheets sync tiers** are real HTTP integrations that degrade to a
  labelled mock when unconfigured — the same pattern as the FR-4 Maps seam.
  (Was: stub-only.)
- **Discharge returns the bed** — `trigger_discharge` credits the admitted bed
  back via an explicit, audited `hospital_sync_events` row, symmetric with the
  QR-handoff decrement. (Was: not re-incremented.)

## Rebrand — GoldenLine + a real front door

The product is branded **GoldenLine** end to end (backend `app_name`, `/health`,
`/docs`, error copy, config comments, both clients). The site now opens on a
proper **sign-in page** (`client/index.html`) instead of dropping straight into
the console:

- Animated dark/gold hero (hand-rolled SVG "golden line" motion + CSS particles,
  no animation library) with marketing copy on why the platform matters, plus a
  feature strip and a stat strip.
- **Staff Login** and **Family / OTP** tabs in one centered glass card; a row of
  one-click demo-account chips for judges.
- **Forgot password** end to end (see above).
- **4-language i18n** (English/Hindi/Tamil/Bengali) for the entire page —
  `client/i18n/*.json`, same key set across all four, checked into the repo.
- On success it hands the console a single token; the console has **no login UI
  of its own any more** — it calls `GET /auth/me`, auto-maps the account's role
  to its dashboard (helper/family/hospital/blood bank/control room/admin — no
  manual role switcher), and bounces back to the sign-in page if there's no
  valid session. Admin still sees every dashboard in one combined nav.
- The **console itself is now on the same dark/gold theme** as the sign-in page —
  both pull from one shared `client/theme.css` (tokens + card/button/badge/input
  classes), so it's one visual system, not two apps that happen to match. Small
  hand-drawn SVG nav icons, soft fade transitions between screens, `--gl-*`
  status badges. (`client/helper-app/` — the separate FR-13/14/15 reference
  client — is not yet re-themed; still its original light UI.)

Remaining prototype scope (per FRP Section 9 / 10): a production deployment swaps
the hand-rolled JWT/PBKDF2 for a vetted IdP, and `family` accounts still use phone
OTP rather than a password (by design).

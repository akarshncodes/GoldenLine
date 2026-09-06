
FUNCTIONAL REQUIREMENTS PLAN (FRP)
Real-Time Emergency Capacity Coordination Platform
Team Vector Zero · Smart India Hackathon 2026
Based on: Complete Project Understanding — v3 (Post-Revision)
Note: the built product is branded "GoldenLine" (see the main README) — this planning document is kept as originally written and uses the working title throughout.
Written for a beginner developer to build the project exactly as designed — nothing added, nothing skipped.

1. How to Use This Document
This is a Functional Requirements Plan (FRP). It tells you, feature by feature, exactly what the app must do, who uses each feature, what order things happen in, what rules your code must never break, and how you can check you built it correctly. It is written assuming you are building this for the first time and are not already deeply familiar with the project.
Read Sections 2–5 first to understand the big picture before writing any code. Then treat Section 6 (Functional Requirements) as your feature-by-feature build checklist — build and test one FR at a time, in roughly the order presented, since later features depend on earlier ones (for example, you cannot build Bed Lock, FR-3, before Hospital Ranking, FR-2, exists).
Every requirement below comes directly from the project's official planning document ("Complete Project Understanding — v3"). Nothing has been invented, and nothing from that document has been left out. Anywhere this FRP adds extra explanation for clarity, it is clearly marked as a "Note for the developer" box, so you always know what is an official requirement versus added guidance.
2. Project Summary (Plain English)
During a medical emergency in India, three things usually go wrong at once: families don't know which hospital actually has a free bed, ICU slot, specialist, or blood unit right now; ambulances sometimes drive to a hospital that then cannot accept the patient, wasting critical time; and hospitals get no warning before a patient arrives, so they scramble instead of preparing.
This platform is a real-time coordination layer that sits between the emergency moment and the hospital. It is NOT a hospital's internal system, NOT a replacement for 108/ambulance dispatch, and NOT a diagnostic tool. Its one job is to make sure the right hospital is picked, that hospital holds a bed for that exact patient, and the hospital is actively preparing before the ambulance arrives.
It is delivered as both a mobile app (for families and ambulance helpers, who need it in-the-moment on a phone) and a website (for hospital and blood bank staff, who manage ongoing data at a desk).
Note for the developer: Keep this one-paragraph mental model in your head throughout development: 'pick the right hospital, hold the bed, get the hospital ready before arrival.' Every single feature in Section 6 exists only to serve this.
3. Glossary — Terms You'll See Throughout This Document
	•	Case — one emergency event, from the moment SOS is triggered / an helper starts it, until the patient is discharged and feedback is collected.
	•	Path A — a case that starts because the family used the app and pressed SOS.
	•	Path B — a case that starts because an ambulance helper began it directly (patient arrived via 108 call, hospital referral, or a walk-up), without the family ever using the app.
	•	Helper — the on-scene ambulance staff member using the app during the case.
	•	Bed lock — a temporary, exclusive reservation of one specific bed/ICU slot at a hospital for one specific case.
	•	Control Room — an AI-run background monitoring process (not a chat interface) that watches for problems across all active cases and escalates them to a human.
	•	DPDP — India's Digital Personal Data Protection framework, which this project's privacy handling must respect.
	•	BLS / ALS — Basic Life Support / Advanced Life Support: two levels of ambulance equipment and capability.
	•	PHC / CHC — Primary Health Centre / Community Health Centre: smaller government facilities that can be used as stabilization waypoints.
	•	Cost tier — one of three hospital pricing categories: Government–Low, Private–Standard, Private–Premium.
	•	Reliability score — a single score per hospital, combining discharge feedback and whether reported beds were genuinely used, that feeds back into hospital ranking.
4. User Roles — Who Uses This App and What They See
Build your permissions/access-control system around these seven roles from day one. Each role must only see the screens and data listed here — this is both a usability requirement and a privacy requirement (see FR-11).
Role
Sees / Does
Family / helper (app path)
Triggers SOS, sees hospital recommendations, picks a hospital, sees live ETA, and (after discharge) the feedback prompt.
Ambulance helper
A minimal operational screen: symptom logging (voice or tap), hospital selection screen, route/waypoint suggestions, and QR generation at arrival. Can also start a case directly (Path B).
Family via SMS link (no-app path)
When the helper starts the case (Path B), the next-of-kin gets full visibility through a lightweight, no-login tracking link instead of the app.
Hospital receptionist
Manages ongoing bed/staff/equipment data, sees incoming case data, confirms AI-triggered prep actions, and scans the QR at arrival.
Blood bank coordinator
Manages blood inventory and gets contacted/booked when a case needs blood.
Control room
AI-run by default; a defined human escalation contact handles anomalies and conflicts it raises.
Government (long-term)
The eventual operator of the platform once it is handed over — not an active role during the prototype.

4.1 What the Control Room Actually Does (Important — Don't Skip)
Beginners often assume 'Control Room' means a chat dashboard where people talk to hospitals. It does not. Think of it as the platform's background supervisor — it never talks to the family or the hospital directly. It watches the pipeline underneath everything else, and has exactly three jobs, detailed fully in FR-10:
	•	Anomaly watching — e.g. an ambulance's location stops updating, or a case goes quiet mid-transit.
	•	Conflict resolution — e.g. two urgent cases both heading toward the same hospital's last ICU bed.
	•	Data reconciliation — e.g. checking whether a reported bed was actually used, or the hospital quietly gave it away.
Every flag it raises goes to a defined human escalation contact — during the prototype, that is the team itself. Nothing is ever silently auto-resolved.
5. The Core Pipeline — The Spine of the Whole System
Every single feature in this app exists to serve one step in this pipeline. Build and test it in this order:
	•	FR-0 — Case is created (Path A or Path B).
	•	FR-9 — (Path B only) Family gets SMS tracking link.
	•	FR-1 — On-scene assessment (criticality + symptoms logged).
	•	FR-2 — AI hospital ranking, and hospital is selected.
	•	FR-3 — Bed lock placed at the selected hospital.
	•	FR-4 — Route/traffic coordination and waypoint check.
	•	FR-5 — Blood check, if relevant.
	•	FR-6 — Hospital pre-arrival preparation suggestions.
	•	FR-7 — QR handoff at arrival.
	•	FR-8 — Discharge feedback, days later.
Running underneath all of the above, at all times: FR-10 (Control Room), FR-11 (Privacy/DPDP), FR-12 (Abuse prevention), FR-13 (Connectivity resilience), FR-14 (Multi-language), FR-15 (Safe-driving design), and FR-16 (Hospital data sync).
Note for the developer: Build FR-0 through FR-8 first, end-to-end, with fake/mock hospital data, before worrying about FR-10 through FR-16. Get one full case moving through the whole pipeline before polishing the cross-cutting systems.

6. Functional Requirements — Full Detail
Each requirement below follows the same structure: what it does, who's involved, what must be true before it can run, the exact step-by-step flow, the business rules your code must enforce, the data fields involved, and acceptance criteria you can literally test against.
FR-0 — Case Creation — Two Paths (Path A and Path B)
What this feature does: This is the very first step of the whole system: how a medical emergency case gets opened inside the platform. There are exactly two ways a case can start, and the app must support both.
Who is involved: Family member (Path A), Ambulance Helper (Path B and both paths afterwards).
Before this can happen (pre-conditions): The user has the app installed (family) or the helper is logged in as a verified, onboarded ambulance staff member.
Step-by-step flow:
	•	PATH A (Family-initiated): The family member opens the app and presses the SOS button.
	•	The app automatically captures the family's phone GPS location and sends it to the backend — no manual address typing.
	•	The backend finds and dispatches the nearest registered ambulance that has the app.
	•	The ambulance helper receives the case and takes over from this point (both paths now follow the exact same steps: FR-1 onward).
	•	PATH B (Helper-initiated): A patient reaches a registered ambulance through any other channel — a 108 emergency call, a hospital referral, or a walk-up at the ambulance.
	•	The helper opens the app on-site and starts the case directly (there is a clear 'Start New Case' button for this).
	•	The helper enters the patient's basic details (name if known, approximate age, gender) and MUST enter a next-of-kin contact phone number — this field cannot be left empty; the app should not let the helper proceed without it.
	•	From this point on, Path B follows the identical pipeline as Path A (FR-1 onward).
Business rules the code must enforce:
	•	GPS/location for the case must always come from the HELPER's device, in both Path A and Path B — never from the family's phone once the ambulance is involved. Only the very first SOS trigger in Path A uses the family's phone GPS to find an ambulance.
	•	There is NO 'self-transport using the family's own phone GPS' mode. If no registered ambulance with the app is physically present for a case, the platform does not engage with that case at all. Do not try to build a workaround for this — it is an intentional, documented limitation.
	•	The next-of-kin phone number field in Path B is mandatory. Use a simple 10-digit Indian mobile number validation (regex like /^[6-9]\d{9}$/) before allowing the helper to continue.
	•	A case record, once created, must store which path (A or B) created it — this decides later on whether the SMS tracking link (FR-9) needs to be sent.
Data fields involved:
	•	case_id (unique, generated by backend)
	•	creation_path (enum: 'A' or 'B')
	•	family_phone_number (Path A) OR next_of_kin_phone_number (Path B)
	•	patient_basic_details: name (optional/unknown allowed), approx_age, gender
	•	gps_coordinates + timestamp
	•	helper_id (the logged-in ambulance staff account)
Acceptance criteria (how you know it's built correctly):
	•	A family member can trigger SOS from the app and a case is created with their location attached.
	•	An helper can start a case from within their own app without the family app being involved.
	•	The system refuses to create a Path B case if the next-of-kin number field is empty or invalid.
	•	After creation, both paths reuse the exact same screens for symptom logging, ranking, etc. (no separate code path duplicated for A vs B beyond this step).
Note for the developer: Build ONE case data model with a 'creation_path' flag, not two separate case tables. Everything after this step reads from the same model regardless of how the case started — this keeps your code simple and avoids bugs from duplicated logic.
FR-9 — Family Access via SMS Link (Path B only)
What this feature does: When a case is started by the helper (Path B), the real family/next-of-kin is not inside the app. So the system sends them a text message with a link to a simple read-only web page where they can watch the case progress, without installing anything or logging in.
Who is involved: Backend notification service, next-of-kin (via their phone's SMS and browser).
Before this can happen (pre-conditions): A Path B case has just been created and a valid next-of-kin number was captured (FR-0).
Step-by-step flow:
	•	The instant a Path B case is created, the backend generates a unique, unguessable case token (a long random string, not the case's normal database ID).
	•	The backend sends a one-time SMS to the next-of-kin number containing a link like https://yourapp.com/track/<token>.
	•	The next-of-kin taps the link — no login, no OTP, no app install required. The token itself acts as the password for viewing this one case.
	•	The web page shows: which hospital the patient is headed to and why (distance, rating, cost tier), the live ETA, bed-lock confirmation once it happens, pre-arrival prep status updates as they occur, and QR-handoff confirmation once the patient arrives.
	•	Because the family is not present to make the hospital choice themselves in this path, the helper confirms the AI's top hospital recommendation on the family's behalf (see FR-2). The family simply sees the confirmed outcome on this page.
	•	The link automatically stops working (expires) a fixed window after the case is closed — between 24 and 48 hours later. This window is long enough to also cover the discharge-feedback step (FR-8) but does not leave the link open forever.
Business rules the code must enforce:
	•	The token must be long and random enough that it cannot be guessed (use something like a UUID v4 or a cryptographically random 32-character string). Do NOT use the sequential case_id as the token.
	•	This page must be strictly READ-ONLY. It must not expose any action buttons, editing, or any data belonging to other cases.
	•	The page must be scoped to exactly one case — the backend must check the token against the case it belongs to on every page load/refresh, and return nothing if the token is invalid or expired.
	•	After expiry, the same URL must show a simple 'This link has expired' message, not an error page or leaked data.
Data fields involved:
	•	case_token (unique, random, tied 1:1 to case_id)
	•	token_created_at, token_expires_at
	•	the same case status fields used on the hospital/helper side (hospital name, distance, rating, cost tier, ETA, bed_lock_status, prep_status, qr_handoff_status)
Acceptance criteria (how you know it's built correctly):
	•	Sending a real SMS with a working link to a test phone number when a Path B case is created.
	•	Opening the link shows live-updating status without asking for any login.
	•	Opening the link after the expiry window shows an expired message and no case data.
	•	Opening a made-up/incorrect token shows no data (not even an error revealing that other tokens exist).
Note for the developer: This reuses the same SMS gateway you are already building for OTP (FR-11) and discharge feedback (FR-8) — do not build a second messaging system. Treat it as a third type of message sent through the same service.
FR-1 — On-Scene Assessment (Symptom Logging)
What this feature does: Once a case exists, the ambulance helper records how serious the patient looks and what symptoms are visible — WITHOUT naming any medical diagnosis, because the helper is not a doctor.
Who is involved: Ambulance helper.
Before this can happen (pre-conditions): A case has been created (Path A or Path B).
Step-by-step flow:
	•	The helper opens the assessment screen and selects a criticality level: Critical, Serious, or Stable.
	•	The helper records observed symptoms using ONE of two input methods: (a) tapping through a checklist of common symptoms, or (b) holding one button and speaking naturally, e.g. 'Male, roughly 60, severe chest pain, breathing difficulty'.
	•	If voice was used, the app converts speech to text and automatically fills in the same checklist fields that option (a) would have filled — the two input methods lead to the exact same data structure.
	•	The helper is shown the auto-filled checklist and MUST review and explicitly confirm it before it is submitted. It never auto-submits from voice alone.
Business rules the code must enforce:
	•	Never allow entry of a named diagnosis anywhere in this screen (e.g. no free-text field labelled 'diagnosis'; only a fixed list of observable symptoms and the criticality level). This is a deliberate safety rule, not an oversight.
	•	Voice input must support English, Tamil, Hindi, and Bengali at launch. Design the speech-to-text integration so more languages can be added later without redesigning the screen (e.g. keep the target language as a simple config value, not hardcoded).
	•	The 'review and confirm' step is mandatory even for voice input — do not skip a confirmation screen to save time.
Data fields involved:
	•	criticality_level (enum: Critical / Serious / Stable)
	•	symptom_checklist (list of fixed symptom tags, e.g. chest_pain, breathing_difficulty, visible_bleeding, trauma, etc.)
	•	input_method (checklist or voice)
	•	raw_voice_transcript (store for audit, even after checklist is derived)
Acceptance criteria (how you know it's built correctly):
	•	An helper can complete a full symptom log using only taps, with no voice.
	•	An helper can speak a sentence and see the checklist pre-filled correctly, then must tap Confirm before it saves.
	•	There is no field or screen anywhere that lets a diagnosis name be typed in and passed downstream.
FR-2 — AI Hospital Ranking
What this feature does: Once symptoms are logged, the system produces a ranked list of nearby hospitals that can actually treat this patient — using simple, explainable rules, not a black-box probability model.
Who is involved: AI/Decision service (backend), family (Path A, makes final choice) or helper (Path B, confirms on family's behalf).
Before this can happen (pre-conditions): Symptoms and criticality have been logged (FR-1).
Step-by-step flow:
	•	STEP 1 — Specialty filter: the system runs a simple, direct rule check on the observed symptoms (e.g. 'chest pain' logged means the hospital must have cardiology capability) and removes any hospital that plainly cannot handle the case. This is a rule lookup against a small fixed table — never a machine-learning probability guess.
	•	STEP 2 — Ranking: the remaining hospitals are ranked by a combination of time, distance, and rating, and are grouped into three cost tiers: Government–Low, Private–Standard, Private–Premium. The system must NEVER invent or estimate rupee figures that were not provided by the hospital itself.
	•	STEP 3 — Government scheme boost: if the family or helper has indicated the patient is covered under Ayushman Bharat or a state health scheme, hospitals that accept that scheme are boosted higher within their own cost tier (a scheme hospital is not allowed to jump into a different cost tier just because of the boost).
	•	FINAL SELECTION — Path A: the ranked list is shown to the family inside the app, and the family taps to choose. The AI must never auto-select a hospital in this path.
	•	FINAL SELECTION — Path B: the helper reviews the AI's top-ranked hospital and taps to confirm it on the family's behalf (the family is not present). The family later sees this confirmed outcome over the SMS link (FR-9).
Business rules the code must enforce:
	•	There must be no condition-probability / disease-likelihood model anywhere in this ranking logic. It was deliberately removed. If you find yourself building a model that predicts 'likely diagnosis', stop — that belongs nowhere in this feature.
	•	The whole ranking logic must be explainable in one sentence to a non-technical judge: 'closest, cheapest-tier-appropriate, best-rated, capable hospital.' If your implementation cannot be described that simply, simplify it.
	•	The AI never makes the final choice by itself in Path A — a human (family) must tap to select.
	•	In Path B the helper's confirmation still counts as the required 'human confirms' step — it is not automatic either.
Data fields involved:
	•	hospital list with: specialties[], live_bed_count, live_icu_count, distance_km, eta_minutes, rating, cost_tier, accepted_schemes[]
	•	ranked_result (ordered list of hospital_ids with computed score)
	•	selected_hospital_id, selected_by (family_user_id or helper_id), selection_timestamp
Acceptance criteria (how you know it's built correctly):
	•	Given a fake hospital list and a symptom of 'chest pain', hospitals without cardiology are excluded from the ranked list.
	•	Sorting order changes correctly when you change distance/rating test data.
	•	A hospital marked as accepting Ayushman Bharat moves up within its own tier when the scheme flag is set, but never crosses into a different tier.
	•	In a Path A test case, the app waits for a tap before locking in a hospital. In a Path B test case, the helper's tap is what confirms it.
FR-3 — Bed Lock
What this feature does: The moment a hospital is chosen, the exact bed or ICU slot that hospital is offering must be temporarily and exclusively reserved so that no other case can be given the same bed while this case is still on the way.
Who is involved: Backend case management service, hospital receptionist (sees the lock on their dashboard).
Before this can happen (pre-conditions): A hospital has been selected (FR-2, final selection step).
Step-by-step flow:
	•	As soon as a hospital is confirmed/selected, the backend places a temporary hold on one specific bed/ICU slot at that hospital.
	•	While the hold is active, that same bed must not be shown as available to any other in-progress case's ranking or selection step.
	•	The hospital receptionist's dashboard shows this bed as 'locked' for this specific incoming case.
	•	The hold is released (bed becomes free again) if the case is cancelled, reassigned, or once the patient is actually admitted and the bed count is properly decremented (see FR-16, adoption/sync).
Business rules the code must enforce:
	•	A locked bed must be atomic — two cases must never be able to lock the same single bed at the same time. Use a database transaction/row lock or an equivalent safe mechanism when decrementing available beds.
	•	The Control Room (FR-10) is responsible for catching and resolving the rare situation where two urgent cases collide on the same hospital's last bed — your code should log this conflict rather than silently letting one case overwrite the other.
Data fields involved:
	•	bed_lock_id, hospital_id, case_id, bed_type (general/ICU), lock_status (active/released), locked_at, released_at
Acceptance criteria (how you know it's built correctly):
	•	Locking a bed for one case immediately reduces the hospital's shown available-bed count by one.
	•	A second, simultaneous case cannot also lock the same already-locked bed.
	•	Cancelling a case releases its lock and the bed count goes back up.
FR-4 — Route, Traffic Coordination and Waypoint Check
What this feature does: Once a hospital is picked, the app shows the ambulance the live route and estimated time, alerts nearby traffic police, and — if needed — suggests a stop at a stabilization point on the way.
Who is involved: Helper (sees route), Control Room (sends traffic alert), traffic police (receives alert — external to this app in the prototype).
Before this can happen (pre-conditions): A hospital has been selected and bed-locked (FR-2, FR-3).
Step-by-step flow:
	•	The app requests a live route and ETA from the Google Maps API. Do not build a custom routing engine — always call the external Maps API for this.
	•	The Control Room automatically sends an alert (route + ETA) to nearby traffic police. Because every case now involves a real registered ambulance in both Path A and Path B, this alert always applies — there is no case type that skips it.
	•	The system checks: does the logged symptom data suggest a real ALS-level (Advanced Life Support) risk, while only a BLS (Basic Life Support) ambulance is assigned to this case?
	•	If yes, the system looks for a registered fixed stabilization waypoint (a PHC or CHC with oxygen and a doctor) that is reasonably on the route, and SUGGESTS a stop there to the helper.
	•	The helper decides whether to actually stop — this suggestion is never automatic or forced.
Business rules the code must enforce:
	•	Routing/ETA must come from the Google Maps API — this is a hard rule, not a suggestion, to avoid the huge effort of building routing from scratch.
	•	The waypoint stop is always a suggestion the helper can accept or ignore — the system must never auto-reroute the ambulance without the helper's action.
Data fields involved:
	•	route_polyline, eta_minutes, eta_range (shown as a range, see FR-14 safe-driving design)
	•	ambulance_level (BLS/ALS)
	•	nearby_waypoints (PHC/CHC list with oxygen/doctor availability flags)
	•	traffic_alert_sent_at, traffic_alert_recipients
Acceptance criteria (how you know it's built correctly):
	•	A test case produces a route and ETA pulled from the real Google Maps API response, not a hardcoded value.
	•	A traffic alert record is created for every single case (Path A and Path B alike).
	•	When ambulance_level is BLS and symptoms indicate an ALS-risk case, a waypoint suggestion appears on the helper's screen and requires a tap to act on.
FR-5 — Blood Check
What this feature does: If the case profile suggests the patient may need blood, the system checks stock at the destination hospital and, if needed, places a hold at a nearby linked blood bank.
Who is involved: Backend case service, blood bank coordinator.
Before this can happen (pre-conditions): A hospital has been selected (FR-2).
Step-by-step flow:
	•	The system checks whether the logged symptoms/case profile suggest a blood requirement (e.g. visible bleeding/trauma flag from FR-1).
	•	If a requirement is suggested, the system checks the destination hospital's own recorded blood stock first.
	•	If the hospital's own stock is insufficient or not confirmed, the system places a hold request at a linked nearby blood bank.
	•	The blood bank coordinator sees this hold request on their dashboard and can confirm or reject it.
Business rules the code must enforce:
	•	This check should only run when relevant (based on symptom flags) — do not run it for every case unconditionally, to avoid noise for blood banks.
Data fields involved:
	•	blood_requirement_flag, blood_group (if known)
	•	hospital_blood_stock (by group), blood_bank_hold_id, hold_status
Acceptance criteria (how you know it's built correctly):
	•	A case with a 'visible bleeding' symptom flag triggers a blood stock check; a case without it does not.
	•	When hospital stock is insufficient, a hold request appears on a linked blood bank's dashboard.
FR-6 — Hospital Pre-Arrival Preparation
What this feature does: While the ambulance is on the way, the receiving hospital is given a generic preparation checklist plus a few simple, symptom-based safety alerts — using a small fixed lookup table, not AI reasoning.
Who is involved: Backend AI/decision service, hospital receptionist (must confirm every action).
Before this can happen (pre-conditions): A hospital has been selected and bed-locked (FR-2, FR-3).
Step-by-step flow:
	•	GENERIC BASELINE (runs for every single case, no exceptions): mark that a bed should be prepared, notify general duty staff, and flag standard equipment to be checked.
	•	SYMPTOM-BASED FLAGS (layered on top, using a small fixed keyword-to-department lookup table): if 'chest pain' was logged, ping cardiology to stand by. If 'visible bleeding/trauma' was logged, alert the blood bank plus surgical standby. If 'breathing difficulty' was logged, trigger a check on oxygen/ventilator availability.
	•	Every one of these prep actions (baseline and symptom-based) is shown to the hospital receptionist on their dashboard as a suggested action.
	•	The receptionist must tap to confirm each action — nothing fires or is marked as 'done' automatically without a human confirming it on the dashboard.
Business rules the code must enforce:
	•	This must be implemented as a small, fixed, hardcoded lookup table (symptom keyword → department/action), not a machine-learning or per-condition inference step. It should be trivially explainable in one sentence.
	•	As a flagged design decision, this table is hospital-wide (the same rules for every hospital) rather than per-hospital-configurable for now. Confirm with your team before building a more complex per-hospital version — it's a valid future extension, not a requirement for the first version.
	•	No prep action may be marked complete or notified-as-done without an explicit human tap on the hospital dashboard. There must be zero silent auto-firing actions.
Data fields involved:
	•	prep_action_id, case_id, action_type (baseline/symptom-based), suggested_department, status (pending/confirmed), confirmed_by, confirmed_at
	•	symptom_to_department_lookup (a simple table/config file, e.g. {chest_pain: 'cardiology', visible_bleeding: ['blood_bank','surgical'], breathing_difficulty: 'oxygen_check'})
Acceptance criteria (how you know it's built correctly):
	•	Every new case produces the three generic baseline actions automatically shown on the hospital dashboard (still pending confirmation).
	•	A case with 'chest pain' logged additionally shows a cardiology-standby suggestion; a case without it does not.
	•	No action's status ever becomes 'confirmed' in the database without a corresponding receptionist tap being recorded.
FR-7 — QR Handoff at Arrival
What this feature does: When the ambulance arrives, the helper's app shows a QR code that the hospital nurse scans to instantly load all the case information gathered during transit — instead of the helper re-explaining everything verbally.
Who is involved: Ambulance helper (generates QR), hospital nurse/receptionist (scans QR).
Before this can happen (pre-conditions): The case has reached FR-1 through FR-6 (symptoms logged, hospital chosen, prep suggested).
Step-by-step flow:
	•	On arrival, the helper's app generates a QR code for this specific case. This works identically in both Path A and Path B, because the helper always has the app in both paths.
	•	The nurse scans the QR code using the hospital's device/app.
	•	Scanning instantly pulls in: the full transit timeline, logged symptoms, timestamps, and admission-ready data captured during transit — patient identity (if known), known allergies, current medications, next-of-kin contact, and government scheme status.
Business rules the code must enforce:
	•	The QR code must encode a reference to the case (e.g. case_id + a short-lived verification token), not the raw patient data itself, so that scanning always pulls fresh data from the backend rather than stale data baked into the code.
	•	This data must only be retrievable via a valid scan tied to that specific case — it should not be publicly fetchable from the case_id alone.
Data fields involved:
	•	qr_code_payload (case reference + short-lived token)
	•	transit_timeline (list of timestamped events from case creation to arrival)
	•	admission_ready_data: patient_identity, known_allergies, current_medications, next_of_kin, scheme_status
Acceptance criteria (how you know it's built correctly):
	•	A generated QR code, when scanned in a test, correctly loads that exact case's data on the hospital side.
	•	An expired or reused QR/token does not return case data.
FR-8 — Discharge Feedback
What this feature does: A few days after the case closes, an SMS is sent asking the family/next-of-kin for simple structured feedback about the hospital experience — no free text, so there's nothing complicated to analyze.
Who is involved: Backend notification service, family (Path A) or next-of-kin (Path B).
Before this can happen (pre-conditions): The case has been marked closed/discharged.
Step-by-step flow:
	•	Some days after discharge, the backend sends an SMS to the verified contact number on file — the family's own number in Path A, or the next-of-kin number captured at case creation in Path B — with that specific case's ID pre-attached in the link.
	•	The family/next-of-kin taps the link and selects structured tags only: wait time, staff behaviour, cleanliness, billing, and 'was it ready as shown' — all as simple pre-set options (e.g. star ratings or yes/no/somewhat), never a free-text box.
	•	The submission is tied to that one case_id. Once submitted, the same case cannot submit feedback again — this blocks spam and duplicate submissions.
	•	The submitted tag counts feed into the hospital's overall reliability score (FR-15), the same score used for bed-reconciliation in the Control Room.
Business rules the code must enforce:
	•	No freeform text/NLP parsing anywhere in this feature — only fixed structured tags/options.
	•	Enforce one submission per case_id at the database level (e.g. a unique constraint on case_id in the feedback table), not just in the UI.
Data fields involved:
	•	feedback_id, case_id (unique constraint), wait_time_tag, staff_behavior_tag, cleanliness_tag, billing_tag, ready_as_shown_tag, submitted_at
Acceptance criteria (how you know it's built correctly):
	•	An SMS with a working feedback link is sent automatically some days after a case is marked discharged.
	•	Submitting feedback twice for the same case_id is rejected the second time.
	•	Submitted tags are visible in the hospital's reliability score calculation.
FR-10 — Control Room (Background Supervisor)
What this feature does: An AI-run background process that does NOT talk to the family or hospital directly. It watches the whole pipeline underneath everything else and raises flags to a human whenever something looks wrong — nothing is ever silently auto-resolved.
Who is involved: Control Room service (backend, largely automated), a defined human escalation contact (the team itself, during the prototype).
Before this can happen (pre-conditions): Cases are actively moving through the pipeline (FR-0 through FR-8).
Step-by-step flow:
	•	ANOMALY WATCHING: continuously check that active ambulances' locations are still updating and that in-progress cases are still sending status updates. If an ambulance's location stops updating, or a case goes quiet mid-transit, raise a flag.
	•	CONFLICT RESOLUTION: detect when two urgent cases are both about to be assigned to the same hospital's last available ICU bed (or similar clash) and raise a flag instead of letting the system silently pick one.
	•	DATA RECONCILIATION: periodically check whether a bed that was reported as used by a case was actually used, or whether the hospital's live counts disagree with what the platform expects (e.g. did the hospital quietly give the bed away outside the platform).
	•	Every flag raised by any of the three jobs above is sent to a defined human escalation contact. During the prototype/hackathon stage, this contact is the team itself.
Business rules the code must enforce:
	•	The Control Room must never silently auto-resolve a flagged anomaly or conflict — it always escalates to a human, even if it also takes a safe temporary action (like pausing a bed lock) while waiting for a human response.
	•	This is a background/monitoring service — it does not have its own chat interface with families or hospitals; it only produces internal alerts.
Data fields involved:
	•	flag_id, flag_type (anomaly/conflict/reconciliation), related_case_id(s), related_hospital_id, details, status (open/escalated/resolved), escalated_to, created_at, resolved_at
Acceptance criteria (how you know it's built correctly):
	•	Simulating a stalled ambulance location update produces an anomaly flag within a defined time window.
	•	Simulating two cases both targeting the same last ICU bed produces a conflict flag, and the bed lock logic (FR-3) does not just silently give it to whichever request arrived first without also logging the flag.
	•	A mismatch between a hospital's reported bed usage and the platform's expected usage produces a reconciliation flag.
FR-11 — Privacy and DPDP Compliance
What this feature does: The platform must collect only the minimum data it actually needs, protect it properly, and respect the patient/family's rights under India's Digital Personal Data Protection (DPDP) framework.
Who is involved: All services that touch personal data.
Before this can happen (pre-conditions): Applies across the entire system, at every step.
Step-by-step flow:
	•	Collect only the minimum data actually required for each step (purpose-limited collection) — do not add extra personal fields 'just in case'.
	•	Rely on DPDP's medical-emergency provision as the legal basis for processing data without going through a lengthy consent flow during an active emergency.
	•	Encrypt personal data both at rest (in the database) and in transit (over the network, i.e. HTTPS everywhere).
	•	Enforce role-based access — a hospital receptionist should only see cases relevant to their hospital, a blood bank coordinator only their own inventory and requests, etc.
	•	Support post-emergency deletion rights — build a way for a user to request their personal data be deleted once the emergency and any required retention window has passed.
	•	The Path B read-only SMS link (FR-9) is scoped under this same emergency-basis reasoning, and access is tied to a token rather than a full account — it must not expose more data than the token's case.
Business rules the code must enforce:
	•	Never store more personal fields than a feature actually needs.
	•	All API traffic must be HTTPS only — no plain HTTP endpoints for anything carrying personal or case data.
	•	Every database query that returns case data must be scoped by the requester's role and their linked hospital/organization ID — never a blanket 'return all cases' query reachable by a normal hospital or blood-bank account.
Data fields involved:
	•	access_control roles: family, helper, hospital_receptionist, blood_bank_coordinator, control_room, admin
	•	deletion_request_id, requested_by, case_id, requested_at, processed_at
Acceptance criteria (how you know it's built correctly):
	•	A hospital account cannot query or view another hospital's case or bed data through the API.
	•	All endpoints reject plain HTTP and only serve over HTTPS.
	•	A deletion request can be filed and is tracked to completion.
FR-12 — Abuse Prevention
What this feature does: Mechanisms to stop fake or duplicate requests, and to make sure every app-originated request is tied to a real, verified person.
Who is involved: Backend auth service, all app users.
Before this can happen (pre-conditions): Applies whenever a new case or request is created.
Step-by-step flow:
	•	For app-originated requests from the family (Path A), use OTP verification to tie every request to a real phone number.
	•	For Path B, the helper is already a verified, onboarded platform user (verified once during onboarding, not per case) — so no separate per-case OTP is required from the helper's side.
	•	If duplicate requests come in for the same location and time window (e.g. someone accidentally taps SOS twice, or two family members both trigger it for the same patient), auto-merge them into a single case instead of creating two.
	•	If a suspiciously high rate of requests comes from the same source, rate-limiting flags this for review — but it never blocks the request in the moment. A real emergency must never be silently blocked.
Business rules the code must enforce:
	•	Rate-limiting must flag, never hard-block, an in-the-moment emergency request.
	•	Duplicate-merge logic should compare both location proximity and a time window (e.g. same rough location within a few minutes) before merging — don't merge unrelated cases that happen to be nearby.
Data fields involved:
	•	otp_verification_id, phone_number, verified_at
	•	duplicate_merge_log (which case_ids were merged and why)
	•	rate_limit_flag_id, source, flagged_at, reviewed
Acceptance criteria (how you know it's built correctly):
	•	A Path A SOS request requires a successfully verified OTP before the case is created.
	•	Two SOS taps within a short time window and close location merge into one case, not two.
	•	A burst of requests from one source is flagged for review but every individual request still goes through.
FR-13 — Connectivity Resilience
What this feature does: The app must keep working reasonably well even with a poor or lost internet connection, since emergencies often happen in low-network areas.
Who is involved: Family app, helper app.
Before this can happen (pre-conditions): Applies whenever network conditions are poor.
Step-by-step flow:
	•	Use offline-first local caching: actions taken while offline are saved locally on the device and automatically synced once connection returns.
	•	If live location cannot be obtained, fall back to the last-known location, clearly labelled on-screen as an estimate (never presented as a live, accurate position).
	•	Provide an SMS fallback channel for critical updates when data connectivity is unavailable.
	•	Keep a pre-downloaded list of nearby hospitals on the helper's device so a basic hospital list is still available if live ranking (FR-2) cannot be reached.
Business rules the code must enforce:
	•	Any location shown to a user that is not from a fresh GPS reading must be visibly labelled as an estimate/last known — never shown identically to a live position.
	•	Locally cached actions must sync automatically without requiring the user to manually retry once the connection is back.
Data fields involved:
	•	local_cache_queue (pending actions to sync)
	•	last_known_location + last_known_location_timestamp
	•	offline_hospital_list (periodically refreshed snapshot)
Acceptance criteria (how you know it's built correctly):
	•	Turning off network on a test device, performing an action, then turning network back on results in the action syncing automatically.
	•	When live location fails, the UI shows a clearly labelled 'estimated location' instead of silently showing stale data as if it were live.
FR-14 — Multi-language Support
What this feature does: The interface and the voice-input feature must support multiple Indian languages, with room to add more later.
Who is involved: All app users.
Before this can happen (pre-conditions): None — applies from first app launch.
Step-by-step flow:
	•	The full app interface must be available in English, Hindi, Tamil, and Bengali.
	•	Voice input for symptom logging (FR-1) currently supports the same four languages.
	•	Build the language selection as a simple configuration/setting, not hardcoded text, so more languages can be added later without a redesign.
Business rules the code must enforce:
	•	Store all user-facing text in language resource files/keys (i18n pattern), never hardcoded strings inside the UI code, so translations can be added or edited without touching logic code.
Data fields involved:
	•	user_language_preference
	•	i18n resource files per supported language
Acceptance criteria (how you know it's built correctly):
	•	Switching the app's language setting changes all visible text, not just some screens.
	•	Voice input correctly transcribes in each of the four supported languages during testing.
FR-15 — Safe-Driving Design
What this feature does: The app's design for the ambulance driver/helper must never encourage risky driving.
Who is involved: Ambulance helper/driver.
Before this can happen (pre-conditions): Applies whenever route/ETA information is shown (FR-4).
Step-by-step flow:
	•	Show ETA as a range (e.g. '12–16 minutes'), never as a single ticking-down countdown number.
	•	Never show driver speed leaderboards, rankings, or any gamified speed comparison between drivers.
	•	The app suggests only the fastest SAFE route — never an aggressive/risky shortcut framed as 'fastest'.
	•	Driver judgment always overrides the app's suggestion — the driver can deviate from the suggested route at any time without the app blocking or penalizing that choice.
Business rules the code must enforce:
	•	Do not implement any feature that ranks, scores, or compares drivers by speed or time, now or later.
	•	ETA must always render as a range in the UI, never a single live-decrementing number.
Data fields involved:
	•	eta_range_min, eta_range_max
Acceptance criteria (how you know it's built correctly):
	•	A design/code review confirms no countdown timer or speed-leaderboard component exists anywhere in the helper app.
	•	The helper can deviate from the suggested route and the app continues to function normally (just recalculates ETA).
FR-16 — Hospital Data Sync & Adoption Strategy
What this feature does: How hospitals keep their bed/staff/equipment data up to date on the platform, and what makes hospitals want to actually use it.
Who is involved: Hospital receptionist, backend sync services.
Before this can happen (pre-conditions): A hospital has been onboarded onto the platform.
Step-by-step flow:
	•	Support tiered auto-sync options for hospitals, from most to least automated: (1) a real HMS (Hospital Management System) API integration, (2) a Google Sheets connector the hospital keeps updated, (3) a one-tap manual counter in the hospital's own dashboard, with (4) auto-decrement of the count whenever a bed lock (FR-3) is confirmed as an actual admission.
	•	Onboard hospitals with real incentives explained clearly in the dashboard/marketing material: a referral flow that brings them patients, fewer chaotic last-minute rejections, a free dashboard, a positive reputational signal, and a compliance angle for government hospitals.
Business rules the code must enforce:
	•	Whichever sync tier a hospital uses, the resulting bed-count data must land in the exact same internal data structure the ranking step (FR-2) reads from — don't build separate ranking logic per sync tier.
	•	Auto-decrement on confirmed admission must be tied to an explicit confirmation event (e.g. the QR handoff in FR-7 or an explicit receptionist action), never inferred silently.
Data fields involved:
	•	hospital_sync_tier (hms_api / google_sheets / manual_counter)
	•	bed_count_by_type, last_synced_at
Acceptance criteria (how you know it's built correctly):
	•	A hospital using the manual one-tap counter and a hospital using the (mocked, for prototype) HMS API integration both correctly feed the same ranking logic.
	•	Confirming an admission via QR handoff correctly decrements that hospital's live bed count.

7. Non-Functional Requirements
7.1 Security
	•	All traffic over HTTPS only (see FR-11).
	•	Role-based access control enforced on every API endpoint, not just hidden in the UI.
	•	Case tokens (FR-9) and QR tokens (FR-7) must be long, random, and time-limited.
	•	Passwords/credentials for staff accounts must be hashed, never stored in plain text.
7.2 Performance & Reliability
	•	Hospital ranking (FR-2) should return a result within a couple of seconds under normal conditions — this is a time-critical emergency tool.
	•	The system should degrade gracefully under poor connectivity rather than fail completely (see FR-13).
	•	Bed lock operations (FR-3) must be atomic to avoid double-booking under concurrent requests.
7.3 Usability
	•	The family/helper-facing screens must be usable under stress, in a real emergency — large tap targets, minimal required typing, voice input support.
	•	The hospital/blood bank dashboards can be denser and more form-like, since staff use them at a desk, not mid-emergency.
7.4 Availability
	•	This is a life-critical tool; downtime directly risks lives. Aim for high uptime and have the offline-first fallback (FR-13) as a safety net, not the primary mode.
7.5 Maintainability
	•	Keep the symptom-to-department lookup table (FR-6) and the specialty filter rules (FR-2) as simple, editable config/data — not buried inside logic code — since the team explicitly may want to make these per-hospital-configurable later.
8. Technical Architecture (Explained Simply)
The system has four layers. As a beginner, think of data as flowing top to bottom and back up again:
8.1 Clients (what people actually see and tap)
	•	Family App (Path A)
	•	Ambulance Helper App (used in both Path A and Path B)
	•	Hospital / Blood Bank Web dashboard
	•	Control Room Dashboard
	•	Read-only SMS Tracking Link page (Path B families, no login) — this is new in this version of the plan.
8.2 Backend API (the 'brain' that all clients talk to)
	•	Auth & OTP handling
	•	Case management — now must support both Path A and Path B entry points
	•	Bed/blood lock logic
	•	Onboarding forms (for hospitals, blood banks, ambulances)
	•	Notification dispatch (SMS/push)
	•	Case-token generator — specifically for the read-only tracking links (FR-9)
Clients talk to the Backend API over REST/HTTPS, plus a live-update channel (e.g. WebSockets or a polling mechanism) so that things like ETA, bed status, and prep status update in real time without the user refreshing the page.
8.3 Database
	•	Hospitals / beds
	•	Cases / helpers
	•	Reliability scores
	•	Feedback tags
8.4 AI / Decision Service
	•	Voice-to-symptom extraction (feeds FR-1)
	•	Specialty filter — rule-based, not probability-based (feeds FR-2)
	•	Ranking by time + distance + rating (feeds FR-2)
	•	Generic prep + keyword flags — a fixed lookup table (feeds FR-6)
	•	Reliability score calculation (feeds FR-8 / FR-2)
8.5 External Services
	•	Google Maps — route/ETA/traffic (FR-4)
	•	Speech-to-text — English/Tamil/Hindi/Bengali (FR-1, FR-14)
	•	SMS/OTP gateway — this single gateway also powers the tracking links (FR-9) and discharge feedback (FR-8), so build it once and reuse it for all three.
8.6 Data Lifecycle — Where Data Comes From and Goes
	•	Hospital / blood bank / ambulance data originates from onboarding forms, is kept current via tiered auto-sync (FR-16), and is retrieved LIVE by the ranking step on every new case — it should never be long-cached, since bed counts change minute to minute.
	•	Case data originates from the helper's app in both Path A and Path B (typed or voice-derived), is written once to the case record, and is then read by: the hospital dashboard (via QR scan, FR-7), the AI service (for ranking/prep, FR-2/FR-6), and the read-only tracking link (via case-token match, FR-9) — never via a full account login for that last one.
9. What This Project Deliberately Does NOT Include
These were considered and intentionally cut. Do not build any of them — if you're ever unsure whether to add a feature, check this list first.
Self-transport mode using the family's own phone GPS
Removed. Replaced entirely by Path B (helper-initiated case creation). The team's reasoning: a registered ambulance with the app is present in almost every real scenario (108 call, hospital referral, walk-up), so it's more reliable to take location from the helper's device than to build a separate, less-trustworthy family-GPS mode.
Condition-probability shortlist in hospital ranking
Removed from the ranking step entirely, to keep the ranking logic fully explainable and defensible (see FR-2). A much lighter, rule-based version of symptom-awareness still exists, but only inside the pre-arrival prep step (FR-6) — never in ranking.
Bay-specific routing, WhatsApp bystander bot, moving ambulance-to-ambulance intercept, family-facing live treatment/EMR view
All cut, unchanged from the prior planning round, for these reasons respectively: no reliable data source available, it would bypass the abuse-prevention design, it carries real-world liability risk, and it would duplicate the government's own EMR mandate.
10. Long-Term Positioning
This platform is explicitly non-profit and designed for eventual handover to a state health department, because a student team has no authority to mandate hospital participation — only a government body does. Keep this in mind: features like guaranteed traffic-signal access, mandatory hospital registration, and fully staffed 24/7 control rooms are believable as later, government-operated phases — do not try to fully build or promise these in the prototype.
11. Quick Build Checklist for the Developer
A condensed, practical order of operations for actually building this, start to finish:
	•	Set up the case data model with a creation_path field (Path A / Path B) — one model, not two.
	•	Build FR-0 (case creation, both paths) and FR-1 (symptom logging) with mock/test data.
	•	Build a small, fixed hospital test dataset, then build FR-2 (ranking) against it.
	•	Build FR-3 (bed lock) directly on top of FR-2's selected hospital.
	•	Build FR-4 (Google Maps route/ETA) and FR-5 (blood check) in parallel — both depend only on FR-2/FR-3.
	•	Build FR-6 (pre-arrival prep) using the fixed lookup table.
	•	Build FR-7 (QR handoff) and FR-8 (discharge feedback) to close the loop.
	•	Add FR-9 (SMS tracking link) once Path B case creation and the case status fields all exist.
	•	Layer in FR-11 (privacy/roles), FR-12 (abuse prevention), and FR-13 (offline resilience) across everything you've built so far.
	•	Add FR-14 (multi-language) and FR-15 (safe-driving UI rules) as you polish the helper app.
	•	Build FR-10 (Control Room) last, as a monitoring layer that watches the data your other features are already producing.
	•	Wire up FR-16 (hospital sync tiers) so hospital bed counts feed properly into FR-2's ranking data.
Note for the developer: If you get stuck on any single FR, re-read its 'Business rules' list first — most beginner mistakes in a project like this come from missing one of those explicit rules (e.g. forgetting that the AI must never auto-select a hospital in Path A), not from the overall logic being wrong.

Real-Time Emergency
Capacity Coordination Platform
Complete Project Understanding — v3 (Post-Revision) Team Vector Zero · SIH 2026
Note: the built product is branded "GoldenLine" (see the main README) — this planning document is kept as originally written and uses the working title throughout.
This is the complete, from-scratch picture of the project — problem, purpose, process, features, and technical
detail — updated with every change made in the last round of review. Sections marked with a colored tag show
exactly what's new, updated, or removed this round, so the whole team can see precisely what changed and
why.
■ NEW ■ UPDATED ■ REMOVED
1. The Problem, Precisely
During a medical emergency in India, three things go wrong independently: families don't know which hospital
has an actual open bed, ICU slot, specialist, or blood unit right now; ambulances sometimes drive to a hospital
that then can't accept the patient, losing critical time; and hospitals get no advance warning of what's coming,
so they scramble instead of preparing. All three happen because hospitals, ambulances, blood banks, and
traffic control operate as disconnected islands with no shared live data.
2. What the Platform Actually Is
A real-time coordination layer — not a hospital's internal system, not a replacement for 108/ambulance
dispatch, not a diagnostic tool. It sits between the emergency moment and the hospital, making sure the right
hospital is picked, holds capacity for that patient, and is actively preparing before the patient arrives. Delivered
as both a mobile app and a website — families need the phone app in the moment, hospital/blood bank staff
manage ongoing data on desktop.
3. The Users and What Each One Sees
• Family/helper (app path) — the person with the patient when the case starts via our app. Sees SOS
trigger, hospital recommendations, ETA, and (post-discharge) the feedback prompt.
• Ambulance helper — on-scene staff of a registered ambulance. Sees a minimal operational interface:
symptom logging (voice or tap), hospital selection screen, route/waypoint suggestions, QR generation at
arrival. Can now also start a case directly — see Section 4.
• Family via SMS link (no-app path) — when the case is started by the helper rather than through the
family's app, next-of-kin still gets full visibility through a lightweight tracking link. See Section 4.
• Hospital receptionist — manages ongoing bed/staff/equipment data. Sees incoming case data,
AI-triggered prep actions to confirm, QR scan-in.
• Blood bank coordinator — manages inventory, gets contacted/booked against.
• Control room — AI-run by default, with a defined human escalation contact for anomalies and conflicts.
• Government (long-term) — the eventual operator, once handed over.
What the Control Room Actually Does
Think of it as the platform's background supervisor — it doesn't talk to the family or the hospital directly, it
watches the pipeline underneath everything else. Three jobs: anomaly watching (an ambulance's location stops
updating, a case goes quiet mid-transit); conflict resolution when two urgent cases collide (two critical patients
heading to the same hospital's last ICU bed); and data reconciliation (did a reported bed actually get used, or
did the hospital quietly give it away). Every flag it raises goes to a defined human escalation contact — during
the prototype, that's the team itself — so nothing is ever silently auto-resolved.
4. The Core Pipeline, Step by Step
This is the spine of the whole system. Every feature exists to serve one of these steps.
Step 0 — How a Case Gets Created (two paths)
UPDATED THIS ROUND
Path A — Family-initiated (through our app): family hits SOS on the app, location shares automatically, our
platform dispatches a registered ambulance, helper takes over on-site.
Path B — Helper-initiated (108 call, hospital referral, walk-up): a patient reaches a registered ambulance
through any channel other than our app. The helper opens the app on-site and starts the case directly,
capturing the patient's basic details and a mandatory next-of-kin contact number. From this point on, it is the
exact same pipeline as Path A.
GPS/location always comes from the helper's device in both paths — never from the family's phone.
An earlier 'self-transport via family GPS' idea was fully scrapped: if there's no registered ambulance with our
app physically present, the platform simply doesn't engage for that case. That's an honest scope limit, not a gap
to solve around.
Why: This is the real-world scenario that matters most — most people call 108, not a startup's app, during an actual
emergency. Building for that instead of assuming app-first adoption is a much stronger, more honest story.
Family Access When the Case Started Without Them (Path B)
NEW / ADDED
The moment a Path B case is created, the system sends the captured next-of-kin number a one-time SMS
containing a link to a lightweight, no-login, read-only web view tied to that case's unique token — not the full
app, just a status page.
• Which hospital the patient is headed to, and why (distance, rating, cost tier)
• Live ETA
• Bed-lock confirmation once it happens
• Pre-arrival prep status updates as they occur
• QR-handoff confirmation once the patient arrives
Since the family isn't in the app to make the final hospital choice in this path, the helper confirms the AI's top
recommendation on their behalf — the same human-confirms principle, just with the helper as the human
present. The family sees the outcome immediately over the link. The link expires a fixed window after case
closure (24–48 hours), covering the discharge-feedback window without leaving old tracking links open
indefinitely.
Why: Zero install friction, no password, no OTP round-trip needed for a read-only view — the case token itself is the
access control. It reuses the SMS gateway already planned for OTP and feedback, so it's a new consumer of existing
infrastructure, not a new subsystem.
Step 1 — On-Scene Assessment
Helper logs criticality (Critical/Serious/Stable) and observed symptoms only — never a named diagnosis,
because a non-doctor's wrong diagnosis acted on downstream is a real safety risk. Two input methods: tap
through a checklist, or hold one button and speak naturally ("Male, roughly 60, severe chest pain, breathing
difficulty"). Speech-to-text transcribes it and auto-fills the same checklist; the helper must review and confirm
before it submits.
UPDATED THIS ROUND
Voice input language support: English, Tamil, Hindi, and Bengali for now — explicitly built to be upgraded to
more languages later, not a permanent limitation.
Step 2 — AI Hospital Ranking
UPDATED THIS ROUND
The condition-probability shortlist has been removed completely from ranking. The new logic is fully explainable
in one sentence:
• Basic specialty filter first — a simple, direct rule check on the observed symptoms (e.g. chest pain
requires a hospital with cardiology capability) filters out hospitals that plainly can't handle the case. This is
a rule lookup, not a probability model.
• Rank the remaining hospitals by time + distance + rating, separated into three cost tiers:
Government–Low, Private–Standard, Private–Premium. Never invented rupee figures.
• Government scheme boost still applies on top — if the family/helper has indicated Ayushman Bharat or
a state scheme, hospitals accepting it are boosted within their tier.
Why: This change makes the ranking logic something you can defend to a judge in one sentence — closest,
cheapest-tier-appropriate, best-rated, capable of the case — instead of defending a probability model you'd have to
justify the accuracy of. It's also simpler to build correctly.
Final selection: in Path A, the family picks from the ranked list — the AI never auto-selects. In Path B, the
helper confirms on the family's behalf (see above), and the family sees the result over the SMS link.
Step 3 — Bed Lock
The instant a hospital is chosen, that specific bed/ICU slot is put on a temporary exclusive hold so no second
case can be assigned it while the hold is active.
Step 4 — Route, Traffic Coordination and Waypoint Check
Live route/ETA pulled from Google Maps API — we never build our own routing engine. Control room
auto-alerts nearby traffic police with route and ETA. Since every case now involves a real registered ambulance
(Path A or Path B), this alert applies uniformly — there's no private-vehicle case to exclude anymore.
If the observed symptoms suggest real ALS-level risk but only a BLS ambulance is on the case, the system
checks for a registered fixed stabilization waypoint (a PHC/CHC with oxygen/a doctor) reasonably on the route,
and suggests a stop. The helper decides — never automatic.
Step 5 — Blood Check
If the case profile suggests it, the system checks the destination hospital's own stock and, if needed, places a
hold at a linked nearby blood bank.
Step 6 — Hospital Pre-Arrival Preparation
UPDATED THIS ROUND
Prep is now generic by default, with light symptom-based flags on top — not condition-specific AI reasoning.
• Generic baseline, every case: bed prepared, general duty staff notified, standard equipment checked.
• Simple keyword-triggered safety flags layered on top, off the observed symptoms, using a small fixed
lookup table: 'chest pain' logged triggers a ping to cardiology to stand by; 'visible bleeding/trauma' triggers
an alert to blood bank plus surgical standby; 'breathing difficulty' triggers a check on oxygen/ventilator
availability.
Assumption, flagged for team confirmation: this mapping is built as a small hardcoded table (fast, one-line
explainable to a judge) rather than a per-hospital-configurable rule set. If the team prefers each hospital to
define its own symptom-to-department rules during onboarding, that's a straightforward extension of the same
table later — hardcoded is faster to build and easier to defend now; per-hospital is more flexible but adds
onboarding complexity not yet scoped.
Why: This is deliberately dumb-simple compared to the old AI shortlist — a fixed lookup, not an inference step — so
it's fully explainable in one line and still gives hospitals a meaningful safety-relevant heads-up rather than nothing.
Every single prep action still requires human confirmation on the hospital dashboard — nothing fires silently, no
exceptions.
Step 7 — QR Handoff at Arrival
Helper's app generates a QR code (in both Path A and Path B — the helper always has the app). Nurse
scans it, instantly pulling in the transit timeline, logged symptoms, timestamps, and admission-ready data
captured during transit: patient identity, known allergies, current medications, next-of-kin, and scheme status.
Step 8 — Discharge Feedback
Days later, an SMS goes to the verified contact number on file — the family's own number in Path A, or the
next-of-kin number captured at case creation in Path B — with that case's ID pre-attached. Structured tags only
(wait time, staff behavior, cleanliness, billing, 'was it ready as shown') — no freeform NLP parsing. One case ID
equals one submission, blocking spam. Tag counts feed into the same hospital reliability score used for
bed-reconciliation.
5. Cross-Cutting Systems
These run underneath every step above, not as separate features.
• Privacy/DPDP compliance — minimal data collected at intake, purpose-limited, relies on DPDP's
medical-emergency provision, encrypted at rest/in transit, role-based access, post-emergency deletion
rights. The Path B read-only link is scoped to the same emergency-basis reasoning, tied to a token rather
than a full account.
• Abuse prevention — OTP ties every app-originated request to a real number; in Path B, the helper is
already a verified, onboarded platform user, so no separate per-case OTP is needed from their side.
Duplicate location and time-window requests auto-merge; rate-limiting flags but never blocks in the
moment.
• Connectivity resilience — offline-first local caching syncing when connection returns, last-known-location
fallback clearly labeled as an estimate, SMS fallback channel, pre-downloaded nearby-hospital list if live
ranking can't be reached.
• Hospital reliability layer — reconciles whether a reserved bed actually resulted in real admission, folds in
patient feedback tags, produces one unified score feeding the ranking step.
• Multi-language — interface in English, Hindi, Tamil, Bengali; voice input currently supports the same four,
built to be extended to more later.
• Safe-driving design — ETA shown as a range not a countdown, no driver speed leaderboards, app
suggests the fastest safe route only, driver judgment always overrides it.
• Adoption strategy — tiered auto-sync (real HMS API, Google Sheets connector, one-tap manual
counters, auto-decrement on confirmed admission), plus real incentives for hospitals (referral flow, fewer
chaotic rejections, free dashboard, reputational signal, compliance angle for government hospitals).
6. What We Deliberately Did Not Build, and Why
Kept and documented so the team has ready answers under questioning.
Self-transport mode using the family's own phone GPS
REMOVED / CUT
Replaced by the helper-initiated case creation (Path B) above. The real-world problem — 'what if the family
didn't book through our app' — is solved by recognizing that a registered ambulance with our app is still present
in almost every real scenario (108, hospital referral, walk-up); it's cleaner and more reliable to source location
from that helper's device than to build a parallel, less-trustworthy family-GPS mode.
Condition-probability shortlist in hospital ranking
REMOVED / CUT
Removed from ranking to make the logic fully explainable and defensible: closest, cheapest-tier-appropriate,
best-rated, capable hospital — no probability model to justify. A lighter, rule-based version of
symptom-awareness survives only in the prep step (Section 4, Step 6), not in ranking.
Bay-specific routing, WhatsApp bystander bot, moving ambulance-to-ambulance intercept,
family-facing live treatment/EMR view
REMOVED / CUT
Unchanged from the prior review round — still cut for the same reasons (no data source, bypasses abuse
prevention, real-world liability risk, and duplicating the government's own EMR mandate respectively).
7. Technical Architecture — Data Flow
Four layers, same shape as before, with two updates: the AI service's ranking logic is simpler, and a new
lightweight tracking-link service supports Path B families.
+-------------------------------------------------------------------+
| CLIENTS |
| - Family App (Path A) - Ambulance Helper App (both paths) |
| - Hospital/Blood Bank Web - Control Room Dashboard |
| - Read-only SMS Tracking Link (Path B families, no login) [NEW] |
+----------------------------+----------------------------------------+
| REST/HTTPS + live-update channel
+----------------------------+----------------------------------------+
| BACKEND API |
| - Auth & OTP - Case management (Path A + Path B entry) [UPD] |
| - Bed/blood lock - Onboarding forms - Notification dispatch |
| - Case-token generator for read-only tracking links [NEW] |
+--------+-------------------------------+------------------------------+
| |
+--------+-------------+ +---------+------------------------------+
| DATABASE | | AI / DECISION SERVICE |
| - Hospitals/beds | | - Voice to symptom extraction |
| - Cases/helpers | | - Specialty filter (rule-based)[UPD]|
| - Reliability scores |<------+ - Rank by time+distance+rating [UPD]|
| - Feedback tags | | - Generic prep + keyword flags [UPD]|
+------------------------------+ | - Reliability score calculation |
+---------------+-----------------------+
|
+------------------------+--------------------+
| EXTERNAL SERVICES |
| - Google Maps (route/ETA/traffic) |
| - Speech-to-text: Eng/Tamil/Hindi/Bengali |
| - SMS/OTP gateway (also powers tracking |
| links + discharge feedback) |
+---------------------------------------------+
Data lifecycle, concretely: hospital/blood bank/ambulance data originates from onboarding forms, kept current
via tiered auto-sync, retrieved live by the ranking step on every new case (never long-cached, since counts
change by the minute). Case data originates from the helper's app in both Path A and Path B — typed or
voice-derived — written once to the case record, and retrieved by the hospital dashboard via QR scan, by the
AI service for ranking/prep, and by the read-only tracking link for Path B families via a case-specific token
match, never a full account login.
8. Long-Term Positioning
Explicitly non-profit and built for eventual handover to a state health department, because students have no
authority to mandate hospital participation and only government does. This framing is also what makes
traffic-signal access, mandatory registration, and staffed control rooms all believable as later-phase items
instead of unresolved gaps in the pitch.
Team Vector Zero - SIH 2026 - Complete Project Picture v3
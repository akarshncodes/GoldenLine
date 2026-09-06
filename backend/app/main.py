"""FastAPI application entrypoint.

Phase 0: app wiring, CORS, /health.
Phase 1: FR-0 Case Creation router (/cases).
Phase 2: FR-1 On-Scene Assessment router (/cases/{case_id}/assessment).
Phase 3: FR-2 AI Hospital Ranking + final selection (/hospitals, /cases/{id}/hospital-ranking, ...).
Phase 4: FR-3 Bed Lock (auto-lock on selection, release, dashboard, conflict log).
Phase 5: FR-4 Route/Traffic/Waypoint + FR-5 Blood Check (run on selection).
Phase 6: FR-6 Hospital Pre-Arrival Preparation (baseline + symptom-based prep actions).
Phase 7: FR-7 QR Handoff at Arrival + FR-8 Discharge Feedback (closes the core loop).
Phase 8: FR-9 Family Access via SMS Link (read-only /track/{token} for Path B).
Phase 9: FR-11 Privacy/DPDP (auth, role scoping, HTTPS, deletion) + FR-12 Abuse
         prevention (OTP on Path A, duplicate auto-merge, rate-limit flagging).
Phase 10: FR-13/14/15 are client-side; the backend only adds GET /languages so
         the app UI + FR-1 voice-input language lists share one source of truth.
Phase 11: FR-10 Control Room — a background supervisor (no chat interface) that
         watches the pipeline and raises internal flags to a human contact:
         anomaly watching, conflict promotion (Phase-4 conflict_logs), and
         hospital bed-usage reconciliation. Only a human can resolve a flag.
Phase 12: FR-16 Hospital Data Sync — tiered bed-count sync (HMS API stub /
         Google Sheets stub / manual one-tap counter), all writing the single
         structure FR-2 ranking reads; QR-handoff admission auto-decrements the
         admitting hospital's live count, traceable to that exact handoff.
Phase 13: FR-17 Bed/Room Categories — hospital-defined capacity beyond
         general+ICU (private, ward, isolation, ...). Purely additive: never
         touches live_bed_count/live_icu_count, and the emergency pipeline
         never routes into these categories.
Phase 14: FR-18 Patient Census + Manual Admit/Discharge/Bed-Assignment —
         hospital-wide patient tracking independent of the emergency pipeline.
         Walk-in/scheduled admissions into general/ICU atomically decrement the
         SAME live_bed_count/live_icu_count columns FR-2/FR-3 read (so ranking
         and bed-lock need zero changes); every QR-handoff-admitted case also
         gets a visibility-only census entry, so the census covers every patient.
Phase 15: FR-19 Doctor/Staff Roster + On-Duty Status — a hospital-managed
         roster (deliberately not new User rows/a new Role; no individual
         doctor login needed). Soft-delete only, preserving history for FR-20.
Phase 16: FR-20 Staff Attendance / Clock-in-out — a time-stamped log, separate
         from FR-19's on-duty flag. Clock-in/out explicitly syncs the staff
         member's on_duty_status (service-to-service call, never a trigger).
Phase 17: FR-21 Medical Resource/Inventory — hospital-defined stock items
         (medicine/consumable/equipment/ppe/other) with a real movement audit
         trail (mirrors hospital_sync_events), not another JSON blob.
Phase 18: FR-22 Rule-Based Fuzzy Import — the final FR-17..22 phase. A one-time
         bootstrap from a CSV upload or Google Sheet into patients/
         hospital_staff/hospital_inventory_items/bed_categories, via stdlib
         difflib column matching (no ML) and a two-step preview/confirm flow
         that never auto-commits. Reuses each target table's own create-
         service function per row, so validation isn't duplicated.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.middleware import SecurityMiddleware
from app.routers import (
    admin,
    assessment,
    auth,
    bed_categories,
    bed_locks,
    blood,
    case_notes,
    cases,
    control_room,
    feedback,
    handoff,
    health,
    hospital_import,
    hospital_inventory,
    hospital_staff,
    hospital_sync,
    hospitals,
    mapview,
    meta,
    otp,
    patients,
    prep,
    privacy,
    route,
    staff_attendance,
    tracking,
)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0-phase18",
    description=(
        f"{settings.app_name} — Real-Time Emergency Capacity Coordination "
        f"Platform API. {settings.app_tagline}"
    ),
)

# FR-11: HTTPS-only (when enabled) + role-scoped access to every /cases/* route.
app.add_middleware(SecurityMiddleware)

# Open CORS during early development so the local web clients can call the API.
# Tighten this to specific origins in a later phase.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(meta.router)
app.include_router(auth.router)
app.include_router(otp.router)
app.include_router(privacy.router)
app.include_router(cases.router)
app.include_router(assessment.router)
app.include_router(case_notes.router)
app.include_router(hospitals.router)
app.include_router(bed_locks.router)
app.include_router(route.router)
app.include_router(blood.router)
app.include_router(prep.router)
app.include_router(handoff.router)
app.include_router(feedback.router)
app.include_router(tracking.router)
app.include_router(control_room.router)
app.include_router(hospital_sync.router)
app.include_router(admin.router)
app.include_router(mapview.router)
app.include_router(bed_categories.router)
app.include_router(patients.router)
app.include_router(hospital_staff.router)
app.include_router(staff_attendance.router)
app.include_router(hospital_inventory.router)
app.include_router(hospital_import.router)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": settings.app_name,
        "phase": "18 - FR-22 Rule-Based Fuzzy Import (final phase; FR-17..FR-22 complete)",
        "docs": "/docs",
        "health": "/health",
    }

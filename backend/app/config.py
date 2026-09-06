"""Application configuration, loaded from environment / .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GoldenLine"
    app_tagline: str = "The golden thread between every emergency and the right bed."
    env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Default: local file-based SQLite. Override with a postgresql+psycopg://... URL later.
    database_url: str = "sqlite:///./dev.db"

    # FR-4: real Google Maps Directions API key. When unset, app/services/maps.py
    # returns a clearly-marked stub route (route_source = "stub"). Plug a real key
    # in via the GOOGLE_MAPS_API_KEY env var to get live route + ETA.
    google_maps_api_key: str | None = None

    # Map view: free OSRM public routing service, used for a real road-following
    # route line when no Google Maps key is set. No key needed; set
    # OSRM_ROUTING_ENABLED=false to force the straight-line stub instead (used by
    # the test suite to stay hermetic / network-free).
    osrm_routing_enabled: bool = True

    # FR-16 tier 1: base URL of the hospitals' HMS integration gateway. When set,
    # app/services/hospital_sync.py does a real GET
    # {HMS_API_BASE_URL}/hospitals/{hospital_id}/beds expecting {"general","ICU"}.
    # When unset it falls back to a labelled mock feed (same pattern as maps.py).
    hms_api_base_url: str | None = None
    hms_api_token: str | None = None

    # --- FR-11: auth + transport security ---
    auth_secret: str = "dev-only-change-me-in-production"  # HMAC key for the JWTs
    access_token_ttl_minutes: int = 720
    # Reject plain-HTTP requests carrying case/personal data. Off for local dev;
    # a production deployment MUST terminate TLS and set FORCE_HTTPS=true (or run
    # behind a proxy that sets X-Forwarded-Proto).
    force_https: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


# --- FR-1: voice-input languages supported at launch ---------------------------
# Add a new language by appending its ISO code here. No logic code should branch
# on specific values — treat this as the single source of truth.
SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "ta": "Tamil",
    "hi": "Hindi",
    "bn": "Bengali",
}

# --- FR-4: mock recipients for the automatic traffic alert --------------------
TRAFFIC_ALERT_RECIPIENTS: list[str] = [
    "Local Traffic Control",
    "City Traffic Police Control Room",
]

# --- FR-5: units of blood assumed needed for a bleeding/trauma case -----------
BLOOD_UNITS_PER_CASE: int = 2
# Blood group used for the stock check when the patient's group is unknown
# (universal donor — safe for emergency transfusion).
UNIVERSAL_DONOR_GROUP: str = "O-"

# --- FR-2: assumed average ambulance speed, used to turn a live-GPS-derived
# distance into an ETA once the case's location is actually known (see
# hospital_ranking.py). A flat assumption, same spirit as the rest of FR-2's
# "explainable, no ML" ranking — not real traffic-aware routing (that's FR-4's
# separate, optional real-Maps-API route step).
AMBULANCE_AVG_SPEED_KMH: float = 30.0


# --- FR-6: Hospital Pre-Arrival Preparation ----------------------------------
# This is THE config table. Edit these two objects to change prep behaviour —
# there is no inference logic anywhere. Rules are hospital-wide (a flagged design
# decision; per-hospital config is a valid future extension, not built yet).

# Baseline actions created for EVERY bed-locked case, no exceptions.
BASELINE_PREP_ACTIONS: list[dict] = [
    {"action_key": "prepare_bed", "label": "Prepare bed", "suggested_department": "ward"},
    {"action_key": "notify_general_duty_staff", "label": "Notify general duty staff", "suggested_department": "duty_desk"},
    {"action_key": "check_standard_equipment", "label": "Check standard equipment", "suggested_department": "biomedical"},
]

# Symptom keyword -> extra prep action(s), layered on top of the baseline.
SYMPTOM_TO_PREP_ACTIONS: dict[str, list[dict]] = {
    "chest_pain": [
        {"action_key": "cardiology_standby", "label": "Cardiology team stand by", "suggested_department": "cardiology"},
    ],
    "visible_bleeding": [
        {"action_key": "blood_bank_alert", "label": "Alert blood bank", "suggested_department": "blood_bank"},
        {"action_key": "surgical_standby", "label": "Surgical team stand by", "suggested_department": "surgery"},
    ],
    "trauma": [
        {"action_key": "blood_bank_alert", "label": "Alert blood bank", "suggested_department": "blood_bank"},
        {"action_key": "surgical_standby", "label": "Surgical team stand by", "suggested_department": "surgery"},
    ],
    "breathing_difficulty": [
        {"action_key": "oxygen_ventilator_check", "label": "Check oxygen / ventilator availability", "suggested_department": "respiratory"},
    ],
}


# --- FR-7: handoff token lifetime --------------------------------------------
QR_TOKEN_TTL_MINUTES: int = 15
# Short alphanumeric handoff code (replaces a scannable QR — read aloud or typed
# in by hand at the hospital desk). Excludes 0/O/1/I/L to avoid misreads.
HANDOFF_CODE_LENGTH: int = 6
HANDOFF_CODE_ALPHABET: str = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

# --- FR-8: mock feedback link base (real SMS gateway wired in a later phase) --
FEEDBACK_LINK_BASE: str = "https://track.goldenline.example/feedback"

# --- FR-11: staff "forgot password" (mirrors the FR-12 OTP pattern) ---------
PASSWORD_RESET_TTL_MINUTES: int = 15
PASSWORD_RESET_CODE_LENGTH: int = 6
PASSWORD_MIN_LENGTH: int = 8

# --- FR-12: abuse prevention ------------------------------------------------
OTP_TTL_MINUTES: int = 10
OTP_CODE_LENGTH: int = 6
# Path A duplicate auto-merge: another SOS this close, this recently -> merge.
DUPLICATE_MERGE_RADIUS_METERS: float = 300.0
DUPLICATE_MERGE_WINDOW_MINUTES: int = 10
# Rate-limit FLAGGING (never blocking): more than N requests from one source
# within the window gets a review flag; the request still goes through.
RATE_LIMIT_WINDOW_SECONDS: int = 60
RATE_LIMIT_THRESHOLD: int = 5


# --- FR-10: Control Room (background supervisor) ----------------------------
# Every flag the Control Room raises is escalated to a human. During the
# prototype that human is the team itself — a single hardcoded contact.
CONTROL_ROOM_ESCALATION_CONTACT: str = (
    "GoldenLine Control Room Team <control-room@goldenline.example>"
)
# ANOMALY WATCHING thresholds. An "active in-transit case" = one with a selected
# hospital that has not yet been admitted/discharged.
#   - location stall: the ambulance/helper device GPS for such a case has not
#     updated in this many minutes -> anomaly flag.
CONTROL_ROOM_LOCATION_STALL_MINUTES: int = 10
#   - gone quiet: no activity of any kind (location, selection, status) on such a
#     case for this many minutes -> anomaly flag.
CONTROL_ROOM_CASE_QUIET_MINUTES: int = 15


# --- FR-9: Path B family SMS tracking link -----------------------------------
TRACKING_LINK_BASE: str = "https://track.goldenline.example/track"
# Placeholder expiry at case-creation time (recomputed once the case closes).
TRACKING_TOKEN_PLACEHOLDER_DAYS: int = 3650
# After the case closes, the link stays live for this long (FRP: 24-48h).
TRACKING_TOKEN_EXPIRY_HOURS_AFTER_CLOSE: int = 36

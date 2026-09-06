"""FR-2 AI Hospital Ranking.

Explainable in one sentence: "closest, cheapest-tier-appropriate, best-rated,
capable hospital." No probability / disease-likelihood model anywhere — STEP 1 is
a plain lookup table, STEP 2 is a weighted sort, STEP 3 is a within-tier nudge.
"""
from dataclasses import dataclass, field
from typing import Protocol

from app.config import AMBULANCE_AVG_SPEED_KMH
from app.models.hospital import COST_TIER_ORDER
from app.services.geo import haversine_km

# --- STEP 1: fixed symptom -> required-specialty rule table (NOT a model) ------
SYMPTOM_REQUIRED_SPECIALTY: dict[str, str] = {
    "chest_pain": "cardiology",
    "breathing_difficulty": "pulmonology",
    "visible_bleeding": "trauma_surgery",
    "trauma": "trauma_surgery",
    "unconsciousness": "emergency",
    "seizure": "neurology",
    "severe_pain": "emergency",
    "burns": "burns_unit",
    "pregnancy_labour": "obstetrics",
    "stroke_signs": "neurology",
    "high_fever": "general_medicine",
    "vomiting": "general_medicine",
    "allergic_reaction": "emergency",
    "poisoning": "emergency",
}

# --- STEP 2: ranking weights (lower combined score = better) ------------------
WEIGHT_ETA = 0.4
WEIGHT_DISTANCE = 0.4
WEIGHT_RATING = 0.2

# --- STEP 3: scheme boost -------------------------------------------------------
# A bounded nudge on the STEP-2 score, applied only inside a hospital's own tier.
# Distance/time/rating stay dominant: a scheme hospital only overtakes a
# non-scheme one in the same tier when they were already close (base-score gap
# < SCHEME_BOOST). It can never move a hospital into a different cost tier.
SCHEME_BOOST = 0.15

# Government scheme codes the platform understands.
GOVERNMENT_SCHEMES: dict[str, str] = {
    "ayushman_bharat": "Ayushman Bharat",
    "state_scheme": "State Health Scheme",
}


class HospitalLike(Protocol):
    hospital_id: str
    name: str
    specialties: list[str]
    live_bed_count: int
    live_icu_count: int
    distance_km: float
    eta_minutes: int
    rating: float
    cost_tier: str
    accepted_schemes: list[str]
    latitude: float | None
    longitude: float | None


def required_specialties_for(symptom_checklist: list[str]) -> set[str]:
    """STEP 1 lookup: the set of specialties a case needs, from its symptoms."""
    return {
        SYMPTOM_REQUIRED_SPECIALTY[s]
        for s in symptom_checklist
        if s in SYMPTOM_REQUIRED_SPECIALTY
    }


@dataclass
class RankedHospital:
    hospital_id: str
    name: str
    cost_tier: str
    rank: int
    score: float
    accepts_case_scheme: bool
    scheme_boost_applied: bool
    distance_km: float
    eta_minutes: int
    rating: float
    live_bed_count: int
    live_icu_count: int
    reason: str
    # FR-3: net of active bed locks (None when availability was not supplied)
    available_general_beds: int | None = None
    available_icu_beds: int | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass
class RankingResult:
    required_specialties: list[str]
    case_scheme: str | None
    bed_type_needed: str | None = None
    excluded_hospital_ids: list[str] = field(default_factory=list)
    excluded_no_capacity_ids: list[str] = field(default_factory=list)
    ranked: list[RankedHospital] = field(default_factory=list)
    # "live" once the case's actual location is known (helper's device has
    # reported at least once) — every distance/ETA below is real haversine
    # distance from that point. "estimated" falls back to each hospital's own
    # fixed mock distance/ETA field when no case location is known yet.
    distance_source: str = "estimated"

    @property
    def explanation(self) -> str:
        cap = (
            f" and any with no free {self.bed_type_needed} bed"
            if self.bed_type_needed
            else ""
        )
        dist_note = (
            "distance/ETA are computed live from the ambulance's current location"
            if self.distance_source == "live"
            else "distance/ETA are estimates (the ambulance hasn't reported its location yet)"
        )
        return (
            f"Hospitals without a required specialty{cap} are removed, then the rest "
            "are ordered cheapest cost tier first and, within each tier, by a blend "
            "of ETA, distance and rating"
            + (
                f"; hospitals accepting '{self.case_scheme}' are nudged up within "
                "their own tier."
                if self.case_scheme
                else "."
            )
            + f" ({dist_note})"
        )


def _normalise(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def _effective_distance_eta(h: HospitalLike, case_location: tuple[float, float] | None) -> tuple[float, int]:
    """The distance/ETA actually used for scoring: real haversine distance
    from the case's current (live, helper-device-reported) location when
    known, else the hospital's own fixed mock distance/ETA fields."""
    if case_location is not None and h.latitude is not None and h.longitude is not None:
        case_lat, case_lon = case_location
        distance_km = round(haversine_km(case_lat, case_lon, h.latitude, h.longitude), 2)
        eta_minutes = max(1, round(distance_km / AMBULANCE_AVG_SPEED_KMH * 60))
        return distance_km, eta_minutes
    return h.distance_km, h.eta_minutes


def rank_hospitals(
    hospitals: list[HospitalLike],
    required_specialties: set[str],
    case_scheme: str | None,
    *,
    availability: dict[str, dict[str, int]] | None = None,
    bed_type_needed: str | None = None,
    case_location: tuple[float, float] | None = None,
) -> RankingResult:
    result = RankingResult(
        required_specialties=sorted(required_specialties),
        case_scheme=case_scheme,
        bed_type_needed=bed_type_needed if availability is not None else None,
        distance_source="live" if case_location is not None else "estimated",
    )

    def avail(hid: str, kind: str) -> int | None:
        if availability is None:
            return None
        return availability.get(hid, {}).get(kind)

    # STEP 1 — specialty filter (plain lookup, no ML), then bed-availability filter
    capable: list[HospitalLike] = []
    for h in hospitals:
        if not required_specialties.issubset(set(h.specialties)):
            result.excluded_hospital_ids.append(h.hospital_id)
            continue
        if (
            availability is not None
            and bed_type_needed is not None
            and (avail(h.hospital_id, bed_type_needed) or 0) <= 0
        ):
            result.excluded_no_capacity_ids.append(h.hospital_id)
            continue
        capable.append(h)

    if not capable:
        return result

    # Distance/ETA actually used everywhere below — live from the case's
    # current location when known, else each hospital's static mock fields.
    effective: dict[str, tuple[float, int]] = {
        h.hospital_id: _effective_distance_eta(h, case_location) for h in capable
    }

    # STEP 2 — base score from ETA + distance + rating (lower = better)
    etas = _normalise([float(effective[h.hospital_id][1]) for h in capable])
    dists = _normalise([float(effective[h.hospital_id][0]) for h in capable])
    ratings = _normalise([float(h.rating) for h in capable])  # higher rating -> higher norm

    base_scores: dict[str, float] = {}
    for h, eta_n, dist_n, rating_n in zip(capable, etas, dists, ratings):
        base_scores[h.hospital_id] = round(
            WEIGHT_ETA * eta_n + WEIGHT_DISTANCE * dist_n + WEIGHT_RATING * (1.0 - rating_n),
            6,
        )

    # STEP 3 — scheme boost: a bounded nudge on the score, only within the tier
    def accepts_scheme(h: HospitalLike) -> bool:
        return bool(case_scheme) and case_scheme in h.accepted_schemes

    def adjusted_score(h: HospitalLike) -> float:
        s = base_scores[h.hospital_id]
        if accepts_scheme(h):
            s -= SCHEME_BOOST
        return round(s, 6)

    def sort_key(h: HospitalLike) -> tuple[int, float]:
        return (COST_TIER_ORDER.get(h.cost_tier, 99), adjusted_score(h))

    ordered = sorted(capable, key=sort_key)

    for i, h in enumerate(ordered, start=1):
        accepts = accepts_scheme(h)
        dist_km, eta_min = effective[h.hospital_id]
        result.ranked.append(
            RankedHospital(
                hospital_id=h.hospital_id,
                name=h.name,
                cost_tier=h.cost_tier,
                rank=i,
                score=adjusted_score(h),
                accepts_case_scheme=accepts,
                scheme_boost_applied=accepts,
                distance_km=dist_km,
                eta_minutes=eta_min,
                rating=h.rating,
                live_bed_count=h.live_bed_count,
                live_icu_count=h.live_icu_count,
                reason=_reason(h, dist_km, eta_min, accepts),
                available_general_beds=avail(h.hospital_id, "general"),
                available_icu_beds=avail(h.hospital_id, "ICU"),
                latitude=h.latitude,
                longitude=h.longitude,
            )
        )
    return result


def _reason(h: HospitalLike, distance_km: float, eta_minutes: int, boosted: bool) -> str:
    bits = [
        f"{h.cost_tier} tier",
        f"~{eta_minutes} min / {distance_km} km away",
        f"rating {h.rating}",
    ]
    if boosted:
        bits.append("accepts the indicated scheme (boosted within tier)")
    return ", ".join(bits)


# --- Cost-class view: the helper's actual choice screen -----------------------
# A separate, simpler cut of the same STEP-2 filtered/ranked list above, for the
# moment the helper asks the family "which class would you like?" inside the
# ambulance. Only ETA + distance decide the single best hospital in each class
# (no rating — that's a STEP-2-only signal). The scheme boost is the same
# bounded nudge as STEP 3: it only flips the pick when the candidates were
# already close, never overrides a clearly faster/closer non-scheme hospital.
CLASS_WEIGHT_ETA = 0.5
CLASS_WEIGHT_DISTANCE = 0.5
CLASS_SCHEME_BOOST = SCHEME_BOOST

COST_TIER_TO_CLASS: dict[str, str] = {
    "Government-Low": "economical",
    "Private-Standard": "moderate",
    "Private-Premium": "expensive",
}


def best_in_class(ranked: list[RankedHospital]) -> dict[str, RankedHospital | None]:
    """Group the already-filtered `ranked` list by cost class and pick, within
    each class, the single best hospital by ETA + distance only (bed
    availability is already guaranteed — `ranked` only ever contains hospitals
    with a free bed of the needed type, see rank_hospitals' capacity filter).
    """
    by_tier: dict[str, list[RankedHospital]] = {}
    for h in ranked:
        by_tier.setdefault(h.cost_tier, []).append(h)

    classes: dict[str, RankedHospital | None] = {cls: None for cls in COST_TIER_TO_CLASS.values()}
    for tier, group in by_tier.items():
        cls = COST_TIER_TO_CLASS.get(tier)
        if cls is None:
            continue
        etas = _normalise([float(h.eta_minutes) for h in group])
        dists = _normalise([float(h.distance_km) for h in group])
        scored: list[tuple[float, RankedHospital]] = []
        for h, eta_n, dist_n in zip(group, etas, dists):
            s = CLASS_WEIGHT_ETA * eta_n + CLASS_WEIGHT_DISTANCE * dist_n
            if h.accepts_case_scheme:
                s -= CLASS_SCHEME_BOOST
            scored.append((round(s, 6), h))
        scored.sort(key=lambda pair: pair[0])
        classes[cls] = scored[0][1]
    return classes

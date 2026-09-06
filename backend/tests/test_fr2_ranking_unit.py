"""FR-2 ranking algorithm — pure unit tests with crafted hospital data."""
from dataclasses import dataclass, field

from app.services.hospital_ranking import rank_hospitals, required_specialties_for


@dataclass
class FakeHospital:
    hospital_id: str
    cost_tier: str
    distance_km: float
    eta_minutes: int
    rating: float
    specialties: list[str] = field(default_factory=lambda: ["emergency"])
    accepted_schemes: list[str] = field(default_factory=list)
    name: str = "Fake"
    live_bed_count: int = 5
    live_icu_count: int = 2
    latitude: float | None = None
    longitude: float | None = None


def _order(result):
    return [h.hospital_id for h in result.ranked]


# --------------------------------------------------------- STEP 1: specialty ----
def test_symptom_specialty_lookup_is_a_plain_table():
    assert required_specialties_for(["chest_pain"]) == {"cardiology"}
    assert required_specialties_for(["chest_pain", "seizure"]) == {"cardiology", "neurology"}
    assert required_specialties_for(["high_fever"]) == {"general_medicine"}


def test_hospital_missing_required_specialty_is_excluded():
    has = FakeHospital("H-CARD", "Private-Standard", 5, 15, 4.0, specialties=["emergency", "cardiology"])
    lacks = FakeHospital("H-NONE", "Private-Standard", 1, 5, 5.0, specialties=["emergency"])
    result = rank_hospitals([has, lacks], {"cardiology"}, case_scheme=None)
    assert _order(result) == ["H-CARD"]
    assert result.excluded_hospital_ids == ["H-NONE"]


# ----------------------------------------------------------- STEP 2: sorting ----
def test_sort_order_follows_time_distance_rating():
    a = FakeHospital("A", "Private-Standard", 5.0, 15, 4.0)
    b = FakeHospital("B", "Private-Standard", 3.0, 10, 4.0)   # closest + fastest
    c = FakeHospital("C", "Private-Standard", 5.0, 15, 4.8)   # same as A but better rated
    result = rank_hospitals([a, b, c], {"emergency"}, case_scheme=None)
    assert _order(result) == ["B", "C", "A"]


def test_changing_test_data_changes_sort_order():
    a = FakeHospital("A", "Private-Standard", 5.0, 15, 5.0)   # now best-rated
    b = FakeHospital("B", "Private-Standard", 3.0, 10, 4.0)
    c = FakeHospital("C", "Private-Standard", 5.0, 15, 3.0)   # now worst-rated
    result = rank_hospitals([a, b, c], {"emergency"}, case_scheme=None)
    assert _order(result) == ["B", "A", "C"]  # A overtakes C purely on rating


def test_cheaper_tier_always_ranks_first():
    premium_great = FakeHospital("P", "Private-Premium", 1.0, 3, 5.0)
    govt_poor = FakeHospital("G", "Government-Low", 20.0, 40, 3.0)
    result = rank_hospitals([premium_great, govt_poor], {"emergency"}, case_scheme=None)
    assert _order(result) == ["G", "P"]


# ------------------------------------------------- STEP 3: scheme boost ---------
def test_scheme_boost_moves_a_CLOSE_hospital_up_within_its_tier():
    # A and B are near-equal; the scheme nudge is enough to flip them.
    a = FakeHospital("A", "Private-Standard", 10, 10, 4.0)
    b = FakeHospital("B", "Private-Standard", 12, 12, 4.0, accepted_schemes=["ayushman_bharat"])
    c = FakeHospital("C", "Private-Standard", 30, 30, 4.0)  # anchors normalisation

    without = rank_hospitals([a, b, c], {"emergency"}, case_scheme=None)
    assert _order(without) == ["A", "B", "C"]

    with_scheme = rank_hospitals([a, b, c], {"emergency"}, case_scheme="ayushman_bharat")
    assert _order(with_scheme) == ["B", "A", "C"]  # B nudged above A, still Private-Standard
    assert all(h.cost_tier == "Private-Standard" for h in with_scheme.ranked)


def test_distance_outweighs_scheme_within_a_tier():
    # A is clearly closer/faster; B has the scheme but is far behind. A stays #1.
    a = FakeHospital("A", "Private-Standard", 10, 10, 4.0)
    b = FakeHospital("B", "Private-Standard", 25, 25, 4.0, accepted_schemes=["ayushman_bharat"])
    c = FakeHospital("C", "Private-Standard", 30, 30, 4.0)

    with_scheme = rank_hospitals([a, b, c], {"emergency"}, case_scheme="ayushman_bharat")
    assert _order(with_scheme) == ["A", "B", "C"]
    assert [h.scheme_boost_applied for h in with_scheme.ranked] == [False, True, False]


def test_scheme_boost_never_crosses_cost_tiers():
    govt = FakeHospital("G", "Government-Low", 30, 40, 3.0)                # poor, no scheme
    premium = FakeHospital("P", "Private-Premium", 1, 2, 5.0,             # excellent + scheme
                           accepted_schemes=["ayushman_bharat"])
    result = rank_hospitals([govt, premium], {"emergency"}, case_scheme="ayushman_bharat")
    g_rank = next(h.rank for h in result.ranked if h.hospital_id == "G")
    p_rank = next(h.rank for h in result.ranked if h.hospital_id == "P")
    assert g_rank < p_rank
    assert result.ranked[-1].hospital_id == "P"


def test_no_ml_model_used_in_ranking_module():
    """No probability/ML model — a plain lookup + weighted sort only."""
    import app.services.hospital_ranking as m
    src = __import__("inspect").getsource(m).lower()
    for banned in ("import sklearn", "import torch", "tensorflow", "predict_proba", ".fit(", "np.random"):
        assert banned not in src

"""FR-12 Abuse Prevention — OTP on Path A, Path B auth, duplicate merge, rate-limit flag."""
from sqlalchemy import func, select

from app.models.auth import DuplicateMergeLog, RateLimitFlag
from tests.helpers import path_a_sos, verified_otp

DELHI = {"latitude": 28.6100, "longitude": 77.2000}
DELHI_NEARBY = {"latitude": 28.6108, "longitude": 77.2003}   # ~90 m away
FARAWAY = {"latitude": 19.0760, "longitude": 72.8777}         # Mumbai


# --------------------------------------------------------------- OTP ---------
def test_path_a_without_otp_is_rejected(client):
    res = client.post(
        "/cases/sos",
        json={"family_phone_number": "9876543210", "family_gps": DELHI},
    )
    assert res.status_code == 422  # otp_verification_id is required


def test_path_a_with_unverified_otp_is_rejected(client):
    req = client.post("/otp/request", json={"phone_number": "9876543210"}).json()
    # do NOT verify
    res = client.post(
        "/cases/sos",
        json={
            "family_phone_number": "9876543210",
            "family_gps": DELHI,
            "otp_verification_id": req["otp_verification_id"],
        },
    )
    assert res.status_code == 401
    assert "OTP" in res.json()["detail"]


def test_path_a_with_wrong_code_cannot_verify(client):
    req = client.post("/otp/request", json={"phone_number": "9876543210"}).json()
    res = client.post(
        "/otp/verify",
        json={"otp_verification_id": req["otp_verification_id"], "code": "000000"},
    )
    assert res.status_code == 400


def test_path_a_with_verified_otp_succeeds(client):
    res = path_a_sos(client, phone_number="9876543210", gps=DELHI)
    assert res.status_code == 201
    assert res.json()["case"]["creation_path"] == "A"


def test_an_otp_cannot_be_reused_for_a_second_case(client):
    otp_id = verified_otp(client, "9876543210")
    body = {"family_phone_number": "9876543210", "family_gps": FARAWAY, "otp_verification_id": otp_id}
    assert client.post("/cases/sos", json=body).status_code == 201
    # same OTP again -> rejected
    body2 = {**body, "family_gps": {"latitude": 13.08, "longitude": 80.27}}
    assert client.post("/cases/sos", json=body2).status_code == 401


# ----------------------------------------------------------- Path B auth ----
def test_path_b_requires_an_authenticated_helper(client_factory):
    anon = client_factory(None)
    res = anon.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 40, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": {"latitude": 12.97, "longitude": 77.59},
        },
    )
    assert res.status_code == 401

    family = client_factory(None)
    tok = family.post("/otp/request", json={"phone_number": "9800000022"}).json()
    v = family.post("/otp/verify", json={"otp_verification_id": tok["otp_verification_id"], "code": tok["dev_code"]}).json()
    family.headers["Authorization"] = f"Bearer {v['access_token']}"
    # a family token is not an helper -> still rejected
    res2 = family.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 40, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": {"latitude": 12.97, "longitude": 77.59},
        },
    )
    assert res2.status_code == 403

    helper = client_factory("HLP-001")
    assert helper.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 40, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": {"latitude": 12.97, "longitude": 77.59},
        },
    ).status_code == 201


# --------------------------------------------------- duplicate auto-merge ---
def test_two_near_duplicate_sos_merge_into_one_case(client, db_session):
    first = path_a_sos(client, phone_number="9800000001", gps=DELHI)
    assert first.status_code == 201
    primary_id = first.json()["case"]["case_id"]

    second = path_a_sos(client, phone_number="9800000002", gps=DELHI_NEARBY)  # different family member
    assert second.status_code == 201
    body = second.json()
    assert body["merged_into_existing_case"] is True
    assert body["case"]["case_id"] == primary_id            # SAME case, not a new one
    assert body["dispatched_ambulance"] is None

    assert db_session.scalar(select(func.count()).select_from(
        __import__("app.models.case", fromlist=["Case"]).Case)) == 1
    log = db_session.scalar(select(DuplicateMergeLog))
    assert log.primary_case_id == primary_id
    assert "Merged into the existing case" in log.reason


def test_far_away_sos_does_not_merge(client, db_session):
    path_a_sos(client, phone_number="9800000003", gps=DELHI)
    second = path_a_sos(client, phone_number="9800000004", gps=FARAWAY)
    assert second.json()["merged_into_existing_case"] is False
    from app.models.case import Case

    assert db_session.scalar(select(func.count()).select_from(Case)) == 2


# --------------------------------------------------- rate-limit flagging ----
def test_burst_of_requests_is_flagged_but_every_one_succeeds(client, db_session):
    codes = []
    for i in range(8):
        res = path_a_sos(
            client, phone_number="9800009999",
            gps={"latitude": 28.61 + i * 2, "longitude": 77.20},   # spread so no merge
        )
        codes.append(res.status_code)

    assert codes == [201] * 8                       # nothing was blocked

    from app.models.case import Case

    assert db_session.scalar(select(func.count()).select_from(Case)) == 8

    flags = db_session.scalars(
        select(RateLimitFlag).where(RateLimitFlag.source == "phone:9800009999")
    ).all()
    assert len(flags) >= 1
    assert flags[0].reviewed is False
    assert flags[0].request_count > 5

    # a control-room / admin account can review the flags
    from tests.helpers import DELHI as _d  # noqa

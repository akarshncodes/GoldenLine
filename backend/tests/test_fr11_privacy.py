"""FR-11 Privacy/DPDP — auth, role scoping, HTTPS, deletion requests."""
import pytest

from tests.helpers import path_a_sos, confirm_hospital

BENGALURU = {"latitude": 12.97, "longitude": 77.59}


def _path_b_case_at(client, hospital_pick_top=True) -> tuple[str, str]:
    cid = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"name": "Asha", "approx_age": 60, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": ["chest_pain"], "confirm": True},
    )
    hid = confirm_hospital(client, cid).json()["selected_hospital_id"]
    return cid, hid


# --------------------------------------------------------------- auth ---------
def test_unauthenticated_request_is_rejected(client_factory):
    anon = client_factory(None)
    cid, _ = _path_b_case_at(client_factory("admin"))
    assert anon.get(f"/cases/{cid}").status_code == 401


def test_login_requires_a_correct_password(client_factory):
    from app.services.user_seed import dev_password

    anon = client_factory(None)

    # right id + right password -> token
    res = anon.post(
        "/auth/login",
        json={"user_id": "recep-hosp-001", "password": dev_password("recep-hosp-001")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["role"] == "hospital_receptionist"
    anon.headers["Authorization"] = f"Bearer {body['access_token']}"
    assert anon.get("/auth/me").json()["hospital_id"] == "HOSP-001"


def test_login_rejects_wrong_or_missing_password(client_factory):
    anon = client_factory(None)
    # wrong password -> 401
    assert anon.post(
        "/auth/login", json={"user_id": "admin", "password": "not-the-password"}
    ).status_code == 401
    # no password field -> 422 (schema requires it)
    assert anon.post("/auth/login", json={"user_id": "admin"}).status_code == 422
    # unknown account -> 401, same generic message as a wrong password
    r_unknown = anon.post("/auth/login", json={"user_id": "nobody", "password": "x"})
    r_wrongpw = anon.post("/auth/login", json={"user_id": "admin", "password": "x"})
    assert r_unknown.status_code == r_wrongpw.status_code == 401
    assert r_unknown.json()["detail"] == r_wrongpw.json()["detail"]


def test_password_hash_is_never_plain_text(db_session):
    from app.models.auth import User
    from app.services.security import verify_password
    from app.services.user_seed import dev_password

    for uid in ("admin", "coord-bb-01", "HLP-001"):
        user = db_session.get(User, uid)
        assert user.password_hash is not None
        assert dev_password(uid) not in user.password_hash        # not stored raw
        assert user.password_hash.startswith("pbkdf2_sha256$")    # encoded PBKDF2
        assert verify_password(dev_password(uid), user.password_hash)
        assert not verify_password("wrong", user.password_hash)


# --------------------------------------------------- forgot / reset password --
def test_forgot_password_end_to_end_for_an_account_with_a_phone(client_factory, db_session):
    from app.models.sms import SmsMessage

    anon = client_factory(None)
    fp = anon.post("/auth/forgot-password", json={"user_id": "HLP-001"})
    assert fp.status_code == 200, fp.text
    body = fp.json()
    assert body["reset_token_id"]
    assert body["dev_code"] and len(body["dev_code"]) == 6   # dev-mode convenience, mirrors OTP

    # HLP-001 has a phone number -> also "sent" over the shared SMS seam
    sms = db_session.query(SmsMessage).filter_by(category="password_reset").all()
    assert len(sms) == 1
    assert sms[0].message.__contains__(body["dev_code"])

    reset = anon.post("/auth/reset-password", json={
        "reset_token_id": body["reset_token_id"], "code": body["dev_code"], "new_password": "brand-new-pass-1",
    })
    assert reset.status_code == 200, reset.text
    new_token = reset.json()["access_token"]

    # old password no longer works
    from app.services.user_seed import dev_password
    assert anon.post("/auth/login", json={"user_id": "HLP-001", "password": dev_password("HLP-001")}).status_code == 401
    # new password does
    relog = anon.post("/auth/login", json={"user_id": "HLP-001", "password": "brand-new-pass-1"})
    assert relog.status_code == 200
    # the reset response itself was already a usable, signed-in token
    anon.headers["Authorization"] = f"Bearer {new_token}"
    assert anon.get("/auth/me").json()["user_id"] == "HLP-001"


def test_forgot_password_unknown_account_is_404(client_factory):
    assert client_factory(None).post(
        "/auth/forgot-password", json={"user_id": "nobody"}
    ).status_code == 404


def test_reset_password_rejects_wrong_code_reuse_and_weak_password(client_factory):
    anon = client_factory(None)
    fp = anon.post("/auth/forgot-password", json={"user_id": "admin"}).json()

    # wrong code
    assert anon.post("/auth/reset-password", json={
        "reset_token_id": fp["reset_token_id"], "code": "000000", "new_password": "longenoughpw",
    }).status_code == 400

    # password too short -> 422 (schema-level minimum)
    assert anon.post("/auth/reset-password", json={
        "reset_token_id": fp["reset_token_id"], "code": fp["dev_code"], "new_password": "short",
    }).status_code == 422

    # correct code succeeds once
    ok = anon.post("/auth/reset-password", json={
        "reset_token_id": fp["reset_token_id"], "code": fp["dev_code"], "new_password": "longenoughpw",
    })
    assert ok.status_code == 200

    # the same code can't be replayed
    replay = anon.post("/auth/reset-password", json={
        "reset_token_id": fp["reset_token_id"], "code": fp["dev_code"], "new_password": "anotherlongpw",
    })
    assert replay.status_code == 400


def test_reset_password_code_expires(client_factory, db_session):
    from app.models.auth import PasswordResetToken
    from datetime import datetime, timedelta, timezone

    anon = client_factory(None)
    fp = anon.post("/auth/forgot-password", json={"user_id": "coord-bb-01"}).json()

    row = db_session.get(PasswordResetToken, fp["reset_token_id"])
    row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    db_session.commit()

    assert anon.post("/auth/reset-password", json={
        "reset_token_id": fp["reset_token_id"], "code": fp["dev_code"], "new_password": "longenoughpw",
    }).status_code == 400


# ----------------------------------------------------- role-scoped cases -----
def test_hospital_account_cannot_fetch_another_hospitals_case(client_factory):
    admin = client_factory("admin")
    cid, hid = _path_b_case_at(admin)          # case is routed to `hid`

    # a receptionist AT that hospital can see it
    own = client_factory("recep-hosp-001") if hid == "HOSP-001" else client_factory("recep-hosp-004")
    other = client_factory("recep-hosp-007")  # Trauma & Burns — never the pick for chest_pain

    if hid == "HOSP-001":
        assert own.get(f"/cases/{cid}").status_code == 200
    assert other.get(f"/cases/{cid}").status_code == 403
    # ...and cannot reach any of its sub-resources either
    assert other.get(f"/cases/{cid}/hospital-ranking").status_code == 403
    assert other.get(f"/cases/{cid}/bed-lock").status_code == 403


def test_hospital_dashboard_is_scoped_to_the_receptionists_hospital(client_factory):
    recep = client_factory("recep-hosp-004")
    rows = recep.get("/hospitals/dashboard").json()
    assert {r["hospital_id"] for r in rows} == {"HOSP-004"}
    hospitals = recep.get("/hospitals").json()
    assert {h["hospital_id"] for h in hospitals} == {"HOSP-004"}


def test_blood_bank_coordinator_sees_only_their_own_bank(client_factory):
    coord = client_factory("coord-bb-02")
    banks = coord.get("/blood-banks").json()
    assert {b["blood_bank_id"] for b in banks} == {"BB-02"}
    assert coord.get("/blood-banks/BB-01/holds").status_code == 403


def test_conflicts_log_is_control_room_only(client_factory):
    assert client_factory("recep-hosp-001").get("/bed-locks/conflicts").status_code == 403
    assert client_factory("control-room").get("/bed-locks/conflicts").status_code == 200
    assert client_factory("admin").get("/bed-locks/conflicts").status_code == 200


def test_family_can_only_see_their_own_case(client_factory):
    admin = client_factory("admin")
    # Path A case belongs to family:<phone>
    res = path_a_sos(admin, phone_number="9800000011")
    cid = res.json()["case"]["case_id"]

    fam = client_factory(None)
    tok = fam.post("/otp/request", json={"phone_number": "9800000011"}).json()
    v = fam.post("/otp/verify", json={"otp_verification_id": tok["otp_verification_id"], "code": tok["dev_code"]}).json()
    fam.headers["Authorization"] = f"Bearer {v['access_token']}"
    assert fam.get(f"/cases/{cid}").status_code == 200

    other_cid, _ = _path_b_case_at(admin)
    assert fam.get(f"/cases/{other_cid}").status_code == 403


# --------------------------------------------------------------- HTTPS -------
def test_https_is_enforced_when_configured(client_factory, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("FORCE_HTTPS", "true")
    get_settings.cache_clear()
    try:
        c = client_factory("admin")
        assert c.get("/health").status_code == 426  # plain http rejected
        assert c.get("/health", headers={"x-forwarded-proto": "https"}).status_code == 200
    finally:
        monkeypatch.delenv("FORCE_HTTPS", raising=False)
        get_settings.cache_clear()


# ---------------------------------------------------- deletion requests ------
def test_deletion_request_flow(client_factory, db_session):
    admin = client_factory("admin")
    cid, _ = _path_b_case_at(admin)
    tok = admin.post(f"/cases/{cid}/qr-handoff").json()["token"]
    admin.post("/qr-handoff/scan", json={"case_id": cid, "token": tok, "scanned_by": "N"})

    # before discharge -> rejected
    assert admin.post(f"/cases/{cid}/deletion-request").status_code == 409

    admin.post(f"/cases/{cid}/trigger-discharge")
    filed = admin.post(f"/cases/{cid}/deletion-request")
    assert filed.status_code == 201
    req_id = filed.json()["deletion_request_id"]
    assert filed.json()["status"] == "pending"

    # a non-admin cannot process it
    assert client_factory("recep-hosp-001").post(f"/deletion-requests/{req_id}/process").status_code == 403

    processed = admin.post(f"/deletion-requests/{req_id}/process")
    assert processed.status_code == 200
    assert processed.json()["status"] == "processed"
    assert processed.json()["processed_at"] is not None

    from app.models.case import Case

    db_session.expire_all()
    case = db_session.get(Case, cid)
    assert case.patient_name is None
    assert case.next_of_kin_phone_number is None


# ------------------------------------------- GET /cases is role-scoped ------
def test_case_list_is_scoped_by_role(client_factory):
    admin = client_factory("admin")
    cid, hid = _path_b_case_at(admin)  # routed to `hid`, helper HLP-001

    # admin sees it
    assert cid in [c["case_id"] for c in admin.get("/cases").json()]

    # the helper who started it sees it
    att = client_factory("HLP-001")
    assert cid in [c["case_id"] for c in att.get("/cases").json()]

    # the receptionist at the routed hospital sees it; others don't
    recep_map = {"HOSP-001": "recep-hosp-001", "HOSP-004": "recep-hosp-004"}
    own = client_factory(recep_map.get(hid, "recep-hosp-001"))
    other = client_factory("recep-hosp-007")  # Trauma & Burns — never picked for chest_pain
    if hid in recep_map:
        assert cid in [c["case_id"] for c in own.get("/cases").json()]
    assert cid not in [c["case_id"] for c in other.get("/cases").json()]

    # anonymous -> 401
    assert client_factory(None).get("/cases").status_code == 401

    # status filter
    assert admin.get("/cases?status_filter=DISCHARGED").json() == [] or all(
        c["status"] == "DISCHARGED" for c in admin.get("/cases?status_filter=DISCHARGED").json()
    )


# ------------------------------------------- FR-9 endpoint not widened -------
def test_tracking_endpoint_field_set_is_unchanged(client_factory, db_session):
    admin = client_factory("admin")
    from app.models.tracking import CaseTrackingToken
    from sqlalchemy import select

    cid = admin.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 40, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]
    token = db_session.scalar(select(CaseTrackingToken.token).where(CaseTrackingToken.case_id == cid))

    body = client_factory(None).get(f"/track/{token}").json()
    assert set(body) == {
        "status", "stage", "hospital", "eta", "bed_lock_status", "prep_status", "qr_handoff_status",
    }

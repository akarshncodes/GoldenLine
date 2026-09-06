"""Shared test helpers. Path A now needs an OTP (FR-12) — do the dance here once."""

DELHI = {"latitude": 28.61, "longitude": 77.20}


def verified_otp(client, phone_number: str) -> str:
    req = client.post("/otp/request", json={"phone_number": phone_number}).json()
    v = client.post(
        "/otp/verify",
        json={"otp_verification_id": req["otp_verification_id"], "code": req["dev_code"]},
    ).json()
    return v["otp_verification_id"]


def path_a_sos(client, *, phone_number: str = "9876543210", gps: dict | None = None, **extra):
    """Full Path A SOS with a fresh verified OTP. Returns the raw response."""
    otp_id = verified_otp(client, phone_number)
    body = {
        "family_phone_number": phone_number,
        "family_gps": gps or DELHI,
        "otp_verification_id": otp_id,
    }
    body.update(extra)
    return client.post("/cases/sos", json=body)


def path_a_case_id(client, **kw) -> str:
    res = path_a_sos(client, **kw)
    assert res.status_code == 201, res.text
    return res.json()["case"]["case_id"]


def confirm_hospital(client, case_id: str, *, helper_id: str = "HLP-001", cls: str = "economical"):
    """Select a hospital for `case_id` via the unified helper-driven endpoint —
    picks the given cost class (falling back to any populated class), and uses
    the right URL for the case's creation path. Defaults to the cheapest
    ("economical") class since that's usually the single candidate in a tier
    for these tests' symptom sets, closest to the old "confirm top-ranked"
    behaviour this replaces. Test scaffolding only; the business rules
    themselves are covered in test_fr2_hospital_ranking.py."""
    ranking = client.get(f"/cases/{case_id}/hospital-ranking").json()
    classes = ranking.get("classes", {})
    picked = classes.get(cls) or next((h for h in classes.values() if h), None)
    assert picked, f"no hospital available in any class for case {case_id}: {ranking}"
    case = client.get(f"/cases/{case_id}").json()
    path = "select-hospital" if case["creation_path"] == "A" else "confirm-hospital"
    return client.post(
        f"/cases/{case_id}/{path}",
        json={"hospital_id": picked["hospital_id"], "helper_id": helper_id},
    )

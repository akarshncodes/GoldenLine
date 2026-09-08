#!/usr/bin/env python3
"""GoldenLine — demo data seeder.

Populates a freshly-migrated dev.db with a realistic spread of activity so the
console dashboards (KPI cards + charts + activity feeds) have something to show:
~16 cases across every status and both paths, hospital staff rosters, medical
inventory (some low-stock), extra blood-bank holds, and control-room flags.

Runs entirely through the real HTTP API (so every downstream table — assessments,
bed locks, routes, prep actions, handoffs — is populated the same way a real
case would), then backdates `cases.created_at` directly in SQLite so the
time-series charts span the last two weeks instead of all landing on today.

Usage:  backend running on :8000, freshly migrated dev.db, then
        python3 seed_demo.py
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "http://127.0.0.1:8000"
DB = Path(__file__).parent / "backend" / "dev.db"
DEMO_PW = ".sih2026"
random.seed(20260907)

NAMES = [
    "Arjun Kumar", "Priya Raman", "Mohammed Ali", "Lakshmi Devi", "Suresh Babu",
    "Divya Menon", "Karthik Reddy", "Anjali Nair", "Vijay Anand", "Meera Pillai",
    "Rahul Sharma", "Fatima Begum", "Ganesh Iyer", "Kavya Krishnan", "Ramesh Gupta",
    "Sneha Varma", "Prakash Rao", "Deepa Joseph", "Naveen Chandra", "Ritu Singh",
]
SYMPTOMS = [
    (["chest_pain", "breathing_difficulty"], "Critical"),
    (["visible_bleeding", "trauma"], "Serious"),
    (["stroke_signs"], "Critical"),
    (["high_fever", "vomiting"], "Stable"),
    (["seizure"], "Serious"),
    (["pregnancy_labour"], "Serious"),
    (["burns"], "Serious"),
    (["allergic_reaction"], "Stable"),
    (["unconsciousness"], "Critical"),
    (["severe_pain"], "Stable"),
]
STAFF = [
    ("Dr. Anand Krishnan", "doctor", "Emergency Medicine"),
    ("Dr. Sunita Rao", "doctor", "Cardiology"),
    ("Dr. Hari Prasad", "doctor", "Trauma Surgery"),
    ("Dr. Leela Menon", "doctor", "Neurology"),
    ("Nurse Beena Thomas", "nurse", "ICU"),
    ("Nurse Ravi Shankar", "nurse", "Casualty"),
    ("Nurse Grace Paul", "nurse", "General Ward"),
    ("Lab Tech Manoj K", "technician", "Radiology"),
    ("Ward Boy Selvam", "support", None),
]
INVENTORY = [
    ("Adrenaline 1mg/mL", "medicine", "ampoule", 45, 20),
    ("Normal Saline 500mL", "consumable", "bag", 8, 15),          # low
    ("Oxygen Cylinder D-type", "equipment", "cylinder", 12, 6),
    ("Nitroglycerin spray", "medicine", "bottle", 3, 5),          # low
    ("IV Cannula 18G", "consumable", "piece", 220, 100),
    ("N95 Respirator", "ppe", "piece", 34, 50),                   # low
    ("Defibrillator pads", "consumable", "pair", 9, 8),
    ("Tranexamic acid 500mg", "medicine", "vial", 60, 25),
    ("Cervical collar", "equipment", "piece", 4, 6),              # low
    ("Suture kit", "consumable", "kit", 40, 20),
]


def _req(method: str, path: str, body=None, token: str | None = None):
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_detail": e.read().decode()[:200]}
    except Exception as e:  # noqa: BLE001
        return {"_error": str(e)}


def login(user_id: str) -> str | None:
    d = _req("POST", "/auth/login", {"user_id": user_id, "password": user_id + DEMO_PW})
    return d.get("access_token")


def main() -> None:
    if not DB.exists():
        sys.exit(f"dev.db not found at {DB} — migrate first")
    if "_error" in _req("GET", "/health"):
        sys.exit("backend not reachable on :8000")

    admin = login("admin")
    helpers = {h: login(h) for h in ("HLP-001", "HLP-002", "HLP-003", "HLP-004", "HLP-005")}
    helpers = {k: v for k, v in helpers.items() if v}
    receps = {r: login(r) for r in ("recep-hosp-001", "recep-hosp-004", "recep-hosp-007")}
    receps = {k: v for k, v in receps.items() if v}
    print(f"logged in: admin={bool(admin)} helpers={list(helpers)} receps={list(receps)}")

    hospitals = _req("GET", "/hospitals", token=admin)
    hosp_ids = [h["hospital_id"] for h in hospitals][:12]

    # ---- staff rosters ----
    made_staff = 0
    for rid, rtok in receps.items():
        me = _req("GET", "/auth/me", token=rtok)
        hid = me.get("hospital_id")
        if not hid:
            continue
        for name, cat, spec in random.sample(STAFF, k=6):
            r = _req("POST", f"/hospitals/{hid}/staff", {
                "full_name": name, "staff_category": cat, "specialty": spec,
                "phone_number": f"9{random.randint(100000000, 999999999)}",
            }, token=rtok)
            if "_error" not in r:
                made_staff += 1
                if random.random() < 0.6 and r.get("staff_id"):
                    _req("PATCH", f"/staff/{r['staff_id']}/on-duty-status",
                         {"on_duty_status": "on_duty"}, token=rtok)
    print(f"staff created: {made_staff}")

    # ---- inventory ----
    made_inv = 0
    for rid, rtok in receps.items():
        me = _req("GET", "/auth/me", token=rtok)
        hid = me.get("hospital_id")
        if not hid:
            continue
        for name, cat, unit, qty, thr in INVENTORY:
            r = _req("POST", f"/hospitals/{hid}/inventory", {
                "item_name": name, "category": cat, "unit": unit,
                "quantity_on_hand": qty, "low_stock_threshold": thr,
            }, token=rtok)
            if "_error" not in r:
                made_inv += 1
    print(f"inventory items created: {made_inv}")

    # ---- census patients ----
    made_pat = 0
    for rid, rtok in receps.items():
        me = _req("GET", "/auth/me", token=rtok)
        hid = me.get("hospital_id")
        if not hid:
            continue
        for _ in range(random.randint(4, 7)):
            nm = random.choice(NAMES)
            r = _req("POST", f"/hospitals/{hid}/patients", {
                "full_name": nm, "approx_age": random.randint(5, 88),
                "gender": random.choice(["male", "female"]),
                "patient_type": random.choice(["walk_in", "scheduled"]),
            }, token=rtok)
            if "_error" not in r and r.get("patient_id") and random.random() < 0.5:
                _req("POST", f"/patients/{r['patient_id']}/admit", {"category_code": "general"}, token=rtok)
            made_pat += 1
    print(f"census patients created: {made_pat}")

    # ---- cases (Path B, full pipeline, varied end states) ----
    case_ids: list[str] = []
    helper_items = list(helpers.items())
    for i in range(16):
        hid_login, htok = helper_items[i % len(helper_items)]
        name = NAMES[i % len(NAMES)]
        symptoms, crit = random.choice(SYMPTOMS)
        c = _req("POST", "/cases", {
            "next_of_kin_phone_number": f"9{random.randint(100000000, 999999999)}",
            "patient": {"name": name, "approx_age": random.randint(3, 90),
                        "gender": random.choice(["male", "female"])},
            "helper_id": hid_login,
            "helper_gps": {"latitude": 10.3673 + random.uniform(-0.05, 0.05),
                           "longitude": 77.9803 + random.uniform(-0.05, 0.05)},
        }, token=htok)
        cid = c.get("case_id")
        if not cid:
            print("  case create failed:", c)
            continue
        case_ids.append(cid)
        _req("POST", f"/cases/{cid}/assessment/checklist",
             {"criticality_level": crit, "symptom_checklist": symptoms, "confirm": True}, token=htok)

        stage = random.choices(["assessed", "selected", "admitted", "discharged"],
                               weights=[3, 4, 5, 4])[0]
        if stage == "assessed":
            continue
        ranking = _req("GET", f"/cases/{cid}/hospital-ranking", token=htok)
        pick = None
        classes = (ranking or {}).get("classes") or {}
        for cls in ("economical", "moderate", "expensive"):
            if classes.get(cls):
                pick = classes[cls]["hospital_id"]
                break
        if not pick:
            continue
        _req("POST", f"/cases/{cid}/confirm-hospital", {"hospital_id": pick, "helper_id": hid_login}, token=htok)
        if stage in ("admitted", "discharged"):
            q = _req("POST", f"/cases/{cid}/qr-handoff", token=htok)
            if q.get("token"):
                # any receptionist can scan in the demo
                rtok = next(iter(receps.values()), admin)
                _req("POST", "/qr-handoff/scan",
                     {"case_id": cid, "token": q["token"], "scanned_by": "recep-hosp-001"}, token=rtok)
            if stage == "discharged":
                _req("POST", f"/cases/{cid}/trigger-discharge", token=htok)
    print(f"cases created: {len(case_ids)}")

    # ---- control-room scan (generates flags from whatever's now in flight) ----
    scan = _req("POST", "/control-room/scan", token=admin)
    print(f"control-room scan: {scan.get('total', scan)}")

    # ---- backdate created_at so charts span 14 days ----
    con = sqlite3.connect(DB)
    cur = con.cursor()
    rows = cur.execute("SELECT case_id FROM cases ORDER BY created_at").fetchall()
    now = datetime.now(timezone.utc)
    for idx, (cid,) in enumerate(rows):
        days_ago = 14 - int(idx / max(1, len(rows)) * 14)
        ts = (now - timedelta(days=days_ago, hours=random.randint(0, 20),
                              minutes=random.randint(0, 59))).strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("UPDATE cases SET created_at = ? WHERE case_id = ?", (ts, cid))
    con.commit()
    con.close()
    print(f"backdated {len(rows)} cases across ~14 days")
    print("\ndone — reload the console dashboards.")


if __name__ == "__main__":
    main()

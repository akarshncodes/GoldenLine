#!/usr/bin/env bash
# End-to-end integration smoke test across every FR + the map/tracking work,
# against the CURRENT API surface (helper-driven 3-class hospital selection,
# real Dindigul hospital/blood-bank/ambulance data, live-location ranking,
# OSRM route paths, the family tracking-link endpoint, the admin cross-bank
# holds view). Replaces the pre-2026-09-04 script, which predated the
# "attender" -> "helper" rename and no longer matched the real request shapes.
#
# Usage: start the backend (see memory/project-overview.md's "Run + demo"
# section) with a freshly-migrated dev.db, then: ./integration_test.sh
set -u
BASE=http://localhost:8000
PASS=0; FAIL=0
chk() { if [ "$2" = "$3" ]; then echo "  ok   $1 ($3)"; PASS=$((PASS+1));
        else echo "  FAIL $1  expected=$2 got=$3"; FAIL=$((FAIL+1)); fi; }
jq1() { python3 -c "import sys,json;print(json.load(sys.stdin)$1)"; }

# --- auth helpers ------------------------------------------------------------
login() {
  curl -s -X POST "$BASE/auth/login" -H 'content-type: application/json' \
    -d "{\"user_id\":\"$1\",\"password\":\"$1.sih2026\"}" | jq1 '["access_token"]'
}
ADMIN=$(login admin)
HELPER=$(login HLP-001)
HELPER2=$(login HLP-002)
CONTROL=$(login control-room)
RECEPTIONIST=$(login recep-hosp-001)
COORDINATOR=$(login coord-bb-01)

curl_as() { local tok=$1; shift; command curl -H "Authorization: Bearer $tok" "$@"; }
code_as() { local tok=$1; shift; curl_as "$tok" -s -o /dev/null -w '%{http_code}' "$@"; }

# Path A SOS: OTP dance + trigger. sos <token> <phone> <lat> <lon> -> full JSON
sos() {
  local rq oid dcode vid
  rq=$(curl_as "$1" -s -X POST "$BASE/otp/request" -H 'content-type: application/json' -d "{\"phone_number\":\"$2\"}")
  oid=$(echo "$rq" | jq1 '["otp_verification_id"]'); dcode=$(echo "$rq" | jq1 '["dev_code"]')
  vid=$(curl_as "$1" -s -X POST "$BASE/otp/verify" -H 'content-type: application/json' \
    -d "{\"otp_verification_id\":\"$oid\",\"code\":\"$dcode\"}" | jq1 '["otp_verification_id"]')
  curl_as "$1" -s -X POST "$BASE/cases/sos" -H 'content-type: application/json' \
    -d "{\"family_phone_number\":\"$2\",\"family_gps\":{\"latitude\":$3,\"longitude\":$4},\"otp_verification_id\":\"$vid\"}"
}

# A verified family session's own access_token (for RBAC negative-checks).
family_token() {
  local rq oid dcode
  rq=$(curl -s -X POST "$BASE/otp/request" -H 'content-type: application/json' -d "{\"phone_number\":\"$1\"}")
  oid=$(echo "$rq" | jq1 '["otp_verification_id"]'); dcode=$(echo "$rq" | jq1 '["dev_code"]')
  curl -s -X POST "$BASE/otp/verify" -H 'content-type: application/json' \
    -d "{\"otp_verification_id\":\"$oid\",\"code\":\"$dcode\"}" | jq1 '["access_token"]'
}

echo "== Phase 0: health + real Dindigul data =="
chk "health 200"              200 "$(code_as "$ADMIN" $BASE/health)"
chk "health db up"            up  "$(curl_as "$ADMIN" -s $BASE/health | jq1 '["database"]')"
chk "25 real Dindigul hospitals" 25 "$(curl_as "$ADMIN" -s $BASE/hospitals | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')"
chk "3 real blood banks"      3   "$(curl_as "$ADMIN" -s $BASE/blood-banks | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')"
chk "20 ambulances (map)"     20  "$(curl_as "$ADMIN" -s $BASE/ambulances | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')"
chk "ambulances needs admin/control_room" 403 "$(code_as "$HELPER" $BASE/ambulances)"

echo "== Path A: SOS -> auto-dispatch -> assessment -> 3-class ranking (map lat/lng) =="
DINDIGUL_PIN='{"latitude":10.365,"longitude":77.982}'
ACASE=$(sos "$ADMIN" 9876543210 10.365 77.982)
ACID=$(echo "$ACASE" | jq1 '["case"]["case_id"]')
chk "path A case created"        A "$(curl_as "$ADMIN" -s $BASE/cases/$ACID | jq1 '["creation_path"]')"
chk "helper auto-assigned (no claim step)" True "$(echo "$ACASE" | python3 -c 'import sys,json; print(bool(json.load(sys.stdin)["case"]["helper_id"]))')"
AHELPER=$(echo "$ACASE" | jq1 '["case"]["helper_id"]')
# Path A has no authoritative case GPS until the helper's OWN device reports
# one (the family's SOS pin is audit-only, per FR-0) — simulate that report
# so ranking goes "live" and a route origin exists, exactly like a real ambulance.
curl_as "$ADMIN" -s -X POST "$BASE/cases/$ACID/helper-location" -H 'content-type: application/json' \
  -d "{\"helper_id\":\"$AHELPER\",\"gps\":{\"latitude\":10.366,\"longitude\":77.981}}" >/dev/null
chk "ranking before symptoms -> 409" 409 "$(code_as "$ADMIN" $BASE/cases/$ACID/hospital-ranking)"
curl_as "$ADMIN" -s -X POST "$BASE/cases/$ACID/assessment/checklist" -H 'content-type: application/json' \
  -d '{"criticality_level":"Serious","symptom_checklist":["chest_pain"],"confirm":true}' >/dev/null
RANK=$(curl_as "$ADMIN" -s "$BASE/cases/$ACID/hospital-ranking")
chk "required specialty cardiology" cardiology "$(echo "$RANK" | jq1 '["required_specialties"][0]')"
chk "distance_source is live (helper reported GPS)" live "$(echo "$RANK" | jq1 '["distance_source"]')"
chk "economical class has lat/lng" True "$(echo "$RANK" | python3 -c 'import sys,json; c=json.load(sys.stdin)["classes"]["economical"]; print(c is not None and c["latitude"] is not None)')"
FAMTOK=$(family_token 9876500001)
chk "family cannot select a hospital (helper-only)" 403 "$(code_as "$FAMTOK" -X POST $BASE/cases/$ACID/select-hospital -H 'content-type: application/json' -d '{"hospital_id":"HOSP-001","helper_id":"HLP-001"}')"
ECON=$(echo "$RANK" | jq1 '["classes"]["economical"]["hospital_id"]')
SEL=$(curl_as "$ADMIN" -s -X POST "$BASE/cases/$ACID/select-hospital" -H 'content-type: application/json' \
  -d "{\"hospital_id\":\"$ECON\",\"helper_id\":\"HLP-001\"}")
chk "helper picks economical class" "$ECON" "$(echo "$SEL" | jq1 '["selected_hospital_id"]')"

echo "== FR-3 Bed Lock =="
chk "bed lock active after selection" active "$(curl_as "$ADMIN" -s $BASE/cases/$ACID/bed-lock | jq1 '["lock_status"]')"

echo "== FR-4 Route: real drawable path (OSRM/Google/stub) =="
ROUTE=$(curl_as "$ADMIN" -s "$BASE/cases/$ACID/route")
chk "route_source is a known tier" True "$(echo "$ROUTE" | python3 -c 'import sys,json; print(json.load(sys.stdin)["route_source"] in ("google_maps","osrm","stub"))')"
chk "route has a drawable path"   True "$(echo "$ROUTE" | python3 -c 'import sys,json; print(len(json.load(sys.stdin).get("route_path") or []) >= 2)')"
chk "ETA is a range, not a point" True "$(echo "$ROUTE" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["eta_max_minutes"] >= d["eta_min_minutes"])')"

echo "== Path B: helper-created, bleeding case -> blood hold -> admin cross-bank view =="
BCID=$(curl_as "$HELPER2" -s -X POST "$BASE/cases" -H 'content-type: application/json' \
  -d '{"next_of_kin_phone_number":"9123456780","patient":{"name":"Test Patient","approx_age":60,"gender":"male"},"helper_id":"HLP-002","helper_gps":{"latitude":10.3705,"longitude":77.9850}}' \
  | jq1 '["case_id"]')
curl_as "$HELPER2" -s -X POST "$BASE/cases/$BCID/assessment/checklist" -H 'content-type: application/json' \
  -d '{"criticality_level":"Serious","symptom_checklist":["visible_bleeding","trauma"],"confirm":true}' >/dev/null
BRANK=$(curl_as "$HELPER2" -s "$BASE/cases/$BCID/hospital-ranking")
BECON=$(echo "$BRANK" | jq1 '["classes"]["economical"]["hospital_id"]')
curl_as "$HELPER2" -s -X POST "$BASE/cases/$BCID/confirm-hospital" -H 'content-type: application/json' \
  -d "{\"hospital_id\":\"$BECON\",\"helper_id\":\"HLP-002\"}" >/dev/null
chk "blood check triggered by bleeding+trauma" 200 "$(code_as "$HELPER2" $BASE/cases/$BCID/blood-check)"

echo "== FR-9 Tracking link (Path B only) + console tracking-link endpoint =="
TLINK=$(curl_as "$HELPER2" -s "$BASE/cases/$BCID/tracking-link")
TOKEN=$(echo "$TLINK" | jq1 '["token"]')
chk "path B tracking-link minted" True "$(python3 -c "print(len('$TOKEN') > 10)")"
PUB=$(curl_as "$ADMIN" -s "$BASE/track/$TOKEN")
chk "public /track/ scoped whitelist only" True "$(echo "$PUB" | python3 -c 'import sys,json; print(set(json.load(sys.stdin)) == {"status","stage","hospital","eta","bed_lock_status","prep_status","qr_handoff_status"})')"
chk "path A case has NO tracking link" 404 "$(code_as "$ADMIN" $BASE/cases/$ACID/tracking-link)"

echo "== FR-5 Blood-bank holds: coordinator scoped + admin unscoped (bug fix) =="
chk "admin sees all holds via /blood-bank-holds" 200 "$(code_as "$ADMIN" $BASE/blood-bank-holds)"
chk "coordinator cannot use the all-banks view" 403 "$(code_as "$COORDINATOR" $BASE/blood-bank-holds)"
chk "control_room can see all holds"  200 "$(code_as "$CONTROL" $BASE/blood-bank-holds)"

echo "== FR-6 Prep actions =="
PREP=$(curl_as "$HELPER2" -s "$BASE/cases/$BCID/prep-actions")
chk "baseline prep actions created" True "$(echo "$PREP" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d["pending"]) + len(d["confirmed"]) >= 3)')"

echo "== FR-7/FR-8 QR handoff -> admit -> discharge -> feedback =="
QR=$(curl_as "$HELPER2" -s -X POST "$BASE/cases/$BCID/qr-handoff")
QTOK=$(echo "$QR" | jq1 '["token"]')
SCAN=$(curl_as "$RECEPTIONIST" -s -X POST "$BASE/qr-handoff/scan" -H 'content-type: application/json' \
  -d "{\"case_id\":\"$BCID\",\"token\":\"$QTOK\",\"scanned_by\":\"recep-hosp-001\"}")
chk "QR scan admits the case"     ADMITTED "$(curl_as "$HELPER2" -s $BASE/cases/$BCID | jq1 '["status"]')"
curl_as "$RECEPTIONIST" -s -X POST "$BASE/cases/$BCID/trigger-discharge" >/dev/null
chk "case discharged"             DISCHARGED "$(curl_as "$HELPER2" -s $BASE/cases/$BCID | jq1 '["status"]')"
chk "tracking reflects discharge" discharged "$(curl_as "$ADMIN" -s $BASE/track/$TOKEN | jq1 '["stage"]')"

echo "== FR-10 Control room background scan =="
SCANRES=$(curl_as "$CONTROL" -s -X POST "$BASE/control-room/scan")
chk "control-room scan responds"  True "$(echo "$SCANRES" | python3 -c 'import sys,json; print("total" in json.load(sys.stdin))')"

echo "== FR-16 hospital sync dashboard =="
chk "hospital dashboard 200"      200 "$(code_as "$RECEPTIONIST" $BASE/hospitals/dashboard)"

echo
echo "================================================================"
echo " $PASS passed, $FAIL failed"
echo "================================================================"
[ "$FAIL" -eq 0 ]

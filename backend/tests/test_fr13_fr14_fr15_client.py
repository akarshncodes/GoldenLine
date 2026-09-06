"""FR-13/14/15 — client-side, checked statically + the /languages backend seam."""
import json
import re
import subprocess
from pathlib import Path

import pytest

CLIENT = Path(__file__).resolve().parents[2] / "client" / "helper-app"
I18N = CLIENT / "js" / "i18n"
LANGS = ["en", "hi", "ta", "bn"]


# --------------------------------------------------- FR-14: /languages seam --
def test_languages_endpoint_shares_one_list_with_voice_input(client):
    body = client.get("/languages").json()
    assert set(body["supported"]) == set(LANGS)
    # FR-14 item 3: FR-1 voice input uses exactly the same set as the UI
    assert body["voice_input_codes"] == body["codes"]


def test_voice_input_still_validates_against_the_same_list(client):
    from app.config import SUPPORTED_LANGUAGES

    assert set(SUPPORTED_LANGUAGES) == set(client.get("/languages").json()["supported"])


# --------------------------------------------------- FR-14: i18n coverage ----
def _keys(lang: str) -> set[str]:
    return set(json.loads((I18N / f"{lang}.json").read_text()))


def test_all_four_language_files_have_identical_keys():
    base = _keys("en")
    assert base, "en.json is empty"
    for lang in LANGS[1:]:
        k = _keys(lang)
        assert k == base, f"{lang}.json key mismatch: missing={base - k}, extra={k - base}"


def test_every_data_i18n_key_in_the_ui_is_defined():
    base = _keys("en")
    used = set()
    for f in [CLIENT / "index.html", *(CLIENT / "js").glob("*.js")]:
        text = f.read_text()
        used |= set(re.findall(r'data-i18n(?:-placeholder|-aria-label)?="([\w.]+)"', text))
        used |= set(re.findall(r"\bt\(\s*['\"]([\w.]+)['\"]", text))
    missing = {k for k in used if k not in base}
    assert not missing, f"i18n keys used in the UI but not defined: {sorted(missing)}"


def test_no_hardcoded_english_sentences_in_screen_markup():
    """Screen builders in app.js must not embed display sentences — only i18n keys."""
    app_js = (CLIENT / "js" / "app.js").read_text()
    # any run of 3+ capitalised/word tokens inside a template literal that is not a
    # data-i18n attribute value or a css/id string is suspicious
    for m in re.finditer(r">([A-Za-z][A-Za-z ,'./-]{14,})<", app_js):
        chunk = m.group(1).strip()
        assert False, f"possible hardcoded UI string in app.js markup: {chunk!r}"


# --------------------------------------------------- FR-15: safe driving -----
def test_safe_driving_check_script_passes():
    res = subprocess.run(
        ["bash", str(CLIENT / "scripts" / "check-safe-driving.sh")],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr


def test_eta_is_only_ever_formatted_as_a_range():
    eta_js = (CLIENT / "js" / "eta.js").read_text()
    assert "formatEtaRange" in eta_js
    # the template must interpolate BOTH ends
    en = json.loads((I18N / "en.json").read_text())
    assert "{min}" in en["route.etaRange"] and "{max}" in en["route.etaRange"]
    # no single-value formatter anywhere
    for f in (CLIENT / "js").glob("*.js"):
        assert not re.search(r"function\s+formatEta\s*\(\s*\w+\s*\)", f.read_text())


def test_route_deviation_never_blocks_or_penalises():
    sd = (CLIENT / "js" / "safe-driving.js").read_text()
    assert "acknowledgeDeviation" in sd
    assert "blocked: false" in sd
    assert "penalty: null" in sd
    assert not re.search(r"\b(preventDeviation|blockDeviation|deviationPenalty)\b", sd)


def test_safe_driving_doc_exists():
    assert (CLIENT / "SAFE_DRIVING.md").exists()


# --------------------------------------------------- FR-13: modules present --
@pytest.mark.parametrize("mod", [
    "offline-queue.js", "location.js", "sms-fallback.js", "hospital-cache.js",
])
def test_fr13_modules_exist(mod):
    assert (CLIENT / "js" / mod).exists()


def test_offline_queue_auto_syncs_without_a_manual_retry_control():
    q = (CLIENT / "js" / "offline-queue.js").read_text()
    # flushes automatically on reconnect...
    assert "addEventListener('online'" in q or 'addEventListener("online"' in q
    assert "startAutoSync" in q
    # ...and there is no user-facing "retry" / "sync now" control anywhere
    ui = (CLIENT / "index.html").read_text() + (CLIENT / "js" / "app.js").read_text()
    assert not re.search(r"(retry|sync now|resend|try again)", ui, re.I)


def test_estimated_location_is_styled_differently_from_live():
    css = (CLIENT / "css" / "app.css").read_text()
    assert '[data-estimated="true"]' in css and '[data-estimated="false"]' in css
    loc = (CLIENT / "js" / "location.js").read_text()
    assert "estimated: true" in loc and "estimated: false" in loc


def test_bundled_offline_hospital_list_present():
    data = json.loads((CLIENT / "data" / "offline-hospitals.json").read_text())
    assert len(data["hospitals"]) >= 4
    assert all("hospital_id" in h and "name" in h for h in data["hospitals"])

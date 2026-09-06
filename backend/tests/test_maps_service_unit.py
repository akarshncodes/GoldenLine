"""Unit tests for app.services.maps: routing tier priority + the drawable path.

Pure unit tests against maps.get_route directly (no HTTP client / DB needed) so
the OSRM/Google branches can be exercised with a mocked httpx.get instead of
real network calls — the test suite otherwise disables OSRM entirely (see
tests/conftest.py::_no_osrm_network) to stay hermetic.
"""
import httpx
import pytest

from app.config import get_settings
from app.services import maps

ORIGIN = (10.3673, 77.9803)
DEST = (10.3520, 77.9880)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.fixture()
def osrm_enabled(monkeypatch):
    monkeypatch.setenv("OSRM_ROUTING_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_decode_polyline_matches_googles_own_example():
    # The canonical example from Google's polyline algorithm documentation.
    encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    points = maps._decode_polyline(encoded)
    assert points == [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]


def test_stub_route_has_no_path_when_locations_unknown():
    result = maps._stub_route(10, None, None, note="test")
    assert result.source == "stub"
    assert result.path == []


def test_stub_route_draws_a_straight_line_when_locations_known():
    result = maps._stub_route(10, ORIGIN, DEST, note="test")
    assert result.path == [ORIGIN, DEST]


def test_osrm_used_when_no_google_key_and_osrm_enabled(monkeypatch, osrm_enabled):
    def fake_get(url, params=None, timeout=None):
        assert "router.project-osrm.org" in url
        return _FakeResponse(
            {
                "code": "Ok",
                "routes": [
                    {
                        "duration": 300,  # 5 minutes
                        "distance": 2500,
                        "geometry": {"coordinates": [[77.9803, 10.3673], [77.9880, 10.3520]]},
                    }
                ],
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    result = maps.get_route(ORIGIN, DEST, fallback_eta_minutes=15)
    assert result.source == "osrm"
    assert result.path == [(10.3673, 77.9803), (10.3520, 77.9880)]
    assert result.distance_km == 2.5
    assert result.eta_min_minutes <= result.eta_minutes <= result.eta_max_minutes


def test_osrm_disabled_by_default_in_tests_falls_back_to_stub():
    # No osrm_enabled fixture here — mirrors the suite's default (see conftest).
    result = maps.get_route(ORIGIN, DEST, fallback_eta_minutes=15)
    assert result.source == "stub"
    assert result.path == [ORIGIN, DEST]


def test_osrm_failure_falls_back_to_stub(monkeypatch, osrm_enabled):
    def fake_get(url, params=None, timeout=None):
        raise httpx.ConnectError("no network in this sandbox")

    monkeypatch.setattr(httpx, "get", fake_get)
    result = maps.get_route(ORIGIN, DEST, fallback_eta_minutes=15)
    assert result.source == "stub"
    assert "osrm call failed" in result.note
    assert result.path == [ORIGIN, DEST]


def test_google_key_takes_priority_over_osrm(monkeypatch, osrm_enabled):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key-for-test")
    get_settings.cache_clear()
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        return _FakeResponse(
            {
                "status": "OK",
                "routes": [
                    {
                        "overview_polyline": {"points": "_p~iF~ps|U_ulLnnqC"},
                        "legs": [{"duration": {"value": 300}, "distance": {"value": 2500}}],
                    }
                ],
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    try:
        result = maps.get_route(ORIGIN, DEST, fallback_eta_minutes=15)
    finally:
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
        get_settings.cache_clear()

    assert result.source == "google_maps"
    assert "maps.googleapis.com" in calls[0]
    assert result.path == [(38.5, -120.2), (40.7, -120.95)]

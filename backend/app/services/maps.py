"""FR-4: route + ETA, plus a drawable path for the map view.

`get_route(origin, destination)` is the single seam, tried in order:
1. Google Maps Directions API — real HTTP call, only when GOOGLE_MAPS_API_KEY is set.
2. OSRM's free public routing service — real road-following route, no key needed.
3. A clearly-marked STUB (`source="stub"`) — a straight line, so the rest of the
   pipeline still works with zero network dependencies.

Every tier returns `path: list[(lat, lon)]` so the client can draw the same shape
of line regardless of which source produced it. None of this is ever presented
as more accurate than it is — `source`/`note` always say which tier answered.
"""
import logging
from dataclasses import dataclass, field

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

GOOGLE_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"

Coord = tuple[float, float]


@dataclass
class RouteResult:
    source: str            # "google_maps" | "osrm" | "stub"
    polyline: str
    eta_minutes: int
    eta_min_minutes: int
    eta_max_minutes: int
    distance_km: float | None
    note: str | None = None
    path: list[Coord] = field(default_factory=list)


def get_route(
    origin: Coord | None,
    destination: Coord | None,
    *,
    fallback_eta_minutes: int,
) -> RouteResult:
    """Return a live route from Google Maps, free OSRM, or a labelled straight-line stub."""
    settings = get_settings()
    key = settings.google_maps_api_key

    if key and origin and destination:
        try:
            return _call_google_directions(key, origin, destination)
        except Exception as exc:  # noqa: BLE001 - never break the pipeline on a maps failure
            logger.warning("Google Maps Directions call failed: %s", exc)

    if settings.osrm_routing_enabled and origin and destination:
        try:
            return _call_osrm(origin, destination)
        except Exception as exc:  # noqa: BLE001 - fall through to the stub
            logger.warning("OSRM routing call failed: %s", exc)
            return _stub_route(
                fallback_eta_minutes,
                origin,
                destination,
                note=f"osrm call failed ({exc}); using straight-line stub route",
            )

    reason = "GOOGLE_MAPS_API_KEY not set" if not key else "origin/destination coordinates unknown"
    return _stub_route(fallback_eta_minutes, origin, destination, note=f"{reason}; using stub route")


def _call_google_directions(key: str, origin: Coord, destination: Coord) -> RouteResult:
    params = {
        "origin": f"{origin[0]},{origin[1]}",
        "destination": f"{destination[0]},{destination[1]}",
        "departure_time": "now",  # enables duration_in_traffic
        "key": key,
    }
    resp = httpx.get(GOOGLE_DIRECTIONS_URL, params=params, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK" or not data.get("routes"):
        raise RuntimeError(f"directions status={data.get('status')!r}")

    route = data["routes"][0]
    leg = route["legs"][0]
    base_secs = leg["duration"]["value"]
    traffic_secs = leg.get("duration_in_traffic", {}).get("value", base_secs)

    lo = max(1, round(min(base_secs, traffic_secs) / 60 * 0.95))
    hi = max(lo, round(max(base_secs, traffic_secs) / 60 * 1.15))
    point = round((lo + hi) / 2)
    encoded = route["overview_polyline"]["points"]

    return RouteResult(
        source="google_maps",
        polyline=encoded,
        eta_minutes=point,
        eta_min_minutes=lo,
        eta_max_minutes=hi,
        distance_km=round(leg["distance"]["value"] / 1000, 1),
        path=_decode_polyline(encoded),
    )


def _call_osrm(origin: Coord, destination: Coord) -> RouteResult:
    url = OSRM_URL.format(lon1=origin[1], lat1=origin[0], lon2=destination[1], lat2=destination[0])
    resp = httpx.get(url, params={"overview": "full", "geometries": "geojson"}, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RuntimeError(f"osrm status={data.get('code')!r}")

    route = data["routes"][0]
    duration_min = route["duration"] / 60
    lo = max(1, round(duration_min * 0.95))
    hi = max(lo, round(duration_min * 1.15))
    point = max(1, round(duration_min))
    # GeoJSON coordinates are [lon, lat]; flip to (lat, lon) for the client.
    path = [(lat, lon) for lon, lat in route["geometry"]["coordinates"]]

    return RouteResult(
        source="osrm",
        polyline="osrm_geojson",
        eta_minutes=point,
        eta_min_minutes=lo,
        eta_max_minutes=hi,
        distance_km=round(route["distance"] / 1000, 1),
        path=path,
    )


def _stub_route(
    fallback_eta_minutes: int, origin: Coord | None, destination: Coord | None, *, note: str
) -> RouteResult:
    eta = max(1, int(fallback_eta_minutes))
    buffer = max(3, round(eta * 0.25))
    path = [origin, destination] if origin and destination else []
    return RouteResult(
        source="stub",
        polyline=f"stub_polyline::eta~{eta}min",
        eta_minutes=eta,
        eta_min_minutes=eta,
        eta_max_minutes=eta + buffer,
        distance_km=None,
        note=note,
        path=path,
    )


def _decode_polyline(encoded: str) -> list[Coord]:
    """Decode a Google-encoded polyline into a list of (lat, lon) points.

    Standard algorithm (see Google's polyline encoding spec) — no third-party
    dependency needed for ~15 lines of integer math.
    """
    points: list[Coord] = []
    index = lat = lon = 0
    length = len(encoded)

    while index < length:
        for is_lat in (True, False):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            if is_lat:
                lat += delta
            else:
                lon += delta
        points.append((lat / 1e5, lon / 1e5))

    return points

/* GoldenLine — shared Leaflet map helper.
 *
 * Deliberately NOT an Alpine component: a Leaflet map instance is a large
 * stateful object with internal DOM/event wiring that Alpine's reactivity
 * proxy would break if it ever ended up inside x-data (the same class of
 * problem already documented for x-transition + directly-assigned state —
 * see the project's build notes). Every map instance here lives in a plain
 * module-level registry, keyed by the caller's own id string, and Alpine
 * components only ever call these plain functions.
 */
const GLMap = (() => {
  const DINDIGUL_CENTER = [10.3673, 77.9803];
  const registry = {};

  const PIN_STYLE = {
    self:        { bg: '#38bdf8', glyph: '●' },
    incident:    { bg: '#f59e0b', glyph: '✚' },
    hospital:    { bg: '#f2c14e', glyph: '🏥' },
    'hospital-selected': { bg: '#f2c14e', glyph: '★' },
    blood:       { bg: '#e11d48', glyph: '🩸' },
    'ambulance-idle':               { bg: '#64748b', glyph: '🚑' },
    'ambulance-en-route-pickup':    { bg: '#f59e0b', glyph: '🚑' },
    'ambulance-en-route-hospital':  { bg: '#f2c14e', glyph: '🚑' },
    // the specific ambulance assigned to the case being viewed (family/helper
    // case-detail map) — a live-position dot, distinct from the fleet-overview
    // 'ambulance-*' kinds above
    'ambulance-live': { bg: '#f2c14e', glyph: '🚑' },
  };

  function _icon(kind, { pulse = false, alert = false } = {}) {
    const style = PIN_STYLE[kind] || PIN_STYLE.hospital;
    const classes = [pulse ? 'gl-map-pulse' : '', alert ? 'gl-map-alert' : ''].filter(Boolean).join(' ');
    return L.divIcon({
      className: 'gl-map-icon',
      html: `<span class="gl-map-pin ${classes}" style="background:${style.bg}">${style.glyph}</span>`,
      iconSize: [26, 26],
      iconAnchor: [13, 13],
      popupAnchor: [0, -14],
    });
  }

  function getOrCreate(el, { center = DINDIGUL_CENTER, zoom = 13 } = {}) {
    if (!el) return null;
    let entry = registry[el.dataset.glMapId];
    if (entry && entry.el === el) return entry.map;

    const id = el.dataset.glMapId || `glmap-${Math.random().toString(36).slice(2)}`;
    el.dataset.glMapId = id;

    const map = L.map(el, { attributionControl: false }).setView(center, zoom);
    const tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);
    L.control.attribution({ prefix: false }).addTo(map);

    // Pins/data (from our own API) work with no internet at all; only the
    // basemap image needs a real connection to OpenStreetMap. Tell the user
    // that explicitly instead of leaving them looking at a blank grey square
    // wondering if the app is broken — a real risk on unreliable venue wifi.
    _watchTileHealth(el, tiles);

    map._glPins = L.layerGroup().addTo(map);
    map._glRoute = null;
    registry[id] = { el, map };
    return map;
  }

  function _watchTileHealth(el, tiles) {
    const banner = document.createElement('div');
    banner.className = 'gl-map-offline-banner';
    banner.textContent = 'Map imagery needs an internet connection — pins below are still live.';
    banner.hidden = true;
    el.appendChild(banner);

    let everLoaded = false;
    let pendingTimer = null;
    tiles.on('tileload', () => {
      everLoaded = true;
      banner.hidden = true;
      if (pendingTimer) { clearTimeout(pendingTimer); pendingTimer = null; }
    });
    tiles.on('tileerror', () => {
      if (everLoaded || pendingTimer) return;
      // A short grace period so one slow/blipped tile doesn't flash a banner.
      pendingTimer = setTimeout(() => {
        pendingTimer = null;
        if (!everLoaded) banner.hidden = false;
      }, 3000);
    });
  }

  function setPins(map, pins) {
    if (!map) return;
    map._glPins.clearLayers();
    const bounds = [];
    for (const p of pins || []) {
      if (p.lat == null || p.lng == null) continue;
      const marker = L.marker([p.lat, p.lng], {
        icon: _icon(p.kind, { pulse: p.pulse, alert: p.alert }),
        draggable: !!p.draggable,
      });
      if (p.label) marker.bindPopup(p.label);
      if (p.draggable && typeof p.onDrag === 'function') {
        marker.on('dragend', (e) => {
          const ll = e.target.getLatLng();
          p.onDrag(ll.lat, ll.lng);
        });
      }
      marker.addTo(map._glPins);
      bounds.push([p.lat, p.lng]);
    }
    if (bounds.length > 1) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
    else if (bounds.length === 1) map.setView(bounds[0], 14);
    setTimeout(() => map.invalidateSize(), 0);
    return bounds;
  }

  function drawRoute(map, path) {
    if (!map) return;
    if (map._glRoute) { map.removeLayer(map._glRoute); map._glRoute = null; }
    if (!path || path.length < 2) return;
    map._glRoute = L.polyline(path, { color: '#f2c14e', weight: 4, opacity: 0.85 }).addTo(map);
    map.fitBounds(map._glRoute.getBounds(), { padding: [30, 30], maxZoom: 15 });
  }

  function destroy(map) {
    if (!map) return;
    const id = Object.keys(registry).find((k) => registry[k].map === map);
    if (id) delete registry[id];
    map.remove();
  }

  return { getOrCreate, setPins, drawRoute, destroy, DINDIGUL_CENTER };
})();

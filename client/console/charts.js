/* GoldenLine — shared Chart.js helper for the console dashboards.
 *
 * Same design stance as map.js: a Chart.js instance is a stateful object with
 * its own canvas + animation loop that Alpine's reactivity proxy must never
 * wrap. Every chart lives in a plain module-level registry keyed by the canvas
 * element's id; Alpine components only call these plain functions (always from
 * a setTimeout(…, 0), never $nextTick — see the project's Alpine gotchas).
 *
 * Chart.js UMD global `Chart` is loaded from cdnjs in console/index.html.
 */
const GLCharts = (() => {
  const registry = {};

  // GoldenLine palette — gold primary, cool secondary, then semantic hues.
  const SERIES = ['#f3c24e', '#7e8cf8', '#4ade80', '#58b6f0', '#fb7185', '#a78bfa', '#fbbf24'];
  const INK_DIM = '#97a1b4';
  const GRID = 'rgba(255,255,255,0.06)';

  function _ready() { return typeof Chart !== 'undefined'; }

  function _destroy(id) {
    if (registry[id]) { registry[id].destroy(); delete registry[id]; }
  }

  function _base(canvas) {
    if (!_ready() || !canvas) return null;
    _destroy(canvas.id || (canvas.id = `glc-${Math.random().toString(36).slice(2)}`));
    return canvas.getContext('2d');
  }

  function _register(canvas, chart) {
    registry[canvas.id] = chart;
    return chart;
  }

  /* doughnut — pass {labels:[], data:[]} + optional colors */
  function donut(canvas, { labels, data, colors } = {}) {
    const ctx = _base(canvas);
    if (!ctx) return null;
    const cols = colors || labels.map((_, i) => SERIES[i % SERIES.length]);
    // all-zero → a single faint placeholder ring so the widget still reads as
    // intentional ("nothing yet") rather than a blank box; the legend beneath
    // already shows the · 0 counts.
    const empty = !(data || []).some((v) => v > 0);
    const chart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: empty ? [''] : labels,
        datasets: [{
          data: empty ? [1] : data,
          backgroundColor: empty ? ['rgba(255,255,255,0.06)'] : cols,
          borderColor: '#141a24',
          borderWidth: 2,
          hoverOffset: empty ? 0 : 6,
        }],
      },
      options: {
        cutout: '68%',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { enabled: !empty, backgroundColor: '#192230', borderColor: 'rgba(255,255,255,.1)', borderWidth: 1, padding: 10, cornerRadius: 8 },
        },
      },
    });
    return _register(canvas, chart);
  }

  /* smooth area line — {labels:[], data:[]} */
  function area(canvas, { labels, data, label } = {}) {
    const ctx = _base(canvas);
    if (!ctx) return null;
    const g = ctx.createLinearGradient(0, 0, 0, 240);
    g.addColorStop(0, 'rgba(243,194,78,0.28)');
    g.addColorStop(1, 'rgba(243,194,78,0.0)');
    const chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: label || 'Series',
          data,
          borderColor: '#f3c24e',
          backgroundColor: g,
          fill: true,
          tension: 0.4,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: '#f3c24e',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { backgroundColor: '#192230', borderColor: 'rgba(255,255,255,.1)', borderWidth: 1, padding: 10, cornerRadius: 8 },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: INK_DIM, font: { size: 10 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 7 } },
          y: { grid: { color: GRID }, ticks: { color: INK_DIM, font: { size: 10 }, precision: 0 }, beginAtZero: true },
        },
      },
    });
    return _register(canvas, chart);
  }

  /* grouped/simple bars — {labels:[], datasets:[{label,data,color}]} */
  function bars(canvas, { labels, datasets, horizontal } = {}) {
    const ctx = _base(canvas);
    if (!ctx) return null;
    const chart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: datasets.map((d, i) => ({
          label: d.label,
          data: d.data,
          backgroundColor: d.color || SERIES[i % SERIES.length],
          borderRadius: 5,
          borderSkipped: false,
          barPercentage: 0.7,
          categoryPercentage: 0.72,
        })),
      },
      options: {
        indexAxis: horizontal ? 'y' : 'x',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: datasets.length > 1, labels: { color: INK_DIM, font: { size: 11 }, boxWidth: 10, boxHeight: 10, usePointStyle: true } },
          tooltip: { backgroundColor: '#192230', borderColor: 'rgba(255,255,255,.1)', borderWidth: 1, padding: 10, cornerRadius: 8 },
        },
        scales: {
          x: { grid: { display: !horizontal ? false : true, color: GRID }, ticks: { color: INK_DIM, font: { size: 10 }, precision: 0 }, stacked: false },
          y: { grid: { display: horizontal ? false : true, color: GRID }, ticks: { color: INK_DIM, font: { size: 10 }, precision: 0 }, beginAtZero: true },
        },
      },
    });
    return _register(canvas, chart);
  }

  function destroyAll() { Object.keys(registry).forEach(_destroy); }

  return { donut, area, bars, destroyAll, SERIES, ready: _ready };
})();

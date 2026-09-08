/* GoldenLine — landing page behaviour (vanilla, no framework).
 *   · rotating headline word
 *   · count-up stats when they scroll into view
 *   · scroll-reveal for .gl-reveal
 *   · FAQ accordion
 *   · sticky-nav shadow + "already signed in" CTA swap
 *   · footer API health line
 */
const API = (typeof window !== 'undefined' && window.GOLDENLINE_API) || 'http://localhost:8000';
const TOKEN_KEY = 'goldenline.token';

document.addEventListener('DOMContentLoaded', () => {
  // ---- rotating headline word ----------------------------------------------
  const rot = document.querySelectorAll('.gl-rotator > span');
  if (rot.length) {
    let i = 0;
    setInterval(() => {
      rot[i].classList.remove('is-active');
      i = (i + 1) % rot.length;
      rot[i].classList.add('is-active');
    }, 2200);
  }

  // ---- scroll reveal -----------------------------------------------------
  // IntersectionObserver for the nice staggered effect, PLUS a plain
  // scroll/timeout fallback so content can never get stuck invisible if IO is
  // throttled or the tab was backgrounded at load.
  const reveals = [...document.querySelectorAll('.gl-reveal')];
  const show = (el) => el.classList.add('is-in');
  const revealVisible = () => {
    const vh = window.innerHeight || document.documentElement.clientHeight;
    for (const el of reveals) {
      if (el.classList.contains('is-in')) continue;
      const r = el.getBoundingClientRect();
      if (r.top < vh * 0.94 && r.bottom > 0) show(el);
    }
  };
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) { show(e.target); io.unobserve(e.target); }
    }, { threshold: 0.1, rootMargin: '0px 0px -6% 0px' });
    reveals.forEach((el) => io.observe(el));
  }
  revealVisible();
  window.addEventListener('scroll', revealVisible, { passive: true });
  window.addEventListener('resize', revealVisible, { passive: true });
  setTimeout(revealVisible, 400);
  setTimeout(() => reveals.forEach(show), 2600);   // hard safety net

  // ---- count-up --------------------------------------------------------
  const countUp = (el) => {
    if (el.dataset.counted) return;
    el.dataset.counted = '1';
    const target = parseFloat(el.dataset.count || '0');
    const prefix = (el.dataset.prefix || '').replace('&lt;', '<');
    const suffix = el.dataset.suffix || '';
    const dur = 1100;
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = `${prefix}${Math.round(target * eased)}${suffix}`;
      if (p < 1) requestAnimationFrame(tick);
      else el.textContent = `${prefix}${target}${suffix}`;
    };
    requestAnimationFrame(tick);
  };
  const counters = [...document.querySelectorAll('[data-count]')];
  const runCountersInView = () => {
    const vh = window.innerHeight || 800;
    for (const el of counters) {
      const r = el.getBoundingClientRect();
      if (r.top < vh * 0.9 && r.bottom > 0) countUp(el);
    }
  };
  if ('IntersectionObserver' in window) {
    const cio = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) { countUp(e.target); cio.unobserve(e.target); }
    }, { threshold: 0.5 });
    counters.forEach((el) => cio.observe(el));
  }
  runCountersInView();
  window.addEventListener('scroll', runCountersInView, { passive: true });
  setTimeout(() => counters.forEach(countUp), 2800);

  // ---- FAQ accordion ----------------------------------------------------
  document.querySelectorAll('.gl-accordion-q').forEach((btn) => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.gl-accordion-item');
      const open = item.classList.contains('is-open');
      document.querySelectorAll('.gl-accordion-item').forEach((x) => x.classList.remove('is-open'));
      if (!open) item.classList.add('is-open');
    });
  });

  // ---- sticky nav ------------------------------------------------------
  const nav = document.getElementById('nav');
  const onScroll = () => nav.classList.toggle('is-stuck', window.scrollY > 24);
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  // ---- already signed in? swap the CTA -------------------------------
  let token = null;
  try { token = localStorage.getItem(TOKEN_KEY); } catch { /* ignore */ }
  if (token) {
    fetch(`${API}/auth/me`, { headers: { authorization: `Bearer ${token}` } })
      .then((r) => {
        if (!r.ok) return;
        const cta = document.getElementById('navCta');
        if (cta) { cta.textContent = 'Open console →'; cta.href = 'console/index.html'; }
        document.querySelectorAll('a[href="login.html"]').forEach((a) => { a.href = 'console/index.html'; });
      })
      .catch(() => {});
  }

  // ---- footer API health --------------------------------------------
  const apiState = document.getElementById('apiState');
  fetch(`${API}/health`)
    .then((r) => { apiState.textContent = r.ok ? 'API online' : 'API unreachable'; })
    .catch(() => { apiState.textContent = 'API offline — start the backend on :8000'; });
});

/* Page d'accueil : diaporama du haut (photo + mot qui changent ensemble),
   mots qui s'allument, scènes qui s'ouvrent au défilement, cartes qui
   apparaissent et s'inclinent, compteurs, rail des produits. */
(function () {
  'use strict';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var clamp = function (v, a, b) { return Math.max(a, Math.min(b, v)); };
  var vh = function () { return window.innerHeight || document.documentElement.clientHeight; };

  /* ── 1) Diaporama du haut ── */
  var hx = document.getElementById('hx');
  if (hx) {
    var slides = [].slice.call(hx.querySelectorAll('.hx__slide'));
    var words = [].slice.call(hx.querySelectorAll('.hx__word'));
    var tabs = [].slice.call(hx.querySelectorAll('.hx__tab'));
    var DUR = 5000, cur = 0, timer = null;
    hx.style.setProperty('--dur', DUR + 'ms');
    var go = function (n) {
      if (n === cur) return;
      var prev = cur; cur = (n + slides.length) % slides.length;
      slides[prev].classList.remove('is-on'); slides[cur].classList.add('is-on');
      words[prev].classList.remove('is-on'); words[prev].classList.add('is-out');
      setTimeout(function () { words[prev].classList.remove('is-out'); }, 700);
      words[cur].classList.add('is-on');
      tabs.forEach(function (t, i) {
        t.classList.remove('is-on');
        t.classList.toggle('is-done', i < cur);
      });
      if (tabs[cur]) { void tabs[cur].offsetWidth; tabs[cur].classList.add('is-on'); }
    };
    var start = function () { clearInterval(timer); if (!reduce) timer = setInterval(function () { go(cur + 1); }, DUR); };
    tabs.forEach(function (t, i) { t.addEventListener('click', function () { go(i); start(); }); });
    start();
  }

  /* ── 2) Constat : les mots s'allument au défilement ── */
  var wordsBox = document.querySelector('[data-words]');
  var wordEls = [];
  if (wordsBox) {
    var HL = ['clients,', 'ventes', 'revenus.'];
    wordsBox.innerHTML = wordsBox.textContent.trim().split(/\s+/).map(function (w) {
      return '<span class="w' + (HL.indexOf(w) > -1 ? ' hl' : '') + '">' + w + '</span>';
    }).join(' ');
    wordEls = [].slice.call(wordsBox.querySelectorAll('.w'));
  }
  var scenes = [].slice.call(document.querySelectorAll('[data-scene]'));

  function onScroll() {
    var h = vh();
    if (wordEls.length) {
      var r = wordsBox.getBoundingClientRect();
      var p = clamp((h * 0.85 - r.top) / (r.height + h * 0.35), 0, 1);
      var n = Math.round(p * wordEls.length);
      for (var i = 0; i < wordEls.length; i++) wordEls[i].classList.toggle('on', i < n);
    }
    var mobile = window.innerWidth <= 820;
    scenes.forEach(function (s) {
      var rs = s.getBoundingClientRect();
      var ps = clamp((h - rs.top) / (h * 0.6), 0, 1);
      s.style.setProperty('--p', ps.toFixed(3));
    });
  }
  if (reduce) {
    wordEls.forEach(function (w) { w.classList.add('on'); });
    scenes.forEach(function (s) { s.style.setProperty('--p', 1); });
  } else {
    var ticking = false;
    var req = function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () { ticking = false; onScroll(); });
    };
    window.addEventListener('scroll', req, { passive: true });
    window.addEventListener('resize', req);
    onScroll();
  }

  /* ── 3) Cartes et compteurs ── */
  var cards = [].slice.call(document.querySelectorAll('.lx-card'));
  var counters = [].slice.call(document.querySelectorAll('[data-count]'));
  var fmt = function (n) { return n.toLocaleString('fr-FR'); };
  function countUp(el) {
    var end = parseInt(el.dataset.count, 10) || 0, t0 = null, dur = 1600;
    (function step(t) {
      if (!t0) t0 = t;
      var q = clamp((t - t0) / dur, 0, 1);
      el.textContent = fmt(Math.round(end * (1 - Math.pow(1 - q, 3))));
      if (q < 1) requestAnimationFrame(step);
    })(performance.now());
  }
  if (reduce || !('IntersectionObserver' in window)) {
    cards.forEach(function (c) { c.classList.add('in'); });
    counters.forEach(function (c) { c.textContent = fmt(parseInt(c.dataset.count, 10) || 0); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var el = e.target;
        if (el.classList.contains('lx-card')) {
          el.style.transitionDelay = (cards.indexOf(el) % 4) * 90 + 'ms';
          el.classList.add('in');
          setTimeout(function () { el.style.transitionDelay = ''; }, 1200);
        } else {
          countUp(el);
        }
        io.unobserve(el);
      });
    }, { threshold: 0.25 });
    cards.forEach(function (c) { io.observe(c); });
    counters.forEach(function (c) { io.observe(c); });
    // filet de sécurité : rien ne reste caché si l'observateur ne se déclenche pas
    setTimeout(function () { cards.forEach(function (c) { if (c.getBoundingClientRect().top < vh()) c.classList.add('in'); }); }, 2500);

    if (window.matchMedia('(pointer: fine)').matches) {
      cards.forEach(function (t) {
        t.addEventListener('pointermove', function (e) {
          var r = t.getBoundingClientRect();
          t.style.setProperty('--ty', (((e.clientX - r.left) / r.width - 0.5) * 6).toFixed(2) + 'deg');
          t.style.setProperty('--tx', (-((e.clientY - r.top) / r.height - 0.5) * 6).toFixed(2) + 'deg');
        });
        t.addEventListener('pointerleave', function () { t.style.setProperty('--tx', '0deg'); t.style.setProperty('--ty', '0deg'); });
      });
    }
  }

  /* ── 4) Rail des produits ── */
  var rail = document.querySelector('[data-rail]');
  if (rail) {
    var by = function (dir) {
      var card = rail.querySelector('.lx-prod');
      rail.scrollBy({ left: dir * (card ? card.offsetWidth + 18 : 300) * 2, behavior: reduce ? 'auto' : 'smooth' });
    };
    var prev = document.querySelector('[data-rail-prev]'), next = document.querySelector('[data-rail-next]');
    prev && prev.addEventListener('click', function () { by(-1); });
    next && next.addEventListener('click', function () { by(1); });
  }
}());

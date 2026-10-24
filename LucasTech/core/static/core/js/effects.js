/* Effets discrets du site : apparition douce des cartes au défilement et chiffres qui montent.
   Respecte le réglage « réduire les animations » du téléphone / de l'ordinateur. */
(function () {
  'use strict';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce || !('IntersectionObserver' in window)) return;

  /* 1) Cartes : elles apparaissent en douceur quand on arrive dessus (seulement celles qui sont sous l'écran) */
  var CARDS = '.sh-card, .sv-card, .fl-card, .pb-card, .pd-rel-card, .sd-related-card, .fd-related-card, .pd-related-card, ' +
              '.nw-card, .nw-mini, .tm-card, .pj-card, .pt-card, .eh-card';
  var cards = Array.prototype.slice.call(document.querySelectorAll(CARDS));
  var below = cards.filter(function (el) { return el.getBoundingClientRect().top > window.innerHeight * 0.92; });
  below.forEach(function (el) { el.classList.add('fx-hidden'); });
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      // visible, ou déjà dépassée (saut vers une ancre, retour en haut) : on l'affiche dans les deux cas
      if (!entry.isIntersecting && entry.boundingClientRect.top >= 0) return;
      var el = entry.target;
      var rank = below.indexOf(el) % 4;           // petit décalage d'une carte à l'autre sur une même ligne
      el.style.transitionDelay = (rank * 70) + 'ms';
      el.classList.add('fx-in');
      io.unobserve(el);
    });
  }, { threshold: 0.08, rootMargin: '0px 0px -4% 0px' });
  below.forEach(function (el) { io.observe(el); });
  // filet de sécurité : rien ne doit rester invisible si l'observateur tarde
  var ticking = false;
  window.addEventListener('scroll', function () {
    if (ticking) return;
    ticking = true;
    setTimeout(function () {
      ticking = false;
      below.forEach(function (el) {
        if (!el.classList.contains('fx-in') && el.getBoundingClientRect().top < window.innerHeight * 0.9) { el.classList.add('fx-in'); io.unobserve(el); }
      });
    }, 120);
  }, { passive: true });

  /* 2) Chiffres clés : ils montent jusqu'à leur valeur la première fois qu'on les voit */
  var counters = Array.prototype.slice.call(document.querySelectorAll('.pt-stat-num, .eh-stat b, [data-count]'));
  var co = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      co.unobserve(entry.target);
      var el = entry.target, text = el.textContent.trim();
      var m = text.match(/^(\d[\d\s]*)(.*)$/);
      if (!m) return;
      var target = parseInt(m[1].replace(/\s/g, ''), 10), suffix = m[2] || '';
      if (!target || target > 100000) return;
      var start = null, dur = 900;
      function tick(t) {
        if (start === null) start = t;
        var p = Math.min(1, (t - start) / dur), eased = 1 - Math.pow(1 - p, 3);
        el.textContent = Math.round(target * eased).toLocaleString('fr-FR') + suffix;
        if (p < 1) requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
    });
  }, { threshold: 0.6 });
  counters.forEach(function (el) { co.observe(el); });
})();

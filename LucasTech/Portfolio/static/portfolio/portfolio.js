/* Portfolio — animations et fenêtres de détail (sans bibliothèque) */
(function () {
  'use strict';
  var root = document.documentElement;
  root.classList.add('js');
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return [].slice.call((c || document).querySelectorAll(s)); };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  }

  /* ── Navigation : ombre au défilement, menu mobile, section active ── */
  var nav = $('#pfNav'), burger = $('#pfBurger'), links = $('#pfLinks');
  function onScrollNav() { if (nav) nav.classList.toggle('scrolled', window.scrollY > 12); }
  onScrollNav();
  window.addEventListener('scroll', onScrollNav, { passive: true });
  function setMenu(open) {
    if (!burger || !links) return;
    links.classList.toggle('open', open);
    if (nav) nav.classList.toggle('menu-open', open);
    burger.classList.toggle('open', open);
    burger.setAttribute('aria-expanded', String(open));
  }
  if (burger) {
    burger.addEventListener('click', function () { setMenu(!links.classList.contains('open')); });
    $$('a', links).forEach(function (a) { a.addEventListener('click', function () { setMenu(false); }); });
  }

  var spy = $$('.pf-links a[href^="#"]').map(function (a) { return { a: a, s: $(a.getAttribute('href')) }; }).filter(function (x) { return x.s && !x.a.classList.contains('pf-cta'); });
  function onScrollSpy() {
    var cur = null, y = window.innerHeight * 0.35;
    spy.forEach(function (x) { if (x.s.getBoundingClientRect().top < y) cur = x; });
    spy.forEach(function (x) { x.a.classList.toggle('on', x === cur); });
  }
  if (spy.length) { window.addEventListener('scroll', onScrollSpy, { passive: true }); onScrollSpy(); }

  /* ── Apparition au défilement ── */
  var rv = $$('.rv');
  if ('IntersectionObserver' in window && !reduce) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.1 });
    rv.forEach(function (n) { io.observe(n); });
  } else { rv.forEach(function (n) { n.classList.add('in'); }); }

  /* ── « Qui est … ? » : le texte s'écrit petit à petit au clic ── */
  var who = $('#who'), whoBtn = $('#whoBtn'), whoText = $('#whoText'), whoSkip = $('#whoSkip'), whoMore = $('.who-more');
  if (who && whoBtn) {
    var words = [];
    function split(node) {
      [].slice.call(node.childNodes).forEach(function (c) {
        if (c.nodeType === 3) {
          var frag = document.createDocumentFragment();
          c.nodeValue.split(/(\s+)/).forEach(function (t) {
            if (!t) return;
            if (/^\s+$/.test(t)) { frag.appendChild(document.createTextNode(' ')); return; }
            var s = el('span', 'w', t); words.push(s); frag.appendChild(s);
          });
          c.parentNode.replaceChild(frag, c);
        } else if (c.nodeType === 1) { split(c); }
      });
    }
    if (whoText) split(whoText);

    var timer = null;
    function finish() {
      clearInterval(timer);
      words.forEach(function (w) { w.classList.add('on'); });
      if (whoSkip) whoSkip.hidden = true;
      if (whoMore) whoMore.classList.add('in');
    }
    function start() {
      who.classList.add('open');
      whoBtn.setAttribute('aria-expanded', 'true');
      if (!words.length || reduce) { finish(); return; }
      var i = 0, step = Math.max(18, Math.min(70, 9000 / words.length));
      timer = setInterval(function () {
        words[i].classList.add('on'); i++;
        if (i >= words.length) { finish(); }
      }, step);
    }
    whoBtn.addEventListener('click', start);
    if (whoSkip) whoSkip.addEventListener('click', finish);
  }

  /* ── Fenêtre de détail ── */
  var modal = $('#pfModal'), box = modal && $('.pf-modal-box', modal), body = $('#pfModalBody'), lastFocus = null;
  function openModal(node, wide) {
    if (!modal) return;
    lastFocus = document.activeElement;
    body.innerHTML = '';
    body.appendChild(node);
    box.classList.toggle('wide', !!wide);
    modal.hidden = false;
    root.classList.add('modal-open');
    var c = $('.pf-modal-close', modal); if (c) c.focus();
  }
  function closeModal() {
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    root.classList.remove('modal-open');
    body.innerHTML = '';
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  if (modal) {
    modal.addEventListener('click', function (e) { if (e.target === modal || e.target.closest('.pf-modal-close')) closeModal(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeModal(); });
  }

  function readData(id) {
    var n = document.getElementById(id);
    try { return n ? JSON.parse(n.textContent) : []; } catch (e) { return []; }
  }

  // Compétences
  var skills = readData('skillsData');
  $$('[data-skill]').forEach(function (b) {
    b.addEventListener('click', function () {
      var s = skills.filter(function (x) { return String(x.id) === b.getAttribute('data-skill'); })[0];
      if (!s) return;
      var wrap = el('div');
      var head = el('div', 'm-head');
      var logo = el('div', 'm-logo');
      if (s.logo) { var im = el('img'); im.src = s.logo; im.alt = ''; logo.appendChild(im); }
      else if (s.icon) { var ic = el('i', s.icon); logo.appendChild(ic); }
      else { logo.textContent = s.name.slice(0, 2); }
      var tt = el('div'); tt.appendChild(el('h3', '', s.name));
      var badges = el('div', 'm-badges'); badges.appendChild(el('span', '', s.category));
      if (s.level) badges.appendChild(el('span', 'lvl', 'Niveau : ' + s.level));
      tt.appendChild(badges); head.appendChild(logo); head.appendChild(tt); wrap.appendChild(head);
      if (s.description) { var a = el('div', 'm-sec'); a.appendChild(el('h4', '', "C'est quoi ?")); a.appendChild(el('p', '', s.description)); wrap.appendChild(a); }
      if (s.usage) { var u = el('div', 'm-sec'); u.appendChild(el('h4', '', "Comment je l'utilise")); u.appendChild(el('p', '', s.usage)); wrap.appendChild(u); }
      if (!s.description && !s.usage) { var e = el('div', 'm-sec'); e.appendChild(el('p', '', "Les détails de cette technologie seront bientôt ajoutés.")); wrap.appendChild(e); }
      if (s.projects && s.projects.length) {
        var p = el('div', 'm-sec'); p.appendChild(el('h4', '', 'Projets où je l\'utilise'));
        var l = el('div', 'm-links');
        s.projects.forEach(function (pr) { var a2 = el('a', '', pr.title); a2.href = pr.url; l.appendChild(a2); });
        p.appendChild(l); wrap.appendChild(p);
      }
      openModal(wrap, false);
    });
  });

  // Certificats
  var certs = readData('certsData');
  $$('[data-cert]').forEach(function (b) {
    b.addEventListener('click', function () {
      var c = certs.filter(function (x) { return String(x.id) === b.getAttribute('data-cert'); })[0];
      if (!c) return;
      var wrap = el('div');
      var head = el('div', 'm-head'); var tt = el('div'); tt.appendChild(el('h3', '', c.title));
      var badges = el('div', 'm-badges'); badges.appendChild(el('span', '', c.kind));
      if (c.organization) badges.appendChild(el('span', '', c.organization));
      if (c.date) badges.appendChild(el('span', '', c.date));
      tt.appendChild(badges); head.appendChild(tt); wrap.appendChild(head);
      if (c.description) { var d = el('div', 'm-sec'); d.appendChild(el('p', '', c.description)); wrap.appendChild(d); }
      if (c.image) { var box2 = el('div', 'm-img'); var im = el('img'); im.src = c.image; im.alt = c.title; box2.appendChild(im); wrap.appendChild(box2); }
      var l = el('div', 'm-links');
      if (c.file) { var f = el('a', '', 'Ouvrir le PDF'); f.href = c.file; f.target = '_blank'; f.rel = 'noopener'; l.appendChild(f); }
      if (c.verify) { var v = el('a', '', 'Vérifier le document'); v.href = c.verify; v.target = '_blank'; v.rel = 'noopener noreferrer'; l.appendChild(v); }
      if (l.children.length) { var sec = el('div', 'm-sec'); sec.appendChild(l); wrap.appendChild(sec); }
      openModal(wrap, true);
    });
  });

  // Images (agrandir)
  $$('[data-zoom]').forEach(function (img) {
    img.addEventListener('click', function () {
      var wrap = el('div', 'm-img'); var im = el('img'); im.src = img.currentSrc || img.src; im.alt = img.alt || ''; wrap.appendChild(im);
      openModal(wrap, true);
    });
  });
})();

/* Recherche instantanée des rubriques : <input data-live=".carte" data-rien="id-du-message" [data-groupes=".groupe"]>.
   Filtre pendant la frappe ; accents, majuscules, mots partiels et fautes de frappe tolérés. */
(function () {
  function n(t) { return (t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, ' ').trim(); }
  function d(a, b) {
    var m = [], i, j; for (i = 0; i <= a.length; i++) m[i] = [i];
    for (j = 0; j <= b.length; j++) m[0][j] = j;
    for (i = 1; i <= a.length; i++) for (j = 1; j <= b.length; j++)
      m[i][j] = Math.min(m[i - 1][j] + 1, m[i][j - 1] + 1, m[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    return m[a.length][b.length];
  }
  function ok(mot, mots) {
    return mots.some(function (x) {
      if (x.indexOf(mot) === 0 || (mot.length > 2 && x.indexOf(mot) >= 0)) return true;
      if (mot.length < 4) return false;
      var tol = mot.length >= 8 ? 2 : 1;
      return d(mot, x.slice(0, mot.length)) <= tol || d(mot, x) <= tol;
    });
  }
  function brancher(q) {
    var cartes = [].slice.call(document.querySelectorAll(q.dataset.live));
    var groupes = q.dataset.groupes ? [].slice.call(document.querySelectorAll(q.dataset.groupes)) : [];
    var rien = q.dataset.rien ? document.getElementById(q.dataset.rien) : null;
    cartes.forEach(function (c) { c._m = n(c.dataset.t || c.textContent).split(' '); });
    function filtrer() {
      var mots = n(q.value).split(' ').filter(Boolean), vus = 0;
      cartes.forEach(function (c) { var v = mots.every(function (m) { return ok(m, c._m); }); c._v = v; c.style.display = v ? '' : 'none'; if (v) vus++; });
      groupes.forEach(function (g) { var l = [].slice.call(g.querySelectorAll(q.dataset.live)); g.style.display = (!l.length || l.some(function (c) { return c._v; })) ? '' : 'none'; });
      if (rien) rien.hidden = vus > 0 || !cartes.length;
    }
    q.addEventListener('input', filtrer);
    var f = q.form;
    if (f && q.dataset.live) f.addEventListener('submit', function (e) { if (cartes.length) { e.preventDefault(); filtrer(); q.blur(); } });
  }
  function go() { [].forEach.call(document.querySelectorAll('input[data-live]'), brancher); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', go); else go();
})();

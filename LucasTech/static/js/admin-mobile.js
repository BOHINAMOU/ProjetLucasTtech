/* Lantante Technologie — administration : menu latéral en tiroir sur mobile/tablette.
   Sous 992 px : fermé par défaut, par-dessus le contenu, fermeture par ✕, fond ou Échap. */
(function () {
  'use strict';
  var BP = 992;
  var body = document.body;
  var mobile = function () { return window.innerWidth < BP; };

  function setOpen(open) {
    body.classList.toggle('sidebar-open', open);
    body.classList.toggle('sidebar-collapse', !open);
    var t = document.querySelector('[data-lte-toggle="sidebar"]');
    if (t) t.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  function close() { if (mobile() && body.classList.contains('sidebar-open')) setOpen(false); }

  function init() {
    var sidebar = document.getElementById('jazzy-sidebar');
    if (!sidebar) return;

    // Fermé par défaut sur mobile et tablette
    if (mobile()) setOpen(false);

    // Fond sombre derrière le tiroir
    var backdrop = document.createElement('div');
    backdrop.className = 'lt-backdrop';
    backdrop.setAttribute('aria-hidden', 'true');
    backdrop.addEventListener('click', close);
    body.appendChild(backdrop);

    // Bouton ✕ dans l'en-tête du menu
    var brand = sidebar.querySelector('.sidebar-brand');
    if (brand && !brand.querySelector('.lt-sidebar-close')) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'lt-sidebar-close';
      btn.setAttribute('aria-label', 'Fermer le menu');
      btn.innerHTML = '<i class="fas fa-times" aria-hidden="true"></i>';
      btn.addEventListener('click', function (e) { e.preventDefault(); setOpen(false); });
      brand.appendChild(btn);
    }

    var toggle = document.querySelector('[data-lte-toggle="sidebar"]');
    if (toggle) {
      toggle.setAttribute('aria-label', 'Ouvrir ou fermer le menu');
      toggle.setAttribute('aria-controls', 'jazzy-sidebar');
    }

    // Échap ferme le menu
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' || e.key === 'Esc') close();
    });

    // Un clic sur un lien du menu ferme le tiroir sur mobile
    sidebar.addEventListener('click', function (e) {
      if (e.target.closest && e.target.closest('a.nav-link[href]:not([href="#"])')) close();
    });

    // Passage d'une grande à une petite largeur : on referme
    var wasMobile = mobile();
    window.addEventListener('resize', function () {
      var m = mobile();
      if (m && !wasMobile) setOpen(false);
      wasMobile = m;
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

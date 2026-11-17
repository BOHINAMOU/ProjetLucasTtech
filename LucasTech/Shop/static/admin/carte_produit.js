/* Carte de l'emplacement du produit (Leaflet + OpenStreetMap, sans clé).
   Recherche de lieu avec suggestions (proxy du site), clic ou repère déplaçable, « Ma position » ;
   l'adresse du point choisi s'affiche sous la carte. */
(function () {
  var API = '/api/mobile/v1/lieux/';
  function init() {
    var lat = document.getElementById('id_retrait_latitude') || document.getElementById('id_latitude');
    var lng = document.getElementById('id_retrait_longitude') || document.getElementById('id_longitude');
    if (!lat || !lng || !window.L) return;
    var bloc = document.createElement('div');
    bloc.style.margin = '8px 0 16px';
    bloc.innerHTML =
      '<div style="position:relative;max-width:820px">' +
      '<div id="carte-produit" style="height:360px;border-radius:12px;border:1px solid #ccd"></div>' +
      '<div style="position:absolute;top:10px;left:10px;right:10px;z-index:1000;display:flex;gap:6px">' +
      '<div style="flex:1;position:relative"><input type="text" id="carte-recherche" placeholder="Rechercher un lieu" autocomplete="off" ' +
      'style="width:100%;padding:9px 12px;border-radius:10px;border:1px solid #ccd;box-shadow:0 2px 8px rgba(0,0,0,.15)">' +
      '<div id="carte-sugg" style="display:none;position:absolute;left:0;right:0;top:42px;background:#fff;border-radius:10px;' +
      'box-shadow:0 6px 18px rgba(0,0,0,.18);overflow:hidden"></div></div>' +
      '<button type="button" id="carte-moi" class="button" style="border-radius:10px">Ma position</button></div></div>' +
      '<div id="carte-adresse" style="margin-top:6px;color:#2f3b35;font-weight:600"></div>';
    var ligne = lat.closest('.form-row') || lat.closest('.form-group') || lat.parentNode;
    ligne.parentNode.insertBefore(bloc, ligne);
    var depart = [parseFloat(lat.value) || 6.1753, parseFloat(lng.value) || 1.2128];
    var carte = L.map('carte-produit').setView(depart, lat.value ? 15 : 12);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
      maxZoom: 19, subdomains: 'abcd', attribution: '&copy; OpenStreetMap &copy; CARTO'
    }).addTo(carte);
    var repere = L.marker(depart, {draggable: true}).addTo(carte);
    var adresse = document.getElementById('carte-adresse');
    function nommer(p) {
      fetch(API + 'inverse/?lat=' + p.lat + '&lng=' + p.lng).then(function (r) { return r.json(); })
        .then(function (d) { adresse.textContent = d.nom ? '📍 ' + d.nom : ''; }).catch(function () {});
    }
    function poser(p, nom) {
      repere.setLatLng(p);
      lat.value = p.lat.toFixed(6);
      lng.value = p.lng.toFixed(6);
      if (nom) adresse.textContent = '📍 ' + nom; else nommer(p);
    }
    if (!lat.value) poser(L.latLng(depart)); else nommer(L.latLng(depart));
    carte.on('click', function (e) { poser(e.latlng); });
    repere.on('dragend', function () { poser(repere.getLatLng()); });
    document.getElementById('carte-moi').onclick = function () {
      if (!navigator.geolocation) return;
      navigator.geolocation.getCurrentPosition(function (pos) {
        var p = L.latLng(pos.coords.latitude, pos.coords.longitude);
        poser(p); carte.setView(p, 16);
      });
    };
    var champ = document.getElementById('carte-recherche'), sugg = document.getElementById('carte-sugg'), t = null;
    champ.addEventListener('keydown', function (e) { if (e.key === 'Enter') e.preventDefault(); });
    champ.addEventListener('input', function () {
      clearTimeout(t);
      var q = champ.value.trim();
      if (q.length < 2) { sugg.style.display = 'none'; return; }
      t = setTimeout(function () {
        fetch(API + '?q=' + encodeURIComponent(q)).then(function (r) { return r.json(); }).then(function (d) {
          var res = d.resultats || [];
          sugg.innerHTML = res.length ? '' : '<div style="padding:10px 12px;color:#777">Aucun lieu trouvé</div>';
          res.forEach(function (x) {
            var a = document.createElement('div');
            a.textContent = x.nom;
            a.style.cssText = 'padding:10px 12px;cursor:pointer;border-top:1px solid #f0f2f1';
            a.onmouseenter = function () { a.style.background = '#eef6f1'; };
            a.onmouseleave = function () { a.style.background = ''; };
            a.onclick = function () {
              var p = L.latLng(x.lat, x.lng);
              poser(p, x.nom); carte.setView(p, 16); sugg.style.display = 'none'; champ.value = x.nom;
            };
            sugg.appendChild(a);
          });
          sugg.style.display = 'block';
        }).catch(function () {});
      }, 400);
    });
    setTimeout(function () { carte.invalidateSize(); }, 300);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();

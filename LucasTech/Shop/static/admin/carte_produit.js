/* Carte de l'emplacement du produit (Leaflet + OpenStreetMap, sans clé).
   Clic ou déplacement du repère = latitude / longitude remplies. */
(function () {
  function init() {
    var lat = document.getElementById('id_retrait_latitude');
    var lng = document.getElementById('id_retrait_longitude');
    if (!lat || !lng || !window.L) return;
    var bloc = document.createElement('div');
    bloc.style.margin = '8px 0 16px';
    bloc.innerHTML =
      '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px">' +
      '<input type="text" id="carte-recherche" placeholder="Rechercher une adresse" style="flex:1;min-width:180px;padding:6px">' +
      '<button type="button" id="carte-chercher" class="button">Chercher</button>' +
      '<button type="button" id="carte-moi" class="button">Ma position</button></div>' +
      '<div id="carte-produit" style="height:320px;border-radius:10px;border:1px solid #ccd"></div>';
    var ligne = lat.closest('.form-row') || lat.closest('.form-group') || lat.parentNode;
    ligne.parentNode.insertBefore(bloc, ligne);
    var depart = [parseFloat(lat.value) || 6.1753, parseFloat(lng.value) || 1.2128];
    var carte = L.map('carte-produit').setView(depart, lat.value ? 15 : 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; OpenStreetMap'
    }).addTo(carte);
    var repere = L.marker(depart, {draggable: true}).addTo(carte);
    function poser(p) {
      repere.setLatLng(p);
      lat.value = p.lat.toFixed(6);
      lng.value = p.lng.toFixed(6);
    }
    if (!lat.value) poser(L.latLng(depart));
    carte.on('click', function (e) { poser(e.latlng); });
    repere.on('dragend', function () { poser(repere.getLatLng()); });
    document.getElementById('carte-moi').onclick = function () {
      if (!navigator.geolocation) return;
      navigator.geolocation.getCurrentPosition(function (pos) {
        var p = L.latLng(pos.coords.latitude, pos.coords.longitude);
        poser(p); carte.setView(p, 16);
      });
    };
    function chercher() {
      var q = document.getElementById('carte-recherche').value.trim();
      if (!q) return;
      fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=tg,bj,ci,bf,ne,sn,ml&q=' +
            encodeURIComponent(q))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d[0]) { var p = L.latLng(+d[0].lat, +d[0].lon); poser(p); carte.setView(p, 16); }
        });
    }
    document.getElementById('carte-chercher').onclick = chercher;
    document.getElementById('carte-recherche').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); chercher(); }
    });
    setTimeout(function () { carte.invalidateSize(); }, 300);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();

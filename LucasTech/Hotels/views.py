from django.db.models import F
from django.shortcuts import get_object_or_404, render

from .api import contact, message_reservation
from .models import CODES, Hotel


ICONES = {'wifi': 'fa-wifi', 'clim': 'fa-snowflake', 'parking': 'fa-square-parking', 'piscine': 'fa-person-swimming',
          'restaurant': 'fa-utensils', 'petit_dejeuner': 'fa-mug-hot', 'tv': 'fa-tv', 'eau_chaude': 'fa-shower',
          'groupe': 'fa-bolt', 'securite': 'fa-shield-halved', 'salle_sport': 'fa-dumbbell', 'navette': 'fa-van-shuttle',
          'salle_reunion': 'fa-people-group', 'bar': 'fa-martini-glass', 'plage': 'fa-umbrella-beach'}


def itineraire(h):
    from urllib.parse import quote
    if h.latitude is not None and h.longitude is not None:
        return f"https://www.google.com/maps/dir/?api=1&destination={h.latitude},{h.longitude}"
    return "https://www.google.com/maps/dir/?api=1&destination=" + quote(f"{h.nom}, {h.adresse or h.ville}, Togo")


def liste(request):
    qs = Hotel.objects.filter(actif=True).prefetch_related('chambres')
    q = (request.GET.get('q') or '').strip()
    if q:
        from api_mobile.recherche import filtrer
        qs = filtrer(qs, q, 'nom', 'ville', 'quartier', 'adresse', alias='alias')
    ville = request.GET.get('ville') or ''
    if ville:
        qs = qs.filter(ville__iexact=ville)
    villes = sorted({h.ville for h in Hotel.objects.filter(actif=True) if h.ville}, key=str.lower)
    return render(request, 'hotels/liste.html', {'hotels': qs, 'q': q, 'ville': ville, 'villes': villes})


def detail(request, slug):
    h = get_object_or_404(Hotel.objects.filter(actif=True).prefetch_related('photos', 'chambres__photos'), slug=slug)
    Hotel.objects.filter(pk=h.pk).update(vues=F('vues') + 1)
    wa, tel = contact(h)
    url = request.build_absolute_uri(h.get_absolute_url())
    chambres = [c for c in h.chambres.all() if c.actif]
    for c in chambres:
        c.message = message_reservation(h, c, url)
        c.equip = [CODES[e] for e in (c.equipements or []) if e in CODES]
    return render(request, 'hotels/detail.html', {
        'h': h, 'wa': wa, 'tel': tel, 'chambres': chambres,
        'equip': [(ICONES.get(e, 'fa-check'), CODES[e]) for e in (h.equipements or []) if e in CODES],
        'itineraire': itineraire(h),
        'message': message_reservation(h, lien=url),
    })

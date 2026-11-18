from django.db.models import F
from django.shortcuts import get_object_or_404, render

from .api import contact
from .models import CODES, Hotel


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
        c.message = f"Bonjour, je souhaite réserver : {c.nom} — {h.nom}. Dates : … Nombre de personnes : …\n{url}"
        c.equip = [CODES[e] for e in (c.equipements or []) if e in CODES]
    return render(request, 'hotels/detail.html', {
        'h': h, 'wa': wa, 'tel': tel, 'chambres': chambres,
        'equip': [CODES[e] for e in (h.equipements or []) if e in CODES],
        'message': f"Bonjour, je souhaite réserver : {h.nom}. Dates : … Nombre de personnes : …\n{url}",
    })

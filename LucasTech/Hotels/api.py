"""Hôtels dans l'appli : liste (recherche nom / ville / localité, filtre ville), fiche, chambre, clics."""
from django.db.models import F
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api_mobile.catalog import grande, public_cache, text, vignette
from api_mobile.utils import error

from .models import CODES, Chambre, Hotel


def _wa(t):
    d = ''.join(c for c in (t or '') if c.isdigit())
    if len(d) == 8:
        d = '228' + d
    return d if len(d) >= 11 else ''


def contact(h):
    """WhatsApp et téléphone de l'hôtel ; à défaut, notre WhatsApp principal."""
    from api_mobile.catalog import _whatsapp_lantante
    wa = _wa(h.whatsapp) or _wa(h.telephone if not h.whatsapp else '') or _wa(_whatsapp_lantante())
    tel = h.telephone or ('+' + wa if wa else '')
    return wa, tel


def _equip(codes):
    return [{'code': c, 'nom': CODES[c]} for c in (codes or []) if c in CODES]


def actifs():
    return Hotel.objects.filter(actif=True).prefetch_related('chambres')


def item(request, h):
    return {'id': h.pk, 'slug': h.slug, 'nom': h.nom, 'ville': h.ville, 'quartier': h.quartier,
            'etoiles': h.etoiles, 'a_partir_de': h.a_partir_de,
            'photo': vignette(request, h.photo) if h.photo else None}


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(60)
def liste(request):
    qs = actifs()
    tous = list(qs)
    q = (request.GET.get('q') or '').strip()
    if q:
        from api_mobile.recherche import filtrer
        qs = filtrer(qs, q, 'nom', 'ville', 'quartier', 'adresse', alias='alias')
    if request.GET.get('ville'):
        qs = qs.filter(ville__iexact=request.GET['ville'])
    villes = sorted({h.ville for h in tous if h.ville}, key=str.lower)
    return Response({'resultats': [item(request, h) for h in qs], 'villes': villes})


def _chambre(request, c, h, courte=True):
    photos = [grande(request, p.image) for p in c.photos.all()]
    d = {'id': c.pk, 'nom': c.nom, 'prix_nuit': c.prix_nuit, 'capacite': c.capacite,
         'photo': photos[0] if photos else None, 'resume': (c.description or '')[:140]}
    if not courte:
        wa, tel = contact(h)
        d.update({'photos': photos, 'description': text(c.description), 'equipements': _equip(c.equipements),
                  'hotel': {'slug': h.slug, 'nom': h.nom}, 'whatsapp': wa, 'telephone': tel,
                  'url': h.get_absolute_url()})
    return d


@api_view(['GET'])
@permission_classes([AllowAny])
def detail(request, slug):
    h = actifs().filter(slug=slug).first()
    if not h:
        return error("Hôtel introuvable.", 404, code='introuvable')
    Hotel.objects.filter(pk=h.pk).update(vues=F('vues') + 1)
    wa, tel = contact(h)
    chambres = [c for c in h.chambres.all() if c.actif]
    # bandeau : photo principale, photos de l'hôtel, puis photos des chambres (nom en légende)
    bande = []
    if h.photo:
        bande.append({'image': grande(request, h.photo), 'legende': ''})
    bande += [{'image': grande(request, p.image), 'legende': p.legende} for p in h.photos.all()]
    for c in chambres:
        for p in c.photos.all()[:2]:
            bande.append({'image': grande(request, p.image), 'legende': c.nom})
    d = item(request, h)
    d.update({'description': text(h.description), 'adresse': h.adresse,
              'latitude': float(h.latitude) if h.latitude is not None else None,
              'longitude': float(h.longitude) if h.longitude is not None else None,
              'equipements': _equip(h.equipements), 'bande': bande, 'site_web': h.site_web,
              'whatsapp': wa, 'telephone': tel,
              'message_whatsapp': (f"Bonjour, je souhaite réserver : {h.nom}. Dates : … Nombre de personnes : …\n"
                                   + request.build_absolute_uri(h.get_absolute_url())),
              'url': request.build_absolute_uri(h.get_absolute_url()),
              'chambres': [_chambre(request, c, h) for c in chambres]})
    return Response(d)


@api_view(['GET'])
@permission_classes([AllowAny])
def chambre(request, pk):
    c = Chambre.objects.filter(pk=pk, actif=True, hotel__actif=True).select_related('hotel').first()
    if not c:
        return error("Chambre introuvable.", 404, code='introuvable')
    Chambre.objects.filter(pk=pk).update(vues=F('vues') + 1)
    d = _chambre(request, c, c.hotel, courte=False)
    d['url'] = request.build_absolute_uri(c.hotel.get_absolute_url())
    d['message_whatsapp'] = (f"Bonjour, je souhaite réserver : {c.nom} — {c.hotel.nom}. "
                             f"Dates : … Nombre de personnes : …\n{d['url']}")
    return Response(d)


@api_view(['POST'])
@permission_classes([AllowAny])
def clic(request, slug, sorte):
    champ = {'reserver': 'clics_reserver', 'appel': 'clics_appel'}.get(sorte)
    if not champ:
        return error("Inconnu.", 404, code='introuvable')
    Hotel.objects.filter(slug=slug).update(**{champ: F(champ) + 1})
    return Response({'ok': True})

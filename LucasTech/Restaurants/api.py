"""Restaurants dans l'appli : liste, fiche (carrousel, plats, options), clic « Commander »."""
from urllib.parse import quote

from django.db.models import F, Prefetch
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api_mobile.catalog import grande, public_cache, text, vignette
from api_mobile.utils import error, media

from .models import GroupeOptions, Plat, Restaurant


def whatsapp(r):
    from api_mobile.catalog import _wa_valide, _whatsapp_lantante
    return _wa_valide(r.whatsapp) or _wa_valide(_whatsapp_lantante())


def itineraire(r):
    if r.latitude is not None and r.longitude is not None:
        return f"https://www.google.com/maps/dir/?api=1&destination={r.latitude},{r.longitude}"
    return "https://www.google.com/maps/dir/?api=1&destination=" + quote(f"{r.nom}, {r.adresse or r.lieu}, Togo")


def visibles():
    return Restaurant.objects.filter(visible=True)


def item(request, r):
    img = r.logo or r.couverture
    return {'id': r.pk, 'slug': r.slug, 'nom': r.nom, 'description': text(r.description)[:160],
            'quartier': r.quartier, 'ville': r.ville, 'lieu': r.lieu,
            'logo': media(request, r.logo) if r.logo else None,
            'image': vignette(request, r.couverture) if r.couverture else (media(request, img) if img else None)}


def plat_dict(request, p, groupes_resto):
    photos = [grande(request, p.image)] if p.image else []
    photos += [grande(request, x.image) for x in p.photos.all()]
    groupes = list(p.groupes_options.all()) + groupes_resto
    return {'id': p.pk, 'nom': p.nom, 'description': text(p.description), 'prix': p.prix,
            'categorie': p.categorie.nom if p.categorie_id else '', 'image': vignette(request, p.image) if p.image else None,
            'photos': photos, 'groupes': [g.as_dict() for g in groupes]}


def fiche(request, r):
    groupes_resto = list(r.groupes_options.filter(plat__isnull=True))
    plats = r.plats.filter(disponible=True).select_related('categorie').prefetch_related('photos', 'groupes_options')
    d = item(request, r)
    d.update({
        'description': text(r.description), 'adresse': r.adresse, 'horaires': r.horaires, 'livraison': r.livraison,
        'telephone': r.telephone, 'whatsapp': whatsapp(r), 'itineraire': itineraire(r),
        'latitude': float(r.latitude) if r.latitude is not None else None,
        'longitude': float(r.longitude) if r.longitude is not None else None,
        'carrousel': [{'image': grande(request, ph.image), 'legende': ph.legende} for ph in r.photos.all()]
                     or ([{'image': grande(request, r.couverture), 'legende': ''}] if r.couverture else []),
        'plats': [plat_dict(request, p, groupes_resto) for p in plats],
        'url': request.build_absolute_uri(r.get_absolute_url()),
    })
    return d


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(60)
def liste(request):
    qs = visibles()
    q = (request.GET.get('q') or '').strip()
    if q:
        from api_mobile.recherche import filtrer
        qs = filtrer(qs, q, 'nom', 'quartier', 'ville', 'plats__nom')
    from api_mobile.catalog import _wa_valide, _whatsapp_lantante
    return Response({'resultats': [item(request, r) for r in qs.distinct()[:200]],
                     'whatsapp_lantante': _wa_valide(_whatsapp_lantante())})


@api_view(['GET'])
@permission_classes([AllowAny])
def detail(request, slug):
    r = visibles().filter(slug=slug).prefetch_related(
        'photos', Prefetch('groupes_options', queryset=GroupeOptions.objects.all())).first()
    if not r:
        return error("Ce restaurant n'est pas disponible.", 404, code='introuvable')
    Restaurant.objects.filter(pk=r.pk).update(vues=F('vues') + 1)
    return Response(fiche(request, r))


@api_view(['POST'])
@permission_classes([AllowAny])
def clic(request, slug):
    Restaurant.objects.filter(slug=slug).update(clics_commander=F('clics_commander') + 1)
    return Response({'ok': True})


__all__ = ['Plat']

"""Logements dans l'appli : liste (recherche ville / quartier / type, fautes et accents tolérés, filtres), fiche, clics."""
from urllib.parse import quote

from django.db.models import F
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api_mobile.catalog import grande, public_cache, text, vignette
from api_mobile.utils import error

from .models import CODES, TYPES, Logement


def notre_whatsapp():
    from api_mobile.catalog import _wa_valide, _whatsapp_lantante
    return _wa_valide(_whatsapp_lantante())


def disponibles():
    return Logement.objects.filter(loue=False).prefetch_related('photos')


def recherche(qs, q):
    """Ville, quartier, type, repère, mots-clés : accents, majuscules, fautes et mots partiels tolérés."""
    from api_mobile.recherche import filtrer
    return filtrer(qs, q, 'quartier', 'ville', 'texte_recherche', alias='alias')


def filtres(qs, g):
    if g.get('ville'):
        qs = qs.filter(ville__iexact=g['ville'])
    if g.get('type'):
        qs = qs.filter(type=g['type'])
    if (g.get('prix_max') or '').isdigit():
        qs = qs.filter(loyer__lte=int(g['prix_max']))
    if g.get('meuble') in ('1', 'oui', 'true'):
        qs = qs.filter(meuble=True)
    elif g.get('meuble') in ('0', 'non', 'false'):
        qs = qs.filter(meuble=False)
    return qs


def itineraire(l):
    if l.latitude is not None and l.longitude is not None:
        return f"https://www.google.com/maps/dir/?api=1&destination={l.latitude},{l.longitude}"
    return "https://www.google.com/maps/dir/?api=1&destination=" + quote(f"{l.quartier}, {l.ville}, Togo")


def message(l, lien=''):
    lignes = ["Bonjour, je suis intéressé(e) par ce logement.",
              f"Type : {l.get_type_display()}",
              f"Quartier : {l.quartier} ({l.ville})",
              f"Loyer : {l.loyer:,} CFA {l.get_periode_display()}".replace(',', ' ')]
    if lien:
        lignes.append(f"Lien : {lien}")
    return "\n".join(lignes)


def item(request, l):
    photo = l.photos.all()[:1]
    return {'id': l.pk, 'nom': l.nom, 'type': l.type, 'type_libelle': l.get_type_display(), 'ville': l.ville,
            'quartier': l.quartier, 'loyer': l.loyer, 'periode': l.periode, 'periode_libelle': l.get_periode_display(),
            'pieces': l.pieces, 'meuble': l.meuble,
            'photo': vignette(request, photo[0].image) if photo else None}


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(60)
def liste(request):
    qs = filtres(disponibles(), request.GET)
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = recherche(qs, q)
    tous = Logement.objects.filter(loue=False)
    villes = sorted(set(tous.values_list('ville', flat=True)), key=str.lower)
    types_presents = set(tous.values_list('type', flat=True))
    return Response({'resultats': [item(request, l) for l in qs[:200]], 'villes': villes,
                     'types': [{'code': c, 'nom': n} for c, n in TYPES if c in types_presents]})


@api_view(['GET'])
@permission_classes([AllowAny])
def detail(request, pk):
    l = disponibles().filter(pk=pk).first()
    if not l:
        return error("Ce logement n'est plus disponible.", 404, code='introuvable')
    Logement.objects.filter(pk=pk).update(vues=F('vues') + 1)
    url = request.build_absolute_uri(l.get_absolute_url())
    wa = notre_whatsapp()
    d = item(request, l)
    d.update({
        'photos': [grande(request, p.image) for p in l.photos.all()],
        'repere': l.repere, 'caution': l.caution, 'description': text(l.description),
        'eau': l.get_compteur_eau_display() if l.compteur_eau else '',
        'electricite': l.get_compteur_electricite_display() if l.compteur_electricite else '',
        'equipements': [{'code': c, 'nom': CODES[c]} for c in (l.equipements or []) if c in CODES],
        'disponible_le': l.disponible_le.isoformat() if l.disponible_le else None,
        'latitude': float(l.latitude) if l.latitude is not None else None,
        'longitude': float(l.longitude) if l.longitude is not None else None,
        'itineraire': itineraire(l), 'whatsapp': wa, 'telephone': ('+' + wa) if wa else '',
        'message_whatsapp': message(l, url), 'url': url,
    })
    return Response(d)


@api_view(['POST'])
@permission_classes([AllowAny])
def clic(request, pk):
    Logement.objects.filter(pk=pk).update(contacts=F('contacts') + 1)
    return Response({'ok': True})

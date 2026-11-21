"""Recherche de lieux et adresse d'un point (cartes de livraison et d'emplacement des produits).

Proxy vers Photon (photon.komoot.io, données OpenStreetMap) : priorité au Togo, français, cache, limite de débit.
Données © OpenStreetMap (attribution affichée sous les cartes)."""
import hashlib
import logging

import requests
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .utils import error

logger = logging.getLogger(__name__)
PHOTON = 'https://photon.komoot.io'
BBOX_TOGO = '-0.15,6.05,1.85,11.15'  # ouest, sud, est, nord
UA = {'User-Agent': 'LantanteTechnologie/1.0 (+https://lantantetechnologie.com)'}
CACHE = 60 * 60 * 24 * 7
LIMITE = 40  # requêtes par minute et par adresse IP


def _trop(request):
    ip = __import__('core.ip', fromlist=['ip_client']).ip_client(request)
    cle = f'lieux:debit:{ip}'
    n = cache.get(cle, 0) + 1
    cache.set(cle, n, 60)
    return n > LIMITE


def _libelle(p):
    """Nom lisible : « Université de Lomé, Lomé » / « Rue 123, Bè, Lomé »."""
    morceaux = []
    for k in ('name', 'street', 'district', 'locality', 'city', 'county', 'state'):
        v = (p.get(k) or '').strip()
        if k == 'street' and v and p.get('housenumber'):
            v = f"{p['housenumber']} {v}"
        if v and v not in morceaux:
            morceaux.append(v)
    if p.get('country') and p.get('countrycode', '').upper() != 'TG':
        morceaux.append(p['country'])
    return ', '.join(morceaux[:4])


def _resultats(data):
    out = []
    for f in (data or {}).get('features', []):
        lng, lat = (f.get('geometry') or {}).get('coordinates', [None, None])[:2]
        if lat is None:
            continue
        nom = _libelle(f.get('properties') or {})
        if nom:
            out.append({'nom': nom, 'lat': round(float(lat), 6), 'lng': round(float(lng), 6)})
    return out


def _photon(chemin, params):
    cle = 'lieux:' + hashlib.sha1(f'{chemin}|{sorted(params.items())}'.encode()).hexdigest()
    deja = cache.get(cle)
    if deja is not None:
        return deja
    r = requests.get(PHOTON + chemin, params=params, headers=UA, timeout=8)
    r.raise_for_status()
    out = _resultats(r.json())
    cache.set(cle, out, CACHE)
    return out


def _google(q, lat=None, lng=None):
    """Recherche Google Places (Text Search) si GOOGLE_MAPS_KEY est configurée, sinon None."""
    from courses.carto import cle_google
    cle = cle_google()
    if not cle:
        return None
    k = 'lieuxg:' + hashlib.sha1(f'{q}|{lat}|{lng}'.encode()).hexdigest()
    deja = cache.get(k)
    if deja is not None:
        return deja
    corps = {'textQuery': q, 'languageCode': 'fr', 'regionCode': 'TG', 'pageSize': 6}
    if lat is not None and lng is not None:
        corps['locationBias'] = {'circle': {'center': {'latitude': lat, 'longitude': lng}, 'radius': 30000.0}}
    try:
        r = requests.post('https://places.googleapis.com/v1/places:searchText', json=corps, timeout=8, headers={
            'X-Goog-Api-Key': cle,
            'X-Goog-FieldMask': 'places.displayName,places.formattedAddress,places.location'})
        r.raise_for_status()
        out = []
        for p in r.json().get('places', []):
            loc = p.get('location') or {}
            nom = (p.get('displayName') or {}).get('text', '')
            adresse = p.get('formattedAddress', '')
            if loc.get('latitude') is None:
                continue
            libelle = nom if not adresse or adresse.startswith(nom) else f"{nom}, {adresse}"
            out.append({'nom': (libelle or adresse)[:160], 'lat': round(loc['latitude'], 6), 'lng': round(loc['longitude'], 6)})
        cache.set(k, out, CACHE)
        return out
    except Exception:  # pragma: no cover - réseau
        logger.warning("Google Places indisponible : OpenStreetMap utilisé")
        return None


def _float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@api_view(['GET'])
@permission_classes([AllowAny])
def lieux(request):
    """?q=texte → suggestions (Togo d'abord)."""
    q = (request.GET.get('q') or '').strip()[:120]
    if len(q) < 2:
        return Response({'resultats': []})
    if _trop(request):
        return error("Trop de recherches. Réessayez dans un instant.", 429, code='trop')
    try:
        g = _google(q, _float(request.GET.get('lat')), _float(request.GET.get('lng')))
        if g is not None:
            return Response({'resultats': g})
        params = {'q': q, 'lang': 'fr', 'limit': 6, 'bbox': BBOX_TOGO}
        if _float(request.GET.get('lat')) is not None and _float(request.GET.get('lng')) is not None:
            params.update({'lat': request.GET['lat'], 'lon': request.GET['lng']})
        res = _photon('/api/', params)
        if not res:  # rien au Togo : recherche plus large, autour de Lomé
            res = _photon('/api/', {'q': q, 'lang': 'fr', 'limit': 6, 'lat': 6.17, 'lon': 1.23})
    except (requests.RequestException, ValueError):
        logger.warning("Recherche de lieux indisponible")
        return error("Recherche indisponible pour le moment.", 503, code='indisponible')
    return Response({'resultats': res})


@api_view(['GET'])
@permission_classes([AllowAny])
def lieu_inverse(request):
    """?lat=&lng= → nom du lieu (adresse affichée sous la carte)."""
    try:
        lat, lng = round(float(request.GET.get('lat')), 5), round(float(request.GET.get('lng')), 5)
    except (TypeError, ValueError):
        return error("Position invalide.", 400, code='donnees_invalides')
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return error("Position invalide.", 400, code='donnees_invalides')
    if _trop(request):
        return error("Trop de recherches. Réessayez dans un instant.", 429, code='trop')
    try:
        res = _photon('/reverse', {'lat': lat, 'lon': lng, 'lang': 'fr', 'limit': 1})
    except (requests.RequestException, ValueError):
        return Response({'nom': ''})
    return Response({'nom': res[0]['nom'] if res else ''})

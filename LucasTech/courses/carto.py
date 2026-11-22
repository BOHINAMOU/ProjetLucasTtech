"""Itinéraire routier : Google Routes API si la clé GOOGLE_MAPS_KEY est dans le .env du serveur (la clé ne quitte
jamais le serveur), sinon estimation (vol d'oiseau × coefficient, vitesse moyenne). Le passage à Google ne demande
que d'ajouter la clé : rien à changer dans l'appli."""
import hashlib
import logging
import os

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)
ROUTES = 'https://routes.googleapis.com/directions/v2:computeRoutes'


def cle_google():
    return getattr(settings, 'GOOGLE_MAPS_KEY', '') or os.getenv('GOOGLE_MAPS_KEY', '')


def decoder_polyline(code):
    """Polyline encodée Google → [[lat, lng], …]."""
    points, i, lat, lng = [], 0, 0, 0
    while i < len(code):
        for axe in (0, 1):
            res, dec = 0, 0
            while True:
                b = ord(code[i]) - 63
                i += 1
                res |= (b & 0x1f) << dec
                dec += 5
                if b < 0x20:
                    break
            delta = ~(res >> 1) if res & 1 else res >> 1
            if axe == 0:
                lat += delta
            else:
                lng += delta
        points.append([round(lat / 1e5, 6), round(lng / 1e5, 6)])
    return points


def itineraire_google(dlat, dlng, alat, alng):
    """(km, minutes, trace) par la route, ou None (pas de clé, erreur, pas de route)."""
    cle = cle_google()
    if not cle:
        return None
    k = 'itin:' + hashlib.sha1(f'{dlat:.4f},{dlng:.4f},{alat:.4f},{alng:.4f}'.encode()).hexdigest()
    deja = cache.get(k)
    if deja:
        return deja
    corps = {
        'origin': {'location': {'latLng': {'latitude': dlat, 'longitude': dlng}}},
        'destination': {'location': {'latLng': {'latitude': alat, 'longitude': alng}}},
        'travelMode': 'DRIVE', 'routingPreference': 'TRAFFIC_AWARE', 'languageCode': 'fr', 'units': 'METRIC',
    }
    try:
        r = requests.post(ROUTES, json=corps, timeout=8, headers={
            'X-Goog-Api-Key': cle,
            'X-Goog-FieldMask': 'routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline'})
        r.raise_for_status()
        route = (r.json().get('routes') or [None])[0]
        if not route:
            return None
        km = round(route.get('distanceMeters', 0) / 1000, 2)
        minutes = max(1, -(-int(str(route.get('duration', '60s')).rstrip('s') or 60) // 60))
        trace = decoder_polyline(route.get('polyline', {}).get('encodedPolyline', ''))
        res = (km, minutes, trace)
        cache.set(k, res, 60 * 30)
        return res
    except Exception:  # pragma: no cover - réseau
        logger.warning("Google Routes indisponible : estimation utilisée")
        return None



OSRM = 'https://router.project-osrm.org/route/v1/driving/{dlng},{dlat};{alng},{alat}?overview=full&geometries=polyline'


def trace_route(dlat, dlng, alat, alng):
    """Tracé (liste [lat, lng]) + km + minutes pour afficher le chemin sur la carte pendant une course.
    Google Routes si la clé existe, sinon OSRM (gratuit, sans clé), sinon None. Mis en cache 2 min."""
    g = itineraire_google(dlat, dlng, alat, alng)
    if g and g[2]:
        return {'km': g[0], 'minutes': g[1], 'trace': g[2]}
    k = 'osrm:' + hashlib.sha1(f'{dlat:.4f},{dlng:.4f},{alat:.4f},{alng:.4f}'.encode()).hexdigest()
    deja = cache.get(k)
    if deja:
        return deja
    try:
        r = requests.get(OSRM.format(dlat=dlat, dlng=dlng, alat=alat, alng=alng), timeout=5,
                         headers={'User-Agent': 'LantanteExpress/1.0'})
        r.raise_for_status()
        route = (r.json().get('routes') or [None])[0]
        if not route:
            return None
        res = {'km': round(route.get('distance', 0) / 1000, 2), 'minutes': max(1, round(route.get('duration', 60) / 60)),
               'trace': decoder_polyline(route.get('geometry', ''))}
        cache.set(k, res, 120)
        return res
    except Exception:  # pragma: no cover - réseau
        logger.warning("Tracé de route indisponible")
        return None

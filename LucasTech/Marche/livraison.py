"""Frais de livraison d'un produit de vendeur.

Même ville (distance au point de retrait <= rayon) : tarif de base + prix par km.
Autre ville : prix fixe défini par le vendeur sur le produit (vide = ne livre pas hors de sa ville).
"""
import math
import unicodedata

from django.core.exceptions import ValidationError


def haversine(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return ''.join(c for c in s if c.isalnum())


def _arrondi(x):
    return int(math.ceil(x / 50.0) * 50)  # au 50 F supérieur


def _float(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def calculer(produit, ville='', lat=None, lng=None):
    """Retourne {'frais', 'mode', 'detail'}. Lève ValidationError si la livraison est impossible."""
    v = getattr(produit, 'vendeur', None)
    if v is None:
        return {'frais': 0, 'mode': '', 'detail': ''}
    from .models import ReglageLivraison
    r = ReglageLivraison.load()
    lat, lng = _float(lat), _float(lng)
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180 if lng is not None else False):
        lat = lng = None
    plat = produit.retrait_latitude if produit.retrait_latitude is not None else v.latitude
    plng = produit.retrait_longitude if produit.retrait_longitude is not None else v.longitude
    distance = None
    if lat is not None and lng is not None and plat is not None and plng is not None:
        distance = haversine(lat, lng, float(plat), float(plng))
    elif ville and _norm(ville) == _norm(v.ville):
        distance = float(r.distance_defaut_km)
    elif not ville and lat is None:
        raise ValidationError("Indiquez votre position ou votre ville pour la livraison.")
    if distance is not None and distance <= r.rayon_ville_km:
        km = max(1, math.ceil(distance))
        return {'frais': _arrondi(r.tarif_base + km * r.prix_km), 'mode': 'km',
                'detail': f"{km} km depuis {v.ville}"}
    if produit.livraison_autre_ville is None:
        raise ValidationError(f"Ce vendeur livre seulement à {v.ville}.")
    return {'frais': int(produit.livraison_autre_ville), 'mode': 'ville', 'detail': f"Envoi depuis {v.ville}"}

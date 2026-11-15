"""Écoles dans l'appli : liste, fiche (photos qui défilent), filières ; « S'inscrire » ouvre le site de l'école."""
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .catalog import grande, paginated, public_cache, short, text, vignette
from .utils import error, media


def _recent(e):
    from datetime import timedelta
    from django.utils import timezone
    d = getattr(e, 'derniere_nouveaute', None)
    return bool(d and d >= timezone.localdate() - timedelta(days=30))


def ecole_item(request, e):
    from Ecoles.models import CYCLES, lien_inscription
    libelles = dict(CYCLES)
    return {'nouveau': _recent(e), 'cycles': [{'code': c, 'nom': libelles.get(c, c)} for c in (e.cycles or [])],
            'id': e.pk, 'slug': e.slug, 'nom': e.nom, 'titre': e.nom, 'type': e.type, 'type_libelle': e.get_type_display(),
            'ville': e.ville, 'logo': media(request, e.logo),
            'image': media(request, e.couverture or e.logo), 'image_vignette': vignette(request, e.couverture or e.logo),
            'resume': short(e.description), 'lien_inscription': lien_inscription(e)}


def _ecoles():
    from django.db.models import F, Max, Q as Q_
    from Ecoles.models import Ecole
    # les écoles avec une nouveauté récente remontent
    return Ecole.objects.filter(publie=True).annotate(
        derniere_nouveaute=Max('nouveautes__date', filter=Q_(nouveautes__publie=True))
    ).order_by(F('derniere_nouveaute').desc(nulls_last=True), 'ordre', 'nom')


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(120)
def ecoles(request):
    qs = _ecoles()
    t = request.GET.get('type') or request.GET.get('categorie')
    if t:
        qs = qs.filter(type=t)
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(ville__icontains=q) | Q(filieres__nom__icontains=q)).distinct()
    return paginated(request, qs, lambda e: ecole_item(request, e))


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(60)
def ecole(request, slug):
    e = _ecoles().filter(slug=slug).prefetch_related('photos', 'filieres', 'nouveautes').first()
    if not e:
        return error("École introuvable.", 404, code='introuvable')
    d = ecole_item(request, e)
    d.update({
        'description': text(e.description), 'telephone': e.telephone, 'whatsapp': e.whatsapp, 'email': e.email,
        'site_web': e.site_web, 'adresse': e.adresse,
        'photos': [{'image': grande(request, p.image), 'legende': p.legende} for p in e.photos.all()],
        'nouveautes': [{'id': n.pk, 'titre': n.titre, 'texte': n.texte, 'date': n.date.isoformat(),
                        'image': grande(request, n.image) if n.image else None}
                       for n in e.nouveautes.all() if n.publie],
        'filieres': [{'id': f.pk, 'cycle': f.cycle, 'nom': f.nom, 'niveau': f.niveau, 'duree': f.duree, 'frais': f.frais,
                      'image': grande(request, f.image) if f.image else None, 'resume': f.resume or short(f.description),
                      'description': text(f.description), 'debouches': text(f.debouches),
                      'conditions': text(f.conditions)} for f in e.filieres.all()],
    })
    return Response(d)

"""API de l'appli : offres d'emploi (non lues d'abord, expirées masquées), lecture, clics sur les contacts."""
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from api_mobile.catalog import grande, text, vignette
from api_mobile.utils import error

from .models import OffreEmploi, OffreLue


def actives():
    return OffreEmploi.objects.filter(publie=True).filter(
        Q(date_limite__isnull=True) | Q(date_limite__gte=timezone.localdate()))


def _wa(t):
    """Numéro WhatsApp au format wa.me (accepte aussi un lien wa.me collé dans l'admin)."""
    d = ''.join(c for c in (t or '') if c.isdigit())
    if len(d) == 8:
        d = '228' + d
    return d if len(d) >= 11 else ''


def item(request, o, lus=frozenset()):
    return {'id': o.pk, 'titre': o.titre, 'entreprise': o.entreprise, 'ville': o.ville,
            'type': o.type_contrat, 'type_libelle': o.get_type_contrat_display(),
            'image': vignette(request, o.image) if o.image else None,
            'date': o.created_at.isoformat(), 'date_limite': o.date_limite.isoformat() if o.date_limite else None,
            'resume': text(o.description)[:160], 'lu': o.pk in lus, 'exemple': o.est_exemple}


def _lus(request):
    if not request.user.is_authenticated:
        return frozenset()
    return frozenset(OffreLue.objects.filter(user=request.user).values_list('offre_id', flat=True))


@api_view(['GET'])
@permission_classes([AllowAny])
def liste(request):
    from api_mobile.recherche import filtrer
    qs = actives()
    t = request.GET.get('type') or ''
    if t:
        qs = qs.filter(type_contrat=t)
    v = request.GET.get('ville') or ''
    if v:
        qs = qs.filter(ville__iexact=v)
    qs = filtrer(qs, request.GET.get('q'), 'titre', 'entreprise', 'ville', 'description')
    lus = _lus(request)
    offres = list(qs[:200])
    if not request.GET.get('q'):
        offres.sort(key=lambda o: o.pk in lus)  # non lues d'abord (le tri par date est gardé)
    return Response({'resultats': [item(request, o, lus) for o in offres],
                     'non_lues': sum(1 for o in offres if o.pk not in lus) if request.user.is_authenticated else None,
                     'types': [{'code': c, 'nom': n} for c, n in OffreEmploi.TYPES
                               if actives().filter(type_contrat=c).exists()],
                     'villes': sorted({o.ville for o in actives().only('ville') if o.ville})})


@api_view(['GET'])
@permission_classes([AllowAny])
def detail(request, pk):
    o = actives().filter(pk=pk).first()
    if not o:
        return error("Cette offre n'est plus disponible.", 404, code='introuvable')
    OffreEmploi.objects.filter(pk=pk).update(vues=F('vues') + 1)
    d = item(request, o, _lus(request))
    d.update({'image_grande': grande(request, o.image) if o.image else None, 'description': text(o.description),
              'telephone': o.telephone, 'whatsapp': _wa(o.whatsapp), 'email': o.email_contact, 'lien': o.lien,
              'message_whatsapp': f"Bonjour, je suis intéressé(e) par votre offre : {o.titre}.",
              'url': request.build_absolute_uri(o.get_absolute_url())})
    return Response(d)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def lu(request, pk):
    if actives().filter(pk=pk).exists():
        OffreLue.objects.get_or_create(offre_id=pk, user=request.user)
    return Response({'lu': True})


CLICS = {'appel': 'clics_appel', 'whatsapp': 'clics_whatsapp', 'lien': 'clics_lien', 'email': 'clics_email'}


@api_view(['POST'])
@permission_classes([AllowAny])
def clic(request, pk, sorte):
    """L'appli signale un appui sur Appeler / WhatsApp / Postuler / E-mail (statistiques)."""
    champ = CLICS.get(sorte)
    if champ:
        OffreEmploi.objects.filter(pk=pk).update(**{champ: F(champ) + 1})
    return Response({'ok': True})

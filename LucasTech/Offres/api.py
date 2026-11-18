"""API de l'appli : offres d'emploi (non lues d'abord), lecture, candidature, mes candidatures. Jamais de CV ici."""
from django.core.cache import cache
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from api_mobile.catalog import grande, text, vignette
from api_mobile.utils import error

from .models import CandidatureEmploi, OffreEmploi, OffreLue

MAX_CV = 5 * 1024 * 1024
EXT_CV = ('.pdf', '.jpg', '.jpeg', '.png', '.webp', '.doc', '.docx')


def actives():
    return OffreEmploi.objects.filter(publie=True).filter(
        Q(date_limite__isnull=True) | Q(date_limite__gte=timezone.localdate()))


def _chiffres(t):
    return ''.join(c for c in (t or '') if c.isdigit())


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
    deja = request.user.is_authenticated and CandidatureEmploi.objects.filter(offre=o, user=request.user).exists()
    d.update({'image_grande': grande(request, o.image) if o.image else None, 'description': text(o.description),
              'telephone': o.telephone, 'whatsapp': _chiffres(o.whatsapp), 'email': o.email_contact, 'lien': o.lien,
              'postuler': o.candidature_appli, 'deja_postule': deja,
              'url': request.build_absolute_uri(o.get_absolute_url())})
    return Response(d)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def lu(request, pk):
    if actives().filter(pk=pk).exists():
        OffreLue.objects.get_or_create(offre_id=pk, user=request.user)
    return Response({'lu': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def postuler(request, pk):
    o = actives().filter(pk=pk, candidature_appli=True).first()
    if not o:
        return error("Cette offre n'accepte pas de candidature.", 404, code='introuvable')
    if CandidatureEmploi.objects.filter(offre=o, user=request.user).exists():
        return error("Vous avez déjà postulé à cette offre.", 400, code='deja')
    cle = f'postuler:{request.user.pk}'
    if cache.get(cle, 0) >= 10:
        return error("Trop de candidatures aujourd'hui. Réessayez demain.", 429, code='limite')
    d = request.data
    nom = (d.get('nom') or '').strip()[:120]
    tel = (d.get('telephone') or '').strip()
    erreurs = {}
    if not nom:
        erreurs['nom'] = ["Saisissez votre nom."]
    if len(_chiffres(tel)) < 8 or any(c not in '0123456789+ ' for c in tel):
        erreurs['telephone'] = ["Numéro invalide : chiffres uniquement."]
    cv = request.FILES.get('cv')
    if cv and (cv.size > MAX_CV or not cv.name.lower().endswith(EXT_CV)):
        erreurs['cv'] = ["CV : PDF, Word ou image, 5 Mo maximum."]
    if erreurs:
        return Response({'detail': "Vérifiez le formulaire.", 'erreurs': erreurs}, status=400)
    c = CandidatureEmploi.objects.create(offre=o, user=request.user, nom=nom, telephone=tel[:30],
                                         email=(d.get('email') or request.user.email or '').strip()[:254],
                                         message=(d.get('message') or '').strip()[:3000], cv=cv or '')
    cache.set(cle, cache.get(cle, 0) + 1, 86400)
    return Response({'id': c.pk, 'detail': "Candidature envoyée."}, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mes_candidatures(request):
    qs = CandidatureEmploi.objects.filter(user=request.user).select_related('offre')
    return Response([{'id': c.pk, 'offre_id': c.offre_id, 'titre': c.offre.titre, 'entreprise': c.offre.entreprise,
                      'statut': c.statut, 'statut_libelle': c.get_statut_display(), 'date': c.created_at.isoformat()}
                     for c in qs])

"""Écoles dans l'appli : liste, fiche (photos et filières qui défilent), inscription."""
import re

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .catalog import grande, paginated, public_cache, short, text, vignette
from .utils import error, media


def ecole_item(request, e):
    return {'id': e.pk, 'slug': e.slug, 'nom': e.nom, 'titre': e.nom, 'type': e.type, 'type_libelle': e.get_type_display(),
            'ville': e.ville, 'logo': media(request, e.logo),
            'image': media(request, e.couverture or e.logo), 'image_vignette': vignette(request, e.couverture or e.logo),
            'resume': short(e.description), 'inscriptions_ouvertes': e.inscriptions_ouvertes}


def _ecoles():
    from Ecoles.models import Ecole
    return Ecole.objects.filter(publie=True)


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
    e = _ecoles().filter(slug=slug).prefetch_related('photos', 'filieres').first()
    if not e:
        return error("École introuvable.", 404, code='introuvable')
    d = ecole_item(request, e)
    d.update({
        'description': text(e.description), 'telephone': e.telephone, 'whatsapp': e.whatsapp, 'email': e.email,
        'site_web': e.site_web,
        'photos': [{'image': grande(request, p.image), 'legende': p.legende} for p in e.photos.all()],
        'filieres': [{'id': f.pk, 'nom': f.nom, 'niveau': f.niveau, 'duree': f.duree, 'frais': f.frais,
                      'image': grande(request, f.image) if f.image else None, 'description': text(f.description),
                      'ouverte': f.ouverte} for f in e.filieres.all()],
    })
    return Response(d)


NOM = re.compile(r"[^\W\d_](?:[^\W\d_]|[ '’\-]){1,59}")


@api_view(['POST'])
@permission_classes([AllowAny])
def inscription(request, slug):
    from Ecoles.models import InscriptionEcole
    from Payments.mobile_money import normalize
    from django.core.exceptions import ValidationError
    e = _ecoles().filter(slug=slug).first()
    if not e:
        return error("École introuvable.", 404, code='introuvable')
    if not e.inscriptions_ouvertes:
        return error("Les inscriptions sont fermées.", 400, code='ferme')
    d = request.data
    nom, prenom = str(d.get('nom') or '').strip(), str(d.get('prenom') or '').strip()
    erreurs = {}
    for champ, v in (('nom', nom), ('prenom', prenom)):
        if not NOM.fullmatch(v):
            erreurs[champ] = "Lettres seulement (2 à 60)."
    try:
        tel = normalize(str(d.get('telephone') or ''), str(d.get('pays') or 'tg'))
    except ValidationError as ex:
        erreurs['telephone'] = ex.messages[0]
        tel = ''
    filiere = None
    if d.get('filiere'):
        filiere = e.filieres.filter(pk=d.get('filiere'), ouverte=True).first()
        if not filiere:
            erreurs['filiere'] = "Filière indisponible."
    email = str(d.get('email') or '').strip()
    if email and '@' not in email:
        erreurs['email'] = "E-mail invalide."
    if erreurs:
        return Response({'detail': next(iter(erreurs.values())), 'code': 'donnees_invalides', 'erreurs': erreurs},
                        status=400)
    user = request.user if request.user.is_authenticated else None
    i = InscriptionEcole.objects.create(ecole=e, filiere=filiere, user=user, nom=nom, prenom=prenom, telephone=tel,
                                        email=email or (user.email if user else ''),
                                        niveau_actuel=str(d.get('niveau_actuel') or '')[:80],
                                        message=str(d.get('message') or '')[:1000])
    if user:
        from .notifs import notifier
        notifier(user, "Inscription envoyée", f"{e.nom}{' — ' + filiere.nom if filiere else ''} : l'école vous contactera.")
    return Response({'id': i.pk, 'detail': "Inscription envoyée. L'école vous contactera."}, status=201)

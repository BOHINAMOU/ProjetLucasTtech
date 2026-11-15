"""Écoles dans l'appli : liste, fiche (photos et filières qui défilent), inscription."""
import re

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
    from Ecoles.models import CYCLES
    libelles = dict(CYCLES)
    return {'nouveau': _recent(e), 'cycles': [{'code': c, 'nom': libelles.get(c, c)} for c in (e.cycles or [])],
            'id': e.pk, 'slug': e.slug, 'nom': e.nom, 'titre': e.nom, 'type': e.type, 'type_libelle': e.get_type_display(),
            'ville': e.ville, 'logo': media(request, e.logo),
            'image': media(request, e.couverture or e.logo), 'image_vignette': vignette(request, e.couverture or e.logo),
            'resume': short(e.description), 'inscriptions_ouvertes': e.inscriptions_ouvertes}


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
    from Ecoles.models import CLASSES, NIVEAUX, SERIES_BAC
    from Ecoles.formulaire import definition
    d = ecole_item(request, e)
    d.update({
        'description': text(e.description), 'telephone': e.telephone, 'whatsapp': e.whatsapp, 'email': e.email,
        'site_web': e.site_web,
        'photos': [{'image': grande(request, p.image), 'legende': p.legende} for p in e.photos.all()],
        'classes': {k: v for k, v in CLASSES.items() if k in (e.cycles or [])},
        'niveaux': NIVEAUX, 'series_bac': SERIES_BAC,
        'champs': definition(e),
        'masquer': {'email': e.masquer_email, 'message': e.masquer_message, 'document': e.masquer_document},
        'nouveautes': [{'id': n.pk, 'titre': n.titre, 'texte': n.texte, 'date': n.date.isoformat(),
                        'image': grande(request, n.image) if n.image else None}
                       for n in e.nouveautes.all() if n.publie],
        'filieres': [{'id': f.pk, 'cycle': f.cycle, 'nom': f.nom, 'niveau': f.niveau, 'duree': f.duree, 'frais': f.frais,
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
    email = '' if e.masquer_email else str(d.get('email') or '').strip()
    if email and '@' not in email:
        erreurs['email'] = "E-mail invalide."
    from Ecoles.models import CLASSES, NIVEAUX, SERIES_BAC
    cycle = str(d.get('cycle') or '').strip()
    classe = niveau = serie = ''
    if e.cycles:
        if cycle not in e.cycles:
            erreurs['cycle'] = "Choisissez le cycle."
        elif cycle in CLASSES:
            classe = str(d.get('classe') or '').strip()
            if classe not in CLASSES[cycle]:
                erreurs['classe'] = "Choisissez la classe."
        elif cycle == 'superieur':
            niveau, serie = str(d.get('niveau') or '').strip(), str(d.get('serie_bac') or '').strip()
            if niveau not in NIVEAUX:
                erreurs['niveau'] = "Choisissez le niveau."
            if serie and serie not in SERIES_BAC:
                erreurs['serie_bac'] = "Série invalide."
    if filiere is not None and cycle and filiere.cycle != cycle:
        erreurs['filiere'] = "Filière indisponible."
    from Ecoles.formulaire import controler
    reponses, fichiers, err_champs = controler(e, cycle if e.cycles else '', d, request.FILES)
    erreurs.update(err_champs)
    doc = None if e.masquer_document else request.FILES.get('document')
    if doc is not None:
        ext = doc.name.rsplit('.', 1)[-1].lower() if '.' in doc.name else ''
        if ext not in ('pdf', 'jpg', 'jpeg', 'png', 'webp'):
            erreurs['document'] = "PDF ou image seulement."
        elif doc.size > 5 * 1024 * 1024:
            erreurs['document'] = "Document trop lourd (5 Mo max)."
    if erreurs:
        return Response({'detail': next(iter(erreurs.values())), 'code': 'donnees_invalides', 'erreurs': erreurs},
                        status=400)
    user = request.user if request.user.is_authenticated else None
    i = InscriptionEcole.objects.create(ecole=e, filiere=filiere, user=user, nom=nom, prenom=prenom, telephone=tel,
                                        email=email or (user.email if user else ''),
                                        niveau_actuel=str(d.get('niveau_actuel') or '')[:80],
                                        cycle=cycle if e.cycles else '', classe=classe, niveau_etudes=niveau,
                                        serie_bac=serie, document=doc, reponses=reponses,
                                        message='' if e.masquer_message else str(d.get('message') or '')[:1000])
    from Ecoles.models import FichierInscription
    for c, f in fichiers.items():
        FichierInscription.objects.create(inscription=i, champ=c, fichier=f)
    if user:
        from .notifs import notifier
        notifier(user, "Inscription envoyée", f"{e.nom}{' — ' + filiere.nom if filiere else ''} : l'école vous contactera.")
    return Response({'id': i.pk, 'detail': "Inscription envoyée. L'école vous contactera."}, status=201)

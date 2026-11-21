"""Code PIN du solde (4 chiffres) : demandé pour voir le solde, payer une course par le solde et demander un versement.

Stocké haché (make_password), jamais en clair. 5 essais faux → blocage 15 min. « PIN oublié » : code à 6 chiffres
par e-mail (comme la réinitialisation du mot de passe), valable 10 min. Une saisie correcte donne un jeton signé
valable 10 min, que l'appli joint aux opérations protégées (en-tête X-Pin ou champ « jeton_pin »).
Tant que l'utilisateur n'a pas créé de PIN, rien n'est bloqué (les anciennes versions de l'appli continuent)."""
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api_mobile.utils import error

from .models import PinSolde

logger = logging.getLogger(__name__)
ESSAIS_MAX = 5
BLOCAGE = timedelta(minutes=15)
DUREE_JETON = 600
DUREE_CODE = timedelta(minutes=10)
SEL = 'lantante-pin-solde'


def _valide(pin):
    return isinstance(pin, str) and len(pin) == 4 and pin.isdigit()


def jeton(user):
    return signing.TimestampSigner(salt=SEL).sign(str(user.pk))


def jeton_valide(user, valeur):
    try:
        return signing.TimestampSigner(salt=SEL).unsign(valeur or '', max_age=DUREE_JETON) == str(user.pk)
    except signing.BadSignature:
        return False


def exige_pin(request):
    """None si l'opération est permise, sinon une réponse d'erreur (PIN requis)."""
    p = PinSolde.objects.filter(user=request.user).first()
    if not p or not p.pin_hash:
        return None
    valeur = request.headers.get('X-Pin') or str(request.data.get('jeton_pin') or '' if hasattr(request, 'data') else '')
    if jeton_valide(request.user, valeur):
        return None
    return error("Code PIN requis.", 403, code='pin_requis')


def _etat(p):
    bloque = bool(p and p.bloque_jusqua and p.bloque_jusqua > timezone.now())
    return {'defini': bool(p and p.pin_hash), 'bloque': bloque,
            'bloque_jusqua': p.bloque_jusqua.isoformat() if bloque else None}


@api_view(['GET'])
def etat(request):
    return Response(_etat(PinSolde.objects.filter(user=request.user).first()))


@api_view(['POST'])
def creer(request):
    """Création du PIN (une seule fois ; ensuite « PIN oublié »)."""
    pin, confirmation = str(request.data.get('pin') or ''), str(request.data.get('confirmation') or '')
    if not _valide(pin):
        return error("Le PIN doit avoir 4 chiffres.", code='pin_invalide')
    if pin != confirmation:
        return error("Les deux codes ne correspondent pas.", code='confirmation')
    p, _ = PinSolde.objects.get_or_create(user=request.user)
    if p.pin_hash:
        return error("Un PIN existe déjà.", code='pin_existe')
    p.pin_hash, p.essais, p.bloque_jusqua = make_password(pin), 0, None
    p.save()
    return Response({**_etat(p), 'jeton': jeton(request.user)}, status=201)


@api_view(['POST'])
def verifier(request):
    p = PinSolde.objects.filter(user=request.user).first()
    if not p or not p.pin_hash:
        return error("Aucun PIN.", 404, code='pas_de_pin')
    maintenant = timezone.now()
    if p.bloque_jusqua and p.bloque_jusqua > maintenant:
        minutes = int((p.bloque_jusqua - maintenant).total_seconds() // 60) + 1
        return error(f"Trop d'essais. Réessayez dans {minutes} min.", 429, code='pin_bloque')
    if check_password(str(request.data.get('pin') or ''), p.pin_hash):
        p.essais, p.bloque_jusqua = 0, None
        p.save(update_fields=['essais', 'bloque_jusqua'])
        return Response({'jeton': jeton(request.user), 'duree_s': DUREE_JETON})
    p.essais += 1
    if p.essais >= ESSAIS_MAX:
        p.essais, p.bloque_jusqua = 0, maintenant + BLOCAGE
        p.save(update_fields=['essais', 'bloque_jusqua'])
        return error("Trop d'essais. Réessayez dans 15 min.", 429, code='pin_bloque')
    p.save(update_fields=['essais'])
    return error(f"PIN incorrect. {ESSAIS_MAX - p.essais} essai(s) restant(s).", 400, code='pin_faux')


@api_view(['POST'])
def oublie(request):
    """Envoie un code à 6 chiffres par e-mail (valable 10 min)."""
    p, _ = PinSolde.objects.get_or_create(user=request.user)
    if p.code_envoye_le and timezone.now() - p.code_envoye_le < timedelta(seconds=60):
        return error("Patientez une minute avant de redemander un code.", 429, code='trop_tot')
    code = f"{secrets.randbelow(1_000_000):06d}"
    p.code_hash, p.code_envoye_le = make_password(code), timezone.now()
    p.save(update_fields=['code_hash', 'code_envoye_le'])
    try:
        send_mail(subject="Code PIN du solde - Lantante",
                  message=(f"Bonjour,\n\nCODE DE VÉRIFICATION : {code}\n\nIl permet de choisir un nouveau code PIN "
                           "pour votre solde Lantante. Valable 10 minutes.\n\n⚠️ Ne partagez jamais ce code.\n"),
                  from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[request.user.email], fail_silently=False)
    except Exception:
        logger.exception("PIN oublié : envoi de l'e-mail impossible")
        return error("Envoi du code impossible pour le moment.", 503, code='envoi')
    return Response({'detail': f"Code envoyé à {request.user.email}."})


@api_view(['POST'])
def reinitialiser(request):
    """{code, pin, confirmation} : nouveau PIN après « PIN oublié »."""
    p = PinSolde.objects.filter(user=request.user).first()
    code = str(request.data.get('code') or '')
    if (not p or not p.code_hash or not p.code_envoye_le or timezone.now() - p.code_envoye_le > DUREE_CODE
            or not check_password(code, p.code_hash)):
        return error("Code incorrect ou expiré.", code='code_invalide')
    pin, confirmation = str(request.data.get('pin') or ''), str(request.data.get('confirmation') or '')
    if not _valide(pin):
        return error("Le PIN doit avoir 4 chiffres.", code='pin_invalide')
    if pin != confirmation:
        return error("Les deux codes ne correspondent pas.", code='confirmation')
    p.pin_hash, p.code_hash, p.essais, p.bloque_jusqua = make_password(pin), '', 0, None
    p.save()
    return Response({**_etat(p), 'jeton': jeton(request.user)})

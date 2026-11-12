"""API REST de l'application mobile (Android / iOS) de lantantetechnologie.com.

Mêmes règles que le site : droits d'accès aux épreuves (abonnements.access), stockage privé des
documents, code de réinitialisation du mot de passe envoyé par email."""
import logging
import mimetypes

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db.models import Count, Prefetch, Q
from django.http import FileResponse

from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from abonnements.access import active_subscriptions
from abonnements.models import SubscriptionPlan, UserSubscription
from concours.models import Contest, ContestCategory, ContestSession, Correction, ExamPaper
from Users.forms import SiteAuthenticationForm
from Users.models import PasswordResetCode

from . import history
from .utils import (OFFLINE_PLAN_CODES, Rights, contest_payload, dt, error, event_payload,
                    formation_payload, product_payload, user_payload)

logger = logging.getLogger(__name__)
User = get_user_model()

LOGIN_MAX_FAILS = 10
LOGIN_WINDOW = 15 * 60  # secondes


def _client_ip(request):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return fwd.split(',')[0].strip() if fwd else request.META.get('REMOTE_ADDR', '')


def _limit_key(prefix, request):
    return f"api_mobile:{prefix}:{_client_ip(request)}"


def _too_many(prefix, request, limit=LOGIN_MAX_FAILS):
    return (cache.get(_limit_key(prefix, request)) or 0) >= limit


def _hit(prefix, request):
    key = _limit_key(prefix, request)
    if cache.add(key, 1, LOGIN_WINDOW):
        return
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, LOGIN_WINDOW)


# ─────────────────────────────
# Compte
# ─────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    if _too_many('login', request):
        return error("Trop de tentatives de connexion. Réessayez dans 15 minutes.", 429, code='trop_de_tentatives')
    ident = (request.data.get('identifiant') or request.data.get('email') or '').strip()
    password = request.data.get('password') or ''
    if not ident or not password:
        return error("Renseignez votre email (ou téléphone) et votre mot de passe.", 400, code='champs_manquants')
    email = ident
    if '@' not in ident:  # pas de nom d'utilisateur sur le site : on accepte le numéro de téléphone
        u = User.objects.filter(phone=ident).first()
        email = u.email if u else ident
    form = SiteAuthenticationForm(request._request, data={'username': email, 'password': password})
    if not form.is_valid():
        _hit('login', request)
        errors = form.non_field_errors()
        msg = str(errors[0]) if errors else "Identifiant ou mot de passe incorrect."
        if 'suspendu' not in msg:
            msg = "Identifiant ou mot de passe incorrect."
        return error(msg, 400, code='identifiants_invalides')
    user = form.get_user()
    token, _ = Token.objects.get_or_create(user=user)
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])
    return Response({'token': token.key, 'user': user_payload(request, user)})


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    if _too_many('register', request):
        return error("Trop d'inscriptions depuis cette connexion. Réessayez plus tard.", 429, code='trop_de_tentatives')
    d = request.data
    data = {k: str(d.get(k) or '').strip() for k in ('first_name', 'last_name', 'email', 'phone', 'country')}
    password = d.get('password') or ''
    errors = {}
    for field, label in (('first_name', 'Le prénom'), ('last_name', 'Le nom'), ('email', "L'email"),
                         ('phone', 'Le téléphone')):
        if not data[field]:
            errors[field] = [f"{label} est obligatoire."]
    if data['email']:
        try:
            validate_email(data['email'])
        except ValidationError:
            errors['email'] = ["Adresse email invalide."]
        else:
            if User.objects.filter(email__iexact=data['email']).exists():
                errors['email'] = ["Cet email est déjà utilisé."]
    if not password:
        errors['password'] = ["Le mot de passe est obligatoire."]
    else:
        try:
            validate_password(password, User(email=data['email'], first_name=data['first_name'],
                                             last_name=data['last_name']))
        except ValidationError as e:
            errors['password'] = list(e.messages)
    if errors:
        first = next(iter(errors.values()))[0]
        return error(first, 400, code='donnees_invalides', errors=errors)
    _hit('register', request)
    user = User.objects.create_user(email=data['email'].lower(), password=password,
                                    first_name=data['first_name'][:150], last_name=data['last_name'][:150],
                                    phone=data['phone'][:20], country=data['country'][:100] or None)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': user_payload(request, user)}, status=201)


@api_view(['POST'])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response({'detail': "Vous êtes déconnecté."})


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset(request):
    """Envoie le code à 6 chiffres du site par email. Répond toujours 200 (pas de fuite des comptes)."""
    ok = Response({'detail': "Si un compte existe pour cette adresse, un code de réinitialisation "
                             "vient d'être envoyé par email. Il est valable 5 minutes."})
    if _too_many('reset', request, limit=5):
        return ok
    _hit('reset', request)
    email = str(request.data.get('email') or '').strip().lower()
    user = User.objects.filter(email__iexact=email).first() if email else None
    if user and user.is_active:
        otp = PasswordResetCode.objects.create(user=user, code=PasswordResetCode.generate_code())
        try:
            send_mail(
                subject="Réinitialisation de mot de passe - Lantante Technologie",
                message=(f"Bonjour {user.email},\n\nVous avez demandé une réinitialisation de mot de passe.\n\n"
                         f"CODE DE VÉRIFICATION : {otp.code}\n\nCe code est valable 5 minutes.\n\n"
                         "⚠️ Ne partagez jamais ce code.\n"),
                from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[user.email], fail_silently=False)
        except Exception:
            logger.exception("API mobile : échec d'envoi de l'email de réinitialisation")
    return ok


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    """{email, code, password} : vérifie le code reçu par email et change le mot de passe."""
    if _too_many('reset_confirm', request):
        return error("Trop de tentatives. Réessayez dans 15 minutes.", 429, code='trop_de_tentatives')
    email = str(request.data.get('email') or '').strip()
    code = str(request.data.get('code') or '').strip()
    password = request.data.get('password') or ''
    user = User.objects.filter(email__iexact=email).first() if email else None
    otp = (PasswordResetCode.objects.filter(user=user, code=code, is_used=False).order_by('-created_at').first()
           if user and code else None)
    if not otp or not otp.is_valid():
        _hit('reset_confirm', request)
        return error("Code invalide ou expiré.", 400, code='code_invalide')
    try:
        validate_password(password, user)
    except ValidationError as e:
        return error(e.messages[0], 400, code='donnees_invalides', errors={'password': list(e.messages)})
    user.set_password(password)
    user.save()
    otp.is_used = True
    otp.save(update_fields=['is_used'])
    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    return Response({'token': token.key, 'user': user_payload(request, user)})


@api_view(['GET'])
def me(request):
    user = request.user
    rights = Rights(user)
    published = Contest.objects.published()
    if rights.staff or rights.unlimited:
        n_contests = published.count()
    else:
        n_contests = published.filter(pk__in=rights.ids).count()
    from Events.models import Ticket
    from Payments.models import Payment
    from Shop.models import ShopOrder
    achats = (Payment.objects.filter(user=user, status='approved').count()
              + ShopOrder.objects.filter(user=user).exclude(payment_method='fedapay')
              .exclude(status='cancelled').count())
    payload = user_payload(request, user)
    payload['stats'] = {
        'abonnements_actifs': active_subscriptions(user).count(),
        'concours_accessibles': n_contests,
        'tickets': Ticket.objects.filter(payment__user=user, payment__status='approved').count(),
        'achats': achats,
    }
    return Response(payload)


# ─────────────────────────────
# Accueil et catalogues
# ─────────────────────────────
def _contests():
    return (Contest.objects.published().select_related('category').annotate(
        n_sessions=Count('sessions', filter=Q(sessions__is_published=True), distinct=True),
        n_papers=Count('sessions__papers', filter=Q(sessions__is_published=True,
                                                    sessions__papers__is_published=True), distinct=True)))


def _events():
    from Events.models import Event
    now = timezone.now()
    return (Event.objects.filter(is_published=True).filter(Q(ends_at__gte=now) | Q(ends_at__isnull=True,
                                                                                    starts_at__gte=now))
            .prefetch_related('ticket_types').order_by('starts_at'))


def _formations():
    from Formations.models import Formation
    return Formation.objects.filter(is_published=True).order_by('-is_featured', '-created_at')


def _products():
    from Shop.models import Product
    return Product.objects.filter(is_available=True).order_by('-is_featured', '-created_at')


@api_view(['GET'])
@permission_classes([AllowAny])
def home(request):
    rights = Rights(request.user)
    populaires = (_contests().annotate(n_abonnes=Count('subscription_links', distinct=True))
                  .order_by('-n_abonnes', '-n_papers', 'acronym')[:6])
    return Response({
        'concours_populaires': [contest_payload(request, c, rights) for c in populaires],
        'evenements': [event_payload(request, e) for e in _events()[:6]],
        'formations': [formation_payload(request, f) for f in _formations()[:6]],
        'produits': [product_payload(request, p) for p in _products()[:6]],
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def evenements(request):
    return Response([event_payload(request, e) for e in _events()])


@api_view(['GET'])
@permission_classes([AllowAny])
def formations(request):
    return Response([formation_payload(request, f) for f in _formations()])


@api_view(['GET'])
@permission_classes([AllowAny])
def produits(request):
    qs = _products()
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    return Response([product_payload(request, p) for p in qs[:200]])


# ─────────────────────────────
# Concours
# ─────────────────────────────
@api_view(['GET'])
@permission_classes([AllowAny])
def concours_categories(request):
    cats = ContestCategory.objects.filter(contests__is_published=True).distinct()
    return Response([{'id': c.pk, 'nom': c.name, 'slug': c.slug} for c in cats])


@api_view(['GET'])
@permission_classes([AllowAny])
def concours_list(request):
    qs = _contests()
    q = (request.GET.get('q') or '').strip()
    cat = (request.GET.get('categorie') or '').strip()
    if cat:
        qs = qs.filter(category__pk=int(cat)) if cat.isdigit() else qs.filter(category__slug=cat)
    if q:
        qs = qs.filter(Q(acronym__icontains=q) | Q(name__icontains=q) | Q(description__icontains=q))
    rights = Rights(request.user)
    return Response([contest_payload(request, c, rights) for c in qs])


def _get_contest(slug):
    return _contests().filter(slug=slug).first()


@api_view(['GET'])
@permission_classes([AllowAny])
def concours_detail(request, slug):
    contest = _get_contest(slug)
    if not contest:
        return error("Concours introuvable.", 404, code='introuvable')
    rights = Rights(request.user)
    data = contest_payload(request, contest, rights)
    sessions = contest.sessions.filter(is_published=True).annotate(
        n=Count('papers', filter=Q(papers__is_published=True)))
    data['description'] = contest.description
    data['annees'] = [{'id': s.pk, 'annee': s.year, 'nb_epreuves': s.n} for s in sessions]
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def concours_annee(request, slug, pk):
    contest = _get_contest(slug)
    sess = ContestSession.objects.filter(contest=contest, pk=pk, is_published=True).first() if contest else None
    if not sess:
        return error("Année introuvable.", 404, code='introuvable')
    rights = Rights(request.user)
    papers = sess.papers.filter(is_published=True).prefetch_related(
        Prefetch('corrections', queryset=Correction.objects.filter(is_published=True)))
    out = []
    for p in papers:
        ok = rights.can_view(p, contest)
        out.append({
            'id': p.pk, 'titre': p.title, 'matiere': p.subject, 'duree': p.duration,
            'coefficient': float(p.coefficient) if p.coefficient is not None else None,
            'description': p.description, 'gratuite': p.is_free, 'accessible': ok,
            'hors_ligne_autorise': ok and rights.offline_allowed(p, contest),
            'document_disponible': bool(p.file),
            'corriges': [{'id': c.pk, 'titre': c.get_kind_display() + (f" — {c.author}" if c.author else ''),
                          'type': c.kind, 'accessible': ok} for c in p.corrections.all()],
        })
    return Response({'concours': contest_payload(request, contest, rights), 'annee': sess.year, 'epreuves': out})


@api_view(['GET'])
@permission_classes([AllowAny])
def document(request, kind, pk):
    """PDF d'une épreuve ou d'un corrigé : mêmes droits que concours.views.file (revérifiés à chaque appel)."""
    unavailable = error("Ce document n'est pas disponible.", 404, code='indisponible')
    if kind == 'epreuve':
        doc = ExamPaper.objects.select_related('session__contest').filter(pk=pk).first()
        paper = doc
        published = bool(doc) and doc.is_published
    elif kind == 'corrige':
        doc = Correction.objects.select_related('paper__session__contest').filter(pk=pk).first()
        paper = doc.paper if doc else None
        published = bool(doc) and doc.is_published and paper.is_published
    else:
        return unavailable
    if not doc:
        return unavailable
    contest = paper.session.contest
    user = request.user
    if not (user.is_authenticated and user.is_staff) and not (
            published and paper.session.is_published and contest.is_published):
        return unavailable
    rights = Rights(user)
    if not rights.can_view(paper, contest):
        if not user.is_authenticated:
            return error("Connectez-vous et abonnez-vous pour lire ce document.", 403, code='abonnement_requis')
        return error(f"Ce document est réservé aux abonnés du concours {contest.acronym}.", 403,
                     code='abonnement_requis')
    if not doc.file:
        return unavailable
    try:
        fh = doc.file.open('rb')
    except (FileNotFoundError, OSError):
        return unavailable
    ctype = mimetypes.guess_type(doc.file.name)[0] or 'application/octet-stream'
    resp = FileResponse(fh, content_type=ctype)
    resp['Content-Disposition'] = 'inline'
    resp['Cache-Control'] = 'private, no-store, max-age=0'
    resp['X-Robots-Tag'] = 'noindex, nofollow'
    offline = rights.offline_allowed(paper, contest)
    resp['X-Hors-Ligne-Autorise'] = '1' if offline else '0'
    until = rights.offline_until(contest) if offline and not paper.is_free else None
    if until:
        resp['X-Hors-Ligne-Jusqu-A'] = dt(until)
    # Filigrane : comme le lecteur du site, l'application superpose l'email du lecteur sur le document.
    resp['X-Filigrane'] = user.email if user.is_authenticated else 'Lantante Technologie'
    resp['Access-Control-Expose-Headers'] = 'X-Hors-Ligne-Autorise, X-Hors-Ligne-Jusqu-A, X-Filigrane'
    return resp


# ─────────────────────────────
# Abonnements
# ─────────────────────────────
@api_view(['GET'])
@permission_classes([AllowAny])
def formules(request):
    plans = SubscriptionPlan.objects.filter(is_active=True)
    return Response([{
        'code': p.code, 'nom': p.name, 'prix_mensuel': p.monthly_price, 'prix_annuel': p.yearly_price,
        'nb_concours': None if p.is_unlimited else p.contest_limit,
        'hors_ligne': p.is_unlimited or p.code in OFFLINE_PLAN_CODES,
    } for p in plans])


@api_view(['GET'])
def abonnements(request):
    now = timezone.now()
    subs = (UserSubscription.objects.filter(user=request.user).exclude(status='fusionne')
            .select_related('plan').prefetch_related('contests__contest', 'extensions'))
    out = []
    for s in subs:
        statut = s.status
        if statut == 'actif' and s.end_at and s.end_at <= now:
            statut = 'expire'
        links = list(s.contests.all())
        out.append({
            'id': s.pk, 'formule': {'code': s.plan.code, 'nom': s.plan.name}, 'statut': statut,
            'statut_libelle': dict(UserSubscription._meta.get_field('status').choices).get(statut, statut),
            'debut': dt(s.start_at), 'fin': dt(s.end_at),
            'concours': [{'sigle': l.contest.acronym, 'nom': l.contest.name} for l in links],
            'places_utilisees': len(links), 'places_total': s.total_limit,
            'illimite': s.is_unlimited,
        })
    return Response(out)


# ─────────────────────────────
# Historique
# ─────────────────────────────
@api_view(['GET'])
def historique(request):
    return Response(history.filtered(request, request.user, request.GET.get('type') or 'tous'))


@api_view(['GET'])
def telechargement(request, reference):
    """Re-téléchargement du PDF acheté (formation ou service), pour le propriétaire du paiement."""
    from Payments.models import Payment
    p = Payment.objects.filter(reference=reference, user=request.user).select_related('formation', 'service').first()
    f = p.downloadable_file if p and p.is_paid else None
    if not f:
        return error("Ce fichier n'est pas disponible.", 404, code='indisponible')
    try:
        fh = f.open('rb')
    except (FileNotFoundError, OSError):
        return error("Ce fichier n'est pas disponible.", 404, code='indisponible')
    resp = FileResponse(fh, as_attachment=True, filename=f.name.rsplit('/', 1)[-1])
    resp['Cache-Control'] = 'private, no-store, max-age=0'
    return resp

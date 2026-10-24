"""API mobile (Android / iOS) : mêmes règles que le site, mêmes formulaires, mêmes actions métier."""
from functools import wraps

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, parser_classes, permission_classes, throttle_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from core.models import Partner, SiteSettings
from Users.forms import RegisterForm, SiteAuthenticationForm

from .. import actions, billing
from ..forms import (
    ApplicationForm, AvailabilityForm, CandidateDocumentForm, CandidateForm, CommentForm, EmployerForm, JobOfferForm,
    MessageForm, NewConversationForm, OfferBoostForm, OrderContentForm, PaymentForm, SpontaneousRequestForm,
    StaffingRequestForm,
)
from ..models import (
    CONTRACT_CHOICES, DOMAIN_CHOICES, INTERNSHIP_DURATION_CHOICES, LEVEL_CHOICES, Appointment, Application,
    CandidateDocument, CandidateProfile, Conversation, DeviceToken, EmployerProfile, FeedPost, JobOffer, Message,
    Notification, PublicationOrder, ServicePlan, SpontaneousRequest,
)
from ..services import (
    account_kind, can_see_private, is_staff, notify, notify_partner_message, notify_staff, partner_recipient, send_auto_ack,
    staff_users,
)
from .serializers import (
    DOMAINS, abs_url, application_payload, appointment_payload, candidate_payload, company_payload, conversation_payload,
    document_payload, notification_payload, offer_payload, order_payload, partner_payload, plan_payload, post_payload,
    spontaneous_payload, user_payload,
)

User = get_user_model()
JSON_AND_FILES = [JSONParser, MultiPartParser, FormParser]


# ─────────────────────────────
# Outils communs
# ─────────────────────────────
class AuthThrottle(SimpleRateThrottle):
    """Connexion et inscription : 10 essais par minute et par adresse IP (anti-force brute)."""
    scope = 'auth'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


def error(detail, status=400, errors=None, code=None):
    body = {'detail': detail}
    if errors:
        body['errors'] = errors
    if code:
        body['code'] = code
    return Response(body, status=status)


def form_errors(form):
    out = {}
    for name, errs in form.errors.items():
        out['non_field' if name == '__all__' else name] = [str(e) for e in errs]
    return out


def invalid(form):
    return error("Certaines informations sont à corriger.", 400, form_errors(form), 'invalid')


def merged(form_class, data, instance=None, **kw):
    """Données d'un formulaire pour une modification partielle : ce qui n'est pas envoyé garde sa valeur actuelle."""
    blank = form_class(instance=instance, **kw) if instance is not None else form_class(**kw)
    payload = {}
    for name, field in blank.fields.items():
        if isinstance(field, forms.FileField):
            continue
        if name in data:
            multi = isinstance(field.widget, (forms.CheckboxSelectMultiple, forms.SelectMultiple))
            payload[name] = data.getlist(name) if (multi and hasattr(data, 'getlist')) else (
                data.get(name) if hasattr(data, 'getlist') else data[name])
        elif instance is not None:
            payload[name] = blank[name].value()
    return payload


def kinds(*allowed):
    """Réserve un point d'entrée à un type de compte (candidat / entreprise / particulier)."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if account_kind(request.user) not in allowed:
                return error("Cette fonction n'est pas disponible pour ce type de compte.", 403, code='wrong_account_type')
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def paginate(request, qs, serialize, per_page=20):
    paginator = Paginator(qs, per_page)
    page = paginator.get_page(request.query_params.get('page'))
    return Response({'count': paginator.count, 'page': page.number, 'pages': paginator.num_pages,
                     'results': [serialize(x) for x in page.object_list]})


def candidate_profile(user):
    return getattr(user, 'candidate_profile', None)


def employer_profile(user):
    return getattr(user, 'employer_profile', None)


def counters(user):
    from ..models import Message as Msg
    access = Q(conversation__participants=user)
    unread = Msg.objects.exclude(sender=user).exclude(read_by=user)
    if is_staff(user):
        access |= Q(conversation__kind='support')
        unread = unread.exclude(is_automatic=True)
    data = {'unread_notifications': user.emploi_notifications.filter(is_read=False).count(),
            'unread_messages': unread.filter(access).distinct().count()}
    employer = employer_profile(user)
    if employer:
        data['new_applications'] = Application.objects.filter(
            Q(offer__employer=employer) | Q(request__employer=employer), shared_with_employer=True, status='received').count()
    return data


# ─────────────────────────────
# Configuration (listes de choix pour les formulaires)
# ─────────────────────────────
@api_view(['GET'])
@permission_classes([AllowAny])
def config(request):
    site = SiteSettings.load()
    return Response({
        'domains': [{'value': k, 'label': v} for k, v in DOMAIN_CHOICES],
        'contracts': [{'value': k, 'label': v} for k, v in CONTRACT_CHOICES],
        'education_levels': [{'value': k, 'label': v} for k, v in LEVEL_CHOICES if k],
        'internship_durations': [d for d, _ in INTERNSHIP_DURATION_CHOICES],
        'request_types': [{'value': k, 'label': v} for k, v in SpontaneousRequest.TYPES],
        'document_kinds': [{'value': k, 'label': v} for k, v in CandidateDocument.KIND],
        'account_types': [{'value': 'candidate', 'label': "Je cherche un emploi"},
                          {'value': 'employer', 'label': "Je représente une entreprise"},
                          {'value': 'member', 'label': "Je suis un particulier (publier une actualité ou une annonce)"}],
        'payment': {'flooz': site.payment_flooz, 'tmoney': site.payment_tmoney, 'whatsapp': site.whatsapp_1},
        'api_version': 1,
    })


# ─────────────────────────────
# Compte
# ─────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def register(request):
    data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
    if 'password' in data:
        data['password1'] = data['password2'] = data['password']
    data.setdefault('account_type', 'candidate')
    form = RegisterForm(data)
    if not form.is_valid():
        return invalid(form)
    try:
        validate_password(form.cleaned_data['password1'])
    except ValidationError as exc:
        return error("Mot de passe trop faible.", 400, {'password1': list(exc.messages)}, 'invalid')
    user = form.save(commit=False)
    user.account_type = form.cleaned_data.get('account_type') or 'candidate'
    user.first_name = str(data.get('first_name', ''))[:150]
    user.last_name = str(data.get('last_name', ''))[:150]
    user.save()
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': user_payload(request, user)}, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def login(request):
    form = SiteAuthenticationForm(request._request, data={
        'username': request.data.get('email') or request.data.get('username') or '',
        'password': request.data.get('password') or ''})
    if not form.is_valid():
        errors = form.non_field_errors()
        return error(str(errors[0]) if errors else "Email ou mot de passe incorrect.", 400, code='invalid_login')
    user = form.get_user()
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': user_payload(request, user)})


@api_view(['POST'])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response(status=204)


@api_view(['GET', 'PATCH'])
@parser_classes(JSON_AND_FILES)
def me(request):
    user = request.user
    if request.method == 'PATCH':
        for field in ('first_name', 'last_name', 'phone', 'city', 'country'):
            if field in request.data:
                setattr(user, field, str(request.data[field])[:150])
        avatar = request.FILES.get('avatar')
        if avatar:
            if avatar.size > 5 * 1024 * 1024 or not avatar.content_type.startswith('image/'):
                return error("La photo doit être une image de 5 Mo maximum.", 400, code='invalid')
            user.avatar = avatar
        user.save()
    return Response({**user_payload(request, user), **counters(user)})


@api_view(['POST'])
def choose_account_type(request):
    """Un compte sans type (ex. connexion Google) choisit son espace, une seule fois."""
    if account_kind(request.user) != 'undefined':
        return error("Le type de compte est déjà défini.", 400, code='already_set')
    kind = request.data.get('account_type')
    if kind not in ('candidate', 'employer', 'member'):
        return error("Type de compte invalide.", 400, code='invalid')
    request.user.account_type = kind
    request.user.save(update_fields=['account_type'])
    return Response(user_payload(request, request.user))


@api_view(['POST', 'DELETE'])
def devices(request):
    token = str(request.data.get('token', '')).strip()
    if not token:
        return error("Jeton manquant.", 400, code='invalid')
    if request.method == 'DELETE':
        DeviceToken.objects.filter(user=request.user, token=token).delete()
        return Response(status=204)
    DeviceToken.objects.update_or_create(token=token, defaults={'user': request.user,
                                                                'platform': str(request.data.get('platform', ''))[:10]})
    return Response(status=201)


# ─────────────────────────────
# Offres, entreprises, partenaires, actualités
# ─────────────────────────────
@api_view(['GET'])
@permission_classes([AllowAny])
def offers(request):
    from ..views import _open_offers
    if account_kind(request.user) in ('employer', 'member'):
        return error("Les offres d'emploi sont réservées aux candidats.", 403, code='wrong_account_type')
    qs = _open_offers()
    q = request.query_params.get('q', '').strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(skills__name__icontains=q)).distinct()
    for param, lookup in (('domain', 'domain'), ('contract', 'contract')):
        if request.query_params.get(param):
            qs = qs.filter(**{lookup: request.query_params[param]})
    if request.query_params.get('city'):
        qs = qs.filter(city__icontains=request.query_params['city'])
    return paginate(request, qs, lambda o: offer_payload(request, o))


@api_view(['GET'])
@permission_classes([AllowAny])
def offer_detail(request, slug):
    offer = get_object_or_404(JobOffer.objects.select_related('employer'), slug=slug)
    owner = request.user.is_authenticated and offer.employer_id and offer.employer.user_id == request.user.pk
    if offer.status != 'published' and not (owner or is_staff(request.user)):
        raise Http404
    kind = account_kind(request.user)
    if kind in ('employer', 'member') and not (owner or is_staff(request.user)):
        return error("Les offres d'emploi sont réservées aux candidats.", 403, code='wrong_account_type')
    data = offer_payload(request, offer, detail=True)
    profile = candidate_profile(request.user) if request.user.is_authenticated else None
    data['applied'] = bool(profile and Application.objects.filter(candidate=profile, offer=offer).exists())
    data['can_apply'] = bool(kind == 'candidate' and offer.is_open and not data['applied'])
    data['company'] = company_payload(request, offer.employer) if offer.employer_id else None
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def companies(request):
    qs = EmployerProfile.objects.filter(status='approved').select_related('partner').order_by('-is_verified', 'company_name')
    return paginate(request, qs, lambda e: company_payload(request, e))


@api_view(['GET'])
@permission_classes([AllowAny])
def company_detail(request, pk):
    from ..views import _open_offers
    company = get_object_or_404(EmployerProfile.objects.select_related('partner'), pk=pk)
    me_owner = request.user.is_authenticated and company.user_id == request.user.pk
    if not company.is_approved and not (me_owner or is_staff(request.user)):
        raise Http404
    data = company_payload(request, company, detail=True)
    kind = account_kind(request.user)
    data['offers'] = [] if (kind in ('employer', 'member') and not me_owner) else \
        [offer_payload(request, o) for o in _open_offers().filter(employer=company)]
    data['posts'] = [post_payload(request, p, request.user) for p in
                     FeedPost.objects.filter(author=company.user, is_hidden=False)[:5]]
    data['can_message'] = bool(request.user.is_authenticated and not me_owner)
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def partners(request):
    return paginate(request, Partner.objects.filter(is_active=True), lambda p: partner_payload(request, p), per_page=50)


@api_view(['GET'])
@permission_classes([AllowAny])
def partner_detail(request, pk):
    partner = get_object_or_404(Partner, pk=pk, is_active=True)
    data = partner_payload(request, partner)
    data['achievements'] = partner.achievements
    data['can_message'] = bool(request.user.is_authenticated and partner_recipient(partner, create=False) is not None)
    employer = getattr(partner, 'employer', None)
    if employer is not None and employer.is_approved:
        data['company'] = company_payload(request, employer, detail=True)
        data['posts'] = [post_payload(request, p, request.user) for p in
                         FeedPost.objects.filter(author=employer.user, is_hidden=False)[:8]]
        from ..views import _open_offers
        data['offers'] = [] if account_kind(request.user) in ('employer', 'member') else             [offer_payload(request, o) for o in _open_offers().filter(employer=employer)]
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def feed(request):
    now = timezone.now()
    posts = FeedPost.objects.filter(is_hidden=False).select_related('author').prefetch_related('comments__author', 'likes').annotate(
        pinned=Case(When(is_featured=True, featured_until__gt=now, then=Value(1)),
                    When(is_featured=True, featured_until__isnull=True, then=Value(1)),
                    default=Value(0), output_field=IntegerField())).order_by('-pinned', '-created_at')
    return paginate(request, posts, lambda p: post_payload(request, p, request.user), per_page=10)


def _organizations():
    """Entreprises et partenaires, c'est la même chose : une seule liste.
    Un partenaire (lié ou non à un compte entreprise) est listé comme partenaire ; les autres entreprises acceptées comme entreprises."""
    partners_ = list(Partner.objects.filter(is_active=True).select_related('employer'))
    companies_ = list(EmployerProfile.objects.filter(status='approved', partner__isnull=True).order_by('-is_verified', 'company_name'))
    return partners_, companies_


def _org_payload(request, kind, obj):
    if kind == 'partner':
        employer = getattr(obj, 'employer', None)
        return {'key': f'partner-{obj.pk}', 'kind': 'partner', 'id': obj.pk, 'name': obj.name, 'logo': abs_url(request, obj.logo),
                'subtitle': obj.domain or obj.country, 'city': obj.country, 'verified': bool(employer and employer.is_verified),
                'is_partner': True}
    return {'key': f'company-{obj.pk}', 'kind': 'company', 'id': obj.pk, 'name': obj.company_name, 'logo': abs_url(request, obj.logo),
            'subtitle': DOMAINS.get(obj.sector, ''), 'city': obj.city, 'verified': obj.is_verified, 'is_partner': False}


@api_view(['GET'])
@permission_classes([AllowAny])
def directory(request):
    """Liste unique des entreprises et partenaires (recherche : ?q=)."""
    partners_, companies_ = _organizations()
    items = [_org_payload(request, 'partner', p) for p in partners_] + [_org_payload(request, 'company', c) for c in companies_]
    q = request.query_params.get('q', '').strip().lower()
    if q:
        items = [i for i in items if q in i['name'].lower() or q in (i['subtitle'] or '').lower() or q in (i['city'] or '').lower()]
    items.sort(key=lambda i: (not i['is_partner'], not i['verified'], i['name'].lower()))
    return paginate(request, items, lambda x: x, per_page=30)


@api_view(['GET'])
@permission_classes([AllowAny])
def highlights(request):
    """Bannière de l'accueil : entreprises/partenaires, actualités et offres d'emploi, l'un après l'autre."""
    from ..views import _open_offers
    kind = account_kind(request.user)
    partners_, companies_ = _organizations()
    orgs = [_org_payload(request, 'partner', p) for p in partners_[:8]] + [_org_payload(request, 'company', c) for c in companies_[:4]]
    orgs = [{'type': 'org', 'target': o['kind'], 'id': o['id'], 'title': o['name'], 'subtitle': o['subtitle'], 'image': o['logo'],
             'logo': o['logo'], 'badge': 'Partenaire' if o['is_partner'] else 'Entreprise'} for o in orgs]
    now = timezone.now()
    posts = FeedPost.objects.filter(is_hidden=False).select_related('author').annotate(
        pinned=Case(When(is_featured=True, featured_until__gt=now, then=Value(1)),
                    When(is_featured=True, featured_until__isnull=True, then=Value(1)),
                    default=Value(0), output_field=IntegerField())).order_by('-pinned', '-created_at')[:8]
    news = []
    for p in posts:
        employer = p.author_employer
        logo = abs_url(request, employer.logo) if employer and employer.logo else None
        news.append({'type': 'post', 'target': 'post', 'id': p.pk, 'title': p.author_label, 'subtitle': p.text[:110],
                     'image': abs_url(request, p.image) or logo, 'logo': logo, 'badge': 'Actualité'})
    jobs = []
    if kind in ('candidate', 'anonymous', 'undefined'):  # les offres sont réservées aux candidats
        for o in _open_offers().order_by('-is_featured', '-created_at')[:8]:
            logo = abs_url(request, o.employer.logo) if o.employer_id and o.employer.logo else None
            jobs.append({'type': 'offer', 'target': 'offer', 'id': o.pk, 'slug': o.slug, 'title': o.title,
                         'subtitle': f"{o.company_name} · {o.city}" if o.city else o.company_name,
                         'image': abs_url(request, o.cover_image) or logo, 'logo': logo, 'badge': "Offre d'emploi"})
    mixed, lists = [], [orgs, news, jobs]
    for i in range(max(len(x) for x in lists)):
        for lst in lists:
            if i < len(lst):
                mixed.append(lst[i])
    return Response({'count': len(mixed), 'results': mixed})


@api_view(['GET'])
@permission_classes([AllowAny])
def post_detail(request, pk):
    post = get_object_or_404(FeedPost, pk=pk, is_hidden=False)
    return Response(post_payload(request, post, request.user))


@api_view(['POST'])
def post_like(request, pk):
    post = get_object_or_404(FeedPost, pk=pk, is_hidden=False)
    if post.likes.filter(pk=request.user.pk).exists():
        post.likes.remove(request.user)
    else:
        post.likes.add(request.user)
    return Response({'liked': post.likes.filter(pk=request.user.pk).exists(), 'likes': post.likes.count()})


@api_view(['POST'])
def post_comment(request, pk):
    post = get_object_or_404(FeedPost, pk=pk, is_hidden=False)
    form = CommentForm({'text': request.data.get('text', '')})
    if not form.is_valid():
        return invalid(form)
    comment = form.save(commit=False)
    comment.post, comment.author = post, request.user
    staff = is_staff(request.user)
    comment.is_hidden = not staff  # publié après validation par Lantante (sauf équipe)
    comment.save()
    if not staff:
        notify_staff(f"Commentaire à valider de {request.user.public_name} : {comment.text[:120]}",
                     f"/lantanteAdminTech/Emploi/feedcomment/{comment.pk}/change/")
    return Response({**post_payload(request, post, request.user), 'comment_pending': not staff}, status=201)


# ─────────────────────────────
# Espace candidat
# ─────────────────────────────
@api_view(['GET', 'POST', 'PATCH'])
@parser_classes(JSON_AND_FILES)
@kinds('candidate', 'undefined')
def candidate_me(request):
    profile = candidate_profile(request.user)
    if request.method == 'GET':
        if not profile:
            return Response({'exists': False})
        return Response({'exists': True, **candidate_payload(request, profile, private=True),
                         'completion': _completion(profile), 'first_name': request.user.first_name,
                         'last_name': request.user.last_name})
    creating = profile is None
    before = None if creating else profile.snapshot()
    data = merged(CandidateForm, request.data, instance=profile, user=request.user)
    form = CandidateForm(data, request.FILES, instance=profile, user=request.user)
    if not form.is_valid():
        return invalid(form)
    profile = form.save()
    if request.user.account_type != 'candidate':
        request.user.account_type = 'candidate'
        request.user.save(update_fields=['account_type'])
    from ..models import ProfileRevision
    admin_url = f"/lantanteAdminTech/Emploi/candidateprofile/{profile.pk}/change/"
    if creating:
        notify_staff(f"Nouveau candidat inscrit : {profile.name} ({profile.headline})", admin_url)
    else:
        after = profile.snapshot()
        changed = [k for k in after if after[k] != before.get(k)]
        if changed:
            ProfileRevision.objects.create(candidate=profile, data=before, changed_fields=", ".join(changed)[:300])
            notify_staff(f"{profile.name} a modifié son profil ({', '.join(changed)})", admin_url)
    return Response({'exists': True, **candidate_payload(request, profile, private=True), 'completion': _completion(profile)},
                    status=201 if creating else 200)


def _completion(profile):
    checks = [bool(profile.user.avatar), bool(profile.bio.strip()), profile.skills.exists(), bool(profile.cv),
              profile.documents.exists(), bool(profile.phone or profile.user.phone)]
    return round(100 * sum(checks) / len(checks))


@api_view(['GET', 'POST'])
@parser_classes(JSON_AND_FILES)
@kinds('candidate')
def candidate_documents(request):
    profile = candidate_profile(request.user)
    if not profile:
        return error("Créez d'abord votre profil candidat.", 400, code='no_profile')
    if request.method == 'GET':
        return Response([document_payload(request, d) for d in profile.documents.all()])
    form = CandidateDocumentForm(request.data, request.FILES)
    if not form.is_valid():
        return invalid(form)
    doc = form.save(commit=False)
    doc.candidate = profile
    doc.save()
    notify_staff(f"{profile.name} a ajouté un document : {doc.title}",
                 f"/lantanteAdminTech/Emploi/candidateprofile/{profile.pk}/change/")
    return Response(document_payload(request, doc), status=201)


@api_view(['DELETE'])
@kinds('candidate')
def candidate_document_delete(request, pk):
    doc = get_object_or_404(CandidateDocument, pk=pk, candidate__user=request.user)
    doc.file.delete(save=False)
    doc.delete()
    return Response(status=204)


@api_view(['POST'])
@kinds('candidate')
def offer_apply(request, slug):
    offer = get_object_or_404(JobOffer, slug=slug, status='published')
    profile = candidate_profile(request.user)
    if not profile:
        return error("Créez d'abord votre profil candidat pour postuler.", 400, code='no_profile')
    if not offer.is_open:
        return error("Cette offre n'accepte plus de candidatures.", 400, code='closed')
    if not profile.cv:
        return error("Ajoutez d'abord votre CV (PDF) dans votre profil : il est envoyé avec chaque candidature.", 400, code='no_cv')
    form = ApplicationForm(request.data, offer=offer, profile=profile)
    if not form.is_valid():
        return invalid(form)
    application, created = actions.apply_to_offer(profile, offer, form.cleaned_data['text'],
                                                  form.cleaned_data.get('internship_duration', ''),
                                                  form.cleaned_data.get('available_from'))
    return Response({'created': created, 'application': application_payload(request, application)},
                    status=201 if created else 200)


@api_view(['GET'])
@kinds('candidate')
def candidate_applications(request):
    profile = candidate_profile(request.user)
    qs = profile.applications.select_related('offer__employer', 'request__employer').prefetch_related('slots', 'appointments') if profile else []
    return Response([application_payload(request, a) for a in qs])


@api_view(['POST'])
@kinds('candidate')
def application_availability(request, pk):
    application = get_object_or_404(Application.objects.select_related('offer', 'request', 'candidate__user'),
                                    pk=pk, candidate__user=request.user)
    if application.status not in ('shortlisted', 'interview'):
        return error("Cette candidature n'est pas à l'étape de l'entretien.", 400, code='wrong_step')
    slots = request.data.get('slots') or []
    form = AvailabilityForm({'slot1': slots[0] if len(slots) > 0 else '', 'slot2': slots[1] if len(slots) > 1 else '',
                             'slot3': slots[2] if len(slots) > 2 else '', 'note': request.data.get('note', '')})
    if not form.is_valid():
        return invalid(form)
    actions.submit_availability(application, form.slots(), form.cleaned_data.get('note', ''))
    return Response(application_payload(request, Application.objects.get(pk=pk)))


@api_view(['POST'])
@kinds('candidate')
def application_consent(request, pk):
    from .. import spontaneous as spont
    application = get_object_or_404(Application, pk=pk, candidate__user=request.user, consent='pending')
    accept = request.data.get('answer') == 'accept'
    spont.respond_consent(application, accept)
    if accept:
        from ..services import share_application
        share_application(application)
    return Response(application_payload(request, Application.objects.get(pk=pk)))


@api_view(['GET', 'POST'])
@kinds('candidate')
def spontaneous_list(request):
    profile = candidate_profile(request.user)
    if not profile:
        return error("Créez d'abord votre profil candidat.", 400, code='no_profile')
    if request.method == 'GET':
        return Response([spontaneous_payload(r) for r in profile.spontaneous_requests.all()])
    form = SpontaneousRequestForm(request.data, candidate=profile)
    if not form.is_valid():
        return invalid(form)
    req = form.save()
    notify_staff(f"Nouvelle demande spontanée : {profile.name} ({req.get_request_type_display()}, {req.get_domain_display()})",
                 f"/lantanteAdminTech/Emploi/spontaneousrequest/{req.pk}/change/")
    return Response(spontaneous_payload(req), status=201)


@api_view(['PATCH', 'DELETE'])
@kinds('candidate')
def spontaneous_item(request, pk):
    req = get_object_or_404(SpontaneousRequest, pk=pk, candidate__user=request.user)
    if request.method == 'DELETE':
        if req.is_open:
            req.status, req.withdrawn = 'closed', True
            req.save(update_fields=['status', 'withdrawn', 'updated_at'])
            notify_staff(f"{req.candidate.name} a retiré sa demande spontanée.",
                         f"/lantanteAdminTech/Emploi/spontaneousrequest/{req.pk}/change/")
        return Response(status=204)
    if not req.can_edit:
        return error("Cette demande ne peut plus être modifiée.", 400, code='locked')
    form = SpontaneousRequestForm(merged(SpontaneousRequestForm, request.data, instance=req, candidate=req.candidate),
                                  instance=req, candidate=req.candidate)
    if not form.is_valid():
        return invalid(form)
    return Response(spontaneous_payload(form.save()))


# ─────────────────────────────
# Espace entreprise
# ─────────────────────────────
@api_view(['GET', 'POST', 'PATCH'])
@parser_classes(JSON_AND_FILES)
@kinds('employer', 'undefined')
def employer_me(request):
    employer = employer_profile(request.user)
    if request.method == 'GET':
        if not employer:
            return Response({'exists': False})
        return Response({'exists': True, **company_payload(request, employer, detail=True), 'status': employer.status,
                         'status_label': employer.get_status_display(), 'decision_message': employer.decision_message,
                         'has_document': bool(employer.document), 'publishing_free': billing.employer_is_exempt(employer)})
    creating = employer is None
    form = EmployerForm(merged(EmployerForm, request.data, instance=employer), request.FILES, instance=employer)
    if not form.is_valid():
        return invalid(form)
    profile = form.save(commit=False)
    profile.user = request.user
    resubmitted = not creating and profile.status == 'rejected'
    if resubmitted:
        profile.status = 'pending'
    profile.save()
    if request.user.account_type != 'employer':
        request.user.account_type = 'employer'
        request.user.save(update_fields=['account_type'])
    url = f"/lantanteAdminTech/Emploi/employerprofile/{profile.pk}/change/"
    if creating:
        notify_staff(f"Nouvelle entreprise à vérifier : {profile.company_name}", url)
    elif resubmitted:
        notify_staff(f"Entreprise corrigée et renvoyée pour analyse : {profile.company_name}", url)
    return Response({'exists': True, **company_payload(request, profile, detail=True), 'status': profile.status},
                    status=201 if creating else 200)


def _approved(request):
    employer = employer_profile(request.user)
    return employer if employer and employer.is_approved else None


def _employer_applications(employer):
    return Application.objects.filter(Q(offer__employer=employer) | Q(request__employer=employer),
                                      shared_with_employer=True).select_related('candidate__user', 'offer', 'request') \
        .prefetch_related('slots', 'appointments', 'candidate__skills', 'candidate__documents')


@api_view(['GET'])
@kinds('employer')
def employer_applications(request):
    employer = _approved(request)
    if not employer:
        return error("Votre entreprise doit d'abord être acceptée par Lantante.", 403, code='not_approved')
    JobOffer.close_expired()
    base = _employer_applications(employer)
    if request.query_params.get('offer', '').isdigit():
        base = base.filter(offer_id=int(request.query_params['offer']))
    tabs = {'new': base.filter(status='received'), 'progress': base.filter(status__in=('shortlisted', 'interview')),
            'hired': base.filter(status='hired'), 'refused': base.filter(status='refused'), 'all': base}
    tab = request.query_params.get('tab') or 'new'
    items = tabs.get(tab, tabs['new'])
    resp = paginate(request, items, lambda a: application_payload(request, a, for_employer=True))
    resp.data['counts'] = {k: v.count() for k, v in tabs.items()}
    return resp


def _my_application(request, pk):
    employer = employer_profile(request.user)
    application = get_object_or_404(Application.objects.select_related('candidate__user', 'offer', 'request'), pk=pk,
                                    shared_with_employer=True)
    if not employer or application.employer != employer:
        raise Http404
    return application


@api_view(['GET'])
@kinds('employer')
def employer_application_detail(request, pk):
    return Response(application_payload(request, _my_application(request, pk), for_employer=True))


@api_view(['POST'])
@kinds('employer')
def employer_decide(request, pk):
    application = _my_application(request, pk)
    action = request.data.get('action')
    if action not in actions.DECISIONS:
        return error("Action inconnue (shortlist, accept ou refuse).", 400, code='invalid')
    actions.decide_application(application, action, str(request.data.get('message', '')))
    return Response(application_payload(request, Application.objects.get(pk=pk), for_employer=True))


@api_view(['POST'])
@kinds('employer')
def employer_schedule(request, pk):
    application = _my_application(request, pk)
    when = parse_datetime(str(request.data.get('when', '')))
    if not when:
        return error("Choisissez la date et l'heure de l'entretien.", 400, code='invalid')
    if timezone.is_naive(when):
        when = timezone.make_aware(when)
    if when < timezone.now():
        return error("Choisissez une date à venir.", 400, code='invalid')
    appt = actions.schedule_interview(application, when, str(request.data.get('place', '')), str(request.data.get('notes', '')))
    return Response(appointment_payload(appt), status=201)


@api_view(['GET'])
@kinds('employer')
def employer_offers(request):
    employer = employer_profile(request.user)
    JobOffer.close_expired()
    qs = employer.offers.filter(status__in=['pending', 'published', 'awaiting_payment']) if employer else []
    return Response([{**offer_payload(request, o), 'applications': o.applications.count()} for o in qs])


@api_view(['POST'])
@kinds('employer')
def offer_filled(request, slug):
    offer = get_object_or_404(JobOffer, slug=slug, employer__user=request.user)
    if offer.status != 'filled':
        offer.status = 'filled'
        offer.save(update_fields=['status', 'updated_at'])
        pending = offer.applications.filter(status='received').count()
        notify_staff(f"Poste pourvu : « {offer.title} » ({offer.company_name}). {pending} candidature(s) encore en attente à traiter.",
                     f"/lantanteAdminTech/Emploi/application/?offer__id__exact={offer.pk}&traitement=pending")
    return Response(offer_payload(request, offer))


# ─────────────────────────────
# Publications payantes (entreprise et particulier)
# ─────────────────────────────
def _publisher(request):
    kind = account_kind(request.user)
    if kind == 'member':
        return None, ServicePlan.MEMBER_KINDS, True
    employer = _approved(request)
    return employer, ServicePlan.EMPLOYER_KINDS, bool(employer)


@api_view(['GET'])
@kinds('employer', 'member')
def publish_plans(request):
    employer, plan_kinds, ok = _publisher(request)
    if not ok:
        return error("Votre entreprise doit d'abord être acceptée par Lantante pour publier.", 403, code='not_approved')
    plans = ServicePlan.objects.filter(is_active=True, kind__in=plan_kinds)
    return Response({'exempt': billing.employer_is_exempt(employer), 'plans': [plan_payload(p) for p in plans]})


@api_view(['GET', 'POST'])
@parser_classes(JSON_AND_FILES)
@kinds('employer', 'member')
def orders(request):
    employer, plan_kinds, ok = _publisher(request)
    if request.method == 'GET':
        qs = request.user.publication_orders.exclude(status='cancelled').select_related('plan')
        return Response([order_payload(request, o) for o in qs])
    if not ok:
        return error("Votre entreprise doit d'abord être acceptée par Lantante pour publier.", 403, code='not_approved')
    plan = get_object_or_404(ServicePlan, code=request.data.get('plan'), is_active=True, kind__in=plan_kinds)
    if plan.kind == 'job':
        form = JobOfferForm(request.data, request.FILES)
        if not form.is_valid():
            return invalid(form)
        offer = form.save(commit=False)
        offer.employer = employer
        offer.status = 'awaiting_payment'
        offer.save()
        form.save_skills(offer)
        order = billing.create_order(plan, request.user, employer, title=offer.title, job_offer=offer)
    elif plan.kind == 'recruit':
        form = StaffingRequestForm(request.data)
        if not form.is_valid():
            return invalid(form)
        req = form.save(commit=False)
        req.employer = employer
        req.save()
        form.save_skills(req)
        notify_staff(f"Demande de recrutement : {req.title} ({employer.company_name})",
                     f"/lantanteAdminTech/Emploi/staffingrequest/{req.pk}/change/")
        order = billing.create_order(plan, request.user, employer, title=req.title, staffing_request=req)
    elif plan.kind == 'job_boost':
        form = OfferBoostForm(request.data, employer=employer)
        if not form.is_valid():
            return invalid(form)
        offer = form.cleaned_data['offer']
        order = billing.create_order(plan, request.user, employer, title=offer.title, boosted_offer=offer)
    else:
        form = OrderContentForm(request.data, request.FILES, plan=plan)
        if not form.is_valid():
            return invalid(form)
        content = {k: v for k, v in form.cleaned_data.items() if v not in (None, '')}
        order = billing.create_order(plan, request.user, employer, **content)
    return Response(order_payload(request, order), status=201)


def _my_order(request, pk):
    return get_object_or_404(PublicationOrder.objects.select_related('plan', 'employer'), pk=pk, user=request.user)


@api_view(['GET', 'PATCH'])
@parser_classes(JSON_AND_FILES)
@kinds('employer', 'member')
def order_item(request, pk):
    order = _my_order(request, pk)
    if request.method == 'GET':
        return Response(order_payload(request, order))
    if not order.can_edit:
        return error("Cette publication ne peut plus être modifiée.", 400, code='locked')
    kind = order.plan.kind
    if kind == 'job' and order.job_offer:
        form = JobOfferForm(merged(JobOfferForm, request.data, instance=order.job_offer), request.FILES, instance=order.job_offer)
    elif kind == 'recruit' and order.staffing_request:
        form = StaffingRequestForm(merged(StaffingRequestForm, request.data, instance=order.staffing_request),
                                   instance=order.staffing_request)
    elif kind == 'job_boost':
        return error("Cette commande ne se modifie pas.", 400, code='locked')
    else:
        form = OrderContentForm(merged(OrderContentForm, request.data, instance=order, plan=order.plan), request.FILES, instance=order)
    if not form.is_valid():
        return invalid(form)
    saved = form.save()
    if hasattr(form, 'save_skills'):
        form.save_skills(saved)
    if kind == 'job' and order.job_offer:
        order.title = order.job_offer.title
        order.save(update_fields=['title'])
    billing.resubmit(order)
    return Response(order_payload(request, PublicationOrder.objects.get(pk=pk)))


@api_view(['POST'])
@kinds('employer', 'member')
def order_pay(request, pk):
    order = _my_order(request, pk)
    if not order.can_pay:
        return error("Cette commande n'attend pas de paiement.", 400, code='not_payable')
    form = PaymentForm(request.data)
    if not form.is_valid():
        return invalid(form)
    billing.declare_payment(order, form.cleaned_data['payment_method'], form.cleaned_data['payer_phone'],
                            form.cleaned_data['payment_reference'])
    return Response(order_payload(request, PublicationOrder.objects.get(pk=pk)))


@api_view(['POST'])
@kinds('employer', 'member')
def order_cancel(request, pk):
    order = _my_order(request, pk)
    billing.cancel_order(order)
    return Response(order_payload(request, PublicationOrder.objects.get(pk=pk)))


@api_view(['GET'])
@kinds('employer', 'member')
def order_receipt(request, pk):
    order = _my_order(request, pk)
    if not order.paid_at:
        return error("Le reçu est disponible après confirmation du paiement.", 400, code='no_receipt')
    return Response({'receipt_number': order.receipt_number, 'paid_at': order.paid_at.isoformat(), 'owner': order.owner_name,
                     'service': order.plan.name, 'title': order.title, 'reference': order.reference,
                     'payment_method': order.get_payment_method_display(), 'payment_reference': order.payment_reference,
                     'amount': order.amount, 'amount_label': order.amount_label})


# ─────────────────────────────
# Messagerie, rendez-vous, notifications
# ─────────────────────────────
def _conversation_filter(user):
    return (Q(participants=user) | Q(kind='support')) if is_staff(user) else Q(participants=user)


@api_view(['GET', 'POST'])
def conversations(request):
    user = request.user
    if request.method == 'GET':
        qs = Conversation.objects.filter(_conversation_filter(user)).distinct().prefetch_related('participants', 'messages')
        return Response([conversation_payload(c, user) for c in qs])
    form = NewConversationForm({'subject': request.data.get('subject', ''), 'body': request.data.get('body', '')})
    if not form.is_valid():
        return invalid(form)
    if request.data.get('support'):
        if is_staff(user):
            return error("L'équipe répond depuis l'administration.", 400, code='invalid')
        existing = Conversation.objects.filter(participants=user, kind='support').exclude(status='closed').first()
        if existing:
            conv = existing
            msg = Message.objects.create(conversation=conv, sender=user, body=form.cleaned_data['body'])
            msg.read_by.add(user)
            conv.save()
            for person in ([conv.assigned_to] if conv.assigned_to_id else list(staff_users())):
                notify(person, f"Nouveau message de {user.public_name} (service client)", f"/emploi/messages/{conv.pk}/")
        else:
            conv = Conversation.objects.create(subject=form.cleaned_data['subject'], kind='support')
            conv.participants.add(user)
            msg = Message.objects.create(conversation=conv, sender=user, body=form.cleaned_data['body'])
            msg.read_by.add(user)
            send_auto_ack(conv)
            for person in staff_users():
                notify(person, f"Nouveau message de {user.public_name} (service client) — à prendre en charge",
                       f"/emploi/messages/{conv.pk}/")
        return Response(conversation_payload(conv, user, with_messages=True), status=201)
    other = get_object_or_404(User, pk=request.data.get('user_id'), is_active=True)
    if other.pk == user.pk:
        return error("Vous ne pouvez pas vous écrire à vous-même.", 400, code='invalid')
    conv = _direct_message(user, other, form.cleaned_data['subject'], form.cleaned_data['body'])
    return Response(conversation_payload(conv, user, with_messages=True), status=201)


def _direct_message(user, other, subject, body):
    """Écrit à une autre personne (la conversation existante est reprise) et la prévient."""
    conv = Conversation.objects.filter(kind='direct').annotate(n=Count('participants', distinct=True)).filter(n=2) \
        .filter(participants=user).filter(participants=other).first()
    if not conv:
        conv = Conversation.objects.create(subject=subject)
        conv.participants.add(user, other)
    msg = Message.objects.create(conversation=conv, sender=user, body=body)
    msg.read_by.add(user)
    conv.save()
    notify_partner_message(other, user, body, f"/emploi/messages/{conv.pk}/")
    return conv


@api_view(['POST'])
def partner_message(request, pk):
    """Écrire à un partenaire : le message va directement chez lui (partenaire = entreprise), pas chez Lantante."""
    partner = get_object_or_404(Partner, pk=pk, is_active=True)
    form = NewConversationForm({'subject': request.data.get('subject', '') or f"Message pour {partner.name}",
                                'body': request.data.get('body', '')})
    if not form.is_valid():
        return invalid(form)
    other = partner_recipient(partner)
    if other is None:
        return error("Ce partenaire ne peut pas être contacté dans l'application. Utilisez ses coordonnées directes.",
                     400, code='no_contact')
    if other.pk == request.user.pk:
        return error("Vous ne pouvez pas vous écrire à vous-même.", 400, code='invalid')
    conv = _direct_message(request.user, other, form.cleaned_data['subject'], form.cleaned_data['body'])
    return Response(conversation_payload(conv, request.user, with_messages=True), status=201)


@api_view(['GET'])
def conversation_detail(request, pk):
    conv = get_object_or_404(Conversation.objects.filter(_conversation_filter(request.user)).distinct(), pk=pk)
    for msg in conv.messages.exclude(sender=request.user).exclude(read_by=request.user):
        msg.read_by.add(request.user)
    return Response(conversation_payload(conv, request.user, with_messages=True))


@api_view(['POST'])
def conversation_send(request, pk):
    user = request.user
    conv = get_object_or_404(Conversation.objects.select_related('assigned_to').filter(_conversation_filter(user)).distinct(), pk=pk)
    form = MessageForm({'body': request.data.get('body', '')})
    if not form.is_valid():
        return invalid(form)
    support, staff_me = conv.kind == 'support', is_staff(user)
    if support and staff_me:
        return error("L'équipe répond depuis le site.", 403, code='wrong_account_type')
    msg = Message.objects.create(conversation=conv, sender=user, body=form.cleaned_data['body'])
    msg.read_by.add(user)
    if support and conv.status == 'closed':
        conv.status = 'assigned' if conv.assigned_to_id else 'new'
    conv.save()
    url = f"/emploi/messages/{conv.pk}/"
    if support:
        for person in ([conv.assigned_to] if conv.assigned_to_id else list(staff_users())):
            notify(person, f"Nouveau message de {user.public_name} (service client)", url)
    else:
        for other in conv.other_participants(user):
            notify(other, f"Nouveau message de {user.public_name}", url)
    return Response(conversation_payload(conv, user, with_messages=True), status=201)


@api_view(['GET'])
def appointments(request):
    qs = Appointment.objects.none()
    profile, employer = candidate_profile(request.user), employer_profile(request.user)
    if profile:
        qs = qs | Appointment.objects.filter(candidate=profile)
    if employer:
        qs = qs | Appointment.objects.filter(employer=employer)
    return Response([appointment_payload(a) for a in qs.select_related('candidate__user', 'employer').distinct()])


@api_view(['POST'])
@kinds('candidate')
def appointment_respond(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, candidate__user=request.user)
    action = request.data.get('action')
    if appt.status in ('proposed', 'confirmed') and action in ('confirm', 'decline'):
        appt.status = 'confirmed' if action == 'confirm' else 'declined'
        appt.save()
        verb = "confirmé" if action == 'confirm' else "décliné"
        text = f"{appt.candidate.name} a {verb} le rendez-vous « {appt.title} » du {timezone.localtime(appt.scheduled_at):%d/%m %H:%M}"
        if appt.employer_id:
            notify(appt.employer.user, text, '/emploi/candidatures-recues/')
        else:
            notify_staff(text, f"/lantanteAdminTech/Emploi/appointment/{appt.pk}/change/")
    return Response(appointment_payload(appt))


@api_view(['GET', 'POST'])
def notifications(request):
    if request.method == 'POST':
        request.user.emploi_notifications.filter(is_read=False).update(is_read=True)
        return Response(status=204)
    return paginate(request, request.user.emploi_notifications.all(), notification_payload, per_page=30)


# ─────────────────────────────
# Fichiers privés (CV, documents) : accès contrôlé, jamais d'adresse publique
# ─────────────────────────────
@api_view(['GET'])
def candidate_cv(request, pk):
    candidate = get_object_or_404(CandidateProfile, pk=pk)
    if not candidate.cv or not can_see_private(request.user, candidate):
        return error("Accès non autorisé à ce CV.", 403, code='forbidden')
    try:
        return FileResponse(candidate.cv.open('rb'), content_type='application/pdf')
    except FileNotFoundError:
        raise Http404


@api_view(['GET'])
def document_file(request, pk):
    doc = get_object_or_404(CandidateDocument.objects.select_related('candidate'), pk=pk)
    if not can_see_private(request.user, doc.candidate):
        return error("Accès non autorisé à ce document.", 403, code='forbidden')
    try:
        return FileResponse(doc.file.open('rb'), filename=doc.file.name.rsplit('/', 1)[-1])
    except FileNotFoundError:
        raise Http404


@api_view(['GET'])
@kinds('employer')
def candidate_detail(request, pk):
    """Une entreprise ne voit que les candidats qui ont postulé chez elle."""
    candidate = get_object_or_404(CandidateProfile.objects.select_related('user'), pk=pk)
    if not can_see_private(request.user, candidate):
        return error("Les profils des candidats sont masqués : vous voyez ceux qui ont postulé à vos offres.", 403, code='masked')
    return Response(candidate_payload(request, candidate, private=True))


# ─────────────────────────────
# Tableau de bord (synthèse pour l'écran d'accueil de l'application)
# ─────────────────────────────
@api_view(['GET'])
def dashboard(request):
    user = request.user
    kind = account_kind(user)
    data = {'user': user_payload(request, user), **counters(user), 'kind': kind}
    profile, employer = candidate_profile(user), employer_profile(user)
    if kind == 'candidate' and profile:
        data['completion'] = _completion(profile)
        data['applications'] = profile.applications.count()
        data['upcoming_appointments'] = profile.appointments.filter(scheduled_at__gte=timezone.now()).exclude(
            status__in=['declined', 'cancelled']).count()
        data['shortlisted'] = [application_payload(request, a) for a in
                               profile.applications.filter(status='shortlisted', slots__isnull=True).distinct()]
        data['pending_consent'] = [application_payload(request, a) for a in profile.applications.filter(consent='pending')]
    if kind == 'employer' and employer:
        data['company_status'] = employer.status
        data['offers'] = employer.offers.filter(status__in=['pending', 'published']).count()
    return Response(data)

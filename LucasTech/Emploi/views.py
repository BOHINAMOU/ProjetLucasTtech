from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Q, Value, When
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Partner

from . import spontaneous as spont
from .forms import (
    OfferBoostForm, SpontaneousRequestForm, OrderContentForm, PaymentForm, ApplicationForm, AvailabilityForm, CandidateDocumentForm, CandidateForm, CommentForm, EmployerForm, FeedPostForm,
    JobOfferForm, MessageForm, NewConversationForm, StaffingRequestForm,
)
from .models import (
    SpontaneousRequest, PublicationOrder, ServicePlan, Appointment, Application, AvailabilitySlot, CandidateDocument, CandidateProfile, Conversation, DOMAIN_CHOICES,
    CONTRACT_CHOICES, EmployerProfile, FeedComment, FeedPost, JobOffer, Message,
    Notification, ProfileRevision, StaffingRequest,
)
from functools import wraps

from . import actions, billing
from .services import (
    account_kind, assign_conversation, can_browse_candidates, notify_application_status, share_application, can_see_private, is_staff, notify, notify_staff,
    send_auto_ack, send_intro, staff_full_name, staff_users,
)

User = get_user_model()


def _space(allowed, label):
    """Réserve une page à un type de compte. Chaque compte a son propre espace, ses menus et ses droits."""
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if account_kind(request.user) not in allowed:
                messages.info(request, f"Cette page est réservée aux comptes {label}. "
                                       "Un compte candidat et un compte entreprise sont deux espaces distincts.")
                return redirect('emploi:dashboard')
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


candidate_space = _space(('candidate', 'undefined'), "candidats")
employer_space = _space(('employer', 'undefined'), "entreprises")
publisher_space = _space(('employer', 'member'), "entreprises et aux particuliers qui publient")


def _qs(request):
    """Filtres de l'URL sans « page », pour les garder en changeant de page."""
    params = request.GET.copy()
    params.pop('page', None)
    encoded = params.urlencode()
    return encoded + '&' if encoded else ''


def _qs(request):
    """Filtres de l'URL sans « page », pour garder les filtres en changeant de page."""
    params = request.GET.copy()
    params.pop("page", None)
    encoded = params.urlencode()
    return encoded + "&" if encoded else ""


def _page(request, queryset, per_page=12):
    return Paginator(queryset, per_page).get_page(request.GET.get('page'))


def _open_offers():
    JobOffer.close_expired()  # date de fin dépassée : l'offre disparaît
    JobOffer.expire_featured()  # mise en avant terminée
    today = timezone.localdate()
    return JobOffer.objects.filter(status='published').filter(
        Q(deadline__isnull=True) | Q(deadline__gte=today)
    ).filter(Q(employer__isnull=True) | Q(employer__status='approved')).select_related('employer', 'employer__partner')


# ─────────────────────────────
# 🏠 ACCUEIL
# ─────────────────────────────
def _employer_redirect(request, text="Les offres d'emploi sont réservées aux candidats : votre espace est ici."):
    messages.info(request, text)
    return redirect('emploi:dashboard')


def home(request):
    if account_kind(request.user) in ('employer', 'member'):
        return redirect('emploi:dashboard')  # entreprise et particulier arrivent directement dans leur espace
    offers = _open_offers()
    context = {
        'partner_list': Partner.objects.filter(is_active=True),
        'latest_offers': offers[:6],
        'offers_count': offers.count(),
        'candidates_count': CandidateProfile.objects.filter(is_published=True).count(),
        'companies_count': EmployerProfile.objects.filter(status='approved').count(),
        'posts': FeedPost.objects.filter(is_hidden=False).select_related('author')[:3],
        'partner_posts': FeedPost.objects.filter(
            is_hidden=False, author__employer_profile__partner__isnull=False,
            author__employer_profile__status='approved',
        ).select_related('author', 'author__employer_profile')[:6],
        'has_candidate': request.user.is_authenticated and hasattr(request.user, 'candidate_profile'),
        'has_employer': request.user.is_authenticated and hasattr(request.user, 'employer_profile'),
        'domains': DOMAIN_CHOICES,
    }
    return render(request, 'emploi/home.html', context)


# ─────────────────────────────
# 💼 OFFRES
# ─────────────────────────────
def offer_list(request):
    if account_kind(request.user) in ('employer', 'member'):
        return _employer_redirect(request)
    qs = _open_offers()
    q = request.GET.get('q', '').strip()
    domain = request.GET.get('domain', '')
    contract = request.GET.get('contract', '')
    city = request.GET.get('city', '').strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(skills__name__icontains=q)).distinct()
    if domain:
        qs = qs.filter(domain=domain)
    if contract:
        qs = qs.filter(contract=contract)
    if city:
        qs = qs.filter(city__icontains=city)
    return render(request, 'emploi/offer_list.html', {
        'page': _page(request, qs), 'qs': _qs(request), 'q': q, 'domain': domain, 'contract': contract, 'city': city,
        'domains': DOMAIN_CHOICES, 'contracts': CONTRACT_CHOICES,
    })


def offer_detail(request, slug, form=None):
    offer = get_object_or_404(JobOffer.objects.select_related('employer'), slug=slug)
    owner = request.user.is_authenticated and offer.employer_id and offer.employer.user_id == request.user.pk
    if offer.status != 'published' and not (owner or is_staff(request.user)):
        raise Http404
    if account_kind(request.user) in ('employer', 'member') and not (owner or is_staff(request.user)):
        return _employer_redirect(request)
    applied = False
    profile = getattr(request.user, 'candidate_profile', None) if request.user.is_authenticated else None
    if profile:
        applied = Application.objects.filter(candidate=profile, offer=offer).exists()
    return render(request, 'emploi/offer_detail.html', {
        'offer': offer, 'applied': applied, 'profile': profile,
        'form': form or ApplicationForm(offer=offer, profile=profile), 'owner': owner,
    })


@candidate_space
@require_POST
def offer_apply(request, slug):
    offer = get_object_or_404(JobOffer, slug=slug, status='published')
    profile = getattr(request.user, 'candidate_profile', None)
    if not profile:
        messages.info(request, "Créez d'abord votre profil candidat pour postuler.")
        return redirect('emploi:candidate_edit')
    if not offer.is_open:
        messages.error(request, "Cette offre n'accepte plus de candidatures.")
        return redirect(offer)
    if not profile.cv:
        messages.error(request, "Ajoutez d'abord votre CV (PDF) dans votre profil : il est envoyé avec chaque candidature.")
        return redirect('emploi:candidate_edit')
    form = ApplicationForm(request.POST, offer=offer, profile=profile)
    if not form.is_valid():
        return offer_detail(request, slug, form=form)
    text = form.cleaned_data['text']
    application, created = actions.apply_to_offer(
        profile, offer, text, form.cleaned_data.get('internship_duration', ''), form.cleaned_data.get('available_from'))
    if created:
        if offer.employer_id:
            messages.success(request, "✓ Candidature envoyée directement à l'entreprise. Vous serez prévenu de sa réponse.")
        else:
            messages.success(request, "✓ Candidature envoyée à Lantante, qui étudie votre dossier. Vous serez prévenu.")
    else:
        messages.info(request, "Vous avez déjà postulé à cette offre.")
    return redirect(offer)


# ─────────────────────────────
# 👥 CANDIDATS (annuaire réservé à Lantante et aux entreprises acceptées)
# ─────────────────────────────
def _directory_denied(request):
    """Redirection si la personne n'a pas le droit de parcourir les candidats."""
    if not request.user.is_authenticated:
        return redirect(f"/users/connexion/?next={request.path}")
    messages.info(request, "Les profils des candidats sont masqués : vous voyez ceux qui ont postulé à vos offres, dans « Candidatures ».")
    return redirect('emploi:home')


def candidate_list(request):
    if not can_browse_candidates(request.user):
        return _directory_denied(request)
    qs = CandidateProfile.objects.filter(is_published=True).select_related('user').prefetch_related('skills').order_by('-updated_at')
    q = request.GET.get('q', '').strip()
    domain = request.GET.get('domain', '')
    city = request.GET.get('city', '').strip()
    stage = request.GET.get('stage') == '1'
    if stage:
        qs = qs.filter(seeking_internship=True)
    if q:
        qs = qs.filter(Q(headline__icontains=q) | Q(skills__name__icontains=q)).distinct()
    if domain:
        qs = qs.filter(domain=domain)
    if city:
        qs = qs.filter(city__icontains=city, show_city=True)
    return render(request, 'emploi/candidate_list.html', {
        'page': _page(request, qs), 'qs': _qs(request), 'q': q, 'domain': domain, 'city': city, 'stage': stage,
        'domains': DOMAIN_CHOICES,
    })


def candidate_detail(request, pk):
    candidate = get_object_or_404(CandidateProfile.objects.select_related('user'), pk=pk)
    is_owner = request.user.is_authenticated and candidate.user_id == request.user.pk
    if not is_owner and not can_see_private(request.user, candidate):
        return _directory_denied(request)  # profil masqué sauf pour celui qui a reçu sa candidature
    if not candidate.is_published and not can_see_private(request.user, candidate):
        raise Http404
    return render(request, 'emploi/candidate_detail.html', {
        'candidate': candidate,
        'private_ok': can_see_private(request.user, candidate),
        'is_me': request.user.is_authenticated and candidate.user_id == request.user.pk,
    })


@candidate_space
def availability(request, pk):
    """Le candidat présélectionné indique quand il est disponible pour l'entretien."""
    application = get_object_or_404(Application.objects.select_related('offer', 'request', 'candidate__user'),
                                    pk=pk, candidate__user=request.user)
    if application.status not in ('shortlisted', 'interview'):
        messages.info(request, "Cette candidature n'est pas à l'étape de l'entretien.")
        return redirect('emploi:dashboard')
    existing = list(application.slots.all())
    initial = {f'slot{i}': slot.start.astimezone(timezone.get_current_timezone()).strftime('%Y-%m-%dT%H:%M')
               for i, slot in enumerate(existing[:3], start=1)}
    if existing:
        initial['note'] = existing[0].note
    form = AvailabilityForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        actions.submit_availability(application, form.slots(), form.cleaned_data.get('note', ''))
        messages.success(request, "✓ Merci ! Lantante vous confirme la date de l'entretien très vite.")
        return redirect('emploi:dashboard')
    return render(request, 'emploi/availability.html', {'form': form, 'application': application,
                                                       'target': application.offer or application.request})


@candidate_space
def documents(request):
    """Diplômes et pièces du candidat : déposés une fois, joints à toutes ses candidatures."""
    profile = getattr(request.user, 'candidate_profile', None)
    if not profile:
        messages.info(request, "Créez d'abord votre profil candidat.")
        return redirect('emploi:candidate_edit')
    form = CandidateDocumentForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        doc = form.save(commit=False)
        doc.candidate = profile
        doc.save()
        notify_staff(f"{profile.name} a ajouté un document : {doc.title}",
                     f"/lantanteAdminTech/Emploi/candidateprofile/{profile.pk}/change/")
        messages.success(request, "✓ Document ajouté. Il sera joint à vos candidatures.")
        return redirect('emploi:documents')
    return render(request, 'emploi/documents.html', {
        'form': form, 'profile': profile, 'docs': profile.documents.all(),
    })


@candidate_space
@require_POST
def document_delete(request, pk):
    doc = get_object_or_404(CandidateDocument, pk=pk, candidate__user=request.user)
    doc.file.delete(save=False)
    doc.delete()
    messages.success(request, "Document supprimé.")
    return redirect('emploi:documents')


@login_required
def document_download(request, pk):
    doc = get_object_or_404(CandidateDocument.objects.select_related('candidate'), pk=pk)
    if not can_see_private(request.user, doc.candidate):
        return HttpResponseForbidden("Accès non autorisé à ce document.")
    try:
        return FileResponse(doc.file.open('rb'), filename=doc.file.name.rsplit('/', 1)[-1])
    except FileNotFoundError:
        raise Http404


@login_required
def cv_download(request, pk):
    candidate = get_object_or_404(CandidateProfile, pk=pk)
    if not candidate.cv or not can_see_private(request.user, candidate):
        return HttpResponseForbidden("Accès non autorisé à ce CV.")
    try:
        response = FileResponse(candidate.cv.open('rb'), content_type='application/pdf')
    except FileNotFoundError:
        raise Http404
    response['Content-Disposition'] = f'inline; filename="CV-{candidate.pk}.pdf"'
    return response


# ─────────────────────────────
# 🏢 ENTREPRISES
# ─────────────────────────────
def company_list(request):
    qs = EmployerProfile.objects.filter(status='approved').annotate(
        n_offers=Count('offers', filter=Q(offers__status='published'))).order_by('-is_verified', 'company_name')
    return render(request, 'emploi/company_list.html', {'page': _page(request, qs)})


def company_detail(request, pk):
    company = get_object_or_404(EmployerProfile, pk=pk)
    me = request.user.is_authenticated and company.user_id == request.user.pk
    if not company.is_approved and not (me or is_staff(request.user)):
        raise Http404
    offers = _open_offers().filter(employer=company)
    posts = FeedPost.objects.filter(author=company.user, is_hidden=False)[:5]
    return render(request, 'emploi/company_detail.html', {
        'company': company, 'offers': offers, 'posts': posts, 'is_me': me,
        'hide_offers': account_kind(request.user) in ('employer', 'member') and not me,
    })


@login_required
def employer_document(request, pk):
    employer = get_object_or_404(EmployerProfile, pk=pk)
    if not employer.document or not (is_staff(request.user) or employer.user_id == request.user.pk):
        return HttpResponseForbidden("Accès non autorisé à ce document.")
    try:
        return FileResponse(employer.document.open('rb'), as_attachment=True,
                            filename=employer.document.name.rsplit('/', 1)[-1])
    except FileNotFoundError:
        raise Http404


# ─────────────────────────────
# 🧭 MON ESPACE
# ─────────────────────────────
@login_required
@require_POST
def choose_member(request):
    """Un compte sans type choisit « particulier » (publier une actualité ou une annonce)."""
    if account_kind(request.user) == 'undefined':
        request.user.account_type = 'member'
        request.user.save(update_fields=['account_type'])
        messages.success(request, "✓ Espace particulier activé : vous pouvez publier une actualité ou une annonce.")
    return redirect('emploi:dashboard')


@login_required
def dashboard(request):
    user = request.user
    candidate = getattr(user, 'candidate_profile', None)
    employer = getattr(user, 'employer_profile', None)
    context = {'kind': account_kind(user), 'candidate': candidate, 'employer': employer,
               'member_orders': user.publication_orders.exclude(status='cancelled')[:8] if account_kind(user) == 'member' else [],
               'my_warnings': list(user.moderation_warnings.filter(is_active=True)[:3])}
    if candidate:
        checks = [
            ("Photo de profil", bool(user.avatar), reverse('emploi:candidate_edit')),
            ("À propos de vous", bool(candidate.bio.strip()), reverse('emploi:candidate_edit')),
            ("Compétences", candidate.skills.exists(), reverse('emploi:candidate_edit')),
            ("CV (PDF)", bool(candidate.cv), reverse('emploi:candidate_edit')),
            ("Diplômes et documents", candidate.documents.exists(), reverse('emploi:documents')),
            ("Téléphone", bool(candidate.phone or user.phone), reverse('emploi:candidate_edit')),
        ]
        context['checks'] = checks
        context['completion'] = round(100 * sum(1 for _, done, _ in checks if done) / len(checks))
        context['apps_count'] = candidate.applications.count()
        context['spontaneous'] = candidate.spontaneous_requests.exclude(status__in=('closed', 'rejected')).filter(withdrawn=False)[:5]
        context['applications'] = candidate.applications.select_related('offer', 'request')[:10]
        context['appointments'] = candidate.appointments.filter(
            scheduled_at__gte=timezone.now()).exclude(status__in=['declined', 'cancelled'])[:5]
    if employer:
        context['orders'] = employer.orders.exclude(status='cancelled')[:8]
        JobOffer.close_expired()
        # Seules les offres en cours : une offre terminée (date de fin ou poste pourvu) disparaît de l'espace.
        context['offers'] = employer.offers.filter(status__in=['pending', 'published'])[:20]
        context['staffing'] = employer.requests.exclude(status__in=['filled', 'cancelled'])[:20]
        context['offer_apps'] = Application.objects.filter(
            Q(offer__employer=employer) | Q(request__employer=employer), shared_with_employer=True
        ).exclude(offer__status__in=['filled', 'closed']).exclude(request__status__in=['filled', 'cancelled']).select_related('candidate__user', 'offer', 'request')[:15]
    return render(request, 'emploi/dashboard.html', context)


@candidate_space
def candidate_edit(request):
    profile = getattr(request.user, 'candidate_profile', None)
    creating = profile is None
    before = None if creating else profile.snapshot()
    form = CandidateForm(request.POST or None, request.FILES or None, instance=profile, user=request.user)
    if request.method == 'POST' and form.is_valid():
        profile = form.save()
        if request.user.account_type != 'candidate':
            request.user.account_type = 'candidate'
            request.user.save(update_fields=['account_type'])
        admin_url = f"/lantanteAdminTech/Emploi/candidateprofile/{profile.pk}/change/"
        if creating:
            notify_staff(f"Nouveau candidat inscrit : {profile.name} ({profile.headline})", admin_url)
            messages.success(request, "✓ Votre profil est créé. Ajoutez maintenant votre CV et vos compétences !")
        else:
            after = profile.snapshot()
            changed = [k for k in after if after[k] != before.get(k)]
            if changed:
                ProfileRevision.objects.create(candidate=profile, data=before,
                                               changed_fields=", ".join(changed)[:300])
                notify_staff(f"{profile.name} a modifié son profil ({', '.join(changed)})", admin_url)
            messages.success(request, "✓ Profil mis à jour.")
        return redirect('emploi:dashboard')
    return render(request, 'emploi/candidate_form.html', {'form': form, 'creating': creating, 'profile': profile})


@employer_space
def employer_edit(request):
    profile = getattr(request.user, 'employer_profile', None)
    creating = profile is None
    form = EmployerForm(request.POST or None, request.FILES or None, instance=profile, user=request.user)
    if request.method == 'POST' and form.is_valid():
        employer = form.save(commit=False)
        employer.user = request.user
        resubmitted = not creating and employer.status == 'rejected'
        if resubmitted:
            employer.status = 'pending'
        employer.save()
        if request.user.account_type != 'employer':
            request.user.account_type = 'employer'
            request.user.save(update_fields=['account_type'])
        if resubmitted:
            notify_staff(f"Entreprise corrigée et renvoyée pour analyse : {employer.company_name}",
                         f"/lantanteAdminTech/Emploi/employerprofile/{employer.pk}/change/")
            messages.success(request, "✓ Fiche renvoyée : Lantante l'analyse de nouveau.")
        elif creating:
            notify_staff(f"Nouvelle entreprise à vérifier : {employer.company_name}",
                         f"/lantanteAdminTech/Emploi/employerprofile/{employer.pk}/change/")
            messages.success(request, "✓ Entreprise enregistrée. Lantante analyse votre fiche et vous répond bientôt.")
        else:
            messages.success(request, "✓ Fiche entreprise mise à jour.")
        return redirect('emploi:dashboard')
    return render(request, 'emploi/employer_form.html', {'form': form, 'creating': creating})


def _require_employer(request):
    """L'entreprise doit exister ET avoir été acceptée par Lantante pour déposer offres et demandes."""
    employer = getattr(request.user, 'employer_profile', None)
    if not employer:
        messages.info(request, "Créez d'abord la fiche de votre entreprise.")
    elif not employer.is_approved:
        messages.info(request, "Votre entreprise doit d'abord être acceptée par Lantante pour déposer une demande.")
        return None
    return employer


@employer_space
def offer_create(request):
    employer = _require_employer(request)
    if not employer:
        return redirect('emploi:dashboard' if hasattr(request.user, 'employer_profile') else 'emploi:employer_edit')
    form = JobOfferForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        offer = form.save(commit=False)
        offer.employer = employer
        plan = ServicePlan.objects.filter(kind='job', is_active=True).first()
        if plan:
            offer.status = 'awaiting_payment'  # brouillon : mis en ligne après paiement et validation
            offer.save()
            form.save_skills(offer)
            order = billing.create_order(plan, request.user, employer, title=offer.title, job_offer=offer)
            return redirect('emploi:order_detail', pk=order.pk)
        offer.status = 'published' if employer.is_verified else 'pending'
        offer.save()
        form.save_skills(offer)
        if offer.status == 'pending':
            notify_staff(f"Offre à valider : {offer.title} ({employer.company_name})",
                         f"/lantanteAdminTech/Emploi/joboffer/{offer.pk}/change/")
            messages.success(request, "✓ Offre envoyée. Elle sera publiée après validation par Lantante.")
        else:
            messages.success(request, "✓ Offre publiée.")
        return redirect('emploi:dashboard')
    return render(request, 'emploi/offer_form.html', {'form': form, 'employer': employer})


@login_required
@require_POST
def offer_filled(request, slug):
    """L'entreprise a trouvé ses candidats : l'offre disparaît du site et de son espace."""
    offer = get_object_or_404(JobOffer, slug=slug)
    owner = offer.employer_id and offer.employer.user_id == request.user.pk
    if not (owner or is_staff(request.user)):
        return HttpResponseForbidden("Accès non autorisé.")
    if offer.status != 'filled':
        offer.status = 'filled'
        offer.save(update_fields=['status', 'updated_at'])
        pending = offer.applications.filter(status='received').count()
        notify_staff(f"Poste pourvu : « {offer.title} » ({offer.company_name}). "
                     f"{pending} candidature(s) encore en attente à traiter.",
                     f"/lantanteAdminTech/Emploi/application/?offer__id__exact={offer.pk}&traitement=pending")
        messages.success(request, "✓ Offre retirée : le poste est pourvu. Merci !")
    return redirect('emploi:dashboard')


@employer_space
def request_create(request):
    employer = _require_employer(request)
    if not employer:
        return redirect('emploi:dashboard' if hasattr(request.user, 'employer_profile') else 'emploi:employer_edit')
    form = StaffingRequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        req = form.save(commit=False)
        req.employer = employer
        req.save()
        form.save_skills(req)
        notify_staff(f"Demande de recrutement : {req.title} ({employer.company_name})",
                     f"/lantanteAdminTech/Emploi/staffingrequest/{req.pk}/change/")
        plan = ServicePlan.objects.filter(kind='recruit', is_active=True).first()
        if plan:
            order = billing.create_order(plan, request.user, employer, title=req.title, staffing_request=req)
            messages.success(request, "✓ Demande envoyée. Lantante vous contacte avec un devis pour l'accompagnement.")
            return redirect('emploi:order_detail', pk=order.pk)
        messages.success(request, "✓ Demande envoyée à Lantante. Nous vous proposerons des candidats rapidement.")
        return redirect('emploi:dashboard')
    return render(request, 'emploi/request_form.html', {'form': form, 'employer': employer})


# ─────────────────────────────
# 📰 FIL D'ACTUALITÉS
# ─────────────────────────────
def _company_must_order(user):
    """Une entreprise (non exonérée / sans badge bleu) publie via le service payant « Publier »."""
    if not user.is_authenticated:
        return False
    kind = account_kind(user)
    if kind == 'member':  # le particulier qui publie paie toujours
        return ServicePlan.objects.filter(kind='news', is_active=True).exists()
    employer = getattr(user, 'employer_profile', None)
    if kind != 'employer' or not employer or ((employer.publishing_free or employer.partner_id) and employer.is_verified):
        return False
    return ServicePlan.objects.filter(kind='news', is_active=True).exists()


def feed(request):
    form = FeedPostForm()
    must_order = _company_must_order(request.user)
    kind = account_kind(request.user)
    can_post = request.user.is_authenticated and (is_staff(request.user) or (kind == 'employer' and not must_order))
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"/users/connexion/?next={request.path}")
        if not (can_post or must_order):
            messages.info(request, "Les actualités sont publiées par les entreprises et par Lantante. "
                                   "Vous pouvez aimer et commenter.")
            return redirect('emploi:feed')
        if must_order:
            messages.info(request, "Les entreprises publient une actualité depuis « Publier » (tarifs et validation par Lantante).")
            return redirect('emploi:publish_hub')
        form = FeedPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, "✓ Publication ajoutée.")
            return redirect('emploi:feed')
    now = timezone.now()
    base = FeedPost.objects.filter(is_hidden=False).select_related('author', 'author__employer_profile')
    pinned = Case(When(is_featured=True, featured_until__gt=now, then=Value(1)),
                  When(is_featured=True, featured_until__isnull=True, then=Value(1)),
                  default=Value(0), output_field=IntegerField())
    posts = base.filter(is_sponsored=False).annotate(pinned=pinned).order_by('-pinned', '-created_at')
    return render(request, 'emploi/feed.html', {
        'page': _page(request, posts, 12), 'form': form, 'must_order': must_order, 'can_post': can_post,
        'news_plan': ServicePlan.objects.filter(kind='news', is_active=True).first(),
        'ads': base.filter(is_sponsored=True).exclude(image='').order_by('-created_at')[:3],
        'latest': base.filter(is_sponsored=False).order_by('-created_at')[:6],
    })


def post_detail(request, pk):
    """Une actualité en entier, avec j'aime, commentaires et partage."""
    post = get_object_or_404(FeedPost.objects.select_related('author').prefetch_related('comments__author', 'likes'), pk=pk, is_hidden=False)
    latest = FeedPost.objects.filter(is_hidden=False, is_sponsored=False).exclude(pk=pk).select_related('author')[:5]
    return render(request, 'emploi/feed_detail.html', {'post': post, 'comment_form': CommentForm(), 'latest': latest})


@login_required
@require_POST
def post_like(request, pk):
    post = get_object_or_404(FeedPost, pk=pk, is_hidden=False)
    if post.likes.filter(pk=request.user.pk).exists():
        post.likes.remove(request.user)
    else:
        post.likes.add(request.user)
    return redirect(request.META.get('HTTP_REFERER') or 'emploi:feed')


@login_required
@require_POST
def post_comment(request, pk):
    post = get_object_or_404(FeedPost, pk=pk, is_hidden=False)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
    return redirect(request.META.get('HTTP_REFERER') or 'emploi:feed')


@login_required
@require_POST
def post_delete(request, pk):
    post = get_object_or_404(FeedPost, pk=pk)
    if post.author_id == request.user.pk or is_staff(request.user):
        post.delete()
    return redirect('emploi:feed')


# ─────────────────────────────
# 💬 MESSAGERIE
# ─────────────────────────────
def _conversation_access(user):
    """Une personne voit ses conversations ; l'équipe voit en plus toutes les demandes du service client."""
    if is_staff(user):
        return Q(participants=user) | Q(kind='support')
    return Q(participants=user)


@login_required
def inbox(request):
    convs = Conversation.objects.filter(_conversation_access(request.user)).distinct() \
        .prefetch_related('participants', 'messages')
    items = []
    for conv in convs:
        last = conv.messages.last()
        unread = conv.messages.exclude(sender=request.user).exclude(read_by=request.user).count()
        items.append({'conv': conv, 'last': last, 'unread': unread, 'title': conv.title_for(request.user)})
    return render(request, 'emploi/inbox.html', {'items': items})


@login_required
def conversation(request, pk):
    conv = get_object_or_404(Conversation.objects.select_related('assigned_to').filter(
        _conversation_access(request.user)).distinct(), pk=pk)
    me_staff = is_staff(request.user)
    support = conv.kind == 'support'
    form = MessageForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        if support and me_staff:
            if conv.assigned_to_id and conv.assigned_to_id != request.user.pk:
                messages.error(request, f"Cette conversation est prise en charge par {staff_full_name(conv.assigned_to)}. "
                                        "Cliquez sur « Reprendre la conversation » pour la reprendre.")
                return redirect('emploi:conversation', pk=conv.pk)
            if not conv.assigned_to_id:
                assign_conversation(conv, request.user)
            # Première réponse humaine : le collaborateur est présenté automatiquement (sous sa propre identité).
            send_intro(conv, request.user)
        msg = Message.objects.create(conversation=conv, sender=request.user, body=form.cleaned_data['body'])
        msg.read_by.add(request.user)
        if support and not me_staff and conv.status == 'closed':
            conv.status = 'assigned' if conv.assigned_to_id else 'new'
        conv.save()  # met à jour « dernier message »
        url = f"/emploi/messages/{conv.pk}/"
        if support and me_staff:
            for person in conv.requesters():
                notify(person, f"Nouveau message de {staff_full_name(request.user)} (équipe Lantante)", url)
        elif support:
            targets = [conv.assigned_to] if conv.assigned_to_id else list(staff_users())
            for person in targets:
                notify(person, f"Nouveau message de {request.user.public_name} (service client)", url)
        else:
            for other in conv.other_participants(request.user):
                notify(other, f"Nouveau message de {request.user.public_name}", url)
        return redirect('emploi:conversation', pk=conv.pk)
    for msg in conv.messages.exclude(sender=request.user).exclude(read_by=request.user):
        msg.read_by.add(request.user)
    assignee = None
    if support and conv.assigned_to_id:
        from .services import staff_title
        assignee = {'name': staff_full_name(conv.assigned_to), 'title': staff_title(conv.assigned_to)}
    return render(request, 'emploi/conversation.html', {
        'conv': conv, 'form': form, 'title': conv.title_for(request.user),
        'support': support, 'me_staff': me_staff, 'assignee': assignee,
        'can_take': support and me_staff and conv.assigned_to_id != request.user.pk,
        'chat': conv.messages.select_related('sender', 'sender__staff_profile'),
    })


@login_required
@require_POST
def conversation_take(request, pk):
    """Un collaborateur reprend (ou prend en charge) une conversation du service client."""
    if not is_staff(request.user):
        return HttpResponseForbidden("Réservé à l'équipe Lantante.")
    conv = get_object_or_404(Conversation, pk=pk, kind='support')
    if conv.assigned_to_id != request.user.pk:
        assign_conversation(conv, request.user)
        messages.success(request, "Vous avez pris en charge cette conversation. Vous vous présenterez avec votre prochain message.")
    return redirect('emploi:conversation', pk=conv.pk)


def _start_conversation(request, others, title, kind='direct', notify_users=None):
    form = NewConversationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        conv = Conversation.objects.create(subject=form.cleaned_data['subject'], kind=kind)
        conv.participants.add(request.user, *others)
        msg = Message.objects.create(conversation=conv, sender=request.user, body=form.cleaned_data['body'])
        msg.read_by.add(request.user)
        if kind == 'support':
            send_auto_ack(conv)  # une seule fois, au début de la conversation
            label = f"Nouveau message de {request.user.public_name} (service client) — à prendre en charge"
        else:
            label = f"Nouveau message de {request.user.public_name}"
        for other in (notify_users if notify_users is not None else others):
            notify(other, label, f"/emploi/messages/{conv.pk}/")
        messages.success(request, "✓ Message envoyé.")
        return redirect('emploi:conversation', pk=conv.pk)
    return render(request, 'emploi/new_conversation.html', {'form': form, 'title': title})


@login_required
def new_conversation(request, user_id):
    other = get_object_or_404(User, pk=user_id, is_active=True)
    if other.pk == request.user.pk:
        return redirect('emploi:inbox')
    # Réutilise la conversation à deux déjà existante, si elle existe.
    existing = Conversation.objects.filter(participants=request.user).filter(participants=other) \
        .annotate(n=Count('participants')).filter(n=2).first()
    if existing:
        return redirect('emploi:conversation', pk=existing.pk)
    return _start_conversation(request, [other], f"Écrire à {other.public_name}")


@login_required
def contact_lantante(request):
    if is_staff(request.user):
        return redirect('emploi:inbox')
    # Une demande déjà ouverte est reprise : pas de nouvel accusé de réception.
    existing = Conversation.objects.filter(participants=request.user, kind='support').exclude(status='closed').first()
    if existing:
        return redirect('emploi:conversation', pk=existing.pk)
    staff = list(staff_users())
    if not staff:
        messages.error(request, "La messagerie Lantante n'est pas disponible pour le moment.")
        return redirect('emploi:home')
    # Seul le demandeur est participant : toute l'équipe a accès aux demandes du service client.
    return _start_conversation(request, [], "Écrire à l'équipe Lantante", kind='support', notify_users=staff)


# ─────────────────────────────
# 📅 RENDEZ-VOUS
# ─────────────────────────────
@login_required
def appointments(request):
    candidate = getattr(request.user, 'candidate_profile', None)
    employer = getattr(request.user, 'employer_profile', None)
    qs = Appointment.objects.none()
    if candidate:
        qs = qs | Appointment.objects.filter(candidate=candidate)
    if employer:
        qs = qs | Appointment.objects.filter(employer=employer)
    return render(request, 'emploi/appointments.html', {
        'appointments': qs.select_related('candidate__user', 'employer').distinct(),
        'now': timezone.now(),
    })


@login_required
@require_POST
def appointment_respond(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, candidate__user=request.user)
    action = request.POST.get('action')
    if appt.status in ('proposed', 'confirmed') and action in ('confirm', 'decline'):
        appt.status = 'confirmed' if action == 'confirm' else 'declined'
        appt.save()
        verb = "confirmé" if action == 'confirm' else "décliné"
        notify_staff(f"{appt.candidate.name} a {verb} le rendez-vous « {appt.title} » du {appt.scheduled_at:%d/%m %H:%M}",
                     f"/lantanteAdminTech/Emploi/appointment/{appt.pk}/change/")
        messages.success(request, f"Rendez-vous {verb}.")
    return redirect('emploi:appointments')


# ─────────────────────────────
# 🔔 NOTIFICATIONS
# ─────────────────────────────
@login_required
def notifications(request):
    items = list(request.user.emploi_notifications.all()[:50])
    request.user.emploi_notifications.filter(is_read=False).update(is_read=True)
    return render(request, 'emploi/notifications.html', {'items': items})


# ─────────────────────────────
# 💳 TARIFS, PUBLICATION ET PAIEMENT
# ─────────────────────────────
def pricing(request):
    """Les deux formules : publication ponctuelle (payante) et partenariat officiel (sur validation)."""
    from core.models import SiteSettings
    return render(request, 'emploi/pricing.html', {
        'plans': ServicePlan.objects.filter(is_active=True, kind__in=ServicePlan.MEMBER_KINDS if account_kind(request.user) == 'member' else ServicePlan.EMPLOYER_KINDS),
        'site': SiteSettings.load(), 'kind': account_kind(request.user),
    })


def _approved_employer(request):
    employer = getattr(request.user, 'employer_profile', None)
    if not employer:
        messages.info(request, "Inscrivez d'abord votre entreprise pour publier.")
        return None
    if not employer.is_approved:
        messages.info(request, "Votre entreprise doit d'abord être acceptée par Lantante pour publier.")
        return None
    return employer


def _publisher(request):
    """(compte, entreprise ou None, services autorisés) — un particulier publie sans fiche entreprise."""
    if account_kind(request.user) == 'member':
        return True, None, ServicePlan.MEMBER_KINDS
    employer = _approved_employer(request)
    return bool(employer), employer, ServicePlan.EMPLOYER_KINDS


@publisher_space
def publish_hub(request):
    ok, employer, kinds = _publisher(request)
    if not ok:
        return redirect('emploi:dashboard' if hasattr(request.user, 'employer_profile') else 'emploi:employer_edit')
    return render(request, 'emploi/publish_hub.html', {
        'plans': ServicePlan.objects.filter(is_active=True, kind__in=kinds), 'employer': employer,
        'exempt': billing.employer_is_exempt(employer), 'is_member': employer is None,
    })


@publisher_space
def order_new(request, code):
    ok, employer, kinds = _publisher(request)
    if not ok:
        return redirect('emploi:dashboard')
    plan = get_object_or_404(ServicePlan, code=code, is_active=True, kind__in=kinds)
    if plan.kind == 'job':
        return redirect('emploi:offer_create')
    if plan.kind == 'recruit':
        return redirect('emploi:request_create')
    if plan.kind == 'job_boost':  # mise en avant d'une offre déjà publiée
        form = OfferBoostForm(request.POST or None, employer=employer)
        if request.method == 'POST' and form.is_valid():
            offer = form.cleaned_data['offer']
            order = billing.create_order(plan, request.user, employer, title=offer.title, boosted_offer=offer)
            return redirect('emploi:order_detail', pk=order.pk)
        return render(request, 'emploi/order_form.html', {'form': form, 'plan': plan, 'employer': employer,
                                                          'exempt': billing.employer_is_exempt(employer)})
    form = OrderContentForm(request.POST or None, request.FILES or None, plan=plan)
    if request.method == 'POST' and form.is_valid():
        data = {k: v for k, v in form.cleaned_data.items() if v not in (None, '')}
        order = billing.create_order(plan, request.user, employer, **data)
        return redirect('emploi:order_detail', pk=order.pk)
    return render(request, 'emploi/order_form.html', {'form': form, 'plan': plan, 'employer': employer,
                                                      'exempt': billing.employer_is_exempt(employer)})


def _my_order(request, pk):
    return get_object_or_404(PublicationOrder.objects.select_related('plan', 'employer'), pk=pk, user=request.user)


@publisher_space
def order_detail(request, pk):
    from core.models import SiteSettings
    order = _my_order(request, pk)
    return render(request, 'emploi/order_detail.html', {
        'order': order, 'site': SiteSettings.load(),
        'form': PaymentForm(initial={'payment_method': 'flooz'}), 'steps': ["Soumise", "Paiement", "Validation", "Publiée"],
    })


@publisher_space
@require_POST
def order_pay(request, pk):
    order = _my_order(request, pk)
    if not order.can_pay:
        messages.info(request, "Cette commande n'attend pas de paiement.")
        return redirect('emploi:order_detail', pk=order.pk)
    form = PaymentForm(request.POST)
    if form.is_valid():
        billing.declare_payment(order, form.cleaned_data['payment_method'], form.cleaned_data['payer_phone'],
                                form.cleaned_data['payment_reference'])
        messages.success(request, "✓ Merci ! Nous vérifions votre paiement : patientez quelques instants.")
        return redirect('emploi:order_detail', pk=order.pk)
    from core.models import SiteSettings
    return render(request, 'emploi/order_detail.html', {
        'order': order, 'site': SiteSettings.load(), 'form': form, 'steps': ["Soumise", "Paiement", "Validation", "Publiée"]})


@publisher_space
def order_edit(request, pk):
    """Modifier le contenu (correction demandée, ou avant paiement) puis renvoyer."""
    from .forms import JobOfferForm, StaffingRequestForm
    order = _my_order(request, pk)
    if not order.can_edit:
        messages.info(request, "Cette publication ne peut plus être modifiée.")
        return redirect('emploi:order_detail', pk=order.pk)
    kind = order.plan.kind
    if kind == 'job' and order.job_offer:
        form = JobOfferForm(request.POST or None, request.FILES or None, instance=order.job_offer)
    elif kind == 'recruit' and order.staffing_request:
        form = StaffingRequestForm(request.POST or None, instance=order.staffing_request)
    else:
        form = OrderContentForm(request.POST or None, request.FILES or None, instance=order)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        if hasattr(form, 'save_skills'):
            form.save_skills(saved)
        if kind == 'job' and order.job_offer:
            order.title = order.job_offer.title
            order.save(update_fields=['title'])
        billing.resubmit(order)
        messages.success(request, "✓ Modifications enregistrées.")
        return redirect('emploi:order_detail', pk=order.pk)
    return render(request, 'emploi/order_form.html', {'form': form, 'plan': order.plan, 'employer': order.employer,
                                                      'editing': True, 'order': order})


@publisher_space
def order_receipt(request, pk):
    order = _my_order(request, pk)
    if not order.paid_at:
        messages.info(request, "Le reçu est disponible après confirmation du paiement.")
        return redirect('emploi:order_detail', pk=order.pk)
    return render(request, 'emploi/order_receipt.html', {'order': order})


@publisher_space
@require_POST
def order_cancel(request, pk):
    order = _my_order(request, pk)
    billing.cancel_order(order)
    messages.success(request, "Commande annulée.")
    return redirect('emploi:dashboard')


# ─────────────────────────────
# 📨 DEMANDES SPONTANÉES
# ─────────────────────────────
def _candidate_or_redirect(request):
    profile = getattr(request.user, 'candidate_profile', None)
    if not profile:
        messages.info(request, "Créez d'abord votre profil candidat pour déposer une demande.")
    return profile


@candidate_space
def spontaneous_list(request):
    profile = _candidate_or_redirect(request)
    if not profile:
        return redirect('emploi:candidate_edit')
    return render(request, 'emploi/spontaneous_list.html', {
        'requests': profile.spontaneous_requests.all(), 'profile': profile,
    })


@candidate_space
def spontaneous_new(request):
    profile = _candidate_or_redirect(request)
    if not profile:
        return redirect('emploi:candidate_edit')
    form = SpontaneousRequestForm(request.POST or None, candidate=profile)
    if request.method == 'POST' and form.is_valid():
        req = form.save()
        notify_staff(f"Nouvelle demande spontanée : {profile.name} ({req.get_request_type_display()}, {req.get_domain_display()})",
                     f"/lantanteAdminTech/Emploi/spontaneousrequest/{req.pk}/change/")
        messages.success(request, "✓ Demande enregistrée. Lantante la garde dans son vivier et vous contacte dès qu'une opportunité correspond.")
        return redirect('emploi:spontaneous_list')
    return render(request, 'emploi/spontaneous_form.html', {'form': form, 'profile': profile})


@candidate_space
def spontaneous_edit(request, pk):
    req = get_object_or_404(SpontaneousRequest, pk=pk, candidate__user=request.user)
    if not req.can_edit:
        messages.info(request, "Cette demande ne peut plus être modifiée.")
        return redirect('emploi:spontaneous_list')
    form = SpontaneousRequestForm(request.POST or None, instance=req, candidate=req.candidate)
    if request.method == 'POST' and form.is_valid():
        form.save()
        notify_staff(f"Demande spontanée mise à jour : {req.candidate.name}",
                     f"/lantanteAdminTech/Emploi/spontaneousrequest/{req.pk}/change/")
        messages.success(request, "✓ Demande mise à jour.")
        return redirect('emploi:spontaneous_list')
    return render(request, 'emploi/spontaneous_form.html', {'form': form, 'profile': req.candidate, 'editing': True})


@candidate_space
@require_POST
def spontaneous_withdraw(request, pk):
    req = get_object_or_404(SpontaneousRequest, pk=pk, candidate__user=request.user)
    if req.is_open:
        req.status = 'closed'
        req.withdrawn = True
        req.save(update_fields=['status', 'withdrawn', 'updated_at'])
        notify_staff(f"{req.candidate.name} a retiré sa demande spontanée.",
                     f"/lantanteAdminTech/Emploi/spontaneousrequest/{req.pk}/change/")
        messages.success(request, "Demande retirée.")
    return redirect('emploi:spontaneous_list')


@candidate_space
@require_POST
def consent_respond(request, pk):
    """Le candidat accepte ou refuse qu'une opportunité proposée par Lantante soit transmise à l'entreprise."""
    application = get_object_or_404(Application, pk=pk, candidate__user=request.user, consent='pending')
    accept = request.POST.get('answer') == 'accept'
    spont.respond_consent(application, accept)
    if accept:
        share_application(application)  # transmission immédiate à l'entreprise
    messages.success(request, "✓ Merci, Lantante transmet votre dossier." if accept else "C'est noté : votre dossier ne sera pas transmis.")
    return redirect('emploi:dashboard')


# ─────────────────────────────
# 📥 CANDIDATURES REÇUES (espace entreprise)
# ─────────────────────────────
def _employer_applications(employer):
    return Application.objects.filter(
        Q(offer__employer=employer) | Q(request__employer=employer), shared_with_employer=True
    ).select_related('candidate__user', 'offer', 'request').prefetch_related('slots', 'appointments')


def _my_application(request, pk):
    employer = getattr(request.user, 'employer_profile', None)
    application = get_object_or_404(Application.objects.select_related('candidate__user', 'offer', 'request'), pk=pk,
                                    shared_with_employer=True)
    if not employer or application.employer != employer:
        raise Http404
    return application


@employer_space
def applications_received(request):
    employer = _approved_employer(request)
    if not employer:
        return redirect('emploi:dashboard')
    JobOffer.close_expired()
    base = _employer_applications(employer)
    offer_id = request.GET.get('offer')
    if offer_id and offer_id.isdigit():
        base = base.filter(offer_id=int(offer_id))
    tab = request.GET.get('tab') or 'new'
    groups = {
        'new': base.filter(status='received'),
        'progress': base.filter(status__in=('shortlisted', 'interview')),
        'hired': base.filter(status='hired'),
        'refused': base.filter(status='refused'),
        'all': base,
    }
    items = groups.get(tab, groups['new'])
    return render(request, 'emploi/applications_received.html', {
        'tab': tab, 'items': items,
        'counts': {k: v.count() for k, v in groups.items()},
        'offers': employer.offers.exclude(status='rejected'), 'offer_id': offer_id or '',
    })


@employer_space
@require_POST
def application_decide(request, pk):
    """L'entreprise présélectionne, accepte ou refuse : le candidat est prévenu (site + e-mail)."""
    application = _my_application(request, pk)
    action = request.POST.get('action')
    mapping = {'shortlist': 'shortlisted', 'accept': 'hired', 'refuse': 'refused'}
    if action not in mapping:
        return redirect('emploi:applications_received')
    actions.decide_application(application, action, request.POST.get('message', ''))
    messages.success(request, {
        'shortlist': f"✓ {application.candidate.name} est présélectionné(e) : il/elle va indiquer ses disponibilités.",
        'accept': f"✓ {application.candidate.name} est accepté(e). Prenez contact pour la suite.",
        'refuse': f"{application.candidate.name} est informé(e) que sa candidature n'est pas retenue.",
    }[action])
    return redirect(request.META.get('HTTP_REFERER') or 'emploi:applications_received')


@employer_space
@require_POST
def application_schedule(request, pk):
    """L'entreprise fixe l'entretien : rendez-vous créé, candidat prévenu (il confirme ou décline)."""
    from django.utils.dateparse import parse_datetime
    application = _my_application(request, pk)
    when = parse_datetime(request.POST.get('when', ''))
    if not when:
        messages.error(request, "Choisissez la date et l'heure de l'entretien.")
        return redirect('emploi:applications_received')
    if timezone.is_naive(when):
        when = timezone.make_aware(when)
    if when < timezone.now():
        messages.error(request, "Choisissez une date à venir.")
        return redirect('emploi:applications_received')
    actions.schedule_interview(application, when, request.POST.get('place', ''), request.POST.get('notes', ''))
    local = timezone.localtime(when).strftime('%d/%m/%Y à %H:%M')
    messages.success(request, f"✓ Entretien fixé le {local} ; {application.candidate.name} est prévenu(e).")
    return redirect(request.META.get('HTTP_REFERER') or 'emploi:applications_received')

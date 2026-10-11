from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Partner

from .forms import (
    ApplicationForm, AvailabilityForm, CandidateDocumentForm, CandidateForm, CommentForm, EmployerForm, FeedPostForm,
    JobOfferForm, MessageForm, NewConversationForm, StaffingRequestForm,
)
from .models import (
    Appointment, Application, AvailabilitySlot, CandidateDocument, CandidateProfile, Conversation, DOMAIN_CHOICES,
    CONTRACT_CHOICES, EmployerProfile, FeedComment, FeedPost, JobOffer, Message,
    Notification, ProfileRevision, StaffingRequest,
)
from .services import can_browse_candidates, can_see_private, is_staff, notify, notify_staff

User = get_user_model()


def _qs(request):
    """Filtres de l'URL sans « page », pour les garder en changeant de page."""
    params = request.GET.copy()
    params.pop('page', None)
    encoded = params.urlencode()
    return encoded + '&' if encoded else ''


def _page(request, queryset, per_page=12):
    return Paginator(queryset, per_page).get_page(request.GET.get('page'))


def _open_offers():
    today = timezone.localdate()
    return JobOffer.objects.filter(status='published').filter(
        Q(deadline__isnull=True) | Q(deadline__gte=today)
    ).filter(Q(employer__isnull=True) | Q(employer__status='approved')).select_related('employer', 'employer__partner')


# ─────────────────────────────
# 🏠 ACCUEIL
# ─────────────────────────────
def home(request):
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
    applied = False
    profile = getattr(request.user, 'candidate_profile', None) if request.user.is_authenticated else None
    if profile:
        applied = Application.objects.filter(candidate=profile, offer=offer).exists()
    return render(request, 'emploi/offer_detail.html', {
        'offer': offer, 'applied': applied, 'profile': profile,
        'form': form or ApplicationForm(offer=offer, profile=profile), 'owner': owner,
    })


@login_required
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
    form = ApplicationForm(request.POST, offer=offer, profile=profile)
    if not form.is_valid():
        return offer_detail(request, slug, form=form)
    text = form.cleaned_data['text']
    application, created = Application.objects.get_or_create(
        candidate=profile, offer=offer,
        defaults={
            'origin': 'candidate',
            'cover_letter': text if offer.requires_cover_letter else '',
            'message': '' if offer.requires_cover_letter else text,
            'internship_duration': form.cleaned_data.get('internship_duration', ''),
            'available_from': form.cleaned_data.get('available_from'),
        },
    )
    if created:
        notify_staff(f"Nouvelle candidature : {profile.name} → {offer.title}", f"/lantanteAdminTech/Emploi/application/{application.pk}/change/")
        if offer.employer_id:
            notify(offer.employer.user, f"Nouvelle candidature pour « {offer.title} ». Lantante vous transmettra les profils retenus.", "")
        messages.success(request, "✓ Candidature envoyée à Lantante, qui étudie votre dossier et le transmet à l'entreprise. Vous serez prévenu.")
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
    messages.info(request, "L'annuaire des candidats est réservé à Lantante et aux entreprises acceptées.")
    return redirect('emploi:home')


def candidate_list(request):
    if not can_browse_candidates(request.user):
        return _directory_denied(request)
    qs = CandidateProfile.objects.filter(is_published=True).select_related('user').prefetch_related('skills')
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
    if not is_owner and not can_browse_candidates(request.user):
        return _directory_denied(request)
    if not candidate.is_published and not can_see_private(request.user, candidate):
        raise Http404
    return render(request, 'emploi/candidate_detail.html', {
        'candidate': candidate,
        'private_ok': can_see_private(request.user, candidate),
        'is_me': request.user.is_authenticated and candidate.user_id == request.user.pk,
    })


@login_required
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
        application.slots.all().delete()
        note = form.cleaned_data.get('note', '')
        slots = [AvailabilitySlot.objects.create(application=application, start=when, note=note)
                 for when in form.slots()]
        target = application.offer or application.request
        when_txt = ", ".join(timezone.localtime(s.start).strftime('%d/%m %H:%M') for s in slots)
        notify_staff(f"{application.candidate.name} est disponible pour l'entretien « {target} » : {when_txt}",
                     f"/lantanteAdminTech/Emploi/application/{application.pk}/change/")
        messages.success(request, "✓ Merci ! Lantante vous confirme la date de l'entretien très vite.")
        return redirect('emploi:dashboard')
    return render(request, 'emploi/availability.html', {'form': form, 'application': application,
                                                       'target': application.offer or application.request})


@login_required
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


@login_required
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
def dashboard(request):
    user = request.user
    candidate = getattr(user, 'candidate_profile', None)
    employer = getattr(user, 'employer_profile', None)
    context = {'candidate': candidate, 'employer': employer}
    if candidate:
        context['applications'] = candidate.applications.select_related('offer', 'request')[:10]
        context['appointments'] = candidate.appointments.filter(
            scheduled_at__gte=timezone.now()).exclude(status__in=['declined', 'cancelled'])[:5]
    if employer:
        context['offers'] = employer.offers.all()[:10]
        context['staffing'] = employer.requests.all()[:10]
        context['offer_apps'] = Application.objects.filter(
            Q(offer__employer=employer) | Q(request__employer=employer), shared_with_employer=True
        ).select_related('candidate__user', 'offer', 'request')[:15]
    return render(request, 'emploi/dashboard.html', context)


@login_required
def candidate_edit(request):
    profile = getattr(request.user, 'candidate_profile', None)
    creating = profile is None
    before = None if creating else profile.snapshot()
    form = CandidateForm(request.POST or None, request.FILES or None, instance=profile, user=request.user)
    if request.method == 'POST' and form.is_valid():
        profile = form.save()
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


@login_required
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


@login_required
def offer_create(request):
    employer = _require_employer(request)
    if not employer:
        return redirect('emploi:dashboard' if hasattr(request.user, 'employer_profile') else 'emploi:employer_edit')
    form = JobOfferForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        offer = form.save(commit=False)
        offer.employer = employer
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
        messages.success(request, "✓ Demande envoyée à Lantante. Nous vous proposerons des candidats rapidement.")
        return redirect('emploi:dashboard')
    return render(request, 'emploi/request_form.html', {'form': form, 'employer': employer})


# ─────────────────────────────
# 📰 FIL D'ACTUALITÉS
# ─────────────────────────────
def feed(request):
    form = FeedPostForm()
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"/users/connexion/?next={request.path}")
        form = FeedPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, "✓ Publication ajoutée.")
            return redirect('emploi:feed')
    posts = FeedPost.objects.filter(is_hidden=False).select_related('author').prefetch_related(
        'comments__author', 'likes')
    return render(request, 'emploi/feed.html', {
        'page': _page(request, posts, 10), 'form': form, 'comment_form': CommentForm(),
    })


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
@login_required
def inbox(request):
    convs = request.user.conversations.prefetch_related('participants', 'messages')
    items = []
    for conv in convs:
        last = conv.messages.last()
        unread = conv.messages.exclude(sender=request.user).exclude(read_by=request.user).count()
        items.append({'conv': conv, 'last': last, 'unread': unread,
                      'others': [u.public_name for u in conv.participants.all() if u.pk != request.user.pk]})
    return render(request, 'emploi/inbox.html', {'items': items})


@login_required
def conversation(request, pk):
    conv = get_object_or_404(Conversation, pk=pk, participants=request.user)
    form = MessageForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        msg = Message.objects.create(conversation=conv, sender=request.user, body=form.cleaned_data['body'])
        msg.read_by.add(request.user)
        conv.save()  # met à jour « dernier message »
        for other in conv.other_participants(request.user):
            notify(other, f"Nouveau message de {request.user.public_name}", f"/emploi/messages/{conv.pk}/")
        return redirect('emploi:conversation', pk=conv.pk)
    for msg in conv.messages.exclude(sender=request.user).exclude(read_by=request.user):
        msg.read_by.add(request.user)
    return render(request, 'emploi/conversation.html', {
        'conv': conv, 'form': form,
        'others': [u.public_name for u in conv.participants.all() if u.pk != request.user.pk],
        'chat': conv.messages.select_related('sender'),
    })


def _start_conversation(request, others, title):
    form = NewConversationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        conv = Conversation.objects.create(subject=form.cleaned_data['subject'])
        conv.participants.add(request.user, *others)
        msg = Message.objects.create(conversation=conv, sender=request.user, body=form.cleaned_data['body'])
        msg.read_by.add(request.user)
        for other in others:
            notify(other, f"Nouveau message de {request.user.public_name}", f"/emploi/messages/{conv.pk}/")
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
    staff = list(User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True))
                 .exclude(pk=request.user.pk))
    if not staff:
        messages.error(request, "La messagerie Lantante n'est pas disponible pour le moment.")
        return redirect('emploi:home')
    return _start_conversation(request, staff, "Écrire à l'équipe Lantante")


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

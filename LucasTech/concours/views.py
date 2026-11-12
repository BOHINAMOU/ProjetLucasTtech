import mimetypes

from django.db.models import Count, Prefetch, Q
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from abonnements.access import can_view_paper, user_can_access

from .models import Contest, ContestCategory, ContestSession, Correction, ExamPaper


def _contests_for(user):
    qs = Contest.objects.select_related('category')
    return qs if user.is_staff else qs.published()


def index(request):
    q = (request.GET.get('q') or '').strip()
    cat_slug = request.GET.get('categorie') or ''
    contests = _contests_for(request.user).annotate(
        n_sessions=Count('sessions', filter=Q(sessions__is_published=True), distinct=True))
    active_category = None
    if cat_slug:
        active_category = ContestCategory.objects.filter(slug=cat_slug).first()
        if active_category:
            contests = contests.filter(category=active_category)
    if q:
        contests = contests.filter(Q(acronym__icontains=q) | Q(name__icontains=q) | Q(description__icontains=q))
    categories = ContestCategory.objects.filter(contests__in=_contests_for(request.user)).distinct()
    return render(request, 'concours/index.html', {
        'contests': contests, 'categories': categories, 'active_category': active_category, 'search_query': q,
    })


def detail(request, slug):
    contest = get_object_or_404(_contests_for(request.user), slug=slug)
    sessions = contest.sessions.filter(is_published=True).annotate(
        n_papers=Count('papers', filter=Q(papers__is_published=True)),
        n_free=Count('papers', filter=Q(papers__is_published=True, papers__is_free=True)))
    return render(request, 'concours/detail.html', {
        'contest': contest, 'sessions': sessions, 'has_access': user_can_access(request.user, contest),
    })


def session(request, slug, year):
    contest = get_object_or_404(_contests_for(request.user), slug=slug)
    sess = get_object_or_404(ContestSession, contest=contest, year=year, is_published=True)
    papers = sess.papers.filter(is_published=True).select_related('specialty').prefetch_related(
        Prefetch('corrections', queryset=Correction.objects.filter(is_published=True)))
    has_access = user_can_access(request.user, contest)
    rows = [(p, has_access or p.is_free) for p in papers]
    return render(request, 'concours/session.html', {
        'contest': contest, 'session': sess, 'rows': rows, 'has_access': has_access,
        'other_years': contest.sessions.filter(is_published=True).exclude(pk=sess.pk),
    })


def _document(request, kind, pk):
    """Renvoie (document, épreuve) publié, sinon 404. Les droits sont vérifiés à part."""
    if kind == 'sujet':
        doc = get_object_or_404(ExamPaper.objects.select_related('session__contest'), pk=pk)
        paper = doc
        published = doc.is_published
    elif kind == 'corrige':
        doc = get_object_or_404(Correction.objects.select_related('paper__session__contest'), pk=pk)
        paper = doc.paper
        published = doc.is_published and paper.is_published
    else:
        raise Http404
    contest = paper.session.contest
    if not request.user.is_staff and not (published and paper.session.is_published and contest.is_published):
        raise Http404
    return doc, paper


@never_cache
def reader(request, kind, pk):
    doc, paper = _document(request, kind, pk)
    allowed = can_view_paper(request.user, paper)
    ext = doc.file.name.rsplit('.', 1)[-1].lower() if doc.file else ''
    ctx = {'doc': doc, 'paper': paper, 'kind': kind, 'contest': paper.session.contest, 'allowed': allowed,
           'is_pdf': ext == 'pdf', 'watermark': request.user.email if request.user.is_authenticated else ''}
    return render(request, 'concours/reader.html', ctx, status=200 if allowed else 403)


@never_cache
def file(request, kind, pk):
    """Seule porte d'accès aux fichiers d'épreuves (stockage privé). Droits vérifiés à CHAQUE requête."""
    doc, paper = _document(request, kind, pk)
    if not can_view_paper(request.user, paper):
        return HttpResponseForbidden("Accès réservé aux abonnés.")
    if not doc.file:
        raise Http404
    try:
        fh = doc.file.open('rb')
    except (FileNotFoundError, OSError):
        raise Http404
    ctype = mimetypes.guess_type(doc.file.name)[0] or 'application/octet-stream'
    resp = FileResponse(fh, content_type=ctype)
    resp['Content-Disposition'] = 'inline'
    resp['Cache-Control'] = 'private, no-store, max-age=0'
    resp['X-Robots-Tag'] = 'noindex, nofollow'
    return resp

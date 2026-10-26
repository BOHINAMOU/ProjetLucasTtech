"""Tableau de bord de l'administration : chiffres clés, éléments à traiter, derniers commentaires et boutons rapides."""
from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.urls import NoReverseMatch, reverse
from django.utils import timezone


def _model(label):
    try:
        return apps.get_model(label)
    except LookupError:
        return None


def _url(label, query='', add=False):
    m = _model(label)
    if m is None:
        return ''
    try:
        return reverse(f"admin:{m._meta.app_label}_{m._meta.model_name}_{'add' if add else 'changelist'}") + (query if not add else '')
    except NoReverseMatch:
        return ''


def _count(label, **filters):
    m = _model(label)
    try:
        return m.objects.filter(**filters).count() if m else 0
    except Exception:
        return 0


def _change_url(obj):
    try:
        return reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk])
    except NoReverseMatch:
        return ''


def build(request):
    now = timezone.now()
    week = now - timedelta(days=7)
    User = get_user_model()

    # ── À traiter : tout ce qui attend une action de l'équipe ──
    todo = [
        ('Commentaires du site non lus', _count('Publications.PublicationComment', is_read=False), 'fa-comment-dots', _url('Publications.PublicationComment', '?is_read__exact=0'), 'red'),
        ('Commentaires du fil emploi non lus', _count('Emploi.FeedComment', is_read=False), 'fa-comments', _url('Emploi.FeedComment', '?is_read__exact=0'), 'red'),
        ('Messages rapides non lus', _count('Publications.QuickMessage', is_read=False), 'fa-envelope', _url('Publications.QuickMessage', '?is_read__exact=0'), 'red'),
        ('Contacts des services non lus', _count('Services.ServiceContact', is_read=False), 'fa-phone-volume', _url('Services.ServiceContact', '?is_read__exact=0'), 'red'),
        ('Service client : nouveaux messages', _count('Emploi.Conversation', kind='support', status='new'), 'fa-headset', _url('Emploi.Conversation', '?status__exact=new'), 'orange'),
        ('Entreprises à analyser', _count('Emploi.EmployerProfile', status='pending'), 'fa-building', _url('Emploi.EmployerProfile', '?status__exact=pending'), 'orange'),
        ('Paiements à vérifier', _count('Emploi.PublicationOrder', status='payment_declared'), 'fa-money-bill-wave', _url('Emploi.PublicationOrder', '?status__exact=payment_declared'), 'orange'),
        ('Actualités payées à valider', _count('Emploi.PublicationOrder', status='in_review'), 'fa-clipboard-check', _url('Emploi.PublicationOrder', '?status__exact=in_review'), 'orange'),
        ('Offres d\'emploi à valider', _count('Emploi.JobOffer', status='pending'), 'fa-bullhorn', _url('Emploi.JobOffer', '?status__exact=pending'), 'orange'),
        ('Candidatures en attente', _count('Emploi.Application', status='received'), 'fa-handshake', _url('Emploi.Application'), 'blue'),
        ('Commandes boutique en attente', _count('Shop.ShopOrder', status='pending'), 'fa-shopping-bag', _url('Shop.ShopOrder', '?status__exact=pending'), 'blue'),
        ('Réservations en attente', _count('Shop.Reservation', status='pending'), 'fa-calendar-check', _url('Shop.Reservation', '?status__exact=pending'), 'blue'),
        ('Demandes de monétisation à traiter', _count('core.MonetizationRequest', status='new'), 'fa-sack-dollar', _url('core.MonetizationRequest', '?status__exact=new'), 'orange'),
        ('Demandes de partenariat', _count('core.PartnerApplication', status='pending'), 'fa-ribbon', _url('core.PartnerApplication', '?status__exact=pending'), 'blue'),
    ]
    todo = [dict(label=a, n=b, icon=c, url=d, tone=e) for a, b, c, d, e in todo]
    total_todo = sum(t['n'] for t in todo)

    # ── Commentaires : lus / non lus / publiés ──
    pc, fc = _model('Publications.PublicationComment'), _model('Emploi.FeedComment')
    pc_all = pc.objects.count() if pc else 0
    fc_all = fc.objects.count() if fc else 0
    pc_unread = pc.objects.filter(is_read=False).count() if pc else 0
    fc_unread = fc.objects.filter(is_read=False).count() if fc else 0
    comments = {
        'total': pc_all + fc_all, 'unread': pc_unread + fc_unread, 'read': pc_all + fc_all - pc_unread - fc_unread,
        'site_url': _url('Publications.PublicationComment'), 'feed_url': _url('Emploi.FeedComment'),
        'unread_url': _url('Publications.PublicationComment', '?is_read__exact=0'),
    }
    latest = []
    if pc:
        for c in pc.objects.select_related('publication').order_by('-created_at')[:6]:
            latest.append({'who': c.name, 'text': c.text, 'on': c.publication.title, 'when': c.created_at, 'read': c.is_read, 'url': _change_url(c), 'src': "Actualités du site"})
    if fc:
        for c in fc.objects.select_related('author', 'post').order_by('-created_at')[:6]:
            latest.append({'who': c.author.public_name, 'text': c.text, 'on': c.post.headline, 'when': c.created_at, 'read': c.is_read, 'url': _change_url(c), 'src': "Fil emploi"})
    latest.sort(key=lambda x: x['when'], reverse=True)

    qm = _model('Publications.QuickMessage')
    messages_latest = [{'who': m.name, 'contact': m.contact, 'text': m.message, 'when': m.created_at, 'read': m.is_read, 'url': _change_url(m)}
                       for m in (qm.objects.order_by('-created_at')[:5] if qm else [])]

    # ── Chiffres clés ──
    pub = _model('Publications.Publication')
    views = (pub.objects.aggregate(v=Sum('views_count'))['v'] or 0) if pub else 0
    stats = [
        ('Comptes utilisateurs', User.objects.count(), f"+{User.objects.filter(date_joined__gte=week).count()} cette semaine", 'fa-users', _url('Users.User')),
        ('Candidats', _count('Emploi.CandidateProfile'), '', 'fa-user-graduate', _url('Emploi.CandidateProfile')),
        ('Entreprises acceptées', _count('Emploi.EmployerProfile', status='approved'), '', 'fa-building', _url('Emploi.EmployerProfile')),
        ('Offres publiées', _count('Emploi.JobOffer', status='published'), '', 'fa-bullhorn', _url('Emploi.JobOffer')),
        ('Candidatures reçues', _count('Emploi.Application'), f"+{_count('Emploi.Application', created_at__gte=week)} cette semaine", 'fa-handshake', _url('Emploi.Application')),
        ('Actualités du site', _count('Publications.Publication', is_published=True), f"{views} lectures", 'fa-newspaper', _url('Publications.Publication')),
        ('Actualités du fil emploi', _count('Emploi.FeedPost', is_hidden=False), '', 'fa-rss', _url('Emploi.FeedPost')),
        ('Produits en boutique', _count('Shop.Product'), '', 'fa-store', _url('Shop.Product')),
        ('Formations', _count('Formations.Formation'), f"{_count('Formations.Registration')} inscriptions", 'fa-graduation-cap', _url('Formations.Formation')),
        ('Services', _count('Services.Service', is_active=True), '', 'fa-wrench', _url('Services.Service')),
        ('Partenaires', _count('core.Partner', is_active=True), '', 'fa-ribbon', _url('core.Partner')),
        ('Inscriptions aux événements', _count('Publications.EventRegistration'), '', 'fa-calendar-alt', _url('Publications.EventRegistration')),
    ]
    stats = [dict(label=a, n=b, sub=c, icon=d, url=e) for a, b, c, d, e in stats]

    # ── Nouveaux comptes sur 14 jours (petit graphique) ──
    days = []
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).date()
        days.append({'label': day.strftime('%d/%m'), 'n': User.objects.filter(date_joined__date=day).count()})
    peak = max([d['n'] for d in days] + [1])
    for d in days:
        d['h'] = max(4, round(100 * d['n'] / peak)) if d['n'] else 4

    app_days = []
    app_model = _model('Emploi.Application')
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).date()
        app_days.append({'label': day.strftime('%d/%m'), 'n': app_model.objects.filter(created_at__date=day).count() if app_model else 0})
    app_peak = max([d['n'] for d in app_days] + [1])
    for d in app_days:
        d['h'] = max(4, round(100 * d['n'] / app_peak)) if d['n'] else 4

    MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
    WEEK = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    today = f"{WEEK[now.weekday()].capitalize()} {now.day} {MONTHS[now.month - 1]} {now.year}"
    hero_kpis = [
        ('Comptes', User.objects.count()), ('Candidatures', _count('Emploi.Application')),
        ('Actualités', _count('Publications.Publication', is_published=True)), ('Commentaires non lus', comments['unread']),
    ]

    # ── Boutons rapides ──

    actions = [
        ('Publier une actualité', 'fa-newspaper', _url('Publications.Publication', add=True), 'green'),
        ('Publier dans le fil emploi', 'fa-rss', _url('Emploi.FeedPost', add=True), 'green'),
        ('Nouvelle offre d\'emploi', 'fa-bullhorn', _url('Emploi.JobOffer', add=True), 'green'),
        ('Ajouter un produit', 'fa-store', _url('Shop.Product', add=True), 'navy'),
        ('Ajouter une formation', 'fa-graduation-cap', _url('Formations.Formation', add=True), 'navy'),
        ('Ajouter un service', 'fa-wrench', _url('Services.Service', add=True), 'navy'),
        ('Ajouter un partenaire', 'fa-ribbon', _url('core.Partner', add=True), 'navy'),
        ('Commentaires à lire', 'fa-comments', comments['unread_url'], 'gold'),
        ('Réglages du site (prix, contacts)', 'fa-sliders-h', _url('core.SiteSettings'), 'gold'),
        ('Voir le site', 'fa-external-link-alt', '/', 'grey'),
    ]
    actions = [dict(label=a, icon=b, url=c, tone=d) for a, b, c, d in actions if c]

    return {
        'todo': todo, 'todo_total': total_todo, 'comments': comments, 'latest_comments': latest[:6], 'messages_latest': messages_latest,
        'stats': stats, 'days': days, 'app_days': app_days, 'actions': actions, 'today': today, 'hero_kpis': hero_kpis,
        'mail_from': getattr(settings, 'DEFAULT_FROM_EMAIL', '') or getattr(settings, 'EMAIL_HOST_USER', ''),
        'greeting': request.user.first_name or request.user.email,
    }

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
        ('Messages rapides non lus', _count('Publications.QuickMessage', is_read=False), 'fa-envelope', _url('Publications.QuickMessage', '?is_read__exact=0'), 'red'),
        ('Contacts des services non lus', _count('Services.ServiceContact', is_read=False), 'fa-phone-volume', _url('Services.ServiceContact', '?is_read__exact=0'), 'red'),
        ('Paiements en ligne en attente', _count('Payments.Payment', status='pending'), 'fa-credit-card', _url('Payments.Payment', '?status__exact=pending'), 'blue'),
        ('Commandes boutique en attente', _count('Shop.ShopOrder', status='pending'), 'fa-shopping-bag', _url('Shop.ShopOrder', '?status__exact=pending'), 'blue'),
        ('Réservations en attente', _count('Shop.Reservation', status='pending'), 'fa-calendar-check', _url('Shop.Reservation', '?status__exact=pending'), 'blue'),
        ('Demandes de monétisation à traiter', _count('core.MonetizationRequest', status='new'), 'fa-sack-dollar', _url('core.MonetizationRequest', '?status__exact=new'), 'orange'),
        ('Messages du portfolio non lus', _count('Portfolio.ContactMessage', is_read=False), 'fa-id-card', _url('Portfolio.ContactMessage', '?is_read__exact=0'), 'red'),
        ('Demandes de partenariat', _count('core.PartnerApplication', status='pending'), 'fa-ribbon', _url('core.PartnerApplication', '?status__exact=pending'), 'blue'),
    ]
    todo = [dict(label=a, n=b, icon=c, url=d, tone=e) for a, b, c, d, e in todo]
    total_todo = sum(t['n'] for t in todo)

    # ── Commentaires : lus / non lus / publiés ──
    pc, fc = _model('Publications.PublicationComment'), None  # module Emploi retiré
    pc_all = pc.objects.count() if pc else 0
    fc_all = fc.objects.count() if fc else 0
    pc_unread = pc.objects.filter(is_read=False).count() if pc else 0
    fc_unread = fc.objects.filter(is_read=False).count() if fc else 0
    comments = {
        'total': pc_all + fc_all, 'unread': pc_unread + fc_unread, 'read': pc_all + fc_all - pc_unread - fc_unread,
        'site_url': _url('Publications.PublicationComment'), 'feed_url': '',
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
        ('Actualités du site', _count('Publications.Publication', is_published=True), f"{views} lectures", 'fa-newspaper', _url('Publications.Publication')),
        ('Paiements en ligne reçus', _count('Payments.Payment', status='approved'), '', 'fa-credit-card', _url('Payments.Payment', '?status__exact=approved')),
        ('Événements', _count('Events.Event'), f"{_count('Events.Ticket')} tickets vendus", 'fa-calendar-days', _url('Events.Event')),
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
    app_model = _model('Payments.Payment')
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).date()
        app_days.append({'label': day.strftime('%d/%m'), 'n': app_model.objects.filter(status='approved', paid_at__date=day).count() if app_model else 0})
    app_peak = max([d['n'] for d in app_days] + [1])
    for d in app_days:
        d['h'] = max(4, round(100 * d['n'] / app_peak)) if d['n'] else 4

    # ── Argent encaissé (paiements réussis seulement) ──
    P = _model('Payments.Payment')
    argent = {}
    if P:
        ok = P.objects.filter(status='approved')

        def somme(qs):
            return qs.aggregate(s=Sum('amount'))['s'] or 0
        def f(n):
            return f"{int(n):,} F".replace(',', '\u202f')
        d30 = now - timedelta(days=30)
        argent = {
            'periodes': [
                {'label': '7 derniers jours', 'montant': f(somme(ok.filter(paid_at__gte=week))), 'n': ok.filter(paid_at__gte=week).count()},
                {'label': '30 derniers jours', 'montant': f(somme(ok.filter(paid_at__gte=d30))), 'n': ok.filter(paid_at__gte=d30).count()},
                {'label': 'Depuis le début', 'montant': f(somme(ok)), 'n': ok.count()},
            ],
            'statuts': [
                ('Réussis', ok.count(), '#0B7A4B', _url('Payments.Payment', '?status__exact=approved')),
                ('En attente', P.objects.filter(status='pending').count(), '#9A6700', _url('Payments.Payment', '?status__exact=pending')),
                ('Refusés / annulés', P.objects.filter(status__in=('declined', 'canceled')).count(), '#B42318', _url('Payments.Payment', '?status__in=declined,canceled')),
                ('Remboursés', P.objects.filter(status='refunded').count(), '#6D28D9', _url('Payments.Payment', '?status__exact=refunded')),
            ],
            'par_type': [
                (label, f(somme(ok.filter(kind=k))), ok.filter(kind=k).count(), _url('Payments.Payment', f'?status__exact=approved&kind__exact={k}'))
                for k, label in (('abonnement', 'Abonnements concours'), ('product', 'Boutique (produit)'), ('shop', 'Boutique (panier)'),
                                 ('formation', 'Formations'), ('ticket', "Tickets d'événement"), ('soutien', 'Soutiens'),
                                 ('service', 'Services'))
            ],
            'derniers': [{'ref': p.reference, 'qui': f"{p.first_name} {p.last_name}".strip(), 'objet': p.description,
                          'montant': f(p.amount), 'statut': p.get_status_display(), 'status': p.status,
                          'quand': p.created_at, 'url': _change_url(p)}
                         for p in P.objects.order_by('-created_at')[:10]],
            'url': _url('Payments.Payment'),
        }
        jours = []
        for i in range(29, -1, -1):
            day = (now - timedelta(days=i)).date()
            jours.append({'label': day.strftime('%d/%m'), 'v': somme(ok.filter(paid_at__date=day))})
        pic = max([j['v'] for j in jours] + [1])
        for j in jours:
            j['h'] = max(3, round(100 * j['v'] / pic)) if j['v'] else 3
            j['txt'] = f(j['v'])
        argent['jours'] = jours

    MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
    WEEK = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    today = f"{WEEK[now.weekday()].capitalize()} {now.day} {MONTHS[now.month - 1]} {now.year}"
    hero_kpis = [
        ('Actualités', _count('Publications.Publication', is_published=True)), ('Commentaires non lus', comments['unread']),
    ]

    # ── Boutons rapides ──

    actions = [
        ('Publier une actualité', 'fa-newspaper', _url('Publications.Publication', add=True), 'green'),
        ('Créer un événement', 'fa-calendar-plus', _url('Events.Event', add=True), 'green'),
        ('Ajouter un produit', 'fa-store', _url('Shop.Product', add=True), 'navy'),
        ('Ajouter une formation', 'fa-graduation-cap', _url('Formations.Formation', add=True), 'navy'),
        ('Ajouter un service', 'fa-wrench', _url('Services.Service', add=True), 'navy'),
        ('Ajouter un partenaire', 'fa-ribbon', _url('core.Partner', add=True), 'navy'),
        ('Commentaires à lire', 'fa-comments', comments['unread_url'], 'gold'),
        ('Modifier mon portfolio', 'fa-user-tie', _url('Portfolio.Profile'), 'navy'),
        ('Réglages du site (prix, contacts)', 'fa-sliders-h', _url('core.SiteSettings'), 'gold'),
        ('Voir le site', 'fa-external-link-alt', '/', 'grey'),
    ]
    actions = [dict(label=a, icon=b, url=c, tone=d) for a, b, c, d in actions if c]

    return {
        'todo': todo, 'todo_total': total_todo, 'comments': comments, 'latest_comments': latest[:6], 'messages_latest': messages_latest,
        'argent': argent, 'stats': stats, 'days': days, 'app_days': app_days, 'actions': actions, 'today': today, 'hero_kpis': hero_kpis,
        'mail_from': getattr(settings, 'DEFAULT_FROM_EMAIL', '') or getattr(settings, 'EMAIL_HOST_USER', ''),
        'greeting': request.user.first_name or request.user.email,
    }

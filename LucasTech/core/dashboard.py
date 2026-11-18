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
        ('Dossiers de répétiteurs à vérifier', _count('Repetiteurs.Candidature', statut='a_verifier'), 'fa-chalkboard-teacher', _url('Repetiteurs.Candidature', '?statut__exact=a_verifier'), 'orange'),
        ('Demandes de vendeurs', _count('Marche.DemandeVendeur', statut='en_attente'), 'fa-user-tag', _url('Marche.DemandeVendeur', '?statut__exact=en_attente'), 'blue'),
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
            return f"{int(n):,} CFA".replace(',', '\u202f')
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
                for k, label in (('concours', 'Concours débloqués'), ('abonnement', 'Abonnements (anciens)'), ('product', 'Boutique (produit)'), ('shop', 'Boutique (panier)'),
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

    icones = {'paiements': 'fa-credit-card', 'concours': 'fa-file-alt', 'boutique': 'fa-store', 'vendeurs': 'fa-user-tag',
               'emplois': 'fa-briefcase', 'formations': 'fa-graduation-cap', 'evenements': 'fa-calendar-days',
               'ecoles': 'fa-school', 'repetiteurs': 'fa-chalkboard-teacher', 'publications': 'fa-newspaper',
               'services': 'fa-wrench', 'notifications': 'fa-bell', 'utilisateurs': 'fa-users'}
    rubriques = [{'titre': t, 'icon': icones.get(c, 'fa-folder'), 'url': f'/lantanteAdminTech/section/{c}/'}
                 for c, (t, _) in SECTIONS.items()]
    return {
        'rubriques': rubriques,
        'todo': todo, 'todo_total': total_todo, 'comments': comments, 'latest_comments': latest[:6], 'messages_latest': messages_latest,
        'argent': argent, 'stats': stats, 'days': days, 'app_days': app_days, 'actions': actions, 'today': today, 'hero_kpis': hero_kpis,
        'mail_from': getattr(settings, 'DEFAULT_FROM_EMAIL', '') or getattr(settings, 'EMAIL_HOST_USER', ''),
        'greeting': request.user.first_name or request.user.email,
    }



def _f(n):
    return f"{int(n or 0):,} CFA".replace(',', '\u202f')


def build_delegue(request):
    """Ce que voit un délégué : ses événements, services, écoles, et leurs chiffres."""
    from django.db.models import Count, Q
    from django.urls import reverse
    from .delegations import evenements_visibles, ids, services_visibles
    u = request.user
    cartes = []
    from Events.models import Event
    for e in evenements_visibles(u, Event.objects.all()):
        ok = e.payments.filter(status='approved')
        cartes.append({'titre': e.title, 'type': 'Événement', 'chiffre': _f(ok.aggregate(s=Sum('amount'))['s']),
                       'detail': f"{ok.count()} payeur(s) · {e.payments.filter(status='pending').count()} en attente",
                       'url': reverse('admin:Events_event_change', args=[e.pk]),
                       'url2': reverse('admin:Payments_payment_changelist') + f'?event__id__exact={e.pk}', 'lien2': 'Paiements'})
    from Services.models import Service
    for s_ in services_visibles(u, Service.objects.all()):
        n = s_.inscriptions.count()
        cartes.append({'titre': s_.title, 'type': 'Service', 'chiffre': str(n),
                       'detail': f"inscription(s) · {s_.inscriptions.filter(statut='nouvelle').count()} nouvelle(s)",
                       'url': reverse('admin:Services_service_change', args=[s_.pk]),
                       'url2': reverse('admin:Services_inscriptionservice_changelist') + f'?service__id__exact={s_.pk}',
                       'lien2': 'Inscriptions'})
    try:
        from Ecoles.admin import mes_ecoles
        for e in mes_ecoles(u):
            cartes.append({'titre': e.nom, 'type': 'École', 'chiffre': str(e.inscriptions.count()),
                           'detail': f"inscription(s) · {e.inscriptions.filter(statut='nouvelle').count()} nouvelle(s)",
                           'url': reverse('admin:Ecoles_ecole_change', args=[e.pk]),
                           'url2': reverse('admin:Ecoles_inscriptionecole_changelist') + f'?ecole__id__exact={e.pk}',
                           'lien2': 'Inscriptions'})
    except Exception:  # pragma: no cover
        pass
    if u.delegations.filter(type='publications').exists():
        from Publications.models import Publication
        cartes.append({'titre': 'Actualités', 'type': 'Publications', 'chiffre': str(Publication.objects.count()),
                       'detail': 'article(s)', 'url': reverse('admin:Publications_publication_changelist'),
                       'url2': reverse('admin:Publications_publication_add'), 'lien2': 'Publier'})
    return {'greeting': u.first_name or u.email, 'cartes': cartes}


SECTIONS = {
    'paiements': ("Paiements", [('Payments.Payment', 'Paiements')]),
    'concours': ("Concours", [('concours.Contest', 'Concours'), ('concours.ContestSession', 'Années'),
                              ('concours.ExamPaper', 'Épreuves'), ('concours.Correction', 'Corrigés'),
                              ('abonnements.UserSubscription', 'Abonnements (anciens)')]),
    'boutique': ("Boutique", [('Shop.Product', 'Produits'), ('Shop.Category', 'Catégories'), ('Shop.ShopOrder', 'Commandes'),
                              ('Marche.ReglageLivraison', 'Livraisons'), ('Payments.CodePromo', 'Codes promo')]),
    'vendeurs': ("Vendeurs", [('Marche.Vendeur', 'Vendeurs'), ('Marche.CategorieVendeur', 'Catégories des vendeurs'),
                              ('Marche.DemandeVendeur', 'Demandes'), ('Marche.Reversement', 'Reversements')]),
    'emplois': ("Emplois", [('Offres.OffreEmploi', "Offres d'emploi")]),
    'formations': ("Formations", [('Formations.Formation', 'Formations'), ('Formations.Registration', 'Inscriptions')]),
    'evenements': ("Événements", [('Events.Event', 'Événements'), ('Events.Ticket', 'Tickets')]),
    'ecoles': ("Écoles", [('Ecoles.Ecole', 'Écoles'), ('Ecoles.Filiere', 'Filières')]),
    'repetiteurs': ("Répétiteurs", [('Repetiteurs.Repetiteur', 'Répétiteurs'), ('Repetiteurs.Candidature', 'Candidatures'),
                                    ('Repetiteurs.ReglageCandidature', 'Réglages des candidatures')]),
    'publications': ("Actualités", [('Publications.Publication', 'Articles'), ('Publications.PublicationCategory', 'Catégories'),
                                    ('Publications.PublicationComment', 'Commentaires'),
                                    ('Publications.PublicationLike', "J'aime")]),
    'services': ("Services", [('Services.Service', 'Services'), ('Services.InscriptionService', 'Inscriptions'),
                              ('Services.ServiceCategory', 'Catégories')]),
    'notifications': ("Notifications et accueil", [('api_mobile.Notification', 'Notifications'),
                                                   ('api_mobile.CarouselItem', "Carrousel de l'accueil")]),
    'utilisateurs': ("Utilisateurs et rôles", [('Users.User', 'Utilisateurs'), ('core.Delegation', 'Rôles délégués')]),
}


def build_section(request, code):
    """Page d'un grand titre : chiffres de chaque élément + liens « Gérer » / « Ajouter »."""
    titre, modeles = SECTIONS[code]
    lignes = []
    if code == 'paiements' and not request.user.is_superuser:
        return {'titre': titre, 'lignes': [], 'extra': []}
    for label, nom in modeles:
        m = _model(label)
        if not m:
            continue
        u, o = request.user, m._meta
        if not (u.has_perm(f'{o.app_label}.view_{o.model_name}') or u.has_perm(f'{o.app_label}.change_{o.model_name}')):
            continue
        ajout = _url(label, add=True) if u.has_perm(f'{o.app_label}.add_{o.model_name}') else ''
        from django.contrib import admin as _admin
        ma = _admin.site._registry.get(m)
        try:
            n = ma.get_queryset(request).count() if ma and not u.is_superuser else m.objects.count()
        except Exception:
            n = 0
        lignes.append({'nom': nom, 'n': n, 'url': _url(label), 'ajout': ajout})
    extra = []
    if not request.user.is_superuser:  # chiffres d'argent : super-admins seulement
        return {'titre': titre, 'lignes': lignes, 'extra': _chiffres(code) if lignes else []}
    P = _model('Payments.Payment')
    kinds = {'paiements': None, 'concours': ('concours', 'abonnement'), 'boutique': ('product', 'shop'),
             'formations': ('formation',), 'evenements': ('ticket', 'soutien'), 'services': ('service',)}
    if P and code in kinds:
        ok = P.objects.filter(status='approved')
        if kinds[code]:
            ok = ok.filter(kind__in=kinds[code])
        extra = [('Encaissé', _f(ok.aggregate(s=Sum('amount'))['s'])), ('Paiements réussis', ok.count())]
    extra += _chiffres(code)
    return {'titre': titre, 'lignes': lignes, 'extra': extra}


def _chiffres(code):
    """Chiffres propres à chaque rubrique (en plus des paiements)."""
    from django.db.models import F
    try:
        if code == 'emplois':
            O = _model('Offres.OffreEmploi')
            a = O.objects.aggregate(v=Sum('vues'), t=Sum('clics_appel'), w=Sum('clics_whatsapp'), l=Sum('clics_lien'), e=Sum('clics_email'))
            actives = sum(1 for o in O.objects.filter(publie=True) if o.active)
            return [('Offres en ligne', actives), ('Vues', a['v'] or 0),
                    ('Contacts (appel, WhatsApp, lien, e-mail)', sum((a[k] or 0) for k in 'twle'))]
        if code == 'publications':
            return [('Lectures', _model('Publications.Publication').objects.aggregate(v=Sum('views_count'))['v'] or 0),
                    ("J'aime", _count('Publications.PublicationLike')),
                    ('Commentaires non lus', _count('Publications.PublicationComment', is_read=False)),
                    ('Sans réponse', _count('Publications.PublicationComment', repondu_le__isnull=True))]
        if code == 'repetiteurs':
            return [('Dossiers à vérifier', _count('Repetiteurs.Candidature', statut='a_verifier')),
                    ('Répétiteurs en ligne', _count('Repetiteurs.Repetiteur', actif=True))]
        if code == 'vendeurs':
            return [('Vendeurs validés', _count('Marche.Vendeur', statut='valide')),
                    ('Produits des vendeurs', _count('Shop.Product', vendeur__isnull=False))]
        if code == 'services':
            a = _model('Services.Service').objects.aggregate(w=Sum('clics_whatsapp'), s=Sum('clics_support'))
            return [('Contacts WhatsApp', a['w'] or 0), ('Contacts support', a['s'] or 0)]
        if code == 'boutique':
            P = _model('Shop.Product')
            a = P.objects.aggregate(v=Sum('vues'), w=Sum('clics_whatsapp'))
            return [('Commandes en attente', _count('Shop.ShopOrder', status='pending')),
                    ('Vues des produits', a['v'] or 0), ('Clics WhatsApp', a['w'] or 0)]
    except Exception:
        return []
    return []

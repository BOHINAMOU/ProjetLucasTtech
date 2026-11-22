"""Admin : traitement d'une plainte (identité complète + réponse), fiche détaillée d'un client et d'une boutique."""
from datetime import timedelta

from django.contrib import admin as _admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

JOURS = 14


def _f(n):
    return f"{int(n or 0):,} F".replace(',', ' ')


def _date(d, motif='%d/%m/%Y %H:%M'):
    return timezone.localtime(d).strftime(motif) if d else '—'


def _c(texte, url='', pil=''):
    """Cellule de tableau : texte, lien facultatif, pastille de couleur facultative."""
    return {'t': texte if texte not in (None, '') else '—', 'u': url, 'p': pil}


def _debut():
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=JOURS - 1)


def _serie(titre, dates_valeurs, unite=''):
    """Barres des 14 derniers jours (jours sans activité compris)."""
    debut = _debut()
    par_jour = {}
    for quand, v in dates_valeurs:
        j = timezone.localtime(quand).date()
        par_jour[j] = par_jour.get(j, 0) + v
    maxi = max(par_jour.values(), default=0) or 1
    points = []
    for i in range(JOURS):
        j = (debut + timedelta(days=i)).date()
        n = par_jour.get(j, 0)
        points.append({'j': j.strftime('%d/%m'), 'n': n, 'h': round(100 * n / maxi), 'unite': unite})
    return {'titre': titre, 'points': points}


def _page(request, **ctx):
    return render(request, 'admin/stats.html', dict(_admin.site.each_context(request), **ctx))


def _identite(u):
    return [("Nom", u.last_name), ("Prénom", u.first_name), ("Téléphone", u.phone), ("E-mail", u.email),
            ("Pays", u.country), ("Ville", u.city), ("Inscrit le", _date(u.date_joined, '%d/%m/%Y')),
            ("Dernière connexion", _date(u.last_login))]


STATUTS_COURSE = {'recherche': ('Recherche', 'or'), 'acceptee': ('En route', 'bl'), 'arrive': ('Arrivé', 'bl'),
                  'en_cours': ('En course', 'bl'), 'terminee': ('Terminée', 'ok'), 'annulee': ('Annulée', 'ko'),
                  'aucun_partenaire': ('Aucun coursier', 'ko'), 'litige': ('Litige', 'ko')}
STATUTS_PLAINTE = {'nouveau': 'ko', 'en_cours': 'or', 'resolu': 'ok', 'rejete': ''}


@staff_member_required
def plainte(request, pk):
    """Une plainte : qui, quelle course, ce qui s'est passé, et le formulaire « Répondre »."""
    from courses.models import Signalement
    from courses.services import _notifier
    if not request.user.has_perm('courses.view_signalement'):
        raise Http404
    s = Signalement.objects.select_related('course__client', 'course__partenaire__user', 'course__categorie', 'auteur').filter(pk=pk).first()
    if not s:
        raise Http404
    peut = request.user.has_perm('courses.change_signalement')
    if request.method == 'POST' and peut:
        reponse = (request.POST.get('reponse') or '').strip()
        statut = request.POST.get('statut') or 'resolu'
        if not reponse or statut not in dict(Signalement._meta.get_field('statut').choices):
            messages.error(request, "Écrivez votre réponse.")
        else:
            s.reponse, s.statut = reponse[:2000], statut
            s.save(update_fields=['reponse', 'statut'])
            _notifier(s.auteur, f"Réponse à votre signalement ({s.course.reference})", reponse[:560])
            messages.success(request, "Réponse envoyée. La personne a reçu une notification.")
        return redirect('admin_plainte', s.pk)
    c, a = s.course, s.auteur
    p = c.partenaire
    infos_course = [("Course", c.reference), ("Date", _date(c.created_at)), ("Véhicule", c.categorie.nom),
                    ("Départ", c.depart_adresse), ("Arrivée", c.arrivee_adresse),
                    ("Prix", _f(c.total_client)), ("Coursier", (p.user.get_full_name() or p.user.email) if p else '—'),
                    ("Téléphone du coursier", (p.telephone or p.user.phone) if p else '—'),
                    ("Plaque", p.plaque if p else '—')]
    fiche = reverse('admin_coursier', args=[p.pk]) if s.par == 'partenaire' and p else reverse('admin_client', args=[a.pk])
    return _page(
        request, title=f"Plainte · {c.reference}", retour=(reverse('admin_section', args=['courses']) + '?vue=demandes', "Plaintes et demandes"),
        entete={'titre': s.get_motif_display(), 'sous': f"Par {a.get_full_name() or a.email} ({'client' if s.par == 'client' else 'coursier'}) · {_date(s.created_at)}",
                'icone': 'report', 'pastilles': [(s.get_statut_display(), STATUTS_PLAINTE.get(s.statut, ''))],
                'actions': [("Voir sa fiche", fiche, True), ("Voir la course", reverse('admin:courses_course_change', args=[c.pk]), False)]},
        blocs=[{'titre': "Personne qui signale", 'lignes': _identite(a)}, {'titre': "Course concernée", 'lignes': infos_course}],
        message={'titre': "Son message", 'texte': s.commentaire or "Aucun commentaire.",
                 'piece': reverse('admin:courses_signalement_change', args=[s.pk]) if s.piece_jointe else ''},
        reponse={'texte': s.reponse, 'statut': s.statut, 'statuts': Signalement._meta.get_field('statut').choices} if peut else None)


@staff_member_required
def client(request, pk):
    """Fiche d'un client : identité, activité des 14 derniers jours, courses, paiements, plaintes."""
    from courses.models import Signalement
    from Payments.models import Payment
    if not request.user.has_perm('Users.view_user'):
        raise Http404
    u = get_user_model().objects.filter(pk=pk).first()
    if not u:
        raise Http404
    debut = _debut()
    courses = u.courses_express.select_related('categorie', 'partenaire__user').order_by('-created_at')
    recentes = list(courses.filter(created_at__gte=debut))
    finies = [c for c in recentes if c.statut == 'terminee']
    paiements = Payment.objects.filter(user=u).order_by('-created_at')
    plaintes = Signalement.objects.filter(auteur=u).select_related('course').order_by('-created_at')
    kpis = [("Courses (14 jours)", len(recentes), 'local_taxi'), ("Terminées (14 jours)", len(finies), 'check_circle'),
            ("Annulées (14 jours)", sum(1 for c in recentes if c.statut == 'annulee'), 'cancel'),
            ("Courses au total", courses.count(), 'route'),
            ("Plaintes", plaintes.count(), 'report')]
    if request.user.is_superuser:
        from Payments.solde import portefeuille
        kpis += [("Dépensé en courses (14 j)", _f(sum(c.total_client for c in finies)), 'payments'),
                 ("Achats payés", _f(paiements.filter(status='approved').aggregate(s=Sum('amount'))['s']), 'shopping_bag'),
                 ("Solde", _f(portefeuille(u).solde), 'account_balance_wallet')]
    tableaux = [{
        'titre': "Ses courses", 'colonnes': ["Date", "N°", "Coursier", "Trajet", "Prix", "Statut"], 'vide': "Aucune course.",
        'lignes': [[_c(_date(c.created_at, '%d/%m %H:%M')), _c(c.reference, reverse('admin:courses_course_change', args=[c.pk])),
                    _c(c.partenaire.user.get_full_name() or c.partenaire.user.email if c.partenaire else '—',
                       reverse('admin_coursier', args=[c.partenaire_id]) if c.partenaire_id else ''),
                    _c(f"{c.depart_adresse[:32]} → {c.arrivee_adresse[:32]}"), _c(_f(c.total_client)),
                    _c(*(lambda x: (x[0], '', x[1]))(STATUTS_COURSE.get(c.statut, (c.statut, ''))))] for c in courses[:40]],
    }, {
        'titre': "Ses plaintes", 'colonnes': ["Date", "Course", "Motif", "Statut"], 'vide': "Aucune plainte.",
        'lignes': [[_c(_date(s.created_at, '%d/%m %H:%M')), _c(s.course.reference), _c(s.get_motif_display(), reverse('admin_plainte', args=[s.pk])),
                    _c(s.get_statut_display(), '', STATUTS_PLAINTE.get(s.statut, ''))] for s in plaintes[:15]],
    }]
    if request.user.is_superuser:
        tableaux.append({
            'titre': "Ses paiements", 'colonnes': ["Date", "Type", "Montant", "Statut"], 'vide': "Aucun paiement.",
            'lignes': [[_c(_date(x.created_at, '%d/%m %H:%M')), _c(x.get_kind_display()), _c(_f(x.amount)),
                        _c(x.get_status_display(), '', 'ok' if x.status == 'approved' else '')] for x in paiements[:15]],
        })
    return _page(
        request, title=u.get_full_name() or u.email, retour=(reverse('admin:courses_compteclient_changelist'), "Clients"),
        entete={'titre': u.get_full_name() or u.email, 'sous': u.phone or u.email, 'icone': 'person',
                'photo': u.avatar.url if u.avatar else '',
                'pastilles': [("Actif", 'ok') if u.is_active else ("Désactivé", 'ko')],
                'actions': [("Modifier le compte", reverse('admin:Users_user_change', args=[u.pk]), True)]},
        blocs=[{'titre': "Identité", 'lignes': _identite(u)}], kpis=kpis,
        serie=_serie("Courses par jour · 14 derniers jours", [(c.created_at, 1) for c in recentes]), tableaux=tableaux)


@staff_member_required
def boutique(request, pk):
    """Fiche d'une boutique : ventes, visites, produits, commandes et reversements."""
    from Marche.admin import comptes
    from Marche.models import Vendeur
    from Payments.models import Payment
    ma = _admin.site._registry.get(Vendeur)
    v = ma.get_queryset(request).select_related('user').filter(pk=pk).first() if ma else None
    if not v or not ma.has_view_or_change_permission(request, v):
        raise Http404
    produits = list(v.produits.select_related('category').order_by('-vues', 'name'))
    debut = _debut()
    ventes = Payment.objects.filter(vendeur=v, status='approved').select_related('user').order_by('-created_at')
    recentes = list(ventes.filter(created_at__gte=debut))
    argent = request.user.is_superuser
    kpis = [("Produits", len(produits), 'inventory_2'), ("En vente", sum(1 for p in produits if p.is_available), 'storefront'),
            ("Rupture de stock", sum(1 for p in produits if p.stock <= 0), 'production_quantity_limits'),
            ("Vues des produits", sum(p.vues for p in produits), 'visibility'),
            ("Clics WhatsApp", sum(p.clics_whatsapp for p in produits), 'chat'),
            ("Ventes (14 jours)", len(recentes), 'shopping_cart')]
    if argent:
        co = comptes(v)
        kpis += [("Ventes au total", co['ventes'], 'receipt_long'), ("Encaissé", _f(co['encaisse']), 'payments'),
                 ("Commission Lantante", _f(co['commission']), 'percent'), ("Dû au vendeur", _f(co['du']), 'account_balance'),
                 ("Déjà reversé", _f(co['reverse']), 'send_money'), ("Reste à reverser", _f(co['reste']), 'pending')]
    tableaux = [{
        'titre': "Produits", 'colonnes': ["Produit", "Catégorie", "Prix", "Stock", "Vues", "WhatsApp", "État"], 'vide': "Aucun produit.",
        'lignes': [[_c(p.name, reverse('admin:Shop_product_change', args=[p.pk])), _c(p.category.name if p.category else '—'), _c(_f(p.price)),
                    _c(p.stock), _c(p.vues), _c(p.clics_whatsapp),
                    _c('En vente', '', 'ok') if p.is_available else _c('Masqué', '', '')] for p in produits[:100]],
    }]
    if argent:
        tableaux.append({
            'titre': "Dernières ventes", 'colonnes': ["Date", "Client", "Téléphone", "Montant", "Commission"], 'vide': "Aucune vente.",
            'lignes': [[_c(_date(x.created_at, '%d/%m %H:%M')),
                        _c((x.user.get_full_name() or x.user.email) if x.user else '—', reverse('admin_client', args=[x.user_id]) if x.user_id else ''),
                        _c(x.user.phone if x.user else '—'), _c(_f(x.amount)), _c(_f(x.commission))] for x in ventes[:25]],
        })
        tableaux.append({
            'titre': "Reversements", 'colonnes': ["Date", "Montant", "Référence"], 'vide': "Aucun reversement.",
            'lignes': [[_c(r.date.strftime('%d/%m/%Y')), _c(_f(r.montant)), _c(r.reference)] for r in v.reversements.all()[:15]],
        })
    infos = [("Boutique", v.boutique), ("Propriétaire", v.user.get_full_name() or v.user.email), ("E-mail", v.user.email),
             ("WhatsApp", v.whatsapp), ("Téléphone", v.telephone or v.user.phone), ("Ville", v.ville),
             ("Point de retrait", v.adresse_retrait), ("Accès jusqu'au", v.fin_acces.strftime('%d/%m/%Y') if v.fin_acces else "Sans limite"),
             ("Créée le", _date(v.created_at, '%d/%m/%Y'))]
    actions = [("Gérer la boutique", reverse('admin_fiche', args=['vendeurs', v.pk]), True)]
    if v.slug:
        actions.append(("Boutique publique", v.lien_public(), False))
    return _page(
        request, title=v.boutique, retour=(reverse('admin_section', args=['vendeurs']), "Vendeurs"),
        entete={'titre': v.boutique, 'sous': f"{v.ville} · {v.user.get_full_name() or v.user.email}", 'icone': 'storefront',
                'photo': v.logo.url if v.logo else '',
                'pastilles': [(v.get_statut_display(), 'ok' if v.actif else 'ko')], 'actions': actions},
        blocs=[{'titre': "Coordonnées", 'lignes': infos}], kpis=kpis,
        serie=_serie("Ventes par jour · 14 derniers jours", [(x.created_at, 1) for x in recentes]), tableaux=tableaux)


def chiffres_vendeurs():
    """Grandes lignes de la rubrique Vendeurs."""
    from Marche.models import Vendeur
    from Payments.models import Payment
    from Shop.models import Product
    a = Vendeur.objects.aggregate(n=Count('pk'), ok=Count('pk', filter=Q(statut='valide')),
                                  att=Count('pk', filter=Q(statut='en_attente')),
                                  sus=Count('pk', filter=Q(statut__in=('suspendu', 'expire'))))
    ventes = Payment.objects.filter(vendeur__isnull=False, status='approved', created_at__gte=_debut())
    return [('Boutiques', a['n']), ('Actives', a['ok']), ('En attente', a['att']), ('Suspendues ou expirées', a['sus']),
            ('Produits des vendeurs', Product.objects.filter(vendeur__isnull=False).count()),
            ('Ventes (14 jours)', ventes.count())]

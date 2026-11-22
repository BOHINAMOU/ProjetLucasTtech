"""Lantante Express dans l'admin : un tableau de bord organisé en onglets
(Aujourd'hui, Coursiers, Plaintes et demandes, Statistiques, Réglages) et la fiche de chaque coursier."""
from datetime import timedelta

from django.contrib import admin as _admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

ONGLETS = [('jour', "Aujourd'hui", 'today'), ('coursiers', "Coursiers", 'two_wheeler'),
           ('demandes', "Plaintes et demandes", 'support_agent'), ('stats', "Statistiques", 'bar_chart'),
           ('reglages', "Réglages", 'tune')]
EN_COURS = ('recherche', 'acceptee', 'arrive', 'en_cours')
STATUTS = {'recherche': ('Recherche', 'or'), 'acceptee': ('Coursier en route', 'bl'), 'arrive': ('Coursier arrivé', 'bl'),
           'en_cours': ('En course', 'bl'), 'terminee': ('Terminée', 'ok'), 'annulee': ('Annulée', 'ko'),
           'aucun_partenaire': ('Aucun coursier', 'ko'), 'litige': ('Litige', 'ko')}


def _f(n):
    return f"{int(n or 0):,} F".replace(',', ' ')


def _u(nom, *args):
    return reverse(f'admin:courses_{nom}', args=args)


def _debut_jour():
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


def _ligne_course(c):
    lib, cls = STATUTS.get(c.statut, (c.statut, ''))
    p = c.partenaire
    return {'c': c, 'heure': timezone.localtime(c.created_at).strftime('%H:%M'),
            'date': timezone.localtime(c.created_at).strftime('%d/%m %H:%M'), 'statut': lib, 'cls': cls,
            'prix': _f(c.prix_final or c.prix_estime), 'client': c.client.get_full_name() or c.client.email,
            'coursier': (p.user.get_full_name() or p.user.email) if p else '—',
            'coursier_url': reverse('admin_coursier', args=[p.pk]) if p else '',
            'client_url': reverse('admin_client', args=[c.client_id]),
            'url': _u('course_change', c.pk)}


def _nom(p):
    return p.user.get_full_name() or p.user.email


def _jour(C, P, M):
    d0 = _debut_jour()
    du_jour = C.objects.filter(created_at__gte=d0)
    term = du_jour.filter(statut='terminee')
    commission = -(M.objects.filter(created_at__gte=d0, type='commission').aggregate(s=Sum('montant'))['s'] or 0)
    kpis = [("Courses du jour", du_jour.count(), 'local_taxi'),
            ("Terminées", term.count(), 'check_circle'),
            ("En cours maintenant", C.objects.filter(statut__in=EN_COURS).count(), 'directions_run'),
            ("Annulées", du_jour.filter(statut='annulee').count(), 'cancel'),
            ("Sans coursier", du_jour.filter(statut='aucun_partenaire').count(), 'person_off'),
            ("Montant des courses", _f(sum((c.prix_final or c.prix_estime) for c in term)), 'payments'),
            ("Commission Lantante", _f(commission), 'savings'),
            ("Coursiers en ligne", P.objects.filter(en_ligne=True, statut='valide').count(), 'wifi_tethering')]
    lignes = [_ligne_course(c) for c in du_jour.select_related('client', 'partenaire__user', 'categorie')
              .order_by('-created_at')[:100]]
    return {'kpis': kpis, 'courses': lignes}


def _coursiers(C, P, filtre='tous'):
    d0 = _debut_jour()
    base = P.objects.all()
    if filtre == 'actifs':
        base = base.filter(statut='valide')
    elif filtre == 'en_ligne':
        base = base.filter(statut='valide', en_ligne=True)
    elif filtre == 'non_actifs':
        base = base.exclude(statut='valide')
    elif filtre == 'solde_negatif':
        from courses.models import Parametres
        base = base.filter(solde__lte=-int(Parametres.get().alerte_solde))
    qs = (base.select_related('user')
          .annotate(n_jour=Count('courses', filter=Q(courses__created_at__gte=d0), distinct=True),
                    n_total=Count('courses', filter=Q(courses__statut='terminee'), distinct=True))
          .order_by('-en_ligne', 'statut', '-n_jour'))
    kpis = [("Inscrits", P.objects.count(), 'group'),
            ("Validés", P.objects.filter(statut='valide').count(), 'verified'),
            ("En ligne", P.objects.filter(en_ligne=True, statut='valide').count(), 'wifi_tethering'),
            ("À valider", P.objects.filter(statut='en_attente').count(), 'pending_actions'),
            ("Profil à compléter", P.objects.filter(statut='a_completer').count(), 'edit_note'),
            ("Suspendus", P.objects.filter(statut='suspendu').count(), 'block')]
    liste = [{'p': p, 'nom': _nom(p), 'url': reverse('admin_coursier', args=[p.pk]),
              'vehicule': p.get_type_vehicule_display() or '—', 'statut': p.get_statut_display(),
              'cls': {'valide': 'ok', 'en_attente': 'or', 'a_completer': 'or'}.get(p.statut, 'ko')} for p in qs[:300]]
    from courses.models import Parametres
    seuil = -int(Parametres.get().alerte_solde)
    filtres = [('tous', "Tous", P.objects.count()), ('actifs', "Actifs (validés)", P.objects.filter(statut='valide').count()),
               ('en_ligne', "En ligne", P.objects.filter(statut='valide', en_ligne=True).count()),
               ('non_actifs', "Non actifs", P.objects.exclude(statut='valide').count()),
               ('solde_negatif', "Solde trop bas", P.objects.filter(solde__lte=seuil).count())]
    return {'kpis': kpis, 'coursiers': liste, 'filtres': filtres, 'filtre': filtre}


def _demandes():
    from courses.models import DemandeChangementType, DemandeVersement, DocumentPartenaire, Remboursement, Signalement
    blocs = []

    def bloc(titre, icone, qs, lien, ligne):
        blocs.append({'titre': titre, 'icone': icone, 'n': qs.count(), 'lien': lien, 'lignes': [ligne(x) for x in qs[:8]]})

    bloc("Plaintes à traiter", 'report', Signalement.objects.filter(statut__in=('nouveau', 'en_cours'))
         .select_related('course__partenaire__user', 'auteur').order_by('-created_at'), _u('signalement_changelist'),
         lambda s: (f"{s.get_motif_display()} · "
                    f"{'client' if s.par == 'client' else 'coursier'}", f"{s.auteur.get_full_name() or s.auteur.email} · {s.auteur.phone or ''} · Coursier : "
                    f"{(s.course.partenaire.user.get_full_name() or s.course.partenaire.user.email) if s.course.partenaire_id else '—'}", reverse('admin_plainte', args=[s.pk])))
    bloc("Papiers à vérifier", 'badge', DocumentPartenaire.objects.filter(statut='en_attente')
         .select_related('partenaire__user').order_by('created_at'), _u('documentpartenaire_changelist') + '?statut__exact=en_attente',
         lambda d: (d.get_type_display(), _nom(d.partenaire), reverse('admin_coursier', args=[d.partenaire_id])))
    bloc("Changements de véhicule", 'swap_horiz', DemandeChangementType.objects.filter(statut='en_attente')
         .select_related('partenaire__user'), _u('demandechangementtype_changelist'),
         lambda d: (f"{d.partenaire.get_type_vehicule_display() or '—'} → {d.get_vehicule_demande_display() or d.get_type_demande_display()}",
                    _nom(d.partenaire), _u('demandechangementtype_change', d.pk)))
    bloc("Retraits demandés par les coursiers", 'account_balance_wallet', DemandeVersement.objects.filter(statut='en_attente')
         .select_related('partenaire__user'), _u('demandeversement_changelist'),
         lambda v: (_f(v.montant), f"{_nom(v.partenaire)} · {v.numero}", _u('demandeversement_change', v.pk)))
    from courses.models import MessageSupport, Parametres, Partenaire
    bloc("Coursiers à contacter : solde trop bas", 'warning',
         Partenaire.objects.filter(solde__lte=-int(Parametres.get().alerte_solde)).select_related('user').order_by('solde'),
         reverse('admin_section', args=['courses']) + '?vue=coursiers&filtre=solde_negatif',
         lambda p: (f"{_nom(p)} : {_f(p.solde)}", p.telephone or p.user.phone or p.user.email,
                    reverse('admin_coursier', args=[p.pk])))
    bloc("Réponses des coursiers", 'forum', MessageSupport.objects.filter(par='coursier', lu_le__isnull=True)
         .select_related('partenaire__user').order_by('-created_at'), _u('messagesupport_changelist') + '?par__exact=coursier',
         lambda m: (_nom(m.partenaire), m.texte[:80], reverse('admin_coursier', args=[m.partenaire_id]) + '#support'))
    bloc("Remboursements à valider", 'currency_exchange', Remboursement.objects.filter(statut='en_attente')
         .select_related('course'), _u('remboursement_changelist'),
         lambda r: (_f(r.montant), f"Course {r.course.reference} · {r.motif[:60]}", _u('remboursement_change', r.pk)))
    return {'blocs': blocs}


def _stats(C, jours=30):
    from api_mobile.models import Notification
    from courses.models import Annulation, MessageCourse, Note, Signalement
    d0 = _debut_jour() - timedelta(days=jours - 1)
    series = []
    qs = C.objects.filter(created_at__gte=d0).only('created_at', 'statut')
    compte, fini = {}, {}
    for c in qs:
        j = timezone.localtime(c.created_at).date()
        compte[j] = compte.get(j, 0) + 1
        if c.statut == 'terminee':
            fini[j] = fini.get(j, 0) + 1
    maxi = max(compte.values(), default=0) or 1
    for i in range(jours):
        j = (d0 + timedelta(days=i)).date()
        series.append({'j': j.strftime('%d/%m'), 'n': compte.get(j, 0), 't': fini.get(j, 0),
                       'h': round(100 * compte.get(j, 0) / maxi)})
    d7 = _debut_jour() - timedelta(days=6)
    periodes = []
    for titre, debut in (("Aujourd'hui", _debut_jour()), ("7 derniers jours", d7), ("30 derniers jours", d0)):
        msgs = MessageCourse.objects.filter(created_at__gte=debut)
        periodes.append({'titre': titre, 'lignes': [
            ("Courses commandées", C.objects.filter(created_at__gte=debut).count()),
            ("Courses terminées", C.objects.filter(created_at__gte=debut, statut='terminee').count()),
            ("Courses annulées", C.objects.filter(created_at__gte=debut, statut='annulee').count()),
            ("Sans coursier", C.objects.filter(created_at__gte=debut, statut='aucun_partenaire').count()),
            ("Messages envoyés (client ↔ coursier)", msgs.count()),
            ("dont messages vocaux", msgs.filter(type='audio').count()),
            ("Notifications envoyées", Notification.objects.filter(created_at__gte=debut).count()),
            ("Plaintes reçues", Signalement.objects.filter(created_at__gte=debut).count()),
            ("Notes données", Note.objects.filter(created_at__gte=debut).count()),
        ]})
    motifs = (Annulation.objects.filter(created_at__gte=d0).values('par', 'motif').annotate(n=Count('id')).order_by('-n')[:8])
    note = Note.objects.filter(created_at__gte=d0).aggregate(n=Count('id'), s=Sum('note'))
    moyenne = round(note['s'] / note['n'], 1) if note['n'] else None
    return {'series': series, 'periodes': periodes, 'motifs': list(motifs), 'moyenne': moyenne}


def _reglages():
    from django.apps import apps
    liens = [("Promotions", 'redeem', 'courses.PromoCourse', "Réductions payées par Lantante (code ou automatiques)"),
             ("Prix des courses", 'sell', 'courses.Categorie', "Tarif de base, prise en charge, prix au km"),
             ("Véhicules", 'two_wheeler', 'courses.Service', "Moto, Tricycle, Voiture, Cargo : activer ou non"),
             ("Heures et majorations", 'schedule', 'courses.PlageHoraire', "Prix plus élevé la nuit, aux heures de pointe"),
             ("Zones couvertes", 'map', 'courses.Zone', "Où on peut commander"),
             ("Lieux connus", 'location_on', 'api_mobile.LieuConnu', "Lieux proposés en premier dans la recherche"),
             ("Paramètres", 'settings', 'courses.Parametres', "Rayon de recherche, délais, commission, dette maximale"),
             ("Accueil de l'appli", 'apps', 'api_mobile.TuileAccueil', "Tuiles affichées sur l'accueil"),
             ("Codes PIN du solde", 'password', 'courses.PinSolde', "Réinitialiser le code d'un client"),
             ("Offres envoyées", 'send', 'courses.OffreCourse', "Historique technique des offres aux coursiers"),
             ("Coursiers favoris", 'favorite', 'courses.CoursierFavori', "Favoris choisis par les clients")]
    res = []
    for titre, ic, label, aide in liens:
        try:
            m = apps.get_model(label)
        except LookupError:
            continue
        res.append({'titre': titre, 'ic': ic, 'aide': aide,
                    'url': reverse(f'admin:{m._meta.app_label}_{m._meta.model_name}_changelist')})
    return {'liens': res}


@staff_member_required
def tableau(request):
    if not request.user.has_perm('courses.view_course'):
        raise Http404
    from courses.models import Course, MouvementSoldePartenaire, Partenaire
    vue = request.GET.get('vue') or 'jour'
    if vue not in dict((o[0], o) for o in ONGLETS):
        vue = 'jour'
    ctx = dict(_admin.site.each_context(request), title="Gestion des courses", onglets=ONGLETS, vue=vue)
    if vue == 'jour':
        ctx.update(_jour(Course, Partenaire, MouvementSoldePartenaire))
    elif vue == 'coursiers':
        ctx.update(_coursiers(Course, Partenaire, request.GET.get('filtre') or 'tous'))
    elif vue == 'demandes':
        ctx.update(_demandes())
    elif vue == 'stats':
        ctx.update(_stats(Course))
    else:
        ctx.update(_reglages())
    ctx['a_traiter'] = sum(b['n'] for b in (ctx.get('blocs') or _demandes()['blocs']))
    ctx['url_courses'] = _u('course_changelist')
    return render(request, 'admin/courses.html', ctx)


@staff_member_required
def coursier(request, pk):
    if not request.user.has_perm('courses.view_partenaire'):
        raise Http404
    from courses.models import Annulation, Partenaire, Signalement
    p = Partenaire.objects.select_related('user').filter(pk=pk).first()
    if not p:
        raise Http404
    d0 = _debut_jour()
    courses = p.courses.select_related('client', 'partenaire__user', 'categorie').order_by('-created_at')
    periode = request.GET.get('periode') or 'semaine'
    debuts = {'jour': d0, 'semaine': d0 - timedelta(days=6), 'mois': d0.replace(day=1)}
    choisies = courses.filter(created_at__gte=debuts[periode]) if periode in debuts else courses
    lignes = []
    for c in choisies[:200]:
        x = _ligne_course(c)
        cl = c.client
        x.update({'client_nom': cl.get_full_name() or '—', 'client_email': cl.email, 'client_tel': cl.phone or '—',
                  'km': float((c.detail_prix or {}).get('compteur_km') or c.distance_reelle_km or 0) or float(c.distance_km),
                  'client_url': reverse('admin_client', args=[cl.pk])})
        lignes.append(x)
    term = courses.filter(statut='terminee')
    gains = sum((c.prix_final or c.prix_estime) for c in term)
    kpis = [("Courses aujourd'hui", courses.filter(created_at__gte=d0).count(), 'today'),
            ("Courses terminées", term.count(), 'check_circle'),
            ("Annulées par lui", Annulation.objects.filter(partenaire=p, par='partenaire').count(), 'cancel'),
            ("Montant des courses", _f(gains), 'payments'),
            ("Note", f"{p.note} ★ ({p.nb_notes})" if p.nb_notes else '—', 'star'),
            ("Solde", _f(p.solde) if p.solde >= 0 else f"Dette {_f(-p.solde)}", 'account_balance_wallet'),
            ("Offres ignorées", p.offres_ignorees, 'notifications_paused'),
            ("Avertissements", p.avertissements, 'warning')]
    plaintes = Signalement.objects.filter(course__partenaire=p).select_related('course').order_by('-created_at')[:20]
    docs = [{'d': d, 'url': _u('documentpartenaire_change', d.pk)} for d in p.documents.all()]
    mouvements = p.mouvements.order_by('-created_at')[:15]
    vu = timezone.localtime(p.position_le).strftime('%d/%m à %H:%M') if p.position_le else 'jamais'
    from courses.models import MessageSupport
    from courses.services import _notifier
    if request.method == 'POST' and request.user.has_perm('courses.add_messagesupport'):
        texte = (request.POST.get('texte') or '').strip()
        if texte:
            MessageSupport.objects.create(partenaire=p, par='support', auteur=request.user, texte=texte[:2000])
            _notifier(p.user, "Message du support Lantante", texte[:200])
        from django.shortcuts import redirect
        return redirect(reverse('admin_coursier', args=[p.pk]) + '#support')
    support = list(p.messages_support.select_related('auteur').order_by('-created_at')[:30])[::-1]
    p.messages_support.filter(par='coursier', lu_le__isnull=True).update(lu_le=timezone.now())
    ctx = dict(_admin.site.each_context(request), title=_nom(p), p=p, nom=_nom(p), kpis=kpis, vu=vu, support=support,
               courses=lignes, periode=periode,
               periodes=[('jour', "Aujourd'hui"), ('semaine', "7 jours"), ('mois', "Ce mois"), ('tout', "Tout")],
               plaintes=plaintes, docs=docs, mouvements=mouvements,
               cls={'valide': 'ok', 'en_attente': 'or', 'a_completer': 'or'}.get(p.statut, 'ko'),
               modifier=_u('partenaire_change', p.pk))
    return render(request, 'admin/coursier.html', ctx)

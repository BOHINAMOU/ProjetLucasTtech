"""Fiches détaillées dans l'admin (école → filières, vendeur → produits) et cartes des pages de rubrique.

Même principe que la fiche hôtel : vue lecture, « Modifier », « Ajouter » avec le parent pré-choisi,
et retour automatique sur la fiche après enregistrement (RetourMixin).
"""
from urllib.parse import quote

from django.contrib import admin as _admin
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse


def _f(n):
    return f"{int(n):,} CFA".replace(',', ' ') if n else '—'


def _url(o, champ):
    f = getattr(o, champ, None)
    try:
        return f.url if f else ''
    except ValueError:
        return ''


def _objet(request, modele, pk):
    """L'objet, seulement s'il est visible pour cet utilisateur selon son admin (droits + filtrage)."""
    ma = _admin.site._registry.get(modele)
    if ma is None:
        raise Http404
    o = ma.get_queryset(request).filter(pk=pk).first()
    if o is None or not ma.has_view_or_change_permission(request, o):
        raise Http404
    return ma, o


def _lien_retour(nom, pk, ici, extra=''):
    return reverse(nom, args=[pk] if pk is not None else None) + f'?{extra}retour={quote(ici)}'


# ── Pages de rubrique : cartes cliquables vers les fiches ──────────────────────────────
def cartes(request, code):
    if code == 'hotels':
        from Hotels.models import Hotel
        ma = _admin.site._registry.get(Hotel)
        if not ma or not ma.has_view_or_change_permission(request):
            return None
        qs = ma.get_queryset(request).prefetch_related('chambres').order_by('ordre', 'nom')
        return "Hôtels", [{'url': reverse('admin_hotel', args=[h.pk]), 'photo': _url(h, 'photo'), 'titre': h.nom,
                           'ligne': f"{h.ville} · {len(h.chambres.all())} chambre{'s' if len(h.chambres.all()) > 1 else ''}",
                           'badge': '' if h.actif else 'Masqué'} for h in qs]
    if code == 'ecoles':
        from Ecoles.models import Ecole
        ma = _admin.site._registry.get(Ecole)
        if not ma or not ma.has_view_or_change_permission(request):
            return None
        qs = ma.get_queryset(request).prefetch_related('filieres').order_by('ordre', 'nom')
        return "Écoles", [{'url': reverse('admin_fiche', args=['ecoles', e.pk]),
                           'photo': _url(e, 'couverture') or _url(e, 'logo'), 'titre': e.nom,
                           'ligne': f"{e.ville or e.get_type_display()} · {len(e.filieres.all())} filière{'s' if len(e.filieres.all()) > 1 else ''}",
                           'badge': '' if e.publie else 'Masquée'} for e in qs]
    if code == 'vendeurs':
        from Marche.models import Vendeur
        ma = _admin.site._registry.get(Vendeur)
        if not ma or not ma.has_view_or_change_permission(request):
            return None
        qs = ma.get_queryset(request).prefetch_related('produits').order_by('boutique')
        return "Vendeurs", [{'url': reverse('admin_fiche', args=['vendeurs', v.pk]), 'photo': _url(v, 'logo'),
                             'titre': v.boutique,
                             'ligne': f"{v.ville} · {len(v.produits.all())} produit{'s' if len(v.produits.all()) > 1 else ''}",
                             'badge': '' if v.actif else v.get_statut_display()} for v in qs]
    return None


# ── Fiches ─────────────────────────────────────────────────────────────────────────────
def _ecole(request, pk):
    from Ecoles.models import CYCLES, Ecole, Filiere
    ma, e = _objet(request, Ecole, pk)
    ici = reverse('admin_fiche', args=['ecoles', e.pk])
    fa = _admin.site._registry.get(Filiere)
    peut = lambda p: fa is not None and getattr(fa, f'has_{p}_permission')(request)  # noqa: E731
    cycles = dict(CYCLES)
    enfants = [{
        'photo': _url(f, 'image'), 'titre': f.nom, 'prix': _f(f.frais) if f.frais else '',
        'ligne': ' · '.join(x for x in (cycles.get(f.cycle, ''), f.niveau, f.duree) if x),
        'modifier': _lien_retour('admin:Ecoles_filiere_change', f.pk, ici) if peut('change') else '',
        'supprimer': _lien_retour('admin:Ecoles_filiere_delete', f.pk, ici) if peut('delete') else '',
    } for f in e.filieres.all()]
    return {
        'rubrique': ('ecoles', "Écoles"), 'titre': e.nom, 'photo': _url(e, 'couverture') or _url(e, 'logo'),
        'logo': _url(e, 'logo') if _url(e, 'couverture') else '',
        'sous_titre': ' · '.join(x for x in (e.get_type_display(), e.ville, '' if e.publie else 'Masquée') if x),
        'description': e.description,
        'pastilles': [cycles.get(c, c) for c in (e.cycles or [])],
        'kpis': [("Filières", len(enfants)), ("Photos", e.photos.count()), ("Nouveautés", e.nouveautes.count()),
                 ("Responsables", e.membres.count())],
        'actions': [a for a in [
            ("Modifier l'école", _lien_retour('admin:Ecoles_ecole_change', e.pk, ici), 'fa-pen', True)
            if ma.has_change_permission(request, e) else None,
            ("Ajouter une filière", _lien_retour('admin:Ecoles_filiere_add', None, ici, f'ecole={e.pk}&'), 'fa-plus', False)
            if peut('add') else None,
        ] if a],
        'enfants_titre': "Filières", 'enfants': enfants,
        'ajouter': ("Ajouter une filière", _lien_retour('admin:Ecoles_filiere_add', None, ici, f'ecole={e.pk}&'))
        if peut('add') else None,
        'vide': "Aucune filière pour le moment.",
    }


def _vendeur(request, pk):
    from Marche.models import Vendeur
    from Shop.models import Product
    ma, v = _objet(request, Vendeur, pk)
    ici = reverse('admin_fiche', args=['vendeurs', v.pk])
    pa = _admin.site._registry.get(Product)
    peut = lambda p: pa is not None and getattr(pa, f'has_{p}_permission')(request)  # noqa: E731
    produits = list(v.produits.all().order_by('-is_available', 'name'))
    enfants = [{
        'photo': _url(p, 'image'), 'titre': p.name, 'prix': _f(p.price),
        'ligne': f"Stock : {p.stock}" + ('' if p.is_available else ' · Indisponible'),
        'modifier': _lien_retour('admin:Shop_product_change', p.pk, ici) if peut('change') else '',
        'supprimer': _lien_retour('admin:Shop_product_delete', p.pk, ici) if peut('delete') else '',
        'voir': reverse('shop:product_detail', args=[p.pk]),
    } for p in produits]
    kpis = [("Produits", len(produits)), ("Disponibles", sum(1 for p in produits if p.is_available))]
    if request.user.is_superuser and hasattr(ma, 'ventes'):
        kpis += [("Ventes", ma.ventes(v)), ("Dû au vendeur", ma.du_f(v)), ("Reste à reverser", ma.reste_f(v))]
    ajout = _lien_retour('admin:Shop_product_add', None, ici, f'vendeur={v.pk}&')
    return {
        'rubrique': ('vendeurs', "Vendeurs"), 'titre': v.boutique, 'photo': _url(v, 'logo'), 'photo_contenue': True,
        'sous_titre': ' · '.join(x for x in (v.ville, v.etat[1],
                                             f"accès jusqu'au {v.fin_acces:%d/%m/%Y}" if v.fin_acces else "accès sans limite") if x),
        'acces': {'etat': v.etat, 'url': reverse('admin_vendeur_acces', args=[v.pk])} if request.user.is_superuser else None,
        'description': v.description,
        'pastilles': [x for x in (v.adresse_retrait and f"Retrait : {v.adresse_retrait}",
                                  v.whatsapp and f"WhatsApp {v.whatsapp}") if x],
        'kpis': kpis,
        'actions': [a for a in [
            ("Modifier le vendeur", _lien_retour('admin:Marche_vendeur_change', v.pk, ici), 'fa-pen', True)
            if ma.has_change_permission(request, v) else None,
            ("Ajouter un produit", ajout, 'fa-plus', False) if peut('add') else None,
            ("Boutique publique", v.lien_public(), 'fa-store', False) if v.slug else None,
        ] if a],
        'enfants_titre': "Produits", 'enfants': enfants,
        'ajouter': ("Ajouter un produit", ajout) if peut('add') else None,
        'vide': "Aucun produit pour le moment.",
    }


@staff_member_required
def vendeur_acces(request, pk):
    """Suspendre / réactiver un vendeur (super-admin, POST). Rien n'est effacé."""
    from django.contrib import messages
    from django.shortcuts import redirect
    from Marche.acces_vendeur import fin_pour, reactiver, suspendre
    from Marche.models import Vendeur
    if request.method != 'POST' or not request.user.is_superuser:
        raise Http404
    v = Vendeur.objects.filter(pk=pk).first()
    if not v:
        raise Http404
    if request.POST.get('action') == 'suspendre':
        suspendre(v)
        messages.success(request, f"« {v.boutique} » est suspendu. Ses produits sont masqués, rien n'est effacé.")
    else:
        from datetime import date
        duree = request.POST.get('duree', '3')
        libre = None
        if duree == 'date':
            try:
                libre = date.fromisoformat(request.POST.get('date_fin', ''))
            except ValueError:
                messages.error(request, "Date de fin invalide.")
                return redirect('admin_fiche', 'vendeurs', v.pk)
        reactiver(v, fin_pour(duree, libre))
        messages.success(request, f"« {v.boutique} » est actif" + (f" jusqu'au {v.fin_acces:%d/%m/%Y}." if v.fin_acces else " sans limite."))
    return redirect('admin_fiche', 'vendeurs', v.pk)


FICHES = {'ecoles': _ecole, 'vendeurs': _vendeur}


@staff_member_required
def fiche(request, code, pk):
    if code not in FICHES:
        raise Http404
    ctx = FICHES[code](request, pk)
    return render(request, 'admin/fiche.html', dict(_admin.site.each_context(request), title=ctx['titre'], f=ctx))

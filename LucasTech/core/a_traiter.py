"""Page « À traiter » : un seul tableau de tout ce qui attend une action de l'équipe."""
from datetime import timedelta

from django.contrib import admin as _admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

LIMITE = 40


def _url_change(o):
    return reverse(f'admin:{o._meta.app_label}_{o._meta.model_name}_change', args=[o.pk])


def _peut(user, label):
    from django.apps import apps
    try:
        m = apps.get_model(label)
    except LookupError:
        return None
    ma = _admin.site._registry.get(m)
    return m if ma and ma.has_view_or_change_permission(_FauxRequete(user)) else None


class _FauxRequete:
    def __init__(self, user):
        self.user = user


def _sources(user):
    """(type, couleur, modèle, filtre, titre(o), date(o), action) pour chaque source visible par l'utilisateur."""
    t = timezone.localdate()
    s = []

    def ajoute(label, typ, couleur, filtre, titre, date, action, superuser=False):
        if superuser and not user.is_superuser:
            return
        m = _peut(user, label)
        if m:
            s.append((typ, couleur, m, filtre, titre, date, action))

    ajoute('Payments.Payment', "Paiement", 'or', Q(status='pending'),
           lambda o: f"{o.description} · {int(o.amount):,} CFA".replace(',', ' '), lambda o: o.created_at, "Vérifier", True)
    ajoute('Publications.PublicationComment', "Commentaire", 'vert', Q(is_hidden=False, reponse=''),
           lambda o: f"{o.name} : « {o.text[:70]} »", lambda o: o.created_at, "Répondre")
    ajoute('Publications.QuickMessage', "Message", 'vert', Q(is_read=False),
           lambda o: f"{o.name} : « {o.message[:70]} »", lambda o: o.created_at, "Lire")
    ajoute('Shop.ShopOrder', "Commande", 'or', Q(status='pending'),
           lambda o: f"Commande {getattr(o, 'receipt_number', o.pk)}", lambda o: getattr(o, 'date', None) or getattr(o, 'created_at', None), "Livrer")
    ajoute('Shop.Reservation', "Réservation", 'or', Q(status='pending'),
           lambda o: str(o), lambda o: getattr(o, 'created_at', None), "Traiter")
    ajoute('Repetiteurs.Candidature', "Répétiteur", 'bleu', Q(statut='a_verifier'),
           lambda o: f"Dossier {o.numero} · {o.prenom} {getattr(o, 'nom', '')}".strip(), lambda o: getattr(o, 'created_at', None), "Vérifier")
    ajoute('Marche.DemandeVendeur', "Vendeur", 'bleu', Q(statut='en_attente'),
           lambda o: f"Demande : {o.boutique}", lambda o: getattr(o, 'created_at', None), "Examiner")
    ajoute('Marche.ContactVendeur', "Vendeur", 'bleu', Q(statut='nouvelle'),
           lambda o: f"Veut vendre : {o.boutique} ({o.get_categorie_display()}, {o.ville})", lambda o: o.created_at, "Contacter")
    ajoute('Marche.Vendeur', "Accès vendeur", 'rouge',
           Q(statut='expire') | Q(statut='valide', fin_acces__lte=t + timedelta(days=7)),
           lambda o: f"{o.boutique} : {o.etat[1].lower()}" + (f" (fin {o.fin_acces:%d/%m/%Y})" if o.fin_acces else ''),
           lambda o: o.fin_acces, "Prolonger")
    ajoute('Logements.Logement', "Logement", 'bleu', Q(statut='attente'),
           lambda o: f"À valider : {o.nom}, {o.loyer:,} CFA".replace(',', ' '), lambda o: o.propose_le or o.created_at, "Valider")
    ajoute('Logements.DemandeLogement', "Cherche logement", 'vert', Q(statut='nouvelle'),
           lambda o: f"{o.nom} : {o.get_type_display()} à {o.lieu}, {o.budget:,} CFA".replace(',', ' '), lambda o: o.created_at, "Répondre")
    ajoute('Services.ServiceContact', "Contact service", 'vert', Q(is_read=False),
           lambda o: f"{o.name} · {o.service}", lambda o: o.created_at, "Rappeler")
    ajoute('core.MonetizationRequest', "Monétisation", 'or', Q(status='new'),
           lambda o: str(o), lambda o: getattr(o, 'created_at', None), "Traiter")
    ajoute('core.PartnerApplication', "Partenariat", 'bleu', Q(status='pending'),
           lambda o: str(o), lambda o: getattr(o, 'created_at', None), "Examiner")
    ajoute('core.Signalement', "Signalement", 'rouge', Q(statut='nouveau'),
           lambda o: str(o), lambda o: o.created_at, "Examiner")
    ajoute('core.DemandeSuppressionCompte', "Suppression de compte", 'rouge', Q(statut='nouvelle'),
           lambda o: o.email, lambda o: o.created_at, "Traiter")
    ajoute('Portfolio.ContactMessage', "Portfolio", 'vert', Q(is_read=False),
           lambda o: str(o), lambda o: getattr(o, 'created_at', None), "Lire")
    return s


def total(user):
    n = 0
    for _t, _c, m, f, *_ in _sources(user):
        try:
            n += m.objects.filter(f).count()
        except Exception:
            pass
    return n


def lignes(user):
    res = []
    for typ, couleur, m, f, titre, date, action in _sources(user):
        try:
            qs = list(m.objects.filter(f).order_by('-pk')[:LIMITE])
        except Exception:
            continue
        for o in qs:
            url = _url_change(o)
            if m._meta.label == 'Publications.PublicationComment':
                url = reverse('admin_section', args=['commentaires']) + f'?c={o.pk}'
            elif m._meta.label == 'Marche.Vendeur':
                url = reverse('admin_fiche', args=['vendeurs', o.pk])
            try:
                d = date(o)
            except Exception:
                d = None
            res.append({'type': typ, 'couleur': couleur, 'titre': titre(o), 'date': d, 'url': url, 'action': action})
    def cle(r):
        d = r['date']
        if d is None:
            return 0
        if hasattr(d, 'timestamp'):
            return d.timestamp()
        from datetime import datetime
        return datetime(d.year, d.month, d.day).timestamp()
    res.sort(key=cle, reverse=True)
    return res


@staff_member_required
def page(request):
    rows = lignes(request.user)
    types = sorted({r['type'] for r in rows})
    filtre = request.GET.get('type', '')
    if filtre:
        rows = [r for r in rows if r['type'] == filtre]
    return render(request, 'admin/a_traiter.html', dict(_admin.site.each_context(request), title="À traiter",
                                                        lignes=rows, types=types, filtre=filtre))

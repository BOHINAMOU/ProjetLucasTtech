"""Barre latérale de l'administration : rubriques groupées, compteurs (pastilles or) et carte de l'utilisateur."""
from django.core.cache import cache


def _compteurs(user):
    """Nombres affichés à droite des liens (mis en cache 60 s par utilisateur)."""
    cle = f'admin:compteurs:{user.pk}'
    c = cache.get(cle)
    if c is not None:
        return c
    from .dashboard import _count, _vendeurs_bientot, _vendeurs_expires
    c = {
        'commentaires': _count('Publications.PublicationComment', is_hidden=False, reponse='')
                        + _count('Publications.QuickMessage', is_read=False),
        'paiements': _count('Payments.Payment', status='pending') if user.is_superuser else 0,
        'boutique': _count('Shop.ShopOrder', status='pending') + _count('Shop.Reservation', status='pending'),
        'vendeurs': _count('Marche.DemandeVendeur', statut='en_attente') + _count('Marche.ContactVendeur', statut='nouvelle')
                    + _vendeurs_bientot() + _vendeurs_expires(),
        'repetiteurs': _count('Repetiteurs.Candidature', statut='a_verifier'),
        'services': _count('Services.ServiceContact', is_read=False),
        'logements': _count('Logements.Logement', statut='attente') + _count('Logements.DemandeLogement', statut='nouvelle'),
    }
    try:
        from .a_traiter import total
        c['a_traiter'] = total(user)
    except Exception:
        c['a_traiter'] = 0
    cache.set(cle, c, 60)
    return c


def rubriques(request):
    if not request.path.startswith('/lantanteAdminTech/') or not getattr(request, 'user', None) \
            or not request.user.is_authenticated or not request.user.is_staff:
        return {}
    from .rubriques import groupes, rubrique_du_chemin, visibles
    u = request.user
    rubs = visibles(u)
    try:
        nb = _compteurs(u)
    except Exception:
        nb = {}
    for r in rubs:
        r['n'] = nb.get(r['code'], 0)
    nom = (u.get_full_name() or u.email or '').strip()
    initiales = ''.join(m[0] for m in nom.replace('@', ' ').split()[:2]).upper() or 'LT'
    # Prénom seulement (le nom complet ne tient pas dans la barre)
    prenom = (u.first_name or '').split()
    court = prenom[-1] if len(prenom) > 1 and prenom[0].isupper() and len(prenom[0]) > 3 else (prenom[0] if prenom else '')
    court = court or (u.email or '').split('@')[0]
    if u.is_superuser:
        role = "Super-admin"
    elif hasattr(u, 'vendeur'):
        role = "Vendeur"
    else:
        role = "Équipe Lantante"
    return {'lt_rubriques': rubs, 'lt_groupes': groupes(rubs), 'lt_actif': rubrique_du_chemin(request.path),
            'lt_a_traiter': nb.get('a_traiter', 0),
            'lt_moi': {'nom': court.capitalize() if court.isupper() else court, 'complet': nom, 'initiales': initiales, 'role': role}}

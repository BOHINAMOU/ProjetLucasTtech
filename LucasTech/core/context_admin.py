"""Barre latérale de l'administration : uniquement les grands titres (rubriques) visibles par l'utilisateur."""


def rubriques(request):
    if not request.path.startswith('/lantanteAdminTech/') or not getattr(request, 'user', None) \
            or not request.user.is_authenticated or not request.user.is_staff:
        return {}
    from .rubriques import groupes, rubrique_du_chemin, visibles
    rubs = visibles(request.user)
    return {'lt_rubriques': rubs, 'lt_groupes': groupes(rubs), 'lt_actif': rubrique_du_chemin(request.path)}

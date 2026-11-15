def abonnement(request):
    """Prix de l'abonnement et fin d'accès (affichés sur les pages concours)."""
    from .annuel import fin_acces
    from .models import ReglageAcces
    try:
        return {'abo_prix': ReglageAcces.load().prix, 'abo_fin': fin_acces(getattr(request, 'user', None))}
    except Exception:  # base pas prête (migrations)
        return {}

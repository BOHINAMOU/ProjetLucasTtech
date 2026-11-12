"""Outils communs de l'API mobile : URL absolues, erreurs, droits (y compris hors connexion), sérialisation."""
from django.db.models import Max, Q
from django.utils import timezone
from rest_framework.response import Response

from abonnements.access import accessible_contest_ids, active_subscriptions, has_unlimited

# Formules qui autorisent la lecture hors connexion dans l'application.
OFFLINE_PLAN_CODES = ('premium', 'ultimate')
LOCAL_HOSTS = ('localhost', '127.0.0.1', '10.0.2.2', 'testserver')


# ─────────────────────────────
# Réponses et URL
# ─────────────────────────────
def error(detail, status=400, code=None, errors=None):
    body = {'detail': detail}
    if code:
        body['code'] = code
    if errors:
        body['errors'] = errors
    return Response(body, status=status)


def absolute(request, path):
    """URL absolue en https (sauf serveur de développement local)."""
    if not path:
        return None
    url = request.build_absolute_uri(path)
    host = request.get_host().split(':')[0]
    if url.startswith('http://') and host not in LOCAL_HOSTS:
        url = 'https://' + url[len('http://'):]
    return url


def media(request, field):
    try:
        return absolute(request, field.url) if field else None
    except ValueError:
        return None


def dt(value):
    return timezone.localtime(value).isoformat() if value else None


def money(value):
    if value is None:
        return None
    return int(value)


# ─────────────────────────────
# Droits
# ─────────────────────────────
class Rights:
    """Droits d'un utilisateur calculés une fois par requête (évite une requête SQL par concours)."""

    def __init__(self, user, now=None):
        self.now = now or timezone.now()
        self.user = user
        self.auth = bool(user and user.is_authenticated)
        self.staff = self.auth and user.is_staff
        self.unlimited = self.auth and has_unlimited(user, self.now)
        self.ids = accessible_contest_ids(user, self.now) if self.auth else set()
        self._offline = None

    def can_access(self, contest):
        return self.staff or self.unlimited or contest.pk in self.ids

    def can_view(self, paper, contest=None):
        return paper.is_free or self.can_access(contest or paper.session.contest)

    def offline_until(self, contest):
        """Date de fin du droit hors connexion (Premium / Ultimate couvrant le concours), sinon None."""
        if not self.auth:
            return None
        if self._offline is None:
            subs = active_subscriptions(self.user, self.now).filter(
                Q(plan__code__in=OFFLINE_PLAN_CODES) | Q(is_unlimited=True))
            unlimited_end = subs.filter(is_unlimited=True).aggregate(m=Max('end_at'))['m']
            per_contest = {}
            for sub in subs.filter(is_unlimited=False).prefetch_related('contests'):
                for link in sub.contests.all():
                    cur = per_contest.get(link.contest_id)
                    per_contest[link.contest_id] = max(cur, sub.end_at) if cur else sub.end_at
            self._offline = (unlimited_end, per_contest)
        unlimited_end, per_contest = self._offline
        dates = [d for d in (unlimited_end, per_contest.get(contest.pk)) if d]
        return max(dates) if dates else None

    def offline_allowed(self, paper, contest=None):
        contest = contest or paper.session.contest
        if paper.is_free or self.staff:
            return True
        return self.offline_until(contest) is not None


# ─────────────────────────────
# Sérialisation
# ─────────────────────────────
def user_payload(request, user):
    return {
        'id': user.pk, 'first_name': user.first_name, 'last_name': user.last_name, 'email': user.email,
        'phone': user.phone or '', 'country': user.country or '', 'photo': media(request, user.avatar),
        'date_joined': dt(user.date_joined),
    }


def contest_payload(request, c, rights):
    return {
        'id': c.pk, 'slug': c.slug, 'sigle': c.acronym, 'nom': c.name,
        'categorie': {'id': c.category_id, 'nom': c.category.name, 'slug': c.category.slug},
        'photo': media(request, c.logo), 'couverture': media(request, c.cover),
        'nb_annees': getattr(c, 'n_sessions', 0), 'nb_epreuves': getattr(c, 'n_papers', 0),
        'est_demo': bool(getattr(c, 'is_demo', False)), 'accessible': rights.can_access(c),
    }


def event_payload(request, e):
    return {'id': e.pk, 'titre': e.title, 'date': dt(e.starts_at), 'lieu': e.location,
            'image': media(request, e.cover), 'prix_min': e.min_price,
            'url_site': absolute(request, e.get_absolute_url())}


def formation_payload(request, f):
    return {'id': f.pk, 'titre': f.title, 'prix': money(f.price), 'image': media(request, f.image),
            'url_site': absolute(request, f.get_absolute_url())}


def product_payload(request, p):
    from django.urls import reverse
    return {'id': p.pk, 'titre': p.name, 'prix': money(p.price), 'image': media(request, p.image),
            'url_site': absolute(request, reverse('shop:product_detail', args=[p.pk]))}

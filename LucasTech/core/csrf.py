"""Échec de la vérification CSRF : au lieu de la page jaune « Interdit (403) » de Django, on renvoie la personne
vers la page d'où elle vient (même site uniquement), ou vers la connexion, avec un message clair.
Cas typique : page restaurée par « Précédent » (surtout Safari sur iPhone) ou ouverte avant une connexion /
déconnexion, dont le jeton n'est plus valable."""
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit



def csrf_failure(request, reason=""):
    target = request.META.get('HTTP_REFERER') or ''
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        target = reverse('users:login')
    # Le message est affiché par core/base.html grâce au paramètre ?session=expiree (pas de doublon avec
    # les pages qui affichent déjà les messages Django).
    parts = urlsplit(target)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != 'session']
    query.append(('session', 'expiree'))
    resp = redirect(urlunsplit(parts._replace(query=urlencode(query))))
    resp['Cache-Control'] = 'no-store'
    return resp

"""Page de connexion de l'administration, avec la vérification en deux étapes (code par e-mail)."""
from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import get_user_model, login as auth_login
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from . import deux_facteurs as df

SESSION_UID, SESSION_SUITE = 'lt_2fa_uid', 'lt_2fa_suite'


def _suite(request, valeur):
    if valeur and url_has_allowed_host_and_scheme(valeur, {request.get_host()}, require_https=request.is_secure()):
        return valeur
    return '/lantanteAdminTech/'


@never_cache
@csrf_protect
def connexion(request, extra_context=None):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect(_suite(request, request.GET.get('next')))
    form = AdminAuthenticationForm(request, data=request.POST or None)
    suite = _suite(request, request.POST.get('next') or request.GET.get('next'))
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        if not df.requise(user) or df.appareil_connu(request, user):
            auth_login(request, user)
            return redirect(suite)
        request.session[SESSION_UID] = user.pk
        request.session[SESSION_SUITE] = suite
        try:
            df.envoyer_code(user)
        except Exception:  # e-mail indisponible : on le dit, sans ouvrir l'accès
            return render(request, 'admin/login.html', dict(admin.site.each_context(request), form=form, next=suite,
                          erreur="Impossible d'envoyer le code par e-mail pour le moment. Réessayez."))
        return redirect('admin_verification')
    return render(request, 'admin/login.html', dict(admin.site.each_context(request), form=form, next=suite))


def _masque(email):
    nom, _, dom = email.partition('@')
    return (nom[:2] + '•' * max(1, len(nom) - 2) + '@' + dom) if dom else email


@never_cache
@csrf_protect
def verification(request):
    uid = request.session.get(SESSION_UID)
    user = get_user_model().objects.filter(pk=uid, is_active=True, is_staff=True).first() if uid else None
    if not user:
        return redirect('admin:login')
    ctx = dict(admin.site.each_context(request), email=_masque(user.email), erreur='', info='')
    if request.method == 'POST':
        if 'renvoyer' in request.POST:
            ctx['info'] = "Nouveau code envoyé." if df.envoyer_code(user) else "Trop de demandes. Patientez quelques minutes."
        else:
            ok, msg = df.verifier(user, request.POST.get('code'))
            if ok:
                suite = request.session.pop(SESSION_SUITE, '/lantanteAdminTech/')
                request.session.pop(SESSION_UID, None)
                auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                r = redirect(suite)
                if request.POST.get('retenir'):
                    df.retenir_appareil(r, user)
                return r
            ctx['erreur'] = msg
    return render(request, 'admin/verification.html', ctx)

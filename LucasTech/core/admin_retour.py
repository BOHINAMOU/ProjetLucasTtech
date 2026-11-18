"""Retour automatique vers une page de l'admin (?retour=/lantanteAdminTech/...) après enregistrement ou suppression."""
from django.http import HttpResponseRedirect

PREFIXE = '/lantanteAdminTech/'


def retour_sur(request):
    r = request.GET.get('retour') or request.POST.get('retour') or ''
    return r if r.startswith(PREFIXE) and '//' not in r and chr(92) not in r else ''


class RetourMixin:
    def retour_defaut(self, obj):
        """Page où revenir sans ?retour= (None : comportement normal de l'admin)."""
        return None

    def _retour(self, request, defaut, obj=None):
        r = retour_sur(request) or (obj is not None and self.retour_defaut(obj)) or ''
        if r and not any(k in request.POST for k in ('_continue', '_addanother', '_saveasnew')):
            return HttpResponseRedirect(r)
        return defaut

    def response_add(self, request, obj, post_url_continue=None):
        return self._retour(request, super().response_add(request, obj, post_url_continue), obj)

    def response_change(self, request, obj):
        return self._retour(request, super().response_change(request, obj), obj)

    def response_delete(self, request, obj_display, obj_id):
        return self._retour(request, super().response_delete(request, obj_display, obj_id))

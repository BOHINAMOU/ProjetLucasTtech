"""Document joint à une inscription : visible seulement par l'équipe de l'école (et les super-admins)."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404

from .admin import mes_ecoles
from .models import InscriptionEcole


@staff_member_required
def document(request, pk):
    i = InscriptionEcole.objects.filter(pk=pk, ecole__in=mes_ecoles(request.user)).first()
    if not i or not i.document:
        raise Http404
    return FileResponse(i.document.open('rb'), as_attachment=False, filename=i.document.name.rsplit('/', 1)[-1])

"""Site : liste et détail des offres (sans formulaire : « Postuler dans l'appli » + contacts). CV : équipe seulement."""
import mimetypes

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from .api import actives
from .models import CandidatureEmploi, OffreEmploi


def liste(request):
    return render(request, 'offres/liste.html', {'offres': actives()})


def detail(request, pk):
    o = get_object_or_404(actives(), pk=pk)
    from django.db.models import F
    OffreEmploi.objects.filter(pk=pk).update(vues=F('vues') + 1)
    wa = ''.join(c for c in o.whatsapp if c.isdigit())
    return render(request, 'offres/detail.html', {'o': o, 'wa': wa})


@login_required
def cv(request, pk):
    if not (request.user.is_staff and request.user.has_perm('Offres.view_candidatureemploi')):
        raise Http404
    c = get_object_or_404(CandidatureEmploi, pk=pk)
    if not c.cv:
        raise Http404
    rep = FileResponse(c.cv.open('rb'), content_type=mimetypes.guess_type(c.cv.name)[0] or 'application/octet-stream')
    rep['Content-Disposition'] = 'inline'
    rep['Cache-Control'] = 'private, no-store'
    rep['X-Content-Type-Options'] = 'nosniff'
    return rep

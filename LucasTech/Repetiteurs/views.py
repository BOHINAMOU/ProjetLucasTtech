"""Site : « Devenir répétiteur » (formulaire + paiement), « Ma candidature », pièce d'identité réservée à l'équipe."""
import mimetypes

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import candidatures
from .forms import CandidatureForm
from .models import Candidature, ReglageCandidature


def _derniere(user):
    return Candidature.objects.filter(user=user).exclude(statut='rejetee').first()


@login_required
def devenir(request):
    c = _derniere(request.user)
    if c and not c.modifiable:
        return redirect('repetiteurs:ma_candidature')
    initial = {} if c else {'prenom': request.user.first_name, 'nom': request.user.last_name,
                            'email': request.user.email}
    form = CandidatureForm(request.POST or None, request.FILES or None, instance=c, initial=initial)
    if request.method == 'POST' and form.is_valid():
        c = form.save(commit=False)
        c.user = request.user
        nouveau = not c.pk
        c.save()
        if nouveau:
            candidatures._trace(c, "Dossier déposé", request.user)
        if c.statut == 'a_corriger':
            candidatures.renvoyer(c)
            return redirect('repetiteurs:ma_candidature')
        return redirect(reverse('payments:checkout', args=['candidature', c.pk]))
    return render(request, 'repetiteurs/devenir.html', {
        'form': form, 'c': c, 'prix': ReglageCandidature.load().prix})


@login_required
def ma_candidature(request):
    c = Candidature.objects.filter(user=request.user).first()
    if not c:
        return redirect('repetiteurs:devenir')
    return render(request, 'repetiteurs/ma_candidature.html', {'c': c, 'prix': ReglageCandidature.load().prix})


@login_required
def piece(request, pk, cote):
    """Pièce d'identité : seulement l'équipe autorisée (jamais publique, jamais dans l'API)."""
    if not (request.user.is_staff and request.user.has_perm('Repetiteurs.view_candidature')):
        raise Http404
    c = get_object_or_404(Candidature, pk=pk)
    f = c.piece_recto if cote == 'recto' else c.piece_verso
    if not f:
        raise Http404
    rep = FileResponse(f.open('rb'), content_type=mimetypes.guess_type(f.name)[0] or 'application/octet-stream')
    rep['Content-Disposition'] = 'inline'
    rep['Cache-Control'] = 'private, no-store'
    rep['X-Content-Type-Options'] = 'nosniff'
    return rep

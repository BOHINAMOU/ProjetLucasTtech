"""Site : « Devenir répétiteur » (sans compte : numéro de dossier + lien privé de suivi), suivi, « Retrouver mon
dossier », pièce d'identité réservée à l'équipe."""
import mimetypes

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import candidatures
from .forms import CandidatureForm, RetrouverForm
from .models import Candidature, ReglageCandidature

LIMITE = 5  # dossiers par adresse IP et par heure (anti-spam)


def _ip(request):
    return (request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR') or '').split(',')[0].strip()


def _trop(request, cle, limite):
    k = f'cand:{cle}:{_ip(request)}'
    n = cache.get(k, 0)
    if n >= limite:
        return True
    cache.set(k, n + 1, 3600)
    return False


def _memoriser(request, c):
    """Ce navigateur peut payer ce dossier (sans compte)."""
    l = [x for x in request.session.get('candidatures', []) if x != c.pk][-9:] + [c.pk]
    request.session['candidatures'] = l


def devenir(request, jeton=None):
    if jeton:
        c = get_object_or_404(Candidature, jeton=jeton)
        if not c.modifiable:
            return redirect(c)
    elif request.user.is_authenticated:
        c = Candidature.objects.filter(user=request.user).exclude(statut='rejetee').first()
        if c and not c.modifiable:
            return redirect(c)
    else:
        c = None
    initial = {}
    if not c and request.user.is_authenticated:
        initial = {'prenom': request.user.first_name, 'nom': request.user.last_name, 'email': request.user.email}
    form = CandidatureForm(request.POST or None, request.FILES or None, instance=c, initial=initial)
    if request.method == 'POST':
        if not c and _trop(request, 'depot', LIMITE):
            form.add_error(None, "Trop de dossiers envoyés. Réessayez dans une heure.")
        elif form.is_valid():
            c = form.save(commit=False)
            nouveau = not c.pk
            if nouveau and request.user.is_authenticated:
                c.user = request.user
            c.save()
            _memoriser(request, c)
            if nouveau:
                candidatures._trace(c, "Dossier déposé", c.nom_complet)
                candidatures._ecrire(c, f"Dossier {c.numero} enregistré",
                                     "Votre dossier de répétiteur est enregistré. Gardez ce lien : "
                                     "il permet de suivre votre dossier, de le corriger et de payer.")
            if c.statut == 'a_corriger':
                candidatures.renvoyer(c)
                return redirect(c)
            return redirect(reverse('payments:checkout', args=['candidature', c.pk]))
    return render(request, 'repetiteurs/devenir.html', {
        'form': form, 'c': c, 'prix': ReglageCandidature.load().prix})


def suivi(request, jeton):
    """Page privée du dossier : seul le bon lien l'ouvre (jeton long, non devinable)."""
    c = get_object_or_404(Candidature, jeton=jeton)
    if c.statut == 'a_payer':
        _memoriser(request, c)
    return render(request, 'repetiteurs/ma_candidature.html', {
        'c': c, 'prix': ReglageCandidature.load().prix, 'lien': request.build_absolute_uri(c.get_absolute_url())})


@login_required
def ma_candidature(request):
    c = Candidature.objects.filter(user=request.user).first()
    return redirect(c) if c else redirect('repetiteurs:devenir')


def retrouver(request):
    """Numéro de dossier + téléphone ou e-mail : le lien est renvoyé par e-mail, ou affiché si le téléphone correspond."""
    form = RetrouverForm(request.POST or None)
    message, lien = '', ''
    if request.method == 'POST' and form.is_valid():
        if _trop(request, 'retrouver', 10):
            message = "Trop d'essais. Réessayez dans une heure."
        else:
            num = form.cleaned_data['numero'].strip().upper().lstrip('R').lstrip('0')
            contact = form.cleaned_data['contact'].strip().lower()
            c = Candidature.objects.filter(pk=int(num)).first() if num.isdigit() else None
            chiffres = ''.join(x for x in contact if x.isdigit())
            if c and '@' in contact and contact == (c.email or '').lower():
                candidatures._ecrire(c, f"Votre dossier {c.numero}", "Voici le lien de suivi de votre dossier.")
                message = "Le lien de votre dossier vient d'être envoyé à cette adresse e-mail."
            elif c and len(chiffres) >= 8 and chiffres[-8:] in ''.join(x for x in c.telephone + c.whatsapp if x.isdigit()):
                lien = c.get_absolute_url()
            else:
                message = "Aucun dossier ne correspond à ces informations."
    return render(request, 'repetiteurs/retrouver.html', {'form': form, 'message': message, 'lien': lien})


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

"""Signalement de contenu et suppression de compte (exigences Google Play), sur le site et dans l'appli."""
from django import forms
from django.core.cache import cache
from django.shortcuts import redirect, render

from .ip import ip_client
from .models import DemandeSuppressionCompte, Signalement

LIMITE = 10  # par heure et par adresse IP


def _trop(request, cle):
    k = f'{cle}:{ip_client(request)}'
    n = cache.get(k, 0)
    if n >= LIMITE:
        return True
    cache.set(k, n + 1, 3600)
    return False


def _prevenir(texte, url):
    try:
        from .alertes import prevenir_equipe
        prevenir_equipe(texte, url)
    except Exception:
        pass


def creer_signalement(request, data):
    """Crée un signalement à partir d'un dictionnaire (formulaire du site ou API). Renvoie (objet, erreur)."""
    typ, motif = (data.get('type') or '').strip(), (data.get('motif') or '').strip()
    if typ not in dict(Signalement.TYPES) or motif not in dict(Signalement.MOTIFS):
        return None, "Choisissez un motif."
    if (data.get('site_internet') or '').strip():
        return None, "Envoi refusé."
    if _trop(request, 'signaler'):
        return None, "Trop de signalements. Réessayez plus tard."
    oid = str(data.get('objet_id') or '')
    u = request.user if getattr(request.user, 'is_authenticated', False) else None
    s = Signalement.objects.create(type=typ, motif=motif, objet_id=int(oid) if oid.isdigit() else None,
                                   titre=(data.get('titre') or '')[:200], url=(data.get('url') or '')[:300],
                                   details=(data.get('details') or '')[:2000], user=u,
                                   email=(u.email if u else (data.get('email') or ''))[:254])
    _prevenir(f"Signalement : {s}", f"/lantanteAdminTech/core/signalement/{s.pk}/change/")
    return s, ''


def signaler(request):
    """Formulaire du site (POST depuis un bouton « Signaler »), retour à la page d'origine."""
    from django.contrib import messages
    retour = request.POST.get('url') or '/'
    if not retour.startswith('/'):
        retour = '/'
    if request.method == 'POST':
        s, err = creer_signalement(request, request.POST)
        if s:
            messages.success(request, "Merci, votre signalement a été envoyé à l'équipe.")
        else:
            messages.error(request, err)
    return redirect(retour)


class SuppressionForm(forms.Form):
    email = forms.EmailField(label="E-mail du compte", error_messages={'required': "Indiquez l'e-mail du compte.", 'invalid': "E-mail invalide."})
    motif = forms.CharField(label="Motif (facultatif)", required=False, widget=forms.Textarea(attrs={'rows': 3}))
    site_internet = forms.CharField(required=False)


def demander_suppression(user, email, motif='', origine='site'):
    d = DemandeSuppressionCompte.objects.filter(email__iexact=email, statut='nouvelle').first()
    if d:
        return d
    d = DemandeSuppressionCompte.objects.create(user=user, email=email, motif=motif[:2000], origine=origine)
    _prevenir(f"Demande de suppression de compte : {email} ({origine})",
              f"/lantanteAdminTech/core/demandesuppressioncompte/{d.pk}/change/")
    return d


def suppression_compte(request):
    """Page publique : comment supprimer son compte Lantante (obligatoire pour Google Play)."""
    envoye = False
    u = request.user if request.user.is_authenticated else None
    form = SuppressionForm(request.POST or None, initial={'email': u.email if u else ''})
    if request.method == 'POST':
        if _trop(request, 'suppression'):
            form.add_error(None, "Trop de demandes. Réessayez plus tard.")
        elif form.is_valid() and not form.cleaned_data.get('site_internet'):
            email = u.email if u else form.cleaned_data['email']
            demander_suppression(u, email, form.cleaned_data.get('motif') or '')
            envoye = True
    return render(request, 'core/suppression_compte.html', {'form': form, 'envoye': envoye})

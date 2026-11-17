"""Site : « Vendre sur Lantante » (sans compte, lien privé de suivi), pièce d'identité réservée à l'équipe."""
import mimetypes

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from Repetiteurs.forms import EXT_PIECE, _verifier
from Repetiteurs.models import whatsapp_togo

from .demandes import ecrire
from .models import DemandeVendeur


class DemandeForm(forms.ModelForm):
    site_internet = forms.CharField(required=False, widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}))

    class Meta:
        model = DemandeVendeur
        fields = ['boutique', 'activite', 'ville', 'prenom', 'nom', 'telephone', 'whatsapp', 'email',
                  'piece_type', 'piece_numero', 'piece']
        widgets = {
            'telephone': forms.TextInput(attrs={'type': 'tel', 'inputmode': 'tel', 'placeholder': '90 12 34 56'}),
            'whatsapp': forms.TextInput(attrs={'type': 'tel', 'inputmode': 'tel', 'placeholder': '+228 90 12 34 56'}),
            'activite': forms.TextInput(attrs={'placeholder': 'Ex. vêtements, téléphones, cosmétiques'}),
            'piece': forms.FileInput(attrs={'accept': 'image/*,application/pdf'}),
        }

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        for nom, f in self.fields.items():
            if f.required and not (self.instance.pk and nom == 'piece'):
                f.widget.attrs['required'] = 'required'

    def clean_site_internet(self):
        if self.cleaned_data.get('site_internet'):
            raise forms.ValidationError("Envoi refusé.")
        return ''

    def clean_whatsapp(self):
        return whatsapp_togo(self.cleaned_data.get('whatsapp'))

    def clean_telephone(self):
        t = self.cleaned_data.get('telephone') or ''
        if len(''.join(c for c in t if c.isdigit())) < 8 or any(c not in '0123456789+ ' for c in t):
            raise forms.ValidationError("Numéro invalide : chiffres uniquement.")
        return t.strip()

    def clean_piece(self):
        return _verifier(self.cleaned_data.get('piece'), EXT_PIECE, "Pièce d'identité")


def _ip(request):
    return (request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR') or '').split(',')[0].strip()


def vendre(request, jeton=None):
    d = get_object_or_404(DemandeVendeur, jeton=jeton) if jeton else None
    if d and not d.modifiable:
        return redirect(d)
    form = DemandeForm(request.POST or None, request.FILES or None, instance=d)
    if request.method == 'POST':
        cle = f'vendre:{_ip(request)}'
        if not d and cache.get(cle, 0) >= 5:
            form.add_error(None, "Trop de demandes envoyées. Réessayez dans une heure.")
        elif form.is_valid():
            nouveau = not form.instance.pk
            d = form.save(commit=False)
            if d.statut == 'a_corriger':
                d.statut = 'en_attente'
            d.save()
            if nouveau:
                cache.set(cle, cache.get(cle, 0) + 1, 3600)
                ecrire(d, f"Demande {d.numero} reçue", "Nous avons bien reçu votre demande. Nous la vérifions et "
                                                     "revenons vers vous rapidement.")
            return redirect(d)
    return render(request, 'marche/vendre.html', {'form': form, 'd': d})


def suivi(request, jeton):
    d = get_object_or_404(DemandeVendeur, jeton=jeton)
    return render(request, 'marche/vendre_suivi.html', {'d': d, 'lien': request.build_absolute_uri(d.get_absolute_url())})


@login_required
def piece(request, pk):
    if not (request.user.is_staff and request.user.has_perm('Marche.view_demandevendeur')):
        raise Http404
    d = get_object_or_404(DemandeVendeur, pk=pk)
    if not d.piece:
        raise Http404
    rep = FileResponse(d.piece.open('rb'), content_type=mimetypes.guess_type(d.piece.name)[0] or 'application/octet-stream')
    rep['Content-Disposition'] = 'inline'
    rep['Cache-Control'] = 'private, no-store'
    rep['X-Content-Type-Options'] = 'nosniff'
    return rep

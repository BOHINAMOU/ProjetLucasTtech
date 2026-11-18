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
    return __import__('core.ip', fromlist=['ip_client']).ip_client(request)


MAX_PIECE = 5 * 1024 * 1024
SIGNATURES = ((b'%PDF', '.pdf'), (b'\xff\xd8\xff', '.jpg'), (b'\x89PNG\r\n\x1a\n', '.png'))


def verifier_piece(f):
    """Taille, extension et type RÉEL du fichier (signature), pas seulement le nom."""
    if not f:
        raise forms.ValidationError("Ajoutez votre pièce d'identité.")
    if f.size > MAX_PIECE:
        raise forms.ValidationError("Fichier trop lourd : 5 Mo maximum.")
    tete = f.read(16)
    f.seek(0)
    for sig, ext in SIGNATURES:
        if tete.startswith(sig):
            nom = f.name.lower()
            if ext == '.jpg' and not nom.endswith(('.jpg', '.jpeg')) or ext != '.jpg' and not nom.endswith(ext):
                f.name = f"piece{ext}"
            return f
    raise forms.ValidationError("Format accepté : JPG, PNG ou PDF.")


class ContactForm(forms.ModelForm):
    site_internet = forms.CharField(required=False, widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}))
    accord = forms.BooleanField(required=True, error_messages={'required': "Cochez la case pour continuer."})

    class Meta:
        from .models import ContactVendeur
        model = ContactVendeur
        fields = ['nom', 'prenom', 'email', 'telephone', 'ville', 'boutique', 'message', 'piece_type', 'piece']
        labels = {'telephone': "Téléphone / WhatsApp", 'message': "Petit message (facultatif)", 'boutique': "Nom de la boutique"}
        widgets = {
            'nom': forms.TextInput(attrs={'autocomplete': 'family-name'}),
            'prenom': forms.TextInput(attrs={'autocomplete': 'given-name'}),
            'boutique': forms.TextInput(attrs={'placeholder': 'Ex. Mode Ama', 'autocomplete': 'organization'}),
            'telephone': forms.TextInput(attrs={'type': 'tel', 'inputmode': 'tel', 'placeholder': '90 12 34 56', 'autocomplete': 'tel-national'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email', 'placeholder': 'vous@exemple.com'}),
            'ville': forms.TextInput(attrs={'placeholder': 'Lomé'}),
            'message': forms.Textarea(attrs={'rows': 3}),
            'piece': forms.FileInput(attrs={'accept': 'image/jpeg,image/png,application/pdf'}),
        }
        error_messages = {
            'nom': {'required': "Indiquez votre nom."}, 'prenom': {'required': "Indiquez votre prénom."},
            'boutique': {'required': "Indiquez le nom de votre boutique."},
            'email': {'required': "Indiquez votre e-mail.", 'invalid': "E-mail invalide."},
            'ville': {'required': "Indiquez votre ville."}, 'telephone': {'required': "Indiquez votre numéro."},
            'piece_type': {'required': "Choisissez le type de pièce."},
        }

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields['prenom'].required = True
        self.fields['piece_type'].required = True
        self.fields['piece'].required = True
        self.fields['piece_type'].choices = [('', "Type de pièce…")] + list(self.fields['piece_type'].choices)[1:]
        for f in self.fields.values():
            if f.required:
                f.widget.attrs['required'] = 'required'

    def clean_site_internet(self):
        if self.cleaned_data.get('site_internet'):
            raise forms.ValidationError("Envoi refusé.")
        return ''

    def clean_telephone(self):
        try:
            return whatsapp_togo(self.cleaned_data.get('telephone'))
        except Exception:
            raise forms.ValidationError("Numéro invalide : 8 chiffres (ex. 90 12 34 56).")

    def clean_piece(self):
        return verifier_piece(self.cleaned_data.get('piece'))

    def save(self, commit=True):
        c = super().save(commit=False)
        c.consentement = bool(self.cleaned_data.get('accord'))
        if commit:
            c.save()
        return c


def _wa_lantante():
    from api_mobile.catalog import _wa_valide, _whatsapp_lantante
    from urllib.parse import quote
    wa = _wa_valide(_whatsapp_lantante())
    return f"https://wa.me/{wa}?text={quote('Bonjour, je veux vendre sur Lantante')}" if wa else ''


def _prevenir(c):
    """E-mail aux super-admins + confirmation au vendeur (ne bloque jamais l'envoi du formulaire)."""
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail
    from django.urls import reverse
    site = (getattr(settings, 'SITE_URL', '') or 'https://lantantetechnologie.com').rstrip('/')
    admins = list(get_user_model().objects.filter(is_superuser=True, is_active=True).exclude(email='')
                  .values_list('email', flat=True))
    try:
        if admins:
            send_mail(f"Nouvelle demande vendeur : {c.boutique}",
                      f"{c.nom_complet} veut vendre sur Lantante.\n\nBoutique : {c.boutique}\n"
                      f"Ville : {c.ville}\nTéléphone : +{c.telephone}\nE-mail : {c.email}\n"
                      "Pièce d'identité : jointe dans l'admin.\n"
                      + (f"Message : {c.message}\n" if c.message else '')
                      + f"\nOuvrir : {site}{reverse('admin:Marche_contactvendeur_change', args=[c.pk])}",
                      settings.DEFAULT_FROM_EMAIL, admins, fail_silently=True)
        send_mail("Demande reçue — Lantante",
                  f"Bonjour {c.prenom or c.nom},\n\nNous avons bien reçu votre demande pour vendre « {c.boutique} » sur Lantante.\n\n"
                  "Nous vous contactons très vite sur WhatsApp ou par téléphone.\n\nL'équipe Lantante",
                  settings.DEFAULT_FROM_EMAIL, [c.email], fail_silently=True)
    except Exception:
        pass


def contact(request):
    """Vendre sur Lantante : WhatsApp OU court formulaire (enregistré dans l'admin)."""
    form = ContactForm(request.POST or None, request.FILES or None)
    envoye = request.GET.get('envoye') == '1'
    if request.method == 'POST':
        cle = f'vendre-contact:{_ip(request)}'
        if cache.get(cle, 0) >= 5:
            form.add_error(None, "Trop de demandes envoyées. Réessayez dans une heure.")
        elif form.is_valid():
            c = form.save()
            cache.set(cle, cache.get(cle, 0) + 1, 3600)
            _prevenir(c)
            return redirect('/vendre/?envoye=1#formulaire')
    return render(request, 'marche/vendre_contact.html', {'lien': _wa_lantante(), 'form': form, 'envoye': envoye})


def vendre(request, jeton=None):
    if not jeton:
        return contact(request)
    d = get_object_or_404(DemandeVendeur, jeton=jeton)
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


@login_required
def piece_contact(request, pk):
    """Pièce d'identité d'une demande de contact vendeur : équipe autorisée seulement, jamais publique."""
    from .models import ContactVendeur
    if not (request.user.is_staff and request.user.has_perm('Marche.view_contactvendeur')):
        raise Http404
    c = get_object_or_404(ContactVendeur, pk=pk)
    if not c.piece:
        raise Http404
    rep = FileResponse(c.piece.open('rb'), content_type=mimetypes.guess_type(c.piece.name)[0] or 'application/octet-stream')
    rep['Content-Disposition'] = 'inline'
    rep['Cache-Control'] = 'private, no-store'
    rep['X-Content-Type-Options'] = 'nosniff'
    rep['X-Frame-Options'] = 'SAMEORIGIN'
    return rep

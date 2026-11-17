from django import forms

from .models import Candidature

MAX = 5 * 1024 * 1024
EXT_PIECE = ('.pdf', '.jpg', '.jpeg', '.png', '.webp')


def _verifier(f, extensions, nom):
    if not f or not hasattr(f, 'size'):
        return f
    if f.size > MAX:
        raise forms.ValidationError(f"{nom} : 5 Mo maximum.")
    if not f.name.lower().endswith(extensions):
        raise forms.ValidationError(f"{nom} : format accepté : PDF, JPG, PNG ou WEBP.")
    return f


class CandidatureForm(forms.ModelForm):
    class Meta:
        model = Candidature
        fields = ['prenom', 'nom', 'telephone', 'whatsapp', 'email',
                  'photo', 'matieres', 'niveaux', 'ville', 'quartier', 'latitude', 'longitude',
                  'experience', 'description', 'tarif',
                  'piece_type', 'piece_numero', 'piece_recto', 'piece_verso']
        widgets = {
            'latitude': forms.HiddenInput(), 'longitude': forms.HiddenInput(),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': "Votre méthode, vos réussites…"}),
            'matieres': forms.TextInput(attrs={'placeholder': "Ex. Mathématiques, Physique-Chimie"}),
            'niveaux': forms.TextInput(attrs={'placeholder': "Ex. 3e, 1re, Tle"}),
            'experience': forms.TextInput(attrs={'placeholder': "Ex. 6 ans, professeur certifié"}),
            'tarif': forms.TextInput(attrs={'placeholder': "Facultatif. Ex. 15 000 CFA / mois"}),
            'whatsapp': forms.TextInput(attrs={'placeholder': "Ex. 22890000000"}),
            'photo': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            # jamais de lien vers la pièce déjà envoyée (elle est privée)
            'piece_recto': forms.FileInput(attrs={'accept': 'image/*,application/pdf'}),
            'piece_verso': forms.FileInput(attrs={'accept': 'image/*,application/pdf'}),
        }

    # piège à robots : champ caché qui doit rester vide
    site_internet = forms.CharField(required=False, widget=forms.TextInput(
        attrs={'tabindex': '-1', 'autocomplete': 'off'}))

    def clean_site_internet(self):
        if self.cleaned_data.get('site_internet'):
            raise forms.ValidationError("Envoi refusé.")
        return ''

    def clean_photo(self):
        return _verifier(self.cleaned_data.get('photo'), ('.jpg', '.jpeg', '.png', '.webp'), "Photo")

    def clean_piece_recto(self):
        return _verifier(self.cleaned_data.get('piece_recto'), EXT_PIECE, "Pièce (recto)")

    def clean_piece_verso(self):
        return _verifier(self.cleaned_data.get('piece_verso'), EXT_PIECE, "Pièce (verso)")

    def clean(self):
        d = super().clean()
        if d.get('piece_type') in ('cni', 'electeur') and not d.get('piece_verso'):
            self.add_error('piece_verso', "Le verso est obligatoire pour cette pièce.")
        return d


class RetrouverForm(forms.Form):
    numero = forms.CharField(label="Numéro de dossier", max_length=12, widget=forms.TextInput(attrs={'placeholder': 'R00012'}))
    contact = forms.CharField(label="Téléphone ou e-mail du dossier", max_length=120)

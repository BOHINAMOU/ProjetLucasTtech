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
                  'photo', 'matieres', 'niveaux', 'ville', 'quartier',
                  'experience', 'description', 'tarif',
                  'piece_type', 'piece_numero', 'piece_recto']
        labels = {'piece_recto': "Pièce d'identité (recto et verso)", 'description': "Présentation"}
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'matieres': forms.TextInput(attrs={'placeholder': "Ex. Mathématiques, Physique-Chimie"}),
            'niveaux': forms.HiddenInput(),
            'experience': forms.TextInput(attrs={'placeholder': "Ex. 6 ans, professeur certifié"}),
            'tarif': forms.TextInput(attrs={'placeholder': "Ex. 15 000 CFA / mois"}),
            'whatsapp': forms.TextInput(attrs={
                'type': 'tel', 'inputmode': 'tel', 'class': 'rp-tel', 'placeholder': "+228 90 12 34 56",
                'pattern': r'^\s*(\+?\s*228)?(\s*\d){8}\s*$', 'title': "+228 suivi de 8 chiffres"}),
            'telephone': forms.TextInput(attrs={
                'type': 'tel', 'inputmode': 'tel', 'class': 'rp-tel', 'placeholder': "90 12 34 56",
                'pattern': r'^[\d\s+]{8,20}$', 'title': "Chiffres uniquement"}),
            'photo': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            # jamais de lien vers la pièce déjà envoyée (elle est privée)
            'piece_recto': forms.FileInput(attrs={'accept': 'image/*,application/pdf'}),
        }

    # piège à robots : champ caché qui doit rester vide
    site_internet = forms.CharField(required=False, widget=forms.TextInput(
        attrs={'tabindex': '-1', 'autocomplete': 'off'}))

    def clean_site_internet(self):
        if self.cleaned_data.get('site_internet'):
            raise forms.ValidationError("Envoi refusé.")
        return ''

    def clean_telephone(self):
        t = self.cleaned_data.get('telephone') or ''
        chiffres = ''.join(c for c in t if c.isdigit())
        if len(chiffres) < 8 or any(c not in '0123456789+ ' for c in t):
            raise forms.ValidationError("Numéro invalide : chiffres uniquement.")
        return t.strip()

    def clean_whatsapp(self):
        from .models import whatsapp_togo
        return whatsapp_togo(self.cleaned_data.get('whatsapp'))

    def clean_photo(self):
        return _verifier(self.cleaned_data.get('photo'), ('.jpg', '.jpeg', '.png', '.webp'), "Photo")

    def clean_piece_recto(self):
        return _verifier(self.cleaned_data.get('piece_recto'), EXT_PIECE, "Pièce (recto)")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields['email'].required = True
        self.fields['niveaux'].required = True
        # contrôle dans le navigateur avant l'envoi : rien n'est perdu (photo, pièce) à cause d'un oubli
        for nom, f in self.fields.items():
            if f.required and nom != 'niveaux' and not (self.instance.pk and nom in ('photo', 'piece_recto')):
                f.widget.attrs['required'] = 'required'


class RetrouverForm(forms.Form):
    numero = forms.CharField(label="Numéro de dossier", max_length=12, widget=forms.TextInput(attrs={'placeholder': 'R00012'}))
    contact = forms.CharField(label="Téléphone ou e-mail du dossier", max_length=120)

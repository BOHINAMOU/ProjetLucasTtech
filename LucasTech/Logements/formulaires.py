"""Location sans annonces fictives : « Je cherche un logement » et « Publier mon logement » (validé par l'équipe)."""
from django import forms
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from Repetiteurs.models import whatsapp_togo

from .models import EQUIPEMENTS, TYPES, DemandeLogement, Logement, PhotoLogement

MAX_PHOTOS = 8
MAX_PHOTO = 8 * 1024 * 1024
LIMITE_HEURE = 5


def _ip(request):
    from core.ip import ip_client
    return ip_client(request)


def _trop(request, quoi):
    return cache.get(f'location-{quoi}:{_ip(request)}', 0) >= LIMITE_HEURE


def _compter(request, quoi):
    cle = f'location-{quoi}:{_ip(request)}'
    cache.set(cle, cache.get(cle, 0) + 1, 3600)


def _tel(valeur):
    try:
        return whatsapp_togo(valeur)
    except ValidationError:
        raise forms.ValidationError("Numéro invalide : 8 chiffres (ex. 90 12 34 56).")


def verifier_photo(f):
    """Vraie image (JPEG, PNG ou WebP), 8 Mo maximum."""
    if f.size > MAX_PHOTO:
        raise forms.ValidationError("Photo trop lourde : 8 Mo maximum.")
    try:
        from PIL import Image
        im = Image.open(f)
        im.verify()
        fmt = (im.format or '').upper()
    except Exception:
        raise forms.ValidationError("Ce fichier n'est pas une photo.")
    finally:
        f.seek(0)
    if fmt not in ('JPEG', 'PNG', 'WEBP'):
        raise forms.ValidationError("Format accepté : JPG, PNG ou WebP.")
    return f


class _Piege(forms.Form):
    site_internet = forms.CharField(required=False, widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}))

    def clean_site_internet(self):
        if self.cleaned_data.get('site_internet'):
            raise forms.ValidationError("Envoi refusé.")
        return ''


class DemandeForm(_Piege, forms.ModelForm):
    class Meta:
        model = DemandeLogement
        fields = ['nom', 'telephone', 'type', 'lieu', 'budget', 'date_souhaitee', 'message']
        labels = {'telephone': "WhatsApp", 'lieu': "Quartier ou ville", 'budget': "Budget par mois (CFA)",
                  'date_souhaitee': "Pour quand (facultatif)", 'message': "Message (facultatif)"}
        widgets = {
            'nom': forms.TextInput(attrs={'autocomplete': 'name'}),
            'telephone': forms.TextInput(attrs={'type': 'tel', 'inputmode': 'tel', 'placeholder': '90 12 34 56'}),
            'lieu': forms.TextInput(attrs={'placeholder': 'Ex. Agoè, Lomé'}),
            'budget': forms.NumberInput(attrs={'inputmode': 'numeric', 'placeholder': 'Ex. 40000', 'min': 1000}),
            'date_souhaitee': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'message': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields['type'].choices = [('', "Type…")] + [c for c in TYPES if c[0] != 'bureau'][:5]
        for f in self.fields.values():
            if f.required:
                f.widget.attrs['required'] = 'required'

    def clean_telephone(self):
        return _tel(self.cleaned_data.get('telephone'))

    def clean_budget(self):
        b = self.cleaned_data.get('budget') or 0
        if b < 1000:
            raise forms.ValidationError("Indiquez un budget en CFA.")
        return b


class _Photos(forms.ClearableFileInput):
    allow_multiple_selected = True


class _ChampPhotos(forms.FileField):
    """Plusieurs fichiers : renvoie la liste brute, vérifiée dans clean_photos."""
    def clean(self, data, initial=None):
        return [d for d in data if d] if isinstance(data, (list, tuple)) else ([data] if data else [])


class PublierForm(_Piege, forms.ModelForm):
    photos = _ChampPhotos(label="Photos (1 à 8)", required=False,
                             widget=_Photos(attrs={'multiple': True, 'accept': 'image/jpeg,image/png,image/webp'}))
    equipements = forms.MultipleChoiceField(label="Équipements", choices=EQUIPEMENTS, required=False,
                                            widget=forms.CheckboxSelectMultiple)
    accord = forms.BooleanField(required=True, error_messages={'required': "Cochez la case pour continuer."})

    class Meta:
        model = Logement
        fields = ['type', 'quartier', 'ville', 'loyer', 'caution', 'pieces', 'meuble', 'description', 'equipements',
                  'proprietaire_nom', 'proprietaire_telephone', 'propose_par_role']
        labels = {'loyer': "Loyer par mois (CFA)", 'caution': "Caution / avance (facultatif)",
                  'pieces': "Nombre de pièces (facultatif)", 'proprietaire_nom': "Votre nom",
                  'proprietaire_telephone': "Votre WhatsApp", 'propose_par_role': "Vous êtes"}
        help_texts = {'proprietaire_telephone': "Privé : seule l'équipe Lantante le voit.", 'caution': ''}
        widgets = {
            'quartier': forms.TextInput(attrs={'placeholder': 'Ex. Adidogomé'}),
            'ville': forms.TextInput(attrs={'placeholder': 'Lomé'}),
            'loyer': forms.NumberInput(attrs={'inputmode': 'numeric', 'placeholder': 'Ex. 35000', 'min': 1000}),
            'caution': forms.TextInput(attrs={'placeholder': "Ex. 3 mois d'avance"}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': "État, accès, eau, électricité…"}),
            'proprietaire_telephone': forms.TextInput(attrs={'type': 'tel', 'inputmode': 'tel', 'placeholder': '90 12 34 56'}),
        }

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields['proprietaire_nom'].required = True
        self.fields['proprietaire_telephone'].required = True
        self.fields['propose_par_role'].required = True
        self.fields['propose_par_role'].choices = [('', "Choisir…")] + list(self.fields['propose_par_role'].choices)[1:]
        self.fields['description'].required = True
        for f in self.fields.values():
            if f.required:
                f.widget.attrs['required'] = 'required'

    def clean_proprietaire_telephone(self):
        return _tel(self.cleaned_data.get('proprietaire_telephone'))

    def clean_loyer(self):
        b = self.cleaned_data.get('loyer') or 0
        if b < 1000:
            raise forms.ValidationError("Indiquez le loyer en CFA.")
        return b

    def clean_photos(self):
        fichiers = self.cleaned_data.get('photos') or []
        if not fichiers:
            raise forms.ValidationError("Ajoutez au moins une photo.")
        if len(fichiers) > MAX_PHOTOS:
            raise forms.ValidationError(f"{MAX_PHOTOS} photos maximum.")
        return [verifier_photo(f) for f in fichiers]

    def save(self, commit=True):
        l = super().save(commit=False)
        l.statut = 'attente'
        l.propose_le = timezone.now()
        l.equipements = self.cleaned_data.get('equipements') or []
        l.save()
        for i, f in enumerate(self.cleaned_data['photos']):
            PhotoLogement.objects.create(logement=l, image=f, ordre=i)
        return l


def _prevenir(texte, url):
    try:
        from core.alertes import prevenir_equipe
        prevenir_equipe(texte, url)
    except Exception:
        pass


def je_cherche(request):
    form = DemandeForm(request.POST or None)
    if request.method == 'POST':
        if _trop(request, 'demande'):
            form.add_error(None, "Trop d'envois. Réessayez dans une heure.")
        elif form.is_valid():
            d = form.save()
            _compter(request, 'demande')
            _prevenir(f"Je cherche un logement : {d.nom} (+{d.telephone})\n{d.get_type_display()} à {d.lieu}, "
                      f"budget {d.budget:,} CFA / mois".replace(',', ' '),
                      reverse('admin:Logements_demandelogement_change', args=[d.pk]))
            return redirect(reverse('logements:je_cherche') + '?envoye=1')
    return render(request, 'logements/je_cherche.html', {'form': form, 'envoye': request.GET.get('envoye') == '1'})


def publier(request):
    form = PublierForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if _trop(request, 'publier'):
            form.add_error(None, "Trop d'envois. Réessayez dans une heure.")
        elif form.is_valid():
            l = form.save()
            _compter(request, 'publier')
            _prevenir(f"Nouveau logement à valider : {l.nom}, {l.loyer:,} CFA / mois".replace(',', ' ')
                      + f"\nProposé par {l.proprietaire_nom} (+{l.proprietaire_telephone})",
                      reverse('admin:Logements_logement_change', args=[l.pk]))
            return redirect(reverse('logements:publier') + '?envoye=1')
    return render(request, 'logements/publier.html', {'form': form, 'envoye': request.GET.get('envoye') == '1',
                                                      'max_photos': MAX_PHOTOS})

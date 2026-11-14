import re
import uuid

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from . import mobile_money

User = get_user_model()

ACCOUNT_CHOICES = [
    ('guest', "Sans compte"),
    ('create', "Créer un compte"),
]


NOM_RE = re.compile(r"[^\W\d_](?:[^\W\d_]|[ '’\-]){1,59}")


class CustomerForm(forms.Form):
    """Coordonnées + paiement Mobile Money (pays, opérateur, numéro), transmis tels quels à FedaPay.

    purpose : 'service', 'formation', 'boutique', 'produit' ou 'ticket'.
    - ticket : pas de compte, WhatsApp obligatoire, email facultatif ;
    - produit : adresse de livraison + WhatsApp ;
    - service / formation : email obligatoire (lien de téléchargement), compte au choix."""

    first_name = forms.CharField(label="Prénom", max_length=100,
                                 widget=forms.TextInput(attrs={'autocomplete': 'given-name'}))
    last_name = forms.CharField(label="Nom", max_length=100,
                                widget=forms.TextInput(attrs={'autocomplete': 'family-name'}))
    whatsapp = forms.CharField(label="Numéro (WhatsApp)", max_length=30,
                               error_messages={'required': "Saisissez votre numéro."},
                               widget=forms.TextInput(attrs={'inputmode': 'tel', 'autocomplete': 'tel-national',
                                                             'placeholder': 'Ex. 90 00 00 00'}))
    city = forms.CharField(label="Localité", max_length=255,
                           error_messages={'required': "Indiquez votre localité."},
                           widget=forms.TextInput(attrs={'autocomplete': 'address-level2',
                                                         'placeholder': 'Ville, quartier'}))
    email = forms.EmailField(label="Email", required=False,
                             widget=forms.EmailInput(attrs={'autocomplete': 'email'}))
    address = forms.CharField(required=False, widget=forms.HiddenInput)

    country = forms.ChoiceField(label="Pays", choices=mobile_money.COUNTRY_CHOICES,
                                initial=mobile_money.DEFAULT_COUNTRY,
                                widget=forms.Select(attrs={'data-pay-country': '1'}))
    operator = forms.ChoiceField(label="Moyen de paiement",
                                 error_messages={'required': "Choisissez votre moyen de paiement.",
                                                 'invalid_choice': "Choisissez un moyen de paiement de la liste."},
                                 widget=forms.Select(attrs={'data-pay-operator': '1'}))
    phone = forms.CharField(label="Numéro Mobile Money", max_length=30,
                            help_text="La demande de paiement arrive sur ce téléphone : confirmez-la avec votre code secret.",
                            error_messages={'required': "Saisissez votre numéro Mobile Money."},
                            widget=forms.TextInput(attrs={'type': 'tel', 'inputmode': 'numeric', 'autocomplete': 'tel',
                                                          'placeholder': 'Ex. 90 00 00 00', 'data-pay-phone': '1'}))

    account = forms.ChoiceField(label="Compte", choices=ACCOUNT_CHOICES, initial='guest',
                                widget=forms.RadioSelect, required=False)
    password1 = forms.CharField(label="Mot de passe", required=False,
                                widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    password2 = forms.CharField(label="Confirmer le mot de passe", required=False,
                                widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    submission = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, user=None, purpose='service', **kwargs):
        self.user = user if user is not None and user.is_authenticated else None
        self.purpose = purpose
        super().__init__(*args, **kwargs)
        self.fields['operator'].choices = [('', '— Choisir —')] + [
            (m, label) for m, (_c, label, _p) in mobile_money.OPERATORS.items()]
        self.fields['operator'].widget.attrs['data-countries'] = ",".join(
            f"{m}:{c}" for m, (c, _l, _p) in mobile_money.OPERATORS.items())

        if purpose == 'produit':
            self.fields['city'].label = "Localité (livraison)"
            self.fields['city'].widget.attrs['placeholder'] = 'Ville, quartier, repère'
        if self.user or purpose in ('ticket', 'soutien'):
            for name in ('account', 'password1', 'password2'):
                self.fields.pop(name)
        if purpose == 'soutien':  # don : nom et Mobile Money suffisent
            self.fields['city'].required = False
            self.fields['whatsapp'].required = False
        if self.user and not self.is_bound:
            self.initial.update({'first_name': self.user.first_name, 'last_name': self.user.last_name,
                                 'email': self.user.email, 'whatsapp': self.user.phone or '',
                                 'city': self.user.city or ''})
        if not self.is_bound:
            self.initial.setdefault('submission', uuid.uuid4().hex)

    @property
    def has_account_choice(self):
        return 'account' in self.fields

    def clean(self):
        data = super().clean()
        country, operator, raw = data.get('country'), data.get('operator'), data.get('phone')
        if raw and not re.fullmatch(r"\+?[0-9 .\-]+", raw.strip()):
            self.add_error('phone', "Le numéro ne doit contenir que des chiffres.")
        elif country and operator and raw:
            try:
                number = mobile_money.normalize(raw, country)
                mobile_money.check_operator(number, country, operator)
                data['phone'] = number
            except forms.ValidationError as exc:
                self.add_error('operator' if 'opérateur disponible' in ' '.join(exc.messages) else 'phone', exc)
        if self.purpose == 'soutien' and not (data.get('whatsapp') or '').strip() and data.get('phone'):
            data['whatsapp'] = data['phone']
        for champ in ('first_name', 'last_name'):
            v = (data.get(champ) or '').strip()
            if v and not NOM_RE.fullmatch(v):
                self.add_error(champ, "Lettres seulement (2 à 60).")
        wa = (data.get('whatsapp') or '').strip()
        if wa and (not re.fullmatch(r"\+?[0-9 .\-]+", wa) or not 8 <= len(re.sub(r'\D', '', wa)) <= 15):
            self.add_error('whatsapp', "Numéro WhatsApp invalide : chiffres uniquement.")

        if self.has_account_choice and data.get('account') == 'create':
            email = (data.get('email') or '').strip()
            if not email:
                self.add_error('email', "L'email est obligatoire pour créer un compte.")
            elif User.objects.filter(email__iexact=email).exists():
                self.add_error('email', "Un compte existe déjà avec cet email : connectez-vous, "
                                        "ou choisissez « Continuer sans compte ».")
            p1, p2 = data.get('password1'), data.get('password2')
            if not p1:
                self.add_error('password1', "Choisissez un mot de passe.")
            elif p1 != p2:
                self.add_error('password2', "Les mots de passe ne correspondent pas.")
            else:
                try:
                    validate_password(p1)
                except forms.ValidationError as e:
                    self.add_error('password1', e)
        return data

    def create_account_if_asked(self):
        if self.user:
            return self.user
        if not self.has_account_choice or self.cleaned_data.get('account') != 'create':
            return None
        d = self.cleaned_data
        return User.objects.create_user(email=d['email'], password=d['password1'], first_name=d['first_name'],
                                        last_name=d['last_name'], phone=d.get('whatsapp') or d['phone'],
                                        city=(d.get('city') or '')[:100], account_type='member')

    def payment_fields(self):
        d = self.cleaned_data
        return {
            'first_name': d['first_name'].strip(), 'last_name': d['last_name'].strip(),
            'email': (d.get('email') or '').strip(), 'phone': d['phone'],
            'whatsapp': (d.get('whatsapp') or '').strip() or d['phone'],
            'city': (d.get('city') or '').strip(), 'operator': d['operator'],
            'address': (d.get('city') or '').strip() if self.purpose == 'produit' else '',
        }

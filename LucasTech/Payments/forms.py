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


class CustomerForm(forms.Form):
    """Coordonnées + paiement Mobile Money (pays, opérateur, numéro), transmis tels quels à FedaPay.

    purpose : 'service', 'formation', 'boutique', 'produit' ou 'ticket'.
    - ticket : pas de compte, WhatsApp obligatoire, email facultatif ;
    - produit : adresse de livraison + WhatsApp ;
    - service / formation : email obligatoire (lien de téléchargement), compte au choix."""

    first_name = forms.CharField(label="Prénom", max_length=100)
    last_name = forms.CharField(label="Nom", max_length=100)
    email = forms.EmailField(label="Email", required=False)
    whatsapp = forms.CharField(label="Numéro WhatsApp", max_length=30, required=False,
                               widget=forms.TextInput(attrs={'inputmode': 'tel', 'placeholder': 'Ex. 90 00 00 00'}))
    address = forms.CharField(label="Adresse de livraison", max_length=255, required=False,
                              widget=forms.TextInput(attrs={'placeholder': 'Quartier, ville, repère'}))

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
    password1 = forms.CharField(label="Mot de passe", required=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmer le mot de passe", required=False, widget=forms.PasswordInput)
    submission = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, user=None, purpose='service', **kwargs):
        self.user = user if user is not None and user.is_authenticated else None
        self.purpose = purpose
        super().__init__(*args, **kwargs)
        self.fields['operator'].choices = [('', '— Choisir —')] + [
            (m, label) for m, (_c, label, _p) in mobile_money.OPERATORS.items()]
        self.fields['operator'].widget.attrs['data-countries'] = ",".join(
            f"{m}:{c}" for m, (c, _l, _p) in mobile_money.OPERATORS.items())

        if purpose == 'ticket':
            self.fields['whatsapp'].required = True
            self.fields['email'].help_text = ""
        elif purpose == 'produit':
            self.fields['whatsapp'].required = True
            self.fields['address'].required = True
            self.fields['email'].help_text = ""
        else:
            self.fields['email'].required = True
            self.fields['email'].help_text = "Votre reçu et votre lien de téléchargement y seront envoyés."
            self.fields['whatsapp'].widget = forms.HiddenInput()
        if purpose != 'produit':
            self.fields['address'].widget = forms.HiddenInput()
        if self.user or purpose == 'ticket':
            for name in ('account', 'password1', 'password2'):
                self.fields.pop(name)
        if self.user and not self.is_bound:
            self.initial.update({'first_name': self.user.first_name, 'last_name': self.user.last_name,
                                 'email': self.user.email, 'whatsapp': self.user.phone or ''})
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
        wa = (data.get('whatsapp') or '').strip()
        if wa and (not re.fullmatch(r"\+?[0-9 .\-]+", wa) or not 8 <= len(re.sub(r'\D', '', wa)) <= 15):
            self.add_error('whatsapp', "Numéro WhatsApp invalide : chiffres uniquement.")

        if self.has_account_choice and data.get('account') == 'create':
            email = (data.get('email') or '').strip()
            if not email:
                self.add_error('email', "L'email est nécessaire pour créer un compte.")
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
                                        last_name=d['last_name'], phone=d['phone'], account_type='member')

    def payment_fields(self):
        d = self.cleaned_data
        return {
            'first_name': d['first_name'].strip(), 'last_name': d['last_name'].strip(),
            'email': (d.get('email') or '').strip(), 'phone': d['phone'],
            'whatsapp': (d.get('whatsapp') or '').strip() or d['phone'],
            'address': (d.get('address') or '').strip(), 'operator': d['operator'],
        }

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

ACCOUNT_CHOICES = [
    ('guest', "Continuer sans compte"),
    ('create', "Créer un compte (retrouver mes achats plus tard)"),
]


class CustomerForm(forms.Form):
    first_name = forms.CharField(label="Prénom", max_length=100)
    last_name = forms.CharField(label="Nom", max_length=100)
    phone = forms.CharField(label="Téléphone", max_length=30,
                            widget=forms.TextInput(attrs={'inputmode': 'tel', 'placeholder': '+228 90 00 00 00'}))
    email = forms.EmailField(label="Email", help_text="Votre reçu et votre lien de téléchargement y seront envoyés.")
    account = forms.ChoiceField(label="Compte", choices=ACCOUNT_CHOICES, initial='guest',
                                widget=forms.RadioSelect, required=False)
    password1 = forms.CharField(label="Mot de passe", required=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmer le mot de passe", required=False, widget=forms.PasswordInput)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user if user is not None and user.is_authenticated else None
        super().__init__(*args, **kwargs)
        if self.user:
            for name in ('account', 'password1', 'password2'):
                self.fields.pop(name)
            if not self.is_bound:
                self.initial.update({
                    'first_name': self.user.first_name, 'last_name': self.user.last_name,
                    'phone': self.user.phone or '', 'email': self.user.email,
                })

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if len([c for c in phone if c.isdigit()]) < 8:
            raise forms.ValidationError("Numéro de téléphone invalide.")
        return phone

    def clean(self):
        data = super().clean()
        if self.user or data.get('account') != 'create':
            return data
        email = (data.get('email') or '').strip()
        if email and User.objects.filter(email__iexact=email).exists():
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
        """Crée le compte si demandé et le renvoie (sinon None)."""
        if self.user:
            return self.user
        if self.cleaned_data.get('account') != 'create':
            return None
        d = self.cleaned_data
        return User.objects.create_user(email=d['email'], password=d['password1'], first_name=d['first_name'],
                                        last_name=d['last_name'], phone=d['phone'], account_type='member')

    def payment_fields(self):
        d = self.cleaned_data
        return {k: d[k].strip() for k in ('first_name', 'last_name', 'phone', 'email')}

from django import forms
from django.contrib.auth import authenticate
from .models import User
from core.countries import COUNTRY_CHOICES


# ─────────────────────────────
# 📝 INSCRIPTION
# ─────────────────────────────
class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)
    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES, required=False,
        widget=forms.Select(attrs={'class': 'auth-input'}),
    )

    class Meta:
        model = User
        fields = ['email', 'phone', 'country', 'city']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Cet email est déjà utilisé.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')

        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


# ─────────────────────────────
# 🔐 CONNEXION
# ─────────────────────────────
class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = None

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get('email')
        password = cleaned.get('password')

        if email and password:
            self._user = authenticate(username=email, password=password)

            if self._user is None:
                raise forms.ValidationError("Email ou mot de passe incorrect.")

            if not self._user.is_active:
                raise forms.ValidationError("Ce compte est désactivé.")

        return cleaned

    def get_user(self):
        return self._user


# ─────────────────────────────
# 📩 RESET PASSWORD - STEP 1 (EMAIL)
# ─────────────────────────────
class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(label="Adresse email")


# ─────────────────────────────
# 🔐 RESET PASSWORD - STEP 3 (NOUVEAU MDP)
# ─────────────────────────────
class SetNewPasswordForm(forms.Form):
    new_password1 = forms.CharField(
        widget=forms.PasswordInput,
        label="Nouveau mot de passe"
    )

    new_password2 = forms.CharField(
        widget=forms.PasswordInput,
        label="Confirmer le mot de passe"
    )

    def clean(self):
        cleaned = super().clean()

        p1 = cleaned.get("new_password1")
        p2 = cleaned.get("new_password2")

        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")

        if p1 and len(p1) < 8:
            raise forms.ValidationError("Le mot de passe doit contenir au moins 8 caractères.")

        return cleaned


# ─────────────────────────────
#  PROFIL
# ─────────────────────────────
class ProfileUpdateForm(forms.ModelForm):
    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES, required=False, label="Pays",
        widget=forms.Select(attrs={'class': 'ep-input'}),
    )
    phone = forms.CharField(
        required=False, label="Téléphone",
        widget=forms.TextInput(attrs={'class': 'ep-input', 'placeholder': 'Ex : 22890000000'}),
    )
    city = forms.CharField(
        required=False, label="Ville",
        widget=forms.TextInput(attrs={'class': 'ep-input', 'placeholder': 'Ex : Lomé'}),
    )
    date_of_birth = forms.DateField(
        required=False, label="Date de naissance",
        widget=forms.DateInput(attrs={'class': 'ep-input', 'type': 'date'}),
    )

    class Meta:
        model = User
        fields = ['phone', 'country', 'city', 'date_of_birth']
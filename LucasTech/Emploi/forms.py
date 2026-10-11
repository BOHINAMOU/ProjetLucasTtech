from django import forms

from .models import (
    CandidateProfile, EmployerProfile, JobOffer, StaffingRequest, Skill,
    FeedPost, FeedComment, Application,
)

CV_MAX_MB = 5


def _style(form):
    """Ajoute la classe CSS commune aux champs."""
    for name, field in form.fields.items():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault('class', 'em-check')
        elif isinstance(widget, forms.FileInput):
            widget.attrs.setdefault('class', 'em-file')
        else:
            widget.attrs.setdefault('class', 'em-input')


class SkillsTextMixin:
    """Champ « skills_text » : compétences séparées par des virgules."""
    skills_text = forms.CharField(
        required=False, label="Compétences",
        help_text="Séparées par des virgules. Ex : Excel, Python, Gestion de stock",
        widget=forms.TextInput(attrs={'placeholder': 'Excel, Python, Gestion de stock'}),
    )

    def init_skills(self):
        if self.instance and self.instance.pk:
            self.fields['skills_text'].initial = ", ".join(
                self.instance.skills.values_list('name', flat=True))

    def save_skills(self, instance):
        names = []
        for raw in self.cleaned_data.get('skills_text', '').split(','):
            name = raw.strip()[:80]
            if name and name.lower() not in [n.lower() for n in names]:
                names.append(name)
        skills = []
        for name in names[:20]:
            skill = Skill.objects.filter(name__iexact=name).first() or Skill.objects.create(name=name)
            skills.append(skill)
        instance.skills.set(skills)


class CandidateForm(SkillsTextMixin, forms.ModelForm):
    first_name = forms.CharField(max_length=150, label="Prénom")
    last_name = forms.CharField(max_length=150, label="Nom")
    avatar = forms.ImageField(required=False, label="Photo de profil")
    skills_text = SkillsTextMixin.skills_text

    class Meta:
        model = CandidateProfile
        fields = ['headline', 'domain', 'city', 'bio', 'experience_years', 'education_level',
                  'contract_wanted', 'available', 'phone', 'cv',
                  'show_photo', 'show_city', 'show_bio', 'show_experience', 'share_with_recruiters']
        widgets = {'bio': forms.Textarea(attrs={'rows': 5})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
        self.init_skills()
        _style(self)

    def clean_cv(self):
        cv = self.cleaned_data.get('cv')
        if cv and hasattr(cv, 'size') and not getattr(cv, '_committed', False):
            if not cv.name.lower().endswith('.pdf'):
                raise forms.ValidationError("Le CV doit être un fichier PDF.")
            if cv.size > CV_MAX_MB * 1024 * 1024:
                raise forms.ValidationError(f"Le CV ne doit pas dépasser {CV_MAX_MB} Mo.")
            head = cv.read(5)
            cv.seek(0)
            if head != b'%PDF-':
                raise forms.ValidationError("Ce fichier n'est pas un vrai PDF.")
        return cv

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = self.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if self.cleaned_data.get('avatar'):
            user.avatar = self.cleaned_data['avatar']
        profile.user = user
        if commit:
            user.save()
            profile.save()
            self.save_skills(profile)
        return profile


class EmployerForm(forms.ModelForm):
    class Meta:
        model = EmployerProfile
        fields = ['company_name', 'logo', 'sector', 'city', 'description', 'products',
                  'website', 'whatsapp', 'contact_email']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'products': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class JobOfferForm(SkillsTextMixin, forms.ModelForm):
    skills_text = SkillsTextMixin.skills_text

    class Meta:
        model = JobOffer
        fields = ['title', 'domain', 'contract', 'city', 'description', 'requirements',
                  'salary', 'deadline']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 6}),
            'requirements': forms.Textarea(attrs={'rows': 4}),
            'deadline': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_skills()
        _style(self)


class StaffingRequestForm(SkillsTextMixin, forms.ModelForm):
    skills_text = SkillsTextMixin.skills_text

    class Meta:
        model = StaffingRequest
        fields = ['title', 'domain', 'positions', 'contract', 'city', 'description', 'urgency']
        widgets = {'description': forms.Textarea(attrs={'rows': 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_skills()
        _style(self)


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['message']
        widgets = {'message': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Un petit mot pour appuyer votre candidature (facultatif)'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class FeedPostForm(forms.ModelForm):
    class Meta:
        model = FeedPost
        fields = ['text', 'image']
        widgets = {'text': forms.Textarea(attrs={'rows': 3, 'placeholder': "Partagez une actualité, une opportunité, une réussite…"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class CommentForm(forms.ModelForm):
    class Meta:
        model = FeedComment
        fields = ['text']
        widgets = {'text': forms.TextInput(attrs={'placeholder': 'Écrire un commentaire…'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class MessageForm(forms.Form):
    body = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Votre message…'}),
                           max_length=4000, label="Message")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class NewConversationForm(MessageForm):
    subject = forms.CharField(max_length=160, required=False, label="Sujet")

    field_order = ['subject', 'body']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)

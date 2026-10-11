from django import forms

from .models import (
    CONTRACT_CHOICES, INTERNSHIP_DURATION_CHOICES, OFFER_DURATION_CHOICES, PublicationOrder, SpontaneousRequest,
    CandidateDocument, CandidateProfile, EmployerProfile, JobOffer, StaffingRequest, Skill,
    FeedPost, FeedComment, Application,
)

CV_MAX_MB = 5


def _style(form):
    """Ajoute la classe CSS commune aux champs."""
    for name, field in form.fields.items():
        widget = field.widget
        if isinstance(widget, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
            continue  # listes de cases / boutons radio : mise en forme par le gabarit
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
    contract_wanted = forms.MultipleChoiceField(
        choices=CONTRACT_CHOICES, required=False, widget=forms.CheckboxSelectMultiple,
        label="Types de contrat souhaités", help_text="Cochez un ou plusieurs types de contrat.")
    internship_duration = forms.ChoiceField(
        choices=[('', "— Choisir —")] + INTERNSHIP_DURATION_CHOICES, required=False, label="Durée de stage souhaitée")

    class Meta:
        model = CandidateProfile
        fields = ['headline', 'domain', 'city', 'bio', 'experience_years', 'education_level',
                  'contract_wanted', 'available', 'seeking_internship', 'internship_duration', 'available_from',
                  'phone', 'cv', 'cover_letter',
                  'show_photo', 'show_city', 'show_bio', 'show_experience']
        widgets = {'bio': forms.Textarea(attrs={'rows': 5}),
                   'cover_letter': forms.Textarea(attrs={'rows': 8, 'placeholder': "Madame, Monsieur, …"}),
                   'available_from': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
        if self.instance.pk:
            self.initial['contract_wanted'] = self.instance.contract_wanted_codes
        if user and not self.instance.pk:
            self.fields['phone'].initial = user.phone or ''
            self.fields['city'].initial = user.city or ''
        self.init_skills()
        _style(self)

    def clean_contract_wanted(self):
        chosen = set(self.cleaned_data.get('contract_wanted') or [])
        return ",".join(code for code, _ in CONTRACT_CHOICES if code in chosen)  # stocké dans l'ordre du catalogue

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


DOC_MAX_MB = 10
# (extension, début du fichier) : on vérifie aussi le contenu, pas seulement le nom.
DOC_SIGNATURES = {
    '.pdf': (b'%PDF-',),
    '.docx': (bytes.fromhex('504b0304'),),  # fichier zip (Office moderne)
    '.xlsx': (bytes.fromhex('504b0304'),),
    '.doc': (bytes.fromhex('d0cf11e0'),),   # ancien format Office
    '.xls': (bytes.fromhex('d0cf11e0'),),
}


class EmployerForm(forms.ModelForm):
    class Meta:
        model = EmployerProfile
        fields = ['company_name', 'logo', 'sector', 'city', 'employees_count', 'description', 'products',
                  'website', 'whatsapp', 'contact_email', 'document']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'products': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Reprend les informations déjà connues du compte (modifiables).
        if user and not self.instance.pk:
            self.fields['contact_email'].initial = user.email
            self.fields['whatsapp'].initial = ''.join(ch for ch in (user.phone or '') if ch.isdigit())
            self.fields['city'].initial = user.city or ''
        # Le document est obligatoire à l'inscription de l'entreprise.
        if not self.instance.pk or not self.instance.document:
            self.fields['document'].required = True
        if not self.instance.pk:
            self.fields['logo'].required = True
        self.fields['employees_count'].required = True
        self.fields['employees_count'].widget.attrs['min'] = 1
        _style(self)

    def clean_document(self):
        doc = self.cleaned_data.get('document')
        if doc and hasattr(doc, 'size') and not getattr(doc, '_committed', False):
            ext = '.' + doc.name.rsplit('.', 1)[-1].lower() if '.' in doc.name else ''
            if ext not in DOC_SIGNATURES:
                raise forms.ValidationError("Format accepté : Word (.doc, .docx), Excel (.xls, .xlsx) ou PDF.")
            if doc.size > DOC_MAX_MB * 1024 * 1024:
                raise forms.ValidationError(f"Le document ne doit pas dépasser {DOC_MAX_MB} Mo.")
            head = doc.read(5)
            doc.seek(0)
            if not any(head.startswith(sig) for sig in DOC_SIGNATURES[ext]):
                raise forms.ValidationError("Ce fichier ne semble pas être un vrai document de ce format.")
        return doc


class JobOfferForm(SkillsTextMixin, forms.ModelForm):
    skills_text = SkillsTextMixin.skills_text
    duration = forms.ChoiceField(choices=[('', "— Aucune —")] + OFFER_DURATION_CHOICES, required=False,
                                 label="Durée (stage, CDD…)")

    class Meta:
        model = JobOffer
        fields = ['title', 'cover_image', 'domain', 'contract', 'city', 'description', 'requirements',
                  'salary', 'duration', 'deadline', 'requires_cover_letter']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 6}),
            'requirements': forms.Textarea(attrs={'rows': 4}),
            'deadline': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_skills()
        _style(self)

    def clean_cover_image(self):
        return _check_cover(self)


def _check_cover(form):
    image = form.cleaned_data.get('cover_image')
    if image and hasattr(image, 'size') and image.size > CV_MAX_MB * 1024 * 1024:
        raise forms.ValidationError(f"La photo ne doit pas dépasser {CV_MAX_MB} Mo.")
    return image


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


COVER_LETTER_MIN = 80


class ApplicationForm(forms.Form):
    """Lettre de motivation : obligatoire si l'offre la demande, sinon facultative. Préremplie depuis le profil."""
    text = forms.CharField(required=False, max_length=5000, widget=forms.Textarea(attrs={'rows': 6}))

    def __init__(self, *args, offer=None, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.needs_letter = bool(offer and offer.requires_cover_letter)
        self.is_internship = bool(offer and offer.contract == 'stage')
        if self.is_internship:
            # Stage : le candidat précise la durée souhaitée et sa date de début.
            wanted = (profile.internship_duration if profile else '') or offer.duration
            self.fields['internship_duration'] = forms.ChoiceField(
                choices=[('', "— Choisir —")] + INTERNSHIP_DURATION_CHOICES, label="Durée de stage souhaitée",
                initial=wanted if wanted in dict(INTERNSHIP_DURATION_CHOICES) else '')
            self.fields['available_from'] = forms.DateField(
                required=False, label="Disponible à partir du",
                initial=profile.available_from if profile else None,
                widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
        field = self.fields['text']
        if profile and profile.cover_letter and not self.is_bound:
            field.initial = profile.cover_letter  # lettre du profil, adaptable à chaque offre
        if self.needs_letter:
            field.required = True
            field.label = "Lettre de motivation (demandée par l'entreprise)"
            field.widget.attrs['placeholder'] = "Expliquez pourquoi ce poste vous intéresse et ce que vous apporterez…"
        else:
            field.label = "Lettre de motivation (facultative)"
            field.widget.attrs['placeholder'] = "Un petit mot ou votre lettre de motivation pour appuyer votre candidature"
        _style(self)

    def clean_text(self):
        text = self.cleaned_data.get('text', '').strip()
        if self.needs_letter and len(text) < COVER_LETTER_MIN:
            raise forms.ValidationError(
                f"La lettre de motivation est demandée : écrivez au moins {COVER_LETTER_MIN} caractères.")
        return text


class AvailabilityForm(forms.Form):
    """Disponibilités proposées par un candidat présélectionné pour son entretien."""
    slot1 = forms.DateTimeField(label="Disponibilité 1", widget=forms.DateTimeInput(
        attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'))
    slot2 = forms.DateTimeField(label="Disponibilité 2 (facultatif)", required=False, widget=forms.DateTimeInput(
        attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'))
    slot3 = forms.DateTimeField(label="Disponibilité 3 (facultatif)", required=False, widget=forms.DateTimeInput(
        attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'))
    note = forms.CharField(label="Précision (facultatif)", required=False, max_length=200,
                           widget=forms.TextInput(attrs={'placeholder': "Ex : plutôt le matin, ou par appel / en visio"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)

    def clean(self):
        from django.utils import timezone
        cleaned = super().clean()
        for name in ('slot1', 'slot2', 'slot3'):
            value = cleaned.get(name)
            if value and value < timezone.now():
                self.add_error(name, "Choisissez une date à venir.")
        return cleaned

    def slots(self):
        return [self.cleaned_data[n] for n in ('slot1', 'slot2', 'slot3') if self.cleaned_data.get(n)]


class FeedPostForm(forms.ModelForm):
    class Meta:
        model = FeedPost
        fields = ['kind', 'text', 'image']
        widgets = {'text': forms.Textarea(attrs={'rows': 3, 'placeholder': "Partagez une actualité, une opportunité, une réussite…"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['kind'].required = False
        _style(self)

    def clean_kind(self):
        return self.cleaned_data.get('kind') or 'news'


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


# Diplômes : PDF ou photo (JPG/PNG), vérifiés sur leur contenu.
DIPLOMA_SIGNATURES = {
    '.pdf': (b'%PDF-',),
    '.jpg': (bytes.fromhex('ffd8ff'),),
    '.jpeg': (bytes.fromhex('ffd8ff'),),
    '.png': (bytes.fromhex('89504e47'),),
}


class CandidateDocumentForm(forms.ModelForm):
    class Meta:
        model = CandidateDocument
        fields = ['kind', 'title', 'file']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)

    def clean_file(self):
        f = self.cleaned_data['file']
        ext = '.' + f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
        if ext not in DIPLOMA_SIGNATURES:
            raise forms.ValidationError("Format accepté : PDF, JPG ou PNG.")
        if f.size > CV_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f"Le fichier ne doit pas dépasser {CV_MAX_MB} Mo.")
        head = f.read(8)
        f.seek(0)
        if not any(head.startswith(sig) for sig in DIPLOMA_SIGNATURES[ext]):
            raise forms.ValidationError("Ce fichier ne semble pas être un vrai document de ce format.")
        return f


class OrderContentForm(forms.ModelForm):
    """Contenu d'une actualité, d'une mise en avant ou d'une publicité."""

    class Meta:
        model = PublicationOrder
        fields = ['title', 'post_kind', 'text', 'image', 'link_url']
        widgets = {'text': forms.Textarea(attrs={'rows': 6})}
        labels = {'title': "Titre (facultatif)", 'post_kind': "Type de publication", 'text': "Texte de la publication",
                  'image': "Image (facultative)", 'link_url': "Lien (site, page Facebook, WhatsApp…)"}

    def __init__(self, *args, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan = plan or self.instance.plan
        self.fields['text'].required = True
        if self.plan.kind != 'ad':
            del self.fields['link_url']
        else:
            self.fields['image'].label = "Visuel de la publicité"
            self.fields['link_url'].required = False
        _style(self)

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size') and image.size > CV_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f"L'image ne doit pas dépasser {CV_MAX_MB} Mo.")
        return image

    def clean(self):
        cleaned = super().clean()
        has_image = cleaned.get('image') or (self.instance.pk and self.instance.image)
        if self.plan.kind == 'ad' and not has_image:
            self.add_error('image', "Une publicité a besoin d'un visuel.")
        return cleaned


class PaymentForm(forms.Form):
    payment_method = forms.ChoiceField(choices=[('flooz', "Flooz"), ('tmoney', "T-Money")],
                                       widget=forms.RadioSelect, label="Moyen de paiement")
    payer_phone = forms.CharField(max_length=30, label="Numéro avec lequel vous avez payé",
                                  widget=forms.TextInput(attrs={'placeholder': '+228 90 00 00 00'}))
    payment_reference = forms.CharField(max_length=80, label="Référence (numéro) de la transaction",
                                        help_text="Reçue par SMS après l'envoi de l'argent.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class SpontaneousRequestForm(SkillsTextMixin, forms.ModelForm):
    """Demande spontanée : se faire connaître même sans offre publiée."""
    skills_text = SkillsTextMixin.skills_text
    duration = forms.ChoiceField(choices=[('', "— Sans objet —")] + INTERNSHIP_DURATION_CHOICES, required=False,
                                 label="Durée souhaitée (stage, alternance)")

    class Meta:
        model = SpontaneousRequest
        fields = ['request_type', 'domain', 'city', 'available_from', 'duration', 'message']
        widgets = {'message': forms.Textarea(attrs={'rows': 5, 'placeholder': "Décrivez ce que vous recherchez, votre parcours, vos atouts…"}),
                   'available_from': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def __init__(self, *args, candidate=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.candidate = candidate
        if candidate and not self.instance.pk:
            self.fields['domain'].initial = candidate.domain
            self.fields['city'].initial = candidate.city
            self.fields['skills_text'].initial = ", ".join(candidate.skills.values_list('name', flat=True))
            self.fields['available_from'].initial = candidate.available_from
        self.init_skills()
        _style(self)

    def save(self, commit=True):
        req = super().save(commit=False)
        if self.candidate:
            req.candidate = self.candidate
        if commit:
            req.save()
            self.save_skills(req)
        return req


class OfferBoostForm(forms.Form):
    """Choix de l'offre à mettre en avant (parmi celles déjà publiées par l'entreprise)."""
    offer = forms.ModelChoiceField(queryset=None, label="Offre à mettre en avant", empty_label="— Choisir une offre —")

    def __init__(self, *args, employer=None, **kwargs):
        from .models import JobOffer
        super().__init__(*args, **kwargs)
        self.fields['offer'].queryset = JobOffer.objects.filter(employer=employer, status='published') if employer \
            else JobOffer.objects.none()
        _style(self)

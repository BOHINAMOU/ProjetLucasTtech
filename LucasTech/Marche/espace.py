"""Espace vendeur : application séparée du site (/espace/<code>/), connexion obligatoire.
Le lien seul ne suffit pas ; chaque vendeur ne voit que ses données ; l'équipe peut suspendre et régénérer le lien."""
import secrets
from datetime import timedelta
from functools import wraps

from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Count, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from Repetiteurs.models import whatsapp_togo

from .models import Vendeur

ESSAIS = 5  # tentatives de connexion par 15 minutes (par lien et adresse IP)


def _site():
    return (getattr(settings, 'SITE_URL', '') or 'https://lantantetechnologie.com').rstrip('/')


def _ip(request):
    return __import__('core.ip', fromlist=['ip_client']).ip_client(request)


def lien_activation(v):
    """Nouveau lien à usage unique pour créer (ou recréer) son mot de passe."""
    v.activation = secrets.token_urlsafe(32)
    v.save(update_fields=['activation'])
    return _site() + reverse('espace:activer', args=[v.code, v.activation])


def envoyer_acces(v):
    lien = lien_activation(v)
    try:
        send_mail("Votre espace vendeur Lantante",
                  f"Bonjour,\n\nVotre espace vendeur « {v.boutique} » est prêt.\n\n"
                  f"Créez votre mot de passe : {lien}\n\nEnsuite, connectez-vous ici : {_site()}{v.lien_espace()}"
                  "\n\nL'équipe Lantante", settings.DEFAULT_FROM_EMAIL, [v.user.email], fail_silently=True)
    except Exception:
        pass
    return lien


def _vendeur(code):
    return get_object_or_404(Vendeur.objects.select_related('user'), code=code)


def espace(vue):
    """Connexion obligatoire, vendeur actif, et seulement SON espace."""
    @wraps(vue)
    def w(request, code, *a, **k):
        v = _vendeur(code)
        if not request.user.is_authenticated or request.user.pk != v.user_id:
            return redirect('espace:connexion', code)
        if not v.actif:
            logout(request)
            return _suspendu(request, v)
        return vue(request, v, *a, **k)
    return w


def _suspendu(request, v):
    from urllib.parse import quote
    from core.models import SiteSettings
    try:
        num = ''.join(c for c in (SiteSettings.load().whatsapp_1 or '') if c.isdigit())
    except Exception:
        num = ''
    num = num or '22892967787'
    txt = f"Bonjour Lantante, je suis le vendeur « {v.boutique} ». Mon accès est {v.etat[1].lower()}, je souhaite le réactiver."
    return render(request, 'marche/espace/suspendu.html', {'v': v, 'wa': f"https://wa.me/{num}?text={quote(txt)}"}, status=403)


# ── Connexion, activation, mot de passe oublié ──

def connexion(request, code):
    v = _vendeur(code)
    if request.user.is_authenticated and request.user.pk == v.user_id and v.actif:
        return redirect('espace:tableau', code)
    erreur = ''
    if request.method == 'POST':
        cle = f'espace:{code}:{_ip(request)}'
        if cache.get(cle, 0) >= ESSAIS:
            erreur = "Trop de tentatives. Réessayez dans 15 minutes."
        else:
            u = authenticate(request, email=request.POST.get('email', '').strip(), password=request.POST.get('password', ''))
            if u and u.pk == v.user_id and not v.actif:
                return _suspendu(request, v)
            if u and u.pk == v.user_id:
                cache.delete(cle)
                login(request, u, backend='django.contrib.auth.backends.ModelBackend')
                return redirect('espace:tableau', code)
            cache.set(cle, cache.get(cle, 0) + 1, 900)
            erreur = "E-mail ou mot de passe incorrect."
    return render(request, 'marche/espace/connexion.html', {'v': v, 'erreur': erreur})


class _MotDePasse(forms.Form):
    password = forms.CharField(label="Mot de passe", min_length=8, widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmer", widget=forms.PasswordInput)

    def clean(self):
        d = super().clean()
        if d.get('password') and d.get('password') != d.get('password2'):
            self.add_error('password2', "Les deux mots de passe sont différents.")
        return d


def activer(request, code, jeton):
    v = _vendeur(code)
    if not v.activation or not secrets.compare_digest(v.activation, jeton):
        raise Http404
    form = _MotDePasse(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        v.user.set_password(form.cleaned_data['password'])
        v.user.save()
        v.activation = ''
        v.save(update_fields=['activation'])
        login(request, v.user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('espace:tableau', code)
    return render(request, 'marche/espace/activer.html', {'v': v, 'form': form})


def oubli(request, code):
    v = _vendeur(code)
    envoye = False
    if request.method == 'POST':
        cle = f'espace-oubli:{code}:{_ip(request)}'
        if cache.get(cle, 0) < 3 and request.POST.get('email', '').strip().lower() == v.user.email.lower():
            envoyer_acces(v)
        cache.set(cle, cache.get(cle, 0) + 1, 3600)
        envoye = True  # même réponse dans tous les cas (rien n'est révélé)
    return render(request, 'marche/espace/oubli.html', {'v': v, 'envoye': envoye})


def deconnexion(request, code):
    logout(request)
    return redirect('espace:connexion', code)


# ── Pages de l'espace ──

def _lien_public(request, v):
    return request.build_absolute_uri(v.lien_public()) if v.slug else ''


@espace
def tableau(request, v):
    from Payments.models import Payment
    from Shop.models import Product
    from .admin import comptes
    produits = Product.objects.filter(vendeur=v)
    p = produits.aggregate(n=Count('pk'), vues=Sum('vues'), clics=Sum('clics_whatsapp'))
    ventes = Payment.objects.filter(vendeur=v, status='approved')
    debut = timezone.localdate() - timedelta(days=13)
    jours = {debut + timedelta(days=i): 0 for i in range(14)}
    for pay in ventes.filter(created_at__date__gte=debut).values('created_at', 'amount'):
        d = timezone.localtime(pay['created_at']).date()
        if d in jours:
            jours[d] += pay['amount']
    haut = max(jours.values()) or 1
    barres = [{'jour': d, 'montant': m, 'h': max(3, int(m * 100 / haut)) if m else 3} for d, m in jours.items()]
    a_faire = []
    sans_photo = produits.filter(image='').count() + produits.filter(image__isnull=True).count()
    if sans_photo:
        a_faire.append((f"{sans_photo} produit{'s' if sans_photo > 1 else ''} sans photo", 'add_a_photo'))
    rupture = produits.filter(is_available=True, stock=0).count()
    if rupture:
        a_faire.append((f"{rupture} produit{'s' if rupture > 1 else ''} en stock 0", 'inventory_2'))
    if not v.logo:
        a_faire.append(("Ajoutez votre logo dans Paramètres", 'storefront'))
    return render(request, 'marche/espace/tableau.html', {
        'v': v, 'page': 'tableau', 'nb_produits': p['n'] or 0, 'vues': p['vues'] or 0, 'clics': p['clics'] or 0,
        'c': comptes(v), 'barres': barres, 'total14': sum(jours.values()), 'a_faire': a_faire,
        'lien': _lien_public(request, v),
        'derniers': produits.order_by('-pk')[:4],
        'commandes': Payment.objects.filter(vendeur=v).order_by('-created_at')[:5]})


@espace
def mon_lien(request, v):
    from urllib.parse import quote
    lien = _lien_public(request, v)
    txt = f"Découvrez ma boutique « {v.boutique} » sur Lantante : {lien}"
    return render(request, 'marche/espace/mon_lien.html', {'v': v, 'page': 'lien', 'lien': lien,
                                                           'wa': f"https://wa.me/?text={quote(txt)}"})


class ProduitForm(forms.ModelForm):
    class Meta:
        from Shop.models import Product
        model = Product
        fields = ['name', 'price', 'old_price', 'description', 'image', 'stock', 'is_available',
                  'mode_commande', 'contact_whatsapp', 'livrable']
        labels = {'name': "Nom", 'price': "Prix (CFA)", 'old_price': "Ancien prix (CFA)", 'image': "Photo",
                  'is_available': "En vente", 'contact_whatsapp': "WhatsApp (facultatif)"}
        help_texts = {'contact_whatsapp': "Vide : le WhatsApp de vos paramètres.", 'old_price': "Facultatif.",
                      'mode_commande': '', 'livrable': ''}
        widgets = {'description': forms.Textarea(attrs={'rows': 4}),
                   'contact_whatsapp': forms.TextInput(attrs={'type': 'tel', 'inputmode': 'tel'})}

    def __init__(self, *a, vendeur=None, **k):
        super().__init__(*a, **k)

    def clean_contact_whatsapp(self):
        w = self.cleaned_data.get('contact_whatsapp') or ''
        return whatsapp_togo(w) if w.strip() else ''


def _categorie_partenaires():
    from Shop.models import Category
    return Category.objects.get_or_create(slug='boutiques-partenaires', defaults={'name': 'Boutiques partenaires'})[0]


@espace
def produits(request, v):
    from Shop.models import Product
    qs = Product.objects.filter(vendeur=v).order_by('-pk')
    return render(request, 'marche/espace/produits.html', {'v': v, 'page': 'produits', 'produits': qs})


@espace
def produit(request, v, pk=None):
    from Shop.models import Product
    obj = get_object_or_404(Product, pk=pk, vendeur=v) if pk else None
    form = ProduitForm(request.POST or None, request.FILES or None, instance=obj, vendeur=v)
    if request.method == 'POST' and form.is_valid():
        p = form.save(commit=False)
        p.vendeur = v
        if not p.category_id:
            p.category = _categorie_partenaires()
        p.save()
        return redirect('espace:produits', v.code)
    return render(request, 'marche/espace/produit.html', {'v': v, 'page': 'produits', 'form': form, 'obj': obj})


@espace
def produit_supprimer(request, v, pk):
    from Shop.models import Product
    p = get_object_or_404(Product, pk=pk, vendeur=v)
    if request.method == 'POST':
        if p.payments.exists():  # déjà vendu : on le retire de la vente au lieu d'effacer l'historique
            p.is_available = False
            p.save(update_fields=['is_available'])
        else:
            p.delete()
    return redirect('espace:produits', v.code)


@espace
def categories(request, v):
    return redirect('espace:produits', v.code)


@espace
def commandes(request, v):
    from Payments.models import Payment
    qs = Payment.objects.filter(vendeur=v).order_by('-created_at')[:200]
    return render(request, 'marche/espace/commandes.html', {'v': v, 'page': 'commandes', 'commandes': qs})


class ParametresForm(forms.ModelForm):
    class Meta:
        model = Vendeur
        fields = ['boutique', 'logo', 'whatsapp', 'telephone', 'ville', 'adresse_retrait', 'description']
        labels = {'adresse_retrait': "Adresse"}
        help_texts = {'whatsapp': "+228 suivi de 8 chiffres."}
        widgets = {'whatsapp': forms.TextInput(attrs={'type': 'tel', 'inputmode': 'tel'}),
                   'telephone': forms.TextInput(attrs={'type': 'tel', 'inputmode': 'tel'}),
                   'description': forms.Textarea(attrs={'rows': 4})}

    def clean_whatsapp(self):
        return whatsapp_togo(self.cleaned_data.get('whatsapp'))

    def clean_telephone(self):
        t = (self.cleaned_data.get('telephone') or '').strip()
        if t and any(c not in '0123456789+ ' for c in t):
            raise forms.ValidationError("Chiffres uniquement.")
        return t


@espace
def parametres(request, v):
    form = ParametresForm(request.POST or None, request.FILES or None, instance=v)
    ok = False
    if request.method == 'POST' and form.is_valid():
        form.save()
        ok = True
    return render(request, 'marche/espace/parametres.html', {'v': v, 'page': 'parametres', 'form': form, 'ok': ok})


# ── Mon site (mini-site du vendeur) ──

class SiteForm(forms.ModelForm):
    class Meta:
        model = Vendeur
        fields = ['boutique', 'slogan', 'logo', 'banniere', 'couleur', 'description', 'whatsapp', 'telephone',
                  'email_contact', 'ville', 'adresse_retrait', 'chaine_whatsapp', 'texte_chaine',
                  'facebook', 'instagram', 'tiktok', 'youtube', 'x', 'telegram', 'site_web']
        labels = {'boutique': "Nom de la boutique", 'adresse_retrait': "Adresse", 'description': "Présentation"}
        help_texts = {'whatsapp': "+228 suivi de 8 chiffres.", 'couleur': '', 'banniere': "Grande image en haut de votre site."}
        widgets = {'couleur': forms.TextInput(attrs={'type': 'color'}),
                   'logo': forms.FileInput(attrs={'accept': 'image/*'}), 'banniere': forms.FileInput(attrs={'accept': 'image/*'}),
                   'whatsapp': forms.TextInput(attrs={'type': 'tel', 'inputmode': 'tel'}),
                   'telephone': forms.TextInput(attrs={'type': 'tel', 'inputmode': 'tel'}),
                   'description': forms.Textarea(attrs={'rows': 3})}

    def clean_whatsapp(self):
        return whatsapp_togo(self.cleaned_data.get('whatsapp'))

    def clean_chaine_whatsapp(self):
        u = (self.cleaned_data.get('chaine_whatsapp') or '').strip()
        if u and 'whatsapp.com' not in u.lower():
            raise forms.ValidationError("Collez le lien de votre chaîne (https://whatsapp.com/channel/…).")
        return u

    def clean_texte_chaine(self):
        return (self.cleaned_data.get('texte_chaine') or '').strip() or "Rejoindre ma chaîne WhatsApp"

    def clean_couleur(self):
        import re
        c = (self.cleaned_data.get('couleur') or '').strip()
        return c if re.match(r'^#[0-9a-fA-F]{6}$', c) else '#0F6B3E'


def _sections_formset():
    from .models import SectionSite
    return forms.modelformset_factory(
        SectionSite, fields=['titre', 'texte', 'image', 'ordre'], extra=1, can_delete=True, max_num=8,
        labels={'titre': "Titre", 'texte': "Texte", 'image': "Image", 'ordre': "Position"},
        widgets={'texte': forms.Textarea(attrs={'rows': 3}), 'ordre': forms.NumberInput(attrs={'min': 0, 'max': 20})})


@espace
def mon_site(request, v):
    FS = _sections_formset()
    form = SiteForm(request.POST or None, request.FILES or None, instance=v, prefix='site')
    fs = FS(request.POST or None, request.FILES or None, queryset=v.sections.all(), prefix='sec')
    ok = False
    if request.method == 'POST' and form.is_valid() and fs.is_valid():
        form.save()
        for s in fs.save(commit=False):
            s.vendeur = v
            s.save()
        for s in fs.deleted_objects:
            s.delete()
        return redirect(f"{request.path}?ok=1")
    return render(request, 'marche/espace/mon_site.html', {
        'v': v, 'page': 'site', 'form': form, 'fs': fs, 'ok': request.GET.get('ok') == '1',
        'lien': _lien_public(request, v)})

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

from .models import CategorieVendeur, Vendeur

ESSAIS = 5  # tentatives de connexion par 15 minutes (par lien et adresse IP)


def _site():
    return (getattr(settings, 'SITE_URL', '') or 'https://lantantetechnologie.com').rstrip('/')


def _ip(request):
    return (request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR') or '').split(',')[0].strip()


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
        if v.statut != 'valide':
            logout(request)
            return render(request, 'marche/espace/connexion.html', {'v': v, 'erreur': "Espace désactivé."})
        return vue(request, v, *a, **k)
    return w


# ── Connexion, activation, mot de passe oublié ──

def connexion(request, code):
    v = _vendeur(code)
    if request.user.is_authenticated and request.user.pk == v.user_id and v.statut == 'valide':
        return redirect('espace:tableau', code)
    erreur = ''
    if request.method == 'POST':
        cle = f'espace:{code}:{_ip(request)}'
        if cache.get(cle, 0) >= ESSAIS:
            erreur = "Trop de tentatives. Réessayez dans 15 minutes."
        else:
            u = authenticate(request, email=request.POST.get('email', '').strip(), password=request.POST.get('password', ''))
            if u and u.pk == v.user_id and v.statut == 'valide':
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

@espace
def tableau(request, v):
    from Payments.models import Payment
    from Shop.models import Product
    produits = Product.objects.filter(vendeur=v)
    p = produits.aggregate(n=Count('pk'), vues=Sum('vues'), clics=Sum('clics_whatsapp'))
    ventes = Payment.objects.filter(vendeur=v, status='approved')
    total = ventes.aggregate(n=Count('pk'), s=Sum('amount'))
    debut = timezone.localdate() - timedelta(days=13)
    jours = {debut + timedelta(days=i): 0 for i in range(14)}
    for pay in ventes.filter(created_at__date__gte=debut).values('created_at', 'amount'):
        d = timezone.localtime(pay['created_at']).date()
        if d in jours:
            jours[d] += pay['amount']
    haut = max(jours.values()) or 1
    barres = [{'jour': d, 'montant': m, 'h': max(4, int(m * 100 / haut)) if m else 4} for d, m in jours.items()]
    return render(request, 'marche/espace/tableau.html', {
        'v': v, 'page': 'tableau', 'nb_produits': p['n'] or 0, 'vues': p['vues'] or 0, 'clics': p['clics'] or 0,
        'commandes': total['n'] or 0, 'ventes': total['s'] or 0, 'barres': barres,
        'derniers': produits.order_by('-pk')[:5]})


class ProduitForm(forms.ModelForm):
    class Meta:
        from Shop.models import Product
        model = Product
        fields = ['name', 'categorie_vendeur', 'price', 'old_price', 'description', 'image', 'stock', 'is_available',
                  'mode_commande', 'contact_whatsapp', 'livrable']
        labels = {'name': "Nom", 'price': "Prix (CFA)", 'old_price': "Ancien prix (CFA)", 'image': "Photo",
                  'is_available': "En vente", 'contact_whatsapp': "WhatsApp (facultatif)", 'categorie_vendeur': "Catégorie"}
        help_texts = {'contact_whatsapp': "Vide : le WhatsApp de vos paramètres.", 'old_price': "Facultatif.",
                      'mode_commande': '', 'livrable': '', 'categorie_vendeur': ''}
        widgets = {'description': forms.Textarea(attrs={'rows': 4}),
                   'contact_whatsapp': forms.TextInput(attrs={'type': 'tel', 'inputmode': 'tel'})}

    def __init__(self, *a, vendeur=None, **k):
        super().__init__(*a, **k)
        self.fields['categorie_vendeur'].queryset = CategorieVendeur.objects.filter(vendeur=vendeur)
        self.fields['categorie_vendeur'].empty_label = "— Sans catégorie —"

    def clean_contact_whatsapp(self):
        w = self.cleaned_data.get('contact_whatsapp') or ''
        return whatsapp_togo(w) if w.strip() else ''


def _categorie_partenaires():
    from Shop.models import Category
    return Category.objects.get_or_create(slug='boutiques-partenaires', defaults={'name': 'Boutiques partenaires'})[0]


@espace
def produits(request, v):
    from Shop.models import Product
    qs = Product.objects.filter(vendeur=v).select_related('categorie_vendeur').order_by('-pk')
    cat = request.GET.get('categorie')
    if cat and cat.isdigit():
        qs = qs.filter(categorie_vendeur_id=int(cat))
    return render(request, 'marche/espace/produits.html', {
        'v': v, 'page': 'produits', 'produits': qs, 'categories': v.categories.all(), 'cat': cat})


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
    erreur = ''
    if request.method == 'POST':
        if request.POST.get('supprimer'):
            CategorieVendeur.objects.filter(vendeur=v, pk=request.POST['supprimer']).delete()
        else:
            nom = (request.POST.get('nom') or '').strip()[:80]
            if nom:
                CategorieVendeur.objects.get_or_create(vendeur=v, nom=nom)
            else:
                erreur = "Saisissez un nom."
        if not erreur:
            return redirect('espace:categories', v.code)
    cats = v.categories.annotate(n=Count('produits'))
    return render(request, 'marche/espace/categories.html', {'v': v, 'page': 'categories', 'cats': cats, 'erreur': erreur})


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

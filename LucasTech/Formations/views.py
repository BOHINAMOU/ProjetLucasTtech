import urllib.parse

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
from django.http import FileResponse, Http404

from .models import (
    Formation, FormationCategory, Cart, CartItem, Order, OrderItem,
    Registration, user_has_purchased,
)
from core.countries import COUNTRIES

WHATSAPP_NUMBER = "22891973334"


# ──────────────────────────────────────────
# 📚 Liste de toutes les formations publiées
# ──────────────────────────────────────────
CAT_COLORS = ['c-1', 'c-2', 'c-3', 'c-4', 'c-5']


def formations(request):
    categories    = FormationCategory.objects.all()
    category_slug = request.GET.get('category', '').strip()
    nav_categories = [
        (cat, CAT_COLORS[i % len(CAT_COLORS)]) for i, cat in enumerate(categories)
    ]

    qs = Formation.objects.filter(is_published=True).select_related('author', 'category')

    active_category = None
    if category_slug:
        active_category = FormationCategory.objects.filter(slug=category_slug).first()
        if active_category:
            qs = qs.filter(category=active_category)

    search_query = request.GET.get('q', '').strip()
    if search_query:
        qs = qs.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )
    return render(request, 'formations/formations.html', {
        'formations':      qs,
        'categories':      categories,
        'nav_categories':  nav_categories,
        'active_category': active_category,
        'search_query':    search_query,
    })


# ──────────────────────────────────────────
# 🔍 Détail d'une formation + ajout panier
# ──────────────────────────────────────────
def formation_detail(request, pk):
    formation = get_object_or_404(Formation, pk=pk, is_published=True)

    if request.method == 'POST' and formation.formation_type in ('cours', 'numerique'):
        if not request.user.is_authenticated:
            messages.error(request, 'Connectez-vous pour ajouter au panier.')
            return redirect('users:login')

        quantity = 1 if formation.formation_type == 'numerique' else max(1, int(request.POST.get('quantity', 1)))
        cart, _ = Cart.objects.get_or_create(user=request.user)
        item, created = CartItem.objects.get_or_create(cart=cart, formation=formation)
        item.quantity = item.quantity + quantity if not created else quantity
        item.save()

        messages.success(request, f'✓ "{formation.title}" ajouté au panier.')
        if request.POST.get('buy_now'):
            return redirect('formations:checkout')
        return redirect('formations:formation_detail', pk=pk)

    related_formations = Formation.objects.filter(
        is_published=True, level=formation.level
    ).exclude(pk=formation.pk)[:4]

    # Images réelles pour la rangée "Explorer" plutôt que des photos statiques
    from Shop.models import Product
    from Publications.models import Publication
    shop_sample = (
        Product.objects.filter(is_available=True, is_featured=True).exclude(image='').first()
        or Product.objects.filter(is_available=True).exclude(image='').first()
    )
    pub_sample = Publication.objects.filter(is_published=True).exclude(cover_image='').first()

    return render(request, 'formations/formation_detail.html', {
        'formation': formation,
        'related_formations': related_formations,
        'shop_tile_image': shop_sample.image.url if shop_sample else None,
        'pub_tile_image': pub_sample.cover_image.url if pub_sample else None,
        'has_purchased': user_has_purchased(request.user, formation) if formation.formation_type == 'numerique' else False,
    })


# ──────────────────────────────────────────
# 📝 Inscription par formulaire (formations type "inscription")
# ──────────────────────────────────────────
def formation_register(request, pk):
    formation = get_object_or_404(Formation, pk=pk, is_published=True, formation_type='inscription')

    if request.method == 'POST':
        country               = request.POST.get('country', '').strip()
        first_name             = request.POST.get('first_name', '').strip()
        last_name              = request.POST.get('last_name', '').strip()
        whatsapp_country_code  = request.POST.get('whatsapp_country_code', '+228').strip()
        whatsapp_number        = request.POST.get('whatsapp_number', '').strip()
        email                  = request.POST.get('email', '').strip()
        motivation              = request.POST.get('motivation', '').strip()

        errors = []
        if not country: errors.append("Le pays est requis.")
        if not first_name: errors.append("Le prénom est requis.")
        if not last_name: errors.append("Le nom est requis.")
        if not whatsapp_number: errors.append("Le numéro WhatsApp est requis.")
        if not email: errors.append("L'email est requis.")

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'formations/formation_register.html', {
                'formation': formation,
                'form_data': request.POST,
                'countries': COUNTRIES,
            })

        Registration.objects.create(
            formation=formation,
            country=country,
            first_name=first_name,
            last_name=last_name,
            whatsapp_country_code=whatsapp_country_code,
            whatsapp_number=whatsapp_number,
            email=email,
            motivation=motivation,
        )

        # Email de confirmation (ne bloque pas l'inscription si l'envoi échoue)
        try:
            subject = f"Merci pour votre inscription — {formation.title}"
            body = (
                f"Bonjour {first_name},\n\n"
                f"Merci pour votre inscription à la formation « {formation.title} ».\n\n"
            )
            if formation.whatsapp_group_link:
                body += f"Rejoignez dès maintenant le groupe WhatsApp de la formation :\n{formation.whatsapp_group_link}\n\n"
            else:
                body += "Notre équipe vous enverra très bientôt le lien du groupe WhatsApp de la formation.\n\n"
            body += "À très bientôt,\nL'équipe Lantante Technologie"
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
        except Exception:
            pass

        return redirect('formations:formation_register_success', pk=formation.pk)

    return render(request, 'formations/formation_register.html', {
        'formation': formation,
        'countries': COUNTRIES,
    })


def formation_register_success(request, pk):
    formation = get_object_or_404(Formation, pk=pk)
    return render(request, 'formations/formation_register_success.html', {'formation': formation})


# ──────────────────────────────────────────
# ⬇️ Téléchargement d'une formation numérique (après paiement confirmé)
# ──────────────────────────────────────────
@login_required
def formation_download(request, pk):
    formation = get_object_or_404(Formation, pk=pk, formation_type='numerique')
    if not user_has_purchased(request.user, formation):
        messages.error(request, "Vous devez d'abord acheter cette formation pour la télécharger.")
        return redirect('formations:formation_detail', pk=pk)
    if not formation.file:
        raise Http404("Aucun fichier disponible pour cette formation.")
    filename = formation.file.name.rsplit('/', 1)[-1]
    return FileResponse(formation.file.open('rb'), as_attachment=True, filename=filename)


# ──────────────────────────────────────────
# 🛒 Voir le panier
# ──────────────────────────────────────────
@login_required
def cart(request):
    cart_obj, _ = Cart.objects.get_or_create(user=request.user)
    items = cart_obj.items.select_related('formation').all()
    total = cart_obj.total_price()

    whatsapp_url = None
    if items:
        lines = "\n".join(f"- {item.formation.title} (x{item.quantity})" for item in items)
        message = (
            "Bonjour, je souhaite suivre les formations suivantes :\n"
            f"{lines}\n\nJe suis disponible pour suivre ces formations."
        )
        whatsapp_url = f"https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(message)}"

    return render(request, 'formations/cart.html', {
        'cart':  cart_obj,
        'items': items,
        'total': total,
        'whatsapp_url': whatsapp_url,
    })


# ──────────────────────────────────────────
# ❌ Retirer un item du panier
# ──────────────────────────────────────────
@login_required
def cart_remove(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    item.delete()
    messages.success(request, 'Formation retirée du panier.')
    return redirect('formations:cart')


# ──────────────────────────────────────────
# ✅ Passer la commande
# ──────────────────────────────────────────
@login_required
def checkout(request):
    cart_obj, _ = Cart.objects.get_or_create(user=request.user)
    items = cart_obj.items.select_related('formation').all()

    if not items.exists():
        messages.error(request, 'Votre panier est vide.')
        return redirect('formations:cart')

    if request.method == 'POST':
        order = Order.objects.create(
            user=request.user,
            total_price=cart_obj.total_price(),
            status='pending',
        )
        for item in items:
            OrderItem.objects.create(
                order=order,
                formation=item.formation,
                quantity=item.quantity,
                price=item.formation.price,
            )
        items.delete()
        messages.success(request, f'✓ Commande #{order.id} passée avec succès !')
        return redirect('formations:formations')

    return render(request, 'formations/checkout.html', {
        'items': items,
        'total': cart_obj.total_price(),
    })

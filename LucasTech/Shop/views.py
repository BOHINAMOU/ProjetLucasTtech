from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
import urllib.parse

from .models import (
    Product, Category, ShopCart, ShopCartItem,
    ShopOrder, ShopOrderItem, Reservation, Review, Announcement, CollabBanner
)


# ─────────────────────────────
# 🏪 BOUTIQUE
# ─────────────────────────────
CAT_COLORS = ['c-1', 'c-2', 'c-3', 'c-4', 'c-5', 'c-6']


def shop(request):
    categories    = Category.objects.all()
    nav_categories = [
        (cat, CAT_COLORS[i % len(CAT_COLORS)]) for i, cat in enumerate(categories)
    ]
    announcement  = Announcement.objects.filter(is_active=True).first()
    collab_banner = CollabBanner.objects.filter(is_active=True).first()
    category_slug = request.GET.get('category')
    search_query  = request.GET.get('q', '').strip()

    products = Product.objects.filter(is_available=True).select_related('category')

    if category_slug:
        products = products.filter(category__slug=category_slug)

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    active_category = None
    if category_slug:
        active_category = Category.objects.filter(slug=category_slug).first()

    return render(request, 'shop/shop.html', {
        'products':        products,
        'categories':      categories,
        'nav_categories':  nav_categories,
        'announcement':    announcement,
        'collab_banner':   collab_banner,
        'search_query':    search_query,
        'active_category': active_category,
    })


# ─────────────────────────────
# 🔍 DÉTAIL PRODUIT
# ─────────────────────────────
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_available=True)
    reviews = product.reviews.all()
    related_products = Product.objects.filter(
        category=product.category, is_available=True
    ).exclude(pk=product.pk)[:4] if product.category else Product.objects.none()
    # Image de la vignette catégorie dans "Explorer" : la photo du produit
    # lui-même si elle existe, sinon celle d'un produit de la même catégorie
    # — jamais la même image que la vignette "Toute la boutique".
    if product.image:
        category_tile_image = product.image.url
    else:
        sample = related_products.exclude(image='').first()
        category_tile_image = sample.image.url if sample else None
    return render(request, 'shop/product_detail.html', {
        'product': product,
        'reviews': reviews,
        'related_products': related_products,
        'category_tile_image': category_tile_image,
    })


# ─────────────────────────────
# ➕ AJOUTER AU PANIER
# ─────────────────────────────
@login_required
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        quantity = max(1, int(request.POST.get('quantity', 1)))
        cart, _  = ShopCart.objects.get_or_create(user=request.user)
        item, created = ShopCartItem.objects.get_or_create(cart=cart, product=product)
        item.quantity = item.quantity + quantity if not created else quantity
        item.save()
        messages.success(request, f'✓ "{product.name}" ajouté au panier.')
        if request.POST.get('buy_now'):
            return redirect('shop:checkout')
    return redirect('shop:cart')


# ─────────────────────────────
# 🛒 PANIER
# ─────────────────────────────
@login_required
def cart(request):
    cart_obj, _ = ShopCart.objects.get_or_create(user=request.user)
    # ← "cart_items" pour correspondre au template
    cart_items  = cart_obj.items.select_related('product__category').all()
    total_price = cart_obj.total_price()
    in_cart_ids = cart_items.values_list('product_id', flat=True)
    recommended = Product.objects.filter(is_available=True).exclude(pk__in=in_cart_ids).order_by('-is_featured', '-created_at')[:4]
    return render(request, 'shop/cart.html', {
        'cart':        cart_obj,
        'cart_items':  cart_items,   # ← nom correct
        'total_price': total_price,  # ← nom correct
        'recommended': recommended,
    })


# ─────────────────────────────
# ❌ RETIRER DU PANIER
# ─────────────────────────────
@login_required
def cart_remove(request, item_id):
    item = get_object_or_404(ShopCartItem, id=item_id, cart__user=request.user)
    item.delete()
    messages.success(request, 'Article retiré du panier.')
    return redirect('shop:cart')


# ─────────────────────────────
# 📋 CHECKOUT — Récap + choix paiement
# ─────────────────────────────
@login_required
def checkout(request):
    cart_obj, _ = ShopCart.objects.get_or_create(user=request.user)
    cart_items  = cart_obj.items.select_related('product').all()

    if not cart_items.exists():
        messages.error(request, 'Votre panier est vide.')
        return redirect('shop:cart')

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'cash')

        # Créer la commande (statut pending)
        order = ShopOrder.objects.create(
            user=request.user,
            total_price=cart_obj.total_price(),
            status='pending',
            payment_method=payment_method,
        )
        for item in cart_items:
            ShopOrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price,
            )
        # Vider le panier
        cart_items.delete()

        # Rediriger selon le moyen de paiement
        if payment_method == 'whatsapp':
            lines = [f"Commande #{order.receipt_number} — Lantante Technologie"]
            for oi in order.items.all():
                lines.append(f"• {oi.product.name} ×{oi.quantity} = {oi.total_price()} FCFA")
            lines.append(f"\nTotal : {order.total_price} FCFA")
            wa_url = f"https://wa.me/22890000000?text={urllib.parse.quote(chr(10).join(lines))}"
            # Marquer comme payé (WhatsApp = accord direct)
            order.status = 'paid'
            order.save()
            return redirect(wa_url)

        # Autres méthodes → page de paiement
        return redirect('shop:payment', pk=order.pk)

    return render(request, 'shop/checkout.html', {
        'cart_items':  cart_items,
        'total_price': cart_obj.total_price(),
    })


# ─────────────────────────────
# 💳 PAIEMENT
# ─────────────────────────────
@login_required
def payment(request, pk):
    order = get_object_or_404(ShopOrder, pk=pk, user=request.user, status='pending')

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method_choice')

        if payment_method == 'cash':
            name = request.POST.get('cash_delivery_name')
            phone = request.POST.get('cash_delivery_phone')
            cash_message = request.POST.get('cash_delivery_message')

            if not name or not phone:
                messages.error(request, "Le nom et le numéro de téléphone sont obligatoires pour la livraison en espèces.")
                return redirect('shop:payment', pk=order.pk)

            order.status = 'cash_on_delivery'
            order.cash_delivery_name = name
            order.cash_delivery_phone = phone
            order.cash_delivery_message = cash_message
            order.save()

            messages.success(request, "Votre commande en espèces a été enregistrée ! Notre équipe vous contactera bientôt.")
            return redirect('shop:order_history')

        elif payment_method in ('flooz', 'tmoney', 'wave'):
            # Simuler la réception du paiement.
            # En prod : intégrer les API Flooz / TMoney / Wave ici.
            transaction_id = request.POST.get('transaction_id', '').strip()
            if not transaction_id:
                messages.error(request, 'Veuillez entrer votre numéro de transaction.')
                return render(request, 'shop/payment.html', {'order': order})

            order.status = 'paid'
            order.save()
            messages.success(request, f'✓ Paiement confirmé ! Commande #{order.receipt_number}')
            return redirect('shop:order_receipt', pk=order.pk)

        else:
            messages.error(request, "Veuillez sélectionner une méthode de paiement valide.")
            return redirect('shop:payment', pk=order.pk)

    return render(request, 'shop/payment.html', {'order': order})


# ─────────────────────────────
# ✅ CONFIRMATION DE PAIEMENT
# ─────────────────────────────
@login_required
def payment_success(request, pk):
    order = get_object_or_404(ShopOrder, pk=pk, user=request.user)
    return render(request, 'shop/payment_success.html', {'order': order})


# ─────────────────────────────
# 🧾 REÇU (seulement si payé)
# ─────────────────────────────
@login_required
def order_receipt(request, pk):
    order = get_object_or_404(ShopOrder, pk=pk, user=request.user)
    if order.status == 'pending':
        messages.error(request, 'Le paiement n\'a pas encore été confirmé.')
        return redirect('shop:payment', pk=order.pk)
    return render(request, 'shop/order_receipt.html', {'order': order})


# ─────────────────────────────
# 📦 HISTORIQUE
# ─────────────────────────────
@login_required
def order_history(request):
    orders = ShopOrder.objects.filter(user=request.user).prefetch_related('items__product')
    return render(request, 'shop/order_history.html', {'orders': orders})


# ─────────────────────────────
# 📅 RÉSERVATION
# ─────────────────────────────
def reserve(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        Reservation.objects.create(
            user       = request.user if request.user.is_authenticated else None,
            product    = product,
            first_name = request.POST.get('first_name', ''),
            last_name  = request.POST.get('last_name', ''),
            phone      = request.POST.get('phone', ''),
            whatsapp   = request.POST.get('whatsapp', ''),
            email      = request.POST.get('email', ''),
            quantity   = max(1, int(request.POST.get('quantity', 1))),
            notes      = request.POST.get('notes', ''),
        )
        return redirect('shop:reserve_success')
    return render(request, 'shop/reserve.html', {'product': product})


def reserve_success(request):
    return render(request, 'shop/reserve_success.html')


# ─────────────────────────────
# ⭐ AVIS
# ─────────────────────────────
def add_review(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        Review.objects.create(
            product    = product,
            user       = request.user if request.user.is_authenticated else None,
            first_name = request.POST.get('first_name', ''),
            last_name  = request.POST.get('last_name', ''),
            email      = request.POST.get('email', ''),
            rating     = int(request.POST.get('rating', 5)),
            comment    = request.POST.get('comment', ''),
        )
        messages.success(request, 'Merci pour votre avis !')
    return redirect('shop:product_detail', pk=pk)


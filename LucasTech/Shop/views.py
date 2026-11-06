from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Case, When, Value, IntegerField, Count, Min, Max
import urllib.parse
from django.utils.http import url_has_allowed_host_and_scheme

from .models import (
    Product, Category, ShopCart, ShopCartItem,
    ShopOrder, ShopOrderItem, Reservation, Review, Announcement, CollabBanner
)
from core.models import SiteSettings


def _cart_whatsapp_number(cart_items):
    """Numéro WhatsApp à utiliser pour contacter au sujet de ce panier.

    Si tous les articles du panier partagent le même numéro de contact
    spécifique (produit revendu pour le compte d'un tiers), on l'utilise ;
    sinon (panier mixte ou aucun override), on retombe sur le numéro par
    défaut du site.
    """
    overrides = {item.product.contact_whatsapp for item in cart_items if item.product.contact_whatsapp}
    if len(overrides) == 1:
        return overrides.pop()
    return SiteSettings.load().whatsapp_1


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
    collab_banner = None  # bandeau de collaboration retiré de la boutique
    category_slug = request.GET.get('category')
    search_query  = request.GET.get('q', '').strip()

    # Les livres (catégorie « livres ») passent toujours en fin de liste ;
    # le reste garde l'ordre habituel (du plus récent au plus ancien).
    products = (
        Product.objects.filter(is_available=True)
        .select_related('category')
        .annotate(is_book=Case(
            When(category__slug='livres', then=Value(1)),
            default=Value(0), output_field=IntegerField(),
        ))
        .order_by('is_book', '-created_at')
    )

    if category_slug:
        products = products.filter(category__slug=category_slug)

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(short_description__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Filtre par prix (FCFA)
    def _num(v):
        try:
            return int(str(v).replace(' ', '')) if str(v).strip() else None
        except ValueError:
            return None
    price_min = _num(request.GET.get('min', ''))
    price_max = _num(request.GET.get('max', ''))
    if price_min is not None:
        products = products.filter(price__gte=price_min)
    if price_max is not None:
        products = products.filter(price__lte=price_max)

    active_category = None
    if category_slug:
        active_category = Category.objects.filter(slug=category_slug).first()

    available = Product.objects.filter(is_available=True)
    cat_counts = dict(
        available.values_list('category_id').annotate(n=Count('id')).values_list('category_id', 'n')
    )
    categories_with_count = [(cat, cat_counts.get(cat.pk, 0)) for cat in categories]
    bounds = available.aggregate(lo=Min('price'), hi=Max('price'))

    return render(request, 'shop/shop.html', {
        'categories_with_count': categories_with_count,
        'total_count':     available.count(),
        'price_min':       price_min,
        'price_max':       price_max,
        'price_lo':        int(bounds['lo'] or 0),
        'price_hi':        int(bounds['hi'] or 0),
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
    ratings = [r.rating for r in reviews]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None
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
        'avg_rating': avg_rating,
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
        messages.success(request, f'« {product.name} » a été ajouté au panier.')
        if request.POST.get('buy_now'):
            return redirect('shop:checkout')
        # Depuis la boutique ou la fiche produit : on reste sur la page, un message confirme l'ajout
        next_url = request.POST.get('next', '')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return redirect(next_url)
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
            wa_number = _cart_whatsapp_number(order.items.select_related('product').all())
            lines = [f"Commande #{order.receipt_number} — Lantante Technologie"]
            for oi in order.items.all():
                lines.append(f"• {oi.product.name} ×{oi.quantity} = {oi.total_price()} FCFA")
            lines.append(f"\nTotal : {order.total_price} FCFA")
            wa_url = f"https://wa.me/{wa_number}?text={urllib.parse.quote(chr(10).join(lines))}"
            # Marquer comme payé (WhatsApp = accord direct)
            order.status = 'paid'
            order.save()
            return redirect(wa_url)

        # Autres méthodes → page de paiement
        return redirect('shop:payment', pk=order.pk)

    return render(request, 'shop/checkout.html', {
        'cart_items':      cart_items,
        'total_price':     cart_obj.total_price(),
        'whatsapp_number': _cart_whatsapp_number(cart_items),
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

        elif payment_method == 'fedapay':
            # Mobile Money / carte : le paiement n'est validé qu'après vérification chez FedaPay.
            return redirect('payments:checkout', kind='boutique', pk=order.pk)

        else:
            messages.error(request, "Veuillez sélectionner une méthode de paiement valide.")
            return redirect('shop:payment', pk=order.pk)

    return render(request, 'shop/payment.html', {
        'order': order,
        'whatsapp_number': _cart_whatsapp_number(order.items.select_related('product').all()),
    })


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


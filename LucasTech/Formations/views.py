from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Formation, Cart, CartItem, Order, OrderItem


# ──────────────────────────────────────────
# 📚 Liste de toutes les formations publiées
# ──────────────────────────────────────────
def formations(request):
    qs = Formation.objects.filter(is_published=True).select_related('author')
    search_query = request.GET.get('q', '').strip()
    if search_query:
        qs = qs.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )
    return render(request, 'formations/formations.html', {
        'formations': qs,
        'search_query': search_query,
    })


# ──────────────────────────────────────────
# 🔍 Détail d'une formation + ajout panier
# ──────────────────────────────────────────
def formation_detail(request, pk):
    formation = get_object_or_404(Formation, pk=pk, is_published=True)

    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, 'Connectez-vous pour ajouter au panier.')
            return redirect('users:login')  # ✅ CORRECTION ICI

        quantity = max(1, int(request.POST.get('quantity', 1)))
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

    return render(request, 'formations/formation_detail.html', {
        'formation': formation,
        'related_formations': related_formations,
    })


# ──────────────────────────────────────────
# 🛒 Voir le panier
# ──────────────────────────────────────────
@login_required
def cart(request):
    cart_obj, _ = Cart.objects.get_or_create(user=request.user)
    items = cart_obj.items.select_related('formation').all()
    total = cart_obj.total_price()
    return render(request, 'formations/cart.html', {
        'cart':  cart_obj,
        'items': items,
        'total': total,
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
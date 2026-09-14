

# Create your views here.
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from .models import Service, ServiceCategory, ServiceContact
# ─────────────────────────────
# 🏠 LISTE DES SERVICES
# ─────────────────────────────
def services(request):
    categories    = ServiceCategory.objects.all()
    category_slug = request.GET.get('category', '').strip()
    search_query  = request.GET.get('q', '').strip()

    qs = Service.objects.filter(is_active=True).select_related('category', 'admin')

    # Filtre catégorie
    active_category = None
    if category_slug:
        active_category = ServiceCategory.objects.filter(slug=category_slug).first()
        if active_category:
            qs = qs.filter(category=active_category)

    # Recherche
    if search_query:
        words = search_query.split()
        query = Q()
        for word in words:
            query &= (
                Q(title__icontains=word) |
                Q(description__icontains=word)
            )
        qs = qs.filter(query)

    # Par défaut (pas de filtre ni de recherche) : on regroupe par catégorie
    # pour montrer d'un coup d'œil tout ce que nous faisons.
    grouped_services = None
    if not active_category and not search_query:
        grouped_services = []
        for cat in categories:
            cat_services = qs.filter(category=cat)
            if cat_services.exists():
                grouped_services.append((cat, cat_services))

    return render(request, 'services/services.html', {
        'services':         qs,
        'categories':       categories,
        'active_category':  active_category,
        'search_query':     search_query,
        'grouped_services': grouped_services,
    })


# ─────────────────────────────
# 🔍 DÉTAIL SERVICE
# ─────────────────────────────
def service_detail(request, pk):
    service = get_object_or_404(Service, pk=pk, is_active=True)

    if request.method == 'POST':
        name    = request.POST.get('name', '').strip()
        phone   = request.POST.get('phone', '').strip()
        message = request.POST.get('message', '').strip()

        if name and phone and message:
            ServiceContact.objects.create(
                service = service,
                user    = request.user if request.user.is_authenticated else None,
                name    = name,
                phone   = phone,
                message = message,
            )
            messages.success(request, '✓ Votre message a bien été envoyé ! Nous vous répondrons rapidement.')
            return redirect('services:service_detail', pk=pk)
        else:
            messages.error(request, 'Veuillez remplir tous les champs.')

    related_services = Service.objects.filter(
        is_active=True, category=service.category
    ).exclude(pk=service.pk)[:4] if service.category else Service.objects.none()

    return render(request, 'services/service_detail.html', {
        'service': service,
        'related_services': related_services,
    })
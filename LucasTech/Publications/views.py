
# Create your views here.
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Publication, PublicationCategory


# ─────────────────────────────
# 📰 LISTE DES PUBLICATIONS
# ─────────────────────────────
def publications(request):
    categories    = PublicationCategory.objects.all()
    category_slug = request.GET.get('category', '').strip()
    search_query  = request.GET.get('q', '').strip()

    qs = Publication.objects.filter(is_published=True).select_related('author', 'category')

    active_category = None
    if category_slug:
        active_category = PublicationCategory.objects.filter(slug=category_slug).first()
        if active_category:
            qs = qs.filter(category=active_category)

    if search_query:
        words = search_query.split()
        query = Q()
        for word in words:
            query &= (Q(title__icontains=word) | Q(content__icontains=word))
        qs = qs.filter(query)

    # À la une (featured) séparés pour le hero
    featured = qs.filter(is_featured=True).first()

    return render(request, 'publications/publications.html', {
        'publications':    qs,
        'categories':      categories,
        'active_category': active_category,
        'search_query':    search_query,
        'featured':        featured,
    })


# ─────────────────────────────
# 📄 DÉTAIL PUBLICATION
# ─────────────────────────────
def publication_detail(request, slug):
    publication = get_object_or_404(Publication, slug=slug, is_published=True)

    # Incrémenter les vues
    Publication.objects.filter(pk=publication.pk).update(views_count=publication.views_count + 1)

    # Articles similaires (même catégorie, pas le même)
    related = Publication.objects.filter(
        is_published=True
    ).exclude(pk=publication.pk)

    if publication.category:
        related = related.filter(category=publication.category)

    related = related[:4]

    return render(request, 'publications/publication_detail.html', {
        'publication': publication,
        'related':     related,
    })
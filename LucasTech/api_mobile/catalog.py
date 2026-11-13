"""Catalogue de l'application : boutique, formations, services, actualités, partenaires, événements,
carrousel d'accueil et version de l'application. Tout se consulte DANS l'application (détails complets,
galeries, prix barrés) ; l'achat ouvre la page de paiement du site dans l'application (voir web_login)."""
import html
import json
import os
import random
import re

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .thumbs import thumb_url
from .utils import absolute, dt, error, media, money

PAGE_SIZE = 20


# ─────────────────────────────
# Outils
# ─────────────────────────────
def text(value):
    """HTML (CKEditor) -> texte lisible avec paragraphes."""
    if not value:
        return ''
    s = re.sub(r'(?i)<\s*br\s*/?>', '\n', value)
    s = re.sub(r'(?i)</\s*(p|div|li|h[1-6]|tr)\s*>', '\n\n', s)
    s = re.sub(r'(?i)<\s*li[^>]*>', '• ', s)
    s = html.unescape(strip_tags(s))
    s = re.sub(r'[ \t\xa0]+', ' ', s)
    s = re.sub(r'\n\s*\n\s*(\n\s*)+', '\n\n', s)
    return '\n'.join(line.strip() for line in s.strip().splitlines())


def short(value, n=140):
    return Truncator(' '.join(text(value).split())).chars(n)


def vignette(request, field):
    return absolute(request, thumb_url(field)) if field else None


def cat(c):
    return {'id': c.pk, 'nom': c.name, 'slug': getattr(c, 'slug', '')} if c else None


def discount(price, old):
    if old and price is not None and old > price:
        return round((old - price) / old * 100)
    return 0


def paginated(request, qs, serialize):
    """Avec ?page=N : {resultats, page, pages, total, suivant}. Sans : liste simple (compatibilité 1.0)."""
    page = request.GET.get('page')
    if not page:
        return Response([serialize(o) for o in qs[:200]])
    try:
        n = max(1, int(page))
    except ValueError:
        n = 1
    pager = Paginator(qs, PAGE_SIZE)
    try:
        p = pager.page(n)
        rows = [serialize(o) for o in p.object_list]
    except EmptyPage:
        rows = []
    return Response({'resultats': rows, 'page': n, 'pages': pager.num_pages, 'total': pager.count,
                     'suivant': n < pager.num_pages})


def search(qs, request, *fields):
    q = (request.GET.get('q') or '').strip()
    if q:
        cond = Q()
        for f in fields:
            cond |= Q(**{f'{f}__icontains': q})
        qs = qs.filter(cond)
    return qs


def by_category(qs, request, field='category'):
    c = (request.GET.get('categorie') or '').strip()
    if c:
        qs = qs.filter(**{f'{field}__pk': int(c)}) if c.isdigit() else qs.filter(**{f'{field}__slug': c})
    return qs


def public_cache(seconds=60):
    """Listes publiques : petit cache côté appli / proxy (mêmes données pour tout le monde)."""
    def deco(view):
        def wrapped(request, *a, **kw):
            resp = view(request, *a, **kw)
            if getattr(resp, 'status_code', 500) == 200 and not resp.has_header('Cache-Control'):
                resp['Cache-Control'] = f'public, max-age={seconds}'
            return resp
        wrapped.__name__ = view.__name__
        wrapped.__doc__ = view.__doc__
        return wrapped
    return deco


def paiement(request, path):
    return absolute(request, path)


# ─────────────────────────────
# Boutique
# ─────────────────────────────
def product_item(request, p):
    return {
        'id': p.pk, 'titre': p.name, 'prix': money(p.price), 'prix_barre': money(p.old_price) if p.is_on_sale else None,
        'remise': p.discount_percent, 'image': media(request, p.image), 'image_vignette': vignette(request, p.image),
        'resume': p.card_description, 'categorie': cat(p.category), 'en_stock': p.stock > 0,
        'url_site': absolute(request, reverse('shop:product_detail', args=[p.pk])),
    }


def _products():
    from Shop.models import Product
    return Product.objects.filter(is_available=True).select_related('category').order_by('-is_featured', '-created_at')


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache()
def produits(request):
    qs = by_category(search(_products(), request, 'name', 'short_description', 'description'), request)
    return paginated(request, qs, lambda p: product_item(request, p))


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache()
def produit(request, pk):
    p = _products().prefetch_related('images').filter(pk=pk).first()
    if not p:
        return error("Produit introuvable.", 404, code='introuvable')
    data = product_item(request, p)
    gallery = [p.image] + [i.image for i in p.images.all()]
    data.update({
        'images': [media(request, f) for f in gallery if f],
        'images_vignettes': [vignette(request, f) for f in gallery if f],
        'description': text(p.description), 'stock': p.stock,
        'prix_gros': money(p.bulk_price), 'quantite_min_gros': p.bulk_min_qty if p.bulk_price else None,
        'video': media(request, p.video),
        'whatsapp': p.contact_whatsapp or '',
        'url_paiement': paiement(request, reverse('payments:checkout', args=['produit', p.pk])) if p.stock > 0 else None,
    })
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(300)
def boutique_categories(request):
    from Shop.models import Category
    return Response([cat(c) for c in Category.objects.filter(products__is_available=True).distinct()])


# ─────────────────────────────
# Formations
# ─────────────────────────────
def formation_item(request, f):
    return {
        'id': f.pk, 'titre': f.title, 'prix': money(f.price), 'prix_barre': money(f.old_price) if f.is_on_sale else None,
        'remise': f.discount_percent, 'image': media(request, f.image), 'image_vignette': vignette(request, f.image),
        'resume': short(f.description), 'categorie': cat(f.category), 'niveau': f.get_level_display(),
        'duree': f.duration, 'type': f.formation_type, 'pdf_inclus': bool(f.file),
        'url_site': absolute(request, f.get_absolute_url()),
    }


def _formations():
    from Formations.models import Formation
    return Formation.objects.filter(is_published=True).select_related('category').order_by('-is_featured', '-created_at')


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache()
def formations(request):
    qs = by_category(search(_formations(), request, 'title', 'description'), request)
    return paginated(request, qs, lambda f: formation_item(request, f))


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache()
def formation(request, pk):
    f = _formations().filter(pk=pk).first()
    if not f:
        return error("Formation introuvable.", 404, code='introuvable')
    data = formation_item(request, f)
    data.update({
        'images': [media(request, f.image)] if f.image else [], 'description': text(f.description),
        'ce_que_vous_apprendrez': f.learn_points(), 'inscrits': f.students_count,
        'url_paiement': paiement(request, reverse('payments:checkout', args=['formation', f.pk])) if f.can_pay_online else None,
        'url_inscription': absolute(request, reverse('formations:formation_register', args=[f.pk]))
        if f.formation_type == 'inscription' else None,
    })
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(300)
def formation_categories(request):
    from Formations.models import FormationCategory
    return Response([cat(c) for c in FormationCategory.objects.filter(formations__is_published=True).distinct()])


# ─────────────────────────────
# Services
# ─────────────────────────────
def service_item(request, s):
    return {
        'id': s.pk, 'titre': s.title, 'prix': s.price, 'prix_a_partir_de': money(s.price_from),
        'image': media(request, s.image), 'image_vignette': vignette(request, s.image), 'icone': s.icon_class, 'resume': short(s.description), 'categorie': cat(s.category),
        'url_site': absolute(request, s.get_absolute_url()),
    }


def _services():
    from Services.models import Service
    return Service.objects.filter(is_active=True).select_related('category').order_by('-is_featured', '-created_at')


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache()
def services(request):
    qs = by_category(search(_services(), request, 'title', 'description'), request)
    return paginated(request, qs, lambda s: service_item(request, s))


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache()
def service(request, pk):
    s = _services().filter(pk=pk).first()
    if not s:
        return error("Service introuvable.", 404, code='introuvable')
    data = service_item(request, s)
    data.update({
        'images': [media(request, s.image)] if s.image else [], 'description': text(s.description),
        'video': media(request, s.video), 'whatsapp': s.whatsapp or '', 'telephone': s.phone or '',
        'url_paiement': paiement(request, reverse('payments:checkout', args=['service', s.pk])) if s.price else None,
    })
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(300)
def service_categories(request):
    from Services.models import ServiceCategory
    return Response([cat(c) for c in ServiceCategory.objects.filter(services__is_active=True).distinct()])


# ─────────────────────────────
# Actualités
# ─────────────────────────────
def publication_item(request, p):
    return {
        'id': p.pk, 'slug': p.slug, 'titre': p.title, 'image': media(request, p.cover_image),
        'image_vignette': vignette(request, p.cover_image), 'resume': short(p.content, 180),
        'categorie': cat(p.category), 'date': dt(p.created_at), 'a_la_une': p.is_featured,
        'type': p.publication_type,
        'url_site': absolute(request, reverse('publications:publication_detail', args=[p.slug])),
    }


def _publications():
    from Publications.models import Publication
    return Publication.objects.filter(is_published=True).select_related('category').order_by('-created_at')


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache()
def publications(request):
    qs = by_category(search(_publications(), request, 'title', 'content'), request)
    return paginated(request, qs, lambda p: publication_item(request, p))


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache()
def publication(request, pk):
    p = _publications().filter(pk=pk).first()
    if not p:
        return error("Article introuvable.", 404, code='introuvable')
    data = publication_item(request, p)
    # Galerie : la couverture + les images insérées dans l'article (éditeur du site).
    imgs = [media(request, p.cover_image)] if p.cover_image else []
    for src in re.findall(r'<img[^>]+src=["']([^"']+)["']', p.content or '', re.I):
        url = src if src.startswith('http') else absolute(request, src)
        if url and url not in imgs:
            imgs.append(url)
    data.update({
        'images': imgs, 'contenu': text(p.content),
        'video': media(request, getattr(p, 'cover_video', None)),
        'document': media(request, getattr(p, 'document', None)),
        'texte_document': getattr(p, 'document_label', '') or '',
        'evenement_date': dt(p.event_date), 'evenement_lieu': p.event_location,
    })
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(300)
def publication_categories(request):
    from Publications.models import PublicationCategory
    return Response([cat(c) for c in PublicationCategory.objects.filter(publications__is_published=True).distinct()])


# ─────────────────────────────
# Partenaires
# ─────────────────────────────
def partner_item(request, p, full=False):
    data = {
        'id': p.pk, 'nom': p.name, 'titre': p.name, 'image': media(request, p.logo),
        'image_vignette': vignette(request, p.logo), 'categorie': cat(p.category), 'pays': p.country,
        'domaine': p.domain, 'resume': short(p.description),
    }
    if full:
        data.update({'description': text(p.description), 'realisations': text(p.achievements),
                     'site_web': p.website or '', 'email': p.email, 'telephone': p.phone, 'whatsapp': p.whatsapp,
                     'images': [media(request, p.logo)] if p.logo else []})
    return data


def _partners():
    from core.models import Partner
    return Partner.objects.filter(is_active=True).select_related('category')


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(300)
def partenaires(request):
    qs = by_category(search(_partners(), request, 'name', 'domain', 'description'), request)
    return paginated(request, qs, lambda p: partner_item(request, p))


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(300)
def partenaire(request, pk):
    p = _partners().filter(pk=pk).first()
    if not p:
        return error("Partenaire introuvable.", 404, code='introuvable')
    return Response(partner_item(request, p, full=True))


# ─────────────────────────────
# Événements
# ─────────────────────────────
def event_item(request, e):
    return {
        'id': e.pk, 'slug': e.slug, 'titre': e.title, 'date': dt(e.starts_at), 'fin': dt(e.ends_at),
        'lieu': e.location, 'image': media(request, e.cover), 'image_vignette': vignette(request, e.cover),
        'prix_min': e.min_price, 'resume': short(e.description), 'passe': e.is_past,
        'url_site': absolute(request, e.get_absolute_url()),
    }


def _events(all_events=False):
    from Events.models import Event
    qs = Event.objects.filter(is_published=True).prefetch_related('ticket_types')
    if not all_events:
        now = timezone.now()
        qs = qs.filter(Q(ends_at__gte=now) | Q(ends_at__isnull=True, starts_at__gte=now))
    return qs.order_by('starts_at')


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache()
def evenements(request):
    qs = search(_events(request.GET.get('passes') == '1'), request, 'title', 'location', 'description')
    return paginated(request, qs, lambda e: event_item(request, e))


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(30)
def evenement(request, pk):
    e = _events(all_events=True).filter(pk=pk).first()
    if not e:
        return error("Événement introuvable.", 404, code='introuvable')
    data = event_item(request, e)
    data.update({
        'images': [media(request, e.cover)] if e.cover else [], 'description': text(e.description),
        'carte': e.map_url,
        'tickets': [{'id': t.pk, 'nom': t.name, 'detail': t.description, 'prix': t.price, 'restant': t.remaining,
                     'max_par_commande': t.max_per_order, 'image': media(request, t.cover)}
                    for t in e.ticket_types.all()],
        # Achat des tickets : page de l'événement du site, ouverte dans l'application (WebView connectée).
        'url_paiement': absolute(request, e.get_absolute_url()) if not e.is_past else None,
    })
    return Response(data)


# ─────────────────────────────
# Carrousel d'accueil
# ─────────────────────────────
TYPE_LABELS = {'concours': 'Concours', 'evenement': 'Événement', 'formation': 'Formation', 'produit': 'Boutique',
               'service': 'Service', 'publication': 'Actualité', 'partenaire': 'Partenaire'}


def carousel_items(request, per_type=3):
    from concours.models import Contest
    items = []

    def add(kind, obj_id, titre, image_field, sous_titre='', prix=None, slug=None):
        if not image_field:
            return
        items.append({'type': kind, 'type_libelle': TYPE_LABELS[kind], 'id': obj_id, 'slug': slug, 'titre': titre,
                      'sous_titre': sous_titre, 'prix': prix, 'image': media(request, image_field),
                      'image_vignette': absolute(request, thumb_url(image_field, 800))})

    for c in Contest.objects.published().exclude(cover='').order_by('?')[:per_type]:
        add('concours', c.pk, f"{c.acronym} — {c.name}", c.cover or c.logo, 'Épreuves et corrigés', slug=c.slug)
    for e in _events()[:per_type]:
        add('evenement', e.pk, e.title, e.cover, e.location, e.min_price)
    for f in _formations().exclude(image='')[:per_type]:
        add('formation', f.pk, f.title, f.image, f.get_level_display(), money(f.price))
    for p in _products().exclude(image='').exclude(image__isnull=True)[:per_type]:
        add('produit', p.pk, p.name, p.image, p.category.name if p.category else '', money(p.price))
    for s in _services().exclude(image='').exclude(image__isnull=True)[:per_type]:
        add('service', s.pk, s.title, s.image, s.category.name if s.category else '', s.price)
    for p in _publications().exclude(cover_image='').exclude(cover_image__isnull=True)[:per_type]:
        add('publication', p.pk, p.title, p.cover_image, timezone.localtime(p.created_at).strftime('%d/%m/%Y'))
    for p in _partners().order_by('?')[:2]:
        add('partenaire', p.pk, p.name, p.logo, p.domain)
    random.shuffle(items)
    return items


@api_view(['GET'])
@permission_classes([AllowAny])
def carrousel(request):
    return Response(carousel_items(request))


# ─────────────────────────────
# Version de l'application (mise à jour intégrée, version distribuée par le site)
# ─────────────────────────────
VERSION_FILE = 'app/version.json'


@api_view(['GET'])
@permission_classes([AllowAny])
def version(request):
    path = os.path.join(settings.MEDIA_ROOT, VERSION_FILE)
    try:
        with open(path, 'rb') as fh:
            data = json.loads(fh.read().decode('utf-8', 'replace'))
    except (OSError, ValueError):
        return error("Aucune version publiée.", 404, code='indisponible')
    out = {'version': str(data.get('version', '')), 'build': int(data.get('build') or 0),
           'url_apk': absolute(request, data.get('url_apk') or settings.MEDIA_URL
                               + (f"app/Lantante-{data.get('version')}.apk" if data.get('version') else 'app/Lantante.apk')),
           'taille': int(data.get('taille') or 0), 'notes': str(data.get('notes') or ''),
           'obligatoire': bool(data.get('obligatoire'))}
    resp = Response(out)
    resp['Cache-Control'] = 'no-cache'
    return resp


# ─────────────────────────────
# Annonces des concours (actualités de la catégorie « Concours » ou qui citent le concours)
# ─────────────────────────────
@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache()
def annonces(request, slug=None):
    qs = _publications()
    if slug:
        from concours.models import Contest
        c = Contest.objects.published().filter(slug=slug).first()
        if not c:
            return error("Concours introuvable.", 404, code='introuvable')
        sigle = c.short_acronym if hasattr(c, 'short_acronym') else c.acronym
        qs = qs.filter(Q(title__icontains=sigle) | Q(title__icontains=c.name) | Q(content__icontains=c.name)
                       | (Q(category__slug='concours') & Q(content__icontains=sigle)))
    else:
        qs = qs.filter(Q(category__slug='concours') | Q(category__name__icontains='concours'))
    qs = search(qs, request, 'title', 'content')
    return paginated(request, qs, lambda p: publication_item(request, p))


# ─────────────────────────────
# Téléchargements hors connexion gardés côté serveur (récupération après réinstallation)
# ─────────────────────────────
@api_view(['GET', 'POST', 'DELETE'])
def telechargements(request):
    from abonnements.access import can_view_paper
    from concours.models import Correction, ExamPaper
    from .models import OfflineDocument
    if request.method in ('POST', 'DELETE'):
        kind = str(request.data.get('type') or '')
        try:
            doc_id = int(request.data.get('id') or 0)
        except (TypeError, ValueError):
            doc_id = 0
        if kind not in ('epreuve', 'corrige') or not doc_id:
            return error("Document inconnu.", 400, code='donnees_invalides')
        if request.method == 'DELETE':
            OfflineDocument.objects.filter(user=request.user, kind=kind, doc_id=doc_id).delete()
        else:
            OfflineDocument.objects.update_or_create(
                user=request.user, kind=kind, doc_id=doc_id,
                defaults={'titre': str(request.data.get('titre') or '')[:200],
                          'sous_titre': str(request.data.get('sous_titre') or '')[:200]})
    out = []
    for o in OfflineDocument.objects.filter(user=request.user):
        if o.kind == 'epreuve':
            paper = ExamPaper.objects.select_related('session__contest').filter(pk=o.doc_id).first()
        else:
            corr = Correction.objects.select_related('paper__session__contest').filter(pk=o.doc_id).first()
            paper = corr.paper if corr else None
        ok = bool(paper) and can_view_paper(request.user, paper)
        out.append({'type': o.kind, 'id': o.doc_id, 'titre': o.titre, 'sous_titre': o.sous_titre,
                    'accessible': ok, 'date': dt(o.created_at)})
    return Response(out)

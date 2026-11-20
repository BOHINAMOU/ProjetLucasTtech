"""Mini-site d'un vendeur (/vendeur/<adresse>/) : Accueil, Produits, Détail, Contact. Aucun habillage Lantante."""
import re
from urllib.parse import quote

from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .models import Vendeur

COULEUR = re.compile(r'^#[0-9a-fA-F]{6}$')


def _chiffres(n):
    return ''.join(c for c in (n or '') if c.isdigit())


def _contexte(v, page):
    couleur = v.couleur if COULEUR.match(v.couleur or '') else '#0F6B3E'
    wa = _chiffres(v.whatsapp)
    return {'v': v, 'page': page, 'couleur': couleur,
            'wa': f"https://wa.me/{wa}?text={quote(f'Bonjour {v.boutique}, je vous contacte depuis votre site.')}" if wa else ''}


def _vendeur(request, slug):
    v = get_object_or_404(Vendeur, slug=slug)
    if not v.actif:
        return v, render(request, 'minisite/indisponible.html', _contexte(v, ''), status=503)
    return v, None


def _produits(v):
    from Shop.models import Product
    return Product.en_vente().filter(vendeur=v).order_by('-is_featured', '-pk')


@xframe_options_sameorigin
def accueil(request, slug):
    v, ferme = _vendeur(request, slug)
    if ferme:
        return ferme
    ctx = _contexte(v, 'accueil')
    ctx.update(sections=v.sections.all(), produits=_produits(v)[:8])
    return render(request, 'minisite/accueil.html', ctx)


@xframe_options_sameorigin
def produits(request, slug):
    v, ferme = _vendeur(request, slug)
    if ferme:
        return ferme
    qs = _produits(v)
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(short_description__icontains=q) | Q(description__icontains=q))
    ctx = _contexte(v, 'produits')
    ctx.update(produits=qs, q=q)
    return render(request, 'minisite/produits.html', ctx)


@xframe_options_sameorigin
def produit(request, slug, pk):
    v, ferme = _vendeur(request, slug)
    if ferme:
        return ferme
    p = get_object_or_404(_produits(v), pk=pk)
    num = _chiffres(p.contact_whatsapp) or _chiffres(v.whatsapp)
    lien = request.build_absolute_uri()
    txt = f"Bonjour {v.boutique}, je souhaite commander « {p.name} » ({int(p.price):,} CFA).\n{lien}".replace(',', ' ')
    ctx = _contexte(v, 'produits')
    ctx.update(p=p, images=list(p.images.all()), commande=f"https://wa.me/{num}?text={quote(txt)}" if num else '',
               autres=_produits(v).exclude(pk=p.pk)[:4])
    return render(request, 'minisite/produit.html', ctx)


@xframe_options_sameorigin
def contact(request, slug):
    v, ferme = _vendeur(request, slug)
    if ferme:
        return ferme
    ctx = _contexte(v, 'contact')
    ctx.update(tel=_chiffres(v.telephone) or _chiffres(v.whatsapp))
    if v.latitude and v.longitude:
        la, lo = float(v.latitude), float(v.longitude)
        ctx['carte'] = (f"https://www.openstreetmap.org/export/embed.html?bbox={lo - .01:.5f},{la - .006:.5f},{lo + .01:.5f},{la + .006:.5f}"
                        f"&layer=mapnik&marker={la:.6f},{lo:.6f}")
    return render(request, 'minisite/contact.html', ctx)

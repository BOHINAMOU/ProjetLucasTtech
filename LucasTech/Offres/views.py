"""Site : liste et détail des offres ; on contacte directement le recruteur."""
from django.shortcuts import get_object_or_404, render

from .api import _wa, actives
from .models import OffreEmploi


def liste(request):
    return render(request, 'offres/liste.html', {'offres': actives()})


def detail(request, pk):
    o = get_object_or_404(actives(), pk=pk)
    from django.db.models import F
    OffreEmploi.objects.filter(pk=pk).update(vues=F('vues') + 1)
    wa = _wa(o.whatsapp)
    from .api import contacts
    return render(request, 'offres/detail.html', {'o': o, 'wa': wa, 'contacts': contacts(o),
                                                  'texte': mise_en_forme(o.description)})


def mise_en_forme(texte):
    """Description : un bloc = un titre court suivi de puces « • » ; le reste en paragraphes (texte échappé)."""
    from django.utils.html import escape
    from django.utils.safestring import mark_safe
    html = []
    for bloc in (texte or '').replace('\r', '').split('\n\n'):
        lignes = [l.strip() for l in bloc.split('\n') if l.strip()]
        if not lignes:
            continue
        puces = [l for l in lignes if l.startswith('•')]
        if puces and not lignes[0].startswith('•') and len(lignes[0]) <= 60 and len(puces) == len(lignes) - 1:
            html.append(f'<h3>{escape(lignes[0])}</h3>')
            lignes = lignes[1:]
        if lignes and all(l.startswith('•') for l in lignes):
            html.append('<ul>' + ''.join(f'<li>{escape(l.lstrip("• ").strip())}</li>' for l in lignes) + '</ul>')
        elif lignes:
            html.append('<p>' + '<br>'.join(escape(l) for l in lignes) + '</p>')
    return mark_safe(''.join(html))

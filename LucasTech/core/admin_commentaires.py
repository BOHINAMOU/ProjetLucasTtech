"""Commentaires : vraie boîte de réception (Sans réponse / Tous / Masqués), lecture, réponse et masquage."""
from django.contrib import admin as _admin
from django.contrib import messages
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone


def _masquer_email(e):
    if not e or '@' not in e:
        return ''
    nom, dom = e.split('@', 1)
    return (nom[:2] + '•••') + '@' + dom


def boite(request):
    from Publications.models import PublicationComment as C
    ma = _admin.site._registry.get(C)
    if not ma or not ma.has_view_or_change_permission(request):
        raise Http404
    peut_modifier = ma.has_change_permission(request)
    ici = reverse('admin_section', args=['commentaires'])
    onglet = request.GET.get('o', 'attente')

    if request.method == 'POST' and peut_modifier:
        c = C.objects.filter(pk=request.POST.get('c')).select_related('publication', 'user').first()
        if not c:
            raise Http404
        action = request.POST.get('action')
        if action == 'masquer':
            c.is_hidden = not c.is_hidden
            c.save(update_fields=['is_hidden'])
            messages.success(request, "Commentaire masqué." if c.is_hidden else "Commentaire de nouveau visible.")
        elif action == 'repondre':
            texte = (request.POST.get('reponse') or '').strip()
            if not texte:
                messages.error(request, "Écrivez une réponse.")
            else:
                c.reponse, c.repondu_le, c.is_read = texte, timezone.now(), True
                c.save(update_fields=['reponse', 'repondu_le', 'is_read'])
                dest = c.email_auteur()
                if request.POST.get('email') and dest:
                    try:
                        send_mail(f"Réponse à votre commentaire — {c.publication.title[:60]}",
                                  f"Bonjour {c.name},\n\nVotre commentaire :\n« {c.text} »\n\nNotre réponse :\n{c.reponse}\n\n"
                                  f"L'équipe Lantante Technologie", None, [dest])
                        messages.success(request, "Réponse enregistrée et envoyée par e-mail.")
                    except Exception:
                        messages.warning(request, "Réponse enregistrée, mais l'e-mail n'a pas pu partir.")
                else:
                    messages.success(request, "Réponse enregistrée.")
        return redirect(f"{ici}?o={onglet}&c={c.pk}")

    base = C.objects.select_related('publication', 'user')
    filtres = {'attente': base.filter(is_hidden=False, reponse=''), 'tous': base.all(), 'masques': base.filter(is_hidden=True)}
    if onglet not in filtres:
        onglet = 'attente'
    liste = list(filtres[onglet].order_by('-created_at')[:200])
    sel = None
    if request.GET.get('c'):
        sel = base.filter(pk=request.GET['c']).first()
    if sel is None and liste:
        sel = liste[0]
    if sel and not sel.is_read and peut_modifier:
        sel.is_read = True
        sel.save(update_fields=['is_read'])
    ctx = dict(_admin.site.each_context(request), title="Commentaires", onglet=onglet, liste=liste, sel=sel,
               peut_modifier=peut_modifier,
               onglets=[('attente', "Sans réponse", filtres['attente'].count()), ('tous', "Tous", filtres['tous'].count()),
                        ('masques', "Masqués", filtres['masques'].count())],
               email_masque=_masquer_email(sel.email_auteur()) if sel else '',
               lien_pub=reverse('publications:publication_detail', args=[sel.publication.slug]) if sel and sel.publication.slug else '',
               messages_rapides=reverse('admin:Publications_quickmessage_changelist'))
    return render(request, 'admin/commentaires.html', ctx)

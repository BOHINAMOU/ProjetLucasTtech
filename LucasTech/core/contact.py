"""Page « Nous contacter » : choix du service, message prêt, envoi sur WhatsApp (numéro principal)."""
from django.shortcuts import render


def contact(request):
    from Services.models import Service
    services = list(Service.objects.filter(is_active=True).select_related('category')
                    .order_by('category__order', 'title').values_list('title', flat=True))
    autres = [t for t in services if t.lower().startswith('autres services')]
    services = [t for t in services if t not in autres] + (autres or ['Autres services'])
    choisi = (request.GET.get('service') or '').strip()
    return render(request, 'core/contact.html', {'services': services, 'choisi': choisi})

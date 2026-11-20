"""Lien vers la fiche d'un service à partir de son nom (repli : page « Nous contacter » avec le service choisi)."""
from urllib.parse import quote

from django import template
from django.urls import reverse

register = template.Library()


@register.filter
def fiche_service(nom):
    from Services.models import Service
    s = Service.objects.filter(title=nom, is_active=True).only('pk').first()
    if s:
        return reverse('services:service_detail', args=[s.pk])
    return reverse('core:contact') + '?service=' + quote(nom)

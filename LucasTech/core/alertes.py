"""Alerte de l'équipe Lantante par e-mail (sans jamais bloquer l'action en cours)."""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Q

logger = logging.getLogger(__name__)
SITE = 'https://lantantetechnologie.com'


def prevenir_equipe(texte, url=''):
    try:
        emails = list(get_user_model().objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True))
                      .exclude(email='').values_list('email', flat=True))
        if not emails:
            return
        lien = url if url.startswith('http') else f"{SITE}{url or '/lantanteAdminTech/'}"
        send_mail("Lantante — nouvelle demande", f"{texte}

Ouvrir : {lien}", settings.DEFAULT_FROM_EMAIL,
                  emails, fail_silently=True)
    except Exception:
        logger.warning("Alerte équipe impossible", exc_info=True)

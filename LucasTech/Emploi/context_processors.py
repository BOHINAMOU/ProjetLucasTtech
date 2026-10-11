from django.db.models import Q


def emploi_counters(request):
    """Compteurs affichés dans le sous-menu Emploi (notifications / messages non lus)."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not request.path.startswith('/emploi/'):
        return {}
    from .models import Message
    access = Q(conversation__participants=user)
    unread = Message.objects.exclude(sender=user).exclude(read_by=user)
    if user.is_staff or user.is_superuser:
        # L'équipe voit aussi les demandes du service client (sans compter les messages automatiques).
        access |= Q(conversation__kind='support')
        unread = unread.exclude(is_automatic=True)
    return {
        'em_unread_notifs': user.emploi_notifications.filter(is_read=False).count(),
        'em_unread_msgs': unread.filter(access).distinct().count(),
    }

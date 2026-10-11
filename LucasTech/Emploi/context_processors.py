def emploi_counters(request):
    """Compteurs affichés dans le sous-menu Emploi (notifications / messages non lus)."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not request.path.startswith('/emploi/'):
        return {}
    from .models import Message
    return {
        'em_unread_notifs': user.emploi_notifications.filter(is_read=False).count(),
        'em_unread_msgs': Message.objects.filter(conversation__participants=user)
                                         .exclude(sender=user).exclude(read_by=user).count(),
    }

from .models import Ticket, TicketType


def issue_tickets(payment):
    """Émet les tickets d'un paiement réussi (appelé une seule fois, dans la transaction de livraison)."""
    if payment.tickets.exists():
        return
    types = {t.pk: t for t in TicketType.objects.filter(event_id=payment.event_id)}
    for item in payment.items or []:
        tt = types.get(item.get('ticket_type'))
        if not tt:
            continue
        for _ in range(int(item.get('quantity') or 0)):
            Ticket.objects.create(event_id=payment.event_id, ticket_type=tt, payment=payment,
                                  holder_name=payment.full_name)

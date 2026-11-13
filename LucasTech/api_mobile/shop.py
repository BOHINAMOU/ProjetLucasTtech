"""Achats, contact, profil et pages légales DANS l'application (aucune page du site n'est ouverte).

Paiement : l'application envoie {type, id, pays, operateur, telephone…} ; le serveur crée le paiement et
lance la demande Mobile Money FedaPay. Soit la demande arrive directement sur le téléphone (on attend la
validation), soit FedaPay renvoie SA page de paiement (opérateurs sans paiement direct) que l'appli affiche.
L'appli interroge ensuite paiements/<référence>/ jusqu'au résultat. La livraison (accès, tickets, commande,
abonnement) suit exactement le même chemin que sur le site (Payments.services)."""
import logging
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import strip_tags
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .catalog import text
from .utils import dt, error, user_payload

logger = logging.getLogger(__name__)


# ─────────────────────────────
# Moyens de paiement
# ─────────────────────────────
@api_view(['GET'])
@permission_classes([AllowAny])
def moyens(request):
    from Payments import fedapay, mobile_money as mm
    return Response({
        'actif': fedapay.is_enabled(),
        'pays': [{'code': code, 'nom': c['label'], 'indicatif': c['dial'], 'exemple': c['example'],
                  'operateurs': [{'code': m, 'nom': label, 'direct': m in mm.DIRECT_MODES}
                                 for m, label, _p in c['operators']]}
                 for code, c in mm.COUNTRIES.items()],
    })


def _cible(user, d):
    """(champs du paiement, montant, description, avant_lancement) selon le type acheté, ou ValidationError."""
    kind = str(d.get('type') or '')
    try:
        pk = int(d.get('id') or 0)
    except (TypeError, ValueError):
        pk = 0
    if kind == 'service':
        from Services.models import Service
        s = Service.objects.filter(pk=pk, is_active=True).first()
        if not s or not s.price:
            raise ValidationError("Ce service ne se paie pas en ligne.")
        return {'kind': 'service', 'service': s}, int(s.price), f"Service : {s.title}", None
    if kind == 'formation':
        from Formations.models import Formation
        f = Formation.objects.filter(pk=pk, is_published=True, formation_type__in=('cours', 'numerique')).first()
        if not f or not f.price:
            raise ValidationError("Cette formation ne se paie pas en ligne.")
        return {'kind': 'formation', 'formation': f}, int(f.price), f"Formation : {f.title}", None
    if kind == 'produit':
        from Shop.models import Product
        p = Product.objects.filter(pk=pk, is_available=True).first()
        if not p or p.stock <= 0:
            raise ValidationError("Ce produit n'est plus disponible.")
        try:
            qty = int(d.get('quantite') or 1)
        except (TypeError, ValueError):
            qty = 1
        qty = max(1, min(qty, p.stock))
        unit = p.bulk_price if (p.bulk_price and qty >= p.bulk_min_qty) else p.price
        desc = f"{p.name} × {qty}" if qty > 1 else p.name
        return ({'kind': 'product', 'product': p,
                 'items': [{'product': p.pk, 'name': p.name, 'quantity': qty, 'price': int(unit)}]},
                int(unit) * qty, desc, None)
    if kind == 'abonnement':
        from abonnements import services as abo
        from abonnements.models import PERIOD_DAYS, SubscriptionPlan
        plan = SubscriptionPlan.objects.filter(code=str(d.get('formule') or ''), is_active=True).first()
        if not plan:
            raise ValidationError("Choisissez une formule.")
        period = d.get('periode') if d.get('periode') in PERIOD_DAYS else 'mois'
        label = 'mois' if period == 'mois' else 'an'
        return ({'kind': 'abonnement'}, plan.price_for(period), f"Abonnement concours {plan.name} (1 {label})",
                lambda payment: abo.create_pending_subscription(user, plan, period, payment=payment))
    if kind == 'ticket':
        from Events.models import Event, TicketType
        e = Event.objects.filter(pk=pk, is_published=True).first()
        if not e or e.is_past:
            raise ValidationError("Cet événement n'est plus en vente.")
        wanted = {str(k): v for k, v in (d.get('tickets') or {}).items()}
        items, amount, count = [], 0, 0
        with transaction.atomic():
            for tt in TicketType.objects.select_for_update().filter(event=e):
                try:
                    q = int(wanted.get(str(tt.pk)) or 0)
                except (TypeError, ValueError):
                    q = 0
                if q <= 0:
                    continue
                if q > tt.max_choice():
                    raise ValidationError(f"Plus que {tt.max_choice()} place(s) « {tt.name} ».")
                items.append({'ticket_type': tt.pk, 'name': tt.name, 'quantity': q, 'price': tt.price})
                amount += tt.price * q
                count += q
        if not items:
            raise ValidationError("Choisissez au moins un ticket.")
        return ({'kind': 'ticket', 'event': e, 'items': items}, amount,
                f"{count} ticket{'s' if count > 1 else ''} — {e.title}", None)
    raise ValidationError("Type d'achat inconnu.")


def payment_payload(p):
    statut = {'approved': 'paye', 'pending': 'en_attente', 'declined': 'refuse', 'canceled': 'annule'}
    tickets = [{'code': t.code, 'type': t.ticket_type.name, 'titulaire': t.holder_name}
               for t in p.tickets.select_related('ticket_type')] if p.kind == 'ticket' else []
    return {
        'reference': p.reference, 'statut': statut.get(p.status, 'en_attente'), 'statut_libelle': p.get_status_display(),
        'montant': p.amount, 'description': p.description, 'operateur': p.operator_short if p.operator else '',
        'telephone': p.phone_display if p.phone else '', 'url_fedapay': p.payment_url or '',
        'message': p.failure_reason or '', 'date': dt(p.created_at), 'tickets': tickets,
        'telechargement': bool(p.is_paid and p.downloadable_file),
    }


@api_view(['POST'])
def payer(request):
    """Lance un paiement Mobile Money depuis l'application (le client ne quitte jamais l'appli)."""
    from Payments import fedapay, mobile_money as mm, services
    from Payments.models import Payment
    user, d = request.user, request.data
    if not fedapay.is_enabled():
        return error("Le paiement en ligne est momentanément indisponible.", 503, code='paiement_indisponible')
    country = str(d.get('pays') or mm.DEFAULT_COUNTRY)
    operator = str(d.get('operateur') or '')
    try:
        phone = mm.normalize(str(d.get('telephone') or ''), country)
        mm.check_operator(phone, country, operator)
        fields, amount, description, before = _cible(user, d)
    except ValidationError as e:
        return error(e.messages[0], 400, code='donnees_invalides')
    if amount <= 0 and fields['kind'] == 'ticket':  # tickets gratuits : pas de FedaPay
        p = Payment.objects.create(user=user, amount=0, description=description, mode='free',
                                   first_name=user.first_name or '-', last_name=user.last_name or '-',
                                   email=user.email, phone=phone, whatsapp=user.phone or phone, operator=operator,
                                   **fields)
        services.mark_paid(p)
        p.refresh_from_db()
        return Response(payment_payload(p), status=201)
    city = str(d.get('ville') or '')[:255]
    p = Payment.objects.create(
        user=user, amount=amount, description=description[:255],
        first_name=(user.first_name or str(d.get('prenom') or '') or '-')[:100],
        last_name=(user.last_name or str(d.get('nom') or '') or '-')[:100],
        email=user.email, phone=phone, whatsapp=(user.phone or phone)[:30], operator=operator,
        city=city, address=city if fields['kind'] == 'product' else '', **fields)
    if before:
        before(p)
    p.mode = fedapay.mode()
    p.save(update_fields=['mode'])
    try:
        if p.mode == 'demo':
            url = None
        else:
            cb = request.build_absolute_uri(reverse('payments:callback', args=[p.reference]))
            url = fedapay.start(p, cb)
    except fedapay.FedaPayError as exc:
        p.status, p.failure_reason = 'canceled', str(exc)[:255]
        p.save(update_fields=['status', 'failure_reason'])
        from abonnements.models import UserSubscription
        UserSubscription.objects.filter(payment=p, status='en_attente').update(status='annule')
        return error(str(exc), 400, code='paiement_refuse')
    p.refresh_from_db()
    data = payment_payload(p)
    data['url_fedapay'] = url or ''
    data['ussd'] = mm.USSD.get(operator, '')
    return Response(data, status=201)


@api_view(['GET'])
def paiement(request, reference):
    """Statut du paiement (relu chez FedaPay) : l'appli l'interroge toutes les quelques secondes."""
    from Payments import services
    from Payments.models import Payment
    p = get_object_or_404(Payment, reference=reference, user=request.user)
    services.refresh(p)
    return Response(payment_payload(p))


# ─────────────────────────────
# Contact (centre d'aide)
# ─────────────────────────────
def _site():
    try:
        from core.models import SiteSettings
        return SiteSettings.objects.first()
    except Exception:  # pragma: no cover
        return None


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def contact(request):
    s = _site()
    email = (getattr(s, 'email', '') or 'contact@lantantetechnologie.com')
    whatsapp = re.sub(r'\D', '', getattr(s, 'whatsapp_1', '') or '')
    phone = ('+' + whatsapp) if whatsapp else ''
    if request.method == 'GET':
        return Response({'email': email, 'whatsapp': whatsapp, 'telephone': phone})
    d = request.data
    message = str(d.get('message') or '').strip()
    sujet = str(d.get('sujet') or 'Message depuis l\'application').strip()[:120]
    if len(message) < 5:
        return error("Écrivez votre message.", 400, code='donnees_invalides')
    u = request.user if request.user.is_authenticated else None
    nom = (u.get_full_name() if u else str(d.get('nom') or '')).strip() or 'Utilisateur de l\'application'
    reply = (u.email if u else str(d.get('email') or '')).strip()
    tel = (u.phone if u and u.phone else str(d.get('telephone') or '')).strip()
    body = (f"Message envoyé depuis l'application Lantante\n\nDe : {nom}\nE-mail : {reply or '-'}\n"
            f"Téléphone / WhatsApp : {tel or '-'}\nSujet : {sujet}\n\n{message}\n")
    try:
        from django.core.mail import EmailMessage
        EmailMessage(subject=f"[Appli] {sujet}", body=body, from_email=settings.DEFAULT_FROM_EMAIL,
                     to=[email], reply_to=[reply] if reply else None).send(fail_silently=False)
    except Exception:
        logger.exception("Contact appli : e-mail non envoyé")
        return error("Le message n'a pas pu être envoyé. Écrivez-nous sur WhatsApp.", 503, code='envoi_impossible')
    return Response({'detail': "Merci ! Votre message a bien été envoyé. Nous vous répondons très vite."})


# ─────────────────────────────
# Profil et pages légales
# ─────────────────────────────
@api_view(['PATCH'])
def profil(request):
    u, d = request.user, request.data
    for field, attr, n in (('first_name', 'first_name', 150), ('last_name', 'last_name', 150),
                           ('phone', 'phone', 20), ('country', 'country', 100), ('city', 'city', 100)):
        if field in d:
            setattr(u, attr, str(d.get(field) or '').strip()[:n] or (None if attr in ('phone', 'country', 'city') else ''))
    u.save()
    return Response(user_payload(request, u))


PAGES = {'confidentialite': ('Confidentialité', 'core/privacy_policy.html'),
         'conditions': ("Conditions d'utilisation", 'core/terms_of_service.html')}


@api_view(['GET'])
@permission_classes([AllowAny])
def page(request, slug):
    from django.template.loader import render_to_string
    if slug not in PAGES:
        return error("Page introuvable.", 404, code='introuvable')
    titre, tpl = PAGES[slug]
    html = render_to_string(tpl, request=request._request)
    m = re.search(r'<main[^>]*>(.*)</main>', html, re.S)
    body = m.group(1) if m else html
    body = re.sub(r'(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>', '', body)
    return Response({'titre': titre, 'contenu': text(body) or strip_tags(body)})


# ─────────────────────────────
# Choix des concours d'un abonnement (dans l'appli)
# ─────────────────────────────
@api_view(['GET', 'POST'])
def abonnement_concours(request, pk):
    from abonnements import services as abo
    from abonnements.models import UserSubscription
    from concours.models import Contest
    sub = get_object_or_404(UserSubscription.objects.select_related('plan'), pk=pk, user=request.user)
    if request.method == 'POST':
        ids = [int(x) for x in (request.data.get('concours') or []) if str(x).isdigit()]
        try:
            abo.add_contests(sub, list(Contest.objects.published().filter(pk__in=ids)))
        except abo.SelectionError as e:
            return error(str(e), 400, code='selection_refusee')
        sub.refresh_from_db()
    contests = Contest.objects.published().filter(is_demo=False).select_related('category')
    states = abo.selection_states(request.user, sub, contests) if sub.is_active and not sub.is_unlimited else []
    return Response({
        'id': sub.pk, 'formule': sub.plan.name, 'actif': sub.is_active, 'illimite': sub.is_unlimited,
        'places_libres': sub.free_slots, 'places_total': sub.total_limit,
        'concours': [{'id': c.pk, 'sigle': c.acronym, 'nom': c.name, 'categorie': c.category.name, 'etat': st}
                     for c, st in states],
    })

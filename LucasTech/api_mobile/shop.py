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
                  'chiffres': list(c['digits']),
                  'operateurs': [{'code': m, 'nom': label, 'direct': m in mm.DIRECT_MODES, 'prefixes': list(p)}
                                 for m, label, p in c['operators']]}
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
        fields = {'kind': 'product', 'product': p,
                  'items': [{'product': p.pk, 'name': p.name, 'quantity': qty, 'price': int(unit)}]}
        articles = int(unit) * qty
        if p.vendeur_id and not p.vendeur.actif:
            raise ValidationError("Ce produit n'est plus disponible.")
        from Marche.livraison import calculer
        liv = calculer(p, str(d.get('ville') or ''), d.get('lat'), d.get('lng'))
        if liv['frais']:
            fields.update(livraison=liv['frais'], livraison_detail=liv['detail'])
        if p.vendeur_id:
            fields.update(vendeur=p.vendeur, commission=int(round(articles * float(p.vendeur.commission_pct) / 100)))
        return fields, articles + liv['frais'], desc, None
    if kind == 'panier':
        return _panier(user, d)
    if kind == 'abonnement':
        raise ValidationError("Les formules ne sont plus vendues : débloquez chaque concours à l'unité.")
    if kind == 'abonnement_ancien':  # gardé pour mémoire, inaccessible
        from abonnements import services as abo
        from abonnements.models import PERIOD_DAYS, SubscriptionPlan
        plan = SubscriptionPlan.objects.filter(code=str(d.get('formule') or ''), is_active=True).first()
        if not plan:
            raise ValidationError("Choisissez une formule.")
        period = d.get('periode') if d.get('periode') in PERIOD_DAYS else 'mois'
        label = 'mois' if period == 'mois' else 'an'
        return ({'kind': 'abonnement'}, plan.price_for(period), f"Abonnement concours {plan.name} (1 {label})",
                lambda payment: abo.create_pending_subscription(user, plan, period, payment=payment))
    if kind == 'depot':
        from Payments.solde import MAX_DEPOT, MIN_DEPOT
        try:
            montant = int(d.get('montant') or 0)
        except (TypeError, ValueError):
            montant = 0
        if not MIN_DEPOT <= montant <= MAX_DEPOT:
            raise ValidationError(f"Montant entre {MIN_DEPOT} CFA et {MAX_DEPOT:,} CFA.".replace(',', ' '))
        return {'kind': 'depot'}, montant, "Recharge du solde Lantante", None
    if kind == 'acces':
        from abonnements.models import ReglageAcces
        r = ReglageAcces.load()
        return {'kind': 'acces'}, int(r.prix), "Abonnement Accès Épreuves (1 an)", None
    if kind == 'concours':
        raise ValidationError("Les concours ne sont plus vendus à l'unité : prenez l'abonnement.")
    if kind == 'soutien':
        from Events.models import Event
        e = Event.objects.filter(pk=pk, is_published=True, kind='soutien').first()
        if not e or e.is_past:
            raise ValidationError("Cet événement n'accepte plus de soutien.")
        try:
            montant = int(d.get('montant') or 0)
        except (TypeError, ValueError):
            montant = 0
        if montant < e.min_amount:
            raise ValidationError(f"Montant minimal : {e.min_amount} CFA.")
        if montant > 1_000_000:
            raise ValidationError("Maximum 1 000 000 CFA.")
        return {'kind': 'soutien', 'event': e}, montant, f"Soutien : {e.title}", None
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


MAX_ARTICLES = 200


def _lire_panier(d):
    """Articles du panier (type, id, quantité) ; prix, stock et disponibilité relus en base."""
    from Formations.models import Formation
    from Shop.models import Product
    arts = d.get('articles')
    if not isinstance(arts, list) or not arts:
        raise ValidationError("Votre panier est vide.")
    items, articles, vendeurs, livrables = [], 0, set(), []
    for a in arts[:MAX_ARTICLES]:
        if not isinstance(a, dict):
            continue
        t = str(a.get('type') or '')
        try:
            pk, qty = int(a.get('id') or 0), int(a.get('quantite') or 1)
        except (TypeError, ValueError):
            raise ValidationError("Panier invalide.")
        if t == 'produit':
            p = Product.objects.select_related('vendeur').filter(pk=pk).first()
            if not p or not p.is_available or p.stock <= 0 or (p.vendeur_id and not p.vendeur.actif):
                raise ValidationError(f"« {p.name if p else 'Un produit'} » n'est plus disponible.")
            if any(i.get('product') == p.pk for i in items):
                continue
            qty = max(1, min(qty, p.stock))
            unit = int(p.bulk_price if (p.bulk_price and qty >= p.bulk_min_qty) else p.price)
            items.append({'product': p.pk, 'name': p.name, 'quantity': qty, 'price': unit})
            articles += unit * qty
            vendeurs.add(p.vendeur_id)
            if p.livrable:
                livrables.append(p)
        elif t == 'formation':
            f = Formation.objects.filter(pk=pk, is_published=True, formation_type__in=('cours', 'numerique')).first()
            if not f or not f.price:
                raise ValidationError(f"« {f.title if f else 'Une formation'} » ne s'achète plus en ligne.")
            if any(i.get('formation') == f.pk for i in items):
                continue
            items.append({'formation': f.pk, 'name': f.title, 'quantity': 1, 'price': int(f.price)})
            articles += int(f.price)
            vendeurs.add(None)
        else:
            raise ValidationError("Panier invalide.")
    if not items:
        raise ValidationError("Votre panier est vide.")
    return items, articles, vendeurs, livrables


def _panier(user, d):
    """Une seule commande pour tout le panier. Les articles d'un vendeur partenaire se paient à part
    (son argent lui est reversé : il ne doit pas être mêlé à d'autres articles)."""
    items, articles, vendeurs, livrables = _lire_panier(d)
    partenaires = {v for v in vendeurs if v}
    if partenaires and len(vendeurs) > 1:
        raise ValidationError("Les articles d'un vendeur partenaire se commandent à part.")
    fields = {'kind': 'shop', 'items': items}
    if livrables:
        from Marche.livraison import calculer
        frais, detail = 0, ''
        for p in livrables:
            c = calculer(p, str(d.get('ville') or ''), d.get('lat'), d.get('lng'))
            if c['frais'] > frais:
                frais, detail = c['frais'], c['detail']
        if frais:
            fields.update(livraison=frais, livraison_detail=detail)
    if partenaires:
        from Marche.models import Vendeur
        v = Vendeur.objects.get(pk=next(iter(partenaires)))
        fields.update(vendeur=v, commission=int(round(articles * float(v.commission_pct) / 100)))
    n = sum(i['quantity'] for i in items)
    desc = items[0]['name'] if n == 1 else f"Panier : {n} articles"

    def commande(payment):
        from Shop.models import ShopOrder, ShopOrderItem
        o = ShopOrder.objects.create(
            user=user, total_price=payment.amount, status='pending', payment_method='fedapay',
            cash_delivery_name=payment.full_name, cash_delivery_phone=payment.whatsapp or payment.phone,
            cash_delivery_message=payment.address)
        for it in items:
            ShopOrderItem.objects.create(order=o, product_id=it.get('product'), formation_id=it.get('formation'),
                                         quantity=it['quantity'], price=it['price'])
        payment.shop_order = o
        payment.save(update_fields=['shop_order'])
    return fields, articles + int(fields.get('livraison') or 0), desc, commande


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
        'livraison': p.livraison, 'remise': p.remise, 'code_promo': p.code_promo.code if p.code_promo_id else '',
        'facture': _facture(p),
    }


def _facture(p):
    if not p.is_paid or p.amount <= 0:
        return ''
    from django.conf import settings
    base = getattr(settings, 'SITE_URL', 'https://lantantetechnologie.com').rstrip('/')
    return f"{base}{reverse('payments:receipt', args=[p.reference])}?t={p.access_token}"


@api_view(['POST'])
def payer(request):
    """Lance un paiement Mobile Money depuis l'application (le client ne quitte jamais l'appli)."""
    from Payments import fedapay, mobile_money as mm, services
    from Payments.models import Payment
    user, d = request.user, request.data
    if str(d.get('moyen') or '') == 'solde':
        return _payer_avec_solde(request)
    if not fedapay.is_enabled():
        return error("Le paiement en ligne est momentanément indisponible.", 503, code='paiement_indisponible')
    country = str(d.get('pays') or mm.DEFAULT_COUNTRY)
    operator = str(d.get('operateur') or '')
    from django.db import transaction
    try:
        phone = mm.normalize(str(d.get('telephone') or ''), country)
        mm.check_operator(phone, country, operator)
        with transaction.atomic():
            fields, amount, description, before = _cible(user, d)
            amount = _appliquer_promo(user, d, fields, amount)
            p = _creer_paiement_mm(user, d, fields, amount, description, before, phone, operator)
    except ValidationError as e:
        return error(e.messages[0], 400, code=_code_erreur(e))
    if p.mode == 'free':
        services.mark_paid(p)
        p.refresh_from_db()
        return Response(payment_payload(p), status=201)
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


def _code_erreur(e):
    m = e.messages[0] if e.messages else ''
    if 'promo' in m.lower() or m.startswith('Code') or 'trop faible' in m:
        return 'code_promo'
    if 'livr' in m.lower() or 'position' in m.lower() or 'localisation' in m.lower():
        return 'livraison'
    return 'donnees_invalides'


def _appliquer_promo(user, d, fields, amount):
    """Applique le code promo (à appeler dans une transaction : le code est verrouillé)."""
    from Payments.promo import remise
    r, code = remise(d.get('code_promo'), user, fields, amount, verrou=True)
    if code:
        fields.update(remise=r, code_promo=code)
    return amount - r


def _creer_paiement_mm(user, d, fields, amount, description, before, phone, operator):
    from Payments import fedapay
    from Payments.models import Payment
    if amount <= 0 and fields['kind'] == 'ticket':  # tickets gratuits : pas de FedaPay
        return Payment.objects.create(user=user, amount=0, description=description, mode='free',
                                      first_name=user.first_name or '-', last_name=user.last_name or '-',
                                      email=user.email, phone=phone, whatsapp=user.phone or phone, operator=operator,
                                      **fields)
    city = str(d.get('ville') or '')[:255]
    p = Payment.objects.create(
        user=user, amount=amount, description=description[:255],
        first_name=(user.first_name or str(d.get('prenom') or '') or '-')[:100],
        last_name=(user.last_name or str(d.get('nom') or '') or '-')[:100],
        email=user.email, phone=phone, whatsapp=(user.phone or phone)[:30], operator=operator,
        city=city, address=_adresse(d, fields), **fields)
    if before:
        before(p)
    p.mode = fedapay.mode()
    p.save(update_fields=['mode'])
    return p


def _adresse(d, fields):
    if fields['kind'] not in ('product', 'shop'):
        return ''
    a = str(d.get('adresse') or d.get('ville') or '').strip()
    if d.get('lat') not in (None, '') and d.get('lng') not in (None, ''):
        a = f"{a} (GPS {d.get('lat')}, {d.get('lng')})".strip()
    return a[:255]


@api_view(['POST'])
def devis(request):
    """Récapitulatif avant paiement : articles + livraison - remise = total (rien n'est créé)."""
    user, d = request.user, request.data
    try:
        fields, amount, _, _ = _cible(user, d)
    except ValidationError as e:
        return error(e.messages[0], 400, code=_code_erreur(e))
    from Payments.promo import remise
    livraison = int(fields.get('livraison') or 0)
    rep = {'articles': amount - livraison, 'livraison': livraison, 'livraison_detail': fields.get('livraison_detail', ''),
           'remise': 0, 'total': amount, 'code_promo': '', 'message_promo': ''}
    p = fields.get('product')
    if p is None and fields.get('kind') == 'shop':
        from Shop.models import Product
        ids = [i['product'] for i in fields['items'] if i.get('product')]
        p = Product.objects.filter(pk__in=ids, livrable=True).first()
        rep['lignes'] = [{'type': 'produit' if i.get('product') else 'formation',
                          'id': i.get('product') or i.get('formation'), 'nom': i['name'],
                          'quantite': i['quantity'], 'prix': i['price']} for i in fields['items']]
    if p is not None and p.livrable:
        from Marche.livraison import depart
        lat, lng, ville = depart(p)
        rep['depart'] = {'lat': lat, 'lng': lng, 'ville': ville}
    if str(d.get('code_promo') or '').strip():
        try:
            r, code = remise(d.get('code_promo'), user, fields, amount)
            rep.update(remise=r, total=amount - r, code_promo=code.code)
        except ValidationError as e:
            rep['message_promo'] = e.messages[0]
    return Response(rep)


def _payer_avec_solde(request):
    """Paiement avec le solde Lantante : débit et livraison dans la même transaction."""
    from django.db import transaction
    from Payments import services
    from Payments.models import Payment
    from Payments.solde import SoldeInsuffisant, payer_avec_solde
    user, d = request.user, request.data
    try:
        fields, amount, description, before = _cible(user, d)
    except ValidationError as e:
        return error(e.messages[0], 400, code=_code_erreur(e))
    if fields['kind'] == 'depot':
        return error("On recharge son solde par Mobile Money.", 400, code='donnees_invalides')
    if amount <= 0:
        return error("Montant invalide.", 400, code='donnees_invalides')
    try:
        with transaction.atomic():
            amount = _appliquer_promo(user, d, fields, amount)
            city = str(d.get('ville') or '')[:255]
            p = Payment.objects.create(
                user=user, amount=amount, description=description[:255], mode='solde', operator='',
                first_name=(user.first_name or str(d.get('prenom') or '') or '-')[:100],
                last_name=(user.last_name or str(d.get('nom') or '') or '-')[:100],
                email=user.email, phone=(user.phone or '')[:30], whatsapp=(user.phone or '')[:30],
                city=city, address=_adresse(d, fields), **fields)
            if before:
                before(p)
            payer_avec_solde(user, amount, p)
            services.mark_paid(p)
    except SoldeInsuffisant:
        return error("Solde insuffisant.", 400, code='solde_insuffisant')
    except ValidationError as e:
        return error(e.messages[0], 400, code=_code_erreur(e))
    p.refresh_from_db()
    return Response(payment_payload(p), status=201)


@api_view(['GET'])
def solde(request):
    """Solde et derniers mouvements (dépôts, paiements)."""
    from Payments.solde import MAX_DEPOT, MIN_DEPOT, portefeuille
    pf = portefeuille(request.user)
    return Response({
        'solde': pf.solde, 'min_depot': MIN_DEPOT, 'max_depot': MAX_DEPOT,
        'mouvements': [{'id': m.pk, 'type': m.type, 'libelle': m.get_type_display(), 'montant': m.montant,
                        'solde_apres': m.solde_apres, 'motif': m.motif, 'date': dt(m.created_at),
                        'reference': m.payment.reference if m.payment_id else ''}
                       for m in pf.mouvements.select_related('payment')[:50]],
    })


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
    piece = request.FILES.get('piece')
    if piece is not None:
        ext = piece.name.rsplit('.', 1)[-1].lower() if '.' in piece.name else ''
        if ext not in ('pdf', 'jpg', 'jpeg', 'png', 'webp'):
            return error("Pièce jointe : PDF ou image seulement.", 400, code='donnees_invalides')
        if piece.size > 5 * 1024 * 1024:
            return error("Pièce jointe trop lourde (5 Mo max).", 400, code='donnees_invalides')
    u = request.user if request.user.is_authenticated else None
    nom = (u.get_full_name() if u else str(d.get('nom') or '')).strip() or 'Utilisateur de l\'application'
    reply = (u.email if u else str(d.get('email') or '')).strip()
    tel = (u.phone if u and u.phone else str(d.get('telephone') or '')).strip()
    body = (f"Message envoyé depuis l'application Lantante\n\nDe : {nom}\nE-mail : {reply or '-'}\n"
            f"Téléphone / WhatsApp : {tel or '-'}\nSujet : {sujet}\n\n{message}\n")
    try:
        from django.core.mail import EmailMessage
        m = EmailMessage(subject=f"[Appli] {sujet}", body=body, from_email=settings.DEFAULT_FROM_EMAIL,
                         to=[email], reply_to=[reply] if reply else None)
        if piece is not None:
            m.attach(piece.name, piece.read(), piece.content_type or 'application/octet-stream')
        m.send(fail_silently=False)
    except Exception:
        logger.exception("Contact appli : e-mail non envoyé")
        return error("Le message n'a pas pu être envoyé. Réessayez.", 503, code='envoi_impossible')
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



@api_view(['GET'])
@permission_classes([AllowAny])
def abonnement(request):
    """Abonnement « Accès Épreuves » : prix, durée, et fin si l'utilisateur est abonné."""
    from abonnements.annuel import fin_acces
    from abonnements.models import ReglageAcces
    r = ReglageAcces.load()
    fin = fin_acces(request.user)
    return Response({'prix': r.prix, 'duree_jours': r.duree_jours, 'actif': fin is not None, 'fin': dt(fin) if fin else None})



@api_view(['GET', 'PUT'])
def panier(request):
    """Panier gardé sur le compte : [{type, id, quantite}] (les prix ne sont jamais stockés)."""
    from Shop.models import PanierAppli
    pa, _ = PanierAppli.objects.get_or_create(user=request.user)
    if request.method == 'PUT':
        arts = request.data.get('articles') if isinstance(request.data, dict) else request.data
        propre = []
        for a in (arts if isinstance(arts, list) else [])[:MAX_ARTICLES]:
            try:
                t, pk, q = str(a.get('type')), int(a.get('id')), int(a.get('quantite') or 1)
            except (AttributeError, TypeError, ValueError):
                continue
            if t in ('produit', 'formation') and pk > 0:
                propre.append({'type': t, 'id': pk, 'quantite': 1 if t == 'formation' else max(1, min(q, 999))})
        pa.contenu = propre
        pa.save(update_fields=['contenu', 'updated_at'])
    return Response({'articles': pa.contenu})

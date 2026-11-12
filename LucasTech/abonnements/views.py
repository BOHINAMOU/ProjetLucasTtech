from functools import wraps
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from concours.models import Contest, ContestCategory
from Payments import fedapay
from Payments.forms import CustomerForm
from Payments.models import Payment
from Payments.views import begin_payment, pay_js_data, whatsapp_link

from . import services
from .access import accessible_contest_ids, active_subscriptions, has_unlimited
from .models import PERIOD_DAYS, ExtensionOption, SubscriptionPlan, UserSubscription


def account_required(view):
    """Achat d'abonnement / d'extension : compte obligatoire (pas d'achat invité).
    Visiteur -> page d'inscription, avec retour automatique ici après création du compte."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Créez votre compte gratuit (ou connectez-vous) pour vous abonner.")
            return redirect(f"{reverse('users:register')}?next={quote(request.get_full_path())}")
        return view(request, *args, **kwargs)
    return wrapper


def plans(request):
    plans = SubscriptionPlan.objects.filter(is_active=True)
    return render(request, 'abonnements/plans.html', {
        'plans': plans, 'options': ExtensionOption.objects.filter(is_active=True),
    })


def _pay_context(form, amount, description, back_url, **extra):
    ctx = {'form': form, 'amount': amount, 'description': description, 'back_url': back_url,
           'enabled': fedapay.is_enabled(), 'mode': fedapay.mode(), 'pay_js': pay_js_data(),
           'pay_label': f"Payer {amount:,} FCFA".replace(',', ' '),
           'whatsapp_url': whatsapp_link(f"Bonjour, je souhaite : {description} ({amount} FCFA).")}
    ctx.update(extra)
    return ctx


@account_required
def subscribe(request, code):
    plan = get_object_or_404(SubscriptionPlan, code=code, is_active=True)
    period = request.POST.get('periode') or request.GET.get('periode') or 'mois'
    if period not in PERIOD_DAYS:
        period = 'mois'
    amount = plan.price_for(period)
    label = 'mois' if period == 'mois' else 'an'
    description = f"Abonnement concours {plan.name} (1 {label})"
    form = CustomerForm(request.POST or None, user=request.user, purpose='abonnement')
    if request.method == 'POST' and fedapay.is_enabled() and form.is_valid():
        created = {}

        def link(payment):
            created['sub'] = services.create_pending_subscription(request.user, plan, period, payment=payment)

        response = begin_payment(request, form, before_start=link, amount=amount, description=description,
                                 kind='abonnement')
        if response:
            return response
        if created.get('sub'):
            UserSubscription.objects.filter(pk=created['sub'].pk).update(status='annule')
    ultimate = services.ultimate_to_extend(request.user) if plan.is_unlimited else None
    return render(request, 'abonnements/checkout.html', _pay_context(
        form, amount, description, reverse('abonnements:plans'), plan=plan, period=period,
        advice=services.advice_for(request.user, plan), ultimate=ultimate,
        days=PERIOD_DAYS[period]))


@account_required
def extend(request, pk):
    sub = get_object_or_404(UserSubscription, pk=pk, user=request.user)
    back = reverse('abonnements:space')
    if not sub.is_active or sub.is_unlimited:
        messages.error(request, "Extension impossible sur cet abonnement.")
        return redirect(back)
    options = [(o, services.extension_price(o, sub)) for o in ExtensionOption.objects.filter(is_active=True)]
    if not options:
        messages.error(request, "Aucune extension disponible pour le moment.")
        return redirect(back)
    try:
        chosen_slots = int(request.POST.get('slots') or request.GET.get('slots') or options[0][0].slots)
    except ValueError:
        chosen_slots = options[0][0].slots
    option, amount = next(((o, p) for o, p in options if o.slots == chosen_slots), options[0])
    description = f"Extension +{option.slots} concours (abonnement {sub.plan.name} #{sub.pk})"
    form = CustomerForm(request.POST or None, user=request.user, purpose='abonnement')
    if request.method == 'POST' and fedapay.is_enabled() and form.is_valid():
        created = {}

        def link(payment):
            created['ext'] = services.create_pending_extension(sub, option, payment=payment)

        response = begin_payment(request, form, before_start=link, amount=amount, description=description,
                                 kind='abonnement')
        if response:
            return response
        if created.get('ext'):
            created['ext'].status = 'annule'
            created['ext'].save(update_fields=['status'])
    return render(request, 'abonnements/extend.html', _pay_context(
        form, amount, description, back, sub=sub, options=options, option=option))


@login_required
def space(request):
    services.expire_overdue()
    user = request.user
    subs = (UserSubscription.objects.filter(user=user)
            .exclude(status='annule')
            .exclude(status='en_attente', payment__status__in=['declined', 'canceled'])
            .select_related('plan', 'payment', 'merged_into')
            .prefetch_related('contests__contest', 'extensions'))
    unlimited = has_unlimited(user)
    ids = accessible_contest_ids(user)
    my_contests = Contest.objects.published().filter(pk__in=ids).select_related('category')
    payments = Payment.objects.filter(user=user, kind='abonnement').order_by('-created_at')[:50]
    return render(request, 'abonnements/space.html', {
        'subs': subs, 'my_contests': my_contests, 'unlimited': unlimited, 'payments': payments,
        'tab': request.GET.get('onglet') or 'abonnements',
        'n_active': active_subscriptions(user).count(),
    })


@login_required
def select(request, pk):
    sub = get_object_or_404(UserSubscription.objects.select_related('plan'), pk=pk, user=request.user)
    if not sub.is_active:
        messages.error(request, "Cet abonnement n'est pas actif.")
        return redirect('abonnements:space')
    if sub.is_unlimited:
        messages.info(request, "Votre formule donne accès à tous les concours.")
        return redirect('concours:index')
    if request.method == 'POST':
        ids = [int(i) for i in request.POST.getlist('contests') if i.isdigit()]
        chosen = list(Contest.objects.published().filter(pk__in=ids, is_demo=False))
        try:
            services.add_contests(sub, chosen)
        except services.SelectionError as exc:
            messages.error(request, str(exc))
        else:
            n = len(chosen)
            messages.success(request, f"{n} concours ajouté{'s' if n > 1 else ''} à votre abonnement.")
            return redirect(reverse('abonnements:space'))
    q = (request.GET.get('q') or '').strip()
    contests = Contest.objects.published().filter(is_demo=False).select_related('category')
    cat = request.GET.get('categorie') or ''
    if cat:
        contests = contests.filter(category__slug=cat)
    if q:
        contests = contests.filter(Q(acronym__icontains=q) | Q(name__icontains=q))
    return render(request, 'abonnements/select.html', {
        'sub': sub, 'rows': services.selection_states(request.user, sub, contests),
        'categories': ContestCategory.objects.filter(contests__is_published=True).distinct(),
        'search_query': q, 'active_cat': cat,
    })

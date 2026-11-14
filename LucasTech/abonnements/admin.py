from django.contrib import admin

from .models import (ExtensionOption, SubscriptionAuditLog, SubscriptionContest, SubscriptionExtension,
                     SubscriptionPlan, UserSubscription)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'monthly_price', 'yearly_price', 'contest_limit', 'is_unlimited', 'is_active',
                    'order')
    list_editable = ('monthly_price', 'yearly_price', 'contest_limit', 'is_active', 'order')


@admin.register(ExtensionOption)
class ExtensionOptionAdmin(admin.ModelAdmin):
    list_display = ('slots', 'price', 'is_active')
    list_editable = ('price', 'is_active')


class ContestInline(admin.TabularInline):
    model = SubscriptionContest
    extra = 0
    autocomplete_fields = ('contest',)
    readonly_fields = ('added_at',)


class ExtensionInline(admin.TabularInline):
    model = SubscriptionExtension
    extra = 0
    fields = ('slots', 'price_paid', 'status', 'payment', 'activated_at')
    raw_id_fields = ('payment',)


class AuditInline(admin.TabularInline):
    model = SubscriptionAuditLog
    extra = 0
    can_delete = False
    fields = ('created_at', 'admin', 'action', 'details')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


def _log(request, sub, action, details=''):
    SubscriptionAuditLog.objects.create(subscription=sub, admin=request.user, action=action[:60],
                                        details=details)


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'plan', 'period', 'status', 'start_at', 'end_at', 'montant', 'n_contests')

    @admin.display(description="Montant", ordering='price_paid')
    def montant(self, obj):
        from Payments.admin import francs
        return francs(obj.price_paid)
    list_filter = ('status', 'plan', 'period')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'payment__reference')
    raw_id_fields = ('user', 'payment', 'merged_into')
    readonly_fields = ('created_at', 'activated_at')
    inlines = [ContestInline, ExtensionInline, AuditInline]
    date_hierarchy = 'created_at'

    @admin.display(description="Concours")
    def n_contests(self, obj):
        return obj.contests.count()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and form.changed_data:
            details = "; ".join(f"{f} : {form.initial.get(f)!s} → {form.cleaned_data.get(f)!s}"
                                for f in form.changed_data)
            _log(request, obj, "Modification manuelle", details)
        elif not change:
            _log(request, obj, "Création manuelle", f"Statut {obj.status}, fin {obj.end_at}")

    def save_formset(self, request, form, formset, change):
        if formset.model is SubscriptionAuditLog:
            return super().save_formset(request, form, formset, change)
        instances = formset.save(commit=False)
        label = formset.model._meta.verbose_name
        for obj in formset.deleted_objects:
            _log(request, form.instance, f"Suppression : {label}", str(obj))
            obj.delete()
        for obj in instances:
            is_new = obj.pk is None
            obj.save()
            _log(request, form.instance, f"{'Ajout' if is_new else 'Modification'} : {label}", str(obj))
        formset.save_m2m()


@admin.register(SubscriptionExtension)
class SubscriptionExtensionAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'slots', 'price_paid', 'status', 'created_at')
    list_filter = ('status',)
    raw_id_fields = ('subscription', 'payment')


@admin.register(SubscriptionAuditLog)
class SubscriptionAuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'subscription', 'admin', 'action')
    search_fields = ('subscription__user__email', 'action', 'details')
    readonly_fields = ('subscription', 'admin', 'action', 'details', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

from django.contrib import admin

from modules.references.backend.models import (
    Currency,
    CurrencyRateType,
    CurrencyRateTypeTranslation,
    CurrencyTranslation,
)


class CurrencyTranslationInline(admin.TabularInline):
    """Edit a currency's localized names from its page."""

    model = CurrencyTranslation
    extra = 1


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    """Administration of the currency reference data."""

    list_display = ("code", "numeric_code", "name", "symbol", "minor_units", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "numeric_code", "name")
    readonly_fields = ("created_at", "updated_at")
    inlines = (CurrencyTranslationInline,)


class CurrencyRateTypeTranslationInline(admin.TabularInline):
    """Edit a rate type's localized names from its page."""

    model = CurrencyRateTypeTranslation
    extra = 1


@admin.register(CurrencyRateType)
class CurrencyRateTypeAdmin(admin.ModelAdmin):
    """Administration of the bank rate types."""

    list_display = (
        "name",
        "code",
        "principle",
        "validity",
        "daily_required",
        "is_system",
        "is_active",
        "order",
    )
    list_filter = ("principle", "validity", "daily_required", "is_system", "is_active")
    search_fields = ("code", "name")
    readonly_fields = ("created_at", "updated_at")
    inlines = (CurrencyRateTypeTranslationInline,)

    def get_changeform_initial_data(self, request):
        """Pre-fill the principle-dependent defaults on the add form."""
        initial = super().get_changeform_initial_data(request)
        principle = initial.get("principle", CurrencyRateType.Principle.OFFICIAL)
        initial.setdefault("validity", CurrencyRateType.default_validity(principle))
        initial.setdefault(
            "daily_required", CurrencyRateType.default_daily_required(principle)
        )
        return initial

    def save_model(self, request, obj, form, change):
        """Apply the defaults when an administrator leaves the fields untouched."""
        if not change:
            if "validity" not in form.changed_data:
                obj.validity = CurrencyRateType.default_validity(obj.principle)
            if "daily_required" not in form.changed_data:
                obj.daily_required = CurrencyRateType.default_daily_required(obj.principle)
        super().save_model(request, obj, form, change)

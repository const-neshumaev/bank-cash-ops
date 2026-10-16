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

    list_display = ("name", "code", "principle", "is_system", "is_active", "order")
    list_filter = ("principle", "is_system", "is_active")
    search_fields = ("code", "name")
    readonly_fields = ("created_at", "updated_at")
    inlines = (CurrencyRateTypeTranslationInline,)

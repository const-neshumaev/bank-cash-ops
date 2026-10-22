from django.contrib import admin

from modules.operations.backend import history as history_service
from modules.operations.backend.models import (
    CashBalance,
    CashDeskOperation,
    Movement,
    Operation,
    OperationLine,
    OperationNumberSequence,
    OperationTemplate,
    OperationType,
    OperationTypeSettingsChange,
    OperationTypeTranslation,
    SlotDef,
    SlotDefTranslation,
)


class SlotDefInline(admin.TabularInline):
    """Edit an operation type's amount slots from its page."""

    model = SlotDef
    extra = 1


class OperationTypeTranslationInline(admin.TabularInline):
    """Edit an operation type's translations from its page."""

    model = OperationTypeTranslation
    extra = 1


class SlotDefTranslationInline(admin.TabularInline):
    """Edit a slot's translations from its page."""

    model = SlotDefTranslation
    extra = 1


@admin.register(OperationType)
class OperationTypeAdmin(admin.ModelAdmin):
    """Administration of the operation type catalogue."""

    list_display = (
        "name",
        "code",
        "kind",
        "client_data_policy",
        "rate_type",
        "is_active",
    )
    list_filter = ("kind", "is_external", "client_data_policy", "is_active")
    search_fields = ("name", "code")
    readonly_fields = ("form", "rate_principle", "created_at", "updated_at")
    inlines = (SlotDefInline, OperationTypeTranslationInline)

    def save_model(self, request, obj, form, change):
        before = history_service.snapshot(type(obj).objects.get(pk=obj.pk)) if change else None
        super().save_model(request, obj, form, change)
        history_service.record_settings_change(
            obj, before=before, user=request.user
        )


@admin.register(SlotDef)
class SlotDefAdmin(admin.ModelAdmin):
    """Administration of the amount slot catalogue and its translations."""

    list_display = ("__str__", "name", "required", "fixed_currency", "order")
    list_filter = ("required", "fixed_currency")
    search_fields = ("name", "code", "operation_type__code", "operation_type__name")
    readonly_fields = ("created_at", "updated_at")
    inlines = (SlotDefTranslationInline,)


class OperationLineInline(admin.TabularInline):
    """Show the amount lines of an operation (read only)."""

    model = OperationLine
    extra = 0
    can_delete = False
    readonly_fields = ("slot", "currency", "amount", "rate", "rate_type", "rate_is_individual")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):
    """Administration of the operation journal (read only)."""

    list_display = ("number", "operation_type", "cash_desk_id", "status", "posted_at")
    list_filter = ("status", "operation_type", "cash_desk_id")
    search_fields = ("number", "client_name", "client_document", "idempotency_key")
    readonly_fields = (
        "operation_type",
        "number",
        "cash_desk_id",
        "shift_id",
        "cashier_id",
        "status",
        "idempotency_key",
        "client_name",
        "client_document",
        "comment",
        "posted_at",
        "reversal_of",
        "created_at",
        "updated_at",
    )
    inlines = (OperationLineInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Movement)
class MovementAdmin(admin.ModelAdmin):
    """Administration of the register movements (read only)."""

    list_display = ("operation", "register", "cash_desk_id", "currency", "amount")
    list_filter = ("register", "currency", "cash_desk_id")
    search_fields = ("operation__number",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CashBalance)
class CashBalanceAdmin(admin.ModelAdmin):
    """Administration of the materialised cash balances (read only)."""

    list_display = ("cash_desk_id", "currency", "amount", "updated_at")
    list_filter = ("currency", "cash_desk_id")
    search_fields = ("cash_desk_id",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OperationNumberSequence)
class OperationNumberSequenceAdmin(admin.ModelAdmin):
    """Administration of the per-cash-desk numbering sequences."""

    list_display = ("cash_desk_id", "last_number")
    search_fields = ("cash_desk_id",)


@admin.register(OperationTypeSettingsChange)
class OperationTypeSettingsChangeAdmin(admin.ModelAdmin):
    """Read-only audit trail of the administrator-managed type settings."""

    list_display = ("operation_type", "changed_at", "changed_by_email")
    list_filter = ("operation_type",)
    search_fields = ("operation_type__code", "operation_type__name", "changed_by_email")
    readonly_fields = (
        "operation_type",
        "changed_at",
        "changed_by_id",
        "changed_by_email",
        "changes",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CashDeskOperation)
class CashDeskOperationAdmin(admin.ModelAdmin):
    """Administration of the per-cash-desk operation configuration."""

    list_display = ("cash_desk_id", "operation_type")
    list_filter = ("operation_type",)
    search_fields = ("cash_desk_id", "operation_type__code", "operation_type__name")
    autocomplete_fields = ("operation_type",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(OperationTemplate)
class OperationTemplateAdmin(admin.ModelAdmin):
    """Administration of the bank-wide and per-branch operation templates."""

    list_display = ("__str__", "branch_id")
    list_filter = ("branch_id",)
    filter_horizontal = ("operation_types",)

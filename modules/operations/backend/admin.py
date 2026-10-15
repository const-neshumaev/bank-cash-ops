from django.contrib import admin

from modules.operations.backend.models import (
    CashBalance,
    CashDeskOperation,
    Movement,
    Operation,
    OperationLine,
    OperationNumberSequence,
    OperationsSettings,
    OperationTemplate,
    OperationType,
    SlotDef,
)


class SlotDefInline(admin.TabularInline):
    """Edit an operation type's amount slots from its page."""

    model = SlotDef
    extra = 1


@admin.register(OperationType)
class OperationTypeAdmin(admin.ModelAdmin):
    """Administration of the operation type catalogue."""

    list_display = ("name", "code", "kind", "is_external", "requires_client", "is_active")
    list_filter = ("kind", "is_external", "requires_client", "is_active")
    search_fields = ("name", "code")
    readonly_fields = ("created_at", "updated_at")
    inlines = (SlotDefInline,)


class OperationLineInline(admin.TabularInline):
    """Show the amount lines of an operation (read only)."""

    model = OperationLine
    extra = 0
    can_delete = False
    readonly_fields = ("slot", "currency", "amount", "rate")

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


@admin.register(OperationsSettings)
class OperationsSettingsAdmin(admin.ModelAdmin):
    """Administer the bank-wide operation settings."""

    def has_add_permission(self, request):
        return not OperationsSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

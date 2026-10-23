from django.contrib import admin

from modules.printing.backend.models import (
    PrintDocument,
    PrintDocumentType,
    PrintDocumentTypeTranslation,
    PrintNumberSequence,
    PrintTemplate,
    PrintTemplateTranslation,
)


class PrintDocumentTypeTranslationInline(admin.TabularInline):
    """Edit a document type's translations from its page."""

    model = PrintDocumentTypeTranslation
    extra = 1


@admin.register(PrintDocumentType)
class PrintDocumentTypeAdmin(admin.ModelAdmin):
    """Administration of the declared print document types."""

    list_display = ("name", "code", "numbering_scope", "is_active")
    list_filter = ("numbering_scope", "is_active")
    search_fields = ("name", "code")
    readonly_fields = ("created_at", "updated_at")
    inlines = (PrintDocumentTypeTranslationInline,)


class PrintTemplateTranslationInline(admin.TabularInline):
    """Edit a template's translations from its page."""

    model = PrintTemplateTranslation
    extra = 1


@admin.register(PrintTemplate)
class PrintTemplateAdmin(admin.ModelAdmin):
    """Administration of the declared print forms and their uploaded files."""

    list_display = ("name", "code", "document_type", "has_file", "is_active", "last_error_at")
    list_filter = ("document_type", "is_active")
    search_fields = ("name", "code", "description")
    readonly_fields = (
        "code",
        "document_type",
        "provider",
        "file_name",
        "file_size",
        "file_updated_at",
        "file_updated_by_id",
        "last_error",
        "last_error_at",
        "created_at",
        "updated_at",
    )
    inlines = (PrintTemplateTranslationInline,)

    @admin.display(boolean=True, description="file uploaded")
    def has_file(self, obj):
        return obj.has_file

    def has_add_permission(self, request):
        return False


@admin.register(PrintNumberSequence)
class PrintNumberSequenceAdmin(admin.ModelAdmin):
    """Administration of the bank-wide document number sequences."""

    list_display = ("document_type", "last_number")
    search_fields = ("document_type",)


@admin.register(PrintDocument)
class PrintDocumentAdmin(admin.ModelAdmin):
    """Read-only view of the rendered documents."""

    list_display = (
        "number",
        "document_type",
        "operation_type_code",
        "operation_id",
        "cash_desk_id",
        "created_at",
    )
    list_filter = ("document_type", "operation_type_code", "cash_desk_id")
    search_fields = ("number", "operation_id", "template_code")
    readonly_fields = (
        "document_type",
        "document_type_name",
        "template_code",
        "template_name",
        "operation_id",
        "operation_type_code",
        "cash_desk_id",
        "number",
        "file_name",
        "context",
        "created_by_id",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

"""Serializers of the ``printing`` module."""

from __future__ import annotations

from rest_framework import serializers

from modules.printing.backend.models import PrintDocumentType, PrintTemplate
from modules.printing.backend.registry import print_template_registry


class PrintTemplateSerializer(serializers.ModelSerializer):
    """Read representation of a print form and its uploaded file metadata."""

    document_type_name = serializers.SerializerMethodField()
    has_file = serializers.BooleanField(read_only=True)
    variables = serializers.SerializerMethodField()

    class Meta:
        model = PrintTemplate
        fields = (
            "code",
            "name",
            "document_type",
            "document_type_name",
            "description",
            "provider",
            "file_name",
            "file_size",
            "file_updated_at",
            "has_file",
            "last_error",
            "last_error_at",
            "is_active",
            "variables",
        )
        read_only_fields = fields

    def get_document_type_name(self, obj) -> str:
        document_type = (
            PrintDocumentType.objects.prefetch_related("translations")
            .filter(code=obj.document_type)
            .first()
        )
        return document_type.localized_name() if document_type is not None else ""

    def get_variables(self, obj) -> list[dict]:
        provider = print_template_registry.get_provider(obj.provider)
        if provider is None:
            return []
        return [
            {
                "code": variable.code,
                "description": str(variable.description),
                "example": variable.example,
            }
            for variable in provider.variables
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = instance.localized_name()
        return data


class PrintDocumentTypeSerializer(serializers.ModelSerializer):
    """Read representation of a printed document type."""

    name = serializers.SerializerMethodField()

    class Meta:
        model = PrintDocumentType
        fields = ("code", "name", "description", "numbering_scope", "is_active")
        read_only_fields = fields

    def get_name(self, obj) -> str:
        return obj.localized_name()


class PrintTemplateUploadSerializer(serializers.Serializer):
    """Input for uploading a Word template."""

    file = serializers.FileField()


class PrintDocumentInfoSerializer(serializers.Serializer):
    """Read representation of a rendered document DTO."""

    id = serializers.IntegerField()
    document_type = serializers.CharField()
    document_type_name = serializers.CharField()
    template_code = serializers.CharField()
    template_name = serializers.CharField()
    operation_id = serializers.IntegerField()
    operation_type_code = serializers.CharField()
    cash_desk_id = serializers.IntegerField()
    number = serializers.IntegerField(allow_null=True)
    file_name = serializers.CharField()
    created_at = serializers.DateTimeField()

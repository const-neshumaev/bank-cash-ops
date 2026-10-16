from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from modules.operations.backend.models import (
    CashBalance,
    Movement,
    Operation,
    OperationLine,
    OperationsSettings,
    OperationTemplate,
    OperationType,
    SlotDef,
)


class SlotDefSerializer(serializers.ModelSerializer):
    """Read-only representation of an operation type's amount slot."""

    class Meta:
        model = SlotDef
        fields = ("code", "name", "required", "fixed_currency", "order")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = instance.localized_name()
        return data


class OperationTypeSerializer(serializers.ModelSerializer):
    """Read-only representation of an operation type and its slots."""

    slots = SlotDefSerializer(many=True, read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = OperationType
        fields = (
            "code",
            "name",
            "kind",
            "kind_display",
            "is_external",
            "requires_client",
            "client_id_threshold",
            "permission_code",
            "is_active",
            "slots",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = instance.localized_name()
        return data


class OperationTypeOptionSerializer(serializers.ModelSerializer):
    """Compact operation type representation used by pickers."""

    class Meta:
        model = OperationType
        fields = ("code", "name", "kind")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = instance.localized_name()
        return data


class MovementSerializer(serializers.ModelSerializer):
    """Read-only representation of a register movement."""

    class Meta:
        model = Movement
        fields = ("register", "currency", "amount", "operation_type_code")


class OperationLineSerializer(serializers.ModelSerializer):
    """Read-only representation of an operation's amount line."""

    class Meta:
        model = OperationLine
        fields = ("slot", "currency", "amount", "rate")


class OperationSerializer(serializers.ModelSerializer):
    """Read-only representation of an operation document."""

    operation_type = serializers.SlugRelatedField(slug_field="code", read_only=True)
    operation_type_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    lines = OperationLineSerializer(many=True, read_only=True)
    movements = MovementSerializer(many=True, read_only=True)

    def get_operation_type_name(self, obj) -> str:
        return obj.operation_type.localized_name()

    class Meta:
        model = Operation
        fields = (
            "id",
            "number",
            "operation_type",
            "operation_type_name",
            "cash_desk_id",
            "shift_id",
            "cashier_id",
            "status",
            "status_display",
            "client_name",
            "client_document",
            "comment",
            "posted_at",
            "reversal_of",
            "lines",
            "movements",
        )
        read_only_fields = fields


class OperationLineInputSerializer(serializers.Serializer):
    """Input for one amount line of a posted operation."""

    slot = serializers.CharField(max_length=64)
    currency = serializers.CharField(max_length=8)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    rate = serializers.DecimalField(
        max_digits=18, decimal_places=8, required=False, allow_null=True
    )


class PostOperationSerializer(serializers.Serializer):
    """Input for posting an operation.

    The cash desk and the shift are not part of the input: they are resolved from
    the cashier's open shift.
    """

    operation_type = serializers.SlugRelatedField(
        slug_field="code", queryset=OperationType.objects.all()
    )
    lines = OperationLineInputSerializer(many=True)
    client_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    client_document = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )
    comment = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    idempotency_key = serializers.CharField(
        max_length=128, required=False, allow_blank=True, default=""
    )

    def validate_operation_type(self, value):
        if not value.is_active:
            raise serializers.ValidationError(_("The operation type is not active."))
        return value


class CashBalanceSerializer(serializers.ModelSerializer):
    """Read-only representation of a cash balance."""

    class Meta:
        model = CashBalance
        fields = ("cash_desk_id", "currency", "amount", "updated_at")


class OperationsSettingsSerializer(serializers.ModelSerializer):
    """Read and update representation of the bank-wide operations settings."""

    class Meta:
        model = OperationsSettings
        fields = ("base_currency", "client_id_threshold", "require_client", "updated_at")
        read_only_fields = ("updated_at",)


class CashDeskOperationsSerializer(serializers.Serializer):
    """Input for replacing the operation types enabled on a cash desk."""

    operations = serializers.ListField(child=serializers.CharField(max_length=64), allow_empty=True)


class OperationTemplateSerializer(serializers.ModelSerializer):
    """Read representation of an operation template (bank or branch)."""

    branch_id = serializers.IntegerField(read_only=True)
    operations = OperationTypeOptionSerializer(source="operation_types", many=True, read_only=True)

    class Meta:
        model = OperationTemplate
        fields = ("id", "branch_id", "operations")


class WorkplaceOperationSerializer(serializers.ModelSerializer):
    """An operation type as the cashier screen needs it (with its slots)."""

    slots = SlotDefSerializer(many=True, read_only=True)

    class Meta:
        model = OperationType
        fields = ("code", "name", "kind", "requires_client", "client_id_threshold", "slots")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = instance.localized_name()
        return data

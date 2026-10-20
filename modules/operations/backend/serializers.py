from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from modules.operations.backend.models import (
    CashBalance,
    Movement,
    Operation,
    OperationLine,
    OperationTemplate,
    OperationType,
    OperationTypeSettingsChange,
    SlotDef,
)
from modules.operations.backend.thresholds import (
    THRESHOLD_TYPES,
    ClientDataPolicy,
    threshold_errors,
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
    """Read and update representation of an operation type and its slots.

    Only the administrator-managed settings are writable: the client-data policy,
    the threshold configuration and the activity flag. Declarative metadata (code,
    name, kind, slots, posting template) is owned by the declaring module.
    """

    slots = SlotDefSerializer(many=True, read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    client_data_policy_display = serializers.CharField(
        source="get_client_data_policy_display", read_only=True
    )
    threshold_type_display = serializers.SerializerMethodField()

    class Meta:
        model = OperationType
        fields = (
            "code",
            "name",
            "kind",
            "kind_display",
            "is_external",
            "client_data_policy",
            "client_data_policy_display",
            "threshold_type",
            "threshold_type_display",
            "threshold_value",
            "threshold_currency",
            "permission_code",
            "is_active",
            "slots",
        )
        read_only_fields = (
            "code",
            "name",
            "kind",
            "kind_display",
            "is_external",
            "client_data_policy_display",
            "threshold_type_display",
            "permission_code",
            "slots",
        )

    def get_threshold_type_display(self, obj) -> str:
        threshold = next(
            (item for item in THRESHOLD_TYPES if item.code == obj.threshold_type), None
        )
        return str(threshold.name) if threshold is not None else ""

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = instance.localized_name()
        return data

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        policy = attrs.get(
            "client_data_policy",
            getattr(instance, "client_data_policy", ClientDataPolicy.NEVER),
        )
        threshold_type = attrs.get("threshold_type", getattr(instance, "threshold_type", ""))
        threshold_value = attrs.get("threshold_value", getattr(instance, "threshold_value", None))
        threshold_currency = attrs.get(
            "threshold_currency", getattr(instance, "threshold_currency", "")
        )

        if policy == ClientDataPolicy.THRESHOLD:
            errors = threshold_errors(
                policy, threshold_type, threshold_value, threshold_currency
            )
            if errors:
                raise serializers.ValidationError(errors)
            attrs["threshold_currency"] = (threshold_currency or "").strip().upper()
        else:
            # Switching away from a threshold clears the unused configuration.
            attrs["threshold_type"] = ""
            attrs["threshold_value"] = None
            attrs["threshold_currency"] = ""
        return attrs


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


class OperationTypeHistorySerializer(serializers.ModelSerializer):
    """Read-only representation of an operation type settings change."""

    operation_type = serializers.SlugRelatedField(slug_field="code", read_only=True)

    class Meta:
        model = OperationTypeSettingsChange
        fields = (
            "id",
            "operation_type",
            "changed_at",
            "changed_by_id",
            "changed_by_email",
            "changes",
        )
        read_only_fields = fields


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
    requires_client = serializers.BooleanField(read_only=True)

    class Meta:
        model = OperationType
        fields = (
            "code",
            "name",
            "kind",
            "client_data_policy",
            "requires_client",
            "slots",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = instance.localized_name()
        return data

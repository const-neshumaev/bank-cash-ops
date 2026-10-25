from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from modules.common.contracts import registry
from modules.operations.backend.models import (
    CashBalance,
    Movement,
    Operation,
    OperationLine,
    OperationPrintConfig,
    OperationTemplate,
    OperationType,
    OperationTypeSettingsChange,
    SlotDef,
)
from modules.operations.backend.printing import operation_ids_with_documents
from modules.operations.backend.thresholds import (
    THRESHOLD_TYPES,
    ClientDataPolicy,
    threshold_errors,
)
from modules.references.contracts import REFERENCE_DIRECTORY


class SlotDefSerializer(serializers.ModelSerializer):
    """Read-only representation of an operation type's amount slot."""

    class Meta:
        model = SlotDef
        fields = (
            "code",
            "name",
            "required",
            "fixed_currency",
            "order",
            "multiple",
            "currency_policy",
            "amount_mode",
            "computation",
            "stores_rate",
            "threshold_basis",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = instance.localized_name()
        return data


class OperationPrintConfigSerializer(serializers.ModelSerializer):
    """A printed document configured for an operation type."""

    template = serializers.CharField(source="template_code")
    document_type_name = serializers.SerializerMethodField()
    template_name = serializers.SerializerMethodField()

    class Meta:
        model = OperationPrintConfig
        fields = (
            "document_type",
            "document_type_name",
            "template",
            "template_name",
            "is_active",
        )

    def get_document_type_name(self, obj) -> str:
        names = self.context.get("print_document_type_names") or {}
        return names.get(obj.document_type, obj.document_type)

    def get_template_name(self, obj) -> str:
        names = self.context.get("print_template_names") or {}
        return names.get(obj.template_code, obj.template_code)


class OperationTypeSerializer(serializers.ModelSerializer):
    """Read and update representation of an operation type and its slots.

    Only the administrator-managed settings are writable: the client-data policy,
    the threshold configuration, the exchange rate type and the activity flag.
    Declarative metadata (code, name, kind, form, slots, posting template) is owned
    by the declaring module.
    """

    slots = SlotDefSerializer(many=True, read_only=True)
    print_configs = OperationPrintConfigSerializer(many=True, read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    client_data_policy_display = serializers.CharField(
        source="get_client_data_policy_display", read_only=True
    )
    threshold_type_display = serializers.SerializerMethodField()
    rate_type_display = serializers.SerializerMethodField()

    class Meta:
        model = OperationType
        fields = (
            "code",
            "name",
            "kind",
            "kind_display",
            "form",
            "is_external",
            "client_data_policy",
            "client_data_policy_display",
            "threshold_type",
            "threshold_type_display",
            "threshold_value",
            "threshold_currency",
            "rate_principle",
            "rate_type",
            "rate_type_display",
            "permission_code",
            "is_active",
            "slots",
            "print_configs",
        )
        read_only_fields = (
            "code",
            "name",
            "kind",
            "kind_display",
            "form",
            "is_external",
            "client_data_policy_display",
            "threshold_type_display",
            "rate_principle",
            "rate_type_display",
            "permission_code",
            "slots",
            "print_configs",
        )

    def get_threshold_type_display(self, obj) -> str:
        threshold = next(
            (item for item in THRESHOLD_TYPES if item.code == obj.threshold_type), None
        )
        return str(threshold.name) if threshold is not None else ""

    def get_rate_type_display(self, obj) -> str:
        if not obj.rate_type:
            return ""
        rate_type = registry.get(REFERENCE_DIRECTORY).get_rate_type(obj.rate_type)
        return rate_type.name if rate_type is not None else obj.rate_type

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
            errors = threshold_errors(policy, threshold_type, threshold_value, threshold_currency)
            if errors:
                raise serializers.ValidationError(errors)
            attrs["threshold_currency"] = (threshold_currency or "").strip().upper()
        else:
            # Switching away from a threshold clears the unused configuration.
            attrs["threshold_type"] = ""
            attrs["threshold_value"] = None
            attrs["threshold_currency"] = ""

        kind = attrs.get("kind", getattr(instance, "kind", ""))
        rate_type = (attrs.get("rate_type", getattr(instance, "rate_type", "")) or "").strip()
        if kind == OperationType.Kind.EXCHANGE:
            if not rate_type:
                raise serializers.ValidationError(
                    {"rate_type": _("The rate type is required for an exchange operation.")}
                )
            directory = registry.get(REFERENCE_DIRECTORY)
            rate_type_dto = directory.get_rate_type(rate_type)
            if rate_type_dto is None or not rate_type_dto.is_active:
                raise serializers.ValidationError(
                    {"rate_type": _("Unknown or inactive rate type.")}
                )
            principle = getattr(instance, "rate_principle", "")
            if principle and rate_type_dto.principle != principle:
                raise serializers.ValidationError(
                    {
                        "rate_type": _("The rate type must use the '%(principle)s' principle.")
                        % {"principle": principle}
                    }
                )
            attrs["rate_type"] = rate_type
        else:
            attrs["rate_type"] = ""
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
        fields = (
            "slot",
            "currency",
            "amount",
            "rate",
            "rate_type",
            "rate_is_individual",
        )


class OperationSerializer(serializers.ModelSerializer):
    """Read-only representation of an operation document."""

    operation_type = serializers.SlugRelatedField(slug_field="code", read_only=True)
    operation_type_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    lines = OperationLineSerializer(many=True, read_only=True)
    movements = MovementSerializer(many=True, read_only=True)
    has_print_documents = serializers.SerializerMethodField()

    def get_operation_type_name(self, obj) -> str:
        return obj.operation_type.localized_name()

    def get_has_print_documents(self, obj) -> bool:
        known = self.context.get("print_operation_ids")
        if known is not None:
            return obj.id in known
        return obj.id in operation_ids_with_documents([obj.id])

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
            "has_print_documents",
            "lines",
            "movements",
        )
        read_only_fields = fields


class PrintDocumentInfoSerializer(serializers.Serializer):
    """Metadata of a rendered document returned after posting."""

    id = serializers.IntegerField()
    document_type = serializers.CharField()
    document_type_name = serializers.CharField()
    template_code = serializers.CharField()
    template_name = serializers.CharField()
    operation_id = serializers.IntegerField()
    operation_type_code = serializers.CharField()
    cash_desk_id = serializers.IntegerField()
    number = serializers.IntegerField()
    file_name = serializers.CharField()
    created_at = serializers.DateTimeField()


class OperationLineInputSerializer(serializers.Serializer):
    """Input for one amount line of a posted operation."""

    slot = serializers.CharField(max_length=64)
    currency = serializers.CharField(max_length=8)
    amount = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, default=Decimal("0")
    )
    rate = serializers.DecimalField(
        max_digits=18, decimal_places=8, required=False, allow_null=True
    )
    rate_is_individual = serializers.BooleanField(required=False, default=False)


class PostOperationSerializer(serializers.Serializer):
    """Input for posting an operation.

    The cash desk and the shift are not part of the input: they are resolved from
    the cashier's open shift.
    """

    operation_type = serializers.SlugRelatedField(
        slug_field="code", queryset=OperationType.objects.all()
    )
    lines = OperationLineInputSerializer(many=True)
    basis_slot = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
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
    rate_type_display = serializers.SerializerMethodField()

    class Meta:
        model = OperationType
        fields = (
            "code",
            "name",
            "kind",
            "form",
            "client_data_policy",
            "requires_client",
            "threshold_type",
            "threshold_value",
            "threshold_currency",
            "rate_principle",
            "rate_type",
            "rate_type_display",
            "slots",
        )

    def get_rate_type_display(self, obj) -> str:
        if not obj.rate_type:
            return ""
        rate_type = registry.get(REFERENCE_DIRECTORY).get_rate_type(obj.rate_type)
        return rate_type.name if rate_type is not None else obj.rate_type

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = instance.localized_name()
        return data

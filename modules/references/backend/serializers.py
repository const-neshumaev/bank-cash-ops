"""REST serializers of the ``references`` module."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from modules.common.contracts import registry
from modules.references.backend.models import Currency, CurrencyRateType
from modules.references.contracts import RATE_TYPE_USAGE_GUARD


class CurrencySerializer(serializers.ModelSerializer):
    """Read and write representation of a currency."""

    class Meta:
        model = Currency
        fields = ("code", "numeric_code", "name", "symbol", "minor_units", "is_active")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = instance.localized_name()
        return data

    def validate_code(self, value):
        return (value or "").strip().upper()


class CurrencyRateTypeSerializer(serializers.ModelSerializer):
    """Read and write representation of a bank rate type."""

    class Meta:
        model = CurrencyRateType
        fields = (
            "id",
            "code",
            "name",
            "principle",
            "validity",
            "daily_required",
            "is_system",
            "is_active",
            "order",
        )
        read_only_fields = ("is_system",)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = instance.localized_name()
        return data

    def create(self, validated_data):
        """Apply the principle-dependent defaults when the client omits them."""
        principle = validated_data.get("principle", CurrencyRateType.Principle.OFFICIAL)
        validated_data.setdefault("validity", CurrencyRateType.default_validity(principle))
        validated_data.setdefault(
            "daily_required", CurrencyRateType.default_daily_required(principle)
        )
        return super().create(validated_data)

    def validate(self, attrs):
        """Refuse to change the storage semantics of a rate type that has rates."""
        attrs = super().validate(attrs)
        instance = self.instance
        if instance is None or "validity" not in attrs:
            return attrs
        if attrs["validity"] == instance.validity:
            return attrs
        try:
            guard = registry.get(RATE_TYPE_USAGE_GUARD)
        except LookupError:
            return attrs
        if guard.is_rate_type_used(instance.code):
            raise serializers.ValidationError(
                {
                    "validity": _(
                        "The rate validity cannot be changed while rates of this type exist."
                    )
                }
            )
        return attrs

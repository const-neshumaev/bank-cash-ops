"""REST serializers of the ``references`` module."""

from __future__ import annotations

from rest_framework import serializers

from modules.references.backend.models import Currency, CurrencyRateType


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
        fields = ("id", "code", "name", "principle", "is_system", "is_active", "order")
        read_only_fields = ("is_system",)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = instance.localized_name()
        return data

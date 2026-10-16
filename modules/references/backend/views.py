"""REST API of the ``references`` module.

The module is mounted under ``/api/references/`` (see ``config/urls.py``).
"""

from __future__ import annotations

from rest_framework import viewsets

from modules.common.backend.permissions import PermissionRequired
from modules.references.backend.models import Currency, CurrencyRateType
from modules.references.backend.permission_codes import PermissionCode
from modules.references.backend.serializers import CurrencyRateTypeSerializer, CurrencySerializer


class CurrencyViewSet(viewsets.ModelViewSet):
    """CRUD administration of the currency reference data."""

    queryset = Currency.objects.prefetch_related("translations")
    serializer_class = CurrencySerializer
    permission_classes = [PermissionRequired]
    lookup_field = "code"
    permission_map = {
        "list": PermissionCode.REFERENCES_VIEW,
        "retrieve": PermissionCode.REFERENCES_VIEW,
        "create": PermissionCode.REFERENCES_MANAGE,
        "update": PermissionCode.REFERENCES_MANAGE,
        "partial_update": PermissionCode.REFERENCES_MANAGE,
        "destroy": PermissionCode.REFERENCES_MANAGE,
    }
    filterset_fields = ["is_active"]
    search_fields = ["code", "numeric_code", "name"]
    ordering_fields = ["code", "name"]
    ordering = ["code"]


class CurrencyRateTypeViewSet(viewsets.ModelViewSet):
    """CRUD administration of the bank rate types."""

    queryset = CurrencyRateType.objects.prefetch_related("translations")
    serializer_class = CurrencyRateTypeSerializer
    permission_classes = [PermissionRequired]
    permission_map = {
        "list": PermissionCode.REFERENCES_VIEW,
        "retrieve": PermissionCode.REFERENCES_VIEW,
        "create": PermissionCode.REFERENCES_MANAGE,
        "update": PermissionCode.REFERENCES_MANAGE,
        "partial_update": PermissionCode.REFERENCES_MANAGE,
        "destroy": PermissionCode.REFERENCES_MANAGE,
    }
    filterset_fields = ["is_active", "principle"]
    search_fields = ["code", "name"]
    ordering_fields = ["order", "code", "name"]
    ordering = ["order", "code"]

    def destroy(self, request, *args, **kwargs):
        """Refuse to delete a system rate type shipped with the product."""
        from rest_framework.exceptions import ValidationError

        instance = self.get_object()
        if instance.is_system:
            raise ValidationError({"detail": "A system rate type cannot be deleted."})
        return super().destroy(request, *args, **kwargs)

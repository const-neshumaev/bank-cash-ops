"""Per-cash-desk operation configuration.

An extension or administrator may restrict the operations available at a cash
desk. The rule is opt-in: a cash desk without configuration allows every active
operation type; once configured, only the listed types are allowed.
"""

from __future__ import annotations

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from modules.operations.backend.models import CashDeskOperation, OperationType


def configured_operation_codes(cash_desk_id: int) -> list[str] | None:
    """Return the operation codes configured for a cash desk, or ``None`` if unset."""
    codes = list(
        CashDeskOperation.objects.filter(cash_desk_id=cash_desk_id).values_list(
            "operation_type__code", flat=True
        )
    )
    return codes or None


def allowed_operation_types(cash_desk_id: int):
    """Operation types available at a cash desk (all active when unconfigured)."""
    queryset = OperationType.objects.filter(is_active=True)
    configured = configured_operation_codes(cash_desk_id)
    if configured is not None:
        queryset = queryset.filter(code__in=configured)
    return queryset.order_by("name")


def is_operation_allowed(cash_desk_id: int, operation_type: OperationType) -> bool:
    """Return whether ``operation_type`` may be posted at the cash desk."""
    configured = configured_operation_codes(cash_desk_id)
    return configured is None or operation_type.code in configured


def set_operation_types(cash_desk_id: int, codes: list[str]) -> None:
    """Replace the operation types enabled on a cash desk with ``codes``."""
    unique_codes = list(dict.fromkeys(codes))
    types = {t.code: t for t in OperationType.objects.filter(code__in=unique_codes)}
    unknown = sorted(set(unique_codes) - set(types))
    if unknown:
        raise ValidationError(
            _("Unknown operation types: %(codes)s.") % {"codes": ", ".join(unknown)}
        )
    with transaction.atomic():
        CashDeskOperation.objects.filter(cash_desk_id=cash_desk_id).delete()
        for code in unique_codes:
            CashDeskOperation.objects.create(cash_desk_id=cash_desk_id, operation_type=types[code])

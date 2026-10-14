"""Filter sets for the ``operations`` module list endpoints."""

from __future__ import annotations

import django_filters

from modules.operations.backend.models import CashBalance, Operation


class OperationFilter(django_filters.FilterSet):
    """Filter the operation journal by place, kind, type and period."""

    cash_desk = django_filters.NumberFilter(field_name="cash_desk_id")
    shift = django_filters.NumberFilter(field_name="shift_id")
    cashier = django_filters.NumberFilter(field_name="cashier_id")
    operation_type = django_filters.CharFilter(field_name="operation_type__code")
    direction = django_filters.CharFilter(field_name="operation_type__kind")
    posted_from = django_filters.IsoDateTimeFilter(field_name="posted_at", lookup_expr="gte")
    posted_to = django_filters.IsoDateTimeFilter(field_name="posted_at", lookup_expr="lte")

    class Meta:
        model = Operation
        fields = (
            "cash_desk",
            "shift",
            "cashier",
            "operation_type",
            "direction",
            "status",
            "posted_from",
            "posted_to",
        )


class CashBalanceFilter(django_filters.FilterSet):
    """Filter cash balances by cash desk and currency."""

    cash_desk = django_filters.NumberFilter(field_name="cash_desk_id")

    class Meta:
        model = CashBalance
        fields = ("cash_desk", "currency")

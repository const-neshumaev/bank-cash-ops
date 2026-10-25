"""Filter sets for the ``core`` module list endpoints."""

from __future__ import annotations

import django_filters

from modules.core.backend.models import CurrencyRate, Shift


class CurrencyRateFilter(django_filters.FilterSet):
    """Filters shared by the rate journal and the current-rates view."""

    scope = django_filters.CharFilter(method="filter_scope")
    effective_date_from = django_filters.DateFilter(field_name="effective_date", lookup_expr="gte")
    effective_date_to = django_filters.DateFilter(field_name="effective_date", lookup_expr="lte")
    effective_from_from = django_filters.IsoDateTimeFilter(
        field_name="effective_from", lookup_expr="gte"
    )
    effective_from_to = django_filters.IsoDateTimeFilter(
        field_name="effective_from", lookup_expr="lte"
    )
    created_from = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_to = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")
    created_by = django_filters.NumberFilter(field_name="created_by_id")
    is_current = django_filters.BooleanFilter(method="filter_is_current")

    class Meta:
        model = CurrencyRate
        fields = (
            "currency",
            "base_currency",
            "rate_type",
            "branch",
            "cash_desk",
            "scope",
            "effective_date_from",
            "effective_date_to",
            "effective_from_from",
            "effective_from_to",
            "created_from",
            "created_to",
            "created_by",
            "is_current",
        )

    def filter_scope(self, queryset, name, value):
        if value == "bank":
            return queryset.filter(branch__isnull=True, cash_desk__isnull=True)
        if value == "branch":
            return queryset.filter(branch__isnull=False)
        if value == "cash_desk":
            return queryset.filter(cash_desk__isnull=False)
        return queryset

    def filter_is_current(self, queryset, name, value):
        return queryset.filter(superseded_at__isnull=value)


class ShiftFilter(django_filters.FilterSet):
    """Filter the shift list by status, place and opening period.

    ``branch`` is resolved through the cash desk because a shift has no direct
    link to a branch. ``opened_from`` / ``opened_to`` accept ISO 8601 datetimes
    and bound the period the shift was opened in.
    """

    branch = django_filters.NumberFilter(field_name="cash_desk__branch")
    opened_from = django_filters.IsoDateTimeFilter(field_name="opened_at", lookup_expr="gte")
    opened_to = django_filters.IsoDateTimeFilter(field_name="opened_at", lookup_expr="lte")

    class Meta:
        model = Shift
        fields = ("status", "cash_desk", "cashier", "branch", "opened_from", "opened_to")

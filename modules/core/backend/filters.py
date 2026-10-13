"""Filter sets for the ``core`` module list endpoints."""

from __future__ import annotations

import django_filters

from modules.core.backend.models import Shift


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

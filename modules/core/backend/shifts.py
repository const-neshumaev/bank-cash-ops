"""Domain services that describe how cashier shifts change."""

from __future__ import annotations

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from modules.core.backend.models import CashDesk, Shift, User
from modules.core.backend.permission_codes import PermissionCode


def visible_shifts(*, user: User, queryset=None):
    """Return the shifts ``user`` is allowed to see.

    A cashier who runs shifts (may open and/or close them) but cannot manage
    shifts belongs to the operational floor and only sees their own shifts;
    everybody else sees every shift. Per-role object scopes will be introduced
    later, so this is the single place that decides visibility today.
    """
    queryset = Shift.objects.all() if queryset is None else queryset
    if user.has_permission(PermissionCode.SHIFTS_MANAGE):
        return queryset
    runs_shifts = user.has_permission(PermissionCode.SHIFTS_OPEN) or user.has_permission(
        PermissionCode.SHIFTS_CLOSE
    )
    if runs_shifts:
        return queryset.filter(cashier=user)
    return queryset


def open_shift(*, cashier: User, cash_desk: CashDesk) -> Shift:
    """Open a shift for ``cashier`` at ``cash_desk``.

    Enforces the module invariants: a cashier may have at most one open shift,
    and a cash desk may host at most one open shift at a time.
    """
    if not cash_desk.is_active:
        raise ValidationError({"cash_desk": _("The cash desk is not active.")})
    if Shift.objects.filter(cashier=cashier, status=Shift.Status.OPEN).exists():
        raise ValidationError(_("You already have an open shift."))
    if Shift.objects.filter(cash_desk=cash_desk, status=Shift.Status.OPEN).exists():
        raise ValidationError({"cash_desk": _("The cash desk already has an open shift.")})
    return Shift.objects.create(cashier=cashier, cash_desk=cash_desk)


def close_shift(*, shift: Shift, closed_by: User) -> Shift:
    """Close an open shift, recording who closed it and when."""
    if shift.status != Shift.Status.OPEN:
        raise ValidationError(_("The shift is already closed."))
    shift.status = Shift.Status.CLOSED
    shift.closed_at = timezone.now()
    shift.closed_by = closed_by
    shift.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
    return shift

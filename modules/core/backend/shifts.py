"""Domain services that describe how cashier shifts change."""

from __future__ import annotations

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from modules.core.backend.models import CashDesk, Shift, User


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

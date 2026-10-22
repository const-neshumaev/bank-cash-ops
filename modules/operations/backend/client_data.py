"""Client-data policy evaluation shared by posting and the preview endpoint.

The policy belongs to the operation type. ``always`` requires the client's name
and document, ``threshold`` requires them only when the operation's basis amount
exceeds the configured threshold. Threshold amounts are compared in the
threshold currency; foreign amounts are converted at the national bank's
official rate. When the rate or the base value needed for the check is missing,
the operation is rejected instead of silently skipping the control.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from modules.common.contracts import registry
from modules.core.contracts import BANK_SETTINGS, CASH_DESK_CONFIG
from modules.operations.backend.models import OperationType
from modules.operations.backend.thresholds import ClientDataPolicy, ThresholdTypeCode
from modules.operations.contracts.dto import SlotValue
from modules.references.contracts import SystemRateTypeCode

ZERO = Decimal("0")


@dataclass(frozen=True)
class ClientDataRequirement:
    """The evaluated client-data requirement of one operation."""

    policy: str
    required: bool
    reason: str
    amount: Decimal | None = None
    threshold: Decimal | None = None
    currency: str = ""


def evaluate_client_data(
    operation_type: OperationType,
    lines: tuple[SlotValue, ...],
    *,
    cash_desk_id: int,
    at: datetime,
) -> ClientDataRequirement:
    """Evaluate whether the operation needs the client's data."""
    policy = operation_type.client_data_policy
    if policy == ClientDataPolicy.NEVER:
        return ClientDataRequirement(policy=policy, required=False, reason="never")
    if policy == ClientDataPolicy.ALWAYS:
        return ClientDataRequirement(policy=policy, required=True, reason="always")
    if policy != ClientDataPolicy.THRESHOLD:
        raise ValidationError(_("Unknown client data policy."))

    threshold, currency = _threshold(operation_type, at)
    amount = _basis_amount(
        operation_type,
        lines,
        currency=currency,
        cash_desk_id=cash_desk_id,
        at=at,
    )
    required = amount > threshold
    return ClientDataRequirement(
        policy=policy,
        required=required,
        reason="threshold" if required else "below_threshold",
        amount=amount,
        threshold=threshold,
        currency=currency,
    )


def enforce_client_data(
    requirement: ClientDataRequirement,
    *,
    client_name: str,
    client_document: str,
) -> None:
    """Reject the operation when required client data is missing."""
    if not requirement.required:
        return
    errors: dict[str, str] = {}
    if not (client_name or "").strip():
        errors["client_name"] = _("The client name is required for this operation.")
    if not (client_document or "").strip():
        errors["client_document"] = _("The client document is required for this operation.")
    if errors:
        raise ValidationError(errors)


def _threshold(operation_type: OperationType, at: datetime) -> tuple[Decimal, str]:
    """Return the configured threshold amount and its currency."""
    value = operation_type.threshold_value
    if value is None:
        raise ValidationError(_("The client data threshold is not configured."))

    if operation_type.threshold_type == ThresholdTypeCode.CURRENCY:
        currency = (operation_type.threshold_currency or "").strip().upper()
        if not currency:
            raise ValidationError(_("The client data threshold currency is not configured."))
        return value, currency

    if operation_type.threshold_type == ThresholdTypeCode.BASE_VALUE:
        settings = registry.get(BANK_SETTINGS).get_settings(timezone.localdate(at))
        if settings.base_value is None:
            raise ValidationError(
                _(
                    "No base value is in force on the operation date; "
                    "the threshold cannot be checked."
                )
            )
        return value * settings.base_value, settings.base_currency

    raise ValidationError(_("The client data threshold type is not configured."))


def _basis_amount(
    operation_type: OperationType,
    lines: tuple[SlotValue, ...],
    *,
    currency: str,
    cash_desk_id: int,
    at: datetime,
) -> Decimal:
    """Sum the operation's threshold-basis lines in ``currency``."""
    slots = {slot.code: slot for slot in operation_type.slots.all()}
    total = ZERO
    for line in lines:
        slot = slots.get(line.slot)
        if slot is None or not slot.threshold_basis:
            continue
        total += _convert(line.amount, line.currency, currency, cash_desk_id=cash_desk_id, at=at)
    return total


def _convert(
    amount: Decimal,
    source_currency: str,
    target_currency: str,
    *,
    cash_desk_id: int,
    at: datetime,
) -> Decimal:
    """Convert an amount between currencies at the official rate."""
    if source_currency == target_currency:
        return amount

    settings = registry.get(BANK_SETTINGS).get_settings(timezone.localdate(at))
    base_currency = settings.base_currency
    config = registry.get(CASH_DESK_CONFIG)

    source_rate = _official_rate(
        config, source_currency, base_currency, cash_desk_id=cash_desk_id, at=at
    )
    target_rate = _official_rate(
        config, target_currency, base_currency, cash_desk_id=cash_desk_id, at=at
    )
    if source_rate is None or target_rate is None or target_rate == 0:
        raise ValidationError(
            _("No official rate is available to check the client data threshold.")
        )
    return amount * source_rate / target_rate


def _official_rate(
    config,
    currency: str,
    base_currency: str,
    *,
    cash_desk_id: int,
    at: datetime,
) -> Decimal | None:
    if currency == base_currency:
        return Decimal("1")
    return config.rate(
        currency,
        SystemRateTypeCode.OFFICIAL,
        cash_desk_id=cash_desk_id,
        at=at,
    )

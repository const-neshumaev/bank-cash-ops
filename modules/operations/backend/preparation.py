"""Validate and prepare operation lines before posting or previewing.

The module applies the declarative slot metadata: currency policies, multiple
currencies, exchange rates and computed legs. The result is the exact set of
lines the engine persists. Client-data evaluation lives in ``client_data``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from modules.operations.backend.client_data import (
    ClientDataRequirement,
    evaluate_client_data,
)
from modules.operations.backend.exchange import (
    base_currency,
    quantize_amount,
    quantize_rate,
    resolve_exchange_rate,
)
from modules.operations.backend.models import OperationType
from modules.operations.contracts.dto import (
    OperationForm,
    SlotAmountMode,
    SlotComputation,
    SlotCurrencyPolicy,
    SlotValue,
)

ZERO = Decimal("0")


@dataclass(frozen=True)
class PreparedOperation:
    """A validated operation ready for preview or posting."""

    operation_type: OperationType
    lines: tuple[SlotValue, ...]
    client_data: ClientDataRequirement


def prepare_operation(
    *,
    operation_type: OperationType,
    cash_desk_id: int,
    lines: tuple[SlotValue, ...] | list[SlotValue],
    at: datetime | None = None,
) -> PreparedOperation:
    """Validate the lines, apply the declared form and evaluate client data."""
    moment = at or timezone.now()
    values = validate_slot_lines(operation_type, lines)
    values = _apply_currency_policies(operation_type, values)
    if operation_type.form == OperationForm.EXCHANGE:
        values = _normalise_exchange(
            operation_type,
            values,
            cash_desk_id=cash_desk_id,
            at=moment,
        )
    requirement = evaluate_client_data(
        operation_type,
        values,
        cash_desk_id=cash_desk_id,
        at=moment,
    )
    return PreparedOperation(
        operation_type=operation_type,
        lines=values,
        client_data=requirement,
    )


def validate_slot_lines(
    operation_type: OperationType, lines: tuple[SlotValue, ...] | list[SlotValue]
) -> tuple[SlotValue, ...]:
    """Check the slot shape: known slots, uniqueness and positive amounts."""
    values = tuple(lines)
    slot_defs = {slot.code: slot for slot in operation_type.slots.all()}
    if not slot_defs:
        return values

    seen: set[tuple[str, str]] = set()
    counts: dict[str, int] = {}
    for value in values:
        slot = slot_defs.get(value.slot)
        if slot is None:
            raise ValidationError(_("Unknown slot '%(slot)s'.") % {"slot": value.slot})

        key = (value.slot, value.currency)
        if key in seen:
            raise ValidationError(
                _("The slot '%(slot)s' is filled more than once for %(currency)s.")
                % {"slot": value.slot, "currency": value.currency}
            )
        seen.add(key)
        counts[value.slot] = counts.get(value.slot, 0) + 1

        if not slot.multiple and counts[value.slot] > 1:
            raise ValidationError(
                _("The slot '%(slot)s' is filled more than once.") % {"slot": value.slot}
            )
        if slot.fixed_currency and slot.fixed_currency != value.currency:
            raise ValidationError(
                _("The slot '%(slot)s' only accepts %(currency)s.")
                % {"slot": value.slot, "currency": slot.fixed_currency}
            )
        if slot.amount_mode != SlotAmountMode.COMPUTED and value.amount <= ZERO:
            raise ValidationError(
                _("The amount of the slot '%(slot)s' must be greater than zero.")
                % {"slot": value.slot}
            )

    missing = [code for code, slot in slot_defs.items() if slot.required and code not in counts]
    if missing:
        raise ValidationError(
            _("Missing required slots: %(slots)s.") % {"slots": ", ".join(sorted(missing))}
        )
    return values


def _apply_currency_policies(
    operation_type: OperationType, lines: tuple[SlotValue, ...]
) -> tuple[SlotValue, ...]:
    slots = {slot.code: slot for slot in operation_type.slots.all()}
    national_currency = ""
    result: list[SlotValue] = []
    for line in lines:
        slot = slots.get(line.slot)
        if slot is None:
            result.append(line)
            continue
        if slot.currency_policy in (
            SlotCurrencyPolicy.BASE,
            SlotCurrencyPolicy.FOREIGN,
        ):
            if not national_currency:
                national_currency = base_currency()
            if slot.currency_policy == SlotCurrencyPolicy.BASE and (
                line.currency != national_currency
            ):
                raise ValidationError(
                    _("The slot '%(slot)s' only accepts the national currency %(currency)s.")
                    % {"slot": line.slot, "currency": national_currency}
                )
            if slot.currency_policy == SlotCurrencyPolicy.FOREIGN and (
                line.currency == national_currency
            ):
                raise ValidationError(
                    _("The slot '%(slot)s' only accepts a foreign currency.")
                    % {"slot": line.slot}
                )
        result.append(line)
    return tuple(result)


def _normalise_exchange(
    operation_type: OperationType,
    lines: tuple[SlotValue, ...],
    *,
    cash_desk_id: int,
    at: datetime,
) -> tuple[SlotValue, ...]:
    slots = {slot.code: slot for slot in operation_type.slots.all()}
    by_slot = {line.slot: line for line in lines}

    computed_slots = [
        slot for slot in slots.values() if slot.amount_mode == SlotAmountMode.COMPUTED
    ]
    rate_slots = [slot for slot in slots.values() if slot.stores_rate]
    if len(slots) != 2 or len(computed_slots) != 1 or len(rate_slots) != 1:
        raise ValidationError(
            _("The exchange operation type '%(code)s' has an invalid slot declaration.")
            % {"code": operation_type.code}
        )

    computed_slot = computed_slots[0]
    rate_slot = rate_slots[0]
    basis_slot = next(slot for slot in slots.values() if slot.code != computed_slot.code)
    basis = by_slot.get(basis_slot.code)
    computed = by_slot.get(computed_slot.code)
    if basis is None or computed is None:
        raise ValidationError(_("Both exchange legs are required."))

    if basis.currency == computed.currency:
        raise ValidationError(_("The exchange legs must use different currencies."))

    rate_line = by_slot[rate_slot.code]
    if rate_line.rate_is_individual:
        if rate_line.rate is None or rate_line.rate <= ZERO:
            raise ValidationError(_("The individual rate must be greater than zero."))
        rate = quantize_rate(rate_line.rate)
    else:
        resolved = resolve_exchange_rate(
            operation_type,
            source_currency=basis.currency,
            target_currency=computed.currency,
            cash_desk_id=cash_desk_id,
            at=at,
        )
        if resolved is None or resolved <= ZERO:
            raise ValidationError(
                _("No rate is available for %(source)s/%(target)s.")
                % {"source": basis.currency, "target": computed.currency}
            )
        rate = quantize_rate(resolved)

    if computed_slot.computation == SlotComputation.MULTIPLY:
        amount = basis.amount * rate
    elif computed_slot.computation == SlotComputation.DIVIDE:
        amount = basis.amount / rate
    else:
        raise ValidationError(
            _("The exchange operation type '%(code)s' has an invalid computation.")
            % {"code": operation_type.code}
        )
    amount = quantize_amount(amount, computed.currency)

    rate_type = (operation_type.rate_type or "").strip()
    is_individual = rate_line.rate_is_individual

    result: list[SlotValue] = []
    for line in lines:
        if line.slot == computed_slot.code:
            result.append(
                replace(
                    line,
                    amount=amount,
                    rate=rate if rate_slot.code == computed_slot.code else None,
                    rate_type=rate_type if rate_slot.code == computed_slot.code else "",
                    rate_is_individual=(
                        is_individual if rate_slot.code == computed_slot.code else False
                    ),
                )
            )
        elif line.slot == rate_slot.code:
            result.append(
                replace(
                    line,
                    rate=rate,
                    rate_type=rate_type,
                    rate_is_individual=is_individual,
                )
            )
        else:
            result.append(
                replace(line, rate=None, rate_type="", rate_is_individual=False)
            )
    return tuple(result)

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
from modules.operations.backend.models import OperationType, SlotDef
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


@dataclass(frozen=True)
class ExchangeLayout:
    """The exchange legs, split into the entered and the derived one.

    ``source`` is the leg the client gives and ``target`` is the leg the bank
    issues; they define the direction of the rate. ``entered`` is the leg whose
    amount the cashier filled in and ``derived`` is computed from it.
    """

    source: SlotDef
    target: SlotDef
    rate: SlotDef
    entered: SlotDef
    derived: SlotDef
    #: How the derived amount is obtained from the entered one.
    computation: str


def prepare_operation(
    *,
    operation_type: OperationType,
    cash_desk_id: int,
    lines: tuple[SlotValue, ...] | list[SlotValue],
    basis_slot: str = "",
    at: datetime | None = None,
) -> PreparedOperation:
    """Validate the lines, apply the declared form and evaluate client data.

    ``basis_slot`` names the exchange leg whose amount the cashier entered; an
    empty value keeps the declared input leg (the leg the client gives).
    """
    moment = at or timezone.now()
    layout = None
    if operation_type.form == OperationForm.EXCHANGE:
        layout = exchange_layout(operation_type, basis_slot)
    values = validate_slot_lines(
        operation_type,
        lines,
        derived_slot=layout.derived.code if layout is not None else "",
    )
    values = _apply_currency_policies(operation_type, values)
    if layout is not None:
        values = _normalise_exchange(
            operation_type,
            values,
            layout=layout,
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
    operation_type: OperationType,
    lines: tuple[SlotValue, ...] | list[SlotValue],
    *,
    derived_slot: str = "",
) -> tuple[SlotValue, ...]:
    """Check the slot shape: known slots, uniqueness and positive amounts.

    ``derived_slot`` is the slot the engine computes, so its submitted amount is
    ignored and may be zero.
    """
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
        if (
            slot.amount_mode != SlotAmountMode.COMPUTED
            and slot.code != derived_slot
            and value.amount <= ZERO
        ):
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
                    _("The slot '%(slot)s' only accepts a foreign currency.") % {"slot": line.slot}
                )
        result.append(line)
    return tuple(result)


def exchange_layout(operation_type: OperationType, basis_slot: str = "") -> ExchangeLayout:
    """Split the exchange legs into the entered and the derived one.

    The declared input slot is the leg the client gives (the rate direction),
    the declared computed slot is the leg the bank issues. ``basis_slot`` may
    name either leg: the other one is then computed with the inverse operation.
    """
    slots = list(operation_type.slots.all())
    computed_slots = [slot for slot in slots if slot.amount_mode == SlotAmountMode.COMPUTED]
    rate_slots = [slot for slot in slots if slot.stores_rate]
    if len(slots) != 2 or len(computed_slots) != 1 or len(rate_slots) != 1:
        raise ValidationError(
            _("The exchange operation type '%(code)s' has an invalid slot declaration.")
            % {"code": operation_type.code}
        )

    target = computed_slots[0]
    source = next(slot for slot in slots if slot.code != target.code)
    requested = (basis_slot or "").strip()
    if requested and requested not in (source.code, target.code):
        raise ValidationError(
            _("The slot '%(slot)s' is not an exchange leg of the operation.") % {"slot": requested}
        )

    if requested == target.code:
        return ExchangeLayout(
            source=source,
            target=target,
            rate=rate_slots[0],
            entered=target,
            derived=source,
            computation=_inverse_computation(target.computation),
        )
    return ExchangeLayout(
        source=source,
        target=target,
        rate=rate_slots[0],
        entered=source,
        derived=target,
        computation=target.computation,
    )


def _inverse_computation(computation: str) -> str:
    """Return the computation that derives the other exchange leg."""
    if computation == SlotComputation.MULTIPLY:
        return SlotComputation.DIVIDE
    if computation == SlotComputation.DIVIDE:
        return SlotComputation.MULTIPLY
    return ""


def _normalise_exchange(
    operation_type: OperationType,
    lines: tuple[SlotValue, ...],
    *,
    layout: ExchangeLayout,
    cash_desk_id: int,
    at: datetime,
) -> tuple[SlotValue, ...]:
    by_slot = {line.slot: line for line in lines}
    entered = by_slot.get(layout.entered.code)
    derived = by_slot.get(layout.derived.code)
    if entered is None or derived is None:
        raise ValidationError(_("Both exchange legs are required."))
    if entered.amount <= ZERO:
        raise ValidationError(
            _("The amount of the slot '%(slot)s' must be greater than zero.")
            % {"slot": entered.slot}
        )

    source = by_slot[layout.source.code]
    target = by_slot[layout.target.code]
    if source.currency == target.currency:
        raise ValidationError(_("The exchange legs must use different currencies."))

    rate_line = by_slot[layout.rate.code]
    if rate_line.rate_is_individual:
        if rate_line.rate is None or rate_line.rate <= ZERO:
            raise ValidationError(_("The individual rate must be greater than zero."))
        rate = quantize_rate(rate_line.rate)
    else:
        resolved = resolve_exchange_rate(
            operation_type,
            source_currency=source.currency,
            target_currency=target.currency,
            cash_desk_id=cash_desk_id,
            at=at,
        )
        if resolved is None or resolved <= ZERO:
            raise ValidationError(
                _("No rate is available for %(source)s/%(target)s.")
                % {"source": source.currency, "target": target.currency}
            )
        rate = quantize_rate(resolved)

    if layout.computation == SlotComputation.MULTIPLY:
        amount = entered.amount * rate
    elif layout.computation == SlotComputation.DIVIDE:
        amount = entered.amount / rate
    else:
        raise ValidationError(
            _("The exchange operation type '%(code)s' has an invalid computation.")
            % {"code": operation_type.code}
        )
    amount = quantize_amount(amount, derived.currency)

    rate_type = (operation_type.rate_type or "").strip()
    is_individual = rate_line.rate_is_individual
    derived_is_rate_slot = layout.rate.code == layout.derived.code

    result: list[SlotValue] = []
    for line in lines:
        if line.slot == layout.derived.code:
            result.append(
                replace(
                    line,
                    amount=amount,
                    rate=rate if derived_is_rate_slot else None,
                    rate_type=rate_type if derived_is_rate_slot else "",
                    rate_is_individual=is_individual if derived_is_rate_slot else False,
                )
            )
        elif line.slot == layout.rate.code:
            result.append(
                replace(
                    line,
                    rate=rate,
                    rate_type=rate_type,
                    rate_is_individual=is_individual,
                )
            )
        else:
            result.append(replace(line, rate=None, rate_type="", rate_is_individual=False))
    return tuple(result)

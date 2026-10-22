"""The operation engine: validate, build postings, apply them, keep balances.

Posting is atomic: within a single transaction the engine resolves the plan
(a registered handler or the declarative template), locks the affected cash
balance rows, rejects any overdraft, writes the operation journal and updates
the balances. Nothing is half-posted.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from modules.common.backend import outbox
from modules.operations.backend.client_data import enforce_client_data
from modules.operations.backend.models import (
    CashBalance,
    Movement,
    Operation,
    OperationLine,
    OperationNumberSequence,
    OperationType,
)
from modules.operations.backend.preparation import prepare_operation
from modules.operations.backend.registers import RegisterCode
from modules.operations.backend.registry import operation_type_registry
from modules.operations.contracts.dto import (
    MovementSpec,
    OperationContext,
    OperationRequest,
    OperationTypeDTO,
    PostingPlan,
    SlotValue,
)

ZERO = Decimal("0")


def post_operation(
    *,
    operation_type: OperationType,
    cash_desk_id: int,
    shift_id: int,
    cashier_id: int,
    lines: Iterable[SlotValue],
    client_name: str = "",
    client_document: str = "",
    comment: str = "",
    idempotency_key: str = "",
    basis_slot: str = "",
) -> Operation:
    """Post an operation and return the journal document.

    Re-posting with the same ``idempotency_key`` on the same cash desk returns
    the already posted operation instead of creating a duplicate.
    """
    if not operation_type.is_active:
        raise ValidationError(_("The operation type is not active."))

    if idempotency_key:
        existing = _find_by_idempotency_key(cash_desk_id, idempotency_key)
        if existing is not None:
            return existing

    prepared = prepare_operation(
        operation_type=operation_type,
        cash_desk_id=cash_desk_id,
        lines=tuple(lines),
        basis_slot=basis_slot,
    )
    enforce_client_data(
        prepared.client_data,
        client_name=client_name,
        client_document=client_document,
    )
    line_values = prepared.lines
    request = OperationRequest(
        operation_type=_to_dto(operation_type),
        context=OperationContext(
            cash_desk_id=cash_desk_id,
            shift_id=shift_id,
            cashier_id=cashier_id,
            operation_type_code=operation_type.code,
            kind=operation_type.kind,
        ),
        lines=line_values,
    )
    plan = _build_plan(operation_type, request)
    if not plan.movements:
        raise ValidationError(_("The operation produced no postings."))

    try:
        with transaction.atomic():
            if idempotency_key:
                existing = _find_by_idempotency_key(cash_desk_id, idempotency_key)
                if existing is not None:
                    return existing
            return _persist(
                operation_type=operation_type,
                cash_desk_id=cash_desk_id,
                shift_id=shift_id,
                cashier_id=cashier_id,
                lines=line_values,
                movements=plan.movements,
                client_name=client_name,
                client_document=client_document,
                comment=comment,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        # A concurrent request won the idempotency race; return its operation.
        if idempotency_key:
            existing = _find_by_idempotency_key(cash_desk_id, idempotency_key)
            if existing is not None:
                return existing
        raise


def reverse_operation(
    *,
    operation: Operation,
    cashier_id: int,
    shift_id: int,
    comment: str = "",
    idempotency_key: str = "",
) -> Operation:
    """Reverse a posted operation by posting the opposite movements.

    The original document is kept and marked ``reversed``; the reversal is a new
    document that references it. A reversal cannot itself be reversed.
    """
    if operation.reversal_of_id is not None:
        raise ValidationError(_("A reversal operation cannot be reversed."))
    if operation.status != Operation.Status.POSTED:
        raise ValidationError(_("Only a posted operation can be reversed."))
    if operation.reversals.exists():
        raise ValidationError(_("The operation has already been reversed."))
    if idempotency_key:
        existing = _find_by_idempotency_key(operation.cash_desk_id, idempotency_key)
        if existing is not None:
            return existing

    movements = tuple(
        MovementSpec(register=m.register, currency=m.currency, amount=-m.amount)
        for m in operation.movements.all()
    )
    lines = tuple(
        SlotValue(
            slot=line.slot,
            currency=line.currency,
            amount=-line.amount,
            rate=line.rate,
            rate_type=line.rate_type,
            rate_is_individual=line.rate_is_individual,
        )
        for line in operation.lines.all()
    )

    with transaction.atomic():
        reversal = _persist(
            operation_type=operation.operation_type,
            cash_desk_id=operation.cash_desk_id,
            shift_id=shift_id,
            cashier_id=cashier_id,
            lines=lines,
            movements=movements,
            client_name=operation.client_name,
            client_document=operation.client_document,
            comment=comment,
            idempotency_key=idempotency_key,
            reversal_of=operation,
        )
        operation.status = Operation.Status.REVERSED
        operation.save(update_fields=["status", "updated_at"])
        outbox.publish(
            "operations.operation.reversed",
            {
                "operation_id": operation.id,
                "reversal_id": reversal.id,
                "cash_desk_id": operation.cash_desk_id,
            },
        )
        return reversal


# --------------------------------------------------------------------------- #
# Posting plan
# --------------------------------------------------------------------------- #
def _build_plan(operation_type: OperationType, request: OperationRequest) -> PostingPlan:
    handler = operation_type_registry.get_handler(operation_type.code)
    if handler is not None:
        return handler.handle(request)
    if operation_type.template:
        return _plan_from_template(operation_type, request)
    raise ValidationError(
        _("The operation type '%(code)s' has no handler and no template.")
        % {"code": operation_type.code}
    )


def _plan_from_template(operation_type: OperationType, request: OperationRequest) -> PostingPlan:
    """Turn a declarative posting template into a plan.

    The template is ``{"movements": [{"register", "slot", "sign"}]}``: every
    movement takes its currency and amount from the referenced slot line and
    applies ``sign`` (default ``1``).
    """
    specs: list[MovementSpec] = []
    for movement in operation_type.template.get("movements", []):
        slot_code = movement["slot"]
        slot_lines = [line for line in request.lines if line.slot == slot_code]
        if not slot_lines:
            raise ValidationError(
                _("The template references an unfilled slot '%(slot)s'.") % {"slot": slot_code}
            )
        for line in slot_lines:
            specs.append(
                MovementSpec(
                    register=movement["register"],
                    currency=line.currency,
                    amount=line.amount * int(movement.get("sign", 1)),
                )
            )
    return PostingPlan(movements=tuple(specs))


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def _persist(
    *,
    operation_type: OperationType,
    cash_desk_id: int,
    shift_id: int,
    cashier_id: int,
    lines: tuple[SlotValue, ...],
    movements: tuple[MovementSpec, ...],
    client_name: str,
    client_document: str,
    comment: str,
    idempotency_key: str,
    reversal_of: Operation | None = None,
) -> Operation:
    _apply_cash_deltas(cash_desk_id, _cash_deltas(movements))

    operation = Operation.objects.create(
        operation_type=operation_type,
        number=_next_number(cash_desk_id),
        cash_desk_id=cash_desk_id,
        shift_id=shift_id,
        cashier_id=cashier_id,
        idempotency_key=idempotency_key,
        client_name=client_name,
        client_document=client_document,
        comment=comment,
        posted_at=timezone.now(),
        reversal_of=reversal_of,
    )
    for line in lines:
        OperationLine.objects.create(
            operation=operation,
            slot=line.slot,
            currency=line.currency,
            amount=line.amount,
            rate=line.rate,
            rate_type=line.rate_type,
            rate_is_individual=line.rate_is_individual,
        )
    for movement in movements:
        Movement.objects.create(
            operation=operation,
            register=movement.register,
            cash_desk_id=cash_desk_id,
            currency=movement.currency,
            operation_type_code=operation_type.code,
            amount=movement.amount,
        )
    outbox.publish(
        "operations.operation.posted",
        {
            "operation_id": operation.id,
            "operation_type": operation_type.code,
            "number": operation.number,
            "cash_desk_id": cash_desk_id,
            "shift_id": shift_id,
            "reversal_of_id": reversal_of.id if reversal_of is not None else None,
        },
    )
    return operation


def _cash_deltas(movements: Iterable[MovementSpec]) -> dict[str, Decimal]:
    """Net change of the cash register per currency."""
    deltas: dict[str, Decimal] = {}
    for movement in movements:
        if movement.register == RegisterCode.CASH:
            deltas[movement.currency] = deltas.get(movement.currency, ZERO) + movement.amount
    return deltas


def _apply_cash_deltas(cash_desk_id: int, deltas: dict[str, Decimal]) -> None:
    """Update the cash balances, rejecting any overdraft.

    The rows are locked in a deterministic (sorted) order so concurrent postings
    on the same cash desk cannot deadlock.
    """
    if not deltas:
        return
    currencies = sorted(deltas)
    for currency in currencies:
        CashBalance.objects.get_or_create(cash_desk_id=cash_desk_id, currency=currency)
    balances = {
        balance.currency: balance
        for balance in CashBalance.objects.select_for_update()
        .filter(cash_desk_id=cash_desk_id, currency__in=currencies)
        .order_by("currency")
    }
    for currency in currencies:
        balance = balances[currency]
        new_amount = balance.amount + deltas[currency]
        if new_amount < 0:
            raise ValidationError(
                _("Insufficient cash: %(currency)s balance at the cash desk is %(amount)s.")
                % {"currency": currency, "amount": balance.amount}
            )
        balance.amount = new_amount
        balance.save(update_fields=["amount", "updated_at"])


def _next_number(cash_desk_id: int) -> int:
    OperationNumberSequence.objects.get_or_create(cash_desk_id=cash_desk_id)
    sequence = OperationNumberSequence.objects.select_for_update().get(cash_desk_id=cash_desk_id)
    sequence.last_number += 1
    sequence.save(update_fields=["last_number"])
    return sequence.last_number


def _find_by_idempotency_key(cash_desk_id: int, idempotency_key: str) -> Operation | None:
    return Operation.objects.filter(
        cash_desk_id=cash_desk_id, idempotency_key=idempotency_key
    ).first()


def _to_dto(operation_type: OperationType) -> OperationTypeDTO:
    return OperationTypeDTO(
        code=operation_type.code,
        name=operation_type.name,
        kind=operation_type.kind,
        is_external=operation_type.is_external,
        requires_client=operation_type.requires_client,
        form=operation_type.form,
        rate_principle=operation_type.rate_principle,
        rate_type=operation_type.rate_type,
    )

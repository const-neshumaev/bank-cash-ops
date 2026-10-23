"""Bridge from cash operations to the ``printing`` module.

The operation owns the print configuration (which form it prints) while the
``printing`` module owns the templates, numbering and rendered files. The
operation is passed as an immutable snapshot, so no table of another module is
read.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from django.utils import timezone

from modules.common.contracts import registry
from modules.core.contracts import BANK_SETTINGS, ORG_DIRECTORY
from modules.operations.backend.models import Operation
from modules.printing.contracts import (
    PRINT_DOCUMENT_SERVICE,
    PrintBinding,
    PrintDocumentInfo,
    PrintOperation,
    PrintOperationLine,
)
from modules.references.contracts import REFERENCE_DIRECTORY

logger = logging.getLogger(__name__)


def render_print_documents(
    operation: Operation, *, user_id: int | None = None
) -> tuple[PrintDocumentInfo, ...]:
    """Render the operation's configured print forms and store the documents."""
    bindings = tuple(
        PrintBinding(document_type=config.document_type, template=config.template_code)
        for config in operation.operation_type.print_configs.filter(is_active=True)
    )
    if not bindings:
        return ()
    service = registry.get(PRINT_DOCUMENT_SERVICE)
    return service.render_operation(build_print_operation(operation), bindings, user_id=user_id)


def operation_ids_with_documents(operation_ids: Iterable[int]) -> set[int]:
    """Return the subset of operations that already have printed documents."""
    try:
        service = registry.get(PRINT_DOCUMENT_SERVICE)
    except LookupError:
        return set()
    return service.operation_ids_with_documents(operation_ids)


def build_print_operation(operation: Operation) -> PrintOperation:
    """Build the snapshot a print variable provider works with."""
    org = registry.get(ORG_DIRECTORY)
    cash_desk = org.get_cash_desk(operation.cash_desk_id)
    references = registry.get(REFERENCE_DIRECTORY)
    settings = registry.get(BANK_SETTINGS).get_settings(timezone.localdate(operation.posted_at))
    slots = {slot.code: slot for slot in operation.operation_type.slots.all()}

    lines: list[PrintOperationLine] = []
    for line in operation.lines.all():
        currency = references.get_currency(line.currency)
        slot = slots.get(line.slot)
        lines.append(
            PrintOperationLine(
                slot=line.slot,
                slot_name=slot.localized_name() if slot is not None else line.slot,
                currency=line.currency,
                currency_name=currency.name if currency is not None else line.currency,
                amount=line.amount,
                rate=line.rate,
                rate_type=line.rate_type,
                rate_is_individual=line.rate_is_individual,
            )
        )

    return PrintOperation(
        id=operation.id,
        number=operation.number,
        operation_type_code=operation.operation_type.code,
        operation_type_name=operation.operation_type.localized_name(),
        operation_kind=operation.operation_type.kind,
        cash_desk_id=operation.cash_desk_id,
        cash_desk_name=cash_desk.name if cash_desk is not None else "",
        cash_desk_code=cash_desk.code if cash_desk is not None else "",
        branch_name=cash_desk.branch_name if cash_desk is not None else "",
        bank_name=cash_desk.bank_name if cash_desk is not None else "",
        cashier_id=operation.cashier_id,
        posted_at=operation.posted_at,
        client_name=operation.client_name,
        client_document=operation.client_document,
        comment=operation.comment,
        base_currency=settings.base_currency,
        lines=tuple(lines),
    )

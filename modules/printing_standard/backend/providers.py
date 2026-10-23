"""Variable providers of the baseline cash receipt templates.

A provider is the developer-owned part of a print form: it knows which
substitution variables the form offers and how to derive their values from an
operation. The bank administrator owns only the Word file.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.printing.contracts import (
    PrintDocumentHeader,
    PrintOperation,
    PrintOperationLine,
    PrintVariable,
)


class CashReceiptProvider:
    """Variables of a cash receipt for an exchange operation.

    The baseline exchange operations (currency purchase, sale and conversion)
    fill the ``received`` and ``issued`` slots, so one provider serves all three
    forms; the operation type name printed by the receipt tells them apart.
    """

    variables: tuple[PrintVariable, ...] = (
        PrintVariable("bank_name", _("Name of the bank (the root branch).")),
        PrintVariable("branch_name", _("Name of the branch that owns the cash desk.")),
        PrintVariable("cash_desk", _("Cash desk or exchange office name and code.")),
        PrintVariable("cash_desk_name", _("Cash desk or exchange office name.")),
        PrintVariable("cash_desk_code", _("Cash desk or exchange office internal code.")),
        PrintVariable("operation_type", _("Operation type name (purchase, sale, conversion).")),
        PrintVariable("operation_kind", _("Operation kind (income, expense, exchange).")),
        PrintVariable("operation_date", _("Date of the operation (DD.MM.YYYY).")),
        PrintVariable("operation_time", _("Time of the operation (HH:MM:SS).")),
        PrintVariable(
            "operation_datetime", _("Date and time of the operation (DD.MM.YYYY HH:MM:SS).")
        ),
        PrintVariable("received_amount", _("Amount received from the client.")),
        PrintVariable("received_currency", _("Name of the currency received from the client.")),
        PrintVariable(
            "received_currency_code", _("ISO code of the currency received from the client.")
        ),
        PrintVariable("issued_amount", _("Amount issued to the client.")),
        PrintVariable("issued_currency", _("Name of the currency issued to the client.")),
        PrintVariable("issued_currency_code", _("ISO code of the currency issued to the client.")),
        PrintVariable("rate", _("Applied exchange rate.")),
        PrintVariable("document_number", _("Number of this printed document.")),
        PrintVariable("operation_number", _("Unique number of the cash operation.")),
        PrintVariable("client_name", _("Client name (when the operation requires client data).")),
        PrintVariable(
            "client_document", _("Client identity document (when client data is required).")
        ),
        PrintVariable("comment", _("Comment of the operation.")),
    )

    def build(self, operation: PrintOperation, document: PrintDocumentHeader) -> dict:
        received = _line(operation, "received")
        issued = _line(operation, "issued")
        local = timezone.localtime(_aware(operation.posted_at))
        return {
            "bank_name": operation.bank_name,
            "branch_name": operation.branch_name,
            "cash_desk": _cash_desk_label(operation),
            "cash_desk_name": operation.cash_desk_name,
            "cash_desk_code": operation.cash_desk_code,
            "operation_type": operation.operation_type_name,
            "operation_kind": str(_KIND_NAMES.get(operation.operation_kind, _("Exchange"))),
            "operation_date": local.strftime("%d.%m.%Y"),
            "operation_time": local.strftime("%H:%M:%S"),
            "operation_datetime": local.strftime("%d.%m.%Y %H:%M:%S"),
            "received_amount": _money(received.amount if received else None),
            "received_currency": received.currency_name if received else "",
            "received_currency_code": received.currency if received else "",
            "issued_amount": _money(issued.amount if issued else None),
            "issued_currency": issued.currency_name if issued else "",
            "issued_currency_code": issued.currency if issued else "",
            "rate": _rate(operation),
            "document_number": str(document.number),
            "operation_number": str(operation.number),
            "client_name": operation.client_name,
            "client_document": operation.client_document,
            "comment": operation.comment,
        }


_KIND_NAMES = {
    "income": _("Income"),
    "expense": _("Expense"),
    "exchange": _("Exchange"),
    "internal": _("Internal"),
}


def _line(operation: PrintOperation, slot: str) -> PrintOperationLine | None:
    return next((line for line in operation.lines if line.slot == slot), None)


def _rate(operation: PrintOperation) -> str:
    line = next(
        (line for line in operation.lines if line.rate is not None),
        None,
    )
    if line is None or line.rate is None:
        return ""
    quantized = line.rate.quantize(Decimal("0.0001"))
    text = format(quantized, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _money(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value:,.2f}".replace(",", " ")


def _cash_desk_label(operation: PrintOperation) -> str:
    if operation.cash_desk_code and operation.cash_desk_name:
        return f"{operation.cash_desk_name} ({operation.cash_desk_code})"
    return operation.cash_desk_name or operation.cash_desk_code


def _aware(value: datetime) -> datetime:
    """Return ``value`` as an aware datetime in the current time zone."""
    if timezone.is_aware(value):
        return value
    return timezone.make_aware(value, timezone.get_current_timezone())

"""The operation engine: postings, balances, overdraft, numbering, reversal."""

from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError

from modules.common.backend.models import OutboxEvent
from modules.operations.backend.engine import post_operation, reverse_operation
from modules.operations.backend.models import (
    CashBalance,
    Movement,
    Operation,
    OperationType,
    SlotDef,
)
from modules.operations.contracts.dto import SlotValue

pytestmark = pytest.mark.django_db

CASH_DESK = 7
OTHER_CASH_DESK = 8
SHIFT = 11
CASHIER = 21


def _make_type(code, kind, *, slots=None, template=None, **extra):
    operation_type = OperationType.objects.create(
        code=code,
        name=code,
        kind=kind,
        template=template or {},
        **extra,
    )
    for order, slot in enumerate(slots or []):
        SlotDef.objects.create(
            operation_type=operation_type,
            code=slot["code"],
            name=slot["code"],
            required=slot.get("required", True),
            fixed_currency=slot.get("fixed_currency", ""),
            order=order,
        )
    return operation_type


def _income_type(code="replenishment", currency=""):
    return _make_type(
        code,
        OperationType.Kind.INCOME,
        slots=[{"code": "amount", "fixed_currency": currency}],
        template={
            "movements": [
                {"register": "cash", "slot": "amount", "sign": 1},
                {"register": "turnover", "slot": "amount", "sign": 1},
            ]
        },
    )


def _expense_type(code="cash_out", currency=""):
    return _make_type(
        code,
        OperationType.Kind.EXPENSE,
        slots=[{"code": "amount", "fixed_currency": currency}],
        template={"movements": [{"register": "cash", "slot": "amount", "sign": -1}]},
    )


def _post(operation_type, amount, currency="USD", **extra):
    return post_operation(
        operation_type=operation_type,
        cash_desk_id=CASH_DESK,
        shift_id=SHIFT,
        cashier_id=CASHIER,
        lines=[SlotValue(slot="amount", currency=currency, amount=Decimal(amount))],
        **extra,
    )


def test_template_income_increases_the_cash_balance():
    operation_type = _income_type()

    operation = _post(operation_type, "500")

    balance = CashBalance.objects.get(cash_desk_id=CASH_DESK, currency="USD")
    assert balance.amount == Decimal("500.00")
    assert operation.number == 1
    assert operation.status == Operation.Status.POSTED
    assert operation.movements.count() == 2
    turnover = operation.movements.get(register="turnover")
    assert turnover.operation_type_code == operation_type.code


def test_posting_publishes_an_outbox_event():
    operation = _post(_income_type(), "500")

    event = OutboxEvent.objects.get(topic="operations.operation.posted")
    assert event.payload["operation_id"] == operation.id
    assert event.payload["operation_type"] == "replenishment"


def test_expense_decreases_the_cash_balance():
    _post(_income_type(), "500")

    _post(_expense_type(), "125")

    balance = CashBalance.objects.get(cash_desk_id=CASH_DESK, currency="USD")
    assert balance.amount == Decimal("375.00")


def test_expense_over_the_balance_is_rejected_and_nothing_is_written():
    operation_type = _expense_type()

    with pytest.raises(ValidationError):
        _post(operation_type, "10")

    assert CashBalance.objects.filter(cash_desk_id=CASH_DESK).count() == 0
    assert Operation.objects.count() == 0
    assert Movement.objects.count() == 0


def test_expense_equal_to_the_balance_is_allowed():
    _post(_income_type(), "100")

    _post(_expense_type(), "100")

    balance = CashBalance.objects.get(cash_desk_id=CASH_DESK, currency="USD")
    assert balance.amount == Decimal("0.00")


def test_multi_currency_exchange_posts_both_legs():
    _post(_income_type(), "200", currency="USD")
    operation_type = _make_type(
        "currency_sale",
        OperationType.Kind.EXCHANGE,
        slots=[
            {"code": "received", "fixed_currency": "BYN"},
            {"code": "issued", "fixed_currency": "USD"},
        ],
        template={
            "movements": [
                {"register": "cash", "slot": "received", "sign": 1},
                {"register": "cash", "slot": "issued", "sign": -1},
            ]
        },
    )

    operation = post_operation(
        operation_type=operation_type,
        cash_desk_id=CASH_DESK,
        shift_id=SHIFT,
        cashier_id=CASHIER,
        lines=[
            SlotValue(slot="received", currency="BYN", amount=Decimal("500")),
            SlotValue(slot="issued", currency="USD", amount=Decimal("125")),
        ],
    )

    byn = CashBalance.objects.get(cash_desk_id=CASH_DESK, currency="BYN")
    usd = CashBalance.objects.get(cash_desk_id=CASH_DESK, currency="USD")
    assert byn.amount == Decimal("500.00")
    assert usd.amount == Decimal("75.00")
    assert operation.lines.count() == 2


def test_idempotency_key_returns_the_same_operation():
    operation_type = _income_type()

    first = _post(operation_type, "500", idempotency_key="abc")
    second = _post(operation_type, "500", idempotency_key="abc")

    assert first.pk == second.pk
    assert Operation.objects.count() == 1
    assert Movement.objects.count() == 2
    balance = CashBalance.objects.get(cash_desk_id=CASH_DESK, currency="USD")
    assert balance.amount == Decimal("500.00")


def test_numbers_are_sequential_per_cash_desk():
    operation_type = _income_type()

    first = _post(operation_type, "10")
    second = _post(operation_type, "10")
    other = post_operation(
        operation_type=operation_type,
        cash_desk_id=OTHER_CASH_DESK,
        shift_id=SHIFT,
        cashier_id=CASHIER,
        lines=[SlotValue(slot="amount", currency="USD", amount=Decimal("10"))],
    )

    assert (first.number, second.number) == (1, 2)
    assert other.number == 1


class TestSlotValidation:
    def test_unknown_slot_is_rejected(self):
        operation_type = _income_type()

        with pytest.raises(ValidationError):
            post_operation(
                operation_type=operation_type,
                cash_desk_id=CASH_DESK,
                shift_id=SHIFT,
                cashier_id=CASHIER,
                lines=[SlotValue("mystery", "USD", Decimal("1"))],
            )

    def test_missing_required_slot_is_rejected(self):
        operation_type = _income_type()

        with pytest.raises(ValidationError):
            post_operation(
                operation_type=operation_type,
                cash_desk_id=CASH_DESK,
                shift_id=SHIFT,
                cashier_id=CASHIER,
                lines=[],
            )

    def test_fixed_currency_is_enforced(self):
        operation_type = _income_type(currency="BYN")

        with pytest.raises(ValidationError):
            _post(operation_type, "10", currency="USD")

    def test_duplicate_slot_is_rejected(self):
        operation_type = _income_type()

        with pytest.raises(ValidationError):
            post_operation(
                operation_type=operation_type,
                cash_desk_id=CASH_DESK,
                shift_id=SHIFT,
                cashier_id=CASHIER,
                lines=[
                    SlotValue("amount", "USD", Decimal("1")),
                    SlotValue("amount", "USD", Decimal("2")),
                ],
            )

    def test_inactive_type_is_rejected(self):
        operation_type = _income_type(currency="")
        operation_type.is_active = False
        operation_type.save(update_fields=["is_active"])

        with pytest.raises(ValidationError):
            _post(operation_type, "10")


class TestReversal:
    def test_reversal_negates_the_operation_and_closes_the_original(self):
        original = _post(_income_type(), "500")

        reversal = reverse_operation(operation=original, cashier_id=CASHIER, shift_id=SHIFT)

        original.refresh_from_db()
        assert original.status == Operation.Status.REVERSED
        assert reversal.reversal_of_id == original.pk
        balance = CashBalance.objects.get(cash_desk_id=CASH_DESK, currency="USD")
        assert balance.amount == Decimal("0.00")

    def test_an_operation_cannot_be_reversed_twice(self):
        original = _post(_income_type(), "500")
        reverse_operation(operation=original, cashier_id=CASHIER, shift_id=SHIFT)
        original.refresh_from_db()

        with pytest.raises(ValidationError):
            reverse_operation(operation=original, cashier_id=CASHIER, shift_id=SHIFT)

    def test_reversal_that_would_overdraw_is_rejected(self):
        original = _post(_income_type(), "100")
        _post(_expense_type(), "100")

        with pytest.raises(ValidationError):
            reverse_operation(operation=original, cashier_id=CASHIER, shift_id=SHIFT)

        original.refresh_from_db()
        assert original.status == Operation.Status.POSTED

    def test_reversal_publishes_an_event(self):
        original = _post(_income_type(), "500")

        reverse_operation(operation=original, cashier_id=CASHIER, shift_id=SHIFT)

        assert OutboxEvent.objects.filter(topic="operations.operation.reversed").exists()

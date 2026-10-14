"""The extension SPI: modules declare operation types and handlers."""

from decimal import Decimal

import pytest

from modules.common.contracts import registry as contract_registry
from modules.operations.backend.engine import post_operation
from modules.operations.backend.models import CashBalance, OperationType
from modules.operations.backend.registry import operation_type_registry
from modules.operations.contracts import (
    OPERATION_TYPES_REGISTRY,
    MovementSpec,
    OperationKind,
    OperationTypeSpec,
    PostingPlan,
    SlotValue,
)

pytestmark = pytest.mark.django_db

CODE = "bank.double_income"
SPEC = OperationTypeSpec(code=CODE, name="Custom income", kind=OperationKind.INCOME)


class _DoubleIncomeHandler:
    """A trivial handler that doubles the requested amount into the cash register."""

    def handle(self, request):
        line = request.lines[0]
        return PostingPlan(
            movements=(
                MovementSpec(register="cash", currency=line.currency, amount=line.amount * 2),
            )
        )


@pytest.fixture
def registered_handler():
    operation_type_registry.register(SPEC, _DoubleIncomeHandler())
    yield
    operation_type_registry.unregister(CODE)


def test_registry_is_published_through_the_contract():
    assert contract_registry.get(OPERATION_TYPES_REGISTRY) is operation_type_registry


def test_a_registered_handler_produces_the_plan(registered_handler):
    operation_type = OperationType.objects.create(
        code=CODE, name="Custom income", kind=OperationType.Kind.INCOME
    )

    post_operation(
        operation_type=operation_type,
        cash_desk_id=1,
        shift_id=1,
        cashier_id=1,
        lines=[SlotValue("amount", "USD", Decimal("50"))],
    )

    assert CashBalance.objects.get(cash_desk_id=1, currency="USD").amount == Decimal("100.00")


def test_registering_a_type_twice_is_rejected():
    operation_type_registry.register(SPEC, _DoubleIncomeHandler())
    try:
        with pytest.raises(RuntimeError):
            operation_type_registry.register(SPEC, _DoubleIncomeHandler())
    finally:
        operation_type_registry.unregister(CODE)
